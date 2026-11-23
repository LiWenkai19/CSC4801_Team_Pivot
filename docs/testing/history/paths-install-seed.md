> 历史报告副本：保留原日期、SHA和当时状态；路径按本次仓库结构重写。历史日志/数据库/截图未发布，当前运行方式见测试README。不能把旧结果当作新提交执行。

# 剩余代码路径、安装、seed与迁移检测报告

日期：2026-11-23（Asia/Shanghai）。本轮先检查GitHub，main较上轮新增1提交：[8569b72](https://github.com/LiWenkai19/CSC4801_Team_Pivot/commit/8569b72ac1d965c252a741f3e62ed71b01f630e7)，“一些样式和体验优化”。六个改动文件均属前端，后端/安装文档/seed/迁移内容未变；本轮固定该SHA，仍重新执行指定范围验证。

项目原checkout保留f12f819，未覆盖工作区；测试使用最新提交的完整Git archive。所有项目跟踪文件字节哈希保持，原仓库git状态clean。仅检测，不修复；Docker继续排除。编辑安装产生的egg-info、.env及构建产物均只在本轮临时副本中。

## 结果

| 范围 | 结果 |
|---|---|
| 当前提交完整现有后端基线 | 145通过，0失败/错误/跳过 |
| 新增剩余路径 | 23个独立case最终全部通过；实际24次执行23通过、1次外部测试调用名错误，已单项复验通过 |
| 安装/seed/迁移检查 | 21项：13通过、8失败，归于3个既有原因SE-02/05/06 |
| 两种实际安装方式 | 全新Python环境按requirements安装及pip check通过；另行实际editable安装和pip check通过，提供显式测试配置后导入也通过 |
| 最新前端影响范围 | build、lint通过；6项真实Chrome检查通过，1260个建议词条规范化后无重复；新增建议、自定义/去重、待添加阻止保存、IME、390窄屏均正常 |
| 累计后端覆盖率 | 语句1042/1043＝99.90%，分支173/174＝99.43%，无exclude；继承与新增证据分开保留 |

“8次失败”不等于8个bug；全部为既有问题在当前版本的新证据。路径补测未发现新产品缺陷。前端只回归此次实际影响，不宣称重跑了上轮完整三引擎套件。

## 三项仍存在的问题

### SE-02：安装配置和运行说明不足

实际依赖安装两种方式均能成功，但INSTALL的Environment Variables、Database Setup and Migrations、Demo Data and Reset Command、Local Development、Running Unit Tests、Troubleshooting六个非Docker章节仍空。根.env.example仍是旧SQLite模板，不包含当前必需APP_NAME/DATABASE_URL。

在干净工作目录按现有说明/示例配置导入app，两次均因缺必填设置失败；显式提供本轮隔离配置的阳性对照成功。这样只能证明测试harness知道怎样启动，不代表INSTALL已经能指导独立部署。证据见delivery-results.json及logs/config-no-env.txt、logs/config-example-env.txt。

### SE-05：seed确定性通过，但预约演示资格失败

两次实际reset/seed均返回0，排除随机加盐密码哈希和创建/更新时间后业务快照一致。5账号（3候选/2雇主）、3职位、5申请、四种状态齐备；实际候选API也验证100/50/0/空要求100四例。

但唯一时段仍为2026-12-01 10:00–11:00 UTC，共60分钟；当前日期下仍未来。独立SQL合格配对为0，Alice/Bob共同可预约集合为空，两个实际预约均409且业务快照不变。单独通过雇主API创建合法30分钟测试时段后，两人均能看到，确认问题在原seed数据而非普通预约可用性；这没有修改seed脚本，也不作为seed修复。

### SE-06：Application.status数据库默认值与模型不一致

空库升级、初始用户表版本升级至head、重复upgrade均成功；已有合法用户在升级后保留，两条升级路径的实际schema相同。默认alembic check通过。

打开compare_server_default后，三个实际数据库均出现同一Application.status默认值差异：模型声明Pending，迁移后的数据库没有。直接SQL省略status失败于非空约束，普通ORM插入仍赋Pending成功；不是普通API投递失败。完整模式、唯一约束/外键/check约束及默认值比较结果见schema-inventories.json、model-migration-differences.json。

## 剩余路径的证据边界

新增检查包括服务层独立角色拒绝、缺公司资料404、实际get_db会话释放、异常子类MRO转换及未知异常不吞没、登录ValueError转换、真实flush后的删除回滚、申请/预约IntegrityError恢复分类与缺失关联防御行为。

正常可达路径使用真实路由和PostgreSQL。合法竞争状态恢复检查明确注入异常，再用真实Session提交合法竞争记录；证明恢复分支而非自然并发时序。FK通常保证关联存在，因此缺关联情况只让Session读取double返回None，真实数据和约束保持不变，不把这种假设环境当实际业务bug。

覆盖率继承前已逐文件证明backend/app与78c3cb6字节一致，使用路径别名映射，再合并本轮基线/新增数据。唯一未执行语句与分支为candidate/router.py第46行的末尾raise：当前except元组与映射同源，正常继承下在循环耗尽前必已转换异常。未修改映射或代码来凑100%，说明与前提见剩余不可达分支说明（历史本地产物：`剩余不可达分支说明.md`，未随仓库发布）。这不是形式化全局证明。

## 失败记录、方法与复现

全部9次原始失败有预期、实际、原因、版本和证据：8次产品/交付检测失败＋1次测试调用错误。修复后新增测试计划单列，尚未修复或执行这些未来计划。未用xfail、过滤产品失败或改断言掩盖问题。

课件方法：L12独立判据/覆盖观察，L14边界与前后条件、失败原子性；模型与数据库实际模式对照；L10版本固定、隔离与干净配置复现。无新增生产变体，不把防御double称为真实可达并发证明。

主要命令为本目录runner.py加paths、paths-replay、paths-employer、baseline、delivery、frontend；install_check.py与install_editable.py执行两种安装路径；combine_coverage.py校验哈希并合并原始覆盖数据。命令、退出码、XML、独立字典和截图均已保存。

测试skill已补入两条通用风险提示：跨版本覆盖率继承先验证文件哈希与路径映射；故障模拟、防御分支与有前提的不可达推理分别留证。保留修改前备份及哈希，skill结构校验通过。

6个本轮PG集群（delivery集群含3个隔离库）及UI后端均已关闭；未触碰原数据库、已有服务、远端分支或项目业务逻辑。之前其他问题不因本轮通过自动关闭。

测试用例索引（历史本地产物：`测试用例索引.md`，未随仓库发布） · 执行统计（历史本地产物：`execution-summary.json`，未随仓库发布） · 失败原因（历史本地产物：`failure-analysis.json`，未随仓库发布） · 修复后新增计划（历史本地产物：`失败原因与修复后加测计划.md`，未随仓库发布） · 覆盖来源证明（历史本地产物：`coverage-inheritance-proof.json`，未随仓库发布） · 完整覆盖数据（历史本地产物：`coverage-final.json`，未随仓库发布）
