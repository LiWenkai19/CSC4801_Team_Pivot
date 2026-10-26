import { useState } from "react";
import { Link } from "react-router-dom";
import type { Application, Slot } from "../../types";
import { useRemote } from "../../hooks/useRemote";
import { ErrorMessage } from "../../components/candidate/ErrorMessage";
import { ApiError } from "../../api/common_api";
import { candidateRequest as request } from "../../api/candidate_api";
/* 把后端四种英文状态映射为界面中文文字：组装字段对象，用于请求正文、状态返回或组件配置。const 不可重新绑定变量；对象的属性仍可更新。 */
const statusLabels = {
  /* 对象字段 Pending；冒号右侧是实际保存/发送的值，不是声明变量。 */
  Pending: "待处理",
  /* 对象字段 Interviewing；冒号右侧是实际保存/发送的值，不是声明变量。 */
  Interviewing: "面试中",
  /* 对象字段 Rejected；冒号右侧是实际保存/发送的值，不是声明变量。 */
  Rejected: "已拒绝",
  /* 对象字段 Accepted；冒号右侧是实际保存/发送的值，不是声明变量。 */
  Accepted: "已录用",
};
/* 把带时区的时间字符串格式化为上海时区的日期时间：箭头函数是稍后调用的回调；创建函数时不会立即执行函数体。const 不可重新绑定变量；对象的属性仍可更新。 */
const slotTime = (value: string) =>
  new Intl.DateTimeFormat("zh-CN", {
    /* 对象字段 明确按 Asia/Shanghai 显示，避免各电脑默认时区不同；冒号右侧是实际保存/发送的值，不是声明变量。 */
    timeZone: "Asia/Shanghai",
    /* 对象字段 日期的显示详细程度；冒号右侧是实际保存/发送的值，不是声明变量。 */
    dateStyle: "medium",
    /* 对象字段 时间的显示详细程度；冒号右侧是实际保存/发送的值，不是声明变量。 */
    timeStyle: "short",
  }).format(new Date(value));
