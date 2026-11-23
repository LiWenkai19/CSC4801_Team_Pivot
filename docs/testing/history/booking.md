> 历史报告副本：保留原日期、SHA和当时状态；路径按本次仓库结构重写。历史日志/数据库/截图未发布，当前运行方式见测试README。不能把旧结果当作新提交执行。

# 预约与跨模块交互阶段检测报告

日期：2026-11-22（Asia/Shanghai）
固定提交：`f12f819df6bddef8a1e914e95b515933cc722a96`。

本轮增量检测 **121 项全部通过，0 失败、0 错误、0 跳过**。未复现新的产品缺陷。此前 SLOT-01 等问题仍未修复，不能因为本轮通过而将它们关闭，也不能由有限测试推出没有其他 bug。

用户要求保持：全部测试和总报告完成前只检测，不修复；失败时记录原因及证据，原因未确认标为假设；修复后在原用例回归之外新增根因驱动用例并实际执行。本阶段没有失败用例，因此没有虚构新的失败原因或已修回归。

## 增量范围与环境

判据见 判据与增量范围（历史本地产物：`判据与增量范围.md`，未随仓库发布）。本轮复用上一轮已验证的基础流程和观测方法，未重新运行其整套 95 次执行；聚焦未覆盖的多条件组合、完整状态转换、等待中前置条件失效、三请求争用与跨模块变化。

从固定 SHA 归档导出本轮 clean-source，使用既有项目独立 Python 3.12.4 依赖环境，在两个新 PostgreSQL 16.4 集群上执行，均只监听 127.0.0.1。测试只冻结 candidate/interview service 的业务时钟为 2030-05-01 UTC；认证时钟与会话机制不改。每项用例前清空本轮测试库，所有请求使用合成账号。

六条件组合中的某些已有预约是用隔离库直插构造的历史状态，用于同时控制“过去、已预约、非 Interviewing”等因素；不是通过修改生产逻辑生成。资格 oracle 在已有资源、合法 30 分钟时段的域中穷举，不覆盖任意输入格式和所有可能的数据库状态。

## 结果与文件位置

| 文件 | 数量 | 主要内容 |
|---|---:|---|
| [test_booking_eligibility.py](../../../tests/specialized/test_booking_eligibility.py) | 73 | 64 种资格组合＋9 类请求错误 |
| [test_booking_states.py](../../../tests/specialized/test_booking_states.py) | 34 | 32 条状态转换＋2 项跨模块/多申请检查 |
| [test_booking_transactions.py](../../../tests/specialized/test_booking_transactions.py) | 7 | 3 项 flush 后失败回滚、1 项未知完整性错误分类、3 项真实 DB 约束 |
| [test_booking_schedules.py](../../../tests/specialized/test_booking_schedules.py) | 7 | 3 项等待中过期、2 项三请求争用、2 项投递/删除调度 |
| 合计 | 121 | 全部通过 |

第一批 107 项通过（pytest 45.15 秒）；第二批 14 项通过（pytest 5.23 秒）。均未使用 --ignore、-k、xfail 或更改断言消除失败。每批有同一条 Starlette/httpx 弃用警告，没有导致失败。未收集覆盖率百分比，也未进行变异测试或形式证明。

测试代码与证据目录为本报告所在文件夹；[conftest.py](../../../tests/specialized/conftest.py) 是本轮夹具，run_stage.py（历史本地产物：`run_stage.py`，未随仓库发布） 是执行入口。逐用例结果（历史本地产物：`用例与结果.md`，未随仓库发布）、汇总 JSON（历史本地产物：`execution-summary.json`，未随仓库发布） 和各批 JUnit XML 保留了实际执行数据。

## 资格组合与状态验证

六个条件为：申请归属、同雇主、Interviewing、未来时间、时段空闲、申请未预约。穷举 64 种组合，只有全部满足的一行创建成功；其余 63 行按合同拒绝，Application、InterviewSlot、Booking、Job 四张相关业务表的完整快照保持不变。多个条件同时不成立时，不擅自规定规格没有定义的错误优先级；孤立归属错误检查 403，孤立资格冲突检查 409。

对满足查看前置条件的组合，还以 fixture 条件独立计算候选人可用列表，检查其 ID 集合和 GET 无业务副作用。结果见 64 行决策表（历史本地产物：`decision-table-results.json`，未随仓库发布），不是从当前服务输出倒推期望。

对四个状态分别检查 source→target，分为已有预约和未预约两类，共 4×4×2=32 项。每次转换先断言请求成功与实际持久化；已有预约的关联保持、雇主可用列表保持不可选；未预约的申请仅在目标状态 Interviewing 时允许预约。覆盖包含同状态重复设置，不人为禁止 Pending→Accepted 等规格允许的转换。

候选人显示名/技能、雇主公司名、职位标题/描述/要求技能更新后，预约和申请关联保持，双方接口展示新资料；删除有申请与预约依赖的职位返回 409，相关数据不变。另验证同一候选人的不同申请可以分别预约不同的合法时段，不添加课程没有规定的“每人只能预约一次”限制。

