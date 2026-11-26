# 高级测试与验证方案

版本：2026-11-25　适用范围：本仓库（`app/`）　执行者：低价 Agent（Sonnet 水平）
本文件只描述测试与验证工作，不包含业务代码修复。业务缺陷一律写报告交回人类决定。

---

## 0. 目标与边界

**目标**：在满足课程 MUST 要求的基础上，叠加讲义 L12–L14 的方法与工业界常用手段，
产出可复现、可量化、可写进 README 映射表的证据。

**本期重点**：自己的仓库。测试他人仓库由其他组员负责；本方案的运行器设计
（一次性 PG、固定种子、产物出仓、只打本地）可以原样迁移过去，见 §7。

**明确不做**：

- 不修改 `backend/app/`、`frontend/src/` 下的生产代码；不"顺手修 bug"。
- 不做压测、DoS、资源耗尽、破坏性测试；不访问任何部署地址。
- 不把测试产物、日志、Cookie/CSRF 值提交进仓库。
- 不重复已有测试。`tests/specialized/` 保持只读，新增能力全部落在新目录。

**时间**：2026-11-25 起两周，第 13–14 天冻结并准备提交。

---

## 1. 分层

| 层 | 位置 | 依赖 | 是否进镜像 | 作用 |
|---|---|---|---|---|
| A 必测套件 | `tests/unit/` | 现有锁文件 + `hypothesis` | 是 | 计入 FP-TEST-1，`python tests/run_tests.py` 一条命令 |
| B 高级套件 | `tests/advanced/`（新） | 独立 `requirements.txt` | 否 | 变异、形式化、模糊、LTL、差分等，单独命令 + CI job |

**为什么这样分**：镜像只需要装"文档里那条必测命令"用到的东西（Docker job 会在镜像内跑它）。
A 层用得到的 Hypothesis 必须写进 `requirements.lock`；B 层的 mutmut、z3、schemathesis、
pytest-cov 体积大、只在开发和 CI 用，一律不进镜像，`DOCKER.md` 只加一句说明。

**目录**：

```text
tests/advanced/
  README.md                  # P0 建，P11 收口
  requirements.txt           # P0 一次性 pin 全部高级依赖
  run.py                     # P0：自动发现模式，后续任务不改
  conftest.py                # P0：一次性 PG 库、client、account、evidence 夹具
  support/
    pg.py                    # P0：本机临时集群 / 外部一次性 PG
    traces.py                # P0：轨迹事件格式（P2 写，P3 读）
    ltl.py                   # P3
  stateful/                  # P2
  ltl/                       # P3
  formal/                    # P4、P5
  differential/              # P6
  mutation/                  # P7（entry.py，SLOW）
  apifuzz/                   # P8（entry.py，SLOW）
  intramorphic/              # P9
  experiments/llm_blind/     # P10（不是模式）
  coverage/                  # P11（entry.py）
  report.py                  # P11
```

**模式自动发现**：`tests/advanced/` 下除 `support/`、`experiments/` 之外的每个子目录就是一个模式，
模式名即目录名。目录里有 `entry.py` 就以子进程运行它，否则对该目录跑 pytest。
目录里有空文件 `SLOW` 的模式不进入 `fast`。因此新增模式**不需要改 `run.py` 或 `ci.yml`**。

**共享文件归属**（并行开发防冲突）：

| 文件 | 唯一修改者 |
|---|---|
| `tests/advanced/{run.py,conftest.py,requirements.txt}`、`support/{pg,traces}.py`、`.gitignore` | P0 |
| `requirements.lock`、`tests/unit/test_matching_properties.py` | P1 |
| `.github/workflows/ci.yml`（advanced job 首版） | P0；最终收口 P11 |
| `.github/workflows/security.yml` | P12 |
| `README.md`、`INSTALL.md`、`DOCKER.md`、`docs/testing/ADVANCED_REPORT.md` | P11 |
| 业务缺陷记录 | 各任务写 `docs/testing/findings/P<n>.md`，P11 汇总 |

