# 依赖与密钥扫描（P12）

本文件记录独立安全 workflow（`.github/workflows/security.yml`）的三个扫描、
2026-11-26 本地运行结果、逐条归因，以及 P12b 的依赖修复与验证。
所有原始日志、报告和下载校验文件都在**仓库外**的
`D:\Study\Y4 - CSC4801\_evidence\P12\` 和 `...\P12b\`；仓库内只保留汇总数字与结论。

## 1. 结论摘要

| 扫描 | 本地命令 | 本地结果 | workflow 预期 |
| --- | --- | --- | --- |
| 全历史密钥 | `gitleaks git . --redact=100 --no-banner --exit-code 1` | 基线 34 条命中 → 允许列表后 **0 条，exit 0** | 绿色 |
| Python 依赖 | `pip-audit -r requirements.lock --strict --ignore-vuln PYSEC-2026-1845` | 修复前 **15 条记录 / 12 个唯一 advisory / 7 个包**，exit 1；修复后 **0 条待处理**（仅 pytest 的 2 条记录被接受），exit 0 | 绿色 |
| 前端依赖 | `npm --prefix frontend audit --omit=dev --audit-level=high` | **0 个漏洞**，exit 0 | 绿色 |

- 密钥命中全部为误报：28 条是版本校验清单里的 SHA-256 文件摘要，6 条是测试夹具里的
  合成 `SECRET_KEY`。**未发现真实密钥，无需按任务要求中止报告。**
- Python 依赖的 12 个 advisory 均有修复版本。P12b 删除了 5 个未使用的 starter 包，
  升级了 `anyio`/`certifi`/`dnspython`/`urllib3`；唯一接受的风险是 pytest 的
  `PYSEC-2026-1845`，已在 workflow 中按精确 ID 忽略并写明理由（见 4.3）。
- P12b 修改了 `requirements.lock`（任务允许的路径）；修复前后数字和验证记录见 4.3。
- 前端生产依赖 0 漏洞；`npm audit` 按任务要求使用 `--omit=dev`，devDependencies
  不在该 job 的范围内。

## 2. workflow 设计

文件：`.github/workflows/security.yml`。触发条件：

- `push` 到 `main`；
- 所有 `pull_request`；
- 每周一 04:17 UTC 的 `schedule`；
- 手动 `workflow_dispatch`。

顶层 `permissions: contents: read`；三个 job 各自有 `timeout-minutes`。
没有使用任何需要 licence key 的 gitleaks marketplace action，也没有 `pull_request_target`。

### 2.1 gitleaks job

1. `actions/checkout@v4` 带 `fetch-depth: 0`，扫描完整历史。
2. 从 GitHub Releases 下载固定版本 `gitleaks 8.30.1` 的
   `gitleaks_8.30.1_linux_x64.tar.gz`。
3. 用 workflow 内硬编码的 SHA-256 校验：
   `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`
   （来源：同版本 release 的 `gitleaks_8.30.1_checksums.txt`）。本地已重新下载
   该 Linux 包并核对哈希一致，且包内包含根目录的 `gitleaks` 可执行文件。
4. 校验 `gitleaks version` 等于固定版本后运行：
   `gitleaks git . --redact=100 --no-banner --exit-code 1`。
5. `.gitleaks.toml` 通过 `[extend] useDefault = true` 继承官方规则，只增加两条
   精确允许列表（见第 3 节）。

### 2.2 pip-audit job

- Python 3.12（与 `ci.yml` 一致）。
- `python -m pip install "pip-audit==2.10.1"`。
- `pip-audit -r requirements.lock --strict --ignore-vuln PYSEC-2026-1845`。
  `--strict` 保证依赖解析失败不会被静默忽略；唯一被忽略的 advisory 是 pytest 的
  UNIX `/tmp` 本地权限问题，理由见 4.3。

### 2.3 npm-audit job

- Node 22（与 `ci.yml` 一致）。
- `npm --prefix frontend ci --no-audit --no-fund`，然后
  `npm --prefix frontend audit --omit=dev --audit-level=high`。
- `ci` 阶段的 `--no-audit` 只是避免重复审计，显式的 audit 步骤是唯一门禁。

## 3. 全历史密钥扫描

### 3.1 工具与本地结果

- gitleaks 8.30.1（Windows x64 官方 release，SHA-256
  `d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e` 已核对）。
- 基线：`64 commits scanned`，`3.49 MB`，`34` 条命中，全部规则为
  `generic-api-key`，exit 1。
- 加入 `.gitleaks.toml` 后：`64 commits scanned`，`no leaks found`，exit 0。
- 提交后再次扫描（本地 `--all` 可见其他分支，共 69 个 commit）：仍为 0 条命中，exit 0。
- 本地用未脱敏临时报告做独立分类后已删除：28 条为 64 位十六进制 SHA-256，
  6 条为合成测试密钥，**0 条无法归类**。

### 3.2 34 条命中逐条归因

| 文件 | 命中数 | 规则 | 归因 |
| --- | ---: | --- | --- |
| `docs/testing/editor-version-verification.json` | 12 | `generic-api-key` | 版本校验清单的 SHA-256 摘要；文件已不在 HEAD，只存在于历史 |
| `docs/testing/version-verification.json` | 6 | `generic-api-key` | 同上 |
| `docs/testing/version-retest-verification.json` | 6 | `generic-api-key` | 同上 |
| `docs/CANDIDATE_BASELINE.json` | 4 | `generic-api-key` | 同上 |
| `backend/employer_tests/conftest.py` | 2 | `generic-api-key` | 测试夹具合成 `SECRET_KEY`（历史路径） |
| `backend/candidate_tests/conftest.py` | 1 | `generic-api-key` | 同上 |
| `backend/candidate_tests/test_candidate_accounts.py` | 1 | `generic-api-key` | 同上 |
| `backend/tests/users/test_account_responses.py` | 1 | `generic-api-key` | 同上 |
| `frontend/tests/employer.browser.mjs` | 1 | `generic-api-key` | 浏览器验证脚本启动临时后端用的合成 `SECRET_KEY` |

合计 34 条，来自 6 个 commit、9 个文件、1 条规则。没有真实密钥、Token、私钥或
个人数据。合成值只用于测试进程内启动应用，不用于签名任何生产凭据。

### 3.3 允许列表设计

`.gitleaks.toml` 使用 `[extend] useDefault = true` 保留官方全部规则，只增加两条
`[[allowlists]]`，且都使用 `condition = "AND"`：

| 允许项 | 精确文件路径 | 精确值 |
| --- | --- | --- |
| 版本校验清单 | `^docs/(?:CANDIDATE_BASELINE\.json|testing/(?:editor-version-verification|version-verification|version-retest-verification)\.json)$` | `^[0-9a-f]{64}$`（只允许完整 SHA-256） |
| 测试夹具 | `^(?:backend/(?:tests|employer_tests|candidate_tests)/.+\.py|frontend/tests/(?:candidate|employer)\.browser\.mjs)$` | `^isolated(?:-ui)?-test-key-with-at-least-32-characters$` |

因此：

- 没有整体关闭 `generic-api-key` 规则；
- 同一合成值如果出现在允许路径之外，仍会报告；
- 同一文件里出现真实密钥（不是完整 64 位十六进制摘要）仍会报告。

### 3.4 自检：允许列表不是“一键变绿”

1. 删除/绕过 `.gitleaks.toml`（使用官方默认配置）→ 34 条命中，exit 1。
2. 恢复 `.gitleaks.toml` → 0 条命中，exit 0。
3. 在一个一次性临时 git 仓库中构造三类输入：
   - 允许路径 + 允许的合成值：被抑制；
   - 同一合成值放到 `elsewhere/`：**仍被报告**；
   - 非允许值的假 Token：**仍被报告**（`stripe-access-token` 规则）。
   结果 3 条命中、exit 1，证明允许列表按“路径 AND 值”精确生效。
4. 对下载的 Linux 包追加一个字节后重新计算 SHA-256，与 workflow 中硬编码值不匹配，
   `sha256sum --check --strict` 会失败；说明 checksum 门禁确实会拦截被篡改的下载。
5. 用一个结构校验脚本检查 workflow：三个 job、四个触发条件、`contents: read`、
   `fetch-depth: 0`、三条必需命令都存在；把 `fetch-depth: 0` 改成 `1` 后校验失败，
   改回后通过。

## 4. Python 依赖审计

### 4.1 本地结果

修复前：

```text
pip-audit 2.10.1 / Python 3.12.0
pip-audit -r requirements.lock --strict
Found 15 known vulnerabilities in 7 packages   (exit 1)
```

`--strict` 没有报依赖解析失败；exit 1 来自 advisory。15 条原始记录中有 3 组重复
（Flask、pytest、certifi 各重复一次），唯一 advisory 为 12 个。

修复后（不忽略 pytest）：

```text
pip-audit -r requirements.lock --strict
Found 2 known vulnerabilities in 1 package      (exit 1)
# 仅 pytest 8.4.2 的 PYSEC-2026-1845，2 条重复记录
```

修复后（按 4.3 接受 pytest 风险）：

```text
pip-audit -r requirements.lock --strict --ignore-vuln PYSEC-2026-1845
No known vulnerabilities found, 2 ignored       (exit 0)
```

### 4.2 逐包归因

以下版本是 **P12b 修复前**的锁定版本；处理后状态见 4.3。

“可达性”指本仓库运行时是否有代码路径会触发对应漏洞；判断依据是
`git grep`（排除 `frontend/node_modules`）以及 `backend/app`、`backend/scripts`
的实际调用。应用是 FastAPI，不使用 Flask/Werkzeug；没有出站 HTTP/TLS 客户端；
没有 DNS wire/zone 解析代码。

| 包（锁定版本） | 原始记录 | Advisory（修复版本） | 可达性判断 |
| --- | ---: | --- | --- |
| `flask 3.1.2` | 2 | `PYSEC-2026-2151` / `CVE-2026-27205`（3.1.3） | **不可达**：全仓库无 `flask` 导入；应用不使用 Flask `session`，因此 `Vary: Cookie` 缓存问题没有触发路径 |
| `werkzeug 3.1.8` | 1 | `PYSEC-2026-4312` / `CVE-2026-102598`（3.1.9） | **不可达**：无 `werkzeug` 导入；不使用 `safe_join`，且部署容器是 Linux |
| `pytest 8.4.2` | 2 | `PYSEC-2026-1845` / `CVE-2025-71176`（9.0.3） | **仅测试工具**：问题在 UNIX `/tmp/pytest-of-{user}` 本地权限/DoS；CI runner 是一次性的，应用运行时不需要 pytest |
| `anyio 4.14.0` | 3 | `PYSEC-2026-4025` / `CVE-2026-63374`；`PYSEC-2026-4023` / `CVE-2026-63349`；`PYSEC-2026-4024` / `CVE-2026-64847`（4.14.2） | **不可达**：作为 Starlette 的传递依赖被加载，但应用不使用 `connect_tcp()`/`TLSStream.wrap()` 做出站 TLS，不使用 `anyio.run_process/open_process` 或进程池；没有 `extra_groups` 调用 |
| `certifi 2026.6.17` | 2 | `PYSEC-2026-4320`（2026.10.18） | **不可达**：certifi 只影响出站 TLS 的 CA 信任库；应用没有出站 HTTPS 客户端 |
| `dnspython 2.8.0` | 2 | `CVE-2026-114605`（2.9.0）；`CVE-2026-128089`（2.9.2） | **不可达**：`EmailStr` 经 Pydantic 调用 email-validator，且 Pydantic 2.13.4 固定使用 `check_deliverability=False`；应用不解析 DNS wire message 或 zone file |
| `urllib3 2.7.0` | 3 | `PYSEC-2026-4175` / `CVE-2026-97687`；`PYSEC-2026-4176` / `CVE-2026-97688`；`PYSEC-2026-4177` / `CVE-2026-97689`（2.8.0） | **不可达**：全仓库无 `urllib3` 导入；应用不做出站 HTTP，因此 streaming/proxy TLS 路径不会被调用 |

补充说明：`tests/specialized` 里确有 `httpx.Client` 和 `urllib.request.urlopen`，但只连
本机进程/本机回环地址，不使用 TLS、不受理不可信响应，也不在生产镜像的请求路径中。
`requirements.lock` 的 Flask/Werkzeug 等条目是历史 starter 依赖，未在
`backend/pyproject.toml` 声明；P12b 已在确认无导入后删除它们（见 4.3）。

### 4.3 处理结果（P12b）

#### 删除的未使用 starter 包

先执行 `git grep`，确认 `backend/`、`tests/`、`frontend/` 中都没有这些包的导入
（Python 包搜 `import`/`from`，frontend 不涉及 Python 包名）：

| 包 | 删除前版本 | 导入检查 |
| --- | --- | --- |
| `Flask` | 3.1.2 | 0 处 import/from |
| `Werkzeug` | 3.1.8 | 0 处 import/from |
| `waitress` | 3.0.2 | 0 处 import/from |
| `blinker` | 1.9.0 | 0 处 import/from |
| `itsdangerous` | 2.2.0 | 0 处 import/from |

`Jinja2`、`MarkupSafe`、`click` 先保留；干净的 Python 3.12 环境执行
`pip install -r requirements.txt` 后 `pip check` 返回
`No broken requirements found.`。用 `importlib.metadata` 反查保留原因：
`fastapi[standard]` 需要 `Jinja2`，`Jinja2`/`Mako` 需要 `MarkupSafe`，
`uvicorn`/`rich-toolkit` 需要 `click`（测试工具 `mutmut` 也需要 `click`）。
`requirements.lock` 中的 starter 注释也同步改为“只在其他包仍需要时保留”。

注意：`tests/advanced/requirements.txt` 的 `schemathesis` 会在**测试 venv** 中
重新拉入 `Werkzeug 3.1.9`；它不属于运行时锁文件，不会进入 Docker 镜像。

#### 升级的包

| 包 | 修复前 | 修复后 | 对应 advisory |
| --- | --- | --- | --- |
| `anyio` | 4.14.0 | 4.14.2 | PYSEC-2026-4023 / 4024 / 4025 |
| `certifi` | 2026.6.17 | 2026.10.18 | PYSEC-2026-4320 |
| `dnspython` | 2.8.0 | 2.9.2 | CVE-2026-114605 / CVE-2026-128089 |
| `urllib3` | 2.7.0 | 2.8.0 | PYSEC-2026-4175 / 4176 / 4177 |

升级后 `pip check` 仍通过，说明没有引入新的依赖冲突。`pytest` 未升级。

#### 接受的风险

只接受 `pytest 8.4.2` 的 `PYSEC-2026-1845` / `CVE-2025-71176`，在
`.github/workflows/security.yml` 的 pip-audit 命令中使用精确的
`--ignore-vuln PYSEC-2026-1845`，并在命令上方注释：

- 只影响测试工具 `pytest`，不影响生产运行时；
- 问题是 UNIX `/tmp/pytest-of-{user}` 的本地权限/DoS；
- CI runner 是一次性的，不存在共享本地用户；
- 生产镜像运行时不使用 pytest。

#### 修复前后 pip-audit 数字

| 状态 | 命令 | 结果 | 退出码 |
| --- | --- | --- | --- |
| 修复前 | `pip-audit -r requirements.lock --strict` | 15 条记录 / 12 唯一 advisory / 7 个包 | 1 |
| 修复后，不 ignore | `pip-audit -r requirements.lock --strict` | 2 条记录 / 1 唯一 advisory / 1 个包（仅 pytest） | 1 |
| 修复后，按上面接受风险 | `pip-audit -r requirements.lock --strict --ignore-vuln PYSEC-2026-1845` | `No known vulnerabilities found, 2 ignored` | 0 |

#### 验证记录

- 干净 Python 3.12 venv（位于仓库外）：
  - `pip install -r requirements.txt`：exit 0；`pip check`：`No broken requirements found.`。
  - `pip install -r requirements.txt -r tests/advanced/requirements.txt`：exit 0，
    无依赖冲突；随后 `pip check` 仍通过。
  - `python tests/run_tests.py`：**251 passed**（15.79s，1 个既有 Starlette 弃用警告）。
  - `pip-audit -r requirements.lock --strict --ignore-vuln PYSEC-2026-1845`：exit 0。
- 临时 PostgreSQL 17.6（随机端口、仅 127.0.0.1、trust 认证）：
  - `python tests/run_tests.py --integration`：**241 passed**（89.53s）。
  - `python tests/advanced/run.py fast`：**4 个模式（differential、formal、smoke、stateful）
    全部 exit 0**，合计 79.09s，`summary.json` 的 `exit_code` 为 0。
- 备注：Windows 上 Python 3.12 自带 `ensurepip` 的 pip 23.2.1 在读取含中文注释的
  `tests/advanced/requirements.txt` 时会用 cp936 解码失败；把该验证 venv 的 pip 升到
  26.2.2 后，同一条组合安装命令 exit 0。这是 pip/locale 问题，不是依赖版本冲突；
  CI 是 UTF-8 的 Linux 环境。运行时锁文件本身不受影响。

**合并条件：PR 必须等 CI 的 `docker` job 变绿后才能合并。**

## 5. 前端依赖审计

```text
npm --prefix frontend ci        # 31 packages
npm --prefix frontend audit --omit=dev --audit-level=high
found 0 vulnerabilities         # exit 0
```

生产依赖（lockfile 中 `dev != true` 的包）为 `cookie`、`react`、`react-dom`、
`react-router`、`react-router-dom`、`scheduler`、`set-cookie-parser`，共 7 个，
全部未命中 advisory。CI 使用 Node 22；本地审计使用 npm 11.12.1 / Node 24.15.0，
结果由 `frontend/package-lock.json` 决定，升级 Node 不会改变锁文件内容。

## 6. FP-SEC-4 的人工补充检查

- `git ls-files` 中只有 `backend/.env.example` 一个 env 文件；`backend/.env` 被
  `.gitignore` 的 `*.env` 规则忽略，未读取其真实值。
- `backend/.env.example` 只有占位符（`APP_NAME=YOUR_NAME`、
  `DATABASE_URL=YOUR_DATABASE_URL`）和非敏感的默认值；没有真实密钥。
- `demo-local-only` 是 README/INSTALL/seed 和浏览器测试使用的**公开演示密码**，
  不是真实凭据；当前 gitleaks 规则未命中它，因此没有为它添加允许列表。若未来规则
  开始命中，应按“精确文件 + 精确字符串”的方式补充，而不是关闭规则。
- 全历史扫描覆盖基线时的 64 个 commit（提交后本地因 `--all` 含其他分支 ref
  变为 69 个）；gitleaks 的 `--redact=100` 保证日志和 CI 输出不打印命中值。

### 局限

- gitleaks 是启发式扫描器；`generic-api-key` 的 stopword/allowlist 机制可能漏掉
  含常见词的合成值（例如 `candidate` 内含 `date`）。因此“0 命中”是证据之一，
  不是“绝对没有密钥”的证明；新增代码仍应人工 review。
- `gitleaks git` 扫描的是 `git log -p` 中的新增行，仅由 merge resolution 引入的
  内容可能不在 diff 中；PR 和每周定时扫描降低但不能消除该风险。
- pip-audit 的可达性判断基于当前代码；如果以后增加出站 HTTP/TLS、DNS wire 解析
  或进程池调用，需要重新评估。

## 7. 复现与证据

本地（仓库根目录）：

```bash
gitleaks git . --redact=100 --no-banner --exit-code 1
python -m pip install "pip-audit==2.10.1"
pip-audit -r requirements.lock --strict --ignore-vuln PYSEC-2026-1845
npm --prefix frontend ci --no-audit --no-fund
npm --prefix frontend audit --omit=dev --audit-level=high
python -c "import yaml; yaml.safe_load(open('.github/workflows/security.yml'))"

