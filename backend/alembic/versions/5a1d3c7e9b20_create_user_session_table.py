"""create user_session table

Revision ID: 5a1d3c7e9b20
Revises: c8f4a2b91d37
Create Date: 2026-11-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "5a1d3c7e9b20"
down_revision: Union[str, Sequence[str], None] = "c8f4a2b91d37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """服务端会话表：只存会话 ID 的哈希；删除用户时级联删除其会话。"""
    op.create_table(
        "user_session",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("csrf_token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_session_token_hash"), "user_session", ["token_hash"], unique=True
    )
    op.create_index(
        op.f("ix_user_session_user_id"), "user_session", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_session_user_id"), table_name="user_session")
    op.drop_index(op.f("ix_user_session_token_hash"), table_name="user_session")
    op.drop_table("user_session")
