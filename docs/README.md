# CSC4801 Final Project: Recruiting and Candidate Matching

Teams will build **a full-stack recruiting platform** with AI coding agents and a spec-driven workflow. The product is fixed: a two-sided marketplace in which candidates find and apply to jobs, employers manage applicants, and candidates book interview slots safely under concurrent use.

The framework, language, database, hosting model, and optional enhancements are your team's choice. The required matching baseline and other observable behavior are fixed in [`REQUIREMENTS.md`](REQUIREMENTS.md); requirements are mandatory unless explicitly marked optional.

## Read these documents

| Document | Purpose |
|---|---|
| [`REQUIREMENTS.md`](REQUIREMENTS.md) | Normative product requirements and acceptance criteria |
| [`PEER_REVIEW.md`](PEER_REVIEW.md) | Required cross-team audit procedure, valid-finding standard, and safety rules |
| [`DOCKER.md`](DOCKER.md) | How to build and run the environment from the repository's `Dockerfile` |
| [`templates/github/ISSUE_TEMPLATE/audit_bug_report.yml`](templates/github/ISSUE_TEMPLATE/audit_bug_report.yml) | GitHub Issue Form for audit findings; every team enables it |
| [`templates/github/labels.yml`](templates/github/labels.yml) | Audit labels every team imports into its repository |


## Grading

The final project is **50% of the overall course grade**. A preliminary 50-point team total is used to rank the expected ten teams:

| Component | Preliminary points |
|---|---:|
| Requirements fulfillment (100 raw points scaled to 10) | 10 |
| Cross-team audit and repair | 30 |
| Presentation | 10 |
| **Total used for ranking** | **50** |


### 1. Requirements fulfillment

Students **MUST** write their own unit tests for every functional requirement in `REQUIREMENTS.md` and map them in `README.md`. Only unit tests are required, including the security and booking conflict logic specified in FP-TEST-1. Grading is based on the number of requirements fulfilled. Students are responsible for ensuring that their tests are correct and complete.

### 2. Cross-team audit and repair

Every team starts at **0 audit points**. Valid findings and evidence-backed repairs add to the audit points. Every report and audit action must follow [`PEER_REVIEW.md`](PEER_REVIEW.md). The [`leadboard`](https://sra-research.github.io/CSC4801/project.html) shows the real-time audit points for each team. The final grade is based on the team ranking, not the absolute number of audit points.

#### Finding points

| Outcome | Points |
|---|---:|
| Security bug | +2 |
| Functional or performance bug | +1 |
| Environmental issue (e.g., the repository's `Dockerfile` fails to build or run) | +0.5 |
| Invalid bug report | -0.5 |
| Duplicate bug report | 0 |

One root cause counts as one finding even if it produces several symptoms.

#### Repair points

| Outcome | Points |
|---|---:|
| Valid fix record, permanent fix commit URL, and regression evidence submitted by the repair deadline | +2 |
| Incorrect fix or regression-test claim | -0.5 |


#### Repository availability

The repository must remain publicly readable during the published audit window. Deduct `0.2` audit points per unavailable audit-window hour, capped at 10 points. Instructor-confirmed GitHub-wide outages do not count.


### 3. Presentation
Each team will present its system to the class and answer questions about its implementation. The presentation is graded on clarity, completeness, and correctness of the system's implementation, as well as the team's ability to answer questions about its design and implementation. The presentation is also an opportunity to demonstrate any optional enhancements implemented by the team.

## Milestones

| Week | Required milestone |
|---|---|
| 1-2 | Form a team of three and create a private repository. |
| 3 | Final project and requirements announced. |
| 3-10 | Build the system, tests, documentation, and seed data. |
| 11 | Feature freeze. tests must pass on the `main` branch. |
| 12 | Make the repository public before the audit window. Other teams build the environment from your repository's `Dockerfile` at the latest commit on `main` and conduct peer audits. After feature freeze, make only bug fixes and documentation corrections on `main`. |
| End of Week 12 | Complete repairs and documentation. Submit the permanent URL for the exact graded commit on `main`; its repository `Dockerfile` must build the complete environment. |
| 13-14 | Present the running system and answer implementation questions. |

Exact calendar dates are published on the course site.

## Audit window

The audit window is **08:00-20:00, Monday-Friday of Week 12** in the course timezone. The repository must remain publicly readable throughout that window. Late or interrupted access will result in a penalty.

All auditing is performed against another team's source at the latest commit on its `main` branch, built from the repository's `Dockerfile`, on the auditor's own machine. This is code review and local testing, not penetration testing of a live service. Every auditor must follow [`PEER_REVIEW.md`](PEER_REVIEW.md).


## Starter repository

The [CSC4801_TeamA starter repository](https://github.com/sra-research/CSC4801_TeamA) provides starter headings, dummy unit-test functions, and an example requirement–test mapping table. Students should use this template, fill in the documents, implementation, and real unit tests before submission. 

A demo [branch](https://github.com/sra-research/CSC4801_TeamA/tree/codex/add-project-starter-scaffold) provide a toy implementation, bug report and fix example.

## Technology and AI resources

MiMo API subscriptions are provided, and Claude Code is recommended. Other coding agents are allowed, but students are responsible for any associated costs. Use of AI does not reduce responsibility for understanding, reviewing, testing, and securing the submitted code.
