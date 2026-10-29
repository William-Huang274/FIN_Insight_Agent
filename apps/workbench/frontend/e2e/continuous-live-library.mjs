// Real browser + business services; no route interception or model API.
import {chromium,expect as baseExpect} from 'playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const expect=baseExpect.configure({timeout:60000});
const origin=process.env.FIN_DELIVERY_BROWSER_ORIGIN, endpoint=new URL(origin);
if(process.env.FIN_CONTINUOUS_LIBRARY_QUALIFICATION!=='1'||endpoint.hostname!=='127.0.0.1'||['18165','18765'].includes(endpoint.port))throw Error('isolated_browser_required');
const project=process.env.FIN_DELIVERY_PROJECT, mode=process.env.FIN_DELIVERY_BROWSER_MODE;
const output=resolve(process.env.FIN_DELIVERY_BROWSER_OUTPUT);
await mkdir(output,{recursive:false});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({baseURL:origin,viewport:{width:1440,height:1000},
 extraHTTPHeaders:{Authorization:'Bearer qualification-alice','X-Workbench-Request':'1'}});
const page=await context.newPage(),requests=[],responses=[],errors=[];
let execution=process.env.FIN_DELIVERY_EXECUTION;
page.on('request',r=>{const u=new URL(r.url());if(u.pathname.startsWith('/api/'))requests.push({method:r.method(),path:u.pathname});});
page.on('response',async r=>{const u=new URL(r.url());if(u.pathname.startsWith('/api/')){
 const row={status:r.status(),path:u.pathname};responses.push(row);
 if(r.status()>=400)row.error=await r.text().catch(()=>'<body unavailable>');
}});
page.on('pageerror',e=>errors.push(String(e)));
async function refreshUntil(locator){
 const deadline=Date.now()+45*60*1000;
 for(let i=0;Date.now()<deadline;i++){
  await expect(page.getByText('正在读取研究记录…',{exact:true})).not.toBeVisible();
  if(await locator.isVisible())return;
  if(await page.getByText('运行异常，请核对原记录',{exact:true}).isVisible())throw Error('native_run_failed');
  await new Promise(r=>setTimeout(r,4000));
  if(i%5===0){
   let reconciled=false;
   for(const name of ['核对首次启动结果','核对原任务操作']){
    const reconcile=page.getByRole('button',{name,exact:true});
    if(await reconcile.isVisible()&&await reconcile.isEnabled()){
     await Promise.all([page.waitForResponse(r=>r.request().method()==='POST'&&r.url().includes('/reconcile')),
       reconcile.click()]);
     // Let the action finish and its own onChanged refresh settle. Refreshing
     // the parent immediately unmounts the handler before it clears pending ID.
     await expect(page.getByText('正在读取研究记录…',{exact:true})).not.toBeVisible();
     await new Promise(r=>setTimeout(r,250));reconciled=true;
    }
   }
   const status=page.getByRole('button',{name:'核对操作状态',exact:true});
   if(!reconciled&&await status.isVisible()&&await status.isEnabled())await status.click();
  }
  if(i%5!==0){
   await page.getByRole('button',{name:'刷新研究记录',exact:true}).click();
   await expect(page.getByText('正在读取研究记录…',{exact:true})).not.toBeVisible();
  }
 }
 await expect(locator).toBeVisible();
}
async function follow(message,kind){
 await refreshUntil(page.getByRole('textbox',{name:'继续提问或交代下一步'}));
 // End the polling/reconcile page lifecycle before editing. A late control
 // refresh can otherwise replace the form just filled by this driver.
 await page.reload();
 await expect(page.getByRole('textbox',{name:'继续提问或交代下一步'})).toBeEnabled();
 await page.getByLabel('这一步的成果',{exact:true}).selectOption(kind);
 await page.getByRole('textbox',{name:'继续提问或交代下一步'}).fill(message);
 await expect(page.getByRole('textbox',{name:'继续提问或交代下一步'})).toHaveValue(message);
 await page.getByRole('button',{name:'准备继续任务',exact:true}).click();
 await page.getByRole('button',{name:'确认继续任务',exact:true}).click();
}
try{
 if(mode==='prepare'){
  await page.goto(`/workspace/projects?scope=organization&project=${project}&view=research`);
  await page.getByLabel('准备单标题',{exact:true}).fill('冻结资料连续工作验证');
  await page.getByRole('textbox',{name:'研究问题',exact:true}).fill('Read the frozen authorized original for engineering qualification. No financial conclusion.');
  await page.getByLabel('研究截止日期',{exact:true}).fill('2026-09-23');
  await page.getByRole('checkbox').first().check();
  await page.getByLabel('检索版本',{exact:true}).selectOption(process.env.FIN_DELIVERY_RELEASE);
  await page.getByRole('button',{name:'保存输入准备单',exact:true}).click();
  await expect(page.getByLabel('希望得到的成果',{exact:true})).toBeVisible();
  await page.getByLabel('希望得到的成果',{exact:true}).selectOption('answer');
  await page.getByRole('button',{name:'准备研究执行',exact:true}).click();
  // A cold full-library validation can outlive the HTTP receipt. Use the
  // product's original-command reconciliation, never create another task.
  for(let i=0;i<100&&!await page.getByRole('button',{name:'开始任务',exact:true}).isVisible();i++){
   await new Promise(r=>setTimeout(r,3000));
   const open=page.getByRole('button',{name:'查看已有研究执行 →',exact:true});
   const reconcile=page.getByRole('button',{name:'核对原准备结果',exact:true});
   if(await open.isVisible())await open.click();
   else if(await reconcile.isVisible()&&await reconcile.isEnabled())await reconcile.click();
   else{
    const read=page.getByRole('button',{name:'读取已有执行',exact:true});
    if(await read.isVisible()&&await read.isEnabled())await read.click();
   }
  }
  await expect(page.getByRole('button',{name:'开始任务',exact:true})).toBeVisible();
  execution=new URL(page.url()).searchParams.get('execution');
 }else{
  await page.goto(`/workspace/projects?scope=organization&project=${project}&view=results&execution=${execution}`);
  if(mode==='run'){
  await page.getByRole('button',{name:'开始任务',exact:true}).click();
  await refreshUntil(page.getByText('工程验证：已通过冻结索引检索并读取准确原文，未作金融判断。',{exact:true}));
  await page.screenshot({path:resolve(output,'answer.png'),fullPage:true});
  }
  if(mode==='run'||mode==='workpaper'){
  await follow('Please save a working paper from the same evidence.','workpaper');
  await refreshUntil(page.getByRole('button',{name:'读取已提交底稿',exact:true}));
  await page.getByRole('button',{name:'读取已提交底稿',exact:true}).click();
  await expect(page.getByText('Engineering fixture only. The same authorized original and prior answer remain available.',{exact:true})).toBeVisible();
  await page.screenshot({path:resolve(output,'workpaper.png'),fullPage:true});
  }
  await follow('Please compose a report using the original already read. Label it as engineering qualification.','report');
  await refreshUntil(page.getByRole('heading',{name:'冻结资料服务验证报告',exact:true}));
  await page.reload();
  await expect(page.getByRole('heading',{name:'冻结资料服务验证报告',exact:true})).toBeVisible();
  await page.getByRole('button',{name:/^查看引用 /}).first().click();
  await expect(page.getByRole('region',{name:'引用快照内容'})).toBeVisible();
  for(const [format,label] of [['html','网页阅读版'],['md','Markdown'],['pdf','PDF'],['docx','Word'],['pptx','PowerPoint']]){
   const pending=page.waitForEvent('download');await page.getByRole('button',{name:label,exact:true}).click();
   const file=await pending;expect(await file.failure()).toBeNull();await file.saveAs(resolve(output,'report.'+format));
  }
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:960});
   expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
   await page.screenshot({path:resolve(output,`report-${width}.png`),fullPage:true});
  }
  const offline=await browser.newContext();await offline.setOffline(true);
  const reader=await offline.newPage(),external=[];
  reader.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url());});
  await reader.goto(pathToFileURL(resolve(output,'report.html')).href);
  await expect(reader.locator('article')).toContainText('本报告仅用于实际服务');
  await expect(reader.locator('#sources details')).not.toHaveCount(0);
  const missing=await reader.locator('a[href^="#"]').evaluateAll(links=>links.map(a=>a.getAttribute('href').slice(1)).filter(id=>!document.getElementById(id)));
  for(const width of [1440,390]){
   await reader.setViewportSize({width,height:960});
   expect(await reader.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
   await reader.screenshot({path:resolve(output,`offline-${width}.png`),fullPage:true});
  }
  expect(missing).toEqual([]);expect(external).toEqual([]);await offline.close();
 }
 expect(errors).toEqual([]);
 await writeFile(resolve(output,'result.json'),JSON.stringify({execution,mode,requests,responses,page_errors:errors,api_interceptions:0},null,2));
}finally{
 await writeFile(resolve(output,'observations.json'),JSON.stringify({execution,requests,responses,page_errors:errors},null,2));
 await page.screenshot({path:resolve(output,'last-page.png'),fullPage:true}).catch(()=>{});
 await browser.close();
}
