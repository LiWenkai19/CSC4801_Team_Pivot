# Cross-Team Peer Review

Read this document before inspecting another team's project. A finding is eligible for points only if it follows this process and the safety boundary. 

> **MUST** and **MUST NOT** requirements are graded. **SHOULD** items are recommended but not graded unless they are required by another **MUST**. **MAY** items are optional.

## 0. Safety boundary

Audit only the target team's source code at the latest commit on its `main` branch, built from the repository's `Dockerfile`, on your own machine or in your own CI. Fixes are pushed to `main`, so always work against the newest commit rather than an older one. You **MAY**:

- read source code and documentation;
- build the environment from the repository's `Dockerfile` and run the project's documented test suite and local server from it;
- write and run a minimal regression test against the local checkout; and
- run static analysis, linters, dependency scanners, and secret scanners against that checkout.

You **MUST NOT**:

- test any deployed URL, shared staging system, real third-party account, or resource the target team did not explicitly provide as local test data;
- perform load testing, denial of service, resource exhaustion, destructive testing, social engineering, or secret exfiltration;
- modify the target team's branches, pull requests, CI, repository settings, or any issue other than the finding you file;
- publish a secret value or personal data; report only its redacted location; or
- scan anything outside the local checkout.

These restrictions apply even if a technique might reveal a valid bug. A safety violation is an academic-integrity issue, not merely an invalid report.

## 1. Audit target

1. Clone the assigned repository and check out the latest commit on its `main` branch.
2. Build the environment from the repository's `Dockerfile` (see [`DOCKER.md`](DOCKER.md)). You **MUST NOT** modify the target source to make the build work.
3. Follow the target team's `INSTALL.md` to start, migrate, seed, test, and smoke-test the environment. You **MUST NOT** modify the target source or repair its setup on a branch or pull request.
4. Use the checked-out source for code inspection and the running Docker environment for runtime review.
5. Record the exact commit SHA where you observed the bug in every report.
6. File findings only during the published audit window.

A finding that omits the exact commit SHA where the bug was observed is not reproducible and is invalid. If the repository's `Dockerfile` fails to build or run, report that environmental problem (it is itself a valid finding) rather than modifying the target source. When the target team pushes a fix to `main`, retest against the latest commit on `main`.

## 2. Valid finding standard

A valid finding **MUST** satisfy every condition below:

- **In scope:** it violates a **MUST** requirement in the course [`REQUIREMENTS.md`](REQUIREMENTS.md), the target team's precise `SPEC.md`, or a documented behavior exposed to users.
- **Present:** it occurs in the environment built from the target repository's `Dockerfile` at the latest `main` commit, without changing the target source.
- **Reproducible:** the report gives exact setup and execution commands plus the smallest practical input or test needed to observe it.
- **Observable:** expected and actual results differ in a concrete way. A style preference, hypothetical concern with no reachable path, or unsupported scanner warning is not a bug.
- **Independent:** it is not a duplicate symptom of an already reported root cause. Search open and closed issues before filing.
- **Safe:** it was found within the boundary in Section 0.

File every finding through the GitHub Issue Form at [`templates/github/ISSUE_TEMPLATE/audit_bug_report.yml`](templates/github/ISSUE_TEMPLATE/audit_bug_report.yml); every team **MUST** enable it in their repository. Missing a required field or reproduction makes the report invalid. One issue **SHOULD** describe one root cause; split only unrelated findings.

### Report types

Every report **MUST** use `audit:report` and `status:needs-triage`, plus exactly one type label. Apply exactly one type label:

| Label | Use when |
|---|---|
| `type:functional` | A required workflow, specification rule, or required test/CI behavior is missing, incorrect, crashes, or cannot be completed. |
| `type:security` | Authentication, authorization, privacy, injection, XSS, prompt safety, secret handling, or test isolation is violated. |
| `type:performance` | A documented performance expectation fails on a small, safe fixture; load or resource-exhaustion testing is never allowed. |

Choose the type that best represents the root cause. `type:security` takes precedence when more than one type could apply.

Every team imports all audit labels (`audit:*`, `type:*`, and `status:*`) into their repository from [`templates/github/labels.yml`](templates/github/labels.yml) so that every repository uses the same label set.

## 3. Reproduction quality

A reader with no prior context should be able to reproduce the result. Include:

- OS and Docker versions and the exact commit SHA you built and observed the bug at, plus any deviation from `INSTALL.md`;
- exact reset and seed commands;
- exact request, UI sequence, or minimal failing test;
- relevant response, exception, assertion, or database count;
- expected behavior with the requirement ID or `SPEC.md` section; and
- actual behavior with secrets and personal data redacted.

Screenshots **MAY** supplement commands but **MUST NOT** replace them. For a concurrency finding, use a synchronization barrier or another repeatable method; sequential requests do not establish a concurrency bug. For a scanner finding, trace the warning to a reachable code path and provide a harmless local proof.

## 4. Triage and resolution

Every new report begins with `status:needs-triage`. The target team or instructor changes it to one of:

- `status:confirmed`: reproducible, in scope, safe, and not a duplicate;
- `status:rejected`: fails any condition in Section 2;
- `status:duplicate`: has the same root cause as an earlier issue, which **MUST** be linked; or
- `status:fixed`: the fix and regression evidence pass at the linked fix commit.

The reporter **MUST NOT** mark their own report confirmed or fixed. For a confirmed issue, the target team **MUST** add a regression test, repair the issue through its normal review process, and open a pull request that links back to the bug report issue and documents the root cause, fix, and verification. The reporter **MAY** build the fixed environment from the linked commit, retest locally, and comment with the result.

All reports and fixes **MUST** meet the published deadlines.

If teams disagree, each side **SHOULD** post one concise, evidence-based comment and ask the instructor or TA to decide. Do not repeatedly change labels or argue about intent. The instructor's final status controls scoring.

## 5. Academic integrity and anti-gaming

- **MUST NOT** split one root cause into several reports to receive extra points.
- **MUST NOT** move, reuse, or backdate commits or claim evidence from a different commit.
- **MUST NOT** fabricate evidence, coordinate duplicate findings, or hide information needed to reproduce a result.
- **MUST NOT** violate the safety boundary to find or demonstrate a bug.

Fabricated evidence, collusion, commit manipulation, and safety violations are academic-integrity matters and earn no audit points.
