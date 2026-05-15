# SEC Tech 10-K Seed Retrieval Evaluation

Date: 2026-05-15

Scope: 30 diagnostic seed queries over 2,842 EvidenceObjects from 30 SEC 10-K filings.

Label status: agent-curated seed labels from the current EvidenceObject store. This is a diagnostic set, not a human-reviewed benchmark.

## Ticker/Year Filtered

This mode assumes the upstream agent has already identified the target ticker and fiscal year.

| Retriever | MRR | Hit@1 | Hit@3 | Hit@5 | Hit@10 | Mean Recall@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.568 | 0.433 | 0.633 | 0.833 | 0.867 | 0.833 |
| Dense MiniLM | 0.628 | 0.467 | 0.767 | 0.833 | 0.867 | 0.833 |
| Hybrid RRF | 0.701 | 0.567 | 0.800 | 0.867 | 1.000 | 0.950 |
| Dense Qwen3-Embedding-0.6B | 0.709 | 0.600 | 0.800 | 0.867 | 0.933 | 0.917 |
| Hybrid RRF + Qwen3-Embedding-0.6B | 0.640 | 0.467 | 0.767 | 0.867 | 0.967 | 0.950 |

Filtered hybrid RRF recovered at least one relevant EvidenceObject for every seed query by top 10. Mean Recall@10 is below 1.0 because three multi-label queries recovered one of two expected evidence IDs.

## Unfiltered Full Corpus

This mode searches the full 2,842-record corpus without ticker/year filters.

| Retriever | MRR | Hit@1 | Hit@3 | Hit@5 | Hit@10 | Mean Recall@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| BM25 | 0.325 | 0.133 | 0.467 | 0.600 | 0.733 | 0.700 |
| Dense MiniLM | 0.462 | 0.367 | 0.500 | 0.633 | 0.733 | 0.683 |
| Hybrid RRF | 0.521 | 0.400 | 0.667 | 0.700 | 0.733 | 0.667 |
| Dense Qwen3-Embedding-0.6B | 0.634 | 0.500 | 0.700 | 0.833 | 0.900 | 0.867 |
| Hybrid RRF + Qwen3-Embedding-0.6B | 0.519 | 0.333 | 0.733 | 0.767 | 0.867 | 0.833 |

The unfiltered result shows that ticker/year detection and metadata filtering are part of the retrieval problem. Qwen3-Embedding-0.6B substantially improves full-corpus dense retrieval over MiniLM. Simple equal-weight RRF is not always beneficial with the stronger dense model, so hybrid weighting should be tuned rather than reused unchanged.

## Artifacts

- Filtered JSON report: `reports/retrieval_eval/sec_tech_10k_seed_eval_cloud_filtered.json`
- Unfiltered JSON report: `reports/retrieval_eval/sec_tech_10k_seed_eval_cloud_unfiltered.json`
- Qwen filtered JSON report: `reports/retrieval_eval/sec_tech_10k_seed_eval_qwen3_0_6b_filtered.json`
- Qwen unfiltered JSON report: `reports/retrieval_eval/sec_tech_10k_seed_eval_qwen3_0_6b_unfiltered.json`
- Gold set: `eval_sets/sec_tech_10k_seed.jsonl`
