"""FP-EMP-3 申请人管理：列表字段与排序、状态四值、预约保留与权限边界。"""

import uuid

import pytest


def test_fp_emp_3_applicant_rows_contain_required_fields(
    client, make_employer, make_candidate, make_job, make_application
):
    """每行含身份、技能、匹配分、状态、预约；绝不含简历。"""
    employer = make_employer()
    candidate = make_candidate(name="Alice", skills=["python", "sql"])
    job = make_job(employer, required_skills=["python", "sql"])
    application = make_application(candidate, job)

    listed = client.get(
        f"/employer/jobs/{job['id']}/applications", headers=employer
    )
    assert listed.status_code == 200, listed.text
    assert "resume_text" not in listed.text
    rows = listed.json()
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {
        "application_id",
        "candidate_id",
        "display_name",
        "skills",
        "match_score",
        "status",
        "booking",
    }
    assert row["application_id"] == str(application.id)
    assert row["display_name"] == "Alice"
    assert row["skills"] == ["python", "sql"]
    assert row["match_score"] == 100
    assert row["status"] == "Pending"
    assert row["booking"] is None


def test_fp_emp_3_applicants_sorted_by_match_score_desc(
    client, make_employer, make_candidate, make_job, make_application
):
    """申请人按匹配分从高到低排列。"""
    employer = make_employer()
    job = make_job(employer, required_skills=["python", "sql"])
    strong = make_candidate(email="s@example.com", name="Strong", skills=["python", "sql"])
    weak = make_candidate(email="w@example.com", name="Weak", skills=["python"])
    none_ = make_candidate(email="n@example.com", name="None", skills=["rust"])
    for candidate_headers in (weak, none_, strong):
        make_application(candidate_headers, job)

    rows = client.get(
        f"/employer/jobs/{job['id']}/applications", headers=employer
    ).json()
    assert [(row["display_name"], row["match_score"]) for row in rows] == [
        ("Strong", 100),
        ("Weak", 50),
        ("None", 0),
    ]


def test_fp_emp_3_applicant_row_shows_booking(
    client, db, make_employer, make_candidate, make_job, make_application, make_slot
):
    """有预约时行内带出时段起止时间。"""
    employer = make_employer()
    candidate = make_candidate()
    job = make_job(employer)
    application = make_application(candidate, job)
    slot = make_slot(employer, job)

    from app.employer.model import Booking

    db.add(Booking(application_id=application.id, slot_id=slot.id))
    db.commit()

    rows = client.get(
        f"/employer/jobs/{job['id']}/applications", headers=employer
    ).json()
    booking = rows[0]["booking"]
    assert booking is not None
    assert booking["slot_id"] == str(slot.id)
    assert booking["starts_at"] is not None
    assert booking["ends_at"] is not None


@pytest.mark.parametrize(
    "new_status", ["Pending", "Interviewing", "Rejected", "Accepted"]
)
def test_fp_emp_3_set_status_all_four_values(
    client, db, make_employer, make_candidate, make_job, make_application, new_status
):
    """四个状态都可设置；非法取值 422。"""
    from app.employer.model import Application

    employer = make_employer()
    candidate = make_candidate()
    job = make_job(employer)
    application = make_application(candidate, job)

    response = client.patch(
        f"/employer/applications/{application.id}/status",
        json={"status": new_status},
        headers=employer,
    )
    assert response.status_code == 200, response.text
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
    assert body["application_id"] == str(application.id)

    db.expire_all()
    saved = db.get(Application, application.id)
    assert saved.status.value == new_status

    invalid = client.patch(
        f"/employer/applications/{application.id}/status",
        json={"status": "Hired"},
        headers=employer,
    )
    assert invalid.status_code == 422


def test_fp_emp_3_status_change_keeps_booking(
    client, db, make_employer, make_candidate, make_job, make_application, make_slot
):
    """离开 Interviewing 后预约仍与申请关联。"""
    from app.employer.model import Booking

    employer = make_employer()
    candidate = make_candidate()
    job = make_job(employer)
    application = make_application(candidate, job)
    slot = make_slot(employer, job)
    booking = Booking(application_id=application.id, slot_id=slot.id)
    db.add(booking)
    db.commit()
    booking_id, slot_id = booking.id, slot.id

    rejected = client.patch(
        f"/employer/applications/{application.id}/status",
        json={"status": "Rejected"},
        headers=employer,
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "Rejected"

    db.expire_all()
    saved = db.get(Booking, booking_id)
    assert saved is not None
    assert saved.application_id == application.id
    assert saved.slot_id == slot_id


def test_fp_emp_3_other_employer_and_candidate_cannot_change(
    client, db, make_employer, make_candidate, make_job, make_application
):
    """FP-SEC-1 边界：其他雇主 403，候选人 403，状态不变。"""
    from app.employer.model import Application

    owner = make_employer(email="owner@example.com", company_name="Owner Co")
    other = make_employer(email="other@example.com", company_name="Other Co")
    candidate = make_candidate()
    job = make_job(owner)
    application = make_application(candidate, job)

    foreign = client.patch(
        f"/employer/applications/{application.id}/status",
        json={"status": "Accepted"},
        headers=other,
    )
    assert foreign.status_code == 403
    assert foreign.json()["detail"] == "Not the owner of this job"

    by_candidate = client.patch(
        f"/employer/applications/{application.id}/status",
        json={"status": "Accepted"},
        headers=candidate,
    )
    assert by_candidate.status_code == 403
    assert by_candidate.json()["detail"] == "Employer role required"

    db.expire_all()
    saved = db.get(Application, application.id)
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


def test_fp_emp_3_applicant_list_owner_only(
    client, make_employer, make_candidate, make_job, make_application
):
    """他人职位的申请人列表 403；不存在的职位 404；不泄露简历。"""
    owner = make_employer(email="owner@example.com", company_name="Owner Co")
    other = make_employer(email="other@example.com", company_name="Other Co")
    candidate = make_candidate(name="Alice", skills=["python"],)
    # 简历放在资料里也不允许出现在申请人列表。
    job = make_job(owner)
    make_application(candidate, job)

    forbidden = client.get(
        f"/employer/jobs/{job['id']}/applications", headers=other
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Not the owner of this job"

    missing = client.get(
        f"/employer/jobs/{uuid.uuid4()}/applications", headers=owner
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Job not found"

    listed = client.get(
        f"/employer/jobs/{job['id']}/applications", headers=owner
    )
    assert listed.status_code == 200
    assert "resume_text" not in listed.text
