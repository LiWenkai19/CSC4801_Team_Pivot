# FP-SCHED 预约状态机的有界模型检验（Z3）

本文件记录 `formal` 模式中 P5 的部分：把预约规则抽象成符号转移系统，用 Z3 做
`k = 6` 步的有界模型检验（BMC）。运行方式与 P4 相同：

```sh
python tests/advanced/run.py formal
```

`formal` 模式**不需要数据库**（目录里没有 `NEEDS_DB`），P4 的匹配公式证明与 P5 的
预约状态机检查在同一个 pytest 进程里运行。

## 1. 结论

- **B1–B4 全部 `unsat`**：在 6 步以内，从合法初始状态出发的**每一条**路径都不违反
  这四条性质（求解器找不到反例）。
- **N1/N2 为 `sat`**：分别去掉 `book` 的“时段未被预约”守卫、`delete_slot` 的
  “时段未被预约”守卫后，求解器给出可读的反例轨迹（§5）。N3/N4 是 B2/B4 的同类
  负向自检，用来证明这两个不变量也不是恒真。
- **非平凡性（可达性）**：另外验证了“存在一条路径真的创建了预约”“存在一条路径真的
  删除了空闲时段”“存在一条路径在预约之后修改状态且预约保留”三个见证，全部 `sat`。
  没有这一步，一个把 `book` 守卫写成恒假的模型也会让 B1–B4 全部 `unsat`（见 §7 的
  M5 变异）。
- `formal` 模式本机实测 **29 passed，模式耗时约 3.6–6.1 s**（P4 18 条 + P5 11 条，
  多次运行的范围；验收上限 60 s）。单次 Z3 查询 0.0005–0.009 s。

**边界必须说清楚**：证明对象是
[`booking_model.py`](../../tests/advanced/formal/booking_model.py) 里的**抽象转移系统**，
不是 `backend/app/` 的 Python 代码。模型与代码的联系来自 §3 的**人工守卫对照表**——
守卫是照着代码抄的，但没有任何自动提取或精化关系；代码改了模型不会自动跟着变。因此
本文所有“证明 / unsat”都应读作“在该抽象与 k=6 的范围内没有反例”，不能读作
“实现已被证明正确”。

## 2. 模型

文件：[`booking_model.py`](../../tests/advanced/formal/booking_model.py)。

### 2.1 规模与状态

| 项 | 取值 |
|---|---|
| 申请 | `a0`、`a1`，同一个雇主 |
| 时段 | `s0`、`s1`，都属于该雇主 |
| 步数 | `k = 6`，状态 `S_0 … S_6` |
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
预约 `s0`，B1 会在第一步之前就被违反，证明失去意义。

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
  是数据库层的性质，顺序转移关系无法表达（见 §8）。

## 3. 守卫 ↔ 代码对应

`candidate/service.py`、`interview/service.py` 与 `employer/service.py` 为行号来源
（本分支 `test/P5` 于 main `ddaece6` 之后）。

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

## 4. 检验结果（B1–B4）

每条性质取反后与初始状态、转移约束一起交给 `z3.Solver`；`unsat` 表示
“6 步内不存在违反对应性质的路径”。

| ID | 性质（对所有 `t ≤ 6`） | 需求条款 | 结果 | 单次查询耗时 |
|---|---|---|---|---|
| B1 | 不存在两个申请同时预约同一时段：`AtMost(booking[a0][t]=s, booking[a1][t]=s, 1)` | FP-SCHED-2 | `unsat` | 0.0065 s |
| B2 | 若 `t` 步 `book(a, s)` 的守卫成立（= 本步真的创建了预约），则 `status[a][t] = Interviewing` | FP-SCHED-2 | `unsat` | 0.0005 s |
| B3 | 若 `t` 步某时段已被预约，则对任意 `t' ≥ t` 该时段仍存在 | FP-SCHED-1 | `unsat` | 0.0090 s |
| B4 | 若 `t` 步改变任一申请 `a` 的状态且 `booking[b][t] ≠ none`，则 `booking[b][t+1] = booking[b][t]`（对任意申请 `b`） | FP-SCHED-2 / FP-EMP-3 | `unsat` | 0.0048 s |

