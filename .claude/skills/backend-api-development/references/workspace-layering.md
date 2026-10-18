# 工作区分层参考

提取来源：SYManage_proj 的 `AGENT.md`、`CLAUDE.md` 及 `backend/app/` 实现，核对日期为 2026-10-06。此文件保存稳定组织方式，执行任务时仍须读取当前工作区，不能将本项目环境名、权限或旧阶段限制套用到其他项目。

## 业务目录与公共能力

```text
backend/
  app/
    main.py                 # 应用装配、路由注册、生命周期
    dependencies.py         # 通用权限依赖
    core/config.py          # Settings 配置
    db/session.py           # engine、get_db
    users/
      model.py
      schema.py
      service.py
      router.py
      security.py
    finance/
      model.py
      schema.py
      service.py
      router.py
      invoice_parser.py     # 发票解析专用能力
      gen_r11t_form.py       # 表单生成专用能力
  alembic/
  pyproject.toml
```

新接口沿用这种业务模块划分，不另建全局 models/schemas/services 三套目录；`PROGRESS.md` 按 Skill 要求放在实际开发的业务目录内。

## 调用边界

- `router.py` 使用 APIRouter、response_model、Depends，将 `get_db` 提供的 Session 和可信当前用户传给 service。
- `service.py` 使用 SQLModel/SQLAlchemy 查询和事务；业务失败通常抛 `ValueError`，router 转换为 HTTP 错误。现有不少路由将业务错误统一返回 400；新接口应明确错误契约，不擅自改变其他接口的状态码。
- `schema.py` 的 DTO 与 `model.py` 的持久化表各司其职，响应显式限制字段。
- `app/dependencies.py` 已有 `require_permissions`、`require_admin`、`require_finance_manager` 等；复用适用依赖，具体允许角色以当前代码和需求为准。
- `users/security.py` 集中处理密码哈希、Token 签发与解析；当前实现使用 pwdlib/Argon2、PyJWT。
- 当前用户权限来自 `user.whitelist.permission`，不要假设 `User` 表有独立 permission 字段；JWT 当前以邮箱作为 `sub`。

## 旧实现与严格分层的差异

当前 `users/service.py` 中的 `get_current_user` 同时承担 FastAPI 认证依赖和 HTTP 错误处理；部分 service 也接收 UploadFile。这些是已有实现，不是允许新业务函数继续混层的依据。

新增通用认证依赖优先归入统一依赖层；新的业务 service 使用纯业务参数或文件内容/路径。复用现有依赖时不要无端迁移所有调用方；确需调整时限定在当前接口必要范围，检查导入循环并跑受影响回归测试。

## 环境与验证注意事项

- `backend/pyproject.toml` 定义依赖和 dev extras，当前 dev 包含 pytest、ruff；检查当前项目环境再运行，不依赖系统 Python 恰好可用。
- `CLAUDE.md` 指定本项目使用 Conda `SYManage`，其他项目不得沿用这个名字。可通过 `conda run -n SYManage python ...` 在后端目录运行，执行前核对解释器与依赖。
- 当前文件扫描未发现正式 pytest 测试目录；`seed_test_data.py`、`check_test_data.py` 不等同于接口自动化测试，不直接运行它们代替验证。
- `db/session.py` 在导入时依据 Settings 创建 PostgreSQL engine；`main.py` lifespan 初始化目录及超级管理员。测试必须先注入隔离配置并隔离初始化，不能先导入真实应用再只替换一处 Session 就认为安全。
- `get_db` 是生成器依赖，用 FastAPI dependency_overrides 接入隔离 Session 时，测试后恢复 overrides 并清理测试数据。
- 迁移配置与模型注册读取当前 `alembic/env.py` 核对；不要展示 `.env` 中真实密钥或数据库凭据。
- 根级 `CLAUDE.md` 和 `.claude/current-phase.md` 的阶段记录可能落后于当前代码；以本轮用户授权、当前规范和实际实现判定范围，不把旧路线图直接当作本轮授权。
