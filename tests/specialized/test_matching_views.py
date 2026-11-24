import uuid

import pytest
from sqlmodel import Session

from test_matching_oracles import oracle


@pytest.mark.parametrize("reverse", [False, True])
def test_candidate_full_order_and_membership_are_independently_precomputed(
    client, account, engine, reverse
):
    from app.employer.model import Job, JobSkill

    one, two, candidate = account(), account(), account("candidate")
    for owner, name in ((one, "Company One"), (two, "Company Two")):
        assert (
            client.patch(
                "/employer/company",
                headers=owner["headers"],
                json={"version": 1, "company_name": name},
            ).status_code
            == 200
        )
    assert (
        client.patch(
            "/candidate/profile",
            headers=candidate["headers"],
            json={"version": 1, "skills": ["python", "sql"]},
        ).status_code
        == 200
    )
    fixtures = [
        (1, "same", ["python", "sql"], one, False),
        (2, "Same", ["python", "sql"], two, False),
        (3, "ALPHA", [], one, False),
        (4, "alpha", [], one, False),
        (5, "Zulu", ["python", "sql", "rust"], one, False),
        (6, "Beta", ["python", "rust"], two, False),
        (7, "Zero", ["rust"], one, False),
        (8, "Deleted", [], one, True),
    ]
    with Session(engine) as session:
        for ident, title, skills, owner, deleted in (
            reversed(fixtures) if reverse else fixtures
        ):
            row = Job(
                id=uuid.UUID(int=ident),
                employer_id=uuid.UUID(owner["id"]),
                title=title,
                description="Synthetic fixed-ID job",
                is_deleted=deleted,
            )
            session.add(row)
            session.flush()
            for skill in skills:
                session.add(JobSkill(job_id=row.id, name=skill))
        session.commit()
    expected = sorted(
        [
            (str(uuid.UUID(int=i)), oracle(["python", "sql"], r), title)
            for i, title, r, _, deleted in fixtures
            if not deleted
        ],
        key=lambda row: (-row[1], row[2].lower(), row[0]),
    )
    response = client.get("/candidate/jobs", headers=candidate["headers"])
    assert response.status_code == 200, response.text
    assert [
        (row["id"], row["match_score"], row["title"]) for row in response.json()
    ] == expected
    for row in response.json():
        assert (
            row["company_name"] in {"Company One", "Company Two"}
            and row["description"] == "Synthetic fixed-ID job"
        )


@pytest.mark.parametrize("reverse", [False, True])
def test_employer_applicant_order_uses_fixed_candidate_ids_and_reference_scores(
    client, account, job, engine, reverse
):
    from app.employer.model import Application
    from app.users.model import User, Role, CandidateProfile, CandidateSkill
    from app.users.security import hash_password

    owner = account()
    posting = job(owner, required_skills=["python", "sql", "rust"])
    data = [
        (1101, "Alice", ["python", "sql", "rust"]),
        (1102, "alice", ["python", "sql", "rust"]),
        (1103, "same", ["python", "sql"]),
        (1104, "Same", ["python", "rust"]),
        (1105, "Zoe", ["python"]),
        (1106, "Aardvark", ["ruby"]),
    ]
    hashed = hash_password("synthetic-fixture-not-for-real-use")
    with Session(engine) as session:
        for ident, name, skills in reversed(data) if reverse else data:
            identifier = uuid.UUID(int=ident)
            session.add(
                User(
                    id=identifier,
                    email=f"fixed-{ident}@example.com",
                    hashed_password=hashed,
                    role=Role.Candidate,
                )
            )
            session.flush()
            session.add(
                CandidateProfile(
                    user_id=identifier,
                    display_name=name,
                    resume_text="Synthetic private resume",
                )
            )
            session.flush()
            for skill in skills:
                session.add(CandidateSkill(candidate_id=identifier, name=skill))
            session.add(
                Application(candidate_id=identifier, job_id=uuid.UUID(posting["id"]))
            )
        session.commit()
    expected = sorted(
        [
            (str(uuid.UUID(int=i)), name, oracle(skills, ["python", "sql", "rust"]))
            for i, name, skills in data
        ],
        key=lambda row: (-row[2], row[1].lower(), row[0]),
    )
    response = client.get(
        f"/employer/jobs/{posting['id']}/applications", headers=owner["headers"]
    )
    assert response.status_code == 200, response.text
    assert [
        (r["candidate_id"], r["display_name"], r["match_score"])
        for r in response.json()
    ] == expected
    assert all("resume_text" not in row for row in response.json())


