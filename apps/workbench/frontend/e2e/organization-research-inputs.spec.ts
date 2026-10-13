import {test,expect,type Page} from './identity-fixture';
const org='10000000-0000-4000-8000-000000000001',project='20000000-0000-4000-8000-000000000002',resource='30000000-0000-4000-8000-000000000003';
const url=`/workspace/projects?scope=organization&project=${project}&view=research`;
async function fixture(page:Page,role='researcher'){
  const state={saved:null as any,posts:[] as any[],drop:false,revoked:false,verifies:0,hold:false,release:null as null|(()=>void)};
  await page.route('**/api/v1/**',async route=>{
    const r=route.request(),u=new URL(r.url()),b=r.postData()?r.postDataJSON():null;let result:any={};
    if(u.pathname==='/api/v1/business/config')result={enabled:true,organization_projects:true,resource_spaces:true,team_collaboration:false};
    else if(u.pathname==='/api/v1/projects')result={revision:0,projects:[],assignments:{},pinned:[]};
    else if(u.pathname==='/api/v1/research-sessions')result=[];
    else if(u.pathname==='/api/v1/business/workspaces')result={spaces:[],organizations:[{id:org,name:'合成研究团队',role:'member'}]};
    else if(u.pathname===`/api/v1/business/workspaces/projects/${project}`)result={id:project,organization_id:org,organization_name:'合成研究团队',name:'AI 基础设施',description:'无模型静态案例',archived:false,revision:3,can_manage:false,role,research_enabled:false};
    else if(u.pathname.endsWith('/members'))result=[];
    else if(u.pathname.endsWith('/resources'))result={items:[{id:resource,title:'季度资料固定副本',resource_type:'files',space_name:'行业研究组'}],next_offset:null};
    else if(u.pathname.endsWith('/research-drafts')){
      if(r.method()==='POST'){
        if(role==='viewer')throw Error('viewer attempted mutation');
        state.posts.push(b);
        if(state.saved)expect(b).toEqual(state.posts[0]);
        state.saved={...b,created_at:'2026-10-13T10:00:00Z',status:'inputs_saved',execution_enabled:false,manifest_digest:'sha256:'+'a'.repeat(64),manifest:{research_as_of:b.research_as_of,inputs:[{resource_id:resource,title:'季度资料固定副本',resource_type:'files',ref:{version_id:'frozen-v1',digest:'b'.repeat(64)}}]}};
        if(state.drop){state.drop=false;await route.fulfill({status:503,json:{detail:'提交响应丢失'}});return;}result=state.saved;
      }else result={items:state.saved&&!state.revoked?[state.saved]:[],next_offset:null};
    }
    else if(u.pathname.endsWith('/verify')){
      state.verifies++;
      if(state.hold)await new Promise<void>(resolve=>{state.release=resolve;});
      if(state.revoked){await route.fulfill({status:404,json:{detail:'准备单或所选资料不可访问'}});return;}
      result={manifest_digest:state.saved.manifest_digest,notice:'本次权限与原件校验通过；不是启动许可，未创建研究运行。'};
    }
    else if(u.pathname.includes('/research-drafts/')){
      if(state.revoked||!state.saved){await route.fulfill({status:404,json:{detail:'准备单或所选资料不可访问'}});return;}result=state.saved;
    }
    else throw Error('Unexpected request '+r.method()+' '+u.pathname);
    await route.fulfill({json:result});
  });return state;
}
async function fill(page:Page){
  await page.getByLabel('准备单标题',{exact:true}).fill('资本开支与现金流研究');
  await page.getByLabel('研究问题',{exact:true}).fill('请核对资本开支与现金流覆盖情况及原始来源。');
  await page.getByLabel('研究截止日期',{exact:true}).fill('2026-10-12');
  await page.getByRole('checkbox',{name:/季度资料固定副本/}).check();
  await page.getByRole('button',{name:'保存输入准备单',exact:true}).click();
}
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
  await page.unroute('**/api/v1/**');const viewer=await fixture(page,'viewer');await page.goto(url);
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
