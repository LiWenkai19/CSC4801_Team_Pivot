"""Compose stricter candidate-workspace routes around the team's existing handlers."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.candidate.profile_schema import (
    AuthResponse, CandidateProfileCreate, CandidateProfilePublic,
    EmployerProfileCreate, EmployerProfilePublic, Token,
    UserCreate, UserLogin, UserPublic,
)
from app.db.session import get_db
from app.users import router as team
from app.users.model import CandidateProfile, EmployerProfile, Role, User
from app.users.service import get_current_user, require_candidate, require_employer

# 这里包装复用团队账号处理函数；前缀决定下面接口都以 /users 开头。
user_router = APIRouter(prefix='/users', tags=['candidate workspace accounts'])


def public_user(session: Session, user: User) -> UserPublic:
    # 根据角色选择资料表；能查到该用户的资料就认为已经完成资料填写。
    model = CandidateProfile if user.role == Role.Candidate else EmployerProfile
    return UserPublic(id=user.id, email=user.email, role=user.role,
                      profile_completed=session.get(model, user.id) is not None)


def auth_response(session: Session, result) -> AuthResponse:
    # 将团队认证结果转换成前端需要的 Token 和公开用户信息。
    user = session.get(User, result.user.id)
    return AuthResponse(access_token=result.access_token, token_type=result.token_type,
                        user=public_user(session, user))


@user_router.post('/register', response_model=AuthResponse)
def register_user(user: UserCreate, session: Session = Depends(get_db)):
    # Depends 由 FastAPI 提供数据库会话；候选人入口会覆盖为安全会话。
    try:
        return auth_response(session, team.register_user(user, session))
    except IntegrityError:
        # 并发注册同一邮箱可能同时通过预检查，最终由数据库唯一约束拦截。
        # 回滚失败事务后再查询，才能判断是否确实是邮箱重复。
        session.rollback()
        existing = session.exec(select(User.id).where(User.email == str(user.email))).first()
        if existing is not None:
            # 映射成现有的用户可理解错误；不是邮箱重复时保留原始异常。
            raise HTTPException(status_code=400, detail="User already exists") from None
        raise


@user_router.post('/login', response_model=AuthResponse)
def login(user: UserLogin, session: Session = Depends(get_db)):
    # JSON 登录复用团队身份验证，再补齐 profile_completed 供前端导航。
    return auth_response(session, team.login(user, session))


@user_router.post('/token', response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(),
                           session: Session = Depends(get_db)):
    # OAuth 客户端使用表单格式，与上面的 JSON 登录是两个不同入口。
    return team.login_for_access_token(form_data, session)


@user_router.get('/me', response_model=UserPublic)
def read_me(curr_user: User = Depends(get_current_user), session: Session = Depends(get_db)):
    # 先由 get_current_user 校验 Token，再返回当前账号的公开信息。
    return public_user(session, curr_user)


@user_router.post('/candidate/profile', response_model=CandidateProfilePublic, status_code=201)
def submit_candidate_profile(profile: CandidateProfileCreate, session: Session = Depends(get_db),
                             curr_user: User = Depends(require_candidate)):
    # require_candidate 限定候选人角色；资料归属来自当前账号，而非客户端指定。
    return team.submit_candidate_profile(profile, session, curr_user)


@user_router.post('/employer/profile', response_model=EmployerProfilePublic, status_code=201)
def submit_employer_profile(profile: EmployerProfileCreate, session: Session = Depends(get_db),
                            curr_user: User = Depends(require_employer)):
    # 同理，只有通过雇主角色检查的账号才能调用雇主资料创建逻辑。
    return team.submit_employer_profile(profile, session, curr_user)
