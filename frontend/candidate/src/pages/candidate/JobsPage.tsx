import { useState } from "react";
import { Link } from "react-router-dom";
import type { Job } from "../../types";
import { useRemote } from "../../hooks/useRemote";
import { ErrorMessage } from "../../components/candidate/ErrorMessage";
import { ApplyButton } from "../../components/candidate/ApplyButton";
import { RecommendationScore } from "../../components/candidate/RecommendationScore";
/* JobsPage：显示后端已排序的全部有效职位，提供匹配分数、技能、描述入口和申请按钮。 */
function JobsPage() {
  /* [revision, refresh]（刷新计数；改变它会让数据重新查询，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [revision, refresh] = useState(0);
  /* 一次查询的数据、错误和加载状态：自定义 Hook：按路径读取服务器数据；路径/刷新计数改变时重查，组件退出后忽略旧结果。const 不可重新绑定变量；对象的属性仍可更新。 */
  const state = useRemote<Job[]>("candidate/jobs", revision);
  /* return 把结果交给调用者并结束本次函数执行；组件返回的 JSX 是界面描述，普通函数返回数据/清理回调。 */
  return (
    <>
      {/* p 组件/HTML 元素；本标签的属性：className。 */}
      <p className="eyebrow">EXPLORE OPPORTUNITIES</p>
      {/* h1 组件/HTML 元素。 */}
      <h1>职位推荐</h1>
      {/* p 组件/HTML 元素。 */}
      <p>职位按匹配分数从高到低排列。评分算法待开发，目前统一为 0 分占位，不代表真实匹配程度；同分按职位名称排序。</p>
      {/* JSX 花括号内计算动态内容：三元表达式：条件 ? 条件成立时的值 : 不成立时的值。&& 可用于按条件显示，map 用于逐项生成列表。 */}
      {state.loading ? (
        /* p 组件/HTML 元素。 */ <p>正在加载职位…</p>
      ) : state.error ? (
        <>
          {/* 按需显示错误提示；本标签的属性：error。 */}
          <ErrorMessage
            error={
              /* JSX 的 error 属性：使用 state.error 作为本步输入/结果。花括号让 JSX 使用 JavaScript 表达式。 */ state.error
            }
          />
          {/* JSX 花括号内计算动态内容：三元表达式：条件 ? 条件成立时的值 : 不成立时的值。&& 可用于按条件显示，map 用于逐项生成列表。 */}
          {state.status === 404 ? (
            /* React 路由链接，点击切换页面而不整页刷新；本标签的属性：to。 */ <Link to="/candidate/profile">
              填写我的资料
            </Link>
          ) : (
            /* 按钮；disabled 可以阻止重复提交；本标签的属性：onClick。 */ <button
              onClick={
                /* JSX 的 onClick 属性：点击时执行回调；渲染此按钮时不会立即执行。花括号让 JSX 使用 JavaScript 表达式。 */ () =>
                  refresh((n) => n + 1)
              }
            >
              重试
            </button>
          )}
        </>
      ) : (
        <>
          {/* JSX 花括号内计算动态内容：比较/计算 !state.data?.length && <p>暂时没有可申请的职位。</p>；=== 比较值，&& 要同时满足，?? 在 null/undefined 时使用备用值。&& 可用于按条件显示，map 用于逐项生成列表。 */}
          {!state.data?.length && (
            /* p 组件/HTML 元素。 */ <p>暂时没有可申请的职位。</p>
          )}
          {/* div 组件/HTML 元素；本标签的属性：className。 */}
          <div className="jobs">
            {/* JSX 花括号内计算动态内容：逐项生成新的数组；用于职位卡片/时段/错误文字等列表展示。&& 可用于按条件显示，map 用于逐项生成列表。 */}
            {state.data?.map((job) => (
              /* 单个职位或申请卡片；本标签的属性：className、key。 */ <article
                className="panel"
                key={
                  /* JSX 的 key 属性：为列表项提供稳定身份，避免换序/换账户后复用错误组件。花括号让 JSX 使用 JavaScript 表达式。 */ job.id
                }
              >
                {/* span 组件/HTML 元素；本标签的属性：className。 */}
                <RecommendationScore score={job.score} />
                {/* h2 组件/HTML 元素。 */}
                <h2>
                  {/* React 路由链接，点击切换页面而不整页刷新；本标签的属性：to。 */}
                  <Link
                    to={
                      /* JSX 的 to 属性：路由跳转目标。花括号让 JSX 使用 JavaScript 表达式。 */ `/candidate/jobs/${job.id}`
                    }
                  >
                    {/* JSX 花括号内计算动态内容：使用 job.title 作为本步输入/结果。&& 可用于按条件显示，map 用于逐项生成列表。 */}
                    {job.title}
                  </Link>
                </h2>
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
                {/* React 路由链接，点击切换页面而不整页刷新；本标签的属性：to。 */}
                <Link
                  to={
                    /* JSX 的 to 属性：路由跳转目标。花括号让 JSX 使用 JavaScript 表达式。 */ `/candidate/jobs/${job.id}`
                  }
                >
                  查看职位描述 →
                </Link>
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
              </article>
            ))}
          </div>
        </>
      )}
    </>
  );
}
export default JobsPage;
