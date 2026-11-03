# 给 main 维护者：合并 employer 与 candidate 两个分支

本文说明如何把 `employer-main-merge`（雇主）与组员的 candidate 分支合并进 main。两个分支都已包含候选人提交 68a1dfe，雇主分支在其基础上新增雇主模块。

## 1. 雇主分支改动范围

| 文件 | 改动 |
| --- | --- |
| `backend/app/main.py` | 新增 `from app.employer.router import employer_router` 和 `app.include_router(employer_router)`，共两处，其余不动 |
| `backend/app/employer/**` | 雇主模块（新增） |
| `backend/alembic/versions/employer_002_create_employer_and_shared_tables.py` | 新迁移，接在 `e07644577837` 之后 |
| `backend/employer_tests/**`、`pytest.employer.ini` | 雇主测试（新增） |
| `scripts/check_employer_ownership.py` | 雇主归属检查，基线为 68a1dfe |
| `docs/EMPLOYER_*.md` | 雇主文档 |

已删除 `backend/app/employer_main.py` 与 `backend/app/employer/database/`（独立迁移链）。前者已并入 `main.py`，后者依赖组员已删除的模块。

## 2. main.py 合并方式

候选人分支在 `main.py` 里改了账户路由、`candidate_router` 和 `get_safe_db` 覆盖，雇主分支只在 `candidate_router` 之后多加两处。两边改的是相邻位置，如果 Git 报冲突，保留双方的行即可，最终应同时包含：

```python
from app.candidate.router import router as candidate_router
from app.employer.router import employer_router
...
app.include_router(candidate_router)
app.include_router(employer_router)
```

## 3. ORM 以雇主为准

`job` 这张表有两个 ORM 类映射：

- 雇主：`app.employer.model.Job`，含 `company_id`（非空）、`created_at`、`updated_at`。
- 候选人：`app.candidate.model.Job`，没有这三列。

约定：**建表以雇主定义为准**，即 `employer_002` 创建的 `job`。候选人类读取没有问题，但它写入时不会提供 `company_id`，在迁移建出的库上会因非空约束失败。组员的种子数据与测试夹具如果直接插入 `Job`，需要补 `company_id`，或改为调用 `POST /employer/jobs`。`JobSkill` 两边列名一致，可共用。

雇主模块不 import 候选人的 `Job`，只通过 `app/employer/adapters.py` 使用候选人的 `Company`、`Application`、`ApplicationStatus`、`InterviewSlot`、`Booking`。候选人这些模型改字段时，只需同步 `employer_002` 与该文件。

## 4. 建库：只用 alembic

```sh
cd backend
alembic upgrade head
```

`employer_002` 一次建出雇主表（`job`、`job_skill`、`employer_company`）和共享表（`company`、`application`、`interview_slot`、`booking`），并补上团队模型新增而初始迁移缺少的 `user.updated_at`、`candidate_profile.updated_at`（归属组员，已在文件中标注）。

注意：

- `app.db.session.init_shared_schema()`（`create_all`）建出的 `job` 没有雇主的列，**不要与 alembic 混用**。当前没有任何调用者，建议在合并后删除或标注废弃。
- 迁移没有回滚，`downgrade()` 会抛 `RuntimeError`，与组员迁移风格一致。
- 若 candidate 分支仍带有 `candidate_flow_001` 之类也会建 `job`、`application` 的迁移，会与 `employer_002` 重复建表且出现双头，合并前必须去掉。68a1dfe 已删除，所以现在不存在这个问题，但请在合并时确认。

## 5. 其他可能的问题

1. 公司名称来源：候选人侧显示 `employer_profile.company_name`，雇主以 `company.name` 为准，两处可能不一致。
2. `db/session.py` 的 `engine` 仍是 `echo=True`，会打印 SQL 参数；`main.py` 已用 `get_safe_db` 覆盖，但直接使用 `engine` 的脚本仍有风险。
3. 逻辑外键：`job.company_id`、`job.employer_id`、`employer_company` 的两列不建数据库外键，由 service 校验。申请侧可调用 `app.employer.service.ensure_active_job()`。
4. 删除职位是软删除（`is_deleted`），有申请或面试时段返回 409。候选人侧列表和申请需继续按 `is_deleted` 过滤。
5. 在 SQLite 上要开启 `PRAGMA foreign_keys=ON` 才能验证外键；PostgreSQL 不受影响。
6. PostgreSQL 只做过离线 DDL 审查，没有真实库的执行证据。
7. 两个归属脚本（`check_candidate_ownership.py`、`check_employer_ownership.py`）在 main 上基线已不适用，是否退役由团队决定。

## 6. 合并后建议验证

```sh
python -m pytest -c pytest.employer.ini -q
python -m pytest backend/tests -q
cd backend && alembic upgrade head --sql
```

合并方式建议用普通 merge commit，不要 squash，以保留双方提交署名。
