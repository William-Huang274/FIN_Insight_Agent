# 030 S7 Deliverable Studio / Dashboard Projection L4 Scope Artifacts

日期：2026-06-29

## 目标

把 R53-R60 S7 从规划落成可审计的 Deliverable Studio / Dashboard Projection：基于 S5 review-ready Workpaper 和 S6 SQL-final task projection，生成 Markdown、Word、Excel appendix 和 dashboard JSON，并把 render job、artifact refs、composer permission gate、quality gate 写入 SQL 主账本。

## 本轮完成

- 新增 `src/sec_agent/r53_r60_deliverable_studio_dashboard.py`，定义 S7 schema、DeliverablePlan、NarrativeSurfaceContract、RenderJob、DashboardProjection、ComposerPermissionGate、DeliverableQualityGate、summary 和 closeout report。
- 新增 `scripts/engineering/build_r53_r60_s7_deliverable_studio_dashboard.py`，可从仓库根目录重建 S7 投影和交付物。
- 扩展 `apps/workbench/backend/app.py`，新增：
  - `GET /api/r53-r60/tasks/{task_id}/deliverables`
  - `POST /api/r53-r60/tasks/{task_id}/render-deliverables`
  - `GET /api/r53-r60/tasks/{task_id}/dashboard-projection`
- 扩展 `apps/workbench/frontend/vite/src/main.tsx` 和 `workbench.css`，在 R53-R60 工作台新增：
  - Deliverable Studio；
  - render jobs / artifact refs；
  - composer permission gate；
  - dashboard projection；
  - deliverable quality gate。
- 新增 `tests/test_r53_r60_deliverable_studio_dashboard.py`，用临时目录重建 S5/S6 fixture 后验证 S7，不依赖本机真实 DB。
- 修复 S6 `collect_gate_rows` 的 slice 隔离：S6 drilldown 只展示 S0-S6 gate artifacts，后续 S7+ gate rows 不得污染 S6 projection。
- 更新 `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md` 的 S7 closeout。

## 生成物

- `configs/r53_r60/s7_deliverable_studio_dashboard_schema_v0_1.json`
- `data/manifests/r53_r60_s7_deliverable_studio_dashboard_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s7_deliverable_studio_dashboard_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_s7_deliverable_studio_dashboard_l4_scope_pass.zh-CN.md`
- runtime deliverables：`reports/deliverables/r53_r60/s7/s5_scope_task_workpaper_lead_review/`
- 私有 runtime DB：`data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`（不提交 Git）

## 结果

真实构建结果：

- DeliverablePlan：`1`；
- NarrativeSurfaceContract：`4`；
- RenderJob：`4`，覆盖 Markdown、DOCX、XLSX、dashboard JSON；
- DashboardProjection：`1`；
- ComposerPermissionGate：`1`；
- DeliverableQualityGate：`4 pass / 0 fail`；
- S7 gate rows：`10 pass / 0 fail`；
- release decision：`S7_L4_scope_pass`；
- next slice unlocked：`S8`。

## 验证

- `python -m py_compile src\sec_agent\r53_r60_deliverable_studio_dashboard.py scripts\engineering\build_r53_r60_s7_deliverable_studio_dashboard.py apps\workbench\backend\app.py`
- `python scripts\engineering\build_r53_r60_s7_deliverable_studio_dashboard.py --root .`
- `python -m pytest tests/test_r53_r60_deliverable_studio_dashboard.py tests/test_workbench_backend.py -q`
- S0-S7 regression：
  - `python -m pytest tests/test_r53_r60_unified_backlog.py tests/test_r53_r60_runtime_task_spine.py tests/test_r53_r60_tool_sandbox_spine.py tests/test_r53_r60_retrieval_evidence_spine.py tests/test_r53_r60_context_graph_skill_registry.py tests/test_r53_r60_workpaper_lead_review_workflow.py tests/test_r53_r60_workbench_frontdoor_drilldown.py tests/test_r53_r60_deliverable_studio_dashboard.py tests/test_workbench_backend.py -q`
- Frontend build：
  - `node node_modules\typescript\bin\tsc -p tsconfig.json`
  - `node node_modules\vite\bin\vite.js build --config vite.config.ts`

## 边界

S7 只证明 deterministic Deliverable Studio / Dashboard Projection 范围达到 `L4_scope_pass`：交付物计划、渲染任务、artifact refs、dashboard projection、Composer 权限和交付质量 gate 可审计、可回放、可追责。

本轮不做：

- 客户可直接发布的人工编辑质量；
- PPT 模板系统；
- Composer 自行检索或取新证据；
- 多租户 / RBAC / 高并发 SLA；
- full-chain answer quality eval。

这些留给后续 S8-S10 和产品化 hardening。

## 后续

- S8：Secondary Market / Capital Feedback Pack，把 ownership、credit/funding、liquidity/positioning、valuation price-in、derivatives 等二级市场/资本反馈数据作为独立 pack 接入。
- S9：Research-to-Quant Lab，把 Workpaper thesis driver 转成 FactorHypothesis 并进入 human approval / PIT / backtest。
- S10：全产品 release candidate，把 S0-S9 的 `L4_scope_pass` 汇总为系统级 release readiness。
