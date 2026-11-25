"""Trace event format shared by the stateful (P2) and LTL (P3) suites.

One JSON file holds one trace: a list of events in step order.  ``props`` is the
set of atomic propositions that hold *after* the step, split into a sorted JSON
array so the artefact is byte-for-byte reproducible for a fixed seed.

The shape is intentionally small and stable::

    Event(step=1, action="apply", ok=True,
          props=frozenset({"applied:a1", "status:a1:Pending"}))

Naming rules for atomic propositions are documented in
``tests/advanced/README.md``.  This module validates types but does not know
about the application; it must stay usable by both the producer (P2) and the
consumer (P3).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

__all__ = [
    "KNOWN_ACTIONS",
    "Event",
    "read_trace",
    "read_traces",
    "write_trace",
]

# Actions the stateful suite emits.  Import is forbidden from other modules so
# later modes can add actions without editing this shared file; these names are
# documented for readers and for the P3 alphabet.
KNOWN_ACTIONS = (
    "apply",
    "set_status",
    "create_slot",
    "book",
    "delete_slot",
    "observe",
)


@dataclass(frozen=True)
class Event:
    """One step of a trace.

    ``step`` is a zero-based or one-based index chosen by the producer; it only
    has to be a non-negative integer.  ``props`` holds atom names that are true
    after the action's effect.
    """

    step: int
    action: str
    ok: bool
    props: frozenset[str]

    def to_json(self) -> dict:
        """Return the JSON-compatible representation (props sorted)."""

        _validate(self)
        return {
            "step": self.step,
            "action": self.action,
            "ok": self.ok,
            "props": sorted(self.props),
        }

    @classmethod
    def from_json(cls, value: object) -> "Event":
        """Build an Event from an untrusted JSON value."""

        if not isinstance(value, dict):
            raise ValueError("trace event must be a JSON object")
        props = value.get("props")
        if not isinstance(props, list) or any(
            not isinstance(item, str) for item in props
        ):
            raise ValueError("trace event 'props' must be a list of strings")
        if len(props) != len(set(props)):
            raise ValueError("trace event 'props' contains duplicate atoms")
        event = cls(
            step=value.get("step"),  # type: ignore[arg-type]
            action=value.get("action"),  # type: ignore[arg-type]
            ok=value.get("ok"),  # type: ignore[arg-type]
            props=frozenset(props),
        )
        _validate(event)
        return event


def _validate(event: Event) -> None:
    if not isinstance(event.step, int) or isinstance(event.step, bool):
        raise ValueError("trace event 'step' must be an integer")
    if event.step < 0:
        raise ValueError("trace event 'step' must be >= 0")
    if not isinstance(event.action, str) or not event.action:
        raise ValueError("trace event 'action' must be a non-empty string")
    if not isinstance(event.ok, bool):
        raise ValueError("trace event 'ok' must be a boolean")
    if not isinstance(event.props, frozenset):
        raise ValueError("trace event 'props' must be a frozenset")
    for atom in event.props:
        if not isinstance(atom, str) or not atom:
            raise ValueError("trace props must be non-empty strings")


def write_trace(path: str | Path, events) -> Path:
    """Write *events* to *path* as one JSON trace and return the path.

    Parent directories are created.  The file ends with a newline and uses
    ``indent=2`` so diffs of committed oracle traces stay readable.
    """

    target = Path(path)
    payload = [event.to_json() for event in events]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target


def read_trace(path: str | Path) -> list[Event]:
    """Read one trace file."""

    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source}: invalid JSON: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError(f"{source}: a trace file must contain a JSON list")
    events = []
    for index, value in enumerate(payload):
        try:
            events.append(Event.from_json(value))
        except ValueError as exc:
            raise ValueError(f"{source}: event {index}: {exc}") from exc
    return events


def read_traces(directory: str | Path) -> list[list[Event]]:
    """Read every ``*.json`` trace in *directory*, ordered by file name."""

    folder = Path(directory)
    if not folder.is_dir():
        raise FileNotFoundError(f"trace directory does not exist: {folder}")
    return [read_trace(path) for path in sorted(folder.glob("*.json"))]
