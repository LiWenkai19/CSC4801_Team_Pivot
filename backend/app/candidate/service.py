import uuid
from collections import defaultdict

from datetime import timedelta, timezone

from sqlalchemy import delete

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from sqlmodel import Session, select

from app.candidate.model import (
    Application,
    ApplicationStatus,
    Booking,
    InterviewSlot,
    Job,
    JobSkill,
)

# 排序及规范化复用共享模块，评分使用独立占位入口
from app.matching import applicant_sort_key, job_sort_key, normalize_skills
from app.matching import SCORE_KIND, placeholder_match_score as match_score

from app.users.model import (
    CandidateProfile,
    CandidateSkill,
    EmployerProfile,
    User,
    Role,
    utc_now,
)

from app.candidate.profile_schema import CandidateProfilePublic, CandidateProfileUpdate


# FlowError 表示可以识别的业务失败，供上层决定如何响应
class FlowError(ValueError):
    def __init__(self, status: int, message: str):
        self.status = status
        # 调用父类 ValueError 保存错误文字；以后 str(error) 就能得到这段文字。
        super().__init__(message)


def utc(value):
    return (
        value.replace(tzinfo=timezone.utc)
        # 这里的条件决定选择/保留哪些值；不满足条件的记录不会进入结果
        if value.tzinfo is None
        # 条件表达式的备用值：前面的条件不成立时使用它
        else value.astimezone(timezone.utc)
    )


def owned_profile(
    session: Session,
    user: User,
    candidate_id: uuid.UUID,
) -> CandidateProfile:
    if candidate_id != user.id:
        raise FlowError(403, "Private candidate profile")
    profile = session.get(CandidateProfile, candidate_id)
    if profile is None:
        raise FlowError(404, "Candidate profile not found; complete your profile first")
    return profile


def profile_public(profile: CandidateProfile) -> CandidateProfilePublic:
    return CandidateProfilePublic(
        user_id=profile.user_id,
        display_name=profile.display_name,
        resume_text=profile.resume_text,
        skills=sorted(s.name for s in profile.skills),
    )


def update_profile(
    session: Session,
    user: User,
    candidate_id: uuid.UUID,
    payload: CandidateProfileUpdate,
):
    profile = owned_profile(session, user, candidate_id)
    changes = payload.model_dump(exclude_unset=True)
    try:
        if "skills" in changes:
            # 执行前面构造的数据库查询/语句，用户值由 ORM 绑定
            session.execute(
                delete(CandidateSkill).where(
                    CandidateSkill.candidate_id == candidate_id
                )
            )
            # pop 把 skills 从 changes 取出并移除：技能是另一张表，不能像普通文字字段一样 setattr。
            for name in normalize_skills(changes.pop("skills")):
                # 把对象加入数据库工作区；这一行本身还不等于提交成功
                session.add(CandidateSkill(candidate_id=candidate_id, name=name))
        for name, value in changes.items():
            # 根据字段名称设置对象属性，用于只修改已提交的资料字段
            setattr(profile, name, value)
        # 把对象加入数据库工作区；这一行本身还不等于提交成功
        session.add(profile)
        # 提交整个事务；成功后数据库中的修改才正式生效
        session.commit()
    except SQLAlchemyError:
        # 撤销本次未成功提交的修改，并恢复 Session 的可用状态
        session.rollback()
        # raise 将当前异常继续交给调用者，不能吞掉无法解释的数据库故障
        raise
    # 从数据库重新读取对象，取得实际保存后的字段值
    session.refresh(profile)
    # profile.skills 是 ORM 关系，可能缓存了旧列表；删除/新增技能后必须让它重新读取，不能返回旧技能。
    # 使已缓存的字段失效，下一次访问重新查询数据库
    session.expire(profile, ["skills"])
    return profile_public(profile)


def active_job(session: Session, job_id: uuid.UUID) -> Job:
    job = session.get(Job, job_id)
    if job is None or job.is_deleted:
        raise FlowError(404, "Job not found")
    return job


