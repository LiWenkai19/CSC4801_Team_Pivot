import { expect, test } from '@playwright/test'

// Explicit diagnostic: success confirms the defect, not a safe regression expectation.

test('audit: transient me failure erases shared session in both tabs', async ({ context }) => {
  const first = await context.newPage()
  await first.goto('/login')
  await first.getByLabel('邮箱', { exact: true }).fill('alice@example.com')
  await first.getByLabel('密码', { exact: true }).fill('Demo-only-123!')
  await first.getByRole('button', { name: '登录', exact: true }).click()
  await expect(first.getByRole('heading', { name: '欢迎，alice@example.com！' })).toBeVisible()
  const token = await first.evaluate(() => localStorage.getItem('token'))
  expect(token).toBeTruthy()

  const second = await context.newPage()
  await second.route('**/users/me', route => route.fulfill({
    status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Temporary outage' }),
  }))
  await second.goto('/candidate/profile')
  await expect.poll(() => first.evaluate(() => localStorage.getItem('token'))).toBeNull()
  await expect(first.getByRole('heading', { name: '登录 SkillMatch 职聘匹配平台' })).toBeVisible()

  const api = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:18019'
  const stillValid = await context.request.get(`${api}/users/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(stillValid.status()).toBe(200)
  console.log('TRANSIENT_503: both tabs logged out; original token still returns 200')
})
