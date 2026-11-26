"""Blind-generated tests for Contract F2: ``app.candidate.service.book``.

Partition map (FP-SCHED-2 / FP-SCHED-3, contract section 2)
===========================================================
Eligibility checks, in the contract's normative order:

  valid / success partitions
    P1  eligible: candidate owns an Interviewing application, job and slot
        exist, employers match, slot unused, future, exactly 30 minutes,
        slot.job_id is None                      -> booking created
    P2  same as P1 but slot.job_id already equals application.job_id
        (check 11 allows "None or equal")        -> booking created

  invalid partitions (each test has exactly one failing condition unless the
  test name says it checks precedence)
    P3  application missing                      -> NotFoundError
    P4  application owned by another candidate   -> ForbiddenError
    P5  application status Pending               -> ConflictError
    P6  application status Rejected              -> ConflictError
    P7  application status Accepted              -> ConflictError
    P8  application already has a Booking        -> ConflictError("Application already booked")
    P9  slot missing                             -> NotFoundError("Slot not found")
    P10 job missing                              -> NotFoundError("Job not found")
    P11 slot.employer_id != job.employer_id      -> ForbiddenError("Slot belongs to another employer")
    P12 slot starts in the past                  -> ConflictError("Slot is in the past")
    P13 slot lasts 29 minutes                    -> ConflictError("Slot must last 30 minutes")
    P14 slot lasts 31 minutes                    -> ConflictError("Slot must last 30 minutes")
    P15 slot already has a Booking               -> ConflictError("Slot already booked")
    P16 slot reserved for another job            -> ConflictError("Slot is reserved for another job")

  FP-SCHED-3 (concurrency / unique constraints)
    P17 commit raises IntegrityError             -> rollback + ConflictError("Slot already booked")

  precedence (contract order is normative, contract section 7.3)
    P18 wrong candidate (check 2) beats wrong status (check 3) -> ForbiddenError
    P19 application already booked (check 4) beats missing slot (check 5)
                                                    -> ConflictError("Application already booked")

Hand calculations for the three contract scenarios
==================================================
S1  2099-01-01T10:00:00Z + 30 minutes = 2099-01-01T10:30:00Z; that is 1800 s,
    strictly after any plausible test-run clock, employer e1 == job employer e1,
    no existing booking.  Expected: BookingPublic(slot_id=s1, starts_at=10:00Z,
    ends_at=10:30Z); slot.job_id becomes j1; one Booking(a1, s1); one commit;
    application status/version untouched (Interviewing/1).
S2  same state with status Pending: check 2 passes, check 3 fires -> ConflictError;
    zero commits, application and slot unchanged.
S3  same state with candidate_id u2 while user.id u1: check 2 fires ->
    ForbiddenError; zero commits, application and slot unchanged.

State snapshot asserted for every pure validation rejection
===========================================================
(application.status, application.version, slot.job_id, session.commit call
count, number of Booking objects passed to session.add), compared before and
after the call, plus explicit "commit not called" and "no Booking staged"
assertions.  Missing rows contribute None to the snapshot.  P17 is the one
rejection produced by a commit, so there the snapshot rule is replaced by:
exactly one commit attempt, rollback requested, no successful persistence, and
application status/version unchanged.

Ambiguities resolved while generating (contract section 7)
==========================================================
1. Messages: the exception class is asserted exactly (``type(exc) is X``) for
   every rejection, but a message string is asserted only where the contract
   fixes one.
2. Rollback on a pure validation rejection: the contract permits but does not
   require it when nothing was staged, so these tests never assert either its
   presence or its absence there.
3. IntegrityError path: contract section 4 says every rejected call has no
   commit and no ``session.add(Booking)``, yet this partition is produced *by*
   a failing commit after the booking is staged.  Interpreted as: one commit
   attempt, a rollback call, and no successful persistence.  The session
   double's rollback is a no-op, so in-memory reversion of ``slot.job_id``
   cannot be observed; it is deliberately not asserted, because a real
   transaction rollback would restore the persisted state.
4. "Strictly in the future": a slot starting exactly at "now" must be rejected,
   but the clock is not injectable and the tests must use fixed timestamps, so
   the exact-now instant is not constructed.  2020 covers the past partition
   and 2099 the future partition.
5. Model columns: the blind generator may not inspect the production models,
   so rows are built from the columns named in the contract on real SQLModel
   classes.  ``_row`` is defensive only about additional required columns
   (validation-free constructor, then a spec'd object); no expected value
   changes with the construction path.
6. Persistence visibility ("same row for both parties") and HTTP status
   mapping (403/404/409) are outside ``book`` as specified, so service-level
   tests do not assert them.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.candidate.service import book, NotFoundError, ForbiddenError, ConflictError
from app.candidate.schema import BookingPublic
from app.employer.model import (
    Application,
    ApplicationStatus,
    Booking,
    InterviewSlot,
    Job,
)
from app.users.model import Role, User

from session_double import make_session


# Fixed IDs from the contract's hand-calculated scenarios.
U1 = uuid.UUID("11111111-1111-4111-8111-111111111111")
U2 = uuid.UUID("22222222-2222-4222-8222-222222222222")
E1 = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeee1")
E2 = uuid.UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeee2")
J1 = uuid.UUID("11111111-2222-4333-8444-555555555551")
J2 = uuid.UUID("11111111-2222-4333-8444-555555555552")
A1 = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1")
A2 = uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2")
S1 = uuid.UUID("55555555-5555-4555-8555-555555555551")
S2 = uuid.UUID("55555555-5555-4555-8555-555555555552")

# Fixed, timezone-aware timestamps (never "now").
T0 = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)
T30 = datetime(2099, 1, 1, 10, 30, tzinfo=timezone.utc)
T29 = datetime(2099, 1, 1, 10, 29, tzinfo=timezone.utc)
T31 = datetime(2099, 1, 1, 10, 31, tzinfo=timezone.utc)
PAST_T0 = datetime(2020, 1, 1, 10, 0, tzinfo=timezone.utc)
PAST_T30 = datetime(2020, 1, 1, 10, 30, tzinfo=timezone.utc)


def _row(model, **fields):
    """Build one model row carrying exactly the columns this contract names.

    Nothing here is an oracle; the fallbacks merely keep the suite usable if a
    table declares further required columns that this blind generator is not
    allowed to discover.  No database or network is touched: in the normal
    case this is simply ``model(**fields)``.
    """

    try:
        return model(**fields)
    except Exception:
        # Contract-unknown required columns (or a validation hook) rejected the
        # partial row; try the framework's validation-free constructor next.
        pass

    construct = getattr(model, "model_construct", None)
    if construct is None:
        construct = getattr(model, "construct", None)
    if construct is not None:
        try:
            row = construct(**fields)
            for name in fields:
                getattr(row, name)
        except Exception:
            pass
        else:
            return row

    row = MagicMock(spec=model)
    for name, value in fields.items():
        setattr(row, name, value)
    return row


def _make_user(user_id=U1):
    # Post-freeze repair: the synthesized account must carry the candidate role
    # that the service checks; the generated file had omitted this field.
    return _row(User, id=user_id, role=Role.Candidate)


def _make_application(
    *,
    application_id=A1,
    candidate_id=U1,
    job_id=J1,
    status=ApplicationStatus.Interviewing,
    version=1,
):
    return _row(
        Application,
        id=application_id,
        candidate_id=candidate_id,
        job_id=job_id,
        status=status,
        version=version,
    )


def _make_job(*, job_id=J1, employer_id=E1):
    return _row(Job, id=job_id, employer_id=employer_id)


def _make_slot(
    *,
    slot_id=S1,
    employer_id=E1,
    job_id=None,
    starts_at=T0,
    ends_at=T30,
):
    return _row(
        InterviewSlot,
        id=slot_id,
        employer_id=employer_id,
        job_id=job_id,
        starts_at=starts_at,
        ends_at=ends_at,
    )


def _booking_adds(session):
    """Return the Booking rows the service passed to ``session.add``."""

    return [
        call.args[0]
        for call in session.add.call_args_list
        if call.args and isinstance(call.args[0], Booking)
    ]


def _snapshot(application, slot, session):
    return (
        None if application is None else application.status,
        None if application is None else application.version,
        None if slot is None else slot.job_id,
        session.commit.call_count,
        len(_booking_adds(session)),
    )


def _assert_rejection(session, application, slot, exc_type, message=None):
    """Call the standard S1-shaped operation and assert a clean rejection."""

    before = _snapshot(application, slot, session)

    with pytest.raises(exc_type) as excinfo:
        book(session, _make_user(), A1, S1)

    assert type(excinfo.value) is exc_type
    if message is not None:
        assert str(excinfo.value) == message

    session.commit.assert_not_called()
    assert _booking_adds(session) == []
    assert _snapshot(application, slot, session) == before


def _assert_booking_created(result, session, application, slot):
    """Assert the exact observable outcome of a successful booking."""

    assert isinstance(result, BookingPublic)
    assert result.slot_id == S1
    assert result.starts_at == T0
    assert result.ends_at == T30

    added = _booking_adds(session)
    assert len(added) == 1
    booking = added[0]
    assert booking.application_id == A1
    assert booking.slot_id == S1
    assert isinstance(result.booking_id, uuid.UUID)
    assert result.booking_id == booking.id
    assert slot.job_id == application.job_id == J1
    assert application.status is ApplicationStatus.Interviewing
    assert application.version == 1
    session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Success partitions
# ---------------------------------------------------------------------------


def test_s1_eligible_booking_succeeds():
    """S1: 10:00Z + 30 min = 10:30Z, future, employer match, empty slot."""

    assert (T30 - T0).total_seconds() == 30 * 60

    application = _make_application()
    slot = _make_slot()
    job = _make_job()
    session = make_session(application=application, slot=slot, job=job)

    result = book(session, _make_user(), A1, S1)

    _assert_booking_created(result, session, application, slot)


def test_slot_already_reserved_for_the_same_job_is_eligible():
    """Check 11 accepts slot.job_id == application.job_id."""

    application = _make_application()
    slot = _make_slot(job_id=J1)
    job = _make_job()
    session = make_session(application=application, slot=slot, job=job)

    result = book(session, _make_user(), A1, S1)

    _assert_booking_created(result, session, application, slot)


# ---------------------------------------------------------------------------
# Eligibility rejections, one failing condition per test
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    [
        ApplicationStatus.Pending,
        ApplicationStatus.Rejected,
        ApplicationStatus.Accepted,
    ],
    ids=["pending", "rejected", "accepted"],
)
def test_s2_status_other_than_interviewing_is_conflict(status):
    """S2: any status other than Interviewing is a conflict."""

    application = _make_application(status=status)
    slot = _make_slot()
    job = _make_job()
    session = make_session(application=application, slot=slot, job=job)

    _assert_rejection(session, application, slot, ConflictError)


def test_s3_application_of_another_candidate_is_forbidden():
    """S3: application.candidate_id != user.id is forbidden."""

    application = _make_application(candidate_id=U2)
    slot = _make_slot()
    job = _make_job()
    session = make_session(application=application, slot=slot, job=job)

    _assert_rejection(session, application, slot, ForbiddenError)


def test_missing_application_is_not_found():
    application = None
    slot = _make_slot()
    job = _make_job()
    session = make_session(application=application, slot=slot, job=job)

    _assert_rejection(session, application, slot, NotFoundError)


def test_missing_slot_is_not_found_with_message():
    application = _make_application()
    slot = None
    job = _make_job()
    session = make_session(application=application, slot=slot, job=job)

    _assert_rejection(session, application, slot, NotFoundError, "Slot not found")


def test_missing_job_is_not_found_with_message():
    application = _make_application()
    slot = _make_slot()
    job = None
    session = make_session(application=application, slot=slot, job=job)

    _assert_rejection(session, application, slot, NotFoundError, "Job not found")


def test_slot_of_another_employer_is_forbidden():
    application = _make_application()
    slot = _make_slot(employer_id=E2)
    job = _make_job(employer_id=E1)
    session = make_session(application=application, slot=slot, job=job)

    _assert_rejection(
        session,
        application,
        slot,
        ForbiddenError,
        "Slot belongs to another employer",
    )


def test_slot_starting_in_the_past_is_conflict():
    application = _make_application()
    slot = _make_slot(starts_at=PAST_T0, ends_at=PAST_T30)
    job = _make_job()
    session = make_session(application=application, slot=slot, job=job)

    _assert_rejection(session, application, slot, ConflictError, "Slot is in the past")


@pytest.mark.parametrize(
    ("starts_at", "ends_at", "minutes"),
    [
        (T0, T29, 29),
        (T0, T31, 31),
    ],
    ids=["29-minutes", "31-minutes"],
)
def test_slot_duration_other_than_thirty_minutes_is_conflict(
    starts_at, ends_at, minutes
):
    assert (ends_at - starts_at).total_seconds() == minutes * 60

    application = _make_application()
    slot = _make_slot(starts_at=starts_at, ends_at=ends_at)
    job = _make_job()
    session = make_session(application=application, slot=slot, job=job)

    _assert_rejection(
        session,
        application,
        slot,
        ConflictError,
        "Slot must last 30 minutes",
    )


def test_application_already_booked_is_conflict():
    application = _make_application()
    slot = _make_slot()
    job = _make_job()
    existing = _row(Booking, application_id=A1, slot_id=S2)
    session = make_session(
        application=application,
        slot=slot,
        job=job,
        application_booking=existing,
    )

    _assert_rejection(
        session,
        application,
        slot,
        ConflictError,
        "Application already booked",
    )


def test_slot_already_booked_is_conflict():
    application = _make_application()
    slot = _make_slot()
    job = _make_job()
    existing = _row(Booking, application_id=A2, slot_id=S1)
    session = make_session(
        application=application,
        slot=slot,
        job=job,
        slot_booking=existing,
    )

    _assert_rejection(session, application, slot, ConflictError, "Slot already booked")


def test_slot_reserved_for_another_job_is_conflict():
    application = _make_application(job_id=J1)
    slot = _make_slot(job_id=J2)
    job = _make_job(job_id=J1)
    session = make_session(application=application, slot=slot, job=job)

    _assert_rejection(
        session,
        application,
        slot,
        ConflictError,
        "Slot is reserved for another job",
    )


# ---------------------------------------------------------------------------
# FP-SCHED-3: unique-constraint violation at commit time
# ---------------------------------------------------------------------------


def test_commit_integrity_error_rolls_back_and_reports_slot_already_booked():
    application = _make_application()
    slot = _make_slot()
    job = _make_job()
    session = make_session(application=application, slot=slot, job=job)
    session.commit.side_effect = IntegrityError(
        "INSERT INTO booking (application_id, slot_id) VALUES (:a, :s)",
        {"a": A1, "s": S1},
        Exception("duplicate key value violates unique constraint"),
    )

    with pytest.raises(ConflictError) as excinfo:
        book(session, _make_user(), A1, S1)

    assert type(excinfo.value) is ConflictError
    assert str(excinfo.value) == "Slot already booked"

    # The commit was attempted by construction and must have been rolled back.
    assert session.commit.call_count == 1
    assert session.rollback.called
    assert application.status is ApplicationStatus.Interviewing
    assert application.version == 1

    # The double records staged rows but never persists them and its rollback
    # is a no-op, so the only observable booking fact is that at most the one
    # attempted row was staged (ambiguity 3).
    assert len(_booking_adds(session)) <= 1


# ---------------------------------------------------------------------------
# Contract-order precedence (only these tests contain two simultaneous faults)
# ---------------------------------------------------------------------------


def test_precedence_wrong_candidate_beats_wrong_status():
    application = _make_application(
        candidate_id=U2,
        status=ApplicationStatus.Pending,
    )
    slot = _make_slot()
    job = _make_job()
    session = make_session(application=application, slot=slot, job=job)

    _assert_rejection(session, application, slot, ForbiddenError)


def test_precedence_application_booking_beats_missing_slot():
    application = _make_application()
    job = _make_job()
    existing = _row(Booking, application_id=A1, slot_id=S2)
    session = make_session(
        application=application,
        slot=None,
        job=job,
        application_booking=existing,
    )

    _assert_rejection(
        session,
        application,
        None,
        ConflictError,
        "Application already booked",
    )
