"""雇主模块测试夹具；只用临时 SQLite 文件，不连接任何业务数据库。"""

import os
import uuid

import pytest
from sqlmodel import Session

os.environ.setdefault("APP_NAME", "Employer workspace tests")
os.environ.setdefault("SECRET_KEY", "isolated-test-key-with-at-least-32-characters")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "10")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@127.0.0.1:1/test")


@pytest.fixture(scope="session", autouse=True)
def isolated_settings():
    """为所有测试提供与业务环境无关的演示配置。"""
    monkey = pytest.MonkeyPatch()
    for key, value in {
        "APP_NAME": "Employer workspace tests",
        "SECRET_KEY": "isolated-test-key-with-at-least-32-characters",
        "ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "10",
        "DATABASE_URL": "postgresql+psycopg://test:test@127.0.0.1:1/test",
    }.items():
        monkey.setenv(key, value)
    yield
    monkey.undo()


@pytest.fixture
def engine(tmp_path):
    """每个测试使用独立的临时 SQLite 文件，迁移需要多次连接。"""
    from app.candidate.database.migration import make_engine

    database = make_engine("sqlite:///" + (tmp_path / "employer.sqlite3").as_posix())
    try:
        yield database
    finally:
        database.dispose()


@pytest.fixture
def migrated_engine(engine):
    """按组员 core → 雇主 → 组员 full 的顺序建库。"""
    from app.candidate.database import migration as candidate_migration
    from app.employer.database import migration as employer_migration

    with engine.begin() as connection:
        candidate_migration.upgrade(connection, "core")
        employer_migration.upgrade(connection)
        candidate_migration.upgrade(connection)
    return engine


@pytest.fixture
def db(migrated_engine):
    """直接读取同一测试数据库，用于断言持久化结果。"""
    with Session(migrated_engine) as session:
        yield session


@pytest.fixture
def client(migrated_engine):
    """新建独立应用，挂载组员账户、组员业务与雇主路由。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.candidate.accounts import user_router
    from app.candidate.router import router as candidate_router
    from app.db.session import get_db
    from app.employer.router import employer_router

    application = FastAPI()
    application.include_router(user_router)
    application.include_router(candidate_router)
    application.include_router(employer_router)

    def test_db():
        with Session(migrated_engine) as session:
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
        email = email or f"{uuid.uuid4().hex}@example.com"
        response = client.post(
            "/users/register",
            json={"email": email, "password": "demo-password", "role": role},
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _register


@pytest.fixture
def make_employer(client, register):
    """注册雇主、填写团队雇主资料并创建公司。"""

    def _make_employer(
        email=None, company_name="Demo Company", profile=True, company=True
    ):
        headers = register(email, "employer")
        if profile:
            response = client.post(
                "/users/employer/profile",
                json={"company_name": company_name},
                headers=headers,
            )
            assert response.status_code == 201, response.text
        if company:
            response = client.post(
                "/employer/company",
                json={"name": company_name, "description": "We build software."},
                headers=headers,
            )
            assert response.status_code == 201, response.text
        return headers

    return _make_employer


@pytest.fixture
def make_candidate(client, register):
    """注册候选人并通过组员接口创建资料与技能。"""

    def _make_candidate(email=None, name="Candidate", skills=None):
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
