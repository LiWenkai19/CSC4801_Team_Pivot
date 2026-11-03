"""将独立候选人数据库的额外结构加入共享数据库。"""
from alembic import op
import sqlalchemy as sa

revision = "candidate_shared_002"
down_revision = "candidate_flow_001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "company",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_company_name"),
    )
    for table, columns in (
        ("candidate_profile", ("updated_at",)),
        ("application", ("created_at", "updated_at")),
        ("interview_slot", ("created_at",)),
        ("booking", ("created_at",)),
    ):
        for name in columns:
            op.add_column(table, sa.Column(name, sa.DateTime(timezone=True), nullable=True))
            op.execute(sa.text(f'UPDATE "{table}" SET "{name}" = CURRENT_TIMESTAMP WHERE "{name}" IS NULL'))


def downgrade():
    raise RuntimeError("Automatic destructive downgrade is disabled; back up and coordinate first")
