// Invoked only by the isolated Python qualification. No API response interception.
import {chromium,expect} from 'playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const origin=process.env.FIN_DELIVERY_BROWSER_ORIGIN;
const endpoint=new URL(origin);
if(process.env.FIN_ORGANIZATION_DELIVERY_QUALIFICATION!=='1'||endpoint.hostname!=='127.0.0.1'||['18165','18765'].includes(endpoint.port))throw Error('isolated_browser_required');
const project=process.env.FIN_DELIVERY_PROJECT,output=resolve(process.env.FIN_DELIVERY_BROWSER_OUTPUT);
const mode=process.env.FIN_DELIVERY_BROWSER_MODE||'create';
await mkdir(output,{recursive:false});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({baseURL:origin,viewport:{width:1440,height:1000},
  extraHTTPHeaders:{Authorization:'Bearer '+(mode==='viewer'?'qualification-viewer':'qualification-alice'),'X-Workbench-Request':'1'}});
const page=await context.newPage(),requests=[],responses=[],failures=[];
const expected=process.env.FIN_DELIVERY_EXPECTED_TEXT||'Synthetic pinned organization evidence.';
page.on('request',request=>{const u=new URL(request.url());if(u.pathname.startsWith('/api/'))requests.push({method:request.method(),path:u.pathname});});
page.on('response',response=>{const u=new URL(response.url());if(u.pathname.startsWith('/api/'))responses.push({status:response.status(),path:u.pathname});});
page.on('pageerror',e=>failures.push(String(e)));
let execution=process.env.FIN_DELIVERY_EXECUTION,draft;
async function refreshUntil(locator){
  for(let i=0;i<90;i++){
    if(await locator.isVisible())return;
    if(await page.getByText('运行异常，请核对原记录',{exact:true}).isVisible())throw Error('native_run_failed; inspect retained native logs');
    await new Promise(r=>setTimeout(r,1000));
    await page.getByRole('button',{name:'刷新研究记录',exact:true}).click();
  }
  await expect(locator).toBeVisible();
}
try{
  if(mode==='create'){
    await page.goto(`/workspace/projects?scope=organization&project=${project}&view=research`);
    await page.getByLabel('准备单标题',{exact:true}).fill(process.env.FIN_DELIVERY_TITLE||'Static browser delivery');
    await page.getByRole('textbox',{name:'研究问题',exact:true}).fill(process.env.FIN_DELIVERY_QUESTION||'Read the fixed original for a static business delivery qualification only.');
    await page.getByLabel('研究截止日期',{exact:true}).fill(process.env.FIN_DELIVERY_AS_OF||'2026-10-19');
    if(process.env.FIN_DELIVERY_SOURCE_TITLES){
      for(const title of JSON.parse(process.env.FIN_DELIVERY_SOURCE_TITLES))await page.getByRole('checkbox',{name:title,exact:false}).check();
    }else await page.getByRole('checkbox').check();
    await page.getByRole('button',{name:'保存输入准备单',exact:true}).click();
    await expect(page.getByRole('button',{name:'准备研究执行',exact:true})).toBeEnabled();
    draft=new URL(page.url()).searchParams.get('draft');
    await page.getByRole('button',{name:'准备研究执行',exact:true}).click();
    if(process.env.FIN_DELIVERY_TITLE==='Synthetic lost organization reply'){
      await expect(page.getByRole('button',{name:'核对原准备结果',exact:true})).toBeVisible();
      await page.reload();await page.getByRole('button',{name:'核对原准备结果',exact:true}).click();
    }
    await expect(page.getByRole('button',{name:'开始预研究',exact:true})).toBeEnabled();
    execution=new URL(page.url()).searchParams.get('execution');
    await page.getByRole('button',{name:'开始预研究',exact:true}).click();
    if(process.env.FIN_DELIVERY_TITLE==='Synthetic lost organization reply'){
      // Worker admission can change the read grant during a snapshot: the BFF
      // correctly returns 409. Explicit refresh recovers controls, never writes.
      await refreshUntil(page.getByRole('button',{name:'核对首次启动结果',exact:true}));
      await page.reload();await refreshUntil(page.getByRole('button',{name:'核对首次启动结果',exact:true}));
      await page.getByRole('button',{name:'核对首次启动结果',exact:true}).click();
    }
    await refreshUntil(page.getByRole('button',{name:'准备正式研究',exact:true}));
    await page.reload();await page.getByRole('button',{name:'准备正式研究',exact:true}).click();
    await page.getByRole('button',{name:'暂不开始',exact:true}).click();
    await page.getByRole('button',{name:'准备正式研究',exact:true}).click();
    await page.getByRole('button',{name:'确认接续研究',exact:true}).click();
    if(process.env.FIN_DELIVERY_TITLE==='Synthetic lost organization reply'){
      await refreshUntil(page.getByRole('button',{name:'核对正式研究结果',exact:true}));
      await page.reload();await refreshUntil(page.getByRole('button',{name:'核对正式研究结果',exact:true}));
      await page.getByRole('button',{name:'核对正式研究结果',exact:true}).click();
    }
    await refreshUntil(page.getByRole('heading',{name:'Static business delivery report',exact:true}));
  }else await page.goto(`/workspace/projects?scope=organization&project=${project}&view=results&execution=${execution}`);
  if(mode==='denied'){
    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.getByRole('heading',{name:'Static business delivery report',exact:true})).toHaveCount(0);
  }else{
    await page.reload();await expect(page.getByRole('heading',{name:'Static business delivery report',exact:true})).toBeVisible();
    await page.getByRole('button',{name:/^查看引用 /}).first().click();
    await expect(page.getByRole('region',{name:'引用快照内容'})).toContainText(expected);
    for(const [format,label] of [['html','网页阅读版'],['md','Markdown'],['pdf','PDF'],['docx','Word'],['pptx','PowerPoint']]){
      const pending=page.waitForEvent('download');await page.getByRole('button',{name:label,exact:true}).click();
      const file=await pending;expect(await file.failure()).toBeNull();
      await file.saveAs(resolve(output,'report.'+format));
    }
    // Open the actual authorized download offline, without API mocks or auth
    // headers. The file must remain readable at desktop and phone widths.
    const offline=await browser.newContext();
    try{
      await offline.setOffline(true);
      const reader=await offline.newPage(),external=[];
      reader.on('request',r=>{if(/^https?:/.test(r.url()))external.push(r.url());});
      await reader.goto(pathToFileURL(resolve(output,'report.html')).href);
      await expect(reader.locator('article')).toContainText(expected);
      await expect(reader.locator('#sources details')).not.toHaveCount(0);
      for(const width of [1440,390]){
        await reader.setViewportSize({width,height:960});
        await reader.screenshot({path:resolve(output,`reader-${width}.png`),fullPage:true});
        expect(await reader.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
      }
      const missing=await reader.locator('a[href^="#"]').evaluateAll(links=>
        links.map(a=>a.getAttribute('href').slice(1)).filter(id=>!document.getElementById(id)));
      await reader.locator('sup.cite a').first().click();
      const excerpt=reader.locator('#sources details').first();
      await excerpt.locator('summary').click();
      await expect(excerpt).toHaveAttribute('open','');
      await expect(excerpt.locator('.quote')).toContainText(expected);
      expect(missing).toEqual([]);expect(external).toEqual([]);
      await writeFile(resolve(output,'reader-checks.json'),JSON.stringify({external_requests:external,missing_anchors:missing,widths:[1440,390],offline:true}));
    }finally{await offline.close();}
    if(mode==='viewer')await expect(page.getByRole('button',{name:/^开始预研究$|^确认接续研究$/})).toHaveCount(0);
  }
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  if(mode!=='create')expect(requests.filter(r=>r.method!=='GET')).toEqual([]);
  expect(failures).toEqual([]);
  await page.screenshot({path:resolve(output,'page.png'),fullPage:true});
  await writeFile(resolve(output,'result.json'),JSON.stringify({mode,execution,draft,requests,responses,page_errors:failures,api_interceptions:0},null,2));
}finally{
  await writeFile(resolve(output,'observations.json'),JSON.stringify({execution,draft,requests,responses,page_errors:failures},null,2));
  await page.screenshot({path:resolve(output,'last-page.png'),fullPage:true}).catch(()=>{});
  await browser.close();
}
