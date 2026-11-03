"""在 backend 目录执行 python -m app.candidate.database。"""

import argparse
import os
from pathlib import Path

from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.candidate.database.migration import check, make_engine, upgrade
from app.candidate.database.model import EXTERNAL_TABLES, OWNED_TABLES


def main(argv=None) -> int:
    # 命令行支持 init（升级）、check（核对差异）和 status（查看状态）。
    parser = argparse.ArgumentParser(description="建立用户负责的七张表，不创建队友表")
    parser.add_argument("action", choices=["init", "check", "status"])
    parser.add_argument("--phase", choices=["core", "full"], default="full")
    args = parser.parse_args(argv)
    # 优先使用显式环境变量；没有设置时使用项目 data 目录下的本地 SQLite。
    database_path = Path(__file__).resolve().parents[3] / "data" / "owned_schema.sqlite3"
    url = os.getenv("OWNED_DATABASE_URL")
    if not url:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        url = "sqlite:///" + database_path.as_posix()
        print(f"Local database: {database_path}")
    engine = make_engine(url)
    try:
        # begin 管理事务和连接；检查表名时只报告现状，不创建团队负责的表。
        with engine.begin() as connection:
            if args.action == "init":
                upgrade(connection, args.phase)
            elif args.action == "check":
                check(connection)
            names = set(inspect(connection).get_table_names())
            version = MigrationContext.configure(connection, opts={
                "version_table": "alembic_owned_version",
            }).get_current_revision()
            print(f"Revision: {version}")
            print("Owned tables: " + ", ".join(sorted(names & OWNED_TABLES)))
            missing = {"employer_profile", "job"} - names
            if missing:
                print("External dependencies pending: " + ", ".join(sorted(missing)))
                print("SQLite schema exists; applications/slots/bookings require teammate tables before use.")
            print("Existing external tables left unchanged: " + ", ".join(sorted(names & EXTERNAL_TABLES)))
    finally:
        # 无论执行成功还是出错，都释放数据库连接池。
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
