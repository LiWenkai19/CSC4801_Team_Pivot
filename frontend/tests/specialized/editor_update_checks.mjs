import assert from 'node:assert/strict';
import path from 'node:path';
import { chromium, firefox, webkit } from 'playwright';
import { base, server, api, save, out } from './browser_support.mjs';

const records = [];
let serial = 0;
const words = {
  'zh-CN': { check: '检查更新', latest: '已加载最新内容。', current: '当前已是最新版本，本页输入已保留。',
    failed: '检查更新失败，本页输入已保留，请重试。', loadFailed: '加载失败，请重试。',
    conflict: '内容已在其他页面更新，本页修改尚未保存。', reload: '重新加载最新内容',
    confirm: '重新加载将丢弃本页尚未保存的修改，是否继续？' },
  'en-US': { check: 'Check for updates', latest: 'Latest content loaded.', current: 'Already up to date. Your input has been kept.',
    failed: 'Could not check for updates. Your input has been kept. Please retry.', loadFailed: 'Could not load. Please try again.',
    conflict: 'This content was updated on another page. Your changes have not been saved.', reload: 'Reload latest content',
    confirm: 'Reloading will discard your unsaved changes on this page. Continue?' },
};
async function sameValue(control, expected) {
  const deadline = Date.now() + 7000;
  while (await control.inputValue() !== expected && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 25));
  assert.equal(await control.inputValue(), expected);
}
async function scenario(browser, engine, locale, target) {
  const contexts = [], observations = [], writes = [], errors = [];
  const w = words[locale];
  async function actor(role) {
    const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
    contexts.push(context);
    await context.addInitScript(value => localStorage.setItem('skillmatch.language', value), locale);
    const v = { context };
    await api(v, 'POST', '/users/register', { role, email: `editor-${Date.now()}-${++serial}@example.com`, password: 'local-browser-only' });
    await api(v, 'POST', `/users/${role}/profile`, role === 'candidate'
      ? { display_name: 'Candidate', resume_text: 'Original', skills: ['python'] }
      : { company_name: 'Company', company_description: 'Original' });
    return v;
  }
  try {
    const owner = await actor(target === 'candidate' ? 'candidate' : 'employer');
    const job = ['job', 'application'].includes(target)
      ? await api(owner, 'POST', '/employer/jobs', { title: 'Original', description: 'Original', required_skills: ['python'] }) : null;
    const applications = [];
    if (target === 'application') {
      for (let i = 0; i < 2; i++) {
        const candidate = await actor('candidate');
        applications.push(await api(candidate, 'POST', `/candidate/jobs/${job.id}/applications`, {}));
      }
    }
    const route = target === 'candidate' ? '/candidate/profile' : target === 'company' ? '/employer/company'
      : target === 'job' ? `/employer/jobs/${job.id}/edit` : `/employer/jobs/${job.id}`;
    const resource = target === 'candidate' ? '/candidate/profile' : target === 'company' ? '/employer/company'
      : target === 'job' ? `/employer/jobs/${job.id}` : `/employer/applications/${applications[0].application_id}/status`;
    const readPath = target === 'application' ? `/employer/jobs/${job.id}/applications` : resource;
    const field = target === 'candidate' ? 'display_name' : target === 'company' ? 'company_name' : target === 'job' ? 'title' : 'status';
    async function read() {
      const response = await api(owner, 'GET', readPath);
      return target === 'application' ? response.find(row => row.application_id === applications[0].application_id) : response;
    }
    async function change(value) {
      const current = await read();
      return api(owner, 'PATCH', resource, { version: current.version, [field]: value });
    }
    const page = await owner.context.newPage();
    page.setDefaultTimeout(10000);
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => { if (request.method() === 'PATCH') writes.push(request.postDataJSON()); });
    await page.goto(base + route);
    let scope = page;
    // Tie the card to its underlying application via stable creation order (both matching scores/names tie on candidate UUID).
    if (target === 'application') {
      const rows = await api(owner, 'GET', readPath);
      scope = page.locator('.employer-applicant-card').nth(rows.findIndex(row => row.application_id === applications[0].application_id));
    }
    const control = scope.locator(target === 'candidate' ? '#display-name' : target === 'company' ? '#company-name' : target === 'job' ? '#job-title' : 'select');
    const submit = scope.locator('button[type="submit"]');
    const check = scope.getByRole('button', { name: w.check, exact: true });
    await check.waitFor();
    await sameValue(control, target === 'application' ? 'Pending' : target === 'company' ? 'Company' : target === 'candidate' ? 'Candidate' : 'Original');
    const fill = value => target === 'application' ? control.selectOption(value) : control.fill(value);
    const currentText = scope.getByText(w.current, { exact: true });
    const latestText = scope.getByText(w.latest, { exact: true });
    const remote1 = target === 'application' ? 'Interviewing' : 'Remote clean';
    await change(remote1);
    let unexpectedDialogs = 0;
    const unexpected = async dialog => { unexpectedDialogs++; await dialog.dismiss(); };
    page.on('dialog', unexpected);
    await check.click();
    await latestText.waitFor();
    await sameValue(control, remote1);
    assert.equal(unexpectedDialogs, 0);
    observations.push('clean updated resource applies without discard prompt');

    const draft = target === 'application' ? 'Accepted' : 'Draft kept';
    await fill(draft);
    let getCount = 0;
    const checkPattern = '**/api' + readPath;
    const delayed = async route => {
      if (route.request().method() === 'GET') {
        getCount++;
        await new Promise(resolve => setTimeout(resolve, 180));
      }
      await route.continue();
    };
    await owner.context.route(checkPattern, delayed);
    await check.evaluate(button => { button.click(); button.click(); });
    await currentText.waitFor();
    await owner.context.unroute(checkPattern, delayed);
    assert.equal(getCount, 1);
    assert.equal(writes.length, 0);
    await sameValue(control, draft);
    assert.equal(await submit.isDisabled(), false);
    assert.equal(unexpectedDialogs, 0);
    observations.push('same-version check and repeated click preserve draft without writing');

    const failGet = async route => route.request().method() === 'GET'
      ? route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Injected local read failure' }) })
      : route.continue();
    await owner.context.route(checkPattern, failGet);
    await check.click();
    await scope.getByRole('alert').filter({ hasText: w.failed }).waitFor();
    await sameValue(control, draft);
    assert.equal(await submit.isDisabled(), false);
    await owner.context.unroute(checkPattern, failGet);
    observations.push('failed check retains complete editable draft');

    page.off('dialog', unexpected);
    let confirmations = 0;
    async function dialogClick(button, accept) {
      const handled = new Promise(resolve => page.once('dialog', async dialog => {
        assert.equal(dialog.message(), w.confirm); confirmations++;
        if (accept) await dialog.accept(); else await dialog.dismiss();
        resolve();
      }));
      await button.click(); await handled;
    }
    const remote2 = target === 'application' ? 'Rejected' : 'Remote changed';
    await change(remote2);
    await dialogClick(check, false);
    await scope.getByText(w.conflict, { exact: true }).waitFor();
    await sameValue(control, draft);
    assert.equal(await submit.isDisabled(), true);
    assert.equal(writes.length, 0);
    await dialogClick(check, true);
    await latestText.waitFor();
    await sameValue(control, remote2);
    assert.equal(await submit.isDisabled(), false);
    observations.push('changed-version cancel keeps old draft; explicit acceptance replaces it');

    if (target === 'candidate' || target === 'job') {
      const search = scope.locator('.skill-input input');
      await search.fill('unsaved query');
      await change('Remote query check');
      await dialogClick(check, false);
      assert.equal(await search.inputValue(), 'unsaved query');
      assert.equal(await submit.isDisabled(), true);
      await dialogClick(check, true);
      await sameValue(search, '');
      await sameValue(control, 'Remote query check');
      observations.push('uncommitted skill query participates in discard confirmation');
    }

    // A real stale save uses the version previously loaded by the form, never an API helper refreshed version.
    const old = await read();
    await fill(draft);
    const remote3 = target === 'application' ? 'Interviewing' : 'Remote before rejected save';
    const newer = await change(remote3);
    const refused = page.waitForResponse(response => response.request().method() === 'PATCH' && response.url().endsWith(resource));
    await submit.click();
    assert.equal((await refused).status(), 409);
    await scope.getByText(w.conflict, { exact: true }).waitFor();
    await sameValue(control, draft);
    assert.equal(writes.at(-1).version, old.version);
    assert.equal(await submit.isDisabled(), true);
    const reload = scope.getByRole('button', { name: w.reload, exact: true });
    await dialogClick(reload, false);
    await sameValue(control, draft);
    await owner.context.route(checkPattern, failGet);
    await dialogClick(reload, true);
    await scope.getByRole('alert').filter({ hasText: w.loadFailed }).waitFor();
    await sameValue(control, draft);
    assert.equal(await submit.isDisabled(), true);
    await owner.context.unroute(checkPattern, failGet);
    if (engine === 'chromium' && locale === 'zh-CN') await page.screenshot({ path: path.join(out, 'screenshots', `editor-${target}-conflict.png`), fullPage: true });
    await dialogClick(reload, true);
    await sameValue(control, remote3);
    assert.equal(await submit.isDisabled(), false);
    await fill(target === 'application' ? 'Accepted' : 'Final saved');
    const success = page.waitForResponse(response => response.request().method() === 'PATCH' && response.url().endsWith(resource));
    await submit.click();
    assert.equal((await success).status(), 200);
    assert.equal(writes.at(-1).version, newer.version);
    assert.equal((await read()).version, newer.version + 1);
    observations.push('409, cancel, failed reload and successful reload preserve correct draft/version lifecycle');

    if (target === 'application') {
      const rows = await api(owner, 'GET', readPath);
      const other = page.locator('.employer-applicant-card').nth(rows.findIndex(row => row.application_id === applications[1].application_id));
      await other.locator('select').selectOption('Accepted');
      await api(owner, 'PATCH', `/employer/applications/${applications[1].application_id}/status`, { version: 1, status: 'Rejected' });
      await check.click();
      await currentText.waitFor();
      assert.equal(await other.locator('select').inputValue(), 'Accepted');
      const rejected = page.waitForResponse(response => response.request().method() === 'PATCH' && response.url().includes(applications[1].application_id));
      await other.locator('button[type="submit"]').click();
      assert.equal((await rejected).status(), 409);
      assert.equal(writes.at(-1).version, 1);
      observations.push('checking one applicant cannot advance another card draft version');
    }
    assert.deepEqual(errors, []);
    records.push({ id: `${engine}-${locale}-${target}`, outcome: 'passed', observations, confirmations, writes });
  } catch (error) {
    records.push({ id: `${engine}-${locale}-${target}`, outcome: 'failed', observations, error: String(error.stack), writes, errors });
  } finally {
    console.log(JSON.stringify({ id: records.at(-1)?.id, outcome: records.at(-1)?.outcome }));
    for (const context of contexts) await context.close();
  }
}
async function doubleTab(browser, engine, locale, target) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
  const w = words[locale], writes = [], errors = [];
  let candidateContext;
  let tabs = [];
  try {
    await context.addInitScript(value => localStorage.setItem('skillmatch.language', value), locale);
    const v = { context };
    await api(v, 'POST', '/users/register', { role: 'employer', email: `tabs-${Date.now()}-${++serial}@example.com`, password: 'local-browser-only' });
    await api(v, 'POST', '/users/employer/profile', { company_name: 'Original company' });
    let job, application;
    if (target === 'application') {
      job = await api(v, 'POST', '/employer/jobs', { title: 'Tabs job', description: 'Details' });
      candidateContext = await browser.newContext();
      const c = { context: candidateContext };
      await api(c, 'POST', '/users/register', { role: 'candidate', email: `tab-candidate-${Date.now()}-${++serial}@example.com`, password: 'local-browser-only' });
      await api(c, 'POST', '/users/candidate/profile', { display_name: 'Tabs Candidate' });
      application = await api(c, 'POST', `/candidate/jobs/${job.id}/applications`, {});
    }
    const route = target === 'company' ? '/employer/company' : `/employer/jobs/${job.id}`;
    const resource = target === 'company' ? route : `/employer/applications/${application.application_id}/status`;
    const a = await context.newPage(), b = await context.newPage();
    tabs = [a, b];
    for (const [tab, page] of [['a', a], ['b', b]]) {
      page.setDefaultTimeout(10000);
      page.on('pageerror', error => errors.push(error.message));
      page.on('request', request => { if (request.method() === 'PATCH') writes.push({ tab, body: request.postDataJSON() }); });
      await page.goto(base + route);
      await page.getByRole('button', { name: w.check, exact: true }).waitFor();
    }
    const control = page => page.locator(target === 'company' ? '#company-name' : '.employer-applicant-card select');
    const submit = page => page.locator(target === 'company' ? 'form button[type="submit"]' : '.employer-applicant-card button[type="submit"]');
    const fill = (page, value) => target === 'company' ? control(page).fill(value) : control(page).selectOption(value);
    const first = target === 'company' ? 'Page A company' : 'Interviewing';
    const draft = target === 'company' ? 'Page B draft' : 'Rejected';
    await fill(b, draft);
    await fill(a, first);
    let response = a.waitForResponse(r => r.request().method() === 'PATCH' && r.url().endsWith(resource));
    await submit(a).click();
    assert.equal((await response).status(), 200);
    assert.equal(writes.at(-1).body.version, 1);
    response = b.waitForResponse(r => r.request().method() === 'PATCH' && r.url().endsWith(resource));
    await submit(b).click();
    assert.equal((await response).status(), 409);
    assert.equal(writes.at(-1).body.version, 1);
    await b.getByText(w.conflict, { exact: true }).waitFor();
    await sameValue(control(b), draft);
    assert.equal(await submit(b).isDisabled(), true);
    const handled = new Promise(resolve => b.once('dialog', async dialog => { assert.equal(dialog.message(), w.confirm); await dialog.accept(); resolve(); }));
    await b.getByRole('button', { name: w.check, exact: true }).click();
    await handled;
    await sameValue(control(b), first);
    assert.equal(await submit(b).isDisabled(), false);
    await fill(b, draft);
    response = b.waitForResponse(r => r.request().method() === 'PATCH' && r.url().endsWith(resource));
    await submit(b).click();
    assert.equal((await response).status(), 200);
    assert.equal(writes.at(-1).body.version, 2);
    const final = target === 'company' ? await api(v, 'GET', resource) : (await api(v, 'GET', `/employer/jobs/${job.id}/applications`))[0];
    assert.equal(final.version, 3);
    assert.equal(final[target === 'company' ? 'company_name' : 'status'], draft);
    assert.deepEqual(errors, []);
    records.push({ id: `${engine}-${locale}-${target}-real-double-tab`, outcome: 'passed', writes });
  } catch (error) {
    const pages = [];
    for (const [index, tab] of tabs.entries()) {
      pages.push({ url: tab.url(), text: await tab.locator('body').innerText().catch(() => 'unavailable') });
      await tab.screenshot({ path: path.join(out, 'screenshots', `${engine}-${locale}-${target}-failed-tab-${index}.png`), fullPage: true }).catch(() => {});
    }
    records.push({ id: `${engine}-${locale}-${target}-real-double-tab`, outcome: 'failed', error: String(error.stack), writes, errors, pages });
  } finally {
    console.log(JSON.stringify({ id: records.at(-1)?.id, outcome: records.at(-1)?.outcome }));
    await context.close(); if (candidateContext) await candidateContext.close();
  }
}

try {
  for (const [engine, type] of Object.entries({ chromium, firefox, webkit })) {
    const browser = await type.launch({ headless: true, ...(engine === 'chromium' && process.env.CHROME_EXECUTABLE_PATH ? { executablePath: process.env.CHROME_EXECUTABLE_PATH } : {}) });
    try {
      for (const locale of ['zh-CN', 'en-US']) {
        for (const target of ['candidate', 'job', 'company', 'application']) await scenario(browser, engine, locale, target);
        for (const target of ['company', 'application']) await doubleTab(browser, engine, locale, target);
      }
    }
    finally { await browser.close(); }
  }
} finally { server.close(); }
await save('editor-update-results.json', { records });
console.log(JSON.stringify(records.map(({ id, outcome, error }) => ({ id, outcome, error }))));
process.exitCode = records.some(record => record.outcome === 'failed') ? 1 : 0;
