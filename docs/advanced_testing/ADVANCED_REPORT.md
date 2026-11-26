# 高级测试与验证报告（P0–P12）

> 本文件由 [`tests/advanced/report.py`](../../tests/advanced/report.py) 从本次运行的 JSON / JUnit 产物自动生成。**不要手工修改数字**；改测试或改实现后重新运行生成命令即可。

- 源码版本：`f28b27974352cd121d0a3f64ac7f859f098301f1`（分支 `test/P11`）
- 运行完成时间：2026-11-26T06:27:00.359497+00:00
- 生成时间：2026-11-26T06:33:42+00:00
- 产物目录：`D:\Study\Y4 - CSC4801\_evidence\P11\final-all-3`
- 确定性：`PYTHONHASHSEED=4801`，Hypothesis `derandomize=True`，`random.Random(4801)`；所有规模有上限。

## 1. 一页摘要

本报告汇总本仓库在必测单元套件（`python tests/run_tests.py`）之外叠加的 13 项高级测试与验证技术：运行器基线、属性测试、有状态模型、有限轨迹 LTL、Z3 规格证明、有界模型检验与归纳、差分测试、变异测试、OpenAPI 属性模糊、蜕变/内蜕变、LLM 盲测实验、安全扫描和覆盖率汇总。本次 `run.py all` 请求 9 个模式，9 个 exit 0；模式自身耗时合计 1121.9s。合并覆盖率为 98.76% statements / 96.97% branches；单元套件分支覆盖 94.44%，CI 门槛取 `90%`。

所有证据都写在 checkout 之外的一次性目录；数据库是 `initdb` 新建的 loopback 临时集群（CI 中由 `postgres:15` service 提供并逐库创建/删除），测试进程不访问外网、不读 `backend/.env` 的真实值。数字来自下面的产物 JSON，正文中的“亮点/局限”引用对应详细文档中的具体反例、表格与自检记录。

### 1.1 总表

| 技术 | 讲义出处 | 规模 | 结果 | 证据文档 |
| --- | --- | --- | --- | --- |
| P0 运行器骨架 | L12 测试层次 / L13 方法 | 9 个模式 | 9/9 exit 0；一次性 PG；产物出仓 | [ADVANCED_BASELINE.md](ADVANCED_BASELINE.md)、[README](../../tests/advanced/README.md) |
| P1 属性测试（必测套件） | L13 性质测试 | 9 条性质 × 200 examples；必测 252 例 | 252 passed / 0 failed；独立 Fraction oracle | [test_matching_properties.py](../../tests/unit/test_matching_properties.py) |
| P2 有状态模型 | L12/L13 状态机 | 25 examples / 300 步 / 23 条去重轨迹 | 5 条不变量在每步后检查，0 失败 | [stateful/test_booking_state_machine.py](../../tests/advanced/stateful/test_booking_state_machine.py) |
| P3 有限轨迹 LTL | L13 slides 46–52 | L1–L5 于 25 条轨迹 / 300 步；自检 232 例 | 5/5 性质全部满足；relax 链 0/25 → 25/25 | [LTL.md](LTL.md) |
| P4 匹配规格证明（Z3） | L13 Hoare 三元组 | 7 条证明 + 2 条负向；1,024 对规格/代码对拍 | 7 unsat / 2 sat；mismatch 0 | [FORMAL_MATCHING.md](FORMAL_MATCHING.md) |
| P5 预约 BMC + k-归纳 | L13 propose→check→counterexample→repair | k=6 步；18 条记录 | 4 条 BMC unsat；3 个可达性见证 sat；归纳义务全部 unsat | [FORMAL_BOOKING.md](FORMAL_BOOKING.md) |
| P6 差分测试 | L12 差分 oracle | 600 对 SQL/Python；600 对双视图 | SQL mismatch 0；tie groups 55 | [differential/test_matching_sql.py](../../tests/advanced/differential/test_matching_sql.py) |
| P7 变异测试 | L13 slide 17 / L14 slide 28 | 304 个变异体 / 5 个文件 | score 93.71%；survived 19，suspicious 2 | [MUTATION.md](MUTATION.md) |
| P8 OpenAPI 属性模糊 | L14 slide 29 | 28 个操作 / 864 请求 | 5xx 0；real_defect 0；schema_drift 793 | [APIFUZZ.md](APIFUZZ.md)、[findings/P8.md](findings/P8.md) |
| P9 蜕变/内蜕变 | L12 slides 29–41 | 5 条蜕变工作流 + 5 条防护层 + 2 个自检 | I2 5 轮一致；自检全部变红 | [INTRAMORPHIC.md](INTRAMORPHIC.md) |
| P10 LLM 盲测 | L14 Exercise 1/3 | 生成 124 个 case；5 个手写变异体 | 123 passed / 1 skipped / 0 failed；生成 5/5 vs 手写 3/5 | [LLM_TEST_EXPERIMENT.md](LLM_TEST_EXPERIMENT.md) |
| P12 依赖与密钥扫描 | L14 安全 | 全历史 69 commits；12 个唯一 advisory | 0 泄露；0 待处理 advisory（1 条有理由接受） | [SECURITY_SCANS.md](SECURITY_SCANS.md) |
| P11 覆盖率与汇总 | L12 覆盖率 | 5 组套件；1,045 statements | combined 98.76% statements / 96.97% branches；unit branch gate 90% | 本报告 |

### 1.2 模式回执与 JUnit 统计

| 模式 | 用例 | 通过 | 失败 | 跳过 | 回执 | 耗时 |
| --- | --- | --- | --- | --- | --- | --- |
| smoke | 2 | 2 | 0 | 0 | exit 0 | 5.58s |
| stateful | 1 | 1 | 0 | 0 | exit 0 | 43.29s |
| ltl | 235 | 235 | 0 | 0 | exit 0 | 47.28s |
| formal | 36 | 36 | 0 | 0 | exit 0 | 4.91s |
| differential | 4 | 4 | 0 | 0 | exit 0 | 26.27s |
| intramorphic | 14 | 14 | 0 | 0 | exit 0 | 12.47s |
| apifuzz | — | — | — | — | exit 0 | 18.68s |
| mutation | — | — | — | — | exit 0 | 766.41s |
| coverage | — | — | — | — | exit 0 | 197.00s |

