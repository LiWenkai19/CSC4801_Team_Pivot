# 高级测试套件（`tests/advanced/`）

本目录是课程项目的 **B 层高级测试**：有状态模型测试、LTL 轨迹检查、Z3 形式化、
差分/蜕变测试、变异测试、API 属性模糊测试、覆盖率与汇总报告。它与必测套件
`tests/unit/`、真实 PG 集成测试 `backend/tests/`、历史专项套件
`tests/specialized/` 相互独立：

- **不进入 Docker 镜像**；高级依赖固定在 `tests/advanced/requirements.txt`；
- **不修改生产代码**；发现业务缺陷只写 `docs/advanced_testing/findings/P<n>.md`；
- **产物只写仓库外**；`--out` 指向 checkout 内部会被直接拒绝；
- 只连**本机临时 PostgreSQL**，只向本机进程发请求，不访问外网。

P0 提供骨架与 `smoke` 模式；P1–P12 已在该骨架上实现全部高级技术。后续任务只需新增自己的模式目录，
**不要修改本目录的共享文件**（`run.py`、`conftest.py`、`requirements.txt`、
`support/{pg,traces}.py`，以及 `.gitignore` 和 CI 的 advanced job 归属见
`docs/advanced_testing/ADVANCED_TEST_PLAN.md` §1）。

## 1. 安装

在仓库根目录使用项目自己的虚拟环境（Windows 示例）：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r tests\advanced\requirements.txt
```

Linux/macOS/CI：

```sh
python -m pip install -r requirements.txt -r tests/advanced/requirements.txt
```

`tests/advanced/requirements.txt` 一次性固定了后续任务要用的全部依赖：
`hypothesis`、`z3-solver`、`mutmut`、`schemathesis`、`pytest-cov`、`coverage`。
注意 **mutmut 固定 3.7.0**：3.8.x 要求 `click>=8.4.2`，会与
`requirements.lock` 的 `click==8.1.8` 冲突；3.7.0 是最后一个兼容版本。后续任务
不要改这个文件；确需改动时先在任务里说明并取得授权。

## 2. PostgreSQL

高级套件只接受一次性 PostgreSQL，绝不连接共享开发库。两种方式：

| 场景 | 做法 |
| --- | --- |
| 本机开发 | 设置 `PG_BIN` 指向 PostgreSQL 服务器工具目录（含 `initdb`、`pg_ctl`、`postgres`），或给 `run.py` 传 `--pg-bin DIR`。`run.py` 会新建临时集群：`initdb`、随机端口、仅 `127.0.0.1`、`trust` 认证，结束后停止并删除。 |
| CI / 已准备好的一次性服务 | 设置 `ADVANCED_PG_URL`，例如 `postgresql+psycopg://postgres:postgres@127.0.0.1:5432/postgres`。`run.py` 直接使用该服务，不启动也不停止它；`conftest.py` 仍会在其上 `CREATE DATABASE advanced_<随机>` 并在结束时 `DROP ... WITH (FORCE)`。 |

限制：

- 只接受 `postgresql` 后端，主机只能是 `127.0.0.1`、`localhost`、`::1`；
  其他主机会被拒绝（`support/pg.py::validate_loopback_url`）。
- `ADVANCED_PG_URL` 中的密码不会被打印，也不会写进 `summary.json`。
- 管理连接默认连该服务的 `postgres` 数据库；CI 的 `postgres:15` service 满足这一点。
- 没有 PG 也能跑纯 Python 模式（如未来的 `formal`）：数据库夹具是惰性的，只有测试
  真正请求 `engine` / `client` / `account` / `db` / `clean_tables` 时才连接。
- 需要数据库的模式目录放一个空文件 `NEEDS_DB`，`run.py` 才会启动临时集群。
- 一次运行中只要所选模式里有一个带 `NEEDS_DB`，`run.py` 就只启动**一个**临时集群，
  供整批模式共用；每个 pytest 模式仍各自新建/删除自己的数据库。
- `entry.py` 模式不会加载 `conftest.py`；如果它需要数据库，必须自己在
  `ADVANCED_PG_URL` 上建库、迁移并在退出前清理，或复用 `support/pg.py` 的规则。

