"""批量读取职位推荐，保留现有评分及排序契约。"""
from collections import defaultdict

from sqlmodel import Session, select

from app.candidate.model import Application, Job, JobSkill
from app.matching import job_sort_key
from app.users.model import CandidateProfile, CandidateSkill, EmployerProfile


def _chunks(values, size=500):
    for start in range(0, len(values), size):
        yield values[start:start + size]


def list_recommendations(session: Session, profile: CandidateProfile, scorer, score_kind):
    jobs = list(session.exec(select(Job).where(Job.is_deleted.is_(False))))
    if not jobs:
        return []
    job_ids = [job.id for job in jobs]
    employer_ids = list({job.employer_id for job in jobs})
    skills = defaultdict(list)
    applications = set()
    companies = {}
    for chunk in _chunks(job_ids):
        for skill in session.exec(select(JobSkill).where(JobSkill.job_id.in_(chunk))):
            skills[skill.job_id].append(skill.name)
        applications.update(session.exec(select(Application.job_id).where(
            Application.candidate_id == profile.user_id, Application.job_id.in_(chunk),
        )))
    for chunk in _chunks(employer_ids):
        companies.update({row.user_id: row.company_name for row in session.exec(
            select(EmployerProfile).where(EmployerProfile.user_id.in_(chunk))
        )})
    candidate_skills = list(session.exec(select(CandidateSkill.name).where(
        CandidateSkill.candidate_id == profile.user_id
    )))
    rows = []
    for job in jobs:
        required = skills[job.id]
        rows.append(dict(id=job.id, employer_id=job.employer_id, title=job.title,
                         description=job.description, company_name=companies[job.employer_id],
                         required_skills=sorted(required), score=scorer(candidate_skills, required),
                         score_kind=score_kind, applied=job.id in applications))
    return sorted(rows, key=job_sort_key)
