> 历史报告副本：保留原日期、SHA和当时状态；路径按本次仓库结构重写。历史日志/数据库/截图未发布，当前运行方式见测试README。不能把旧结果当作新提交执行。

# 匹配、申请和职位回归阶段检测报告

日期：2026-11-22（Asia/Shanghai）
固定提交：`f12f819df6bddef8a1e914e95b515933cc722a96`。

本阶段共 **86 次 pytest 执行，73 通过、13 失败、0 错误、0 跳过**；另有 3 个生成式用例内部合计 3000 组合法技能输入及相应蜕变检查全部通过。评分公式、两端排序、常规 CRUD 和申请回归没有在这些检查中失败；失败集中于并发技能整体替换和不可存储 NUL 文本处理。

按两类问题记录，其中候选技能与职位要求技能为两个独立实现/修复落点，分别建立原因 ID；NUL 的多个字段按同一存储表示边界原因归并。13 次失败不等于 13 个 bug，本报告不自行推算课程审计计分。已有文档曾记载候选技能竞态和 NUL 待修，本轮提供当前 SHA 的动态证据，不冒称首次发现这些历史线索。

项目源码、现有测试、迁移、seed 与配置均未修改，统一修复尚未开始。每项失败已关联原因、适用条件、原始证据和修复后新增测试计划，见 失败原因记录（历史本地产物：`失败原因与修复后加测计划.md`，未随仓库发布）。

## 范围与输入

判据在执行前保存于 测试矩阵（历史本地产物：`判据与测试矩阵.md`，未随仓库发布），依据 FP-MATCH-1、FP-CAN-2/3、FP-EMP-2/3 与当前整体技能替换契约。使用固定归档、新建的三个只监听本机的 PostgreSQL 16.4 集群、项目独立 Python 3.12.4 环境；每个用例清空本轮隔离库。

快照包含 Job、JobSkill、CandidateProfile、CandidateSkill、EmployerProfile、Application、Booking、InterviewSlot 八张相关表。固定 ID 排序数据和历史依赖在测试库中直接构造；正常创建、更新、投递与读取通过真实路由。权限仅用合成账号验证现有归属合同。

## 批次结果

| 批次 | 内容 | 通过 | 失败 |
|---|---|---:|---:|
| scores-views | 精确评分、固定 seed 输入、两端完整排序和实时重算 | 25 | 0 |
| crud-replacement | 常规职位/申请回归与并发/存储边界 | 45 | 5 |
| focused-replays | 新库复核、交叉技能邻域、顺序和 Unicode 对照 | 3 | 8 |
| 合计 | 含复现/诊断重复 witness | 73 | 13 |

原始失败均保留，未以修改实现、放宽断言、忽略用例或 xfail 隐藏。每批有同一条 Starlette/httpx 弃用警告，不影响结果。未收集代码覆盖率百分比、未进行变异测试或 CPE 内部变体。

## 已通过的核心检查

- 独立参考使用集合与 Fraction/floor，不调用项目 normalize_skills 或 match_score 生成期望。手算 100/50/0/空要求 100、2/3=66、1/3=33；Unicode 按 lower，未擅自用 casefold。
- 固定 seed 4801、20261122、73013 各生成 1000 组结构化合法技能列表，验证精确结果、整数范围、输入未被修改；排列、空白、重复、空项、无关技能和新增满足技能关系。大小写蜕变只用于 ASCII 域，避免 ß/İ 产生错误关系。不是覆盖反馈 fuzzing 或任何论文完整系统的复现。
- 两端用固定 UUID、真正同名与大小写变化、相反插入次序、不同分数，从 fixture 独立算完整有序 ID/分数；候选列表不包含已删除职位。不是对输出自身排序后充当 oracle。
- 原始简历、职位描述、公司描述变化不影响分数及顺序；技能和要求更新立即重算，要求清空为 100；双方调用同一实现，并分别与独立值比较。
- 职位创建/更新错误输入以 422 拒绝，八表快照不变；字段省略保留、要求技能清空、非空标题/描述与正常归一化持久化；四类删除依赖真值表。
- 新申请 Pending，四种状态下重复均拒绝且八表快照不变；额外字段、缺失/已删除职位、非法 ID 和其他雇主读/改/删/管理申请人均按合同拒绝。历史申请在固定时间/ID 排序和已删除职位夹具中保留字段。共享但未绑定职位的时段不随独立职位删除而消失。

## 已确认失败原因

### REG-CAND-01：候选技能并发整体替换合并

初始技能 [legacy]；两个正常 PATCH 分别替换为 [python] 和 [sql]。测试在第一个 DELETE 持锁后发出第二个请求，并用 PostgreSQL 的 Lock 等待与阻塞 PID 确认第二个 DELETE 正在等待。两者最终返回 200，但持久技能变为 [python, sql]，既不是第一份也不是第二份完整替换。

当职位要求为 [python, sql] 时，任一正确完整替换的分数都应为 50，实际合并后为 100。新库复核相同；把两份输入改成交叉集合时，第二个请求因 candidate_skill_pkey 重复返回 500。顺序更新对照正常得到 [sql] 和 50 分。评分函数本身没有算错，错误是并发持久化改变了其输入。

### REG-JOB-01：职位要求技能的独立实现有同类竞态

同样的非空旧技能删除窗口出现在 employer.update_job。两个返回 200 的更新把要求合并为 [python, sql]。候选技能为 [python] 时，任何一份完整要求都应得 100 或 0，实际合并后为 50；交叉输入触发 job_skill_pkey 重复并返回 500，顺序对照则正常。

