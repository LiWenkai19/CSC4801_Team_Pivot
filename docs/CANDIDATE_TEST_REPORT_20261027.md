# Candidate Flow 当前版本测试报告

日期：2026-10-27（Asia/Shanghai）。分支：`candidate`；业务代码基于当前提交 `c2667bd7805a6f779c6cf90e32aa3b40bc95bdfc`，包含追加的独立 Booking 迁移。本轮只新增/适配测试与文档，没有修改业务实现或队友文件；修订尚未提交、推送。

## 结论与最终结果

当前可执行范围的测试均通过。未排除问题文件的全仓库仍有既有收集错误，真实 PostgreSQL 并发测试因环境缺失跳过；不能将下表表述为全仓库和所有团队界面无条件全部验收通过。

| 检查 | 结果 | 范围 |
| --- | --- | --- |
| 最终联合后端回归 | **294 passed，1 skipped**，35.89秒 | 除已知schema收集错误文件外的全部仓库测试；包含候选人227项和原账号/参考单元67项 |
| 候选人检查入口 | 通过，退出码0 | `scripts/check_candidate.py`：归属、pip check、Ruff、候选人后端220项通过/1跳过、前端构建/lint/单测；之后追加的7项Booking用例在最终联合回归中通过 |
| 原账号与仓库参考单元测试 | **67 passed** | `backend/tests/users/test_account_responses.py` 与 `tests/unit`，另行独立运行也通过；已包含在294中，不重复计数 |
| 前端单元测试 | **4 passed，2 files** | 纯文本安全渲染、技能目录和规范化 |
| Chromium真实端到端 | **10 passed**，22.8秒 | 实际Vite、FastAPI、迁移后的临时SQLite；不是整套mock接口 |
| TypeScript/Vite构建、Oxlint | 通过 | 候选人独立前端 |
| Ruff、pip check | 通过 | 候选人代码/测试/脚本，Python依赖一致性 |
| 预览smoke | 通过 | 临时建库、迁移、种子数据、两项服务启动并自动停止 |
| 文件归属 | 通过 | 88个团队原文件SHA-256未变 |

## 针对功能的覆盖

| 功能 | 本轮及既有用例覆盖 |
| --- | --- |
| CAN-001 简历权限 | 本人读改、其他候选人禁止、雇主只读自己职位的申请人、越权不落库、失效身份、非法ID、伪造归属、申请移除及职位归属变化 |
| CAN-002 重复申请 | 四种申请状态均拒绝重复，保留原状态/记录，数据库唯一约束兜底，不同候选人/职位独立；真实第二客户端提交后旧页面收到409并持续显示中文反馈 |
| CAN-003 状态/面试 | 双方读取同一状态及预约，状态变化后预约仍保留；跨角色/职位拒绝；浏览器真实第二客户端抢占后冲突恢复、刷新后仍显示预约 |
| CAN-004 查询授权 | 8个业务GET接口的匿名/伪造令牌/本人/其他候选人/所属雇主/无关雇主矩阵；非法与缺失ID；已有认证测试覆盖过期令牌和不存在账号 |
| CAN-005 技能标签 | j建议Java/JavaScript、键盘选择、去重且两语言不混同、自定义、特殊字符、真实保存与刷新、移除/清空、未确认输入阻止写入、HTML不执行、输入法确认不误选、390px无横向溢出 |
| CAN-006 推荐占位 | score=0及placeholder标记、隐藏职位/已申请标记、稳定同分排序、注入可控评分检验降序及同分规则、首次保存后进入推荐、界面占位说明 |
| 独立数据库及Booking | 迁移、约束、触发器、外键、模型差异、离线PG DDL；新增7项验证Booking跨连接持久化、UTC时间、application/slot各自唯一、孤立外键拒绝、已引用申请/时段删除保护 |

新增及适配的样例：

