# 【数据库迁移】SQLModel 的类是结构描述，Alembic 才负责把结构应用到数据库；升级和回退要遵守外键依赖顺序。
# 阅读提示：缩进表示代码属于哪个分支；= 保存值，== 比较值；None 表示缺失；类型注解不等于数据库操作。
"""共享职位、申请与面试预约表。"""

# 导入 alembic 中的 op，供后续代码调用；导入不是发起 HTTP 请求
from alembic import op

# 导入 sqlalchemy（本文件用 sa 作别名），供后续代码调用；导入不是发起 HTTP 请求
import sqlalchemy as sa

# 将结果保存在 revision：使用固定值 'candidate_flow_001'
revision = "candidate_flow_001"
# 将结果保存在 down_revision：使用固定值 'e07644577837'
down_revision = "e07644577837"
# 将结果保存在 branch_labels：使用固定值 None
branch_labels = None
# 将结果保存在 depends_on：使用固定值 None
depends_on = None


# 函数 upgrade()：按外键依赖顺序创建数据库结构；模型声明不会自动替代实际迁移。
def upgrade():
    # 在迁移中建立新表；各 Column 与约束构成真实数据库结构
    op.create_table(
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "job",
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("id", sa.Uuid(), primary_key=True),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column(
            # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
            "employer_id",
            # 继续完成上面的多行语句：在迁移中建立新表；各 Column 与约束构成真实数据库结构
            sa.Uuid(),
            # 继续完成上面的多行语句：在迁移中建立新表；各 Column 与约束构成真实数据库结构
            sa.ForeignKey("employer_profile.user_id"),
            # 是否允许数据库 NULL；False 表示必须有值
            nullable=False,
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("title", sa.String(), nullable=False),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("description", sa.String(), nullable=False),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_job_title"),
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        sa.CheckConstraint("length(trim(description)) > 0", name="ck_job_description"),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 建立索引以支持对应字段查询；unique=True 时还限制唯一性
    op.create_index("ix_job_employer_id", "job", ["employer_id"])
    # 在迁移中建立新表；各 Column 与约束构成真实数据库结构
    op.create_table(
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "job_skill",
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id"), primary_key=True),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("name", sa.String(), primary_key=True),
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        sa.CheckConstraint(
            # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
            "length(name) > 0 AND name = lower(trim(name))",
            name="ck_job_skill_name",
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 在迁移中建立新表；各 Column 与约束构成真实数据库结构
    op.create_table(
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "application",
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("id", sa.Uuid(), primary_key=True),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column(
            # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
            "candidate_id",
            # 继续完成上面的多行语句：在迁移中建立新表；各 Column 与约束构成真实数据库结构
            sa.Uuid(),
            # 继续完成上面的多行语句：在迁移中建立新表；各 Column 与约束构成真实数据库结构
            sa.ForeignKey("candidate_profile.user_id"),
            # 是否允许数据库 NULL；False 表示必须有值
            nullable=False,
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id"), nullable=False),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column(
            # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
            "status",
            # 继续完成上面的多行语句：在迁移中建立新表；各 Column 与约束构成真实数据库结构
            sa.Enum(
                # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
                "Pending",
                # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
                "Interviewing",
                # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
                "Rejected",
                # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
                "Accepted",
                # 这一项指定 name；逗号分隔同一调用/结构中的各个参数或字段
                name="application_status",
                # False 表示不创建 PostgreSQL 独立枚举类型
                native_enum=False,
                # 开启数据库 CHECK 约束，阻止非法枚举值
                create_constraint=True,
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 是否允许数据库 NULL；False 表示必须有值
            nullable=False,
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ),
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        sa.UniqueConstraint(
            # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
            "candidate_id",
            "job_id",
            name="uq_application_candidate_job",
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 建立索引以支持对应字段查询；unique=True 时还限制唯一性
    op.create_index("ix_application_candidate_id", "application", ["candidate_id"])
    # 建立索引以支持对应字段查询；unique=True 时还限制唯一性
    op.create_index("ix_application_job_id", "application", ["job_id"])
    # 在迁移中建立新表；各 Column 与约束构成真实数据库结构
    op.create_table(
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "interview_slot",
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("id", sa.Uuid(), primary_key=True),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column(
            # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
            "employer_id",
            # 继续完成上面的多行语句：在迁移中建立新表；各 Column 与约束构成真实数据库结构
            sa.Uuid(),
            # 继续完成上面的多行语句：在迁移中建立新表；各 Column 与约束构成真实数据库结构
            sa.ForeignKey("employer_profile.user_id"),
            # 是否允许数据库 NULL；False 表示必须有值
            nullable=False,
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("job.id"), nullable=True),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        sa.CheckConstraint("ends_at > starts_at", name="ck_slot_time_order"),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 建立索引以支持对应字段查询；unique=True 时还限制唯一性
    op.create_index("ix_interview_slot_employer_id", "interview_slot", ["employer_id"])
    # 在迁移中建立新表；各 Column 与约束构成真实数据库结构
    op.create_table(
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "booking",
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column("id", sa.Uuid(), primary_key=True),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column(
            # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
            "application_id",
            sa.Uuid(),
            sa.ForeignKey("application.id"),
            nullable=False,
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ),
        # 定义真实数据库列的名称、类型及其约束；这是迁移中的建表描述
        sa.Column(
            # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
            "slot_id",
            sa.Uuid(),
            sa.ForeignKey("interview_slot.id"),
            nullable=False,
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ),
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        sa.UniqueConstraint("application_id", name="uq_booking_application"),
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        sa.UniqueConstraint("slot_id", name="uq_booking_slot"),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 函数 downgrade()：按依赖的反方向撤销此迁移，先删除引用其他表的记录结构。
def downgrade():
    # for 循环：依次从 ['booking', 'interview_slot', 'application', 'job_skill', 'job'] 取出元素，保存在 name 后处理
    for name in ["booking", "interview_slot", "application", "job_skill", "job"]:
        # 删除此迁移创建的表；必须先删依赖它的其他表
        op.drop_table(name)
