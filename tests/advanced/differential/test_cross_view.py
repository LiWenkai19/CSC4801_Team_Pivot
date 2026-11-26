"""Differential cross-view test for FP-MATCH-1 / FP-CAN-2 / FP-EMP-3.

The candidate dashboard and the employer applicant list are two separate code
paths that must compute the same score for the same (candidate, job) pair.
This test builds one deterministic 40 x 15 dataset through the real HTTP API,
has every candidate apply to every job (600 applications), then compares the
two tables of ``(candidate_id, job_id) -> score`` entry by entry.

It also checks each ordering against an independently written key function:

* candidate dashboard: (-score, case-folded title, job id);
* employer applicants: (-score, case-folded display name, candidate id).

The dataset deliberately contains six job titles that differ only by case and
six candidate names that differ only by case, so both secondary keys and both
tertiary tie-breaks are actually exercised.  Scores are hand-checkable: the
Robin Lee candidates and the ``Data Engineer`` jobs both have the skill set
{``python``, ``sql``, ``rust``}, so those pairs must score exactly 100.

Synthetic accounts use a cheap KDF instead of Argon2 (see
``fast_registration``); the real HTTP registration path still runs, and these
tests target matching, not password storage.

Two self-checks live here: monkeypatching the candidate service's
``match_score`` to ``lambda candidate, required: 0`` must make the equality
oracle fail, and a reversed list must make the sorting oracle fail.  Both are
restored inside the test, so production code is never modified.
"""

from __future__ import annotations

from collections import defaultdict
import json
import random
import uuid

import pytest

SEED = 4801
CANDIDATE_COUNT = 40
JOB_COUNT = 15

SKILL_VOCABULARY = (
    "python",
    "sql",
    "java",
    "c++",
    "rust",
    "go",
    "docker",
    "kubernetes",
    "javascript",
    "postgresql",
)

_STYLES = (
    lambda skill: skill,
    lambda skill: skill.upper(),
    lambda skill: skill.capitalize(),
    lambda skill: "  " + skill,
    lambda skill: skill.upper() + "  ",
    lambda skill: " " + skill.capitalize() + " ",
)

# Six names that differ only by case: equal case-folded secondary key.  Using
# more than the required three makes it very unlikely that a buggy raw-string
# sort happens to coincide with the stable-ID order.
TIE_CANDIDATE_NAMES = (
    "Robin Lee",
    "ROBIN LEE",
    "robin lee",
    "Robin lee",
    "ROBIN lee",
    "robin LEE",
)
# Six titles that differ only by case: equal case-folded secondary key.
TIE_JOB_TITLES = (
    "Data Engineer",
    "DATA ENGINEER",
    "data engineer",
    "Data engineer",
    "DATA engineer",
    "data ENGINEER",
)
# Both tie groups share this skill set, so their score is hand-computable.
TIE_SKILLS = ("Python", "sql", "Rust")

EXPECTED_APPLICATIONS = CANDIDATE_COUNT * JOB_COUNT


@pytest.fixture
def fast_registration(monkeypatch):
    """Use a cheap deterministic KDF for the dozens of synthetic accounts.

    The real registration/profile/job HTTP paths still run end to end; only the
    expensive Argon2 KDF is replaced.  Matching tests never verify passwords.
    """

    from app.users import service as users_service

    monkeypatch.setattr(
        users_service,
        "hash_password",
        lambda password: "advanced-fast::" + password,
    )


def _styled(rng: random.Random, skill: str) -> str:
    return rng.choice(_STYLES)(skill)


