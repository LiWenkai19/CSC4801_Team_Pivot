# Candidate Flow 逐文件阅读导航

更新：2026-11-03。原有107个文件及对抗性审阅新增4个，共111个文件；不计node_modules、.venv、构建缓存、截图或本地SQLite等产物。

当前分支为candidate，HEAD为c2667bd。表内“已提交”表示文件已纳入本地分支，不表示本次测试后的最新修改已推送；“本地修改”“新增未提交”可据此区分。

这些文件涵盖独立实现、已有候选人实现复用及团队代码的独立派生副本；不能将所有文件都解释为原创。前端来源见[PROVENANCE.md](../frontend/candidate/PROVENANCE.md)。团队原有88个文件保持不变。

## 建议先按这条主线阅读

1. [功能与权限台账](CANDIDATE_FEATURE_PERMISSION_LEDGER.md)：先了解CAN-001～006做了什么。
2. [整体入口说明](CANDIDATE_README.md)和[接入边界](CANDIDATE_INTEGRATION.md)：了解如何运行及哪些需要队友接入。
3. [前端路由](../frontend/candidate/src/App.tsx) → [资料页](../frontend/candidate/src/pages/candidate/ProfilePage.tsx) → [表单](../frontend/candidate/src/pages/users/CandidateForm.tsx) → [标签组件](../frontend/candidate/src/components/skills/SkillTagPicker.tsx)。
4. [请求包装](../frontend/candidate/src/api/candidate_api.ts) → [后端路由](../backend/app/candidate/router.py) → [业务服务](../backend/app/candidate/service.py)。
5. [简历读取授权](../backend/app/candidate/resume_access.py)、[请求字段校验](../backend/app/candidate/profile_schema.py)、[当前响应结构](../backend/app/candidate/schema.py)。
6. [运行应用模型](../backend/app/candidate/model.py)与[独立七表模型](../backend/app/candidate/database/model.py)对照看，再读各自迁移链。二者不要混作同一个已接入的业务数据库。
7. [推荐列表](../frontend/candidate/src/pages/candidate/JobsPage.tsx) → [评分占位入口](../backend/app/candidate/recommendation_scoring.py) → [申请按钮](../frontend/candidate/src/components/candidate/ApplyButton.tsx) → [申请/预约页](../frontend/candidate/src/pages/candidate/ApplicationsPage.tsx)。
8. [最新测试报告](CANDIDATE_TEST_REPORT_20261027.md)，再逐个看本导航测试分组中的样例。

下面按上述层次列出全部文件，每项均可打开。编号仅表示阅读次序。

## 1. 总览、需求与交付文档（14个）

