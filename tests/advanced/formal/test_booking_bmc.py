"""Bounded model checking of the booking rules with Z3 (P5).

The system under test is the abstract transition system in
:mod:`booking_model`, whose guards were copied from
``backend/app/candidate/service.py::book`` / ``::_eligible_application`` and
``backend/app/interview/service.py::delete_slot``.  Nothing here imports the
application: the model and the implementation are two descriptions of the
same requirement, and ``docs/advanced_testing/FORMAL_BOOKING.md`` records the
line-by-line correspondence.

Each property is checked by asking Z3 for a path of at most ``k = 6`` steps
that violates it:

* **B1-B4** must be ``unsat``: no such path exists within the bound.
* **N1-N4** weaken one guard and must be ``sat`` with a counterexample trace.
  N1/N2 are the negative controls required by the task; N3/N4 play the same
  role for B2/B4, so every invariant has a demonstration that the solver can
  falsify it when its guard is removed.
* The reachability tests show that booking, deletion and a status change of a
  booked application actually occur on some path; without them an
  over-constrained model could make B1-B4 vacuously true.

``sat`` is not a bug report about the application: it is a counterexample to
the *model*.  The model is only as good as the guard-to-code table, and the
report states that limitation explicitly.
"""

from __future__ import annotations

import pytest

import booking_model

#: One solver query may not exceed this; the whole ``formal`` mode must stay
#: under the 60 s acceptance budget.  Observed queries take ~0.01 s.
QUERY_TIME_LIMIT_SECONDS = 5.0

#: Filled by every test and flushed to ``$ADVANCED_OUT/formal/booking_bmc.json``
#: by the autouse fixture, so results and counterexamples survive the run even
#: though pytest captures stdout.
RECORDS: list[dict] = []


@pytest.fixture(autouse=True)
def _evidence_on_teardown(evidence):
    """Persist all records after every test; the last write has every row."""

    yield
    evidence(
        "booking_bmc",
        {
            "steps": booking_model.STEPS,
            "apps": list(booking_model.APPS),
            "slots": list(booking_model.SLOTS),
            "statuses": list(booking_model.STATUSES),
            "query_time_limit_seconds": QUERY_TIME_LIMIT_SECONDS,
            "records": RECORDS,
        },
    )


# -- trace helpers -----------------------------------------------------


def _emit(request, text: str) -> None:
    """Write ``text`` to the real terminal/log despite pytest's capture.

    ``run.py`` redirects the subprocess stdout to ``run.log`` and uses
    ``-q``, so a plain ``print`` would only appear in the captured section of
    a failing test.  Suspending capture for the write keeps the counterexample
    action sequences visible in the acceptance log; the same text is also
    persisted to ``booking_bmc.json`` through ``evidence()``.
    """

    capture = request.config.pluginmanager.getplugin("capturemanager")
    if capture is None:  # pragma: no cover - pytest always provides it
        print(text)
        return
    with capture.global_and_fixture_disabled():
        print(text, flush=True)


def _set_status_target(raw: str) -> tuple[str, str]:
    """``set_status_a0_Pending`` -> ``("a0", "Pending")``."""

    app, status = raw[len("set_status_") :].split("_", 1)
    return app, status


def _book_target(raw: str) -> tuple[str, str]:
    """``book_a0_s0`` -> ``("a0", "s0")``."""

    app, slot = raw[len("book_") :].split("_", 1)
    return app, slot


def _delete_target(raw: str) -> str:
    """``delete_slot_s0`` -> ``"s0"``."""

    return raw[len("delete_slot_") :]


def _effective_book_steps(rows: list[dict]) -> list[dict]:
    """Book steps whose post-state shows the application bound to the slot."""

    steps = []
    for index, row in enumerate(rows[:-1]):
        action = row.get("action")
        if action is None or not action["raw"].startswith("book_"):
            continue
        app, slot = _book_target(action["raw"])
        if rows[index + 1]["state"]["booking_of_app"][app] == slot:
            steps.append({"t": row["t"], "app": app, "slot": slot})
    return steps


