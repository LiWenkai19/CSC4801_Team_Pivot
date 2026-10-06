# 用户模块进度

## 2026-10-06：用户数据库模型

- 范围：按用户明确授权，仅实现 model.py 的用户模型，其他业务模型写入 docs/数据模型设计.md。
- 已定义 User、CandidateProfile、EmployerProfile、CandidateSkill，以及角色枚举、UTC 时间、双向 ORM 关系、邮箱唯一约束、技能组合主键和 CHECK 约束。
- 需求摘录和继承 / 关联说明见 [数据模型设计](../../../../docs/数据模型设计.md)。
- 状态：模型验证通过；接口与数据库迁移尚未实现。
- 验证环境：用户指定的 SYManage，Python 3.12.13、SQLModel 0.0.38、SQLAlchemy 2.0.51。
- 静态检查：`C:/Users/10677/miniconda3/envs/SYManage/python.exe -m ruff check backend/app/users/model.py` 通过（项目根目录执行）。
- 在 backend 目录使用上述解释器，通过 stdin 执行隔离 SQLite 内存数据库验证脚本：建表、两种资料的双向关系、关系重新加载、技能持久化、邮箱唯一、技能唯一、技能规范化 CHECK、外键及角色 CHECK 均通过。
- PostgreSQL 方言建表 DDL 编译通过，确认生成带时区时间列及角色 CHECK；未连接 PostgreSQL，也未验证实际 PostgreSQL 迁移或运行行为。
- 待完成：旧 schema/service/router 与新模型的适配、注册事务及角色一致性、技能规范化、私有简历响应控制、Alembic 模型注册与数据库迁移。上述项目不在本次实现范围内。

## 2026-10-06：认证与资料 schema

- 用户明确范围：处理 schema，注册仅填账户信息，后续单独填写对应 profile；简历、技能、公司描述不强制填写。
- 已调整 UserCreate、UserLogin、UserPublic、Token，补充 AuthResponse 及候选人 / 雇主的资料创建、局部更新、响应结构。移除 UserPublic 中模型不存在的 username。
- UserPublic 的 profile_completed 由后续服务计算；基本资料名称必填，简历 / 技能 / 公司描述可省略且默认空值，不必修改数据库列。
- 局部更新未传字段保持原值；显式 null 被拒绝；空字符串 / 空列表用于清空非必填内容。请求拒绝未声明字段。
- 已同步 docs/数据模型设计.md，更新注册后创建资料的流程、schema 继承及字段契约。
- 测试：新增 backend/tests/users/test_schema.py，覆盖账户注册字段、登录默认值、资料创建默认值、名称 / 技能校验、非法额外字段、局部更新与清空、显式 null 拒绝、认证响应机密隔离及本人简历原文保留。
- 实际验证：SYManage 环境在 backend 目录执行 `python -m pytest tests/users/test_schema.py -q`，22 passed；项目根目录执行 `python -m ruff check backend/app/users/schema.py backend/tests/users/test_schema.py` 及相同文件的 `ruff format --check` 均通过。
- 状态：schema 验证通过；未连接任何数据库或外部服务，未测试 HTTP 授权或页面跳转。本次未修改 model/service/router，未新增 HTTP 接口或执行迁移。
- 下一步：先实现注册认证或资料填写中的一个具体接口，再落实资料完成状态计算、前端跳转、服务端角色与所有权校验；旧接口模板仍需适配。

## 2026-10-06：修正账户创建字段

- 按用户选中语句的明确授权，仅将 create_user 中 User 构造参数改为 email、password_hash、role，移除旧模板的 whitelist_id。
- SYManage 环境中提取现有 get_user_by_email / create_user 函数，在隔离 SQLite 内存数据库验证：两种角色均能创建、密码哈希可验证、重复邮箱被拒绝；通过。未导入完整 service 模块或验证 HTTP 接口。
- 遗留：authenticate_user 仍读取旧字段 user.hashed_password，应改用 user.password_hash；service 仍含旧白名单模板引用。本次未修改这些范围外内容。

## 2026-10-06：按注册流程简化账户响应

