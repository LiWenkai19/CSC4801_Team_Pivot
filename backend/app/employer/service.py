"""雇主业务规则；业务错误继承 ValueError，由 router 转为 HTTP 响应。"""

import uuid

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, select

from app.employer import adapters
from app.employer.model import EmployerCompany, Job, JobSkill
from app.employer.schema import (
    ApplicationStatusPublic,
    ApplicationStatusUpdate,
    CompanyCreate,
    CompanyPublic,
    CompanyUpdate,
    JobCreate,
    JobPublic,
    JobUpdate,
)
from app.users.model import EmployerProfile, Role, User, utc_now
from app.users.service import EmployerRoleRequiredError, normalize_skills


class EmployerProfileRequiredError(ValueError):
    """当前雇主尚未填写团队雇主资料，不能创建公司。"""


class CompanyAlreadyLinkedError(ValueError):
    """当前雇主已经属于一家公司。"""


class CompanyNotFoundError(ValueError):
    """当前雇主尚未关联公司，或公司记录不存在。"""


class CompanyRequiredError(ValueError):
    """发布职位前必须先关联公司。"""


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


def _membership(session: Session, user: User) -> EmployerCompany | None:
    """读取当前雇主的公司成员关系。"""
    return session.get(EmployerCompany, user.id)


def _company_public(company: adapters.Company) -> CompanyPublic:
    """只返回公司公开字段。"""
    return CompanyPublic(
        id=company.id,
        name=company.name,
        description=company.description,
        created_at=company.created_at,
        updated_at=company.updated_at,
    )


def _job_public(session: Session, job: Job) -> JobPublic:
    """组合职位字段、公司名称与规范化技能；公司名称以 company 表为准。"""
    company = adapters.get_company(session, job.company_id)
    skills = session.exec(
        select(JobSkill.name).where(JobSkill.job_id == job.id)
    ).all()
    return JobPublic(
        id=job.id,
        company_id=job.company_id,
        company_name=company.name if company is not None else "",
        employer_id=job.employer_id,
        title=job.title,
        description=job.description,
        required_skills=sorted(skills),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def create_company(session: Session, user: User, data: CompanyCreate) -> CompanyPublic:
    """创建公司并让当前雇主自动成为成员，一次事务提交。"""
    _require_employer(user)
    if session.get(EmployerProfile, user.id) is None:
        raise EmployerProfileRequiredError("Employer profile required")
    if _membership(session, user) is not None:
        raise CompanyAlreadyLinkedError("Company already linked")

    company = adapters.Company(name=data.name, description=data.description)
    session.add(company)
    session.add(EmployerCompany(employer_id=user.id, company_id=company.id))
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if _membership(session, user) is not None:
            raise CompanyAlreadyLinkedError("Company already linked") from error
        raise
    except SQLAlchemyError:
        session.rollback()
        raise

    session.refresh(company)
    return _company_public(company)


def _my_company(session: Session, user: User) -> adapters.Company:
    """读取当前雇主的公司；没有成员关系或记录缺失都视为不存在。"""
    membership = _membership(session, user)
    if membership is None:
        raise CompanyNotFoundError("Company not found")
    company = adapters.get_company(session, membership.company_id)
    if company is None:
        raise CompanyNotFoundError("Company not found")
    return company


def get_my_company(session: Session, user: User) -> CompanyPublic:
    """返回当前雇主所属公司的资料。"""
    _require_employer(user)
    return _company_public(_my_company(session, user))


def update_my_company(
    session: Session, user: User, changes: CompanyUpdate
) -> CompanyPublic:
    """只修改本次显式提交的字段；updated_at 由数据库触发器维护。"""
    _require_employer(user)
    company = _my_company(session, user)
    try:
        for name, value in changes.model_dump(exclude_unset=True).items():
            setattr(company, name, value)
        session.add(company)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        raise

    session.refresh(company)
    return _company_public(company)


def create_job(session: Session, user: User, data: JobCreate) -> JobPublic:
    """发布职位并写入规范化技能；company_id 取自当前雇主成员关系。"""
    _require_employer(user)
    membership = _membership(session, user)
    if membership is None or adapters.get_company(session, membership.company_id) is None:
        raise CompanyRequiredError("Company required")

    job = Job(
        company_id=membership.company_id,
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
    """列出当前雇主负责的未删除职位；未关联公司时返回空列表。"""
    _require_employer(user)
    if _membership(session, user) is None:
        return []
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
        if adapters.job_has_applications(
            session, job.id
        ) or adapters.job_has_interview_slots(session, job.id):
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


def change_application_status(
    session: Session,
    user: User,
    application_id: uuid.UUID,
    data: ApplicationStatusUpdate,
) -> ApplicationStatusPublic:
    """只修改申请状态；四个状态之间可任意切换，不触碰预约。"""
    _require_employer(user)
    application = adapters.get_application(session, application_id)
    if application is None:
        raise ApplicationNotFoundError("Application not found")
    job = session.get(Job, application.job_id)
    if job is None or job.employer_id != user.id:
        raise JobForbiddenError("Not the owner of this job")

    application.status = data.status
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


def ensure_active_job(session: Session, job_id: uuid.UUID) -> Job:
    """application.job_id 的逻辑外键校验；不存在或已删除视为 404。"""
    job = session.get(Job, job_id)
    if job is None or job.is_deleted:
        raise JobNotFoundError("Job not found")
    return job


def list_active_jobs(session: Session) -> list[JobPublic]:
    """供其他模块读取的全部未删除职位。"""
    jobs = session.exec(select(Job).where(Job.is_deleted.is_(False))).all()
    rows = [_job_public(session, job) for job in jobs]
    return sorted(
        rows,
        key=lambda row: (-row.created_at.timestamp(), str(row.id)),
    )


def get_active_job_public(session: Session, job_id: uuid.UUID) -> JobPublic:
    """供其他模块读取的单个未删除职位。"""
    return _job_public(session, ensure_active_job(session, job_id))
