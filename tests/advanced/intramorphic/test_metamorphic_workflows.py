"""Metamorphic tests for the end-to-end candidate/employer workflows (P9).

The matching formula's own metamorphic properties are already covered by
``tests/specialized/test_matching_oracles.py`` and are deliberately not
repeated here.  Each test below transforms a *workflow* input through the real
HTTP API and asserts a relation that follows from the requirements:

* M1: creating the slot before or after applying/interviewing is equivalent;
* M2: unrelated employers, jobs, slots and applications are additive noise for
  the original candidate's recommendation order and availability;
* M3: spelling variants of required skills normalize to the same set;
* M4: ``resume_text`` is not an input to the matching score;
* M5: a status round trip without a booking leaves the availability set intact.

Expected values are hand-computed from FP-MATCH-1 / FP-SCHED-1 / FP-SCHED-2,
never produced by calling the function under test.
"""

from __future__ import annotations

import pytest

import variants as v


@pytest.fixture
def fast_registration(monkeypatch):
    """Cheap KDF so fixtures with several accounts stay fast."""

    v.install_fast_registration(monkeypatch)


def test_m1_slot_before_or_after_apply_same_availability(
    client, account, clean_tables, evidence, fast_registration
):
    employer_a, _ = account("employer", name="M1 Employer A")
    employer_b, _ = account("employer", name="M1 Employer B")
    job_a = v.create_job(client, employer_a, "M1 Role A", ["python", "sql"])
    job_b = v.create_job(client, employer_b, "M1 Role B", ["python", "sql"])
    candidate, _ = account("candidate", skills=["Python", "SQL"], name="M1 Candidate")
    start = v.future_at(days=4, hour=9)

    # Workflow A: create the slot first, then apply and become Interviewing.
    slot_a = v.create_slot(client, employer_a, start)
    application_a = v.apply_to_job(client, candidate, job_a["id"])
    v.set_status(
        client,
        employer_a,
        application_a["application_id"],
        application_a["version"],
        "Interviewing",
    )
    available_a = v.available_slots(client, candidate, application_a["application_id"])

    # Workflow B: apply and become Interviewing first, then create the slot.
    application_b = v.apply_to_job(client, candidate, job_b["id"])
    v.set_status(
        client,
        employer_b,
        application_b["application_id"],
        application_b["version"],
        "Interviewing",
    )
    slot_b = v.create_slot(client, employer_b, start)
    available_b = v.available_slots(client, candidate, application_b["application_id"])

    v.assert_slots_unchanged(available_a, available_b, "M1")
    assert v.slot_signature(available_a) == [(slot_a["starts_at"], slot_a["ends_at"])]
    assert v.slot_signature(available_b) == [(slot_b["starts_at"], slot_b["ends_at"])]

    evidence(
        "M1",
        {
            "relation": "slot-before-apply == apply-before-slot for availability",
            "workflow_a": "slot -> apply -> Interviewing",
            "workflow_b": "apply -> Interviewing -> slot",
            "workflow_a_slots": v.slot_signature(available_a),
            "workflow_b_slots": v.slot_signature(available_b),
            "same_timestamps": v.slot_signature(available_a)
            == v.slot_signature(available_b),
            "expected_slot_count": 1,
        },
    )


