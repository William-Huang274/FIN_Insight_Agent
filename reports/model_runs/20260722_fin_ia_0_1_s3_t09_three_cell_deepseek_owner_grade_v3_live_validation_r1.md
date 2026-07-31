# Model Run: 20260722 FIN 0.1 S3-T09 DeepSeek owner-grade output-v3 live validation r1

## Summary

- Purpose: consume the issued fresh output-v3 admission exactly once and test whether the fixture-proven owner-grade contract produces canonical live artifacts.
- Status: terminal failed at the first Specialist; admission consumed; no retry, fallback or rerun.
- Run type: bounded paid inference.
- Environment: local Windows workspace, branch `codex/layered-data-source-expansion`, staged FIN 0.1 program changes plus the current result closeout.

## Code And Command

- Entry point: `scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py`.
- Admission: `configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_exact_admission_v1_0.json`.
- Issuance: `configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_fresh_exact_admission_issuance_v1_0.json`.
- Command: set `LLM_GATEWAY_TRANSPORT_RETRIES=0`, then run `execute --issuance <issuance-ref> --output-prefix owner_grade_v3_live` exactly once.
- Provider/model: DeepSeek / `deepseek-v4-pro`.
- Random seed: not applicable; provider inference.

## Inputs And Boundaries

- Case: `case_ac6fce120bf27977a1b45832:v1`, as-of `2026-07-21T00:00:00Z`.
- Input digest: `dba3d25144edfd0f7411d638b964deba8bab70406fb33b3bfca7c16be6bcf06e`.
- Output contract: `fin01.s3.bounded_agent_three_cell_output:v3`.
- Fresh Run: `research_run_fin01_b939a453b921cb5bcf3c2edf`.
- Source network, external tool and live Case head write: disabled.
- Retry/fallback/rerun: `0/0/0`.
- Maximum calls: 6 semantic / 6 provider / 6 network; maximum total cost USD 0.10.

## Results

- Canonical state: WorkUnit/Attempt/ResearchRun all `failed`; no orphan.
- Artifacts/events: 0 Artifact, 7 Run events.
- Calls: 1 model / 1 provider / 1 network.
- Tokens: 2,916 input + 1,316 output = 4,232 total.
- Estimated cost: USD 0.00241338.
- Provider latency: 17.305 seconds; one transport attempt; `finish_reason=stop`.
- Failure stage: `domain_specialist:demand_authenticity_and_sustainability`.
- Failure code: `s3_bounded_specialist_output_schema_invalid:demand_authenticity_and_sustainability`.

The Provider returned a non-empty native JSON object and stopped normally, so this was not HTTP, JSON syntax, truncation or canonical terminalization failure. The local validator rejected the exact top-level Specialist schema or `program_cell_id` binding before any Artifact commit. Safe telemetry deliberately does not persist raw output and the current code coalesces those alternatives into one failure code, so missing keys, unexpected keys and cell-ID mismatch cannot be reconstructed honestly.

## Governance And Research Quality

- Exact execution and terminalization worked as designed; the admission is consumed and must not be reused.
- The fixture-proven output-v3 semantic repair is not live-proven because no Specialist output or downstream Artifact passed validation.
- No paired comparison, Human Review, T10, S4, release or production action occurred.
- No new Evidence, financial metric or Alpha was produced.
- The historical output-v2 runtime result was preserved under its original SHA256; the runner used prefixed files for this run.
- A post-terminal preflight reuse attempt was rejected with `s3_t09_exact_execution_identity_already_consumed`; gateway event lines stayed `16→16`, proving rejection before Provider execution.

Next action: a separately authorized zero-call root-cause and transport-contract decision. It must decide whether to add closed safe shape-subtype telemetry, change the Provider-side structured-output transport, or revise how the exact schema is conveyed; it must not reuse this admission or silently relax the local v3 validator.
