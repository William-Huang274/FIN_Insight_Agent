# Model Run: 20260515_phase1_multifacet_retrieval_eval

## Summary

- Purpose: Evaluate complex finance questions with multi-facet qrels and test
  query decomposition / facet-aware retrieval.
- Status: completed.
- Run type: retrieval evaluation.
- Timestamp: 2026-05-15.
- Environment: cloud Linux workspace with one NVIDIA GeForce RTX 4090, plus a
  local BM25 diagnostic run.

## Code And Command

- Branch: `feature/phase1-sec-foundation`.
- Reusable entry point: `scripts/evaluate_multifacet_retrieval.py`.
- New evaluation utilities:
  - `src/eval/multifacet_retrieval_eval.py`
  - `src/retrieval/facet_aware_retriever.py`
- Main cloud command shape:
  - `/root/miniconda3/bin/python scripts/evaluate_multifacet_retrieval.py --retrievers dense,hybrid,facet_dense,facet_hybrid,facet_dense_rr,facet_hybrid_rr --dense-index-dir data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16 --filter-mode ticker_year --device cuda`
  - `/root/miniconda3/bin/python scripts/evaluate_multifacet_retrieval.py --retrievers dense,hybrid,facet_dense_rr,facet_hybrid_rr --dense-index-dir data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16 --filter-mode none --device cuda`

## Inputs

- Gold set: `eval_sets/sec_tech_10k_complex_multifacet.jsonl`.
- Query count: 12 complex finance questions.
- Facet count: 36.
- Label source: agent-authored diagnostic qrels from the current
  `EvidenceObject` store.
- Evidence store: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`.
- Evidence count: 2,842.
- Indexes:
  - BM25: `data/indexes/bm25/sec_tech_10k/`.
  - Dense Qwen:
    `data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16/`.

## Outputs

- Summary report:
  `reports/retrieval_eval/sec_tech_10k_complex_multifacet_eval_summary.md`.
- Filtered Qwen report:
  `reports/retrieval_eval/sec_tech_10k_complex_multifacet_eval_qwen_filtered_rr.json`.
- Unfiltered Qwen report:
  `reports/retrieval_eval/sec_tech_10k_complex_multifacet_eval_qwen_unfiltered_rr.json`.
- Local BM25 diagnostic:
  `reports/retrieval_eval/sec_tech_10k_complex_multifacet_eval_bm25_local.json`.

## Results

Filtered mode, using ticker/year metadata:

| Retriever | nDCG@10 | FacetCov@10 | AllFacets@10 | Recall@10 |
| --- | ---: | ---: | ---: | ---: |
| dense | 0.766 | 0.833 | 0.583 | 0.771 |
| hybrid | 0.794 | 0.889 | 0.667 | 0.839 |
| facet_dense RRF | 0.689 | 0.806 | 0.417 | 0.768 |
| facet_hybrid RRF | 0.679 | 0.778 | 0.417 | 0.742 |
| facet_dense_rr | 0.852 | 0.889 | 0.667 | 0.867 |
| facet_hybrid_rr | 0.853 | 0.917 | 0.750 | 0.900 |

Unfiltered full-corpus mode:

| Retriever | nDCG@10 | FacetCov@10 | AllFacets@10 | Recall@10 |
| --- | ---: | ---: | ---: | ---: |
| dense | 0.674 | 0.806 | 0.500 | 0.743 |
| hybrid | 0.477 | 0.611 | 0.250 | 0.529 |
| facet_dense_rr | 0.743 | 0.778 | 0.417 | 0.764 |
| facet_hybrid_rr | 0.673 | 0.778 | 0.417 | 0.743 |

## Interpretation

- Query decomposition helps only when the fusion policy preserves facet
  diversity. Naive RRF over the decomposed queries performed worse than the
  original-query baselines.
- Facet-first round-robin is the best current filtered strategy. It explicitly
  gives each facet query candidate slots before filling the final top-k list.
- In full-corpus mode, Qwen dense is still the most stable baseline at
  `AllFacets@10`, while `facet_dense_rr` improves early coverage and `nDCG@5`.
- Equal-weight hybrid RRF remains risky with Qwen dense, especially without
  metadata filters.

## Experiment Governance

- Hypothesis: complex finance questions need facet-level qrels and retrieval
  policies that preserve evidence diversity across revenue, margin, capex,
  RPO, risk, and liquidity facets.
- Decision target: compare original-query dense/hybrid retrieval against
  decomposed facet-aware retrieval.
- Ceiling / upper bound: qrels are agent-authored and diagnostic-only; no human
  adjudication, no answer generation, and no reranker in this run.
- Baselines to beat: Qwen dense original-query retrieval and equal-weight
  BM25+dense hybrid RRF.
- Split and leakage guard: no model training or tuning; public SEC filings
  only.
- Stop conditions: do not tune retrievers directly against this 12-query set.
  Expand and human-review multi-facet qrels first.
- Decision label: diagnostic-success.
- Mainline decision: keep Qwen dense and add facet-first round-robin as a
  candidate retrieval path; do not promote naive facet RRF.

## Caveats And Next Step

- The qrels are not exhaustive relevance labels. `precision@k` is measured
  against the listed gold evidence only.
- Facet queries are oracle/agent-authored in this run. A production path still
  needs automatic decomposition and validation.
- Next step: human-review multi-facet qrels, then test a dense-first strategy
  with controlled BM25 fallback or reranking.
