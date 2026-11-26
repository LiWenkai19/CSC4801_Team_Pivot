"""Finite-trace linear temporal logic (LTL) for the P3 booking checker.

This module is an **independent oracle**: it knows nothing about the application
under test, only about the trace format in :mod:`support.traces`.  The P2 state
machine writes one event per step, where ``Event.props`` is the set of atomic
propositions that hold *after* that step (a state slice, not a delta).  The
checker therefore evaluates properties over a finite sequence of states.

Syntax
------

The AST can be built with Python constructors (no parser and no third-party LTL
package)::

    from support.ltl import And, Atom, F, G, Implies, Not, X, forall

    formula = forall(
        ("a", "s"),
        G(Implies(Atom("booked:?a:?s"), Not(Atom("available:?s")))),
    )

Atoms are proposition patterns.  A ``?name`` segment is a variable; every other
segment is a literal and is compared exactly (case-sensitively), so
``status:a1:Interviewing`` and ``status:a1:intervewing`` are different atoms and
the application's original status spelling matters.  A pattern matches an atom
with the same number of ``:``-separated segments::

    Atom("booked:?a:?s")   matches  "booked:a1:s1"  binding {a: a1, s: s1}
    Atom("available:?s")   matches  "available:s1"  binding {s: s1}
    Atom("slot:s1")        matches  only "slot:s1"

Quantifiers
-----------

``forall(variables, body)`` and ``exists(variables, body)`` implement finite
domain quantification over the trace itself: the domain of a variable is the
set of values that occur in trace atoms matching an atom pattern of ``body`` in
which that variable is free.  Values that never occur are not enumerated, so a
quantifier over an empty domain is vacuously true (``forall``) or false
(``exists``).  This is why the P3 report also counts non-vacuous satisfaction:
``G(p -> q)`` is satisfied by a trace in which ``p`` never holds, but that is
not evidence for the implication.

Semantics on a finite trace
---------------------------

Let ``s = [e_0, ..., e_{n-1}]`` and let ``i`` be a suffix index with
``0 <= i <= n``.  ``e_i.props`` is the set of atoms true after step ``i``.
The operators are interpreted as follows (``n`` is the trace length):

===================  ==================================================
``Atom(p)``          ``i < n`` and ``p`` (after bindings) is in ``e_i.props``
``!phi``             ``not eval(phi, i)``
``phi & psi``        ``eval(phi, i) and eval(psi, i)``
``phi | psi``        ``eval(phi, i) or eval(psi, i)``
``phi -> psi``       ``not eval(phi, i) or eval(psi, i)``
``X phi``            ``i + 1 < n`` and ``eval(phi, i + 1)``
                     (strong next: false at the last state)
``WX phi``           ``i + 1 >= n`` or ``eval(phi, i + 1)``
                     (weak next: true at the last state)
``G phi``            ``eval(phi, k)`` for every ``k`` in ``[i, n)``
                     (vacuously true for an empty suffix)
``F phi``            ``eval(phi, k)`` for some ``k`` in ``[i, n)``
``phi U psi``        there is ``k`` in ``[i, n)`` with ``eval(psi, k)`` and
                     ``eval(phi, j)`` for every ``j`` in ``[i, k)``
===================  ==================================================

Two boundary cases are deliberate and are tested:

* an **empty trace** satisfies every ``G`` and every ``WX``, violates every
  ``F``, ``U``, ``X`` and atom, and satisfies ``forall`` over its empty domain;
* the **last state** is where strong and weak next differ: ``X p`` is false
  there, ``WX p`` is true there.

``evaluate`` rejects a formula that still has free variables; wrap it in
``forall(...)`` (or ``exists(...)``) first.  ``explain`` locates the earliest
step that makes the formula fail and prints that step's event, which is the
counterexample a reviewer needs.

This module contains no randomness and no application imports, so it is usable
by the self-tests without PostgreSQL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
import re
from typing import Iterable, Iterator, Sequence

__all__ = [
    "And",
    "Atom",
    "Exists",
    "F",
    "Forall",
    "Formula",
    "G",
    "Implies",
    "Not",
    "Or",
    "U",
    "WX",
    "X",
    "evaluate",
    "exists",
    "explain",
    "forall",
    "format_formula",
    "match_atom",
    "replace_at",
    "trace_atoms",
    "walk",
]

_VARIABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------


class Formula:
    """Base class for the immutable LTL AST.

    Subclasses are frozen dataclasses, so structural equality and hashing come
    for free and a refinement step can be compared with the previous formula.
    """

    def children(self) -> tuple["Formula", ...]:
        """Return the immediate subformulas in a stable left-to-right order."""

        return ()

    def with_children(self, children: Sequence["Formula"]) -> "Formula":
        """Return a copy with the immediate subformulas replaced by *children*."""

        raise NotImplementedError(f"{type(self).__name__} has no children")

    def free_variables(self) -> frozenset[str]:
        """Return the variables that occur free in this formula."""

        variables: set[str] = set()
        for child in self.children():
            variables.update(child.free_variables())
        return frozenset(variables)

    def __str__(self) -> str:  # pragma: no cover - overridden by every node
        return type(self).__name__


@dataclass(frozen=True)
class Atom(Formula):
    """An atomic proposition or a proposition pattern with ``?variables``."""

    pattern: str
    _segments: tuple[str, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.pattern, str):
            raise TypeError("Atom pattern must be a string")
        if not self.pattern:
            raise ValueError("Atom pattern must be non-empty")
        segments = tuple(self.pattern.split(":"))
        if any(segment == "" for segment in segments):
            raise ValueError(
                f"Atom pattern {self.pattern!r} has an empty ':' segment"
            )
        for segment in segments:
            if segment.startswith("?"):
                name = segment[1:]
                if not _VARIABLE.match(name):
                    raise ValueError(
                        f"Atom pattern {self.pattern!r} has an invalid "
                        f"variable segment {segment!r}"
                    )
        object.__setattr__(self, "_segments", segments)

    @property
    def segments(self) -> tuple[str, ...]:
        """Return the pattern split on ``:`` (``?name`` segments are variables)."""

        return self._segments

    def free_variables(self) -> frozenset[str]:
        return frozenset(
            segment[1:]
            for segment in self._segments
            if segment.startswith("?")
        )

    def __str__(self) -> str:
        return self.pattern


@dataclass(frozen=True)
class Not(Formula):
    """Logical negation."""

    body: Formula

    def children(self) -> tuple[Formula, ...]:
        return (self.body,)

    def with_children(self, children: Sequence[Formula]) -> Formula:
        (body,) = children
        return Not(body)

    def __str__(self) -> str:
        return f"!{_operand(self.body)}"


@dataclass(frozen=True)
class And(Formula):
    """Logical conjunction."""

    left: Formula
    right: Formula

    def children(self) -> tuple[Formula, ...]:
        return (self.left, self.right)

    def with_children(self, children: Sequence[Formula]) -> Formula:
        left, right = children
        return And(left, right)

    def __str__(self) -> str:
        return f"({self.left} & {self.right})"


@dataclass(frozen=True)
class Or(Formula):
    """Logical disjunction."""

    left: Formula
    right: Formula

    def children(self) -> tuple[Formula, ...]:
        return (self.left, self.right)

    def with_children(self, children: Sequence[Formula]) -> Formula:
        left, right = children
        return Or(left, right)

    def __str__(self) -> str:
        return f"({self.left} | {self.right})"


@dataclass(frozen=True)
class Implies(Formula):
    """Logical implication ``left -> right``."""

    left: Formula
    right: Formula

    def children(self) -> tuple[Formula, ...]:
        return (self.left, self.right)

    def with_children(self, children: Sequence[Formula]) -> Formula:
        left, right = children
        return Implies(left, right)

    def __str__(self) -> str:
        return f"({self.left} -> {self.right})"


@dataclass(frozen=True)
class X(Formula):
    """Strong next: ``X phi`` is false on the last state of a finite trace."""

    body: Formula

    def children(self) -> tuple[Formula, ...]:
        return (self.body,)

    def with_children(self, children: Sequence[Formula]) -> Formula:
        (body,) = children
        return X(body)

    def __str__(self) -> str:
        return f"X({self.body})"


@dataclass(frozen=True)
class WX(Formula):
    """Weak next: ``WX phi`` is true on the last state of a finite trace."""

    body: Formula

    def children(self) -> tuple[Formula, ...]:
        return (self.body,)

    def with_children(self, children: Sequence[Formula]) -> Formula:
        (body,) = children
        return WX(body)

    def __str__(self) -> str:
        return f"WX({self.body})"


@dataclass(frozen=True)
class G(Formula):
    """Always: ``G phi`` holds on every state of the remaining suffix."""

    body: Formula

    def children(self) -> tuple[Formula, ...]:
        return (self.body,)

    def with_children(self, children: Sequence[Formula]) -> Formula:
        (body,) = children
        return G(body)

    def __str__(self) -> str:
        return f"G({self.body})"


@dataclass(frozen=True)
class F(Formula):
    """Eventually: ``F phi`` holds on some state of the remaining suffix."""

    body: Formula

    def children(self) -> tuple[Formula, ...]:
        return (self.body,)

    def with_children(self, children: Sequence[Formula]) -> Formula:
        (body,) = children
        return F(body)

    def __str__(self) -> str:
        return f"F({self.body})"


@dataclass(frozen=True)
class U(Formula):
    """Until: ``left U right`` (``right`` must eventually hold, ``left``
    must hold at every earlier state of the suffix)."""

    left: Formula
    right: Formula

    def children(self) -> tuple[Formula, ...]:
        return (self.left, self.right)

    def with_children(self, children: Sequence[Formula]) -> Formula:
        left, right = children
        return U(left, right)

    def __str__(self) -> str:
        return f"({self.left} U {self.right})"


@dataclass(frozen=True)
class Forall(Formula):
    """Finite-domain universal quantification over values observed in a trace."""

    variables: tuple[str, ...]
    body: Formula

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "variables", _normalize_variables(self.variables, "forall")
        )

    def children(self) -> tuple[Formula, ...]:
        return (self.body,)

    def with_children(self, children: Sequence[Formula]) -> Formula:
        (body,) = children
        return Forall(self.variables, body)

    def free_variables(self) -> frozenset[str]:
        return self.body.free_variables() - frozenset(self.variables)

    def __str__(self) -> str:
        return f"forall {', '.join(self.variables)}: {self.body}"


@dataclass(frozen=True)
class Exists(Formula):
    """Finite-domain existential quantification over values observed in a trace.

    ``Exists`` is not required by the P3 specification; it is included because
    the natural formulation of "an application eventually gets *some* booking"
    needs ``exists s: booked(a, s)`` and the refinement demo uses it.
    """

    variables: tuple[str, ...]
    body: Formula

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "variables", _normalize_variables(self.variables, "exists")
        )

    def children(self) -> tuple[Formula, ...]:
        return (self.body,)

    def with_children(self, children: Sequence[Formula]) -> Formula:
        (body,) = children
        return Exists(self.variables, body)

    def free_variables(self) -> frozenset[str]:
        return self.body.free_variables() - frozenset(self.variables)

    def __str__(self) -> str:
        return f"exists {', '.join(self.variables)}: {self.body}"


def _operand(formula: Formula) -> str:
    """Render *formula* for unary syntax without redundant parentheses."""

    if isinstance(formula, (Atom, Not, X, WX, G, F)):
        return str(formula)
    return f"({formula})"


def _normalize_variables(
    variables: Iterable[str] | str, where: str
) -> tuple[str, ...]:
    """Normalize a quantifier's variable list, accepting ``"a, s"`` or ``("a", "s")``."""

    if isinstance(variables, str):
        items: list[str] = (
            variables.replace(",", " ").replace("?", " ").split()
        )
    else:
        items = list(variables)
    if not items:
        raise ValueError(f"{where} needs at least one variable")
    names: list[str] = []
    for item in items:
        name = item[1:] if item.startswith("?") else item
        if not _VARIABLE.match(name):
            raise ValueError(f"{where} has an invalid variable name {item!r}")
        if name in names:
            raise ValueError(f"{where} repeats the variable {name!r}")
        names.append(name)
    return tuple(names)


