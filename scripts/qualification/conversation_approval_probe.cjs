/** Resume one existing knowledge approval in the real UI; never resubmit a prompt. */
const fs=require('node:fs'),path=require('node:path');
const {createRequire}=require('node:module');
const {chromium}=createRequire(path.resolve(__dirname,'../../apps/workbench/frontend/package.json'))('playwright');
const args=process.argv.slice(2), option=name=>args[args.indexOf(name)+1];
if(!args.includes('--execute') || !args.includes('--case') || !args.includes('--output'))throw Error('Explicit --execute --case --output required; resume can incur model usage');
const spec=JSON.parse(fs.readFileSync(option('--case'),'utf8')),output=path.resolve(option('--output'));
if(!/^[0-9a-f-]{36}$/.test(spec.thread_id) || !['approve','reject'].includes(spec.decision) || !Array.isArray(spec.source_ids))throw Error('A single thread, decision and exact source IDs are required');
const base=new URL(option('--base-url'));if(base.hostname!=='127.0.0.1')throw Error('Loopback only');
fs.mkdirSync(output);fs.writeFileSync(path.join(output,'case.json'),JSON.stringify(spec,null,2));
(async()=>{
  const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}});
  try{
    const route=`/api/v1/conversations/${spec.thread_id}`;
    const response=await page.request.get(new URL(route,base).href);if(!response.ok())throw Error('State read failed');
    const before=await response.json(),pending=before.approvals,actions=pending?.[0]?.value?.action_requests;
    if(before.status!=='interrupted' || pending?.length!==1 || actions?.length!==1 || actions[0].name!=='save_sources_to_knowledge' ||
      JSON.stringify([...actions[0].args.source_ids].sort())!==JSON.stringify([...spec.source_ids].sort()))throw Error('Pending action differs from explicit qualification; no mutation');
    if(spec.decision==='approve' && spec.source_ids.some(id=>!before.approval_sources?.[id]?.preview))throw Error('Original source preview missing; no approval');
    fs.writeFileSync(path.join(output,'before.json'),JSON.stringify(before,null,2));
    await page.goto(new URL(`/workspace/assistant?thread=${spec.thread_id}`,base).href);
    await page.getByRole('region',{name:'待批准的工具操作'}).waitFor();
    await page.getByRole('region',{name:'待批准的工具操作'}).scrollIntoViewIfNeeded();
    await page.screenshot({path:path.join(output,'before.png'),fullPage:true});
    const submitted=page.waitForResponse(r=>r.request().method()==='POST' && new URL(r.url()).pathname===route+'/approvals');
    await page.getByRole('button',{name:spec.decision==='approve'?'批准这些操作':'拒绝这些操作',exact:true}).click();
    const sent=await submitted,identity=await sent.json();
    fs.writeFileSync(path.join(output,'submission.json'),JSON.stringify({status:sent.status(),...identity},null,2));
    if(!sent.ok())throw Error('Resume failed; no retry');
    const start=Date.now();let state;
    while(Date.now()-start<240000){
      const current=await page.request.get(new URL(route,base).href);if(!current.ok())throw Error('State read failed; submitted identity retained');
      state=await current.json();const run=state.runs.find(r=>r.run_id===identity.run_id);
      if(run && !['pending','running'].includes(run.status))break;
      await page.waitForTimeout(1500);
    }
    fs.writeFileSync(path.join(output,'after.json'),JSON.stringify(state,null,2));
    await page.reload();await page.getByLabel('发送消息',{exact:true}).waitFor();
    await page.screenshot({path:path.join(output,'after.png'),fullPage:true});
    if(state.runs.find(r=>r.run_id===identity.run_id)?.status!=='success' || state.approvals?.length)throw Error('Resume did not complete; inspect retained state');
    console.log(JSON.stringify({status:'resumed_pending_content_review',...identity}));
  }catch(e){fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:String(e)}));process.exitCode=1;console.error(String(e));}
  finally{await browser.close();}
})();
