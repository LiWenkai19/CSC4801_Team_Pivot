from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session

STATES = ["Pending", "Interviewing", "Rejected", "Accepted"]


@pytest.mark.parametrize("before", STATES)
@pytest.mark.parametrize("after", STATES)
def test_booked_status_transitions_preserve_new_managed_flag(
    client, flow, snapshot, before, after
):
    data = flow()
    owner, candidate = data["owner"], data["candidate"]
    app = data["application_id"]
    slot = data["slot"]
    booked = client.post(
        f"/candidate/applications/{app}/booking",
        headers=candidate["headers"],
        json={"slot_id": slot["id"]},
    )
    assert booked.status_code == 201
    assert (
        client.patch(
            f"/employer/applications/{app}/status",
            headers=owner["headers"],
            json={"status": before},
        ).status_code
        == 200
    )
    before_state = snapshot()
    updated = client.patch(
        f"/employer/applications/{app}/status",
        headers=owner["headers"],
        json={"status": after},
    )
    assert updated.status_code == 200 and updated.json()["status"] == after
    listed = client.get("/employer/interview-slots", headers=owner["headers"])
    assert listed.status_code == 200 and listed.json() == [dict(slot, is_booked=True)]
    assert snapshot()["booking"] == before_state["booking"]
    assert snapshot()["interview_slot"] == before_state["interview_slot"]
    ours = client.get(
        f"/candidate/applications/{app}", headers=candidate["headers"]
    ).json()
    assert ours["booking"]["slot_id"] == slot["id"] and ours["status"] == after
    rejected = client.delete(
        "/employer/interview-slots/" + slot["id"], headers=owner["headers"]
    )
    assert rejected.status_code == 409


def test_new_managed_list_owner_time_flags_legacy_duration_and_sort(
    client, account, insert_slot, flow, create_slot, engine
):
    owner = account()
    other = account()
    start = datetime(2030, 5, 2, tzinfo=timezone.utc)
    ordinary = insert_slot(
        owner, start + timedelta(hours=1), 30, identifier=str(uuid.UUID(int=12))
    )
    legacy = insert_slot(
        owner, start + timedelta(hours=2), 60, identifier=str(uuid.UUID(int=13))
    )
    insert_slot(owner, start - timedelta(days=2), 30)
    insert_slot(other, start, 30)
    data = flow(owner)
    slot = data["slot"]
    ap = data["application_id"]
    assert (
        client.post(
            f"/candidate/applications/{ap}/booking",
            headers=data["candidate"]["headers"],
            json={"slot_id": slot["id"]},
        ).status_code
        == 201
    )
    rows = client.get("/employer/interview-slots", headers=owner["headers"]).json()
    expected_ids = [slot["id"], ordinary, legacy]
    assert [x["id"] for x in rows] == expected_ids
    assert {x["id"]: x["is_booked"] for x in rows} == {
        ordinary: False,
        legacy: False,
        slot["id"]: True,
    }


def test_ordinary_create_list_new_schema_round_trip(client, account):
    owner = account()
    made = client.post(
        "/employer/interview-slots",
        headers=owner["headers"],
        json={"starts_at": "2031-06-01T10:00:00+08:00"},
    )
    assert made.status_code == 201
    assert client.get("/employer/interview-slots", headers=owner["headers"]).json() == [
        dict(made.json(), is_booked=False)
    ]


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_concurrent_first_profile_create_has_one_success_one_conflict(
    client, account, engine, evidence, role
):
    actor = account(role, complete=False)
    gate = Barrier(2)
    table = role + "_profile"

    def sync(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().startswith("INSERT INTO " + table):
            gate.wait(timeout=8)

    event.listen(engine, "before_cursor_execute", sync)
    try:

        def request(i):
            body = (
                {"display_name": "Candidate " + str(i), "skills": ["python"]}
                if role == "candidate"
                else {"company_name": "Company " + str(i)}
            )
            return client.post(
                "/users/" + role + "/profile", headers=actor["headers"], json=body
            )

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(request, range(2)))
    finally:
        event.remove(engine, "before_cursor_execute", sync)
    codes = sorted(r.status_code for r in responses)
    with engine.connect() as c:
        count = c.execute(text("SELECT count(*) FROM " + table)).scalar_one()
    evidence(
        "profile-create-race", {"role": role, "codes": codes, "profile_count": count}
    )
    assert codes == [201, 409] and count == 1


@pytest.mark.parametrize("role", ["candidate", "employer"])
@pytest.mark.parametrize("kind", ["integrity", "generic"])
def test_profile_failed_commit_rolls_back_real_flush(
    client, account, snapshot, monkeypatch, role, kind
):
    actor = account(role, complete=False)
    before = snapshot()
    original = Session.commit

    def fail(session):
        session.flush()
        if kind == "integrity":
            raise IntegrityError(
                "synthetic test failure", {}, Exception("unknown constraint")
            )
        raise SQLAlchemyError("synthetic test failure")

    monkeypatch.setattr(Session, "commit", fail)
    payload = (
        {"display_name": "Rollback candidate", "skills": ["python", "sql"]}
        if role == "candidate"
        else {"company_name": "Rollback company"}
    )
    response = client.post(
        "/users/" + role + "/profile", headers=actor["headers"], json=payload
    )
    assert response.status_code == 500
    monkeypatch.setattr(Session, "commit", original)
    assert snapshot() == before
    assert (
        client.post(
            "/users/" + role + "/profile", headers=actor["headers"], json=payload
        ).status_code
        == 201
    )


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_service_role_precondition_independent_of_router(engine, role):
    from app.users.model import User, Role
    from app.users import service, schema

    wrong = User(
        role=Role.Employer if role == "candidate" else Role.Candidate,
        email="synthetic-role@example.com",
        hashed_password="unused",
    )
    payload = (
        schema.CandidateProfileCreate(display_name="Normal")
        if role == "candidate"
        else schema.EmployerProfileCreate(company_name="Normal")
    )
    error = (
        service.CandidateRoleRequiredError
        if role == "candidate"
        else service.EmployerRoleRequiredError
    )
    action = (
        service.create_candidate_profile
        if role == "candidate"
        else service.create_employer_profile
    )
    with Session(engine) as session:
        with pytest.raises(error):
            action(session, wrong, payload)
