"""SMT encoding of the FP-MATCH-1 score specification.

The encoding mirrors the *specification* in ``docs/REQUIREMENTS.md``
(section 5, FP-MATCH-1)::

    score = 100                                      when |R| = 0
    score = floor(100 * |C intersection R| / |R|)    otherwise

It deliberately does not import the application.  The SMT side and the
Python side are two independent descriptions of the same requirement: the
proof tests check this description, and ``test_spec_to_code.py`` links it to
``app.employer.matching.match_score`` with a bounded exhaustive comparison.

Encoding conventions
--------------------

* ``n = |R|`` and ``k = |C intersection R|`` are SMT integers.  The partial
  formula is only defined for ``n >= 1``; :func:`total_score_term` adds the
  ``n == 0 -> 100`` special case from the requirements.
* Z3Py's ``/`` on two ``Int`` terms builds the SMT-LIB ``div`` operator
  (Euclidean integer division).  Every division below has a non-negative
  numerator and a positive denominator, where ``div`` is ``floor``.  This is
  what makes the encoding the specification's floor rather than a real
  division; ``test_matching_theory.py::test_n1_*`` demonstrates the
  difference with a counterexample.
* Sets are encoded extensionally as Boolean membership vectors over a fixed
  finite universe.  ``unsat`` results are therefore about bounded sets, and
  the report states that limitation explicitly.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import z3

UNIVERSE_SIZE = 6
"""Default number of elements in the bounded set universe."""


def int_div(numerator: z3.ArithRef, denominator: z3.ArithRef) -> z3.ArithRef:
    """Return SMT integer division (``div``) of two integer terms."""

    return numerator / denominator


def score_term(k: z3.ArithRef, n: z3.ArithRef) -> z3.ArithRef:
    """FP-MATCH-1 score for ``n >= 1``: ``(100*k) div n``."""

    return int_div(100 * k, n)


def total_score_term(k: z3.ArithRef, n: z3.ArithRef) -> z3.ArithRef:
    """FP-MATCH-1 score including the requirement ``n = 0 -> 100``."""

    return z3.If(n == 0, z3.IntVal(100), int_div(100 * k, n))


def bool_vector(
    name: str, size: int = UNIVERSE_SIZE
) -> list[z3.BoolRef]:
    """Return ``size`` Boolean membership variables ``name_0 .. name_N``."""

    return [z3.Bool(f"{name}_{index}") for index in range(size)]


def set_pair(
    name: str = "set", size: int = UNIVERSE_SIZE
) -> tuple[list[z3.BoolRef], list[z3.BoolRef]]:
    """Return the ``(candidate, required)`` membership vectors of one universe."""

    return bool_vector(f"{name}_c", size), bool_vector(f"{name}_r", size)


def cardinality(flags: Sequence[z3.BoolRef]) -> z3.ArithRef:
    """Set size as an SMT integer: the sum of the membership indicators."""

    return z3.Sum([z3.If(flag, 1, 0) for flag in flags])


def intersection(
    left: Sequence[z3.BoolRef], right: Sequence[z3.BoolRef]
) -> list[z3.BoolRef]:
    """Membership vector of ``left intersection right``."""

    return [z3.And(a, b) for a, b in zip(left, right)]


def subset(
    left: Sequence[z3.BoolRef], right: Sequence[z3.BoolRef]
) -> z3.BoolRef:
    """``left subset right`` as a quantifier-free Boolean term."""

    return z3.And([z3.Implies(a, b) for a, b in zip(left, right)])


def set_counts(
    candidate: Sequence[z3.BoolRef], required: Sequence[z3.BoolRef]
) -> tuple[z3.ArithRef, z3.ArithRef]:
    """Return ``(k, n) = (|C intersection R|, |R|)`` for membership vectors."""

    n = cardinality(required)
    k = cardinality(intersection(candidate, required))
    return k, n


def set_score(
    candidate: Sequence[z3.BoolRef], required: Sequence[z3.BoolRef]
) -> z3.ArithRef:
    """Full FP-MATCH-1 score of two encoded sets, including ``|R| = 0``."""

    k, n = set_counts(candidate, required)
    return total_score_term(k, n)


def concrete_flags(bits: int, size: int = UNIVERSE_SIZE) -> list[z3.BoolRef]:
    """Turn a membership bit mask into constant Boolean membership terms."""

    return [
        z3.BoolVal(bool(bits & (1 << index))) for index in range(size)
    ]


def evaluate_scores(
    assignments: Iterable[tuple[int, int]], size: int = UNIVERSE_SIZE
) -> list[int]:
    """Evaluate the set encoding on concrete membership bit masks.

    ``assignments`` yields ``(candidate_bits, required_bits)`` pairs.  All
    pairs go into one solver, each next to a fresh score variable; the values
    are then read from the single model.  They are therefore *entailed by the
    encoding* for those concrete assignments, not computed by a separate
    Python formula.
    """

    solver = z3.Solver()
    solver.set("timeout", 30_000)
    scores: list[z3.ArithRef] = []
    for index, (candidate_bits, required_bits) in enumerate(assignments):
        score = z3.Int(f"score_{index}")
        scores.append(score)
        solver.add(
            score
            == set_score(
                concrete_flags(candidate_bits, size),
                concrete_flags(required_bits, size),
            )
        )
    result = solver.check()
    if result != z3.sat:
        raise AssertionError(
            f"concrete set encoding was {result}, expected sat"
        )
    model = solver.model()
    return [model[score].as_long() for score in scores]
