# 全阶段专项测试报告与仓库整合记录

## 2026-11-25：剩余本地修改发布前复核

本轮基线为 `1a256d314e384bebd4a6c2335e965277ad9bc137`，按用户授权一并提交此前保留的本地修改。修复范围包括文本 NUL 校验、原子 seed 重置与未来 30 分钟共享时段、`application.status` 数据库默认值迁移、本地安装说明、会话 Cookie/CSRF 浏览器工具，以及随上游字段变化的测试适配。

完整单元在导出的实际待提交源码快照执行，**196/196 通过，0 失败/错误/跳过**。申请人邮箱测试现在构造真实角色的 User 替身；时段列表测试现在提供六字段关联行，继续校验预约标志、职位与申请人信息。此前 main 上的两项旧夹具失败在本次适配后通过。此前公司简介提交单独校验时的 155/157 仍是对应提交的历史结果，不改写成早已全绿。

本轮结果已补充到 [机器可读证据](nul-fix-verification.json) 的 `publication_verification`。待提交源码树为 `384ca5ec220dae12137d11314c509282dbc3c40a`；最终提交仅额外更新文档和测试来源元数据，受测代码逐文件哈希一致。

| 验证 | 本次执行结果 | 说明 |
|---|---|---|
| 完整课程单元 | **196/196 通过** | 实际暂存源码导出快照；包含原两项旧夹具适配 |
| 完整后端/API/数据库 | **241/241 通过** | 同一源码快照，新建隔离 PostgreSQL |
| 全功能专项 | **411 项：407 通过、4 原始失败** | 时段97、预约121、匹配102、认证42、定向26、剩余23；仅认证组4项失败 |
| 浏览器回归 | **308/308 通过** | 版本冲突12、检查更新36、公司简介84、认证37+23、旧工具2、跨浏览器78、补测9、冒烟6、改动页面21 |
| 非 Docker 交付 | **21/21 通过** | 隔离数据库安装、升级/降级、状态默认值、seed重置与配置说明 |
| 前端构建 / lint | **通过 / 通过（3 项既有警告）** | AuthContext热更新导出2项、浏览器脚本未使用函数1项 |

4项失败仍是 AUTH-01：两种角色的并发同邮箱注册及两种角色组合的驱动复现，实际500不满足原有业务拒绝断言。按团队此前决定不列为待修bug；本轮没有跳过、改成xfail或放宽断言。单元全绿不表示所有专项全绿，各套件有重叠，不能相加当作独立用例总数。

本轮没有重新测量性能、长时间运行、变异或覆盖率，也未重新运行独立SSR及10项seed套件；seed已由本次交付验收重新覆盖。以下 NUL 专项、main 完整复测和更早报告保留原版本及统计，历史段落中的“未提交”等描述只对应当时状态。测试数据库与服务均隔离并已停止，未使用团队数据库，Docker不在本轮范围。详细日志与XML在工作区外层 `tmp/remaining-local-submit-20261125/`。

---

## 2026-11-25：NUL 输入校验修复（当前结果）

REG-TEXT-01 已在本地修复并验证。版本为 `c39d36bbce554479f4e59f0fc448b21e6f6ca392` 加未提交补丁，原有本地工作保留，没有提交、推送或操作团队数据库。机器可读证据见 [nul-fix-verification.json](nul-fix-verification.json)。下方昨日全量复测的失败与覆盖率仍按其原版本保留。

业务修改仅在 `backend/app/users/schema.py`、`backend/app/employer/schema.py`。共享 `DatabaseText` 拒绝真实 U+0000，`NonBlankName` 保留去空白及非空规则并增加相同校验。首次资料、公司更新、职位创建和更新的名称、描述及技能元素在写库前拒绝 NUL，返回 422 与字段/列表下标定位。候选人 PATCH 的队友实现保留。service、router、模型、迁移、前端和依赖未改动。

| 验证 | 结果 | 范围 |
|---|---|---|
| 修前 Schema 基线 | 32 项：19 通过、13 失败 | 本轮修改前重新运行并保存 XML |
| 完整单元测试 | **196/196 通过** | 原189项及新增7项边界；同名原32项全部通过 |
| 匹配/资料/职位 API 组 | **102/102 通过** | 原86项加新增16组；原五项500用例现通过 |
| 新增 API 验证 | **16/16 组通过** | 创建/更新、混合字段、列表中间元素；422定位、完整快照不变、原版本重试及新请求GET读回 |
| 完整后端回归 | **233/233 通过** | 全新隔离PostgreSQL；原账号测试使用其隔离SQLite |
| seed独立验收 | **10/10 通过** | 演示账号、匹配、重置、预约和回滚 |
| 全功能专项 | **411项：407通过、4原始失败** | 仅AUTH-01四条旧错误码断言失败，按团队决定不作为待修bug |
| 静态与范围 | 通过 | 修改文件Ruff、diff检查、原有改动哈希和清理核验 |

