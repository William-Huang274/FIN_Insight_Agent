# Model Run: 20260722 FIN 0.1 S3-T09 DeepSeek owner-grade v3 segmented live validation r1

## Summary

- Purpose: consume the issued fresh segmented output-v3 admission exactly once and test live Provider conformance plus canonical Artifact production.
- Status: terminal failed at the first Specialist segment; admission consumed; no retry, fallback, repair or rerun.
- Run type: bounded paid inference.
- Environment: local Windows workspace, branch `codex/layered-data-source-expansion`; the repository already contained the staged FIN 0.1 program slice and no unstaged or untracked files before this closeout began.

## Code And Command

- Entry point: `scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py`.
- Admission: `configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_segmented_exact_admission_v1_0.json`.
- Issuance: `configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_fresh_exact_admission_issuance_v1_0.json`.
- Preflight: set `LLM_GATEWAY_TRANSPORT_RETRIES=0`; run Project OS scoped preflight and runner `preflight` with output prefix `owner_grade_v3_segmented_live`.
- Execution: with the same retry-zero environment, run `execute` with that issuance and prefix exactly once.
- Provider/model: DeepSeek / `deepseek-v4-pro`.
- Random seed: not applicable; Provider inference.

## Inputs And Budgets

- Case: `case_ac6fce120bf27977a1b45832:v1`, as-of `2026-07-21T00:00:00Z`.
- WorkUnit/Attempt/Run: `wu_p02_5_188c135034fd8ab3a921ba08` / `attempt_fin01_753df78d2dd4eed1940beb09` / `research_run_fin01_613dad1d30f9ce5357213b21`.
- Input digest: `41179ecdca0853e0e4d1a49af6ada129cb5bfae5913891b0a184eb900a60dd05`.
- Preparation digest: `80f3ed8d0b0cbc69ca80f73e3af9befecfa52041f10323fb59169c8973c34028`.
- Transport/output: `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v1` / `fin01.s3.bounded_agent_three_cell_output:v3`.
- Maximum semantic/provider/network calls: `12/12/12`; Specialist segment output caps `1600/1200/1400`; aggregate maximum output tokens 16,200; maximum total cost USD 0.10.
- Retry/fallback/repair/rerun: `0/0/0/0`.
- Source network, external tools and live business Case head writes: disabled.

## Result

- Canonical state: WorkUnit/Attempt/ResearchRun all `failed`; no orphan.
- Artifacts/events: 0 Artifact, 7 events.
- Calls: 1 model / 1 Provider / 1 network; one transport attempt.
- Tokens: 2,582 input + 294 output = 2,876 total.
- Estimated cost: USD 0.00137895.
- Provider latency: 6.287 seconds; `finish_reason=stop`.
- Failed stage: `domain_specialist:demand_authenticity_and_sustainability:facts_explanation_and_terminal`.
- Failure code: `s3_bounded_segmented_specialist_contract_invalid:demand_authenticity_and_sustainability:facts_explanation_and_terminal:s3_bounded_specialist_output_text_length_invalid:demand_authenticity_and_sustainability:explanation_layer`.
- Runtime result SHA256: `32b2696eb0cf764b0e0e28f2e42f90386a57ffbaf4cc2e96e9f4834be9fc88ed`.

The Provider request and native JSON parse succeeded. Exact segment keys and Cell binding passed, and `explanation_layer` passed list/cardinality validation. At least one item failed the combined local requirement of being a nonblank string no longer than 320 Unicode characters. Because raw output and item lengths were deliberately not persisted, the evidence cannot distinguish a non-string item, blank item or over-320-character item. It would be incorrect to label this specifically as truncation or merely “too long.”

The validator stopped before the second segment and before any Artifact commit. Post-terminal inspection added zero calls. A reuse preflight was rejected before Provider execution, with gateway event lines unchanged at `18→18`.

Closeout verification: the result plus live-state tests passed `13/13`. The full S3-T09 suite produced `121 passed / 2 failed` only because two historical tests still expected the mutable backlog to point to the now-consumed live-execution action; after updating those time-sensitive assertions, both affected files passed `14/14`. Taken together, all 123 S3-T09 test assertions are green. Project OS result-closeout and repository-hygiene preflights both passed with zero open blockers.

## Product And Governance Assessment

- Pass: exact admission consumption, retry-zero execution, first-failure stop, typed canonical terminalization, no orphan and nonreuse guard.
- Fail: fresh segmented Agent Artifact proof and owner-grade research proof.
- Not performed: paired comparison, owner acceptance, Human Review, T10, S4, release and production.
- Research output delta: none; no new Evidence, financial metric or Alpha.

Next action: separately authorize the zero-call `S3-T09-OWNER-GRADE-V3-SEGMENTED-FIRST-SEGMENT-TEXT-LENGTH-FAILURE-RESULT-AND-ROOT-CAUSE-DECISION`. It may classify and freeze a bounded next repair, but cannot reuse this admission, call a model or rerun automatically.
