"""账户、候选人资料、技能、公司；不包含雇主资料。"""

import sqlalchemy as sa
from alembic import op

revision = "owned_core_001"
down_revision = None
branch_labels = None
depends_on = None


def timestamp(name):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False,
                     server_default=sa.func.current_timestamp())


def add_updated_at_trigger(table):
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
    op.create_table(
        "user",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.Enum("candidate", "employer", name="user_role",
                                  native_enum=False, create_constraint=True), nullable=False),
        timestamp("created_at"),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_table(
        "candidate_profile",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user.id"), primary_key=True),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("resume_text", sa.Text(), nullable=False, server_default=""),
        timestamp("updated_at"),
        sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_candidate_display_name"),
    )
    op.create_table(
        "candidate_skill",
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("candidate_profile.user_id"),
                  primary_key=True),
        sa.Column("name", sa.String(), primary_key=True),
        sa.CheckConstraint("length(name) > 0 AND name = lower(trim(name))",
                           name="ck_candidate_skill_normalized_name"),
    )
    op.create_table(
        "company",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        timestamp("created_at"),
        timestamp("updated_at"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_company_name"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION owned_set_updated_at() RETURNS trigger AS $$
            BEGIN NEW.updated_at = CURRENT_TIMESTAMP; RETURN NEW; END;
            $$ LANGUAGE plpgsql""")
    add_updated_at_trigger("candidate_profile")
    add_updated_at_trigger("company")


def downgrade():
    raise RuntimeError("No automatic destructive downgrade; back up and coordinate table ownership first")
