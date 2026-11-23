> 历史报告副本：保留原日期、SHA和当时状态；路径按本次仓库结构重写。历史日志/数据库/截图未发布，当前运行方式见测试README。不能把旧结果当作新提交执行。

# 现有基线阶段检测报告

日期：2026-11-22（Asia/Shanghai）
固定提交：`f12f819df6bddef8a1e914e95b515933cc722a96`。

完整后端现有基线为 **145 passed、0 failed、0 errors、0 skipped**，pytest 耗时 25.28 秒，退出码 0；未用 --ignore、-k、xfail、修改断言或重试掩盖失败。没有通过现有基线复现新的产品运行缺陷，另记录 2 项测试覆盖缺口和若干断言局限。所有项目源码和现有测试均未修改，修复继续延后到所有测试和总报告完成之后。

## 执行环境与隔离

使用同一提交的全新源码归档副本，以及上一阶段按 requirements.txt 创建的独立 Python 3.12.4 环境。pip check 通过。新建 PostgreSQL 16.4 集群，只监听 127.0.0.1；候选人测试自行创建随机测试库，雇主使用该新集群内的 symanage_test，账户测试使用隔离 SQLite。

只在本轮导出副本写入 backend/.env，以满足现有雇主 fixture 的配置读取方式；原仓库配置和现有数据库不受影响。PYTHONHASHSEED=4801；未冻结已有测试的系统时钟，也未强行固定 UUID、线程调度或随机会话令牌。因此本轮是一轮基线执行，不是确定性调度证明。

```text
# cwd: 本轮 clean-source/backend
<project-python> -m pytest tests -q -ra -p no:cacheprovider --junitxml=<evidence-dir>/full.xml
```

完整参数、绝对路径和退出码见 full-backend.json（历史本地产物：`full-backend.json`，未随仓库发布），原始控制台输出见 logs/full-backend.txt（历史本地产物：`full-backend.txt`，未随仓库发布），逐用例结果见 full-summary.json（历史本地产物：`full-summary.json`，未随仓库发布） 和 JUnit XML（历史本地产物：`full.xml`，未随仓库发布）。

## 模块结果

| 模块 | 通过 | 失败/错误/跳过 |
|---|---:|---:|
| tests.candidate.test_booking | 8 | 0/0/0 |
| tests.candidate.test_jobs | 19 | 0/0/0 |
| tests.candidate.test_profiles | 12 | 0/0/0 |
| tests.employer.test_applicants | 11 | 0/0/0 |
| tests.employer.test_company | 4 | 0/0/0 |
| tests.employer.test_jobs | 9 | 0/0/0 |
| tests.employer.test_matching | 4 | 0/0/0 |
| tests.users.test_account_responses | 56 | 0/0/0 |
| tests.users.test_schema | 22 | 0/0/0 |
| 合计 | 145 | 0/0/0 |

候选人合计 39 项，雇主 28 项，账号响应 56 项，数据结构校验 22 项。旧的 test_schema.py 收集问题没有重现，22 项校验测试已实际执行并通过。

本轮已执行现有的两个预约并发测试及重复投递并发测试，并非跳过这部分。它们使用真实 PostgreSQL、多个客户端和同步屏障，实际结果满足原有断言；单次通过不能保证所有并发调度正确。

## 测试发现与通过计数的边界

仓库根目录额外执行了一次 collect-only，收集到 162 项：145 项后端用例加 17 项 pass 模板。该次只收集，不声称 162 项在本轮全部执行；17 项模板上一阶段已执行，但不计入有效行为验证。见 根目录收集日志（历史本地产物：`root-collection.txt`，未随仓库发布） 和 静态用例清单（历史本地产物：`static-test-inventory.json`，未随仓库发布）。

前端构建和 lint 沿用上一阶段同一提交、相同依赖环境的通过记录：构建（历史本地产物：`frontend-build.json`，未随仓库发布）、lint（历史本地产物：`frontend-lint.json`，未随仓库发布）。原源码及依赖未变，本轮未重复执行。浏览器脚本留待页面阶段，不列入这 145 项基线。

本轮有 1 条 Starlette/httpx 弃用警告，未造成失败。没有安装覆盖率插件、没有收集分支或语句覆盖率，也没有运行变异测试；不能将 145 项通过换算成覆盖率或测试强度分数。

## 两项覆盖缺口

**BL-G01：新增雇主时段管理没有实质自动化测试覆盖**

对应要求：FP-SCHED-1 / FP-TEST-1。证据状态：静态确认；不是已复现的产品功能 bug。

145 项全部位于 candidate/employer/users；现有测试没有调用 /employer/interview-slots 或 app.interview 的创建、列表、删除逻辑。时段 fixture 直接插表；根目录时段测试是 pass 占位符。