Windows 本机若没有 PostgreSQL 服务工具，可以用任意便携版 PostgreSQL 15 的 `bin`
目录作为 `PG_BIN`；不要指向系统上正在运行的共享实例做测试。

## 3. 命令

```sh
# 列出自动发现到的模式及 SLOW / NEEDS_DB / runner
python tests/advanced/run.py list

# 单个模式
python tests/advanced/run.py smoke
python tests/advanced/run.py stateful
python tests/advanced/run.py ltl
python tests/advanced/run.py formal
python tests/advanced/run.py differential
python tests/advanced/run.py intramorphic
python tests/advanced/run.py apifuzz
python tests/advanced/run.py mutation
python tests/advanced/run.py coverage

# 所有非 SLOW 模式（CI push 使用）
python tests/advanced/run.py fast

# 所有模式
python tests/advanced/run.py all
```

选项：

```text
--out DIR          产物目录，必须在 checkout 之外，且不存在或为空；默认新建系统临时目录
--pg-bin DIR       PostgreSQL 服务器工具目录；也认环境变量 PG_BIN
--max-examples N   以 ADVANCED_MAX_EXAMPLES 传给子进程（各模式自行读取并设上限）
```

示例（Windows PowerShell）：

```powershell
$env:PG_BIN = "C:\tools\pgsql\bin"
.\.venv\Scripts\python.exe tests\advanced\run.py smoke --out "$env:TEMP\adv-smoke"
```

Linux：

```sh
PG_BIN=/usr/lib/postgresql/15/bin python tests/advanced/run.py fast --out "$RUNNER_TEMP/advanced"
```

退出码：`0` 全部成功；`1` 至少一个模式失败；`2` 参数/基础设施错误（例如
`--out` 在仓库内、PG 无法启动）。任一模式失败都会继续跑完其余模式，便于一次
收集全部失败，但最终仍返回非零。

## 4. 模式自动发现（新增模式不用改 `run.py`）

`tests/advanced/` 下**每个子目录就是一个模式**，模式名 = 目录名。例外：

- `support/`：共享 Python 包，不是模式；
- `experiments/`：实验材料（如 P10 的 LLM 盲测），不是模式；
- `__pycache__/`、以 `.` 开头的目录：忽略。

目录约定：

| 文件 | 作用 |
| --- | --- |
| `entry.py` | 存在时以子进程 `python entry.py`（cwd = 该目录）运行；否则对该目录跑 `pytest`。 |
| `SLOW` | 空文件。有它则**不进入** `fast`；`all` 和显式点名仍会运行。 |
| `NEEDS_DB` | 空文件。有它则 `run.py` 为该模式启动一次性 PostgreSQL，并设置 `ADVANCED_PG_URL`。 |

新增模式的步骤：

1. 新建目录，例如 `tests/advanced/ltl/`；
2. 放 `test_*.py`（pytest 模式）或 `entry.py`（脚本模式）；
3. 需要数据库就 `New-Item tests/advanced/ltl/NEEDS_DB`；很慢就再加 `SLOW`；
4. `python tests/advanced/run.py list` 确认被发现；
5. 不需要改 `run.py`、`conftest.py`、`requirements.txt` 或 CI。

每个模式在独立子进程中运行，互不共享 Python 状态；数据库也是每个 pytest 会话
新建一个 `advanced_<随机>` 库。

默认超时：`run.py` 不设置模式超时（`SLOW` 模式可能跑很久），由调用方/CI job 的
`timeout-minutes` 兜底。`entry.py` 自己应打印结构化结果并返回非零表示失败。

## 5. 共享夹具（`tests/advanced/conftest.py`）

所有 pytest 模式自动获得以下夹具。**数据库夹具惰性连接**，不需要 PG 的模式可以
直接收集和运行。

