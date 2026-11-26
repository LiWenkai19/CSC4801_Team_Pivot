"""Plumbing for the P2 state machine: real HTTP calls, SQL snapshots, artefacts.

This module deliberately contains no business rules.  It turns an alias from
:mod:`stateful.model` into a request against the real FastAPI application, reads
the database back through the test engine, and writes the trace artefacts that
P3 consumes.

Identifier aliases (``c1``, ``e1``, ``j1``, ``a1``, ``s1``) stay inside the
suite; UUIDs only travel between the harness and the model binding helpers.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

from support.traces import Event, write_trace

__all__ = [
    "ARTEFACT_NAMES",
    "Harness",
    "Recorder",
    "artefact_dir",
    "body_json",
]

#: Application tables snapshotted by every step; order is stable for evidence.
ARTEFACT_NAMES = (
    "user",
    "user_session",
    "candidate_profile",
    "candidate_skill",
    "employer_profile",
    "job",
    "job_skill",
    "application",
    "interview_slot",
    "booking",
)

_COUNT_SQL = "SELECT " + ", ".join(
    f'(SELECT count(*) FROM "{name}") AS "{name}"' for name in ARTEFACT_NAMES
)


def artefact_dir(subdirectory: str) -> Path:
    """Return ``$ADVANCED_OUT/<mode>/<subdirectory>`` (outside the checkout).

    Mirrors ``conftest.evidence``: a direct pytest invocation without
    ``ADVANCED_OUT`` falls back to a directory under the system temporary
    directory, so artefacts never land inside the repository.
    """

    base = os.environ.get("ADVANCED_OUT")
    mode = os.environ.get("ADVANCED_MODE", "adhoc")
    if base:
        folder = Path(base) / mode
    else:
        folder = Path(tempfile.gettempdir()) / "csc4801-advanced-evidence" / mode
    return folder / subdirectory


class Recorder:
    """Collects trace files and the aggregated numbers for ``evidence``."""

    def __init__(self, traces: Path, evidence) -> None:
        self.traces = traces
        self.traces.mkdir(parents=True, exist_ok=True)
        self._evidence = evidence
        self._next_index = 1
        self.examples = 0
        self.steps = 0
        self.operations: dict[str, int] = {}
        self.outcomes: dict[str, int] = {}
        self.action_outcomes: dict[str, int] = {}
        self.reasons: dict[str, int] = {}
        self.distinct_traces = 0
        self._digests: set[str] = set()

    def record(self, events: list[Event]) -> None:
        """Persist one example's trace; examples without steps are skipped.

        Hypothesis occasionally replays the same generated example, so the
        number of files can exceed the number of distinct traces; both numbers
        are reported.
        """

        self.examples += 1
        self.steps += len(events)
        for event in events:
            self.operations[event.action] = self.operations.get(event.action, 0) + 1
        if not events:
            return
        digest = hashlib.sha256(
            json.dumps(
                [event.to_json() for event in events], sort_keys=True
            ).encode("utf-8")
        ).hexdigest()
        if digest not in self._digests:
            self._digests.add(digest)
            self.distinct_traces += 1
        name = f"{self._next_index:04d}.json"
        write_trace(self.traces / name, events)
        self._next_index += 1

    def count_reason(self, reason: str) -> None:
        """Count an auxiliary fact, e.g. the status a transition moved to."""

        self.reasons[reason] = self.reasons.get(reason, 0) + 1

    def count_outcome(self, action: str, code: int, reason: str | None = None) -> None:
        """Count ``(action, status)`` pairs, e.g. ``book -> 201``.

        ``reason`` is the model branch that produced the prediction; it is
        recorded separately so the evidence shows which conflict paths ran.
        """

        key = f"{action}->{code}"
        self.action_outcomes[key] = self.action_outcomes.get(key, 0) + 1
        if reason is not None:
            key = f"{action}:{reason}"
            self.reasons[key] = self.reasons.get(key, 0) + 1
        key = f"http_{code}"
        self.outcomes[key] = self.outcomes.get(key, 0) + 1

    def summary(self) -> dict:
        return {
            "examples": self.examples,
            "steps": self.steps,
            "traces": self._next_index - 1,
            "distinct_traces": self.distinct_traces,
            "trace_dir": str(self.traces),
            "operations": dict(sorted(self.operations.items())),
            "action_outcomes": dict(sorted(self.action_outcomes.items())),
            "reasons": dict(sorted(self.reasons.items())),
            "http_outcomes": dict(sorted(self.outcomes.items())),
        }

    def write_summary(self) -> dict:
        payload = self.summary()
        self._evidence("summary", payload)
        return payload


class Harness:
    """Real-HTTP driver plus read-only SQL snapshots of the test database."""

    def __init__(self, client, engine, account, truncate) -> None:
        self.client = client
        self.engine = engine
        self.account = account
        self.truncate = truncate
        self.actors: dict[str, dict] = {}

    # -- scenario construction ----------------------------------------

    def new_world(self):
        """Truncate every application table and rebuild the fixed cast."""

        from stateful.model import EMPLOYERS, JOBS, World

        self.truncate()
        self.actors = {}
        world = World()

        for alias in world.candidates:
            spec = world.candidates[alias]
            headers, user_id = self.account(
                "candidate", skills=list(spec.skills), name=spec.display_name
            )
            self.actors[alias] = headers
            world.bind_candidate(alias, user_id)

        for alias in world.employers:
            spec = world.employers[alias]
            headers, user_id = self.account("employer", name=spec.company_name)
            self.actors[alias] = headers
            world.bind_employer(alias, user_id)

        for alias in world.jobs:
            posting = world.jobs[alias]
            response = self.client.post(
                "/employer/jobs",
                headers=self.actors[posting.employer],
                json={
                    "title": posting.title,
                    "description": f"Posting for {posting.title}",
                    "required_skills": list(posting.required_skills),
                },
            )
            assert response.status_code == 201, (
                f"scenario setup could not create job {alias}: {response.text}"
            )
            world.bind_job(alias, _uuid(response.json()["id"]))

        return world

    # -- HTTP operations ----------------------------------------------

    def apply(self, candidate: str, job_id) -> object:
        return self.client.post(
            f"/candidate/jobs/{job_id}/applications",
            headers=self.actors[candidate],
            json={},
        )

    def book(self, candidate: str, application_id, slot_id) -> object:
        return self.client.post(
            f"/candidate/applications/{application_id}/booking",
            headers=self.actors[candidate],
            json={"slot_id": str(slot_id)},
        )

    def available_slots(self, candidate: str, application_id) -> object:
        return self.client.get(
            f"/candidate/applications/{application_id}/slots",
            headers=self.actors[candidate],
        )

    def set_status(self, actor: str, application_id, version: int, status: str) -> object:
        return self.client.patch(
            f"/employer/applications/{application_id}/status",
            headers=self.actors[actor],
            json={"version": version, "status": status},
        )

    def create_slot(self, employer: str, starts_at) -> object:
        return self.client.post(
            "/employer/interview-slots",
            headers=self.actors[employer],
            json={"starts_at": starts_at.isoformat()},
        )

    def delete_slot(self, employer: str, slot_id) -> object:
        return self.client.delete(
            f"/employer/interview-slots/{slot_id}",
            headers=self.actors[employer],
        )

    def delete_job(self, employer: str, job_id) -> object:
        return self.client.delete(
            f"/employer/jobs/{job_id}", headers=self.actors[employer]
        )

    def applicants(self, employer: str, job_id) -> object:
        return self.client.get(
            f"/employer/jobs/{job_id}/applications",
            headers=self.actors[employer],
        )

    # -- database snapshots -------------------------------------------

    def counts(self) -> dict[str, int]:
        """Row count of every application table, in one statement."""

        from sqlalchemy import text

        with self.engine.connect() as connection:
            row = connection.execute(text(_COUNT_SQL)).mappings().one()
        return {name: int(row[name]) for name in ARTEFACT_NAMES}

    def snapshot(self) -> dict:
        """Read every persisted fact the invariants need over one connection.

        One pooled connection for the whole snapshot keeps the per-step cost
        down; the queries are still plain, fully parameter-free SQL.
        """

        from sqlalchemy import text

        with self.engine.connect() as connection:
            counts = connection.execute(text(_COUNT_SQL)).mappings().one()
            applications = connection.execute(
                text(
                    "SELECT id, candidate_id, job_id, status, version"
                    " FROM application"
                )
            ).mappings().all()
            slots = connection.execute(
                text("SELECT id, employer_id, job_id FROM interview_slot")
            ).mappings().all()
            bookings = connection.execute(
                text("SELECT application_id, slot_id FROM booking")
            ).all()
            jobs = connection.execute(
                text("SELECT id, is_deleted FROM job")
            ).mappings().all()
        return {
            "counts": {name: int(counts[name]) for name in ARTEFACT_NAMES},
            "applications": {
                _uuid(row["id"]): {
                    "status": str(row["status"]),
                    "version": int(row["version"]),
                    "candidate_id": _uuid(row["candidate_id"]),
                    "job_id": _uuid(row["job_id"]),
                }
                for row in applications
            },
            "slots": {
                _uuid(row["id"]): {
                    "employer_id": _uuid(row["employer_id"]),
                    "job_id": _uuid(row["job_id"]) if row["job_id"] else None,
                }
                for row in slots
            },
            "bookings": [(_uuid(row[0]), _uuid(row[1])) for row in bookings],
            "jobs": {_uuid(row["id"]): bool(row["is_deleted"]) for row in jobs},
        }


def _uuid(value) -> object:
    """Return *value* as ``uuid.UUID`` (drivers may hand back ``str``)."""

    import uuid

    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def body_json(response) -> dict:
    """Best-effort JSON body of a response without raising on empty bodies."""

    try:
        return response.json()
    except (json.JSONDecodeError, ValueError):
        return {}
