"""Add company-profile and application-status edit revisions without resetting data."""

from alembic import op
import sqlalchemy as sa

revision = "8c3d0e5f7a21"
down_revision = "7b2c9d4e6f10"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("employer_profile", "application"):
        op.add_column(
            table,
            sa.Column(
                "version", sa.Integer(), nullable=False, server_default=sa.text("1")
            ),
        )
        op.create_check_constraint(f"ck_{table}_version", table, "version > 0")


def downgrade():
    for table in ("application", "employer_profile"):
        op.drop_constraint(f"ck_{table}_version", table, type_="check")
        op.drop_column(table, "version")
