"""真实 PostgreSQL 测试；每次会话创建独立数据库，结束后删除。"""

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url
from sqlmodel import Session, create_engine, text

BACKEND = Path(__file__).resolve().parents[2]
# 连接只作为建测试库的来源；实际测试从不使用来源库。
SOURCE_URL = os.environ.get("CANDIDATE_TEST_DATABASE_URL")
os.environ.setdefault("APP_NAME", "Candidate workflow tests")
os.environ.setdefault("SECRET_KEY", "candidate-test-key-with-at-least-32-characters")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault(
    "DATABASE_URL", SOURCE_URL or "postgresql+psycopg://unused@127.0.0.1:1/unused"
)


@pytest.fixture(scope="session")
def engine():
    """主迁移链建表；随机测试库不与开发库或队友测试库混用。"""
    if not SOURCE_URL:
        pytest.fail(
            "Set CANDIDATE_TEST_DATABASE_URL to a PostgreSQL instance with CREATE DATABASE permission"
        )
    from alembic import command
    from alembic.config import Config
    from app.core.config import settings

    source = make_url(SOURCE_URL)
    if source.get_backend_name() != "postgresql":
        pytest.fail("Candidate tests require real PostgreSQL")
    name = f"csc4801_candidate_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    database_engine = create_engine(source.set(database=name))
    previous = settings.DATABASE_URL
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        settings.DATABASE_URL = source.set(database=name).render_as_string(
            hide_password=False
        )
        command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
        settings.DATABASE_URL = previous
        yield database_engine
    finally:
        settings.DATABASE_URL = previous
        database_engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture(autouse=True)
def clean_tables(engine):
    """仅清空本次随机测试库。"""
    from sqlmodel import SQLModel

    names = ", ".join(f'"{table.name}"' for table in SQLModel.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db(engine):
    """独立 Session 断言持久化状态。"""
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine):
    """执行真实主应用，只有数据库依赖替换为隔离库。"""
    from fastapi.testclient import TestClient
    from app.db.session import get_db
    from app.main import app

    def test_db():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def account(client):
    """通过真实注册和资料接口创建角色，返回认证头及 ID。"""

    def create(role="candidate", skills=None, complete=True):
        response = client.post(
            "/users/register",
            json={
                "email": f"{uuid.uuid4().hex}@example.com",
                "password": "test-local-password",
                "role": role,
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        if complete:
            payload = (
                {
                    "display_name": "Candidate",
                    "resume_text": "Private resume",
                    "skills": skills or [],
                }
                if role == "candidate"
                else {"company_name": "Test Company"}
            )
            saved = client.post(f"/users/{role}/profile", headers=headers, json=payload)
            assert saved.status_code == 201, saved.text
        return headers, uuid.UUID(data["user"]["id"])

    return create


@pytest.fixture
def job(client):
    """由雇主真实发布职位。"""

    def create(employer, **changes):
        response = client.post(
            "/employer/jobs",
            headers=employer,
            json={
                "title": "Engineer",
                "description": "Build software",
                "required_skills": ["python", "sql"],
                **changes,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    return create


@pytest.fixture
def interview(client, account, job, db):
    """真实投递后由雇主发出面试邀约；时段管理仍由其他模块负责。"""
    from datetime import timedelta
    from app.employer.model import InterviewSlot
    from app.users.model import utc_now

    employer, employer_id = account("employer")
    candidate, candidate_id = account(skills=["python"])
    posting = job(employer)
    applied = client.post(
        f"/candidate/jobs/{posting['id']}/applications", headers=candidate, json={}
    ).json()
    changed = client.patch(
        f"/employer/applications/{applied['application_id']}/status",
        headers=employer,
        json={"status": "Interviewing"},
    )
    assert changed.status_code == 200
    start = utc_now() + timedelta(days=1)
    slot = InterviewSlot(
        employer_id=employer_id, starts_at=start, ends_at=start + timedelta(minutes=30)
    )
    db.add(slot)
    db.commit()
    db.refresh(slot)
    return {
        "employer": employer,
        "employer_id": employer_id,
        "candidate": candidate,
        "candidate_id": candidate_id,
        "job": posting,
        "application": applied,
        "slot": slot,
    }
