from sqlmodel import Session, create_engine
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL,echo=True,pool_size = 10,max_overflow=20)

def get_db():
    with Session(engine) as session:
        yield session



# 候选人及共享入口使用的安全会话；原有 engine/get_db 保留供已有调用方使用。
from sqlalchemy import event

# 从配置读取数据库地址；关闭 SQL 回显并隐藏参数，避免简历等内容出现在 SQL 日志。
safe_engine = create_engine(settings.DATABASE_URL, echo=False, hide_parameters=True)

if safe_engine.dialect.name == "sqlite":
    # SQLite 默认不一定启用外键；每建立一条新连接时都启用约束检查。
    @event.listens_for(safe_engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")


def get_safe_db():
    # FastAPI 依赖会取得 yield 的 Session；请求结束后 with 自动关闭会话。
    with Session(safe_engine) as session:
        yield session
