# Model Run: 20260724_fin_ia_0_1_s3_t09_three_cell_deepseek_research_lead_v5_live_validation_r1

## Summary

- Purpose: validate the fresh output-v4 / Specialist-v7 / Research Lead-v5 / Writer-v3 path under the compact scoped-reference and dual-capacity contract.
- Status: terminal failed at Research Lead-v5 per-field narrative length validation; admission consumed exactly once.
- Run type: exact-live inference validation.
- Timestamp: 2026-07-24 00:07:27–00:09:06（Asia/Shanghai）。
- Environment: local Windows canonical runtime, DeepSeek `deepseek-v4-pro`.

## Code And Command

- Entry point: `scripts/releases/run_fin_ia_0_1_s3_t09_three_cell_deepseek_live_execution.py`
- Admission: `configs/releases/fin_ia_0_1_s3_t09_three_cell_deepseek_owner_grade_research_lead_v5_exact_admission_r1.json`
- Issuance: `configs/releases/fin_ia_0_1_s3_t09_research_lead_v5_fresh_exact_admission_issuance_v1_0.json`
- Admission digest: `ac364bd6fccdd881e47bef72cec19d44b3eadb0c3de40befc041916d6c84e264`
- Retry environment: process-local `LLM_GATEWAY_TRANSPORT_RETRIES=0`
- Random seed: not applicable to remote inference.

## Inputs And Boundary

- Case: `case_ac6fce120bf27977a1b45832:v1`
- As-of: `2026-07-21T00:00:00Z`
- Input digest: `6fd6585549db9c483a7ea430507185791d83762a62da20381ebec80628981f4c`
- WorkUnit: `wu_p02_5_772dcb33e32d7c39bdae2875`
- Attempt: `attempt_fin01_3e298924838c215f8d5bea8d`
- ResearchRun: `research_run_fin01_2aeba4619781fa9a56f55af0`
- Source network / external tool / live business head writes: `0 / 0 / 0`
- Baseline body exposed to Agent: no.

## Model And Contract

- Provider/model: DeepSeek / `deepseek-v4-pro`
- Output: `fin01.s3.bounded_agent_three_cell_output:v4`
- Specialist: `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v7`
- Lead: `fin01.s3.bounded_agent.research_lead_owner_grade:v5`
- Writer: `fin01.s3.bounded_agent.memo_writer_owner_grade:v3`
- Scoped identity: `fin01.s3.cell_scoped_research_identity:v1`
- Calls ceiling: 12
- Output-token ceiling: Specialist 4200 each, Lead 1800, Writer 1400, Verifier 1000; aggregate 16800.
- Capacity: Lead raw wire 8192 UTF-8 bytes, canonical alias 6000 bytes, local expanded hard cap 32768 bytes, aggregate narrative 3200 characters, each narrative item 320 characters.
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
- Tokens: input `42,040`, output `5,860`, total `47,900`
- Estimated cost: `USD 0.0223365`
- Retry/fallback/rerun: `0/0/0`
- Provider output capture/restricted readback: `10/10`
- All finish reasons: `stop`
- Lead output tokens/cap: `1050/1800`
- Captured Provider latency: `86,204 ms`; slowest call was Lead at `16,196 ms`.

## Failure And Restricted Replay

Failure code is `s3_bounded_research_lead_v3_text_item_over_max_unicode_characters`; stage is `research_lead`, family is `text`, subtype is `item_over_max_unicode_characters`. The `v3` namespace is the shared closed validator telemetry used by the v5 transport; the active Lead transport was v5.

The restricted Lead answer is durably stored but not copied into this report. Read-only structural audit found:

- valid JSON with the exact four top-level members;
- raw wire size `4,628 / 8,192` UTF-8 bytes;
- aggregate narrative `3,077 / 3,200` characters;
- 16 narrative items;
- three per-field violations: dependency statements `388` and `343` characters, and variant-view statement `423` characters, exceeding the 320 limit by `68 / 23 / 103`.

Therefore Lead-v5 fixed the earlier typed-reference wire amplification and token truncation: the answer stopped normally at 1,050 tokens and stayed within raw-wire and aggregate limits. The first later failure is per-field length compliance. Runtime safe telemetry reports a generic failing count of 1, while restricted structural replay locates 3 items; this discrepancy must be examined in the next zero-call root-cause decision.

## Experiment Governance

- Hypothesis: compact aliases and local typed expansion let the exact output-v4 three-Cell chain pass Lead capacity and reach Writer/Verifier.
- Decision target: terminal succeeded, 12 calls, six logical nodes, nine Artifact families.
- Observed: Lead wire and aggregate capacity passed, but per-field text validation failed after 10 calls and zero Artifact.
- Stop condition: first credible failure. Triggered and respected.
- Decision label: stop; zero-call root-cause decision required.
- Mainline decision: not accepted; no paired comparison or owner review.

## Runtime Efficiency

- Canonical execution wall time: about 98 seconds.
- Captured Provider latency: 86.2 seconds.
- Bottleneck: per-field contract compliance, not token, raw-wire, aggregate narrative or local compute capacity.
- Serving implication: unresolved; no successful full research product exists.

## Caveats And Next Step

- This run proves the specific Lead-v4 truncation mechanism did not recur under Lead-v5.
- It does not prove local typed expansion through Writer/Verifier or complete Artifact lineage because validation stopped before those nodes.
- No new accepted evidence, financial metric, research product or Alpha was produced.
- No retry, fallback, repair or rerun is authorized.
- Next: `S3-T09-OWNER-GRADE-RESEARCH-LEAD-V5-PER-FIELD-NARRATIVE-LENGTH-FAILURE-ZERO-CALL-ROOT-CAUSE-DECISION`.
