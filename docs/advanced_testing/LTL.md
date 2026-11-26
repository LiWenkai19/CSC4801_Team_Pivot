# LTL 时序性质检查器（P3）

## 0. 结论速览

- **检查器**：`tests/advanced/support/ltl.py`，纯 Python 有限轨迹 LTL，无第三方 LTL 依赖，
  AST 支持 `Atom / Not / And / Or / Implies / X / WX / G / F / U`，另有有限域
  `Forall / Exists` 与参数化原子（`booked:?a:?s`）。
- **性质**：L1–L5 在 P2 的 25 个轨迹文件（23 条去重轨迹、300 步）上全部满足；
  每条性质的满足数、非空真轨迹数、触发实例数都写进了 `ltl_results.json`。
- **自检**：`test_checker_selftest.py` 232 个用例，每个运算符至少 3 条满足 + 3 条违反，
  `G(p -> X q)` / `p U q` / `F G p` 各有穷举真值表；另对 L1–L5 各喂一条手写违反轨迹。
- **加分项**：`refine.py` 在 L13 slide 46 的 `G(a -> X(b U c))` 形状上演示 relax/restrict，
  固定 seed 4801 的精化链为
  `F: 0/25 → F': 10/25 → F'': 10/25 → F''': 25/25`，同 seed 结果逐字节可复现。
- **没有修改生产代码**；所有临时变异自检都用仓库外的 `-p` 插件完成，运行结束后不落盘到仓库。

## 1. 文件与运行方式

| 路径 | 作用 |
| --- | --- |
| `tests/advanced/support/ltl.py` | AST、有限轨迹求值、量化、`explain`、遍历/替换工具 |
| `tests/advanced/ltl/properties.py` | L1–L5 公式、需求条款、空真（前件触发）统计辅助函数 |
| `tests/advanced/ltl/test_checker_selftest.py` | 手工轨迹 + 穷举真值表 + L1–L5 反例 + 解释器自检 |
| `tests/advanced/ltl/test_booking_traces.py` | 读取/生成 P2 轨迹、对全部轨迹求值、写 evidence、refine 复现测试 |
| `tests/advanced/ltl/refine.py` | 加分项：relax/restrict 演示（讲义 L13 slides 46–52） |
| `tests/advanced/ltl/NEEDS_DB` | P2 轨迹缺失时需要一次性 PostgreSQL 来生成；有轨迹时测试本身不连库 |

```sh
# 验收：自动发现 ltl 模式；没有现成 P2 轨迹时先生成，再检查
python tests/advanced/run.py ltl --out <仓库外的新目录>

# 已有 $ADVANCED_OUT/stateful/traces 时可以完全不连数据库
ADVANCED_OUT=<含 stateful/traces 的目录> ADVANCED_MODE=ltl \
  python -m pytest tests/advanced/ltl -q

# 只跑检查器自检（不需要数据库）
python -m pytest tests/advanced/ltl/test_checker_selftest.py -q

# 必测套件（应与 main 一致）
python tests/run_tests.py
```

`run.py` 会把 `PYTHONHASHSEED=4801`、`PYTHONPATH`、`ADVANCED_OUT` 传给子进程；
`needs_db` 只影响外层是否启动一次性 PostgreSQL。若 `$ADVANCED_OUT/stateful/traces`
不存在，`test_booking_traces.py` 以子进程运行
`python tests/advanced/run.py stateful --out $ADVANCED_OUT/ltl/stateful --max-examples 25`，
复用外层的 `ADVANCED_PG_URL`，然后把轨迹归一到 `$ADVANCED_OUT/ltl/stateful/traces`
（放在 ltl 模式自己的目录里，避免和 `run.py fast/all` 中真正的 stateful 模式的产物互相覆盖）。
也可以设置 `ADVANCED_MAX_EXAMPLES` 减少生成规模（上限 100）。

## 2. 有限轨迹语义

记轨迹为 `s = [e_0, ..., e_{n-1}]`，`e_i.props` 是第 `i` **步之后**成立的原子集合
（P2 的 `Event.props` 是状态切片，不是增量）。后缀下标 `i` 满足 `0 <= i <= n`。

