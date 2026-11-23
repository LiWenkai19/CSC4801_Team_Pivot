"""从仓库根目录运行课程单测；集成测试需显式选择和隔离PG配置。"""

from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    args = sys.argv[1:]
    integration = "--integration" in args
    if integration:
        args.remove("--integration")
        for key in ("CANDIDATE_TEST_DATABASE_URL", "EMPLOYER_TEST_DATABASE_URL"):
            if not os.environ.get(key):
                print(
                    f"Set {key} to a disposable PostgreSQL instance before integration tests",
                    file=sys.stderr,
                )
                return 2
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "backend") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if integration:
        targets = [ROOT / "backend/tests"]
    else:
        targets = [ROOT / "tests/unit", ROOT / "backend/tests/users/test_schema.py"]
        env.update(
            APP_NAME="Business unit tests",
            DATABASE_URL="postgresql+psycopg://unit:unit@127.0.0.1:1/unit_not_a_database",
            COOKIE_SECURE="false",
        )
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--rootdir=" + str(ROOT),
            *map(str, targets),
            "-q",
            "-ra",
            "-p",
            "no:cacheprovider",
            *args,
        ],
        cwd=ROOT / "backend" if integration else ROOT,
        env=env,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
