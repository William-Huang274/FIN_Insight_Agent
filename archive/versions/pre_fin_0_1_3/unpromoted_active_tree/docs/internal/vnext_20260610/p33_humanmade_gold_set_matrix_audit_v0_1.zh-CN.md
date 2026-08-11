# P33 Humanmade Gold Set Matrix Audit v0.1

日期：2026-07-06

## 1. 审计口径

这轮不是继续跑模型，也不是把 AI/Semis 单 case 的问题直接外推成全行业结论。
本轮做的是 no-paid matrix audit：把 1 个 Deep Gold Case、8 个 Rubric Gold Case 和 6 个 Negative Gold Case 放在同一张矩阵里，判断当前项目已经证明了什么、还只是文档/规则、以及哪些风险会跨行业复现。

未运行：paid LLM、full-chain、模型对比、新检索、爬虫或 parser。

## 2. 故事线

这次审计串起来看，故事不是“某个节点又坏了”，而是项目进入了一个更关键的阶段：工程链路已经能把任务跑成 required items、JudgmentCandidates、MemoLogicPlan 和 writer payload，但这条链路还没有稳定把金融研究方法和公开源证据转成成熟 analyst briefing。

### 2.1 1_engineering_chain_exists_but_research_chain_is_thin

项目现在不是没有图谱、证据路径或 agent 节点，而是这些路径在进入最终判断前仍会变成 context、边界说明和泛化锚点，没有稳定形成 analyst-grade judgment。

支撑 case：`ai_semis_dell_nvda_anchor_v0_1`。

### 2.2 2_deep_case_exposes_the_first_faulty_floor

AI/Semis deep case 暴露的最早硬问题在 gold-depth source rows 和产品图谱投影：`product_runtime_fact_count=0`，多个 required item 仍是 context/proxy，即使 route 和 shape gate 已经通过。

支撑 case：`ai_semis_dell_nvda_anchor_v0_1`, `negative_sku_revenue_missing_not_product_failure_v0_1`。

### 2.3 3_rubric_cases_show_this_will_generalize_unless_methods_become_runtime_contracts

Semicap、Cloud/SaaS、Financials、Healthcare、Energy、Retail、Auto 和 Secondary-market 每个行业都要求不同 operating metrics 和证据桥。AI/Semis 上的结构性通过，不能证明这些 vertical method 已经 runtime-active。

支撑 case：`semicap_cycle_rubric_v0_1`, `cloud_saas_ai_monetization_rubric_v0_1`, `financials_rate_credit_capital_rubric_v0_1`, `healthcare_regulated_product_adoption_rubric_v0_1`, `energy_utilities_power_demand_rubric_v0_1`, `retail_consumer_traffic_margin_rubric_v0_1`, `auto_ev_industrial_cycle_rubric_v0_1`, `capital_market_feedback_price_in_rubric_v0_1`。

### 2.4 4_negative_cases_define_the_failure_modes_that_must_be_machine_checked

最危险的失败不是空答案，而是过度提权、虚假 source absence、已有 evidence 未使用、public proxy 冒充 exact。这些必须绑定 artifact 做机器检查，不能依赖 reviewer 记忆。

支撑 case：`negative_sku_revenue_missing_not_product_failure_v0_1`, `negative_demand_pool_not_supplier_allocation_v0_1`, `negative_relationship_graph_not_financial_fact_v0_1`, `negative_parser_gap_not_public_source_absent_v0_1`, `negative_available_evidence_not_used_v0_1`, `negative_commercial_tracker_boundary_v0_1`。

### 2.5 5_next_repair_must_compile_gold_set_into_runtime

下一步不是继续跑模型，而是把 gold set 编译进 `HumanmadeGoldSetAudit`、`BriefingPackQualityGate`、source ingestion、graph projection、specialist contracts 和 Research Lead veto。

支撑 case：`ai_semis_dell_nvda_anchor_v0_1`, `semicap_cycle_rubric_v0_1`, `cloud_saas_ai_monetization_rubric_v0_1`, `financials_rate_credit_capital_rubric_v0_1`, `healthcare_regulated_product_adoption_rubric_v0_1`, `energy_utilities_power_demand_rubric_v0_1`, `retail_consumer_traffic_margin_rubric_v0_1`, `auto_ev_industrial_cycle_rubric_v0_1`, `capital_market_feedback_price_in_rubric_v0_1`, `negative_sku_revenue_missing_not_product_failure_v0_1`, `negative_demand_pool_not_supplier_allocation_v0_1`, `negative_relationship_graph_not_financial_fact_v0_1`, `negative_parser_gap_not_public_source_absent_v0_1`, `negative_available_evidence_not_used_v0_1`, `negative_commercial_tracker_boundary_v0_1`。