关于 B2 的诚实说明：B2 的证明内容一部分是“`book` 守卫里确实写了
`status = Interviewing`”，另一部分（也是真正有信息量的部分）是**没有别的动作能创建
预约**——转移关系里只有 `book` 会写 `booking`，`set_status`、`delete_slot`、`noop`
都不写。N3 说明去掉状态守卫后 B2 立刻可被违反，因此这个 `unsat` 不是纯粹的恒真式。

B3 的方向是“曾经被预约过 → 之后一直存在”，而不是“当前仍被预约 → 存在”。这样即使
（错误地）允许清除预约，只要之后删除了该时段，B3 仍会报警——§7 的 M4 变异正是这种情况，
它会同时弄红 B3 和 B4。

B4 对“改变任一申请的状态”量化（不只改变持有预约的那个申请），因此它也覆盖“改
`a0` 的状态不能碰 `a1` 的预约”。

## 5. 负向演示：放宽守卫后求解器给出反例

每个负向演示只改一个守卫；期望 `sat`，并把 `model` 渲染成逐状态、逐动作的序列。
`--out` 下的 `formal/booking_bmc.json` 保存同一份 `trace_text`，`formal/run.log`
也会打印（测试通过 pytest 的 capture manager 暂时关闭捕获后写出）。

### N1：去掉 `book` 的“时段未被预约”守卫 → B1 被违反

```text
B1 counterexample (variant: allow_booking_taken_slot):
t=0  status[a0]=Pending  status[a1]=Pending  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[0]: set_status(a0, Interviewing)
t=1  status[a0]=Interviewing  status[a1]=Pending  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[1]: set_status(a0, Rejected)
t=2  status[a0]=Rejected  status[a1]=Pending  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[2]: set_status(a1, Interviewing)
t=3  status[a0]=Rejected  status[a1]=Interviewing  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[3]: book(a1, s1)
t=4  status[a0]=Rejected  status[a1]=Interviewing  booking[a0]=none  booking[a1]=s1  exists[s0]=yes  exists[s1]=yes
        action[4]: set_status(a0, Interviewing)
t=5  status[a0]=Interviewing  status[a1]=Interviewing  booking[a0]=none  booking[a1]=s1  exists[s0]=yes  exists[s1]=yes
        action[5]: book(a0, s1)
t=6  status[a0]=Interviewing  status[a1]=Interviewing  booking[a0]=s1  booking[a1]=s1  exists[s0]=yes  exists[s1]=yes
```

两个申请最终都预约了 `s1`：`action[3]` 先把 `s1` 分给 `a1`，`action[5]` 又把同一时段分给
`a0`（这正是被删掉的守卫本该拒绝的）。测试
`test_n1_without_slot_free_guard_two_applications_share_a_slot` 从轨迹里断言：
恰好 2 次**成功**的 `book`、申请集合为 `{a0, a1}`、两次指向同一时段，且轨迹中**存在**
两个申请同时绑定同一时段的状态。

### N2：去掉 `delete_slot` 的“时段未被预约”守卫 → B3 被违反

```text
B3 counterexample (variant: skip_delete_booking_guard):
t=0  status[a0]=Pending  status[a1]=Pending  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[0]: set_status(a0, Interviewing)
t=1  status[a0]=Interviewing  status[a1]=Pending  booking[a0]=none  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[1]: book(a0, s0)
t=2  status[a0]=Interviewing  status[a1]=Pending  booking[a0]=s0  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[2]: set_status(a1, Interviewing)
t=3  status[a0]=Interviewing  status[a1]=Interviewing  booking[a0]=s0  booking[a1]=none  exists[s0]=yes  exists[s1]=yes
        action[3]: book(a1, s1)
t=4  status[a0]=Interviewing  status[a1]=Interviewing  booking[a0]=s0  booking[a1]=s1  exists[s0]=yes  exists[s1]=yes
        action[4]: set_status(a0, Rejected)
t=5  status[a0]=Rejected  status[a1]=Interviewing  booking[a0]=s0  booking[a1]=s1  exists[s0]=yes  exists[s1]=yes
        action[5]: delete_slot(s0)
t=6  status[a0]=Rejected  status[a1]=Interviewing  booking[a0]=s0  booking[a1]=s1  exists[s0]=no  exists[s1]=yes
```

