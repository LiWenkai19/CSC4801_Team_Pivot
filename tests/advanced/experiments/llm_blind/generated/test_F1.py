r"""
Blind test generation — Contract F1: ``app.employer.matching.match_score``
=========================================================================

Source of truth: ``tests/advanced/experiments/llm_blind/contracts/F1.md`` only.
While writing this file no production code, existing test, or application helper
was read or executed, and no expected value below is produced by calling
``match_score``, ``normalize_skills`` or any other application function. Every
number is derived from the FP-MATCH-1 formula plus hand arithmetic, written in
the comment next to the assertion.

Formula (contract section 3), on the NORMALISED sets ``C`` (candidate) and
``R`` (required)::

    score = 100                          if |R| == 0
    score = floor(100 * |C & R| / |R|)   otherwise        (== 100 * k // n)

Normalisation (contract section 2), applied to each list independently:
strip -> lower() -> drop entries that are empty after strip -> deduplicate.


PARTITION MAP  (prompt step 1)
-------------------------------------------------------------------------------
P1  Valid / ordinary
    P1a full overlap, C == R, k = n > 0                                -> 100
    P1b partial overlap, 0 < k < n                                     -> floor
    P1c disjoint, k = 0, n > 0                                         -> 0
    P1d required is a proper subset of candidate, C contains R         -> 100
    P1e candidate carries skills irrelevant to R (denominator is |R|,
        never |C|, |C u R| or |C - R|)                                 -> |R| based
P2  Boundary
    P2a |R| = 0 with |C| > 0                                           -> 100
    P2b |R| = 0 with |C| = 0                                           -> 100
    P2c |C| = 0 with |R| > 0                                           -> 0
    P2d k = n > 0 (every required skill matched)                       -> 100
    P2e k = 0 with |R| > 0                                             -> 0
    P2f floor boundary, |R| = 3, k = 2                                 -> 66
    P2g floor boundary, |R| = 3, k = 1                                 -> 33
    P2h floor boundary for denominators 6, 7, 8, 9, 11, 12, 13, 16 etc.
    P2i 100 * k // n < 1, i.e. floor collapses to 0 (|R| = 200, k = 1)  -> 0
P3  Normalisation (contract section 2; two inputs with the same normalised
    (C, R) must return the same score)
    P3a surrounding whitespace: spaces, tabs, newlines
    P3b case variants, including mixed case inside one list
    P3c duplicates inside either list (must touch neither k nor n)
    P3d empty strings dropped
    P3e whitespace-only entries dropped
    P3f combined case/space/duplicate noise: contract section 4 hand example
P4  Invariance
    P4a permutation of either list leaves the score unchanged
    P4b duplication in either list leaves the score unchanged
P5  Unicode / symbols
    P5a non-ASCII skill names, unchanged by str.lower()                -> 100
    P5b symbol skills "C++", "C#", ".NET", "Node.js"                   -> lower()
    P5c str.lower() is not casefold(): "SS" -> "ss" but the sharp s
        character is unchanged, so those two skills are distinct       -> 0
    P5d U+0130 lowercases to "i" + U+0307, which is not "i"            -> 0
P6  Type / range envelope (contract section 3)
    P6a type(result) is int (excludes bool and float) — asserted on every case
    P6b 0 <= result <= 100 — asserted on every case
P7  Purity / determinism (contract section 3)
    P7a the caller's input lists are not mutated
    P7b repeated calls return the same value (no hidden state, no I/O)
P8  Out of contract (a documented gap, not a behaviour partition)
    P8a None, a bare str, or non-str elements: the contract specifies no
        behaviour -> recorded as ambiguity A1, no exception is demanded.


AMBIGUITIES RECORDED AND HOW THEY WERE RESOLVED  (prompt step 6)
-------------------------------------------------------------------------------
A1. Inputs outside ``list[str]`` (None, a bare string, a list of ints) have no
    specified behaviour; contract section 6.1 calls them undefined. This file
    therefore asserts neither an exception nor a value for them (see P8a).
A2. "Lowercase" means ``str.lower()``, not ``casefold()`` (contract sections 2.2
    and 6.2). Hence "SS" and the sharp s are DIFFERENT skills, and U+0130 is not
    "I" after lowercasing; those pairs are asserted as non-matching (score 0),
    never as equal.
A3. Internal whitespace is preserved (contract section 6.3), so "data science"
    and "data  science" (two interior spaces) never match each other.
A4. The special case |R| = 0 is measured on the NORMALISED set R, because
    section 2 declares normalisation part of the contract and section 3 speaks
    of the resulting sets. A required list of ["", "  "] therefore has |R| = 0
    and scores 100 for any candidate.
A5. ``bool`` subclasses ``int``; section 6.4 constrains only the return to be
    ``int``. Every check here uses ``type(result) is int`` (never isinstance) so
    that True/False and floats are rejected. No non-int result is legitimate.
A6. "No mutation of the input lists" (section 3) constrains the caller's lists.
    Mutating a private copy, sorting a copy, etc. is allowed and not tested.
A7. Only whitespace at the two ends of an entry is removed; an entry that is
    entirely whitespace becomes empty and is dropped rather than kept as "".
    No other string preprocessing (no collapsing, no casefold, no accent
    stripping) is assumed anywhere.
A8. |C & R| is exact string equality on the normalised forms; no stemming,
    fuzzy matching, synonyms or prefixes are assumed (contract section 2).
"""

