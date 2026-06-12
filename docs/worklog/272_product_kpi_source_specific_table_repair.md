# 272 Product KPI Source-Specific Table Repair

Date: 2026-06-11

## Prompt

Continue targeted repair because high-confidence repair facts can be promoted into the SEC product KPI fact layer, while unresolved public/commercial gaps must remain explicit gaps instead of fallback evidence.

## Decision

Keep the monotonic promotion rule from `271`: never replace the accepted baseline fact layer. Add only repair candidates that pass audited source-specific table gates.

The v0.3 gate adds three narrow layouts:

- `Sales of Principal Products` tables for company-disclosed product sales.
- `Total Sales | %` mix tables where only the high-value sales cell is selected and share/percentage cells are rejected.
- Lowe's merchandising-table continuation spans where the table header is truncated, but the citation still contains multiple adjacent Lowe's merchandising categories and share-like cells.

The gate still rejects sentence-derived candidates, existing baseline claims, generic labels, change/growth columns, period-after-fiscal-year rows, non-currency rows, and same-claim multi-value conflicts.

## Work Completed

- Extended `scripts/data_expansion/promote_product_kpi_repair_candidates.py` from broad v0.1 promotion into source-specific v0.3 promotion.
- Added tests for principal-product sales tables, total-sales/percentage mix tables, same-claim conflicts, and Lowe's truncated continuation spans.
- Materialized v0.3 combined facts, promoted-only facts, rejection ledger, and promotion summary on Z.
- Rebuilt the 603-company product evidence graph with the v0.3 combined fact layer.
- Updated the evidence graph builder defaults so a no-argument run uses the v0.3 monotonic fact layer and v0.3 graph output directory.

## Results

Promotion output:

- Baseline facts preserved: `6,162`.
- Semantic repair candidates evaluated: `1,345` across `101` tickers.
- Promoted facts: `24` across `6` tickers.
- Combined facts: `6,186` across `184` tickers.
- Rejected repair candidates: `1,321`.

Promoted scope:

- `company_disclosed_product_or_segment_revenue`: `12` facts across AMT, KMB, and LOW.
- `company_disclosed_geographic_segment_revenue`: `12` facts across ABNB, COIN, and ENPH.

Incremental v0.3 source-specific additions over v0.1:

- KMB: `2` Consumer Tissue sales facts from `Sales of Principal Products`.
- LOW: `6` Kitchens & Bath / Millwork sales facts from audited merchandising sales-mix tables.

Evidence graph after v0.3:

- SEC verified product-KPI coverage: `184` companies, up from `179` baseline and `183` v0.1 monotonic repair.
- Company-disclosed KPI gap: `419` companies, down from `424` baseline and `420` v0.1.
- Evidence nodes: `5,861`.
- Gaps: `2,981`.
- Monotonic repair facts in graph: `24` across `6` companies.

## Remaining Gaps

The largest rejection reasons remain:

- `not_structured_table_metric`: `428`.
- `not_currency_revenue`: `277`.
- `claim_already_covered_by_baseline`: `242`.
- `missing_strong_revenue_table_context`: `103`.
- `forbidden_financial_statement_context`: `73`.
- `not_bound_to_structured_row_label`: `67`.

Not promoted in this pass:

- ED gas/electric delivery and revenue-like utility tables: table semantics still mix delivery volumes, revenue, and operating-revenue rows.
- DRI restaurant sales tables: current and prior-year high values collide under the same claim because the parser does not yet preserve the table's column group.
- GPC geographic net sales tables: period/column assignment creates multiple high-value conflicts for the same claim.
- Pharma/medtech product tables with regional columns: current schema lacks a region dimension, so regional product sales cannot be promoted as total product revenue.

## Outputs

- Combined facts: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_with_monotonic_repair_v0_3.jsonl`.
- Promoted facts only: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_monotonic_repair_promoted_v0_3.jsonl`.
- Rejections: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_monotonic_repair_rejections_v0_3.jsonl`.
- Promotion summary: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_monotonic_repair_promotion_summary_v0_3.json`.
- Promotion report: `Z:/FIN_Insight_Agent/docs/internal/vnext_20260610/product_kpi_monotonic_repair_promotion_v0_3_execution.zh-CN.md`.
- Repaired evidence graph: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_monotonic_repair_v0_3/`.
- Evidence graph report: `Z:/FIN_Insight_Agent/docs/internal/vnext_20260610/company_product_evidence_graph_monotonic_repair_v0_3_execution.zh-CN.md`.

## Evidence

- `python -m pytest tests\test_product_kpi_repair_promotion.py` -> `7 passed`.
- `python -m pytest tests\test_product_taxonomy_kpi_parser.py tests\test_product_evidence_strategy_artifacts.py tests\test_public_source_strength_materialization_report.py tests\test_public_source_extended_materialization.py tests\test_product_kpi_repair_promotion.py tests\test_company_product_evidence_graph.py` -> `38 passed`.
- `python -m py_compile scripts\data_expansion\promote_product_kpi_repair_candidates.py scripts\data_expansion\build_company_product_evidence_graph.py` -> pass.
- `python scripts\data_expansion\promote_product_kpi_repair_candidates.py` -> pass, `24` promoted facts.
- `python scripts\data_expansion\build_company_product_evidence_graph.py` -> pass with v0.3 defaults, `2,981` gaps.
- `git diff --check` -> pass.
- Secret scan over touched promotion/worklog files -> no matches.

## Safety Notes

- Baseline facts were preserved unchanged.
- Percentage/share cells from mixed tables are recorded as rejections, not runtime facts.
- Geographic segment rows remain bounded as geographic revenue, not product demand or market share.
- Remaining repair candidates stay in `review_queue_not_runtime_fact`.
