/** Read-only real UI export of a saved final answer; no model call. */
const fs=require('node:fs'),path=require('node:path');
const {createRequire}=require('node:module');
const {chromium}=createRequire(path.resolve(__dirname,'../../apps/workbench/frontend/package.json'))('playwright');
const args=process.argv.slice(2),opt=name=>args[args.indexOf(name)+1];
if(!args.includes('--thread') || !args.includes('--output') || !args.includes('--base-url'))throw Error('Explicit loopback URL, thread and new output directory required');
const tid=opt('--thread'),base=new URL(opt('--base-url')),output=path.resolve(opt('--output'));
if(!/^[0-9a-f-]{36}$/.test(tid) || base.hostname!=='127.0.0.1')throw Error('Invalid qualification scope');
fs.mkdirSync(output);
(async()=>{
 const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}});
 try{
  await page.goto(new URL(`/workspace/assistant?thread=${tid}`,base).href);
  const answerIndex=args.includes('--answer-index')?Number(opt('--answer-index')):-1;
  if(!Number.isInteger(answerIndex)||answerIndex < -1)throw Error('Invalid answer index');
  const nav=page.getByRole('navigation',{name:'导出这条回答'}).nth(answerIndex);await nav.waitFor();await nav.scrollIntoViewIfNeeded();
  await page.screenshot({path:path.join(output,'answer.png'),fullPage:true});
  const receipts=[];
  for(const [label,ext] of [['MD','md'],['PDF','pdf'],['Word','docx']]){
   const link=nav.getByRole('link',{name:label,exact:true}),href=await link.getAttribute('href');
   const pending=page.waitForEvent('download');await link.click();const download=await pending;
   await download.saveAs(path.join(output,`answer.${ext}`));if(await download.failure())throw Error('Download failed');
   receipts.push({format:ext,href,bytes:fs.statSync(path.join(output,`answer.${ext}`)).size});
  }
  fs.writeFileSync(path.join(output,'exports.json'),JSON.stringify(receipts,null,2));console.log(JSON.stringify(receipts));
 }catch(e){fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:String(e)}));process.exitCode=1;console.error(String(e));}
 finally{await browser.close();}
})();
