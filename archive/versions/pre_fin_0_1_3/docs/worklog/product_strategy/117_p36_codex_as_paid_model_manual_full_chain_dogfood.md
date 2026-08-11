# 117 P36 Codex-as-Paid-Model Manual Full-Chain Dogfood

日期：2026-07-09

## 背景

用户确认：本轮不是运行 paid DeepSeek，而是让 Codex 自己进入 agent 链路，作为“paid DeepSeek”一样逐节点扮演强模型执行体。评价不能只凭使用体验，必须同时使用投研质量标尺和 agent 产品工程标尺。

额外约束：writer 阶段不能自己补源。Codex supervisor 可以补源，但必须单独记录，不能伪装成 agent runtime 能力。

## 本轮新增

- `docs/project_os/p36_agent_dogfood_ruler_v0_1.json`
- `docs/internal/vnext_20260610/p36_codex_as_paid_model_manual_full_chain_dogfood_execution.zh-CN.md`
- `docs/internal/vnext_20260610/p36_node_01_research_lead_manual_run.zh-CN.md`
- `docs/internal/vnext_20260610/p36_node_02_retrieval_rag_sql_source_route_manual_run.zh-CN.md`
- `docs/internal/vnext_20260610/p36_node_03_parser_evidence_operator_manual_run.zh-CN.md`
- `docs/internal/vnext_20260610/p36_node_04_graph_relationship_value_capture_manual_run.zh-CN.md`
- `docs/internal/vnext_20260610/p36_node_05_fundamental_specialist_manual_run.zh-CN.md`
- `docs/internal/vnext_20260610/p36_node_06_industry_product_specialist_manual_run.zh-CN.md`
- `docs/internal/vnext_20260610/p36_node_07_market_capital_price_in_specialist_manual_run.zh-CN.md`
- `docs/internal/vnext_20260610/p36_node_08_risk_counterevidence_specialist_manual_run.zh-CN.md`
- `docs/project_os/p36_manual_full_chain_node_ledger_v0_1.json`
- `docs/project_os/p36_supervisor_source_supplement_ledger_v0_1.json`
- `docs/internal/vnext_20260610/p36_node_10_writer_report_generation_manual_run.zh-CN.md`
- `docs/internal/vnext_20260610/p36_ai_infra_manual_writer_research_report.zh-CN.md`
- `docs/internal/vnext_20260610/p36_codex_as_paid_model_dogfood_recap_report.zh-CN.md`

## 已记录的节点

### `node_01_research_lead`

已读取：

- `src/sec_agent/prompts/skills/research_lead_planning_skill_v0_1.md`
- `src/sec_agent/prompts/skills/evidence_requirement_and_sufficiency_skill_v0_1.md`
- `src/sec_agent/prompts/skills/fundamental_analysis_skill_v0_2.md`
- `src/sec_agent/prompts/skills/industry_supply_chain_analysis_skill_v0_2.md`
- `src/sec_agent/prompts/skills/market_valuation_analysis_skill_v0_2.md`
- `docs/project_os/p35_ai_infra_decision_surface_framework_v0_1.json`
- `docs/project_os/p35_ai_infra_current_system_gap_audit_v0_1.json`

结果：

- Research Lead 可以在 P35 decision surface 手工注入后，产出可用 thesis path、required items、source-route plan、specialist assignment、missing-but-retrievable、bounded/commercial gaps 和 writer order。
- 但这暴露了一个工程事实：P35 decision surface 仍不是 Research Lead 原生 runtime contract；目前是 Codex supervisor 手工注入。
- 当前节点不补源，符合 Research Lead prompt 约束。

### `node_02_retrieval_rag_sql_source_route`

新增文档：

- `docs/internal/vnext_20260610/p36_node_02_retrieval_rag_sql_source_route_manual_run.zh-CN.md`

已读取/调用：

- agent registry / contracts / MCP tool registry / market snapshot / P34 lane runtime。
- P34 source route plan、live route attempts、goldcase availability alignment。
- P35 gap audit and source supplement ledger。
- ObjectBM25 本地索引：`sec_investment_coverage_mixed_with_8k_fy2023_2027_objects`、`sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects`。
- Market evidence packs and capital ownership rows。

结果：

- P34 runtime rows 有价值：21 条 accepted runtime rows + 2 条 typed gaps，能支撑 scoped memo 的局部判断。
- 但这些 rows 是旧 20 个 evidence slots 的 source-route replay，不是当前用户问题所需的 5 链条 x 多维度 decision surface。
- ObjectBM25 能召回 NVDA/MU/AMAT/MSFT/META/DELL/SMCI/HPE/LRCX/KLAC 等官方 filing 候选，但 index 选择很敏感，且 recall hits 不会自动进入 parser/exact-value promotion。
- Market snapshot 能给 13 个相关 ticker 的 price action / volatility rows，13F/ownership rows 也存在；但 valuation coverage 不完整，并且没有接入 P34 price-in decision cell。
- 非美和 IR/PDF/press-release 表格仍是主要 runtime 缺口，尤其 SK hynix、Samsung、TSMC、ASML。

工程判断：

- writer 不能自发补源的边界是对的。
- 当前缺的是 writer 前的 `SourceHunterLoop` / parser promotion / cell-level retrieval coverage map。
- 因为没有 `DecisionSurfaceContract` 驱动检索，RAG/SQL/market/ownership 明明有部分材料，却不会自然变成用户可见的研究判断。

### `node_03_parser_evidence_operator`

新增文档：

- `docs/internal/vnext_20260610/p36_node_03_parser_evidence_operator_manual_run.zh-CN.md`

已读取/调用：

- `sec_query_exact_value_ledger` over `sec_investment_coverage_mixed_with_8k_fy2023_2027_core_ledger.duckdb`
- `sec_query_exact_value_ledger` over `sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_core_ledger.duckdb`
- `exact_slot_rows_v0_1.jsonl`
- `industry_operating_metric_slot_rows_v0_1.jsonl`
- `product_kpi_source_specific_verifier_*`

结果：

- 基础财务不是缺失。sector-depth ledger 能召回 DELL / SMCI / HPE / MU / AMAT / LRCX / KLAC 的 revenue、gross margin、gross profit、net revenue 等行。
- exact slot rows 覆盖本 case 多数 ticker，包括 AMD、HPE、ASML、NVDA、AMAT、DELL、MU、SMCI、KLAC、Samsung、LRCX、TSM、SK hynix。
- 但业务线经济性仍缺：AI server gross margin、GPU pass-through、HBM-only revenue/margin、CoWoS pricing/capacity/allocation、semicap AI-specific bookings/backlog。
- Parser/promotion 有 sanity 风险：NVDA gross margin query 返回 `1.0` / `-1.2` `usd_millions` 这类疑似 delta/表格局部值；SMCI 有 `usd_thousands` 与 `usd_millions` 重复；ASML industry operating rows 出现 inventory / bank accounts 等被 product-revenue-like 归类。
- Product KPI verifier 很安全但太稀疏，21,838 candidates 只 promote 12 rows / 1 ticker。

工程判断：

- Exact-Value Ledger 是 metric-family query，不是 decision-cell promotion API。
- 多个 store / manifest 各自有价值，但没有统一的 cell-level promotion result。
- 如果直接给 writer，数值可能被误用；如果完全不给 writer，结果就会边界声明过多。
- 需要在 writer 前加入 headline selector、unit/period sanity、row-label sanity、parser false-positive review 和 decision-cell promotion ledger。

### `node_04_graph_relationship_value_capture`

新增文档：

- `docs/internal/vnext_20260610/p36_node_04_graph_relationship_value_capture_manual_run.zh-CN.md`

已读取/调用：

- relationship graph / ProductRelationshipGraph / ProductIntelligenceGraph / Research Graph Store 代码和测试。
- `relationship_graph_lookup` runtime-like 查询。
- ProductIntelligenceGraph SQLite / company packs。
- Research Graph Store SQLite / summary。
- P33 capital-market feedback fixture。

结果：

- 图谱资产不是没有。ProductRelationshipGraph 有 603 companies / 25,251 edges，ProductIntelligenceGraph 有 71,034 edges / 603 company packs，Research Graph Store 有 100,145 edges / 113,199 support rows，P33 capital-market feedback 有 14,706 signals / 4,221 graph edges。
- ProductIntelligenceGraph 是真实潜在优势：能按 ticker 给出产品槽、exact product KPI、industry operating metric、deployment/supply-chain signal 和 typed gaps。它对 DELL / SMCI / HPE / TSM / ASML / MU / SK hynix / Samsung 等都有结构化材料。
- 但图谱还不是 value-capture graph。`relationship_graph_lookup` 对 product edge 的 ticker extraction / focus filtering 不够好，结果里 `related_ticker` 经常为空，不同 focus 都扫出 568 graph rows。
- ProductIntelligenceGraph 没有投射到本 case 的 decision surface；Research Graph Store 证明 evidence support，但不表达 value-capture direction、economic materiality 或 risk-transmission strength。
- P33 capital-market feedback graph 存在，但 `market_valuation_analyst` 当前只吃 `market_snapshot`，没有把 valuation / ownership / derivatives / liquidity pack 接到本 case writer payload。

工程判断：

- 图谱应从 `scope/evidence-support graph` 升级为 `DecisionSurfaceGraphProjection` / `GraphToDecisionCellProjection`。
- 否则图谱边界声明会增加合规文本，但不会提升用户看到的报告主干。
- 这也是 multi-agent 的关键分水岭：如果图谱不能把关系转成业务线经济问题和可验证 source routes，multi-agent 只是更复杂的 DAG。

### `node_05_fundamental_specialist`

