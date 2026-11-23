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