| 序号 | 文件 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| 1 | [docs/CANDIDATE_BASELINE.json](CANDIDATE_BASELINE.json) | 88个团队基线文件的提交号及SHA-256，用于检查原文件未被改动。 | 已提交 |
| 2 | [docs/CANDIDATE_DATABASE.md](CANDIDATE_DATABASE.md) | 独立七表结构、字段、迁移方式、数据库依赖与接入边界。 | 已提交 |
| 3 | [docs/CANDIDATE_DATABASE_POSTGRESQL.sql](CANDIDATE_DATABASE_POSTGRESQL.sql) | 独立迁移生成的PostgreSQL离线DDL，不代表已经在PG上执行。 | 已提交 |
| 4 | [docs/CANDIDATE_DATABASE_VALIDATION.json](CANDIDATE_DATABASE_VALIDATION.json) | 独立数据库结构与检查的历史机器可读证据。 | 已提交 |
| 5 | [docs/CANDIDATE_FEATURE_PERMISSION_LEDGER.md](CANDIDATE_FEATURE_PERMISSION_LEDGER.md) | CAN-001～006功能、角色权限、边界、接入事项及最新验收状态的总台账。 | 已提交，本地有修改 |
| 6 | [docs/CANDIDATE_FILES.json](CANDIDATE_FILES.json) | 候选人文件归属清单；本导航以它为索引并核对Git新增文件。 | 已提交，本地有修改 |
| 7 | [docs/CANDIDATE_FILE_GUIDE.md](CANDIDATE_FILE_GUIDE.md) | 本次新增的逐文件阅读导航；为原有98个文件补充用途、顺序及本地状态。 | 本次新增导航，未提交 |
| 8 | [docs/CANDIDATE_INTEGRATION.md](CANDIDATE_INTEGRATION.md) | 队友接入后端路由、页面、技能标签、评分和权限时需要遵守的接口约定。 | 已提交 |
| 9 | [docs/CANDIDATE_PROGRESS.md](CANDIDATE_PROGRESS.md) | 按日期记录开发、验证及限制；较早条目是历史记录。 | 已提交，本地有修改 |
| 10 | [docs/CANDIDATE_README.md](CANDIDATE_README.md) | 独立扩展总入口，介绍安装、启动、检查及浏览器测试命令。 | 已提交，本地有修改 |
| 11 | [docs/CANDIDATE_RESUME_ACCESS.md](CANDIDATE_RESUME_ACCESS.md) | 简历读改接口、身份与投递关系授权规则，以及错误状态码。 | 已提交 |
| 12 | [docs/CANDIDATE_SKILL_TAGS.md](CANDIDATE_SKILL_TAGS.md) | 技能标签组件行为、雇主接入片段、共享目录边界及验证更新。 | 已提交，本地有修改 |
| 13 | [docs/CANDIDATE_TEST_REPORT_20261027.md](CANDIDATE_TEST_REPORT_20261027.md) | 最新完整测试结果、功能覆盖、复现命令、已知收集阻塞与PG限制。 | 新增未提交 |
| 14 | [docs/CANDIDATE_VALIDATION.json](CANDIDATE_VALIDATION.json) | 历史验证记录及latest_run当前测试结果，阅读时优先看latest_run。 | 已提交，本地有修改 |

## 2. 后端运行入口与业务实现（13个）

| 序号 | 文件 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| 15 | [backend/app/candidate/AGENTS.md](../backend/app/candidate/AGENTS.md) | 该独立目录的维护约定与文件修改边界。 | 已提交 |
| 16 | [backend/app/candidate/REQUIREMENTS.md](../backend/app/candidate/REQUIREMENTS.md) | 候选人需求摘录，注明用户对权限和占位评分的最新调整。 | 已提交 |
| 17 | [backend/app/candidate/accounts.py](../backend/app/candidate/accounts.py) | 包装团队账号接口，增加严格字段校验及资料完成状态。 | 已提交 |
| 18 | [backend/app/candidate/model.py](../backend/app/candidate/model.py) | 当前运行应用的职位、技能、申请、时段和预约模型，复用团队账号模型。 | 已提交 |
| 19 | [backend/app/candidate/profile_schema.py](../backend/app/candidate/profile_schema.py) | 注册、登录、资料创建/更新的扩展校验，拒绝额外字段、非法null和伪造归属。 | 已提交 |
| 20 | [backend/app/candidate/recommendation_scoring.py](../backend/app/candidate/recommendation_scoring.py) | 当前生效的评分占位入口，统一返回0，后续替换真实算法。 | 已提交 |
| 21 | [backend/app/candidate/resume_access.py](../backend/app/candidate/resume_access.py) | 简历读取授权：候选人仅读本人，雇主仅读自己职位的申请人。 | 已提交 |
| 22 | [backend/app/candidate/router.py](../backend/app/candidate/router.py) | 候选人HTTP路由，连接身份依赖、业务服务与错误状态码。 | 已提交 |
| 23 | [backend/app/candidate/schema.py](../backend/app/candidate/schema.py) | 职位、申请、时段、预约等API请求和响应结构。 | 已提交 |
| 24 | [backend/app/candidate/seed.py](../backend/app/candidate/seed.py) | 独立演示环境的虚构账号、职位、技能、申请与时段。 | 已提交 |
| 25 | [backend/app/candidate/service.py](../backend/app/candidate/service.py) | 资料保存、职位列表、重复申请、申请读取、预约与雇主申请列表的主要业务逻辑。 | 已提交 |
| 26 | [backend/app/candidate_main.py](../backend/app/candidate_main.py) | 独立FastAPI入口，挂载候选人和账号扩展路由，不修改团队main。 | 已提交 |
| 27 | [backend/app/matching.py](../backend/app/matching.py) | 保留技能规范化、列表排序及历史技能交集评分；当前业务评分已转到recommendation_scoring。 | 已提交 |