def forall(variables: Iterable[str] | str, formula: Formula) -> Forall:
    """Convenience constructor for :class:`Forall`."""

    return Forall(_normalize_variables(variables, "forall"), formula)


def exists(variables: Iterable[str] | str, formula: Formula) -> Exists:
    """Convenience constructor for :class:`Exists`."""

    return Exists(_normalize_variables(variables, "exists"), formula)


# ---------------------------------------------------------------------------
# AST traversal (used by the refinement demo and by tests)
# ---------------------------------------------------------------------------


def walk(formula: Formula) -> Iterator[tuple[tuple[int, ...], Formula]]:
    """Yield ``(path, subformula)`` in a deterministic pre-order.

    A path is a tuple of child indexes; the root has path ``()``.
    """

    yield (), formula
    for index, child in enumerate(formula.children()):
        for suffix, node in walk(child):
            yield (index,) + suffix, node


def replace_at(
    formula: Formula, path: Sequence[int], replacement: Formula
) -> Formula:
    """Return a copy of *formula* with the subformula at *path* replaced."""

    path = tuple(path)
    if not path:
        return replacement
    head, *rest = path
    children = list(formula.children())
    if not 0 <= head < len(children):
        raise IndexError(f"path {path!r} does not address a child of {formula}")
    children[head] = replace_at(children[head], rest, replacement)
    return formula.with_children(tuple(children))