新增文档：

- `docs/internal/vnext_20260610/p36_node_05_fundamental_specialist_manual_run.zh-CN.md`

已读取/调用：

- `src/sec_agent/prompts/skills/fundamental_analysis_skill_v0_2.md`
- `src/sec_agent/prompts/skills/shared_evidence_boundary_skill_v0_1.md`
- `src/sec_agent/specialist_llm.py`
- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/role_evidence_selector.py`
- `src/sec_agent/agent_registry.py`
- ProductIntelligenceGraph SQLite。
- SEC / sector-depth DuckDB ledgers。
- Product KPI verifier / industry operating metric summary。

结果：

- Fundamental skill/prompt 本身方向是对的：要求从 required claim slots 出发，优先读 `fundamental_statement_pack` / peer panel，保持 period role，不能乱推 peer comparison，也要求 AI/Semis 财务桥接。
- 真实问题在输入投射。`fundamental_analyst` 是 inspect-only、无工具权限；如果上游没有把 PIG、operating metrics、exact ledger rows 变成 cell-ready `fundamental_statement_pack` / `fundamental_peer_statement_panel` / promoted product evidence rows，specialist 不会自己补。
- registry 虽允许 fundamental 使用 `company_product_evidence_graph`，但 data view 只有在 rows 带合格 `promotion_status` 并进入 `product_evidence_rows` / `context_rows` 时才会稳定消费。
- 项目内可见材料足以写 partial memolet：Accelerator 收入/毛利方向、Server OEM revenue proxy 与 margin risk、TSM HPC exposure、Memory segment exposure、Semicap baseline quality。不能写完整 HBM-only margin、CoWoS economics、AI server-only gross margin、semicap AI-specific backlog 和 price-in。
- ledger/PIG 探针还显示 sanity 风险：AMD 8-K revenue 行可能混到 percent change，MU gross margin 行可能返回美元金额，AMAT/KLAC headline 与 change/delta 行可能混在一起，PIG product/operating rows 也可能重复或 period-role 不清。

工程判断：

- Fundamental Specialist 不是主要坏点。
- 当前缺的是 `DecisionSurfaceContract -> EvidenceOperator -> ProductIntelligenceGraph / exact ledger / operating metric -> FundamentalStatementPack` 的投射链。
- 如果输入包不改，这个节点即使用强模型也会自然输出 missing confirmations / boundary prose；不是因为它“不愿意分析”，而是它没有被给到可安全使用的 cell-level financial pack。

### `node_06_industry_product_specialist`

新增文档：

- `docs/internal/vnext_20260610/p36_node_06_industry_product_specialist_manual_run.zh-CN.md`

已读取/调用：

- `src/sec_agent/prompts/skills/product_technology_analysis_skill_v0_1.md`
- `src/sec_agent/prompts/skills/industry_supply_chain_analysis_skill_v0_2.md`
- `src/sec_agent/product_intelligence_runtime.py`
- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/specialist_llm.py`
- `product_intelligence_context_rows_for_state(...)`
- `build_agent_data_view("product_technology_analyst", state)`
- `build_agent_data_view("industry_supply_chain_analyst", state)`

结果：

- Product / Industry skill 本身方向是对的：Product 节点清楚区分 exact product KPI、taxonomy、deployment、supply-chain signal 和 commercial gap；Industry 节点要求 chain map、transmission mechanism、confirmation metrics。
- PIG autoload 是真实优势。13 个 case tickers 用 runtime-like budget 能加载 `592` rows，其中 exact product KPI `112`、relationship edge `174`、deployment `24`、industry operating metric `41`、gap `10`。
- 但 Product Specialist 最终 bounded rows 只有 `48`，主要是 product slots：`product_slot=35`、profile/spec `7`、relationship `5`、gap `1`。`ProductSpecPack` summary 里虽有 `product_kpi_ref_count=32`，但最终 rows 没充分暴露 exact KPI，容易让模型偏 taxonomy/context。
- Industry Specialist 最终 bounded rows 也是 `48`，但在最小 state 探针里被 SK hynix / Samsung 的 memory relationship rows 占满，`000660.KS=25`、`005930.KS=23`，其它链条没进入最终 rows。
- `template_context_edge` 被过滤是正确边界，但意味着如果 upstream relationship graph 没另外传入具体 rows，server OEM / foundry / semicap 链条可能在 Industry prompt 里缺失。

工程判断：

- PIG / ProductEvidencePack 是我们区别于 WorkBuddy 的真实资产，但当前 selector 没把它投射成用户题面的五链条 decision surface。
- 这个节点比 Fundamental 更能讲故事链，但仍不能直接写 backlog、order、allocation、share、ASP、margin。
- 下一步需要 `ProductIndustryDecisionSurfaceProjection`：按 Accelerator / Server OEM / Foundry-Packaging / HBM / Semicap 每条链分配 rows、KPI、relationship、deployment、gap 和 what-would-change。

### `node_07_market_capital_price_in_specialist`

新增文档：

- `docs/internal/vnext_20260610/p36_node_07_market_capital_price_in_specialist_manual_run.zh-CN.md`

已读取/调用：

- `src/sec_agent/prompts/skills/market_valuation_analysis_skill_v0_2.md`
- `src/sec_agent/agent_registry.py`
- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/capital_macro_pack.py`
- 2026-06-24 603 ticker market snapshot pack。
- 2026-05-27 full78 FMP valuation-enriched market pack。
- `capital_ownership_rows.jsonl`
- P33 capital-market feedback fixture。
- `build_agent_data_view("market_valuation_analyst", state)`
- `build_capital_macro_pack(state)`

结果：

- Market skill 本身边界正确，但 registry/data view 把该节点实际定义为 `market_snapshot` specialist，不是完整 Market / Capital / Price-in specialist。
- 2026-06-24 market snapshot 覆盖本 case 13 个 ticker，可写 price action / volatility / relative return context，但所有 ticker 都缺 valuation multiples。
- 2026-05-27 valuation-enriched pack 只覆盖本 case NVDA / AMD / AMAT / MU，其中 NVDA / AMD 有 valuation multiples 和 event window。
- `capital_ownership_rows.jsonl` 对 NVDA/AMD/DELL/SMCI/HPE/ASML/AMAT/LRCX/KLAC/MU 有 154 条 capital/ownership rows；`build_capital_macro_pack()` 可生成 capital structure、debt、credit facility、ownership positions。
- P33 capital feedback 有 14,706 signals / 4,221 graph edges / 42 judgment material rows，但本 case 只覆盖 NVDA/AMD/DELL/ASML/SK hynix/Samsung 六个 ticker，且不被当前 market specialist 消费。
- `build_agent_data_view("market_valuation_analyst")` 在载入 17 条 market rows 和 154 条 capital/ownership rows 后，最终只给出 16 条 `market_snapshot` bounded rows；没有 `capital_macro_pack`，并且 nested `market_reaction` / `valuation_context` / `event_window` 主要被压缩进 summary 文本。

工程判断：

- 资本市场数据不是完全没有，问题是 market snapshot、capital macro pack、P33 capital feedback、ownership rows 被拆散，没有共同的 price-in decision-surface output contract。
- 当前节点能写出有用的 price action memolet，但写不出完整 price-in / crowding / valuation risk matrix。
- 下一步需要 `MarketCapitalDecisionSurfaceProjection`，并考虑拆成 market snapshot、capital positioning、price-in risk 三个更清晰的 specialist 或 pack。

### `node_08_risk_counterevidence_specialist`

新增文档：

- `docs/internal/vnext_20260610/p36_node_08_risk_counterevidence_specialist_manual_run.zh-CN.md`

已读取/调用：

- `src/sec_agent/prompts/skills/risk_counterevidence_skill_v0_2.md`
- `src/sec_agent/prompts/skills/shared_evidence_boundary_skill_v0_1.md`
- `src/sec_agent/agent_registry.py`
- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/specialist_llm.py`
- `src/sec_agent/dimension_evidence_portfolio.py`
- `src/sec_agent/capital_macro_pack.py`
- `product_intelligence_context_rows_for_state(...)`
- `build_agent_data_view("risk_counterevidence_analyst", state)`

结果：

- Risk skill 本身方向正确，要求 stress-test strongest thesis components，并明确 AI/Semis strong pass 应覆盖 capex digestion、export control、customer concentration、margin dilution、supply bottleneck、pricing pressure、deployment delay 和 missing-but-retrievable evidence。
- Risk 节点比 Market 节点宽，能接 runtime ledger、context rows、market rows、industry rows、derived metrics、product evidence rows、public source rows，并会附 `capital_macro_pack`。
- 但它不会自动加载 PIG，也不会自动追加 relationship rows；如果上游没有把 PIG / relationship / supply-chain risk rows 投进 state，Risk 只能看见 market rows、gap refs 和 capital pack summary。
- Probe A 最小状态：17 条 market rows + 154 条 capital/ownership rows + 5 条 source gaps；最终 bounded rows 16 条，全部是 `market_snapshot`，虽然有 `capital_macro_pack` 和 5 条 bounded gap refs。
- Probe B 手工投射 PIG rows：加入 592 条 product_evidence_rows 后，bounded rows 仍只有 16 条，其中 company product graph 12 条、market snapshot 3 条、live context 1 条；数据更丰富，但不是 risk-specific，很多是 product/revenue slots，不是直接风险、冲突或 falsifier。
- Prompt selector 仍含旧 required ids：`req_dell_margin_quality`、`req_hyperscaler_capex`、`req_supply_chain`、`req_customer_deployment`，而不是 P36 的 margin dilution / supply bottleneck / capex digestion / export control / price-in cells。
- Risk role 的 CapitalMacroPack prompt projection 排除了 `ownership_positions`，会削弱 price-in / crowding / positioning 风险分析。

