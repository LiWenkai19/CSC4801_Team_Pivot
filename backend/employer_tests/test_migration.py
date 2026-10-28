"""验证雇主迁移链的依赖、表结构与组员模型一致性。"""

import pytest
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.candidate.database.migration import check as candidate_check
from app.employer.database.migration import check, upgrade

EXPECTED_JOB_COLUMNS = {
    "id",
    "company_id",
    "employer_id",
    "title",
    "description",
    "is_deleted",
    "created_at",
    "updated_at",
}


def test_employer_chain_requires_candidate_core(engine):
    """空库直接执行雇主迁移必须报缺少组员 core 依赖。"""
    with engine.begin() as connection:
        with pytest.raises(RuntimeError, match="External dependency missing: user"):
            upgrade(connection)


def test_three_step_chain_creates_expected_tables(migrated_engine):
    """三步迁移后所有表存在，job 列齐全且没有数据库外键。"""
    with migrated_engine.begin() as connection:
        names = set(inspect(connection).get_table_names())
        assert {
            "employer_profile",
            "job",
            "job_skill",
            "employer_company",
            "application",
            "interview_slot",
            "booking",
        } <= names
        job_columns = {
            column["name"]
            for column in inspect(connection).get_columns("job")
        }
        assert job_columns == EXPECTED_JOB_COLUMNS
        assert inspect(connection).get_foreign_keys("job") == []
        assert {
            column["name"]
            for column in inspect(connection).get_columns("job_skill")
        } == {"job_id", "name"}
        assert {
            column["name"]
            for column in inspect(connection).get_columns("employer_company")
        } == {"employer_id", "company_id", "created_at"}
        assert {
            column["name"]
            for column in inspect(connection).get_columns("employer_profile")
        } == {"user_id", "company_name", "company_description"}
        assert inspect(connection).get_foreign_keys("job_skill")[0]["referred_table"] == "job"
        assert inspect(connection).get_indexes("job")
        assert {
            index["name"] for index in inspect(connection).get_indexes("job")
        } == {"ix_job_company_id", "ix_job_employer_id"}
        assert {
            index["name"]
            for index in inspect(connection).get_indexes("employer_company")
        } == {"ix_employer_company_company_id"}


def test_employer_profile_matches_team_model(migrated_engine):
    """employer_profile 的列名集合与团队模型一致。"""
    from app.users.model import EmployerProfile

    with migrated_engine.begin() as connection:
        columns = {
            column["name"]
            for column in inspect(connection).get_columns("employer_profile")
        }
    assert columns == {column.name for column in EmployerProfile.__table__.columns}


def test_employer_chain_check_has_no_diff(migrated_engine):
    """迁移后的结构、类型和默认值与独立元数据一致。"""
    with migrated_engine.begin() as connection:
        check(connection)
        candidate_check(connection)
        assert MigrationContext.configure(
            connection, opts={"version_table": "alembic_employer_version"}
        ).get_current_revision() == "employer_001"