两处原因都是未将父对象读取、删除旧技能和插入新技能作为整体替换进行串行化。在 READ COMMITTED 下，第二条 DELETE 的语句快照早于第一事务提交，等待后不能删除第一事务新插入的技能。两处实现须分别核验修复；不因为模式相同就假设修一处会修好另一处。

定位：`backend/app/candidate/service.py:111`；`backend/app/candidate/service.py:121`；`backend/app/employer/service.py:189`；`backend/app/employer/service.py:202`。证据包含 候选最终状态（历史本地产物：`test_concurrent_whole_list_replacements_cannot_merge_into_a_third_value_candidate-skills_-replacement-result.json`，未随仓库发布）、职位最终状态（历史本地产物：`test_concurrent_whole_list_replacements_cannot_merge_into_a_third_value_job-skills_-replacement-result.json`，未随仓库发布） 及 交叉输入的数据库重复约束日志（历史本地产物：`focused-replays-postgres.log`，未随仓库发布）。

### REG-TEXT-01：NUL 输入未在存储边界前校验

JSON 可表达的真实 NUL 字符通过当前 schema，普通标题、描述或技能中的该字符到写入阶段才触发 PostgreSQL text fields cannot contain NUL (0x00) bytes，接口返回 500。新库复核到候选简历/技能、公司描述、职位描述更新；普通 Unicode 与标点对照正常。失败后八表快照均不变，因此本轮没有证据表明发生部分写入或数据破坏。

本项预期是对不支持的存储输入明确 4xx 拒绝并保持状态，不把它算作安全利用、SQL 注入或普通 Unicode 均不可用；精确错误码与支持字符规则可在后续统一修复时按确认的契约落实。实际异常类型/堆栈见 驱动错误证据（历史本地产物：`test_capture_nul_driver_exception_without_changing_application-nul-exception.json`，未随仓库发布）。

## 失败记录与修复后新增测试

13 个失败执行分别关联已确认原因：REG-CAND-01 为 3 次，REG-JOB-01 为 3 次，REG-TEXT-01 为 7 次；每条保留原 SHA、断言输出、预期和根因证据，见 failure-analysis.json（历史本地产物：`failure-analysis.json`，未随仓库发布）。

修复后须在原复现红转绿和原通过组回归之外，另行新增初始空列表、三请求/清空、技能与独立字段并发、字符位置及字面转义对照等用例。已登记各项新增维度与原因，目前只是计划，不是已修或已运行回归。当前所有探索均属于修复前测试，不能以后改名充当“修复后新增”。

## 文件与复现

| 文件 | 用途 |
|---|---|
| [test_matching_oracles.py](../../../tests/specialized/test_matching_oracles.py) | 手算/参考公式、3000 trial、蜕变关系、共享实现 |
| [test_matching_views.py](../../../tests/specialized/test_matching_views.py) | 两端排序、实时匹配和无关文本 |
| [test_applications_jobs.py](../../../tests/specialized/test_applications_jobs.py) | 45 项申请与职位回归 |
| [test_replacement_and_text.py](../../../tests/specialized/test_replacement_and_text.py) | 初次并发与文本边界失败 |
| [test_failure_replays.py](../../../tests/specialized/test_failure_replays.py) | 新库复核、原因对照与邻域扩展 |
| [conftest.py](../../../tests/specialized/conftest.py) / run_stage.py（历史本地产物：`run_stage.py`，未随仓库发布） | 隔离夹具、八表快照、运行与清理 |

```text
<project-python> run_stage.py scores-views <stage>/test_matching_oracles.py <stage>/test_matching_views.py
<project-python> run_stage.py crud-replacement <stage>/test_applications_jobs.py <stage>/test_replacement_and_text.py
<project-python> run_stage.py focused-replays <stage>/test_failure_replays.py
```

完整 cwd、参数、退出码与日志见各批 *-tests.json；逐用例结果见 用例与结果（历史本地产物：`用例与结果.md`，未随仓库发布）。三个临时 PostgreSQL 集群均已关闭，原仓库干净，原始跟踪内容与固定提交一致。未操作已有服务或真实业务库。

## 与课件对应及剩余范围

独立判据和差分参考对应 L12 p.8–21；蜕变关系对应 L12 p.22–28；有界结构化生成与固定 seed 对应 L13 p.6–18；输入边界和失败原子性对应 L14 p.7–19、23–27。受控 DELETE 等待是本组功能并发观测，不声称形式证明；未修改生产代码构造变异。

本轮未做完整浏览器、全面安全审查、真实大规模性能或可选 AI 功能评测。既有 SLOT-01 和早期文档/交付问题仍未修复；此前投递/职位删除的有锁调度证据沿用，没有机械重跑旧整套测试。后续阶段继续按计划，统一修复仍在总检测报告之后。

- 结构化发现（历史本地产物：`findings.json`，未随仓库发布）
- 汇总（历史本地产物：`execution-summary.json`，未随仓库发布）
- 第一批（历史本地产物：`scores-views-summary.json`，未随仓库发布）、第二批（历史本地产物：`crud-replacement-summary.json`，未随仓库发布）、聚焦复核（历史本地产物：`focused-replays-summary.json`，未随仓库发布）
- 第一批完整性（历史本地产物：`scores-views-integrity.json`，未随仓库发布）、第二批完整性（历史本地产物：`crud-replacement-integrity.json`，未随仓库发布）、复核完整性（历史本地产物：`focused-replays-integrity.json`，未随仓库发布）
- 常见问题与重点风险记录（历史本地产物：`常见问题与重点风险记录.md`，未随仓库发布）