- 用户确认注册成功后由前端直接跳转资料填写页，因此移除 UserPublic.profile_completed，不新增完成状态计算逻辑。
- 注册与 /me 的 UserPublic 字段映射改为 id、email、role；登录与 /token 继续返回 Token。未修改 service、安全逻辑或前端。
- 同步设计文档及认证响应的既有测试；当前 User 密码字段以用户修改后的 hashed_password 为准，早期记录的 password_hash 不再代表当前模型。
- 新增 tests/users/test_account_responses.py，使用隔离 SQLite 和真实路由 / service / Token 认证验证两种角色注册、重复邮箱、两种登录方式、/me 响应、未认证请求及非法角色；没有替换当前用户依赖或连接业务数据库。
- 实际验证：SYManage 环境在 backend 目录执行 `python -m pytest tests/users/test_account_responses.py -q`，4 passed；router.py 与新增测试的 Ruff 检查通过。
- 既有 tests/users/test_schema.py 无法收集：它仍导入当前已注释的 CandidateProfilePublic 等类型。仅同步了本次涉及的账户响应测试，未恢复用户注释的功能，也未宣称完整测试套件通过。
- 状态：本次账户响应适配验证通过；旧 schema 测试待按当前保留的功能调整。前端自动跳转未实现；backend/main.py 的用户路由注册仍被注释，本次未改变它。

## 2026-10-06：接入 AuthResponse

- 用户明确确认 /users/register 与 /users/login 都返回 AuthResponse；注册成功后直接签发访问令牌，返回 access_token、token_type、user（id、email、role）。
- 本次修改 router.py，沿用已确认的 schema 及现有密码 / Token 工具；/token 与 /me 返回结构不变。同步设计文档及 test_account_responses.py。
- 实际验证：SYManage 环境中 `python -m pytest tests/users/test_account_responses.py -q`，6 passed；router.py 与测试的 Ruff 检查通过。覆盖两种角色的注册 / 登录响应、注册 Token 可访问 /me、重复邮箱、非法角色、无效 Token、错误密码及不存在账户；测试仅使用隔离 SQLite。
- 状态：本次接口验证通过；没有新增资料接口或修改前端，旧 schema 测试及 main.py 路由注册遗留问题保持待处理。

## 2026-10-06：角色检查依赖

- 用户明确授权实现 require_candidate / require_employer，按现有认证依赖的位置放在 service.py 中；复用 get_current_user 获取数据库中的当前用户。
- 未认证沿用 401；角色不符返回 403；匹配时返回 User，供后续业务接口查询所有权。没有新增生产接口或自动限制已有的 /me。
- test_account_responses.py 增加仅在测试应用中注册的受保护路由，覆盖两种角色的允许 / 拒绝矩阵，以及缺失、无效、过期 Token；不替换认证依赖。
- 实际验证：SYManage 环境在 backend 目录执行 `python -m pytest tests/users/test_account_responses.py -q`，16 passed（新增角色依赖场景 10 项，已有认证接口回归 6 项）；测试文件 Ruff 检查通过。
- 状态：角色依赖验证通过；依赖仅检查角色，不检查具体业务对象的所有权或存在性。旧 schema 测试收集问题仍未处理，本次不宣称全套测试通过。

## 2026-10-06：首次创建雇主公司资料

- 用户授权按已讨论方案先实现一个接口，选择 POST /users/employer/profile；候选人接口不在本次范围内。
- 契约：雇主登录；company_name 去首尾空白后非空；company_description 可省略，默认空字符串；所有者从当前用户取得。成功 201，未认证 401，角色不符 403，已有资料 409，非法字段 422。
- 恢复 EmployerProfilePublic；service 新增 create_employer_profile 及明确的业务异常，router 复用 require_employer。主键保障唯一，提交失败回滚，并区分重复资料与其他数据库错误。
- 实际验证：SYManage 环境执行 `python -m pytest tests/users/test_account_responses.py -q`，27 passed（本次资料接口相关 11 项，已有认证 / 角色回归 16 项）；schema、service、router 与测试的 Ruff 检查通过。清理这些已修改文件中原有的未使用导入。
- 验证包含保存及省略描述、重复创建不覆盖、非法输入不写入、未认证 / 错误角色、不能替他人创建资料，以及数据库写入后提交失败的回滚。测试使用隔离 SQLite，没有验证实际 PostgreSQL 运行行为。
- 状态：接口隔离验证通过；同步 docs/数据模型设计.md 的接口契约。数据库表结构未变化，不生成新结构迁移；当前 main.py 已由用户挂载 user_router，本次未修改入口。已有 Alembic 模型注册 / 建表仍待验证，本次不连接业务数据库。

