"""FP-CAN-2/3、FP-MATCH-1：推荐排序、唯一投递及申请范围。"""

import uuid

import pytest
from sqlalchemy import event
from sqlmodel import select

from app.employer.model import Application, ApplicationStatus, Job


def test_concurrent_duplicate_applications_have_one_winner(client, account, job, db):
    """真实并发投递只创建一次，重复请求不会变成数据库 500。"""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi.testclient import TestClient
    from app.main import app

    employer, _ = account("employer")
    candidate, candidate_id = account()
    posting = job(employer)
    barrier = Barrier(2)

    def submit():
        with TestClient(app) as local_client:
            barrier.wait(timeout=10)
            return local_client.post(
                f"/candidate/jobs/{posting['id']}/applications", headers=candidate
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(submit) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert sorted(row.status_code for row in results) == [201, 409]
    assert (
        len(
            db.exec(
                select(Application).where(Application.candidate_id == candidate_id)
            ).all()
        )
        == 1
    )


def test_recommendations_share_scores_and_title_ties(client, account, job):
    employer, _ = account("employer")
    candidate, _ = account(skills=[" PYTHON ", "python", ""])
    postings = [
        job(employer, title=title, required_skills=skills)
        for title, skills in [
            ("Zulu", ["python"]),
            ("alpha", ["python"]),
            ("ALPHA", []),
            ("Half", ["python", "sql"]),
            ("Zero", ["rust"]),
        ]
    ]
    rows = client.get("/candidate/jobs", headers=candidate).json()
    assert [row["match_score"] for row in rows] == [100, 100, 100, 50, 0]
    assert [(r["title"].lower(), r["id"]) for r in rows[:3]] == sorted(
        (r["title"].lower(), r["id"]) for r in rows[:3]
    )
    for posting in postings:
        applied = client.post(
            f"/candidate/jobs/{posting['id']}/applications", headers=candidate
        )
        assert applied.status_code == 201
        theirs = client.get(
            f"/employer/jobs/{posting['id']}/applications", headers=employer
        ).json()[0]
        ours = client.get(f"/candidate/jobs/{posting['id']}", headers=candidate).json()
        assert ours["match_score"] == theirs["match_score"]
        assert ours["applied"] is True


def test_recommendation_queries_do_not_grow_per_job(client, account, job, engine):
    employer, _ = account("employer")
    candidate, _ = account()
    job(employer)
    counts = []

    def count_queries(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            counts.append(statement)

    def measured(path):
        counts.clear()
        event.listen(engine, "before_cursor_execute", count_queries)
        try:
            response = client.get(path, headers=candidate)
            assert response.status_code == 200
            return len(counts)
        finally:
            event.remove(engine, "before_cursor_execute", count_queries)

    one = measured("/candidate/jobs")
    assert one == 4  # 三次业务查询，加一次真实账号认证查询。
    for index in range(12):
        job(employer, title=f"Job {index}")
    assert measured("/candidate/jobs") == one
    for posting in client.get("/candidate/jobs", headers=candidate).json():
        assert (
            client.post(
                f"/candidate/jobs/{posting['id']}/applications", headers=candidate
            ).status_code
            == 201
        )
    assert measured("/candidate/applications") == 4


def test_recommendations_require_profile_even_without_jobs(client, account, job):
    """无技能不等于无资料；未建资料时保留原有 404 及错误优先级。"""
    candidate, _ = account(complete=False)
    expected = {"detail": "Candidate profile not found"}
    response = client.get("/candidate/jobs", headers=candidate)
    assert response.status_code == 404 and response.json() == expected
    employer, _ = account("employer")
    posting = job(employer)
    for path in ["/candidate/jobs", f"/candidate/jobs/{posting['id']}"]:
        response = client.get(path, headers=candidate)
        assert response.status_code == 404 and response.json() == expected
    missing = client.get(f"/candidate/jobs/{uuid.uuid4()}", headers=candidate)
    assert missing.status_code == 404 and missing.json() == {"detail": "Job not found"}


def test_deleted_missing_jobs_and_empty_lists(client, account, job):
    employer, _ = account("employer")
    candidate, _ = account()
    assert client.get("/candidate/jobs", headers=candidate).json() == []
    assert client.get("/candidate/applications", headers=candidate).json() == []
    posting = job(employer)
    assert (
        client.delete(f"/employer/jobs/{posting['id']}", headers=employer).status_code
        == 204
    )
    assert client.get("/candidate/jobs", headers=candidate).json() == []
    for job_id in [posting["id"], str(uuid.uuid4())]:
        assert (
            client.get(f"/candidate/jobs/{job_id}", headers=candidate).status_code
            == 404
        )
        assert (
            client.post(
                f"/candidate/jobs/{job_id}/applications", headers=candidate
            ).status_code
            == 404
        )
    assert (
        client.get("/candidate/jobs/not-a-uuid", headers=candidate).status_code == 422
    )


@pytest.mark.parametrize("state", list(ApplicationStatus))
def test_apply_once_in_every_status(client, account, job, db, state):
    employer, _ = account("employer")
    candidate, candidate_id = account()
    posting = job(employer)
    path = f"/candidate/jobs/{posting['id']}/applications"
    first = client.post(path, headers=candidate, json={})
    assert first.status_code == 201 and first.json()["status"] == "Pending"
    assert (
        client.patch(
            f"/employer/applications/{first.json()['application_id']}/status",
            headers=employer,
            json={"version": 1, "status": state.value},
        ).status_code
        == 200
    )
    duplicate = client.post(path, headers=candidate)
    assert (
        duplicate.status_code == 409 and duplicate.json()["detail"] == "Already applied"
    )
    rows = db.exec(
        select(Application).where(Application.candidate_id == candidate_id)
    ).all()
    assert len(rows) == 1 and rows[0].status == state
    assert client.get("/candidate/jobs", headers=candidate).json()[0]["applied"]


def test_application_isolation_and_historical_records(client, account, job, db):
    employer, _ = account("employer")
    candidate, _ = account()
    other, _ = account()
    posting = job(employer)
    path = f"/candidate/jobs/{posting['id']}/applications"
    assert (
        client.post(
            path, headers=candidate, json={"candidate_id": str(uuid.uuid4())}
        ).status_code
        == 422
    )
    assert (
        client.post(path, headers=candidate, json={"status": "Accepted"}).status_code
        == 422
    )
    application = client.post(path, headers=candidate).json()
    detail = f"/candidate/applications/{application['application_id']}"
    assert client.get(detail, headers=other).status_code == 403
    assert client.get(detail, headers=employer).status_code == 403
    assert client.get("/candidate/applications", headers=other).json() == []
    assert (
        client.patch(
            f"/employer/applications/{application['application_id']}/status",
            headers=candidate,
            json={"version": 1, "status": "Accepted"},
        ).status_code
        == 403
    )
    assert (
        client.get(
            f"/candidate/applications/{uuid.uuid4()}", headers=candidate
        ).status_code
        == 404
    )
    saved = db.get(Job, uuid.UUID(posting["id"]))
    saved.is_deleted = True
    db.add(saved)
    db.commit()
    assert client.get(detail, headers=candidate).json()["job_title"] == posting["title"]
    assert client.get("/candidate/applications", headers=candidate).json() == [
        client.get(detail, headers=candidate).json()
    ]


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/candidate/profile", None),
        ("PATCH", "/candidate/profile", {}),
        ("GET", "/candidate/jobs", None),
        ("GET", f"/candidate/jobs/{uuid.UUID(int=1)}", None),
        ("POST", f"/candidate/jobs/{uuid.UUID(int=1)}/applications", {}),
        ("GET", "/candidate/applications", None),
        ("GET", f"/candidate/applications/{uuid.UUID(int=1)}", None),
        ("GET", f"/candidate/applications/{uuid.UUID(int=1)}/slots", None),
        (
            "POST",
            f"/candidate/applications/{uuid.UUID(int=1)}/booking",
            {"slot_id": str(uuid.UUID(int=1))},
        ),
    ],
)
def test_candidate_endpoint_auth_matrix(client, account, method, path, payload):
    employer, _ = account("employer")
    assert client.request(method, path, json=payload).status_code == 401
    assert (
        client.request(method, path, headers=employer, json=payload).status_code == 403
    )



