# 后端指令

本文件适用于 `backend/` 及其子目录，与项目根目录 `AGENTS.md` 的通用约定共同使用。技术经验按当前实现和需求适用，不作为新增业务模块的授权。

## Python 环境与依赖

- 使用当前项目指定的 Python / Conda / 虚拟环境，不复用其他项目的环境名称。
- 执行后端命令前，确认解释器与依赖版本兼容。遇到模型导入或类型注解异常时，先排查 Python、SQLModel 及相关依赖的兼容性。
- 若项目使用 `pyproject.toml` 和开发依赖组，可在后端目录执行 `pip install -e ".[dev]"`。

## 后端分层

按业务功能组织模块，例如 `app/<feature>/`：

| 文件 | 职责 |
| --- | --- |
| `model.py` | SQLModel 数据库表及关系 |
| `schema.py` | 请求与响应的数据结构 |
| `service.py` | 数据库操作与业务规则 |
| `router.py` | API 路由、依赖注入与 HTTP 错误转换 |
| `security.py` | 项目需要时，集中处理密码与 Token 相关工具 |

- 数据库 Session 通过统一的依赖（例如 `get_db`）提供。
- 采用原文的错误处理约定时，service 使用 `ValueError` 表达业务错误，由 router 转换为 `HTTPException` 和对应状态码；不要在 service 中混入 HTTP 层逻辑。
- 新项目已有其他错误类型或分层约定时，遵循其现有设计。

## 数据库迁移

- Alembic 的数据库地址来源取决于 `env.py` 的实现；先确认它读取应用 Settings 还是 `alembic.ini`。
- 使用 SQLModel 时，将 `SQLModel.metadata` 配置为自动生成迁移的目标元数据。
- 新增数据库表后，确保模型被迁移环境导入并注册到元数据，否则自动生成可能无法发现新表。
- PostgreSQL 的枚举（Enum）是独立的数据库类型，autogenerate 处理不好，遇到过两类问题：
  - **多张表共用同一个枚举**：autogenerate 会给每张表各写一个 `sa.Enum(...)`，`CREATE TYPE` 被执行多次，`upgrade` 在第二张表报 `DuplicateObject: 类型 "xxx" 已经存在`。需手动改用 `postgresql.ENUM(..., create_type=False)`（`create_type=False` 只有 PG 方言认，写在通用 `sa.Enum` 上会被静默忽略），手动 `enum.create(op.get_bind(), checkfirst=True)` 建一次，各列复用同一个 enum 对象；downgrade 在删完所有表后再 `sa.Enum(name='xxx').drop(op.get_bind(), checkfirst=True)`。
  - **向已有枚举新增取值**：autogenerate 检测不到枚举值变化，不会生成任何语句，需手写 `op.execute("ALTER TYPE xxx ADD VALUE 'new_value'")`；PG 不支持删除枚举值，downgrade 通常留空（要真正回滚只能重建类型）。

```sh
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

## 配置管理

- 使用 `pydantic-settings` 的 Settings 类集中读取配置；按实际设置加载 `.env`。
- 无默认值的必填配置缺失会导致 Settings 初始化失败。启动前核对必填项和环境文件的加载位置。
- 常见配置包括应用名称、数据库地址，以及会话有效期与 Cookie 相关配置（见 `app/core/config.py`，均有默认值）。
- 管理员初始化、业务文件目录等配置根据新项目需求定义，不沿用旧项目的必填项清单。

## 登录相关技术经验

- 认证采用**服务端会话 + HttpOnly Cookie + CSRF 令牌**，不使用 JWT。
- 密码用 `pwdlib` / Argon2；会话 ID 是 256 位随机串，`user_session.token_hash` 只存其 SHA-256，原文只存在于浏览器 Cookie。
- 需要登录的路由依赖 `get_current_user` 或 `require_candidate` / `require_employer`：它们同时完成会话校验和写请求（POST/PUT/PATCH/DELETE）的 `X-CSRF-Token` 校验；新路由不要绕过它们自己读 Cookie。
- 认证只发一次 SQL：`UserSession.user` 配置为 joined 内连接，会话与账户一起加载。候选人推荐接口的查询数测试依赖这一点。
- GET 接口必须无副作用（`SameSite=Lax` 允许跨站顶级导航 GET 携带 Cookie）。
- 改密码、禁用账号时调用 `revoke_all_sessions` 让该用户所有会话失效；删除用户时数据库级联删除其会话。
- 前端统一请求 `/api/...`，由 Vite 代理去掉前缀后转发到后端（同源，Cookie 无跨源问题）；后端路由本身不带 `/api`。
- 测试中用 `{"Cookie": "session=...", "X-CSRF-Token": ...}` 作为认证头，并清空 TestClient 的 Cookie 罐，避免多账户串号（见各模块 `conftest.py`）。
- 部署到 HTTPS 时必须设置 `COOKIE_SECURE=true`。

## 后端开发与检查命令

以下为相同工具链下的示例；入口路径与 npm 脚本需核对新项目配置。

```sh
fastapi dev app/main.py
# 或
uvicorn app.main:app --reload
ruff check .
pytest
pytest path/to/test_file.py::test_name
```
