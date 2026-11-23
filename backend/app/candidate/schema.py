"""候选人请求和响应；数据库模型仍由 users/employer 维护。"""

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import AfterValidator, ConfigDict, field_validator
from sqlmodel import SQLModel

from app.employer.model import ApplicationStatus
from app.employer.schema import BookingPublic as EmployerBookingPublic, JobPublic
from app.users.schema import NonBlankName


def _as_utc(value: datetime) -> datetime:
    """PostgreSQL 会按会话时区返回时间，候选人响应统一转换为 UTC。"""
    return value.astimezone(timezone.utc)


UTCDateTime = Annotated[datetime, AfterValidator(_as_utc)]


class BookingPublic(EmployerBookingPublic):
    """保留共享预约字段，时间以 UTC 传输。"""

    starts_at: UTCDateTime
    ends_at: UTCDateTime


class RequestSchema(SQLModel):
    """拒绝伪造归属、状态及其他未声明字段。"""

    model_config = ConfigDict(extra="forbid")


class ProfileUpdate(RequestSchema):
    """省略保留，文本和技能可以清空，显式 null 不合法。"""

    display_name: NonBlankName | None = None
    resume_text: str | None = None
    skills: list[str] | None = None

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value: Any) -> Any:
        """数据库非空字段用空字符串或空数组清空。"""
        if value is None:
            raise ValueError("Field cannot be null; omit it to keep the current value")
        return value


class RecommendedJob(JobPublic):
    """职位与当前候选人的实时匹配分、投递状态。"""

    match_score: int
    applied: bool
    created_at: UTCDateTime
    updated_at: UTCDateTime


class ApplicationPublic(SQLModel):
    """本人申请及共享预约，不包含私有简历或账户凭据。"""

    application_id: uuid.UUID
    job_id: uuid.UUID
    job_title: str
    company_name: str
    status: ApplicationStatus
    created_at: UTCDateTime
    booking: BookingPublic | None


class SlotPublic(SQLModel):
    """UTC 面试时段；前端统一使用上海时区展示。"""

    id: uuid.UUID
    starts_at: UTCDateTime
    ends_at: UTCDateTime


class BookingCreate(RequestSchema):
    """申请取自 URL，候选人取自认证身份。"""

    slot_id: uuid.UUID