def _effective_delete_steps(rows: list[dict]) -> list[dict]:
    """Delete steps whose post-state shows the slot gone."""

    steps = []
    for index, row in enumerate(rows[:-1]):
        action = row.get("action")
        if action is None or not action["raw"].startswith("delete_slot_"):
            continue
        slot = _delete_target(action["raw"])
        before = row["state"]["slot_exists"][slot]
        after = rows[index + 1]["state"]["slot_exists"][slot]
        if before and not after:
            steps.append({"t": row["t"], "slot": slot})
    return steps


def _status_changes(rows: list[dict]) -> list[dict]:
    """Every status-change step with the booking it starts and ends with."""

    changes = []
    for index, row in enumerate(rows[:-1]):
        action = row.get("action")
        if action is None or not action["raw"].startswith("set_status_"):
            continue
        app, status = _set_status_target(action["raw"])
        changes.append(
            {
                "t": row["t"],
                "app": app,
                "to": status,
                "booking_before": row["state"]["booking_of_app"][app],
                "booking_after": rows[index + 1]["state"][
                    "booking_of_app"
                ][app],
            }
        )
    return changes


# -- proof and counterexample harnesses --------------------------------


def _proof(name: str) -> None:
    """Assert that requirement ``name`` has no violating path within ``k``."""

    bmc = booking_model.BookingBMC()
    result = bmc.check(name)
    metadata = booking_model.PROPERTIES[name]
    RECORDS.append(
        {
            "id": name,
            "kind": "property",
            "title": metadata["title"],
            "requirement": metadata["requirement"],
            "variant": bmc.variant.describe(),
            "steps": bmc.steps,
            "result": result.status,
            "seconds": round(result.seconds, 6),
        }
    )
    detail = ""
    if result.is_sat:
        assert result.model is not None
        detail = (
            "\ncounterexample:\n"
            + booking_model.format_trace(bmc.trace(result.model))
        )
    elif result.reason is not None:
        detail = f"; reason: {result.reason}"
    assert result.status == "unsat", (
        f"{name} ({metadata['title']}): expected no violating path within "
        f"{bmc.steps} steps, got {result.status}{detail}"
    )
    assert result.seconds < QUERY_TIME_LIMIT_SECONDS, (
        f"{name}: query took {result.seconds:.3f}s "
        f"(limit {QUERY_TIME_LIMIT_SECONDS}s)"
    )


def _counterexample(
    name: str, variant: booking_model.Variant, request
) -> list[dict]:
    """Assert that weakened variant ``variant`` violates ``name``; return trace."""

    bmc = booking_model.BookingBMC(variant=variant)
    result = bmc.check(name)
    metadata = booking_model.PROPERTIES[name]
    record = {
        "id": name,
        "kind": "negative_control",
        "title": metadata["title"],
        "requirement": metadata["requirement"],
        "variant": variant.describe(),
        "steps": bmc.steps,
        "result": result.status,
        "seconds": round(result.seconds, 6),
    }
    RECORDS.append(record)
    assert result.status == "sat", (
        f"{name} under variant {variant.describe()!r}: expected a "
        f"counterexample, got {result.status}"
    )
    assert result.seconds < QUERY_TIME_LIMIT_SECONDS, (
        f"{name}: query took {result.seconds:.3f}s "
        f"(limit {QUERY_TIME_LIMIT_SECONDS}s)"
    )
    assert result.model is not None
    rows = bmc.trace(result.model)
    record["trace"] = rows
    record["trace_text"] = booking_model.format_trace(rows)
    _emit(
        request,
        f"\n{name} counterexample (variant: {variant.describe()}):\n"
        f"{record['trace_text']}",
    )
    return rows


