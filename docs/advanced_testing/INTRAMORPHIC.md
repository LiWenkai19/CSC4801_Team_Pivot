# P9 蜕变与内蜕变测试报告

本文件对应 `tests/advanced/intramorphic/` 模式。所有测试只通过真实 HTTP 接口和一次性
PostgreSQL 运行，生产代码（`backend/app/`）没有改动。原始输出写在仓库外的 `--out`
目录；本文件只保留汇总数字和结论。

## 1. 方法

### 1.1 蜕变测试（metamorphic）

对业务工作流而不是匹配公式构造“语义等价或关系已知”的输入变换。若原输入为 `x`、变换为
`T`，要求输出满足：

```text
f(T(x)) == f(x)                 或
相对关系 f(T(x)) 与 f(x) 相同
```

本任务覆盖的匹配公式蜕变（排列、大小写、空白、重复）已经在
`tests/specialized/test_matching_oracles.py` 里覆盖；P9 只在**工作流层**验证从投递、
状态流转、时段创建、无关数据扰动到推荐/可用时段的可观察结果。

### 1.2 内蜕变测试（intramorphic）

输入不变，用 `pytest` 的 `monkeypatch` 构造程序的“受控变体”，每次只关掉一条可能的
防护层，再比较原版与变体的结果：

```text
原版：input -> 规则 R 的全部层 -> output_original
变体：input -> 去掉第 k 层     -> output_variant
```

如果变体仍然正确，说明被去掉的层不是唯一保证；如果变体错误而原版正确，说明这一层
在单独支撑规则。它回答的是演示问题“**哪一层在保证这条规则**”，而不是“测试能不能
杀死一个变异体”（后者由 P7 的 mutation 模式负责）。

### 1.3 为什么用 `monkeypatch`

- 不修改 `backend/app/`，不在磁盘上留下任何临时生产代码；
- `pytest` 在测试结束（包括断言失败）时自动还原属性；
- 变体仍在同一进程、同一真实路由/数据库上运行，观察的是真实事务和约束，不是替身
  数据库。

两个实现细节：

1. `book` / `apply` 的“预检查询”和 `IntegrityError` 恢复分支使用**同一条 SQL**。
   变体只跳过第一次匹配（成功路径的预检），让恢复分支照常执行。如果把这条查询
   “恒返回 None”，恢复分支也会误以为没有冲突，`IntegrityError` 会直接冒出成 500，
   而不是需求要求的 409。因此本套件用“跳过第一次”而不是“永远返回 None”。
2. I2 的第二个 Barrier 放在时段预检查询之后。它是**并发证据仪器**，不是业务变体：
   两个请求都必须真实执行预检、都观察到时段空闲，然后才允许任一请求插入。这样输家
   必然走到数据库唯一约束，而不是靠应用层预检提前返回。

### 1.4 环境与确定性

- Python 3.14.4（主 checkout 的 `.venv`）；
- PostgreSQL **18.6**（本机只安装了 18.x 的服务器工具；CI/Docker 规定 15，两者
  使用的唯一约束/行锁语义相同）；
- `PYTHONHASHSEED=4801`，无 Hypothesis、无网络、只有本机临时数据库；
- 每个模式会话使用一个 `advanced_<随机>` 临时库，测试后 `DROP ... WITH (FORCE)`。

## 2. 蜕变结果（M1–M5）

| ID | 原输入 → 变换 | 关系 | 实际结果 |
|---|---|---|---|
| M1 | `建时段 → 投递 → Interviewing` ↔ `投递 → Interviewing → 建时段` | 候选人可用时段集合相同 | 两个流程都只看到 1 个时段，`(starts_at, ends_at)` 完全相同 |
| M2 | 基线 ↔ 追加无关雇主的 2 个职位、1 个时段、1 个申请 | 原候选人的相对推荐顺序、原职位分数、可用时段不变 | 3 个原职位保持 `100 / 50 / 0` 的相对顺序；可用时段仍为原 1 个；新职位出现但只是插入噪声 |
| M3 | 职位要求技能 `python/sql` 等 → 大小写、空白、重复变体 | 推荐分数与顺序不变 | 变体都规范化回同一集合；分数仍为 `100 / 50 / 0`，完整签名的顺序不变 |
| M4 | 候选人资料只改 `resume_text`（空 → 106 字符，含 `Rust` 和哨兵词） | 推荐分数与顺序不变 | 简历版本从 1 到 2，技能不变；两条推荐的分数/顺序完全不变 |
| M5 | `Interviewing → Rejected → Interviewing`（期间无预约） | 可用时段集合与原来相同 | 回退后 2 个时段的 ID 和起止时间与之前完全一致；中间 Rejected 时正确返回 409 |

每条 M 测试都写自己的 evidence，例如：

```text
<out>/intramorphic/M1.json ... M5.json
```

## 3. 内蜕变结果（I1–I5）

### 3.1 总表：“规则 → 防护层 → 关掉后会怎样”

