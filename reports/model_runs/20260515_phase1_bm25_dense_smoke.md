# Model Run: 20260515_phase1_bm25_dense_smoke

## Summary
- Purpose: 验证 SEC chunks -> EvidenceObject -> BM25/dense retrieval 的端到端可行性。
- Status: completed.
- Run type: inference / indexing / smoke.
- Timestamp: 2026-05-15.
- Environment: local Windows workspace plus cloud Linux workspace with one NVIDIA GeForce RTX 4090.

## Code And Command
- Branch: `feature/phase1-sec-foundation`.
- Code version: working tree before committing the retrieval smoke changes.
- Local commands:
  - `python -m compileall src scripts`
  - `python scripts/build_evidence_store.py`
  - `python scripts/build_bm25_index.py`
  - `python scripts/search_bm25.py "What drove Microsoft cloud revenue growth in 2024?" --ticker MSFT --year 2024 --top-k 5`
  - `python scripts/search_bm25.py "What are NVIDIA supply constraints and customer concentration risks?" --ticker NVDA --year 2025 --top-k 5`
- Cloud commands:
  - `python -m compileall src scripts`
  - `python scripts/build_evidence_store.py`
  - `python scripts/build_bm25_index.py`
  - `HF_ENDPOINT=https://hf-mirror.com python scripts/build_dense_index.py --device cuda --batch-size 128`
  - `HF_ENDPOINT=https://hf-mirror.com python scripts/search_dense.py "...Microsoft cloud revenue growth..." --ticker MSFT --year 2024 --top-k 3 --device cuda`
  - `HF_ENDPOINT=https://hf-mirror.com python scripts/search_dense.py "...NVIDIA supply constraints..." --ticker NVDA --year 2025 --top-k 3 --device cuda`
- Seeds: not applicable; no stochastic training.

## Inputs
- Chunk input: `data/processed_private/chunks/sec_tech_10k_chunks.jsonl`.
- Evidence input/output: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`.
- Data profile: 30 SEC 10-K filings from 10 Nasdaq technology companies across fiscal years 2023, 2024, and 2025.
- Candidate boundary: target sections Item 1, Item 1A, Item 7, Item 7A, and Item 8.
- Row count: 2,842 EvidenceObjects.
- Leakage guard: retrieval smoke uses public filings only and no labeled evaluation split.

## Model Parameters
- BM25: `rank_bm25.BM25Okapi` over EvidenceObject search text.
- Dense model: `sentence-transformers/all-MiniLM-L6-v2`.
- Dense batch size: 128.
- Dense device: `cuda`.
- Embedding dim: 384.
- Dense normalization: enabled; retrieval uses dot product as cosine similarity.

## Outputs
- BM25 index: `data/indexes/bm25/sec_tech_10k/`.
- Dense index: `data/indexes/dense/sec_tech_10k/`.
- Dense files: `embeddings.npy`, `records.jsonl`, `metadata.json`.
- Dense index size on cloud: about 18.2 MB.

## Results
- EvidenceObject build:
  - Input chunks: 2,842.
  - Output EvidenceObjects: 2,842.
  - Table-bearing evidence: 982.
- Evidence type counts:
  - `business_description`: 423.
  - `risk_disclosure`: 989.
  - `management_discussion`: 524.
  - `market_risk_disclosure`: 47.
  - `financial_statement_or_note`: 859.
- BM25 MSFT query top hit:
  - `MSFT_2024_10K_ITEM7_BLOCK_0003_CHUNK_0001`, MD&A highlights.
  - Preview includes Microsoft Cloud revenue increased 23% to $137.4 billion.
- BM25 NVDA query top hits:
  - `NVDA_2025_10K_ITEM7_BLOCK_0007_CHUNK_0001`, concentration of revenue.
  - `NVDA_2025_10K_ITEM1A_BLOCK_0004_PART_01_OF_03`, risks related to demand, supply, and manufacturing.
- Dense MSFT query top hit:
  - `MSFT_2024_10K_ITEM7_BLOCK_0003_CHUNK_0001`, score about 0.717.
- Dense NVDA query top hits:
  - `NVDA_2025_10K_ITEM7_BLOCK_0007_CHUNK_0001`, score about 0.616.
  - `NVDA_2025_10K_ITEM1A_BLOCK_0004_PART_03_OF_03`, score about 0.597.

## Experiment Governance
- Hypothesis: EvidenceObject schema plus section/table-aware chunking is sufficient for first sparse/dense retrieval smoke tests.
- Decision target: top hits for two hand-written diagnostic queries should land in the expected ticker/year and business section.
- Ceiling / upper bound: no gold query set yet, so quality claims are diagnostic-only.
- Baselines to beat: no previous accepted retrieval baseline; BM25 and dense are first baselines.
- Split and leakage guard: no training, no labeled test set, no benchmark metric.
- Stop conditions: stop if evidence build breaks schema, if table markers are lost, or if dense model cannot be loaded on cloud.
- Efficiency gate: dense index must build within a few minutes for the 2,842-record smoke set.
- Decision label: proceed for infrastructure; diagnostic-only for retrieval quality.
- Mainline decision: keep BM25 and dense as Phase 1 baselines, then add gold queries and hybrid RRF evaluation.

## Runtime Efficiency
- Dense build wall time on cloud: about 51.5 seconds after using `HF_ENDPOINT=https://hf-mirror.com`.
- Dense batch count: 23 batches for 2,842 records at batch size 128.
- GPU: NVIDIA GeForce RTX 4090.
- Observed bottleneck: first model download; direct `huggingface.co` timed out from the cloud host.
- Query inefficiency: CLI search scripts reload the dense model for every query, taking about 20-26 seconds per query in the smoke run.
- Next optimization: add an in-process retrieval runner/API that loads the dense model once for a query set.

## Safety Notes
- No credentials or private connection details were written to the repository.
- Generated SEC data and indexes remain under ignored data directories.
- The result should not be presented as final retrieval quality until a gold evidence query set and evaluation script exist.
