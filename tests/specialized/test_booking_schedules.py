from conftest import expected_slots_with_booking_jobs
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import importlib.util
from pathlib import Path
import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from conftest import FROZEN

# Reuse the prior tested observation helper without rerunning its nine scenarios.
previous = Path(__file__).resolve().parent / "test_slots_races.py"
spec = importlib.util.spec_from_file_location("prior_slot_lock_observer", previous)
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


def request_as_waiter(method, path, headers, body=None):
    from app.main import app

    with TestClient(app, raise_server_exceptions=False) as local:
        return local.request(
            method, path, headers={**headers, "X-Audit-Actor": "second"}, json=body
        )


def observe_waiters(engine, count):
    deadline = time.monotonic() + 6
    found = []
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            found = [
                dict(row)
                for row in connection.execute(
                    text(
                        "SELECT pid,wait_event_type,wait_event,query,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE datname=current_database() AND application_name='slot-audit-second' AND wait_event_type='Lock'"
                    )
                ).mappings()
            ]
        if len(found) >= count and all(row["blockers"] for row in found):
            return found
        time.sleep(0.02)
    raise AssertionError(
        f"Expected {count} blocked PostgreSQL requests, observed {len(found)}"
    )


@pytest.mark.parametrize("operation", ["create", "delete", "book"])
def test_time_is_rechecked_after_database_lock_wait(
    client, account, flow, engine, snapshot, evidence, monkeypatch, operation
):
    from app.candidate import service as candidate
    from app.interview import service as interview

    clock = {"now": FROZEN}
    monkeypatch.setattr(candidate, "utc_now", lambda: clock["now"])
    monkeypatch.setattr(interview, "utc_now", lambda: clock["now"])
    target_start = FROZEN + timedelta(days=1)
    if operation == "create":
        owner = account()
        lock_sql = "SELECT user_id FROM employer_profile WHERE user_id=:id FOR UPDATE"
        lock_id = owner["id"]
        args = (
            "POST",
            "/employer/interview-slots",
            owner["headers"],
            {"starts_at": target_start.isoformat()},
        )
    else:
        data = flow()
        lock_sql = "SELECT id FROM interview_slot WHERE id=:id FOR UPDATE"
        lock_id = data["slot"]["id"]
        args = (
            (
                "DELETE",
                "/employer/interview-slots/" + lock_id,
                data["owner"]["headers"],
                None,
            )
            if operation == "delete"
            else (
                "POST",
                f"/candidate/applications/{data['application_id']}/booking",
                data["candidate"]["headers"],
                {"slot_id": lock_id},
            )
        )
    before = snapshot()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with engine.begin() as holder:
            holder.execute(text(lock_sql), {"id": uuid.UUID(lock_id)})
            future = pool.submit(request_as_waiter, *args)
            waits = observe_waiters(engine, 1)
            clock["now"] = target_start
        response = future.result(timeout=15)
    after = snapshot()
    evidence(
        "time-wait",
        {
            "operation": operation,
            "waits": waits,
            "clock_before": FROZEN,
            "clock_after": clock["now"],
            "response_status": response.status_code,
            "response": response.text,
            "state_unchanged": before == after,
        },
    )
    assert response.status_code == (422 if operation == "create" else 409), (
        response.text
    )
    assert response.json()["detail"] == (
        "Slot must start in the future"
        if operation == "create"
        else "Slot is in the past"
    )
    assert after == before


@pytest.mark.parametrize(
    "kind", ["three-candidates-one-slot", "one-application-three-slots"]
)
def test_three_simultaneously_waiting_requests_have_exactly_one_booking(
    client, flow, add_applicant, create_slot, engine, snapshot, evidence, kind
):
    first = flow()
    if kind == "three-candidates-one-slot":
        entries = [
            first,
            add_applicant(first["owner"], first["job_id"]),
            add_applicant(first["owner"], first["job_id"]),
        ]
        specs = [
            (
                "POST",
                f"/candidate/applications/{row['application_id']}/booking",
                row["candidate"]["headers"],
                {"slot_id": first["slot"]["id"]},
            )
            for row in entries
        ]
        lock_sql = "SELECT id FROM interview_slot WHERE id=:id FOR UPDATE"
        lock_id = first["slot"]["id"]
    else:
        slots = [
            first["slot"],
            create_slot(first["owner"], FROZEN + timedelta(days=2)),
            create_slot(first["owner"], FROZEN + timedelta(days=3)),
        ]
        specs = [
            (
                "POST",
                f"/candidate/applications/{first['application_id']}/booking",
                first["candidate"]["headers"],
                {"slot_id": slot["id"]},
            )
            for slot in slots
        ]
        lock_sql = "SELECT id FROM application WHERE id=:id FOR UPDATE"
        lock_id = first["application_id"]
    before = snapshot()
    with ThreadPoolExecutor(max_workers=3) as pool:
        with engine.begin() as holder:
            holder.execute(text(lock_sql), {"id": uuid.UUID(lock_id)})
            futures = [pool.submit(request_as_waiter, *args) for args in specs]
            waits = observe_waiters(engine, 3)
        responses = [future.result(timeout=15) for future in futures]
    after = snapshot()
    evidence(
        "three-way",
        {
            "kind": kind,
            "waiters": waits,
            "statuses": [r.status_code for r in responses],
            "responses": [r.text for r in responses],
            "booking_count": len(after["booking"]),
        },
    )
    assert sorted(r.status_code for r in responses) == [201, 409, 409], [
        r.text for r in responses
    ]
    assert len(after["booking"]) == 1
    assert (
        after["application"] == before["application"]
        and after["interview_slot"] == expected_slots_with_booking_jobs(before, after["booking"])
        and after["job"] == before["job"]
    )
    for response in responses:
        if response.status_code == 409:
            assert response.json()["detail"] == (
                "Slot already booked"
                if kind == "three-candidates-one-slot"
                else "Application already booked"
            )
    winners = [i for i, r in enumerate(responses) if r.status_code == 201]
    win = winners[0]
    assert after["booking"][0]["application_id"] == specs[win][1].split("/")[3]
    assert after["booking"][0]["slot_id"] == specs[win][3]["slot_id"]


@pytest.mark.parametrize("order", ["apply-first", "delete-first"])
def test_job_delete_and_application_have_serializable_business_outcome(
    client, account, engine, snapshot, evidence, order
):
    owner, candidate = account(), account("candidate")
    job = client.post(
        "/employer/jobs",
        headers=owner["headers"],
        json={
            "title": "Race job",
            "description": "Synthetic application/delete race",
            "required_skills": [],
        },
    )
    assert job.status_code == 201, job.text
    identifier = job.json()["id"]
    apply = (
        "POST",
        f"/candidate/jobs/{identifier}/applications",
        candidate["headers"],
        {},
    )
    delete = ("DELETE", f"/employer/jobs/{identifier}", owner["headers"], None)
    first, second = (apply, delete) if order == "apply-first" else (delete, apply)
    result = prior.run_locked_pair(engine, first, second, "job", evidence)
    assert [r.status_code for r in result] == (
        [201, 409] if order == "apply-first" else [204, 404]
    ), [r.text for r in result]
    final = snapshot()
    assert final["booking"] == [] and final["interview_slot"] == []
    assert final["job"][0]["is_deleted"] == (order == "delete-first")
    assert len(final["application"]) == (1 if order == "apply-first" else 0)
    if final["application"]:
        assert (
            final["application"][0]["job_id"] == identifier
            and final["application"][0]["status"] == "Pending"
        )
