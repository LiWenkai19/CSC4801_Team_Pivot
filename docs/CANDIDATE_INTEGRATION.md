# 候选人扩展接入说明

此文件只描述接口依赖，不要求助手编辑队友文件。当前扩展可独立运行。

## 数据与业务

- 原账户、候选人资料、技能和公司资料表继续使用 `app.users.model`；不重复定义。
- `app.candidate.model` 定义 Job、JobSkill、Application、ApplicationStatus、InterviewSlot 和 Booking。团队其他模块尚未定义这些表；接入时复用这些模型，避免重复表或迁移。
- CAN-006（2026-10-26 更新）：运行服务使用 `app.candidate.recommendation_scoring.match_score` 作为双方共享的占位评分入口，统一返回 0，并在职位及雇主申请行中返回 `score_kind=placeholder`。`app.matching` 保留规范化和排序；旧技能交集评分函数仍在文件中，但当前运行服务不调用。后续真实算法另行开发，不能将占位 0 理解为不匹配。
- 雇主模块仍负责职位管理、申请状态修改、时段管理。候选人无状态修改能力；四个状态值保持 Pending、Interviewing、Rejected、Accepted。
- 预约检查所有权、同雇主、Interviewing、未来且未占用、申请未预约；使用事务、行锁和唯一约束。冲突返回 `409 Slot already booked`。真实 PostgreSQL 并发仍须实际验收。

## HTTP 与界面

- CAN-005：候选人首次填写和编辑表单已使用 `SkillTagPicker`。雇主可在自己的职位表单复用该组件及预置技能目录，并通过自己模块的授权保存接口写入 JobSkill；本扩展未新增雇主职位写入路由。接入片段、目录边界及预览页见 `CANDIDATE_SKILL_TAGS.md`。
- CAN-003：候选人通过 `GET /candidate/applications` 和 `GET /candidate/applications/{application_id}` 查看本人状态及预约；雇主通过 `GET /employer/jobs/{job_id}/applications` 查看自己职位的同类信息。共用 status、booking 数据；Interviewing 且无 booking 表示邀约待选时段，有 booking 展示预约时间。雇主页面由对应所有者接入，具体权限、状态变化和刷新边界见 `CANDIDATE_FEATURE_PERMISSION_LEDGER.md`。
- `app.candidate.router.router` 提供资料读改、职位、申请和预约接口；2026-10-26 权限更新为候选人仅读本人、已登录雇主仅读申请过自己职位的候选人、候选人仅本人可改。雇主页面通过 `GET /users/candidates/{candidate_id}/profile` 展示简历，详情见 `CANDIDATE_RESUME_ACCESS.md`。
- `app.candidate.accounts.user_router` 在独立应用中包装现有 handler，加严格字段校验，保留团队账户实现。
- 当前新应用完整入口为 `app.candidate_main:app`，不会给 `app.main.app` 动态插入路由或替换全局函数。
- 前端入口在 `frontend/candidate/src/App.tsx`，候选人页面在 `src/pages/candidate/`。认证、API、资料补填派生文件使用独立路径，保留最新补填退出按钮与会话隔离。
- 未来主应用需要挂载路由时，由入口文件所有者决定如何调用这些组件与路由；不得简单覆盖原 App、AuthContext 或 common_api。

## 配置与文档

- 独立 Alembic 配置同时读取团队原迁移目录与候选人新增迁移目录；原 env.py 和初始迁移不改动。
- 安装前端依赖只针对 `frontend/candidate/`，不修改外层 package.json 或锁文件。
- 根 `INSTALL.md`、`SPEC.md`、README 和原进度文档保留原样。本扩展的安装、规格位置、测试证据在 CANDIDATE_README.md 和 CANDIDATE_PROGRESS.md；课程最终交付文档由相应所有者合并。
- `scripts/check_candidate_ownership.py` 对比重新克隆时的 88 个原文件 SHA-256，并检查新增文件是否仍在候选人范围内。上游文件有意升级时，先审阅、再重新建立基线，不跳过检查。