## 3. 独立七表数据库与迁移（8个）

| 序号 | 文件 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| 28 | [backend/app/candidate/database/__init__.py](../backend/app/candidate/database/__init__.py) | 独立七表数据库包的范围说明。 | 已提交 |
| 29 | [backend/app/candidate/database/__main__.py](../backend/app/candidate/database/__main__.py) | 独立数据库CLI入口，用显式数据库地址执行建库/检查等操作。 | 已提交 |
| 30 | [backend/app/candidate/database/migration.py](../backend/app/candidate/database/migration.py) | 独立迁移配置、连接及模型差异检查的封装。 | 已提交 |
| 31 | [backend/app/candidate/database/migrations/env.py](../backend/app/candidate/database/migrations/env.py) | 独立七表迁移环境，仅管理用户负责的表。 | 已提交 |
| 32 | [backend/app/candidate/database/migrations/versions/owned_booking_003.py](../backend/app/candidate/database/migrations/versions/owned_booking_003.py) | 第三阶段增量迁移：Booking及申请/时段的唯一关联和外键。 | 已提交 |
| 33 | [backend/app/candidate/database/migrations/versions/owned_core_001.py](../backend/app/candidate/database/migrations/versions/owned_core_001.py) | 第一阶段迁移：账号、候选人资料、技能、公司及相关约束/时间维护。 | 已提交 |
| 34 | [backend/app/candidate/database/migrations/versions/owned_flow_002.py](../backend/app/candidate/database/migrations/versions/owned_flow_002.py) | 第二阶段迁移：申请和面试时段，依赖队友职位及雇主表。 | 已提交 |
| 35 | [backend/app/candidate/database/model.py](../backend/app/candidate/database/model.py) | 独立registry中的用户负责七表映射；与当前运行应用的模型是两套映射，不自动切换业务库。 | 已提交 |

## 4. 当前运行应用的迁移链（3个）

| 序号 | 文件 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| 36 | [backend/alembic.candidate.ini](../backend/alembic.candidate.ini) | 当前运行应用的独立Alembic配置，引用团队原迁移但不修改它们。 | 已提交 |
| 37 | [backend/candidate_alembic/env.py](../backend/candidate_alembic/env.py) | 当前运行应用的迁移环境，注册团队账号与候选人业务元数据。 | 已提交 |
| 38 | [backend/candidate_alembic/versions/candidate_flow_001.py](../backend/candidate_alembic/versions/candidate_flow_001.py) | 当前运行应用的职位、技能、申请、时段、预约迁移；与独立七表迁移链区分阅读。 | 已提交 |

## 5. 前端页面与表单（12个）