工程判断：

- Risk 节点是 multi-agent 本该体现增益的位置，但目前缺的是 `RiskCounterevidenceDecisionSurfaceProjection` 和 `RiskMatrixPack`。
- 它能写出有价值的 partial risk memolet：server OEM margin unsupported、price-in risk bounded、HBM/CoWoS economics gap、semicap export/backlog gap、capex digestion missing test。
- 但如果不做 risk-cell projection，它仍容易退化成“列缺口和边界”，而不是真正的反证矩阵。

### `node_09_aggregate_judgment_planner`

新增文档：

- `docs/internal/vnext_20260610/p36_node_09_aggregate_judgment_planner_manual_run.zh-CN.md`

已读取/调用：

- `src/sec_agent/multi_agent_contracts.py`
- `src/sec_agent/memo_logic_plan.py`
- `src/sec_agent/langgraph_orchestrator.py`
- `src/sec_agent/prompts/skills/judgment_plan_aggregation_skill_v0_1.md`
- `scripts/eval_multi_agent/run_p33_aggregate_judgment_plan_from_specialist_checkpoint.py`
- `tests/test_multi_agent_judgment_memo_verifier.py`
- `tests/test_memo_logic_plan.py`
- `tests/test_p33_aggregate_judgment_plan_runner.py`
- `aggregate_specialist_judgment_plan(...)`
- `verify_specialist_outputs_for_memo(...)`
- `attach_judgment_state(...)`
- `build_memo_logic_plan(...)`

结果：

- Aggregate/JudgmentPlanner 不是简单摘要器。它能保留 supported / unsupported / conflict，生成 `memo_thesis_plan`、`memo_thesis_pack`、`thesis_driver_pack`、`judgment_cards`、`thesis_path`，并让 MemoLogicPlan 禁止 writer 使用 `database_query`、`live_web_snapshot`、`retrieval`、`new_fact_generation`。
- 这证明 writer 不能补源是正确的 runtime boundary；补源应该在 writer 前由 source hunter / supervisor / parser route 完成。
- Probe A：我手工构造 P36 风格 specialist memolets，聚合器输出 `supported_claim_count=9`、`unsupported_claim_count=1`、`memo_writer_allowed=true`，但 section 仍是 `fundamentals / product_and_production / capital_and_financing / competition_and_market_position / industry_supply_chain / risk_and_counterevidence / evidence_gap`，不是五链条 matrix。MemoLogicPlan 因缺 `product_reasoning_frame` validation fail。
- Probe B：我强行把 ClaimCard `analysis_dimension` 写成 `chain_accelerator / chain_server_oem / chain_foundry_packaging / chain_hbm / chain_semicap`，聚合层仍折叠成 generic analysis dimensions。MemoLogicPlan 可以 pass，但仍没有五链条 decision surface。
- 结论：当前 aggregate 层有真实价值，强在 writer-safety / thesis-path / unsupported 排除；弱在没有 case-specific `DecisionSurfaceAdjudicator`。它无法把 WorkBuddy-style decision matrix 作为主输出面，只能给 writer 一个通用 memo plan。

工程判断：

- 这是 multi-agent 能否真正超过联网 single-agent 的关键断点。
- 如果没有 `DecisionSurfacePack`，RAG / SQL / 图谱 / parser / skill 最后仍会被压缩成通用维度和边界话术。
- 需要在 specialist memolets 与 MemoLogicPlan 之间新增 `DecisionSurfaceAdjudicator`，保留 `decision_surface_cell_id`、`chain_segment_id`、`evidence_quality_grade`、`real_demand_vs_proxy`、`numeric_sanity_status`、`cell_conclusion`、`what_would_change` 等字段。

### `node_10_writer_report_generation_manual_run`

新增文档：

- `docs/internal/vnext_20260610/p36_node_10_writer_report_generation_manual_run.zh-CN.md`
- `docs/internal/vnext_20260610/p36_ai_infra_manual_writer_research_report.zh-CN.md`
- `docs/internal/vnext_20260610/p36_codex_as_paid_model_dogfood_recap_report.zh-CN.md`
- `docs/project_os/p36_supervisor_source_supplement_ledger_v0_1.json`

已读取/使用：

- Node01-09 已记录材料和 P36 node ledger。
- Codex supervisor 重新核验公开源：NVIDIA、Dell、SMCI、HPE、TSMC、SK hynix、Samsung、Micron、ASML、AMAT、LRCX、KLA、BIS。

结果：

- Runtime-only writer 可以写出 bounded partial report，但不能交付完整五链条 decision matrix。
- 完整报告依赖 supervisor supplement ledger；这些 source rows 不是 accepted runtime rows，也不是 evidence operator/parser 输出。
- 研究结论：AI 基建需求真实，但利润捕获不均。HBM 与 TSMC / advanced packaging 最像瓶颈租；NVIDIA 收入和毛利事实最硬但 export / capex digestion / price-in 风险集中；Server OEM 收入真实但 Dell/HPE 与 SMCI 显著分化；Semicap 是高质量滞后 capex read-through。
- Dogfood 结论：multi-agent 有治理价值，但缺 `DecisionSurfaceContract -> SourceHunterLoop -> parser promotion -> specialist cell packs -> DecisionSurfaceAdjudicator -> DecisionSurfacePack -> writer` 这条用户可见价值链。

工程判断：

- writer 禁止补源是正确边界，不能为了报告完整性放开。
- 补源应在 writer 前由 SourceHunterLoop / parser / Workbench cell review 完成。
- Node10 新增 root cause：报告质量依赖 supervisor supplement，而不是 runtime 已生成 DecisionSurfacePack。

### `node_11_verifier_workbench_review`

新增文档：

- `docs/internal/vnext_20260610/p36_node_11_verifier_workbench_review_manual_run.zh-CN.md`
- `docs/project_os/p36_verifier_workbench_review_v0_1.json`

已读取/审查：

- `src/sec_agent/memo_llm.py`
- `src/sec_agent/p33_workbench_artifact_review_surface_fixture.py`
- `src/sec_agent/r53_r60_workbench_frontdoor_drilldown.py`
- `apps/workbench/backend/app.py`
- `tests/test_multi_agent_judgment_memo_verifier.py`
- `tests/test_multi_agent_memo_llm_repair.py`
- `tests/test_p33_workbench_artifact_review_surface_fixture.py`
- `tests/test_workbench_backend.py`
- Node10 研究报告、dogfood 复盘报告、supervisor supplement ledger。

结果：

- Runtime-only writer 只能判 `pass_as_bounded_partial_only`，不能判完整研究报告通过。
- Supervisor-augmented report 可判 `pass_for_manual_human_reading_with_supplement_boundary`，但必须同时判 `fail_as_runtime_capability`。
- Verifier 当前能审 raw rows / tool calls / unsupported claims / source-boundary misuse，也能允许 bounded blocked answer；但它审的是 memo claim / evidence ref / source family，不是 P36 五链条 decision cells。
- Workbench 当前能展示 task、sections、ClaimCards、typed gaps、gates、artifacts、events 和 append-only review actions；但 review target 仍是 claim/gap/judgment/artifact 级，不是 `decision_surface_cell`。
- Node11 新增 root cause：verifier / Workbench 能守边界，但缺 decision-cell review surface。

工程判断：

- P36 到 Node11 已完成手工 dogfood 闭环，但不能被记为 runtime pass。
- 下一步不应直接 paid rerun、broad full-chain 或模型对比，而应先做 no-paid deterministic `DecisionSurfacePack` 与 Workbench `decision_surface_cell` review fixtures。
- Supervisor supplement ledger 是下一轮 SourceHunterLoop / parser / runtime-row fixture 的输入队列，不是 runtime success evidence。

## 追加记录：检索 / 数据库 / reranker 问题

记录时间：2026-07-09

用户追问：P36 暴露的“召回强，精度和提权弱”是不是 reranker 问题；“数据没有按用户问题的决策格进入 runtime payload，并且 DB 查数缺少足够严格的 row 选择与数值审计”具体是什么意思。

结论：这不是单纯 reranker 问题。reranker 只能解决“候选材料已经被召回以后，谁排在前面”的一段问题；P36 暴露的是 route selection、candidate recall、SQL/DB row selection、numeric sanity、authority promotion、DecisionSurface payload wiring 和 writer boundary 的组合问题。

### 分层判断

| 层级 | 是否主要是 reranker 问题 | P36 观察 |
|---|---|---|
| 候选材料排序 | 是，reranker 可改善 | 例如 `DELL gross margin / AI server margin` 召回后，reranker 可以把更像 AI server / ISG / margin 的材料排前。 |
| 该查哪个 index / ledger | 不是 | `sec_investment` 与 `sector_depth_full238` 覆盖差异很大；同一个 ticker / query 在一个库 0 hit，另一个库有 rows。需要 route planner / tool selection，不是 reranker。 |
| SQL 查数是否是正确事实行 | 主要不是 | DB 会把 change 列、百分比、cash flow、tax、cost of revenues、customer concentration 等混入 revenue / gross margin family。需要 row selector、cell_kind / metric_role / unit / period sanity。 |
| source 是否可提权为 exact fact | 不是 | RAG hit 或 DB row 排第一，不代表可给 writer。还要过 source authority、parser lineage、exact/bounded 分类、cannot-infer 边界和 promotion gate。 |
| 非美 IR/PDF / press release 是否进入 runtime | 不是 | TSMC、ASML、SK hynix、Samsung 等官方源可达，但没有稳定转成 accepted runtime rows；这是 ingestion / adapter / parser / source-route gap。 |
| market / ownership 是否进入 price-in cell | 不是 | market snapshot、valuation-enriched pack、ownership rows、P33 capital feedback 分散存在，但没有 MarketCapitalDecisionSurfaceProjection。 |
| writer 是否能写五链条矩阵 | 不是 | writer 已正确禁止补源；缺的是 writer 前的 DecisionSurfacePack。 |

