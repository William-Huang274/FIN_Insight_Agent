# P38 Point01 M6.3R.1 Exact-Value SQL Request / Plan / Scope Repair

## Status

- Date: 2026-07-14.
- Reviewer decision being repaired: `reject_and_repair_m6_3r_1_exact_value_sql_request_plan_scope_binding`.
- Current milestone status: `skeleton_independently_accepted_non_authoritative` after the final total-reviewer audit. The scope is accepted as a zero-execution skeleton only; it is neither an authority-admitted SQL policy nor runtime retrieval.
- This is an R.1 in-memory typed-contract repair. It does not read an index, graph, SQL database or receipt registry and does not invoke a tool, network, model, parser, promotion, SourceHunter or canonical-store write.

## Owned Root Cause And Repair

The preceding repair made a supplied candidate match `ExactValueSqlFilters`, but a caller could still create those filters with a wrong metric, row selector, unit/scale, form type or source tier. Candidate-to-filter binding alone cannot restore the upstream authority that selected the filters.

The repaired boundary has two independent bindings:

1. `EvidenceRequest + ToolSelectionPlanScopeReference + ExactValueSqlBindingPolicy -> ExactValueSqlExecutionScope -> ExactValueSqlFilters`. Metric derives from the immutable M6.1 `metric_intent`; unit/scale derives from a versioned normalization mapping; row selector, form and source tier derive only from frozen route policy. Missing metric/unit mapping becomes `typed_policy_upgrade_required`, never a caller fallback.
2. `ToolInvocationReceiptReference -> request/plan/snapshot/execution-scope/filter-selector digest`. R.1 still does not read a receipt or a plan registry. The typed references explicitly carry `registry_not_read` and `not_admitted` / `required_not_invoked` states, so no opaque digest is represented as a verified runtime authorization.

`ExactValueSqlExecutionScope` is create-owned and recomputes canonical id/digest on replay. Its filter-selector contract digest includes policy ref/version/digest and the full derived filters. `LocalRetrievalQuery` only exposes a compatibility read-only `exact_value_filters` view; its constructor no longer accepts raw SQL filters.

## Evidence And Required Negative Coverage

- Runtime contracts: `src/sec_agent/canonical_runtime/local_retrieval_skeleton.py`
- Frozen SQL binding policy: `configs/engineering_handoff/point01_m6_3r_1_exact_value_sql_binding_policy_v1_0.json`
- Owner mapping and manifest: `configs/engineering_handoff/point01_m6_3r_1_skeleton_api_owner_mapping_v1_0.json`, `configs/engineering_handoff/point01_m6_3r_1_skeleton_test_manifest_v1_0.json`
- Gate: `scripts/engineering/run_point01_m6_3r_1_local_retrieval_skeleton_gate.py`
- Contract tests: `tests/contract/test_point01_m6_3r_1_local_retrieval_skeleton.py`

The fixture request `metric_intent=(revenue,)` and `unit=USD_millions` resolves only to the frozen policy scope: `us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`, `USD/millions`, `row:consolidated_income_revenue`, `10-K`, `primary_sec`. Wrong metric, unit/scale, row selector, form/source tier, plan digest, snapshot digest, execution-scope digest, filter-selector digest and replay digest all fail closed. Candidate-to-filter and request/plan-to-filter are both declared separately in the manifest.

## Boundary

R.2 remains `not_implemented_pending_separate_approval`. This repair is not M6.3 full or calibrated, does not promote evidence, and does not authorize DuckDB, MCP/direct handlers, ToolInvocation, receipts, external calls, Context, Writer, provider/model/full-chain, business Case mutation or legacy cutover.

## Final Reviewer Acceptance And Residual Risk

The reviewer accepted R.1 and authorized only M6.3R.2 sanitized immutable fixtures. A self-signed `ExactValueSqlBindingPolicy` can still resolve at this non-authoritative layer because R.1 deliberately neither reads a policy registry nor has execution admission. This must never be interpreted as live policy authority. R.2 pins the reviewed policy artifact and rejects alternate self-signed policies; R.3 must add separately approved registry/admission resolution before any SQL adapter read.
