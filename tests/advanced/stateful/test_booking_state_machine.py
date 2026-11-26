"""P2: a Hypothesis state machine over the real booking lifecycle.

Every step performs one real HTTP call against the real FastAPI application on a
disposable PostgreSQL database, compares the response with an independent
in-memory model (:mod:`stateful.model`), and then re-checks the invariants below
against the database and the candidate/employer endpoints.  Each example is
written to ``$ADVANCED_OUT/stateful/traces/<number>.json`` for the P3 LTL
checker.

The eight operations from the task brief are the ``_do_*`` methods below; the
two bundles from the brief are the model's ``applications`` and ``slots``
collections:

==========================================  =========================
operation                                   requirement clause
==========================================  =========================
``apply``                                   FP-CAN-3
``set_status`` / ``set_status_wrong_owner`` FP-EMP-3
``create_slot`` / ``delete_slot``           FP-SCHED-1
``book`` / ``book_foreign``                 FP-SCHED-2, FP-SCHED-3
``delete_job``                              FP-EMP-2
==========================================  =========================

One dispatcher rule and one operation per step
----------------------------------------------
Hypothesis calls at most one rule per step.  Its rule sampler is deliberately
biased (``FeatureFlags`` swarm testing plus the integer-shrinking bias in
``sampled_from``), and with eight rules it handed roughly half of an example's
steps to a single cheap rule, truncating the traces before the booking
lifecycle was reached.  ``perform`` therefore draws a ``hypothesis.strategies.
randoms()`` instance - the documented way to obtain reproducibility-controlled
randomness inside a test - and uses it to pick uniformly among the *applicable*
operations.  The draw is still part of the Hypothesis data stream, so
``derandomize=True`` keeps runs byte-for-byte reproducible and shrinking still
works.

Invariants checked after every step:

1. a slot has at most one booking and an application has at most one booking
   (counted directly in SQL, not through the API);
2. a booked slot is not offered to any candidate as available;
3. every booking was created while its application was ``Interviewing``, and a
   later status change keeps the booking;
4. every row of the employer's applicant list carries the match score of an
   independent FP-MATCH-1 oracle, and the list is ordered as FP-MATCH-1 says;
5. a rejected operation changes no row count in any application table.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from functools import partial
import os
import random
import uuid

from hypothesis import HealthCheck, settings, strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    invariant,
    rule,
    run_state_machine_as_test,
)

from stateful.harness import Harness, Recorder, artefact_dir, body_json
from stateful.model import (
    CANDIDATES,
    EMPLOYERS,
    INTERVIEWING,
    JOBS,
    SLOT_LENGTH,
    STATUSES,
)
from support.traces import Event


def _max_examples() -> int:
    """Read ``ADVANCED_MAX_EXAMPLES`` and keep the run bounded."""

    raw = os.environ.get("ADVANCED_MAX_EXAMPLES")
    if not raw:
        return 25
    try:
        value = int(raw)
    except ValueError:
        return 25
    return min(max(value, 1), 100)


SETTINGS = settings(
    max_examples=_max_examples(),
    stateful_step_count=12,
    deadline=None,
    derandomize=True,
    database=None,
    suppress_health_check=[HealthCheck.too_slow],
)

#: Per-example execution caps.  They stop a 12-step trace from spending most of
#: its budget on the cheap negative operations (``delete_job`` is a one-line
#: 404 as soon as the posting is gone) and keep every trace diverse.
RULE_LIMITS: dict[str, int | None] = {
    "apply": 4,
    "set_status": None,
    "set_status_wrong_owner": 2,
    "create_slot": None,
    "book": None,
    "book_foreign": 2,
    "delete_slot": None,
    "delete_job": 2,
}

#: FP-EMP-3 allows all four statuses; ``Interviewing`` is weighted up because it
#: is the only status that unlocks the FP-SCHED-2 booking path.  A uniform draw
#: left an application ``Interviewing`` for barely one step, so a 12-step trace
#: almost never reached a booking, let alone a status change afterwards.
STATUS_DRAW = (
    "Interviewing",
    "Interviewing",
    "Interviewing",
    "Pending",
    "Rejected",
    "Accepted",
)

#: Full documented slot grid: 1..5 days ahead, 0..47 half-hours.  A fresh slot is
#: almost never colliding on this grid, so one creation in three reuses the start
#: of an existing slot on purpose; that keeps the FP-SCHED-1 overlap branch in
#: every longer trace while still leaving plenty of bookable windows.
SLOT_DAYS = range(1, 6)
SLOT_HALF_HOURS = range(0, 48)
SLOT_REUSE_PROBABILITY = 0.35


def _parse_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp returned by the API into an aware datetime."""

    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None, f"API returned a naive timestamp: {value!r}"
    return parsed.astimezone(timezone.utc)


