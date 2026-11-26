"""Temporal properties checked against the P2 booking traces.

Every property is a closed :mod:`support.ltl` formula.  The comment above each
one names the requirement clause it encodes and the P2/README atom it uses.
The antecedents are also extracted programmatically below so ``test_booking_traces``
can report *non-vacuous* satisfaction: ``G(p -> q)`` is trivially true on a trace
in which ``p`` never occurs, and such a trace is not evidence for the rule.

The trace vocabulary is documented in ``tests/advanced/README.md`` section 8 and
produced by ``tests/advanced/stateful/test_booking_state_machine.py``:

``applied:a``              application ``a`` exists
``status:a:<Status>``      application ``a`` currently has exactly that status
``booked:a:s``             application ``a`` is bound to slot ``s``
``available:s``            slot ``s`` is visible in an eligible candidate's list
``slot:s``                 slot ``s`` exists
``new_booking:a``          this step created the booking of application ``a``

``props`` is a state slice after the step, so a booking that survives a status
change keeps ``booked:a:s`` and ``slot:s`` in every later step.  The status value
is case-sensitive and uses the application spelling (``Interviewing``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from support.ltl import (
    Atom,
    Exists,
    Formula,
    Forall,
    G,
    Implies,
    Not,
    WX,
    forall,
    match_atom,
    walk,
)
from support.traces import Event

__all__ = [
    "BY_ID",
    "PROPERTIES",
    "Property",
    "antecedent_of",
    "quantified_variables",
    "trigger_bindings",
    "trigger_steps",
]


@dataclass(frozen=True)
class Property:
    """One named business property plus its requirement clause."""

    identifier: str
    title: str
    clause: str
    formula: Formula
    rationale: str = ""

    def __str__(self) -> str:
        return f"{self.identifier} ({self.clause}): {self.title}"

    def antecedent(self) -> Formula | None:
        """Return the ``p`` of the outermost ``G(p -> q)``, if there is one."""

        return antecedent_of(self.formula)

    def variables(self) -> tuple[str, ...]:
        """Return the variables bound by the outermost quantifier."""

        return quantified_variables(self.formula)


# ---------------------------------------------------------------------------
# L1..L5
# ---------------------------------------------------------------------------

# FP-SCHED-1 / FP-SCHED-2: a booked slot is never offered as available again.
# The weak next is intentional: a booking made on the very last state has no
# successor, and "from the next state on" is vacuous there.
L1_BOOKED_STAYS_UNAVAILABLE = forall(
    ("a", "s"),
    G(
        Implies(
            Atom("booked:?a:?s"),
            WX(G(Not(Atom("available:?s")))),
        )
    ),
)

# FP-SCHED-2: a booking is only created while the application is Interviewing.
# ``new_booking:a`` is emitted on the step that successfully booked; the same
# state slice must also contain ``status:a:Interviewing``.
L2_BOOKING_REQUIRES_INTERVIEWING = forall(
    ("a",),
    G(
        Implies(
            Atom("new_booking:?a"),
            Atom("status:?a:Interviewing"),
        )
    ),
)

# FP-SCHED-2: a booking is not unbound when the application later leaves
# Interviewing.  Once ``booked:a:s`` appears, it must hold in every later slice.
L3_BOOKING_IS_PERMANENT = forall(
    ("a", "s"),
    G(Implies(Atom("booked:?a:?s"), G(Atom("booked:?a:?s")))),
)

# FP-SCHED-1: a booked slot is never deleted (deletion of a booked slot is
# rejected, so the slot row and therefore ``slot:s`` stay present).
L4_BOOKED_SLOT_IS_PERMANENT = forall(
    ("a", "s"),
    G(Implies(Atom("booked:?a:?s"), G(Atom("slot:?s")))),
)

# FP-CAN-3: an application row never disappears; the only deletion in the
# lifecycle is the soft delete of a job posting, not of an application.
L5_APPLICATION_IS_PERMANENT = forall(
    ("a",),
    G(Implies(Atom("applied:?a"), G(Atom("applied:?a")))),
)

PROPERTIES: tuple[Property, ...] = (
    Property(
        "L1",
        "a booked slot never becomes available again",
        "FP-SCHED-1 / FP-SCHED-2",
        L1_BOOKED_STAYS_UNAVAILABLE,
        "A successful booking must keep the slot unavailable even after the "
        "application later changes status (FP-SCHED-2).",
    ),
    Property(
        "L2",
        "a booking is created only while the application is Interviewing",
        "FP-SCHED-2",
        L2_BOOKING_REQUIRES_INTERVIEWING,
        "The step that emits new_booking:a must also show "
        "status:a:Interviewing.",
    ),
    Property(
        "L3",
        "an existing booking never disappears",
        "FP-SCHED-2",
        L3_BOOKING_IS_PERMANENT,
        "A later status change must not unbind the application or the slot.",
    ),
    Property(
        "L4",
        "a booked slot is never deleted",
        "FP-SCHED-1",
        L4_BOOKED_SLOT_IS_PERMANENT,
        "Deleting a booked slot is rejected, so slot:s must survive every "
        "later step.",
    ),
    Property(
        "L5",
        "an application never disappears",
        "FP-CAN-3",
        L5_APPLICATION_IS_PERMANENT,
        "Applications are only created, never deleted; deleting a posting is "
        "a soft delete of the posting.",
    ),
)

BY_ID: dict[str, Property] = {
    property_.identifier: property_ for property_ in PROPERTIES
}


# ---------------------------------------------------------------------------
# Vacuity instrumentation
# ---------------------------------------------------------------------------


def antecedent_of(formula: Formula) -> Formula | None:
    """Return the antecedent ``p`` of ``forall...: G(p -> q)``.

    Returns ``None`` when the outermost shape is not a quantified ``G`` of an
    implication.  The helper is deliberately structural: the statistics below
    must count exactly the implication antecedent the property asserts.
    """

    node: Formula = formula
    while isinstance(node, (Forall, Exists)):
        node = node.body
    if isinstance(node, G) and isinstance(node.body, Implies):
        return node.body.left
    return None


def quantified_variables(formula: Formula) -> tuple[str, ...]:
    """Return the variables of the outermost quantifier (innermost first only)."""

    if isinstance(formula, (Forall, Exists)):
        return formula.variables
    return ()


def _antecedent_atoms(antecedent: Formula) -> list[Atom]:
    return [node for _, node in walk(antecedent) if isinstance(node, Atom)]


def _bindings_at_step(
    antecedent: Formula, variables: Sequence[str], event: Event
) -> set[tuple[str, ...]]:
    """Return every antecedent binding in *event* that covers all variables.

    A state slice can contain several ``booked`` atoms when more than one
    application has been booked, so collecting only the first match would
    under-count the trigger instances used by the vacuity report.
    """

    found: set[tuple[str, ...]] = set()
    for atom in _antecedent_atoms(antecedent):
        for prop in event.props:
            binding = match_atom(atom.pattern, prop)
            if binding is None:
                continue
            try:
                values = tuple(binding[variable] for variable in variables)
            except KeyError:
                continue
            found.add(values)
    return found


def trigger_bindings(
    formula: Formula, trace: Sequence[Event]
) -> set[tuple[str, ...]]:
    """Return distinct antecedent bindings that occur anywhere in *trace*.

    For L1 this is the set of distinct ``(a, s)`` pairs that were ever booked.
    A non-empty result means the implication's antecedent fired at least once;
    an empty result means the property is vacuously satisfied on this trace.
    """

    antecedent = antecedent_of(formula)
    if antecedent is None:
        return set()
    variables = quantified_variables(formula)
    if not variables:
        return set()
    found: set[tuple[str, ...]] = set()
    for event in trace:
        found.update(_bindings_at_step(antecedent, variables, event))
    return found


def trigger_steps(formula: Formula, trace: Sequence[Event]) -> int:
    """Count states in *trace* at which the antecedent can be instantiated."""

    antecedent = antecedent_of(formula)
    if antecedent is None:
        return 0
    variables = quantified_variables(formula)
    if not variables:
        return 0
    return sum(
        1
        for event in trace
        if _bindings_at_step(antecedent, variables, event)
    )
