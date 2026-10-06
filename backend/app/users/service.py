import jwt
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, select

from app.users.model import CandidateProfile, CandidateSkill, EmployerProfile, Role, User
from app.users.schema import (
    CandidateProfileCreate,
    CandidateProfilePublic,
    EmployerProfileCreate,
    EmployerProfilePublic,
    UserCreate,
)
from app.users.security import hash_password, verify_password, decode_access_token
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
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

    
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/token")
def get_current_user(session: Session = Depends(get_db), token: str = Depends(oauth2_scheme)) -> User:
    try:
        email= decode_access_token(token)
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        user = get_user_by_email(session, email) 
        
        if user is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        return user
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")


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


    

