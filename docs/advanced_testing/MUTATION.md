# 变异测试（P7）与必测套件补强

> 对应讲义 L14 slide 28：用工具化变异测试量化**必测单元套件**的缺陷检出能力，
> 逐个归因幸存者，对"缺测试"的幸存者补测试，给出
> "加属性测试前 → 加属性测试后、补强前 → 补强后"的三列分数对比。
>
> 测量对象：`tests/unit/`（`python tests/run_tests.py` 里的 pytest 部分）。
> 测量工具：`tests/advanced/mutation/entry.py`（`python tests/advanced/run.py mutation`）。
> 本文件只写数字与结论；日志、变异体 diff、副本等原始产物全部写在仓库外的 `--out` 目录。

---

## 0. 摘要

| 指标 | 加属性测试前（基线） | 加属性测试后、补强前 | 补强后 | 变化（基线→最终） |
|---|---:|---:|---:|---:|
| 变异体总数 | 304 | 304 | 304 | 0 |
| killed | 184 | 184 | 283 | **+99** |
| survived | 118 | 118 | 19 | −99 |
| timeout | 0 | 0 | 0 | 0 |
| suspicious（无法判定） | 2 | 2 | 2 | 0 |
| 参与计分（总数 − suspicious） | 302 | 302 | 302 | 0 |
| **mutation score = killed / 计分** | **60.93 %** | **60.93 %** | **93.71 %** | **+32.78 pt** |
| 保守下界（suspicious 记为 survived） | 60.53 % | 60.53 % | 93.09 % | +32.56 pt |
| `tests/unit` 用例数 | 176 | 185 | 229 | +53 |
| 必测命令 `python tests/run_tests.py` 用例数 | 198 | 207 | 251 | +53 |
| 相对前一列新增 killed | — | **0** | **+99** | +99 |

> **属性测试单独新增 killed = 0**：P1 的 9 个 Hypothesis 属性测试（`tests/unit/test_matching_properties.py`）
> 在中间列把 `tests/unit` 从 176 例增加到 185 例，但 304 个变异体的判定结果与基线**完全相同**
> （184 killed / 118 survived）。这 9 个测试验证的是有界性、独立 `Fraction` oracle、置换/重复/
> 空白不变性等**规格性质**，不是本报告 6 类运算符的定向杀手；补强测试仍贡献全部 99 个新增 kills。
> 中间列单独计分，正是为了不让补强测试的 99 个 kills 掩盖"属性测试单独贡献为 0"这一事实。

按文件：

| 文件 | 变异体 | 基线 killed | 基线分数 | +属性后 killed | +属性后分数 | 补强后 killed | 补强后分数 | 最终 Δ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `backend/app/employer/matching.py` | 7 | 7 | **100.00 %** | 7 | **100.00 %** | 7 | **100.00 %** | 0 |
| `backend/app/users/service.py` | 51 | 26 | 50.98 % | 26 | 50.98 % | 51 | **100.00 %** | +49.02 |
| `backend/app/candidate/service.py` | 126 | 75 | 59.52 % | 75 | 59.52 % | 117 | 92.86 % | +33.34 |
| `backend/app/employer/service.py` | 77 | 53 | 68.83 % | 53 | 68.83 % | 73 | 94.81 % | +25.98 |
| `backend/app/interview/service.py` | 43 | 23 | 56.10 % | 23 | 56.10 % | 35 | 85.37 % | +29.27 |
| **合计** | **304** | **184** | **60.93 %** | **184** | **60.93 %** | **283** | **93.71 %** | **+32.78** |

分数定义：`killed / (killed + survived + timeout)`。`suspicious` 是"没有判定"的变异体
（本次只有 2 个：把 `SLOT_END_CUTOFF_UTC` 的月/日改成 `0`，模块导入时 `datetime()` 直接
`ValueError`，测试套件并未执行到任何断言），因此不计入分子也不计入分母；同时给出把
`suspicious` 当作幸存者的保守下界。这与 mutmut 的 `killed/survived/timeout/suspicious`
词表一致。

目标达成：`matching.py` 基线已是 100 %（7/7，`tests/unit/test_matching.py` 覆盖了
FP-MATCH-1 的四个例子、归一化、floor 与两个排序平局规则）；其余四个文件全部显著提高，
`users/service.py` 也达到 100 %。

