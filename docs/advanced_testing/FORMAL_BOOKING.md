# FP-SCHED 预约状态机的有界模型检验与归纳证明（Z3）

本文件记录 `formal` 模式中 P5 的部分：把预约规则抽象成符号转移系统，用 Z3 同时做

1. `k = 6` 步的**有界模型检验**（BMC）——在有限步内搜索反例；以及
2. `k = 1` 的**归纳证明**——把 B1–B4 从“6 步内无反例”提升为“对任意步数成立”。

运行方式与 P4 相同：

```sh
python tests/advanced/run.py formal
```

`formal` 模式**不需要数据库**（目录里没有 `NEEDS_DB`），P4 的匹配公式证明与 P5 的
预约状态机检查在同一个 pytest 进程里运行。

## 1. 结论

- **BMC（k = 6）：B1–B4 全部 `unsat`**。在 6 步以内，从合法初始状态出发的**每一条**
  路径都不违反这四条性质（求解器找不到反例）；N1/N2 在放宽守卫后为 `sat` 并给出可读
  反例（§5）；3 个可达性见证全部 `sat`，说明这些 `unsat` 不是空真。
- **归纳（k = 1）：全部证明义务 `unsat`**。状态不变式
  `Inv(S) = B1(S) ∧ (booking_of_app[a] = s → slot_exists[s])` 满足基例和归纳步；
  B2、B4 作为单步转移性质在“任意满足 Inv 的状态 + 任意一步”上成立；再证明辅助单步
  性质“预约只增不减”，就能把 B3 的状态形式提升为时间形式（§7）。
- **因此，在抽象模型上 B1–B4 对任意步数成立**。BMC 与归纳分工不同：BMC 负责在
  具体路径上找反例、给出可读轨迹和可达性见证；归纳负责覆盖任意长度。两者都不改变
  下一段的边界。
- **与真实代码之间仍然是“模型 ↔ 代码”的对应关系**：证明对象是
  [`booking_model.py`](../../tests/advanced/formal/booking_model.py) 里的抽象转移系统，
  守卫是人工从 `backend/app/` 抄写的（§3），没有自动提取或精化关系。代码改了模型不会
  自动跟着变，因此所有“证明 / unsat”都应读作“在该抽象上没有反例 / 在该抽象上成立”，
  不能读作“实现已被证明正确”。
- `formal` 模式本机实测 **36 passed，模式耗时约 5.2–6.7 s**（P4 18 条 + P5 18 条，
  多次运行范围；验收上限 60 s）。单次 Z3 查询 0.0005–0.02 s。

## 2. 模型

文件：[`booking_model.py`](../../tests/advanced/formal/booking_model.py)。

### 2.1 规模与状态

| 项 | 取值 |
|---|---|
| 申请 | `a0`、`a1`，同一个雇主 |
| 时段 | `s0`、`s1`，都属于该雇主 |
| BMC 步数 | `k = 6`，状态 `S_0 … S_6` |
| 申请状态 | `status[a][t] ∈ {Pending, Interviewing, Rejected, Accepted}`（`EnumSort`） |
| 申请的预约 | `booking[a][t] ∈ {none, s0, s1}`（`EnumSort`；一个申请至多一个预约，对应 `uq_booking_application`） |
| 时段存在 | `slot_exists[s][t] : Bool` |

Z3 的 `EnumSort` 保证状态与预约取值互斥且完备；`booking[a][t]` 是单值枚举，所以
“一个申请最多一个预约”是**结构性的**，不需要单独的性质。

### 2.2 动作

`action[t]` 是一个 `EnumSort` 常量，取值恰好 15 个：
`noop`、`set_status(a, S)`（2×4）、`book(a, s)`（2×2）、`delete_slot(s)`（2）。
每步只有一个动作，因此“每步恰选一个”不需要额外的互斥约束。

### 2.3 迁移语义

对每个 `t`，只有被选中的动作能改变状态；守卫不成立时**所有状态变量保持不变**：

