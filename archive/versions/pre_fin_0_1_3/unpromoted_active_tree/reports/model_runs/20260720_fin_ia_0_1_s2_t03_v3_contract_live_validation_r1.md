# Model Run: 20260720_fin_ia_0_1_s2_t03_v3_contract_live_validation_r1

## Summary

- Purpose: validate the v3 specialist+lead output-shape contract on one bounded NVDA demand-signal Cell.
- Status: `terminal_failed_first_stage_unexpected_outer_keys / no_automatic_rerun`.
- Run type: inference / bounded live validation.
- Timestamp: 2026-07-20.
- Environment: local isolated canonical runtime root.

## Exact Identity And Input

- Runtime root: `.codex_runtime/fin01-s2-t03-v3-live-validation-r1`.
- Admission: `configs/releases/fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v3_0.json`.
- Admission ID: `fin01-s2-t03-bounded-agent-v3-contract-live-validation-r1`.
- WorkUnit idempotency key: `fin01-s2-t03-bounded-agent-work-unit-v3-contract-r1`.
- Case: `case_87682fa72e72d7d042dabba0:v1`.
- As-of: `2026-07-20T00:00:00Z`.
- Candidate boundary: 3 repo-local SEC official candidates; Candidate is not promoted Evidence.
- Input digest: `ce6f5758ecb1e3f5d18d50028cf23214e2c1628ed00a99038c7a8bb5cec228ea`.
- Prepared-input observation: model/provider/network/external-tool calls all 0.

## Model, Budget, And Boundaries

- Provider/model: `deepseek/deepseek-v4-pro`.
- Output contract: `fin01.bounded_agent.specialist_lead_output:v3`.
- Semantic/provider/network calls: at most 3/3/3.
- Transport attempts per call: 1; retry budget: 0.
- Stage output caps: specialist 1600, writer 1000, verifier 900 tokens.
- Total estimated cost cap: USD 0.05.
- Source network, external tools and live business Case head writes: disabled.
- Credential handling: presence only; value must not be printed or persisted.

## Governance And Stop Rule

- Historical v1 and v2 admissions and WorkUnit identities are consumed and may not be reused.
- Execution may start only after deterministic regression, Project OS scoped preflight and exact zero-call preflight pass.
- Execute at most once. Stop on success or the earliest typed failure; no retry, fallback or provider-health probe.
- This validation does not authorize T04, S3, release or production.

## Pre-run Verification

- Isolated prepare: `prepared_no_model_call`; exact digest match; candidate count=3.
- T02/T03 deterministic contract regression: `18 passed in 28.96s`.
- Project OS scoped preflight: `pass`, scope=`S2_T03_v3_bounded_live_validation`, no blocker override.
- Exact zero-call preflight: `pass_no_model_call`; admission digest=`8e058866434b8fe8e276af6deb59df9d11010a01aa869e6ca072f8554473f710`; credential present but value not persisted; output-only cost ceiling USD 0.003045.
- Live execution consumed: true; no retry or rerun occurred.

## Outputs And Results

- Canonical cardinality: 1 WorkUnit (`wu_p02_5_5ab54cb4e6cf262915768e6b`) / 1 Attempt (`attempt_fin01_c058cc2c206c715aa933bd8b`) / 1 failed ResearchRun (`research_run_fin01_9239b033666398bd8dece2a5`) / 0 Artifact.
- The admission and idempotency key were distinct from v1/v2. The canonical logical IDs repeat because the current isolated runtime derives them from identical Case/input content; the stores are separate, but this is a lineage ambiguity to resolve before a shared-store validation.
- Terminal reason: `bounded_agent_profile_error:BoundedAgentExecutionError:bounded_specialist_and_lead:contract_validation_failed`.
- Typed failure: `bounded_agent_specialist_outer_keys_unexpected`.
- Output shape: all three required keys were present with expected types; missing keys=0; total outer keys=8; unexpected keys=5; unknown-key digest=`774c9c26f3dc06b8cb832afa196f0c25041000ebee79efac58140b16c2e6b557`.
- Observed counts: model/provider/network=1/1/1; source network=0; external tool=0; fallback=0; automatic rerun=0.
- Receipt: input=1010 tokens, output=1508, total=2518, finish reason=`stop`, transport attempts=1, latency=19175 ms, estimated cost USD 0.00175131.
- Raw provider response, unknown key names and private reasoning persisted: false.
- Research-quality assessment: none; no Artifact was produced, so material gain versus deterministic baseline cannot be assessed.

## Disposition

- v3 shape telemetry worked as designed and narrowed the failure from generic outer-schema mismatch to five additional top-level keys.
- v3 did not make T03 pass: the current contract forbids silently dropping unknown keys, so execution stopped before Writer and Verifier.
- The exact v3 admission and WorkUnit key are consumed and now rejected before provider access. No further execution, T04, S3, release or production is authorized.
- Post-run verification: focused T02/T03=`19 passed`; related S1/S2/Workbench regression=`43 passed in 47.49s`.
