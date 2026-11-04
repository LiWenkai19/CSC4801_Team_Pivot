"""雇主模块测试夹具：连本机 PostgreSQL 的独立测试库，测试间清空业务表。"""

import os
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_PATH = BACKEND_DIR / ".env"
TEST_DATABASE = "symanage_test"


def _read_env_database_url() -> str:
    """从 backend/.env 读取 DATABASE_URL，只取值不回显内容。"""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("DATABASE_URL="):
            value = stripped.split("=", 1)[1].strip()
            return value.strip('"').strip("'")
    raise RuntimeError(f"DATABASE_URL missing in {ENV_PATH}")


def _build_test_database_url() -> str:
    """复用 .env 的主机与账号，把库名换成独立测试库。"""
    from sqlalchemy.engine import make_url

    url = make_url(_read_env_database_url())
    return url.set(database=TEST_DATABASE).render_as_string(hide_password=False)


# 在任何 app 导入前设定环境：仅复用数据库连接，认证密钥全部用测试占位值。
os.environ["APP_NAME"] = "Employer workflow tests"
os.environ["SECRET_KEY"] = "isolated-test-key-with-at-least-32-characters"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["DATABASE_URL"] = _build_test_database_url()


def _ensure_database() -> None:
    """测试库不存在时自动创建。"""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import make_url

    admin_url = make_url(os.environ["DATABASE_URL"]).set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": TEST_DATABASE},
            ).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE}"'))
    finally:
        admin_engine.dispose()


def _run_migrations() -> None:
    """对测试库执行主迁移链建表，顺带验证迁移脚本可运行。"""
    from alembic import command
    from alembic.config import Config

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    command.upgrade(config, "head")


import pytest  # noqa: E402  环境准备完成后才允许导入依赖。
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, create_engine, text  # noqa: E402


@pytest.fixture(scope="session")
def engine():
    """会话级测试库引擎：先建库再跑迁移。"""
    _ensure_database()
    _run_migrations()
    database_engine = create_engine(os.environ["DATABASE_URL"])
    try:
        yield database_engine
    finally:
        database_engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables(engine):
    """每个测试前清空全部业务表，保证用例互相隔离。"""
    from app.employer.model import (  # noqa: F401 -- 触发模型注册。
        Application,
        Booking,
        InterviewSlot,
        Job,
        JobSkill,
    )
    from app.users.model import (  # noqa: F401 -- 触发模型注册。
        CandidateProfile,
        CandidateSkill,
        EmployerProfile,
        User,
    )
    from sqlmodel import SQLModel

    names = ", ".join(f'"{table.name}"' for table in SQLModel.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db(engine):
    """直接读写测试库，用于断言持久化结果。"""
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(engine):
    """新建独立应用，挂载账户与雇主路由并注入测试库 Session。"""
    from app.db.session import get_db
    from app.employer.router import employer_router
    from app.users.router import user_router

    application = FastAPI()
    application.include_router(user_router)
    application.include_router(employer_router)

    def test_db():
        """仅向真实业务服务提供测试库 Session。"""
        with Session(engine) as session:
            yield session

    application.dependency_overrides[get_db] = test_db
    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


@pytest.fixture
def register(client):
    """注册账户并返回认证请求头。"""

    def _register(email=None, role="candidate"):
        """注册指定角色账户，邮箱缺省时随机生成。"""
        email = email or f"{uuid.uuid4().hex}@example.com"
        response = client.post(
            "/users/register",
            json={"email": email, "password": "demo-password", "role": role},
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _register


@pytest.fixture
def user_id(client):
    """读取指定认证账户的 ID。"""

    def _user_id(headers):
        """调用 /users/me 取当前账户 ID。"""
        return uuid.UUID(client.get("/users/me", headers=headers).json()["id"])

    return _user_id


@pytest.fixture
def make_employer(client, register):
    """注册雇主并填写公司资料。"""

    def _make_employer(
        email=None, company_name="Demo Company", description="We build software."
    ):
        """注册雇主账户并创建公司资料，返回认证请求头。"""
        headers = register(email, "employer")
        response = client.post(
            "/users/employer/profile",
            json={"company_name": company_name, "company_description": description},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        return headers

    return _make_employer


@pytest.fixture
def make_candidate(client, register):
    """注册候选人并填写资料与技能。"""

    def _make_candidate(email=None, name="Candidate", skills=None):
        """注册候选人账户并创建资料，返回认证请求头。"""
        headers = register(email, "candidate")
        response = client.post(
            "/users/candidate/profile",
            json={"display_name": name, "skills": skills or []},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        return headers

    return _make_candidate


@pytest.fixture
def make_job(client):
    """通过雇主接口发布职位并返回响应 JSON。"""

    def _make_job(headers, **fields):
        """发布职位，字段可覆盖默认标题、描述和技能。"""
        payload = {
            "title": "Backend Engineer",
            "description": "Build services.",
            "required_skills": ["python"],
        }
        payload.update(fields)
        response = client.post("/employer/jobs", json=payload, headers=headers)
        assert response.status_code == 201, response.text
        return response.json()

    return _make_job


@pytest.fixture
def make_application(client, db, user_id):
    """直插申请记录（本分支没有候选人申请接口）。"""

    def _make_application(candidate_headers, job_json, status=None):
        """为候选人向指定职位插入一条申请。"""
        from app.employer.model import Application, ApplicationStatus

        application = Application(
            candidate_id=user_id(candidate_headers),
            job_id=uuid.UUID(job_json["id"]),
            status=status or ApplicationStatus.Pending,
        )
        db.add(application)
        db.commit()
        db.refresh(application)
        return application

    return _make_application


@pytest.fixture
def make_slot(client, db, user_id):
    """直插面试时段记录。"""

    def _make_slot(headers, job_json=None):
        """为雇主插入一个 30 分钟面试时段。"""
        from datetime import datetime, timedelta, timezone

        from app.employer.model import InterviewSlot

        start = datetime.now(timezone.utc) + timedelta(days=1)
        slot = InterviewSlot(
            employer_id=user_id(headers),
            job_id=uuid.UUID(job_json["id"]) if job_json else None,
            starts_at=start,
            ends_at=start + timedelta(minutes=30),
        )
        db.add(slot)
        db.commit()
        db.refresh(slot)
        return slot

    return _make_slot