- [test_feature_acceptance.py](../backend/tests/candidate/test_feature_acceptance.py)：65项功能和权限场景。
- [test_owned_database.py](../backend/tests/candidate/test_owned_database.py)：追加7项Booking关系、持久化与完整性场景。
- [test_resume_access.py](../backend/tests/candidate/test_resume_access.py)：已有简历关系授权回归。
- [test_candidate_flow.py](../backend/tests/candidate/test_candidate_flow.py)、[test_candidate_integration.py](../backend/tests/candidate/test_candidate_integration.py)：按当前占位需求适配。
- [features.spec.ts](../frontend/candidate/e2e/features.spec.ts)：新增4项真实浏览器验收。
- [candidate.spec.ts](../frontend/candidate/e2e/candidate.spec.ts)：适配原6项完整流程。
- [skillCatalog.test.ts](../frontend/candidate/src/components/skills/skillCatalog.test.ts)：新增3项单测，另有既有纯文本安全渲染1项。

## 初始失败与处理

初始后端结果为152通过、3失败、1跳过：旧测试仍期待真实技能交集分数，已改为用户确认的0分占位、placeholder和稳定排序。另注入可控不同分数验证真实降序逻辑，避免因全为0而漏掉排序错误。旧浏览器技能行定位及首次保存后的页面预期也已适配。

新增预约一致性用例起初比较UTC时间原始字符串；候选人typed响应使用`Z`，雇主响应使用`+00:00`，表示同一时刻。改用BookingPublic规范化后比较预约，不为满足字符串断言而修改业务。

新增原生校验用例起初尝试点击被正常展开的下拉覆盖的保存按钮而超时；改为先Escape关闭菜单，再检查未确认输入确实阻止请求，随后完成自定义并保存。未用强制点击绕过真实交互。

没有因这些测试而更改业务源码。旧技能交集函数的历史单测仍可运行，但不证明当前推荐服务调用了旧算法。

## 限制和未完成验证

1. **全仓库既有收集错误**：`backend/tests/users/test_schema.py` 导入 `app.users.schema.CandidateProfileUpdate` 失败。该测试及schema与团队基线一致，按文件归属规范未修改。直接全量收集仍返回非零；最终294通过是明确排除该文件后的结果，需对应所有者修正导入契约。
2. **真实PostgreSQL并发**：`test_postgres_atomic_booking_and_duplicate_application` 因没有专用 `PIVOT_TEST_DATABASE_URL` 跳过。Docker Desktop Linux引擎管道不存在，无法使用当前Docker启动专用库；未使用个人业务数据库凭据。SQLite唯一约束和真实第二客户端的顺序抢占，不等同于PostgreSQL同时提交/行锁验证。PG离线DDL通过也不等同于实际PG迁移通过。
3. **团队接入与算法**：雇主正式页面和职位保存服务仍待所有者接入；本轮通过API验证雇主权限，不声称未接入页面已验收。真实评分算法仍待开发，只验证占位契约及排序基础。
4. **环境与告警**：未运行远程CI、Docker镜像或生产部署验收。已有Starlette/httpx弃用警告，不影响本轮结果。Windows沙箱内异步网络曾挂起，本轮经执行授权在沙箱外运行隔离测试；测试和浏览器只使用临时、虚构数据。

## 复现命令

仓库根目录：

```powershell
.\.venv\Scripts\python.exe scripts/check_candidate.py
.\.venv\Scripts\python.exe -m pytest backend/tests/users/test_account_responses.py tests/unit -q
.\.venv\Scripts\python.exe -m pytest -q --ignore=backend/tests/users/test_schema.py
.\.venv\Scripts\python.exe scripts/preview_candidate.py --smoke
```

浏览器：

```powershell
Set-Location frontend/candidate
$env:PLAYWRIGHT_BROWSERS_PATH = 'C:/Users/沿途南行/AppData/Local/ms-playwright'
npm.cmd run test:e2e -- --reporter=line
```

浏览器路径需替换为执行者实际安装位置；测试自动启动服务，不复用已占用的5173/18019端口。
