# 前端进度

## 2026-10-19：注册、登录及登录守卫统一资料补填引导

- 用户确认四个目标源文件的实现方案，并额外授权同步本进度文档；函数模式预计 10 个新增或实质修改函数，不修改其他源文件。
- AuthContext 统一根据认证响应的 user 建立登录态、计算目标地址；register / login 返回 Promise<AuthDestination>，不在认证成功后额外请求 /me。刷新页面仍用原有 /me 恢复登录状态，资料保存后仍复用 refreshCurrentUser。
- RegisterPage 移除定时器及跳回登录页的分支；LoginForm 移除固定跳主页，二者均直接跳转认证返回的地址。RequireAuth 对资料未完成者拦截主页及错误角色资料页，同时放行本人资料页以避免重定向循环。
- 状态：本次浏览器交互及隔离联调验证通过；仅修改四个已确认的源文件和本进度文档，保留用户对登录页标题等已有修改。
- 函数模式实际 10 个函数：AuthContext.tsx 的 getAuthDestination、AuthProvider、finishAuthentication、login、register（5）；RegisterPage.tsx 的 RegisterPage、handleSubmit（2）；LoginForm.tsx 的 LoginForm、handleLogin（2）；RequireAuth.tsx 的 RequireAuth（1）。既有注销、资料刷新和输入事件逻辑保持原样。
- 浏览器验证：两种角色均通过 UI 注册后直接进入各自资料页；未完成时登录直接补填；手输 /navpage、另一角色资料地址以及刷新页面均不能绕过补填，并正确放行自己的资料页。填写最少资料后进入主页，注销后再次登录和刷新均保持在主页。确认密码不一致、错误密码、重复邮箱均保留输入并显示错误；登录失败后访问主页会返回登录页，不残留旧登录态。
- 数据验证：真实浏览器调用实际 FastAPI 服务，但服务仍连接系统临时目录中的隔离 SQLite；两种角色各只有一个测试账户，预期名称的资料均已持久化。未连接业务 PostgreSQL、未修改后端；localhost:5173 测试会话与用户在 127.0.0.1:5173 的会话分离。
- 静态检查：`npm run lint` 返回 0，保留 NavPage 未使用 Link 和 AuthContext Fast Refresh 的既有警告；`node_modules/.bin/tsc.cmd -p tsconfig.app.json --incremental false --noUnusedLocals false --noUnusedParameters false` 返回 0。`npm run build` 仍被 main.tsx:1、NavPage.tsx:2/3、LoginPage.tsx:2 的既有未使用导入阻塞；已授权改动的 RequireAuth 中未使用 React 导入随修改清除。本次未扩展到其他文件修复构建。
- 已重新读取四个最终源文件并核对 diff，`git diff --check` 对本次文件通过。浏览器验证截图：C:/Users/10677/AppData/Local/Temp/codex-auth-routing-verified.png，展示资料已完成用户登录后进入主页的结果。

## 2026-10-19：雇主公司资料表单、页面及路由

