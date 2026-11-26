"""Hand-computed self-tests for the finite-trace LTL checker.

Every expected value below was worked out by hand from the semantics in
``support/ltl.py`` (or, for the exhaustive truth tables, from an independent
Boolean expression written next to the assertion).  The module deliberately
does not use the production application or the P2 traces, so it runs without
PostgreSQL even though the ``ltl`` mode directory carries a ``NEEDS_DB`` marker
for the sibling trace test.

Layout:

* one parameterized table per operator, with at least three satisfying and
  three violating traces each;
* exhaustive truth tables over three-step traces for ``G(p -> X q)``,
  ``p U q`` and ``F G p``;
* boundary tests (empty trace, last state, strong vs. weak next);
* quantifier tests, including the finite-domain/vacuity rule;
* counterexample tests for L1-L5: each business property is fed a hand-written
  violating trace and must return ``False`` with the right first step;
* the mandatory L1 self-check whose output is quoted in ``docs/.../LTL.md``.
"""

from __future__ import annotations

from itertools import product

import pytest

from support.ltl import (
    And,
    Atom,
    F,
    G,
    Implies,
    Not,
    Or,
    U,
    WX,
    X,
    evaluate,
    exists,
    explain,
    forall,
    match_atom,
    replace_at,
    trace_atoms,
    walk,
)
from support.traces import Event

import properties


# ---------------------------------------------------------------------------
# Small hand-written traces
# ---------------------------------------------------------------------------


def make_trace(*states, start: int = 1) -> list[Event]:
    """Build a trace of ``observe`` steps whose props are the given sets.

    ``make_trace({"p"}, set(), {"p", "q"})`` is three steps; step numbers start
    at 1 to mirror the producer.  An empty state is written ``set()`` and an
    empty trace is ``make_trace()``.
    """

    return [
        Event(start + index, "observe", True, frozenset(state))
        for index, state in enumerate(states)
    ]


P = Atom("p")
Q = Atom("q")
R = Atom("r")


# ---------------------------------------------------------------------------
# One hand-checked table per operator: 3 satisfying + 3 violating traces
# ---------------------------------------------------------------------------

# ``states`` is a tuple of prop sets; the formula is evaluated at suffix 0.
# Each expected value is hand-computed from the finite-trace semantics.
OPERATOR_CASES: dict[str, tuple[object, list[tuple[tuple, bool]]]] = {
    "atom": (
        P,
        [
            (({"p"},), True),  # p is in the only state
            (({"p", "q"},), True),  # extra atoms do not disturb p
            (({"p"}, {"q"}), True),  # the atom is checked at suffix 0
            ((), False),  # empty trace: no state, so no atom
            (({"q"},), False),  # a different atom is not p
            (({"q"}, {"p"}), False),  # p at step 1 does not help suffix 0
        ],
    ),
    "not": (
        Not(P),
        [
            ((), True),  # nothing holds, so !p holds
            (({"q"},), True),
            (({"q"}, {"p"}), True),  # p only at step 1; suffix 0 is still !p
            (({"p"},), False),
            (({"p"}, {"q"}), False),
            (({"p", "q"},), False),
        ],
    ),
    "and": (
        And(P, Q),
        [
            (({"p", "q"},), True),
            (({"p", "q"}, set()), True),  # only suffix 0 matters here
            (({"p", "q", "r"},), True),
            (({"p"},), False),
            (({"q"},), False),
            ((), False),
        ],
    ),
    "or": (
        Or(P, Q),
        [
            (({"p"},), True),
            (({"q"},), True),
            (({"p", "q"},), True),
            ((), False),
            (({"r"},), False),
            ((set(), {"p"}), False),  # p appears only after suffix 0
        ],
    ),
    "implies": (
        Implies(P, Q),
        [
            ((), True),  # false antecedent
            (({"q"},), True),  # false antecedent, true consequent
            (({"p", "q"},), True),
            (({"p"},), False),
            (({"p"}, {"q"}), False),  # q at step 1 is too late
            (({"p", "r"},), False),
        ],
    ),
    "x": (
        X(P),
        [
            ((set(), {"p"}), True),  # successor holds p
            (({"p"}, {"p"}), True),
            ((set(), {"p"}, set()), True),
            ((), False),  # empty trace: no successor
            (({"p"},), False),  # p at the last state, no successor
            (({"p"}, set()), False),  # successor does not hold p
        ],
    ),
    "wx": (
        WX(P),
        [
            ((), True),  # weak next is true on an empty trace
            (({"p"},), True),  # weak next is true at the last state
            ((set(), {"p"}), True),
            ((set(), set()), False),
            (({"q"}, set()), False),
            (({"p"}, {"q"}), False),
        ],
    ),
    "g": (
        G(P),
        [
            ((), True),  # vacuously true over the empty suffix
            (({"p"},), True),
            (({"p"}, {"p"}), True),
            (({"q"},), False),
            (({"p"}, {"q"}), False),  # fails at step 1
            (({"p"}, {"p"}, set()), False),
        ],
    ),
    "f": (
        F(P),
        [
            (({"p"},), True),
            (({"q"}, {"p"}), True),
            (({"q"}, {"p"}, {"r"}), True),
            ((), False),
            (({"q"},), False),
            (({"q"}, {"r"}), False),
        ],
    ),
    "u": (
        U(P, Q),
        [
            (({"q"},), True),  # right operand holds immediately
            (({"p"}, {"q"}), True),  # left until right
            (({"p"}, {"p"}, {"q"}), True),
            ((), False),  # right never holds
            (({"p"},), False),  # right never holds
            (({"p"}, set()), False),  # left stops before right holds
            # right holds eventually, but the left operand stopped first:
            (({"p"}, set(), {"q"}), False),
        ],
    ),
}


