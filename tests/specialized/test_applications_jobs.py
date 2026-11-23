from datetime import timedelta
import uuid

import pytest
from sqlalchemy import text
from conftest import FROZEN

INVALID = [
    {"title": ""},
    {"title": " \t"},
    {"title": None},
    {"title": 7},
    {"description": ""},
    {"description": " \n"},
    {"description": None},
    {"required_skills": None},
    {"required_skills": "python"},
    {"required_skills": [None]},
    {"required_skills": [7]},
    {"is_deleted": True},
]


@pytest.mark.parametrize("fields", INVALID)
@pytest.mark.parametrize("operation", ["create", "update"])
def test_invalid_job_inputs_are_rejected_without_partial_writes(
    client, account, job, snapshot, fields, operation
):
    owner = account()
    posting = job(owner)
    before = snapshot()
    if operation == "create":
        body = {
            "title": "Valid title",
            "description": "Valid description",
            "required_skills": ["python"],
        } | fields
        result = client.post("/employer/jobs", headers=owner["headers"], json=body)
    else:
        result = client.patch(
            f"/employer/jobs/{posting['id']}", headers=owner["headers"], json=fields
        )
    assert result.status_code == 422, result.text
    assert snapshot() == before


def test_job_update_omission_clear_and_normalized_replacement(
    client, account, job, snapshot
):
    owner = account()
    posting = job(
        owner,
        title="  Trimmed title  ",
        description="  Preserve description whitespace  ",
        required_skills=[" Python ", "SQL", "sql", ""],
    )
    assert (
        posting["title"] == "Trimmed title"
        and posting["description"] == "  Preserve description whitespace  "
    )
    assert posting["required_skills"] == ["python", "sql"]
    changed = client.patch(
        f"/employer/jobs/{posting['id']}",
        headers=owner["headers"],
        json={"title": "Renamed"},
    )
    assert (
        changed.status_code == 200
        and changed.json()["required_skills"] == posting["required_skills"]
    )
    assert changed.json()["description"] == posting["description"]
    cleared = client.patch(
        f"/employer/jobs/{posting['id']}",
        headers=owner["headers"],
        json={"required_skills": []},
    )
    assert cleared.status_code == 200 and cleared.json()["required_skills"] == []
    assert snapshot()["job_skill"] == []
    reread = client.get(f"/employer/jobs/{posting['id']}", headers=owner["headers"])
    assert reread.status_code == 200 and reread.json() == cleared.json()


@pytest.mark.parametrize(
    "applications,slots", [(False, False), (True, False), (False, True), (True, True)]
)
def test_job_delete_dependency_truth_table_preserves_full_state(
    client,
    account,
    job,
    add_applicant,
    insert_slot,
    engine,
    snapshot,
    applications,
    slots,
):
    owner = account()
    posting = job(owner)
    if applications:
        add_applicant(owner, posting["id"], status="Pending")
    if slots:
        identifier = insert_slot(owner, FROZEN + timedelta(days=1))
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE interview_slot SET job_id=:job WHERE id=:slot"),
                {"job": uuid.UUID(posting["id"]), "slot": uuid.UUID(identifier)},
            )
    before = snapshot()
    result = client.delete(f"/employer/jobs/{posting['id']}", headers=owner["headers"])
    if applications or slots:
        assert result.status_code == 409, result.text
        assert snapshot() == before
    else:
        assert result.status_code == 204 and result.content == b""
        assert snapshot()["job"][0]["is_deleted"] is True
        assert (
            client.get(
                f"/employer/jobs/{posting['id']}", headers=owner["headers"]
            ).status_code
            == 404
        )


def test_shared_unbound_slot_survives_deleting_independent_job(
    client, account, job, create_slot, snapshot
):
    owner = account()
    posting = job(owner)
    slot = create_slot(owner)
    before = snapshot()
    result = client.delete(f"/employer/jobs/{posting['id']}", headers=owner["headers"])
    assert result.status_code == 204, result.text
    after = snapshot()
    assert (
        after["interview_slot"] == before["interview_slot"]
        and after["interview_slot"][0]["id"] == slot["id"]
    )


