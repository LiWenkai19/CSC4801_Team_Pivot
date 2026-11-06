# Project Title

## Project Overview

## Team Members

## Architecture Summary

## Quick Start

## Demo Accounts

## Running Unit Tests

## Requirement–Test Mapping

Example rows only: replace the placeholder tests with your own assertions and
extend this table to cover every requirement ID. Include implementation file(s)
and named unit tests for each functional requirement. For non-functional
requirements, describe the relevant verification evidence; mark unimplemented
optional requirements as `N/A`. The `pass` examples do not verify behavior.

| Requirement ID | Behavior to verify | Implementation file(s) | Unit test(s) / verification evidence |
|---|---|---|---|
| FP-AUTH-1 | Registration and session lifecycle | To be filled by the team | `tests/unit/test_auth.py::test_fp_auth_1_registration_and_session_lifecycle` (placeholder) |
| FP-EMP-1 | Employer can view and edit company profile (name + description) | `backend/app/employer/router.py`, `backend/app/employer/service.py`, `backend/app/employer/schema.py` | `backend/tests/employer/test_company.py::test_fp_emp_1_view_and_edit_company_profile`; `::test_fp_emp_1_company_profile_validation`; `::test_fp_emp_1_missing_profile_returns_404`; `::test_fp_emp_1_role_and_auth_boundaries` |
| FP-EMP-2 | Job posting CRUD, ownership 403, delete conflict 409 when dependents exist | `backend/app/employer/service.py` (`create_job`/`list_my_jobs`/`get_my_job`/`update_job`/`delete_job`), `backend/app/employer/model.py` | `backend/tests/employer/test_jobs.py::test_fp_emp_2_create_job_fields_and_skills`; `::test_fp_emp_2_create_job_validation`; `::test_fp_emp_2_list_and_get_only_own_active_jobs`; `::test_fp_emp_2_update_job_replaces_skills_and_updated_at`; `::test_fp_emp_2_other_employer_cannot_edit_or_delete`; `::test_fp_emp_2_soft_delete_without_dependents`; `::test_fp_emp_2_delete_conflict_with_application`; `::test_fp_emp_2_delete_conflict_with_interview_slot`; `::test_fp_sec_2_job_title_sql_metacharacters_are_bound` |
| FP-EMP-3 | Applicant list sorted by match score; status limited to four values; only owning employer can change | `backend/app/employer/service.py` (`list_job_applicants`/`change_application_status`), `backend/app/employer/schema.py` | `backend/tests/employer/test_applicants.py::test_fp_emp_3_applicant_rows_contain_required_fields`; `::test_fp_emp_3_applicants_sorted_by_match_score_desc`; `::test_fp_emp_3_applicant_row_shows_booking`; `::test_fp_emp_3_set_status_all_four_values`; `::test_fp_emp_3_status_change_keeps_booking`; `::test_fp_emp_3_other_employer_and_candidate_cannot_change`; `::test_fp_emp_3_missing_application_returns_404`; `::test_fp_emp_3_applicant_list_owner_only` |
| FP-MATCH-1 | Skill-overlap examples and tie-breaking | `backend/app/employer/matching.py` (`match_score`), `backend/app/employer/service.py` (`list_job_applicants` sort key) | `backend/tests/employer/test_matching.py::test_fp_match_1_skill_overlap_examples`; `::test_fp_match_1_normalization_applies_to_both_sides`; `::test_fp_match_1_score_is_floor_and_bounded`; `::test_fp_match_1_employer_applicant_tie_breakers` (employer-side rule; candidate-side title tie-break lands with the candidate module); seed examples in `backend/scripts/seed_demo.py` |
| FP-SCHED-3 | Booking conflict outcome | To be filled by the team | `tests/unit/test_scheduling.py::test_fp_sched_3_conflict_contract` (placeholder) |

## Document Index

## Known Limitations

## Candidate Rebuild (2026-11-05)

Candidate workflow is integrated into the existing application and frontend.
See [candidate architecture, API, commands and verification boundaries](docs/CANDIDATE_REBUILD.md).
The employer and candidate views call the same real matching implementation.

| Requirement ID | Implementation | Named verification |
|---|---|---|
| FP-CAN-1 | `backend/app/candidate/service.py`; candidate profile page and shared skill picker | `backend/tests/candidate/test_profiles.py::test_profile_patch_persists_and_preserves_omitted_fields`; `::test_profile_permission_matrix`; `::test_profile_failed_commit_rolls_back_text_and_skills` |
| FP-CAN-2 / FP-MATCH-1 (candidate) | `list_jobs`, shared employer `match_score` | `backend/tests/candidate/test_jobs.py::test_recommendations_share_scores_and_title_ties`; `::test_recommendation_queries_do_not_grow_per_job` |
| FP-CAN-3 | candidate application services | `backend/tests/candidate/test_jobs.py::test_apply_once_in_every_status`; `::test_application_isolation_and_historical_records`; `::test_concurrent_duplicate_applications_have_one_winner` |
| FP-SCHED-2 | candidate booking services, shared models | `backend/tests/candidate/test_booking.py::test_booking_visible_to_both_roles_and_survives_status_change`; `::test_booking_invalid_slot_rolls_back`; `::test_booking_rejects_foreign_application_and_non_interviewing` |
| FP-SCHED-3 | PostgreSQL transactions and existing unique constraints | `backend/tests/candidate/test_booking.py::test_real_postgres_two_candidates_compete_for_one_slot`; `::test_same_application_concurrent_booking_has_one_winner` |
| FP-SEC-1/2/3 | candidate authorization, ORM queries, escaped React text | profile permission matrix, candidate endpoint auth matrix, browser text/XSS checks in `frontend/tests/candidate.browser.mjs` |

Current supported backend regression: **116 passed** on isolated PostgreSQL.
Full collection still fails on the pre-existing `tests/users/test_schema.py` import;
the documented regression command explicitly excludes it. The earlier placeholder
rows above remain team-owned roadmap entries; this table records candidate coverage.
