# P38 Point01 M6.3/M6.5 v5 Live Artifact Contract Remediation

## Summary

- Date: 2026-07-13
- Scope: offline repair of the v4 authorized NVDA 10-K pilot artifact contract.
- Decision state: `artifact_contract_remediated_refrozen_pending_total_reviewer`.
- Network / model / external tool execution in this repair: `0 / 0 / 0`.

## Problem And Decision

The v4 live JSON was restricted audit input, not an acceptable exported terminal artifact: it retained a raw approval nonce, reused package-freeze state in a live result, mixed static package prohibition with execution-time authorization, and reused a request/plan-only invocation identity that could collide with the v3 incident.

The original v4 JSON and temporary SQLite evidence were preserved without rewrite.  They are now locally quarantined and ignored by Git.  A separate sanitized projection is the only human-facing audit artifact produced by this repair.

## Delivered

- `M6GlobalOneShotApprovalReceipt` and both SEC invocation receipt types persist `approval_nonce_sha256` only. Raw nonce is registration input only.
- The document executor binds execution identity to the active receipt digest, approval id/version, WorkUnit/Attempt, task correlation and local-store identity. Candidate/parser/fact/trace each carry this execution instance id.
- Live terminal output is now a distinct schema with `package_authority_boundary`, `execution_authorization_snapshot` and `execution_outcome`; a package freeze remains static and cannot be mistaken for an execution outcome.
- Added restricted-retention policy, sanitizer and secret scan. The sanitized projection has a new digest-bound execution identity and keeps all lineage unpromoted/non-citable behind a downstream firewall.
- Updated the future v5 authority/pilot contract and immutable package manifest. No receipt was registered for v5.

## Evidence

- v4 original: restricted, local-only, ignored, SHA-256 `de3ca1c2d841242faac29c67d29f0a836632d18a9b55d0941b14743d8074bdd5`.
- v5 sanitized audit projection: [point01_m6_3_5_v5_sanitized_authorized_live_audit_projection_v1_0.json](/D:/FIN_Insight_Agent/data/manifests/point01_m6_3_5_v5_sanitized_authorized_live_audit_projection_v1_0.json), SHA-256 `27e4b30b086ded648c26b6fbf20ca0c1e811297755c0328fa4f7338d72d7dbbe`.
- v5 package: `a8210e702e2a7147513537916c505baec92dc0ff7526139c7eb557f19cdfbd23`; manifest: `272eb312f635e88da37254b6853b15709a18cdb8ec9cade66541b6fc269b3faa`; scope: `bcec5108da71785c7b21c52ea8d671ef8f18e330c962324bc3f44f0935545236`.
- Targeted contract regression: `19 passed`.
- Full Point01 M6 contract suite: `92 passed`.
- SQLite/RuntimeFacade: `28 passed`.
- Design lint, actual-shape parser gate, compileall, worktree diff checks and exportable-artifact secret scan: pass.
- Fixed approval store before/after: database SHA-256 `ae48eea1eec25ae96143a49266c991365fe9974d1c282d3d5579ccd56ab561f4`; content fingerprint `a7a7acad7e03460cbbe92bd967a10a6d62a11be7e0ad72f28fae3adb1b1a33c0`; rows `4`.

## Total Reviewer Acceptance And Closeout

Total reviewer `william / 003` independently accepted the repair with `conditional_approve_m6_3_5_v5_artifact_contract_remediation_audit_only`. The acceptance is recorded in the package-external, read-only [reviewer receipt](/D:/FIN_Insight_Agent/data/manifests/point01_m6_3_5_v5_artifact_contract_total_reviewer_acceptance_receipt_v1_0.json), SHA-256 `50b7440680b2339d6bf9749aaa310bdaa891eb12736d65e80e58ec61fce82e87`.

The receipt binds the exact v5 package/manifest/scope and projection digest but is deliberately excluded from the package manifest. The dedicated closeout re-computed the package before and after receipt validation, validated the decision-text digest and reviewer identity, and re-ran the exportable secret scan including the receipt. All checks passed; canonical-store, external, network, tool and model writes/calls are `0`.

The accepted status is `remediated_v5_artifact_contract_independently_accepted_no_downstream_authority`. It does not register an execution receipt, authorize another SEC GET, or permit promotion, Context/Writer, M6.4/M6.6/M6.7, models, full-chain, production authority, or Case mutation.

## Safety And Next Step

No new receipt, User-Agent, live send, retry, fallback, promotion, M6.4, M6.6, M6.7, Writer, model, full-chain, business Case mutation or legacy authority change occurred. The v4 success is recorded only as `single authorized source/parser behavior observed`; it is not M6.3/M6.5 full or calibrated, and M6 is not complete.

The next approved execution point is `M6.3R.0 local retrieval/rerank/context-expansion design freeze only`. It must stay in design/schema/adapter-inventory/test-plan scope, with no local retrieval execution, network, parser/numeric, promotion, SourceHunter, Context/Writer, models or full-chain. It must return to audit before any skeleton implementation.