### 具体发现

1. P34 旧 source-route 通过率不能等同于 P36 研究问题通过率。
   - P34 有 `20` 个 evidence slots、`21` 条 accepted runtime rows、`2` 条 typed gaps。
   - 这些 rows 支持 scoped memo，但按旧 20 个 slots 组织，不是按 P36 的五链条 decision surface 组织。
   - 因此看起来“slot 都有 attempt”，但用户真正要的 HBM / CoWoS / AI server margin / semicap price-in 等 decision cells 仍缺或只有 proxy。

2. 本地 RAG / ObjectBM25 召回能力不弱，但不会自动完成提权。
   - `sec_investment_coverage_mixed_with_8k_fy2023_2027_objects` 有 `1,118,234` object records。
   - `sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects` 有 `3,035,688` object records。
   - 对 NVDA、MU、AMAT、MSFT、META、DELL、SMCI、HPE、LRCX、KLAC 等能召回有用 filing / table / claim candidates。
   - 但 RAG hit 只是 retrieval candidate，不是 writer-ready fact；还要进入 parser / exact ledger / source-route attempt / typed gap / authority boundary。

3. DB 查数是“召回强，精度不够”。
   - `sec_investment` ledger 有 `131,773` facts，主要覆盖 NVDA / AMD / MU / AMAT。
   - `sector_depth` ledger 有 `2,257,112` facts，对 DELL / HPE / SMCI / KLAC / LRCX 等覆盖更强。
   - P36 case 实查显示：DELL `15,201` rows、HPE `15,148` rows、KLAC `11,899` rows、SMCI `7,702` rows、LRCX `6,617` rows。
   - 但关键词或 metric_family 查询会混入错行：NVDA gross margin 可查到正确 `74.9% / 75.0%`，也可查到 `1.0 / -1.2 usd_millions`；DELL gross margin 可混入 `Cash flow from operations`；SMCI revenue 可混入 advertising / percentage / change 句子；KLAC revenue 可混入 tax、cost of revenues、customer concentration。
   - 这说明需要 headline selector、unit sanity、period_role、cell_kind、metric_role、row_label、table_title 和 source_text 一起审，而不是只靠 reranker。

4. 业务线经济性仍是缺口，不是排序问题。
   - `CoWoS=0`、`GPU pass-through=0`、`HBM` 只在 MU 有极少命中，`AI server` 主要只有 DELL 少量命中。
   - DELL / HPE / SMCI 基础财务可查，但 AI server-only gross margin、GPU pass-through、attach economics、backlog conversion margin 没有 accepted runtime row。
   - TSMC 有公司级 primary disclosure / advanced node context，但 CoWoS capacity / pricing / customer allocation 未进 runtime。
   - SK hynix / Samsung / Micron 有公司级 disclosure / product surface，但 HBM-only revenue / margin / allocation peer panel 未形成 runtime pack。
   - Semicap 有 AMAT / LRCX / KLAC / ASML 部分 rows，但 AI-specific bookings / backlog / China exposure / WFE peer matrix 不完整。

5. market / ownership 数据存在，但没有 price-in decision surface。
   - market snapshot 对本 case 13 个 ticker 有 price action / volatility context，但 valuation fields 大量缺失。
   - valuation-enriched pack 只覆盖 NVDA / AMD / AMAT / MU。
   - capital / ownership rows 对 10 个 case ticker 有 `154` 条，且 CapitalMacroPack 能 pass。
   - 但 `market_valuation_analyst` 当前主要消费 `market_snapshot` bounded rows，不自然消费 CapitalMacroPack、ownership positions 或 P33 capital feedback。
   - 所以能写 bounded price-action memolet，不能写完整 price-in / crowding / valuation-risk matrix。

6. writer 不应自己补源，正确修复点在 writer 前。
   - writer 禁止 `database_query`、`live_web_snapshot`、`retrieval`、`new_fact_generation` 是正确边界。
   - 如果上游没有交付 cell-level accepted rows / typed gaps / forbidden claims，writer 只能写 bounded partial 或依赖 supervisor supplement。
   - P36 Node10 的完整报告依赖 `p36_supervisor_source_supplement_ledger_v0_1.json`，因此必须记为 `supervisor_supplement_only`，不能记为 runtime capability。

### 影响

- 不能把“加 reranker”当作 P36 的主修复。reranker 有用，但只是排序器，不是裁判。
- 真正要补的是 `DecisionSurfaceContract -> cell-level retrieval routes -> parser / SQL row selector -> numeric sanity -> authority promotion -> specialist cell packs -> DecisionSurfaceAdjudicator -> DecisionSurfacePack -> writer`。
- 每个 cell 需要输出：`cell_id`、`required_evidence`、`retrieval_routes_attempted`、`candidate_rows`、`accepted_rows`、`rejected_rows_with_reason`、`typed_gap`、`numeric_sanity_status`、`writer_allowed_claims`、`writer_forbidden_claims`。
- 后续讨论应追加到本节，尤其是 reranker 是否要训练 / 如何评估、SQL selector 如何做、SourceHunterLoop 是否先重检索 KB 再补官方源、DecisionSurfacePack 如何进入 Workbench review。

### 当前未运行

- 未运行 paid LLM。
- 未运行 true runtime full-chain。
- 未训练或替换 reranker。
- 未做 source ingestion / parser 修复。
- 未把本次本地 DB/RAG 探针结果伪装成 accepted runtime rows。

## 追加记录：Agentic Research Operating System 框架讨论

记录时间：2026-07-09

用户追问：当前各节点是否基本是一次性 prompt 注入后输出；是否应该让每个节点 agent 有持续思考、行动、查数、补缺口的能力；是否应让专家 agent 按需取数，由 Lead 注入数据库、知识库、tool use、subagent 能力后先做推理循环，再派发任务、审草稿、补叙事，writer 则专注输出质量和 WorkBuddy-like dashboard。

结论：产品最终形态不应停留在 static multi-agent pipeline，也不应只是“Lead 拆任务 + specialist 一次性回答 + writer 汇总”。更合理的方向是 `Agentic Research Operating System`：Lead 作为 `Research Controller` 维护完整 case control plane；specialist / evidence / parser / source hunter 在授权范围内执行 bounded tool-use loop；所有跨 agent 通信进入结构化 artifact 和 ledger；writer 不补源，但作为 `Research Presentation Agent` 负责语言、结构、表格、图表、dashboard board 和客户/内部口径。

### 本次形成的产品判断

1. Lead 应持有完整 case-level 上下文，但不应吞下所有 raw evidence。
   - Lead 的上下文应覆盖用户问题、追问、decision cells、任务派发、缺口、补源请求、叙事计划、writer 注意事项和 human review 状态。
   - raw rows、PDF、DB result、graph object、market pack 应留在 evidence / artifact store，由 Lead 持有 refs、摘要和状态。
   - 这样后续用户追问时，系统至少有一个控制层 agent 能解释“为什么这么判断、哪里缺、下一步查什么”。

2. Subagent 可以自主取数，但必须是 bounded、permissioned、audited。
   - 专家 agent 拿到任务后应做一次意图理解，并可在授权范围内调用 KB / SQL / RAG / graph / market / parser / SourceHunter。
   - 每轮行动应写入 `ToolUseLedger`、`EvidenceLedger`、`RejectedCandidateLedger`、`NumericSanityLedger` 或 `SpecialistCellPack`。
   - 不允许 subagent 无限扩查；必须有预算、route plan、stop condition、typed gap 和回到 Lead 的机制。

3. 不暴露原始 CoT，但要暴露可审计行动链。
   - 产品对象不应是“模型思维链文本”，而应是 `plan -> tool_call -> observation_summary -> decision -> rejection_reason -> next_action`。
   - 这能支持 review、debug、复盘和合规，同时避免把不可控的内部推理当成可依赖证据。

4. SourceHunter / 补源必须和知识库重检索区分。
   - 默认顺序应倾向于先做已有 KB / DB / RAG / graph route，再按 cell gap 触发 SourceHunter。
   - 如果强模型或人工 supervisor 手工补源，必须单独记录为 supervisor supplement，不能伪装成 runtime agent 自带能力。
   - 后续需要讨论哪些 official-source cell 可以直接触发 SourceHunter，哪些必须先证明 KB route 失败。

5. Writer 不应只是写手，但绝不能成为事实发现者。
   - Writer 应消费 `DecisionSurfacePack`、`WriterBrief`、approved evidence refs、typed gaps 和 Lead 的叙事要求。
   - Writer 的强项应是输出格式、用语、母语习惯、结构、表格、图表、dashboard-style board、客户版/内部版切换。
   - Writer 发现叙事断裂或证据不足时，应返回 `writer_blocker` 给 Lead，而不是自己查 DB、RAG 或联网补源。

6. 成稿前需要 Lead review checkpoint。
   - Lead 应审查 decision cells 是否覆盖、证据/缺口是否闭环、反方是否存在、故事线是否足以支撑 writer、writer forbidden claims 是否明确。
   - 如果不完整，应触发 targeted repair、specialist rework、SourceHunter 或 typed gap，而不是把问题推给 writer。