# {S_0 = two Pending applications with no booking, slots s0 and s1 exist}
#   steps 0..k  {B1: at most one application holds a booking on a slot}
def test_b1_slot_has_at_most_one_booking():
    """FP-SCHED-2: two applications can never book the same slot."""

    _proof("B1")


# {S_0 as above}  steps 0..k
#   {B2: book(a, s) succeeds at t -> status[a][t] = Interviewing}
def test_b2_booking_requires_interviewing_status():
    """FP-SCHED-2: only an Interviewing application may create a booking."""

    _proof("B2")


# {S_0 as above}  steps 0..k
#   {B3: booked at t -> the slot exists at every step t' >= t}
def test_b3_booked_slot_is_never_deleted():
    """FP-SCHED-1: deleting a booked slot is rejected, so it stays."""

    _proof("B3")


# {S_0 as above}  steps 0..k
#   {B4: set_status(a, ·) at t with booking[a][t] != none
#        -> booking[a][t+1] = booking[a][t]}
def test_b4_status_change_does_not_clear_booking():
    """FP-SCHED-2: a booking survives an application leaving Interviewing."""

    _proof("B4")


def test_n1_without_slot_free_guard_two_applications_share_a_slot(request):
    """N1: drop "slot not booked" from ``book`` and B1 becomes falsifiable."""

    rows = _counterexample(
        "B1",
        booking_model.Variant(allow_booking_taken_slot=True),
        request,
    )
    books = _effective_book_steps(rows)
    assert len(books) == 2, f"expected two successful bookings, got {books}"
    assert {step["app"] for step in books} == set(booking_model.APPS)
    shared = {step["slot"] for step in books}
    assert len(shared) == 1, f"both applications should share one slot: {books}"
    # B1 is violated by a *state* where both applications hold one slot, not
    # necessarily by the last state: assert the violation itself.
    simultaneous = [
        (row["t"], slot)
        for row in rows
        for slot in booking_model.SLOTS
        if all(
            row["state"]["booking_of_app"][app] == slot
            for app in booking_model.APPS
        )
    ]
    assert simultaneous, (
        "expected a state where both applications hold the same slot, got "
        f"final bookings {rows[-1]['state']['booking_of_app']}"
    )


def test_n2_without_delete_guard_a_booked_slot_is_deleted(request):
    """N2: drop the booking check from ``delete_slot`` and B3 becomes false."""

    rows = _counterexample(
        "B3",
        booking_model.Variant(skip_delete_booking_guard=True),
        request,
    )
    books = _effective_book_steps(rows)
    deletes = _effective_delete_steps(rows)
    assert books, "the counterexample must contain a booking first"
    assert deletes, "the counterexample must contain a deletion"
    # B3 is violated when a slot that was booked at some t is missing at some
    # t' >= t; assert exactly that on the trace rather than a final-state shape.
    violations = []
    for t, row in enumerate(rows):
        for app in booking_model.APPS:
            slot = row["state"]["booking_of_app"][app]
            if slot == "none":
                continue
            gone_at = [
                later
                for later in range(t, len(rows))
                if not rows[later]["state"]["slot_exists"][slot]
            ]
            if gone_at:
                violations.append(
                    {"t": t, "app": app, "slot": slot, "gone_at": gone_at[0]}
                )
    assert violations, (
        "expected a booked slot that disappeared later, trace: "
        f"{booking_model.format_trace(rows)}"
    )


def test_n3_without_status_guard_booking_of_non_interviewing_application(request):
    """Self-check for B2: without its guard, a Rejected/Accepted app can book."""

    rows = _counterexample(
        "B2", booking_model.Variant(skip_status_guard=True), request
    )
    offending = []
    for index, row in enumerate(rows[:-1]):
        action = row.get("action")
        if action is None or not action["raw"].startswith("book_"):
            continue
        app, slot = _book_target(action["raw"])
        booked = rows[index + 1]["state"]["booking_of_app"][app] == slot
        status = row["state"]["status"][app]
        if booked and status != "Interviewing":
            offending.append({"t": row["t"], "app": app, "status": status})
    assert offending, (
        "expected a successful booking made by a non-Interviewing "
        f"application, trace: {booking_model.format_trace(rows)}"
    )


