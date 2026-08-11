# Model Run: 20260720_fin_ia_0_1_s2_t03_v2_contract_live_validation_r1

## Summary

- Purpose: validate the repaired specialist+lead v2 output contract on one bounded NVDA demand-signal Cell.
- Status: `terminal_failed_first_stage_outer_schema / no_automatic_rerun`.
- Run type: inference / bounded live validation.
- Timestamp: 2026-07-20.
- Environment: local isolated canonical runtime root.

## Code And Command

- Entry point: `scripts/releases/run_fin_ia_0_1_s2_t03_bounded_agent_first_run.py`.
- Runtime root: `.codex_runtime/fin01-s2-t03-v2-live-validation-r1`.
- Admission: `configs/releases/fin_ia_0_1_s2_t03_bounded_agent_exact_admission_v2_0.json`.
- WorkUnit idempotency key: `fin01-s2-t03-bounded-agent-work-unit-v2-contract-r1`.
- Git state: branch `codex/layered-data-source-expansion`, staged FIN 0.1 release slice, no unstaged or untracked repository files before admission preparation.

## Inputs

- Case: `case_87682fa72e72d7d042dabba0:v1`.
- As-of: `2026-07-20T00:00:00Z`.
- Program Cell: `demand_authenticity_and_sustainability` / `demand_signal`.
- Candidate boundary: 3 repo-local SEC official candidates; Candidate is not promoted Evidence.
- Input digest: `ce6f5758ecb1e3f5d18d50028cf23214e2c1628ed00a99038c7a8bb5cec228ea`.
- Source network and external tools: disabled.
- Prepared-input observation: model/provider/network/external-tool calls all 0.

## Model And Budget

- Provider/model: `deepseek/deepseek-v4-pro`.
- Output contract: `fin01.bounded_agent.specialist_lead_output:v2`.
- Semantic/provider/network calls: at most 3/3/3.
- Transport attempts per call: 1; retry budget: 0.
- Stage output caps: specialist 1600, writer 1000, verifier 900 tokens.
- Total estimated cost cap: USD 0.05.
- Credential handling: environment-variable presence only; value must not be read, printed or persisted.

## Experiment Governance

- Hypothesis: the v2 concrete JSON example plus strict local validation removes the earliest owned first-stage prompt/validator mismatch while retaining evidence boundaries.
- Decision target: one terminal canonical Run with either exact artifacts or a typed earliest failure with safe receipts.
- Baseline: historical v1 Run terminal failed, 0 Artifact, exact call count not reconstructable.
- Stop conditions: any provider/transport/JSON/schema/budget/integrity failure; no automatic retry or fallback.
- Decision label: `proceed_once_after_scoped_preflight`.
- Downstream boundary: success does not authorize T04, S3, release or production.

## Outputs And Results

- Prepared input: `.codex_runtime/fin01-s2-t03-v2-live-validation-r1/prepared_input.json`.
- Project OS preflight: `pass`, scope=`S2_T03_v2_bounded_live_validation`, no blocker override.
- Exact zero-call preflight: `pass_no_model_call`; admission digest=`03cf4bfaaa0148f585003b030ae1efa9604cc308a90eea2fe369a7fe3a9136ea`; credential present but value not persisted; output-only cost ceiling USD 0.003045.
- Canonical cardinality: 1 WorkUnit (`wu_p02_5_5ab54cb4e6cf262915768e6b`) / 1 Attempt (`attempt_fin01_c058cc2c206c715aa933bd8b`) / 1 failed ResearchRun (`research_run_fin01_9239b033666398bd8dece2a5`) / 0 Artifact.
- Terminal reason: `bounded_agent_profile_error:BoundedAgentExecutionError:bounded_specialist_and_lead:contract_validation_failed`.
- Typed failure: `bounded_agent_specialist_outer_schema_invalid` (historical code emitted before the post-run missing/extra split repair).
- Observed counts: model/provider/network=1/1/1; source network=0; external tool=0; fallback=0; automatic rerun=0.
- Receipt: input=1010 tokens, output=1512, total=2522, finish reason=`stop`, transport attempts=1, latency=18212 ms, estimated cost USD 0.00175479.
- Raw provider response/private reasoning persisted: false/false.
- Research-quality assessment: none; no Artifact was produced, so material gain versus deterministic baseline cannot be assessed.

## Caveats And Next Step

- A separate provider-health probe is not admitted because it would add a fourth paid/network call; the first admitted semantic call is also the fail-closed connectivity check.
- Evidence-operator execution is not applicable: the exact input contains frozen repo-local candidates and source network/external tools remain prohibited.
- The admitted v2 validation was consumed and cannot be repeated. Because post-run deterministic repair changes contract semantics, it is versioned separately as `fin01.bounded_agent.specialist_lead_output:v3`; v1/v2 are rejected before provider access. v3 supports lossless `output_contract_ref + result/output/data` flattening and future secret-safe key-shape telemetry, but the exact historical response shape cannot be reconstructed because raw content was intentionally not persisted.
- Any second live validation requires explicit user direction and a new exact v3 admission; T04/S3 remain blocked.