def test_m2_unrelated_data_does_not_change_relative_order_or_slots(
    client, account, clean_tables, evidence, fast_registration
):
    employer, _ = account("employer", name="M2 Main Employer")
    jobs = [
        v.create_job(client, employer, "Alpha Role", ["python", "sql"]),
        v.create_job(client, employer, "Beta Role", ["python", "rust"]),
        v.create_job(client, employer, "Gamma Role", ["go"]),
    ]
    candidate, _ = account("candidate", skills=["Python", "SQL"], name="M2 Candidate")
    application = v.apply_to_job(client, candidate, jobs[0]["id"])
    v.set_status(
        client,
        employer,
        application["application_id"],
        application["version"],
        "Interviewing",
    )
    v.create_slot(client, employer, v.future_at(days=4, hour=10))

    baseline_dashboard = v.dashboard(client, candidate)
    baseline_slots = v.available_slots(client, candidate, application["application_id"])
    original_ids = [job["id"] for job in jobs]
    baseline_order = v.relative_order(baseline_dashboard, original_ids)
    baseline_scores = {
        job_id: v.score_map(baseline_dashboard)[job_id] for job_id in original_ids
    }
    # Hand oracle (FP-MATCH-1): {python,sql} against
    # {python,sql}/{python,rust}/{go} -> 100 / 50 / 0.
    assert baseline_scores == {
        jobs[0]["id"]: 100,
        jobs[1]["id"]: 50,
        jobs[2]["id"]: 0,
    }
    assert baseline_order == original_ids
    assert len(v.slot_signature(baseline_slots)) == 1

    # Add a completely unrelated employer, two jobs, one slot and one
    # application by another candidate.  These rows must be invisible noise for
    # the original candidate's relative order and availability.
    unrelated_employer, _ = account("employer", name="M2 Unrelated Employer")
    unrelated_jobs = [
        v.create_job(
            client, unrelated_employer, "AAA Unrelated", ["python", "sql", "rust"]
        ),
        v.create_job(client, unrelated_employer, "ZZZ Unrelated", []),
    ]
    unrelated_candidate, _ = account(
        "candidate", skills=["Rust"], name="M2 Unrelated Candidate"
    )
    unrelated_application = v.apply_to_job(
        client, unrelated_candidate, unrelated_jobs[0]["id"]
    )
    v.set_status(
        client,
        unrelated_employer,
        unrelated_application["application_id"],
        unrelated_application["version"],
        "Interviewing",
    )
    v.create_slot(client, unrelated_employer, v.future_at(days=4, hour=11))

    perturbed_dashboard = v.dashboard(client, candidate)
    perturbed_slots = v.available_slots(
        client, candidate, application["application_id"]
    )
    perturbed_scores = v.score_map(perturbed_dashboard)

    assert len(perturbed_dashboard) == len(baseline_dashboard) + 2, (
        "the unrelated jobs did not appear in the dashboard"
    )
    assert {row["id"] for row in perturbed_dashboard} == set(original_ids) | {
        job["id"] for job in unrelated_jobs
    }
    v.assert_relative_order_unchanged(
        baseline_dashboard, perturbed_dashboard, original_ids, "M2"
    )
    assert {
        job_id: perturbed_scores[job_id] for job_id in original_ids
    } == baseline_scores
    v.assert_slots_unchanged(baseline_slots, perturbed_slots, "M2")
    assert len(v.slot_signature(perturbed_slots)) == 1

    evidence(
        "M2",
        {
            "relation": (
                "unrelated rows leave the original candidate's relative "
                "recommendation order and availability unchanged"
            ),
            "baseline_jobs": len(baseline_dashboard),
            "unrelated_jobs": len(unrelated_jobs),
            "baseline_order": baseline_order,
            "perturbed_order": v.relative_order(perturbed_dashboard, original_ids),
            "baseline_scores": baseline_scores,
            "baseline_slots": v.slot_signature(baseline_slots),
            "perturbed_slots": v.slot_signature(perturbed_slots),
            "slot_id_sets_equal": v.slot_ids(perturbed_slots)
            == v.slot_ids(baseline_slots),
        },
    )


def test_m3_required_skill_variants_do_not_change_scores_or_order(
    client, account, clean_tables, evidence, fast_registration
):
    employer, _ = account("employer", name="M3 Employer")
    specs = [
        (
            "M3 Alpha",
            ["python", "sql"],
            ["  PYTHON ", "SQL", "python", "  sql", "   "],
            ["python", "sql"],
        ),
        (
            "M3 Beta",
            ["rust"],
            ["RUST", " rust ", "Rust"],
            ["rust"],
        ),
        (
            "M3 Gamma",
            ["python", "rust"],
            [" Python", "rust ", "PYTHON"],
            ["python", "rust"],
        ),
    ]
    jobs = []
    for title, plain_skills, _variants, _normalized in specs:
        job = v.create_job(client, employer, title, plain_skills)
        jobs.append(job)

    candidate, _ = account(
        "candidate", skills=["Python", "SQL", "Go"], name="M3 Candidate"
    )
    baseline = v.dashboard(client, candidate)
    baseline_signature = v.dashboard_signature(baseline)
    baseline_scores = v.score_map(baseline)
    # Hand oracle (FP-MATCH-1): Alpha 2/2 = 100, Gamma 1/2 = 50, Beta 0/1 = 0.
    assert baseline_scores == {
        jobs[0]["id"]: 100,
        jobs[1]["id"]: 0,
        jobs[2]["id"]: 50,
    }
    assert v.relative_order(baseline, [job["id"] for job in jobs]) == [
        jobs[0]["id"],
        jobs[2]["id"],
        jobs[1]["id"],
    ]

    updated_jobs = []
    for job, (title, _plain, variants, normalized) in zip(jobs, specs):
        response = client.patch(
            f"/employer/jobs/{job['id']}",
            headers=employer,
            json={"version": job["version"], "required_skills": variants},
        )
        updated = v.expect(response, 200, f"update variants for {title}")
        assert updated["required_skills"] == normalized, (
            f"{title}: the API did not normalize the variant list to {normalized!r}"
        )
        updated_jobs.append((updated, variants, normalized))

    perturbed = v.dashboard(client, candidate)
    v.assert_dashboard_unchanged(baseline, perturbed, "M3")
    assert v.score_map(perturbed) == baseline_scores

    evidence(
        "M3",
        {
            "relation": "required-skill spelling variants preserve score and order",
            "variants": [
                {"raw": raw, "normalized": normalized}
                for _updated, raw, normalized in updated_jobs
            ],
            "baseline_scores": baseline_scores,
            "baseline_order": [row["id"] for row in baseline],
            "perturbed_order": [row["id"] for row in perturbed],
            "baseline_signature": baseline_signature,
            "perturbed_signature": v.dashboard_signature(perturbed),
        },
    )