def job_public(session: Session, job: Job, profile: CandidateProfile) -> dict:
    required = list(
        session.exec(select(JobSkill.name).where(JobSkill.job_id == job.id))
    )
    company = session.get(EmployerProfile, job.employer_id)
    applied = session.exec(
        select(Application.id).where(
            Application.job_id == job.id,
            Application.candidate_id == profile.user_id,
        )
    ).first()
    return dict(
        id=job.id,
        employer_id=job.employer_id,
        title=job.title,
        description=job.description,
        company_name=company.company_name,
        required_skills=sorted(required),
        score=match_score([s.name for s in profile.skills], required),
        score_kind=SCORE_KIND,
        applied=applied is not None,
    )


def list_jobs(session: Session, user: User):
    profile = owned_profile(session, user, user.id)
    return list_recommendations(session, profile, match_score, SCORE_KIND)


def apply(session: Session, user: User, job_id: uuid.UUID):
    # 先确认目标 ID 就是登录用户，再读取资料；不能让他人拿到私有简历
    owned_profile(session, user, user.id)
    job = session.exec(select(Job).where(Job.id == job_id).with_for_update()).first()
    if job is None or job.is_deleted:
        raise FlowError(404, "Job not found")
    duplicate = select(Application).where(
        Application.candidate_id == user.id,
        Application.job_id == job_id,
    )
    if session.exec(duplicate).first():
        raise FlowError(409, "Already applied")
    application = Application(candidate_id=user.id, job_id=job_id)
    try:
        # 把对象加入数据库工作区；这一行本身还不等于提交成功
        session.add(application)
        # 提交整个事务；成功后数据库中的修改才正式生效
        session.commit()
    except IntegrityError:
        # 撤销本次未成功提交的修改，并恢复 Session 的可用状态
        session.rollback()
        if session.exec(duplicate).first():
            raise FlowError(409, "Already applied") from None
        # raise 将当前异常继续交给调用者，不能吞掉无法解释的数据库故障
        raise
    except SQLAlchemyError:
        # 撤销本次未成功提交的修改，并恢复 Session 的可用状态
        session.rollback()
        # raise 将当前异常继续交给调用者，不能吞掉无法解释的数据库故障
        raise
    return application_public(session, application)


def owned_application(
    session: Session,
    user: User,
    application_id: uuid.UUID,
    lock=False,
):
    query = select(Application).where(Application.id == application_id)
    if lock:
        query = query.with_for_update()
    application = session.exec(query).first()
    if application is None:
        raise FlowError(404, "Application not found")
    if application.candidate_id != user.id:
        raise FlowError(403, "Private application")
    return application


def application_public(session: Session, application: Application):
    job = session.get(Job, application.job_id)
    company = session.get(EmployerProfile, job.employer_id)
    booking = session.exec(
        select(Booking).where(Booking.application_id == application.id)
    ).first()
    info = None
    if booking:
        slot = session.get(InterviewSlot, booking.slot_id)
        info = dict(
            id=booking.id,
            slot_id=slot.id,
            starts_at=utc(slot.starts_at),
            ends_at=utc(slot.ends_at),
        )
    return dict(
        id=application.id,
        job_id=job.id,
        title=job.title,
        company_name=company.company_name,
        status=application.status,
        booking=info,
    )


def eligible_application(
    session: Session,
    user: User,
    application_id: uuid.UUID,
    lock=False,
):
    application = owned_application(session, user, application_id, lock)
    if application.status != ApplicationStatus.Interviewing:
        raise FlowError(409, "Application must be Interviewing")
    if session.exec(
        select(Booking).where(Booking.application_id == application.id)
    ).first():
        raise FlowError(409, "Application already booked")
    return application