> 入口型（`entry.py`）模式没有 pytest JUnit；它们的用例数/请求数在各自一节从业务 JSON 读取。`run.py` 的模式回执来自 `<out>/<mode>/result.json`。

## 2. 方法论

**独立 oracle。** 每条 oracle 都由需求文字、手算或独立实现得到，不调用被测实现生成期望值：P1 用 `Fraction` 与集合交重写 FP-MATCH-1；P4 的 Z3 编码不导入 `app.*`，1024 对子集另行与真实 `match_score` 对拍；P6 的 SQL 打分不导入生产匹配模块；P8 的期望状态矩阵从 FP-AUTH-3/SPEC 手写。

**每个 oracle 至少做一次“故意引入错误 → 测试变红 → 恢复”。** P1 用仓库外 `-p` 插件替换实现；P2 故意把“已预约时段可删除”预测为 204，并要求 Hypothesis 给出最小操作序列；P3 在内存里替换检查器运算符；P4 把 `int_div` 改成乘法近似；P5 用 `Variant` 逐条删除守卫；P6 用 monkeypatch 改候选视图分数；P7 的 304 个变异体本身就是 304 次受控错误注入；P8 在 `finally` 中恢复 4 个受控回归；P9 直接删除数据库唯一约束（比吞掉异常更忠实）；P10 用 5 个手写变异体与 F3 不安全渲染对照。生产代码没有被修改，所有临时变异都在仓库外或进程内完成。

**空真与可达性检查。** P3 为每条 LTL 性质单独统计前件触发实例数，并显式报告“非空真轨迹”；P5 用 3 个可达性见证证明 BMC 的 `unsat` 不是空模型，用 M5 展示“守卫恒假时 BMC 仍 unsat”的假绿风险。P4 的 N1/N2 是两个故意为假的负向查询，`sat` 才说明编码能判错。

**确定性。** `PYTHONHASHSEED=4801` 由 `run.py` 传给所有子进程；Hypothesis 统一 `derandomize=True`、`deadline=None`；随机数据用 `random.Random(4801)`；每个模式的规模有上限（属性 200、状态机 25×12 步、模糊读 20/写 10、变异 304 个）。P3 的 relax 链与 P2 的轨迹逐字节可复现。

**安全边界。** `--out` 在 checkout 内会被 `run.py` 拒绝；数据库只允许 `127.0.0.1`/`localhost`/`::1`；`ADVANCED_PG_URL` 的密码不会写进 summary；日志和 evidence 不打印 Cookie/CSRF/密码/哈希；测试不访问外网。

## 3. 逐项技术

每小节按“讲义出处 / 要回答的问题 / 命令 / 关键数字 / 亮点 / 局限 / 详细文档”组织；关键数字表第三列是产物相对路径，数字由本脚本读取，不手填。

### 3.0 P0 运行器骨架：自动发现、一次性 PG、产物出仓

**讲义出处**：L12（测试层次与可复现运行）/ L13（测试方法与工具）。

**要回答的问题**：高级套件能否一条命令复现，并且不污染仓库、共享数据库或管理员环境？

**命令**：`python tests/advanced/run.py all --out <仓库外新目录>`；本次 `run.py` 实际模式列表：`apifuzz`, `coverage`, `differential`, `formal`, `intramorphic`, `ltl`, `mutation`, `smoke`, `stateful`。

| 指标 | 值 | 产物 |
| --- | --- | --- |
| 发现的模式数 | 9 | `summary.json` |
| 一次性 PG 启动 | yes | `summary.json` |
| PG 模式 | disposable | `summary.json` |
| 模式总耗时 | 1121.90s | `summary.json` |
| git 工作区干净 | no | `summary.json` |

**亮点**：模式由目录自动发现（`entry.py` 或 pytest、`SLOW`、`NEEDS_DB` 三个标记），新增模式不需要改 `run.py` 或 CI；`run.py` 用 `initdb` 在随机端口新建仅 loopback、trust 认证的临时集群，结束后删除；`--out` 必须在 checkout 外且新目录/空目录，避免把含合成会话令牌的日志提交进仓库；`support/pg.py::validate_loopback_url` 拒绝非 loopback 主机。

**局限**：`run.py` 不设模式超时，靠调用方/CI 的 `timeout-minutes` 兜底；`entry.py` 模式不加载共享 `conftest.py`，需要自己建库/迁移/清理；各模式独立子进程，无法共享 Python 状态（这是隔离性，也是无法复用昂贵对象的原因）。

**详细文档**：[ADVANCED_BASELINE.md](ADVANCED_BASELINE.md)、[README](../../tests/advanced/README.md)。

### 3.1 P1 属性测试：FP-MATCH-1 的规格性质

**讲义出处**：L13（性质测试与独立 oracle）。

**要回答的问题**：匹配分数与技能归一化在任意合法输入上是否满足需求，而不只是四个示例行？

**命令**：`python tests/run_tests.py --junitxml=<仓库外>/unit.xml`。

| 指标 | 值 | 产物 |
| --- | --- | --- |
| 必测套件用例 | 252 | `unit.xml` |
| 必测套件失败 | 0 | `unit.xml` |
| 属性测试用例 | 9 | `unit.xml` |
| 每个性质规模 | 200 examples | `test_matching_properties.py` |
| oracle | Fraction + 集合交 + floor | `test_matching_properties.py` |

**亮点**：9 条性质覆盖返回值范围/类型、独立 oracle、空需求 100、排列/重复/空白不变性、无关技能不变、单调性、归一化幂等与输入不被原地修改。自检时把 `//` 改成 `round()`，Hypothesis 自动缩小出最小反例`['0','00']` vs `['0','00','000']`（floor 66 vs round 67）；把 `.strip()` 删除时生成测试单独杀死对应变异体。属性测试已进入**必测** `python tests/run_tests.py`，不是可选脚本。

