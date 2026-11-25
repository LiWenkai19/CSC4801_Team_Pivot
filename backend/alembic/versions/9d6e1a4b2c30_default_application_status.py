"""Align the application status database default with the shared model."""

from alembic import op
import sqlalchemy as sa

revision = "9d6e1a4b2c30"
down_revision = "8c3d0e5f7a21"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("application", "status", server_default=sa.text("'Pending'"))


def downgrade():
    op.alter_column("application", "status", server_default=None)
