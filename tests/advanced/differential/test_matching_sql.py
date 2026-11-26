"""Differential oracle: FP-MATCH-1 in Python versus an independent SQL query.

The Python side calls the production ``app.employer.matching.match_score``.
The SQL side is written from the specification in this file and never imports
the production matching module.  Both are evaluated on the same rows that were
created through the real HTTP API, so the stored skill names already went
through ``normalize_skills`` (trim, lowercase, drop empty items, deduplicate).

FP-MATCH-1::

    score = 100                                                if |R| = 0
    score = floor(100 * |C intersection R| / |R|)              otherwise

Expected values therefore come from the written requirement, not from the
implementation under test.  A disagreement prints both skill lists, the SQL
value and the Python value for the counterexample.

The dataset is generated with ``random.Random(4801)``: 40 candidates and 15
jobs, i.e. 600 (candidate, job) pairs.  Skill inputs deliberately contain case
and whitespace variants so the real normalisation path is exercised.
"""

from __future__ import annotations

from collections import defaultdict
import json
import os
from pathlib import Path
import random
from tempfile import gettempdir

import pytest
from sqlalchemy import text

from app.employer.matching import match_score

SEED = 4801
CANDIDATE_COUNT = 40
JOB_COUNT = 15
EXPECTED_PAIRS = CANDIDATE_COUNT * JOB_COUNT

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

# Case / surrounding-whitespace variants of the canonical vocabulary.
_STYLES = (
    lambda skill: skill,
    lambda skill: skill.upper(),
    lambda skill: skill.capitalize(),
    lambda skill: "  " + skill,
    lambda skill: skill.upper() + "  ",
    lambda skill: " " + skill.capitalize() + " ",
)

# One independent implementation of FP-MATCH-1 in SQL.  The database stores
# already-normalised names (CHECK constraints enforce lower(trim(name))), so the
# query must not lower/trim again.  ``:perfect`` and ``:deleted`` are bound
# parameters; no identifier is interpolated into the statement.
SQL_SCORE = text(
    """
    SELECT cp.user_id AS candidate_id,
           j.id AS job_id,
           CASE
               WHEN required.total = 0 THEN :perfect
               ELSE CAST(
                   floor((100.0 * overlap.total) / required.total)
                   AS integer
               )
           END AS score
      FROM candidate_profile AS cp
     CROSS JOIN job AS j
     CROSS JOIN LATERAL (
           SELECT count(*) AS total
             FROM job_skill AS js
            WHERE js.job_id = j.id
     ) AS required
     CROSS JOIN LATERAL (
           SELECT count(*) AS total
             FROM job_skill AS js
            WHERE js.job_id = j.id
              AND EXISTS (
                  SELECT 1
                    FROM candidate_skill AS cs
                   WHERE cs.candidate_id = cp.user_id
                     AND cs.name = js.name
              )
     ) AS overlap
     WHERE j.is_deleted = :deleted
     ORDER BY cp.user_id, j.id
    """
)


def _styled(rng: random.Random, skill: str) -> str:
    """Return *skill* in a random case/whitespace variant."""

    return rng.choice(_STYLES)(skill)


@pytest.fixture
def fast_registration(monkeypatch):
    """Use a cheap deterministic KDF for the synthetic accounts.

    Registration, profile creation and job creation still run through the real
    HTTP API; only the expensive Argon2 KDF is replaced.  These tests exercise
    skill normalisation and matching, never password verification.
    """

    from app.users import service as users_service

    monkeypatch.setattr(
        users_service,
        "hash_password",
        lambda password: "advanced-fast::" + password,
    )


def _normalized(skills: list[str]) -> list[str]:
    """Independent hand implementation of the FP-MATCH-1 normalisation rule."""

    return sorted({skill.strip().lower() for skill in skills} - {""})


def _generated_specs() -> tuple[list[tuple[str, list[str]]], list[tuple[str, list[str]]]]:
    """Build the deterministic 40-candidate / 15-job specification."""

    rng = random.Random(SEED)
    candidates: list[tuple[str, list[str]]] = []
    for index in range(CANDIDATE_COUNT):
        if index == 0:  # full overlap with every job, including the full job
            picked = list(SKILL_VOCABULARY)
        elif index == 1:  # no skills: 0 for non-empty requirement lists
            picked = []
        else:
            picked = rng.sample(SKILL_VOCABULARY, rng.randint(1, 6))
        candidates.append(
            (f"SQL Candidate {index:02d}", [_styled(rng, skill) for skill in picked])
        )

    jobs: list[tuple[str, list[str]]] = []
    for index in range(JOB_COUNT):
        if index == 0:  # no requirements: everyone scores 100
            picked = []
        elif index == 1:  # every skill required: exercises full-coverage scores
            picked = list(SKILL_VOCABULARY)
        else:
            picked = rng.sample(SKILL_VOCABULARY, rng.randint(1, 6))
        jobs.append(
            (f"SQL Role {index:02d}", [_styled(rng, skill) for skill in picked])
        )
    return candidates, jobs


