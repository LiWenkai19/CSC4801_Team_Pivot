import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
export const out=process.env.UI_OUT;
export const server=http.createServer(async(req,res)=>{
 if(req.url.startsWith('/api/')){const p=http.request({host:'127.0.0.1',port:process.env.UI_API_PORT,path:req.url.slice(4),method:req.method,headers:req.headers},r=>{res.writeHead(r.statusCode,r.headers);r.pipe(res);});p.on('error',()=>{res.writeHead(502);res.end();});req.pipe(p);return;}
 try{const url=new URL(req.url,'http://localhost');const name=url.pathname.startsWith('/assets/')?path.join(process.env.UI_DIST,'assets',path.basename(url.pathname)):url.pathname==='/favicon.svg'?path.join(process.env.UI_DIST,'favicon.svg'):path.join(process.env.UI_DIST,'index.html');res.setHeader('Content-Type',name.endsWith('.js')?'text/javascript':name.endsWith('.css')?'text/css':name.endsWith('.svg')?'image/svg+xml':'text/html');res.end(await fs.readFile(name));}catch{res.writeHead(404);res.end();}
});await new Promise(r=>server.listen(0,'127.0.0.1',r));
export const base='http://127.0.0.1:'+server.address().port;
export async function api(v,method,route,data){const cookies=await v.context.cookies(base);const csrf=cookies.find(c=>c.name==='csrf_token')?.value;const r=await v.context.request.fetch(base+'/api'+route,{method,data,headers:csrf?{'X-CSRF-Token':csrf}:{}});assert(r.ok(),`${method} ${route}: ${r.status()} ${await r.text()}`);return r.status()===204?null:r.json();}
let n=0;
export async function fresh(browser){const context=await browser.newContext({viewport:{width:1280,height:900},timezoneId:'America/New_York'});await context.addInitScript(()=>{if(!localStorage.getItem('skillmatch.language'))localStorage.setItem('skillmatch.language','zh-CN');});const page=await context.newPage();page.setDefaultTimeout(7000);const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',async d=>{errors.push('Unexpected dialog');await d.dismiss();});return {context,page,errors};}
export async function identity(browser,role='candidate'){const v=await fresh(browser);v.email=`gap-${role}-${Date.now()}-${++n}@example.com`;v.user=(await api(v,'POST','/users/register',{email:v.email,password:'local-browser-only',role})).user;await api(v,'POST','/users/'+role+'/profile',role==='candidate'?{display_name:'Gap Candidate',resume_text:'Ordinary résumé 中文',skills:['python']}:{company_name:'Gap Company',company_description:'Ordinary synthetic company'});return v;}
export async function posting(v,title='Gap Job'){return api(v,'POST','/employer/jobs',{title,description:'Normal job description',required_skills:['python','sql']});}
export async function save(name,value){await fs.writeFile(path.join(out,name),JSON.stringify(value,null,2));}
export async function visible(page,text){await page.getByText(text,{exact:true}).first().waitFor();}
