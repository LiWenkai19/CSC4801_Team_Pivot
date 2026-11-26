"""Relax/restrict property refinement demo (lecture L13, slides 46-52).

The lecture describes two dual operations on a temporal property:

* **relax** -- when a property has a counterexample, replace one operator by a
  weaker one (``X -> F``, ``G -> F``, drop a conjunct, ``U -> F(right)``) and
  repeat until every observed trace is accepted.  The chain ``F -> F' -> F''``
  and the accepted-trace ratio at every step is a logic-based measure of how far
  the system deviates from the intended property.
* **restrict** -- when a property has no counterexample, strengthen one
  operator (``F -> G``, ``F -> X``) to see whether the trace set actually
  exercises the weaker property or whether it was satisfied vacuously.

The demo deliberately starts from the over-strong property

``forall a: G(status(a, Interviewing) -> X(status(a, Interviewing) U booked(a, _)))``

("as soon as an application is Interviewing, it stays Interviewing until it is
booked, starting at the very next step").  Business requirements do not promise
that: an employer may reject or accept the application, or the trace may end
while it is still Interviewing.  This is the same ``G(a -> X(b U c))`` shape as
slide 46, instantiated with the booking vocabulary from ``properties.py``.

The random choice of operator is deterministic: ``random.Random(seed)`` and a
stable pre-order traversal mean the same seed always produces the same chain.
``test_booking_traces.py`` asserts that reproducibility.
"""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Sequence

from support.ltl import (
    And,
    Atom,
    F,
    Formula,
    G,
    Implies,
    Not,
    Or,
    U,
    X,
    evaluate,
    exists,
    explain,
    forall,
    replace_at,
    walk,
)
from support.traces import Event

__all__ = [
    "DEMO_PROPERTY",
    "DEMO_TITLE",
    "RefinementResult",
    "RefinementStep",
    "format_chain",
    "relax",
    "restrictions",
    "run_demo",
    "weakenings",
]


#: The over-strong property used by the demo (see the module docstring).
DEMO_TITLE = (
    "every Interviewing application stays Interviewing until it is booked, "
    "starting at the very next step"
)
DEMO_PROPERTY: Formula = forall(
    ("a",),
    G(
        Implies(
            Atom("status:?a:Interviewing"),
            X(
                U(
                    Atom("status:?a:Interviewing"),
                    exists(("s",), Atom("booked:?a:?s")),
                )
            ),
        )
    ),
)


# ---------------------------------------------------------------------------
# One refinement step
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RefinementStep:
    """One formula in a refinement chain, with its acceptance count."""

    label: str
    formula: Formula
    satisfied: int
    total: int
    operation: str | None = None

    @property
    def ratio(self) -> float:
        return 0.0 if self.total == 0 else self.satisfied / self.total

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "formula": str(self.formula),
            "satisfied": self.satisfied,
            "total": self.total,
            "ratio": round(self.ratio, 6),
            "operation": self.operation,
        }


@dataclass(frozen=True)
class RefinementResult:
    """The relax chain and the optional restrict probe."""

    seed: int
    property: Formula
    steps: tuple[RefinementStep, ...]
    restricted: RefinementStep | None = None
    restricted_from: int | None = None
    counterexample: str | None = None
    restriction_candidates: tuple[RefinementStep, ...] = ()

    def to_dict(self) -> dict:
        return {
            "seed": self.seed,
            "property": str(self.property),
            "title": DEMO_TITLE,
            "steps": [step.to_dict() for step in self.steps],
            "restricted": (
                None if self.restricted is None else self.restricted.to_dict()
            ),
            "restricted_from": self.restricted_from,
            "counterexample": self.counterexample,
            "restriction_candidates": [
                step.to_dict() for step in self.restriction_candidates
            ],
        }


# ---------------------------------------------------------------------------
# Candidate operators
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Choice:
    """A single operator replacement at a deterministic tree path."""

    path: tuple[int, ...]
    description: str
    replacement: Formula


