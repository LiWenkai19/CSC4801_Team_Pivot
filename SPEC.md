# Project Specification

## Product Scope

## Architecture

## Data Model and Relationships

## Authentication and Authorization

## API Routes or Server Actions

## User Interface and Workflows

## Matching Algorithm and Skill Storage

## Interview Scheduling and Booking Transaction

### 雇主时段管理

[interview 模块](backend/app/interview/PLAN.md)提供三个雇主接口。在 `backend/app/interview/` 下，`router.py` 处理 HTTP，`schema.py` 校验请求及定义响应，`service.py` 执行业务与事务。路由由 `backend/app/main.py` 注册。

| 接口 | 请求与成功响应 | 业务错误 |
| --- | --- | --- |
| `POST /employer/interview-slots` | 请求体只含 `starts_at`，服务端加 30 分钟得出 `ends_at`。创建成功返回 `201` 和 `{id, starts_at, ends_at}`。 | 雇主资料缺失返回 `404`。与本人已有时段重叠返回 `409`。额外字段或时间非法返回 `422`。 |
| `GET /employer/interview-slots` | 返回本雇主尚未开始的所有时段，含 `is_booked`，按 `starts_at`、`id` 排序。返回 `200`，无时段时为 `[]`。 | 适用统一认证和角色校验。 |
| `DELETE /employer/interview-slots/{slot_id}` | 用 UUID 标识时段，删除本雇主的未来空闲时段，成功返回 `204`。 | UUID 格式非法返回 `422`，时段不存在返回 `404`，属于其他雇主返回 `403`，已预约或已开始返回 `409`。 |

- **权限** 使用 `require_employer` 核验服务端会话。未登录返回 `401`，候选人访问返回 `403`。创建和删除还需通过 `X-CSRF-Token` 校验。列表限定 `employer_id = current_user.id`，创建也从当前登录用户取得 `employer_id`。
- **时间** `starts_at` 为带 `Z` 或 UTC 偏移量的 ISO 8601 字符串（如 `2026-12-01T09:00:00+08:00`）。服务端归一为 UTC，确认开始时间晚于当前时间后加 30 分钟。数据库使用 `timestamptz`，接口以 UTC 返回时间，新管理页面按 `Asia/Shanghai` 标注和展示。
- **重叠** 按同一雇主判断，已预约时段也占用时间。两个时段首尾相接时可以创建。
- **数据** 复用 `interview_slot` 与 `booking`。新时段由雇主跨职位共享，现有可空 `job_id` 在创建时留空。时段是否已被预约以 `booking.slot_id` 为准。

### 候选人资格与可见性

复用现有候选人时段列表与预约接口。只有申请本人能通过处于 `Interviewing` 且尚未预约的申请，查看和预约该职位所属雇主未来、空闲的 30 分钟时段。雇主时段管理页显示已预约时段并禁用删除。预约结果通过候选人申请和雇主本人职位的申请人列表分别展示。

列表查询以查询时的数据库状态为准。雇主用 `EXISTS` 获取预约状态，候选人的可预约列表排除已有预约的时段。删除与预约在写入事务中重新检查条件。

### 事务与行锁

1. **创建时段** 事务先锁定雇主资料行，再查询重叠并插入。按 `READ COMMITTED`，等待锁的同一雇主请求会看到前一请求提交的时段。
2. **删除时段** 在 PostgreSQL 事务中用 `SELECT … FOR UPDATE` 锁住时段行。确认归属后，在持锁状态下检查预约和开始时间，再删除并提交。失败时回滚，保留时段和关联数据。
3. **创建预约** 沿用申请行、时段行的加锁顺序，持锁检查资格后写入预约。删除只锁时段行。按 `READ COMMITTED` 在获得时段锁后查询 `booking`，可看到先提交的预约。预约先提交时删除返回 `409`，删除先提交时预约返回 `404`。
4. **并发约束** `booking.application_id` 和 `booking.slot_id` 分别唯一，外键保护预约引用的时段。两名符合资格的候选人竞争同一时段时，一方成功，另一方收到 `409` 和 `Slot already booked`，数据库保留一条预约。

### 申请状态流转

新申请默认为 `Pending`，见 [FP-CAN-3](docs/REQUIREMENTS.md#fp-can-3-applications)。[FP-EMP-3](docs/REQUIREMENTS.md#fp-emp-3-applicant-management)规定了四个合法状态 `Pending`、`Interviewing`、`Rejected`、`Accepted`，并规定只有职位所属雇主能修改。课程未规定状态流转顺序，现有实现允许直接从 `Pending` 改为 `Accepted`。

[FP-SCHED-2](docs/REQUIREMENTS.md#fp-sched-2-booking-eligibility)把 `Interviewing` 设为创建预约的前提。已有预约的申请改为 `Accepted` 或其他状态后，预约继续关联原申请，时段继续占用。状态更新与预约共用申请行锁。

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