---

## 1. 测量口径

| 项 | 取值 |
|---|---|
| 变异范围 | `employer/matching.py`、`users/service.py`、`candidate/service.py`、`employer/service.py`、`interview/service.py` |
| 测试集 | `tests/unit/`（纯替身、不连数据库；基线 176 例，加属性测试后 185 例，补强后 229 例） |
| 变异算子 | 比较运算翻转、`//`→`/`、`and`↔`or`、整型常量 ±1、`raise`→`pass`、`return X`→`return None` |
| 单个变异体超时 | 30 s |
| 并行度 | CPU 核数 − 1（本机 16 逻辑核 → 15 个 worker） |
| 确定性 | `PYTHONHASHSEED=4801`；两次全量运行生成完全相同的 304 个变异体 ID |
| 判定 | 测试套件失败（有 `FAILED` 用例）→ killed；全绿 → survived；30 s 未结束 → timeout；无失败用例的收集/导入错误或 pytest 非 0/1 退出 → suspicious |

判定细节（写进 `entry.py::classify`，避免"假杀"）：

- 变异体注入前先用 `compile()` 检查语法，语法错误不算 kill；
- 任何变异体判定之前，先在**同一个副本**里跑一遍干净套件；不绿就直接失败退出，
  不产出分数（防止把"环境坏了"误记成"变异体被杀"）；
- 只有出现 `FAILED <nodeid>` 才算 killed；模块导入失败（无断言执行）记为 suspicious。

---

## 2. 为什么没有用 mutmut（降级说明）

任务允许在 mutmut 与本项目不兼容且 1 小时内无法解决时，改为在 `entry.py` 里实现基于
AST 的变异器。实测的第一个不兼容点是硬阻塞（平台），证据保存在
`$ADVANCED_OUT/mutation/mutmut-probe.log`：

1. **平台**：`tests/advanced/requirements.txt` 固定 `mutmut==3.7.0`（3.8.x 要求
   `click>=8.4.2`，与 `requirements.lock` 的 `click==8.1.8` 冲突）。该版本在原生 Windows
   上直接拒绝启动：

   ```text
   $ python -m mutmut --version
   To run mutmut on Windows, please use the WSL.
   Native windows support is tracked in https://github.com/boxed/mutmut/issues/397
   ```

   这不是文案问题：mutmut 3.x 的运行循环依赖 `os.fork()`（`set_start_method("fork")`、
   `os.wait()`）与 `resource.setrlimit()`，两者在 Windows 上都不存在。
   本机唯一的 WSL 发行版是 Docker Desktop 的停止状态 VM，没有本项目依赖闭包（fastapi、
   sqlmodel、psycopg、argon2…）；在 Docker 里重建还要联网装依赖并拉镜像，超出"1 小时内
   解决"的预算，也违反"不访问外网"的约束。

2. **超时语义**：即使平台可解，mutmut 3.7 的单个变异体超时是自适应公式
   `(该变异体的测试估算耗时 + timeout_constant) × timeout_multiplier`（默认 15 倍 + 1 s），
   不是任务要求的"每个变异体 30 s"。用 `timeout_multiplier/constant` 只能近似，
   而且会随测试耗时漂移，破坏"确定性"和跨机器可比性。

3. **导入根需要额外配置**（不是不可解，但必须显式配置且本平台无法验证）：mutmut 3.7 会
   `change_cwd("mutants")` 再在进程内跑 pytest，并把 `mutants/` 插进 `sys.path`；
   而 `tests/unit/conftest.py` 会把 `ROOT/"backend"` 插到 `sys.path[0]`，其中 `ROOT`
   由 `conftest.py` 的位置推导。要让被测包落到副本上，必须让 `source_paths = backend`
   （副本位于 `mutants/backend`，于是 conftest 推导出的 `ROOT` 正好是 `mutants/`），
   并处理 `tests/unit/test_rendering.py` 需要 `frontend/`（`also_copy` 会复制 300 MB 的
   `node_modules`，或者改为 deselect 该用例）。以上配置**没有在本平台被验证过**，
   所以不提交一个从未运行过的 `setup.cfg` —— 那比没有更容易误导人。