def _operator_parameters():
    parameters = []
    for name, (formula, rows) in OPERATOR_CASES.items():
        for index, (states, expected) in enumerate(rows):
            verdict = "sat" if expected else "viol"
            parameters.append(
                pytest.param(
                    formula,
                    states,
                    expected,
                    id=f"{name}-{index}-{verdict}",
                )
            )
    return parameters


@pytest.mark.parametrize("formula, states, expected", _operator_parameters())
def test_operator_hand_traces(formula, states, expected):
    """Each operator on six hand-written traces (three true, three false)."""

    assert evaluate(formula, make_trace(*states)) is expected


@pytest.mark.parametrize("name", sorted(OPERATOR_CASES))
def test_operator_has_three_satisfying_and_three_violating_cases(name):
    """Keep the self-test honest: every operator must be exercised both ways."""

    _, rows = OPERATOR_CASES[name]
    satisfying = sum(1 for _, expected in rows if expected)
    violating = sum(1 for _, expected in rows if not expected)
    assert satisfying >= 3
    assert violating >= 3


# ---------------------------------------------------------------------------
# Boundary semantics
# ---------------------------------------------------------------------------


def test_empty_trace_semantics():
    empty: list[Event] = []
    assert evaluate(G(P), empty) is True
    assert evaluate(WX(P), empty) is True
    assert evaluate(F(P), empty) is False
    assert evaluate(X(P), empty) is False
    assert evaluate(U(P, Q), empty) is False
    assert evaluate(P, empty) is False
    assert evaluate(Not(P), empty) is True
    assert evaluate(forall(("a",), Atom("applied:?a")), empty) is True
    assert evaluate(exists(("a",), Atom("applied:?a")), empty) is False


def test_last_state_is_where_strong_and_weak_next_differ():
    one_step = make_trace({"p"})
    assert evaluate(X(P), one_step) is False
    assert evaluate(WX(P), one_step) is True
    assert evaluate(X(P), one_step, i=1) is False
    assert evaluate(WX(P), one_step, i=1) is True
    # ``G`` and ``WX`` hold on the empty suffix; ``F``/``U``/atom do not.
    assert evaluate(G(P), one_step, i=1) is True
    assert evaluate(F(P), one_step, i=1) is False
    assert evaluate(U(P, Q), one_step, i=1) is False
    assert evaluate(P, one_step, i=1) is False


def test_suffix_index_is_validated():
    trace = make_trace({"p"})
    assert evaluate(P, trace, i=0) is True
    assert evaluate(G(P), trace, i=1) is True
    with pytest.raises(ValueError, match="outside"):
        evaluate(P, trace, i=2)
    with pytest.raises(ValueError, match="outside"):
        evaluate(P, trace, i=-1)


def test_free_variables_must_be_quantified():
    with pytest.raises(ValueError, match="free variable"):
        evaluate(Atom("booked:?a:?s"), make_trace({"booked:a1:s1"}))
    with pytest.raises(ValueError, match="free variable"):
        evaluate(forall(("a",), Atom("booked:?a:?s")), make_trace({"booked:a1:s1"}))
    # Once both variables are quantified the formula is closed.
    closed = forall(("a", "s"), Atom("booked:?a:?s"))
    assert evaluate(closed, make_trace({"booked:a1:s1"})) is True


