"""面试时段的请求和响应。"""

from datetime import datetime, timezone

from pydantic import field_validator
from sqlmodel import SQLModel

from app.candidate.schema import SlotPublic as SlotPublic


class ManagedSlotPublic(SlotPublic):
    """雇主列表另带预约状态，用于控制删除操作。"""

    is_booked: bool


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
