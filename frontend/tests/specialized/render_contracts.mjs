// Pure server-side rendering; course-required string is inert data, never executed.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
const root=process.env.UI_SOURCE;
const {default:ts}=await import(pathToFileURL(path.join(root,'node_modules/typescript/lib/typescript.js')).href);
const target=path.join(process.env.UI_OUT,'render-components');await fs.mkdir(target,{recursive:true});
await fs.writeFile(path.join(target,'package.json'),'{"type":"module"}');
async function compile(dir){for(const item of await fs.readdir(dir,{withFileTypes:true})){
 const p=path.join(dir,item.name);if(item.isDirectory()){await compile(p);continue;}
 if(!/\.tsx?$/.test(item.name))continue;
 let source=await fs.readFile(p,'utf8');
 if(item.name==='JobDetailPage.tsx')source+='\nexport { ApplicantCard };\n';
 let code=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
 code=code.replace(/^import\s+['"][^'"]+\.css['"];?\s*$/gm,'');
 code=code.replace(/(from\s+['"])(\.[^'"]+)(['"])/g,(_,a,b,c)=>a+(/\.js$/.test(b)?b:b+'.js')+c);
 code=code.replace(/(from\s+['"])(react(?:\/jsx-runtime)?|react-router-dom)(['"])/g,(_,a,b,c)=>a+pathToFileURL(path.join(root,'node_modules',b==='react-router-dom'?'react-router-dom/dist/index.mjs':b==='react/jsx-runtime'?'react/jsx-runtime.js':'react/index.js')).href+c);
 const destination=path.join(target,path.relative(path.join(root,'src'),p)).replace(/\.tsx?$/,'.js');await fs.mkdir(path.dirname(destination),{recursive:true});await fs.writeFile(destination,code);
}}
await compile(path.join(root,'src'));
const {default:React}=await import(pathToFileURL(path.join(root,'node_modules/react/index.js')).href);
const {renderToStaticMarkup}=await import(pathToFileURL(path.join(root,'node_modules/react-dom/server.node.js')).href);
const {MemoryRouter}=await import(pathToFileURL(path.join(root,'node_modules/react-router-dom/dist/index.mjs')).href);
const {default:Picker}=await import(pathToFileURL(path.join(target,'components/skills/SkillTagPicker.js')).href);
const {ApplicantCard}=await import(pathToFileURL(path.join(target,'pages/employer/JobDetailPage.js')).href);
const {default:LanguageProvider}=await import(pathToFileURL(path.join(target,'i18n/LanguageProvider.js')).href);
globalThis.window={localStorage:{getItem:()=> 'zh-CN'}};
const render=node=>renderToStaticMarkup(React.createElement(LanguageProvider,null,node));
const records=[];function check(id,fn){try{fn();records.push({id,outcome:'passed'});}catch(e){records.push({id,outcome:'failed',error:String(e.stack)});}}
const inputs=['<script>alert(1)</script>','<b>Audit & literal</b>','普通 résumé 🌏'];
for(const [i,input] of inputs.entries())check('RENDER-SKILL-'+i,()=>{const html=render(React.createElement(Picker,{value:[input],onChange:()=>{},legend:'Skills',selectedLabel:'Selected skills',inputLabel:'Search skills',addLabel:'Add',help:'',emptyHint:'No matches'}));assert(!html.includes('<script>'));assert(!html.includes('<b>'));assert(html.includes(i===0?'&lt;script&gt;alert(1)&lt;/script&gt;':i===1?'&lt;b&gt;audit &amp; literal&lt;/b&gt;':input));});
for(const [i,input] of inputs.slice(0,2).entries())check('RENDER-APPLICANT-'+i,()=>{
 const row={version:1,application_id:'application',candidate_id:'candidate',display_name:input,skills:[input],match_score:100,status:'Pending',booking:null};
 const html=render(React.createElement(MemoryRouter,null,React.createElement('ul',null,React.createElement('li',null,React.createElement(ApplicantCard,{applicant:row,jobId:'job',onUpdated:()=>{}})))));
 assert(!html.includes('<script>'));assert(!html.includes('<b>'));assert(html.includes(i===0?'&lt;script&gt;alert(1)&lt;/script&gt;':'&lt;b&gt;Audit &amp; literal&lt;/b&gt;'));
});
check('RENDER-BOOKING-UTC',()=>{const row={version:1,application_id:'a',candidate_id:'c',display_name:'Normal',skills:[],match_score:0,status:'Accepted',booking:{starts_at:'2030-06-01T10:00:00+08:00',ends_at:'2030-06-01T10:30:00+08:00'}};const html=render(React.createElement(MemoryRouter,null,React.createElement('ul',null,React.createElement('li',null,React.createElement(ApplicantCard,{applicant:row,jobId:'job',onUpdated:()=>{}})))));const expected=new Intl.DateTimeFormat('zh-CN',{timeZone:'Asia/Shanghai',dateStyle:'medium',timeStyle:'medium',hourCycle:'h23'});for(const value of [row.booking.starts_at,row.booking.ends_at]){assert(html.includes(expected.format(new Date(value))));assert(html.includes(`dateTime="${value}"`));}});
await fs.writeFile(path.join(process.env.UI_OUT,'render-contract-results.json'),JSON.stringify({records,method:'Original TSX transpiled with TypeScript; CSS omitted; private ApplicantCard export exposed only in artifact; no rendering logic changed; no JS payload execution'},null,2));
console.log(JSON.stringify(records));process.exitCode=records.some(r=>r.outcome==='failed')?1:0;