```text
status[a][t+1]      = S                    if action[t] = set_status(a, S)
                    = status[a][t]         otherwise
booking[a][t+1]     = s                    if action[t] = book(a, s) ∧ book_guard(a, s, t)
                    = booking[a][t]        otherwise
slot_exists[s][t+1] = false                if action[t] = delete_slot(s) ∧ delete_guard(s, t)
                    = slot_exists[s][t]    otherwise
```

守卫失败 → 状态不变，对应需求 “Ineligible bookings **MUST** fail without partially
changing either record”（FP-SCHED-2）以及代码里的 `session.rollback()`
（`candidate/service.py:422-439`、`interview/service.py:144-145`）。

`book_guard` 建模的四个条件（与任务书一致）：

```text
status[a][t] = Interviewing
∧ booking[a][t] = none
∧ slot_exists[s][t]
∧ ∀ a' ≠ a: booking[a'][t] ≠ s          （“时段未被任何申请预约”）
```

`delete_guard`：

```text
slot_exists[s][t] ∧ ∀ a: booking[a][t] ≠ s
```

### 2.4 初始状态

`status[a][0] = Pending`（新申请的状态，`employer/model.py:89-102` 默认值）、
`booking[a][0] = none`、`slot_exists[s][0] = true`。

固定初始状态让 B1–B4 变成**可达性**命题：如果不固定，`t = 0` 就可以让两个申请都
预约 `s0`，B1 会在第一步之前就被违反，BMC 证明失去意义。

### 2.5 抽象假设

模型只保留调度规则约束的状态，以下条件被抽象为“恒真/不建模”，都是**假设**：

- **时间**：所有时段都在未来且恰好 30 分钟，因此 `starts_at > now` 与
  “时长 = 30 分钟”两个检查恒成立；
- **归属**：两个申请属于同一雇主，两个时段也属于该雇主，因此 `slot.employer_id`
  与 `application` 的归属检查恒成立，跨雇主场景不在模型里；
- **时段创建**：`s0`、`s1` 在初始状态已存在（建模为场景设置），模型里没有
  `create_slot` 动作；
- **职位保留**：实现里预约成功会把 `slot.job_id` 绑定到职位，已绑定其它职位的时段
  不能复用（`candidate/service.py:414-417`）。这是 FP-SCHED-2 措辞之外的实现细节，
  且单雇主场景下不会触发，故不建模；
- **乐观锁 / 版本号**：`change_application_status` 的 `version` 冲突检查
  （`employer/service.py:368-369`）不在模型里；
- **并发**：FP-SCHED-3 的“两个候选人并发抢同一时段”由数据库行锁 + 唯一约束保证，
  是数据库层的性质，顺序转移关系无法表达（见 §9）。

### 2.6 同一份编码，两种用法

`BookingBMC` 的守卫（`book_guard` / `delete_guard`）和效果（`_next_*`）只有一份实现，
BMC 与归纳共用，避免两套编码悄悄分叉：

| 用法 | 构造 | 查询 |
|---|---|---|
| BMC | `BookingBMC(steps=6)` | 初始状态 + 6 步转移，对 B1–B4 取反求解 |
| 归纳基例 | `BookingBMC(steps=1)` | `solve_initial()` 只用初始状态约束 |
| 归纳步 / 单步性质 | `BookingBMC(steps=1, include_initial=False)` | 任意 `(S, a, S')`，S 不要求可达 |

`include_initial=False` 是“对任意状态 S”的关键：如果带着初始状态约束，归纳步就只能
从初始状态出发，那就退化成一步 BMC，而不是归纳证明。

## 3. 守卫 ↔ 代码对应

`candidate/service.py`、`interview/service.py` 与 `employer/service.py` 为行号来源
（本分支 `test/P5` 于 main `ddaece6` 之后）。BMC 与归纳证明用的是同一张表里的守卫，
所以这张表同时是两者的“模型 ↔ 代码”桥。

