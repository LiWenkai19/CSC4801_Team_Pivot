"""共享职位、申请与面试预约表。"""

from alembic import op

import sqlalchemy as sa

revision = "candidate_flow_001"
down_revision = "e07644577837"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "employer_id",
            sa.Uuid(),
            sa.ForeignKey("employer_profile.user_id"),
            # 是否允许数据库 NULL；False 表示必须有值
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_job_title"),
        sa.CheckConstraint("length(trim(description)) > 0", name="ck_job_description"),
    )
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
        "application",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Uuid(),
            sa.ForeignKey("candidate_profile.user_id"),
            # 是否允许数据库 NULL；False 表示必须有值
            nullable=False,
        ),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id"), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "Pending",
                "Interviewing",
                "Rejected",
                "Accepted",
                name="application_status",
                # False 表示不创建 PostgreSQL 独立枚举类型
                native_enum=False,
                # 开启数据库 CHECK 约束，阻止非法枚举值
                create_constraint=True,
            ),
            # 是否允许数据库 NULL；False 表示必须有值
            nullable=False,
        ),
        sa.UniqueConstraint(
            "candidate_id",
            "job_id",
            name="uq_application_candidate_job",
        ),
    )
    op.create_index("ix_application_candidate_id", "application", ["candidate_id"])
    op.create_index("ix_application_job_id", "application", ["job_id"])
    op.create_table(
        "interview_slot",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "employer_id",
            sa.Uuid(),
            sa.ForeignKey("employer_profile.user_id"),
            # 是否允许数据库 NULL；False 表示必须有值
            nullable=False,
        ),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id"), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_slot_time_order"),
    )
    op.create_index("ix_interview_slot_employer_id", "interview_slot", ["employer_id"])
    op.create_table(
        "booking",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("application.id"),
            nullable=False,
        ),
        sa.Column(
            "slot_id",
            sa.Uuid(),
            sa.ForeignKey("interview_slot.id"),
            nullable=False,
        ),
        sa.UniqueConstraint("application_id", name="uq_booking_application"),
        sa.UniqueConstraint("slot_id", name="uq_booking_slot"),
    )


def downgrade():
    for name in ["booking", "interview_slot", "application", "job_skill", "job"]:
        # 删除此迁移创建的表；必须先删依赖它的其他表
        op.drop_table(name)
