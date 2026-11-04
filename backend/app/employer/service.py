"""雇主业务规则；业务错误继承 ValueError，由 router 转为 HTTP 响应。"""

import uuid

from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.employer.matching import match_score
from app.employer.model import (
    Application,
    Booking,
    InterviewSlot,
    Job,
    JobSkill,
)
from app.employer.schema import (
    ApplicantPublic,
    ApplicationStatusPublic,
    ApplicationStatusUpdate,
    BookingPublic,
    CompanyPublic,
    CompanyUpdate,
    JobCreate,
    JobPublic,
    JobUpdate,
)
from app.users.model import (
    CandidateProfile,
    CandidateSkill,
    EmployerProfile,
    Role,
    User,
    utc_now,
)
from app.users.service import EmployerRoleRequiredError, normalize_skills


class CompanyNotFoundError(ValueError):
    """当前雇主尚未填写公司资料。"""


class CompanyRequiredError(ValueError):
    """发布职位前必须先填写公司资料。"""


class JobNotFoundError(ValueError):
    """职位不存在或已软删除。"""


class JobForbiddenError(ValueError):
    """当前雇主不负责该职位。"""


class JobHasDependentsError(ValueError):
    """职位仍有申请或面试时段，不能删除。"""


class ApplicationNotFoundError(ValueError):
    """申请不存在。"""


def _require_employer(user: User) -> None:
    """拒绝非雇主账户；router 依赖之外在 service 再检查一次。"""
    if user.role != Role.Employer:
        raise EmployerRoleRequiredError("Employer role required")


def _company_public(profile: EmployerProfile) -> CompanyPublic:
    """把公司资料映射为响应结构。"""
    return CompanyPublic(
        user_id=profile.user_id,
        company_name=profile.company_name,
        company_description=profile.company_description,
    )


def get_my_company(session: Session, user: User) -> CompanyPublic:
    """返回当前雇主的公司资料；未填写时 404。"""
    _require_employer(user)
    profile = session.get(EmployerProfile, user.id)
    if profile is None:
        raise CompanyNotFoundError("Company not found")
    return _company_public(profile)


def update_my_company(
    session: Session, user: User, changes: CompanyUpdate
) -> CompanyPublic:
    """只修改本次显式提交的公司资料字段。"""
    _require_employer(user)
    profile = session.get(EmployerProfile, user.id)
    if profile is None:
        raise CompanyNotFoundError("Company not found")
    try:
        for name, value in changes.model_dump(exclude_unset=True).items():
            setattr(profile, name, value)
        session.add(profile)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise

    session.refresh(profile)
    return _company_public(profile)


