# LLM 盲测生成与断言质量评估（P10）

本文件是 P10 的实验报告，对应讲义 L14 Exercise 1（AI-assisted test generation）
与 Exercise 3（assertion writing / quality evaluation）。实验对象是本仓库的三个函数：

| ID | 目标 | 类型 | 契约 | 生成测试 |
|---|---|---|---|---|
| F1 | `app.employer.matching.match_score` | 纯函数 | [`contracts/F1.md`](../../tests/advanced/experiments/llm_blind/contracts/F1.md) | [`generated/test_F1.py`](../../tests/advanced/experiments/llm_blind/generated/test_F1.py) |
| F2 | `app.candidate.service.book` | 服务层（会话替身） | [`contracts/F2.md`](../../tests/advanced/experiments/llm_blind/contracts/F2.md) | [`generated/test_F2.py`](../../tests/advanced/experiments/llm_blind/generated/test_F2.py) |
| F3 | `SkillTagPicker` 的 HTML 转义 | React 组件 | [`contracts/F3.md`](../../tests/advanced/experiments/llm_blind/contracts/F3.md) | [`generated/test_F3.mjs`](../../tests/advanced/experiments/llm_blind/generated/test_F3.mjs) |

**结论先行。**

- 冻结运行（生成后直接跑，未改测试）：F3 11/11 通过；F1 在 collection 阶段因生成器
  写错 parametrize id 数量而中断；F2 19/19 因生成器构造的 `User` 漏了 `role` 而被
  服务层的角色检查拒绝。**这三类都不是业务缺陷。**
- 修正生成器的 setup 错误后（期望值一处未改），最终运行 **123 passed / 1 skipped /
  0 failed**。唯一的 skip 是契约明确不定义的输入类型，不是隐藏失败。
- 与手写测试比较：生成测试在 F1 的归一化/边界、F2 的缺失职位/29–31 分钟/状态组合/
  检查顺序上覆盖更宽；手写测试在可预约时段过滤、HTTP 状态映射、通用
  `SQLAlchemyError` 回滚、F3 的 label 关联上有独有覆盖。
- 五个手写变异体：生成测试杀掉 **5/5**，手写测试杀掉 **3/5**。手写测试幸存的两个
  变异体分别暴露了：归一化用例把带空格和不带空格的技能混在同一列表（因此观察不到
  `strip()` 被删除），以及缺少“职位不存在”路径。
- **没有发现业务缺陷**，因此没有 `docs/advanced_testing/findings/P10.md`。实验中真正暴露的
  问题是“LLM 生成测试本身的 setup/API 错误”和“手写测试的断言盲区”，不是生产 bug。

---

## 1. 协议、冻结与 commit 顺序

### 1.1 盲测协议

1. 主会话只读 `docs/REQUIREMENTS.md`、`SPEC.md` 与目标签名，写
   `contracts/F{1,2,3}.md`；每个契约含手算期望值和歧义清单。
2. 三个**独立子代理**各自只收到：一份契约、一份 prompt、目标 import 路径、测试
   harness。明确禁止它们打开 `backend/app/`、`frontend/src/` 或任何已有测试，也禁止
   在冻结前执行目标。
3. 子代理交回后，先做语法检查（`py_compile` / `node --check`），随后 commit
   **生成文件**；commit 信息含 “generated before reading implementation”。
4. 冻结后才运行 `pytest` / `node --test`，记录每个 case；之后才阅读实现做归因。
5. 归因后仍不修改期望值；只修生成器的 setup 错误，并单独 commit、在下面逐条披露。

### 1.2 commit 顺序（本分支）

| # | commit | 内容 | 与实现阅读/运行的关系 |
|---|---|---|---|
| 1 | `c0859d0208fd5c20c2fa90e786538db8f6732bb8` | 契约、prompt、harness、**三个生成测试** | 冻结；此时未运行、未完整阅读实现 |
| 2 | `467a6f279365fb6d2190d3436e83bc7ce83603d6` | 修 F1 parametrize id 数、F2 合成 `User` 的 `role` | 冻结运行之后；只改 setup，不改期望值 |
| 3 | `e76641feaecb3d17a8a46912e596916409d59cf6` | F2 IntegrityError 用例补“并发赢家”行 | 冻结运行之后；只改测试替身状态，不改期望值 |
| 4 | 本报告所在 commit | `results.json`、`mutation/results.json`、本报告 | 实验收口 |

`git log --follow` 对 `generated/` 的路径可复核：生成文件首次出现在 #1，晚于它的
#2/#3 只修 setup。

### 1.3 协议偏离（必须披露）

