from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlmodel import Session
from app.core.config import settings
from app.db.session import get_db
from app.users.schema import (
    AuthResponse,
    CandidateProfileCreate,
    CandidateProfilePublic,
    EmployerProfileCreate,
    EmployerProfilePublic,
    UserCreate,
    UserLogin,
    UserPublic,
)
from app.users.service import create_user
from app.users.model import User, UserSession
from app.users.service import get_current_user, authenticate_user
from app.users.service import (
    CandidateRoleRequiredError,
    EmployerRoleRequiredError,
    ProfileAlreadyExistsError,
    create_employer_profile,
    create_candidate_profile,
    get_current_user_public,
    create_session,
    require_candidate,
    require_csrf,
    require_employer,
    revoke_session,
)


user_router = APIRouter(prefix="/users", tags=["users"])


def _set_auth_cookies(response: Response, token: str, row: UserSession, remember_me: bool) -> None:
    """下发两个 Cookie：会话 ID（HttpOnly，JS 读不到）和 CSRF 令牌（JS 可读）。

    凭证只经 Set-Cookie 传递，不出现在响应体中（FP-AUTH-2）。
    """
    # max_age=None 表示浏览器会话 Cookie：关闭浏览器即丢弃。
    max_age = settings.SESSION_REMEMBER_DAYS * 24 * 3600 if remember_me else None
    common = {
        "max_age": max_age,
        "path": "/",
        "samesite": "lax",
        "secure": settings.COOKIE_SECURE,
    }
    response.set_cookie(settings.SESSION_COOKIE_NAME, token, httponly=True, **common)
    response.set_cookie(settings.CSRF_COOKIE_NAME, row.csrf_token, httponly=False, **common)


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/")


@user_router.post("/register", response_model=AuthResponse)
def register_user(
    user: UserCreate, response: Response, session: Session = Depends(get_db)
) -> AuthResponse:
    """注册账户并直接建立会话，返回资料完成状态，供用户继续填写资料。"""
    try:
        new_user = create_user(session, user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    token, row = create_session(session, new_user, remember_me=False)
    _set_auth_cookies(response, token, row, remember_me=False)
    return AuthResponse(user=get_current_user_public(session, new_user))
        
@user_router.post("/login", response_model=AuthResponse)
def login(
    self_user: UserLogin, response: Response, session: Session = Depends(get_db)
) -> AuthResponse:
    """验证登录凭据并建立新会话；登录前尚无会话，因此不校验 CSRF。"""
    try:
        user = authenticate_user(session, self_user.email, self_user.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    token, row = create_session(session, user, self_user.remember_me)
    _set_auth_cookies(response, token, row, self_user.remember_me)
    return AuthResponse(user=get_current_user_public(session, user))


@user_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session: Session = Depends(get_db),
    sess: UserSession = Depends(require_csrf),
) -> None:
    """删除服务端会话并清除 Cookie；旧 Cookie 即使被留存也已失效（FP-AUTH-1 登出）。"""
    revoke_session(session, sess)
    _clear_auth_cookies(response)


@user_router.get("/me", response_model=UserPublic)
def read_me(
    curr_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> UserPublic:
    """返回本人账户及当前角色资料的完成状态。"""
    return get_current_user_public(session, curr_user)


@user_router.post(
    "/employer/profile",
    response_model=EmployerProfilePublic,
    status_code=status.HTTP_201_CREATED,
)
def submit_employer_profile(
    profile: EmployerProfileCreate,
    session: Session = Depends(get_db),
    curr_user: User = Depends(require_employer),
) -> EmployerProfilePublic:
    """首次保存当前雇主的公司资料，拒绝角色不符及重复创建。"""
    try:
        return create_employer_profile(session, curr_user, profile)
    except ProfileAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    except EmployerRoleRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(error)
        ) from error


@user_router.post(
    "/candidate/profile",
    response_model=CandidateProfilePublic,
    status_code=status.HTTP_201_CREATED,
)
def submit_candidate_profile(
    profile: CandidateProfileCreate,
    session: Session = Depends(get_db),
    curr_user: User = Depends(require_candidate),
) -> CandidateProfilePublic:
    """首次保存候选人本人的资料和技能，简历仅返回给本人。"""
    try:
        return create_candidate_profile(session, curr_user, profile)
    except ProfileAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(error)
        ) from error
    except CandidateRoleRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(error)
        ) from error
    


