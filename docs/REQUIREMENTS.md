# Final Project Product Requirements

This is the normative specification for the project. Every team builds the recruiting and candidate matching system below.

> **MUST** and **MUST NOT** requirements are graded. **SHOULD** items are recommended but not graded unless they are required by another **MUST**. **MAY** items are optional.

## 1. Product boundary

### FP-ARCH-1: Full-stack boundary

The submission **MUST** be a locally runnable full-stack application with:


- **a browser-based user interface;**
- **a backend server or API enforcing business rules and authorization; and**
- **a persistent relational database.**

The application **MUST** work from a clean checkout by following `INSTALL.md`. Using a hosted service is optional and **MUST NOT** be necessary for grading. If the application uses an external LLM, the core system and automated tests **MUST** still run without paid credentials, using a deterministic fake or a non-LLM fallback.

## 2. Roles and authentication

### FP-AUTH-1: Accounts

The system **MUST** support exactly two application roles: `Candidate` and `Employer`. A user **MUST** be able to register, log in, and log out. Email or username identifiers **MUST** be unique.

### FP-AUTH-2: Credential storage

Passwords **MUST** be stored with an established password-hashing function. Plain text, reversible encryption, and a general-purpose fast hash such as unsalted SHA-256 do not satisfy this requirement. Authentication secrets **MUST NOT** be returned by an API or rendered in the UI.

### FP-AUTH-3: Server-side authorization

Every protected operation **MUST** enforce role and ownership on the server; hiding a button in the UI is not sufficient. The observable response contract is:

- unauthenticated request: `401 Unauthorized` or redirect to login;
- authenticated user with the wrong role or owner: `403 Forbidden`; and
- missing object that the caller would otherwise be allowed to access: `404 Not Found`.

For non-HTTP frameworks, the UI and service layer **MUST** provide equivalent, clearly distinguishable outcomes.

## 3. Candidate workflow

### FP-CAN-1: Candidate profile and resume

A candidate **MUST** be able to view and edit only their own profile, including a display name and a list of technical skills. Skills **MUST** be saved and available to the matching function.

A candidate **MUST** be able to enter a raw-text resume. The application **MUST** persist the text and allow the owner to view and replace it. PDF upload and extraction are optional. Resume contents are private: only the owning candidate may read or modify them. Any other candidate or employer **MUST** receive `403` through a direct URL/API request.

### FP-CAN-2: Recommendations

A candidate dashboard **MUST** list all current (not deleted) jobs with a visible match score and sort them from highest to lowest score. The dashboard **MUST** include the job title, employer/company, required skills, and a way to view the description.

### FP-CAN-3: Applications

A candidate **MUST** be able to apply to a job once. A new application **MUST** have status `Pending`. A duplicate application by the same candidate to the same job **MUST** be rejected without creating another row. A candidate **MUST** be able to view the job, employer, current status, and interview booking (if any) for each of their own applications.

A candidate **MUST NOT** be able to view another candidate's applications or change an application status.

## 4. Employer workflow

### FP-EMP-1: Company profile

An employer **MUST** be able to view and edit a company profile containing at least a company name and description.

### FP-EMP-2: Job postings

An employer **MUST** be able to create, view, edit, and delete their own job postings. Each posting **MUST** contain a non-empty title and description plus a required-skills list; the list may be empty. An employer **MUST** receive `403` when attempting to edit, delete, or manage applicants for another employer's posting.

A job with no applications or interview slots **MUST** be deletable. If either kind of dependent record exists, deletion **MUST** fail with `409 Conflict` (or a clearly documented equivalent) and leave the job and dependent records unchanged.

### FP-EMP-3: Applicant management

For each owned job, an employer **MUST** be able to view its applicants sorted by match score from highest to lowest. Each row **MUST** show candidate identity, skills, match score, application status, and interview booking (if any).

The employer who owns the job **MUST** be able to set an application to one of exactly these statuses: `Pending`, `Interviewing`, `Rejected`, or `Accepted`. Other employers and candidates **MUST NOT** be able to change the status.

## 5. Matching contract

### FP-MATCH-1: Score definition

The required match score is a deterministic skill-overlap score. Resume text is not an input. Normalize candidate and required skills by trimming surrounding whitespace, converting to lowercase, removing empty values, and removing duplicates. Let `C` and `R` be the resulting candidate-skill and required-skill sets:

```text
score = 100                                      when |R| = 0
score = floor(100 * |C intersection R| / |R|)   otherwise
```

The result **MUST** be an integer from 0 through 100. Candidate and employer views **MUST** call the same implementation. Sort by descending score. Break candidate dashboard ties by case-insensitive job title and then stable job ID; break employer applicant ties by case-insensitive candidate display name and then stable candidate ID.

The seed data and unit tests **MUST** include these examples:

