import { test, expect, type Page } from "./identity-fixture";

for (const width of [1440, 1024, 390]) test(`formal navigation, generic tasks and draft continuity at ${width}`, async ({page}) => {
  await page.setViewportSize({width,height:950});
  const a = "00000000-0000-4000-8000-000000000011", b = "00000000-0000-4000-8000-000000000012", checkpoint = "00000000-0000-4000-8000-000000000013";
  const tasks = [a,b].map((id,i) => ({thread_id:id, title:i ? "Orion · 订阅收入" : "Atlas · 库存周转", status:"interrupted", phase:"ready_for_human_review", report_version:1, report_digest:(i ? "b" : "a").repeat(64), can_respond:true,
    report:{title:i ? "订阅质量" : "库存结构", narrative_markdown:"## 待核判断\n\n口径需要核实。[C1]", citations:{C1:{claim:{statement:"口径需要核实。",kind:"fact"},sources:[{source_id:"DOC::one",title:"公司披露"}]}}}, runs:[], model_events:[]}));
  const writes: any[] = [];
  await page.route("**/api/v1/**", async route => { const u=new URL(route.request().url()); let body:any={};
    if(route.request().method()!=="GET") writes.push({path:u.pathname,...route.request().postDataJSON()});
    if(u.pathname.endsWith("research-session-config")) body={fresh_research_enabled:true,research_as_of:"2026-09-02"};
    else if(u.pathname.endsWith("research-sessions")) body=route.request().method()==="GET" ? tasks : {thread_id:b};
    else if(u.pathname.endsWith("report-versions")) body={versions:[{version:1,checkpoint_id:checkpoint}],next_cursor:null};
    else body=tasks.find(s=>u.pathname.endsWith(s.thread_id)) || {};
    await route.fulfill({json:body});
  });
  const nav=async(name:string)=>{if(width<=760){await page.getByRole("button",{name:"打开导航",exact:true}).click();await page.locator(".fs-nav-dialog").getByRole("button",{name,exact:true}).click();}else await page.locator(".fs-sidebar").getByRole("button",{name,exact:true}).click();};
  await page.goto(`/workspace/session?thread=${a}`);
  await page.locator(".fs-tree-branches").getByRole("button",{name:"待核判断",exact:true}).click();
  await page.locator(".fs-tree-branches").getByRole("button",{name:"口径需要核实。",exact:true}).click();
  await page.getByRole("button",{name:"针对这条引用写修订意见"}).click(); await page.getByLabel("你的假设 / 质疑 / 补证要求").fill("请说明期间和库存口径。");
  await nav("研究报告"); await expect(page.getByRole("article")).toContainText("口径需要核实"); await page.goBack();
  await expect(page.getByLabel("你的假设 / 质疑 / 补证要求")).toHaveValue("请说明期间和库存口径。");
  await nav("全部研究"); await page.getByRole("textbox",{name:"搜索研究"}).fill("Orion"); await expect(page.locator(".fs-research-list>button")).toHaveCount(1); await page.locator(".fs-research-list>button").click();
  await page.locator(".fs-tree-branches").getByRole("button",{name:"待核判断",exact:true}).click(); await page.locator(".fs-tree-branches").getByRole("button",{name:"口径需要核实。",exact:true}).click(); await page.getByRole("button",{name:"针对这条引用写修订意见"}).click(); await expect(page.getByLabel("你的假设 / 质疑 / 补证要求")).toHaveValue("");
  await nav("全部研究"); await page.getByRole("textbox",{name:"搜索研究"}).fill("Atlas"); await page.locator(".fs-research-list>button").click();
  await page.getByRole("button",{name:"针对这条引用写修订意见"}).click(); await expect(page.getByLabel("你的假设 / 质疑 / 补证要求")).toHaveValue("请说明期间和库存口径。");
  await page.reload(); await page.getByRole("button",{name:"针对这条引用写修订意见"}).click(); await expect(page.getByLabel("你的假设 / 质疑 / 补证要求")).toHaveValue("请说明期间和库存口径。");
  await nav("修订记录"); await expect(page.getByRole("heading",{name:"尚无已提交的修订"})).toBeVisible();
  await nav("运行与费用"); await expect(page.getByRole("heading", {name:"研究现场",exact:true})).toBeVisible();
  await nav("外观与偏好"); await page.getByRole("combobox",{name:"界面外观"}).selectOption("dark"); await expect(page.locator(".fs-workspace")).toHaveAttribute("data-theme","dark");
  await page.getByRole("checkbox",{name:"减少动态效果"}).check();
  await nav("新建研究"); await page.getByLabel("这次你想研究什么？").fill("研究 Orion 的订阅续费质量，核查最新季度收入与现金。"); expect(writes).toEqual([]);
  await page.getByRole("button",{name:"保存为资料准备草稿",exact:true}).click(); await expect.poll(()=>writes.length).toBe(1); expect(writes[0]).toMatchObject({mode:"research",defer_start:true}); expect(writes[0].title).toContain("Orion");
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
