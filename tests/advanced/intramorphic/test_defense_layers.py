"""Intramorphic tests: which defence layer actually enforces each rule?

Every test runs the original program first (the control) and then one
*controlled program variant* installed with ``monkeypatch``.  The production
source tree is never edited; pytest restores every attribute at teardown.

The five rules and their variants are:

* I1: slot uniqueness -- disable the application-layer "slot already booked"
  precheck; the database unique constraint must still reject the request;
* I2: concurrent single winner -- remove every row lock; the database unique
  constraint must still produce exactly one winner, with a barrier proving that
  the two requests really did overlap inside ``book``;
* I3: duplicate application -- disable the application-layer duplicate
  precheck; the database unique constraint must still reject the request;
* I4: matching is insensitive to the order produced by ``normalize_skills``;
* I5: deleting a job with dependents -- disable the service dependency probes
  and record whether the database blocks the soft delete.

I1 and I3 have extra self-checks: the relevant unique constraint is
deliberately removed from the throwaway database, the same HTTP request is
repeated, and the invariant oracle must go red when a duplicate row exists.
The constraint is restored in a ``finally`` block.  (A Python-level ``commit``
wrapper cannot make PostgreSQL store a duplicate; the physical constraint has
to be absent, which is what the self-check removes.)
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
import uuid

import pytest
from sqlmodel import Session

import variants as v

DEFENSE_RESULTS: dict[str, dict] = {}


def record(evidence, rule_id: str, payload: dict) -> None:
    """Keep the module-wide rule table and write the combined evidence file."""

    DEFENSE_RESULTS[rule_id] = payload
    evidence(
        "defense_layers",
        {
            "seed": v.SEED,
            "rules": dict(sorted(DEFENSE_RESULTS.items())),
        },
    )


@pytest.fixture
def fast_registration(monkeypatch):
    """Cheap KDF for the small synthetic fixtures."""

    v.install_fast_registration(monkeypatch)


def _booking_url(application_id) -> str:
    return f"/candidate/applications/{application_id}/booking"


def _interviewing_pair(client, employer, job_id, candidates):
    """Create one interview-ready application per candidate."""

    applications = []
    for headers in candidates:
        application = v.apply_to_job(client, headers, job_id)
        v.set_status(
            client,
            employer,
            application["application_id"],
            application["version"],
            "Interviewing",
        )
        applications.append(application)
    return applications


def test_i1_slot_precheck_removed_unique_constraint_still_rejects_second_booking(
    client,
    account,
    engine,
    clean_tables,
    evidence,
    monkeypatch,
    fast_registration,
):
    employer, _ = account("employer", name="I1 Employer")
    job = v.create_job(client, employer, "I1 Role", ["python"])
    first, _ = account("candidate", skills=["Python"], name="I1 First")
    second, _ = account("candidate", skills=["Python"], name="I1 Second")
    first_application, second_application = _interviewing_pair(
        client, employer, job["id"], [first, second]
    )
    slot = v.create_slot(client, employer, v.future_at(days=4, hour=9))
    first_booking = client.post(
        _booking_url(first_application["application_id"]),
        headers=first,
        json={"slot_id": slot["id"]},
    )
    v.expect(first_booking, 201, "first booking")
    assert v.count_rows(engine, "booking") == 1

    # Original control: the application-layer precheck rejects the second
    # candidate.  No INSERT is attempted, so no IntegrityError is recorded.
    control = client.post(
        _booking_url(second_application["application_id"]),
        headers=second,
        json={"slot_id": slot["id"]},
    )
    assert control.status_code == 409
    assert control.json()["detail"] == "Slot already booked"
    assert v.count_rows(engine, "booking") == 1

    precheck = v.install_skip_first_slot_precheck(monkeypatch)
    commits = v.install_commit_recorder(monkeypatch)
    variant = client.post(
        _booking_url(second_application["application_id"]),
        headers=second,
        json={"slot_id": slot["id"]},
    )
    body = v.expect(variant, 409, "variant second booking")
    assert body["detail"] == "Slot already booked"
    assert precheck["skipped"] == 1, "the application-layer precheck was not bypassed"
    assert len(commits) == 1, "the database constraint did not reject the INSERT"
    assert commits[0]["constraint"] == "uq_booking_slot"
    assert v.count_rows(engine, "booking") == 1
    v.assert_single_booking(engine, slot["id"])

    record(
        evidence,
        "I1",
        {
            "rule": "a slot can be booked only once (FP-SCHED-3)",
            "layers": {
                "application_precheck": "candidate.service.book selects Booking by slot_id",
                "row_lock": "SELECT InterviewSlot ... FOR UPDATE",
                "database_constraint": "unique constraint uq_booking_slot",
            },
            "original": {
                "status": control.status_code,
                "detail": control.json()["detail"],
                "integrity_errors": 0,
            },
            "variant": {
                "disabled_layer": "application_precheck",
                "status": variant.status_code,
                "detail": body["detail"],
                "precheck_bypassed": precheck["skipped"],
                "integrity_events": commits,
            },
            "booking_rows": v.count_rows(engine, "booking"),
            "slot_booking_rows": len(v.booking_rows_for_slot(engine, slot["id"])),
            "conclusion": (
                "database unique constraint is a sufficient backstop; the "
                "application precheck is not the only layer"
            ),
        },
    )


def test_i1_selfcheck_missing_database_constraint_is_detected(
    client,
    account,
    engine,
    clean_tables,
    evidence,
    monkeypatch,
    fast_registration,
):
    employer, _ = account("employer", name="I1 Selfcheck Employer")
    job = v.create_job(client, employer, "I1 Selfcheck Role", ["python"])
    first, _ = account("candidate", skills=["Python"], name="I1 Selfcheck First")
    second, _ = account("candidate", skills=["Python"], name="I1 Selfcheck Second")
    first_application, second_application = _interviewing_pair(
        client, employer, job["id"], [first, second]
    )
    slot = v.create_slot(client, employer, v.future_at(days=4, hour=10))
    v.expect(
        client.post(
            _booking_url(first_application["application_id"]),
            headers=first,
            json={"slot_id": slot["id"]},
        ),
        201,
        "selfcheck first booking",
    )

    v.install_skip_first_slot_precheck(monkeypatch)
    dropped = False
    detected = False
    rows_before_restore = None
    try:
        v.drop_booking_slot_unique_constraint(engine)
        dropped = True
        response = client.post(
            _booking_url(second_application["application_id"]),
            headers=second,
            json={"slot_id": slot["id"]},
        )
        body = v.expect(response, 201, "selfcheck second booking")
        assert body["slot_id"] == slot["id"]
        rows_before_restore = v.booking_rows_for_slot(engine, slot["id"])
        assert len(rows_before_restore) == 2, (
            "without the database constraint the second booking should create "
            "a second row"
        )
        with pytest.raises(AssertionError, match="booking rows"):
            v.assert_single_booking(engine, slot["id"])
        detected = True
    finally:
        if dropped:
            v.restore_booking_slot_unique_constraint(engine, slot["id"])

    restored_rows = v.booking_rows_for_slot(engine, slot["id"])
    assert len(restored_rows) == 1
    v.assert_single_booking(engine, slot["id"])
    assert detected, "the invariant oracle did not detect the missing constraint"

    record(
        evidence,
        "I1_selfcheck",
        {
            "purpose": (
                "prove the I1 oracle is not vacuous: remove the database "
                "constraint, let the same HTTP request create two rows, and "
                "require assert_single_booking to fail"
            ),
            "constraint_removed": "uq_booking_slot",
            "second_booking_status": 201,
            "rows_with_constraint_removed": len(rows_before_restore or []),
            "oracle_raised": detected,
            "rows_after_restore": len(restored_rows),
            "conclusion": "the slot-booking oracle detects the missing layer",
        },
    )


def test_i2_row_lock_removed_unique_constraint_still_has_one_winner(
    client,
    account,
    engine,
    clean_tables,
    evidence,
    monkeypatch,
    fast_registration,
):
    employer, _ = account("employer", name="I2 Employer")
    job = v.create_job(client, employer, "I2 Role", ["python"])
    base = v.future_at(days=5, hour=8)

    from app.candidate import service as candidate_service
    from app.main import app
    from fastapi.testclient import TestClient

    # Original control: the real service with its row locks.  One 201, one 409,
    # one persisted booking.  This is the baseline the variant is compared with.
    control_candidates = [
        account("candidate", skills=["Python"], name="I2 Control A")[0],
        account("candidate", skills=["Python"], name="I2 Control B")[0],
    ]
    control_applications = _interviewing_pair(
        client, employer, job["id"], control_candidates
    )
    control_slot = v.create_slot(client, employer, base)
    control_barrier = Barrier(2)

    def control_reserve(headers, application_id):
        with TestClient(app) as local_client:
            control_barrier.wait(timeout=30)
            return local_client.post(
                _booking_url(application_id),
                headers=headers,
                json={"slot_id": control_slot["id"]},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        control_futures = [
            pool.submit(
                control_reserve,
                control_candidates[index],
                control_applications[index]["application_id"],
            )
            for index in range(2)
        ]
        control_responses = [future.result(timeout=60) for future in control_futures]
    control_statuses = sorted(response.status_code for response in control_responses)
    assert control_statuses == [201, 409], (
        f"the original program must produce exactly one winner; got {control_statuses}"
    )
    control_loser = next(
        response for response in control_responses if response.status_code == 409
    )
    assert control_loser.json()["detail"] == "Slot already booked"
    v.assert_single_booking(engine, control_slot["id"])
    assert v.count_rows(engine, "booking") == 1

    original_book = candidate_service.book
    timeline = v.BookingTimeline()
    timeline.reset()
    precheck_gate = v.PrecheckGate()
    precheck_gate.reset()

    monkeypatch.setattr(candidate_service, "book", timeline.wrap(original_book))
    locks = v.install_no_row_locks(monkeypatch)
    commits = v.install_commit_recorder(monkeypatch)
    gate_state = v.install_slot_precheck_gate(monkeypatch, precheck_gate)

    rounds = []
    for round_index in range(5):
        first, _ = account(
            "candidate",
            skills=["Python"],
            name=f"I2 Candidate A{round_index}",
        )
        second, _ = account(
            "candidate",
            skills=["Python"],
            name=f"I2 Candidate B{round_index}",
        )
        applications = _interviewing_pair(client, employer, job["id"], [first, second])
        slot = v.create_slot(
            client,
            employer,
            base + timedelta(minutes=45 * (round_index + 1)),
        )

        timeline.reset()
        precheck_gate.reset()
        commits_before = len(commits)
        gated_before = gate_state["gated"]

        def reserve(headers, application_id):
            with TestClient(app) as local_client:
                return local_client.post(
                    _booking_url(application_id),
                    headers=headers,
                    json={"slot_id": slot["id"]},
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(
                reserve, first, applications[0]["application_id"]
            )
            second_future = pool.submit(
                reserve, second, applications[1]["application_id"]
            )
            responses = [
                first_future.result(timeout=60),
                second_future.result(timeout=60),
            ]

        statuses = sorted(response.status_code for response in responses)
        assert statuses == [201, 409], (
            f"round {round_index}: expected exactly one 201 and one 409, got {statuses}"
        )
        loser = next(response for response in responses if response.status_code == 409)
        assert loser.json()["detail"] == "Slot already booked"

        assert gate_state["gated"] - gated_before == 2, (
            f"round {round_index}: both requests must pass the slot precheck"
        )
        assert len(precheck_gate.observations) == 2
        assert all(
            observation["is_none"] for observation in precheck_gate.observations
        ), (
            f"round {round_index}: both requests must observe the slot as free "
            "before either inserts"
        )

        entries = timeline.entries
        exits = timeline.exits
        assert len(entries) == len(exits) == 2, (
            f"round {round_index}: expected two book intervals"
        )
        sessions_distinct = entries[0]["session"] != entries[1]["session"]
        assert sessions_distinct, (
            f"round {round_index}: the two requests shared one Session"
        )
        overlap = max(entry["at"] for entry in entries) < min(
            exit_["at"] for exit_ in exits
        )
        assert overlap, f"round {round_index}: the two book calls did not overlap"
        assert entries[0]["thread_id"] != entries[1]["thread_id"], (
            f"round {round_index}: both requests ran on the same thread"
        )
        threads_distinct = True

        new_commits = commits[commits_before:]
        assert len(new_commits) == 1, (
            f"round {round_index}: expected exactly one IntegrityError from "
            f"the unique constraint, got {new_commits!r}"
        )
        assert new_commits[0]["constraint"] == "uq_booking_slot"
        v.assert_single_booking(engine, slot["id"])
        assert v.count_rows(engine, "booking") == round_index + 2

        rounds.append(
            {
                "round": round_index,
                "statuses": statuses,
                "loser_detail": loser.json()["detail"],
                "sessions_distinct": sessions_distinct,
                "threads_distinct": threads_distinct,
                "book_intervals_overlap": overlap,
                "entries": [dict(entry) for entry in entries],
                "exits": [dict(exit_) for exit_ in exits],
                "precheck_observations": [
                    dict(observation) for observation in precheck_gate.observations
                ],
                "integrity_event": new_commits[0],
                "slot_booking_rows": len(v.booking_rows_for_slot(engine, slot["id"])),
            }
        )

    assert locks["calls"] >= 20, (
        "the row-lock variant did not intercept the expected SELECT ... FOR "
        "UPDATE calls"
    )
    assert all(len(round_["statuses"]) == 2 for round_ in rounds)
    record(
        evidence,
        "I2",
        {
            "rule": (
                "two concurrent bookings of one slot have exactly one winner "
                "(FP-SCHED-3)"
            ),
            "layers": {
                "application_precheck": "slot availability query in book",
                "row_lock": "SELECT ... FOR UPDATE on application and slot",
                "database_constraint": "unique constraint uq_booking_slot",
            },
            "disabled_layer": "row_lock (Select.with_for_update is a no-op)",
            "row_lock_calls_intercepted": locks["calls"],
            "original_control": {
                "statuses": control_statuses,
                "loser_detail": control_loser.json()["detail"],
                "slot_booking_rows": len(
                    v.booking_rows_for_slot(engine, control_slot["id"])
                ),
                "total_booking_rows": 1,
            },
            "rounds": rounds,
            "round_count": len(rounds),
            "all_rounds_consistent": all(
                round_["statuses"] == [201, 409] for round_ in rounds
            ),
            "conclusion": (
                "the database unique constraint alone still produces exactly "
                "one winner; the row locks are not the only line of defence"
            ),
        },
    )


def test_i3_application_precheck_removed_unique_constraint_still_rejects_duplicate(
    client,
    account,
    engine,
    clean_tables,
    evidence,
    monkeypatch,
    fast_registration,
):
    employer, _ = account("employer", name="I3 Employer")
    job = v.create_job(client, employer, "I3 Role", ["python"])
    candidate, candidate_id = account(
        "candidate", skills=["Python"], name="I3 Candidate"
    )
    v.apply_to_job(client, candidate, job["id"])

    control = client.post(
        f"/candidate/jobs/{job['id']}/applications",
        headers=candidate,
        json={},
    )
    assert control.status_code == 409
    assert control.json()["detail"] == "Already applied"
    assert v.application_count_for_pair(engine, candidate_id, job["id"]) == 1

    precheck = v.install_skip_first_application_precheck(monkeypatch)
    commits = v.install_commit_recorder(monkeypatch)
    variant = client.post(
        f"/candidate/jobs/{job['id']}/applications",
        headers=candidate,
        json={},
    )
    body = v.expect(variant, 409, "variant duplicate application")
    assert body["detail"] == "Already applied"
    assert precheck["skipped"] == 1, "the application-layer precheck was not bypassed"
    assert len(commits) == 1, "the database constraint did not reject the INSERT"
    assert commits[0]["constraint"] == "uq_application_candidate_job"
    assert v.application_count_for_pair(engine, candidate_id, job["id"]) == 1
    assert v.count_rows(engine, "application") == 1

    record(
        evidence,
        "I3",
        {
            "rule": ("a candidate may apply to the same job only once (FP-CAN-3)"),
            "layers": {
                "application_precheck": "candidate.service.apply selects Application by candidate/job",
                "row_lock": "SELECT Job ... FOR UPDATE",
                "database_constraint": "unique constraint uq_application_candidate_job",
            },
            "original": {
                "status": control.status_code,
                "detail": control.json()["detail"],
                "integrity_errors": 0,
            },
            "variant": {
                "disabled_layer": "application_precheck",
                "status": variant.status_code,
                "detail": body["detail"],
                "precheck_bypassed": precheck["skipped"],
                "integrity_events": commits,
            },
            "application_rows_for_pair": v.application_count_for_pair(
                engine, candidate_id, job["id"]
            ),
            "total_application_rows": v.count_rows(engine, "application"),
            "conclusion": (
                "the database unique constraint is a sufficient backstop; the "
                "application precheck is not the only layer"
            ),
        },
    )


def test_i3_selfcheck_missing_application_constraint_is_detected(
    client,
    account,
    engine,
    clean_tables,
    evidence,
    monkeypatch,
    fast_registration,
):
    employer, _ = account("employer", name="I3 Selfcheck Employer")
    job = v.create_job(client, employer, "I3 Selfcheck Role", ["python"])
    candidate, candidate_id = account(
        "candidate", skills=["Python"], name="I3 Selfcheck Candidate"
    )
    v.apply_to_job(client, candidate, job["id"])
    v.assert_single_application(engine, candidate_id, job["id"])

    v.install_skip_first_application_precheck(monkeypatch)
    dropped = False
    detected = False
    duplicate_count = None
    try:
        v.drop_application_unique_constraint(engine)
        dropped = True
        response = client.post(
            f"/candidate/jobs/{job['id']}/applications",
            headers=candidate,
            json={},
        )
        v.expect(response, 201, "selfcheck duplicate application")
        duplicate_count = v.application_count_for_pair(engine, candidate_id, job["id"])
        assert duplicate_count == 2
        with pytest.raises(AssertionError, match="applications for job"):
            v.assert_single_application(engine, candidate_id, job["id"])
        detected = True
    finally:
        if dropped:
            v.restore_application_unique_constraint(engine, candidate_id, job["id"])

    restored_count = v.application_count_for_pair(engine, candidate_id, job["id"])
    assert restored_count == 1
    v.assert_single_application(engine, candidate_id, job["id"])
    assert detected, (
        "the duplicate-application oracle did not detect the missing constraint"
    )

    record(
        evidence,
        "I3_selfcheck",
        {
            "purpose": (
                "prove the I3 oracle is not vacuous: remove the candidate/job "
                "unique constraint, let the same HTTP request create a second "
                "application, and require assert_single_application to fail"
            ),
            "constraint_removed": "uq_application_candidate_job",
            "second_application_status": 201,
            "application_rows_without_constraint": duplicate_count,
            "oracle_raised": detected,
            "rows_after_restore": restored_count,
            "conclusion": "the duplicate-application oracle detects the missing layer",
        },
    )


def test_i4_reversed_normalization_preserves_scores_and_order(
    client,
    account,
    clean_tables,
    evidence,
    monkeypatch,
    fast_registration,
):
    employer, _ = account("employer", name="I4 Employer")
    candidate_specs = [
        ("I4 Candidate One", ["Python", "SQL"]),
        ("I4 Candidate Two", ["Rust"]),
        ("I4 Candidate Three", ["Python", "Rust", "Go"]),
    ]
    candidates = []
    for name, skills in candidate_specs:
        headers, candidate_id = account("candidate", skills=skills, name=name)
        candidates.append({"id": str(candidate_id), "headers": headers})

    jobs = [
        v.create_job(client, employer, "I4 Alpha", ["python", "sql"]),
        v.create_job(client, employer, "I4 Beta", ["rust"]),
        v.create_job(client, employer, "I4 Gamma", ["python", "rust", "go"]),
    ]
    for candidate in candidates:
        for job in jobs:
            v.apply_to_job(client, candidate["headers"], job["id"])

    baseline_dashboard = {
        candidate["id"]: v.dashboard(client, candidate["headers"])
        for candidate in candidates
    }
    baseline_applicants = {
        job["id"]: v.applicant_list(client, employer, job["id"]) for job in jobs
    }

    # Hand oracle for all nine dashboard cells; these are independent of the
    # implementation.  The metamorphic relation then checks that reversing the
    # normalized list order changes neither these scores nor the row order.
    assert v.score_map(baseline_dashboard[candidates[0]["id"]]) == {
        jobs[0]["id"]: 100,
        jobs[1]["id"]: 0,
        jobs[2]["id"]: 33,
    }
    assert v.score_map(baseline_dashboard[candidates[1]["id"]]) == {
        jobs[0]["id"]: 0,
        jobs[1]["id"]: 100,
        jobs[2]["id"]: 33,
    }
    assert v.score_map(baseline_dashboard[candidates[2]["id"]]) == {
        jobs[0]["id"]: 50,
        jobs[1]["id"]: 100,
        jobs[2]["id"]: 100,
    }

    normalize_state = v.install_reversed_normalize(monkeypatch)
    assert normalize_state["function"](["SQL", "Python"]) == [
        "sql",
        "python",
    ], "the variant did not reverse the normalized list order"

    variant_dashboard = {
        candidate["id"]: v.dashboard(client, candidate["headers"])
        for candidate in candidates
    }
    variant_applicants = {
        job["id"]: v.applicant_list(client, employer, job["id"]) for job in jobs
    }

    for candidate in candidates:
        v.assert_dashboard_unchanged(
            baseline_dashboard[candidate["id"]],
            variant_dashboard[candidate["id"]],
            f"I4 candidate {candidate['id']}",
        )
    for job in jobs:
        v.assert_applicant_lists_unchanged(
            baseline_applicants[job["id"]],
            variant_applicants[job["id"]],
            f"I4 job {job['id']}",
        )
    assert normalize_state["calls"] > 0

    record(
        evidence,
        "I4",
        {
            "rule": (
                "match_score is insensitive to the order of the list returned "
                "by normalize_skills (FP-MATCH-1)"
            ),
            "layers": {
                "algorithm": "match_score converts both normalized lists to sets",
                "database": "not involved in this property",
            },
            "disabled_layer": ("normalize_skills order (returns the list reversed)"),
            "variant_calls": normalize_state["calls"],
            "sample_normalized_order": ["sql", "python"],
            "dashboard_rows_compared": sum(
                len(rows) for rows in baseline_dashboard.values()
            ),
            "applicant_rows_compared": sum(
                len(rows) for rows in baseline_applicants.values()
            ),
            "scores_and_order_unchanged": True,
            "conclusion": (
                "the set-based algorithm makes normalization order irrelevant; "
                "this is a property of the matching implementation, not a "
                "separate check"
            ),
        },
    )


def test_i5_dependency_check_removed_records_whether_database_blocks_delete(
    client,
    account,
    engine,
    clean_tables,
    evidence,
    monkeypatch,
    fast_registration,
):
    from app.employer.model import InterviewSlot

    employer, employer_id = account("employer", name="I5 Employer")
    candidate, _ = account("candidate", skills=["Python"], name="I5 Candidate")

    job_with_application = v.create_job(
        client, employer, "I5 Job With Application", ["python"]
    )
    v.apply_to_job(client, candidate, job_with_application["id"])

    job_with_slot = v.create_job(client, employer, "I5 Job With Slot", ["python"])
    start = v.future_at(days=4, hour=13)
    with Session(engine) as session:
        slot = InterviewSlot(
            employer_id=employer_id,
            job_id=uuid.UUID(job_with_slot["id"]),
            starts_at=start,
            ends_at=start + timedelta(minutes=30),
        )
        session.add(slot)
        session.commit()

    control_application = client.delete(
        f"/employer/jobs/{job_with_application['id']}", headers=employer
    )
    control_slot = client.delete(
        f"/employer/jobs/{job_with_slot['id']}", headers=employer
    )
    assert control_application.status_code == 409
    assert control_slot.status_code == 409
    assert (
        control_application.json()["detail"]
        == "Job has applications or interview slots"
    )
    assert v.job_is_deleted(engine, job_with_application["id"]) is False
    assert v.job_is_deleted(engine, job_with_slot["id"]) is False

    dependency_checks = v.install_skip_job_dependency_checks(monkeypatch)
    variant_application = client.delete(
        f"/employer/jobs/{job_with_application['id']}", headers=employer
    )
    variant_slot = client.delete(
        f"/employer/jobs/{job_with_slot['id']}", headers=employer
    )
    assert variant_application.status_code == 204
    assert variant_slot.status_code == 204
    assert dependency_checks["skipped"] == 4, (
        "expected both dependency probes in each delete to be bypassed"
    )

    application_deleted = v.job_is_deleted(engine, job_with_application["id"])
    slot_deleted = v.job_is_deleted(engine, job_with_slot["id"])
    assert application_deleted is True
    assert slot_deleted is True
    assert v.count_rows(engine, "application") == 1
    assert v.count_rows(engine, "interview_slot") == 1
    assert len(v.slot_rows_for_job(engine, job_with_slot["id"])) == 1

    conclusion = (
        "single application-layer check; the database does not block a soft delete"
    )
    record(
        evidence,
        "I5",
        {
            "rule": (
                "deleting a job with applications or interview slots must "
                "fail with 409 and leave dependents unchanged (FP-EMP-2)"
            ),
            "layers": {
                "application_precheck": (
                    "employer.service.delete_job selects Application and "
                    "InterviewSlot by job_id"
                ),
                "database": (
                    "foreign keys exist, but delete_job is a soft delete "
                    "(UPDATE job.is_deleted), so they are never exercised"
                ),
            },
            "original": {
                "job_with_application_status": control_application.status_code,
                "job_with_slot_status": control_slot.status_code,
                "detail": control_application.json()["detail"],
                "deleted": [False, False],
            },
            "variant": {
                "disabled_layer": "application_precheck",
                "dependency_probes_bypassed": dependency_checks["skipped"],
                "job_with_application_status": variant_application.status_code,
                "job_with_slot_status": variant_slot.status_code,
                "deleted": [application_deleted, slot_deleted],
            },
            "dependents_after_variant": {
                "applications": v.count_rows(engine, "application"),
                "slots": v.count_rows(engine, "interview_slot"),
                "slots_bound_to_job": len(
                    v.slot_rows_for_job(engine, job_with_slot["id"])
                ),
            },
            "conclusion": conclusion,
            "is_business_bug": False,
        },
    )
