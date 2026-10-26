# 【业务规则】Session 是本次数据库工作区；select/where 只构造查询，exec/get 才读取；add 暂存，commit 提交，rollback 撤销。
# 阅读提示：缩进表示代码属于哪个分支；= 保存值，== 比较值；None 表示缺失；类型注解不等于数据库操作。
# 导入 uuid，供后续代码调用；导入不是发起 HTTP 请求
import uuid

# 导入 datetime 中的 timedelta、timezone，供后续代码调用；导入不是发起 HTTP 请求
from datetime import timedelta, timezone

# 导入 sqlalchemy 中的 delete，供后续代码调用；导入不是发起 HTTP 请求
from sqlalchemy import delete

# 导入 sqlalchemy.exc 中的 IntegrityError、SQLAlchemyError，供后续代码调用；导入不是发起 HTTP 请求
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

# 导入 sqlmodel 中的 Session、select，供后续代码调用；导入不是发起 HTTP 请求
from sqlmodel import Session, select

# 导入 app.candidate.model 中的 Application、ApplicationStatus、Booking、InterviewSlot、Job、JobSkill，供后续代码调用；导入不是发起 HTTP 请求
from app.candidate.model import (
    # 继续导入 Application，与上面的 from/import 属于同一语句
    Application,
    # 继续导入 ApplicationStatus，与上面的 from/import 属于同一语句
    ApplicationStatus,
    # 继续导入 Booking，与上面的 from/import 属于同一语句
    Booking,
    # 继续导入 InterviewSlot，与上面的 from/import 属于同一语句
    InterviewSlot,
    # 继续导入 Job，与上面的 from/import 属于同一语句
    Job,
    # 继续导入 JobSkill，与上面的 from/import 属于同一语句
    JobSkill,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)

# 排序及规范化复用共享模块，评分使用独立占位入口
from app.matching import applicant_sort_key, job_sort_key, normalize_skills
from app.candidate.recommendation_scoring import SCORE_KIND, match_score

# 导入 app.users.model 中的 CandidateProfile、CandidateSkill、EmployerProfile、User、utc_now，供后续代码调用；导入不是发起 HTTP 请求
from app.users.model import (
    # 继续导入 CandidateProfile，与上面的 from/import 属于同一语句
    CandidateProfile,
    # 继续导入 CandidateSkill，与上面的 from/import 属于同一语句
    CandidateSkill,
    # 继续导入 EmployerProfile，与上面的 from/import 属于同一语句
    EmployerProfile,
    # 继续导入 User，与上面的 from/import 属于同一语句
    User,
    # 继续导入 utc_now，与上面的 from/import 属于同一语句
    utc_now,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)

# 导入 app.users.schema 中的 CandidateProfilePublic、CandidateProfileUpdate，供后续代码调用；导入不是发起 HTTP 请求
from app.candidate.profile_schema import CandidateProfilePublic, CandidateProfileUpdate


# FlowError 表示可以识别的业务失败，供上层决定如何响应
class FlowError(ValueError):
    # 函数 __init__(self, status, message)：创建业务异常对象时保存 HTTP 状态码和错误文字，供 router 正确响应。
    def __init__(self, status: int, message: str):
        # 将结果保存在 self.status：使用 状态值
        self.status = status
        # 调用父类 ValueError 保存错误文字；以后 str(error) 就能得到这段文字。
        super().__init__(message)


