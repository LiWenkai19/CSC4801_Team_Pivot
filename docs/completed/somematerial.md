# Project Specification

## Product Scope

The recruiting platform supports Candidate and Employer accounts. Candidates
maintain a profile, browse ranked jobs, apply, track application status, and
book interviews. Employers manage their postings and applicants in the same
application. This document describes the Candidate Flow and its shared contracts.

## Architecture

The React and TypeScript UI uses the shared client in `frontend/src/api/common_api.ts`.
In local development, Vite forwards same-origin `/api/` requests to FastAPI. The
application registers the users, candidate, and employer routers in
`backend/app/main.py`. Within `backend/app/candidate/`, `schema.py` defines request
and response types, `router.py` handles HTTP and dependencies, and `service.py`
implements authorization, queries, scoring integration, and transactions.
Both workflows use PostgreSQL through SQLModel and a shared Alembic migration chain.

## Data Model and Relationships

| Relationship | Purpose |
| --- | --- |
| `User` → `UserSession` | One user can have multiple expiring sessions. Each stores a unique token hash and a session-specific CSRF token. |
| `User` → `CandidateProfile` or `EmployerProfile` | The role-specific profile uses the account ID as its primary key. A candidate profile holds the display name and raw resume text. |
| `CandidateProfile` → `CandidateSkill`; `Job` → `JobSkill` | Skills are stored as separate rows keyed by parent ID and normalized name. The employer owns each job. |
| `CandidateProfile` → `Application` ← `Job` | An application stores its status and links one candidate to one job. The candidate/job pair is unique. |
| `EmployerProfile` → `InterviewSlot` | A slot belongs to one employer, can reference a job, and stores its start and end times. Candidate eligibility checks the employer ID. |
| `Application` → `Booking` ← `InterviewSlot` | Separate unique constraints on the application and slot allow at most one booking per application and one per slot. |

The shared model definitions are in `backend/app/users/model.py` and
`backend/app/employer/model.py`.

## Authentication and Authorization

Registration at `POST /users/register` creates an account with a unique email
and one of the two supported roles. Registration and `POST /users/login`
each create a server-side session and return public account details. By
default, the browser receives an HttpOnly `session` cookie with a
random session token and a readable `csrf_token` cookie, both with
`SameSite=Lax`. PostgreSQL stores the token's SHA-256 hash in `token_hash`.
The browser sends the cookies on same-origin requests, and the shared client
echoes the CSRF token in `X-CSRF-Token` on protected writes. `GET /users/me`
returns the account and profile-completion state. `POST /users/logout` revokes
the current session and clears both cookies.

The server checks session validity, role, and resource ownership. A missing,
invalid, expired, or revoked session returns `401`. A valid session with a
missing or invalid CSRF token on a protected write returns `403`. A caller
with the wrong role or ownership also receives `403`. Missing objects return
`404` where applicable. Validation errors return `422` and business conflicts
return `409`. Candidate requests derive account ownership from the authenticated
user. Candidates cannot change an application status.

## API Routes or Server Actions

Paths below are FastAPI paths. The browser reaches them through the `/api` prefix.
All routes in the table require a valid session.

| Method and path | Access | CSRF | Result |
| --- | --- | --- | --- |
| `POST /users/candidate/profile` | Candidate | Yes | Creates the caller's profile and skills (`201`). An existing profile returns `409`. |
| `GET /candidate/profile` | Candidate | — | Returns the caller's profile. |
| `PATCH /candidate/profile` | Candidate | Yes | Updates the caller's display name, raw resume text, and/or skills. |
| `GET /candidate/profiles/{candidate_id}` | Owner or employer with an application from that candidate to one of its jobs | — | Returns the candidate profile, including its resume. See the privacy limitation below. |
| `GET /candidate/jobs` | Candidate | — | Lists active jobs with company, required skills, description, score, and the caller's applied flag. |
| `GET /candidate/jobs/{job_id}` | Candidate | — | Returns the active job's details and personalized score. |
| `POST /candidate/jobs/{job_id}/applications` | Candidate with a profile | Yes | Creates a `Pending` application (`201`). A duplicate returns `409`. Omit the body or send `{}`. |
| `GET /candidate/applications` | Candidate | — | Lists the caller's applications by creation time descending, then application ID ascending. |
| `GET /candidate/applications/{application_id}` | Owning candidate | — | Returns the application with job title, company, status, and booking if present. |
| `GET /candidate/applications/{application_id}/slots` | Owning candidate | — | Lists available slots for an eligible application, ordered by start time then ID. |
| `POST /candidate/applications/{application_id}/booking` | Owning candidate | Yes | Takes a `slot_id` and creates a booking (`201`) if the checks below pass. |

