# 341 R12 Company-Reported Product KPI Runtime Projection

Date: 2026-06-16

## Scope

This checkpoint projects parser/quality verified company-disclosed product KPI facts into runtime-visible L1 exact rows.

It does not rescan broad keyword candidates, and it does not promote unverified `company_product_operating_metric_candidates` rows.

## Changes

- Added `scripts/data_expansion/build_company_reported_product_operating_metric_runtime_rows.py`.
- Added `tests/test_company_reported_product_operating_metric_runtime_rows.py`.
- Extended `src/sec_agent/source_coverage_gate.py` source-class mapping for `company_reported_product_operating_metric`.

## Runtime Materialization

Input:

- `Z:/FIN_Insight_Agent/data/manifests/product_evidence_v0_1/company_product_kpi_facts_parser_verified_with_quality_operating_repair_v0_1.jsonl`

Generated outputs:

- `data/manifests/company_reported_product_operating_metric_runtime_rows_v0_1.jsonl`
- `data/manifests/company_reported_product_operating_metric_runtime_rejections_v0_1.jsonl`
- `data/manifests/company_reported_product_operating_metric_runtime_summary_v0_1.json`
- `data/manifests/company_reported_product_operating_metric_runtime_coverage_gate_v0_1.json`

Observed result:

- `input_fact_count=5,976`
- `runtime_row_count=5,976`
- `exact_runtime_row_count=5,976`
- `runtime_ticker_count=186`
- `rejection_count=0`
- `primary_company_disclosure` runtime-case coverage gate: `pass`
- `official_product_surface` runtime-case coverage gate: `pass`

Metric family distribution:

- `product_revenue=5,682`
- `production_or_throughput=239`
- `unit_sales_or_deliveries=47`
- `backlog_or_orders=6`
- `subscribers_or_arpu=2`

Repair status distribution:

- `baseline_parser_verified=5,922`
- `monotonic_repair_promoted=45`
- `operating_metric_repair_promoted=9`

## Claim Boundary

Allowed:

- company-disclosed product/segment KPI facts for the disclosed `product_or_segment`, `metric`, `period`, `unit`, `value`, and citation span

Forbidden:

- market share
- channel inventory
- sell-through
- undisclosed SKU economics
- commercial tracker estimates
- inference beyond the cited company-disclosed metric

Every generated row is:

- `source_id=company_reported_product_operating_metrics`
- `source_family=company_product_evidence_graph`
- `source_layer_id=L1`
- `promotion_status=runtime_fact_allowed`
- `exact_value_authority=true`
- `can_support_company_exact_fact=true`

## Verification

Commands run:

```powershell
python -m py_compile src\sec_agent\source_coverage_gate.py scripts\data_expansion\build_company_reported_product_operating_metric_runtime_rows.py scripts\data_expansion\build_official_product_surface_context_rows.py
python -m pytest tests\test_source_coverage_gate.py tests\test_official_product_surface_context_rows.py tests\test_company_reported_product_operating_metric_runtime_rows.py tests\test_company_product_evidence_graph.py -q
python scripts\data_expansion\build_company_reported_product_operating_metric_runtime_rows.py --strict
```

Results:

- targeted tests: `13 passed`
- runtime projection strict: `pass`

## Remaining Gap

The product evidence graph still reports:

- `companies_with_sec_verified_product_kpi=186`
- `companies_with_company_disclosed_kpi_gap=417`

This means product KPI exact facts are now runtime-addressable where parser gates passed, but the remaining companies still need source-specific parser repair, official/IR targeted repair, or explicit public/commercial gap exposure.

Commercial tracker gaps remain outside the no-commercial policy boundary for market share, channel inventory, sell-through, POS, app revenue, and consensus-style estimates.