def test_atom_pattern_validation():
    assert match_atom("booked:?a:?s", "booked:a1:s1") == {"a": "a1", "s": "s1"}
    assert match_atom("booked:?a:?s", "booked:a1") is None  # wrong arity
    assert match_atom("status:?a:Interviewing", "status:a1:Rejected") is None
    assert Atom("status:?a:Interviewing").free_variables() == frozenset({"a"})
    with pytest.raises(ValueError):
        Atom("")
    with pytest.raises(ValueError):
        Atom("booked:?:s")
    with pytest.raises(ValueError):
        forall(("a", "a"), P)
    with pytest.raises(ValueError):
        forall((), P)


# ---------------------------------------------------------------------------
# Quantifiers and vacuity
# ---------------------------------------------------------------------------


def test_forall_hand_traces():
    formula = forall(("a",), Atom("status:?a:Interviewing"))
    assert evaluate(formula, make_trace()) is True  # empty domain
    assert (
        evaluate(formula, make_trace({"status:a1:Interviewing"})) is True
    )
    assert (
        evaluate(
            formula,
            make_trace(
                {
                    "status:a1:Interviewing",
                    "status:a2:Interviewing",
                },
                {
                    "status:a1:Interviewing",
                    "status:a2:Interviewing",
                },
            ),
        )
        is True
    )
    assert evaluate(formula, make_trace({"status:a1:Pending"})) is False
    assert (
        evaluate(
            formula,
            make_trace(
                {"status:a1:Interviewing", "status:a2:Rejected"}
            ),
        )
        is False
    )
    assert (
        evaluate(
            formula,
            make_trace({"status:a1:Pending", "status:a2:Interviewing"}),
        )
        is False
    )


def test_exists_hand_traces():
    formula = exists(("a", "s"), Atom("booked:?a:?s"))
    assert evaluate(formula, make_trace()) is False
    assert evaluate(formula, make_trace({"slot:s1"})) is False
    assert evaluate(formula, make_trace({"booked:a1:s1"})) is True
    assert (
        evaluate(
            formula,
            make_trace({"booked:a1:s1", "booked:a2:s2"}),
        )
        is True
    )
    assert evaluate(formula, make_trace({"applied:a1"})) is False


def test_quantifier_domain_is_collected_from_the_trace_only():
    """A value that never occurs is outside the finite domain (vacuity)."""

    applied = forall(("a",), Atom("applied:?a"))
    assert evaluate(applied, make_trace()) is True
    assert evaluate(applied, make_trace({"applied:a1"})) is True
    assert evaluate(applied, make_trace({"applied:a1", "applied:a2"})) is True
    # No ``applied`` atom at all: the domain is empty, so the forall is true
    # even though a status atom mentions an application.
    assert evaluate(applied, make_trace({"status:a1:Interviewing"})) is True


def test_quantifier_respects_occurrence_values():
    """Only values that actually occur in the trace are enumerated."""

    formula = forall(("a",), G(Atom("status:?a:Interviewing")))
    assert (
        evaluate(
            formula,
            make_trace(
                {"status:a1:Interviewing"},
                {"status:a1:Interviewing"},
            ),
        )
        is True
    )
    # a2 occurs in the trace but is never Interviewing, so the forall is false.
    assert (
        evaluate(
            formula,
            make_trace(
                {"status:a1:Interviewing", "status:a2:Pending"},
                {"status:a1:Interviewing", "status:a2:Pending"},
            ),
        )
        is False
    )


def test_vacuity_helpers_count_implication_antecedents():
    two_bookings = make_trace(
        {"booked:a1:s1", "booked:a2:s2"},
        {"booked:a1:s1", "booked:a2:s2"},
    )
    assert properties.trigger_bindings(
        properties.L1_BOOKED_STAYS_UNAVAILABLE, two_bookings
    ) == {("a1", "s1"), ("a2", "s2")}
    assert (
        properties.trigger_steps(
            properties.L1_BOOKED_STAYS_UNAVAILABLE, two_bookings
        )
        == 2
    )
    # An available atom does not satisfy L1's booked antecedent.
    available_only = make_trace({"available:s1"})
    assert (
        properties.trigger_bindings(
            properties.L1_BOOKED_STAYS_UNAVAILABLE, available_only
        )
        == set()
    )
    # L2's antecedent is new_booking, not booked.
    assert (
        properties.trigger_bindings(
            properties.L2_BOOKING_REQUIRES_INTERVIEWING, two_bookings
        )
        == set()
    )