| 规则 | 第一层：应用检查 | 第二层：锁 | 第三层：数据库约束 | 关闭的层 | 关闭后的实际结果 | 结论 |
|---|---|---|---|---|---|---|
| I1 一个时段只能预约一次 | `book` 查询 `Booking.slot_id` | `InterviewSlot ... FOR UPDATE` | `uq_booking_slot` | 应用预检 | 第二次预约仍 409 `Slot already booked`；commit 捕获 1 次 `IntegrityError`；预约表 1 行 | 数据库约束兜底；纵深防御 |
| I2 并发预约单赢家 | 同一时段预检 | 申请/时段 `FOR UPDATE` | `uq_booking_slot` | 所有行锁 | 5 轮都是 1×201 + 1×409，每轮预约表 1 行，每轮 1 次 `uq_booking_slot` 冲突 | 唯一约束单独即可保证单赢家；行锁负责减少冲突/串行化 |
| I3 重复投递 | `apply` 查询 `(candidate_id, job_id)` | `Job ... FOR UPDATE` | `uq_application_candidate_job` | 应用预检 | 第二次投递仍 409 `Already applied`；commit 捕获 1 次 `IntegrityError`；申请表 1 行 | 数据库约束兜底；纵深防御 |
| I4 匹配对归一化顺序不敏感 | `match_score` 把两个列表转成集合 | 无 | 无 | `normalize_skills` 返回反转列表 | 9 条推荐分数/排序与 9 条申请人分数/排序全部不变 | 集合算法天然消除顺序；这是实现性质，不是单独检查 |
| I5 删除有依赖的职位 | `delete_job` 两次依赖查询 | `Job ... FOR UPDATE` | 有外键，但软删除不触发 | 应用依赖检查 | 204，职位 `is_deleted=true`；申请和时段仍在；数据库没有阻止 | **单层防护**（应用层检查）；正常代码仍返回 409，不是 bug |

### 3.2 I1：时段唯一性

- 原版对照：第二个候选人预约同一时段 → 409 `Slot already booked`，预约表 1 行，
  预检就返回，没有 `IntegrityError`。
- 变体：跳过第一次时段预检 → 仍然 409 `Slot already booked`；`Session.commit`
  捕获 `uq_booking_slot` 冲突，预约表 1 行。
- 结论：应用预检不是唯一防线；数据库唯一约束是充分兜底。

### 3.3 I2：并发预约单赢家（5 轮）

原版对照（保留行锁）：1×201 + 1×409，1 个预约行。

变体（`Select.with_for_update` 变成返回 `self`）：

| 轮次 | 状态码 | 进入 `book` 的时间重叠 | 独立 Session | 独立线程 | 预检均观察到空闲 | `IntegrityError` 约束 | 时段预约行数 |
|---|---|---|---|---:|---:|---:|---|---:|
| 0 | 201 / 409 | 是 | 是 | 是 | 是 | `uq_booking_slot` | 1 |
| 1 | 201 / 409 | 是 | 是 | 是 | 是 | `uq_booking_slot` | 1 |
| 2 | 201 / 409 | 是 | 是 | 是 | 是 | `uq_booking_slot` | 1 |
| 3 | 201 / 409 | 是 | 是 | 是 | 是 | `uq_booking_slot` | 1 |
| 4 | 201 / 409 | 是 | 是 | 是 | 是 | `uq_booking_slot` | 1 |

并发证据：

- 两个线程各自 `with TestClient(app)`，每次请求由依赖注入创建独立 `Session`；
  evidence 记录两个不同的 `session` 对象 id。
- 进入 `book` 前 `Barrier(2)`：两个请求都进入后才继续，所以两段
  `[进入, 退出]` 区间必然重叠；evidence 记录 `book_intervals_overlap: true`。
- 时段预检后的第二个 Barrier：两个请求都完成“查询并观察到空闲”后才继续，
  evidence 记录两次 `is_none: true`。因此输家不是被预检提前拒绝，而是真正与赢家
  一起进入了插入阶段。
- 每轮恰好 1 次 `uq_booking_slot` 的 `IntegrityError`，最终数据库 1 行。

结论：去掉行锁后，数据库唯一约束仍单独保证单赢家；行锁不是唯一防护层。

### 3.4 I3：重复投递

- 原版对照：第二次投递 → 409 `Already applied`，申请表 1 行，无 `IntegrityError`。
- 变体：跳过第一次重复预检 → 仍 409 `Already applied`；commit 捕获
  `uq_application_candidate_job`；申请表 1 行。
- 结论：数据库唯一约束兜底。

### 3.5 I4：匹配实现与集合顺序

构造 3 个候选人和 3 个职位（分数覆盖 `0 / 33 / 50 / 100`），全部投递；先把
`app.employer.matching.normalize_skills` 包一层，让它返回反转后的列表。结果：

- 9 条候选人仪表盘行、9 条雇主申请人行，分数与相对顺序完全不变；
- 变体实际被调用 37 次（说明确实走了被修改的实现）；
- 样例：`normalize_skills(["SQL", "Python"])` 原版返回 `["python", "sql"]`，变体
  返回 `["sql", "python"]`；`match_score` 内部使用 `set`，所以结果一样。

