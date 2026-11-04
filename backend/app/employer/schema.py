"""雇主接口的请求与响应结构；请求一律拒绝未声明字段。"""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, ConfigDict, field_validator
from sqlmodel import Field, SQLModel

from app.employer.model import ApplicationStatus
from app.users.schema import NonBlankName


def _require_non_blank(value: str) -> str:
    """只校验包含非空白字符，保留原始文本。"""
    if not value.strip():
        raise ValueError("Text must contain non-whitespace characters")
    return value


NonBlankText = Annotated[str, AfterValidator(_require_non_blank)]


class RequestSchema(SQLModel):
    """拒绝请求中未声明的字段。"""

    model_config = ConfigDict(extra="forbid")


class PartialUpdateSchema(RequestSchema):
    """局部更新拒绝显式 null；省略字段表示保持原值。"""

    @field_validator("*", mode="before")
    @classmethod
    def reject_null(cls, value: Any) -> Any:
        """显式 null 一律拒绝，清空文本请提交空字符串。"""
        if value is None:
            raise ValueError(
                "Field cannot be null; omit it to keep the current value"
            )
        return value


class CompanyPublic(SQLModel):
    """公司资料的响应结构；字段与 EmployerProfile 一一对应。"""

    user_id: uuid.UUID
    company_name: str
    company_description: str


class CompanyUpdate(PartialUpdateSchema):
    """只修改本次显式提交的公司资料字段。"""

    company_name: NonBlankName | None = None
    company_description: str | None = None


class JobCreate(RequestSchema):
    """发布职位；required_skills 可以为空列表。"""

    title: NonBlankName
    description: NonBlankText
    required_skills: list[str] = Field(default_factory=list)


class JobUpdate(PartialUpdateSchema):
    """只修改本次显式提交的职位字段；技能整体替换。"""

    title: NonBlankName | None = None
    description: NonBlankText | None = None
    required_skills: list[str] | None = None


class JobPublic(SQLModel):
    """职位响应；技能为规范化并排序后的名称，公司名取自公司资料。"""

    id: uuid.UUID
    company_name: str
    employer_id: uuid.UUID
    title: str
    description: str
    required_skills: list[str]
    created_at: datetime
    updated_at: datetime


class BookingPublic(SQLModel):
    """面试预约的响应结构；无预约时整段为 null。"""

    booking_id: uuid.UUID
    slot_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime


class ApplicantPublic(SQLModel):
    """申请人行；不含简历等私有字段。"""

    application_id: uuid.UUID
    candidate_id: uuid.UUID
    display_name: str
    skills: list[str]
    match_score: int
    status: ApplicationStatus
    booking: BookingPublic | None


class ApplicationStatusUpdate(RequestSchema):
    """申请状态只能是四个取值之一。"""

    status: ApplicationStatus


class ApplicationStatusPublic(SQLModel):
    """状态修改结果；不包含简历、邮箱或密码哈希。"""

    application_id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    status: ApplicationStatus
    updated_at: datetime
