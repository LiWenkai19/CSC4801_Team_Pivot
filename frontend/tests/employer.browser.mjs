/**
 * 雇主前端浏览器回归：创建独立 PostgreSQL 库，执行迁移并灌入测试数据。
 * 自动启动生产预览与真实后端；结束时停止服务、删除测试库，保留结果与截图。
 * 前置：项目 Python 环境及 backend/.env；在 frontend 执行 npm run build。
 * 另需 Playwright 和 Chromium，脚本不会自动修改项目依赖。
 * 用法（仓库根目录）：node frontend/tests/employer.browser.mjs
 * UI_PYTHON 指定项目 Python；PLAYWRIGHT_MODULE 可指定 Playwright 入口绝对路径。
 * 所有演示记录只写入本轮新建的隔离库，不向开发数据库写测试数据。
 */
import assert from 'node:assert/strict'
import { access, mkdtemp, readFile, writeFile } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('../../', import.meta.url))
const frontend = path.join(root, 'frontend')
const python = process.env.UI_PYTHON || 'python'
await access(path.join(frontend, 'dist/index.html')).catch(() => {
  throw new Error('请先在 frontend 执行 npm run build。')
})
const { chromium } = await (process.env.PLAYWRIGHT_MODULE
  ? import(pathToFileURL(path.resolve(process.env.PLAYWRIGHT_MODULE)).href)
  : import('playwright')).catch(() => {
  throw new Error('未找到 Playwright。请安装到独立工具目录，并用 PLAYWRIGHT_MODULE 指定其 index.mjs。')
})
const resultDir = await mkdtemp(path.join(tmpdir(), 'csc4801-employer-ui-'))
const fixturesPath = path.join(resultDir, 'manifest.json')
console.log('浏览器回归结果目录：', resultDir)

// 临时后端通过进程参数运行，无需向后端代码区写入文件。
const backendSource = String.raw`import json, os, re, sys, uuid
from pathlib import Path
from datetime import datetime, timedelta, timezone
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
values = dotenv_values(ROOT / '.env')
manifest_path = Path(os.environ['UI_FIXTURES'])
if '--cleanup' in sys.argv:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    name = manifest['database']
    assert re.fullmatch(r'csc4801_ui_[0-9a-f]{12}', name)
    source = make_url(values['DATABASE_URL'])
    admin = create_engine(source.set(database='postgres'), isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    admin.dispose()
    print('Removed isolated browser-test database: ' + name)
    raise SystemExit(0)
name = 'csc4801_ui_' + uuid.uuid4().hex[:12]
assert re.fullmatch(r'csc4801_ui_[0-9a-f]{12}', name)
source = make_url(values['DATABASE_URL'])
admin = create_engine(source.set(database='postgres'), isolation_level='AUTOCOMMIT')
with admin.connect() as connection:
    connection.execute(text(f'CREATE DATABASE "{name}"'))
admin.dispose()
manifest_path.write_text(json.dumps({'database': name}), encoding='utf-8')
os.environ.update(APP_NAME='Isolated employer frontend verification', SECRET_KEY='isolated-ui-test-key-with-at-least-32-characters', ALGORITHM='HS256', ACCESS_TOKEN_EXPIRE_MINUTES='120', DATABASE_URL=source.set(database=name).render_as_string(hide_password=False))
from alembic import command
from alembic.config import Config
command.upgrade(Config(str(ROOT / 'alembic.ini')), 'head')
from app.db.session import engine
engine.echo = False
from sqlmodel import Session
from scripts.seed_demo import build_seed_rows, fixed_id
from app.employer.model import Application, Booking, InterviewSlot, Job
from app.users.model import CandidateProfile, CandidateSkill, Role, User
from app.users.security import hash_password
with Session(engine) as session:
    for group in build_seed_rows():
        session.add_all(group)
        session.flush()
    # 同分、同名候选人检验稳定 ID 排序；另建已预约时段和仅时段依赖职位。
    twin_ids = [uuid.UUID(int=1), uuid.UUID(int=2)]
    for candidate_id in twin_ids:
        session.add(User(id=candidate_id, email=f'twin{candidate_id.int}@example.com', hashed_password=hash_password('demo-local-only'), role=Role.Candidate))
        session.flush()
        session.add(CandidateProfile(user_id=candidate_id, display_name='alice', resume_text='PRIVATE MUST NOT LEAK'))
        session.flush()
        session.add_all([CandidateSkill(candidate_id=candidate_id, name='python'), CandidateSkill(candidate_id=candidate_id, name='sql')])
        session.add(Application(candidate_id=candidate_id, job_id=fixed_id('job-backend')))
    start = datetime.now(timezone.utc) + timedelta(days=5)
    slot = InterviewSlot(employer_id=fixed_id('employer-1'), job_id=fixed_id('job-backend'), starts_at=start, ends_at=start + timedelta(minutes=30))
    session.add(slot)
    session.flush()
    session.add(Booking(application_id=fixed_id('app-alice-backend'), slot_id=slot.id))
    slot_job = Job(employer_id=fixed_id('employer-1'), title='Slot dependency only', description='Cannot delete a job with slots.')
    session.add(slot_job)
    session.flush()
    session.add(InterviewSlot(employer_id=fixed_id('employer-1'), job_id=slot_job.id, starts_at=start, ends_at=start + timedelta(minutes=30)))
    session.commit()
    manifest = {'database':name, 'backendJob':str(fixed_id('job-backend')), 'otherJob':str(fixed_id('job-data-entry')), 'generalJob':str(fixed_id('job-general')), 'slotJob':str(slot_job.id), 'aliceApplication':str(fixed_id('app-alice-backend'))}
manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
from app.main import app
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=[os.environ['UI_ORIGIN']], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])
import uvicorn
uvicorn.run(app, host='127.0.0.1', port=int(os.environ['UI_BACKEND_PORT']), log_level='warning')`

