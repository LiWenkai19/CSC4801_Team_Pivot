import { useState } from "react";
import type { Job } from "../../types";
import { ApiError } from "../../api/common_api";
import { candidateRequest as request } from "../../api/candidate_api";
import { ApplicationFeedback, duplicateApplicationMessage } from "./ApplicationFeedback";
/* ApplyButton：提交本人申请；提交时禁用按钮，成功或重复冲突后刷新服务器的已申请标记。 */
export function ApplyButton({
  job,
  onApplied,
}: {
  /* 字段 一个职位的展示数据：Job。 */
  job: Job; /* 字段 申请完成后刷新列表/详情的回调：() => void。 */
  onApplied: () => void;
}) {
  /* [busy, setBusy]（是否正在提交，防止重复点击，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [busy, setBusy] = useState(false);
  /* [error, setError]（用于显示给用户的错误文字，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [error, setError] = useState("");
  /* return 把结果交给调用者并结束本次函数执行；组件返回的 JSX 是界面描述，普通函数返回数据/清理回调。 */
  return (
    /* div 组件/HTML 元素。 */ <div>
      {/* 按钮；disabled 可以阻止重复提交；本标签的属性：disabled、onClick。 */}
      <button
        disabled={
          /* JSX 的 disabled 属性：布尔值控制能否点击，提交中/已申请时禁用。花括号让 JSX 使用 JavaScript 表达式。 */ busy ||
          job.applied
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
                `candidate/jobs/${job.id}/applications`,
                "POST",
                {},
              );
              /* 调用 onApplied，把括号内输入交给对应函数处理。 */
              onApplied();
            } catch (e) {
              /* 捕获失败并显示错误文字；TypeScript 的 as Error 只说明类型，不会把失败变成成功。 */
              /* 调用 setError 修改对应页面状态，React 会更新显示。 */
              setError(e instanceof ApiError && e.status === 409
                ? duplicateApplicationMessage
                : (e as Error).message);
              /* if 检查 e instanceof ApiError && e.status === 409；成立才执行随后语句，提前 return 可阻止不该继续的路径。 */
              if (e instanceof ApiError && e.status === 409)
                /* 调用 onApplied，把括号内输入交给对应函数处理。 */
                onApplied();
            } finally {
              /* 调用 setBusy 修改对应页面状态，React 会更新显示。 */
              setBusy(false);
            }
          }
        }
      >
        {/* JSX 花括号内计算动态内容：三元表达式：条件 ? 条件成立时的值 : 不成立时的值。&& 可用于按条件显示，map 用于逐项生成列表。 */}
        {job.applied ? "已申请" : busy ? "提交中…" : "申请职位"}
      </button>
      {/* 按需显示错误提示；本标签的属性：error。 */}
      <ApplicationFeedback
        applied={job.applied}
        error={
          /* JSX 的 error 属性：读取 用于显示给用户的错误文字。花括号让 JSX 使用 JavaScript 表达式。 */ error
        }
      />
    </div>
  );
}
