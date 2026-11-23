"""候选人资料/职位的版本契约、真实事务及修后根因邻域。"""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError


@pytest.fixture(params=["candidate", "job"])
def resource(request, client, account, job):
    candidate, candidate_id = account(skills=["python"])
    owner, owner_id = account("employer")
    posting = job(owner)
    is_candidate = request.param == "candidate"
    path = "/candidate/profile" if is_candidate else f"/employer/jobs/{posting['id']}"
    headers = candidate if is_candidate else owner
    response = client.get(path, headers=headers)
    assert response.status_code == 200 and response.json()["version"] == 1
    assert posting["version"] == 1
    return dict(
        kind=request.param,
        path=path,
        headers=headers,
        initial=response.json(),
        field="skills" if is_candidate else "required_skills",
        text_field="resume_text" if is_candidate else "title",
        user_id=candidate_id if is_candidate else owner_id,
        candidate=candidate,
        posting=posting,
    )


def test_version_stale_edit_is_rejected_without_side_effects(client, resource):
    r = resource
    first = client.patch(
        r["path"],
        headers=r["headers"],
        json={"version": 1, r["field"]: ["python", "sql"]},
    )
    assert first.status_code == 200 and first.json()["version"] == 2
    before = client.get(r["path"], headers=r["headers"]).json()
    stale = client.patch(
        r["path"],
        headers=r["headers"],
        json={
            "version": 1,
            r["field"]: ["python", "java"],
            r["text_field"]: "Stale text",
        },
    )
    assert stale.status_code == 409
    assert stale.json() == {"detail": "Resource version conflict"}
    assert client.get(r["path"], headers=r["headers"]).json() == before
    next_save = client.patch(
        r["path"], headers=r["headers"], json={"version": 2, r["field"]: ["sql"]}
    )
    assert next_save.status_code == 200 and next_save.json()["version"] == 3


@pytest.mark.parametrize("version", [None, 0, -1, True, False, "1", 1.5, "missing"])
def test_version_invalid_or_absent_is_not_an_unprotected_write(
    client, resource, version
):
    r = resource
    payload = {r["field"]: ["sql"]}
    if version != "missing":
        payload["version"] = version
    response = client.patch(r["path"], headers=r["headers"], json=payload)
    assert response.status_code == 422
    assert any(
        error["loc"] == ["body", "version"] for error in response.json()["detail"]
    )
    assert client.get(r["path"], headers=r["headers"]).json() == r["initial"]


def test_version_noop_same_value_and_clear_have_explicit_revision_rules(
    client, resource
):
    r = resource
    noop = client.patch(r["path"], headers=r["headers"], json={"version": 1})
    assert noop.status_code == 200 and noop.json() == r["initial"]
    same = client.patch(
        r["path"],
        headers=r["headers"],
        json={"version": 1, r["field"]: r["initial"][r["field"]]},
    )
    assert same.status_code == 200 and same.json()["version"] == 2
    cleared = client.patch(
        r["path"], headers=r["headers"], json={"version": 2, r["field"]: []}
    )
    assert cleared.status_code == 200
    assert cleared.json()["version"] == 3 and cleared.json()[r["field"]] == []
    assert cleared.json()[r["text_field"]] == r["initial"][r["text_field"]]


@pytest.mark.parametrize("initial", [[], ["legacy"]])
@pytest.mark.parametrize(
    "sets",
    [
        (["python"], ["sql"]),
        (["python", "sql"], ["sql", "rust"]),
        ([], ["sql"]),
        (["python"], ["sql"], []),
    ],
)
def test_version_concurrent_replacements_have_one_complete_winner(
    client, resource, initial, sets
):
    from app.main import app

    r = resource
    seeded = client.patch(
        r["path"], headers=r["headers"], json={"version": 1, r["field"]: initial}
    )
    assert seeded.status_code == 200 and seeded.json()["version"] == 2
    barrier = Barrier(len(sets))

    def save(values):
        with TestClient(app) as local:
            barrier.wait(timeout=10)
            return local.patch(
                r["path"], headers=r["headers"], json={"version": 2, r["field"]: values}
            )

    with ThreadPoolExecutor(max_workers=len(sets)) as pool:
        futures = [pool.submit(save, values) for values in sets]
        results = [future.result(timeout=20) for future in futures]
    assert sorted(row.status_code for row in results) == [200] + [409] * (len(sets) - 1)
    winner = next(
        values for values, response in zip(sets, results) if response.status_code == 200
    )
    actual = client.get(r["path"], headers=r["headers"]).json()
    assert actual[r["field"]] == sorted(winner)
    assert actual["version"] == 3
    matched = client.get(
        f"/candidate/jobs/{r['posting']['id']}", headers=r["candidate"]
    )
    assert matched.status_code == 200
    skills, required = (
        (winner, ["python", "sql"])
        if r["kind"] == "candidate"
        else (["python"], winner)
    )
    expected = (
        100 * len(set(skills) & set(required)) // len(set(required))
        if required
        else 100
    )
    assert matched.json()["match_score"] == expected


