"""Z3 bounded model checking (BMC) of the interview-booking state machine.

This module is the *model*, not the implementation.  It encodes the rules the
application is required to follow (``docs/REQUIREMENTS.md``) as a symbolic
transition system and lets :mod:`test_booking_bmc` ask Z3 whether a rule can
be violated within ``k`` steps.  The guards were copied by hand from

* ``backend/app/candidate/service.py::_eligible_application`` (lines 348-360)
  and ``::book`` (lines 389-446), and
* ``backend/app/interview/service.py::delete_slot`` (lines 122-146).

Section 2 of ``docs/advanced_testing/FORMAL_BOOKING.md`` is the line-by-line
guard-to-code table.

Requirement clauses modelled
----------------------------

``FP-SCHED-2``
    A booking is legal only if the application is ``Interviewing``, has no
    existing booking, and the slot exists and is not already booked by
    another application.  A booking is never removed by a later status
    change.
``FP-SCHED-1``
    A slot that is booked cannot be deleted.
``FP-EMP-3``
    An application moves between ``Pending``, ``Interviewing``, ``Rejected``
    and ``Accepted``, and a status change does not touch the booking.

Abstraction (documented assumptions)
------------------------------------

The model keeps only the state the scheduling rules constrain:

* **Two applications, two slots, one employer.**  Both applications belong
  to jobs of the same employer and both slots belong to that employer, so
  the ownership checks in ``book``/``delete_slot`` are always satisfied and
  are not encoded.
* **Time is abstracted away.**  Every slot is assumed to be in the future
  and to last exactly 30 minutes, so ``starts_at``/duration checks pass.
* **Slot creation is not an action.**  The two slots exist in the initial
  state; creating them is the scenario setup, not part of the booking
  lifecycle.
* **The job-reservation rule is not modelled.**  The implementation binds a
  booked slot to the posting (``slot.job_id``, ``book`` line 414-417).  This
  is an implementation detail beyond FP-SCHED-2's employer-level wording and
  cannot fire here because the scenario has one employer.
* **Concurrency is out of scope.**  FP-SCHED-3 (row lock plus unique
  constraint) is a property of the database, not of a sequential transition
  relation; the dedicated concurrency tests cover it.

Encoding
--------

States are ``S_0 .. S_k``.  For every step ``t`` one ``action[t]`` -- a
single ``EnumSort`` constant -- transforms ``S_t`` into ``S_{t+1}``.  Because
the action is one enumeration value, exactly one action is chosen per step.
A guarded action whose guard is false leaves every state variable untouched,
which is how the requirement "ineligible bookings MUST fail without partially
changing either record" is represented.

A requirement is *checked*, not assumed: its negation is conjoined with the
initial state and the transition relation and handed to Z3.  ``unsat`` means
no path of at most ``k`` steps violates it; ``sat`` yields a concrete
counterexample trace that :meth:`BookingBMC.trace` renders as readable text.

The ``Variant`` flags are deliberate deviations from the implemented guards.
They exist only for negative controls: they show that the solver does find a
counterexample when a guard is removed, so the ``unsat`` results above are
not vacuous.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

import z3

#: Number of transition steps used by every check in the test module.
STEPS = 6

#: Modelled applications.  Both belong to jobs of the same employer.
APPS = ("a0", "a1")

#: Modelled interview slots.  Both exist at ``t = 0`` and belong to the
#: employer of both applications.
SLOTS = ("s0", "s1")

#: The only statuses FP-EMP-3 allows.
STATUSES = ("Pending", "Interviewing", "Rejected", "Accepted")

#: A new application is ``Pending`` (FP-CAN-3), which is the initial status.
INITIAL_STATUS = "Pending"

#: Per-query solver timeout.  Observed queries take well under 0.1 s; the
#: limit only turns a runaway encoding into a visible failure.
QUERY_TIMEOUT_MS = 10_000

#: One Z3 context per process; the enum sorts are therefore module singletons.
_STATUS_SORT, _STATUS_VALUES = z3.EnumSort("BookingStatus", list(STATUSES))
STATUS_CONST: dict[str, z3.ExprRef] = dict(zip(STATUSES, _STATUS_VALUES))

_BOOKING_SORT, _BOOKING_VALUES = z3.EnumSort(
    "SlotBooking", ["none", *SLOTS]
)
BOOKING_CONST: dict[str, z3.ExprRef] = dict(zip(("none", *SLOTS), _BOOKING_VALUES))


def _set_status_action(app: str, status: str) -> str:
    return f"set_status_{app}_{status}"


def _book_action(app: str, slot: str) -> str:
    return f"book_{app}_{slot}"


def _delete_action(slot: str) -> str:
    return f"delete_slot_{slot}"


#: Every action of the transition system: ``noop``, all status changes, all
#: bookings and all deletions.  The list order is stable and only used for
#: deterministic symbol creation.
ACTION_NAMES = (
    "noop",
    *(
        _set_status_action(app, status)
        for app in APPS
        for status in STATUSES
    ),
    *(_book_action(app, slot) for app in APPS for slot in SLOTS),
    *(_delete_action(slot) for slot in SLOTS),
)

_ACTION_SORT, _ACTION_VALUES = z3.EnumSort(
    "BookingAction", list(ACTION_NAMES)
)
ACTION_CONST: dict[str, z3.ExprRef] = dict(zip(ACTION_NAMES, _ACTION_VALUES))

#: Human-readable rendering of an action symbol, used for counterexamples.
_ACTION_FORMS: dict[str, str] = {
    "noop": "noop",
    **{
        _set_status_action(app, status): f"set_status({app}, {status})"
        for app in APPS
        for status in STATUSES
    },
    **{
        _book_action(app, slot): f"book({app}, {slot})"
        for app in APPS
        for slot in SLOTS
    },
    **{
        _delete_action(slot): f"delete_slot({slot})"
        for slot in SLOTS
    },
}


def render_action(name: str) -> str:
    """Return ``book(a0, s0)``-style text for an action symbol."""

    return _ACTION_FORMS.get(name, name)


#: Property metadata: requirement clause and one-line reading of each check.
PROPERTIES: dict[str, dict[str, str]] = {
    "B1": {
        "title": "no two applications hold a booking on the same slot",
        "requirement": (
            "FP-SCHED-2: a slot is booked by at most one application"
        ),
    },
    "B2": {
        "title": (
            "a successful book(a, s) step only happens while "
            "status[a] = Interviewing"
        ),
        "requirement": (
            "FP-SCHED-2: the application status is Interviewing"
        ),
    },
    "B3": {
        "title": "a booked slot still exists after every later step",
        "requirement": (
            "FP-SCHED-1: deletion of a booked slot is rejected"
        ),
    },
    "B4": {
        "title": "a status change never clears an existing booking",
        "requirement": (
            "FP-SCHED-2 / FP-EMP-3: a booking survives leaving Interviewing"
        ),
    },
}

PROPERTY_IDS = tuple(PROPERTIES)


@dataclass(frozen=True)
class Variant:
    """Deliberate deviations from the implemented guards.

    ``Variant()`` is the model used for B1-B4.  Each flag removes exactly the
    guard named by the field; the negative-control tests use one flag at a
    time and expect the solver to find a counterexample.  Variants are test
    instruments, never a description of the production system.
    """

    #: N1: ``book`` no longer checks that the slot is free.
    allow_booking_taken_slot: bool = False
    #: N3: ``book`` no longer checks that the application is Interviewing.
    skip_status_guard: bool = False
    #: N2: ``delete_slot`` no longer checks that the slot is free.
    skip_delete_booking_guard: bool = False
    #: N4: a status change resets the application's booking to ``none``.
    clear_booking_on_status_change: bool = False

    def describe(self) -> str:
        """Return a compact label such as ``skip_status_guard``."""

        names = [
            "allow_booking_taken_slot",
            "skip_status_guard",
            "skip_delete_booking_guard",
            "clear_booking_on_status_change",
        ]
        active = [name for name in names if getattr(self, name)]
        return ", ".join(active) if active else "unmodified"


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one solver query."""

    status: str
    seconds: float
    model: z3.ModelRef | None = None
    reason: str | None = None

    @property
    def is_unsat(self) -> bool:
        return self.status == "unsat"

    @property
    def is_sat(self) -> bool:
        return self.status == "sat"