| Candidate skills | Required skills | Expected score |
|---|---|---:|
| `Python, SQL` | `Python, SQL` | 100 |
| `Python` | `Python, SQL` | 50 |
| `Rust` | `Python, SQL` | 0 |
| any skills | empty list | 100 |

`SPEC.md` **MUST** identify the matching implementation and describe how skills are stored. It may cite this formula rather than inventing another scoring oracle.

### FP-MATCH-2: Optional AI enhancement

Teams **MAY** add an LLM-generated explanation or secondary recommendation, but it earns no substitute credit and **MUST NOT** alter the required score or ordering. If user-controlled text is sent to an LLM, it **MUST** be treated as untrusted data, **MUST NOT** reveal prompts or secrets, and the data flow **MUST** be documented in `SPEC.md`. An optional AI enhancement is part of the peer-audit scope.

## 6. Applications and interview scheduling

### FP-SCHED-1: Availability

An employer **MUST** be able to create and delete future, 30-minute availability slots. Each slot **MUST** have one owner and an exact start and end time with an unambiguous, documented timezone. The system **MUST** reject invalid durations, end-before-start values, and deletion of a booked slot. Booked slots **MUST NOT** be shown as available.

### FP-SCHED-2: Booking eligibility

The system **MUST** allow a candidate to book a slot if and only if all of the following are true:

- the candidate owns the application;
- the slot belongs to the employer for the candidate's application;
- the application status is `Interviewing`;
- the slot is in the future and is not already booked; and
- the application has no existing booking.

A successful booking **MUST** link the candidate's application to the slot and be visible to both that candidate and the owning employer. Ineligible bookings **MUST** fail without partially changing either record. If a booked application later leaves `Interviewing`, its booking **MUST** remain associated with the application and the slot **MUST** remain unavailable.

### FP-SCHED-3: Atomic concurrency

Booking **MUST** be atomic at the database layer. Use a transaction plus row locking, optimistic concurrency, a uniqueness constraint, or an equivalent database mechanism. An in-process check alone is insufficient.

When two eligible candidates concurrently attempt to book the same slot, exactly one attempt **MUST** succeed, the other **MUST** fail with conflict status (HTTP `409` or a clearly documented equivalent) and the message `Slot already booked`, and the database **MUST** contain exactly one booking afterward. Students **MUST** write unit tests for the booking conflict-handling logic. Database atomicity is verified through implementation review and the running system; students are not required to provide a synchronized multi-client test.

## 7. Security requirements

### FP-SEC-1: Object access

Changing an object ID in a request **MUST NOT** bypass FP-AUTH-3. Unit tests of the authorization logic **MUST** cover these representative boundaries:

1. one candidate cannot read or modify another candidate's resume or application;
2. one employer cannot modify another employer's job or read its applicant list;
3. a candidate cannot book a slot using another candidate's application.

Unit tests for each functional requirement are additionally required by FP-TEST-1; code review and demonstration supplement that evidence.

### FP-SEC-2: SQL injection

All database access involving user-controlled values **MUST** use parameterized queries, a correctly used ORM, or an equivalent safe API. Concatenating raw user input into a query is prohibited. At least one unit test **MUST** pass SQL metacharacters to the query-building or data-access logic and verify that the input remains a bound value rather than executable SQL. Code review and the running system verify the use of safe database APIs.

### FP-SEC-3: Cross-site scripting

User-controlled profile, resume, company, job, and search text **MUST** be escaped when rendered as HTML. If the design intentionally supports formatted HTML, it **MUST** use an allow-list sanitizer. At least one unit test **MUST** pass `<script>alert(1)</script>` to the rendering or sanitization logic and verify that it is not emitted as executable markup.

### FP-SEC-4: Secrets and test isolation

The repository **MUST** contain no real secrets or personal data. Unit tests **MUST** use isolated fixtures or test doubles and **MUST NOT** call real third-party services. Any test that uses a database **MUST** use an isolated test database. `.env.example` **MUST** contain placeholders only.

## 8. Spec-driven and AI-assisted engineering

### FP-PROC-1: Living specification

`SPEC.md` **MUST** describe the architecture, data model and relationships, authentication/authorization design, API routes or server actions, major UI screens, matching contract, booking transaction, and security controls. The requirement–test mapping **MUST** be written in `README.md` as specified in FP-DOC-2, rather than in `SPEC.md`.

The specification **MUST** match the graded commit. A large generated document that does not match the submitted system receives no credit for accuracy.

Every team member **MUST** be able to explain and safely modify the submitted code, regardless of which portions were AI-generated.

## 9. Documentation, data, tests, and CI

### FP-DOC-1: Installation

`INSTALL.md` **MUST** list prerequisite versions, exact install commands, environment variables, database setup/migrations, seed command, run command, test command, `Dockerfile` build and start commands, and troubleshooting for any non-obvious dependency. A grader with a clean checkout who builds the repository's `Dockerfile` **MUST** not need an undocumented command or secret.

