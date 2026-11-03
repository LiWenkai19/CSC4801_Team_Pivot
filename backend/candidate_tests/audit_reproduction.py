"""审计复现更新为修复回归；显式运行，不重复加入常规测试。

文件名刻意不使用test_前缀；仅显式执行本文件，不加入正常回归套件。
"""
import logging

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session

from app.candidate.model import Job


def test_secure_sql_logging_hides_synthetic_resume(flow, caplog, monkeypatch):
    from app.candidate.secure_session import engine as runtime_engine

    assert runtime_engine.echo is False
    assert runtime_engine.hide_parameters is True
    monkeypatch.setattr(flow["engine"], "echo", True)
    monkeypatch.setattr(flow["engine"], "hide_parameters", True)
    sentinel = "AUDIT-ONLY-PRIVATE-RESUME-CONTENT"
    with caplog.at_level(logging.INFO, logger="sqlalchemy.engine.Engine"):
        response = flow["client"].patch(
            f"/users/candidates/{flow['ids'][0]}/profile",
            headers=flow["headers"][0], json={"resume_text": sentinel},
        )
    assert response.status_code == 200
    assert sentinel not in caplog.text
    print("REGRESSION SQL_ECHO: secure engine hides private parameters")


def test_recommendation_query_count_is_batched(flow):
    statements = []

    def record(*args):
        statements.append(args[2])

    event.listen(flow["engine"], "before_cursor_execute", record)
    try:
        small = flow["client"].get("/candidate/jobs", headers=flow["headers"][0])
        before = len(statements)
        assert small.status_code == 200
        with Session(flow["engine"]) as session:
            session.add_all(Job(employer_id=flow["ids"][2], title=f"Audit job {i}",
                                description="Synthetic audit only") for i in range(20))
            session.commit()
        statements.clear()
        large = flow["client"].get("/candidate/jobs", headers=flow["headers"][0])
        after = len(statements)
        assert large.status_code == 200
        assert len(large.json()) == len(small.json()) + 20
        assert after == before
        print(f"REGRESSION BATCHED: {len(small.json())} jobs -> {before} SQL statements; "
              f"{len(large.json())} jobs -> {after}; entire list returned without pagination")
    finally:
        event.remove(flow["engine"], "before_cursor_execute", record)


def test_register_unique_race_maps_to_duplicate_error(flow, monkeypatch):
    from app.candidate_main import app
    from app.users import service as accounts

    monkeypatch.setattr(accounts, "get_user_by_email", lambda *args: None)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/users/register", json={
            "email": "user0@example.com", "password": "Audit-only-123!", "role": "candidate",
        })
    assert response.status_code == 400
    assert response.json()["detail"] == "User already exists"
    print("REGRESSION REGISTRATION_RACE: duplicate maps to HTTP 400")


def test_current_profile_accepts_large_resume_and_skill_set(flow):
    resume = "审计用虚构内容" * 20_000
    skills = [f"audit-skill-{i}" for i in range(1_000)]
    response = flow["client"].patch(
        f"/users/candidates/{flow['ids'][0]}/profile", headers=flow["headers"][0],
        json={"resume_text": resume, "skills": skills},
    )
    assert response.status_code == 200
    assert len(response.json()["resume_text"]) == len(resume)
    assert len(response.json()["skills"]) == 1_000
    print(f"AUDIT INPUT_BOUNDS: accepted {len(resume)} resume characters and 1000 skills; "
          "no load or denial-of-service attack was performed")
