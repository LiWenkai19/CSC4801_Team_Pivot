"""FP-CAN-1：资料、纯文本持久化及投递关系授权。"""

import uuid

import pytest


def test_profile_failed_commit_rolls_back_text_and_skills(
    client, account, db, monkeypatch
):
    """提交失败时不能只保存简历或只替换技能。"""
    from sqlalchemy.exc import SQLAlchemyError
    from app.candidate import service
    from app.candidate.schema import ProfileUpdate
    from app.users.model import User

    candidate, candidate_id = account(skills=["python"])
    before = client.get("/candidate/profile", headers=candidate).json()
    user = db.get(User, candidate_id)

    def fail_commit():
        raise SQLAlchemyError("Injected commit failure")

    monkeypatch.setattr(db, "commit", fail_commit)
    with pytest.raises(SQLAlchemyError):
        service.update_my_profile(
            db, user, ProfileUpdate(resume_text="unsaved", skills=["sql"])
        )
    assert client.get("/candidate/profile", headers=candidate).json() == before


def test_profile_patch_persists_and_preserves_omitted_fields(client, account):
    candidate, _ = account(skills=[" PYTHON ", "python", " "])
    initial = client.get("/candidate/profile", headers=candidate).json()
    assert initial["skills"] == ["python"]
    text = "  中文\n<script>alert(1)</script>\n' ; DROP TABLE job; --  "
    updated = client.patch(
        "/candidate/profile", headers=candidate, json={"resume_text": text}
    )
    assert updated.status_code == 200
    assert updated.json() == initial | {"resume_text": text}
    assert (
        client.get("/candidate/profile", headers=candidate).json()["resume_text"]
        == text
    )
    changed = client.patch(
        "/candidate/profile",
        headers=candidate,
        json={"display_name": " Alice ", "skills": [" SQL ", "sql", "PYTHON", ""]},
    )
    assert changed.json()["skills"] == ["python", "sql"]
    assert changed.json()["display_name"] == "Alice"
    assert changed.json()["resume_text"] == text
    empty = client.patch(
        "/candidate/profile", headers=candidate, json={"resume_text": "", "skills": []}
    )
    assert empty.json()["resume_text"] == "" and empty.json()["skills"] == []
    assert (
        client.patch("/candidate/profile", headers=candidate, json={}).json()
        == empty.json()
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": " "},
        {"display_name": None},
        {"resume_text": None},
        {"skills": None},
        {"skills": "python"},
        {"skills": [1]},
        {"resume_text": 5},
        {"user_id": str(uuid.uuid4())},
        {"role": "employer"},
    ],
)
def test_profile_invalid_patch_is_atomic(client, account, payload):
    candidate, _ = account()
    initial = client.get("/candidate/profile", headers=candidate).json()
    assert (
        client.patch("/candidate/profile", headers=candidate, json=payload).status_code
        == 422
    )
    assert client.get("/candidate/profile", headers=candidate).json() == initial


def test_profile_permission_matrix(client, account, job):
    candidate, candidate_id = account()
    other, _ = account()
    employer, _ = account("employer")
    outsider, _ = account("employer")
    path = f"/candidate/profiles/{candidate_id}"
    assert client.get(path).status_code == 401
    assert (
        client.get(path, headers={"Authorization": "Bearer invalid"}).status_code == 401
    )
    assert client.get(path, headers=other).status_code == 403
    assert client.get(path, headers=employer).status_code == 403
    posting = job(employer)
    application = client.post(
        f"/candidate/jobs/{posting['id']}/applications", headers=candidate
    ).json()
    for state in ["Pending", "Interviewing", "Rejected", "Accepted"]:
        assert (
            client.patch(
                f"/employer/applications/{application['application_id']}/status",
                headers=employer,
                json={"status": state},
            ).status_code
            == 200
        )
        response = client.get(path, headers=employer)
        assert response.status_code == 200
        assert set(response.json()) == {
            "user_id",
            "display_name",
            "resume_text",
            "skills",
        }
    assert client.get(path, headers=outsider).status_code == 403
    assert (
        client.patch(
            "/candidate/profile", headers=employer, json={"resume_text": "stolen"}
        ).status_code
        == 403
    )
    assert client.get("/candidate/profile", headers=employer).status_code == 403
    assert (
        client.get(f"/candidate/profiles/{uuid.uuid4()}", headers=other).status_code
        == 403
    )
    incomplete, incomplete_id = account(complete=False)
    assert client.get("/candidate/profile", headers=incomplete).status_code == 404
    assert (
        client.get(
            f"/candidate/profiles/{incomplete_id}", headers=incomplete
        ).status_code
        == 404
    )