### FP-DOC-2: Repository README

`README.md` **MUST** give a short product overview, architecture summary, quick-start link to `INSTALL.md`, demo account credentials for seeded non-production users, unit-test command, document index, and known limitations. It **MUST** include a requirement–test mapping table covering every requirement ID in this document, with implementation file(s) and named student-written unit tests for each functional requirement. Non-functional requirements may cite the appropriate verification evidence. An optional enhancement that is not implemented may be marked `N/A`.

### FP-DOC-3: Deterministic demo data

One documented command **MUST** reset and seed a local database. Seed data **MUST** include at least:

- two candidates and two employers;
- two jobs with required skills;
- the four matching examples required by FP-MATCH-1;
- applications covering all four statuses; and
- two `Interviewing` candidates eligible to race for the same available slot.

Seed credentials **MUST** be clearly marked as local/demo credentials.

### FP-TEST-1: Automated verification

Students **MUST** write their own unit tests for every functional requirement: FP-AUTH-1 through FP-AUTH-3, FP-CAN-1 through FP-CAN-3, FP-EMP-1 through FP-EMP-3, FP-MATCH-1, and FP-SCHED-1 through FP-SCHED-3 (plus FP-MATCH-2 if implemented). Tests **MUST** exercise the team's actual business logic, cover successful behavior and applicable validation, permission, and conflict cases, and assert observable outcomes. Each functional requirement **MUST** map to named unit tests in the `README.md` table; copied example tests or `pass` placeholders do not satisfy this obligation. Students remain responsible for writing, reviewing, and explaining their tests when using AI assistance.

Only unit tests are required from students. One documented command **MUST** run the complete unit-test suite non-interactively and return a nonzero exit status on failure. The unit tests **MUST** cover:

- the unauthenticated, forbidden, and missing-object outcomes in FP-AUTH-3;
- the four skill-overlap examples and both tie-breaking rules;
- the representative authorization boundaries in FP-SEC-1;
- the SQL-injection case in FP-SEC-2;
- the XSS case in FP-SEC-3; and
- the booking conflict-handling logic in FP-SCHED-3.

Demonstrations **MUST NOT** replace the required unit tests. Product requirements, including database atomicity and server-side security, remain mandatory and may also be checked through code review and the running system. Unit tests with test doubles do not by themselves prove database concurrency behavior.

## 10. Submission protocol

### FP-SUB-1: Submission protocol

Each team **MUST** submit a permanent GitHub commit URL on `main`, and the repository at that commit **MUST** build and run entirely from its own `Dockerfile`. Both conditions **MUST** hold at the same graded commit. Failing either fails the submission-format check below.

#### Git submission

The team **MUST** submit one permanent GitHub commit URL through the course-site submission link, using the form `https://github.com/<owner>/<repository>/commit/<40-character-sha>`. This URL identifies both the repository and the exact graded commit. A moving branch URL such as `/tree/main` **MUST NOT** be used. The linked commit **MUST** be pushed to the repository's `main` branch by the deadline, and the repository **MUST** be public so the instructor and other teams can access it.


#### Dockerfile

The repository **MUST** contain a `Dockerfile` that builds the complete runnable environment from the graded commit, so that graders and auditors can rebuild it after every commit or bug fix. There is **no image tar to upload** — see [`DOCKER.md`](DOCKER.md). The build **MUST**:

- succeed from a clean checkout of the graded commit with no undocumented command or secret;
- include every application and standard dependency image (databases, caches, message brokers) needed to run and test the environment;
- work **without pulling or downloading any undocumented container image** at run time; and
- contain no real credential, API key, personal data, or production database.

The `Dockerfile`, entrypoint scripts, migrations, and seed scripts **MUST** remain in the Git repository. Docker images do not preserve database volumes, so the documented seed command **MUST** initialize the grading data after startup. The image does not replace source submission, CI, migrations, or deterministic seed data.

Before the deadline, the team **SHOULD** verify the build on a clean machine:

1. clone the repository and check out the graded commit;
2. build the environment (`docker build`);
3. start the complete environment using the documented command;
4. run migrations and deterministic seed data;
5. run the required automated test command; and
6. open the browser UI and complete a documented smoke test.

#### Submission-format check and second submission

The first submission passes the format check only if the permanent commit URL is present and resolves to an accessible graded commit on a public repository, the repository's `Dockerfile` builds from that commit, and the documented start/seed/test flow works without downloading any undocumented container image.

- If the first submission passes this check, there is no submission-format deduction.
- If the first submission fails this check, the team will make one corrective second submission by the instructor's published deadline. If the second submission passes, **5 points are deducted from the 50-point preliminary total before ranking**. The reduced preliminary total is used to determine the team's rank.
- If the second submission is not made by the deadline or still fails the check, **the final project score is 0**, and the team is not included in the normal rank conversion.
