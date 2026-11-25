# Specialized local test suites

The user-authorized edit-version repair covers profile, job, company and application-status PATCH contracts:
explicitly supply the version from the editor's prior GET. Sequential controls
advance their saved version; concurrent cases share one version captured before
starting either request and require exactly one 200 and one 409. Test helpers never
silently refresh an outdated request. Historical reproduction evidence is retained
in the reports; unrelated failing cases remain ordinary failures.

The real-browser regressions cover all four editors in Chinese/English
on Chromium, Firefox and WebKit, including retained drafts, cancel, failed reload
and confirmed reload followed by another save:

```sh
python tests/specialized/run.py browser --browser-script version_conflicts
python tests/specialized/run.py browser --browser-script editor_update_checks
```

These are the historical exploratory/regression tests, now runnable from this
checkout. They supplement the course unit command `python tests/run_tests.py`.
They intentionally keep assertions that currently expose business bugs. A nonzero
exit is not automatically a harness problem; read the phase XML/JSON and report.

## Install test dependencies

From the repository root, in the project's Python environment:

```sh
python -m pip install -r requirements.txt -r tests/specialized/requirements.txt
npm --prefix frontend ci
npm --prefix frontend/tests/specialized ci
```

PostgreSQL **server tools** (`initdb`, `pg_ctl`, `postgres`) must be installed;
having only a running PostgreSQL service/client is insufficient. Set `PG_BIN`
to their directory, add it to PATH, or pass `--pg-bin`. PostgreSQL16.4, Python3.12.4
and Node24.16.0 were used for the recorded local validation. On Unix, run as a
normal user because initdb refuses root. No pre-existing service is stopped.

Browser modes additionally need Playwright's local browser binaries. Install them
from the independent test package (not the application package):

```sh
cd frontend/tests/specialized
npx playwright install chromium firefox webkit
cd ../../..
```

Linux may also need the OS libraries described by Playwright's installer. Optional
`CHROME_EXECUTABLE_PATH` selects an installed Chrome binary; otherwise Chromium
uses Playwright's installed binary. `PLAYWRIGHT_BROWSERS_PATH` and `NODE_BINARY`
can select an existing cache/Node executable. No machine-specific executable path
is embedded in the scripts.

## Run from repository root

```powershell
# Example only: replace with your installed PostgreSQL server tools directory.
$env:PG_BIN = "C:\Program Files\PostgreSQL\16\bin"
python tests/specialized/run.py functional
```

```sh
export PG_BIN=/path/to/postgresql/bin
python tests/specialized/run.py functional
```

The entry creates a **new cluster and database** on a random loopback port and
ignores supplied application database URLs. It pins the DB timezone to
Asia/Shanghai so the historical date-return boundary has the same precondition.
All accounts/data are synthetic. The cluster is stopped in finally; artifacts and
synthetic data are retained in the printed system-temporary directory for review.
Never run the specialized files directly against a shared DB: their fixture
truncates all test tables and requires the managed-run marker.

| Command suffix | Scope |
|---|---|
| `functional` | 393 executions: slots95, booking121, matching86, auth42, targeted26, remaining23 |
| `slots`, `booking`, `matching`, `auth`, `targeted`, `remaining` | One of the six functional groups |
| `performance` | 10/100/1000-row correctness/query observations and the original **360-second** bounded loop |
| `browser` | All seven real-browser/probe entrypoints; three engines where the module specifies them |
| `browser --browser-script frontend_changed_pages` | One browser module (see CLI help for all names) |
| `render` | Six focused and 30 broader actual-TSX SSR checks; no PG/server/browser process required |
| `mutation` | Eight baseline predicates and seven non-equivalent plus one equivalent test-only mutations |
| `delivery` | 21 installation/configuration, seed, schema/default and migration checks |
| `all` | All above groups; includes the six-minute loop and all browser/mutation work |

For example:

