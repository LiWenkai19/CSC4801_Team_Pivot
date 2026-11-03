"""账户、候选人资料、技能、公司；不包含雇主资料。"""

import sqlalchemy as sa
from alembic import op

# 这是独立迁移链的第一个版本，因此没有前置版本。
revision = "owned_core_001"
down_revision = None
branch_labels = None
depends_on = None


def timestamp(name):
    # 构造不允许为空、由数据库提供默认当前时间的时间列。
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False,
                     server_default=sa.func.current_timestamp())


def add_updated_at_trigger(table):
    # PostgreSQL 和 SQLite 的触发器语法不同；更新记录时维护 updated_at。
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"""CREATE TRIGGER owned_{table}_updated_at
            BEFORE UPDATE ON {table} FOR EACH ROW
            EXECUTE FUNCTION owned_set_updated_at()""")
    else:
        key = "user_id" if table == "candidate_profile" else "id"
        op.execute(f"""CREATE TRIGGER owned_{table}_updated_at
            AFTER UPDATE ON {table} FOR EACH ROW
            WHEN NEW.updated_at = OLD.updated_at
            BEGIN
                UPDATE {table} SET updated_at = STRFTIME('%Y-%m-%d %H:%M:%f', 'now')
                WHERE {key} = NEW.{key};
            END""")


def upgrade():
    # 依次创建账号、候选人资料、技能和公司四张用户负责的核心表。
    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.Enum("candidate", "employer", name="user_role",
                                  native_enum=False, create_constraint=True), nullable=False),
        timestamp("created_at"),
    )
    # 邮箱唯一索引既辅助查询，也由数据库阻止重复邮箱。
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    # 资料表的 user_id 是外键和主键，约束显示名称不能为空白。
    op.create_table(
        "candidate_profile",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("resume_text", sa.Text(), nullable=False, server_default=""),
        timestamp("updated_at"),
        sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_candidate_display_name"),
    )
    # 技能表使用候选人 ID 与规范名称的组合主键阻止重复技能。
    op.create_table(
        "candidate_skill",
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidate_profile.user_id"),
                  primary_key=True),
        sa.Column("name", sa.String(), primary_key=True),
        sa.CheckConstraint("length(name) > 0 AND name = lower(trim(name))",
                           name="ck_candidate_skill_normalized_name"),
    )
    # 公司名称必须有效，描述可以为空字符串。
    op.create_table(
        "company",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        timestamp("created_at"),
        timestamp("updated_at"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_company_name"),
    )
    # PostgreSQL 共用一个触发函数；SQLite 使用各表自己的触发器。
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION owned_set_updated_at() RETURNS trigger AS $$
            BEGIN NEW.updated_at = CURRENT_TIMESTAMP; RETURN NEW; END;
            $$ LANGUAGE plpgsql""")
    add_updated_at_trigger("candidate_profile")
    add_updated_at_trigger("company")


def downgrade():
    # 禁止自动删除业务表；回退前需要先备份并协调。
    raise RuntimeError("No automatic destructive downgrade; back up and coordinate table ownership first")
