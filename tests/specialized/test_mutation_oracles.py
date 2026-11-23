from datetime import datetime, timedelta, timezone
import pytest


@pytest.mark.parametrize(
    "candidate,required,expected",
    [
        (["python", "sql"], ["python", "sql", "rust"], 66),
        (["rust"], ["python", "sql"], 0),
        (["anything"], [], 100),
        ([" PYTHON "], ["python"], 100),
    ],
)
def test_independent_score_witnesses(candidate, required, expected):
    from app.employer.matching import match_score

    assert match_score(candidate, required) == expected


def test_slot_exact_cutoff_is_rejected(client, account, snapshot):
    actor = account()
    before = snapshot()
    r = client.post(
        "/employer/interview-slots",
        headers=actor["headers"],
        json={"starts_at": "2030-05-01T00:00:00Z"},
    )
    assert r.status_code == 422 and snapshot() == before


def test_created_slot_is_exactly_thirty_minutes(client, account):
    actor = account()
    r = client.post(
        "/employer/interview-slots",
        headers=actor["headers"],
        json={"starts_at": "2030-05-02T00:00:00Z"},
    )
    assert r.status_code == 201
    data = r.json()
    parse = lambda x: datetime.fromisoformat(x.replace("Z", "+00:00"))
    assert parse(data["ends_at"]) - parse(data["starts_at"]) == timedelta(minutes=30)


def test_candidate_role_guard_rejects_normal_employer(client, account, snapshot):
    actor = account("employer")
    before = snapshot()
    r = client.get("/candidate/jobs", headers=actor["headers"])
    assert r.status_code == 403 and snapshot() == before


def test_candidate_guard_direct_contract_independent_of_service_guard():
    from fastapi import HTTPException
    from app.users.model import User, Role
    from app.users.service import require_candidate

    normal_employer = User(
        email="synthetic-employer@example.com",
        hashed_password="unused-test-hash",
        role=Role.Employer,
    )
    with pytest.raises(HTTPException) as caught:
        require_candidate(normal_employer)
    assert caught.value.status_code == 403