定位：`backend/tests/candidate/conftest.py:155`；`backend/tests/employer/conftest.py:251`；`tests/unit/test_scheduling.py:4`。

后续验证：下一阶段用原接口验证时间/时长、时区、重叠、列表、删除、权限及相关竞争，本轮不新增或修复测试。

**BL-G02：缺少实际渲染或净化逻辑的 XSS 单元测试**

对应要求：FP-SEC-3 / FP-TEST-1。证据状态：静态确认；不是已复现的 XSS 漏洞。

后端用例只验证特殊文本存取；实际页面文本检查在两份 browser.mjs 中。前端没有 unit-test 脚本或实质渲染单测，浏览器脚本不能替代课程规定的单元测试。

定位：`backend/tests/candidate/test_profiles.py:32`；`frontend/package.json:6`；`frontend/tests/candidate.browser.mjs:188`。

后续验证：后续安全/页面阶段验证渲染控制，并在总报告中区分实际产品安全与单元测试证据缺失。本轮不执行脚本内容。

## 关键断言抽查

本轮按 10 组对象抽查 setup、独立判据、响应、持久化和拒绝后的副作用。以下记录是源码审查结论，未用程序变异检验每条断言的辨别力。

| 编号 | 对象 | 结论 |
|---|---|---|
| AR-01 | test_fp_match_1_skill_overlap_examples / test_fp_match_1_score_is_floor_and_bounded | 有独立精确判据 |
| AR-02 | test_fp_match_1_employer_applicant_tie_breakers / test_recommendations_share_scores_and_title_ties | 覆盖两端平级排序；可加强固定预期 |
| AR-03 | test_apply_once_in_every_status | 响应和存储均有断言 |
| AR-04 | test_fp_emp_2_delete_conflict_with_application / test_fp_emp_2_delete_conflict_with_interview_slot | 分别检查两类删除依赖 |
| AR-05 | test_booking_invalid_slot_rolls_back | 已有拒绝与无新增预约断言，失败原子性证据不完整 |
| AR-06 | test_real_postgres_two_candidates_compete_for_one_slot / test_same_application_concurrent_booking_has_one_winner | 真实数据库并发证据 |
| AR-07 | test_booking_visible_to_both_roles_and_survives_status_change | 双角色一致性已覆盖；状态变化前提可加强 |
| AR-08 | test_register_login_and_me_return_current_schema / test_unsafe_requests_require_matching_csrf_token | 认证状态与拒绝副作用有实质断言 |
| AR-09 | test_profile_permission_matrix | 测试体现项目策略；课程规格冲突仍在 |
| AR-10 | test_fp_sec_2_job_title_sql_metacharacters_are_bound / test_profile_patch_persists_and_preserves_omitted_fields | 普通数据存取有证据；不等于渲染验证 |

完整定位和解释见 assertion-review.json（历史本地产物：`assertion-review.json`，未随仓库发布）。需要优先补充的证据是：拒绝预约后的 Application、InterviewSlot 完整快照，以及预约保留测试中状态 PATCH 的成功码和最终状态。这里只记录局限，不改测试。

已有简历读取策略与课程规范的冲突仍为上一阶段 SPEC-Q01。对应权限测试通过只证明当前策略被实现，不证明课程隐私要求满足；不重复算作新发现。

## 课件方法与下一阶段

本轮采用固定版本/环境隔离（L10 p.8–20、29–52）、基线执行与 oracle/断言审查（L12 p.8–21）、按可观察结果区分有效用例与占位符（L14 p.4–13）。执行了仓库已有的并发和原子性测试，未新增覆盖方法，也未进行 fuzzing、内部变体或形式证明。

下一阶段按计划测试新增雇主时段管理：未来时间与时区边界、固定时长、重叠与首尾相接、列表过滤、删除规则，以及与预约交互。测试期间继续只记录问题，不提前修复。

## 清理与证据

基线结束时，候选人的随机测试库均已由 fixture 删除，集群内仅有 postgres 和 symanage_test；整个临时 PostgreSQL 实例已停止。原仓库 Git 状态干净，跟踪文件内容与固定提交一致。

- 固定输入与环境（历史本地产物：`full-manifest.json`，未随仓库发布）
- 数据库收尾清单（历史本地产物：`full-database-inventory.json`，未随仓库发布）
- 数据库关闭日志（历史本地产物：`full-pg-stop.txt`，未随仓库发布）
- 源码完整性（历史本地产物：`full-integrity.json`，未随仓库发布）
- 基线结果（历史本地产物：`full-summary.json`，未随仓库发布）
- 覆盖缺口与发现分类（历史本地产物：`findings.json`，未随仓库发布）
- [前一阶段报告](spec-env.md)
