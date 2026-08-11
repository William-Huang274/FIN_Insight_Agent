# P36 Node 05 Fundamental Specialist Manual Run

日期：2026-07-09

## 节点定位

节点：`node_05_fundamental_specialist`

目标：在 Fundamental Analyst 的真实约束下，检查它能否把 node 02-04 的项目内证据转成“收入证据 / 利润质量 / 经营杠杆 / 资本强度 / peer context”的可写材料，而不是只复述边界。

本节点不写最终报告，不补外源，不调用 paid LLM，也不运行 true runtime full-chain。

## 已读取或调用的 runtime / artifact / tool

- `src/sec_agent/prompts/skills/fundamental_analysis_skill_v0_2.md`
- `src/sec_agent/prompts/skills/shared_evidence_boundary_skill_v0_1.md`
- `src/sec_agent/specialist_llm.py`
- `src/sec_agent/multi_agent_runtime.py`
- `src/sec_agent/role_evidence_selector.py`
- `src/sec_agent/agent_registry.py`
- `data/workbench_private/research_data/product_intelligence_graph_v0_1.sqlite`
- `data/processed_private/ledger/sec_investment_coverage_mixed_with_8k_fy2023_2027_core_ledger.duckdb`
- `data/processed_private/ledger/sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_core_ledger.duckdb`
- `data/manifests/product_kpi_source_specific_verifier_summary_v0_1.json`
- `data/manifests/industry_operating_metric_slot_summary_v0_1.json`
- `docs/internal/vnext_20260610/p36_node_03_parser_evidence_operator_manual_run.zh-CN.md`
- `docs/internal/vnext_20260610/p36_node_04_graph_relationship_value_capture_manual_run.zh-CN.md`

说明：本节点使用的 SQLite / DuckDB 查询是 Codex supervisor 为了重建“上游理论上应传给 specialist 的输入包”而做的本地探针，不是 Fundamental Specialist runtime 自己可调用的工具。

## 节点允许与禁止

允许：

- 读取 bounded evidence rows、`fundamental_statement_pack`、`fundamental_peer_statement_panel`、`capital_macro_pack` 和 shared context。
- 将 SEC / 8-K / exact ledger / company-authored rows 转成 company-reported financial observations。
- 对 revenue、gross margin、gross profit、operating income、inventory、cash flow、segment/product revenue 做 period-safe 和 unit-safe 的有限判断。
- 在缺少同口径 peer / business-line GM / product economics 时，输出 unsupported claims 和 missing confirmations。

禁止：

- 不调用工具或发起检索。
- 不从模型记忆补数据。
- 不把 8-K commentary 当成 audited fact。
- 不把 product graph / relationship graph / market snapshot 直接写成公司收入或利润事实。
- 不推断 AI server revenue 等于 margin improvement。
- 不让 writer 阶段自发补源。

## Runtime prompt / data-view 观察

Fundamental skill 本身方向是对的：

- 要求从 `assigned_task_card.relevant_requirements` 和 `required_claim_slots` 开始，而不是扫全量 rows。
- 要求优先使用 `fundamental_statement_pack`，再读 free-form rows。
- 要求保持 period role，peer comparison 只在 same metric / unit / period 下成立。
- AI/Semis 额外要求把产品或周期证据桥接到 revenue exposure、margin quality、working capital、capex、cash flow 和 peer context。

真实工程问题在输入投射：

- `agent_registry.py` 声明 `fundamental_analyst` 是 `inspect_only`，`allowed_tools=[]`，这符合 writer 前 specialist 的边界。
- registry 允许 `fundamental_analyst` 使用 `company_product_evidence_graph`，但这只有在上游把 ProductIntelligenceGraph / ProductEvidence rows 变成 `product_evidence_rows` 或 `context_rows` 且带 `promotion_status in {runtime_fact_allowed, runtime_context_taxonomy_only}` 时才会进入 data view。
- `specialist_llm.build_specialist_request_from_state()` 会把 `fundamental_statement_pack` / `fundamental_peer_statement_panel` 传给 Fundamental Analyst，但这些 pack 依赖 state 中已有的 runtime rows；它不会自己去 PIG / source hunter / DuckDB 重新找缺口。
- fallback `_bounded_rows_for_agent()` 对 fundamental 只拿 `runtime_ledger_rows` 与 SEC/8-K context，并截前 12 行；如果 `build_agent_data_view()` 没成功投射 role-specific rows，specialist 会严重 row-starved。
- `_bounded_rows_for_agent_data_view()` 比 fallback 强，确实纳入 `derived_metric_layer` 与合格 `product_evidence_rows`，但前提仍是上游已经把产品/业务线 rows 晋升到 runtime fact/context。P36 当前 case 的关键问题正是在这里。

