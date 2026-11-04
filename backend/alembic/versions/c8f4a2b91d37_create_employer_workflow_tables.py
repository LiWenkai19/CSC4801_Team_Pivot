"""create employer workflow tables

Revision ID: c8f4a2b91d37
Revises: e07644577837
Create Date: 2026-11-04

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "c8f4a2b91d37"
down_revision: Union[str, Sequence[str], None] = "e07644577837"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建职位、职位技能、申请、面试时段和预约表。"""
    op.create_table(
        "job",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employer_id", sa.Uuid(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_job_title"),
        sa.CheckConstraint(
            "length(trim(description)) > 0", name="ck_job_description"
        ),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["employer_profile.user_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_employer_id"), "job", ["employer_id"], unique=False)
    op.create_table(
        "job_skill",
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.CheckConstraint(
            "length(name) > 0 AND name = lower(trim(name))",
            name="ck_job_skill_name",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.id"],
        ),
        sa.PrimaryKeyConstraint("job_id", "name"),
    )
    op.create_table(
        "application",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "Pending",
                "Interviewing",
                "Rejected",
                "Accepted",
                name="application_status",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate_profile.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),
    )
    op.create_index(
        op.f("ix_application_candidate_id"), "application", ["candidate_id"], unique=False
    )
    op.create_index(
        op.f("ix_application_job_id"), "application", ["job_id"], unique=False
    )
    op.create_table(
        "interview_slot",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("employer_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_slot_time_order"),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["employer_profile.user_id"],
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_interview_slot_employer_id"),
        "interview_slot",
        ["employer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_interview_slot_job_id"), "interview_slot", ["job_id"], unique=False
    )
    op.create_table(
        "booking",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("application_id", sa.Uuid(), nullable=False),
        sa.Column("slot_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["application.id"],
        ),
        sa.ForeignKeyConstraint(
            ["slot_id"],
            ["interview_slot.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_booking_application"),
        sa.UniqueConstraint("slot_id", name="uq_booking_slot"),
    )


def downgrade() -> None:
    """按外键依赖的逆序删除本次创建的表。"""
    op.drop_table("booking")
    op.drop_index(op.f("ix_interview_slot_job_id"), table_name="interview_slot")
    op.drop_index(op.f("ix_interview_slot_employer_id"), table_name="interview_slot")
    op.drop_table("interview_slot")
    op.drop_index(op.f("ix_application_job_id"), table_name="application")
    op.drop_index(op.f("ix_application_candidate_id"), table_name="application")
    op.drop_table("application")
    op.drop_table("job_skill")
    op.drop_index(op.f("ix_job_employer_id"), table_name="job")
    op.drop_table("job")
