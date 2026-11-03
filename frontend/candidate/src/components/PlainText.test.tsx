


import { renderToStaticMarkup } from "react-dom/server";

import { expect, test } from "vitest";

import { PlainText } from "./PlainText";


test("user supplied script is escaped by the actual text renderer", () => {

  const html = renderToStaticMarkup(
     <PlainText>
      {"<script>alert(1)</script>\nResume"}
    </PlainText>,
  );

  expect(html).toContain("&lt;script&gt;alert(1)&lt;/script&gt;");

  expect(html).not.toContain("<script>");

  expect(html).toContain("\nResume");
});
