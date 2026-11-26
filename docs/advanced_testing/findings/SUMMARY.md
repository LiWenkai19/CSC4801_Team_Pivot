# 高级测试业务缺陷汇总（P11）

> 下文为 P11 历史证据；后续补齐 OpenAPI 4xx 声明的复测见 [APIFUZZ.md](../APIFUZZ.md#post-audit-documentation-retest)。保留的793条历史漂移记录不表示仍未修复。AUTH-01 按团队决定不作为 bug，不属于待修条目。

本文件汇总 `docs/advanced_testing/findings/P*.md` 中的业务/契约缺陷，按**根因去重**。
测试与验证任务（P0–P12）没有修改生产代码；修复由实现负责人在独立分支完成，
本文件只记录状态与验证证据。

## 0. 汇总

| # | 标题 | 需求条款 | 根因 | 状态 | 修复 commit | 回归测试 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 面试时段创建的 422 业务响应体不符合 OpenAPI 的 `HTTPValidationError` | FP-SCHED-1 / SPEC Employer interview slots | 路由对业务错误抛 `HTTPException(422, str(error))`，但 OpenAPI 只声明了 FastAPI 的 `HTTPValidationError` 数组；同一状态码两种响应体 | **已修复** | `0ea722364e18b921cbdacdcba879a9ef44a43c03`（PR #14，merge `88a660e`） | `tests/unit/test_scheduling.py::test_fp_sched_1_openapi_422_documents_business_and_validation_shapes` |

当前只有 1 条需要修复的缺陷；没有“未修”条目。

## 1. 已修复条目

### P8：`POST /employer/interview-slots` 的 422 契约不一致

- **来源文件**：[P8.md](P8.md)
- **发现方式**：P8 从实时 `/openapi.json` 生成请求，用 Schemathesis
  `response_schema_conformance` 检查响应体；一次完整运行中雇主轮 10 个写样例有 9 个命中。
- **最小输入**：已登录且带 CSRF 的雇主执行
  `POST /employer/interview-slots`，body `{"starts_at": "2000-01-01T00:00:00Z"}`。
- **期望**：422，响应体符合 OpenAPI 的 `HTTPValidationError`，即 `detail` 是数组。
- **实际（修复前）**：422，`{"detail": "Slot must start in the future"}`（字符串），
  `ST108 Response violates schema`。
- **根因**：`backend/app/interview/router.py` 的业务错误映射返回字符串 detail，
  而 OpenAPI 只声明了请求校验阶段的数组结构；`backend/app/main.py` 的自定义 422
  处理器只覆盖 `RequestValidationError`，不覆盖路由自己抛出的 `HTTPException`。
- **修复**：commit `0ea722364e18b921cbdacdcba879a9ef44a43c03`
  （`fix(interview): document both 422 response shapes for slot creation`，
  PR #14，merge `88a660e`）。路由为 422 声明 `anyOf`，同时记录
  `HTTPValidationError` 数组与业务字符串两种响应体。
- **回归测试**：`tests/unit/test_scheduling.py::test_fp_sched_1_openapi_422_documents_business_and_validation_shapes`
  （断言 OpenAPI 422 schema 的 `detail` 同时允许 `string` 与 `array`）。
- **重跑验证**：修复后 `python tests/advanced/run.py apifuzz` 的 `attribution.real_defect`
  从 9 降到 **0**；`schema_drift = 793` 仍保留，因为 FastAPI 未声明 FP-AUTH-3 要求的
  401/403/404 与 SPEC 的 400/409，这属于 API 文档工作，不是本次缺陷。
- **修复 commit 与回归测试的核实方式**（没有只看任务书）：
  `git show --stat 0ea7223` 显示只改 `backend/app/interview/router.py` 与
  `tests/unit/test_scheduling.py`；`git branch --contains 0ea7223` 确认它已通过
  `88a660e` 合并进 `main`；回归测试名从 `tests/unit/test_scheduling.py:274` 读出。

## 2. 已归因但“不是缺陷”的条目

这些条目出现在各任务的报告里，但按需求/SPEC 判断不构成业务缺陷，故没有
`findings/P*.md`，在此单列以免被误读为漏记：

| 来源 | 现象 | 为什么不是缺陷 |
| --- | --- | --- |
| P7 | 19 个变异体 survived | 逐个归因为等价变异、契约等价、不可达或“仅真实 SQL 可观测”；属于缺测试或单元层不可观测，不是实现错误。 |
| P8 | 793 次 `schema_drift` | 401/403/404/400/409 是 FP-AUTH-3/SPEC 要求的行为，FastAPI 只是没有在 OpenAPI 中声明；按 `schema_drift` 记录，不用过滤器吞掉。 |
| P9 | I5 删除职位只由应用层检查 | `delete_job` 是软删除，数据库外键不阻止 `UPDATE`；正常代码路径仍返回 409，符合 FP-EMP-2，是防御纵深事实。 |
| P10 | 冻结运行 F1 collection error / F2 19 个失败 | 分别是生成器的 parametrize id 数写错、合成 `User` 漏 `role`；修正 setup 后 123 passed / 1 skipped / 0 failed，期望值未改。 |
| P10 | 1 个 skipped | 契约明确不定义 `None`/裸字符串/非 str 元素的行为，记录为歧义 A1，不是隐藏失败。 |

## 3. 复现

```sh
# 当前唯一缺陷的测试入口（修复后应 real_defect=0）
python tests/advanced/run.py apifuzz --out <仓库外空目录>

# 回归测试
python tests/run_tests.py

# 汇总报告（P11）
python tests/advanced/report.py <run.py all 的产物目录> --unit-junit <unit.xml>
```
