# R26 Second / Third Layer Runtime Acceptance Gate

Date: 2026-06-24

## Scope

This entry records the runtime implementation of the R26 second-layer and third-layer deterministic acceptance gates. The prior `391` entry froze the contract. This entry verifies that current manifests and runtime objects can satisfy the gates without LLM judgment.

## Code Changes

- Added `src/sec_agent/layer_acceptance_gates.py`.
- Added `scripts/data_expansion/build_r26_second_third_layer_acceptance_gates.py`.
- Added `FundamentalPeerStatementPanel` to `src/sec_agent/financial_statement_analysis.py`.
- Wired `FundamentalPeerStatementPanel` into:
  - `build_agent_data_view("fundamental_analyst", ...)`
  - `build_specialist_request_from_state("fundamental_analyst", ...)`
  - specialist known evidence refs and repair payload compaction.

## Generated Artifacts

- `data/manifests/r26_second_layer_acceptance_gate_summary_v0_1.json`
- `data/manifests/r26_third_layer_acceptance_gate_summary_v0_1.json`
- `data/manifests/r26_second_third_layer_acceptance_gate_summary_v0_1.json`

Gate status:

- second layer: `pass`
- third layer: `pass`
- combined: `pass`

Second-layer acceptance metrics:

- Company product-slot coverage: `603/603`.
- ProductRelationshipGraph: `6,454` slots, `24,237` edges, summary validation pass.
- Relationship coverage includes `COMPETES_WITH=3,358` and nonzero supply/input/manufacturing dependency coverage.
- Product-KPI closeout covers `603` companies with `unclassified_count=0`.
- Product-KPI closeout states: `product_kpi_exact_ready=173`, `business_segment_metric_ready=52`, `geographic_or_non_product_metric_only=10`, `product_kpi_exact_gap=368`.
- R17 strong product signal rows: `24`; non-financial boundary violation count: `0`.

Third-layer acceptance metrics:

- SEC FSD + non-US L1 financial statement coverage reaches the `603` company universe.
- SEC structured financial statement rows include AR, inventory, AP, deferred revenue, current assets/current liabilities, cash, short-term debt, OCF, and capex proxy.
- Capital/funding/ownership context rows: `13,185`.
- Capital context split: `capital_structure_disclosure=2,956`, `lagged_ownership_context=5,000`, `working_capital_liquidity=5,229`.
- SEC capital-market filing-event rows: `7,584`.
- R18 registry and authority mart hard gates pass.

## FundamentalPeerStatementPanel

`FundamentalPeerStatementPanel` converts `FundamentalStatementPack` into a deterministic planning surface:

- `ThreeStatementMetricPanel`
- `PeerComparableMetricPanel`
- `IndustryPriorityMetricPanel`
- `DerivedMetricPanel`
- `ProductFinancialBridge`
- `CapitalFundingBridge`
- `StatementAnomalyDetector`

The panel is not a writer. It gives the fundamental analyst a structured planning surface so the agent can reason by financial dimension rather than listing evidence rows.

## Verification

Commands:

```powershell
python scripts/data_expansion/build_r26_second_third_layer_acceptance_gates.py
python -m pytest tests/test_r26_layer_acceptance_gates.py tests/test_financial_statement_analysis.py -q
python -m pytest tests/test_product_slot_relationship_graph.py tests/test_source_route_registry_v2.py tests/test_r18_data_source_admission_ledger.py tests/test_sec_capital_market_event_context_rows.py tests/test_capital_funding_ownership_context_rows.py -q
python -m py_compile src/sec_agent/layer_acceptance_gates.py scripts/data_expansion/build_r26_second_third_layer_acceptance_gates.py src/sec_agent/financial_statement_analysis.py src/sec_agent/multi_agent_runtime.py src/sec_agent/specialist_llm.py
```

Results:

- R26 gate script: `pass/pass/pass`.
- R26 + financial panel tests: `7 passed`.
- Related registry/runtime tests: `20 passed`.
- `py_compile`: pass.

## Boundaries

R26 pass does not claim SKU revenue, unit sales, ASP, market share, sell-through, backlog, order value, or realtime fund flows are public exact facts. It confirms:

- second-layer product/product-family/relationship/signal scaffolding is parser-backed and boundary-gated;
- third-layer financial statement, working-capital, capital-context, and capital filing-event metadata are accepted under explicit authority boundaries;
- exact parser follow-ups remain open for Form 3/4/5 XML, 13D/13G schedules, offering terms, proxy tables, N-PORT/fund flow, short interest, ETF/factor flow, and more granular market-liquidity data.
