// 执行原浏览器脚本内的真实辅助函数，验证当前 Cookie/CSRF 合同。
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
const out = process.env.UI_OUT, apiBase = 'http://127.0.0.1:' + process.env.UI_API_PORT;
const source = path.join(process.env.UI_SOURCE, 'tests'), records = [];
for (const kind of ['candidate', 'employer']) {
  const record = { id: 'DEL-LEGACY-' + kind, source: kind + '.browser.mjs' };
  try {
    const code = await fs.readFile(path.join(source, kind + '.browser.mjs'), 'utf8');
    const begin = code.indexOf('async function api(');
    const end = code.indexOf(kind === 'candidate' ? '\nconst passed' : '\n  async function sessionFor', begin);
    assert(begin >= 0 && end > begin, 'Actual API helper must be extractable');
    const helper = new Function('apiBase', 'assert', code.slice(begin, end) + '; return api;')(apiBase, assert);
    const value = result => kind === 'candidate' ? result : result.value;
    const credentials = { email: `helper-${kind}-${Date.now()}@example.com`, password: 'local-browser-only', role: kind };
    const registered = await helper('POST', '/users/register', null, credentials);
    const login = await helper('POST', '/users/login', null, { email: credentials.email, password: credentials.password });
    const session = login.session;
    assert(session?.cookie && session.csrf);
    assert.equal(Object.hasOwn(value(login), 'access_token'), false);
    const me = value(await helper('GET', '/users/me', session));
    assert.equal(me.id, value(registered).user.id);
    const profile = kind === 'candidate' ? { display_name: 'Probe candidate' } : { company_name: 'Probe company' };
    await helper('POST', `/users/${kind}/profile`, session, profile);
    const route = kind === 'candidate' ? '/candidate/profile' : '/employer/company';
    const saved = value(await helper('PATCH', route, session, { version: 1, ...(kind === 'candidate' ? { resume_text: 'Probe résumé' } : { company_description: 'Probe description' }) }));
    assert.equal(saved.version, 2);
    const denied = await fetch(apiBase + route, { method: 'PATCH', headers: { Cookie: session.cookie, 'Content-Type': 'application/json' }, body: JSON.stringify({ version: 2, ...profile }) });
    assert.equal(denied.status, 403);
    assert.deepEqual(value(await helper('GET', route, session)), saved);
    await helper('POST', '/users/logout', session);
    const revoked = await fetch(apiBase + '/users/me', { headers: { Cookie: session.cookie } });
    assert.equal(revoked.status, 401);
    record.outcome = 'passed';
    record.protected_read_status = 200;
    record.csrf_write_version = saved.version;
    record.missing_csrf_status = denied.status;
    record.revoked_session_status = revoked.status;
  } catch (error) {
    record.outcome = 'failed';
    record.error = String(error.stack);
  }
  records.push(record);
}
await fs.writeFile(path.join(out, process.env.UI_STAGE_MODE + '-existing-browser-probes-results.json'), JSON.stringify(records, null, 2));
console.log(JSON.stringify(records));
process.exitCode = records.some(record => record.outcome === 'failed') ? 1 : 0;
