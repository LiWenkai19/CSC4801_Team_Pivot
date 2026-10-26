# 【演示数据】只使用虚构用户。固定 ID 便于重现；未来面试日期相对当前 UTC 生成。重置不是普通启动步骤。
# 阅读提示：缩进表示代码属于哪个分支；= 保存值，== 比较值；None 表示缺失；类型注解不等于数据库操作。
"""只针对本地演示数据库的显式重置命令，不在服务启动时执行。"""

# 导入 argparse，供后续代码调用；导入不是发起 HTTP 请求
import argparse

# 导入 uuid，供后续代码调用；导入不是发起 HTTP 请求
import uuid

# 导入 datetime 中的 timedelta，供后续代码调用；导入不是发起 HTTP 请求
from datetime import timedelta

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

# 导入 app.db.session 中的 engine，供后续代码调用；导入不是发起 HTTP 请求
from app.db.session import engine

# 导入 app.users.model 中的 CandidateProfile、CandidateSkill、EmployerProfile、Role、User、utc_now，供后续代码调用；导入不是发起 HTTP 请求
from app.users.model import (
    # 继续导入 CandidateProfile，与上面的 from/import 属于同一语句
    CandidateProfile,
    # 继续导入 CandidateSkill，与上面的 from/import 属于同一语句
    CandidateSkill,
    # 继续导入 EmployerProfile，与上面的 from/import 属于同一语句
    EmployerProfile,
    # 继续导入 Role，与上面的 from/import 属于同一语句
    Role,
    # 继续导入 User，与上面的 from/import 属于同一语句
    User,
    # 继续导入 utc_now，与上面的 from/import 属于同一语句
    utc_now,
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)

# 导入 app.users.security 中的 hash_password，供后续代码调用；导入不是发起 HTTP 请求
from app.users.security import hash_password


