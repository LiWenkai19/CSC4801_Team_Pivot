"""Bounded exhaustive link between the FP-MATCH-1 specification and its code.

The SMT proofs in ``test_matching_theory.py`` are about the specification
formula encoded in :mod:`encoding`.  A proof about a formula says nothing
about whether the Python function implements that formula, so this module
runs the *real* ``app.employer.matching.match_score`` on every subset pair
of a five-element universe (2^5 x 2^5 = 1024 pairs) and compares each result
with the Z3 encoding evaluated on the same pair and with an independent
``floor`` formula derived from the requirement text.

It then replays every proven T-property on those concrete pairs with the
real implementation.  These are exhaustive-for-the-bound checks, **not**
proofs; the report keeps that distinction.
"""

from __future__ import annotations

import time

import pytest

import encoding
from app.employer.matching import match_score

UNIVERSE = ("a", "b", "c", "d", "e")
SUBSET_COUNT = 1 << len(UNIVERSE)  # 32
PAIR_COUNT = SUBSET_COUNT * SUBSET_COUNT  # 1024


def _subsets() -> list[tuple[str, ...]]:
    """All subsets of ``UNIVERSE``; the list index is the membership bit mask."""

    return [
        tuple(
            skill
            for index, skill in enumerate(UNIVERSE)
            if mask & (1 << index)
        )
        for mask in range(SUBSET_COUNT)
    ]


SUBSETS = _subsets()


@pytest.fixture(scope="module")
def observations() -> list[dict]:
    """Score every subset pair with the real function and the Z3 encoding."""

    assignments = [
        (candidate_mask, required_mask)
        for candidate_mask in range(SUBSET_COUNT)
        for required_mask in range(SUBSET_COUNT)
    ]
    encoded_scores = encoding.evaluate_scores(
        assignments, size=len(UNIVERSE)
    )
    records = []
    for (candidate_mask, required_mask), encoded in zip(
        assignments, encoded_scores
    ):
        candidate = SUBSETS[candidate_mask]
        required = SUBSETS[required_mask]
        overlap = len(set(candidate) & set(required))
        required_count = len(required)
        python_formula = (
            100
            if required_count == 0
            else (100 * overlap) // required_count
        )
        records.append(
            {
                "candidate_mask": candidate_mask,
                "required_mask": required_mask,
                "candidate": candidate,
                "required": required,
                "k": overlap,
                "n": required_count,
                "actual": match_score(list(candidate), list(required)),
                "encoded": encoded,
                "python_formula": python_formula,
            }
        )
    return records


def _describe(record: dict) -> str:
    return (
        f"candidate={list(record['candidate'])} "
        f"required={list(record['required'])} "
        f"n={record['n']} k={record['k']} "
        f"actual={record['actual']} encoded={record['encoded']} "
        f"python_formula={record['python_formula']}"
    )


def _record_property(evidence, theorem, *, checks, guarded, seconds, **extra):
    evidence(
        f"bounded_{theorem}",
        {
            "theorem": theorem,
            "mode": "bounded exhaustive over 1024 subset pairs",
            "pair_checks": checks,
            "guarded_out": guarded,
            "seconds": round(seconds, 6),
            **extra,
        },
    )


# FP-MATCH-1 examples: 100 on full overlap, 50 on one of two, 0 on no
# overlap, 100 for an empty required list (hand-computed expectations).
def test_requirement_examples(evidence):
    examples = [
        (["Python", "SQL"], ["Python", "SQL"], 100, "required example row 1"),
        (["Python"], ["Python", "SQL"], 50, "required example row 2"),
        (["Rust"], ["Python", "SQL"], 0, "required example row 3"),
        (["Go", "Rust"], [], 100, "required example row 4"),
    ]
    results = []
    for candidate, required, expected, source in examples:
        actual = match_score(candidate, required)
        assert actual == expected, (
            f"{source}: expected {expected}, got {actual} "
            f"(candidate={candidate}, required={required})"
        )
        results.append(
            {
                "candidate": candidate,
                "required": required,
                "expected": expected,
                "actual": actual,
                "source": source,
            }
        )
    evidence("requirement_examples", {"cases": results})


# {|C|, |R| <= 5}  score := match_score(C, R)
#   {score = z3_encoding(C, R) = floor(100*|C∩R|/|R|)}
def test_all_1024_pairs_agree_with_z3_encoding(observations, evidence):
    """Every subset pair of ``{a,b,c,d,e}`` gives the same score on both sides."""

    assert len(observations) == PAIR_COUNT
    encoding_mismatches = [
        record
        for record in observations
        if record["actual"] != record["encoded"]
    ]
    formula_mismatches = [
        record
        for record in observations
        if record["actual"] != record["python_formula"]
    ]
    assert not encoding_mismatches, (
        "match_score disagrees with the SMT encoding: "
        + _describe(encoding_mismatches[0])
    )
    assert not formula_mismatches, (
        "match_score disagrees with the requirement formula: "
        + _describe(formula_mismatches[0])
    )
    histogram: dict[str, int] = {}
    for record in observations:
        key = str(record["actual"])
        histogram[key] = histogram.get(key, 0) + 1
    evidence(
        "spec_to_code_pairs",
        {
            "universe": list(UNIVERSE),
            "subsets": len(UNIVERSE),
            "pairs": len(observations),
            "z3_encoding_mismatches": 0,
            "requirement_formula_mismatches": 0,
            "score_histogram": histogram,
        },
    )


