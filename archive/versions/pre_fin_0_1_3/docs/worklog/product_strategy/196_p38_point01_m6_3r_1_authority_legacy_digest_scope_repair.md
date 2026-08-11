# P38 Point01 M6.3R.1 Authority / Legacy / Digest / Scope Repair

## Status

- Date: 2026-07-13
- Reviewer decision being repaired: `reject_and_repair_m6_3r_1_authority_legacy_digest_scope_binding`.
- Current status: superseded by `197_p38_point01_m6_3r_1_exact_value_sql_request_plan_scope_repair.md`; the reviewer found an additional SQL request/plan-to-filter authority bypass, so R.1 is `rejected_pending_exact_sql_scope_repair` until that repair is independently audited.
- Scope: typed R.1 repair only. No local index/graph/SQL read, ToolInvocation, network, model/provider, parser/numeric, promotion, SourceHunter, Context, Writer, full-chain, receipt or canonical-store write occurred.

## Root-Cause Repair

- Removed `agent` as a valid Top-K request origin and removed caller-controlled profile, role and source-type fields. `LegacyEvidenceRequestTopKAdapter` now accepts only a complete immutable M6.1 `EvidenceRequest` plus injected `LegacyTopKMappingRegistry`.
- Added exact compiler-policy and registry ref/version/SHA-256 binding. The frozen registry records actual M6.1 `issuer_metric=3/12` and `relationship_signal=5/12` lowering profiles; `commercial_tracker_metric=1/1` is a typed `commercial_gap_not_retrieval` terminal, never a retrieval profile.
- Enforced SHA-256 syntax for digest references. `TopKPolicyAuditDecision`, `LocalRetrievalQuery`, `CandidateBundleProjection` and `EvidenceGateCandidateProjection` now recompute and verify their own canonical digest/id during `model_validate` replay.
- Bound snapshots to registry ref/version/digest/admission state. Bound every supplied candidate to adapter/id/kind/snapshot/entity/period/source-policy/route/source-role/evidence-role/candidate-kind and required `fixture_supplied_not_retrieved` provenance.
- Extended the future exact-value SQL candidate contract with metric, row selector, unit, scale, form/source tier and source/parser lineage; no SQL read or numeric promotion exists in this point.
- Required Evidence Gate candidate ids to be unique, stable in bundle order, scoped eligible subsets and at most the resolved hard cap (never over five).

## Evidence

- Runtime contract: `src/sec_agent/canonical_runtime/local_retrieval_skeleton.py`
- Frozen registry: `configs/engineering_handoff/point01_m6_3r_1_legacy_topk_mapping_registry_v1_0.json`
- Gate: `scripts/engineering/run_point01_m6_3r_1_local_retrieval_skeleton_gate.py`
- Regression suite: `tests/contract/test_point01_m6_3r_1_local_retrieval_skeleton.py`
- Gate result: `data/manifests/point01_m6_3r_1_local_retrieval_skeleton_gate_result_v1_0.json`；它直接验证同一冻结 registry，digest=`6506a1f1efb2923b9955e363297a8e5a8f871dc3b9df4a3bd526f32f845d4e5b`，避免测试/审计使用不同 authority。

## Verification And Boundary

- Scoped R0 design + repaired R1 + canonical schema suite: `36 passed`.
- R0 design lint and R1 skeleton gate: `pass`.
- Compileall, schema export and JSONL parse are required closeout checks; all execution-side counts remain zero.
- R.2 fixture remains `not_implemented_pending_separate_approval`. This repair does not establish M6.3/M6.5 full or calibrated maturity and does not close M6.
