import assert from 'node:assert/strict';
import {chromium,firefox,webkit} from 'playwright';
import {out,base,server,api,identity,fresh,posting,save} from './browser_support.mjs';
const results=[];
const resultName=(process.env.UI_RESULT_PREFIX||'browser-followup')+'-results.json';
async function check(engine,id,fn){if(process.env.UI_SUITE_ONLY==='webkit-nav'&&id!=='NAV-scoped-stale-response-replay')return;const detail={};try{await fn(detail);results.push({engine,id,outcome:'passed',detail});}catch(e){results.push({engine,id,outcome:'failed',detail,error:String(e.stack)});}await save(resultName,{sha:process.env.GAP_SHA,results});}
try{
 for(const [engine,type,options] of [['chrome',chromium,(process.env.CHROME_EXECUTABLE_PATH?{executablePath:process.env.CHROME_EXECUTABLE_PATH}:{})],['firefox',firefox,{}],['webkit',webkit,{}]]){
  if(process.env.UI_SUITE_ONLY==='webkit-nav'&&engine!=='webkit')continue;
  const browser=await type.launch({headless:true,...options});
  try{
   await check(engine,'NAV-scoped-stale-response-replay',async()=>{
    const e=await identity(browser,'employer'),c=await identity(browser);try{
     const a=await posting(e,'Delayed A'),b=await posting(e,'Current B');let release,arrived;const gate=new Promise(r=>release=r),ready=new Promise(r=>arrived=r);
     await c.context.route('**/api/candidate/jobs/'+a.id,async r=>{const response=await r.fetch();arrived();await gate;await r.fulfill({response});});
     await c.page.goto(base+'/candidate/jobs');await c.page.locator(`a[href="/candidate/jobs/${a.id}"]`).first().click();await ready;await c.page.getByRole('link',{name:'职位推荐',exact:true}).click();await c.page.locator(`a[href="/candidate/jobs/${b.id}"]`).first().click();await c.page.getByRole('heading',{name:'Current B',exact:true,level:1}).waitFor();release();await c.page.waitForTimeout(150);assert(c.page.url().endsWith('/'+b.id));assert.equal(await c.page.getByRole('heading',{name:'Delayed A',exact:true}).count(),0);
    }finally{await e.context.close();await c.context.close();}
   });
   await check(engine,'LABEL-new-password-and-confirm-focus-after-team-update',async()=>{const v=await fresh(browser);try{for(const route of ['login','register']){await v.page.goto(base+'/'+route);for(const text of (route==='login'?['密码']:['密码','确认密码'])){const input=v.page.getByLabel(text,{exact:true});await input.waitFor();const id=await input.getAttribute('id');await v.page.locator(`label[for="${id}"]`).click();assert.equal(await v.page.evaluate(()=>document.activeElement.id),id);}}}finally{await v.context.close();}});
   if(engine==='chrome')await check(engine,'DATE-accepted-slot-remains-readable-real-http',async detail=>{const e=await identity(browser,'employer');try{const made=await api(e,'POST','/employer/interview-slots',{starts_at:'9999-12-31T15:30:00Z'});const r=await e.context.request.get(base+'/api/employer/interview-slots');detail.created_id=made.id;detail.list_status=r.status();detail.timezone='Database Asia/Shanghai';assert.equal(r.status(),200,'An accepted slot must remain readable');}finally{await e.context.close();}});
   if(engine==='webkit')for(const width of [1280,390])await check(engine,'KEYBOARD-native-control-'+width,async detail=>{const e=await identity(browser,'employer');try{
    const j=await posting(e,'Native tab control');await e.page.setViewportSize({width,height:900});await e.page.goto(base+'/employer/jobs/'+j.id);await e.page.getByRole('heading',{name:'职位详情与申请人'}).waitFor();await e.page.getByRole('status').filter({hasText:/^正在加载/}).waitFor({state:'hidden'});await e.page.keyboard.press('Tab');detail.productTab=await e.page.evaluate(()=>document.activeElement.tagName);await e.page.keyboard.press('Alt+Tab');detail.productAltTab=await e.page.evaluate(()=>document.activeElement.tagName);const anchor=e.page.getByRole('link',{name:'返回职位列表',exact:true});await anchor.focus();assert.equal(await e.page.evaluate(()=>document.activeElement.tagName),'A');
    const control=await e.context.newPage();await control.setContent('<a href="#control">Native link</a>');await control.keyboard.press('Tab');detail.nativeTab=await control.evaluate(()=>document.activeElement.tagName);await control.keyboard.press('Alt+Tab');detail.nativeAltTab=await control.evaluate(()=>document.activeElement.tagName);assert.equal(detail.productTab,detail.nativeTab,'Compare project with native engine link-only control');detail.assessment='Link-only Tab behavior matches native WebKit control; not evidence of a product focus defect';
   }finally{await e.context.close();}});
  }finally{await browser.close();}
 }
}finally{await new Promise(r=>server.close(r));await save(resultName,{sha:process.env.GAP_SHA,results});}
console.log(JSON.stringify({total:results.length,passed:results.filter(r=>r.outcome==='passed').length,failed:results.filter(r=>r.outcome==='failed').length}));process.exitCode=results.some(r=>r.outcome==='failed')?1:0;
