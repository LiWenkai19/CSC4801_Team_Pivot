# start.bat 本地开发账号

运行 `start.bat` 后，在 <http://127.0.0.1:5173/> 使用以下账号登录。凭据仅用于本地开发。

| 角色 | 邮箱 | 初始密码 |
| --- | --- | --- |
| 候选人 | `local-candidate@example.com` | `dev-local-only` |
| 雇主 | `local-employer@example.com` | `dev-local-only` |

## 启动行为

- 启动时按邮箱检查数据库。缺哪个就创建哪个，已有账号继续使用当前密码和资料。
- 新账号首次登录后可填写角色资料。按 `Ctrl+C` 停止前后端，账号及关联数据保留在数据库中。
- 旧版临时邮箱为 `dev-candidate@example.com` 和 `dev-employer@example.com`，新启动流程使用上表的邮箱，原有的临时账号可以留在库里。

## 环境

准备已执行迁移的本地数据库，在 `backend/.env` 或环境变量中配置连接。使用项目 Python 环境，安装前端依赖后确保后端端口 `8000` 和前端端口 `5173` 空闲。 [启动脚本](../backend/scripts/dev_start.py)

需要完整的公司、职位、申请与面试时段样例时，可以在专用演示库运行 `seed_demo.py`。它会清空该库的业务表并加载另一套样例。 [演示数据脚本](../backend/scripts/seed_demo.py)
