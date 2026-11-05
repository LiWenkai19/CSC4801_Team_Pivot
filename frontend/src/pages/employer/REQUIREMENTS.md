# 雇主前端需求摘录

来源：[需求原文](../../../../docs/REQUIREMENTS.md)、[中文翻译](../../../../docs/REQUIREMENTS%20中文翻译.md)、[页面规划](../../../../docs/雇主前端页面规划.md)。原文为规范依据；实施与验证结果见 [完成报告](../../../../docs/雇主前端完成报告.md)。

## 本模块必须满足

- **FP-EMP-1**：雇主能查看、编辑公司名称和描述；创建资料沿用 `/employer/details`。
- **FP-EMP-2**：雇主能增删改查本人职位。标题和描述不能只有空白；技能列表可为空。有申请或面试时段时删除应返回 409，保持数据不变。其他雇主管理该职位应返回 403。
- **FP-EMP-3**：申请人按分数降序展示，每行包含身份、技能、匹配分、状态和面试预约。仅职位所有者可设置 Pending、Interviewing、Rejected、Accepted 四种状态。
- **FP-MATCH-1（雇主侧）**：直接显示后端分数及顺序。技能经 trim、lowercase、去空、去重后，要求为空得 100，否则为 `floor(100 * 交集数量 / 要求数量)`。同分按显示名忽略大小写、再按稳定候选人 ID 排序；简历不参与打分。
- **FP-AUTH-3 / FP-SEC-1**：复用登录守卫及角色提示；真实权限由后端校验。未认证、无权、对象缺失应分别表现为登录跳转/401、403、404。
- **FP-SCHED-2（仅关联展示）**：显示已有预约的准确起止时间与 UTC 时区；申请离开 Interviewing 后预约仍关联该申请。
- **FP-SEC-3 / FP-SEC-4**：将用户内容作为文本渲染；自动测试使用隔离数据，不访问业务库或第三方服务。

## 页面与接口

| 页面 | 路由 | 后端接口 |
| --- | --- | --- |
| 公司资料 | `/employer/company` | GET/PATCH `/employer/company` |
| 职位列表 | `/employer/jobs` | GET `/employer/jobs`、DELETE `/employer/jobs/{id}` |
| 共用职位表单 | `/employer/jobs/new`、`/employer/jobs/:jobId/edit` | POST `/employer/jobs`、GET/PATCH `/employer/jobs/{id}` |
| 职位详情及申请人 | `/employer/jobs/:jobId` | GET `/employer/jobs/{id}`、GET `/employer/jobs/{id}/applications`、PATCH `/employer/applications/{id}/status` |

## 交互验收

空白公司名、职位标题和描述在前端拦截；公司 PATCH 只发送修改字段。逗号技能输入转为数组，空输入提交 `[]` 清空技能。提交期间防重复，失败保留输入并允许重试；成功更新显示或返回列表。公司 404 引导已有补填页；职位/申请 403、404 提示服务端消息并提供返回入口；删除 409 显示依赖冲突，204 正常移除列表记录。

候选人推荐与申请、面试时段管理、预约资格与并发预约不在本页面规划范围。完整 FP-SCHED-1～3 仍须后续模块实现，预约显示不能替代预约功能。
