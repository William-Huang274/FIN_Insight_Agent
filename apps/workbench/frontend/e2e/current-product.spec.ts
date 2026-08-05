import { expect, test } from "playwright/test";

test("current product exposes three isolated cases, ten immutable surfaces, and review control", async ({ page }, testInfo) => {
  const currentRequests: Array<{ mode: string | undefined; permission: string | undefined; actor: string | undefined }> = [];
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/current-product/")) {
      currentRequests.push({
        mode: request.headers()["x-fin-product-mode"],
        permission: request.headers()["x-fin-case-permissions"],
        actor: request.headers()["x-fin-current-actor"],
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
  await expect(page.getByTestId("current-repair-control")).toContainText("返修控制与历史回放");
  await expect(page.getByTestId("current-repair-control")).toContainText("Reviewer authority");
  await expect(page.getByTestId("current-repair-control")).toContainText("未认证 · 尚未执行（归 T07）");
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
  expect(currentRequests.every((request) => request.permission === "current_product:read,current_product:request_repair")).toBeTruthy();
  expect(currentRequests.every((request) => request.actor === "current_internal_operator")).toBeTruthy();
});

test("report and quality remain honest about acceptance boundaries", async ({ page }, testInfo) => {
  await page.goto("/current/NVDA/report");
  await expect(page.getByTestId("current-report")).toContainText("NVDA 三单元内部研究备忘录");
  await expect(page.getByTestId("current-report")).toContainText("局限");
  await page.getByTestId("surface-quality").click();
  await expect(page.getByTestId("quality-surface")).toContainText("L1–L4 分层验收");
  await expect(page.getByTestId("quality-surface")).toContainText("qualified human review");
  await expect(page.getByTestId("quality-surface")).toContainText("false");
  await expect(page.getByRole("button", { name: "针对当前“质量验收”请求返修" })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath("nvda-quality.png"), fullPage: true });
});

test("typed repair form records an append-only control response without changing the report", async ({ page }) => {
  await page.route("**/api/v1/current-product/cases/NVDA/return-requests", async (route) => {
    const command = route.request().postDataJSON() as Record<string, string>;
    const initialResponse = await page.request.get(
      "http://127.0.0.1:8765/api/v1/current-product/cases/NVDA/review-control",
      {
        headers: {
          "X-Fin-Product-Mode": "current",
          "X-Fin-Current-Actor": "current_internal_operator",
          "X-Fin-Case-Permissions": "current_product:read,current_product:request_repair",
        },
      },
    );
    const state = await initialResponse.json();
    const requestId = "current_return_browser_proof";
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({
        ...state,
        event_count: state.event_count + 1,
        return_requests: [
          ...state.return_requests,
          {
            request_id: requestId,
            action_type: "return_for_repair",
            status: "repair_requested",
            case_key: "NVDA",
            target_surface: command.target_surface,
            target_view_digest: command.expected_target_view_digest,
            target_ref: command.target_ref,
            reason_code: command.reason_code,
            reviewer_note: command.reviewer_note,
            repair_owner: "evidence_operator",
            requested_resolution: "current_evidence_repair",
            actor_ref: command.actor_ref,
            requested_at: "2026-08-05T23:30:00+08:00",
            qualified_human_review: false,
            automatic_repair_execution: false,
          },
        ],
        replay_digest: "b".repeat(64),
        T07_handoff: {
          ...state.T07_handoff,
          status: "repair_required_before_qualified_review",
          open_return_request_ids: [requestId],
        },
      }),
    });
  });

  await page.goto("/current/NVDA/report");
  await expect(page.getByTestId("current-report")).toContainText("NVDA 三单元内部研究备忘录");
  await page.getByRole("button", { name: "针对当前“交付报告”请求返修" }).click();
  await page.getByLabel("返修说明").fill("需要补充权威证据并明确说明判断边界。");
  await page.getByRole("button", { name: "记录返修请求" }).click();
  await expect(page.getByTestId("current-repair-control")).toContainText("1 个返修请求待处理");
  await expect(page.getByTestId("current-repair-control")).toContainText("需要补充权威证据并明确说明判断边界。");
  await expect(page.getByTestId("current-repair-control")).toContainText("未认证 · 尚未执行（归 T07）");
  await expect(page.getByTestId("current-report")).toContainText("NVDA 三单元内部研究备忘录");
});

test("unknown case URLs fail closed to the registered case set", async ({ page }) => {
  await page.goto("/current/AMD/case");
  await expect(page.getByRole("heading", { name: "DELL 研究工作台" })).toBeVisible();
  await expect(page).toHaveURL(/\/current\/DELL\/case$/);
  await expect(page.getByTestId("case-AMD")).toHaveCount(0);
});
