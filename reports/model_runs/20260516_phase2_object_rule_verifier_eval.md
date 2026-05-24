# Model Run: 20260516_phase2_object_rule_verifier_eval

## Summary

- Purpose: Export object-level review candidates and test a deterministic
  direct/partial/false verifier baseline before moving to a semantic reranker or
  small verifier model.
- Status: completed
- Run type: verifier evaluation
- Timestamp: 2026-05-16
- Environment: local Windows workspace, CPU

## Code And Command

- Entry points:
  - `scripts/build_object_review_set.py`
  - `scripts/apply_object_rule_verifier.py`
  - `scripts/evaluate_object_gold_coverage.py`
- Commands:

```powershell
python -m py_compile src\eval\object_verifier.py scripts\build_object_review_set.py scripts\apply_object_rule_verifier.py scripts\evaluate_object_gold_coverage.py
python scripts\build_object_review_set.py
python scripts\apply_object_rule_verifier.py --output-path reports\retrieval_eval\sec_tech_10k_object_rule_verifier_predictions.jsonl
python scripts\evaluate_object_gold_coverage.py --predictions-path reports\retrieval_eval\sec_tech_10k_object_rule_verifier_predictions.jsonl --report-path reports\retrieval_eval\sec_tech_10k_object_rule_verifier_eval.json
```

- Config:
  - verifier label space: `direct | partial | false`
  - `max_selected_per_facet=5`
  - `max_partial_per_facet=1`
  - `min_partial_score=4.0`
- Git commit / dirty files: working tree dirty; Phase 2 scripts, docs, and
  reports are not yet committed.
- Seeds: none.

## Inputs

- Object gold draft:
  `eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_draft.jsonl`
- Candidate predictions:
  `reports/retrieval_eval/sec_tech_10k_object_bm25_variant_predictions.jsonl`
- Structured object directory:
  `data/processed_private/structured_objects`
- Label protocol:
  `draft_auto_mapped_needs_human_review`
- Candidate boundary:
  top-25 facet-level object candidates from variant-fused BM25.
- Row/object counts:
  575 candidate rows across 6 queries and 23 facets.

## Model Parameters

- Model: deterministic phrase/numeric verifier.
- Features:
  - exact phrase match after normalization,
  - numeric match with direct value and billion-to-million tolerance,
  - important-token overlap for partial evidence,
  - object type, provenance, BM25 rank, and preview exported for review.
- Selection:
  direct objects first by verifier score, then up to one high-score partial
  object, capped at five selected objects per facet.

## Outputs

- Review JSONL:
  `eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_review_candidates.jsonl`
- Review CSV:
  `reports/retrieval_eval/sec_tech_10k_object_review_candidates.csv`
- Verifier predictions:
  `reports/retrieval_eval/sec_tech_10k_object_rule_verifier_predictions.jsonl`
- Verifier metrics:
  `reports/retrieval_eval/sec_tech_10k_object_rule_verifier_eval.json`
- Ablation outputs:
  `reports/retrieval_eval/sec_tech_10k_object_rule_verifier_selected5_predictions.jsonl`,
  `reports/retrieval_eval/sec_tech_10k_object_rule_verifier_selected5_eval.json`,
  `reports/retrieval_eval/sec_tech_10k_object_rule_verifier_selected10_predictions.jsonl`,
  `reports/retrieval_eval/sec_tech_10k_object_rule_verifier_selected10_eval.json`

## Results

- Candidate facet coverage: 1.0
- Selected facet coverage: 1.0
- Cited facet coverage: 0.0
- Candidate object precision: 0.1948
- Selected object precision: 0.5412
- Selected objects: 85
- Selected target objects: 46
- Auto label counts over candidate review rows:
  - direct: 102
  - partial: 373
  - false: 100
- Baseline comparison:
  - lexical selected@5 selected facet coverage: 0.9565
  - lexical selected@5 selected object precision: 0.4174
  - rule verifier selected facet coverage: 1.0
  - rule verifier selected object precision: 0.5412
- Interpretation:
  the deterministic verifier is useful as a review/export and diagnostic
  baseline. It improves selected precision while preserving facet hit coverage,
  but it still relies on lexical matching and cannot replace a semantic
  reranker or small verifier model.

## Experiment Governance

- Hypothesis: structured objects plus direct/partial/false phrase and numeric
  checks should reduce obvious false positives versus selecting the top BM25
  candidates directly.
- Decision target: selected object precision and selected facet coverage on the
  6-query object draft.
- Ceiling / upper bound: current target refs are auto-mapped from evidence-level
  labels and can over-include partial objects. The run is diagnostic-only for
  final answer quality.
- Baselines to beat: lexical selected@5 from the object BM25 run.
- Split and leakage guard: diagnostic-only; no train/valid/test claim.
  `must_find` fields are used as task criteria and must not be confused with
  production planner output.
- Stop conditions: if selected facet coverage dropped below candidate coverage
  or precision failed to improve, do not promote this verifier baseline.
- Efficiency gate: local CPU run should finish in seconds to minutes.
- Decision label: proceed
- Mainline decision: proceed to human review and then semantic reranker/small
  verifier; do not train LoRA yet.

## Runtime Efficiency

- Wall time:
  - compile check: under 1 second
  - review set export: about 2.5 seconds
  - verifier prediction export: about 2.4 seconds
  - coverage evaluation: under 1 second
- CPU/RAM/GPU utilization: CPU-only; GPU not used.
- Throughput: adequate for current offline review set.
- Bottleneck diagnosis:
  negligible at this scale; semantic reranking will become the next bottleneck.
- Efficiency improvement:
  keep structured object maps loaded in process for larger review batches.
- Serving latency implication:
  this rule baseline can be used as a cheap prefilter, but serving decisions
  should use a batched semantic verifier once labels exist.

## Caveats And Next Step

- Not run: no transformer reranker, no 0.8B/1.5B verifier, no LoRA, no final
  synthesis.
- Known risks:
  the review rows and metrics are based on auto-mapped draft gold, so they are
  not final quality claims.
- Reproduce:
  rerun the commands in `Code And Command`.
- Next decision:
  review the CSV/JSONL labels, correct false target refs, then use those labels
  to evaluate a semantic reranker and small verifier.
