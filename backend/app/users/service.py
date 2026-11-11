import datetime

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, delete, select

from app.core.config import settings
from app.users.model import (
    CandidateProfile,
    CandidateSkill,
    EmployerProfile,
    Role,
    User,
    UserSession,
    utc_now,
)
from app.users.schema import (
    CandidateProfileCreate,
    CandidateProfilePublic,
    EmployerProfileCreate,
    EmployerProfilePublic,
    UserCreate,
    UserPublic,
)
from app.users.security import (
    hash_password,
    hash_session_token,
    new_random_token,
    tokens_equal,
    verify_password,
)
from fastapi.security import APIKeyCookie, APIKeyHeader
from fastapi import Depends, HTTPException, Request, status
from app.db.session import get_db


def get_user_by_email(session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


def create_user(session: Session, user: UserCreate) -> User:
    existing_user = get_user_by_email(session, user.email)
    if existing_user:
        raise ValueError("User already exists")

    hashed_password = hash_password(user.password)
    new_user = User(email=user.email, hashed_password=hashed_password, role=user.role)
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return new_user
    

def authenticate_user(session: Session, email: str, password: str) -> User | None:
    user : User | None  = get_user_by_email(session, email)
    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user

    
def get_current_user_public(session: Session, curr_user: User) -> UserPublic:
    """只检查当前用户对应角色的资料是否存在，不返回资料内容。"""
    profile_model = (
        CandidateProfile if curr_user.role == Role.Candidate else EmployerProfile
    )
    profile_completed = session.get(profile_model, curr_user.id) is not None
    return UserPublic(
        id=curr_user.id,
        email=curr_user.email,
        role=curr_user.role,
        profile_completed=profile_completed,
    )


# ===== 会话管理 =====

def session_lifetime(remember_me: bool) -> datetime.timedelta:
    """"记住我"决定服务端会话的有效期。"""
    if remember_me:
        return datetime.timedelta(days=settings.SESSION_REMEMBER_DAYS)
    return datetime.timedelta(minutes=settings.SESSION_TTL_MINUTES)


def create_session(session: Session, user: User, remember_me: bool) -> tuple[str, UserSession]:
    """为用户新建会话，返回 (会话 ID 原文, 会话行)。

    原文只交给 router 写进 Cookie，数据库里只保存它的哈希。
    每次登录都新建会话，防止会话固定攻击（攻击者预先塞给受害者一个已知 ID）。
    """
    token = new_random_token()
    row = UserSession(
        token_hash=hash_session_token(token),
        csrf_token=new_random_token(),
        user_id=user.id,
        expires_at=utc_now() + session_lifetime(remember_me),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return token, row


def revoke_session(session: Session, row: UserSession) -> None:
    """删除会话行；之后同一个 Cookie 再来请求会得到 401。"""
    session.delete(row)
    session.commit()


def revoke_all_sessions(session: Session, user_id) -> None:
    """删除用户全部会话；改密码、禁用账号时调用。"""
    session.exec(delete(UserSession).where(UserSession.user_id == user_id))  # type: ignore[call-overload]
    session.commit()


def _as_aware(value: datetime.datetime) -> datetime.datetime:
    """SQLite（单元测试库）读回的时间不带时区，按 UTC 补齐后再比较。"""
    return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)


# ===== FastAPI 认证依赖 =====

# APIKeyCookie / APIKeyHeader 会出现在 OpenAPI 文档里，Swagger 的 Authorize 可以填写 CSRF 令牌。
session_cookie = APIKeyCookie(name=settings.SESSION_COOKIE_NAME, auto_error=False)
csrf_header = APIKeyHeader(name="X-CSRF-Token", auto_error=False)

# 会修改数据的 HTTP 方法；GET/HEAD/OPTIONS 必须保持无副作用。
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def get_valid_session(
    db: Session = Depends(get_db),
    token: str | None = Depends(session_cookie),
) -> UserSession:
    """根据 Cookie 里的会话 ID 找到有效会话，否则 401（FP-AUTH-3 未认证）。"""
    unauthorized = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    if not token:
        raise unauthorized
    # UserSession.user 配置为 joined 内连接：一次查询同时取回会话和账户。
    row = db.exec(
        select(UserSession).where(UserSession.token_hash == hash_session_token(token))
    ).first()
    if row is None:
        raise unauthorized
    if _as_aware(row.expires_at) <= utc_now():
        revoke_session(db, row)  # 过期会话顺手清理
        raise unauthorized
    return row


def require_csrf(
    request: Request,
    sess: UserSession = Depends(get_valid_session),
    csrf: str | None = Depends(csrf_header),
) -> UserSession:
    """写请求必须带回与会话绑定的 CSRF 令牌，否则 403。"""
    if request.method in UNSAFE_METHODS and not (csrf and tokens_equal(csrf, sess.csrf_token)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing or invalid")
    return sess


def get_current_user(sess: UserSession = Depends(require_csrf)) -> User:
    """业务路由的认证入口：会话校验 + 写请求 CSRF 校验一并完成。

    require_candidate / require_employer 均依赖它，签名保持不变，业务模块无需改动。
    账户随会话一起加载，这里不再额外查询数据库。
    """
    return sess.user


def require_candidate(curr_user: User = Depends(get_current_user)) -> User:
    """要求已认证用户为候选人，否则拒绝访问。"""
    if curr_user.role != Role.Candidate:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate role required",
        )
    return curr_user


def require_employer(curr_user: User = Depends(get_current_user)) -> User:
    """要求已认证用户为雇主，否则拒绝访问。"""
    if curr_user.role != Role.Employer:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Employer role required",
        )
    return curr_user


