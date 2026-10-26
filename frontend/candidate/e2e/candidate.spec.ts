import { expect, test } from "@playwright/test";

const api =
  process.env.VITE_API_BASE_URL ??
  (process.env.PIVOT_BROWSER_BASE_URL
    ? `${process.env.PIVOT_BROWSER_BASE_URL}/api`
    : "http://127.0.0.1:18019");
const password = "Demo-only-123!";

async function login(page: import("@playwright/test").Page, email: string) {
  await page.goto("/login");
  await page.getByLabel("邮箱", { exact: true }).fill(email);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: `欢迎，${email}！` }),
  ).toBeVisible();
}

test("资料编辑、实时匹配、申请、真实预约冲突恢复和换账户隔离", async ({
  page,
  request,
}) => {
  await login(page, "alice@example.com");
  await page.getByRole("link", { name: "我的资料", exact: true }).click();
  await page.getByLabel("显示名称（必填）").fill(" Alice updated ");
  await page.getByLabel("技能 1", { exact: true }).fill(" PYTHON ");
  await page.getByLabel("技能 2", { exact: true }).fill("python");
  await page.getByRole("button", { name: "添加技能", exact: true }).click();
  const resume = "<script>alert(1)</script>\nPrivate candidate text";
  let dialogs = 0;
  page.on("dialog", async (dialog) => {
    dialogs++;
    await dialog.dismiss();
  });
  await page.getByLabel("简历（选填）").fill(resume);
  await page.getByRole("button", { name: "保存资料", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "资料已保存" }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("显示名称（必填）")).toHaveValue(
    "Alice updated",
  );
  await expect(page.getByLabel("技能 1", { exact: true })).toHaveValue(
    "python",
  );
  await expect(page.getByLabel("技能 2", { exact: true })).toHaveCount(0);
  await expect(page.getByLabel("简历（选填）")).toHaveValue(resume);
  await expect(page.locator(".plain-text")).toContainText(
    "<script>alert(1)</script>",
  );
  expect(await page.locator(".plain-text script").count()).toBe(0);
  expect(dialogs).toBe(0);

  await page.getByRole("link", { name: "职位推荐", exact: true }).click();
  await expect(page.locator("article")).toHaveCount(5);
  await expect(page.locator("article").first().getByRole("heading")).toHaveText(
    "Open Role",
  );
  await expect(
    page.locator("article", { hasText: "Backend Engineer" }),
  ).toContainText("50%");
  await page
    .getByRole("link", { name: "Platform Engineer", exact: true })
    .click();
  await expect(page.getByRole("heading", { name: "职位描述" })).toBeVisible();
  await page.getByRole("button", { name: "申请职位", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "已申请", exact: true }),
  ).toBeDisabled();
  await page.getByRole("link", { name: "我的申请", exact: true }).click();
  await expect(
    page.locator("article", { hasText: "Platform Engineer" }),
  ).toContainText("待处理");
  const interview = page.locator("article", { hasText: "Backend Engineer" });
  await interview
    .getByRole("button", { name: "选择面试时段", exact: true })
    .click();
  await expect(
    interview.getByRole("button", { name: "预约", exact: true }),
  ).toHaveCount(2);

  // 另一个真实客户端抢先预约，当前页保存着旧时段列表，接着验证实际 409 的恢复。
  const bobLogin = await request.post(`${api}/users/login`, {
    data: { email: "bob@example.com", password },
  });
  expect(bobLogin.ok()).toBeTruthy();
  const bob = await bobLogin.json();
  const competing = await request.post(
    `${api}/candidate/applications/00000000-0000-0000-0000-0000000000c9/booking`,
    {
      headers: { Authorization: `Bearer ${bob.access_token}` },
      data: { slot_id: "00000000-0000-0000-0000-00000000012c" },
    },
  );
  expect(competing.status()).toBe(201);
  await interview
    .getByRole("button", { name: "预约", exact: true })
    .first()
    .click();
  await expect(interview.getByRole("alert")).toContainText(
    "Slot already booked",
  );
  await expect(
    interview.getByRole("button", { name: "预约", exact: true }),
  ).toHaveCount(1);
  await interview.getByRole("button", { name: "预约", exact: true }).click();
  await expect(interview.getByRole("status")).toContainText("已预约");
  await page.reload();
  await expect(
    page
      .locator("article", { hasText: "Backend Engineer" })
      .getByRole("status"),
  ).toContainText("Asia/Shanghai");
  await page.getByRole("button", { name: "注销", exact: true }).click();
  await login(page, "bob@example.com");
  await page.getByRole("link", { name: "我的资料", exact: true }).click();
  await expect(page.getByLabel("显示名称（必填）")).toHaveValue("Bob");
  await expect(page.getByLabel("简历（选填）")).not.toHaveValue(resume);
  await page.screenshot({
    path: "test-results/candidate-profile.png",
    fullPage: true,
  });
});