## 事务、约束与等待期间的失效

创建申请、修改状态、创建预约均在真实 flush 后注入提交失败，检查所有相关记录回滚。未知的 IntegrityError 在没有实际重复记录时继续抛出原数据库错误，而非误报已预约。它们是测试侧故障注入，没有修改生产实现。

实际数据库拒绝重复 slot_id、重复 application_id，SQLSTATE 均为 23505；直接删除被预约引用的 slot 被外键以 23503 拒绝，失败后完整快照不变。这与 API 合同测试互补，不能将单个约束通过当作整套业务验证。约束名称与原始结果见 调度与约束结果（历史本地产物：`schedule-and-constraint-results.json`，未随仓库发布）。

## 七组新增受控调度

所有等待均先由 PostgreSQL pg_stat_activity 的 Lock 状态及非空 pg_blocking_pids 确认；不以线程启动或屏障本身代替数据库争用证据。

| 场景 | 实际结果 |
|---|---|
| 投递/职位删除：apply-first | 201 / 409 |
| 投递/职位删除：delete-first | 204 / 404 |
| 三条请求均已等待：one-application-three-slots | 201 / 409 / 409 |
| 三条请求均已等待：three-candidates-one-slot | 201 / 409 / 409 |
| 等待中恰好到开始时刻：book | 409 |
| 等待中恰好到开始时刻：create | 422 |
| 等待中恰好到开始时刻：delete | 409 |

三个过期场景中，请求先在有效时间发出并进入实际行锁等待，测试侧将时钟推进至 starts_at，再释放锁。创建返回 422，删除/预约返回 409，消息均对应时间失效，相关业务快照不变，说明在这些轨迹下持锁后重新检查了时间。

两个三请求场景分别为三候选人争同一时段、同一申请争三个不同时段。释放前确认三个不同 PID 均在等待，之后各恰一 201、两 409，数据库仅一条预约，指向实际胜出的申请/时段。投递先提交时删除冲突；删除先提交时投递缺失，未出现对已删除职位的新申请。

有限调度无法证明所有线程时序、超时策略或数据库隔离级别均正确；本报告仅确认上述观察到的轨迹。

## 课件方法与剩余边界

| 方法 | 课件依据 | 本轮产物 |
|---|---|---|
| 规格拆解与决策表 | L06/L07；L14 p.7–13 | 六条件独立布尔 oracle，64 行组合 |
| 有界状态关系、前后条件 | L13 p.19–26、45–52 | 32 条转换、等待期间前置条件失效 |
| 失败原子性与精确断言 | L14 p.23–27；L12 p.8–21 | 四表快照、flush 后失败、SQLSTATE 与真实关联 |
| 固定输入和隔离 | L10 p.8–20、29–52 | 固定归档、两个新集群、命令/日志/完整性 |

本轮是手工有界组合、状态关系和可控调度；没有将它们改名为 fuzzing、内部变体或穷尽真实系统状态的形式验证。没有调用真实第三方服务，也没有停止已有业务服务。

完整浏览器 UI、其他匹配/CRUD 和全面认证安全矩阵仍由后续阶段处理。SLOT-01 的极端日期与数据库时区问题沿用此前未修复状态，本轮不重复该已确认根因，不把普通日期下全绿当作它已修复。

## 命令、依赖与清理

```text
<project-python> run_stage.py decision-states <stage>/test_booking_eligibility.py <stage>/test_booking_states.py
<project-python> run_stage.py transactions-schedules <stage>/test_booking_transactions.py <stage>/test_booking_schedules.py
```

run_stage.py 默认也可运行四个文件。调度模块复用 [上一阶段锁等待观察 helper](../../../tests/specialized/test_slots_races.py)，只调用 helper，不重跑其九项旧测试；复制本阶段产物时需一并保留该依赖。所有原始参数、退出码、cwd 和日志见各批 *-tests.json。

两个新 PostgreSQL 集群均已停止，目录保留本轮合成数据。原仓库 Git 状态干净，原始跟踪内容与固定 SHA 一致；未修改业务实现、既有测试、seed、迁移或项目配置。风险记录已回填，统一修复尚未开始。

- 第一批结果（历史本地产物：`decision-states-summary.json`，未随仓库发布）、命令（历史本地产物：`decision-states-tests.json`，未随仓库发布）、原始日志（历史本地产物：`decision-states-tests.txt`，未随仓库发布）
- 第二批结果（历史本地产物：`transactions-schedules-summary.json`，未随仓库发布）、命令（历史本地产物：`transactions-schedules-tests.json`，未随仓库发布）、原始日志（历史本地产物：`transactions-schedules-tests.txt`，未随仓库发布）
- 发现与未修复问题状态（历史本地产物：`findings.json`，未随仓库发布）
- 第一批完整性（历史本地产物：`decision-states-integrity.json`，未随仓库发布）、第二批完整性（历史本地产物：`transactions-schedules-integrity.json`，未随仓库发布）
- 常见问题与重点风险记录（历史本地产物：`常见问题与重点风险记录.md`，未随仓库发布）
