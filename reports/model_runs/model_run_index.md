# Model Run Index

| Run ID | Date | Type | Status | Summary |
| --- | --- | --- | --- | --- |
| `20260515_phase1_bm25_dense_smoke` | 2026-05-15 | retrieval smoke | completed | Built EvidenceObject store, BM25 index, and MiniLM dense index for 2,842 SEC 10-K evidence records. |
| `20260515_phase1_seed_retrieval_eval` | 2026-05-15 | retrieval evaluation | completed | Evaluated BM25, dense MiniLM, and hybrid RRF on 30 seed evidence queries with and without ticker/year filters. |
| `20260515_phase1_qwen3_embedding_eval` | 2026-05-15 | retrieval evaluation | completed | Downloaded Qwen3-Embedding-0.6B from ModelScope, built a 1024-dim dense index, and evaluated it on the seed query set. |
| `20260515_phase1_qwen3_seq8192_batch_probe` | 2026-05-15 | embedding index probe | completed | Tested Qwen seq8192 with batch 16/32, added precision/nDCG eval reports, and kept the run diagnostic-only because current evidence does not exceed 4096 tokens. |
