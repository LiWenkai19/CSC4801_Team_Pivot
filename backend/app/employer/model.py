"""雇主工作流的数据库表；统一注册到 SQLModel.metadata，随主迁移链建表。"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import CheckConstraint, Column, DateTime, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel

from app.users.model import utc_now


class ApplicationStatus(str, Enum):
    """申请状态只允许四个取值，与需求契约一致。"""

    Pending = "Pending"
    Interviewing = "Interviewing"
    Rejected = "Rejected"
    Accepted = "Accepted"


def timestamp_column() -> Column:
    """带时区的非空时间列；写入值由 service 层显式给出。"""
    return Column(DateTime(timezone=True), nullable=False)


class Job(SQLModel, table=True):
    """职位；company_id 不再单独存表，公司名称以 EmployerProfile 为唯一来源。"""

    __tablename__ = "job"  # type: ignore
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_job_title"),
        CheckConstraint("length(trim(description)) > 0", name="ck_job_description"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employer_id: uuid.UUID = Field(foreign_key="employer_profile.user_id", index=True)
    title: str = Field(nullable=False)
    description: str = Field(sa_column=Column(Text(), nullable=False))
    is_deleted: bool = Field(default=False, nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())

    skills: list["JobSkill"] = Relationship(back_populates="job")


class JobSkill(SQLModel, table=True):
    """职位要求的技能；名称须为去空白、小写后的值。"""

    __tablename__ = "job_skill"  # type: ignore
    __table_args__ = (
        CheckConstraint(
            "length(name) > 0 AND name = lower(trim(name))",
            name="ck_job_skill_name",
        ),
    )

    job_id: uuid.UUID = Field(foreign_key="job.id", primary_key=True)
    name: str = Field(primary_key=True)

    job: Job = Relationship(back_populates="skills")


class Application(SQLModel, table=True):
    """申请；同一候选人对同一职位只能有一条申请。"""

    __tablename__ = "application"  # type: ignore
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    candidate_id: uuid.UUID = Field(
        foreign_key="candidate_profile.user_id", index=True
    )
    job_id: uuid.UUID = Field(foreign_key="job.id", index=True)
    status: ApplicationStatus = Field(
        default=ApplicationStatus.Pending,
        sa_column=Column(
            SAEnum(
                ApplicationStatus,
                name="application_status",
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
                values_callable=lambda values: [value.value for value in values],
            ),
            nullable=False,
            server_default="Pending",
        ),
    )
    created_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())


class InterviewSlot(SQLModel, table=True):
    """面试时段；本轮只作为职位删除依赖与预约展示，不提供管理接口。"""

    __tablename__ = "interview_slot"  # type: ignore
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_slot_time_order"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employer_id: uuid.UUID = Field(
        foreign_key="employer_profile.user_id", index=True
    )
    job_id: uuid.UUID | None = Field(default=None, foreign_key="job.id", index=True)
    starts_at: datetime = Field(sa_column=timestamp_column())
    ends_at: datetime = Field(sa_column=timestamp_column())


class Booking(SQLModel, table=True):
    """面试预约；一份申请和一个时段都只能被预约一次。"""

    __tablename__ = "booking"  # type: ignore
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_booking_application"),
        UniqueConstraint("slot_id", name="uq_booking_slot"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    application_id: uuid.UUID = Field(foreign_key="application.id", nullable=False)
    slot_id: uuid.UUID = Field(foreign_key="interview_slot.id", nullable=False)
    created_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())
