"""新版账户完成状态与候选人业务的共同契约；使用真实路由和隔离数据库。"""

from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.candidate.model import (
    Application,
    ApplicationStatus,
    Booking,
    InterviewSlot,
    Job,
)
from app.users.model import utc_now


def test_registration_profile_edit_recommendation_and_application_contract(flow):
    client = flow["client"]
    credentials = {
        "email": "new-candidate@example.com",
        "password": "test-password",
        "role": "candidate",
    }
    registered = client.post("/users/register", json=credentials)
    assert registered.status_code == 200
    auth = registered.json()
    assert auth["user"]["profile_completed"] is False
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    assert client.get("/candidate/jobs", headers=headers).status_code == 404
    assert (
        client.post(
            "/users/candidate/profile",
            headers=headers,
            json={"display_name": " New ", "skills": [" PYTHON ", "python"]},
        ).status_code
        == 201
    )
    assert client.get("/users/me", headers=headers).json()["profile_completed"] is True
    login = client.post(
        "/users/login", json={k: credentials[k] for k in ("email", "password")}
    ).json()
    assert login["user"]["profile_completed"] is True
    path = f"/users/candidates/{auth['user']['id']}/profile"
    assert (
        client.patch(
            path,
            headers=headers,
            json={"resume_text": "Private\ntext", "skills": ["SQL"]},
        ).status_code
        == 200
    )
    assert client.get(path, headers=headers).json()["resume_text"] == "Private\ntext"
    rows = client.get("/candidate/jobs", headers=headers).json()
    assert [r["title"] for r in rows] == ["Empty", "alpha", "Alpha", "Beta"]
    assert next(r["score"] for r in rows if r["title"] == "alpha") == 50
    response = client.post(
        f"/candidate/jobs/{flow['jobs'][0]}/applications", headers=headers
    )
    assert response.status_code == 201
    application = response.json()
    assert application["status"] == "Pending" and application["booking"] is None
    assert (
        application["title"] == "alpha" and application["company_name"] == "Company A"
    )
    assert client.get("/candidate/applications", headers=headers).json() == [
        application
    ]
    # 清空可选资料不等于删除资料，不能让登录守卫再次强制补填。
    assert (
        client.patch(
            path, headers=headers, json={"resume_text": "", "skills": []}
        ).status_code
        == 200
    )
    assert client.get("/users/me", headers=headers).json()["profile_completed"] is True


@pytest.mark.parametrize("path", ["/candidate/jobs", "/candidate/applications"])
def test_candidate_list_requires_authentication_and_role(flow, path):
    assert flow["client"].get(path).status_code == 401
    assert flow["client"].get(path, headers=flow["headers"][2]).status_code == 403


@pytest.mark.parametrize(
    "payload",
    [{"candidate_id": "injected"}, {"status": "Accepted"}, {"role": "employer"}],
)
def test_application_rejects_client_owned_identity_or_status(flow, payload):
    response = flow["client"].post(
        f"/candidate/jobs/{flow['jobs'][1]}/applications",
        headers=flow["headers"][0],
        json=payload,
    )
    assert response.status_code == 422
    with Session(flow["engine"]) as session:
        assert (
            session.exec(
                select(Application).where(Application.job_id == flow["jobs"][1])
            ).all()
            == []
        )


@pytest.mark.parametrize("minutes", [15, 60])
def test_malformed_slot_is_hidden_and_cannot_be_booked(flow, minutes):
    with Session(flow["engine"]) as session:
        slot = session.get(InterviewSlot, flow["slots"][0])
        slot.ends_at = slot.starts_at + timedelta(minutes=minutes)
        session.add(slot)
        session.commit()
    base = f"/candidate/applications/{flow['applications'][0]}"
    headers = flow["headers"][0]
    assert flow["client"].get(base + "/slots", headers=headers).json() == []
    response = flow["client"].post(
        base + "/booking", headers=headers, json={"slot_id": str(flow["slots"][0])}
    )
    assert response.status_code == 409
    with Session(flow["engine"]) as session:
        assert session.exec(select(Booking)).all() == []


def test_old_slot_and_existing_booking_reject_without_partial_changes(flow):
    with Session(flow["engine"]) as session:
        slot = session.get(InterviewSlot, flow["slots"][0])
        slot.starts_at = utc_now() - timedelta(minutes=10)
        slot.ends_at = slot.starts_at + timedelta(minutes=30)
        session.add(slot)
        session.commit()
    path = f"/candidate/applications/{flow['applications'][0]}/booking"
    response = flow["client"].post(
        path, headers=flow["headers"][0], json={"slot_id": str(flow["slots"][0])}
    )
    assert response.status_code == 409
    with Session(flow["engine"]) as session:
        assert session.exec(select(Booking)).all() == []


def test_existing_application_remains_visible_if_job_hidden_and_all_statuses(flow):
    # 应用只过滤推荐列表；已有申请仍能看到职位、公司和最新状态。
    client, headers = flow["client"], flow["headers"][0]
    with Session(flow["engine"]) as session:
        job = session.get(Job, flow["jobs"][0])
        job.is_deleted = True
        session.add(job)
        session.commit()
    assert (
        client.get(f"/candidate/jobs/{flow['jobs'][0]}", headers=headers).status_code
        == 404
    )
    for status in ApplicationStatus:
        with Session(flow["engine"]) as session:
            application = session.get(Application, flow["applications"][0])
            application.status = status
            session.add(application)
            session.commit()
        rows = client.get("/candidate/applications", headers=headers).json()
        assert rows[0]["status"] == status.value and rows[0]["title"] == "alpha"