因此按任务要求的降级方案实现：`ast` 驱动的变异器（`entry.py`），算子覆盖任务列出的
六类，并且严格实现"每个变异体 30 s"的固定超时。`--selfcheck` 用一个内存样例模块逐类
验证算子确实改到目标 token（`tests/advanced/mutation/entry.py --selfcheck`：
16 个候选、6 个算子族）。

---

## 3. 运行方式与安全保证

```powershell
# 验收命令（产物必须写到仓库外；--out 可以是任意新目录）
.\.venv\Scripts\python.exe tests\advanced\run.py mutation --out "$env:TEMP\p7-final"

# 也可以直接调用（需要 ADVANCED_OUT 或 --out）
.\.venv\Scripts\python.exe tests\advanced\mutation\entry.py --out "$env:TEMP\p7-final"
```

执行流程（`entry.py`）：

1. 先对仓库内 `backend/app` 做 SHA-256 快照（文件名 + 内容），运行结束再算一次；
   任何不同 → 打印 `backend/app changed during the run` 并以退出码 3 结束。
2. 把 `backend/` 复制到 `$ADVANCED_OUT/mutation/work/pristine/backend`（**绝不在仓库原地变异**），
   统一成 LF 换行；同时复制 `tests/__init__.py`、`tests/unit/`，以及
   `frontend/tests/rendering.unit.mjs` + `frontend/src/`（因为 `tests/unit/test_rendering.py`
   会调用 Node）。
3. 按 `--jobs`（默认 CPU−1）复制出 worker 副本；每个 worker 只被一个线程占用，
   逐个注入变异体 → 跑套件 → 用 pristine 恢复。
4. 子进程环境与 `tests/run_tests.py` 的单元测试分支一致：`APP_NAME`、占位
   `DATABASE_URL`、`COOKIE_SECURE=false`、`PYTHONPATH=<worker>/backend`、
   `PYTHONUTF8=1`、`PYTHONDONTWRITEBYTECODE=1`，另加 `PYTHONHASHSEED=4801`；
   继承环境里的 `DATABASE_*`、`CANDIDATE_TEST_*`、`EMPLOYER_TEST_*`、`ADVANCED_*`
   全部清除，`TEMP/TMP` 指向 `--out` 内的目录。`tests/unit/conftest.py` 的
   autouse 夹具仍然禁止真实数据库连接。
5. 结束后写 `result.json`（本次运行的详细报告）、`mutants.json`（304 个变异体清单）、
   `survivors/<id>.diff`（每个幸存者一个 unified diff）、`mutmut-probe.log`。

产物目录结构（仓库外）：

```text
<out>/
  summary.json                 # run.py 的顶层汇总
  mutation/
    run.log                    # entry.py 的 stdout/stderr（run.py 收集）
    result.json                # run.py 的模式回执（会被 run.py 覆盖，见下）
    mutation-result.json       # ★ 本次运行的详细报告（durable，推荐看这个）
    mutants.json               # 生成的变异体清单（id/kind/line/old/new）
    survivors/<id>.diff        # 19 个幸存者各一个 diff
    mutmut-probe.log           # mutmut 不可用的证据
    work/pristine/             # 变异所基于的副本（保存；worker-* 已清理）
```

> 说明：`tests/advanced/run.py` 在模式子进程结束后会把**自己的**模式回执写到
> `<out>/<mode>/result.json`，会覆盖 `entry.py` 写的同名文件。所以 durable 报告是
> `mutation-result.json`；直接运行 `entry.py` 时 `result.json` 就是详细报告。两个文件
> 内容完全一致，`result.json` 的最终内容由 `run.py` 决定（P0 的共享文件，P7 不改）。

---

## 4. 幸存者归因（最终 19 个）

类别：**等价**＝行为不变；**契约等价**＝需求固定的可观测契约不变（仅内部文案不同）；
**不可达**＝防御性代码；**仅真实 SQL 可观测**＝会话替身不执行 SQL，`LIMIT`/`JOIN ON`
是否命中只有数据库能体现（属于集成/差分测试的证据范围，不是"缺单元测试"）。

