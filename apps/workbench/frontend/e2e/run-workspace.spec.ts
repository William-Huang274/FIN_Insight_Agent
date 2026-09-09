import { test, expect } from "playwright/test";
for (const width of [1440, 1024, 390]) test(`agent conversation and run history at ${width}`, async ({ page }) => {
  await page.setViewportSize({ width, height: 950 });
  const id = "00000000-0000-4000-8000-000000000031", run = "00000000-0000-4000-8000-000000000032";
  let writes = 0;
  const session: any = { thread_id: id, title: "Atlas · 局部修订", status: "interrupted", phase: "ready_for_human_review", report_version: 2,
    report: { title: "报告", narrative_markdown: "## 判断\n\n现金口径。[P01:C9]", citations: { "P01:C9": { claim: { statement: "经营现金流需核对期间口径。" }, sources: [] } } },
    runs: [{ run_id: run, status: "success", human_action: "revise", created_at: "2026-09-08T08:00:00Z", revision_target: { citation_id: "P01:C9", base_version: 1 }, cost_estimate: { known_cny: .03, unknown_or_pending_requests: 1 }, usage: { total_tokens: 120 } }],
    model_events: [{ run_id: run, kind: "stage", actor: "writer", event: "progress", objective: "我先核对季度口径，再检查比较分母。", recorded_at: "2026-09-08T08:00:01Z" },
      { run_id: run, kind: "tool", actor: "writer", event: "outcome", tool: "read_current_source", status: "success", recorded_at: "2026-09-08T08:00:02Z" },
      { run_id: run, kind: "stage", actor: "report_verifier", event: "progress", objective: "正在复核新增的期间限定。", recorded_at: "2026-09-08T08:00:03Z" }] };
  session.runs[0].context_usage = { notice: "最近一次模型请求输入，不是累计计费量。", nodes: [{actor:"writer",call_id:"context-test",model:"deepseek-v4-flash",input_tokens:810000,capacity_tokens:1000000,basis:"provider_reported_input",near_capacity:true}] };
  await page.route("**/api/v1/**", async route => { if (route.request().method() !== "GET") writes++; const path = new URL(route.request().url()).pathname; await route.fulfill({ json: path.endsWith("research-sessions") ? [session] : path.endsWith("research-session-config") ? { fresh_research_enabled: true } : path.endsWith("report-versions") ? { versions: [], next_cursor: null } : session }); });
  await page.goto(`/workspace/session?thread=${id}&view=activity`);
  await expect(page.getByRole("log", { name: "Agent 活动流" })).toBeVisible();
  const context = page.getByRole("region", {name:"模型上下文用量"});
  await expect(context).toContainText("810,000 tokens");
  await context.locator("summary").click();
  await expect(context.getByRole("progressbar")).toHaveAttribute("value", "810000");
  await expect(context).toContainText("接近模型窗口上限");
  await expect(page.locator(".fs-run-target")).toContainText("经营现金流需核对期间口径");
  await expect(page.locator(".fs-live-prose")).toHaveCount(2);
  await page.locator(".fs-live-calls summary").click(); await expect(page.locator(".fs-live-calls")).toContainText("读取引用来源 · 已返回");
  await page.locator(".fs-live-context").getByRole("button", { name: "报告复核", exact: true }).click();
  await expect(page.locator(".fs-live-prose")).toHaveCount(1); await expect(page.locator(".fs-live-prose")).toContainText("正在复核");
  await page.getByRole("button", { name: "全部活动", exact: true }).click(); await expect(page.locator(".fs-live-prose")).toHaveCount(2);
  for (let i = 0; i < 2; i++) { await page.locator(".fs-run-history>summary").click(); await expect(page.getByLabel("搜索运行记录")).toBeVisible(); await page.locator(".fs-run-history>div>button").click(); await expect(page.getByLabel("搜索运行记录")).toBeHidden(); }
  await expect(page.getByRole("button", { name: "停止", exact: true })).toBeDisabled();
  expect(writes).toBe(0); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  // A fresh run has no report yet. Its task panel must still be collapsible.
  delete session.report; session.status = "busy"; session.phase = "researching";
  session.question = "核对两个不同财年的日期与收入单位。";
  session.runs[0].status = "running"; session.runs[0].human_action = "research";
  await page.reload();
  const panel = page.locator("#task-details-panel");
  await expect(panel).toBeHidden();
  await page.getByRole("button", { name:"任务说明与资料", exact:true }).click();
  await expect(panel).toBeVisible();
  await page.getByRole("button", { name:"收起资料面板", exact:true }).click();
  await expect(panel).toBeHidden();
  await expect(page.getByRole("log", {name:"Agent 活动流"})).toBeVisible();
  session.status = "error"; session.runs[0].status = "error";
  session.model_events.push({run_id:run, kind:"stage", actor:"specialist", event:"output", status:"recovered_candidate",
    objective:"## 已执行结果\n\n已核对期间和单位。**不同财年不可直接比较**。", recorded_at:"2026-09-08T08:00:04Z"});
  await page.reload();
  await expect(page.getByRole("region", {name:"失败说明"})).toBeVisible();
  await expect(page.getByRole("heading", {name:"已执行结果"})).toBeVisible();
  await expect(page.locator(".fs-live-output-label")).toHaveText("从历史提交记录恢复的候选输出");
  expect(await page.locator(".fs-live-prose").first().evaluate(el => parseFloat(getComputedStyle(el).fontSize))).toBeGreaterThanOrEqual(16);
  session.runs[0].status = "success"; session.phase = "research_needs_attention";
  session.research_tasks = [{ task_id: "task-a", objective: "核对年度收入依据", dependency_ids: [] }];
  session.research_failures = [{ run_id: run, task_id: "task-a", reason: "model_turn_ceiling_reached_no_silent_completion",
    model_explanation: "原文读取未完成，请核对来源访问。",
    accepted: false, candidate: { narrative_markdown: "## 未验收结果\n\n仍保留提交内容。" },
    feedback_codes: ["specialist_tool_arguments_invalid"], validation_issues: [{location:["claims",1], message:"invalid authority",type:"value_error"}],
    model_turns: 2, tool_actions: 1, saved_observations: 1 }];
  await page.reload();
  await expect(page.getByRole("region", {name:"失败说明"})).toBeVisible();
  await expect(page.getByRole("region", {name:"未完成底稿"})).toContainText("核对年度收入依据");
  await expect(page.getByRole("heading", {name:"未验收结果"})).toBeVisible();
  await expect(page.getByLabel("模型交接说明")).toContainText("原文读取未完成，请核对来源访问。");
  await page.getByText("查看提交校验与停止原因", {exact:true}).click();
  await expect(page.getByRole("region", {name:"未完成底稿"})).toContainText("invalid authority");
  session.runs.unshift({run_id:"later-run", status:"success", created_at:"2026-09-09T08:00:00Z"});
  session.phase = "ready_for_human_review";
  await page.reload();
  await expect(page.getByRole("region", {name:"未完成底稿"})).toHaveCount(0);
});
