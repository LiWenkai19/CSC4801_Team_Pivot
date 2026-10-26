# 【接口数据格式】BaseModel 是请求/响应的字段清单，不创建数据库表。类型注解决定 FastAPI 怎样校验与输出 JSON。
# 阅读提示：缩进表示代码属于哪个分支；= 保存值，== 比较值；None 表示缺失；类型注解不等于数据库操作。
# 导入 uuid，供后续代码调用；导入不是发起 HTTP 请求
import uuid
from typing import Literal

# 导入 datetime 中的 datetime，供后续代码调用；导入不是发起 HTTP 请求
from datetime import datetime

# 导入 pydantic 中的 BaseModel、ConfigDict，供后续代码调用；导入不是发起 HTTP 请求
from pydantic import BaseModel, ConfigDict

# 导入 app.candidate.model 中的 ApplicationStatus，供后续代码调用；导入不是发起 HTTP 请求
from app.candidate.model import ApplicationStatus


# EmptyRequest 继承 BaseModel；把相关字段/行为组织在同一类型中
class EmptyRequest(BaseModel):
    # 将结果保存在 model_config：调用 ConfigDict（参数见括号），取得结果或执行相应操作
    model_config = ConfigDict(extra="forbid")


# BookingCreate 继承 EmptyRequest；把相关字段/行为组织在同一类型中
class BookingCreate(EmptyRequest):
    # 面试时段 ID：类型为 uuid.UUID；这里只声明数据格式
    slot_id: uuid.UUID


# JobPublic 继承 BaseModel；把相关字段/行为组织在同一类型中
class JobPublic(BaseModel):
    # 记录的唯一标识：类型为 uuid.UUID；这里只声明数据格式
    id: uuid.UUID
    # 雇主账户 ID：类型为 uuid.UUID；这里只声明数据格式
    employer_id: uuid.UUID
    # 职位标题：类型为 str；这里只声明数据格式
    title: str
    # 职位描述：类型为 str；这里只声明数据格式
    description: str
    # 公司名称：类型为 str；这里只声明数据格式
    company_name: str
    # 职位要求的技能：类型为 list[str]；这里只声明数据格式
    required_skills: list[str]
    # 0～100 的整数匹配分数：类型为 int；这里只声明数据格式
    score: int
    score_kind: Literal["placeholder"]
    # 本人是否已经申请此职位：类型为 bool；这里只声明数据格式
    applied: bool


# SlotPublic 继承 BaseModel；把相关字段/行为组织在同一类型中
class SlotPublic(BaseModel):
    # 记录的唯一标识：类型为 uuid.UUID；这里只声明数据格式
    id: uuid.UUID
    # 带时区的面试开始时间：类型为 datetime；这里只声明数据格式
    starts_at: datetime
    # 带时区的面试结束时间：类型为 datetime；这里只声明数据格式
    ends_at: datetime


# BookingPublic 继承 SlotPublic；把相关字段/行为组织在同一类型中
class BookingPublic(SlotPublic):
    # 面试时段 ID：类型为 uuid.UUID；这里只声明数据格式
    slot_id: uuid.UUID


# ApplicationPublic 继承 BaseModel；把相关字段/行为组织在同一类型中
class ApplicationPublic(BaseModel):
    # 记录的唯一标识：类型为 uuid.UUID；这里只声明数据格式
    id: uuid.UUID
    # 职位 ID：类型为 uuid.UUID；这里只声明数据格式
    job_id: uuid.UUID
    # 职位标题：类型为 str；这里只声明数据格式
    title: str
    # 公司名称：类型为 str；这里只声明数据格式
    company_name: str
    # 状态值：类型为 ApplicationStatus；这里只声明数据格式
    status: ApplicationStatus
    # 预约记录：类型为 BookingPublic | None；这里只声明数据格式
    booking: BookingPublic | None
