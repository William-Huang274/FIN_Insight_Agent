import { expect, test } from "playwright/test";

for (const width of [1440, 1024, 390]) {
  test(`saved evidence graph, draft and checkpoint isolation at ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 950 });
    const id = "00000000-0000-4000-8000-000000000001", checkpoint = "00000000-0000-4000-8000-000000000002";
    const source = { source_id: "CALC::graph", title: "测试保存计算", result_state: "non_authoritative_metric", value_decimal: "0.6", unit: "ratio" };
    const calculation = { expression: "cash/profit", value_decimal: "0.6", result_unit: "ratio", arithmetic_verified: true, financial_semantics_verified: false,
      operands: { cash: { source_id: "RAW::cash", value_decimal: "60", unit: "USD" }, profit: { value_decimal: "100", unit: "USD", authority: "explicit_assumption" } }, operand_source_aliases: { "RAW::cash": "P01:S001" } };
    const citations = { C1: { claim: { statement: "现金转换率需要核查。", kind: "calculation" }, sources: [source] },
      C2: { claim: { statement: "第二条独立引用。", kind: "fact" }, sources: [{ source_id: "SOURCE::other", title: "另一条来源" }] } };
    const report = { title: "图集成测试报告", narrative_markdown: "## 判断\n\n现金转换率需要核查。[C1]", citations, charts: [] };
    const session = { thread_id: id, title: "图测试任务", status: "interrupted", report_version: 4, report, conversation: [], runs: [], model_events: [], can_respond: true };
    let failSource = true;
    const requests: string[] = [], writes: string[] = [];
    await page.route("**/api/v1/**", async route => {
      const url = new URL(route.request().url());
      if (route.request().method() !== "GET") writes.push(url.pathname);
      let body: unknown = {};
      if (url.pathname.endsWith("/research-session-config")) body = { fresh_research_enabled: false };
      else if (url.pathname.endsWith("/research-sessions")) body = [session];
      else if (url.pathname.endsWith("/report-versions")) body = { versions: [{ version: 4, checkpoint_id: checkpoint, title: report.title }], next_cursor: null };
      else if (url.pathname.endsWith("/source")) {
        requests.push(url.search);
        if (failSource) { await route.fulfill({ status: 503, json: { detail: "测试来源读取失败" } }); return; }
        body = url.searchParams.get("source_id") === "P01:S001" ? { source_id: "P01:S001", text: "原始现金流出处。" }
          : width === 1024 ? { ...source, text: JSON.stringify(calculation), arithmetic_verified: true, financial_semantics_verified: false }
            : { ...source, calculation };
      } else if (url.pathname.endsWith(id)) body = session;
      await route.fulfill({ json: body });
    });
    await page.goto(`/workspace/session?thread=${id}`);
    const graph = page.getByRole("region", { name: "研究依据图" });
    await expect(graph).toBeVisible();
    await expect(graph.getByText("已固定报告 v4 的来源版本")).toBeVisible();
    await graph.getByRole("button", { name: "展开来源 / 计算", exact: true }).click();
    await expect(graph.getByRole("alert")).toContainText("测试来源读取失败");
    failSource = false;
    await graph.getByRole("button", { name: "重试来源读取" }).click();
    await expect(graph.getByText("金融语义：未通过 / 未验证", { exact: false })).toBeVisible();
    await graph.getByRole("button", { name: "在图上展开操作数" }).click();
    await expect(graph.locator('.react-flow__node[data-id="source:CALC::graph:operand:cash"]')).toBeVisible();
    if (width === 390) await graph.getByRole("button", { name: "cash = 60", exact: true }).click();
    else await graph.locator('.react-flow__node[data-id="source:CALC::graph:operand:cash"]').click();
    await expect(graph.getByText("原始现金流出处。", { exact: true })).toBeVisible();
    expect(requests.every(q => q.includes(`checkpoint_id=${checkpoint}`))).toBe(true);
    expect(requests.some(q => q.includes("P01%3AS001"))).toBe(true);
    await graph.getByRole("button", { name: "针对这条引用写修订意见" }).click();
    await graph.getByLabel("你的假设 / 质疑 / 补证要求").fill("请核对回款跨期，不应直接视为已发生事实。");
    await graph.getByRole("button", { name: "查看修订范围" }).click();
    await expect(graph.getByRole("status")).toContainText("尚未连接修订执行");
    await expect(graph.locator('.react-flow__node.rg-affected')).toHaveCount(2);
    await graph.getByLabel("选择研究引用", { exact: false }).selectOption("C2");
    await graph.getByRole("button", { name: "针对这条引用写修订意见" }).click();
    await expect(graph.getByLabel("你的假设 / 质疑 / 补证要求")).toHaveValue("");
    await graph.getByLabel("选择研究引用", { exact: false }).selectOption("C1");
    await graph.getByRole("button", { name: "针对这条引用写修订意见" }).click();
    await expect(graph.getByLabel("你的假设 / 质疑 / 补证要求")).toHaveValue("请核对回款跨期，不应直接视为已发生事实。");
    await graph.getByRole("button", { name: "阅读完整报告" }).click();
    await expect(page.getByRole("heading", { name: report.title, exact: true })).toBeVisible();
    await page.getByRole("button", { name: "研究图", exact: true }).click();
    await expect(graph.getByLabel("你的假设 / 质疑 / 补证要求")).toHaveValue("请核对回款跨期，不应直接视为已发生事实。");
    expect(writes).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  });
}