/** 分配空闲本地端口，避开其他工作区的开发服务。 */
async function freePort() {
  const server = createServer()
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  const port = server.address().port
  await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()))
  return port
}

/** 将启动日志保存在临时目录，便于定位子进程错误。 */
function launch(command, args, cwd, env, name) {
  const child = spawn(command, args, { cwd, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  child.taskLog = ''
  child.taskError = null
  child.on('error', error => { child.taskError = error })
  for (const stream of [child.stdout, child.stderr]) {
    stream.setEncoding('utf8')
    stream.on('data', value => { child.taskLog += value })
  }
  child.taskName = name
  return child
}

async function ready(url, child) {
  const deadline = Date.now() + 30000
  while (Date.now() < deadline) {
    if (child.taskError) throw child.taskError
    if (child.exitCode !== null) throw new Error(`${child.taskName} 启动失败：${child.taskLog}`)
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1000) })
      if (response.ok) return
    } catch { /* 服务尚未就绪，继续短间隔检查。 */ }
    await new Promise(resolve => setTimeout(resolve, 200))
  }
  throw new Error(`${child.taskName} 启动超时：${child.taskLog}`)
}

async function stop(child) {
  if (!child) return
  if (child.exitCode === null && child.signalCode === null && child.pid) {
    const exited = once(child, 'exit')
    child.kill()
    await exited
  }
  await writeFile(path.join(resultDir, `${child.taskName}.log`), child.taskLog)
}

/** 仅读取本轮随机临时目录中的库名，Python 会再次验证名称格式。 */
async function cleanupDatabase() {
  try {
    await access(fixturesPath)
  } catch (error) {
    if (error.code === 'ENOENT') return
    throw error
  }
  const cleanup = launch(python, ['-u', '-c', backendSource, '--cleanup'], path.join(root, 'backend'), testEnv, 'cleanup')
  const [code] = await once(cleanup, 'exit')
  await stop(cleanup)
  if (code !== 0) throw new Error(`隔离库清理失败：${cleanup.taskLog}`)
}

