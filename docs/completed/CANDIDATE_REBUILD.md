# Candidate 重建说明

更新：2026-11-05。基于 `employer-only` 提交 `acae44d73a08090eeecc898500535bbd257feeb9`，本地分支 `candidate-rebuild`。

## 结构与维护入口

- 后端 `app/candidate/schema.py` 定义契约，`service.py` 负责全部查询、授权、响应组装和事务，`router.py` 只处理 HTTP。业务异常为 ValueError 子类，按类型转换 403/404/409。
- 复用 `users.model` 的资料/技能，以及 `employer.model` 的职位/申请/预约/时段。未新增表或迁移；候选人没有独立数据库、认证、启动入口或模型副本。
- 匹配直接调用 `app.employer.matching.match_score`。推荐排序键为 `(-match_score, title.lower(), str(id))`。职位及申请列表批量查询关联记录，测试核对查询数量不会逐项增长。
- 前端 `api/candidate_api.ts` 复用统一请求，页面位于 `pages/candidate/`；技能选择器和投递按钮仅因实际复用需要独立。没有新增运行时依赖或通用数据加载框架。
- 页面继承 employer 的排版、原生控件与共享颜色。新增样式限定在 candidate/技能组件作用域；未修改共享全局样式。

## API

| 方法 | 路径 | 行为 |
| --- | --- | --- |
| POST | `/users/candidate/profile` | 沿用首次创建资料接口 |
| GET/PATCH | `/candidate/profile` | 本人读取/局部更新资料 |
| GET | `/candidate/profiles/{candidate_id}` | 本人或有投递关系的雇主读取 |
| GET | `/candidate/jobs` | 有效职位、实时分数、本人 applied 标记 |
| GET | `/candidate/jobs/{job_id}` | 有效职位详情 |
| POST | `/candidate/jobs/{job_id}/applications` | 创建 Pending 申请，重复 409 |
| GET | `/candidate/applications` | 本人申请，创建时间降序、ID 升序 |
| GET | `/candidate/applications/{application_id}` | 本人申请详情 |
| GET | `/candidate/applications/{application_id}/slots` | 本人面试申请可预约时段 |
| POST | `/candidate/applications/{application_id}/booking` | `{ "slot_id": "UUID" }`，创建预约 |

新投递请求体可省略或为 `{}`，不允许伪造状态/归属。PATCH 资料只接受 display_name、resume_text、skills；省略保留，空文本/数组清空，显式 null 拒绝；名称不能空白。新请求校验不会更改共享首次创建接口的原有校验行为。

职位响应在 employer 的 JobPublic 字段上增加 match_score、applied。申请响应包含 application_id、job_id、job_title、company_name、status、created_at、booking；booking 字段与雇主响应一致。时间值在 candidate 响应中统一为 UTC，雇主原有时间格式不变。

所有 candidate 业务接口依赖真实认证。角色错误/对象越权为 403，缺失资源为 404，状态冲突为 409，参数错误为 422，未认证为 401。雇主读取简历必须存在该候选人向自己职位投递的关系，不因申请状态变化撤销；历史职位关系仍可用。该权限是用户确认的原需求覆盖，详见模块 REQUIREMENTS。

## 事务与共享行为

投递锁住职位，再查重写入，与现有雇主软删除逻辑协调；既有 candidate/job 唯一约束兜底。预约先锁申请，再锁时段，重新校验资格并提交；slot_id、application_id 的两个唯一约束兜底。业务冲突及数据库异常均回滚；只有可确认的重复写入会转换成 409，未知数据库异常继续抛出。

不复制状态或预约；雇主改状态后候选人刷新直接看到同一条 Application，双方从同一 Booking 读取预约。时段按对应雇主匹配，与已确认旧功能一致。

## 验证命令

在项目独立 Python 环境安装 `requirements.txt`，前端执行 `npm ci`。以下 PowerShell 命令在 backend 目录运行，连接地址须指向允许创建测试库的 PostgreSQL 实例：

```powershell
$env:CANDIDATE_TEST_DATABASE_URL = 'postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/postgres'
..\.venv\Scripts\python.exe -m pytest tests/candidate -q
```

candidate 测试创建 `csc4801_candidate_test_<随机值>` 数据库，经现有 Alembic 主链迁移，结束后删除；仅截断该随机测试库。不会重置 URL 指定的来源库。禁止将该测试 URL 提交到源码。

现有 employer 测试另从 `backend/.env` 读取连接，并使用固定 `symanage_test` 库；测试前会清空该库，因此应使用隔离 PostgreSQL 实例。准备该 .env 后，当前可运行的后端联合回归命令为：

```powershell
..\.venv\Scripts\python.exe -m pytest tests --ignore=tests/users/test_schema.py -q
```

该排除是显式的既有阻塞说明，不代表完整仓库测试全部通过。原 `tests/users/test_schema.py` 导入 users.schema 中被注释的 CandidateProfileUpdate，仍不能收集；本次没有修改该文件或共享账号逻辑。

在 frontend 执行 `npm run build`、`npm run lint`。真实浏览器回归从仓库根目录运行：

```powershell
# Playwright 可安装在独立工具目录，无需改本项目依赖。
$env:PLAYWRIGHT_MODULE = 'ABSOLUTE_PATH_TO_PLAYWRIGHT/index.mjs'
$env:UI_BROWSER_CHANNEL = 'msedge' # 或留空使用 Playwright Chromium
node frontend/tests/candidate.browser.mjs
```

