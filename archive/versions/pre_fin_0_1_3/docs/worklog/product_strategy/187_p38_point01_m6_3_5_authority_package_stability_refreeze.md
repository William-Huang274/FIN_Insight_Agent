# 187 P38 Point 01 M6.3/M6.5 Authority Package Stability Refreeze

Date: 2026-07-13

## Decision applied

`parser_repair_accepted_authority_package_self_invalidation_repair_required`

The parser repair remains accepted, but package `c190b420…` was not eligible for receipt registration: its hash-covered authority policy carried a mutable approval status. Updating that status after review would have changed the approved package.

## Repair

- Split stable policy rules from package-external, append-only human receipt state.
- The immutable policy now requires an external exact-digest total-reviewer decision and an active exact receipt in the fixed approval store; it carries no mutable approval disposition or superseded-package digest.
- Receipt registration and live execution no longer depend on editing a package-included config. The runtime checks an active receipt bound to package/manifest/scope digest, nonce, UTC expiry, reviewer identity and fixed store identity.
- Added read-only receipt preflight; the executor still atomically consumes the receipt before a send. A copied SQLite approval store fails because store identity includes its resolved path.
- Corrected the positive-document policy model to include the process-local User-Agent scope-confirmation variable, which had been masked by the former early denial.

## Regressions and local evidence

- M6.3/M6.5 authority/design contracts: `16 passed`.
- Complete `test_point01_m6_*.py` manifest: `82 passed`.
- SQLite/RuntimeFacade: `28 passed`.
- Design lint: `pass`; actual-shape compatibility gate: `pass`; all three emitted `external_call_count=0`.
- Regression covers package digest stability before/after receipt registration, missing receipt, wrong package/scope/reviewer/expiry, exact receipt as the send gate, and copied-store denial.

## Refrozen package

```text
package_ref:      point01-m6-3-5-nvda-10k-positive-retrieval-parser-package-v3-immutable-authority-boundary
package_digest:   7d2a5b40ad765a8de655c1d0fbd73e82130ed58e1be659cb5899aa5871054ca5
manifest_digest:  8970c0aae48d9059ed11d8ec8efc54882a8cbc74e32ee4f29f5932c792b714f3
scope_digest:     ad5df001105162f36528c217457464df65ff5e4e1778c55134412a50296ee1b0
```

Current status is `package_frozen_external_total_reviewer_decision_required`. No receipt was registered, no User-Agent was set for runtime, and no SEC GET, Evidence promotion, Writer, Domain Judgment, M6.7, provider/model, full-chain, business Case mutation or legacy-authority change occurred.

The first local rerun was fail-closed because Docker's `docker_engine` named pipe was unavailable. After Docker was restored, the same M1 gate passed: PostgreSQL 16 conformance `pass`, fast-contract suite `273 passed`, no unmet conditions, and `milestone_status=M1_complete`. This is an M1 regression result only; it does not broaden the M6.3/M6.5 receipt or live-send authorization.
