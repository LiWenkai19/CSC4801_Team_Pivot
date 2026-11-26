"""Evaluate L1-L5 on the P2 booking traces and report vacuity honestly.

The trace producer is the P2 state machine.  ``run.py ltl`` starts a disposable
PostgreSQL, so this mode can create the traces itself when the artefact
directory is missing:

* if ``$ADVANCED_OUT/stateful/traces`` (the canonical P2 location) or
  ``$ADVANCED_OUT/ltl/stateful/traces`` already contains trace files, they are
  read directly (the mode then needs no database at all);
* otherwise the test runs ``python tests/advanced/run.py stateful`` as a
  subprocess with ``$ADVANCED_OUT/ltl/stateful`` as its output directory.  The
  nested runner reuses the ``ADVANCED_PG_URL`` of the outer ``run.py``, so only
  one disposable PostgreSQL server is involved.  ``--max-examples`` defaults to
  25 to match the canonical P2 run and is capped at 100.

The test is a *checker* around the P2 oracle, not a replacement for it: a
violation is reported with :func:`support.ltl.explain` (first offending step and
event), and a property whose implication antecedent never fires is counted as
vacuously satisfied rather than as evidence.  The evidence file stores both the
raw-file and de-duplicated numbers because Hypothesis replays a few examples.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

import pytest

from support.ltl import evaluate, explain
from support.traces import Event, read_traces

import properties
import refine


ROOT = Path(__file__).resolve().parents[3]
ADVANCED = ROOT / "tests" / "advanced"
RUNNER = ADVANCED / "run.py"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

#: Canonical P2 run uses 25 examples.  Keep the generated run bounded and allow
#: ``run.py --max-examples`` / ``ADVANCED_MAX_EXAMPLES`` for slower CI jobs.
DEFAULT_MAX_EXAMPLES = 25
GENERATION_TIMEOUT_SECONDS = 900

_TRACE_CACHE: dict | None = None


# ---------------------------------------------------------------------------
# Locating or creating the P2 traces
# ---------------------------------------------------------------------------


def _max_examples() -> int:
    """Read ``ADVANCED_MAX_EXAMPLES`` with the same clamp the P2 suite uses."""

    raw = os.environ.get("ADVANCED_MAX_EXAMPLES")
    if not raw:
        return DEFAULT_MAX_EXAMPLES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_EXAMPLES
    return min(max(value, 1), 100)


def _trace_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.json"))


def _outside_checkout(path: Path) -> bool:
    try:
        return not path.resolve().is_relative_to(ROOT)
    except ValueError:
        return True


def _existing_trace_dir() -> Path | None:
    """Find traces without generating anything.

    The canonical P2 location is ``$ADVANCED_OUT/stateful/traces`` (used when a
    stateful run happened first, or when a caller prepared the evidence
    directory).  A previous ltl run may also have left its self-generated copy
    under ``$ADVANCED_OUT/ltl/stateful/traces``; both are read-only here.
    """

    base = os.environ.get("ADVANCED_OUT")
    if not base:
        return None
    for candidate in (
        Path(base) / "stateful" / "traces",
        Path(base) / "ltl" / "stateful" / "traces",
    ):
        if candidate.is_dir() and _trace_files(candidate):
            return candidate
    return None


def _generation_target() -> Path:
    """Return the nested run.py output directory (never inside the checkout).

    The target lives under the ``ltl`` mode directory rather than under the
    ``stateful`` mode directory that ``run.py`` reserves for a real stateful
    run.  This keeps ``run.py fast`` / ``run.py all`` from mixing the ltl
    self-generated traces with the stateful mode's own artefacts.
    """

    base = os.environ.get("ADVANCED_OUT")
    if base:
        candidate = Path(base) / "ltl" / "stateful"
        if not candidate.exists() and _outside_checkout(candidate):
            return candidate
    return Path(tempfile.mkdtemp(prefix="p3-stateful-"))


def _generate_traces(target: Path) -> dict:
    """Run the P2 stateful mode in a subprocess and return generation metadata."""

    if not os.environ.get("ADVANCED_PG_URL"):
        pytest.fail(
            "the P2 traces are missing and ADVANCED_PG_URL is not set; run "
            "this mode through python tests/advanced/run.py ltl",
            pytrace=False,
        )
    examples = _max_examples()
    command = [
        sys.executable,
        str(RUNNER),
        "stateful",
        "--out",
        str(target),
        "--max-examples",
        str(examples),
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GENERATION_TIMEOUT_SECONDS,
            creationflags=CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired:
        pytest.fail(
            "generating the P2 traces timed out after "
            f"{GENERATION_TIMEOUT_SECONDS}s: {' '.join(command)}",
            pytrace=False,
        )
    seconds = time.monotonic() - started
    nested_trace_dir = target / "stateful" / "traces"
    if completed.returncode != 0 or not _trace_files(nested_trace_dir):
        output = (completed.stdout or "") + (completed.stderr or "")
        tail = output.strip()[-4000:]
        pytest.fail(
            "generating the P2 traces failed (exit "
            f"{completed.returncode}): {' '.join(command)}\n"
            f"trace dir: {nested_trace_dir}\n"
            f"nested runner output tail:\n{tail}",
            pytrace=False,
        )
    # The nested runner writes ``<target>/stateful/traces``.  With the ltl
    # target ``$ADVANCED_OUT/ltl/stateful`` that means one redundant level;
    # move the files up so the mode owns ``<out>/ltl/stateful/traces`` and a
    # later direct pytest invocation can reuse them without regenerating.
    trace_dir = target / "traces"
    if not trace_dir.exists():
        shutil.move(str(nested_trace_dir), str(trace_dir))
    else:  # pragma: no cover - only when a caller pre-created the folder
        trace_dir = nested_trace_dir
    return {
        "generated": True,
        "generation_seconds": round(seconds, 3),
        "generation_command": command,
        "generated_examples": examples,
        "generation_target": str(target),
        "trace_dir": str(trace_dir),
    }


def ensure_trace_dir() -> tuple[Path, dict]:
    """Return ``(trace directory, metadata)``, generating P2 traces if needed."""

    global _TRACE_CACHE
    if _TRACE_CACHE is not None:
        return Path(_TRACE_CACHE["trace_dir"]), dict(_TRACE_CACHE)

    existing = _existing_trace_dir()
    if existing is not None:
        metadata = {
            "generated": False,
            "trace_dir": str(existing),
        }
    else:
        target = _generation_target()
        metadata = _generate_traces(target)
        existing = Path(metadata["trace_dir"])
    _TRACE_CACHE = dict(metadata)
    return existing, metadata


# ---------------------------------------------------------------------------
# Statistics helpers
# ---------------------------------------------------------------------------


def trace_digest(trace: list[Event]) -> str:
    """Stable digest of one trace for duplicate detection and reporting."""

    payload = [event.to_json() for event in trace]
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()


def _deduplicate(traces: list[list[Event]]) -> list[list[Event]]:
    seen: set[str] = set()
    distinct: list[list[Event]] = []
    for trace in traces:
        digest = trace_digest(trace)
        if digest in seen:
            continue
        seen.add(digest)
        distinct.append(trace)
    return distinct


def _property_statistics(
    property_, traces: list[list[Event]], distinct: list[list[Event]]
) -> dict:
    """Evaluate one property and collect satisfaction plus vacuity numbers."""

    satisfactions = [
        evaluate(property_.formula, trace) for trace in traces
    ]
    distinct_satisfactions = [
        evaluate(property_.formula, trace) for trace in distinct
    ]
    bindings = [
        properties.trigger_bindings(property_.formula, trace)
        for trace in traces
    ]
    distinct_bindings = [
        properties.trigger_bindings(property_.formula, trace)
        for trace in distinct
    ]
    return {
        "title": property_.title,
        "clause": property_.clause,
        "formula": str(property_.formula),
        "traces": len(traces),
        "satisfied": sum(1 for value in satisfactions if value),
        "traces_distinct": len(distinct),
        "satisfied_distinct": sum(
            1 for value in distinct_satisfactions if value
        ),
        # A trace is non-vacuous for this property when the implication
        # antecedent occurs at least once somewhere in it.
        "nonvacuous_traces": sum(1 for item in bindings if item),
        "nonvacuous_traces_distinct": sum(
            1 for item in distinct_bindings if item
        ),
        "trigger_instances": sum(len(item) for item in bindings),
        "trigger_instances_distinct": sum(
            len(item) for item in distinct_bindings
        ),
        "trigger_steps": sum(
            properties.trigger_steps(property_.formula, trace)
            for trace in traces
        ),
    }


def _event_statistics(traces: list[list[Event]]) -> dict:
    """Count the actions and facts the report quotes next to the properties."""

    actions = Counter()
    outcomes = Counter()
    new_booking_steps = 0
    booked_state_steps = 0
    delete_slot_rejected = 0
    delete_slot_accepted = 0
    for trace in traces:
        for event in trace:
            actions[event.action] += 1
            outcomes[f"{event.action}->{'ok' if event.ok else 'rejected'}"] += 1
            if any(atom.startswith("new_booking:") for atom in event.props):
                new_booking_steps += 1
            if any(atom.startswith("booked:") for atom in event.props):
                booked_state_steps += 1
            if event.action == "delete_slot":
                if event.ok:
                    delete_slot_accepted += 1
                else:
                    delete_slot_rejected += 1
    return {
        "actions": dict(sorted(actions.items())),
        "action_outcomes": dict(sorted(outcomes.items())),
        "new_booking_steps": new_booking_steps,
        "booked_state_steps": booked_state_steps,
        "delete_slot_rejected": delete_slot_rejected,
        "delete_slot_accepted": delete_slot_accepted,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_ltl_properties_hold_on_all_p2_traces(evidence):
    """L1-L5 must hold on every trace; report non-vacuous counts as evidence."""

    started = time.monotonic()
    trace_dir, metadata = ensure_trace_dir()
    traces = read_traces(trace_dir)
    assert traces, f"no traces were found in {trace_dir}"
    distinct = _deduplicate(traces)

    failures: list[str] = []
    property_results: dict[str, dict] = {}
    for property_ in properties.PROPERTIES:
        result = _property_statistics(property_, traces, distinct)
        property_results[property_.identifier] = result
        if result["satisfied"] != len(traces):
            for index, trace in enumerate(traces):
                if evaluate(property_.formula, trace):
                    continue
                failures.append(
                    f"{property_.identifier} ({property_.clause}) failed on "
                    f"trace file {index + 1:04d}.json:\n"
                    + explain(property_.formula, trace)
                )
                break

    event_stats = _event_statistics(traces)
    weak_vacuity = [
        identifier
        for identifier, result in property_results.items()
        if result["nonvacuous_traces"] < 5
    ]
    payload = {
        **metadata,
        "seed": 4801,
        "trace_source": str(trace_dir),
        "traces": {
            "files": len(traces),
            "distinct": len(distinct),
            "steps": sum(len(trace) for trace in traces),
            "steps_distinct": sum(len(trace) for trace in distinct),
        },
        "properties": property_results,
        "events": event_stats,
        "nonvacuous_traces_under_5": weak_vacuity,
        "duration_seconds": None,  # filled in below, after evaluation
    }
    payload["duration_seconds"] = round(time.monotonic() - started, 3)
    evidence("ltl_results", payload)

    summary = " ".join(
        f"{identifier}={result['satisfied']}/{result['traces']}"
        f"(nonvac={result['nonvacuous_traces']},"
        f"triggers={result['trigger_instances']})"
        for identifier, result in property_results.items()
    )
    print(
        "ltl traces: files={files} distinct={distinct} steps={steps} "
        f"{summary}".format(**payload["traces"])
    )
    print(
        "ltl events: new_booking_steps={new_booking_steps} "
        "delete_slot_rejected={delete_slot_rejected} "
        "delete_slot_accepted={delete_slot_accepted}".format(**event_stats)
    )
    if weak_vacuity:
        print(
            "ltl warning: non-vacuous traces < 5 for "
            + ", ".join(sorted(weak_vacuity))
        )

    if failures:
        pytest.fail("\n\n".join(failures), pytrace=False)


def test_refinement_demo_is_reproducible(evidence):
    """Relax until every trace is accepted, then probe one restriction.

    The same seed must produce the same chain; every relaxation step must be
    monotone (it accepts at least the traces the previous formula accepted); and
    the final relaxed property must accept all traces.  The restriction probe is
    reported with all its F -> G / F -> X candidates so a reviewer can see
    whether the traces actually exercise the operator.
    """

    trace_dir, metadata = ensure_trace_dir()
    traces = read_traces(trace_dir)
    assert traces, f"no traces were found in {trace_dir}"

    first = refine.run_demo(traces, seed=4801)
    second = refine.run_demo(traces, seed=4801)
    assert first.to_dict() == second.to_dict(), (
        "the refinement demo is not reproducible for seed 4801"
    )

    assert len(first.steps) >= 2, (
        "the over-strong demo property was not violated by any trace; "
        "there is nothing to relax"
    )
    assert first.steps[0].satisfied < first.steps[0].total, (
        "the demo needs at least one counterexample to the initial property"
    )
    for previous, current in zip(first.steps, first.steps[1:]):
        assert current.satisfied >= previous.satisfied, (
            "a relaxation step must not lose accepted traces: "
            f"{previous.label}={previous.satisfied} -> "
            f"{current.label}={current.satisfied}"
        )
    assert first.steps[-1].satisfied == first.steps[-1].total, (
        "the relaxation chain did not reach a property accepted by every trace"
    )
    assert first.restricted is not None
    assert first.restriction_candidates
    assert first.restricted.satisfied <= first.restricted.total

    evidence("refinement", first.to_dict())
    print(
        "ltl refinement: steps={steps} restricted={restricted} "
        "counterexample={counterexample}".format(
            steps=len(first.steps),
            restricted=(
                None
                if first.restricted is None
                else f"{first.restricted.satisfied}/{first.restricted.total}"
            ),
            counterexample=bool(first.counterexample),
        )
    )
    print(refine.format_chain(first))


def test_explain_formats_the_first_violating_step():
    """A tiny guard on the reviewer-facing message used by the report."""

    trace = [
        Event(1, "book", True, frozenset({"booked:a1:s1", "slot:s1"})),
        Event(2, "delete_slot", True, frozenset({"booked:a1:s1"})),
    ]
    message = explain(properties.L4_BOOKED_SLOT_IS_PERMANENT, trace)
    assert "trace index 1" in message
    assert "step 2" in message
    assert "action=delete_slot" in message