任务原文要求主会话写契约时“只读函数签名（`def` 那一行与 docstring）”。我在提取
`book` 的签名时，用 AST 辅助脚本额外打印了该函数的 `raise` 子句和模块导入，用来在
契约里写出三个公开异常类名（`NotFoundError` / `ForbiddenError` / `ConflictError`）与
部分公开消息。**没有读取函数体逻辑**，生成子代理也完全没有接触源码；但这确实超出了
“只读签名与 docstring”的字面范围。为了让实验可复核，这里如实记录。冻结运行之后，
主会话才完整阅读实现与手写测试。

### 1.4 复现命令与产物

```powershell
# 最终运行（仓库根目录；需要 frontend/node_modules）
.\.venv\Scripts\python.exe tests\advanced\experiments\llm_blind\run_experiment.py `
  --out "$env:TEMP\p10-llm-blind-final" `
  --node-modules frontend\node_modules

# 五个变异体
.\.venv\Scripts\python.exe tests\advanced\experiments\llm_blind\mutation\run_mutants.py `
  --out "$env:TEMP\p10-mutants"

# F3 负向自检
$env:NODE_PATH = "$PWD\frontend\node_modules"
node tests\advanced\experiments\llm_blind\mutation\f3_selfcheck.mjs

# 必测套件仍须全绿
.\.venv\Scripts\python.exe tests\run_tests.py
```

本次证据（仓库外）：

- 冻结运行：`C:\Users\mdrakr\AppData\Local\Temp\p10-llm-blind-20261126-100242`
- 修正后最终运行：`C:\Users\mdrakr\AppData\Local\Temp\p10-llm-blind-final2-20261126-100934`
- 变异矩阵：`C:\Users\mdrakr\AppData\Local\Temp\p10-mutants-fixed-20261126-100720`
- 汇总：`tests/advanced/experiments/llm_blind/results.json`
- 变异汇总：`tests/advanced/experiments/llm_blind/mutation/results.json`

---

## 2. F1 — `match_score`

### 2.1 需求与契约

需求：`docs/REQUIREMENTS.md` **FP-MATCH-1**；`SPEC.md` “Matching Algorithm and Skill
Storage”。契约把输入、归一化、输出、边界、歧义写死，并给出四个必测例子：

| 候选人技能 | 必需技能 | 手算 | 期望 |
|---|---|---|---:|
| `["Python","SQL"]` | `["Python","SQL"]` | k=2,n=2; 100*2//2 | 100 |
| `["Python"]` | `["Python","SQL"]` | k=1,n=2; 100*1//2 | 50 |
| `["Rust"]` | `["Python","SQL"]` | k=0,n=2; 100*0//2 | 0 |
| 任意 | `[]` | n=0 特例 | 100 |

另一个手算归一化例子：候选 `[" SQL ","sql","Python",""]`、必需
`["SQL","  ","python "]` → C=R={sql,python} → 100。

### 2.2 生成测试与运行结果

生成文件 709 行、22 个测试函数、94 个收集 case。覆盖：四个必测例子、空列表边界、
`len(R)=3/4/6/7/8/9/11/12/13/16/40/100/200` 的 floor 扫描、空白/大小写/重复/空串
归一化、顺序与重复不变性、Unicode 与符号、`type(result) is int`、0..100、
输入不被修改、重复调用确定性。唯一 skip 是 `None`/裸字符串/非 str 元素——契约明确
不定义，记录为歧义 A1。

| 运行 | cases | passed | failed | skipped |
|---|---:|---:|---:|---:|
| 冻结运行 | 1（collection error） | 0 | 1 | 0 |
| 修正后最终运行 | 94 | 93 | 0 | 1 |

冻结运行的失败归因：

- 症状：`In test_empty_list_boundaries: 9 parameter sets specified, with different
  number of ids: 10`。
- 归因：**生成错误**（参数字典有 9 行，`ids` 写了 10 个），不是实现问题。
- 修复：删掉多余的 `empty-candidate-only-100` id（commit `467a6f2`）；期望值未动。
- 为什么可信：修复后 93 个断言全部通过，包括 `str.lower()` 不是 `casefold()`、
  内部空白保留、`|R|=0` 按归一化后的集合判断等容易被实现“顺手改掉”的边界。

### 2.3 与手写测试比较

手写文件：`tests/unit/test_matching.py`，4 个测试函数、8 个 case；其中直接测
`match_score` 的只有 1 个函数 × 5 个参数（100/50/0/100/66），另外 3 个是推荐排序。

| 分区 | 生成测试 | 手写测试 | 说明 |
|---|---|---|---|
| FP-MATCH-1 四例 | ✅ | ✅ | 都覆盖 |
| `len(R)=3, k=2 → 66` | ✅ | ✅ | 手写有 66 |
| 空候选人 + 非空必需 | ✅ | ❌ | 手写没有 |
| 两边都空 | ✅ | ❌ | 手写没有 |
| 空白-only 必需技能 | ✅ | ❌ | 手写没有 |
| 空白/大小写/重复 | ✅ 分离用例 | ⚠️ 合并且混淆 | 见下 |
| 顺序/重复不变性 | ✅ | ❌ | 手写没有 |
| Unicode / 符号 | ✅ | ❌ | 手写只有 ASCII |
| `lower()` vs `casefold()` | ✅ | ❌ | 手写没有 |
| 精确 `int` 类型与 0..100 | ✅ | ❌ | 手写只断言相等 |
| 输入不被修改/确定性 | ✅ | ❌ | 手写没有 |

**独有发现（测试质量，不是业务 bug）**：手写的归一化用例构造候选为
`[" " + s.upper() + " " for s in skills] + skills + [""]`，即把“带空格副本”和
“不带空格的原值”放进同一个列表。这样即使实现删掉 `.strip()`，不带空格的原值仍会
命中必需技能，分数不变。变异体 `F1_M3_drop_trim` 因此**只被生成测试杀死**（13 个
生成 case 变红，手写 8 个 case 全绿）。这是本次实验里最具体的“手写断言不够锐利”
证据。

### 2.4 归因结论

F1 没有实现 bug。冻结运行的失败是 LLM 生成器的 parametrize 书写错误；修正后所有
契约断言通过。生成测试比手写测试多覆盖了归一化、类型、边界和 Unicode 分区，并在
变异实验中多杀一个变异体。

---

## 3. F2 — `book`

### 3.1 需求与契约

需求：`docs/REQUIREMENTS.md` **FP-SCHED-2**、**FP-SCHED-3**；`SPEC.md` “Interview
Scheduling and Booking Transaction”。契约列出 11 条资格条件、成功副作用、拒绝时的
“异常类型 + 状态未改变”义务，以及 `IntegrityError` 的唯一约束路径。

三个手算场景：

| 场景 | 状态 | 期望 |
|---|---|---|
| S1 | 本人申请、`Interviewing`、无预约；未来 30 分钟空闲时段，`slot.job_id=None` | 成功；`BookingPublic(slot_id=s1, 10:00Z..10:30Z)`；`slot.job_id=j1`；一条 `Booking(a1,s1)`；一次 commit |
| S2 | 同 S1，但状态 `Pending` | `ConflictError`；commit 0 次；状态/版本/`slot.job_id` 不变 |
| S3 | 同 S1，但申请属于另一个候选人 | `ForbiddenError`；commit 0 次；状态不变 |

### 3.2 生成测试与运行结果

生成文件 549 行、19 个 case（16 个函数，含参数化）。覆盖：成功、`slot.job_id`
等于同一职位、缺失申请、他人申请、`Pending`/`Rejected`/`Accepted`、申请已有预约、
缺失时段、缺失职位、时段属于其他雇主、过去时段、29/31 分钟、时段已预约、时段绑定
其他职位、`IntegrityError` → 回滚 + `ConflictError("Slot already booked")`，以及
“他人申请优先于错误状态”“申请已有预约优先于缺失时段”两个顺序用例。

| 运行 | cases | passed | failed |
|---|---:|---:|---:|
| 冻结运行 | 19 | 0 | 19 |
| 修正后最终运行 | 19 | 19 | 0 |

冻结运行的失败归因：

1. **19/19 同一个生成器 setup 错误。** 症状：
   `app.users.service.CandidateRoleRequiredError: Candidate role required`。
   生成器的 `_make_user()` 只构造了 `User(id=...)`，没有 `role`；服务层的角色检查
   （`_require_candidate`）正确地拒绝了它。归因：**生成错误（API 用错）**，不是
   实现 bug。修复：`role=Role.Candidate`（commit `467a6f2`）。
2. **修正后仍剩 1 个 IntegrityError 用例失败。** 生成器直接给
   `session.commit` 注入 `IntegrityError`，但没有让“并发赢家”的 `Booking` 在回滚后
   可见；实现查不到冲突行，按设计重新抛出未分类的 `IntegrityError`。归因：
   **测试替身缺口 + 契约歧义**（真实数据库在唯一约束冲突后应能看到已提交的赢家，
   但会话替身没有模拟这一点），不是实现 bug。修复：替身增加
   `late_slot_bookings`，在 commit 失败时把赢家行加入可见集合（commit `e76641f`）。

### 3.3 与手写测试比较

手写文件：`tests/unit/test_scheduling.py`，32 个 case；其中直接测 `book` 的 13 个
（成功 1、拒绝 8、冲突契约 3、通用提交失败 1），其余 19 个测时段创建/删除/列表/
路由。

| 分区 | 生成测试 | 手写测试 | 说明 |
|---|---|---|---|
| 合格预约成功 | ✅ | ✅ | 都断言 booking 字段与 commit |
| `slot.job_id` 已等于本职位 | ✅ | ❌ | 手写没有 |
| 缺失申请 | ✅ | ❌ | 手写没有 |
| 他人申请 | ✅ | ✅ | |
| `Pending` / `Rejected` / `Accepted` | ✅ 全 | ⚠️ 只有 Pending | |
| 申请已有预约 | ✅ | ✅ | |
| 缺失时段 | ✅ | ✅ | |
| **缺失职位** | ✅ | ❌ | 手写没有 |
| 时段属于其他雇主 | ✅ | ✅ | |
| 过去时段 | ✅ | ✅ | |
| 29 / 31 分钟 | ✅ | ⚠️ 只有 60 分钟 | 手写能杀“时长检查”，但不测精确 30 分钟边界 |
| 时段已预约 | ✅ | ✅ | |
| 时段绑定其他职位 | ✅ | ❌ | 手写没有 |
| `IntegrityError` 转 slot conflict | ✅ | ✅ | 手写还覆盖 application/unknown 分支 |
| 通用 `SQLAlchemyError` 回滚 | ❌ | ✅ | 手写独有 |
| 可预约时段过滤 | ❌ | ✅ | 不属于 `book`，手写独有 |
| HTTP 403/404/409 映射 | ❌ | ✅ | 不属于 `book`，手写独有 |
| 检查顺序（双故障） | ✅ | ❌ | 生成独有 |
| 拒绝后完整状态快照 | ✅ 更广 | ⚠️ 部分 | 生成断言 status/version/slot.job_id/commit/add；手写断言 status/starts/ends + add/commit |

**独有发现（测试质量）**：手写测试没有“职位不存在”的 case，所以
`F2_M5_skip_missing_job_check` 只被生成测试杀死；手写 32 个 case 全绿。生成的
“缺失职位”用例直接补上了这个分区。

### 3.4 归因结论

F2 没有实现 bug。冻结运行的 19 个失败全部是生成器的 `User` setup 错误；修正后
18/19 通过，最后一个失败是会话替身没有模拟并发赢家，补上后 19/19。生成测试在
`book` 的资格条件与边界上覆盖更全；手写测试在 session 层之外（时段过滤、路由映射、
通用 SQLAlchemyError）有独有覆盖。

---

## 4. F3 — `SkillTagPicker` 转义

### 4.1 需求与契约

需求：`docs/REQUIREMENTS.md` **FP-SEC-3**；`SPEC.md` “Security Controls → Access
control and safe rendering”。契约要求：技能名作为文本而不是标记输出；`< > & " '`
被 React 转义；不得出现原始 `<script`；属性里的副本也要转义；普通 Unicode 保留。

