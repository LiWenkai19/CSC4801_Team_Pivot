from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session
from app.db.session import get_db
from app.users.schema import (
    AuthResponse,
    CandidateProfileCreate,
    CandidateProfilePublic,
    EmployerProfileCreate,
    EmployerProfilePublic,
    Token,
    UserCreate,
    UserLogin,
    UserPublic,
)
from app.users.service import create_user
from app.users.model import User
from app.users.service import get_current_user, authenticate_user
from app.users.service import (
    CandidateRoleRequiredError,
    EmployerRoleRequiredError,
    ProfileAlreadyExistsError,
    create_employer_profile,
    create_candidate_profile,
    require_candidate,
    require_employer,
)
from app.users.security import create_access_token



user_router = APIRouter(prefix="/users", tags=["users"])

@user_router.post("/register", response_model=AuthResponse)
def register_user(user: UserCreate, session: Session = Depends(get_db)) -> AuthResponse:
    """注册账户并签发访问令牌，供用户继续填写资料。"""
    try:
        new_user = create_user(session, user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    token = create_access_token(new_user.email)
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserPublic(id=new_user.id, email=new_user.email, role=new_user.role),
    )
        
@user_router.post("/login", response_model=AuthResponse)
def login(self_user: UserLogin, session: Session = Depends(get_db)) -> AuthResponse:
    """验证登录凭据并返回访问令牌与账户信息。"""
    try:
        user = authenticate_user(session, self_user.email, self_user.password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    token = create_access_token(user.email)
    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserPublic(id=user.id, email=user.email, role=user.role),
    )

# 测试环境的登陆接口
@user_router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_db),
) -> Token:
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.email)
    return Token(access_token=token, token_type="bearer")
    
    
    
@user_router.get("/me", response_model=UserPublic)
def read_me(curr_user: User = Depends(get_current_user)) -> UserPublic:
    """返回已认证用户的账户标识与角色。"""
    return UserPublic(
        id=curr_user.id,
        email=curr_user.email,
        role=curr_user.role,
    )    


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
    