def format_formula(formula: Formula) -> str:
    """Return a stable textual rendering (equivalent to ``str(formula)``)."""

    return str(formula)


# ---------------------------------------------------------------------------
# Atom matching
# ---------------------------------------------------------------------------


def _match_segments(
    segments: Sequence[str], atom: str
) -> dict[str, str] | None:
    """Match split pattern *segments* against concrete *atom*."""

    parts = atom.split(":")
    if len(parts) != len(segments):
        return None
    binding: dict[str, str] = {}
    for segment, part in zip(segments, parts):
        if segment.startswith("?"):
            name = segment[1:]
            previous = binding.get(name)
            if previous is not None and previous != part:
                return None
            binding[name] = part
        elif segment != part:
            return None
    return binding


def match_atom(pattern: str, atom: str) -> dict[str, str] | None:
    """Match one atom pattern against one concrete atom.

    Returns the variable binding or ``None``.  An atom without variables is a
    valid pattern and binds nothing.
    """

    return _match_segments(tuple(pattern.split(":")), atom)


def _binding(atom: Atom, prop: str) -> dict[str, str] | None:
    return _match_segments(atom.segments, prop)


def _substitute(
    segments: Sequence[str], environment: dict[str, str]
) -> tuple[str, ...]:
    """Replace bound ``?variables`` in *segments*; leave free ones untouched."""

    return tuple(
        environment.get(segment[1:], segment)
        if segment.startswith("?")
        else segment
        for segment in segments
    )


