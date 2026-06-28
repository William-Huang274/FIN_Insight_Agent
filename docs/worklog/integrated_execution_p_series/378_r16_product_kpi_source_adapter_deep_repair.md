# 378 R16 Product-KPI Source Adapter Deep Repair

Date: 2026-06-21

## Scope

Continue after R15 public-source gap exhaustion. The goal was not to reopen weak fallback, but to deep-repair the remaining company-disclosed Product-KPI / source-adapter buckets where parser-backed exact rows could still be promoted or safely rerouted.

## Changes

- Added `scripts/data_expansion/build_r16_product_kpi_deep_repair_rows.py`.
- Materialized `r16_product_kpi_deep_repair_runtime_rows_v0_1.jsonl`, attempts, summary, and internal report.
- Wired R16 rows into:
  - `build_exact_slot_coverage_matrix.py`
  - `build_exact_slot_gap_closeout_ledger.py`
  - `build_product_kpi_deep_gap_diagnostic.py`
  - `runtime_source_context_store.py`
- Added deterministic tests in `tests/test_r16_product_kpi_deep_repair_rows.py`.

## Result

R16 strict summary:

- `runtime_row_count=76`
- `runtime_ticker_count=8`
- `product_kpi_exact_repair_row_count=52`
- `business_segment_metric_repair_row_count=12`
- `operating_metric_repair_row_count=12`
- `attempt_row_count=1088`
- `unclassified_attempt_count=0`

Exact-slot refresh:

- validation `pass`
- `all_required_exact_ready_company_count=503`
- `partial_exact_ready_company_count=100`
- `no_exact_ready_company_count=0`
- `exact_slot_gap_count=108`

Product-KPI closeout:

- `product_kpi_exact_ready_ticker_count=172`
- `business_segment_metric_ready_ticker_count=52`
- `product_or_business_kpi_ready_ticker_count=224`
- `product_kpi_gap_count=369`
- `unclassified_closeout_count=0`

Deep diagnostic:

- `product_family_exact_ready_ticker_count=134`
- `business_or_segment_exact_ready_ticker_count=90`
- `product_or_business_kpi_ready_ticker_count=224`
- `no_candidate_gap_ticker_count=105`
- `strict_candidate_gap_ticker_count=264`
- `unclassified_count=0`

## Boundary

R16 does not treat product pages, channel rows, hiring rows, patents, news, geography-only rows, percentage/change rows, or generic segment rows as product sales / ASP / market-share / sell-through / SKU economics evidence. Boundary and closeout rows remain non-evidence.

## Verification

```powershell
python scripts/data_expansion/build_r16_product_kpi_deep_repair_rows.py --strict
python scripts/data_expansion/build_exact_slot_coverage_matrix.py
python scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py --strict
python scripts/data_expansion/build_product_kpi_deep_gap_diagnostic.py --strict
python -m pytest tests/test_r16_product_kpi_deep_repair_rows.py -q
python -m py_compile scripts/data_expansion/build_r16_product_kpi_deep_repair_rows.py scripts/data_expansion/build_exact_slot_coverage_matrix.py scripts/data_expansion/build_exact_slot_gap_closeout_ledger.py scripts/data_expansion/build_product_kpi_deep_gap_diagnostic.py src/sec_agent/runtime_source_context_store.py
```

All targeted checks passed.
