// Real HTTP/browser acceptance. Optional loss of a real reply; no fabricated data.
import {chromium,expect} from 'playwright/test';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const origin=process.env.FIN_METRIC_BROWSER_ORIGIN,endpoint=new URL(origin);
if(process.env.FIN_METRIC_BROWSER_QUALIFICATION!=='1'||endpoint.hostname!=='127.0.0.1'||['18165','18765'].includes(endpoint.port))throw Error('isolated_browser_required');
const spec=JSON.parse(await readFile(process.env.FIN_STRUCTURED_SQL_CASES,'utf8'));
const output=resolve(process.env.FIN_METRIC_BROWSER_OUTPUT);
await mkdir(output,{recursive:false});
const browser=await chromium.launch({headless:true});
const context=await browser.newContext({baseURL:origin,viewport:{width:1440,height:1000},
  extraHTTPHeaders:{Authorization:'Bearer qualification-alice','X-Workbench-Request':'1'}});
// Only block outbound traffic; no service response is fabricated.
await context.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
const page=await context.newPage(),requests=[],errors=[],results=[],drafts=[],recoveries=[];
page.setDefaultTimeout(45000);
page.on('pageerror',e=>errors.push(String(e)));
page.on('request',r=>{if(new URL(r.url()).pathname.startsWith('/api/'))requests.push({method:r.method(),path:new URL(r.url()).pathname});});
try{
  for(const [index,c] of spec.cases.entries()){
    const row=c.snapshot.rows[c.entity_id==='COMPANY::meta'?2:0];
    await page.goto(`/workspace/assets?view=financial-data&company=${encodeURIComponent(c.entity_id)}`);
    await page.getByRole('navigation',{name:'数据层级目录'}).getByRole('button',{name:/指标分析/}).click();
    await page.getByLabel('搜索指标总览').fill(row.label);
    const pending=page.waitForResponse(r=>r.url().endsWith('/metrics/query')&&r.request().postDataJSON()?.section==='card');
    await page.locator('.mw-overview-grid button').filter({hasText:row.label}).first().click();
    const card=await (await pending).json();
    expect(card.items[0].id).toBe(row.id);
    expect(card.items).toEqual([row]);
    await page.getByRole('button',{name:'保存此数据卡到项目',exact:true}).click();
    await page.getByLabel('来源目标项目').selectOption(process.env.FIN_METRIC_PRIVATE_PROJECT);
    const title=`Historical card ${index+1} ${row.company_name}`;
    await page.getByLabel('来源资产名称').fill(title);
    await page.getByLabel('来源批注').fill('历史案例工程验收；不代表新的金融结论。');
    const savedResponse=page.waitForResponse(r=>r.url().endsWith('/asset-workspace/captures')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'保存到项目',exact:true}).click();
    const saved=await (await savedResponse).json();
    await page.getByRole('link',{name:'打开已保存资产 →',exact:true}).click();
    await expect(page.getByRole('region',{name:'已保存指标数据卡'})).toContainText(row.value??row.text_value);
    await page.reload();
    await expect(page.getByRole('region',{name:'已保存指标数据卡'})).toContainText(row.period_label);
    await page.getByRole('button',{name:'发布到组织空间',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'发布资料到组织空间'});
    await dialog.getByLabel('本页资料').selectOption(saved.document_id);
    await dialog.getByLabel('目标空间').selectOption(process.env.FIN_METRIC_SPACE);
    await dialog.getByRole('checkbox').check();
    let persisted=null;
    const loseReply=index===0&&process.env.FIN_METRIC_PUBLICATION_REPLY_LOSS==='1';
    if(loseReply)await page.route('**/api/v1/asset-workspace/spaces/publish',async route=>{
      // Commit through the real service, then suppress only the browser reply.
      const response=await route.fetch({maxRetries:0});
      expect(response.status()).toBe(200);
      persisted=await response.json();
      await route.abort('failed');
    },{times:1});
    await dialog.getByRole('button',{name:'确认发布此版本',exact:true}).click();
    if(loseReply){
      await expect(dialog.getByRole('alert')).toBeVisible();
      expect(persisted).not.toBeNull();
      const posts=()=>requests.filter(r=>r.path.endsWith('/spaces/publish')&&r.method==='POST').length;
      expect(posts()).toBe(1);
      await page.reload();
      await page.getByRole('button',{name:'发布到组织空间',exact:true}).click();
      await expect(dialog.getByRole('region',{name:'待核对的发布'})).toBeVisible();
      await page.screenshot({path:resolve(output,'publication-recovery-1440.png'),fullPage:true});
      await page.setViewportSize({width:390,height:844});
      await page.screenshot({path:resolve(output,'publication-recovery-390.png'),fullPage:true});
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
      await page.setViewportSize({width:1440,height:1000});
      await dialog.getByRole('button',{name:'查询发布结果',exact:true}).click();
      await expect(dialog.getByRole('link',{name:'打开空间中的资料'})).toHaveAttribute('href',new RegExp(`resource=${persisted.id}`));
      expect(posts()).toBe(1);
      recoveries.push({resource_id:persisted.id,reply_lost_after_real_commit:true,reload_preserved:true,query_without_resubmit:true});
    }
    const published=dialog.getByRole('link',{name:'打开空间中的资料'});
    await expect(published).toBeVisible();
    const resource=new URL(await published.getAttribute('href'),origin).searchParams.get('resource');
    await published.click();
    await expect(page.getByRole('region',{name:'已保存指标数据卡'})).toContainText(row.value??row.text_value);
    await page.goto(`/workspace/projects?scope=organization&project=${process.env.FIN_METRIC_TEAM_PROJECT}&view=files`);
    await page.getByText('关联团队资料',{exact:true}).click();
    await page.getByLabel('关联来源空间').selectOption(process.env.FIN_METRIC_SPACE);
    await page.locator('.pw-row').filter({hasText:title}).getByRole('button',{name:'关联到项目',exact:true}).click();
    await page.getByRole('button',{name:title+'.md',exact:true}).click();
    await expect(page.getByRole('region',{name:'已保存指标数据卡'})).toContainText(row.unit);
    await page.screenshot({path:resolve(output,`card-${index+1}-1440.png`),fullPage:true});
    if(index===2){
      await page.getByText('计算输入与公式',{exact:true}).click();
      await expect(page.getByRole('region',{name:'已保存指标数据卡'})).toContainText(row.inputs[0].value);
      await page.setViewportSize({width:390,height:844});
      await page.screenshot({path:resolve(output,'calculation-390.png'),fullPage:true});
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
      await page.setViewportSize({width:1440,height:1000});
    }
    results.push({entity_id:c.entity_id,record_id:row.id,document_id:saved.document_id,resource_id:resource,card_digest:card.capture_selection.snapshot});
  }
  // Save immutable business inputs, then explicitly verify originals. No native
  // thread is created: even the valid draft stops before "prepare execution".
  let original=null;
  for(const [label,cutoff,status] of [['early','2020-01-01',409],['valid',spec.as_of,200]]){
    if(label==='early'){
      await page.goto(`/workspace/projects?scope=organization&project=${process.env.FIN_METRIC_TEAM_PROJECT}&view=research`);
      await page.getByRole('textbox',{name:'研究问题',exact:true}).fill('核对已选历史指标的公司、期间、来源及计算输入，不生成研究结论。');
      const choices=page.getByRole('checkbox');
      await expect(choices).toHaveCount(4);
      for(const choice of await choices.all())await choice.check();
    }else{
      // An invalid cutoff clears the stale detail. Refresh authorizes the old
      // record again, then copy must re-read it without creating anything.
      await page.getByRole('button',{name:'刷新准备单',exact:true}).click();
      await expect(page.getByRole('heading',{name:'Historical metrics early',exact:true})).toBeVisible();
      const writes=()=>requests.filter(r=>r.path.endsWith('/research-drafts')&&r.method==='POST').length;
      const before=writes();
      await page.getByRole('button',{name:'复制为新准备单',exact:true}).click();
      await expect(page.getByRole('textbox',{name:'研究问题',exact:true})).toHaveValue(original.question);
      await expect(page.getByLabel('研究截止日期',{exact:true})).toHaveValue('2020-01-01');
      for(const choice of await page.getByRole('checkbox').all())await expect(choice).toBeChecked();
      expect(writes()).toBe(before);
      await page.setViewportSize({width:390,height:844});
      await page.screenshot({path:resolve(output,'copy-preparation-390.png'),fullPage:true});
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
      await page.setViewportSize({width:1440,height:1000});
    }
    await page.getByLabel('准备单标题',{exact:true}).fill(`Historical metrics ${label}`);
    await page.getByLabel('研究截止日期',{exact:true}).fill(cutoff);
    const saving=page.waitForResponse(r=>/\/research-drafts$/.test(new URL(r.url()).pathname)&&r.request().method()==='POST');
    await page.getByRole('button',{name:'保存输入准备单',exact:true}).click();
    const response=await saving;expect(response.status()).toBe(200);
    const draft=await response.json();
    expect(draft.manifest.inputs.map(i=>i.resource_id).sort()).toEqual(results.map(i=>i.resource_id).sort());
    if(label==='early')original=draft;
    else{
      expect(draft.id).not.toBe(original.id);
      expect(draft.manifest.inputs).toEqual(original.manifest.inputs);
      const old=await context.request.get(`/api/v1/business/workspaces/projects/${process.env.FIN_METRIC_TEAM_PROJECT}/research-drafts/${original.id}`);
      expect(old.status()).toBe(200);
      expect(await old.json()).toEqual(original);
    }
    const verifying=page.waitForResponse(r=>r.url().endsWith(`/research-drafts/${draft.id}/verify`));
    await page.getByRole('button',{name:'重新校验权限与原件',exact:true}).click();
    expect((await verifying).status()).toBe(status);
    if(label==='early')await expect(page.getByRole('alert')).toContainText('可获知日');
    else{
      await expect(page.getByRole('status')).toContainText('校验通过');
      await page.reload();
      await expect(page.getByRole('heading',{name:`Historical metrics ${label}`,exact:true})).toBeVisible();
      await page.screenshot({path:resolve(output,'research-inputs-1440.png'),fullPage:true});
    }
    drafts.push({id:draft.id,manifest_digest:draft.manifest_digest,research_as_of:cutoff,verification_status:status,
      ...(label==='valid'?{copied_from:original.id,original_unchanged:true,fixed_inputs_unchanged:true}:{})});
  }
  expect(errors).toEqual([]);
  expect(requests.filter(r=>/\/(runs|start|continue)$/.test(r.path))).toEqual([]);
  await writeFile(resolve(output,'result.json'),JSON.stringify({results,drafts,recoveries,requests,page_errors:errors,provider_calls:0,response_mocks:0},null,2));
}finally{
  await writeFile(resolve(output,'observations.json'),JSON.stringify({results,requests,page_errors:errors},null,2));
  await page.screenshot({path:resolve(output,'last-page.png'),fullPage:true}).catch(()=>{});
  await browser.close();
}
