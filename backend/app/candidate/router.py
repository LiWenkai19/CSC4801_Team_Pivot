# 【HTTP 入口】浏览器请求先到这里：路径参数定位对象，Depends 提供会话与登录用户，service 执行业务规则。
# 阅读提示：缩进表示代码属于哪个分支；= 保存值，== 比较值；None 表示缺失；类型注解不等于数据库操作。
# 导入 uuid，供后续代码调用；导入不是发起 HTTP 请求
import uuid

# 导入 fastapi 中的 APIRouter、Body、Depends、HTTPException，供后续代码调用；导入不是发起 HTTP 请求
from fastapi import APIRouter, Body, Depends, HTTPException

# 导入 sqlmodel 中的 Session、select，供后续代码调用；导入不是发起 HTTP 请求
from sqlmodel import Session, select

# 导入 app.candidate 中的 service，供后续代码调用；导入不是发起 HTTP 请求
from app.candidate import service
from app.candidate.resume_access import readable_profile

# 导入 app.candidate.model 中的 Application，供后续代码调用；导入不是发起 HTTP 请求
from app.candidate.model import Application

# 导入 app.candidate.schema 中的 ApplicationPublic、BookingCreate、BookingPublic、EmptyRequest、JobPublic、SlotPublic，供后续代码调用；导入不是发起 HTTP 请求
from app.candidate.schema import (
    # 继续导入 ApplicationPublic，与上面的 from/import 属于同一语句
    ApplicationPublic,
    # 继续导入 BookingCreate，与上面的 from/import 属于同一语句
    BookingCreate,
    # 继续导入 BookingPublic，与上面的 from/import 属于同一语句
    BookingPublic,
    # 继续导入 EmptyRequest，与上面的 from/import 属于同一语句
    EmptyRequest,
    # 继续导入 JobPublic，与上面的 from/import 属于同一语句
    JobPublic,
    # 继续导入 SlotPublic，与上面的 from/import 属于同一语句
    SlotPublic,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)

# 导入 app.db.session 中的 get_db，供后续代码调用；导入不是发起 HTTP 请求
from app.db.session import get_db

# 导入 app.users.model 中的 User，供后续代码调用；导入不是发起 HTTP 请求
from app.users.model import User

# 导入 app.users.schema 中的 CandidateProfilePublic、CandidateProfileUpdate，供后续代码调用；导入不是发起 HTTP 请求
from app.candidate.profile_schema import CandidateProfilePublic, CandidateProfileUpdate

# 导入 app.users.service 中的 require_candidate、require_employer，供后续代码调用；导入不是发起 HTTP 请求
from app.users.service import get_current_user, require_candidate, require_employer

# 将结果保存在 router：调用 APIRouter（参数见括号），取得结果或执行相应操作
router = APIRouter(tags=["candidate"])


# 装饰器把下面函数注册为 HTTP 接口；get 读数据，post 创建，patch 局部修改
@router.get("/employer/jobs/{job_id}/applications")
# 函数 employer_applicants(job_id, session, user)：只向职位所属雇主展示申请人技能、分数、状态和预约，绝不返回简历。
def employer_applicants(
    # 这一项指定 职位 ID；逗号分隔同一调用/结构中的各个参数或字段
    job_id: uuid.UUID,
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session = Depends(get_db),
    # 这一项指定 已通过认证的账户；逗号分隔同一调用/结构中的各个参数或字段
    user: User = Depends(require_employer),
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
):
    # return 结束本函数并把结果交给调用者：在路由层把业务异常翻译成 HTTP 状态码，业务服务本身不负责浏览器协议
    return execute(service.employer_applicants, session, user, job_id)


# 函数 execute(action)：在路由层把业务异常翻译成 HTTP 状态码，业务服务本身不负责浏览器协议。
def execute(action, *args):
    # try 包住可能失败的步骤；对应 except 负责区分失败原因并处理回滚
    try:
        # return 结束本函数并把结果交给调用者：调用 action（参数见括号），取得结果或执行相应操作
        return action(*args)
    # except 捕获 service.FlowError；只处理这一类失败，不把所有错误假装成同一原因
    except service.FlowError as error:
        # 抛出失败并立即停止成功路径：HTTPException(error.status, str(error))
        raise HTTPException(error.status, str(error)) from error


