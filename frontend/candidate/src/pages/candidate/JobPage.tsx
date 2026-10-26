import { useState } from "react";
import { RecommendationScore } from "../../components/candidate/RecommendationScore";
import { Link, useParams } from "react-router-dom";
import type { Job } from "../../types";
import { useRemote } from "../../hooks/useRemote";
import { ErrorMessage } from "../../components/candidate/ErrorMessage";
import { ApplyButton } from "../../components/candidate/ApplyButton";
import { PlainText } from "../../components/PlainText";
/* JobPage：读取 URL 中的职位 ID，展示职位描述和实时分数，复用申请按钮。 */
function JobPage() {
  /* { jobId }：读取浏览器 URL 中冒号参数对应的 ID。const 不可重新绑定变量；对象的属性仍可更新。 */
  const { jobId } = useParams();
  /* [revision, refresh]（刷新计数；改变它会让数据重新查询，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [revision, refresh] = useState(0);
  /* 一次查询的数据、错误和加载状态：自定义 Hook：按路径读取服务器数据；路径/刷新计数改变时重查，组件退出后忽略旧结果。const 不可重新绑定变量；对象的属性仍可更新。 */
  const state = useRemote<Job>(`candidate/jobs/${jobId}`, revision);
  /* if 检查 state.loading；成立才执行随后语句，提前 return 可阻止不该继续的路径。 */
  if (state.loading)
    /* return 把结果交给调用者并结束本次函数执行；组件返回的 JSX 是界面描述，普通函数返回数据/清理回调。 */
    return /* p 组件/HTML 元素。 */ <p>正在加载职位…</p>;
  /* if 检查 state.error || !state.data；成立才执行随后语句，提前 return 可阻止不该继续的路径。 */
  if (state.error || !state.data)
    /* return 把结果交给调用者并结束本次函数执行；组件返回的 JSX 是界面描述，普通函数返回数据/清理回调。 */
    return (
      <>
        {/* 按需显示错误提示；本标签的属性：error。 */}
        <ErrorMessage
          error={
            /* JSX 的 error 属性：使用 state.error 作为本步输入/结果。花括号让 JSX 使用 JavaScript 表达式。 */ state.error
          }
        />
        {/* React 路由链接，点击切换页面而不整页刷新；本标签的属性：to。 */}
        <Link to="/candidate/jobs">返回职位列表</Link>
      </>
    );
  /* 一个职位的展示数据：使用 state.data 作为本步输入/结果。const 不可重新绑定变量；对象的属性仍可更新。 */
  const job = state.data;
  /* return 把结果交给调用者并结束本次函数执行；组件返回的 JSX 是界面描述，普通函数返回数据/清理回调。 */
  return (
    <>
      {/* React 路由链接，点击切换页面而不整页刷新；本标签的属性：to。 */}
      <Link to="/candidate/jobs">← 职位推荐</Link>
      {/* 一组相关内容；本标签的属性：className。 */}
      <section className="panel">
        {/* span 组件/HTML 元素；本标签的属性：className。 */}
        <RecommendationScore score={job.score} />
        {/* h1 组件/HTML 元素。 */}
        <h1>
          {/* JSX 花括号内计算动态内容：使用 job.title 作为本步输入/结果。&& 可用于按条件显示，map 用于逐项生成列表。 */}
          {job.title}
        </h1>
        {/* p 组件/HTML 元素。 */}
        <p>
          {/* JSX 花括号内计算动态内容：使用 job.company_name 作为本步输入/结果。&& 可用于按条件显示，map 用于逐项生成列表。 */}
          {job.company_name}
        </p>
        {/* div 组件/HTML 元素；本标签的属性：className。 */}
        <div className="skills">
          {/* JSX 花括号内计算动态内容：逐项生成新的数组；用于职位卡片/时段/错误文字等列表展示。&& 可用于按条件显示，map 用于逐项生成列表。 */}
          {job.required_skills.map((skill) => (
            /* span 组件/HTML 元素；本标签的属性：key。 */ <span
              key={
                /* JSX 的 key 属性：为列表项提供稳定身份，避免换序/换账户后复用错误组件。花括号让 JSX 使用 JavaScript 表达式。 */ skill
              }
            >
              {/* JSX 花括号内计算动态内容：读取 skill。&& 可用于按条件显示，map 用于逐项生成列表。 */}
              {skill}
            </span>
          ))}
        </div>
        {/* h2 组件/HTML 元素。 */}
        <h2>职位描述</h2>
        {/* 安全显示纯文本，用户输入不会作为 HTML 执行。 */}
        <PlainText>
          {/* JSX 花括号内计算动态内容：使用 job.description 作为本步输入/结果。&& 可用于按条件显示，map 用于逐项生成列表。 */}
          {job.description}
        </PlainText>
        {/* 可复用的职位申请按钮；本标签的属性：job、onApplied。 */}
        <ApplyButton
          job={
            /* JSX 的 job 属性：读取 一个职位的展示数据。花括号让 JSX 使用 JavaScript 表达式。 */ job
          }
          onApplied={
            /* JSX 的 onApplied 属性：箭头函数是稍后调用的回调；创建函数时不会立即执行函数体。花括号让 JSX 使用 JavaScript 表达式。 */ () =>
              refresh((n) => n + 1)
          }
        />
      </section>
    </>
  );
}
export default JobPage;
