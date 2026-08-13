import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test } from "playwright/test";


async function capture(page: import("playwright/test").Page, name: string, project: string) {
  const root = process.env.FINSIGHT_E2E_SCREENSHOT_DIR;
  if (!root) return;
  mkdirSync(root, { recursive: true });
  await page.screenshot({ path: resolve(root, `${project}-${name}.png`) });
}

async function expectNoHorizontalOverflow(page: import("playwright/test").Page) {
  const dimensions = await page.evaluate(() => ({
    viewport: document.documentElement.clientWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport);
}

test("workspace exposes the three identity-bound reviewed cases", async ({ page }, testInfo) => {
  const productDataExpected = Boolean(process.env.FINSIGHT_E2E_DATA_ROOT);
  await page.goto("/workspace");
  await expect(page.getByRole("heading", { name: "当前研究案例" })).toBeVisible();
  await expect(page.getByText(/3 个案例已通过身份与摘要绑定/)).toBeVisible();
  for (const ticker of ["DELL", "MU", "NVDA"]) {
    await expect(page.getByText(ticker, { exact: true })).toBeVisible();
  }
  await expectNoHorizontalOverflow(page);
  await capture(page, "workspace-index", testInfo.project.name);

  const dell = page.getByRole("button", { name: /Dell Technologies/ });
  if (!productDataExpected) {
    await expect(dell).toBeDisabled();
    await expect(page.getByText(/仍需挂载 DELL、MU、NVDA 证据对象/)).toBeVisible();
    return;
  }

  await expect(dell).toBeEnabled();
  await dell.click();
  await expect(page.getByRole("heading", { name: "Dell Technologies Inc." })).toBeVisible();
  await expect(page.getByText(/CIK 0001571996/)).toBeVisible();
  await expect(page.getByText("不可变绑定")).toBeVisible();
  await page.getByRole("button", { name: /证据与缺口/ }).click();
  await expect(page.getByRole("heading", { name: "已审 Evidence" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Residual Gaps" })).toBeVisible();
  await page.getByRole("button", { name: /检索候选/ }).click();
  await expect(page.getByRole("heading", { name: "当前候选检索" })).toBeVisible();
  await expect(page.getByText("candidate_not_evidence", { exact: false })).toHaveCount(0);
  await expect(page.getByText(/这些是待审候选，不是 Evidence/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "同对象排名对照" })).toBeVisible();
  await expect(page.getByText(/这组数字只比较同一批对象如何排序/)).toBeVisible();
  for (const route of ["BM25 关键词", "BGE-M3 语义", "1:1 RRF 融合", "金融角色重排"]) {
    await expect(page.getByText(route, { exact: true }).first()).toBeVisible();
  }
  await expect(page.getByText(/point_in_time_market/)).toBeVisible();
  await expectNoHorizontalOverflow(page);
  await capture(page, "dell-evidence", testInfo.project.name);
  await page.getByRole("button", { name: /返回案例列表/ }).click();
  await expect(page.getByRole("heading", { name: "当前研究案例" })).toBeVisible();
});


test("operations is isolated from the research product", async ({ page }, testInfo) => {
  await page.goto("/operations");
  await expect(page.getByRole("heading", { name: "运行与数据控制台" })).toBeVisible();
  await expect(page.getByText("服务状态")).toBeVisible();
  await expect(page.getByText("评测目录")).toBeVisible();
  await expect(page.getByRole("heading", { name: "官方资料入库" })).toBeVisible();
  await expect(page.getByLabel("已登记来源")).toHaveValue(/DELL_Q1_FY2027/);
  await expect(page.getByText(/入库成功仍不是 Evidence/)).toBeVisible();
  await expect(page.getByRole("button", { name: "自动获取一次" })).toBeEnabled();
  await expectNoHorizontalOverflow(page);
  await capture(page, "operations", testInfo.project.name);
  await page.getByRole("link", { name: /研究工作区/ }).click();
  await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.getByRole("heading", { name: "当前研究案例" })).toBeVisible();
});


test("retired frontend route resolves to the current workspace", async ({ page }) => {
  await page.goto("/current/NVDA/report");
  await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.getByRole("heading", { name: "当前研究案例" })).toBeVisible();
});
