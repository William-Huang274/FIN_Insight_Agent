# Model Run: 20260520_sec_universe_plus10_cloud_source_index_build

## Summary

- Purpose: Expand the SEC source/index corpus from 10 companies to 20 companies
  after the full40 reviewed pipeline pass.
- Status: completed
- Run type: source ingestion + embedding/index build
- Timestamp: 2026-05-20 Asia/Shanghai
- Environment: cloud RTX 5090 32GB, `/root/autodl-tmp/FIN_Insight_Agent`

## Code And Command

- Entry points:
  - `scripts/download_sec_filings.py`
  - `scripts/build_sec_manifest.py`
  - `scripts/build_sec_chunks.py`
  - `scripts/build_evidence_store.py`
  - `scripts/build_structured_objects.py`
  - `scripts/validate_structured_objects.py`
  - `scripts/build_bm25_index.py`
  - `scripts/build_object_bm25_index.py`
  - `scripts/build_dense_index.py`
- Config: `configs/sec_tech_universe.yaml`
- Added tickers:
  `AVGO`, `CSCO`, `INTC`, `QCOM`, `TXN`, `AMAT`, `MU`, `INTU`, `ADP`, `CRWD`
- Parser change: `src/ingestion/section_splitter.py` adds a bounded
  non-traditional 10-K fallback for readable layouts such as Intel's annual
  report.

## Inputs

- Years: 2023, 2024, 2025
- Companies: 20 tickers x 3 fiscal years
- SEC cache root: `data/raw_private/sec`
- Embedding model:
  `/root/autodl-tmp/FIN_Insight_Agent/data/models_private/modelscope/Qwen/Qwen3-Embedding-0___6B`
- Dense settings: batch size 16, CUDA, max sequence length 4096, query prompt
  metadata `query`

## Outputs

- Summary: `reports/quality/sec_universe_plus10_cloud_build_summary.json`
- Manifest: `data/processed_private/manifests/sec_tech_10k_manifest.jsonl`
- Chunks: `data/processed_private/chunks/sec_tech_10k_chunks.jsonl`
- Evidence: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`
- Structured objects:
  `data/processed_private/structured_objects/sec_tech_10k_{tables,metrics,claims}.jsonl`
- BM25 index: `data/indexes/bm25/sec_tech_10k`
- Object BM25 index: `data/indexes/bm25/sec_tech_10k_objects`
- Dense/FAISS index:
  `data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq4096_bs16_plus10_20co`

## Results

- Manifest rows: 60
- Ticker count: 20
- Chunks/evidence rows: 5,472
- Structured tables: 5,658
- Structured metrics: 95,372
- Structured claims: 46,905
- Object BM25 records: 147,935
- Dense records: 5,472
- Embedding dimension: 1024
- FAISS index: `IndexFlatIP`
- FAISS `ntotal`: 5,472
- Structured anchor validation: passed

## Experiment Governance

- Hypothesis: expanding from 10 to 20 SEC companies will reveal source,
  parsing, retrieval, and structured-object coverage risks before adding new
  reviewed benchmark cases.
- Decision target: 60 manifest rows, nonzero evidence/structured coverage for
  added companies, rebuilt BM25/ObjectBM25/dense/FAISS indexes, and no SEC
  filing download failures.
- Ceiling: this is an upstream source/index build only. It does not establish
  reviewed gold facts, Qwen answer quality, or broad-company benchmark claims.
- Baselines: prior 10-company SEC corpus and full40 reviewed BGE-M3 + Qwen9B
  diagnostic pass.
- Split and leakage guard: no benchmark answer thresholds were tuned from this
  run.
- Stop conditions: failed manifest coverage, failed existing anchor checks,
  missing filing downloads, or disk pressure blocking the Qwen3.6-27B-FP8
  download.
- Decision label: `proceed_to_cloud_source_index_build`
- Mainline decision: source/index build passed; next step is case design and
  reviewed gold creation for the expanded company universe.

## Runtime Efficiency

- Full rerun wall time: about 4 minutes 49 seconds.
- Dense Qwen embedding stage: about 2 minutes 32 seconds for 5,472 evidence
  objects.
- GPU: RTX 5090 used for dense embedding, observed at 100% utilization during
  the encoding stage.
- Bottleneck diagnosis: dense encoding is GPU-bound while structured extraction
  and BM25 builds are CPU/local I/O bound.
- Serving relevance: the FAISS file now supports faster dense candidate lookup
  for the expanded 20-company corpus; retrieval code still needs to explicitly
  load `faiss.index` if online serving should use FAISS instead of NumPy.

## Caveats And Next Step

- No Qwen answer inference was run in this source/index build.
- No reviewed gold artifacts were created for the 10 added companies.
- `Qwen/Qwen3.6-27B-FP8` download was started and remained in progress after
  this build; it is a separate deployment feasibility step.
- Next decision: design new company-diverse SEC benchmark cases and review gold
  context/facts before running BGE-M3 + Judgment Plan + Qwen on the expanded
  universe.