| # | 模型中的条件 | 代码位置 | 模型里的处理 |
|---|---|---|---|
| 1 | 申请属于调用者 | `candidate/service.py:352`（`_owned_application`） | 抽象：恒真 |
| 2 | `status = Interviewing` | `candidate/service.py:353-354` | `status[a][t] = Interviewing` |
| 3 | 该申请没有预约 | `candidate/service.py:355-359` | `booking[a][t] = none` |
| 4 | 时段存在 | `candidate/service.py:395-399` | `slot_exists[s][t]` |
| 5 | 时段属于申请对应雇主 | `candidate/service.py:403-404` | 抽象：恒真 |
| 6 | 时段在未来 | `candidate/service.py:405-406` | 抽象：恒真 |
| 7 | 时段时长 30 分钟 | `candidate/service.py:407-408` | 抽象：恒真 |
| 8 | 时段未被任何申请预约 | `candidate/service.py:409-413` | `∀a'≠a: booking[a'][t] ≠ s`（N1 删掉） |
| 9 | 时段未被其它职位保留 | `candidate/service.py:414-416` | 不建模（§2.5） |
| 10 | 预约效果：写入 `Booking(application_id, slot_id)` | `candidate/service.py:417-421` | `booking[a][t+1] = s` |
| 11 | 删除时时段存在 | `interview/service.py:125-129` | `slot_exists[s][t]` |
| 12 | 删除者拥有时段 | `interview/service.py:130-131` | 抽象：恒真 |
| 13 | 删除时段未被预约 | `interview/service.py:134-138` | `∀a: booking[a][t] ≠ s`（N2 删掉） |
| 14 | 删除时时段在未来 | `interview/service.py:139-140` | 抽象：恒真 |
| 15 | 删除效果 | `interview/service.py:142-143` | `slot_exists[s][t+1] = false` |
| 16 | 状态只能在四个值间切换，不碰预约 | `employer/service.py:346-389`，尤其 `370-372` | `status[a][t+1] = S`，booking 不变（B4） |
| 17 | 新申请默认 `Pending` | `employer/model.py:89-102` | `status[a][0] = Pending` |
| 18 | 数据库唯一约束 | `employer/model.py:129-132`（`uq_booking_application`、`uq_booking_slot`） | 单值 `booking_of_app`（含“每申请一个预约”）+ B1（含“每时段一个预约”） |

失败动作不部分修改：模型里守卫失败的 `book`/`delete` 分支不改任何变量；代码在异常
路径调用 `session.rollback()`（`candidate/service.py:422-439`、
`interview/service.py:144-145`）。

## 4. 有界模型检验（BMC，k = 6）

每条性质取反后与初始状态、转移约束一起交给 `z3.Solver`；`unsat` 表示
“6 步内不存在违反对应性质的路径”。

| ID | 性质（对所有 `t ≤ 6`） | 需求条款 | 结果 | 单次查询耗时 |
|---|---|---|---|---|
| B1 | 不存在两个申请同时预约同一时段：`AtMost(booking[a0][t]=s, booking[a1][t]=s, 1)` | FP-SCHED-2 | `unsat` | 0.0118 s |
| B2 | 若 `t` 步 `book(a, s)` 的守卫成立（= 本步真的创建了预约），则 `status[a][t] = Interviewing` | FP-SCHED-2 | `unsat` | 0.0009 s |
| B3 | 若 `t` 步某时段已被预约，则对任意 `t' ≥ t` 该时段仍存在 | FP-SCHED-1 | `unsat` | 0.0113 s |
| B4 | 若 `t` 步改变任一申请 `a` 的状态且 `booking[b][t] ≠ none`，则 `booking[b][t+1] = booking[b][t]`（对任意申请 `b`） | FP-SCHED-2 / FP-EMP-3 | `unsat` | 0.0063 s |

关于 B2 的诚实说明：B2 的证明内容一部分是“`book` 守卫里确实写了
`status = Interviewing`”，另一部分（也是真正有信息量的部分）是**没有别的动作能创建
预约**——转移关系里只有 `book` 会写 `booking`，`set_status`、`delete_slot`、`noop`
都不写。N3 说明去掉状态守卫后 B2 立刻可被违反，因此这个 `unsat` 不是纯粹的恒真式。

