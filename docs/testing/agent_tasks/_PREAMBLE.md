# 通用前言（每个任务会话先粘贴本文件，再粘贴任务文件）

你在一个招聘/候选人匹配系统的课程期末项目里工作，任务是**为本仓库补充高级测试与验证**。
你当前位于一个专用 git worktree 和分支中，其他 Agent 在别的分支上并行做别的任务。

## 项目速览

- 后端：FastAPI + SQLModel + PostgreSQL，代码在 `backend/app/`；按功能分模块
  `users/`、`candidate/`、`employer/`、`interview/`，每个模块有 `model.py`、`schema.py`、
  `service.py`、`router.py`。service 抛 `ValueError` 子类，router 转 HTTP 状态码。
- 认证：服务端会话 + HttpOnly Cookie + CSRF 令牌。测试里请求头写法：
  `{"Cookie": "session=<值>", "X-CSRF-Token": <csrf_token cookie 值>}`，并在每次响应后清空
  TestClient 的 Cookie 罐。参考 `backend/tests/candidate/conftest.py`。
- 匹配分数唯一实现：`backend/app/employer/matching.py::match_score`；技能归一化：
  `backend/app/users/service.py::normalize_skills`。
- 预约：`backend/app/candidate/service.py::book`（行锁 + 唯一约束）；时段：
  `backend/app/interview/service.py`（30 分钟、未来、不重叠）。
- 需求原文：`docs/REQUIREMENTS.md`；规格：`SPEC.md`；总方案：`docs/testing/ADVANCED_TEST_PLAN.md`。

## 现有测试（只读，不要修改，不要重复实现）

- `tests/unit/`：必测单元套件，`python tests/run_tests.py` 运行；用 MagicMock 会话替身，
  autouse 夹具禁止真实数据库连接。
- `backend/tests/`：真实 PG 集成测试，`python tests/run_tests.py --integration`，
  需要环境变量 `CANDIDATE_TEST_DATABASE_URL`、`EMPLOYER_TEST_DATABASE_URL`。
- `tests/specialized/`：历史专项套件（已有：1000 次固定种子匹配 fuzz + 6 个蜕变维度、
  8 个手写变异体、Barrier 并发测试、Playwright 浏览器测试）。**只读**。
- `tests/advanced/`：高级套件，由 P0 搭骨架，用法见其 `README.md`。

## 硬性规则

1. **不修改生产代码**：`backend/app/`、`frontend/src/`、`backend/alembic/`、`backend/scripts/`
   一律只读。发现业务 bug：写到 `docs/testing/findings/P<n>.md`（格式见下），**不要修**，
   **不要为了变绿去改断言或加 skip/xfail**。
2. **只改任务文件里"允许修改"列出的路径**。需要改别的文件：停下，在汇报里说明原因。
3. **确定性**：`PYTHONHASHSEED=4801`；Hypothesis 用 `derandomize=True` 或固定 seed，
   `deadline=None`；随机数用 `random.Random(4801)`；每个模式的规模有上限。
4. **安全边界**：只连本机临时 PostgreSQL（随机端口新建，或 CI 提供的一次性服务）；
   只向本机进程发请求；不访问外网；不读取 `backend/.env` 的真实值；
   不在日志、报告中打印 Cookie/CSRF/密码哈希。
5. **产物位置**：日志和原始输出写到 `--out` 指定的**仓库外**目录；仓库里只写汇总数字与结论。
6. **独立 oracle**：期望值必须来自需求、手算或独立实现，**不得调用被测函数生成期望值**。
7. **证明测试会失败**：每个新 oracle/不变量，至少做一次"故意引入错误 → 测试变红 → 恢复"
   的自检（在测试代码或 monkeypatch 里做，不改生产代码），并在汇报里写出结果。
8. **完成前必须通过**：
   - `python tests/run_tests.py` 全绿；
   - 任务的验收命令全部通过；
   - `git status` 只显示允许的路径。
9. **提交**：本任务一个或少量 commit，信息格式 `test(advanced): P<n> <简述>`；
   **不要 `git push`**，不要改 `main`。
10. 子代理同样受以上规则约束；把本前言连同任务要求一起传给子代理。

## 业务缺陷记录格式（`docs/testing/findings/P<n>.md`）

```markdown
## <一句话标题>
- 需求条款：FP-xxx-n / SPEC 章节
- 复现命令：<完整命令>
- 最小输入：<数据>
- 期望：<…>　实际：<…>
- 定位线索：<文件:行，如果知道>
```

## 汇报模板（任务结束时原样输出）

```text
任务：P<n> <名称>
分支 / 最后 commit：<branch> / <sha>
改动：<新增/修改的文件列表>
命令：<验收命令，逐条>
结果：<每条命令的退出码与关键数字（用例数、通过数、得分、证明数、耗时）>
自检：<故意引入错误后测试是否变红>
证据：<--out 产物路径>
业务缺陷：<无 | docs/testing/findings/P<n>.md 条目数>
阻塞/偏离：<无 | 具体问题、已尝试方案、需要人类决定的事>
```