**命令**（与 specialized 风格一致）：

```sh
python tests/advanced/run.py smoke
python tests/advanced/run.py stateful
python tests/advanced/run.py ltl
python tests/advanced/run.py formal
python tests/advanced/run.py differential
python tests/advanced/run.py intramorphic
python tests/advanced/run.py apifuzz
python tests/advanced/run.py mutation
python tests/advanced/run.py coverage
python tests/advanced/run.py fast     # 所有非 SLOW 模式（CI push 时）
python tests/advanced/run.py all      # 全部模式
```

`run.py` 沿用 `tests/specialized/run.py` 的约定：`--out` 必须在仓库外；`summary.json`
记录 commit SHA、模式、用例数、通过/失败、耗时、种子；任一阶段失败即非零退出。

---

## 2. 给 Agent 的硬性约定

每个任务的提示词里都要原样带上这一段。

1. **只读生产代码**。允许新增文件只限任务里列出的路径。发现业务 bug：写进
   `docs/testing/findings/P<n>.md`，不要改代码，不要为了让测试变绿而改断言。
2. **确定性**：固定 `PYTHONHASHSEED=4801`；Hypothesis 用 `derandomize=True` 或固定
   seed；设置 `deadline=None`；每个模式的 `max_examples` 有上限（见各任务）。
3. **边界**：只连本机临时 PG（随机端口、`initdb` 新建）；只对本机进程发请求；
   不访问外网；不读 `backend/.env` 的真实值；不打印 Cookie/CSRF。
4. **产物**：日志、harness 生成的临时文件放 `--out`（仓库外）；只有汇总数字和结论
   可以写进 `docs/testing/`。
5. **完成定义（DoD）**：任务自己的模式跑通 + `python tests/run_tests.py` 仍全绿 +
   汇报里给出命令、退出码、关键数字、产物路径、阻塞点。
6. **提交**：一个任务一个 commit；不改无关文件；不 `git push`。

**汇报模板**（Agent 交回的内容）：

```text
任务：P<n> <名称>
改动：<文件列表，新增/修改>
命令：<完整命令>
结果：<退出码>，<用例数/通过数/得分/证明数>
证据：<产物路径>
阻塞/偏离：<无 | 具体说明与已尝试的方案>
结论：<对需求或讲义方法的意义>
```

---

## 3. 任务清单

### P0 基线固化与运行器骨架　（约 2h，无依赖）

- **文件**：新增 `tests/advanced/{README.md,requirements.txt,run.py,conftest.py}`、
  `docs/testing/ADVANCED_BASELINE.md`；`.gitignore` 追加 `.hypothesis/`、`.mutmut-cache/`、
  `coverage.xml`、`htmlcov/`。
- **步骤**
  1. 记录 `git rev-parse HEAD`、Python/Node/PostgreSQL 版本、
     `python tests/run_tests.py` 与 `--integration` 的用例数与耗时。
  2. `run.py` 实现 `smoke` 模式（打印环境与 SHA、写 `summary.json`）与 `--out` 校验。
  3. CI 增加 `advanced` job：装 `tests/advanced/requirements.txt` + `postgres:15` service，
     先只跑 `smoke`，设 `continue-on-error: true`，稳定后改为必过。
- **验收**：`python tests/advanced/run.py smoke` 退出 0 且 `summary.json` 含 sha；
  `python tests/run_tests.py` 全绿。
- **证据**：`ADVANCED_BASELINE.md`（只写数字）。

### P1 Hypothesis 属性测试进入必测套件　（约 3h）

- **依赖**：P0。**目标**：只写进 README 的映射表还不够，让必测命令本身包含属性测试。
- **文件**：新增 `tests/unit/test_matching_properties.py`；修改 `requirements.lock`
  （追加 `hypothesis` 及其依赖 `attrs`、`sortedcontainers`，全部 pin 死）；
  `.gitignore` 确认含 `.hypothesis/`。