def available_slots(session: Session, user: User, application_id: uuid.UUID):
    application = eligible_application(session, user, application_id)
    job = session.get(Job, application.job_id)
    occupied = select(Booking.slot_id)
    slots = session.exec(
        select(InterviewSlot).where(
            InterviewSlot.employer_id == job.employer_id,
            InterviewSlot.id.not_in(occupied),
        )
    )
    return sorted(
        [
            dict(id=s.id, starts_at=utc(s.starts_at), ends_at=utc(s.ends_at))
            for s in slots
            # 这里的条件决定选择/保留哪些值；不满足条件的记录不会进入结果
            if utc(s.starts_at) > utc_now()
            # and 表示还必须同时满足这一条条件
            and utc(s.ends_at) - utc(s.starts_at) == timedelta(minutes=30)
        ],
        # 排序时调用此函数/表达式产生比较依据
        key=lambda row: (row["starts_at"], str(row["id"])),
    )


# 并发示例：Alice 和 Bob 同时抢同一时段。先拿到时段行锁的人提交预约，另一人等待后看到已占用。
# 两个唯一约束是最后防线：即使其他代码未按约定加锁，也不能提交重复 application_id 或 slot_id。
def book(session: Session, user: User, application_id: uuid.UUID, slot_id: uuid.UUID):
    try:
        application = eligible_application(session, user, application_id, lock=True)
        slot = session.exec(
            select(InterviewSlot).where(InterviewSlot.id == slot_id).with_for_update()
        ).first()
        if slot is None:
            raise FlowError(404, "Slot not found")
        job = session.get(Job, application.job_id)
        if slot.employer_id != job.employer_id:
            raise FlowError(403, "Slot belongs to another employer")
        if utc(slot.starts_at) <= utc_now():
            raise FlowError(409, "Slot is in the past")
        if utc(slot.ends_at) - utc(slot.starts_at) != timedelta(minutes=30):
            raise FlowError(409, "Slot must last 30 minutes")
        if session.exec(select(Booking).where(Booking.slot_id == slot_id)).first():
            raise FlowError(409, "Slot already booked")
        booking = Booking(application_id=application_id, slot_id=slot_id)
        # 把对象加入数据库工作区；这一行本身还不等于提交成功
        session.add(booking)
        # 提交整个事务；成功后数据库中的修改才正式生效
        session.commit()
    except IntegrityError:
        # 撤销本次未成功提交的修改，并恢复 Session 的可用状态
        session.rollback()
        if session.exec(select(Booking).where(Booking.slot_id == slot_id)).first():
            raise FlowError(409, "Slot already booked") from None
        if session.exec(
            select(Booking).where(Booking.application_id == application_id)
        ).first():
            raise FlowError(409, "Application already booked") from None
        # raise 将当前异常继续交给调用者，不能吞掉无法解释的数据库故障
        raise
    except (FlowError, SQLAlchemyError):
        # 撤销本次未成功提交的修改，并恢复 Session 的可用状态
        session.rollback()
        # raise 将当前异常继续交给调用者，不能吞掉无法解释的数据库故障
        raise
    return application_public(session, application)["booking"]


def employer_applicants(session: Session, user: User, job_id: uuid.UUID):
    """雇主模块的共享读取接口；永远不包含私有简历。"""
    job = session.get(Job, job_id)
    if job is None:
        raise FlowError(404, "Job not found")
    if job.employer_id != user.id:
        raise FlowError(403, "Job belongs to another employer")
    required = list(
        session.exec(select(JobSkill.name).where(JobSkill.job_id == job.id))
    )
    rows = []
    for application in session.exec(
        select(Application).where(Application.job_id == job.id)
    ):
        profile = session.get(CandidateProfile, application.candidate_id)
        skills = sorted(s.name for s in profile.skills)
        rows.append(
            dict(
                candidate_id=profile.user_id,
                display_name=profile.display_name,
                skills=skills,
                score=match_score(skills, required),
                score_kind=SCORE_KIND,
                # 用 ** 展开已有字典的键值，合并到正在组装的返回数据中
                **application_public(session, application),
            )
        )
    return sorted(rows, key=applicant_sort_key)