| 序号 | 文件 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| 39 | [frontend/candidate/src/pages/NavPage.tsx](../frontend/candidate/src/pages/NavPage.tsx) | 独立主页导航，候选人可进入资料、推荐和申请页。 | 已提交 |
| 40 | [frontend/candidate/src/pages/candidate/ApplicationsPage.tsx](../frontend/candidate/src/pages/candidate/ApplicationsPage.tsx) | 本人申请状态、面试邀约对应的选时段入口、预约提交和已预约时间。 | 已提交 |
| 41 | [frontend/candidate/src/pages/candidate/JobPage.tsx](../frontend/candidate/src/pages/candidate/JobPage.tsx) | 单个职位详情、占位分数与申请操作。 | 已提交 |
| 42 | [frontend/candidate/src/pages/candidate/JobsPage.tsx](../frontend/candidate/src/pages/candidate/JobsPage.tsx) | 推荐列表，按后端顺序显示职位、技能、分数、详情与申请入口。 | 已提交 |
| 43 | [frontend/candidate/src/pages/candidate/ProfilePage.tsx](../frontend/candidate/src/pages/candidate/ProfilePage.tsx) | 本人资料读取/编辑、已保存简历展示和推荐入口。 | 已提交 |
| 44 | [frontend/candidate/src/pages/users/CandidateDetailsPage.tsx](../frontend/candidate/src/pages/users/CandidateDetailsPage.tsx) | 首次资料填写、保存后确认完成状态并进入推荐。 | 已提交 |
| 45 | [frontend/candidate/src/pages/users/CandidateForm.tsx](../frontend/candidate/src/pages/users/CandidateForm.tsx) | 候选人名称、文本简历和技能标签的复用表单；首次填写与编辑共用。 | 已提交 |
| 46 | [frontend/candidate/src/pages/users/EmployerDetailsPage.tsx](../frontend/candidate/src/pages/users/EmployerDetailsPage.tsx) | 独立派生的雇主公司资料补填页，不是职位管理页。 | 已提交 |
| 47 | [frontend/candidate/src/pages/users/EmployerForm.tsx](../frontend/candidate/src/pages/users/EmployerForm.tsx) | 独立派生的公司资料表单，不包含雇主职位保存服务。 | 已提交 |
| 48 | [frontend/candidate/src/pages/users/LoginForm.tsx](../frontend/candidate/src/pages/users/LoginForm.tsx) | 独立登录表单及输入状态。 | 已提交 |
| 49 | [frontend/candidate/src/pages/users/LoginPage.tsx](../frontend/candidate/src/pages/users/LoginPage.tsx) | 登录页面，调用认证上下文并跳转。 | 已提交 |
| 50 | [frontend/candidate/src/pages/users/RegisterPage.tsx](../frontend/candidate/src/pages/users/RegisterPage.tsx) | 账号注册与角色选择，成功后进入对应资料补填流程。 | 已提交 |

## 6. 前端功能组件（10个）

| 序号 | 文件 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| 51 | [frontend/candidate/src/components/PlainText.tsx](../frontend/candidate/src/components/PlainText.tsx) | 安全展示简历/职位说明纯文本，保留文本而不插入HTML。 | 已提交 |
| 52 | [frontend/candidate/src/components/RequireAuth.tsx](../frontend/candidate/src/components/RequireAuth.tsx) | 登录和资料完成状态守卫，限制私有页面访问。 | 已提交 |
| 53 | [frontend/candidate/src/components/RequireCandidate.tsx](../frontend/candidate/src/components/RequireCandidate.tsx) | 候选人角色页面守卫，雇主进入时展示禁止访问。 | 已提交 |
| 54 | [frontend/candidate/src/components/candidate/ApplicationFeedback.tsx](../frontend/candidate/src/components/candidate/ApplicationFeedback.tsx) | 已申请状态及重复申请的持续中文反馈。 | 已提交 |
| 55 | [frontend/candidate/src/components/candidate/ApplyButton.tsx](../frontend/candidate/src/components/candidate/ApplyButton.tsx) | 申请提交、提交中禁用、重复409处理及已申请状态刷新。 | 已提交 |
| 56 | [frontend/candidate/src/components/candidate/ErrorMessage.tsx](../frontend/candidate/src/components/candidate/ErrorMessage.tsx) | 共用错误展示，使用可访问的alert提示。 | 已提交 |
| 57 | [frontend/candidate/src/components/candidate/RecommendationScore.tsx](../frontend/candidate/src/components/candidate/RecommendationScore.tsx) | 明确显示0分占位，避免被理解为真实匹配百分比。 | 已提交 |
| 58 | [frontend/candidate/src/components/skills/SkillTagPicker.css](../frontend/candidate/src/components/skills/SkillTagPicker.css) | 技能标签、搜索框、下拉建议和选中/禁用/焦点状态的局部样式。 | 已提交 |
| 59 | [frontend/candidate/src/components/skills/SkillTagPicker.tsx](../frontend/candidate/src/components/skills/SkillTagPicker.tsx) | 标签搜索、下拉推荐、键盘/鼠标选择、自定义、去重、移除及未确认输入校验。 | 已提交 |
| 60 | [frontend/candidate/src/components/skills/skillCatalog.ts](../frontend/candidate/src/components/skills/skillCatalog.ts) | 共享初始技能目录、规范化和去重函数，供双方标签组件复用。 | 已提交 |

