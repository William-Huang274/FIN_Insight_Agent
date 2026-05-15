# Model Run: 20260515_phase1_seed_retrieval_eval

## Summary
- Purpose: 评估 BM25、dense MiniLM、hybrid RRF 在 seed evidence query set 上的召回效果。
- Status: completed.
- Run type: evaluation / inference.
- Timestamp: 2026-05-15.
- Environment: cloud Linux workspace with one NVIDIA GeForce RTX 4090.

## Code And Command
- Branch: `feature/phase1-sec-foundation`.
- Entry point: `scripts/evaluate_retrieval.py`.
- Commands:
  - `python scripts/evaluate_retrieval.py --retrievers bm25,dense,hybrid --device cuda --output reports/retrieval_eval/sec_tech_10k_seed_eval_cloud_filtered.json`
  - `python scripts/evaluate_retrieval.py --retrievers bm25,dense,hybrid --filter-mode none --device cuda --output reports/retrieval_eval/sec_tech_10k_seed_eval_cloud_unfiltered.json`
- Environment note: `HF_ENDPOINT=https://hf-mirror.com` was set because direct `huggingface.co` access from the cloud host timed out in the previous dense smoke run.
- Seeds: not applicable.

## Inputs
- Gold set: `eval_sets/sec_tech_10k_seed.jsonl`.
- Query count: 30.
- Label source: agent-curated seed labels from the current EvidenceObject store.
- Label protocol: each seed query has a known ticker/year and 1-2 current
  EvidenceObject IDs that directly answer the question. Labels are not
  exhaustive corpus relevance judgments.
- Evidence store: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`.
- Evidence count: 2,842.
- Indexes:
  - BM25: `data/indexes/bm25/sec_tech_10k/`.
  - Dense: `data/indexes/dense/sec_tech_10k/`.
- Model: `sentence-transformers/all-MiniLM-L6-v2`.

## Outputs
- Filtered eval report: `reports/retrieval_eval/sec_tech_10k_seed_eval_cloud_filtered.json`.
- Unfiltered eval report: `reports/retrieval_eval/sec_tech_10k_seed_eval_cloud_unfiltered.json`.
- Summary report: `reports/retrieval_eval/sec_tech_10k_seed_eval_summary.md`.

## Results
- Ticker/year filtered mode:
  - BM25: MRR 0.568, Hit@5 0.833, Hit@10 0.867, Mean Recall@10 0.833,
    Mean Precision@10 0.110, Mean nDCG@10 0.623.
  - Dense MiniLM: MRR 0.628, Hit@5 0.833, Hit@10 0.867,
    Mean Recall@10 0.833, Mean Precision@10 0.110, Mean nDCG@10 0.657.
  - Hybrid RRF: MRR 0.701, Hit@5 0.867, Hit@10 1.000,
    Mean Recall@10 0.950, Mean Precision@10 0.123, Mean nDCG@10 0.741.
- Unfiltered full-corpus mode:
  - BM25: MRR 0.325, Hit@5 0.600, Hit@10 0.733, Mean Recall@10 0.700,
    Mean Precision@10 0.090, Mean nDCG@10 0.405.
  - Dense MiniLM: MRR 0.462, Hit@5 0.633, Hit@10 0.733,
    Mean Recall@10 0.683, Mean Precision@10 0.087, Mean nDCG@10 0.483.
  - Hybrid RRF: MRR 0.521, Hit@5 0.700, Hit@10 0.733,
    Mean Recall@10 0.667, Mean Precision@10 0.087, Mean nDCG@10 0.533.

## Metric Interpretation
- `precision@k` is qrel precision against the seed labels. Since labels are not
  exhaustive, non-matched retrieved chunks are not automatically irrelevant.
- `nDCG@k` measures whether the known truth IDs are ranked early. This is more
  useful than Hit@10 for deciding whether retrieval output will be comfortable
  for an answer synthesizer or reranker.
- The current reports include `top_hit` metadata and text previews for manual
  error inspection.

## Experiment Governance
- Hypothesis: hybrid RRF should improve seed retrieval robustness over BM25 or dense alone.
- Decision target: improve Hit@K/MRR on the 30-query seed set, especially in the ticker/year filtered mode used by a structured financial agent.
- Ceiling / upper bound: the seed set is not human-reviewed, so this is diagnostic-only for quality claims.
- Baselines to beat: BM25-only and dense-only.
- Split and leakage guard: no training or tuning; queries and labels are seed diagnostics over public filings.
- Stop conditions: stop before claiming production retrieval quality until labels are human-reviewed and expanded.
- Efficiency gate: full evaluation should complete within minutes on the cloud host.
- Decision label: proceed for engineering; diagnostic-only for model quality.
- Mainline decision: keep hybrid RRF as the next retrieval baseline, but prioritize reviewed labels and query routing before tuning dense models.

## Runtime Efficiency
- Dense model loaded from local cache after the prior cloud build.
- Current evaluation path loads the dense model separately for dense and hybrid retrievers.
- Main bottleneck: repeated model load and Python in-process sorting, not GPU embedding throughput.
- Next optimization: implement a long-lived retrieval runner that shares loaded retrievers across BM25, dense, hybrid, and evaluation calls.

## Safety Notes
- No credentials or private connection details were written to the repository.
- Reports are small derived metrics and evidence IDs; raw SEC filings and generated indexes remain ignored.
- Metrics should be presented as seed diagnostics until labels are reviewed.
