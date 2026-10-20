import {test,expect,type Page} from './identity-fixture';
const org='10000000-0000-4000-8000-000000000001',team='20000000-0000-4000-8000-000000000002',personal='30000000-0000-4000-8000-000000000003',resource='40000000-0000-4000-8000-000000000004';
const ref={project_id:org,kind:'document',asset_id:'UPLOAD::a',version_id:'UPLOAD::a',digest:'a'.repeat(64)};
const version={ref,title:'资本开支资料.md',sequence:1,created_at:'2026-09-23T01:00:00Z',access_status:'active',status:'complete',role:'document'};
async function fixture(page:Page,manager=true){
  const calls:{method:string;path:string;query:URLSearchParams;body:any}[]=[],publications:any[]=[];
  const spaces=[{id:personal,name:'我的工作区',organization_id:org,organization_name:'研究团队',kind:'personal',can_manage:true,organization_admin:manager},{id:team,name:'AI 基础设施',organization_id:org,organization_name:'研究团队',kind:'team',can_manage:manager,organization_admin:manager}];
  const organizations=[{id:org,name:'研究团队',role:manager?'admin':'member'}];
  let active=true;
  await page.route('**/api/v1/**',async route=>{
    const r=route.request(),u=new URL(r.url()),body=r.postData()?r.postDataJSON():null;
    calls.push({method:r.method(),path:u.pathname,query:u.searchParams,body});let result:unknown={};
    if(u.pathname==='/api/v1/projects')result={revision:1,projects:[{id:org,name:'AI 基础设施',archived:false}],assignments:{},pinned:[]};
    else if(u.pathname==='/api/v1/business/config')result={enabled:true,resource_spaces:true};
    else if(u.pathname==='/api/v1/business/workspaces')result={spaces,organizations};
    else if(u.pathname==='/api/v1/business/workspaces/projects')result={items:[],next_offset:null};
    else if(u.pathname==='/api/v1/business/workspaces/organizations'){
      organizations.push({id:body.id,name:body.name,role:'admin'});
      spaces.push({id:body.id,name:'我的工作区',organization_id:body.id,organization_name:body.name,kind:'personal',can_manage:true,organization_admin:true});
      result={spaces,organizations};
    }
    else if(u.pathname.endsWith('/members'))result=[{subject:'alice',display_name:'Alice',role:manager?'admin':'reader',active:true}];
    else if(u.pathname===`/api/v1/business/workspaces/spaces/${team}/resources`)result={items:active&&(!u.searchParams.get('type')||u.searchParams.get('type')==='files')?[{id:resource,title:version.title,resource_type:'files',revision:1}]:[],next_offset:null};
    else if(u.pathname===`/api/v1/business/workspaces/spaces/${personal}/resources`)result={items:[],next_offset:null};
    else if(u.pathname.startsWith('/api/v1/business/workspaces/spaces/')&&u.pathname.endsWith('/resources'))result={items:[],next_offset:null};
    else if(u.pathname.startsWith('/api/v1/asset-workspace/spaces/resources/'))result={resource_id:u.pathname.split('/').at(-1),version,text:'发布时的合成资料。',truncated:false,editable:false,permission_revision:1,publication:{space_id:team,source_ref:ref}};
    else if(u.pathname.endsWith('/revoke')){active=false;result={revoked:true};}
    else if(u.pathname==='/api/v1/asset-workspace/catalog')result={items:[{project_id:org,project_name:'AI 基础设施',asset_id:ref.asset_id,kind:'document',version_count:1,current:version}],next_offset:null};
    else if(u.pathname==='/api/v1/asset-workspace/spaces/publish'){
      publications.push(body);
      if(publications.length===1){await route.fulfill({status:503,json:{detail:'空间服务响应丢失，请保留原发布标识。'}});return;}
      result={id:body.id,revision:1};
    }
    else throw Error('Unexpected request '+u.pathname);
    await route.fulfill({json:result});
  });return {calls,publications,spaces};
}
test('long organization and space names stay within mobile viewport',async({page},info)=>{
  await page.setViewportSize({width:390,height:960});
  const {spaces}=await fixture(page,false);
  for(const space of spaces){space.organization_name='Historical unified organization';space.name='Historical team inputs';}
  await page.goto(`/workspace/assets?view=all-resources&space=${team}`);
  await expect(page.getByRole('combobox',{name:'所属空间'})).toHaveValue(team);
  const overflow=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,
    elements:[...document.querySelectorAll('label,select')].map(e=>({tag:e.tagName,text:e.textContent?.slice(0,100),right:e.getBoundingClientRect().right})).filter(e=>e.right>innerWidth+1)}));
  expect(overflow.scroll,JSON.stringify(overflow)).toBeLessThanOrEqual(overflow.width+1);
  await page.screenshot({path:info.outputPath('long-space-name-390.png'),fullPage:true});
});
for(const width of [1440,390])test(`unified space and type navigation with readonly publication at ${width}`,async({page},info)=>{
  await page.setViewportSize({width,height:960});const {calls}=await fixture(page,false);
  await page.goto(`/workspace/assets?view=all-resources&space=${team}`);
  await expect(page.getByRole('combobox',{name:'所属空间'})).toHaveValue(team);
  await expect(page.getByText('资本开支资料.md',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'数据库',exact:true}).click();
  await expect(page).toHaveURL(new RegExp(`space=${team}`));
  await expect(page.getByText(/当前范围内尚无发布资料/)).toBeVisible();
  expect(calls.at(-1)?.query.get('type')).toBe('database');
  await page.getByRole('button',{name:'文件资料',exact:true}).click();
  await page.getByRole('button').filter({hasText:'资本开支资料.md'}).click();
  await expect(page.getByRole('heading',{name:'资本开支资料.md'})).toBeVisible();
  await expect(page.getByText('发布的固定版本 · 只读')).toBeVisible();
  await expect(page.getByRole('button',{name:'撤销此发布'})).toHaveCount(0);
  await page.screenshot({path:info.outputPath(`resource-space-reader-${width}.png`),fullPage:true});
  await page.getByRole('button',{name:'返回空间资料'}).click();
  await page.getByRole('combobox',{name:'所属空间'}).selectOption(personal);
  await expect(page.getByText(/组织内个人工作区，默认本人可见/)).toBeVisible();
  await page.reload();await expect(page.getByRole('combobox',{name:'所属空间'})).toHaveValue(personal);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  expect(calls.some(c=>/\/(start|runs|contexts)$/.test(c.path))).toBe(false);
});
test('explicit publication retains identity on manual retry after unknown response',async({page},info)=>{
  const {publications}=await fixture(page);
  await page.goto(`/workspace/assets?view=files&return_thread=${resource}`);
  await expect(page.getByRole('link',{name:'返回研究',exact:true})).toHaveAttribute('href',`/workspace/session?thread=${resource}&view=graph`);
  await page.getByRole('button',{name:'发布到组织空间'}).click();
  const dialog=page.getByRole('dialog',{name:'发布资料到组织空间'});
  await dialog.getByLabel('本页资料').selectOption(ref.version_id);
  await dialog.getByLabel('目标空间').selectOption(team);
  await expect(dialog.getByRole('button',{name:'确认发布此版本'})).toBeDisabled();
  await dialog.getByRole('checkbox').check();
  await page.screenshot({path:info.outputPath('resource-publication-confirmation.png')});
  await dialog.getByRole('button',{name:'确认发布此版本'}).click();
  await expect(dialog.getByRole('alert')).toContainText('响应丢失');
  expect(publications).toHaveLength(1);
  await dialog.getByRole('button',{name:'按原请求重试'}).click();
  await expect(dialog.getByRole('link',{name:'打开空间中的资料'})).toBeVisible();
  expect(publications).toHaveLength(2);expect(publications[0]).toEqual(publications[1]);
});
for(const outcome of ['saved','unavailable','mismatch'] as const)test(`publication recovery after reload: ${outcome}`,async({page},info)=>{
  const {publications}=await fixture(page);
  await page.goto('/workspace/assets?view=files');
  await page.getByRole('button',{name:'发布到组织空间'}).click();
  const dialog=page.getByRole('dialog',{name:'发布资料到组织空间'});
  await dialog.getByLabel('本页资料').selectOption(ref.version_id);
  await dialog.getByLabel('目标空间').selectOption(team);
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button',{name:'确认发布此版本'}).click();
  await expect(dialog.getByRole('alert')).toContainText('响应丢失');
  const original=publications[0];
  await page.reload();
  await page.getByRole('button',{name:'发布到组织空间'}).click();
  await expect(dialog.getByRole('region',{name:'待核对的发布'})).toBeVisible();
  await expect(dialog.getByLabel('目标空间')).toHaveCount(0);
  expect(publications).toHaveLength(1);
  if(outcome!=='saved')await page.route(`**/api/v1/asset-workspace/spaces/resources/${original.id}`,route=>route.fulfill(
    outcome==='unavailable'?{status:404,json:{detail:'资料不可访问'}}:
      {json:{resource_id:original.id,publication:{space_id:team,source_ref:{...ref,digest:'b'.repeat(64)}}}}));
  await dialog.getByRole('button',{name:'查询发布结果'}).click();
  if(outcome==='saved'){
    await expect(dialog.getByRole('link',{name:'打开空间中的资料'})).toHaveAttribute('href',new RegExp(`resource=${original.id}`));
  }else{
    await expect(dialog.getByRole('alert')).toContainText('不能据此认定发布没有发生');
    await expect(dialog.getByRole('region',{name:'待核对的发布'})).toBeVisible();
    await expect(dialog.getByRole('link',{name:'打开空间中的资料'})).toHaveCount(0);
    if(outcome==='unavailable'){
      page.once('dialog',d=>d.dismiss());
      await dialog.getByRole('button',{name:'结束本次核对'}).click();
      await expect(dialog.getByRole('region',{name:'待核对的发布'})).toBeVisible();
      page.once('dialog',d=>d.accept());
      await dialog.getByRole('button',{name:'结束本次核对'}).click();
      await expect(dialog.getByRole('button',{name:'确认发布此版本'})).toBeDisabled();
    }
  }
  expect(publications).toHaveLength(1);
  await page.screenshot({path:info.outputPath(`publication-recovery-${outcome}.png`)});
});
test('publication pending intent is not offered to another login identity',async({page})=>{
  const {publications}=await fixture(page);
  await page.goto('/workspace/assets?view=files');
  await page.evaluate(({team,ref})=>sessionStorage.setItem('finsight.space.intent:local-pilot:publish',
    JSON.stringify({id:crypto.randomUUID(),encoded:JSON.stringify({space_id:team,ref})})),{team,ref});
  await page.route('**/auth/status',route=>route.fulfill({json:{
    mode:'oidc_product',authenticated:true,browser_login:false,owner:'another-user'}}));
  await page.reload();
  await page.getByRole('button',{name:'发布到组织空间'}).click();
  const dialog=page.getByRole('dialog',{name:'发布资料到组织空间'});
  await expect(dialog.getByLabel('目标空间')).toBeVisible();
  await expect(dialog.getByRole('region',{name:'待核对的发布'})).toHaveCount(0);
  expect(publications).toHaveLength(0);
  expect(await page.evaluate(()=>sessionStorage.getItem('finsight.space.intent:local-pilot:publish'))).not.toBeNull();
});
test('manager revokes publication and stale space links do not display other-space contents',async({page})=>{
  await fixture(page);
  await page.goto(`/workspace/assets?view=files&space=${team}&resource=${resource}`);
  page.on('dialog',dialog=>dialog.accept());
  await page.getByRole('button',{name:'撤销此发布'}).click();
  await expect(page.getByText(/当前范围内尚无发布资料/)).toBeVisible();
  await page.goto(`/workspace/assets?view=files&space=${personal}&resource=${resource}`);
  await expect(page.getByRole('alert')).toContainText('不属于当前空间');
  await expect(page.getByText('发布时的合成资料。')).toHaveCount(0);
});
test('creating a same-name organization selects its own personal workspace',async({page},info)=>{
  const {calls}=await fixture(page);
  await page.goto(`/workspace/assets?view=all-resources&space=${team}`);
  await page.getByText('空间与成员管理',{exact:true}).click();
  await page.getByRole('textbox',{name:'组织名称',exact:true}).fill('研究团队');
  await page.getByRole('textbox',{name:'我的成员名称'}).fill('Alice');
  await page.getByRole('button',{name:'创建组织',exact:true}).click();
  await expect(page.getByText('已保存。',{exact:true})).toBeVisible();
  const created=calls.find(c=>c.path==='/api/v1/business/workspaces/organizations')!.body.id;
  await expect(page.getByRole('combobox',{name:'所属空间'})).toHaveValue(created);
  await expect(page.getByText(/组织内个人工作区，默认本人可见/)).toBeVisible();
  await page.screenshot({path:info.outputPath('organization-personal-workspace.png'),fullPage:true});
});
