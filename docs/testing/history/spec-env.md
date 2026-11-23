> 历史报告副本：保留原日期、SHA和当时状态；路径按本次仓库结构重写。历史日志/数据库/截图未发布，当前运行方式见测试README。不能把旧结果当作新提交执行。

# 规格与环境阶段检测报告

日期：2026-11-22（Asia/Shanghai）
版本：`f12f819df6bddef8a1e914e95b515933cc722a96`；分支：`test-prep-20261121`。

本轮记录 6 项已确认问题，其中 5 项涉及交付、文档或演示数据，1 项为模型与迁移差异；另有 2 项环境阻塞和 2 项待确认规格问题。所有问题均未修复。这里只完成规格与环境阶段，不代表后续功能、权限、并发和浏览器测试已完成。

用户要求：所有测试先找 bug，不修复；所有阶段完成并生成总检测报告之后，再统一处理修复。后续修复仍需遵守队友代码归属约束。

## 已通过的检查

- 原仓库工作区干净；原始跟踪文件与固定提交内容一致，比较时已区分工作区 CRLF 与归档 LF。
- 现有环境中 70 项适用的锁定依赖版本全部一致，pip check 通过。
- 全新 Python 3.12.4 虚拟环境按 requirements.txt 安装成功，pip check 通过；无需付费模型凭证即可启动后端。
- 干净前端副本 npm ci 成功（31 个包）；TypeScript 编译与 Vite 生产构建通过。lint 无错误，有两条 Fast Refresh 警告。
- PostgreSQL 16.4 上两个空库均升级到 5a1d3c7e9b20；前一迁移版本升级、重复 upgrade head 均成功。
- 两次重置 seed 命令均返回 0，排除随机密码哈希和创建/更新时间后业务快照完全一致。
- seed 有 3 名候选人、2 名雇主、3 个职位、5 份申请，包含四种状态及评分要求的四例；预约可用性单独失败。
- 全新依赖环境的真实 Uvicorn 启动成功；OpenAPI 返回 200，含 22 条路径；候选人和雇主登录及代表性读取均返回 200。
- 在导出副本临时提供 backend/.env 后，完整后端测试收集为 145 项，无收集错误。本轮未执行这些业务测试。

## 问题清单

优先级用于安排后续统一修复，不是课程缺陷计分结论。相同根因只列一次。

| 编号 | 优先级 | 问题 | 证据状态 |
|---|---|---|---|
| SE-01 | P1 | Dockerfile 仍是退出型模板，未提供可运行交付环境 | 已确认（静态＋默认命令等价执行；容器构建受阻） |
| SE-02 | P1 | INSTALL.md 缺少干净环境运行所需步骤 | 已确认 |
| SE-03 | P2 | README 需求映射和验证说明未完成、未更新 | 已确认 |
| SE-04 | P2 | SPEC 仍缺少多项必需设计说明 | 已确认（静态文档缺口） |
| SE-05 | P1 | 默认 seed 的 60 分钟时段无法支持双候选人预约演示 | 已复现 |
| SE-06 | P3 | application.status 的数据库默认值未随模型迁移 | 已确认（模式差异；不等同于 ORM 投递失败） |

## SE-01：Dockerfile 仍是退出型模板，未提供可运行交付环境

定位：`Dockerfile:20`。

判据：Dockerfile 构建并启动完整应用环境。

实际结果：默认 CMD 直接抛出 SystemExit，退出码 1；文件未构建前端、配置数据库或启动服务器。

影响与限制：按当前默认命令无法启动评分所需应用。Docker 引擎未运行是另一项环境阻塞，不能用它证明镜像构建失败。

证据：logs/docker-placeholder-command.txt（历史本地产物：`docker-placeholder-command.txt`，未随仓库发布）、docker-build-isolated-config.json（历史本地产物：`docker-build-isolated-config.json`，未随仓库发布）。

## SE-02：INSTALL.md 缺少干净环境运行所需步骤

定位：`INSTALL.md:27`。

判据：准确说明 Node/PostgreSQL 等前提、配置、迁移、seed、启动、完整测试和 Docker 命令。

实际结果：8 个安装/运行章节无正文；干净导出在未提供 APP_NAME、DATABASE_URL 时无法导入应用，按环境变量提供配置后雇主测试仍要求 backend/.env。

影响与限制：本轮能运行依赖额外从源码和模块文档推导的步骤，不能据此宣称 INSTALL.md 的干净安装流程通过。

证据：spec-audit.json（历史本地产物：`spec-audit.json`，未随仓库发布）、logs/clean-config-import.txt（历史本地产物：`clean-config-import.txt`，未随仓库发布）、logs/clean-backend-collection.txt（历史本地产物：`clean-backend-collection.txt`，未随仓库发布）。

## SE-03：README 需求映射和验证说明未完成、未更新

定位：`README.md:15`；`README.md:53`。

