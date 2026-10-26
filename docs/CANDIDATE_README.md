# 候选人独立扩展

2026-10-24 从 GitHub 重新克隆 `LiWenkai19/CSC4801_Team_Pivot`，基线为 `8486388c4bb839149654d820b99b644fdb983e6f`，开发分支为 `candidate/isolated-20261024`。

候选人资料读取与编辑、文本简历、技能匹配、职位列表与详情、申请、状态展示和预约功能复用了此前本地代码。2026-10-26 简历权限更新为候选人仅读本人、已登录雇主仅读申请过自己职位的候选人、候选人仅本人可改，见 `CANDIDATE_RESUME_ACCESS.md`。团队原有 88 个文件保留原内容；新增内容清单见 `CANDIDATE_FILES.json`，来源说明见 `frontend/candidate/PROVENANCE.md`。

## 安装与检查

当前需求变更：CAN-005 已将技能输入替换为标签；CAN-006 将运行评分改为统一 0 分占位、真实算法待开发。旧后端分数断言及浏览器技能行定位需要在开发完成后的统一验收阶段更新。下方完整检查命令是入口说明，不表示旧测试已适配当前需求或本轮全套通过；最新记录见 `CANDIDATE_PROGRESS.md` 和功能权限台账。

在仓库根目录使用 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock -e './backend[dev]'
npm --prefix frontend/candidate ci
.\.venv\Scripts\python.exe scripts/check_candidate.py
```

最后一条命令检查文件归属、依赖一致性、扩展代码 Ruff、候选人隔离测试、前端构建、lint 和 React XSS 测试；遇到失败立即返回非零状态。只收集 `backend/candidate_tests`，不向团队 `backend/tests` 注入夹具。

## 本地预览

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe scripts/preview_candidate.py
```

- 页面：`http://127.0.0.1:5173`；API 文档：`http://127.0.0.1:18019/docs`。
- 候选人：`alice@example.com`、`bob@example.com`；密码均为 `Demo-only-123!`，仅为虚构演示账户。
- 自动创建临时 SQLite、执行完整 Alembic 迁移并填充演示数据。不会读取个人数据库地址；退出后演示数据不保留。
- Ctrl+C 停止本次启动的两项服务；端口占用时直接退出，不关闭或复用其他人的服务。
- `--smoke` 参数只检查启动成功，随后自动停止，适合验收。

## 浏览器回归

```powershell
Set-Location frontend/candidate
npx playwright install chromium
npm run test:e2e
```

测试自动启动临时 SQLite 与 Vite。覆盖资料保存和刷新、匹配、申请、真实第二客户端预约冲突、XSS、换账户隔离、失败后保留输入、两角色补填与退出，以及注销后的迟到响应。无需个人数据库或付费凭据。

## 使用持久化开发数据库

临时预览用于验证，不替代课程要求的持久化数据库。需要持久化时，在 `backend/` 为专用开发库提供 `APP_NAME`、`SECRET_KEY`、`ALGORITHM`、`ACCESS_TOKEN_EXPIRE_MINUTES` 和 `DATABASE_URL` 环境变量，再运行：

```powershell
..\.venv\Scripts\python.exe -m alembic -c alembic.candidate.ini upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.candidate_main:app --host 127.0.0.1 --port 8000
```

前端在 `frontend/candidate/` 通过 `VITE_API_BASE_URL=http://127.0.0.1:8000` 启动 `npm run dev`。不复制旧目录中的个人 `.env`，也不自动修改个人 PostgreSQL。

## 工程边界

后端独立入口是 `backend/app/candidate_main.py`。schema 继承、账户路由包装、候选人业务均在 `backend/app/candidate/`，原 `users`、`core`、`db`、`main.py` 不修改。技能规范化导入团队既有函数，评分在 `backend/app/matching.py`，两端共享。

迁移配置、环境和新增迁移位于 `backend/alembic.candidate.ini` 与 `backend/candidate_alembic/`；既有迁移仅引用，不编辑。前端使用独立入口和依赖清单，账户类型与 CSS 导入原文件，其余派生页面保留原作者归属。

现有 `start.bat`、原应用入口、原 Dockerfile 和文档保持团队版本；它们不会自动启动候选人扩展。队友将来接入主应用时，使用 `CANDIDATE_INTEGRATION.md` 的说明自行处理归属范围内的入口。

本轮执行结果见 `CANDIDATE_PROGRESS.md`。不代表雇主职位 CRUD、状态修改、时段管理或整个项目已完成；真实 PostgreSQL 并发、Docker 和远程 CI 另行验收。
