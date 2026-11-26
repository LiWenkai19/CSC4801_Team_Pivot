"""Independent in-memory model of the interview-booking lifecycle (P2).

Nothing in this module imports ``app``: every predicted status code, every
expected row and every expected match score is derived from the requirement
text and the published HTTP contract, so the model is free to disagree with the
implementation under test.  A disagreement is the product of this suite.

Requirement clauses encoded here (see ``docs/REQUIREMENTS.md``):

``FP-CAN-3``
    A candidate applies to a job once; a new application is ``Pending``; a
    duplicate is rejected without creating a second row.
``FP-EMP-2``
    Only the owning employer may touch a posting, and a posting that has
    dependent records must not be deletable.
``FP-EMP-3``
    The owning employer sets an application to exactly one of ``Pending``,
    ``Interviewing``, ``Rejected`` or ``Accepted``; nobody else may change it.
``FP-MATCH-1``
    ``score = 100`` when the required-skill set is empty, otherwise
    ``floor(100 * |C & R| / |R|)`` on whitespace-trimmed, lower-cased,
    de-duplicated, non-empty skill names.
``FP-SCHED-1``
    Slots are future 30-minute windows owned by one employer; a booked slot
    cannot be deleted and is never offered as available.
``FP-SCHED-2``
    Booking is allowed if and only if the caller owns the application, the slot
    belongs to the application's employer, the application is ``Interviewing``,
    the slot is in the future and not booked, and the application has no other
    booking.  A booking survives a later status change and keeps its slot
    unavailable.
``FP-SCHED-3``
    Booking conflicts surface as HTTP 409 with the message ``Slot already
    booked``; a failed attempt must not change stored rows.

The model is intentionally small.  It tracks exactly the state that the
requirements constrain: which applications exist and in which status, which
slots exist, and which application is bound to which slot.  Anything the
requirements do not constrain (row ids beyond identity, timestamps, e-mail
addresses) is carried only as far as the suite needs it to address a request.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import uuid

__all__ = [
    "CANDIDATES",
    "EMPLOYERS",
    "JOBS",
    "Application",
    "Candidate",
    "Employer",
    "Job",
    "Prediction",
    "SLOT_LENGTH",
    "Slot",
    "STATUSES",
    "World",
    "match_score",
    "normalize",
]

SLOT_LENGTH = timedelta(minutes=30)

#: The only four statuses FP-EMP-3 allows.
STATUSES = ("Pending", "Interviewing", "Rejected", "Accepted")
PENDING = "Pending"
INTERVIEWING = "Interviewing"

#: Fixed cast of the scenario.  Skill lists carry deliberate noise (padding,
#: mixed case, duplicates) because FP-MATCH-1 defines the normalisation and the
#: applicant list must agree with it.
CANDIDATES: dict[str, dict] = {
    "c1": {"display_name": "Alice", "skills": (" Python ", "SQL", "sql")},
    "c2": {"display_name": "bob", "skills": ("Python",)},
    "c3": {"display_name": "Carol", "skills": ("Rust", "Go")},
}

EMPLOYERS: dict[str, dict] = {
    "e1": {"company_name": "Acme Robotics"},
    "e2": {"company_name": "Borealis Data"},
}

#: One posting per employer.  ``j2`` deliberately requires no skills, which
#: pins the ``|R| = 0`` branch of FP-MATCH-1 to real applicant rows.
JOBS: dict[str, dict] = {
    "j1": {"employer": "e1", "title": "Backend Engineer", "required_skills": ("Python", "SQL")},
    "j2": {"employer": "e2", "title": "Generalist", "required_skills": ()},
}


def normalize(skills) -> set[str]:
    """Return the FP-MATCH-1 skill set: trimmed, lower-cased, non-empty, unique."""

    normalized: set[str] = set()
    for skill in skills:
        cleaned = skill.strip().lower()
        if cleaned:
            normalized.add(cleaned)
    return normalized


def match_score(candidate_skills, required_skills) -> int:
    """Return the FP-MATCH-1 score for one candidate/job pair.

    This is a second implementation written from the requirement formula; it
    never calls the code under test.
    """

    required = normalize(required_skills)
    if not required:
        return 100
    return (100 * len(normalize(candidate_skills) & required)) // len(required)


@dataclass
class Candidate:
    """A candidate account and the raw skill list it registered with."""

    alias: str
    display_name: str
    skills: tuple[str, ...]
    user_id: uuid.UUID | None = None

    @property
    def normalized_skills(self) -> list[str]:
        return sorted(normalize(self.skills))


@dataclass
class Employer:
    """An employer account and its company name."""

    alias: str
    company_name: str
    user_id: uuid.UUID | None = None


@dataclass
class Job:
    """A job posting; ``deleted`` mirrors the soft-delete flag."""

    alias: str
    employer: str
    title: str
    required_skills: tuple[str, ...]
    job_id: uuid.UUID | None = None
    deleted: bool = False


@dataclass
class Application:
    """One candidate's application to one job."""

    alias: str
    candidate: str
    job: str
    status: str = PENDING
    version: int = 1
    application_id: uuid.UUID | None = None
    #: Slot alias this application is bound to, if any (FP-SCHED-2).
    booking: str | None = None
    #: Status recorded at the moment the booking was created (invariant 3).
    status_when_booked: str | None = None


