# Installation Guide

## Prerequisites and Versions

The current backend uses Python 3.11 or later; the locked dependency set was
verified with Python 3.12.13 in the project's `SYManage` Conda environment.
It uses FastAPI, SQLModel, and PostgreSQL. Flask dependencies from the starter
remain in the lock file; Flask is not a required application framework.

## Dependency Installation

Run these commands from the repository root in your activated Python environment:

```sh
python -m pip install -r requirements.txt
python -m pip check
```

`requirements.txt` includes `requirements.lock`, which pins backend runtime,
test, and development dependencies, including the required package extras.
To install the backend as an editable package with the same locked versions:

```sh
python -m pip install -r requirements.txt -e "./backend[dev]"
```

## Environment Variables

## Database Setup and Migrations

## Demo Data and Reset Command

## Docker Build

## Docker Startup

## Local Development

## Running Unit Tests

Run commands from the repository root in the activated Python environment.
Python dependencies are installed by the earlier `pip install -r requirements.txt`
step. Install the locked frontend dependencies too, because the required rendering
unit test uses the actual React component, ReactDOM and TypeScript:

```sh
npm --prefix frontend ci
python tests/run_tests.py
```

Python 3.12.4 and Node 24.16.0 were used for the recorded validation. Use a Node
version satisfying the frontend lockfile/toolchain (Vite declares
`^20.19.0 || >=22.12.0`). If Node is not on PATH, set `NODE_BINARY` to its executable.
No new frontend test dependency or package-lock change is required.

The single Python command runs the complete business/schema/component unit suite
non-interactively; a failing test, missing Node/dependency, or renderer failure
returns a nonzero exit code. Optional JUnit output:

```sh
python tests/run_tests.py --junitxml=unit-results.xml
```

Unit tests set an unreachable synthetic configuration internally and forbid real
database connections. They need no `.env`, server, PostgreSQL, browser, external
service or paid API key. The Node bridge runs `node --test` on
`frontend/tests/rendering.unit.mjs`; it transpiles the actual SkillTagPicker TSX
without changing render expressions and checks text escaping via ReactDOM SSR.
To inspect the three component results alone:

```sh
node --test frontend/tests/rendering.unit.mjs
```

The full command currently has one genuine failing course-contract test:
`test_fp_can_1_course_resume_privacy_includes_related_employer`. It expects an
employer to be denied private resume access; current business logic permits a
related employer. Expected full result is 114 passed/1 failed (exit 1), not a
green suite. No skip/xfail/filter is used; resolve the policy/business mismatch
through the team's authorized repair process rather than weakening the test.

### Existing PostgreSQL/API regression (separate from unit tests)

Use only a disposable local PostgreSQL instance with CREATE DATABASE permission.
The candidate fixture creates/drops a random database; the employer fixture uses
`symanage_test` and clears it between tests. Never point these variables at a
production/shared development instance. The explicit environment overrides avoid
reading or changing `backend/.env` for this command.

PowerShell (replace the demo port/user with your disposable instance):

```powershell
$env:CANDIDATE_TEST_DATABASE_URL = "postgresql+psycopg://test_user@127.0.0.1:55432/postgres"
$env:EMPLOYER_TEST_DATABASE_URL = $env:CANDIDATE_TEST_DATABASE_URL
python tests/run_tests.py --integration
```

POSIX shell:

```sh
export CANDIDATE_TEST_DATABASE_URL='postgresql+psycopg://test_user@127.0.0.1:55432/postgres'
export EMPLOYER_TEST_DATABASE_URL="$CANDIDATE_TEST_DATABASE_URL"
python tests/run_tests.py --integration
```

These are synthetic local example settings, not real credentials; configure local
authentication for the disposable database separately. This complete legacy suite
was verified with 145 passing cases on isolated PostgreSQL16.4 (account tests use
their own in-memory SQLite). Failure also returns nonzero. The runner requires
both explicit URLs and never starts/stops an existing database service.

Do not use bare root-level `pytest` as the documented entry: automatic collection
also finds legacy API/PG tests with different setup requirements. Use the two
explicit commands above so their evidence and environments remain distinct.

## Specialized Tests and Browser Suites

The independent historical regression tooling is described in
[tests/specialized/README.md](tests/specialized/README.md). Install its optional
instrumentation and locked browser-test package, in addition to the existing
application dependencies:

```sh
python -m pip install -r tests/specialized/requirements.txt
npm --prefix frontend/tests/specialized ci
```

Install Playwright's chromium/firefox/webkit binaries from that package directory
as shown in the test README. Set PG_BIN to the PostgreSQL server tools directory,
then run from the repository root:

```sh
python tests/specialized/run.py functional
python tests/specialized/run.py browser
python tests/specialized/run.py render
```

Other modes cover delivery/seed/migrations, mutation and a 360-second performance
loop. Each creates its own loopback DB/service when needed and ignores existing
application DB configuration. Output is always outside the checkout; use a new
empty --out path to preserve logs. Never point a raw specialized fixture at a
shared database. Known product failures return nonzero, as documented in
[the report](docs/testing/REPORT.md); no xfail/skip turns them into passes.

## Troubleshooting