def _build_dataset(client, account):
    """Create 40 candidates and 15 jobs through the real HTTP API."""

    rng = random.Random(SEED)

    candidates = []
    for index in range(CANDIDATE_COUNT):
        if index < len(TIE_CANDIDATE_NAMES):
            name = TIE_CANDIDATE_NAMES[index]
            raw_skills = list(TIE_SKILLS)
        else:
            name = f"Candidate {index:02d}"
            picked = rng.sample(SKILL_VOCABULARY, rng.randint(0, 6))
            raw_skills = [_styled(rng, skill) for skill in picked]
        headers, user_id = account("candidate", skills=raw_skills, name=name)
        candidates.append(
            {"id": str(user_id), "name": name, "headers": headers}
        )

    employer_headers, _ = account("employer", name="Differential Company")

    jobs = []
    for index in range(JOB_COUNT):
        if index < len(TIE_JOB_TITLES):
            title = TIE_JOB_TITLES[index]
            raw_skills = list(TIE_SKILLS)
        else:
            title = f"Role {index:02d}"
            if index == len(TIE_JOB_TITLES):  # empty requirements: 100 for all
                picked = []
            elif index == len(TIE_JOB_TITLES) + 1:  # every skill required
                picked = list(SKILL_VOCABULARY)
            else:
                picked = rng.sample(SKILL_VOCABULARY, rng.randint(1, 6))
            raw_skills = [_styled(rng, skill) for skill in picked]
        response = client.post(
            "/employer/jobs",
            headers=employer_headers,
            json={
                "title": title,
                "description": f"Cross-view differential job: {title}",
                "required_skills": raw_skills,
            },
        )
        assert response.status_code == 201, response.text
        jobs.append({"id": response.json()["id"], "title": title})

    return candidates, employer_headers, jobs


def _application_plan(candidates, jobs):
    """Return the ``(candidate_id, job_id)`` pairs to create.

    Every candidate applies to every job, so the employer side has one row per
    pair and the two views can be compared on all 600 pairs.
    """

    return {
        (candidate["id"], job["id"])
        for candidate in candidates
        for job in jobs
    }


def _apply_plan(client, candidates, plan):
    headers = {candidate["id"]: candidate["headers"] for candidate in candidates}
    for candidate_id, job_id in sorted(plan):
        response = client.post(
            f"/candidate/jobs/{job_id}/applications",
            headers=headers[candidate_id],
            json={},
        )
        assert response.status_code == 201, response.text
    return len(plan)


def _collect_views(client, candidates, employer_headers, jobs, plan):
    """Build the two ``(candidate_id, job_id) -> score`` tables.

    The candidate dashboard lists every job, so it yields a score for all 600
    pairs; with every candidate applying to every job the employer view has the
    same 600 rows.  Raw response rows are also returned so ordering can be
    checked separately.
    """

    job_ids = {job["id"] for job in jobs}
    candidate_rows: dict[str, list[dict]] = {}
    candidate_scores: dict[tuple[str, str], int] = {}
    for candidate in candidates:
        response = client.get("/candidate/jobs", headers=candidate["headers"])
        assert response.status_code == 200, response.text
        rows = response.json()
        candidate_rows[candidate["id"]] = rows
        assert {row["id"] for row in rows} == job_ids, (
            f"candidate {candidate['id']} does not see exactly the 15 jobs"
        )
        for row in rows:
            candidate_scores[(candidate["id"], row["id"])] = row["match_score"]

    expected_applicants: dict[str, set[str]] = defaultdict(set)
    for candidate_id, job_id in plan:
        expected_applicants[job_id].add(candidate_id)

    employer_rows: dict[str, list[dict]] = {}
    employer_scores: dict[tuple[str, str], int] = {}
    for job in jobs:
        response = client.get(
            f"/employer/jobs/{job['id']}/applications",
            headers=employer_headers,
        )
        assert response.status_code == 200, response.text
        rows = response.json()
        employer_rows[job["id"]] = rows
        assert {row["candidate_id"] for row in rows} == expected_applicants[
            job["id"]
        ], f"job {job['id']} applicant set does not match the application plan"
        for row in rows:
            employer_scores[(row["candidate_id"], job["id"])] = row["match_score"]

    return candidate_scores, candidate_rows, employer_scores, employer_rows


