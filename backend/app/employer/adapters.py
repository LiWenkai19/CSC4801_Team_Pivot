"""雇主模块对组员 candidate 模块的全部导入集中在这里。"""

import uuid

from sqlalchemy import select
from sqlmodel import Session

from app.candidate.database.model import Application, Booking, Company, InterviewSlot

__all__ = ["Application", "Booking", "Company", "InterviewSlot"]


def get_company(session: Session, company_id: uuid.UUID) -> Company | None:
    """按主键读取公司；公司表由组员 core 迁移创建。"""
    return session.get(Company, company_id)


def job_has_applications(session: Session, job_id: uuid.UUID) -> bool:
    """是否存在该职位的申请；成员表映射由组员提供。"""
    statement = (
        select(Application.id).where(Application.job_id == job_id).limit(1)
    )
    return session.exec(statement).first() is not None


def job_has_interview_slots(session: Session, job_id: uuid.UUID) -> bool:
    """是否存在该职位的面试时段；本轮只读取，不管理时段。"""
    statement = (
        select(InterviewSlot.id).where(InterviewSlot.job_id == job_id).limit(1)
    )
    return session.exec(statement).first() is not None


def get_application(session: Session, application_id: uuid.UUID) -> Application | None:
    """按主键读取申请；状态修改直接操作返回的组员 ORM 对象。"""
    return session.get(Application, application_id)
