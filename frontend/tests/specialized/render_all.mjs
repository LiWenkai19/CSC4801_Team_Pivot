// Exercise actual TSX render expressions with deterministic initial hook states.
// The required script-shaped course string is inert SSR data; no browser execution.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const out=process.env.UI_OUT,root=process.env.UI_SOURCE,target=path.join(out,'render-all');
const {default:ts}=await import(pathToFileURL(path.join(root,'node_modules/typescript/lib/typescript.js')).href);
await fs.mkdir(target,{recursive:true});await fs.writeFile(path.join(target,'package.json'),'{"type":"module"}');
const extras={'pages/employer/JobDetailPage.tsx':'export {ApplicantCard,JobDetail};','pages/candidate/JobPage.tsx':'export {JobContent};'};
async function compile(dir){for(const item of await fs.readdir(dir,{withFileTypes:true})){
 const p=path.join(dir,item.name);if(item.isDirectory()){await compile(p);continue;}if(!/\.tsx?$/.test(item.name))continue;
 const rel=path.relative(path.join(root,'src'),p).replaceAll('\\','/');let source=await fs.readFile(p,'utf8');source+='\n'+(extras[rel]||'');
 let code=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
 code=code.replace(/^import\s+['"][^'"]+\.css['"];?\s*$/gm,'');
 code=code.replace(/(from\s+['"])(\.[^'"]+)(['"])/g,(_,a,b,c)=>a+(/\.js$/.test(b)?b:b+'.js')+c);
 code=code.replace(/(from\s+['"])(react(?:\/jsx-runtime)?|react-router-dom)(['"])/g,(_,a,b,c)=>a+pathToFileURL(path.join(root,'node_modules',b==='react-router-dom'?'react-router-dom/dist/index.mjs':b==='react/jsx-runtime'?'react/jsx-runtime.js':'react/index.js')).href+c);
 if(/\buseState\(/.test(code)){
   code=code.replace(/\buseState\(/g,'__auditUseState(');
   code+='\nfunction __auditUseState(initial){const q=globalThis.__AUDIT_RENDER_STATE__?.['+JSON.stringify(rel)+'];return useState(q?.length?q.shift():initial);}\n';
 }
 const destination=path.join(target,rel).replace(/\.tsx?$/,'.js');await fs.mkdir(path.dirname(destination),{recursive:true});await fs.writeFile(destination,code);
}}
await compile(path.join(root,'src'));
const {default:React}=await import(pathToFileURL(path.join(root,'node_modules/react/index.js')).href);
const {renderToStaticMarkup}=await import(pathToFileURL(path.join(root,'node_modules/react-dom/server.node.js')).href);
const {MemoryRouter}=await import(pathToFileURL(path.join(root,'node_modules/react-router-dom/dist/index.mjs')).href);
const load=async name=>import(pathToFileURL(path.join(target,name.replace(/\.tsx$/,'.js'))).href);
const {AuthContext}=await load('contexts/AuthContext.tsx');
const components={};for(const name of ['pages/candidate/ProfilePage.tsx','pages/candidate/JobsPage.tsx','pages/candidate/ApplicationsPage.tsx','pages/candidate/JobPage.tsx','pages/employer/CompanyPage.tsx','pages/employer/JobListPage.tsx','pages/employer/JobDetailPage.tsx','pages/users/CandidateForm.tsx','pages/users/EmployerForm.tsx','components/skills/SkillTagPicker.tsx'])components[name]=await load(name);
const records=[];const inputStrings=['<script>alert(1)</script>','<b>audit & literal</b>','普通 résumé 🌏\n第二行'];
const escape=x=>x.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#x27;'}[c]));
for(const [i,value] of inputStrings.entries()){
 const job={id:'job',title:value,description:value,company_name:value,company_description:'公司简介 '+value,required_skills:[value],match_score:100,applied:false,created_at:'2030-01-01T00:00:00Z'};
 const profile={display_name:value,resume_text:value,skills:[value],user_id:'candidate'};
 const company={company_name:value,company_description:value,user_id:'employer'};
 const applicant={application_id:'app',candidate_id:'candidate',display_name:value,skills:[value],match_score:100,status:'Pending',booking:null};
 const application={application_id:'app',job_id:'job',job_title:value,company_name:value,status:'Pending',booking:null};
 const specs=[
  ['profile-name-resume-skills','candidate','pages/candidate/ProfilePage.tsx',[profile,false,'','','',false,0],{},'default'],
  ['recommended-job-title-company-skills','candidate','pages/candidate/JobsPage.tsx',[[job],false,'',0],{},'default'],
  ['job-detail-title-description-company-skills','candidate','pages/candidate/JobPage.tsx',[job,false,'',0],{jobId:'job'},'JobContent'],
  ['application-job-company','candidate','pages/candidate/ApplicationsPage.tsx',[[application],false,'',0],{},'default'],
  ['company-name-description','employer','pages/employer/CompanyPage.tsx',[company,value,value,false,false,false,'','',0],{},'default'],
  ['employer-job-list','employer','pages/employer/JobListPage.tsx',[[job],false,'','','',null,0],{},'default'],
  ['employer-job-and-applicant-detail','employer','pages/employer/JobDetailPage.tsx',[job,[applicant],false,'','',0],{jobId:'job'},'JobDetail'],
  ['initial-candidate-form','candidate','pages/users/CandidateForm.tsx',[value,value,[value],''],{submitting:false,submitError:'',onSubmit:async()=>{}},'default'],
  ['initial-employer-form','employer','pages/users/EmployerForm.tsx',[value,value,''],{submitting:false,submitError:'',onSubmit:async()=>{}},'default'],
  ['skill-search-query-tags-status','candidate','components/skills/SkillTagPicker.tsx',[value,value],{value:[value],onChange:()=>{}},'default'],
 ];
 for(const [id,role,name,states,props,exportName] of specs){
  globalThis.__AUDIT_RENDER_STATE__={[name]:states.slice()};
  try{
   const currentUser={id:role,email:role+'@example.com',role,profile_completed:true};
   const auth={currentUser,loading:false,logout:async()=>{},refreshCurrentUser:async()=>currentUser,getAuthDestination:()=>'/navpage'};
   const node=React.createElement(MemoryRouter,null,React.createElement(AuthContext.Provider,{value:auth},React.createElement(components[name][exportName],props)));
   const html=renderToStaticMarkup(node);
   assert(!html.includes('<script>'),'No executable script markup');assert(!html.includes('<b>'),'No raw formatted HTML');assert(html.includes(escape(value)),'Exact escaped marker emitted by actual component');
   if(name==='pages/candidate/JobsPage.tsx'){
    assert(html.includes('<p class="record-meta">'+escape(value)+'</p>'),'Job preview shows company name only');
    assert(!html.includes(escape(job.company_description)),'Job preview must not display company description');
   }
   if(name==='pages/candidate/JobPage.tsx')assert(html.includes('<p class="page-intro company-summary">'+escape(value+'：'+job.company_description)+'</p>'),'Job detail shows name followed by company description');
   records.push({id:id+'-'+i,outcome:'passed',component:name,text_class:i,html_sha256:(await import('node:crypto')).createHash('sha256').update(html).digest('hex')});
  }catch(e){records.push({id:id+'-'+i,outcome:'failed',component:name,text_class:i,error:String(e.stack)});}
 }
}
delete globalThis.__AUDIT_RENDER_STATE__;
await fs.writeFile(path.join(out,'all-render-results.json'),JSON.stringify({sha:process.env.GAP_SHA,records,method:'Original latest-main TSX render expressions; TypeScript transpile, CSS omitted; module-local useState adapter injects only initial fixtures; private render components exposed in generated artifacts. Does not exercise effects/events or replace independent browser evidence.',script_execution:false,scope:'10 component/output groups × 3 text classes; no general free-text search feature except skill query'},null,2));
console.log(JSON.stringify({total:records.length,passed:records.filter(r=>r.outcome==='passed').length,failed:records.filter(r=>r.outcome==='failed').length}));process.exitCode=records.some(r=>r.outcome==='failed')?1:0;