def _assert_score_tables_equal(candidate_scores, employer_scores):
    """Raise with a minimal counterexample when the two views disagree."""

    missing = sorted(set(candidate_scores) - set(employer_scores))
    extra = sorted(set(employer_scores) - set(candidate_scores))
    differing = [
        {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "candidate_view": candidate_scores[(candidate_id, job_id)],
            "employer_view": employer_scores[(candidate_id, job_id)],
        }
        for candidate_id, job_id in sorted(
            set(candidate_scores) & set(employer_scores)
        )
        if candidate_scores[(candidate_id, job_id)]
        != employer_scores[(candidate_id, job_id)]
    ]
    if missing or extra or differing:
        raise AssertionError(
            "candidate and employer views disagree: "
            + json.dumps(
                {
                    "missing_in_employer_view": missing[:5],
                    "missing_in_candidate_view": extra[:5],
                    "differing_scores": differing[:5],
                },
                indent=2,
                sort_keys=True,
            )
        )
    return len(candidate_scores)


def _candidate_sort_key(row):
    """Independent FP-MATCH-1 candidate ordering: -score, title, job id."""

    return (
        -row["match_score"],
        row["title"].casefold(),
        uuid.UUID(row["id"]).int,
    )


def _employer_sort_key(row):
    """Independent FP-MATCH-1 applicant ordering: -score, name, candidate id."""

    return (
        -row["match_score"],
        row["display_name"].casefold(),
        uuid.UUID(row["candidate_id"]).int,
    )


def _check_order(rows, key, label):
    """Validate a view order and return the number of real tie groups.

    A tie group is a maximal adjacent run with an equal primary score and an
    equal case-folded secondary key; its tertiary key must be ascending.
    """

    keys = [key(row) for row in rows]
    for position in range(1, len(keys)):
        if keys[position] < keys[position - 1]:
            raise AssertionError(
                f"{label}: order violates (-score, case-folded secondary key, "
                f"ID) at positions {position - 1} and {position}: "
                f"{keys[position - 1]!r} > {keys[position]!r}"
            )

    groups = 0
    index = 0
    while index < len(keys):
        end = index + 1
        while end < len(keys) and keys[end][:2] == keys[index][:2]:
            end += 1
        if end - index >= 2:
            tertiary = [keys[position][2] for position in range(index, end)]
            if tertiary != sorted(tertiary):
                raise AssertionError(
                    f"{label}: tie group {index}..{end - 1} is not ordered by "
                    f"stable ID: {tertiary!r}"
                )
            groups += 1
        index = end
    return groups


