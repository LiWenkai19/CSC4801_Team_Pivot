"""Candidate-owned validation extensions; the team's schema module stays unchanged."""
from pydantic import ConfigDict, field_validator

from app.users.schema import (  # Re-export existing contracts for extension callers.
    CandidateProfileCreate as TeamCandidateProfileCreate,
    CandidateProfilePublic,
    EmployerProfileCreate as TeamEmployerProfileCreate,
    EmployerProfilePublic,
    NonBlankName,
    Token,
    UserCreate as TeamUserCreate,
    UserLogin as TeamUserLogin,
    UserPublic as TeamUserPublic,
)


# 继承团队原有字段校验，并禁止提交契约以外的字段，避免客户端偷偷附加数据。
class UserCreate(TeamUserCreate):
    model_config = ConfigDict(extra='forbid')


class UserLogin(TeamUserLogin):
    model_config = ConfigDict(extra='forbid')


class CandidateProfileCreate(TeamCandidateProfileCreate):
    model_config = ConfigDict(extra='forbid')


class EmployerProfileCreate(TeamEmployerProfileCreate):
    model_config = ConfigDict(extra='forbid')


class UserPublic(TeamUserPublic):
    # 前端据此区分直接进入工作区还是先补填资料。
    profile_completed: bool


class AuthResponse(Token):
    # 登录响应既包含继承来的 Token 字段，也包含公开用户信息。
    user: UserPublic


class CandidateProfileUpdate(TeamCandidateProfileCreate):
    """Partial updates reject explicit null and client-provided ownership."""
    model_config = ConfigDict(extra='forbid')
    # 默认值表示 PATCH 可以省略字段；省略不等于显式传入 JSON null。
    display_name: NonBlankName | None = None
    resume_text: str | None = None
    skills: list[str] | None = None

    @field_validator('*', mode='before')
    @classmethod
    def reject_null(cls, value):
        # 对客户端实际传入的每个字段执行预校验；清空时应使用空字符串或空列表。
        if value is None:
            raise ValueError('Omit the field or use empty text/list; null is not allowed')
        return value

# 对外声明可复用的数据结构；这不会触发数据库操作。
__all__ = ["UserCreate", "UserLogin", "CandidateProfileCreate", "CandidateProfilePublic", "EmployerProfileCreate", "EmployerProfilePublic", "NonBlankName", "Token", "UserPublic", "AuthResponse", "CandidateProfileUpdate"]