def _as_uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class BookingStateMachine(RuleBasedStateMachine):
    """Random operation sequences with a model prediction before every request."""

    def __init__(self, harness: Harness, recorder: Recorder) -> None:
        super().__init__()
        self.harness = harness
        self.recorder = recorder
        self.world = harness.new_world()
        self.step = 0
        self.events: list[Event] = []
        self.operations: list[str] = []
        self._op_counts: Counter[str] = Counter()
        self._pending: tuple[str, bool | None] | None = None
        self._before = harness.counts()
        self._new_booking: str | None = None
        self._outsider_calls = 0

    # -- scheduling ----------------------------------------------------

    @rule(seed=st.integers(min_value=0, max_value=2**32 - 1))
    def perform(self, seed: int) -> None:
        """Run one uniformly chosen applicable operation.

        The seed comes from the Hypothesis data stream, so ``derandomize=True``
        and shrinking keep working; a :class:`random.Random` built from it gives
        an unbiased choice.  ``hypothesis.strategies.randoms()`` is not used
        because under ``derandomize`` it degenerates into an all-zero pick for
        the smallest examples, which repeatedly selected one operation.
        """

        rng = self._rng(seed)
        candidates = self._applicable()
        assert candidates, (
            "no operation is applicable: the state machine cannot make progress"
        )
        action = rng.choice(candidates)
        getattr(self, f"_do_{action}")(rng)

    def _rng(self, seed: int) -> random.Random:
        """Mix the drawn seed with the step number before seeding.

        Hypothesis's smallest example draws ``seed = 0`` for every step; without
        the step in the mix a whole example would repeat one operation.  Mixing
        the step keeps the sequence varied while remaining a pure function of
        the data stream (str seeding is not used: ``random.Random(str)`` is
        stable, but the integer mix needs no hashing guarantee at all).
        """

        return random.Random((seed * 1_000_003 + self.step * 79_999) % 2**32)

    def _applicable(self) -> list[str]:
        """Operations whose preconditions currently hold, plus scheduling weights.

        The list may contain an operation more than once: that is the schedule's
        weight, not a semantic difference.  A cold scenario starts with no
        application, no slot and nothing ``Interviewing``, and a 12-step trace
        would spend most of its budget before FP-SCHED-2 became reachable at
        all.  The weights therefore bootstrap the missing state and favour a
        booking exactly when one is possible:

        * ``apply`` x3 while no application exists;
        * ``create_slot`` x3 while no slot exists;
        * ``set_status`` x3 while no application is ``Interviewing``;
        * ``book`` x3 while an eligible application and a free slot of its
          employer exist.

        ``delete_slot`` additionally keeps one slot alive for the same reason.
        Nothing here changes what the model predicts or what is asserted.
        """

        live_slots = self._live_slots()
        applications = list(self.world.applications)
        available = {
            "apply": True,
            "set_status": bool(applications),
            "set_status_wrong_owner": bool(applications),
            "create_slot": True,
            "book": bool(applications) and bool(live_slots),
            "book_foreign": bool(applications),
            "delete_slot": len(live_slots) > 1,
            "delete_job": sum(
                not posting.deleted for posting in self.world.jobs.values()
            )
            > 1,
        }
        interviewing = any(
            record.status == INTERVIEWING
            for record in self.world.applications.values()
        )
        booking_ready = self._booking_possible()
        weighted: list[str] = []
        for action in sorted(available):
            if not available[action] or not self._room(action):
                continue
            weight = 1
            if action == "apply" and not applications:
                weight = 3
            elif action == "create_slot" and not live_slots:
                weight = 3
            elif action == "set_status" and applications and not interviewing:
                weight = 3
            elif action == "book" and booking_ready:
                weight = 3
            weighted.extend([action] * weight)
        return weighted

    def _booking_possible(self) -> bool:
        """Whether some eligible application could book some free slot now."""

        for record in self.world.eligible_applications():
            posting = self.world.jobs[record.job]
            for window in self.world.slots.values():
                if window.deleted or window.booking is not None:
                    continue
                if window.employer != posting.employer:
                    continue
                if window.job is not None and window.job != posting.alias:
                    continue
                return True
        return False

    def _room(self, action: str) -> bool:
        limit = RULE_LIMITS[action]
        return limit is None or self._op_counts[action] < limit

    def _live_slots(self) -> list[str]:
        return [
            alias for alias, slot in self.world.slots.items() if not slot.deleted
        ]

    # -- bookkeeping ---------------------------------------------------

    def _begin(self, action: str) -> None:
        self.step += 1
        self._op_counts[action] += 1
        self._pending = (action, None)
        self._new_booking = None

    def _expect(self, prediction, response, summary: str) -> None:
        """Compare the predicted status/message with the real response."""

        action = prediction.action
        code = response.status_code
        self.recorder.count_outcome(action, code, prediction.reason)
        self.operations.append(
            f"{summary} -> {code} (model predicted {prediction.code})"
        )
        if code != prediction.code:
            self._pending = (action, False)
            raise AssertionError(
                f"{action}: model predicted HTTP {prediction.code}, "
                f"application answered HTTP {code} with {body_json(response)!r}\n"
                + self._operation_log()
            )
        self._pending = (action, prediction.ok)
        if prediction.detail is not None:
            detail = str(body_json(response).get("detail", ""))
            if prediction.detail.lower() not in detail.lower():
                self._pending = (action, False)
                raise AssertionError(
                    f"{action}: expected the documented message "
                    f"{prediction.detail!r}, application answered {detail!r}\n"
                    + self._operation_log()
                )

    def _operation_log(self) -> str:
        return "operations:\n  " + "\n  ".join(self.operations)

    def _next_candidate(self, owner: str) -> str:
        others = [alias for alias in sorted(CANDIDATES) if alias != owner]
        return others[self._outsider_calls % len(others)]

    def _pick_outsider(self, employer: str, candidate: str):
        """Alternate between "another employer" and "a candidate" as the actor."""

        self._outsider_calls += 1
        if self._outsider_calls % 2:
            return self.world.other_employer(employer), "employer"
        return self._next_candidate(candidate), "candidate"

    # -- operations: FP-CAN-3 ------------------------------------------

    def _do_apply(self, rng) -> None:
        """FP-CAN-3: apply once; a duplicate is a conflict without a new row."""

        self._begin("apply")
        candidate = rng.choice(sorted(CANDIDATES))
        job = self._pick_job(rng)
        prediction = self.world.predict_apply(candidate, job)
        response = self.harness.apply(candidate, self.world.jobs[job].job_id)
        self._expect(prediction, response, f"apply({candidate}, {job})")
        if prediction.code != 201:
            return
        body = body_json(response)
        assert body["status"] == "Pending", (
            "apply: FP-CAN-3 requires a new application to be Pending, "
            f"got {body['status']!r}"
        )
        assert int(body["version"]) == 1, (
            f"apply: a new application starts at version 1, got {body['version']!r}"
        )
        self.world.bind_application(prediction.created, _as_uuid(body["application_id"]))

    def _pick_job(self, rng) -> str:
        """Prefer a live posting, but still hit the deleted-posting path."""

        live = [
            alias for alias, posting in self.world.jobs.items() if not posting.deleted
        ]
        if live and rng.random() < 0.75:
            return rng.choice(live)
        return rng.choice(sorted(JOBS))

    # -- operations: FP-EMP-3 ------------------------------------------

    def _do_set_status(self, rng) -> None:
        """FP-EMP-3: the owning employer moves an application between statuses."""

        self._begin("set_status")
        application = rng.choice(sorted(self.world.applications))
        status = rng.choice(STATUS_DRAW)
        record = self.world.applications[application]
        employer = self.world.employer_of_application(application)
        version = record.version
        prediction = self.world.predict_set_status(application, status)
        response = self.harness.set_status(
            employer, record.application_id, version, status
        )
        self._expect(prediction, response, f"set_status({application}, {status})")
        self.recorder.count_reason(f"set_status_to:{status}")
        body = body_json(response)
        assert body["status"] == status, (
            f"set_status: requested {status!r}, application reports "
            f"{body['status']!r}"
        )
        assert int(body["version"]) == record.version, (
            f"set_status: expected version {record.version}, "
            f"application reports {body['version']!r}"
        )

    def _do_set_status_wrong_owner(self, rng) -> None:
        """FP-EMP-3: another employer and a candidate are both refused."""

        self._begin("set_status_wrong_owner")
        application = rng.choice(sorted(self.world.applications))
        record = self.world.applications[application]
        employer = self.world.employer_of_application(application)
        actor, role = self._pick_outsider(employer, record.candidate)
        prediction = self.world.predict_set_status_as_outsider(
            application, actor, role
        )
        response = self.harness.set_status(
            actor, record.application_id, record.version, STATUSES[0]
        )
        self._expect(
            prediction,
            response,
            f"set_status_wrong_owner({application}, actor={actor}/{role})",
        )

    # -- operations: FP-SCHED-1 ----------------------------------------

    def _do_create_slot(self, rng) -> None:
        """FP-SCHED-1: create a future 30-minute slot unless it overlaps."""

        self._begin("create_slot")
        employer = rng.choice(sorted(EMPLOYERS))
        starts_at, label = self._pick_slot_start(rng, employer)
        prediction = self.world.predict_create_slot(employer, starts_at)
        response = self.harness.create_slot(employer, starts_at)
        self._expect(prediction, response, f"create_slot({employer}, {label})")
        if prediction.code != 201:
            return
        body = body_json(response)
        actual_start = _parse_timestamp(body["starts_at"])
        actual_end = _parse_timestamp(body["ends_at"])
        assert actual_start == starts_at, (
            f"create_slot: asked for {starts_at.isoformat()}, "
            f"application stored {actual_start.isoformat()}"
        )
        assert actual_end - actual_start == SLOT_LENGTH, (
            "create_slot: FP-SCHED-1 requires a 30-minute slot, got "
            f"{actual_end - actual_start}"
        )
        self.world.bind_slot(prediction.created, _as_uuid(body["id"]))

    def _pick_slot_start(self, rng, employer: str):
        """Return ``(starts_at, label)`` for the next creation attempt."""

        live = [
            slot
            for slot in self.world.slots.values()
            if slot.employer == employer and not slot.deleted
        ]
        if live and rng.random() < SLOT_REUSE_PROBABILITY:
            window = rng.choice(live)
            return window.starts_at, f"reusing the start of {window.alias}"
        offset_days = rng.choice(list(SLOT_DAYS))
        half_hour = rng.choice(list(SLOT_HALF_HOURS))
        return (
            self.world.slot_start(offset_days, half_hour),
            f"+{offset_days}d, half_hour={half_hour}",
        )

    def _do_delete_slot(self, rng) -> None:
        """FP-SCHED-1: a free slot can be deleted, a booked one cannot."""

        self._begin("delete_slot")
        live = self._live_slots()
        booked = [
            alias for alias in live if self.world.slots[alias].booking is not None
        ]
        # Half of the attempts aim at a booked slot: FP-SCHED-1 forbids deleting
        # it, and that conflict is otherwise too rare to appear in a trace.
        slot = (
            rng.choice(booked)
            if booked and rng.random() < 0.5
            else rng.choice(live)
        )
        window = self.world.slots[slot]
        prediction = self.world.predict_delete_slot(slot)
        response = self.harness.delete_slot(window.employer, window.slot_id)
        self._expect(
            prediction, response, f"delete_slot({slot}, {window.employer})"
        )

    # -- operations: FP-SCHED-2 / FP-SCHED-3 ---------------------------

    def _do_book(self, rng) -> None:
        """FP-SCHED-2: book when all five conditions hold, conflict otherwise."""

        self._begin("book")
        application, slot = self._pick_booking_pair(rng)
        record = self.world.applications[application]
        window = self.world.slots[slot]
        prediction = self.world.predict_book(application, slot)
        response = self.harness.book(
            record.candidate, record.application_id, window.slot_id
        )
        self._expect(prediction, response, f"book({application}, {slot})")
        if prediction.code != 201:
            return
        self._new_booking = application
        body = body_json(response)
        assert _as_uuid(body["slot_id"]) == window.slot_id, (
            f"book: expected slot {slot}, application reports {body['slot_id']!r}"
        )
        assert (
            _parse_timestamp(body["ends_at"]) - _parse_timestamp(body["starts_at"])
            == SLOT_LENGTH
        ), "book: the booked window must be the 30-minute slot it names"

    def _pick_booking_pair(self, rng):
        """Pick ``(application, slot)`` mixing the success path with conflicts.

        A purely uniform choice spends nearly every attempt on a conflict: at
        most two of the six applications are ``Interviewing``, and half of the
        slots belong to the other employer.  Half of the attempts therefore
        start from an eligible application and, when it exists, take a slot of
        that application's employer; the rest stay uniform, which keeps the
        "not Interviewing", "already booked" and "slot belongs to another
        employer" conflicts in the trace.
        """

        eligible = [
            record.alias for record in self.world.eligible_applications()
        ]
        if eligible and rng.random() < 0.9:
            application = rng.choice(eligible)
        else:
            application = rng.choice(sorted(self.world.applications))
        employer = self.world.employer_of_application(application)
        live = self._live_slots()
        same_employer = [
            alias
            for alias in live
            if self.world.slots[alias].employer == employer
        ]
        if same_employer and rng.random() < 0.7:
            return application, rng.choice(same_employer)
        return application, rng.choice(live)

    def _do_book_foreign(self, rng) -> None:
        """FP-SCHED-2/FP-SEC-1: booking under someone else's identity is refused."""

        self._begin("book_foreign")
        application = rng.choice(sorted(self.world.applications))
        record = self.world.applications[application]
        actor = self._next_candidate(record.candidate)
        prediction = self.world.predict_book_as_outsider(application, actor)
        # The ownership check runs before the slot is looked up, so an unknown
        # slot is enough when the scenario has not created one yet.
        live = self._live_slots()
        slot_id = (
            self.world.slots[rng.choice(live)].slot_id if live else uuid.uuid4()
        )
        response = self.harness.book(actor, record.application_id, slot_id)
        self._expect(
            prediction, response, f"book_foreign({application}, as {actor})"
        )

    # -- operations: FP-EMP-2 ------------------------------------------

    def _do_delete_job(self, rng) -> None:
        """FP-EMP-2: delete a posting only when it has no dependent records."""

        self._begin("delete_job")
        job = rng.choice(sorted(JOBS))
        posting = self.world.jobs[job]
        prediction = self.world.predict_delete_job(job)
        response = self.harness.delete_job(posting.employer, posting.job_id)
        self._expect(prediction, response, f"delete_job({job}, {posting.employer})")

    # -- invariants -----------------------------------------------------

    @invariant()
    def invariants_hold(self) -> None:
        """Re-check every invariant against the database and the API."""

        if self._pending is None:  # before the first rule
            return
        assert self._pending[1] is not None, "step ended without an expectation"
        try:
            state = self._collect()
            self._verify(state)
            self._append_event(state)
        except AssertionError as error:
            action = self._pending[0]
            self._pending = (action, False)
            raise AssertionError(
                f"after step {self.step} ({action})\n{error}\n"
                + self._operation_log()
            ) from error

    def _collect(self) -> dict:
        """Fetch the authoritative view: SQL rows plus the read endpoints."""

        state = self.harness.snapshot()
        state["applicants"] = {}
        state["available"] = {}
        for alias, posting in self.world.jobs.items():
            response = self.harness.applicants(posting.employer, posting.job_id)
            if posting.deleted:
                assert response.status_code == 404, (
                    f"FP-EMP-2: deleted posting {alias} still answers the "
                    f"applicant list with {response.status_code}"
                )
                continue
            assert response.status_code == 200, (
                f"applicant list for {alias} answered {response.status_code}: "
                f"{body_json(response)!r}"
            )
            state["applicants"][alias] = response.json()
        for application in self.world.eligible_applications():
            response = self.harness.available_slots(
                application.candidate, application.application_id
            )
            assert response.status_code == 200, (
                f"FP-SCHED-2: application {application.alias} is Interviewing "
                "and unbooked, but its slot list answered "
                f"{response.status_code}: {body_json(response)!r}"
            )
            state["available"][application.alias] = response.json()
        return state

    def _verify(self, state: dict) -> None:
        self._check_rows(state)
        self._check_model(state)
        self._check_bookings(state)
        self._check_availability(state)
        self._check_booking_origin(state)
        self._check_applicants(state)

    def _check_rows(self, state: dict) -> None:
        """Invariant 5: a rejected operation changes no application table."""

        if self._pending[1]:
            return
        changed = {
            name: (before, state["counts"][name])
            for name, before in self._before.items()
            if state["counts"][name] != before
        }
        assert not changed, (
            "invariant 5: a rejected operation must leave every table "
            f"unchanged, but {{table: (before, after)}} = {changed}"
        )

    def _check_model(self, state: dict) -> None:
        """The stored rows must be exactly the rows the model believes in."""

        expected_applications = {
            record.application_id: record
            for record in self.world.applications.values()
        }
        stored_applications = set(state["applications"])
        assert stored_applications == set(expected_applications), (
            "stored applications differ from the model: "
            f"database-only={sorted(map(str, stored_applications - set(expected_applications)))}, "
            f"model-only={sorted(map(str, set(expected_applications) - stored_applications))}"
        )
        for application_id, row in state["applications"].items():
            record = expected_applications[application_id]
            assert row["status"] == record.status, (
                f"stored status of {record.alias} is {row['status']!r}, "
                f"model has {record.status!r}"
            )
            assert row["version"] == record.version, (
                f"stored version of {record.alias} is {row['version']}, "
                f"model has {record.version}"
            )
            assert (
                row["candidate_id"]
                == self.world.candidates[record.candidate].user_id
            ), f"stored candidate of {record.alias} is not the modelled one"
            assert row["job_id"] == self.world.jobs[record.job].job_id, (
                f"stored posting of {record.alias} is not the modelled one"
            )

        expected_slots = {
            window.slot_id: window
            for window in self.world.slots.values()
            if not window.deleted
        }
        stored_slots = set(state["slots"])
        assert stored_slots == set(expected_slots), (
            "stored interview slots differ from the model: "
            f"database-only={sorted(map(str, stored_slots - set(expected_slots)))}, "
            f"model-only={sorted(map(str, set(expected_slots) - stored_slots))}"
        )
        for slot_id, row in state["slots"].items():
            window = expected_slots[slot_id]
            assert (
                row["employer_id"]
                == self.world.employers[window.employer].user_id
            ), f"stored owner of {window.alias} is not the modelled employer"
            expected_job = (
                None if window.job is None else self.world.jobs[window.job].job_id
            )
            assert row["job_id"] == expected_job, (
                f"stored job binding of {window.alias} is {row['job_id']}, "
                f"model has {expected_job}"
            )

        expected_bookings = {
            (record.application_id, self.world.slots[record.booking].slot_id)
            for record in self.world.applications.values()
            if record.booking is not None
        }
        assert set(state["bookings"]) == expected_bookings, (
            "stored bookings differ from the model: "
            f"database-only={sorted((str(a), str(s)) for a, s in set(state['bookings']) - expected_bookings)}, "
            f"model-only={sorted((str(a), str(s)) for a, s in expected_bookings - set(state['bookings']))}"
        )

        expected_deleted = {
            posting.job_id: posting.deleted
            for posting in self.world.jobs.values()
        }
        assert state["jobs"] == expected_deleted, (
            "stored postings differ from the model: "
            f"database={[str(key) for key in state['jobs']]}, "
            f"model={[str(key) for key in expected_deleted]}"
        )

    def _check_bookings(self, state: dict) -> None:
        """Invariant 1: at most one booking per slot and per application."""

        booked_applications = [pair[0] for pair in state["bookings"]]
        booked_slots = [pair[1] for pair in state["bookings"]]
        assert len(booked_applications) == len(set(booked_applications)), (
            "invariant 1: an application has more than one booking: "
            f"{len(booked_applications)} rows for "
            f"{len(set(booked_applications))} applications"
        )
        assert len(booked_slots) == len(set(booked_slots)), (
            "invariant 1: a slot has more than one booking: "
            f"{len(booked_slots)} rows for {len(set(booked_slots))} slots"
        )
        for application_id, slot_id in state["bookings"]:
            assert application_id in state["applications"], (
                "invariant 1: a booking points at an application that does not "
                f"exist ({application_id})"
            )
            assert slot_id in state["slots"], (
                "invariant 1: a booking points at a slot that does not exist "
                f"({slot_id})"
            )

    def _check_availability(self, state: dict) -> None:
        """Invariant 2: booked slots are never offered as available."""

        booked = {pair[1] for pair in state["bookings"]}
        for application, rows in state["available"].items():
            returned = set()
            for row in rows:
                slot_id = _as_uuid(row["id"])
                assert slot_id not in booked, (
                    "invariant 2: booked slot "
                    f"{self._slot_alias(slot_id)} is still offered to "
                    f"{application}"
                )
                returned.add(slot_id)
            predicted = {
                self.world.slots[alias].slot_id
                for alias in self.world.available_slots(application)
            }
            assert returned == predicted, (
                f"invariant 2: available slots for {application} differ from "
                "FP-SCHED-1/2: endpoint-only="
                f"{sorted(self._slot_alias(item) for item in returned - predicted)}, "
                "model-only="
                f"{sorted(self._slot_alias(item) for item in predicted - returned)}"
            )
            starts = [_parse_timestamp(row["starts_at"]) for row in rows]
            assert starts == sorted(starts), (
                f"available slots for {application} are not ordered by start: "
                f"{[item.isoformat() for item in starts]}"
            )

    def _check_booking_origin(self, state: dict) -> None:
        """Invariant 3: bookings start in Interviewing and survive status changes."""

        stored = set(state["bookings"])
        for record in self.world.applications.values():
            if record.booking is None:
                continue
            assert record.status_when_booked == INTERVIEWING, (
                f"invariant 3: booking of {record.alias} was created while the "
                f"application was {record.status_when_booked!r}, not "
                f"{INTERVIEWING!r}"
            )
            window = self.world.slots[record.booking]
            assert (record.application_id, window.slot_id) in stored, (
                f"invariant 3: the booking of {record.alias} to {window.alias} "
                f"disappeared (current status {record.status!r})"
            )

    def _check_applicants(self, state: dict) -> None:
        """Invariant 4: applicant rows and their match scores match the oracle."""

        for job, rows in state["applicants"].items():
            oracle = self.world.applicants_oracle(job)
            assert len(rows) == len(oracle), (
                f"invariant 4: applicant list of {job} has {len(rows)} rows, "
                f"the model has {len(oracle)}"
            )
            for actual, expected in zip(rows, oracle):
                alias = expected["application"]
                assert _as_uuid(actual["application_id"]) == expected["application_id"]
                assert _as_uuid(actual["candidate_id"]) == expected["candidate_id"]
                assert actual["display_name"] == expected["display_name"]
                assert actual["skills"] == expected["skills"], (
                    f"invariant 4: skills of {alias} are {actual['skills']!r}, "
                    f"FP-MATCH-1 normalisation gives {expected['skills']!r}"
                )
                assert actual["status"] == expected["status"], (
                    f"invariant 4: status of {alias} is {actual['status']!r}, "
                    f"the model has {expected['status']!r}"
                )
                assert actual["version"] == expected["version"]
                assert actual["match_score"] == expected["match_score"], (
                    f"invariant 4: match_score of {alias} on {job} is "
                    f"{actual['match_score']}, the independent FP-MATCH-1 "
                    f"oracle says {expected['match_score']}"
                )
                slot = expected["booking_slot"]
                if slot is None:
                    assert actual["booking"] is None, (
                        f"invariant 4: {alias} has no modelled booking but the "
                        f"applicant row reports {actual['booking']!r}"
                    )
                else:
                    assert actual["booking"] is not None, (
                        f"invariant 4: {alias} is booked to {slot} but the "
                        "applicant row reports no booking"
                    )
                    assert (
                        _as_uuid(actual["booking"]["slot_id"])
                        == self.world.slots[slot].slot_id
                    )

    # -- trace ----------------------------------------------------------

    def _append_event(self, state: dict) -> None:
        """Record the post-step state slice as atomic propositions."""

        action, ok = self._pending
        props: set[str] = set()
        for application_id, row in state["applications"].items():
            alias = self._application_alias(application_id)
            props.add(f"applied:{alias}")
            props.add(f"status:{alias}:{row['status']}")
        for slot_id in state["slots"]:
            props.add(f"slot:{self._slot_alias(slot_id)}")
        for application_id, slot_id in state["bookings"]:
            props.add(
                f"booked:{self._application_alias(application_id)}:"
                f"{self._slot_alias(slot_id)}"
            )
        for rows in state["available"].values():
            for row in rows:
                props.add(f"available:{self._slot_alias(_as_uuid(row['id']))}")
        if self._new_booking is not None:
            props.add(f"new_booking:{self._new_booking}")
        self.events.append(Event(self.step, action, bool(ok), frozenset(props)))
        self._before = state["counts"]

    def _application_alias(self, application_id) -> str:
        for alias, record in self.world.applications.items():
            if record.application_id == application_id:
                return alias
        raise AssertionError(f"unexpected application id {application_id}")

    def _slot_alias(self, slot_id) -> str:
        for alias, window in self.world.slots.items():
            if window.slot_id == slot_id:
                return alias
        raise AssertionError(f"unexpected slot id {slot_id}")

    def teardown(self) -> None:
        self.recorder.record(self.events)


def test_booking_state_machine(client, engine, account, clean_tables, evidence):
    """Run the state machine and leave one trace file per example behind."""

    recorder = Recorder(artefact_dir("traces"), evidence)
    harness = Harness(client, engine, account, clean_tables)
    try:
        run_state_machine_as_test(
            partial(BookingStateMachine, harness, recorder),
            settings=SETTINGS,
        )
    finally:
        payload = recorder.write_summary()
        print(
            "stateful summary: examples={examples} steps={steps} "
            "traces={traces} operations={operations}".format(**payload)
        )
