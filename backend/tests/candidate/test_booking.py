"""FP-SCHED-2/3：真实数据库事务、状态一致性与并发竞争。"""

import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.employer.model import Booking, InterviewSlot
from app.users.model import utc_now


def test_booking_visible_to_both_roles_and_survives_status_change(client, interview):
    data = interview
    application_id = data["application"]["application_id"]
    path = f"/candidate/applications/{application_id}"
    slots = client.get(path + "/slots", headers=data["candidate"])
    assert slots.status_code == 200 and slots.json()[0]["id"] == str(data["slot"].id)
    booked = client.post(
        path + "/booking",
        headers=data["candidate"],
        json={"slot_id": str(data["slot"].id)},
    )
    assert booked.status_code == 201
    assert booked.json()["starts_at"].endswith("Z")
    ours = client.get(path, headers=data["candidate"]).json()["booking"]
    theirs = client.get(
        f"/employer/jobs/{data['job']['id']}/applications", headers=data["employer"]
    ).json()[0]["booking"]
    assert ours == booked.json()
    assert ours["booking_id"] == theirs["booking_id"]
    assert ours["slot_id"] == theirs["slot_id"]
    assert datetime.fromisoformat(ours["starts_at"]) == datetime.fromisoformat(
        theirs["starts_at"]
    )
    assert datetime.fromisoformat(ours["ends_at"]) == datetime.fromisoformat(
        theirs["ends_at"]
    )
    client.patch(
        f"/employer/applications/{application_id}/status",
        headers=data["employer"],
        json={"status": "Accepted"},
    )
    assert (
        client.get(path, headers=data["candidate"]).json()["booking"] == booked.json()
    )
    again = client.post(
        path + "/booking",
        headers=data["candidate"],
        json={"slot_id": str(data["slot"].id)},
    )
    assert again.status_code == 409


@pytest.mark.parametrize(
    "kind,expected",
    [("past", 409), ("duration", 409), ("foreign", 403), ("missing", 404)],
)
def test_booking_invalid_slot_rolls_back(
    client, interview, account, db, kind, expected
):
    data = interview
    slot = data["slot"]
    if kind == "past":
        slot.starts_at = utc_now() - timedelta(days=1)
        slot.ends_at = slot.starts_at + timedelta(minutes=30)
    elif kind == "duration":
        slot.ends_at = slot.starts_at + timedelta(minutes=45)
    elif kind == "foreign":
        _, slot.employer_id = account("employer")
    db.add(slot)
    db.commit()
    slot_id = str(uuid.uuid4()) if kind == "missing" else str(slot.id)
    path = f"/candidate/applications/{data['application']['application_id']}"
    response = client.post(
        path + "/booking", headers=data["candidate"], json={"slot_id": slot_id}
    )
    assert response.status_code == expected
    assert db.exec(select(Booking)).all() == []
    if kind != "missing":
        assert client.get(path + "/slots", headers=data["candidate"]).json() == []


def test_booking_rejects_foreign_application_and_non_interviewing(
    client, interview, account
):
    data = interview
    other, _ = account()
    path = f"/candidate/applications/{data['application']['application_id']}"
    payload = {"slot_id": str(data["slot"].id)}
    for suffix in ["/slots", "/booking"]:
        response = (
            client.get(path + suffix, headers=other)
            if suffix == "/slots"
            else client.post(path + suffix, headers=other, json=payload)
        )
        assert response.status_code == 403
    assert (
        client.post(
            path + "/booking",
            headers=data["candidate"],
            json=payload | {"candidate_id": str(uuid.uuid4())},
        ).status_code
        == 422
    )
    for state in ["Pending", "Rejected", "Accepted"]:
        client.patch(
            f"/employer/applications/{data['application']['application_id']}/status",
            headers=data["employer"],
            json={"status": state},
        )
        assert client.get(path + "/slots", headers=data["candidate"]).status_code == 409
        assert (
            client.post(
                path + "/booking", headers=data["candidate"], json=payload
            ).status_code
            == 409
        )


def test_real_postgres_two_candidates_compete_for_one_slot(
    client, interview, account, engine
):
    data = interview
    second, _ = account()
    applied = client.post(
        f"/candidate/jobs/{data['job']['id']}/applications", headers=second
    ).json()
    client.patch(
        f"/employer/applications/{applied['application_id']}/status",
        headers=data["employer"],
        json={"status": "Interviewing"},
    )
    barrier = Barrier(2)
    from app.main import app

    def reserve(headers, application_id):
        with TestClient(app) as local_client:
            barrier.wait(timeout=10)
            return local_client.post(
                f"/candidate/applications/{application_id}/booking",
                headers=headers,
                json={"slot_id": str(data["slot"].id)},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(
            reserve, data["candidate"], data["application"]["application_id"]
        )
        other = pool.submit(reserve, second, applied["application_id"])
        results = [first.result(timeout=20), other.result(timeout=20)]
    assert sorted(response.status_code for response in results) == [201, 409]
    assert (
        next(response for response in results if response.status_code == 409).json()[
            "detail"
        ]
        == "Slot already booked"
    )
    with Session(engine) as session:
        assert len(session.exec(select(Booking)).all()) == 1
    loser = data["candidate"] if results[0].status_code == 409 else second
    loser_id = (
        data["application"]["application_id"]
        if results[0].status_code == 409
        else applied["application_id"]
    )
    assert (
        client.get(f"/candidate/applications/{loser_id}/slots", headers=loser).json()
        == []
    )


def test_same_application_concurrent_booking_has_one_winner(
    client, interview, db, engine
):
    data = interview
    start = utc_now() + timedelta(days=2)
    slot = InterviewSlot(
        employer_id=data["employer_id"],
        starts_at=start,
        ends_at=start + timedelta(minutes=30),
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    barrier = Barrier(2)
    from app.main import app

    def reserve(slot_id):
        with TestClient(app) as local_client:
            barrier.wait(timeout=10)
            return local_client.post(
                f"/candidate/applications/{data['application']['application_id']}/booking",
                headers=data["candidate"],
                json={"slot_id": str(slot_id)},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(reserve, slot_id) for slot_id in [slot.id, data["slot"].id]
        ]
        results = [future.result(timeout=20) for future in futures]
    assert sorted(row.status_code for row in results) == [201, 409]
    with Session(engine) as session:
        assert len(session.exec(select(Booking)).all()) == 1
