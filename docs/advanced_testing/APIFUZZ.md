# P8：基于 OpenAPI 的 API 属性模糊测试（Schemathesis）

状态：已实现并通过验收运行。下文原始数字属于历史 P8 验收；最新声明修复与复测见文末 [Post-audit documentation retest](#post-audit-documentation-retest)。入口：

```sh
python tests/advanced/run.py apifuzz
```

模式目录：`tests/advanced/apifuzz/`（`entry.py` + `hooks.py` + `NEEDS_DB` + `SLOW`）。
本文只记录测试与验证结果；发现的业务/契约缺陷写在
[`findings/P8.md`](findings/P8.md)，没有修改生产代码。

## 1. 目标

从 `app.main.app` 自动生成的 OpenAPI 文档出发，对本地后端做**有界、单进程、
可复现**的属性模糊测试，检查三件事：

1. 除公开的注册/登录外，受保护操作在匿名请求下返回 `401`（`422` 仅在请求
   校验先于认证时记录并归因）；
2. 认证角色与资源所有权对应的 `401/403/404` 符合 FP-AUTH-3；
3. 没有未分类的 `5xx`，且响应符合 OpenAPI 声明的 schema。

不做压测、不做长时间运行、不访问外网；目标总时长远低于 5 分钟。

## 2. 环境与安全边界

| 项 | 值 |
| --- | --- |
| Python | 3.14.4（主 checkout 的 `.venv`） |
| FastAPI / Starlette | 0.138.0 / 1.3.1 |
| Schemathesis / Hypothesis | 4.34.2 / 6.170.17 |
| PostgreSQL | 15.20（`PG_BIN` 指向便携版 PostgreSQL 15 的 `bin`） |
| 传输 | `schemathesis.openapi.from_asgi("/openapi.json", app)`，进程内 ASGI，**不占用端口** |
| 数据库 | `run.py` 新建的一次性 PG 集群；每次运行新建 `advanced_apifuzz_<随机>` 库，结束 `DROP ... WITH (FORCE)` |
| 网络 | 只与进程内 ASGI app 交互；不访问外网、不请求 `127.0.0.1` 之外的主机 |
| 凭证 | 报告中的 Cookie/CSRF/password/token 值全部替换为 `[REDACTED]`；测试账号使用随机合成邮箱 |
| 生产代码 | 只读；自检通过 monkeypatch/依赖覆盖临时注入错误，并在 `finally` 中恢复 |

`entry.py` 不读取 `backend/.env` 的真实值；启动前显式设置 `APP_NAME`、
`COOKIE_SECURE=false` 和一次性数据库的 `DATABASE_URL`。

## 3. 方法

### 3.1 schema 与请求生成

`from_asgi` 读取实时 `/openapi.json`，`get_all_operations()` 得到 28 个操作。
每个操作使用 `op.as_strategy(...)` 生成 `Case`，由 Hypothesis 执行：

- `max_examples`：**读 20 / 写 10**（`POST/PUT/PATCH/DELETE` 算写）；
  `ADVANCED_MAX_EXAMPLES=N` 或 `run.py --max-examples N` 可同时下调两个上限；
- `derandomize=True`、`database=None`、`deadline=None`；
- 单 worker；不使用 Schemathesis 的 CLI 并发/比率控制；
- 认证轮通过固定 `cookies={"session": ...}` 与 `headers={"X-CSRF-Token": ...}`
  注入夹具账号；匿名轮不注入。

路径参数（`job_id`、`application_id`、`slot_id`、`candidate_id`）由 Schemathesis
按 OpenAPI 的 `uuid` 格式随机生成，因此不对真实 ID 做假设，也不复用上一响应的 ID。

### 3.2 三轮

| 轮次 | 账号 | 操作范围 | 断言 |
| --- | --- | --- | --- |
| anonymous | 无 | 全部 28 个操作 | 注册/登录按公开契约；其余必须 `401`（`422` 记录为“校验先于认证”）；无 5xx |
| candidate | 真实注册并完成资料的候选人 | `/candidate/*` 与 `GET /users/me` | 自有资源读/写符合预期矩阵；`/employer/*` 全部必须 `403` |
| employer | 真实注册并完成资料的雇主 | `/employer/*` 与 `GET /users/me` | 自有资源读/写符合预期矩阵；`/candidate/*` 全部必须 `403` |

写操作只使用夹具自己拥有的资源或随机 UUID；随机 UUID 的期望是
`404/403/422`，不得出现 `500`。候选人与雇主轮对 `selfcheck` 之后才结束，
自检的 monkeypatch 在每项检查后立即恢复。

### 3.3 检查项与独立 oracle

Schemathesis 内置检查：

- `not_a_server_error`：任何未声明的 5xx；
- `status_code_conformance`：响应状态是否出现在 OpenAPI 的 `responses` 中；
- `response_schema_conformance`：声明过的状态码，其响应体是否符合 schema。

自定义检查（`hooks.py::make_expected_status_check`）：
`expected_status_matrix`，按上面的三轮矩阵逐操作断言状态码集合。矩阵是**手写**的，
来源是 `docs/REQUIREMENTS.md` 的 FP-AUTH-3/FP-SEC-1 与 `SPEC.md` 的 API 路由表，
不是从被测实现或实际响应反推的。

### 3.4 失败归因

`FailureStore` 对每个失败记录 `round / operation / status / check / category / count /
examples`，`category` 只能是：

- `real_defect`：实现/契约行为不符合需求或 OpenAPI schema（写 findings）；
- `schema_drift`：状态码是 FP-AUTH-3 等要求的行为，但 OpenAPI 没有声明该状态码
  （例如 401/403/404/409/400）；
- `test_config`：harness、策略生成、传输或自检配置问题。

不使用过滤器丢弃失败；schema drift 也按操作/状态逐条计数，只把它与真实缺陷分开归因。

### 3.5 受控自检（证明 oracle 会变红）

每次运行默认执行 `_selfcheck`（`--no-selfcheck` 可跳过），在**不改生产代码**的前提下注入：

| 自检 | 注入方式 | 期望 | 结果 |
| --- | --- | --- | --- |
| `wrong_role_matrix` | 覆盖 `require_employer` 依赖并让 `list_my_jobs` 返回 `[]` | 候选人访问 `/employer/jobs` 得到 200 → 自定义检查报错 | 检测到；恢复后 403 |
| `server_error` | 让 `employer.service.list_my_jobs` 抛 `RuntimeError` | app 返回 500 → `not_a_server_error` 报错 | 检测到；恢复后 200 |
| `response_schema` | 用合成 `requests.Response` 构造 `200 {"detail": ...}` | `response_schema_conformance` 报 `JsonSchemaError` | 检测到 |
| `status_code_conformance` | 候选人正常得到 403 | `status_code_conformance` 报 `UndefinedStatusCode` | 检测到 |

`wrong_role` 与 `server_error` 两项还验证了恢复后的干净路径（403 / 200），
防止自检留下永久 monkeypatch。

## 4. 结果（一次完整运行）

运行：`python tests/advanced/run.py apifuzz --out <仓库外空目录>`；
报告：`<out>/apifuzz/report.json`；完整运行报告内 `seconds` 为 **16–19 s**
（多次运行的负载差异；均远低于 5 分钟）。

| 轮次 | 操作数 | 请求数 | 2xx | 400 | 401 | 403 | 404 | 409 | 422 | 失败记录 | 失败次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| anonymous | 28 | 410 | 9（200） | 1 | 398 | 0 | 0 | 0 | 2 | 28 | 399 |
| candidate | 23 | 227 | 6（200） | 0 | 0 | 133 | 80 | 1 | 7 | 19 | 214 |
| employer | 23 | 227 | 6（200）+ 7（201） | 0 | 0 | 113 | 67 | 0 | 34 | 17 | 189 |
| **合计** | — | **864** | **28** | **1** | **398** | **246** | **147** | **1** | **43** | **64** | **802** |

- **5xx：0**。
- 匿名轮 `422-before-auth：0`；所有受保护操作实际都先返回 401。
- 候选/雇主轮所有 `/employer/*`、`/candidate/*` 的错角色请求均为 403。
- 随机 UUID 的写操作只出现 404/403/422，没有 500。
- 失败总次数 802，但按“轮次 × 操作 × 状态 × 检查 × 类别”聚合为 64 条记录。

状态码一致性检查（`status_code_conformance`）的 793 次失败分布：

| 状态 | 失败次数 | 归因 |
| ---: | ---: | --- |
| 401 | 398 | 匿名访问受保护操作；FP-AUTH-3 要求，但 FastAPI 的 OpenAPI 未声明 |
| 403 | 246 | 错角色/所有权；FP-AUTH-3 要求，但未声明 |
| 404 | 147 | 随机 UUID 对应对象不存在；FP-SEC-1/SPEC 要求，但未声明 |
| 400 | 1 | 注册重复邮箱；SPEC 声明了 400，但 OpenAPI 未声明 |
| 409 | 1 | 资料版本冲突；SPEC 声明了 409，但 OpenAPI 未声明 |

这些不是行为错误，而是 **OpenAPI 文档漂移**；报告仍完整列出，未静默过滤。
真正需要实现方处理的是下一节的 422 响应体缺陷。

### 4.1 一次运行的可复现性

两次独立的完整运行（相同 `PYTHONHASHSEED=4801`、相同 schema、相同代码）得到相同的
逐轮状态分布：`real_defect=9`、`schema_drift=793`、`test_config=0`。零参数 GET 的策略
空间是有限的，Hypothesis 可能在小于 20 次时耗尽并提前停止；因此表中部分无参数 GET
的请求数小于上限。`max_examples` 是**上限**，不是“必须生成恰好 N 次”的承诺。

## 5. 发现与归因

### 5.1 真实缺陷（已写入 `findings/P8.md`，未修复）

`POST /employer/interview-slots` 在业务校验失败（开始时间在过去、或晚于 3001 年）时返回：

```json
{"detail": "Slot must start in the future"}
```

但 OpenAPI 为该操作声明的 `422` 响应是 `HTTPValidationError`：

```json
{"detail": [{"loc": ["body", "starts_at"], "msg": "...", "type": "..."}]}
```

即 `detail` 应为数组，实际是字符串。本次运行 10 个雇主写样例中有 **9** 个命中，
`response_schema_conformance` 全部报 `ST108`。定位：

- `backend/app/interview/router.py:17` 把 `InvalidSlotError` 映射为 422；
- `backend/app/interview/router.py:37` 用 `HTTPException(..., str(error))` 返回字符串 detail；
- `backend/app/interview/service.py:44,47` 抛出该业务错误；
- `backend/app/main.py:32-41` 的 422 处理器只覆盖 `RequestValidationError`。

### 5.2 Schema 漂移（不是业务缺陷）

FastAPI 生成的 OpenAPI 只声明成功状态与 422，没有声明 FP-AUTH-3 要求的
401/403/404，也没有声明 SPEC 中的 400/409。测试把它们归为 `schema_drift`，
保留在报告里；修复方式是在路由上补充 `responses={...}` 或统一错误模型，
属于生产代码/API 文档工作，不在本任务范围内。

### 5.3 测试配置问题

本次运行 `test_config=0`，`harness_errors=0`。Schemathesis 与当前
FastAPI/Starlette 版本工作正常，没有触发任务说明中的降级方案。

## 6. 局限

1. **操作级、非状态序列**：每个操作独立生成请求，不执行多步工作流
   （例如“创建职位 → 投递 → 改状态 → 建时段 → 预约”）；需要多步状态的工作流
   属于 P2/P9 的范围。
2. **有限样例**：读 20 / 写 10 是有界采样，不是穷举；零参数 GET 可能更少。
3. **随机 UUID 只覆盖拒绝路径**：不尝试从响应中提取真实 ID 再访问，因此
   “本人资源成功路径”的深度由夹具账号与随机 UUID 决定，不覆盖跨用户 IDOR 的
   全部组合（P1/P2/专项套件覆盖）。
4. **ASGI 直连**：不经过 uvicorn/中间件代理，不验证端口、TLS、反向代理或真实
   网络超时行为；这是任务允许的进程内边界。
5. **Schema 漂移数量大**：793 次失败主要是 OpenAPI 未声明 4xx，不代表 793 个
   独立业务 bug；报告按检查与状态聚合，findings 只收录实现/契约缺陷。
6. **不验证并发**：单 worker、无并发；预约并发由 P2 的 Barrier 测试覆盖。
7. **自检注入的是受控回归**：证明 oracle 能变红，不证明生产代码在所有路径上都正确。

## 7. 复现与产物

```sh
# 完整模式（需要 PG_BIN 或 ADVANCED_PG_URL）
python tests/advanced/run.py apifuzz --out <仓库外空目录>

# 缩短采样（仍保留三轮与自检）
python tests/advanced/run.py apifuzz --max-examples 5 --out <仓库外空目录>
```

产物（均在仓库外）：

```text
<out>/apifuzz/report.json     # 本模式的机器可读报告（持久）
<out>/apifuzz/result.json     # run.py 的模式回执（会被 run.py 覆盖）
<out>/apifuzz/run.log         # stdout/stderr
<out>/summary.json            # run.py 顶层汇总
```

`report.json` 的关键字段：

- `rounds[*].operation_count` / `requests` / `status_counts` / `failures`；
- `failures[*]`：`category`、`check`、`status`、`count`、`examples[*].curl`；
- `attribution`：`real_defect` / `schema_drift` / `test_config` 计数；
- `selfcheck.checks`：每项受控回归的注入、检测与恢复结果；
- `outcome`：`clean` / `findings` / `error`；
- 默认 `exit_code=0`（发现已归因，报告可供人工决定）；`--fail-on-findings`
  可让任何 `real_defect`/`schema_drift` 导致退出 1；harness 或基础设施错误
  始终非零（`1`/`2`）。

## 8. 与验收命令的对应

| 命令 | 结果 |
| --- | --- |
| `python tests/advanced/run.py apifuzz` | 退出 0；`outcome=findings`；自检全部通过；报告已写 |
| `python tests/run_tests.py` | **251 passed**（P8 未改必测套件） |

`run.py` 的 `SLOW` 标记使 `apifuzz` 不进入 `python tests/advanced/run.py fast`；
显式点名或 `all` 仍会运行。

## Post-audit documentation retest

2026-11-26，在 `fix/final-audit-20261126` 修复分支（基线 `fa8317cbf3119433ff3ff0673a69bd3cf411db46` 加工作区补丁）补齐28个业务操作的实际4xx响应声明，统一为 `ErrorResponse`。原时段创建422的数组/字符串两种结构保留。业务函数、注册逻辑、成功响应和权限判断均不改变。

完整运行 `python tests/advanced/run.py apifuzz`，仍采用原读20/写10预算和三轮独立状态矩阵：

| 项目 | 历史证据 | 本轮复测 |
| --- | ---: | ---: |
| 业务操作 | 28 | 28 |
| 生成请求 | 864 | 864 |
| `real_defect` | 0 | 0 |
| `schema_drift` | 793 | **0** |
| `test_config` | 0 | **0** |
| selfcheck | 通过 | **4项全部通过** |
| outcome / exit | findings / 0 | **clean / 0** |

状态码自检原先依赖生产OpenAPI没有声明真实403。该缺口修好后，自检改为：先确认真实403符合schema，再只将测试响应对象临时改成未声明418，要求 `UndefinedStatusCode` 被检出，最后恢复403。其他三项受控回归仍保留。没有修改生成输入预算、预期状态矩阵、归因规则或屏蔽失败。

本轮必测253项通过；新增的 `test_fp_auth_3_openapi_documents_actual_error_shapes` 检查错误声明与真实未认证响应。历史251/252计数属于各自旧版本。

AUTH-01 仍按团队决定为 `not_a_bug_by_team_decision`，不修改注册实现。单worker的P8不建立同邮箱并发交错；原专项中4条状态码断言仍如实失败，不能因P8为clean就写成“注册并发问题已修复”。

本地原始证据：`tmp/final-audit-20261126/repair/apifuzz-verified/`（仓库之外）。修复分支未发布时，以上结论适用于工作区补丁，不冒充GitHub main的新测量。
