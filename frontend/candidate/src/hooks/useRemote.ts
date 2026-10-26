import { useEffect, useState } from "react";
import { candidateRequest as request } from "../api/candidate_api";
/* useRemote：自定义 Hook：按路径读取服务器数据；路径/刷新计数改变时重查，组件退出后忽略旧结果。泛型 T 是调用方指定的数据类型，不是固定数据库表。 */
export function useRemote<T>(path: string, revision = 0) {
  /* [data, setData]（从后端读取的数据，尚未得到结果时为 null，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [data, setData] = useState<T | null>(null);
  /* [error, setError]（用于显示给用户的错误文字，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [error, setError] = useState("");
  /* [status, setStatus]（HTTP 状态码，区分未登录、越权、缺失和冲突，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [status, setStatus] = useState(0);
  /* [loading, setLoading]（是否还在等待结果，用于显示加载提示，第二项是更新函数）：useState 保存页面状态，返回 [当前值, 修改函数]；修改后 React 重新渲染。const 不可重新绑定变量；对象的属性仍可更新。 */
  const [loading, setLoading] = useState(true);
  /* 启动异步请求：then 保存成功结果，catch 显示失败，finally 解除加载；旧页面的结果通过 active 检查丢弃。 */
  useEffect(() => {
    /* 组件是否仍接收结果；旧请求不能覆盖新页面：使用 true 作为本步输入/结果。let 允许后面重新赋值，例如把 active 改为 false。 */
    let active = true;
    /* 调用 setLoading 修改对应页面状态，React 会更新显示。 */
    setLoading(true);
    /* 调用 setError 修改对应页面状态，React 会更新显示。 */
    setError("");
    /* 调用 setStatus 修改对应页面状态，React 会更新显示。 */
    setStatus(0);
    /* 调用 setData 修改对应页面状态，React 会更新显示。 */
    setData(null);
    /* 启动异步请求：then 保存成功结果，catch 显示失败，finally 解除加载；旧页面的结果通过 active 检查丢弃。 */
    request<T>(path)
      .then((value) => {
        /* if 检查 active；成立才执行随后语句，提前 return 可阻止不该继续的路径。 */
        if (active)
          /* 调用 setData 修改对应页面状态，React 会更新显示。 */
          setData(value);
      })
      .catch((e) => {
        /* if 检查 active；成立才执行随后语句，提前 return 可阻止不该继续的路径。 */
        if (active) {
          /* 调用 setError 修改对应页面状态，React 会更新显示。 */
          setError(e.message);
          /* 调用 setStatus 修改对应页面状态，React 会更新显示。 */
          setStatus(e.status ?? 0);
        }
      })
      .finally(() => {
        /* if 检查 active；成立才执行随后语句，提前 return 可阻止不该继续的路径。 */
        if (active)
          /* 调用 setLoading 修改对应页面状态，React 会更新显示。 */
          setLoading(false);
      });
    /* return 把结果交给调用者并结束本次函数执行；组件返回的 JSX 是界面描述，普通函数返回数据/清理回调。 */
    return () => {
      /* 将右侧值赋给 active，改变数据；单个 = 不是比较运算。 */
      active = false;
    };
  }, [path, revision]);
  /* return 把结果交给调用者并结束本次函数执行；组件返回的 JSX 是界面描述，普通函数返回数据/清理回调。 */
  return { data, error, status, loading };
}
