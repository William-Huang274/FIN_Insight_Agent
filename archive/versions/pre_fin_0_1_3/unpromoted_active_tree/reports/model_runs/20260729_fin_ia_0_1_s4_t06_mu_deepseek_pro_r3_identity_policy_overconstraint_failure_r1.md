# Model Run: 20260729_fin_ia_0_1_s4_t06_mu_deepseek_pro_r3_identity_policy_overconstraint_failure_r1

## Summary

- Purpose: reprove the mandatory material-truth and identity safety closure on the exact MU input.
- Status: terminal failed at the first Specialist segment; no retry and no paired assessment.
- Run type: exact-live inference.
- Timestamp: 2026-07-29.
- Environment: local Windows canonical runtime with supervision-v2.

## Code And Command

- Entry point: `scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py`
- Supervisor: `scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py`
- Admission: `configs/releases/fin_ia_0_1_s4_t06_mu_mandatory_material_truth_identity_safety_closure_fresh_exact_admission_r3.json`
- Admission digest: `da4c91eb69499ab197332e2f263556f5528b66e451c33be54e925b20924632a5`
- Git state: dirty shared release worktree; no commit or staging performed in this run.
- Retry/fallback/relaunch/rerun: `0/0/0/0`.

## Inputs

- Case: MU, version 1.
- Exact input digest: `7887b5bb447fc6a844c410751f2038a04a1c0b04dbbe7e5bde41b040135a12e1`.
- Preparation digest: `9724bf1c2bb201e409400748ee49aefa60dcf0a613f25a84e7225b967adc6b73`.
- Research profile: `fin01.s4.research_profile.mu_hbm_three_cell:v1`.
- Safety profile: `fin01.s4.case_runtime_mandatory_material_truth_and_identity_safety_closure:v1`.
- Provider/model: DeepSeek / `deepseek-v4-pro`.

## Outputs

- Canonical WorkUnit/Attempt/Run: `failed/failed/failed`.
- Artifact count: `0`.
- Usage receipts / restricted captures / readbacks: `1/1/1`.
- Runtime result: `.codex_runtime/fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1/s4_t06_mu_mandatory_safety_closure_r3_live_execution_result.json`.
- Durable failure summary: `configs/releases/fin_ia_0_1_s4_t06_mu_mandatory_material_truth_identity_safety_closure_r3_exact_live_execution_failure_result_v1_0.json`.

## Results

- Calls: `1 model / 1 provider / 1 network`.
- Tokens: `3,994 input / 494 output / 4,488 total`.
- Estimated cost: `USD 0.00216717`.
- Provider result: `status=ok`, `finish_reason=stop`, one transport attempt.
- First failure: `s4_case_delivery_identity_provider_narrative_invalid`.
- Failure subtype: `provider_authored_case_entity_token`.
- Lifecycle phase: `node_envelope_accounting`.

Restricted content-free inspection found four occurrences of the correct current-case token `MU` and zero occurrences of `DELL` or `NVDA`. The output therefore did not exhibit cross-case identity contamination. The local policy rejected the correct identity because it bans every known ticker token, including the current case.

## Experiment Governance

- Hypothesis: mandatory safety binding will preserve the exact MU input and permit a coherent 12-call/9-Artifact chain while rejecting wrong numeric or cross-case identity content.
- Decision target: terminal success, 12 receipts/captures, 9 Artifacts, independent L1 pass and retained Agent analytical gain.
- Stop condition: any new L1 failure stops the sequence without retry, patch, R4, paired assessment or owner acceptance.
- Decision label: `stop`.
- Mainline decision: S4-T06 remains blocked; T07 is not entered.

## Runtime Efficiency

- Provider latency observed: 7,305 ms.
- Full-chain wall time was not reached because the first segment failed.
- Serving implication: the failure is contract-policy overconstraint, not provider latency or capacity.

## Caveats And Next Step

- Numeric rendering and final 9-Artifact L1 were not reached, so the live run does not prove or disprove those downstream protections.
- The model did repeat a correct ticker against a strict instruction, but the earliest controllable fault is the blanket identity-token ban and its fake-fixture blind spot.
- No raw assistant body, credential or private reasoning is stored in this ledger.
- Next decision: program-level scope replacement or blocking decision; no second runtime repair bundle is automatically allowed.
