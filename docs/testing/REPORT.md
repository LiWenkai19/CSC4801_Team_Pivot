# 全阶段专项测试报告与仓库整合记录

日期：2026-11-23，Asia/Shanghai。业务基线a8f3d3a27f1f4dd411d1fb57b8c2967fb0eb154f；本次仅迁移测试/必要工具/文档，不修复业务bug。下列新执行基于该基线加本次测试工作区，历史执行保留原SHA。

## 本次整理范围

- 全部21个未提交专项Python文件已进入tests/specialized；6组功能文件、性能文件和变异判据文件均保留。
- 全部10个历史浏览器/SSR模块已进入frontend/tests/specialized，其中7个浏览器入口、2个SSR入口、1个共享支持模块；独立Playwright测试依赖及锁文件随仓库提供。
- 原来多份机器专属run_stage/runner被一个跨平台入口和公共执行上下文替代；包含实际PG启动/迁移/停止、API启动/关闭、日志/XML/退出码、源文件完整性检查。另保留受限的过期会话工具、模型/seed审查和临时副本变异工具。
- 未复制虚拟环境、node_modules、浏览器、PG二进制/数据、源码归档、实际.env、截图或原始请求/会话日志。运行输出必须位于仓库外的新目录。

## 本次实测结果

| 范围 | 结果 | 结论边界 |
|---|---|---|
| 时段95 | 88通过、7失败 | 同一SLOT-01极端日期原因 |
| 预约/跨模块121 | 全部通过 | 有限资格/状态/受控调度，不是全局证明 |
| 匹配/申请/职位86 | 73通过、13失败 | 两个技能替换落点和NUL存储原因 |
| 认证42 | 38通过、4失败 | AUTH-01同邮箱并发错误分类 |
| 新规格定向26 | 全部通过 | 真实管理列表/状态/回滚等 |
| 剩余路径23 | 全部通过 | 正常、故障模型与防御路径分别说明 |
| 功能合计393 | **369通过、24失败** | 不是24个bug |
| 浏览器157次 | **149通过、8失败** | 三引擎；UI-02五次、DEL-01两次、SLOT-01一次 |
| SSR36 | 全部通过 | 实际TSX，测试侧转译/初始hook适配，不执行输入脚本 |
| 交付21 | 13通过、8失败 | 归SE-02/05/06三个已有原因 |
| 关键变异 | 原版8项通过；7非等价全检出，1等价单列 | 只修改临时app副本并还原，不改仓库 |
| 性能/持续运行4 | 全部通过 | 10/100/1000规模及原360秒预算，无生产容量/SLA承诺 |
| 已提交课程单测 | 114通过、1失败 | SPEC-Q01相关雇主读取简历政策；本次再次确认入口可运行 |

浏览器共272次原始执行（247通过、25失败），包含两批复验；最终认可的157次为上表149通过/8失败。前一轮2次旧“欢迎”标题定位和12次不匹配的WebKit控件对照错误属于工具问题，分别修正并复验对应完整37/78项；未当作产品bug。最终表明确选择复验结果，其余原始尝试留在本地，不合并虚增用例数。

完整新结果见[汇总JSON](verification-summary.json)；所有40次已知功能/浏览器/交付失败逐例关联原因、独立预期及修后新增计划，见[失败索引](failed-cases.json)。单测政策失败单列，不混进这40次。所有失败都是未修复证据，未使用skip/xfail/放宽产品断言。

## 判据与移植说明

新版SPEC明确雇主管理列表保留未来已预约/遗留时段并返回is_booked；旧版“预约后雇主列表为空”判据不适用。移植时改为精确管理标志/完整ID集合断言，候选可用列表仍排除已预约项。页面标题、ApplicantCard结构、上海时间显示按当前实现/规格定位；公共列表按稳定ID定位，WebKit与等价原生控件序列比较。

生产渲染表达式保持原样，SSR产物放在仓库外并解析同一React模块，不需要符号链接权限。跨平台资源观察在Windows使用句柄数、其他平台使用文件描述符，不能跨环境直接比较两指标。原始文件来源、SHA-256和最终移植哈希见[provenance.json](../../tests/specialized/provenance.json)。

历史课件方法包括规格/边界、蜕变与独立评分参考、3000有界生成trial、64资格组合、32状态关系、失败原子性、真实PG锁等待、关键变异、防御性文本/依赖/历史审查和360秒可观测性。未宣称执行CPE或全局形式化证明。此前后端99.90%/99.43%为明确同源继承的历史覆盖数据，本轮未重算新的全程序覆盖率。

## 已知问题与交付状态

历史统计口径保留：12条非Docker开放问题，UI-01由队友版本改变后复验关闭；Docker SE-01历史问题排除。覆盖率、变异分数或新工具正常运行不能关闭这些问题。SPEC-Q01在课程单测中仍红；依赖公告和CI/正式提交等另为风险/外部证据项。

