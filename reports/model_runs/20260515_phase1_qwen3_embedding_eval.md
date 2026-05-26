# Model Run: 20260515_phase1_qwen3_embedding_eval

## Summary
- Purpose: 从 ModelScope 下载 Qwen 系 embedding 模型，比较它相对 MiniLM 的 SEC 10-K seed retrieval 效果。
- Status: completed.
- Run type: embedding index build / retrieval evaluation.
- Timestamp: 2026-05-15.
- Environment: cloud Linux workspace with one NVIDIA GeForce RTX 4090.

## Code And Command
- Branch: `feature/phase1-sec-foundation`.
- Download:
  - `python scripts/download_modelscope_model.py --model-id Qwen/Qwen3-Embedding-0.6B --cache-dir data/models_private/modelscope`
- Build:
  - `python scripts/build_dense_index.py --model data/models_private/modelscope/Qwen/Qwen3-Embedding-0___6B --output-dir data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b --device cuda --batch-size 8 --query-prompt-name query --max-seq-length 4096`
- Eval:
  - `python scripts/evaluate_retrieval.py --retrievers dense,hybrid --dense-index-dir data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b --device cuda --output reports/retrieval_eval/sec_tech_10k_seed_eval_qwen3_0_6b_filtered.json`
  - `python scripts/evaluate_retrieval.py --retrievers dense,hybrid --filter-mode none --dense-index-dir data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b --device cuda --output reports/retrieval_eval/sec_tech_10k_seed_eval_qwen3_0_6b_unfiltered.json`

## Inputs
- Model source: ModelScope `Qwen/Qwen3-Embedding-0.6B`.
- Model cache: `data/models_private/modelscope/Qwen/Qwen3-Embedding-0___6B`.
- Evidence store: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`.
- Evidence count: 2,842.
- Gold set: `eval_sets/sec_tech_10k_seed.jsonl`.
- Query count: 30.

## Model Parameters
- Model: Qwen3-Embedding-0.6B.
- Embedding dimension: 1024.
- Batch size: 8.
- Device: CUDA.
- Document max sequence length: 4096.
- Query prompt: `query`.
- Normalization: enabled.

## Outputs
- Dense index: `data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b/`.
- Dense index size: about 26 MB.
- Filtered report: `reports/retrieval_eval/sec_tech_10k_seed_eval_qwen3_0_6b_filtered.json`.
- Unfiltered report: `reports/retrieval_eval/sec_tech_10k_seed_eval_qwen3_0_6b_unfiltered.json`.

## Results
- Index build:
  - Model download size on disk: about 1.2 GB.
  - Index build elapsed: about 86.5 seconds.
  - Records: 2,842.
  - Embedding dim: 1024.
- Ticker/year filtered mode:
  - Dense Qwen: MRR 0.709, Hit@5 0.867, Hit@10 0.933, Mean Recall@10 0.917.
  - Hybrid RRF + Qwen: MRR 0.640, Hit@5 0.867, Hit@10 0.967, Mean Recall@10 0.950.
- Unfiltered full-corpus mode:
  - Dense Qwen: MRR 0.634, Hit@5 0.833, Hit@10 0.900, Mean Recall@10 0.867.
  - Hybrid RRF + Qwen: MRR 0.519, Hit@5 0.767, Hit@10 0.867, Mean Recall@10 0.833.

## Seq8192 And Batch Probe
- Token-length analysis over `evidence_search_text` for 2,842 records:
  - Minimum: 85.
  - Median: 791.
  - Mean: 856.1.
  - Maximum: 3,536.
  - P95: 1,742.
  - P99: 2,335.
  - Records over 4,096 tokens: 0.
  - Records over 8,192 tokens: 0.
- Rebuild A: seq8192, batch 32.
  - Output: `data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs32/`.
  - Elapsed: 105.67 seconds.
  - Peak CUDA allocated/reserved: 16.700 / 18.557 GB.
  - Index size: 25.123 MB.
- Rebuild B: seq8192, batch 16.
  - Output: `data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16/`.
  - Elapsed: 96.76 seconds.
  - Peak CUDA allocated/reserved: 8.984 / 11.150 GB.
  - Index size: 25.123 MB.
- Seq8192 batch 16 evaluation:
  - Filtered dense Qwen: MRR 0.716, Hit@5 0.900, Hit@10 0.933,
    Mean Recall@10 0.917, Mean Precision@10 0.117, Mean nDCG@10 0.747.
  - Filtered hybrid RRF + Qwen: MRR 0.649, Hit@5 0.867, Hit@10 0.967,
    Mean Recall@10 0.950, Mean Precision@10 0.123, Mean nDCG@10 0.711.
  - Unfiltered dense Qwen: MRR 0.652, Hit@5 0.867, Hit@10 0.900,
    Mean Recall@10 0.867, Mean Precision@10 0.110, Mean nDCG@10 0.689.
  - Unfiltered hybrid RRF + Qwen: MRR 0.541, Hit@5 0.767, Hit@10 0.867,
    Mean Recall@10 0.833, Mean Precision@10 0.107, Mean nDCG@10 0.595.

## Interpretation
- Qwen3-Embedding-0.6B is a clear improvement over MiniLM for dense retrieval on the current seed set.
- The biggest lift is in unfiltered full-corpus retrieval, where dense Qwen Hit@10 improved from MiniLM's 0.733 to 0.900.
- Equal-weight RRF with BM25 is not automatically better once the dense model is stronger. The next hybrid step should test weighted RRF or dense-first retrieval with BM25 as a fallback.
- Opening max sequence length from 4,096 to 8,192 is safe on the RTX 4090, but
  current evidence records do not need it because no record exceeds 4,096
  tokens. Larger batch size was not faster on this corpus.

## Safety Notes
- The user asked for Qwen3.5; no dedicated Qwen3.5 embedding model was used. This run used the official ModelScope Qwen3 embedding model.
- Model weights are stored under ignored private data paths and were not committed.
- Metrics remain diagnostic because the seed labels are not human-reviewed.
