"""可重复的本地浏览器验证环境；只在系统临时目录创建虚构 SQLite 数据，不连接业务库。"""

import argparse
import os
from pathlib import Path
import secrets
import sys

# Resolve the review copy before any editable installation from another checkout.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=18000)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(
        prefix="pivot-candidate-browser-", ignore_cleanup_errors=True
    ) as folder:
        database = Path(folder) / "browser.sqlite3"
        os.environ.update(
            APP_NAME="Isolated Candidate Browser Tests",
            SECRET_KEY=secrets.token_urlsafe(48),
            ALGORITHM="HS256",
            ACCESS_TOKEN_EXPIRE_MINUTES="30",
            DATABASE_URL=f"sqlite:///{database.as_posix()}",
        )
        # 环境配置必须在 app 导入前设置，防止 Settings 提前读到个人数据库地址。
        from sqlmodel import Session, SQLModel
        import uvicorn
        from app.main import app
        from app.db.session import safe_engine as engine
        from app.candidate.seed import seed

        try:
            SQLModel.metadata.create_all(engine)
            with Session(engine) as session:
                seed(session)
            uvicorn.run(app, host="127.0.0.1", port=args.port)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