# 函数 seed(session)：给专用空演示库写入固定 ID 的虚构账户、技能、职位、申请与未来时段。
def seed(session: Session):
    # if 判断：比较 session.exec(select(User)).first() is not None；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
    if session.exec(select(User)).first() is not None:
        # 抛出失败并立即停止成功路径：ValueError('Database is not empty; use --reset --confirm-demo-reset for a dedicated demo database')
        raise ValueError(
            # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
            "Database is not empty; use --reset --confirm-demo-reset for a dedicated demo database"
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
    # 将结果保存在 users：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
    users = [
        # 继续完成上面的多行语句：将结果保存在 users：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
        User(
            # 这一项指定 记录的唯一标识；逗号分隔同一调用/结构中的各个参数或字段
            id=uuid.UUID(int=i + 1),
            # 这一项指定 账户邮箱；逗号分隔同一调用/结构中的各个参数或字段
            email=email,
            # 这一项指定 role；逗号分隔同一调用/结构中的各个参数或字段
            role=Role.Candidate if i in (0, 1, 4) else Role.Employer,
            # 这一项指定 不可逆的密码哈希；逗号分隔同一调用/结构中的各个参数或字段
            hashed_password=hash_password("Demo-only-123!"),
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
        # 推导式的遍历部分：每次取出一条记录，交给上面的表达式生成结果
        for i, email in enumerate(
            # 继续完成上面的多行语句：将结果保存在 users：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
            [
                # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
                "alice@example.com",
                # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
                "bob@example.com",
                # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
                "employer1@example.com",
                # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
                "employer2@example.com",
                # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
                "carol@example.com",
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ]
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ]
    # 把一组对象加入 Session，等待统一提交
    session.add_all(users)
    # 把暂存修改发给数据库检查约束，但尚未正式提交事务
    session.flush()
    # 把一组对象加入 Session，等待统一提交
    session.add_all(
        # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
        [
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            CandidateProfile(
                # 这一项指定 资料所有者的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                user_id=users[0].id,
                # 这一项指定 候选人显示名称；逗号分隔同一调用/结构中的各个参数或字段
                display_name="Alice",
                # 这一项指定 只有本人可读写的纯文本简历；逗号分隔同一调用/结构中的各个参数或字段
                resume_text="Fictional local demo resume.",
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            CandidateProfile(
                # 这一项指定 资料所有者的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                user_id=users[1].id,
                # 这一项指定 候选人显示名称；逗号分隔同一调用/结构中的各个参数或字段
                display_name="Bob",
                # 这一项指定 只有本人可读写的纯文本简历；逗号分隔同一调用/结构中的各个参数或字段
                resume_text="Fictional local demo resume.",
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            CandidateProfile(
                # 这一项指定 资料所有者的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                user_id=users[4].id,
                # 这一项指定 候选人显示名称；逗号分隔同一调用/结构中的各个参数或字段
                display_name="Carol",
                # 这一项指定 只有本人可读写的纯文本简历；逗号分隔同一调用/结构中的各个参数或字段
                resume_text="Fictional Rust candidate.",
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            EmployerProfile(
                # 这一项指定 资料所有者的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                user_id=users[2].id,
                # 这一项指定 公司名称；逗号分隔同一调用/结构中的各个参数或字段
                company_name="Demo Labs",
                # 这一项指定 公司介绍；逗号分隔同一调用/结构中的各个参数或字段
                company_description="Local demo",
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            EmployerProfile(
                # 这一项指定 资料所有者的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                user_id=users[3].id,
                # 这一项指定 公司名称；逗号分隔同一调用/结构中的各个参数或字段
                company_name="Example Studio",
                # 这一项指定 公司介绍；逗号分隔同一调用/结构中的各个参数或字段
                company_description="Local demo",
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ]
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 把暂存修改发给数据库检查约束，但尚未正式提交事务
    session.flush()
    # 把一组对象加入 Session，等待统一提交
    session.add_all(
        # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
        [CandidateSkill(candidate_id=users[0].id, name=s) for s in ["python", "sql"]]
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 把对象加入数据库工作区；这一行本身还不等于提交成功
    session.add(CandidateSkill(candidate_id=users[1].id, name="python"))
    # 把对象加入数据库工作区；这一行本身还不等于提交成功
    session.add(CandidateSkill(candidate_id=users[4].id, name="rust"))
    # 将结果保存在 titles：组装有顺序的列表，方括号内是各个元素
    titles = [
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "Backend Engineer",
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "Rust Engineer",
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "Open Role",
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "Data Engineer",
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "Platform Engineer",
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ]
    # 将结果保存在 jobs：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
    jobs = [
        # 继续完成上面的多行语句：将结果保存在 jobs：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
        Job(
            # 这一项指定 记录的唯一标识；逗号分隔同一调用/结构中的各个参数或字段
            id=uuid.UUID(int=100 + i),
            # 这一项指定 雇主账户 ID；逗号分隔同一调用/结构中的各个参数或字段
            employer_id=users[2 if i < 4 else 3].id,
            # 这一项指定 职位标题；逗号分隔同一调用/结构中的各个参数或字段
            title=t,
            # 这一项指定 职位描述；逗号分隔同一调用/结构中的各个参数或字段
            description=f"{t}: fictional role for local demonstration.",
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
        # 推导式的遍历部分：每次取出一条记录，交给上面的表达式生成结果
        for i, t in enumerate(titles)
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    ]
    # 把一组对象加入 Session，等待统一提交
    session.add_all(jobs)
    # 把暂存修改发给数据库检查约束，但尚未正式提交事务
    session.flush()
    # 将结果保存在 职位要求的技能：组装有顺序的列表，方括号内是各个元素
    required = [["python", "sql"], ["rust"], [], ["python", "sql"], ["sql"]]
    # 把一组对象加入 Session，等待统一提交
    session.add_all(
        # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
        [
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            JobSkill(job_id=job.id, name=s)
            # 推导式的遍历部分：每次取出一条记录，交给上面的表达式生成结果
            for job, skills in zip(jobs, required)
            # 推导式的遍历部分：每次取出一条记录，交给上面的表达式生成结果
            for s in skills
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ]
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 把一组对象加入 Session，等待统一提交
    session.add_all(
        # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
        [
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            Application(
                # 这一项指定 记录的唯一标识；逗号分隔同一调用/结构中的各个参数或字段
                id=uuid.UUID(int=200),
                # 这一项指定 候选人的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                candidate_id=users[0].id,
                # 这一项指定 职位 ID；逗号分隔同一调用/结构中的各个参数或字段
                job_id=jobs[0].id,
                # 这一项指定 状态值；逗号分隔同一调用/结构中的各个参数或字段
                status=ApplicationStatus.Interviewing,
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            Application(
                # 这一项指定 记录的唯一标识；逗号分隔同一调用/结构中的各个参数或字段
                id=uuid.UUID(int=201),
                # 这一项指定 候选人的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                candidate_id=users[1].id,
                # 这一项指定 职位 ID；逗号分隔同一调用/结构中的各个参数或字段
                job_id=jobs[0].id,
                # 这一项指定 状态值；逗号分隔同一调用/结构中的各个参数或字段
                status=ApplicationStatus.Interviewing,
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            Application(
                # 这一项指定 记录的唯一标识；逗号分隔同一调用/结构中的各个参数或字段
                id=uuid.UUID(int=202),
                # 这一项指定 候选人的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                candidate_id=users[0].id,
                # 这一项指定 职位 ID；逗号分隔同一调用/结构中的各个参数或字段
                job_id=jobs[1].id,
                # 这一项指定 状态值；逗号分隔同一调用/结构中的各个参数或字段
                status=ApplicationStatus.Rejected,
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            Application(
                # 这一项指定 记录的唯一标识；逗号分隔同一调用/结构中的各个参数或字段
                id=uuid.UUID(int=203),
                # 这一项指定 候选人的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                candidate_id=users[0].id,
                # 这一项指定 职位 ID；逗号分隔同一调用/结构中的各个参数或字段
                job_id=jobs[2].id,
                # 这一项指定 状态值；逗号分隔同一调用/结构中的各个参数或字段
                status=ApplicationStatus.Accepted,
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            Application(
                # 这一项指定 记录的唯一标识；逗号分隔同一调用/结构中的各个参数或字段
                id=uuid.UUID(int=204),
                # 这一项指定 候选人的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                candidate_id=users[0].id,
                # 这一项指定 职位 ID；逗号分隔同一调用/结构中的各个参数或字段
                job_id=jobs[3].id,
                # 这一项指定 状态值；逗号分隔同一调用/结构中的各个参数或字段
                status=ApplicationStatus.Pending,
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ]
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 将结果保存在 start：调用 (utc_now() + timedelta(days=2)).replace（参数见括号），取得结果或执行相应操作
    start = (utc_now() + timedelta(days=2)).replace(
        # 这一项指定 hour；逗号分隔同一调用/结构中的各个参数或字段
        hour=2,
        minute=0,
        second=0,
        microsecond=0,
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 把对象加入数据库工作区；这一行本身还不等于提交成功
    session.add(
        # 继续完成上面的多行语句：把对象加入数据库工作区；这一行本身还不等于提交成功
        InterviewSlot(
            # 这一项指定 记录的唯一标识；逗号分隔同一调用/结构中的各个参数或字段
            id=uuid.UUID(int=300),
            # 这一项指定 雇主账户 ID；逗号分隔同一调用/结构中的各个参数或字段
            employer_id=users[2].id,
            # 这一项指定 带时区的面试开始时间；逗号分隔同一调用/结构中的各个参数或字段
            starts_at=start,
            # 这一项指定 带时区的面试结束时间；逗号分隔同一调用/结构中的各个参数或字段
            ends_at=start + timedelta(minutes=30),
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )
    # 提交整个事务；成功后数据库中的修改才正式生效
    # 第二个时段用于演示发生竞争冲突后，候选人仍能重新选择并预约。
    session.add(
        InterviewSlot(
            id=uuid.UUID(int=301),
            employer_id=users[2].id,
            starts_at=start + timedelta(hours=1),
            ends_at=start + timedelta(hours=1, minutes=30),
        )
    )
    session.commit()


# 函数 main()：解析演示重置参数；只有显式确认后才删除配置库内的应用记录。
def main():
    # 将结果保存在 parser：调用 argparse.ArgumentParser（参数见括号），取得结果或执行相应操作
    parser = argparse.ArgumentParser()
    # 调用 parser.add_argument（参数见括号），取得结果或执行相应操作
    parser.add_argument("--reset", action="store_true")
    # 调用 parser.add_argument（参数见括号），取得结果或执行相应操作
    parser.add_argument("--confirm-demo-reset", action="store_true")
    # 将结果保存在 args：调用 parser.parse_args（参数见括号），取得结果或执行相应操作
    args = parser.parse_args()
    # if 判断：组合多个判断；and 要全部成立，or 只需其中一个成立；成立时执行下面缩进的代码
    if args.reset and not args.confirm_demo_reset:
        # 调用 parser.error（参数见括号），取得结果或执行相应操作
        parser.error(
            # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
            "Reset requires --confirm-demo-reset; all application records will be deleted"
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with Session(engine) as session:
        # if 判断：读取 args 的 reset 属性；成立时执行下面缩进的代码
        if args.reset:
            # for 循环：依次从 [Booking, InterviewSlot, Application, JobSkill, Job, CandidateSkill, CandidateProfile, EmployerProfile, User] 取出元素，保存在 model 后处理
            for model in [
                # 继续完成上面的多行语句：for 循环：依次从 [Booking, InterviewSlot, Application, JobSkill, Job, CandidateSkill, CandidateProfile, EmployerProfile, User] 取出元素，保存在 model 后处理
                Booking,
                # 继续完成上面的多行语句：for 循环：依次从 [Booking, InterviewSlot, Application, JobSkill, Job, CandidateSkill, CandidateProfile, EmployerProfile, User] 取出元素，保存在 model 后处理
                InterviewSlot,
                # 继续完成上面的多行语句：for 循环：依次从 [Booking, InterviewSlot, Application, JobSkill, Job, CandidateSkill, CandidateProfile, EmployerProfile, User] 取出元素，保存在 model 后处理
                Application,
                # 继续完成上面的多行语句：for 循环：依次从 [Booking, InterviewSlot, Application, JobSkill, Job, CandidateSkill, CandidateProfile, EmployerProfile, User] 取出元素，保存在 model 后处理
                JobSkill,
                # 继续完成上面的多行语句：for 循环：依次从 [Booking, InterviewSlot, Application, JobSkill, Job, CandidateSkill, CandidateProfile, EmployerProfile, User] 取出元素，保存在 model 后处理
                Job,
                # 继续完成上面的多行语句：for 循环：依次从 [Booking, InterviewSlot, Application, JobSkill, Job, CandidateSkill, CandidateProfile, EmployerProfile, User] 取出元素，保存在 model 后处理
                CandidateSkill,
                # 继续完成上面的多行语句：for 循环：依次从 [Booking, InterviewSlot, Application, JobSkill, Job, CandidateSkill, CandidateProfile, EmployerProfile, User] 取出元素，保存在 model 后处理
                CandidateProfile,
                # 继续完成上面的多行语句：for 循环：依次从 [Booking, InterviewSlot, Application, JobSkill, Job, CandidateSkill, CandidateProfile, EmployerProfile, User] 取出元素，保存在 model 后处理
                EmployerProfile,
                # 继续完成上面的多行语句：for 循环：依次从 [Booking, InterviewSlot, Application, JobSkill, Job, CandidateSkill, CandidateProfile, EmployerProfile, User] 取出元素，保存在 model 后处理
                User,
                # 继续完成上面的多行语句：for 循环：依次从 [Booking, InterviewSlot, Application, JobSkill, Job, CandidateSkill, CandidateProfile, EmployerProfile, User] 取出元素，保存在 model 后处理
            ]:
                # for 循环：依次从 session.exec(select(model)) 取出元素，保存在 row 后处理
                for row in session.exec(select(model)):
                    # 准备删除指定记录；最终是否生效取决于事务提交
                    session.delete(row)
                # 把暂存修改发给数据库检查约束，但尚未正式提交事务
                session.flush()
        # 给专用空演示库写入固定 ID 的虚构账户、技能、职位、申请与未来时段
        seed(session)
    # 输出本地演示操作的结果提示，不输出真实密钥
    print(
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "Local demo ready: alice@example.com / bob@example.com; password Demo-only-123!"
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )


# if 判断：比较 __name__ == '__main__'；结果为 True/False，决定分支或测试是否通过；成立时执行下面缩进的代码
if __name__ == "__main__":
    # 解析演示重置参数；只有显式确认后才删除配置库内的应用记录
    main()
