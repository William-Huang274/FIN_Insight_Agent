# 273 Product KPI Final Public Repair Closeout

Date: 2026-06-12

## Prompt

User asked to document the four rejection groups, execute repairs in order, and return only after all facts that can be fixed or promoted under public/free data have been handled. Weak proxy fallback and commercial-tracker substitution remain disallowed.

## Decision

Use SEC/global filings as the only runtime fact anchor for company-disclosed product KPI facts. Public official/regulatory/macro sources remain context or gap evidence unless a source-specific parser can bind company/product/metric/value/unit/period/citation.

The final public repair chain is:

1. v0.4 rejection closeout audit.
2. Source-specific revenue table repair.
3. Quality filter for accepted fact false positives.
4. Operating metric repair for non-revenue product performance facts.
5. Sentence local verifier.
6. Final product evidence graph and closeout ledger.

## Work Completed

- Added the execution plan: `docs/internal/vnext_20260610/product_kpi_rejection_repair_execution_plan_v0_4.zh-CN.md`.
- Added a closeout classifier that consumes the final accepted fact layer plus phase rejection ledgers, so accepted/rejected rows do not stay in the unresolved repair bucket.
- Extended source-specific revenue repair to v0.4:
  - TSN `Sales | Operating Income (Loss)` promotes only Sales block values.
  - DRI `Sales | Average Annual Sales per Restaurant` promotes only the sales-in-millions block.
- Added a quality filter that removes high-confidence false positives from the runtime layer:
  - non-positive product revenue facts,
  - subscriber metrics misclassified as revenue,
  - ED `Total Gas Delivered to CECONY Customers` rows with unrepaired `units/systems` units.
- Added operating metric repair:
  - WBD Total Streaming subscribers promoted as `subscribers_or_arpu / streaming_subscribers`.
  - ED CECONY Gas Delivered promoted as `unit_sales_or_deliveries / gas_delivered` with unit `MDt`.
- Added a strict sentence verifier; no sentence candidates passed the local product-value-revenue relation gate.
- Rebuilt the final public repair fact layer and evidence graph.

## Results

Final accepted fact layer:

- Facts: `5,976`.
- Covered tickers: `186`.
- Monotonic revenue repair facts: `45` across `10` tickers.
- Operating metric repair facts: `9` across `2` tickers.
- Sentence repair facts: `0`.

Quality filter:

- Input facts: `6,207`.
- Filtered facts before operating repair: `5,967`.
- Suppressed facts: `240`.
- Suppression reasons:
  - `non_positive_product_revenue_level_invalid`: `196`.
  - `ed_gas_delivered_requires_mdt_source_specific_repair`: `40`.
  - `subscriber_metric_misclassified_as_product_revenue`: `4`.

Operating repair:

- Promoted: `9` facts.
- ED: `7` CECONY Gas Delivered facts for FY2019-FY2025, unit `MDt`.
- WBD: `2` Total Streaming subscriber facts, unit `subscribers`.
- Rejected: `33` rows:
  - `20` ED small/customer-count/subtotal row-binding failures.
  - `13` duplicate operating claims already covered by the promoted MDt rows.

Sentence verifier:

- Candidates: `428` across `43` tickers.
- Promoted: `0`.
- Rejections:
  - `local_product_value_relation_not_verified`: `229`.
  - `sentence_non_currency_or_percentage_not_level_revenue`: `123`.
  - `change_or_financial_context_not_level_revenue_fact`: `56`.
  - `local_revenue_metric_word_missing`: `20`.

Final evidence graph:

- Companies: `603`.
- SEC taxonomy coverage: `566`.
- SEC verified product-KPI coverage: `186`.
- Company-disclosed KPI gap companies: `417`.
- Evidence nodes: `5,873`.
- Gaps: `2,979`.
- Repair candidate companies still review-only: `112`.

Final closeout ledger over v0.4 rejections:

