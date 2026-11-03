"""申请与面试时段；外键依赖雇主和职位表，由其所有者提供。"""

import sqlalchemy as sa
from alembic import op

# 第二阶段依赖核心表完成后才执行。
revision = "owned_flow_002"
down_revision = "owned_core_001"
branch_labels = None
depends_on = None


def timestamp(name):
    # 使用数据库当前时间作为默认值，列不可为空。
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False,
                     server_default=sa.func.current_timestamp())


def upgrade():
    dialect = op.get_bind().dialect.name
    # PostgreSQL 在建表时要求外键目标存在；SQLite 可先建立六表结构。
    if dialect == "postgresql" and not op.get_context().as_sql:
        # 在线升级前核实队友负责的外键目标表和对应列存在；离线生成 SQL 不做连接检查。
        inspector = sa.inspect(op.get_bind())
        for table, key in (("employer_profile", "user_id"), ("job", "id")):
            if not inspector.has_table(table):
                raise RuntimeError(f"External dependency missing: {table}; run core phase first")
            columns = {column["name"] for column in inspector.get_columns(table)}
            if key not in columns:
                raise RuntimeError(f"External dependency missing column: {table}.{key}")
    # 建申请表，并用候选人和职位的组合唯一约束防止重复申请。
    op.create_table(
        "application",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidate_profile.user_id"),
                  nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id"), nullable=False),
        sa.Column("status", sa.Enum("Pending", "Interviewing", "Rejected", "Accepted",
                                    name="application_status", native_enum=False,
                                    create_constraint=True),
                  nullable=False, server_default="Pending"),
        timestamp("created_at"),
        timestamp("updated_at"),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),
    )
    op.create_index("ix_application_candidate_id", "application", ["candidate_id"])
    op.create_index("ix_application_job_id", "application", ["job_id"])
    # 两种数据库的时间运算不同，分别表达固定 30 分钟的检查条件。
    duration = ("(ends_at - starts_at) = INTERVAL '30 minutes'" if dialect == "postgresql"
                else "abs((julianday(ends_at) - julianday(starts_at)) * 86400 - 1800) < 0.0001")
    # 建时段表：关联雇主、可选职位，要求结束时间晚于开始时间。
    op.create_table(
        "interview_slot",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("employer_id", sa.Uuid(), sa.ForeignKey("employer_profile.user_id"),
                  nullable=False),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        timestamp("created_at"),
        sa.CheckConstraint("ends_at > starts_at", name="ck_slot_time_order"),
        sa.CheckConstraint(duration, name="ck_slot_duration"),
    )
    op.create_index("ix_interview_slot_employer_id", "interview_slot", ["employer_id"])
    # 用数据库专用触发器在申请更新时维护 updated_at。
    if dialect == "postgresql":
        op.execute("""CREATE TRIGGER owned_application_updated_at
            BEFORE UPDATE ON application FOR EACH ROW
            EXECUTE FUNCTION owned_set_updated_at()""")
    else:
        op.execute("""CREATE TRIGGER owned_application_updated_at
            AFTER UPDATE ON application FOR EACH ROW
            WHEN NEW.updated_at = OLD.updated_at
            BEGIN
                UPDATE application SET updated_at = STRFTIME('%Y-%m-%d %H:%M:%f', 'now')
                WHERE id = NEW.id;
            END""")


def downgrade():
    # 阻止自动删除申请等数据，回退前需要明确备份与协调。
    raise RuntimeError("No automatic destructive downgrade; back up and coordinate table ownership first")
