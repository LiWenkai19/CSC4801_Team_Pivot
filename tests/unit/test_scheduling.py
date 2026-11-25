"""FP-SCHED-1/2/3：真实服务规则、错误映射及受控提交失败。"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.candidate import router as candidate_router, service as candidate
from app.employer.model import Application, ApplicationStatus, InterviewSlot, Job
from app.interview import router, service
from app.interview.schema import SlotCreate
from app.users.model import EmployerProfile

NOW = datetime(2030, 5, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def clock(monkeypatch):
    monkeypatch.setattr(service, "utc_now", lambda: NOW)
    monkeypatch.setattr(candidate, "utc_now", lambda: NOW)


def test_fp_sched_1_slot_creation_timezones_and_deletion(db, actors, result):
    owner = actors[1]
    db.get.return_value = EmployerProfile(user_id=owner.id, company_name="Company")
    payload = SlotCreate(starts_at="2030-05-02T09:00:00+08:00")
    saved = service.create_slot(db, owner, payload)
    assert saved.starts_at == datetime(2030, 5, 2, 1, tzinfo=timezone.utc)
    assert saved.ends_at - saved.starts_at == timedelta(minutes=30)
    slot = db.add.call_args.args[0]
    assert slot.employer_id == owner.id
    db.get.assert_called_once_with(EmployerProfile, owner.id, with_for_update=True)
    db.reset_mock()
    db.exec.side_effect = [result(first=slot), result()]
    service.delete_slot(db, owner, slot.id)
    db.delete.assert_called_once_with(slot)
    db.commit.assert_called_once()


@pytest.mark.parametrize(
    "payload",
    [
        {"starts_at": "2030-05-02T01:00:00"},
        {"starts_at": "not-a-time"},
        {"starts_at": 0},
        {"starts_at": "2030-05-02T01:00:00Z", "ends_at": "2030-05-01T01:00:00Z"},
    ],
)
def test_fp_sched_1_invalid_slots(payload):
    with pytest.raises(ValidationError):
        SlotCreate(**payload)


@pytest.mark.parametrize(
    "start", ["2030-04-30T23:59:59Z", "2030-05-01T00:00:00Z", "9999-12-31T23:59:59Z"]
)
def test_fp_sched_1_time_boundary_rejected_before_write(db, actors, start):
    db.get.return_value = EmployerProfile(user_id=actors[1].id, company_name="Company")
    with pytest.raises(service.InvalidSlotError):
        service.create_slot(db, actors[1], SlotCreate(starts_at=start))
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_fp_sched_1_overlap_is_conflict(db, actors, result):
    db.get.return_value = EmployerProfile(user_id=actors[1].id, company_name="Company")
    db.exec.return_value = result(first=uuid4())
    with pytest.raises(service.ConflictError, match="overlaps"):
        service.create_slot(db, actors[1], SlotCreate(starts_at="2030-05-02T01:00:00Z"))
    db.add.assert_not_called()
    db.rollback.assert_called_once()


@pytest.mark.parametrize(
    "case,error",
    [
        ("missing", service.NotFoundError),
        ("foreign", service.ForbiddenError),
        ("booked", service.ConflictError),
        ("started", service.ConflictError),
    ],
)
def test_fp_sched_1_delete_rejects_invalid_state(db, actors, result, case, error):
    slot = InterviewSlot(
        employer_id=uuid4() if case == "foreign" else actors[1].id,
        starts_at=NOW if case == "started" else NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=1, minutes=30),
    )
    db.exec.side_effect = [
        result(first=None if case == "missing" else slot),
        result(first=uuid4() if case == "booked" else None),
    ]
    with pytest.raises(error):
        service.delete_slot(db, actors[1], slot.id)
    db.delete.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_fp_sched_1_management_list_preserves_booking_flag(db, actors, result):
    slot = InterviewSlot(
        employer_id=actors[1].id,
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=1, minutes=30),
    )
    unbooked_slot = InterviewSlot(
        employer_id=actors[1].id,
        starts_at=slot.ends_at,
        ends_at=slot.ends_at + timedelta(minutes=30),
    )
    job_id, application_id = uuid4(), uuid4()
    db.exec.return_value = result(
        rows=[
            (slot, uuid4(), application_id, job_id, "Backend Engineer", "Candidate"),
            (unbooked_slot, None, None, None, None, None),
        ]
    )
    rows = service.list_slots(db, actors[1])
    booked, available = rows
    assert booked.id == slot.id and booked.is_booked
    assert booked.job_id == job_id and booked.job_title == "Backend Engineer"
    assert booked.application_id == application_id and booked.applicant_name == "Candidate"
    assert available.id == unbooked_slot.id and not available.is_booked
    assert available.job_id is None and available.application_id is None
    query = db.exec.call_args.args[0].compile()
    assert actors[1].id in query.params.values() and NOW in query.params.values()
    assert "LEFT OUTER JOIN booking" in str(query)
    assert "interview_slot.employer_id" in str(query)


def prepare_booking(db, actors, result, case="valid"):
    row = Application(
        candidate_id=uuid4() if case == "foreign-application" else actors[0].id,
        job_id=uuid4(),
        status=ApplicationStatus.Pending
        if case == "pending"
        else ApplicationStatus.Interviewing,
    )
    slot = InterviewSlot(
        employer_id=uuid4() if case == "foreign-slot" else actors[1].id,
        starts_at=NOW if case == "past" else NOW + timedelta(days=1),
        ends_at=(NOW if case == "past" else NOW + timedelta(days=1))
        + timedelta(minutes=60 if case == "duration" else 30),
    )
    db.get.return_value = Job(
        id=row.job_id, employer_id=actors[1].id, title="Job", description="Description"
    )
    db.exec.side_effect = [
        result(first=row),
        result(first=uuid4() if case == "application-booked" else None),
        result(first=None if case == "missing-slot" else slot),
        result(first=uuid4() if case == "slot-booked" else None),
    ]
    return row, slot


def test_fp_sched_2_eligible_booking(db, actors, result):
    row, slot = prepare_booking(db, actors, result)
    saved = candidate.book(db, actors[0], row.id, slot.id)
    booking = db.add.call_args.args[0]
    assert booking.application_id == row.id and booking.slot_id == slot.id
    assert saved.slot_id == slot.id and saved.starts_at == slot.starts_at
    db.commit.assert_called_once()


def test_fp_sched_2_available_list_filters_owner_time_length_and_booking(
    db, actors, result
):
    row = Application(
        candidate_id=actors[0].id, job_id=uuid4(), status=ApplicationStatus.Interviewing
    )
    slot = InterviewSlot(
        employer_id=actors[1].id,
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=1, minutes=30),
    )
    db.get.return_value = Job(
        id=row.job_id, employer_id=actors[1].id, title="Job", description="Details"
    )
    db.exec.side_effect = [result(first=row), result(), result(rows=[slot])]
    rows = candidate.available_slots(db, actors[0], row.id)
    assert [r.id for r in rows] == [slot.id]
    query = db.exec.call_args.args[0].compile()
    assert actors[1].id in query.params.values() and NOW in query.params.values()
    assert timedelta(minutes=30) in query.params.values()
    assert "NOT IN" in str(query) and "booking.slot_id" in str(query)
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "case,error",
    [
        ("foreign-application", candidate.ForbiddenError),
        ("pending", candidate.ConflictError),
        ("application-booked", candidate.ConflictError),
        ("missing-slot", candidate.NotFoundError),
        ("foreign-slot", candidate.ForbiddenError),
        ("past", candidate.ConflictError),
        ("duration", candidate.ConflictError),
        ("slot-booked", candidate.ConflictError),
    ],
)
def test_fp_sched_2_ineligible_booking(db, actors, result, case, error):
    row, slot = prepare_booking(db, actors, result, case)
    before = (row.status, slot.starts_at, slot.ends_at)
    with pytest.raises(error):
        candidate.book(db, actors[0], row.id, slot.id)
    assert before == (row.status, slot.starts_at, slot.ends_at)
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@pytest.mark.parametrize("kind", ["slot", "application", "unknown"])
def test_fp_sched_3_conflict_contract(db, actors, result, kind):
    row, slot = prepare_booking(db, actors, result)
    error = IntegrityError(
        "INSERT booking", {}, Exception("synthetic constraint failure")
    )
    db.commit.side_effect = error
    db.exec.side_effect = [
        result(first=row),
        result(),
        result(first=slot),
        result(),
        result(first=uuid4() if kind == "slot" else None),
        result(first=uuid4() if kind == "application" else None),
    ]
    if kind == "unknown":
        with pytest.raises(IntegrityError) as caught:
            candidate.book(db, actors[0], row.id, slot.id)
        assert caught.value is error
    else:
        expected = (
            "Slot already booked" if kind == "slot" else "Application already booked"
        )
        with pytest.raises(HTTPException) as caught:
            candidate_router.execute(candidate.book, db, actors[0], row.id, slot.id)
        assert caught.value.status_code == 409 and caught.value.detail == expected
    db.rollback.assert_called_once()


def test_fp_sched_2_commit_failure_rolls_back(db, actors, result):
    row, slot = prepare_booking(db, actors, result)
    db.commit.side_effect = SQLAlchemyError("synthetic failure")
    with pytest.raises(SQLAlchemyError):
        candidate.book(db, actors[0], row.id, slot.id)
    db.rollback.assert_called_once()


@pytest.mark.parametrize(
    "error,status",
    [
        (service.InvalidSlotError, 422),
        (service.NotFoundError, 404),
        (service.ForbiddenError, 403),
        (service.ConflictError, 409),
    ],
)
def test_fp_sched_1_route_error_contract(db, actors, monkeypatch, error, status):
    def fail(*args):
        raise error("Synthetic refusal")

    monkeypatch.setattr(service, "create_slot", fail)
    with pytest.raises(HTTPException) as caught:
        router.create_slot(SlotCreate(starts_at="2030-05-02T01:00:00Z"), db, actors[1])
    assert caught.value.status_code == status