- **性质**（每条一个测试函数，名字要能进 README 映射）：
  1. 返回值恒为 `int` 且 `0 <= s <= 100`；
  2. 等于独立 oracle（`Fraction` + 集合交，**不得**调用被测实现）；
  3. 必需技能归一化后为空 ⇒ 100；
  4. 输入排列、重复、空串、首尾空白不改变结果；
  5. 候选技能追加无关技能分数不变；追加一个缺失的必需技能分数不减；
  6. 固定 R 时，分数随 `|C∩R|` 单调不减；
  7. `normalize_skills` 幂等、去重、去空白、转小写。
- **设置**：`@settings(derandomize=True, max_examples=200, deadline=None)`；
  文本用 `st.text(max_size=12)` 并排除代理项（`blacklist_categories=("Cs",)`），
  另加显式 Unicode 词表（`ß/SS`、`İ`、`机器学习`、`C++`）。
- **验收**：`python tests/run_tests.py` 全绿且新用例被收集；用例总数上升；
  在 Docker 内执行同一命令仍全绿（CI 的 docker job 会验证）。
- **降级**：改动锁文件导致镜像或 CI 不稳时，把文件移到
  `tests/advanced/property/`，不进必测命令，只保留为高级证据。

### P2 有状态模型测试：预约生命周期　（约 6h）

- **依赖**：P0。**目标**：用 Hypothesis 状态机随机走业务序列，每步检查不变量。
- **文件**：`tests/advanced/stateful/`（`support/pg.py` 由 P0 提供）。
- **规则**（`RuleBasedStateMachine`）：注册候选人/雇主 → 建职位 → 投递 → 雇主改状态
  （仅四个合法值）→ 建未来 30 分钟时段 → 预约 → 读候选人可用列表 / 雇主申请人列表。
- **不变量**（每步后断言）：
  1. 每个时段至多一条预约；每个申请至多一条；
  2. 已预约时段不出现在候选人可用列表；
  3. 预约成功那一刻申请必须为 `Interviewing`；状态离开 `Interviewing` 后旧预约保留、
     时段仍不可用；
  4. 所有分数 `0..100`，候选人视图与雇主视图对同一 (C,R) 分数一致；
  5. 非法操作（重复投递、他人申请、删已约时段）必须冲突且相关表行数不变。
- **设置**：`max_examples=25`、单次最多 12 步、`deadline=None`、seed 4801；
  总时长目标 < 120s。
- **验收**：`run.py stateful` 退出 0；人为写一条必然违规的临时规则时它能报错
  （证明不变量真的会失败，而不是恒真）；运行时间达标。
- **证据**：`summary.json` 的 examples/steps/失败反例（若有，打印种子与最后 5 步）。

### P3 LTL 轨迹检查器　（约 5h）

- **依赖**：P2 的轨迹记录（可先用独立生成器开发）。**目标**：直接用讲义 L13 的时序逻辑。
- **文件**：`tests/advanced/support/ltl.py`、`tests/advanced/support/traces.py`、
  `tests/advanced/ltl/test_booking_traces.py`、`tests/advanced/ltl/test_checker_selftest.py`。
- **实现**：支持 `G`（总是）、`F`（最终）、`X`（下一步）、`U`（直到）、`& | !`；
  原子命题由状态机记录：`booked(app,slot)`、`available(slot)`、`status(app,S)`、
  `applied(app)`。
- **性质示例**：
  1. `G(booked(a,s) -> X(G(!available(s))))`——预约后永不再显示为空闲；
  2. `G(new_booking(a) -> status_at(a) = Interviewing)`；
  3. `G(booked(a,s) -> F(G(!del_slot(s))))`——已预约时段永不被删（删除会冲突）。