# P12b clean-venv validation
python -m pip install -r requirements.txt
python -m pip check
python -m pip install -r requirements.txt -r tests/advanced/requirements.txt
python tests/run_tests.py
python tests/run_tests.py --integration      # 需要一次性 PostgreSQL
python tests/advanced/run.py fast --out <仓库外目录>
```

原始证据（**仓库外**）：

- `D:\Study\Y4 - CSC4801\_evidence\P12\logs\gitleaks-baseline.log` / `.json`
- `D:\Study\Y4 - CSC4801\_evidence\P12\logs\gitleaks-final.log` / `.json`
- `D:\Study\Y4 - CSC4801\_evidence\P12\logs\pip-audit.log` / `pip-audit.json`
- `D:\Study\Y4 - CSC4801\_evidence\P12\logs\npm-audit.log` / `npm-ci.log`
- `D:\Study\Y4 - CSC4801\_evidence\P12\logs\unit-tests.log`
- `D:\Study\Y4 - CSC4801\_evidence\P12\bin\gitleaks_8.30.1_checksums.txt`
- `D:\Study\Y4 - CSC4801\_evidence\P12b\logs\install-runtime.log`
- `D:\Study\Y4 - CSC4801\_evidence\P12b\logs\pip-check-runtime.log`
- `D:\Study\Y4 - CSC4801\_evidence\P12b\logs\install-runtime-advanced-retry.log`
- `D:\Study\Y4 - CSC4801\_evidence\P12b\logs\pip-audit-after.log` / `pip-audit-after-noignore.json`
- `D:\Study\Y4 - CSC4801\_evidence\P12b\logs\pip-audit-clean-venv.log`
- `D:\Study\Y4 - CSC4801\_evidence\P12b\logs\unit-tests-clean-venv.log`
- `D:\Study\Y4 - CSC4801\_evidence\P12b\logs\integration-clean-venv.log`
- `D:\Study\Y4 - CSC4801\_evidence\P12b\logs\advanced-fast.log`
- `D:\Study\Y4 - CSC4801\_evidence\P12b\advanced-fast\summary.json`

未脱敏的临时分类报告在分类后已删除，未提交、未上传。