三个手算期望：

| 输入 | 手算转义 | 期望片段 |
|---|---|---|
| `<script>alert(1)</script>` | `<`→`&lt;`, `>`→`&gt;`，字母/括号/斜杠不变 | `&lt;script&gt;alert(1)&lt;/script&gt;`，且无 `/<script(?:\s|>)/i` |
| `onmouseover="x"` | 每个 `"`→`&quot;` | `onmouseover=&quot;x&quot;`，且无原始 `onmouseover="x"` |
| `a&b` | `&`→`&amp;` | `a&amp;b`，且无原始 `a&b` |

### 4.2 生成测试与运行结果

生成文件 207 行、11 个 `node:test` case。覆盖：H1 script 载荷、H2 闭合标签、H3
混合大小写、H4 双引号属性逃逸、H5 `&`、H6 字面实体、B1 空列表、B2 单字符、B3
纯元字符（含 `'` → `&#x27;`）、V1 Unicode、V2 标签样文本。调用约定与
`frontend/tests/rendering.unit.mjs` 相同：TypeScript 转译真实 TSX、
`renderToStaticMarkup` 渲染、在 `LanguageProvider` 内使用
`CandidateSkillPicker`。

| 运行 | cases | passed | failed |
|---|---:|---:|---:|
| 冻结运行 | 11 | 11 | 0 |
| 最终运行 | 11 | 11 | 0 |