import pytest

from app.employer.matching import match_score


# ---------------------------------------------------------------------------
# Local assertion helper. It computes NO expected value and calls no
# application function; it only checks the section 3 type/range envelope.
# ---------------------------------------------------------------------------
def _check_contract_score(result: object) -> None:
    """Enforce P6: an exact ``int`` in ``[0, 100]`` (contract section 3)."""
    # type(...) is int, not isinstance: bool subclasses int and must not pass.
    assert type(result) is int, (
        f"match_score must return exactly int, got {type(result).__name__}"
    )
    assert 0 <= result <= 100, f"match_score must return 0..100, got {result!r}"


# ---------------------------------------------------------------------------
# P1 / P2 — the four required FP-MATCH-1 examples (contract section 4)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("candidate", "required", "expected"),
    [
        # FP-MATCH-1 example 1: k=2, n=2 -> 100*2//2 = 100
        (["Python", "SQL"], ["Python", "SQL"], 100),
        # FP-MATCH-1 example 2: k=1, n=2 -> 100*1//2 = 50
        (["Python"], ["Python", "SQL"], 50),
        # FP-MATCH-1 example 3: k=0, n=2 -> 100*0//2 = 0
        (["Rust"], ["Python", "SQL"], 0),
        # FP-MATCH-1 example 4: |R| = 0 -> special case, 100 whatever C is
        (["Python", "SQL", "Rust"], [], 100),
    ],
    ids=[
        "full-overlap-100",
        "partial-overlap-50",
        "disjoint-0",
        "empty-required-100",
    ],
)
def test_fp_match_1_required_examples(candidate, required, expected):
    result = match_score(candidate, required)
    _check_contract_score(result)
    assert result == expected


def test_fp_match_1_normalisation_example():
    """Contract section 4, second hand calculation.

    candidate [" SQL ", "sql", "Python", ""] -> C = {"sql", "python"}
    required  ["SQL", "  ", "python "]       -> R = {"sql", "python"}
    k = |{sql, python} & {sql, python}| = 2, n = |R| = 2
    100 * 2 // 2 = 100
    """
    result = match_score([" SQL ", "sql", "Python", ""], ["SQL", "  ", "python "])
    _check_contract_score(result)
    assert result == 100