| ID | 问题 |
|---|---|
| SE-02 | INSTALL与示例配置不足，无法按文档独立启动 |
| SE-03 | README映射、占位测试引用及旧验证结论未更新 |
| SE-04 | SPEC缺少架构、认证、页面及安全等必需设计说明 |
| SE-05 | seed唯一60分钟时段不满足30分钟预约资格 |
| SE-06 | Application.status的数据库默认Pending未进入迁移 |
| SLOT-01 | 已接受的极端日期在数据库返回时区下无法读回 |
| REG-CAND-01 | 候选技能整体替换竞争会合并集合或返回500 |
| REG-JOB-01 | 职位要求技能的独立替换实现存在同类竞争 |
| REG-TEXT-01 | 实际NUL被Schema接受，持久化时返回500 |
| AUTH-01 | 同邮箱并发注册的失败方返回500 |
| UI-02 | 过期会话注销留下未处理Promise拒绝 |
| DEL-01 | 仓库原浏览器脚本仍依赖旧Bearer/access_token |

[完整原因与修复后新增计划](findings.json)。原BL-G01/G02仓库测试集成缺口已由a8f3d3a的业务/组件单测整合处理；此前历史报告保留当时状态，不篡改成早已解决。其他业务bug、seed、迁移及Docker均未修复。

## 运行和索引

按[专项运行说明](../../tests/specialized/README.md)安装测试依赖，使用统一入口逐组运行。默认课程单测仍为python tests/run_tests.py，与专项/浏览器/性能分开统计。各模块返回真实非零失败码；不会因为失败属于已知原因而强制变绿。

| Python文件 | 静态测试函数数（不是执行次数） |
|---|---:|
| [tests/specialized/test_applications_jobs.py](../../tests/specialized/test_applications_jobs.py) | 8 |
| [tests/specialized/test_auth_contracts.py](../../tests/specialized/test_auth_contracts.py) | 9 |
| [tests/specialized/test_auth_replays.py](../../tests/specialized/test_auth_replays.py) | 7 |
| [tests/specialized/test_booking_eligibility.py](../../tests/specialized/test_booking_eligibility.py) | 2 |
| [tests/specialized/test_booking_schedules.py](../../tests/specialized/test_booking_schedules.py) | 3 |
| [tests/specialized/test_booking_states.py](../../tests/specialized/test_booking_states.py) | 3 |
| [tests/specialized/test_booking_transactions.py](../../tests/specialized/test_booking_transactions.py) | 3 |
| [tests/specialized/test_failure_replays.py](../../tests/specialized/test_failure_replays.py) | 4 |
| [tests/specialized/test_matching_oracles.py](../../tests/specialized/test_matching_oracles.py) | 3 |
| [tests/specialized/test_matching_views.py](../../tests/specialized/test_matching_views.py) | 5 |
| [tests/specialized/test_mutation_oracles.py](../../tests/specialized/test_mutation_oracles.py) | 5 |
| [tests/specialized/test_performance.py](../../tests/specialized/test_performance.py) | 2 |
| [tests/specialized/test_remaining_paths.py](../../tests/specialized/test_remaining_paths.py) | 14 |
| [tests/specialized/test_replacement_and_text.py](../../tests/specialized/test_replacement_and_text.py) | 2 |
| [tests/specialized/test_slots_additional_boundaries.py](../../tests/specialized/test_slots_additional_boundaries.py) | 2 |
| [tests/specialized/test_slots_contract.py](../../tests/specialized/test_slots_contract.py) | 12 |
| [tests/specialized/test_slots_date_boundary.py](../../tests/specialized/test_slots_date_boundary.py) | 2 |
| [tests/specialized/test_slots_date_paths.py](../../tests/specialized/test_slots_date_paths.py) | 2 |
| [tests/specialized/test_slots_interactions.py](../../tests/specialized/test_slots_interactions.py) | 8 |
| [tests/specialized/test_slots_races.py](../../tests/specialized/test_slots_races.py) | 1 |
| [tests/specialized/test_targeted.py](../../tests/specialized/test_targeted.py) | 6 |

[机器可读函数/模块索引](test-inventory.json)。临时数据库/API在所有已验收运行后均已关闭，业务源码/迁移/seed/依赖锁保持基线字节。测试输出没有入库。

## 历史报告

以下副本保留原版本、计数与证据边界；旧本地产物链接改为明确文字标注，未伪装成仓库内可下载文件。最新重放结果以前文为准。

- [spec-env.md](history/spec-env.md)
- [baseline.md](history/baseline.md)
- [slots.md](history/slots.md)
- [booking.md](history/booking.md)
- [matching.md](history/matching.md)
- [auth-pages.md](history/auth-pages.md)
- [gap-completion.md](history/gap-completion.md)
- [paths-install-seed.md](history/paths-install-seed.md)
- [unit-integration.md](history/unit-integration.md)
- [final-findings.md](history/final-findings.md)

真机/Safari、生产多日稳定性、Docker完整交付和课程系统回执仍未验证；策略和CI课程口径仍需团队确认。本次提交没有执行任何业务修复或正式课程递交。