def _populate(client, account, candidate_specs, job_specs):
    """Create candidates and jobs through the real HTTP API.

    Returns candidate ids, job ids and the expected normalised skill lists for
    both sides (computed here, not by the production helper).
    """

    candidates: list[str] = []
    expected_candidate_skills: dict[str, list[str]] = {}
    for name, raw_skills in candidate_specs:
        _, user_id = account("candidate", skills=raw_skills, name=name)
        key = str(user_id)
        candidates.append(key)
        expected_candidate_skills[key] = _normalized(raw_skills)

    employer_headers, _ = account("employer", name="SQL Differential Company")
    jobs: list[str] = []
    expected_job_skills: dict[str, list[str]] = {}
    for title, raw_skills in job_specs:
        response = client.post(
            "/employer/jobs",
            headers=employer_headers,
            json={
                "title": title,
                "description": f"Deterministic differential job: {title}",
                "required_skills": raw_skills,
            },
        )
        assert response.status_code == 201, response.text
        job_id = response.json()["id"]
        jobs.append(job_id)
        expected = _normalized(raw_skills)
        # The public response echoes the names persisted by create_job.
        assert response.json()["required_skills"] == expected
        expected_job_skills[job_id] = expected
    return candidates, jobs, expected_candidate_skills, expected_job_skills


def _read_stored_skills(engine):
    """Read the persisted, already-normalised skills from PostgreSQL."""

    stored_candidates: dict[str, list[str]] = defaultdict(list)
    stored_jobs: dict[str, list[str]] = defaultdict(list)
    with engine.connect() as connection:
        for candidate_id, name in connection.execute(
            text("SELECT candidate_id, name FROM candidate_skill")
        ):
            stored_candidates[str(candidate_id)].append(name)
        for job_id, name in connection.execute(
            text("SELECT job_id, name FROM job_skill")
        ):
            stored_jobs[str(job_id)].append(name)
    return stored_candidates, stored_jobs


def _assert_stored_normalised(actual, expected, label):
    """The SQL oracle is only valid if the database holds normalised names."""

    assert set(actual) <= set(expected), (
        f"{label}: unexpected owners in the database: "
        f"{sorted(set(actual) - set(expected))}"
    )
    for owner, expected_names in expected.items():
        names = actual.get(owner, [])
        assert sorted(names) == expected_names, (
            f"{label} {owner}: stored skills {sorted(names)!r} != expected "
            f"{expected_names!r} from the real API normalisation path"
        )
        assert all(name == name.strip().lower() for name in names), (
            f"{label} {owner}: a stored name is not trim/lower normalised: "
            f"{sorted(names)!r}"
        )


def _sql_scores(engine):
    """Return ``{(candidate_id, job_id): score}`` from the independent SQL."""

    with engine.connect() as connection:
        rows = connection.execute(
            SQL_SCORE, {"perfect": 100, "deleted": False}
        ).all()
    return {
        (str(row.candidate_id), str(row.job_id)): int(row.score) for row in rows
    }


def _python_scores(candidate_ids, job_ids, candidate_skills, job_skills):
    """Return the production ``match_score`` for every pair."""

    return {
        (candidate_id, job_id): match_score(
            candidate_skills.get(candidate_id, []), job_skills.get(job_id, [])
        )
        for candidate_id in candidate_ids
        for job_id in job_ids
    }


def _differences(sql_scores, python_scores, candidate_skills, job_skills):
    """Return minimal counterexamples with both skill lists and both scores."""

    differences = []
    for key in sorted(set(sql_scores) & set(python_scores)):
        sql_value = sql_scores[key]
        python_value = python_scores[key]
        if sql_value == python_value:
            continue
        candidate_id, job_id = key
        differences.append(
            {
                "candidate_id": candidate_id,
                "job_id": job_id,
                "candidate_skills": sorted(candidate_skills.get(candidate_id, [])),
                "required_skills": sorted(job_skills.get(job_id, [])),
                "sql_score": sql_value,
                "python_score": python_value,
            }
        )
    return differences


def _raise_on_differences(differences, total):
    if not differences:
        return
    raise AssertionError(
        f"{len(differences)} of {total} (candidate, job) pairs disagree between "
        "the Python implementation and the independent SQL oracle; first "
        "counterexamples:\n"
        + json.dumps(differences[:5], indent=2, sort_keys=True)
    )


