// Execute unchanged helper functions extracted from the tracked browser scripts.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
const out=process.env.UI_OUT, apiBase='http://127.0.0.1:'+process.env.UI_API_PORT;
const source=path.join(process.env.UI_SOURCE,'tests');const records=[];
for(const kind of ['candidate','employer']){
  const text=await fs.readFile(path.join(source,kind+'.browser.mjs'),'utf8');
  const begin=text.indexOf('async function api(');
  const end=text.indexOf(kind==='candidate'?'\nconst passed':'\n  async function tokenFor',begin);
  assert(begin>=0&&end>begin);
  const helper=new Function('apiBase','assert',text.slice(begin,end)+'; return api;')(apiBase,assert);
  const credentials={email:`helper-${kind}-${Date.now()}@example.com`,password:'local-browser-only',role:kind};
  const signup=await fetch(apiBase+'/users/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(credentials)});assert.equal(signup.status,200);
  const login=await helper('POST','/users/login',null,{email:credentials.email,password:credentials.password});
  const body=kind==='candidate'?login:login.value;
  let status, error;
  try{
    const read=await helper('GET',kind==='candidate'?'/users/me':'/employer/jobs',body.access_token);
    status=read.status||200;
  }catch(e){error=e.message;status=Number(/: (\d{3})/.exec(error)?.[1]||0);}
  records.push({id:'DEL-LEGACY-'+kind,outcome:status===200?'passed':'failed',login_body_keys:Object.keys(body),access_token_present:Object.hasOwn(body,'access_token'),protected_read_status:status,error,reason:'Tracked browser helper expects obsolete access_token/Bearer; node fetch has no cookie jar',source:kind+'.browser.mjs'});
}
await fs.writeFile(path.join(out,process.env.UI_STAGE_MODE+'-existing-browser-probes-results.json'),JSON.stringify(records,null,2));
console.log(JSON.stringify(records));process.exitCode=records.some(r=>r.outcome==='failed')?1:0;
