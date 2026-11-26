"""候选/雇主业务单测；会话替身不模拟数据库并发保证。"""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.candidate import router, service as candidate
from app.candidate.schema import ProfileUpdate
from app.employer import service as employer
from app.employer.model import (
    Application,
    ApplicationStatus,
    Booking,
    InterviewSlot,
    Job,
    JobSkill,
)
from app.employer.schema import (
    ApplicationStatusUpdate,
    CompanyUpdate,
    JobCreate,
    JobUpdate,
)
from app.users.model import CandidateProfile, EmployerProfile
from app.users.schema import CandidateProfileCreate, EmployerProfileCreate


@pytest.mark.parametrize("field,value,location", [
    ("display_name", "\x00Leading", ("display_name",)),
    ("display_name", "Trailing\x00", ("display_name",)),
    ("resume_text", "\x00", ("resume_text",)),
    ("resume_text", " text\x00 ", ("resume_text",)),
    ("skills", ["\x00python", "sql"], ("skills", 0)),
    ("skills", ["python", "sql\x00"], ("skills", 1)),
])
def test_nul_at_text_and_list_boundaries_is_rejected_without_mutating_input(field, value, location):
    payload = {"display_name": "Valid owner", field: value}
    with pytest.raises(ValidationError) as caught:
        CandidateProfileCreate.model_validate(payload)
    assert caught.value.errors()[0]["loc"] == location
    assert "NUL" in caught.value.errors()[0]["msg"]
    assert payload[field] == value


def test_other_controls_and_literal_nul_escape_remain_valid_text():
    text = "Résumé 中文 🙂\nsecond\tline \\u0000 \x01"
    profile = CandidateProfileCreate(display_name="  Owner  ", resume_text=text)
    assert profile.display_name == "Owner"
    assert profile.resume_text == text


@pytest.mark.parametrize("schema,payload,field", [
    (CandidateProfileCreate, {"display_name": "Name"}, "resume_text"),
    (CandidateProfileCreate, {"display_name": "Name"}, "skills"),
    (EmployerProfileCreate, {"company_name": "Company"}, "company_description"),
    (ProfileUpdate, {"version": 1}, "resume_text"),
    (ProfileUpdate, {"version": 1}, "skills"),
    (CompanyUpdate, {"version": 1}, "company_description"),
    (JobCreate, {"title": "Job", "description": "Description"}, "description"),
    (JobCreate, {"title": "Job", "description": "Description"}, "required_skills"),
    (JobUpdate, {"version": 1}, "description"),
    (JobUpdate, {"version": 1}, "required_skills"),
])
@pytest.mark.parametrize("invalid", ["a\ud800b", "a\udfffb", "\ud800\ud800"])
def test_unencodable_surrogates_are_rejected_at_persisted_field(schema, payload, field, invalid):
    supplied = ["python", invalid] if field in {"skills", "required_skills"} else invalid
    data = dict(payload, **{field: supplied})
    with pytest.raises(ValidationError) as caught:
        schema.model_validate(data)
    expected = (field, 1) if isinstance(supplied, list) else (field,)
    assert caught.value.errors()[0]["loc"] == expected
    assert data[field] == supplied


def test_demo_credentials_in_readme_match_seed_source():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    source = ast.parse((root / "backend/scripts/seed_demo.py").read_text(encoding="utf-8"))
    password = next(
        ast.literal_eval(node.value) for node in source.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "DEMO_PASSWORD" for target in node.targets)
    )
    emails = {
        node.value for node in ast.walk(source)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node.value.startswith("demo-") and node.value.endswith("@example.com")
    }
    readme = (root / "README.md").read_text(encoding="utf-8")
    assert len(emails) == 5
    for email in emails:
        assert any(email in line and password in line for line in readme.splitlines())
    assert "LOCAL/DEMO ONLY" in readme


@pytest.mark.parametrize("text", ["\U0001f642", "literal \\ud800", "\ud7ff\ue000\U0010ffff"])
def test_valid_unicode_near_surrogates_roundtrips_unchanged(text):
    import json

    decoded = json.loads(json.dumps(text, ensure_ascii=True))
    created = CandidateProfileCreate(display_name="Owner", resume_text=decoded, skills=[decoded])
    updated = ProfileUpdate(version=1, resume_text=decoded, skills=[decoded])
    company = CompanyUpdate(version=1, company_description=decoded)
    posting = JobCreate(title="Role", description=decoded, required_skills=[decoded])
    assert created.resume_text == updated.resume_text == company.company_description == posting.description == text
    assert created.skills == updated.skills == posting.required_skills == [text]