B3 的方向是“曾经被预约过 → 之后一直存在”，而不是“当前仍被预约 → 存在”。这样即使
（错误地）允许清除预约，只要之后删除了该时段，B3 仍会报警——§8 的 M4 变异正是这种情况，
它会同时弄红 B3 和 B4。

B4 对“改变任一申请的状态”量化（不只改变持有预约的那个申请），因此它也覆盖“改
`a0` 的状态不能碰 `a1` 的预约”。

BMC 的作用是**找反例**：k = 6 足以覆盖 N1/N2 的最短反例与完整预约生命周期，并且
把反例渲染成可读轨迹；它不承担“对任意步数成立”的证明，后者由 §7 的归纳完成。

## 5. 负向演示（BMC）：放宽守卫后求解器给出反例

每个负向演示只改一个守卫；期望 `sat`，并把 `model` 渲染成逐状态、逐动作的序列。
`--out` 下的 `formal/booking_bmc.json` 保存同一份 `trace_text`，`formal/run.log`
也会打印（测试通过 pytest 的 capture manager 暂时关闭捕获后写出）。

### N1：去掉 `book` 的“时段未被预约”守卫 → B1 被违反

```text
B1 counterexample (variant: allow_booking_taken_slot):
t=0  status[a0]=Pending  status[a1]=Pending  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[0]: set_status(a0, Interviewing)
t=1  status[a0]=Interviewing  status[a1]=Pending  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[1]: noop
t=2  status[a0]=Interviewing  status[a1]=Pending  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[2]: book(a0, s1)
t=3  status[a0]=Interviewing  status[a1]=Pending  booking[a0]=s1  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[3]: set_status(a1, Pending)
t=4  status[a0]=Interviewing  status[a1]=Pending  booking[a0]=s1  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[4]: set_status(a1, Interviewing)
t=5  status[a0]=Interviewing  status[a1]=Interviewing  booking[a0]=s1  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[5]: book(a1, s1)
t=6  status[a0]=Interviewing  status[a1]=Interviewing  booking[a0]=s1  booking[a1]=s1  exists[s0]=yes  exists[s1]=yes
```

两个申请最终都预约了 `s1`：`action[2]` 先把 `s1` 分给 `a0`，`action[5]` 又把同一时段分给
`a1`（这正是被删掉的守卫本该拒绝的）。测试
`test_n1_without_slot_free_guard_two_applications_share_a_slot` 从轨迹里断言：
恰好 2 次**成功**的 `book`、申请集合为 `{a0, a1}`、两次指向同一时段，且轨迹中**存在**
两个申请同时绑定同一时段的状态。

### N2：去掉 `delete_slot` 的“时段未被预约”守卫 → B3 被违反

```text
B3 counterexample (variant: skip_delete_booking_guard):
t=0  status[a0]=Pending  status[a1]=Pending  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[0]: set_status(a1, Interviewing)
t=1  status[a0]=Pending  status[a1]=Interviewing  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[1]: noop
t=2  status[a0]=Pending  status[a1]=Interviewing  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[2]: set_status(a1, Rejected)
t=3  status[a0]=Pending  status[a1]=Rejected  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[3]: set_status(a0, Interviewing)
t=4  status[a0]=Interviewing  status[a1]=Rejected  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[4]: book(a0, s0)
t=5  status[a0]=Interviewing  status[a1]=Rejected  booking[a0]=s0  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[5]: delete_slot(s0)
t=6  status[a0]=Interviewing  status[a1]=Rejected  booking[a0]=s0  booking[a1]=none  exists[s0]=no  exists[s1]=yes
```

`a0` 仍持有 `s0` 的预约，但 `s0` 在 `action[5]` 之后不再存在。测试
`test_n2_without_delete_guard_a_booked_slot_is_deleted` 从轨迹里断言：先有成功预约、
再有成功删除，且轨迹中存在“`t` 步已预约、某个 `t' ≥ t` 时该时段已删”的状态对。

### N3/N4：B2/B4 的负向自检

