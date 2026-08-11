# Model Run: 20260516_phase2_object_reranker_baseline_compare

## Summary

- Purpose: 对同一份 object-level BM25 top25 候选池跑两个语义 reranker 基线。
- Status: completed
- Run type: inference + evaluation
- Timestamp: 2026-05-16
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, RTX 4090 24GB, conda base, Python 3.12.3, torch 2.11.0+cu130, transformers 5.8.1, sentence-transformers 5.5.0, modelscope 1.34.0.

## Code And Command

- Entry point: `scripts/evaluate_object_reranker.py`
- Local code change: added `qwen-reranker` mode using official Qwen3 yes/no causal-LM logit scoring.
- Remote model source: ModelScope cache under `/root/autodl-tmp/modelscope_cache`.
- Commands:

```bash
python scripts/evaluate_object_reranker.py --mode bm25 --model-alias bm25_order_cloud ...
python scripts/evaluate_object_reranker.py --mode cross-encoder --model-name /root/autodl-tmp/modelscope_cache/BAAI/bge-reranker-v2-m3 --model-alias bge_reranker_v2_m3_cloud --batch-size 8 --max-length 2048 --doc-max-chars 6000 --device cuda ...
python scripts/evaluate_object_reranker.py --mode qwen-reranker --model-name /root/autodl-tmp/modelscope_cache/Qwen/Qwen3-Reranker-0___6B --model-alias qwen3_reranker_0_6b_official_cloud --batch-size 4 --max-length 2048 --doc-max-chars 6000 --device cuda ...
```

## Inputs

- Candidate boundary: `reports/retrieval_eval/sec_tech_10k_object_bm25_variant_predictions.jsonl`
- Labels: `eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates_codex_labeled.jsonl`
- Structured objects: `data/processed_private/structured_objects/sec_tech_10k_{tables,metrics,claims}.jsonl`
- Label protocol: Codex-assisted first-pass labels, `direct=2`, `partial=1`, `false=0`; 575 labeled candidate rows across 23 facets.
- Rerank boundary: rerank only BM25 object top25 per facet; select top5; no candidate expansion.

## Outputs

- `reports/retrieval_eval/sec_tech_10k_object_bm25_order_cloud_eval.json`
- `reports/retrieval_eval/sec_tech_10k_object_bge_reranker_v2_m3_cloud_eval.json`
- `reports/retrieval_eval/sec_tech_10k_object_qwen3_reranker_0_6b_official_cloud_eval.json`
- `reports/retrieval_eval/sec_tech_10k_object_reranker_baseline_comparison.json`
- `reports/retrieval_eval/sec_tech_10k_object_reranker_baseline_comparison.csv`

## Results

| Model | Relevant P@5 | Direct P@5 | False@5 | nDCG@5 | Direct Coverage | Relevant Coverage | Scoring Seconds | Wall Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 order | 0.7739 | 0.4435 | 1.1304 | 0.7780 | 0.9565 | 0.9565 | 0.0000 | 1.7197 |
| BGE reranker v2 m3 | 0.8609 | 0.6174 | 0.6957 | 0.9458 | 1.0000 | 1.0000 | 3.2317 | 18.9659 |
| Qwen3 reranker 0.6B official | 0.8522 | 0.5478 | 0.7391 | 0.8857 | 1.0000 | 1.0000 | 7.8213 | 34.3622 |

Interpretation:

- Both semantic rerankers beat BM25 on coverage, direct precision, relevant precision, nDCG, and noise reduction.
- BGE is the stronger first production-style reranker baseline on this eval: higher direct precision, higher nDCG, lower false@5, and faster scoring.
- Qwen3-Reranker-0.6B is valid only through the official causal-LM yes/no logit scoring path. The generic `sentence-transformers CrossEncoder` path was discarded as invalid because the model card uses a different inference contract.

## Experiment Governance

- Hypothesis: semantic reranking should reduce false top5 object hits and improve direct evidence ordering over lexical BM25.
- Decision target: improve `mean_precision_direct_at_5`, `mean_ndcg_at_5`, and reduce `mean_false_at_5` on the 23-facet object review set.
- Ceiling: candidate relevant/direct facet coverage was already high enough for a reranker experiment because BM25 top25 had labels in the pool for almost all facets.
- Baseline to beat: BM25 top25 candidate order selected top5.
- Leakage guard: reranker only sees query text plus candidate object text; it does not use labels during inference.
- Decision label: proceed with BGE as the current reranker baseline; keep Qwen official path as an alternate model, not the current winner.

## Runtime Efficiency

- BGE scoring throughput: 575 pairs / 3.2317s scoring, batch 8, CUDA.
- Qwen official scoring throughput: 575 pairs / 7.8213s scoring, batch 4, CUDA.
- First ModelScope downloads dominated wall-clock during setup and are not included as model scoring time.
- Serving implication: both are feasible as a batched rerank stage for top25 candidates; BGE is currently cheaper and stronger for this object-level eval.

## Caveats And Next Step

- The labels are still Codex-assisted review labels, not final human gold.
- `Qwen3-Reranker-0.6B` was tested at `max_length=2048` and `doc_max_chars=6000` for same-budget comparison; a long-context diagnostic can be run separately.
- Next decision: use BGE reranker to generate cleaner topK pools, then add a small semantic verifier for `direct/partial/false` classification over structured objects.