**局限**：每个性质是有界随机采样（200 examples），不是穷举证明；归一化按需求的 `str.lower()` 解释（`ß`/`İ` 不折叠）；不覆盖数据库、路由或前端渲染。

**详细文档**：[test_matching_properties.py](../../tests/unit/test_matching_properties.py)。

### 3.2 P2 有状态模型：预约生命周期

**讲义出处**：L12/L13（状态机与模型化测试）。

**要回答的问题**：在任意合法/非法操作序列下，预约生命周期的 5 条不变量是否始终成立？

**命令**：`python tests/advanced/run.py stateful`。

| 指标 | 值 | 产物 |
| --- | --- | --- |
| examples | 25 | `stateful/summary.json` |
| 总步数 | 300 | `stateful/summary.json` |
| 轨迹文件 / 去重 | 25 / 23 | `stateful/summary.json` |
| 成功预约 | 11 | `stateful/summary.json` |
| 删除已预约时段被拒 | 2 | `stateful/summary.json` |
| 状态改成功 | 75 | `stateful/summary.json` |
| 失败数 | 0 | `stateful/junit.xml` |

**亮点**：每步都是**真实 HTTP 调用 + 真实 SQL 断言**，不是会话替身：不变量 1 直接数 `booking` 行，不变量 2 检查已预约时段不出现在可用列表，不变量 3 检查预约只在 `Interviewing` 时创建且状态变化后保留，不变量 4 用独立 FP-MATCH-1 oracle 核对雇主申请人列表的分数与排序，不变量 5 检查被拒绝操作不改变任何表行数。`perform` 用 `hypothesis.strategies.randoms()` 在**适用操作**间均匀抽取，避免 Hypothesis 的规则采样偏置把一半步骤分给同一条廉价规则；这个 draw 仍在 Hypothesis 数据流里，所以 `derandomize=True` 下轨迹逐字节可复现，shrinking 也仍然有效。两个自检分别验证“已预约时段可删除”的错误模型预测和“可用列表包含已预约时段”的 monkeypatch 都会变红，并要求 Hypothesis 给出最小操作序列。

**局限**：25 个 example、每例最多 12 步是**有界随机探索**，不是穷举；规则权重与 seed 决定轨迹空间；删除已预约时段的成功分支在本次轨迹中只触发了 2 次拒绝，覆盖较薄；真实并发由数据库行锁/唯一约束保证，状态机是顺序执行。

**详细文档**：模块 docstring [test_booking_state_machine.py](../../tests/advanced/stateful/test_booking_state_machine.py)。

### 3.3 P3 有限轨迹 LTL：空真检查与 relax/restrict

**讲义出处**：L13 slides 46–52（LTL、relax/restrict 精化）。

**要回答的问题**：P2 产生的业务轨迹是否满足 FP-SCHED/FP-CAN 的时序性质？检查器本身是否能判出违规？

**命令**：`python tests/advanced/run.py ltl`。

| 指标 | 值 | 产物 |
| --- | --- | --- |
| 轨迹文件 / 去重 | 25 / 23 | `ltl/ltl_results.json` |
| 步数 / 去重步数 | 300 / 276 | `ltl/ltl_results.json` |
| 性质数 | 5 | `ltl/ltl_results.json` |
| selftest 用例 | 232 | `ltl/junit.xml` |
| refine 链 | F 0/25 → F' 10/25 → F'' 10/25 → F''' 25/25 | `ltl/refinement.json` |

**关键数字（逐性质，来自 `ltl/ltl_results.json`）**：

| 性质 | 标题 | 满足/轨迹 | 非空真轨迹 | 前件触发实例 |
| --- | --- | --- | --- | --- |
| `L1` | a booked slot never becomes available again | 25/25 | 11/25 | 11 |
| `L2` | a booking is created only while the application is Interviewing | 25/25 | 11/25 | 11 |
| `L3` | an existing booking never disappears | 25/25 | 11/25 | 11 |
| `L4` | a booked slot is never deleted | 25/25 | 11/25 | 11 |
| `L5` | an application never disappears | 25/25 | 25/25 | 43 |

**亮点**：自研有限轨迹 LTL 支持 `G/F/X/WX/U`、布尔连接词、有限域`forall/exists` 与参数化原子；每个运算符至少 3 条满足 + 3 条违反，`G(p -> X q)` / `p U q` 各穷举 3 步的 64 种真值组合，`F G p` 穷举 8 种。**空真检查**不是口号：每条性质单独统计前件触发实例（L1/L4 为 11 个 booking、L5 为 43 个申请），并列出“非空真轨迹 < 5”的警告。`explain` 给出第一个违规的 trace index、step、props、binding 与原因。relax 链用 `random.Random(4801)` 从 0/25 精化到 25/25，restrict 探针 R0/R1 又分别暴露 15/1 条新反例，说明“放宽到 100%”不等于性质已无约束。

**局限**：只支持有限轨迹，不支持无限轨迹/lasso/公平性；25 条轨迹的有界随机探索不是穷尽证明；量词域只来自轨迹中出现过的值，是依赖 P2 原子词汇表的有限近似；L4 的“删除已预约时段被拒”分支只有 2 次拒绝尝试，主要靠 P2 不变量与 P5 模型检验补强。

**详细文档**：[LTL.md](LTL.md)。

### 3.4 P4 匹配规格的 Z3 证明：Hoare 三元组与有界对拍

**讲义出处**：L13（Hoare 三元组、SMT 与规格证明）。

**要回答的问题**：FP-MATCH-1 的规格公式是否满足 7 条性质？真实 `match_score` 在有限全集上是否与规格一致？

**命令**：`python tests/advanced/run.py formal`。

| 指标 | 值 | 产物 |
| --- | --- | --- |
| T1–T7 | 7 条，7 unsat | `formal/matching_theory.json` |
| N1–N2 负向 | 2 条，2 sat | `formal/matching_theory.json` |
| 全集大小 / 子集对 | 5^5 / 1,024 | `formal/spec_to_code_pairs.json` |
| 规格/代码 mismatch | 0 | `formal/spec_to_code_pairs.json` |
| Z3 编码 mismatch | 0 | `formal/spec_to_code_pairs.json` |

