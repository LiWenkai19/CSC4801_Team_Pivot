"""在独立空库/旧版本库验证增量迁移，不触碰开发数据。"""

from pathlib import Path
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import create_engine


@pytest.mark.parametrize("legacy", [False, True])
def test_version_migration_preserves_data_and_matches_model_defaults(engine, legacy):
    from app.core.config import settings
    from app.employer.model import Job
    from app.users.model import CandidateProfile

    name = "csc4801_version_migration_" + uuid.uuid4().hex[:12]
    admin = create_engine(
        engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    migrated = create_engine(engine.url.set(database=name))
    previous = settings.DATABASE_URL
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    candidate, employer, posting = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    def seed():
        with migrated.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO \"user\" (id,email,hashed_password,role,created_at) VALUES (:id,:email,'synthetic',:role,now())"
                ),
                [
                    dict(id=candidate, email="candidate@example.com", role="candidate"),
                    dict(id=employer, email="employer@example.com", role="employer"),
                ],
            )
            connection.execute(
                text(
                    "INSERT INTO candidate_profile (user_id,display_name,resume_text) VALUES (:id,'Owner','Preserved résumé')"
                ),
                dict(id=candidate),
            )
            connection.execute(
                text(
                    "INSERT INTO employer_profile (user_id,company_name,company_description) VALUES (:id,'Company','Preserved company')"
                ),
                dict(id=employer),
            )
            connection.execute(
                text(
                    "INSERT INTO job (id,employer_id,title,description,is_deleted,created_at,updated_at) VALUES (:id,:owner,'Job','Preserved job',false,now(),now())"
                ),
                dict(id=posting, owner=employer),
            )
            connection.execute(
                text(
                    "INSERT INTO candidate_skill (candidate_id,name) VALUES (:id,'python')"
                ),
                dict(id=candidate),
            )
            connection.execute(
                text("INSERT INTO job_skill (job_id,name) VALUES (:id,'sql')"),
                dict(id=posting),
            )

    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        settings.DATABASE_URL = engine.url.set(database=name).render_as_string(
            hide_password=False
        )
        command.upgrade(config, "5a1d3c7e9b20" if legacy else "head")
        seed()
        if legacy:
            command.upgrade(config, "head")
        for table, model in [("candidate_profile", CandidateProfile), ("job", Job)]:
            column = next(
                c
                for c in inspect(migrated).get_columns(table)
                if c["name"] == "version"
            )
            assert column["nullable"] is False
            assert (
                column["default"]
                == str(model.__table__.c.version.server_default.arg)
                == "1"
            )
            checks = inspect(migrated).get_check_constraints(table)
            assert any(c["name"] == f"ck_{table}_version" for c in checks)
            with migrated.connect() as connection:
                assert (
                    connection.execute(
                        text(f'SELECT version FROM "{table}"')
                    ).scalar_one()
                    == 1
                )
            with pytest.raises(IntegrityError):
                with migrated.begin() as connection:
                    connection.execute(text(f'UPDATE "{table}" SET version=0'))
        with migrated.connect() as connection:
            assert connection.execute(
                text("SELECT display_name,resume_text FROM candidate_profile")
            ).one() == ("Owner", "Preserved résumé")
            assert connection.execute(
                text("SELECT title,description FROM job")
            ).one() == ("Job", "Preserved job")
            assert (
                connection.execute(
                    text("SELECT name FROM candidate_skill")
                ).scalar_one()
                == "python"
            )
            assert (
                connection.execute(text("SELECT name FROM job_skill")).scalar_one()
                == "sql"
            )
        command.downgrade(config, "5a1d3c7e9b20")
        assert all(c["name"] != "version" for c in inspect(migrated).get_columns("job"))
        with migrated.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT resume_text FROM candidate_profile")
                ).scalar_one()
                == "Preserved résumé"
            )
        command.upgrade(config, "head")
        with migrated.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT version FROM candidate_profile")
                ).scalar_one()
                == 1
            )
    finally:
        settings.DATABASE_URL = previous
        migrated.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.mark.parametrize("legacy", [False, True])
