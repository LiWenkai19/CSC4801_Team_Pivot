from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import text
from conftest import FROZEN

PATH = "/employer/interview-slots"


def test_create_has_exact_duration_utc_ownership_and_persistence(
    client, account, create_slot, snapshot
):
    owner = account()
    start = FROZEN + timedelta(days=1, microseconds=123456)
    slot = create_slot(owner, start)
    assert set(slot) == {"id", "starts_at", "ends_at"}
    assert datetime.fromisoformat(slot["starts_at"]) == start
    assert datetime.fromisoformat(slot["ends_at"]) == start + timedelta(minutes=30)
    assert slot["starts_at"].endswith("Z") and slot["ends_at"].endswith("Z")
    rows = snapshot()["interview_slot"]
    assert (
        len(rows) == 1
        and rows[0]["employer_id"] == owner["id"]
        and rows[0]["job_id"] is None
    )
    assert rows[0]["id"] == slot["id"]
    assert client.get(PATH, headers=owner["headers"]).json() == [
        {**slot, "is_booked": False}
    ]


@pytest.mark.parametrize(
    "delta,expected",
    [(-1, 422), (0, 422), (1, 201)],
    ids=["one-us-before-now", "exactly-now", "one-us-after-now"],
)
def test_future_boundary_is_strict_and_rejection_is_atomic(
    client, account, snapshot, delta, expected
):
    owner = account()
    before = snapshot()
    response = client.post(
        PATH,
        headers=owner["headers"],
        json={"starts_at": (FROZEN + timedelta(microseconds=delta)).isoformat()},
    )
    assert response.status_code == expected, response.text
    if expected != 201:
        assert snapshot() == before
    else:
        assert len(snapshot()["interview_slot"]) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"starts_at": None},
        {"starts_at": True},
        {"starts_at": 1900000000},
        {"starts_at": []},
        {"starts_at": {}},
        {"starts_at": "2030-05-02"},
        {"starts_at": "2030-05-02T12:00:00"},
        {"starts_at": "2030-02-30T12:00:00Z"},
        {"starts_at": "2030-05-02T12:00:00+25:00"},
        {"starts_at": "not-a-date"},
        {"starts_at": "2030-05-02T12:00:00Z", "ends_at": "2030-05-02T13:00:00Z"},
        {"starts_at": "2030-05-02T12:00:00Z", "employer_id": str(uuid.UUID(int=9))},
        {"starts_at": "9999-12-31T23:50:00Z"},
        {"starts_at": "9999-12-31T23:00:00-08:00"},
    ],
    ids=[
        "missing",
        "null",
        "boolean",
        "number",
        "array",
        "object",
        "date-only",
        "naive",
        "bad-day",
        "bad-offset",
        "bad-string",
        "extra-end",
        "extra-owner",
        "end-overflow",
        "utc-overflow",
    ],
)
def test_invalid_create_is_422_without_any_business_write(
    client, account, snapshot, payload
):
    owner = account()
    before = snapshot()
    response = client.post(PATH, headers=owner["headers"], json=payload)
    assert response.status_code == 422, response.text
    assert snapshot() == before


@pytest.mark.parametrize(
    "value",
    [
        "2030-05-02T12:00:00Z",
        "2030-05-02T20:00:00+08:00",
        "2030-05-02T08:00:00-04:00",
        "2030-05-02T17:45:00+05:45",
    ],
)
def test_equivalent_timezone_representations_have_same_result(
    client, account, create_slot, value
):
    slot = create_slot(account(), value)
    assert slot["starts_at"] == "2030-05-02T12:00:00Z"
    assert slot["ends_at"] == "2030-05-02T12:30:00Z"


@pytest.mark.parametrize(
    "offset,expected",
    [
        (-60, 201),
        (-30, 201),
        (-29, 409),
        (-15, 409),
        (0, 409),
        (15, 409),
        (29, 409),
        (30, 201),
        (60, 201),
    ],
)
def test_overlap_matches_half_open_interval_oracle(
    client, account, create_slot, snapshot, offset, expected
):
    owner = account()
    start = FROZEN + timedelta(days=1, hours=12)
    create_slot(owner, start)
    before = snapshot()
    new_start = start + timedelta(minutes=offset)
    independently_overlaps = (
        start < new_start + timedelta(minutes=30)
        and start + timedelta(minutes=30) > new_start
    )
    assert expected == (409 if independently_overlaps else 201)
    response = client.post(
        PATH, headers=owner["headers"], json={"starts_at": new_start.isoformat()}
    )
    assert response.status_code == expected, response.text
    if expected == 409:
        assert response.json()["detail"] == "Slot overlaps an existing slot"
        assert snapshot() == before
    else:
        assert len(snapshot()["interview_slot"]) == 2


