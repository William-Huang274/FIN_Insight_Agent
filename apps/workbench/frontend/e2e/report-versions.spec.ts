import { expect, test } from "./identity-fixture";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

for (const width of [1440, 1024, 390]) {
  test(`report history, real diff and selected-source navigation at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 950 });
    const id = "00000000-0000-4000-8000-000000000001";
    const checkpoint = "00000000-0000-4000-8000-000000000002";
    const source = { source_id: "NUMFACT::fixture", title: "合成财务来源", source_url: "https://example.com/source", value_decimal: "12", unit: "USD", numeric_fact_authority: true };
    const citations = { "NUMFACT::fixture": { claim: { kind: "numeric_fact", statement: "合成引用用于界面验证。" }, sources: [source] } };
    const gap = { source_id: "MCPFACT::fixture", title: "本地查询边界回执", result_state: "query_gap_receipt",
      numeric_fact_authority: false, text: "合成查询期间内没有结果，不证明发行人未披露。", authority_note: "仅为本地查询回执。" };
    const gapCitations = { "MCPFACT::fixture": { claim: { kind: "local_query_gap", statement: "本地查询缺数不代表发行人未披露。" }, sources: [gap] } };
    const calc = { source_id: "CALC::fixture", title: "合成保存计算", value_decimal: "0.9", unit: "ratio", numeric_fact_authority: false,
      text: "合成操作数 a=9，b=10；a/b=0.9。", calculation: { expression: "a/b", value_decimal: "0.9", result_unit: "ratio",
        arithmetic_verified: true, financial_semantics_verified: false,
        operands: { a: { source_id: source.source_id, value_decimal: "9", unit: "USD", period_end: "2025-12-31" }, b: { value_decimal: "10", unit: "USD", authority: "explicit_assumption" } } } };
    const answerCitations = { ...gapCitations, "CALC::fixture": { claim: { kind: "calculation", statement: "保存计算" }, sources: [calc] } };
    const oldReport = { title: "历史报告标题", narrative_markdown: "## 研究结论\n\n旧版研究结论。[NUMFACT::fixture]", citations, charts: [] };
    const report = { ...oldReport, title: "当前研究报告", narrative_markdown: "## 研究结论\n\n修订后的现金流解释。[NUMFACT::fixture]\n\n" + "解释现金流的口径。\n\n".repeat(40) + "## 研究结论\n\n第二节同名标题仍可定位。[NUMFACT::fixture]" };
    const session = { thread_id: id, status: "interrupted", phase: "ready_for_human_review", question: "合成界面验证：收入增长是否转为现金？", research_as_of: "2026-09-02", report_version: 2,
      report, report_review: { summary: "合成审阅示例，未启动研究。", findings: [], unresolved_data_requests: [] }, can_respond: true,
      runs: [], conversation: [{ role: "user", content: "请解释现金兑现。" }, { role: "assistant",
        content: "该期间本地未取得数值。[MCPFACT::fixture]\n\n已保存计算 CALC::fixture 回读。\n\n`[CALC::fixture]`\n\nCALC::fixture-invented\n\n[CALC::fixture/suffix]\n\n未绑定记录 P01:C99 与 NUMFACT::abcdef。\n\n判断编号 P01:C98\n\n[未绑定链接](#claim:CALC%3A%3Aunknown) [坏编码](#claim:%ZZ)", citations: answerCitations }],
      model_events: [
        { kind: "model", event: "outcome", actor: "lead", call_id: "resumed-id", run_id: "first-run", total_tokens: 82, status: "provider_output_truncated" },
        { kind: "model", event: "outcome", actor: "lead", call_id: "resumed-id", run_id: "second-run", total_tokens: 58, status: "success" },
      ] };
    let selectedSource = "";
    let sourceUnavailable = false;
    await page.route("**/api/v1/**", async route => {
      const url = new URL(route.request().url());
      let body: unknown = {};
      if (url.pathname.endsWith("/research-session-config")) body = { fresh_research_enabled: false };
      else if (url.pathname.endsWith("/research-sessions")) body = [{ thread_id: id, title: "版本验证任务", status: "interrupted" }];
      else if (url.pathname.endsWith("/report-versions")) body = { versions: [{ version: 1, checkpoint_id: checkpoint, title: oldReport.title, reason: "初始研究" }], next_cursor: null };
      else if (url.pathname.endsWith(`/report-versions/${checkpoint}`)) body = { report: oldReport, report_version: 1, checkpoint_id: checkpoint, reason: "初始研究" };
      else if (url.pathname.endsWith("/report-diff")) body = { before_version: 1, after_version: 2, reason: "根据原始现金流来源修订", diff: "--- v1\n+++ v2\n@@ -1 +1 @@\n-旧版研究结论。\n+修订后的现金流解释。", charts_changed: false, citations_changed: false };
      else if (url.pathname.endsWith("/source")) {
        if (sourceUnavailable) { await route.fulfill({ status: 503, json: { detail: "合成来源暂时不可读取" } }); return; }
        selectedSource = url.search; body = url.searchParams.get("source_id") === gap.source_id ? gap : url.searchParams.get("source_id") === calc.source_id
          ? width === 1024 ? { ...calc, calculation: undefined, result_state: "non_authoritative_metric", arithmetic_verified: true, financial_semantics_verified: false, text: JSON.stringify(calc.calculation) } : calc
          : { ...source, text: "该历史版本绑定的来源片段。", next_offset: null }; }
      else if (url.pathname.endsWith(`/${id}`)) body = session;
      await route.fulfill({ json: body });
    });
    await page.goto(`/workspace/session?thread=${id}`);
    await taskPage(page, "研究报告");
    await expect(page.getByRole("heading", { name: "当前研究报告" })).toBeVisible();
    await expect(page.getByLabel("研究对话")).toBeHidden();
    await expect(page.getByText(session.question, { exact: true })).toBeHidden();
    const headings = page.locator(".rs-prose [id^='report-section-']");
    const headingIds = await headings.evaluateAll(items => items.map(item => item.id));
    expect(new Set(headingIds).size).toBe(2);
    if (width <= 1200) await page.locator("#report-section-picker").selectOption(headingIds[1]);
    else await page.getByRole("navigation", { name: "报告目录" }).getByRole("button", { name: "研究结论", exact: true }).nth(1).click();
    const reportScroll = await page.locator(".rs-document").evaluate(el => el.scrollTop);
    expect(reportScroll).toBeGreaterThan(100);
    const secondCitation = page.locator(".rs-report-pane .rs-cite").nth(1);
    await secondCitation.click();
    sourceUnavailable = true;
    await page.getByRole("button", { name: "查看捕获片段与上下文" }).click();
    await expect(page.getByRole("alert")).toContainText("来源读取失败");
    sourceUnavailable = false;
    await page.getByRole("button", { name: "查看捕获片段与上下文" }).click();
    await expect(page.getByText("该历史版本绑定的来源片段。", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "关闭详情", exact: true }).click();
    await expect(secondCitation).toBeFocused();
    expect(Math.abs(await page.locator(".rs-document").evaluate(el => el.scrollTop) - reportScroll)).toBeLessThan(5);
    await taskPage(page, "追问与反馈");
    await page.getByLabel("研究对话").getByRole("button", { name: "依据 1", exact: true }).click();
    await expect(page.getByText("本地查询边界 · 非事实证据", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "查看查询条件与回执" }).click();
    await expect(page.getByText(gap.text, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "关闭详情", exact: true }).click();
    const conversation = page.getByLabel("研究对话");
    await expect(conversation.getByRole("button", { name: "依据 2", exact: true })).toHaveCount(1);
    await expect(conversation.locator("code")).toHaveText("[CALC::fixture]");
    await expect(conversation.getByText("CALC::fixture-invented", { exact: true })).toBeVisible();
    await expect(conversation.getByText("[CALC::fixture/suffix]", { exact: true })).toBeVisible();
    await expect(conversation.getByRole("button", { name: "未绑定链接", exact: true })).toHaveCount(0);
    await expect(conversation).toContainText("未绑定记录 判断编号 P01:C99 与 财务数据编号 NUMFACT::abcdef。");
    await expect(conversation).toContainText("判断编号 P01:C98");
    await expect(conversation).not.toContainText("判断编号 判断编号");
    await expect(conversation.getByRole("button", { name: /P01:C99|NUMFACT::abcdef/ })).toHaveCount(0);
    await conversation.getByRole("button", { name: "依据 2", exact: true }).click();
    await page.getByRole("button", { name: "查看捕获片段与上下文" }).click();
    await expect(page.getByRole("heading", { name: "计算过程", exact: true })).toBeVisible();
    await expect(page.getByText("金融语义：未确认", { exact: false })).toBeVisible();
    expect(selectedSource).toContain("source_id=CALC%3A%3Afixture");
    await page.getByRole("button", { name: "查看操作数 a 来源" }).click();
    await expect(page.getByText("该历史版本绑定的来源片段。", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "← 返回上一级来源 / 计算" }).click();
    await expect(page.getByRole("heading", { name: "计算过程", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "关闭详情", exact: true }).click();
    await taskPage(page, "研究报告");
    // The mobile navigation closes before the route transition commits. Wait
    // for the report pane before opening a panel on the destination page.
    await expect(page.locator(".rs-report-pane")).toBeVisible();
    await page.locator(".rs-top").getByRole("button", { name: "运行与费用", exact: true }).click();
    await expect(page.getByRole("heading", { name: "研究现场", exact: true })).toBeVisible();
    await page.getByText("模型与工具活动 · 2 条记录", { exact: true }).click();
    await expect(page.getByLabel("Agent 活动流")).toContainText("82 tokens");
    await expect(page.getByLabel("Agent 活动流")).toContainText("58 tokens");
    await page.getByRole("button", { name: "阅读当前报告", exact: true }).click();
    await expect(page.getByLabel("研究对话")).toBeHidden();
    await page.getByLabel("阅读报告版本").selectOption(checkpoint);
    await expect(page.getByRole("heading", { name: "历史报告标题" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Markdown", exact: true })).toHaveAttribute("href", new RegExp(`checkpoint_id=${checkpoint}`));
    await page.getByRole("button", { name: "与当前版本比较" }).click();
    await page.locator(".fs-diff-reason summary").click();
    await expect(page.getByText("根据原始现金流来源修订", { exact: false })).toBeVisible();
    const root = process.env.FINSIGHT_E2E_SCREENSHOT_DIR;
    if (root) { mkdirSync(root, { recursive: true }); await page.screenshot({ path: resolve(root, `report-versions-${width}.png`) }); }
    const dimension = await page.evaluate(() => ({ width: document.documentElement.clientWidth, full: document.documentElement.scrollWidth }));
    expect(dimension.full).toBeLessThanOrEqual(dimension.width);
    await page.locator(".rs-report-pane .rs-cite").first().click();
    await page.getByRole("button", { name: "查看捕获片段与上下文" }).click();
    await expect(page.getByText("该历史版本绑定的来源片段。", { exact: true })).toBeVisible();
    expect(selectedSource).toContain(`checkpoint_id=${checkpoint}`);
    await page.getByRole("button", { name: "关闭详情", exact: true }).click();
    await page.getByLabel("阅读报告版本").selectOption("");
    await expect(page.getByRole("heading", { name: "当前研究报告" })).toBeVisible();
  });
}

async function taskPage(page: import("playwright/test").Page, name: string) {
  if ((page.viewportSize()?.width || 1440) <= 760) {
    await page.getByRole("button", { name: "打开导航", exact: true }).click();
    await page.locator(".fs-nav-dialog").getByRole("button", { name, exact: true }).click();
  } else await page.locator(".fs-sidebar").getByRole("button", { name, exact: true }).click();
}