7. Workbench 应围绕 decision surface 展示，而不是只展示 memo claim。
   - P36 Node11 已暴露：当前 Workbench 能审 claim/gap/judgment/artifact，但缺 `decision_surface_cell` review surface。
   - 新框架要求 Workbench 展示 cell status、accepted/rejected candidates、numeric sanity、source boundary、repair history、human action 和 writer allowed/forbidden claims。

### 追加编排更改：repair / evidence layer / evidence compiler

记录时间：2026-07-09 续

本轮用户选中三段结论，要求把对应编排更改同步进 PRD 和记录文档。三条更改如下。

1. Repair ownership：Lead 负责 triage / reroute / adjudication，不是万能补源 agent。
   - 规则：`gap / failure -> Lead Repair Triage -> RepairTicket -> 来源节点或最有权限 agent repair loop -> RepairResult -> Lead adjudication`。
   - Lead-local repair 只覆盖用户问题理解、decision cell 拆分、assignment、stop condition、writer brief 和叙事路径。
   - KB/RAG route 错回 Evidence / Retrieval Agent；SQL row / numeric sanity 问题回 Parser / Numeric Agent；官方源缺失回 SourceHunter；图谱价值捕获问题回 Graph / Relationship Agent 或对应 specialist；market/capital 缺失回 Market / Capital Agent；专家判断太泛回对应 Specialist；语言/格式问题回 Writer，但 Writer 仍不得补事实。
   - 新增核心对象：`RepairTicket`，字段包括 `cell_id`、`gap_type`、`source_agent`、`owner_agent`、`reason`、`required_evidence`、`allowed_tools`、`budget`、`stop_condition`、`previous_rejections`、`writer_forbidden_claims`。

2. Evidence Layer：DB / RAG / 补源是共享证据能力，不是专家私有工具。
   - 专家 agent 可以提出结构化 `EvidenceRequest`，说明自己为什么需要证据、什么证据才够用、哪些 proxy 禁止使用。
   - Evidence Layer 负责查库、RAG、graph、market、SourceHunter、parser、authority gate 和 rejected candidate ledger。
   - 专家消费 `EvidenceResponse` / typed evidence pack 后生成 `SpecialistCellPack`，而不是直接把 raw DB/RAG/web rows 包装成判断。
   - DB query 主要是 deterministic tool；RAG/KB 是 tool + retrieval operator；Parser/Numeric 与 SourceHunter 是证据治理型 agent；Specialist 是业务判断 agent；Lead 是控制和裁决 agent。

3. Evidence / SourceHunter：不能靠通识完成不同角色需求，必须成为结构化证据编译器。
   - Evidence / SourceHunter 要把 specialist 的业务需求编译为 route、query、source policy、parser rule 和 evidence gate。
   - `EvidenceRequest` 至少包含 `cell_id`、`requester_role`、`evidence_domain`、`target_entity`、`metric_intent` / `product_intent`、`period`、`granularity`、`unit`、`acceptable_sources`、`acceptable_proxy`、`forbidden_proxy`、`stop_condition` 和 `clarification_policy`。
   - Evidence Orchestrator 应按 domain 路由：Financial Evidence Operator、Product Evidence Operator、Market / Capital Evidence Operator、Risk / Counterevidence Operator、SourceHunter。
   - 如果请求太模糊，返回 `clarification_needed`；如果公开源或现有库不披露，返回 typed gap / commercial gap；不得用通识补一个看似合理的事实。

本次同步的 PRD 位置：

- `修订记录` 增加三条编排规则；
- `7.2 Repair ownership 编排规则`；
- `7.3 Evidence Layer 与专家关系`；
- `7.4 Evidence / SourceHunter 作为结构化证据编译器`；
- `9.7 Agentic research workflow 验收` 增加 `RepairTicket`、`EvidenceRequest` 和 domain evidence operator 验收；
- `12 后续需拆技术文档` 和 `13 当前开放问题` 增加对应技术拆分与待定问题。

状态边界：这些更改仍是 PRD / worklog 层的 `documented` / `contract-design`，不是 runtime 已实现。未新增代码、未跑 fixture、未跑 paid LLM、未做 source ingestion、未把补源变成 accepted runtime rows。

### 已同步到 PRD

同日已把上述讨论追加进 `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`，并标注 2026-07-09 修改日期。主要新增位置：

- `修订记录`；
- `4.1.1 Agentic Research Operating System`；
- `6.2 Research Task Center` 的 `DecisionSurfaceContract` 扩展；
- `6.8 Deliverable Studio` 的 `Research Presentation Agent` 边界；
- `7.1 Agent 权限和通信边界`；
- `7.2 Repair ownership 编排规则`；
- `7.3 Evidence Layer 与专家关系`；
- `7.4 Evidence / SourceHunter 作为结构化证据编译器`；
- `9.7 Agentic research workflow 验收`；
- `10 指标`、`12 后续需拆技术文档`、`13 当前开放问题`。

### 当前未运行

- 未运行 paid LLM。
- 未运行 true runtime full-chain。
- 未修改 agent runtime。
- 未做 source ingestion / parser / reranker 修复。
- 未把本次框架讨论记为已实现能力。

## 下一步

进入 runtime repair backlog，而不是 full-chain rerun：

1. `DecisionSurfaceContract` fixture。
2. `SourceHunterLoop` fixture。
3. official press release / IR PDF parser fixture。
4. supplement ledger to runtime row fixture。
5. Product / Industry decision-surface projection fixture。
6. Market / Capital decision-surface projection fixture。
7. RiskMatrixPack fixture。
8. DecisionSurfacePack to MemoLogicPlan projection test。
9. Workbench `decision_surface_cell` review replay。
10. Agentic Research Operating System 技术设计：Lead Research Controller、CaseControlMemory、bounded tool loops、SourceHunterLoop、DecisionSurfacePack、WriterBrief 和 Workbench cell-level review。
11. `RepairTicket` / `EvidenceRequest` / Evidence Orchestrator / domain evidence operator 合同设计与 no-paid fixture。

## 未运行

- paid LLM API
- true runtime full-chain
- model comparison
- case expansion
- release eval

## 追加记录：P36 后 agent 框架落地与工具栈分层

记录时间：2026-07-09 续

用户追问：具体到项目应如何落地 Lead Controller + shared Evidence Layer + domain operators + RepairTicket + Writer no-source；落地后功能形态是什么；并补充一组工具项目：SEC EDGAR APIs、OpenBB、RSS/feedparser、GDELT、Crawl4AI、Crawlee+Playwright、news-please / Trafilatura、Docling、MinerU、MarkItDown、pdfplumber / Camelot。

### 本轮判断

这些工具总体有用，但不应作为“专家 agent 私有工具”散落在各节点里。正确落点是共享 Evidence Layer、SourceHunter、Parser / Numeric Agent、DocumentMetadataIndex 和 ArtifactConsistencyGraph。工具输出默认只是 candidate rows；只有通过 metadata filter、source authority、parser lineage、numeric sanity、promotion gate 和 cell-level adjudication 后，才能成为 writer-allowed evidence。

P36 后的落地核心不是先跑 paid writer，也不是先训练 reranker，而是补以下一等对象：

- `DecisionSurfaceContract`：用户问题到链条 x 决策格的合同。
- `DocumentMetadataIndex`：company、ticker、period、doc type、source authority、section、table lineage 必须进入 retrieval filter。
- `EvidenceRequest` / `EvidenceResponse`：专家按结构化需求取数，Evidence Layer 返回 accepted / rejected / gap / repair。
- `NumericProgramTrace`：所有 growth、margin、CAGR、bridge、peer comp、valuation multiple 可执行、可复算、可审。
- `DecisionSurfacePack`：writer 前的 report-first 中间态。
- `ArtifactConsistencyGraph`：memo、PPT、Excel、dashboard 的数字、口径、引用一致性检查。

### 落地后的功能形态

用户创建任务后，系统先显示 `Decision Surface Matrix`，而不是直接吐一篇 memo。例如 AI 基础设施任务：

- 行：Accelerator、Server OEM、Foundry/Packaging、HBM、Semicap、Cloud buyer、Power/Cooling。
- 列：demand evidence、value capture、margin quality、supply bottleneck、capex read-through、price-in/crowding、risk/counter-thesis、what-would-change。
- 每个 cell 有状态：`accepted`、`proxy_only`、`estimate_only`、`typed_gap`、`needs_source`、`needs_parser`、`needs_repair`、`human_review`。
- 点击 cell 展示 accepted evidence、rejected candidates、source grade、numeric trace、ToolUseLedger、RepairTickets。
- Workbench 同时展示 document grid、numeric trace drawer、artifact consistency review 和 repair queue。
- Writer 只能消费 `DecisionSurfacePack`、`WriterBrief`、approved refs 和 typed gaps，负责中文表达、表格、图表、dashboard board、Excel appendix、PPT outline，但不得补源。

流程应变成：

```text
User Task
 -> Lead Research Controller
 -> DecisionSurfaceContract
 -> EvidenceRequest Queue
 -> Evidence Orchestrator
 -> DB / RAG / Graph / Market / SourceHunter / Parser / Numeric Agent
 -> EvidenceResponse
 -> Domain Evidence Operators / Specialists
 -> DecisionSurfacePack
 -> NumericProgramTrace
 -> MemoLogicPlan + WriterBrief
 -> Writer no-source
 -> Memo / Dashboard / Excel / PPT
 -> ArtifactConsistencyGraph
 -> Workbench decision_surface_cell review
 -> RepairTicket loop
```

### 工具栈采用建议