| ID | 位置 | 变异 | 类别 | 归因 |
|---|---|---|---|---|
| ca013 | `candidate/service.py:109` | `elif user.role == Role.Employer` → `!=` | 契约等价 | 三个分支都抛 `ForbiddenError`（→ 403），只有 `detail` 文案从 "Employers cannot access…" 变成 "Profile access denied"。FP-CAN-1/SPEC 只固定 403，未固定文案；断言文案等于复述实现，故不补测试 |
| ca015 | `candidate/service.py:112` | `raise ForbiddenError("Profile access denied")` → `pass` | 不可达 | `Role` 只有 `Candidate`/`Employer` 两个成员，前两个分支已穷尽，`else` 是防御性代码 |
| ca029 | `candidate/service.py:153` | `return job` → `None` | 等价 | `_active_job` 的唯一调用点 `apply` 不使用返回值（`_active_job(session, job_id, lock=True)`） |
| ca032 | `candidate/service.py:167` | `Job.employer_id == EmployerProfile.user_id` → `!=` | 仅真实 SQL 可观测 | `_recommended_jobs` 的 `outerjoin` ON 条件；替身直接返回预置元组，JOIN 是否命中不可见 |
| ca048 | `candidate/service.py:225` | `[0]` → `[-1]` | 等价 | 指定 `job_id` 时 `_recommended_jobs` 最多返回 1 个元素，单元素列表两者相同 |
| ca058 | `candidate/service.py:252` | `Job.employer_id == EmployerProfile.user_id` → `!=` | 仅真实 SQL 可观测 | `_applications_public` 的 jobs `outerjoin` ON 条件 |
| ca059 | `candidate/service.py:273` | `Booking.slot_id == InterviewSlot.id` → `!=` | 仅真实 SQL 可观测 | `_applications_public` 的 `join(InterviewSlot, …)` ON 条件 |
| ca068 | `candidate/service.py:310` | `[0]` → `[-1]` | 等价 | 同 ca048（`get_application` 的单元素列表） |
| ca081 | `candidate/service.py:345` | `[0]` → `[-1]` | 等价 | 同 ca048（`apply` 返回 `_applications_public([application])[0]`） |
| es042 | `employer/service.py:259` | `.limit(1)` → `.limit(0)` | 仅真实 SQL 可观测 | 删除前的申请存在性检查；替身不执行 `LIMIT`，真实库下会"看不到"依赖行而错误放行 |
| es043 | `employer/service.py:259` | `.limit(1)` → `.limit(2)` | 等价 | 只取 `.first()`，`LIMIT 1` 与 `LIMIT 2` 行为相同 |
| es046 | `employer/service.py:265` | `.limit(1)` → `.limit(0)` | 仅真实 SQL 可观测 | 同上，面试时段存在性检查 |
| es047 | `employer/service.py:265` | `.limit(1)` → `.limit(2)` | 等价 | 同 es043 |
| iv018 | `interview/service.py:57` | `.limit(1)` → `.limit(0)` | 仅真实 SQL 可观测 | 重叠检查；真实库下会漏掉重叠时段 |
| iv019 | `interview/service.py:57` | `.limit(1)` → `.limit(2)` | 等价 | 同 es043 |
| iv024 | `interview/service.py:87` | `Booking.slot_id == InterviewSlot.id` → `!=` | 仅真实 SQL 可观测 | `list_slots` 的 `outerjoin(Booking, …)` ON 条件 |
| iv025 | `interview/service.py:88` | `Application.id == Booking.application_id` → `!=` | 仅真实 SQL 可观测 | `outerjoin(Application, …)` ON 条件 |
| iv026 | `interview/service.py:89` | `Job.id == Application.job_id` → `!=` | 仅真实 SQL 可观测 | `outerjoin(Job, …)` ON 条件 |
| iv027 | `interview/service.py:91` | `CandidateProfile.user_id == Application.candidate_id` → `!=` | 仅真实 SQL 可观测 | `outerjoin(CandidateProfile, …)` ON 条件 |

分类小计：等价 7、契约等价 1、不可达 1、仅真实 SQL 可观测 10。

