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
    assert measured("/candidate/applications") <= 5


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
            json={"status": state.value},
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
            json={"status": "Accepted"},
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