结论：Fundamental Specialist 不是主要坏点。它的 prompt / skill 可以产生有质量 memolet，但要求上游给它一个 cell-ready 的 `fundamental_statement_pack` / `fundamental_peer_statement_panel` / business-line rows。现在很多材料存在于 PIG、industry operating slots、exact ledger 或 graph store，但没有投射成它能稳定消费的 decision-cell financial pack。

## 项目内证据探针

以下只是 supervisor 重建输入，不是本节点补源。

### ProductIntelligenceGraph / operating metric examples

| 链条 | 项目内可见 rows | 可支持 | 不能支持 |
|---|---|---|---|
| Accelerator | AMD `Data Center` product revenue rows；NVDA 在 exact ledger 有 revenue / gross margin headline rows | AMD 数据中心收入暴露；NVDA 高毛利基础财务轮廓 | NVDA Data Center 分部收入质量、GPU ASP / units、出口管制敏感收入、peer-comparable accelerator profit pool |
| Server OEM | DELL `Servers and Networking` operating rows；HPE `Server` product revenue rows；SMCI net sales / gross profit rows | AI/server demand proxy 与低毛利风险的方向性材料 | AI server-only gross margin、GPU pass-through economics、rack-level bill-of-material margin bridge |
| Foundry / Packaging | TSM `High Performance Computing` revenue mix rows，FY2024 为 43%、FY2023 为 41%、FY2022 为 37% | HPC 暴露上升，foundry 受 AI demand 拉动的基础判断 | CoWoS capacity / pricing / allocation / packaging profit pool |
| HBM / Memory | MU MCBU / CDBU revenue mix rows；SK hynix / Samsung local disclosure segment rows | memory / semiconductor segment exposure | HBM-only revenue、HBM-only gross margin、HBM3E/HBM4 allocation、customer split |
| Semicap | AMAT Semiconductor Systems / Applied Global Services revenue rows；LRCX memory/foundry revenue mix and customer-support revenue rows；KLAC gross margin headline rows | equipment peer 的基础财务与 memory/foundry exposure | AI-specific bookings/backlog、China/export sensitivity by tool type、last-baton capex digestion |

### Exact ledger / financial examples

`sector_depth_full238` 和 `sec_investment` ledger 能召回不少基础财务，但也暴露 sanity 风险：

- NVDA: 8-K rows 能召回 revenue 与 GAAP / non-GAAP gross margin headline rows。
- AMD: 10-Q rows 能召回 net revenue、gross profit、operating income；但 8-K summary rows 中也有 revenue 行返回 `percent` 的情况，需要 headline selector。
- DELL: 8-K rows 能召回 net revenue、Non-GAAP operating income、ISG net revenue；但 period / column label 需要进一步规范。
- SMCI: 10-Q rows 能召回 net sales 与 gross profit，能支持“gross profit / net sales 大约低双位数”的 margin-dilution 方向，但不能直接说 AI server-only margin。
- HPE: 10-Q rows 能召回 net revenue、gross profit、gross profit margin。
- AMAT / LRCX / KLAC: 能召回 revenue / gross margin rows，但 AMAT / KLAC 都出现 change / delta 行与 headline 行混在一起的风险。
- MU: 8-K rows 里 gross margin 行可能返回美元金额而非 margin percentage，需要 table relation sanity。

这解释了为什么下游容易变保守：如果直接让 writer 用这些 rows，存在误写数字风险；如果 specialist 不敢用，就只剩边界声明。

## 手工模拟 SpecialistMemolet

在不补源、只使用项目内证据和上述边界下，我作为 Fundamental Analyst 可以写出一个 partial memolet：

### Observation 1: Accelerator 收入和利润质量方向成立，但 peer-level accelerator profit pool 仍不完整

- `claim_type`: `business_observation`
- `ticker_scope`: `NVDA / AMD`
- `metric_scope`: revenue / gross margin / Data Center revenue exposure
- `memo_slot`: `accelerator_revenue_profit_quality`
- `materiality`: high
- `direction`: positive for revenue evidence, partial for profit-quality attribution
- `supported_by_project_rows`: NVDA revenue / gross margin exact ledger rows；AMD Data Center product revenue rows。
- `business_mechanism`: accelerator 是 AI capex 最直接的收费节点，NVDA headline gross margin rows 和 AMD Data Center revenue rows能支持“收入证据强、利润质量较高”的方向。
- `cannot_infer`: 不能从当前 bounded rows 推断 NVDA Data Center-only margin、Blackwell allocation、export-control-adjusted China exposure、AMD MI-series profitability。
- `what_would_change_view`: 需要 Data Center segment revenue / gross margin bridge、accelerator backlog/allocation、export-control revenue sensitivity 和 peer same-period comparison。

