# SEC Tech 10-K Seed Retrieval Evaluation

Date: 2026-05-15

Scope: 30 diagnostic seed queries over 2,842 EvidenceObjects from 30 SEC 10-K filings.

Label status: agent-curated seed labels from the current EvidenceObject store. This is a diagnostic set, not a human-reviewed benchmark.

## Label Protocol

The seed truth set was created by selecting current EvidenceObject IDs that directly answer each diagnostic question. Each query has a known ticker and fiscal year, plus one or two relevant evidence IDs. The labels are intentionally narrow and are not exhaustive relevance judgments over the corpus.

Metric implication: `precision@k` here means precision against the seed qrels only. A retrieved item that is not in `relevant_evidence_ids` may still be useful context, a same-topic adjacent section, a wrong-year duplicate, or a true false positive. Use `nDCG@k` and MRR to judge whether the known truth appears early; do not treat low precision as a complete irrelevant-rate estimate until labels are human-reviewed and expanded.

## Ticker/Year Filtered

This mode assumes the upstream agent has already identified the target ticker and fiscal year.

| Retriever | MRR | Hit@1 | Hit@3 | Hit@5 | Hit@10 | Recall@10 | P@10 | nDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.568 | 0.433 | 0.633 | 0.833 | 0.867 | 0.833 | 0.110 | 0.623 |
| Dense MiniLM | 0.628 | 0.467 | 0.767 | 0.833 | 0.867 | 0.833 | 0.110 | 0.657 |
| Hybrid RRF | 0.701 | 0.567 | 0.800 | 0.867 | 1.000 | 0.950 | 0.123 | 0.741 |
| Dense Qwen3-Embedding-0.6B seq8192 | 0.716 | 0.600 | 0.800 | 0.900 | 0.933 | 0.917 | 0.117 | 0.747 |
| Hybrid RRF + Qwen3 seq8192 | 0.649 | 0.500 | 0.767 | 0.867 | 0.967 | 0.950 | 0.123 | 0.711 |

Filtered hybrid RRF with MiniLM recovered at least one relevant EvidenceObject for every seed query by top 10. Qwen dense had the best MRR and nDCG@10, so it ranked the known truths earlier on average. Qwen hybrid improved Hit@10 versus Qwen dense but degraded MRR and nDCG, which means equal-weight RRF sometimes pulled weaker BM25 candidates above stronger dense hits.

## Unfiltered Full Corpus

This mode searches the full 2,842-record corpus without ticker/year filters.

| Retriever | MRR | Hit@1 | Hit@3 | Hit@5 | Hit@10 | Recall@10 | P@10 | nDCG@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.325 | 0.133 | 0.467 | 0.600 | 0.733 | 0.700 | 0.090 | 0.405 |
| Dense MiniLM | 0.462 | 0.367 | 0.500 | 0.633 | 0.733 | 0.683 | 0.087 | 0.483 |
| Hybrid RRF | 0.521 | 0.400 | 0.667 | 0.700 | 0.733 | 0.667 | 0.087 | 0.533 |
| Dense Qwen3-Embedding-0.6B seq8192 | 0.652 | 0.533 | 0.700 | 0.867 | 0.900 | 0.867 | 0.110 | 0.689 |
| Hybrid RRF + Qwen3 seq8192 | 0.541 | 0.367 | 0.733 | 0.767 | 0.867 | 0.833 | 0.107 | 0.595 |

The unfiltered result shows that ticker/year detection and metadata filtering are part of the retrieval problem. Qwen3-Embedding-0.6B substantially improves full-corpus dense retrieval over MiniLM. Simple equal-weight RRF is not always beneficial with the stronger dense model, so hybrid weighting should be tuned rather than reused unchanged.

## Qwen Context And Batch Probe

Token-length analysis with the Qwen tokenizer found no current EvidenceObject over 4,096 tokens:
minimum 85, median 791, mean 856.1, maximum 3,536, p95 1,742, p99 2,335.

The seq8192 rebuild therefore tests headroom and throughput, not truncation recovery. On the RTX 4090 cloud host:

| Build | Elapsed | Peak CUDA Allocated | Peak CUDA Reserved | Index Size |
| --- | ---: | ---: | ---: | ---: |
| seq4096, batch 8 | about 86.5s | not captured | not captured | about 26 MB |
| seq8192, batch 16 | 96.76s | 8.984 GB | 11.150 GB | 25.123 MB |
| seq8192, batch 32 | 105.67s | 16.700 GB | 18.557 GB | 25.123 MB |

The larger batch did not improve throughput on this corpus, likely because variable-length padding and longer max length increased wasted compute. Current mainline should keep Qwen dense, but prefer batch 8 or 16 unless a larger corpus changes the throughput profile.

## Artifacts

- Filtered JSON report: `reports/retrieval_eval/sec_tech_10k_seed_eval_cloud_filtered.json`
- Unfiltered JSON report: `reports/retrieval_eval/sec_tech_10k_seed_eval_cloud_unfiltered.json`
- Qwen seq8192 filtered JSON report: `reports/retrieval_eval/sec_tech_10k_seed_eval_qwen3_0_6b_seq8192_filtered.json`
- Qwen seq8192 unfiltered JSON report: `reports/retrieval_eval/sec_tech_10k_seed_eval_qwen3_0_6b_seq8192_unfiltered.json`
- Qwen seq8192 batch runtime reports: `reports/model_runs/qwen3_embedding_seq8192_bs16_runtime.json`, `reports/model_runs/qwen3_embedding_seq8192_bs32_runtime.json`
- Gold set: `eval_sets/sec_tech_10k_seed.jsonl`