- 已完成 EmployerForm.tsx 与 EmployerDetailsPage.tsx：公司名称去首尾空白后必填，公司描述选填并保留原文；提交期间禁用操作，保存失败保留输入。Page 复用 createEmployerProfile、ApiError 和 refreshCurrentUser，处理 409 及保存后的状态确认重试。
- 用户明确确认额外修改 App.tsx 和本进度文档；已将 /employer/details 放入现有 RequireAuth 登录守卫中。未修改其他源文件或后端。
- 状态：浏览器交互及隔离联调验证通过。未登录进入登录页，候选人访问返回主页；空名称被浏览器拦截，纯空白名称显示校验提示；仅填公司名称可保存成功并跳转主页，完成后再次访问不重复填写。已观察提交期间输入与按钮禁用。
- 错误恢复：仅对隔离测试账号注入 SQLite 保存故障，验证错误提示、输入保留和无资料残留；解除故障后保存成功。另对该测试账号临时改变认证邮箱，使保存后的 /me 确认失败，验证“重新检查”入口；恢复测试邮箱后点击重试可进入主页。故障触发器均已删除，测试邮箱已恢复。
- 并发 / 重复：另一客户端先保存同一隔离账号资料后，页面提交收到 409，刷新状态后进入主页；SQLite 断言原公司名称没有被覆盖。隔离库同时确认公司名称去首尾空白、描述保留换行和首尾空白，以及描述可留空。
- 静态检查：`npm run lint` 返回 0（保留原有 NavPage 未使用 Link 与 AuthContext Fast Refresh 警告）；`node_modules/.bin/tsc.cmd -p tsconfig.app.json --incremental false --noUnusedLocals false --noUnusedParameters false` 返回 0。`npm run build` 仍被 RequireAuth.tsx:1、main.tsx:1、NavPage.tsx:2/3、LoginPage.tsx:2 的既有未使用导入阻塞，本轮未修改这些文件。已重新读取本次路由及页面，核对 diff。
- 预览与测试边界：复用先前系统临时目录中的隔离 SQLite 后端，未连接业务 PostgreSQL；浏览器使用 localhost:5173 独立登录会话，不改变用户在 127.0.0.1:5173 的登录状态。保留 http://localhost:5173/employer/details 的 employer-view@example.com 临时预览账号及未提交示例，截图为 C:/Users/10677/AppData/Local/Temp/codex-employer-details.png。注册 / 登录自动跳转仍为后续工作。

## 2026-10-19：候选人资料表单与页面

- 用户要求先实现候选人表单以便查看，并将技能输入改为按钮逐次添加输入框。范围：一个候选人资料页面及其必要关联接入；雇主页、注册 / 登录自动跳转不在本次范围内。
- 已实现 CandidateForm 的名称校验、选填简历、技能动态增加 / 删除、稳定行 ID、过滤空技能、提交禁用及失败保留输入；CandidateDetailsPage 调用真实资料接口，成功后刷新 /me 并进入 /navpage，409 改为重新检查状态，保存后状态查询失败可单独重试。
- 关联修改：UserPublic 同步 profile_completed；AuthContext 增加不触发全局 loading 的 refreshCurrentUser；API 错误保留状态码；App 增加受认证保护的 /candidate/details 路由。未修改后端。
- 状态：本次交互及隔离联调验证通过；完整项目构建仍受既有未使用导入阻塞。使用原生表单及必要可读样式，不新增依赖，保留工作区原有改动。
- 静态检查：`npm run lint` 返回 0，保留 AuthContext 的 Fast Refresh 和 NavPage 未使用 Link 的既有警告；本次涉及文件的 Oxlint 检查返回 0。`node_modules/.bin/tsc.cmd -p tsconfig.app.json --noUnusedLocals false --noUnusedParameters false` 返回 0，类型兼容性通过；`npm run build` 失败点为 RequireAuth.tsx:1、main.tsx:1、NavPage.tsx:2/3、LoginPage.tsx:2 的未使用导入，本轮未修改这些无关文件。`git diff --check -- frontend` 通过，已重新读取代码并复核 diff。
- 浏览器验证：Chrome 实际操作通过未登录跳转、空白名称拒绝、逐次添加技能、删除中间技能后保留其他行、空技能过滤、提交成功刷新并进入主页、已有资料阻止重复填写。隔离库断言名称裁剪、简历原文及技能规范化持久化正确。
- 失败恢复验证：仅在临时 SQLite 测试库插入故障触发器，验证保存失败显示错误并保留全部输入，且无资料残留；已移除测试触发器。通过模拟另一标签页先保存资料，验证当前页面遇到 409 后刷新状态并进入主页。保存成功后 /me 查询失败的单独重试分支已实现，本轮未注入该特定故障。
- 预览：Vite 127.0.0.1:5173；实际后端在 127.0.0.1:8000 使用系统临时目录下 csc4801-candidate-preview-* 中的隔离 SQLite，不连接业务 PostgreSQL。Chrome 保留 /candidate/details 页面及未提交的 Python / SQL 示例技能；预览使用 candidate-view@example.com 临时账号，截图在 C:/Users/10677/AppData/Local/Temp/codex-candidate-details.png。未向业务库写测试账户，未修改后端文件；预览服务停止后不应将临时账户视为正式账户。

