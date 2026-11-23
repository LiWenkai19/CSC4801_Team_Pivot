"""Add versions for candidate profile and job edits without replacing existing data."""

from alembic import op
import sqlalchemy as sa

revision = "7b2c9d4e6f10"
down_revision = "5a1d3c7e9b20"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("candidate_profile", "job"):
        op.add_column(
            table,
            sa.Column(
                "version", sa.Integer(), nullable=False, server_default=sa.text("1")
            ),
        )
        op.create_check_constraint(f"ck_{table}_version", table, "version > 0")


def downgrade():
    for table in ("job", "candidate_profile"):
        op.drop_constraint(f"ck_{table}_version", table, type_="check")
        op.drop_column(table, "version")