| ID | 变异 | 期望 | 轨迹要点 |
|---|---|---|---|
| N3 | `book` 不再检查 `status = Interviewing` | `sat`（B2 被违反） | `action[1]: book(a1, s1)` 发生在 `status[a1] = Rejected` 时；测试从轨迹断言“成功的 `book` + 前置状态 ≠ Interviewing” |
| N4 | 状态改变时把申请预约重置为 `none` | `sat`（B4 被违反） | `t=3` 时 `booking[a1] = s0`，`action[3]: set_status(a1, Accepted)` 之后 `booking[a1]` 变为 `none` |

完整轨迹同样在 `formal/booking_bmc.json` 和 `run.log` 里。

## 6. 为什么 k = 6

- **反例所需的最短步数**：N1 需要“两次改状态 + 两次预约”，最少 4 步；N2 需要
  “改状态 + 预约 + 删除”，最少 3 步；N3 最少 1 步（初始 `Pending` 直接 `book`）；
  N4 最少 3 步（改状态、预约、再改状态）。
- **覆盖组合而不膨胀**：6 步足以让一个预约经历“创建 → 状态改变 → 尝试删除”的完整
  生命周期，并且还有余量容纳与违规无关的动作（反例轨迹里确实出现了这类步骤）。
- **可判定规模**：每个状态 4² × 3² × 2² = 576 种取值、15 个动作、7 个状态，Z3 每次
  查询都在 10 ms 量级（§4），`formal` 模式整体（含 pytest 启动与 P4 测试）本机
  5.2–6.7 s，远低于 60 s 上限。
- **BMC 的边界**：`k = 6` 只排除“6 步以内的反例”；需要更长前缀才能触发的缺陷不在
  BMC 覆盖范围内。任意步数的结论由 §7 的归纳证明给出，不再依赖 k 的大小。

## 7. 归纳证明（k = 1）

### 7.1 方法

`k`-归纳在 `k = 1` 时就是普通的不变式归纳：找一个状态不变式 `Inv`，证明

1. **基例**：初始状态满足 `Inv`；
2. **归纳步**：对**任意**状态 `S`（不要求从初始状态可达）和任意动作 `a`，
   若 `Inv(S)` 且 `Trans(S, a, S')`，则 `Inv(S')`。

两条合起来（对轨迹长度做元归纳）就得到：每一个可达状态都满足 `Inv`。Z3 证明的是
取反后的公式 `unsat`。

- **任意状态 S**：用 `BookingBMC(steps=1, include_initial=False)`，只保留转移约束，
  `S_0` 与 `action_0` 都是自由变量。
- **同一份编码**：守卫与效果函数和 BMC 完全共用（§2.6），归纳证明的对象就是 BMC
  探索的那个转移关系。
- **任意动作**：`action_0` 是 15 个值的 `EnumSort`；求解器对它的存在量化正对应
  “对任意动作”。

### 7.2 Inv 的最终形式

```text
Inv(S) = B1(S) ∧ (∀a, s: booking_of_app[a] = s → slot_exists[s])
       = “同一时段至多一个申请预约” ∧ “预约到的时段必须存在”
```

后一项就是 B3 的状态形式。`BookingBMC.invariant(t)` 返回该公式。

### 7.3 加强过程（L13：propose → check → counterexample → repair）

**候选 1（被拒绝的加强）**：把 B2 的状态形式也并进不变式，
即 `Inv_A = Inv ∧ (booking_of_app[a] ≠ none → status[a] = Interviewing)`。

- 检查：`Inv_A(S) ∧ Trans(S, a, S') ∧ ¬Inv_A(S')` → **`sat`**。
- Z3 给出的反例（`run.log` 中 `rejected strengthening counterexample`）：

```text
t=0  status[a0]=Interviewing  status[a1]=Rejected  booking[a0]=s0  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[0]: set_status(a0, Rejected)
t=1  status[a0]=Rejected  status[a1]=Rejected  booking[a0]=s0  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
```

