"""候选人独立应用的数据库会话，不记录查询参数。"""
from sqlalchemy import event
from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=False, hide_parameters=True)

if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")


def get_safe_db():
    with Session(engine) as session:
        yield session
