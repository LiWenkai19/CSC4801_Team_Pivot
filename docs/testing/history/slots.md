> 历史报告副本：保留原日期、SHA和当时状态；路径按本次仓库结构重写。历史日志/数据库/截图未发布，当前运行方式见测试README。不能把旧结果当作新提交执行。

# 新增时段管理与高优先级交互阶段检测报告

日期：2026-11-22（Asia/Shanghai）
固定提交：`f12f819df6bddef8a1e914e95b515933cc722a96`。

首轮 80 项测试为 **79 passed、1 failed**；随后按失败根因追加日期边界、共享入口、真实 HTTP 及微秒/遗留时段测试。四批合计 95 次用例执行，88 通过、7 失败、0 错误、0 跳过；7 次失败归于同一个极端日期/数据库时区根因 SLOT-01。复现与诊断会重复同一 witness，因此不能把 95 次执行当作 95 个独立风险，也不能把 7 次失败计为 7 个 bug。

常规时间输入、创建/列表/删除、拒绝原子性、预约关联保留，以及 9 组受控数据库竞争均通过本轮断言。未修改项目实现或已有测试、seed、迁移和配置；仅在仓库外新建测试 harness、证据和报告。后续统一修复的要求保持不变。

## 固定输入与判据

执行前判据见 判据与测试矩阵（历史本地产物：`判据与测试矩阵.md`，未随仓库发布）。来源为本提交 SPEC、interview/PLAN 和课程 FP-SCHED-1～3、FP-AUTH-3。重叠规则和精确接口字段来自项目 SPEC；不额外创造课程 MUST。

使用原 Git archive 导出的源码、上阶段按 lock 安装的项目 Python 3.12.4 环境，以及四个全新 PostgreSQL 16.4 集群，均只监听 127.0.0.1。业务边界测试只冻结两个 service 导入的时钟为 2030-05-01 00:00:00 UTC；认证沿用真实 Cookie/CSRF。真实 HTTP 复现子进程未使用这个时钟替换。

每个用例前清空本轮测试库。拒绝原子性比较 Application、InterviewSlot、Booking、Job 四张相关业务表的完整快照，并在独立连接重读；这不声称已验证项目之外的外部副作用。测试代码位于本目录，未被追加进原仓库或替换队友测试。

## 实际执行结果

| 批次 | 范围 | 通过 | 失败 | 错误/跳过 |
|---|---|---:|---:|---:|
| initial | 52 项接口契约、19 项预约/回滚交互、9 项受控并发 | 79 | 1 | 0/0 |
| replay | 极端日期最小边界与 UTC 会话对照 | 2 | 2 | 0/0 |
| related-paths | 同一时段的删除、候选人列表、预约与真实 HTTP | 0 | 4 | 0/0 |
| precision-legacy | 微秒级重叠、旧长/短时段包含与相接 | 7 | 0 | 0/0 |
| 合计 | 含有重复 witness 的复现/诊断执行 | 88 | 7 | 0/0 |

逐用例结果见 用例与结果（历史本地产物：`用例与结果.md`，未随仓库发布），机器结果见 execution-summary.json（历史本地产物：`execution-summary.json`，未随仓库发布）。四批均保留非零失败退出码，没有改断言、xfail、过滤失败或修补实现让结果变绿。每批有同一条 Starlette/httpx 弃用警告，不影响测试判定。

## 常规与高优先级场景已检查的内容

