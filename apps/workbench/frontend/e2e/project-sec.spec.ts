import {test,expect} from 'playwright/test';
import {writeFile} from 'node:fs/promises';

test('SEC真实连接保存与桌面手机回读',async({page,browser},testInfo)=>{
  const replay=process.env.FIN_SEC_PROJECT_REPLAY==='1';
  test.skip(process.env.FIN_SEC_PROJECT_LIVE!=='1'&&!replay,'Explicit live capture or saved-source replay qualification only');
  test.setTimeout(120000);
  await page.setViewportSize({width:1440,height:1000});
  await page.goto('/workspace/session');
  if(!replay){await page.locator('.fs-sidebar').getByRole('button',{name:'管理项目',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'管理项目'});
  await dialog.getByLabel('新项目名称').fill('微软公开结构化资料');
  await dialog.getByRole('button',{name:'创建项目',exact:true}).click();
  await expect(dialog.getByLabel('新项目名称')).toHaveValue('');
  await dialog.getByLabel('关闭项目管理').click();}
  await page.locator('.fs-sidebar').getByRole('button',{name:'打开项目 微软公开结构化资料',exact:true}).click();
  const section=page.getByLabel('SEC结构化数据',{exact:true});
  if(replay)await page.route('**/api/v1/projects/*/sec',async route=>{
    if(route.request().method()==='POST')throw new Error('Saved-source replay must not fetch SEC again');
    await route.continue();
  });
  let snapshot:any;
  if(!replay){await section.getByLabel('SEC股票代码',{exact:true}).fill('MSFT');
  await section.getByLabel('SEC CIK',{exact:true}).fill('789019');
  const captured=page.waitForResponse(r=>r.url().endsWith('/sec')&&r.request().method()==='POST',{timeout:75000});
  await section.getByRole('button',{name:'连接并保存新版本',exact:true}).click();
  const response=await captured;snapshot=await response.json();
  await writeFile(testInfo.outputPath('sec-capture-response.json'),JSON.stringify(snapshot,null,2));
  expect(response.status()).toBe(200);expect(snapshot.status).toBe('complete');
  expect(snapshot.sources).toHaveLength(2);expect(snapshot.numeric_fact_authority).toBe(false);
  await expect(section.getByRole('status')).toHaveText('已保存新的数据版本。请选择版本和指标查看。');
  }else{
    const project=new URL(page.url()).searchParams.get('project');
    snapshot=(await (await page.request.get(`/api/v1/projects/${project}/sec`)).json()).items[0];
    expect(snapshot.status).toBe('complete');
  }
  await section.getByRole('button',{name:'查看数据版本',exact:true}).click();
  const metric=JSON.stringify(['us-gaap','RevenueFromContractWithCustomerExcludingAssessedTax']);
  await section.getByLabel('SEC原始指标',{exact:true}).selectOption(metric);
  await section.getByLabel('SEC披露截止日期',{exact:true}).fill('2025-08-01');
  await section.getByRole('button',{name:'查询已保存指标',exact:true}).click();
  await expect(section.locator('tbody')).toContainText('281724000000');
  await expect(section.locator('tbody')).toContainText('USD');
  await section.scrollIntoViewIfNeeded();
  await page.screenshot({path:testInfo.outputPath('sec-desktop.png'),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  const url=page.url();const second=await browser.newContext({viewport:{width:390,height:900}});
  try{const phone=await second.newPage();await phone.goto(url);
    const other=phone.getByLabel('SEC结构化数据',{exact:true});
    await expect(other.getByRole('button',{name:'查看数据版本',exact:true})).toHaveCount(1);
    await other.getByRole('button',{name:'查看数据版本',exact:true}).click();
    await other.getByLabel('SEC原始指标',{exact:true}).selectOption(metric);
    await other.getByLabel('SEC披露截止日期',{exact:true}).fill('2025-08-01');
    await other.getByRole('button',{name:'查询已保存指标',exact:true}).click();
    await expect(other.locator('tbody')).toContainText('281724000000');
    await other.scrollIntoViewIfNeeded();await phone.screenshot({path:testInfo.outputPath('sec-phone.png'),fullPage:true});
    expect(await phone.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
    expect(await phone.locator('.fs-project-library').evaluate(el=>el.scrollWidth<=el.clientWidth+1)).toBe(true);
    const download=await phone.request.get(`/api/v1/projects/${new URL(url).searchParams.get('project')}/sec/${snapshot.version}/download/sec_companyfacts`);
    expect(download.status()).toBe(200);expect((await download.json()).cik).toBe(789019);
  }finally{await second.close();}
});
