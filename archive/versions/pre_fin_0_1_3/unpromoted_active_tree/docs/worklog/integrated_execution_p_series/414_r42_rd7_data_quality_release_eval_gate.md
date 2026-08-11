# R42 RD7 Data Quality / Release Eval Gate

## Problem

RD0-RD6 已经把 raw provenance、parser ledger、Gold Mart、Graph Store、Retrieval Index Registry 和 Agent Runtime Consumption Contract 落成主账本，但下一步进入 full-chain / agent graph 调度前，需要一个统一的 release eval gate 来判断数据底座是否有硬阻断。

本轮开始前还发现 RD1 产物存在一次半更新问题：`raw_source_documents_v0_1.jsonl` 已包含 SEC CompanyFacts 文档，但 `runtime_row_source_lineage_v0_1.jsonl` / summary 仍保留 `386` 条 `sec_financial_statement_data_sets` exact-authority unresolved。原因不是公开源缺失，而是上次全量重建在写完 source documents 后超时，且 source document external keys 没有持久写入 `sec_companyfacts_by_ticker:<ticker>`。

## Decision

先修 RD1 provenance，再落 RD7 gate。不能用 RD7 忽略或兜底 stale lineage。

RD7 gate 分 hard / soft：

- hard fail：exact-authority unresolved、unresolved lineage、missing artifact、SQLite parity mismatch、unsupported/dangling graph edge、planning/gap row 被选入 evidence。
- soft warn：URL-only snapshot、parser unknown status、模型化关系边、staging raw replay、Milvus/legacy index lineage 未直接映射 parser artifact。

## Work Completed

- 更新 `src/sec_agent/raw_source_provenance_store.py`：把 `sec_companyfacts_by_ticker:<ticker>` 写入 SEC CompanyFacts source document external keys。
- 新增 `scripts/data_expansion/repair_raw_source_provenance_lineage_from_existing_documents.py`：复用已存在 source documents 快速重建 lineage/snapshot/summary，避免为半更新问题重复全量 raw lake 扫描。
- 更新 `tests/test_raw_source_provenance_store.py`，断言 SEC CompanyFacts 文档自身带派生 external key。
- 新增 `src/sec_agent/data_quality_release_eval_gate.py`。
- 新增 `scripts/data_expansion/build_data_quality_release_eval_gate.py`。
- 新增 `tests/test_data_quality_release_eval_gate.py`，覆盖 pass-with-warnings、hard fail 和 SQLite mirror。
- 物化：
  - `data/manifests/data_quality_release_eval_gate_rows_v0_1.jsonl`
  - `data/manifests/data_quality_release_eval_gate_summary_v0_1.json`
  - `data/workbench_private/research_data/data_quality_release_eval_gate_v0_1.sqlite`
  - `docs/internal/vnext_20260610/rd7_data_quality_release_eval_gate.zh-CN.md`
- 更新 24 文档和 master checklist。

## Result And Evidence

RD1 定向修复后：

| Metric | Value |
| --- | ---: |
| status | `pass` |
| runtime lineage rows | `71,004` |
| exact-authority unresolved | `0` |
| unresolved lineage | `0` |
| companyfacts external-key documents | `588` |
| matched derived structured source documents | `386` |
| URL-only context lineage | `35,587` |

RD7 真实构建：

| Metric | Value |
| --- | ---: |
| status | `pass_with_warnings` |
| release decision | `release_allowed_with_recorded_warnings` |
| gate rows | `47` |
| pass / warn / fail | `42 / 5 / 0` |
| SQLite gate rows | `47` |

5 个 warning：

- RD1 `url_only_context_lineage_count=35,587`：URL 可追，但未全部本地 replay/cache。
- RD2 `parser_status_counts.unknown=10`：部分历史 parser summary 缺明确 pass/fail。
- RD4 `modelled_relationship_without_direct_evidence_ref=65`：模型化关系边保留 bounded/planning，不进入 evidence bundle。
- RD5 `record_snapshot_without_verified_raw_trace=1`：staging Tier1 BM25 records 缺本地 raw html replay。
- RD5 `no_parser_artifact_match=3`：Milvus summary/parquet 和 legacy 8-K raw-trace lineage 不直接映射 parser artifact。

Verification:

- `python -m py_compile src/sec_agent/raw_source_provenance_store.py scripts/data_expansion/repair_raw_source_provenance_lineage_from_existing_documents.py`
- `python -m pytest tests/test_raw_source_provenance_store.py -q` -> `4 passed`
- `python scripts/data_expansion/repair_raw_source_provenance_lineage_from_existing_documents.py` -> `status=pass`
- `python -m py_compile src/sec_agent/data_quality_release_eval_gate.py scripts/data_expansion/build_data_quality_release_eval_gate.py`
- `python -m pytest tests/test_data_quality_release_eval_gate.py -q` -> `3 passed`
- `python scripts/data_expansion/build_data_quality_release_eval_gate.py` -> `status=pass_with_warnings`

## Boundary And Follow-Up

- RD7 允许进入下一阶段，但不是全绿。Warnings 必须进入后续 full-chain / eval registry，而不是被 Memo Writer 或下游 prompt 隐藏。
- URL-only rows 不得因为有 provenance ledger 而升级为 exact evidence；重要 source 后续应继续做 fetch/cache/replay。
- 模型化关系边必须保持 bounded/planning，除非后续补到 direct evidence ref。
- 下一步应在 RD0-RD7 主账本上推进 ProductIntelligenceGraph / Capital graph / Research Lead planning / full-chain release case，而不是回到散装 JSONL 检索。
