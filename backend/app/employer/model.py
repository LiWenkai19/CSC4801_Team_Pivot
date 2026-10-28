"""雇主模块独立元数据；不注册到全局 SQLModel.metadata。"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, Text, false, func
from sqlalchemy.orm import registry
from sqlmodel import Field, Relationship, SQLModel

from app.candidate.database.model import UTCDateTime, utc_now


class EmployerModel(SQLModel, registry=registry()):
    """雇主模块独立元数据；不注册到全局 SQLModel.metadata。"""


def timestamp_column():
    """带时区、数据库默认当前时间的非空时间列。"""
    return Column(
        UTCDateTime(), nullable=False, server_default=func.current_timestamp()
    )


class Job(EmployerModel, table=True):
    """职位；company_id 与 employer_id 是逻辑外键，由 service 校验。"""

    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_job_title"),
        CheckConstraint("length(trim(description)) > 0", name="ck_job_description"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    company_id: uuid.UUID = Field(nullable=False, index=True)
    employer_id: uuid.UUID = Field(nullable=False, index=True)
    title: str = Field(nullable=False)
    description: str = Field(sa_column=Column(Text(), nullable=False))
    is_deleted: bool = Field(
        default=False,
        sa_column=Column(Boolean(), nullable=False, server_default=false()),
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())

    skills: list["JobSkill"] = Relationship(back_populates="job")


class JobSkill(EmployerModel, table=True):
    """职位要求的技能；名称须为去空白、小写后的值。"""

    __tablename__ = "job_skill"
    __table_args__ = (
        CheckConstraint(
            "length(name) > 0 AND name = lower(trim(name))",
            name="ck_job_skill_name",
        ),
    )

    job_id: uuid.UUID = Field(foreign_key="job.id", primary_key=True)
    name: str = Field(primary_key=True)

    job: Job = Relationship(back_populates="skills")


class EmployerCompany(EmployerModel, table=True):
    """雇主与公司的成员关系；一个雇主只属于一家公司。"""

    __tablename__ = "employer_company"

    employer_id: uuid.UUID = Field(primary_key=True)
    company_id: uuid.UUID = Field(nullable=False, index=True)
    created_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())