# 装饰器把下面函数注册为 HTTP 接口；get 读数据，post 创建，patch 局部修改
@router.get(
    # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
    "/users/candidates/{candidate_id}/profile",
    response_model=CandidateProfilePublic,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)
# 函数 read_profile(candidate_id, session, user)：候选人仅读本人，雇主仅读自己职位的申请人。
def read_profile(
    # 这一项指定 候选人的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
    candidate_id: uuid.UUID,
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session = Depends(get_db),
    # 这一项指定 已通过认证的账户；逗号分隔同一调用/结构中的各个参数或字段
    user: User = Depends(get_current_user),
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
):
    # 明确挑选资料字段，不把完整账户或 ORM 对象直接暴露给浏览器
    return service.profile_public(
        # 继续完成上面的多行语句：return 结束本函数并把结果交给调用者：明确挑选允许返回给本人的资料字段，不把完整 ORM 对象直接暴露给浏览器
        execute(readable_profile, session, user, candidate_id)
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 装饰器把下面函数注册为 HTTP 接口；get 读数据，post 创建，patch 局部修改
@router.patch(
    # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
    "/users/candidates/{candidate_id}/profile",
    response_model=CandidateProfilePublic,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)
# 函数 patch_profile(candidate_id, payload, session, user)：处理本人资料的局部修改请求；payload 由更新 schema 先行校验。
def patch_profile(
    # 这一项指定 候选人的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
    candidate_id: uuid.UUID,
    # 这一项指定 已经过类型校验的请求内容；逗号分隔同一调用/结构中的各个参数或字段
    payload: CandidateProfileUpdate,
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session = Depends(get_db),
    # 这一项指定 已通过认证的账户；逗号分隔同一调用/结构中的各个参数或字段
    user: User = Depends(require_candidate),
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
):
    # return 结束本函数并把结果交给调用者：在路由层把业务异常翻译成 HTTP 状态码，业务服务本身不负责浏览器协议
    return execute(service.update_profile, session, user, candidate_id, payload)


# 装饰器把下面函数注册为 HTTP 接口；get 读数据，post 创建，patch 局部修改
@router.get("/candidate/jobs", response_model=list[JobPublic])
# 函数 jobs(session, user)：处理候选人职位列表请求，具体查询和排序交给 service。
def jobs(session: Session = Depends(get_db), user: User = Depends(require_candidate)):
    # return 结束本函数并把结果交给调用者：在路由层把业务异常翻译成 HTTP 状态码，业务服务本身不负责浏览器协议
    return execute(service.list_jobs, session, user)


# 装饰器把下面函数注册为 HTTP 接口；get 读数据，post 创建，patch 局部修改
@router.get("/candidate/jobs/{job_id}", response_model=JobPublic)
# 函数 job_detail(job_id, session, user)：处理一个职位的详情请求，复用资料校验与公开职位组装。
def job_detail(
    # 这一项指定 职位 ID；逗号分隔同一调用/结构中的各个参数或字段
    job_id: uuid.UUID,
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session = Depends(get_db),
    # 这一项指定 已通过认证的账户；逗号分隔同一调用/结构中的各个参数或字段
    user: User = Depends(require_candidate),
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
):
    # 将结果保存在 候选人资料：在路由层把业务异常翻译成 HTTP 状态码，业务服务本身不负责浏览器协议
    profile = execute(service.owned_profile, session, user, user.id)
    # return 结束本函数并把结果交给调用者：组合职位、公司、技能、实时分数和本人申请标记，供列表和详情共同使用
    return service.job_public(
        # 继续完成上面的多行语句：return 结束本函数并把结果交给调用者：组合职位、公司、技能、实时分数和本人申请标记，供列表和详情共同使用
        session,
        execute(service.active_job, session, job_id),
        profile,
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 装饰器把下面函数注册为 HTTP 接口；get 读数据，post 创建，patch 局部修改
@router.post(
    # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
    "/candidate/jobs/{job_id}/applications",
    # 限定返回 JSON 字段与类型，避免意外泄露未声明内容
    response_model=ApplicationPublic,
    # 设置成功响应状态码；201 表示已创建新记录
    status_code=201,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)
# 函数 apply(job_id, payload, session, user)：创建状态固定为 Pending 的本人申请，数据库唯一约束防止重复提交。
def apply(
    # 这一项指定 职位 ID；逗号分隔同一调用/结构中的各个参数或字段
    job_id: uuid.UUID,
    # 这一项指定 已经过类型校验的请求内容；逗号分隔同一调用/结构中的各个参数或字段
    payload: EmptyRequest = Body(default=EmptyRequest()),
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session = Depends(get_db),
    # 这一项指定 已通过认证的账户；逗号分隔同一调用/结构中的各个参数或字段
    user: User = Depends(require_candidate),
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
):
    # return 结束本函数并把结果交给调用者：在路由层把业务异常翻译成 HTTP 状态码，业务服务本身不负责浏览器协议
    return execute(service.apply, session, user, job_id)


# 装饰器把下面函数注册为 HTTP 接口；get 读数据，post 创建，patch 局部修改
@router.get("/candidate/applications", response_model=list[ApplicationPublic])
# 函数 applications(session, user)：只查询当前登录候选人的申请，不能靠客户端传入其他人的 ID。
def applications(
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session = Depends(get_db),
    user: User = Depends(require_candidate),
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
):
    # 将结果保存在 准备返回的记录列表：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
    rows = session.exec(
        # 继续完成上面的多行语句：将结果保存在 准备返回的记录列表：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
        select(Application)
        # 为查询添加筛选条件；不是把字符串拼接为 SQL
        .where(Application.candidate_id == user.id)
        # 指定数据库结果的排序依据
        .order_by(Application.id)
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # return 结束本函数并把结果交给调用者：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
    return [service.application_public(session, a) for a in rows]


# 装饰器把下面函数注册为 HTTP 接口；get 读数据，post 创建，patch 局部修改
@router.get(
    # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
    "/candidate/applications/{application_id}",
    response_model=ApplicationPublic,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)
# 函数 application_detail(application_id, session, user)：处理单个申请详情请求，必须先检查对象所有权。
def application_detail(
    # 这一项指定 申请 ID；逗号分隔同一调用/结构中的各个参数或字段
    application_id: uuid.UUID,
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session = Depends(get_db),
    # 这一项指定 已通过认证的账户；逗号分隔同一调用/结构中的各个参数或字段
    user: User = Depends(require_candidate),
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
):
    # return 结束本函数并把结果交给调用者：组合申请、职位、公司和已有预约，候选人与雇主复用相同展示数据
    return service.application_public(
        # 继续完成上面的多行语句：return 结束本函数并把结果交给调用者：组合申请、职位、公司和已有预约，候选人与雇主复用相同展示数据
        session,
        execute(service.owned_application, session, user, application_id),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 装饰器把下面函数注册为 HTTP 接口；get 读数据，post 创建，patch 局部修改
@router.get(
    # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
    "/candidate/applications/{application_id}/slots",
    response_model=list[SlotPublic],
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)
# 函数 slots(application_id, session, user)：为一个属于本人的面试中申请查询可用时段。
def slots(
    # 这一项指定 申请 ID；逗号分隔同一调用/结构中的各个参数或字段
    application_id: uuid.UUID,
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session = Depends(get_db),
    # 这一项指定 已通过认证的账户；逗号分隔同一调用/结构中的各个参数或字段
    user: User = Depends(require_candidate),
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
):
    # return 结束本函数并把结果交给调用者：在路由层把业务异常翻译成 HTTP 状态码，业务服务本身不负责浏览器协议
    return execute(service.available_slots, session, user, application_id)


# 装饰器把下面函数注册为 HTTP 接口；get 读数据，post 创建，patch 局部修改
@router.post(
    # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
    "/candidate/applications/{application_id}/booking",
    # 限定返回 JSON 字段与类型，避免意外泄露未声明内容
    response_model=BookingPublic,
    # 设置成功响应状态码；201 表示已创建新记录
    status_code=201,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)
# 函数 booking(application_id, payload, session, user)：接收 slot_id 并调用原子预约服务，成功返回 201。
def booking(
    # 这一项指定 申请 ID；逗号分隔同一调用/结构中的各个参数或字段
    application_id: uuid.UUID,
    # 这一项指定 已经过类型校验的请求内容；逗号分隔同一调用/结构中的各个参数或字段
    payload: BookingCreate,
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session = Depends(get_db),
    # 这一项指定 已通过认证的账户；逗号分隔同一调用/结构中的各个参数或字段
    user: User = Depends(require_candidate),
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
):
    # return 结束本函数并把结果交给调用者：在路由层把业务异常翻译成 HTTP 状态码，业务服务本身不负责浏览器协议
    return execute(service.book, session, user, application_id, payload.slot_id)