## 3. Case 矩阵审计

| Case | 类型 | 当前状态 | 问题模式 | 最可能的早期故障层 |
| --- | --- | --- | --- | --- |
| `ai_semis_dell_nvda_anchor_v0_1` | `deep_gold_case` | `artifact_backed_fail_for_gold_depth` | 真实 AI/Semis artifact 已经能证明工程链路有形状、有 trace，但产品架构、客户部署、DELL 利润质量桥、semicap read-through、market price-in 和反证还没有达到 humanmade gold answer depth。 | source_runtime_ingestion, ProductIntelligenceGraph projection, Coverage depth gate |
| `semicap_cycle_rubric_v0_1` | `rubric_gold_case` | `partial_from_ai_semis_deep_case_unproven_as_standalone_runtime_case` | 系统能识别 ASML/AMAT/LRCX/KLAC 和半导体设备周期，但当前证据仍偏 peer scope / context；合格答案需要 bookings、backlog、shipment、service mix、客户晶圆厂周期和 China/export exposure。 | FPI/company_IR/local_disclosure_parser, semicap_playbook_to_specialist_contract, ProductIntelligenceGraph edge investment projection |
| `cloud_saas_ai_monetization_rubric_v0_1` | `rubric_gold_case` | `catalog_ready_runtime_artifact_missing` | 系统有 capex、产品和 source 层，但还没有 runtime 证明能把 AI 产品发布 / AI capex 转成云和 SaaS 的 RPO、ARR、usage、margin、depreciation 和 FCF 回报分析。 | Research Lead required-item planning for monetization versus cost burden, FundamentalStatementPack SaaS/cloud operating metric slots, CapitalMarketFeedback price-in and capex burden projection |
| `financials_rate_credit_capital_rubric_v0_1` | `rubric_gold_case` | `catalog_ready_runtime_artifact_missing` | 当前 AI/Semis 路径不能证明金融行业能力；银行/金融股必须从 deposits、NIM、loan growth、provision、capital、liquidity 和 funding cost 出发，不能按工业公司的收入/EPS 模板分析。 | financials industry playbook not runtime-proven, FundamentalStatementPack bank-specific KPI slots, macro/rate context to issuer financial bridge |
| `healthcare_regulated_product_adoption_rubric_v0_1` | `rubric_gold_case` | `catalog_ready_runtime_artifact_missing` | 系统有 ClinicalTrials/openFDA 等 source 概念，但还没有证明 trial、FDA、产品适应症、adoption、reimbursement 能进入产品表现 briefing。 | regulated product context adapter depth, healthcare product-to-commercialization playbook, ProductIntelligenceGraph product indication and adoption edges |
| `energy_utilities_power_demand_rubric_v0_1` | `rubric_gold_case` | `catalog_ready_runtime_artifact_missing` | 系统有宏观/监管和资本包概念，但还没有证明能把 load growth、rate base、allowed ROE、capex、debt、cash flow 放在同一条公用事业分析链里。 | utility industry operating metric slots, EIA/regulatory data adapter to issuer exposure bridge, capital/debt/FCF bridge projection |
| `retail_consumer_traffic_margin_rubric_v0_1` | `rubric_gold_case` | `catalog_ready_runtime_artifact_missing` | 系统可能能拿到部分收入和公司披露 KPI，但还没证明能避免把零售/消费写成泛泛 revenue growth；合格答案需要 traffic、ticket、mix、promo、inventory、shrink 和 margin bridge。 | retail operating metric slot normalization, commercial POS/channel boundary, Fundamental analyst operating decomposition skill |
| `auto_ev_industrial_cycle_rubric_v0_1` | `rubric_gold_case` | `catalog_ready_runtime_artifact_missing` | 系统有 NHTSA 和产品层概念，但还没证明能把 deliveries、ASP、inventory、recall、capacity utilization、financing sensitivity 桥到 margin quality。 | auto/industrial operating metric slots, NHTSA and recall context projection, channel/inventory parser routes |
| `capital_market_feedback_price_in_rubric_v0_1` | `rubric_gold_case` | `partial_platform_foundation_but_case_pack_missing` | S8 资本市场反馈在平台层已存在，但 AI/Semis 具体 case 里 NVDA/AMD/GOOGL/DELL 的 valuation、positioning、crowding 和 price-in 证据仍缺 case-specific pack。 | CapitalMarketFeedback case-specific pack selection, valuation/ownership/liquidity source routing, market_valuation_analyst required-item contract |
| `negative_sku_revenue_missing_not_product_failure_v0_1` | `negative_gold_case` | `open_guard_needed_ai_semis_currently_fails_depth` | 没有 SKU revenue 不能等于产品层失败；但当前 AI/Semis artifact 仍缺 runtime product facts，容易把产品判断压扁成 exact KPI 缺口。 | product source runtime ingestion, ProductIntelligenceGraph product fact projection, product specialist answer contract |
| `negative_demand_pool_not_supplier_allocation_v0_1` | `negative_gold_case` | `partial_guard_present_needs_machine_check` | MSFT/AMZN capex 只能证明 demand pool，不能直接证明 DELL/NVDA supplier allocation；未来 writer / specialist 必须有机器检查防止提权。 | Research Lead evidence role plan, specialist cannot-infer boundary, Memo Writer source-role projection |
| `negative_relationship_graph_not_financial_fact_v0_1` | `negative_gold_case` | `partial_guard_present_projection_needs_investment_roles` | relationship graph 不能直接当财务事实；当前大体避免了直接提权，但图谱边还缺稳定 investment-role projection。 | ProductIntelligenceGraph investment-role projection, relationship_graph edge authority schema, JudgmentCard graph_edge_refs |
| `negative_parser_gap_not_public_source_absent_v0_1` | `negative_gold_case` | `partial_guard_present_not_generalized` | ASML/TSM SEC manifest gaps 已被写成 retrievable route gaps，但这还不能证明非美/FPI/local disclosure parser 在所有 case 中都能正确归因。 | FPI/company_IR/local_exchange source router, table/PDF parser attribution, gap taxonomy |
| `negative_available_evidence_not_used_v0_1` | `negative_gold_case` | `open_guard_needed_old_memo_showed_symptom` | 如果 aggregate / writer payload 已有 DELL/LRCX 财务或经营证据，memo 仍写成缺失，这不是 source gap，而是 selector / projection / writer consumption failure。 | selected claim bridge, MemoLogicPlan required_item_answer_plan consumption, Memo Writer evidence ref inventory |
| `negative_commercial_tracker_boundary_v0_1` | `negative_gold_case` | `contract_defined_runtime_guard_unproven` | 公开 proxy 可以保留研究价值，但不能冒充 exact sales/share/flow；当前 boundary 概念已有，尚未被 matrix audit 证明为可执行 runtime guard。 | source authority model, commercial_gap taxonomy, Memo Writer proxy wording |

