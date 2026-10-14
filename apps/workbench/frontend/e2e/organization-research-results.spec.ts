import {test,expect} from './identity-fixture';
import {writeFile} from 'node:fs/promises';
const project='20000000-0000-4000-8000-000000000002',execution='30000000-0000-4000-8000-000000000003';
for(const width of [1440,390])test(`organization results read and revoked source clear at ${width}`,async({page},info)=>{
  let revoked=false;const calls:string[]=[];
  await page.setViewportSize({width,height:960});
  await page.route('**/api/v1/**',async route=>{
    const r=route.request(),u=new URL(r.url());calls.push(r.method()+' '+u.pathname);
    expect(r.method()).toBe('GET');let result:any={};
    if(u.pathname==='/api/v1/business/config')result={enabled:true,organization_projects:true};
    else if(u.pathname==='/api/v1/projects')result={revision:0,projects:[],assignments:{},pinned:[]};
    else if(u.pathname==='/api/v1/research-sessions')result=[];
    else if(u.pathname===`/api/v1/business/workspaces/projects/${project}`)result={id:project,organization_id:'org',organization_name:'静态团队',name:'AI 基础设施',role:'viewer',can_manage:false,archived:false};
    else if(u.pathname.endsWith('/members'))result=[];
    else if(u.pathname.endsWith('/control'))result={can_operate:false};
    else if(u.pathname===`/api/v1/organization-projects/${project}/research`)result={items:[{execution_id:execution,draft_id:'draft',title:'固定资料研究',run_id:'run'}],next_offset:null};
    else if(u.pathname===`/api/v1/organization-projects/${project}/research/${execution}`)result={title:'固定资料研究',phase:'ready_for_human_review',read_only:true,
      research_orientation:{overview:'已保存的预研究概览',findings:[{finding_id:'F1',judgment:'存在一份固定资料',unresolved:'仍需核对财务含义'}]},
      report:{title:'合成报告',narrative_markdown:'这是用于权限验收的合成正文。',citations:{C1:{sources:[{source_id:'ORG:S1'}]}}}};
    else if(u.pathname.endsWith('/source')){
      if(revoked){await route.fulfill({status:404,json:{detail:'资料当前不可访问'}});return;}
      result={source_id:'ORG:S1',text:'固定引用片段',period:'FY2025',unit:'USD',next_offset:null};
    }else throw Error('Unexpected API '+u.pathname);
    await route.fulfill({json:result});
  });
  await page.goto(`/workspace/projects?scope=organization&project=${project}&view=results`);
  await page.getByRole('button',{name:/固定资料研究/}).click();
  await expect(page.getByRole('heading',{name:'合成报告',exact:true})).toBeVisible();
  await expect(page.getByText('预研究供确定方向，不表示正式研究完成或结论通过审批。')).toBeVisible();
  const exports=page.getByRole('navigation',{name:'组织报告导出'});
  await expect(exports.getByRole('link',{name:'Word',exact:true})).toHaveAttribute('href',`/api/v1/organization-projects/${project}/research/${execution}/report/export/docx`);
  await page.getByRole('button',{name:'查看引用 ORG:S1'}).click();await expect(page.getByText('固定引用片段',{exact:true})).toBeVisible();
  await page.screenshot({path:info.outputPath(`organization-results-${width}.png`),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  revoked=true;await page.getByRole('button',{name:'查看引用 ORG:S1'}).click();
  await expect(page.getByRole('alert')).toContainText('资料当前不可访问');
  await expect(page.getByRole('heading',{name:'合成报告',exact:true})).toHaveCount(0);
  await expect(page.getByText('固定引用片段',{exact:true})).toHaveCount(0);
  expect(calls.some(p=>p.includes(`/research-sessions/${execution}`))).toBe(false);
  await expect(page.getByRole('button',{name:/启动|接续/})).toHaveCount(0);
});

for(const width of [1440,390])test(`organization browser start unknown reconcile and confirm at ${width}`,async({page},info)=>{
  let stage='prepared',starts=0,continues=0,revoked=false;
  const writes:string[]=[],run='40000000-0000-4000-8000-000000000004';
  const preview={previous_run_id:run,checkpoint_id:'50000000-0000-4000-8000-000000000005',state_digest:'sha256:'+'a'.repeat(64)};
  await page.setViewportSize({width,height:1000});
  await page.route('**/api/v1/**',async route=>{
    const r=route.request(),p=new URL(r.url()).pathname;let result:any={};
    if(r.method()==='POST')writes.push(p);
    if(p==='/api/v1/business/config')result={organization_projects:true};
    else if(p==='/api/v1/projects')result={revision:0,projects:[],assignments:{},pinned:[]};
    else if(p==='/api/v1/research-sessions')result=[];
    else if(p===`/api/v1/business/workspaces/projects/${project}`)result={id:project,organization_id:'org',organization_name:'产业研究组',name:'AI 基础设施',role:'researcher',can_manage:false,archived:false};
    else if(p.endsWith('/members'))result=[];
    else if(p===`/api/v1/organization-projects/${project}/research`)result={items:[{execution_id:execution,title:'算力扩张能否带来持续现金流？',run_id:stage==='prepared'?null:run}],next_offset:null};
    else if(p.endsWith('/control'))result={can_operate:true,enabled:true,preparation:'received',start:stage==='prepared'?'absent':stage==='unknown'?'unknown':'received',continuation:stage==='full'?'received':'absent'};
    else if(p.endsWith('/start')&&!p.includes('/reconcile/')){starts++;stage='unknown';result={status:'unknown'};}
    else if(p.endsWith('/reconcile/start')){stage='orientation';result={status:'received',run_id:run};}
    else if(p.endsWith('/continuation-preview'))result=preview;
    else if(p.endsWith('/continue')){expect(r.postDataJSON()).toEqual(preview);continues++;stage='full';result={status:'received'};}
    else if(p.endsWith('/events')){await route.fulfill({contentType:'text/event-stream',body:'id: 1-0\nevent: custom\ndata: {"actor":"研究负责人","objective":"资料核对已完成"}\n\n'});return;}
    else if(p===`/api/v1/organization-projects/${project}/research/${execution}`){
      if(revoked){await route.fulfill({status:404,json:{detail:'资料访问权限已撤销'}});return;}
      result={title:'算力扩张能否带来持续现金流？',run_id:stage==='orientation'||stage==='full'?run:null,status:'idle',phase:stage==='full'?'research_needs_attention':stage==='orientation'?'research_orientation_submitted':undefined,
        research_orientation:stage==='orientation'||stage==='full'?{overview:'从资本开支、产能兑现与经营现金流三个维度，核对本轮基础设施投入的回报路径。当前结论基于项目固定资料，仍需补齐业务与财务证据。',findings:[
          {finding_id:'F1',judgment:'资本开支增长需要与实际投产节奏对齐，不能将签约容量直接计为已交付产能。',unresolved:'补充季度投产进度与可比口径。'},
          {finding_id:'F2',judgment:'现金流覆盖能力应结合租赁承诺和采购义务一起判断。',unresolved:'核对合同承诺与现金支出期间。'}]}:undefined};
    }else throw Error('Unexpected '+p);
    await route.fulfill({json:result});
  });
  await page.goto(`/workspace/projects?scope=organization&project=${project}&view=research&execution=${execution}`);
  if(width===390){const menu=page.getByRole('button',{name:'展开或收起工作空间导航'});await expect(menu).toHaveAttribute('aria-expanded','false');await menu.click();await expect(page.getByRole('navigation',{name:'工作空间导航'})).toBeVisible();await menu.click();await expect(page.getByRole('navigation',{name:'工作空间导航'})).toBeHidden();}
  await page.getByRole('button',{name:'开始预研究',exact:true}).click();
  await expect(page.getByRole('button',{name:'核对首次启动结果',exact:true})).toBeVisible();expect(starts).toBe(1);
  await page.reload();await expect(page.getByRole('button',{name:'核对首次启动结果',exact:true})).toBeVisible();expect(starts).toBe(1);
  await page.getByRole('button',{name:'核对首次启动结果',exact:true}).click();
  await expect(page.getByRole('heading',{name:'预研究判断',exact:true})).toBeVisible();
  await page.screenshot({path:info.outputPath(`organization-workspace-${width}.png`),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  const cdp=await page.context().newCDPSession(page);await cdp.send('DOM.enable');await cdp.send('CSS.enable');
  const {root}=await cdp.send('DOM.getDocument');const {nodeId}=await cdp.send('DOM.querySelector',{nodeId:root.nodeId,selector:'.org-orientation p'});
  await writeFile(info.outputPath('rendered-fonts.json'),JSON.stringify(await cdp.send('CSS.getPlatformFontsForNode',{nodeId})));await cdp.detach();
  await page.getByText('运行动态',{exact:false}).filter({has:page.locator('span')}).first().click();
  await expect(page.getByText('研究负责人 · 资料核对已完成',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'准备正式研究',exact:true}).click();expect(continues).toBe(0);
  await page.getByRole('button',{name:'暂不开始',exact:true}).click();expect(continues).toBe(0);
  await page.getByRole('button',{name:'准备正式研究',exact:true}).click();
  await page.getByRole('button',{name:'确认接续研究',exact:true}).click();
  await expect(page.getByText('正式研究已受理。可查看运行动态与保存内容；刷新不会重复执行。')).toBeVisible();
  await page.reload();await expect(page.getByText('正式研究已受理。可查看运行动态与保存内容；刷新不会重复执行。')).toBeVisible();
  expect(starts).toBe(1);expect(continues).toBe(1);expect(writes).toHaveLength(3);
  if(width===1440){await page.evaluate(()=>localStorage.setItem('finsight.theme','dark'));await page.reload();await expect(page.locator('.pw-shell')).toHaveAttribute('data-theme','dark');await expect(page.getByText('正式研究已受理。可查看运行动态与保存内容；刷新不会重复执行。')).toBeVisible();await page.screenshot({path:info.outputPath('organization-workspace-dark.png'),fullPage:true});}
  revoked=true;await page.getByRole('button',{name:'刷新研究记录',exact:true}).click();
  await expect(page.getByRole('alert')).toContainText('撤销');
  await expect(page.getByRole('heading',{name:'预研究判断',exact:true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'确认接续研究',exact:true})).toHaveCount(0);
});
