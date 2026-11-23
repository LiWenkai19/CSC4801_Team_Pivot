from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from conftest import FROZEN

PATH = "/employer/interview-slots"


def run_locked_pair(engine, first, second, lock_table, evidence):
    """Hold the first real row lock, observe the second transaction waiting, then release."""
    from app.main import app

    acquired, release = Event(), Event()
    observed = []

    def after_cursor(connection, cursor, statement, parameters, context, executemany):
        if (
            connection.info.get("audit_actor") == "first"
            and "FOR UPDATE" in statement.upper()
            and lock_table in statement
            and not acquired.is_set()
        ):
            acquired.set()
            if not release.wait(timeout=12):
                raise RuntimeError("Test lock release timed out")

    def request(actor, spec):
        method, path, headers, payload = spec
        with TestClient(app, raise_server_exceptions=False) as local:
            return local.request(
                method, path, headers={**headers, "X-Audit-Actor": actor}, json=payload
            )

    event.listen(engine, "after_cursor_execute", after_cursor)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(request, "first", first)
            try:
                assert acquired.wait(timeout=6), (
                    "First request never acquired the expected database lock"
                )
                b = pool.submit(request, "second", second)
                deadline = time.monotonic() + 6
                while time.monotonic() < deadline:
                    with engine.connect() as connection:
                        rows = (
                            connection.execute(
                                text(
                                    "SELECT pid,wait_event_type,wait_event,query,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE datname=current_database() AND application_name='slot-audit-second' AND wait_event_type='Lock'"
                                )
                            )
                            .mappings()
                            .all()
                        )
                        observed = [dict(row) for row in rows]
                    if observed:
                        break
                    time.sleep(0.02)
                assert observed and observed[0]["blockers"], (
                    "Second request was not observed waiting for a PostgreSQL lock"
                )
            finally:
                release.set()
            results = [a.result(timeout=15), b.result(timeout=15)]
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", after_cursor)
    evidence(
        "lock-schedule",
        {
            "lock_table": lock_table,
            "second_database_wait": observed,
            "responses": [{"status": r.status_code, "body": r.text} for r in results],
        },
    )
    return results


@pytest.mark.parametrize(
    "kind",
    [
        "overlap-create",
        "adjacent-create",
        "delete-before-book",
        "book-before-delete",
        "two-candidates-one-slot",
        "one-application-two-slots",
        "reject-before-book",
        "book-before-reject",
        "double-delete",
    ],
)
def test_real_database_schedules_preserve_contract(
    client, account, create_slot, flow, snapshot, engine, evidence, kind
):
    if kind in {"overlap-create", "adjacent-create"}:
        owner = account()
        first = ("POST", PATH, owner["headers"], {"starts_at": "2030-05-02T00:00:00Z"})
        second = (
            "POST",
            PATH,
            owner["headers"],
            {
                "starts_at": "2030-05-02T00:00:00Z"
                if kind == "overlap-create"
                else "2030-05-02T00:30:00Z"
            },
        )
        responses = run_locked_pair(engine, first, second, "employer_profile", evidence)
        assert [r.status_code for r in responses] == (
            [201, 409] if kind == "overlap-create" else [201, 201]
        ), [r.text for r in responses]
        assert len(snapshot()["interview_slot"]) == (
            1 if kind == "overlap-create" else 2
        )
        return
    data = flow()
    slot_path = PATH + "/" + data["slot"]["id"]
    booking_path = f"/candidate/applications/{data['application_id']}/booking"
    delete = ("DELETE", slot_path, data["owner"]["headers"], None)
    booking = (
        "POST",
        booking_path,
        data["candidate"]["headers"],
        {"slot_id": data["slot"]["id"]},
    )
    reject = (
        "PATCH",
        f"/employer/applications/{data['application_id']}/status",
        data["owner"]["headers"],
        {"status": "Rejected"},
    )
    lock_table = "interview_slot"
    if kind == "delete-before-book":
        first, second, expected = delete, booking, [204, 404]
    elif kind == "book-before-delete":
        first, second, expected = booking, delete, [201, 409]
    elif kind == "double-delete":
        first, second, expected = delete, delete, [204, 404]
    elif kind == "reject-before-book":
        first, second, expected, lock_table = reject, booking, [200, 409], "application"
    elif kind == "book-before-reject":
        first, second, expected, lock_table = booking, reject, [201, 200], "application"
    elif kind == "two-candidates-one-slot":
        extra = flow(owner=data["owner"], with_slot=False)
        first, second, expected = (
            booking,
            (
                "POST",
                f"/candidate/applications/{extra['application_id']}/booking",
                extra["candidate"]["headers"],
                {"slot_id": data["slot"]["id"]},
            ),
            [201, 409],
        )
    elif kind == "one-application-two-slots":
        extra = create_slot(data["owner"], FROZEN + timedelta(days=2))
        first, second, expected, lock_table = (
            booking,
            (
                "POST",
                booking_path,
                data["candidate"]["headers"],
                {"slot_id": extra["id"]},
            ),
            [201, 409],
            "application",
        )
    before = snapshot()
    responses = run_locked_pair(engine, first, second, lock_table, evidence)
    assert [r.status_code for r in responses] == expected, [r.text for r in responses]
    after = snapshot()
    if kind in {"delete-before-book", "double-delete"}:
        assert after["interview_slot"] == [] and after["booking"] == []
        assert after["application"] == before["application"]
    elif kind == "reject-before-book":
        assert (
            after["booking"] == [] and after["application"][0]["status"] == "Rejected"
        )
        assert after["interview_slot"] == before["interview_slot"]
    else:
        assert len(after["booking"]) == 1
        row = after["booking"][0]
        assert (
            row["application_id"] == data["application_id"]
            and row["slot_id"] == data["slot"]["id"]
        )
        assert after["interview_slot"] == before["interview_slot"]
        if kind == "book-before-reject":
            assert after["application"][0]["status"] == "Rejected"
        else:
            assert after["application"] == before["application"]
        assert client.get(PATH, headers=data["owner"]["headers"]).json() == (
            [{**data["slot"], "is_booked": True}]
            + (
                [{**extra, "is_booked": False}]
                if kind == "one-application-two-slots"
                else []
            )
        )
    if kind == "two-candidates-one-slot":
        assert responses[1].json()["detail"] == "Slot already booked"
    assert after["job"] == before["job"]
