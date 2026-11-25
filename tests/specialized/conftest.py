import json
import os
from pathlib import Path
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

FROZEN = datetime(2030, 5, 1, tzinfo=timezone.utc)


def expected_managed_slot(slot, state):
    """Derive the management DTO independently from the raw SQL snapshot."""
    stored = next(row for row in state["interview_slot"] if row["id"] == slot["id"])
    booking = next((row for row in state["booking"] if row["slot_id"] == slot["id"]), None)
    result = dict(slot, is_booked=booking is not None, job_id=stored["job_id"], job_title=None,
                  application_id=None, applicant_name=None)
    if booking is not None:
        application = next(row for row in state["application"] if row["id"] == booking["application_id"])
        job = next(row for row in state["job"] if row["id"] == application["job_id"])
        profile = next(row for row in state["candidate_profile"] if row["user_id"] == application["candidate_id"])
        result.update(job_id=job["id"], job_title=job["title"], application_id=application["id"], applicant_name=profile["display_name"])
    return result


def expected_slots_with_booking_jobs(before, bookings):
    """Only booked slots may gain the exact job of their validated application."""
    jobs = {row["id"]: row["job_id"] for row in before["application"]}
    assignments = {row["slot_id"]: jobs[row["application_id"]] for row in bookings}
    return [dict(row, job_id=assignments.get(row["id"], row["job_id"])) for row in before["interview_slot"]]


OUT = Path(os.environ.get("SLOT_AUDIT_OUT", "."))
if os.environ.get("CSC4801_ISOLATED_AUDIT") != "1":
    raise RuntimeError(
        "Use python tests/specialized/run.py; direct collection cannot clear a shared database"
    )


@pytest.fixture(scope="session")
def engine():
    from app.users import model as users_model
    from app.employer import model as employer_model

    value = create_engine(os.environ["DATABASE_URL"], pool_size=8, max_overflow=4)
    yield value
    value.dispose()


@pytest.fixture(autouse=True)
def clean_and_clock(engine, monkeypatch):
    from app.candidate import service as candidate
    from app.interview import service as interview

    tables = ", ".join(
        '"' + table.name + '"' for table in SQLModel.metadata.sorted_tables
    )
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE " + tables + " RESTART IDENTITY CASCADE"))
    monkeypatch.setattr(interview, "utc_now", lambda: FROZEN)
    monkeypatch.setattr(candidate, "utc_now", lambda: FROZEN)


@pytest.fixture
def client(engine):
    from app.main import app
    from app.db.session import get_db

    def isolated_db(request: Request):
        with Session(engine) as session:
            actor = request.headers.get("X-Audit-Actor", "normal")
            session.connection().info["audit_actor"] = actor
            if actor in {"first", "second"}:
                session.execute(
                    text("SELECT set_config('application_name', :name, true)"),
                    {"name": "slot-audit-" + actor},
                )
                session.execute(text("SELECT set_config('lock_timeout', '8000', true)"))
                session.execute(
                    text("SELECT set_config('statement_timeout', '15000', true)")
                )
            yield session

    app.dependency_overrides[get_db] = isolated_db
    try:
        with TestClient(app, raise_server_exceptions=False) as value:
            value.event_hooks["response"].append(lambda response: value.cookies.clear())
            yield value
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def account(client):
    def create(role="employer", complete=True):
        response = client.post(
            "/users/register",
            json={
                "email": uuid.uuid4().hex + "@example.com",
                "password": "local-audit-only",
                "role": role,
            },
        )
        assert response.status_code == 200, response.text
        data = {
            "id": response.json()["user"]["id"],
            "headers": {
                "Cookie": "session=" + response.cookies["session"],
                "X-CSRF-Token": response.cookies["csrf_token"],
            },
        }
        if complete:
            payload = (
                {"company_name": "Audit company"}
                if role == "employer"
                else {"display_name": "Audit candidate", "skills": ["python"]}
            )
            saved = client.post(
                f"/users/{role}/profile", headers=data["headers"], json=payload
            )
            assert saved.status_code == 201, saved.text
        return data

    return create


