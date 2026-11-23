import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright';

const out=process.env.UI_OUT, mode=process.env.UI_STAGE_MODE, dist=process.env.UI_DIST;
const results=[], consoleErrors=[], contexts=[];
const shots=path.join(out,'screenshots'); await fs.mkdir(shots,{recursive:true});
// Test-only same-origin proxy: real HTTP to the isolated backend, unchanged production assets.
const server=http.createServer(async(req,res)=>{
  if(req.url.startsWith('/api/')) {
    const p=http.request({host:'127.0.0.1',port:Number(process.env.UI_API_PORT),path:req.url.slice(4),method:req.method,headers:req.headers},r=>{res.writeHead(r.statusCode,r.headers);r.pipe(res);});
    p.on('error',()=>{res.writeHead(502);res.end();}); req.pipe(p); return;
  }
  try{
    const url=new URL(req.url,'http://localhost');
    const filename=url.pathname.startsWith('/assets/')?path.join(dist,'assets',path.basename(url.pathname)):path.join(dist,'index.html');
    const data=await fs.readFile(filename);
    res.setHeader('Content-Type',filename.endsWith('.js')?'text/javascript':filename.endsWith('.css')?'text/css':'text/html');res.end(data);
  }catch{res.writeHead(404);res.end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE_PATH?{executablePath:process.env.CHROME_EXECUTABLE_PATH}:{})});
