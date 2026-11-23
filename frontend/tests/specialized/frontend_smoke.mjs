import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {chromium} from 'playwright';
import {base,server,api,identity,save} from './browser_support.mjs';
const out=process.env.UI_OUT,root=process.env.UI_SOURCE,results=[];
const {default:ts}=await import(pathToFileURL(path.join(root,'node_modules/typescript/lib/typescript.js')).href);
const file=path.join(root,'src/components/skills/SkillTagPicker.tsx');
const ast=ts.createSourceFile(file,await fs.readFile(file,'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
let suggestions=[];function walk(node){if(ts.isVariableDeclaration(node)&&node.name.getText(ast)==='suggestions'&&ts.isArrayLiteralExpression(node.initializer))suggestions=node.initializer.elements.map(e=>e.text);ts.forEachChild(node,walk);}walk(ast);
const norm=s=>s.trim().toLowerCase(),freq=new Map();for(const x of suggestions)freq.set(norm(x),(freq.get(norm(x))||0)+1);
const duplicated=[...freq].filter(([,n])=>n>1).map(([name,count])=>({name,count}));
await save('skill-dictionary-inventory.json',{entries:suggestions.length,unique_normalized:freq.size,duplicates:duplicated});
const browser=await chromium.launch({headless:true,...(process.env.CHROME_EXECUTABLE_PATH?{executablePath:process.env.CHROME_EXECUTABLE_PATH}:{})});
const user=await identity(browser);user.page.setDefaultTimeout(6000);
async function check(id,fn){try{await fn();results.push({id,outcome:'passed'});}catch(e){results.push({id,outcome:'failed',error:String(e.stack)});}await save('frontend-results.json',{results,version:browser.version(),source_sha:'8569b72ac1d965c252a741f3e62ed71b01f630e7'});}
try{
 await user.page.goto(base+'/candidate/profile');
 await check('new-dictionary-suggestion-add-and-persist',async()=>{await user.page.getByLabel('搜索或输入技能').fill('carbon accounting');await user.page.getByRole('button',{name:'Carbon Accounting',exact:true}).click();await user.page.getByRole('button',{name:'保存资料',exact:true}).click();await user.page.getByText('资料已保存，职位推荐会使用最新技能。',{exact:true}).waitFor();assert((await api(user,'GET','/candidate/profile')).skills.includes('carbon accounting'));});
 await check('custom-unlisted-skill-enter-and-dedup',async()=>{const input=user.page.getByLabel('搜索或输入技能');await input.fill('  自定义测试技能2026  ');await input.press('Enter');await input.fill(' 自定义测试技能2026 ');await input.press('Enter');assert.equal(await user.page.getByRole('button',{name:'移除 自定义测试技能2026',exact:true}).count(),1);await user.page.getByRole('button',{name:'保存资料',exact:true}).click();await user.page.getByText('资料已保存，职位推荐会使用最新技能。',{exact:true}).waitFor();assert.equal((await api(user,'GET','/candidate/profile')).skills.filter(s=>s==='自定义测试技能2026').length,1);});
 await check('pending-query-prevents-accidental-save',async()=>{const input=user.page.getByLabel('搜索或输入技能');await input.fill('pending-unadded');let patches=0;const observe=req=>{if(req.method()==='PATCH'&&req.url().endsWith('/api/candidate/profile'))patches++;};user.page.on('request',observe);await user.page.getByRole('button',{name:'保存资料',exact:true}).click();assert.equal(patches,0);user.page.off('request',observe);await input.fill('');});
 await check('IME-composition-enter-does-not-prematurely-add',async()=>{const input=user.page.getByLabel('搜索或输入技能');await input.fill('输入法测试');await input.evaluate(n=>n.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',isComposing:true,bubbles:true})));assert.equal(await user.page.getByRole('button',{name:'移除 输入法测试',exact:true}).count(),0);await input.press('Enter');assert.equal(await user.page.getByRole('button',{name:'移除 输入法测试',exact:true}).count(),1);});
 await check('normalized-dictionary-options-not-duplicated',async()=>{if(duplicated.length){const chosen=duplicated[0].name;await user.page.getByLabel('搜索或输入技能').fill(chosen);const names=await user.page.getByRole('list',{name:'技能建议',exact:true}).getByRole('button').allTextContents();assert.equal(new Set(names.map(norm)).size,names.length,'Visible suggestions should not repeat normalized names');await user.page.getByLabel('搜索或输入技能').fill('');}else assert.equal(duplicated.length,0);});
 await check('narrow-profile-with-expanded-dictionary',async()=>{await user.page.setViewportSize({width:390,height:900});await user.page.getByLabel('搜索或输入技能').fill('workplace');await user.page.getByRole('list',{name:'技能建议',exact:true}).waitFor();const geometry=await user.page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));await user.page.screenshot({path:path.join(out,'skill-picker-390.png'),fullPage:true});assert(geometry.scroll<=geometry.width,JSON.stringify(geometry));});
}finally{await browser.close();await new Promise(r=>server.close(r));await save('frontend-results.json',{results,source_sha:'8569b72ac1d965c252a741f3e62ed71b01f630e7'});}
console.log(JSON.stringify({total:results.length,passed:results.filter(x=>x.outcome==='passed').length,failed:results.filter(x=>x.outcome==='failed').length,dictionary_entries:suggestions.length,duplicate_normalized_names:duplicated.length}));process.exitCode=results.some(x=>x.outcome==='failed')?1:0;