def _job_public(session: Session, job: Job) -> JobPublic:
    """组合职位字段、公司名称与规范化技能；公司名称以公司资料为准。"""
    profile = session.get(EmployerProfile, job.employer_id)
    skills = session.exec(
        select(JobSkill.name).where(JobSkill.job_id == job.id)
    ).all()
    return JobPublic(
        id=job.id,
        company_name=profile.company_name if profile is not None else "",
        employer_id=job.employer_id,
        title=job.title,
        description=job.description,
        required_skills=sorted(skills),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def create_job(session: Session, user: User, data: JobCreate) -> JobPublic:
    """发布职位并写入规范化技能；公司名称取自当前雇主的公司资料。"""
    _require_employer(user)
    if session.get(EmployerProfile, user.id) is None:
        raise CompanyRequiredError("Company required")

    job = Job(
        employer_id=user.id,
        title=data.title,
        description=data.description,
    )
    session.add(job)
    for name in normalize_skills(data.required_skills):
        session.add(JobSkill(job_id=job.id, name=name))
    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise

    session.refresh(job)
    return _job_public(session, job)


def list_my_jobs(session: Session, user: User) -> list[JobPublic]:
    """列出当前雇主负责的未删除职位，新建的在前。"""
    _require_employer(user)
    jobs = session.exec(
        select(Job).where(
            Job.employer_id == user.id,
            Job.is_deleted.is_(False),
        )
    ).all()
    rows = [_job_public(session, job) for job in jobs]
    return sorted(
        rows,
        key=lambda row: (-row.created_at.timestamp(), str(row.id)),
    )


def _load_owned_job(
    session: Session, user: User, job_id: uuid.UUID, lock: bool = False
) -> Job:
    """读取未删除职位并检查负责雇主；lock=True 时锁住该行。"""
    if lock:
        job = session.exec(
            select(Job).where(Job.id == job_id).with_for_update()
        ).first()
    else:
        job = session.get(Job, job_id)
    if job is None or job.is_deleted:
        raise JobNotFoundError("Job not found")
    if job.employer_id != user.id:
        raise JobForbiddenError("Not the owner of this job")
    return job


def get_my_job(session: Session, user: User, job_id: uuid.UUID) -> JobPublic:
    """返回当前雇主负责的单个职位。"""
    _require_employer(user)
    return _job_public(session, _load_owned_job(session, user, job_id))


def update_job(
    session: Session,
    user: User,
    job_id: uuid.UUID,
    changes: JobUpdate,
) -> JobPublic:
    """修改职位；required_skills 传入即整体替换，空列表表示清空。"""
    _require_employer(user)
    job = _load_owned_job(session, user, job_id)
    fields = changes.model_dump(exclude_unset=True)
    try:
        if "required_skills" in fields:
            session.execute(delete(JobSkill).where(JobSkill.job_id == job.id))
            for name in normalize_skills(fields.pop("required_skills")):
                session.add(JobSkill(job_id=job.id, name=name))
        for name, value in fields.items():
            setattr(job, name, value)
        job.updated_at = utc_now()
        session.add(job)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise

    session.refresh(job)
    session.expire(job, ["skills"])
    return _job_public(session, job)


def delete_job(session: Session, user: User, job_id: uuid.UUID) -> None:
    """软删除职位；有申请或面试时段时冲突且不写入任何内容。"""
    _require_employer(user)
    job = _load_owned_job(session, user, job_id, lock=True)
    try:
        has_application = (
            session.exec(
                select(Application.id).where(Application.job_id == job.id).limit(1)
            ).first()
            is not None
        )
        has_slot = (
            session.exec(
                select(InterviewSlot.id).where(InterviewSlot.job_id == job.id).limit(1)
            ).first()
            is not None
        )
        if has_application or has_slot:
            raise JobHasDependentsError(
                "Job has applications or interview slots"
            )
        job.is_deleted = True
        job.updated_at = utc_now()
        session.add(job)
        session.commit()
    except JobHasDependentsError:
        session.rollback()
        raise
    except SQLAlchemyError:
        session.rollback()
        raise


def _booking_public(session: Session, application_id: uuid.UUID) -> BookingPublic | None:
    """读取申请的面试预约；没有预约返回 None。"""
    booking = session.exec(
        select(Booking).where(Booking.application_id == application_id)
    ).first()
    if booking is None:
        return None
    slot = session.get(InterviewSlot, booking.slot_id)
    if slot is None:
        return None
    return BookingPublic(
        booking_id=booking.id,
        slot_id=slot.id,
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
    )


def list_job_applicants(
    session: Session, user: User, job_id: uuid.UUID
) -> list[ApplicantPublic]:
    """列出职位申请人，按匹配分降序，平级按显示名不区分大小写再按候选人 ID。"""
    _require_employer(user)
    job = _load_owned_job(session, user, job_id)
    required_skills = session.exec(
        select(JobSkill.name).where(JobSkill.job_id == job.id)
    ).all()
    applications = session.exec(
        select(Application).where(Application.job_id == job.id)
    ).all()

    rows: list[ApplicantPublic] = []
    for application in applications:
        profile = session.get(CandidateProfile, application.candidate_id)
        if profile is None:
            continue
        skills = session.exec(
            select(CandidateSkill.name).where(
                CandidateSkill.candidate_id == application.candidate_id
            )
        ).all()
        rows.append(
            ApplicantPublic(
                application_id=application.id,
                candidate_id=application.candidate_id,
                display_name=profile.display_name,
                skills=sorted(skills),
                match_score=match_score(skills, required_skills),
                status=application.status,
                booking=_booking_public(session, application.id),
            )
        )
    rows.sort(
        key=lambda row: (-row.match_score, row.display_name.lower(), str(row.candidate_id))
    )
    return rows


def change_application_status(
    session: Session,
    user: User,
    application_id: uuid.UUID,
    data: ApplicationStatusUpdate,
) -> ApplicationStatusPublic:
    """只修改申请状态；四个状态之间可任意切换，不触碰预约。"""
    _require_employer(user)
    application = session.exec(
        select(Application).where(Application.id == application_id).with_for_update()
    ).first()
    if application is None:
        raise ApplicationNotFoundError("Application not found")
    job = session.get(Job, application.job_id)
    if job is None or job.is_deleted:
        raise JobNotFoundError("Job not found")
    if job.employer_id != user.id:
        raise JobForbiddenError("Not the owner of this job")

    application.status = data.status
    application.updated_at = utc_now()
    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise

    session.refresh(application)
    return ApplicationStatusPublic(
        application_id=application.id,
        job_id=application.job_id,
        candidate_id=application.candidate_id,
        status=application.status,
        updated_at=application.updated_at,
    )