- 解读：`S` 满足 `Inv_A`；一步 `set_status(a0, Rejected)` 之后预约仍存在，但状态离开
  了 `Interviewing`，于是 `Inv_A(S')` 为假。**这正是 B4 要求的行为**——FP-SCHED-2
  明确要求“预约后离开 Interviewing 预约仍保留”。把 B2 的状态形式并进 `Inv` 会排除
  需求本身允许的状态，因此拒绝这个加强。
- 附带发现：在 §8 的 M4 变异（状态改变清空预约）下，这个加强反而变成归纳成立的，
  因为它把“预约后状态变化”的行为一起删掉了。这说明该加强是“用错误换归纳性”，不能
  采用。
- 最终方案：`Inv` 保持 B1 ∧ B3 状态形式；B2 作为**单步转移性质**证明（§7.4），
  不塞进状态不变式。

**候选 2（最终）**：`Inv = B1 ∧ B3 状态形式`。归纳步第一次检查即 **`unsat`**，
无需进一步加强。

**辅助性质的加强**：`Inv` 本身只说“预约的时段现在存在”。要把 B3 提升为时间形式
（“`t` 步被预约 → 之后每一步都存在”），还需要预约**不被清除**。这不是状态不变式
能表达的（它是两步之间的关系），因此作为辅助单步性质
`Persist(S, S') = ∀a: booking[a](S) ≠ none → booking[a](S') = booking[a](S)`
单独证明（§7.4）。这是对**证明义务**的加强，而不是对 `Inv` 的加强。

### 7.4 证明义务与结果

全部查询都是“断言取反后 `unsat`”（负向演示除外）。耗时取自本机一次运行。

| 义务 | 公式（取反后求解） | 结果 | 耗时 |
|---|---|---|---|
| 基例 | `Initial(S_0) ∧ ¬Inv(S_0)` | `unsat` | 0.0005 s |
| 归纳步 | `Inv(S) ∧ Trans(S, a, S') ∧ ¬Inv(S')` | `unsat` | 0.0033 s |
| B2 单步 | `Inv(S) ∧ Trans(S, a, S') ∧ ¬B2(S, a, S')` | `unsat` | 0.0007 s |
| B4 单步 | `Inv(S) ∧ Trans(S, a, S') ∧ ¬B4(S, a, S')` | `unsat` | 0.0037 s |
| 预约保持（辅助） | `Inv(S) ∧ Trans(S, a, S') ∧ ¬Persist(S, S')` | `unsat` | 0.0026 s |
| N1 变体的归纳步（负向） | 同上，但去掉“时段未被预约”守卫 | `sat` | 0.0034 s |
| 被拒绝的加强（负向） | `Inv_A(S) ∧ Trans ∧ ¬Inv_A(S')` | `sat` | 0.0038 s |

**B2/B4 为什么是单步就够**：它们只约束**一步转移**——`book` 成功时前置状态必须
`Interviewing`；状态改变时预约必须保留。若它们对每个转移都成立，那么对任意长度的
轨迹、在任意一步上都成立，不需要时间不变式。前提“S 满足 Inv”在逻辑上不是必需的
（守卫/效果是局部的），加上它是为了与归纳证明使用同一组假设。

**B1 与 B3 的任意步数结论**：

- `Inv` 归纳保持 ⇒ 每个可达状态满足 B1，所以 B1 对任意步数成立；
- 每个可达状态满足 `booked → exists`；
- 再结合 `Persist`（每个转移都不清除预约）对时间做元归纳：若 `t` 步有预约，则
  `t' ≥ t` 的每一步仍有该预约，因此由 `Inv` 在该步成立得到该时段存在。于是 B3 的
  时间形式对任意步数成立。

### 7.5 负向自检：N1 变体下归纳步必须失败

在 N1 的变体（去掉“时段未被预约”守卫）下重跑归纳步，必须得到 `sat`，并打印那个
“满足 `Inv`、走一步后违反”的状态。实际输出（`run.log`）：

