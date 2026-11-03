# Candidate flow 对抗性测试记录（2026-10-29）

本轮针对 `CSC4801_Team_Pivot_clean_20261024` 当前工作区（含已有未提交修复），使用独立入口 `app.candidate_main:app`。仅新增诊断与本报告，没有修改业务源码、既有测试或队友文件，没有连接业务数据库。当前权限以功能台账为准：已投递职位的所属雇主可读候选人简历，评分明确为占位；这两项不作为缺陷报告。

## 结论与实际执行

- 既有候选人回归：**232 passed、1 skipped**，22.76 秒。跳过的是真实 PostgreSQL 测试，不能视为并发验收。
- 新增后端诊断：**8 passed**，1.96 秒，使用隔离 SQLite、真实 API、真实约束与查询计数。
- 新增浏览器诊断：**1 passed**，14.7 秒，临时 SQLite + 本地前后端 + 全新无头 Edge 上下文；只对第二个标签页的 `/users/me` 注入 503。
- **诊断通过表示成功复现当前缺陷/边界，不表示代码已修好。** 文件不加入默认回归发现范围。
- Ruff 通过；归属检查确认 88 个团队原文件不变。启动时另保存全部 195 个既有 Git 可见文件的 SHA-256，收尾核对无变化。

## 确认的问题

### ADV-01 / P2：临时服务错误导致全标签页会话丢失

位置：`frontend/candidate/src/contexts/AuthContext.tsx:55-56`，启动恢复身份的 catch 对任何错误执行 `clearSession()`；后者在第 41 行删除共享 token。

复现：标签页 A 正常登录 Alice；标签页 B 打开候选人页面，令 B 的 `/users/me` 返回 503。B 删除 localStorage token，A 接收 storage 事件后也回到登录页。原 token 直接访问正常服务的 `/users/me` 仍为 **200**，证明其身份未失效。浏览器断网、连接错误也会进入同一 catch，但本轮动态注入的是 503。

影响：单页恢复登录遇到短暂故障会使其他正常页面也退出，正在编辑的未保存表单可能丢失。不是跨账号越权。

建议：区分认证失效与可重试故障；只有确定的认证失败清除共享会话，503/网络错误保留 token 并展示重试。恢复失败时仍不得直接展示未经确认的私有页面。候选人自有 AuthContext 可修复。

### ADV-02 / P2：特殊文本绕过校验，保存接口返回 500

位置：`backend/app/candidate/profile_schema.py:25,41`；`backend/app/candidate/service.py:122`。候选人 schema 未限制这些字符，继承的创建服务也未转换相应错误。

真实请求及结果：

| 请求 | 输入片段（JSON 转义） | 结果 |
| --- | --- | --- |
| PATCH 本人资料 | `{"skills":["\u0000"]}` | 500 |
| POST 首次候选人资料 | `{"display_name":"Audit","skills":["\u0000"]}` | 500 |
| PATCH 本人资料 | `{"resume_text":"\ud800"}` | 500 |
| PATCH 本人资料 | `{"display_name":"\ud800"}` | 500 |
| PATCH 本人资料 | `{"skills":["\ud800"]}` | 500 |

根因：NUL 技能经 Python strip/lower 后仍非空，但 SQLite 的 length 对起始 NUL 给出零，触发现有技能 CHECK 约束；孤立 UTF-16 代理项可经 JSON 转义输入，之后在数据库 UTF-8 编码阶段失败。应在进入持久化前拒绝此类文本并返回可解释的 4xx。

影响与边界：已认证用户可用很小的请求稳定触发服务器错误。本轮所有 PATCH 失败后资料与原值一致，首次保存失败后 `profile_completed` 仍为 false，**未观察到部分写入或其他用户数据损坏**。没有据此声称能使整个服务不可用。动态结论限于本轮 SQLite 环境；未在 PostgreSQL 重测。

建议：在候选人自有创建/更新 schema 中统一验证合法 Unicode 标量及 NUL，保证字段值在数据库可存储范围内；对字段类型错误仍保留现有 422。不要把所有数据库异常统统吞成“无效输入”。

### ADV-03 / P2：OAuth 表单登录未规范化邮箱域名，合法凭据被拒绝

位置：`backend/app/candidate/accounts.py:50-52` 直接将 OAuth2 表单交给团队 handler；该 handler 使用原始 username 查询，而 JSON 登录经过 EmailStr 规范化。