# 函数 utc(value)：统一时间为 UTC，避免把不同时区的钟表时间直接比较。
def utc(value):
    # return 结束本函数并把结果交给调用者：条件成立取 if 前的值，否则取 else 后的值
    return (
        # 继续完成上面的多行语句：return 结束本函数并把结果交给调用者：条件成立取 if 前的值，否则取 else 后的值
        value.replace(tzinfo=timezone.utc)
        # 这里的条件决定选择/保留哪些值；不满足条件的记录不会进入结果
        if value.tzinfo is None
        # 条件表达式的备用值：前面的条件不成立时使用它
        else value.astimezone(timezone.utc)
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 函数 owned_profile(session, user, candidate_id)：先确认目标 ID 就是登录用户，再读取资料；不能让他人拿到私有简历。
def owned_profile(
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session,
    user: User,
    candidate_id: uuid.UUID,
    # 函数参数的类型注解帮助校验/理解输入；等号右侧（若有）是省略参数时的默认值
) -> CandidateProfile:
    # if 判断：比较 candidate_id != user.id；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
    if candidate_id != user.id:
        # 抛出失败并立即停止成功路径：FlowError(403, 'Private candidate profile')
        raise FlowError(403, "Private candidate profile")
    # 将结果保存在 候选人资料：用主键查询 CandidateProfile；找不到时得到 None
    profile = session.get(CandidateProfile, candidate_id)
    # if 判断：比较 profile is None；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
    if profile is None:
        # 抛出失败并立即停止成功路径：FlowError(404, 'Candidate profile not found; complete your profile first')
        raise FlowError(404, "Candidate profile not found; complete your profile first")
    # return 结束本函数并把结果交给调用者：使用 候选人资料
    return profile


# 函数 profile_public(profile)：明确挑选允许返回给本人的资料字段，不把完整 ORM 对象直接暴露给浏览器。
def profile_public(profile: CandidateProfile) -> CandidateProfilePublic:
    # return 结束本函数并把结果交给调用者：调用 CandidateProfilePublic（参数见括号），取得结果或执行相应操作
    return CandidateProfilePublic(
        # 这一项指定 资料所有者的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
        user_id=profile.user_id,
        # 这一项指定 候选人显示名称；逗号分隔同一调用/结构中的各个参数或字段
        display_name=profile.display_name,
        # 这一项指定 只有本人可读写的纯文本简历；逗号分隔同一调用/结构中的各个参数或字段
        resume_text=profile.resume_text,
        # 这一项指定 技术技能列表；逗号分隔同一调用/结构中的各个参数或字段
        skills=sorted(s.name for s in profile.skills),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 函数 update_profile(session, user, candidate_id, payload)：只修改明确提交的字段，名称/简历/技能一起提交，任何失败都整体回滚。
def update_profile(
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session,
    # 这一项指定 已通过认证的账户；逗号分隔同一调用/结构中的各个参数或字段
    user: User,
    # 这一项指定 候选人的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
    candidate_id: uuid.UUID,
    # 这一项指定 已经过类型校验的请求内容；逗号分隔同一调用/结构中的各个参数或字段
    payload: CandidateProfileUpdate,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
):
    # 将结果保存在 候选人资料：先确认目标 ID 就是登录用户，再读取资料；不能让他人拿到私有简历
    profile = owned_profile(session, user, candidate_id)
    # 将结果保存在 本次明确提交的修改字段：将已校验对象转为字典；exclude_unset=True 只保留请求明确传入的字段
    changes = payload.model_dump(exclude_unset=True)
    # try 包住可能失败的步骤；对应 except 负责区分失败原因并处理回滚
    try:
        # if 判断：比较 'skills' in changes；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
        if "skills" in changes:
            # 执行前面构造的数据库查询/语句，用户值由 ORM 绑定
            session.execute(
                # 继续完成上面的多行语句：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
                delete(CandidateSkill).where(
                    # 继续完成上面的多行语句：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
                    CandidateSkill.candidate_id == candidate_id
                    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
                )
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            )
            # pop 把 skills 从 changes 取出并移除：技能是另一张表，不能像普通文字字段一样 setattr。
            # for 循环：依次从 normalize_skills(changes.pop('skills')) 取出元素，保存在 name 后处理
            for name in normalize_skills(changes.pop("skills")):
                # 把对象加入数据库工作区；这一行本身还不等于提交成功
                session.add(CandidateSkill(candidate_id=candidate_id, name=name))
        # for 循环：依次从 changes.items() 取出元素，保存在 (name, value) 后处理
        for name, value in changes.items():
            # 根据字段名称设置对象属性，用于只修改已提交的资料字段
            setattr(profile, name, value)
        # 把对象加入数据库工作区；这一行本身还不等于提交成功
        session.add(profile)
        # 提交整个事务；成功后数据库中的修改才正式生效
        session.commit()
    # except 捕获 SQLAlchemyError；只处理这一类失败，不把所有错误假装成同一原因
    except SQLAlchemyError:
        # 撤销本次未成功提交的修改，并恢复 Session 的可用状态
        session.rollback()
        # raise 将当前异常继续交给调用者，不能吞掉无法解释的数据库故障
        raise
    # 从数据库重新读取对象，取得实际保存后的字段值
    session.refresh(profile)
    # profile.skills 是 ORM 关系，可能缓存了旧列表；删除/新增技能后必须让它重新读取，不能返回旧技能。
    # 使已缓存的字段失效，下一次访问重新查询数据库
    session.expire(profile, ["skills"])
    # return 结束本函数并把结果交给调用者：明确挑选允许返回给本人的资料字段，不把完整 ORM 对象直接暴露给浏览器
    return profile_public(profile)


# 函数 active_job(session, job_id)：查找仍有效的职位；不存在或已删除都视为无法申请。
def active_job(session: Session, job_id: uuid.UUID) -> Job:
    # 将结果保存在 职位：用主键查询 Job；找不到时得到 None
    job = session.get(Job, job_id)
    # if 判断：组合多个判断；and 要全部成立，or 只需其中一个成立；成立时执行下面缩进的代码
    if job is None or job.is_deleted:
        # 抛出失败并立即停止成功路径：FlowError(404, 'Job not found')
        raise FlowError(404, "Job not found")
    # return 结束本函数并把结果交给调用者：使用 职位
    return job


# 函数 job_public(session, job, profile)：组合职位、公司、技能、实时分数和本人申请标记，供列表和详情共同使用。
def job_public(session: Session, job: Job, profile: CandidateProfile) -> dict:
    # 将结果保存在 职位要求的技能：把查询/可迭代结果收集成普通列表
    required = list(
        # 继续完成上面的多行语句：将结果保存在 职位要求的技能：把查询/可迭代结果收集成普通列表
        session.exec(select(JobSkill.name).where(JobSkill.job_id == job.id))
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 将结果保存在 雇主公司资料：用主键查询 EmployerProfile；找不到时得到 None
    company = session.get(EmployerProfile, job.employer_id)
    # 将结果保存在 本人是否已经申请此职位：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
    applied = session.exec(
        # 继续完成上面的多行语句：将结果保存在 本人是否已经申请此职位：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
        select(Application.id).where(
            # 继续完成上面的多行语句：将结果保存在 本人是否已经申请此职位：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
            Application.job_id == job.id,
            Application.candidate_id == profile.user_id,
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
        # 继续完成上面的多行语句：将结果保存在 本人是否已经申请此职位：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
    ).first()
    # return 结束本函数并把结果交给调用者：组装只含指定字段的字典，随后作为 JSON 返回或展示
    return dict(
        # 这一项指定 记录的唯一标识；逗号分隔同一调用/结构中的各个参数或字段
        id=job.id,
        # 这一项指定 雇主账户 ID；逗号分隔同一调用/结构中的各个参数或字段
        employer_id=job.employer_id,
        # 这一项指定 职位标题；逗号分隔同一调用/结构中的各个参数或字段
        title=job.title,
        # 这一项指定 职位描述；逗号分隔同一调用/结构中的各个参数或字段
        description=job.description,
        # 这一项指定 公司名称；逗号分隔同一调用/结构中的各个参数或字段
        company_name=company.company_name,
        # 这一项指定 职位要求的技能；逗号分隔同一调用/结构中的各个参数或字段
        required_skills=sorted(required),
        # 这一项指定 0～100 的整数匹配分数；逗号分隔同一调用/结构中的各个参数或字段
        score=match_score([s.name for s in profile.skills], required),
        score_kind=SCORE_KIND,
        # 这一项指定 本人是否已经申请此职位；逗号分隔同一调用/结构中的各个参数或字段
        applied=applied is not None,
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 函数 list_jobs(session, user)：列出全部未删除职位并执行规定排序；没有资料时先引导填写。
def list_jobs(session: Session, user: User):
    # 将结果保存在 候选人资料：先确认目标 ID 就是登录用户，再读取资料；不能让他人拿到私有简历
    profile = owned_profile(session, user, user.id)
    # 将结果保存在 准备返回的记录列表：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
    rows = [
        # 继续完成上面的多行语句：将结果保存在 准备返回的记录列表：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
        job_public(session, j, profile)
        # 推导式的遍历部分：每次取出一条记录，交给上面的表达式生成结果
        for j in session.exec(select(Job).where(Job.is_deleted.is_(False)))
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ]
    # return 结束本函数并把结果交给调用者：返回排序后的新列表；若提供 key，则按 key 生成的值比较
    return sorted(rows, key=job_sort_key)


# 函数 apply(session, user, job_id)：创建状态固定为 Pending 的本人申请，数据库唯一约束防止重复提交。
def apply(session: Session, user: User, job_id: uuid.UUID):
    # 先确认目标 ID 就是登录用户，再读取资料；不能让他人拿到私有简历
    owned_profile(session, user, user.id)
    # 将结果保存在 职位：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
    job = session.exec(select(Job).where(Job.id == job_id).with_for_update()).first()
    # if 判断：组合多个判断；and 要全部成立，or 只需其中一个成立；成立时执行下面缩进的代码
    if job is None or job.is_deleted:
        # 抛出失败并立即停止成功路径：FlowError(404, 'Job not found')
        raise FlowError(404, "Job not found")
    # 将结果保存在 查询重复申请的语句：为查询添加筛选条件；不是把字符串拼接为 SQL
    duplicate = select(Application).where(
        # 继续完成上面的多行语句：将结果保存在 查询重复申请的语句：为查询添加筛选条件；不是把字符串拼接为 SQL
        Application.candidate_id == user.id,
        Application.job_id == job_id,
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # if 判断：执行前面构造的数据库查询/语句，用户值由 ORM 绑定；成立时执行下面缩进的代码
    if session.exec(duplicate).first():
        # 抛出失败并立即停止成功路径：FlowError(409, 'Already applied')
        raise FlowError(409, "Already applied")
    # 将结果保存在 职位申请：调用 Application（参数见括号），取得结果或执行相应操作
    application = Application(candidate_id=user.id, job_id=job_id)
    # try 包住可能失败的步骤；对应 except 负责区分失败原因并处理回滚
    try:
        # 把对象加入数据库工作区；这一行本身还不等于提交成功
        session.add(application)
        # 提交整个事务；成功后数据库中的修改才正式生效
        session.commit()
    # except 捕获 IntegrityError；只处理这一类失败，不把所有错误假装成同一原因
    except IntegrityError:
        # 撤销本次未成功提交的修改，并恢复 Session 的可用状态
        session.rollback()
        # if 判断：执行前面构造的数据库查询/语句，用户值由 ORM 绑定；成立时执行下面缩进的代码
        if session.exec(duplicate).first():
            # 抛出失败并立即停止成功路径：FlowError(409, 'Already applied')
            raise FlowError(409, "Already applied") from None
        # raise 将当前异常继续交给调用者，不能吞掉无法解释的数据库故障
        raise
    # except 捕获 SQLAlchemyError；只处理这一类失败，不把所有错误假装成同一原因
    except SQLAlchemyError:
        # 撤销本次未成功提交的修改，并恢复 Session 的可用状态
        session.rollback()
        # raise 将当前异常继续交给调用者，不能吞掉无法解释的数据库故障
        raise
    # return 结束本函数并把结果交给调用者：组合申请、职位、公司和已有预约，候选人与雇主复用相同展示数据
    return application_public(session, application)


# 函数 owned_application(session, user, application_id, lock)：读取申请并检查所有权；预约时可额外锁定此行，防止并发修改。
def owned_application(
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session,
    user: User,
    application_id: uuid.UUID,
    lock=False,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
):
    # 将结果保存在 尚未执行的查询语句：为查询添加筛选条件；不是把字符串拼接为 SQL
    query = select(Application).where(Application.id == application_id)
    # if 判断：使用 是否在查询时锁定数据库行；成立时执行下面缩进的代码
    if lock:
        # 将结果保存在 尚未执行的查询语句：为查询加 PostgreSQL 行锁，其他竞争者需等待当前事务结束
        query = query.with_for_update()
    # 将结果保存在 职位申请：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
    application = session.exec(query).first()
    # if 判断：比较 application is None；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
    if application is None:
        # 抛出失败并立即停止成功路径：FlowError(404, 'Application not found')
        raise FlowError(404, "Application not found")
    # if 判断：比较 application.candidate_id != user.id；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
    if application.candidate_id != user.id:
        # 抛出失败并立即停止成功路径：FlowError(403, 'Private application')
        raise FlowError(403, "Private application")
    # return 结束本函数并把结果交给调用者：使用 职位申请
    return application


# 函数 application_public(session, application)：组合申请、职位、公司和已有预约，候选人与雇主复用相同展示数据。
def application_public(session: Session, application: Application):
    # 将结果保存在 职位：用主键查询 Job；找不到时得到 None
    job = session.get(Job, application.job_id)
    # 将结果保存在 雇主公司资料：用主键查询 EmployerProfile；找不到时得到 None
    company = session.get(EmployerProfile, job.employer_id)
    # 将结果保存在 预约记录：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
    booking = session.exec(
        # 继续完成上面的多行语句：将结果保存在 预约记录：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
        select(Booking).where(Booking.application_id == application.id)
        # 继续完成上面的多行语句：将结果保存在 预约记录：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
    ).first()
    # 将结果保存在 预约展示信息：使用固定值 None
    info = None
    # if 判断：使用 预约记录；成立时执行下面缩进的代码
    if booking:
        # 将结果保存在 面试时段：用主键查询 InterviewSlot；找不到时得到 None
        slot = session.get(InterviewSlot, booking.slot_id)
        # 将结果保存在 预约展示信息：组装只含指定字段的字典，随后作为 JSON 返回或展示
        info = dict(
            # 这一项指定 记录的唯一标识；逗号分隔同一调用/结构中的各个参数或字段
            id=booking.id,
            # 这一项指定 面试时段 ID；逗号分隔同一调用/结构中的各个参数或字段
            slot_id=slot.id,
            # 这一项指定 带时区的面试开始时间；逗号分隔同一调用/结构中的各个参数或字段
            starts_at=utc(slot.starts_at),
            # 这一项指定 带时区的面试结束时间；逗号分隔同一调用/结构中的各个参数或字段
            ends_at=utc(slot.ends_at),
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
    # return 结束本函数并把结果交给调用者：组装只含指定字段的字典，随后作为 JSON 返回或展示
    return dict(
        # 这一项指定 记录的唯一标识；逗号分隔同一调用/结构中的各个参数或字段
        id=application.id,
        # 这一项指定 职位 ID；逗号分隔同一调用/结构中的各个参数或字段
        job_id=job.id,
        # 这一项指定 职位标题；逗号分隔同一调用/结构中的各个参数或字段
        title=job.title,
        # 这一项指定 公司名称；逗号分隔同一调用/结构中的各个参数或字段
        company_name=company.company_name,
        # 这一项指定 状态值；逗号分隔同一调用/结构中的各个参数或字段
        status=application.status,
        # 这一项指定 预约记录；逗号分隔同一调用/结构中的各个参数或字段
        booking=info,
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 函数 eligible_application(session, user, application_id, lock)：检查申请为 Interviewing 且尚未预约；这是选择和预约时段的共同入口。
def eligible_application(
    # 这一项指定 数据库会话（本次操作与数据库交互的对象）；逗号分隔同一调用/结构中的各个参数或字段
    session: Session,
    user: User,
    application_id: uuid.UUID,
    lock=False,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
):
    # 将结果保存在 职位申请：读取申请并检查所有权；预约时可额外锁定此行，防止并发修改
    application = owned_application(session, user, application_id, lock)
    # if 判断：比较 application.status != ApplicationStatus.Interviewing；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
    if application.status != ApplicationStatus.Interviewing:
        # 抛出失败并立即停止成功路径：FlowError(409, 'Application must be Interviewing')
        raise FlowError(409, "Application must be Interviewing")
    # if 判断：执行前面构造的数据库查询/语句，用户值由 ORM 绑定；成立时执行下面缩进的代码
    if session.exec(
        # 继续完成上面的多行语句：if 判断：执行前面构造的数据库查询/语句，用户值由 ORM 绑定；成立时执行下面缩进的代码
        select(Booking).where(Booking.application_id == application.id)
        # 继续完成上面的多行语句：if 判断：执行前面构造的数据库查询/语句，用户值由 ORM 绑定；成立时执行下面缩进的代码
    ).first():
        # 抛出失败并立即停止成功路径：FlowError(409, 'Application already booked')
        raise FlowError(409, "Application already booked")
    # return 结束本函数并把结果交给调用者：使用 职位申请
    return application


# 函数 available_slots(session, user, application_id)：排除其他雇主、过去、已预约和非 30 分钟的时段，只返回可选项。
def available_slots(session: Session, user: User, application_id: uuid.UUID):
    # 将结果保存在 职位申请：检查申请为 Interviewing 且尚未预约；这是选择和预约时段的共同入口
    application = eligible_application(session, user, application_id)
    # 将结果保存在 职位：用主键查询 Job；找不到时得到 None
    job = session.get(Job, application.job_id)
    # 将结果保存在 查询已被预约的时段 ID 的子查询：构造选择哪些模型/列的查询；尚未向数据库发送请求
    occupied = select(Booking.slot_id)
    # 将结果保存在 slots：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
    slots = session.exec(
        # 继续完成上面的多行语句：将结果保存在 slots：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
        select(InterviewSlot).where(
            # 继续完成上面的多行语句：将结果保存在 slots：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
            InterviewSlot.employer_id == job.employer_id,
            # 继续完成上面的多行语句：将结果保存在 slots：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
            InterviewSlot.id.not_in(occupied),
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # return 结束本函数并把结果交给调用者：返回排序后的新列表；若提供 key，则按 key 生成的值比较
    return sorted(
        # 继续完成上面的多行语句：return 结束本函数并把结果交给调用者：返回排序后的新列表；若提供 key，则按 key 生成的值比较
        [
            # 继续完成上面的多行语句：return 结束本函数并把结果交给调用者：返回排序后的新列表；若提供 key，则按 key 生成的值比较
            dict(id=s.id, starts_at=utc(s.starts_at), ends_at=utc(s.ends_at))
            # 推导式的遍历部分：每次取出一条记录，交给上面的表达式生成结果
            for s in slots
            # 这里的条件决定选择/保留哪些值；不满足条件的记录不会进入结果
            if utc(s.starts_at) > utc_now()
            # and 表示还必须同时满足这一条条件
            and utc(s.ends_at) - utc(s.starts_at) == timedelta(minutes=30)
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ],
        # 排序时调用此函数/表达式产生比较依据
        key=lambda row: (row["starts_at"], str(row["id"])),
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# 函数 book(session, user, application_id, slot_id)：在数据库事务内先锁申请再锁时段，重新校验资格，确保并发竞争只有一人成功。
# 并发示例：Alice 和 Bob 同时抢同一时段。先拿到时段行锁的人提交预约，另一人等待后看到已占用。
# 两个唯一约束是最后防线：即使其他代码未按约定加锁，也不能提交重复 application_id 或 slot_id。
def book(session: Session, user: User, application_id: uuid.UUID, slot_id: uuid.UUID):
    # try 包住可能失败的步骤；对应 except 负责区分失败原因并处理回滚
    try:
        # 将结果保存在 职位申请：检查申请为 Interviewing 且尚未预约；这是选择和预约时段的共同入口
        application = eligible_application(session, user, application_id, lock=True)
        # 将结果保存在 面试时段：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
        slot = session.exec(
            # 继续完成上面的多行语句：将结果保存在 面试时段：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
            select(InterviewSlot).where(InterviewSlot.id == slot_id).with_for_update()
            # 继续完成上面的多行语句：将结果保存在 面试时段：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
        ).first()
        # if 判断：比较 slot is None；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
        if slot is None:
            # 抛出失败并立即停止成功路径：FlowError(404, 'Slot not found')
            raise FlowError(404, "Slot not found")
        # 将结果保存在 职位：用主键查询 Job；找不到时得到 None
        job = session.get(Job, application.job_id)
        # if 判断：比较 slot.employer_id != job.employer_id；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
        if slot.employer_id != job.employer_id:
            # 抛出失败并立即停止成功路径：FlowError(403, 'Slot belongs to another employer')
            raise FlowError(403, "Slot belongs to another employer")
        # if 判断：比较 utc(slot.starts_at) <= utc_now()；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
        if utc(slot.starts_at) <= utc_now():
            # 抛出失败并立即停止成功路径：FlowError(409, 'Slot is in the past')
            raise FlowError(409, "Slot is in the past")
        # if 判断：比较 utc(slot.ends_at) - utc(slot.starts_at) != timedelta(minutes=30)；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
        if utc(slot.ends_at) - utc(slot.starts_at) != timedelta(minutes=30):
            # 抛出失败并立即停止成功路径：FlowError(409, 'Slot must last 30 minutes')
            raise FlowError(409, "Slot must last 30 minutes")
        # if 判断：执行前面构造的数据库查询/语句，用户值由 ORM 绑定；成立时执行下面缩进的代码
        if session.exec(select(Booking).where(Booking.slot_id == slot_id)).first():
            # 抛出失败并立即停止成功路径：FlowError(409, 'Slot already booked')
            raise FlowError(409, "Slot already booked")
        # 将结果保存在 预约记录：调用 Booking（参数见括号），取得结果或执行相应操作
        booking = Booking(application_id=application_id, slot_id=slot_id)
        # 把对象加入数据库工作区；这一行本身还不等于提交成功
        session.add(booking)
        # 提交整个事务；成功后数据库中的修改才正式生效
        session.commit()
    # except 捕获 IntegrityError；只处理这一类失败，不把所有错误假装成同一原因
    except IntegrityError:
        # 撤销本次未成功提交的修改，并恢复 Session 的可用状态
        session.rollback()
        # if 判断：执行前面构造的数据库查询/语句，用户值由 ORM 绑定；成立时执行下面缩进的代码
        if session.exec(select(Booking).where(Booking.slot_id == slot_id)).first():
            # 抛出失败并立即停止成功路径：FlowError(409, 'Slot already booked')
            raise FlowError(409, "Slot already booked") from None
        # if 判断：执行前面构造的数据库查询/语句，用户值由 ORM 绑定；成立时执行下面缩进的代码
        if session.exec(
            # 继续完成上面的多行语句：if 判断：执行前面构造的数据库查询/语句，用户值由 ORM 绑定；成立时执行下面缩进的代码
            select(Booking).where(Booking.application_id == application_id)
            # 继续完成上面的多行语句：if 判断：执行前面构造的数据库查询/语句，用户值由 ORM 绑定；成立时执行下面缩进的代码
        ).first():
            # 抛出失败并立即停止成功路径：FlowError(409, 'Application already booked')
            raise FlowError(409, "Application already booked") from None
        # raise 将当前异常继续交给调用者，不能吞掉无法解释的数据库故障
        raise
    # except 捕获 (FlowError, SQLAlchemyError)；只处理这一类失败，不把所有错误假装成同一原因
    except (FlowError, SQLAlchemyError):
        # 撤销本次未成功提交的修改，并恢复 Session 的可用状态
        session.rollback()
        # raise 将当前异常继续交给调用者，不能吞掉无法解释的数据库故障
        raise
    # return 结束本函数并把结果交给调用者：用方括号从 application_public(session, application) 取指定字段/元素
    return application_public(session, application)["booking"]


# 函数 employer_applicants(session, user, job_id)：只向职位所属雇主展示申请人技能、分数、状态和预约，绝不返回简历。
def employer_applicants(session: Session, user: User, job_id: uuid.UUID):
    """雇主模块的共享读取接口；永远不包含私有简历。"""
    # 将结果保存在 职位：用主键查询 Job；找不到时得到 None
    job = session.get(Job, job_id)
    # if 判断：比较 job is None；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
    if job is None:
        # 抛出失败并立即停止成功路径：FlowError(404, 'Job not found')
        raise FlowError(404, "Job not found")
    # if 判断：比较 job.employer_id != user.id；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
    if job.employer_id != user.id:
        # 抛出失败并立即停止成功路径：FlowError(403, 'Job belongs to another employer')
        raise FlowError(403, "Job belongs to another employer")
    # 将结果保存在 职位要求的技能：把查询/可迭代结果收集成普通列表
    required = list(
        # 继续完成上面的多行语句：将结果保存在 职位要求的技能：把查询/可迭代结果收集成普通列表
        session.exec(select(JobSkill.name).where(JobSkill.job_id == job.id))
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 将结果保存在 准备返回的记录列表：组装有顺序的列表，方括号内是各个元素
    rows = []
    # for 循环：依次从 session.exec(select(Application).where(Application.job_id == job.id)) 取出元素，保存在 application 后处理
    for application in session.exec(
        # 继续完成上面的多行语句：for 循环：依次从 session.exec(select(Application).where(Application.job_id == job.id)) 取出元素，保存在 application 后处理
        select(Application).where(Application.job_id == job.id)
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ):
        # 将结果保存在 候选人资料：用主键查询 CandidateProfile；找不到时得到 None
        profile = session.get(CandidateProfile, application.candidate_id)
        # 将结果保存在 技术技能列表：返回排序后的新列表；若提供 key，则按 key 生成的值比较
        skills = sorted(s.name for s in profile.skills)
        # 调用 rows.append（参数见括号），取得结果或执行相应操作
        rows.append(
            # 继续完成上面的多行语句：调用 rows.append（参数见括号），取得结果或执行相应操作
            dict(
                # 这一项指定 候选人的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                candidate_id=profile.user_id,
                # 这一项指定 候选人显示名称；逗号分隔同一调用/结构中的各个参数或字段
                display_name=profile.display_name,
                # 这一项指定 技术技能列表；逗号分隔同一调用/结构中的各个参数或字段
                skills=skills,
                # 这一项指定 0～100 的整数匹配分数；逗号分隔同一调用/结构中的各个参数或字段
                score=match_score(skills, required),
                score_kind=SCORE_KIND,
                # 用 ** 展开已有字典的键值，合并到正在组装的返回数据中
                **application_public(session, application),
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            )
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
    # return 结束本函数并把结果交给调用者：返回排序后的新列表；若提供 key，则按 key 生成的值比较
    return sorted(rows, key=applicant_sort_key)