- Rows: `1,300` across `99` tickers.
- Accepted/non-gap:
  - `already_covered_not_gap`: `275`.
  - `correctly_rejected_cell_not_gap`: `18`.
  - `final_accepted_not_gap`: `9`.
- Phase-verified rejected/non-gap: `448`.
- Remaining parser/schema candidates:
  - `region_schema_candidate`: `69`.
  - `taxonomy_binding_candidate`: `8`.
  - `period_column_group_candidate`: `9`.
  - `versioned_schema_required`: `15`.
  - `revenue_table_schema_candidate`: `0`.
- Non-promotable public disclosure cells: `449`.
- Retired stale buckets from earlier closeout drafts:
  - `revenue_table_schema_candidate` was reduced from `118` to `0` after TSN/DRI/LOW/HUBB/ES source-specific gates and ICE period/column-group classification.
  - `unclassified_review_required` was reduced to `0`.

## Remaining Boundaries

The remaining rows are not all commercial gaps. They fall into these bounded categories:

- Public disclosure exists, but current schema cannot safely express it yet:
  - region/product-region revenue needs a region dimension;
  - GPC-like restatement/source-version conflicts need source-version schema;
  - some table layouts still need audited source-specific column/row binding.
- Public disclosure row is not a level KPI:
  - percentage/change/negative values;
  - sentence growth attribution or financial-context statements;
  - ED low values that are customer count/subtotal row-binding failures.
- Public/free sources cannot directly fill the missing external measurement:
  - market share, ASP, channel inventory, POS sell-through, prescription share, app revenue/downloads, systematic registrations, and forecast tracker metrics remain commercial tracker gaps under current policy.

## Outputs

- Final fact layer: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_final_public_repair_v0_1.jsonl`.
- Final evidence graph: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_final_public_repair_v0_1/`.
- Final closeout ledger: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_repair_final_closeout_v0_1.jsonl`.
- Final closeout summary: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_repair_final_closeout_summary_v0_1.json`.
- Operating repair summary: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_operating_metric_repair_summary_v0_1.json`.
- Sentence verifier summary: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_sentence_repair_summary_v0_1.json`.
- Graph summary: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_final_public_repair_v0_1/company_product_evidence_graph_summary_v0_1.json`.

## Evidence

- `python -m py_compile scripts\data_expansion\audit_product_kpi_rejection_repair_closeout.py scripts\data_expansion\promote_product_kpi_repair_candidates.py scripts\data_expansion\quality_filter_product_kpi_fact_layer.py scripts\data_expansion\promote_product_operating_metric_repair_candidates.py scripts\data_expansion\verify_product_kpi_sentence_repair_candidates.py scripts\data_expansion\build_company_product_evidence_graph.py` -> pass.
- `python -m pytest tests\test_product_kpi_rejection_closeout.py tests\test_product_kpi_repair_promotion.py tests\test_product_kpi_quality_filter.py tests\test_product_operating_metric_repair_promotion.py tests\test_product_kpi_sentence_repair_verifier.py tests\test_company_product_evidence_graph.py` -> `28 passed`.
- `python -m pytest tests\test_product_taxonomy_kpi_parser.py tests\test_product_evidence_strategy_artifacts.py tests\test_public_source_strength_materialization_report.py tests\test_public_source_extended_materialization.py tests\test_public_source_information_strength_report.py tests\test_public_source_mapping_endpoint_gates.py tests\test_public_source_inventory_adapter.py` -> `41 passed`.

## Safety Notes

- The strict baseline was not overwritten; final runtime facts come from quality-filtered accepted facts plus explicit repair-promoted rows.
- ED raw `units/systems` rows are suppressed; only corrected `MDt` rows enter the final runtime layer.
- Sentence-derived candidates remain rejected unless a stricter local relation verifier can prove product/value/revenue binding.
- Commercial tracker gaps are exposed as gaps, not filled by public proxy fallback.