### Observation 2: Server OEM 可以证明 revenue proxy，但 margin quality 是缺口核心

- `claim_type`: `business_observation`
- `ticker_scope`: `DELL / SMCI / HPE`
- `metric_scope`: server revenue / net sales / gross profit
- `memo_slot`: `server_oem_demand_proxy_margin_quality`
- `materiality`: high
- `direction`: revenue evidence positive, profit quality weak / mixed
- `supported_by_project_rows`: DELL Servers and Networking / ISG revenue rows；HPE Server revenue and gross profit margin rows；SMCI net sales and gross profit rows。
- `business_mechanism`: server OEM 收入可以随 AI server shipments 放大，但 GPU/accelerator pass-through 会稀释利润质量。SMCI 的 net sales / gross profit rows 能支持低毛利风险方向，HPE/DELL rows 支持 server revenue exposure。
- `cannot_infer`: 当前 rows 不能给 AI server-only gross margin、GPU content pass-through、liquid cooling/rack integration margin、customer concentration by AI server。
- `what_would_change_view`: 需要 AI server revenue vs gross margin bridge、backlog/order commentary、inventory/working-capital turns 和 peer same-period margin table。

### Observation 3: TSM Foundry 暴露可见，但 CoWoS 价值捕获不在 fundamental pack 里

- `claim_type`: `business_observation`
- `ticker_scope`: `TSM`
- `metric_scope`: HPC revenue mix
- `memo_slot`: `foundry_packaging_revenue_quality`
- `materiality`: high
- `direction`: positive for HPC exposure, partial for packaging economics
- `supported_by_project_rows`: TSM High Performance Computing revenue mix rows: FY2022 37%、FY2023 41%、FY2024 43%。
- `business_mechanism`: HPC mix 上升支持 TSM 对 AI / high-performance compute demand 的收入暴露。
- `cannot_infer`: 不能从 current fundamental rows 推断 CoWoS capacity、CoWoS ASP、packaging gross margin 或 allocation power。
- `what_would_change_view`: 需要 CoWoS capacity / pricing / allocation official or company-authored rows，以及 advanced packaging revenue/profit bridge。

### Observation 4: HBM / Memory 有 segment exposure，但 HBM-only profit quality 未被证明

- `claim_type`: `business_observation`
- `ticker_scope`: `MU / 000660.KS / 005930.KS`
- `metric_scope`: memory / MCBU / DS segment revenue
- `memo_slot`: `hbm_memory_profit_quality`
- `materiality`: high
- `direction`: positive for memory-cycle exposure, unsupported for HBM-only margin ranking
- `supported_by_project_rows`: MU MCBU / CDBU revenue mix rows；SK hynix / Samsung local disclosure semiconductor / DS segment rows。
- `business_mechanism`: memory vendors have disclosed segment exposure tied to AI memory demand, but current rows are too coarse to isolate HBM.
- `cannot_infer`: HBM-only revenue、HBM gross margin、HBM3E/HBM4 mix、NVIDIA / hyperscaler allocation split。
- `what_would_change_view`: 需要 HBM-specific revenue/margin/capacity rows，或至少 company-authored HBM shipment/allocation/guidance rows。

### Observation 5: Semicap 基础财务强，但 AI-specific last-baton 风险不能由 fundamental alone 证明

- `claim_type`: `business_observation`
- `ticker_scope`: `ASML / AMAT / LRCX / KLAC`
- `metric_scope`: segment/product revenue, gross margin, memory/foundry mix
- `memo_slot`: `semicap_revenue_quality_and_lag_risk`
- `materiality`: medium-high
- `direction`: positive for equipment quality, partial for AI-specific demand conversion
- `supported_by_project_rows`: AMAT Semiconductor Systems / Applied Global Services revenue rows；LRCX memory/foundry mix rows and revenue / gross margin rows；KLAC gross margin rows with sanity caveat。
- `business_mechanism`: semicap vendors monetize AI supply expansion through WFE and foundry/memory capacity buildout, but timing lags end-demand and capex digestion risk is material。
- `cannot_infer`: AI-specific bookings/backlog、China/export-sensitive tool mix、leading vs lagging order quality、customer capex digestion by node/tool。
- `what_would_change_view`: 需要 bookings/backlog by segment/geography、China exposure and export-control rows、management commentary tied to AI/HBM/advanced packaging capacity。