def test_scores_recompute_after_skill_replacement_and_empty_requirements(
    client, account, job, snapshot
):
    owner, candidate = account(), account("candidate")
    posting = job(owner, required_skills=["python", "sql", "rust"])
    applied = client.post(
        f"/candidate/jobs/{posting['id']}/applications",
        headers=candidate["headers"],
        json={},
    )
    assert applied.status_code == 201
    app_before = snapshot()["application"]
    stages = [
        (["python", "sql"], ["python", "sql", "rust"], 66),
        (["python"], ["python", "sql", "rust"], 33),
        (["python"], ["python", "sql"], 50),
        ([], ["python", "sql"], 0),
        ([], [], 100),
    ]
    for version, (skills, required, expected) in enumerate(stages, start=1):
        assert (
            client.patch(
                "/candidate/profile",
                headers=candidate["headers"],
                json={"version": version, "skills": skills},
            ).status_code
            == 200
        )
        assert (
            client.patch(
                f"/employer/jobs/{posting['id']}",
                headers=owner["headers"],
                json={"version": version, "required_skills": required},
            ).status_code
            == 200
        )
        ours = client.get(
            f"/candidate/jobs/{posting['id']}", headers=candidate["headers"]
        )
        theirs = client.get(
            f"/employer/jobs/{posting['id']}/applications", headers=owner["headers"]
        )
        assert ours.status_code == 200 and theirs.status_code == 200
        assert oracle(skills, required) == expected
        assert ours.json()["match_score"] == theirs.json()[0]["match_score"] == expected
        assert (
            ours.json()["applied"] is True and snapshot()["application"] == app_before
        )


@pytest.mark.parametrize("field", ["resume", "job-description", "company-description"])
def test_irrelevant_text_cannot_change_score_or_order(client, account, job, field):
    owner, candidate = account(), account("candidate")
    first = job(owner, title="A", required_skills=["python", "sql"])
    job(owner, title="B", required_skills=[])
    before = client.get("/candidate/jobs", headers=candidate["headers"]).json()
    if field == "resume":
        path, headers, payload = (
            "/candidate/profile",
            candidate["headers"],
            {"resume_text": "Rust SQL Python Go and unrelated resume words"},
        )
    elif field == "job-description":
        path, headers, payload = (
            f"/employer/jobs/{first['id']}",
            owner["headers"],
            {"description": "Rust SQL Python Go and unrelated description"},
        )
    else:
        path, headers, payload = (
            "/employer/company",
            owner["headers"],
            {
                "company_description": "Rust SQL Python Go and unrelated company description"
            },
        )
    payload["version"] = 1
    changed = client.patch(path, headers=headers, json=payload)
    assert changed.status_code == 200, changed.text
    after = client.get("/candidate/jobs", headers=candidate["headers"]).json()
    assert [(r["id"], r["match_score"]) for r in after] == [
        (r["id"], r["match_score"]) for r in before
    ]


def test_normalized_unicode_and_punctuation_skills_persist_and_score_exactly(
    client, account, job
):
    owner, candidate = account(), account("candidate")
    skills = [" C++ ", "SQL", "sql", "机器学习", "ß", "  "]
    required = ["c++", " SQL ", "机器学习", "SS"]
    patched = client.patch(
        "/candidate/profile", headers=candidate["headers"], json={"version": 1, "skills": skills}
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["skills"] == sorted({"c++", "sql", "机器学习", "ß"})
    posting = job(owner, required_skills=required)
    response = client.get(
        f"/candidate/jobs/{posting['id']}", headers=candidate["headers"]
    )
    assert response.status_code == 200
    assert response.json()["match_score"] == oracle(skills, required) == 75