class ProfileAlreadyExistsError(ValueError):
    """当前用户已有对应资料，不能再次创建。"""


class EmployerRoleRequiredError(ValueError):
    """公司资料只能由雇主账户创建。"""


def create_employer_profile(
    session: Session, curr_user: User, profile: EmployerProfileCreate
) -> EmployerProfilePublic:
    """为当前雇主首次创建公司资料，重复或失败时不覆盖已有记录。"""
    if curr_user.role != Role.Employer:
        raise EmployerRoleRequiredError("Employer role required")

    user_id = curr_user.id
    if session.get(EmployerProfile, user_id) is not None:
        raise ProfileAlreadyExistsError("Employer profile already exists")

    new_profile = EmployerProfile(
        user_id=user_id,
        company_name=profile.company_name,
        company_description=profile.company_description,
    )
    session.add(new_profile)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        # 主键同时防止并发重复创建，只将确认的资料重复转换为业务冲突。
        if session.get(EmployerProfile, user_id) is not None:
            raise ProfileAlreadyExistsError("Employer profile already exists") from error
        raise
    except SQLAlchemyError:
        session.rollback()
        raise

    session.refresh(new_profile)
    return EmployerProfilePublic.model_validate(new_profile)


class CandidateRoleRequiredError(ValueError):
    """候选人资料只能由候选人账户创建。"""


def normalize_skills(skills: list[str]) -> list[str]:
    """技能去首尾空白、转小写、去空项并去重，按名称排序返回。"""
    normalized = {skill.strip().lower() for skill in skills}
    normalized.discard("")
    return sorted(normalized)


def create_candidate_profile(
    session: Session, curr_user: User, profile: CandidateProfileCreate
) -> CandidateProfilePublic:
    """首次创建当前候选人的资料及技能，一次提交，失败全部回滚。"""
    if curr_user.role != Role.Candidate:
        raise CandidateRoleRequiredError("Candidate role required")

    user_id = curr_user.id
    if session.get(CandidateProfile, user_id) is not None:
        raise ProfileAlreadyExistsError("Candidate profile already exists")

    skills = normalize_skills(profile.skills)
    new_profile = CandidateProfile(
        user_id=user_id,
        display_name=profile.display_name,
        resume_text=profile.resume_text,
    )
    session.add(new_profile)
    for name in skills:
        new_skill = CandidateSkill(candidate_id=user_id, name=name)
        new_profile.skills.append(new_skill)
        session.add(new_skill)

    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if session.get(CandidateProfile, user_id) is not None:
            raise ProfileAlreadyExistsError("Candidate profile already exists") from error
        raise
    except SQLAlchemyError:
        session.rollback()
        raise

    session.refresh(new_profile)
    return CandidateProfilePublic(
        user_id=new_profile.user_id,
        display_name=new_profile.display_name,
        resume_text=new_profile.resume_text,
        skills=skills,
    )


    

