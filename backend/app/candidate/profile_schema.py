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


class UserCreate(TeamUserCreate):
    model_config = ConfigDict(extra='forbid')


class UserLogin(TeamUserLogin):
    model_config = ConfigDict(extra='forbid')


class CandidateProfileCreate(TeamCandidateProfileCreate):
    model_config = ConfigDict(extra='forbid')


class EmployerProfileCreate(TeamEmployerProfileCreate):
    model_config = ConfigDict(extra='forbid')


class UserPublic(TeamUserPublic):
    profile_completed: bool


class AuthResponse(Token):
    user: UserPublic


class CandidateProfileUpdate(TeamCandidateProfileCreate):
    """Partial updates reject explicit null and client-provided ownership."""
    model_config = ConfigDict(extra='forbid')
    display_name: NonBlankName | None = None
    resume_text: str | None = None
    skills: list[str] | None = None

    @field_validator('*', mode='before')
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError('Omit the field or use empty text/list; null is not allowed')
        return value

__all__ = ["UserCreate", "UserLogin", "CandidateProfileCreate", "CandidateProfilePublic", "EmployerProfileCreate", "EmployerProfilePublic", "NonBlankName", "Token", "UserPublic", "AuthResponse", "CandidateProfileUpdate"]
