"""雇主接口的请求与响应结构；请求一律拒绝未声明字段。"""

import uuid
from datetime import datetime
from typing import Annotated, Any

from pydantic import AfterValidator, ConfigDict, field_validator
from sqlmodel import Field, SQLModel

from app.candidate.model import ApplicationStatus
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
        if value is None:
            raise ValueError(
                "Field cannot be null; omit it to keep the current value"
            )
        return value


class CompanyCreate(RequestSchema):
    """创建公司只需要名称，描述可以省略。"""

    name: NonBlankName
    description: str = ""


class CompanyUpdate(PartialUpdateSchema):
    """只修改本次显式提交的公司字段。"""

    name: NonBlankName | None = None
    description: str | None = None


class CompanyPublic(SQLModel):
    """公司资料的响应结构。"""

    id: uuid.UUID
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


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
    """职位响应；技能为规范化并排序后的名称。"""

    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str
    employer_id: uuid.UUID
    title: str
    description: str
    required_skills: list[str]
    created_at: datetime
    updated_at: datetime


class ApplicationStatusUpdate(RequestSchema):
    """申请状态只能是组员定义的四个取值。"""

    status: ApplicationStatus


class ApplicationStatusPublic(SQLModel):
    """状态修改结果；不包含简历、邮箱或密码哈希。"""

    application_id: uuid.UUID
    job_id: uuid.UUID
    candidate_id: uuid.UUID
    status: ApplicationStatus
    updated_at: datetime
