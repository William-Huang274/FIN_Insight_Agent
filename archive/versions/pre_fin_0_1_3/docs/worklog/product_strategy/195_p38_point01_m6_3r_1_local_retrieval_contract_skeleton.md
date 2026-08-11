# P38 Point01 M6.3R.1 Local Retrieval Contract Skeleton

## Scope And Status

- Date: 2026-07-13
- Reviewer decision: `approve_m6_3r_0_design_repair_authorize_m6_3r_1_skeleton_only`.
- Status: `superseded_by_196_authority_legacy_digest_scope_repair`.
- This is a typed, deterministic contract slice only. It neither opens nor invokes a local adapter.

## Implemented Contract

- `TopKPolicyRequest/Profile/Resolution/Audit` resolves a request-bound, versioned profile. The standard profile is `50/20/5`; CandidateBundle, rerank and future Evidence Gate capacities remain separate.
- `LegacyEvidenceRequestTopKAdapter` maps the M6.1 `top_k/candidate_limit` shape only under an explicit mapping version. It never mutates M6.1 objects or reinterprets two legacy fields as three capacities.
- `LocalAdapterSnapshot`, `LocalRetrievalQuery`, `LocalRecallCandidate`, `DeterministicRerankDecision` and `NeighborExpansionPlan` are frozen serializable contracts.
- Read-only BM25/ObjectBM25/graph/exact-value SQL protocols are injected seams only. The SQL shape requires pinned snapshot digest, exact entity/period/form/source-tier/unit/row-selector filters and a `ToolInvocationReceiptReference`; it forbids relaxed fallback.
- `CandidateBundleProjection` maps only to the existing `CandidateBundle`. `EvidenceGateCandidateProjection` remains non-persistent, non-promoted, non-citable and capped at five candidates.

## Verification

- `python scripts/engineering/run_point01_m6_3r_1_local_retrieval_skeleton_gate.py` → pass; records deterministic schema hashes and all counts zero.
- M6.3R.0 design regression, M6.3R.1 skeleton regression and canonical schema export regression → `24 passed`.
- Compileall passed for the new runtime contract, schema exporter, gate and tests.
- Final scoped rerun after exact SQL receipt-binding negative coverage → `24 passed in 1.65s`; both design/skeleton gates and Project OS JSONL parsing remained pass.

The import/constructor regression proves the new module imports no real BM25, graph, DuckDB, MCP handler, HTTP client or store module; its probe adapter is injected but never called.

## Boundary And R.2 Fixture Plan

No local index/graph/SQL read, ToolInvocation, network, model/provider, parser/numeric, Evidence Gate promotion, SourceHunter, Context, Writer, full-chain, receipt creation, production store access, business Case mutation or legacy authority cutover occurred.

R.2 is only a future sanitized immutable fixture tranche: candidate/neighbor/exact-value SQL-row fixtures plus Top-K/diversity/exhaustion matrices. It needs separate total-reviewer approval and must still make zero adapter calls.

## Supersession

The independent R.1 audit found that this initial skeleton still accepted agent-origin profile selection, did not consume a full immutable M6.1 request for real `3/12`, `5/12`, `1/1` compatibility, did not recompute create-owned digests on replay, and did not fully bind supplied candidates/gate subsets to query scope. Those issues are owned R.1 contract defects. They are repaired and recorded in `196_p38_point01_m6_3r_1_authority_legacy_digest_scope_repair.md`; this entry is not an acceptance claim.
