# RD5 RAG Index Registry / Retrieval Parity

- Generated at: `2026-06-26T17:44:04+00:00`
- Status: `pass`
- Index snapshots: `22`
- Source lineage rows: `23`
- Total declared records: `12584655`
- Missing source artifacts: `0`
- Missing record-file snapshots: `0`

## Outputs

- `retrieval_index_snapshots`: `D:\FIN_Insight_Agent\data\manifests\retrieval_index_snapshot_registry_v0_1.jsonl`
- `retrieval_index_source_lineage`: `D:\FIN_Insight_Agent\data\manifests\retrieval_index_source_lineage_v0_1.jsonl`
- `sqlite`: `D:\FIN_Insight_Agent\data\workbench_private\research_data\retrieval_index_registry_v0_1.sqlite`
- `summary`: `D:\FIN_Insight_Agent\data\manifests\retrieval_index_registry_summary_v0_1.json`
- `report`: `D:\FIN_Insight_Agent\docs\internal\vnext_20260610\rd5_retrieval_index_registry.zh-CN.md`

## Index Types

| Index type | Snapshots |
| --- | ---: |
| `dense_numpy_cosine` | `2` |
| `milvus_lite_vector_collection` | `1` |
| `rank_bm25` | `16` |
| `sqlite_fts5` | `3` |

## Source Artifact Status

| Status | Lineage rows |
| --- | ---: |
| `source_artifact_exists` | `22` |
| `source_artifact_missing_but_record_snapshot_has_raw_trace` | `1` |

## Parser Artifact Link

| Status | Lineage rows |
| --- | ---: |
| `matched_parser_artifact` | `20` |
| `no_parser_artifact_match` | `3` |

## Record Snapshot Trace Status

| Status | Lineage rows |
| --- | ---: |
| `no_records_jsonl_snapshot` | `5` |
| `record_snapshot_has_raw_trace` | `17` |
| `record_snapshot_without_verified_raw_trace` | `1` |

## Boundary

- RD5 只登记 retrieval index snapshot 与 source-artifact lineage，不把 retrieval hit 直接提权为 fact。
- Milvus 仍是 semantic recall supplement，不承担 exact-value authority。
- 旧云端绝对路径会重定位到当前 repo；若无法重定位则作为 missing source artifact 暴露。
