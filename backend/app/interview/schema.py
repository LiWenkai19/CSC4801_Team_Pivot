"""面试时段的请求和响应。"""

import uuid
from datetime import datetime, timezone

from pydantic import field_validator
from sqlmodel import SQLModel

from app.candidate.schema import SlotPublic as SlotPublic


class ManagedSlotPublic(SlotPublic):
    """雇主列表另带预约状态，以及已预约时段的申请人和职位。"""

    is_booked: bool
    # 时段被预约后归属该职位；历史数据可能为空，此时回退到申请上的职位。
    job_id: uuid.UUID | None = None
    job_title: str | None = None
    applicant_name: str | None = None


class SlotCreate(SQLModel):
    """创建时段只接收开始时间，结束时间由服务计算。"""

    model_config = {"extra": "forbid"}

    starts_at: datetime

    @field_validator("starts_at", mode="before")
    @classmethod
    def parse_utc_time(cls, value: object) -> datetime:
        """将带时区的 ISO 8601 字符串转换为 UTC。"""
        if not isinstance(value, str):
            raise ValueError("Expected an ISO 8601 datetime string")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("Timezone is required")
        try:
            return parsed.astimezone(timezone.utc)
        except OverflowError as error:
            raise ValueError("Datetime is out of range in UTC") from error
