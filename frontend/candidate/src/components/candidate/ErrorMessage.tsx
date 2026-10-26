/* ErrorMessage：有错误时显示带 role=alert 的提示，没有错误时不渲染元素。 */
export function ErrorMessage({
  error,
}: {
  /* 字段 用于显示给用户的错误文字：string。 */
  error: string;
}) {
  /* return 把结果交给调用者并结束本次函数执行；组件返回的 JSX 是界面描述，普通函数返回数据/清理回调。 */
  return error ? (
    /* p 组件/HTML 元素；本标签的属性：role、className。 */ <p
      role="alert"
      className="error"
    >
      {/* JSX 花括号内计算动态内容：读取 用于显示给用户的错误文字。&& 可用于按条件显示，map 用于逐项生成列表。 */}
      {error}
    </p>
  ) : null;
}