**关键数字（逐条记录，来自 `formal/matching_theory.json`）**：

| ID | 标题 | 结果 | 单次查询 |
| --- | --- | --- | --- |
| `T1` | 0 <= score <= 100 | unsat | 0.013170s |
| `T2` | k = n -> score = 100 and k = 0 -> score = 0 | unsat | 0.003056s |
| `T3` | floor definition: score*n <= 100k < (score+1)*n | unsat | 0.006057s |
| `T4` | k1 <= k2 -> score(k1) <= score(k2) for the same n | unsat | 0.008484s |
| `T5` | score = 100 iff R subset C | unsat | 0.004984s |
| `T6` | adding x not in R to C leaves the score unchanged | unsat | 0.015014s |
| `T7` | n = 2 and k = 1 -> score = 50 | unsat | 0.000633s |
| `N1` | floor(100k/n) = round_half_up(100k/n) | sat | 0.018224s |
| `N2` | score = floor(100*|C∩R| / |C|) | sat | 0.009322s |

**亮点**：每个测试上方用 Hoare 三元组写 `{P} C {Q}`，并与 FP-MATCH-1 条款逐条对应；T1–T7 的否定全部 `unsat`，N1 的 floor/round 反例是`n=6, k=4`：floor 66 vs round 67，N2 的分母误用反例证明“分母是 |R| 不是 |C|”不是文字游戏。`|U|=5` 的 1024 个 `(C,R)` 对同时比较真实实现、Z3 编码与需求文字三方一致，0 mismatch。自检把 `int_div` 改成乘法后 T1/T2/T3/T5/T7 变 `sat` 并报出真实反例，恢复后全绿。

**局限**：证明对象是 `encoding.py` 的**规格公式**，不是 Python 代码；代码只通过 `|U|=5` 的 1024 对有界穷举与规格关联；归一化不在 SMT 模型内；Hoare 三元组是语义层描述，没有经过证明助手检查。

**详细文档**：[FORMAL_MATCHING.md](FORMAL_MATCHING.md)。

### 3.5 P5 预约状态机：BMC + k-归纳

**讲义出处**：L13（BMC、k-归纳与 propose→check→counterexample→repair）。

**要回答的问题**：B1–B4 在 6 步以内有没有反例？能否从“6 步内无”提升到“任意步数成立”？

**命令**：`python tests/advanced/run.py formal`（与 P4 同一模式）。

| 指标 | 值 | 产物 |
| --- | --- | --- |
| BMC 步数 | 6 | `formal/booking_bmc.json` |
| 记录数 | 18 | `formal/booking_bmc.json` |
| BMC 性质 unsat | 4 | `formal/booking_bmc.json` |
| 负向控制 sat | 5 | `formal/booking_bmc.json` |
| 可达性见证 sat | 3 | `formal/booking_bmc.json` |
| 归纳义务 unsat | 5 | `formal/booking_bmc.json` |

**关键数字（逐记录，来自 `formal/booking_bmc.json`）**：

| ID | 类别 | 结果 | 变体 |
| --- | --- | --- | --- |
| `B1` | property | unsat | unmodified |
| `B2` | property | unsat | unmodified |
| `B3` | property | unsat | unmodified |
| `B4` | property | unsat | unmodified |
| `B1` | negative_control | sat | allow_booking_taken_slot |
| `B3` | negative_control | sat | skip_delete_booking_guard |
| `B2` | negative_control | sat | skip_status_guard |
| `B4` | negative_control | sat | clear_booking_on_status_change |
| `reach-booking` | reachability | sat |  |
| `reach-delete` | reachability | sat |  |
| `reach-status-change` | reachability | sat |  |
| `IND-base` | induction_base | unsat | unmodified |
| `IND-step` | induction_step | unsat | unmodified |
| `IND-strengthen-rejected` | rejected_candidate | sat | unmodified |
| `IND-B2` | single_step | unsat | unmodified |
| `IND-B4` | single_step | unsat | unmodified |
| `IND-persist` | single_step | unsat | unmodified |
| `IND-N1` | negative_control | sat | allow_booking_taken_slot |

**亮点**：BMC（k=6）与 k-归纳（k=1）共用同一份守卫/效果编码，避免两套编码悄悄分叉；`include_initial=False` 让归纳步对**任意状态**量化，这是“有界 → 无界”的关键。3 个可达性见证（预约、删除、状态改变）都是`sat`，证明 `unsat` 不是空模型；M5 把 `book_guard` 改成恒假后 BMC 仍`unsat`，暴露“没有可达性见证就可能空真”的风险。被拒绝的不变式加强 `Inv_A` 得到 `sat` 反例（`set_status(a0, Rejected)` 后预约保留但状态离开 `Interviewing`），正好对应讲义 L13 的 propose→check→counterexample→repair；最终 `Inv = B1 ∧ B3状态形式` 一次归纳步即 `unsat`。

**局限**：证明对象是 `booking_model.py` 的抽象转移系统；守卫是人工从代码抄写的，没有自动精化和模型/代码一致性证明；时间、30 分钟、跨雇主、职位保留、版本冲突都被抽象为恒真/不建模；并发由数据库行锁 + 唯一约束保证，顺序转移系统无法表达；`基例 + 归纳步 ⇒ 所有可达状态`是元层面论证，不是机器检查的定理。

**详细文档**：[FORMAL_BOOKING.md](FORMAL_BOOKING.md)。

### 3.6 P6 差分测试：Python 打分 vs SQL 打分

**讲义出处**：L12（差分测试与独立 oracle）。

**要回答的问题**：同一批数据库行，用独立 SQL 算出的 FP-MATCH-1 分数是否与生产 `match_score` 一致？候选人视图与雇主视图对同一 (C,R) 是否一致？

**命令**：`python tests/advanced/run.py differential`。