| 公式 | 在 `i` 处的语义 |
| --- | --- |
| `Atom(p)` | `i < n` 且（绑定后）`p ∈ e_i.props` |
| `!φ` | `not eval(φ, i)` |
| `φ & ψ` | `eval(φ, i)` 且 `eval(ψ, i)` |
| `φ \| ψ` | `eval(φ, i)` 或 `eval(ψ, i)` |
| `φ -> ψ` | `not eval(φ, i)` 或 `eval(ψ, i)` |
| `X φ` | **强下一步**：`i + 1 < n` 且 `eval(φ, i+1)`；最后一步为假 |
| `WX φ` | **弱下一步**：`i + 1 >= n` 或 `eval(φ, i+1)`；最后一步为真 |
| `G φ` | 对所有 `k ∈ [i, n)` 有 `eval(φ, k)`；空后缀为真（空真） |
| `F φ` | 存在 `k ∈ [i, n)` 使 `eval(φ, k)`；空后缀为假 |
| `φ U ψ` | 存在 `k ∈ [i, n)` 使 `eval(ψ, k)`，且对所有 `j ∈ [i, k)` 有 `eval(φ, j)` |

边界语义是刻意测试的：空轨迹满足 `G` 和 `WX`，违反 `F`、`X`、`U` 和原子；最后一步是
强/弱下一步唯一分歧的地方。`evaluate(formula, trace, i)` 允许 `i == n`（空后缀），
不允许负数或超过长度。

### 2.1 参数化原子与有限域量化

`Atom("booked:?a:?s")` 的每一段要么是字面量（精确、区分大小写），要么是 `?name`
变量；模式与具体原子的段数必须相同。例如：

```text
booked:?a:?s         匹配 booked:a1:s1        绑定 {a: a1, s: s1}
status:?a:Interviewing  匹配 status:a1:Interviewing
slot:s1               只匹配 slot:s1
```

`forall(vars, φ)` / `exists(vars, φ)` 的域来自**轨迹中实际出现的值**：
对每个变量 `v`，扫描轨迹里形状与 `φ` 中某个“`v` 自由出现”的原子模式相符的原子。
“形状”指命名空间（第一段）和段数；模式中不由外层环境绑定的非首段字面量不参与域收集。
这样 `status:?a:Interviewing` 也能把 `status:a2:Rejected` 的 `a2` 纳入域，
避免“域太小 → 量词空真通过”的错误。外层量词已经绑定的变量会精确比较，
所以 `booked:?a:?s` 在 `a = a1` 下只收集 `a1` 的时段。

- 域为空时，`forall` 为真、`exists` 为假——这是空真，报告必须单独统计；
- 含自由变量的公式不能直接 `evaluate`，必须先用 `forall`/`exists` 关闭；
- 量化域是**整条轨迹**出现过的值（不是当前后缀），所以性质在时间上仍然是标准的
  有限轨迹语义；这也是“空真统计”存在的原因。

### 2.2 `explain`

`explain(formula, trace)` 在公式满足时返回 success 消息；失败时给出**第一个导致失败的
状态**（不是简单的后缀 0）：先按结构定位（`G` 逐状态找第一个失败点、`X` 找后继、
`And/Or` 取最早违反、量词记录绑定），再输出：

```text
first violation at trace index 3 (step 4, action=observe, ok=True)
  props: [...]
  binding: a=a1, s=s1
  reason: negated subformula available:s1 holds here
```

`trace index` 是列表下标（0 起），`step` 是生产方写入的步号（P2 从 1 起）。

## 3. 性质 L1–L5

原子命名与 P2 状态切片的约定见 `tests/advanced/README.md` 第 8 节。所有公式都写在本目录的
`properties.py` 中，注释里逐条标注需求条款。

| ID | 公式 | 条款 | 业务含义 |
| --- | --- | --- | --- |
| L1 | `forall a,s: G(booked:a:s -> WX G(!available:s))` | FP-SCHED-1/2 | 预约后时段永不再出现在可用列表；最后一步预约时弱下一步为空真 |
| L2 | `forall a: G(new_booking:a -> status:a:Interviewing)` | FP-SCHED-2 | 只有 `Interviewing` 的申请才能新建预约 |
| L3 | `forall a,s: G(booked:a:s -> G(booked:a:s))` | FP-SCHED-2 | 预约一旦建立永不消失；申请离开 `Interviewing` 也不解绑 |
| L4 | `forall a,s: G(booked:a:s -> G(slot:s))` | FP-SCHED-1 | 已预约时段永不被删除（删除已预约时段会被拒绝） |
| L5 | `forall a: G(applied:a -> G(applied:a))` | FP-CAN-3 | 申请行不会消失（删除职位只是软删除 posting） |

## 4. 真实轨迹结果

