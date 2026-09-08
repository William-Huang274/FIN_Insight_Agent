import { test, expect } from "playwright/test";
for (const width of [1440, 1024, 390]) test(`general conversation persists and selects controls at ${width}`, async ({page}) => {
  await page.setViewportSize({width,height:950});
  const id="00000000-0000-4000-8000-000000000090";
  const snapshot:any = {thread_id:id,title:"HTTP 缓存说明",status:"idle",messages:[{id:"a",role:"assistant",content:"**可继续的回答**\n\n缓存可以复用来源。"}],events:[],runs:[],permissions_notice:"只读工具；不授权修改用户原文件。"};
  const writes:any[]=[];
  await page.route("**/api/v1/conversations**",async route=>{
    if(route.request().method()==="POST"){const body=route.request().postDataJSON(); writes.push(body);snapshot.messages.push({id:"u",role:"user",content:body.message}); await route.fulfill({json:{thread_id:id,run_id:"run"}});return;}
    await route.fulfill({json:new URL(route.request().url()).pathname.endsWith("conversations")?[snapshot]:snapshot});
  });
  await page.goto("/workspace/assistant");
  await page.getByLabel("发送消息",{exact:true}).fill("改成给同事的三条说明");
  await page.getByRole("combobox",{name:"模型",exact:true}).selectOption("deepseek-v4-pro");
  await page.getByRole("combobox",{name:"权限",exact:true}).selectOption("approve_for_me");
  await page.getByRole("button",{name:"发送",exact:true}).click();
  await expect(page).toHaveURL(new RegExp(id));
  await expect(page.getByText("可继续的回答",{exact:true})).toBeVisible();
  expect(writes).toEqual([{message:"改成给同事的三条说明",model:"deepseek-v4-pro",permission_mode:"approve_for_me"}]);
  await page.reload(); await expect(page.getByText("改成给同事的三条说明",{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1)).toBeTruthy();
  if(width===390) await page.getByRole("button",{name:"对话列表",exact:true}).click();
  await page.getByRole("button",{name:"新对话",exact:true}).click();
  await expect(page.getByRole("heading",{name:"从一个问题开始"})).toBeVisible();
});