### 4.3 与手写测试比较

手写链路：`tests/unit/test_rendering.py` 1 个 pytest wrapper，内部运行
`frontend/tests/rendering.unit.mjs` 的 3 个 node case（script 转义、Unicode/引号、
label/id 关联）。

| 分区 | 生成测试 | 手写测试 | 说明 |
|---|---|---|---|
| `<script>alert(1)</script>` | ✅ | ✅ | |
| Unicode + 引号 | ✅ | ✅ | |
| label 指向实际 input | ❌ | ✅ | 手写独有 |
| 闭合标签 `</script>` | ✅ | ❌ | |
| 混合大小写 `<ScRiPt>` | ✅ | ❌ | |
| 字面实体 `&lt;` | ✅ | ❌ | |
| 纯元字符 `'` | ✅ | ❌ | |
| 空列表 | ✅ | ❌ | |
| 标签样文本 `<b>bold</b>` | ✅ | ❌ | |
| 双引号属性逃逸 | ✅ | ✅（部分） | 手写检查 `&quot;` |
| `&amp;` | ✅ | ✅ | 手写检查 `&amp;` |

F3 没有失败可归因；11 个生成 case 全绿，且比手写多覆盖 7 类敌意/边界输入。手写
独有的是 label/id 关联，属于可访问性而非转义。