- 创建起止时间精确相差 30 分钟、UTC 输出、微秒保留、真实归属及跨职位共享。
- 当前时刻前 1 微秒、恰好当前、后 1 微秒；缺失和错误类型、无时区、错误日期/偏移、额外字段、UTC 及结束时间溢出。
- 同一时刻的 Z、+08:00、-04:00、+05:45 表示，分别在清洁状态下产生相同 UTC 起止。
- 重合、左右部分重叠、首尾相接、不同雇主同一时间；补充 1 微秒重叠和间隙、旧 60 分钟包含新时段以及旧短时段被新时段包含。
- 独立构造列表真值：仅本人未来、未预约、30 分钟记录；同开始时间按固定 ID 排序；GET 业务快照不变。
- 未登录、错误角色、其他雇主、缺失对象、非法 UUID、缺少/错误 CSRF；正常删除为 204 空体，重复删除为 404，已开始或已预约拒绝且快照不变。
- 每项预约资格单独失败，完整业务快照不变；真实入口创建的时段可供多个本雇主职位的合格申请使用。
- 已预约时段阻止重叠创建、从雇主可用列表消失、不能删除；双方预约 ID 与关联一致。四种状态转换均先验证成功码及持久化状态，再验证预约保持和不可用性。
- 创建/删除在真实 flush 后注入提交失败，再验证数据库回滚。这是测试侧的故障注入，不是修改生产条件或修复事务。

## 受控数据库竞争

每个场景让第一条请求先取得实际 FOR UPDATE 行锁，再由测试侧 SQLAlchemy 观察回调暂停；第二条独立请求发出后，通过 pg_stat_activity 的 Lock 等待与 pg_blocking_pids 确认它确实被阻塞，之后才释放第一条请求。观测不会改变锁条件、SQL 或业务判断。

| 场景 | 第一/第二请求结果 | 等待行 |
|---|---|---|
| 相接创建 | 201 / 201 | employer_profile |
| 预约先、删除后 | 201 / 409 | interview_slot |
| 预约先、改 Rejected 后 | 201 / 200 | application |
| 删除先、预约后 | 204 / 404 | interview_slot |
| 重复删除 | 204 / 404 | interview_slot |
| 同一申请争两个时段 | 201 / 409 | application |
| 重叠创建 | 201 / 409 | employer_profile |
| 改 Rejected 先、预约后 | 200 / 409 | application |
| 两候选人争同一时段 | 201 / 409 | interview_slot |

9 组均通过，并断言唯一预约、关联有效、允许的最终状态及无部分写入。记录见 race-results.json（历史本地产物：`race-results.json`，未随仓库发布），每条记录链接原始等待信息和响应。它们是有限可控调度的证据，不是对所有调度或不同隔离级别的证明。

## SLOT-01：接受后的极端未来时段在时区读回时失败

状态：已复现，未修复。优先级暂记 P2；日期极端且依赖数据库返回时区，常规业务本轮未见同类失败。该根因与此前 SE-05 的 60 分钟 seed 问题不同。

最小前提：完整雇主账号；数据库会话 TimeZone=Asia/Shanghai；提交当前 SPEC 未排除且创建 API 实际接受的未来 ISO 时间。

```text
GET /employer/interview-slots -> 200
POST /employer/interview-slots {"starts_at":"9999-12-31T15:30:00Z"} -> 201
GET /employer/interview-slots -> 500
```

服务端生成的 UTC 结束时间为 9999-12-31 16:00:00，数据库按 UTC+8 返回时变为 10000-01-01 00:00:00+08。psycopg 在 ORM 读取阶段抛出 DataError，早于 SlotPublic 的 UTC 转换。创建时检查了 Python UTC 解析和加 30 分钟是否溢出，但没有覆盖数据库返回时区的可表示范围。

已缩小的边界：开始时间 9999-12-31T15:29:59.999999Z 可正常创建与列出；15:30:00Z 开始失败。原始异常与数据库文本，以及仅在隔离连接中设置 UTC 后同一 list_slots 正常读取的对照，见 根因证据（历史本地产物：`test_driver_exception_and_utc_session_control-root-cause.json`，未随仓库发布）。

按同根因追加了删除、候选人可用列表和预约入口，三者也返回 500，失败后相关业务快照不变。真实 Uvicorn HTTP 服务上，先创建普通时段并成功列出，再创建该极端时段，整个本人列表变为 500，证明它不是 TestClient 或冻结时钟造成的假象。见 真实 HTTP 证据（历史本地产物：`test_minimal_witness_through_real_http_server-real-http.json`，未随仓库发布） 与 服务日志（历史本地产物：`real-http-boundary.txt`，未随仓库发布）。

