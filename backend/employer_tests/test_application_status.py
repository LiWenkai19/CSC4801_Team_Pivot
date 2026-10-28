"""FP-EMP-3 申请状态：四个取值、预约保留与权限边界。"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import select

from app.employer import adapters
from app.employer.model import Job


def create_application(client, employer, candidate):
    """雇主发布职位，候选人通过组员接口申请，返回申请响应。"""
    job = client.post(
        "/employer/jobs",
        json={
            "title": "Engineer",
            "description": "Build services.",
            "required_skills": ["python"],
        },
        headers=employer,
    ).json()
    applied = client.post(
        f"/candidate/jobs/{job['id']}/applications", headers=candidate
    )
    assert applied.status_code == 201, applied.text
    return job, applied.json()


@pytest.mark.parametrize(
    "new_status", ["Pending", "Interviewing", "Rejected", "Accepted"]
)
def test_fp_emp_3_set_status_all_four_values(
    client, db, make_candidate, make_employer, new_status
):
    """四个状态都可设置；非法取值 422。"""
    employer = make_employer()
    candidate = make_candidate()
    job, application = create_application(client, employer, candidate)

    response = client.patch(
        f"/employer/applications/{application['id']}/status",
        json={"status": new_status},
        headers=employer,
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "application_id",
        "job_id",
        "candidate_id",
        "status",
        "updated_at",
    }
    assert body["status"] == new_status
    assert body["job_id"] == job["id"]
    assert body["application_id"] == application["id"]

    db.expire_all()
    saved = db.get(adapters.Application, uuid.UUID(application["id"]))
    assert saved.status.value == new_status

    invalid = client.patch(
        f"/employer/applications/{application['id']}/status",
        json={"status": "Hired"},
        headers=employer,
    )
    assert invalid.status_code == 422


def test_fp_emp_3_status_change_keeps_booking(
    client, db, make_candidate, make_employer
):
    """离开 Interviewing 后预约仍与申请关联。"""
    employer = make_employer()
    candidate = make_candidate()
    job, application = create_application(client, employer, candidate)
    application_id = uuid.UUID(application["id"])

    interviewing = client.patch(
        f"/employer/applications/{application['id']}/status",
        json={"status": "Interviewing"},
        headers=employer,
    )
    assert interviewing.status_code == 200

    me = client.get("/users/me", headers=employer).json()
    start = datetime.now(timezone.utc) + timedelta(days=1)
    slot = adapters.InterviewSlot(
        employer_id=uuid.UUID(me["id"]),
        job_id=uuid.UUID(job["id"]),
        starts_at=start,
        ends_at=start + timedelta(minutes=30),
    )
    db.add(slot)
    db.flush()
    booking = adapters.Booking(application_id=application_id, slot_id=slot.id)
    db.add(booking)
    db.commit()
    booking_id, slot_id = booking.id, slot.id

    rejected = client.patch(
        f"/employer/applications/{application['id']}/status",
        json={"status": "Rejected"},
        headers=employer,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "Rejected"

    db.expire_all()
    saved = db.get(adapters.Booking, booking_id)
    assert saved is not None
    assert saved.application_id == application_id
    assert saved.slot_id == slot_id


def test_fp_emp_3_other_employer_and_candidate_cannot_change(
    client, db, make_candidate, make_employer
):
    """FP-SEC-1 第 2 条：其他雇主与候选人都不能改状态。"""
    owner = make_employer(email="owner@example.com", company_name="Owner Co")
    other = make_employer(email="other@example.com", company_name="Other Co")
    candidate = make_candidate()
    _, application = create_application(client, owner, candidate)

    foreign = client.patch(
        f"/employer/applications/{application['id']}/status",
        json={"status": "Accepted"},
        headers=other,
    )
    assert foreign.status_code == 403
    assert foreign.json()["detail"] == "Not the owner of this job"

    by_candidate = client.patch(
        f"/employer/applications/{application['id']}/status",
        json={"status": "Accepted"},
        headers=candidate,
    )
    assert by_candidate.status_code == 403
    assert by_candidate.json()["detail"] == "Employer role required"

    db.expire_all()
    saved = db.get(adapters.Application, uuid.UUID(application["id"]))
    assert saved.status.value == "Pending"


def test_fp_emp_3_missing_application_returns_404(client, make_employer):
    """不存在的申请返回 404。"""
    employer = make_employer()
    response = client.patch(
        f"/employer/applications/{uuid.uuid4()}/status",
        json={"status": "Accepted"},
        headers=employer,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Application not found"


def test_fp_emp_3_applicant_list_reuses_teammate_route(
    client, make_candidate, make_employer
):
    """组员的申请人列表可用，且不泄露简历；其他雇主 403。"""
    owner = make_employer(email="owner@example.com", company_name="Owner Co")
    other = make_employer(email="other@example.com", company_name="Other Co")
    candidate = make_candidate(name="Alice", skills=["python"])
    job, application = create_application(client, owner, candidate)
    candidate_id = client.get("/users/me", headers=candidate).json()["id"]

    listed = client.get(
        f"/employer/jobs/{job['id']}/applications", headers=owner
    )
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["candidate_id"] == candidate_id
    assert row["display_name"] == "Alice"
    assert row["status"] == "Pending"
    assert "resume_text" not in row
    assert "resume_text" not in listed.text

    forbidden = client.get(
        f"/employer/jobs/{job['id']}/applications", headers=other
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Job belongs to another employer"


def test_fp_emp_3_application_status_owned_job_uses_soft_deleted_rule(
    client, db, make_candidate, make_employer
):
    """状态修改按职位所有者判断；职位删除受申请阻止，不存在越权修改。"""
    employer = make_employer()
    candidate = make_candidate()
    job, application = create_application(client, employer, candidate)

    conflict = client.delete(f"/employer/jobs/{job['id']}", headers=employer)
    assert conflict.status_code == 409

    db.expire_all()
    saved = db.get(Job, uuid.UUID(job["id"]))
    assert saved.is_deleted is False
    assert db.exec(
        select(adapters.Application).where(
            adapters.Application.id == uuid.UUID(application["id"])
        )
    ).one() is not None