### 4.4 F3 的负向自检

`mutation/f3_selfcheck.mjs` 把同一组三条转义断言应用到：

1. 真实组件渲染 → 必须通过；
2. 一个故意使用 `dangerouslySetInnerHTML` 的“不安全组件”渲染同一载荷 → 必须被
   断言拒绝。

运行结果：`real render passed; unsafe render rejected`。这证明 F3 的 oracle 不是
恒真——如果组件真的输出原始标记，测试会红。

---

## 5. 断言杀伤力（五个手写变异体）

P7 的 mutmut 未合并，因此按 L14 slide 28 手写 5 个变异体，通过
`monkeypatch`/源码替换注入到模块属性（不修改 `backend/app`）。每个变异体在独立子
进程里运行，baseline 每个 suite 先跑一遍全绿，再跑变异体。定义：**killed = suite 中
至少一个 case 失败**。

| 变异体 | 类别 | 生成测试 | 手写测试 |
|---|---|---|---|
| `F1_M1_floor_round`：`//` → `round()` | 算术 | ✅ 27 个 case 失败 | ✅ 1 个 case 失败 |
| `F1_M2_empty_required_zero`：100 → 0 | 常量/边界 | ✅ 6 个 | ✅ 1 个 |
| `F1_M3_drop_trim`：删除 `.strip()` | 去掉一项检查 | ✅ 13 个 | ❌ 0 个（幸存） |
| `F2_M4_skip_duration_check`：禁用 30 分钟检查 | 去掉一项检查 | ✅ 2 个 | ✅ 1 个（60 分钟 case） |
| `F2_M5_skip_missing_job_check`：缺失职位不再 `NotFoundError` | 去掉一项检查 | ✅ 1 个 | ❌ 0 个（幸存） |
| **合计** | | **5/5** | **3/5** |

关键观察：

- 生成测试的 5/5 不是因为它“更多”，而是因为它把每个变异体对应的**最小边界**单独
  建了 case（空白-only、29/31 分钟、缺失职位）。
- 手写测试的 3/5 暴露了两个具体的断言弱点：归一化用例的输入混入了不带空格的副本；
  `book` 的拒绝矩阵没有缺失职位。
- 变异体注入本身是自检：故意引入错误 → 测试变红 → 子进程结束即恢复；生产文件
  从未被修改。第一次矩阵曾出现 `past` 的假失败，原因是变异函数用了复制的 globals
  字典，导致测试对 `utc_now` 的 monkeypatch 失效；改为 exec 进真实模块 globals 后
  消失。最终矩阵是修正后的结果。

---

## 6. L14 slide 30：通过 ≠ 正确；我会额外跑的两项检查

**为什么“十个生成测试都通过”不能推出代码正确：**

1. 通过只说明这些输入上的输出与 oracle 一致；oracle 本身来自契约，契约漏掉的
   分区（例如本实验手写测试漏掉的“缺失职位”）不会被测试发现。
2. 生成测试与生成它的模型共享同一套假设和误读；本实验冻结运行的 F2 失败正是
   “测试自己写错 setup”，而不是代码错。反过来说，测试全绿也可能只是测试没碰到
   错误路径。
