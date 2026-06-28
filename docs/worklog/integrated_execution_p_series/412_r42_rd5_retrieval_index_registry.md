# R42 RD5 Retrieval Index Registry

## Problem

RD0/RD1/RD2 已经能盘点 raw / parser / runtime rows，RD3/RD4 已把事实、信号和图边落入 Gold Mart / Graph Store。但 RAG 层仍然分散在 BM25、ObjectBM25、SQLite FTS、dense/faiss 和 Milvus 配置中；如果不建检索索引账本，Research Lead 和 eval 仍无法判断一个 retrieval hit 究竟来自哪个 corpus snapshot、是否有 parser lineage、是否只是 semantic supplement。

## Decision

实现 RD5 RAG Index Registry / Retrieval Parity：

- 把 `data/indexes/**/metadata.json` / `index_metadata.json` 和 accepted Milvus runtime config 统一登记为 `retrieval_index_snapshot`。
- 把 `evidence_path`、`structured_dir`、Milvus parquet export / rebuild summary 等登记为 `retrieval_index_source_lineage`。
- 用 RD2 `parser_output_artifact_ledger_v0_1.jsonl` 反查 parser artifact / parser run ids。
- 同步写 SQLite mirror，供后续 Research Lead、eval 和 Workbench 直接查表。
- 保持边界：retrieval index 只负责 recall，不承担 exact-value authority。

## Work Completed

- 新增 `src/sec_agent/retrieval_index_registry.py`。
- 新增 `scripts/data_expansion/build_retrieval_index_registry.py`。
- 新增 `tests/test_retrieval_index_registry.py`，覆盖旧云端路径重定位、missing source 暴露、records raw-trace 特殊状态、Milvus config lineage 和 SQLite parity。
- 物化：
  - `data/manifests/retrieval_index_snapshot_registry_v0_1.jsonl`
  - `data/manifests/retrieval_index_source_lineage_v0_1.jsonl`
  - `data/manifests/retrieval_index_registry_summary_v0_1.json`
  - `data/workbench_private/research_data/retrieval_index_registry_v0_1.sqlite`
  - `docs/internal/vnext_20260610/rd5_retrieval_index_registry.zh-CN.md`
- 更新 `docs/architecture/agent_graph_vnext/24_raw_disclosure_rag_database_recap_and_data_base_plan.zh-CN.md` 和 master checklist。

## Result And Evidence

真实构建结果：

| Metric | Value |
| --- | ---: |
| status | `pass` |
| index snapshots | `22` |
| source lineage rows | `23` |
| total declared records | `12,584,655` |
| missing source artifacts | `0` |
| missing record-file snapshots | `0` |
| SQLite snapshots / lineage | `22 / 23` |

Index family:

| Family | Snapshots |
| --- | ---: |
| `bm25_lexical` | `10` |
| `object_bm25_or_fts` | `7` |
| `sqlite_fts_object` | `2` |
| `dense_embedding` | `2` |
| `milvus_semantic` | `1` |

重要发现：

- 旧 8-K BM25 metadata 指向的 `/root/autodl-tmp/.../sec_tech_primary_mixed_with_8k_earnings_full30_evidence_fy2023_2027.jsonl` 本地不存在，但 `records.jsonl` 自带 SEC `source_url/local_path`，且 raw filing 可重定位到本地，因此登记为 `source_artifact_missing_but_record_snapshot_has_raw_trace`。这不是 fallback 提权，只是保留可回放 retrieval corpus trace。
- `parser_artifact_link_status=no_parser_artifact_match` 共 `3` 条：2 条 Milvus parquet / summary lineage 不属于 parser 输出；1 条为上述旧 8-K BM25 evidence-path 缺失但 record snapshot 可追 raw trace。
- `record_snapshot_without_verified_raw_trace=1` 是 staging Tier1 BM25；source evidence artifact 和 parser ledger 可用，但 staging raw html 未随本地 raw lake 完整保留，后续 RD7 应纳入 replay/cache gate。

Verification:

- `python -m py_compile src/sec_agent/retrieval_index_registry.py scripts/data_expansion/build_retrieval_index_registry.py`
- `python -m pytest tests/test_retrieval_index_registry.py -q` -> `5 passed`
- `python scripts/data_expansion/build_retrieval_index_registry.py` -> `status=pass`

## Follow-Up

- RD6：把 RD0-RD5 产物合并为 Research Lead / specialist 可消费的数据底座 brief 和 EvidencePack contract。
- RD7：把 staging raw replay、URL-only context snapshot、retrieval source lineage、record snapshot trace、parser artifact link status 纳入 release eval gate。
- 不允许用 RD5 registry 中的 retrieval hit 直接生成事实；必须回到 RD3/RD4 authority gate。