@dataclass
class Slot:
    """An employer-owned 30-minute interview window."""

    alias: str
    employer: str
    starts_at: datetime
    ends_at: datetime
    slot_id: uuid.UUID | None = None
    #: Set when the slot is booked: the booking binds the slot to that job.
    job: str | None = None
    #: Application alias that booked this slot, if any.
    booking: str | None = None
    deleted: bool = False


@dataclass(frozen=True)
class Prediction:
    """What the model expects one HTTP call to return.

    ``detail`` is only set where a requirement fixes the message text
    (FP-SCHED-3 requires the string ``Slot already booked``).
    """

    code: int
    action: str
    detail: str | None = None
    created: str | None = None
    #: Short tag for the branch that produced the prediction; used for coverage
    #: counting in the evidence file, never for assertions.
    reason: str | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.code < 300


@dataclass
class World:
    """The modelled business state of one scenario.

    ``predict_*`` methods decide the expected HTTP status from the requirement
    text and, when the requirement says the call must succeed, apply the effect
    to the model.  The caller compares the prediction with the real response;
    on a mismatch the trace fails, so an optimistic mutation is never silently
    accepted.
    """

    candidates: dict[str, Candidate] = field(default_factory=dict)
    employers: dict[str, Employer] = field(default_factory=dict)
    jobs: dict[str, Job] = field(default_factory=dict)
    applications: dict[str, Application] = field(default_factory=dict)
    slots: dict[str, Slot] = field(default_factory=dict)
    #: First half-hour boundary of the slot grid; always at least a day ahead,
    #: so every modelled slot is "in the future" for the whole run.
    base_time: datetime = field(
        default_factory=lambda: (
            datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
            + timedelta(days=1)
        )
    )
    _application_counter: int = 0
    _slot_counter: int = 0

    def __post_init__(self) -> None:
        for alias, spec in CANDIDATES.items():
            self.candidates[alias] = Candidate(
                alias=alias,
                display_name=spec["display_name"],
                skills=tuple(spec["skills"]),
            )
        for alias, spec in EMPLOYERS.items():
            self.employers[alias] = Employer(
                alias=alias, company_name=spec["company_name"]
            )
        for alias, spec in JOBS.items():
            self.jobs[alias] = Job(
                alias=alias,
                employer=spec["employer"],
                title=spec["title"],
                required_skills=tuple(spec["required_skills"]),
            )

    # -- identity -----------------------------------------------------

    def bind_candidate(self, alias: str, user_id: uuid.UUID) -> None:
        self.candidates[alias].user_id = user_id

    def bind_employer(self, alias: str, user_id: uuid.UUID) -> None:
        self.employers[alias].user_id = user_id

    def bind_job(self, alias: str, job_id: uuid.UUID) -> None:
        self.jobs[alias].job_id = job_id

    def bind_application(self, alias: str, application_id: uuid.UUID) -> None:
        self.applications[alias].application_id = application_id

    def bind_slot(self, alias: str, slot_id: uuid.UUID) -> None:
        self.slots[alias].slot_id = slot_id

    def slot_start(self, offset_days: int, half_hour: int) -> datetime:
        """Return the modelled start time of the slot grid cell."""

        return self.base_time + timedelta(days=offset_days - 1, minutes=30 * half_hour)

    # -- scoped queries -----------------------------------------------

    def application_for(self, candidate: str, job: str) -> Application | None:
        for application in self.applications.values():
            if application.candidate == candidate and application.job == job:
                return application
        return None

    def applications_of_job(self, job: str) -> list[Application]:
        return [
            application
            for application in self.applications.values()
            if application.job == job
        ]

    def employer_of_application(self, application: str) -> str:
        return self.jobs[self.applications[application].job].employer

    def other_employer(self, employer: str) -> str:
        others = [alias for alias in self.employers if alias != employer]
        assert len(others) == 1, "scenario has exactly two employers"
        return others[0]

    def eligible_applications(self) -> list[Application]:
        """Applications whose available-slot list is defined by FP-SCHED-2."""

        return [
            application
            for application in self.applications.values()
            if application.status == INTERVIEWING and application.booking is None
        ]

    def available_slots(self, application: str) -> list[str]:
        """Return the slot aliases FP-SCHED-1/2 say this application may book."""

        record = self.applications[application]
        job = self.jobs[record.job]
        available = []
        for slot in self.slots.values():
            if slot.deleted or slot.booking is not None:
                continue
            if slot.employer != job.employer:
                continue
            # A slot bound to another posting is not reusable by this one.
            if slot.job is not None and slot.job != job.alias:
                continue
            available.append(slot.alias)
        available.sort(key=lambda alias: (self.slots[alias].starts_at, alias))
        return available

    def visible_slots(self) -> set[str]:
        """Slots at least one eligible application can currently see."""

        visible: set[str] = set()
        for application in self.eligible_applications():
            visible.update(self.available_slots(application.alias))
        return visible

    # -- independent oracle for FP-MATCH-1 / FP-EMP-3 -----------------

    def applicants_oracle(self, job: str) -> list[dict]:
        """Expected ``GET /employer/jobs/{id}/applications`` payload, row by row.

        The ordering rule comes from FP-MATCH-1: descending score, then
        case-insensitive display name, then the stable candidate id.
        """

        posting = self.jobs[job]
        rows = []
        for application in self.applications_of_job(job):
            candidate = self.candidates[application.candidate]
            rows.append(
                {
                    "application": application.alias,
                    "application_id": application.application_id,
                    "candidate": candidate.alias,
                    "candidate_id": candidate.user_id,
                    "display_name": candidate.display_name,
                    "skills": candidate.normalized_skills,
                    "match_score": match_score(
                        candidate.skills, posting.required_skills
                    ),
                    "status": application.status,
                    "version": application.version,
                    "booking_slot": application.booking,
                }
            )
        rows.sort(
            key=lambda row: (
                -row["match_score"],
                row["display_name"].lower(),
                str(row["candidate_id"]),
            )
        )
        return rows

    # -- predictions ---------------------------------------------------

    def predict_apply(self, candidate: str, job: str) -> Prediction:
        """FP-CAN-3: one application per candidate/job pair, filed as Pending."""

        posting = self.jobs[job]
        if posting.deleted:
            return Prediction(404, "apply", reason="job_deleted")
        if self.application_for(candidate, job) is not None:
            return Prediction(409, "apply", reason="duplicate")
        self._application_counter += 1
        alias = f"a{self._application_counter}"
        self.applications[alias] = Application(
            alias=alias, candidate=candidate, job=job
        )
        return Prediction(201, "apply", created=alias, reason="created")

    def predict_set_status(self, application: str, status: str) -> Prediction:
        """FP-EMP-3: the owning employer sets one of the four statuses."""

        record = self.applications[application]
        if self.jobs[record.job].deleted:
            return Prediction(404, "set_status", reason="job_deleted")
        record.status = status
        record.version += 1
        return Prediction(200, "set_status", reason="updated")

    def predict_set_status_as_outsider(
        self, application: str, actor: str, actor_role: str
    ) -> Prediction:
        """FP-EMP-3/FP-SEC-1: anyone but the owning employer is refused."""

        record = self.applications[application]
        if self.jobs[record.job].deleted:
            return Prediction(404, "set_status_wrong_owner", reason="job_deleted")
        if actor_role == "candidate":
            # Role guard rejects the caller before the request body is read.
            return Prediction(403, "set_status_wrong_owner", reason="candidate")
        assert actor != self.employer_of_application(application)
        return Prediction(403, "set_status_wrong_owner", reason="other_employer")

    def predict_create_slot(self, employer: str, starts_at: datetime) -> Prediction:
        """FP-SCHED-1: future 30-minute slots that do not overlap."""

        ends_at = starts_at + SLOT_LENGTH
        for slot in self.slots.values():
            if slot.deleted or slot.employer != employer:
                continue
            if slot.starts_at < ends_at and slot.ends_at > starts_at:
                return Prediction(409, "create_slot", reason="overlap")
        self._slot_counter += 1
        alias = f"s{self._slot_counter}"
        self.slots[alias] = Slot(
            alias=alias,
            employer=employer,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        return Prediction(201, "create_slot", created=alias, reason="created")

    def predict_book(self, application: str, slot: str) -> Prediction:
        """FP-SCHED-2: the five eligibility conditions, in contract order."""

        record = self.applications[application]
        posting = self.jobs[record.job]
        window = self.slots[slot]
        if record.status != INTERVIEWING:
            return Prediction(409, "book", reason="not_interviewing")
        if record.booking is not None:
            return Prediction(409, "book", reason="application_booked")
        if window.deleted:
            return Prediction(404, "book", reason="slot_gone")
        if window.employer != posting.employer:
            return Prediction(403, "book", reason="other_employer")
        if window.booking is not None:
            # FP-SCHED-3 fixes this message for the "already taken" conflict.
            return Prediction(
                409,
                "book",
                detail="Slot already booked",
                reason="slot_booked",
            )
        record.booking = window.alias
        record.status_when_booked = record.status
        window.booking = record.alias
        window.job = posting.alias
        return Prediction(201, "book", reason="created")

    def predict_book_as_outsider(self, application: str, actor: str) -> Prediction:
        """FP-SCHED-2/FP-SEC-1: a candidate may only book their own application."""

        record = self.applications[application]
        assert actor != record.candidate, "outsider must differ from the owner"
        return Prediction(403, "book_foreign", reason="not_owner")

    def predict_delete_slot(self, slot: str) -> Prediction:
        """FP-SCHED-1: booked slots cannot be deleted; deletion is permanent."""

        window = self.slots[slot]
        if window.deleted:
            return Prediction(404, "delete_slot", reason="gone")
        if window.booking is not None:
            return Prediction(409, "delete_slot", reason="booked")
        window.deleted = True
        return Prediction(204, "delete_slot", reason="deleted")

    def predict_delete_job(self, job: str) -> Prediction:
        """FP-EMP-2: a posting with dependent records stays; otherwise it goes."""

        posting = self.jobs[job]
        if posting.deleted:
            return Prediction(404, "delete_job", reason="gone")
        if self.applications_of_job(job):
            return Prediction(409, "delete_job", reason="has_applications")
        if any(
            slot.job == job and not slot.deleted for slot in self.slots.values()
        ):
            return Prediction(409, "delete_job", reason="has_slots")
        posting.deleted = True
        return Prediction(204, "delete_job", reason="deleted")
