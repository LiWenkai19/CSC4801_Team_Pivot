# 用户负责的数据表：独立建库与接入

2026-10-26。用户追加授权 Booking 后，当前数据库实现包含用户负责的七张表。所有代码均为独立文件，
没有编辑团队 users/model.py、团队入口、原迁移、配置，或现有候选人共享模型。

## 范围与当前状态

- 用户表：`user`、`candidate_profile`、`candidate_skill`、`company`、`application`、`interview_slot`、`booking`。
- 队友表：`employer_profile`、`job`、`job_skill`；本迁移不创建、修改、删除或写入它们。
- 不建立匹配结果表，不保存 score；候选人和雇主共用既有匹配函数，读取技能后计算。
- 公司资料独立存储；雇主、职位尚未接入 company_id，由相应文件所有者完成。
- 本地持久化文件：`backend/data/owned_schema.sqlite3`，已通过 Git 忽略规则排除。
  文件只包含七张空业务表和独立迁移版本表，没有写入演示账号或测试业务数据，当前版本 owned_booking_003。
- SQLite 允许先建立带外部外键的表。缺少 employer_profile / job 时，只完成结构搭建，
  申请、时段和预约不能投入实际使用。没有创建空壳队友表来绕过依赖。
- PostgreSQL 已生成离线 DDL；当前 Docker 引擎不可连接，没有真实 PostgreSQL 执行证据。
- 没有自动更换应用的 DATABASE_URL，也没有把新库接入现有运行服务。

## 字段清单

所有 ID 为 UUID；除 interview_slot.job_id 外，所有字段 NOT NULL。
时间使用带时区类型；Python 模型拒绝无时区输入，并将输入和读取结果统一为 UTC。

| 表 | 完整字段 |
| --- | --- |
| user | id UUID PK；email STRING UNIQUE；hashed_password STRING；role ENUM(candidate, employer)；created_at TIMESTAMPTZ |
| candidate_profile | user_id UUID PK/FK → user.id；display_name STRING；resume_text TEXT DEFAULT ''；updated_at TIMESTAMPTZ |
| candidate_skill | candidate_id UUID FK → candidate_profile.user_id；name STRING；联合主键(candidate_id, name) |
| company | id UUID PK；name STRING；description TEXT DEFAULT ''；created_at TIMESTAMPTZ；updated_at TIMESTAMPTZ |
| application | id UUID PK；candidate_id UUID FK → candidate_profile.user_id；job_id UUID FK → job.id；status ENUM(Pending, Interviewing, Rejected, Accepted) DEFAULT Pending；created_at TIMESTAMPTZ；updated_at TIMESTAMPTZ |
| interview_slot | id UUID PK；employer_id UUID FK → employer_profile.user_id；job_id UUID NULL FK → job.id；starts_at TIMESTAMPTZ；ends_at TIMESTAMPTZ；created_at TIMESTAMPTZ |
| booking | id UUID PK；application_id UUID UNIQUE FK → application.id；slot_id UUID UNIQUE FK → interview_slot.id；created_at TIMESTAMPTZ |

SQLite 没有 PostgreSQL 的 TIMESTAMPTZ 类型；本地保存 UTC 日期时间，由 UTCDateTime
适配器在读取时补充 UTC 时区。PostgreSQL 使用原生 TIMESTAMP WITH TIME ZONE。

数据完整性约束：

- 邮箱唯一；候选人对同一职位只允许一份申请。
- booking.application_id 与 slot_id 分别唯一，保证一份申请最多一个预约、一个时段最多一个预约。
  不能用两列联合唯一代替这两个独立约束。创建时间默认由数据库生成，时间读取统一为 UTC。
- 候选人名称、公司名称不能全为空白。公司名称允许重复。
- 技能去首尾空白、转小写、去空项并去重后写入；数据库 CHECK 拒绝不规范的单行值。
  规范化操作本身继续复用既有服务，不在数据库建库脚本里处理业务输入。
- interview_slot 的 ends_at 必须晚于 starts_at，且时长为 30 分钟。
- candidate_profile、company、application 的 updated_at 由数据库触发器维护，
  即使旧 ORM 没有映射该列，修改其他字段仍能更新时间。候选人技能为独立子表；
  单独修改技能不触发资料行 updated_at，本阶段也不使用它判断匹配分数有效性。
- 外键没有配置级联删除：有申请或关联时段的职位不能被直接删除。
- 索引：user.email 唯一索引；application.candidate_id / job_id；interview_slot.employer_id。

以上为结构约束。账号角色与资料一致性、资源所有权、私有简历访问、未来时段、
职位与时段是否属于同一雇主、公司成员身份，以及预约资格仍由服务层校验。
新建数据库结构不等于这些 API 已接入；不能仅凭存在外键就声称权限校验完成。

## 运行方式

在项目根目录打开 PowerShell。使用该目录自己的 .venv，不安装或更改依赖。

```powershell
Set-Location 'E:\26-27term1\CSC4801\CSC4801_Team_Pivot_clean_20261024\backend'
..\.venv\Scripts\python.exe -m app.candidate.database init
..\.venv\Scripts\python.exe -m app.candidate.database check
..\.venv\Scripts\python.exe -m app.candidate.database status
```

未设置 OWNED_DATABASE_URL 时，命令只连接上面列出的本地 SQLite 文件。
不会读取团队 .env 或通用 DATABASE_URL，不会推测并连接个人 PostgreSQL。
init 可以在本迁移初始化过的数据库重复执行，保留已有数据；check 验证模型与迁移后的列、
类型、默认值、索引等是否一致。CHECK 约束与触发器另由运行测试验证。

