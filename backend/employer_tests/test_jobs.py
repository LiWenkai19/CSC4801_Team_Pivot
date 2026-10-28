"""FP-EMP-2 职位发布：字段、校验、所有权与软删除。"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import select

from app.employer import adapters
from app.employer.model import EmployerCompany, Job, JobSkill


def user_id(client, headers):
    """读取当前认证账户的 ID。"""
    return uuid.UUID(client.get("/users/me", headers=headers).json()["id"])


def test_fp_emp_2_create_job_fields_and_skills(client, db, make_employer):
    """技能去空白、转小写、去重；company_id 来自成员关系。"""
    headers = make_employer(company_name="Acme")
    job = client.post(
        "/employer/jobs",
        json={
            "title": " Backend Engineer ",
            "description": " Build services. ",
            "required_skills": [" Python", "python", "SQL", ""],
        },
        headers=headers,
    ).json()
    assert job["title"] == "Backend Engineer"
    assert job["description"] == " Build services. "
    assert job["required_skills"] == ["python", "sql"]
    assert job["company_name"] == "Acme"
    assert job["employer_id"] == str(user_id(client, headers))
    membership = db.get(EmployerCompany, user_id(client, headers))
    assert job["company_id"] == str(membership.company_id)

    saved = db.get(Job, uuid.UUID(job["id"]))
    assert saved.company_id == membership.company_id
    skills = sorted(
        row.name
        for row in db.exec(select(JobSkill).where(JobSkill.job_id == saved.id))
    )
    assert skills == ["python", "sql"]

    empty = client.post(
        "/employer/jobs",
        json={"title": "No skills", "description": "Empty list", "required_skills": []},
        headers=headers,
    )
    assert empty.status_code == 201
    assert empty.json()["required_skills"] == []


def test_fp_emp_2_create_job_validation(client, db, make_employer):
    """空白文本、缺字段、多余字段均 422；未关联公司 409。"""
    headers = make_employer()
    invalid_payloads = [
        {"title": "   ", "description": "Text"},
        {"title": "Title", "description": "   "},
        {"title": "Only title"},
        {"title": "Title", "description": "Text", "company_id": str(uuid.uuid4())},
        {"title": "Title", "description": "Text", "employer_id": str(uuid.uuid4())},
    ]
    for payload in invalid_payloads:
        response = client.post("/employer/jobs", json=payload, headers=headers)
        assert response.status_code == 422, payload
    assert db.exec(select(Job)).all() == []

    unlinked = make_employer(email="unlinked@example.com", company=False)
    missing_company = client.post(
        "/employer/jobs",
        json={"title": "Title", "description": "Text"},
        headers=unlinked,
    )
    assert missing_company.status_code == 409
    assert missing_company.json()["detail"] == "Company required"
    assert db.exec(select(Job)).all() == []


def test_fp_emp_2_list_and_get_only_own_active_jobs(
    client, make_candidate, make_employer, make_job
):
    """列表只含本人职位；他人职位 403，随机 UUID 404，候选人 403。"""
    first = make_employer(email="a@example.com", company_name="Company A")
    second = make_employer(email="b@example.com", company_name="Company B")
    older = make_job(first, title="Older")
    newer = make_job(first, title="Newer")
    foreign = make_job(second, title="Foreign")

    listed = client.get("/employer/jobs", headers=first)
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.json()]
    assert ids == [newer["id"], older["id"]]
    assert foreign["id"] not in ids

    forbidden = client.get(f"/employer/jobs/{foreign['id']}", headers=first)
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Not the owner of this job"

    missing = client.get(f"/employer/jobs/{uuid.uuid4()}", headers=first)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Job not found"

    candidate = make_candidate()
    denied = client.get("/employer/jobs", headers=candidate)
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Employer role required"


def test_fp_emp_2_update_job_replaces_skills_and_updated_at(
    client, db, make_employer, make_job
):
    """PATCH 整体替换技能、[] 清空、updated_at 变大、company_id 不变。"""
    headers = make_employer(company_name="Acme")
    job = make_job(headers, required_skills=["python", "sql"])
    original = client.get(f"/employer/jobs/{job['id']}", headers=headers).json()

    replaced = client.patch(
        f"/employer/jobs/{job['id']}",
        json={"title": "Data Engineer", "required_skills": [" Go ", "go", "Rust"]},
        headers=headers,
    )
    assert replaced.status_code == 200
    body = replaced.json()
    assert body["title"] == "Data Engineer"
    assert body["description"] == original["description"]
    assert body["required_skills"] == ["go", "rust"]
    assert body["company_id"] == original["company_id"]
    assert body["updated_at"] > original["updated_at"]

    cleared = client.patch(
        f"/employer/jobs/{job['id']}",
        json={"required_skills": []},
        headers=headers,
    )
    assert cleared.status_code == 200
    assert cleared.json()["required_skills"] == []
    assert cleared.json()["title"] == "Data Engineer"

    db.expire_all()
    saved = db.get(Job, uuid.UUID(job["id"]))
    assert saved.company_id == uuid.UUID(original["company_id"])
    assert db.exec(
        select(JobSkill).where(JobSkill.job_id == saved.id)
    ).all() == []


def test_fp_emp_2_other_employer_cannot_edit_or_delete(
    client, db, make_employer, make_job
):
    """FP-SEC-1 第 2 条：其他雇主 PATCH/DELETE 均 403，职位不变。"""
    owner = make_employer(email="owner@example.com", company_name="Owner Co")
    other = make_employer(email="other@example.com", company_name="Other Co")
    job = make_job(owner, title="Protected")

    patched = client.patch(
        f"/employer/jobs/{job['id']}", json={"title": "Hijacked"}, headers=other
    )
    assert patched.status_code == 403
    assert patched.json()["detail"] == "Not the owner of this job"

    deleted = client.delete(f"/employer/jobs/{job['id']}", headers=other)
    assert deleted.status_code == 403
    assert deleted.json()["detail"] == "Not the owner of this job"

    db.expire_all()
    saved = db.get(Job, uuid.UUID(job["id"]))
    assert saved.title == "Protected"
    assert saved.is_deleted is False


def test_fp_emp_2_soft_delete_without_dependents(client, db, make_employer, make_job):
    """无依赖时可删除：行保留并标记 is_deleted，之后 GET/DELETE 都 404。"""
    headers = make_employer()
    job = make_job(headers)

    removed = client.delete(f"/employer/jobs/{job['id']}", headers=headers)
    assert removed.status_code == 204
    assert removed.content == b""

    db.expire_all()
    saved = db.get(Job, uuid.UUID(job["id"]))
    assert saved is not None
    assert saved.is_deleted is True

    assert client.get(
        f"/employer/jobs/{job['id']}", headers=headers
    ).status_code == 404
    assert client.delete(
        f"/employer/jobs/{job['id']}", headers=headers
    ).status_code == 404
    listed = client.get("/employer/jobs", headers=headers).json()
    assert job["id"] not in [row["id"] for row in listed]


def test_fp_emp_2_delete_conflict_with_application(
    client, db, make_candidate, make_employer, make_job
):
    """有申请时删除返回 409，职位与申请都不变。"""
    employer = make_employer()
    candidate = make_candidate(skills=["python"])
    job = make_job(employer)

    applied = client.post(
        f"/candidate/jobs/{job['id']}/applications", headers=candidate
    )
    assert applied.status_code == 201

    conflict = client.delete(f"/employer/jobs/{job['id']}", headers=employer)
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Job has applications or interview slots"

    db.expire_all()
    saved = db.get(Job, uuid.UUID(job["id"]))
    assert saved.is_deleted is False
    assert len(db.exec(select(adapters.Application)).all()) == 1


def test_fp_emp_2_delete_conflict_with_interview_slot(
    client, db, make_employer, make_job
):
    """有面试时段时删除返回 409，记录不变。"""
    headers = make_employer()
    job = make_job(headers)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    slot = adapters.InterviewSlot(
        employer_id=user_id(client, headers),
        job_id=uuid.UUID(job["id"]),
        starts_at=start,
        ends_at=start + timedelta(minutes=30),
    )
    db.add(slot)
    db.commit()
    slot_id = slot.id

    conflict = client.delete(f"/employer/jobs/{job['id']}", headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["detail"] == "Job has applications or interview slots"

    db.expire_all()
    saved = db.get(Job, uuid.UUID(job["id"]))
    assert saved.is_deleted is False
    assert db.get(adapters.InterviewSlot, slot_id) is not None


def test_fp_sec_2_job_title_sql_metacharacters_are_bound(
    client, db, make_employer, make_job
):
    """FP-SEC-2：SQL 元字符作为绑定值原样存取，job 表仍可查询。"""
    headers = make_employer()
    payload = "x'); DROP TABLE job; --"
    job = make_job(headers, title=payload)
    assert job["title"] == payload

    fetched = client.get(f"/employer/jobs/{job['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["title"] == payload

    db.expire_all()
    assert db.exec(select(Job)).all() != []