def test_job_detail_includes_company_description(client, account, job):
    """修前复现：雇主保存非空简介后，候选人详情必须收到同公司的原文。"""
    employer, _ = account("employer")
    candidate, _ = account(skills=["python"])
    description = "Example company introduction\nSecond line"
    updated = client.patch("/employer/company", headers=employer,
                           json={"version": 1, "company_description": description})
    assert updated.status_code == 200 and updated.json()["company_description"] == description
    posting = job(employer)
    response = client.get(f"/candidate/jobs/{posting['id']}", headers=candidate)
    assert response.status_code == 200
    assert response.json().get("company_description") == description


@pytest.mark.parametrize(
    "description",
    ["", " \t\n", "\u2003\u00a0", "公司介绍\n第二行 Résumé 🙂", "<b>Ordinary & literal</b>", "long-introduction-" * 500],
    ids=["empty", "whitespace", "unicode-space", "multiline", "markup-literal", "long-token"],
)
def test_company_description_roundtrip_preserves_other_job_fields(client, account, job, description):
    """同因边界：简介必须原样经过列表/详情，且不改变职位内容、匹配或投递。"""
    employer, _ = account("employer")
    candidate, _ = account(skills=["python"])
    posting = job(employer)
    path = f"/candidate/jobs/{posting['id']}"
    before = client.get(path, headers=candidate).json()
    assert before["company_description"] == ""
    saved = client.patch("/employer/company", headers=employer,
                         json={"version": 1, "company_description": description})
    assert saved.status_code == 200, saved.text
    detail = client.get(path, headers=candidate)
    assert detail.status_code == 200
    assert detail.json() == {**before, "company_description": description}
    listed = client.get("/candidate/jobs", headers=candidate).json()
    assert listed == [detail.json()]
    assert client.post(path + "/applications", headers=candidate).status_code == 201
    assert client.get(path, headers=candidate).json() == {**detail.json(), "applied": True}


def test_company_description_uses_employer_id_and_remains_live(client, account, job):
    """同名公司不会串简介；更新一家简介不改变另一家、职位版本或推荐次序。"""
    owners = [account("employer")[0], account("employer")[0]]
    candidate, _ = account(skills=["python"])
    postings = []
    for index, owner in enumerate(owners):
        saved = client.patch("/employer/company", headers=owner,
                             json={"version": 1, "company_description": f"Introduction {index}"})
        assert saved.status_code == 200
        postings.append(job(owner, title=f"Description job {index}"))
    before = client.get("/candidate/jobs", headers=candidate).json()
    assert {row["company_name"] for row in before} == {"Test Company"}
    assert {row["id"]: row["company_description"] for row in before} == {
        postings[index]["id"]: f"Introduction {index}" for index in range(2)
    }
    saved = client.patch("/employer/company", headers=owners[0],
                         json={"version": 2, "company_description": "Updated introduction"})
    assert saved.status_code == 200
    after = client.get("/candidate/jobs", headers=candidate).json()
    assert after == [dict(row, company_description="Updated introduction")
                     if row["id"] == postings[0]["id"] else row for row in before]
    for row in after:
        assert client.get(f"/candidate/jobs/{row['id']}", headers=candidate).json() == row
