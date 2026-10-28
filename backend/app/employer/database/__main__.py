"""在 backend 目录执行 python -m app.employer.database。"""

import argparse
import os
from pathlib import Path

from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.candidate.database.migration import make_engine
from app.employer.database.migration import check, upgrade

EMPLOYER_TABLES = frozenset({"employer_profile", "job", "job_skill", "employer_company"})
DEPENDENCY_TABLES = ("user", "company")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="建立雇主负责的四张表，不创建组员的业务表"
    )
    parser.add_argument("action", choices=["init", "check", "status"])
    args = parser.parse_args(argv)
    database_path = (
        Path(__file__).resolve().parents[3] / "data" / "owned_schema.sqlite3"
    )
    url = os.getenv("OWNED_DATABASE_URL")
    if not url:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        url = "sqlite:///" + database_path.as_posix()
        print(f"Local database: {database_path}")
    engine = make_engine(url)
    try:
        with engine.begin() as connection:
            if args.action == "init":
                upgrade(connection)
            elif args.action == "check":
                check(connection)
            names = set(inspect(connection).get_table_names())
            version = MigrationContext.configure(
                connection, opts={"version_table": "alembic_employer_version"}
            ).get_current_revision()
            print(f"Revision: {version}")
            print("Employer tables: " + ", ".join(sorted(names & EMPLOYER_TABLES)))
            missing = set(DEPENDENCY_TABLES) - names
            if missing:
                print(
                    "External dependencies pending: " + ", ".join(sorted(missing))
                )
                print("Run the candidate core phase first.")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
