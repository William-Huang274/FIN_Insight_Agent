# Model Run: 20260723_fin_ia_0_1_s3_t09_cross_cell_scoped_identity_output_v4_live_validation_r1

## Summary

- Purpose: validate the fresh output-v4 Cell-scoped Claim/WWC identity path through Specialist-v7, Research Lead-v4, Memo Writer-v3 and Verifier.
- Status: terminal failed at Research Lead-v4 capacity; admission consumed exactly once.
- Run type: exact-live inference validation.
- Timestamp: 2026-07-23 21:38:22–21:39:59（Asia/Shanghai）。
- Environment: local Windows canonical runtime, DeepSeek `deepseek-v4-pro`.

## Code And Command

- Entry point: `scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py`
- Admission: `configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_cross_cell_scoped_identity_output_v4_exact_admission_r1.json`
- Issuance: `configs/releases/fin_ia_0_1_s3_t09_cross_cell_scoped_identity_fresh_exact_admission_issuance_v1_0.json`
- Admission digest: `ba3642d023209208cb90ebfd4295fe00291fae27cbc382561d81d8a4f0aa8973`
- Retry environment: process-local `LLM_GATEWAY_TRANSPORT_RETRIES=0`
- Random seed: not applicable to remote inference.

## Inputs And Boundary

- Case: `case_ac6fce120bf27977a1b45832:v1`
- As-of: `2026-07-21T00:00:00Z`
- Input digest: `897f0c24b4a73b45989343d4f1baa16050093546b36dc12122c0a23bbc3886d4`
- WorkUnit: `wu_p02_5_eb20ec3266ec17ff47448b74`
- Attempt: `attempt_fin01_d8f5d991b89a6d5677973060`
- ResearchRun: `research_run_fin01_389411049b562ebd57000528`
- Source network / external tool / live business head writes: `0 / 0 / 0`
- Baseline body exposed to Agent: no.

## Model And Contract

- Provider/model: DeepSeek / `deepseek-v4-pro`
- Output: `fin01.s3.bounded_agent_three_cell_output:v4`
- Specialist: `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v7`
- Lead: `fin01.s3.bounded_agent.research_lead_owner_grade:v4`
- Writer: `fin01.s3.bounded_agent.memo_writer_owner_grade:v3`
- Scoped identity: `fin01.s3.cell_scoped_research_identity:v1`
- Calls ceiling: 12
- Output-token ceiling: Specialist 4200 each, Lead 1800, Writer 1400, Verifier 1000; aggregate 16800.
- Cost ceiling: USD 0.10.
- Retry/fallback/rerun: forbidden.

## Results

- Canonical states: `failed / failed / failed`
- Orphaned Run: false
- Artifact count: 0
- Calls: model/provider/network=`10/10/10`
- Specialist segments completed: 9/9
- Research Lead called: yes
- Memo Writer / Verifier called: no / no
- Tokens: input `42,373`, output `6,279`, total `48,652`
- Estimated cost: `USD 0.02284589`
- Retry/fallback/rerun: `0/0/0`
- Provider output capture/restricted readback: `10/10`
- Lead finish reason: `length`
- Lead output tokens/cap: `1800/1800`

## Failure And Restricted Replay

Failure code is `s3_bounded_research_lead_v3_capacity_provider_length_stop`; stage is `research_lead`, family is `capacity`, subtype is `provider_length_stop`.

The restricted Lead answer is durably stored but not copied into this report. Read-only structural audit found:

- 7,177 characters / 7,177 UTF-8 bytes;
- 25 occurrences of typed `identity_kind`;
- all three Cell IDs already present;
- dependencies, conflict adjudications and remaining gaps had started;
- invalid JSON because the answer was cut inside the `program_cell_id` string at line 208.

This is not evidence of a random DeepSeek JSON formatting failure. The Provider exhausted the exact 1,800-token cap while emitting output-v4 typed scoped references. The previously closed RC-P36-040 capacity assumption is therefore invalid under the larger v4 wire shape.

## Experiment Governance

- Hypothesis: scoped identity v1 can carry all three Cells through the six-node output-v4 pipeline without namespace loss.
- Decision target: terminal succeeded, 12 calls, six logical nodes, nine Artifact families.
- Observed: terminal failed after 10 calls, five logical nodes not all completed, zero Artifact.
- Stop condition: first credible failure. Triggered and respected.
- Decision label: stop; zero-call root-cause decision required.
- Mainline decision: not accepted; no paired comparison or owner review.

## Runtime Efficiency

- Live execution wall time between canonical start and terminal events: about 97 seconds.
- Slowest observed call: Research Lead, 17,150 ms.
- Total captured Provider latency: 78,038 ms.
- Bottleneck: output contract size/capacity, not compute utilization.
- Serving implication: unresolved; no successful full product exists.

## Caveats And Next Step

- Scoped identity received partial live proof only through Specialists and Lead wire output.
- Writer, Verifier and nine-Artifact product remain unexercised.
- No new evidence, financial metric or Alpha was produced.
- No retry, fallback, repair or rerun is authorized.
- Next: `S3-T09-OWNER-GRADE-CROSS-CELL-SCOPED-IDENTITY-RESEARCH-LEAD-V4-CAPACITY-RECURRENCE-ZERO-CALL-ROOT-CAUSE-DECISION`.
