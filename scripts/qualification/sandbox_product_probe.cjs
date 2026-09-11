/** Four bounded real-UI sandbox checks. Explicit execution, no paid retries. */
const fs=require('node:fs'),path=require('node:path'),{execFileSync}=require('node:child_process');
const {createRequire}=require('node:module');
const {chromium}=createRequire(path.resolve(__dirname,'../../apps/workbench/frontend/package.json'))('playwright');
const args=process.argv.slice(2),opt=n=>args[args.indexOf(n)+1];
if(!args.includes('--execute')||!args.includes('--output'))throw Error('Explicit --execute --output required; real provider calls');
const output=path.resolve(opt('--output')),base='http://127.0.0.1:18795';
fs.mkdirSync(output);
const code='print("FINSIGHT_SANDBOX_OK", 6 * 7)';
const cases=[['request_standard','reject'],['request_standard','approve'],['approve_for_me',null],['full_access',null]];
fs.writeFileSync(path.join(output,'TokenBudgetBasis.json'),JSON.stringify({
 node_purpose:'Verify real frontend approval through native Agent Server, authenticated MCP and disposable Docker',
 input_scale:'Four fresh one-turn conversations, existing deployed tool catalog, fixed one-line Python',
 required_outputs:['Exactly one sandbox tool request per case','Reject produces no container','Approve/auto modes return 42 and isolation receipt'],
 schema_burden:'One code string tool call and short public answer; no financial report',
 materiality_quality_risk:'Execute only reviewed fixed print code; no file, network or research data operations',
 comparable_run_evidence:'Four scripted MCP approval checks passed, real deployment host/container authentication passed',
 reasoning_profile:'Deployed native conversation: deepseek-v4-flash, thinking disabled, low',
 stop_truncation_behavior:'Stop suite on first failure; no retries, retain run IDs; deployed per-run 8-call/3000-output limits unchanged',
 expected_model_requests:8, maximum_runs:6, model_calls_are_paid:true
},null,2));
const save=(name,data)=>fs.writeFileSync(path.join(output,name),JSON.stringify(data,null,2));
function events(thread,since){
 const text=execFileSync('docker',['events','--since',String(since),'--until',String(Math.floor(Date.now()/1000)+1),
   '--filter','type=container','--filter','label=org.finsight.thread='+thread,'--format','{{json .}}'],{encoding:'utf8',timeout:10000});
 return text.trim()?text.trim().split('\n').map(x=>JSON.parse(x)):[];
}
(async()=>{
 const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1440,height:1050}});
 const results=[];let current;
 async function state(thread){const r=await page.request.get(`${base}/api/v1/conversations/${thread}`);if(!r.ok())throw Error('State read failed');return r.json();}
 async function terminal(thread,run){
   const start=Date.now();while(Date.now()-start<180000){const s=await state(thread);const r=s.runs.find(x=>x.run_id===run);
     if(r&&!['pending','running'].includes(r.status))return s;await page.waitForTimeout(1200);}
   throw Error('Run timeout; identity saved; do not resubmit');
 }
 try{
  for(let i=0;i<cases.length;i++){
   const [mode,decision]=cases[i],prefix='case-'+(i+1);const since=Math.floor(Date.now()/1000)-1;
   await page.goto(base+'/workspace/assistant');
   await page.getByRole('combobox',{name:'模型',exact:true}).selectOption('deepseek-v4-flash');
   await page.getByRole('combobox',{name:'权限',exact:true}).selectOption(mode);
   await page.getByRole('combobox',{name:'执行方式',exact:true}).selectOption('native');
   await page.getByLabel('发送消息',{exact:true}).fill('这是产品隔离执行验收，不是金融任务。只调用一次 run_isolated_python，code 必须逐字为：'+code+'。不要调用其他工具，不写文件、不联网。如等待批准则等待；如拒绝则停止且不得重试。如成功只报告工具实际返回的结果。');
   const sent=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/v1/conversations');
   await page.getByRole('button',{name:'发送',exact:true}).click();const response=await sent;
   current=await response.json();save(prefix+'-submission.json',{status:response.status(),...current});
   if(!response.ok())throw Error('Submission failed; no retry');
   let snapshot=await terminal(current.thread_id,current.run_id);save(prefix+'-before.json',snapshot);
   if(decision){
    const actions=snapshot.approvals?.[0]?.value?.action_requests;
    if(snapshot.approvals?.length!==1||actions?.length!==1||actions[0].name!=='run_isolated_python'||actions[0].args.code!==code)
      throw Error('Pending operation not exactly the reviewed code; no approval');
    const before=events(current.thread_id,since);save(prefix+'-events-before.json',before);
    if(before.length)throw Error('Container activity occurred before approval');
    await page.reload();await page.getByRole('region',{name:'待批准的工具操作'}).waitFor();
    await page.screenshot({path:path.join(output,prefix+'-approval.png'),fullPage:true});
    const resumed=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/approvals'));
    await page.getByRole('button',{name:decision==='approve'?'批准这些操作':'拒绝这些操作',exact:true}).click();
    const resumedResponse=await resumed;current=await resumedResponse.json();save(prefix+'-resume.json',{status:resumedResponse.status(),...current});
    if(!resumedResponse.ok())throw Error('Resume failed; no retry');
    snapshot=await terminal(current.thread_id,current.run_id);
   }else if(snapshot.approvals?.length)throw Error('Unexpected approval for empty disposable work');
   save(prefix+'-after.json',snapshot);
   const nativeResponse=await page.request.get(`http://127.0.0.1:18165/threads/${current.thread_id}/state`);
   if(!nativeResponse.ok())throw Error('Native receipt unavailable');
   const native=await nativeResponse.json();save(prefix+'-native.json',native);
   const executionEvents=events(current.thread_id,since);save(prefix+'-events-after.json',executionEvents);
   const creates=executionEvents.filter(e=>e.Action==='create').length,destroys=executionEvents.filter(e=>e.Action==='destroy').length;
   if(creates!==(decision==='reject'?0:1)||destroys!==creates)throw Error('Unexpected container execution/cleanup count');
   const tools=(native.values?.messages||[]).filter(m=>m.type==='tool'&&m.name==='run_isolated_python');
   if(decision!=='reject'){
    const receipt=JSON.parse(tools.at(-1)?.content);
    if(receipt.exit_code!==0||receipt.output.trim()!=='FINSIGHT_SANDBOX_OK 42'||receipt.isolation.network!=='none'||
      receipt.isolation.readonly_root!==true||receipt.isolation.user!=='65534:65534'||receipt.isolation.bind_mounts.length)
      throw Error('Invalid output/isolation receipt');
   }
   if(snapshot.runs.find(r=>r.run_id===current.run_id)?.status!=='success')throw Error('Final run did not succeed');
   const answer=snapshot.messages.filter(m=>m.role==='assistant'&&m.final_answer).at(-1);
   if(!answer||(decision!=='reject'&&!answer.content.includes('42')))throw Error('No corresponding final answer');
   await page.reload();await page.getByLabel('发送消息',{exact:true}).waitFor();
   await page.waitForFunction(needle=>document.body.innerText.includes(needle),
      decision==='reject'?'工具调用被拒绝':'FINSIGHT_SANDBOX_OK 42');
   await page.screenshot({path:path.join(output,prefix+'-final.png'),fullPage:true});
   results.push({mode,decision,thread_id:current.thread_id,containers:creates,cleaned:destroys,passed:true,answer:answer.content});
   save('results.json',results);console.log(JSON.stringify(results.at(-1)));
  }
 }catch(e){save('failure.json',{error:String(e),current,results});console.error(String(e));process.exitCode=1;}
 finally{await browser.close();}
})();
