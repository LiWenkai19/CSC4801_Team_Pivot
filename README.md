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

Build and start the single-container environment using the Docker guide, then load the demo data and run the unit tests. For development against a local PostgreSQL server, follow the local setup instructions. [Docker build](INSTALL.md#docker-build) · [Docker startup and test commands](INSTALL.md#docker-startup) · [Local development](INSTALL.md#local-development)

The local setup covers configuration, database creation, migrations, seeding, startup, and tests.

### Demo accounts

`backend/scripts/seed_demo.py` creates the accounts below. They are **local/demo
credentials only** — never use them in a deployed environment.

| Role | Email | Password |
| --- | --- | --- |
| Employer 1 | `demo-employer1@example.com` | `demo-local-only` |
| Employer 2 | `demo-employer2@example.com` | `demo-local-only` |
| Candidate Alice | `demo-alice@example.com` | `demo-local-only` |
| Candidate Bob | `demo-bob@example.com` | `demo-local-only` |
| Candidate Carol | `demo-carol@example.com` | `demo-local-only` |

Alice and Bob both have an `Interviewing` application for the same job and can
compete for the single shared 30-minute slot, which demonstrates the booking
conflict path.

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

The complete suite was re-run from this branch on 2026-11-26: **252 unit cases
passed** (exit 0), including the P1 property tests and the P7 mutation-hardening
tests. The disposable-PostgreSQL integration command passed **241 cases**
(exit 0) on a local PostgreSQL 17.6 temporary cluster; Docker and CI run the same
suite on PostgreSQL 15.

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

## Specialized Regression

The previously local exploratory suites and their portable tools are now in
[tests/specialized](tests/specialized/README.md).
There are 21 specialized Python files and 10 browser/SSR modules, separate from
course unit tests. Use their managed entry, which creates a new loopback PG
cluster and keeps artifacts outside the repository:

```sh
python tests/specialized/run.py functional
python tests/specialized/run.py browser
python tests/specialized/run.py render
```

Install the separate test dependencies and PostgreSQL server tools as documented
there. These suites are supplementary: the graded command remains
`python tests/run_tests.py`, and CI does not run the specialized browser suites.
They never modify application code or force a successful status. The performance
mode preserves its explicit 360-second budget; Docker remains excluded.

## Advanced Testing and Verification

The required course suite above is kept independent of the advanced layer in
`tests/advanced/`. That layer adds 13 techniques from lectures L12–L14 —
property-based and stateful testing, finite-trace LTL, Z3 specification and
model-checking proofs, differential testing, mutation testing, OpenAPI property
fuzzing, metamorphic/intramorphic experiments, an LLM blind experiment, security
scans and coverage. These are **supplementary evidence, not a replacement for
the required unit tests**: they do not change the required
`python tests/run_tests.py` command, they use separately pinned dependencies and
disposable loopback PostgreSQL databases, and every artifact is written outside
the checkout. Each oracle is required to pass a deliberate-break self-check
(break it, watch it go red, restore), and fixed seeds keep the runs repeatable.

- **P0 — reproducible runner** (L12 test levels; L13 methods): one entry point, disposable PostgreSQL, artifacts outside the repository.
- **P1 — property-based tests** (L13 property testing): 9 FP-MATCH-1 properties with an independent `Fraction` oracle, 200 examples each; part of the required suite.
- **P2 — stateful model** (L12/L13 state machines): 25 Hypothesis examples and 300 steps checking 5 booking invariants.
- **P3 — finite-trace LTL** (L13 slides 46–52): 5 temporal properties over 25 recorded traces, plus 232 checker self-tests.
- **P4 — Z3 matching proof** (L13 Hoare triples/SMT): 7 `unsat` proofs, 2 `sat` negative controls, and 1,024 specification/code pairs.
- **P5 — booking BMC and k-induction** (L13): bounded model checking at k=6, induction at k=1, and reachability witnesses against vacuous proofs.
- **P6 — differential testing** (L12 differential oracle): 600 Python-vs-SQL score pairs and 600 candidate/employer view pairs.
- **P7 — mutation testing** (L13 slide 17; L14 slide 28): 304 injected mutants, 93.71% score after the required-suite hardening.
- **P8 — OpenAPI property fuzzing** (L14 slide 29): 28 operations and 864 generated requests; the one real contract defect found is fixed and regression-tested.
- **P9 — metamorphic and intramorphic testing** (L12 slides 29–41): 5 workflow relations plus 5 defense-layer experiments, including the 5-round I2 concurrent-booking race.
- **P10 — LLM blind experiment** (L14 Exercise 1/3): 124 generated cases and a generated-vs-handwritten mutant comparison.
- **P12 — dependency and secret scans** (L14): full-history secret scan with zero leaks and dependency advisories triaged to zero pending.
- **P11 — coverage** (L12): 98.85% combined statement and 96.97% branch coverage, with a 90% unit branch gate in CI.

Run the suite from the repository root (the full instructions, including
`PG_BIN`/`ADVANCED_PG_URL`, are in the
[advanced test section of INSTALL.md](INSTALL.md#advanced-test-suite-optional)):

```sh
python -m pip install -r requirements.txt -r tests/advanced/requirements.txt
python tests/advanced/run.py list
python tests/advanced/run.py fast
python tests/advanced/run.py all --out <new empty directory outside the checkout>
```

The complete results, per-technique limitations and the P8 defect/fix loop are
in [ADVANCED_REPORT.md](docs/advanced_testing/ADVANCED_REPORT.md); exact sizes,
seeds and evidence paths are in the per-technique documents beside it.

## Requirement–Test Mapping

Paths are repository-relative and test names identify actual assertions. The
course requirements are in [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md); the local
professor package was also checked. The **Required named unit tests** column
lists cases that run under `python tests/run_tests.py`. The
**Mutation-hardening** column lists the additional required-suite tests added to
kill surviving mutants (P7), so it is part of the same command. The
**Supplementary evidence** column is explicitly *not* part of the required unit
suite: it records real-PostgreSQL, browser, or advanced-suite evidence. This
table marks unresolved behavior/documentation rather than treating a named test
as proof of compliance.

| Requirement ID | Implementation file(s) | Required named unit tests | Mutation-hardening unit tests (P7, required suite) | Supplementary evidence (not required by FP-TEST-1) |
|---|---|---|---|---|
| FP-ARCH-1 | `backend/app/main.py`, `backend/app/users/model.py`, `backend/app/employer/model.py`, `frontend/src/App.tsx`, `Dockerfile`, `deploy/` | — (architecture is exercised end-to-end) | — | Full-stack browser and PostgreSQL evidence and the single-container Docker build/start check; CI runs the documented commands inside the image. |
| FP-AUTH-1 | `backend/app/users/service.py`; `backend/app/users/schema.py` | `tests/unit/test_auth.py`:<br>`test_fp_auth_1_registration_and_session_lifecycle`<br>`test_fp_auth_1_duplicate_identifier_is_rejected`<br>`test_fp_auth_1_invalid_registration`<br>`test_fp_auth_1_login_checks_actual_password` | `tests/unit/test_mutation_hardening.py`:<br>`test_pauth1_profile_completed_tracks_the_role_specific_profile`<br>`test_pauth1_session_lifetime_has_two_documented_forms` | — |
| FP-AUTH-2 | `backend/app/users/security.py`; `backend/app/users/schema.py` | `tests/unit/test_auth.py`:<br>`test_fp_auth_2_salted_hash_and_password_verification`<br>`test_fp_auth_2_response_has_no_authentication_secrets`<br>`test_fp_auth_2_validation_errors_do_not_echo_password` | — | — |
| FP-AUTH-3 | `backend/app/users/service.py`; candidate/employer routers and services | `tests/unit/test_auth.py`:<br>`test_fp_auth_3_unauthenticated_is_401`<br>`test_fp_auth_3_valid_session_and_role_guards`<br>`test_fp_auth_3_expired_session_is_revoked`<br>`test_fp_auth_3_csrf_contract`<br>`tests/unit/test_workflows.py`:<br>`test_fp_auth_3_missing_object_becomes_404` | `tests/unit/test_mutation_hardening.py`:<br>`test_pauth3_session_lookup_uses_the_sha256_digest`<br>`test_pauth3_revoke_all_sessions_touches_one_account`<br>`test_pauth3_candidate_services_reject_the_employer_role` | — |
| FP-CAN-1 | `backend/app/candidate/service.py`; `backend/app/candidate/schema.py` | `tests/unit/test_workflows.py`:<br>`test_fp_can_1_profile_read_and_partial_replace`<br>`test_fp_can_1_skill_replace_normalizes_input`<br>`test_fp_can_1_invalid_profile_update`<br>`test_fp_can_1_course_resume_privacy_includes_related_employer`<br>`tests/unit/test_versions.py`:<br>`test_stale_version_rejects_before_any_edit` | `tests/unit/test_mutation_hardening.py`:<br>`test_pcan1_candidate_profile_creation_persists_normalized_skills`<br>`test_pcan1_candidate_profile_conflicts_are_translated`<br>`test_pcan1_candidate_profile_creation_requires_the_candidate_role`<br>`test_pcan1_owner_reads_own_private_profile`<br>`test_pcan1_profile_update_locks_the_owner_row` | `backend/tests/candidate/test_versions.py::test_version_stale_edit_is_rejected_without_side_effects` (both resource types); four-editor browser workflow in `frontend/tests/specialized/editor_update_checks.mjs`. |
| FP-CAN-2 | `backend/app/candidate/service.py`; `frontend/src/pages/candidate/JobsPage.tsx` | `tests/unit/test_matching.py`:<br>`test_fp_can_2_recommendations_preserve_fields_and_rank_all_jobs`<br>`test_fp_can_2_empty_jobs_and_missing_profile` | `tests/unit/test_mutation_hardening.py`:<br>`test_pcan2_get_job_reads_only_the_requested_active_job`<br>`test_pcan2_recommendations_scope_applied_flag_and_skills_to_the_caller` | — |
| FP-CAN-3 | `backend/app/candidate/service.py`; shared Application/Booking models | `tests/unit/test_workflows.py`:<br>`test_fp_can_3_pending_duplicate_and_application_owner`<br>`test_fp_can_3_owned_application_read_and_list_are_scoped`<br>`test_fp_can_3_booking_is_visible_in_both_role_serializers`<br>`test_fp_sec_1_other_candidate_cannot_read_application` | `tests/unit/test_mutation_hardening.py`:<br>`test_pcan3_applying_to_a_missing_or_deleted_job_is_not_found`<br>`test_pcan3_missing_and_foreign_applications_are_not_visible`<br>`test_pcan3_application_list_is_scoped_to_the_caller`<br>`test_pcan3_apply_locks_the_active_job_and_returns_the_public_view`<br>`test_pcan3_duplicate_apply_from_the_unique_constraint_is_a_conflict`<br>`test_pcan3_non_duplicate_integrity_error_surfaces_unchanged` | P9 I3 shows the duplicate-apply rule is also backstopped by the database unique constraint, not only the application precheck (`docs/advanced_testing/INTRAMORPHIC.md`). |
| FP-EMP-1 | `backend/app/employer/service.py`; `backend/app/employer/schema.py` | `tests/unit/test_workflows.py`:<br>`test_fp_emp_1_company_profile`<br>`test_fp_emp_1_missing_company_and_wrong_role` | `tests/unit/test_mutation_hardening.py`:<br>`test_pemp1_employer_profile_creation_and_conflicts`<br>`test_pemp1_employer_profile_failures_are_translated`<br>`test_pemp1_company_update_requires_a_profile_and_locks_it` | `backend/tests/candidate/test_extended_versions.py::test_stale_company_or_status_tab_cannot_overwrite_newer_save[company]`; company edit cases in `tests/unit/test_versions.py`. |
| FP-EMP-2 | `backend/app/employer/service.py`; `backend/app/employer/schema.py` | `tests/unit/test_workflows.py`:<br>`test_fp_emp_2_job_create_read_and_replace`<br>`test_fp_emp_2_nonempty_fields_are_validated`<br>`test_fp_emp_2_job_validation_and_deletion`<br>`test_fp_emp_2_company_required_and_missing_job`<br>`test_fp_sec_1_foreign_employer_cannot_manage_job` | `tests/unit/test_mutation_hardening.py`:<br>`test_pemp2_job_list_is_owner_scoped_newest_first`<br>`test_pemp2_job_creation_rolls_back_infrastructure_failure`<br>`test_pemp2_job_deletion_checks_both_dependent_tables`<br>`test_pemp2_job_deletion_rolls_back_infrastructure_failure`<br>`test_pemp2_job_access_and_skill_queries_are_owner_scoped` | `backend/tests/candidate/test_versions.py::test_version_concurrent_replacements_have_one_complete_winner`; `frontend/tests/specialized/version_conflicts.mjs`. |
| FP-EMP-3 | `backend/app/employer/service.py`; `backend/app/employer/schema.py` | `tests/unit/test_matching.py::test_fp_match_1_employer_ties_use_name_then_stable_id`<br>`tests/unit/test_workflows.py`:<br>`test_fp_emp_3_applicant_status_and_booking_preservation`<br>`test_fp_emp_3_other_employer_and_candidate_cannot_change_status`<br>`test_fp_emp_3_invalid_status_is_rejected`<br>`test_fp_can_3_booking_is_visible_in_both_role_serializers` | `tests/unit/test_mutation_hardening.py`:<br>`test_pemp3_status_change_requires_a_live_owned_job`<br>`test_pemp3_applicant_list_skips_rows_without_a_profile`<br>`test_pemp3_booking_lookup_is_application_scoped` | Applicant-status version and booking-preservation regressions in `backend/tests/candidate/test_extended_versions.py` and the four-editor browser workflow. |
| FP-MATCH-1 | `backend/app/employer/matching.py`; both workflow services | `tests/unit/test_matching.py`:<br>`test_fp_match_1_examples_normalization_and_floor`<br>`test_fp_can_2_recommendations_preserve_fields_and_rank_all_jobs`<br>`test_fp_match_1_employer_ties_use_name_then_stable_id`<br>`tests/unit/test_matching_properties.py` (9 properties, P1):<br>`test_fp_match_1_property_score_is_bounded_integer`<br>`test_fp_match_1_property_equals_independent_oracle`<br>`test_fp_match_1_property_empty_required_is_100`<br>`test_fp_match_1_property_invariant_under_permutation_duplication_whitespace`<br>`test_fp_match_1_property_irrelevant_skill_does_not_change_score`<br>`test_fp_match_1_property_adding_required_skill_never_decreases`<br>`test_fp_match_1_property_monotone_in_overlap`<br>`test_fp_match_1_property_normalize_is_idempotent_and_canonical`<br>`test_fp_match_1_property_inputs_are_not_mutated` | — | P4 Z3 theorem/proof evidence for the specification (`docs/advanced_testing/FORMAL_MATCHING.md`), P6 600-pair Python-vs-SQL differential (`tests/advanced/differential/`), and P9 I4 order-insensitivity (`docs/advanced_testing/INTRAMORPHIC.md`). |
| FP-MATCH-2 | N/A | — (not implemented) | — | Optional LLM explanation/recommendation is not implemented; no paid credentials are needed. |
| FP-SCHED-1 | `backend/app/interview/service.py`; `backend/app/interview/schema.py`; `backend/app/interview/router.py` | `tests/unit/test_scheduling.py`:<br>`test_fp_sched_1_slot_creation_timezones_and_deletion`<br>`test_fp_sched_1_invalid_slots`<br>`test_fp_sched_1_time_boundary_rejected_before_write`<br>`test_fp_sched_1_overlap_is_conflict`<br>`test_fp_sched_1_delete_rejects_invalid_state`<br>`test_fp_sched_1_management_list_preserves_booking_flag`<br>`test_fp_sched_1_route_error_contract`<br>`test_fp_sched_1_openapi_422_documents_business_and_validation_shapes` | `tests/unit/test_mutation_hardening.py`:<br>`test_psched1_slot_creation_requires_an_employer_profile`<br>`test_psched1_overlap_query_is_employer_scoped_and_half_open`<br>`test_psched1_slot_end_must_precede_the_documented_cutoff`<br>`test_psched1_slot_list_is_employer_scoped_and_future_only`<br>`test_psched1_slot_deletion_queries_are_scoped` | P8 OpenAPI fuzzing found the 422 response-shape defect, fixed in `0ea7223` and covered by the last required test above (`docs/advanced_testing/findings/P8.md`). |
| FP-SCHED-2 | `backend/app/candidate/service.py`; `backend/app/employer/service.py` | `tests/unit/test_scheduling.py`:<br>`test_fp_sched_2_eligible_booking`<br>`test_fp_sched_2_ineligible_booking`<br>`test_fp_sched_2_available_list_filters_owner_time_length_and_booking`<br>`test_fp_sched_2_commit_failure_rolls_back`<br>`tests/unit/test_workflows.py`:<br>`test_fp_can_3_booking_is_visible_in_both_role_serializers`<br>`test_fp_emp_3_applicant_status_and_booking_preservation` | `tests/unit/test_mutation_hardening.py`:<br>`test_psched2_booking_reads_are_scoped_to_the_application_and_slot`<br>`test_psched2_available_slots_query_carries_every_eligibility_rule`<br>`test_psched2_available_slots_requires_the_application_job`<br>`test_psched2_slot_reserved_for_another_job_is_a_conflict`<br>`test_psched2_booking_requires_the_application_job` | P2 stateful model and P3 finite-trace LTL check the booking lifecycle over recorded traces (`tests/advanced/stateful/`, `docs/advanced_testing/LTL.md`). |
| FP-SCHED-3 | `backend/app/candidate/service.py::book`; Booking unique constraints | `tests/unit/test_scheduling.py::test_fp_sched_3_conflict_contract` covers slot/application conflicts, the exact 409 message and unclassified errors. | `tests/unit/test_mutation_hardening.py::test_psched3_conflict_recovery_queries_are_scoped` | **Supplementary evidence, not required by FP-TEST-1:** P9 I2 runs 5 rounds of two real threads/sessions against one slot and observes exactly one 201, one 409 and one booking row each round (`docs/advanced_testing/INTRAMORPHIC.md`); P5 proves booking invariants on the abstract state machine with BMC (k=6) and k-induction (`docs/advanced_testing/FORMAL_BOOKING.md`); real-PG races are in `backend/tests/candidate/test_booking.py`. |
| FP-SEC-1 | `backend/app/users/service.py`; `backend/app/candidate/service.py`; `backend/app/employer/service.py`; `backend/app/interview/service.py`; candidate/employer routers | `tests/unit/test_workflows.py`:<br>`test_fp_sec_1_other_candidate_cannot_read_resume`<br>`test_fp_sec_1_other_candidate_cannot_read_application`<br>`test_fp_sec_1_foreign_employer_cannot_manage_job`<br>`tests/unit/test_scheduling.py::test_fp_sched_2_ineligible_booking`<br>`tests/unit/test_versions.py` covers version-write authorization indirectly through `test_stale_version_rejects_before_any_edit`. | `tests/unit/test_mutation_hardening.py`:<br>`test_pauth3_candidate_services_reject_the_employer_role`<br>`test_pcan1_owner_reads_own_private_profile`<br>`test_pcan3_missing_and_foreign_applications_are_not_visible`<br>`test_pcan3_application_list_is_scoped_to_the_caller`<br>`test_pemp2_job_list_is_owner_scoped_newest_first`<br>`test_pemp2_job_access_and_skill_queries_are_owner_scoped`<br>`test_pemp3_status_change_requires_a_live_owned_job`<br>`test_psched1_slot_list_is_employer_scoped_and_future_only`<br>`test_psched1_slot_deletion_queries_are_scoped`<br>`test_psched2_booking_reads_are_scoped_to_the_application_and_slot`<br>`test_psched2_slot_reserved_for_another_job_is_a_conflict` | **Supplementary evidence, not required by FP-TEST-1:** P9 I2 two-thread booking race and P5 formal booking model (same evidence as FP-SCHED-3); P8's per-role request matrix exercises the unauthenticated/forbidden/missing-object boundaries (`docs/advanced_testing/APIFUZZ.md`). Owner-only resume access remains enforced. |
| FP-SEC-2 | `backend/app/users/service.py::get_user_by_email`; SQLAlchemy bound queries | `tests/unit/test_auth.py::test_fp_sec_2_email_is_a_bound_value` compiles the actual query and checks separate bound parameters; no SQL text is executed. | `tests/unit/test_mutation_hardening.py::test_pauth3_email_lookup_is_equality_on_a_bound_value` | — |
| FP-SEC-3 | `frontend/src/components/skills/SkillTagPicker.tsx`; React text rendering | `tests/unit/test_rendering.py::test_fp_sec_3_actual_component_escapes_required_text` runs `frontend/tests/rendering.unit.mjs`: actual component SSR of the required script string, ordinary Unicode/quotes, and label association. | — | This is not a full browser/security proof. |
| FP-SEC-4 | `tests/unit/conftest.py`; isolated existing integration fixtures | — (enforced by the shared fixtures rather than one named test) | — | Unit tests prohibit Engine.connect and use session doubles; integration tests use disposable PostgreSQL and isolated SQLite; P12 scans the full history for secrets and audits dependencies (`docs/advanced_testing/SECURITY_SCANS.md`). |
| FP-PROC-1 | `SPEC.md` | — (documentation requirement) | — | SPEC covers architecture, data models, authorization, API routes, UI workflows, matching, booking, and security controls. |
| FP-DOC-1 | `INSTALL.md`, `tests/run_tests.py`, `Dockerfile` | — (documentation requirement) | — | The guide documents Docker build, startup, migrations, seeding, and test commands, plus the local development setup and optional advanced suite. |
| FP-DOC-2 | `README.md` | — (documentation requirement) | — | This table covers all 25 requirement IDs with named functional tests and separated supplementary evidence; it records evidence and known limitations, not universal requirement fulfillment. |
| FP-DOC-3 | `backend/scripts/seed_demo.py` | — (data requirement) | — | From `backend`, run `python scripts/seed_demo.py` to reset the configured demo database. The seed creates one shared 30-minute slot; Alice and Bob both have `Interviewing` applications for the same job and can compete for that slot. |
| FP-TEST-1 | `tests/unit/`; existing `backend/tests/users/test_schema.py`; `tests/run_tests.py`; `frontend/tests/rendering.unit.mjs` | One non-interactive command, `python tests/run_tests.py`, includes backend business/schema and actual component tests and returns nonzero for any failure (252 passed on 2026-11-26). Version-schema, stale-write, no-op and server-assigned creation contracts are in `tests/unit/test_versions.py`. | The whole mutation-hardening column above is part of this command. | Real-PG migration/concurrency tests under `backend/tests/candidate/`; the optional advanced suite in `tests/advanced/` is separate and not required. |
| FP-SUB-1 | `Dockerfile`, GitHub main commit submission | — (delivery requirement) | — | Use the Docker guide for delivery verification. The permanent public commit on `main` and reproducible Docker build and startup are the final submission checks; CI rebuilds, seeds and runs the unit suite in the image. |

## Current Editor Protection Extension (2026-11-23)

Version protection covers **company profiles and applicant status**, alongside
candidate profiles and job edits. All four editors
have **Check for updates** beside Save. An unchanged server version keeps input;
a changed version requires confirmation before discarding a draft. A cancelled
check or failed read retains the draft and its old version. Checking one applicant
card cannot advance another card's draft version. No cross-tab communication
service is required.

Apply migration `8c3d0e5f7a21` after `7b2c9d4e6f10`, deploying database, backend and
frontend together. Company/status PATCH requests now require the loaded strict
positive version, with the same 409 conflict contract as profile/job updates.
New/create, booking and delete contracts are preserved. Existing records receive
version 1 without resetting data. See [INSTALL](INSTALL.md) and the
[editor workflow tests](frontend/tests/specialized/editor_update_checks.mjs).

Additional requirement-to-test mapping:

| Requirement | Additional actual tests |
|---|---|
| FP-EMP-1 company edit | `backend/tests/candidate/test_extended_versions.py::test_stale_company_or_status_tab_cannot_overwrite_newer_save[company]`; `test_extended_same_value_and_omission_revision_rules[company]`; company schema/no-op cases in `tests/unit/test_versions.py` |
| FP-EMP-3 applicant status | Application parameters of `test_extended_invalid_versions_cannot_write`, `test_extended_concurrent_edit_has_one_winner`, `test_extended_commit_failure_rolls_back_revision_and_content`; existing four-state and booking-preservation regressions |
| FP-CAN-1 / FP-EMP-1 / FP-EMP-2 / FP-EMP-3 editor drafts | `frontend/tests/specialized/editor_update_checks.mjs`: all four editors, both languages, three engines; failed reads, unchanged version, discard cancellation/confirmation, unadded skill query, independent cards and real double tabs |
| Migration consistency / FP-TEST-1 | `test_extended_migration_preserves_old_company_application_and_defaults`: isolated 7b → 8c upgrade, preserved rows, new SQL defaults, positive/non-null constraints and downgrade/re-upgrade; schema contracts in `tests/unit/test_versions.py` |

## Known Limitations

- Scores are computed per request in Python from normalised skill sets; there is
  no cached or denormalised score column, so the design targets the course-scale
  catalogue rather than very large job volumes.
- Optional AI explanations (FP-MATCH-2) are not implemented, so no paid
  credentials, external service or network access is required at any point.
- The optional advanced suite in `tests/advanced/` is supplementary evidence and
  is not part of the graded unit command; its tools (Z3, Schemathesis, coverage,
  mutmut) are deliberately absent from the Docker image.
- CI's dependency scan accepts one advisory, `PYSEC-2026-1845` (pytest 8.4.2),
  after an unreachability analysis recorded in the security scan notes.
- The historical suites under `tests/specialized/` are retained for reference and
  are not run by CI; their recorded browser and functional results predate later
  fixes.
- The formal proofs in the advanced report target abstract models and the
  specification formula, not the Python implementation itself.

## Document Index

- [Installation and test commands](INSTALL.md)
- [Product requirements](docs/REQUIREMENTS.md)
- [Living specification](SPEC.md)
- [Business unit tests](tests/unit/)
- [Component rendering unit tests](frontend/tests/rendering.unit.mjs)
- [Existing API/database regression](backend/tests/)
- [Specialized test suites and runners](tests/specialized/README.md)
- [Advanced testing and verification report](docs/advanced_testing/ADVANCED_REPORT.md)
- [Advanced test runner and fixtures](tests/advanced/README.md)
- [Four-editor version protection tests](frontend/tests/specialized/editor_update_checks.mjs)

Detailed historical test reports and internal defect inventories are kept with
local test artifacts, including raw logs, database directories and screenshots.