```text
induction counterexample under N1 variant (Inv state, one step breaks B1):
t=0  status[a0]=Rejected  status[a1]=Interviewing  booking[a0]=s0  booking[a1]=none  exists[s0]=yes  exists[s1]=no
        action[0]: book(a1, s0)
t=1  status[a0]=Rejected  status[a1]=Interviewing  booking[a0]=s0  booking[a1]=s0  exists[s0]=yes  exists[s1]=no
```

`S_0` 满足 `Inv`（`a0` 预约 `s0`，`s0` 存在，且没有第二个申请预约它）；一步
`book(a1, s0)` 在缺少“时段未被预约”守卫时成功，`S_1` 中两个申请都预约 `s0`，
B1 被破坏，`Inv` 不再成立。这证明归纳步检查不是空转：去掉关键守卫后它会立刻变红。
测试 `test_induction_n1_relaxed_slot_guard_breaks_the_step` 还用纯 Python 重新计算
`Inv(S_0)`/`Inv(S_1)`，不依赖编码自证。

### 7.6 结论与边界

- 在抽象模型上，B1–B4 对**任意步数**成立：基例 + 归纳步覆盖所有可达状态，B2/B4 的
  单步性质覆盖每一步，`Persist` 把 B3 的状态形式提升为时间形式。
- 这一结论的可靠性完全取决于 §2/§3 的抽象与人工对照；`Inv` 的归纳性是对**编码**的
  性质，不是对 Python 代码的性质。若模型新增动作（例如 `create_slot`、职位绑定）或
  修改守卫，必须重新检查归纳步。
- 归纳证明不能替代 BMC 与负向演示：它们负责证明编码不是空真、给出可读反例，并展示
  去掉守卫后的真实失败；三类证据互相补充。

## 8. 自检：故意引入错误 → 测试变红 → 恢复

用仓库外脚本修改
[`booking_model.py`](../../tests/advanced/formal/booking_model.py) 的默认
`Variant`（或某条守卫），每次只改一处，运行
`python tests/advanced/run.py formal`，记录失败的测试，再用备份**逐字节**恢复
（恢复后 SHA-256 与原始文件一致）。生产代码全程未改动。

| 变异 | 期望变红 | 实际结果 |
|---|---|---|
| M1：`allow_booking_taken_slot=True`（去掉 book 的时段空闲守卫） | B1、归纳步 | `2 failed`：B1 的 BMC 测试 + `test_induction_step_preserves_invariant`（`Inv` 不再归纳保持） |
| M2：`skip_status_guard=True`（去掉 Interviewing 守卫） | B2 | `2 failed`：B2 的 BMC 测试 + `test_induction_b2_is_a_single_step_property` |
| M3：`skip_delete_booking_guard=True`（去掉 delete 的未预约守卫） | B3、归纳步 | `3 failed`：B3、归纳步、被拒绝的加强测试（变异后 Z3 可能选到一条先破坏 `Inv` 的轨迹，该测试的结构断言因此失败） |
| M4：`clear_booking_on_status_change=True`（状态改变清空预约） | B4、保持性 | `6 failed`：B3、B4、状态改变见证、`Persist`、B4 单步、被拒绝的加强测试（清空预约后该加强反而归纳成立，测试“期望 sat”因此变红——说明该加强恰恰与 B4 互斥） |
| M5：`book_guard` 恒假（模型过约束） | 可达性/负向控制 | `7 failed`：N1–N4、booking 与状态改变见证、N1 归纳步（`book` 不可能发生，归纳反例不存在）；B1–B4 与归纳义务反而保持 `unsat`——这正说明没有负向/可达性证据时 `unsat` 可能是空真 |

恢复后模型文件 SHA-256 与变异前一致，`git status` 干净。

确定性：两次独立运行（`run20`、`run21`）的 18 条记录除耗时外完全相同，全部
`trace_text` 逐字一致；`formal` 模式耗时分别为 5.320 s 与 5.245 s。

## 9. 局限

- **模型不是代码**：守卫是人工照着代码抄写的（§3），没有自动提取、没有精化关系。
  代码改动后模型可能过期；模型与代码的偏差只能靠代码评审发现。BMC 与归纳证明都只
  说明“抽象模型上成立”。