def test_status_default_migration_preserves_states_and_explicit_values(engine, legacy):
    from app.core.config import settings

    name = "csc4801_status_default_" + uuid.uuid4().hex[:12]
    admin = create_engine(engine.url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    migrated = create_engine(engine.url.set(database=name))
    previous = settings.DATABASE_URL
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    candidate, employer = uuid.uuid4(), uuid.uuid4()
    states = ["Pending", "Interviewing", "Rejected", "Accepted"]
    jobs = [uuid.uuid4() for _ in range(7)]
    applications = [uuid.uuid4() for _ in jobs]
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        settings.DATABASE_URL = migrated.url.render_as_string(hide_password=False)
        command.upgrade(config, "8c3d0e5f7a21" if legacy else "head")
        with migrated.begin() as connection:
            connection.execute(
                text('INSERT INTO "user" (id,email,hashed_password,role,created_at) '
                     "VALUES (:id,:email,'synthetic',:role,now())"),
                [dict(id=candidate, email="candidate@example.com", role="candidate"),
                 dict(id=employer, email="employer@example.com", role="employer")],
            )
            connection.execute(text("INSERT INTO candidate_profile (user_id,display_name,resume_text) "
                                    "VALUES (:id,'Candidate','Preserved')"), dict(id=candidate))
            connection.execute(text("INSERT INTO employer_profile (user_id,company_name,company_description) "
                                    "VALUES (:id,'Company','Preserved')"), dict(id=employer))
            connection.execute(
                text("INSERT INTO job (id,employer_id,title,description,is_deleted,created_at,updated_at) "
                     "VALUES (:id,:owner,'Job','Preserved',false,now(),now())"),
                [dict(id=job, owner=employer) for job in jobs],
            )
            connection.execute(
                text("INSERT INTO application (id,candidate_id,job_id,status,created_at,updated_at) "
                     "VALUES (:id,:candidate,:job,:status,now(),now())"),
                [dict(id=applications[i], candidate=candidate, job=jobs[i], status=state)
                 for i, state in enumerate(states)],
            )
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        with migrated.connect() as connection:
            assert sorted(connection.execute(text("SELECT status FROM application")).scalars()) == sorted(states)
        status = next(c for c in inspect(migrated).get_columns("application") if c["name"] == "status")
        assert "Pending" in status["default"]
        assert status["nullable"] is False
        with migrated.begin() as connection:
            assert connection.execute(
                text("INSERT INTO application (id,candidate_id,job_id,created_at,updated_at) "
                     "VALUES (:id,:candidate,:job,now(),now()) RETURNING status"),
                dict(id=applications[4], candidate=candidate, job=jobs[4]),
            ).scalar_one() == "Pending"
            assert connection.execute(
                text("INSERT INTO application (id,candidate_id,job_id,status,created_at,updated_at) "
                     "VALUES (:id,:candidate,:job,'Accepted',now(),now()) RETURNING status"),
                dict(id=applications[5], candidate=candidate, job=jobs[5]),
            ).scalar_one() == "Accepted"
        with pytest.raises(IntegrityError):
            with migrated.begin() as connection:
                connection.execute(
                    text("INSERT INTO application (id,candidate_id,job_id,status,created_at,updated_at) "
                         "VALUES (:id,:candidate,:job,NULL,now(),now())"),
                    dict(id=applications[6], candidate=candidate, job=jobs[6]),
                )
        command.downgrade(config, "8c3d0e5f7a21")
        assert next(c for c in inspect(migrated).get_columns("application") if c["name"] == "status")["default"] is None
        command.upgrade(config, "head")
        with migrated.connect() as connection:
            assert sorted(connection.execute(text("SELECT status FROM application")).scalars()) == sorted(states + ["Pending", "Accepted"])
    finally:
        settings.DATABASE_URL = previous
        migrated.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