```sh
python tests/specialized/run.py browser
python tests/specialized/run.py render
python tests/specialized/run.py delivery
python tests/specialized/run.py mutation
```

`--out /new/path/outside/checkout` selects an empty artifact directory; existing
nonempty directories are rejected to preserve old evidence. Output inside the
checkout is rejected because logs may include synthetic Cookie/CSRF values. Do
not commit raw output, databases or node_modules. `--coverage` records separate
backend/app branch/statement data files for Python groups; uncombined files are
not a new whole-system coverage claim. No exclusions hide known failures.

## Results and interpretation

- Every phase writes its actual command, exit code, log and XML/JSON. The parent
  returns nonzero if any phase fails, times out or has a source/cleanup error.
- `manifest.json` fixes HEAD, dirty-state context and business source hashes;
  `summary.json` records phase statuses, source integrity and PG cleanup.
- Browser scripts use only a test proxy to the isolated backend, real Cookie/CSRF
  sessions and synthetic accounts. The expiry helper changes only that fresh DB.
  Probe scripts deliberately expose the original tracked Bearer helper mismatch.
- Mutation tooling copies only backend/app into the external artifact directory,
  alters one copy at a time and restores it. Production files are never edited.
- SSR compiles the actual TSX to external artifacts. The broader script supplies
  deterministic initial hook state; rendering expressions stay unchanged. It
  verifies output nodes/text, not browser event execution or a universal security
  guarantee. Required script-shaped input is never executed.
- The model/migration tool resets only its freshly created DB and checks default
  comparisons explicitly. It does not repair seed or migrations.

Historical port-baseline evidence: functional369 pass/24 fail, browser149 pass/8 fail,
SSR36 pass, delivery13 pass/8 fail. These original counts and the then-failing
privacy-contract test belong to the port baseline.

Current edit-version follow-up: browser169 (161 passed/8 known failures), SSR36
passed, performance4 passed including the complete 360-second budget, original
non-equivalent mutation samples7/7 detected, non-Docker delivery13 passed/8 known
failures. The browser total includes the 12 version-conflict scenarios and counts
each accepted scenario once.
SSR uses the real LanguageProvider and required props, browser selectors follow
the current accessible names, and catalogue inventory must be nonempty. None of
these adaptations suppresses product exceptions or changes rendering expressions.

## Historical adaptation

All 21 Python and 10 JS sources are inventoried. Duplicate fixtures and old
machine-dependent run_stage scripts were consolidated into conftest.py,
audit_context.py and run.py. No app logic or original production assertions were
patched. Old employer-list assertions were migrated because current SPEC retains
booked future slots and returns is_booked; candidate availability still excludes
them. Current ApplicantCard markup/Shanghai time and workspace heading are used.
WebKit keyboard checks compare equivalent native control types and initial focus.

No Docker execution, production/live-target probing, credential validation,
deployment or business repair is performed by these test entrypoints.

## Optional audit-tool reruns

Historical dependency/history reviews are documented in the reports. If those
databases/history have changed, rerun the approved read-only tools against the
local checkout, keeping output outside Git. For example, with separately installed
`pip-audit` and `gitleaks`:

```sh
python -m pip_audit -r requirements.lock -f json
npm --prefix frontend audit --json
gitleaks git . --log-opts="--all --full-history -m" --redact=100 --no-banner
```

Tool findings require contextual review; a dependency version hit is not proof of
an exploitable app path, and a scanner hit is not automatically a real secret.
These optional external-tool commands were not re-executed merely by copying the
historical reports. Always redact credentials/personal data before publication.

`editor_update_checks.mjs` runs 24 engine/language/editor scenarios plus 12 real company/status double-tab scenarios covering same-version checks, draft preservation, failed reads, cancelled/confirmed reloads, real 409 saves, pending skill queries and independent applicant cards. It captures the submitted versions; it never refreshes a stale PATCH body in the API helper.
