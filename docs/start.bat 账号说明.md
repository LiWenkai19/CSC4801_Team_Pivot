# start.bat 提供的账号密码说明

## 结论：密码不固定，只在启动窗口的控制台里

`start.bat` 本身不包含、也不打印任何账号密码。它的调用链是：

```
start.bat  →  backend/scripts/dev_start.py  →  启动后端(8000) + 前端(5173)
```

账号由 [backend/scripts/dev_start.py](../backend/scripts/dev_start.py) 在**每次启动时**创建，密码当场随机生成，**不写入任何文件**，只打印到运行 `start.bat` 的那个控制台窗口。

## 账号从哪里来

定义位置：[backend/scripts/dev_start.py](../backend/scripts/dev_start.py)

| 项 | 内容 | 位置 |
| --- | --- | --- |
| 候选人邮箱 | `dev-candidate@example.com` | 常量 `CANDIDATE_EMAIL` |
| 雇主邮箱 | `dev-employer@example.com` | 常量 `EMPLOYER_EMAIL` |
| 密码 | 每次启动随机生成：`secrets.token_urlsafe(18)` | 创建账号的 `accounts` 元组 |
| 角色 | 一个 Candidate、一个 Employer | 同上 |

也就是说：**邮箱是固定的，密码每次启动都不同**，仓库里搜不到任何一次的具体密码值。

## 在哪里看到密码

启动成功后，`start.bat` 所在的控制台窗口会打印类似内容：

```
Temporary accounts (valid only while this window is running):
  Candidate: dev-candidate@example.com / <本次随机密码>
  Employer: dev-employer@example.com / <本次随机密码>
Frontend: http://127.0.0.1:5173/
Press Ctrl+C here to stop both servers and remove the accounts.
```

登录地址为 <http://127.0.0.1:5173/>，把窗口里打印的邮箱 / 密码填入登录页即可。

## 账号的生命周期

- **只在本次启动窗口运行期间有效**（脚本原文即此约定）。
- 在该窗口按 `Ctrl+C` 正常退出时，脚本会自动删除这两个账号及其候选人/雇主资料。
- 强制结束进程或断电**不会**执行清理；若发生这种情况，下次启动会因"账号已存在"而拒绝启动，并提示遗留账号 ID，需手动在数据库中删除（含 `candidate_profile` / `candidate_skill` / `employer_profile` / `user` 相关行）。

## 启动前置条件（脚本会检查）

1. `backend/.env` 存在，或已设置 `DATABASE_URL`。
2. Python 环境可用（优先用 `CONDA_PREFIX` 或 `SYManage` 环境的解释器）。
3. `frontend/node_modules` 已安装（`npm install`）。
4. 端口 8000、5173 均空闲；被占用时**不会创建任何账号**。
5. 两个 dev 邮箱在库中尚不存在；已存在则直接报错退出，不动已有账号。

## 与 seed_demo.py 演示账号的区别

[backend/scripts/seed_demo.py](../backend/scripts/seed_demo.py) 是另一套独立的**本地演示数据**脚本，与 `start.bat` 无关：

| | start.bat / dev_start.py | seed_demo.py |
| --- | --- | --- |
| 密码 | 每次随机，只在控制台 | 固定 `demo-local-only`（仅限本地演示） |
| 数据 | 只建两个空账号 | 清空业务表后重建完整演示数据 |
| 清理 | 正常退出自动删号 | 不自动清理，重复执行会重建数据 |

需要带公司、职位、申请、面试时段的完整演示环境时，才用 `seed_demo.py`；日常联调登录用 `start.bat` 打印的临时账号即可。
