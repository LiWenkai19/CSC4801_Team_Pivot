# 雇主模块迁移：接在团队初始迁移之后，建出雇主表以及雇主依赖的共享表。
# company、application、interview_slot、booking 的结构归属候选人模块（app/candidate/model.py），
# 此处按其当前定义创建；job、job_skill、employer_company 归属雇主模块（app/employer/model.py）。
# user.updated_at 与 candidate_profile.updated_at 是团队模型新增、初始迁移缺少的列，归属组员，在此一并补上。
import sqlalchemy as sa
from alembic import op

revision = 'employer_002'
down_revision = 'e07644577837'
branch_labels = None
depends_on = None


def ts(name):
    return sa.Column(
        name,
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.current_timestamp(),
    )


def add_updated_at(table):
    # 归属组员。SQLite 不能用非常量默认值新增非空列，先加可空列再回填。
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.add_column(table, ts('updated_at'))
    else:
        op.add_column(table, sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
        quoted = bind.dialect.identifier_preparer.quote(table)
        op.execute(sa.text('UPDATE ' + quoted + ' SET updated_at = CURRENT_TIMESTAMP'))


def upgrade():
    dialect = op.get_bind().dialect.name
    add_updated_at('user')
    add_updated_at('candidate_profile')

    # 归属组员：company
    op.create_table(
        'company',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        ts('created_at'),
        ts('updated_at'),
        sa.CheckConstraint('length(trim(name)) > 0', name='ck_company_name'),
    )

    # 归属雇主：job（company_id、employer_id 为逻辑外键，不建数据库外键）
    op.create_table(
        'job',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        sa.Column('employer_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default=sa.false()),
        ts('created_at'),
        ts('updated_at'),
        sa.CheckConstraint('length(trim(title)) > 0', name='ck_job_title'),
        sa.CheckConstraint('length(trim(description)) > 0', name='ck_job_description'),
    )
    op.create_index('ix_job_company_id', 'job', ['company_id'])
    op.create_index('ix_job_employer_id', 'job', ['employer_id'])

    op.create_table(
        'job_skill',
        sa.Column('job_id', sa.Uuid(), sa.ForeignKey('job.id'), primary_key=True),
        sa.Column('name', sa.String(), primary_key=True),
        sa.CheckConstraint(
            'length(name) > 0 AND name = lower(trim(name))', name='ck_job_skill_name'
        ),
    )

    op.create_table(
        'employer_company',
        sa.Column('employer_id', sa.Uuid(), primary_key=True),
        sa.Column('company_id', sa.Uuid(), nullable=False),
        ts('created_at'),
    )
    op.create_index('ix_employer_company_company_id', 'employer_company', ['company_id'])

    # 归属组员：application
    op.create_table(
        'application',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('candidate_id', sa.Uuid(), sa.ForeignKey('candidate_profile.user_id'), nullable=False),
        sa.Column('job_id', sa.Uuid(), sa.ForeignKey('job.id'), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'Pending',
                'Interviewing',
                'Rejected',
                'Accepted',
                name='application_status',
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        ts('created_at'),
        ts('updated_at'),
        sa.UniqueConstraint('candidate_id', 'job_id', name='uq_application_candidate_job'),
    )
    op.create_index('ix_application_candidate_id', 'application', ['candidate_id'])
    op.create_index('ix_application_job_id', 'application', ['job_id'])

    # 归属组员：interview_slot，30 分钟约束按方言分别书写
    if dialect == 'postgresql':
        duration = sa.CheckConstraint("(ends_at - starts_at) = INTERVAL '30 minutes'", name='ck_slot_duration')
    else:
        duration = sa.CheckConstraint(
            'abs((julianday(ends_at) - julianday(starts_at)) * 86400 - 1800) < 0.0001',
            name='ck_slot_duration',
        )
    op.create_table(
        'interview_slot',
        sa.Column('id', sa.Uuid(), primary_key=True),
        ts('created_at'),
        sa.Column('employer_id', sa.Uuid(), sa.ForeignKey('employer_profile.user_id'), nullable=False),
        sa.Column('job_id', sa.Uuid(), sa.ForeignKey('job.id'), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('ends_at > starts_at', name='ck_slot_time_order'),
        duration,
    )
    op.create_index('ix_interview_slot_employer_id', 'interview_slot', ['employer_id'])

    # 归属组员：booking
    op.create_table(
        'booking',
        sa.Column('id', sa.Uuid(), primary_key=True),
        ts('created_at'),
        sa.Column('application_id', sa.Uuid(), sa.ForeignKey('application.id'), nullable=False),
        sa.Column('slot_id', sa.Uuid(), sa.ForeignKey('interview_slot.id'), nullable=False),
        sa.UniqueConstraint('application_id', name='uq_booking_application'),
        sa.UniqueConstraint('slot_id', name='uq_booking_slot'),
    )


def downgrade():
    raise RuntimeError(
        'No automatic destructive downgrade; back up and coordinate table ownership first'
    )