运行环境：本机 Windows、Python 3.14.4、**PostgreSQL 18.6 便携版**
（`PG_BIN=D:\Study\Y4 - CSC4801\tools\pgsql\bin`）。任务/CI 的 Docker 镜像是 PostgreSQL 15；
本机没有 15.x 的服务器工具，故用 18.6，并单独记录了版本。生成结果与 P2 已合并代码在
相同 seed 下的正式数字一致（25 files / 23 distinct / 11 次成功预约 / 2 次删除已预约时段被拒绝）。
外层 `run.py ltl` 新建临时集群（随机端口、仅 loopback、trust、运行后删除）；
不读取 `backend/.env`，不访问外网。

轨迹由 P2 状态机在 `max_examples=25, stateful_step_count=12, derandomize=True` 下产生：

```text
files=25, distinct=23, steps=300, distinct steps=276
new_booking 步=11, 处于 booked 状态的状态步=29
delete_slot 事件=4（成功 2、被拒绝 2——即 2 次删除已预约时段的尝试）
```

| ID | 满足/轨迹（去重） | 非空真轨迹（去重） | 前件触发实例 | 前件触发状态步 |
| --- | --- | --- | --- | --- |
| L1 | 25/25（23/23） | 11（10） | 11 | 29 |
| L2 | 25/25（23/23） | 11（10） | 11 | 11 |
| L3 | 25/25（23/23） | 11（10） | 11 | 29 |
| L4 | 25/25（23/23） | 11（10） | 11 | 29 |
| L5 | 25/25（23/23） | 25（23） | 43 | 278 |

解释：

- “非空真轨迹”指该性质外层蕴含的前件（`booked`、`new_booking`、`applied`）在这条轨迹里
  至少触发过一次；没有触发的轨迹只是空真满足，不计为有效证据。
- Hypothesis 会重放少量 example，因此文件数（25）大于去重数（23）；表中同时报告两套数字。
- **空真警告**：本批轨迹中没有任何性质的“非空真轨迹”少于 5 条，所以 evidence 的
  `nonvacuous_traces_under_5` 为空。但 L1/L4 的前件只由 11 个 booking（10 条去重轨迹）触发；
  L4 真正“删除已预约时段”的分支只有 **2 次**拒绝尝试。也就是说，L4 的非空真样本主要证明
  “预约存在时段就存在”，对“删除尝试一定被拒绝”这一具体分支的覆盖很薄。
  该分支由 P2 自己的不变量补强：P2 在每个成功预约后检查 booked slot 不在 available 列表
  （不变量 2）、booking 的起点必为 `Interviewing` 且状态变化后仍存在（不变量 3）、
  被拒绝的操作不改变任何表行数（不变量 5）；P5 的 Z3 有界模型检验若交付，可在
  6 步转移模型上独立补强这条分支。**本次 P3 没有、也不能把 P2 的 11 个 booking 变成
  更多删除尝试**——按任务要求没有修改 P2 的代码或权重。L1–L5 的“全部满足”是这 25 条
  有界随机轨迹上的事实，不是穷尽证明。

证据文件（`--out` 下）：

```text
<out>/ltl/ltl_results.json      # 上面的全部数字 + 每条性质的公式/条款
<out>/ltl/refinement.json       # relax/restrict 链与所有 restrict 候选
<out>/ltl/run.log               # pytest 摘要（不含 Cookie/CSRF/密码）
<out>/ltl/junit.xml
```

若 P2 轨迹是本次 ltl 模式自动生成的，轨迹在 `<out>/ltl/stateful/traces/`，嵌套的
`stateful` 运行元数据在 `<out>/ltl/stateful/stateful/`；生成耗时计入
`generation_seconds`，纯求值耗时通常 < 0.1s（evidence 的 `duration_seconds`）。

## 5. 检查器自检

`test_checker_selftest.py` 共 **232** 个用例（`pytest -q` 统计；整个 ltl 模式 235 个 =
232 + 3 个轨迹/集成测试）。

- 每个运算符一张手写表：`atom/not/and/or/implies/x/wx/g/f/u` 各至少 3 条满足 + 3 条违反，
  期望值按上面的语义手算；`test_operator_has_three_satisfying_and_three_violating_cases`
  还会检查表格没有被后续编辑破坏。
- 真值表：`G(p -> X q)` 与 `p U q` 各穷举 3 步的所有 64 种 `p/q` 取值；
  `F G p` 穷举 8 种 `p` 取值。期望值由手推的独立布尔表达式给出，例如
  `F G p` 在非空轨迹上等价于“最后一步 `p` 为真”（取最后一步作见证）。