## 4. 审计后的总体判断

项目已经越过了最基础的编排失败阶段，但还没有把 vertical research methods 和公开源证据稳定转成可复用的 runtime judgment assets。

AI/Semis deep case 的价值在于，它不是抽象规则，而是真实暴露了当前链路的断层：shape/trace 可以通过，但 product architecture、customer deployment、financial bridge、semicap read-through、market price-in 和 counter-thesis 还不能形成 gold answer。

8 个 Rubric Gold Case 的价值在于，它们说明这个问题不是 AI/Semis 独有。每个行业都有自己的“正确分析语言”：银行要资产负债表和信用周期，公用事业要 rate base / capex / debt，零售要 traffic / ticket / mix / inventory，医疗要 clinical / regulatory / adoption / reimbursement。只要这些方法没有进入 runtime contract，换行业后就会重新退化成证据摘要。

6 个 Negative Gold Case 的价值在于，它们定义了金融 agent 最危险的坏输出：不是答不出来，而是把 proxy 写成 exact，把 graph 写成财务事实，把 parser gap 写成公开源没有，把上游已有证据写成缺失。

## 5. 下一步

- 实现 artifact-backed `HumanmadeGoldSetAudit`，并把它接成 Memo Writer 前的必过审计。
- 新增 `BriefingPackQualityGate`，按 deep/rubric/negative gold case 检查 briefing pack 的研究深度。
- 先把 AI/Semis human source ledger 接进 runtime slots，不先扩 paid cases。
- 把 rubric cases 编译成 vertical playbook runtime contracts，再声明跨行业能力。
- 把 negative cases 编译成 aggregate、writer payload、final memo 的 deterministic failure gates。

当前仍不得直接 paid Memo Writer、full-chain、模型对比或扩 case。
