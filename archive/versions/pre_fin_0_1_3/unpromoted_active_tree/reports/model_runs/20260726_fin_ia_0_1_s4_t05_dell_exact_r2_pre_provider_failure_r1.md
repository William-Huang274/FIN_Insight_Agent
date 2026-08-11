# Model Run: 20260726_FIN01_S4_T05_DELL_exact_R2_pre_provider_failure_r1

## Summary

- Purpose: DELL source-grounded three-Cell exact R2 execution
- Status: terminal failed before model/Provider invocation
- Run type: inference admission consumed, inference not started
- Timestamp: 2026-07-26
- Environment: local Windows, supervision-v2

## Code And Command

- Entry point: `scripts/releases/supervise_fin_ia_0_1_s3_t09_exact_live_execution.py`
- Admission: `fin01-s4-t04-dell-fresh-exact-admission-r1`
- Admission digest: `da035e71d9eee81e9c76c5243a396bafaacfc29cd1f01e66eb1a66b8b757a60f`
- ResearchRun: `research_run_fin01_2eced17671df87082b95db9a`
- Retry/fallback/replay/relaunch/rerun: `0/0/0/0/0`

## Inputs

- Case: DELL / `case_7b5c2042bef3825b8df71a96:v1`
- As-of: `2026-07-26T00:00:00Z`
- Input digest: `3499c03470c5bec5168dc87a2974802869da389f2ef588f41021731828d09e96`
- Source boundary: frozen issuer-bound Evidence/Numeric, context-only Graph, typed gaps
- Source/tool/live Case writes: forbidden

## Results

- Terminal states: `failed / failed / failed`
- Failure: `EvidenceServiceError / s3_required_evidence_role_slot_missing`
- Model/provider/network calls: `0/0/0`
- Input/output tokens: `0/0`
- Cost: `USD 0`
- Artifacts: `0`
- Orphan: `false`
- Paired assessment: not performed

## Experiment Governance

- Decision label: `stop`
- Mainline decision: DELL R2 not proven
- Root cause: `RC-P36-058`, project-owned evidence-role taxonomy to runtime-plan bridge gap
- Stop condition satisfied: first credible pre-Provider failure

## Runtime Efficiency

- Provider latency: not applicable
- Token throughput: not applicable
- Bottleneck: deterministic contract composition before adapter execution
- Serving implication: no serving claim; repair actual planning/preflight parity first

## Caveats And Next Step

- The consumed Run is immutable.
- No model output exists; this result says nothing about DeepSeek DELL research quality.
- Next: separately authorized zero-call root-cause disposition; no replacement admission or second execution is authorized.