def _prime(index: int) -> str:
    """Return ``F``, ``F'``, ``F''``, ... for chain labels."""

    return "F" + "'" * index


def _step(
    formula: Formula, label: str, operation: str | None, traces: Sequence
) -> RefinementStep:
    satisfied = sum(1 for trace in traces if evaluate(formula, trace))
    return RefinementStep(
        label=label,
        formula=formula,
        satisfied=satisfied,
        total=len(traces),
        operation=operation,
    )


def weakenings(formula: Formula) -> list[_Choice]:
    """Return the lecture's weakening replacements, in stable pre-order.

    Primary relaxations (slide 46): ``X -> F``, ``G -> F``, drop a conjunct and
    ``U -> F(right)``.  ``F -> true`` and ``WX -> true`` are only offered by
    :func:`_fallbacks` once the primary list is exhausted, so the demo does not
    jump straight to a tautology.
    """

    choices: list[_Choice] = []
    for path, node in walk(formula):
        if isinstance(node, X):
            choices.append(
                _Choice(path, "X -> F", F(node.body))
            )
        elif isinstance(node, G):
            choices.append(
                _Choice(path, "G -> F", F(node.body))
            )
        elif isinstance(node, And):
            choices.append(
                _Choice(path, "drop right conjunct", node.left)
            )
            choices.append(
                _Choice(path, "drop left conjunct", node.right)
            )
        elif isinstance(node, U):
            choices.append(
                _Choice(path, "U -> F(right)", F(node.right))
            )
    return choices


def _fallbacks(formula: Formula) -> list[_Choice]:
    """Last-resort weakenings that make a formula trivially true."""

    choices: list[_Choice] = []
    for path, node in walk(formula):
        if isinstance(node, F):
            choices.append(_Choice(path, "F -> true", _tautology()))
    return choices


def _tautology() -> Formula:
    """A closed formula that is true on every trace."""

    marker = Atom("__ltl_true__")
    return Or(marker, Not(marker))


def restrictions(formula: Formula) -> list[_Choice]:
    """Return the lecture's restriction replacements (slide 47): F -> G, F -> X."""

    choices: list[_Choice] = []
    for path, node in walk(formula):
        if isinstance(node, F):
            choices.append(_Choice(path, "F -> G", G(node.body)))
            choices.append(_Choice(path, "F -> X", X(node.body)))
    return choices


# ---------------------------------------------------------------------------
# Algorithms
# ---------------------------------------------------------------------------


def _apply(formula: Formula, choice: _Choice) -> Formula:
    return replace_at(formula, choice.path, choice.replacement)


def relax(
    formula: Formula,
    traces: Sequence[Sequence[Event]],
    *,
    seed: int = 4801,
    max_steps: int = 25,
) -> tuple[tuple[RefinementStep, ...], random.Random]:
    """Relax *formula* until every trace is accepted (or fall back to true).

    Returns the chain (the initial formula is the first step) and the generator
    that made the choices, so :func:`run_demo` can continue the same random
    stream for the restrict probe.
    """

    traces = tuple(traces)
    total = len(traces)
    generator = random.Random(seed)
    steps: list[RefinementStep] = [
        _step(formula, "F", None, traces)
    ]
    current = formula
    for _ in range(max_steps):
        if steps[-1].satisfied >= total:
            break
        choices = weakenings(current)
        if not choices:
            choices = _fallbacks(current)
        if not choices:  # pragma: no cover - only for malformed custom nodes
            break
        choice = generator.choice(choices)
        current = _apply(current, choice)
        steps.append(
            _step(current, _prime(len(steps)), choice.description, traces)
        )
    if steps[-1].satisfied < total:  # pragma: no cover - safety net
        steps.append(
            _step(
                _tautology(),
                _prime(len(steps)),
                "fallback: true",
                traces,
            )
        )
    return tuple(steps), generator


