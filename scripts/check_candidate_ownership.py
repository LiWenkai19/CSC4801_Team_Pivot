"""Verify that the upstream checkout is unchanged and additions stay in scope."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args]).decode('utf-8')


def allowed(path):
    return (
        path.startswith(('backend/app/candidate/', 'backend/candidate_tests/',
                         'backend/candidate_alembic/', 'frontend/candidate/'))
        or path in {'backend/app/candidate_main.py', 'backend/app/matching.py',
                    'backend/alembic.candidate.ini', 'pytest.candidate.ini',
                    'scripts/check_candidate.py', 'scripts/check_candidate_ownership.py',
                    'scripts/preview_candidate.py'}
        or path.startswith('docs/CANDIDATE_')
    )


def main():
    baseline = json.loads((ROOT / 'docs/CANDIDATE_BASELINE.json').read_text(encoding='utf-8'))
    errors = []
    ancestry = subprocess.run(['git', '-C', str(ROOT), 'merge-base', '--is-ancestor', baseline['commit'], 'HEAD'])
    if ancestry.returncode:
        errors.append('HEAD no longer descends from the audited upstream commit; re-audit the baseline.')
    for name, expected in baseline['tracked_sha256'].items():
        path = ROOT / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            errors.append(f'Upstream file changed: {name}')
    added = git('ls-files', '--others', '--exclude-standard', '-z').split('\0')
    added += [name for name in git('ls-files', '-z').split('\0')
              if name and name not in baseline['tracked_sha256']]
    for name in filter(None, added):
        if not allowed(name):
            errors.append(f'Addition outside the candidate scope: {name}')
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Ownership check passed: {len(baseline["tracked_sha256"])} upstream files unchanged; additions stay in candidate scope.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