def _render(formula: Formula, environment: dict[str, str]) -> str:
    """Render *formula* with bound variables substituted for a message."""

    if isinstance(formula, Atom):
        return ":".join(_substitute(formula.segments, environment))
    return str(formula)


# ---------------------------------------------------------------------------
# Trace helpers
# ---------------------------------------------------------------------------


def _validate_trace(trace) -> tuple:
    """Return the trace as a tuple and check the minimal Event contract."""

    if isinstance(trace, (str, bytes)):
        raise TypeError("trace must be a sequence of events, not a string")
    try:
        events = tuple(trace)
    except TypeError as exc:
        raise TypeError("trace must be an iterable of events") from exc
    for position, event in enumerate(events):
        props = getattr(event, "props", None)
        if props is None:
            raise TypeError(
                f"trace event {position} has no 'props' attribute: {event!r}"
            )
        for atom in props:
            if not isinstance(atom, str):
                raise TypeError(
                    f"trace event {position} has a non-string atom: {atom!r}"
                )
    return events


def trace_atoms(trace) -> frozenset[str]:
    """Return every atomic proposition that occurs anywhere in *trace*."""

    return frozenset(atom for event in _validate_trace(trace) for atom in event.props)


def _ensure_closed(formula: Formula) -> None:
    free = formula.free_variables()
    if free:
        raise ValueError(
            "formula has free variable(s) "
            f"{sorted(free)}; wrap it with forall(...) or exists(...)"
        )


# ---------------------------------------------------------------------------
# Quantifier domains and assignments
# ---------------------------------------------------------------------------


def _atoms_for_variable(
    formula: Formula, variable: str
) -> Iterator[Atom]:
    """Yield atoms in which *variable* is free, respecting nested binders."""

    if isinstance(formula, (Forall, Exists)):
        if variable in formula.variables:
            return
        yield from _atoms_for_variable(formula.body, variable)
        return
    if isinstance(formula, Atom):
        if variable in formula.free_variables():
            yield formula
        return
    for child in formula.children():
        yield from _atoms_for_variable(child, variable)


