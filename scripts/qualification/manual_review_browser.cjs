/** Apply an explicitly prepared editorial decision through the real local UI. */
const fs=require('node:fs'),path=require('node:path'),{createRequire}=require('node:module');
const {chromium}=createRequire(path.resolve(__dirname,'../../apps/workbench/frontend/package.json'))('playwright');
const args=process.argv.slice(2),opt=n=>args[args.indexOf(n)+1];
const tid=opt('--thread'),file=path.resolve(opt('--decision')),out=path.resolve(opt('--output'));
if(!/^[0-9a-f-]{36}$/.test(tid))throw Error('Explicit thread required');
const d=JSON.parse(fs.readFileSync(file,'utf8'));if(!d.confirmed)throw Error('Prepared confirmation required');
fs.mkdirSync(out);
(async()=>{const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});
try{
 const base='http://127.0.0.1:18795';
 await page.goto(`${base}/workspace/session?thread=${tid}&view=report`);
 if(!args.includes('--verify-only')){
 await page.getByRole('button',{name:'人工修改与确认',exact:true}).click();
 const dlg=page.getByRole('dialog',{name:'人工修改与确认'});
 const response=await page.request.get(`${base}/api/v1/research-sessions/${tid}/manual-review`);
 const editor=await response.json();if(!response.ok()||editor.base_version!==d.base_version)throw Error('Stale report');
 for(const p of d.paper_edits||[]){const area=dlg.getByLabel(`修改底稿 ${p.paper_id}`,{exact:true});await area.locator('..').locator('summary').click();await area.fill(p.body);}
 await dlg.getByLabel('人工修改报告正文',{exact:true}).fill(d.report_markdown);
 for(const c of d.chart_edits||[])await dlg.getByLabel(`修改图表说明 ${c.chart_index+1}`,{exact:true}).fill(c.interpretation);
 await dlg.getByLabel('人工修改说明',{exact:true}).fill(d.reason);await dlg.getByRole('checkbox').check();
 const pending=page.waitForResponse(r=>r.url().endsWith(`/${tid}/actions`)&&r.request().method()==='POST');
 await dlg.getByRole('button',{name:'保存修改并确认完成',exact:true}).click();
 const saved=await pending;const action=await saved.json();
 fs.writeFileSync(path.join(out,'action.json'),JSON.stringify(action,null,2));
 if(!saved.ok())throw Error(`Save rejected: ${saved.status()}`);
 await dlg.waitFor({state:'hidden'});
 }
 let state;
 for(let i=0;i<20;i++){
  state=await (await page.request.get(`${base}/api/v1/research-sessions/${tid}`)).json();
  if(state.phase==='human_completed'&&state.report_version===d.base_version+1)break;
  await page.waitForTimeout(500);
 }
 if(state.phase!=='human_completed'||state.report_version!==d.base_version+1)throw Error('Completion not committed');
 fs.writeFileSync(path.join(out,'state.json'),JSON.stringify(state,null,2));
 await page.reload();
 const memory=page.getByRole('button',{name:'保存到个人研究记忆',exact:true});
 const remembered=page.waitForResponse(r=>r.url().endsWith(`/${tid}/remember`)&&r.request().method()==='POST');
 await memory.click();const mr=await remembered;if(!mr.ok())throw Error('Research memory save failed');
 fs.writeFileSync(path.join(out,'memory.json'),JSON.stringify(await mr.json(),null,2));
 await page.screenshot({path:path.join(out,'completed.png')});
 console.log(JSON.stringify({phase:state.phase,report_version:state.report_version,human_edit_count:state.human_edit_count,model_calls:0}));
}catch(e){fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e)}));process.exitCode=1;console.error(String(e));}finally{await browser.close();}})();