| 夹具 | 签名 / 用法 | 说明 |
| --- | --- | --- |
| `engine` | session 级，`engine` | 在 `ADVANCED_PG_URL` 上 `CREATE DATABASE advanced_<随机>`，跑 `alembic upgrade head`，结束时 `DROP DATABASE ... WITH (FORCE)`。没有 `ADVANCED_PG_URL` 时，只有请求它的测试会失败并提示用 `run.py`。 |
| `clean_tables` | `clean_tables`（fixture）或 `clean_tables()`（返回的 callable） | **不是 autouse**。显式请求时先 `TRUNCATE` 全部应用表（`RESTART IDENTITY CASCADE`）；返回的 callable 可在测试中途再次清空。大多数测试应只造自己需要的行。 |
| `db` | `db` | 直接对测试库做持久化断言的 `Session`。需要 `engine`。 |
| `client` | `client` | 真实 `app.main.app` 的 `TestClient`，只把 `get_db` 覆盖为测试库；每个响应后清空 Cookie 罐，所以多账户请求只由显式 `headers` 决定身份。 |
| `account` | `headers, user_id = account(role="candidate"\|"employer", skills=None, name=None)` | 通过真实注册 + 资料接口创建角色，返回 `(headers, uuid.UUID)`。`headers` 形如 `{"Cookie": "session=...", "X-CSRF-Token": "..."}`。密码和会话值不会出现在断言消息里。 |
| `evidence` | `evidence(name, data)` | 把 JSON 写到 `$ADVANCED_OUT/<mode>/<name>.json`；`run.py` 会设置这两个变量。直接 `pytest` 且没有 `ADVANCED_OUT` 时退到系统临时目录。`name` 中的非安全字符会替换为 `_`。 |
| `utc_future` | `utc_future(days=1, minutes=0) -> datetime` | 返回**带 UTC 时区**的“现在 + 偏移”，用于建未来时段/预约。 |

使用示例：

```python
def test_candidate_can_see_own_profile(client, account):
    headers, user_id = account("candidate", skills=["Python", "sql"])
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["id"] == str(user_id)


def test_slot_is_in_future(account, utc_future):
    employer, _ = account("employer")
    start = utc_future(days=2, minutes=15)
    assert start > datetime.now(timezone.utc)
```

`conftest.py` 在导入任何 `app` 之前强制设置 `APP_NAME`、
`COOKIE_SECURE=false`、占位的 `DATABASE_URL`，并把 `backend/` 与
`tests/advanced/` 加入 `sys.path`；因此测试进程不会误读开发库配置，也不依赖
`backend/.env` 的真实值。

## 6. `run.py` 为子进程设置的环境

| 变量 | 值 / 作用 |
| --- | --- |
| `PYTHONHASHSEED` | `4801`（所有模式一致）。 |
| `PYTHONUTF8` / `PYTHONIOENCODING` | `1` / `utf-8`。 |
| `PYTHONDONTWRITEBYTECODE` | `1`。 |
| `PYTHONPATH` | `backend/` + `tests/advanced/` + 原有值。 |
| `ADVANCED_OUT` | 本次运行的 `--out` 绝对路径。 |
| `ADVANCED_MODE` | 当前模式名；`evidence` 用它决定子目录。 |
| `ADVANCED_PG_URL` | 仅 `NEEDS_DB` 模式设置：CI 传入的一次性服务，或 `run.py` 新建的临时集群。 |
| `ADVANCED_MAX_EXAMPLES` | 仅传了 `--max-examples` 时设置。 |
| `TEMP` / `TMP` / `TMPDIR` | 指向 `<out>/temp`，避免临时文件散落。 |
| 清除 | 继承环境中的 `DATABASE_*`、`CANDIDATE_TEST_*`、`EMPLOYER_TEST_*` 一律删除。 |

各模式仍应遵守确定性约定：Hypothesis `derandomize=True` 或固定 seed、`deadline=None`；
随机数用 `random.Random(4801)`；`max_examples` 有上限；不要依赖系统时间或网络。

## 7. 产物结构

`--out` 必须是仓库外的新目录或空目录；`run.py` 不会覆盖旧证据。

```text
<out>/
  summary.json                 # 顶层汇总
  temp/                        # 子进程临时目录
  <mode>/
    result.json                # 该模式的命令、退出码、耗时、junit 路径
    run.log                    # 子进程 stdout+stderr（pytest 摘要、entry 输出）
    junit.xml                  # pytest 模式才有
    <evidence-name>.json       # 测试通过 evidence() 写的证据
```

