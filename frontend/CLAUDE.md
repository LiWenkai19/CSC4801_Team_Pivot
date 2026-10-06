# 前端指令

本文件适用于 `frondend/` 及其子目录，与项目根目录 `AGENTS.md` 的通用约定共同使用。

## 前端类型与事件

- 前端 TypeScript 类型应与后端请求、响应及枚举定义保持同步；后端 schema 改动时检查对应前端类型与调用方。
- React 事件处理器使用匹配的元素类型，例如 `React.ChangeEvent<HTMLInputElement>`、`React.ChangeEvent<HTMLTextAreaElement>`、`React.ChangeEvent<HTMLSelectElement>` 和 `React.MouseEvent<HTMLButtonElement>`。
- 显式声明事件类型时，提供匹配的泛型元素参数。
- 表单提交事件类型以项目安装的 React 类型定义为准；检查 `FormEvent` / `SubmitEvent` 等类型是否可用及是否标记为弃用，不直接套用旧项目的版本结论。

## 前端开发与检查命令

以下为相同工具链下的示例；入口路径与 npm 脚本需核对新项目配置。

```sh
npm install
npm run dev
npm run build
npm run lint
```

- 检查 `package.json` 中脚本的实际内容，不默认 lint 一定使用 ESLint 或 Oxlint。
- 若 build 脚本使用 `tsc -b` 与 `vite build`，构建检查同时覆盖 TypeScript 编译与前端打包。