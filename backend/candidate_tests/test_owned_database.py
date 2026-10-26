"""验证六表迁移、数据完整性和队友表边界；所有写入均在临时数据库。"""

import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlmodel import Session, SQLModel, select

from app.candidate import model as team_flow
from app.candidate.database.migration import check, config_for, make_engine, upgrade
from app.candidate.database.model import (
    Application, CandidateProfile, CandidateSkill, Company, InterviewSlot,
    OWNED_TABLES, OwnedModel, User,
)
from app.users import model as team_users


@pytest.fixture
def database(tmp_path):
    engine = make_engine("sqlite:///" + (tmp_path / "owned.sqlite3").as_posix())
    try:
        yield engine
    finally:
        engine.dispose()


def external_fixture(connection):
    """仅测试中模拟队友交付的四张表，生产迁移从不创建它们。"""
    for model in (team_users.EmployerProfile, team_flow.Job, team_flow.JobSkill, team_flow.Booking):
        model.__table__.create(connection)


def schema_snapshot(connection):
    return connection.execute(text(
        "SELECT name, sql FROM sqlite_master WHERE tbl_name IN "
        "('employer_profile', 'job', 'job_skill', 'booking') ORDER BY name"
    )).all()


@pytest.fixture
def integrated(database):
    with database.begin() as connection:
        upgrade(connection, "core")
        external_fixture(connection)
        before = schema_snapshot(connection)
        upgrade(connection)
        assert schema_snapshot(connection) == before
        candidate_id, employer_id, job_id = [uuid.uuid4() for _ in range(3)]
        connection.execute(User.__table__.insert(), [
            dict(id=candidate_id, email="candidate@test.invalid", hashed_password="hash",
                 role="candidate"),
            dict(id=employer_id, email="employer@test.invalid", hashed_password="hash",
                 role="employer"),
        ])
        connection.execute(CandidateProfile.__table__.insert(), dict(
            user_id=candidate_id, display_name="Candidate",
        ))
        connection.execute(team_users.EmployerProfile.__table__.insert(), dict(
            user_id=employer_id, company_name="Existing company", company_description="Existing",
        ))
        connection.execute(team_flow.Job.__table__.insert(), dict(
            id=job_id, employer_id=employer_id, title="Existing job", description="Description",
            is_deleted=False,
        ))
    return database, candidate_id, employer_id, job_id


def test_empty_database_creates_exactly_six_owned_tables(database):
    with database.begin() as connection:
        original_metadata = set(SQLModel.metadata.tables)
        upgrade(connection)
        assert set(inspect(connection).get_table_names()) == OWNED_TABLES | {"alembic_owned_version"}
        assert set(SQLModel.metadata.tables) == original_metadata
        assert "company" not in SQLModel.metadata.tables
        assert "score" not in {column["name"] for column in inspect(connection).get_columns("application")}
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
        check(connection)
        upgrade(connection)
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []


def test_core_then_external_tables_then_full_is_repeatable(integrated):
    engine, candidate_id, employer_id, job_id = integrated
    with engine.begin() as connection:
        before = schema_snapshot(connection)
        rows_before = connection.execute(team_flow.Job.__table__.select()).all()
        upgrade(connection)
        check(connection)
        assert schema_snapshot(connection) == before
        assert connection.execute(team_flow.Job.__table__.select()).all() == rows_before
        assert connection.execute(team_users.EmployerProfile.__table__.select()).one().user_id == employer_id
        assert connection.execute(team_flow.Job.__table__.select()).one().id == job_id
        assert connection.execute(CandidateProfile.__table__.select()).one().user_id == candidate_id


def test_core_phase_has_no_external_dependencies(database):
    with database.begin() as connection:
        upgrade(connection, "core")
        assert set(inspect(connection).get_table_names()) == {
            "user", "candidate_profile", "candidate_skill", "company", "alembic_owned_version",
        }
        assert connection.execute(text("SELECT version_num FROM alembic_owned_version")).scalar() == "owned_core_001"


def test_orm_persistence_defaults_and_utc_across_reconnect(integrated):
    engine, candidate_id, employer_id, job_id = integrated
    start = datetime(2035, 1, 1, 10, tzinfo=timezone(timedelta(hours=8)))
    with Session(engine) as session:
        company = Company(name="Company")
        application = Application(candidate_id=candidate_id, job_id=job_id)
        slot = InterviewSlot(employer_id=employer_id, job_id=job_id,
                             starts_at=start, ends_at=start + timedelta(minutes=30))
        session.add_all([company, application, slot, CandidateSkill(candidate_id=candidate_id, name="sql")])
        session.commit()
        company_id, application_id, slot_id = company.id, application.id, slot.id
    engine.dispose()
    with Session(engine) as session:
        assert session.get(Company, company_id).description == ""
        assert session.get(Application, application_id).status.value == "Pending"
        assert session.get(Application, application_id).created_at.tzinfo == timezone.utc
        assert session.get(InterviewSlot, slot_id).starts_at == start.astimezone(timezone.utc)
        assert session.get(CandidateProfile, candidate_id).resume_text == ""
        assert session.get(User, candidate_id).created_at.tzinfo == timezone.utc
        assert session.exec(select(CandidateSkill)).one().name == "sql"


def test_email_and_skill_and_application_uniqueness(integrated):
    engine, candidate_id, _, job_id = integrated
    with engine.begin() as connection:
        connection.execute(CandidateSkill.__table__.insert(), dict(candidate_id=candidate_id, name="python"))
        connection.execute(Application.__table__.insert(), dict(candidate_id=candidate_id, job_id=job_id))
    for table, values in [
        (User.__table__, dict(email="candidate@test.invalid", hashed_password="hash", role="candidate")),
        (CandidateSkill.__table__, dict(candidate_id=candidate_id, name="python")),
        (Application.__table__, dict(candidate_id=candidate_id, job_id=job_id)),
    ]:
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(table.insert(), values)


