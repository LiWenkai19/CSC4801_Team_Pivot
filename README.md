# Recruiting and Candidate Matching

## Project Overview

A shared FastAPI/SQLModel backend and React frontend support candidate profiles,
skill-overlap recommendations, applications, employer job/applicant management,
and interview scheduling. Authentication uses server-side sessions, HttpOnly
cookies and CSRF tokens. Core behavior and tests do not require an external LLM.

## Architecture Summary

Business rules live in `backend/app/users`, `candidate`, `employer` and `interview`.
Candidate and employer services share relational models and `match_score`.
The frontend uses same-origin `/api` requests; the backend routes have no `/api`
prefix. PostgreSQL is the business database; SQLite appears only in isolated
legacy account tests.

## Quick Start

See [INSTALL.md](INSTALL.md), especially [test commands](INSTALL.md#running-unit-tests).
The complete clean-install/Docker instructions are still outstanding.

## Running Unit Tests

After Python dependency installation and `npm ci` in `frontend`, run from the
repository root:

```sh
python tests/run_tests.py
```

This runs all `tests/unit` cases, existing pure schema tests in
`backend/tests/users/test_schema.py`, and the actual React component unit tests
through a pytest bridge. It needs no running database, browser or paid credentials.
`--junitxml=unit-results.xml` may be appended. There is no `xfail`, skip or default
filter to hide known failures. Any failed assertion or component subprocess gives
a nonzero exit status.

The new business tests invoke production functions with session/result doubles;
unit fixtures reject any real database connection. They prove rule/serialization/
query-construction contracts, not PostgreSQL lock behavior. Real-database and API
tests remain separately available:

```sh
python tests/run_tests.py --integration
```

That command requires explicit `CANDIDATE_TEST_DATABASE_URL` and
`EMPLOYER_TEST_DATABASE_URL` pointing only to a disposable local PostgreSQL
instance; see INSTALL. It runs the complete existing `backend/tests` suite,
including in-memory SQLite account tests. Both commands belong to the regression
evidence; integration/browser demonstrations do not replace required unit tests.

## Specialized Regression and Test Reports

The previously local exploratory suites and their portable tools are now in
[tests/specialized](tests/specialized/README.md); historical/browser/SSR evidence
and current migration results are in [docs/testing/REPORT.md](docs/testing/REPORT.md).
There are 21 specialized Python files and 10 browser/SSR modules, separate from
course unit tests. Use their managed entry, which creates a new loopback PG
cluster and keeps artifacts outside the repository:

```sh
python tests/specialized/run.py functional
python tests/specialized/run.py browser
python tests/specialized/run.py render
```

Install the separate test dependencies and PostgreSQL server tools as documented
there. Known business failures remain red: these commands do not fix application
code or force a successful status. The performance mode preserves its explicit
360-second budget; Docker remains excluded.

## Requirement–Test Mapping

Paths are repository-relative and test names identify actual assertions. The
course requirements are in [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md); the local
professor package was also checked. This table explicitly marks unresolved
behavior/documentation rather than treating a named test as proof of compliance.

| Requirement ID | Implementation file(s) | Named unit tests / verification evidence |
|---|---|---|
| FP-ARCH-1 | `backend/app/main.py`; `frontend/src/App.tsx`; shared SQLModel models | Full-stack code and historical local browser/PG evidence; Docker and clean-install acceptance remain outstanding. |
| FP-AUTH-1 | `backend/app/users/service.py`; `backend/app/users/schema.py` | `tests/unit/test_auth.py::test_fp_auth_1_registration_and_session_lifecycle`; `tests/unit/test_auth.py::test_fp_auth_1_duplicate_identifier_is_rejected`; `tests/unit/test_auth.py::test_fp_auth_1_invalid_registration`; `tests/unit/test_auth.py::test_fp_auth_1_login_checks_actual_password` |
| FP-AUTH-2 | `backend/app/users/security.py`; `backend/app/users/schema.py` | `tests/unit/test_auth.py::test_fp_auth_2_salted_hash_and_password_verification`; `tests/unit/test_auth.py::test_fp_auth_2_response_has_no_authentication_secrets` |
| FP-AUTH-3 | `backend/app/users/service.py`; candidate/employer routers and services | `tests/unit/test_auth.py::test_fp_auth_3_unauthenticated_is_401`; `tests/unit/test_auth.py::test_fp_auth_3_valid_session_and_role_guards`; `tests/unit/test_auth.py::test_fp_auth_3_expired_session_is_revoked`; `tests/unit/test_auth.py::test_fp_auth_3_csrf_contract`; `tests/unit/test_workflows.py::test_fp_auth_3_missing_object_becomes_404` |
| FP-CAN-1 | `backend/app/candidate/service.py`; `backend/app/candidate/schema.py` | `tests/unit/test_workflows.py::test_fp_can_1_profile_read_and_partial_replace`; `tests/unit/test_workflows.py::test_fp_can_1_skill_replace_normalizes_input`; `tests/unit/test_workflows.py::test_fp_can_1_invalid_profile_update`; `tests/unit/test_workflows.py::test_fp_can_1_course_resume_privacy_includes_related_employer`; `tests/unit/test_versions.py::test_stale_version_rejects_before_any_edit`; `backend/tests/candidate/test_versions.py::test_version_stale_edit_is_rejected_without_side_effects` (both resource types) |
| FP-CAN-2 | `backend/app/candidate/service.py`; `frontend/src/pages/candidate/JobsPage.tsx` | `tests/unit/test_matching.py::test_fp_can_2_recommendations_preserve_fields_and_rank_all_jobs`; `tests/unit/test_matching.py::test_fp_can_2_empty_jobs_and_missing_profile` |
| FP-CAN-3 | `backend/app/candidate/service.py`; shared Application/Booking models | `tests/unit/test_workflows.py::test_fp_can_3_pending_duplicate_and_application_owner`; `tests/unit/test_workflows.py::test_fp_can_3_owned_application_read_and_list_are_scoped`; `tests/unit/test_workflows.py::test_fp_can_3_booking_is_visible_in_both_role_serializers`; `tests/unit/test_workflows.py::test_fp_sec_1_other_candidate_cannot_read_application` |
| FP-EMP-1 | `backend/app/employer/service.py`; `backend/app/employer/schema.py` | `tests/unit/test_workflows.py::test_fp_emp_1_company_profile`; `tests/unit/test_workflows.py::test_fp_emp_1_missing_company_and_wrong_role` |
| FP-EMP-2 | `backend/app/employer/service.py`; `backend/app/employer/schema.py` | `tests/unit/test_workflows.py::test_fp_emp_2_job_create_read_and_replace`; `tests/unit/test_workflows.py::test_fp_emp_2_nonempty_fields_are_validated`; `tests/unit/test_workflows.py::test_fp_emp_2_job_validation_and_deletion`; `tests/unit/test_workflows.py::test_fp_emp_2_company_required_and_missing_job`; `tests/unit/test_workflows.py::test_fp_sec_1_foreign_employer_cannot_manage_job`; `backend/tests/candidate/test_versions.py::test_version_concurrent_replacements_have_one_complete_winner`; `frontend/tests/specialized/version_conflicts.mjs` |
| FP-EMP-3 | `backend/app/employer/service.py`; `backend/app/employer/schema.py` | `tests/unit/test_matching.py::test_fp_match_1_employer_ties_use_name_then_stable_id`; `tests/unit/test_workflows.py::test_fp_emp_3_applicant_status_and_booking_preservation`; `tests/unit/test_workflows.py::test_fp_emp_3_other_employer_and_candidate_cannot_change_status`; `tests/unit/test_workflows.py::test_fp_emp_3_invalid_status_is_rejected`; `tests/unit/test_workflows.py::test_fp_can_3_booking_is_visible_in_both_role_serializers` |
| FP-MATCH-1 | `backend/app/employer/matching.py`; both workflow services | `tests/unit/test_matching.py::test_fp_match_1_examples_normalization_and_floor`; `tests/unit/test_matching.py::test_fp_can_2_recommendations_preserve_fields_and_rank_all_jobs`; `tests/unit/test_matching.py::test_fp_match_1_employer_ties_use_name_then_stable_id` |
| FP-MATCH-2 | N/A | Optional LLM explanation/recommendation is not implemented; no paid credentials are needed. |
| FP-SCHED-1 | `backend/app/interview/service.py`; `backend/app/interview/schema.py`; `backend/app/interview/router.py` | `tests/unit/test_scheduling.py::test_fp_sched_1_slot_creation_timezones_and_deletion`; `tests/unit/test_scheduling.py::test_fp_sched_1_invalid_slots`; `tests/unit/test_scheduling.py::test_fp_sched_1_time_boundary_rejected_before_write`; `tests/unit/test_scheduling.py::test_fp_sched_1_overlap_is_conflict`; `tests/unit/test_scheduling.py::test_fp_sched_1_delete_rejects_invalid_state`; `tests/unit/test_scheduling.py::test_fp_sched_1_management_list_preserves_booking_flag`; `tests/unit/test_scheduling.py::test_fp_sched_1_route_error_contract` |
| FP-SCHED-2 | `backend/app/candidate/service.py`; `backend/app/employer/service.py` | `tests/unit/test_scheduling.py::test_fp_sched_2_eligible_booking`; `tests/unit/test_scheduling.py::test_fp_sched_2_ineligible_booking`; `tests/unit/test_scheduling.py::test_fp_sched_2_available_list_filters_owner_time_length_and_booking`; `tests/unit/test_scheduling.py::test_fp_sched_2_commit_failure_rolls_back`; `tests/unit/test_workflows.py::test_fp_can_3_booking_is_visible_in_both_role_serializers`; `tests/unit/test_workflows.py::test_fp_emp_3_applicant_status_and_booking_preservation` |
| FP-SCHED-3 | `backend/app/candidate/service.py::book`; Booking unique constraints | `tests/unit/test_scheduling.py::test_fp_sched_3_conflict_contract` covers slot/application conflicts, exact 409 message and unclassified errors. Real-PG evidence additionally exists in `backend/tests/candidate/test_booking.py::test_real_postgres_two_candidates_compete_for_one_slot`; `backend/tests/candidate/test_booking.py::test_same_application_concurrent_booking_has_one_winner`. |
| FP-SEC-1 | Candidate/employer ownership and role checks | `tests/unit/test_workflows.py::test_fp_sec_1_other_candidate_cannot_read_resume`; `tests/unit/test_workflows.py::test_fp_sec_1_other_candidate_cannot_read_application`; `tests/unit/test_workflows.py::test_fp_sec_1_foreign_employer_cannot_manage_job`; `tests/unit/test_scheduling.py::test_fp_sched_2_ineligible_booking`; `backend/tests/candidate/test_versions.py::test_version_does_not_override_authorization_or_missing_resource_errors`. Owner-only resume access remains enforced. |
| FP-SEC-2 | `backend/app/users/service.py::get_user_by_email`; SQLAlchemy bound queries | `tests/unit/test_auth.py::test_fp_sec_2_email_is_a_bound_value` compiles the actual query and checks separate bound parameters; no SQL text is executed. |
| FP-SEC-3 | `frontend/src/components/skills/SkillTagPicker.tsx`; React text rendering | `tests/unit/test_rendering.py::test_fp_sec_3_actual_component_escapes_required_text` runs `frontend/tests/rendering.unit.mjs`: actual component SSR of the required script string, ordinary Unicode/quotes, and label association. This is not a full browser/security proof. |
| FP-SEC-4 | `tests/unit/conftest.py`; isolated existing integration fixtures | Unit tests prohibit Engine.connect, use session doubles and synthetic data; component tests render locally. Integration tests use disposable PG and isolated SQLite. Historical secret/lock audits remain supplementary; not a universal secrets guarantee. |
| FP-PROC-1 | `SPEC.md`; module plans | SPEC describes current slot semantics but other required design sections remain incomplete. This test-only change does not claim full specification compliance. |
| FP-DOC-1 | `INSTALL.md`; `tests/run_tests.py` | Exact unit and optional integration commands below; complete Docker/setup acceptance remains outstanding. |
| FP-DOC-2 | `README.md` | This table covers all 25 IDs with named functional tests. The table records evidence and outstanding failures, not universal requirement fulfillment. |
| FP-DOC-3 | `backend/scripts/seed_demo.py` | The existing script resets the configured database (from backend: `python scripts/seed_demo.py`). Prior semantic snapshot checks passed, but its 60-minute slot does not meet the required 30-minute shared booking demo; not repaired here. |
| FP-TEST-1 | `tests/unit/`; existing `backend/tests/users/test_schema.py`; `tests/run_tests.py`; `frontend/tests/rendering.unit.mjs` | One non-interactive unit command includes backend business/schema and actual component tests; it returns nonzero for any failure. Version-schema, stale-write, no-op and server-assigned creation contracts are in `tests/unit/test_versions.py`; real-PG migration and concurrency tests are under `backend/tests/candidate/`. |
| FP-SUB-1 | `Dockerfile`; GitHub main commit submission | Permanent public main commit and complete Docker build/start remain final submission checks. Docker is excluded from this local test-only task; no submission or CI pass is claimed. |

## Verification Status and Known Limitations

Validation baseline: `5143f1e944cac5b9e19e484320e2684b883b5ab4` plus the
user-authorized local version-protection patch (2026-11-23). No new commit is
claimed. Historical reports retain their original versions and results.

- Complete unit command: **137 passed**, no failures/errors/skips. This includes
  115 business/component-bridge cases and 22 existing schema cases. The bridge
  executes 3 Node component assertions; those are not added again to the pytest
  count. Original 17 `pass` templates have been replaced by substantive tests.
- Existing API/database regression on a fresh isolated PostgreSQL instance:
  **195 passed**, no failures/errors/skips. This is not 195 pure unit tests.
- The original privacy test passes after teammate commit `5143f1e`; this patch
  preserves owner-only resume access.
- REG-CAND-01 and REG-JOB-01 are repaired with parent-row locking and mandatory
  version checks. Stale pages receive 409 and retain their drafts. The three-engine,
  two-language browser suite passes all **12 double-tab scenarios**.
- Complete specialized functional replay: **375 passed, 18 failed**. The six
  previously failing skill-replacement cases pass; the remaining failures are
  known date, text-storage and registration issues, not hidden with skip/xfail.
- Follow-up remaining regression: **169 browser scenarios, 161 passed/8 known
  failures** (including the 12 version-conflict scenarios above); **36 SSR** and
  **4 performance** checks passed. Original mutation samples detected 7/7
  non-equivalent changes; non-Docker delivery retained 13 passes/8 known failures.
  See the [follow-up report](docs/testing/VERSION_RETEST.md) for failed-case causes,
  test-tool adaptations and the bounded six-minute soak evidence.
- Text-storage errors and other unrelated reported bugs remain unrepaired.
  Detailed before/after evidence is in the [version repair report](docs/testing/VERSION_PROTECTION.md).
- Docker, incomplete SPEC/installation sections, demo seed slot duration and
  migration default drift remain outstanding. External test reports do not
  automatically satisfy these repository delivery obligations.

## Document Index

- [Installation and test commands](INSTALL.md)
- [Product requirements](docs/REQUIREMENTS.md)
- [Living specification](SPEC.md)
- [Candidate integration notes](docs/completed/CANDIDATE_REBUILD.md) (historical; older test
  counts/import limitations there are not current validation results)
- [Business unit tests](tests/unit/)
- [Component rendering unit tests](frontend/tests/rendering.unit.mjs)
- [Existing API/database regression](backend/tests/)
- [Specialized test suites and runners](tests/specialized/README.md)
- [Consolidated and historical test reports](docs/testing/REPORT.md)

The consolidated report and rewritten historical report copies are committed in
`docs/testing`. Raw logs, database directories, screenshots, dependency installations
and synthetic session values remain local artifacts. The current version repair
is documented separately from the historical test-only reports.