`a0` 仍持有 `s0` 的预约，但 `s0` 在 `action[5]` 之后不再存在。测试
`test_n2_without_delete_guard_a_booked_slot_is_deleted` 从轨迹里断言：先有成功预约、
再有成功删除，且轨迹中存在“`t` 步已预约、某个 `t' ≥ t` 时该时段已删”的状态对。
轨迹里与违规无关的动作（例如 `a1` 的预约）不影响反例。

### N3/N4：B2/B4 的负向自检

| ID | 变异 | 期望 | 轨迹要点 |
|---|---|---|---|
| N3 | `book` 不再检查 `status = Interviewing` | `sat`（B2 被违反） | `action[5]: book(a0, s1)` 发生在 `status[a0] = Pending` 时；测试从轨迹断言“成功的 `book` + 前置状态 ≠ Interviewing” |
| N4 | 状态改变时把申请预约重置为 `none` | `sat`（B4 被违反） | `t=2` 时 `booking[a0] = s1`，`action[2]: set_status(a0, Interviewing)` 之后 `booking[a0]` 变为 `none`（变异对“改成相同状态值”也生效） |

完整轨迹同样在 `formal/booking_bmc.json` 和 `run.log` 里。

## 6. 为什么 k = 6

- **反例所需的最短步数**：N1 需要“两次改状态 + 两次预约”，最少 4 步；N2 需要
  “改状态 + 预约 + 删除”，最少 3 步；N3 最少 1 步（初始 `Pending` 直接 `book`）；
  N4 最少 3 步（改状态、预约、再改状态）。
- **覆盖组合而不膨胀**：6 步足以让一个预约经历“创建 → 状态改变 → 尝试删除”的完整
  生命周期，并且还有余量容纳与违规无关的动作（最终反例轨迹里也确实出现了这类步骤）。
- **可判定规模**：每个状态 4² × 3² × 2² = 576 种取值、15 个动作、7 个状态，Z3 每次
  查询都在 10 ms 量级（§4）；`formal` 模式整体（含 pytest 启动与 P4 测试）本机
  3.6–6.1 s，远低于 60 s 上限。
- **有界性的代价**：`k = 6` 只排除“6 步以内的反例”；需要更长前缀才能触发的缺陷
  不在覆盖范围内。BMC 不能替代归纳不变式证明。

## 7. 自检：故意引入错误 → 测试变红 → 恢复

用仓库外脚本修改
[`booking_model.py`](../../tests/advanced/formal/booking_model.py) 的默认
`Variant`（或某条守卫），每次只改一处，运行
`python tests/advanced/run.py formal`，记录失败的测试，再用备份**逐字节**恢复
（恢复后 SHA-256 与原始文件一致）。生产代码全程未改动。

| 变异 | 期望变红 | 实际结果 |
|---|---|---|
| M1：`allow_booking_taken_slot=True`（去掉 book 的时段空闲守卫） | B1 | `1 failed`：`test_b1_slot_has_at_most_one_booking` |
| M2：`skip_status_guard=True`（去掉 Interviewing 守卫） | B2 | `1 failed`：`test_b2_booking_requires_interviewing_status` |
| M3：`skip_delete_booking_guard=True`（去掉 delete 的未预约守卫） | B3 | `1 failed`：`test_b3_booked_slot_is_never_deleted` |
| M4：`clear_booking_on_status_change=True`（状态改变清空预约） | B4 | `3 failed`：B4、B3、`test_booking_survives_a_reachable_status_change`（见下） |
| M5：`book_guard` 恒假（模型过约束） | 可达性见证 | `6 failed`：4 个 N 负向演示、booking 见证、状态改变见证（B1–B4 反而保持 `unsat`——这正说明没有可达性见证时 `unsat` 可能是空真） |

