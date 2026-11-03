"""共享业务表；雇主与 scheduling 模块应复用这些模型。"""

import uuid

from datetime import datetime, timezone

from enum import Enum

from sqlalchemy import CheckConstraint, Column, DateTime, Text, UniqueConstraint, func, text

from sqlalchemy import Enum as SAEnum

from sqlmodel import Field, SQLModel


class Company(SQLModel, table=True):
    __tablename__ = "company"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="ck_company_name"),)
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(nullable=False)
    description: str = Field(default="", sa_column=Column(Text, nullable=False, server_default=text("''")))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),
                                 sa_column=Column(DateTime(timezone=True), nullable=False,
                                                  server_default=func.current_timestamp()))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),
                                 sa_column=Column(DateTime(timezone=True), nullable=False,
                                                  server_default=func.current_timestamp(),
                                                  onupdate=func.current_timestamp()))


# ApplicationStatus 定义一组固定选项，避免状态/角色任意拼写
class ApplicationStatus(str, Enum):
    Pending = "Pending"
    Interviewing = "Interviewing"
    Rejected = "Rejected"
    Accepted = "Accepted"


# Job 是数据库表模型；继承 SQLModel，table=True 表示字段会映射为数据库列
class Job(SQLModel, table=True):
    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint("length(trim(title)) > 0", name="ck_job_title"),
        CheckConstraint("length(trim(description)) > 0", name="ck_job_description"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # 雇主账户 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    employer_id: uuid.UUID = Field(foreign_key="employer_profile.user_id", index=True)
    # 职位标题：类型为 str；这里只声明数据格式
    title: str
    # 职位描述：类型为 str；这里只声明数据格式
    description: str
    # 职位的删除标记（True 表示不再展示）：类型为 bool；使用固定值 False
    is_deleted: bool = False


# JobSkill 是数据库表模型；继承 SQLModel，table=True 表示字段会映射为数据库列
class JobSkill(SQLModel, table=True):
    __tablename__ = "job_skill"
    __table_args__ = (
        CheckConstraint(
            "length(name) > 0 AND name = lower(trim(name))",
            name="ck_job_skill_name",
        ),
    )
    # 职位 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    job_id: uuid.UUID = Field(foreign_key="job.id", primary_key=True)
    # name：类型为 str；声明字段的默认值、主键、外键或数据库列设置
    name: str = Field(primary_key=True)


# Application 是数据库表模型；继承 SQLModel，table=True 表示字段会映射为数据库列
class Application(SQLModel, table=True):
    __tablename__ = "application"
    __table_args__ = (
        UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc),
                                        sa_column=Column(DateTime(timezone=True), nullable=True))
    updated_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc),
                                        sa_column=Column(DateTime(timezone=True), nullable=True,
                                                         onupdate=func.current_timestamp()))
    # 候选人的账户 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    candidate_id: uuid.UUID = Field(foreign_key="candidate_profile.user_id", index=True)
    # 职位 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    job_id: uuid.UUID = Field(foreign_key="job.id", index=True)
    # 状态值：类型为 ApplicationStatus；声明字段的默认值、主键、外键或数据库列设置
    status: ApplicationStatus = Field(
        # 未提供字段时使用的默认值
        default=ApplicationStatus.Pending,
        # 指定底层 SQLAlchemy 列，让时区/枚举约束正确写入数据库
        sa_column=Column(
            SAEnum(
                ApplicationStatus,
                # False 表示不创建 PostgreSQL 独立枚举类型
                native_enum=False,
                # 开启数据库 CHECK 约束，阻止非法枚举值
                create_constraint=True,
                # 让数据库存枚举的字符串值，而不是 Python 成员对象
                values_callable=lambda values: [v.value for v in values],
                name="application_status",
            ),
            # 是否允许数据库 NULL；False 表示必须有值
            nullable=False,
        ),
    )


# InterviewSlot 是数据库表模型；继承 SQLModel，table=True 表示字段会映射为数据库列
class InterviewSlot(SQLModel, table=True):
    __tablename__ = "interview_slot"
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="ck_slot_time_order"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc),
                                        sa_column=Column(DateTime(timezone=True), nullable=True))
    # 雇主账户 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    employer_id: uuid.UUID = Field(foreign_key="employer_profile.user_id", index=True)
    # 职位 ID：类型为 uuid.UUID | None；声明字段的默认值、主键、外键或数据库列设置
    job_id: uuid.UUID | None = Field(default=None, foreign_key="job.id")
    # 带时区的面试开始时间：类型为 datetime；声明字段的默认值、主键、外键或数据库列设置
    starts_at: datetime = Field(
        # 指定底层 SQLAlchemy 列，让时区/枚举约束正确写入数据库
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    # 带时区的面试结束时间：类型为 datetime；声明字段的默认值、主键、外键或数据库列设置
    ends_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


# Booking 是数据库表模型；继承 SQLModel，table=True 表示字段会映射为数据库列
class Booking(SQLModel, table=True):
    __tablename__ = "booking"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_booking_application"),
        UniqueConstraint("slot_id", name="uq_booking_slot"),
    )
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(timezone.utc),
                                        sa_column=Column(DateTime(timezone=True), nullable=True))
    # 申请 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    application_id: uuid.UUID = Field(foreign_key="application.id")
    # 面试时段 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    slot_id: uuid.UUID = Field(foreign_key="interview_slot.id")
