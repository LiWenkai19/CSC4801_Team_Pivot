/** 真实 API/PostgreSQL 浏览器回归；随机数据库和临时服务在 finally 中清理。
 * 先 npm run build；设置 CANDIDATE_TEST_DATABASE_URL、PLAYWRIGHT_MODULE（可选）、UI_BROWSER_CHANNEL（可选）。
 * 从仓库根目录执行 node frontend/tests/candidate.browser.mjs。
 */
import assert from 'node:assert/strict'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('../../', import.meta.url))
const python = process.env.UI_PYTHON || path.join(root, '.venv', 'Scripts', 'python.exe')
assert(process.env.CANDIDATE_TEST_DATABASE_URL, 'Set CANDIDATE_TEST_DATABASE_URL to an isolated PostgreSQL instance')
const { chromium } = await (process.env.PLAYWRIGHT_MODULE ? import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href) : import('playwright'))
const output = await mkdtemp(path.join(tmpdir(), 'csc4801-candidate-ui-'))
const manifest = path.join(output, 'manifest.json')
console.log(`Results: ${output}`)

const backendSource = String.raw`import json, os, re, sys, uuid
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
source = make_url(os.environ['CANDIDATE_TEST_DATABASE_URL'])
admin = create_engine(source.set(database='postgres'), isolation_level='AUTOCOMMIT')
manifest = Path(os.environ['UI_MANIFEST'])
if '--cleanup' in sys.argv:
    if manifest.exists():
        name = json.loads(manifest.read_text())['database']
        assert re.fullmatch(r'csc4801_candidate_ui_[0-9a-f]{12}', name)
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()
    raise SystemExit(0)
name = 'csc4801_candidate_ui_' + uuid.uuid4().hex[:12]
with admin.connect() as connection:
    connection.execute(text(f'CREATE DATABASE "{name}"'))
admin.dispose()
manifest.write_text(json.dumps({'database': name}))
os.environ.update(APP_NAME='Candidate browser tests', SECRET_KEY='candidate-ui-test-key-with-at-least-32-characters', ALGORITHM='HS256', ACCESS_TOKEN_EXPIRE_MINUTES='120', DATABASE_URL=source.set(database=name).render_as_string(hide_password=False))
from alembic import command
from alembic.config import Config
command.upgrade(Config('alembic.ini'), 'head')
from app.db.session import engine
engine.echo = False
from sqlmodel import Session
from scripts.seed_demo import build_seed_rows, fixed_id
from app.employer.model import InterviewSlot
from app.users.model import utc_now
from datetime import timedelta
with Session(engine) as session:
    for group in build_seed_rows():
        session.add_all(group)
        session.flush()
    # 不改团队种子：测试自行准备两个未来 30 分钟时段。
    start = utc_now() + timedelta(days=2)
    for index in range(2):
        begins = start + timedelta(hours=index)
        session.add(InterviewSlot(employer_id=fixed_id('employer-1'), starts_at=begins, ends_at=begins + timedelta(minutes=30)))
    session.commit()
from app.main import app
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=[os.environ['UI_ORIGIN']], allow_methods=['*'], allow_headers=['*'])
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=int(os.environ['UI_API_PORT']), log_level='warning')`