M4 额外弄红 B3 与状态改变见证的原因：状态改变清空预约后，“曾经被预约”的时段随即可被
删除，于是 B3（`t` 步被预约 → 之后一直存在）被违反；状态改变见证也因预约没有保留而
失败。这些是变异的真实后果，不是误报。N1/N2 在 M4 下仍然通过，因为它们只断言各自
负向演示的违规结构（同时持有同一时段、已预约时段后来消失），不依赖“预约不会被清除”
这一被变异的假设。

## 8. 局限

- **有界**：只检查 6 步以内。长度 7 步及以上的反例不会被发现；`unsat` 不是无界证明。
- **模型不是代码**：守卫是人工照着代码抄写的（§3），没有自动提取、没有精化关系。
  代码改动后模型可能过期；模型与代码的偏差只能靠代码评审发现。
- **抽象掉时间与跨雇主**：未来时间、30 分钟时长、归属检查都当作恒真；跨雇主与
  “时段绑定其它职位”的场景不在模型里（§2.5）。
- **并发不在模型中**：FP-SCHED-3 的原子性由数据库行锁
  （`candidate/service.py:394-396` 的 `with_for_update`）加唯一约束
  （`employer/model.py:129-132`）保证；顺序转移系统无法表达两个事务的交错。
  B1 证明的是**应用层守卫**在顺序执行下足够，数据库约束是第二道防线；并发抢同一
  时段的用例在 `tests/specialized/test_booking_schedules.py`（三线程抢一个时段，
  期望 `[201, 409, 409]` 且只落一条预约）里有覆盖，本模式不重复。
- **状态机是“规则级”的**：`set_status` 没有版本冲突、没有作业归属检查；`book` 没有
  作业保留检查。这些被列为假设，而不是被证明。
- **反例取值依赖 Z3 版本**：测试只断言“存在反例”和轨迹中的关键结构（同一时段、删除
  已预约时段等），不固定具体是 `s0` 还是 `s1`，也不固定无关步骤。
- **没有 Hoare 逻辑证明**：SMT 只检查一个有限的转移关系；没有对 Python 函数做符号
  执行或最弱前置条件演算。

## 9. 复现与产物

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
<out>/formal/run.log                # pytest 汇总 + B1..B4 负向演示的反例轨迹
<out>/formal/junit.xml
<out>/formal/result.json            # 命令、退出码、formal 模式总耗时
<out>/formal/booking_bmc.json       # 11 条记录：B1-B4、N1-N4、3 个可达性见证
                                    #（含 trace 与 trace_text）
<out>/formal/matching_theory.json   # P4
<out>/formal/spec_to_code_pairs.json# P4
<out>/formal/bounded_T1..T7.json    # P4
```

自检产物（仓库外；下例是本机一次运行的路径）：

```text
<p5-evidence>/selfcheck/run_selfcheck.ps1          # 变异 → 运行 → 恢复
<p5-evidence>/selfcheck/M{1..5}-*.run.log          # 每次变异的 pytest 输出
<p5-evidence>/selfcheck/summary.json               # 退出码、失败测试列表
<p5-evidence>/run12,run13/formal/booking_bmc.json  # 两次确定性复跑的证据
```

本机实测：`M1`–`M5` 的退出码均为 1，期望的测试全部变红；每次运行后模型文件的
SHA-256 与变异前一致。两次独立运行（`run12`、`run13`）的记录除耗时外完全相同：11 条
结果的 `sat/unsat` 与全部 `trace_text` 逐字一致；这两次 `formal` 模式耗时分别为
4.019 s 与 3.564 s，提交后按验收命令直接运行（不传 `--out`）的一次为 5.493 s——同一台
机器上的正常抖动，均远低于 60 s。
