---
title: CSC4801 期末项目：招聘与候选人匹配
source: README.md
translator: AI 翻译稿，已经二次对照原文复查修订
---

# CSC4801 期末项目：招聘与候选人匹配

各团队将借助 AI 编码代理与规格驱动的工作流构建**一个全栈招聘平台**。产品是固定的：一个双边市场——候选人在其中查找并申请职位，雇主管理申请人，候选人在并发使用下安全地预约面试时段。

框架、语言、数据库、托管模式与可选增强由你们团队自行选择。所要求的匹配基线及其他可观察行为已在 [`REQUIREMENTS.md`](REQUIREMENTS.md) 中固定；除非明确标记为可选，需求均为强制性要求。

## Read these documents（阅读这些文档）

| 文档 | 用途 |
|---|---|
| [`REQUIREMENTS.md`](REQUIREMENTS.md) | 规范性产品需求与验收标准 |
| [`PEER_REVIEW.md`](PEER_REVIEW.md) | 必需的跨团队审计规程、有效发现标准与安全规则 |
| [`DOCKER.md`](DOCKER.md) | 如何从仓库的 `Dockerfile` 构建并运行环境 |
| [`templates/github/ISSUE_TEMPLATE/audit_bug_report.yml`](templates/github/ISSUE_TEMPLATE/audit_bug_report.yml) | 用于审计发现的 GitHub Issue Form；每个团队都要启用它 |
| [`templates/github/labels.yml`](templates/github/labels.yml) | 每个团队导入到其仓库的审计标签 |


## Grading（评分）

期末项目占**课程总成绩的 50%**。一份 50 分的初步团队总分用于对预期的十支团队排名：

| 组成部分 | 初步分值 |
|---|---:|
| 需求满足度（原始 100 分折算为 10 分） | 10 |
| 跨团队审计与修复 | 30 |
| 展示汇报 | 10 |
| **用于排名的总分** | **50** |


### 1. Requirements fulfillment（需求满足度）

学生**必须**（MUST）为 `REQUIREMENTS.md` 中的每一项功能需求编写自己的单元测试，并在 `README.md` 中做需求—测试映射。仅要求单元测试，包括 FP-TEST-1 中规定的安全与预约冲突逻辑。评分以已满足的需求数量为依据。学生有责任确保其测试正确且完整。

### 2. Cross-team audit and repair（跨团队审计与修复）