## 7. 前端会话、请求与路由基础（9个）

| 序号 | 文件 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| 61 | [frontend/candidate/src/App.css](../frontend/candidate/src/App.css) | 通过导入复用团队App样式的独立桥接文件。 | 已提交 |
| 62 | [frontend/candidate/src/App.tsx](../frontend/candidate/src/App.tsx) | 独立前端页面路由，组合登录守卫、资料补填和候选人页面。 | 已提交 |
| 63 | [frontend/candidate/src/api/candidate_api.ts](../frontend/candidate/src/api/candidate_api.ts) | 候选人接口请求包装，统一调用已登录请求函数。 | 已提交 |
| 64 | [frontend/candidate/src/api/common_api.ts](../frontend/candidate/src/api/common_api.ts) | 独立请求及账号API封装，解析错误、保存状态码并处理失效认证。 | 已提交 |
| 65 | [frontend/candidate/src/contexts/AuthContext.tsx](../frontend/candidate/src/contexts/AuthContext.tsx) | 认证会话状态、登录/注册、账号刷新、退出和迟到响应隔离。 | 已提交 |
| 66 | [frontend/candidate/src/hooks/useRemote.ts](../frontend/candidate/src/hooks/useRemote.ts) | 业务数据读取Hook，管理加载、错误、刷新及过期请求结果。 | 已提交 |
| 67 | [frontend/candidate/src/index.css](../frontend/candidate/src/index.css) | 通过导入复用团队全局样式的独立桥接文件。 | 已提交 |
| 68 | [frontend/candidate/src/main.tsx](../frontend/candidate/src/main.tsx) | React启动，挂载路由与认证Provider。 | 已提交 |
| 69 | [frontend/candidate/src/types.ts](../frontend/candidate/src/types.ts) | 复用团队账号类型，补充候选人Job/Application/Slot/Booking响应类型。 | 已提交 |

## 8. 后端及前端测试（14个）

| 序号 | 文件 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| 70 | [backend/candidate_tests/browser_server.py](../backend/candidate_tests/browser_server.py) | 真实E2E后端：创建临时SQLite、运行迁移、注入虚构数据并启动API。 | 已提交 |
| 71 | [backend/candidate_tests/conftest.py](../backend/candidate_tests/conftest.py) | 候选人后端测试夹具，提供隔离数据库、认证身份及接口客户端。 | 已提交 |
| 72 | [backend/candidate_tests/test_candidate_accounts.py](../backend/candidate_tests/test_candidate_accounts.py) | 注册、登录、角色、资料填写、账号完成状态及回滚测试。 | 已提交 |
| 73 | [backend/candidate_tests/test_candidate_flow.py](../backend/candidate_tests/test_candidate_flow.py) | 资料、职位、历史评分函数、当前占位推荐、申请、预约及雇主读取回归。 | 已提交，本地有修改 |
| 74 | [backend/candidate_tests/test_candidate_integration.py](../backend/candidate_tests/test_candidate_integration.py) | 从注册/资料到推荐、申请和预约的跨模块接口契约测试。 | 已提交，本地有修改 |
| 75 | [backend/candidate_tests/test_candidate_schemas.py](../backend/candidate_tests/test_candidate_schemas.py) | 字段类型、默认值、额外字段、null、名称和归属校验测试。 | 已提交 |
| 76 | [backend/candidate_tests/test_feature_acceptance.py](../backend/candidate_tests/test_feature_acceptance.py) | CAN-001～006针对性验收，含8个查询接口权限矩阵、重复申请和双方数据一致性。 | 新增未提交 |
| 77 | [backend/candidate_tests/test_owned_database.py](../backend/candidate_tests/test_owned_database.py) | 独立七表迁移、外键/唯一约束、触发器及Booking持久化与删除保护测试。 | 已提交，本地有修改 |
| 78 | [backend/candidate_tests/test_postgres.py](../backend/candidate_tests/test_postgres.py) | 真实PostgreSQL并发预约/重复申请测试，需专用测试库；当前环境跳过。 | 已提交 |
| 79 | [backend/candidate_tests/test_resume_access.py](../backend/candidate_tests/test_resume_access.py) | 简历身份、对象归属、投递关系、修改拒绝及边界专项测试。 | 已提交 |
| 80 | [frontend/candidate/e2e/candidate.spec.ts](../frontend/candidate/e2e/candidate.spec.ts) | 6项既有完整浏览器流程，现已适配技能标签和占位评分。 | 已提交，本地有修改 |
| 81 | [frontend/candidate/e2e/features.spec.ts](../frontend/candidate/e2e/features.spec.ts) | 4项新功能浏览器验收：标签、自定义/校验、重复409提示、输入法和窄屏。 | 新增未提交 |
| 82 | [frontend/candidate/src/components/PlainText.test.tsx](../frontend/candidate/src/components/PlainText.test.tsx) | 验证实际文本渲染器会转义用户HTML，不执行脚本。 | 已提交 |
| 83 | [frontend/candidate/src/components/skills/skillCatalog.test.ts](../frontend/candidate/src/components/skills/skillCatalog.test.ts) | 技能规范化、Java/JavaScript区分、目录去重和扩展选项测试。 | 新增未提交 |

