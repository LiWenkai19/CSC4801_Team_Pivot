from types import SimpleNamespace
import re
import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, select


def test_unexported_handover_token_is_urlsafe_and_new():
    from app.users.security import gen_handover_token

    first, second = gen_handover_token(), gen_handover_token()
    assert len(first) == len(second) == 11 and re.fullmatch(r"[A-Za-z0-9_-]+", first)
    assert first != second


def test_actual_database_dependency_yields_and_releases_session():
    from app.db.session import get_db, engine

    gen = get_db()
    db = next(gen)
    assert db.exec(select(1)).one() == 1
    with pytest.raises(StopIteration):
        next(gen)
    assert engine.pool.checkedout() == 0


def test_direct_candidate_policy_rejects_normal_employer(account, engine):
    from app.candidate.service import get_my_profile
    from app.users.model import User
    from app.users.service import CandidateRoleRequiredError

    actor = account("employer")
    with Session(engine) as db:
        with pytest.raises(CandidateRoleRequiredError):
            get_my_profile(db, db.get(User, uuid.UUID(actor["id"])))


def test_direct_employer_policy_rejects_normal_candidate(account, engine):
    from app.employer.service import get_my_company
    from app.users.model import User
    from app.users.service import EmployerRoleRequiredError

    actor = account("candidate")
    with Session(engine) as db:
        with pytest.raises(EmployerRoleRequiredError):
            get_my_company(db, db.get(User, uuid.UUID(actor["id"])))


def test_unsupported_role_defensive_double_denied_without_database():
    from app.candidate.service import read_profile, ForbiddenError

    # A hypothetical internal caller fault; this role cannot pass API/DB schema.
    with pytest.raises(ForbiddenError):
        read_profile(None, SimpleNamespace(role=None, id=uuid.uuid4()), uuid.uuid4())


@pytest.mark.parametrize("method", ["get", "patch"])
def test_missing_company_normal_route_is_404(client, account, snapshot, method):
    actor = account("employer", complete=False)
    before = snapshot()
    args = (
        {"json": {"version": 1, "company_name": "No existing company"}} if method == "patch" else {}
    )
    r = getattr(client, method)("/employer/company", headers=actor["headers"], **args)
    assert r.status_code == 404 and snapshot() == before


@pytest.mark.parametrize("role", ["candidate", "employer"])
def test_direct_profile_route_translates_service_role_error(engine, role):
    from app.users import router, schema
    from app.users.model import User, Role

    user = User(
        role=Role.Employer if role == "candidate" else Role.Candidate,
        email="synthetic@example.com",
        hashed_password="unused",
    )
    action = (
        router.submit_candidate_profile
        if role == "candidate"
        else router.submit_employer_profile
    )
    payload = (
        schema.CandidateProfileCreate(display_name="Normal")
        if role == "candidate"
        else schema.EmployerProfileCreate(company_name="Normal")
    )
    with Session(engine) as db:
        with pytest.raises(HTTPException) as caught:
            action(payload, session=db, curr_user=user)
    assert caught.value.status_code == 403


def test_login_value_error_translation_is_400(client, monkeypatch, snapshot):
    from app.users import router

    before = snapshot()

    def invalid(*args):
        raise ValueError("Synthetic credential validation failure")

    monkeypatch.setattr(router, "authenticate_user", invalid)
    r = client.post(
        "/users/login", json={"email": "synthetic@example.com", "password": "normal"}
    )
    assert r.status_code == 400 and snapshot() == before


def test_candidate_error_subclass_walks_mro():
    from app.candidate import router, service

    class SpecificMissing(service.NotFoundError):
        pass

    def action():
        raise SpecificMissing("Synthetic subtype")

    with pytest.raises(HTTPException) as caught:
        router.execute(action)
    assert caught.value.status_code == 404


def test_employer_error_subclass_and_unknown_error_are_distinct():
    from app.employer import router, service

    class SpecificMissing(service.JobNotFoundError):
        pass

    assert router._to_http(SpecificMissing("Known")).status_code == 404
    error = ValueError("Unmapped internal error")
    with pytest.raises(ValueError) as caught:
        router._to_http(error)
    assert caught.value is error


def test_delete_job_commit_failure_rolls_back_real_update(
    client, account, job, snapshot, monkeypatch
):
    owner = account()
    posting = job(owner)
    before = snapshot()

    def fail(db):
        db.flush()
        raise SQLAlchemyError("Synthetic commit failure after actual flush")

    monkeypatch.setattr(Session, "commit", fail)
    r = client.delete("/employer/jobs/" + posting["id"], headers=owner["headers"])
    assert r.status_code == 500 and snapshot() == before