**不能把 init 当作已有旧数据库的升级命令。** 该迁移面向新库：已有 user 等表但没有
alembic_owned_version 的旧库会因表已存在而失败，不会删除原表、自动 stamp、迁移旧公司
数据或悄悄替换旧版本历史。已有共享库需由团队协调编写一次增量迁移；只对用户表加列与
新建 company，队友自行迁移其 company_id。不能同时运行两套会重复建表的初始迁移。
自动破坏性 downgrade 未提供，调用会明确报错。

## PostgreSQL 与队友接入顺序

选择一个明确的新开发数据库，将其完整 SQLAlchemy 地址放入环境变量
OWNED_DATABASE_URL（例如 postgresql+psycopg://...；不要把真实密码写进文档或命令历史）。
迁移不会创建 PostgreSQL server 或 database，连接目标应已存在。

1. 先执行 `python -m app.candidate.database init --phase core`。
   创建 user、candidate_profile、candidate_skill、company，版本 owned_core_001。
2. 队友创建自己的 employer_profile 和 job，保留 UUID 外键契约：
   employer_profile.user_id、job.id；这两列需要是 PK 或 UNIQUE。
3. 执行 `python -m app.candidate.database init`。
   依次创建 application、interview_slot（owned_flow_002）和 booking（owned_booking_003）；若 PostgreSQL 缺少外部表，迁移明确失败。
4. 队友创建或接入 job_skill；预约业务可复用本模块的 Booking，不重复建表。
5. 执行 `python -m app.candidate.database check`，再由配置和入口所有者接入应用。

公司接入需由队友完成：

| 文件/模型所有者 | 接入内容 |
| --- | --- |
| EmployerProfile | 新增 company_id UUID FK → company.id；雇主账号当前属于一家公司；同公司可有多个雇主。公司名称与描述从 company 读取，旧字段与旧数据的迁移由队友处理。 |
| Job | 新增 company_id UUID FK → company.id，保留 employer_id 表示负责人；创建/分配时校验雇主所属公司，更换雇主公司不得自动改写职位历史。 |
| 公司资料 API | 在授权成员流程确定后查询/更新 Company；不能允许任意雇主提交公司 ID 就取得修改权。 |
| 预约业务 | 本模块已创建 Booking，外键引用 application.id 和 interview_slot.id；业务层继续检查身份、Interviewing、未来时段及同雇主，并使用事务处理并发唯一约束冲突。 |
| 共享入口、配置、迁移环境 | 根据团队采用的新库/旧库路径接入，不覆盖原 env.py 或 main.py。 |

现有 users / candidate 服务继续可读取新表中已有的同名列；数据库默认值与触发器使旧 ORM
写入不会漏填新增时间字段。需要显式读取新字段和 Company 时，导入
`app.candidate.database.model` 的七个模型。这些映射使用独立 registry，指向相同物理表名，
没有额外复制业务数据，也没有给团队类动态加字段。一次业务操作尽量统一使用一套映射。
它们不会自动替换团队服务的导入或 HTTP 响应。

新模型 metadata 内复制了 employer_profile、job 的外键目标元数据以解析引用，
**不要调用 OwnedModel.metadata.create_all()**，应使用本迁移入口；入口严格限制创建范围。
独立迁移使用 alembic_owned_version，与原 alembic_version 分离。

本模块原有版本 owned_flow_002 的数据库可直接执行 init，新增迁移 owned_booking_003 只创建
booking，不重建六张旧表。如果数据库已经通过另一套迁移创建 booking，本迁移会报表已存在，
不会覆盖、删除或自动接管它；需要先协调两套迁移的版本历史与字段差异。

完整 PostgreSQL 离线 SQL 见 CANDIDATE_DATABASE_POSTGRESQL.sql，供审阅；新库执行时必须在
core 和 flow 两阶段之间由队友提供外部表，不能把整份 SQL 直接用于缺少依赖的空 PostgreSQL。

## 测试与需求依据

对应规范：docs/REQUIREMENTS.md 的 FP-AUTH-1/2/3、FP-CAN-1/3、FP-EMP-1/2、
FP-MATCH-1、FP-SCHED-1/2/3。中文需求已对照 docs/REQUIREMENTS 中文翻译.md 阅读。
这里实现其数据结构部分：两角色账户和唯一标识、私有简历存储、持久化技能、公司资料、
唯一申请与四状态、明确时区和 30 分钟时段，以及申请/时段各自唯一的预约。
评分不存入数据库；预约资格与完整权限流程仍由业务层负责，不能以结构验证代替业务验收。

在项目根目录执行：

```powershell
$ownedTestRoot = Join-Path (Get-Location) ('backend/data/pytest-owned-' + [guid]::NewGuid().ToString('N'))
.venv\Scripts\python.exe -m pytest -c pytest.candidate.ini backend/candidate_tests/test_owned_database.py -q --basetemp $ownedTestRoot
.venv\Scripts\python.exe scripts/check_candidate_ownership.py
```

测试仅在新建的临时 SQLite 文件中模拟队友表，验证用户表迁移不改变其结构与已有数据；
本地交付文件不包含这些测试夹具。测试还覆盖数据保留、UTC、约束、时间更新和旧 ORM
兼容写入，以及 PostgreSQL 离线 DDL 不包含队友表的 CREATE/ALTER。
Windows sandbox 的默认临时目录可能不可写，故显式使用本项目 backend/data 下的唯一测试目录。

本次 Booking 扩展按项目台账安排不新增或运行正式测试样例；仅同步既有测试夹具的表归属和
表数，避免将 booking 继续作为外部表预建。实际完成的是本地迁移、Alembic 模型差异检查、
字段/外键/独立唯一约束/默认值检查、数据库完整性、PostgreSQL 离线 DDL、Ruff 与归属检查。
先前版本的测试通过数字仅为历史记录，不代表新增预约模型或当前业务套件已通过验收。