def run_demo(
    traces: Sequence[Sequence[Event]], *, seed: int = 4801
) -> RefinementResult:
    """Run the full relax chain and one restrict probe.

    The restrict probe starts from the last chain formula that is accepted by
    every trace (walking backwards so it still works if the chain ended in a
    tautology without an ``F``).  One random ``F -> G`` or ``F -> X`` is applied
    and the accepted-trace count is recorded; if that count drops, the first
    violation is kept as a reviewer-readable counterexample.
    """

    traces = tuple(tuple(trace) for trace in traces)
    steps, generator = relax(DEMO_PROPERTY, traces, seed=seed)
    total = len(traces)

    restricted: RefinementStep | None = None
    restricted_from: int | None = None
    counterexample: str | None = None
    probes: tuple[RefinementStep, ...] = ()
    for index in range(len(steps) - 1, -1, -1):
        if steps[index].satisfied < total:
            continue
        choices = restrictions(steps[index].formula)
        if not choices:
            continue
        # Try every F -> G / F -> X candidate on the last fully accepted
        # formula.  One is chosen with the same deterministic generator for the
        # headline probe; the full list shows whether the restriction exposed a
        # counterexample or the trace set simply never exercised that operator.
        candidate_steps = tuple(
            _step(
                _apply(steps[index].formula, choice),
                f"R{candidate}",
                f"restrict {steps[index].label}: {choice.description}",
                traces,
            )
            for candidate, choice in enumerate(choices)
        )
        probes = candidate_steps
        restricted = generator.choice(candidate_steps)
        restricted_from = index
        if restricted.satisfied < total:
            failing = next(
                trace
                for trace in traces
                if not evaluate(restricted.formula, trace)
            )
            counterexample = explain(restricted.formula, failing)
        break
    return RefinementResult(
        seed=seed,
        property=DEMO_PROPERTY,
        steps=steps,
        restricted=restricted,
        restricted_from=restricted_from,
        counterexample=counterexample,
        restriction_candidates=probes,
    )


def format_chain(result: RefinementResult) -> str:
    """Render a refinement result as the chain printed in the report."""

    total = result.steps[0].total
    lines = [
        f"seed={result.seed}  traces={total}  property={result.property}",
    ]
    for step in result.steps:
        percentage = 0.0 if not step.total else 100.0 * step.ratio
        operation = f"  [{step.operation}]" if step.operation else ""
        lines.append(
            f"{step.label:>5}  {step.satisfied:>3}/{step.total} accepted "
            f"({percentage:5.1f}%){operation}"
        )
        lines.append(f"       {step.formula}")
    if result.restricted is not None:
        step = result.restricted
        percentage = 0.0 if not step.total else 100.0 * step.ratio
        lines.append(
            f"{step.label:>5}  {step.satisfied:>3}/{step.total} accepted "
            f"({percentage:5.1f}%)  [{step.operation}]"
        )
        lines.append(f"       {step.formula}")
        if result.counterexample:
            lines.append("       counterexample returned by the restriction:")
            for line in result.counterexample.splitlines():
                lines.append("       " + line)
    if result.restriction_candidates:
        lines.append("restriction candidates on the last accepted formula:")
        for step in result.restriction_candidates:
            marker = "chosen" if step == result.restricted else "also  "
            lines.append(
                f"  {marker} {step.label}: {step.satisfied}/{step.total} "
                f"accepted  [{step.operation}]"
            )
    return "\n".join(lines)


def _main(argv: Sequence[str]) -> int:  # pragma: no cover - manual demo entry
    """Print the demo for a directory of trace JSON files."""

    from pathlib import Path

    from support.traces import read_traces

    if len(argv) != 1:
        print("usage: python refine.py <trace-directory>")
        return 2
    traces = read_traces(Path(argv[0]))
    result = run_demo(traces)
    print(format_chain(result))
    return 0


if __name__ == "__main__":  # pragma: no cover - manual demo entry
    import sys

    raise SystemExit(_main(sys.argv[1:]))
