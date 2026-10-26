# 【自动测试】fixture 准备隔离环境，客户端调用真实接口，assert 校验结果；测试不依赖生产数据库。
# 阅读提示：缩进表示代码属于哪个分支；= 保存值，== 比较值；None 表示缺失；类型注解不等于数据库操作。
# 导入 os，供后续代码调用；导入不是发起 HTTP 请求
import os

# 导入 uuid，供后续代码调用；导入不是发起 HTTP 请求
import uuid

# 导入 datetime 中的 timedelta，供后续代码调用；导入不是发起 HTTP 请求
from datetime import timedelta

# 导入 pytest，供后续代码调用；导入不是发起 HTTP 请求
import pytest

# 导入 fastapi.testclient 中的 TestClient，供后续代码调用；导入不是发起 HTTP 请求
from fastapi.testclient import TestClient

# 导入 sqlalchemy 中的 event，供后续代码调用；导入不是发起 HTTP 请求
from sqlalchemy import event

# 导入 sqlalchemy.pool 中的 StaticPool，供后续代码调用；导入不是发起 HTTP 请求
from sqlalchemy.pool import StaticPool

# 导入 sqlmodel 中的 Session、SQLModel、create_engine，供后续代码调用；导入不是发起 HTTP 请求
from sqlmodel import Session, SQLModel, create_engine

# 调用 os.environ.update（参数见括号），取得结果或执行相应操作
os.environ.update(
    # 这一项指定 应用名称；逗号分隔同一调用/结构中的各个参数或字段
    APP_NAME="Isolated tests",
    # 这一项指定 JWT 签名密钥，从本地环境配置读取；逗号分隔同一调用/结构中的各个参数或字段
    SECRET_KEY="isolated-test-key-with-at-least-32-characters",
    # 这一项指定 JWT 签名算法；逗号分隔同一调用/结构中的各个参数或字段
    ALGORITHM="HS256",
    # 这一项指定 令牌有效分钟数；逗号分隔同一调用/结构中的各个参数或字段
    ACCESS_TOKEN_EXPIRE_MINUTES="10",
    # 这一项指定 数据库连接地址；逗号分隔同一调用/结构中的各个参数或字段
    DATABASE_URL="postgresql+psycopg://test:test@127.0.0.1:1/test",
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)