@pytest.mark.parametrize("schema,payload,field", [
    (CandidateProfileCreate, {"display_name": "Name"}, "display_name"),
    (CandidateProfileCreate, {"display_name": "Name"}, "resume_text"),
    (CandidateProfileCreate, {"display_name": "Name"}, "skills"),
    (EmployerProfileCreate, {"company_name": "Company"}, "company_name"),
    (EmployerProfileCreate, {"company_name": "Company"}, "company_description"),
    (ProfileUpdate, {"version": 1}, "display_name"),
    (ProfileUpdate, {"version": 1}, "resume_text"),
    (ProfileUpdate, {"version": 1}, "skills"),
    (CompanyUpdate, {"version": 1}, "company_name"),
    (CompanyUpdate, {"version": 1}, "company_description"),
    (JobCreate, {"title": "Job", "description": "Description"}, "title"),
    (JobCreate, {"title": "Job", "description": "Description"}, "description"),
    (JobCreate, {"title": "Job", "description": "Description"}, "required_skills"),
    (JobUpdate, {"version": 1}, "title"),
    (JobUpdate, {"version": 1}, "description"),
    (JobUpdate, {"version": 1}, "required_skills"),
])
@pytest.mark.parametrize("bad", [False, True], ids=["unicode-and-literal-escape", "actual-nul"])
def test_persisted_text_distinguishes_nul_from_unicode_and_literal_escape(schema, payload, field, bad):
    value = "prefix\x00suffix" if bad else "Résumé 中文 🙂\n\\u0000"
    supplied = ["python", value] if field in {"skills", "required_skills"} else value
    data = {**payload, field: supplied}
    if bad:
        with pytest.raises(ValidationError) as caught:
            schema.model_validate(data)
        assert caught.value.errors()[0]["loc"][0] == field
    else:
        assert getattr(schema.model_validate(data), field) == supplied


def test_fp_can_1_profile_read_and_partial_replace(db, actors, result):
    profile = CandidateProfile(
        user_id=actors[0].id, display_name="Original", resume_text="Old resume"
    )
    db.get.return_value = profile
    db.exec.return_value = result(rows=["python"])
    initial = candidate.get_my_profile(db, actors[0])
    assert initial.resume_text == "Old resume" and initial.skills == ["python"]
    db.exec.side_effect = [result(first=profile), result(rows=["python"])]
    changed = candidate.update_my_profile(
        db, actors[0], ProfileUpdate(version=1, resume_text="New\nRésumé 中文")
    )
    assert (
        changed.resume_text == "New\nRésumé 中文" and changed.display_name == "Original"
    )
    assert changed.skills == ["python"]
    assert initial.version == 1 and changed.version == 2
    db.commit.assert_called_once()


def test_fp_can_1_skill_replace_normalizes_input(db, actors, result):
    profile = CandidateProfile(user_id=actors[0].id, display_name="Original")
    db.get.return_value = profile
    db.exec.side_effect = [result(first=profile), result(rows=["python", "sql"])]
    candidate.update_my_profile(
        db, actors[0], ProfileUpdate(version=1, skills=[" SQL ", "python", "PYTHON", ""])
    )
    added = [call.args[0] for call in db.add.call_args_list]
    assert sorted(row.name for row in added if hasattr(row, "name")) == [
        "python",
        "sql",
    ]
    assert db.execute.call_args.args[0].table.name == "candidate_skill"


@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": " "},
        {"skills": None},
        {"resume_text": None},
        {"user_id": str(uuid4())},
    ],
)
def test_fp_can_1_invalid_profile_update(payload):
    with pytest.raises(ValidationError):
        ProfileUpdate(version=1, **payload)


def test_fp_sec_1_other_candidate_cannot_read_resume(db, actors):
    with pytest.raises(candidate.ForbiddenError):
        candidate.read_profile(db, actors[0], uuid4())
    db.get.assert_not_called()
    db.exec.assert_not_called()


def test_fp_can_1_course_resume_privacy_includes_related_employer(db, actors, result):
    """课程 FP-CAN-1：简历私有，有投递关系的雇主直接读取也必须 403。"""
    owner_id = uuid4()
    db.exec.side_effect = [result(first=uuid4()), result(rows=["python"])]
    db.get.return_value = CandidateProfile(
        user_id=owner_id, display_name="Owner", resume_text="Private"
    )
    with pytest.raises(candidate.ForbiddenError):
        candidate.read_profile(db, actors[1], owner_id)