def test_distinct_employers_can_use_same_time(client, account, create_slot, snapshot):
    first, second = account(), account()
    one, two = create_slot(first), create_slot(second)
    assert one["id"] != two["id"]
    assert {x["id"] for x in client.get(PATH, headers=first["headers"]).json()} == {
        one["id"]
    }
    assert {x["id"] for x in client.get(PATH, headers=second["headers"]).json()} == {
        two["id"]
    }
    assert len(snapshot()["interview_slot"]) == 2


@pytest.mark.parametrize("method", ["GET", "POST", "DELETE"])
@pytest.mark.parametrize("identity,expected", [("anonymous", 401), ("candidate", 403)])
def test_auth_role_contract_is_enforced_without_business_mutation(
    client, account, create_slot, snapshot, method, identity, expected
):
    owner = account()
    slot = create_slot(owner)
    headers = {} if identity == "anonymous" else account("candidate")["headers"]
    before = snapshot()
    path = PATH + ("/" + slot["id"] if method == "DELETE" else "")
    response = client.request(
        method,
        path,
        headers=headers,
        json={"starts_at": "2030-05-03T12:00:00Z"} if method == "POST" else None,
    )
    assert response.status_code == expected, response.text
    assert snapshot() == before


@pytest.mark.parametrize("method", ["POST", "DELETE"])
@pytest.mark.parametrize("csrf", [None, "ordinary-wrong-token"])
def test_csrf_rejection_preserves_all_business_rows(
    client, account, create_slot, snapshot, method, csrf
):
    owner = account()
    slot = create_slot(owner)
    headers = {"Cookie": owner["headers"]["Cookie"]}
    if csrf is not None:
        headers["X-CSRF-Token"] = csrf
    before = snapshot()
    response = client.request(
        method,
        PATH + ("/" + slot["id"] if method == "DELETE" else ""),
        headers=headers,
        json={"starts_at": "2030-05-03T12:00:00Z"} if method == "POST" else None,
    )
    assert response.status_code == 403, response.text
    assert snapshot() == before


def test_create_without_employer_profile_is_404_and_atomic(client, account, snapshot):
    owner = account(complete=False)
    before = snapshot()
    response = client.post(
        PATH, headers=owner["headers"], json={"starts_at": "2030-05-02T12:00:00Z"}
    )
    assert (
        response.status_code == 404
        and response.json()["detail"] == "Employer profile not found"
    )
    assert snapshot() == before


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("other-owner", 403),
        ("missing", 404),
        ("invalid-uuid", 422),
        ("past", 409),
        ("now", 409),
    ],
)
def test_delete_rejections_are_distinct_and_atomic(
    client, account, create_slot, insert_slot, snapshot, kind, expected
):
    owner, other = account(), account()
    if kind in {"past", "now"}:
        slot_id = insert_slot(
            owner, FROZEN - timedelta(minutes=30) if kind == "past" else FROZEN
        )
    else:
        slot_id = create_slot(other if kind == "other-owner" else owner)["id"]
    if kind == "missing":
        slot_id = str(uuid.UUID(int=999))
    if kind == "invalid-uuid":
        slot_id = "ordinary-invalid-id"
    before = snapshot()
    response = client.delete(PATH + "/" + slot_id, headers=owner["headers"])
    assert response.status_code == expected, response.text
    assert snapshot() == before


def test_delete_success_removes_only_target_and_repeat_is_404(
    client, account, create_slot, snapshot
):
    owner = account()
    first = create_slot(owner)
    second = create_slot(owner, FROZEN + timedelta(days=2))
    response = client.delete(PATH + "/" + first["id"], headers=owner["headers"])
    assert response.status_code == 204 and response.content == b""
    assert [row["id"] for row in snapshot()["interview_slot"]] == [second["id"]]
    assert (
        client.delete(PATH + "/" + first["id"], headers=owner["headers"]).status_code
        == 404
    )


@pytest.mark.parametrize("start", ["9999-12-31T15:00:00Z", "9999-12-31T16:00:00Z"])
def test_accepted_representable_future_time_remains_readable(
    client, account, snapshot, evidence, start
):
    owner = account()
    response = client.post(PATH, headers=owner["headers"], json={"starts_at": start})
    assert response.status_code == 201, response.text
    listed = client.get(PATH, headers=owner["headers"])
    evidence(
        "readability",
        {
            "input": start,
            "create_status": response.status_code,
            "create_body": response.json(),
            "list_status": listed.status_code,
            "list_body": listed.text,
            "business_state": snapshot(),
        },
    )
    assert listed.status_code == 200, (
        "Accepted and persisted slot must remain listable: " + listed.text
    )
    assert listed.json() == [{**response.json(), "is_booked": False}]