def _quantifier_domains(
    formula: Forall | Exists, trace: tuple, environment: dict[str, str]
) -> dict[str, tuple[str, ...]]:
    """Collect the finite domain of every variable of *formula* from *trace*.

    The domain of variable ``v`` is the set of values observed in trace atoms
    whose *shape* matches an atom pattern of the quantifier body in which ``v``
    is free.  A shape match uses the namespace (first segment) and the number of
    ``:``-separated segments, and compares segments that are already bound by an
    outer quantifier; it deliberately ignores an unbound pattern's non-leading
    literals.  Otherwise ``status:?a:Interviewing`` would miss an application
    that currently has ``status:a1:Rejected`` and the quantification would be
    silently too small (see the "domain is collected from the trace" tests).

    Outer bindings are substituted first; an inner binder shadows an outer one.
    """

    basis = {
        name: value
        for name, value in environment.items()
        if name not in formula.variables
    }
    domains: dict[str, tuple[str, ...]] = {}
    for variable in formula.variables:
        values: set[str] = set()
        patterns = [
            atom.segments
            for atom in _atoms_for_variable(formula.body, variable)
        ]
        for event in trace:
            for prop in event.props:
                for segments in patterns:
                    binding = _structural_binding(segments, prop, basis)
                    if binding is not None and variable in binding:
                        values.add(binding[variable])
        domains[variable] = tuple(sorted(values))
    return domains


def _structural_binding(
    segments: Sequence[str], atom: str, environment: dict[str, str]
) -> dict[str, str] | None:
    """Bind free pattern variables from *atom* for domain collection.

    The first segment must match exactly (the namespace); later literal
    segments are ignored because they usually encode a *value* of the domain
    variable rather than a property of the domain.  Segments bound by an outer
    quantifier are compared exactly, so ``booked:?a:?s`` with ``a = a1`` only
    contributes slots actually booked to ``a1``.
    """

    parts = atom.split(":")
    if len(parts) != len(segments):
        return None
    binding: dict[str, str] = {}
    for position, (segment, part) in enumerate(zip(segments, parts)):
        if segment.startswith("?"):
            name = segment[1:]
            if name in environment:
                if environment[name] != part:
                    return None
            else:
                binding[name] = part
        elif position == 0 and segment != part:
            return None
    return binding


def _assignments(
    variables: Sequence[str], domains: dict[str, tuple[str, ...]]
) -> Iterator[dict[str, str]]:
    """Yield assignments in sorted, deterministic order."""

    if any(not domains[variable] for variable in variables):
        return
    for combination in product(*(domains[variable] for variable in variables)):
        yield dict(zip(variables, combination))


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------


def evaluate(formula: Formula, trace, i: int = 0) -> bool:
    """Evaluate *formula* on the finite *trace* starting at suffix *i*.

    Parameters
    ----------
    formula:
        A closed formula (no free variables).  Build parameterized properties
        with :func:`forall` so the checker enumerates every value observed in
        the trace before evaluating the body.
    trace:
        A sequence of objects exposing a ``props`` iterable of atom strings,
        normally :class:`support.traces.Event` read with
        :func:`support.traces.read_traces`.
    i:
        Suffix index, ``0 <= i <= len(trace)``.  ``i == len(trace)`` is the
        empty suffix: ``G`` and ``WX`` hold there, ``F``, ``U``, ``X`` and
        atoms do not.

    See the module docstring for the exact finite-trace semantics.
    """

    if not isinstance(formula, Formula):
        raise TypeError("formula must be a support.ltl.Formula")
    events = _validate_trace(trace)
    if isinstance(i, bool) or not isinstance(i, int):
        raise TypeError("i must be an integer")
    if not 0 <= i <= len(events):
        raise ValueError(
            f"suffix index {i} is outside [0, {len(events)}] for this trace"
        )
    _ensure_closed(formula)
    return _evaluate(formula, events, i, {})


