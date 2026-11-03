# 共享数据库与候选人模型

候选人和雇主应用共用 `DATABASE_URL` 指向的数据库。账号模型位于 `backend/app/users/model.py`，候选人业务模型位于 `backend/app/candidate/model.py`；小数据库及候选人独立迁移已移除。

新数据库在 `backend` 目录设置应用配置和专用 `DATABASE_URL` 后，可以运行：

```powershell
..\.venv\Scripts\python.exe -c "from app.db.session import init_shared_schema; init_shared_schema()"
```

该命令只创建尚不存在的表，不会修改已有表或删除数据。对已经存在旧结构的数据库，它不会补列或约束；此前数据库如果记录了已删除的 candidate 迁移版本，现有 Alembic 版本记录也需要单独处理。此操作未在实际团队数据库或 PostgreSQL 上执行。

数据库层对候选人职位申请和预约设有唯一约束，对面试时段设有30分钟约束。`updated_at` 由 ORM 更新时维护，直接 SQL 更新不保证自动更新。Company 表尚未与雇主关联。