Profile edits preserve omitted fields. An empty resume string or skills list
clears that field. Explicit null, extra fields, and a blank display name are
invalid. Successful edits save the text and skill changes in one transaction.

Job recommendations and details also require a completed candidate profile
and return `404` if that profile is missing. A deleted job is unavailable in
recommendations, job details, and new applications. The application list
still includes existing records for historical jobs.

## User Interface and Workflows

1. A new candidate signs up and completes the profile at `/candidate/details`.
   Returning candidates can edit their display name, plain-text resume, and
   skill tags at `/candidate/profile`.
2. `/candidate/jobs` shows the ranked recommendations with match scores. The
   job detail at `/candidate/jobs/:jobId` shows the description and supports
   applying. The list and detail reflect whether the candidate already applied.
3. `/candidate/applications` shows the candidate's own applications and
   their status and existing booking. An eligible candidate can view available
   times and reserve one from this screen.

## Matching Algorithm and Skill Storage

Both workflows call `match_score` in `backend/app/employer/matching.py`. Skills
are trimmed, lowercased, and deduplicated after empty strings are removed. Let
`C` be the candidate's skill set and `R` the required skill set. The integer
score is `100` if `R` is empty and `floor(100 × |C ∩ R| / |R|)` otherwise.
The candidate list sorts by decreasing score, lowercased job title, and stable
job ID. The employer applicant list uses decreasing score, lowercased
candidate display name, and stable candidate ID. Scoring uses the
`CandidateSkill` and `JobSkill` rows. Resume text is excluded.

## Application Creation

The service verifies the candidate's profile, locks the active job row,
checks for an existing application, and inserts a new application with the
model's `Pending` default. The job lock coordinates with job deletion. A
unique constraint on `(candidate_id, job_id)` enforces one application per
candidate and job.

## Interview Scheduling and Booking Transaction

Only the owner of an unbooked `Interviewing` application can reserve a slot.
The slot must belong to the employer for that application, start in the
future, last exactly 30 minutes, and be unbooked.

The PostgreSQL transaction locks the application row first and checks its
ownership, status, and existing booking. It then locks the slot row and
rechecks slot eligibility before adding a booking. Unique constraints on
`booking.application_id` and `booking.slot_id` back up the row locks.
Validation failures and database errors before commit roll back the
transaction. If two eligible candidates compete for the same available
slot, exactly one can reserve it and the other receives `409` with
`Slot already booked`. The candidate and owning employer read the same
booking record. A later application status change preserves the booking and
keeps the slot unavailable. Candidate API timestamps use UTC. The candidate
screen displays interview times in `Asia/Shanghai` (UTC+8).

## Security Controls

The account service hashes passwords with Argon2. Public account responses
contain neither the password hash nor session credentials. The backend
checks role and ownership on protected operations and uses bound ORM
expressions for candidate queries. Candidate pages render resume, company,
and job text through React text rendering.

## Optional AI Features and Data Flow

Candidate scoring uses the deterministic skill-overlap implementation. It
does not send profile or resume data to an external LLM.

## Design Decisions and Limitations

- **Resume access differs from FP-CAN-1.** The current profile-read endpoint
  also allows an employer to read the resume if the candidate has an
  application to a job owned by that employer, regardless of application
  status. The owner alone can edit it. The course requires all employers to
  receive `403` for direct resume access.
- The current database engine enables SQL parameter logging. Candidate profile
  writes can put resume text in development logs.
- Profile updates commit the text and skill changes together. Concurrent
  updates that replace the same candidate's skill set lack a profile-row lock
  and can combine skills from both requests.
- The ORM sets the initial application status to `Pending`. The Alembic
  migration creates a non-null status column without a database default, so
  direct inserts must supply a status.
- Employer-side slot creation and deletion are pending.

See [installation and verification](INSTALL.md) for reproduction steps and
[the Candidate rebuild record](docs/CANDIDATE_REBUILD.md) for historical context.