let seq=0;
async function fresh(){
  const context=await browser.newContext({viewport:{width:1280,height:900},timezoneId:'America/New_York'}); contexts.push(context);
  const page=await context.newPage(); page.setDefaultTimeout(6000);
  page.on('pageerror',e=>consoleErrors.push(e.message));
  page.on('dialog',async d=>{consoleErrors.push('Unexpected dialog');await d.dismiss();});
  return {context,page};
}
async function api(context,method,route,data){
  const cookies=await context.cookies(base);const csrf=cookies.find(c=>c.name==='csrf_token')?.value;
  const response=await context.request.fetch(base+'/api'+route,{method,data,headers:csrf?{'X-CSRF-Token':csrf}:{}});
  assert(response.ok(),`${method} ${route}: ${response.status()} ${await response.text()}`);
  return response.status()===204?null:response.json();
}
async function identity(role='candidate',complete=true){
  const value=await fresh();value.email=`${role}-${Date.now()}-${++seq}@example.com`;
  value.user=await api(value.context,'POST','/users/register',{email:value.email,password:'local-browser-only',role});
  if(complete) await api(value.context,'POST',`/users/${role}/profile`,role==='candidate'?{display_name:'Browser Candidate',skills:['python'],resume_text:'Ordinary résumé 中文'}:{company_name:'Browser Company',company_description:'Ordinary company 中文'});
  return value;
}
async function go(v,p){await v.page.goto(base+p);}
async function visible(p,text){await p.getByText(text,{exact:true}).first().waitFor();}
async function check(id,action){
  const started=Date.now();try{const detail=await action();results.push({id,outcome:'passed',ms:Date.now()-started,detail});console.log('PASS '+id);}
  catch(e){results.push({id,outcome:'failed',ms:Date.now()-started,error:String(e.stack)});console.log('FAIL '+id+' '+e.message.slice(0,300));}
  await fs.writeFile(path.join(out,mode+'-results.json'),JSON.stringify({base,browser:browser.version(),results,consoleErrors},null,2));
}
async function loginUI(v){await go(v,'/login');await v.page.locator('input[type=email]').fill(v.email);await v.page.locator('input[type=password]').fill('local-browser-only');await v.page.getByRole('button',{name:'登录',exact:true}).click();await v.page.waitForURL('**/navpage');}
const markers='<b>Audit & literal text</b> 中文';
try{
await check('UI-AUTH-01-anonymous-deep-link',async()=>{const v=await fresh();await go(v,'/candidate/profile');await v.page.waitForURL('**/login');await v.page.getByRole('button',{name:'登录',exact:true}).waitFor();});
for(const role of ['candidate','employer']) await check('UI-AUTH-02-register-'+role,async()=>{
 const v=await fresh();await go(v,'/register');await v.page.locator('input[type=email]').fill(`ui-${role}-${Date.now()}@example.com`);const pw=v.page.locator('input[type=password]');await pw.nth(0).fill('local-browser-only');await pw.nth(1).fill('local-browser-only');await v.page.locator('select').selectOption(role);await v.page.getByRole('button',{name:'注册',exact:true}).click();await v.page.waitForURL('**/'+role+'/details');await go(v,'/'+role+'/jobs');await v.page.waitForURL('**/'+role+'/details');
 await v.page.getByLabel(role==='candidate'?'显示名称（必填）':'公司名称（必填）').fill('Browser '+role);await v.page.getByRole('button',{name:'保存并继续'}).click();await v.page.waitForURL('**/navpage');await v.page.reload();await v.page.getByRole('heading',{name:'招聘工作台',exact:true}).waitFor();assert.equal((await api(v.context,'GET','/users/me')).profile_completed,true);
 await v.page.getByRole('button',{name:'注销',exact:true}).click();await v.page.waitForURL('**/login');const response=await v.context.request.get(base+'/api/users/me');assert.equal(response.status(),401);
});
await check('UI-AUTH-03-confirm-mismatch-retains-input',async()=>{const v=await fresh();await go(v,'/register');await v.page.locator('input[type=email]').fill('mismatch@example.com');await v.page.locator('input[type=password]').nth(0).fill('first');await v.page.locator('input[type=password]').nth(1).fill('second');let posts=0;v.page.on('request',r=>{if(r.url().endsWith('/api/users/register'))posts++;});await v.page.getByRole('button',{name:'注册',exact:true}).click();await visible(v.page,'Passwords do not match');assert.equal(posts,0);assert.equal(await v.page.locator('input[type=email]').inputValue(),'mismatch@example.com');});
await check('UI-AUTH-04-invalid-login-and-recovery',async()=>{const v=await identity();await api(v.context,'POST','/users/logout');await go(v,'/login');await v.page.locator('input[type=email]').fill(v.email);await v.page.locator('input[type=password]').fill('wrong-normal-password');await v.page.getByRole('button',{name:'登录',exact:true}).click();await visible(v.page,'Invalid credentials');assert.equal(await v.page.locator('input[type=email]').inputValue(),v.email);await v.page.locator('input[type=password]').fill('local-browser-only');await v.page.getByRole('button',{name:'登录',exact:true}).click();await v.page.waitForURL('**/navpage');});
for(const role of ['candidate','employer']) await check('UI-AUTH-05-opposite-role-'+role,async()=>{const v=await identity(role);await go(v,role==='candidate'?'/employer/jobs':'/candidate/jobs');await visible(v.page,role==='candidate'?'仅雇主可访问此页面。':'仅候选人可访问此页面。');});
await check('UI-AUTH-06-incomplete-profile-sign-out',async()=>{const v=await identity('candidate',false);await go(v,'/navpage');await v.page.waitForURL('**/candidate/details');await v.page.getByRole('button',{name:'退出登录'}).click();await v.page.waitForURL('**/login');});
await check('UI-PROFILE-01-save-failure-preserves-form-and-retries',async()=>{
 const v=await identity();await go(v,'/candidate/profile');const name=v.page.getByLabel('显示名称（必填）');await name.fill('Retry Candidate');await v.page.getByLabel('简历（选填）').fill(markers);
 let failSave=true;
 await v.context.route('**/api/candidate/profile',async route=>{if(route.request().method()==='PATCH'&&failSave){failSave=false;return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Local retry check'})});}return route.continue();});
 await v.page.getByRole('button',{name:'保存资料',exact:true}).click();await visible(v.page,'Local retry check');assert.equal(await name.inputValue(),'Retry Candidate');assert.equal((await api(v.context,'GET','/candidate/profile')).display_name,'Browser Candidate');await v.page.getByRole('button',{name:'保存资料',exact:true}).click();await visible(v.page,'资料已保存，职位推荐会使用最新技能。');await v.page.reload();assert.equal(await v.page.getByLabel('简历（选填）').inputValue(),markers);
});
await check('UI-PROFILE-02-pending-skill-keyboard-and-clear',async()=>{const v=await identity();await go(v,'/candidate/profile');await v.page.getByLabel('搜索或输入技能').fill('custom-skill');await v.page.getByRole('button',{name:'保存资料',exact:true}).click();assert.deepEqual((await api(v.context,'GET','/candidate/profile')).skills,['python']);await v.page.getByLabel('搜索或输入技能').press('Enter');await v.page.getByRole('button',{name:'移除 python',exact:true}).click();await v.page.getByRole('button',{name:'保存资料',exact:true}).click();await visible(v.page,'资料已保存，职位推荐会使用最新技能。');assert.deepEqual((await api(v.context,'GET','/candidate/profile')).skills,['custom-skill']);});

const employer=await identity('employer'), candidate=await identity();let posting, application, slot;
await check('UI-JOB-01-create-and-render-literal-text',async()=>{
 await go(employer,'/employer/jobs/new');await employer.page.getByLabel('标题（必填）').fill(markers);await employer.page.getByLabel('描述（必填）').fill(markers);await employer.page.getByLabel('所需技能（逗号分隔，可留空）').fill('Python， SQL, python');await employer.page.getByRole('button',{name:'保存职位',exact:true}).click();await employer.page.waitForURL('**/employer/jobs');posting=(await api(employer.context,'GET','/employer/jobs')).find(j=>j.title===markers);assert(posting);assert.deepEqual(posting.required_skills,['python','sql']);await go(candidate,'/candidate/jobs/'+posting.id);await candidate.page.getByRole('heading',{name:markers,exact:true}).waitFor();await visible(candidate.page,'匹配分数：50 / 100');assert.equal(await candidate.page.locator('main b').count(),0);
});
await check('UI-APPLICATION-01-apply-once-and-reload',async()=>{assert(posting);await go(candidate,'/candidate/jobs/'+posting.id);await candidate.page.getByRole('button',{name:'申请职位',exact:true}).click();await visible(candidate.page,'你已申请该职位，请勿重复申请。');await candidate.page.reload();await candidate.page.getByRole('button',{name:'已申请',exact:true}).waitFor();const rows=await api(candidate.context,'GET','/candidate/applications');assert.equal(rows.length,1);application=rows[0];assert.equal(application.status,'Pending');});
await check('UI-JOB-02-dependent-delete-conflict-retains-row',async()=>{assert(application);await go(employer,'/employer/jobs');const row=employer.page.locator('li').filter({has:employer.page.getByRole('heading',{name:markers,exact:true})});await row.getByRole('button',{name:'删除',exact:true}).click();await visible(employer.page,'有申请或面试时段，不能删除');await row.getByRole('heading',{name:markers,exact:true}).waitFor();assert.equal((await api(employer.context,'GET','/employer/jobs')).length,1);});
await check('UI-APPLICATION-02-employer-status-save',async()=>{assert(application);await go(employer,'/employer/jobs/'+posting.id);await employer.page.getByRole('combobox').selectOption('Interviewing');await employer.page.getByRole('button',{name:'保存状态',exact:true}).click();await visible(employer.page,'状态已保存');assert.equal((await api(candidate.context,'GET','/candidate/applications'))[0].status,'Interviewing');});
await check('UI-SLOT-01-create-shanghai-time-and-overlap',async()=>{await go(employer,'/employer/interview-slots');await employer.page.getByLabel('开始时间（上海时间 UTC+8）').fill('2030-06-01T10:00');await employer.page.getByRole('button',{name:'创建 30 分钟时段',exact:true}).click();await visible(employer.page,'已创建面试时段。');let rows=await api(employer.context,'GET','/employer/interview-slots');assert.equal(rows.length,1);slot=rows[0];assert.equal(new Date(slot.starts_at).toISOString(),'2030-06-01T02:00:00.000Z');assert.equal(new Date(slot.ends_at)-new Date(slot.starts_at),1800000);await employer.page.getByLabel('开始时间（上海时间 UTC+8）').fill('2030-06-01T10:15');await employer.page.getByRole('button',{name:'创建 30 分钟时段',exact:true}).click();await visible(employer.page,'与已有面试时段重叠，请选择其他开始时间。');assert.equal((await api(employer.context,'GET','/employer/interview-slots')).length,1);});
await check('UI-BOOKING-01-candidate-book-both-views',async()=>{assert(application&&slot);await go(candidate,'/candidate/applications');await candidate.page.getByRole('button',{name:'加载可预约时段',exact:true}).click();await candidate.page.getByLabel('选择面试时段（上海时间）').selectOption(slot.id);await candidate.page.getByRole('button',{name:'确认预约',exact:true}).click();await candidate.page.getByText('面试已预约：',{exact:false}).waitFor();await employer.page.reload();await employer.page.getByRole('button',{name:'刷新时段',exact:true}).waitFor();await visible(employer.page,'已预约');assert(await employer.page.getByRole('button',{name:'删除',exact:true}).isDisabled());await go(employer,'/employer/jobs/'+posting.id);await employer.page.locator('.employer-applicant-card time').first().waitFor();assert.equal(new Date(await employer.page.locator('.employer-applicant-card time').first().getAttribute('datetime')).getTime(),new Date(slot.starts_at).getTime()); await visible(employer.page,'按匹配分从高到低排列，面试时间为上海时间（UTC+8）。');});
await check('UI-BOOKING-02-status-leaves-interviewing-preserves-booking',async()=>{assert(slot&&application);await go(employer,'/employer/jobs/'+posting.id);await employer.page.getByRole('combobox').selectOption('Accepted');await employer.page.getByRole('button',{name:'保存状态',exact:true}).click();await visible(employer.page,'状态已保存');await go(candidate,'/candidate/applications');await visible(candidate.page,'申请状态：已录用');await candidate.page.getByText('面试已预约：',{exact:false}).waitFor();assert.equal((await api(candidate.context,'GET','/candidate/applications'))[0].booking.slot_id,slot.id);});
await check('UI-JOB-03-edit-clear-requirements-and-delete-independent',async()=>{const p=await api(employer.context,'POST','/employer/jobs',{title:'Editable',description:'Normal',required_skills:['rust']});await go(employer,'/employer/jobs/'+p.id+'/edit');await employer.page.getByLabel('标题（必填）').fill('Edited');await employer.page.getByLabel('所需技能（逗号分隔，可留空）').fill('');await employer.page.getByRole('button',{name:'保存职位',exact:true}).click();await employer.page.waitForURL('**/employer/jobs');assert.deepEqual((await api(employer.context,'GET','/employer/jobs/'+p.id)).required_skills,[]);const row=employer.page.locator('li').filter({has:employer.page.getByRole('heading',{name:'Edited',exact:true})});await row.getByRole('button',{name:'删除',exact:true}).click();await visible(employer.page,'已删除职位：Edited');assert(!(await api(employer.context,'GET','/employer/jobs')).some(j=>j.id===p.id));});
await check('UI-COMPANY-01-edit-and-reload',async()=>{await go(employer,'/employer/company');await employer.page.getByLabel('公司名称（必填）').fill('Updated company');await employer.page.getByLabel('公司描述',{exact:true}).fill(markers);await employer.page.getByRole('button',{name:'保存公司资料'}).click();await visible(employer.page,'已保存');await employer.page.reload();assert.equal(await employer.page.getByLabel('公司描述',{exact:true}).inputValue(),markers);});
await check('UI-RECOVERY-01-list-load-retry',async()=>{const v=await identity();let fault=true;await v.context.route('**/api/candidate/jobs',route=>{if(fault){fault=false;return route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Local list unavailable'})});}return route.continue();});await go(v,'/candidate/jobs');await visible(v.page,'Local list unavailable');await v.page.getByRole('button',{name:'重新加载'}).click();await v.page.getByRole('heading',{name:markers,exact:true}).waitFor();});
for(const [role,v,paths] of [['candidate',candidate,['/candidate/jobs','/candidate/profile','/candidate/applications']],['employer',employer,['/employer/company','/employer/jobs','/employer/jobs/'+(posting?.id||'missing'),'/employer/interview-slots']]]){
 for(const width of [1280,390]) for(const route of paths) await check(`UI-LAYOUT-${role}-${width}-${route.split('/').pop()}`,async()=>{await v.page.setViewportSize({width,height:900});await go(v,route);await v.page.getByRole('heading',{level:1}).first().waitFor();await v.page.getByRole('status').filter({hasText:/^正在加载/}).waitFor({state:'hidden'});const geometry=await v.page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));await v.page.screenshot({path:path.join(shots,`${role}-${width}-${route.split('/').pop()}.png`),fullPage:true});assert(geometry.scroll<=geometry.width,JSON.stringify(geometry));await v.page.keyboard.press('Tab');assert(await v.page.evaluate(()=>document.activeElement!==document.body));return geometry;});
}
await check('UI-ACCESSIBLE-login-input-names',async()=>{const v=await fresh();await go(v,'/login');const count=await v.page.getByRole('textbox',{name:'邮箱',exact:true}).count();await v.page.screenshot({path:path.join(shots,'login.png'),fullPage:true});assert.equal(count,1,'Visible email label should name its textbox');});
await check('UI-ACCESSIBLE-register-input-names',async()=>{const v=await fresh();await go(v,'/register');assert.equal(await v.page.getByRole('textbox',{name:'邮箱',exact:true}).count(),1,'Visible email label should name its textbox');});
await check('UI-RUNTIME-no-page-exceptions',async()=>{assert.deepEqual(consoleErrors,[]);});
}finally{
 await fs.writeFile(path.join(out,mode+'-results.json'),JSON.stringify({base,browser:browser.version(),results,consoleErrors},null,2));
 await browser.close();await new Promise(r=>server.close(r));
}
const failed=results.filter(r=>r.outcome==='failed');console.log(JSON.stringify({total:results.length,passed:results.length-failed.length,failed:failed.length}));process.exitCode=failed.length?1:0;