判据：25 个需求 ID 均有适当实现/具名测试或验证证据，命令与同一提交一致。

实际结果：展开 FP-SEC-1/2/3 等缩写后，仍有 12 个 ID 未列入映射；AUTH-1 仍引用占位测试。根目录 17 个 pass 测试虽显示通过，但未验证行为。文档仍声称 schema 导入阻塞；配置后本轮已成功收集 145 项。

影响与限制：无法通过现有 README 独立复查需求覆盖；不能把模板通过数和旧版 117 passed 当作本提交验证结果。并不据此断言实际业务测试全部缺失。

证据：spec-audit.json（历史本地产物：`spec-audit.json`，未随仓库发布）、logs/root-template-tests.txt（历史本地产物：`root-template-tests.txt`，未随仓库发布）、logs/configured-backend-collection.txt（历史本地产物：`configured-backend-collection.txt`，未随仓库发布）。

## SE-04：SPEC 仍缺少多项必需设计说明

定位：`SPEC.md:5`；`SPEC.md:9`；`SPEC.md:80`。

判据：SPEC 对同一提交说明架构、数据关系、认证授权、API、页面、评分、事务和安全控制。

实际结果：10 个二级章节为空；后附 Candidate Integration 和时段章节提供部分信息，但未完整说明当前会话认证、主要页面及安全控制。旧 Candidate Integration 中的范围描述按其日期理解，不作为当前功能缺失的证据。

影响与限制：后续测试不能仅凭该文档获得完整且一致的判据。空标题本身不是发现，缺少其要求承载的内容才构成问题。

证据：spec-audit.json（历史本地产物：`spec-audit.json`，未随仓库发布）、openapi.json（历史本地产物：`openapi.json`，未随仓库发布）。

## SE-05：默认 seed 的 60 分钟时段无法支持双候选人预约演示

定位：`backend/scripts/seed_demo.py:207`；`backend/scripts/seed_demo.py:208`。

判据：重置 seed 后，两名 Interviewing 候选人可竞争同一未来、空闲的 30 分钟时段。

实际结果：两名 Interviewing 候选人存在，但唯一时段为 2026-12-01 10:00–11:00 UTC，时长 60 分钟；测试时尚未过期。独立 SQL 判定合格配对数为 0，雇主 GET /employer/interview-slots 返回 200 []。

影响与限制：按默认演示数据无法进行规格要求的预约竞争演示。两个 seed 命令本身均成功，该问题是数据语义错误。

证据：logs/seed-first.txt（历史本地产物：`seed-first.txt`，未随仓库发布）、logs/seed-second.txt（历史本地产物：`seed-second.txt`，未随仓库发布）、seed-comparison.json（历史本地产物：`seed-comparison.json`，未随仓库发布）、api-startup-smoke.json（历史本地产物：`api-startup-smoke.json`，未随仓库发布）。

## SE-06：application.status 的数据库默认值未随模型迁移

定位：`backend/app/employer/model.py:90`；`backend/alembic/versions/c8f4a2b91d37_create_employer_workflow_tables.py:65`。

判据：通过主迁移链创建的数据库与模型声明一致。

实际结果：模型声明 server_default=Pending，实际 PostgreSQL 列默认值为 NULL；开启 compare_server_default 后出现 modify_default 差异。普通 alembic check 返回成功，因为默认值比较未开启。

影响与限制：存在部署模式漂移。本轮没有验证直接 SQL 省略状态的业务入口，不将其算作已复现的 API 功能缺陷，也不单独归因为课程 MUST 违例。

证据：logs/alembic-check.txt（历史本地产物：`alembic-check.txt`，未随仓库发布）、logs/metadata-with-server-defaults.txt（历史本地产物：`metadata-with-server-defaults.txt`，未随仓库发布）、schema-inventory.json（历史本地产物：`schema-inventory.json`，未随仓库发布）。

## 环境阻塞与规格问题

- **BLOCK-01 Docker 构建/容器启动**：Docker Desktop Linux 引擎管道不存在；使用隔离 Docker 配置重试后同样失败。未启动或修复 Docker。 证据：docker-build-isolated-config.json（历史本地产物：`docker-build-isolated-config.json`，未随仓库发布）。
- **BLOCK-02 原始 start.bat 全链路启动**：5173 已有本机监听进程；本轮未停止或请求该服务。启动脚本实际未进入启动流程。8000 无监听。 证据：port-status.json（历史本地产物：`port-status.json`，未随仓库发布）。
- **SPEC-Q01 简历读取权限冲突**：课程 FP-CAN-1 要求雇主也不得读取简历；SPEC 和 candidate 模块保留已确认的投递后雇主读取策略。列为策略与课程要求冲突，本轮不运行授权边界测试、不修改权限、不计入 6 项已确认问题。
- **SPEC-Q02 课程材料版本差异**：本地课程包与仓库英文 REQUIREMENTS 唯一内容差异是 FP-SUB-1 的 required CI checks pass。两份均有 25 个 ID；正式评分采用哪版尚未在线核定，不把未发现 CI workflow 单独判为课程违例。

