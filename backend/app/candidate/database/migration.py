"""显式选择数据库的迁移入口，不读取团队 .env，也不默认连接 PostgreSQL。"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection

# core 是第一阶段版本，head 是当前完整迁移链的最新版本。
CORE_REVISION = "owned_core_001"
HEAD_REVISION = "owned_booking_003"


def config_for(connection: Connection | None = None, url: str | None = None) -> Config:
    # 告诉 Alembic 去哪里找独立迁移脚本，并传入已有连接或显式 URL。
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
    config.attributes["connection"] = connection
    config.attributes["database_url"] = url
    return config


def make_engine(url: str):
    # 只接受项目验证过的 SQLite 和 PostgreSQL；SQLite 每个连接都打开外键检查。
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
    # core 只升级到核心表，full 按迁移链升级到最新版本。
    if phase not in {"core", "full"}:
        raise ValueError("phase must be core or full")
    command.upgrade(config_for(connection), CORE_REVISION if phase == "core" else "head")


def check(connection: Connection) -> None:
    # 检查独立模型与已迁移数据库之间是否存在未生成的迁移差异。
    command.check(config_for(connection))