def test_vacuity_is_reported_for_a_never_triggered_property():
    trace = make_trace({"applied:a1"}, {"applied:a1"})
    assert evaluate(properties.L1_BOOKED_STAYS_UNAVAILABLE, trace) is True
    assert (
        properties.trigger_bindings(
            properties.L1_BOOKED_STAYS_UNAVAILABLE, trace
        )
        == set()
    )


# ---------------------------------------------------------------------------
# Exhaustive truth tables (independent Boolean expressions)
# ---------------------------------------------------------------------------


def _truth_trace(p_bits, q_bits) -> list[Event]:
    states = []
    for p_value, q_value in zip(p_bits, q_bits):
        state = set()
        if p_value:
            state.add("p")
        if q_value:
            state.add("q")
        states.append(state)
    return make_trace(*states)


THREE = list(product([False, True], repeat=3))
PAIRS = [(p, q) for p in THREE for q in THREE]


@pytest.mark.parametrize("p,q", PAIRS)
def test_truth_table_g_p_implies_x_q(p, q):
    """``G(p -> X q)`` on three states, for all 64 p/q valuations.

    Hand-derived: at step 0 and 1 the implication needs q at the successor
    (``X`` is strong); at the last step ``X q`` is false, so p must be false.
    """

    expected = all(
        (not p[index]) or (index + 1 < 3 and q[index + 1])
        for index in range(3)
    )
    assert (
        evaluate(G(Implies(Atom("p"), X(Atom("q")))), _truth_trace(p, q))
        is expected
    )


@pytest.mark.parametrize("p,q", PAIRS)
def test_truth_table_p_until_q(p, q):
    """``p U q`` on three states, for all 64 p/q valuations.

    Hand-derived: some state j holds q and every earlier state holds p.
    """

    expected = any(
        q[j] and all(p[k] for k in range(j)) for j in range(3)
    )
    assert evaluate(U(Atom("p"), Atom("q")), _truth_trace(p, q)) is expected


@pytest.mark.parametrize("p", THREE)
def test_truth_table_f_g_p(p):
    """``F G p`` on three states, for all 8 p valuations.

    Hand-derived: F G p means some suffix is entirely p.  On a non-empty trace
    that holds exactly when the last state holds p (choose the last state as
    the witness); an empty trace would be false and is tested separately.
    """

    expected = p[-1]
    assert (
        evaluate(F(G(Atom("p"))), _truth_trace(p, [False, False, False]))
        is expected
    )


def test_truth_table_spot_checks():
    # p holds on the last state but X q cannot: false.
    assert (
        evaluate(
            G(Implies(Atom("p"), X(Atom("q")))),
            make_trace({"p"}),
        )
        is False
    )
    # p holds at step 0, q holds at step 1, p is false afterwards: true.
    assert (
        evaluate(
            G(Implies(Atom("p"), X(Atom("q")))),
            make_trace({"p"}, {"q"}, set()),
        )
        is True
    )
    # p U q: q at the last state with p before it is enough.
    assert evaluate(U(Atom("p"), Atom("q")), make_trace({"p"}, {"p"}, {"q"})) is True
    # p U q: q never holds.
    assert evaluate(U(Atom("p"), Atom("q")), make_trace({"p"}, {"p"})) is False
    # F G p: a p, then a permanent failure.
    assert evaluate(F(G(Atom("p"))), make_trace({"p"}, set())) is False


# ---------------------------------------------------------------------------
# L1-L5 counterexamples and explanations
# ---------------------------------------------------------------------------


def _l1_counterexample() -> list[Event]:
    """A hand-written L1 violation: a booked slot is offered again at step 4."""

    return [
        Event(1, "create_slot", True, frozenset({"slot:s1"})),
        Event(
            2,
            "set_status",
            True,
            frozenset(
                {"applied:a1", "status:a1:Interviewing", "slot:s1"}
            ),
        ),
        Event(
            3,
            "book",
            True,
            frozenset(
                {
                    "applied:a1",
                    "status:a1:Interviewing",
                    "slot:s1",
                    "booked:a1:s1",
                    "new_booking:a1",
                }
            ),
        ),
        Event(
            4,
            "observe",
            True,
            frozenset(
                {
                    "applied:a1",
                    "status:a1:Interviewing",
                    "slot:s1",
                    "booked:a1:s1",
                    "available:s1",
                }
            ),
        ),
    ]


def _l1_corrected() -> list[Event]:
    """The same trace without the illegal available:s1 state (L1 must hold)."""

    return [
        *_l1_counterexample()[:3],
        Event(
            4,
            "observe",
            True,
            frozenset(
                {
                    "applied:a1",
                    "status:a1:Interviewing",
                    "slot:s1",
                    "booked:a1:s1",
                }
            ),
        ),
    ]


