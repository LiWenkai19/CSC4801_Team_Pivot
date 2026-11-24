# 面试时段与预约实现计划

雇主端三个后端接口已接入。验收依据见[课程需求 FP-SCHED-1～3](../../../docs/REQUIREMENTS%20中文翻译.md)。

## 范围

- **FP-SCHED-1** 雇主可创建、查看和删除本人时段。新建时段须在未来、恰好 30 分钟。项目另规定时段结束时间须早于上海时间 `3001-01-01 00:00`，超出返回 `422`。已预约时段在雇主管理页标为已预约，并禁止删除。
- **FP-SCHED-2** 复用[候选人预约流程](../candidate/service.py)。只允许申请本人预约该职位所属雇主的未来空闲时段，申请须处于 `Interviewing` 且尚无预约。成功后双方可见，后续状态变更保留预约。
- **FP-SCHED-3** 复用 PostgreSQL 行锁和唯一约束。同一时段发生竞争时恰好一个成功，另一请求返回 `409 Slot already booked`，数据库只保留一条预约。

## 数据模型

复用[现有模型](../employer/model.py)与迁移。服务层校验开始时间在未来，再加 30 分钟得出结束时间。

| 表 | 字段与约束 |
| --- | --- |
| `interview_slot` | `id` 为 UUID 主键，`employer_id` 指向雇主资料。保留现有可空 `job_id`，新建时段按雇主共享，`job_id` 留空。`starts_at` 和 `ends_at` 为 PostgreSQL `timestamptz`，已有约束要求结束晚于开始。 |
| `booking` | `id` 为 UUID 主键，`application_id` 和 `slot_id` 为外键且分别唯一，`created_at` 记录预约时间。是否已预约由该表判断。 |

开始时间使用带时区的 ISO 8601 字符串，如 `2026-12-01T09:00:00+08:00`。服务统一转 UTC 后比较、保存和返回。新页面以 `Asia/Shanghai` 展示并标注时区。

## 雇主接口

统一使用 `require_employer`。未登录返回 `401`，错误角色或删除他人时段返回 `403`。时段归属取自登录用户，时段响应包含 `id`、`starts_at` 和 `ends_at`。

| 接口 | 行为 |
| --- | --- |
| `POST /employer/interview-slots` | 仅接收 `starts_at`，由服务端加 30 分钟计算结束时间。成功返回 `201`，同一雇主的时段重叠返回 `409`，时间非法或传入额外字段返回 `422`，雇主资料缺失返回 `404`。 |
| `GET /employer/interview-slots` | 返回本人尚未开始的所有时段，含 `is_booked`，按开始时间和 ID 排序。 |
| `DELETE /employer/interview-slots/{slot_id}` | 删除本人的未来空闲时段，成功返回 `204`。时段不存在返回 `404`，已开始或已预约返回 `409`。 |

创建时先锁住雇主资料行，再检查是否与已有时段重叠。已预约时段参与检查，首尾相接允许创建。

删除和预约对同一时段使用 PostgreSQL `FOR UPDATE`。删除在持锁后检查预约并提交。预约先成功时删除返回 `409`。删除先成功时预约返回 `404`。现有外键同时保护已被预约引用的时段。

## 实施顺序

1. 先实现创建接口，在模块内按 `schema.py`、`service.py`、`router.py` 分层。接入后端应用，验证时区、时长、未来时间和雇主身份。
2. 实现列表和删除，覆盖跨雇主访问、过期时段过滤、预约状态显示、删除失败后记录保留，以及删除与预约的并发。
3. 接入雇主页面的创建、查看、删除流程。回归候选人预约、双方查看和状态变更后保留预约，并在隔离 PostgreSQL 上验证两个候选人竞争同一时段。同步规格和需求对应的测试名称。

## 修复进度

- 2026-11-24 · SLOT-01 验证通过。创建服务 [`create_slot`](service.py) 在写入前检查年份上限，雇主页面显示对应语言的提示。`python tests/specialized/run.py slots` 在隔离 PostgreSQL 上通过 12 个日期用例，总计 90 通过、7 失败。剩余 7 项在修复前的提交 `86712d6` 上也失败，涉及列表字段与预约后职位关联。使用 `UI_SUITE_ONLY=slot-cutoff` 运行 `python tests/specialized/run.py browser --browser-script browser_followup`，Chrome 用例通过。已存在的越界时段仍需单独处理。
