# 【自动测试】fixture 准备隔离环境，客户端调用真实接口，assert 校验结果；测试不依赖生产数据库。
# 阅读提示：缩进表示代码属于哪个分支；= 保存值，== 比较值；None 表示缺失；类型注解不等于数据库操作。
"""可选真实 PostgreSQL 验证；每次使用独立 schema，不修改业务表。"""

# 导入 os，供后续代码调用；导入不是发起 HTTP 请求
import os

# 导入 uuid，供后续代码调用；导入不是发起 HTTP 请求
import uuid

# 导入 concurrent.futures 中的 ThreadPoolExecutor，供后续代码调用；导入不是发起 HTTP 请求
from concurrent.futures import ThreadPoolExecutor

# 导入 threading 中的 Barrier，供后续代码调用；导入不是发起 HTTP 请求
from threading import Barrier

# 导入 pytest，供后续代码调用；导入不是发起 HTTP 请求
import pytest

# 导入 sqlalchemy 中的 text，供后续代码调用；导入不是发起 HTTP 请求
from sqlalchemy import text

# 导入 sqlmodel 中的 Session、SQLModel、create_engine、select，供后续代码调用；导入不是发起 HTTP 请求
from sqlmodel import Session, SQLModel, create_engine, select


# 条件满足时显式跳过此测试；真实 PostgreSQL 验证需要单独配置测试地址
@pytest.mark.skipif(
    not os.getenv("PIVOT_TEST_DATABASE_URL"),
    # 这一项指定 reason；逗号分隔同一调用/结构中的各个参数或字段
    reason="Set PIVOT_TEST_DATABASE_URL for isolated PostgreSQL verification",
    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
)
# 函数 test_postgres_atomic_booking_and_duplicate_application()：定义独立测试；pytest 会运行它，assert 必须验证实际结果而不是只打印。
def test_postgres_atomic_booking_and_duplicate_application():
    # 导入 app.candidate.seed 中的 seed，供后续代码调用；导入不是发起 HTTP 请求
    from app.candidate.seed import seed

    # 导入 app.candidate.service 中的 FlowError、apply、book，供后续代码调用；导入不是发起 HTTP 请求
    from app.candidate.service import FlowError, apply, book

    # 导入 app.candidate.model 中的 Application、Booking，供后续代码调用；导入不是发起 HTTP 请求
    from app.candidate.model import Application, Booking

    # 导入 app.users.model 中的 User，供后续代码调用；导入不是发起 HTTP 请求
    from app.users.model import User

    # 将结果保存在 url：用方括号从 os.environ 取指定字段/元素
    url = os.environ["PIVOT_TEST_DATABASE_URL"]
    # 将结果保存在 admin：创建连接引擎；URL 指向数据库，具体连接由 Session 使用
    admin = create_engine(url)
    # 将结果保存在 隔离测试使用的 PostgreSQL 命名空间：计算 'candidate_test_' + uuid.uuid4().hex，得到新的值
    schema = "candidate_test_" + uuid.uuid4().hex
    # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
    with admin.begin() as conn:
        # 执行前面构造的数据库查询/语句，用户值由 ORM 绑定
        conn.execute(
            # 继续完成上面的多行语句：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
            text(f'CREATE SCHEMA "{schema}"')
            # 继续完成上面的多行语句：执行前面构造的数据库查询/语句，用户值由 ORM 绑定
        )  # 随机内部标识，不来自用户输入。
    # 将结果保存在 数据库连接引擎：创建连接引擎；URL 指向数据库，具体连接由 Session 使用
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    # try 包住可能失败的步骤；对应 except 负责区分失败原因并处理回滚
    try:
        # 在隔离测试库建立模型中的表；生产结构仍应通过 Alembic 迁移
        SQLModel.metadata.create_all(engine)
        # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
        with Session(engine) as s:
            # 给专用空演示库写入固定 ID 的虚构账户、技能、职位、申请与未来时段
            seed(s)
        # 将结果保存在 barrier：调用 Barrier（参数见括号），取得结果或执行相应操作
        barrier = Barrier(2)

        # 函数 reserve(index)：一个并发客户端尝试预约；每个线程独立 Session，共同等待后开始竞争。
        def reserve(index):
            # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
            with Session(engine) as s:
                # 将结果保存在 已通过认证的账户：用主键查询 User；找不到时得到 None
                user = s.get(User, uuid.UUID(int=index + 1))
                # 让并发线程在此会合，再同时开始竞争
                barrier.wait(timeout=10)
                # try 包住可能失败的步骤；对应 except 负责区分失败原因并处理回滚
                try:
                    # 在数据库事务内先锁申请再锁时段，重新校验资格，确保并发竞争只有一人成功
                    book(s, user, uuid.UUID(int=200 + index), uuid.UUID(int=300))
                    # return 结束本函数并把结果交给调用者：使用固定值 201
                    return 201
                # except 捕获 FlowError；只处理这一类失败，不把所有错误假装成同一原因
                except FlowError as e:
                    # return 结束本函数并把结果交给调用者：组装元组；用于多个排序依据时，从左向右依次比较
                    return e.status, str(e)

        # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
        with ThreadPoolExecutor(max_workers=2) as pool:
            # 将结果保存在 results：把查询/可迭代结果收集成普通列表
            results = list(pool.map(reserve, [0, 1]))
        # assert 检查测试预期：比较 results.count(201) == 1；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        assert results.count(201) == 1
        # assert 检查测试预期：比较 (409, 'Slot already booked') in results；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        assert (409, "Slot already booked") in results
        # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
        with Session(engine) as s:
            # assert 检查测试预期：比较 len(s.exec(select(Booking)).all()) == 1；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
            assert len(s.exec(select(Booking)).all()) == 1
        # 将结果保存在 barrier：调用 Barrier（参数见括号），取得结果或执行相应操作
        barrier = Barrier(2)

        # 函数 submit(_)：一个并发客户端尝试申请相同职位，观察数据库最终去重结果。
        def submit(_):
            # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
            with Session(engine) as s:
                # 将结果保存在 已通过认证的账户：用主键查询 User；找不到时得到 None
                user = s.get(User, uuid.UUID(int=1))
                # 让并发线程在此会合，再同时开始竞争
                barrier.wait(timeout=10)
                # try 包住可能失败的步骤；对应 except 负责区分失败原因并处理回滚
                try:
                    # 创建状态固定为 Pending 的本人申请，数据库唯一约束防止重复提交
                    apply(s, user, uuid.UUID(int=104))
                    # return 结束本函数并把结果交给调用者：使用固定值 201
                    return 201
                # except 捕获 FlowError；只处理这一类失败，不把所有错误假装成同一原因
                except FlowError as e:
                    # return 结束本函数并把结果交给调用者：读取 e 的 状态值 属性
                    return e.status

        # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
        with ThreadPoolExecutor(max_workers=2) as pool:
            # 将结果保存在 results：把查询/可迭代结果收集成普通列表
            results = list(pool.map(submit, [0, 1]))
        # assert 检查测试预期：比较 sorted(results) == [201, 409]；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
        assert sorted(results) == [201, 409]
        # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
        with Session(engine) as s:
            # assert 检查测试预期：比较 len(s.exec(select(Application).where(Application.job_id == uuid.UUID(int=104))).all()) == 1；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
            assert (
                # 继续完成上面的多行语句：assert 检查测试预期：比较 len(s.exec(select(Application).where(Application.job_id == uuid.UUID(int=104))).all()) == 1；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
                len(
                    # 继续完成上面的多行语句：assert 检查测试预期：比较 len(s.exec(select(Application).where(Application.job_id == uuid.UUID(int=104))).all()) == 1；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
                    s.exec(
                        # 继续完成上面的多行语句：assert 检查测试预期：比较 len(s.exec(select(Application).where(Application.job_id == uuid.UUID(int=104))).all()) == 1；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
                        select(Application).where(
                            # 继续完成上面的多行语句：assert 检查测试预期：比较 len(s.exec(select(Application).where(Application.job_id == uuid.UUID(int=104))).all()) == 1；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
                            Application.job_id == uuid.UUID(int=104)
                            # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
                        )
                        # 继续完成上面的多行语句：assert 检查测试预期：比较 len(s.exec(select(Application).where(Application.job_id == uuid.UUID(int=104))).all()) == 1；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
                    ).all()
                    # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
                )
                # 继续完成上面的多行语句：assert 检查测试预期：比较 len(s.exec(select(Application).where(Application.job_id == uuid.UUID(int=104))).all()) == 1；结果为 True/False，决定分支或测试是否通过；不成立则测试失败
                == 1
                # 结束上面跨多行的参数/容器；这些行共同组成同一条语句，尚未开始新的操作
            )
    # finally：无论成功或失败都执行，确保关闭资源或结束等待状态
    finally:
        # 释放连接池，避免测试结束后留下数据库连接
        engine.dispose()
        # with 管理临时资源/测试上下文；即使中途发生异常，退出时仍执行清理
        with admin.begin() as conn:
            # 执行前面构造的数据库查询/语句，用户值由 ORM 绑定
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        # 释放连接池，避免测试结束后留下数据库连接
        admin.dispose()
