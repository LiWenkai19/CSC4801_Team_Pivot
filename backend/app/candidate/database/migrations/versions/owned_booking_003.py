"""面试预约：每份申请和每个时段最多对应一个预约。"""

import sqlalchemy as sa
from alembic import op

# Alembic 用 revision 和 down_revision 确认本迁移应接在申请和时段迁移之后。
revision = "owned_booking_003"
down_revision = "owned_flow_002"
branch_labels = None
depends_on = None


def upgrade():
    # 创建预约表；两个外键指向已有的申请与时段，两条唯一约束防止重复占用。
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
    # 不自动删除可能包含业务数据的表，回退需要先备份并协调所有权。
    raise RuntimeError("No automatic destructive downgrade; back up and coordinate table ownership first")