- **归纳的边界**：`k = 1` 归纳的可靠性依赖 `Inv` 对当前编码的转移关系确实归纳保持；
  新增动作/守卫后必须重跑归纳步。归纳证明的是安全性质（B1–B4），不涉及活性、公平性
  或并发。
- **有界的是 BMC**：BMC 仍只覆盖 6 步；它的作用是找反例与验证具体轨迹。任意步数
  的结论来自 §7 的归纳，而不是把 k 调大。
- **抽象掉时间与跨雇主**：未来时间、30 分钟时长、归属检查都当作恒真；跨雇主与
  “时段绑定其它职位”的场景不在模型里（§2.5）。
- **并发不在模型中**：FP-SCHED-3 的原子性由数据库行锁
  （`candidate/service.py:394-396` 的 `with_for_update`）加唯一约束
  （`employer/model.py:129-132`）保证；顺序转移系统无法表达两个事务的交错。
  B1/归纳证明的是**应用层守卫**在顺序执行下足够，数据库约束是第二道防线；并发抢同一
  时段的用例在 `tests/specialized/test_booking_schedules.py`（三线程抢一个时段，
  期望 `[201, 409, 409]` 且只落一条预约）里有覆盖，本模式不重复。
- **状态机是“规则级”的**：`set_status` 没有版本冲突、没有作业归属检查；`book` 没有
  作业保留检查。这些被列为假设，而不是被证明。
- **反例取值依赖 Z3 版本**：测试只断言“存在反例”和轨迹中的关键结构，不固定具体是
  `s0` 还是 `s1`，也不固定无关步骤；本文引用的轨迹是本机一次运行的输出。
- **没有辅助证明器**：“基例 + 归纳步 ⇒ 所有可达状态满足 Inv”是标准的元层面论证，
  不是经过机器检查的定理；SMT 只检查两个有限公式的不可满足性。
- **B3 时间形式的提升**是 `Inv` + `Persist` 对时间的元归纳，不是 Z3 直接证明的时序
  逻辑性质。

## 10. 复现与产物

```powershell
# 仓库根目录，项目虚拟环境（见 tests/advanced/README.md）
python tests/advanced/run.py formal --out "$env:TEMP\csc4801-formal"
python tests/run_tests.py
```

```sh
python tests/advanced/run.py formal --out "$TMPDIR/csc4801-formal"
python tests/run_tests.py
```

`--out` 必须在 checkout 之外且为新目录。P5 相关产物：

```text
<out>/formal/run.log                # pytest 汇总 + BMC 负向反例 + 归纳反例/加强反例
<out>/formal/junit.xml
<out>/formal/result.json            # 命令、退出码、formal 模式总耗时
<out>/formal/booking_bmc.json       # 18 条记录：
                                    #   BMC：B1–B4、N1–N4、3 个可达性见证
                                    #   归纳：基例、归纳步、B2/B4 单步、Persist、
                                    #         被拒绝的加强、N1 归纳负向
<out>/formal/matching_theory.json   # P4
<out>/formal/spec_to_code_pairs.json# P4
<out>/formal/bounded_T1..T7.json    # P4
```

自检产物（仓库外；下例是本机一次运行的路径）：

```text
<p5-evidence>/selfcheck/run_selfcheck.ps1          # 变异 → 运行 → 恢复
<p5-evidence>/selfcheck/M{1..5}-*.run.log          # 每次变异的 pytest 输出
<p5-evidence>/selfcheck/summary.json               # 退出码、失败测试列表
<p5-evidence>/run20,run21/formal/booking_bmc.json  # 两次确定性复跑的证据
```

本机实测：`M1`–`M5` 的退出码均为 1，期望的测试全部变红；每次运行后模型文件的
SHA-256 与变异前一致。两次独立运行（`run20`、`run21`）的 18 条记录除耗时外完全
相同；`formal` 模式耗时分别为 5.320 s 与 5.245 s，均远低于 60 s。
