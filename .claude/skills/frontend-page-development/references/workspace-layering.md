# 工作区架构与代码规律

来源：SYManage 工作区于 2026-10-15 的规范及实际前端代码。以下路径相对于项目根目录，供定位和类比；使用时重新核对，不依赖此项目的绝对路径。

本文件解释规则从哪里提取，以及如何映射到其他项目。用户要求的“默认一个页面或至多 15 个特定函数、功能描述先问清”属于 skill 的工作流程约束，并非声称原代码已有数量限制。

## 1. 实际层级与依据

```text
frontend/
  package.json                 构建、检查与依赖事实
  tsconfig.app.json            类型检查及导入约束
  .oxlintrc.json               Oxlint 配置
  src/
    main.tsx                   React 根节点、Router、AuthProvider
    App.tsx                    公开页面和 RequireAuth 下的受保护路由
    types.ts                   跨 API/页面使用的请求、响应与业务枚举
    api/
      common_api.ts            request / requestWithToken / fileRequest
      UserManage_api.ts        人员/白名单/任职交接接口
      finance_api.ts           财务业务接口
    contexts/
      AuthContext.tsx          AuthProvider / useAuth
    components/
      RequireAuth.tsx          登录守卫
      UserCard.tsx             接收 WhitelistPublic 的展示组件
      RecordList.tsx           接收 FinanceRecordPublic 的展示组件
    pages/
      NavPage.tsx               功能入口导航
      users/
        LoginPage.tsx           页面容器
        LoginForm.tsx           本业务表单
        RegisterPage.tsx
        UserManagePage.tsx      页面数据、筛选、弹窗与回调协调
        AddWhitelistModal.tsx   页面专用弹窗
        HandoverModal.tsx
      finance/
        FinancePage.tsx         页面数据及专用弹窗协调
        CreateRecordModal.tsx   录入并通过 onSubmit 通知父级
        RecordModal.tsx         读取记录并组合展示组件
        InvoiceUploadModal.tsx  选择文件、解析、核对、确认流程
    index.css                  已有全局样式与变量
    App.css                    既有样式，使用前核对实际引用
```

这体现了“按业务组织页面、按职责组织共用能力”的结构，而非所有东西都放在页面内。已有独立文件不等于必须创建同名文件；没有实际用途时不补空目录或占位模块。

| 来源 | 提取出的规律 | 使用时的边界 |
| --- | --- | --- |
| `CLAUDE.md` 的 Frontend / Working Style | 前后端类型对应，事件目标类型明确，中文解释改动的原因 | 其中阶段、版本和角色信息仍需用当前文件核对 |
| `main.tsx`、`App.tsx`、`RequireAuth.tsx` | Provider 在应用外层，路由声明与登录守卫独立 | 新增页面只接入现有结构，不重复创建 Router |
| `pages/users/`、`pages/finance/` | 页面与本业务的表单、弹窗就近组织 | 不强制将单页专用组件提升到全局 components |
| `UserCard.tsx`、`RecordList.tsx` | 展示组件接收有类型的数据 Props | 不因为现有例子简单，就往展示组件加入全局请求或业务权限流程 |
| `UserManagePage.tsx` | 原始列表与学年选择是 state；显示列表在 render 阶段派生 | 学年算法是此项目业务细节，不推广到其他页面 |
| `FinancePage.tsx` | 初次进入与写入成功后复用数据刷新函数；局部 loading 保持弹窗存活 | 关闭弹窗的具体时机按当前需求确定，不能依据注释猜测行为 |
| `CreateRecordModal.tsx`、`AddWhitelistModal.tsx` | 专用组件通过回调向父页面传达写入结果 | 本地追加与重新请求是两种策略，依据响应完整度及业务结果选择 |
| `InvoiceUploadModal.tsx` | 把响应填入表单、不可变更新明细、按状态提供后续动作 | 实际状态和允许回退路径必须与用户及后端契约核对 |
| `common_api.ts`、`finance_api.ts` | 公共请求机制与业务接口函数分离，业务 API 无 UI 副作用 | 不把固定后端地址或 localStorage 存储方式变成跨项目硬规则 |

## 2. 页面、子组件与状态的归属

当前有两种合理的组合方式：

- `LoginPage → LoginForm`：页面承担入口，专用表单处理输入、调用已有登录能力并导航。
- `UserManagePage / FinancePage → 专用 Modal → 回调`：父页面管理页面数据与打开状态，弹窗完成一条具体操作，再通知父级更新。

单页实现时沿用相近的邻近范例，不强制把两者统一成大型容器模式。跨页面确实共享的展示能力才放入 `components/`；组件是展示型还是业务型，按其职责与当前调用方判断，不能单看文件所在目录。

常见的一条写入数据流：

```text
页面打开弹窗
  → 用户编辑受控输入
  → 处理器校验并调用业务 API
  → 公共请求层发送请求 / 转换错误
  → 成功回调携带响应或通知刷新
  → 父页面更新数据
  → 按已约定规则保留、重置或关闭弹窗
```

`FinancePage` 明确保留弹窗挂载，余额区域自行展示 loading/error，防止刷新余额时丢失输入。将这一规律用于有同样生命周期需求的页面；没有子表单保留需求时，简单页面可以采用符合现状的整体加载态。

