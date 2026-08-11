# R41 Product Intelligence Graph Current Structure Audit

## Prompt

在继续实现新的产品智能图谱前，先审计当前项目里的所有数据结构、层级、图谱和图边，整理已有基座、真实边界和下一步实现方向，避免把 `Product-KPI exact`、产品规格、客户部署、竞品关系和资本/财务层混在一起推进。

## Scope Audited

- 架构文档：`docs/architecture/agent_graph_vnext/16_l4_weak_signal_and_vertical_source_lane_framework.zh-CN.md`、`23_non_financial_signal_authority_and_multidimensional_research_basis.zh-CN.md`。
- 最近阶段日志：`docs/worklog/integrated_execution_p_series/404_r40_source_specific_product_kpi_closeout.md`。
- Source / authority manifests：`source_layer_capability_audit_summary_v0_1.json`、`r18_source_route_registry_v2_summary.json`、`r18_source_authority_data_mart_summary_v0_1.json`、`company_public_source_coverage_matrix_v0_1.jsonl`、`exact_slot_coverage_matrix_v0_1.jsonl`。
- 产品/图谱 manifests：`product_family_lane_registry_v0_1.json`、`company_product_family_assignments_v0_1.jsonl`、`company_product_slots_v0_1.jsonl`、`product_relationship_graph_nodes_v0_1.jsonl`、`product_relationship_graph_edges_v0_1.jsonl`、`product_relationship_graph_summary_v0_1.json`。
- 二三层 depth manifests：`second_third_layer_real_source_readiness_gate_summary_v0_1.json`、`second_third_layer_depth_parity_summary_v0_1.json`、`second_third_layer_depth_parity_gap_action_plan_v0_1.jsonl`。
- Runtime graph code：`src/sec_agent/langgraph_orchestrator.py`、`src/sec_agent/layer_acceptance_gates.py`、`src/sec_agent/product_slot_relationship_graph.py`、`src/sec_agent/product_family_source_routes.py`、`src/sec_agent/runtime_source_context_store.py`。

## Current Layer Map

### 1. Source / Lane / Authority Layer

Current source substrate is already more than a crawler list:

- `VerticalSourceLaneRegistry` has 8 lanes and classifies 603 companies by primary/secondary lane.
- `ProductFamilyLaneRegistry` has 81 product families.
- `CompanyProductFamilyAssignment` has 663 assignments.
- `R18 SourceRouteRegistry` has 28 source roles and 32 observed source ids.
- `R18 SourceAuthorityDataMart` has 7,181 rows:
  - `exact_company_fact_authority=2,925`
  - `bounded_thesis_driver_authority=4,256`
  - `evidence_bundle_allowed=7,156`
  - `planning_or_gap_only=25`
- `company_public_source_coverage_matrix_v0_1` has 603 company rows:
  - `pass=578`
  - `gap=25`
- `exact_slot_coverage_matrix_v0_1` has:
  - `all_required_exact_ready=578`
  - `partial_exact_ready=25`

Boundary:

- Source readiness is not the same as depth parity.
- A company can have parser-backed public rows but still lack product KPI exact, customer deployment, or capital detail depth.

### 2. Product Profile / Product Surface / Product Spec Layer

Product identity and surface coverage is now broad:

- `company_disclosed_product_profile_context_rows_v0_1`: 8,880 rows across 603 tickers.
  - `ProductProfileSlot=8,827`
  - `BusinessProfileSlot=53`
- `official_product_surface_context_rows_v0_1`: 2,408 rows.
  - official product taxonomy / product spec / product surface table context.
- `official_product_spec_context_rows_v0_1`: 242 strict technical spec rows.
  - examples include size/dimension, power rating, process node support, bandwidth, memory capacity, core count, range, speed/frequency.
- `product_spec_depth=603/603`.

Boundary:

- These rows can support product existence, taxonomy, specification, architecture, and comparison context.
- They cannot support revenue, market share, ASP, shipment, sell-through, backlog, channel inventory, or undisclosed product KPI.

### 3. Product / Business KPI Exact Layer

This is the strict financial-operating product layer:

- `company_disclosed_product_business_mix_runtime_rows_v0_1`: 1,186 rows / 71 tickers.
  - `company_disclosed_product_business_mix_percent_fact=1,174`
  - `company_disclosed_product_business_revenue_amount_fact=12`
- `industry_operating_metric_slot_rows_v0_1`: 1,923 rows / 186 tickers.
  - includes business/segment operating slots such as orders, payment activity, marketplace GOV, capacity/production, AUM/subscribers where parser gates pass.
- Latest depth:
  - `Product/Business-KPI=443/603`
  - remaining `160` classified gaps.

Boundary:

- `Product-KPI exact` is only one sublayer of product intelligence.
- It should remain strict, but it must not define whether the broader product layer is useful.

