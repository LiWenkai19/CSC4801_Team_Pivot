"""验证团队 alembic 链（employer_002）建出的表结构。"""

from sqlalchemy import inspect

EXPECTED_JOB_COLUMNS = {
    "id", "company_id", "employer_id", "title", "description",
    "is_deleted", "created_at", "updated_at",
}


def test_head_creates_employer_and_shared_tables(migrated_engine):
    """upgrade head 后雇主表与共享表都存在。"""
    names = set(inspect(migrated_engine).get_table_names())
    assert {
        "user", "candidate_profile", "employer_profile", "company", "job",
        "job_skill", "employer_company", "application", "interview_slot", "booking",
    } <= names


def test_job_columns_and_logical_foreign_keys(migrated_engine):
    """job 列与设计图一致，company_id / employer_id 不建数据库外键。"""
    insp = inspect(migrated_engine)
    assert {c["name"] for c in insp.get_columns("job")} == EXPECTED_JOB_COLUMNS
    assert insp.get_foreign_keys("job") == []
    assert insp.get_foreign_keys("employer_company") == []
    assert insp.get_foreign_keys("job_skill")[0]["referred_table"] == "job"
    assert {i["name"] for i in insp.get_indexes("job")} == {"ix_job_company_id", "ix_job_employer_id"}


def test_team_models_get_updated_at_columns(migrated_engine):
    """团队模型新增的 updated_at 由 employer_002 补齐。"""
    insp = inspect(migrated_engine)
    for table in ("user", "candidate_profile", "company", "application"):
        assert "updated_at" in {c["name"] for c in insp.get_columns(table)}, table


def test_shared_tables_match_candidate_models(migrated_engine):
    """共享表的列集合与 app.candidate.model 一致。"""
    from app.candidate import model

    insp = inspect(migrated_engine)
    for cls in (model.Company, model.Application, model.InterviewSlot, model.Booking):
        table = cls.__table__
        assert {c["name"] for c in insp.get_columns(table.name)} == {c.name for c in table.columns}, table.name
