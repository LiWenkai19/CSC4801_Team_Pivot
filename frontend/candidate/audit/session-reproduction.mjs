// 会话修复回归诊断，不加入正常E2E回归套件。
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { chromium } from '@playwright/test';

const api = 'http://127.0.0.1:19019';
const ui = 'http://127.0.0.1:5173';
const processes = [];
let browser;

async function ensureFree(port) {
  await new Promise((resolve, reject) => {
    const probe = createServer();
    probe.once('error', () => reject(new Error(`Port ${port} is occupied; audit will not reuse it`)));
    probe.listen(port, '127.0.0.1', () => probe.close(resolve));
  });
}

function start(args, env) {
  const child = spawn(args[0], args.slice(1), { windowsHide: true, stdio: 'pipe', env });
  processes.push(child);
  child.stdout.resume();
  child.stderr.resume();
  return child;
}

async function ready(url, child) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (child.exitCode !== null) throw new Error(`Audit service stopped: ${child.exitCode}`);
    try { if ((await fetch(url)).ok) return; } catch { /* 启动期间继续等待。 */ }
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  throw new Error('Audit service did not become ready');
}

try {
  await ensureFree(19019);
  await ensureFree(5173);
  const backend = start(['../../.venv/Scripts/python.exe', '../../backend/candidate_tests/browser_server.py', '--port', '19019'], process.env);
  await ready(`${api}/openapi.json`, backend);
  const frontend = start([process.execPath, 'node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5173', '--strictPort'],
    { ...process.env, VITE_API_BASE_URL: api });
  await ready(ui, frontend);
  browser = await chromium.launch({ channel: 'msedge', headless: true });
  const context = await browser.newContext();
  const first = await context.newPage();
  const second = await context.newPage();
  await Promise.all([first.goto(`${ui}/login`), second.goto(`${ui}/login`)]);
  for (const page of [first, second]) {
    await page.getByRole('heading', { name: '登录 SkillMatch 职聘匹配平台' }).waitFor();
    await page.evaluate(() => {
      window.auditStorageEvents = [];
      window.addEventListener('storage', event => {
        if (event.key === 'token') window.auditStorageEvents.push({ hasNewValue: event.newValue !== null });
      });
    });
  }
  await first.getByLabel('邮箱', { exact: true }).fill('alice@example.com');
  await first.getByLabel('密码', { exact: true }).fill('Demo-only-123!');
  const authenticated = first.waitForResponse(response => response.url() === `${api}/users/login`);
  await first.getByRole('button', { name: '登录', exact: true }).click();
  const response = await authenticated;
  assert.equal(response.status(), 200);
  const auth = await response.json();
  await first.getByRole('heading', { name: '欢迎，alice@example.com！' }).waitFor();
  assert.equal(await first.evaluate(() => localStorage.getItem('token') !== null), true);
  await second.waitForFunction(() => window.auditStorageEvents.some(event => event.hasNewValue));
  assert.equal(await second.evaluate(() => localStorage.getItem('token') !== null), true);
  console.log('REGRESSION MULTI_TAB: second tab preserves shared token; first tab remains signed in');

  await second.close();
  await first.getByRole('button', { name: '注销', exact: true }).click();
  await first.getByRole('heading', { name: '登录 SkillMatch 职聘匹配平台' }).waitFor();
  const reused = await fetch(`${api}/users/me`, { headers: { Authorization: `Bearer ${auth.access_token}` } });
  assert.equal(reused.status, 200);
  console.log('AUDIT LOGOUT_LIMITATION: UI logout clears browser storage; copied token still gets HTTP 200 until expiry');
} finally {
  if (browser) await browser.close();
  for (const child of processes.reverse()) if (child.exitCode === null) child.kill();
}
