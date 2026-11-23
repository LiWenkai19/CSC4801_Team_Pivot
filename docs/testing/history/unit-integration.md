> 历史报告副本：保留原日期、SHA和当时状态；路径按本次仓库结构重写。历史日志/数据库/截图未发布，当前运行方式见测试README。不能把旧结果当作新提交执行。

# 单元测试整合验收报告

日期：2026-11-23；业务基线：8569b72ac1d965c252a741f3e62ed71b01f630e7。本地test-prep-20261121分支先从f12f819快进同步队友两次提交到8569b72，再做测试/文档改动。远端未推送，业务bug未修复。

## 结果

- 完整单测入口：`python tests/run_tests.py`，115项，114通过、1失败，0错误/跳过，退出码1。
- 其中tests/unit共93项，现有纯schema测试22项；Node真实组件3项由一个Python桥接case纳入，不另混加pytest计数。
- `python tests/run_tests.py --integration`：完整原有backend/tests共145通过、0失败/错误/跳过，退出码0。仅既有Starlette/httpx弃用警告；使用新建只监听127.0.0.1的PG16.4，已停止。
- 单独`node --test frontend/tests/rendering.unit.mjs`：3通过。
- Ruff检查、git diff --check通过。缺少显式集成测试URL时入口退出2，不读取开发.env启动测试。
- README25个需求ID全部映射，61处具名Python测试引用存在，原17个pass占位测试已替换。

## 未修复的真实失败

`tests/unit/test_workflows.py::test_fp_can_1_course_resume_privacy_includes_related_employer`

课程FP-CAN-1规定只有简历本人可读取，其他候选/雇主应403。当前候选服务对有投递关系的雇主允许读取；单测准备正常合成资料和投递关系，直接调用原read_profile，预期ForbiddenError，实际返回资料。它是此前SPEC-Q01的明确课程合同证据，不伪称新发现，也不把政策改为当前实现来让测试通过。

业务逻辑保持原样；README/INSTALL明确列出当前红测试和退出1，无skip/xfail/过滤。若按最终授权政策修复，原复现须转绿，另加新雇主/状态关系维度并实测；当前只记录未来计划。

## 变更范围

新增/替换只在tests、frontend/tests，以及README/INSTALL；原雇主fixture仅增加显式EMPLOYER_TEST_DATABASE_URL优先读取，未设置时保留原.env逻辑。默认单测不需要数据库；Engine.connect被禁止，查询/事务边界用Session替身。真实PG并发仍由既有集成测试提供补充证据。

真实组件测试转译原SkillTagPicker，不改渲染表达式，以ReactDOM SSR检查课程规定文本转义及普通Unicode/属性引号，不执行输入脚本。没有改package.json、锁文件、生产组件、模型、迁移或seed。

## 证据

- 最后单测XML（历史本地产物：`unit-final.xml`，未随仓库发布）、完整单测命令/退出码（历史本地产物：`unit-command.json`，未随仓库发布）、原始单测日志（历史本地产物：`unit-command.log`，未随仓库发布）
- 集成XML（历史本地产物：`integration.xml`，未随仓库发布）、集成命令（历史本地产物：`integration.json`，未随仓库发布）、原始集成日志（历史本地产物：`integration.log`，未随仓库发布）、PG停止（历史本地产物：`pg-stop.json`，未随仓库发布）
- 组件日志（历史本地产物：`rendering-command.log`，未随仓库发布）、逐次失败原因及修后新增计划（历史本地产物：`failure-analysis.json`，未随仓库发布）、范围/映射核验（历史本地产物：`validation.json`，未随仓库发布）

首轮4个收集错误为合成URL选择不适配导入时的连接池参数；第二轮还有一次测试误索引apply返回值。两者只改测试，原始XML与原因保留。其余早期多阶段报告保留原SHA及历史状态，本次未重新跑数百个仓库外探索case或关闭既有并发等问题。