| 层级 | 工具 | 采用判断 | 边界 |
| --- | --- | --- | --- |
| 官方披露 / 市场数据 | SEC EDGAR APIs、OpenBB | SEC EDGAR APIs 应作为美国公司 filing / XBRL / companyfacts 的一级官方 adapter；OpenBB 可作为 market / fundamentals / provider aggregation adapter | SEC 是 authority source；OpenBB 是 connector，authority 取决于底层 provider |
| 事件 / 新闻发现 | RSS/feedparser、GDELT | feedparser 适合 issuer/news RSS watch；GDELT 适合全球新闻、事件热度、跨语种风险 discovery | 只能做 discovery/context，不能直接晋升 issuer fact |
| 网页抓取 | Crawl4AI、Crawlee+Playwright | Crawl4AI 作为 SourceHunter 默认网页到 Markdown 候选；复杂 JS / 动态站点再用 Crawlee+Playwright | 必须 obey robots / terms / fair access；动态抓取成本高，需 tool ledger |
| 新闻正文抽取 | Trafilatura、news-please | Trafilatura 作为默认正文和 metadata 抽取；news-please 用于新闻站递归、RSS 和 archive 场景 | 新闻抽取结果需实体解析、去重、source grade、事实边界 |
| 文档解析主链路 | Docling、MinerU | Docling 做主力 PDF / Office / 图片结构化；MinerU 做复杂扫描件、复杂研报、公式/表格/OCR fallback | parser 输出必须带 page / section / table / cell lineage；MinerU 不应默认全量跑 |
| 轻量转换 | MarkItDown | 用于 Office、杂文件和快速 Markdown preview | 不替代表格级 parser、财务科目选择或 numeric sanity |
| 表格 fallback | pdfplumber、Camelot | 用于 machine-generated PDF 的表格抽取、视觉调试和单表 fallback；Camelot 适合 lattice / stream table | 只能产出 table candidates，需要 row selector 和 sanity gate |

工具触发顺序建议：

```text
Existing KB / DB / RAG / Graph route
 -> metadata-filtered retrieval
 -> parser / numeric sanity
 -> SourceHunter official-source supplement
 -> complex crawler / OCR fallback
 -> typed gap / commercial gap / human review
```

### 为什么不是直接改成“每个专家自己查”

如果让 Fundamental / Product / Market / Risk specialist 各自私有化 Crawlee、OpenBB、Docling 或 SQL，会出现四个问题：

1. 同一 source row 会被不同专家重复解释，source authority 和 parser lineage 不一致。
2. 专家容易把 RAG hit、news hit 或 table candidate 直接写成事实。
3. reviewer 无法在 Workbench 中按 cell 审 accepted / rejected / gap。
4. Writer 前仍然缺 `DecisionSurfacePack`，最终报告质量依旧靠强模型补脑。

因此工具要集中进 Evidence Layer；专家只发结构化 `EvidenceRequest`，解释自己需要什么证据、为什么需要、什么证据才够用、哪些 proxy 禁止使用。

### 已同步到 PRD

本轮已把上述内容追加进 `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`，并标注 2026-07-09 修改日期。主要新增：

- `4.1.2 P36 后目标落地形态`；
- `7.5 Evidence Layer 工具栈分层`；
- `8.8 B7：P36 Decision Surface / Evidence Tooling Repair Slice`；
- `9.7 Agentic research workflow 验收` 中新增 `DocumentMetadataIndex`、`NumericProgramTrace`、`ArtifactConsistencyGraph` 验收；
- `10 指标` 中新增 client-ready、senior-review-ready、cross-artifact consistency、numeric reproducibility、citation-clickthrough、workflow time saved 等指标；
- `12 后续需拆技术文档` 和 `13 当前开放问题` 增加 Evidence Tooling Stack、DocumentMetadataIndex、NumericProgramTrace、ArtifactConsistencyGraph 等技术拆分和待定问题。

### 外部主源核对

本轮只做工具定位核对，未做 PoC。参考主源包括：

- SEC EDGAR APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- OpenBB: https://github.com/OpenBB-finance/OpenBB
- feedparser: https://github.com/kurtmckee/feedparser
- GDELT data / API overview: https://www.gdeltproject.org/data.html
- Crawl4AI: https://github.com/unclecode/crawl4AI
- Crawlee: https://github.com/apify/crawlee
- news-please: https://github.com/fhamborg/news-please
- Trafilatura: https://github.com/adbar/trafilatura
- Docling: https://github.com/docling-project/docling
- MinerU: https://github.com/opendatalab/mineru
- MarkItDown: https://github.com/microsoft/markitdown
- pdfplumber: https://github.com/jsvine/pdfplumber
- Camelot: https://github.com/atlanhq/camelot

### 当前未运行

- 未运行 paid LLM。
- 未运行 true runtime full-chain。
- 未修改 agent runtime。
- 未做 source ingestion / parser / reranker 修复。
- 未做任何工具 PoC 或安装。
- 未把本轮工具判断记为 runtime capability。
- 未把 P36 supervisor supplement rows 写成 accepted runtime rows。

## 追加记录：Z 盘工具 PoC 与 agentic tool-use 三层

记录时间：2026-07-09 续

用户要求：把第一、第二优先级仓库先落到 Z 盘，并针对项目常见问题环节（动态网页、官方页面、PDF、文档、表格、RSS/news、market connector、复杂爬虫）用新增工具做测试，对比现有工具效果；随后追问这些技术栈是否应交给模型做工具调用，以及工具失败后是否允许模型重新选择工具。

### 本轮完成

仓库与 PoC 目录：

- repo root：`Z:\FinInsightToolBench\repos`
- 输出报告：`Z:\FinInsightToolBench\tool_bench_report_20260709.md`
- 原始输出：`Z:\FinInsightToolBench\bench_outputs`
- 下载样例：`Z:\FinInsightToolBench\bench_inputs`
- 主 PoC venv：`Z:\FinInsightToolBench\.venv`
- OpenBB isolated venv：`Z:\FinInsightToolBench\.venv_openbb`

已落地仓库：

- `docling`：HEAD `df7050b`
- `pdfplumber`：HEAD `4c64b92`
- `camelot`：HEAD `cd8ac79`
- `trafilatura`：HEAD `db7be91`
- `crawl4ai`：HEAD `987541e`
- `openbb`：HEAD `1c74893`
- `feedparser`：HEAD `19de310`
- `markitdown`：HEAD `e144e0a`
- `gdelt-doc-api`：HEAD `4122016`

SEC EDGAR APIs 是 API，不是 repo；本轮用 direct API / SEC Atom / RSS 做 smoke，对比现有 CompanyFacts / submissions 路径。

### PoC 结果摘要

1. 动态 official page / crawler：
   - TSMC quarterly results 静态 requests / Trafilatura 只能拿到少量页面文本，Crawl4AI 可抓到实际渲染后的季度表格，包括 net revenue、exchange rate、gross margin、operating margin 的 actual / guidance。
   - NVIDIA data center 页面 Crawl4AI 可保留大量 product link / Blackwell / line-card PDF 信息；当前 parser 只能产生 context rows，不能提权。
   - ASML annual report 页面 Crawl4AI 可发现大量 PDF 引用；financial-results 页面本身没有普通 PDF href。
   - 结论：Crawl4AI 应进入 SourceHunter 动态网页与 PDF locator discovery，但仍需 selector、source policy、budget 和 ToolUseLedger。

2. PDF / 表格解析：
   - `pdfplumber`：ASML Financial Performance PDF 10 页约 1.23s，NVIDIA line card 3 页约 0.25s；适合 fast first-pass text/table candidate。
   - `Camelot`：对 ASML 部分表格可用，但 NVIDIA line card stream/lattice 都失败；适合 page-targeted fallback，不能全量默认跑。
   - `MarkItDown`：快速转 Markdown，适合 data room preview / lightweight conversion；不替代表格级 parser。
   - `Docling`：ASML 年报财务表和 NVIDIA line card 表格结构保持最好，但成本高；NVIDIA 3 页首次约 228s，ASML 10 页约 37s。适合 heavy fallback，不适合默认热路径。
   - 结论：PDF fallback 顺序应按 doc type / cost 配置，推荐 `MarkItDown -> pdfplumber -> Camelot(page-targeted) -> Docling(heavy fallback)`。

3. RSS / GDELT / 新闻正文：
   - `feedparser` 配合 requests + controlled User-Agent 可解析 SEC NVDA 8-K Atom 10 条和 SEC US-GAAP RSS 200 条。
   - `GDELT` 可返回 NVIDIA Blackwell、TSMC capex 等新闻候选，并能配合 Trafilatura 抽正文，但结果混有低权重站点、转载、营销页。
   - 结论：feedparser 可作为 issuer / SEC / news feed watch；GDELT 只能做 event discovery / risk radar，不能直接晋升 issuer fact。

4. OpenBB / market connector：
   - full `openbb` 安装在 Python 3.12 环境下因依赖摩擦失败。
   - minimal `openbb-core + openbb-yfinance + openbb-equity` 可用，能通过 `obb.equity.price.historical` 取 NVDA OHLCV，约 4.19s 返回 26 行；quote、metrics、income 也可返回。
   - 结论：OpenBB 可降低 market/fundamental provider adapter 工作量，但 tested provider 是 yfinance，不是 authority upgrade；不能替代 SEC CompanyFacts exact facts，建议隔离为 connector/service。

5. 当前项目对比：
   - SEC CompanyFacts 仍是结构化 official fact 的强路径；NVDA CompanyFacts direct smoke 可返回 626 个 US-GAAP fact concepts。
   - 当前 `public_web_context_parser` 能产生 bounded context rows，也能看到部分 HTML table rows，但 `exact_value_authority=false`，不能直接 writer-allowed。
   - 核心短板仍是 source/page/table 已经可达，但缺 row selector、period/unit sanity、numeric audit、metadata lineage 和 promotion gate。

