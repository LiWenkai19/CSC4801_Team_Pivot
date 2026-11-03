import os

import uuid

from datetime import timedelta

import pytest

from fastapi.testclient import TestClient

from sqlalchemy import event

from sqlalchemy.pool import StaticPool

from sqlmodel import Session, SQLModel, create_engine

os.environ.update(
    APP_NAME="Isolated tests",
    SECRET_KEY="isolated-test-key-with-at-least-32-characters",
    ALGORITHM="HS256",
    ACCESS_TOKEN_EXPIRE_MINUTES="10",
    DATABASE_URL="postgresql+psycopg://test:test@127.0.0.1:1/test",
)


@pytest.fixture
def flow():
    from app.main import app

    from app.db.session import get_db

    from app.candidate.model import (
        Application,
        ApplicationStatus,
        InterviewSlot,
        Job,
        JobSkill,
    )

    from app.users.model import (
        CandidateProfile,
        CandidateSkill,
        EmployerProfile,
        Role,
        User,
        utc_now,
    )

    from app.users.security import create_access_token, hash_password

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # 监听数据库事件，让下面函数在对应事件发生时执行
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        # 执行前面构造的数据库查询/语句，用户值由 ORM 绑定
        connection.execute("PRAGMA foreign_keys=ON")

    SQLModel.metadata.create_all(engine)
    password_hash = hash_password("demo-password")
    with Session(engine) as session:
        users = [
            User(
                email=f"user{i}@example.com",
                hashed_password=password_hash,
                role=Role.Candidate if i < 2 else Role.Employer,
            )
            for i in range(4)
        ]
        session.add_all(users)
        session.flush()
        ids = [u.id for u in users]
        session.add_all(
            [
                CandidateProfile(
                    user_id=ids[0],
                    display_name="Alice",
                    resume_text="Private\nResume",
                ),
                CandidateProfile(user_id=ids[1], display_name="Bob"),
                EmployerProfile(user_id=ids[2], company_name="Company A"),
                EmployerProfile(user_id=ids[3], company_name="Company B"),
            ]
        )
        session.flush()
        session.add_all(
            [
                CandidateSkill(candidate_id=ids[0], name="python"),
                CandidateSkill(candidate_id=ids[0], name="sql"),
            ]
        )
        jobs = [
            Job(
                id=uuid.UUID(int=10 + i),
                employer_id=ids[2],
                title=title,
                description="Description",
            )
            for i, title in enumerate(["alpha", "Alpha", "Beta", "Empty", "Deleted"])
        ]
        jobs[-1].is_deleted = True
        session.add_all(jobs)
        session.flush()
        session.add_all(
            [
                JobSkill(job_id=jobs[i].id, name=name)
                for i in range(3)
                for name in ["python", "sql"]
            ]
        )
        applications = [
            Application(
                candidate_id=ids[i],
                job_id=jobs[0].id,
                status=ApplicationStatus.Interviewing,
            )
            for i in range(2)
        ]
        session.add_all(applications)
        start = utc_now() + timedelta(days=1)
        slots = [
            InterviewSlot(
                employer_id=ids[2],
                starts_at=start,
                ends_at=start + timedelta(minutes=30),
            ),
            InterviewSlot(
                employer_id=ids[3],
                starts_at=start,
                ends_at=start + timedelta(minutes=30),
            ),
            InterviewSlot(
                employer_id=ids[2],
                starts_at=start - timedelta(days=2),
                ends_at=start - timedelta(days=2) + timedelta(minutes=30),
            ),
        ]
        session.add_all(slots)
        # 提交整个事务；成功后数据库中的修改才正式生效
        session.commit()
        headers = [
            {"Authorization": f"Bearer {create_access_token(u.email)}"}
            for u in users
        ]
        result = dict(
            engine=engine,
            ids=ids,
            # 带上测试账户的认证请求头，使请求以指定身份执行
            headers=headers,
            jobs=[j.id for j in jobs],
            applications=[a.id for a in applications],
            slots=[s.id for s in slots],
        )

    def database():
        with Session(engine) as session:
            # yield 暂时把资源/夹具交给使用方，使用结束后从此处继续清理
            yield session

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        result["client"] = client
        # yield 暂时把资源/夹具交给使用方，使用结束后从此处继续清理
        yield result
    # 恢复测试前的数据库依赖，避免清除共享应用默认的安全会话。
    if previous_override is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous_override
    engine.dispose()
