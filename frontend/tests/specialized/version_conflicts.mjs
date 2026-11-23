import assert from 'node:assert/strict';
import path from 'node:path';
import { chromium, firefox, webkit } from 'playwright';
import { base, server, api, save, out } from './browser_support.mjs';

const results = [];
const words = {
  'zh-CN': {
    candidate: ['显示名称（必填）', '简历（选填）', '搜索并添加技能', '已选技能', '保存资料'],
    job: ['标题（必填）', '描述（必填）', '搜索所需技能', '已选技能要求', '保存职位'],
    conflict: '内容已在其他页面更新，本页修改尚未保存。',
    reload: '重新加载最新内容', failed: '加载失败，请重试。',
    confirm: '重新加载将丢弃本页尚未保存的修改，是否继续？',
  },
  'en-US': {
    candidate: ['Display Name (required)', 'Résumé (optional)', 'Search and add a skill', 'Selected Skills', 'Save Profile'],
    job: ['Title (required)', 'Description (required)', 'Search required skills', 'Selected Required Skills', 'Save Job'],
    conflict: 'This content was updated on another page. Your changes have not been saved.',
    reload: 'Reload latest content', failed: 'Could not load. Please try again.',
    confirm: 'Reloading will discard your unsaved changes on this page. Continue?',
  },
};
let serial = 0;