### Agentic tool-use 三层结论

本轮讨论后形成的新产品 / runtime 方向：

```text
模型负责选择和修复路径，
系统负责约束和验收。
```

也就是模型可以有工具选择权和失败后重试权，但没有 evidence promotion 权。

三层如下：

1. `Tool Registry`
   - 记录每个工具的 capability、source role、authority level、input/output schema、cost class、latency、budget、failure types、forbidden claims。
   - 模型只能在 registry 允许的 source role / budget / permission 内选择工具。

2. `Evidence Tool Planner`
   - 根据 cell-level `EvidenceRequest` 做 bounded ReAct：选择工具、观察结果、分类失败、切换 fallback、停止或提交 Evidence Gate。
   - 典型 fallback：official dynamic page 从 static fetch / Trafilatura 切 Crawl4AI；PDF 从 MarkItDown / pdfplumber / Camelot 切 Docling；news/event 从 RSS/feedparser / GDELT 到 Trafilatura，再回 official verification。
   - 每一步必须写入 `ToolUseLedger`、`ObservationSummary`、`RejectedCandidateLedger` 或 typed failure。

3. `Evidence Gate`
   - 由 deterministic / auditable gate 决定 source authority、metadata binding、parser lineage、period/unit/metric、numeric sanity、citation lineage 和 promotion status。
   - 模型可以建议 accepted / rejected / repair，但不能直接把 observation、RAG hit、news hit、PDF table candidate 或 supervisor supplement 晋升为 writer-allowed evidence。

常见 failure types：

- `fetch_fail`
- `dynamic_render_gap`
- `parser_table_gap`
- `row_selector_gap`
- `metadata_binding_missing`
- `low_authority_source`
- `numeric_sanity_fail`
- `period_unit_mismatch`
- `commercial_gap`
- `budget_exhausted`

### 已同步到 PRD

本轮已把上述内容追加进 `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`，并标注 2026-07-09 修改日期。主要新增：

- `修订记录` 新增 Z 盘工具 PoC 与 agentic tool-use 三层；
- `7.6 已验证工具栈与 agentic tool-use 三层`；
- `9.7 Agentic research workflow 验收` 增加 `Tool Registry`、`Evidence Tool Planner`、`Evidence Gate`、fallback 和 promotion gate 验收；
- `12 后续需拆技术文档` 增加 `Agentic Tool Calling Control Plane`；
- `13 当前开放问题` 增加 Tool Registry taxonomy、Planner 策略、Evidence Gate deterministic/model-assisted 边界和 OpenBB 隔离问题。

### 当前边界

- 本轮执行了 Z 盘工具 PoC 和外部网页/API/PDF smoke，但未修改 runtime code。
- 未运行 paid LLM。
- 未运行 true runtime full-chain。
- 未做 source ingestion。
- 未做 parser promotion 或 reranker 训练。
- 未把 PoC 输出写成 accepted runtime rows。
- 未把 P36 supervisor supplement rows 写成 agent runtime 能力。
- 未运行 pytest；本轮验证证据是 Z 盘 PoC 输出和 `tool_bench_report_20260709.md`。

### 下一步讨论入口

后续应继续讨论：

1. 项目是否真正转向 agentic search / agentic research。
2. 走 agentic 后，RAG / 知识库从“最终答案来源”转为哪些角色：candidate generator、memory、source index、artifact store、metadata filter、repair cache 或 institutional knowledge layer。
3. 哪些查询必须先走 KB / DB / RAG，哪些 official-source decision cells 可以直接触发 SourceHunter。
4. Evidence Tool Planner 第一版是 model-first，还是 deterministic fallback policy first。
5. Tool Registry / Evidence Gate 的 runtime schema 和 Workbench review surface 如何落地。

## 追加记录：Agentic Search / Agentic Research 与 RAG / 知识库角色

记录时间：2026-07-09 续

用户要求：本轮先不要考虑最小闭环和落地顺序，只把有关 agentic search、agentic research、RAG 和知识库角色的产品判断落到 PRD 与记录文档中。后续再讨论工程问题，例如 MCP、Harness 和上下文管理。

### 本轮产品判断

项目应支持真正的 agentic search 和 agentic research，但二者要拆开定义，不能混成“让模型自己查一切并直接写答案”。

`Agentic Search` 是 Evidence Layer 内的 cell-level 取证循环：

- 输入是 `EvidenceRequest`、source policy、`Tool Registry`、`DocumentMetadataIndex`、预算和 stop condition；
- 行为是选择 DB / RAG / SQL / graph / market connector / web source / crawler / parser，观察结果，分类失败，改写 query，切 fallback；
- 输出是 candidate evidence、rejected candidate、typed failure、typed gap、parser request 或 SourceHunter request；
- 不负责最终判断、证据晋升、叙事组织或写稿。

`Agentic Research` 是 Lead 驱动的研究闭环：

- Lead 将用户问题转成 `DecisionSurfaceContract`、关键 decision cells、evidence requirements、specialist assignments、repair policy 和 writer constraints；
- specialist 提出业务判断和证据需求，但取数必须经共享 Evidence Layer；
- Evidence Layer 把 agentic search 结果转成 accepted evidence、context_only、table_candidate、typed_gap 或 commercial_gap；
- Lead 用 `CaseControlMemory`、`DecisionSurfacePack`、`RepairTicket` 和 `WriterBrief` 审查故事线、缺口和可交付性；
- Writer / Presentation Agent 负责语言、结构、表格、图表、dashboard 表达和用户要求格式，但仍然不能补源。

### RAG / 知识库的新定位

走 agentic 后，RAG / 知识库不应再被当作最终回答引擎，也不能把 raw hit、reranker score 或历史底稿片段直接送进 writer payload。它应该成为 Evidence Layer 和 Lead control plane 的基础设施。

RAG / KB 的主要角色：

- `Candidate Generator`：为 EvidenceRequest 召回可能相关 chunk、table、filing、新闻、历史底稿和 graph node。
- `Source Index`：告诉系统某公司、期间、doc type、section、table lineage 可能在哪里。
- `Metadata Filter`：用 company、ticker、period、doc type、source authority、section、table lineage 先过滤，再 rerank。
- `Artifact Router`：找到 memo、PPT、Excel、dashboard、workpaper 中可复用或需一致性检查的对象。
- `Institutional Memory`：保存机构模板、house view、用户偏好、coverage universe、review decision 和 prior gaps。
- `Repair Cache`：记录过去某类 gap 的有效 source、无效 query、失败 parser、有效 fallback。
- `Context Router`：帮助 Lead / specialist 取最少必要上下文，减少 context pollution。
- `Coverage Auditor`：发现长期缺 source、缺 parser、缺 commercial data 的 decision cells。

RAG / KB 明确不能做：

- 不能替代 official source authority；
- 不能替代 parser lineage、row selector、unit / period sanity 和 numeric audit；
- 不能直接给 Writer 当 writer-allowed evidence；
- 不能把 Method / Playbook KB 引用成事实；
- 不能把历史研究结论当成当前 as-of 证据；
- 不能绕过 Evidence Gate。

### 知识库分层

本轮把知识库拆成五层：

1. `Raw Source Library`：filing、issuer IR、PDF、网页 snapshot、用户上传材料、市场数据 raw pull。它只表示 source 可追溯，不等于 accepted evidence。
2. `Parsed Evidence Store`：chunk、table candidate、exact-value row、parser lineage、page / section / cell refs。未过 gate 前不能给 Writer。
3. `Accepted Research Memory`：accepted evidence、`DecisionSurfacePack`、`NumericProgramTrace`、`WorkpaperPack`、review decisions。必须保留 as-of、source revision 和复核状态。
4. `Method / Playbook KB`：行业框架、分析模板、估值方法、风险清单、输出 rubric。只能辅助 planning，不能当事实证据。
5. `User / Institutional Context`：用户偏好、机构口径、coverage universe、house style、历史反馈。必须与事实证据隔离展示。

核心规则：

```text
RAG tells where the answer may be.
Evidence Gate decides whether it is usable.
Specialist and Lead decide what it means.
Writer only presents what has been approved.
```

### 对 P36 发现的解释

P36 Node02 / Node03 反复暴露的问题不是“系统完全没数据”，而是已有数据没有按用户问题的 decision cells 进入 runtime payload；RAG 召回强，但精度、metadata filter、row selection、numeric sanity 和 evidence promotion 弱。

因此，后续评价 RAG 不能只看 top-k recall 或 answer hit rate，而应看：

- decision-cell candidate recall；
- metadata-filtered precision；
- RAG hit 到 accepted evidence 的转化率；
- rejected candidate 解释覆盖率；
- exact fact authority violation rate；
- citation clickthrough success rate；
- repair cache reuse rate；
- context pollution rate。

### 已同步到 PRD

已更新 `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`：

- `修订记录` 增加 Agentic Search / Agentic Research 与 RAG / 知识库角色定位；
- 新增 `7.7 Agentic Search / Agentic Research 与 RAG / 知识库角色（2026-07-09 追加）`；
- `9.7 Agentic research workflow 验收` 增加 agentic search、agentic research、RAG / KB promotion boundary 和 RAG eval 验收；
- `10 指标` 增加 decision-cell RAG recall、RAG hit to accepted evidence conversion、exact authority violation、context pollution、repair cache reuse；
- `12 后续需拆技术文档` 增加 `Agentic Search / Agentic Research / Knowledge Layer Contract`；
- `13 当前开放问题` 增加 RAG / KB 分层、agent 权限、eval、method-only boundary 和 stale evidence 问题。

