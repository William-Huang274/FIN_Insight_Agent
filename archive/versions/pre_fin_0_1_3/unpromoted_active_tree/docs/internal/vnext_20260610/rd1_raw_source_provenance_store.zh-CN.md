# RD1 Bronze Raw Source Provenance Store

- Generated at: `2026-06-26T18:04:09Z`
- Status: `pass`
- Raw source documents: `27720`
- Fetch attempts: `34580`
- Source snapshots: `27720`
- Runtime row lineage rows: `71004`
- Exact-authority unresolved lineage: `0`
- URL-only context lineage: `35587`

## Outputs

- `raw_source_documents`: `D:\FIN_Insight_Agent\data\manifests\raw_source_documents_v0_1.jsonl`
- `raw_fetch_attempts`: `D:\FIN_Insight_Agent\data\manifests\raw_fetch_attempts_v0_1.jsonl`
- `source_snapshots`: `D:\FIN_Insight_Agent\data\manifests\source_snapshots_v0_1.jsonl`
- `runtime_row_source_lineage`: `D:\FIN_Insight_Agent\data\manifests\runtime_row_source_lineage_v0_1.jsonl`
- `summary`: `D:\FIN_Insight_Agent\data\manifests\raw_source_provenance_summary_v0_1.json`
- `report`: `D:\FIN_Insight_Agent\docs\internal\vnext_20260610\rd1_raw_source_provenance_store.zh-CN.md`

## Runtime Lineage Status

| Status | Rows |
| --- | ---: |
| `matched_derived_structured_source_document` | `386` |
| `matched_raw_document` | `34929` |
| `runtime_declared_source_document` | `35689` |

## Snapshot Storage

| Storage status | Rows |
| --- | ---: |
| `api_response_cached` | `4384` |
| `local_raw_snapshot_available` | `3322` |
| `missing_snapshot` | `48` |
| `url_only_no_local_snapshot` | `19966` |

## Fetch Attempt Status

| Status class | Rows |
| --- | ---: |
| `credential_or_access` | `307` |
| `locator_miss` | `1581` |
| `parser_miss` | `653` |
| `public_boundary` | `756` |
| `source_unavailable` | `127` |
| `success` | `27800` |
| `unknown_status` | `3356` |

## Boundary

- RD1 只建立 provenance，不新增事实提权。
- `local_raw_snapshot_available` / `api_response_cached` 行可回放；`url_only_no_local_snapshot` 行只能说明 runtime row 声明了来源 URL，后续需要缓存快照或在 run audit 中绑定 fetch attempt。
- exact-authority 行如果出现 unresolved，RD2/RD3 不允许把它们升级为主事实层。