# ---------------------------------------------------------------------------
# P2a-P2c — empty-list boundaries
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("candidate", "required", "expected"),
    [
        # |R| = 0 with |C| = 0 -> special case => 100   (P2b)
        ([], [], 100),
        # k=0, n=1 -> 100*0//1 = 0   (P2c: empty candidate, non-empty required)
        ([], ["Python"], 0),
        # k=0, n=2 -> 100*0//2 = 0
        ([], ["Python", "SQL"], 0),
        # k=0, n=3 -> 100*0//3 = 0
        ([], ["Python", "SQL", "Go"], 0),
        # |R| = 0 -> 100 even though k = 0
        (["Python"], [], 100),
        # |R| = 0 -> 100, candidate content irrelevant
        (["Rust", "Go", "Cobol"], [], 100),
        # both lists normalise to the empty set: |R| = 0 -> 100
        (["  ", "\t", "\n"], [], 100),
        # C = {} after strip, R = {"sql"}: k=0, n=1 -> 100*0//1 = 0
        (["  ", "\t"], ["sql"], 0),
        # R = ["  ", "\t", ""] normalises to {} -> |R| = 0 -> 100  (A4)
        (["sql"], ["  ", "\t", ""], 100),
    ],
    ids=[
        "empty-and-empty-100",
        "empty-candidate-only-100",
        "empty-candidate-required-1",
        "empty-candidate-required-2",
        "empty-candidate-required-3",
        "empty-required-nonempty-candidate-100",
        "empty-required-3-skills-100",
        "both-whitespace-only-100",
        "whitespace-candidate-real-required-0",
        "whitespace-only-required-100",
    ],
)
def test_empty_list_boundaries(candidate, required, expected):
    result = match_score(candidate, required)
    _check_contract_score(result)
    assert result == expected


# ---------------------------------------------------------------------------
# P2d / P1a / P1d — full coverage of R scores 100
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("candidate", "required"),
    [
        # k=1, n=1 -> 100*1//1 = 100
        (["Python"], ["Python"]),
        # k=2, n=2 -> 100*2//2 = 100
        (["Python", "SQL"], ["SQL", "Python"]),
        # k=3, n=3 -> 100*3//3 = 100
        (["Python", "SQL", "Go"], ["Go", "Python", "SQL"]),
        # P1d: C contains R and four extra skills; k=2, n=2 -> 100
        (["Python", "SQL", "Rust", "Go", "Java", "C#"], ["SQL", "Python"]),
        # P1d: single required skill, many extra candidate skills; k=1, n=1 -> 100
        (["Rust", "Go", "SQL", "Java", "Python", "C++"], ["SQL"]),
        # P2d: duplicates do not push k above n; k=2, n=2 -> 100
        (["Python", "Python", "SQL", "SQL"], ["Python", "SQL"]),
    ],
    ids=[
        "single-skill",
        "two-skills",
        "three-skills",
        "superset-of-required-2",
        "superset-of-required-1",
        "duplicated-but-complete",
    ],
)
def test_candidate_covers_required(candidate, required):
    result = match_score(candidate, required)
    _check_contract_score(result)
    # k = n in every row above -> 100 * n // n = 100
    assert result == 100


# ---------------------------------------------------------------------------
# P1e — the denominator is |R|, never |C| and never |C u R|
# ---------------------------------------------------------------------------
def test_denominator_is_required_count_not_candidate_count():
    """Candidate has 6 skills, required has 2, both required skills present.

    C = {python, sql, rust, go, cobol, ada}, R = {python, sql}
    k = 2, n = |R| = 2 -> 100 * 2 // 2 = 100
    Using |C| = 6 or |C u R| = 6 as the denominator would give 100*2//6 = 33,
    so this case separates the |R| denominator from both alternatives.
    """
    candidate = ["python", "sql", "rust", "go", "cobol", "ada"]
    required = ["python", "sql"]
    result = match_score(candidate, required)
    _check_contract_score(result)
    assert result == 100


