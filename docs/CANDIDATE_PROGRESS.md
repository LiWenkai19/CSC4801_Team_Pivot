# 候选人独立扩展进度

## 2026-10-26：职位推荐与占位评分（CAN-006）

- 用户要求保存简历后获得按匹配分数降序的职位列表，算法暂占位、后续开发。原列表和排序已存在，本轮新增 `recommendation_scoring.py` 并将运行服务切换至统一 0 分；旧技能交集算法保留但不再由业务服务调用。
- 双方评分使用同一占位入口，职位列表/详情及雇主申请行返回 score_kind=placeholder。前端列表/详情显示“0 分（占位）”，明确算法待开发；同分按标题及 ID 稳定排序。
- 候选人首次资料保存并确认完成后进入推荐页，已有资料编辑页新增查看推荐入口。权限、有效职位过滤、已申请标记及拒绝重复申请沿用现有规则；没有增加非空简历门槛、文件上传或评分存储表。
- 台账已登记 CAN-006，并更新需求摘录、接入说明及 README 的旧测试适配提醒。正式算法输入、空技能规则及分数含义后续再确认。
- 实际完成前端 TypeScript/生产构建、lint、候选人后端 Ruff 和归属检查；88 个团队原文件不变。使用虚构接口响应做了 1440/768/390px 界面预览，看到两条“0 分（占位）”；该预览未连接数据库，不代表后端排序或权限运行验收。
- 按用户安排未新增或执行正式测试样例。现有真实分数及部分旧浏览器断言待最终统一适配，不能声称此前 155 项测试仍全部通过本轮变更。

## 2026-10-26：搜索与自定义技能标签（CAN-005）

- 当前旧表单只有动态文本行。本轮新建可复用 SkillTagPicker、CSS 及共享预置目录，接入候选人首次资料与编辑表单；支持下拉搜索、选择、删除、自定义、去重、键盘/输入法及原生表单未完成输入校验。
- 沿用既有技能字符串数组和后端规范化，不改匹配算法、模型或迁移；本地推荐不查询数据库。自定义随当前资料/职位保存，不自动发布为公共目录项。
- 新增无数据库预览页 `/previews/skill-tags.html`，演示候选人表单及雇主复用组件；雇主正式职位页和保存服务由对应所有者接入。详情及片段见 `CANDIDATE_SKILL_TAGS.md`，台账已登记 CAN-005。
- 实际检查：前端 TypeScript/生产构建、lint 通过；浏览器组件预览完成 1440/768/390px 截图，显示 j 推荐 Java、JavaScript，选择和自定义后的预览提交值为 python、java、个人自定义技能。仅使用预览页，无数据库访问。
- Playwright 默认浏览器在沙箱中不可用，Edge 沙箱启动失败；获执行授权后在同一沙箱外进程启动临时 Vite 与无头 Edge 完成预览，结束后关闭本次进程。没有安装浏览器、使用个人浏览器资料或连接业务数据库。
- 未新增或运行正式测试样例，旧 E2E 技能行定位待统一验收时更新。组件预览不代表后端持久化、雇主角色权限或完整 E2E 已验收。

## 2026-10-26：业务查询权限审阅（CAN-004）

- 用户确认范围为所有业务查询接口，要求服务端判断当前角色是否有权请求。
- 清点独立应用已挂载的 8 个业务 GET 接口，逐项审阅身份依赖、角色限制、本人/职位归属、投递关系及列表范围；现有入口均有相应校验，未发现需要补建的查询权限路径。
- 登录身份来自有效令牌对应的数据库账号；客户端传入角色不能替代授权。查询身份及权限关系所需的内部读取与受保护业务结果返回已在台账中区分。
- 已登记 CAN-004 完整接口权限矩阵、认证入口例外、应用层授权边界和后续新增接口要求。没有将维护脚本、直接数据库连接或未来队友接口视为已受统一权限保护。
- 本轮仅补充独立台账及进度，未修改业务代码或队友文件；未新增或运行测试样例，最终权限验收待开发完成后统一执行。

