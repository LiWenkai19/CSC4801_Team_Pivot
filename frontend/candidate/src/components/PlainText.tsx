/* 本文件参与候选人请求、认证或页面初始化。注释解释调用时机和数据来源；类型声明本身不会执行数据库或网络操作。 */

/* PlainText：把用户文字作为 React 文本节点显示，自动转义 HTML；禁止用 innerHTML 执行简历内容。 */
export function PlainText({
  children,
}: {
  /* 字段 组件内部包住的内容，由外层传入：string。 */
  children: string;
}) {
  /* return 把结果交给调用者并结束本次函数执行；组件返回的 JSX 是界面描述，普通函数返回数据/清理回调。 */
  return (
    /* div 组件/HTML 元素；本标签的属性：className。 */ <div className="plain-text" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
      {/* JSX 花括号内计算动态内容：读取 组件内部包住的内容，由外层传入。&& 可用于按条件显示，map 用于逐项生成列表。 */}
      {children}
    </div>
  );
}