def _evaluate(
    formula: Formula, trace: tuple, index: int, environment: dict[str, str]
) -> bool:
    length = len(trace)

    if isinstance(formula, Atom):
        segments = _substitute(formula.segments, environment)
        remaining = [segment for segment in segments if segment.startswith("?")]
        if remaining:
            raise ValueError(
                f"atom {formula.pattern!r} still has free variable(s) "
                f"{sorted(segment[1:] for segment in remaining)}"
            )
        if index >= length:
            return False
        return ":".join(segments) in trace[index].props

    if isinstance(formula, Not):
        return not _evaluate(formula.body, trace, index, environment)

    if isinstance(formula, And):
        return _evaluate(formula.left, trace, index, environment) and _evaluate(
            formula.right, trace, index, environment
        )

    if isinstance(formula, Or):
        return _evaluate(formula.left, trace, index, environment) or _evaluate(
            formula.right, trace, index, environment
        )

    if isinstance(formula, Implies):
        return not _evaluate(
            formula.left, trace, index, environment
        ) or _evaluate(formula.right, trace, index, environment)

    if isinstance(formula, X):
        return index + 1 < length and _evaluate(
            formula.body, trace, index + 1, environment
        )

    if isinstance(formula, WX):
        return index + 1 >= length or _evaluate(
            formula.body, trace, index + 1, environment
        )

    if isinstance(formula, G):
        return all(
            _evaluate(formula.body, trace, position, environment)
            for position in range(index, length)
        )

    if isinstance(formula, F):
        return any(
            _evaluate(formula.body, trace, position, environment)
            for position in range(index, length)
        )

    if isinstance(formula, U):
        for position in range(index, length):
            if _evaluate(formula.right, trace, position, environment):
                return True
            if not _evaluate(formula.left, trace, position, environment):
                return False
        return False

    if isinstance(formula, Forall):
        domains = _quantifier_domains(formula, trace, environment)
        if any(not domains[variable] for variable in formula.variables):
            return True
        for assignment in _assignments(formula.variables, domains):
            merged = {**environment, **assignment}
            if not _evaluate(formula.body, trace, index, merged):
                return False
        return True

    if isinstance(formula, Exists):
        domains = _quantifier_domains(formula, trace, environment)
        if any(not domains[variable] for variable in formula.variables):
            return False
        for assignment in _assignments(formula.variables, domains):
            merged = {**environment, **assignment}
            if _evaluate(formula.body, trace, index, merged):
                return True
        return False

    raise TypeError(f"unsupported formula node: {type(formula).__name__}")


# ---------------------------------------------------------------------------
# Explanation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Violation:
    """Where and why a formula fails, in reviewer-readable form."""

    index: int
    reason: str
    assignment: tuple[tuple[str, str], ...] = ()


def _best(violations: Sequence[_Violation]) -> _Violation:
    """Return the violation with the earliest step, breaking ties stably."""

    return min(violations, key=lambda item: (item.index, item.assignment))