新增根因测试区分 NUL 首尾、独立NUL、列表下标及混合字段整次拒绝；普通Unicode、表情、换行、字面反斜线-u0000和U+0001可实际保存并重新读取，制表符另有Schema保留检查。名称去空白、技能规范化、清空/省略/显式null及版本保护沿用原合同，不静默删除NUL。原驱动诊断用例沿用名称，修后要求422、正确字段、无未捕获异常和零写SQL；旧DataError证据仍保留，未改名充作新增用例。

原13项Schema失败本轮由红转绿。原5项API失败取自昨日同一Schema源码的执行，本轮同名用例通过；已核对基线源码哈希。没有skip/xfail、过滤失败或放宽正常业务断言。API最终复验额外确认保存后的独立GET内容和版本，而非只看保存响应。

本轮未重复浏览器、性能、Docker或覆盖率测量；AUTH-01团队决定保持。所有临时数据库已停止。日志、XML、备份和哈希在工作区外层 `tmp/nul-fix-20261125/`，后端/seed证据在 `tmp/del-seed-20261124/nul-fix-20261125/`。当前剩余跟踪项是SE-04的SPEC文档完整性。

---

## 2026-11-24：拉取 main 后的完整复测（当前结果）

已从 GitHub 默认分支 main 拉取并快进合并 7 个提交，HEAD 从 `72654ed630dfba73ed1222fd4f4da9cfe3cf9ae2` 更新到 **`c39d36bbce554479f4e59f0fc448b21e6f6ca392`**。测试结束后再次核对远端 main，仍为该 SHA。所有结果针对这个提交加保留的本地未提交修复；没有提交或推送。本地原有 12 个文件在合并时逐文件哈希相同；后续仅适配测试工具并更新报告，产品 `backend/app`、`frontend/src` 均与当前 main 一致。seed、迁移、配置等原本地修复保留。

完整机器可读结果见 [full-retest-verification.json](full-retest-verification.json)，当前问题状态见 [findings.json](findings.json)。下方较早报告保留当时版本与统计，不能当作当前状态。

| 范围 | 最终执行结果 | 说明 |
|---|---|---|
| 完整课程单元命令 | **189 项：176 通过、13 失败** | 13 项均为 REG-TEXT-01 的剩余 Schema 校验缺口；候选人 PATCH 的三项 NUL 检查已通过 |
| 完整后端/API/数据库 | **233 项全部通过** | 新建隔离 PostgreSQL；原账户测试另用隔离 SQLite，迁移测试亦不接触团队数据库 |
| 全功能专项 | **395 项：386 通过、9 原始失败** | 其中 4 项 AUTH-01 按团队决定不作为 bug；其余 5 项为公司/职位 NUL 的真实 API 500 |
| 时段专项 | **97/97 通过** | 当前年份上界、UTC/上海时间、归属、列表关联和受控竞争 |
| 预约及跨模块专项 | **121/121 通过** | 64 资格组合、状态关系、回滚和实际数据库锁竞争 |
| 新规格定向/剩余路径 | **26/26、23/23 通过** | 管理列表新字段与防御路径等 |
| 全部专项浏览器 | **224/224 通过** | 九个入口；Chrome/Firefox/WebKit 按各模块设计执行，含双语言四编辑器、注销故障恢复与新增跳转 |
| 原完整浏览器脚本 | **候选人 8/8 组、雇主 30/30 组** | Chrome；与专项场景分别统计，避免当作全新独立用例叠加 |
| 实际组件 SSR | **36/36 通过** | 6 项聚焦及 30 项广泛渲染检查；不替代真实浏览器事件验证 |
| 配置/seed/迁移交付 | **21/21 通过** | 配置缺失被明确拒绝、示例配置能导入、空库/旧库/重复迁移、默认值及实际 seed 预约 |
| seed 重写独立验收 | **10/10 通过** | 最新业务版本下再验证真实竞争、匹配、日期、重置及失败保留旧数据 |
| 性能与持续运行 | **4/4 通过** | 10/100/1000 职位有序 ID/分数及每请求 4 查询；360.22 秒循环，4044 次读取全 200，101 对写入/删除，结束借出连接 0 |
| 变异检验 | **基线 8 项通过；7/7 非等价变异检出** | 1 个等价变异单列；仅修改临时 app 副本并还原，不算产品失败 |
| 构建、依赖及静态检查 | 构建、pip check、业务/单元 Ruff、Node 语法与 diff 检查通过 | 前端 lint 退出 0，3 个既有警告；旧专项工具的未使用导入 F401：main 基线 10 条，本地 9 条，无新增问题 |

### 仍需处理的内容

