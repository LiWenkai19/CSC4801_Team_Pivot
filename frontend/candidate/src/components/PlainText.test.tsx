/* 测试必须实际操作页面/渲染组件再断言。await 等待操作完成；expect 不满足就报错，截图只是补充证据。 */

/* 从 react-dom/server 导入后面要用的函数、组件或类型；import type 只用于编译检查，不生成运行时代码。 */
import { renderToStaticMarkup } from "react-dom/server";
/* 从 vitest 导入后面要用的函数、组件或类型；import type 只用于编译检查，不生成运行时代码。 */
import { expect, test } from "vitest";
/* 从 ./PlainText 导入后面要用的函数、组件或类型；import type 只用于编译检查，不生成运行时代码。 */
import { PlainText } from "./PlainText";

/* 定义 Playwright/Vitest 测试，测试回调中的断言必须全部通过。 */
test("user supplied script is escaped by the actual text renderer", () => {
  /* html：调用 renderToStaticMarkup，把括号内输入交给对应函数处理。const 不可重新绑定变量；对象的属性仍可更新。 */
  const html = renderToStaticMarkup(
    /* 安全显示纯文本，用户输入不会作为 HTML 执行。 */ <PlainText>
      {/* JSX 花括号内计算动态内容：使用固定字符串 <script>alert(1)</script>
Resume。&& 可用于按条件显示，map 用于逐项生成列表。 */}
      {"<script>alert(1)</script>\nResume"}
    </PlainText>,
  );
  /* 断言实际页面/输出满足预期；不满足时测试失败，不用截图代替断言。 */
  expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");
  /* 断言实际页面/输出满足预期；不满足时测试失败，不用截图代替断言。 */
  expect(html).not.toContain("<script>");
  /* 断言实际页面/输出满足预期；不满足时测试失败，不用截图代替断言。 */
  expect(html).toContain("\nResume");
});
