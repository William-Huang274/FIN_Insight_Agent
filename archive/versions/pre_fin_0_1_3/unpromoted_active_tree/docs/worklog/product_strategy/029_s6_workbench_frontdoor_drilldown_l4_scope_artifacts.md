# 029 S6 Workbench Frontdoor / Drilldown L4 Scope Artifacts

日期：2026-06-29

## 目标

把 R53-R60 S6 从规划落成可用的 Workbench frontdoor / drilldown：用户可以从前端任务中心看到 S1-S5 SQL-final runtime ledger 中的任务，并下钻到 Workpaper sections、ClaimCards、typed gaps、LeadReview、JudgmentState、context refs、gate rows、artifact refs、task events、review action 和 ops projection。

## 本轮完成

- 新增 `src/sec_agent/r53_r60_workbench_frontdoor_drilldown.py`，定义 S6 schema、API contract、SQL projection tables、gate rows、summary 和 closeout report。
- 新增 `scripts/engineering/build_r53_r60_s6_workbench_frontdoor_drilldown.py`，可从仓库根目录重建 S6 投影。
- 扩展 `apps/workbench/backend/app.py`，新增 `/api/r53-r60/*` 系列接口：
  - task list / task detail / task events；
  - task artifacts / drilldown；
  - review queue / review action；
  - resume / cancel；
  - ops projection / scope gate。
- 扩展 `apps/workbench/frontend/vite/src/main.tsx` 和 `workbench.css`，新增 R53-R60 工作台：
  - Task Center；
  - Lead / Judgment 摘要；
  - Workpaper sections；
  - ClaimCards；
  - typed gaps；
  - gate rows；
  - review queue 与 review action；
  - ops projection。
- 新增 `tests/test_r53_r60_workbench_frontdoor_drilldown.py`，用临时目录重建 S3-S5 fixture 后验证 S6，而不是依赖本机真实 DB。
- 更新 `docs/architecture/agent_graph_vnext/36_r53_r60_unified_demand_backlog_execution_plan.zh-CN.md` 的 S6 closeout。

## 生成物

- `configs/r53_r60/s6_workbench_frontdoor_drilldown_schema_v0_1.json`
- `data/manifests/r53_r60_s6_workbench_frontdoor_drilldown_gate_rows_v0_1.jsonl`
- `data/manifests/r53_r60_s6_workbench_frontdoor_drilldown_summary_v0_1.json`
- `docs/internal/vnext_20260610/r53_r60_s6_workbench_frontdoor_drilldown_l4_scope_pass.zh-CN.md`
- 私有 runtime DB：`data/workbench_private/research_data/r53_r60_runtime_task_spine_v0_1.sqlite`（不提交 Git）

## 结果

真实构建结果：

- Workbench API contracts：`11`；
- Workbench SQL projection tables：`6`；
- task projection：`s5_scope_task_workpaper_lead_review`；
- Workpaper sections：`6`；
- ClaimCards：`6`；
- typed gaps：`3`；
- task events：`12`；
- artifact refs：`3`；
- gate rows visible in drilldown：`58`；
- S6 gate rows：`8 pass / 0 fail`；
- release decision：`S6_L4_scope_pass`；
- next slice unlocked：`S7`。

## 验证

- `python -m py_compile src\sec_agent\r53_r60_workbench_frontdoor_drilldown.py scripts\engineering\build_r53_r60_s6_workbench_frontdoor_drilldown.py apps\workbench\backend\app.py`
- `python -m pytest tests/test_r53_r60_workbench_frontdoor_drilldown.py tests/test_workbench_backend.py -q`
  - 结果：`36 passed`
- Frontend build：
  - `node node_modules\typescript\bin\tsc -p tsconfig.json`
  - `node node_modules\vite\bin\vite.js build --config vite.config.ts`
  - 结果：通过

## 边界

S6 只证明 Workbench frontdoor / drilldown 范围达到 `L4_scope_pass`：任务中心、SQL-final drilldown、review action ledger 和 ops projection 可审计、可回放、可追责。

本轮不做：

- Markdown / Word / PPT / Excel deliverable generation；
- Dashboard projection 写回；
- full-chain answer quality eval；
- 多租户 / RBAC / 高并发 SLA；
- Java gateway 生产级路由。

这些留给 S7 / S10。

## 后续

- S7：Deliverable Studio / Dashboard Projection，基于 S5 Workpaper 和 S6 task drilldown 生成可审阅交付物。
- S8 / S9：secondary market / quant labs 继续作为后续功能 slice。
- S10：全产品 release candidate，把 S0-S9 的 `L4_scope_pass` 汇总为系统级 `L4_production_pass` 候选。
