# SEC Tech 10-K Complex Multi-Facet Retrieval Evaluation

## Summary

This evaluation converts the prior complex finance probe into 12 multi-facet
qrels. Each query has a top-level complex question, three facet subqueries, and
facet-specific relevant `EvidenceObject` IDs.

The labels are agent-authored diagnostic qrels from the current evidence store,
not final human-reviewed relevance judgments. They are useful for comparing
retrieval strategies, but `precision@k` should be read as precision against
this narrow qrel set rather than a complete false-positive rate.

## Inputs

- Gold set: `eval_sets/sec_tech_10k_complex_multifacet.jsonl`
- Query count: 12
- Facet count: 36
- Corpus: 2,842 SEC 10-K `EvidenceObject` records
- Dense model: `Qwen/Qwen3-Embedding-0.6B`
- Dense index: `sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16`
- Fusion baselines:
  - `dense`: original complex query only.
  - `hybrid`: original complex query with BM25+dense RRF.
  - `facet_dense` / `facet_hybrid`: original query plus facet queries fused
    with RRF.
  - `facet_dense_rr` / `facet_hybrid_rr`: original query plus facet queries
    fused with facet-first round-robin quota.

## Filtered Results

Filtered mode uses the gold ticker and fiscal year as metadata filters.

| Retriever | MRR | nDCG@5 | nDCG@10 | FacetCov@5 | FacetCov@10 | AllFacets@10 | Recall@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dense | 0.944 | 0.742 | 0.766 | 0.778 | 0.833 | 0.583 | 0.771 | 0.317 |
| hybrid | 0.917 | 0.733 | 0.794 | 0.778 | 0.889 | 0.667 | 0.839 | 0.350 |
| facet_dense RRF | 0.826 | 0.578 | 0.689 | 0.583 | 0.806 | 0.417 | 0.768 | 0.317 |
| facet_hybrid RRF | 0.792 | 0.600 | 0.679 | 0.583 | 0.778 | 0.417 | 0.742 | 0.317 |
| facet_dense_rr | 0.958 | 0.779 | 0.852 | 0.778 | 0.889 | 0.667 | 0.867 | 0.358 |
| facet_hybrid_rr | 0.958 | 0.751 | 0.853 | 0.750 | 0.917 | 0.750 | 0.900 | 0.375 |

Best filtered run: `facet_hybrid_rr`.

- It has the strongest `FacetCov@10` at 0.917.
- It has the strongest `AllFacets@10` at 0.750.
- It also has the best `Recall@10` and `Precision@10` among these runs.
- `facet_dense_rr` is very close and has the best `nDCG@5`.

Naive RRF facet fusion is worse than the original-query baselines. It should
not become the mainline facet-aware method.

## Unfiltered Results

Unfiltered mode searches the full corpus without ticker/year filters.

| Retriever | MRR | nDCG@5 | nDCG@10 | FacetCov@5 | FacetCov@10 | AllFacets@10 | Recall@10 | Precision@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dense | 0.826 | 0.575 | 0.674 | 0.583 | 0.806 | 0.500 | 0.743 | 0.308 |
| hybrid | 0.709 | 0.393 | 0.477 | 0.417 | 0.611 | 0.250 | 0.529 | 0.225 |
| facet_dense_rr | 0.861 | 0.680 | 0.743 | 0.750 | 0.778 | 0.417 | 0.764 | 0.317 |
| facet_hybrid_rr | 0.808 | 0.569 | 0.673 | 0.639 | 0.778 | 0.417 | 0.743 | 0.308 |

Unfiltered interpretation:

- Qwen dense remains the most stable full-corpus baseline at `AllFacets@10`.
- `facet_dense_rr` improves early ranking and multi-facet coverage at top 3/5:
  `nDCG@5` rises from 0.575 to 0.680 and `FacetCov@5` rises from 0.583 to 0.750.
- Full-corpus hybrid RRF is weak here. BM25 introduces enough cross-company or
  cross-year noise that it hurts Qwen's dense ranking.

## Local BM25 Diagnostic

The same multi-facet evaluator also ran against the local BM25 index.

| Retriever | nDCG@10 | FacetCov@10 | AllFacets@10 | Recall@10 |
| --- | ---: | ---: | ---: | ---: |
| BM25 | 0.667 | 0.806 | 0.583 | 0.708 |
| facet_bm25 RRF | 0.674 | 0.750 | 0.417 | 0.733 |
| facet_bm25_rr | 0.770 | 0.861 | 0.583 | 0.867 |

This supports the same design conclusion: the problem is not decomposition by
itself. The fusion policy matters. Round-robin quota is more aligned with
multi-facet analyst questions than naive RRF over decomposed queries.

## Decision

- Keep Qwen dense as the robust baseline.
- Keep facet-first round-robin retrieval as the first facet-aware candidate.
- Do not promote naive facet RRF.
- Keep ticker/year routing as a first-class retrieval component. The
  unfiltered results are still materially weaker.
- Treat the new qrels as diagnostic. The next benchmark step is human review
  and expansion of multi-facet labels, not model tuning against this small set.
