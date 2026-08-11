# Model Run: 20260516_phase2_codex_object_review_labeling

## Summary

- Purpose: Fill the object review sheet with Codex model-assisted
  `human_label` values so reranker and verifier experiments can be evaluated
  against a more explicit direct/partial/false label protocol.
- Status: completed
- Run type: labeling + evaluation
- Timestamp: 2026-05-16
- Environment: local Windows workspace, CPU

## Code And Command

- Entry points:
  - `scripts/label_object_review_candidates_codex.py`
  - `scripts/evaluate_object_review_labels.py`
- Commands:

```powershell
python -m py_compile scripts\label_object_review_candidates_codex.py scripts\evaluate_object_review_labels.py
python scripts\label_object_review_candidates_codex.py
python scripts\evaluate_object_review_labels.py --predictions-path reports\retrieval_eval\sec_tech_10k_object_rule_verifier_predictions.jsonl --report-path reports\retrieval_eval\sec_tech_10k_object_rule_verifier_codex_label_eval.json
python scripts\evaluate_object_review_labels.py --predictions-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_selected5_predictions.jsonl --report-path reports\retrieval_eval\sec_tech_10k_object_bm25_selected5_codex_label_eval.json
```

- Config:
  - reviewer: `codex_model_assisted_review`
  - ruleset: `codex_object_review_v0.1`
  - label space: `direct | partial | false`
- Git commit / dirty files: working tree dirty; Phase 2 scripts, docs, and
  reports are not yet committed.
- Seeds: none.

## Inputs

- Review candidates:
  `eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates.jsonl`
- Structured object directory:
  `data/processed_private/structured_objects`
- Rule verifier predictions:
  `reports/retrieval_eval/sec_tech_10k_object_rule_verifier_predictions.jsonl`
- Lexical selected@5 predictions:
  `reports/retrieval_eval/sec_tech_10k_object_bm25_variant_selected5_predictions.jsonl`
- Label protocol:
  model-assisted first-pass labels; user spot-check still required before
  treating this as final human gold.

## Model Parameters

- Model: Codex-authored deterministic domain rules over structured object text.
- Rule criteria:
  - `direct`: object directly states a facet-critical metric, claim, caveat, or
    table containing the required values.
  - `partial`: object is relevant but incomplete, such as one metric from a
    multi-metric facet or contextual caveat.
  - `false`: wrong company, wrong segment, wrong metric, wrong period, or
    lexical overlap without evidence value.

## Outputs

- Labeled JSONL:
  `eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates_codex_labeled.jsonl`
- Labeled CSV:
  `reports/retrieval_eval/sec_tech_10k_object_review_candidates_codex_labeled.csv`
- Rule verifier vs Codex-label report:
  `reports/retrieval_eval/sec_tech_10k_object_rule_verifier_codex_label_eval.json`
- Lexical selected@5 vs Codex-label report:
  `reports/retrieval_eval/sec_tech_10k_object_bm25_selected5_codex_label_eval.json`

## Results

- Labeled rows: 575
- Label counts:
  - direct: 100
  - partial: 193
  - false: 282

Rule verifier against Codex labels:

- Candidate relevant facet coverage: 1.0
- Candidate direct facet coverage: 1.0
- Selected relevant facet coverage: 1.0
- Selected direct facet coverage: 1.0
- Candidate object precision, relevant: 0.5096
- Selected object precision, relevant: 0.9294
- Selected object precision, direct: 0.6353
- Selected objects: 85
- Selected labels: direct 54, partial 25, false 6

Lexical selected@5 against Codex labels:

- Selected relevant facet coverage: 0.9565
- Selected direct facet coverage: 0.9565
- Selected object precision, relevant: 0.7739
- Selected object precision, direct: 0.4435
- Selected objects: 115
- Selected labels: direct 51, partial 38, false 26

Interpretation:

- The model-assisted labels make the earlier issue visible: top lexical hits
  can keep many useful rows but select too many false positives.
- The rule verifier is not a final semantic verifier, but it is a materially
  better prefilter than lexical selected@5 on this first-pass label set.

## Experiment Governance

- Hypothesis: explicit object labels will make verifier precision and false
  positive analysis more meaningful than the auto-mapped target refs alone.
- Decision target: label all current review candidates and compare rule
  verifier against lexical selected@5 under the same label protocol.
- Ceiling / upper bound: labels are model-assisted, not user-reviewed; this can
  guide engineering but should not be the final benchmark for model claims.
- Baselines to beat: lexical selected@5 on the same candidate pool.
- Split and leakage guard: diagnostic-only; no train/test split. The labels use
  query/facet criteria and current candidate rows only.
- Stop conditions: if labels are too noisy or incomplete, do not train verifier
  LoRA; review or revise the label protocol first.
- Efficiency gate: local CPU labeling and evaluation should complete quickly.
- Decision label: proceed
- Mainline decision: use this as first-pass reviewed data for reranker/small
  verifier prototyping, while preserving the need for user spot-check.

## Runtime Efficiency

- Wall time:
  - compile check: under 1 second
  - label export: about 2.4 seconds
  - each label evaluation: under 1 second
- CPU/RAM/GPU utilization: CPU-only; GPU not used.
- Throughput: adequate for the current 575-row label set.
- Bottleneck diagnosis:
  no runtime bottleneck at this scale.
- Efficiency improvement:
  for 200-500 high-quality final verifier samples, keep this script as a
  bootstrap and let user review focus on boundary cases and false positives.
- Serving latency implication:
  none directly; labels are offline training/evaluation artifacts.

## Caveats And Next Step

- Not run: no semantic reranker, small verifier model, LoRA, or synthesis.
- Known risks:
  this is Codex model-assisted labeling, not independent human annotation.
- Reproduce:
  rerun the commands in `Code And Command`.
- Next decision:
  sample-check labeled false positives and train/evaluate a semantic reranker
  or 0.8B/1.5B verifier only after accepting the label protocol.
