# 雇主模块进度

## 2026-11-04：雇主工作流模块（employer-only 分支）

- 背景：在 main 基础上剔除 candidate 分支继承来的逻辑，只保留雇主侧。用户裁决：共享数据层参照 main 少量添加（不继承 candidate 的数据模型）；FP-EMP-3 申请人列表在 employer 自建并真实打分；candidate 侧周边产物全清。测试连本机 pgsql 的独立库 `symanage_test`，以 employer 分支旧代码为参考移植。
- 范围：一次性实现 FP-EMP-1/2/3 与 FP-MATCH-1 雇主侧全部接口（用户明确批准的埋点清单）：
  - `GET/PATCH /employer/company`（FP-EMP-1）
  - `POST/GET /employer/jobs`、`GET/PATCH/DELETE /employer/jobs/{job_id}`（FP-EMP-2）
  - `GET /employer/jobs/{job_id}/applications`、`PATCH /employer/applications/{id}/status`（FP-EMP-3）
  - `match_score`（FP-MATCH-1，候选人侧调用点待 candidate 模块接入）
- 状态：验证通过。
- 设计要点：
  - 无独立 company 表；公司资料读写 users 模块的 `EmployerProfile`（company_name 唯一真相源）。
  - 五张业务表（job/job_skill/application/interview_slot/booking）挂 `SQLModel.metadata`，迁移 `c8f4a2b91d37`；`ApplicationStatus` 用 SAEnum `native_enum=False`。
  - 业务错误为 `ValueError` 子类，router `_to_http` 走 MRO 查表转 HTTP；404（资源不存在/已删）与 403（非本人）语义分开；删除/改状态带 `with_for_update` 行锁。
  - 职位软删除（is_deleted）；有申请或面试时段时删除 409 且不写入。
  - 申请人列表行含 application_id/candidate_id/display_name/skills/match_score/status/booking，绝不含 resume_text；排序键 `(-match_score, display_name.lower(), str(candidate_id))`。
  - 打分契约：normalize（trim/lower/去空/去重）后 `score = 100`（|R|=0）或 `floor(100*|C∩R|/|R|)`。
- 涉及文件：
  - 新增 `app/employer/`（model/schema/service/router/matching/REQUIREMENTS.md/PROGRESS.md）、`alembic/versions/c8f4a2b91d37_create_employer_workflow_tables.py`、`tests/employer/`（conftest + 4 个测试文件）、`scripts/seed_demo.py`。
  - 修改 `alembic/env.py`（注册 employer 模型到迁移元数据）、`app/main.py`（挂载 employer_router）。
  - README.md 的 Requirement–Test Mapping 表填入 FP-EMP-1/2/3、FP-MATCH-1 行。
- 实际验证：SYManage 解释器在 backend 目录执行
  - `python -m ruff check app/employer tests/employer alembic/versions/c8f4a2b91d37_create_employer_workflow_tables.py alembic/env.py app/main.py` → All checks passed（env.py 两模型导入改为别名消除 F811）。
  - `python -m pytest tests/employer -q` → 28 passed。
  - `python -m pytest tests/employer tests/users/test_account_responses.py -q` → 78 passed（用户模块回归 50 项通过）。
  - 测试基础设施：连本机 pgsql 的 `symanage_test`（自动建库、session 级 `alembic upgrade head` 验证迁移链、每测试前 TRUNCATE 隔离）；认证配置用测试占位值，只复用 .env 的数据库连接。
- 测试覆盖（每接口按正常/非法参数/未登录/越权/不存在五场景评估，详见测试文件 docstring）：
  - FP-EMP-1：查看编辑、422 校验（空白名/null/未声明字段）、未填资料 404、角色 403/未登录 401。
  - FP-EMP-2：创建字段与技能规范化、422/409、列表/详情所有权、PATCH 替换技能、他人禁改删（FP-SEC-1）、软删、两类删除冲突 409、SQL 元字符绑定（FP-SEC-2）。
  - FP-EMP-3：行字段（无 resume_text）、按分降序、行内 booking、状态四值 parametrize + 非法 422、改状态保预约、他人/候选人禁改、404、列表仅属主。
  - FP-MATCH-1：四示例、归一化两侧、floor 边界、雇主侧平级规则（显示名不区分大小写 → candidate_id）。
  - 未登录场景：company/jobs/applications 各组测试经真实 `require_employer` 依赖验证 401/403；未替换认证依赖。
- 遗留及下一步：
  - FP-MATCH-1 的候选人侧平级规则（按职位标题）与共用调用点，待 candidate 模块实现时接入 `app/employer/matching.match_score`（或届时迁到共享位置）。
  - FP-SCHED 系列（时段管理、预约、竞争）不在本轮范围；interview_slot/booking 表仅作为删除依赖与列表展示。
  - `scripts/seed_demo.py` 已按 FP-DOC-3 写好（含 FP-MATCH-1 四示例、四状态、两名 Interviewing 候选人竞争同一空闲时段）。已在 `symanage_test` 上验证（DATABASE_URL 指向测试库执行，exit=0，四个示例分数 100/50/0/100 与预期一致；首次运行因依赖分组顺序触发外键冲突，改为按外键依赖分组 flush 后通过）；未对开发库执行。
  - `tests/users/test_schema.py` 为 main 上的既有坏测试（导入被注释的 CandidateProfileUpdate），未动。
  - 工作区原有 AGENT.md 删除与 AGENTS.md 修改属用户未提交改动，本轮未触碰、不随本分支提交。
