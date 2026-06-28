# RD0 Raw Disclosure / RAG / Database Inventory

- Generated at: `2026-06-26T16:27:13+00:00`
- Status: `pass`
- Raw disclosure inventory rows: `31`
- RAG index inventory rows: `19`
- Runtime database inventory rows: `11`
- Missing path count: `1`
- Missing required path count: `0`
- Missing optional configured path count: `1`

## Outputs

- `raw_disclosure_data_inventory`: `D:\FIN_Insight_Agent\data\manifests\raw_disclosure_data_inventory_v0_1.jsonl`
- `rag_index_inventory`: `D:\FIN_Insight_Agent\data\manifests\rag_index_inventory_v0_1.jsonl`
- `runtime_database_inventory`: `D:\FIN_Insight_Agent\data\manifests\runtime_database_inventory_v0_1.jsonl`
- `summary`: `D:\FIN_Insight_Agent\data\manifests\raw_disclosure_rag_database_inventory_summary_v0_1.json`
- `report`: `D:\FIN_Insight_Agent\docs\internal\vnext_20260610\rd0_raw_disclosure_rag_database_inventory.zh-CN.md`

## Raw Layers

| Layer | Rows |
| --- | ---: |
| `authority_mart` | `1` |
| `bronze_raw` | `8` |
| `bronze_source_plan` | `1` |
| `bronze_to_silver_summary` | `1` |
| `gold_fact_mart_candidate` | `6` |
| `gold_signal_mart_candidate` | `6` |
| `graph_candidate` | `3` |
| `quality_gate` | `1` |
| `silver_parsed` | `3` |
| `silver_staging` | `1` |

## RAG Index Types

| Index type | Rows |
| --- | ---: |
| `dense_embedding_baseline` | `2` |
| `milvus_lite_vector_collection` | `1` |
| `rank_bm25` | `15` |
| `sqlite_fts5` | `1` |

## Runtime Database Kinds

| Database kind | Rows |
| --- | ---: |
| `duckdb` | `7` |
| `object_store_root` | `1` |
| `runtime_private_root` | `1` |
| `sqlite` | `2` |

## Boundary

- 本 inventory 只说明数据资产存在、规模、schema hint、主键和血缘状态；不把任何 URL、chunk、vector hit 或 closeout row 直接提升为 evidence。
- Milvus 继续保持 semantic recall supplement，不提供 exact-value authority。
- 后续 RD1/RD2 应在此基础上补 raw source provenance 和 parser run ledger。