- **自检（必须有）**：3 条满足轨迹 + 3 条违规轨迹，确保检查器能判出违规；
  没有自检的 oracle 等于没有 oracle。
- **验收**：`run.py ltl` 退出 0；自检用例全部按预期判定；真实轨迹全部满足。
- **加分（stretch）**：对 1 条过严性质演示 relax/restrict，输出 F → F′ → F″ 的放宽
  序列与每步接受的轨迹比例（对应 L13 slides 46–52）。

### P4 Z3：匹配公式的形式化证明　（约 4h）

- **文件**：`tests/advanced/formal/test_matching_theory.py`、`docs/testing/FORMAL_MATCHING.md`。
- **证明**（每个性质用 `z3.Solver`，期望 `unsat`）：
  1. `0 <= 100k//n <= 100`（`n>=1, 0<=k<=n`）；
  2. `k=n => 100`，`k=0 => 0`；
  3. floor 定义：`score*n <= 100k < (score+1)*n`；
  4. 单调：`k1<=k2 => score(k1)<=score(k2)`；
  5. `score=100 <=> R⊆C`（有界全集的集合编码）。
- **写法**：每个证明上方用 Hoare 三元组注释 `{P} match_score(C,R) {Q}`，并与
  FP-MATCH-1 的条款逐条对应，报告里给"条款 → 性质 → 证明状态"表。
- **验收**：pytest 全部通过；单条 < 1s；`z3-solver` 只出现在 advanced 依赖里。
- **说明**：证明对象是**规格公式**，不是 Python 代码本身；报告里要写清楚这一点，
  不要夸大。

### P5（stretch）Z3 有界模型检验：预约状态机　（约 8h）

- **文件**：`tests/advanced/formal/test_booking_bmc.py`。
- **做法**：编码 k=6 步转移（申请状态、时段预约位、申请的预约位），断言
  "任何时刻至多一个预约/时段"与"预约仅发生在 Interviewing"；期望 `unsat`。
  故意放宽一条规则时必须得到 `sat` 并打印反例轨迹（证明编码非空）。
- **验收**：不变量 `unsat`；放宽规则后 `sat` 且反例可读。
- **放不下就砍**：这条是加分项，不影响主线。

### P6 差分测试：Python 打分 vs SQL 打分　（约 3h）

- **文件**：`tests/advanced/differential/test_matching_sql.py`。
- **做法**：真实 PG 造数据（候选人技能、职位必需技能），用 SQL 算交集比例，
  与 `match_score` 对比 500 组；再对比候选人视图与雇主视图在同一数据上的分数
  （排序键不同，分数必须相同）。
- **验收**：500/500 一致；不一致时打印最小反例（两侧技能列表与结果）。

### P7 变异测试（mutmut）　（约 6h）

- **文件**：`tests/advanced/mutation/run_mutmut.py`、`docs/testing/MUTATION.md`。
- **范围**：`employer/matching.py`、`users/service.py`（`normalize_skills` 与鉴权）、
  `interview/service.py`、`candidate/service.py`（`book`/`_eligible_application`）、
  `employer/service.py`（`delete_job`、状态变更）。
- **配置**：mutmut 锁定一个兼容版本；以 `tests/unit` 作为测试集；每个变异体超时 30s。
- **验收**：给出 mutation score；每个幸存变异体必须归因为「等价变异」或「缺测试」；
  「缺测试」的补进 `tests/unit`，并保证必测套件仍全绿。
- **降级**：mutmut 与 SQLModel/pytest 冲突时，在 `tests/advanced/mutation/` 写独立
  diff 式变异器（复制 `tests/specialized/mutation_checks.py` 的做法，不改原文件）。

### P8 API 属性模糊测试（Schemathesis）　（约 5h）

- **文件**：`tests/advanced/apifuzz/run_schemathesis.py`。
- **做法**：本地起 uvicorn（随机端口）+ 一次性 PG；用种子账号建立候选/雇主会话；
  `max-examples=20`、固定 seed、单 worker；只跑 GET 与自身资源读接口。