def _evidence_folder() -> Path:
    """Same location contract as the shared ``evidence`` fixture."""

    base = os.environ.get("ADVANCED_OUT")
    mode = os.environ.get("ADVANCED_MODE", "adhoc")
    if base:
        return Path(base) / mode
    return Path(gettempdir()) / "csc4801-advanced-evidence" / mode


def _existing_evidence(name: str) -> dict:
    """Read a JSON file written earlier by the sibling differential test."""

    path = _evidence_folder() / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def test_python_match_score_agrees_with_independent_sql(
    client, account, engine, clean_tables, evidence, fast_registration
):
    """All 600 pairs must agree with the hand-written SQL implementation."""

    candidate_specs, job_specs = _generated_specs()
    candidates, jobs, expected_candidate_skills, expected_job_skills = _populate(
        client, account, candidate_specs, job_specs
    )
    assert len(candidates) == CANDIDATE_COUNT
    assert len(jobs) == JOB_COUNT

    candidate_skills, job_skills = _read_stored_skills(engine)
    _assert_stored_normalised(
        candidate_skills, expected_candidate_skills, "candidate_skill"
    )
    _assert_stored_normalised(job_skills, expected_job_skills, "job_skill")

    sql_scores = _sql_scores(engine)
    python_scores = _python_scores(candidates, jobs, candidate_skills, job_skills)

    all_pairs = {(candidate, job) for candidate in candidates for job in jobs}
    assert set(sql_scores) == all_pairs, (
        "the SQL query did not return exactly one row per (candidate, job): "
        f"missing={sorted(all_pairs - set(sql_scores))[:5]} "
        f"extra={sorted(set(sql_scores) - all_pairs)[:5]}"
    )
    assert set(python_scores) == all_pairs
    assert len(sql_scores) == EXPECTED_PAIRS

    differences = _differences(
        sql_scores, python_scores, candidate_skills, job_skills
    )

    # Merge with the cross-view metrics when the whole mode ran in order.
    merged = dict(_existing_evidence("differential"))
    merged.update(
        {
            "pairs": len(sql_scores),
            "sql_mismatch": len(differences),
            "candidate_count": len(candidates),
            "job_count": len(jobs),
            "distinct_scores": len(set(sql_scores.values())),
            "zero_scores": sum(value == 0 for value in sql_scores.values()),
            "perfect_scores": sum(value == 100 for value in sql_scores.values()),
        }
    )
    if differences:
        merged["mismatch_examples"] = differences[:5]
    evidence("differential", merged)

    _raise_on_differences(differences, len(sql_scores))

    # Guard against a vacuous comparison: the generated data must exercise both
    # boundaries of the score range and at least one fractional score.
    values = list(sql_scores.values())
    assert min(values) >= 0 and max(values) <= 100
    assert 0 in values, "generated data produced no zero score"
    assert 100 in values, "generated data produced no perfect score"
    assert any(0 < value < 100 for value in values), (
        "generated data produced no intermediate (floor) score"
    )


def test_sql_oracle_goes_red_on_a_corrupted_score(
    client, account, engine, clean_tables, fast_registration
):
    """Self-check: a one-point SQL deviation must be detected and printed.

    The corruption exists only in a local dictionary; production code and the
    SQL statement stay untouched.  The uncorrupted comparison first proves the
    same helper accepts agreeing tables, so the red result is meaningful.
    """

    candidate_specs = [
        ("Self Check A", ["Python", "SQL"]),
        ("Self Check B", []),
    ]
    job_specs = [
        ("Self Check Role", ["Python", "SQL"]),
        ("Self Check Empty", []),
    ]
    candidates, jobs, expected_candidate_skills, expected_job_skills = _populate(
        client, account, candidate_specs, job_specs
    )
    candidate_skills, job_skills = _read_stored_skills(engine)
    _assert_stored_normalised(
        candidate_skills, expected_candidate_skills, "candidate_skill"
    )
    _assert_stored_normalised(job_skills, expected_job_skills, "job_skill")

    sql_scores = _sql_scores(engine)
    python_scores = _python_scores(candidates, jobs, candidate_skills, job_skills)
    differences = _differences(
        sql_scores, python_scores, candidate_skills, job_skills
    )
    _raise_on_differences(differences, len(sql_scores))

    corrupted = dict(sql_scores)
    key = sorted(corrupted)[0]
    corrupted[key] = (corrupted[key] + 1) % 101
    corrupted_differences = _differences(
        corrupted, python_scores, candidate_skills, job_skills
    )
    assert len(corrupted_differences) == 1, (
        "corrupting exactly one SQL score must yield exactly one mismatch, "
        f"got {corrupted_differences!r}"
    )
    with pytest.raises(AssertionError, match="disagree"):
        _raise_on_differences(corrupted_differences, len(corrupted))
