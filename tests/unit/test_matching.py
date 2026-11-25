"""FP-MATCH-1及FP-CAN-2：实际评分与两端排序的独立预期。"""

from uuid import UUID

import pytest

from app.candidate import service as candidate
from app.employer import service as employer
from app.employer.matching import match_score
from app.employer.model import Application, ApplicationStatus, Job
from app.users.model import CandidateProfile


@pytest.mark.parametrize(
    "skills,required,expected",
    [
        (["Python", "SQL"], ["Python", "SQL"], 100),
        (["Python"], ["Python", "SQL"], 50),
        (["Rust"], ["Python", "SQL"], 0),
        (["anything"], [], 100),
        (["a", "b"], ["a", "b", "c"], 66),
    ],
)
def test_fp_match_1_examples_normalization_and_floor(skills, required, expected):
    assert match_score(skills, required) == expected
    assert (
        match_score([" " + s.upper() + " " for s in skills] + skills + [""], required)
        == expected
    )


def test_fp_can_2_recommendations_preserve_fields_and_rank_all_jobs(db, actors, result):
    jobs = [
        Job(
            id=UUID(int=i),
            employer_id=actors[1].id,
            title=title,
            description="Description",
        )
        for i, title in [(3, "Zulu"), (2, "alpha"), (1, "Alpha"), (4, "Zero")]
    ]
    db.exec.side_effect = [
        result(rows=[(job, "Company", f"Intro {job.id}", False) for job in jobs]),
        result(rows=[(actors[0].id, "python")]),
        result(rows=[(j.id, "rust" if j.id.int == 4 else "python") for j in jobs]),
    ]
    rows = candidate.list_jobs(db, actors[0])
    assert [row.id.int for row in rows] == [1, 2, 3, 4]
    assert [row.match_score for row in rows] == [100, 100, 100, 0]
    assert all(
        row.company_name == "Company" and row.description == "Description"
        for row in rows
    )
    assert rows[-1].required_skills == ["rust"]
    assert all(row.company_description == f"Intro {row.id}" for row in rows)
    from sqlalchemy.dialects import postgresql

    query = db.exec.call_args_list[0].args[0].compile(dialect=postgresql.dialect())
    assert "is_deleted IS false" in str(query)


def test_fp_match_1_employer_ties_use_name_then_stable_id(
    db, actors, result, monkeypatch
):
    job = Job(employer_id=actors[1].id, title="Job", description="Description")
    profiles = {
        UUID(int=i): CandidateProfile(user_id=UUID(int=i), display_name=name)
        for i, name in [(3, "zoe"), (2, "alice"), (1, "Alice")]
    }
    applications = [Application(candidate_id=i, job_id=job.id) for i in profiles]
    db.get.side_effect = lambda model, ident: job if model is Job else profiles[ident]
    db.exec.side_effect = [
        result(rows=["python"]),
        result(rows=applications),
        *[result(rows=["python"]) for _ in applications],
    ]
    monkeypatch.setattr(employer, "_booking_public", lambda session, ident: None)
    rows = employer.list_job_applicants(db, actors[1], job.id)
    assert [row.candidate_id.int for row in rows] == [1, 2, 3]
    assert all(
        row.match_score == 100 and row.status == ApplicationStatus.Pending
        for row in rows
    )


def test_fp_can_2_empty_jobs_and_missing_profile(db, actors, result):
    db.exec.side_effect = [result(), result(rows=[(actors[0].id, None)])]
    assert candidate.list_jobs(db, actors[0]) == []
    db.exec.side_effect = [result(), result()]
    with pytest.raises(candidate.NotFoundError, match="profile"):
        candidate.list_jobs(db, actors[0])
