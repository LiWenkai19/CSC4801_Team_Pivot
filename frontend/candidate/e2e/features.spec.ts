import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

const api = process.env.VITE_API_BASE_URL ?? (process.env.PIVOT_BROWSER_BASE_URL
  ? `${process.env.PIVOT_BROWSER_BASE_URL}/api` : "http://127.0.0.1:18019");

async function candidate(page: Page, request: APIRequestContext) {
  const registered = await request.post(`${api}/users/register`, { data: {
    email: `acceptance-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`,
    password: "Local-test-only-123!", role: "candidate",
  } });
  expect(registered.status()).toBe(200);
  const auth = await registered.json();
  const headers = { Authorization: `Bearer ${auth.access_token}` };
  const profile = await request.post(`${api}/users/candidate/profile`, { headers,
    data: { display_name: "Acceptance Candidate", resume_text: "测试简历", skills: [] },
  });
  expect(profile.status()).toBe(201);
  await page.addInitScript(token => localStorage.setItem("token", token), auth.access_token);
  return { headers, id: auth.user.id };
}

test("标签推荐、键盘选择、区分Java/JavaScript、自定义和刷新持久化", async ({ page, request }) => {
  const auth = await candidate(page, request);
  await page.goto("/candidate/profile");
  const search = page.getByRole("combobox", { name: "技能（选填）" });
  await search.fill("j");
  await expect(page.getByRole("option").filter({ hasText: /^Java添加$/ })).toBeVisible();
  await expect(page.getByRole("option").filter({ hasText: /^JavaScript添加$/ })).toBeVisible();
  await search.press("ArrowDown");
  await search.press("Enter");
  await search.fill("j");
  await page.getByRole("option").filter({ hasText: /^JavaScript添加$/ }).click();
  await search.fill(" JAVA ");
  await search.press("Enter");
  await expect(page.getByLabel("已选技能").getByRole("listitem")).toHaveCount(2);
  await search.fill("  自定义分析  ");
  await page.getByRole("option").filter({ hasText: "自定义：自定义分析" }).click();
  const markup = '<img src=x onerror="window.pwned=1">';
  await search.fill(markup);
  await page.getByRole("option").filter({ hasText: `自定义：${markup}` }).click();
  await search.press("Escape");
  await expect(page.getByLabel("已选技能").locator("img")).toHaveCount(0);
  await page.getByRole("button", { name: "保存资料", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "资料已保存" })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("已选技能").getByRole("listitem")).toHaveCount(4);
  const saved = await request.get(`${api}/users/candidates/${auth.id}/profile`, { headers: auth.headers });
  expect((await saved.json()).skills).toEqual([markup, "java", "javascript", "自定义分析"]);
  expect(await page.evaluate(() => (window as unknown as { pwned?: number }).pwned)).toBeUndefined();
  await page.getByRole("button", { name: "移除技能 Java", exact: true }).click();
  await page.getByRole("button", { name: "保存资料", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "资料已保存" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("button", { name: "移除技能 Java", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "移除技能 JavaScript", exact: true })).toBeVisible();
});

test("未确认的技能输入阻止保存，完成自定义后可保存并清空全部标签", async ({ page, request }) => {
  const auth = await candidate(page, request);
  await page.goto("/candidate/profile");
  const search = page.getByRole("combobox", { name: "技能（选填）" });
  await search.fill("UnconfirmedSkill");
  await search.press("Escape");
  let writes = 0;
  page.on("request", req => { if (req.method() === "PATCH") writes++; });
  await page.getByRole("button", { name: "保存资料", exact: true }).click();
  expect(await search.evaluate((element: HTMLInputElement) => element.validity.customError)).toBe(true);
  expect(writes).toBe(0);
  await search.focus();
  await page.getByRole("option").filter({ hasText: "自定义：UnconfirmedSkill" }).click();
  await search.press("Escape");
  await page.getByRole("button", { name: "保存资料", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "资料已保存" })).toBeVisible();
  await page.getByRole("button", { name: "移除技能 unconfirmedskill", exact: true }).click();
  await page.getByRole("button", { name: "保存资料", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "资料已保存" })).toBeVisible();
  const saved = await request.get(`${api}/users/candidates/${auth.id}/profile`, { headers: auth.headers });
  expect((await saved.json()).skills).toEqual([]);
});

test("另一个客户端已申请时显示中文重复反馈并刷新已申请状态", async ({ page, request }) => {
  const auth = await candidate(page, request);
  const jobs = await request.get(`${api}/candidate/jobs`, { headers: auth.headers });
  const rows = await jobs.json();
  expect(rows.length).toBeGreaterThan(0);
  expect(rows.every((job: { score: number; score_kind: string }) => job.score === 0 && job.score_kind === "placeholder")).toBe(true);
  const job = rows[0];
  await page.goto(`/candidate/jobs/${job.id}`);
  await expect(page.getByRole("button", { name: "申请职位", exact: true })).toBeEnabled();
  const first = await request.post(`${api}/candidate/jobs/${job.id}/applications`, { headers: auth.headers, data: {} });
  expect(first.status()).toBe(201);
  const duplicate = page.waitForResponse(response => response.url().endsWith(`/candidate/jobs/${job.id}/applications`) && response.request().method() === "POST");
  await page.getByRole("button", { name: "申请职位", exact: true }).click();
  expect((await duplicate).status()).toBe(409);
  await expect(page.getByRole("button", { name: "已申请", exact: true })).toBeDisabled();
  await expect(page.getByText("你已申请该职位，请勿重复申请。", { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByText("你已申请该职位，请勿重复申请。", { exact: true })).toBeVisible();
  const applications = await request.get(`${api}/candidate/applications`, { headers: auth.headers });
  expect((await applications.json()).filter((row: { job_id: string }) => row.job_id === job.id)).toHaveLength(1);
});

test("窄屏技能下拉框不横向溢出，输入法确认不误选技能", async ({ page, request }) => {
  await candidate(page, request);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/candidate/profile");
  const search = page.getByRole("combobox", { name: "技能（选填）" });
  await search.fill("j");
  await search.dispatchEvent("keydown", { key: "Enter", code: "Enter", isComposing: true });
  await expect(search).toHaveValue("j");
  await expect(page.getByLabel("已选技能")).toHaveCount(0);
  await search.press("Escape");
  await expect(search).toHaveAttribute("aria-expanded", "false");
  await search.fill("没有预置的长技能名称".repeat(8));
  await page.getByRole("option").filter({ hasText: "自定义：" }).click();
  await search.press("Escape");
  const overflow = await page.locator(".skill-picker").evaluate(element => element.scrollWidth > element.clientWidth);
  expect(overflow).toBe(false);
});