- **断言**：无未分类 5xx；401/403/404 符合 FP-AUTH-3；响应符合 OpenAPI。
- **验收**：JSON 报告；每个异常都要归因（真 bug / schema 漂移 / 测试配置），
  不得静默用过滤器吞掉。
- **降级**：版本或 ASGI 兼容问题 → 用 Hypothesis + `TestClient` 手写请求生成器，
  边界同样受限。

### P9 蜕变与内蜕变扩展　（约 5h）

- **文件**：`tests/advanced/intramorphic/test_defense_layers.py`、报告一节。
- **蜕变**（避开已有 matching 蜕变，不重复计分）：
  1. 增加无关时段/技能不改变既有结果；
  2. 先建时段后投递 vs 先投递后建时段，最终可见状态一致；
  3. 时区等价表示结果一致（已被 slots 套件覆盖，标为「复用」）。
- **内蜕变**（L12 slides 29–41，用 monkeypatch 构造受控变体，不改源码）：
  1. 去掉 `with_for_update`，看唯一约束是否仍保证单赢家；
  2. 跳过应用层「已预约」预检，看数据库约束是否兜底；
  3. 匹配实现用 `dict` 替代 `set`，输出应完全相同。
- **产出**：一张「规则 → 由哪层保证 → 移除哪层会破坏」的表，是很好的报告素材。
- **验收**：每个变体有明确结论；全程不落盘改生产代码。

### P10 LLM 盲测生成与断言质量　（约 4h，直接对应 L14 Exercise 1/3）

- **目标**：把「AI 生成测试」做成可复现实验，而不是口头声称。
- **文件**：`tests/advanced/experiments/llm_blind/`（生成的测试、prompt 原文、结果表）、
  `docs/testing/LLM_TEST_EXPERIMENT.md`。
- **目标函数**：`match_score`、预约资格判定（服务层，替身会话）、HTML 转义组件。
- **流程**：
  1. 只读 `SPEC.md` / `REQUIREMENTS.md` 写契约（输入、输出、异常、边界）；
  2. 生成测试时**不看实现**（先提交生成文件，再看源码运行）；
  3. 运行，把用例分为 通过 / 失败 / 契约歧义；
  4. 失败逐条归因：实现 bug、契约歧义、生成错误；
  5. 与手写测试对比：分区覆盖、数量、用 P7 的变异体衡量断言杀伤力。
- **验收**：报告含 prompt、生成文件、结果表、漏洞结论；不修改生产代码。

### P11 覆盖率、汇总面板与文档　（约 4h）

- **文件**：`tests/advanced/coverage/run_coverage.py`、`tests/advanced/report.py`、
  `docs/testing/ADVANCED_REPORT.md`、`README.md`、`INSTALL.md`、`DOCKER.md`（各加一小节）。
- **覆盖率**：pytest-cov 分支覆盖，分别跑「必测单元套件」与「集成套件」，
  报告 `backend/app` 的数字；**先测量，再决定门槛**，不拍脑袋设 90%。
- **面板**：每条技术的命令、结果数字、耗时、种子、commit SHA、已知限制，
  由 `report.py` 从各 `summary.json` 生成，保证数字与运行一致。
- **README**：新增「高级测试」小节；FP-MATCH-1 / FP-SCHED-3 / FP-TEST-1 的映射行
  追加新的具名测试；把过时的「157 tests」等数字更新为实测值。
- **验收**：一条命令重生成报告；报告数字与重跑一致；必测套件全绿。

### P12（可选）依赖与密钥扫描进 CI　（约 2h）

- `gitleaks`、`pip-audit`、`npm audit` 各一个 job；命中必须归因，
  扫描器报警不等于漏洞，不得直接宣称。

---

## 4. 排期与并行

假设 3 个 Agent 并行（A1/A2/A3），每天 4–6 小时有效工作。

