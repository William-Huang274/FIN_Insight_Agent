# RD2 Silver Parser / Chunk / Table / Metric Ledger

- Generated at: `2026-06-26T17:09:52+00:00`
- Status: `pass_with_recorded_rejections`
- Parser runs: `52`
- Parser output artifacts: `217`
- Rejection taxonomy rows: `38`
- Missing declared outputs: `0`
- Large artifacts not line-counted: `13`

## Outputs

- `parser_run_ledger`: `D:\FIN_Insight_Agent\data\manifests\parser_run_ledger_v0_1.jsonl`
- `parser_output_artifact_ledger`: `D:\FIN_Insight_Agent\data\manifests\parser_output_artifact_ledger_v0_1.jsonl`
- `parser_rejection_taxonomy`: `D:\FIN_Insight_Agent\data\manifests\parser_rejection_taxonomy_v0_1.jsonl`
- `summary`: `D:\FIN_Insight_Agent\data\manifests\parser_quality_summary_v0_1.json`
- `report`: `D:\FIN_Insight_Agent\docs\internal\vnext_20260610\rd2_parser_chunk_table_metric_ledger.zh-CN.md`

## Declared Parser Volume

- Chunks: `161455`
- Tables: `374536`
- Metric candidates: `7974456`
- Claim candidates: `2459906`
- Runtime rows: `19715`
- Context rows: `6556`
- Rejections: `30557`

## Owner Stages

| Stage | Runs |
| --- | ---: |
| `capital_market_context_parser` | `1` |
| `chunk_build` | `1` |
| `customer_deployment_context_parser` | `1` |
| `financial_statement_runtime_parser` | `2` |
| `industry_operating_metric_parser` | `1` |
| `manifest_parser_summary` | `10` |
| `market_context_parser` | `2` |
| `product_kpi_runtime_parser` | `6` |
| `product_surface_context_parser` | `2` |
| `source_context_parser` | `19` |
| `structured_object_extraction` | `7` |

## Artifact Kinds

| Kind | Artifacts |
| --- | ---: |
| `chunk_rows` | `18` |
| `claim_candidates` | `8` |
| `context_rows` | `9` |
| `coverage_gate_json` | `10` |
| `data_mart_rows` | `1` |
| `input_evidence_rows` | `14` |
| `jsonl_rows` | `37` |
| `metric_candidates` | `8` |
| `rejection_rows` | `6` |
| `report_markdown` | `9` |
| `runtime_rows` | `35` |
| `summary_json` | `54` |
| `table_rows` | `8` |

## Rejection Classes

| Class | Rejected rows |
| --- | ---: |
| `business_segment_boundary` | `2` |
| `conflict_resolution` | `2` |
| `financial_statement_not_product_kpi` | `3` |
| `not_product_kpi_exact` | `5` |
| `other` | `10` |
| `outside_canonical_scope` | `1` |
| `parser_schema_gap` | `1` |
| `percentage_or_change_only` | `5` |
| `region_only_or_geography` | `3` |
| `value_unit_period_binding` | `6` |

## Boundary

- RD2 不把 parser rejections、closeout、boundary rows 升级成 accepted evidence。
- GB 级 rowset 以 summary 声明的 row count 为准，避免为 ledger 重扫大文件；需要逐行质量审计时应另起 targeted audit。
- RD2 只处理 parser/chunk/table/metric/claim 质量，不替代 RD3 Gold Fact Mart 和 RD5 retrieval parity。