`summary.json` 字段（稳定接口，P11 的 `report.py` 依赖）：

```json
{
  "sha": "<git rev-parse HEAD>",
  "branch": "<branch>",
  "git_status_clean": false,
  "git_status": "?? ...",
  "seed": 4801,
  "max_examples": null,
  "python": "...", "python_executable": "...", "argv": ["..."],
  "modes_requested": ["smoke"],
  "pg": {"requested": true, "external": false, "started": true, "mode": "disposable"},
  "results": [
    {"mode": "smoke", "kind": "pytest", "command": ["..."], "cwd": "...",
     "exit_code": 0, "seconds": 6.01, "junit": "...", "log": "...",
     "slow": false, "needs_db": true, "seed": 4801, "max_examples": null}
  ],
  "exit_code": 0,
  "error": null,
  "finished_at": "2026-11-25T16:38:53+00:00"
}
```

`pg.started` 表示本次运行是否**由 `run.py` 启动**了临时集群；使用
`ADVANCED_PG_URL` 时它是 `false`。`error` 非空表示基础设施错误（PG 起不来等），
此时对应模式不会留下 `result.json`。

## 8. 轨迹与原子命题命名（P2 写，P3 读）

`support/traces.py` 定义共享轨迹格式，**只做数据结构与 JSON 读写**，不含业务逻辑。

```python
@dataclass(frozen=True)
class Event:
    step: int                # 非负整数，生产方自选 0 或 1 起
    action: str              # apply | set_status | create_slot | book | delete_slot | observe
    ok: bool                 # 该步操作是否成功
    props: frozenset[str]    # 该步“之后”成立的原子命题
```

一个 JSON 文件 = 一条轨迹（事件列表）。`props` 写盘时按字典序放入数组，读回时
还原为 `frozenset`；重复原子会报错。读目录时按文件名**字典序**排序。

```python
from support.traces import Event, read_traces, write_trace

write_trace(out_dir / "trace-0001.json", [
    Event(0, "apply", True, frozenset({"applied:a1", "status:a1:Pending"})),
    Event(1, "set_status", True, frozenset({"applied:a1", "status:a1:Interviewing"})),
])
traces = read_traces(out_dir)   # list[list[Event]]
```

**原子命题命名规则**（后续任务必须遵守，P3 的字母表按此解析）：

```text
<namespace>:<subject>[:<value>]
```

- 全小写 ASCII，`:` 分隔，不允许空格和换行；
- 标识符用稳定的短标签（如 `a1`、`s1`、`c1`），不要用 UUID，保证轨迹可读、可比较；
- 状态值使用应用枚举的原始大小写拼写：`Pending`、`Interviewing`、`Rejected`、`Accepted`；
- 已使用的命名：

| 原子 | 含义 | 例 |
| --- | --- | --- |
| `applied:<application>` | 申请存在 | `applied:a1` |
| `status:<application>:<Status>` | 申请当前状态 | `status:a1:Interviewing` |
| `booked:<application>:<slot>` | 申请与时段已绑定预约 | `booked:a1:s1` |
| `available:<slot>` | 时段空闲（候选人的可用列表里可见） | `available:s1` |
| `deleted:<slot>` | 时段已被删除（若需要显式记录） | `deleted:s1` |
| `slot:<slot>` | 时段存在 | `slot:s1` |
| `new_booking:<application>` | 本步新建了预约（仅当步出现） | `new_booking:a1` |

约定：`props` 表示**该步完成后的状态切片**，不是增量；每一步应写出所有需要被
LTL 检查的相关真命题（至少覆盖该模式性质里出现的原子）。同一个原子在一个
`frozenset` 里只能出现一次。

## 9. 确定性、安全与自检

- **确定性**：`PYTHONHASHSEED=4801`；Hypothesis `derandomize=True` 或固定 seed，
  `deadline=None`；随机数用 `random.Random(4801)`；`max_examples` 有明确上限。
- **安全**：只连本机临时 PG；只请求本机进程；不访问外网；不读 `backend/.env`
  的真实值；日志、`evidence()`、`summary.json` 里不出现 Cookie、CSRF、密码或哈希。
