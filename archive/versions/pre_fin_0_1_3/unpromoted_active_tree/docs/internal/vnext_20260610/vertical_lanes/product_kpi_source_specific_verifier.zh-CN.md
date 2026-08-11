# Product-KPI Source-Specific Verifier

- schema_version: `finsight_product_kpi_source_specific_verifier_summary_v0_1`
- generated_at: `2026-06-25T15:20:10Z`
- status: `pass`
- target_ticker_count: `272`
- candidate_count: `21838`
- promotable_product_metric_count: `12`
- business_segment_metric_candidate_count: `7468`
- region_only_candidate_count: `1653`
- percentage_or_change_candidate_count: `5608`
- sentence_relation_insufficient_candidate_count: `988`
- operating_metric_defer_step2_candidate_count: `2236`
- unclassified_candidate_count: `0`

## Class Counts

| class | count |
| --- | ---: |
| `business_segment_metric` | 7468 |
| `business_segment_mixed_table_needs_column_group` | 1454 |
| `non_product_or_total` | 2035 |
| `operating_metric_defer_step2` | 2236 |
| `percentage_or_change` | 5608 |
| `period_or_version_conflict` | 384 |
| `promotable_product_category_or_product_line_metric` | 12 |
| `region_only` | 1653 |
| `sentence_relation_insufficient` | 988 |

## Ticker Summary Samples

| ticker | candidates | top classes |
| --- | ---: | --- |
| `ABNB` | 50 | `{"operating_metric_defer_step2": 12, "region_only": 36, "sentence_relation_insufficient": 2}` |
| `ABT` | 76 | `{"business_segment_metric": 42, "non_product_or_total": 22, "region_only": 12}` |
| `ACLS` | 18 | `{"non_product_or_total": 6, "percentage_or_change": 12}` |
| `ACN` | 55 | `{"business_segment_metric": 30, "business_segment_mixed_table_needs_column_group": 4, "non_product_or_total": 3, "operating_metric_defer_step2": 9, "percentage_or_change": 9}` |
| `ADI` | 90 | `{"percentage_or_change": 90}` |
| `ADP` | 14 | `{"percentage_or_change": 14}` |
| `ADSK` | 42 | `{"business_segment_metric": 21, "business_segment_mixed_table_needs_column_group": 3, "percentage_or_change": 18}` |
| `AEP` | 69 | `{"business_segment_metric": 20, "operating_metric_defer_step2": 9, "period_or_version_conflict": 40}` |
| `AIG` | 58 | `{"business_segment_mixed_table_needs_column_group": 9, "non_product_or_total": 40, "region_only": 6, "sentence_relation_insufficient": 3}` |
| `AJG` | 259 | `{"business_segment_metric": 72, "business_segment_mixed_table_needs_column_group": 83, "non_product_or_total": 81, "percentage_or_change": 23}` |
| `ALB` | 64 | `{"business_segment_metric": 21, "business_segment_mixed_table_needs_column_group": 9, "non_product_or_total": 6, "percentage_or_change": 1, "region_only": 27}` |
| `ALGN` | 89 | `{"business_segment_metric": 23, "business_segment_mixed_table_needs_column_group": 4, "non_product_or_total": 15, "percentage_or_change": 30, "region_only": 17}` |
| `ALLE` | 26 | `{"percentage_or_change": 26}` |
| `ANET` | 52 | `{"non_product_or_total": 6, "percentage_or_change": 10, "region_only": 36}` |
| `AON` | 131 | `{"business_segment_metric": 72, "business_segment_mixed_table_needs_column_group": 8, "non_product_or_total": 20, "period_or_version_conflict": 13, "region_only": 10, "sentence_relation_insufficient": 8}` |
| `AOS` | 68 | `{"business_segment_metric": 48, "region_only": 6, "sentence_relation_insufficient": 14}` |
| `APD` | 19 | `{"operating_metric_defer_step2": 10, "percentage_or_change": 6, "sentence_relation_insufficient": 3}` |
| `APP` | 30 | `{"region_only": 30}` |
| `ARM` | 72 | `{"business_segment_metric": 50, "non_product_or_total": 9, "percentage_or_change": 1, "region_only": 12}` |
| `ASML` | 150 | `{"business_segment_metric": 75, "business_segment_mixed_table_needs_column_group": 11, "non_product_or_total": 7, "percentage_or_change": 20, "period_or_version_conflict": 1, "region_only": 36}` |
| `AVB` | 9 | `{"percentage_or_change": 9}` |
| `AVY` | 220 | `{"business_segment_metric": 96, "business_segment_mixed_table_needs_column_group": 7, "non_product_or_total": 45, "region_only": 72}` |
| `BALL` | 65 | `{"non_product_or_total": 2, "percentage_or_change": 63}` |
| `BAX` | 322 | `{"business_segment_metric": 102, "business_segment_mixed_table_needs_column_group": 78, "non_product_or_total": 12, "operating_metric_defer_step2": 36, "percentage_or_change": 73, "region_only": 20, "sentence_relation_insufficient": 1}` |
| `BDX` | 194 | `{"business_segment_metric": 80, "non_product_or_total": 5, "operating_metric_defer_step2": 3, "percentage_or_change": 16, "region_only": 30, "sentence_relation_insufficient": 60}` |
| `BE` | 10 | `{"business_segment_metric": 6, "non_product_or_total": 4}` |
| `BEN` | 29 | `{"business_segment_metric": 13, "non_product_or_total": 3, "percentage_or_change": 1, "region_only": 12}` |
| `BF-B` | 10 | `{"percentage_or_change": 10}` |
| `BHP` | 211 | `{"operating_metric_defer_step2": 211}` |
| `BILL` | 42 | `{"business_segment_metric": 24, "operating_metric_defer_step2": 18}` |

## Boundary

This verifier classifies strict Product-KPI repair candidates before promotion. Only product/category/product-line currency revenue rows with product-table context are promotable as Product-KPI exact. Business segment rows are classified for Step 2 and are not product-family KPI proof.
