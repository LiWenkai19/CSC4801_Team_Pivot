import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { chromium, request } from 'playwright';
const out=process.env.UI_OUT,results=[];
const server=http.createServer(async(req,res)=>{
 if(req.url.startsWith('/api/')){const p=http.request({host:'127.0.0.1',port:process.env.UI_API_PORT,path:req.url.slice(4),method:req.method,headers:req.headers},r=>{res.writeHead(r.statusCode,r.headers);r.pipe(res);});p.on('error',()=>{res.writeHead(502);res.end();});req.pipe(p);return;}
 try{const filename=req.url.startsWith('/assets/')?path.join(process.env.UI_DIST,'assets',path.basename(req.url)):path.join(process.env.UI_DIST,'index.html');res.setHeader('Content-Type',filename.endsWith('.js')?'text/javascript':filename.endsWith('.css')?'text/css':'text/html');res.end(await fs.readFile(filename));}catch{res.writeHead(404);res.end();}
});await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE_PATH?{executablePath:process.env.CHROME_EXECUTABLE_PATH}:{})});
async function fresh(){const context=await browser.newContext();await context.addInitScript(()=>{if(!localStorage.getItem('skillmatch.language'))localStorage.setItem('skillmatch.language','zh-CN');});const page=await context.newPage();page.setDefaultTimeout(5000);return {context,page};}
async function check(id,fn){let evidence={};try{await fn(evidence);results.push({id,outcome:'passed',evidence});console.log('PASS '+id);}catch(e){results.push({id,outcome:'failed',error:String(e.stack),evidence});console.log('FAIL '+id+' '+e.message.slice(0,160));}}
async function api(v,method,route,data){const cookies=await v.context.cookies(base);const csrf=cookies.find(c=>c.name==='csrf_token')?.value;const r=await v.context.request.fetch(base+'/api'+route,{method,data,headers:csrf?{'X-CSRF-Token':csrf}:{}});assert(r.ok());return r.json();}
/** 使用隔离服务创建已登录的候选人或雇主。 */
async function actor(complete, role = 'candidate') {
    const v = await fresh();
    v.user = (await api(v, 'POST', '/users/register', {
        email: `expiry-${Date.now()}-${Math.random().toString(16).slice(2)}@example.com`,
        password: 'local-browser-only', role,
    })).user;
    if (complete) await api(v, 'POST', '/users/candidate/profile', {display_name: 'Expiry Candidate'});
    return v;
}
function expire(v){execFileSync(process.env.UI_PYTHON,[process.env.UI_EXPIRE_TOOL,v.user.id],{env:process.env,windowsHide:true,stdio:['ignore','pipe','pipe']});}

const logoutRoutes = [
    {path: '/navpage', label: '注销', complete: true, role: 'candidate'},
    {path: '/candidate/details', label: '退出登录', complete: false, role: 'candidate'},
    {path: '/employer/details', label: '退出登录', complete: false, role: 'employer'},
];
const logoutUrl = base + '/api/users/logout';
const meUrl = base + '/api/users/me';

/** 在独立请求上下文撤销同一会话，保留页面中的原 Cookie。 */
async function revokeFromAnotherContext(context) {
    const storageState = await context.storageState();
    const csrf = storageState.cookies.find(cookie => cookie.name === 'csrf_token')?.value;
    assert(csrf);
    const client = await request.newContext({storageState});
    try {
        const response = await client.post(logoutUrl, {headers: {'X-CSRF-Token': csrf}});
        assert.equal(response.status(), 204);
    } finally {
        await client.dispose();
    }
}

