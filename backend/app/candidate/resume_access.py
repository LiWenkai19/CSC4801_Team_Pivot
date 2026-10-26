"""简历读取权限：候选人仅读本人，雇主仅读自己职位的申请人。"""
import uuid

from sqlmodel import Session, select

from app.candidate.model import Application, Job
from app.candidate.service import FlowError
from app.users.model import CandidateProfile, Role, User


def readable_profile(
    session: Session, user: User, candidate_id: uuid.UUID,
) -> CandidateProfile:
    if user.role != Role.Employer and not (
        user.role == Role.Candidate and user.id == candidate_id
    ):
        raise FlowError(403, "Candidate profiles are readable by their owner or employers")
    candidate = session.get(User, candidate_id)
    profile = session.get(CandidateProfile, candidate_id)
    if candidate is None or candidate.role != Role.Candidate or profile is None:
        raise FlowError(404, "Candidate profile not found")
    if user.role == Role.Employer:
        application = session.exec(
            select(Application.id)
            .join(Job, Application.job_id == Job.id)
            .where(Application.candidate_id == candidate_id, Job.employer_id == user.id)
            .limit(1)
        ).first()
        if application is None:
            raise FlowError(403, "Candidate has not applied to your jobs")
    return profile
