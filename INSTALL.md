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

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `DATABASE_URL` | yes | image default points at the in-container PostgreSQL | SQLAlchemy/psycopg connection string |
| `APP_NAME` | yes | `CSC4801 Final Project` | FastAPI title |
| `COOKIE_SECURE` | no | `false` | must be `true` behind HTTPS |
| `SESSION_TTL_MINUTES` | no | `720` | server-side session lifetime |
| `SESSION_REMEMBER_DAYS` | no | `30` | "remember me" lifetime |
| `SESSION_COOKIE_NAME` | no | `session` | HttpOnly session cookie name |
| `CSRF_COOKIE_NAME` | no | `csrf_token` | CSRF cookie name |
| `POSTGRES_PASSWORD` | no | `postgres` | demo-only password of the container database |

The image ships demo defaults only; no real credential is baked into it.
Override any of them with `docker run -e NAME=value`.

For local development, `APP_NAME` and `DATABASE_URL` have **no application
defaults**. Settings reads `.env` in the command's working directory. From the
repository root, copy the template (`backend/.env.example`, placeholders only)
without overwriting an existing configuration:

```powershell
if (!(Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

On POSIX: `test -f backend/.env || cp backend/.env.example backend/.env`.
Then replace `YOUR_NAME` and `YOUR_DATABASE_URL` with your local values. For the
demo role and database created in the next section, that means:

```sh
APP_NAME=CSC4801 Final Project
DATABASE_URL=postgresql+psycopg://skillmatch:local-demo-only@127.0.0.1:5432/skillmatch
```

These values are synthetic local/demo configuration, not credentials for any
shared or production system. `.env` must not be committed.

## Database Setup and Migrations

For a fresh local PostgreSQL installation, create the demo role and database
once, using the administrative account configured by your installer:

```sh
psql -h 127.0.0.1 -U postgres -c "CREATE ROLE skillmatch LOGIN PASSWORD 'local-demo-only';"
psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE skillmatch OWNER skillmatch;"
```

These commands target the local development database. Existing installations
should use their own credentials/database and must not recreate or reset them.
The additional `9d6e1a4b2c30` migration sets the missing `application.status`
database default to `Pending` without rewriting existing application states.

The edit-version release adds migration `7b2c9d4e6f10` after
`5a1d3c7e9b20`, then `8c3d0e5f7a21` for company profiles and application status.
With APP_NAME/DATABASE_URL configured for the intended application database, run
from the repository root in the activated project environment:

```sh
cd backend
python -m alembic upgrade head
cd ..
```

This adds positive, non-null `version` columns to candidate profiles, jobs,
company profiles and applications, initializing existing rows to 1 without
resetting application data. Coordinate
the database, backend and frontend upgrade while writes are stopped, then refresh
open editor pages. All four edit PATCH endpoints require the version returned by
their GET: missing/invalid versions return 422, stale versions return 409.
Creation requests must not supply version. New database migration checks are in
`backend/tests/candidate/test_version_migration.py` and
`backend/tests/candidate/test_extended_versions.py` and run only in disposable
test databases. The local repair validation did not migrate a shared/development DB.

## Demo Data and Reset Command

Without Docker, from the repository root run the following **only against a
disposable demo database** configured in `backend/.env`; it deletes all business
records and sessions in that database:

```sh
cd backend
python scripts/seed_demo.py
cd ..
```

One documented command resets and reseeds the application database. With the
container running (see "Docker Startup"):

```sh
docker exec -w /app/backend csc4801 python scripts/seed_demo.py
```

The script truncates every business table and rewrites deterministic demo rows:
2 employers, 3 candidates, 3 jobs (2 with required skills), 5 applications
covering all four statuses, 1 interview slot, and the four FP-MATCH-1 examples.

Seeded accounts are **LOCAL/DEMO ONLY**, never production credentials:

| Role | Email | Password |
| --- | --- | --- |
| Employer 1 | `demo-employer1@example.com` | `demo-local-only` |
| Employer 2 | `demo-employer2@example.com` | `demo-local-only` |
| Candidate Alice | `demo-alice@example.com` | `demo-local-only` |
| Candidate Bob | `demo-bob@example.com` | `demo-local-only` |
| Candidate Carol | `demo-carol@example.com` | `demo-local-only` |

## Docker Build

From the repository root (the directory containing this file and `Dockerfile`):

```sh
docker build -t csc4801-final .
```

No secret or undocumented command is needed. The image is built in two stages:
Node builds `frontend/dist`, then a Python 3.12 image adds PostgreSQL 15, nginx
and supervisor. All Python dependencies come from the locked
`requirements.txt`/`requirements.lock`; the frontend uses `npm ci` against
`package-lock.json`.

## Docker Startup

```sh
docker run -d --name csc4801 -p 127.0.0.1:8080:80 csc4801-final
```

The container entrypoint initialises PostgreSQL on first boot, creates the
`employ` database, runs `alembic upgrade head`, then starts uvicorn
(`127.0.0.1:8000`) and nginx (`:80`). Open <http://localhost:8080/> once
`docker ps` reports the container as `healthy`.

Explicit migration command (already executed at startup, idempotent):

```sh
docker exec -w /app/backend csc4801 python -m alembic upgrade head
```

Seed the deterministic demo data (required once after the first startup):

```sh
docker exec -w /app/backend csc4801 python scripts/seed_demo.py
```

Run the unit suite and the PostgreSQL integration suite:

```sh
docker exec -w /app csc4801 python tests/run_tests.py
docker exec -w /app csc4801 python tests/run_tests.py --integration
```

Inspect logs, stop, or keep data across recreations:

```sh
docker logs csc4801
docker stop csc4801 && docker rm csc4801
docker run -d --name csc4801 -p 127.0.0.1:8080:80 \
  -v csc4801-pgdata:/var/lib/postgresql/data csc4801-final