/** 用真实会话验证注销后跳转，或留在原页并显示可重试的错误。 */
async function verifyLogout(entry, scenario, evidence) {
    const {page, context, user} = await actor(entry.complete, entry.role);
    try {
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        await page.goto(base + entry.path);
        const button = page.getByRole('button', {name: entry.label, exact: true});
        await button.waitFor();

        if (scenario === 'expired') expire({user});
        if (scenario === 'check-unavailable') await page.route(meUrl, route => route.fulfill({status: 500}));
        if (scenario === 'network') await page.route(logoutUrl, route => route.abort('failed'));
        if (['session-active', 'session-revoked', 'check-unavailable'].includes(scenario)) {
            await page.route(logoutUrl, async route => {
                if (scenario === 'session-revoked') await revokeFromAnotherContext(context);
                await route.fulfill({status: 500});
            });
        }

        const checks = [];
        page.on('response', response => {
            if (response.url() === meUrl) checks.push(response.status());
        });
        const logoutResult = scenario === 'network'
            ? page.waitForEvent('requestfailed', event => event.url() === logoutUrl)
            : page.waitForResponse(response => response.url() === logoutUrl);
        await button.click();
        const result = await logoutResult;
        const status = scenario === 'network' ? 'network' : result.status();
        const signedOut = ['normal', 'expired', 'session-revoked'].includes(scenario);
        if (signedOut) {
            await page.waitForURL(base + '/login');
        } else {
            const message = scenario === 'check-unavailable'
                ? '暂时无法确认是否已注销，请重试。'
                : '注销失败，请重试。';
            await page.getByRole('alert').filter({hasText: message}).waitFor();
            await button.and(page.locator(':enabled')).waitFor();
            assert.equal(page.url(), base + entry.path);
        }

        const sessionStatus = (await context.request.get(meUrl)).status();
        Object.assign(evidence, {status, checks, sessionStatus, errors});
        assert.equal(status, {normal: 204, expired: 401, network: 'network'}[scenario] ?? 500);
        const checkStatus = {network: 200, 'session-active': 200, 'session-revoked': 401, 'check-unavailable': 500}[scenario];
        assert.deepEqual(checks, checkStatus ? [checkStatus] : []);
        assert.equal(sessionStatus, signedOut ? 401 : 200);
        assert.deepEqual(errors, []);

        if (!signedOut) {
            await page.unroute(logoutUrl);
            await page.unroute(meUrl);
            const retried = page.waitForResponse(response => response.url() === logoutUrl);
            await button.click();
            assert.equal((await retried).status(), 204);
            await page.waitForURL(base + '/login');
            assert.equal((await context.request.get(meUrl)).status(), 401);
            assert.deepEqual(errors, []);
        }
    } finally {
        await context.close();
    }
}

try{
for(const route of ['login','register'])await check('FOCUS-LABEL-'+route,async evidence=>{const v=await fresh();await v.page.goto(base+'/'+route);await v.page.locator('input[type=email]').waitFor();evidence.inputs=await v.page.locator('input').evaluateAll(nodes=>nodes.map(n=>({type:n.type,id:n.id,associatedLabels:n.labels.length,ariaLabel:n.getAttribute('aria-label'),ariaLabelledby:n.getAttribute('aria-labelledby')})));evidence.visibleLabels=await v.page.locator('label').allTextContents();assert(evidence.inputs.every(n=>n.associatedLabels>0||n.ariaLabel||n.ariaLabelledby),'Visible credential labels must name each input');await v.context.close();});
await check('FOCUS-LABEL-click-login-email',async evidence=>{const v=await fresh();await v.page.goto(base+'/login');await v.page.locator('label').filter({hasText:'邮箱'}).click();evidence.focusedType=await v.page.evaluate(()=>document.activeElement?.getAttribute('type'));assert.equal(evidence.focusedType,'email');await v.context.close();});
await check('FOCUS-LABEL-profile-positive-control',async()=>{const v=await actor(true);await v.page.goto(base+'/candidate/profile');await v.page.getByLabel('显示名称（必填）').waitFor();await v.page.locator('label[for="display-name"]').click();assert.equal(await v.page.evaluate(()=>document.activeElement.id),'display-name');await v.context.close();});
for (const entry of logoutRoutes) {
    for (const scenario of ['normal', 'expired', 'session-active', 'session-revoked', 'check-unavailable', 'network']) {
        await check(`FOCUS-LOGOUT${entry.path}-${scenario}`, evidence => verifyLogout(entry, scenario, evidence));
    }
}
await check('FOCUS-EXPIRY-reload-redirect-control',async()=>{const v=await actor(true);await v.page.goto(base+'/candidate/jobs');await v.page.getByRole('heading',{level:1}).waitFor();expire(v);await v.page.reload();await v.page.waitForURL('**/login');await v.context.close();});
}finally{await fs.writeFile(path.join(out,process.env.UI_STAGE_MODE+'-results.json'),JSON.stringify({base,browser:browser.version(),results},null,2));await browser.close();await new Promise(r=>server.close(r));}
console.log(JSON.stringify({total:results.length,passed:results.filter(r=>r.outcome==='passed').length,failed:results.filter(r=>r.outcome==='failed').length}));process.exitCode=results.some(r=>r.outcome==='failed')?1:0;