def test_numerator_counts_only_required_skills():
    """Candidate has 5 skills, only one of them is required.

    C = {python, rust, go, ada, cobol}, R = {python, sql}
    k = |{python}| = 1, n = 2 -> 100 * 1 // 2 = 50
    """
    candidate = ["python", "rust", "go", "ada", "cobol"]
    required = ["python", "sql"]
    result = match_score(candidate, required)
    _check_contract_score(result)
    assert result == 50


# ---------------------------------------------------------------------------
# P2f-P2i — floor rounding, hand-pinned small denominators
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("candidate", "required", "expected"),
    [
        # ---- |R| = 3 -----------------------------------------------------
        # k=0, n=3 -> 100*0//3 = 0
        (["Go"], ["python", "sql", "rust"], 0),
        # k=1, n=3 -> 100*1//3 = 33   (100/3 = 33.33... floored)
        (["python"], ["python", "sql", "rust"], 33),
        # k=2, n=3 -> 100*2//3 = 66   (66.66... floored: contract section 5)
        (["python", "sql"], ["python", "sql", "rust"], 66),
        # k=3, n=3 -> 100*3//3 = 100
        (["python", "sql", "rust"], ["python", "sql", "rust"], 100),
        # ---- |R| = 4 -----------------------------------------------------
        # k=1, n=4 -> 100*1//4 = 25
        (["python"], ["python", "a", "b", "c"], 25),
        # k=2, n=4 -> 100*2//4 = 50
        (["python", "a"], ["python", "a", "b", "c"], 50),
        # k=3, n=4 -> 100*3//4 = 75
        (["python", "a", "b"], ["python", "a", "b", "c"], 75),
        # ---- |R| = 6 -----------------------------------------------------
        # k=1, n=6 -> 100*1//6 = 16   (16.66...)
        (["python"], ["python", "a", "b", "c", "d", "e"], 16),
        # k=5, n=6 -> 100*5//6 = 83   (83.33...)
        (["python", "a", "b", "c", "d"], ["python", "a", "b", "c", "d", "e"], 83),
        # ---- |R| = 7 -----------------------------------------------------
        # k=1, n=7 -> 100*1//7 = 14   (14.28...)
        (["python"], ["python", "a", "b", "c", "d", "e", "f"], 14),
        # k=6, n=7 -> 100*6//7 = 85   (85.71...)
        (
            ["python", "a", "b", "c", "d", "e"],
            ["python", "a", "b", "c", "d", "e", "f"],
            85,
        ),
        # ---- |R| = 8 -----------------------------------------------------
        # k=3, n=8 -> 100*3//8 = 37   (37.5, exact .5 floored down)
        (["python", "a", "b"], ["python", "a", "b", "c", "d", "e", "f", "g"], 37),
        # ---- |R| = 9 -----------------------------------------------------
        # k=4, n=9 -> 100*4//9 = 44   (44.44...)
        (["python", "a", "b", "c"], ["python", "a", "b", "c", "d", "e", "f", "g", "h"], 44),
        # k=8, n=9 -> 100*8//9 = 88   (88.88...)
        (
            ["python", "a", "b", "c", "d", "e", "f", "g"],
            ["python", "a", "b", "c", "d", "e", "f", "g", "h"],
            88,
        ),
        # ---- |R| = 11 ----------------------------------------------------
        # k=1, n=11 -> 100*1//11 = 9   (9.09...)
        (["python"], ["python", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j"], 9),
        # k=10, n=11 -> 100*10//11 = 90   (90.90...)
        (
            ["python", "a", "b", "c", "d", "e", "f", "g", "h", "i"],
            ["python", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j"],
            90,
        ),
        # ---- |R| = 12 ----------------------------------------------------
        # k=5, n=12 -> 100*5//12 = 41   (41.66...)
        (["python", "a", "b", "c", "d"], ["python", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"], 41),
        # k=12, n=12 handled by the k=n test above; k=11, n=12 -> 1100//12 = 91 (91.66)
        (
            ["python", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j"],
            ["python", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"],
            91,
        ),
        # ---- |R| = 13 ----------------------------------------------------
        # k=12, n=13 -> 100*12//13 = 92   (92.30...)
        (
            ["python", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k"],
            ["python", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l"],
            92,
        ),
        # ---- |R| = 200, floor collapses to 0 -----------------------------
        # k=1, n=200 -> 100*1//200 = 0   (0.5 floored to 0)  [P2i]
        (["python"], ["python"] + [f"s{i}" for i in range(199)], 0),
        # k=199, n=200 -> 100*199//200 = 99   (99.5 floored)
        (["python"] + [f"s{i}" for i in range(198)], ["python"] + [f"s{i}" for i in range(199)], 99),
    ],
    ids=[
        "n3-k0-0",
        "n3-k1-33",
        "n3-k2-66",
        "n3-k3-100",
        "n4-k1-25",
        "n4-k2-50",
        "n4-k3-75",
        "n6-k1-16",
        "n6-k5-83",
        "n7-k1-14",
        "n7-k6-85",
        "n8-k3-37",
        "n9-k4-44",
        "n9-k8-88",
        "n11-k1-9",
        "n11-k10-90",
        "n12-k5-41",
        "n12-k11-91",
        "n13-k12-92",
        "n200-k1-0",
        "n200-k199-99",
    ],
)
def test_floor_rounding(candidate, required, expected):
    result = match_score(candidate, required)
    _check_contract_score(result)
    assert result == expected


# ---------------------------------------------------------------------------
# P2h — floor rounding over a sweep of denominators, lists built from indices
# so that the arithmetic stays hand-checkable
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("n", "k", "expected"),
    [
        (3, 1, 33),  # 100*1//3   = 33   (33.33...)
        (3, 2, 66),  # 100*2//3   = 66   (66.66...)
        (6, 1, 16),  # 100*1//6   = 16   (16.66...)
        (6, 5, 83),  # 100*5//6   = 83   (83.33...)
        (7, 1, 14),  # 100*1//7   = 14   (14.28...)
        (7, 6, 85),  # 100*6//7   = 85   (85.71...)
        (8, 1, 12),  # 100*1//8   = 12   (12.5 floored)
        (8, 3, 37),  # 100*3//8   = 37   (37.5 floored)
        (9, 1, 11),  # 100*1//9   = 11   (11.11...)
        (9, 4, 44),  # 100*4//9   = 44   (44.44...)
        (9, 8, 88),  # 100*8//9   = 88   (88.88...)
        (11, 1, 9),  # 100*1//11  = 9    (9.09...)
        (11, 10, 90),  # 100*10//11 = 90  (90.90...)
        (12, 5, 41),  # 100*5//12  = 41  (41.66...)
        (13, 12, 92),  # 100*12//13 = 92  (92.30...)
        (16, 1, 6),  # 100*1//16  = 6    (6.25 floored)
        (16, 15, 93),  # 100*15//16 = 93  (93.75 floored)
        (40, 1, 2),  # 100*1//40  = 2    (2.5 floored)
        (40, 39, 97),  # 100*39//40 = 97  (97.5 floored)
        (100, 1, 1),  # 100*1//100 = 1
        (100, 99, 99),  # 100*99//100 = 99
        (200, 1, 0),  # 100*1//200 = 0    (0.5 floored to 0)
        (200, 199, 99),  # 100*199//200 = 99 (99.5 floored)
    ],
)
def test_floor_rounding_sweep(n, k, expected):
    required = [f"skill{i}" for i in range(n)]  # n distinct, already normalised
    candidate = required[:k]  # exactly k of the n required skills
    assert len(required) == n and len(candidate) == k
    result = match_score(candidate, required)
    _check_contract_score(result)
    assert result == expected


# ---------------------------------------------------------------------------
# P3 — normalisation (contract section 2)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("candidate", "required", "expected"),
    [
        # ---- P3a surrounding whitespace ----------------------------------
        # C = {python}, R = {python}: k=1, n=1 -> 100*1//1 = 100
        (["  Python  "], ["python"], 100),
        # tab and newline are stripped too: C = {python}, R = {python} -> 100
        (["\tPython\n"], ["  python  "], 100),
        # C = {python}, R = {python, sql}: k=1, n=2 -> 100*1//2 = 50
        (["  python  "], ["python", "sql"], 50),
        # ---- P3b case variants -------------------------------------------
        # C = {python}, R = {python}: k=1, n=1 -> 100
        (["PYTHON", "pYtHoN", "Python"], ["python"], 100),
        # C = {python, sql}, R = {python, sql}: k=2, n=2 -> 100
        (["PYTHON", "SQL"], ["python", "sql"], 100),
        # C = {python}, R = {python, sql}: k=1, n=2 -> 50
        (["Python"], ["PYTHON", "SQL"], 50),
        # ---- P3c duplicates ----------------------------------------------
        # C = {python}, R = {python}: k=1, n=1 -> 100 (denominator not inflated)
        (["python"], ["Python", "python", "python "], 100),
        # C = {python, sql}, R = {python, sql}: k=2, n=2 -> 100
        (["python", "Python", "PYTHON", "sql"], ["python", "sql"], 100),
        # C = {python, go}, R = {python, go, rust}: k=2, n=3 -> 100*2//3 = 66
        (["Python", "Python", "Go", "Go"], ["python", "go", "rust"], 66),
        # ---- P3d empty strings dropped -----------------------------------
        # C = {sql}, R = {sql}: k=1, n=1 -> 100
        (["", "", "sql"], ["sql", ""], 100),
        # C = {python}, R = {python}: k=1, n=1 -> 100
        (["", "Python", ""], ["python"], 100),
        # ---- P3e whitespace-only entries dropped -------------------------
        # C = {python, sql}, R = {python, sql}: k=2, n=2 -> 100
        (["  ", "python", "\t"], ["python", "   ", "\n"], 100),
        # C = {python, sql}, R = {python, sql}: k=2, n=2 -> 100
        (["python", "sql", " \t\n "], ["python", "sql"], 100),
        # ---- P3f combined noise (contract section 4 example shape) -------
        # C = {sql, python}, R = {sql, python}: k=2, n=2 -> 100
        (["  SQL  ", " python ", "SQL", "", "\t"], ["sql", "PYTHON ", "  "], 100),
        # C = {python, sql}, R = {python, sql, rust}: k=2, n=3 -> 66
        ([" Python ", "SQL", "sql ", ""], ["\tpython", "SQL", "Rust"], 66),
    ],
    ids=[
        "strip-spaces",
        "strip-tab-newline",
        "strip-and-partial",
        "case-mixed-in-one-list",
        "case-both-lists",
        "case-partial",
        "dup-required",
        "dup-candidate",
        "dup-partial",
        "empty-strings",
        "empty-strings-2",
        "whitespace-entries",
        "whitespace-entries-2",
        "combined-noise",
        "combined-noise-partial",
    ],
)
def test_normalisation_whitespace_case_duplicates(candidate, required, expected):
    result = match_score(candidate, required)
    _check_contract_score(result)
    assert result == expected


def test_normalisation_equivalence_same_score():
    """Contract section 2: equal normalised (C, R) must give equal scores.

    All three candidate spellings normalise to {python, sql, go} and all three
    required spellings normalise to {python, sql, rust}.
    k = 2, n = 3 -> 100 * 2 // 3 = 66 for every pairing.
    """
    candidate_forms = [
        ["python", "sql", "go"],
        ["  Python  ", "SQL", "\tgo\n"],
        ["PYTHON", "python", "Sql", "sql ", "GO", "go"],
    ]
    required_forms = [
        ["python", "sql", "rust"],
        ["  PYTHON ", "sql\t", "Rust"],
        ["python", "sql", "rust", " rust ", "RUST"],
    ]
    for candidate in candidate_forms:
        for required in required_forms:
            result = match_score(candidate, required)
            _check_contract_score(result)
            # k=2, n=3 -> 100*2//3 = 66
            assert result == 66, (candidate, required)


# ---------------------------------------------------------------------------
# P4 — invariance under permutation and duplication
# ---------------------------------------------------------------------------
def test_input_order_invariance():
    """Contract section 1/2: lists are sets after normalisation, so order is
    irrelevant. C = {python, java, sql}, R = {sql, go, python}
    k = |{python, sql}| = 2, n = 3 -> 100 * 2 // 3 = 66.
    """
    base = match_score(["python", "java", "sql"], ["sql", "go", "python"])
    _check_contract_score(base)
    assert base == 66

    permuted = match_score(["sql", "python", "java"], ["python", "sql", "go"])
    _check_contract_score(permuted)
    # same sets -> k=2, n=3 -> 100*2//3 = 66
    assert permuted == 66
    assert permuted == base


def test_duplicate_invariance():
    """Duplicates must not change k or n.

    plain      C = {python, sql, go}, duplicated C = {python, sql, go}
    required   R = {python, sql, rust}
    k = 2, n = 3 -> 100 * 2 // 3 = 66 for both.
    """
    required = ["Python", "SQL", "Rust"]
    base = match_score(["python", "sql", "go"], required)
    duplicated = match_score(
        ["Python", "python ", "SQL", "sql", "go", "GO", "go", "  python  "],
        required,
    )
    _check_contract_score(base)
    _check_contract_score(duplicated)
    # k=2, n=3 -> 100*2//3 = 66
    assert base == 66
    assert duplicated == 66
    assert duplicated == base


# ---------------------------------------------------------------------------
# P5 — Unicode and symbol skills
# ---------------------------------------------------------------------------
def test_unicode_skills_are_matched_verbatim():
    """str.lower() leaves CJK text unchanged (contract section 5).

    C = {"机器学习"}, R = {"机器学习"}: k=1, n=1 -> 100*1//1 = 100
    """
    result = match_score(["机器学习"], ["机器学习"])
    _check_contract_score(result)
    assert result == 100


def test_unicode_mixed_with_ascii_partial():
    """C = {机器学习, python}, R = {python, 机器学习, sql}
    k = 2, n = 3 -> 100 * 2 // 3 = 66
    """
    result = match_score(["机器学习", "Python"], ["PYTHON", "机器学习", "SQL"])
    _check_contract_score(result)
    assert result == 66


def test_symbol_skills_are_lowercased():
    """Symbols are ordinary characters: "C++" -> "c++" (contract section 5)."""
    # C = {"c++"}, R = {"c++"}: k=1, n=1 -> 100*1//1 = 100
    symbol_result = match_score(["C++"], ["c++"])
    _check_contract_score(symbol_result)
    assert symbol_result == 100

    # C = {c#, .net, node.js}, R = {node.js, c#}: k=2, n=2 -> 100
    result = match_score(["C#", ".NET", "Node.js"], ["node.js", "C#"])
    _check_contract_score(result)
    assert result == 100

    # C = {c#}, R = {f#, rust}: k=0, n=2 -> 100*0//2 = 0
    disjoint = match_score(["C#"], ["F#", "Rust"])
    _check_contract_score(disjoint)
    assert disjoint == 0


def test_lower_is_not_casefold():
    """Contract section 2.2 / A2: str.lower(), never str.casefold().

    "SS".lower() == "ss", but the sharp s (U+00DF) lowercases to itself, so
    C = {sharp s}, R = {"ss"} -> k=0, n=1 -> 100*0//1 = 0.
    """
    sharp_s = "\u00df"  # LATIN SMALL LETTER SHARP S; str.lower() keeps it
    result = match_score([sharp_s], ["SS"])
    _check_contract_score(result)
    assert result == 0

    # U+0130 lowercases to "i" + U+0307 (two code points), which is not "i".
    # C = {"i" + U+0307}, R = {"i"} -> k=0, n=1 -> 100*0//1 = 0
    dotted_i = "\u0130"
    result_i = match_score([dotted_i], ["I"])
    _check_contract_score(result_i)
    assert result_i == 0

    # Control case: the same letters match after str.lower().
    # C = {"ss"}, R = {"ss"}: k=1, n=1 -> 100*1//1 = 100
    control = match_score(["SS"], ["ss"])
    _check_contract_score(control)
    assert control == 100


def test_internal_whitespace_is_preserved():
    """Contract section 6.3 / A3: only leading/trailing whitespace is stripped.

    C = {"data science"} (one interior space), R = {"data  science"} (two)
    -> k=0, n=1 -> 100*0//1 = 0
    """
    result = match_score(["data science"], ["data  science"])
    _check_contract_score(result)
    assert result == 0

    # Surrounding whitespace and case are still normalised:
    # C = {"data science"}, R = {"data science"}: k=1, n=1 -> 100
    stripped = match_score(["  data science\t"], ["DATA SCIENCE"])
    _check_contract_score(stripped)
    assert stripped == 100


# ---------------------------------------------------------------------------
# P6 — return type and range, independent of the per-case helper
# ---------------------------------------------------------------------------
def test_return_type_is_exactly_int():
    """Contract section 3: return an int, not bool and not float."""
    result = match_score(["Python", "SQL"], ["Python", "SQL", "Go"])
    # k=2, n=3 -> 100*2//3 = 66 (a non-integral quotient: a float return would
    # show up here as 66.66... or 66.0)
    assert type(result) is int
    assert 0 <= result <= 100
    assert result == 66


def test_return_range_on_boundary_inputs():
    """Contract section 3: 0 <= result <= 100 for every valid input."""
    cases = [
        ([], []),
        ([], ["python"]),
        (["python"], []),
        (["python"], ["python"]),
        (["python"], ["python", "sql"]),
        (["rust"], ["python", "sql"]),
        (["  "], ["\t"]),
        (["python"] * 5, ["python"] * 3),
    ]
    for candidate, required in cases:
        result = match_score(candidate, required)
        assert type(result) is int, (candidate, required)
        assert 0 <= result <= 100, (candidate, required)


# ---------------------------------------------------------------------------
# P7 — purity and determinism (contract section 3)
# ---------------------------------------------------------------------------
def test_inputs_are_not_mutated():
    """Contract section 3: "no mutation of the input lists".

    C = {python, sql}, R = {python, sql}: k=2, n=2 -> 100*2//2 = 100
    """
    candidate = ["  Python ", "SQL", "sql", ""]
    required = ["python", " SQL "]
    candidate_before = list(candidate)
    required_before = list(required)

    result = match_score(candidate, required)
    _check_contract_score(result)
    # k=2, n=2 -> 100*2//2 = 100
    assert result == 100
    assert candidate == candidate_before, "candidate_skills was mutated"
    assert required == required_before, "required_skills was mutated"


def test_repeated_calls_are_deterministic():
    """Contract section 3: pure and deterministic, no hidden state.

    C = {python, go}, R = {python, go, rust}: k=2, n=3 -> 100*2//3 = 66
    """
    candidate = ["Python", " Go "]
    required = ["python", "go", "rust"]
    results = [
        match_score(candidate, required),
        match_score(candidate, required),
        match_score(list(candidate), list(required)),
    ]
    for result in results:
        _check_contract_score(result)
        # k=2, n=3 -> 100*2//3 = 66
        assert result == 66
    assert results[0] == results[1] == results[2]


# ---------------------------------------------------------------------------
# P8 — out-of-contract inputs: recorded, not asserted
# ---------------------------------------------------------------------------
def test_out_of_contract_inputs_are_undefined():
    """A1 / contract section 6.1: behaviour for non-``list[str]`` inputs is
    undefined, so no exception or value is demanded here (prompt step 4)."""
    pytest.skip(
        "Contract F1 does not define behaviour for None, a bare str, or "
        "non-str elements (ambiguity A1); nothing is asserted."
    )
