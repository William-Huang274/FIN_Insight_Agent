import { test, expect } from "playwright/test";

for (const width of [1440,1024,390]) test(`research start, organization, panel and rendered revision at ${width}`, async ({page}) => {
  await page.setViewportSize({width,height:950});
  const id="00000000-0000-4000-8000-000000000031", checkpoint="00000000-0000-4000-8000-000000000032";
  const writes:string[]=[];
  const config={schema_version:1,title:"标准研究编排",methods:{lead:"规划",finance:"财务",industry_product:"行业",counter:"反证",writer:"# 写作方法",verifier:"核验"},bindings:{lead:"lead",specialist:"finance",counter:"counter",verifier:"verifier",repair:"finance",synthesis:"writer",research_verifier:"verifier",writer:"writer",report_verifier:"verifier",quick_writer:"writer"},max_parallel_tasks:2,review_order:"parallel"};
  const roles={lead:"研究负责人",specialist:"研究专家",counter:"反证审查",verifier:"底稿核验",repair:"责任修订",synthesis:"综合研究",research_verifier:"研究判断复核",writer:"报告写作与修订",report_verifier:"报告独立复核",quick_writer:"简短追问"};
  let saved:any=null;
  const session={thread_id:id,title:"Atlas · 盈利质量",status:"interrupted",report_version:2,report_digest:"a".repeat(64),question:"研究 Atlas 最近季度的盈利质量。".repeat(30),can_upload:true,
    report:{title:"Atlas研究",narrative_markdown:"## 现金质量\n\n当前判断。",citations:{}},research_tasks:[],
    runs:[{run_id:"saved-run",status:"success",human_action:"revise",revision_target:{citation_id:"C1",base_version:1,base_checkpoint:checkpoint}}]};
  await page.route("**/api/v1/**",async route=>{
    const path=new URL(route.request().url()).pathname; if(route.request().method()!=="GET")writes.push(path);
    let body:any={};
    if(path.endsWith("research-studio/configurations")){if(route.request().method()==="POST"){saved=route.request().postDataJSON();body={assistant_id:checkpoint};}else body={default:config,roles,versions:saved?[{assistant_id:checkpoint,title:saved.title,created_at:"2026-09-08T00:00:00Z"}]:[]};}
    else if(path.endsWith(`configurations/${checkpoint}`))body={configuration:saved};
    else if(path.endsWith("/apply"))body={notice:"已应用到任务；下一次运行固定读取此版本"};
    else if(path.endsWith("research-session-config"))body={fresh_research_enabled:true};
    else if(path.endsWith("research-sessions"))body=[session];
    else if(path.endsWith("report-versions"))body={versions:[{version:2,checkpoint_id:checkpoint}],next_cursor:null};
    else if(path.endsWith("report-diff"))body={before_version:1,after_version:2,reason:"补充口径",charts_changed:false,citations_changed:false,diff:"--- v1\n+++ v2\n@@ -1,3 +1,3 @@\n ## 现金质量\n \n-**旧判断**：需要核实。[C1]\n+**新判断**：仅限本季度。[C1]"};
    else if(path.endsWith("research-studio"))body={methods:[{method_id:"finance",title:"财务研究方法",summary:"核对口径",version:1,content:"# 财务研究方法\n\n**检查期间**，保留反证。"}]};
    else if(path.includes("research-studio/graph/"))body={graph_id:path.endsWith("research")?"research_session":"report_review",nodes:[{id:"writer"},{id:"verifier"}],edges:[{source:"writer",target:"verifier",conditional:false}]};
    else if(path.endsWith(id))body=session;
    await route.fulfill({json:body});
  });
  const nav=async(name:string)=>{if(width<=760){await page.getByRole("button",{name:"打开导航",exact:true}).click();await page.locator(".fs-nav-dialog").getByRole("button",{name,exact:true}).click();}else await page.locator(".fs-sidebar").getByRole("button",{name,exact:true}).click();};
  await page.goto("/workspace");await expect(page.getByRole("heading",{name:"这次，你想弄清楚什么？"})).toBeVisible();
  await page.getByRole("button",{name:"解读最新财报"}).click();await expect(page.getByLabel("输入研究问题")).toHaveValue(/季度/);
  await page.getByLabel("输入研究问题").fill("核对 Atlas 本季度收入与经营现金流的期间口径。");await page.getByRole("button",{name:"准备研究",exact:true}).click();await expect(page.getByLabel("这次你想研究什么？")).toHaveValue("核对 Atlas 本季度收入与经营现金流的期间口径。");
  await nav("管理项目");const dialog=page.getByRole("dialog",{name:"管理项目"});await dialog.getByLabel("新项目名称").fill("财报跟踪");await dialog.getByRole("button",{name:"创建项目"}).click();
  await dialog.getByLabel("归类 Atlas · 盈利质量").selectOption({label:"财报跟踪"});await dialog.getByLabel("置顶 Atlas · 盈利质量").click();await dialog.getByLabel("关闭项目管理").click();await page.reload();
  await nav("管理项目");await expect(dialog.getByLabel("归类 Atlas · 盈利质量").locator("option:checked")).toHaveText("财报跟踪");await expect(dialog.getByLabel("置顶 Atlas · 盈利质量")).toHaveAttribute("aria-pressed","true");await dialog.getByLabel("关闭项目管理").click();
  await page.goto(`/workspace/session?thread=${id}&view=report`);
  const toggle=page.getByRole("button",{name:"任务说明与资料",exact:true});const panel=page.locator("#task-details-panel");
  for(let i=0;i<3;i++){await toggle.click();await expect(panel).toBeVisible();await toggle.click();await expect(panel).toBeHidden();}
  await toggle.click();await panel.evaluate(el=>el.scrollTop=el.scrollHeight);await page.getByRole("button",{name:"收起资料面板"}).click();await expect(panel).toBeHidden();await expect(toggle).toBeFocused();
  await nav("修订记录");await page.getByRole("button",{name:"比较基线与当前报告"}).click();
  await expect(page.locator(".fs-diff-side.after strong")).toHaveText("新判断");await expect(page.locator(".fs-diff-side.before strong")).toHaveText("旧判断");await expect(page.locator(".fs-diff-raw pre")).toBeHidden();
  await page.getByRole("checkbox",{name:"显示邻近上下文"}).check();await expect(page.locator(".fs-diff-side.after h2")).toHaveText("现金质量");
  await nav("研究配置");await page.getByLabel("专家并行数").selectOption("1");await page.getByLabel("审查执行顺序").selectOption("counter_first");
  await page.getByRole("button",{name:"编辑此 Skill"}).click();await page.getByLabel("Skill 内容").fill("# 新方法\n\n核对期间、单位和反证。");
  await page.getByRole("button",{name:"保存为新版本"}).click();await expect(page.getByRole("status")).toContainText("已保存到运行服务");
  expect(saved.max_parallel_tasks).toBe(1);expect(saved.review_order).toBe("counter_first");expect(saved.methods.writer).toContain("核对期间");
  await page.getByLabel("应用配置的任务").selectOption(id);await page.getByRole("button",{name:"应用保存版本"}).click();await expect(page.getByRole("status")).toContainText("已应用到任务");
  await page.reload();await page.getByLabel("保存版本").selectOption(checkpoint);await page.getByRole("button",{name:"投研 Skills"}).click();await expect(page.getByLabel("Skill 内容")).toHaveValue(saved.methods.writer);
  expect(writes).toEqual(["/api/v1/research-studio/configurations",`/api/v1/research-studio/configurations/${checkpoint}/apply`]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
});