@pytest.mark.parametrize("name", ["", " ", "Python", " python", "python "])
def test_skill_normalization_enforced_by_database(integrated, name):
    engine, candidate_id, _, _ = integrated
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(CandidateSkill.__table__.insert(), dict(candidate_id=candidate_id, name=name))


def test_blank_names_invalid_roles_and_status_are_rejected(integrated):
    engine, candidate_id, _, job_id = integrated
    statements = [
        ("INSERT INTO company(id, name) VALUES (:id, ' ')", {}),
        ("UPDATE candidate_profile SET display_name = ' ' WHERE user_id = :candidate", {}),
        ('UPDATE "user" SET role = \'admin\' WHERE id = :candidate', {}),
        ("INSERT INTO application(id, candidate_id, job_id, status) VALUES (:id, :candidate, :job, 'Unknown')", {}),
    ]
    for statement, _ in statements:
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(statement), dict(id=uuid.uuid4().hex, candidate=candidate_id.hex, job=job_id.hex))


def test_foreign_keys_reject_orphans_and_protect_job(integrated):
    engine, candidate_id, employer_id, job_id = integrated
    invalid = uuid.uuid4()
    for table, values in [
        (CandidateProfile.__table__, dict(user_id=invalid, display_name="Orphan")),
        (CandidateSkill.__table__, dict(candidate_id=invalid, name="sql")),
        (Application.__table__, dict(candidate_id=candidate_id, job_id=invalid)),
        (Application.__table__, dict(candidate_id=invalid, job_id=job_id)),
        (InterviewSlot.__table__, dict(employer_id=invalid, starts_at=datetime(2035, 1, 1, tzinfo=timezone.utc),
                                      ends_at=datetime(2035, 1, 1, 0, 30, tzinfo=timezone.utc))),
    ]:
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(table.insert(), values)
    with engine.begin() as connection:
        connection.execute(Application.__table__.insert(), dict(candidate_id=candidate_id, job_id=job_id))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(team_flow.Job.__table__.delete().where(team_flow.Job.id == job_id))


@pytest.mark.parametrize("minutes", [-30, 0, 15, 31, 60])
def test_slot_duration_is_enforced_at_database_layer(integrated, minutes):
    engine, _, employer_id, job_id = integrated
    start = datetime(2035, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(InterviewSlot.__table__.insert(), dict(
            employer_id=employer_id, job_id=job_id, starts_at=start,
            ends_at=start + timedelta(minutes=minutes),
        ))


def test_slot_rejects_naive_time_and_accepts_employer_wide_slot(integrated):
    engine, _, employer_id, _ = integrated
    start = datetime(2035, 1, 1)
    with pytest.raises(StatementError), engine.begin() as connection:
        connection.execute(InterviewSlot.__table__.insert(), dict(
            employer_id=employer_id, starts_at=start, ends_at=start + timedelta(minutes=30),
        ))
    with engine.begin() as connection:
        connection.execute(InterviewSlot.__table__.insert(), dict(
            employer_id=employer_id, starts_at=start.replace(tzinfo=timezone.utc),
            ends_at=(start + timedelta(minutes=30)).replace(tzinfo=timezone.utc),
        ))


def test_updated_at_triggers_work_with_existing_team_orm(integrated):
    engine, candidate_id, _, job_id = integrated
    with engine.begin() as connection:
        connection.execute(Company.__table__.insert(), dict(name="Before"))
        connection.execute(Application.__table__.insert(), dict(candidate_id=candidate_id, job_id=job_id))
        for table in ("candidate_profile", "company", "application"):
            connection.execute(text(f"UPDATE {table} SET updated_at = '2000-01-01 00:00:00'"))
    with Session(engine) as session:
        # 旧类没有 updated_at 字段，数据库仍负责维护，避免旧服务写入后时间失效。
        profile = session.get(team_users.CandidateProfile, candidate_id)
        profile.display_name = "After"
        application = session.exec(select(team_flow.Application)).one()
        application.status = team_flow.ApplicationStatus.Interviewing
        session.add_all([profile, application])
        session.commit()
    with engine.begin() as connection:
        connection.execute(text("UPDATE company SET name = 'After'"))
    with Session(engine) as session:
        assert session.get(CandidateProfile, candidate_id).updated_at.year > 2000
        assert session.exec(select(Application)).one().updated_at.year > 2000
        assert session.exec(select(Company)).one().updated_at.year > 2000


def test_postgresql_offline_sql_creates_only_owned_tables():
    output = io.StringIO()
    config = config_for(url="postgresql+psycopg://unused/unused")
    config.output_buffer = output
    command.upgrade(config, "head", sql=True)
    sql = output.getvalue()
    for name in OWNED_TABLES:
        assert f'CREATE TABLE {name} (' in sql or f'CREATE TABLE "{name}" (' in sql
    for name in ("employer_profile", "job", "job_skill", "booking"):
        assert f"CREATE TABLE {name} " not in sql
        assert f"ALTER TABLE {name} " not in sql
    assert "INTERVAL '30 minutes'" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "owned_set_updated_at()" in sql
    assert "REFERENCES job (id)" in sql
    assert "REFERENCES employer_profile (user_id)" in sql


def test_new_models_do_not_change_team_metadata():
    assert OwnedModel.metadata is not SQLModel.metadata
    assert "updated_at" not in team_users.CandidateProfile.__table__.columns
    assert "created_at" not in team_flow.Application.__table__.columns
    assert "company_id" not in team_users.EmployerProfile.__table__.columns