## 9. 前端工程配置与预览（12个）

| 序号 | 文件 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| 84 | [frontend/candidate/.env.example](../frontend/candidate/.env.example) | 独立前端配置示例，只含API地址等示例配置，不含真实凭据。 | 已提交 |
| 85 | [frontend/candidate/.gitignore](../frontend/candidate/.gitignore) | 排除独立前端依赖、构建、测试产物及本地环境文件。 | 已提交 |
| 86 | [frontend/candidate/.oxlintrc.json](../frontend/candidate/.oxlintrc.json) | 独立前端静态检查规则。 | 已提交 |
| 87 | [frontend/candidate/AGENTS.md](../frontend/candidate/AGENTS.md) | 该独立目录的维护约定与文件修改边界。 | 已提交 |
| 88 | [frontend/candidate/PROVENANCE.md](../frontend/candidate/PROVENANCE.md) | 前端来源说明，区分原有实现复用、团队代码派生与独立扩展。 | 已提交 |
| 89 | [frontend/candidate/index.html](../frontend/candidate/index.html) | 独立Vite应用的HTML挂载入口。 | 已提交 |
| 90 | [frontend/candidate/package-lock.json](../frontend/candidate/package-lock.json) | 独立前端依赖锁定，通常无需逐行阅读。 | 已提交 |
| 91 | [frontend/candidate/package.json](../frontend/candidate/package.json) | 独立前端依赖及dev/build/lint/test/e2e命令。 | 已提交 |
| 92 | [frontend/candidate/playwright.config.ts](../frontend/candidate/playwright.config.ts) | 浏览器测试配置，自动启动隔离后端和前端，限制测试并发。 | 已提交 |
| 93 | [frontend/candidate/previews/skill-tags.html](../frontend/candidate/previews/skill-tags.html) | 无数据库组件预览，演示候选人表单与雇主技能选择器。 | 已提交 |
| 94 | [frontend/candidate/tsconfig.json](../frontend/candidate/tsconfig.json) | 独立前端TypeScript编译配置。 | 已提交 |
| 95 | [frontend/candidate/vite.config.ts](../frontend/candidate/vite.config.ts) | 独立Vite开发/构建配置。 | 已提交 |

## 10. 检查、启动脚本与测试配置（4个）

