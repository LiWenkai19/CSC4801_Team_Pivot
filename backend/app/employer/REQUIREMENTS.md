# 雇主模块需求摘录

摘自 [docs/REQUIREMENTS.md](../../../../docs/REQUIREMENTS.md)，供本模块二次复核。分数公式引用原文，不另造打分口径。

## FP-EMP-1: Company profile

An employer **MUST** be able to view and edit a company profile containing at least a company name and description.

## FP-EMP-2: Job postings

An employer **MUST** be able to create, view, edit, and delete their own job postings. Each posting **MUST** contain a non-empty title and description plus a required-skills list; the list may be empty. An employer **MUST** receive `403` when attempting to edit, delete, or manage applicants for another employer's posting.

A job with no applications or interview slots **MUST** be deletable. If either kind of dependent record exists, deletion **MUST** fail with `409 Conflict` (or a clearly documented equivalent) and leave the job and dependent records unchanged.

## FP-EMP-3: Applicant management

For each owned job, an employer **MUST** be able to view its applicants sorted by match score from highest to lowest. Each row **MUST** show candidate identity, skills, match score, application status, and interview booking (if any).

The employer who owns the job **MUST** be able to set an application to one of exactly these statuses: `Pending`, `Interviewing`, `Rejected`, or `Accepted`. Other employers and candidates **MUST NOT** be able to change the status.

## FP-MATCH-1: Score definition

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

## 涉及的安全条款

- FP-SEC-1：改对象 ID 不得绕过 FP-AUTH-3，越权边界必须有单测。
- FP-SEC-2：SQL 元字符必须作为绑定值处理，不得拼接执行。

## 实现归属（本分支）

| 条款 | 实现位置 |
| --- | --- |
| FP-EMP-1 | `GET/PATCH /employer/company`（[service.py](service.py) `get_my_company`/`update_my_company`，公司资料复用 users 模块 `EmployerProfile`） |
| FP-EMP-2 | `/employer/jobs` CRUD（[service.py](service.py) `create_job`/`list_my_jobs`/`get_my_job`/`update_job`/`delete_job`） |
| FP-EMP-3 | `GET /employer/jobs/{job_id}/applications`、`PATCH /employer/applications/{id}/status`（[service.py](service.py) `list_job_applicants`/`change_application_status`） |
| FP-MATCH-1 | [matching.py](matching.py) `match_score`；平级规则在 `list_job_applicants` 的排序键 |