## 3. 请求与类型契约

`common_api.ts` 的实际职责：

- `request<T>`：基础 JSON 请求与统一错误处理。
- `requestWithToken<T>`：JSON 请求携带认证头；即使 GET/DELETE 无 body，也必须有认证头。
- `fileRequest<T>`：带认证的 FormData 请求，由浏览器生成 multipart Content-Type 和 boundary。
- `showError`：将 FastAPI 字符串 `detail`、422 校验数组及状态码兜底转换成可展示的 Error。

`finance_api.ts` 以 `getBalance`、`createFinanceRecord`、`uploadInvoice` 等函数描述业务动作，再委托公共层；页面不重复拼接基础地址和认证头。`UserManage_api.ts` 存在手动读 token 再调用 `request` 的旧写法：复用已有函数即可，新代码在适用时使用现有带认证封装，不为统一写法重构整模块。

当前公共封装成功时均调用 `response.json()`，这是现状而非普适保证。遇到 204、文件流或纯文本响应，要先核对契约，再在当前范围内采用正确处理方式；`Promise<void>` 的声明本身不保证服务器无响应体。

`types.ts` 集中放置共享请求/响应类型，如 `WhitelistCreate` 与 `WhitelistPublic`、`FinanceRecordCreate` 与 `FinanceRecordPublic`。组件的 `Props` 就近声明，避免把所有局部 UI 类型都堆到共享文件。金额常以字符串传输，可空字段、枚举、联合响应需逐项对齐；不要自动改为 number、空字符串或一个猜测的响应类型。

## 4. 登录与权限

- `AuthContext.tsx` 负责启动时恢复当前用户，以及 login/logout 更新 `currentUser` 与 loading；页面通过 `useAuth()` 使用这些状态。
- `RequireAuth.tsx` 先等待登录检查，再将未登录用户重定向到登录页，已登录时渲染 `Outlet`。
- `App.tsx` 将公开登录/注册与受保护业务页面分开；受保护页面接入既有守卫。
- 一些页面根据 `currentUser.permission` 展示操作。具体允许哪些角色是业务契约，不复制旧文档的角色列表，更不在前端擅自决定新的访问权限。

这是此项目的 Context + Router 结构。其他项目已有 store、服务端会话、路由 meta 或其他认证方式时保留其机制，复用相同的状态归属和调用方向即可。

## 5. 工具与实际限制

- `package.json` 当前使用 React 19、TypeScript、Vite、React Router，检查工具为 Oxlint；版本以实际依赖及安装内容为准，不把本快照的小版本写入新项目要求。
- `npm run build` 执行 `tsc -b && vite build`；`npm run lint` 执行 `oxlint`。当前没有定义 `test` script，不能声称运行了现成的前端测试套件。
- `tsconfig.app.json` 开启 `verbatimModuleSyntax`、`noUnusedLocals` 和 `noUnusedParameters`，使用自动 JSX 转换；仅作为类型使用的导入应使用 `import type`，不盲目保留无用的 React 值导入。
- 本工作区规范和表单代码使用 `React.SubmitEvent<HTMLFormElement>`；输入/下拉框使用对应元素的 `React.ChangeEvent<...>`。其他项目按自身已安装类型适配。
- `.oxlintrc.json` 配置 Hooks 规则和组件导出检查，验证时以其真实输出为准，不把 Context/Hook 相关的既有警告隐瞒成无问题。
- 全局 CSS 仍含模板样式，一些页面使用行内样式；未发现足以推广的完整视觉设计系统。新页面复用已使用的样式与变量，不能宣称仓库已经规定某个 UI 框架或组件库。

## 6. 应避免推广的旧实现与未完成内容

- 根 `CLAUDE.md` 和 `.claude/current-phase.md` 仍保留“仅登录/人员”的旧阶段描述，但当前路由和代码已有财务模块；路线图不能替代本轮授权，旧阶段记录也不能直接否认当前用户明确提出的任务。
- 旧文件有大小写与 snake_case/camelCase 混用、过时注释、缺少完整事件泛型、无用导入及零散错误处理。新改动遵守当前文件上下文与真实类型要求，不把不一致之处提升为统一标准。
- `GenR11tFormModal.tsx` 在本次读取时是尚未闭合的开发中代码，不作为页面模板。若之后全项目构建因此失败，应报告当时实际错误；本次提取 skill 未运行前端构建，不能据此断言当前构建结果。
- 对现有类型/后端返回字段差异、列表 key、权限展示或批量校验等问题，只在与本次明确任务有关时处理；创建或使用 skill 不自动授权修复全部历史代码。

## 7. 迁移到其他前端项目

先找真实页面入口、业务组件、共享组件、状态层、业务 API、公共请求层及契约位置。保留该项目已有框架、目录命名和依赖，把主文件中的职责映射过去。

可迁移的是业务归类、UI 与请求分离、状态所有权、明确回调与可验证流程；本项目的路径、接口地址、角色、金额类型、Context 方案及 React 事件类型都需要重新核对。默认范围与提问澄清约束继续执行。