## 2026-10-26：双方查看申请状态与面试邀约（CAN-003）

- 用户确认沿用现有流程：Interviewing 表示邀约，候选人选择时段后双方查看预约结果，无需独立邀约记录。
- 代码检查确认候选人列表/详情及雇主职位申请列表已有 status、booking 读取，复用同一组装函数；候选人限定本人，雇主限定自己职位，跨角色及跨账户/职位访问被拒绝。
- 候选人页面已有四种状态及已预约时间展示，雇主读取接口可用，雇主界面仍待对应所有者接入。无预约的 Interviewing 表示待选时段，状态变化后已保存预约仍保留。
- 功能、权限、数据含义、刷新方式及后续验收范围已登记在 `CANDIDATE_FEATURE_PERMISSION_LEDGER.md` 的 CAN-003，并补充团队接入说明。
- 本轮仅补充独立文档，未修改业务代码、数据库或队友文件；按用户安排未新增或执行测试。没有将独立接口可用视为双方完整界面或团队集成验收完成。

## 2026-10-26：重复申请检查与中文反馈（CAN-002）

- 检查确认已有 `apply` 按候选人 ID、职位 ID 查重，重复返回 409/Already applied；模型和迁移含联合唯一约束，数据库冲突回滚后转换为相同业务反馈，无需修改后端或迁移。
- 已有共用按钮在提交中及已申请时禁用，列表与详情从服务端获取 applied 标记。发现冲突消息为英文，且刷新会卸载临时提示；新增独立 `ApplicationFeedback.tsx` 并在本人的 ApplyButton 中复用，已申请及重复请求均显示“你已申请该职位，请勿重复申请。”。
- 已在 `CANDIDATE_FEATURE_PERMISSION_LEDGER.md` 新增 CAN-002，记录状态变化后仍禁止重复、不同候选人/职位隔离、软删除返回 404、物理移除申请记录的边界及后续验收范围。
- 本轮仅执行前端 build、lint 和文件归属检查，全部通过；88 个团队原文件不变。按用户安排未新增或运行测试样例，浏览器流程及真实 PostgreSQL 并发待开发完成后统一验收。
- impeccable 上下文启动器因引擎缺失且缓存目录不可写未运行，未安装工具或改动工作区外文件；直接沿用当前页面和样式完成提示调整。

## 2026-10-26：收紧雇主简历读取范围（当前规则）

- 用户进一步明确：雇主只能读取申请过自己职位的候选人简历；本节替代下方同日早先的“所有雇主可读”规则。
- `resume_access.py` 在读取资料时连接 Application 与 Job，检查 candidate_id 和职位 employer_id；无对应投递关系返回 403。候选人仅读本人、修改仅本人、匿名 401 均保持适用。
- 所有申请状态均构成投递关系，职位软删除后保留历史读取；移除对应投递记录后不再授权，职位所属雇主以当前记录为准。上述边界记录于 `CANDIDATE_RESUME_ACCESS.md`。
- 修订既有测试并补充无投递、跨雇主、申请状态、投递移除和职位归属检查，修正候选人提示、需求摘录与接入说明。
- 实测后端 155 passed、1 skipped（真实 PostgreSQL）；Ruff、前端 build/lint 通过。88 个团队原文件指纹不变，git diff 无团队文件修改。没有新增迁移、连接业务数据库、提交或推送。

## 2026-10-26：简历读取与修改权限

