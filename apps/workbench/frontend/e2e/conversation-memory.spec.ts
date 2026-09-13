import {test,expect} from './identity-fixture';
for(const width of [1440,390]) test(`context directory exact reads, empty region and closing at ${width}`,async({page})=>{
  await page.setViewportSize({width,height:950});
  const tid='00000000-0000-4000-8000-000000000081';
  const snapshot={thread_id:tid,title:'上下文接续验收',status:'idle',messages:[],events:[],runs:[],permissions_notice:'只读',
    context_memory:{regions:{conversation:1},original_message_count:20,projected_message_count:4,summary_count:2,summary_status:'limited',
      summary_text:'只整理 NOVA FY2024，旧计划取消。',notice:'原文独立保存；摘要只是索引。'}};
  await page.route('**/api/v1/conversations**',async route=>{
    const url=new URL(route.request().url());
    expect(route.request().method()).toBe('GET');
    const data=url.pathname.endsWith('/context/read')?{text:'原始用户要求：**只整理 NOVA FY2024**。',total_characters:30,next_offset:null}:
      url.pathname.endsWith('/context')?{items:url.searchParams.get('region')==='conversation'&&!url.searchParams.get('query')?[{key:'original-user',label:'用户消息',preview:'只整理 NOVA FY2024',read_tool:'read_context_turn'}]:[],next_offset:null,total_matches:1}:
      url.pathname.endsWith('/conversations')?[snapshot]:snapshot;
    await route.fulfill({json:data});
  });
  await page.clock.install();
  await page.goto(`/workspace/assistant?thread=${tid}`);
  for(let refresh=0;refresh<3;refresh++) {
    const refreshed=page.waitForResponse(response=>new URL(response.url()).pathname===`/api/v1/conversations/${tid}`);
    await page.clock.runFor(2600);await refreshed;
    await expect(page.getByRole('button',{name:'查看记忆目录',exact:true})).toHaveCount(1);
  }
  await page.getByRole('button',{name:'查看记忆目录',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'记忆目录',exact:true});
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button',{name:/用户消息/}).click();
  await expect(dialog.getByRole('article',{name:'记忆原文'}).getByText('只整理 NOVA FY2024',{exact:true})).toBeVisible();
  await dialog.getByRole('button',{name:/数字与计算/}).click();
  await expect(dialog.getByText(/此分区没有匹配记录/)).toBeVisible();
  await expect(dialog.getByText('原始用户要求：',{exact:false})).not.toBeVisible();
  await dialog.getByLabel('检索记忆目录').fill('没有的记录');
  await expect(dialog.getByText(/此分区没有匹配记录/)).toBeVisible();
  expect(await dialog.evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBeTruthy();
  await page.keyboard.press('Escape');await expect(dialog).not.toBeVisible();
  await page.getByRole('button',{name:'查看记忆目录',exact:true}).click();
  await dialog.getByRole('button',{name:'关闭记忆目录'}).click();await expect(dialog).not.toBeVisible();
});
