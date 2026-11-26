"""Child process used by ``run_mutants.py``.

It sets the unit-test environment, imports the application, applies exactly one
mutant with ``monkeypatch``-style attribute replacement (no production file is
edited), and then runs one pytest file in-process.  The process exit code is the
pytest exit code: 0 means every test passed (the mutant survived), 1 means at
least one test failed (the mutant was killed).
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
BACKEND = ROOT / "backend"

os.environ["APP_NAME"] = "LLM blind mutation experiment"
os.environ["COOKIE_SECURE"] = "false"
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://unit:unit@127.0.0.1:1/unit_not_a_database"
)
os.environ["PYTHONHASHSEED"] = "4801"
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

for entry in (str(BACKEND), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from mutants import apply_mutant  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--mutant", required=True)
    parser.add_argument("--test", required=True, help="test file, relative to repo root")
    parser.add_argument("--junit", required=True)
    args = parser.parse_args(argv)

    test_path = (ROOT / args.test).resolve()
    if not test_path.is_file():
        print(f"missing test file: {test_path}", file=sys.stderr)
        return 2

    apply_mutant(args.mutant)

    import pytest

    return pytest.main(
        [
            str(test_path),
            "-q",
            "--rootdir",
            str(ROOT),
            "-p",
            "no:cacheprovider",
            f"--junitxml={args.junit}",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