@pytest.mark.parametrize("exists", [False, True])
def test_fp_can_3_pending_duplicate_and_application_owner(
    db, actors, result, monkeypatch, exists
):
    profile = CandidateProfile(user_id=actors[0].id, display_name="Owner")
    job = Job(employer_id=actors[1].id, title="Job", description="Description")
    db.get.return_value = profile
    db.exec.side_effect = [result(first=job), result(first=uuid4() if exists else None)]
    monkeypatch.setattr(candidate, "_applications_public", lambda session, rows: rows)
    if exists:
        with pytest.raises(candidate.ConflictError, match="Already applied"):
            candidate.apply(db, actors[0], job.id)
        db.add.assert_not_called()
        db.commit.assert_not_called()
        db.rollback.assert_called_once()
    else:
        saved = candidate.apply(db, actors[0], job.id)
        assert saved.candidate_id == actors[0].id and saved.job_id == job.id
        assert saved.status == ApplicationStatus.Pending
        db.commit.assert_called_once()


def test_fp_sec_1_other_candidate_cannot_read_application(db, actors, result):
    foreign = Application(candidate_id=uuid4(), job_id=uuid4())
    db.exec.return_value = result(first=foreign)
    with pytest.raises(candidate.ForbiddenError):
        candidate.get_application(db, actors[0], foreign.id)
    db.commit.assert_not_called()


def test_fp_can_3_owned_application_read_and_list_are_scoped(
    db, actors, result, monkeypatch
):
    row = Application(candidate_id=actors[0].id, job_id=uuid4())
    db.exec.return_value = result(first=row, rows=[row])
    monkeypatch.setattr(candidate, "_applications_public", lambda session, rows: rows)
    assert candidate.get_application(db, actors[0], row.id) is row
    assert candidate.list_applications(db, actors[0]) == [row]
    query = db.exec.call_args.args[0].compile()
    assert actors[0].id in query.params.values()
    db.commit.assert_not_called()


def test_fp_can_3_booking_is_visible_in_both_role_serializers(db, actors, result):
    from datetime import datetime, timedelta, timezone

    application = Application(
        candidate_id=actors[0].id, job_id=uuid4(), status=ApplicationStatus.Interviewing
    )
    start = datetime(2030, 5, 2, tzinfo=timezone.utc)
    slot = InterviewSlot(
        employer_id=actors[1].id, starts_at=start, ends_at=start + timedelta(minutes=30)
    )
    booking = Booking(application_id=application.id, slot_id=slot.id)
    db.exec.side_effect = [
        result(rows=[(application.job_id, "Job", "Company")]),
        result(
            rows=[(application.id, booking.id, slot.id, slot.starts_at, slot.ends_at)]
        ),
    ]
    view = candidate._applications_public(db, [application])[0]
    assert view.job_title == "Job" and view.company_name == "Company"
    assert view.booking.booking_id == booking.id and view.booking.slot_id == slot.id
    db.exec.side_effect = None
    db.exec.return_value = result(first=booking)
    db.get.return_value = slot
    employer_view = employer._booking_public(db, application.id)
    assert employer_view.booking_id == view.booking.booking_id
    assert (
        employer_view.starts_at == view.booking.starts_at
        and employer_view.ends_at == view.booking.ends_at
    )


def test_fp_emp_1_company_profile(db, actors, result):
    profile = EmployerProfile(
        user_id=actors[1].id, company_name="Company", company_description="Before"
    )
    db.get.return_value = profile
    assert employer.get_my_company(db, actors[1]).company_name == "Company"
    db.exec.return_value = result(first=profile)
    saved = employer.update_my_company(
        db, actors[1], CompanyUpdate(version=1, company_description="After")
    )
    assert saved.company_name == "Company" and saved.company_description == "After"
    db.commit.assert_called_once()


def test_fp_emp_1_missing_company_and_wrong_role(db, actors):
    from app.users.service import EmployerRoleRequiredError

    with pytest.raises(employer.CompanyNotFoundError):
        employer.get_my_company(db, actors[1])
    with pytest.raises(EmployerRoleRequiredError):
        employer.update_my_company(db, actors[0], CompanyUpdate(version=1, company_name="Other"))
    db.commit.assert_not_called()


def test_fp_emp_2_job_create_read_and_replace(db, actors, result):
    profile = EmployerProfile(user_id=actors[1].id, company_name="Company")
    db.get.return_value = profile
    db.exec.return_value = result(rows=["python", "sql"])
    saved = employer.create_job(
        db,
        actors[1],
        JobCreate(
            title="Job",
            description="Details",
            required_skills=[" SQL ", "Python", "sql"],
        ),
    )
    jobs = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], Job)]
    skills = [
        c.args[0].name for c in db.add.call_args_list if isinstance(c.args[0], JobSkill)
    ]
    assert len(jobs) == 1 and sorted(skills) == ["python", "sql"]
    assert saved.title == "Job" and saved.company_name == "Company"
    job = jobs[0]
    db.get.side_effect = lambda model, ident: job if model is Job else profile
    db.reset_mock()
    db.exec.side_effect = [result(first=job), result(rows=[])]
    changed = employer.update_job(
        db, actors[1], job.id, JobUpdate(version=1, title="Updated", required_skills=[])
    )
    assert changed.title == "Updated" and changed.description == "Details"
    assert not any(isinstance(c.args[0], JobSkill) for c in db.add.call_args_list)
    assert db.execute.call_args.args[0].table.name == "job_skill"
    assert saved.version == 1 and changed.version == 2
    db.exec.side_effect = None
    assert employer.get_my_job(db, actors[1], job.id).id == job.id