```

The in-container PostgreSQL listens on `127.0.0.1:5432` only and is not
published to the host, so it cannot collide with a locally installed server.

## Local Development

After configuring the local database and running migrations, install the
frontend dependencies with `npm --prefix frontend ci`. Start these in separate
terminals from the repository root:

```sh
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```sh
npm --prefix frontend run dev -- --host 127.0.0.1
```

Open [the local UI](http://127.0.0.1:5173/). Keep the same host name for UI
requests so the session and CSRF cookies use the same origin.

Without Docker: activate a Python 3.12 environment, install
`pip install -r requirements.txt`, make sure a PostgreSQL server is running and
`backend/.env` contains `APP_NAME` and `DATABASE_URL`, then from the repository
root run `python -m alembic upgrade head` (inside `backend/`) and start both
servers with `start.bat` (Windows) or run `uvicorn app.main:app --reload --port
8000` in `backend/` plus `npm --prefix frontend run dev`. The browser UI is then
served at <http://127.0.0.1:5173/>, where Vite proxies `/api` to port 8000.

On Windows, `start.bat` selects Python in this order.

1. `.venv\Scripts\python.exe` in the repository root.
2. `python.exe` in the active Conda environment.
3. `python.exe` in the `SYManage` environment under `%USERPROFILE%\miniconda3\envs`.
4. `python` on `PATH`.

Before starting the servers, the script checks that the selected Python can import FastAPI, SQLModel, and Uvicorn. It also checks for `npm.cmd` and the frontend's installed Vite executable. Install the dependencies from `requirements.txt` with the Python interpreter selected by the launcher. [Windows launcher](start.bat)

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

After the text-validation and fixture updates the complete unit command passes **196
tests** (exit 0), including strict versions, stale-write rejection and no-op
semantics. The old employer-privacy test already passes after teammate commit
`5143f1e`. No skip/xfail/filter is used. See the
[extension evidence](docs/testing/EDITOR_VERSIONS.md) for before/after results.

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
was verified with 241 passing cases on isolated PostgreSQL16.4 (account tests use
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
python tests/specialized/run.py browser --browser-script version_conflicts
python tests/specialized/run.py browser --browser-script editor_update_checks
python tests/specialized/run.py render
```

Other modes cover delivery/seed/migrations, mutation and a 360-second performance
loop. Each creates its own loopback DB/service when needed and ignores existing
application DB configuration. Output is always outside the checkout; use a new
empty --out path to preserve logs. Never point a raw specialized fixture at a
shared database. Known product failures return nonzero, as documented in
[the report](docs/testing/REPORT.md); no xfail/skip turns them into passes.

```sh
python tests/specialized/run.py performance
python tests/specialized/run.py mutation
python tests/specialized/run.py delivery
```

The edit-version follow-up re-executed these modes and the complete browser/SSR
sets; counts, remaining failures and test-harness adaptations are in the
[follow-up report](docs/testing/VERSION_RETEST.md). Delivery mode excludes Docker.

The company/status extension and always-visible update-check button have their
own [verification report](docs/testing/EDITOR_VERSIONS.md). The integration entry
includes real concurrent company/status saves, rollback, ORM cache, and a migration
that creates and drops a separate random database inside the disposable cluster.
The browser extension checks all four editors in Chinese/English on Chromium,
Firefox and WebKit. Old company/status scripts must include their loaded version;
refresh old tabs after deploying the coordinated database/backend/frontend update.

## Troubleshooting

- Missing `APP_NAME`/`DATABASE_URL`: confirm `backend/.env` exists and run
  backend commands from `backend/`, or explicitly export both variables. An
  unconfigured import is expected to fail; no shared database is selected silently.
- Connection refused or authentication failed: check the PostgreSQL service,
  port, role, password and database in `DATABASE_URL`. The default local example
  uses port 5432; tests create their own disposable clusters on random ports.
- Missing tables/columns: run `python -m alembic upgrade head` in `backend/`
  against the intended database. Refresh old editor tabs after the coordinated
  migration/backend/frontend update.
- UI API requests fail: ensure the backend is on port 8000 and use the Vite URL
  above. Local HTTP requires `COOKIE_SECURE=false`; HTTPS deployment requires true.
- Tests cannot import packages: activate the environment where requirements were
  installed. Browser suites separately need their locked test dependencies and
  installed browser engines, as documented in `tests/specialized/README.md`.
- An expired login requires signing in again. Resetting seed also removes sessions.
