# SEC Universe Plus10 Cloud Build

## Prompt

After the full40 reviewed pipeline pass, expand the SEC universe beyond the
current 10 companies. First check ModelScope for Qwen3.6-27B deployability,
delete the old Qwen3.5-27B model if the replacement is available, start the new
model download, then build the expanded SEC filings, evidence, embeddings, and
FAISS indexes on the cloud RTX 5090 machine.

## Governance Gate

- Hypothesis: adding 10 more SEC companies will expose retrieval and structured
  extraction generalization issues that are hidden by the current 10-company
  full40 route.
- Decision target: cloud build completes with 60 SEC 10-K manifest rows
  covering 20 companies x 3 fiscal years, evidence/structured-object counts are
  nonzero for every added ticker, BM25/ObjectBM25/dense FAISS indexes are rebuilt
  against the expanded corpus, and no SEC filing download failures occur.
- Ceiling: this step builds source/index coverage only. It does not create
  reviewed gold facts for the new companies and does not support scored Qwen
  benchmark claims until new case artifacts are designed and reviewed.
- Baselines: current 10-company corpus with 30 filings, full40 reviewed
  BGE-M3 + Qwen9B diagnostic pass, and existing BM25/ObjectBM25/dense indexes.
- Split and leakage guard: no model answer quality threshold will be tuned from
  this build. New company filings enter retrieval/index artifacts only; reviewed
  benchmark cases remain a separate future step.
- Stop conditions: stop before promoting the expanded corpus if any ticker-year
  filing is missing, if manifest count is below 60, if structured-object
  validation fails for existing anchor checks, or if disk pressure threatens the
  Qwen3.6-27B-FP8 download.
- Efficiency gate: download and parsing may run in the background on cloud; dense
  index build should use CUDA if available and produce a reproducible metadata
  summary.
- Decision label: `proceed_to_cloud_source_index_build`.

## Planned Company Expansion

The first plus10 expansion uses the recorded 22-company candidate universe and
adds the first 10 tickers not already in `configs/sec_tech_universe.yaml`:

- `AVGO`
- `CSCO`
- `INTC`
- `QCOM`
- `TXN`
- `AMAT`
- `MU`
- `INTU`
- `ADP`
- `CRWD`

Deferred from the 22-company candidate list for a later expansion: `MDB` and
`TEAM`.

## Initial Model Decision

- ModelScope API confirms `Qwen/Qwen3.6-27B` and `Qwen/Qwen3.6-27B-FP8` exist.
- The `Instruct`, `GPTQ-Int4`, and `Instruct-FP8` names checked in this turn do
  not exist on ModelScope.
- The active replacement download is `Qwen/Qwen3.6-27B-FP8`, because it is the
  best match for a first RTX 5090 32GB deployability test.
- Old model removed on cloud after path whitelist validation:
  `/root/autodl-tmp/FIN_Insight_Agent/data/models_private/modelscope/Qwen/Qwen3___5-27B-GPTQ-Int4`.
- New download log:
  `/root/autodl-tmp/FIN_Insight_Agent/.tmp_remote_jobs/qwen36_27b_fp8_modelscope_download.log`.

## Cloud Build Result

Status: source/index build completed on the cloud RTX 5090 machine.

Generated summary:
`reports/quality/sec_universe_plus10_cloud_build_summary.json`

Remote generated artifacts:

- Manifest: `data/processed_private/manifests/sec_tech_10k_manifest.jsonl`
- Chunks: `data/processed_private/chunks/sec_tech_10k_chunks.jsonl`
- Evidence: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`
- Structured objects: `data/processed_private/structured_objects/sec_tech_10k_{tables,metrics,claims}.jsonl`
- BM25 index: `data/indexes/bm25/sec_tech_10k`
- Object BM25 index: `data/indexes/bm25/sec_tech_10k_objects`
- Dense/FAISS index:
  `data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq4096_bs16_plus10_20co`

Counts:

- Manifest rows: 60, covering 20 tickers x 3 fiscal years.
- Chunks/evidence rows: 5,472.
- Structured tables: 5,658.
- Structured metrics: 95,372.
- Structured claims: 46,905.
- Object BM25 records: 147,935.
- Dense embedding records: 5,472, dimension 1024.
- FAISS index: `IndexFlatIP`, `ntotal=5472`, using inner product on normalized
  embeddings.

Validation:

- Existing structured anchor validation passed after the full 20-company rebuild.
- AAPL Services gross margin amount and percentage anchors passed.
- SNOW RPO / consumption anchors passed.
- NVDA supply-risk anchor passed.

Implementation note:

- Intel's 10-K uses a readable non-traditional layout where formal `Item`
  labels only appear in the cross-reference index. The first rebuild produced
  zero INTC chunks, so `src/ingestion/section_splitter.py` now has a bounded
  fallback that only activates when traditional Item splitting yields no
  sections. Remote smoke confirmed INTC now produces chunks for 2023, 2024, and
  2025, including Item 7A in the 2025 ordering.

Runtime:

- Full rerun started at 2026-05-20 18:13:30 CST and completed at 18:18:19 CST.
- Dense Qwen embedding stage ran from 18:15:47 to 18:18:19 CST on RTX 5090.
- Qwen3.6-27B-FP8 download was still running after the source/index build, with
  the target directory at about 19G and `/root/autodl-tmp` at about 57G free.

## Safety Notes

- No SSH password, token, or temporary credential is recorded here.
- Qwen3.6-27B-FP8 download is a deployment feasibility step only; it is not yet
  a benchmark inference result.
- Expanded SEC build should run on cloud and write generated artifacts under
  ignored `data/` and `reports/` paths.
