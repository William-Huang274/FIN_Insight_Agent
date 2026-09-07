import { expect, test } from "playwright/test";
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
      text: "合成操作数 a=9，b=10；a/b=0.9。" };
    const answerCitations = { ...gapCitations, "CALC::fixture": { claim: { kind: "calculation", statement: "保存计算" }, sources: [calc] } };
    const oldReport = { title: "历史报告标题", narrative_markdown: "## 研究结论\n\n旧版研究结论。[NUMFACT::fixture]", citations, charts: [] };
    const report = { ...oldReport, title: "当前研究报告", narrative_markdown: "## 研究结论\n\n修订后的现金流解释。[NUMFACT::fixture]" };
    const session = { thread_id: id, status: "interrupted", phase: "ready_for_human_review", question: "合成界面验证：收入增长是否转为现金？", research_as_of: "2026-09-02", report_version: 2,
      report, report_review: { summary: "合成审阅示例，未启动研究。", findings: [], unresolved_data_requests: [] }, can_respond: true,
      runs: [], conversation: [{ role: "user", content: "请解释现金兑现。" }, { role: "assistant",
        content: "该期间本地未取得数值。[MCPFACT::fixture]\n\n已保存计算 CALC::fixture 回读。\n\n`[CALC::fixture]`\n\nCALC::fixture-invented\n\n[未绑定链接](#claim:CALC%3A%3Aunknown) [坏编码](#claim:%ZZ)", citations: answerCitations }],
      model_events: [
        { kind: "model", event: "outcome", actor: "lead", call_id: "resumed-id", run_id: "first-run", total_tokens: 82, status: "provider_output_truncated" },
        { kind: "model", event: "outcome", actor: "lead", call_id: "resumed-id", run_id: "second-run", total_tokens: 58, status: "success" },
      ] };
    let selectedSource = "";
    await page.route("**/api/v1/**", async route => {
      const url = new URL(route.request().url());
      let body: unknown = {};
      if (url.pathname.endsWith("/research-session-config")) body = { fresh_research_enabled: false };
      else if (url.pathname.endsWith("/research-sessions")) body = [{ thread_id: id, title: "版本验证任务", status: "interrupted" }];
      else if (url.pathname.endsWith("/report-versions")) body = { versions: [{ version: 1, checkpoint_id: checkpoint, title: oldReport.title, reason: "初始研究" }], next_cursor: null };
      else if (url.pathname.endsWith(`/report-versions/${checkpoint}`)) body = { report: oldReport, report_version: 1, checkpoint_id: checkpoint, reason: "初始研究" };
      else if (url.pathname.endsWith("/report-diff")) body = { before_version: 1, after_version: 2, reason: "根据原始现金流来源修订", diff: "--- v1\n+++ v2\n-旧版研究结论。\n+修订后的现金流解释。", charts_changed: false, citations_changed: false };
      else if (url.pathname.endsWith("/source")) { selectedSource = url.search; body = url.searchParams.get("source_id") === gap.source_id ? gap : url.searchParams.get("source_id") === calc.source_id ? calc : { ...source, text: "该历史版本绑定的来源片段。", next_offset: null }; }
      else if (url.pathname.endsWith(`/${id}`)) body = session;
      await route.fulfill({ json: body });
    });
    await page.goto(`/workspace/session?thread=${id}`);
    await expect(page.getByRole("heading", { name: "当前研究报告" })).toBeVisible();
    const conversationTab = page.getByRole("button", { name: /^追问与反馈/ });
    const tabbed = await conversationTab.isVisible();
    if (tabbed) await conversationTab.click();
    await page.getByLabel("研究对话").getByRole("button", { name: "1", exact: true }).click();
    await expect(page.getByText("本地查询边界 · 非事实证据", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "查看查询条件与回执" }).click();
    await expect(page.getByText(gap.text, { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "关闭详情", exact: true }).click();
    const conversation = page.getByLabel("研究对话");
    await expect(conversation.getByRole("button", { name: "2", exact: true })).toHaveCount(1);
    await expect(conversation.locator("code")).toHaveText("[CALC::fixture]");
    await expect(conversation.getByText("CALC::fixture-invented", { exact: true })).toBeVisible();
    await expect(conversation.getByRole("button", { name: "未绑定链接", exact: true })).toHaveCount(0);
    await conversation.getByRole("button", { name: "2", exact: true }).click();
    await page.getByRole("button", { name: "查看捕获片段与上下文" }).click();
    await expect(page.getByText(calc.text, { exact: true })).toBeVisible();
    expect(selectedSource).toContain("source_id=CALC%3A%3Afixture");
    await page.getByRole("button", { name: "关闭详情", exact: true }).click();
    if (tabbed) await page.getByRole("button", { name: "研究报告", exact: true }).click();
    await page.getByRole("button", { name: "审查、来源与运行", exact: true }).click();
    await page.getByRole("button", { name: "运行", exact: true }).click();
    await expect(page.getByText(/活动视图当前载入 2 次模型结果记录、140 个已报告 tokens/)).toBeVisible();
    await page.getByRole("button", { name: "关闭详情", exact: true }).click();
    if (width >= 1280) await expect(page.getByLabel("研究对话")).toBeVisible();
    await page.getByLabel("阅读报告版本").selectOption(checkpoint);
    await expect(page.getByRole("heading", { name: "历史报告标题" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Markdown", exact: true })).toHaveAttribute("href", new RegExp(`checkpoint_id=${checkpoint}`));
    await page.getByRole("button", { name: "与当前版本比较" }).click();
    await expect(page.getByText("根据原始现金流来源修订", { exact: false })).toBeVisible();
    const root = process.env.FINSIGHT_E2E_SCREENSHOT_DIR;
    if (root) { mkdirSync(root, { recursive: true }); await page.screenshot({ path: resolve(root, `report-versions-${width}.png`) }); }
    const dimension = await page.evaluate(() => ({ width: document.documentElement.clientWidth, full: document.documentElement.scrollWidth }));
    expect(dimension.full).toBeLessThanOrEqual(dimension.width);
    await page.getByRole("button", { name: /1/ }).filter({ hasText: "1" }).first().click();
    await page.getByRole("button", { name: "查看捕获片段与上下文" }).click();
    await expect(page.getByText("该历史版本绑定的来源片段。", { exact: true })).toBeVisible();
    expect(selectedSource).toContain(`checkpoint_id=${checkpoint}`);
    await page.getByRole("button", { name: "关闭详情", exact: true }).click();
    await page.getByLabel("阅读报告版本").selectOption("");
    await expect(page.getByRole("heading", { name: "当前研究报告" })).toBeVisible();
  });
}