async function freePort() {
    const server = createServer().listen(0, '127.0.0.1')
    await once(server, 'listening')
    const port = server.address().port
    await new Promise(resolve => server.close(resolve))
    return port
}
const uiPort = await freePort()
const apiPort = await freePort()
const base = `http://127.0.0.1:${uiPort}`
const apiBase = `http://127.0.0.1:${apiPort}`
const env = { ...process.env, UI_MANIFEST: manifest, UI_ORIGIN: base, UI_API_PORT: String(apiPort) }
function launch(command, args, cwd) {
    const child = spawn(command, args, { cwd, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
    child.log = ''
    child.stdout.on('data', chunk => { child.log += chunk })
    child.stderr.on('data', chunk => { child.log += chunk })
    child.on('error', error => { child.failure = error })
    return child
}
async function ready(url, child) {
    const deadline = Date.now() + 30000
    while (Date.now() < deadline) {
        if (child.failure || child.exitCode !== null) throw new Error(child.failure?.message || child.log)
        try { if ((await fetch(url)).ok) return } catch { /* 启动尚未完成。 */ }
        await new Promise(resolve => setTimeout(resolve, 150))
    }
    throw new Error(`Startup timed out: ${child.log}`)
}
async function stop(child, name) {
    if (!child) return
    if (child.exitCode === null && child.signalCode === null) {
        const exited = once(child, 'exit')
        child.kill()
        await exited
    }
    await writeFile(path.join(output, `${name}.log`), child.log)
}
async function api(method, pathname, token, body) {
    const response = await fetch(`${apiBase}${pathname}`, {
        method, headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body ? { 'Content-Type': 'application/json' } : {}) },
        body: body ? JSON.stringify(body) : undefined,
    })
    assert(response.ok, `${method} ${pathname}: ${response.status}`)
    return response.json()
}
const passed = [], errors = []
let backend, preview, browser
try {
    backend = launch(python, ['-u', '-c', backendSource], path.join(root, 'backend'))
    preview = launch(process.execPath, ['node_modules/vite/bin/vite.js', 'preview', '--host', '127.0.0.1', '--port', String(uiPort), '--strictPort'], path.join(root, 'frontend'))
    await Promise.all([ready(`${apiBase}/openapi.json`, backend), ready(base, preview)])
    browser = await chromium.launch({ headless: true, ...(process.env.UI_BROWSER_CHANNEL ? { channel: process.env.UI_BROWSER_CHANNEL } : {}) })
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: 'light' })
    const page = await context.newPage()
    page.setDefaultTimeout(10000)
    page.on('pageerror', error => errors.push(error.message))
    page.on('dialog', async dialog => { errors.push(`Unexpected dialog: ${dialog.message()}`); await dialog.dismiss() })
    let fault = null
    await context.route('http://127.0.0.1:8000/**', async route => {
        const url = new URL(route.request().url())
        if (fault === url.pathname) {
            fault = null
            return route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Temporarily unavailable' }) })
        }
        const response = await route.fetch({ url: `${apiBase}${url.pathname}${url.search}` })
        await route.fulfill({ response })
    })
    async function check(name, action) { await action(); passed.push(name); console.log(`PASS ${name}`) }
    async function go(route) { await page.goto(`${base}${route}`) }
    async function visible(text) { await page.getByText(text, { exact: true }).first().waitFor() }
    async function login(email) {
        await go('/login')
        await page.locator('input[type=email]').fill(email)
        await page.locator('input[type=password]').fill('demo-local-only')
        await page.getByRole('button', { name: '登录', exact: true }).click()
        await page.waitForURL('**/navpage')
    }
    const payload = '<script>alert(1)</script>'
    let candidateToken, targetJob, applicationId
    await check('注册、技能建议与自定义标签、首次保存返回主页', async () => {
        await go('/register')
        await page.locator('input[type=email]').fill(`candidate-${Date.now()}@example.com`)
        await page.locator('input[type=password]').nth(0).fill('demo-local-only')
        await page.locator('input[type=password]').nth(1).fill('demo-local-only')
        await page.getByRole('button', { name: '注册', exact: true }).click()
        await page.waitForURL('**/candidate/details')
        await page.getByLabel('显示名称（必填）').fill('测试候选人')
        await page.getByLabel('简历（选填）').fill(payload)
        await page.getByLabel('搜索或输入技能').fill('py')
        await page.getByRole('button', { name: 'Python', exact: true }).click()
        await page.getByLabel('搜索或输入技能').fill('自定义技能')
        await page.getByLabel('搜索或输入技能').press('Enter')
        await page.getByRole('button', { name: '保存并继续' }).click()
        await page.waitForURL('**/navpage')
        candidateToken = await page.evaluate(() => localStorage.getItem('token'))
        const profile = await api('GET', '/candidate/profile', candidateToken)
        assert.deepEqual(profile.skills, ['python', '自定义技能'])
        assert.equal(profile.resume_text, payload)
    })
    await check('真实推荐、故障重试与无重复投递', async () => {
        fault = '/candidate/jobs'
        await page.getByRole('button', { name: '候选人工作流', exact: true }).click()
        await visible('Temporarily unavailable')
        await page.getByRole('button', { name: '重新加载' }).click()
        await page.getByRole('heading', { name: 'Backend Engineer', exact: true }).waitFor()
        const jobs = await api('GET', '/candidate/jobs', candidateToken)
        assert.deepEqual(jobs.map(row => row.match_score), [100, 50, 0])
        targetJob = jobs.find(row => row.title === 'Backend Engineer')
        await page.getByRole('link', { name: 'Backend Engineer', exact: true }).click()
        await page.getByRole('button', { name: '申请职位', exact: true }).click()
        await visible('你已申请该职位，请勿重复申请。')
        await page.reload()
        await page.getByRole('button', { name: '已申请', exact: true }).waitFor()
        const applications = await api('GET', '/candidate/applications', candidateToken)
        assert.equal(applications.length, 1)
        assert.equal(applications[0].status, 'Pending')
        applicationId = applications[0].application_id
    })
    await check('编辑资料持久化、待添加技能阻止保存、纯文本 XSS', async () => {
        await page.getByRole('link', { name: '我的资料', exact: true }).click()
        await page.getByLabel('显示名称（必填）').fill('更新后的候选人')
        await page.getByLabel('搜索或输入技能').fill('sql')
        await page.getByRole('button', { name: '保存资料', exact: true }).click()
        assert.equal((await api('GET', '/candidate/profile', candidateToken)).display_name, '测试候选人')
        await page.getByRole('button', { name: 'SQL', exact: true }).click()
        await page.getByRole('button', { name: '保存资料', exact: true }).click()
        await visible('资料已保存，职位推荐会使用最新技能。')
        await page.reload()
        assert.equal(await page.getByLabel('简历（选填）').inputValue(), payload)
        assert.equal(await page.locator('main script').count(), 0)
        assert((await api('GET', '/candidate/profile', candidateToken)).skills.includes('sql'))
        await page.screenshot({ path: path.join(output, 'profile-desktop.png'), fullPage: true })
    })
    await check('职位描述按纯文本渲染，SQL 元字符保持为内容', async () => {
        const employer = await api('POST', '/users/login', null, { email: 'demo-employer1@example.com', password: 'demo-local-only' })
        const title = "Text safety '; DROP TABLE job; --"
        const posting = await api('POST', '/employer/jobs', employer.access_token, { title, description: payload, required_skills: [] })
        await go(`/candidate/jobs/${posting.id}`)
        await page.getByRole('heading', { name: title, exact: true }).waitFor()
        await visible(payload)
        assert.equal(await page.locator('main script').count(), 0)
    })
    await check('申请状态同步、预约冲突恢复、双方可见且状态变化保留预约', async () => {
        const employer = await api('POST', '/users/login', null, { email: 'demo-employer1@example.com', password: 'demo-local-only' })
        await api('PATCH', `/employer/applications/${applicationId}/status`, employer.access_token, { status: 'Interviewing' })
        await page.getByRole('link', { name: '我的申请', exact: true }).click()
        await visible('申请状态：面试中')
        await page.getByRole('button', { name: '加载可预约时段' }).click()
        const slots = await api('GET', `/candidate/applications/${applicationId}/slots`, candidateToken)
        assert(slots.length > 0)
        await page.getByLabel('选择面试时段（上海时间）').selectOption(slots[0].id)
        // Bob 抢先预约，当前页面持有过期选择，必须处理真实 409。
        const bob = await api('POST', '/users/login', null, { email: 'demo-bob@example.com', password: 'demo-local-only' })
        const bobApplications = await api('GET', '/candidate/applications', bob.access_token)
        const bobInterview = bobApplications.find(row => row.status === 'Interviewing')
        await api('POST', `/candidate/applications/${bobInterview.application_id}/booking`, bob.access_token, { slot_id: slots[0].id })
        await page.getByRole('button', { name: '确认预约' }).click()
        await visible('该时段已被预约，请重新加载并选择其他时段。')
        await page.getByRole('button', { name: '加载可预约时段' }).click()
        const remaining = await api('GET', `/candidate/applications/${applicationId}/slots`, candidateToken)
        assert.equal(remaining.length, 1)
        await page.getByLabel('选择面试时段（上海时间）').selectOption(remaining[0].id)
        await page.getByRole('button', { name: '确认预约' }).click()
        await page.getByText('面试已预约：', { exact: false }).waitFor()
        const self = await api('GET', `/candidate/applications/${applicationId}`, candidateToken)
        assert.equal(self.booking.slot_id, remaining[0].id)
        const changed = await api('GET', `/candidate/applications/${bobInterview.application_id}`, bob.access_token)
        const applicants = await api('GET', `/employer/jobs/${targetJob.id}/applications`, employer.access_token)
        assert.equal(applicants.find(row => row.application_id === bobInterview.application_id).booking.booking_id, changed.booking.booking_id)
        // 当前候选人再投递其他职位；已有申请状态仍按服务端返回展示。
        await page.screenshot({ path: path.join(output, 'applications-desktop.png'), fullPage: true })
        await login('demo-bob@example.com')
        await go('/candidate/applications')
        await page.getByText('面试已预约：', { exact: false }).waitFor()
        await api('PATCH', `/employer/applications/${bobInterview.application_id}/status`, employer.access_token, { status: 'Accepted' })
        await page.getByRole('button', { name: '刷新申请', exact: true }).click()
        await visible('申请状态：已录用')
        await page.getByText('面试已预约：', { exact: false }).waitFor()
    })
    await check('桌面与窄屏导航、键盘和布局', async () => {
        for (const width of [1280, 390]) {
            await page.setViewportSize({ width, height: 900 })
            for (const route of ['/candidate/jobs', '/candidate/profile', '/candidate/applications']) {
                await go(route)
                await page.getByRole('heading', { level: 1 }).waitFor()
                await page.getByRole('status').filter({ hasText: /^正在加载/ }).waitFor({ state: 'hidden' })
                assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${route}: overflow at ${width}`)
                await page.screenshot({ path: path.join(output, `${route.split('/').pop()}-${width}.png`), fullPage: true })
            }
        }
        await page.keyboard.press('Tab')
        assert(await page.evaluate(() => document.activeElement !== document.body))
    })
    await check('候选人路由拒绝雇主，既有雇主页面可继续访问', async () => {
        await login('demo-employer1@example.com')
        await go('/candidate/jobs')
        await visible('仅候选人可访问此页面。')
        await go('/employer/jobs')
        await page.getByRole('heading', { name: '我的职位' }).waitFor()
        await page.getByRole('heading', { name: 'Backend Engineer', exact: true }).waitFor()
        await page.screenshot({ path: path.join(output, 'employer-reference.png'), fullPage: true })
    })
    assert.deepEqual(errors, [])
    await writeFile(path.join(output, 'results.json'), JSON.stringify({ passed, errors }, null, 2))
} finally {
    await browser?.close()
    await stop(preview, 'preview')
    await stop(backend, 'backend')
    const cleanup = launch(python, ['-c', backendSource, '--cleanup'], path.join(root, 'backend'))
    const [code] = await once(cleanup, 'exit')
    await stop(cleanup, 'cleanup')
    if (code !== 0) {
        console.error(`Database cleanup failed: ${cleanup.log}`)
        process.exitCode = 1
    }
}
