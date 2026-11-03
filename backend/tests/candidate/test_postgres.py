"""可选真实 PostgreSQL 验证；每次使用独立 schema，不修改业务表。"""

import os

import uuid

from concurrent.futures import ThreadPoolExecutor

from threading import Barrier

import pytest

from sqlalchemy import text

from sqlmodel import Session, SQLModel, create_engine, select


# 条件满足时显式跳过此测试；真实 PostgreSQL 验证需要单独配置测试地址
@pytest.mark.skipif(
    not os.getenv("PIVOT_TEST_DATABASE_URL"),
    reason="Set PIVOT_TEST_DATABASE_URL for isolated PostgreSQL verification",
)
def test_postgres_atomic_booking_and_duplicate_application():
    from app.candidate.seed import seed

    from app.candidate.service import FlowError, apply, book

    from app.candidate.model import Application, Booking

    from app.users.model import User

    url = os.environ["PIVOT_TEST_DATABASE_URL"]
    admin = create_engine(url)
    schema = "candidate_test_" + uuid.uuid4().hex
    with admin.begin() as conn:
        # 执行前面构造的数据库查询/语句，用户值由 ORM 绑定
        conn.execute(
            text(f'CREATE SCHEMA "{schema}"')
        )  # 随机内部标识，不来自用户输入。
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        SQLModel.metadata.create_all(engine)
        with Session(engine) as s:
            # 给专用空演示库写入固定 ID 的虚构账户、技能、职位、申请与未来时段
            seed(s)
        barrier = Barrier(2)

        def reserve(index):
            with Session(engine) as s:
                user = s.get(User, uuid.UUID(int=index + 1))
                # 让并发线程在此会合，再同时开始竞争
                barrier.wait(timeout=10)
                try:
                    # 在数据库事务内先锁申请再锁时段，重新校验资格，确保并发竞争只有一人成功
                    book(s, user, uuid.UUID(int=200 + index), uuid.UUID(int=300))
                    return 201
                except FlowError as e:
                    return e.status, str(e)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve, [0, 1]))
        assert results.count(201) == 1
        assert (409, "Slot already booked") in results
        with Session(engine) as s:
            assert len(s.exec(select(Booking)).all()) == 1
        barrier = Barrier(2)

        def submit(_):
            with Session(engine) as s:
                user = s.get(User, uuid.UUID(int=1))
                # 让并发线程在此会合，再同时开始竞争
                barrier.wait(timeout=10)
                try:
                    # 创建状态固定为 Pending 的本人申请，数据库唯一约束防止重复提交
                    apply(s, user, uuid.UUID(int=104))
                    return 201
                except FlowError as e:
                    return e.status

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, [0, 1]))
        assert sorted(results) == [201, 409]
        with Session(engine) as s:
            assert (
                len(
                    s.exec(
                        select(Application).where(
                            Application.job_id == uuid.UUID(int=104)
                        )
                    ).all()
                )
                == 1
            )
    # finally：无论成功或失败都执行，确保关闭资源或结束等待状态
    finally:
        engine.dispose()
        with admin.begin() as conn:
            # 执行前面构造的数据库查询/语句，用户值由 ORM 绑定
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