| 指标 | 值 | 产物 |
| --- | --- | --- |
| SQL/Python 对数 | 600 | `differential/differential.json` |
| SQL mismatch | 0 | `differential/differential.json` |
| 双视图对数 | 600 | `differential/cross-view.json` |
| 申请行 | 600 | `differential/cross-view.json` |
| tie groups | 55 | `differential/differential.json` |
| 不同分数 / 100 分 / 0 分 | 14 / 62 / 102 | `differential/differential.json` |

**亮点**：数据经**真实 HTTP API** 写入（技能已经过生产归一化），SQL 侧是从需求文字独立写出的 `floor(100*overlap/required)`，不导入生产匹配模块；600 对 `(candidate, job)` 全部一致，0 mismatch。双视图测试让40 个候选人 × 15 个职位全部投递，600 对候选人仪表盘与雇主申请人列表分数一致，并用手写排序键检查 40 + 15 = 55 个大小写平局组；两个常驻自检分别 monkeypatch 候选视图分数和排序键，要求 oracle 变红后恢复。

**局限**：600 对是有界随机数据集（40×15，`random.Random(4801)`），不是穷举；SQL 与 Python 只比较归一化后的集合语义，不重复测试归一化本身；只覆盖 `match_score`，不覆盖推荐排序的全部业务规则。

**详细文档**：[test_matching_sql.py](../../tests/advanced/differential/test_matching_sql.py)、[test_cross_view.py](../../tests/advanced/differential/test_cross_view.py)。

### 3.7 P7 变异测试：必测套件的缺陷检出能力

**讲义出处**：L13 slide 17（变异测试引擎）/ L14 slide 28（变异分数与幸存者归因）。

**要回答的问题**：`tests/unit` 能检出多少人为注入的代码缺陷？哪些幸存者是等价变异、哪些是缺测试？

**命令**：`python tests/advanced/run.py mutation`（SLOW；自研 AST 引擎）。

| 指标 | 值 | 产物 |
| --- | --- | --- |
| 变异体总数 | 304 | `mutation/mutation-result.json` |
| killed / survived | 283 / 19 | `mutation/mutation-result.json` |
| suspicious | 2 | `mutation/mutation-result.json` |
| 计分分母 | 302 | `mutation/mutation-result.json` |
| 并行度 | 7 | `mutation/mutation-result.json` |
| mutation score | 93.71% | `mutation/mutation-result.json` |
| 保守下界 | 93.09% | `mutation/mutation-result.json` |
| backend/app 未被改动 | yes | `mutation/mutation-result.json` |

**按文件（来自 `mutation/mutation-result.json`）**：

| 文件 | 变异体 | killed | survived | 分数 |
| --- | --- | --- | --- | --- |
| `app/employer/matching.py` | 7 | 7 | 0 | 100.00% |
| `app/users/service.py` | 51 | 51 | 0 | 100.00% |
| `app/candidate/service.py` | 126 | 117 | 9 | 92.86% |
| `app/employer/service.py` | 77 | 73 | 4 | 94.81% |
| `app/interview/service.py` | 43 | 35 | 6 | 85.37% |

**亮点**：由于 mutmut 3.7 在原生 Windows 上结构性不可用（依赖 `os.fork` 与 `resource.setrlimit`），P7 按任务允许的降级方案实现了一个**自研 AST 变异引擎**（L13 slide 17 的思想），覆盖比较翻转、`//`→`/`、`and↔or`、常量 ±1、`raise`→`pass`、`return X`→`return None` 六类算子；每个变异体固定 30s 超时，只在 `$ADVANCED_OUT/mutation/work/` 的副本里注入，前后对 `backend/app` 做 SHA-256 快照。三列对比为 **60.93% → 60.93% → 93.71%**：P1 属性测试把 `tests/unit` 从 176 例增加到 185 例，但**单独新增 killed = 0**；全部 99 个新增 kills 来自补强测试。报告没有掩盖这个事实，而是把中间列单独计分，说明属性测试的价值在规格性质而非这套 6 类算子的杀伤力。

**局限**：变异分数是**同口径前后对比**，不是 mutmut 全量算子集的横向分数；19 个幸存者中有 10 个属于“仅真实 SQL 可观测”（`LIMIT`/`JOIN ON`），应由集成/差分覆盖；2 个 suspicious 是导入期错误，保守地不计入分母；变异范围只覆盖 5 个文件。本次证据运行记录 `jobs=7`；在并发过高导致每个变异体 30s 固定超时出现假 timeout 的环境里，可用 `PYTHON_CPU_COUNT` 限制并行度后重跑，变异体集合、判定逻辑与最终 killed/survived 分类不变。

**详细文档**：[MUTATION.md](MUTATION.md)、[tests/unit/test_mutation_hardening.py](../../tests/unit/test_mutation_hardening.py)。

### 3.8 P8 OpenAPI 属性模糊：从真实缺陷到修复重跑

**讲义出处**：L14 slide 29（属性测试 → 真实缺陷 → 修复回归）。

**要回答的问题**：自动生成的 OpenAPI 文档能否驱动有界、可复现的 API 属性测试？认证/所有权矩阵是否符合 FP-AUTH-3？有没有未声明的 5xx？

**命令**：`python tests/advanced/run.py apifuzz`（SLOW）。

| 指标 | 值 | 产物 |
| --- | --- | --- |
| OpenAPI 操作 | 28 | `apifuzz/report.json` |
| 总请求数 | 864 | `apifuzz/report.json` |
| 未声明 5xx | 0 | `apifuzz/report.json` |
| real_defect | 0 | `apifuzz/report.json` |
| schema_drift | 793 | `apifuzz/report.json` |
| test_config | 0 | `apifuzz/report.json` |
| 自检通过 | yes | `apifuzz/report.json` |

**逐轮状态分布（来自 `apifuzz/report.json`）**：

| 轮次 | 操作 | 请求 | 状态分布 | 失败记录 |
| --- | --- | --- | --- | --- |
| anonymous | 28 | 410 | 200:9, 400:1, 401:398, 422:2 | 28 |
| candidate | 23 | 227 | 200:6, 403:133, 404:80, 409:1, 422:7 | 19 |
| employer | 23 | 227 | 200:6, 201:7, 403:113, 404:67, 422:34 | 16 |