async function scenario(browser, engine, locale, target) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  await context.addInitScript(value => localStorage.setItem('skillmatch.language', value), locale);
  const errors = [], writes = [], reads = [], observations = [];
  const a = await context.newPage(), b = await context.newPage();
  for (const [tab, page] of [['a', a], ['b', b]]) {
    page.setDefaultTimeout(10000);
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (request.method() === 'PATCH') writes.push({ tab, url: request.url(), body: request.postDataJSON() });
      if (tab === 'b' && request.method() === 'GET') reads.push(request.url());
    });
  }
  try {
    const v = { context }, role = target === 'candidate' ? 'candidate' : 'employer';
    await api(v, 'POST', '/users/register', { email: `versions-${Date.now()}-${++serial}@example.com`, password: 'local-browser-only', role });
    await api(v, 'POST', `/users/${role}/profile`, role === 'candidate'
      ? { display_name: 'Original', resume_text: 'Original text', skills: ['python'] }
      : { company_name: 'Version Company' });
    const job = target === 'job' ? await api(v, 'POST', '/employer/jobs', { title: 'Original', description: 'Original text', required_skills: ['python'] }) : null;
    const resource = target === 'candidate' ? '/candidate/profile' : `/employer/jobs/${job.id}`;
    const route = target === 'candidate' ? '/candidate/profile' : `/employer/jobs/${job.id}/edit`;
    const field = target === 'candidate' ? 'skills' : 'required_skills';
    const textField = target === 'candidate' ? 'resume_text' : 'description';
    const w = words[locale], [nameLabel, textLabel, skillLabel, selectedLabel, saveLabel] = w[target];
    await Promise.all([a.goto(base + route), b.goto(base + route)]);
    for (const page of [a, b]) await page.getByRole('button', { name: saveLabel, exact: true }).waitFor();
    assert.equal((await api(v, 'GET', resource)).version, 1);
    const addSkill = async (page, value) => {
      await page.getByLabel(skillLabel, { exact: true }).fill(value);
      await page.getByLabel(skillLabel, { exact: true }).press('Enter');
      await page.getByRole('list', { name: selectedLabel, exact: true }).getByRole('button', { name: new RegExp(value, 'i') }).waitFor();
    };
    await a.getByLabel(nameLabel, { exact: true }).fill('Saved A');
    await a.getByLabel(textLabel, { exact: true }).fill('Saved A text\n第二行');
    await addSkill(a, 'SQL');
    await b.getByLabel(nameLabel, { exact: true }).fill('Draft B');
    await b.getByLabel(textLabel, { exact: true }).fill('Draft B text\n未保存');
    await addSkill(b, 'Java');
    const waitWrite = page => page.waitForResponse(response => response.request().method() === 'PATCH' && response.url().endsWith('/api' + resource));
    const firstResponse = waitWrite(a);
    await a.getByRole('button', { name: saveLabel, exact: true }).click();
    const first = await firstResponse;
    assert.equal(first.status(), 200);
    assert.equal((await first.json()).version, 2);
    observations.push('first_save_200_version_2');
    const secondResponse = waitWrite(b);
    await b.getByRole('button', { name: saveLabel, exact: true }).click();
    const second = await secondResponse;
    assert.equal(second.status(), 409);
    assert.deepEqual(await second.json(), { detail: 'Resource version conflict' });
    await b.getByText(w.conflict, { exact: true }).waitFor();
    assert.deepEqual(writes.map(value => value.body.version), [1, 1]);
    assert.deepEqual(writes[1].body[field].sort(), ['java', 'python']);
    const assertDraft = async () => {
      assert.equal(await b.getByLabel(nameLabel, { exact: true }).inputValue(), 'Draft B');
      assert.equal(await b.getByLabel(textLabel, { exact: true }).inputValue(), 'Draft B text\n未保存');
      assert(await b.getByRole('button', { name: saveLabel, exact: true }).isDisabled());
      await b.getByRole('list', { name: selectedLabel, exact: true }).getByRole('button', { name: /Java/i }).waitFor();
    };
    await assertDraft();
    const unchanged = await api(v, 'GET', resource);
    assert.equal(unchanged.version, 2);
    assert.deepEqual(unchanged[field], ['python', 'sql']);
    assert.equal(unchanged[textField], 'Saved A text\n第二行');
    await b.locator('form').evaluate(form => form.requestSubmit());
    assert.equal(writes.length, 2, 'Conflict guard also prevents programmatic resubmission');
    observations.push('stale_save_409_preserves_draft_and_server');
    await b.screenshot({ path: path.join(out, 'screenshots', `${engine}-${locale}-${target}-conflict.png`), fullPage: true });

    async function reload(accept) {
      const handled = new Promise((resolve, reject) => b.once('dialog', async dialog => {
        try {
          assert.equal(dialog.type(), 'confirm');
          assert.equal(dialog.message(), w.confirm);
          if (accept) await dialog.accept(); else await dialog.dismiss();
          resolve();
        } catch (error) { reject(error); }
      }));
      await b.getByRole('button', { name: w.reload, exact: true }).click();
      await handled;
    }
    const readCount = reads.length;
    await reload(false);
    await assertDraft();
    assert.equal(reads.length, readCount);
    observations.push('cancel_reload_keeps_draft_without_fetch');

    let failReload = true;
    await b.route('**/api' + resource, async route => {
      if (route.request().method() === 'GET' && failReload) {
        failReload = false;
        return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Temporary reload failure' }) });
      }
      return route.continue();
    });
    await reload(true);
    await b.getByText(w.failed, { exact: true }).waitFor();
    assert.equal(failReload, false);
    await assertDraft();
    observations.push('failed_reload_preserves_draft_and_conflict');
    await reload(true);
    await b.getByRole('button', { name: saveLabel, exact: true }).waitFor({ state: 'visible' });
    await b.waitForFunction(({ label }) => [...document.querySelectorAll('button')].some(button => button.textContent === label && !button.disabled), { label: saveLabel });
    assert.equal(await b.getByLabel(nameLabel, { exact: true }).inputValue(), 'Saved A');
    assert.equal(await b.getByLabel(textLabel, { exact: true }).inputValue(), 'Saved A text\n第二行');
    await addSkill(b, 'Java');
    const finalResponse = waitWrite(b);
    await b.getByRole('button', { name: saveLabel, exact: true }).click();
    const final = await finalResponse;
    assert.equal(final.status(), 200);
    const actual = await final.json();
    assert.equal(actual.version, 3);
    assert.deepEqual(actual[field], ['java', 'python', 'sql']);
    assert.deepEqual(writes.map(value => value.body.version), [1, 1, 2]);
    observations.push('confirmed_reload_uses_latest_version_then_save_200_version_3');
    assert.deepEqual(errors, []);
    return { observations, submitted_versions: writes.map(value => value.body.version), final_version: 3 };
  } finally { await context.close(); }
}

try {
  for (const [engine, type, options] of [
    ['chromium', chromium, process.env.CHROME_EXECUTABLE_PATH ? { executablePath: process.env.CHROME_EXECUTABLE_PATH } : {}],
    ['firefox', firefox, {}], ['webkit', webkit, {}],
  ]) {
    const browser = await type.launch({ headless: true, ...options });
    try {
      for (const locale of ['zh-CN', 'en-US']) for (const target of ['candidate', 'job']) {
        try {
          results.push({ engine, browser_version: browser.version(), locale, target, outcome: 'passed', detail: await scenario(browser, engine, locale, target) });
        } catch (error) {
          results.push({ engine, browser_version: browser.version(), locale, target, outcome: 'failed', error: String(error.stack) });
        }
        await save('version-conflicts.json', { results });
      }
    } finally { await browser.close(); }
  }
} finally { await new Promise(resolve => server.close(resolve)); }
console.log(JSON.stringify({ scenarios: results.length, passed: results.filter(value => value.outcome === 'passed').length, failed: results.filter(value => value.outcome === 'failed').length }));
if (results.some(value => value.outcome === 'failed')) process.exitCode = 1;