## 2026-10-06：首次创建候选人资料

- 用户确认继续按既定方案实现 POST /users/candidate/profile；要求候选人登录，所有者从认证用户取得。
- display_name 去首尾空白后非空；resume_text 默认空字符串，skills 默认空列表。技能去首尾空白、转小写、去空项、去重，并排序以稳定响应顺序。
- 恢复 CandidateProfilePublic，新增 normalize_skills、create_candidate_profile 及候选人角色业务异常；router 返回 201 / 401 / 403 / 409 / 422，复用现有角色依赖。
- 资料与技能通过 ORM 关系一次提交，数据库失败全部回滚；只确认资料已存在时转换为重复创建冲突。不修改已实现的雇主接口行为。
- 实际验证：SYManage 环境在 backend 目录执行 `python -m pytest tests/users/test_account_responses.py -q`，40 passed（本次候选人场景 13 项，既有回归 27 项）；schema / service / router 及测试 Ruff 检查通过。
- 覆盖资料和技能持久化、规范化和默认值、简历原文、重复创建不覆盖、非法输入不写入、未认证 / 雇主拒绝、客户端不能指定他人所有权，以及资料和技能均写入后的提交失败回滚。
- 状态：接口隔离验证通过，同步 docs/数据模型设计.md；现有表结构未变化，不生成新结构迁移，不连接业务数据库。没有验证实际 PostgreSQL 运行和并发行为；旧 schema 测试仍引用被注释的更新类型，未宣称完整测试套件通过。

## 2026-10-06：展开技能保存步骤

- 按用户要求，将 create_candidate_profile 的技能列表推导式展开为循环：逐条创建 CandidateSkill、设置 candidate_id、关联资料并显式 session.add。
- 原写法依赖 ORM 关系级联保存；新写法明确展示每条技能加入 Session，资料与技能仍统一 commit，不逐条提交。
- 验证：SYManage 环境执行 `python -m pytest tests/users/test_account_responses.py -q -k 'candidate_profile_saves or candidate_profile_failed_commit or candidate_profile_duplicate'`，4 passed；覆盖资料 / 技能实际持久化、重复提交及整体回滚。service.py 的 Ruff 检查通过。
- 状态：验证通过；未新增测试文件或修改接口契约。

## 2026-10-06：已确认接口复核与 PostgreSQL 建表

- 按用户要求复核当前负责范围：注册、登录、Swagger 表单认证、本人账户信息、两种角色依赖，以及候选人 / 雇主资料首次创建均已实现，没有发现需要先补齐的已确认接口。登出沿用前端清除 Token 的方案；资料读取 / 修改及其他业务接口不属于本次已确认范围。
- SYManage 环境执行 `python -m pytest tests/users/test_account_responses.py -q`，40 passed；model / schema / service / router 的 Ruff 检查通过。旧 test_schema.py 仍引用已被用户注释的更新类型，本次未宣称完整测试套件通过。
- 实际 PostgreSQL 原先没有表，登录查询报 relation "user" does not exist。已在 alembic/env.py 注册用户模型，生成初始迁移 e07644577837，补齐生成文件缺少的 sqlmodel 导入，并审查离线 PostgreSQL DDL。
- 按用户明确授权执行 `python -m alembic upgrade head`，成功创建 user、candidate_profile、employer_profile、candidate_skill，以及 alembic_version；没有新增业务接口或种子数据。
- 实际数据库验证：邮箱唯一索引、角色 CHECK、资料 / 技能外键、技能组合主键和规范化 CHECK、带时区时间列、迁移版本均通过；`python -m alembic check` 未发现模型与数据库的待迁移差异。检查时四张业务表均为零行。
- 运行中的实际服务验证：GET /docs 返回 200，未认证 GET /users/me 返回 401，不存在账户的 POST /users/login 返回 401，原建表前的 500 已消失。迁移文件与 env.py 的 Ruff 检查通过；同步 docs/数据模型设计.md。
- 状态：当前已确认接口及建表完成；完整注册 / 资料写入流程此前在隔离 SQLite 验证，本次未向业务 PostgreSQL 写入测试账户，也未验证 PostgreSQL 并发写入行为。