## 测试执行方式与复现

所有写入位于本报告目录：从固定 SHA 用 git archive 导出源码，新建依赖环境和只监听 127.0.0.1 的 PostgreSQL 实例。原仓库、原数据库、现有 5173 服务均未修改。导出副本的 backend/.env 只用于配置测试；不属于对原项目的修复。

真实运行环境：Windows、Python 3.12.4、PostgreSQL 16.4、Node 24.16.0、npm 11.13.0；Docker 客户端 29.2.1，服务端不可用。Python 3.12.13 是仓库作者声明的历史验证版本，本轮没有验证该具体补丁版本或 Linux 容器。

关键命令（完整 cwd、参数、退出码和输出见各 JSON 与 logs）：

```text
git archive --format=zip --output=<artifact.zip> f12f819df6bddef8a1e914e95b515933cc722a96
<fresh-python> -m pip install -r clean-source/requirements.txt
<fresh-python> -m pip check
npm ci --no-audit --no-fund
npm run build
npm run lint
<fresh-python> -m alembic upgrade head
<fresh-python> -m alembic upgrade c8f4a2b91d37
<fresh-python> -m alembic check
<fresh-python> scripts/seed_demo.py    # 仅指向本轮隔离库；执行两次
<fresh-python> -m uvicorn app.main:app --host 127.0.0.1 --port <temporary-port>
<fresh-python> -m pytest tests --collect-only -q -p no:cacheprovider
docker --config <temporary-config> --host npipe:////./pipe/dockerDesktopLinuxEngine build -t csc4801-specenv:f12f819 .
```

数据库默认值比较使用 `MigrationContext.configure(connection, opts={'compare_server_default': True})` 与 `compare_metadata`；见 原始输出（历史本地产物：`metadata-with-server-defaults.txt`，未随仓库发布）。seed 资格通过独立 SQL 检查时长、未来时间、雇主关系、Interviewing 状态及无预约条件；不是以当前过滤函数充当判据。

本轮曾遇到沙箱临时目录权限和 Windows 子进程输出句柄问题，调整了本次测试脚本的临时目录与日志方式后继续；它们不计入项目问题。早期失败的测试脚本运行已终止，数据库实例和 API 服务已关闭。

## 与课件方法的对应

| 方法 | 课件位置 | 本轮产物 |
|---|---|---|
| 规格拆解、遗漏与冲突检查 | L06 p.7–18、22–37；L07 p.25–37 | spec-audit.json、需求与证据映射.md、SPEC-Q01/Q02 |
| 固定版本、隔离与可复现协作 | L10 p.8–20、29–52 | manifest.json、干净源码导出、独立依赖/数据库、integrity-check.json |
| 独立判据与完整状态观察 | L12 p.8–21；L14 p.4–13 | seed 独立 SQL、业务快照、实际接口输出；识别 pass 占位测试 |
| 关系判据的项目迁移：重置前后语义一致 | L12 p.22–28 | 两次 seed 的规范化快照与哈希比较 |

环境命令本身归为可复现性检查；未声称本轮已做 fuzzing、mutation testing、内部变体或形式证明。

## 后续阶段与证据索引

下一阶段先运行 145 项现有后端业务测试并审查有效断言，再依计划测试时段边界、预约状态/并发、匹配与 CRUD、认证安全及浏览器流程。测试期间继续只记录问题；不提前修复、不弱化断言、不用排除失败替代完整结果。

- 需求与证据映射（历史本地产物：`需求与证据映射.md`，未随仓库发布）
- 结构化问题清单（历史本地产物：`findings.json`，未随仓库发布）
- 环境阻塞与规格问题（历史本地产物：`blockers-and-spec-questions.json`，未随仓库发布）
- 版本及源码哈希（历史本地产物：`manifest.json`，未随仓库发布）
- 原仓库完整性检查（历史本地产物：`integrity-check.json`，未随仓库发布）
- seed 快照比较（历史本地产物：`seed-comparison.json`，未随仓库发布）
- seed 独立评分示例（历史本地产物：`seed-independent-examples.json`，未随仓库发布）
- 迁移后数据库模式（历史本地产物：`schema-inventory.json`，未随仓库发布）
- 实际 API 启动检查（历史本地产物：`api-startup-smoke.json`，未随仓库发布）
- 启动入口检查（历史本地产物：`launcher-smoke.json`，未随仓库发布）

本目录保留已关闭的临时 PostgreSQL 数据目录，以便追溯；其中只有本轮合成演示数据。日志中的演示凭据来自仓库公开标记的本地账号，不含现有业务库连接凭据。
