import assert from 'node:assert/strict';
import path from 'node:path';
import { chromium, firefox, webkit } from 'playwright';
import { api, base, out, save, server } from './browser_support.mjs';

const records = [], versions = [];
let serial = 0;
const values = [
  ['ordinary', 'A company building useful software.'],
  ['empty', ''],
  ['whitespace', ' \t\n'],
  ['unicode-space', '\u2003\u00a0'],
  ['multiline', '示例公司介绍 Résumé 🙂\nSecond line of the introduction.'],
  ['markup-literal', '<b>Company & literal</b>'],
  ['long-token', 'LongCompanyIntroduction'.repeat(60)],
];

async function actor(browser, locale, role, name) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 1000 } });
  await context.addInitScript(value => localStorage.setItem('skillmatch.language', value), locale);
  const v = { context };
  await api(v, 'POST', '/users/register', { role, email: `description-${Date.now()}-${++serial}@example.com`, password: 'local-browser-only' });
  await api(v, 'POST', `/users/${role}/profile`, role === 'candidate'
    ? { display_name: 'Example Candidate', skills: ['python'] }
    : { company_name: name, company_description: '' });
  return v;
}

try {
  for (const [engine, type] of Object.entries({ chromium, firefox, webkit })) {
    const browser = await type.launch({ headless: true, ...(engine === 'chromium' && process.env.CHROME_EXECUTABLE_PATH ? { executablePath: process.env.CHROME_EXECUTABLE_PATH } : {}) });
    versions.push({ engine, version: browser.version() });
    try {
      for (const locale of ['zh-CN', 'en-US']) {
        const contexts = [];
        try {
          const owner = await actor(browser, locale, 'employer', 'Example Company A'); contexts.push(owner.context);
          const other = await actor(browser, locale, 'employer', 'Example Company B'); contexts.push(other.context);
          const candidate = await actor(browser, locale, 'candidate'); contexts.push(candidate.context);
          const title = `Company introduction ${engine} ${locale}`;
          const job = await api(owner, 'POST', '/employer/jobs', { title, description: 'Job responsibilities', required_skills: ['python', 'sql'] });
          const otherJob = await api(other, 'POST', '/employer/jobs', { title: 'Other company job', description: 'Other job responsibilities' });
          await api(other, 'PATCH', '/employer/company', { version: 1, company_description: 'Other company introduction' });
          let companyVersion = 1;
          const page = await candidate.context.newPage(); page.setDefaultTimeout(10000);
          const errors = []; page.on('pageerror', error => errors.push(error.message));
          for (const [kind, introduction] of values) {
            const saved = await api(owner, 'PATCH', '/employer/company', { version: companyVersion, company_description: introduction });
            companyVersion = saved.version;
            const detail = await api(candidate, 'GET', `/candidate/jobs/${job.id}`);
            assert.equal(detail.company_description, introduction);
            assert.equal(detail.employer_id, job.employer_id);
            assert.equal(detail.match_score, 50);
            assert.equal(detail.version, 1);
            assert.equal(detail.description, 'Job responsibilities');
            assert.equal((await api(candidate, 'GET', `/candidate/jobs/${otherJob.id}`)).company_description, 'Other company introduction');
            for (const width of [1280, 390]) {
              const id = `${engine}-${locale}-${kind}-${width}`;
              try {
                await page.setViewportSize({ width, height: 1000 });
                await page.goto(base + '/candidate/jobs');
                const titleLink = page.locator(`a.record-title[href="/candidate/jobs/${job.id}"]`);
                await titleLink.waitFor();
                const row = page.locator('li.recommended-job').filter({ has: titleLink });
                assert((await row.innerText()).includes('Example Company A'));
                if (introduction.trim()) assert(!(await row.innerText()).includes(introduction), 'List preview must not show the introduction');
                await titleLink.click();
                await page.waitForURL(`**/candidate/jobs/${job.id}`);
                await page.getByRole('heading', { level: 1, name: title, exact: true }).waitFor();
                const heading = page.locator('.candidate-heading');
                assert((await heading.innerText()).includes('Example Company A'));
                const bio = heading.locator('.company-introduction');
                if (introduction.trim()) {
                  await bio.waitFor();
                  assert.equal(await bio.textContent(), introduction);
                  const style = await bio.evaluate(node => ({ whiteSpace: getComputedStyle(node).whiteSpace, overflowWrap: getComputedStyle(node).overflowWrap }));
                  assert.deepEqual(style, { whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' });
                } else assert.equal(await bio.count(), 0, 'Blank introduction must not create an empty paragraph');
                assert.equal(await heading.locator('b').count(), 0, 'Company markup must remain literal text');
                const geometry = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth }));
                assert(geometry.scroll <= geometry.width, JSON.stringify(geometry));
                assert.deepEqual(errors, []);
                if (engine === 'chromium' && locale === 'zh-CN' && kind === 'ordinary') {
                  await page.screenshot({ path: path.join(out, 'screenshots', `company-description-${width}.png`), fullPage: true });
                }
                records.push({ id, outcome: 'passed', geometry, match_score: detail.match_score });
              } catch (error) {
                records.push({ id, outcome: 'failed', error: String(error.stack), url: page.url(), errors: errors.slice() });
                await page.screenshot({ path: path.join(out, 'screenshots', `${id}-failed.png`), fullPage: true }).catch(() => {});
              }
            }
          }
        } finally { for (const context of contexts) await context.close(); }
      }
    } finally { await browser.close(); }
  }
} finally { server.close(); }
await save('company-description-results.json', { versions, records });
console.log(JSON.stringify({ total: records.length, passed: records.filter(r => r.outcome === 'passed').length, failed: records.filter(r => r.outcome === 'failed').length }));
process.exitCode = records.some(r => r.outcome === 'failed') ? 1 : 0;