1. **REG-TEXT-01：部分输入仍接受真实 NUL。** 队友 `86712d6` 修复了候选人 PATCH 的姓名、简历和技能。首次资料创建、公司和职位的部分请求 Schema 仍缺校验，产生上述 13 项单测失败；真实公司描述、职位描述/标题/技能保存另有 5 项 500 复现。两组失败对应同一类根因，不能相加成 18 个 bug。本轮没有擅自修业务代码、跳过或放宽失败断言。
2. **SE-04：SPEC 的设计说明仍未完整。** 架构、模型、认证和 API 已有正文，但主要 UI 流程、匹配与安全控制等章节仍有缺口。README 的 25 个需求映射和 64 处具名 Python 测试引用已静态核对，不再保留旧 SE-03 的缺映射结论。

**AUTH-01** 的四条历史并发错误码断言仍按原样执行并失败；依据用户与队友的明确决定，不作为待修 bug，也不将它改称已经修复。

**SLOT-01** 的新增请求已按最新 SPEC 的年份范围验证，所有 97 项时段检查通过。诊断测试仍证明：若已有数据库记录被直插为驱动无法表示的极端日期，上海时区下仍可能解码失败；本轮没有修改、清理或迁移团队数据库，不能将新增校验描述为遗留数据修复。**UI-02** 已由队友修复；23 项聚焦浏览器检查通过，包括三个注销入口及成功、过期、网络失败、会话状态和重试。

### 为当前版本适配的测试与原始失败

- 主入口首次启用覆盖率时缺少 coverage，七个 Python 阶段没有实际执行；补用本地既有的 coverage 7.17.4/psutil 7.2.2 后完整补跑。没有把工具启动失败记为产品 bug。
- 两项单元 mock 未提供新增 User 邮箱及六列时段查询结果；已适配真实查询合同，并明确断言邮箱、关联职位和申请人字段。
- 旧专项认为预约后 interview_slot 完全不变；按新功能，只允许被预约时段的 job_id 变为对应申请的职位，其余字段和其他时段仍逐项比较。管理列表 DTO 的预期从独立原始 SQL 快照构造，继续严格比较完整字段及失败无副作用。
- 旧交付工具错误要求两人顺序预约同一时段均为 201；现精确要求首个 201、第二个 409 且快照不变。已预约申请不可再选时段；未预约候选仍能选新时段。直接 SQL 默认值成功后先清理该测试行，再与 ORM 比较，避免制造重复申请。
- 申请人标题新增邮箱文本，旧精确名称选择器失效；适配后保持姓名/排序/权限断言并验证邮箱文本。新增三引擎真实流程：时段列表关联职位链接、申请人锚点定位、邮箱展示、品牌返回主页。该入口从原 18 项扩展为 21 项，最终均通过。
- 原始 XML/JSON、失败堆栈和重跑结果均保留；最终表采用完整复验替换对应首轮结果，不叠加重复执行。变异造成的预期红测试也不计应用缺陷。

### 覆盖范围与限制

仅合并本次当前源码的功能/性能覆盖数据，后端 app 语句 **1086/1113＝97.57%**、分支 **173/196＝88.27%**，无排除项；没有继承旧版 99.90%/99.43%。完整单元、后端集成和浏览器虽已运行，但未纳入这份覆盖率，因此不称为全项目覆盖率。

Docker 客户端存在，但 desktop-linux 引擎管道不可用，容器 build/start 未执行；不据此判镜像失败。未执行真机、生产长期稳定性或新一轮依赖公告/秘密历史审计，也未重复创建全新 venv 安装。这里的完整轮次覆盖本机现有可执行测试入口，不能表述为所有交付环境均验证完成。

原始记录在工作区外层 `tmp/full-retest-20261124/`；完整后端、seed 和原浏览器脚本记录在 `tmp/del-seed-20261124/merged-main-*`。本地修复备份、快进前后 SHA、命令/退出码、每例归因、当前源码哈希、覆盖率输入和服务清理结果均已保存。所有本轮临时 API/浏览器和 PostgreSQL 集群均已停止，未操作团队数据库。

---

## 2026-11-24：团队决定、DEL-01 与 seed 重写验收

本轮按用户与队友的讨论，仅处理 AUTH-01 的分类、DEL-01 的测试工具修复，以及 SE-05 的 seed 重写。基线 HEAD 为 `72654ed630dfba73ed1222fd4f4da9cfe3cf9ae2` 加本地未提交改动；没有提交、推送或操作团队数据库。下文旧版本统计保持历史口径，最新状态以本节及 findings.json 为准。

