import {test,expect} from "playwright/test";
for(const width of [1440,390]) test(`working papers read render and close at ${width}`,async({page})=>{
  await page.setViewportSize({width,height:950});
  const id="00000000-0000-4000-8000-000000000090";
  const snapshot={thread_id:id,title:"底稿验证",status:"idle",messages:[],events:[],runs:[]};
  const revisions:any[]=[];
  await page.route("**/api/v1/conversations**",async route=>{
    const url=new URL(route.request().url());
    let data:any=url.pathname.endsWith("conversations")?[snapshot]:snapshot;
    if(url.pathname.endsWith('/working-notes/revise')){revisions.push(route.request().postDataJSON());data={thread_id:'revision-thread',run_id:'revision-run',notice:'已交给责任角色'};}
    if(url.pathname.endsWith("working-notes")) {
      const version=Number(url.searchParams.get("version")||2);
      data=url.searchParams.has("note_id")?{found:true,id:"note",title:"现金流判断",version,body:version===1?"原来的暂定判断。":"**按用户意见更正**\n\n|年份|CFO|\n|---|---|\n|2025|45|",next_offset:null,is_current:version===2}:
        {enabled:true,items:[{id:"note",title:"现金流判断",actor:"研究员",version:2,preview:"保留同向增长，删除过度推断"}],next_offset:null};
      if(url.searchParams.get("download"))data={markdown:"原来的暂定判断。"};
    }
    await route.fulfill({json:data});
  });
  await page.goto(`/workspace/assistant?thread=${id}`);
  await page.getByRole("button",{name:"工作底稿",exact:true}).click();
  const dialog=page.getByRole("dialog",{name:"工作底稿"});
  await dialog.getByRole("button",{name:/现金流判断/}).click();
  await expect(dialog.locator("strong").filter({hasText:"按用户意见更正"})).toBeVisible();
  await expect(dialog.getByRole("table")).toBeVisible();
  await dialog.getByRole("button",{name:"上一版本"}).click();
  await expect(dialog).toContainText("原来的暂定判断。");
  const download=page.waitForEvent("download");await dialog.getByRole("button",{name:"下载正文"}).click();
  expect((await download).suggestedFilename()).toBe("finsight-working-note.md");
  await dialog.getByRole('button',{name:'最新版本',exact:true}).click();
  await dialog.getByLabel('底稿修改意见').fill('只保留观察，取消因果判断');
  await dialog.getByLabel('修订执行方式').selectOption('hermes');
  await dialog.getByRole('button',{name:'交给责任 Agent 修订'}).click();
  await expect(dialog.getByRole('link',{name:/查看本次修订/})).toHaveAttribute('href','/workspace/assistant?thread=revision-thread');
  expect(revisions[0]).toMatchObject({note_id:'note',version:2,instruction:'只保留观察，取消因果判断',harness:'hermes'});
  await page.keyboard.press("Escape");await expect(dialog).toBeHidden();
  await page.getByRole("button",{name:"工作底稿",exact:true}).click();
  await dialog.getByLabel("关闭工作底稿").click();await expect(dialog).toBeHidden();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