每支团队从 **0 审计分**起算。有效发现与有证据支持的修复会增加审计分。每一份报告与每一次审计操作都必须遵循 [`PEER_REVIEW.md`](PEER_REVIEW.md)。[排行榜](https://sra-research.github.io/CSC4801/project.html) 显示各团队的实时审计分。最终成绩依据团队排名，而非审计分的绝对数量。

#### 发现分

| 结果 | 分值 |
|---|---:|
| 安全缺陷 | +2 |
| 功能或性能缺陷 | +1 |
| 环境问题（例如，仓库的 `Dockerfile` 无法构建或运行） | +0.5 |
| 无效的缺陷报告 | -0.5 |
| 重复的缺陷报告 | 0 |

一个根因计为一项发现，即使它产生多个症状。

#### 修复分

| 结果 | 分值 |
|---|---:|
| 在修复截止时间前提交的有效修复记录、永久性修复 commit URL 与回归证据 | +2 |
| 不正确的修复或回归测试声明 | -0.5 |


#### 仓库可用性

仓库在公布的审计窗口期间必须保持公开可读。审计窗口内每不可用一小时扣除 `0.2` 审计分，扣分上限为 10 分。经教师确认的 GitHub 全站故障不计在内。


### 3. Presentation（展示汇报）

每支团队将向全班展示汇报其系统，并回答有关其实施的问题。展示汇报的评分依据是系统实施的清晰度、完备性与正确性，以及团队回答有关其设计与实施问题的能力。展示汇报也是展示团队所实现的任何可选增强的机会。

## Milestones（里程碑）

| 周次 | 必需的里程碑 |
|---|---|
| 1-2 | 组建三人团队并创建私有仓库。 |
| 3 | 公布期末项目与需求。 |
| 3-10 | 构建系统、测试、文档与种子数据。 |
| 11 | 功能冻结。测试必须在 `main` 分支上通过。 |
| 12 | 在审计窗口前将仓库设为公开。其他团队从你仓库 `main` 分支最新提交处的 `Dockerfile` 构建环境，并进行同伴审计。功能冻结后，`main` 上只做缺陷修复与文档更正。 |
| 第 12 周结束 | 完成修复与文档。提交 `main` 上确切被评分提交的永久 URL；其仓库 `Dockerfile` 必须能构建完整环境。 |
| 13-14 | 展示运行中的系统并回答实施问题。 |

确切日历日期公布在课程网站上。

## Audit window（审计窗口）

审计窗口为**第 12 周周一至周五 08:00-20:00（课程时区）**。仓库在整个窗口期间必须保持公开可读。延迟或中断的访问将受处罚。

所有审计均针对另一团队 `main` 分支最新提交处的源码，在审计者自己的机器上从仓库的 `Dockerfile` 构建。这是代码审查与本地测试，而非针对在线服务的渗透测试。每位审计者必须遵循 [`PEER_REVIEW.md`](PEER_REVIEW.md)。


## Starter repository（起始仓库）

[CSC4801_TeamA 起始仓库](https://github.com/sra-research/CSC4801_TeamA)提供了起始标题、占位单元测试函数，以及一份需求—测试映射表示例。学生应当使用该模板，在提交前补全文档、实现与真实的单元测试。

一个演示[分支](https://github.com/sra-research/CSC4801_TeamA/tree/codex/add-project-starter-scaffold)提供了一个玩具实现、缺陷报告与修复示例。

## Technology and AI resources（技术与 AI 资源）

提供 MiMo API 订阅，并推荐使用 Claude Code。允许使用其他编码代理，但学生需承担任何相关费用。使用 AI 不会减轻理解、审查、测试与保护所提交代码的责任。

---

## 译注

### 术语定译

本文档关键术语定译如下（与 `REQUIREMENTS 中文翻译.md` 冲突处以本清单为准）：

| 英文 | 定译 |
|---|---|
| MUST / MUST NOT / SHOULD / MAY | **必须**（MUST）/ **不得**（MUST NOT）/ **应当**（SHOULD）/ **可以**（MAY） |
| clean checkout | 干净检出 |
| seed data / seed | 种子数据（动词：灌入种子数据） |
| migration | 迁移 |
| unit test | 单元测试 |
| regression test | 回归测试 |
| smoke test | 冒烟测试 |
| requirement–test mapping | 需求—测试映射 |
| peer audit / peer review | 同伴审计 |
| bug | 缺陷 |
| bug report | 缺陷报告 |
| audit | 审计 |
| audit points | 审计分 |
| finding | 发现 |
| repair | 修复 |
| root cause | 根因 |
| feature freeze | 功能冻结 |
| audit window | 审计窗口 |
| the graded commit | 被评分提交 |
| documented command | 写入文档的命令 |
| undocumented | 未写入文档的 |
| secrets | 机密 |
| personal data | 个人数据 |
| leaderboard | 排行榜 |
| starter repository | 起始仓库（starter repository） |
| presentation | 展示汇报 |
| cross-team audit and repair | 跨团队审计与修复 |
| requirements fulfillment | 需求满足度 |
| matching baseline | 匹配基线 |
| security bug | 安全缺陷 |
| functional or performance bug | 功能或性能缺陷 |
| environmental issue | 环境问题 |
| invalid bug report | 无效的缺陷报告 |
| duplicate bug report | 重复的缺陷报告 |
| fix record | 修复记录 |
| regression evidence | 回归证据 |
| regression-test claim | 回归测试声明 |
| two-sided marketplace | 双边市场 |
| interview slot | 面试时段 |
| toy implementation | 玩具实现 |

状态枚举、角色标识符、HTTP 状态码、需求编号（FP-XXX-n）、文件路径、命令、URL 与 commit SHA 均原样保留，不翻译。

### 源文瑕疵与处理

1. **`leadboard` 拼写错误**（应为 leaderboard）。该句位于第 2 节 “Cross-team audit and repair” 开头段（任务说明写作 “Repository availability 前后”，与源文件实际位置略有出入，不影响处理方式）：正文链接文字译为“排行榜”，链接 URL `https://sra-research.github.io/CSC4801/project.html` 原样保留。原文拼写为 `leadboard`。
2. **“A demo [branch](…) provide a toy implementation, bug report and fix example.”** 主谓不一致（`provide` 应为 `provides`）。按语义正常译为“提供了一个玩具实现、缺陷报告与修复示例”，不保留错误的动词形态。
3. **“Feature freeze. tests must pass on the `main` branch.”** 后半句以小写 `tests` 起头，属排版瑕疵。正常译为“功能冻结。测试必须在 `main` 分支上通过。”
4. **评分表 “Requirements fulfillment (100 raw points scaled to 10)”** 括号内容准确译出为“（原始 100 分折算为 10 分）”，明确是原始 100 分折算为 10 分计入初步总分。

存疑决策（取最保守读法，未擅自补全）：

1. 任务说明称 `leadboard` 一句在 “Repository availability” 前后，源文件中该句实际位于第 2 节导语段。译文按源文件位置翻译，拼写瑕疵按指定方式处理。
2. 四级标题（`#### Finding points` 等）未在任务说明中规定格式。对照 `REQUIREMENTS 中文翻译.md` 的四级标题惯例（纯中文），译为“发现分 / 修复分 / 仓库可用性”；若主会话要求与二级/三级一致的“英文（中文）”格式，可再改。
3. “dummy unit-test functions” 译为“占位单元测试函数”（起始模板中的空测试桩），未译作“哑元/伪”，以免与 test doubles（测试替身）混淆。
4. “starter headings” 译为“起始标题”，指起始仓库提供的文档章节骨架标题；原文未进一步说明其具体形态。
5. “Only unit tests are required, including the security and booking conflict logic specified in FP-TEST-1.” 中 `including` 的修饰范围略有歧义（是“仅要求单元测试”这一范围包含二者，还是单元测试须覆盖二者）。译文取保守读法：“仅要求单元测试，包括 FP-TEST-1 中规定的安全与预约冲突逻辑”，与 FP-TEST-1 正文要求覆盖预约冲突逻辑的表述一致，不另作扩写。
6. “Late or interrupted access will result in a penalty.” 未给出处罚幅度。译为“将受处罚”，未擅自补成具体扣分值。
7. “the expected ten teams” 译为“预期的十支团队”，未理解为“期望上限”或其他含义。
8. 源文中非 RFC 加粗的普通 `must` / `should`（如仓库可读性、审计者遵循规程、使用起始模板等）译为“必须 / 应当”，不加（MUST）/（SHOULD）标记；仅第 1 节的 `**MUST**` 按定译标注英文。
9. “permanent fix commit URL” 按 `REQUIREMENTS 中文翻译.md` 的“永久性 GitHub commit URL”体例译为“永久性修复 commit URL”，保留 `commit` 原词。
10. 原文 “GitHub Issue Form” 为 GitHub 产品功能名，保留英文，未译作“议题表单”。

### 二次复查修订记录

1. 开篇句 "and candidates book interview slots safely under concurrent use" 初译作“并发使用下候选人安全地预约面试时段”，语序拗口且主语“候选人”位置游离，改为“候选人在并发使用下安全地预约面试时段”，与原文三分句并列结构（candidates / employers / candidates）对应。
2. "Valid findings and evidence-backed repairs add to the audit points." 中 "Valid findings" 初译“有效的发现”，与 `PEER_REVIEW 中文翻译.md` 定译“有效发现（valid finding）”不一致，统一为“有效发现”。
3. "Deduct 0.2 audit points per unavailable audit-window hour" 初译“每一不可用的审计窗口小时扣除 0.2 审计分”欧化拗口，改为“审计窗口内每不可用一小时扣除 0.2 审计分”，语义不变。
