import datetime
import uuid
from enum import Enum
from typing import Optional

from sqlalchemy import CheckConstraint, Column, DateTime
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, Relationship, SQLModel


class Role(str, Enum):
    """系统仅支持候选人和雇主两种角色。"""

    Candidate = "candidate"
    Employer = "employer"


def utc_now() -> datetime.datetime:
    """生成带 UTC 时区的当前时间。"""
    return datetime.datetime.now(datetime.timezone.utc)


class User(SQLModel, table=True):
    """共用登录账户；密码哈希不得出现在 API 响应中。"""

    __tablename__ = "user"  # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(nullable=False, unique=True, index=True)
    hashed_password: str = Field(nullable=False)
    role: Role = Field(
        sa_column=Column(
            SAEnum(
                Role,
                name="user_role",
                native_enum=False,
                create_constraint=True,
                validate_strings=True,
                values_callable=lambda roles: [role.value for role in roles],
            ),
            nullable=False,
        )
    )
    created_at: datetime.datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    candidate_profile: Optional["CandidateProfile"] = Relationship(back_populates="user")
    employer_profile: Optional["EmployerProfile"] = Relationship(back_populates="user")


class CandidateProfile(SQLModel, table=True):
    """候选人资料；简历仅允许所属候选人读取和替换。"""

    __tablename__ = "candidate_profile"  # type: ignore

    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    display_name: str = Field(nullable=False)
    resume_text: str = Field(default="", nullable=False)

    user: User = Relationship(back_populates="candidate_profile")
    skills: list["CandidateSkill"] = Relationship(back_populates="candidate")


class EmployerProfile(SQLModel, table=True):
    """雇主拥有的公司资料。"""

    __tablename__ = "employer_profile"  # type: ignore

    user_id: uuid.UUID = Field(foreign_key="user.id", primary_key=True)
    company_name: str = Field(nullable=False)
    company_description: str = Field(default="", nullable=False)

    user: User = Relationship(back_populates="employer_profile")


class CandidateSkill(SQLModel, table=True):
    """候选人技能；写入前应去空白、转小写、去空项并去重。"""

    __tablename__ = "candidate_skill"  # type: ignore
    __table_args__ = (
        CheckConstraint(
            "length(name) > 0 AND name = lower(trim(name))",
            name="ck_candidate_skill_normalized_name",
        ),
    )

    candidate_id: uuid.UUID = Field(
        foreign_key="candidate_profile.user_id", primary_key=True
    )
    name: str = Field(primary_key=True)

    candidate: CandidateProfile = Relationship(back_populates="skills")


class UserSession(SQLModel, table=True):
    """服务端会话：浏览器 Cookie 里只有随机会话 ID，库里只存它的 SHA-256 哈希。

    删除这一行即令该会话立即失效（注销、改密码踢下线都依赖这一点）。
    """

    __tablename__ = "user_session"  # type: ignore

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # 会话 ID 的哈希；数据库泄露时攻击者拿不到可直接使用的 Cookie 值。
    token_hash: str = Field(nullable=False, unique=True, index=True)
    # 与会话绑定的 CSRF 令牌；写请求必须在 X-CSRF-Token 头里原样带回。
    csrf_token: str = Field(nullable=False)
    # 删除用户时数据库级联删除其会话，清理账户的脚本无需额外处理。
    user_id: uuid.UUID = Field(
        foreign_key="user.id", ondelete="CASCADE", nullable=False, index=True
    )
    created_at: datetime.datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    expires_at: datetime.datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # 加载会话时用内连接一并取回账户：认证只需一次查询；账户已删除的会话查不到。
    user: User = Relationship(sa_relationship_kwargs={"lazy": "joined", "innerjoin": True})