定位：`backend/app/interview/schema.py:20`；`backend/app/interview/service.py:42`；`backend/app/interview/service.py:84`；`backend/app/interview/service.py:46`；`backend/app/candidate/service.py:349`；`backend/app/candidate/service.py:373`。

只记录后续修复方向：统一数据库返回时间域，或在清晰声明的支持范围外于创建阶段拒绝；选型和补丁留到总报告之后。没有改变应用连接时区、输入范围或异常处理，也没有手工删除项目数据。所有症状只计一个根因。

## 课件方法、记录更新和剩余范围

| 方法 | 课件依据 | 具体证据 |
|---|---|---|
| 等价类与精确边界 | L14 p.7–13 | 冻结时钟、微秒阈值、30 分钟、区间相接与包含、输入和日期上下文 |
| 蜕变测试 | L12 p.22–28 | 相同 UTC 时刻的多种偏移表示，比较约定的起止字段，不比较随机 ID |
| 前后条件、状态序列、失败原子性 | L13 p.19–26、45–52；L14 p.23–27 | 拒绝前后四表快照、四种已确认转换、提交失败回滚 |
| 独立判据与跨层观察 | L12 p.8–21 | 区间公式、预置固定 ID 的列表真值、API/数据库/真实 HTTP |
| 固定版本与隔离 | L10 p.8–20、29–52 | 原始归档、独立集群、完整命令、源码完整性 |

UTC 会话对照属于环境对照；数据库行锁同步属于测试 harness 的可控调度。没有将它们声称为 CPE 内部变体，没有进行 fuzzing、变异测试或形式证明。未采集代码覆盖率百分比。

已回填 常见问题与重点风险记录（历史本地产物：`常见问题与重点风险记录.md`，未随仓库发布），并向测试 skill 的常见问题参考补充“写入成功后检查返回时区与关联入口”的经验。原提交里缺少测试的 BL-G01 仍未修复；本轮外部测试只是补足检测证据，尚未提交到项目。

本轮覆盖新增模块 API/服务/数据库及所列高优先级交互；完整浏览器页面、其他匹配/CRUD、一般认证安全矩阵和更多状态组合仍按后续阶段执行。Docker 与已有 5173 服务均未改动，未复测此前环境阻塞。

## 复现与完整性

原始命令、退出码和日志均保留：

```text
<project-python> run_stage.py initial
<project-python> run_stage.py replay <artifact-dir>/test_slots_date_boundary.py
<project-python> run_stage.py related-paths <artifact-dir>/test_slots_date_paths.py
<project-python> run_stage.py precision-legacy <artifact-dir>/test_slots_additional_boundaries.py
```

默认 runner 以全新数据库启动；再次使用同一标签时仍由每个用例清空隔离库。原项目源码和既有测试保持固定 SHA。四批临时 PostgreSQL 实例、真实 HTTP 子进程均已关闭；数据库目录只含本轮合成数据，保留用于追溯。

- 结构化发现（历史本地产物：`findings.json`，未随仓库发布）
- 汇总结果（历史本地产物：`execution-summary.json`，未随仓库发布）
- 初轮（历史本地产物：`initial-summary.json`，未随仓库发布）、最小边界复核（历史本地产物：`replay-summary.json`，未随仓库发布）、关联入口（历史本地产物：`related-paths-summary.json`，未随仓库发布）、精度和旧数据（历史本地产物：`precision-legacy-summary.json`，未随仓库发布）
- 初轮源码完整性（历史本地产物：`initial-integrity.json`，未随仓库发布）、复核完整性（历史本地产物：`replay-integrity.json`，未随仓库发布）、关联入口完整性（历史本地产物：`related-paths-integrity.json`，未随仓库发布）、补测完整性（历史本地产物：`precision-legacy-integrity.json`，未随仓库发布）