def _assert_constructed_ties(candidate_rows, employer_rows, candidates, jobs):
    """Check the deliberately constructed case-only tie groups.

    Returns the number of employer-side tie groups observed.  The candidate
    dashboard contains every job, so its title tie group must be present for
    all 40 candidates; every applicant list contains every candidate, so the
    employer name tie group must be present on all 15 jobs.
    """

    tie_job_ids = {
        job["id"] for job in jobs if job["title"].casefold() == "data engineer"
    }
    assert len(tie_job_ids) == len(TIE_JOB_TITLES), (
        "expected exactly "
        f"{len(TIE_JOB_TITLES)} job titles differing only by case, got "
        f"{sorted(job['title'] for job in jobs)!r}"
    )
    tie_candidate_ids = {
        candidate["id"]
        for candidate in candidates
        if candidate["name"].casefold() == "robin lee"
    }
    assert len(tie_candidate_ids) == len(TIE_CANDIDATE_NAMES), (
        "expected exactly "
        f"{len(TIE_CANDIDATE_NAMES)} candidate names differing only by case, "
        "got "
        f"{sorted(candidate['name'] for candidate in candidates if candidate['id'] in tie_candidate_ids)!r}"
    )

    # Candidate dashboard: the six case-only titles are always present.
    expected_tie_ids = sorted(uuid.UUID(job_id).int for job_id in tie_job_ids)
    tie_size = len(TIE_JOB_TITLES)
    for candidate in candidates:
        rows = candidate_rows[candidate["id"]]
        scores = {
            row["match_score"] for row in rows if row["id"] in tie_job_ids
        }
        assert len(scores) == 1, (
            f"candidate {candidate['id']}: case-only title variants do not "
            f"share one score: {scores!r}"
        )
        positions = [
            position
            for position, row in enumerate(rows)
            if row["id"] in tie_job_ids
        ]
        assert positions == list(range(positions[0], positions[0] + tie_size)), (
            f"candidate {candidate['id']}: title tie group is not adjacent"
        )
        actual = [uuid.UUID(rows[position]["id"]).int for position in positions]
        assert actual == expected_tie_ids, (
            f"candidate {candidate['id']}: title tie group not ordered by job id"
        )
        if candidate["name"].casefold() == "robin lee":
            # Hand oracle: identical normalised P/S/R sets => 100.
            assert scores == {100}, (
                f"candidate {candidate['id']}: expected 100 on every P/S/R "
                f"tie job, got {scores!r}"
            )

    # Employer applicants: every candidate applied, so all six name variants
    # are present on every job.
    employer_groups = 0
    for job in jobs:
        rows = employer_rows[job["id"]]
        robin_rows = [
            row
            for row in rows
            if row["candidate_id"] in tie_candidate_ids
        ]
        scores = {row["match_score"] for row in robin_rows}
        assert len(scores) <= 1, (
            f"job {job['id']}: case-only name variants do not share one "
            f"score: {scores!r}"
        )
        if len(robin_rows) >= 2:
            positions = [
                position
                for position, row in enumerate(rows)
                if row["candidate_id"] in tie_candidate_ids
            ]
            assert positions == list(
                range(positions[0], positions[0] + len(robin_rows))
            ), f"job {job['id']}: applicant tie group is not adjacent"
            actual = [
                uuid.UUID(rows[position]["candidate_id"]).int
                for position in positions
            ]
            assert actual == sorted(actual), (
                f"job {job['id']}: applicant tie group not ordered by "
                f"candidate id: {actual!r}"
            )
            employer_groups += 1
        if job["title"].casefold() == "data engineer":
            # Every candidate applies to the title jobs, so the full group of
            # six case-only names must be there, all with the hand oracle 100.
            assert len(robin_rows) == len(TIE_CANDIDATE_NAMES), (
                f"job {job['id']}: expected all "
                f"{len(TIE_CANDIDATE_NAMES)} P/S/R tie candidates, got "
                f"{len(robin_rows)}"
            )
            assert scores == {100}, (
                f"job {job['id']}: expected 100 for every P/S/R candidate, "
                f"got {scores!r}"
            )
    return employer_groups


def test_candidate_and_employer_views_agree_on_every_pair(
    client, account, clean_tables, evidence, fast_registration
):
    candidates, employer_headers, jobs = _build_dataset(client, account)
    plan = _application_plan(candidates, jobs)
    applied = _apply_plan(client, candidates, plan)
    assert applied == len(plan) == EXPECTED_APPLICATIONS

    candidate_scores, candidate_rows, employer_scores, employer_rows = (
        _collect_views(client, candidates, employer_headers, jobs, plan)
    )
    assert set(employer_scores) == plan
    applied_candidate_scores = {key: candidate_scores[key] for key in plan}
    cross_view_pairs = _assert_score_tables_equal(
        applied_candidate_scores, employer_scores
    )
    assert cross_view_pairs == EXPECTED_APPLICATIONS

    candidate_tie_groups = sum(
        _check_order(rows, _candidate_sort_key, f"candidate {candidate_id}")
        for candidate_id, rows in candidate_rows.items()
    )
    employer_tie_groups = sum(
        _check_order(rows, _employer_sort_key, f"job {job_id}")
        for job_id, rows in employer_rows.items()
    )
    assert candidate_tie_groups == CANDIDATE_COUNT, (
        "every candidate dashboard must contain exactly one case-only title "
        f"tie group, saw {candidate_tie_groups}"
    )
    constructed_employer_groups = _assert_constructed_ties(
        candidate_rows, employer_rows, candidates, jobs
    )
    assert employer_tie_groups == constructed_employer_groups, (
        "the generic ordering check and the constructed-tie check disagree "
        f"about employer tie groups: {employer_tie_groups} != "
        f"{constructed_employer_groups}"
    )
    assert employer_tie_groups == JOB_COUNT, (
        "every applicant list must contain exactly one case-only name tie "
        f"group, saw {employer_tie_groups}"
    )

    cross_view = {
        "cross_view_pairs": cross_view_pairs,
        "applications": applied,
        "candidate_dashboard_pairs": len(candidate_scores),
        "tie_groups": candidate_tie_groups + employer_tie_groups,
        "candidate_tie_groups": candidate_tie_groups,
        "employer_tie_groups": employer_tie_groups,
        "tie_job_title_variants": len(TIE_JOB_TITLES),
        "tie_candidate_name_variants": len(TIE_CANDIDATE_NAMES),
        "application_policy": "every candidate applies to every job",
        "tie_group_definition": (
            "maximal adjacent runs with equal score and equal case-folded "
            "secondary key, counted once per candidate list and once per job "
            "list"
        ),
    }
    # ``differential`` is merged with the SQL metrics by the sibling test when
    # the whole mode runs; writing it here keeps a standalone run complete.
    evidence("cross-view", cross_view)
    evidence("differential", cross_view)


