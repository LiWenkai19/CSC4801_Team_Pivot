"""独立映射用户负责的表，沿用已有物理表名和字段，供新数据库使用。

独立 registry 避免重定义 SQLModel.metadata 中的团队模型。外部表仅复制
元数据以解析外键；建库必须使用迁移，不能对整个 metadata 调用 create_all。
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Text, UniqueConstraint, func, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import registry
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel

from app.candidate.model import ApplicationStatus
from app.candidate.model import Job as TeamJob
from app.users.model import EmployerProfile as TeamEmployerProfile
from app.users.model import Role

OWNED_TABLES = frozenset({
    "user", "candidate_profile", "candidate_skill", "company", "application",
    "interview_slot",
})
CORE_TABLES = ("user", "candidate_profile", "candidate_skill", "company")
EXTERNAL_TABLES = frozenset({"employer_profile", "job", "job_skill", "booking"})


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """拒绝无时区输入；SQLite 读取后也返回明确的 UTC 时间。"""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Datetime must include a timezone")
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def timestamp_column():
    return Column(UTCDateTime(), nullable=False, server_default=func.current_timestamp())


class OwnedModel(SQLModel, registry=registry()):
    """与旧 ORM 并存的独立元数据；不改变团队类或字段。"""


class User(OwnedModel, table=True):
    __tablename__ = "user"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(nullable=False, unique=True, index=True)
    hashed_password: str = Field(nullable=False)
    role: Role = Field(sa_column=Column(
        SAEnum(Role, name="user_role", native_enum=False, create_constraint=True,
               validate_strings=True, values_callable=lambda values: [v.value for v in values]),
        nullable=False,
    ))
    created_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())


class CandidateProfile(OwnedModel, table=True):
    __tablename__ = "candidate_profile"
    __table_args__ = (
        CheckConstraint("length(trim(display_name)) > 0", name="ck_candidate_display_name"),
    )

    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    display_name: str = Field(nullable=False)
    resume_text: str = Field(default="", sa_column=Column(
        Text(), nullable=False, server_default=text("''"),
    ))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())


class CandidateSkill(OwnedModel, table=True):
    __tablename__ = "candidate_skill"
    __table_args__ = (
        CheckConstraint("length(name) > 0 AND name = lower(trim(name))",
                        name="ck_candidate_skill_normalized_name"),
    )

    candidate_id: uuid.UUID = Field(foreign_key="candidate_profile.user_id", primary_key=True)
    name: str = Field(primary_key=True)


class Company(OwnedModel, table=True):
    __tablename__ = "company"
    __table_args__ = (
        CheckConstraint("length(trim(name)) > 0", name="ck_company_name"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(nullable=False)
    description: str = Field(default="", sa_column=Column(
        Text(), nullable=False, server_default=text("''"),
    ))
    created_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())


class Application(OwnedModel, table=True):
    __tablename__ = "application"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    candidate_id: uuid.UUID = Field(foreign_key="candidate_profile.user_id", index=True)
    job_id: uuid.UUID = Field(foreign_key="job.id", index=True)
    status: ApplicationStatus = Field(default=ApplicationStatus.Pending, sa_column=Column(
        SAEnum(ApplicationStatus, name="application_status", native_enum=False,
               create_constraint=True, validate_strings=True,
               values_callable=lambda values: [v.value for v in values]),
        nullable=False, server_default="Pending",
    ))
    created_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())
    updated_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())


class InterviewSlot(OwnedModel, table=True):
    __tablename__ = "interview_slot"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_slot_time_order"),
        CheckConstraint("(ends_at - starts_at) = INTERVAL '30 minutes'",
                        name="ck_slot_duration").ddl_if(dialect="postgresql"),
        CheckConstraint(
            "abs((julianday(ends_at) - julianday(starts_at)) * 86400 - 1800) < 0.0001",
            name="ck_slot_duration",
        ).ddl_if(dialect="sqlite"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    employer_id: uuid.UUID = Field(foreign_key="employer_profile.user_id", index=True)
    job_id: uuid.UUID | None = Field(default=None, foreign_key="job.id")
    starts_at: datetime = Field(sa_column=Column(UTCDateTime(), nullable=False))
    ends_at: datetime = Field(sa_column=Column(UTCDateTime(), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=timestamp_column())


# 外键目标沿用队友定义的类型；只复制元数据，绝不创建或更改这些表。
TeamEmployerProfile.__table__.to_metadata(OwnedModel.metadata)
TeamJob.__table__.to_metadata(OwnedModel.metadata)


def include_object(obj, name, type_, reflected, compare_to):
    """Alembic 仅比较用户表；不把外部表、版本表当作待创建/待删除对象。"""
    if type_ == "table":
        return name in OWNED_TABLES
    return True
