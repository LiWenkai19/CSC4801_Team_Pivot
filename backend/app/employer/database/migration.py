"""显式选择数据库的迁移入口，不读取团队 .env，也不默认连接 PostgreSQL。"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection

from app.candidate.database.migration import make_engine

__all__ = ["config_for", "make_engine", "upgrade", "check"]


def config_for(connection: Connection | None = None, url: str | None = None) -> Config:
    config = Config()
    config.set_main_option(
        "script_location", str(Path(__file__).parent / "migrations")
    )
    config.attributes["connection"] = connection
    config.attributes["database_url"] = url
    return config


def upgrade(connection: Connection) -> None:
    command.upgrade(config_for(connection), "head")


def check(connection: Connection) -> None:
    command.check(config_for(connection))