- 现状检查：原实现支持候选人本人读改，但拒绝雇主读取；用户确认新规则为候选人仅读本人、所有已登录雇主可读所有候选人、仅候选人本人可改。
- 新建 `backend/app/candidate/resume_access.py`，现有资料 GET 接入读取策略；PATCH 保留候选人角色与本人 ID 双重校验。返回资料字段白名单，不返回账户机密；没有新增数据库表或迁移。
- 新建 `backend/candidate_tests/test_resume_access.py`（24 项），覆盖雇主无投递关系读取、本人保存及清空、跨账户修改拒绝且数据不变、失效认证、目标缺失或角色不符、非法 UUID、伪造归属与非法类型。更新原权限测试以匹配新需求。
- 修正候选人资料页旧隐私提示，更新独立需求摘录与接入说明。雇主页面由对应所有者使用现有 GET 接口接入；未新增雇主页面，未修改团队入口。
- 实际验证：候选人后端 148 passed、1 skipped（真实 PostgreSQL）；Ruff、前端 build、lint、纯文本 XSS 测试（1 passed）通过。沙箱内接口测试挂起后停止，取得执行授权后在沙箱外运行同一隔离 SQLite 套件，35.44 秒完成。
- 归属校验：88 个团队原文件不变，`git diff --exit-code` 返回 0，变更仅在独立候选人文件内。没有切换六表开发库，没有连接业务数据库、提交或推送。
- 权限矩阵、接口、空值及并发保存边界见 `CANDIDATE_RESUME_ACCESS.md`。当前简历为纯文本，PDF/Word 文件上传不在本项实现范围。

## 2026-10-26：按用户分工建立六张数据库表

- 用户负责 User、CandidateProfile、CandidateSkill、Company、Application、InterviewSlot；明确排除 EmployerProfile、Job、JobSkill、Booking。
- 新增 `backend/app/candidate/database/`：六表 SQLModel 独立映射、两阶段 Alembic 迁移、显式连接的 CLI。沿用原表名，新增独立 Company、所需时间字段、约束和更新时间触发器，不建匹配分数表。
- 在 `backend/data/owned_schema.sqlite3` 实际创建六张空业务表，版本 owned_flow_002；连接重开后的结构、外键开关、数据库完整性和模型差异检查通过。文件没有队友表或测试业务数据，未切换运行服务的数据库。
- 新增数据库测试 21 passed；独立候选人全套 124 passed、1 skipped，跳过项需要真实 PostgreSQL。Ruff 和归属检查通过，88 个团队原文件不变；没有修改既有共享模型、原迁移、配置或入口。
- 首次回归在 Windows sandbox 的 asyncio.socketpair 初始化挂起；取得执行授权后在沙箱外运行同一隔离 SQLite 测试套件，10.93 秒完成。未修改业务代码来绕过环境限制。
- PostgreSQL 离线 DDL 已生成并验证只创建用户表；Docker 引擎仍无法连接，没有实际 PostgreSQL 迁移/并发验证。未连接个人或共享业务数据库，没有提交或推送。
- `application`、`interview_slot` 的外键依赖队友提供的 `employer_profile`、`job`；SQLite 当前仅完成结构，相关流程待依赖接入。公司关联 company_id 也由队友在雇主与职位模型中接入。
- 完整字段、命令、需求摘录、新库/旧库迁移边界、接入步骤与限制见 `CANDIDATE_DATABASE.md`；离线 SQL 为 `CANDIDATE_DATABASE_POSTGRESQL.sql`，证据清单为 `CANDIDATE_DATABASE_VALIDATION.json`。全仓库既有 schema 测试导入问题不属于本次修改范围，未声称全仓库测试通过。

## 2026-10-24：按用户要求清理旧版本

- 删除旧开发副本 CSC4801_Team_Pivot、CSC4801_Team_Pivot_latest_20261019 内的旧代码与依赖，以及 .codex_inspect 下对应的注释副本、集成快照、审阅备份和迁移脚本；审阅副本中的两个依赖目录链接已先单独移除。
- 最新开发目录保留 CSC4801_Team_Pivot_clean_20261024。课程资料、作业、REA 和其他无关文件保持原样。
- CSC4801_Team_Pivot 的内容已全部删除，但其空目录仍被外部进程占用，Windows 拒绝移除目录本身；未终止归属不明的进程。CSC4801_Team_Pivot_latest_20261019 已完整删除。
- 最新目录使用自己的 Python 环境和前端依赖，不依赖旧目录。清理后归属检查确认 88 个原文件不变，pip check、Ruff、前端构建、lint 与 XSS 检查通过，候选人后端 103 passed、1 skipped（真实 PostgreSQL 测试）。