test("新版注册补填、动态技能和保存失败保留输入，然后恢复保存", async ({
  page,
}) => {
  await page.goto("/register");
  const email = `candidate-${Date.now()}@example.com`;
  await page.getByLabel("邮箱", { exact: true }).fill(email);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByLabel("确认密码").fill(password);
  await page.getByRole("button", { name: "注册", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "填写候选人资料" }),
  ).toBeVisible();
  await page.goto("/navpage");
  await expect(
    page.getByRole("heading", { name: "填写候选人资料" }),
  ).toBeVisible();
  await page.goto("/employer/details");
  await expect(
    page.getByRole("heading", { name: "填写候选人资料" }),
  ).toBeVisible();
  await page.getByLabel("显示名称（必填）").fill("New Candidate");
  await page.getByRole("button", { name: "保存并继续", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: `欢迎，${email}！` }),
  ).toBeVisible();
  await page.getByRole("link", { name: "我的资料", exact: true }).click();
  await page.getByLabel("显示名称（必填）").fill("Revised Candidate");
  await page.route("**/users/candidates/*/profile", async (route) => {
    if (route.request().method() === "PATCH")
      await route.fulfill({
        status: 500,
        json: { detail: "Temporary save failure" },
      });
    else await route.continue();
  });
  await page.getByRole("button", { name: "保存资料", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Temporary save failure");
  await expect(page.getByLabel("显示名称（必填）")).toHaveValue(
    "Revised Candidate",
  );
  await page.unroute("**/users/candidates/*/profile");
  await page.getByRole("button", { name: "保存资料", exact: true }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "资料已保存" }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("显示名称（必填）")).toHaveValue(
    "Revised Candidate",
  );
  // 令牌失效后请求层清除旧会话，私有页面必须退出，不能只在页面内显示错误。
  await page.evaluate(() => localStorage.setItem("token", "invalid-token"));
  await page.getByRole("link", { name: "职位推荐", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "登录 SkillMatch 职聘匹配平台" }),
  ).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("token"))).toBeNull();
});

test("保留雇主注册补填流程，并禁止雇主进入候选人工作区", async ({ page }) => {
  await page.goto("/register");
  const email = `employer-${Date.now()}@example.com`;
  await page.getByLabel("邮箱", { exact: true }).fill(email);
  await page.getByLabel("密码", { exact: true }).fill(password);
  await page.getByLabel("确认密码").fill(password);
  await page.getByLabel("角色").selectOption("employer");
  await page.getByRole("button", { name: "注册", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "填写公司资料" }),
  ).toBeVisible();
  await page.getByLabel("公司名称（必填）").fill("Local Demo Company");
  await page.getByRole("button", { name: "保存并继续", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: `欢迎，${email}！` }),
  ).toBeVisible();
  await page.goto("/candidate/jobs");
  await expect(page.getByRole("heading", { name: "禁止访问" })).toBeVisible();
});

test("注销之后迟到的 /me 结果不能恢复旧账户", async ({ page, request }) => {
  const response = await request.post(`${api}/users/login`, {
    data: { email: "bob@example.com", password },
  });
  const auth = await response.json();
  await page.addInitScript(
    (token) => localStorage.setItem("token", token),
    auth.access_token,
  );
  let release!: () => void;
  const gate = new Promise<void>((resolve) => {
    release = resolve;
  });
  let captured!: () => void;
  const started = new Promise<void>((resolve) => {
    captured = resolve;
  });
  await page.route("**/users/me", async (route) => {
    captured();
    await gate;
    await route.fulfill({ status: 200, json: auth.user });
  });
  await page.goto("/candidate/jobs", { waitUntil: "domcontentloaded" });
  await started;
  await page.evaluate(() => window.dispatchEvent(new Event("auth-expired")));
  await expect(
    page.getByRole("heading", { name: "登录 SkillMatch 职聘匹配平台" }),
  ).toBeVisible();
  const delivered = page.waitForResponse("**/users/me");
  release();
  await delivered;
  await expect(
    page.getByRole("heading", { name: "登录 SkillMatch 职聘匹配平台" }),
  ).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("token"))).toBeNull();
});

for (const role of ["candidate", "employer"] as const) {
  test(`${role} 未完成资料时可退出登录`, async ({ page }) => {
    await page.goto("/register");
    await page.getByLabel("邮箱", { exact: true }).fill(`logout-${role}-${Date.now()}@example.com`);
    await page.getByLabel("密码", { exact: true }).fill(password);
    await page.getByLabel("确认密码").fill(password);
    await page.getByLabel("角色").selectOption(role);
    await page.getByRole("button", { name: "注册", exact: true }).click();
    await expect(page.getByRole("heading", {
      name: role === "candidate" ? "填写候选人资料" : "填写公司资料",
    })).toBeVisible();
    await page.getByRole("button", { name: "退出登录", exact: true }).click();
    await expect(page.getByRole("heading", { name: "登录 SkillMatch 职聘匹配平台" })).toBeVisible();
    expect(await page.evaluate(() => localStorage.getItem("token"))).toBeNull();
    await page.goto(role === "candidate" ? "/candidate/details" : "/employer/details");
    await expect(page.getByRole("heading", { name: "登录 SkillMatch 职聘匹配平台" })).toBeVisible();
  });
}
