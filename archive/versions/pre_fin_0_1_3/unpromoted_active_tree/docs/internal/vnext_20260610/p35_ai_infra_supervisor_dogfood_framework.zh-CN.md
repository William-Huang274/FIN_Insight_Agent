# P35 AI Infra Supervisor Dogfood Framework

本文件是 no-paid deterministic dogfood 产物：先把用户题面需要的研究框架固化，再对照当前 P34 runtime rows 和 WorkBuddy 样本检查缺口。不调用 LLM，不跑 full-chain。

## 最终输出预期

- 开头必须是 TL;DR 判断和五链条决策面，不是数据 lineage 或边界声明。
- 决策面覆盖 Accelerator、Server OEM、Foundry/Packaging、HBM、Semicap。
- 每个链条都要回答 demand proof、capture mechanism、revenue evidence、profit quality、bottleneck monetization、margin dilution、capex digestion、export control、price-in、counter-thesis、source grade、numeric sanity。
- 官方披露、parser row、二级估算、推断和 attempt-backed gap 必须分层标注。
- 如果当前库不够，supervisor 必须补源或写清楚 source-hunter attempt，而不是直接把报告写成边界声明。

## 决策面规模

- 产业链环节：`5`。
- 判断维度：`12`。
- 决策单元格：`60`。

## 当前系统审计摘要

- P34 accepted runtime rows：`21`。
- P34 typed gaps：`2`。
- P34 quality audit：`bounded_quality_audit_pass_scoped_writer_allowed_full_chain_blocked`；full-chain allowed：`False`。
- WorkBuddy HTML samples read：`9`。
- Missing decision-surface cells：`25`。

## 关键缺口

### p35_case_scope_mismatch

- 层级：`case_definition`。
- 发现：P34 grew out of the AI/Semis gold case around accelerator, Dell, customer deployment, capex, semicap read-through, and market boundary. The user case now asks for a full five-segment industry decision surface that explicitly includes HBM, SMCI/HPE, CoWoS pricing, semicap peer split, and price-in.
- 影响：The current runtime can pass P34 gates while still failing the user's visible question.
- 修复方向：Make the decision surface the upstream contract, not a renderer afterthought.

### p35_decision_surface_not_runtime_contract

- 层级：`research_lead_to_writer_contract`。
- 发现：P34 has judgment chains and fact-table blocks, but no segment-by-dimension decision surface with required fields for every cell. The verifier therefore checks lineage and typed gaps more strongly than front-office completeness.
- 影响：A report can be safe yet incomplete; the user experiences it as boundary-heavy.
- 修复方向：Inject decision-surface cells into Research Lead, source routes, specialist outputs, MemoLogicPlan, and verifier.

### p35_source_hunter_loop_absent

- 层级：`source_route_runtime`。
- 发现：Current P34 source routes are predetermined by 20 evidence slots. WorkBuddy instead repeatedly searches and fetches until the story has enough surface area.
- 影响：Our RAG/graph/sql assets do not automatically compensate when the specific case surface is under-specified.
- 修复方向：Add a supervisor source-hunter loop that opens missing decision-surface cells, tries official first, then graded secondary sources, and writes supplement rows.

### p35_parser_depth_vs_context_rows

- 层级：`parser_adapter`。
- 发现：P34 accepted rows include useful official context, but several rows are context_summary rather than extracted value/unit/period/product table cells.
- 影响：Writer receives enough material to say what cannot be inferred, but not enough numbers to rank segments with confidence.
- 修复方向：Prioritize official IR/press/PDF table extraction for HBM, CoWoS, server OEM peers, semicap bookings/backlog, and capex/depreciation.

### p35_output_product_surface_gap

- 层级：`deliverable_surface`。
- 发现：WorkBuddy renders polished HTML/ECharts-style artifacts by default. FIN currently projects memo/workpaper text and Workbench review surfaces, but the report product is not yet optimized for decision scanning.
- 影响：Even when our evidence is better governed, users compare the visible artifact first.
- 修复方向：Treat decision tables, heatmaps, and source-grade appendices as first-class render targets.

## 本轮未运行

- `paid_llm`
- `true_full_chain`
- `model_comparison`
- `case_expansion`
- `release_eval`