**亮点**：**864 个请求、0 个 5xx**。匿名轮所有受保护操作都先返回 401（`422-before-auth=0`）；候选/雇主轮错角色请求全部 403。更重要的是一条真实缺陷的完整闭环：模糊测试发现 `POST /employer/interview-slots` 的业务 422 返回字符串 `detail`，但 OpenAPI 声明的是 `HTTPValidationError` 数组，Schemathesis `response_schema_conformance` 报 `ST108`（10 个写样例中 9 个命中）；写入 `findings/P8.md` 后由队友提交 `0ea7223` 修复，回归测试 `test_fp_sched_1_openapi_422_documents_business_and_validation_shapes` 覆盖两种响应体；P11 重跑 `real_defect` 从 **9 → 0**。4 个受控自检（错误角色矩阵、服务端 500、响应 schema、状态码）都在 `finally` 中恢复，证明 oracle 会变红而不是恒真。

**局限**：操作级、非状态序列（多步工作流由 P2/P9 覆盖）；读 20/写 10 是有界采样，零参数 GET 可能提前耗尽；随机 UUID 只覆盖拒绝路径；ASGI 直连不验证端口/代理/TLS；**793 个 schema drift 不是 793 个业务 bug**，而是 FastAPI 未声明 FP-AUTH-3 要求的 401/403/404 与 SPEC 的 400/409，报告按检查/状态分别计数，没有用过滤器静默吞掉。

**详细文档**：[APIFUZZ.md](APIFUZZ.md)、[findings/P8.md](findings/P8.md)。

### 3.9 P9 蜕变与内蜕变：规则由哪一层保证

**讲义出处**：L12 slides 29–41（蜕变测试与内蜕变）。

**要回答的问题**：工作流层的语义等价变换是否保持可观察结果？关掉某条防护层后，规则会由哪一层兜底、还是直接失效？

**命令**：`python tests/advanced/run.py intramorphic`。

| 指标 | 值 | 产物 |
| --- | --- | --- |
| 蜕变工作流 | 5 | `intramorphic/M1..M5.json` |
| 防护层规则 | 5 | `intramorphic/defense_layers.json` |
| I2 并发轮数 | 5 | `intramorphic/defense_layers.json` |
| I2 每轮单赢家 | yes | `intramorphic/defense_layers.json` |
| I1 自检 red | yes | `intramorphic/defense_layers.json` |
| I3 自检 red | yes | `intramorphic/defense_layers.json` |

**关键数字（来自 `intramorphic/defense_layers.json`）**：

| 规则 | 内容 | 关闭的层 | 结论 |
| --- | --- | --- | --- |
| `I1` | a slot can be booked only once (FP-SCHED-3) | application_precheck | database unique constraint is a sufficient backstop; the application precheck is not the only layer |
| `I2` | two concurrent bookings of one slot have exactly one winner (FP-SCHED-3) | row_lock (Select.with_for_update is a no-op) | the database unique constraint alone still produces exactly one winner; the row locks are not the only line of defence |
| `I3` | a candidate may apply to the same job only once (FP-CAN-3) | application_precheck | the database unique constraint is a sufficient backstop; the application precheck is not the only layer |
| `I4` | match_score is insensitive to the order of the list returned by normalize_skills (FP-MATCH-1) | normalize_skills order (returns the list reversed) | the set-based algorithm makes normalization order irrelevant; this is a property of the matching implementation, not a separate check |
| `I5` | deleting a job with applications or interview slots must fail with 409 and leave dependents unchanged (FP-EMP-2) | application_precheck | single application-layer check; the database does not block a soft delete |

**蜕变关系（M1–M5，来自 `intramorphic/M*.json`）**：

| ID | 关系 | 可观察结果不变 |
| --- | --- | --- |
| `M1` | slot-before-apply == apply-before-slot for availability | yes |
| `M2` | unrelated rows leave the original candidate's relative recommendation order and availability unchanged | yes |
| `M3` | required-skill spelling variants preserve score and order | yes |
| `M4` | resume_text is not a matching input | yes |
| `M5` | Interviewing -> Rejected -> Interviewing without a booking restores exactly the same availability set | yes |

**亮点**：一张“规则 → 应用检查 → 行锁 → 数据库约束 → 关掉后会怎样”的总表，把“哪一层在保证规则”变成可观察实验。I2 用两个真实线程/独立 Session 和两个 Barrier 做并发：两个请求都进入 `book`、都观察到时段空闲后才允许插入，去掉全部行锁后 5 轮仍是 1×201 + 1×409、每轮 1 行 `booking`、每轮 1 次 `uq_booking_slot` 冲突——说明唯一约束单独即可保证单赢家，行锁负责减少竞争。I1 的自检比原方案更正确：没有 monkeypatch 吞掉 `IntegrityError`（那不能让 PostgreSQL 保存第二行），而是在一次性库里 `DROP CONSTRAINT`，观察第二次预约真的返回 201、预约表 2 行，然后恢复约束。I3 同样验证重复投递；I5 如实记录“职位依赖检查只在应用层”的单层防护事实，因为正常路径符合需求，所以不记业务缺陷。

**局限**：I2 的并发窗口由 Barrier 构造，不等于生产负载下的随机交错；monkeypatch 变体只覆盖 5 条规则；I5 是事实记录而非 bug；内蜕变回答“哪层保证”，不回答“测试能否杀死变异体”。

**详细文档**：[INTRAMORPHIC.md](INTRAMORPHIC.md)。

### 3.10 P10 LLM 盲测：生成测试 vs 手写测试

**讲义出处**：L14 Exercise 1/3（AI 生成测试、断言质量与变异杀伤力）。

**要回答的问题**：LLM 在只读契约、未看实现的情况下生成的测试质量如何？与手写测试相比，断言杀伤力和分区覆盖有什么差异？

**命令**：`python tests/advanced/experiments/llm_blind/run_experiment.py --out <仓库外>`；变异矩阵 `python .../mutation/run_mutants.py --out <仓库外>`。

