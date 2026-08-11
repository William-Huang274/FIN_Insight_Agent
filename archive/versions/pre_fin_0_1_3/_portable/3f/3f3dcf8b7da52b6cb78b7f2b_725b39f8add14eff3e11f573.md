# FIN 0.1 S3-T09 DeepSeek Specialist-v5 + Research Lead-v2 live validation R1

## Summary

- Purpose: exact-once fresh proof of Specialist transport-v5 plus the closed Research Lead-v2 contract.
- Status: terminal failed at local assembled Lead canonical validation.
- Run type: paid inference / live validation.
- Timestamp: 2026-07-23 11:37–11:38 Asia/Shanghai.
- Environment: local Windows runtime, DeepSeek beta endpoint, model `deepseek-v4-pro`.

The admission `fin01-s3-t09-three-cell-deepseek-owner-grade-v3-specialist-v5-research-lead-v2-exact-admission-r1` with digest `65a934d69766bfc4eff56b0decf2f986bba685d9cbbc3a68b781ce5202118cc0` was consumed exactly once.

## Inputs and contract

- Case: `case_ac6fce120bf27977a1b45832`, version 1.
- Input digest: `86ad143c69b3ef146e64048fcf981e33e751f1fa41a9190b91449b511da1b232`.
- Specialist transport: `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v5`.
- Lead transport: `fin01.s3.bounded_agent.research_lead_owner_grade:v2`.
- Output contract: owner-grade v3.
- Model / Provider / network ceiling: `12 / 12 / 12`.
- Output ceiling: 16,800 tokens; total cost ceiling: USD 0.10.
- Retry / fallback / rerun: `0 / 0 / 0`.
- Source network, external tools, and live business Case-head writes: disabled.

Project OS scoped preflight and exact runner preflight passed. The target identity was absent with canonical counts `9/9/9/13`.

## Result

All three Specialists and all nine segments completed with `finish_reason=stop`. Research Lead also returned `finish_reason=stop` at 1,094 of 1,800 output tokens. Its four-member v2 object passed native JSON, exact shape, cardinality, text, authority, and provider-byte checks:

- dependencies / conflicts / gaps: `3 / 3 / 4`
- Provider output: 3,424 UTF-8 bytes of a 6,000-byte limit
- locally assembled Lead: 4,437 UTF-8 bytes of an 8,192-byte limit

The prior Lead truncation did not recur. RC-P36-040's capacity repair therefore has live evidence.

The assembled output then failed the historical canonical Lead validator with `s3_owner_grade_lead_fact_presence_mismatch`, surfaced safely as `s3_bounded_research_lead_v2_assembly_canonical_validation_failed`. WorkUnit, Attempt, and ResearchRun are consistently failed; Artifact count is zero, event count is seven, and the Run is not orphaned. Writer and Verifier were not called.

## Root-cause observation

Restricted structural replay, without emitting raw answer text, found two total Facts in the Value/Profit Cell and zero Facts in the other two Cells. Two conflict rows described only zero-Fact claims/Cells as `no_facts_present`. The canonical validator rejects every `no_facts_present` conflict whenever the global three-Cell fact count is greater than zero, even if the unrelated Facts are outside that conflict.

Lead-v2 currently validates the field as an enum but does not close whether fact presence is global, involved-Cell, involved-claim, or direct-support scoped. This is a project-owned scope-contract mismatch, not a token-cap or Provider transport failure. One additional `mixed_fact_presence` row also needs the future decision to define the intended scope; no semantic repair is inferred from this Run alone.

## Usage and runtime efficiency

- Model / Provider / network calls: `10 / 10 / 10`.
- Input / output / total tokens: `39,443 / 5,999 / 45,442`.
- Provider-receipt latency total: 83,172 ms.
- Estimated cost: USD 0.02154861.
- Retry / fallback / rerun: `0 / 0 / 0`.
- Source network / external tools: `0 / 0`.

The desktop command wrapper returned a timeout after 14 seconds, but the original runner process remained active and completed normally. Canonical polling was read-only; no second execute command was issued.

## Captures and safety

Ten final assistant outputs are persisted in the restricted content-addressed object store and were read back through the Run-bound facade. Tracked result files contain only digests and structural audit facts; no assistant body, raw HTTP envelope, credential, or private reasoning is tracked.

Closeout verification passed 46 focused current/historical contract tests and the scoped Project OS preflight with zero open full-chain blockers. Verification made zero additional model, Provider, or network calls.

## Decision

The admission is consumed and cannot be reused. The Run proves the Lead-v2 capacity repair live, but the Agent product proof still fails because no Artifact was committed.

Next action is a separately authorized zero-call root-cause decision:

`S3-T09-OWNER-GRADE-V3-RESEARCH-LEAD-V2-CONFLICT-FACT-PRESENCE-SCOPE-ROOT-CAUSE-DECISION`

No validator patch, replacement admission, retry, rerun, paired comparison, Human Review, T10, S4, release, or production action is authorized by this result.
