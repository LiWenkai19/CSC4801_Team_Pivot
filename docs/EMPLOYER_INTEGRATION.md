# 雇主模块接入说明（合并版）

本文件面向组员和 main 维护者。合并步骤与 ORM 约定见 `EMPLOYER_MERGE_GUIDE.md`。

## 1. 入口

`backend/app/main.py` 已挂载 `employer_router`（紧跟 `candidate_router`）。独立入口 `employer_main.py` 已删除。

## 2. 建库

只用团队 alembic 链，在 `backend/` 目录执行：

```sh
alembic upgrade head
```

`employer_002` 接在 `e07644577837` 之后，建出 company、job、job_skill、employer_company、application、interview_slot、booking，并补上 `user.updated_at`、`candidate_profile.updated_at`。不要与 `init_shared_schema()` 混用。

## 3. 需要组员注意

- 组员的 `Job` 类与雇主的 `Job` 映射同一张表，组员那一侧没有 `company_id`、`created_at`、`updated_at`；在迁移建出的库上直接插入职位会因 `company_id` 非空而失败，需补字段或改用 `POST /employer/jobs`。
- 公司名称：候选人侧读 `employer_profile.company_name`，雇主以 `company.name` 为准。
- 删除职位为软删除；候选人侧需继续按 `is_deleted` 过滤。
- 逻辑外键校验函数：`app.employer.service.ensure_active_job()`。
- 申请人列表继续使用组员的 `GET /employer/jobs/{job_id}/applications`。

## 4. 测试

```sh
python -m pytest -c pytest.employer.ini -q
```

## 5. 前端

`common_api.ts` 不支持 PATCH，也不处理 204 空响应；职位技能表单可复用 `SkillTagPicker`。