复现（同一账号与正确密码）：

| 接口与邮箱 | 状态码 |
| --- | --- |
| `/users/token`，`user0@example.com` | 200 |
| `/users/login`，`user0@EXAMPLE.COM` | 200 |
| `/users/token`，`user0@EXAMPLE.COM` | **401** |

影响：Swagger/OAuth 客户端使用大小写不同的域名时误报密码错误，行为与网页 JSON 登录不一致。只针对域名大小写，不建议粗暴把邮箱本地部分全部转小写。

建议：在候选人包装层复用与 JSON 登录一致的邮箱校验/规范化，再调用已有认证逻辑；团队 users 文件保持原样，由所有者决定是否统一修复。

### ADV-04 / P2：我的申请列表仍有 N+1 查询

位置：`backend/app/candidate/router.py:189-206` 逐条调用 `service.application_public`；`backend/app/candidate/service.py:322` 逐申请读取职位、公司、预约。

复现：监听 `/candidate/applications` 一次请求内所有 SQL。本人 1 条申请时 **5 次查询**；加入 20 个不同职位、对应本人申请后，21 条申请产生 **65 次查询**。新增职位均属于同一个雇主，仍额外产生 60 次查询。

影响：申请数量增长使列表数据库开销线性放大；接口一次返回全部申请。这是查询数量测量，不是压力测试，也没有证明已经造成拒绝服务。此前推荐列表的批量查询修复没有覆盖此接口。

建议：一次加载申请，再批量读取所需职位、雇主、预约、时段并组装响应；保留现有授权与排序。是否分页需结合产品需求，不作为本次必要修复前提。

## 已观察但不列为明确 bug 的业务边界

同一候选人在两个雇主处、两条 Interviewing 申请上预约完全相同的 30 分钟，两个 POST 都返回 **201**。现有检查只避免同一申请重复预约或同一 slot 重复占用，不检查候选人跨申请时间重叠。

现有 FP-SCHED-2 对资格的列举没有禁止这种跨申请重叠，因此这是需要产品决策的边界，而非已确认违反当前约定。若新增“本人不可撞期”规则，查询过滤和事务内校验均需实现，并考虑并发提交不同 slot 的情况。

本轮没有将现有占位评分、已授权的雇主读简历、状态变化后保留预约、历史申请读取策略重新列为 bug。上一轮提到的输入规模上限、登录限流和注销后 JWT 撤销仍需单独决策/验证，本报告不重复声称新发现。

## 复现命令

在仓库根目录：

```powershell
.venv/Scripts/python.exe -m pytest -c pytest.candidate.ini -q
.venv/Scripts/python.exe -m pytest -c pytest.candidate.ini backend/candidate_tests/adversarial_20261029.py -q -s
.venv/Scripts/python.exe -m ruff check backend/candidate_tests/adversarial_20261029.py
.venv/Scripts/python.exe scripts/check_candidate_ownership.py
```

在 `frontend/candidate`：

```powershell
node node_modules/@playwright/test/cli.js test --config audit/adversarial_20261029.config.ts
```

浏览器配置不复用已有服务，使用 18019 和 5173 端口；占用时应停止测试而非连接未知服务。仅调用本轮临时服务，结束后 Playwright 关闭其启动的服务。默认 E2E 不收集 `.diagnostic.ts`，默认 pytest 不收集 `adversarial_20261029.py`。

环境记录：Python 3.12.4、FastAPI 0.138.0、SQLModel 0.0.38。沙箱内 TestClient 初始化挂起，停止该执行后使用获准的沙箱外隔离测试；浏览器首轮因独立配置改变相对工作目录未启动，修正新配置 cwd 后重跑成功。未修改业务实现来绕过这些环境问题。

## 本轮新增文件

1. `backend/candidate_tests/adversarial_20261029.py`
2. `frontend/candidate/audit/adversarial_20261029.diagnostic.ts`
3. `frontend/candidate/audit/adversarial_20261029.config.ts`
4. 本报告 `docs/CANDIDATE_ADVERSARIAL_REVIEW_20261029.md`

没有修复、提交或推送业务代码。既有回归通过不代表不存在以上未覆盖边界；当前结果也不替代真实 PostgreSQL 并发、团队主入口或部署环境测试。
