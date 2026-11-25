import traceback

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

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
    protected = {"version": 1}
    normal = client.patch(path, headers=headers, json={**protected, field: ordinary})
    assert normal.status_code == 200, normal.text
    before = snapshot()
    value = ["py\x00thon"] if field == "skills" else "ordinary\x00text"
    protected = {"version": normal.json()["version"]}
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
    client, account, engine, snapshot, evidence
):
    """保留原诊断入口，修后要求在驱动写入前拒绝，原 DataError 日志留存。"""
    from app.main import app

    owner = account()
    before = snapshot()
    writes = []

    def observe(connection, cursor, statement, parameters, context, many):
        if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            writes.append(statement)

    event.listen(engine, "before_cursor_execute", observe)
    response = None
    try:
        with TestClient(app, raise_server_exceptions=True) as diagnostic:
            response = diagnostic.post(
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
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    evidence(
        "nul-exception", {"exception": details, "state_unchanged": snapshot() == before,
                          "write_attempts": len(writes), "status": response.status_code if response is not None else None}
    )
    assert details is None, details
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "title"]
    assert "NUL" in response.json()["detail"][0]["msg"]
    assert writes == []
    assert snapshot() == before


@pytest.mark.parametrize("target,field", [
    ("candidate-create", "display_name"), ("candidate-create", "resume_text"),
    ("candidate-create", "skills"), ("employer-create", "company_name"),
    ("employer-create", "company_description"), ("candidate-update", "display_name"),
    ("candidate-update", "resume_text"), ("candidate-update", "skills"),
    ("company-update", "company_name"), ("company-update", "company_description"),
    ("job-create", "title"), ("job-create", "description"),
    ("job-create", "required_skills"), ("job-update", "title"),
    ("job-update", "description"), ("job-update", "required_skills"),
])
def test_nul_rejection_is_atomic_and_same_version_accepts_normal_text(
    client, account, job, snapshot, evidence, target, field
):
    """覆盖创建路径、混合字段更新和列表元素；拒绝后原版本仍可正常保存。"""
    role = "candidate" if target.startswith("candidate") else "employer"
    owner = account(role, complete=not target.endswith("create") or target == "job-create")
    if target == "candidate-create":
        path, method = "/users/candidate/profile", "POST"
        payload = {"display_name": "New name", "resume_text": "New résumé", "skills": ["python"]}
    elif target == "employer-create":
        path, method = "/users/employer/profile", "POST"
        payload = {"company_name": "New company", "company_description": "New description"}
    elif target == "candidate-update":
        path, method = "/candidate/profile", "PATCH"
        payload = {"version": 1, "display_name": "Changed name", "resume_text": "Changed résumé", "skills": ["sql"]}
    elif target == "company-update":
        path, method = "/employer/company", "PATCH"
        payload = {"version": 1, "company_name": "Changed company", "company_description": "Changed description"}
    else:
        path, method = "/employer/jobs", "POST"
        payload = {"title": "Changed job", "description": "Changed description", "required_skills": ["sql"]}
        if target == "job-update":
            posting = job(owner)
            path, method = path + "/" + posting["id"], "PATCH"
            payload["version"] = posting["version"]
    bad = dict(payload)
    is_list = field in {"skills", "required_skills"}
    bad[field] = ["python", "prefix\x00suffix", "sql"] if is_list else "prefix\x00suffix"
    before = snapshot()
    rejected = client.request(method, path, headers=owner["headers"], json=bad)
    assert rejected.status_code == 422, rejected.text
    assert rejected.json()["detail"][0]["loc"] == ["body", field] + ([1] if is_list else [])
    assert "NUL" in rejected.json()["detail"][0]["msg"]
    assert snapshot() == before
    ordinary = "Résumé 中文 🙂\nLiteral \\u0000 \x01"
    corrected = dict(payload, **{field: ["python", ordinary, "sql"] if is_list else ordinary})
    saved = client.request(method, path, headers=owner["headers"], json=corrected)
    assert saved.status_code == (201 if method == "POST" else 200), saved.text
    assert saved.json()["version"] == payload.get("version", 0) + 1
    expected = sorted({value.strip().lower() for value in corrected[field]}) if is_list else ordinary.strip() if field in {"display_name", "company_name", "title"} else ordinary
    assert saved.json()[field] == expected
    read_path = (
        "/candidate/profile" if target == "candidate-create" else
        "/employer/company" if target == "employer-create" else
        "/employer/jobs/" + saved.json()["id"] if target == "job-create" else path
    )
    readback = client.get(read_path, headers=owner["headers"])
    assert readback.status_code == 200, readback.text
    assert readback.json()[field] == expected
    assert readback.json()["version"] == saved.json()["version"]
    evidence("nul-atomic-retry", {"target": target, "field": field, "rejected_status": 422,
                                   "retry_status": saved.status_code, "saved_version": saved.json()["version"]})
