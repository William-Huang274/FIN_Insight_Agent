# Model Run: 20260515_phase1_qwen3_seq8192_batch_probe

## Summary
- Purpose: Test whether Qwen3-Embedding-0.6B benefits from a larger document max
  sequence length and larger batch size on the RTX 4090 cloud host.
- Status: completed.
- Run type: embedding index build / retrieval evaluation.
- Timestamp: 2026-05-15.
- Environment: cloud Linux workspace with one NVIDIA GeForce RTX 4090.

## Code And Command
- Branch: `feature/phase1-sec-foundation`.
- Entry points:
  - `scripts/build_dense_index.py`.
  - `scripts/evaluate_retrieval.py`.
- Model artifact:
  `data/models_private/modelscope/Qwen/Qwen3-Embedding-0___6B`.
- Build commands:
  - `python scripts/build_dense_index.py --model data/models_private/modelscope/Qwen/Qwen3-Embedding-0___6B --output-dir data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs32 --device cuda --batch-size 32 --query-prompt-name query --max-seq-length 8192`
  - `python scripts/build_dense_index.py --model data/models_private/modelscope/Qwen/Qwen3-Embedding-0___6B --output-dir data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16 --device cuda --batch-size 16 --query-prompt-name query --max-seq-length 8192`
- Eval commands:
  - `python scripts/evaluate_retrieval.py --retrievers dense,hybrid --dense-index-dir data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16 --device cuda --output reports/retrieval_eval/sec_tech_10k_seed_eval_qwen3_0_6b_seq8192_filtered.json`
  - `python scripts/evaluate_retrieval.py --retrievers dense,hybrid --filter-mode none --dense-index-dir data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16 --device cuda --output reports/retrieval_eval/sec_tech_10k_seed_eval_qwen3_0_6b_seq8192_unfiltered.json`
- Seeds: not applicable.

## Inputs
- Evidence store:
  `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`.
- Evidence count: 2,842.
- Gold set: `eval_sets/sec_tech_10k_seed.jsonl`.
- Query count: 30.
- Label protocol: agent-curated seed labels from current EvidenceObjects; not
  exhaustive human-reviewed relevance judgments.

## Model Parameters
- Model: Qwen3-Embedding-0.6B.
- Embedding dimension: 1024.
- Document max sequence length: 8192.
- Query prompt: `query`.
- Normalization: enabled.
- Batch sizes tested: 16 and 32.

## Outputs
- Batch 16 dense index:
  `data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16/`.
- Batch 32 dense index:
  `data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs32/`.
- Runtime JSON:
  - `reports/model_runs/qwen3_embedding_seq8192_bs16_runtime.json`.
  - `reports/model_runs/qwen3_embedding_seq8192_bs32_runtime.json`.
- Eval JSON:
  - `reports/retrieval_eval/sec_tech_10k_seed_eval_qwen3_0_6b_seq8192_filtered.json`.
  - `reports/retrieval_eval/sec_tech_10k_seed_eval_qwen3_0_6b_seq8192_unfiltered.json`.

## Results
- Qwen token length over current evidence text:
  - Count: 2,842.
  - Minimum: 85.
  - Median: 791.
  - Mean: 856.1.
  - Maximum: 3,536.
  - P90/P95/P99: 1,532 / 1,742 / 2,335.
  - Over 4,096 tokens: 0.
  - Over 8,192 tokens: 0.
- Runtime:
  - seq8192 batch 16: 96.76 seconds, 8.984 GB peak CUDA allocated,
    11.150 GB peak CUDA reserved, 25.123 MB index.
  - seq8192 batch 32: 105.67 seconds, 16.700 GB peak CUDA allocated,
    18.557 GB peak CUDA reserved, 25.123 MB index.
- Filtered dense Qwen seq8192 batch 16:
  - MRR 0.716, Hit@10 0.933, Mean Recall@10 0.917,
    Mean Precision@10 0.117, Mean nDCG@10 0.747.
- Unfiltered dense Qwen seq8192 batch 16:
  - MRR 0.652, Hit@10 0.900, Mean Recall@10 0.867,
    Mean Precision@10 0.110, Mean nDCG@10 0.689.

## Experiment Governance
- Hypothesis: larger max sequence length and larger batch may improve recall or
  throughput if current chunks are being truncated or GPU is underused.
- Decision target: improve dense Qwen retrieval quality or index build time on
  the 30-query seed set without exceeding 4090 memory.
- Ceiling / upper bound: current evidence text has no records over 4,096 Qwen
  tokens, so seq8192 cannot improve quality through truncation recovery.
- Baselines to beat: seq4096 batch 8 Qwen dense index, which built in about
  86.5 seconds and reached Hit@10 0.933 filtered / 0.900 unfiltered.
- Split and leakage guard: no training or tuning; seed queries only evaluate
  retrieval over public filings.
- Stop conditions: do not continue increasing batch size if wall time worsens
  or memory rises without metric gain.
- Efficiency gate: stay under 24 GB VRAM and keep full index build within a few
  minutes.
- Decision label: diagnostic-only.
- Mainline decision: keep Qwen dense as the main dense baseline; use seq4096 or
  batch 8/16 for current corpus until larger chunks require a longer context.

## Runtime Efficiency
- Wall time: 96.76 seconds for batch 16, 105.67 seconds for batch 32.
- GPU memory: batch 32 used about 2x the allocated memory of batch 16 and was
  slower.
- Bottleneck diagnosis: larger max length plus variable-length padding likely
  increased wasted compute; current corpus does not need seq8192.
- Serving relevance: query-time model load and embedding remain the bigger
  serving issue than index build throughput. A long-lived retrieval runner is
  still needed before interactive demos.

## Caveats And Next Step
- Not run: no weighted RRF, reranker, or expanded human-reviewed qrels.
- Known risk: seed labels are narrow and not exhaustive.
- Next decision: test dense-first retrieval with BM25 fallback or weighted RRF
  after adding a reviewed label slice.
