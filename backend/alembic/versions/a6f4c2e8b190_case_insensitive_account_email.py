"""Use one canonical, case-insensitive account email without merging users."""

from alembic import op
import sqlalchemy as sa

revision = "a6f4c2e8b190"
down_revision = "9d6e1a4b2c30"
branch_labels = None
depends_on = None


def upgrade():
    op.execute('LOCK TABLE "user" IN ACCESS EXCLUSIVE MODE')
    duplicate = op.get_bind().execute(sa.text(
        'SELECT 1 FROM "user" GROUP BY lower(btrim(email)) '
        'HAVING count(*) > 1 LIMIT 1'
    )).first()
    if duplicate is not None:
        raise RuntimeError(
            "Case-insensitive duplicate email accounts exist; resolve account "
            "ownership explicitly before retrying this migration. No users were merged."
        )
    op.execute(sa.text(
        'UPDATE "user" SET email = lower(btrim(email)) '
        'WHERE email IS DISTINCT FROM lower(btrim(email))'
    ))
    op.drop_index("ix_user_email", table_name="user")
    op.create_index("ix_user_email", "user", [sa.text("lower(email)")], unique=True)
    op.create_index("ix_user_email_lookup", "user", ["email"], unique=False)


def downgrade():
    op.drop_index("ix_user_email_lookup", table_name="user")
    op.drop_index("ix_user_email", table_name="user")
    op.create_index("ix_user_email", "user", ["email"], unique=True)
