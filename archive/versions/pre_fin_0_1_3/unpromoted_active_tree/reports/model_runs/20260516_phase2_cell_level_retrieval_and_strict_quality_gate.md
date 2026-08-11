# Model Run: 20260516_phase2_cell_level_retrieval_and_strict_quality_gate

## Summary
- Purpose: Fix expanded v0.2 evidence coverage root causes before scaling samples.
- Status: completed diagnostic
- Run type: retrieval evaluation + structured extraction rebuild + quality gate
- Timestamp: 2026-05-16 Asia/Shanghai
- Environment: local Windows workspace, Python 3.10

## Code And Command
- Entry points:
  - `scripts/build_expanded_object_tasks.py`
  - `scripts/build_structured_objects.py`
  - `scripts/build_object_bm25_index.py`
  - `scripts/evaluate_object_retrieval.py`
  - `scripts/build_bge_evidence_pool.py`
  - `scripts/build_aspect_evidence_pool.py`
  - `scripts/apply_object_rule_verifier.py`
  - `scripts/export_calibrated_evidence_pool.py`
  - `scripts/score_synthesis_quality.py`
- Key commands:
  - `python scripts/build_structured_objects.py`
  - `python scripts/build_object_bm25_index.py`
  - `python scripts/evaluate_object_retrieval.py --gold-path eval_sets/sec_tech_10k_expanded_eval_v0_2_object_tasks.jsonl --top-k 15 --variant-top-k 15 --predictions-path reports/retrieval_eval/sec_tech_10k_expanded_v0_2_cell_bm25_predictions.jsonl --report-path reports/retrieval_eval/sec_tech_10k_expanded_v0_2_cell_bm25_eval.json`
  - `python scripts/score_synthesis_quality.py --output-path reports/quality/sec_tech_10k_expanded_v0_2_answer_quality_strict.json`
- Git commit: dirty workspace, no commit created.
- Seeds: not applicable.

## Inputs
- Evidence store: `data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl`
- Expanded eval set: `eval_sets/sec_tech_10k_expanded_eval_v0_2.jsonl`
- Prior synthesis for strict scoring: `reports/demo/qwen9b_expanded_v0_2_synthesis_demo.json`
- Prior citation validation: `reports/quality/sec_tech_10k_expanded_v0_2_citation_validation.json`
- Candidate boundary: structured objects from SEC 10-K evidence only.

## Outputs
- Cell-level object tasks: `eval_sets/sec_tech_10k_expanded_eval_v0_2_object_tasks.jsonl`
- Structured tables/metrics/claims: `data/processed_private/structured_objects/`
- BM25 index: `data/indexes/bm25/sec_tech_10k_objects/`
- Cell BM25 predictions: `reports/retrieval_eval/sec_tech_10k_expanded_v0_2_cell_bm25_predictions.jsonl`
- Cell BM25 evidence pool: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_bm25_evidence_pool.jsonl`
- Cell aspect pool: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_cell_bm25_aspect_evidence_pool.jsonl`
- Rule verifier smoke: `reports/retrieval_eval/sec_tech_10k_expanded_v0_2_cell_rule_verifier_predictions.jsonl`
- Multi-cite export over old Qwen verifier predictions: `reports/evidence_pool/sec_tech_10k_expanded_v0_2_calibrated_evidence_pool_multi_cite.jsonl`
- Strict quality gate: `reports/quality/sec_tech_10k_expanded_v0_2_answer_quality_strict.json`

## Results
- Structured rebuild: 2,187 tables, 41,939 metrics, 23,598 claims.
- BM25 object index: 67,724 records.
- Expanded tasks: 698 cell/aspect retrieval tasks, up from the old 168 aspect tasks.
- Cell BM25 evidence pool: 6,980 candidates; object counts were metric 5,339, claim 1,564, table 77.
- Rule verifier smoke: 698 facets, 2,003 selected objects, decision labels direct 8,946, partial 1,398, false 126.
- Old-pool multi-cite export: citation evidence increased from 143 to 387 and background evidence from 503 to 832, but old coarse verifier still had 25 missing aspects.
- Strict quality gate: 13/13 current synthesis outputs were `teacher_ready=false`; mean overall 0.5791; blockers included missing machine-readable cell JSON 7, citation/number warning 9, low required coverage 8, low citation use rate 5.

## Experiment Governance
- Hypothesis: Cell-level task decomposition and table cell extraction should prevent strong company/year/metric evidence from being lost before reranker/verifier.
- Decision target: Critical multi-company metrics such as `GOOGL/META x 2023/2024/2025 x total income from operations` must enter top candidates with correct period and unit.
- Ceiling / upper bound: This run only verifies BM25 candidate construction and strict scoring; it does not establish final semantic verifier precision.
- Baselines to beat: Old v0.2 pool had 168 aspects, 143 citation objects, 25 missing aspects, and single-citation-per-aspect squeeze.
- Split and leakage guard: No answer baseline was injected into retrieval or synthesis; prior synthesis was used only for strict post-hoc quality scoring.
- Stop conditions: Do not treat current synthesis as teacher data while cell JSON and numeric validator are missing.
- Efficiency gate: Local cell BM25 retrieval must finish in minutes, not hang on full-corpus scoring.
- Decision label: proceed to reranker/verifier rerun; current output remains diagnostic-only.
- Mainline decision: Upstream task and extraction contract accepted for the next cloud reranker/verifier run.

## Runtime Efficiency
- Structured rebuild: 16.6 seconds.
- BM25 index rebuild: 6.7 seconds.
- Initial cell BM25 attempt: timed out before retriever optimization.
- Optimized cell BM25 retrieval: 38-62 seconds on local CPU.
- Bottleneck diagnosis: Unoptimized BM25 called full-corpus `get_scores` per cell query; fixed by `get_batch_scores` over filtered ticker/year candidates plus filter cache.
- Serving implication: Cell-level retrieval is feasible as a batched offline step; online serving should keep ticker/year filters and avoid full-corpus scoring per subtask.

## Caveats And Next Step
- Not run: No BGE reranker, Qwen verifier, or Qwen9B synthesis was rerun on the new 698 cell tasks.
- Known risks: Rule verifier direct counts are a smoke signal only and are too permissive to be final precision evidence.
- Next decision: Run BGE/Qwen verifier on the new cell aspect pool, then require final synthesis to emit machine-readable cell JSON before numeric validation.