| 指标 | 值 | 产物 |
| --- | --- | --- |
| 生成 case 总数 | 124 | `llm_blind/results.json` |
| passed / skipped / failed | 123 / 1 / 0 | `llm_blind/results.json` |
| 生成测试杀变异体 | 5/5 | `llm_blind/results.json` |
| 手写测试杀变异体 | 3/5 | `llm_blind/results.json` |
| 冻结 commit | `c0859d0208fd5c20c2fa90e786538db8f6732bb8` | `llm_blind/results.json` |

**分区对比（来自 `llm_blind/results.json`）**：

| 目标 | 生成 case | 手写 case | 独有发现 |
| --- | --- | --- | --- |
| F1 | 94 | 8 | generated tests alone kill the dropped-trim mutant; the handwritten normalization case mixes spaced and unspaced copies in one candidate list, so it cannot observe the missing strip |
| F2 | 19 | 32 | generated tests alone kill the missing-job-check mutant |
| F3 | 11 | 3 |  |

**亮点**：盲测协议把“生成”与“运行/读实现”用 commit 顺序冻结（`c0859d0` 生成文件 → `467a6f2`/`e76641f` 只修 setup → 本报告收口）；冻结运行 F3 11/11 通过，F1 因生成器的 parametrize id 数错误在 collection 中断，F2 19/19 因合成 `User` 漏 `role` 被服务层正确拒绝，**三类都不是业务缺陷**。修正 setup 后 123 passed / 1 skipped / 0 failed。5 个手写变异体上生成测试 **5/5**、手写测试 **3/5**；两个幸存者暴露了手写断言的盲区（归一化用例混入不带空格副本，观察不到 `strip()` 被删除；`book` 拒绝矩阵缺少“职位不存在”），这两个缺口后来被 P7 的补强测试覆盖。F3 的负向自检把同一组转义断言应用到 `dangerouslySetInnerHTML` 的不安全渲染，必须被拒绝。

**局限**：生成器仍是 LLM，协议保证的是“没有读本仓库实现”，不是没有世界知识；主会话在契约阶段用 AST 额外读了 `book` 的 `raise` 子句（已在文档披露）；F2 用会话替身、F3 用 `renderToStaticMarkup`，都不证明真实事务/浏览器安全；5 个手写变异体只是抽样，完整全量对比未在本任务完成（见 §5）。

**详细文档**：[LLM_TEST_EXPERIMENT.md](LLM_TEST_EXPERIMENT.md)。

### 3.11 P12 依赖与密钥扫描

**讲义出处**：L14（验证与安全扫描）/ 课程安全要求 FP-SEC-4。

**要回答的问题**：全历史有没有真实密钥？运行时 Python 依赖与前端生产依赖有没有未归因的漏洞？

**命令**：独立 workflow `.github/workflows/security.yml`（gitleaks / pip-audit / npm audit）；本报告只链接文档，不重复运行扫描。

| 指标 | 值 | 来源 |
| --- | --- | --- |
| 全历史扫描 | 69 commits，0 泄露 | `SECURITY_SCANS.md` |
| Python 依赖 | 12 个唯一 advisory → 0 待处理 | `SECURITY_SCANS.md` |
| 接受的风险 | pytest PYSEC-2026-1845（有理由） | `SECURITY_SCANS.md` |
| 前端生产依赖 | 0 漏洞 | `SECURITY_SCANS.md` |

**亮点**：允许列表不是“一键变绿”，而是**路径 AND 值**：28 条 64 位十六进制 SHA-256 与 6 条测试夹具合成 `SECRET_KEY` 分别按精确路径 + 精确值抑制；在临时 git 仓库里把同一合成值放到允许路径之外仍被报告，非允许值的假 Token也仍被报告。P12b 删除 5 个未使用的 starter 包并升级 4 个包，12 个 advisory 归零；唯一接受的 pytest advisory 只影响测试工具的 UNIX `/tmp` 权限。

**局限**：gitleaks 是启发式扫描器，0 命中不是“绝对没有密钥”的证明；只由 merge resolution 引入的内容可能不在 `git log -p` diff 中；`pip-audit` 只扫运行时锁文件，`tests/advanced/requirements.txt` 的测试依赖不在范围内；可达性判断基于当前代码。

**详细文档**：[SECURITY_SCANS.md](SECURITY_SCANS.md)。

### 3.12 P11 覆盖率：分组测量与合并

**讲义出处**：L12（覆盖率、测试充分性与门槛）。

**要回答的问题**：必测单元套件、真实 PG 集成套件与三个高级模式分别覆盖了 `backend/app` 的多少语句/分支？合并后是多少？门槛取多少才不会被环境差异弄红？

**命令**：`python tests/advanced/run.py coverage`（SLOW、NEEDS_DB；入口为 `tests/advanced/coverage/entry.py`）。

| 套件 | 目标 | 用例 | 语句覆盖 | 分支覆盖 | 耗时 |
| --- | --- | --- | --- | --- | --- |
| `unit` | `tests/unit` | 230 | 92.63% | 94.44% | 12.911s |
| `integration` | `backend/tests` | 241 | 90.24% | 76.77% | 94.631s |
| `stateful` | `tests/advanced/stateful` | 1 | 74.74% | 41.41% | 43.29s |
| `differential` | `tests/advanced/differential` | 4 | 62.58% | 21.72% | 26.27s |
| `intramorphic` | `tests/advanced/intramorphic` | 14 | 78.37% | 46.46% | 12.47s |

| 指标 | 值 | 产物 |
| --- | --- | --- |
| 合并语句覆盖 | 98.76% | `coverage/coverage-summary.json` |
| 合并分支覆盖 | 96.97% | `coverage/coverage-summary.json` |
| 语句 covered/total | 1,032/1,045 | `coverage/coverage-summary.json` |
| 分支 covered/total | 192/198 | `coverage/coverage-summary.json` |
| 单元分支门槛（向下取 5 的倍数） | 90% | `coverage/coverage-summary.json` |

