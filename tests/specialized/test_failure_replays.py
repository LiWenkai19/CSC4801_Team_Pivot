import traceback

import pytest
from fastapi.testclient import TestClient

from test_replacement_and_text import overlapping_replacements


def prepare(client, account, job, target):
    owner, candidate = account(), account("candidate")
    posting = job(
        owner,
        required_skills=["python", "sql"]
        if target == "candidate-skills"
        else ["legacy"],
    )
    if target == "candidate-skills":
        result = client.patch(
            "/candidate/profile",
            headers=candidate["headers"],
            json={"version": 1, "skills": ["legacy"]},
        )
        assert result.status_code == 200
        path, headers, field, table = (
            "/candidate/profile",
            candidate["headers"],
            "skills",
            "candidate_skill",
        )
    else:
        path, headers, field, table = (
            f"/employer/jobs/{posting['id']}",
            owner["headers"],
            "required_skills",
            "job_skill",
        )
    return candidate, posting, path, headers, field, table


@pytest.mark.parametrize("target", ["candidate-skills", "job-skills"])
@pytest.mark.parametrize("sets_overlap", [False, True])
def test_fresh_database_replacement_replay_and_overlap_neighbor(
    client, account, job, engine, snapshot, evidence, target, sets_overlap
):
    candidate, posting, path, headers, field, table = prepare(
        client, account, job, target
    )
    first, second = (
        (["python", "sql"], ["sql", "rust"]) if sets_overlap else (["python"], ["sql"])
    )
    version = client.get(path, headers=headers).json()["version"]
    results = overlapping_replacements(
        engine, path, headers, field, table, first, second, evidence, version
    )
    got = client.get(
        "/candidate/profile" if target == "candidate-skills" else path, headers=headers
    )
    assert got.status_code == 200
    final = got.json()[field]
    evidence(
        "root-replay",
        {
            "target": target,
            "overlapping_input_sets": sets_overlap,
            "first": first,
            "second": second,
            "statuses": [r.status_code for r in results],
            "final": final,
            "state": snapshot(),
        },
    )
    assert sorted(r.status_code for r in results) == [200, 409], (
        "Normal concurrent replacements must not produce server error: "
        + str([r.status_code for r in results])
    )
    assert final in (sorted(first), sorted(second)), (
        "Final list is neither complete replacement: " + str(final)
    )
    assert got.json()["version"] == version + 1


@pytest.mark.parametrize("target", ["candidate-skills", "job-skills"])
def test_sequential_replacement_control_has_no_union(
    client, account, job, evidence, target
):
    candidate, posting, path, headers, field, table = prepare(
        client, account, job, target
    )
    version = client.get(path, headers=headers).json()["version"]
    for value in (["python"], ["sql"]):
        response = client.patch(path, headers=headers, json={"version": version, field: value})
        assert response.status_code == 200 and response.json()[field] == value, (
            response.text
        )
        assert response.json()["version"] == version + 1
        version += 1
    response = client.get(
        "/candidate/profile" if target == "candidate-skills" else path, headers=headers
    )
    score = client.get(f"/candidate/jobs/{posting['id']}", headers=candidate["headers"])
    assert response.json()[field] == ["sql"]
    assert score.json()["match_score"] == (50 if target == "candidate-skills" else 0)
    evidence(
        "sequential-control",
        {
            "target": target,
            "final": response.json()[field],
            "score": score.json()["match_score"],
        },
    )


@pytest.mark.parametrize(
    "target",
    [
        "candidate-resume",
        "candidate-skill",
        "company-description",
        "job-update-description",
    ],
)
def test_shared_nul_storage_boundary_with_normal_unicode_control(
    client, account, job, snapshot, evidence, target
):
    owner, candidate = account(), account("candidate")
    if target == "candidate-resume":
        path, headers, field = "/candidate/profile", candidate["headers"], "resume_text"
    elif target == "candidate-skill":
        path, headers, field = "/candidate/profile", candidate["headers"], "skills"
    elif target == "company-description":
        path, headers, field = (
            "/employer/company",
            owner["headers"],
            "company_description",
        )
    else:
        posting = job(owner)
        path, headers, field = (
            f"/employer/jobs/{posting['id']}",
            owner["headers"],
            "description",
        )
    ordinary = ["c++", "sql"] if field == "skills" else "普通文本 Résumé 🙂 C++"
    protected = {} if target == "company-description" else {"version": 1}
    normal = client.patch(path, headers=headers, json={**protected, field: ordinary})
    assert normal.status_code == 200, normal.text
    before = snapshot()
    value = ["py\x00thon"] if field == "skills" else "ordinary\x00text"
    protected = {} if target == "company-description" else {"version": normal.json()["version"]}
    bad = client.patch(path, headers=headers, json={**protected, field: value})
    after = snapshot()
    evidence(
        "nul-neighbor",
        {
            "target": target,
            "normal_unicode_status": normal.status_code,
            "nul_status": bad.status_code,
            "response": bad.text,
            "state_unchanged": before == after,
        },
    )
    assert after == before
    assert 400 <= bad.status_code < 500, (
        "Unsupported storage character returned " + str(bad.status_code)
    )


def test_capture_nul_driver_exception_without_changing_application(
    client, account, snapshot, evidence
):
    from app.main import app

    owner = account()
    before = snapshot()
    try:
        with TestClient(app, raise_server_exceptions=True) as diagnostic:
            diagnostic.post(
                "/employer/jobs",
                headers=owner["headers"],
                json={
                    "title": "ordinary\x00text",
                    "description": "Normal description",
                    "required_skills": [],
                },
            )
    except Exception as error:
        details = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }
    else:
        details = None
    evidence(
        "nul-exception", {"exception": details, "state_unchanged": snapshot() == before}
    )
    assert details is not None and (
        "NUL" in details["message"]
        or "0x00" in details["message"]
        or "0x00" in details["traceback"]
    ), details
    assert snapshot() == before
