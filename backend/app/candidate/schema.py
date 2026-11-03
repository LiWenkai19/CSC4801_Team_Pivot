import uuid
from typing import Literal

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.candidate.model import ApplicationStatus


# EmptyRequest 继承 BaseModel；把相关字段/行为组织在同一类型中
class EmptyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


# BookingCreate 继承 EmptyRequest；把相关字段/行为组织在同一类型中
class BookingCreate(EmptyRequest):
    # 面试时段 ID：类型为 uuid.UUID；这里只声明数据格式
    slot_id: uuid.UUID


# JobPublic 继承 BaseModel；把相关字段/行为组织在同一类型中
class JobPublic(BaseModel):
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