## 2026-10-18：创建角色资料页面文件，暂不实现

- 用户认可两种角色各自 Page / Form 的组织方式，明确要求先创建文件并讨论一个文件的写法，暂不实现。
- 新增空文件 src/pages/users/CandidateDetailsPage.tsx、EmployerDetailsPage.tsx、EmployerForm.tsx；CandidateForm.tsx 已存在，保留原内容，未覆盖已有空函数及导入。
- 已核对三个新文件为空，并校验 CandidateForm.tsx 创建前后的 SHA256 一致。未增加组件实现、路由接入、API 调用或类型变更；未运行构建及交互测试。
- 当前讨论对象：CandidateForm.tsx；建议负责字段输入、名称校验和通过 onSubmit 向 Page 提交数据，Page 负责 API、提交状态、错误及成功后跳转。可选字段是否本次展示、技能输入方式尚未确定，当前仍为待细化。

## 2026-10-08：登录表单提交状态

- src/pages/users/LoginForm.tsx 复用认证 Context 的 loading 状态，加载期间阻止重复提交并禁用登录按钮，按钮显示“登录中...”；有效提交开始时清除上次错误，保持原有表单样式。
- 验证：npm run lint 返回 0，AuthContext 仍有警告；npm run build 未通过，剩余错误为 App、RequireAuth、main、NavPage、LoginPage 的未使用 React 导入及 AuthContext 的未使用 error 参数，LoginForm 无类型错误。未进行浏览器交互或后端联调。

## 2026-10-07：注册页补齐角色选择

- 在 src/pages/users/RegisterPage.tsx 增加候选人 / 雇主下拉框，沿用现有表单的间距、宽度及 loading 禁用行为；绑定已有 role 状态并通过 createUser 提交，默认及注册成功后仍为 candidate。
- 移除该页面未使用的 UserCreate 类型导入。
- 验证：npm run lint 返回 0，其他模板文件仍有警告；npm run build 未通过，报错位于其他文件的未使用导入 / 参数，以及 NavPage 的 username 与 UserPublic 不匹配，RegisterPage 未报类型错误。未进行浏览器交互或实际注册联调。

## 2026-10-07：沿用现有模板补齐用户 API

- 用户要求先对接已有及尚未接上的后端用户接口；保留认证上下文、路由结构和模板请求封装，不再次清理这些文件。
- 修改 src/api/common_api.ts：注册增加必填 role，注册 / JSON 登录返回 AuthResponse 并保存 Token；补齐 getUserPublic，并保留 getCurrentUser 兼容名称；新增 /token 表单认证和候选人 / 雇主资料首次提交函数。登出继续只清除本地 Token，原文件上传与请求封装保留。
- 修改 src/types.ts：新增 CandidateProfilePublic、EmployerProfilePublic，与当前后端响应字段一致。当前已实现的六个后端端点均有 API 调用函数。
- 验证：API / types 独立严格 TypeScript 检查通过；Node 临时脚本执行实际 API 实现，使用 fetch 替身检查六个端点、两种注册角色、请求体及可选字段、认证响应、Bearer 头、Token 保存 / 清除，以及 401 / 403 / 409 / 422 错误传播，均通过。未写入业务数据库。
- npm run lint 返回 0，保留模板文件仍有警告；npm run build 未通过，现有 App 引用的页面及 react-router-dom 缺失，AuthContext / RequireAuth 的 userPublic、UserPublic、CurrentUser、currentUser 名称还未统一，另有未使用导入 / 参数。这些文件正在由用户清理，本次未修改。
- 实际 HTTP 联调未完成：尝试访问 127.0.0.1:8000 时连接被拒绝。当前完成的是 API 调用与类型对接，未新增页面、表单、跳转流程或后端接口。
