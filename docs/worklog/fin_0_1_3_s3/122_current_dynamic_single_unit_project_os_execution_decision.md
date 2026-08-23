# FIN 0.1.3 S3 — current dynamic single-unit Project OS execution decision

Date: 2026-08-23

## Why a new decision type is required

The historical `dynamic_single_cell` Project OS decision describes a different
product path: SEC-only evidence, one planner, three fixed analysis fragments and
three fixed submissions, for a seven-call ceiling. Reusing that decision for the
current R32 loop would misstate both the product behavior and the paid-call
authority.

The current loop begins with only the DELL question, company identity, as-of date
and a bounded request catalog. DeepSeek must select real S1/S2 requests, consume
reviewed Evidence, NumericFact and actionable FeedbackReceipt results, then return
PlanDelta, hypothesis-only GraphDelta and StopDecision before one final
`value_capture` workpaper.

## Decision and limits

- Added the provider-neutral Project OS schema
  `fin_ia_s3_current_dynamic_single_unit_live_scope_decision_v1_0`.
- Bound the immutable two-round current-runtime zero-call result, loop policy and
  DeepSeek V4 Pro GA profile by SHA-256 and canonical result digest.
- Copied the task-specific `TokenBudgetBasis` from the bound policy instead of
  inventing a generic cheap/fast token ceiling.
- Authorized at most four model/transport steps, two retrieval rounds and twelve
  S1/S2 requests, with zero retries, external source network calls, candidate
  promotions, fallbacks or current-product pointer mutations.
- Explicitly withheld S1 acceptance, S3 acceptance, multi-agent execution,
  publication and release.

## Verification at this checkpoint

- Full repository regression: `1076 passed`; the only warnings are the two
  pre-existing SWIG deprecations.
- The focused Project OS cases include a negative budget-drift mutation.
- The decision-bound preflight passes when repository cleanliness is deliberately
  not checked; the formal preflight remains pending until this implementation and
  decision are committed and pushed to a clean synchronized branch.
- `compileall`, active-baseline verification (`205 Python / 8 frontend / 5
  detectors / 28 runtime resources / 0 forbidden`), 879 config JSON parses,
  diff check and a 7,691-file secret scan all pass.
- No model, provider, network or paid tool call occurred in this checkpoint.

## Next exact step

The decision implementation was committed and pushed at clean/synced commit
`925b2cfa356fe20eca15a54395fbc91d9af65a1e`. The formal Project OS preflight
then passed with credential-presence-only checking, no blocked root-cause scope
and no credential persistence.

The unique authority `dell-current-dynamic-single-unit-r1-20260823t0046z` is now
signed against that implementation commit, current Pack digest, task-readiness
digest, zero-call result, loop policy and provider profile. The authority must be
committed and pushed before execution; after that, the next exact step is the one
authorized DeepSeek live run followed by independent L1 and content assessment.
