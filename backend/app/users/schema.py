import uuid
from typing import Annotated, Any

from pydantic import AfterValidator, EmailStr, StrictInt, StringConstraints, model_validator
from sqlmodel import Field, SQLModel

from app.users.model import Role


def _reject_nul(value: str) -> str:
    """在写库前拒绝 PostgreSQL 文本列无法保存的 NUL 字符。"""
    if "\x00" in value:
        raise ValueError("Text cannot contain NUL characters")
    return value


DatabaseText = Annotated[str, AfterValidator(_reject_nul)]
NonBlankName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
    AfterValidator(_reject_nul),
]
ResourceVersion = Annotated[StrictInt, Field(gt=0)]


class ErrorResponse(SQLModel):
    """认证、权限及业务拒绝共用的响应体；不包含请求原文。"""

    detail: str


def error_responses(*status_codes: int) -> dict[int, dict[str, Any]]:
    """给已有错误状态声明同一响应结构，不改变运行时处理。"""
    return {code: {"model": ErrorResponse} for code in status_codes}


class UserCreate(SQLModel):
    """注册仅提交账户凭据和角色，资料在注册后单独填写。"""

    model_config = {"extra": "forbid"}

    email: EmailStr
    password: str = Field(min_length=1)
    role: Role


class UserLogin(SQLModel):
    """登录已有账户；remember_me 决定会话有效期与 Cookie 是否持久化。"""

    email: EmailStr
    password: str = Field(min_length=1)
    remember_me: bool = False


class UserPublic(SQLModel):
    """统一返回账户标识、角色和实时资料完成状态，不包含认证机密。"""

    id: uuid.UUID
    email: EmailStr
    role: Role
    profile_completed: bool


class AuthResponse(SQLModel):
    """认证响应只含账户信息；会话凭证通过 HttpOnly Cookie 下发，不出现在响应体（FP-AUTH-2）。"""

    user: UserPublic


class CandidateProfileCreate(SQLModel):
    """首次填写候选人资料；只要求显示名称，简历和技能可以后补。"""

    display_name: NonBlankName
    resume_text: DatabaseText = ""
    skills: list[DatabaseText] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_client_version(cls, values: Any) -> Any:
        """首次创建的版本由服务器分配，保留既有其他额外字段的处理方式。"""
        if isinstance(values, dict) and "version" in values:
            raise ValueError("Version is assigned by the server")
        return values


class EmployerProfileCreate(SQLModel):
    """首次填写雇主资料；只要求公司名称，公司描述可以后补。"""

    model_config = {"extra": "forbid"}

    company_name: NonBlankName
    company_description: DatabaseText = ""

    @model_validator(mode="before")
    @classmethod
    def ignore_client_supplied_owner(cls, value: Any) -> Any:
        """兼容提交了 user_id 的请求，资料归属始终取自认证用户。"""
        if isinstance(value, dict) and "user_id" in value:
            value = value.copy()
            del value["user_id"]
        return value


# class ProfileUpdateSchema(RequestSchema):
#     """局部更新允许省略字段；显式 null 不用于清空非空数据库列。"""

#     @field_validator("*", mode="before")
#     @classmethod
#     def reject_null(cls, value: Any) -> Any:
#         """拒绝显式 null；清空文本或技能应提交空字符串或空列表。"""
#         if value is None:
#             raise ValueError("Field cannot be null; omit it to keep the current value")
#         return value


# class CandidateProfileUpdate(ProfileUpdateSchema):
#     """只替换本次提供的候选人资料字段。"""

#     display_name: NonBlankName | None = None
#     resume_text: str | None = None
#     skills: list[str] | None = None


# class EmployerProfileUpdate(ProfileUpdateSchema):
#     """只替换本次提供的雇主资料字段。"""

#     company_name: NonBlankName | None = None
#     company_description: str | None = None


class CandidateProfilePublic(SQLModel):
    """仅向候选人本人返回完整资料，包含私有简历。"""

    user_id: uuid.UUID
    display_name: str
    resume_text: str
    skills: list[str]
    version: int


class EmployerProfilePublic(SQLModel):
    """雇主公司资料的响应结构。"""

    user_id: uuid.UUID
    company_name: str
    company_description: str
    version: int
