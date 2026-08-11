# Model Run: 20260516_phase2_qwen35_4b_compact_full_verifier_eval

## Summary

- Purpose: 用 compact Qwen3.5-4B verifier 在完整 BGE top10 evidence pool 上做 strict-fast-path direct/partial/false 评估。
- Status: diagnostic-only
- Run type: inference evaluation + error analysis
- Timestamp: 2026-05-16
- Environment: cloud `/root/autodl-tmp/FIN_Insight_Agent`, RTX 4090 24GB, conda base, Python 3.12.3, torch 2.11.0+cu130, transformers 5.8.1.

## Code And Command

- Entry points:
  - `scripts/run_qwen_small_verifier.py`
  - `scripts/evaluate_small_verifier.py`
- Model: `/root/autodl-tmp/system_disk_backup/root/hf_models/Qwen3.5-4B`
- Runtime: strict fast path required; no fallback warning observed.
- Command profile:

```bash
python scripts/run_qwen_small_verifier.py \
  --input-path reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl \
  --output-path reports/verifier/sec_tech_10k_qwen35_4b_compact_full230.jsonl \
  --model-name /root/autodl-tmp/system_disk_backup/root/hf_models/Qwen3.5-4B \
  --device cuda \
  --torch-dtype bfloat16 \
  --batch-size 4 \
  --max-length 4096 \
  --max-new-tokens 64 \
  --require-fast-path
```

## Inputs

- Evidence pool: `reports/evidence_pool/sec_tech_10k_bge_top10_evidence_pool.jsonl`
- Pool boundary: BGE reranker top10 per `(query_id, facet)`.
- Rows: 230 rows, 23 facets.
- Label protocol: Codex-assisted object labels in `eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates_codex_labeled.jsonl`.

## Outputs

- Predictions: `reports/verifier/sec_tech_10k_qwen35_4b_compact_full230.jsonl`
- Metrics: `reports/metrics/sec_tech_10k_qwen35_4b_compact_full230_metrics.json`
- Log: `reports/logs/qwen35_4b_compact_full230_20260516.log`
- Error analysis: `reports/metrics/sec_tech_10k_qwen35_4b_compact_full230_error_analysis.json`
- Error examples: `reports/metrics/sec_tech_10k_qwen35_4b_compact_full230_error_examples.csv`
- Debug subset:
  - `reports/verifier/sec_tech_10k_qwen35_4b_debug_error_subset_input.jsonl`
  - `reports/verifier/sec_tech_10k_qwen35_4b_debug_error_subset.jsonl`
  - `reports/logs/qwen35_4b_debug_error_subset_20260516.log`

## Results

Full compact verifier:

- Rows: 230
- Parse status: 230 parsed, 0 invalid
- Accuracy: 0.5478
- Macro F1: 0.5342
- Predicted label counts: direct 89, partial 70, false 71
- Gold label counts in BGE top10 pool: direct 87, partial 78, false 65

Class metrics:

- Direct precision / recall / F1: 0.7416 / 0.7586 / 0.7500
- Partial precision / recall / F1: 0.3571 / 0.3205 / 0.3378
- False precision / recall / F1: 0.4930 / 0.5385 / 0.5147

Policy metrics:

| Policy | Kept Objects | Avg / Facet | Direct Precision | Relevant Precision | False Rate | Direct Coverage | Relevant Coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| BGE top10 pool | 230 | 10.0000 | 0.3783 | 0.7174 | 0.2826 | 1.0000 | 1.0000 |
| Qwen keep direct | 89 | 3.8696 | 0.7416 | 0.9551 | 0.0449 | 1.0000 | 1.0000 |
| Qwen keep direct+partial | 159 | 6.9130 | 0.5346 | 0.8113 | 0.1887 | 1.0000 | 1.0000 |

For reference, BGE selected@5 over the same labeled review setup had average relevant P@5 0.8609 and direct P@5 0.6174.

## Error Analysis

Confusion highlights:

- Pred direct but gold partial: 19
- Pred direct but gold false: 4
- Gold direct but pred partial: 19
- Gold direct but pred false: 2
- Gold partial but pred false: 34
- Gold false but pred partial: 26

By object type for keep-direct:

| Object Type | Rows | Kept Direct | Direct Precision | False Rate |
| --- | ---: | ---: | ---: | ---: |
| claim | 134 | 40 | 0.7750 | 0.0750 |
| metric | 69 | 27 | 0.6296 | 0.0000 |
| table | 27 | 22 | 0.8182 | 0.0455 |

The debug subset over the 4 actual false-positive direct cases and 2 direct-to-false cases showed a label/prompt mismatch:

- Some current labels are strict about object identity, while the model sees useful context embedded in the object's `object_text`.
- Some current `direct` labels mean "directly supports one key aspect of the facet"; the prompt can read `must_find` as all listed aspects must be satisfied by one object.
- Example: Snowflake consumption visibility evidence was gold direct, but the debug verifier marked it false because it did not cover RPO and customer metrics together.
- Example: NVIDIA demand context was gold direct for data-center growth context, but the debug verifier marked it false because it lacked exact growth numbers and all listed drivers.

## Experiment Governance

- Hypothesis: compact Qwen3.5-4B strict-fast-path verifier can clean BGE top10 evidence before synthesis.
- Decision target: reduce false evidence while preserving direct/relevant facet coverage.
- Ceiling / upper bound: BGE top10 already contains direct evidence for every facet under current labels.
- Baselines:
  - BGE top10 pool false rate 0.2826 and direct precision 0.3783.
  - BGE selected@5 direct P@5 0.6174 and relevant P@5 0.8609.
- Stop conditions: stop promotion if parse failures appear, if direct coverage drops below 23/23, or if false evidence remains high.
- Efficiency gate: strict fast path required; no fallback accepted.
- Decision label: diagnostic-only.
- Mainline decision: Qwen3.5-4B compact verifier is useful as a precision gate after BGE, especially `keep_direct`; however, before promoting it, align the label protocol and prompt around aspect-level directness.

## Runtime Efficiency

- Batch size: 4
- Max new tokens: 64
- Shell elapsed: 431 seconds for model load + 230 rows on cloud run.
- Script generation wall time: 335.5812s for 230 rows.
- Effective generation throughput: about 0.69 rows/sec including batching overhead, excluding cold model load.
- Debug subset run was intentionally small and explanation-bearing; it is not representative of serving mode.

## Caveats And Next Step

- Labels are Codex-assisted and not human-reviewed final gold.
- Accuracy and macro F1 are not the most useful metrics here because the production policy likely keeps only direct evidence.
- The next step should not be another bigger model run yet. First define whether `direct` means:
  - direct support for at least one facet aspect, or
  - complete support for all `must_find` aspects in the facet.
- After that, either revise labels or split facets into aspect-level verifier tasks, then rerun the compact 4B verifier.
