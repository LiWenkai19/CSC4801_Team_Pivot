# from contextlib import asynccontextmanager
from fastapi import FastAPI
# from sqlmodel import Session
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
# from app.db.session import engine
from app.users.router import user_router
# from app.users.service import init_superadmin


# @asynccontextmanager
# async def lifespan(app: FastAPI):
    
    # 如果启动时需要初始化文件夹，参照下方代码
    # settings.invoice_dir.mkdir(parents=True, exist_ok=True)
    # 启动时执行
    # with Session(engine) as session:
    #     init_superadmin(session)
    # yield
    # 关闭时执行（如果需要清理资源）


app = FastAPI(title=settings.APP_NAME)

# cross origin resourse sharing middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(user_router)