def test_m4_resume_text_is_not_a_matching_input(
    client, account, clean_tables, evidence, fast_registration
):
    employer, _ = account("employer", name="M4 Employer")
    jobs = [
        v.create_job(client, employer, "M4 Alpha", ["python", "sql"]),
        v.create_job(client, employer, "M4 Beta", ["rust"]),
    ]
    candidate, _ = account("candidate", skills=["Python", "SQL"], name="M4 Candidate")
    baseline = v.dashboard(client, candidate)
    baseline_signature = v.dashboard_signature(baseline)
    baseline_scores = v.score_map(baseline)
    # Hand oracle: Alpha 2/2 = 100, Beta 0/1 = 0.
    assert baseline_scores == {jobs[0]["id"]: 100, jobs[1]["id"]: 0}

    profile = v.expect(
        client.get("/candidate/profile", headers=candidate),
        200,
        "read baseline profile",
    )
    assert profile["resume_text"] == ""
    assert profile["version"] == 1

    new_resume = (
        "M4 candidate resume. It mentions Rust, Kubernetes and a made-up "
        "keyword: metamorphic-resume-sentinel-4801."
    )
    updated_profile = v.expect(
        client.patch(
            "/candidate/profile",
            headers=candidate,
            json={"version": profile["version"], "resume_text": new_resume},
        ),
        200,
        "replace resume text",
    )
    assert updated_profile["resume_text"] == new_resume
    assert updated_profile["skills"] == ["python", "sql"]
    assert updated_profile["version"] == 2

    perturbed = v.dashboard(client, candidate)
    v.assert_dashboard_unchanged(baseline, perturbed, "M4")
    assert v.score_map(perturbed) == baseline_scores

    evidence(
        "M4",
        {
            "relation": "resume_text is not a matching input",
            "resume_before": "",
            "resume_after_length": len(new_resume),
            "resume_contains_rust_and_sentinel": (
                "Rust" in new_resume
                and "metamorphic-resume-sentinel-4801" in new_resume
            ),
            "profile_version_after": updated_profile["version"],
            "baseline_scores": baseline_scores,
            "baseline_signature": baseline_signature,
            "perturbed_signature": v.dashboard_signature(perturbed),
        },
    )


def test_m5_status_round_trip_without_booking_preserves_slots(
    client, account, engine, clean_tables, evidence, fast_registration
):
    employer, _ = account("employer", name="M5 Employer")
    job = v.create_job(client, employer, "M5 Role", ["python"])
    candidate, _ = account("candidate", skills=["Python"], name="M5 Candidate")
    application = v.apply_to_job(client, candidate, job["id"])
    interviewing = v.set_status(
        client,
        employer,
        application["application_id"],
        application["version"],
        "Interviewing",
    )
    v.create_slot(client, employer, v.future_at(days=4, hour=10))
    v.create_slot(client, employer, v.future_at(days=4, hour=11))

    before = v.available_slots(client, candidate, application["application_id"])
    assert len(v.slot_signature(before)) == 2
    before_ids = v.slot_ids(before)

    rejected = v.set_status(
        client,
        employer,
        application["application_id"],
        interviewing["version"],
        "Rejected",
    )
    ineligible = client.get(
        f"/candidate/applications/{application['application_id']}/slots",
        headers=candidate,
    )
    assert ineligible.status_code == 409, (
        "a Rejected application must not expose availability"
    )
    assert ineligible.json()["detail"] == "Application must be Interviewing"

    restored = v.set_status(
        client,
        employer,
        application["application_id"],
        rejected["version"],
        "Interviewing",
    )
    after = v.available_slots(client, candidate, application["application_id"])

    v.assert_slots_unchanged(before, after, "M5")
    assert v.slot_ids(after) == before_ids
    assert restored["status"] == "Interviewing"
    assert v.count_rows(engine, "booking") == 0, (
        "the status round trip created a booking"
    )
    assert v.count_rows(engine, "interview_slot") == 2

    evidence(
        "M5",
        {
            "relation": (
                "Interviewing -> Rejected -> Interviewing without a booking "
                "restores exactly the same availability set"
            ),
            "transitions": [
                "Pending -> Interviewing",
                "Interviewing -> Rejected",
                "Rejected -> Interviewing",
            ],
            "middle_status_code": ineligible.status_code,
            "middle_detail": ineligible.json()["detail"],
            "before_slots": v.slot_signature(before),
            "after_slots": v.slot_signature(after),
            "slot_ids_equal": before_ids == v.slot_ids(after),
        },
    )