class BookingBMC:
    """One bounded transition system of ``steps + 1`` states.

    Constructing the object only declares the variables and transition
    constraints; nothing is solved until :meth:`check` or :meth:`solve` is
    called.  Every query builds a fresh solver so proofs and counterexample
    searches cannot influence each other.
    """

    def __init__(
        self,
        *,
        steps: int = STEPS,
        variant: Variant = Variant(),
    ) -> None:
        if steps < 1:
            raise ValueError("steps must be a positive integer")
        self.steps = steps
        self.variant = variant

        self.status = {
            app: [
                z3.Const(f"status_{app}_{t}", _STATUS_SORT)
                for t in range(steps + 1)
            ]
            for app in APPS
        }
        self.booking_of_app = {
            app: [
                z3.Const(f"booking_of_app_{app}_{t}", _BOOKING_SORT)
                for t in range(steps + 1)
            ]
            for app in APPS
        }
        self.slot_exists = {
            slot: [
                z3.Bool(f"slot_exists_{slot}_{t}")
                for t in range(steps + 1)
            ]
            for slot in SLOTS
        }
        self.action = [
            z3.Const(f"action_{t}", _ACTION_SORT) for t in range(steps)
        ]

        self.constraints: list[z3.BoolRef] = []
        self._add_initial_state()
        self._add_transitions()

    # -- transition relation ------------------------------------------

    def _add_initial_state(self) -> None:
        """The scenario starts with two Pending, unbooked applications.

        Both slots exist and belong to the employer.  Fixing the initial
        state keeps the checks about the *reachable* behaviour: without it
        two applications could already share a slot at ``t = 0`` and B1
        would be violated before any action runs.
        """

        for app in APPS:
            self.constraints.append(
                self.status[app][0] == STATUS_CONST[INITIAL_STATUS]
            )
            self.constraints.append(
                self.booking_of_app[app][0] == BOOKING_CONST["none"]
            )
        for slot in SLOTS:
            self.constraints.append(self.slot_exists[slot][0])

    def _add_transitions(self) -> None:
        for t in range(self.steps):
            for app in APPS:
                self.constraints.append(
                    self.status[app][t + 1] == self._next_status(app, t)
                )
                self.constraints.append(
                    self.booking_of_app[app][t + 1] == self._next_booking(app, t)
                )
            for slot in SLOTS:
                self.constraints.append(
                    self.slot_exists[slot][t + 1]
                    == self._next_slot_exists(slot, t)
                )

    def _next_status(self, app: str, t: int) -> z3.ExprRef:
        """Apply the selected ``set_status`` action; nothing else touches it."""

        result = self.status[app][t]
        for status in STATUSES:
            result = z3.If(
                self.action[t]
                == ACTION_CONST[_set_status_action(app, status)],
                STATUS_CONST[status],
                result,
            )
        return result

    def _next_booking(self, app: str, t: int) -> z3.ExprRef:
        """Apply a successful booking, then the N4 variant if enabled."""

        result = self.booking_of_app[app][t]
        for slot in SLOTS:
            result = z3.If(
                z3.And(
                    self.action[t] == ACTION_CONST[_book_action(app, slot)],
                    self.book_guard(app, slot, t),
                ),
                BOOKING_CONST[slot],
                result,
            )
        if self.variant.clear_booking_on_status_change:
            result = z3.If(
                self._status_change(app, t),
                BOOKING_CONST["none"],
                result,
            )
        return result

    def _next_slot_exists(self, slot: str, t: int) -> z3.BoolRef:
        """Delete the selected slot only when the delete guard holds."""

        deleted_now = z3.And(
            self.action[t] == ACTION_CONST[_delete_action(slot)],
            self.delete_guard(slot, t),
        )
        return z3.If(deleted_now, z3.BoolVal(False), self.slot_exists[slot][t])

    # -- guards (copied from the implementation) ----------------------

    def book_guard(self, app: str, slot: str, t: int) -> z3.BoolRef:
        """FP-SCHED-2 preconditions of ``book`` modelled here.

        ``_eligible_application`` (candidate/service.py:348-360): the row is
        owned by the caller (abstracted: all applications are the caller's),
        ``status == Interviewing``, no booking for this application.
        ``book`` (candidate/service.py:395-416): the slot exists, belongs to
        the application's employer (abstracted: true), is in the future and
        lasts 30 minutes (abstracted: true), is not booked by any
        application, and is not reserved for another posting (abstracted:
        not modelled, see the module docstring).
        """

        conditions: list[z3.BoolRef] = []
        if not self.variant.skip_status_guard:
            conditions.append(
                self.status[app][t] == STATUS_CONST["Interviewing"]
            )
        conditions.append(
            self.booking_of_app[app][t] == BOOKING_CONST["none"]
        )
        conditions.append(self.slot_exists[slot][t])
        if not self.variant.allow_booking_taken_slot:
            conditions.extend(
                self.booking_of_app[other][t] != BOOKING_CONST[slot]
                for other in APPS
                if other != app
            )
        return z3.And(*conditions)

    def delete_guard(self, slot: str, t: int) -> z3.BoolRef:
        """FP-SCHED-1 preconditions of ``delete_slot`` modelled here.

        ``delete_slot`` (interview/service.py:125-140): the slot exists,
        belongs to the caller (abstracted: true), is in the future
        (abstracted: true), and no booking references it.
        """

        conditions: list[z3.BoolRef] = [self.slot_exists[slot][t]]
        if not self.variant.skip_delete_booking_guard:
            conditions.extend(
                self.booking_of_app[app][t] != BOOKING_CONST[slot] for app in APPS
            )
        return z3.And(*conditions)

    def _status_change(self, app: str, t: int) -> z3.BoolRef:
        """Is ``action[t]`` a status change of *app*?"""

        return z3.Or(
            *[
                self.action[t]
                == ACTION_CONST[_set_status_action(app, status)]
                for status in STATUSES
            ]
        )

    # -- properties ----------------------------------------------------

    def property(self, name: str) -> z3.BoolRef:
        """Return requirement ``name`` as a term that must hold on all paths."""

        builders = {
            "B1": self._slot_exclusive,
            "B2": self._booking_requires_interviewing,
            "B3": self._booked_slot_survives,
            "B4": self._status_change_keeps_booking,
        }
        if name not in builders:
            raise KeyError(
                f"unknown property {name!r}; expected {PROPERTY_IDS}"
            )
        return builders[name]()

    def _slot_exclusive(self) -> z3.BoolRef:
        """B1: at every step, at most one application holds a given slot."""

        claims = []
        for t in range(self.steps + 1):
            for slot in SLOTS:
                holders = [
                    self.booking_of_app[app][t] == BOOKING_CONST[slot]
                    for app in APPS
                ]
                claims.append(z3.AtMost(*holders, 1))
        return z3.And(*claims)

    def _booking_requires_interviewing(self) -> z3.BoolRef:
        """B2: a booking is only created by a guarded ``book`` step.

        The antecedent is exactly the transition's "this booking happened"
        condition: the action selects ``book(a, s)`` *and* its guard holds.
        """

        claims = []
        for t in range(self.steps):
            for app in APPS:
                for slot in SLOTS:
                    booked_here = z3.And(
                        self.action[t]
                        == ACTION_CONST[_book_action(app, slot)],
                        self.book_guard(app, slot, t),
                    )
                    claims.append(
                        z3.Implies(
                            booked_here,
                            self.status[app][t]
                            == STATUS_CONST["Interviewing"],
                        )
                    )
        return z3.And(*claims)

    def _booked_slot_survives(self) -> z3.BoolRef:
        """B3: once a slot is booked it exists at every later step."""

        claims = []
        for slot in SLOTS:
            for t in range(self.steps + 1):
                booked = z3.Or(
                    *[
                        self.booking_of_app[app][t] == BOOKING_CONST[slot]
                        for app in APPS
                    ]
                )
                claims.extend(
                    z3.Implies(booked, self.slot_exists[slot][later])
                    for later in range(t, self.steps + 1)
                )
        return z3.And(*claims)

    def _status_change_keeps_booking(self) -> z3.BoolRef:
        """B4: a status change never clears an existing booking.

        Quantified over every application whose status changes and every
        application that holds a booking, so it also covers the case where
        changing ``a0`` must not touch ``a1``'s booking.
        """

        claims = []
        for t in range(self.steps):
            for changed in APPS:
                status_change = self._status_change(changed, t)
                for holder in APPS:
                    claims.append(
                        z3.Implies(
                            z3.And(
                                self.booking_of_app[holder][t]
                                != BOOKING_CONST["none"],
                                status_change,
                            ),
                            self.booking_of_app[holder][t + 1]
                            == self.booking_of_app[holder][t],
                        )
                    )
        return z3.And(*claims)

    # -- reachability witnesses (non-vacuity) -------------------------

    def booking_created(self) -> z3.BoolRef:
        """Some reachable step creates a booking."""

        return z3.Or(
            *[
                z3.And(
                    self.action[t]
                    == ACTION_CONST[_book_action(app, slot)],
                    self.book_guard(app, slot, t),
                )
                for t in range(self.steps)
                for app in APPS
                for slot in SLOTS
            ]
        )

    def slot_deleted(self) -> z3.BoolRef:
        """Some reachable state has a deleted slot."""

        return z3.Or(
            *[
                z3.Not(self.slot_exists[slot][t])
                for slot in SLOTS
                for t in range(self.steps + 1)
            ]
        )

    def booking_then_status_change(self) -> z3.BoolRef:
        """A reachable step changes the status of an already-booked application."""

        return z3.Or(
            *[
                z3.And(
                    self.booking_of_app[app][t] != BOOKING_CONST["none"],
                    self._status_change(app, t),
                )
                for t in range(self.steps)
                for app in APPS
            ]
        )

    # -- solving -------------------------------------------------------

    def check(self, name: str) -> CheckResult:
        """Look for a path of at most ``self.steps`` steps violating ``name``.

        ``unsat`` means the requirement holds on every path from the initial
        state within the bound; ``sat`` carries the counterexample model.
        """

        return self._query(z3.Not(self.property(name)))

    def solve(self, *extra: z3.BoolRef) -> CheckResult:
        """Satisfiability query used by the reachability witnesses."""

        return self._query(*extra)

    def _query(self, *goal: z3.BoolRef) -> CheckResult:
        solver = z3.Solver()
        solver.set("timeout", QUERY_TIMEOUT_MS)
        solver.add(*self.constraints, *goal)
        started = time.perf_counter()
        result = solver.check()
        seconds = time.perf_counter() - started
        model = solver.model() if result == z3.sat else None
        reason = solver.reason_unknown() if result == z3.unknown else None
        return CheckResult(
            status=str(result), seconds=seconds, model=model, reason=reason
        )

    # -- counterexample rendering -------------------------------------

    @staticmethod
    def _value_name(value: z3.ExprRef) -> str:
        if z3.is_const(value):
            return value.decl().name()
        return str(value)

    def state_at(self, model: z3.ModelRef, t: int) -> dict:
        """Read the concrete state ``S_t`` out of a counterexample model."""

        return {
            "status": {
                app: self._value_name(
                    model.eval(self.status[app][t], model_completion=True)
                )
                for app in APPS
            },
            "booking_of_app": {
                app: self._value_name(
                    model.eval(self.booking_of_app[app][t], model_completion=True)
                )
                for app in APPS
            },
            "slot_exists": {
                slot: z3.is_true(
                    model.eval(
                        self.slot_exists[slot][t], model_completion=True
                    )
                )
                for slot in SLOTS
            },
        }

    def trace(self, model: z3.ModelRef) -> list[dict]:
        """Return the counterexample as ``k + 1`` readable states."""

        rows = []
        for t in range(self.steps + 1):
            row: dict = {"t": t, "state": self.state_at(model, t)}
            if t < self.steps:
                raw = self._value_name(
                    model.eval(self.action[t], model_completion=True)
                )
                row["action"] = {
                    "raw": raw,
                    "pretty": render_action(raw),
                }
            rows.append(row)
        return rows


def format_trace(rows: list[dict]) -> str:
    """Render :meth:`BookingBMC.trace` output as a readable action sequence."""

    lines = []
    for row in rows:
        state = row["state"]
        parts = [
            f"status[{app}]={state['status'][app]}" for app in APPS
        ]
        parts.extend(
            f"booking[{app}]={state['booking_of_app'][app]}"
            for app in APPS
        )
        parts.extend(
            f"exists[{slot}]={'yes' if state['slot_exists'][slot] else 'no'}"
            for slot in SLOTS
        )
        lines.append(f"t={row['t']:<2} " + "  ".join(parts))
        action = row.get("action")
        if action is not None:
            lines.append(f"        action[{row['t']}]: {action['pretty']}")
    return "\n".join(lines)
