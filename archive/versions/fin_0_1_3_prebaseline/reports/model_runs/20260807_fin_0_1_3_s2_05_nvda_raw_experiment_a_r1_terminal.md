# Model Run: 20260807_NVDA_S2_05_same_evidence_raw_Experiment_A_r1

## Summary

- Purpose: measure DeepSeek Pro's autonomous NVDA reasoning on the frozen same-evidence pack.
- Status: `terminal failed at Lead / project numeric-scale false positive / no retry / no promotion`.
- Run type: inference plus zero-call root-cause replay.
- Timestamp: 2026-08-07 02:09:32Z.
- Environment: local Windows workspace; network used only by the single authorized Provider call.

## Code And Command

- Execution commit: `32b03a8d943a077ca5f0c9bdd3ce56d016c23b57`.
- Entry point: `scripts/releases/run_fin_ia_0_1_3_s2_05_experiment_a.py`.
- Policy: `configs/runtime/fin_ia_0_1_3_s2_05_experiment_a_runtime_policy_v1_0.json`.
- Provider/model: DeepSeek / `deepseek-v4-pro`, temperature 0, thinking disabled.
- Admission: one Git-ignored NVDA admission, exact-once consumed.

## Inputs

- Case: NVDA, as-of 2026-08-06.
- Frozen case digest: `45422727...81c5`.
- Input surface: 13 Evidence, 3 derived Numeric and 4 explicit gaps.
- Tools/search: none. DELL/MU raw, correction and hidden Gold were not visible.

## Outputs And Efficiency

- Completed nodes: Lead only; Specialists/Synthesis/Writer/Verifier were not called.
- Calls/captures: `1/1`, gateway=`ok`, finish reason=`stop`.
- Tokens: `3,603 input / 1,179 output / 4,782 total`.
- Estimated policy-rate cost: USD `0.0041661`; latency `20,551 ms`.
- Retry/fallback/supervisor/business promotion: `0/0/0/0`.
- Terminal: `terminal_failed_no_retry / lead_planning / experiment_a_unbound_numeric_surface`.

## Root Cause

The Lead rendered NVDA's approved market-cap authority `5359 USD_billion` as `$5.36T`. The frozen statement also expresses the value as approximately `5.359 trillion USD`. This is a legitimate unit conversion and two-decimal rounding, not an invented number.

The execution-time numeric compiler generated `5359B` but no equivalent trillion-scale forms, so it rejected `5.36T`. The project-owned compiler was repaired zero-call to generate exact, one-decimal and two-decimal trillion equivalents for USD-billion values at or above 1,000. The immutable captured Lead then replayed successfully. The original terminal remains failed and was not rewritten.

## Experiment Governance

- The first CLI invocation used an existing parent directory instead of a fresh run-specific root. It failed before root creation, ledger reservation or Provider activity and did not consume the admission.
- The corrected invocation consumed the admission once and made one Provider call.
- Raw chain complete: false; hidden score and formal research-quality score: unavailable.
- DELL/MU remain complete-quality-fail; NVDA remains incomplete due to the project gate false positive.
- No automatic replacement run is authorized.

## Caveats And Next Step

- The natural Lead looked case-specific and covered all mandatory families, but there is no downstream research output to evaluate.
- The repair proves only the deterministic numeric-scale contract and immutable Lead replay.
- Commit and push the zero-call repair, then make a separate NVDA replacement authority decision if completing the three-case raw campaign remains desired.