### 当前边界

- 本轮只做 PRD / worklog 文档更新。
- 未修改 runtime code。
- 未运行 paid LLM。
- 未运行 true runtime full-chain。
- 未做 source ingestion、parser promotion、reranker 训练或 DB 写入。
- 未把 PoC 工具能力、supervisor supplement 或本轮产品判断写成 agent runtime 已具备能力。

### 下一步讨论入口

下一轮可以进入工程问题：MCP 工具面、Harness / eval harness、上下文管理、CaseControlMemory、ToolUseLedger、EvidenceRequest schema、Knowledge Layer permission 和 agent communication contract。

## 追加记录：Agentic Research Harness 工程控制面

记录时间：2026-07-09 续

用户继续给出工程参考：上下文工程、context rot / governance decay / self-compaction、LangSmith / OpenAI Agents SDK / Claude Code hooks 的 trajectory observability、guardrails / permission gates / sandbox、LangGraph durable execution / HITL / persistence、OpenAI Agents SDK sessions、Claude Code subagents、OpenAI handoffs / agents-as-tools、LangGraph subgraphs、Claude Code skills / progressive disclosure、LangSmith / Terminal-Bench / OSWorld / Pi-bench 这类 trajectory / execution eval，以及 trace-driven harness self-improvement 和 claim-level provenance。

### 本轮产品 / 工程判断

FIN 不应只是在 agentic search / research 上接更多工具，而应形成 `Agentic Research Harness`。Harness 是运行时控制面，不是另一个 agent；它负责把 MCP / ToolGateway、上下文、权限、安全、durable state、trace、eval 和自我迭代统一起来。

目标结构：

```text
User Task
 -> Lead Control Plane
 -> DecisionSurfaceContract
 -> Durable Run State / CaseControlMemory
 -> Subagents-as-Tools / Evidence Tool Planner
 -> MCP / ToolGateway / Sandbox / Permission Gate
 -> Tool Observations / Evidence Candidates
 -> Evidence Gate / Numeric Gate / Provenance Graph
 -> DecisionSurfacePack
 -> Writer no-source
 -> Verifier / Workbench / Eval Harness
 -> Trace-driven Self-Improvement Loop
```

### Harness 模块拆分

1. `MCP / ToolGateway`
   - MCP 是工具和资源的接入协议，不是研究大脑。
   - SEC、OpenBB、RSS/GDELT、crawler、parser、renderer、browser、Drive/GitHub connector 适合逐步 MCP 化或 ToolGateway 化。
   - 内部 SQL、RAG、graph、parser 可以先不用 MCP，但必须暴露相同 tool contract，并经过 `Tool Registry -> Permission Gate -> ToolInvocationLedger -> Evidence Gate`。

2. `Durable Run State`
   - 长任务必须支持 pause、resume、retry、replay、timeout、cancel、human approve。
   - 一等状态对象应包括 `TaskRun`、`CaseControlMemory`、`NodeAttempt`、`ToolInvocation`、`Observation`、`EvidenceCandidate`、`PromotionDecision`、`Artifact` 和 `ReviewAction`。
   - 不得用 full-chain rerun 代替节点级 checkpoint replay。

3. `ContextEngine / Self-compaction`
   - 上下文分为 pinned governance、case working context、role context pack、artifact context 和 institutional context。
   - writer no-source、source authority、permission policy、supervisor supplement boundary、commercial boundary 必须 pinned。
   - 每次 compaction 应生成 `CompactionEvent`，如果丢失治理约束或 decision cell，应记录为 `context_governance_decay`。

4. `Subagents-as-Tools`
   - subagent 是独立上下文 worker，不是多 agent roleplay。
   - 推荐工程分工：ExploreAgent、PlanAgent、EvidenceAgent、DomainOperator、WriterPresentationAgent、VerifierAgent。
   - 跨 agent 共享必须通过 structured artifacts，不得把私有 scratchpad 当事实。

5. `Skills / Progressive Disclosure`
   - 行业 playbook、source policy、parser rule、writer rubric、verifier rule 应按任务和角色渐进加载。
   - skill 只是方法和约束来源；未进入 runtime prompt/schema/gate 前不得称为 active capability。

6. `Tracing / Provenance`
   - 仅记录 token / latency 不够，最终 claim 必须可追溯到 decision cell、evidence ref、tool invocation、observation、parser / numeric lineage、promotion decision、verifier result 和 artifact。
   - 可对接 LangSmith / OpenTelemetry / Langfuse / Phoenix 等后端，但 FIN 必须有最小可审 trace schema。

7. `Guardrails / Permission Gates`
   - prompt 说禁止不够，runtime 必须让越权动作不可执行或 fail-closed。
   - gate 分为 pre-run、pre-tool、post-tool、promotion、writer 和 Workbench 六层。
   - 模型可以建议通过或 repair，但不能绕过 gate。

8. `Trajectory / Execution Eval`
   - eval 需要覆盖 trajectory、execution、provenance、context、permission、artifact consistency 和 Agent Information Economy。
   - 目标是检查过程是否正确，而不只是最终答案是否像样。

9. `Harness Self-Improvement`
   - 从 trace corpus 中聚类 recurring issue，生成 root-cause issue、harness / prompt / schema / skill / eval patch proposal，再用 deterministic fixture 和 human review 合并。
   - 可以自动建议，不能自动合并 runtime behavior 变更。

### 已同步到 PRD

已更新 `docs/product/PRD_20260628_b2b_financial_research_workbench.zh-CN.md`：

- `修订记录` 新增 Agentic Research Harness 工程控制面；
- 新增 `7.8 Agentic Research Harness 工程控制面（2026-07-09 追加）`；
- `9.7 Agentic research workflow 验收` 增加 durable state、ContextEngine、claim provenance、subagent artifacts、guardrails、trajectory eval 和 harness self-improvement 验收；
- `10 指标` 增加 claim provenance coverage、trace span completeness、context governance decay、compaction boundary preservation、permission gate violation、writer no-source violation、checkpoint replay、self-improvement proposal acceptance 等指标；
- `12 后续需拆技术文档` 增加 `Agentic Research Harness`；
- `13 当前开放问题` 增加 MCP vs ToolGateway、durable state backend、ContextEngine 分层、trace backend、subagent 划分和 self-improvement 自动化边界问题。

### 当前 PRD 模块地图

截至本轮，PRD 可以按以下模块理解：

1. `产品定位 / 用户 / 核心问题`（第 1-3 章）
   - FinSight 是 B 端 evidence-backed financial research workbench，不是通用金融聊天框，也不是自动投资决策系统。
   - 目标用户是买方、卖方、咨询、企业战略等需要可审计研究底稿和交付物的角色。

2. `产品形态 / 任务执行`（第 4 章）
   - 产品从普通 multi-agent report generator 升级为 agentic research operating system。
   - 核心对象是 `DecisionSurfaceContract`、`DecisionSurfacePack`、`DocumentMetadataIndex`、`NumericProgramTrace`、`ArtifactConsistencyGraph`。
   - `Agent Information Economy` 把 token / context / specialist fanout 是否转成判断产出作为产品质量指标。

3. `数据与信息范围`（第 5 章）
   - 覆盖基本面、披露、产品技术、客户供应链、行业政策、资本市场、用户上传材料。
   - 当前新增理解是：数据不是越多越好，必须进入 decision cell、source authority、parser lineage 和 promotion gate。

4. `功能模块`（第 6 章）
   - Dashboard、Research Task Center、Data Room、Evidence Workbench、Workpaper Builder、Graph Workspace、Research-to-Quant、Deliverable Studio、Watchlist、Human Review、Admin Governance。
   - Writer / Deliverable Studio 已明确为 presentation agent，只能消费 approved package，不得补源。

5. `Multi-agent / Evidence / Harness 架构`（第 7 章）
   - 7.1-7.4 定义 agent 权限、repair ownership、Evidence Layer、SourceHunter / Evidence compiler。
   - 7.5-7.6 定义工具栈和 agentic tool-use 三层：Tool Registry、Evidence Tool Planner、Evidence Gate。
   - 7.7 定义 agentic search / agentic research 与 RAG / KB 角色。
   - 7.8 新增 Harness 工程控制面：MCP / ToolGateway、durable state、ContextEngine、subagents-as-tools、skills、tracing、guardrails、eval、自我迭代。

6. `MVP / Repair Slice`（第 8 章）
   - 原 MVP 覆盖产品壳、财报点评、公司深度、供应链研究、Data Room、Watchlist、Research-to-Quant。
   - B7 新增 P36 Decision Surface / Evidence Tooling Repair Slice，把 P36 发现转成 no-paid deterministic repair program。

7. `验收 / 指标`（第 9-10 章）
   - 验收不再只是报告好不好看，而是是否有 decision cell closure、source boundary、numeric reproducibility、trace provenance、artifact consistency、writer no-source 和 trajectory correctness。

8. `非目标 / 后续技术文档 / 开放问题`（第 11-13 章）
   - 非目标保持：不自动给买卖建议、不替代投委会、不做真实资金交易、不用弱信号形成核心结论。
   - 后续技术文档已经从产品 PRD 拆到 Agentic Research OS、Evidence Tooling、Decision Surface、Agentic Tool Calling、Knowledge Layer 和 Harness。

### 当前边界

- 本轮只做 PRD / worklog 文档更新。
- 未修改 runtime code。
- 未运行 paid LLM。
- 未运行 true runtime full-chain。
- 未运行 source ingestion、parser promotion、MCP server、LangGraph replay 或 eval harness。
- 本轮新增内容是 `documented` 状态，不是 `runtime_injected` 或 `node_level_consumed`。
