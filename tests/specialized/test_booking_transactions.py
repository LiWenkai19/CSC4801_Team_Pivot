import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session
from conftest import FROZEN


@pytest.mark.parametrize("operation", ["booking", "status-update", "application"])
def test_flush_then_failed_commit_restores_all_related_records(
    client, account, flow, engine, snapshot, monkeypatch, operation
):
    from app.candidate import service as candidate
    from app.employer import service as employer
    from app.employer.schema import ApplicationStatusUpdate
    from app.users.model import User

    data = flow()
    actor = data["candidate"] if operation == "booking" else data["owner"]
    if operation == "application":
        actor = account("candidate")
    before = snapshot()
    with Session(engine) as session:
        user = session.get(User, uuid.UUID(actor["id"]))

        def failed_commit():
            session.flush()
            raise SQLAlchemyError("Synthetic commit failure after real flush")

        monkeypatch.setattr(session, "commit", failed_commit)
        with pytest.raises(SQLAlchemyError, match="Synthetic commit failure"):
            if operation == "booking":
                candidate.book(
                    session,
                    user,
                    uuid.UUID(data["application_id"]),
                    uuid.UUID(data["slot"]["id"]),
                )
            elif operation == "status-update":
                employer.change_application_status(
                    session,
                    user,
                    uuid.UUID(data["application_id"]),
                    ApplicationStatusUpdate(version=data["version"], status="Accepted"),
                )
            else:
                candidate.apply(session, user, uuid.UUID(data["job_id"]))
    assert snapshot() == before


def test_unrelated_integrity_error_is_not_misreported_as_already_booked(
    client, flow, engine, snapshot, monkeypatch
):
    from app.candidate import service
    from app.users.model import User

    data = flow()
    before = snapshot()
    with Session(engine) as session:
        user = session.get(User, uuid.UUID(data["candidate"]["id"]))

        def unrelated_failure():
            session.flush()
            raise IntegrityError(
                "synthetic ordinary write",
                None,
                Exception("Synthetic unrelated storage constraint"),
            )

        monkeypatch.setattr(session, "commit", unrelated_failure)
        with pytest.raises(IntegrityError):
            service.book(
                session,
                user,
                uuid.UUID(data["application_id"]),
                uuid.UUID(data["slot"]["id"]),
            )
    assert snapshot() == before


@pytest.mark.parametrize(
    "constraint", ["slot-unique", "application-unique", "booked-slot-foreign-key"]
)
def test_real_database_booking_constraints_remain_effective(
    client, flow, add_applicant, create_slot, engine, snapshot, evidence, constraint
):
    from datetime import timedelta

    data = flow()
    booked = client.post(
        f"/candidate/applications/{data['application_id']}/booking",
        headers=data["candidate"]["headers"],
        json={"slot_id": data["slot"]["id"]},
    )
    assert booked.status_code == 201, booked.text
    application_id, slot_id = data["application_id"], data["slot"]["id"]
    if constraint == "slot-unique":
        application_id = add_applicant(data["owner"], data["job_id"])["application_id"]
    if constraint == "application-unique":
        slot_id = create_slot(data["owner"], FROZEN + timedelta(days=2))["id"]
    before = snapshot()
    with pytest.raises(IntegrityError) as caught:
        with engine.begin() as connection:
            if constraint == "booked-slot-foreign-key":
                connection.execute(
                    text("DELETE FROM interview_slot WHERE id=:id"),
                    {"id": uuid.UUID(slot_id)},
                )
            else:
                connection.execute(
                    text(
                        "INSERT INTO booking(id,application_id,slot_id,created_at) VALUES(:id,:app,:slot,:time)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "app": uuid.UUID(application_id),
                        "slot": uuid.UUID(slot_id),
                        "time": FROZEN,
                    },
                )
    code = caught.value.orig.sqlstate
    expected = "23503" if constraint == "booked-slot-foreign-key" else "23505"
    assert code == expected
    assert snapshot() == before
    evidence(
        "constraint",
        {
            "check": constraint,
            "sqlstate": code,
            "constraint_name": caught.value.orig.diag.constraint_name,
            "state_unchanged": True,
        },
    )
