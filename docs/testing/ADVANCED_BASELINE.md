# 高级测试基线（P0）

测量时间：2026-11-26（Asia/Shanghai）

| 项 | 值 |
| --- | --- |
| 基线 commit（测量时 HEAD） | `1b3c4b4361d3b2264ec597bca3b5b5713f8ee401` |
| Python（本机运行） | 3.14.4 |
| Python（干净 venv 依赖验证） | 3.12.0 |
| Node | v24.15.0 |
| PostgreSQL | 15.20（`127.0.0.1` 临时集群；CI service 为 `postgres:15`） |
| pytest | 8.4.2 |
| hypothesis | 6.170.17 |
| z3-solver | 5.4.1.0 |
| mutmut | 3.7.0 |
| schemathesis | 4.34.2 |
| pytest-cov | 7.1.0 |
| coverage | 7.17.5 |

## 必测套件

| 命令 | 用例 | 通过 | 失败 | pytest 耗时 | 命令总耗时 | 退出码 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `python tests/run_tests.py` | 198 | 198 | 0 | 2.53s | 5.35s | 0 |

## 真实 PostgreSQL 集成套件

| 命令 | 用例 | 通过 | 失败 | pytest 耗时 | 命令总耗时 | 退出码 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `python tests/run_tests.py --integration` | 241 | 241 | 0 | 52.56s | 55.36s | 0 |

## 高级骨架

| 命令 | 模式数 | 用例 | 通过 | 失败 | 模式耗时 | 命令总耗时 | 退出码 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `python tests/advanced/run.py smoke` | 1 | 2 | 2 | 0 | 4.169s | 7.49s | 0 |
| `python tests/advanced/run.py fast` | 1 | 2 | 2 | 0 | 3.979s | 7.29s | 0 |

## 运行器检查

| 检查 | 数值 | 退出码 |
| --- | ---: | ---: |
| `run.py list` 发现模式数（仅 `smoke`） | 1 | 0 |
| 临时目录 `zz_tmp/test_x.py` 被发现 | 1 | 0 |
| 临时模式 `zz_tmp`（无 `NEEDS_DB`、无 PG）通过 | 1 | 0 |
| `SLOW` 模式 `zz_slow` 在 `fast` 中被请求 | 0 | 0 |
| `SLOW` 模式 `zz_slow` 在 `all` 中运行 | 1 | 0 |
| 使用外部 `ADVANCED_PG_URL` 运行 `smoke` | 1 模式 / 2 passed | 0 |
| 非 loopback `ADVANCED_PG_URL` 被拒绝 | 0 个模式运行 | 2 |
| 非 loopback URL 中的密码出现在产物中 | 0 次 | - |
| `--out tests/advanced/zz_out` 被拒绝 | 0 个目录创建 | 2 |
| 故意把 `user` 表名改错 | 1 failed / 1 passed | 1 |
| 故意把 `/users/me` 期望 200 改为 201 | 1 failed / 1 passed | 1 |
| 恢复后 `run.py smoke` | 2 passed | 0 |

## 干净 Python 3.12 依赖安装

| 项 | 值 |
| --- | ---: |
| `pip install -r requirements.txt -r tests/advanced/requirements.txt` | 0（安装成功） |
| 安装包数 | 91 |
| 冲突数 | 0 |
