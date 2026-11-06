"""候选人业务规则；权限、查询与事务集中于此，HTTP 转换留在 router。"""

import uuid
from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, select

from app.candidate.schema import (
    ApplicationPublic,
    BookingPublic,
    ProfileUpdate,
    RecommendedJob,
    SlotPublic,
)
from app.employer.matching import match_score
from app.employer.model import (
    Application,
    ApplicationStatus,
    Booking,
    InterviewSlot,
    Job,
    JobSkill,
)
from app.users.model import (
    CandidateProfile,
    CandidateSkill,
    EmployerProfile,
    Role,
    User,
    utc_now,
)
from app.users.schema import CandidateProfilePublic
from app.users.service import CandidateRoleRequiredError, normalize_skills


class NotFoundError(ValueError):
    """请求的资源不存在。"""


class ForbiddenError(ValueError):
    """当前身份不能访问该资源。"""


class ConflictError(ValueError):
    """操作与当前业务状态冲突。"""


def _require_candidate(user: User) -> None:
    """service 被直接调用时同样检查角色。"""
    if user.role != Role.Candidate:
        raise CandidateRoleRequiredError("Candidate role required")


def _profile(session: Session, candidate_id: uuid.UUID) -> CandidateProfile:
    """资料存在才可访问；身份范围由调用方预先验证。"""
    profile = session.get(CandidateProfile, candidate_id)
    if profile is None:
        raise NotFoundError("Candidate profile not found")
    return profile


def _profile_public(
    session: Session, profile: CandidateProfile
) -> CandidateProfilePublic:
    """显式选择公开给授权读取者的字段。"""
    skills = session.exec(
        select(CandidateSkill.name).where(
            CandidateSkill.candidate_id == profile.user_id
        )
    ).all()
    return CandidateProfilePublic(
        user_id=profile.user_id,
        display_name=profile.display_name,
        resume_text=profile.resume_text,
        skills=sorted(skills),
    )


def get_my_profile(session: Session, user: User) -> CandidateProfilePublic:
    """读取本人的名称、简历及技能。"""
    _require_candidate(user)
    return _profile_public(session, _profile(session, user.id))


def read_profile(
    session: Session, user: User, candidate_id: uuid.UUID
) -> CandidateProfilePublic:
    """本人或有投递关系的雇主可读；不按申请状态撤销关系。"""
    if user.role == Role.Candidate:
        if user.id != candidate_id:
            raise ForbiddenError("Not the owner of this profile")
    elif user.role == Role.Employer:
        related = session.exec(
            select(Application.id)
            .join(Job, Application.job_id == Job.id)
            .where(
                Application.candidate_id == candidate_id,
                Job.employer_id == user.id,
            )
            .limit(1)
        ).first()
        if related is None:
            raise ForbiddenError("No application relationship with this candidate")
    else:
        raise ForbiddenError("Profile access denied")
    return _profile_public(session, _profile(session, candidate_id))


def update_my_profile(
    session: Session, user: User, changes: ProfileUpdate
) -> CandidateProfilePublic:
    """资料与技能一次提交；更新不改变账户或资料归属。"""
    _require_candidate(user)
    profile = _profile(session, user.id)
    fields = changes.model_dump(exclude_unset=True)
    try:
        if "skills" in fields:
            session.execute(
                delete(CandidateSkill).where(CandidateSkill.candidate_id == user.id)
            )
            for name in normalize_skills(fields.pop("skills")):
                session.add(CandidateSkill(candidate_id=user.id, name=name))
        for name, value in fields.items():
            setattr(profile, name, value)
        session.add(profile)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise
    session.refresh(profile)
    session.expire(profile, ["skills"])
    return _profile_public(session, profile)


def _active_job(session: Session, job_id: uuid.UUID, lock: bool = False) -> Job:
    """投递时锁住职位，与雇主删除操作串行化。"""
    statement = select(Job).where(Job.id == job_id)
    job = session.exec(statement.with_for_update() if lock else statement).first()
    if job is None or job.is_deleted:
        raise NotFoundError("Job not found")
    return job


