import {test,expect} from 'playwright/test';
for(const width of [1440,390])test(`human edits and completed workspace ${width}`,async({page})=>{
  await page.setViewportSize({width,height:1000});
  const id='00000000-0000-4000-8000-000000000097';let edits:any[]=[];
  let report={title:'测试研究',narrative_markdown:'原观察 [P01:C1]',citations:{},charts:[]};let phase='needs_revision';
  const snapshot=()=>({thread_id:id,status:'interrupted',phase,report,report_version:edits.length+1,human_edits:edits,human_edit_count:edits.length,can_manual_complete:true,can_respond:true,conversation:[],runs:[],report_review:{summary:'观察需要调整',findings:[],unresolved_data_requests:[]}});
  await page.route('**/api/v1/**',async route=>{
    const url=new URL(route.request().url());let data:any={};
    if(url.pathname.endsWith('/research-sessions'))data=[{...snapshot(),title:report.title}];
    else if(url.pathname.endsWith('/manual-review'))data={base_version:1,report_markdown:report.narrative_markdown,papers:[{paper_id:'P01',branch_id:'Q1_ISSUER_TRUTH',thesis:'现金观察',body:'原底稿'}],review:snapshot().report_review};
    else if(url.pathname.endsWith('/actions')){const body=route.request().postDataJSON();expect(body.action).toBe('manual_complete');const d=body.manual_review;expect(d.confirmed).toBe(true);edits=[{number:1,owner:'local-pilot',recorded_at:new Date().toISOString(),reason:d.reason,base_version:1,report_before:report.narrative_markdown,report_after:d.report_markdown,papers:[{paper_id:'P01',actor:'Q1_ISSUER_TRUTH',title:'现金观察',before:'原底稿',after:d.paper_edits[0].body}]}];report={...report,narrative_markdown:d.report_markdown};phase='human_completed';data={run_id:'manual',status:'pending'};}
    else if(url.pathname.endsWith('/'+id))data=snapshot();
    else if(url.pathname.endsWith('/report-versions'))data={versions:[]};
    await route.fulfill({json:data});
  });
  await page.goto(`/workspace/session?thread=${id}&view=report`);
  await page.getByRole('button',{name:'人工修改与确认',exact:true}).click();const dlg=page.getByRole('dialog',{name:'人工修改与确认'});
  await dlg.getByText('收入、利润与现金 — 现金观察',{exact:true}).click();await dlg.getByLabel('修改底稿 P01').fill('只描述观察，不作归因。');
  await dlg.getByLabel('人工修改报告正文').fill('改后观察 [P01:C1]');await dlg.getByLabel('人工修改说明').fill('去除过度归因');await dlg.getByRole('checkbox').check();
  await dlg.getByRole('button',{name:'保存修改并确认完成'}).click();await expect(dlg).not.toBeVisible();
  await page.getByText('人工修改 1 次 · 查看角色与底稿',{exact:true}).click();await page.locator('.fs-human-history').getByText('收入、利润与现金 — 现金观察',{exact:true}).click();await expect(page.locator('.fs-human-history').getByText('只描述观察，不作归因。',{exact:true}).first()).toBeVisible();
  if(width===390)await page.getByRole('button',{name:'打开导航',exact:true}).click();
  const nav=page.getByRole('navigation',{name:width===390?'移动工作区导航':'工作区导航',exact:true});await nav.getByRole('button',{name:'已完成研究',exact:true}).click();await expect(page.getByRole('heading',{name:'已完成研究',exact:true})).toBeVisible();await expect(page.locator('.fs-research-list>button')).toHaveCount(1);
});
