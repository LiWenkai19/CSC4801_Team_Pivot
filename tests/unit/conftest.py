"""直接测试实际业务逻辑，数据库调用由Session替身隔离。"""

import os
from pathlib import Path
import sys
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["APP_NAME"] = "Business unit tests"
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://unit:unit@127.0.0.1:1/unit_not_a_database"
)
os.environ["COOKIE_SECURE"] = "false"


@pytest.fixture(autouse=True)
def no_database_connections(monkeypatch):
    from sqlalchemy.engine import Engine

    def forbidden(*args, **kwargs):
        raise AssertionError("Unit tests must use a session double, not a database")

    monkeypatch.setattr(Engine, "connect", forbidden)


@pytest.fixture
def result():
    def make(rows=(), first=None):
        value = MagicMock()
        value.all.return_value = list(rows)
        value.first.return_value = first
        value.one_or_none.return_value = first
        value.__iter__.return_value = iter(rows)
        return value

    return make


@pytest.fixture
def db(result):
    from sqlmodel import Session

    value = MagicMock(spec=Session)
    value.get.return_value = None
    value.exec.return_value = result()
    return value


@pytest.fixture
def actors():
    from app.users.model import Role, User

    return (
        User(
            email="candidate@example.com",
            hashed_password="synthetic",
            role=Role.Candidate,
        ),
        User(
            email="employer@example.com",
            hashed_password="synthetic",
            role=Role.Employer,
        ),
    )
