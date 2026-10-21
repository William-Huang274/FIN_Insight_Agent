// Real OIDC, page controls, Java ACLs and persistent native MCP. No intercepted API.
// Run publication, publish the exact index offline, then run acceptance.
import {chromium, expect} from 'playwright/test';
import {readFile, writeFile, mkdir, copyFile, access} from 'node:fs/promises';
import {randomUUID, createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
const root=process.env.FIN_NORMAL_DEPLOYMENT_ROOT, scenario=process.env.FIN_MULTISOURCE_CASE;
const phase=process.argv[2], origin=process.env.FINSIGHT_PUBLIC_ORIGIN;
if(!root||!scenario||origin!=='https://localhost:18866'||!['publication','acceptance'].includes(phase))
  throw Error('explicit_local_multisource_acceptance_required');
const load=async path=>JSON.parse(await readFile(path,'utf8'));
const save=(path,value)=>writeFile(path,JSON.stringify(value,null,2),{flag:'wx'});
const prior=await load(root+'/oidc-browser-r5/result.json');
const credentials=await load(root+'/private/identity/credentials.private.json');
const fixture=await load(scenario+'/excerpts/manifest.json');
for(const source of fixture.sources){
 const bytes=await readFile(scenario+'/excerpts/'+source.file);
 if(createHash('sha256').update(bytes).digest('hex')!==source.content_sha256)throw Error('exact_original_bytes_required_before_upload');
}
const query=(await load(scenario+'/excerpts/query-vector.json')).query;
const attempt=process.env.FIN_MULTISOURCE_ATTEMPT||phase;
if(!/^[a-z0-9-]+$/.test(attempt))throw Error('invalid_attempt_name');
const output=scenario+'/'+attempt;await mkdir(output,{recursive:false});
const browser=await chromium.launch({headless:true});
const business='/api/v1/business/workspaces', assets='/api/v1/asset-workspace';
let stage='login', checks=[], owner, reader, state, spaceRemoved=false, projectRemoved=false, child;
async function login(username){
 const context=await browser.newContext({baseURL:origin,viewport:{width:1440,height:1000}}),page=await context.newPage();
 await page.goto('/workspace');await page.getByRole('link',{name:'安全登录'}).click();
 await page.locator('#username').fill(username);await page.locator('#password').fill(credentials.users[username]);
 await page.locator('#kc-login').click();await page.waitForURL(origin+'/workspace');return page;
}
async function api(page,method,path,body,file){
 return page.evaluate(async({method,path,body,file})=>{
  const response=await fetch(path,{method,headers:{'X-Workbench-Request':'1',
   'Content-Type':file?'application/octet-stream':'application/json',...(file?{'X-File-Name':file}:{})},
   ...(body===undefined?{}:{body:file?body:JSON.stringify(body)})});
  return {status:response.status,body:await response.json()};
 },{method,path,body,file});
}
async function ok(page,method,path,body,file){
 const response=await api(page,method,path,body,file);
 if(response.status!==200)throw Error(stage+': HTTP '+response.status+' '+JSON.stringify(response.body).slice(0,300));
 return response.body;
}
async function membership(role){
 const project=await ok(owner,'GET',business+'/projects/'+state.project);
 await ok(owner,'POST',business+`/projects/${state.project}/members`,{revision:project.revision,subject:prior.identities['finsight-reader'],role});
}
async function spaceMembership(role){
 await ok(owner,'POST',business+`/spaces/${state.sources[1].space}/members`,{subject:prior.identities['finsight-reader'],role});
}
async function native(path){const response=await fetch('http://127.0.0.1:18865'+path);expect(response.status).toBe(200);return response.json();}
try{
 owner=await login('finsight-owner');reader=await login('finsight-reader');
 if(phase==='publication'){
  stage='create_isolated_case';state={organization:prior.organization,project:randomUUID(),sources:[],question:query};
  await save(output+'/intent.json',state);
  await ok(owner,'POST',business+'/projects',{id:state.project,organization_id:state.organization,name:'多空间资料权限验收',description:'Two public excerpts, current ACL and frozen inputs; no model calls'});
  await membership('researcher');
  for(const source of fixture.sources){
   const item={...source,space:randomUUID(),resource:randomUUID(),privateProject:randomUUID()};
   await ok(owner,'POST',business+'/spaces',{id:item.space,organization_id:state.organization,name:source.name+' 授权验收空间'});
   const catalog=await ok(owner,'GET','/api/v1/projects');
   await ok(owner,'PUT','/api/v1/projects',{revision:catalog.revision,projects:[...catalog.projects,{id:item.privateProject,name:source.name+' 公开摘录来源'}],assignments:catalog.assignments,pinned:catalog.pinned});
   const text=await readFile(scenario+'/excerpts/'+source.file,'utf8');
   await ok(owner,'POST',`/api/v1/projects/${item.privateProject}/documents`,text,source.file);
   const originals=await ok(owner,'GET',assets+'/projects/'+item.privateProject);
   await ok(owner,'POST',assets+'/spaces/publish',{id:item.resource,space_id:item.space,ref:originals.items[0].current.ref});
   const project=await ok(owner,'GET',business+'/projects/'+state.project);
   await ok(owner,'POST',business+`/projects/${state.project}/resources/${item.resource}`,{revision:project.revision,linked:true});
   expect((await api(reader,'GET',assets+'/spaces/resources/'+item.resource)).status).toBe(404);
   await ok(owner,'POST',business+`/spaces/${item.space}/members`,{subject:prior.identities['finsight-reader'],role:'reader'});
   expect((await ok(reader,'GET',assets+'/spaces/resources/'+item.resource)).text).toBe(text);
   state.sources.push(item);
  }
  stage='pre_index_preparation';state.draft=randomUUID();state.execution=randomUUID();
  state.payload={id:state.draft,title:'离线索引发布输入',question:query,research_as_of:'2026-09-23',resource_ids:state.sources.map(s=>s.resource)};
  const draft=await ok(owner,'POST',business+`/projects/${state.project}/research-drafts`,state.payload);
  state.manifest_digest=draft.manifest_digest;
  await ok(owner,'POST',assets+`/organization-projects/${state.project}/research-drafts/${state.draft}/verify`,{});
  const receipt=await ok(owner,'POST',`/api/v1/organization-projects/${state.project}/research-drafts/${state.draft}/prepare`,{execution_id:state.execution,manifest_digest:state.manifest_digest,execution:{mode:'auto',model:'default',branch_ids:[]}});
  expect(receipt.status).toBe('received');
  checks.push('two_independently_authorized_originals_published','project_membership_alone_denied_both_sources');
 }else{
  if(process.env.FIN_MULTISOURCE_PREPARED){
   stage='resume_same_preparation';state=await load(process.env.FIN_MULTISOURCE_PREPARED);
   const draft=await ok(reader,'GET',business+`/projects/${state.project}/research-drafts/${state.frozen_draft}`);
   const receipt=await ok(reader,'POST',`/api/v1/organization-projects/${state.project}/research/${state.frozen_execution}/reconcile/preparation`,{});
   const thread=await native('/threads/'+state.frozen_execution);
   expect(draft.manifest_digest).toBe(state.frozen_manifest_digest);expect(draft.manifest.retrieval_index).toEqual(state.contract);
   expect(receipt.execution).toEqual({...state.submitted.execution,continuation_scope:'original_question',require_all_branches:false});
   expect(thread.metadata.organization_run_configuration.configurable.finsight_execution).toEqual(receipt.execution);
   expect(thread.metadata.configuration_digest).toBe(receipt.result.configuration_digest);
   expect(await native('/threads/'+state.frozen_execution+'/runs')).toEqual([]);
   checks.push('resumed_exact_existing_page_preparation_without_resubmission');
  }else{
  state=await load(scenario+'/publication/result.json');const release=await load(scenario+'/release.json');
  stage='register_release';const contract=await ok(owner,'POST',assets+`/organization-projects/${state.project}/research-drafts/${state.draft}/retrieval-releases/${release.release_id}/register`,{});
  stage='ordinary_page_form';await reader.goto(`/workspace/projects?scope=organization&project=${state.project}&view=research`);
  await reader.getByRole('button',{name:'新建准备单',exact:true}).click();
  await reader.getByLabel('准备单标题',{exact:true}).fill('双资料 · 当前授权与冻结配置验收');
  await reader.getByLabel('研究问题',{exact:true}).fill(query);
  await reader.getByLabel('研究截止日期',{exact:true}).fill('2026-09-23');
  for(const source of state.sources)await reader.getByRole('checkbox',{name:new RegExp(source.file)}).check();
  await reader.getByLabel('检索版本',{exact:true}).selectOption(release.release_id);
  await reader.screenshot({path:output+'/selected-inputs.png',fullPage:true});
  const draftResponse=reader.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname===business+`/projects/${state.project}/research-drafts`);
  await reader.getByRole('button',{name:'保存输入准备单',exact:true}).click();
  const saved=await draftResponse;expect(saved.status()).toBe(200);const draft=await saved.json();
  expect(draft.manifest.retrieval_index).toEqual(contract);
  expect(new Set(draft.manifest.inputs.map(i=>i.resource_id))).toEqual(new Set(state.sources.map(s=>s.resource)));
  state.frozen_draft=draft.id;state.frozen_manifest_digest=draft.manifest_digest;state.contract=contract;
  const verification=reader.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith(`/research-drafts/${draft.id}/verify`));
  await reader.getByRole('button',{name:'重新校验权限与原件',exact:true}).click();expect((await verification).status()).toBe(200);
  stage='ordinary_page_execution_mode';
  await reader.getByRole('region',{name:'准备执行',exact:true}).getByRole('combobox').selectOption('standard');
  const prepareResponse=reader.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith(`/research-drafts/${draft.id}/prepare`));
  await reader.getByRole('button',{name:'准备研究执行',exact:true}).click();
  const prepared=await prepareResponse;expect(prepared.status()).toBe(200);const receipt=await prepared.json();expect(receipt.status).toBe('received');
  const submitted=prepared.request().postDataJSON();state.frozen_execution=submitted.execution_id;
  expect(submitted.execution).toEqual({mode:'standard',model:'default',branch_ids:[]});
  stage='frozen_configuration';const thread=await native('/threads/'+state.frozen_execution);
  await save(output+'/prepared.json',{...state,submitted,receipt,configuration_digest:thread.metadata.configuration_digest});
  expect(thread.metadata.organization_execution.manifest_digest).toBe(state.frozen_manifest_digest);
  // Java supplies documented defaults absent from the browser's small request.
  expect(receipt.execution).toEqual({...submitted.execution,continuation_scope:'original_question',require_all_branches:false});
  expect(thread.metadata.organization_run_configuration.configurable.finsight_execution).toEqual(receipt.execution);
  expect(thread.metadata.configuration_digest).toBe(receipt.result.configuration_digest);
  expect(thread.metadata.owner_id).toBe('organization:'+state.organization);
  expect(await native('/threads/'+state.frozen_execution+'/runs')).toEqual([]);
  const control=await ok(reader,'GET',`/api/v1/organization-projects/${state.project}/research/${state.frozen_execution}/control`);
  expect(control.enabled).toBe(false);
  await expect(reader.getByText('此环境尚未启用组织研究执行。',{exact:true})).toBeVisible();
  await reader.screenshot({path:output+'/prepared-execution.png',fullPage:true});
  checks.push('ordinary_page_selected_both_sources_and_exact_release','ordinary_page_standard_mode_matches_native_frozen_configuration','native_thread_has_no_runs_and_start_disabled');
  }
  stage='native_warm';
  const probeName='multisource-'+state.frozen_execution+'-'+attempt, hostProbe=root+'/state/calls/'+probeName, containerProbe='/run/finsight/calls/'+probeName;
  await mkdir(hostProbe,{recursive:false});await save(hostProbe+'/binding.json',state);
  await copyFile(process.env.FIN_MULTISOURCE_PROBE,hostProbe+'/probe.py');
  const transport=process.env.FIN_MULTISOURCE_TRANSPORT||'container';
  if(transport==='host'){
   if(!process.env.FIN_MULTISOURCE_PYTHON)throw Error('explicit_host_python_required');
   const businessEnv=await load(root+'/private/business-env.private.json');
   const manifest=await load(root+'/manifest.json');
   const hashes={...manifest.source_hashes,...manifest.deployment_source_overrides};
   let verified=0;
   for(const [path,digest] of Object.entries(hashes)){
    if(path.startsWith('src/')){
     expect(createHash('sha256').update(await readFile(root+'/source/'+path)).digest('hex')).toBe(digest);verified++;
    }
   }
   const env={...process.env,PYTHONPATH:root+'/source/src',PYTHONUTF8:'1',PYTHONDONTWRITEBYTECODE:'1',LANGSMITH_TRACING:'false',
    FINSIGHT_ORGANIZATION_ASSETS_ROOT:root+'/state/project-library/organization-assets',
    FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT:root+'/state/organization-indexes',
    FINSIGHT_BUSINESS_API_URL:businessEnv.FINSIGHT_BUSINESS_API_URL,
    FINSIGHT_ORGANIZATION_RUNTIME_SECRET:businessEnv.FINSIGHT_ORGANIZATION_RUNTIME_SECRET,
    FINSIGHT_ORGANIZATION_AUTHORITY_NETWORK:'loopback'};
   for(const key of ['FINSIGHT_ORGANIZATION_QUERY_EMBEDDING','OPENAI_API_KEY','DEEPSEEK_API_KEY','QWEN_API_KEY','DASHSCOPE_API_KEY','LANGSMITH_API_KEY'])delete env[key];
   state.probe_runtime={transport:'host',source_root:root+'/source/src',source_hashes_verified:verified,container_probe:'pending_control_plane_recovery'};
   child=spawn(process.env.FIN_MULTISOURCE_PYTHON,[hostProbe+'/probe.py','--directory',hostProbe],{windowsHide:true,env,stdio:['ignore','pipe','pipe']});
  }else if(transport==='container'){
   if(!process.env.FIN_DOCKER_EXECUTABLE)throw Error('explicit_docker_executable_required');
   state.probe_runtime={transport:'container',container:'finsight-release-native-langgraph-api-1'};
   child=spawn(process.env.FIN_DOCKER_EXECUTABLE,['exec','finsight-release-native-langgraph-api-1','python',containerProbe+'/probe.py','--directory',containerProbe],{windowsHide:true,stdio:['ignore','pipe','pipe']});
  }else throw Error('unknown_probe_transport');
  // Never forward raw process output or request headers into user-visible logs.
  child.stdout.resume();child.stderr.resume();let childDone=false,childCode;
  const completion=new Promise(resolve=>child.once('exit',code=>{childDone=true;childCode=code;resolve(code);}));
  child.once('error',()=>{childDone=true;childCode=-1;});
  async function waitFor(name){
   const deadline=Date.now()+150000;
   while(Date.now()<deadline){
    try{await access(hostProbe+'/failure.json');throw Error('native_probe_failed:'+JSON.stringify(await load(hostProbe+'/failure.json')));}catch(e){if(e.code!=='ENOENT')throw e;}
    try{return await load(hostProbe+'/'+name+'.done.json');}catch(e){if(e.code!=='ENOENT')throw e;}
    if(childDone)throw Error('native_probe_exited:'+childCode);
    await new Promise(resolve=>setTimeout(resolve,200));
   }throw Error('native_probe_checkpoint_timeout:'+name);
  }
  const signal=name=>writeFile(hostProbe+'/'+name+'.go','ready',{flag:'wx'});
  await waitFor('warm');checks.push('same_production_mcp_session_warms_hybrid_cache_and_reads_both_originals');
  stage='space_revocation';await spaceMembership('remove');spaceRemoved=true;
  expect((await api(reader,'GET',assets+'/spaces/resources/'+state.sources[1].resource)).status).toBe(404);
  expect((await api(reader,'GET',assets+'/spaces/resources/'+state.sources[0].resource)).status).toBe(200);
  const visible=await ok(reader,'GET',business+`/projects/${state.project}/resources`);
  expect(visible.items.map(i=>i.id)).toEqual([state.sources[0].resource]);
  expect((await api(reader,'GET',business+`/projects/${state.project}/research-drafts/${state.frozen_draft}`)).status).toBe(404);
  await signal('space-revoked');await waitFor('space-revoked');
  await reader.goto(`/workspace/projects?scope=organization&project=${state.project}&view=research&draft=${state.frozen_draft}`);
  await expect(reader.getByText('准备单不可读取；请刷新核对当前权限。',{exact:true})).toBeVisible();
  await reader.screenshot({path:output+'/revoked-preparation.png',fullPage:true});
  checks.push('space_revocation_hides_source_title_and_denies_frozen_draft_cached_search_and_both_observed_readbacks');
  stage='space_restore';await spaceMembership('reader');spaceRemoved=false;
  await signal('space-restored');await waitFor('space-restored');
  stage='project_revocation';await membership('remove');projectRemoved=true;
  expect((await api(reader,'GET',business+'/projects/'+state.project)).status).toBe(404);
  expect((await api(reader,'GET',assets+'/spaces/resources/'+state.sources[0].resource)).status).toBe(200);
  await signal('project-revoked');await waitFor('project-revoked');
  checks.push('project_revocation_denies_same_execution_even_when_space_membership_remains');
  stage='project_restore';await membership('researcher');projectRemoved=false;
  await signal('project-restored');await waitFor('project-restored');expect(await completion).toBe(0);
  const restored=await ok(reader,'GET',business+`/projects/${state.project}/research-drafts/${state.frozen_draft}`);
  expect(restored.manifest_digest).toBe(state.frozen_manifest_digest);
  expect(restored.manifest.retrieval_index).toEqual(state.contract);
  expect(await native('/threads/'+state.frozen_execution+'/runs')).toEqual([]);
  checks.push('regrant_restores_original_ids_without_new_execution_or_model_calls');
  state.native_probe=hostProbe+'/result.json';
 }
 await save(output+'/result.json',{...state,checks,provider_calls:0,browser_api_interceptions:0,tls_verification:true,financial_quality:'not_assessed'});
 console.log(JSON.stringify({phase,checks,provider_calls:0}));
}catch(error){
 const failure={stage,checks,error:error.name,summary:String(error.message).split('\n')[0].slice(0,500)};
 if(reader&&new URL(reader.url()).pathname.startsWith('/workspace')){
  await reader.screenshot({path:output+'/failed-page.png',fullPage:true});
  failure.formState=await reader.locator('body').evaluate(body=>({
   headings:[...body.querySelectorAll('h2,h3,h4')].map(n=>n.textContent),
   alerts:[...body.querySelectorAll('[role="alert"]')].map(n=>n.textContent),
   selects:[...body.querySelectorAll('select')].map(n=>({label:n.closest('label')?.textContent,options:[...n.options].map(o=>({value:o.value,text:o.textContent,disabled:o.disabled}))}))}));
 }
 await save(output+'/failure.json',failure);console.error(JSON.stringify(failure));process.exitCode=1;
}finally{
 // Undo only this case's temporary removals, even when an assertion fails.
 if(spaceRemoved)try{await spaceMembership('reader');}catch{console.error('case_space_restore_failed');}
 if(projectRemoved)try{await membership('researcher');}catch{console.error('case_project_restore_failed');}
 if(child&&child.exitCode===null)child.kill();
 await browser.close();
}