另有 2 个 **suspicious**（不计分）：`iv005`（`datetime(3001, 0, 1)`）与 `iv007`
（`datetime(3001, 1, 0)`），都在模块导入时抛 `ValueError`，测试套件没有执行到任何断言。
按 mutmut 的退出码词表它们会被算作 killed；本报告保守地记为"未判定"并同时给出保守下界。

> 没有发现业务缺陷。基线中"缺测试"的 99 个幸存者全部是**未被断言的行为**，
> 不是实现错误；因此没有 `docs/advanced_testing/findings/P7.md`。

---

## 5. 补强测试（`tests/unit/test_mutation_hardening.py`，41 个行为测试 + 3 个自检）

只新增这一个单元测试文件，不改任何既有单元测试。每个测试名/文档串写明它杀掉的变异体 ID；
期望值来自 `docs/REQUIREMENTS.md` / `SPEC.md` 的条款，不调用被测函数生成期望值。

| 需求条款 | 测试 | 杀掉的变异体 |
|---|---|---|
| FP-AUTH-1 | `test_pauth1_profile_completed_tracks_the_role_specific_profile` | us006 us007 us008 |
| FP-AUTH-1 | `test_pauth1_session_lifetime_has_two_documented_forms` | us009 |
| FP-AUTH-1/FP-AUTH-3 | `test_pauth3_email_lookup_is_equality_on_a_bound_value` | us001 |
| FP-AUTH-2/FP-AUTH-3 | `test_pauth3_session_lookup_uses_the_sha256_digest` | us015 |
| FP-AUTH-3 | `test_pauth3_revoke_all_sessions_touches_one_account` | us012 |
| FP-AUTH-3 | `test_pauth3_candidate_services_reject_the_employer_role` | ca002 |
| FP-CAN-1 | `test_pcan1_candidate_profile_creation_persists_normalized_skills` | us043 us045 us051 |
| FP-CAN-1 | `test_pcan1_candidate_profile_creation_requires_the_candidate_role` | us044 |
| FP-CAN-1 | `test_pcan1_candidate_profile_conflicts_are_translated` | us046 us047 us048 us049 us050 |
| FP-CAN-1 | `test_pcan1_owner_reads_own_private_profile` | ca007 ca010 ca016 |
| FP-CAN-1 | `test_pcan1_profile_update_locks_the_owner_row` | ca003 ca020 |
| FP-CAN-2 | `test_pcan2_get_job_reads_only_the_requested_active_job` | ca033 ca034 ca037 ca047 ca049 |
| FP-CAN-2 | `test_pcan2_recommendations_scope_applied_flag_and_skills_to_the_caller` | ca030 ca031 ca038 ca039 |
| FP-CAN-3 | `test_pcan3_applying_to_a_missing_or_deleted_job_is_not_found` | ca027 ca028 |
| FP-CAN-3 | `test_pcan3_apply_locks_the_active_job_and_returns_the_public_view` | ca025 |
| FP-CAN-3 | `test_pcan3_missing_and_foreign_applications_are_not_visible` | ca050 ca052 |
| FP-CAN-3 | `test_pcan3_application_list_is_scoped_to_the_caller` | ca056 ca065 |
| FP-CAN-3 | `test_pcan3_duplicate_apply_from_the_unique_constraint_is_a_conflict` | ca070 ca071 ca074 ca075 ca076 ca077 |
| FP-CAN-3 | `test_pcan3_non_duplicate_integrity_error_surfaces_unchanged` | ca078 |
| FP-EMP-1 | `test_pemp1_employer_profile_creation_and_conflicts` | us033 us034 us035 us036 us041 |
| FP-EMP-1 | `test_pemp1_employer_profile_failures_are_translated` | us037 us038 us039 us040 |
| FP-EMP-1 | `test_pemp1_company_update_requires_a_profile_and_locks_it` | es007 es009 |
| FP-EMP-2 | `test_pemp2_job_list_is_owner_scoped_newest_first` | es023 es024 |
| FP-EMP-2 | `test_pemp2_job_creation_rolls_back_infrastructure_failure` | es021 |
| FP-EMP-2 | `test_pemp2_job_deletion_checks_both_dependent_tables` | es041 es045 |
| FP-EMP-2 | `test_pemp2_job_deletion_rolls_back_infrastructure_failure` | es052 |
| FP-EMP-2 | `test_pemp2_job_access_and_skill_queries_are_owner_scoped` | es016 es025 es036 |
| FP-EMP-3 | `test_pemp3_status_change_requires_a_live_owned_job` | es064 es066 es068 es069 |
| FP-EMP-3 | `test_pemp3_applicant_list_skips_rows_without_a_profile` | es057 es058 es060 es062 |
| FP-EMP-3 | `test_pemp3_booking_lookup_is_application_scoped` | es053 |
| FP-SCHED-1 | `test_psched1_slot_creation_requires_an_employer_profile` | iv010 |
| FP-SCHED-1 | `test_psched1_overlap_query_is_employer_scoped_and_half_open` | iv015 iv016 iv017 |
| FP-SCHED-1 | `test_psched1_slot_end_must_precede_the_documented_cutoff` | iv003 iv004 iv006 iv008 |
| FP-SCHED-1 | `test_psched1_slot_list_is_employer_scoped_and_future_only` | iv028 iv029 |
| FP-SCHED-1 | `test_psched1_slot_deletion_queries_are_scoped` | iv033 iv038 |
| FP-SCHED-2 | `test_psched2_booking_reads_are_scoped_to_the_application_and_slot` | ca085 ca098 ca111 |
| FP-SCHED-2 | `test_psched2_available_slots_query_carries_every_eligibility_rule` | ca091 ca092 ca093 ca094 |
| FP-SCHED-2 | `test_psched2_available_slots_requires_the_application_job` | ca090 |
| FP-SCHED-2 | `test_psched2_booking_requires_the_application_job` | ca102 |
| FP-SCHED-2 | `test_psched2_slot_reserved_for_another_job_is_a_conflict` | ca116 ca117 |
| FP-SCHED-3 | `test_psched3_conflict_recovery_queries_are_scoped` | ca118 ca121 |

