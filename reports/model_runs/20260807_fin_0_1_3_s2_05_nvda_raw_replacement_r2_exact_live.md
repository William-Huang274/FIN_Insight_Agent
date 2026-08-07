# Model Run: 20260807_NVDA_S2_05_same_evidence_raw_replacement_r2

## Summary

- Purpose: re-prove the repaired NVDA numeric-scale boundary and complete the third frozen same-evidence raw measurement.
- Status: `raw chain complete / research quality fail / no retry / no promotion`.
- Run type: inference plus zero-call three-case evaluator replay.
- Timestamp: 2026-08-07 02:35:17Z.
- Environment: local Windows workspace; network used only by the ten authorized DeepSeek calls.

## Code And Command

- Execution commit: `a5f0adf95ce75b5fd78e35ba3e1751de84645add`.
- Entry point: `scripts/releases/run_fin_ia_0_1_3_s2_05_experiment_a.py`.
- Policy: `configs/runtime/fin_ia_0_1_3_s2_05_experiment_a_runtime_policy_v1_0.json`.
- Provider/model: DeepSeek / `deepseek-v4-pro`, temperature 0, thinking disabled.
- Admission: one Git-ignored R2 admission, exact-once consumed.

## Inputs

- Case: NVDA, as-of 2026-08-06.
- Frozen case digest: `45422727...81c5`.
- Input surface: 13 Evidence, 3 derived Numeric and 4 explicit gaps.
- Tools/search: none. DELL/MU raw, correction, supervisor prompt and hidden Gold were not visible.

## Outputs And Efficiency

- Completed nodes: Lead, six Specialists, Synthesis, Writer and Verifier.
- Calls/captures: `10/10`, all gateway=`ok`, finish reason=`stop`.
- Tokens: `31,947 input / 6,649 output / 38,596 total`.
- Estimated policy-rate cost: USD `0.0304715`; summed Provider latency=`163,606 ms`.
- Retry/fallback/supervisor/business promotion: `0/0/0/0`.
- Terminal: `terminal_completed_layered_raw_evaluation / case_complete / experiment_a_layered_raw_candidate_with_material_findings`.
- R1 numeric-scale false positive did not recur.

## Research Quality

Execution-time evaluator v1.3 returned `5 L1 / 2 L2 / 27 L3`. Post-run audit found two cash-flow/P-E co-occurrence false positives plus one derived Verifier semantic false positive, while also finding a real Writer citation-role defect that v1.3 missed. Evaluator v1.4 therefore performs path-aware bridge detection and complete case-local ID-role checks.

Final immutable NVDA replay is `4 L1 / 1 L2 / 27 L3`:

- three material numeric-role violations: hypothetical `$5B/$2B` thresholds escaped the permitted WWC surface into Specialist/Synthesis analysis;
- one Writer citation-role failure: Gap IDs were placed in `evidence_ids`;
- one Verifier false-green: it accepted the raw candidate with zero findings;
- six Specialists supplied no explicit counterevidence IDs;
- twenty-one hypothetical threshold surfaces remained uncalibrated.

## Three-Case Campaign

Evaluator v1.4 replay, with raw mutations=`0`:

- DELL=`3 L1 / 1 L2 / 23 L3`;
- MU=`8 L1 / 2 L2 / 14 L3`;
- NVDA=`4 L1 / 1 L2 / 27 L3`.

All three raw chains are complete and all three fail the research-quality gate. Three deterministic supervision boundaries were materialized, but no supervisor model call or corrected candidate exists.

## Caveats And Next Step

- Formal hidden score remains unavailable because L1/L2 did not pass.
- This same-evidence experiment does not prove Agentic Search, current-source truth or product report quality.
- No R3 is authorized.
- Next decision: separately authorize or reject one unified three-case supervisor experiment; do not patch or rerun each raw case.
