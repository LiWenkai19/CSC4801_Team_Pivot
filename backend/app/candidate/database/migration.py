"""显式选择数据库的迁移入口，不读取团队 .env，也不默认连接 PostgreSQL。"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection

CORE_REVISION = "owned_core_001"
HEAD_REVISION = "owned_flow_002"


def config_for(connection: Connection | None = None, url: str | None = None) -> Config:
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    config.attributes["connection"] = connection
    config.attributes["database_url"] = url
    return config


def make_engine(url: str):
    engine = create_engine(url)
    if engine.dialect.name not in {"sqlite", "postgresql"}:
        engine.dispose()
        raise ValueError("Only SQLite and PostgreSQL are supported")
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
    return engine


def upgrade(connection: Connection, phase: str = "full") -> None:
    if phase not in {"core", "full"}:
        raise ValueError("phase must be core or full")
    command.upgrade(config_for(connection), CORE_REVISION if phase == "core" else "head")


def check(connection: Connection) -> None:
    command.check(config_for(connection))
