import { expect, test } from "playwright/test";

test("current product exposes three isolated cases and ten read-only surfaces", async ({ page }, testInfo) => {
  const currentRequests: Array<{ mode: string | undefined; permission: string | undefined }> = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/current-product/")) {
      currentRequests.push({
        mode: request.headers()["x-fin-product-mode"],
        permission: request.headers()["x-fin-case-permissions"],
      });
    }
  });

  await page.goto("/current/NVDA/case");
  await expect(page.getByTestId("current-product-root")).toBeVisible();
  await expect(page.getByTestId("case-DELL")).toBeVisible();
  await expect(page.getByTestId("case-MU")).toBeVisible();
  await expect(page.getByTestId("case-NVDA")).toBeVisible();
  await expect(page.locator(".current-case-list > button")).toHaveCount(3);
  await expect(page.getByTestId("current-product-root")).not.toContainText("fixture_internal");
  for (const surface of ["case", "run", "evidence", "numeric", "graph", "gaps", "workpaper", "report", "trace", "quality"]) {
    await expect(page.getByTestId(`surface-${surface}`)).toBeVisible();
  }

  await page.getByTestId("surface-graph").click();
  await expect(page.getByTestId("graph-empty")).toContainText("没有获批的 Graph 边");
  await expect(page.getByTestId("graph-empty")).toContainText("诚实空状态");

  await page.getByTestId("case-DELL").click();
  await expect(page.getByRole("heading", { name: "DELL 研究工作台" })).toBeVisible();
  await expect(page.getByTestId("graph-empty")).toBeVisible();

  await page.getByTestId("surface-evidence").click();
  await expect(page.getByTestId("evidence-list").locator("article")).toHaveCount(15);
  await expect(page.getByTestId("current-product-root")).toHaveAttribute("data-active-case", "DELL");
  await page.screenshot({ path: testInfo.outputPath("dell-evidence.png"), fullPage: true });

  expect(currentRequests.length).toBeGreaterThan(0);
  expect(currentRequests.every((request) => request.mode === "current")).toBeTruthy();
  expect(currentRequests.every((request) => request.permission === "current_product:read")).toBeTruthy();
});

test("report and quality remain honest about acceptance boundaries", async ({ page }, testInfo) => {
  await page.goto("/current/NVDA/report");
  await expect(page.getByTestId("current-report")).toContainText("NVDA 三单元内部研究备忘录");
  await expect(page.getByTestId("current-report")).toContainText("局限");
  await page.getByTestId("surface-quality").click();
  await expect(page.getByTestId("quality-surface")).toContainText("L1–L4 分层验收");
  await expect(page.getByTestId("quality-surface")).toContainText("qualified human review");
  await expect(page.getByTestId("quality-surface")).toContainText("false");
  await page.screenshot({ path: testInfo.outputPath("nvda-quality.png"), fullPage: true });
});

test("unknown case URLs fail closed to the registered case set", async ({ page }) => {
  await page.goto("/current/AMD/case");
  await expect(page.getByRole("heading", { name: "DELL 研究工作台" })).toBeVisible();
  await expect(page).toHaveURL(/\/current\/DELL\/case$/);
  await expect(page.getByTestId("case-AMD")).toHaveCount(0);
});