L1_COUNTEREXAMPLE = _l1_counterexample()

PROPERTY_COUNTEREXAMPLES = {
    "L2": (
        [
            Event(
                1,
                "book",
                True,
                frozenset(
                    {
                        "applied:a1",
                        "status:a1:Pending",
                        "new_booking:a1",
                    }
                ),
            )
        ],
        0,
    ),
    "L3": (
        [
            Event(
                1,
                "book",
                True,
                frozenset(
                    {
                        "applied:a1",
                        "status:a1:Interviewing",
                        "slot:s1",
                        "booked:a1:s1",
                    }
                ),
            ),
            Event(2, "observe", True, frozenset({"slot:s1"})),
        ],
        1,
    ),
    "L4": (
        [
            Event(
                1,
                "book",
                True,
                frozenset(
                    {
                        "applied:a1",
                        "status:a1:Interviewing",
                        "slot:s1",
                        "booked:a1:s1",
                    }
                ),
            ),
            Event(2, "delete_slot", True, frozenset({"booked:a1:s1"})),
        ],
        1,
    ),
    "L5": (
        [
            Event(1, "apply", True, frozenset({"applied:a1"})),
            Event(2, "observe", True, frozenset()),
        ],
        1,
    ),
}


def test_every_property_is_closed_and_catalogued():
    assert [property_.identifier for property_ in properties.PROPERTIES] == [
        "L1",
        "L2",
        "L3",
        "L4",
        "L5",
    ]
    for property_ in properties.PROPERTIES:
        assert property_.formula.free_variables() == frozenset()
        assert property_.clause.startswith("FP-")


def test_l1_counterexample_is_detected_and_explained():
    """Mandatory P3 self-check: a booked slot becoming available again.

    The error appears in trace index 3 (producer step 4), so L1 must be false
    and ``explain`` must point at that step, not at the booking step.
    """

    formula = properties.L1_BOOKED_STAYS_UNAVAILABLE
    assert evaluate(formula, L1_COUNTEREXAMPLE) is False
    message = explain(formula, L1_COUNTEREXAMPLE)
    assert "first violation at trace index 3" in message
    assert "step 4" in message
    assert "action=observe" in message
    assert "available:s1" in message
    assert "binding: a=a1, s=s1" in message
    # Removing the illegal available state repairs the trace.
    assert evaluate(formula, _l1_corrected()) is True


@pytest.mark.parametrize("identifier", ["L2", "L3", "L4", "L5"])
def test_business_property_detects_its_counterexample(identifier):
    property_ = properties.BY_ID[identifier]
    trace, expected_index = PROPERTY_COUNTEREXAMPLES[identifier]
    assert evaluate(property_.formula, trace) is False
    message = explain(property_.formula, trace)
    assert f"first violation at trace index {expected_index}" in message


@pytest.mark.parametrize(
    "identifier, trace",
    [
        (
            "L2",
            make_trace(
                {
                    "applied:a1",
                    "status:a1:Interviewing",
                    "new_booking:a1",
                }
            ),
        ),
        (
            "L3",
            make_trace(
                {"booked:a1:s1", "slot:s1"},
                {"booked:a1:s1", "slot:s1"},
            ),
        ),
        (
            "L4",
            make_trace(
                {"booked:a1:s1", "slot:s1"},
                {"booked:a1:s1", "slot:s1"},
            ),
        ),
        ("L5", make_trace({"applied:a1"}, {"applied:a1"})),
    ],
)
def test_business_property_holds_on_a_corrected_trace(identifier, trace):
    assert evaluate(properties.BY_ID[identifier].formula, trace) is True


def test_explain_reports_success_without_a_violation():
    message = explain(Atom("p"), make_trace({"p"}))
    assert message.startswith("LTL property holds")
    assert "1 step(s)" in message


# ---------------------------------------------------------------------------
# Traversal helpers (used by the refinement demo)
# ---------------------------------------------------------------------------


def test_walk_and_replace_at_round_trip():
    formula = G(Implies(P, X(Q)))
    paths = [
        (path, str(node)) for path, node in walk(formula)
    ]
    assert paths[0] == ((), "G((p -> X(q)))")
    assert (0, 1, 0) in dict(paths)
    replaced = replace_at(formula, (0, 1, 0), R)
    assert str(replaced) == "G((p -> X(r)))"
    assert formula == G(Implies(P, X(Q)))


def test_trace_atoms_returns_the_union_of_states():
    trace = make_trace({"p", "q"}, set(), {"r"})
    assert trace_atoms(trace) == frozenset({"p", "q", "r"})