### 4. Customer Deployment / Adoption / Relationship Layer

Customer deployment is already partially represented as product graph edge context:

- `official_customer_deployment_surface_context_rows_v0_1`: 336 rows.
  - `official_customer_order_or_deployment_event=214`
  - `supply_chain_official_relationship=122`
- Product graph edges include:
  - `OFFICIAL_CUSTOMER_DEPLOYMENT_EVENT=222`
  - `OFFICIAL_SUPPLY_CHAIN_RELATIONSHIP=147`
  - `PUBLIC_ORDER_OR_TENDER_CONTEXT=273`
  - `CHANNEL_OR_DISTRIBUTION_CONTEXT=99`
- Latest depth:
  - `CustomerDeployment=531/603`
  - remaining `72` gaps.

Boundary:

- CustomerDeployment should not be an isolated dimension anymore.
- It should become typed product graph edges such as `deployed_by`, `ordered_by`, `adopted_by`, `sold_through`, `configured_in`, `regulated_for`, and `contracted_with`.
- These edges can support bounded demand/adoption thesis drivers.
- They cannot directly become revenue, order value, backlog, market share, ASP, or shipment facts unless exact fields are separately disclosed.

### 5. Product Relationship Graph Layer

The graph exists and is usable as a navigation / analyst-context graph:

- `product_relationship_graph_nodes_v0_1`:
  - 8,187 nodes
  - `product_slot=6,521`
  - `company_product_family=663`
  - `company=603`
  - `external_counterparty=321`
  - `product_family=79`
- `product_relationship_graph_edges_v0_1`:
  - 25,251 edges
  - `HAS_PRODUCT_SLOT=6,521`
  - `FAMILY_HAS_PRODUCT_SLOT=6,521`
  - `BELONGS_TO_FAMILY=6,521`
  - `COMPETES_WITH=3,420`
  - `HAS_PRODUCT_FAMILY=663`
  - parser-backed relationship/event edges count: 741.

Boundary:

- `COMPETES_WITH` is currently same-family comparable candidate, not proof of actual win/loss, share shift, pricing pressure, or direct displacement.
- Supply-chain / complement edges are analyst-context edges unless promoted by official/source-specific parser rows.
- The graph has edge types, evidence refs, confidence, claim boundaries, and forbidden claims, but Research Lead / Product Specialist runtime consumption is still an explicit follow-up.

### 6. Fundamental / Capital / Liquidity Layer

Capital and financial substrate is strong but still split by role:

- `sec_financial_statement_metric_runtime_rows_v0_1`: 10,146 rows / 587 SEC-covered tickers.
- `capital_funding_ownership_context_rows_v0_1`: 13,185 rows.
  - `working_capital_liquidity=5,229`
  - `lagged_ownership_context=5,000`
  - `capital_structure_disclosure=2,956`
- `sec_capital_market_event_context_rows_v0_1`: 17,485 rows.
  - offering, Form 3/4/5, 13D/13G, proxy/governance event metadata.
- `market_liquidity_driver_context_rows_v0_1`: 603 rows.
- Latest depth:
  - `CapitalMarketDetail=601/603`
  - `MarketLiquidity=603/603`.

Boundary:

- Form/event metadata is event-existence context unless exact source-specific parser extracts amount/share/ownership/vote/term fields.
- 13F is lagged ownership context, not real-time flow.
- Market liquidity rows are public price/volume context, not short interest/options/ETF/factor flow authority.

### 7. Runtime / Agent Graph Layer

Runtime already has channels needed for this architecture:

- Multi-agent graph order includes Research Lead, reflection gate, universe relationship expansion, evidence operators, fusion selector, coverage reflection, second pass, specialist subgraph, aggregate judgment, memo writer, verifier, renderer.
- Runtime state includes:
  - `product_evidence_rows`
  - `public_source_context_rows`
  - `source_capability_router`
  - `source_authority_coverage`
  - `fundamental_statement_pack`
  - `memo_logic_plan`
  - `supervising_analyst_pack`
  - `relationship_graph_observation`
  - `claim_evidence_ledger`
  - `typed_gap_ledger`
- `RuntimeSourceContextStore` can already attach product/public rows into runtime.

Boundary:

- Product graph and exact-slot matrix are not yet unified as a first-class `ProductIntelligenceGraph` contract consumed by Research Lead and Product Specialist.
- Current checklist still has open follow-ups for product graph runtime integration and exact-slot runtime integration.

## Key Diagnosis