合计 **99** 个变异体从 survived 变成 killed（相对中间列 184 → 283，全部 99 个由补强测试贡献；
P1 属性测试单独贡献为 0），41 个行为测试每个至少杀 1 个。

两类 oracle（都不是"复述实现"）：

1. **行为 oracle**：用既有 `MagicMock` session 替身驱动 service，断言需求承诺的结果
   （成功返回值、409/403/404 对应的异常、版本递增、回滚、不写入等）。
2. **授权范围 oracle**：编译 service 交给 session 的语句，断言 `… WHERE owner = caller`
   谓词与绑定参数。请求行由 `Session` 替身固定返回，替身看不到"查了哪些行"，所以对
   FP-SEC-1 / FP-AUTH-3 的**归属过滤**而言，语句本身就是单元层唯一可观测的证据 ——
   这与既有套件已经采用的写法一致（`test_fp_sec_2_email_is_a_bound_value`、
   `test_fp_sched_1_management_list_preserves_booking_flag`、
   `test_fp_match_1_employer_ties_use_name_then_stable_id`）。只对**安全关键谓词**这样做，
   JOIN ON 条件与 `LIMIT` 一律不写（见 §4 的"仅真实 SQL 可观测"）。

---

## 6. 自检：证明新 oracle 会失败

1. **逐变异体的红→绿**：99 个被补强测试杀掉的变异体，在基线运行里是 `survived`，
   在最终运行里是 `killed`，并且 `mutation-result.json` 的 `killed_by` 记录了触发的
   具体 `tests/unit/test_mutation_hardening.py::<test>` 节点 ID（§5 的表就是由它生成）。
   这就是每个 oracle 的"故意引入错误 → 测试变红 → 恢复"实验：错误注入只发生在
   `$ADVANCED_OUT/mutation/work/` 的副本里，每个 worker 用完立刻用 pristine 恢复，
   仓库 `backend/app` 的 SHA-256 前后一致（`guard.unchanged = true`）。
