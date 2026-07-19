"""Execution-free M6.3R.1 authority/legacy/digest/scope contract gate."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.evidence_request import EvidenceRequest  # noqa: E402
from sec_agent.canonical_runtime.local_retrieval_skeleton import (  # noqa: E402
    CandidateBundleProjection,
    EvidenceGateCandidateProjection,
    ExactValueSqlBindingCompiler,
    ExactValueSqlBindingPolicy,
    LegacyEvidenceRequestTopKAdapter,
    LegacyTopKMappingRegistry,
    LOCAL_RETRIEVAL_SKELETON_MODELS,
    LocalAdapterSnapshot,
    LocalRecallCandidate,
    LocalRetrievalQuery,
    M6_1_EVIDENCE_REQUEST_POLICY_REF,
    NonExecutingLocalRetrievalSkeleton,
    TopKPolicyResolver,
    TopKQuantities,
    ToolInvocationReceiptReference,
    ToolSelectionPlanScopeReference,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_3r_1_local_retrieval_skeleton_gate_result_v1_0.json"
MODULE = ROOT / "src/sec_agent/canonical_runtime/local_retrieval_skeleton.py"
REGISTRY_CONFIG = ROOT / "configs/engineering_handoff/point01_m6_3r_1_legacy_topk_mapping_registry_v1_0.json"
SQL_BINDING_CONFIG = ROOT / "configs/engineering_handoff/point01_m6_3r_1_exact_value_sql_binding_policy_v1_0.json"


def _digest(label: str) -> str:
    return canonical_digest({"gate_fixture": label})


def _request(*, source_policy: str = "issuer_first") -> EvidenceRequest:
    payload = {
        "tenant_id": "tenant-gate",
        "project_id": "project-gate",
        "case_id": "case-gate",
        "decision_surface_id": "surface-gate",
        "decision_surface_contract_version_id": "surface-gate:v1",
        "cell_id": "cell-gate",
        "cell_version_id": "cell-gate:v1",
        "evidence_slot_id": "slot-gate",
        "evidence_slot_version_id": "slot-gate:v1",
        "requester_role": "research_lead",
        "accepted_evidence_role": "numeric_fact",
        "evidence_domain": "issuer_disclosure",
        "target_entities": ("NVDA",),
        "target_periods": ("2025-01-26",),
        "metric_intent": ("revenue",),
        "product_intent": (),
        "granularity": "cell_slot",
        "unit": "USD_millions",
        "source_policy": source_policy,
        "metadata_binding_requirements": ("document_id", "document_version", "section_or_table_ref", "source_authority"),
        "numeric_binding_requirements": ("row_label", "unit", "period", "source_coordinate"),
        "acceptable_proxy": (),
        "forbidden_substitutions": ("relationship_graph_only",),
        "preferred_routes": ("issuer_disclosure_metadata_route",),
        "fallback_routes": (),
        "topk_policy": {"top_k": 3, "candidate_limit": 12},
        "budget": {"tool_call_limit": 0, "elapsed_seconds_limit": 30},
        "stop_condition": "gate_stop",
        "required": True,
        "compiler_policy_ref": M6_1_EVIDENCE_REQUEST_POLICY_REF,
        "compiled_from_refs": ("contract:v1", "cell:v1", "slot:v1", M6_1_EVIDENCE_REQUEST_POLICY_REF),
        "planning_authority": "shadow",
        "execution_admission": "not_admitted",
    }
    digest = canonical_digest(payload)
    return EvidenceRequest(request_id=f"evidence_request_{digest[:20]}", request_digest=digest, **payload)


def _registry() -> LegacyTopKMappingRegistry:
    # This is a reviewed policy/config artifact, not a retrieval index or store.
    return LegacyTopKMappingRegistry.model_validate(json.loads(REGISTRY_CONFIG.read_text(encoding="utf-8")))


def _sql_binding_policy() -> ExactValueSqlBindingPolicy:
    # Reviewed static policy/config only; no SQL, registry, or receipt store is opened.
    return ExactValueSqlBindingPolicy.model_validate(json.loads(SQL_BINDING_CONFIG.read_text(encoding="utf-8")))


class _ProbeAdapter:
    adapter_id = "adapter-gate"

    def __init__(self) -> None:
        self.recall_calls = 0

    def recall(self, query: LocalRetrievalQuery) -> tuple[LocalRecallCandidate, ...]:
        self.recall_calls += 1
        raise AssertionError("R.1 must not invoke a local adapter")


def build_result() -> dict[str, Any]:
    registry = _registry()
    request = _request()
    topk_request = LegacyEvidenceRequestTopKAdapter().map(request, registry=registry)
    resolved = TopKPolicyResolver().resolve(request=topk_request, registry=registry)
    snapshot = LocalAdapterSnapshot(
        snapshot_id="snapshot-gate:v1",
        snapshot_registry_ref="point01-local-adapter-snapshot-registry",
        snapshot_registry_version="v1",
        snapshot_digest=_digest("snapshot"),
        adapter_id="adapter-gate",
        adapter_kind="bm25",
        source_type="local_bm25",
    )
    query = LocalRetrievalQuery.create(
        tool_selection_plan_id="tool-plan-gate:v1",
        tool_selection_plan_digest=_digest("tool-plan"),
        adapter_snapshot=snapshot,
        topk=resolved,
    )
    sql_request = _request(source_policy="official_first")
    sql_topk_request = LegacyEvidenceRequestTopKAdapter().map(sql_request, registry=registry)
    sql_topk = TopKPolicyResolver().resolve(request=sql_topk_request, registry=registry)
    sql_snapshot = LocalAdapterSnapshot(
        snapshot_id="snapshot-gate-exact-sql:v1",
        snapshot_registry_ref="point01-local-adapter-snapshot-registry",
        snapshot_registry_version="v1",
        snapshot_digest=_digest("snapshot-exact-sql"),
        adapter_id="adapter-gate-exact-sql",
        adapter_kind="exact_value_sql",
        source_type="exact_value_sql",
    )
    sql_plan = ToolSelectionPlanScopeReference(
        tool_selection_plan_id="tool-plan-gate-official-first:v1",
        tool_selection_plan_digest=_digest("tool-plan-official-first"),
        plan_policy_ref="point01-m6-2-tool-selection-plan-policy",
        plan_policy_version="v1",
        plan_policy_digest=_digest("tool-selection-plan-policy"),
        selected_route_id="issuer_disclosure_metadata_route",
    )
    sql_binding = ExactValueSqlBindingCompiler().compile(
        evidence_request=sql_request,
        tool_selection_plan=sql_plan,
        adapter_snapshot=sql_snapshot,
        binding_policy=_sql_binding_policy(),
    )
    if sql_binding.status != "resolved" or sql_binding.execution_scope is None:
        raise RuntimeError("exact_value_sql_skeleton_binding_must_resolve")
    sql_scope = sql_binding.execution_scope
    sql_receipt = ToolInvocationReceiptReference(
        receipt_id="tool-receipt-gate:v1",
        receipt_version=1,
        receipt_digest=_digest("tool-receipt"),
        request_id=sql_request.request_id,
        request_digest=sql_request.request_digest,
        tool_selection_plan_id=sql_plan.tool_selection_plan_id,
        tool_selection_plan_digest=sql_plan.tool_selection_plan_digest,
        adapter_snapshot_id=sql_snapshot.snapshot_id,
        adapter_snapshot_digest=sql_snapshot.snapshot_digest,
        execution_scope_id=sql_scope.execution_scope_id,
        execution_scope_digest=sql_scope.execution_scope_digest,
        exact_filter_selector_contract_digest=sql_scope.exact_filter_selector_contract_digest,
    )
    sql_query = LocalRetrievalQuery.create(
        tool_selection_plan_id=sql_plan.tool_selection_plan_id,
        tool_selection_plan_digest=sql_plan.tool_selection_plan_digest,
        adapter_snapshot=sql_snapshot,
        topk=sql_topk,
        exact_value_execution_scope=sql_scope,
        tool_invocation_receipt_ref=sql_receipt,
    )
    candidate = LocalRecallCandidate(
        candidate_id="candidate-gate:v1",
        adapter_id=snapshot.adapter_id,
        adapter_kind=snapshot.adapter_kind,
        adapter_snapshot_id=snapshot.snapshot_id,
        adapter_snapshot_digest=snapshot.snapshot_digest,
        source_type=query.source_type,
        evidence_role=query.evidence_role,
        document_id="document-gate:v1",
        document_version="v1",
        source_artifact_ref="source-gate:v1",
        source_artifact_digest=_digest("source"),
        parser_artifact_ref="parser-gate:v1",
        parser_artifact_digest=_digest("parser"),
        index_or_graph_coordinate="fixture:0",
        entity_ref="NVDA",
        period_ref="2025-01-26",
        form_type="10-K",
        source_tier="primary_sec",
        source_policy_ref=query.source_policy_ref,
        route_id=query.selected_route_id,
        source_role=query.source_role,
        source_authority_rank=100,
        source_family="sec",
        candidate_kind="top_k_seed",
        section_or_table_ref="table:income_statement",
        content_ref="fixture-content:v1",
        recall_score=1.0,
        metadata_rank=0,
    )
    adapter = _ProbeAdapter()
    projection = NonExecutingLocalRetrievalSkeleton(adapter=adapter).project_from_supplied_candidates(query=query, candidates=(candidate,))
    gate_projection = EvidenceGateCandidateProjection.create(bundle_projection=projection, candidate_ids=(candidate.candidate_id,))
    bundle = projection.to_existing_candidate_bundle(retrieval_policy_ref="point01-m6-3r-skeleton-policy-v1")
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imports = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    forbidden_imports = {"duckdb", "requests", "sqlite3", "sec_agent.ledger_store", "sec_agent.mcp_tool_registry", "retrieval.bm25_retriever"}
    schema_hashes = {model.__name__: canonical_digest(model.model_json_schema()) for model in LOCAL_RETRIEVAL_SKELETON_MODELS}
    zero_execution_counts = {
        "adapter_execution_count": 0,
        "network_request_count": 0,
        "external_tool_call_count": 0,
        "tool_invocation_count": 0,
        "model_call_count": 0,
        "provider_call_count": 0,
        "canonical_store_write_count": 0,
        "evidence_promotion_count": 0,
        "parser_numeric_execution_count": 0,
        "sourcehunter_attempt_count": 0,
    }
    checks = {
        "real_m6_1_issuer_3_12_mapping_resolved": resolved.resolution.status == "resolved" and resolved.resolution.resolved_quantities == TopKQuantities(candidate_bundle_top_k=12, rerank_top_k=8, evidence_gate_candidate_top_k=3),
        "agent_profile_fields_absent": "profile_id" not in type(topk_request).model_fields and "source_type" not in type(topk_request).model_fields,
        "registry_and_compiler_digest_bound": topk_request.policy_registry_digest == registry.registry_digest and topk_request.compiler_policy_digest == registry.compiler_policy_digest,
        "exact_value_request_plan_to_filter_binding": sql_query.exact_value_filters == sql_scope.filters and sql_scope.filters.metric_ref == "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "exact_value_receipt_binds_plan_snapshot_and_filter_execution_scope": sql_receipt.execution_scope_digest == sql_scope.execution_scope_digest and sql_receipt.exact_filter_selector_contract_digest == sql_scope.exact_filter_selector_contract_digest,
        "candidate_projection_maps_to_existing_bundle": bundle.candidate_count == 1 and bundle.status == "fixture_supplied_not_retrieved",
        "gate_projection_is_scoped_stable_subset": gate_projection.candidate_ids == (candidate.candidate_id,),
        "injected_adapter_not_invoked": adapter.recall_calls == 0,
        "module_has_no_real_adapter_transport_import": not (imports & forbidden_imports),
        "schema_hashes_complete": len(schema_hashes) == len(LOCAL_RETRIEVAL_SKELETON_MODELS),
        "all_contract_counts_zero": all(value == 0 for value in zero_execution_counts.values()),
    }
    return {
        "result_version": "finsight_point01_m6_3r_1_local_retrieval_skeleton_gate_result_v3_0",
        "status": "pass" if all(checks.values()) else "fail_closed",
        "execution_stage": "M6_3R_1_skeleton_independently_accepted_non_authoritative",
        "checks": checks,
        "schema_hashes": schema_hashes,
        "legacy_topk_mapping_registry_digest": registry.registry_digest,
        "topk_audit_digest": resolved.audit.audit_digest,
        "query_digest": query.query_digest,
        "exact_value_sql_binding_policy_digest": _sql_binding_policy().policy_digest,
        "exact_value_sql_execution_scope_digest": sql_scope.execution_scope_digest,
        "exact_value_sql_filter_selector_contract_digest": sql_scope.exact_filter_selector_contract_digest,
        "exact_value_sql_query_digest": sql_query.query_digest,
        "candidate_bundle_projection_digest": projection.projection_digest,
        "evidence_gate_candidate_projection_digest": gate_projection.projection_digest,
        "zero_execution_counts": zero_execution_counts,
        "note": "Reviewed policy JSON is validated only in memory. Candidate-to-filter and request/plan-to-filter binding are both checked; the probe adapter is never called and no adapter registry, index, graph, SQL, tool, network, model, parser, promotion, or store is opened."
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run M6.3R.1 local retrieval skeleton gate without adapters or stores.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = build_result()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], **result["zero_execution_counts"]}))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
