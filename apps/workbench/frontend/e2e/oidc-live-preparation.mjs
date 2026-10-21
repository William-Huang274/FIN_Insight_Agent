// Real login and production publication/preparation. Never starts model work.
import {chromium,expect} from 'playwright/test';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
const root=process.env.FIN_NORMAL_DEPLOYMENT_ROOT, output=process.env.FIN_OIDC_EVIDENCE;
if(!root||!output||process.env.FINSIGHT_PUBLIC_ORIGIN!=='https://localhost:18866')throw Error('explicit_local_deployment_required');
const origin=process.env.FINSIGHT_PUBLIC_ORIGIN;
const credentials=JSON.parse(await readFile(root+'/private/identity/credentials.private.json','utf8'));
const prior=JSON.parse(await readFile(root+'/oidc-browser-r5/result.json','utf8'));
await mkdir(output,{recursive:false});
const browser=await chromium.launch({headless:true}),checks=[];
let stage='login';
async function login(username){
 const context=await browser.newContext({baseURL:origin,viewport:{width:1440,height:1000}}),page=await context.newPage();
 await page.goto('/workspace');await page.getByRole('link',{name:'安全登录'}).click();
 await page.locator('#username').fill(username);await page.locator('#password').fill(credentials.users[username]);
 await page.locator('#kc-login').click();await page.waitForURL(origin+'/workspace');return page;
}
async function api(page,method,path,body,raw=false){
 return page.evaluate(async({method,path,body,raw})=>{
  const r=await fetch(path,{method,headers:{'X-Workbench-Request':'1','Content-Type':raw?'application/octet-stream':'application/json',
   ...(raw?{'X-File-Name':'NVIDIA-historical-disclosure-excerpt.txt'}:{})},...(body===undefined?{}:{body:raw?body:JSON.stringify(body)})});
  return {status:r.status,body:await r.json()};
 },{method,path,body,raw});
}
async function ok(page,method,path,body,raw=false){const r=await api(page,method,path,body,raw);if(r.status!==200)throw Error(stage+': HTTP '+r.status+' '+JSON.stringify(r.body).slice(0,400));return r.body;}
try{
 const owner=await login('finsight-owner');
 const business='/api/v1/business/workspaces', assets='/api/v1/asset-workspace';
 const execution={mode:'auto',model:'default',branch_ids:[],continuation_scope:'original_plan',require_all_branches:false};
 let state;
 if(!process.env.FIN_NORMAL_INDEX_RELEASE){
  stage='create_space'; const space=randomUUID(),resource=randomUUID(),privateProject=randomUUID(),draft=randomUUID(),binding=randomUUID();
  await ok(owner,'POST',business+'/spaces',{id:space,organization_id:prior.organization,name:'历史公开披露 · 授权验收'});
  stage='private_original';const index=await ok(owner,'GET','/api/v1/projects');
  await ok(owner,'PUT','/api/v1/projects',{revision:index.revision,projects:[...index.projects,{id:privateProject,name:'组织发布来源'}],assignments:index.assignments,pinned:index.pinned});
  const text=await readFile(root+'/public-excerpt/NVIDIA-historical-disclosure-excerpt.txt','utf8');
  await ok(owner,'POST',`/api/v1/projects/${privateProject}/documents`,text,true);
  const catalog=await ok(owner,'GET',assets+'/projects/'+privateProject);
  const ref=catalog.items[0].current.ref;
  stage='publish';await ok(owner,'POST',assets+'/spaces/publish',{id:resource,space_id:space,ref});
  const project=await ok(owner,'GET',business+'/projects/'+prior.project);
  await ok(owner,'POST',business+`/projects/${prior.project}/resources/${resource}`,{revision:project.revision,linked:true});
  checks.push('real_original_uploaded_and_published_through_authenticated_bff');
  stage='source_acl';const reader=await login('finsight-reader');
  expect((await api(reader,'GET',assets+'/spaces/resources/'+resource)).status).toBe(404);
  await ok(owner,'POST',business+`/spaces/${space}/members`,{subject:prior.identities['finsight-reader'],role:'reader'});
  const visible=await ok(reader,'GET',assets+'/spaces/resources/'+resource);
  expect(visible.text).toBe(text);
  checks.push('project_membership_does_not_grant_source_access');
  stage='draft'; const payload={id:draft,title:'NVIDIA 客户集中度 · 资料准备',question:'What does NVIDIA disclose about revenue concentration among its direct customers?',research_as_of:'2026-09-23',resource_ids:[resource]};
  const prepared=await ok(owner,'POST',business+`/projects/${prior.project}/research-drafts`,payload);
  await ok(owner,'POST',assets+`/organization-projects/${prior.project}/research-drafts/${draft}/verify`,{});
  stage='native_prepare';const receipt=await ok(owner,'POST',`/api/v1/organization-projects/${prior.project}/research-drafts/${draft}/prepare`,{execution_id:binding,manifest_digest:prepared.manifest_digest,execution});
  expect(receipt.status).toBe('received');checks.push('java_preparation_creates_production_native_thread_without_run');
  state={organization:prior.organization,project:prior.project,space,resource,privateProject,draft,execution:binding,manifest_digest:prepared.manifest_digest,payload};
 }else{
  state=JSON.parse(await readFile(root+'/publication-r1/result.json','utf8'));
  const release=process.env.FIN_NORMAL_INDEX_RELEASE;
  stage='register_release';const contract=await ok(owner,'POST',assets+`/organization-projects/${state.project}/research-drafts/${state.draft}/retrieval-releases/${release}/register`,{});
  stage='frozen_draft';const draft=randomUUID(),binding=randomUUID();
  const prepared=await ok(owner,'POST',business+`/projects/${state.project}/research-drafts`,{...state.payload,id:draft,retrieval_release_id:release});
  expect(prepared.manifest.retrieval_index).toEqual(contract);
  await ok(owner,'POST',assets+`/organization-projects/${state.project}/research-drafts/${draft}/verify`,{});
  stage='frozen_native_prepare';const receipt=await ok(owner,'POST',`/api/v1/organization-projects/${state.project}/research-drafts/${draft}/prepare`,{execution_id:binding,manifest_digest:prepared.manifest_digest,execution});
  expect(receipt.status).toBe('received');
  const control=await ok(owner,'GET',`/api/v1/organization-projects/${state.project}/research/${binding}/control`);
  expect(control.enabled).toBe(false);
  expect((await api(owner,'POST',`/api/v1/organization-projects/${state.project}/research/${binding}/start`,{})).status).toBe(503);
  checks.push('index_release_bound_to_java_preparation_and_native_thread','start_remains_disabled');
  state={...state,frozen_draft:draft,frozen_execution:binding,frozen_manifest_digest:prepared.manifest_digest,contract};
 }
 stage='page';await owner.goto('/workspace/projects?scope=organization&project='+state.project+'&view=files');
 await expect(owner.getByRole('heading',{name:'项目资料',exact:true})).toBeVisible();
 await expect(owner.getByText('NVIDIA-historical-disclosure-excerpt.txt',{exact:true}).first()).toBeVisible();
 await owner.screenshot({path:output+'/project-sources.png',fullPage:true});
 await writeFile(output+'/result.json',JSON.stringify({...state,checks,provider_calls:0,browser_api_interceptions:0,tls_verification:true},null,2));
 console.log(JSON.stringify({checks,provider_calls:0}));
}catch(e){await writeFile(output+'/failure.json',JSON.stringify({stage,checks,error:e.name,summary:String(e.message).split('\n')[0].slice(0,500)},null,2));console.error(JSON.stringify({stage,error:e.name,summary:String(e.message).split('\n')[0].slice(0,500)}));process.exitCode=1;}
finally{await browser.close();}
