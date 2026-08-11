# Model Run: 20260722 FIN 0.1 S3-T09 DeepSeek three-cell output-v2 live validation r1

## Summary

- Purpose: consume the separately issued output-v2 replacement admission exactly once and determine terminal/runtime/artifact truth.
- Status: terminal succeeded; S3-T09 final acceptance remains pending paired baseline and owner review.
- Run type: bounded paid inference.
- Environment: local Windows workspace, branch `codex/layered-data-source-expansion`, dirty/staged FIN 0.1 release slice.

## Code And Command

- Entry point: `scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py`
- Admission: `configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_segmented_output_v2_exact_admission_v1_0.json`
- Issuance: `configs/releases/fin_ia_0_1_s3_t09_replacement_exact_admission_issuance_v1_0.json`
- Command: set `LLM_GATEWAY_TRANSPORT_RETRIES=0`, then run `execute --issuance <issuance-ref>`.
- Provider/model: DeepSeek / `deepseek-v4-pro`.
- Random seed: not applicable; provider inference.

## Inputs And Boundaries

- Case: `case_ac6fce120bf27977a1b45832:v1`, as-of `2026-07-21T00:00:00Z`.
- Input digest: `80822c5ff99e529e3de0aed73f0d3782819e987732473b7f48f6e08d593364fb`.
- Three Cell scope: demand authenticity/durability, value/profit capture, bottleneck/counterevidence/WWC.
- Source network, external tool, live Case head write: disabled.
- Retry/fallback/rerun: 0/0/0.
- Maximum calls: 6 semantic / 6 provider / 6 network; maximum total cost USD 0.10.

## Results

- Canonical state: WorkUnit/Attempt/ResearchRun all `succeeded`; no orphan.
- Artifacts/events: 9 canonical Artifact types, 23 Run events.
- Calls: 6 model / 6 provider / 6 network.
- Tokens: 14,833 input + 2,850 output = 17,683 total.
- Estimated cost: USD 0.00893187.
- Wall time observed by execution command: about 81.8 seconds; summed provider latency 46.887 seconds.
- Specialist stage latencies: 6.820s / 9.437s / 5.983s; Lead 10.686s; Writer 10.838s; Verifier 3.123s.
- All calls returned `finish_reason=stop` with exactly one transport attempt.

## Artifact And Research-Quality Audit

- Three Specialist receipts bind the exact model-view v1 digests frozen by the issuance decision.
- Terminal classes: demand=`typed_cannot_infer`; value=`value_capture_unattributed`; bottleneck=`typed_gap_source_followup_required`.
- One company-total numeric fact row is retained; no segment/product allocation is invented.
- Machine verifier decision is `accept_for_internal_review`; deterministic integrity, semantic fidelity, financial coherence and visual delivery all pass.
- No live Evidence head was promoted; no new source, new metric beyond the frozen numeric pack, or investment Alpha was produced.
- `agent_fallback_comparison` remains `pending_distinct_terminal_deterministic_run`; owner review is `not_performed`. Therefore this run proves the output-v2 live path and artifacts, not final T09 acceptance or T10 readiness.

## Governance And Safety

- Decision label: live execution pass; T09 acceptance pending.
- No automatic retry, fallback or rerun was performed.
- Raw provider response, private chain of thought and credential value were not persisted.
- Reuse must fail before Provider execution because the exact WorkUnit/Attempt/Run identity is now consumed.
- Next decision: read-only exact artifact validation and paired-baseline disposition; do not enter T10 automatically.