def _first_violation(
    formula: Formula,
    trace: tuple,
    index: int,
    environment: dict[str, str],
    assignment: tuple[tuple[str, str], ...] = (),
) -> _Violation | None:
    """Locate the earliest state that explains why *formula* fails."""

    length = len(trace)

    if isinstance(formula, Atom):
        if _evaluate(formula, trace, index, environment):
            return None
        rendered = _render(formula, environment)
        if index >= length:
            return _Violation(
                index,
                f"atom {rendered!r} cannot hold past the end of the trace",
                assignment,
            )
        return _Violation(
            index,
            f"required atom {rendered!r} is absent at this step",
            assignment,
        )

    if isinstance(formula, Not):
        if _evaluate(formula.body, trace, index, environment):
            return _Violation(
                index,
                f"negated subformula {_render(formula.body, environment)} "
                "holds here",
                assignment,
            )
        return None

    if isinstance(formula, And):
        violations = [
            violation
            for child in (formula.left, formula.right)
            if (violation := _first_violation(
                child, trace, index, environment, assignment
            ))
            is not None
        ]
        return _best(violations) if violations else None

    if isinstance(formula, Or):
        if _evaluate(formula, trace, index, environment):
            return None
        violations = [
            violation
            for child in (formula.left, formula.right)
            if (violation := _first_violation(
                child, trace, index, environment, assignment
            ))
            is not None
        ]
        if not violations:  # defensive: evaluate said false, children must say why
            return _Violation(index, "both disjuncts are false", assignment)
        return _best(violations)

    if isinstance(formula, Implies):
        if not _evaluate(formula.left, trace, index, environment):
            return None
        return _first_violation(
            formula.right, trace, index, environment, assignment
        )

    if isinstance(formula, X):
        if index + 1 >= length:
            return _Violation(
                index,
                "strong X has no successor at the last state",
                assignment,
            )
        return _first_violation(
            formula.body, trace, index + 1, environment, assignment
        )

    if isinstance(formula, WX):
        if index + 1 >= length:
            return None
        return _first_violation(
            formula.body, trace, index + 1, environment, assignment
        )

    if isinstance(formula, G):
        for position in range(index, length):
            if not _evaluate(formula.body, trace, position, environment):
                return _first_violation(
                    formula.body, trace, position, environment, assignment
                )
        return None

    if isinstance(formula, F):
        for position in range(index, length):
            if _evaluate(formula.body, trace, position, environment):
                return None
        last = max(index, length - 1)
        return _Violation(
            last,
            "F subformula "
            f"{_render(formula.body, environment)} never holds in the "
            "remaining trace",
            assignment,
        )

    if isinstance(formula, U):
        for position in range(index, length):
            if _evaluate(formula.right, trace, position, environment):
                return None
            if not _evaluate(formula.left, trace, position, environment):
                return _Violation(
                    position,
                    "left operand of U stopped holding before the right "
                    "operand "
                    f"{_render(formula.right, environment)} was reached",
                    assignment,
                )
        last = max(index, length - 1)
        return _Violation(
            last,
            "right operand "
            f"{_render(formula.right, environment)} of U never holds",
            assignment,
        )

    if isinstance(formula, Forall):
        domains = _quantifier_domains(formula, trace, environment)
        if any(not domains[variable] for variable in formula.variables):
            return None
        violations: list[_Violation] = []
        for assignment_values in _assignments(formula.variables, domains):
            merged = {**environment, **assignment_values}
            if _evaluate(formula.body, trace, index, merged):
                continue
            located = _first_violation(
                formula.body,
                trace,
                index,
                merged,
                assignment + tuple(sorted(assignment_values.items())),
            )
            if located is not None:
                violations.append(located)
        if violations:
            return _best(violations)
        return None

    if isinstance(formula, Exists):
        domains = _quantifier_domains(formula, trace, environment)
        for assignment_values in _assignments(formula.variables, domains):
            merged = {**environment, **assignment_values}
            if _evaluate(formula.body, trace, index, merged):
                return None
        description = ", ".join(
            f"{variable} in {list(domains[variable])!r}"
            for variable in formula.variables
        )
        return _Violation(
            index,
            f"no assignment satisfies the body ({description or 'empty domain'})",
            assignment,
        )

    raise TypeError(f"unsupported formula node: {type(formula).__name__}")


def explain(formula: Formula, trace) -> str:
    """Explain the first violation of *formula* on *trace*.

    Returns a one-line success message when the formula holds.  On failure the
    message names the zero-based trace index, the producer's step number, the
    action and outcome of that step, the step's atomic propositions, the
    quantifier binding (if any) and the structural reason.  The first
    *offending* state is reported: for ``G(booked -> WX G(!available))`` that
    is the step at which ``available`` reappears, not step 0.
    """

    events = _validate_trace(trace)
    _ensure_closed(formula)
    if _evaluate(formula, events, 0, {}):
        return (
            f"LTL property holds on this trace ({len(events)} step(s)): "
            f"{formula}"
        )
    violation = _first_violation(formula, events, 0, {})
    if violation is None:  # pragma: no cover - evaluate and locate must agree
        return (
            "LTL property is false but the first violation could not be "
            f"located: {formula}"
        )

    lines = [f"LTL property violated: {formula}"]
    if not events:
        lines.append("first violation at trace index 0: the trace is empty")
    elif violation.index >= len(events):
        lines.append(
            "first violation after the last step "
            f"(index {violation.index}, trace has {len(events)} step(s))"
        )
    else:
        event = events[violation.index]
        lines.append(
            "first violation at trace index "
            f"{violation.index} (step {event.step}, action={event.action}, "
            f"ok={event.ok})"
        )
        lines.append(f"  props: {sorted(event.props)}")
    if violation.assignment:
        rendered = ", ".join(
            f"{name}={value}" for name, value in violation.assignment
        )
        lines.append(f"  binding: {rendered}")
    lines.append(f"  reason: {violation.reason}")
    return "\n".join(lines)