**亮点**：五组各自用独立 data file 运行 `coverage run --branch --source=backend/app`，最后用 coverage API `combine` 合并；单元组的 `branch_pct` 实测值向下取整到 5 的倍数得到 CI 门槛 `90%`。门槛只放在 `advanced` job：`pytest-cov`/`coverage` 只存在于 `tests/advanced/requirements.txt`，`unit` job 与 Docker 镜像都只装 `requirements.lock`，把 `--cov-fail-under` 加到必测命令会让镜像内测试失败。集成组用 `ADVANCED_PG_URL` 同时设置两个 `*_TEST_DATABASE_URL`，每组测试仍各自建/删一次性数据库。

**局限**：合并覆盖只衡量**被执行的行/分支**，不衡量断言质量（变异分数由 P7 负责）；`tests/unit` 组在本地包含 Node 渲染测试，CI 的 advanced job 因此也安装 Node 依赖；覆盖率受 Python/插件版本与导入路径影响，门槛取整到 5 的倍数是为了留出跨平台抖动余量，不是“越高越好”的分数竞赛。

**详细文档**：本报告；`tests/advanced/coverage/entry.py`。

## 4. 发现与闭环：P8 的 422 契约缺陷

这是本套件唯一写入 `findings/` 的业务契约缺陷，也是 L14 slide 29“发现问题 → 修复 → 回归”的完整闭环：

1. **需求**：FP-SCHED-1 要求拒绝非法时段；`SPEC.md` 的 `POST /employer/interview-slots` 声明 422，OpenAPI 该响应为 `HTTPValidationError`（`detail` 是数组）。
2. **测试**：P8 从实时 `/openapi.json` 生成请求，用 Schemathesis 的 `response_schema_conformance` 检查 422 响应体。
3. **失败**：10 个雇主写样例有 9 个返回 `{"detail": "Slot must start in the future"}`（字符串），`ST108 Response violates schema`。
4. **修复**：`backend/app/interview/router.py`（commit `0ea722364e18b921cbdacdcba879a9ef44a43c03`，PR #14 / merge `88a660e`）为 422 声明 `anyOf`，同时记录数组与字符串两种响应体；回归测试 `tests/unit/test_scheduling.py::test_fp_sched_1_openapi_422_documents_business_and_validation_shapes`。
5. **重跑**：P11 正式证据运行中 `apifuzz` 的 `real_defect` 为 0（修复前为 9）；剩余 `schema_drift` 793 是 FastAPI 未声明 401/403/404/400/409，不是本次缺陷。

缺陷汇总与去重见 [findings/SUMMARY.md](findings/SUMMARY.md)。P2/P7/P9/P10 的自检没有发现业务缺陷；P9 的 I5“单层防护”按文档记录为事实，不是 bug。

## 5. 局限与未做

- **形式化证明的对象是抽象模型/规格**：P4 证明 `encoding.py` 的规格公式，P5 证明 `booking_model.py` 的转移系统；Python 实现只通过有界穷举/对拍关联，没有自动精化关系。代码改动后模型可能过期。
- **BMC/归纳之外的并发由数据库保证**：P5 的顺序转移系统无法表达两个事务的交错；FP-SCHED-3 的原子性由行锁 + 唯一约束保证，P9 的 I2 与专项套件覆盖这一层。
- **变异分数是同口径前后对比**：93.71% 来自自研 6 类 AST 算子，不能与 mutmut 全量算子集横向比较；P1 属性测试单独新增 killed = 0，报告已如实写出。
- **`pip-audit` 只扫运行时锁文件**：`tests/advanced/requirements.txt` 的测试依赖不在范围内；npm audit 用 `--omit=dev`，devDependencies 不在范围内。
- **PostgreSQL 版本差异**：本报告如果由本地开发证据生成，使用的是 Windows 便携版 PostgreSQL 18.6；任务/CI 的正式镜像是 `postgres:15`。两者在唯一约束、行锁、`DROP ... WITH (FORCE)` 语义上一致，但版本差异仍应记录；正式 CI 证据由 `advanced-slow` 在 `postgres:15` 上重跑。
- **P10 的 5 个手写变异体是小样本**：任务 §7 的“P10 全量对比”与“属性测试单独杀伤力”是可选加分项，本次未完成；5/5 vs 3/5 只应读作抽样结论。P7 的 304 个全量变异体是必测套件的证据，不直接等同于 P10 生成测试的分数。
- **P8 的 schema drift 未修**：793 次失败是 FastAPI 未声明 4xx，属于生产 API 文档工作，不在测试任务范围内；报告保留而不静默过滤。
- **`run.py` 无模式超时**：CI 由 `advanced` 的 30 分钟与 `advanced-slow` 的 90 分钟 `timeout-minutes` 兜底；本地运行需要自己控制时长。

## 6. 页脚

- 源码版本：`f28b27974352cd121d0a3f64ac7f859f098301f1`（分支 `test/P11`）
- 运行完成时间：2026-11-26T06:27:00.359497+00:00
- 报告生成时间：2026-11-26T06:33:42+00:00
- Python：3.14.4 (tags/v3.14.4:23116f9, Apr  7 2026, 14:10:54) [MSC v.1944 64 bit (AMD64)]
- PostgreSQL 版本：PostgreSQL 18.6
- 证据来源：本地开发证据目录 `D:\Study\Y4 - CSC4801\_evidence\P11\final-all-3`（`run.py all`；PostgreSQL 18.6）。正式 CI 证据（`postgres:15`）由 `advanced-slow` job 生成（artifact 名 `advanced-slow-results`）；下载 artifact 后运行 `python tests/advanced/report.py <artifact> --unit-junit <unit.xml> --ci-run <run-id>` 即可把本页脚替换为 CI run 号与 artifact 名。
- 重新生成：`python tests/advanced/report.py D:\Study\Y4 - CSC4801\_evidence\P11\final-all-3 --unit-junit <unit.xml>`
- 产物命名约定：`run.py` 会覆盖 `<out>/<mode>/result.json`，因此业务报告使用各自的 durable 文件名（`mutation-result.json`、`report.json`、`ltl_results.json`、`booking_bmc.json`、`coverage-summary.json` 等）。

