# FIN 0.1 S3 Specialist contract policy convergence v1

## Decision

New owner-grade Specialist transports must compose immutable capabilities and
typed domain policies. They must not infer behavior by copying cumulative
`if transport in {vN...}` sets.

The first converged transport is
`fin01.s3.bounded_agent.deepseek_segmented_owner_grade_specialist:v7`.
It preserves canonical output-v3, six logical nodes, nine Artifact families,
Research Lead-v3 and Memo Writer-v2.

## Policy ownership

- `FactSupportAuthorityPolicy` owns the exact, field-local Evidence/Numeric
  authority exposed beside `fact_layer.support_refs` and the matching local
  validation precedence.
- `EpistemicStatePolicy` owns the Claim status matrix used by the Provider
  request and local pre-assembly validation.
- `ClaimScopeResolver` owns deterministic scope assembly from validated
  `support_fact_ids -> Fact support_refs -> Numeric authority`.
- `BoundedResearchProfile` owns company, Cell inventory, narrative/byte
  capacity, and output-token budgets.
- `SpecialistTransportContract` declares which of those capabilities a
  transport uses.

Provider adapters own wire shape only. They may not promote Candidate or Graph
context, invent a Fact reference, normalize canonical scope tokens, or repair a
failed output.

## Compatibility

Transport v1-v6 constants and Provider request behavior remain immutable.
Admissions created before `research_profile_ref` existed omit it from their
digest payload and resolve to the frozen NVDA three-Cell profile. A new v7
admission must bind that profile explicitly.

Historical failed outputs remain failed. In particular, the v6 Value/Profit
answer containing one Graph ref among Fact support refs is not normalized,
filtered, or reclassified.

## Validation and telemetry

The v7 Fact support validator uses this precedence:

1. invalid support type or non-array/empty support;
2. non-string or blank item;
3. Candidate/Graph misclassified as Fact authority;
4. Evidence/Numeric cross-type selection;
5. value outside the current Cell authority;
6. duplicate support ref.

Failure telemetry is content-free and contains only contract, segment, field,
subtype, failing count, and false persistence flags. Raw refs, hashes, item
indexes, arbitrary key names, and private reasoning are forbidden.

## Generalization proof boundary

Deterministic fixtures cover:

- the existing NVDA three-Cell profile;
- an AMD one-Cell profile object;
- a nonstandard `2027-Q1-53W` period;
- Evidence-only, Numeric-only, and mixed authority;
- Graph/Candidate, cross-type, unknown, empty, and duplicate negatives;
- v6 Provider-request immutability;
- a 12-call fake-Provider six-node/nine-Artifact path.

This proves domain-policy configurability, not a non-NVDA end-to-end product.
The current runtime input compiler and product acceptance surface remain the
NVDA three-Cell anchor until a separately planned cross-company slice is
implemented and dogfooded.

## Next gate

The next permitted item is a zero-call fresh v7 Agent-proof decision. Admission
issuance, model/Provider/network calls, comparison, Human Review, T10, S4,
release, and production require separate authority.
