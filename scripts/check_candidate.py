"""Run candidate checks with the interpreter and files from this checkout."""
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'frontend/candidate'


def main():
    npm = shutil.which('npm.cmd' if sys.platform == 'win32' else 'npm')
    if npm is None:
        raise SystemExit('npm is required; install Node.js and the candidate dependencies.')
    checks = [
        ([sys.executable, 'scripts/check_candidate_ownership.py'], ROOT),
        ([sys.executable, '-m', 'pip', 'check'], ROOT),
        ([sys.executable, '-m', 'ruff', 'check', 'backend/app/candidate',
          'backend/app/candidate_main.py', 'backend/app/matching.py',
          'backend/candidate_tests', 'backend/candidate_alembic', 'scripts'], ROOT),
        ([sys.executable, '-m', 'pytest', '-c', 'pytest.candidate.ini', '-q'], ROOT),
        ([npm, 'run', 'build'], UI),
        ([npm, 'run', 'lint'], UI),
        ([npm, 'test'], UI),
    ]
    for args, cwd in checks:
        result = subprocess.run(args, cwd=cwd)
        if result.returncode:
            return result.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
