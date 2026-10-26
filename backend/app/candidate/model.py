# 【数据库模型】每个 table=True 的类对应一张表；Field 定义列，外键连接不同表，唯一约束防止并发重复记录。
# 阅读提示：缩进表示代码属于哪个分支；= 保存值，== 比较值；None 表示缺失；类型注解不等于数据库操作。
"""共享业务表；雇主与 scheduling 模块应复用这些模型。"""

# 导入 uuid，供后续代码调用；导入不是发起 HTTP 请求
import uuid

# 导入 datetime 中的 datetime，供后续代码调用；导入不是发起 HTTP 请求
from datetime import datetime

# 导入 enum 中的 Enum，供后续代码调用；导入不是发起 HTTP 请求
from enum import Enum

# 导入 sqlalchemy 中的 CheckConstraint、Column、DateTime、UniqueConstraint，供后续代码调用；导入不是发起 HTTP 请求
from sqlalchemy import CheckConstraint, Column, DateTime, UniqueConstraint

# 导入 sqlalchemy 中的 Enum（本文件用 SAEnum 作别名），供后续代码调用；导入不是发起 HTTP 请求
from sqlalchemy import Enum as SAEnum

# 导入 sqlmodel 中的 Field、SQLModel，供后续代码调用；导入不是发起 HTTP 请求
from sqlmodel import Field, SQLModel


# ApplicationStatus 定义一组固定选项，避免状态/角色任意拼写
class ApplicationStatus(str, Enum):
    # 将结果保存在 待处理：使用固定值 'Pending'
    Pending = "Pending"
    # 将结果保存在 面试中：使用固定值 'Interviewing'
    Interviewing = "Interviewing"
    # 将结果保存在 已拒绝：使用固定值 'Rejected'
    Rejected = "Rejected"
    # 将结果保存在 已录用：使用固定值 'Accepted'
    Accepted = "Accepted"


# Job 是数据库表模型；继承 SQLModel，table=True 表示字段会映射为数据库列
class Job(SQLModel, table=True):
    # 将结果保存在 __tablename__：使用固定值 'job'
    __tablename__ = "job"
    # 将结果保存在 __table_args__：组装元组；用于多个排序依据时，从左向右依次比较
    __table_args__ = (
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        CheckConstraint("length(trim(title)) > 0", name="ck_job_title"),
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        CheckConstraint("length(trim(description)) > 0", name="ck_job_description"),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 记录的唯一标识：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # 雇主账户 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    employer_id: uuid.UUID = Field(foreign_key="employer_profile.user_id", index=True)
    # 职位标题：类型为 str；这里只声明数据格式
    title: str
    # 职位描述：类型为 str；这里只声明数据格式
    description: str
    # 职位的删除标记（True 表示不再展示）：类型为 bool；使用固定值 False
    is_deleted: bool = False


# JobSkill 是数据库表模型；继承 SQLModel，table=True 表示字段会映射为数据库列
class JobSkill(SQLModel, table=True):
    # 将结果保存在 __tablename__：使用固定值 'job_skill'
    __tablename__ = "job_skill"
    # 将结果保存在 __table_args__：组装元组；用于多个排序依据时，从左向右依次比较
    __table_args__ = (
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        CheckConstraint(
            # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
            "length(name) > 0 AND name = lower(trim(name))",
            name="ck_job_skill_name",
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 职位 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    job_id: uuid.UUID = Field(foreign_key="job.id", primary_key=True)
    # name：类型为 str；声明字段的默认值、主键、外键或数据库列设置
    name: str = Field(primary_key=True)


# Application 是数据库表模型；继承 SQLModel，table=True 表示字段会映射为数据库列
class Application(SQLModel, table=True):
    # 将结果保存在 __tablename__：使用固定值 'application'
    __tablename__ = "application"
    # 将结果保存在 __table_args__：组装元组；用于多个排序依据时，从左向右依次比较
    __table_args__ = (
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        UniqueConstraint("candidate_id", "job_id", name="uq_application_candidate_job"),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 记录的唯一标识：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # 候选人的账户 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    candidate_id: uuid.UUID = Field(foreign_key="candidate_profile.user_id", index=True)
    # 职位 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    job_id: uuid.UUID = Field(foreign_key="job.id", index=True)
    # 状态值：类型为 ApplicationStatus；声明字段的默认值、主键、外键或数据库列设置
    status: ApplicationStatus = Field(
        # 未提供字段时使用的默认值
        default=ApplicationStatus.Pending,
        # 指定底层 SQLAlchemy 列，让时区/枚举约束正确写入数据库
        sa_column=Column(
            # 继续完成上面的多行语句：状态值：类型为 ApplicationStatus；声明字段的默认值、主键、外键或数据库列设置
            SAEnum(
                # 继续完成上面的多行语句：状态值：类型为 ApplicationStatus；声明字段的默认值、主键、外键或数据库列设置
                ApplicationStatus,
                # False 表示不创建 PostgreSQL 独立枚举类型
                native_enum=False,
                # 开启数据库 CHECK 约束，阻止非法枚举值
                create_constraint=True,
                # 让数据库存枚举的字符串值，而不是 Python 成员对象
                values_callable=lambda values: [v.value for v in values],
                # 这一项指定 name；逗号分隔同一调用/结构中的各个参数或字段
                name="application_status",
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 是否允许数据库 NULL；False 表示必须有值
            nullable=False,
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# InterviewSlot 是数据库表模型；继承 SQLModel，table=True 表示字段会映射为数据库列
class InterviewSlot(SQLModel, table=True):
    # 将结果保存在 __tablename__：使用固定值 'interview_slot'
    __tablename__ = "interview_slot"
    # 将结果保存在 __table_args__：组装元组；用于多个排序依据时，从左向右依次比较
    __table_args__ = (
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        CheckConstraint("ends_at > starts_at", name="ck_slot_time_order"),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 记录的唯一标识：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # 雇主账户 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    employer_id: uuid.UUID = Field(foreign_key="employer_profile.user_id", index=True)
    # 职位 ID：类型为 uuid.UUID | None；声明字段的默认值、主键、外键或数据库列设置
    job_id: uuid.UUID | None = Field(default=None, foreign_key="job.id")
    # 带时区的面试开始时间：类型为 datetime；声明字段的默认值、主键、外键或数据库列设置
    starts_at: datetime = Field(
        # 指定底层 SQLAlchemy 列，让时区/枚举约束正确写入数据库
        sa_column=Column(DateTime(timezone=True), nullable=False)
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 带时区的面试结束时间：类型为 datetime；声明字段的默认值、主键、外键或数据库列设置
    ends_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


# Booking 是数据库表模型；继承 SQLModel，table=True 表示字段会映射为数据库列
class Booking(SQLModel, table=True):
    # 将结果保存在 __tablename__：使用固定值 'booking'
    __tablename__ = "booking"
    # 将结果保存在 __table_args__：组装元组；用于多个排序依据时，从左向右依次比较
    __table_args__ = (
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        UniqueConstraint("application_id", name="uq_booking_application"),
        # 添加数据库约束；它由数据库强制执行，不能只靠前端按钮限制
        UniqueConstraint("slot_id", name="uq_booking_slot"),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 记录的唯一标识：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # 申请 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    application_id: uuid.UUID = Field(foreign_key="application.id")
    # 面试时段 ID：类型为 uuid.UUID；声明字段的默认值、主键、外键或数据库列设置
    slot_id: uuid.UUID = Field(foreign_key="interview_slot.id")
