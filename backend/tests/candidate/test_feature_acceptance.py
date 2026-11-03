"""CAN-001～006 的接口权限矩阵、数据约束与跨角色一致性验收。"""
import uuid

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.candidate import service
from app.candidate.model import Application, ApplicationStatus, JobSkill
from app.candidate.schema import BookingPublic


def query_paths(flow):
    return [
        "/users/me",
        f"/users/candidates/{flow['ids'][0]}/profile",
        "/candidate/jobs",
        f"/candidate/jobs/{flow['jobs'][0]}",
        "/candidate/applications",
        f"/candidate/applications/{flow['applications'][0]}",
        f"/candidate/applications/{flow['applications'][0]}/slots",
        f"/employer/jobs/{flow['jobs'][0]}/applications",
    ]


@pytest.mark.parametrize("endpoint", range(8))
@pytest.mark.parametrize("invalid", [False, True])
def test_all_business_queries_require_authentication(flow, endpoint, invalid):
    headers = {"Authorization": "Bearer forged-token"} if invalid else {}
    response = flow["client"].get(query_paths(flow)[endpoint], headers=headers)
    assert response.status_code == 401
    assert "Private" not in response.text


@pytest.mark.parametrize("endpoint", range(8))
@pytest.mark.parametrize("reader,expected", [
    (0, [200, 200, 200, 200, 200, 200, 200, 403]),
    (1, [200, 403, 200, 200, 200, 403, 403, 403]),
    (2, [200, 200, 403, 403, 403, 403, 403, 200]),
    (3, [200, 403, 403, 403, 403, 403, 403, 403]),
])
def test_business_query_role_and_object_scope(flow, endpoint, reader, expected):
    response = flow["client"].get(query_paths(flow)[endpoint], headers=flow["headers"][reader])
    assert response.status_code == expected[endpoint]


@pytest.mark.parametrize("status", list(ApplicationStatus))
def test_duplicate_does_not_reset_status_or_create_another_record(flow, status):
    with Session(flow["engine"]) as session:
        application = session.get(Application, flow["applications"][0])
        application.status = status
        session.add(application)
        session.commit()
    response = flow["client"].post(
        f"/candidate/jobs/{flow['jobs'][0]}/applications", headers=flow["headers"][0], json={},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Already applied"}
    with Session(flow["engine"]) as session:
        rows = session.exec(select(Application).where(
            Application.candidate_id == flow["ids"][0], Application.job_id == flow["jobs"][0],
        )).all()
        assert len(rows) == 1
        assert rows[0].id == flow["applications"][0] and rows[0].status == status


def test_database_uniqueness_cannot_be_bypassed_by_skipping_service(flow):
    with Session(flow["engine"]) as session:
        session.add(Application(candidate_id=flow["ids"][0], job_id=flow["jobs"][0]))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        rows = session.exec(select(Application).where(
            Application.candidate_id == flow["ids"][0], Application.job_id == flow["jobs"][0],
        )).all()
        assert len(rows) == 1


def test_application_isolation_between_candidates_and_jobs(flow):
    client = flow["client"]
    path = f"/candidate/jobs/{flow['jobs'][1]}/applications"
    for reader in [0, 1]:
        assert client.post(path, headers=flow["headers"][reader], json={}).status_code == 201
        assert client.post(path, headers=flow["headers"][reader], json={}).status_code == 409
    other = f"/candidate/jobs/{flow['jobs'][2]}/applications"
    assert client.post(other, headers=flow["headers"][0], json={}).status_code == 201


@pytest.mark.parametrize("status", list(ApplicationStatus))
def test_candidate_and_employer_share_status_and_keep_booking(flow, status):
    client = flow["client"]
    base = f"/candidate/applications/{flow['applications'][0]}"
    booked = client.post(base + "/booking", headers=flow["headers"][0],
                         json={"slot_id": str(flow["slots"][0])})
    assert booked.status_code == 201
    with Session(flow["engine"]) as session:
        application = session.get(Application, flow["applications"][0])
        application.status = status
        session.add(application)
        session.commit()
    candidate = client.get(base, headers=flow["headers"][0]).json()
    rows = client.get(f"/employer/jobs/{flow['jobs'][0]}/applications", headers=flow["headers"][2]).json()
    employer = next(row for row in rows if row["id"] == str(flow["applications"][0]))
    assert candidate["status"] == employer["status"] == status.value
    normalized = [BookingPublic.model_validate(item).model_dump(mode="json")
                  for item in [candidate["booking"], employer["booking"], booked.json()]]
    assert normalized[0] == normalized[1] == normalized[2]
    assert candidate["booking"]["starts_at"].endswith("Z")
    assert "resume_text" not in employer and "hashed_password" not in employer


@pytest.mark.parametrize("target", ["profile", "application", "job", "employer_job"])
def test_missing_and_invalid_identifiers_do_not_return_business_data(flow, target):
    paths = {
        "profile": "/users/candidates/{}/profile", "application": "/candidate/applications/{}",
        "job": "/candidate/jobs/{}", "employer_job": "/employer/jobs/{}/applications",
    }
    reader = 2 if target in {"profile", "employer_job"} else 0
    for identifier, expected in [(str(uuid.uuid4()), 404), ("invalid", 422)]:
        response = flow["client"].get(paths[target].format(identifier), headers=flow["headers"][reader])
        assert response.status_code == expected


def test_recommendation_orders_by_replaceable_score_then_stable_tie(flow, monkeypatch):
    with Session(flow["engine"]) as session:
        session.execute(delete(JobSkill))
        for job_id, skill in zip(flow["jobs"][:3], ["rust", "java", "python"], strict=True):
            session.add(JobSkill(job_id=job_id, name=skill))
        session.commit()
    def scoring(candidate, required):
        assert candidate == ["python", "sql"]
        return {("rust",): 75, ("java",): 95, ("python",): 95, (): 20}[tuple(required)]
    monkeypatch.setattr(service, "match_score", scoring)
    response = flow["client"].get("/candidate/jobs", headers=flow["headers"][0])
    assert response.status_code == 200
    rows = response.json()
    assert [row["score"] for row in rows] == [95, 95, 75, 20]
    assert [row["id"] for row in rows] == [str(flow["jobs"][i]) for i in [1, 2, 0, 3]]


def test_placeholder_recommendations_keep_fields_and_applied_flags(flow):
    rows = flow["client"].get("/candidate/jobs", headers=flow["headers"][0]).json()
    assert [row["id"] for row in rows] == [str(job) for job in flow["jobs"][:4]]
    assert all(row["score"] == 0 and row["score_kind"] == "placeholder" for row in rows)
    assert rows[0]["applied"] is True and rows[1]["applied"] is False
    assert all({"title", "description", "company_name", "required_skills"} <= row.keys() for row in rows)


def test_tag_values_normalize_persist_and_do_not_alias_java_to_javascript(flow):
    client = flow["client"]
    path = f"/users/candidates/{flow['ids'][0]}/profile"
    response = client.patch(path, headers=flow["headers"][0], json={
        "skills": [" Java ", "JAVA", "JavaScript", " C++ ", "C#", "Node.js", "自定义技能", "  "],
    })
    assert response.status_code == 200
    expected = ["c#", "c++", "java", "javascript", "node.js", "自定义技能"]
    assert response.json()["skills"] == expected
    assert client.get(path, headers=flow["headers"][0]).json()["skills"] == expected
    assert client.get(path, headers=flow["headers"][2]).json()["skills"] == expected
    assert client.patch(path, headers=flow["headers"][0], json={"skills": []}).status_code == 200
    assert client.get(path, headers=flow["headers"][0]).json()["skills"] == []
