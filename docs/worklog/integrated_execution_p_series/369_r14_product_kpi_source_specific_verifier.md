# 369 R14 Product-KPI Source-Specific Verifier

Date: 2026-06-19

## Scope

按当前 1-6 修复顺序完成第 1 步：先修 Product-KPI verifier。目标不是降低 Product-KPI exact 门槛，而是把 272 家 `product_kpi_source_specific_table_verifier` 候选逐条分成：

- 可提权 product/category/product-line metric
- business segment metric
- region-only
- percentage/change
- sentence relation 不足
- operating metric 待第 2 步

## Implementation

新增：

- `scripts/data_expansion/build_product_kpi_source_specific_verifier.py`
- `tests/test_product_kpi_source_specific_verifier.py`

更新：

- `scripts/data_expansion/build_company_gap_docket.py`
- `docs/architecture/agent_graph_vnext/19_source_role_product_kpi_exact_slot_deep_repair.zh-CN.md`
- `docs/internal/vnext_20260610/vertical_lanes/product_kpi_source_specific_verifier.zh-CN.md`

Runtime outputs:

- `data/manifests/product_kpi_source_specific_verifier_v0_1.jsonl`
- `data/manifests/product_kpi_source_specific_verifier_ticker_summary_v0_1.jsonl`
- `data/manifests/product_kpi_source_specific_verifier_promotable_rows_v0_1.jsonl`
- `data/manifests/product_kpi_source_specific_verifier_summary_v0_1.json`

`CompanyGapDocket` now carries `source_specific_verifier_summary` for Product-KPI docket rows, so Step 2 can consume classified segment/operating candidates directly.

## Results

Verifier strict run:

- `target_ticker_count=272`
- `candidate_count=21,822`
- `unclassified_candidate_count=0`
- `promotable_product_metric_count=0`
- `business_segment_metric_candidate_count=7,468`
- `operating_metric_defer_step2_candidate_count=2,232`
- `region_only_candidate_count=1,653`
- `percentage_or_change_candidate_count=5,608`
- `sentence_relation_insufficient_candidate_count=988`

Key conclusion: the 272 companies are now classified, not ignored. No candidate safely promoted to Product-KPI exact because the available rows are business segment rows, operating metrics, region rows, percentage/change cells, sentence candidates without local relation verification, period conflicts, or generic total/non-product rows.

## Verification

- `python -m pytest tests\test_product_kpi_source_specific_verifier.py -q` -> `4 passed`
- `python -m py_compile scripts\data_expansion\build_product_kpi_source_specific_verifier.py`
- `python scripts\data_expansion\build_product_kpi_source_specific_verifier.py --strict` -> `status=pass`
- `python -m py_compile scripts\data_expansion\build_company_gap_docket.py`
- `python -m pytest tests\test_company_gap_docket.py tests\test_product_kpi_source_specific_verifier.py -q` -> `6 passed`
- `python scripts\data_expansion\build_company_gap_docket.py --strict` -> `status=pass`, `unclassified_docket_count=0`
- `python -m pytest tests\test_product_kpi_deep_gap_diagnostic.py tests\test_product_kpi_repair_promotion.py -q` -> `14 passed`

## Next

Proceed to Step 2 only after this verifier remains green:

- repair industry operating metric slot
- convert eligible business/segment/operating metrics into industry-specific exact slots such as AUM, deposits, loan balance, capacity, utilization, MW, contracts, ARR/subscribers, patient volume
- keep Product-KPI exact separate from business/operating metric exact
