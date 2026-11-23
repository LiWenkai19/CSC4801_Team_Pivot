"""版本冲突自身的合同；数据库互斥由真实PG测试覆盖。"""

import pytest
from pydantic import ValidationError

from app.candidate import service as candidate
from app.candidate.schema import ProfileUpdate
from app.employer import service as employer
from app.employer.model import Job
from app.employer.schema import JobUpdate
from app.users.model import CandidateProfile
from app.users.schema import CandidateProfileCreate
from app.employer.schema import JobCreate


@pytest.mark.parametrize(
    "schema,payload",
    [
        (CandidateProfileCreate, {"display_name": "Owner"}),
        (JobCreate, {"title": "Job", "description": "Details"}),
    ],
)
def test_creation_version_is_assigned_only_by_the_server(schema, payload):
    with pytest.raises(ValidationError):
        schema(**payload, version=1)


@pytest.mark.parametrize("schema", [ProfileUpdate, JobUpdate])
@pytest.mark.parametrize("value", [None, 0, -1, True, False, "1", 1.5])
def test_update_version_is_a_strict_positive_integer(schema, value):
    with pytest.raises(ValidationError) as caught:
        schema(version=value)
    assert caught.value.errors()[0]["loc"] == ("version",)


@pytest.mark.parametrize("schema", [ProfileUpdate, JobUpdate])
def test_update_cannot_omit_version(schema):
    with pytest.raises(ValidationError) as caught:
        schema()
    assert caught.value.errors()[0]["loc"] == ("version",)


@pytest.mark.parametrize("target", ["candidate", "job"])
def test_stale_version_rejects_before_any_edit(db, actors, result, target):
    if target == "candidate":
        row = CandidateProfile(user_id=actors[0].id, display_name="Latest", version=2)
        db.exec.return_value = result(first=row)

        def action():
            return candidate.update_my_profile(
                db, actors[0], ProfileUpdate(version=1, skills=["sql"])
            )

        error = candidate.ConflictError
    else:
        row = Job(
            employer_id=actors[1].id, title="Latest", description="Details", version=2
        )
        db.exec.return_value = result(first=row)

        def action():
            return employer.update_job(
                db, actors[1], row.id, JobUpdate(version=1, required_skills=["sql"])
            )

        error = employer.JobVersionConflictError
    with pytest.raises(error, match="Resource version conflict"):
        action()
    assert row.version == 2
    db.execute.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


@pytest.mark.parametrize("target", ["candidate", "job"])
def test_version_only_request_is_a_noop(db, actors, result, target):
    if target == "candidate":
        row = CandidateProfile(user_id=actors[0].id, display_name="Owner")
        db.exec.side_effect = [result(first=row), result(rows=["python"])]
        saved = candidate.update_my_profile(db, actors[0], ProfileUpdate(version=1))
    else:
        row = Job(employer_id=actors[1].id, title="Job", description="Details")
        timestamp = row.updated_at
        db.exec.side_effect = [result(first=row), result(rows=["python"])]
        saved = employer.update_job(db, actors[1], row.id, JobUpdate(version=1))
        assert row.updated_at == timestamp
    assert saved.version == 1 and row.version == 1
    db.execute.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_called_once()
