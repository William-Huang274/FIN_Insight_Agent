# Model Run: 20260607_tier1_tier2_sec_full_source_object_hybrid_retrieval_ab_v0_3

## Summary

- Purpose: Validate the expanded Object SQLite FTS baseline against expanded BM25, reused Milvus typed semantic recall, and Hybrid RRF before wiring expanded retrieval into agent gates.
- Status: accepted retrieval-only staging diagnostic / not full-chain mainline.
- Run type: retrieval evaluation.
- Timestamp: 2026-06-07 Asia/Shanghai.
- Environment: cloud `/autodl-fs/data/fin_agent_milvus_bge_m3`, RTX GPU with BGE-M3 local model, reused Milvus Lite DB.

## Code And Command

- Entry point: `scripts/eval_retrieval/eval_milvus_retrieval_ab.py`
- Local code change: summary/report now exposes ObjectBM25 usable rows, metric rows, enabled case count, and exact object metric gate count.
- Remote script path: `/autodl-fs/data/fin_agent_milvus_bge_m3/scripts/eval_retrieval/eval_milvus_retrieval_ab.py`
- Command profile:
  - Evidence: `/autodl-fs/data/fin_agent_milvus_bge_m3/data/evidence/tier1_tier2_sec_full_source_mixed_evidence_fy2023_2027_v0_1.jsonl`
  - BM25: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/bm25/tier1_tier2_sec_full_source_mixed_fy2023_2027_v0_1`
  - Object SQLite FTS: `/autodl-fs/data/fin_agent_milvus_bge_m3/indexes/sqlite_fts/tier1_tier2_sec_full_source_mixed_objects_fy2023_2027_v0_1`
  - Reused Milvus DB: `/autodl-fs/data/fin_agent_milvus_bge_m3/milvus/20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2/milvus_lite.db`
  - Collection: `fin_ab_20260606_tier1_tier2_sec_full_source_milvus_bge_m3_cloud_full_evidence_batch128_v0_2_1780744242`
  - Object vectors disabled for this run; this run evaluates Object SQLite FTS as a lexical structured-object baseline and reuses the existing evidence-only typed semantic Milvus collection.
- Seeds: deterministic retrieval evaluation; no random training seed.

## Inputs

- Cases: `tests/fixtures/fin_agent_retrieval_ab_cases_v0_1.jsonl`
- Case count: `12`
- Categories: exact lookup, sector-depth, relationship, paraphrase.
- Expanded evidence rows in source artifact: `231842`
- Expanded Object SQLite FTS metadata: `7493637` records, including `266080` tables, `5564948` metrics, and `1662609` claims.
- Reused Milvus collection rows: `662908`

## Outputs

- Summary JSON: `/autodl-fs/data/fin_agent_milvus_bge_m3/outputs/milvus_retrieval_ab/20260607_tier1_tier2_sec_full_source_object_hybrid_ab_v0_3/milvus_retrieval_ab_summary.json`
- Summary Markdown: `/autodl-fs/data/fin_agent_milvus_bge_m3/outputs/milvus_retrieval_ab/20260607_tier1_tier2_sec_full_source_object_hybrid_ab_v0_3/milvus_retrieval_ab_summary.md`
- Precheck 1-case run: `20260607_tier1_tier2_object_ab_jpm_smoke_v0_2_summary_metrics`

## Results

- Gate: pass.
- Cases: `12/12`.
- By category:
  - exact lookup: `2/2`
  - sector-depth: `6/6`
  - relationship: `2/2`
  - paraphrase: `2/2`
- Mean usable evidence rows:
  - BM25: `19.5`
  - ObjectBM25 / SQLite FTS: `15.25`
  - ObjectBM25 metric rows: `9.8333`
  - Milvus semantic: `18.6667`
  - Hybrid RRF: `19.4167`
- ObjectBM25 enabled case count: `12`
- Exact object metric hit pass count: `2`
- 1-case JPM precheck:
  - gate: pass
  - Object usable: `20`
  - Object metric: `20`
  - exact object metric hit: `1/1`

## Interpretation

The expanded structured-object baseline is now available and auditable for retrieval-only diagnostics. Object SQLite FTS supplies metric/table support for exact cases and participates in Hybrid RRF without dropping the 12-case gate. This closes the first next-step item in the expanded-universe architecture document at the retrieval-only layer.

This does not promote expanded retrieval into the agent full chain. The next required step is source-inventory wiring for market/industry artifacts, then Evidence Operator and Fusion Selector changes, followed by A1-A5 layered gates.

## Runtime Efficiency

- 12-case wall time observed from command runtime: about `363` seconds.
- Per-case elapsed times ranged roughly from `7.3s` to `39.7s`.
- BGE-M3 model loaded once; Milvus DB was reused.
- Object SQLite FTS queries are feasible for this gate but should remain bounded by case filters and route budgets before full-chain use.

## Caveats And Next Step

- Combined exact-value ledger count `6789032` from the architecture draft was not verified as a cloud DuckDB in this handoff; use verified Tier1 and Tier2 ledger paths until a combined artifact is located or rebuilt.
- The earlier empty `object_hybrid_v0_1/v0_2` and `ai_sector_smoke` cloud directories are not valid evidence; use `20260607_tier1_tier2_sec_full_source_object_hybrid_ab_v0_3`.
- Next: write market/industry merged artifact paths into source inventory and keep them context-only before Evidence Operator/Fusion integration.

## Safety Notes

- No API key, SSH password, private token, or raw LLM response was saved.
- No LLM inference or full-chain run was executed.
- Cloud raw/index/vector/ledger artifacts remain generated/private staging assets.