# 批量推荐与简历授权放在同一业务服务层，供路由使用。
def _chunks(values, size=500):
    # 将 ID 列表分成每组最多 500 个，避免一次 IN 查询携带过多参数。
    # yield 每次交出一组；调用方循环时才继续产生下一组。
    for start in range(0, len(values), size):
        yield values[start:start + size]


def list_recommendations(session: Session, profile: CandidateProfile, scorer, score_kind):
    # 先一次读取未删除的职位；这里不会把软删除职位放进推荐结果。
    jobs = list(session.exec(select(Job).where(Job.is_deleted.is_(False))))
    if not jobs:
        # 没有职位就直接返回空列表，避免后续多余的数据库查询。
        return []
    # 列表推导式提取 ID；集合去重，让同一雇主只需读取一次。
    job_ids = [job.id for job in jobs]
    employer_ids = list({job.employer_id for job in jobs})
    # 三个容器分别按职位保存技能、保存已申请职位、按雇主保存公司名称。
    # defaultdict(list) 遇到尚无技能的职位时自动提供空列表。
    skills = defaultdict(list)
    applications = set()
    companies = {}
    for chunk in _chunks(job_ids):
        # 每批一次读取全部职位技能，而不是每个职位单独查一次数据库。
        for skill in session.exec(select(JobSkill).where(JobSkill.job_id.in_(chunk))):
            skills[skill.job_id].append(skill.name)
        # 只取当前候选人的申请，避免把其他人的投递状态显示给当前用户。
        applications.update(session.exec(select(Application.job_id).where(
            Application.candidate_id == profile.user_id, Application.job_id.in_(chunk),
        )))
    for chunk in _chunks(employer_ids):
        # 构建 {雇主 ID: 公司名称}，之后组装职位时可以直接查找。
        companies.update({row.user_id: row.company_name for row in session.exec(
            select(EmployerProfile).where(EmployerProfile.user_id.in_(chunk))
        )})
    # 候选人的技能整次请求只读取一次，交给每个职位的评分函数。
    candidate_skills = list(session.exec(select(CandidateSkill.name).where(
        CandidateSkill.candidate_id == profile.user_id
    )))
    rows = []
    for job in jobs:
        # 组合接口需要的字段；scorer 当前是占位评分，applied 来自本人申请集合。
        required = skills[job.id]
        rows.append(dict(id=job.id, employer_id=job.employer_id, title=job.title,
                         description=job.description, company_name=companies[job.employer_id],
                         required_skills=sorted(required), score=scorer(candidate_skills, required),
                         score_kind=score_kind, applied=job.id in applications))
    # job_sort_key 负责统一排序，评分与同分规则由该函数决定。
    return sorted(rows, key=job_sort_key)


def readable_profile(
    session: Session, user: User, candidate_id: uuid.UUID,
) -> CandidateProfile:
    # 第一层角色检查：候选人只能请求自己的 ID；雇主还需要在下方检查申请关系。
    if user.role != Role.Employer and not (
        user.role == Role.Candidate and user.id == candidate_id
    ):
        raise FlowError(403, "Candidate profiles are readable by their owner or employers")
    # 分别读取账号和简历。目标不存在、不是候选人或尚无资料时都返回 404。
    candidate = session.get(User, candidate_id)
    profile = session.get(CandidateProfile, candidate_id)
    if candidate is None or candidate.role != Role.Candidate or profile is None:
        raise FlowError(404, "Candidate profile not found")
    if user.role == Role.Employer:
        # 将申请关联到职位，再同时限制候选人 ID 和职位所属雇主 ID。
        # limit(1) 只需要判断是否存在一条符合条件的申请，无需取出所有申请。
        application = session.exec(
            select(Application.id)
            .join(Job, Application.job_id == Job.id)
            .where(Application.candidate_id == candidate_id, Job.employer_id == user.id)
            .limit(1)
        ).first()
        if application is None:
            # 已登录雇主也不能查看没有申请自己职位的候选人。
            raise FlowError(403, "Candidate has not applied to your jobs")
    # 两层检查都通过后才把简历交给调用方；是否返回给前端由路由负责。
    return profile
