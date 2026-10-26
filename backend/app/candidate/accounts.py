"""Compose stricter candidate-workspace routes around the team's existing handlers."""
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.candidate.profile_schema import (
    AuthResponse, CandidateProfileCreate, CandidateProfilePublic,
    EmployerProfileCreate, EmployerProfilePublic, Token,
    UserCreate, UserLogin, UserPublic,
)
from app.db.session import get_db
from app.users import router as team
from app.users.model import CandidateProfile, EmployerProfile, Role, User
from app.users.service import get_current_user, require_candidate, require_employer

user_router = APIRouter(prefix='/users', tags=['candidate workspace accounts'])


def public_user(session: Session, user: User) -> UserPublic:
    model = CandidateProfile if user.role == Role.Candidate else EmployerProfile
    return UserPublic(id=user.id, email=user.email, role=user.role,
                      profile_completed=session.get(model, user.id) is not None)


def auth_response(session: Session, result) -> AuthResponse:
    user = session.get(User, result.user.id)
    return AuthResponse(access_token=result.access_token, token_type=result.token_type,
                        user=public_user(session, user))


@user_router.post('/register', response_model=AuthResponse)
def register_user(user: UserCreate, session: Session = Depends(get_db)):
    return auth_response(session, team.register_user(user, session))


@user_router.post('/login', response_model=AuthResponse)
def login(user: UserLogin, session: Session = Depends(get_db)):
    return auth_response(session, team.login(user, session))


@user_router.post('/token', response_model=Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(),
                           session: Session = Depends(get_db)):
    return team.login_for_access_token(form_data, session)


@user_router.get('/me', response_model=UserPublic)
def read_me(curr_user: User = Depends(get_current_user), session: Session = Depends(get_db)):
    return public_user(session, curr_user)


@user_router.post('/candidate/profile', response_model=CandidateProfilePublic, status_code=201)
def submit_candidate_profile(profile: CandidateProfileCreate, session: Session = Depends(get_db),
                             curr_user: User = Depends(require_candidate)):
    return team.submit_candidate_profile(profile, session, curr_user)


@user_router.post('/employer/profile', response_model=EmployerProfilePublic, status_code=201)
def submit_employer_profile(profile: EmployerProfileCreate, session: Session = Depends(get_db),
                            curr_user: User = Depends(require_employer)):
    return team.submit_employer_profile(profile, session, curr_user)