@pytest.fixture
def create_slot(client):
    def create(owner, start=None):
        when = start if start is not None else FROZEN + timedelta(days=1)
        value = when.isoformat() if isinstance(when, datetime) else when
        response = client.post(
            "/employer/interview-slots",
            headers=owner["headers"],
            json={"starts_at": value},
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create


@pytest.fixture
def flow(client, account, create_slot):
    def create(owner=None, with_slot=True):
        owner = owner or account()
        candidate = account("candidate")
        posting = client.post(
            "/employer/jobs",
            headers=owner["headers"],
            json={
                "title": "Audit job",
                "description": "Synthetic test data",
                "required_skills": ["python"],
            },
        )
        assert posting.status_code == 201, posting.text
        applied = client.post(
            f"/candidate/jobs/{posting.json()['id']}/applications",
            headers=candidate["headers"],
            json={},
        )
        assert applied.status_code == 201, applied.text
        app_id = applied.json()["application_id"]
        changed = client.patch(
            f"/employer/applications/{app_id}/status",
            headers=owner["headers"],
            json={"version": 1, "status": "Interviewing"},
        )
        assert (
            changed.status_code == 200 and changed.json()["status"] == "Interviewing"
        ), changed.text
        result = {
            "owner": owner,
            "candidate": candidate,
            "application_id": app_id,
            "version": changed.json()["version"],
            "job_id": posting.json()["id"],
        }
        if with_slot:
            result["slot"] = create_slot(owner)
        return result

    return create


@pytest.fixture
def snapshot(engine):
    def read():
        values = {}
        with engine.begin() as connection:
            connection.execute(text("SELECT set_config('TimeZone','UTC',true)"))
            for name in (
                "application",
                "interview_slot",
                "booking",
                "job",
                "job_skill",
                "candidate_profile",
                "candidate_skill",
                "employer_profile",
            ):
                values[name] = connection.execute(
                    text(
                        f"SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text), '[]'::jsonb) FROM {name} t"
                    )
                ).scalar_one()
        return values

    return read


@pytest.fixture
def insert_slot(engine):
    def insert(owner, start, minutes=30, identifier=None):
        identifier = identifier or str(uuid.uuid4())
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO interview_slot(id,employer_id,starts_at,ends_at) VALUES(:id,:owner,:start,:end)"
                ),
                {
                    "id": uuid.UUID(identifier),
                    "owner": uuid.UUID(owner["id"]),
                    "start": start,
                    "end": start + timedelta(minutes=minutes),
                },
            )
        return identifier

    return insert


@pytest.fixture
def evidence(request):
    def save(name, value):
        folder = OUT / "evidence"
        folder.mkdir(exist_ok=True)
        safe = "".join(
            c if c.isalnum() or c in "-_." else "_" for c in request.node.name
        )
        (folder / (safe + "-" + name + ".json")).write_text(
            json.dumps(value, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    return save


@pytest.fixture
def add_applicant(client, account):
    def create(owner, job_id, candidate=None, status="Interviewing"):
        candidate = candidate or account("candidate")
        result = client.post(
            f"/candidate/jobs/{job_id}/applications",
            headers=candidate["headers"],
            json={},
        )
        assert result.status_code == 201, result.text
        application_id = result.json()["application_id"]
        result = client.patch(
            f"/employer/applications/{application_id}/status",
            headers=owner["headers"],
            json={"version": 1, "status": status},
        )
        assert result.status_code == 200 and result.json()["status"] == status, (
            result.text
        )
        return {
            "owner": owner,
            "candidate": candidate,
            "job_id": job_id,
            "application_id": application_id,
            "version": result.json()["version"],
        }

    return create


@pytest.fixture
def job(client):
    def create(owner, **fields):
        payload = {
            "title": "Regression job",
            "description": "Synthetic job description",
            "required_skills": ["python", "sql"],
        }
        payload.update(fields)
        response = client.post("/employer/jobs", headers=owner["headers"], json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return create
