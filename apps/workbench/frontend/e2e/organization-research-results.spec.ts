import {test,expect} from './identity-fixture';
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
