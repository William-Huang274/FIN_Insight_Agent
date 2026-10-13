import {test,expect,type Page} from './identity-fixture';
const org='10000000-0000-4000-8000-000000000001',project='20000000-0000-4000-8000-000000000002',space='30000000-0000-4000-8000-000000000003',resource='40000000-0000-4000-8000-000000000004';
const url=`/workspace/projects?scope=organization&project=${project}&view=files`;
async function fixture(page:Page,manager=true){
  let p={id:project,organization_id:org,organization_name:'研究团队',name:'AI 基础设施',description:'投入与回报',revision:1,archived:false,role:manager?'manager':'viewer',can_manage:manager,research_enabled:false};
  const state={linked:false,revoked:false,conflict:false,delayRead:false,releaseRead:()=>{},posts:[] as any[],reads:[] as string[],catalogs:[] as string[]};
  const row={id:resource,space_id:space,space_name:'行业组',title:'资本开支资料.md',resource_type:'files',revision:1};
  const version={ref:{project_id:space,asset_id:'UPLOAD::synthetic',version_id:'UPLOAD::synthetic-v1',digest:'a'.repeat(64),kind:'document'},title:row.title,sequence:1,created_at:'2026-10-13T01:00:00Z',access_status:'active',status:'complete',role:'document'};
  await page.route('**/api/v1/**',async route=>{
    const r=route.request(),u=new URL(r.url()),body=r.postData()?r.postDataJSON():null;let result:any={};
    if(u.pathname==='/api/v1/business/config')result={enabled:true,organization_projects:true,resource_spaces:true,team_collaboration:false};
    else if(u.pathname==='/api/v1/projects')result={revision:0,projects:[],assignments:{},pinned:[]};
    else if(u.pathname==='/api/v1/research-sessions')result=[];
    else if(u.pathname==='/api/v1/business/workspaces')result={organizations:[{id:org,name:'研究团队',role:manager?'admin':'member'}],spaces:[{id:space,organization_id:org,organization_name:'研究团队',name:'行业组',kind:'team',can_manage:manager,organization_admin:manager}]};
    else if(u.pathname===`/api/v1/business/workspaces/projects/${project}`)result=p;
    else if(u.pathname.endsWith('/members'))result=[];
    else if(u.pathname==='/api/v1/business/workspaces/projects')result={items:[p],next_offset:null};
    else if(u.pathname===`/api/v1/business/workspaces/projects/${project}/resources/${resource}`){
      state.posts.push(body);
      if(state.conflict){await route.fulfill({status:409,json:{detail:'项目已更新，请重新读取后再修改'}});return;}
      if(!manager||body.revision!==p.revision)throw Error('invalid synthetic mutation');
      state.linked=body.linked;p={...p,revision:p.revision+1};result={revision:p.revision,linked:state.linked};
    }
    else if(u.pathname===`/api/v1/business/workspaces/projects/${project}/resources`||u.pathname===`/api/v1/business/workspaces/spaces/${space}/resources`){
      state.catalogs.push(u.pathname+u.search);
      const associated=u.pathname.includes('/projects/')||u.searchParams.has('project_id');
      result={items:!state.revoked&&(!associated||state.linked)&&(!u.searchParams.get('type')||u.searchParams.get('type')==='files')?[row]:[],next_offset:null};
    }
    else if(u.pathname===`/api/v1/asset-workspace/organization-projects/${project}/resources/${resource}`){
      state.reads.push(u.pathname);
      if(state.delayRead)await new Promise<void>(resolve=>{state.releaseRead=resolve;});
      if(state.revoked||!state.linked){await route.fulfill({status:404,json:{detail:'项目资料不可访问'}});return;}
      result={version,text:'发布时固定的合成资料正文。',truncated:false,permission_revision:1,publication:{space_id:space}};
    }
    else throw Error('Unexpected request '+r.method()+' '+u.pathname);
    await route.fulfill({json:result});
  });return state;
}
for(const width of [1440,390])test(`project linking and library filter preserve scope at ${width}`,async({page},info)=>{
  await page.setViewportSize({width,height:960});const state=await fixture(page);
  await page.goto(url);await expect(page.getByText('当前没有可读取的关联资料。关联不会额外授予源资料权限。')).toBeVisible();
  await page.getByText('关联团队资料',{exact:true}).click();await page.getByLabel('关联来源空间').selectOption(space);
  await page.getByRole('button',{name:'关联到项目',exact:true}).click();
  await expect(page.getByRole('button',{name:'移除关联',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'资本开支资料.md',exact:true}).click();await expect(page.getByText('发布时固定的合成资料正文。')).toBeVisible();
  await page.screenshot({path:info.outputPath(`project-resources-${width}.png`),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.getByRole('link',{name:'在资料库查看',exact:true}).click();
  await expect(page.getByLabel('按组织项目筛选资料')).toHaveValue(project);
  await page.getByRole('button',{name:'数据库',exact:true}).click();await expect(page).toHaveURL(new RegExp('organization_project='+project));
  await expect(page.getByText(/当前范围内尚无发布资料/)).toBeVisible();
  expect(state.catalogs.at(-1)).toContain('project_id='+project);
  await page.getByRole('button',{name:'文件资料',exact:true}).click();await page.getByRole('button').filter({hasText:'资本开支资料.md'}).click();
  await expect(page.getByText('发布时固定的合成资料正文。')).toBeVisible();
  await page.reload();await expect(page.getByText('发布时固定的合成资料正文。')).toBeVisible();
  expect(state.reads.every(p=>p.includes('/organization-projects/'))).toBe(true);
  await page.goto(url);page.on('dialog',d=>d.accept());await page.getByRole('button',{name:'移除关联',exact:true}).click();
  await expect(page.getByText('当前没有可读取的关联资料。关联不会额外授予源资料权限。')).toBeVisible();
  expect(state.posts.map(b=>b.linked)).toEqual([true,false]);expect(state.posts.map(b=>b.revision)).toEqual([1,2]);
});
test('project reader loses source visibility and content on next request',async({page})=>{
  const state=await fixture(page,false);state.linked=true;await page.goto(url);
  await expect(page.getByText('关联团队资料',{exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'移除关联'})).toHaveCount(0);
  await page.getByRole('button',{name:'资本开支资料.md'}).click();await expect(page.getByText('发布时固定的合成资料正文。')).toBeVisible();
  state.revoked=true;await page.getByRole('button',{name:'资本开支资料.md'}).click();
  await expect(page.getByRole('alert')).toContainText('项目资料不可访问');await expect(page.getByText('发布时固定的合成资料正文。')).toHaveCount(0);
  await expect(page.getByRole('button',{name:'资本开支资料.md'})).toHaveCount(0);expect(state.posts).toHaveLength(0);
});
test('stale link submission is not automatically retried',async({page})=>{
  const state=await fixture(page);state.conflict=true;await page.goto(url);
  await page.getByText('关联团队资料',{exact:true}).click();await page.getByLabel('关联来源空间').selectOption(space);await page.getByRole('button',{name:'关联到项目'}).click();
  await expect(page.getByRole('alert')).toContainText('项目已更新');await expect(page.getByRole('button',{name:'关联到项目'})).toHaveCount(0);
  expect(state.posts).toHaveLength(1);expect(state.linked).toBe(false);
});
test('late content response cannot restore a cleared view after conflicting unlink',async({page})=>{
  const state=await fixture(page);state.linked=true;state.delayRead=true;state.conflict=true;
  await page.goto(url);await page.getByRole('button',{name:'资本开支资料.md'}).click();
  await expect.poll(()=>state.reads.length).toBe(1);
  page.on('dialog',d=>d.accept());await page.getByRole('button',{name:'移除关联'}).click();
  await expect(page.getByRole('alert')).toContainText('项目已更新');
  const response=page.waitForResponse(r=>r.url().includes('/asset-workspace/organization-projects/'));
  state.releaseRead();await response;
  await expect(page.getByText('发布时固定的合成资料正文。')).toHaveCount(0);
});
