# Model Run: 20260516_phase2_object_bm25_candidate_eval

## Summary

- Purpose: Build a BM25 index over structured evidence objects and test
  whether object-level targets can enter the candidate pool before reranker or
  verifier work.
- Status: completed
- Run type: retrieval evaluation
- Timestamp: 2026-05-16
- Environment: local Windows workspace, CPU

## Code And Command

- Entry points:
  - `scripts/build_object_bm25_index.py`
  - `scripts/evaluate_object_retrieval.py`
  - `scripts/evaluate_object_gold_coverage.py`
- Commands:

```powershell
python scripts\build_object_bm25_index.py
python scripts\evaluate_object_retrieval.py --top-k 25 --variant-top-k 25 --predictions-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_predictions.jsonl --report-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_eval.json
python scripts\evaluate_object_gold_coverage.py --predictions-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_predictions.jsonl
python scripts\evaluate_object_retrieval.py --top-k 25 --variant-top-k 25 --selected-top-n 5 --predictions-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_selected5_predictions.jsonl --report-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_selected5_eval.json
python scripts\evaluate_object_gold_coverage.py --predictions-path reports\retrieval_eval\sec_tech_10k_object_bm25_variant_selected5_predictions.jsonl
```

- Config: default structured object paths and object gold draft.
- Git commit / dirty files: working tree dirty; new Phase 2 scripts and docs
  are not yet committed.
- Seeds: none.

## Inputs

- Structured object directory:
  `data/processed_private/structured_objects`
- Object gold draft:
  `eval_sets/sec_tech_10k_agent_reasoning_eval_v2_object_draft.jsonl`
- Label protocol:
  `draft_auto_mapped_needs_human_review`
- Candidate boundary:
  structured objects from current SEC tech 10-K corpus.
- Row/object counts:
  70,130 total objects: 2,187 tables, 44,345 metrics, 23,598 claims.

## Model Parameters

- Model: BM25Okapi over structured object search text.
- Retrieval:
  - per-facet query variants
  - RRF-style fusion over variants
  - `top_k=25`
  - `variant_top_k=25`
- Filters:
  - ticker from query row
  - fiscal year from query row

## Outputs

- Object BM25 index:
  `data/indexes/bm25/sec_tech_10k_objects`
- Predictions:
  `reports/retrieval_eval/sec_tech_10k_object_bm25_variant_predictions.jsonl`
- Metrics:
  `reports/retrieval_eval/sec_tech_10k_object_bm25_variant_eval.json`
- Lexical selected@5 metrics:
  `reports/retrieval_eval/sec_tech_10k_object_bm25_variant_selected5_eval.json`

## Results

- Query count: 6
- Facet count: 23
- Candidate facet coverage: 1.0
- Selected facet coverage: 0.0
- Cited facet coverage: 0.0
- Lexical selected@5 selected facet coverage: 0.9565
- Lexical selected@5 selected object precision: 0.4174
- Lexical selected@5 selected target objects: 48 / 115 selected objects
- Baseline comparison:
  - Single long facet query at top-25 hit 22/23 facets.
  - Variant-fused facet retrieval at top-25 hit 23/23 facets.
- Interpretation:
  candidate generation is sufficient for the current draft gold set; the next
  bottleneck is precision-oriented selection and verification. The selected@5
  lexical baseline keeps almost all facets covered but admits substantial
  noise.

## Experiment Governance

- Hypothesis: structured objects plus facet-specific query variants should
  improve target-in-candidate coverage versus raw chunk retrieval for
  multi-facet finance questions.
- Decision target: 6-query object draft, 23 facets, target object in top-25
  candidate pool.
- Ceiling / upper bound: current gold is auto-mapped and must be human-reviewed;
  this run can validate candidate plumbing but not final answer quality.
- Baselines to beat: single-query object BM25 candidate retrieval at 22/23
  facet coverage.
- Split and leakage guard: diagnostic-only on the current model-authored
  reviewed-style eval set; no train/test split claim.
- Stop conditions: if target objects could not enter candidates, fix object
  extraction or retrieval before verifier work.
- Efficiency gate: local CPU run should complete in minutes.
- Decision label: proceed
- Mainline decision: proceed to reranker/small verifier only after human review
  of object target labels.

## Runtime Efficiency

- Wall time:
  - object index build: about 11 seconds
  - variant retrieval/evaluation: about 77 seconds
  - selected@5 variant retrieval/evaluation: about 51 seconds
- CPU/RAM/GPU utilization: CPU-only; GPU not used.
- Throughput: adequate for offline eval; not yet optimized for serving.
- Bottleneck diagnosis:
  Python loops and repeated BM25 scoring per query variant dominate.
- Efficiency improvement:
  cache per-variant scores or keep an in-process retrieval service when running
  larger eval sets.
- Serving latency implication:
  current script is offline-only; serving path should batch/fuse queries in
  process and avoid reloading the index.

## Caveats And Next Step

- Not run: no dense object retrieval, reranker, verifier model, synthesis, or
  LoRA training.
- Known risks:
  object gold labels are auto-mapped and may over-include partial objects.
- Reproduce:
  rerun the commands in `Code And Command`.
- Next decision:
  review target object refs as `direct`, `partial`, or `false`, then evaluate
  a reranker or small verifier on candidate-to-selected coverage.
