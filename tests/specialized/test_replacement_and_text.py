from concurrent.futures import ThreadPoolExecutor
from threading import Event
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text


def overlapping_replacements(
    engine, path, headers, field, table, first_values, second_values, evidence
):
    from app.main import app

    acquired, release = Event(), Event()

    def observe(connection, cursor, statement, parameters, context, executemany):
        if (
            connection.info.get("audit_actor") == "first"
            and statement.lstrip().upper().startswith("DELETE")
            and table in statement
            and not acquired.is_set()
        ):
            acquired.set()
            if not release.wait(timeout=12):
                raise RuntimeError("Test release timeout")

    def change(actor, values):
        with TestClient(app, raise_server_exceptions=False) as client:
            return client.patch(
                path, headers={**headers, "X-Audit-Actor": actor}, json={field: values}
            )

    event.listen(engine, "after_cursor_execute", observe)
    waits = []
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(change, "first", first_values)
            try:
                assert acquired.wait(timeout=6), "First DELETE was not reached"
                second = pool.submit(change, "second", second_values)
                deadline = time.monotonic() + 6
                while time.monotonic() < deadline:
                    with engine.connect() as connection:
                        waits = [
                            dict(row)
                            for row in connection.execute(
                                text(
                                    "SELECT pid,wait_event_type,wait_event,query,pg_blocking_pids(pid) AS blockers FROM pg_stat_activity WHERE datname=current_database() AND application_name='slot-audit-second' AND wait_event_type='Lock'"
                                )
                            ).mappings()
                        ]
                    if waits and waits[0]["blockers"]:
                        break
                    time.sleep(0.02)
                assert waits and waits[0]["blockers"], (
                    "Second DELETE did not actually wait in PostgreSQL"
                )
            finally:
                release.set()
            results = [first.result(timeout=15), second.result(timeout=15)]
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", observe)
    evidence(
        "replacement-schedule",
        {
            "path": path,
            "field": field,
            "first_values": first_values,
            "second_values": second_values,
            "waits": waits,
            "responses": [{"status": r.status_code, "body": r.text} for r in results],
        },
    )
    return results


@pytest.mark.parametrize("target", ["candidate-skills", "job-skills"])
def test_concurrent_whole_list_replacements_cannot_merge_into_a_third_value(
    client, account, job, engine, snapshot, evidence, target
):
    owner, candidate = account(), account("candidate")
    posting = job(
        owner,
        required_skills=["python", "sql"]
        if target == "candidate-skills"
        else ["legacy"],
    )
    if target == "candidate-skills":
        assert (
            client.patch(
                "/candidate/profile",
                headers=candidate["headers"],
                json={"skills": ["legacy"]},
            ).status_code
            == 200
        )
        path, headers, field, table = (
            "/candidate/profile",
            candidate["headers"],
            "skills",
            "candidate_skill",
        )
    else:
        path, headers, field, table = (
            f"/employer/jobs/{posting['id']}",
            owner["headers"],
            "required_skills",
            "job_skill",
        )
    results = overlapping_replacements(
        engine, path, headers, field, table, ["python"], ["sql"], evidence
    )
    readback = client.get(
        "/candidate/profile" if target == "candidate-skills" else path, headers=headers
    )
    assert readback.status_code == 200, readback.text
    final = readback.json()[field]
    matched = client.get(
        f"/candidate/jobs/{posting['id']}", headers=candidate["headers"]
    )
    evidence(
        "replacement-result",
        {
            "target": target,
            "statuses": [r.status_code for r in results],
            "final_skills": final,
            "actual_score": matched.json().get("match_score"),
            "valid_complete_replacements": [["python"], ["sql"]],
            "state": snapshot(),
        },
    )
    assert all(r.status_code == 200 for r in results), [r.text for r in results]
    assert final in (["python"], ["sql"]), (
        "Whole-list replacement produced combined value: " + str(final)
    )


@pytest.mark.parametrize("field", ["title", "description", "required_skills"])
def test_unrepresentable_nul_text_is_validation_error_not_server_error(
    client, account, snapshot, evidence, field
):
    owner = account()
    body = {
        "title": "Normal title",
        "description": "Normal description",
        "required_skills": ["python"],
    }
    body[field] = ["py\x00thon"] if field == "required_skills" else "ordinary\x00text"
    before = snapshot()
    response = client.post("/employer/jobs", headers=owner["headers"], json=body)
    after = snapshot()
    evidence(
        "nul-result",
        {
            "field": field,
            "payload": body,
            "status": response.status_code,
            "response": response.text,
            "state_unchanged": before == after,
        },
    )
    assert after == before
    assert 400 <= response.status_code < 500, (
        "Unsupported PostgreSQL text should be a validation rejection, got "
        + str(response.status_code)
    )
