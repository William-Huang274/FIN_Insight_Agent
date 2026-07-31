# Model Run: 20260722 FIN 0.1 S3-T09 DeepSeek owner-grade transport-v3 live validation r1

## Summary

- Purpose: consume the issued transport-v3 exact admission once and test complete six-node, nine-Artifact owner-grade conformance.
- Status: terminal failed in the second Specialist claim-card segment; admission consumed; no retry, fallback, repair or rerun.
- Run type: bounded paid inference on branch `codex/layered-data-source-expansion`.

## Exact Contract

- Admission: `fin01-s3-t09-three-cell-deepseek-owner-grade-v3-segmented-transport-v3-exact-admission-r1`, digest `d04c86a1590420b7efa11e7d79ca77a440348883aa336963d81ad273788cba84`.
- Case: `case_ac6fce120bf27977a1b45832:v1`, as-of `2026-07-21T00:00:00Z`.
- WorkUnit / Attempt / Run: `wu_p02_5_4c750d8d75f970935c9c181e` / `attempt_fin01_78f45641670c4b42695d8bea` / `research_run_fin01_9bc3ffd904ae98b26b5cba95`.
- Input / preparation digest: `4bac3542b8fcbe3f9f5cd398be6bb6b82afe11eda06ab7ffaf6b58639ce4ab2e` / `6a32df5d5834bffc6b389bc45ca53811f513a5ec924ff2cb36f72ca49d09d2a4`.
- Transport / output: `fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v3` / `fin01.s3.bounded_agent_three_cell_output:v3`.
- Maximum calls `12/12/12`, aggregate output cap 16,200, cost cap USD 0.10; retry/fallback/rerun all zero.

## Preflight Owner Repair

The first zero-call preflight exposed a runner defect: it recompiled the exact input by opening the target canonical store writable, which changed the SQLite main-file digest although the latest logical counts remained `6/6/6/13`, the target identity stayed absent, the object tree was unchanged, and calls remained zero. Before consuming the admission, the runner was repaired to read target rows through SQLite URI `mode=ro` and compile only in a disposable full runtime clone. Runner contracts passed `5/5`; the aligned physical-hash regression passed again. The repaired real-target preflight preserved database digest `ddf4241...ce1b` and object-tree digest `00ac740b...ea75` exactly.

## Result

- Canonical WorkUnit, Attempt and ResearchRun all terminal `failed`; 0 Artifact, 7 events, no orphan.
- Five DeepSeek `deepseek-v4-pro` requests all returned `finish_reason=stop`, one transport attempt each.
- Usage: 18,167 input + 1,863 output = 20,030 tokens; estimated cost USD 0.00941302; summed receipt latency 28.262 seconds.
- The Demand Specialist completed all three segments and local validation. The Value/Profit Specialist completed facts/explanation, then its claim-card segment reached local semantic validation.
- Failure code: `s3_bounded_segmented_specialist_contract_invalid:value_and_profit_capture:owner_grade_claim_cards:s3_owner_grade_epistemic_status_statement_conflict`.

This code means at least one claim labeled `cannot_infer` conflicted with its support set or its required `cannot_support_statement`. It is not the prior transport-v2 `context_ref` membership failure. Safe persistence does not retain the raw response, so the exact card and which of the two branches failed cannot be reconstructed and must not be guessed.

The validator stopped before the second Specialist actionable segment, third Specialist, Lead, Writer, Verifier and every Artifact commit. Zero-call terminal inspection confirmed one exact failed WorkUnit/Attempt/Run, no Artifact, and no additional model, Provider or network call. The canonical object tree stayed unchanged; no credential value, raw response or private reasoning was persisted.

Closeout verification passed the new result plus issuance contracts `13/13`, the historical mutable-head repair set `10/10`, and the complete S3-T09 contract suite `192/192 in 683.69s`. JSON/JSONL parsing, Python compile and diff check passed. Scoped result-closeout and repository-hygiene Project OS preflights both passed with zero open blockers.

## Product And Governance Assessment

- Pass: exact-once admission consumption, retry-zero execution, typed first-failure stop, canonical closeout, no orphan and boundary compliance.
- Fail: transport-v3 Artifact proof and owner-grade research-product proof. There is no new Evidence, Numeric, Judgment, Report or Alpha deliverable.
- Not performed: repair, rerun, paired comparison, owner acceptance, Human Review, T10, S4, release or production.

Next action is the separately authorized zero-call `S3-T09-OWNER-GRADE-V3-SEGMENTED-TRANSPORT-V3-EPISTEMIC-STATUS-STATEMENT-CONFLICT-RESULT-AND-ROOT-CAUSE-DECISION`. It must decide the earliest owned field-contract/model-view/provider-route cause without another live call. Because the typed subtype differs from the prior context-authority membership failure, provider-route disposition is not asserted before that decision.