def _recommended_jobs(
    session: Session, user: User, jobs: list[Job]
) -> list[RecommendedJob]:
    """批量加载关联数据；职位数量增加不会增加每职位查询。"""
    profile = _profile(session, user.id)
    if not jobs:
        return []
    ids = [job.id for job in jobs]
    skills: dict[uuid.UUID, list[str]] = {job_id: [] for job_id in ids}
    for job_id, name in session.exec(
        select(JobSkill.job_id, JobSkill.name).where(JobSkill.job_id.in_(ids))
    ):
        skills[job_id].append(name)
    companies = dict(
        session.exec(
            select(EmployerProfile.user_id, EmployerProfile.company_name).where(
                EmployerProfile.user_id.in_({job.employer_id for job in jobs})
            )
        ).all()
    )
    candidate_skills = session.exec(
        select(CandidateSkill.name).where(
            CandidateSkill.candidate_id == profile.user_id
        )
    ).all()
    applied = set(
        session.exec(
            select(Application.job_id).where(
                Application.candidate_id == user.id, Application.job_id.in_(ids)
            )
        ).all()
    )
    return [
        RecommendedJob(
            id=job.id,
            employer_id=job.employer_id,
            title=job.title,
            description=job.description,
            company_name=companies.get(job.employer_id, ""),
            required_skills=sorted(skills[job.id]),
            created_at=job.created_at,
            updated_at=job.updated_at,
            match_score=match_score(candidate_skills, skills[job.id]),
            applied=job.id in applied,
        )
        for job in jobs
    ]


def list_jobs(session: Session, user: User) -> list[RecommendedJob]:
    """全部有效职位按分数降序、标题忽略大小写、稳定 ID 排列。"""
    _require_candidate(user)
    jobs = session.exec(select(Job).where(Job.is_deleted.is_(False))).all()
    return sorted(
        _recommended_jobs(session, user, jobs),
        key=lambda row: (-row.match_score, row.title.lower(), str(row.id)),
    )


def get_job(session: Session, user: User, job_id: uuid.UUID) -> RecommendedJob:
    """返回有效职位及当前候选人的投递标记。"""
    _require_candidate(user)
    return _recommended_jobs(session, user, [_active_job(session, job_id)])[0]


def _owned_application(
    session: Session, user: User, application_id: uuid.UUID, lock: bool = False
) -> Application:
    """先检查角色，再检查申请存在性与所有权。"""
    _require_candidate(user)
    statement = select(Application).where(Application.id == application_id)
    row = session.exec(statement.with_for_update() if lock else statement).first()
    if row is None:
        raise NotFoundError("Application not found")
    if row.candidate_id != user.id:
        raise ForbiddenError("Not the owner of this application")
    return row


def _applications_public(
    session: Session, applications: list[Application]
) -> list[ApplicationPublic]:
    """批量组合职位、公司和预约；保留历史申请。"""
    if not applications:
        return []
    jobs = {
        job.id: job
        for job in session.exec(
            select(Job).where(Job.id.in_({row.job_id for row in applications}))
        ).all()
    }
    companies = dict(
        session.exec(
            select(EmployerProfile.user_id, EmployerProfile.company_name).where(
                EmployerProfile.user_id.in_({job.employer_id for job in jobs.values()})
            )
        ).all()
    )
    bookings = {
        booking.application_id: BookingPublic(
            booking_id=booking.id,
            slot_id=slot.id,
            starts_at=slot.starts_at,
            ends_at=slot.ends_at,
        )
        for booking, slot in session.exec(
            select(Booking, InterviewSlot)
            .join(
                InterviewSlot,
                Booking.slot_id == InterviewSlot.id,
            )
            .where(Booking.application_id.in_([row.id for row in applications]))
        ).all()
    }
    return [
        ApplicationPublic(
            application_id=row.id,
            job_id=row.job_id,
            job_title=jobs[row.job_id].title,
            company_name=companies.get(jobs[row.job_id].employer_id, ""),
            status=row.status,
            created_at=row.created_at,
            booking=bookings.get(row.id),
        )
        for row in applications
    ]


def list_applications(session: Session, user: User) -> list[ApplicationPublic]:
    """只查询本人申请，新申请在前。"""
    _require_candidate(user)
    rows = session.exec(
        select(Application)
        .where(Application.candidate_id == user.id)
        .order_by(Application.created_at.desc(), Application.id)
    ).all()
    return _applications_public(session, rows)