2. **套件内自检**（`monkeypatch` 构造受控变体，不改生产代码）：

   | 自检 | 模拟的变异 | 期望 |
   |---|---|---|
   | `test_selfcheck_session_lifetime_oracle_detects_us009` | `session_lifetime` 返回 `None` | oracle 断言失败 |
   | `test_selfcheck_profile_completed_oracle_detects_us008` | `get_current_user_public` 返回 `None` | oracle 断言失败 |
   | `test_selfcheck_owner_read_oracle_detects_ca016` | `_profile_public` 返回 `None` | oracle 断言失败 |

3. **变异器自检**：`entry.py --selfcheck` 用一个内存样例（含 6 类算子）验证每个算子
   确实改到目标 token：`{"candidates": 16, "applied": 15, "families": ["boolop",
   "compare", "constant", "floordiv", "raise", "return"]}`。

---

## 7. 复现与耗时

| 命令 | 退出码 | 关键数字 | 耗时（entry.py 模式） |
|---|---:|---|---:|
| `entry.py --out <baseline> --label baseline`（移出属性 + 补强测试） | 0 | 304 变异体；184/302 = 60.93 % | 229.5 s |
| `entry.py --out <middle> --label middle`（只移出补强测试） | 0 | 304 变异体；184/302 = 60.93 % | 409.1 s |
| `python tests/advanced/run.py mutation --out <final>` | 0 | 304 变异体；283/302 = 93.71 % | 403.2 s |
| `python tests/run_tests.py` | 0 | 251 passed | 5.3 s |

环境：Python 3.14.4（`requirements.lock` + `tests/advanced/requirements.txt` 的项目环境）、
16 逻辑核、`jobs=15`、`timeout=30 s`、`PYTHONHASHSEED=4801`。三次全量运行分别约
3.8、6.8、6.7 分钟，合计约 17.3 分钟；中间列因为每个变异体都要跑 9 个 200-example
属性测试，比基线慢约 1.8 倍。

基线可复现性：三列只改变 `tests/unit/` 里的两个文件，不动源码或变异体：
- 基线（加属性测试前）：把 `tests/unit/test_matching_properties.py` 和
  `tests/unit/test_mutation_hardening.py` 都移出仓库；
- 中间列（加属性测试后、补强前）：只把 `tests/unit/test_mutation_hardening.py` 移出；
- 最终列（补强后）：两个文件都保留。

变异体 ID 只由源码决定，三次运行完全一致（304 个 ID 相同），因此可以逐 ID 对比。

产物（本次最终运行的 `--out`）：

```text
C:\Users\mdrakr\AppData\Local\Temp\p7-mutation-final\
  summary.json
  mutation\mutation-result.json   # 详细报告（durable）
  mutation\mutants.json
  mutation\survivors\*.diff       # 19 个幸存者
  mutation\mutmut-probe.log
  mutation\work\pristine\         # 变异所基于的副本
```

基线/中间列的对应产物在 `$env:TEMP\p7-mutation-baseline\` 和
`$env:TEMP\p7-mutation-middle\`，目录结构相同。

---

## 8. 限制与后续

- **P1 属性测试的贡献为 0**：本报告已把 P1 合并后的 9 个属性测试纳入中间列，并把
  `tests/unit` 从 176 例增加到 185 例；但 304 个变异体的判定结果完全不变（60.93 % →
  60.93 %）。也就是说，在这套 6 类 AST 算子下，Hypothesis 没有额外杀死任何变异体；
  它的价值在规格性质（有界、独立 oracle、不变性）而非变异杀伤力。最终 93.71 % 的提升
  全部来自 44 个补强测试。
- **算子子集**：AST 变异器覆盖任务列出的 6 类算子，不是 mutmut 的全量算子集，因此
  93.71 % 不能和"某项目用 mutmut 得到 93.71 %"直接横向比较；它是**同口径前后对比**。
- **单元层的边界**：§4 的 10 个"仅真实 SQL 可观测"幸存者需要数据库真正执行 `LIMIT`/
  `JOIN ON`。它们属于集成套件（`backend/tests/`）、P6 差分（Python 打分 vs SQL 打分）
  与 P11 覆盖率的分工，不应靠给单元测试加 SQL 文本断言来"凑分"。
- **suspicious 的 2 个**导入期错误变异体：如果希望与 mutmut 的 `killed` 口径对齐，可把
  它们计入 killed，得到 285/304 = 93.75 %；本报告选择更保守的"未判定"。
