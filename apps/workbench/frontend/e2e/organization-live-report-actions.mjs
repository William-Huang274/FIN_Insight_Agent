// Real BFF/Java/native requests, static output producers, no route interception.
import {chromium,expect} from 'playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const origin=process.env.FIN_DELIVERY_BROWSER_ORIGIN,endpoint=new URL(origin);
if(process.env.FIN_ORGANIZATION_REPORT_ACTIONS_QUALIFICATION!=='1'||endpoint.hostname!=='127.0.0.1'||['18165','18765'].includes(endpoint.port))throw Error('isolated_browser_required');
const output=resolve(process.env.FIN_DELIVERY_BROWSER_OUTPUT),project=process.env.FIN_DELIVERY_PROJECT,execution=process.env.FIN_DELIVERY_EXECUTION;
await mkdir(output,{recursive:false});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({baseURL:origin,viewport:{width:1440,height:1000},
  extraHTTPHeaders:{Authorization:'Bearer qualification-alice','X-Workbench-Request':'1'}});
const page=await context.newPage(),requests=[],failures=[];
page.on('request',r=>{const p=new URL(r.url()).pathname;if(p.startsWith('/api/'))requests.push({method:r.method(),path:p});});
page.on('pageerror',e=>failures.push(String(e)));
async function refreshUntil(locator){
  for(let i=0;i<75;i++){
    if(await locator.isVisible())return;
    if(await page.getByText('运行异常，请核对原记录',{exact:true}).isVisible())throw Error('native_action_failed');
    await new Promise(r=>setTimeout(r,800));
    await page.getByRole('button',{name:'刷新研究记录',exact:true}).click();
  }
  await expect(locator).toBeVisible();
}
try{
  await page.goto(`/workspace/projects?scope=organization&project=${project}&view=results&execution=${execution}`);
  for(const [action,message] of [['追问','First static question'],['追问','Second static question'],['修订','Static explicit revision'],['追问','Static lost action']]){
    const area=page.getByRole('region',{name:'报告追问与修订'});
    if(action==='修订'){
      await area.getByRole('button',{name:'提出修订',exact:true}).click();
      await area.getByRole('combobox',{name:'修订关注范围'}).selectOption('C1');
    }
    else await area.getByRole('button',{name:'追问解释',exact:true}).click();
    await area.getByRole('textbox',{name:'问题或修订意见'}).fill(message);
    await area.getByRole('button',{name:`核对并准备${action}`,exact:true}).click();
    await expect(area.getByRole('button',{name:`确认提交${action}`,exact:true})).toBeVisible();
    await area.getByRole('button',{name:`确认提交${action}`,exact:true}).click();
    if(message==='Static lost action'){
      await refreshUntil(page.getByRole('button',{name:'核对报告操作',exact:true}));
      await page.reload();
      await page.getByRole('button',{name:'核对报告操作',exact:true}).click();
    }
    await refreshUntil(action==='追问'
      ? page.getByRole('region',{name:'报告交流记录'}).getByText('Static answer: '+message,{exact:true})
      : page.getByText('Static explicit revision; not a financial conclusion.',{exact:true}));
    await page.reload();
    await expect(page.getByRole('region',{name:'报告交流记录'}).getByText(message,{exact:true})).toBeVisible();
  }
  for(const width of [1440,390]){
    await page.setViewportSize({width,height:1000});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
    await page.screenshot({path:resolve(output,`report-actions-${width}.png`),fullPage:true});
  }
  expect(requests.filter(r=>r.method==='POST'&&r.path.endsWith('/report-commands'))).toHaveLength(4);
  expect(failures).toEqual([]);
  await writeFile(resolve(output,'result.json'),JSON.stringify({requests,page_errors:failures,api_interceptions:0,actions:4},null,2));
}finally{
  await writeFile(resolve(output,'observations.json'),JSON.stringify({requests,page_errors:failures},null,2));
  await page.screenshot({path:resolve(output,'last-page.png'),fullPage:true}).catch(()=>{});
  await browser.close();
}
