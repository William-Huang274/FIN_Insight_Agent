# Model Run: 20260515_phase1_complex_query_probe

## Summary
- Purpose: Manually inspect retrieval behavior on common and deeper finance
  questions before treating seed metrics as meaningful quality evidence.
- Status: completed.
- Run type: retrieval inference / manual evaluation.
- Timestamp: 2026-05-15.
- Environment: cloud Linux workspace with one NVIDIA GeForce RTX 4090.

## Code And Command
- Branch: `feature/phase1-sec-foundation`.
- Remote workspace: `/root/autodl-tmp/FIN_Insight_Agent`.
- Entry point: temporary probe script executed from `/tmp`; no reusable project
  script was added.
- Retriever:
  - Dense: Qwen3-Embedding-0.6B seq8192 batch16 index.
  - Hybrid: equal-weight BM25+dense RRF with `rrf_k=60`.
- Command:
  - `/root/miniconda3/bin/python /tmp/sec_complex_query_probe.py`.
- Seeds: not applicable.

## Inputs
- Evidence store:
  `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`.
- Evidence count: 2,842.
- Indexes:
  - BM25: `data/indexes/bm25/sec_tech_10k/`.
  - Dense Qwen:
    `data/indexes/dense/sec_tech_10k_qwen3_embedding_0_6b_seq8192_bs16/`.
- Query set: 12 manually designed common and deep finance questions over
  `MSFT`, `AAPL`, `NVDA`, `AMZN`, `META`, `GOOGL`, `ADBE`, `SNOW`, `PANW`,
  and `AMD`.

## Outputs
- Raw JSON:
  `reports/retrieval_eval/sec_tech_10k_complex_query_probe.json`.
- Manual inspection report:
  `reports/retrieval_eval/sec_tech_10k_complex_query_probe.md`.

## Results
- Runtime: 19.209 seconds after model load.
- Unfiltered dense metadata match:
  - 41 of 60 top5 hits matched the target ticker/year.
  - Strong matches: MSFT and AAPL had 5/5 target ticker/year hits.
  - Weak matches: NVIDIA data-center query had 1/5, NVIDIA risk query had 2/5,
    and Amazon liquidity query had 2/5.
- Filtered retrieval quality:
  - Good: MSFT cloud/AI margin, AAPL iPhone/Services margin, SNOW
    consumption/RPO/customer metrics, AMD segment/margin/inventory, and NVIDIA
    supply/customer risk when using hybrid.
  - Partial: AMZN AWS/capex, META ads/AI capex, GOOGL ads/cloud/capex, ADBE
    ARR/RPO, AMZN liquidity/leases/commitments.
  - Weak: PANW platformization/billings/RPO.

## Interpretation
- Current seed metrics have value as ranking diagnostics for known evidence
  IDs, especially MRR and nDCG.
- They are not enough to claim deep finance retrieval quality because the seed
  qrels do not verify multi-facet coverage.
- Ticker/year filtering remains mandatory. Without it, semantically similar
  filings from adjacent years or peer companies enter top5.
- Single-query retrieval is not enough for many analyst-style questions. A
  query about AWS margin and capex, or ARR and RPO, needs either decomposition
  into facets or a second-stage planner that retrieves revenue, margin,
  commitments, and risk evidence separately.
- Equal-weight RRF should not be promoted as the mainline. It helps exact-term
  risk queries but can also lift noisy BM25 matches above better dense results.

## Experiment Governance
- Hypothesis: complex finance questions will reveal whether the seed metrics
  reflect useful retrieval behavior beyond narrow evidence-id hits.
- Decision target: manually verify top5 evidence relevance for 12 complex
  queries, with and without metadata filters.
- Ceiling / upper bound: no human-reviewed qrels or final answer synthesis;
  this is inspection-only.
- Baselines to beat: current Qwen dense and equal-weight Qwen+BM25 RRF.
- Split and leakage guard: no training or tuning; public SEC filings only.
- Stop conditions: do not tune retrievers from this probe alone. Convert
  observed failures into qrels and retrieval design changes first.
- Efficiency gate: run the full probe in minutes on one RTX 4090.
- Decision label: diagnostic-only.
- Mainline decision: keep Qwen dense as the dense baseline, but add
  complex-query reviewed qrels and facet-aware retrieval before claiming
  quality.

## Runtime Efficiency
- Wall time: 19.209 seconds.
- Bottleneck diagnosis: one-time model load dominates small query batches.
- Serving implication: a long-lived retrieval runner is needed; per-query CLI
  model loading remains unsuitable for interactive use.

## Caveats And Next Step
- Not run: no answer generation, reranker, weighted RRF, or human-reviewed qrel
  expansion.
- Known risks: manual judgments are qualitative and should be converted into
  reproducible labels.
- Next decision: add complex multi-facet qrels and implement query
  decomposition/facet-aware retrieval before reranker work.