浏览器脚本使用上述 CANDIDATE_TEST_DATABASE_URL，创建随机 `csc4801_candidate_ui_*` 库、执行迁移、准备虚构数据、启动临时后端和生产前端预览；finally 清理服务与测试库。截图/日志/results.json 保存到输出中显示的系统临时目录。UI_PYTHON 可指定项目 Python 解释器。

## 本轮验证结果

- PostgreSQL 16.4 临时实例，仅监听本机；candidate 38 项、现有 employer 28 项、账号 50 项，联合回归 **116 passed**。
- 真实 PostgreSQL 并发验证：两人争抢同一时段、同一申请争抢两个时段、重复投递均恰好一个成功；数据库记录数量符合约束。资料提交失败测试验证文本与技能整体回滚。
- 前端 TypeScript/生产构建、Ruff、pip 依赖检查通过。前端 lint 无错误，仅共享 AuthContext 既有两条 Fast Refresh 警告。测试依赖有既有 Starlette/httpx 弃用提示。
- 浏览器 7 组流程通过，使用真实 API 与 PostgreSQL：注册/首次资料、标签建议与自定义、持久化、重试、投递、状态同步、预约竞争恢复和成功预约、文本/XSS；1280/390px 检查及截图复核。最终浏览器结果以本轮输出的 results.json 为准。
- 本轮使用本机 55439 端口的临时 PostgreSQL。随机 candidate 测试/UI 数据库已核对全部删除，临时实例已关闭。当前被忽略的 backend/.env 仅为该临时实例的测试配置；运行开发服务前应换成自己的开发数据库配置。
- 原 `frontend/tests/employer.browser.mjs` 含“candidate 入口仍应占位”的旧断言，本次未修改或声称完整通过该脚本。employer 后端原测试完整通过，浏览器另核对现有雇主页面与角色边界。

## 保留边界

- users、employer 业务源码、共享认证 Context、迁移与队友测试保持不变；共享入口仅添加 candidate 注册/导航/类型。CandidateForm 的技能交互替换已获用户明确授权。
- 当前 employer 分支只有时段模型，尚无雇主时段管理接口。本次实现候选人预约，不补做该团队模块；预约测试自行准备时段。
- 团队 seed_demo 的既有 slot 是 60 分钟，候选人会按规则过滤；没有擅改队友种子。浏览器夹具另加未来 30 分钟时段。团队讨论后可另行修正演示种子。
- 雇主读取简历仅提供权限接口，不接入雇主页面。旧 candidate 目录和数据库保留原样，无兼容层或数据迁移。
- 未自动提交、推送或合并；无生产数据库迁移或部署验证。

## 2026-11-06：上传前审查记录

用户要求先将当前实现上传到 GitHub 的 `candidate-rebuild` 分支；本次上传不包含以下问题的修复，也不合并到其他分支。上文验证结果记录的是当时的测试覆盖，不能排除本次定向审查发现的问题。

- 新增 candidate 代码：技能整体替换没有锁住候选人资料行。真实 PostgreSQL 并发请求分别提交 `["python"]` 与 `["sql"]`，最终可能得到两者并集。需要在 candidate service 内串行化保存并补充回归测试。
- 继承的共享配置：`app/db/session.py` 的 `echo=True` 会在 SQL 参数日志中写出简历原文，已用虚构文本验证。涉及队友文件，待团队确认后调整日志配置。
- 继承的模型/迁移差异：Application 模型声明状态的数据库默认值 Pending，但现有迁移未建立默认值。带 server-default 比较的元数据核对确认该差异；直接 SQL 省略状态会触发非空约束错误，当前 ORM 投递仍能正常写入 Pending。待团队确认后以新增迁移处理。

审查使用随机临时 PostgreSQL 数据库，已删除并关闭实例；未修改真实业务库或上述业务代码。队友业务、模型、迁移与认证文件相对 employer-only 保持不变；共享入口、导航、类型及获授权的 CandidateForm 技能交互改动保留。

## 2026-11-06：查询精简优化

- 推荐查询合并本人资料存在性与技能读取，只选择资料 ID 和技能名称，不加载简历；职位查询同时关联公司名称，并以 EXISTS 判断本人是否投递。职位技能继续单独批量读取，避免多技能导致职位行重复。
- `_recommended_jobs` 现在负责查询并组装有效职位，可选 job_id 用于详情；list_jobs 保留原排序。未建资料即使没有职位仍返回 404；单职位不存在时仍优先返回 Job not found。已有资料但没有技能仍可正常推荐。
- 申请摘要合并职位标题和公司名称查询，不读取完整职位描述；预约只读取响应需要的字段。保留历史申请及原有顺序，不新增删除状态过滤。
- 删除资料更新后对当前响应无作用的 skills 关系缓存失效操作；30 分钟时段条件移至 PostgreSQL 查询。预约提交时仍重新检查时长与资格。
- 在随机 PostgreSQL 库对比原提交与优化实现：职位列表/详情 SELECT 从 6 次降到 3 次，申请列表/详情从 4 次降到 3 次，均不含认证查询；六类操作的响应相同，包括资料保存和可用时段读取。混合 29/30/31/60 分钟时段只返回 30 分钟时段。这些结果证明查询次数减少，不代表已经完成大规模延迟基准测试。
- 新增资料缺失及错误优先级回归，现有查询计数测试验证包含认证后推荐和申请列表均为 4 次 SELECT。candidate 39 项、employer 28 项、账号 50 项，联合回归 **117 passed**；仍显式排除上述既有 schema 收集错误。Ruff 通过。
- 仅精简 candidate 自有业务代码；未修改共享评分函数、模型、迁移、接口契约或前端。本次提交包含查询优化、对应测试和说明；前述技能并发替换、NUL 文本校验、共享 SQL 日志与迁移默认值问题仍待修复。