def test_cross_view_oracle_goes_red_and_recovers(
    client, account, clean_tables, monkeypatch, fast_registration
):
    """Self-check: mutate the candidate service and require a red oracle."""

    employer_headers, _ = account("employer", name="Mutation Check Company")
    jobs = []
    for title, required in (
        ("Mutation Role A", ["Python", "SQL"]),
        ("Mutation Role B", ["Rust"]),
    ):
        response = client.post(
            "/employer/jobs",
            headers=employer_headers,
            json={
                "title": title,
                "description": f"Self-check job: {title}",
                "required_skills": required,
            },
        )
        assert response.status_code == 201, response.text
        jobs.append({"id": response.json()["id"], "title": title})

    candidate_headers, candidate_id = account(
        "candidate", skills=["Python"], name="Mutation Check Candidate"
    )
    candidates = [
        {
            "id": str(candidate_id),
            "name": "Mutation Check Candidate",
            "headers": candidate_headers,
        }
    ]
    plan = {(str(candidate_id), job["id"]) for job in jobs}
    assert _apply_plan(client, candidates, plan) == 2

    job_a = jobs[0]["id"]
    key_a = (str(candidate_id), job_a)
    candidate_scores, candidate_rows, employer_scores, _ = _collect_views(
        client, candidates, employer_headers, jobs, plan
    )
    # Hand oracle: |{python, sql} intersect {python}| / 2 = 50.
    assert candidate_scores[key_a] == employer_scores[key_a] == 50
    assert _assert_score_tables_equal(candidate_scores, employer_scores) == 2

    from app.candidate import service as candidate_service

    monkeypatch.setattr(
        candidate_service, "match_score", lambda candidate, required: 0
    )
    (
        mutated_candidate_scores,
        mutated_candidate_rows,
        mutated_employer_scores,
        _,
    ) = _collect_views(client, candidates, employer_headers, jobs, plan)
    assert mutated_candidate_scores[key_a] == 0
    assert mutated_employer_scores[key_a] == 50
    with pytest.raises(
        AssertionError, match="candidate and employer views disagree"
    ):
        _assert_score_tables_equal(
            mutated_candidate_scores, mutated_employer_scores
        )

    # The independent ordering oracle must also reject a deliberately
    # unsorted list instead of accepting whatever order the implementation
    # returned.
    rows = mutated_candidate_rows[str(candidate_id)]
    with pytest.raises(AssertionError, match="order violates"):
        _check_order(
            list(reversed(rows)), _candidate_sort_key, "self-check candidate"
        )

    monkeypatch.undo()
    restored_candidate_scores, _, restored_employer_scores, _ = _collect_views(
        client, candidates, employer_headers, jobs, plan
    )
    assert restored_candidate_scores[key_a] == 50
    assert _assert_score_tables_equal(
        restored_candidate_scores, restored_employer_scores
    ) == 2