## 双标尺评价

### 投研质量标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| question_answerability | partial | Fundamental 能回答基础收入/利润方向，但不能覆盖 HBM-only、CoWoS、AI server-only margin 和 price-in。 |
| decision_surface_completeness | partial | 五条链都能给一条 observation，但七个风险列不能由 fundamental alone 填满。 |
| financial_and_operating_depth | partial | 基础财务 rows 存在；业务线经济性和 peer same-period comparability 不足。 |
| capital_market_price_in_depth | fail_for_this_node | Fundamental 节点不负责 price-in，且 capital/market pack 未进入本节点核心输出。 |
| source_grade_and_lineage | pass_with_sanity_caveat | 公司披露/ledger lineage 强，但 unit/period/row-label sanity 需要 gate。 |
| counter_thesis_and_turning_signals | partial | 可以给 cannot-infer / what-would-change，但系统性 counter-thesis 应交给 risk / market / industry。 |
| writer_readiness | partial | 可作为 writer 的财务 memolet 输入，但不应直接成为最终报告 fact table。 |

### Agent 产品工程标尺

| 维度 | 评分 | 理由 |
|---|---|---|
| input_contract_quality | partial | Skill 要求的 `fundamental_statement_pack` / peer panel 是好合同，但当前输入不是 decision-cell-ready。 |
| output_contract_quality | pass_partial | SpecialistMemolet / judgment_candidates 结构可用，但缺 per-cell fact table output。 |
| tool_affordance_fit | pass_for_role_boundary | inspect-only 正确；问题是上游工具/pack 没把材料准备好。 |
| observability | pass | 能定位到 registry、data view、pack 构建、ledger/PIG rows 和 sanity 风险。 |
| recoverability | partial | 能识别 missing confirmations，但不能自己触发 source hunter / parser repair。 |
| information_economy | partial | 有 role-specific pack 机制，但 rows 选择仍可能被重复/噪声/非 cell rows 消耗预算。 |
| marginal_contribution | partial | 比单 agent 有更强边界和 lineage，但只有在上游 pack 够好时才兑现。 |
| human_review_surface | partial | 缺少 Fundamental decision-cell review table；只能看 memolet 和 refs。 |
| product_value_over_single_agent | partial | 当前能比单 agent 更可信，但未比单 agent 更完整；优势被输入投射缺口抵消。 |

## Root-cause notes

- Fundamental Specialist prompt / skill 不是主要问题。它已经要求财务桥接、period discipline、peer comparability 和 AI/Semis margin/capex/cash-flow 思维。
- 主要问题是 `DecisionSurfaceContract -> EvidenceOperator -> ProductIntelligenceGraph / exact ledger / operating metric -> FundamentalStatementPack` 这条投射链不完整。
- ProductIntelligenceGraph 里有业务线和产品 rows，但若没有 `promotion_status` 和 decision-cell mapping，Fundamental Specialist 不会稳定消费。
- Product KPI verifier 当前很安全但过稀；industry operating metrics 更丰富但需要 headline selector / unit sanity / row-label sanity。
- 如果这个节点被强行要求输出“完整研究结论”，它会自然走向 missing-confirmation 和 boundary prose；这是节点输入合同的问题，不是单纯模型风格问题。
- WorkBuddy 单 agent 的优势在于它默认先把故事链讲完整，再轻量声明边界；FIN 当前的优势应是：同样先给 decision surface，但每个 cell 有 source grade / numeric sanity / cannot-infer / what-would-change。现在还没有把这套结构喂给 Fundamental Specialist。

## 对下一节点的交接

下一节点建议进入 `node_06_industry_product_specialist`：

1. 用 ProductIntelligenceGraph / ProductEvidencePack / relationship graph / industry operating rows 检查产品、供给瓶颈、deployment、customer/order proxy 是否能转成 value-capture material。
2. 明确区分 product taxonomy / technical spec / deployment signal / supply-chain relationship / product KPI exact。
3. 检查 Product Specialist 是否比 Fundamental Specialist 更能填 HBM、CoWoS、AI server、semicap backlog 等 cells。
4. 若仍缺，记录 SourceHunterLoop / parser fixture / graph projection 的具体 cell-level repair queue。

## 未运行

- paid LLM API
- true runtime full-chain
- external source supplement
- source ingestion
- parser repair
- model comparison
- case expansion
- release eval