@pytest.mark.parametrize("kind", ["duplicate", "unknown"])
def test_apply_integrity_error_classification_after_rollback(
    client, account, job, engine, monkeypatch, evidence, kind
):
    from app.employer.model import Application

    owner, candidate = account(), account("candidate")
    posting = job(owner)
    original = Session.commit

    def failure(db):
        if any(isinstance(row, Application) for row in db.new):
            if kind == "duplicate":
                db.rollback()  # Release original locks before modeling competing commit.
                with Session(engine) as competitor:
                    competitor.add(
                        Application(
                            candidate_id=uuid.UUID(candidate["id"]),
                            job_id=uuid.UUID(posting["id"]),
                        )
                    )
                    original(competitor)
            else:
                db.flush()
            raise IntegrityError(
                "Injected database rejection",
                {},
                Exception("synthetic integrity failure"),
            )
        return original(db)

    monkeypatch.setattr(Session, "commit", failure)
    r = client.post(
        "/candidate/jobs/" + posting["id"] + "/applications",
        headers=candidate["headers"],
        json={},
    )
    with engine.connect() as c:
        count = c.execute(text("SELECT count(*) FROM application")).scalar_one()
    evidence(
        "integrity-path",
        {
            "kind": kind,
            "status": r.status_code,
            "rows": count,
            "modeled_fault": "database rejection then observe actual valid competitor commit; not evidence of naturally reached schedule",
        },
    )
    assert r.status_code == (409 if kind == "duplicate" else 500)
    assert count == (1 if kind == "duplicate" else 0)


@pytest.mark.parametrize("kind", ["slot", "application", "unknown"])
def test_booking_integrity_classification_with_valid_competitor_state(
    client, flow, add_applicant, create_slot, engine, monkeypatch, evidence, kind
):
    from app.employer.model import Booking

    data = flow()
    other = add_applicant(data["owner"], data["job_id"])
    alternate = create_slot(
        data["owner"], start=datetime(2030, 5, 3, tzinfo=timezone.utc)
    )
    original = Session.commit

    def failure(db):
        if any(isinstance(row, Booking) for row in db.new):
            if kind != "unknown":
                db.rollback()
                with Session(engine) as competitor:
                    app = (
                        other["application_id"]
                        if kind == "slot"
                        else data["application_id"]
                    )
                    slot = data["slot"]["id"] if kind == "slot" else alternate["id"]
                    competitor.add(
                        Booking(application_id=uuid.UUID(app), slot_id=uuid.UUID(slot))
                    )
                    original(competitor)
            else:
                db.flush()
            raise IntegrityError(
                "Injected database rejection",
                {},
                Exception("synthetic integrity failure"),
            )
        return original(db)

    monkeypatch.setattr(Session, "commit", failure)
    r = client.post(
        "/candidate/applications/" + data["application_id"] + "/booking",
        headers=data["candidate"]["headers"],
        json={"slot_id": data["slot"]["id"]},
    )
    with engine.connect() as c:
        count = c.execute(text("SELECT count(*) FROM booking")).scalar_one()
    evidence(
        "booking-integrity-path",
        {
            "kind": kind,
            "status": r.status_code,
            "bookings": count,
            "modeled_fault": True,
        },
    )
    assert r.status_code == (500 if kind == "unknown" else 409)
    if kind != "unknown":
        assert r.json()["detail"] == (
            "Slot already booked" if kind == "slot" else "Application already booked"
        )
    assert count == (0 if kind == "unknown" else 1)


@pytest.mark.parametrize(
    "operation",
    ["available-slots", "book", "applicant-list", "booking-public", "status-update"],
)
def test_defensive_missing_related_lookup_without_corrupting_real_database(
    client, flow, engine, monkeypatch, snapshot, operation
):
    from app.candidate import service as candidate
    from app.employer import service as employer
    from app.employer.model import Booking, Job, InterviewSlot
    from app.employer.schema import ApplicationStatusUpdate
    from app.users.model import User, CandidateProfile

    data = flow()
    if operation == "booking-public":
        assert (
            client.post(
                "/candidate/applications/" + data["application_id"] + "/booking",
                headers=data["candidate"]["headers"],
                json={"slot_id": data["slot"]["id"]},
            ).status_code
            == 201
        )
    before = snapshot()
    with Session(engine) as db:
        person = db.get(User, uuid.UUID(data["candidate"]["id"]))
        owner = db.get(User, uuid.UUID(data["owner"]["id"]))
        original = db.get
        hidden = (
            CandidateProfile
            if operation == "applicant-list"
            else InterviewSlot
            if operation == "booking-public"
            else Job
        )
        monkeypatch.setattr(
            db,
            "get",
            lambda model, *args, **kw: (
                None if model is hidden else original(model, *args, **kw)
            ),
        )
        if operation == "available-slots":
            with pytest.raises(candidate.NotFoundError):
                candidate.available_slots(db, person, uuid.UUID(data["application_id"]))
        elif operation == "book":
            with pytest.raises(candidate.NotFoundError):
                candidate.book(
                    db,
                    person,
                    uuid.UUID(data["application_id"]),
                    uuid.UUID(data["slot"]["id"]),
                )
        elif operation == "applicant-list":
            assert (
                employer.list_job_applicants(db, owner, uuid.UUID(data["job_id"])) == []
            )
        elif operation == "booking-public":
            assert (
                employer._booking_public(db, uuid.UUID(data["application_id"])) is None
            )
        else:
            with pytest.raises(employer.JobNotFoundError):
                employer.change_application_status(
                    db,
                    owner,
                    uuid.UUID(data["application_id"]),
                    ApplicationStatusUpdate(version=data["version"], status="Accepted"),
                )
    assert snapshot() == before
