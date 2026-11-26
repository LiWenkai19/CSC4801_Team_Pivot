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
They retain historical assertions, including four AUTH-01 status-code assertions
that the team explicitly does not classify as a bug. A nonzero exit must be
interpreted with the recorded contract and team disposition below; it is neither
a hidden pass nor automatically a new product defect.

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
| `functional` | 411 executions: slots97, booking121, matching102, auth42, targeted26, remaining23 |
| `slots`, `booking`, `matching`, `auth`, `targeted`, `remaining` | One of the six functional groups |
| `performance` | 10/100/1000-row correctness/query observations and the original **360-second** bounded loop |
| `browser` | All ten real-browser/probe entrypoints; three engines where the module specifies them |
| `browser --browser-script frontend_changed_pages` | One browser module (see CLI help for all names) |
| `render` | Six focused and 33 broader actual-TSX SSR checks; no PG/server/browser process required |
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
  Probe scripts verify the current Cookie/CSRF helpers; both role probes passed.
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

Historical edit-version snapshot (before the latest fixes): browser169
(161 passed/8 failures), SSR36, performance4 including the complete 360-second
budget, original non-equivalent mutations7/7 detected, and delivery13 passed/8
failures. Its original SHA is not recorded in this paragraph; these figures are
retained as historical context and are not current acceptance results.

Latest complete audit baseline: `fa8317cbf3119433ff3ff0673a69bd3cf411db46`,
2026-11-26. Functional411 = 407 passed + 4 original AUTH-01 assertion failures;
browser308/308 passed across all ten scripts; SSR39/39; delivery21/21. The browser
count includes version-conflicts12, four-editor checks36, company introduction84,
auth37, focused auth23, helper probes2, cross-browser78, follow-up9, frontend
smoke6 and page checks21. Duplicate standalone reruns and screenshots are not
added to that total. Later documentation-only repairs preserve the same
functional contract; fresh retest receipts are recorded in the repair report.

**AUTH-01 — not a bug by team decision.** The team confirmed this on 2026-11-24
and again on 2026-11-25; the user reconfirmed it on 2026-11-26. The database
correctly admits one account when concurrent requests use the same email; the
loser may return 500, as documented in [SPEC](../../SPEC.md#accounts-and-profile-setup).
The four old assertions expect 400/409 and remain ordinary failures. They are
not pending fixes, skipped tests or xfails, and must not be described as repaired.
The post-audit changes do not modify registration business logic.

Post-audit retest on 2026-11-26 (`fix/final-audit-20261126`, baseline above plus
the local OpenAPI/documentation patch): functional411 remains407 passed/4
accepted AUTH-01 assertion failures; all ten browser/probe scripts308/308,
SSR39/39 and delivery21/21 passed again. Docker build/start/seed, the complete
unit suite253/253 and PostgreSQL integration241/241 passed. Advanced fast ran
all six modes (292 cases); P8 generated864 requests with real_defect=0,
schema_drift=0 and test_config=0, including all four oracle self-checks.
Raw receipts remain outside Git in the review workspace's
`tmp/final-audit-20261126/repair/`. These are local patch measurements, not
claims that the patch has been pushed to GitHub main.
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