1. The project already has most raw ingredients for the six product-intelligence layers, but they are scattered across source authority rows, product slots, ProductSpec/Profile rows, Product-KPI rows, CustomerDeployment rows, relationship graph edges, and depth gates.
2. `CustomerDeployment` is structurally a graph edge, not a standalone isolated dimension. It should be attached to product/family/customer/channel/counterparty nodes and then used by thesis driver logic.
3. `Product-KPI exact` should remain strict, but it should not be used as the only product-quality gate. Product specs, architecture, deployment, customer adoption, benchmark, channel availability, and supply-chain read-through need their own authority path.
4. Product graph edges are currently mixed:
   - hard structural edges: company -> family -> slot;
   - comparable/navigation edges: same-family competition candidates;
   - parser-backed event/context edges: customer deployment, supply-chain, order/tender, channel;
   - template analyst-context edges: upstream/complement/dependency.
   These need separate promotion rules.
5. The next architecture should not rebuild everything. It should normalize existing artifacts into one `ProductIntelligenceGraph` / `ProductEvidencePack` and make Research Lead / Product Specialist consume it deterministically.

## Recommended Next Step

Implement a `ProductIntelligenceGraph v0.1` integration slice before more data scraping.

### PIG-0 Contract

Define the runtime contract:

- `ProductProfileNode`
- `ProductSpecNode`
- `ProductGenerationEdge`
- `ProductKPIExactFact`
- `CustomerDeploymentEdge`
- `ChannelAdoptionEdge`
- `SupplyChainRelationshipEdge`
- `CompetitiveComparableEdge`
- `ProductPerformanceProxy`
- `ProductEvidencePack`

Each object must carry:

- `ticker`
- `product_family_id`
- `product_or_service`
- `source_role`
- `authority_type`
- `evidence_refs`
- `claim_boundary`
- `forbidden_claims`
- `confidence`
- `period_or_event_date`
- `promotion_status`

### PIG-1 Normalizer

Build a normalizer that reads existing manifests and emits one company/family-scoped pack:

- `company_product_slots_v0_1`
- `product_relationship_graph_edges_v0_1`
- `official_product_spec_context_rows_v0_1`
- `company_disclosed_product_profile_context_rows_v0_1`
- `company_disclosed_product_business_mix_runtime_rows_v0_1`
- `industry_operating_metric_slot_rows_v0_1`
- `official_customer_deployment_surface_context_rows_v0_1`
- `targeted_supply_chain_official_relationship_context_rows_v0_1`
- `family_source_route_plan_v0_1`

Output:

- `product_intelligence_graph_nodes_v0_1.jsonl`
- `product_intelligence_graph_edges_v0_1.jsonl`
- `product_intelligence_company_pack_v0_1.jsonl`
- `product_intelligence_gap_ledger_v0_1.jsonl`
- summary / gate report.

### PIG-2 Authority Gate

Separate edge authority into:

- `exact_product_kpi_authority`
- `technical_fact_authority`
- `deployment_signal_authority`
- `channel_presence_signal`
- `supply_chain_signal`
- `competitive_context_candidate`
- `template_context_edge`
- `commercial_gap`

The gate must block:

- spec -> revenue/share/sales
- deployment -> order amount/revenue/backlog
- channel -> ASP/sell-through/inventory
- same-family comparable -> direct displacement/win-loss
- supply-chain relationship -> allocation/share/gross margin

### PIG-3 Runtime Consumption

Research Lead should read the ProductEvidencePack before assigning specialists:

- decide product/technology specialist scope from product family graph;
- decide whether `CustomerDeployment` is evidence, retrievable gap, bounded gap, or not applicable;
- decide which edges can support thesis drivers;
- dispatch targeted repair only for missing but theoretically retrievable product edges.

Product Specialist should output:

- product capability judgment;
- competitive comparison;
- deployment/adoption read-through;
- product-to-financial bridge;
- evidence boundary and missing data.

Memo Writer should not read raw slots directly; it should read the Research Lead logic plan derived from the ProductEvidencePack.

### PIG-4 Eval

Add deterministic eval before full-chain:

- NVDA / AMD / GOOGL TPU: spec + architecture + customer deployment + competitive edges cannot become SKU revenue.
- ASML / TSM / AMAT / LRCX: semicap / foundry upstream dependency edges must remain bounded but usable for supply-chain read-through.
- MSFT / AMZN / GOOGL: cloud capex and AI service deployment must bridge to supplier read-through without pretending supplier revenue exact.
- Auto / pharma / SaaS representative cases should prove ProductProfile works for non-SKU service/product models.

## Decision

Proceed with `ProductIntelligenceGraph v0.1` as the next implementation slice. Do not lower `Product-KPI exact` gates. Instead, create a parallel, bounded but usable product-intelligence authority path so product specs, architecture, deployment, competitive relationship, supply-chain and channel signals can support thesis drivers with explicit boundaries.

## Verification

This was an audit/documentation task only. No runtime code, data manifest, or test artifact was changed in this entry.
