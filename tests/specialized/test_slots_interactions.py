from datetime import timedelta
import uuid

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from conftest import FROZEN

PATH = "/employer/interview-slots"


def book(client, data, slot_id=None):
    return client.post(
        f"/candidate/applications/{data['application_id']}/booking",
        headers=data["candidate"]["headers"],
        json={"slot_id": slot_id or data["slot"]["id"]},
    )


def test_listing_reference_filters_owner_clock_duration_booking_and_id_order(
    client, account, flow, insert_slot, snapshot
):
    data = flow(with_slot=False)
    owner, other = data["owner"], account()
    start = FROZEN + timedelta(days=1)
    booked = insert_slot(owner, start - timedelta(hours=1))
    response = book(client, data, booked)
    assert response.status_code == 201, response.text
    expected_ids = [
        str(uuid.UUID(int=101)),
        str(uuid.UUID(int=102)),
        str(uuid.UUID(int=103)),
    ]
    insert_slot(owner, start, identifier=expected_ids[1])
    insert_slot(owner, start, identifier=expected_ids[0])
    insert_slot(owner, start + timedelta(hours=1), identifier=expected_ids[2])
    for minutes in (29, 31, 60):
        insert_slot(owner, start + timedelta(hours=2), minutes=minutes)
    insert_slot(owner, FROZEN - timedelta(hours=1))
    insert_slot(owner, FROZEN)
    insert_slot(other, start)
    before = snapshot()
    response = client.get(PATH, headers=owner["headers"])
    assert response.status_code == 200, response.text
    expected_ids = [
        row["id"]
        for row in sorted(
            before["interview_slot"], key=lambda row: (row["starts_at"], row["id"])
        )
        if row["employer_id"] == owner["id"]
        and __import__("datetime").datetime.fromisoformat(row["starts_at"]) > FROZEN
    ]
    assert [row["id"] for row in response.json()] == expected_ids
    assert {row["id"] for row in response.json() if row["is_booked"]} == {booked}
    assert snapshot() == before


def test_unbooked_employer_shared_slot_is_visible_to_multiple_owned_jobs(client, flow):
    first = flow()
    second = flow(owner=first["owner"], with_slot=False)
    for data in (first, second):
        response = client.get(
            f"/candidate/applications/{data['application_id']}/slots",
            headers=data["candidate"]["headers"],
        )
        assert response.status_code == 200, response.text
        assert response.json() == [first["slot"]]


def test_booking_removes_availability_and_blocks_delete_with_full_snapshot(
    client, flow, snapshot
):
    data = flow()
    result = book(client, data)
    assert result.status_code == 201, result.text
    owner = data["owner"]
    before = snapshot()
    assert client.get(PATH, headers=owner["headers"]).json() == [
        {**data["slot"], "is_booked": True}
    ]
    another = client.delete(PATH + "/" + data["slot"]["id"], headers=owner["headers"])
    assert (
        another.status_code == 409 and another.json()["detail"] == "Slot already booked"
    )
    assert snapshot() == before
    ours = client.get(
        f"/candidate/applications/{data['application_id']}",
        headers=data["candidate"]["headers"],
    ).json()["booking"]
    rows = client.get(
        f"/employer/jobs/{data['job_id']}/applications", headers=owner["headers"]
    ).json()
    assert (
        ours["booking_id"]
        == result.json()["booking_id"]
        == rows[0]["booking"]["booking_id"]
    )
    assert ours["slot_id"] == data["slot"]["id"]


def test_already_booked_slot_still_blocks_overlapping_create(client, flow, snapshot):
    data = flow()
    assert book(client, data).status_code == 201
    before = snapshot()
    response = client.post(
        PATH,
        headers=data["owner"]["headers"],
        json={"starts_at": "2030-05-02T00:15:00Z"},
    )
    assert response.status_code == 409, response.text
    assert snapshot() == before