结论：规则由“集合算法”保证，而不是某个单独的检查；这也说明“顺序”不是匹配契约的
一部分。

### 3.6 I5：删除有依赖的职位（事实记录，不是 bug）

两个独立场景：

1. 职位有 1 条申请；
2. 职位被 1 个时段直接绑定（测试里用 `InterviewSlot` 写入，因为公开 API 的时段
   创建后由预约绑定到职位）。

原版对照：两个删除都 409 `Job has applications or interview slots`，职位
`is_deleted=false`。

变体：让 `delete_job` 的两次依赖查询都返回“无依赖”：

- 两个删除都 204；
- 两个职位 `is_deleted=true`；
- 申请 1 行、时段 1 行仍在，且时段仍绑定原职位。

结论：**单层防护**。`delete_job` 是软删除（`UPDATE job.is_deleted`），数据库外键
不会阻止 UPDATE，因此唯一阻止删除的是应用层依赖检查。正常代码路径满足
FP-EMP-2，所以这不是业务缺陷，只是防御纵深事实。

## 4. 自检：证明 oracle 不是空断言

| 自检 | 故意引入的错误 | 观察到的红/绿 | 恢复 |
|---|---|---|---|
| I1 缺约束 | 在一次性库里 `DROP CONSTRAINT uq_booking_slot`，跳过时段预检，第二次预约 | 第二次返回 **201**，预约表 **2 行**；`assert_single_booking` 抛出 `AssertionError` | `finally` 删除多余行并 `ADD CONSTRAINT`；复查 1 行 |
| I3 缺约束 | 在一次性库里 `DROP CONSTRAINT uq_application_candidate_job`，跳过重复投递预检，第二次投递 | 第二次返回 **201**，申请表 **2 行**；`assert_single_application` 抛出 `AssertionError` | `finally` 删除多余行并 `ADD CONSTRAINT`；复查 1 行 |
| M 仪表盘 oracle | `monkeypatch` 把 `candidate.service.match_score` 改成恒 0 | 50 分被改成 0；`assert_dashboard_unchanged` 抛出 `AssertionError` | `monkeypatch.undo()` 后恢复 50 分，oracle 通过 |
| M 时段 oracle | 把 `candidate.service.available_slots` 截断为前 1 个 | 2 个时段变 1 个；`assert_slots_unchanged` 抛出 `AssertionError` | `monkeypatch.undo()` 后恢复 2 个，oracle 通过 |

关于 I1 自检的说明：任务文本建议“monkeypatch 让 `session.commit` 吞掉
`IntegrityError`”。在 PostgreSQL 里唯一约束是在 INSERT/FLUSH 阶段执行的，Python 层
吞掉异常的 commit 并不能让数据库真的保存第二条重复行；更忠实于“没有约束”的做法是
在一次性测试库中临时删除物理约束。上表采用了后者，并在 `finally` 中恢复。自检仍然
验证了同一件事：**约束不存在时，HTTP 路径会成功，oracle 必须变红**。

## 5. 复现

```sh
# 本机：PG_BIN 指向 PostgreSQL 服务器工具目录（Windows 示例）
$env:PG_BIN = "D:\Study\Y4 - CSC4801\tools\pgsql\bin"
python tests/advanced/run.py intramorphic \
  --out "$env:TEMP\adv-intramorphic" \
  --pg-bin "$env:PG_BIN"

# 必测套件
python tests/run_tests.py
```

本次运行结果（两次重复验收）：

- `python tests/advanced/run.py intramorphic`：exit 0，**14 passed**，
  pytest 约 8.3–8.4 s，模式总耗时约 11.0–11.2 s；
- `python tests/run_tests.py`：exit 0，**251 passed**，9.32 s；
- `git diff main -- backend/`：空。

产物（仓库外）：

```text
<out>/intramorphic/
  run.log
  result.json
  defense_layers.json     # I1/I2/I3/I4/I5 + 两个自检
  M1.json ... M5.json
  selfcheck_metamorphic_dashboard.json
  selfcheck_metamorphic_slots.json
```

## 6. 结论

1. **唯一性规则有两层以上防护**：时段单次预约、并发单赢家、重复投递都不是只靠
   应用层预检；数据库唯一约束可以单独兜底（I1/I2/I3）。
2. **行锁不是唯一保证**：I2 去掉行锁后单赢家仍成立；行锁的价值是减少冲突和
   串行化竞争，而不是唯一正确性来源。
3. **I4 是算法性质**：`match_score` 用集合而不是列表顺序，`normalize_skills` 的
   返回顺序不影响分数/排序。
4. **I5 是单层防护事实**：职位依赖检查只在应用层；数据库外键不阻止软删除。正常
   路径行为符合需求，因此不记业务缺陷。
5. 未发现需要写入 `docs/advanced_testing/findings/P9.md` 的业务缺陷；I5 的
   “单层防护”按任务要求作为事实记录，而不是 bug。