@pytest.mark.parametrize("field", ["title", "description"])
def test_fp_emp_2_nonempty_fields_are_validated(field):
    payload = dict(title="Job", description="Details", required_skills=[])
    payload[field] = " "
    with pytest.raises(ValidationError):
        JobCreate(**payload)


@pytest.mark.parametrize(
    "has_application,has_slot",
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_fp_emp_2_job_validation_and_deletion(
    db, actors, result, has_application, has_slot
):
    job = Job(employer_id=actors[1].id, title="Job", description="Details")
    db.exec.side_effect = [
        result(first=job),
        result(first=uuid4() if has_application else None),
        result(first=uuid4() if has_slot else None),
    ]
    if has_application or has_slot:
        with pytest.raises(employer.JobHasDependentsError):
            employer.delete_job(db, actors[1], job.id)
        assert not job.is_deleted
        db.commit.assert_not_called()
        db.rollback.assert_called_once()
    else:
        employer.delete_job(db, actors[1], job.id)
        assert job.is_deleted
        db.commit.assert_called_once()


@pytest.mark.parametrize("operation", ["get", "update", "delete", "applicants"])
def test_fp_sec_1_foreign_employer_cannot_manage_job(db, actors, result, operation):
    job = Job(employer_id=uuid4(), title="Foreign", description="Details")
    db.get.return_value = job
    db.exec.return_value = result(first=job)
    action = {
        "get": lambda: employer.get_my_job(db, actors[1], job.id),
        "update": lambda: employer.update_job(
            db, actors[1], job.id, JobUpdate(version=1, title="Changed")
        ),
        "delete": lambda: employer.delete_job(db, actors[1], job.id),
        "applicants": lambda: employer.list_job_applicants(db, actors[1], job.id),
    }[operation]
    with pytest.raises(employer.JobForbiddenError):
        action()
    assert job.title == "Foreign" and not job.is_deleted
    db.commit.assert_not_called()


@pytest.mark.parametrize("status", list(ApplicationStatus))
def test_fp_emp_3_applicant_status_and_booking_preservation(db, actors, result, status):
    row = Application(candidate_id=uuid4(), job_id=uuid4())
    job = Job(
        id=row.job_id, employer_id=actors[1].id, title="Job", description="Details"
    )
    db.exec.return_value = result(first=row)
    db.get.return_value = job
    saved = employer.change_application_status(
        db, actors[1], row.id, ApplicationStatusUpdate(version=1, status=status)
    )
    assert saved.status == status and saved.candidate_id == row.candidate_id
    db.delete.assert_not_called()
    db.add.assert_called_once_with(row)
    assert saved.version == 2 and row.version == 2
    db.execute.assert_not_called()
    assert db.exec.call_count == 1
    db.commit.assert_called_once()


def test_fp_emp_3_other_employer_and_candidate_cannot_change_status(db, actors, result):
    from app.users.service import EmployerRoleRequiredError

    row = Application(candidate_id=uuid4(), job_id=uuid4())
    db.exec.return_value = result(first=row)
    db.get.return_value = Job(
        id=row.job_id, employer_id=uuid4(), title="Foreign", description="Details"
    )
    for user, error in [
        (actors[1], employer.JobForbiddenError),
        (actors[0], EmployerRoleRequiredError),
    ]:
        with pytest.raises(error):
            employer.change_application_status(
                db, user, row.id, ApplicationStatusUpdate(version=1, status="Accepted")
            )
    assert row.status == ApplicationStatus.Pending
    db.commit.assert_not_called()


def test_fp_emp_3_invalid_status_is_rejected():
    with pytest.raises(ValidationError):
        ApplicationStatusUpdate(version=1, status="Unknown")


def test_fp_auth_3_missing_object_becomes_404(db, actors):
    with pytest.raises(HTTPException) as caught:
        router.execute(candidate.get_my_profile, db, actors[0])
    assert caught.value.status_code == 404


def test_fp_emp_2_company_required_and_missing_job(db, actors):
    with pytest.raises(employer.CompanyRequiredError):
        employer.create_job(
            db,
            actors[1],
            JobCreate(title="Job", description="Details", required_skills=[]),
        )
    with pytest.raises(employer.JobNotFoundError):
        employer.get_my_job(db, actors[1], uuid4())
    db.add.assert_not_called()
    db.commit.assert_not_called()
