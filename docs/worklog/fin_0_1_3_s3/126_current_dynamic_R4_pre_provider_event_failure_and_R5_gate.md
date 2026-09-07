# FIN 0.1.3 S3 — current dynamic R4 pre-provider event failure and R5 gate

Date: 2026-08-23

## What R4 did and did not do

R4 did not call DeepSeek. The runner copied the immutable R3 research checkpoint,
then attempted to append `workpaper_submission_successor_started`, which is not a
legal event in the canonical Runtime contract. `CanonicalRuntimeError` escaped
before the provider executor and before the old runner could materialize a
terminal result. There were zero Provider calls, retrieval rounds, S1/S2 requests,
network calls, Candidate promotions, retries or model outputs.

The consumed R4 authority now has an explicit public and private terminal receipt.
It is project-owned integration evidence only; it says nothing about DeepSeek
quality and does not invalidate R3's completed two-round dynamic research.

## Structural repair

The workpaper successor now uses the existing canonical event vocabulary:
`provider_attempt_requested`, `provider_attempt_completed` and
`provider_attempt_failed`. It does not grow the Runtime contract with one-off node
event names. Message compilation, Tool Schema compilation, event append, provider
dispatch and local workpaper validation are exposed through one execution seam,
and the test suite runs that same seam with a fake Provider. Known local and
provider errors are converted to the typed terminal result; a defensive local
exception classification prevents another traceback-only attempt.

## Bounded continuation

R4 remains immutable and its output identity cannot be reused. The R5 scope
decision binds both the R3 research predecessor and the R4 zero-call failure.
R5 may make exactly one non-thinking workpaper submission, with zero retrieval,
S1/S2, external source, Evidence promotion, retry or fallback. It must use a new
run and attempt ID after a clean commit, push and repository-aware preflight.

Even a contract-valid R5 proves only a DELL `value_capture` dynamic single-unit
candidate. Independent L1 and eight-dimension content assessment remain required
before any five-unit or multi-agent execution.