def test_metamorphic_dashboard_oracle_goes_red_on_corrupted_score(
    client, account, clean_tables, evidence, monkeypatch, fast_registration
):
    """Self-check: the M3/M4/I4 comparison rejects a changed score.

    ``match_score`` is replaced only for this test; the HTTP route, schemas and
    database stay real.  After ``monkeypatch.undo()`` the same comparison must
    pass again, proving the red result came from the oracle and not from a
    broken fixture.
    """

    employer, _ = account("employer", name="Selfcheck Dashboard Employer")
    job = v.create_job(client, employer, "Selfcheck Dashboard Role", ["python", "sql"])
    candidate, _ = account(
        "candidate", skills=["Python"], name="Selfcheck Dashboard Candidate"
    )
    baseline = v.dashboard(client, candidate)
    # Hand oracle: one of two required skills -> 50.
    assert v.score_map(baseline) == {job["id"]: 50}

    from app.candidate import service as candidate_service

    monkeypatch.setattr(candidate_service, "match_score", lambda candidate, required: 0)
    corrupted = v.dashboard(client, candidate)
    assert v.score_map(corrupted) == {job["id"]: 0}
    with pytest.raises(AssertionError, match="recommendation signature changed"):
        v.assert_dashboard_unchanged(baseline, corrupted, "self-check")

    monkeypatch.undo()
    restored = v.dashboard(client, candidate)
    v.assert_dashboard_unchanged(baseline, restored, "restored")

    evidence(
        "selfcheck_metamorphic_dashboard",
        {
            "purpose": ("prove the M3/M4/I4 dashboard oracle rejects a changed score"),
            "baseline_score": 50,
            "corrupted_score": 0,
            "oracle_raised": True,
            "restored_score": v.score_map(restored)[job["id"]],
        },
    )


def test_metamorphic_slot_oracle_goes_red_on_truncated_availability(
    client, account, clean_tables, evidence, monkeypatch, fast_registration
):
    """Self-check: the M1/M2/M5 comparison rejects a changed slot set."""

    employer, _ = account("employer", name="Selfcheck Slot Employer")
    job = v.create_job(client, employer, "Selfcheck Slot Role", ["python"])
    candidate, _ = account(
        "candidate", skills=["Python"], name="Selfcheck Slot Candidate"
    )
    application = v.apply_to_job(client, candidate, job["id"])
    v.set_status(
        client,
        employer,
        application["application_id"],
        application["version"],
        "Interviewing",
    )
    v.create_slot(client, employer, v.future_at(days=4, hour=10))
    v.create_slot(client, employer, v.future_at(days=4, hour=11))
    baseline = v.available_slots(client, candidate, application["application_id"])
    assert len(baseline) == 2

    from app.candidate import service as candidate_service

    real_available = candidate_service.available_slots

    def truncated(session, user, application_id):
        return real_available(session, user, application_id)[:1]

    monkeypatch.setattr(candidate_service, "available_slots", truncated)
    corrupted = v.available_slots(client, candidate, application["application_id"])
    assert len(corrupted) == 1
    with pytest.raises(AssertionError, match="availability signature changed"):
        v.assert_slots_unchanged(baseline, corrupted, "self-check")

    monkeypatch.undo()
    restored = v.available_slots(client, candidate, application["application_id"])
    v.assert_slots_unchanged(baseline, restored, "restored")

    evidence(
        "selfcheck_metamorphic_slots",
        {
            "purpose": (
                "prove the M1/M2/M5 availability oracle rejects a changed slot set"
            ),
            "baseline_slots": len(baseline),
            "corrupted_slots": len(corrupted),
            "oracle_raised": True,
            "restored_slots": len(restored),
        },
    )