def test_all_four_verified_status_changes_preserve_booking_and_unavailability(
    client, flow, snapshot
):
    data = flow()
    booked = book(client, data)
    assert booked.status_code == 201, booked.text
    fixed = snapshot()
    for version, status in enumerate(("Pending", "Rejected", "Accepted", "Interviewing"), start=data["version"]):
        changed = client.patch(
            f"/employer/applications/{data['application_id']}/status",
            headers=data["owner"]["headers"],
            json={"version": version, "status": status},
        )
        assert changed.status_code == 200 and changed.json()["status"] == status, (
            changed.text
        )
        current = client.get(
            f"/candidate/applications/{data['application_id']}",
            headers=data["candidate"]["headers"],
        )
        assert current.status_code == 200 and current.json()["status"] == status
        assert current.json()["booking"] == booked.json()
        state = snapshot()
        assert state["application"][0]["status"] == status
        assert (
            state["booking"] == fixed["booking"]
            and state["interview_slot"] == fixed["interview_slot"]
        )
        assert client.get(PATH, headers=data["owner"]["headers"]).json() == [
            {**data["slot"], "is_booked": True}
        ]
        deletion = client.delete(
            PATH + "/" + data["slot"]["id"], headers=data["owner"]["headers"]
        )
        assert deletion.status_code == 409
        assert snapshot() == state


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("Pending", 409),
        ("Rejected", 409),
        ("Accepted", 409),
        ("foreign-employer", 403),
        ("foreign-application", 403),
        ("past", 409),
        ("now", 409),
        ("29-min", 409),
        ("31-min", 409),
        ("60-min", 409),
        ("missing", 404),
    ],
)
def test_each_ineligible_booking_preserves_complete_related_state(
    client, account, flow, insert_slot, snapshot, kind, expected
):
    data = flow(with_slot=False)
    start, duration = FROZEN + timedelta(days=1), 30
    slot_owner = data["owner"]
    if kind == "foreign-employer":
        slot_owner = account()
    if kind == "past":
        start = FROZEN - timedelta(days=1)
    if kind == "now":
        start = FROZEN
    if kind.endswith("-min"):
        duration = int(kind.split("-")[0])
    slot_id = insert_slot(slot_owner, start, minutes=duration)
    if kind in {"Pending", "Rejected", "Accepted"}:
        response = client.patch(
            f"/employer/applications/{data['application_id']}/status",
            headers=data["owner"]["headers"],
            json={"version": 2, "status": kind},
        )
        assert response.status_code == 200 and response.json()["status"] == kind
    if kind == "foreign-application":
        data = {**data, "candidate": account("candidate")}
    if kind == "missing":
        slot_id = str(uuid.UUID(int=9999))
    before = snapshot()
    rejected = book(client, data, slot_id)
    assert rejected.status_code == expected, rejected.text
    assert snapshot() == before


def test_existing_booking_rejection_preserves_second_slot_and_original_link(
    client, flow, create_slot, snapshot
):
    data = flow()
    assert book(client, data).status_code == 201
    second = create_slot(data["owner"], FROZEN + timedelta(days=2))
    before = snapshot()
    result = book(client, data, second["id"])
    assert (
        result.status_code == 409
        and result.json()["detail"] == "Application already booked"
    )
    assert snapshot() == before


@pytest.mark.parametrize("operation", ["create", "delete"])
def test_flush_then_commit_failure_rolls_back_real_database_effects(
    engine, account, create_slot, snapshot, monkeypatch, operation
):
    from app.interview import service
    from app.interview.schema import SlotCreate
    from app.users.model import User

    owner = account()
    slot = create_slot(owner) if operation == "delete" else None
    before = snapshot()
    with Session(engine) as session:
        user = session.get(User, uuid.UUID(owner["id"]))

        def failing_commit():
            session.flush()
            raise SQLAlchemyError("Synthetic commit failure after a real flush")

        monkeypatch.setattr(session, "commit", failing_commit)
        with pytest.raises(SQLAlchemyError, match="Synthetic commit failure"):
            if operation == "create":
                service.create_slot(
                    session, user, SlotCreate(starts_at="2030-05-02T00:00:00Z")
                )
            else:
                service.delete_slot(session, user, uuid.UUID(slot["id"]))
    assert snapshot() == before
