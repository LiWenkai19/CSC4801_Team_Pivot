# Project Specification

## Product Scope

## Architecture

## Data Model and Relationships

## Authentication and Authorization

## API Routes or Server Actions

## User Interface and Workflows

## Matching Algorithm and Skill Storage

## Interview Scheduling and Booking Transaction

## Security Controls

## Optional AI Features and Data Flow

## Design Decisions and Limitations

## Candidate Integration (2026-11-05)

Candidate routes use the existing users/employer SQLModel tables and Alembic chain.
The matching implementation is `backend/app/employer/matching.py::match_score`,
called directly by both workflows. Skills are normalized using the existing
`normalize_skills` function and stored in CandidateSkill/JobSkill rows. Resume text
does not participate in matching. Candidate ties use lowercase job title, then ID.

Candidate profile updates, applications and bookings live in a schema/service/router
module. Booking locks the application before the slot; the existing two unique
constraints enforce one booking per application and slot. Responses use UTC,
and candidate pages display Asia/Shanghai. State changes preserve existing bookings.

The user-approved profile policy allows an employer to read a candidate's resume
only after that candidate applies to one of the employer's jobs; editing remains
candidate-only. This intentionally differs from the original course privacy text
and must be reconciled by the team before final submission. The employer UI is not
changed to consume this endpoint.

API contracts, test commands and known integration boundaries are documented in
[CANDIDATE_REBUILD.md](docs/CANDIDATE_REBUILD.md). No old candidate database or API
compatibility layer is included. Employer slot management remains outside this change.
