/** Presentation checks using real read-only product API receipts. No writes/models. */
const fs=require('node:fs'),path=require('node:path'),{createRequire}=require('node:module');
const {chromium}=createRequire(path.resolve(__dirname,'../../apps/workbench/frontend/package.json'))('playwright');
const args=process.argv.slice(2),opt=n=>args[args.indexOf(n)+1];
const live=args.includes('--live');
const responses=live?null:JSON.parse(fs.readFileSync(opt('--responses'),'utf8')),out=path.resolve(opt('--output'));
fs.mkdirSync(out);
(async()=>{const browser=await chromium.launch({headless:true});const results=[];
try{for(const width of [1440,2160,390]){
 const page=await browser.newPage({viewport:{width,height:1000}});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
 if(!live) await page.route('**/api/v1/data-library/**',async route=>{
  const u=new URL(route.request().url());let key=decodeURIComponent(u.pathname);
  if(key.endsWith('/sources')&&u.searchParams.get('ticker')==='MSFT')key+='?ticker=MSFT&year=2024';
  if(key.endsWith('/financials')&&u.searchParams.get('ticker')==='MSFT')key+='?ticker=MSFT&fiscal_year=2025&query=现金流';
  if(!responses[key])throw Error('Unqualified API fixture '+key);
  await route.fulfill({json:responses[key]});
 });
 await page.goto('http://127.0.0.1:18795/workspace/session?view=library');
 await page.getByRole('heading',{name:'公司资料库',exact:true}).waitFor();
 await page.locator('.dl-card').first().waitFor();
 await page.locator('.dl-page').evaluate(e=>Promise.all(e.getAnimations({subtree:true}).map(a=>a.finished)));
 await page.screenshot({path:path.join(out,`library-${width}.png`)});
 await page.getByLabel('公司',{exact:true}).selectOption('MSFT');await page.getByLabel('报告期结束年份',{exact:true}).selectOption('2024');
 await page.locator('.dl-card').first().click();await page.locator('.dl-reading section').first().waitFor();
 await page.locator('.dl-reading').evaluate(e=>e.scrollTop=500);
 if(!(await page.locator('.dl-reading').evaluate(e=>e.scrollTop>0)))throw Error('Reader scroll unavailable');
 await page.screenshot({path:path.join(out,`reader-${width}.png`)});
 await page.keyboard.press('Escape');await page.getByLabel('公共资料阅读',{exact:true}).waitFor({state:'detached'});
 await page.getByRole('button',{name:'查询财务数据',exact:true}).click();await page.locator('.dl-table tbody tr').first().waitFor();
 await page.screenshot({path:path.join(out,`financials-${width}.png`)});
 if(!(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)))throw Error('Page overflow');
 await page.goto('http://127.0.0.1:18795/workspace/session?thread=01a08f2e-422f-7b32-94a7-a799775216dd&view=graph');
 await page.locator('.fs-outline-grid .fs-node-card').first().waitFor();
 if(live) await page.locator('.fs-task-link').first().waitFor({state:'attached',timeout:60000});
 const cards=await page.locator('.fs-outline-grid .fs-node-card').evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width}}));
 if(width>=1440&&cards[0].y!==cards[1].y)throw Error('Desktop map not using multiple columns');
 await page.screenshot({path:path.join(out,`map-${width}.png`)});
 if(errors.length)throw Error(errors.join('\n'));
 results.push({width,cards:cards.length,reader_scroll:true,page_overflow:false,api_mode:live?'deployed API without interception':'frozen real API receipt, not deployed data API'});await page.close();
 }
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({results,model_calls:0},null,2));console.log(JSON.stringify(results));
}catch(e){console.error(e);fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({error:String(e)}));process.exitCode=1;}finally{await browser.close();}})();