3. F2 用的是会话替身，不执行真实 SQL：行锁、唯一约束、并发提交都未被证明；
   F3 用的是 `renderToStaticMarkup`，不执行浏览器 JavaScript。它们证明的是契约
   层行为，不是端到端安全/并发。
4. 变异实验给出了直接反例：手写套件在 2/5 个非等价变异体下仍全绿。生成套件也可能
   在对它未覆盖的变异体下全绿；“全绿”不是充分条件。

**我会额外运行的两项检查：**

1. **更广的变异测试**（P7 的 mutmut 或同等的变异器）：不是只看测试是否通过，而是
   看 **killed / non-equivalent mutants**，并逐个检查幸存者。本实验的 5 个变异体
   只是抽样，覆盖不了 `book` 的锁顺序、`normalize_skills` 的其余分支等。
2. **真实一次性 PostgreSQL 的并发/差分集成检查**：用两个真实连接并发预约同一
   时段，验证恰好一个成功、另一个得到 `409 Slot already booked`、数据库只有一条
   `booking`；同时用独立 SQL/集合 oracle 对 `match_score` 做差分。这能验证会话
   替身和 `renderToStaticMarkup` 证明不了的事务与存储行为。

---

## 7. 有效性与限制

- **生成器不是人类**：三个子代理仍是 LLM；它们可能带有对本项目常见实现的先验。
  协议保证的是“没有读本仓库实现”，不是“没有世界知识”。
- **主会话的契约阶段有小偏离**：见 §1.3。异常类名是从 `book` 的 `raise` 子句提取
  的；生成子代理没有看到这些源码。冻结 commit 仍早于完整实现阅读与任何运行。
- **post-freeze 修复**：`467a6f2` 修 parametrize id 与 `User.role`；`e76641f` 给
  F2 替身补并发赢家。三处都只改 setup，没有改任何 expected value；原始冻结运行
  的数字仍保留在 §2–§3 和 `results.json` 的 `frozen_run` 里。
- **F2 的替身**：没有真实数据库，不能证明 FP-SCHED-3 的数据库原子性；它验证的是
  服务层的检查、异常类型、rollback 调用和可观察状态。
- **F3 的渲染**：`renderToStaticMarkup` 不做浏览器解析/执行；它证明字符串层面的
  转义，不是完整 XSS 证明。
- **变异测试的粒度**：手写 suite 按整个 `test_scheduling.py`（32 case）计 kill，
  不是只挑 13 个 book case；生成 suite 按整个 `test_F2.py`（19 case）。这对双方
  一致：任一 case 失败即 killed。
- **确定性**：`PYTHONHASHSEED=4801`；F2 使用固定 2099/2020 时间戳；没有网络、
  真实数据库或真实服务；`--out` 全部在仓库外。
- **必测套件**：本实验不进入 `tests/unit` 或 `run.py` 模式；`python tests/run_tests.py`
  仍为 198 passed。

---

## 8. 附录 A：prompt 原文

三个 prompt 的逐字原文保存在 `prompts/`。为满足“附 prompt 原文”，这里原样收录。

### A.1 F1

```text
You are the test-generation agent in a blind experiment (course Lecture 14,
Exercise 1). You have been given exactly two inputs: this prompt and the contract
file `tests/advanced/experiments/llm_blind/contracts/F1.md`. Work from the contract
only.

HARD RULES
- Do NOT open any file under `backend/app/` (production implementation), and do
  NOT open `tests/unit/test_matching.py` or any existing test of this function.
- Do NOT execute the target function or run pytest; the experiment owner runs the
  generated tests after freezing them in a commit. Running them would leak
  implementation behaviour into the generation step.
- Do NOT modify production code, contracts, prompts, helpers, or any file other
  than the single output file named below.
- Use only the Python standard library and pytest.

TASK
Write `tests/advanced/experiments/llm_blind/generated/test_F1.py` containing
pytest tests for `app.employer.matching.match_score`, imported exactly as
`from app.employer.matching import match_score`. The signature is:

    def match_score(candidate_skills: list[str], required_skills: list[str]) -> int

PROCEDURE (follow the order)
1. Map FP-MATCH-1 from the contract to valid, boundary, and invalid partitions.
   Put the partition map in a module docstring or a comment block. For inputs
   outside the declared `list[str]` type, record the contract ambiguity instead of
   inventing an expected exception.
2. For every expected value, calculate it from the contract and write the
   arithmetic next to the assertion (for example
   `# k=1, n=2 -> 100*1//2 = 50`). Do not call `match_score`, `normalize_skills`,
   or any application helper to obtain an expected value.
