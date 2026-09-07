# FIN 0.1.3 S3 — current dynamic R2 feedback contract failure and R3 gate

Date: 2026-08-23

## R2 proved before it stopped

R2 crossed the DeepSeek thinking-mode transport boundary that stopped R1. The
model naturally selected six first-round requests covering issuer demand,
subject supply execution, PVM, margin, counterparty value pool and issuer
counterevidence. The current S1/S2 runtime then returned 12 reviewed Evidence,
11 NumericFacts, five typed numeric relations and nine residual gaps. No initial
Evidence Pack was pre-fed, no Candidate was promoted and no external-source
network route ran.

The first reflection was also substantive. It distinguished reported AI orders,
revenue and backlog from product-level ASP, unit volume and supplier allocation;
it proposed the six unexecuted requests for price/configuration, units, upstream
capacity, bilateral supplier relationship, ecosystem counterevidence and
downstream demand. This is useful natural evidence that the model can identify a
material second round after consuming tool results. It is not a completed
dynamic run because the reflection was rejected before round two.

## Exact failure and ownership

The Tool message contained eight current-round `FeedbackReceipt` objects. The
runner nevertheless tried to recover those receipts by filtering on a
`round_id` field that the canonical receipt contract does not contain. The
resulting Tool Schema exposed only `FEEDBACK::NONE`. DeepSeek followed that
schema exactly. The validator then rejected `FEEDBACK::NONE` because only real
receipt identifiers are valid. R2 is therefore preserved as
`terminal_failed_no_retry` with two Provider calls and one retrieval round.

This is a project-owned compiled-contract contradiction, not a DeepSeek
instruction-following failure and not an S1 evidence failure. The same audit
also found latent sentinel contradictions when a final round has no remaining
request or when no Evidence reference is available, plus a public-result
projection that used internal Provider step objects instead of the redacted
index projection.

## Structural repair

- Bind receipt batches to runtime round numbers in the runner rather than
  inventing a field on `FeedbackReceipt`.
- Compile actual current-round receipt IDs into the Tool Schema and require at
  least one receipt when receipts exist.
- Compile true zero-length arrays when feedback, next requests or Evidence refs
  are absent; never require fake sentinel refs that the validator rejects.
- Keep the local validator on the same reference domain as the Tool Schema.
- Keep complete model requests/responses in restricted capture-first storage;
  public results expose only hashes, usage, finish reason and capture refs.

The corrected two-round zero-model replay completed all 12 requests once,
bound 20 FeedbackReceipts, generated two PlanDelta/GraphDelta steps, stopped
explicitly and compiled the workpaper contract. CUDA/FP16, checkpoint/resume,
cross-case/date/repeat/premature-stop and permutation mutations all remained
fail closed or stable. The final targeted gate is `82 passed`; the full
repository gate is `1082 passed` with only two pre-existing SWIG deprecation
warnings. Python compileall, active-baseline verification (`205 Python / 8
frontend / 5 detectors / 28 Runtime / 0 forbidden`), all `885` config JSON
documents, the `7,699`-file repository secret scan and `git diff --check` pass.
The full repository gate initially
reported one decision-fixture mismatch because the successor copied an updated
TokenBudgetBasis instead of the policy-bound basis; the decision was corrected
to keep the already frozen task budget unchanged. A second stale assertion kept
the already-closed RC-S3-058 transport issue as a permanent scope blocker; it
was corrected so historical decisions remain parseable while consumed
exact-once authorities and immutable results continue to prevent reuse.

## Next gate

R3 may be signed only after full regression, active-baseline, config parse,
secret scan, clean commit/push and repository-aware Project OS preflight. R3 is
one fresh full dynamic attempt rather than a retry of R2. It keeps the same
question, current Pack, model, two retrieval rounds, 12-request ceiling,
four-call ceiling and zero retry/network/promotion boundaries. Success still
requires independent L1 and content assessment before any multi-agent work.
