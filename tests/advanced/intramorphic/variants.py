"""Helpers for the P9 metamorphic / intramorphic suite.

The intramorphic tests leave the production source tree untouched.  Every
"variant" is a *controlled program variant* installed with pytest's
``monkeypatch`` fixture, so pytest restores the original attribute at the end
of each test even when an assertion fails.

Two kinds of helpers live here:

* small real-HTTP builders (accounts still come from the shared ``account``
  fixture; these helpers only remove repetition);
* monkeypatch installers that disable one defence layer at a time, plus the
  bookkeeping needed to prove the concurrent and database-constraint evidence.

Nothing in this module imports a production function to compute an expected
value: the assertions live in the test modules and use hand-written oracles or
an invariant of the workflow.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import threading
import time

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.selectable import Select
from sqlmodel import Session

SEED = 4801


# ---------------------------------------------------------------------------
# Real-HTTP helpers
# ---------------------------------------------------------------------------


def expect(response, status: int, label: str):
    """Assert one HTTP outcome and return the decoded JSON body."""

    if response.status_code != status:
        raise AssertionError(
            f"{label}: expected HTTP {status}, got {response.status_code}: "
            f"{response.text[:800]}"
        )
    return response.json() if response.content else None


def create_job(client, headers, title: str, required_skills, description=None):
    """Publish a real job and return its public representation."""

    response = client.post(
        "/employer/jobs",
        headers=headers,
        json={
            "title": title,
            "description": description or f"P9 job: {title}",
            "required_skills": list(required_skills),
        },
    )
    return expect(response, 201, f"create job {title!r}")


def apply_to_job(client, headers, job_id):
    """Submit one real application."""

    response = client.post(
        f"/candidate/jobs/{job_id}/applications",
        headers=headers,
        json={},
    )
    return expect(response, 201, f"apply to job {job_id}")


def set_status(client, headers, application_id, version: int, status: str):
    """Move an application to one of the four explicit statuses."""

    response = client.patch(
        f"/employer/applications/{application_id}/status",
        headers=headers,
        json={"version": version, "status": status},
    )
    return expect(response, 200, f"set application {application_id} to {status}")


def create_slot(client, headers, starts_at: datetime):
    """Create a real 30-minute availability slot."""

    response = client.post(
        "/employer/interview-slots",
        headers=headers,
        json={"starts_at": starts_at.isoformat()},
    )
    return expect(response, 201, "create interview slot")


def available_slots(client, headers, application_id):
    """Read the candidate-visible availability set."""

    response = client.get(
        f"/candidate/applications/{application_id}/slots",
        headers=headers,
    )
    return expect(response, 200, f"available slots for {application_id}")


def dashboard(client, headers):
    """Read the candidate recommendation dashboard."""

    response = client.get("/candidate/jobs", headers=headers)
    return expect(response, 200, "candidate dashboard")


def applicant_list(client, headers, job_id):
    """Read the employer applicant list for one job."""

    response = client.get(f"/employer/jobs/{job_id}/applications", headers=headers)
    return expect(response, 200, f"applicant list for {job_id}")


def future_at(days: int = 3, hour: int = 9, minute: int = 0) -> datetime:
    """Return a fixed, clearly-future UTC wall-clock instant.

    The offset is applied to the real clock because the application compares
    slots with ``utc_now()``; the result is rounded to a whole minute so two
    equivalent workflows can use *exactly* the same timestamp.
    """

    base = datetime.now(timezone.utc) + timedelta(days=days)
    return base.replace(hour=hour, minute=minute, second=0, microsecond=0)


def slot_signature(rows):
    """Canonical comparable form of an availability response."""

    return [(row["starts_at"], row["ends_at"]) for row in rows]


def slot_ids(rows):
    return [row["id"] for row in rows]


def dashboard_signature(rows):
    """Score/order/applied fields that a matching metamorphism may not change."""

    return [(row["id"], row["match_score"], row["applied"]) for row in rows]


def score_map(rows):
    return {row["id"]: row["match_score"] for row in rows}


def relative_order(rows, job_ids):
    """Keep only the original jobs, preserving their order in the new list."""

    wanted = {str(job_id) for job_id in job_ids}
    return [row["id"] for row in rows if row["id"] in wanted]


def applicant_signature(rows):
    return [(row["candidate_id"], row["match_score"]) for row in rows]


def assert_dashboard_unchanged(before, after, label: str) -> None:
    """Metamorphic oracle for M3/M4/I4 dashboards."""

    if dashboard_signature(before) != dashboard_signature(after):
        raise AssertionError(
            f"{label}: recommendation signature changed "
            f"(before={dashboard_signature(before)!r}, "
            f"after={dashboard_signature(after)!r})"
        )


def assert_applicant_lists_unchanged(before, after, label: str) -> None:
    if applicant_signature(before) != applicant_signature(after):
        raise AssertionError(
            f"{label}: employer applicant signature changed "
            f"(before={applicant_signature(before)!r}, "
            f"after={applicant_signature(after)!r})"
        )


def assert_slots_unchanged(before, after, label: str) -> None:
    """Metamorphic oracle for M1/M2/M5 availability sets."""

    if slot_signature(before) != slot_signature(after):
        raise AssertionError(
            f"{label}: availability signature changed "
            f"(before={slot_signature(before)!r}, "
            f"after={slot_signature(after)!r})"
        )


def assert_relative_order_unchanged(before, after, job_ids, label: str) -> None:
    before_order = relative_order(before, job_ids)
    after_order = relative_order(after, job_ids)
    if after_order != before_order:
        raise AssertionError(
            f"{label}: relative recommendation order changed "
            f"(before={before_order!r}, after={after_order!r})"
        )


# ---------------------------------------------------------------------------
# Read-only database oracles
# ---------------------------------------------------------------------------

_COUNTABLE_TABLES = frozenset({"booking", "application", "interview_slot", "job"})


def _scalar(engine, sql: str, params=None):
    with engine.connect() as connection:
        return connection.execute(text(sql), params or {}).scalar_one()


def _rows(engine, sql: str, params=None):
    with engine.connect() as connection:
        return connection.execute(text(sql), params or {}).mappings().all()


def count_rows(engine, table: str) -> int:
    if table not in _COUNTABLE_TABLES:
        raise ValueError(f"refusing to count unexpected table {table!r}")
    return int(_scalar(engine, f'SELECT count(*) FROM "{table}"'))


def booking_rows_for_slot(engine, slot_id):
    """All persisted bookings for one slot, oldest first."""

    return _rows(
        engine,
        "SELECT id, application_id, slot_id FROM booking "
        "WHERE slot_id = :slot_id ORDER BY created_at, id",
        {"slot_id": slot_id},
    )


def assert_single_booking(engine, slot_id):
    """FP-SCHED-3 oracle: exactly one booking row for a slot.

    This is deliberately a read-only query executed through a separate
    connection.  It does not call ``book`` or any production helper to decide
    what the answer should be.
    """

    rows = booking_rows_for_slot(engine, slot_id)
    if len(rows) != 1:
        raise AssertionError(
            f"defense-layer violation: slot {slot_id} has {len(rows)} "
            "booking rows, expected exactly 1"
        )
    return rows[0]


def application_count_for_pair(engine, candidate_id, job_id) -> int:
    """FP-CAN-3 oracle: at most one application for a candidate/job pair."""

    return int(
        _scalar(
            engine,
            "SELECT count(*) FROM application "
            "WHERE candidate_id = :candidate_id AND job_id = :job_id",
            {"candidate_id": candidate_id, "job_id": job_id},
        )
    )


def assert_single_application(engine, candidate_id, job_id) -> None:
    count = application_count_for_pair(engine, candidate_id, job_id)
    if count != 1:
        raise AssertionError(
            f"defense-layer violation: candidate {candidate_id} has {count} "
            f"applications for job {job_id}, expected exactly 1"
        )


def job_is_deleted(engine, job_id) -> bool:
    value = _scalar(
        engine,
        "SELECT is_deleted FROM job WHERE id = :job_id",
        {"job_id": job_id},
    )
    return bool(value)


def slot_rows_for_job(engine, job_id):
    return _rows(
        engine,
        "SELECT id, employer_id, job_id, starts_at, ends_at "
        "FROM interview_slot WHERE job_id = :job_id ORDER BY starts_at, id",
        {"job_id": job_id},
    )


def drop_booking_slot_unique_constraint(engine) -> None:
    """Remove the physical slot uniqueness constraint in this throwaway DB.

    Used only by the I1 self-check, never by a normal defence-layer comparison.
    PostgreSQL always enforces the constraint while it exists, so this is the
    only faithful way to construct the condition "the database has no unique
    constraint" that the self-check needs.
    """

    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE booking DROP CONSTRAINT uq_booking_slot"))


def restore_booking_slot_unique_constraint(engine, slot_id) -> None:
    """Delete any duplicate rows and put the unique constraint back."""

    with engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM booking WHERE slot_id = :slot_id AND id <> ("
                "  SELECT id FROM booking WHERE slot_id = :slot_id "
                "  ORDER BY created_at, id LIMIT 1"
                ")"
            ),
            {"slot_id": slot_id},
        )
        connection.execute(
            text("ALTER TABLE booking ADD CONSTRAINT uq_booking_slot UNIQUE (slot_id)")
        )


def drop_application_unique_constraint(engine) -> None:
    """Remove the candidate/job uniqueness constraint in the throwaway DB."""

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE application DROP CONSTRAINT uq_application_candidate_job")
        )


def restore_application_unique_constraint(engine, candidate_id, job_id) -> None:
    """Delete duplicate applications for the pair and restore the constraint."""

    with engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM application "
                "WHERE candidate_id = :candidate_id AND job_id = :job_id "
                "AND id <> ("
                "  SELECT id FROM application "
                "  WHERE candidate_id = :candidate_id AND job_id = :job_id "
                "  ORDER BY created_at, id LIMIT 1"
                ")"
            ),
            {"candidate_id": candidate_id, "job_id": job_id},
        )
        connection.execute(
            text(
                "ALTER TABLE application ADD CONSTRAINT "
                "uq_application_candidate_job UNIQUE (candidate_id, job_id)"
            )
        )


# ---------------------------------------------------------------------------
# Fast registration for larger synthetic fixtures
# ---------------------------------------------------------------------------


def install_fast_registration(monkeypatch):
    """Replace only the expensive KDF; the real HTTP registration path runs.

    Copied from ``tests/advanced/differential`` and kept local to P9 so the
    shared ``conftest.py`` stays untouched.  Matching/booking tests never
    verify a password, so Argon2 would only make fixtures slow.
    """

    from app.users import service as users_service

    monkeypatch.setattr(
        users_service,
        "hash_password",
        lambda password: "advanced-fast::" + password,
    )


# ---------------------------------------------------------------------------
# Controlled program variants
# ---------------------------------------------------------------------------


def _sql_shape(statement) -> str:
    try:
        return str(statement)
    except Exception:  # pragma: no cover - defensive only
        return ""


def _is_slot_booking_lookup(statement) -> bool:
    """The precheck and IntegrityError recovery query in ``candidate.book``."""

    sql = _sql_shape(statement)
    return "FROM booking" in sql and "booking.slot_id" in sql


def _is_application_duplicate_lookup(statement) -> bool:
    """The duplicate-application precheck and recovery query in ``apply``."""

    sql = _sql_shape(statement)
    return (
        "FROM application" in sql
        and "application.candidate_id" in sql
        and "application.job_id" in sql
    )


def _is_job_dependency_lookup(statement) -> bool:
    """The two dependency probes in ``employer.delete_job``."""

    sql = _sql_shape(statement)
    return ("FROM application" in sql and "application.job_id" in sql) or (
        "FROM interview_slot" in sql and "interview_slot.job_id" in sql
    )


class _EmptyScalarResult:
    """Stand-in for ``session.exec(...).first()`` returning no row."""

    def first(self):
        return None

    def all(self):
        return []

    def __iter__(self):
        return iter(())


def _install_skip_first(monkeypatch, predicate):
    """Answer the first matching SELECT with an empty result, then pass through.

    The same SQL shape is used by the precheck and by the recovery branch after
    an ``IntegrityError``.  Skipping only the first occurrence targets the
    application-layer precheck while leaving the recovery query intact, which
    is what lets the test observe the database constraint's own answer.
    """

    real_exec = Session.exec
    state = {"matched": 0, "skipped": 0}

    def exec_(self, statement, *args, **kwargs):
        if predicate(statement):
            state["matched"] += 1
            if state["matched"] == 1:
                state["skipped"] += 1
                return _EmptyScalarResult()
        return real_exec(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "exec", exec_)
    return state


def install_skip_first_slot_precheck(monkeypatch):
    """I1: disable the ``Slot already booked`` application-layer precheck."""

    return _install_skip_first(monkeypatch, _is_slot_booking_lookup)


def install_skip_first_application_precheck(monkeypatch):
    """I3: disable the ``Already applied`` application-layer precheck."""

    return _install_skip_first(monkeypatch, _is_application_duplicate_lookup)


def install_skip_job_dependency_checks(monkeypatch):
    """I5: make both dependency probes in ``delete_job`` report "no rows"."""

    real_exec = Session.exec
    state = {"skipped": 0}

    def exec_(self, statement, *args, **kwargs):
        if _is_job_dependency_lookup(statement):
            state["skipped"] += 1
            return _EmptyScalarResult()
        return real_exec(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "exec", exec_)
    return state


def install_no_row_locks(monkeypatch):
    """I2: turn every ``SELECT ... FOR UPDATE`` into an ordinary SELECT."""

    state = {"calls": 0}

    def unlocked(self, *args, **kwargs):
        state["calls"] += 1
        return self

    monkeypatch.setattr(Select, "with_for_update", unlocked)
    return state


def install_reversed_normalize(monkeypatch):
    """I4: return the normalized skills in reverse order.

    ``match_score`` consumes a set, so a correct implementation must not care
    about the order of the list.
    """

    from app.employer import matching

    original = matching.normalize_skills
    state = {"calls": 0, "function": None}

    def reversed_normalize(skills):
        state["calls"] += 1
        return list(reversed(original(skills)))

    state["function"] = reversed_normalize
    monkeypatch.setattr(matching, "normalize_skills", reversed_normalize)
    return state


def install_commit_recorder(monkeypatch):
    """Record (but re-raise) unique violations observed by ``Session.commit``.

    Evidence is limited to the constraint name; SQL text and parameter values
    never reach the artefact.
    """

    real_commit = Session.commit
    events = []

    def commit(self):
        try:
            return real_commit(self)
        except IntegrityError as error:
            diag = getattr(getattr(error, "orig", None), "diag", None)
            events.append(
                {
                    "type": type(error).__name__,
                    "constraint": getattr(diag, "constraint_name", None),
                }
            )
            raise

    monkeypatch.setattr(Session, "commit", commit)
    return events


class _GatedFirst:
    """Execute ``first()``, then wait until both requests observed the state."""

    def __init__(self, result, gate):
        self._result = result
        self._gate = gate

    def first(self):
        value = self._result.first()
        self._gate.after_query(value)
        return value

    def __getattr__(self, name):
        return getattr(self._result, name)


#: Per-request marker used by the precheck gate.  Starlette reuses worker
#: threads across requests, so a plain ``threading.local`` flag would leak from
#: one round to the next; ``BookingTimeline`` resets this marker at the start of
#: every real ``book`` call.
_REQUEST_STATE = threading.local()


def install_slot_precheck_gate(monkeypatch, gate):
    """Synchronise the two booking requests after their slot precheck query.

    This is instrumentation, not a business variant: it only makes the race
    deterministic.  Both requests run the real precheck, both must observe the
    slot as free, and only then may either insert.  The loser is therefore
    forced through the database unique constraint instead of taking the
    application-layer precheck shortcut.
    """

    real_exec = Session.exec
    state = {"gated": 0}

    def exec_(self, statement, *args, **kwargs):
        result = real_exec(self, statement, *args, **kwargs)
        if _is_slot_booking_lookup(statement) and not getattr(
            _REQUEST_STATE, "slot_precheck_gated", False
        ):
            _REQUEST_STATE.slot_precheck_gated = True
            state["gated"] += 1
            return _GatedFirst(result, gate)
        return result

    monkeypatch.setattr(Session, "exec", exec_)
    return state


class ConcurrencyGate:
    """A two-party barrier that records who arrived and when."""

    def __init__(self):
        self.barrier = threading.Barrier(2)
        self.arrivals = []
        self._lock = threading.Lock()

    def wait(self, label: str):
        with self._lock:
            self.arrivals.append(
                {
                    "label": label,
                    "thread": threading.current_thread().name,
                    "thread_id": threading.get_ident(),
                    "at": time.perf_counter(),
                }
            )
        try:
            self.barrier.wait(timeout=30)
        except threading.BrokenBarrierError as error:
            raise AssertionError(
                f"concurrency barrier broke before both requests arrived ({label})"
            ) from error


class BookingTimeline:
    """Wrap ``candidate.service.book`` to timestamp entry and exit.

    The wrapper waits on a fresh barrier *inside* ``book`` before calling the
    real function, so the two intervals necessarily overlap: both entries are
    recorded before the barrier can release, and both exits happen after it.
    The real service function is captured by the test before any monkeypatch.
    """

    def __init__(self):
        self.gate = None
        self.entries = []
        self.exits = []
        self._lock = threading.Lock()

    def reset(self):
        self.entries.clear()
        self.exits.clear()
        self.gate = ConcurrencyGate()

    def wrap(self, real_book):
        def wrapped(session, user, application_id, slot_id):
            _REQUEST_STATE.slot_precheck_gated = False
            entry = {
                "at": time.perf_counter(),
                "thread": threading.current_thread().name,
                "thread_id": threading.get_ident(),
                "session": id(session),
            }
            with self._lock:
                self.entries.append(entry)
            if self.gate is None:  # pragma: no cover - test sets it first
                raise AssertionError("booking timeline gate is not configured")
            self.gate.wait("inside book")
            try:
                return real_book(session, user, application_id, slot_id)
            finally:
                with self._lock:
                    self.exits.append(
                        {
                            "at": time.perf_counter(),
                            "thread": entry["thread"],
                            "thread_id": entry["thread_id"],
                            "session": entry["session"],
                        }
                    )

        return wrapped


class PrecheckGate:
    """A second barrier placed immediately after the slot precheck query."""

    def __init__(self):
        self.barrier = threading.Barrier(2)
        self.observations = []
        self._lock = threading.Lock()

    def reset(self):
        self.observations.clear()
        self.barrier = threading.Barrier(2)

    def after_query(self, value):
        with self._lock:
            self.observations.append(
                {
                    "is_none": value is None,
                    "thread": threading.current_thread().name,
                    "thread_id": threading.get_ident(),
                }
            )
        try:
            self.barrier.wait(timeout=30)
        except threading.BrokenBarrierError as error:
            raise AssertionError(
                "slot-precheck barrier broke before both requests observed the slot"
            ) from error