| 序号 | 文件 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| 96 | [pytest.candidate.ini](../pytest.candidate.ini) | 只收集候选人后端测试并设置模块路径，避免默认混入队友测试。 | 已提交 |
| 97 | [scripts/check_candidate.py](../scripts/check_candidate.py) | 统一检查入口：归属、依赖、静态检查、后端测试及前端构建/测试。 | 已提交 |
| 98 | [scripts/check_candidate_ownership.py](../scripts/check_candidate_ownership.py) | 比对团队基线指纹并检查新增文件范围。 | 已提交 |
| 99 | [scripts/preview_candidate.py](../scripts/preview_candidate.py) | 创建临时虚构数据并启动独立前后端，支持smoke检查和自动清理。 | 已提交 |

## 不计入上述源码文件数的本地产物

- `.venv/`、`node_modules/`：运行依赖。
- `dist/`、测试结果、Playwright报告、缓存和截图：可再生成的验证产物。
- `backend/data/owned_schema.sqlite3`：本地独立数据库，未纳入Git源码清单；查看结构优先读数据库模型和说明，避免直接改库。
- 团队原有 `backend/app/users/`、`backend/app/core/`、`backend/app/db/`、原 `main.py` 及外层 `frontend/src/`：被导入或复用，但没有因为本轮candidate flow而成为新增文件，也未被修改。

## 2026-10-28 安全审计新增文件（3个）

下表为本次新增、未提交文件；此前各行提交状态为2026-10-27建立导航时的快照。

| 序号 | 文件 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| 100 | [backend/candidate_tests/audit_reproduction.py](../backend/candidate_tests/audit_reproduction.py) | 后端修复回归及大输入诊断；前三项也由常规套件调用。 | 新增未提交 |
| 101 | [frontend/candidate/audit/session-reproduction.mjs](../frontend/candidate/audit/session-reproduction.mjs) | 独立浏览器会话修复回归及令牌撤销边界诊断。 | 新增未提交 |
| 102 | [docs/CANDIDATE_SECURITY_REVIEW_20261028.md](CANDIDATE_SECURITY_REVIEW_20261028.md) | 2026-10-28安全审阅：4项确认问题、证据、严重程度、修复建议和边界。 | 新增未提交 |

## 2026-10-28 缺陷修复新增文件（5个）

| 序号 | 文件 | 用途 | 当前状态 |
| --- | --- | --- | --- |
| 103 | [backend/app/candidate/secure_session.py](../backend/app/candidate/secure_session.py) | 独立安全数据库会话。 | 新增未提交 |
| 104 | [backend/app/candidate/recommendation_queries.py](../backend/app/candidate/recommendation_queries.py) | 批量读取职位推荐资料。 | 新增未提交 |
| 105 | [backend/candidate_tests/test_bugfix_regression.py](../backend/candidate_tests/test_bugfix_regression.py) | 后端缺陷回归。 | 新增未提交 |
| 106 | [frontend/candidate/e2e/session_security.spec.ts](../frontend/candidate/e2e/session_security.spec.ts) | 多标签页会话浏览器回归。 | 新增未提交 |
| 107 | [docs/CANDIDATE_BUGFIX_20261028.md](CANDIDATE_BUGFIX_20261028.md) | 修复范围及剩余边界。 | 新增未提交 |

## 2026-10-29 对抗性审阅新增文件（4个）

| 序号 | 文件 | 用途 | 状态快照 |
| --- | --- | --- | --- |
| 108 | [backend/candidate_tests/adversarial_20261029.py](../backend/candidate_tests/adversarial_20261029.py) | 使用隔离数据库复现后端问题。 | 推送前新增 |
| 109 | [frontend/candidate/audit/adversarial_20261029.config.ts](../frontend/candidate/audit/adversarial_20261029.config.ts) | 独立浏览器诊断配置。 | 推送前新增 |
| 110 | [frontend/candidate/audit/adversarial_20261029.diagnostic.ts](../frontend/candidate/audit/adversarial_20261029.diagnostic.ts) | 复现临时服务错误下的会话问题。 | 推送前新增 |
| 111 | [docs/CANDIDATE_ADVERSARIAL_REVIEW_20261029.md](CANDIDATE_ADVERSARIAL_REVIEW_20261029.md) | 已确认问题、复现证据与尚未修复的边界。 | 推送前新增 |
