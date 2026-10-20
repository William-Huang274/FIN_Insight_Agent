import {test,expect,type Page} from './identity-fixture';
const org='10000000-0000-4000-8000-000000000001',project='20000000-0000-4000-8000-000000000002',resource='30000000-0000-4000-8000-000000000003';
const url=`/workspace/projects?scope=organization&project=${project}&view=research`;
async function fixture(page:Page,role='researcher'){
  const state={releases:[] as any[],saved:null as any,drafts:{} as Record<string,any>,posts:[] as any[],drop:false,revoked:false,verifies:0,hold:false,holdRead:false,release:null as null|(()=>void),execution:null as any,prepares:[] as any[],reconciles:0};
  await page.route('**/api/v1/**',async route=>{
    const r=route.request(),u=new URL(r.url()),b=r.postData()?r.postDataJSON():null;let result:any={};
    if(u.pathname==='/api/v1/business/config')result={enabled:true,organization_projects:true,resource_spaces:true,team_collaboration:false};
    else if(u.pathname==='/api/v1/projects')result={revision:0,projects:[],assignments:{},pinned:[]};
    else if(u.pathname==='/api/v1/research-sessions')result=[];
    else if(u.pathname==='/api/v1/business/workspaces')result={spaces:[],organizations:[{id:org,name:'合成研究团队',role:'member'}]};
    else if(u.pathname===`/api/v1/business/workspaces/projects/${project}`)result={id:project,organization_id:org,organization_name:'合成研究团队',name:'AI 基础设施',description:'无模型静态案例',archived:false,revision:3,can_manage:false,role,research_enabled:false};
    else if(u.pathname.endsWith('/retrieval-releases'))result={items:state.revoked?[]:state.releases};
    else if(u.pathname.endsWith('/members'))result=[];
    else if(u.pathname.endsWith('/resources'))result={items:[{id:resource,title:'季度资料固定副本',resource_type:'files',space_name:'行业研究组'}],next_offset:null};
    else if(u.pathname.endsWith('/research-drafts')){
      if(r.method()==='POST'){
        if(role==='viewer')throw Error('viewer attempted mutation');
        state.posts.push(b);
        if(state.drafts[b.id])expect(b).toEqual(state.posts.find(p=>p.id===b.id));
        state.saved={...b,created_at:'2026-10-13T10:00:00Z',status:'inputs_saved',execution_enabled:false,manifest_digest:'sha256:'+'a'.repeat(64),manifest:{...(b.retrieval_release_id?{retrieval_index:state.releases.find(x=>x.release_id===b.retrieval_release_id)}:{}),research_as_of:b.research_as_of,inputs:[{resource_id:resource,title:'季度资料固定副本',resource_type:'files',ref:{version_id:'frozen-v1',digest:'b'.repeat(64)}}]}};
        state.drafts[b.id]=state.saved;
        if(state.drop){state.drop=false;await route.fulfill({status:503,json:{detail:'提交响应丢失'}});return;}result=state.saved;
      }else result={items:state.revoked?[]:Object.values(state.drafts),next_offset:null};
    }
    else if(u.pathname.endsWith('/verify')){
      state.verifies++;
      if(state.hold)await new Promise<void>(resolve=>{state.release=resolve;});
      if(state.revoked){await route.fulfill({status:404,json:{detail:'准备单或所选资料不可访问'}});return;}
      result={manifest_digest:state.saved.manifest_digest,notice:'本次权限与原件校验通过；不是启动许可，未创建研究运行。'};
    }
    else if(u.pathname.endsWith('/executions'))result=state.execution?[{execution_id:state.execution.execution_id,preparation:'unknown',closed:false}]:[];
    else if(u.pathname.endsWith('/prepare')){state.prepares.push(b);state.execution=b;result={status:'unknown'};}
    else if(u.pathname.endsWith('/reconcile/preparation')){state.reconciles++;result={status:'received'};}
    else if(u.pathname.endsWith('/control'))result={can_operate:true,enabled:true,preparation:'received',start:'absent',continuation:'absent'};
    else if(u.pathname===`/api/v1/organization-projects/${project}/research`)result={items:[{execution_id:state.execution.execution_id,title:state.saved.title,run_id:null}],next_offset:null};
    else if(u.pathname===`/api/v1/organization-projects/${project}/research/${state.execution?.execution_id}`)result={title:state.saved.title,run_id:null};
    else if(u.pathname.includes('/research-drafts/')){
      if(state.holdRead)await new Promise<void>(resolve=>{state.release=resolve;});
      const draft=state.drafts[u.pathname.split('/').at(-1)!];
      if(state.revoked||!draft){await route.fulfill({status:404,json:{detail:'准备单或所选资料不可访问'}});return;}result=draft;
    }
    else throw Error('Unexpected request '+r.method()+' '+u.pathname);
    await route.fulfill({json:result});
  });return state;
}
async function fill(page:Page){
  await page.getByLabel('准备单标题',{exact:true}).fill('资本开支与现金流研究');
  await page.getByRole('textbox',{name:'研究问题',exact:true}).fill('请核对资本开支与现金流覆盖情况及原始来源。');
  await page.getByLabel('研究截止日期',{exact:true}).fill('2026-10-12');
  await page.getByRole('checkbox',{name:/季度资料固定副本/}).check();
  await page.getByRole('button',{name:'保存输入准备单',exact:true}).click();
}
test('selected release survives response loss and copying while source changes require reselection',async({page})=>{
  const state=await fixture(page),release='40000000-0000-4000-8000-000000000004';
  state.releases=[{release_id:release,model:'qwen3.7-text-embedding',index_digest:'c'.repeat(64),
    published_at:'2026-10-20T10:00:00Z',resource_ids:[resource]}];
  await page.goto(url);
  await page.getByLabel('准备单标题',{exact:true}).fill('固定检索版本');
  await page.getByLabel('研究问题',{exact:true}).fill('研究固定披露中的现金流和资本支出变化。');
  await page.getByLabel('研究截止日期',{exact:true}).fill('2026-10-12');
  await page.getByRole('checkbox',{name:/季度资料固定副本/}).check();
  await page.getByLabel('检索版本',{exact:true}).selectOption(release);
  state.drop=true;
  await page.getByRole('button',{name:'保存输入准备单',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('响应丢失');
  await page.reload();
  await page.getByRole('button',{name:'以原内容重试保存',exact:true}).click();
  await expect(page.getByText(/检索版本已固定/)).toBeVisible();
  expect(state.posts).toHaveLength(2);
  expect(state.posts[1]).toEqual(state.posts[0]);
  expect(state.posts[0].retrieval_release_id).toBe(release);
  await page.getByRole('button',{name:'复制为新准备单',exact:true}).click();
  await expect(page.getByLabel('检索版本',{exact:true})).toHaveValue(release);
  await page.getByRole('checkbox',{name:/季度资料固定副本/}).uncheck();
  await expect(page.getByLabel('检索版本',{exact:true})).toHaveValue('');
  await expect(page.getByRole('status')).toContainText('资料选择已变化');
  expect(state.posts).toHaveLength(2);
});
for(const width of [1440,390])test(`frozen preparation, explicit verify and withdrawal at ${width}`,async({page},info)=>{
  await page.setViewportSize({width,height:960});const state=await fixture(page);
  await page.goto(url);await expect(page.getByRole('checkbox',{name:/季度资料固定副本/})).toBeVisible();
  await page.screenshot({path:info.outputPath(`organization-inputs-form-${width}.png`),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await fill(page);
  await expect(page.getByRole('heading',{name:'资本开支与现金流研究',exact:true})).toBeVisible();
  await expect(page.getByRole('button',{name:/启动研究/})).toHaveCount(0);
  await page.getByText('版本核对信息',{exact:true}).click();await expect(page.getByText(/frozen-v1/)).toBeVisible();
  await page.getByRole('button',{name:'重新校验权限与原件'}).click();await expect(page.getByRole('status')).toContainText('本次权限与原件校验通过');
  await page.screenshot({path:info.outputPath(`organization-inputs-${width}.png`),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.reload();await expect(page.getByRole('heading',{name:'资本开支与现金流研究',exact:true})).toBeVisible();expect(state.verifies).toBe(1);
  state.revoked=true;await page.getByRole('button',{name:'重新校验权限与原件'}).click();await expect(page.getByRole('alert')).toContainText('不可访问');
  await expect(page.getByText('请核对资本开支与现金流覆盖情况及原始来源。',{exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:/资本开支与现金流研究/})).toHaveCount(0);expect(state.posts).toHaveLength(1);
  await page.getByRole('button',{name:'新建准备单',exact:true}).click();
  await expect(page.getByRole('checkbox',{name:/季度资料固定副本/})).toHaveCount(0);
});
test('unknown response survives reload and explicit replay uses the same body',async({page})=>{
  const state=await fixture(page);state.drop=true;await page.goto(url);await fill(page);
  await expect(page.getByRole('alert')).toContainText('响应丢失');await page.reload();
  await expect(page.getByText(/上次提交待核对/)).toBeVisible();expect(state.posts).toHaveLength(1);
  await page.getByRole('button',{name:'以原内容重试保存'}).click();await expect(page.getByRole('heading',{name:'资本开支与现金流研究',exact:true})).toBeVisible();
  expect(state.posts).toHaveLength(2);expect(state.posts[0]).toEqual(state.posts[1]);
});
test('reading the original resolves a pending save; viewer has no mutation controls',async({page})=>{
  const state=await fixture(page);state.drop=true;await page.goto(url);await fill(page);
  await expect(page.getByRole('alert')).toContainText('响应丢失');await page.getByRole('button',{name:'核对原准备单'}).click();
  await expect(page.getByRole('heading',{name:'资本开支与现金流研究',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'新建准备单',exact:true}).click();await expect(page.getByText(/上次提交待核对/)).toHaveCount(0);expect(state.posts).toHaveLength(1);
  await page.goto('about:blank');await page.unroute('**/api/v1/**');const viewer=await fixture(page,'viewer');await page.goto(url);
  await expect(page.getByText(/只读成员可以查看有权读取的准备单/)).toBeVisible();
  await expect(page.getByRole('button',{name:'保存输入准备单'})).toHaveCount(0);expect(viewer.posts).toHaveLength(0);
});
test('late verification cannot replace a newly selected preparation form',async({page})=>{
  const state=await fixture(page);await page.goto(url);await fill(page);
  await expect(page.getByRole('heading',{name:'资本开支与现金流研究',exact:true})).toBeVisible();state.hold=true;
  await page.getByRole('button',{name:'重新校验权限与原件'}).click();await expect.poll(()=>!!state.release).toBe(true);
  await page.goto(url);await expect(page.getByRole('heading',{name:'准备研究输入',exact:true})).toBeVisible();
  state.release!();await expect(page.getByText('本次权限与原件校验通过；不是启动许可，未创建研究运行。',{exact:true})).toHaveCount(0);
});

test('execution preparation recovers the same unknown command after reload without starting',async({page})=>{
  const state=await fixture(page);await page.goto(url);await fill(page);
  await page.getByRole('button',{name:'准备研究执行',exact:true}).click();
  await expect(page.getByRole('button',{name:'核对原准备结果',exact:true})).toBeVisible();
  expect(state.prepares).toHaveLength(1);const id=state.prepares[0].execution_id;
  await page.reload();await expect(page.getByRole('button',{name:'核对原准备结果',exact:true})).toBeVisible();
  expect(state.prepares).toHaveLength(1);
  await page.getByRole('button',{name:'核对原准备结果',exact:true}).click();
  await expect(page.getByRole('button',{name:'开始预研究',exact:true})).toBeVisible();
  expect(new URL(page.url()).searchParams.get('execution')).toBe(id);
  expect(state.reconciles).toBe(1);expect(state.prepares).toHaveLength(1);
});

for(const width of [1440,390])test(`copy corrects cutoff without changing original or automatic submission at ${width}`,async({page},info)=>{
  await page.setViewportSize({width,height:960});const state=await fixture(page);
  await page.goto(url);await fill(page);
  await expect(page.getByRole('heading',{name:'资本开支与现金流研究',exact:true})).toBeVisible();
  const original=structuredClone(state.saved);
  await page.getByRole('button',{name:'复制为新准备单',exact:true}).click();
  await expect(page.getByRole('textbox',{name:'研究问题',exact:true})).toHaveValue(original.question);
  await expect(page.getByRole('checkbox',{name:/季度资料固定副本/})).toBeChecked();
  expect(state.posts).toHaveLength(1);
  await page.getByLabel('准备单标题',{exact:true}).fill('修正截止日期');
  await page.getByLabel('研究截止日期',{exact:true}).fill('2026-10-13');
  await page.screenshot({path:info.outputPath(`copy-preparation-${width}.png`),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  state.drop=true;
  await page.getByRole('button',{name:'保存输入准备单',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('响应丢失');
  await page.reload();await page.getByRole('button',{name:'以原内容重试保存',exact:true}).click();
  await expect(page.getByRole('heading',{name:'修正截止日期',exact:true})).toBeVisible();
  expect(state.posts).toHaveLength(3);expect(state.posts[2]).toEqual(state.posts[1]);
  expect(state.saved.id).not.toBe(original.id);
  expect(state.saved.manifest.inputs).toEqual(original.manifest.inputs);
  expect(state.drafts[original.id]).toEqual(original);expect(state.prepares).toHaveLength(0);
  await page.getByRole('button',{name:'新建准备单',exact:true}).click();
  await expect(page.getByRole('textbox',{name:'研究问题',exact:true})).toHaveValue('');
  await expect(page.getByRole('checkbox',{name:/季度资料固定副本/})).not.toBeChecked();
});
test('copy checks current permission and erases denied source without a write',async({page})=>{
  const state=await fixture(page);await page.goto(url);await fill(page);
  await expect(page.getByRole('heading',{name:'资本开支与现金流研究',exact:true})).toBeVisible();
  state.revoked=true;
  await page.getByRole('button',{name:'复制为新准备单',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('不可访问');
  await expect(page.getByText('请核对资本开支与现金流覆盖情况及原始来源。',{exact:true})).toHaveCount(0);
  await page.getByRole('button',{name:'新建准备单',exact:true}).click();
  await expect(page.getByRole('textbox',{name:'研究问题',exact:true})).toHaveValue('');
  await expect(page.getByRole('checkbox')).toHaveCount(0);
  expect(state.posts).toHaveLength(1);
});
test('late copy response cannot overwrite navigation',async({page})=>{
  const state=await fixture(page);await page.goto(url);await fill(page);
  await expect(page.getByRole('heading',{name:'资本开支与现金流研究',exact:true})).toBeVisible();
  state.holdRead=true;await page.getByRole('button',{name:'复制为新准备单',exact:true}).click();
  await expect.poll(()=>!!state.release).toBe(true);
  await page.goto(url);await expect(page.getByRole('heading',{name:'准备研究输入',exact:true})).toBeVisible();
  state.release!();
  await expect(page.getByRole('textbox',{name:'研究问题',exact:true})).toHaveValue('');
  await expect(page.getByRole('complementary',{name:'复制的研究输入'})).toHaveCount(0);
  expect(state.posts).toHaveLength(1);
});
test('copied selection outside current resource page is visible and removable',async({page})=>{
  const state=await fixture(page);await page.goto(url);await fill(page);
  await expect(page.getByRole('heading',{name:'资本开支与现金流研究',exact:true})).toBeVisible();
  // Source is authorized but paginated out of the current resource list.
  await page.route('**/resources?offset=*',route=>route.fulfill({json:{items:[],next_offset:null}}));
  await page.reload();
  await page.getByRole('button',{name:'复制为新准备单',exact:true}).click();
  await expect(page.getByRole('checkbox')).toHaveCount(0);
  await page.getByRole('button',{name:'移除 季度资料固定副本',exact:true}).click();
  await expect(page.getByRole('button',{name:'保存输入准备单',exact:true})).toBeDisabled();
  expect(state.posts).toHaveLength(1);
});
test('an unresolved different submission cannot be overwritten by copying a saved draft',async({page})=>{
  const state=await fixture(page);await page.goto(url);await fill(page);
  await expect(page.getByRole('heading',{name:'资本开支与现金流研究',exact:true})).toBeVisible();
  const originalId=state.saved.id;
  await page.getByRole('button',{name:'新建准备单',exact:true}).click();
  state.drop=true;await fill(page);
  await expect(page.getByRole('alert')).toContainText('响应丢失');
  await page.goto(`${url}&draft=${originalId}`);
  await expect(page.getByRole('button',{name:'复制为新准备单',exact:true})).toBeDisabled();
  await page.getByRole('button',{name:'新建准备单',exact:true}).click();
  await expect(page.getByText(/上次提交待核对/)).toBeVisible();
  expect(state.posts).toHaveLength(2);
});