# 注册 pytest 测试夹具，测试通过同名参数自动获取它
@pytest.fixture
# 函数 flow()：搭建隔离数据库和真实接口，测试结果不会写入业务库。
def flow():
    # 导入 app.main 中的 app，供后续代码调用；导入不是发起 HTTP 请求
    from app.candidate_main import app

    # 导入 app.db.session 中的 get_db，供后续代码调用；导入不是发起 HTTP 请求
    from app.db.session import get_db

    # 导入 app.candidate.model 中的 Application、ApplicationStatus、InterviewSlot、Job、JobSkill，供后续代码调用；导入不是发起 HTTP 请求
    from app.candidate.model import (
        # 继续导入 Application，与上面的 from/import 属于同一语句
        Application,
        # 继续导入 ApplicationStatus，与上面的 from/import 属于同一语句
        ApplicationStatus,
        # 继续导入 InterviewSlot，与上面的 from/import 属于同一语句
        InterviewSlot,
        # 继续导入 Job，与上面的 from/import 属于同一语句
        Job,
        # 继续导入 JobSkill，与上面的 from/import 属于同一语句
        JobSkill,
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )

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

    # 导入 app.users.security 中的 create_access_token、hash_password，供后续代码调用；导入不是发起 HTTP 请求
    from app.users.security import create_access_token, hash_password

    # 将结果保存在 数据库连接引擎：创建连接引擎；URL 指向数据库，具体连接由 Session 使用
    engine = create_engine(
        # 固定文字/字段名属于当前参数列表或数据容器，不会单独执行
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
    )

    # 监听数据库事件，让下面函数在对应事件发生时执行
    @event.listens_for(engine, "connect")
    # 函数 foreign_keys(connection, _)：启用 SQLite 外键约束，让单元测试不会误接受无效关联。
    def foreign_keys(connection, _):
        # 执行前面构造的数据库查询/语句，用户值由 ORM 绑定
        connection.execute("PRAGMA foreign_keys=ON")

    # 在隔离测试库建立模型中的表；生产结构仍应通过 Alembic 迁移
    SQLModel.metadata.create_all(engine)
    # 将结果保存在 password_hash：使用 Argon2 的随机盐生成密码哈希，不能用普通 SHA-256 代替
    password_hash = hash_password("demo-password")
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with Session(engine) as session:
        # 将结果保存在 users：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
        users = [
            # 继续完成上面的多行语句：将结果保存在 users：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
            User(
                # 这一项指定 账户邮箱；逗号分隔同一调用/结构中的各个参数或字段
                email=f"user{i}@example.com",
                # 这一项指定 不可逆的密码哈希；逗号分隔同一调用/结构中的各个参数或字段
                hashed_password=password_hash,
                # 这一项指定 role；逗号分隔同一调用/结构中的各个参数或字段
                role=Role.Candidate if i < 2 else Role.Employer,
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            )
            # 推导式的遍历部分：每次取出一条记录，交给上面的表达式生成结果
            for i in range(4)
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ]
        # 把一组对象加入 Session，等待统一提交
        session.add_all(users)
        # 把暂存修改发给数据库检查约束，但尚未正式提交事务
        session.flush()
        # 将结果保存在 ids：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
        ids = [u.id for u in users]
        # 把一组对象加入 Session，等待统一提交
        session.add_all(
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            [
                # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
                CandidateProfile(
                    # 这一项指定 资料所有者的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                    user_id=ids[0],
                    display_name="Alice",
                    resume_text="Private\nResume",
                    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
                ),
                # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
                CandidateProfile(user_id=ids[1], display_name="Bob"),
                # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
                EmployerProfile(user_id=ids[2], company_name="Company A"),
                # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
                EmployerProfile(user_id=ids[3], company_name="Company B"),
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ]
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
        # 把暂存修改发给数据库检查约束，但尚未正式提交事务
        session.flush()
        # 把一组对象加入 Session，等待统一提交
        session.add_all(
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            [
                # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
                CandidateSkill(candidate_id=ids[0], name="python"),
                # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
                CandidateSkill(candidate_id=ids[0], name="sql"),
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ]
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
        # 将结果保存在 jobs：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
        jobs = [
            # 继续完成上面的多行语句：将结果保存在 jobs：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
            Job(
                # 这一项指定 记录的唯一标识；逗号分隔同一调用/结构中的各个参数或字段
                id=uuid.UUID(int=10 + i),
                # 这一项指定 雇主账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                employer_id=ids[2],
                # 这一项指定 职位标题；逗号分隔同一调用/结构中的各个参数或字段
                title=title,
                # 这一项指定 职位描述；逗号分隔同一调用/结构中的各个参数或字段
                description="Description",
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            )
            # 推导式的遍历部分：每次取出一条记录，交给上面的表达式生成结果
            for i, title in enumerate(["alpha", "Alpha", "Beta", "Empty", "Deleted"])
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ]
        # 将结果保存在 jobs[-1].is_deleted：使用固定值 True
        jobs[-1].is_deleted = True
        # 把一组对象加入 Session，等待统一提交
        session.add_all(jobs)
        # 把暂存修改发给数据库检查约束，但尚未正式提交事务
        session.flush()
        # 把一组对象加入 Session，等待统一提交
        session.add_all(
            # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
            [
                # 继续完成上面的多行语句：把一组对象加入 Session，等待统一提交
                JobSkill(job_id=jobs[i].id, name=name)
                # 推导式的遍历部分：每次取出一条记录，交给上面的表达式生成结果
                for i in range(3)
                # 推导式的遍历部分：每次取出一条记录，交给上面的表达式生成结果
                for name in ["python", "sql"]
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ]
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )
        # 将结果保存在 applications：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
        applications = [
            # 继续完成上面的多行语句：将结果保存在 applications：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
            Application(
                # 这一项指定 候选人的账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                candidate_id=ids[i],
                # 这一项指定 职位 ID；逗号分隔同一调用/结构中的各个参数或字段
                job_id=jobs[0].id,
                # 这一项指定 状态值；逗号分隔同一调用/结构中的各个参数或字段
                status=ApplicationStatus.Interviewing,
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            )
            # 推导式的遍历部分：每次取出一条记录，交给上面的表达式生成结果
            for i in range(2)
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ]
        # 把一组对象加入 Session，等待统一提交
        session.add_all(applications)
        # 将结果保存在 start：计算 utc_now() + timedelta(days=1)，得到新的值
        start = utc_now() + timedelta(days=1)
        # 将结果保存在 slots：组装有顺序的列表，方括号内是各个元素
        slots = [
            # 继续完成上面的多行语句：将结果保存在 slots：组装有顺序的列表，方括号内是各个元素
            InterviewSlot(
                # 这一项指定 雇主账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                employer_id=ids[2],
                # 这一项指定 带时区的面试开始时间；逗号分隔同一调用/结构中的各个参数或字段
                starts_at=start,
                # 这一项指定 带时区的面试结束时间；逗号分隔同一调用/结构中的各个参数或字段
                ends_at=start + timedelta(minutes=30),
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 继续完成上面的多行语句：将结果保存在 slots：组装有顺序的列表，方括号内是各个元素
            InterviewSlot(
                # 这一项指定 雇主账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                employer_id=ids[3],
                # 这一项指定 带时区的面试开始时间；逗号分隔同一调用/结构中的各个参数或字段
                starts_at=start,
                # 这一项指定 带时区的面试结束时间；逗号分隔同一调用/结构中的各个参数或字段
                ends_at=start + timedelta(minutes=30),
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 继续完成上面的多行语句：将结果保存在 slots：组装有顺序的列表，方括号内是各个元素
            InterviewSlot(
                # 这一项指定 雇主账户 ID；逗号分隔同一调用/结构中的各个参数或字段
                employer_id=ids[2],
                # 这一项指定 带时区的面试开始时间；逗号分隔同一调用/结构中的各个参数或字段
                starts_at=start - timedelta(days=2),
                # 这一项指定 带时区的面试结束时间；逗号分隔同一调用/结构中的各个参数或字段
                ends_at=start - timedelta(days=2) + timedelta(minutes=30),
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            ),
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ]
        # 把一组对象加入 Session，等待统一提交
        session.add_all(slots)
        # 提交整个事务；成功后数据库中的修改才正式生效
        session.commit()
        # 将结果保存在 HTTP 请求头（包含 Bearer 令牌）：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
        headers = [
            # 继续完成上面的多行语句：将结果保存在 HTTP 请求头（包含 Bearer 令牌）：用推导式依次处理元素；for 决定遍历对象，if（若有）决定保留条件
            {"Authorization": f"Bearer {create_access_token(u.email)}"}
            for u in users
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        ]
        # 将结果保存在 执行结果：组装只含指定字段的字典，随后作为 JSON 返回或展示
        result = dict(
            # 这一项指定 数据库连接引擎；逗号分隔同一调用/结构中的各个参数或字段
            engine=engine,
            # 这一项指定 ids；逗号分隔同一调用/结构中的各个参数或字段
            ids=ids,
            # 带上测试账户的认证请求头，使请求以指定身份执行
            headers=headers,
            # 这一项指定 jobs；逗号分隔同一调用/结构中的各个参数或字段
            jobs=[j.id for j in jobs],
            # 这一项指定 applications；逗号分隔同一调用/结构中的各个参数或字段
            applications=[a.id for a in applications],
            # 这一项指定 slots；逗号分隔同一调用/结构中的各个参数或字段
            slots=[s.id for s in slots],
            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
        )

    # 函数 database()：向测试应用提供隔离 Session，替代生产数据库依赖。
    def database():
        # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
        with Session(engine) as session:
            # yield 暂时把资源/夹具交给使用方，使用结束后从此处继续清理
            yield session

    # 将结果保存在 app.dependency_overrides[get_db]：使用 database
    app.dependency_overrides[get_db] = database
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with TestClient(app) as client:
        # 将结果保存在 result['client']：使用 模拟发送 HTTP 请求的测试客户端
        result["client"] = client
        # yield 暂时把资源/夹具交给使用方，使用结束后从此处继续清理
        yield result
    # 调用 app.dependency_overrides.clear（参数见括号），取得结果或执行相应操作
    app.dependency_overrides.clear()
    # 释放连接池，避免测试结束后留下数据库连接
    engine.dispose()
