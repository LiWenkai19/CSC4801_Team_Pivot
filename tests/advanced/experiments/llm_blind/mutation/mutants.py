"""Five hand-written mutants for the P10 assertion-kill experiment.

Lecture 14 slide 28 categories: boundary/constant change, arithmetic change, and
removing a check.  The mutants are injected at import time by replacing the
module attribute with a mutated function; no file under ``backend/app`` is
modified.  The F1/F2 mutants are faithful source mutations of the real function
(``inspect.getsource`` -> textual replacement -> ``exec``) so they do not depend
on any particular session-double call order.

``apply_mutant("BASELINE")`` is a no-op used to measure the healthy baseline.
"""

from __future__ import annotations

import inspect
import textwrap

MUTANTS = {
    "F1_M1_floor_round": {
        "function": "F1",
        "description": "floor division becomes round(): arithmetic mutation",
    },
    "F1_M2_empty_required_zero": {
        "function": "F1",
        "description": "empty required skills score 100 -> 0: constant mutation",
    },
    "F1_M3_drop_trim": {
        "function": "F1",
        "description": "normalize_skills drops .strip(): boundary/normalisation check removed",
    },
    "F2_M4_skip_duration_check": {
        "function": "F2",
        "description": "the exactly-30-minutes check in book() is disabled",
    },
    "F2_M5_skip_missing_job_check": {
        "function": "F2",
        "description": "missing job is replaced by a synthetic job instead of NotFoundError",
    },
}


def _mutate_source(module, function_name, old, new):
    """Replace one literal fragment of a real function and install the result."""

    function = getattr(module, function_name)
    source = textwrap.dedent(inspect.getsource(function))
    if source.count(old) != 1:
        raise AssertionError(
            f"mutation anchor must occur exactly once in {function_name}: {old!r}"
        )
    mutated = source.replace(old, new, 1)
    # Exec into the real module globals (not a copy) so test monkeypatches of
    # module attributes such as ``utc_now`` keep affecting the mutated function,
    # exactly as they affect the production function.
    exec(compile(mutated, f"<mutant:{function_name}>", "exec"), module.__dict__)
    setattr(module, function_name, module.__dict__[function_name])


def _apply_f1_floor_round():
    import app.employer.matching as matching

    _mutate_source(
        matching,
        "match_score",
        "return (100 * len(candidate & required)) // len(required)",
        "return round(100 * len(candidate & required) / len(required))",
    )


def _apply_f1_empty_required_zero():
    import app.employer.matching as matching

    _mutate_source(matching, "match_score", "return 100", "return 0")


def _apply_f1_drop_trim():
    import app.employer.matching as matching

    def no_strip(skills):
        # Removed check: no surrounding-whitespace normalisation.  Matching's
        # own set() still deduplicates, which is irrelevant to this mutation.
        return [skill.lower() for skill in skills if skill]

    matching.normalize_skills = no_strip


def _apply_f2_skip_duration_check():
    import app.candidate.service as candidate

    _mutate_source(
        candidate,
        "book",
        "if slot.ends_at - slot.starts_at != timedelta(minutes=30):",
        "if False:",
    )


def _apply_f2_skip_missing_job_check():
    import app.candidate.service as candidate

    _mutate_source(
        candidate,
        "book",
        "        job = session.get(Job, application.job_id)\n"
        "        if job is None:\n"
        '            raise NotFoundError("Job not found")',
        "        job = session.get(Job, application.job_id)\n"
        "        if job is None:\n"
        "            job = type(\n"
        '                "SyntheticJob",\n'
        "                (),\n"
        '                {"id": application.job_id, "employer_id": slot.employer_id},\n'
        "            )()",
    )


_APPLIERS = {
    "F1_M1_floor_round": _apply_f1_floor_round,
    "F1_M2_empty_required_zero": _apply_f1_empty_required_zero,
    "F1_M3_drop_trim": _apply_f1_drop_trim,
    "F2_M4_skip_duration_check": _apply_f2_skip_duration_check,
    "F2_M5_skip_missing_job_check": _apply_f2_skip_missing_job_check,
}


def apply_mutant(mutant_id: str) -> None:
    if mutant_id == "BASELINE":
        return
    try:
        applier = _APPLIERS[mutant_id]
    except KeyError as error:
        raise SystemExit(f"unknown mutant: {mutant_id}") from error
    applier()
