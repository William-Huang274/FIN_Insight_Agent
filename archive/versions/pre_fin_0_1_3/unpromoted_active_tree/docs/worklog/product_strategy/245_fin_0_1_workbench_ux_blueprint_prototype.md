# 245 - FIN 0.1 Workbench UX Blueprint and Clickable Prototype

## Status

`DRAFT_VISUAL_PROTOTYPE_USER_DECISION_PENDING`

## Date

2026-07-19

## Why this work exists

The current Workbench exposes substantial backend capability but composes it as object pages, approval states, persistent multi-column chrome, and technical fields. Repeated CSS and page-level additions did not fix the product model. This iteration stops implementation changes and creates a design freeze candidate before further frontend work.

## Product decision embodied

- Global level: Task Center for persistent institutional multi-case work.
- Case level: WorkBuddy-like research workspace.
- Primary composition: structured Research Run thread + Artifact Canvas + on-demand Inspector.
- Agents, models, tools, skills, graph, orchestration, and budgets are summarized in Run Profile.
- Raw chain-of-thought is never exposed; structured events and auditable outcomes are.
- Analyst, Review, and Inspect are distinct modes over the same Case.
- Evidence is a decision matrix, Workpaper is a structured editable artifact, Report is a decision narrative, and Senior Review is inline with the exact claim context.

## Durable artifacts

- `docs/product/FIN_0_1_WORKBENCH_UX_BENCHMARK_INTERACTION_BLUEPRINT_20260719.zh-CN.md`
- `docs/product/prototypes/fin_0_1_workbench_next/index.html`
- `docs/product/prototypes/fin_0_1_workbench_next/styles.css`
- `docs/product/prototypes/fin_0_1_workbench_next/prototype.js`
- `docs/product/design_assets/fin_0_1_workbench_next/*.png` after Playwright render

## Engineering assessment

The existing typed API clients and feature-domain logic are reusable. The current shell and accumulated page CSS should not be extended incrementally. The recommended implementation path is a feature-flagged `CaseWorkspaceNext` shell inside the same React/Vite application, with deep-link adapters for existing routes. A separate frontend package remains an explicit clean-break option, but it carries dual-frontend drift risk.

## Current authority boundary

This prototype is disconnected from runtime and backend data. It does not change Point status, release admission, operational qualification, authority, receipts, secrets, external calls, or real Case state. It is a product-design decision artifact only.

## Verification

- JavaScript syntax: `node --check` passed.
- Browser routes rendered: Task Center, Case Ready, Case Running, Evidence Matrix, Workpaper, Senior Review, Report Complete, Inspect.
- Playwright browser console/page errors: `0`.
- Interaction checks: Run Profile modal opens and closes; Ready starts Running; review action records selected state.
- Viewport checks: 1440x900, 1600x1000, and 1920x1080 have no horizontal overflow.
- Visual screenshots: eight 1600x1000 PNG files under `docs/product/design_assets/fin_0_1_workbench_next/`.
- Existing production frontend files changed: `0`.
- Backend/API/schema/runtime files changed: `0`.
- Network/model/provider/paid/full-chain/real Case mutation counts: `0`.

## Next decision

The user should review the eight rendered screens and decide:

1. Whether the Task Center + Case Workspace information architecture is correct.
2. Whether Thread + Canvas + Inspector is the correct Case composition.
3. Whether implementation should use the in-app replacement shell or a separate new frontend.

No production frontend migration should begin until those decisions are recorded.