- 边界：空轨迹、`i == n`、`X` vs `WX`、自由变量报错、`forall`/`exists` 空域、
  量化域只从轨迹收集。
- 每条性质一条手写违反轨迹，断言 `evaluate` 为假且 `explain` 指到正确步号；
  另有修正后的合成轨迹断言为真。
- 必做 L1 自检：预约后同一时段再次 `available`：

```text
evaluate = False
LTL property violated: forall a, s: G((booked:?a:?s -> WX(G(!available:?s))))
first violation at trace index 3 (step 4, action=observe, ok=True)
  props: ['applied:a1', 'available:s1', 'booked:a1:s1', 'slot:s1', 'status:a1:Interviewing']
  binding: a=a1, s=s1
  reason: negated subformula available:s1 holds here
```

去掉第 4 步的 `available:s1` 后同一公式返回 `True`，说明检查器既能判真也能判假，
不是恒真 oracle。

### 5.1 证明测试会失败（故意引入错误 → 变红 → 恢复）

所有变异都用仓库外临时 `-p` 插件 monkeypatch 内存中的检查器/性质，**没有改生产代码**；
每个变异都先跑正常目标用例确认绿色，再加载插件运行，观察失败，然后在新进程中不加载插件
重新运行确认恢复绿色。

| 故意引入的错误 | 目标用例 | 观察到的红 |
| --- | --- | --- |
| 把强 `X` 实现成弱 `WX`（最后一步返回真） | `-k "operator_hand_traces and x- and not wx"` | `x-3-viol`, `x-4-viol` 失败（2 failed） |
| 把 `U` 弱化成只检查右侧 `F(right)` | `-k "operator_hand_traces and u-"` | `u-6-viol` 失败（右操作数后来成立但左操作数先失败） |
| 量化域改回“字面量精确匹配”（`status:?a:Interviewing` 看不到 `a2:Pending`） | `-k "quantifier_respects_occurrence_values or forall_hand_traces"` | 2 个用例失败，证明域不能被悄悄缩小 |
| 空真统计恒返回空集 | `-k "vacuity"` | `test_vacuity_helpers_count_implication_antecedents` 失败 |
| 把 L1–L5 全替换成恒真公式 | `-k "l1_counterexample or business_property_detects"` | L1 + L2/L3/L4/L5 共 5 个反例用例失败 |
| 让 `explain` 永远报 trace index 0 | selftest `-k "l1_counterexample"` | L1 解释断言失败 |
| 让 `refine.restrictions` 返回空（无法 restrict） | `test_booking_traces.py -k refinement_demo` | `assert first.restricted is not None` 失败 |

## 6. 加分项：relax/restrict 精化演示（L13 slides 46–52）

`refine.py` 取一条故意过强的性质，形状与讲义 slide 46 的
`G(a -> X(b U c))` 相同，业务化为：

```text
forall a:
  G( status:a:Interviewing
     -> X( status:a:Interviewing U (exists s: booked:a:s) ) )
```

含义是“申请一旦进入 `Interviewing`，从下一步起必须一直保持 `Interviewing`，
直到它被预约”。需求并不保证这一点：雇主可以改成 `Rejected`/`Accepted`，轨迹也可以
在仍是 `Interviewing` 时结束。所以它有反例，可以演示 relax。

### 6.1 Relax 链（固定 seed 4801，25 条轨迹）

| 步骤 | 接受的轨迹 | 操作 |
| --- | --- | --- |
| `F` | 0/25（0.0%） | 初始过强性质 |
| `F'` | 10/25（40.0%） | `X -> F` |
| `F''` | 10/25（40.0%） | `U -> F(right)` |
| `F'''` | 25/25（100.0%） | `G -> F` |

随机选择用 `random.Random(4801)`，遍历顺序是稳定前序遍历，所以同一 seed 产生同一链；
`test_refinement_demo_is_reproducible` 断言两次 `run_demo` 的 `to_dict()` 完全相同，
并检查每一步的接受数单调不减、最后一步接受全部轨迹。`weakenings` 覆盖讲义要求的
`X -> F`、`G -> F`、去掉合取项，以及 `U -> F(right)`；`F -> true` 只在没有其它候选时兜底。

### 6.2 Restrict 探针