# {subset pairs of U, |U| = 5}  score := match_score(C, R)  {0 <= score <= 100}
def test_bounded_t1_score_range(observations, evidence):
    started = time.perf_counter()
    for record in observations:
        assert isinstance(record["actual"], int), _describe(record)
        assert 0 <= record["actual"] <= 100, _describe(record)
    seconds = time.perf_counter() - started
    _record_property(
        evidence, "T1", checks=len(observations), guarded=0, seconds=seconds
    )


# {subset pairs of U, |U| = 5, |R| >= 1}  score := match_score(C, R)
#   {k = n -> score = 100 ∧ k = 0 -> score = 0}
def test_bounded_t2_saturation(observations, evidence):
    started = time.perf_counter()
    checked = 0
    guarded = 0
    for record in observations:
        if record["n"] == 0:
            guarded += 1
            continue
        if record["k"] == record["n"]:
            assert record["actual"] == 100, _describe(record)
        if record["k"] == 0:
            assert record["actual"] == 0, _describe(record)
        checked += 1
    seconds = time.perf_counter() - started
    assert checked == 992 and guarded == 32
    _record_property(
        evidence, "T2", checks=checked, guarded=guarded, seconds=seconds
    )


# {subset pairs of U, |U| = 5, |R| >= 1}  score := match_score(C, R)
#   {score*|R| <= 100*|C∩R| < (score+1)*|R|}
def test_bounded_t3_floor_definition(observations, evidence):
    started = time.perf_counter()
    checked = 0
    guarded = 0
    for record in observations:
        if record["n"] == 0:
            guarded += 1
            continue
        score = record["actual"]
        k = record["k"]
        n = record["n"]
        assert score * n <= 100 * k < (score + 1) * n, _describe(record)
        checked += 1
    seconds = time.perf_counter() - started
    assert checked == 992
    _record_property(
        evidence, "T3", checks=checked, guarded=guarded, seconds=seconds
    )


# {subset pairs of U, |U| = 5, |R| >= 1}
#   {k1 <= k2 -> match_score(C1, R) <= match_score(C2, R)} for equal |R|
def test_bounded_t4_monotonicity(observations, evidence):
    started = time.perf_counter()
    observed: dict[tuple[int, int], set[int]] = {}
    guarded = 0
    for record in observations:
        if record["n"] == 0:
            guarded += 1
            continue
        observed.setdefault((record["n"], record["k"]), set()).add(
            record["actual"]
        )

    # The score must depend only on the two counts; otherwise comparing
    # scores for k1 <= k2 would not be well-defined.
    for (n, k), scores in sorted(observed.items()):
        assert len(scores) == 1, (
            f"score is not deterministic for n={n}, k={k}: {sorted(scores)}"
        )

    # Every possible (n, k) with 1 <= n <= 5, 0 <= k <= n must appear.
    expected_keys = {
        (n, k) for n in range(1, len(UNIVERSE) + 1) for k in range(n + 1)
    }
    assert set(observed) == expected_keys

    comparisons = 0
    for n in range(1, len(UNIVERSE) + 1):
        for k1 in range(n + 1):
            for k2 in range(k1, n + 1):
                low = next(iter(observed[(n, k1)]))
                high = next(iter(observed[(n, k2)]))
                assert low <= high, (
                    f"monotonicity failed for n={n}, k1={k1}, "
                    f"k2={k2}: {low} > {high}"
                )
                comparisons += 1
    seconds = time.perf_counter() - started
    assert len(observed) == 20 and comparisons == 55
    _record_property(
        evidence,
        "T4",
        checks=comparisons,
        guarded=guarded,
        seconds=seconds,
        count_combinations=len(observed),
        observed_pairs=len(observations) - guarded,
    )


# {subset pairs of U, |U| = 5, |R| >= 1}  score := match_score(C, R)
#   {score = 100 ↔ R ⊆ C}
def test_bounded_t5_full_score_iff_subset(observations, evidence):
    started = time.perf_counter()
    checked = 0
    guarded = 0
    for record in observations:
        if record["n"] == 0:
            guarded += 1
            continue
        required_subset_candidate = set(record["required"]) <= set(
            record["candidate"]
        )
        assert (record["actual"] == 100) == required_subset_candidate, (
            _describe(record)
        )
        checked += 1
    seconds = time.perf_counter() - started
    assert checked == 992
    _record_property(
        evidence, "T5", checks=checked, guarded=guarded, seconds=seconds
    )


# {subset pairs of U, |U| = 5, x ∈ U, x ∉ R, x ∉ C}
#   {match_score(C ∪ {x}, R) = match_score(C, R)}
def test_bounded_t6_unrelated_skill(observations, evidence):
    started = time.perf_counter()
    additions = 0
    for record in observations:
        candidate = set(record["candidate"])
        required = set(record["required"])
        for skill in UNIVERSE:
            if skill in required or skill in candidate:
                continue
            enriched = sorted(candidate | {skill})
            actual = match_score(enriched, list(required))
            assert actual == record["actual"], (
                f"adding unrelated skill {skill!r} changed the score: "
                f"{record['actual']} -> {actual}; " + _describe(record)
            )
            additions += 1
    seconds = time.perf_counter() - started
    assert additions == 1280
    _record_property(
        evidence, "T6", checks=additions, guarded=0, seconds=seconds
    )


# {subset pairs of U, |U| = 5, |R| = 2, |C∩R| = 1}  score := match_score(C, R)
#   {score = 50}
def test_bounded_t7_example_row_two(observations, evidence):
    started = time.perf_counter()
    checked = 0
    for record in observations:
        if record["n"] == 2 and record["k"] == 1:
            assert record["actual"] == 50, _describe(record)
            checked += 1
    seconds = time.perf_counter() - started
    assert checked == 160
    _record_property(
        evidence, "T7", checks=checked, guarded=0, seconds=seconds
    )
