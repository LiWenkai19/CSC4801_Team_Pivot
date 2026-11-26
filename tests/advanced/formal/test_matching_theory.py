"""SMT proofs for the FP-MATCH-1 score specification (``z3-solver``).

The theorems below are proved about :mod:`encoding`, the mathematical
specification.  They do **not** execute or verify the Python implementation;
``test_spec_to_code.py`` connects the same properties to the real
``app.employer.matching.match_score`` with a bounded exhaustive comparison.

Each proof negates the property under its precondition and asks Z3 for
``unsat``: there is no assignment satisfying the precondition that violates
the property.  The Hoare triple above each test names the same contract, and
the docstring cites the FP-MATCH-1 clause it comes from.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

import pytest
import z3

import encoding

PROOF_TIME_LIMIT_SECONDS = 2.0
SOLVER_TIMEOUT_MS = 5_000
RECORDS: list[dict] = []


@pytest.fixture(autouse=True)
def _evidence_on_teardown(evidence):
    """Persist a small summary after every test; the last write has all rows."""

    yield
    evidence(
        "matching_theory",
        {
            "time_limit_seconds": PROOF_TIME_LIMIT_SECONDS,
            "solver_timeout_ms": SOLVER_TIMEOUT_MS,
            "records": RECORDS,
        },
    )


def _solve(assertions: Iterable) -> tuple[z3.CheckSatResult, float, z3.Solver]:
    """Run one solver query and return (result, solver seconds, solver)."""

    solver = z3.Solver()
    solver.set("timeout", SOLVER_TIMEOUT_MS)
    solver.add(*assertions)
    started = time.perf_counter()
    result = solver.check()
    return result, time.perf_counter() - started, solver


def _record(*, theorem_id, title, kind, requirement, hoare, result, seconds):
    record = {
        "id": theorem_id,
        "title": title,
        "kind": kind,
        "requirement": requirement,
        "hoare": hoare,
        "result": str(result),
        "seconds": round(seconds, 6),
    }
    RECORDS.append(record)
    return record


def _prove_unsat(
    *, theorem_id, title, requirement, hoare, assertions
) -> None:
    """Assert that the *negation* of a property has no model."""

    result, seconds, solver = _solve(assertions)
    _record(
        theorem_id=theorem_id,
        title=title,
        kind="proof",
        requirement=requirement,
        hoare=hoare,
        result=result,
        seconds=seconds,
    )
    detail = ""
    if result == z3.sat:
        detail = f"; counterexample: {solver.model()}"
    elif result == z3.unknown:
        detail = f"; reason: {solver.reason_unknown()}"
    assert result == z3.unsat, (
        f"{theorem_id}: expected the negated property to be unsat, "
        f"got {result}{detail}"
    )
    assert seconds < PROOF_TIME_LIMIT_SECONDS, (
        f"{theorem_id}: proof took {seconds:.3f}s "
        f"(limit {PROOF_TIME_LIMIT_SECONDS}s)"
    )


def _find_counterexample(
    *, theorem_id, title, requirement, hoare, assertions
):
    """Assert that a deliberately false property *does* have a model."""

    result, seconds, solver = _solve(assertions)
    record = _record(
        theorem_id=theorem_id,
        title=title,
        kind="negative",
        requirement=requirement,
        hoare=hoare,
        result=result,
        seconds=seconds,
    )
    assert result == z3.sat, (
        f"{theorem_id}: the false property was expected to have a "
        f"counterexample, got {result}"
    )
    assert seconds < PROOF_TIME_LIMIT_SECONDS, (
        f"{theorem_id}: query took {seconds:.3f}s "
        f"(limit {PROOF_TIME_LIMIT_SECONDS}s)"
    )
    model = solver.model()
    record["model"] = str(model)
    print(f"{theorem_id} counterexample: {model}")
    return model, record


def _int_in_model(model: z3.ModelRef, expression) -> int:
    value = model.evaluate(expression, model_completion=True)
    assert z3.is_int_value(value), f"expected an integer value, got {value}"
    return value.as_long()


def _bool_in_model(model: z3.ModelRef, expression) -> bool:
    value = model.evaluate(expression, model_completion=True)
    assert z3.is_bool(value), f"expected a Boolean value, got {value}"
    return z3.is_true(value)


def _select(flags: list[z3.BoolRef], index: z3.ArithRef) -> z3.BoolRef:
    """``flags[index]`` for a symbolic in-range index, as a Boolean term."""

    expression = flags[-1]
    for position in range(len(flags) - 2, -1, -1):
        expression = z3.If(index == position, flags[position], expression)
    return expression


# {n >= 1 ∧ 0 <= k <= n}  score := (100*k) div n  {0 <= score <= 100}
def test_t1_score_is_bounded():
    """FP-MATCH-1: "The result MUST be an integer from 0 through 100"."""

    n = z3.Int("t1_n")
    k = z3.Int("t1_k")
    score = encoding.score_term(k, n)
    _prove_unsat(
        theorem_id="T1",
        title="0 <= score <= 100",
        requirement="FP-MATCH-1: integer result from 0 through 100",
        hoare=(
            "{n >= 1 ∧ 0 <= k <= n}  score := (100*k) div n  "
            "{0 <= score <= 100}"
        ),
        assertions=[
            n >= 1,
            k >= 0,
            k <= n,
            z3.Not(z3.And(score >= 0, score <= 100)),
        ],
    )


# {n >= 1 ∧ 0 <= k <= n}  score := (100*k) div n
#   {k = n -> score = 100  ∧  k = 0 -> score = 0}
def test_t2_saturation_is_one_hundred_and_zero():
    """FP-MATCH-1 example rows 1 and 3: full overlap is 100, no overlap is 0."""

    n = z3.Int("t2_n")
    k = z3.Int("t2_k")
    score = encoding.score_term(k, n)
    property_ = z3.And(
        z3.Implies(k == n, score == 100),
        z3.Implies(k == 0, score == 0),
    )
    _prove_unsat(
        theorem_id="T2",
        title="k = n -> score = 100 and k = 0 -> score = 0",
        requirement="FP-MATCH-1 example rows 1 and 3",
        hoare=(
            "{n >= 1 ∧ 0 <= k <= n}  score := (100*k) div n  "
            "{k = n -> score = 100 ∧ k = 0 -> score = 0}"
        ),
        assertions=[n >= 1, k >= 0, k <= n, z3.Not(property_)],
    )


# {n >= 1 ∧ 0 <= k <= n}  score := (100*k) div n
#   {score*n <= 100*k  ∧  100*k < (score+1)*n}
def test_t3_floor_definition():
    """FP-MATCH-1: score is exactly ``floor(100*|C∩R|/|R|)``."""

    n = z3.Int("t3_n")
    k = z3.Int("t3_k")
    score = encoding.score_term(k, n)
    property_ = z3.And(
        score * n <= 100 * k,
        100 * k < (score + 1) * n,
    )
    _prove_unsat(
        theorem_id="T3",
        title="floor definition: score*n <= 100k < (score+1)*n",
        requirement="FP-MATCH-1: floor(100*|C∩R|/|R|)",
        hoare=(
            "{n >= 1 ∧ 0 <= k <= n}  score := (100*k) div n  "
            "{score*n <= 100*k ∧ 100*k < (score+1)*n}"
        ),
        assertions=[n >= 1, k >= 0, k <= n, z3.Not(property_)],
    )


# {n >= 1 ∧ 0 <= k1 <= k2 <= n}
#   score1 := (100*k1) div n; score2 := (100*k2) div n
#   {score1 <= score2}
def test_t4_score_is_monotonic_in_overlap():
    """FP-MATCH-1 ordering: more shared required skills cannot lower the score."""

    n = z3.Int("t4_n")
    k1 = z3.Int("t4_k1")
    k2 = z3.Int("t4_k2")
    score1 = encoding.score_term(k1, n)
    score2 = encoding.score_term(k2, n)
    _prove_unsat(
        theorem_id="T4",
        title="k1 <= k2 -> score(k1) <= score(k2) for the same n",
        requirement="FP-MATCH-1: rank by the overlap percentage",
        hoare=(
            "{n >= 1 ∧ 0 <= k1 <= k2 <= n}  "
            "score1 := (100*k1) div n; score2 := (100*k2) div n  "
            "{score1 <= score2}"
        ),
        assertions=[
            n >= 1,
            k1 >= 0,
            k1 <= k2,
            k2 <= n,
            z3.Not(score1 <= score2),
        ],
    )


# {|R| >= 1}  score := score_of_sets(C, R)  {score = 100 ↔ R ⊆ C}
def test_t5_full_score_iff_required_subset_candidate():
    """FP-MATCH-1: only 100 when every required skill is present."""

    candidate, required = encoding.set_pair("t5")
    _, n = encoding.set_counts(candidate, required)
    score = encoding.set_score(candidate, required)
    required_subset_candidate = encoding.subset(required, candidate)
    property_ = z3.And(
        z3.Implies(score == 100, required_subset_candidate),
        z3.Implies(required_subset_candidate, score == 100),
    )
    _prove_unsat(
        theorem_id="T5",
        title="score = 100 iff R subset C",
        requirement="FP-MATCH-1: full score semantics",
        hoare=(
            "{|R| >= 1}  score := score_of_sets(C, R)  "
            "{score = 100 ↔ R ⊆ C}"
        ),
        assertions=[n >= 1, z3.Not(property_)],
    )


# {|R| = n ∧ x ∉ R ∧ x ∉ C}
#   score := score_of_sets(C, R); score' := score_of_sets(C ∪ {x}, R)
#   {score' = score}
def test_t6_unrelated_skill_does_not_change_score():
    """FP-MATCH-1: adding a skill that is not required cannot move the score."""

    candidate, required = encoding.set_pair("t6")
    index = z3.Int("t6_i")
    element_required = _select(required, index)
    element_in_candidate = _select(candidate, index)
    enriched = [
        z3.Or(flag, index == position)
        for position, flag in enumerate(candidate)
    ]
    original_score = encoding.set_score(candidate, required)
    enriched_score = encoding.set_score(enriched, required)
    _prove_unsat(
        theorem_id="T6",
        title="adding x not in R to C leaves the score unchanged",
        requirement="FP-MATCH-1: only C ∩ R contributes",
        hoare=(
            "{|R| = n ∧ x ∉ R ∧ x ∉ C}  "
            "score := score_of_sets(C, R); "
            "score' := score_of_sets(C ∪ {x}, R)  {score' = score}"
        ),
        assertions=[
            index >= 0,
            index < encoding.UNIVERSE_SIZE,
            z3.Not(element_required),
            z3.Not(element_in_candidate),
            z3.Not(enriched_score == original_score),
        ],
    )


# {n = 2 ∧ k = 1}  score := (100*k) div n  {score = 50}
def test_t7_example_row_two_is_fifty():
    """FP-MATCH-1 example row 2: one of two required skills gives 50."""

    n = z3.Int("t7_n")
    k = z3.Int("t7_k")
    score = encoding.score_term(k, n)
    _prove_unsat(
        theorem_id="T7",
        title="n = 2 and k = 1 -> score = 50",
        requirement="FP-MATCH-1 example row 2",
        hoare="{n = 2 ∧ k = 1}  score := (100*k) div n  {score = 50}",
        assertions=[n == 2, k == 1, z3.Not(score == 50)],
    )


# {n >= 1 ∧ 0 <= k <= n}
#   score := (100*k) div n; rounded := (200*k + n) div (2*n)
#   {score = rounded}                       (deliberately false)
def test_n1_rounding_is_not_the_floor_definition():
    """Negative control: floor and round-half-up are not the same function.

    If this query were ``unsat`` the encoding would be trivially true, or
    ``/`` would be real rather than integer division, and the T3 proof would
    be meaningless.  ``sat`` plus a printed counterexample shows it is not.
    """

    n = z3.Int("n1_n")
    k = z3.Int("n1_k")
    floor_score = encoding.score_term(k, n)
    rounded_score = encoding.int_div(200 * k + n, 2 * n)
    claim = floor_score == rounded_score
    model, record = _find_counterexample(
        theorem_id="N1",
        title="floor(100k/n) = round_half_up(100k/n)",
        requirement="negative control: false rounding identity",
        hoare=(
            "{n >= 1 ∧ 0 <= k <= n}  "
            "floor := (100*k) div n; rounded := (200*k+n) div (2*n)  "
            "{floor = rounded}  (false)"
        ),
        assertions=[n >= 1, k >= 0, k <= n, z3.Not(claim)],
    )
    n_value = _int_in_model(model, n)
    k_value = _int_in_model(model, k)
    floor_value = _int_in_model(model, floor_score)
    rounded_value = _int_in_model(model, rounded_score)
    assert 1 <= n_value and 0 <= k_value <= n_value
    assert floor_value != rounded_value
    record["counterexample"] = {
        "n": n_value,
        "k": k_value,
        "floor": floor_value,
        "round_half_up": rounded_value,
    }


# {|R| >= 1 ∧ |C| >= 1}
#   score := score_of_sets(C, R); wrong := (100*|C∩R|) div |C|
#   {score = wrong}                         (deliberately false)
def test_n2_candidate_size_is_not_the_denominator():
    """Negative control: the requirement count, not the candidate count, divides.

    A plausible implementation mistake divides by ``|C|``.  On ``C = {a}``
    and ``R = {a, b}`` the specification says 50 while that variant says 100,
    so the encoding is not merely restating a tautology.
    """

    candidate, required = encoding.set_pair("n2")
    k, n = encoding.set_counts(candidate, required)
    candidate_size = encoding.cardinality(candidate)
    spec_score = encoding.set_score(candidate, required)
    wrong_score = encoding.int_div(100 * k, candidate_size)
    claim = spec_score == wrong_score
    model, record = _find_counterexample(
        theorem_id="N2",
        title="score = floor(100*|C∩R| / |C|)",
        requirement="negative control: false denominator",
        hoare=(
            "{|R| >= 1 ∧ |C| >= 1}  "
            "score := score_of_sets(C, R); "
            "wrong := (100*|C∩R|) div |C|  {score = wrong}  (false)"
        ),
        assertions=[n >= 1, candidate_size >= 1, z3.Not(claim)],
    )
    n_value = _int_in_model(model, n)
    k_value = _int_in_model(model, k)
    candidate_size_value = _int_in_model(model, candidate_size)
    spec_value = _int_in_model(model, spec_score)
    wrong_value = _int_in_model(model, wrong_score)
    assert n_value >= 1 and candidate_size_value >= 1
    assert spec_value != wrong_value
    record["counterexample"] = {
        "candidate_bits": [
            _bool_in_model(model, flag) for flag in candidate
        ],
        "required_bits": [
            _bool_in_model(model, flag) for flag in required
        ],
        "n": n_value,
        "k": k_value,
        "candidate_size": candidate_size_value,
        "spec_score": spec_value,
        "wrong_score": wrong_value,
    }
