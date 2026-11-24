"""版本冲突自身的合同；数据库互斥由真实PG测试覆盖。"""

import pytest
from pydantic import ValidationError

from app.candidate import service as candidate
from app.candidate.schema import ProfileUpdate
from app.employer import service as employer
from app.employer.model import Job
from app.employer.schema import JobUpdate
from app.users.model import CandidateProfile
from app.users.schema import CandidateProfileCreate, EmployerProfileCreate
from app.employer.schema import JobCreate, CompanyUpdate, ApplicationStatusUpdate


@pytest.mark.parametrize(
    "schema,payload",
    [
        (CandidateProfileCreate, {"display_name": "Owner"}),
        (EmployerProfileCreate, {"company_name": "Company"}),
        (JobCreate, {"title": "Job", "description": "Details"}),
    ],
)
def test_creation_version_is_assigned_only_by_the_server(schema, payload):
    with pytest.raises(ValidationError):
        schema(**payload, version=1)


@pytest.mark.parametrize("schema", [ProfileUpdate, JobUpdate, CompanyUpdate, ApplicationStatusUpdate])
@pytest.mark.parametrize("value", [None, 0, -1, True, False, "1", 1.5])
def test_update_version_is_a_strict_positive_integer(schema, value):
    with pytest.raises(ValidationError) as caught:
        schema(version=value, **({"status": "Pending"} if schema is ApplicationStatusUpdate else {}))
    assert caught.value.errors()[0]["loc"] == ("version",)


@pytest.mark.parametrize("schema", [ProfileUpdate, JobUpdate, CompanyUpdate, ApplicationStatusUpdate])
def test_update_cannot_omit_version(schema):
    with pytest.raises(ValidationError) as caught:
        schema(**({"status": "Pending"} if schema is ApplicationStatusUpdate else {}))
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


@pytest.mark.parametrize("target", ["company", "application"])
def test_extended_stale_lock_and_noop_do_not_write(db, actors, result, target):
    from uuid import uuid4
    from app.users.model import EmployerProfile
    from app.employer.model import Application
    if target == "company":
        row = EmployerProfile(user_id=actors[1].id, company_name="Latest", version=2)
        db.exec.return_value = result(first=row)
        def action():
            return employer.update_my_company(db, actors[1], CompanyUpdate(version=1, company_name="Stale"))
    else:
        row = Application(candidate_id=uuid4(), job_id=uuid4(), version=2)
        db.exec.return_value = result(first=row)
        db.get.return_value = Job(id=row.job_id, employer_id=actors[1].id, title="Job", description="Details")
        def action():
            return employer.change_application_status(db, actors[1], row.id, ApplicationStatusUpdate(version=1, status="Rejected"))
    with pytest.raises(employer.ResourceVersionConflictError, match="Resource version conflict"):
        action()
    statement = db.exec.call_args.args[0]
    assert statement._for_update_arg is not None
    assert statement.get_execution_options()["populate_existing"] is True
    assert row.version == 2
    db.add.assert_not_called()
    db.flush.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_company_version_only_is_noop_but_explicit_same_value_increments(db, actors, result):
    from app.users.model import EmployerProfile
    row = EmployerProfile(user_id=actors[1].id, company_name="Company")
    db.exec.return_value = result(first=row)
    assert employer.update_my_company(db, actors[1], CompanyUpdate(version=1)).version == 1
    db.add.assert_not_called()
    db.flush.assert_not_called()
    saved = employer.update_my_company(db, actors[1], CompanyUpdate(version=1, company_name="Company"))
    assert saved.version == row.version == 2
    db.flush.assert_called_once()