/* BookingPanel：为本人面试中申请读取可用时段；提交失败若是冲突则刷新，成功交给外层刷新申请。 */
function BookingPanel({
  application,
  onBooked,
}: {
  /* 字段 一份申请的展示数据：Application。 */
  application: Application;
  /* 字段 预约完成后刷新申请列表的回调：() => void。 */
  onBooked: () => void;
}) {
  /* [revision, refresh]（刷新计数；改变它会让数据重新查询，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [revision, refresh] = useState(0);
  /* 一次查询的数据、错误和加载状态：自定义 Hook：按路径读取服务器数据；路径/刷新计数改变时重查，组件退出后忽略旧结果。const 不可重新绑定变量；对象的属性仍可更新。 */
  const state = useRemote<Slot[]>(
    `candidate/applications/${application.id}/slots`,
    revision,
  );
  /* [busy, setBusy]（是否正在提交，防止重复点击，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [busy, setBusy] = useState(false);
  /* [error, setError]（用于显示给用户的错误文字，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [error, setError] = useState("");
  /* return 把结果交给调用者并结束本次函数执行；组件返回的 JSX 是界面描述，普通函数返回数据/清理回调。 */
  return (
    /* 一组相关内容。 */ <section>
      {/* h3 组件/HTML 元素。 */}
      <h3>选择面试时段</h3>
      {/* p 组件/HTML 元素。 */}
      <p>以下时间均为 Asia/Shanghai（UTC+8）。</p>
      {/* JSX 花括号内计算动态内容：三元表达式：条件 ? 条件成立时的值 : 不成立时的值。&& 可用于按条件显示，map 用于逐项生成列表。 */}
      {state.loading ? (
        /* p 组件/HTML 元素。 */ <p>正在加载时段…</p>
      ) : state.error ? (
        <>
          {/* 按需显示错误提示；本标签的属性：error。 */}
          <ErrorMessage
            error={
              /* JSX 的 error 属性：使用 state.error 作为本步输入/结果。花括号让 JSX 使用 JavaScript 表达式。 */ state.error
            }
          />
          {/* 按钮；disabled 可以阻止重复提交；本标签的属性：onClick。 */}
          <button
            onClick={
              /* JSX 的 onClick 属性：点击时执行回调；渲染此按钮时不会立即执行。花括号让 JSX 使用 JavaScript 表达式。 */ () =>
                refresh((n) => n + 1)
            }
          >
            刷新时段
          </button>
        </>
      ) : (
        <>
          {/* JSX 花括号内计算动态内容：比较/计算 !state.data?.length && <p>暂无可用时段。</p>；=== 比较值，&& 要同时满足，?? 在 null/undefined 时使用备用值。&& 可用于按条件显示，map 用于逐项生成列表。 */}
          {!state.data?.length && (
            /* p 组件/HTML 元素。 */ <p>暂无可用时段。</p>
          )}
          {/* JSX 花括号内计算动态内容：逐项生成新的数组；用于职位卡片/时段/错误文字等列表展示。&& 可用于按条件显示，map 用于逐项生成列表。 */}
          {state.data?.map((slot) => (
            /* div 组件/HTML 元素；本标签的属性：className、key。 */ <div
              className="slot"
              key={
                /* JSX 的 key 属性：为列表项提供稳定身份，避免换序/换账户后复用错误组件。花括号让 JSX 使用 JavaScript 表达式。 */ slot.id
              }
            >
              {/* span 组件/HTML 元素。 */}
              <span>
                {/* JSX 花括号内计算动态内容：调用 slotTime，把括号内输入交给对应函数处理。&& 可用于按条件显示，map 用于逐项生成列表。 */}
                {slotTime(slot.starts_at)}
                {/* 显式保留分隔符两侧的空格，避免注释排版改变时间显示。 */}
                {" — "}
                {/* JSX 花括号内计算动态内容：调用 slotTime，把括号内输入交给对应函数处理。&& 可用于按条件显示，map 用于逐项生成列表。 */}
                {slotTime(slot.ends_at)}
              </span>
              {/* 按钮；disabled 可以阻止重复提交；本标签的属性：disabled、onClick。 */}
              <button
                disabled={
                  /* JSX 的 disabled 属性：布尔值控制能否点击，提交中/已申请时禁用。花括号让 JSX 使用 JavaScript 表达式。 */ busy
                }
                onClick={
                  /* JSX 的 onClick 属性：点击时执行回调；渲染此按钮时不会立即执行。花括号让 JSX 使用 JavaScript 表达式。 */ async () => {
                    /* 调用 setBusy 修改对应页面状态，React 会更新显示。 */
                    setBusy(true);
                    /* 调用 setError 修改对应页面状态，React 会更新显示。 */
                    setError("");
                    /* try 尝试异步操作；catch 处理失败，finally 保证解除 busy/loading，不论成功还是失败。 */
                    try {
                      /* await 等待异步结果；等待期间浏览器仍可处理其他事件。 */ /* await 等待异步结果；等待期间浏览器仍可处理其他事件。 */
                      await request(
                        `candidate/applications/${application.id}/booking`,
                        "POST",
                        {
                          /* 对象字段 面试时段 ID；冒号右侧是实际保存/发送的值，不是声明变量。 */
                          slot_id: slot.id,
                        },
                      );
                      /* 调用 onBooked，把括号内输入交给对应函数处理。 */
                      onBooked();
                    } catch (e) {
                      /* 捕获失败并显示错误文字；TypeScript 的 as Error 只说明类型，不会把失败变成成功。 */
                      /* 调用 setError 修改对应页面状态，React 会更新显示。 */
                      setError((e as Error).message);
                      /* if 检查 e instanceof ApiError && e.status === 409；成立才执行随后语句，提前 return 可阻止不该继续的路径。 */
                      if (e instanceof ApiError && e.status === 409)
                        /* 调用 refresh，把括号内输入交给对应函数处理。 */
                        refresh((n) => n + 1);
                    } finally {
                      /* 调用 setBusy 修改对应页面状态，React 会更新显示。 */
                      setBusy(false);
                    }
                  }
                }
              >
                预约
              </button>
            </div>
          ))}
        </>
      )}
      {/* 按需显示错误提示；本标签的属性：error。 */}
      <ErrorMessage
        error={
          /* JSX 的 error 属性：读取 用于显示给用户的错误文字。花括号让 JSX 使用 JavaScript 表达式。 */ error
        }
      />
    </section>
  );
}
/* ApplicationsPage：展示本人申请及四种状态；已有预约显示结果，否则符合条件才显示预约入口。 */
function ApplicationsPage() {
  /* [revision, refresh]（刷新计数；改变它会让数据重新查询，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [revision, refresh] = useState(0);
  /* 一次查询的数据、错误和加载状态：自定义 Hook：按路径读取服务器数据；路径/刷新计数改变时重查，组件退出后忽略旧结果。const 不可重新绑定变量；对象的属性仍可更新。 */
  const state = useRemote<Application[]>("candidate/applications", revision);
  /* [selected, setSelected]（目前展开预约时段的申请 ID，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [selected, setSelected] = useState<string | null>(null);
  /* return 把结果交给调用者并结束本次函数执行；组件返回的 JSX 是界面描述，普通函数返回数据/清理回调。 */
  return (
    <>
      {/* p 组件/HTML 元素；本标签的属性：className。 */}
      <p className="eyebrow">YOUR PROGRESS</p>
      {/* h1 组件/HTML 元素。 */}
      <h1>我的申请</h1>
      {/* JSX 花括号内计算动态内容：三元表达式：条件 ? 条件成立时的值 : 不成立时的值。&& 可用于按条件显示，map 用于逐项生成列表。 */}
      {state.loading ? (
        /* p 组件/HTML 元素。 */ <p>正在加载申请…</p>
      ) : state.error ? (
        <>
          {/* 按需显示错误提示；本标签的属性：error。 */}
          <ErrorMessage
            error={
              /* JSX 的 error 属性：使用 state.error 作为本步输入/结果。花括号让 JSX 使用 JavaScript 表达式。 */ state.error
            }
          />
          {/* 按钮；disabled 可以阻止重复提交；本标签的属性：onClick。 */}
          <button
            onClick={
              /* JSX 的 onClick 属性：点击时执行回调；渲染此按钮时不会立即执行。花括号让 JSX 使用 JavaScript 表达式。 */ () =>
                refresh((n) => n + 1)
            }
          >
            重试
          </button>
        </>
      ) : (
        <>
          {/* JSX 花括号内计算动态内容：比较/计算 !state.data?.length && ( <p> 尚未申请职位。<Link to="/candidate/jobs">浏览职位</Link> </p> )；=== 比较值，&& 要同时满足，?? 在 null/undefined 时使用备用值。&& 可用于按条件显示，map 用于逐项生成列表。 */}
          {!state.data?.length && (
            /* p 组件/HTML 元素。 */ <p>
              尚未申请职位。
              {/* React 路由链接，点击切换页面而不整页刷新；本标签的属性：to。 */}
              <Link to="/candidate/jobs">浏览职位</Link>
            </p>
          )}
          {/* JSX 花括号内计算动态内容：逐项生成新的数组；用于职位卡片/时段/错误文字等列表展示。&& 可用于按条件显示，map 用于逐项生成列表。 */}
          {state.data?.map((application) => (
            /* 单个职位或申请卡片；本标签的属性：className、key。 */ <article
              className="panel"
              key={
                /* JSX 的 key 属性：为列表项提供稳定身份，避免换序/换账户后复用错误组件。花括号让 JSX 使用 JavaScript 表达式。 */ application.id
              }
            >
              {/* span 组件/HTML 元素；本标签的属性：className。 */}
              <span className="badge">
                {/* JSX 花括号内计算动态内容：使用 statusLabels[application.status] 作为本步输入/结果。&& 可用于按条件显示，map 用于逐项生成列表。 */}
                {statusLabels[application.status]}
              </span>
              {/* h2 组件/HTML 元素。 */}
              <h2>
                {/* JSX 花括号内计算动态内容：使用 application.title 作为本步输入/结果。&& 可用于按条件显示，map 用于逐项生成列表。 */}
                {application.title}
              </h2>
              {/* p 组件/HTML 元素。 */}
              <p>
                {/* JSX 花括号内计算动态内容：使用 application.company_name 作为本步输入/结果。&& 可用于按条件显示，map 用于逐项生成列表。 */}
                {application.company_name}
              </p>
              {/* JSX 花括号内计算动态内容：三元表达式：条件 ? 条件成立时的值 : 不成立时的值。&& 可用于按条件显示，map 用于逐项生成列表。 */}
              {application.booking ? (
                /* p 组件/HTML 元素；本标签的属性：role。 */ <p role="status">
                  已预约：
                  {/* JSX 花括号内计算动态内容：调用 slotTime，把括号内输入交给对应函数处理。&& 可用于按条件显示，map 用于逐项生成列表。 */}
                  {slotTime(application.booking.starts_at)} —
                  {/* JSX 花括号内计算动态内容：使用固定字符串  。&& 可用于按条件显示，map 用于逐项生成列表。 */}{" "}
                  {/* JSX 花括号内计算动态内容：调用 slotTime，把括号内输入交给对应函数处理。&& 可用于按条件显示，map 用于逐项生成列表。 */}
                  {slotTime(application.booking.ends_at)}
                  （Asia/Shanghai，UTC+8）
                </p>
              ) : (
                application.status === "Interviewing" && (
                  <>
                    {/* 按钮；disabled 可以阻止重复提交；本标签的属性：onClick。 */}
                    <button
                      onClick={
                        /* JSX 的 onClick 属性：点击时执行回调；渲染此按钮时不会立即执行。花括号让 JSX 使用 JavaScript 表达式。 */ () =>
                          setSelected(
                            selected === application.id ? null : application.id,
                          )
                      }
                    >
                      选择面试时段
                    </button>
                    {/* JSX 花括号内计算动态内容：比较/计算 selected === application.id && ( <BookingPanel application={ application} onBooked={ () => { setSelected(null); refresh((n) => n + 1); }} /> )；=== 比较值，&& 要同时满足，?? 在 null/undefined 时使用备用值。&& 可用于按条件显示，map 用于逐项生成列表。 */}
                    {selected === application.id && (
                      /* 可复用的面试时段选择区域；本标签的属性：application、onBooked。 */ <BookingPanel
                        application={
                          /* JSX 的 application 属性：读取 一份申请的展示数据。花括号让 JSX 使用 JavaScript 表达式。 */ application
                        }
                        onBooked={
                          /* JSX 的 onBooked 属性：箭头函数是稍后调用的回调；创建函数时不会立即执行函数体。花括号让 JSX 使用 JavaScript 表达式。 */ () => {
                            /* 调用 setSelected 修改对应页面状态，React 会更新显示。 */
                            setSelected(null);
                            /* 调用 refresh，把括号内输入交给对应函数处理。 */
                            refresh((n) => n + 1);
                          }
                        }
                      />
                    )}
                  </>
                )
              )}
            </article>
          ))}
        </>
      )}
    </>
  );
}
export default ApplicationsPage;
