import {test,expect,type Page} from './identity-fixture';
const org='10000000-0000-4000-8000-000000000001',project='20000000-0000-4000-8000-000000000002';
async function fixture(page:Page,manager=true){
  let p={id:project,organization_id:org,organization_name:'合成研究团队',name:'AI 基础设施',description:'静态案例：项目归属与成员管理',archived:false,revision:1,can_manage:manager,role:manager?'manager':'viewer',research_enabled:false};
  let members=[{subject:'alice',display_name:'小王',role:'manager',organization_admin:true},{subject:'bob',display_name:'小李',role:'viewer',organization_admin:false}];
  const state={conflict:false,denied:false,created:[] as any[],writes:[] as string[],dropCreate:false};
  await page.route('**/api/v1/**',async route=>{
    const r=route.request(),u=new URL(r.url()),b=r.postData()?r.postDataJSON():null;let result:any={};
    if(r.method()!=='GET')state.writes.push(u.pathname);
    if(u.pathname==='/api/v1/business/config')result={enabled:true,organization_projects:true,resource_spaces:true,team_collaboration:false};
    else if(u.pathname==='/api/v1/projects')result={revision:0,projects:[],assignments:{},pinned:[]};
    else if(u.pathname==='/api/v1/research-sessions')result=[];
    else if(u.pathname==='/api/v1/business/workspaces')result={spaces:[],organizations:[{id:org,name:p.organization_name,role:manager?'admin':'member'}]};
    else if(u.pathname===`/api/v1/business/workspaces/organizations/${org}/members`)result=[{subject:'alice',display_name:'小王',role:'admin',active:true},{subject:'bob',display_name:'小李',role:'member',active:true}];
    else if(u.pathname==='/api/v1/business/workspaces/projects'){
      if(r.method()==='POST'){state.created.push(b);if(state.dropCreate&&state.created.length===1){await route.fulfill({status:503,json:{detail:'响应丢失，请核对原项目'}});return;}p={...p,...b};result=p;}
      else result={items:state.denied||String(p.archived)!==(u.searchParams.get('archived')||'false')||!p.name.includes(u.searchParams.get('query')||'')?[]:[p],next_offset:null};
    }
    else if(u.pathname===`/api/v1/business/workspaces/projects/${p.id}`||u.pathname===`/api/v1/business/workspaces/projects/${p.id}/members`){
      if(state.denied){await route.fulfill({status:404,json:{detail:'项目不可访问'}});return;}
      if(r.method()==='POST'){
        if(!manager){await route.fulfill({status:403,json:{detail:'需要项目管理权限'}});return;}
        if(state.conflict){state.conflict=false;p={...p,name:'同事修改后的项目',revision:p.revision+1};await route.fulfill({status:409,json:{detail:'项目已更新，请重新读取后再修改'}});return;}
        if(b.revision!==p.revision)throw Error('stale revision submitted');
        p={...p,...(u.pathname.endsWith('/members')?{}:b),revision:p.revision+1};
        if(u.pathname.endsWith('/members'))members=members.filter(m=>m.subject!==b.subject).concat(b.role==='remove'?[]:[{subject:b.subject,display_name:'小李',role:b.role,organization_admin:false}]);
      }
      result=u.pathname.endsWith('/members')?(r.method()==='GET'?members:{id:p.id,revision:p.revision}):p;
    }
    else throw Error('Unexpected request '+r.method()+' '+u.pathname);
    await route.fulfill({json:result});
  });return state;
}
for(const width of [1440,390])test(`organization project member management and conflicts at ${width}`,async({page},info)=>{
  await page.setViewportSize({width,height:960});const state=await fixture(page);
  await page.goto('/workspace/projects');await page.getByRole('link',{name:'AI 基础设施',exact:true}).click();
  await expect(page).toHaveURL(/scope=organization/);
  await page.getByRole('navigation',{name:'项目导航'}).getByRole('link',{name:'项目管理'}).click();
  await page.getByLabel('选择项目成员').selectOption('bob');await page.getByLabel('项目成员角色').selectOption('researcher');await page.getByRole('button',{name:'保存成员权限'}).click();
  await expect(page.locator('.op-members').getByText('研究成员',{exact:true})).toBeVisible();
  state.conflict=true;await page.getByRole('textbox',{name:'项目说明',exact:true}).fill('我修改的说明');await page.getByRole('button',{name:'保存修改'}).click();
  await expect(page.getByRole('alert')).toContainText('项目已更新');
  await page.getByRole('button',{name:'重新读取项目'}).click();await expect(page.getByRole('textbox',{name:'项目名称',exact:true})).toHaveValue('同事修改后的项目');
  await page.screenshot({path:info.outputPath(`organization-project-members-${width}.png`),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  page.on('dialog',d=>d.accept());await page.getByRole('button',{name:'归档项目',exact:true}).click();await expect(page.getByRole('button',{name:'恢复项目'})).toBeVisible();
  await page.reload();await expect(page.getByRole('button',{name:'恢复项目'})).toBeVisible();await page.getByRole('button',{name:'恢复项目'}).click();await expect(page.getByRole('button',{name:'归档项目',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'移出项目',exact:true}).click();await expect(page.getByText('小李',{exact:true})).toHaveCount(0);
  expect(state.writes.some(x=>x==='/api/v1/projects'||/\/(tasks|start|runs|contexts)$/.test(x))).toBe(false);
});
test('viewer cannot edit and revoked access clears project data; no research dispatch',async({page})=>{
  const state=await fixture(page,false);await page.goto(`/workspace/projects?scope=organization&project=${project}&view=settings`);
  await expect(page.getByText('项目信息和成员由项目管理员维护。')).toBeVisible();await expect(page.getByRole('button',{name:'保存修改'})).toHaveCount(0);
  await page.getByRole('navigation',{name:'项目导航'}).getByRole('link',{name:'研究',exact:true}).click();await expect(page.getByText(/此组织项目尚未开放这项功能/)).toBeVisible();
  state.denied=true;await page.getByRole('button',{name:'刷新项目'}).click();await expect(page.getByRole('alert')).toContainText('项目不可访问');await expect(page.getByRole('heading',{name:'AI 基础设施',exact:true})).toHaveCount(0);expect(state.writes).toHaveLength(0);
});
test('create retries reuse identity after unknown response',async({page})=>{
  const state=await fixture(page);state.dropCreate=true;await page.goto('/workspace/projects');await page.getByRole('button',{name:'新建组织项目',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'新建组织项目'});await dialog.getByLabel('组织项目名称').fill('消费研究');await dialog.getByLabel('组织项目说明').fill('创建响应丢失演练');await dialog.getByRole('button',{name:'创建组织项目',exact:true}).click();await expect(dialog.getByRole('alert')).toContainText('响应丢失');
  await dialog.getByRole('button',{name:'创建组织项目',exact:true}).click();await expect(page.getByRole('heading',{name:'消费研究',exact:true})).toBeVisible();expect(state.created).toHaveLength(2);expect(state.created[0]).toEqual(state.created[1]);
});