def test_version_competing_text_and_skill_changes_do_not_silently_overwrite(
    client, resource
):
    r = resource
    changed = client.patch(
        r["path"],
        headers=r["headers"],
        json={"version": 1, r["text_field"]: "New text"},
    )
    assert changed.status_code == 200 and changed.json()["version"] == 2
    refused = client.patch(
        r["path"], headers=r["headers"], json={"version": 1, r["field"]: ["sql"]}
    )
    assert refused.status_code == 409
    assert client.get(r["path"], headers=r["headers"]).json() == changed.json()


def test_version_commit_failure_rolls_back_both_revision_and_content(
    client, resource, db, monkeypatch
):
    from app.candidate.service import update_my_profile
    from app.candidate.schema import ProfileUpdate
    from app.employer.service import update_job
    from app.employer.schema import JobUpdate
    from app.users.model import User

    r = resource
    user = db.get(User, r["user_id"])

    def fail_commit():
        raise SQLAlchemyError("Injected commit failure after flush")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(SQLAlchemyError):
        if r["kind"] == "candidate":
            update_my_profile(
                db,
                user,
                ProfileUpdate(version=1, skills=["sql"], resume_text="Unsaved"),
            )
        else:
            update_job(
                db,
                user,
                uuid.UUID(r["posting"]["id"]),
                JobUpdate(version=1, required_skills=["sql"], title="Unsaved"),
            )
    assert client.get(r["path"], headers=r["headers"]).json() == r["initial"]


def test_version_identity_map_cannot_hide_a_newer_committed_revision(
    client, resource, db
):
    from app.candidate.service import ConflictError, update_my_profile
    from app.candidate.schema import ProfileUpdate
    from app.employer.service import JobVersionConflictError, update_job
    from app.employer.schema import JobUpdate
    from app.users.model import CandidateProfile, User
    from app.employer.model import Job

    r = resource
    user = db.get(User, r["user_id"])
    cached = db.get(
        CandidateProfile if r["kind"] == "candidate" else Job,
        r["user_id"] if r["kind"] == "candidate" else uuid.UUID(r["posting"]["id"]),
    )
    assert cached.version == 1
    saved = client.patch(
        r["path"], headers=r["headers"], json={"version": 1, r["field"]: ["sql"]}
    )
    assert saved.status_code == 200 and saved.json()["version"] == 2
    with pytest.raises(
        (ConflictError, JobVersionConflictError), match="Resource version conflict"
    ):
        if r["kind"] == "candidate":
            update_my_profile(db, user, ProfileUpdate(version=1, skills=["rust"]))
        else:
            update_job(
                db, user, cached.id, JobUpdate(version=1, required_skills=["rust"])
            )
    assert client.get(r["path"], headers=r["headers"]).json() == saved.json()


def test_version_success_response_is_not_reassembled_after_commit(
    client, resource, db, monkeypatch
):
    from app.candidate.service import update_my_profile
    from app.candidate.schema import ProfileUpdate
    from app.employer.service import update_job
    from app.employer.schema import JobUpdate
    from app.users.model import User

    r = resource
    original_commit = db.commit

    def commit_then_another_save():
        original_commit()
        later = client.patch(
            r["path"],
            headers=r["headers"],
            json={"version": 2, r["text_field"]: "Later"},
        )
        assert later.status_code == 200 and later.json()["version"] == 3

    monkeypatch.setattr(db, "commit", commit_then_another_save)
    user = db.get(User, r["user_id"])
    if r["kind"] == "candidate":
        response = update_my_profile(
            db, user, ProfileUpdate(version=1, resume_text="First")
        )
    else:
        response = update_job(
            db, user, uuid.UUID(r["posting"]["id"]), JobUpdate(version=1, title="First")
        )
    assert response.version == 2
    assert getattr(response, r["text_field"]) == "First"
    assert client.get(r["path"], headers=r["headers"]).json()["version"] == 3


@pytest.mark.parametrize("target", ["candidate", "job"])
def test_version_cannot_be_supplied_on_creation(client, account, target):
    if target == "candidate":
        headers, _ = account(complete=False)
        response = client.post(
            "/users/candidate/profile",
            headers=headers,
            json={"display_name": "Owner", "version": 99},
        )
        assert response.status_code == 422
        assert client.get("/candidate/profile", headers=headers).status_code == 404
    else:
        headers, _ = account("employer")
        response = client.post(
            "/employer/jobs",
            headers=headers,
            json={"title": "Job", "description": "Details", "version": 99},
        )
        assert response.status_code == 422
        assert client.get("/employer/jobs", headers=headers).json() == []


def test_version_does_not_override_authorization_or_missing_resource_errors(
    client, resource, account
):
    r = resource
    payload = {"version": 999, r["field"]: ["sql"]}
    assert client.patch(r["path"], json=payload).status_code == 401
    wrong_role, _ = account("employer" if r["kind"] == "candidate" else "candidate")
    assert client.patch(r["path"], headers=wrong_role, json=payload).status_code == 403
    if r["kind"] == "candidate":
        incomplete, _ = account(complete=False)
        assert (
            client.patch(r["path"], headers=incomplete, json=payload).status_code == 404
        )
    else:
        outsider, _ = account("employer")
        assert (
            client.patch(r["path"], headers=outsider, json=payload).status_code == 403
        )
        assert (
            client.patch(
                f"/employer/jobs/{uuid.uuid4()}", headers=r["headers"], json=payload
            ).status_code
            == 404
        )