@pytest.mark.parametrize("state", ["Pending", "Interviewing", "Rejected", "Accepted"])
def test_duplicate_application_in_every_state_preserves_all_related_tables(
    client, account, job, snapshot, state
):
    owner, candidate = account(), account("candidate")
    posting = job(owner)
    path = f"/candidate/jobs/{posting['id']}/applications"
    first = client.post(path, headers=candidate["headers"], json={})
    assert first.status_code == 201 and first.json()["status"] == "Pending"
    changed = client.patch(
        f"/employer/applications/{first.json()['application_id']}/status",
        headers=owner["headers"],
        json={"status": state},
    )
    assert changed.status_code == 200 and changed.json()["status"] == state
    before = snapshot()
    duplicate = client.post(path, headers=candidate["headers"])
    assert (
        duplicate.status_code == 409 and duplicate.json()["detail"] == "Already applied"
    )
    assert snapshot() == before and len(before["application"]) == 1


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("extra-status", 422),
        ("extra-owner", 422),
        ("extra-job", 422),
        ("missing-job", 404),
        ("deleted-job", 404),
        ("bad-id", 422),
    ],
)
def test_application_input_and_target_rejections_are_atomic(
    client, account, job, snapshot, kind, expected
):
    owner, candidate = account(), account("candidate")
    posting = job(owner)
    body = {}
    identifier = posting["id"]
    if kind == "extra-status":
        body = {"status": "Accepted"}
    if kind == "extra-owner":
        body = {"candidate_id": candidate["id"]}
    if kind == "extra-job":
        body = {"job_id": identifier}
    if kind == "missing-job":
        identifier = str(uuid.UUID(int=99999))
    if kind == "bad-id":
        identifier = "ordinary-invalid-job-id"
    if kind == "deleted-job":
        assert (
            client.delete(
                f"/employer/jobs/{identifier}", headers=owner["headers"]
            ).status_code
            == 204
        )
    before = snapshot()
    result = client.post(
        f"/candidate/jobs/{identifier}/applications",
        headers=candidate["headers"],
        json=body,
    )
    assert result.status_code == expected, result.text
    assert snapshot() == before


@pytest.mark.parametrize("action", ["read", "edit", "delete", "applicants"])
def test_job_owner_boundaries_preserve_data(client, account, job, snapshot, action):
    owner, other = account(), account()
    posting = job(owner)
    path = f"/employer/jobs/{posting['id']}"
    before = snapshot()
    if action == "read":
        result = client.get(path, headers=other["headers"])
    elif action == "edit":
        result = client.patch(
            path, headers=other["headers"], json={"title": "Other employer edit"}
        )
    elif action == "delete":
        result = client.delete(path, headers=other["headers"])
    else:
        result = client.get(path + "/applications", headers=other["headers"])
    assert result.status_code == 403, result.text
    assert snapshot() == before


def test_application_history_order_and_deleted_job_fields_are_preserved(
    client, account, job, engine, snapshot
):
    owner, candidate = account(), account("candidate")
    fixed = []
    for index in range(3):
        posting = job(owner, title="Job " + str(index))
        result = client.post(
            f"/candidate/jobs/{posting['id']}/applications",
            headers=candidate["headers"],
            json={},
        )
        assert result.status_code == 201
        identifier = str(uuid.UUID(int=500 + index))
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE application SET id=:new,created_at=:created WHERE id=:old"
                ),
                {
                    "new": uuid.UUID(identifier),
                    "old": uuid.UUID(result.json()["application_id"]),
                    "created": FROZEN + timedelta(seconds=1 if index == 2 else 0),
                },
            )
            if index == 0:
                connection.execute(
                    text("UPDATE job SET is_deleted=true WHERE id=:id"),
                    {"id": uuid.UUID(posting["id"])},
                )
        fixed.append((identifier, posting["id"]))
    before = snapshot()
    result = client.get("/candidate/applications", headers=candidate["headers"])
    assert result.status_code == 200, result.text
    assert [r["application_id"] for r in result.json()] == [
        fixed[2][0],
        fixed[0][0],
        fixed[1][0],
    ]
    assert (
        result.json()[1]["job_title"] == "Job 0"
        and result.json()[1]["company_name"] == "Audit company"
    )
    assert (
        result.json()[1]["booking"] is None and result.json()[1]["status"] == "Pending"
    )
    assert snapshot() == before
