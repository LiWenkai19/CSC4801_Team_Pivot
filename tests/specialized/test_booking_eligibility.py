from conftest import expected_slots_with_booking_jobs
from datetime import timedelta
from itertools import product
import uuid

import pytest
from sqlalchemy import text
from conftest import FROZEN


def persist_booking(engine, application_id, slot_id):
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO booking(id,application_id,slot_id,created_at) VALUES(:id,:application,:slot,:time)"
            ),
            {
                "id": uuid.uuid4(),
                "application": uuid.UUID(application_id),
                "slot": uuid.UUID(slot_id),
                "time": FROZEN - timedelta(days=2),
            },
        )


FLAGS = list(product((True, False), repeat=6))


@pytest.mark.parametrize(
    "owns,same_employer,interviewing,future,slot_free,application_free",
    FLAGS,
    ids=["b" + "".join("1" if x else "0" for x in row) for row in FLAGS],
)
def test_full_booking_eligibility_decision_table(
    client,
    account,
    flow,
    add_applicant,
    insert_slot,
    engine,
    snapshot,
    evidence,
    owns,
    same_employer,
    interviewing,
    future,
    slot_free,
    application_free,
):
    data = flow(with_slot=False)
    requester = data["candidate"] if owns else account("candidate")
    slot_owner = data["owner"] if same_employer else account()
    start = FROZEN + timedelta(days=1) if future else FROZEN - timedelta(hours=1)
    slot_id = insert_slot(slot_owner, start)
    if not slot_free:
        auxiliary = (
            add_applicant(data["owner"], data["job_id"])
            if same_employer
            else flow(owner=slot_owner, with_slot=False)
        )
        persist_booking(engine, auxiliary["application_id"], slot_id)
    if not application_free:
        existing_slot = insert_slot(data["owner"], FROZEN + timedelta(days=2))
        persist_booking(engine, data["application_id"], existing_slot)
    if not interviewing:
        changed = client.patch(
            f"/employer/applications/{data['application_id']}/status",
            headers=data["owner"]["headers"],
            json={"version": 2, "status": "Pending"},
        )
        assert changed.status_code == 200 and changed.json()["status"] == "Pending"
    before = snapshot()
    if owns and interviewing and application_free:
        available = client.get(
            f"/candidate/applications/{data['application_id']}/slots",
            headers=requester["headers"],
        )
        assert available.status_code == 200, available.text
        assert [row["id"] for row in available.json()] == (
            [slot_id] if same_employer and future and slot_free else []
        )
        assert snapshot() == before
    response = client.post(
        f"/candidate/applications/{data['application_id']}/booking",
        headers=requester["headers"],
        json={"slot_id": slot_id},
    )
    after = snapshot()
    flags = {
        "owns": owns,
        "same_employer": same_employer,
        "interviewing": interviewing,
        "future": future,
        "slot_free": slot_free,
        "application_free": application_free,
    }
    accepted = all(flags.values())
    evidence(
        "decision",
        {
            "conditions": flags,
            "independent_expected_acceptance": accepted,
            "http_status": response.status_code,
            "response": response.text,
            "business_unchanged": before == after,
            "booking_count_before": len(before["booking"]),
            "booking_count_after": len(after["booking"]),
        },
    )
    if accepted:
        assert response.status_code == 201, response.text
        assert len(after["booking"]) == 1
        assert (
            after["booking"][0]["application_id"] == data["application_id"]
            and after["booking"][0]["slot_id"] == slot_id
        )
        assert (
            after["application"] == before["application"]
            and after["interview_slot"] == expected_slots_with_booking_jobs(before, after["booking"])
        )
        ours = client.get(
            f"/candidate/applications/{data['application_id']}",
            headers=data["candidate"]["headers"],
        ).json()["booking"]
        theirs = client.get(
            f"/employer/jobs/{data['job_id']}/applications",
            headers=data["owner"]["headers"],
        ).json()[0]["booking"]
        assert (
            ours["booking_id"] == theirs["booking_id"] == response.json()["booking_id"]
        )
    else:
        assert response.status_code in (403, 409), response.text
        if not owns:
            assert response.status_code == 403
        if sum(not value for value in flags.values()) == 1:
            assert response.status_code == (
                403 if not same_employer or not owns else 409
            )
        assert after == before


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("missing", 422),
        ("null", 422),
        ("bad-uuid", 422),
        ("numeric", 422),
        ("extra-owner", 422),
        ("extra-status", 422),
        ("missing-slot", 404),
        ("invalid-app-id", 422),
        ("missing-app", 404),
    ],
)
def test_booking_request_errors_have_no_partial_effects(
    client, flow, snapshot, kind, expected
):
    data = flow()
    path = f"/candidate/applications/{data['application_id']}/booking"
    payload = {"slot_id": data["slot"]["id"]}
    if kind == "missing":
        payload = {}
    if kind == "null":
        payload = {"slot_id": None}
    if kind == "bad-uuid":
        payload = {"slot_id": "ordinary-invalid-uuid"}
    if kind == "numeric":
        payload = {"slot_id": 7}
    if kind == "extra-owner":
        payload["candidate_id"] = data["candidate"]["id"]
    if kind == "extra-status":
        payload["status"] = "Accepted"
    if kind == "missing-slot":
        payload["slot_id"] = str(uuid.UUID(int=99999))
    if kind == "invalid-app-id":
        path = "/candidate/applications/ordinary-invalid-id/booking"
    if kind == "missing-app":
        path = f"/candidate/applications/{uuid.UUID(int=88888)}/booking"
    before = snapshot()
    result = client.post(path, headers=data["candidate"]["headers"], json=payload)
    assert result.status_code == expected, result.text
    assert snapshot() == before
