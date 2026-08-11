# Model Run: 20260722 FIN 0.1 S3-T09 DeepSeek owner-grade v3 segmented transport-v2 live validation r1

## Summary

- Purpose: consume the issued fresh transport-v2 exact admission once and test full owner-grade output-v3 conformance plus canonical Artifact production.
- Status: terminal failed during the second Specialist claim-card segment; admission consumed; no retry, fallback, repair or rerun.
- Run type: bounded paid inference.
- Environment: local Windows workspace, branch `codex/layered-data-source-expansion`.

## Code And Command

- Entry point: `scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py`.
- Admission: `configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_v3_segmented_text_contract_v2_exact_admission_v1_0.json`.
- Issuance: `configs/releases/fin_ia_0_1_s3_t09_owner_grade_v3_segmented_text_contract_v2_fresh_exact_admission_issuance_v1_0.json`.
- Preflight and execution process set `LLM_GATEWAY_TRANSPORT_RETRIES=0`; output prefix was `owner_grade_v3_segmented_text_contract_v2_r1`.
- Provider/model: DeepSeek / `deepseek-v4-pro`.
- Random seed: not applicable; Provider inference.

## Inputs And Budgets

- Case: `case_ac6fce120bf27977a1b45832:v1`, as-of `2026-07-21T00:00:00Z`.
- WorkUnit/Attempt/Run: `wu_p02_5_8bffbd97d1953b74088c5195` / `attempt_fin01_cfea2f1895cb04d73073a8ec` / `research_run_fin01_fe1dc2df883030283d38d362`.
- Input digest: `c69c0f1f7929a01bdb2eeff965737bf3813fed1cadc6e2ba20f1c97454f239cc`.
- Preparation digest: `cc82f50a23f257f0c2eb51b31aada2c380ae8d7a7ae6d6ae98a75f598ec0b96f`.
- Transport/output: `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v2` / `fin01.s3.bounded_agent_three_cell_output:v3`.
- Maximum semantic/provider/network calls: `12/12/12`; Specialist segment caps `1600/1200/1400`; aggregate maximum output 16,200 tokens; total cost cap USD 0.10.
- Retry/fallback/repair/rerun: `0/0/0/0`.
- Source network, external tools and live business Case head writes: disabled.

## Result

- Canonical state: WorkUnit/Attempt/ResearchRun all `failed`; no orphan.
- Artifacts/events: 0 Artifact, 7 events.
- Calls: 5 model / 5 Provider / 5 network; each call used one transport attempt.
- Tokens: 17,682 input + 2,519 output = 20,201 total.
- Estimated cost: USD 0.00883411.
- Summed Provider receipt latency: 48.242 seconds; all five calls reported `finish_reason=stop`.
- Failed stage: `domain_specialist:value_and_profit_capture:owner_grade_claim_cards`.
- Failure code: `s3_bounded_segmented_specialist_contract_invalid:value_and_profit_capture:owner_grade_claim_cards:s3_owner_grade_claim_context_authority_invalid`.
- Runtime result SHA256: `d78858ff42f53e7556fe65ea293dc33bc22af9d4b8da72a281fdafd7079c1370`.

The first Demand Specialist completed all three segments and local validation. The Value/Profit Specialist completed its facts/explanation segment, and its claim-card response passed Provider transport, native JSON parsing, exact segment shape, Cell binding and claim-card shape checks up to context authority validation. At least one `context_ref` was outside the frozen set of candidate and graph context references allowed for that Cell.

The raw Provider body and reference values were deliberately not persisted. Therefore the evidence cannot identify the offending reference, its position, or how many invalid references occurred. It would be incorrect to classify this as an HTTP/JSON/schema-shape failure or to invent a specific prompt/model root cause before the separate zero-call root-cause decision.

The validator stopped before the second Specialist actionable segment, the third Specialist, Lead, Writer, Verifier and all Artifact commits. Post-terminal inspection added zero calls. A reuse preflight rejected the consumed identity before Provider execution; gateway event lines remained `28→28`. Canonical totals are now six WorkUnits, six Attempts, six Runs and thirteen Artifacts; the object tree digest remains unchanged.

Closeout verification: the new result plus adjacent history contracts passed `19/19`; the complete S3-T09 suite passed `158/158 in 346.89s`; post-refresh backlog/stable-source contracts passed `11/11`. Config/docs JSON, Project OS JSONL, 9/9 stable source digests, compileall, diff check and both scoped Project OS preflights passed. No key-shaped plaintext exists in the 276 changed files. A broader read-only scan found legacy report JSON and key-shaped files outside the changed set; they were not read for values, modified or included in this execution result.

## Product And Governance Assessment

- Pass: exact admission consumption, retry-zero execution, first-failure stop, typed canonical terminalization, no orphan and nonreuse guard.
- Fail: fresh transport-v2 Agent Artifact proof and owner-grade research-product proof.
- Not performed: root-cause/repair decision, paired comparison, owner acceptance, Human Review, T10, S4, release and production.
- Research output delta: none; no new Evidence, financial metric, Judgment, Report or Alpha deliverable.

Next action: separately authorize the zero-call `S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V2-CONTEXT-AUTHORITY-FAILURE-RESULT-AND-ROOT-CAUSE-DECISION`. It may determine the earliest owned contract/prompt/model-view cause and choose a bounded disposition, but cannot reuse this admission, call a model or rerun automatically.