## 2026-10-24：用户要求再次验证

- 独立复核 Git 提交对象：基线文件列表与指纹清单完整对应，88 个原文件与提交 8486388 一致，git diff 无原文件改动。
- 重新执行候选人检查：103 passed、1 skipped；原账号测试 50 passed；前端 build、lint、React XSS 测试及 Ruff、pip check 全部通过。
- Chromium 六项真实 API 流程全部通过；预览 smoke 重新启动并停止两项服务成功。
- 在独立临时 SQLite 文件上执行完整迁移、alembic check、种子数据写入和关闭引擎后重新连接：10 张表齐全，版本 candidate_flow_001，模型无待迁移差异，5 个演示账户保留。该检查验证重新连接后的文件持久化，不代表 PostgreSQL 或进程重启验收。
- 发现全仓库测试收集的既有阻塞：`python -m pytest --collect-only -q` 返回 1；backend/tests/users/test_schema.py 仍导入 CandidateProfileUpdate / EmployerProfileUpdate，而 app/users/schema.py 已注释这两个类。这两个文件与 GitHub 基线相同，未修改。独立扩展测试通过不代表全仓库套件通过；由对应文件所有者协调修复。
- Docker 客户端 29.2.1 可用，但 dockerDesktopLinuxEngine 管道不存在，当前引擎无法连接；真实 PostgreSQL 并发、Docker 镜像和远程 CI 仍未验证。
- 本次未修改业务实现或队友文件，仅补充独立验证记录。

## 2026-10-24：重新克隆并迁入独立实现

- GitHub 基线：`8486388c4bb839149654d820b99b644fdb983e6f`，分支 `candidate/isolated-20261024`。从远程重新克隆，未覆盖旧目录，也未执行旧目录的恢复清单。
- 复用此前本地候选人业务、匹配、迁移、界面与测试；按新规则使用单独文件。原有 88 个文件的 SHA-256 校验通过，`git diff --exit-code` 返回 0。
- 本项目新建自己的 `.venv`，按原 requirements.lock 安装；前端依赖仅装入 frontend/candidate/node_modules，未使用旧目录的依赖链接。
- 最新上游资料补填页的退出按钮已保留；账户类型、技能规范化和 CSS 导入团队实现，其他派生代码保留来源说明。
- 候选人测试、pytest 配置和 Alembic 环境均独立，不更改团队入口、迁移或测试夹具。

| 本轮实际执行 | 结果 |
| --- | --- |
| `python scripts/check_candidate_ownership.py` | 88 个原文件不变，新增文件均在候选人范围 |
| `python -m pip check` | 通过 |
| 扩展代码与脚本 Ruff | 通过 |
| `python -m pytest -c pytest.candidate.ini -q` | 103 passed，1 skipped |
| 原团队账号接口 `backend/tests/users/test_account_responses.py` | 50 passed |
| frontend/candidate 的 build、lint | 通过 |
| React 纯文本 XSS 单测 | 1 passed |
| Chromium + 临时 SQLite + 实际 API | 6 passed |
| `python scripts/preview_candidate.py --smoke` | 两项服务启动成功并自动停止 |

后端各有一个既有 Starlette/httpx 弃用警告；跳过项为需要显式提供测试地址的真实 PostgreSQL 并发测试。浏览器测试执行了独立 Alembic 配置的完整 SQLite 迁移，并验证第二客户端实际预约冲突；这些证据不替代 PostgreSQL 并发验证。

本轮没有连接个人数据库，没有验证真实 PostgreSQL、Docker 或远程 CI；没有提交、推送。整个团队项目仍依赖雇主职位管理、申请状态修改及面试时段管理，不能将候选人扩展通过视为全项目完成。

运行方式见 CANDIDATE_README.md；队友接入依赖见 CANDIDATE_INTEGRATION.md；本轮文件清单与原文件指纹分别在 CANDIDATE_FILES.json、CANDIDATE_BASELINE.json。
