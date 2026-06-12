# 271 Product KPI Monotonic Repair Promotion

Date: 2026-06-11

## Prompt

Continue targeted repair because successfully promoted facts are the highest-confidence option under current public-source constraints.

## Decision

Do not replace the accepted `6,162`-fact baseline with the targeted repair run. Instead, run a monotonic promotion gate: preserve all baseline facts, add only semantic repair candidates that independently pass stricter table-level checks, and reject everything else with explicit reasons.

The promotion gate is intentionally narrow:

- Accept only structured table-derived candidates, not sentence-derived repair rows.
- Require `product_revenue`, `USD`, row-label product/segment binding, positive value, period not after fiscal year, and strong revenue table context.
- Reject change/growth columns, generic labels, forbidden financial-statement contexts, existing baseline claims, and same-claim multi-value conflicts.
- Allow geographic segment revenue only with explicit geographic/revenue table context and mark it as geographic segment revenue, not product performance.

## Work Completed

- Added `scripts/data_expansion/promote_product_kpi_repair_candidates.py`.
- Added `tests/test_product_kpi_repair_promotion.py`.
- Updated `scripts/data_expansion/build_company_product_evidence_graph.py` to expose `monotonic_repair_fact_count`.
- Updated `tests/test_company_product_evidence_graph.py`.
- Materialized the monotonic repaired fact layer and reran the evidence graph with that fact layer.

## Results

Promotion output:

- Baseline facts preserved: `6,162`.
- Semantic repair candidates evaluated: `1,345` across `101` tickers.
- Promoted facts: `16` across `4` tickers.
- Combined facts: `6,178` across `183` tickers.
- Rejected repair candidates: `1,329`.

Promoted scope:

- `company_disclosed_product_or_segment_revenue`: `4` facts, all AMT Data Centers revenue.
- `company_disclosed_geographic_segment_revenue`: `12` facts across ABNB, COIN, and ENPH.

Evidence graph after repair:

- SEC verified product-KPI coverage: `183` companies, up from `179`.
- Company-disclosed KPI gap: `420` companies, down from `424`.
- Evidence nodes: `5,861`.
- Gaps: `2,982`.
- Monotonic repair facts in graph: `16`.

## Outputs

- Combined facts: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_with_monotonic_repair_v0_1.jsonl`.
- Promoted facts only: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_monotonic_repair_promoted_v0_1.jsonl`.
- Rejections: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_monotonic_repair_rejections_v0_1.jsonl`.
- Promotion summary: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_monotonic_repair_promotion_summary_v0_1.json`.
- Promotion report: `Z:/FIN_Insight_Agent/docs/internal/vnext_20260610/product_kpi_monotonic_repair_promotion_execution.zh-CN.md`.
- Repaired evidence graph: `Z:/FIN_Insight_Agent/data/manifests/product_evidence_graph_monotonic_repair_v0_1/`.

## Evidence

- `python -m py_compile scripts\data_expansion\promote_product_kpi_repair_candidates.py scripts\data_expansion\build_company_product_evidence_graph.py` -> pass.
- `python -m pytest tests\test_product_kpi_repair_promotion.py tests\test_company_product_evidence_graph.py` -> `5 passed`.

## Follow-Up

- Add a second pass for source-specific table layouts only where the row/column grid can disambiguate actual revenue values from price/volume/currency waterfalls.
- Keep sentence-derived repair candidates in review until they can prove local product/value relation rather than relying on section-level segment aliases.
- Audit existing baseline same-claim conflicts separately; this promotion pass does not alter baseline rows.

## Safety Notes

- No baseline facts were removed or overwritten.
- Geographic revenue rows are explicitly bounded and cannot be used as product demand or product market-share evidence.
- Large outputs remain on Z.