对最后一条被全部轨迹接受的性质，尝试每个 `F -> G` / `F -> X` 候选（slide 47）：

| 探针 | 接受轨迹 | 操作 |
| --- | --- | --- |
| R0 | 10/25（40.0%） | 最外层 `F -> G` |
| R1 | 24/25（96.0%） | 最外层 `F -> X` |
| R2 | 25/25 | 内层 `F -> G` |
| R3（随机选中） | 25/25 | 内层 `F -> X` |
| R4 | 25/25 | 内层 `F -> G` |
| R5 | 25/25 | 内层 `F -> X` |

seed 4801 随机选中的 R3 没有暴露反例，但 R0/R1 分别暴露了 15 条和 1 条新反例：
说明“relax 到 100%”并不等于性质已经空到没有约束，最外层从 `F` 收紧回 `G/X`
会重新产生反例。这正是讲义 slide 50 的“记录仍被违反的最后一个性质”思想的可观测版本；
R0/R1 的失败轨迹也可以用 `explain` 定位（evidence 的 `restriction_candidates`
保留每个候选的公式、接受数和是否出现反例）。

可复现性测试的目标：

```sh
ADVANCED_OUT=<含 stateful/traces 的目录> ADVANCED_MODE=ltl \
  python -m pytest tests/advanced/ltl/test_booking_traces.py -q -k refinement_demo
```

## 7. 局限（明确不夸大）

1. **有限轨迹**：只支持 `evaluate(formula, trace, i)` 的有限序列语义，不支持无限轨迹、
   lasso、公平性；`G/F/U` 在空后缀上的边界按本文档定义，不是所有 LTL 文献的默认约定。
2. **有界随机探索**：25 个 Hypothesis example、每例最多 12 步、`derandomize=True` 且固定
   seed 4801。全部满足只说明这 25 条轨迹没有反例，**不是**穷尽证明；P2 的规则权重和
   固定 seed 决定了轨迹空间，改变权重/seed 可能到达未覆盖的分支。
3. **量化域来自轨迹**：`forall`/`exists` 只能枚举轨迹里出现过的值；一个值如果从未出现在
   轨迹的相应原子中，就不在域内。域收集用“命名空间 + 段数 + 外层已绑定值”的结构匹配，
   这是为了不让 `status:?a:Interviewing` 漏掉 `status:a2:Rejected`；但它仍是有限的、
   依赖 P2 原子词汇表的近似，不是完整的一阶域。
4. **轨迹是状态切片**：`props` 是每步之后的状态，不记录“这一步之前的状态”或事件的完整
   历史。`L2` 依赖 P2 在成功预约同一步写出 `new_booking`；如果生产方漏写该原子，
   L2 会空真通过。检查器只能验证写进轨迹的事实。
5. **空真**：L1/L4 的非空真轨迹是 11（去重 10），并非 0；但 L4 的删除分支只有 2 次拒绝
   尝试，证据主要由 P2 不变量和未来 P5 模型检验补强，不能由 P3 单独证明。
6. **refine 的“更弱”**：`G -> F` 在**非空**轨迹上是弱化；在空后缀（`i == n`）上
   `G` 真而 `F` 假，不构成弱化。P2 的轨迹都非空，`run_demo` 也只在这些轨迹上运行；
   因此这里不声称对空轨迹成立。`U -> F(right)`、`X -> F`、去掉合取项对非空后缀同样
   是弱化，`F -> true` 是兜底真公式。
7. **不是穷尽验证**：本任务是测试/验证工具，不修改生产代码，也不把 P2 的轨迹当业务正确性
   的证明；所有数字都可从 evidence JSON 重算。

## 8. 证据与复现核对清单

- `ltl_results.json` 应包含：
  `traces.files/distinct/steps/steps_distinct`、`properties.{L1..L5}` 的
  `satisfied`/`nonvacuous_traces`/`trigger_instances`/`trigger_steps`、
  `events.new_booking_steps`、`events.delete_slot_rejected`、
  `nonvacuous_traces_under_5`。
- `refinement.json` 应包含 `steps`（F→F'→F''→F'''）、`restricted`、
  `restriction_candidates`、`counterexample`（若选中候选有反例）。
- `run.log` 只有 pytest 摘要；任何会话令牌、CSRF、密码哈希都不应出现。
- 复现命令：

```sh
PG_BIN=<PostgreSQL 15 bin，或本机 18.x bin> \
  python tests/advanced/run.py ltl --out <仓库外的新目录>
python tests/run_tests.py
```