3. Check the exact result type: assert `type(result) is int` (not
   `isinstance`, because `bool` is an `int` subclass), and assert `0 <= result <= 100`.
4. Check the exact exception behaviour only where the contract specifies it. The
   contract specifies none for valid `list[str]` inputs, so do not demand an
   exception for out-of-contract inputs.
5. Cover at least: the four required FP-MATCH-1 examples; an empty candidate list
   with a non-empty required list; floor rounding with `len(R)=3` and `k=1,2`;
   normalisation by whitespace, case and duplicates; input order/duplicate
   invariance; and Unicode/symbol skills.
6. List every ambiguity you had to resolve at the top of the file.
7. Make the file self-contained and syntactically valid Python 3.12+ (no
   dependency on the experiment owner's fixtures). Do not write a `conftest.py`.

OUTPUT
Write only the file `tests/advanced/experiments/llm_blind/generated/test_F1.py`.
Reply with a short summary: which partitions you covered, the expected values you
calculated, and the ambiguities you recorded. Do not paste the whole file back.
```

### A.2 F2

```text
You are the test-generation agent in a blind experiment (course Lecture 14,
Exercises 1 and 3). You have been given exactly two inputs: this prompt and the
contract file `tests/advanced/experiments/llm_blind/contracts/F2.md`. Work from the
contract only.

HARD RULES
- Do NOT open any file under `backend/app/` (production implementation), and do
  NOT open `tests/unit/test_scheduling.py`, `tests/unit/test_workflows.py`, or any
  existing test of `book`.
- You MAY read and import the harness helper
  `tests/advanced/experiments/llm_blind/generated/session_double.py` (it is a test
  double, not the implementation) and `tests/advanced/experiments/llm_blind/generated/conftest.py`.
- Do NOT execute `book` or run pytest; the experiment owner runs the generated
  tests after freezing them in a commit. Running them would leak implementation
  behaviour into the generation step.
- Do NOT modify production code, contracts, prompts, helpers, or any file other
  than the single output file named below.
- Use only the Python standard library and pytest.

TASK
Write `tests/advanced/experiments/llm_blind/generated/test_F2.py` containing
pytest tests for `app.candidate.service.book`, imported exactly as

    from app.candidate.service import book, NotFoundError, ForbiddenError, ConflictError

The signature is:

    def book(session: Session, user: User, application_id: uuid.UUID, slot_id: uuid.UUID) -> BookingPublic

PROCEDURE (follow the order)
1. Map FP-SCHED-2 and FP-SCHED-3 from the contract to valid, boundary, and
   invalid partitions. Put the partition map in a module docstring or comment
   block.
2. For every scenario, construct the state explicitly and calculate the expected
   outcome from the contract, including the arithmetic for the 30-minute duration
   and the future/past timestamps. Do not call `book` to discover expectations.
   Use fixed, timezone-aware timestamps (for example 2099 and 2020) rather than
   “now + 1 day”.
3. Check the exact exception class: `pytest.raises(ConflictError)`,
   `pytest.raises(ForbiddenError)`, `pytest.raises(NotFoundError)`; a bare
   `ValueError` is not acceptable. Assert the fixed message where the contract
   gives one.
4. **For every rejected call** (Lecture 14 slide 26), snapshot the whole relevant
   state before the call and assert afterwards:
   - `session.commit` was not called;
   - no `Booking` was persisted (`session.add` did not receive a `Booking`, and the
     object graph has no new booking);
   - `slot.job_id`, `application.status` and `application.version` are unchanged;
   - if the function staged a write or attempted a commit, `session.rollback` was
     called. Do not assert a rollback for a pure validation rejection that stages
     nothing.
5. Cover all success and rejection conditions in the contract: eligible success;
   pending/rejected/accepted status; wrong candidate; missing application; missing
   slot; missing job; slot in the past; 29-minute and 31-minute durations; slot
   already booked; slot reserved for another job; commit raising
   `sqlalchemy.exc.IntegrityError` → rollback + `ConflictError("Slot already booked")`.
6. For the success case assert the exact observable outcome: returned
   `BookingPublic` fields, `slot.job_id` set to the application's job, exactly one
   `Booking` added with the right IDs, and one commit.
7. List every ambiguity you had to resolve at the top of the file.
8. Make the file self-contained apart from the provided helper.

RECOMMENDED SESSION SETUP
`from session_double import make_session` and read its docstring/signature. Build
the entities as real SQLModel instances (not `MagicMock`s) when the attributes are
read by the service, so status comparisons are real enum comparisons. The helper
accepts the application, slot and job objects and optional existing bookings. If
you build your own `MagicMock(spec=Session)`, make every result chain empty by
default (`.first()`, `.one_or_none()`, `.all()`, `.scalars().first()`) and configure
`get`/`exec` side effects by object rather than by call order.

OUTPUT
Write only the file `tests/advanced/experiments/llm_blind/generated/test_F2.py`.
Reply with a short summary: partitions covered, the three hand-calculated expected
values, which state snapshots you assert, and the ambiguities you recorded. Do not
paste the whole file back.
```

### A.3 F3

```text
You are the test-generation agent in a blind experiment (course Lecture 14,
Exercises 1 and 3). You have been given exactly two inputs: this prompt and the
contract file `tests/advanced/experiments/llm_blind/contracts/F3.md`. Work from the
contract only.

HARD RULES
- Do NOT open any file under `frontend/src/` (the component implementation).
- Do NOT open existing tests except the calling-convention reference
  `frontend/tests/rendering.unit.mjs`, which you may read to see how the component
  is transpiled and rendered.
- Do NOT execute the render helper or run node tests; the experiment owner runs
  the generated tests after freezing them in a commit. Running them would leak
  implementation behaviour into the generation step.
- Do NOT modify production code, contracts, prompts, helpers, or any file other
  than the single output file named below.
- Use only Node.js built-ins, `node:test`, `node:assert/strict`, and the provided
  helper.

TASK
Write `tests/advanced/experiments/llm_blind/generated/test_F3.mjs`, an ES module
test using `node:test`, for the `SkillTagPicker` escaping behaviour. Use the
provided helper:

    import {renderSkills} from './render_helper.mjs';

`renderSkills(value)` renders the real component with
`renderToStaticMarkup` and returns the HTML string. Your test file must run with
`node --test tests/advanced/experiments/llm_blind/generated/test_F3.mjs` from the
repository root.

PROCEDURE (follow the order)
1. Map FP-SEC-3 from the contract to valid, boundary, and invalid/hostile
   partitions. Put the partition map in a comment block at the top.
2. For every expected escaped fragment, calculate it by hand from the contract
   (React escapes `<`, `>`, `&`, `"`, `'` as `&lt;`, `&gt;`, `&amp;`, `&quot;`,
   `&#x27;`). Write the reason in a comment. Do not infer expected output from
   reading the component source.
3. For hostile input assert both the positive escaped fragment and the absence of
   raw executable markup, for example:
   - `html.includes('&lt;script&gt;alert(1)&lt;/script&gt;')`
   - `!/<script(?:\s|>)/i.test(html)`
   - `!html.includes('<script>alert(1)</script>')`
4. Check attribute escaping for a double-quote payload: assert the escaped
   `onmouseover=&quot;x&quot;` is present and the raw `onmouseover="x"` is absent.
5. Check ampersand escaping: `a&amp;b` present, raw `a&b` absent.
6. Check the empty list boundary and ordinary Unicode text (`中文 résumé 🙂`)
   survive rendering.
7. Do not assert a whole-HTML string, attribute order, CSS class names, or the
   component's display normalisation; compare case-insensitively when a value's
   case may be normalised.
8. List every ambiguity you had to resolve at the top of the file.

OUTPUT
Write only the file `tests/advanced/experiments/llm_blind/generated/test_F3.mjs`.
Reply with a short summary: partitions covered, the hand-calculated escaped
fragments, and the ambiguities you recorded. Do not paste the whole file back.
```

## 9. 附录 B：复现与文件索引

| 内容 | 路径 |
|---|---|
| 协议与运行说明 | [`README.md`](../../tests/advanced/experiments/llm_blind/README.md) |
| 契约 | [`contracts/`](../../tests/advanced/experiments/llm_blind/contracts) |
| prompt | [`prompts/`](../../tests/advanced/experiments/llm_blind/prompts) |
| 生成测试 | [`generated/`](../../tests/advanced/experiments/llm_blind/generated) |
| 运行器 | [`run_experiment.py`](../../tests/advanced/experiments/llm_blind/run_experiment.py) |
| 结果 | [`results.json`](../../tests/advanced/experiments/llm_blind/results.json) |
| 变异体 | [`mutation/`](../../tests/advanced/experiments/llm_blind/mutation) |
| 手写对照 | `tests/unit/test_matching.py`、`tests/unit/test_scheduling.py`、`tests/unit/test_rendering.py` |
| 手写渲染用例 | `frontend/tests/rendering.unit.mjs` |

没有 `docs/advanced_testing/findings/P10.md`：本实验未发现需要交给人类修复的业务缺陷。
