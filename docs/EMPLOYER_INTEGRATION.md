# 雇主工作流模块接入说明

本文件面向组员（candidate 模块）与团队入口 / 文档所有者。实现范围见 `implement_guideline.md`；本模块不改动任何他人已跟踪文件。

## 1. 迁移顺序（只适用于新库）

```text
python -m app.candidate.database init --phase core   # 组员：user、candidate_profile、candidate_skill、company
python -m app.employer.database init                 # 雇主：employer_profile、job、job_skill、employer_company
python -m app.candidate.database init                # 组员：application、interview_slot、booking
```

- 两条链共用 `OWNED_DATABASE_URL`，未设置时都使用 `backend/data/owned_schema.sqlite3`。
- 雇主迁移开头检查 `user`、`company` 是否存在，缺失时以 `External dependency missing: <表名>; run candidate core phase first` 失败。
- 已有旧库（没有独立版本表）不能直接用本链升级；本链只负责新库。
- 版本表互相独立：`alembic_owned_version` 与 `alembic_employer_version`。

## 2. 组员的种子数据与旧测试夹具

组员现有种子 / 夹具用 `app.candidate.model.Job` 插入职位，不带 `company_id`。在新库上会因 `job.company_id` 非空而失败。需要组员：

- 在插入职位前先创建 `company` 与 `employer_company` 记录并补上 `company_id`；或
- 改为调用雇主接口 `POST /employer/jobs` 创建职位。

`job` 表新增列：`company_id`、`created_at`、`updated_at`；原有列 `id`、`employer_id`、`title`、`description`、`is_deleted` 的名称与含义保持不变，组员读取代码无需改动。

## 3. 公司名称来源不一致

组员的 `job_public` / `application_public` 读取 `employer_profile.company_name`；雇主模块以 `company.name` 为准（`employer_profile` 保持团队原结构，仅用于兼容旧入口）。建议组员改为：

- 调用 `app.employer.service.get_active_job_public()` / `list_active_jobs()`；或
- 直接读取组员自己的 `company` 表。

团队雇主资料创建接口（`POST /users/employer/profile`）仍是 `profile_completed` 的依据；雇主模块要求该资料存在才能 `POST /employer/company`（409 `Employer profile required`）。

## 4. 申请人列表

组员的 `employer_applicants`（`GET /employer/jobs/{job_id}/applications`）没有按 `is_deleted` 过滤职位。按本模块的删除规则，有申请的职位不能被删除，所以目前不会返回已删除职位的申请人；后续若改变删除规则，需要组员补过滤。

该接口继续负责排序、分数与预约展示；本模块只复用，不定义同一路径。

## 5. 逻辑外键

`application.job_id` 由数据库外键指向 `job.id`。代码层可调用：

```python
from app.employer.service import ensure_active_job

ensure_active_job(session, job_id)  # 不存在或已软删除 -> JobNotFoundError
```

组员 `apply()` 目前自己检查职位存在与 `is_deleted`，是否改为调用本函数由组员决定；错误语义一致（404 `Job not found`）。

## 6. 团队入口与 README 映射草稿

`app.main` 没有挂载本模块路由。合并时由入口所有者决定是否采用 `app.employer_main` 的组合方式：新建独立 `FastAPI`，依次挂载 `app.candidate.accounts.user_router`、`app.candidate.router.router`、`app.employer.router.employer_router`。

README 需求—测试映射行草稿（供文档所有者合并）：

| 需求 | 实现 | 单元测试 |
| --- | --- | --- |
| FP-EMP-1 | `backend/app/employer/service.py`（`create_company`、`get_my_company`、`update_my_company`）、`backend/app/employer/router.py` | `test_fp_emp_1_create_company_links_employer`、`test_fp_emp_1_create_company_requires_profile_and_once`、`test_fp_emp_1_get_and_patch_company`、`test_fp_emp_1_patch_rejects_blank_null_extra`、`test_fp_emp_1_company_auth_outcomes`、`test_fp_emp_1_patch_only_affects_own_company` |
| FP-EMP-2 | `backend/app/employer/service.py`（`create_job`、`list_my_jobs`、`get_my_job`、`update_job`、`delete_job`）、`backend/app/employer/model.py` | `test_fp_emp_2_create_job_fields_and_skills`、`test_fp_emp_2_create_job_validation`、`test_fp_emp_2_list_and_get_only_own_active_jobs`、`test_fp_emp_2_update_job_replaces_skills_and_updated_at`、`test_fp_emp_2_other_employer_cannot_edit_or_delete`、`test_fp_emp_2_soft_delete_without_dependents`、`test_fp_emp_2_delete_conflict_with_application`、`test_fp_emp_2_delete_conflict_with_interview_slot` |
| FP-EMP-3 | `backend/app/employer/service.py`（`change_application_status`）；申请人列表复用组员 `backend/app/candidate/router.py` | `test_fp_emp_3_set_status_all_four_values`、`test_fp_emp_3_status_change_keeps_booking`、`test_fp_emp_3_other_employer_and_candidate_cannot_change`、`test_fp_emp_3_missing_application_returns_404`、`test_fp_emp_3_applicant_list_reuses_teammate_route` |
| FP-SEC-1 | 所有权检查在 `service._load_owned_job`、`service.change_application_status` | `test_fp_emp_2_other_employer_cannot_edit_or_delete`、`test_fp_emp_3_other_employer_and_candidate_cannot_change`、`test_fp_emp_1_patch_only_affects_own_company` |
| FP-SEC-2 | `service.py` 全部使用 ORM 绑定参数 | `test_fp_sec_2_job_title_sql_metacharacters_are_bound` |

测试命令：`python -m pytest -c pytest.employer.ini -q`（仓库根目录 `app/`）。

## 7. 前端

组员的 `frontend/candidate/src/api/common_api.ts` 不支持 `PATCH` 方法，也不处理 204 空响应。雇主页面接入时需要：

- 为 `PATCH /employer/company`、`PATCH /employer/jobs/{job_id}`、`PATCH /employer/applications/{application_id}/status` 增加 PATCH 支持；
- 处理 `DELETE /employer/jobs/{job_id}` 的 204 空 body；
- 职位技能表单可复用组员的 `SkillTagPicker`。
