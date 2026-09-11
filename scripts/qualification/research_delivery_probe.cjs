/** Read-only real report downloads and role/paper history, no model calls. */
const fs=require('node:fs'),path=require('node:path'),{createRequire}=require('node:module');
const {chromium}=createRequire(path.resolve(__dirname,'../../apps/workbench/frontend/package.json'))('playwright');
const args=process.argv.slice(2),opt=n=>args[args.indexOf(n)+1];
const tid=opt('--thread'),out=path.resolve(opt('--output'));
if(!/^[0-9a-f-]{36}$/.test(tid))throw Error('Explicit thread required');
fs.mkdirSync(out);
(async()=>{const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1000}});
try{
 const base='http://127.0.0.1:18795';
 const response=await page.request.get(`${base}/api/v1/research-sessions/${tid}`);if(!response.ok())throw Error('Report unreadable');
 const state=await response.json();if(!state.report)throw Error('No saved report');
 await page.goto(`${base}/workspace/session?thread=${tid}&view=report`);
 const actions=page.locator('.rs-export-actions').filter({hasText:'导出这版报告'});await actions.waitFor();
 await page.getByText('正在读取版本…',{exact:true}).waitFor({state:'hidden'});
 await page.screenshot({path:path.join(out,'report.png'),fullPage:false});
 const exports=[];
 for(const [label,ext] of [['Markdown','md'],['PDF','pdf'],['Word','docx']]){
  const link=actions.getByRole('link',{name:label,exact:true});
  const pending=page.waitForEvent('download');await link.click();const d=await pending;
  await d.saveAs(path.join(out,`report.${ext}`));if(await d.failure())throw Error('Download failed');
  exports.push({format:ext,bytes:fs.statSync(path.join(out,`report.${ext}`)).size});
 }
 const history=page.locator('.fs-human-history');let roles=[];
 if(state.human_edit_count){
  await history.locator(':scope > summary').click();
  const paper=history.locator('section > details').first();await paper.locator(':scope > summary').click();
  roles=await history.locator('summary').allTextContents();
  const heading=page.locator('.rs-heading'),box=await heading.boundingBox();
  await page.mouse.move(box.x+box.width*.7,box.y+box.height-30);await page.mouse.wheel(0,750);await page.waitForTimeout(300);
  if(!(await heading.evaluate(e=>e.scrollTop>0)))throw Error('Expanded history cannot scroll');
  await page.screenshot({path:path.join(out,'role-paper-history.png'),fullPage:false});
 }
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({thread_id:tid,phase:state.phase,report_version:state.report_version,human_edit_count:state.human_edit_count,charts:state.report.charts?.length||0,exports,roles,model_calls:0},null,2));
 console.log(JSON.stringify({report_version:state.report_version,human_edit_count:state.human_edit_count,exports}));
}catch(e){fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e)}));process.exitCode=1;console.error(String(e));}finally{await browser.close();}})();
