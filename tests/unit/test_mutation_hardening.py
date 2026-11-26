"""P7 mutation hardening: unit tests added because a mutant survived.

Every test here names the mutant ids it is designed to kill.  A mutant id is
``<file code><ordinal>`` as produced by ``tests/advanced/mutation/entry.py``
(``em`` = ``employer/matching.py``, ``us`` = ``users/service.py``,
``ca`` = ``candidate/service.py``, ``es`` = ``employer/service.py``,
``iv`` = ``interview/service.py``), and the baseline/final standings are
recorded in ``docs/advanced_testing/MUTATION.md``.

Two kinds of oracle are used, both derived from ``docs/REQUIREMENTS.md`` and
``SPEC.md`` rather than from the implementation:

* behaviour oracles drive a service through the existing ``MagicMock`` session
  double and assert the outcome the requirement promises;
* scoping oracles compile the statement a service hands to the session and
  assert the authorization predicate (``... WHERE owner = caller``) plus the
  bound parameter.  A session double cannot see which rows a query selects, so
  for owner scoping - the requirement of FP-SEC-1 / FP-AUTH-3 - the statement
  itself is the only unit-observable evidence.  This mirrors the assertions the
  pre-existing suite already makes (``test_fp_sec_2_email_is_a_bound_value``,
  ``test_fp_sched_1_management_list_preserves_booking_flag``).

The suites are ordered by requirement.  ``PURE_ORACLES`` at the bottom replays
the "deliberately break it, watch it go red" self-check for a representative
subset; the mutation run itself plays the same trick for every other test by
comparing its baseline (survived) and final (killed) status.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.candidate import service as candidate
from app.candidate.schema import ProfileUpdate
from app.employer import service as employer
from app.employer.model import (
    Application,
    ApplicationStatus,
    Booking,
    InterviewSlot,
    Job,
)
from app.employer.schema import (
    ApplicationStatusUpdate,
    CompanyUpdate,
    JobCreate,
    JobUpdate,
)
from app.interview import service as interview
from app.interview.schema import SlotCreate
from app.users import service as users
from app.users.model import (
    CandidateProfile,
    CandidateSkill,
    EmployerProfile,
    Role,
    User,
    UserSession,
)
from app.users.schema import (
    CandidateProfileCreate,
    CandidateProfilePublic,
    EmployerProfileCreate,
    EmployerProfilePublic,
    UserPublic,
)

FUTURE = datetime(2030, 5, 2, 1, 0, tzinfo=timezone.utc)
NOW = datetime(2030, 5, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def compiled(statement) -> str:
    """The SQL a statement would send, whitespace-normalised for assertions."""

    sql = str(statement.compile(dialect=postgresql.dialect()))
    return " ".join(sql.split())


def expect_equality(statement, column: str) -> None:
    """Assert a required ``column = value`` predicate, and not its negation.

    PostgreSQL quotes reserved identifiers (``"user".email``), so both spellings
    are accepted for the left-hand side.
    """

    sql = compiled(statement)
    table, _, field = column.rpartition(".")
    spellings = [column, f'"{table}".{field}']
    assert any(f"{name} = " in sql for name in spellings), sql
    assert all(f"{name} != " not in sql for name in spellings), sql


def assert_predicate(statement, predicate: str, forbidden: str) -> None:
    sql = compiled(statement)
    assert predicate in sql, sql
    assert forbidden not in sql, sql


def params_of(statement) -> list:
    return list(statement.compile().params.values())


def reset(db, make_result) -> None:
    """Clear call counts and configured behaviour, then restore the fixtures.

    ``MagicMock.reset_mock()`` keeps ``return_value``/``side_effect`` by default,
    which would silently leak one scenario's double into the next.
    """

    db.reset_mock(return_value=True, side_effect=True)
    db.get.return_value = None
    db.exec.return_value = make_result()


def store(*rows):
    """A ``Session.get`` double that only knows the (model, primary key) pairs."""

    known = {(type(row), row.user_id): row for row in rows}

    def get(model, ident, *args, **kwargs):
        return known.get((model, ident))

    return get


def future_slot(employer_id, job_id=None, starts_at=FUTURE, minutes=30) -> InterviewSlot:
    return InterviewSlot(
        employer_id=employer_id,
        job_id=job_id,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=minutes),
    )


def candidate_profile(actors) -> CandidateProfile:
    return CandidateProfile(user_id=actors[0].id, display_name="Owner")


# --------------------------------------------------------------------------- #
# FP-AUTH-1 accounts: profile completeness and session lifetime
# --------------------------------------------------------------------------- #


def _check_profile_completed(db, actors):
    candidate_user, employer_user = actors
    db.get.side_effect = store(
        CandidateProfile(user_id=candidate_user.id, display_name="Candidate")
    )
    view = users.get_current_user_public(db, candidate_user)
    assert view == UserPublic(
        id=candidate_user.id,
        email=candidate_user.email,
        role=Role.Candidate,
        profile_completed=True,
    )

    db.get.side_effect = store()
    assert users.get_current_user_public(db, candidate_user).profile_completed is False

    db.get.side_effect = store(
        EmployerProfile(user_id=employer_user.id, company_name="Company")
    )
    assert users.get_current_user_public(db, employer_user) == UserPublic(
        id=employer_user.id,
        email=employer_user.email,
        role=Role.Employer,
        profile_completed=True,
    )


def test_pauth1_profile_completed_tracks_the_role_specific_profile(db, actors):
    """Kills us006 us007 us008 (FP-AUTH-1: profile_completed is live status)."""

    _check_profile_completed(db, actors)


def _check_session_lifetime():
    # SPEC "User Login and Session Lifecycle": 720 minutes by default, 30 days
    # with remember_me enabled.
    assert users.session_lifetime(False) == timedelta(minutes=720)
    assert users.session_lifetime(True) == timedelta(days=30)


def test_pauth1_session_lifetime_has_two_documented_forms():
    """Kills us009 (FP-AUTH-1: remember_me chooses the session lifetime)."""

    _check_session_lifetime()


# --------------------------------------------------------------------------- #
# FP-AUTH-2/3 credential and session lookups
# --------------------------------------------------------------------------- #


def test_pauth3_email_lookup_is_equality_on_a_bound_value(db):
    """Kills us001 (FP-AUTH-1 uniqueness lookup, FP-SEC-2 binding)."""

    email = "ordinary'quote;--@example.com"
    users.get_user_by_email(db, email)
    statement = db.exec.call_args.args[0]
    expect_equality(statement, "user.email")
    assert email in params_of(statement)


def test_pauth3_session_lookup_uses_the_sha256_digest(db, actors, result):
    """Kills us015 (FP-AUTH-2: the database stores only a digest)."""

    token = "unit-session-token"
    row = UserSession(
        user_id=actors[0].id,
        token_hash="placeholder",
        csrf_token="csrf",
        expires_at=FUTURE,
    )
    db.exec.return_value = result(first=row)
    assert users.get_valid_session(db, token) is row
    statement = db.exec.call_args.args[0]
    expect_equality(statement, "user_session.token_hash")
    expected = hashlib.sha256(token.encode("utf-8")).hexdigest()
    assert expected in params_of(statement)
    assert token not in params_of(statement)


def test_pauth3_revoke_all_sessions_touches_one_account(db):
    """Kills us012 (FP-AUTH-3: revoking one account's sessions)."""

    user_id = uuid4()
    users.revoke_all_sessions(db, user_id)
    statement = db.exec.call_args.args[0]
    expect_equality(statement, "user_session.user_id")
    assert user_id in params_of(statement)
    db.commit.assert_called_once()


# --------------------------------------------------------------------------- #
# FP-CAN-1 candidate profile: creation, conflicts, owner-only reading
# --------------------------------------------------------------------------- #


def test_pcan1_candidate_profile_creation_persists_normalized_skills(db, actors):
    """Kills us043 us045 us051 (FP-CAN-1)."""

    request = CandidateProfileCreate(
        display_name=" Owner ",
        resume_text="Private CV",
        skills=[" SQL ", "python", "PYTHON", ""],
    )
    saved = users.create_candidate_profile(db, actors[0], request)
    assert saved == CandidateProfilePublic(
        user_id=actors[0].id,
        display_name="Owner",
        resume_text="Private CV",
        skills=["python", "sql"],
        version=1,
    )
    added = [call.args[0] for call in db.add.call_args_list]
    assert any(isinstance(row, CandidateProfile) for row in added)
    assert sorted(row.name for row in added if isinstance(row, CandidateSkill)) == [
        "python",
        "sql",
    ]
    db.flush.assert_called_once()
    db.commit.assert_called_once()


def test_pcan1_candidate_profile_conflicts_are_translated(db, actors, result):
    """Kills us046 us047 us048 us049 us050 (FP-CAN-1: at most one profile)."""

    request = CandidateProfileCreate(display_name="Owner")

    db.get.return_value = CandidateProfile(
        user_id=actors[0].id, display_name="Existing"
    )
    with pytest.raises(users.ProfileAlreadyExistsError):
        users.create_candidate_profile(db, actors[0], request)
    db.add.assert_not_called()
    db.commit.assert_not_called()

    # Concurrent insert: the unique violation is confirmed by a re-read.
    reset(db, result)
    db.get.return_value = None
    db.get.side_effect = [
        None,
        CandidateProfile(user_id=actors[0].id, display_name="Winner"),
    ]
    db.flush.side_effect = IntegrityError("INSERT", {}, Exception("duplicate key"))
    with pytest.raises(users.ProfileAlreadyExistsError):
        users.create_candidate_profile(db, actors[0], request)
    db.rollback.assert_called_once()

    # A unique violation that is not about this profile must surface unchanged.
    reset(db, result)
    db.get.return_value = None
    db.get.side_effect = [None, None]
    db.flush.side_effect = IntegrityError("INSERT", {}, Exception("other key"))
    with pytest.raises(IntegrityError):
        users.create_candidate_profile(db, actors[0], request)
    db.rollback.assert_called_once()

    # Infrastructure failure must roll back and surface.
    reset(db, result)
    db.get.return_value = None
    db.flush.side_effect = SQLAlchemyError("connection lost")
    with pytest.raises(SQLAlchemyError):
        users.create_candidate_profile(db, actors[0], request)
    db.rollback.assert_called_once()


def test_pcan1_candidate_profile_creation_requires_the_candidate_role(db, actors):
    """Kills us044 (FP-CAN-1 with FP-AUTH-3: setup is role gated)."""

    db.get.return_value = None
    with pytest.raises(users.CandidateRoleRequiredError):
        users.create_candidate_profile(
            db, actors[1], CandidateProfileCreate(display_name="Owner")
        )
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_pauth3_candidate_services_reject_the_employer_role(db, actors):
    """Kills ca002 (FP-AUTH-3: the service layer repeats the role check)."""

    employer = actors[1]
    calls = [
        ("get_my_profile", lambda: candidate.get_my_profile(db, employer)),
        (
            "update_my_profile",
            lambda: candidate.update_my_profile(db, employer, ProfileUpdate(version=1)),
        ),
        ("list_jobs", lambda: candidate.list_jobs(db, employer)),
        ("get_job", lambda: candidate.get_job(db, employer, uuid4())),
        ("list_applications", lambda: candidate.list_applications(db, employer)),
        ("get_application", lambda: candidate.get_application(db, employer, uuid4())),
        ("apply", lambda: candidate.apply(db, employer, uuid4())),
        ("book", lambda: candidate.book(db, employer, uuid4(), uuid4())),
    ]
    for name, call in calls:
        try:
            call()
        except users.CandidateRoleRequiredError:
            continue
        raise AssertionError(f"{name} accepted an employer account")
    db.exec.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()


def _check_owner_reads_own_profile(db, actors, result):
    profile = CandidateProfile(
        user_id=actors[0].id, display_name="Owner", resume_text="Private CV", version=3
    )
    db.get.return_value = profile
    db.exec.return_value = result(rows=["sql", "python"])
    view = candidate.read_profile(db, actors[0], actors[0].id)
    assert view == CandidateProfilePublic(
        user_id=actors[0].id,
        display_name="Owner",
        resume_text="Private CV",
        skills=["python", "sql"],
        version=3,
    )
    expect_equality(db.exec.call_args.args[0], "candidate_skill.candidate_id")


def test_pcan1_owner_reads_own_private_profile(db, actors, result):
    """Kills ca007 ca010 ca016 (FP-CAN-1: owner-only resume access)."""

    _check_owner_reads_own_profile(db, actors, result)


def test_pcan1_profile_update_locks_the_owner_row(db, actors, result):
    """Kills ca003 ca020 (FP-CAN-1, SPEC version-protected edits)."""

    profile = CandidateProfile(user_id=actors[0].id, display_name="Owner")
    db.exec.side_effect = [result(first=profile), result(rows=["python"])]
    candidate.update_my_profile(
        db, actors[0], ProfileUpdate(version=1, skills=[" Python "])
    )
    expect_equality(db.exec.call_args_list[0].args[0], "candidate_profile.user_id")
    expect_equality(db.execute.call_args.args[0], "candidate_skill.candidate_id")


# --------------------------------------------------------------------------- #
# FP-EMP-1 company profile
# --------------------------------------------------------------------------- #


def test_pemp1_employer_profile_creation_and_conflicts(db, actors, result):
    """Kills us033 us034 us035 us036 us041 (FP-EMP-1)."""

    request = EmployerProfileCreate(company_name="Company", company_description="Intro")
    saved = users.create_employer_profile(db, actors[1], request)
    assert saved == EmployerProfilePublic(
        user_id=actors[1].id,
        company_name="Company",
        company_description="Intro",
        version=1,
    )
    db.flush.assert_called_once()
    db.commit.assert_called_once()

    reset(db, result)
    db.get.return_value = EmployerProfile(
        user_id=actors[1].id, company_name="Existing"
    )
    with pytest.raises(users.ProfileAlreadyExistsError):
        users.create_employer_profile(db, actors[1], request)
    db.add.assert_not_called()
    db.commit.assert_not_called()

    reset(db, result)
    db.get.return_value = None
    with pytest.raises(users.EmployerRoleRequiredError):
        users.create_employer_profile(db, actors[0], request)
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_pemp1_employer_profile_failures_are_translated(db, actors, result):
    """Kills us037 us038 us039 us040 (FP-EMP-1: at most one company profile)."""

    request = EmployerProfileCreate(company_name="Company")

    db.get.return_value = None
    db.get.side_effect = [
        None,
        EmployerProfile(user_id=actors[1].id, company_name="Winner"),
    ]
    db.flush.side_effect = IntegrityError("INSERT", {}, Exception("duplicate key"))
    with pytest.raises(users.ProfileAlreadyExistsError):
        users.create_employer_profile(db, actors[1], request)
    db.rollback.assert_called_once()

    reset(db, result)
    db.get.return_value = None
    db.get.side_effect = [None, None]
    db.flush.side_effect = IntegrityError("INSERT", {}, Exception("other key"))
    with pytest.raises(IntegrityError):
        users.create_employer_profile(db, actors[1], request)
    db.rollback.assert_called_once()

    reset(db, result)
    db.get.return_value = None
    db.flush.side_effect = SQLAlchemyError("connection lost")
    with pytest.raises(SQLAlchemyError):
        users.create_employer_profile(db, actors[1], request)
    db.rollback.assert_called_once()


def test_pemp1_company_update_requires_a_profile_and_locks_it(db, actors, result):
    """Kills es007 es009 (FP-EMP-1: 404 before setup)."""

    db.exec.return_value = result(first=None)
    with pytest.raises(employer.CompanyNotFoundError):
        employer.update_my_company(
            db, actors[1], CompanyUpdate(version=1, company_name="Name")
        )
    expect_equality(db.exec.call_args.args[0], "employer_profile.user_id")
    db.commit.assert_not_called()


# --------------------------------------------------------------------------- #
# FP-CAN-2 recommendations and single job view
# --------------------------------------------------------------------------- #


def test_pcan2_get_job_reads_only_the_requested_active_job(db, actors, result):
    """Kills ca033 ca034 ca037 ca047 (FP-CAN-2)."""

    job = Job(employer_id=actors[1].id, title="Job", description="Details")
    db.exec.side_effect = [
        result(rows=[(job, "Company", "Intro", False)]),
        result(rows=[(actors[0].id, "python")]),
        result(rows=[(job.id, "python")]),
    ]
    view = candidate.get_job(db, actors[0], job.id)
    assert view.id == job.id and view.title == "Job"
    assert view.match_score == 100 and view.applied is False
    statement = db.exec.call_args_list[0].args[0]
    expect_equality(statement, "job.id")
    assert job.id in params_of(statement)

    # A soft-deleted or unknown job is a 404, not an empty recommendation list.
    reset(db, result)
    db.exec.return_value = result()
    with pytest.raises(candidate.NotFoundError, match="Job not found"):
        candidate.get_job(db, actors[0], job.id)


def test_pcan2_recommendations_scope_applied_flag_and_skills_to_the_caller(
    db, actors, result
):
    """Kills ca030 ca031 ca039 (FP-CAN-2: per-candidate applied flag)."""

    job = Job(employer_id=actors[1].id, title="Job", description="Details")
    db.exec.side_effect = [
        result(rows=[(job, "Company", "Intro", False)]),
        result(rows=[(actors[0].id, "python")]),
        result(rows=[(job.id, "python")]),
    ]
    rows = candidate.list_jobs(db, actors[0])
    assert [row.id for row in rows] == [job.id]
    main = db.exec.call_args_list[0].args[0]
    expect_equality(main, "application.candidate_id")
    assert_predicate(main, "application.job_id = ", "application.job_id != ")
    assert actors[0].id in params_of(main)
    profile_query = db.exec.call_args_list[1].args[0]
    expect_equality(profile_query, "candidate_profile.user_id")
    assert actors[0].id in params_of(profile_query)


# --------------------------------------------------------------------------- #
# FP-CAN-3 applications
# --------------------------------------------------------------------------- #


def test_pcan3_applying_to_a_missing_or_deleted_job_is_not_found(db, actors, result):
    """Kills ca027 ca028 (FP-CAN-3 with FP-EMP-2 soft deletion)."""

    for job in (
        None,
        Job(employer_id=actors[1].id, title="Gone", description="D", is_deleted=True),
    ):
        reset(db, result)
        db.get.return_value = candidate_profile(actors)
        db.exec.return_value = result(first=job)
        with pytest.raises(candidate.NotFoundError, match="Job not found"):
            candidate.apply(db, actors[0], uuid4())
        db.add.assert_not_called()
        db.commit.assert_not_called()
        db.rollback.assert_called_once()


def test_pcan3_missing_and_foreign_applications_are_not_visible(db, actors, result):
    """Kills ca050 ca052 (FP-AUTH-3: 404 for missing, 403 for foreign)."""

    db.exec.return_value = result(first=None)
    with pytest.raises(candidate.NotFoundError, match="Application not found"):
        candidate.get_application(db, actors[0], uuid4())
    expect_equality(db.exec.call_args.args[0], "application.id")

    foreign = Application(candidate_id=uuid4(), job_id=uuid4())
    db.exec.return_value = result(first=foreign)
    with pytest.raises(candidate.ForbiddenError):
        candidate.get_application(db, actors[0], foreign.id)
    db.commit.assert_not_called()


def test_pcan3_application_list_is_scoped_to_the_caller(db, actors, result):
    """Kills ca056 ca065 (FP-CAN-3)."""

    db.exec.return_value = result(rows=[])
    assert candidate.list_applications(db, actors[0]) == []
    statement = db.exec.call_args.args[0]
    expect_equality(statement, "application.candidate_id")
    assert actors[0].id in params_of(statement)


def test_pcan3_apply_locks_the_active_job_and_returns_the_public_view(
    db, actors, result
):
    """Kills ca025 (FP-CAN-3 with SPEC job-deletion/application serialisation)."""

    job = Job(employer_id=actors[1].id, title="Job", description="Details")
    db.get.return_value = candidate_profile(actors)
    db.exec.side_effect = [
        result(first=job),
        result(first=None),
        result(rows=[(job.id, "Job", "Company")]),
        result(rows=[]),
    ]
    saved = candidate.apply(db, actors[0], job.id)
    assert saved.job_id == job.id and saved.job_title == "Job"
    assert saved.company_name == "Company" and saved.booking is None
    assert saved.status == ApplicationStatus.Pending
    expect_equality(db.exec.call_args_list[0].args[0], "job.id")
    assert job.id in params_of(db.exec.call_args_list[0].args[0])
    db.commit.assert_called_once()


def test_pcan3_duplicate_apply_from_the_unique_constraint_is_a_conflict(
    db, actors, result
):
    """Kills ca074 ca075 ca076 ca077 (FP-CAN-3: one application per job)."""

    job = Job(employer_id=actors[1].id, title="Job", description="Details")
    db.get.return_value = candidate_profile(actors)
    db.exec.side_effect = [
        result(first=job),
        result(first=None),
        result(first=uuid4()),
    ]
    db.commit.side_effect = IntegrityError("INSERT", {}, Exception("duplicate key"))
    with pytest.raises(candidate.ConflictError, match="Already applied"):
        candidate.apply(db, actors[0], job.id)
    assert db.exec.call_count == 3
    precheck = db.exec.call_args_list[1].args[0]
    expect_equality(precheck, "application.candidate_id")
    expect_equality(precheck, "application.job_id")
    recheck = db.exec.call_args_list[2].args[0]
    expect_equality(recheck, "application.candidate_id")
    expect_equality(recheck, "application.job_id")
    assert actors[0].id in params_of(recheck) and job.id in params_of(recheck)
    db.rollback.assert_called_once()


def test_pcan3_non_duplicate_integrity_error_surfaces_unchanged(db, actors, result):
    """Kills ca078 (FP-CAN-3: only confirmed duplicates become 409)."""

    job = Job(employer_id=actors[1].id, title="Job", description="Details")
    error = IntegrityError("INSERT", {}, Exception("other constraint"))
    db.get.return_value = candidate_profile(actors)
    db.exec.side_effect = [result(first=job), result(first=None), result(first=None)]
    db.commit.side_effect = error
    with pytest.raises(IntegrityError) as caught:
        candidate.apply(db, actors[0], job.id)
    assert caught.value is error
    db.rollback.assert_called_once()


# --------------------------------------------------------------------------- #
# FP-SCHED-1 availability slots
# --------------------------------------------------------------------------- #


def test_psched1_slot_creation_requires_an_employer_profile(db, actors):
    """Kills iv010 (FP-SCHED-1 / SPEC: 404 before setup)."""

    db.get.return_value = None
    with pytest.raises(interview.NotFoundError, match="Employer profile"):
        interview.create_slot(
            db, actors[1], SlotCreate(starts_at="2030-05-02T01:00:00Z")
        )
    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_psched1_overlap_query_is_employer_scoped_and_half_open(db, actors, result):
    """Kills iv015 iv016 iv017 (FP-SCHED-1: no overlap for one employer)."""

    db.get.return_value = EmployerProfile(
        user_id=actors[1].id, company_name="Company"
    )
    db.exec.return_value = result(first=None)
    saved = interview.create_slot(
        db, actors[1], SlotCreate(starts_at="2030-05-02T01:00:00Z")
    )
    assert saved.ends_at - saved.starts_at == timedelta(minutes=30)
    statement = db.exec.call_args.args[0]
    expect_equality(statement, "interview_slot.employer_id")
    assert_predicate(
        statement, "interview_slot.starts_at < ", "interview_slot.starts_at >= "
    )
    assert_predicate(
        statement, "interview_slot.ends_at > ", "interview_slot.ends_at <= "
    )
    assert actors[1].id in params_of(statement)


def test_psched1_slot_end_must_precede_the_documented_cutoff(db, actors, result):
    """Kills iv003 iv004 iv006 iv008 (FP-SCHED-1 / SPEC interview date limit)."""

    cutoff = datetime(3001, 1, 1, tzinfo=ZoneInfo("Asia/Shanghai")).astimezone(
        timezone.utc
    )
    db.get.return_value = EmployerProfile(
        user_id=actors[1].id, company_name="Company"
    )
    db.exec.return_value = result(first=None)

    last_allowed = cutoff - timedelta(minutes=30, seconds=1)
    saved = interview.create_slot(
        db, actors[1], SlotCreate(starts_at=last_allowed.isoformat())
    )
    assert saved.ends_at < cutoff

    for rejected in (cutoff - timedelta(minutes=30), cutoff - timedelta(seconds=1)):
        db.rollback.reset_mock()
        with pytest.raises(interview.InvalidSlotError):
            interview.create_slot(
                db, actors[1], SlotCreate(starts_at=rejected.isoformat())
            )
        db.rollback.assert_called_once()


def test_psched1_slot_list_is_employer_scoped_and_future_only(db, actors, result):
    """Kills iv028 iv029 (FP-SCHED-1: an employer sees only its future slots)."""

    db.exec.return_value = result(rows=[])
    assert interview.list_slots(db, actors[1]) == []
    statement = db.exec.call_args.args[0]
    expect_equality(statement, "interview_slot.employer_id")
    assert_predicate(
        statement, "interview_slot.starts_at > ", "interview_slot.starts_at <= "
    )
    assert actors[1].id in params_of(statement)


def test_psched1_slot_deletion_queries_are_scoped(db, actors, result):
    """Kills iv033 iv038 (FP-SCHED-1 with FP-SEC-1 ownership)."""

    slot = future_slot(actors[1].id)
    db.exec.side_effect = [result(first=slot), result(first=None)]
    interview.delete_slot(db, actors[1], slot.id)
    expect_equality(db.exec.call_args_list[0].args[0], "interview_slot.id")
    expect_equality(db.exec.call_args_list[1].args[0], "booking.slot_id")
    db.delete.assert_called_once_with(slot)
    db.commit.assert_called_once()


# --------------------------------------------------------------------------- #
# FP-SCHED-2/3 booking
# --------------------------------------------------------------------------- #


def prepare_booking(db, actors, result):
    application = Application(
        candidate_id=actors[0].id,
        job_id=uuid4(),
        status=ApplicationStatus.Interviewing,
    )
    slot = future_slot(actors[1].id)
    db.get.return_value = Job(
        id=application.job_id, employer_id=actors[1].id, title="Job", description="D"
    )
    db.exec.side_effect = [
        result(first=application),
        result(first=None),
        result(first=slot),
        result(first=None),
    ]
    return application, slot


def test_psched2_booking_reads_are_scoped_to_the_application_and_slot(
    db, actors, result
):
    """Kills ca085 ca098 ca111 (FP-SCHED-2/3: no cross-object booking)."""

    application, slot = prepare_booking(db, actors, result)
    saved = candidate.book(db, actors[0], application.id, slot.id)
    assert saved.slot_id == slot.id and saved.starts_at == slot.starts_at
    assert slot.job_id == application.job_id
    calls = [call.args[0] for call in db.exec.call_args_list]
    expect_equality(calls[0], "application.id")
    expect_equality(calls[1], "booking.application_id")
    expect_equality(calls[2], "interview_slot.id")
    expect_equality(calls[3], "booking.slot_id")
    assert application.id in params_of(calls[1]) and slot.id in params_of(calls[3])
    db.commit.assert_called_once()


def test_psched2_available_slots_query_carries_every_eligibility_rule(
    db, actors, result
):
    """Kills ca091 ca092 ca093 ca094 (FP-SCHED-2 eligibility)."""

    application = Application(
        candidate_id=actors[0].id,
        job_id=uuid4(),
        status=ApplicationStatus.Interviewing,
    )
    db.get.return_value = Job(
        id=application.job_id, employer_id=actors[1].id, title="Job", description="D"
    )
    db.exec.side_effect = [result(first=application), result(first=None), result()]
    assert candidate.available_slots(db, actors[0], application.id) == []
    statement = db.exec.call_args.args[0]
    expect_equality(statement, "interview_slot.employer_id")
    assert_predicate(statement, "interview_slot.job_id = ", "interview_slot.job_id != ")
    assert_predicate(
        statement, "interview_slot.starts_at > ", "interview_slot.starts_at <= "
    )
    assert_predicate(
        statement,
        "interview_slot.ends_at - interview_slot.starts_at = ",
        "interview_slot.ends_at - interview_slot.starts_at != ",
    )
    params = params_of(statement)
    assert actors[1].id in params and timedelta(minutes=30) in params


def test_psched2_available_slots_requires_the_application_job(db, actors, result):
    """Kills ca090 (FP-SCHED-2: a vanished job has no bookable slots)."""

    application = Application(
        candidate_id=actors[0].id,
        job_id=uuid4(),
        status=ApplicationStatus.Interviewing,
    )
    db.get.return_value = None
    db.exec.side_effect = [result(first=application), result(first=None)]
    with pytest.raises(candidate.NotFoundError, match="Job not found"):
        candidate.available_slots(db, actors[0], application.id)


def test_psched2_slot_reserved_for_another_job_is_a_conflict(db, actors, result):
    """Kills ca116 ca117 (FP-SCHED-2: 409 Slot is reserved for another job)."""

    application = Application(
        candidate_id=actors[0].id,
        job_id=uuid4(),
        status=ApplicationStatus.Interviewing,
    )
    slot = future_slot(actors[1].id, job_id=uuid4())
    db.get.return_value = Job(
        id=application.job_id, employer_id=actors[1].id, title="Job", description="D"
    )
    db.exec.side_effect = [
        result(first=application),
        result(first=None),
        result(first=slot),
        result(first=None),
    ]
    with pytest.raises(candidate.ConflictError, match="reserved for another job"):
        candidate.book(db, actors[0], application.id, slot.id)
    assert slot.job_id != application.job_id
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_psched2_booking_requires_the_application_job(db, actors, result):
    """Kills ca102 (FP-SCHED-2: a vanished job cannot be booked)."""

    application = Application(
        candidate_id=actors[0].id,
        job_id=uuid4(),
        status=ApplicationStatus.Interviewing,
    )
    slot = future_slot(actors[1].id)
    db.get.return_value = None
    db.exec.side_effect = [
        result(first=application),
        result(first=None),
        result(first=slot),
    ]
    with pytest.raises(candidate.NotFoundError, match="Job not found"):
        candidate.book(db, actors[0], application.id, slot.id)
    db.add.assert_not_called()


def test_psched3_conflict_recovery_queries_are_scoped(db, actors, result):
    """Kills ca118 ca121 (FP-SCHED-3: 409 names the collision that happened)."""

    application = Application(
        candidate_id=actors[0].id,
        job_id=uuid4(),
        status=ApplicationStatus.Interviewing,
    )
    slot = future_slot(actors[1].id)
    db.get.return_value = Job(
        id=application.job_id, employer_id=actors[1].id, title="Job", description="D"
    )
    error = IntegrityError("INSERT booking", {}, Exception("unique violation"))

    # The slot was taken by a competitor: the slot unique constraint fired.
    db.exec.side_effect = [
        result(first=application),
        result(first=None),
        result(first=slot),
        result(first=None),
        result(first=uuid4()),
        result(first=None),
    ]
    db.commit.side_effect = error
    with pytest.raises(candidate.ConflictError, match="Slot already booked"):
        candidate.book(db, actors[0], application.id, slot.id)
    expect_equality(db.exec.call_args_list[4].args[0], "booking.slot_id")
    assert slot.id in params_of(db.exec.call_args_list[4].args[0])

    # This application already booked a different slot.
    reset(db, result)
    db.get.return_value = Job(
        id=application.job_id, employer_id=actors[1].id, title="Job", description="D"
    )
    db.exec.side_effect = [
        result(first=application),
        result(first=None),
        result(first=slot),
        result(first=None),
        result(first=None),
        result(first=uuid4()),
    ]
    db.commit.side_effect = error
    with pytest.raises(candidate.ConflictError, match="Application already booked"):
        candidate.book(db, actors[0], application.id, slot.id)
    expect_equality(db.exec.call_args_list[5].args[0], "booking.application_id")
    assert application.id in params_of(db.exec.call_args_list[5].args[0])
    db.rollback.assert_called_once()


# --------------------------------------------------------------------------- #
# FP-EMP-2 job postings
# --------------------------------------------------------------------------- #


def test_pemp2_job_list_is_owner_scoped_newest_first(db, actors, result):
    """Kills es023 es024 (FP-EMP-2: own active jobs, newest first)."""

    older = Job(
        employer_id=actors[1].id,
        title="Older",
        description="D",
        created_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    newer = Job(
        employer_id=actors[1].id,
        title="Newer",
        description="D",
        created_at=datetime(2030, 2, 1, tzinfo=timezone.utc),
    )
    db.get.return_value = EmployerProfile(
        user_id=actors[1].id, company_name="Company"
    )
    db.exec.side_effect = [
        result(rows=[older, newer]),
        result(rows=["python"]),
        result(rows=["sql"]),
    ]
    rows = employer.list_my_jobs(db, actors[1])
    assert [row.title for row in rows] == ["Newer", "Older"]
    statement = db.exec.call_args_list[0].args[0]
    expect_equality(statement, "job.employer_id")
    assert actors[1].id in params_of(statement)
    assert "job.is_deleted IS false" in compiled(statement)


def test_pemp2_job_creation_rolls_back_infrastructure_failure(db, actors):
    """Kills es021 (FP-EMP-2 / SPEC: a failed write leaves no partial row)."""

    db.get.return_value = EmployerProfile(
        user_id=actors[1].id, company_name="Company"
    )
    db.commit.side_effect = SQLAlchemyError("connection lost")
    with pytest.raises(SQLAlchemyError):
        employer.create_job(
            db,
            actors[1],
            JobCreate(title="Job", description="D", required_skills=["python"]),
        )
    db.rollback.assert_called_once()


def test_pemp2_job_deletion_checks_both_dependent_tables(db, actors, result):
    """Kills es041 es045 (FP-EMP-2: applications or slots block deletion)."""

    job = Job(employer_id=actors[1].id, title="Job", description="D")
    db.exec.side_effect = [result(first=job), result(first=None), result(first=None)]
    employer.delete_job(db, actors[1], job.id)
    calls = [call.args[0] for call in db.exec.call_args_list]
    expect_equality(calls[1], "application.job_id")
    expect_equality(calls[2], "interview_slot.job_id")
    assert job.id in params_of(calls[1]) and job.id in params_of(calls[2])
    assert job.is_deleted
    db.commit.assert_called_once()


def test_pemp2_job_deletion_rolls_back_infrastructure_failure(db, actors, result):
    """Kills es052 (FP-EMP-2: failed deletion leaves the job active)."""

    job = Job(employer_id=actors[1].id, title="Job", description="D")
    db.exec.side_effect = [result(first=job), result(first=None), result(first=None)]
    db.commit.side_effect = SQLAlchemyError("connection lost")
    with pytest.raises(SQLAlchemyError):
        employer.delete_job(db, actors[1], job.id)
    db.rollback.assert_called_once()


def test_pemp2_job_access_and_skill_queries_are_owner_scoped(db, actors, result):
    """Kills es016 es025 es036 (FP-EMP-2 with FP-SEC-1 ownership)."""

    job = Job(employer_id=actors[1].id, title="Job", description="D")
    db.get.side_effect = lambda model, ident, *a, **k: (
        job
        if model is Job
        else EmployerProfile(user_id=actors[1].id, company_name="Company")
    )
    db.exec.return_value = result(first=job, rows=["python"])
    employer.get_my_job(db, actors[1], job.id)
    expect_equality(db.exec.call_args.args[0], "job_skill.job_id")
    assert job.id in params_of(db.exec.call_args.args[0])

    reset(db, result)
    db.get.side_effect = lambda model, ident, *a, **k: (
        job
        if model is Job
        else EmployerProfile(user_id=actors[1].id, company_name="Company")
    )
    db.exec.side_effect = [result(first=job), result(rows=["python"])]
    employer.update_job(
        db, actors[1], job.id, JobUpdate(version=1, required_skills=["python"])
    )
    expect_equality(db.exec.call_args_list[0].args[0], "job.id")
    expect_equality(db.execute.call_args.args[0], "job_skill.job_id")


# --------------------------------------------------------------------------- #
# FP-EMP-3 applicant management
# --------------------------------------------------------------------------- #


def test_pemp3_status_change_requires_a_live_owned_job(db, actors, result):
    """Kills es064 es066 es068 es069 (FP-EMP-3 with FP-AUTH-3)."""

    application = Application(candidate_id=uuid4(), job_id=uuid4(), version=1)
    db.exec.return_value = result(first=None)
    with pytest.raises(employer.ApplicationNotFoundError):
        employer.change_application_status(
            db,
            actors[1],
            application.id,
            ApplicationStatusUpdate(version=1, status="Interviewing"),
        )
    expect_equality(db.exec.call_args.args[0], "application.id")

    reset(db, result)
    db.exec.return_value = result(first=application)
    db.get.return_value = Job(
        id=application.job_id,
        employer_id=actors[1].id,
        title="Job",
        description="D",
        is_deleted=True,
    )
    with pytest.raises(employer.JobNotFoundError):
        employer.change_application_status(
            db,
            actors[1],
            application.id,
            ApplicationStatusUpdate(version=1, status="Interviewing"),
        )
    assert application.status == ApplicationStatus.Pending
    db.commit.assert_not_called()


def test_pemp3_applicant_list_skips_rows_without_a_profile(db, actors, result):
    """Kills es057 es058 es060 es062 (FP-EMP-3: only real candidates are listed)."""

    job = Job(employer_id=actors[1].id, title="Job", description="D")
    ann = uuid4()
    bob = uuid4()
    applications = [
        Application(candidate_id=bob, job_id=job.id),
        Application(candidate_id=ann, job_id=job.id),
    ]
    accounts = {
        ann: User(
            id=ann,
            email="ann@example.com",
            hashed_password="synthetic",
            role=Role.Candidate,
        ),
        bob: User(
            id=bob,
            email="bob@example.com",
            hashed_password="synthetic",
            role=Role.Candidate,
        ),
    }
    profiles = {ann: CandidateProfile(user_id=ann, display_name="Ann")}

    def get(model, ident, *args, **kwargs):
        if model is Job and ident == job.id:
            return job
        if model is CandidateProfile:
            return profiles.get(ident)
        if model is User:
            return accounts.get(ident)
        return None

    db.get.side_effect = get
    db.exec.side_effect = [
        result(rows=["python"]),
        result(rows=applications),
        result(rows=["python"]),
        result(first=None),
    ]
    rows = employer.list_job_applicants(db, actors[1], job.id)
    assert [row.candidate_id for row in rows] == [ann]
    assert rows[0].match_score == 100 and rows[0].display_name == "Ann"
    calls = [call.args[0] for call in db.exec.call_args_list]
    expect_equality(calls[0], "job_skill.job_id")
    expect_equality(calls[1], "application.job_id")
    expect_equality(calls[2], "candidate_skill.candidate_id")


def test_pemp3_booking_lookup_is_application_scoped(db, actors, result):
    """Kills es053 (FP-EMP-3: the applicant row shows its own booking)."""

    application_id = uuid4()
    slot = future_slot(actors[1].id)
    booking = Booking(application_id=application_id, slot_id=slot.id)
    db.exec.return_value = result(first=booking)
    db.get.return_value = slot
    view = employer._booking_public(db, application_id)
    assert view is not None and view.booking_id == booking.id
    expect_equality(db.exec.call_args.args[0], "booking.application_id")
    assert application_id in params_of(db.exec.call_args.args[0])

    reset(db, result)
    db.exec.return_value = result(first=None)
    assert employer._booking_public(db, application_id) is None


# --------------------------------------------------------------------------- #
# self-check: the hardening oracles are not vacuous
# --------------------------------------------------------------------------- #
#
# Requirement 7 of the task brief asks for one "deliberately break it, watch it
# go red, restore it" rehearsal per new oracle.  The mutation run is that
# rehearsal for every test above: the mutant is injected into a disposable copy
# of ``backend/`` (never the repository), the test goes red, the copy is
# restored, and ``killed_by`` in ``mutation-result.json`` records the exact node
# id that detected it - the same test is green without the mutant.
#
# These three tests additionally replay the mechanism in-process with
# ``monkeypatch`` so the property is visible inside the unit suite itself.


def test_selfcheck_session_lifetime_oracle_detects_us009(monkeypatch):
    """us009 makes ``session_lifetime`` return None; the oracle must notice."""

    monkeypatch.setattr(users, "session_lifetime", lambda remember_me: None)
    with pytest.raises(AssertionError):
        _check_session_lifetime()


def test_selfcheck_profile_completed_oracle_detects_us008(monkeypatch, db, actors):
    """us008 makes the account view collapse to None; the oracle must notice."""

    monkeypatch.setattr(users, "get_current_user_public", lambda session, user: None)
    with pytest.raises(AssertionError):
        _check_profile_completed(db, actors)


def test_selfcheck_owner_read_oracle_detects_ca016(
    monkeypatch, db, actors, result
):
    """ca016 drops the public profile view; the oracle must notice."""

    monkeypatch.setattr(candidate, "_profile_public", lambda session, profile: None)
    with pytest.raises(AssertionError):
        _check_owner_reads_own_profile(db, actors, result)