| 日期 | A1 | A2 | A3 | 里程碑 |
|---|---|---|---|---|
| D1 | P0 | P1（先写测试再改锁文件） | 读 SPEC，准备 P10 契约 | 基线与骨架 |
| D2–D3 | P2 | P3 检查器 + 自检 | P7 mutmut 配置与首次全量 | P1/P2/P3 绿 |
| D4–D5 | P2 收尾 + P6 | P4 证明 | P7 幸存者归因与补测试 | 形式化 + 变异分 |
| D6–D7 | P8 | P3 stretch（relax/restrict）或 P5 | P9 内蜕变 | 模糊 + 内蜕变 |
| D8–D9 | P10 执行 | P11 覆盖率与面板 | P9 收尾、报告素材 | 实验报告 |
| D10 | P11 文档收口 | 复审所有产物 | CI 必过化、Docker 复验 | 全绿 |
| D11–D12 | 稳定化：抖动排查、重跑、冻结 | | | 准备提交 |
| D13–D14 | 缓冲 + 提交 commit URL | | | 提交 |

**决策门**：

- D3 结束：P1 与 P2 未达标 → P2 降级为固定序列测试（不用状态机），把时间让给 P3/P4。
- D7 结束：P4 未完成 → 砍 P5；P8 反复不稳定 → 砍 P8，保留其余。
- D10 结束：报告未写完 → 停止新增技术，先冻结数字写报告。

---

## 5. 风险与降级

| 风险 | 处理 |
|---|---|
| Hypothesis 进锁文件导致镜像/CI 变化 | 回退到 B 层，必测套件不动 |
| mutmut 与 SQLModel/pytest 不兼容 | 用独立 diff 式变异器（P7 降级方案） |
| Schemathesis 版本 API 变化 | 改用 Hypothesis + TestClient |
| 状态机测试慢/不稳 | 降 `max_examples` 到 10、固定 seed、`deadline=None` |
| CI 时间过长 | 变异与 apifuzz 放 `schedule` 每周跑，push 时只跑快模式 |
| Agent 擅自改生产代码 | 每个任务开始前 `git status` 快照，结束对比；发现即回滚并汇报 |

---

## 6. 最终交付清单

- [ ] `tests/advanced/` 全部模式可运行，`run.py all` 在本地通过
- [ ] `python tests/run_tests.py` 全绿，且含 P1 的属性测试
- [ ] `python tests/run_tests.py --integration` 全绿
- [ ] Docker job 四个阶段全绿（build / healthy / seed / unit + smoke）
- [ ] `docs/testing/ADVANCED_REPORT.md` 数字与重跑一致
- [ ] `docs/testing/FORMAL_MATCHING.md`、`MUTATION.md`、`LLM_TEST_EXPERIMENT.md` 完成
- [ ] README 映射表更新，过时数字改正
- [ ] CI 的 advanced job 稳定后转为必过
- [ ] 业务缺陷清单（若有）单独列出，未自行修复

---

## 7. 迁移到他人仓库（交给组员）

运行器天然满足 PEER_REVIEW 的安全边界，迁移时只需：

1. `git clone` 目标仓库，`git checkout` `main` 最新 commit，记录完整 SHA；
2. 用它的 `Dockerfile` 和 `INSTALL.md` 起环境，不修改目标源码；
3. 把 `tests/advanced/` 复制到仓库**之外**的独立目录，用 `PYTHONPATH` 指向目标
   checkout，产物写到仓库外；
4. 固定种子、限制 `max_examples`、只连本机容器里的数据库；
5. 每个发现整理成 issue 模板字段：commit SHA、复现命令、最小输入、期望/实际；
6. 不跑压测、不碰部署地址、不改对方仓库设置。

注意：`stateful`、`apifuzz`、`mutation` 依赖目标项目的包结构和测试命令，
迁移前先把这三处路径参数化（`--tests-dir`、`--app-module`、`--base-url`）。