def test_n4_clearing_booking_on_status_change_is_found(request):
    """Self-check for B4: a status change that wipes the booking violates it."""

    rows = _counterexample(
        "B4",
        booking_model.Variant(clear_booking_on_status_change=True),
        request,
    )
    cleared = [
        change
        for change in _status_changes(rows)
        if change["booking_before"] != "none"
        and change["booking_after"] == "none"
    ]
    assert cleared, (
        "expected a status change that clears a booking, trace: "
        f"{booking_model.format_trace(rows)}"
    )


# -- non-vacuity witnesses ---------------------------------------------


def test_scenario_can_create_a_booking(request):
    """The guards admit a reachable booking: B1/B2/B3 are not vacuous."""

    bmc = booking_model.BookingBMC()
    result = bmc.solve(bmc.booking_created())
    RECORDS.append(
        {
            "id": "reach-booking",
            "kind": "reachability",
            "title": "some path creates a booking",
            "steps": bmc.steps,
            "result": result.status,
            "seconds": round(result.seconds, 6),
        }
    )
    assert result.status == "sat", "the model cannot produce a booking"
    assert result.model is not None
    rows = bmc.trace(result.model)
    books = _effective_book_steps(rows)
    assert books, f"no effective booking in witness: {rows}"
    RECORDS[-1]["trace_text"] = booking_model.format_trace(rows)
    _emit(request, "\nbooking witness:\n" + booking_model.format_trace(rows))


def test_scenario_can_delete_an_unbooked_slot(request):
    """An unbooked slot is deletable: the delete guard is not always false."""

    bmc = booking_model.BookingBMC()
    result = bmc.solve(bmc.slot_deleted())
    RECORDS.append(
        {
            "id": "reach-delete",
            "kind": "reachability",
            "title": "some path deletes an unbooked slot",
            "steps": bmc.steps,
            "result": result.status,
            "seconds": round(result.seconds, 6),
        }
    )
    assert result.status == "sat", "the model cannot delete any slot"
    assert result.model is not None
    rows = bmc.trace(result.model)
    assert _effective_delete_steps(rows), f"no effective delete in witness: {rows}"
    RECORDS[-1]["trace_text"] = booking_model.format_trace(rows)
    _emit(request, "\ndelete witness:\n" + booking_model.format_trace(rows))


def test_booking_survives_a_reachable_status_change(request):
    """A booking can exist before a status change: B4 is not vacuous.

    ``sat`` of the antecedent plus the equality checked on the trace is the
    concrete counterpart of the B4 proof.
    """

    bmc = booking_model.BookingBMC()
    result = bmc.solve(bmc.booking_then_status_change())
    RECORDS.append(
        {
            "id": "reach-status-change",
            "kind": "reachability",
            "title": "a booked application reaches a status change",
            "steps": bmc.steps,
            "result": result.status,
            "seconds": round(result.seconds, 6),
        }
    )
    assert result.status == "sat", (
        "the model cannot change the status of a booked application"
    )
    assert result.model is not None
    rows = bmc.trace(result.model)
    booked_changes = [
        change
        for change in _status_changes(rows)
        if change["booking_before"] != "none"
    ]
    assert booked_changes, (
        "expected a status change after the booking, trace: "
        f"{booking_model.format_trace(rows)}"
    )
    for change in booked_changes:
        assert change["booking_after"] == change["booking_before"], (
            f"booking changed across status change at t={change['t']}: "
            f"{change}"
        )
    RECORDS[-1]["trace_text"] = booking_model.format_trace(rows)
    _emit(
        request,
        "\nbooking + status change witness:\n"
        + booking_model.format_trace(rows),
    )