- **AUTH-01：团队决定不作为 bug，不修复。** 注册服务及路由均未改动。保留并发失败方返回 500 的历史观测与旧测试断言，不改称已经修复，也不将它作为本轮待修项。
- **DEL-01：本地已修复并验证。** 两份原浏览器脚本分别维护 Cookie/CSRF 会话，移除旧 access_token/Bearer 依赖；浏览器同源 `/api` 请求只转发到本轮随机 API 端口。雇主脚本必须显式提供 `EMPLOYER_TEST_DATABASE_URL`，不会读取团队 backend/.env 来创建测试库。原完整场景适配了当前导航、申请卡片、技能标签、中文错误文案和必填版本字段；没有修改产品页面来满足旧脚本。仍断言精确排序、持久化、拒绝后状态、预约关系、失败恢复和角色隔离。新增 CSRF 拒绝、会话隔离、注销撤销及 8000 端口哨兵检查；原辅助函数探针同步使用当前合同。
- **SE-05：重写版通过验收，保留重写版。** 保留原账号、固定 UUID、三个职位、五条申请和四种状态；时段改为雇主共享、严格 30 分钟，默认 UTC 次日 10:00，避免固定日历日期过期。可用 `python scripts/seed_demo.py --reference-date 2035-12-31` 固定复现日期；相同日期的业务数据一致，密码仍使用随机盐。清空业务/会话表和写入共用一个事务，任一写入失败时旧数据与会话均完整保留。默认命令仍为在 backend 目录执行 `python scripts/seed_demo.py`。

| 实际执行 | 结果 | 证据范围 |
|---|---|---|
| 原 seed 备份上的同一核心验收 | 3 项失败 | 时段资格、实际双候选演示、清空后的写入失败回滚；原文件未替换回工作区 |
| 重写 seed 独立验收 | **10 项通过** | 四个真实 API 匹配分、同一时段一 201/一 409、双方预约回显、重置清理会话、逐字段回滚、固定日期重复性、跨年/闰日和开始前/等于/后的边界、非法 CLI 日期无副作用 |
| 原候选浏览器脚本 | **8 组通过** | 原完整流程及新增会话/CSRF合同；Chrome |
| 原雇主浏览器脚本 | **30 组通过** | 原完整流程及新增会话/CSRF合同；Chrome |
| 两份原 API 辅助函数探针 | **2 组通过** | 真实受保护读取 200、CSRF 更新成功、缺失 CSRF 403、注销后旧会话 401 |
| 随机端口隔离 | **两次 8000 端口哨兵均 0 次访问** | 本轮同时占用 8000 作为独立哨兵，脚本只访问本轮服务 |
| 完整后端回归 | **231 项通过** | 全新隔离 PostgreSQL；含上轮已在工作区的两项迁移测试 |
| 当前完整单元命令 | **173 通过、16 失败** | 16 项均为上轮新增且尚未修复的 REG-TEXT-01/NUL 复现，不属于本轮处理范围；没有 skip/xfail 或放宽断言 |
| 构建与静态检查 | 通过 | Vite/TypeScript 构建，三个 Node 脚本语法检查，seed Ruff，git diff --check |

所有数据库均由新建的本机 PostgreSQL 集群提供，数据库与服务已清理/停止。原 seed 的字节备份及 SHA-256 位于工作区外层 `tmp/del-seed-20261124/backup/backend/scripts/seed_demo.py` 和 `before.json`；最终源文件哈希、XML、浏览器结果、命令、退出码及清理证据在同目录 `verification.json` 和各运行子目录。该目录是本地证据位置，不随仓库发布。若后续需要回退，可以从该字节备份恢复。

本轮未重跑全部历史专项、三引擎、性能或 Docker，也没有把单个 seed 命令成功冒称全系统通过。旧 delivery_checks.py 的两个候选依次预约同一个时段却都期望 201，静态上与同一时段只允许一个预约的规则冲突；本轮未修改该非目标脚本，seed 资格与竞争由上述独立真实 API 验收判定。

---

版本改动的后续遗漏回归已完成：浏览器 169 场景为 161 通过／8 个既有失败；SSR 36 项、性能 4 项通过，原变异 7/7 检出，非 Docker 交付 13 通过／8 个既有失败。参见[补测报告](VERSION_RETEST.md)及[逐例原因索引](version-retest-verification.json)。本次仅适配测试工具，没有新增业务修复；原历史统计保持原口径。

后续更新（2026-11-23）：队友在 `5143f1e` 修复简历直接读取权限；本地经用户授权实现候选人资料与职位的版本保护，修复 REG-CAND-01／REG-JOB-01。最新验收为单元 137 项、完整后端 195 项、双标签页浏览器 12 个场景全部通过；功能专项 375 通过／18 个其他已知失败。详见[版本保护修复报告](VERSION_PROTECTION.md)及[机器可读结果](version-verification.json)。下文原阶段版本、统计与历史结论保留，不表示这些已修问题仍未修复。

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
