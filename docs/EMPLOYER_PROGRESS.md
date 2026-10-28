# 雇主工作流模块进度记录

依据 `implement_guideline.md`（2026-10-28 版）。本文件只记录实际执行的命令与结果，不代替实现说明。

## 基线

- BASE_COMMIT：`c2667bd7805a6f779c6cf90e32aa3b40bc95bdfc`（`origin/candidate` 分支顶端，提交信息 `feat(database): add booking table and incremental migration`）
- 工作分支：`employer`（`git switch -c employer origin/candidate`）
- 环境：仓库根目录 `app/` 下新建 `.venv`（实际解释器 Python 3.14.4，`pip install -r requirements.txt` 安装 `requirements.lock` 中锁定的依赖；`.venv` 已在 `.gitignore` 中）
- 本地测试使用 `backend/data/` 下的临时 SQLite 文件；该目录已在 `.gitignore` 中，测试前需存在（`New-Item -ItemType Directory backend/data`），否则 `--basetemp` 无法创建子目录。

## 步骤 1：分支与归属检查

实际执行：

```powershell
git fetch origin
git switch -c employer origin/candidate
git rev-parse HEAD
```

结果：`c2667bd7805a6f779c6cf90e32aa3b40bc95bdfc`，工作区干净。

新增文件：

- `scripts/check_employer_ownership.py`（硬编码 BASE_COMMIT，M/D/R 一律报错，新增文件必须在雇主范围内）
- `pytest.employer.ini`
- `backend/app/employer/__init__.py`
- `backend/app/employer/AGENTS.md`

检查：

```powershell
.venv\Scripts\python.exe scripts/check_employer_ownership.py
```

结果：`Ownership check passed: HEAD descends from c2667bd7805a6f779c6cf90e32aa3b40bc95bdfc; all additions stay in the employer scope.`

## 切换前候选人基线

```powershell
.venv\Scripts\python.exe -m pytest -c pytest.candidate.ini backend/candidate_tests/test_owned_database.py -q --basetemp <backend/data 下唯一目录>
```

结果：`21 passed, 1 warning`（Starlette/httpx 弃用警告，与本次改动无关）。

## 步骤 2：模型与独立迁移链

新增：`backend/app/employer/model.py`、`database/__init__.py`、`database/migration.py`、`database/__main__.py`、`database/migrations/env.py`、`database/migrations/script.py.mako`、`database/migrations/versions/employer_001.py`、`backend/employer_tests/conftest.py`、`backend/employer_tests/test_migration.py`。

实现要点：

- `EmployerModel(SQLModel, registry=registry())`，不注册到全局 `SQLModel.metadata`；时间列复用组员的 `UTCDateTime`。
- `job` 的外键为空；`job_skill.job_id` 指向本模块 `job.id`；`employer_company` 为独立成员表。
- 迁移开头检查 `user`、`company`；离线模式跳过。`downgrade()` 明确拒绝自动破坏性降级。
- 独立版本表 `alembic_employer_version`；`make_engine` 直接复用组员实现（打开 SQLite 外键）。

实际执行：

```powershell
.venv\Scripts\python.exe -m pytest -c pytest.employer.ini -q backend/employer_tests/test_migration.py
```

结果：`4 passed`（首次运行发现 SQLModel 不允许 `nullable` 与 `sa_column` 同时传入，改为在 `Column` 内声明后通过）。

CLI 验证（临时 SQLite，先 core 再雇主）：

```powershell
$env:OWNED_DATABASE_URL = 'sqlite:///<临时文件>'
..\.venv\Scripts\python.exe -m app.candidate.database init --phase core
..\.venv\Scripts\python.exe -m app.employer.database init
..\.venv\Scripts\python.exe -m app.employer.database status
..\.venv\Scripts\python.exe -m app.employer.database check
```

结果：`Revision: employer_001`；`Employer tables: employer_company, employer_profile, job, job_skill`；`No new upgrade operations detected.`

## 步骤 3：公司资料 API

新增：`adapters.py`、`schema.py`、`service.py`、`router.py`、`employer_main.py`、`test_company.py`。

实际执行：

```powershell
.venv\Scripts\python.exe -m pytest -c pytest.employer.ini -q backend/employer_tests/test_company.py
```

结果：`6 passed`。

## 步骤 4：职位 CRUD

新增：`test_jobs.py`（补充 `EmployerCompany` 导入）。

实际执行：

```powershell
.venv\Scripts\python.exe -m pytest -c pytest.employer.ini -q backend/employer_tests/test_jobs.py
```

结果：`9 passed`。

## 步骤 5：申请状态与对接函数

新增：`test_application_status.py`、`test_integration.py`。

实际执行：

```powershell
.venv\Scripts\python.exe -m pytest -c pytest.employer.ini -q backend/employer_tests/test_application_status.py backend/employer_tests/test_integration.py
```

结果：首次 `10 passed, 2 failed`（测试直接使用未导出的 `adapters.Booking`；组员 `ApplicationPublic` 不含 `candidate_id`）。修正为 `adapters` 导出 `Booking`、测试改用 `/users/me` 取得候选人 ID 后：

结果：`12 passed`。

## 步骤 6：文档与全量检查

新增：`docs/EMPLOYER_INTEGRATION.md`、`backend/app/employer/REQUIREMENTS.md`（按项目约定摘录本模块需求，便于复核）。

实际执行与结果：

```powershell
.venv\Scripts\python.exe -m pytest -c pytest.employer.ini -q
# 31 passed, 1 warning

.venv\Scripts\python.exe -m pytest -c pytest.candidate.ini backend/candidate_tests/test_owned_database.py -q --basetemp <backend/data 下唯一目录>
# 21 passed, 1 warning

.venv\Scripts\python.exe -m ruff check backend/app/employer backend/app/employer_main.py backend/employer_tests scripts/check_employer_ownership.py
# All checks passed!（首次发现 adapters.py 的 Booking、migration.py 的 make_engine 为 F401；
# 两者都是对外导出，加入 __all__ 后通过）

.venv\Scripts\python.exe scripts/check_employer_ownership.py
# Ownership check passed

.venv\Scripts\python.exe scripts/check_candidate_ownership.py
# 按 implement_guideline §0.1.4 预期报出雇主新增文件 "Addition outside the candidate scope"；未修改其脚本
```

额外验证：设置演示环境变量后 `from app.employer_main import app`，OpenAPI 路径包含全部 `/employer/*`、`/candidate/*`、`/users/*` 路由。

## 提交

Git 未配置 `user.name` / `user.email`；实现完成后由用户在本机配置身份并自行创建本地提交。全部 25 个新增文件已暂存（`git status` 显示为 `A`），push 需另行确认。

## 已知限制

- 本轮不实现前端、面试时段管理与匹配分数。
- 组员种子数据需要补 `company_id`，详见 `docs/EMPLOYER_INTEGRATION.md`。
- 组员 `frontend/candidate` 的 `common_api.ts` 尚不支持 PATCH 与 204 空响应。
