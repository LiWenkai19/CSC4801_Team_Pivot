"""面试预约：每份申请和每个时段最多对应一个预约。"""

import sqlalchemy as sa
from alembic import op

revision = "owned_booking_003"
down_revision = "owned_flow_002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "booking",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("application_id", sa.Uuid(), sa.ForeignKey("application.id"), nullable=False),
        sa.Column("slot_id", sa.Uuid(), sa.ForeignKey("interview_slot.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.UniqueConstraint("application_id", name="uq_booking_application"),
        sa.UniqueConstraint("slot_id", name="uq_booking_slot"),
    )


def downgrade():
    raise RuntimeError("No automatic destructive downgrade; back up and coordinate table ownership first")
