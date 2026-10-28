"""雇主资料、职位、职位技能与雇主公司归属；依赖组员 core 阶段。"""

import sqlalchemy as sa
from alembic import op

revision = "employer_001"
down_revision = None
branch_labels = None
depends_on = None


def timestamp(name):
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.current_timestamp(),
    )


def check_dependencies():
    """新库必须已有 user 与 company；离线模式不连接数据库。"""
    if op.get_context().as_sql:
        return
    inspector = sa.inspect(op.get_bind())
    for table in ("user", "company"):
        if not inspector.has_table(table):
            raise RuntimeError(
                f"External dependency missing: {table}; "
                "run candidate core phase first"
            )


def upgrade():
    check_dependencies()
    # 与团队迁移 e07644577837 中的 employer_profile 定义逐列一致。
    op.create_table(
        "employer_profile",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("company_name", sa.String(), nullable=False),
        sa.Column("company_description", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "job",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("employer_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        timestamp("created_at"),
        timestamp("updated_at"),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_job_title"),
        sa.CheckConstraint(
            "length(trim(description)) > 0", name="ck_job_description"
        ),
    )
    op.create_index("ix_job_company_id", "job", ["company_id"])
    op.create_index("ix_job_employer_id", "job", ["employer_id"])
    op.create_table(
        "job_skill",
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id"), primary_key=True),
        sa.Column("name", sa.String(), primary_key=True),
        sa.CheckConstraint(
            "length(name) > 0 AND name = lower(trim(name))",
            name="ck_job_skill_name",
        ),
    )
    op.create_table(
        "employer_company",
        sa.Column("employer_id", sa.Uuid(), primary_key=True),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        timestamp("created_at"),
    )
    op.create_index(
        "ix_employer_company_company_id", "employer_company", ["company_id"]
    )


def downgrade():
    raise RuntimeError(
        "No automatic destructive downgrade; back up and coordinate table "
        "ownership first"
    )
