import assert from 'node:assert/strict';
import {chromium,firefox,webkit} from 'playwright';
import {base,server,api,identity,fresh,posting,save} from './browser_support.mjs';
const results=[];
const resultName=(process.env.UI_RESULT_PREFIX||'browser-followup')+'-results.json';
const focused={
 'webkit-nav':{engine:'webkit',id:'NAV-scoped-stale-response-replay'},
 'slot-cutoff':{engine:'chrome',id:'DATE-slot-cutoff-rejected-real-http'},
}[process.env.UI_SUITE_ONLY];
async function check(engine,id,fn){if(focused&&id!==focused.id)return;const detail={};try{await fn(detail);results.push({engine,id,outcome:'passed',detail});}catch(e){results.push({engine,id,outcome:'failed',detail,error:String(e.stack)});}await save(resultName,{sha:process.env.GAP_SHA,results});}
try{
 for(const [engine,type,options] of [['chrome',chromium,(process.env.CHROME_EXECUTABLE_PATH?{executablePath:process.env.CHROME_EXECUTABLE_PATH}:{})],['firefox',firefox,{}],['webkit',webkit,{}]]){
  if(focused&&engine!==focused.engine)continue;
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
   if(engine==='chrome')await check(engine,'DATE-slot-cutoff-rejected-real-http',async detail=>{
    // 结束时间跨入 3001 年时，页面显示上限提示，已有时段仍可读取。
    const e=await identity(browser,'employer');
    try{
     const route='/employer/interview-slots';
     const made=await api(e,'POST',route,{starts_at:'3000-12-31T15:29:59.999999Z'});
     await e.page.goto(base+route);
     await e.page.getByLabel('开始时间（上海时间 UTC+8）').fill('3000-12-31T23:30');
     const [rejected]=await Promise.all([
      e.page.waitForResponse(response=>response.url()===base+'/api'+route&&response.request().method()==='POST'),
      e.page.getByRole('button',{name:'创建 30 分钟时段'}).click(),
     ]);
     detail.create_status=rejected.status();
     assert.equal(rejected.status(),422,await rejected.text());
     await e.page.getByRole('alert').filter({hasText:'面试时段最晚只能安排在 3000 年内（北京时间）。'}).waitFor();
     const slots=await api(e,'GET',route);
     assert.deepEqual(slots.map(slot=>slot.id),[made.id]);
    }finally{await e.context.close();}
   });
   if(engine==='webkit')for(const width of [1280,390])await check(engine,'KEYBOARD-native-control-'+width,async detail=>{const e=await identity(browser,'employer');try{
    const j=await posting(e,'Native tab control');await e.page.setViewportSize({width,height:900});await e.page.goto(base+'/employer/jobs/'+j.id);await e.page.getByRole('heading',{name:'职位详情与申请人'}).waitFor();await e.page.getByRole('status').filter({hasText:/^正在加载/}).waitFor({state:'hidden'});await e.page.keyboard.press('Tab');detail.productTab=await e.page.evaluate(()=>document.activeElement.tagName);await e.page.keyboard.press('Alt+Tab');detail.productAltTab=await e.page.evaluate(()=>document.activeElement.tagName);const anchor=e.page.getByRole('link',{name:'返回职位列表',exact:true});await anchor.focus();assert.equal(await e.page.evaluate(()=>document.activeElement.tagName),'A');
    const control=await e.context.newPage();await control.setContent('<a href="#control">Native link</a>');await control.keyboard.press('Tab');detail.nativeTab=await control.evaluate(()=>document.activeElement.tagName);await control.keyboard.press('Alt+Tab');detail.nativeAltTab=await control.evaluate(()=>document.activeElement.tagName);assert.equal(detail.productTab,detail.nativeTab,'Compare project with native engine link-only control');detail.assessment='Link-only Tab behavior matches native WebKit control; not evidence of a product focus defect';
   }finally{await e.context.close();}});
  }finally{await browser.close();}
 }
}finally{await new Promise(r=>server.close(r));await save(resultName,{sha:process.env.GAP_SHA,results});}
console.log(JSON.stringify({total:results.length,passed:results.filter(r=>r.outcome==='passed').length,failed:results.filter(r=>r.outcome==='failed').length}));process.exitCode=results.some(r=>r.outcome==='failed')?1:0;
