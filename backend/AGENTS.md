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
- 常见配置包括应用名称、数据库地址；使用 JWT 时还包括密钥、算法和 Token 有效期。
- 管理员初始化、业务文件目录等配置根据新项目需求定义，不沿用旧项目的必填项清单。

## 登录相关技术经验

- 使用同类方案时，可通过 `pwdlib` / Argon2 处理密码哈希，通过 PyJWT 签发与解析 JWT。
- JWT 的 `sub` 用于标识账号，具体使用邮箱或其他标识由新项目确定；签发与解析两端应保持一致。
- JSON 登录接口与 OAuth2 密码表单接口使用不同的请求格式；若保留表单接口，`OAuth2PasswordBearer` 的 `tokenUrl` 应指向实际接口。
- FastAPI 的依赖注入可用于读取 Token 并加载当前用户，具体身份与权限模型按新项目需求设计。

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