def get_application(
    session: Session, user: User, application_id: uuid.UUID
) -> ApplicationPublic:
    """读取本人申请详情及已有预约。"""
    return _applications_public(
        session, [_owned_application(session, user, application_id)]
    )[0]


def apply(session: Session, user: User, job_id: uuid.UUID) -> ApplicationPublic:
    """数据库唯一约束保证每人每职位只能投递一次。"""
    _require_candidate(user)
    _profile(session, user.id)
    try:
        _active_job(session, job_id, lock=True)
        existing = session.exec(
            select(Application.id).where(
                Application.candidate_id == user.id, Application.job_id == job_id
            )
        ).first()
        if existing is not None:
            raise ConflictError("Already applied")
        application = Application(candidate_id=user.id, job_id=job_id)
        session.add(application)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if (
            session.exec(
                select(Application.id).where(
                    Application.candidate_id == user.id, Application.job_id == job_id
                )
            ).first()
            is not None
        ):
            raise ConflictError("Already applied") from error
        raise
    except (ValueError, SQLAlchemyError):
        session.rollback()
        raise
    session.refresh(application)
    return _applications_public(session, [application])[0]


def _eligible_application(
    session: Session, user: User, application_id: uuid.UUID, lock: bool = False
) -> Application:
    """预约要求本人面试中申请且没有已有预约。"""
    row = _owned_application(session, user, application_id, lock)
    if row.status != ApplicationStatus.Interviewing:
        raise ConflictError("Application must be Interviewing")
    if (
        session.exec(select(Booking.id).where(Booking.application_id == row.id)).first()
        is not None
    ):
        raise ConflictError("Application already booked")
    return row


def available_slots(
    session: Session, user: User, application_id: uuid.UUID
) -> list[SlotPublic]:
    """按申请对应雇主选择未来空闲的 30 分钟时段。"""
    application = _eligible_application(session, user, application_id)
    job = session.get(Job, application.job_id)
    if job is None:
        raise NotFoundError("Job not found")
    slots = session.exec(
        select(InterviewSlot)
        .where(
            InterviewSlot.employer_id == job.employer_id,
            InterviewSlot.starts_at > utc_now(),
            InterviewSlot.id.not_in(select(Booking.slot_id)),
        )
        .order_by(InterviewSlot.starts_at, InterviewSlot.id)
    ).all()
    return [
        SlotPublic(id=slot.id, starts_at=slot.starts_at, ends_at=slot.ends_at)
        for slot in slots
        if slot.ends_at - slot.starts_at == timedelta(minutes=30)
    ]


def book(
    session: Session, user: User, application_id: uuid.UUID, slot_id: uuid.UUID
) -> BookingPublic:
    """申请锁与时段锁跨进程生效，唯一约束防止绕开锁后的重复写入。"""
    try:
        application = _eligible_application(session, user, application_id, lock=True)
        slot = session.exec(
            select(InterviewSlot).where(InterviewSlot.id == slot_id).with_for_update()
        ).first()
        if slot is None:
            raise NotFoundError("Slot not found")
        job = session.get(Job, application.job_id)
        if job is None:
            raise NotFoundError("Job not found")
        if slot.employer_id != job.employer_id:
            raise ForbiddenError("Slot belongs to another employer")
        if slot.starts_at <= utc_now():
            raise ConflictError("Slot is in the past")
        if slot.ends_at - slot.starts_at != timedelta(minutes=30):
            raise ConflictError("Slot must last 30 minutes")
        if (
            session.exec(select(Booking.id).where(Booking.slot_id == slot_id)).first()
            is not None
        ):
            raise ConflictError("Slot already booked")
        booking = Booking(application_id=application.id, slot_id=slot.id)
        session.add(booking)
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if (
            session.exec(select(Booking.id).where(Booking.slot_id == slot_id)).first()
            is not None
        ):
            raise ConflictError("Slot already booked") from error
        if (
            session.exec(
                select(Booking.id).where(Booking.application_id == application_id)
            ).first()
            is not None
        ):
            raise ConflictError("Application already booked") from error
        raise
    except (ValueError, SQLAlchemyError):
        session.rollback()
        raise
    session.refresh(booking)
    return BookingPublic(
        booking_id=booking.id,
        slot_id=slot.id,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
    )
