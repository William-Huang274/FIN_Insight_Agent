import {test,expect,type Page} from './identity-fixture';
const a='10000000-0000-4000-8000-000000000001',b='20000000-0000-4000-8000-000000000002';
async function fixture(page:Page){
  let index={revision:1,projects:[{id:a,name:'AI 基础设施',description:'资本开支研究',archived:false},{id:b,name:'财务披露阅读',description:'整理公司原文',archived:false}],assignments:{},pinned:[]};
  const version=(project:string,name:string,id:string)=>({ref:{project_id:project,kind:'document',asset_id:id,version_id:id,digest:'a'.repeat(64)},title:name,sequence:1,created_at:'2026-09-23T01:00:00Z',access_status:'active',status:'complete',role:'document'});
  const rows=[{project_id:a,project_name:'AI 基础设施',asset_id:'UPLOAD::a',kind:'document',version_count:1,current:version(a,'AI 资本开支资料.md','UPLOAD::a')},{project_id:b,project_name:'财务披露阅读',asset_id:'UPLOAD::b',kind:'document',version_count:1,current:version(b,'MSFT 披露原文.md','UPLOAD::b')}];
  const calls:string[]=[];
  await page.route('**/api/v1/**',async route=>{
    const r=route.request(),u=new URL(r.url());calls.push(`${r.method()} ${u.pathname}`);let body:unknown={};
    if(u.pathname==='/api/v1/projects'){if(r.method()==='PUT')index={...r.postDataJSON(),revision:index.revision+1};body=index;}
    else if(u.pathname==='/api/v1/business/config')body={enabled:false};
    else if(u.pathname==='/api/v1/research-sessions')body=[];
    else if(u.pathname==='/api/v1/asset-workspace/catalog')body={items:rows.filter(x=>(!u.searchParams.get('project_id')||x.project_id===u.searchParams.get('project_id'))&&x.current.title.includes(u.searchParams.get('query')||'')&&(!u.searchParams.get('role')||x.current.role===u.searchParams.get('role'))),next_offset:null};
    else if(u.pathname.startsWith('/api/v1/asset-workspace/projects/'))body={items:rows.filter(x=>u.pathname.endsWith(x.project_id)).map(x=>({...x,versions:[x.current]}))};
    else if(u.pathname==='/api/v1/asset-workspace/profile')body={version:0,body:''};
    else if(u.pathname==='/api/v1/asset-workspace/read'){const row=rows.find(x=>x.current.ref.version_id===r.postDataJSON().version_id)!;body={version:row.current,editable:true,text:'保存的合成披露原文，不调用模型。',truncated:false};}
    else if(u.pathname.endsWith('/storage'))body={versions:1,original_bytes:30,max_versions:2000,max_original_bytes:2000000000};
    else throw Error('Unexpected request '+u.pathname);
    await route.fulfill({json:body});
  });return calls;
}
for(const width of [1440,390])test(`project navigation and filtered catalogue return at ${width}`,async({page},info)=>{
  await page.setViewportSize({width,height:960});const calls=await fixture(page);
  await page.goto('/workspace');await expect(page).toHaveURL(/\/workspace\/projects$/);await page.getByRole('link',{name:'AI 基础设施',exact:true}).last().click();
  await expect(page.getByRole('heading',{name:'AI 基础设施',exact:true})).toBeVisible();
  await expect(page.getByText('AI 资本开支资料.md',{exact:true})).toBeVisible();
  await expect(page.getByText(a,{exact:true})).toHaveCount(0);
  await page.screenshot({path:info.outputPath(`project-overview-${width}.png`),fullPage:true});
  await page.getByRole('navigation',{name:'项目导航'}).getByRole('link',{name:'资料',exact:true}).click();
  await page.getByRole('link',{name:'在全局资料库中查看'}).click();
  const picker=page.getByRole('combobox',{name:'按项目筛选资料'});
  await expect(picker).toHaveValue(a);await expect(page.getByText('MSFT 披露原文.md',{exact:true})).toHaveCount(0);
  await picker.selectOption(b);await expect(page.getByText('MSFT 披露原文.md',{exact:true})).toBeVisible();await expect(page.getByText('AI 资本开支资料.md',{exact:true})).toHaveCount(0);
  await page.getByLabel('搜索资料名称').fill('MSFT');await page.getByRole('button',{name:'搜索',exact:true}).click();
  await page.getByRole('link').filter({hasText:'MSFT 披露原文.md'}).click();
  await expect(page.getByRole('heading',{name:'MSFT 披露原文.md',exact:true})).toBeVisible();
  await page.getByRole('button',{name:'返回资料库',exact:true}).click();
  await expect(picker).toHaveValue(b);await expect(page.getByLabel('搜索资料名称')).toHaveValue('MSFT');
  await page.reload();await expect(picker).toHaveValue(b);await expect(page.getByText('MSFT 披露原文.md',{exact:true})).toBeVisible();
  await page.screenshot({path:info.outputPath(`library-filter-${width}.png`),fullPage:true});
  await page.getByRole('button',{name:'清除筛选'}).click();await expect(picker).toHaveValue('');await expect(page.getByText('AI 资本开支资料.md',{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  expect(calls.some(c=>/\/(start|runs|contexts)$/.test(c))).toBe(false);
});
test('project create edit archive and restore survive reload without Java',async({page})=>{
  await fixture(page);await page.goto('/workspace/projects');await page.getByRole('button',{name:'新建项目',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'新建项目'});await dialog.getByLabel('项目名称').fill('消费行业');await dialog.getByLabel('项目说明').fill('需求和库存');await dialog.getByRole('button',{name:'创建项目'}).click();
  await expect(page.getByRole('heading',{name:'消费行业',exact:true})).toBeVisible();
  await page.getByRole('navigation',{name:'项目导航'}).getByRole('link',{name:'项目管理'}).click();
  await page.getByRole('textbox',{name:'项目说明',exact:true}).fill('需求、库存与现金流');await page.getByRole('button',{name:'保存修改'}).click();await expect(page.getByText('项目设置已保存。')).toBeVisible();
  await page.reload();await expect(page.getByRole('textbox',{name:'项目说明',exact:true})).toHaveValue('需求、库存与现金流');
  await page.getByRole('button',{name:'归档项目',exact:true}).click();await expect(page.getByRole('button',{name:'恢复项目'})).toBeVisible();
  await page.getByRole('navigation',{name:'工作空间导航'}).getByRole('link',{name:'所有项目'}).click();
  await expect(page.getByRole('link',{name:'消费行业',exact:true})).toHaveCount(0);
  await page.getByLabel('项目状态').selectOption('archived');await page.getByRole('link',{name:'消费行业',exact:true}).click();
  await page.getByRole('navigation',{name:'项目导航'}).getByRole('link',{name:'项目管理'}).click();await page.getByRole('button',{name:'恢复项目'}).click();await expect(page.getByRole('button',{name:'归档项目',exact:true})).toBeVisible();
});
