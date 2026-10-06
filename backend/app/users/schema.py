import uuid
from typing import Annotated, Literal

from pydantic import EmailStr, StringConstraints
from sqlmodel import Field, SQLModel

from app.users.model import Role


NonBlankName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

class UserCreate(SQLModel):
    """注册仅提交账户凭据和角色，资料在注册后单独填写。"""

    email: EmailStr
    password: str = Field(min_length=1)
    role: Role


class UserLogin(SQLModel):
    """登录已有账户；remember_me 的有效期策略由认证服务处理。"""

    email: EmailStr
    password: str = Field(min_length=1)
    remember_me: bool = False


class UserPublic(SQLModel):
    """返回账户标识与角色，不包含认证机密。"""

    id: uuid.UUID
    email: EmailStr
    role: Role


class Token(SQLModel):
    """认证成功后签发的访问令牌。"""

    access_token: str
    token_type: Literal["bearer"] = "bearer"


class AuthResponse(Token):
    """认证响应包含访问令牌和账户信息。"""

    user: UserPublic


class CandidateProfileCreate(SQLModel):
    """首次填写候选人资料；只要求显示名称，简历和技能可以后补。"""

    display_name: NonBlankName
    resume_text: str = ""
    skills: list[str] = Field(default_factory=list)


class EmployerProfileCreate(SQLModel):
    """首次填写雇主资料；只要求公司名称，公司描述可以后补。"""

    company_name: NonBlankName
    company_description: str = ""


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


class EmployerProfilePublic(SQLModel):
    """雇主公司资料的响应结构。"""

    user_id: uuid.UUID
    company_name: str
    company_description: str
