"""与组员 candidate 模块的物理表兼容性。"""

import uuid

import pytest
from sqlmodel import select

from app.employer import service
from app.employer.model import Job


def test_candidate_job_list_reads_employer_jobs(
    client, make_candidate, make_employer, make_job
):
    """雇主发布的职位出现在候选人列表；软删除后消失。"""
    employer = make_employer(company_name="Acme")
    candidate = make_candidate(skills=["python", "sql"])
    job = make_job(employer, title="Backend", required_skills=["python", "sql"])

    listed = client.get("/candidate/jobs", headers=candidate)
    assert listed.status_code == 200
    row = next(item for item in listed.json() if item["id"] == job["id"])
    assert row["title"] == "Backend"
    assert row["required_skills"] == ["python", "sql"]

    removed = client.delete(f"/employer/jobs/{job['id']}", headers=employer)
    assert removed.status_code == 204
    assert job["id"] not in [
        item["id"] for item in client.get("/candidate/jobs", headers=candidate).json()
    ]


def test_apply_to_soft_deleted_job_is_404(
    client, make_candidate, make_employer, make_job
):
    """软删除后候选人申请返回 404。"""
    employer = make_employer()
    candidate = make_candidate(skills=["python"])
    job = make_job(employer)

    assert client.delete(f"/employer/jobs/{job['id']}", headers=employer).status_code == 204

    response = client.post(
        f"/candidate/jobs/{job['id']}/applications", headers=candidate
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"


def test_ensure_active_job_logical_fk(
    client, db, make_employer, make_job
):
    """有效职位返回 Job；已删除或不存在的职位抛 JobNotFoundError。"""
    employer = make_employer()
    job = make_job(employer)
    job_id = uuid.UUID(job["id"])

    active = service.ensure_active_job(db, job_id)
    assert active.id == job_id
    assert active.title == job["title"]

    removed = make_job(employer, title="Removed")
    assert client.delete(
        f"/employer/jobs/{removed['id']}", headers=employer
    ).status_code == 204
    db.expire_all()
    with pytest.raises(service.JobNotFoundError, match="Job not found"):
        service.ensure_active_job(db, uuid.UUID(removed["id"]))
    with pytest.raises(service.JobNotFoundError, match="Job not found"):
        service.ensure_active_job(db, uuid.uuid4())

    assert db.exec(select(Job).where(Job.is_deleted.is_(False))).all()
