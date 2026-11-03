"""通过真实认证及隔离数据库验证简历读取和修改权限。"""
import uuid
from datetime import timedelta

import jwt
import pytest
from sqlalchemy import delete
from sqlmodel import Session

from app.candidate.model import Application, ApplicationStatus, Job
from app.core.config import settings
from app.users.model import CandidateProfile, User, utc_now


@pytest.mark.parametrize("reader", [0, 2])
def test_owner_and_applied_employer_read_only_public_fields(flow, reader):
    response = flow["client"].get(
        f"/users/candidates/{flow['ids'][0]}/profile",
        headers=flow["headers"][reader],
    )
    assert response.status_code == 200
    assert response.json() == {
        "user_id": str(flow["ids"][0]), "display_name": "Alice",
        "resume_text": "Private\nResume", "skills": ["python", "sql"],
    }


@pytest.mark.parametrize("editor", [1, 2, 3])
def test_other_candidates_and_employers_cannot_modify(flow, editor):
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    response = flow["client"].patch(
        path, headers=flow["headers"][editor],
        json={"resume_text": "overwritten", "display_name": "attacker", "skills": []},
    )
    assert response.status_code == 403
    with Session(flow["engine"]) as session:
        profile = session.get(CandidateProfile, flow["ids"][0])
        assert profile.resume_text == "Private\nResume"
        assert profile.display_name == "Alice"
        assert sorted(s.name for s in profile.skills) == ["python", "sql"]


def test_owner_update_and_clear_visible_to_employer(flow):
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    text = '<script>alert(1)</script>\n中文简历\n  保留空白  '
    for value in [text, ""]:
        response = flow["client"].patch(
            path, headers=flow["headers"][0], json={"resume_text": value},
        )
        assert response.status_code == 200
        assert flow["client"].get(path, headers=flow["headers"][2]).json()["resume_text"] == value
        with Session(flow["engine"]) as session:
            assert session.get(CandidateProfile, flow["ids"][0]).resume_text == value


@pytest.mark.parametrize("target", ["unknown", "employer", "incomplete"])
def test_employer_read_missing_or_non_candidate_returns_404(flow, target):
    candidate_id = uuid.uuid4() if target != "employer" else flow["ids"][2]
    if target == "incomplete":
        with Session(flow["engine"]) as session:
            session.add(User(id=candidate_id, email="incomplete@example.com",
                             hashed_password="unused", role="candidate"))
            session.commit()
    response = flow["client"].get(
        f"/users/candidates/{candidate_id}/profile", headers=flow["headers"][2],
    )
    assert response.status_code == 404


@pytest.mark.parametrize("method", ["get", "patch"])
@pytest.mark.parametrize("token_kind", ["missing", "invalid", "expired", "deleted_user"])
def test_resume_requires_valid_existing_account(flow, method, token_kind):
    headers = {}
    if token_kind != "missing":
        token = "not-a-jwt"
        if token_kind in {"expired", "deleted_user"}:
            token = jwt.encode(
                {"sub": "user0@example.com" if token_kind == "expired" else "gone@example.com",
                 "exp": utc_now() + timedelta(minutes=-1 if token_kind == "expired" else 5)},
                settings.SECRET_KEY, algorithm=settings.ALGORITHM,
            )
        headers = {"Authorization": f"Bearer {token}"}
    kwargs = {"json": {"resume_text": "bad"}} if method == "patch" else {}
    response = getattr(flow["client"], method)(
        f"/users/candidates/{flow['ids'][0]}/profile", headers=headers, **kwargs,
    )
    assert response.status_code == 401


@pytest.mark.parametrize("payload", [
    {"user_id": "someone-else", "resume_text": "bad"},
    {"candidate_id": "someone-else"}, {"role": "employer"},
    {"resume_text": None}, {"resume_text": 123},
])
def test_owner_cannot_inject_identity_or_invalid_resume(flow, payload):
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    response = flow["client"].patch(path, headers=flow["headers"][0], json=payload)
    assert response.status_code == 422
    assert flow["client"].get(path, headers=flow["headers"][2]).json()["resume_text"] == "Private\nResume"


def test_invalid_candidate_identifier(flow):
    response = flow["client"].get(
        "/users/candidates/not-a-uuid/profile", headers=flow["headers"][2],
    )
    assert response.status_code == 422


def test_unrelated_employer_cannot_read_resume(flow):
    response = flow["client"].get(
        f"/users/candidates/{flow['ids'][0]}/profile", headers=flow["headers"][3],
    )
    assert response.status_code == 403
    assert "resume_text" not in response.json()
    assert "Private" not in response.text


def test_no_application_denies_employer_but_owner_can_still_read(flow):
    with Session(flow["engine"]) as session:
        session.execute(delete(Application).where(Application.candidate_id == flow["ids"][0]))
        session.commit()
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    assert flow["client"].get(path, headers=flow["headers"][2]).status_code == 403
    assert flow["client"].get(path, headers=flow["headers"][0]).status_code == 200


@pytest.mark.parametrize("status", list(ApplicationStatus))
def test_application_status_does_not_remove_read_permission(flow, status):
    with Session(flow["engine"]) as session:
        application = session.get(Application, flow["applications"][0])
        application.status = status
        session.add(application)
        session.commit()
    response = flow["client"].get(
        f"/users/candidates/{flow['ids'][0]}/profile", headers=flow["headers"][2],
    )
    assert response.status_code == 200


def test_permission_uses_current_job_owner_and_existing_application(flow):
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    with Session(flow["engine"]) as session:
        job = session.get(Job, flow["jobs"][0])
        job.employer_id = flow["ids"][3]
        session.add(job)
        session.commit()
    assert flow["client"].get(path, headers=flow["headers"][2]).status_code == 403
    assert flow["client"].get(path, headers=flow["headers"][3]).status_code == 200


def test_soft_deleted_job_keeps_historical_application_access(flow):
    with Session(flow["engine"]) as session:
        job = session.get(Job, flow["jobs"][0])
        job.is_deleted = True
        session.add(job)
        session.commit()
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    assert flow["client"].get(path, headers=flow["headers"][2]).status_code == 200
    assert flow["client"].get(path, headers=flow["headers"][3]).status_code == 403
