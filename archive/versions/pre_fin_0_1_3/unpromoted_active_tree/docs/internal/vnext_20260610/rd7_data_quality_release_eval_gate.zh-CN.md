# RD7 Data Quality / Release Eval Gate

- Generated at: `2026-06-26T18:10:37Z`
- Status: `pass_with_warnings`
- Release decision: `release_allowed_with_recorded_warnings`
- Gate rows: `47`
- Pass / Warn / Fail: `42` / `5` / `0`

## Outputs

- `gate_rows`: `D:\FIN_Insight_Agent\data\manifests\data_quality_release_eval_gate_rows_v0_1.jsonl`
- `sqlite`: `D:\FIN_Insight_Agent\data\workbench_private\research_data\data_quality_release_eval_gate_v0_1.sqlite`
- `summary`: `D:\FIN_Insight_Agent\data\manifests\data_quality_release_eval_gate_summary_v0_1.json`
- `report`: `D:\FIN_Insight_Agent\docs\internal\vnext_20260610\rd7_data_quality_release_eval_gate.zh-CN.md`

## Gate Status By Group

| Group | Pass | Warn | Fail |
| --- | ---: | ---: | ---: |
| `cross_authority_consumption` | 1 | 0 | 0 |
| `rd1_raw_source_provenance` | 6 | 1 | 0 |
| `rd2_parser_quality` | 6 | 1 | 0 |
| `rd3_gold_fact_signal_mart` | 6 | 0 | 0 |
| `rd4_research_graph_store` | 8 | 1 | 0 |
| `rd5_retrieval_index_registry` | 7 | 2 | 0 |
| `rd6_agent_runtime_consumption` | 8 | 0 | 0 |

## Warnings

| Gate | Status | Observed | Threshold | Message |
| --- | --- | ---: | --- | --- |
| `rd1_raw_source_provenance.url_only_context_lineage_count` | `warn` | `35587` | `0 preferred` | URL-only rows are traceable but not locally replayable until cached. |
| `rd2_parser_quality.parser_status_counts.unknown` | `warn` | `10` | `0 preferred` | Parser run status has unknown rows; keep as parser-ledger quality debt. |
| `rd4_research_graph_store.support_status_counts.modelled_relationship_without_direct_evidence_ref` | `warn` | `65` | `0 preferred` | Modelled relationship edges exist without direct evidence ref; keep bounded and auditable. |
| `rd5_retrieval_index_registry.record_snapshot_trace_status_counts.record_snapshot_without_verified_raw_trace` | `warn` | `1` | `0 preferred` | Index records contain a source artifact but not a verified local raw trace. |
| `rd5_retrieval_index_registry.parser_artifact_link_status_counts.no_parser_artifact_match` | `warn` | `3` | `0 preferred` | Some index lineage rows do not map to a parser artifact; allowed for Milvus summary/legacy raw-trace rows only. |

## Failures

_None._

## Boundary

- RD7 不新增事实、不放松 authority gate，只判断 RD1-RD6 数据底座是否可作为 agent runtime 输入。
- `warn` 项允许进入下一阶段，但必须作为 replay/cache/parser-depth debt 暴露给 Research Lead / eval registry。
- `fail` 项阻断 release：尤其是 exact-authority unresolved、缺 artifact、SQLite parity、unsupported graph edge、planning/gap row 被选入 evidence。