- **证明测试会失败**：每个新 oracle / 不变量至少做一次“故意引入错误 → 测试变红 →
  恢复”的自检。可以在测试代码里临时改断言，或用 `monkeypatch` 构造受控变体，
  **不要改生产代码**。把自检结果写进任务汇报；没有自检的 oracle 不算 oracle。
- **独立 oracle**：期望值必须来自需求、手算或独立实现，不得调用被测函数生成期望值。

## 10. 当前模式（全部已实现）

| 模式 | 状态 | 归属 | SLOW | NEEDS_DB | 运行器 | 说明 |
| --- | --- | --- | --- | --- | --- | --- |
| `smoke` | 已实现 | P0 | 否 | 是 | pytest | 迁移后 `user` 表存在；真实注册的候选人 `GET /users/me` 返回 200。 |
| `stateful` | 已实现 | P2 | 否 | 是 | pytest | Hypothesis 状态机，预约生命周期 5 条不变量；写出 P3 轨迹。 |
| `ltl` | 已实现 | P3 | 否 | 是 | pytest | 有限轨迹 LTL 检查器 + 232 个自检；relax/restrict 演示。 |
| `formal` | 已实现 | P4/P5 | 否 | 否 | pytest | Z3 匹配规格证明（T1–T7/N1–N2）、预约 BMC（k=6）与 k-归纳；纯 Python。 |
| `differential` | 已实现 | P6 | 否 | 是 | pytest | 600 对 Python 打分 vs SQL 打分；600 对候选人/雇主视图。 |
| `mutation` | 已实现 | P7 | 是 | 否 | entry | 自研 AST 变异引擎，304 个变异体；需要 `frontend/node_modules` 以保持单元套件与本机一致。 |
| `apifuzz` | 已实现 | P8 | 是 | 是 | entry | Schemathesis 进程内 ASGI，864 请求、0 个 5xx。 |
| `intramorphic` | 已实现 | P9 | 否 | 是 | pytest | 5 条蜕变工作流 + 5 条防护层内蜕变 + 2 个自检。 |
| `coverage` | 已实现 | P11 | 是 | 是 | entry | 分组测量 `backend/app` 分支覆盖（unit/integration/stateful/differential/intramorphic），写 `coverage-summary.json` 与 `coverage.xml`；unit 组需要 `frontend/node_modules`。 |

`python tests/advanced/run.py fast` 运行所有非 `SLOW` 模式（`smoke`、`stateful`、`ltl`、
`formal`、`differential`、`intramorphic`），供 CI 的 `advanced` job 在每次 push/PR 使用。
`python tests/advanced/run.py all` 再加上 `mutation`、`apifuzz`、`coverage`，供每周
`advanced-slow` job 与正式证据运行使用。`mutation`/`coverage` 需要 Node 依赖，因为
被测的 `tests/unit/test_rendering.py` 会调用真实 React 组件；CI 的两个 advanced job
都会先执行 `npm --prefix frontend ci`。

## 11. 故障排查

| 现象 | 处理 |
| --- | --- |
| `ADVANCED_PG_URL is not set` | 用 `run.py` 运行；或设置 `ADVANCED_PG_URL` 指向一次性本机服务。 |
| `PostgreSQL server tools not found` | 设置 `PG_BIN` 或传 `--pg-bin`，目录里要有 `initdb`/`pg_ctl`/`postgres`。 |
| `Refusing non-loopback PostgreSQL host` | 只允许 `127.0.0.1`/`localhost`/`::1`；不要指向远程或共享库。 |
| `--out must be outside the checkout` | 产物可能在日志里含合成会话令牌，必须写到仓库外。 |
| `--out must be new or empty` | 换新目录；旧证据不会被覆盖。 |
| pytest 报 `No module named support` | 从仓库根用 `python tests/advanced/run.py ...`；`run.py` 负责 `PYTHONPATH`。 |
| 端口被占用/残留进程 | `run.py` 用随机端口并正常停止；异常退出后可手工结束 `postgres` 进程并删除系统临时目录下的 `csc4801-advanced-pg-*`。 |