const uiPort = await freePort()
let apiPort = await freePort()
while (apiPort === uiPort) apiPort = await freePort()
const base = `http://127.0.0.1:${uiPort}`
const apiBase = `http://127.0.0.1:${apiPort}`
const clientOrigin = 'http://127.0.0.1:8000'
const testEnv = { ...process.env, UI_FIXTURES: fixturesPath, UI_ORIGIN: base, UI_BACKEND_PORT: String(apiPort) }
let browser, backend, preview
try {
  backend = launch(python, ['-u', '-c', backendSource], path.join(root, 'backend'), testEnv, 'backend')
  preview = launch(process.execPath, [path.join(frontend, 'node_modules/vite/bin/vite.js'), 'preview', '--host', '127.0.0.1', '--port', String(uiPort), '--strictPort'], frontend, process.env, 'preview')
  await Promise.all([ready(`${apiBase}/openapi.json`, backend), ready(base, preview)])
  const manifest = JSON.parse(await readFile(fixturesPath, 'utf8'))
  browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const page = await context.newPage()
  page.setDefaultTimeout(10000)
  // 请求始终转发到本轮独立后端，故障注入仅用于页面恢复场景。
  const requests = [], errors = [], passed = []
  let fault = null
  page.on('pageerror', error => errors.push(error.message))
  await context.route(`${clientOrigin}/**`, async route => {
    const request = route.request()
    const url = new URL(request.url())
    const entry = { method: request.method(), path: url.pathname, body: request.postDataJSON(), auth: request.headers().authorization }
    requests.push(entry)
    if (fault && fault.method === entry.method && fault.path === entry.path && fault.remaining > 0) {
      const current = fault
      current.remaining--
      if (current.gate) await current.gate
      if (current.abort) return route.abort('failed')
      if (current.status) return route.fulfill({ status: current.status, contentType: 'application/json', body: JSON.stringify({ detail: current.detail }) })
    }
    const response = await route.fetch({ url: `${apiBase}${url.pathname}${url.search}` })
    await route.fulfill({ response })
  })
  async function check(name, action) {
    await action()
    passed.push(name)
    console.log(`PASS ${name}`)
  }
  async function textVisible(text) { await page.getByText(text, { exact: true }).first().waitFor() }
  async function alertVisible(text) { await page.getByRole('alert').filter({ hasText: text }).first().waitFor() }
  async function go(url) { await page.goto(`${base}${url}`) }
  async function login(email) {
    await go('/login')
    await page.locator('input[type=email]').fill(email)
    await page.locator('input[type=password]').fill('demo-local-only')
    await page.getByRole('button', { name: '登录', exact: true }).click()
    await page.waitForURL('**/navpage')
  }
  async function api(method, url, token, body) {
    const response = await fetch(`${apiBase}${url}`, { method, headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body ? { 'Content-Type': 'application/json' } : {}) }, body: body ? JSON.stringify(body) : undefined })
    const value = response.status === 204 ? null : await response.json()
    return { status: response.status, value }
  }
  async function tokenFor(email) { return (await api('POST', '/users/login', null, { email, password: 'demo-local-only' })).value.access_token }
  function count(method, url) { return requests.filter(r => r.method === method && r.path === url).length }
  function inject(method, url, status, detail) { fault = { method, path: url, status, detail, remaining: method === 'GET' ? Infinity : 1 } }
  const token = await tokenFor('demo-employer1@example.com')
  await api('PATCH','/employer/company',token,{company_name:'Acme Demo Labs',company_description:'Local demo employer one.'})
  for (const job of (await api('GET','/employer/jobs',token)).value) {
    if (job.title.startsWith('UI job') || job.title === 'Double submit job' || job.title === '<script>alert(1)</script>') await api('DELETE',`/employer/jobs/${job.id}`,token)
  }
  await api('PATCH',`/employer/applications/${manifest.aliceApplication}/status`,token,{status:'Interviewing'})
  try {
    await check('未登录访问所有雇主路由均跳登录', async () => {
      for (const route of ['/employer/company','/employer/jobs','/employer/jobs/new',`/employer/jobs/${manifest.backendJob}`,`/employer/jobs/${manifest.backendJob}/edit`]) {
        await go(route); await page.waitForURL('**/login')
      }
    })
    await login('demo-employer1@example.com')
    await check('主页雇主入口和公司资料入口', async () => {
      await page.getByRole('button', { name: '雇主工作流' }).click(); await page.waitForURL('**/employer/jobs')
      await textVisible('Backend Engineer')
      await page.getByRole('link', { name: '公司资料', exact: true }).click(); await page.getByLabel('公司名称（必填）').waitFor()
      assert.equal(await page.getByLabel('公司名称（必填）').inputValue(), 'Acme Demo Labs')
    })
    await check('空白公司名拦截且不请求', async () => {
      const before = count('PATCH','/employer/company')
      await page.getByLabel('公司名称（必填）').fill('   ')
      await page.getByRole('button', { name: '保存公司资料' }).click(); await alertVisible('不能只填写空格')
      assert.equal(count('PATCH','/employer/company'), before)
    })
    await check('公司只提交修改字段并可清空描述', async () => {
      await page.getByLabel('公司名称（必填）').fill('Acme Demo Labs')
      await page.getByLabel('公司描述', { exact: true }).fill('')
      await page.getByRole('button', { name: '保存公司资料' }).click(); await textVisible('已保存')
      assert.deepEqual(requests.filter(r=>r.method==='PATCH' && r.path==='/employer/company').at(-1).body, {company_description:''})
      assert.equal((await api('GET','/employer/company',token)).value.company_description,'')
    })
    await check('公司 422 和网络失败保留输入，可重试', async () => {
      await page.getByLabel('公司名称（必填）').fill('Updated Company')
      inject('PATCH','/employer/company',422,[{loc:['body','company_name'],msg:'Injected validation error'}])
      await page.getByRole('button',{name:'保存公司资料'}).click(); await alertVisible('body.company_name: Injected validation error')
      assert.equal(await page.getByLabel('公司名称（必填）').inputValue(),'Updated Company')
      fault = {method:'PATCH',path:'/employer/company',abort:true,remaining:1}
      await page.getByRole('button',{name:'保存公司资料'}).click(); await alertVisible('Failed to fetch')
      assert.equal(await page.getByLabel('公司名称（必填）').inputValue(),'Updated Company')
      fault=null
      await page.getByRole('button',{name:'保存公司资料'}).click(); await textVisible('已保存')
      await page.reload(); assert.equal(await page.getByLabel('公司名称（必填）').inputValue(),'Updated Company')
    })
    await check('公司保存中禁用，连续提交只请求一次', async () => {
      await page.getByLabel('公司描述',{exact:true}).fill('Saved once')
      let release
      const gate = new Promise(resolve => {release=resolve})
      fault={method:'PATCH',path:'/employer/company',gate,remaining:1}
      const before=count('PATCH','/employer/company')
      await page.locator('form').evaluate(form=>{form.requestSubmit();form.requestSubmit()})
      await page.getByRole('button',{name:'保存中...'}).waitFor()
      assert.equal(await page.getByLabel('公司名称（必填）').isDisabled(),true)
      assert.equal(count('PATCH','/employer/company'),before+1)
      release(); await textVisible('已保存'); fault=null
    })
    await check('职位列表显示字段与最新公司名称', async () => {
      await page.getByRole('link',{name:'职位列表',exact:true}).click(); await textVisible('Backend Engineer')
      const row=page.getByRole('listitem').filter({hasText:'Backend Engineer'})
      assert.match(await row.innerText(),/Updated Company/); assert.match(await row.innerText(),/python, sql/)
      assert.equal(await row.locator('time').count(),1)
    })
    await check('新建职位空白标题和描述拦截', async () => {
      await page.getByRole('link',{name:'新建职位',exact:true}).click()
      await page.getByLabel('标题（必填）').fill('   ')
      await page.getByLabel('描述（必填）').fill('description')
      const before=count('POST','/employer/jobs')
      await page.getByRole('button',{name:'保存职位'}).click(); await alertVisible('标题和描述不能为空')
      await page.getByLabel('标题（必填）').fill('UI job')
      await page.getByLabel('描述（必填）').fill('   ')
      await page.getByRole('button',{name:'保存职位'}).click(); await alertVisible('标题和描述不能为空')
      assert.equal(count('POST','/employer/jobs'),before)
    })
    await check('职位 422 保留输入；新建技能拆分、归一化并返回列表', async () => {
      await page.getByLabel('描述（必填）').fill('UI description\nsecond line')
      await page.getByLabel('所需技能（逗号分隔，可留空）').fill(' Python,SQL，python, , ')
      inject('POST','/employer/jobs',422,[{loc:['body','title'],msg:'Test rejection'}])
      await page.getByRole('button',{name:'保存职位'}).click(); await alertVisible('body.title: Test rejection')
      assert.equal(await page.getByLabel('标题（必填）').inputValue(),'UI job')
      assert.equal(await page.getByLabel('所需技能（逗号分隔，可留空）').inputValue(),' Python,SQL，python, , ')
      fault=null
      await page.getByRole('button',{name:'保存职位'}).click(); await page.waitForURL('**/employer/jobs'); await textVisible('UI job')
      const job=(await api('GET','/employer/jobs',token)).value.find(j=>j.title==='UI job')
      manifest.uiJob=job.id; assert.deepEqual(job.required_skills,['python','sql'])
    })
    await check('职位编辑回填并清空技能，刷新后持久化', async () => {
      await page.getByRole('listitem').filter({hasText:'UI job'}).getByRole('link',{name:'编辑',exact:true}).click()
      assert.equal(await page.getByLabel('标题（必填）').inputValue(),'UI job')
      await page.getByLabel('标题（必填）').fill('UI job edited')
      await page.getByLabel('所需技能（逗号分隔，可留空）').fill('')
      await page.getByRole('button',{name:'保存职位'}).click(); await page.waitForURL('**/employer/jobs'); await textVisible('UI job edited')
      assert.deepEqual((await api('GET',`/employer/jobs/${manifest.uiJob}`,token)).value.required_skills,[])
      await page.reload(); await textVisible('UI job edited')
    })
    await check('职位编辑 PATCH 422 保留全部输入并可重试', async () => {
      await go(`/employer/jobs/${manifest.uiJob}/edit`)
      await page.getByLabel('标题（必填）').waitFor()
      inject('PATCH',`/employer/jobs/${manifest.uiJob}`,422,[{loc:['body','description'],msg:'Edit validation failed'}])
      await page.getByRole('button',{name:'保存职位'}).click(); await alertVisible('body.description: Edit validation failed')
      assert.equal(await page.getByLabel('标题（必填）').inputValue(),'UI job edited')
      assert.equal(await page.getByLabel('描述（必填）').inputValue(),'UI description\nsecond line')
      assert.equal(await page.getByLabel('所需技能（逗号分隔，可留空）').inputValue(),'')
      fault=null; await page.getByRole('button',{name:'保存职位'}).click(); await page.waitForURL('**/employer/jobs'); await textVisible('UI job edited')
    })
    await check('新建表单重置；职位提交与删除防重复且禁用', async () => {
      await page.getByRole('link',{name:'新建职位',exact:true}).click()
      assert.equal(await page.getByLabel('标题（必填）').inputValue(),'')
      assert.equal(await page.getByLabel('描述（必填）').inputValue(),'')
      await page.getByLabel('标题（必填）').fill('Double submit job')
      await page.getByLabel('描述（必填）').fill('Saved once')
      let release; const gate=new Promise(resolve=>{release=resolve})
      fault={method:'POST',path:'/employer/jobs',gate,remaining:1}; const before=count('POST','/employer/jobs')
      await page.locator('form').evaluate(form=>{form.requestSubmit();form.requestSubmit()})
      await page.getByRole('button',{name:'保存中...'}).waitFor()
      assert.equal(await page.getByLabel('标题（必填）').isDisabled(),true)
      assert.equal(count('POST','/employer/jobs'),before+1)
      release(); await page.waitForURL('**/employer/jobs'); await textVisible('Double submit job'); fault=null
      const double=(await api('GET','/employer/jobs',token)).value.find(j=>j.title==='Double submit job')
      let releaseDelete; const deleteGate=new Promise(resolve=>{releaseDelete=resolve})
      const url=`/employer/jobs/${double.id}`; const beforeDelete=count('DELETE',url)
      fault={method:'DELETE',path:url,gate:deleteGate,remaining:1}
      const row=page.getByRole('listitem').filter({hasText:'Double submit job'})
      await row.getByRole('button',{name:'删除',exact:true}).evaluate(button=>{button.click();button.click()})
      await row.getByRole('button',{name:'删除中...'}).waitFor()
      assert.equal(await row.getByRole('button',{name:'删除中...'}).isDisabled(),true)
      assert.equal(count('DELETE',url),beforeDelete+1)
      releaseDelete(); await textVisible('已删除职位：Double submit job'); fault=null
    })
    await check('空申请人、职位描述换行及编辑入口', async () => {
      await page.getByRole('listitem').filter({hasText:'UI job edited'}).getByRole('link',{name:'查看详情/申请人'}).click()
      await textVisible('暂无申请人'); assert.match(await page.getByRole('region',{name:'职位信息'}).innerText(),/UI description\nsecond line/)
      await page.getByRole('link',{name:'编辑职位'}).waitFor()
    })
    await check('申请人分数降序、同分姓名与稳定 ID 排序、预约和隐私', async () => {
      await go(`/employer/jobs/${manifest.backendJob}`)
      await page.getByRole('table').waitFor()
      const rows=await page.locator('tbody tr').all()
      assert.equal(rows.length,5)
      assert.deepEqual(await Promise.all(rows.map(r=>r.locator('td').nth(1).innerText())),['100','100','100','50','0'])
      assert.deepEqual(await Promise.all(rows.slice(0,2).map(r=>r.locator('small').innerText())),['00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000002'])
      const alice=page.getByRole('row').filter({has:page.getByRole('rowheader',{name:/^Alice/})})
      assert.match(await alice.innerText(),/UTC/); assert.equal(await alice.locator('time').count(),2)
      const bob=page.getByRole('row').filter({has:page.getByRole('rowheader',{name:/^Bob/})})
      assert.equal(await bob.locator('td').last().innerText(),'无')
      assert.doesNotMatch(await page.locator('body').innerText(),/PRIVATE MUST NOT LEAK|Demo resume/)
      await page.screenshot({path:path.join(resultDir,'applicants.png'),fullPage:true})
    })
    await check('固定四种状态且每种保存后立即更新，离开 Interviewing 保留预约', async () => {
      const alice=page.getByRole('row').filter({has:page.getByRole('rowheader',{name:/^Alice/})})
      assert.deepEqual(await alice.locator('option').allTextContents(),['Pending','Interviewing','Rejected','Accepted'])
      for (const status of ['Pending','Interviewing','Rejected','Accepted']) {
        await alice.getByRole('combobox').selectOption(status)
        await alice.getByRole('button',{name:'保存状态'}).click()
        await alice.getByText(`当前状态：${status}`,{exact:true}).waitFor()
        assert.equal(await alice.locator('time').count(),2)
      }
      const saved=(await api('GET',`/employer/jobs/${manifest.backendJob}/applications`,token)).value.find(a=>a.application_id===manifest.aliceApplication)
      assert.equal(saved.status,'Accepted'); assert.ok(saved.booking)
    })
    await check('改状态 403/404 显示原消息并保留选择与当前状态', async () => {
      const alice=page.getByRole('row').filter({has:page.getByRole('rowheader',{name:/^Alice/})})
      const url=`/employer/applications/${manifest.aliceApplication}/status`
      for (const [status,detail] of [[403,'Not the owner of this job'],[404,'Application not found']]) {
        await alice.getByRole('combobox').selectOption('Rejected'); inject('PATCH',url,status,detail)
        await alice.getByRole('button',{name:'保存状态'}).click(); await alertVisible(detail)
        assert.equal(await alice.getByRole('combobox').inputValue(),'Rejected')
        await alice.getByText('当前状态：Accepted',{exact:true}).waitFor()
        await alice.getByRole('link',{name:'返回职位列表'}).waitFor()
      }
      fault=null; await alice.getByRole('button',{name:'保存状态'}).click(); await alice.getByText('当前状态：Rejected',{exact:true}).waitFor()
    })
    await check('状态保存中仅禁用该行，连续提交只请求一次', async () => {
      const alice=page.getByRole('row').filter({has:page.getByRole('rowheader',{name:/^Alice/})})
      const url=`/employer/applications/${manifest.aliceApplication}/status`
      let release; const gate=new Promise(resolve=>{release=resolve})
      fault={method:'PATCH',path:url,gate,remaining:1}; const before=count('PATCH',url)
      await alice.getByRole('combobox').selectOption('Interviewing')
      await alice.locator('form').evaluate(form=>{form.requestSubmit();form.requestSubmit()})
      await alice.getByRole('button',{name:'保存中...'}).waitFor()
      assert.equal(await alice.getByRole('combobox').isDisabled(),true)
      assert.equal(await page.getByRole('row').filter({has:page.getByRole('rowheader',{name:/^Bob/})}).getByRole('combobox').isEnabled(),true)
      assert.equal(count('PATCH',url),before+1)
      release(); await alice.getByText('当前状态：Interviewing',{exact:true}).waitFor(); fault=null
    })
    await check('实际他人职位详情与编辑 403，缺失职位 404', async () => {
      for (const suffix of ['', '/edit']) {
        await go(`/employer/jobs/${manifest.otherJob}${suffix}`); await alertVisible('Not the owner of this job'); await page.getByRole('link',{name:'返回职位列表'}).waitFor()
        await go(`/employer/jobs/ffffffff-ffff-ffff-ffff-ffffffffffff${suffix}`); await alertVisible('Job not found'); await page.getByRole('link',{name:'返回职位列表'}).waitFor()
      }
    })
    await check('申请人加载失败保留职位，重试可恢复', async () => {
      inject('GET',`/employer/jobs/${manifest.backendJob}/applications`,503,'Applicants temporarily unavailable')
      await go(`/employer/jobs/${manifest.backendJob}`); await alertVisible('Applicants temporarily unavailable'); await textVisible('Backend Engineer')
      fault=null; await page.getByRole('button',{name:'重新加载'}).click(); await page.getByRole('table').waitFor()
    })
    await check('有申请和仅面试时段两种删除 409 均保留职位', async () => {
      await go('/employer/jobs'); await textVisible('Backend Engineer')
      for (const title of ['Backend Engineer','Slot dependency only']) {
        await page.getByRole('listitem').filter({hasText:title}).getByRole('button',{name:'删除',exact:true}).click()
        await alertVisible('有申请或面试时段，不能删除'); await textVisible(title)
      }
      assert.equal((await api('GET',`/employer/jobs/${manifest.backendJob}`,token)).status,200)
      assert.equal((await api('GET',`/employer/jobs/${manifest.slotJob}`,token)).status,200)
    })
    await check('删除 403/404 原消息且不移除记录', async () => {
      for (const [status,detail] of [[403,'Delete forbidden'],[404,'Delete missing']]) {
        inject('DELETE',`/employer/jobs/${manifest.uiJob}`,status,detail)
        await page.getByRole('listitem').filter({hasText:'UI job edited'}).getByRole('button',{name:'删除',exact:true}).click()
        await alertVisible(detail); await textVisible('UI job edited')
      }
      fault=null
    })
    await check('无依赖职位 DELETE 204 成功移除且刷新后不再出现', async () => {
      await page.getByRole('listitem').filter({hasText:'UI job edited'}).getByRole('button',{name:'删除',exact:true}).click()
      await textVisible('已删除职位：UI job edited')
      assert.equal(await page.getByRole('heading',{name:'UI job edited',exact:true}).count(),0)
      await page.reload(); await textVisible('Backend Engineer')
      assert.equal(await page.getByRole('heading',{name:'UI job edited',exact:true}).count(),0)
      assert.equal((await api('GET',`/employer/jobs/${manifest.uiJob}`,token)).status,404)
    })
    await check('列表网络失败提示，重新加载恢复', async () => {
      fault={method:'GET',path:'/employer/jobs',abort:true,remaining:Infinity}
      await go('/employer/jobs'); await alertVisible('Failed to fetch')
      fault=null; await page.getByRole('button',{name:'重新加载'}).click(); await textVisible('Backend Engineer')
    })
    await check('公司 GET 404 引导创建；公司 GET 失败可重试', async () => {
      inject('GET','/employer/company',404,'Company not found')
      await go('/employer/company'); await textVisible('Company not found'); await page.getByRole('link',{name:'填写公司资料',exact:true}).waitFor()
      inject('GET','/employer/company',503,'Company unavailable')
      await page.reload(); await alertVisible('Company unavailable')
      fault=null; await page.getByRole('button',{name:'重新加载'}).click(); assert.equal(await page.getByLabel('公司名称（必填）').inputValue(),'Updated Company')
    })
    await check('XSS 载荷按纯文本展示且不执行（真实保存和读取）', async () => {
      const payload='<script>alert(1)</script>'
      const xss=(await api('POST','/employer/jobs',token,{title:payload,description:payload,required_skills:[payload]})).value
      let dialogs=0; page.on('dialog',async dialog=>{dialogs++;await dialog.dismiss()})
      await go(`/employer/jobs/${xss.id}`); await page.getByRole('heading',{name:payload,exact:true}).waitFor()
      assert.equal(await page.locator('main script').count(),0); assert.equal(dialogs,0)
      assert.equal((await api('DELETE',`/employer/jobs/${xss.id}`,token)).status,204)
    })
    await check('candidate 入口占位，所有雇主页面拒绝且不发送雇主请求', async () => {
      await go('/navpage'); await page.getByRole('button',{name:'注销'}).click(); await page.waitForURL('**/login')
      await login('demo-alice@example.com')
      await page.getByRole('button',{name:'候选人工作流'}).click(); await textVisible('候选人工作流尚未实现')
      const before=requests.filter(r=>r.path.startsWith('/employer')).length
      for (const route of ['/employer/company','/employer/jobs','/employer/jobs/new',`/employer/jobs/${manifest.backendJob}`,`/employer/jobs/${manifest.backendJob}/edit`]) {
        await go(route); await alertVisible('仅雇主可访问此页面。')
      }
      assert.equal(requests.filter(r=>r.path.startsWith('/employer')).length,before)
    })
    await check('真实服务端 401/403/404 与非法状态 422', async () => {
      const candidate=await tokenFor('demo-alice@example.com')
      assert.equal((await api('GET','/employer/jobs')).status,401)
      assert.equal((await api('GET','/employer/jobs',candidate)).status,403)
      assert.equal((await api('GET',`/employer/jobs/${manifest.otherJob}/applications`,token)).status,403)
      assert.equal((await api('PATCH',`/employer/jobs/${manifest.otherJob}`,token,{title:'Forbidden'})).status,403)
      assert.equal((await api('DELETE',`/employer/jobs/${manifest.otherJob}`,token)).status,403)
      assert.equal((await api('PATCH',`/employer/applications/${manifest.aliceApplication}/status`,candidate,{status:'Accepted'})).status,403)
      assert.equal((await api('PATCH',`/employer/applications/ffffffff-ffff-ffff-ffff-ffffffffffff/status`,token,{status:'Pending'})).status,404)
      assert.equal((await api('PATCH',`/employer/applications/${manifest.aliceApplication}/status`,token,{status:'Unknown'})).status,422)
    })
    await check('无公司账号沿用现有补填页，创建后空职位列表', async () => {
      const email=`ui-blank-${Date.now()}@example.com`
      const created=await api('POST','/users/register',null,{email,password:'demo-local-only',role:'employer'})
      assert.equal((await api('GET','/employer/company',created.value.access_token)).status,404)
      await go('/navpage'); await page.getByRole('button',{name:'注销'}).click(); await page.waitForURL('**/login')
      await page.locator('input[type=email]').fill(email); await page.locator('input[type=password]').fill('demo-local-only')
      await page.getByRole('button',{name:'登录',exact:true}).click(); await page.waitForURL('**/employer/details')
      await page.getByLabel('公司名称（必填）').fill('New UI company'); await page.getByRole('button',{name:'保存并继续'}).click(); await page.waitForURL('**/navpage')
      await page.getByRole('button',{name:'雇主工作流'}).click(); await textVisible('暂无职位')
    })
    await check('雇主请求均带 Bearer，浏览器无未处理异常', async () => {
      assert.ok(requests.filter(r=>r.path.startsWith('/employer')).every(r=>r.auth?.startsWith('Bearer ')))
      assert.deepEqual(errors,[])
    })
    await writeFile(path.join(resultDir,'results.json'),JSON.stringify({passed:passed.length,checks:passed,errors,backend:apiBase,frontend:base,database:manifest.database},null,2))
    console.log(`ALL ${passed.length} CHECK GROUPS PASSED`)
  } catch(error) {
    await page.screenshot({path:path.join(resultDir,'failure.png'),fullPage:true})
    console.error('FAILED after',passed.length,'groups at',page.url())
    throw error
  }

} finally {
  try {
    await browser?.close()
  } finally {
    const stopped = await Promise.allSettled([stop(preview), stop(backend)])
    for (const result of stopped) {
      if (result.status === 'rejected') {
        console.error('临时服务清理失败：', result.reason)
        process.exitCode = 1
      }
    }
    await cleanupDatabase()
  }
}
