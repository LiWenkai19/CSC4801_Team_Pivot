import assert from 'node:assert/strict';
import path from 'node:path';
import {chromium,firefox,webkit} from 'playwright';
import {base,server,api,identity,posting,save} from './browser_support.mjs';

const sha='8569b72ac1d965c252a741f3e62ed71b01f630e7', results=[], versions=[];
async function check(engine,id,fn){try{const detail=await fn();results.push({engine,id,outcome:'passed',detail});}catch(error){results.push({engine,id,outcome:'failed',error:String(error.stack)});}await save('frontend-final-results.json',{sha,versions,results});}
const shanghai=value=>new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',dateStyle:'medium',timeStyle:'short',hour12:false}).format(new Date(value));
try{
 for(const [engine,type,options] of [['chrome',chromium,(process.env.CHROME_EXECUTABLE_PATH?{executablePath:process.env.CHROME_EXECUTABLE_PATH}:{})],['firefox',firefox,{}],['webkit',webkit,{}]]){
  const browser=await type.launch({headless:true,...options});versions.push({engine,version:browser.version()});
  try{
   const employer=await identity(browser,'employer'), candidate=await identity(browser), other=await identity(browser);
   await api(candidate,'PATCH','/candidate/profile',{display_name:'Revision Candidate A'});
   await api(other,'PATCH','/candidate/profile',{display_name:'Revision Candidate B'});
   const job=await posting(employer,`Revision Job ${engine}`);
   const first=await api(candidate,'POST',`/candidate/jobs/${job.id}/applications`,{});
   const second=await api(other,'POST',`/candidate/jobs/${job.id}/applications`,{});
   await check(engine,'latest-job-link-desktop-and-keyboard',async()=>{
    await candidate.page.goto(base+'/candidate/jobs');
    const row=candidate.page.locator('li').filter({has:candidate.page.getByRole('heading',{name:job.title,exact:true})});
    const link=row.getByRole('link',{name:'查看职位',exact:true});await link.waitFor();
    assert.equal(await link.getAttribute('href'),`/candidate/jobs/${job.id}`);
    assert((await link.getAttribute('class')).includes('button-primary'));await link.focus();await link.press('Enter');
    await candidate.page.waitForURL(`**/candidate/jobs/${job.id}`);await candidate.page.getByRole('heading',{name:job.title,exact:true}).waitFor();
   });
   await check(engine,'latest-job-link-390-layout-and-click',async()=>{
    await candidate.page.setViewportSize({width:390,height:900});await candidate.page.goto(base+'/candidate/jobs');
    const row=candidate.page.locator('li').filter({has:candidate.page.getByRole('heading',{name:job.title,exact:true})});
    const link=row.getByRole('link',{name:'查看职位',exact:true});await link.waitFor();
    const box=await link.boundingBox();assert(box&&box.height>=38);assert(box.x>=0&&box.x+box.width<=391);
    assert(await candidate.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await link.click();await candidate.page.waitForURL(`**/candidate/jobs/${job.id}`);
    return {link_box:box};
   });
   await employer.page.goto(base+`/employer/jobs/${job.id}`);
   const card=name=>employer.page.locator('li.employer-applicant-card').filter({has:employer.page.getByRole('heading',{name,exact:true})});
   await check(engine,'latest-applicant-card-status-isolation',async()=>{
    await card('Revision Candidate A').getByRole('heading',{name:'Revision Candidate A',exact:true}).waitFor();
    assert.equal(await card('Revision Candidate A').locator('.employer-applicant-score strong').innerText(),'50 / 100');
    await card('Revision Candidate A').getByRole('combobox').selectOption('Interviewing');await card('Revision Candidate A').getByRole('button',{name:'保存状态',exact:true}).click();
    await card('Revision Candidate A').getByText('状态已保存',{exact:true}).waitFor();
    assert.equal((await api(candidate,'GET','/candidate/applications')).find(a=>a.application_id===first.application_id).status,'Interviewing');
    assert.equal((await api(other,'GET','/candidate/applications')).find(a=>a.application_id===second.application_id).status,'Pending');
   });
   const slot=await api(employer,'POST','/employer/interview-slots',{starts_at:'2031-04-05T01:00:00Z'});
   let booking;
   await check(engine,'latest-booking-times-after-save-and-reload',async()=>{
    await candidate.page.goto(base+'/candidate/applications');await candidate.page.getByRole('button',{name:'加载可预约时段',exact:true}).click();
    await candidate.page.getByRole('combobox',{name:'选择面试时段（上海时间）',exact:true}).selectOption(slot.id);await candidate.page.getByRole('button',{name:'确认预约',exact:true}).click();
    await candidate.page.getByText('面试已预约：',{exact:false}).waitFor();
    for(const reload of [false,true]){
     if(reload){await candidate.page.reload();await candidate.page.getByText('面试已预约：',{exact:false}).waitFor();}
     await candidate.page.getByText('面试时间均为上海时间（UTC+8）。',{exact:true}).waitFor();
     const times=candidate.page.locator('time');assert.equal(await times.count(),2);
     assert.equal(await times.nth(0).getAttribute('datetime'),slot.starts_at);assert.equal(await times.nth(0).innerText(),shanghai(slot.starts_at));
     assert.equal(await times.nth(1).innerText(),shanghai(slot.ends_at));
    }
    booking=(await api(candidate,'GET','/candidate/applications')).find(a=>a.application_id===first.application_id).booking;assert.equal(booking.slot_id,slot.id);
    return {browser_timezone:'America/New_York',display_timezone:'Asia/Shanghai',booking};
   });
   await check(engine,'latest-applicant-booking-and-390-layout',async()=>{
    await employer.page.reload();await card('Revision Candidate A').locator('time').first().waitFor();assert.equal(await card('Revision Candidate A').locator('time').count(),2);
    assert.equal(await card('Revision Candidate B').locator('time').count(),0);
    await employer.page.getByText('按匹配分从高到低排列，面试时间为上海时间（UTC+8）。',{exact:true}).waitFor();
    const geometries=[];
    for(const width of [1280,390]){
     await employer.page.setViewportSize({width,height:900});assert(await employer.page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
     const heading=await card('Revision Candidate A').getByRole('heading',{name:'Revision Candidate A',exact:true}).boundingBox(), score=await card('Revision Candidate A').locator('.employer-applicant-score').boundingBox();
     assert(heading&&score&&heading.x+heading.width<=score.x+1);geometries.push({width,heading,score});
    }
    await employer.page.screenshot({path:path.join(process.env.UI_OUT,`latest-applicant-${engine}-390.png`),fullPage:true});
    return {geometries,applicants:(await api(employer,'GET',`/employer/jobs/${job.id}/applications`)).map(a=>({id:a.application_id,status:a.status,booking:a.booking}))};
   });
   await check(engine,'latest-changed-pages-no-unhandled-errors',async()=>{assert.deepEqual(candidate.errors,[]);assert.deepEqual(employer.errors,[]);assert.deepEqual(other.errors,[]);});
  }finally{await browser.close();}
 }
}finally{await new Promise(resolve=>server.close(resolve));await save('frontend-final-results.json',{sha,versions,results});}
console.log(JSON.stringify({total:results.length,passed:results.filter(x=>x.outcome==='passed').length,failed:results.filter(x=>x.outcome==='failed').length}));process.exitCode=results.some(x=>x.outcome==='failed')?1:0;
