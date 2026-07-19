from __future__ import annotations

import ast
import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.candidate_bundle import CandidateBundle
from sec_agent.canonical_runtime.evidence_request import EvidenceRequest, EvidenceRequestTopKPolicy
from sec_agent.canonical_runtime.local_retrieval_skeleton import (
    CandidateBundleProjection,
    EvidenceGateCandidateProjection,
    ExactValueSqlBindingCompiler,
    ExactValueSqlBindingPolicy,
    ExactValueSqlExecutionScope,
    ExactValueSqlFilters,
    LegacyEvidenceRequestTopKAdapter,
    LegacyTopKMappingEntry,
    LegacyTopKMappingRegistry,
    LOCAL_RETRIEVAL_SKELETON_MODELS,
    LocalAdapterSnapshot,
    LocalRecallCandidate,
    LocalRetrievalQuery,
    LocalRetrievalSkeletonError,
    M6_1_EVIDENCE_REQUEST_POLICY_REF,
    NonExecutingLocalRetrievalSkeleton,
    ToolInvocationReceiptReference,
    TopKPolicyProfile,
    TopKPolicyRequest,
    TopKPolicyResolver,
    TopKQuantities,
    ToolSelectionPlanScopeReference,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.schema_export import build_schema_bundle


MODULE = ROOT / "src/sec_agent/canonical_runtime/local_retrieval_skeleton.py"
GATE = ROOT / "scripts/engineering/run_point01_m6_3r_1_local_retrieval_skeleton_gate.py"
POLICY = ROOT / "configs/engineering_handoff/point01_m6_1_evidence_request_policy_v1_0.json"
REGISTRY_CONFIG = ROOT / "configs/engineering_handoff/point01_m6_3r_1_legacy_topk_mapping_registry_v1_0.json"
SQL_BINDING_CONFIG = ROOT / "configs/engineering_handoff/point01_m6_3r_1_exact_value_sql_binding_policy_v1_0.json"


def _digest(label: str) -> str:
    return canonical_digest({"fixture": label})


def _compiler_policy_digest() -> str:
    return canonical_digest(json.loads(POLICY.read_text(encoding="utf-8")))


def _evidence_request(*, role: str, source_policy: str | None = None) -> EvidenceRequest:
    fields = {
        "issuer_metric": {
            "accepted_evidence_role": "numeric_fact",
            "evidence_domain": "issuer_disclosure",
            "source_policy": source_policy or "issuer_first",
            "preferred_routes": ("issuer_disclosure_metadata_route",),
            "top_k": 3,
            "candidate_limit": 12,
            "metric_intent": ("revenue",),
            "unit": "USD_millions",
        },
        "relationship_signal": {
            "accepted_evidence_role": "context",
            "evidence_domain": "relationship_graph",
            "source_policy": "relationship_graph_only",
            "preferred_routes": ("relationship_graph_metadata_route",),
            "top_k": 5,
            "candidate_limit": 12,
            "metric_intent": (),
            "unit": None,
        },
        "commercial_tracker_metric": {
            "accepted_evidence_role": "gap_evidence",
            "evidence_domain": "commercial_data_boundary",
            "source_policy": "commercial_gap",
            "preferred_routes": ("commercial_gap_record_route",),
            "top_k": 1,
            "candidate_limit": 1,
            "metric_intent": (),
            "unit": None,
        },
    }[role]
    payload = {
        "tenant_id": "tenant-fixture",
        "project_id": "project-fixture",
        "case_id": "case-fixture",
        "decision_surface_id": "surface-fixture",
        "decision_surface_contract_version_id": "surface:v1",
        "cell_id": f"cell-{role}",
        "cell_version_id": f"cell-{role}:v1",
        "evidence_slot_id": f"slot-{role}",
        "evidence_slot_version_id": f"slot-{role}:v1",
        "requester_role": "research_lead",
        "accepted_evidence_role": fields["accepted_evidence_role"],
        "evidence_domain": fields["evidence_domain"],
        "target_entities": ("NVDA",),
        "target_periods": ("2025-01-26",),
        "metric_intent": fields["metric_intent"],
        "product_intent": (),
        "granularity": "cell_slot",
        "unit": fields["unit"],
        "source_policy": fields["source_policy"],
        "metadata_binding_requirements": ("document_id", "document_version", "section_or_table_ref", "source_authority"),
        "numeric_binding_requirements": ("row_label", "unit", "period", "source_coordinate") if role == "issuer_metric" else (),
        "acceptable_proxy": (),
        "forbidden_substitutions": ("relationship_graph_only",) if role == "issuer_metric" else ("issuer_metric_substitute",) if role == "relationship_signal" else ("public_proxy_as_exact",),
        "preferred_routes": fields["preferred_routes"],
        "fallback_routes": (),
        "topk_policy": {"top_k": fields["top_k"], "candidate_limit": fields["candidate_limit"]},
        "budget": {"tool_call_limit": 0, "elapsed_seconds_limit": 30},
        "stop_condition": "fixture_stop",
        "required": True,
        "compiler_policy_ref": M6_1_EVIDENCE_REQUEST_POLICY_REF,
        "compiled_from_refs": ("contract:v1", "cell:v1", "slot:v1", M6_1_EVIDENCE_REQUEST_POLICY_REF),
        "planning_authority": "shadow",
        "execution_admission": "not_admitted",
    }
    digest = canonical_digest(payload)
    return EvidenceRequest(request_id=f"evidence_request_{digest[:20]}", request_digest=digest, **payload)


def _reowned_evidence_request(request: EvidenceRequest, **overrides: object) -> EvidenceRequest:
    payload = request.model_dump(mode="json")
    payload.pop("request_id")
    payload.pop("request_digest")
    payload.update(overrides)
    digest = canonical_digest(payload)
    return EvidenceRequest(request_id=f"evidence_request_{digest[:20]}", request_digest=digest, **payload)


def _profile(*, source_policy: str, source_type: str, route_id: str, role: str, quantities: TopKQuantities) -> TopKPolicyProfile:
    return TopKPolicyProfile(
        profile_id=f"legacy-{source_policy}-{source_type}",
        profile_version="v1",
        accepted_evidence_role=role,
        source_policy=source_policy,
        selected_route_id=route_id,
        source_type=source_type,
        source_role="issuer_filing" if role == "numeric_fact" else "relationship_graph",
        allowed_candidate_kinds=("top_k_seed", "neighbor_section", "table_context") if role == "numeric_fact" else ("top_k_seed", "neighbor_section"),
        quantities=quantities,
        lowering_profile=True,
        lowering_authority_ref="point01-m6-3r-legacy-mapping-lowering-authority-v1",
        policy_ref="point01-m6-3r-topk-policy-v1",
    )


def _registry() -> LegacyTopKMappingRegistry:
    compiler_digest = _compiler_policy_digest()
    issuer_quantities = TopKQuantities(candidate_bundle_top_k=12, rerank_top_k=8, evidence_gate_candidate_top_k=3)
    relationship_quantities = TopKQuantities(candidate_bundle_top_k=12, rerank_top_k=8, evidence_gate_candidate_top_k=5)
    entries: list[LegacyTopKMappingEntry] = []
    for source_policy, source_type in (
        ("issuer_first", "local_bm25"),
        ("filing_first", "local_bm25"),
        ("official_first", "exact_value_sql"),
    ):
        entries.append(
            LegacyTopKMappingEntry(
                compiler_policy_ref=M6_1_EVIDENCE_REQUEST_POLICY_REF,
                compiler_policy_digest=compiler_digest,
                accepted_evidence_role="numeric_fact",
                source_policy=source_policy,
                required_preferred_route_id="issuer_disclosure_metadata_route",
                legacy_top_k=3,
                legacy_candidate_limit=12,
                terminal_status="resolved",
                terminal_reason="explicit_legacy_issuer_metric_mapping",
                profile=_profile(
                    source_policy=source_policy,
                    source_type=source_type,
                    route_id="issuer_disclosure_metadata_route",
                    role="numeric_fact",
                    quantities=issuer_quantities,
                ),
            )
        )
    entries.append(
        LegacyTopKMappingEntry(
            compiler_policy_ref=M6_1_EVIDENCE_REQUEST_POLICY_REF,
            compiler_policy_digest=compiler_digest,
            accepted_evidence_role="context",
            source_policy="relationship_graph_only",
            required_preferred_route_id="relationship_graph_metadata_route",
            legacy_top_k=5,
            legacy_candidate_limit=12,
            terminal_status="resolved",
            terminal_reason="explicit_legacy_relationship_context_mapping",
            profile=_profile(
                source_policy="relationship_graph_only",
                source_type="relationship_graph",
                route_id="relationship_graph_metadata_route",
                role="context",
                quantities=relationship_quantities,
            ),
        )
    )
    entries.append(
        LegacyTopKMappingEntry(
            compiler_policy_ref=M6_1_EVIDENCE_REQUEST_POLICY_REF,
            compiler_policy_digest=compiler_digest,
            accepted_evidence_role="gap_evidence",
            source_policy="commercial_gap",
            required_preferred_route_id="commercial_gap_record_route",
            legacy_top_k=1,
            legacy_candidate_limit=1,
            terminal_status="typed_commercial_gap",
            terminal_reason="commercial_gap_not_retrieval",
        )
    )
    return LegacyTopKMappingRegistry.create(
        registry_ref="point01-m6-3r-1-legacy-topk-mapping-registry",
        registry_version="v1",
        compiler_policy_ref=M6_1_EVIDENCE_REQUEST_POLICY_REF,
        compiler_policy_digest=compiler_digest,
        entries=tuple(entries),
    )


def _resolved(*, role: str = "issuer_metric", source_policy: str | None = None):
    legacy = _evidence_request(role=role, source_policy=source_policy)
    registry = _registry()
    request = LegacyEvidenceRequestTopKAdapter().map(legacy, registry=registry)
    return legacy, registry, request, TopKPolicyResolver().resolve(request=request, registry=registry)


def _snapshot(*, kind: str = "bm25", source_type: str = "local_bm25") -> LocalAdapterSnapshot:
    return LocalAdapterSnapshot(
        snapshot_id=f"snapshot-{kind}:v1",
        snapshot_registry_ref="point01-local-adapter-snapshot-registry",
        snapshot_registry_version="v1",
        snapshot_digest=_digest(f"snapshot-{kind}"),
        adapter_id=f"adapter-{kind}",
        adapter_kind=kind,  # type: ignore[arg-type]
        source_type=source_type,
    )


def _sql_binding_policy() -> ExactValueSqlBindingPolicy:
    return ExactValueSqlBindingPolicy.model_validate(json.loads(SQL_BINDING_CONFIG.read_text(encoding="utf-8")))


def _sql_plan_scope() -> ToolSelectionPlanScopeReference:
    return ToolSelectionPlanScopeReference(
        tool_selection_plan_id="tool-plan:official-first:v1",
        tool_selection_plan_digest=_digest("tool-plan-official-first"),
        plan_policy_ref="point01-m6-2-tool-selection-plan-policy",
        plan_policy_version="v1",
        plan_policy_digest=_digest("tool-selection-plan-policy"),
        selected_route_id="issuer_disclosure_metadata_route",
    )


def _query(*, kind: str = "bm25", source_policy: str | None = None) -> LocalRetrievalQuery:
    source_policy = source_policy or ("official_first" if kind == "exact_value_sql" else "issuer_first")
    _, _, _, resolved = _resolved(source_policy=source_policy)
    snapshot = _snapshot(kind=kind, source_type=resolved.resolution.resolved_profile.source_type)  # type: ignore[union-attr]
    scope = None
    receipt = None
    plan_id = "tool-plan:v1"
    plan_digest = _digest("tool-plan")
    if kind == "exact_value_sql":
        plan = _sql_plan_scope()
        resolution = ExactValueSqlBindingCompiler().compile(
            evidence_request=resolved.audit.request.evidence_request,
            tool_selection_plan=plan,
            adapter_snapshot=snapshot,
            binding_policy=_sql_binding_policy(),
        )
        assert resolution.status == "resolved"
        assert resolution.execution_scope is not None
        scope = resolution.execution_scope
        plan_id = plan.tool_selection_plan_id
        plan_digest = plan.tool_selection_plan_digest
        receipt = ToolInvocationReceiptReference(
            receipt_id="tool-receipt:v1",
            receipt_version=1,
            receipt_digest=_digest("tool-receipt"),
            request_id=resolved.audit.request.request_id,
            request_digest=resolved.audit.request.request_digest,
            tool_selection_plan_id=plan.tool_selection_plan_id,
            tool_selection_plan_digest=plan.tool_selection_plan_digest,
            adapter_snapshot_id=snapshot.snapshot_id,
            adapter_snapshot_digest=snapshot.snapshot_digest,
            execution_scope_id=scope.execution_scope_id,
            execution_scope_digest=scope.execution_scope_digest,
            exact_filter_selector_contract_digest=scope.exact_filter_selector_contract_digest,
        )
    return LocalRetrievalQuery.create(
        tool_selection_plan_id=plan_id,
        tool_selection_plan_digest=plan_digest,
        adapter_snapshot=snapshot,
        topk=resolved,
        exact_value_execution_scope=scope,
        tool_invocation_receipt_ref=receipt,
    )


def _candidate(query: LocalRetrievalQuery, *, candidate_id: str = "candidate:1", rank: int = 0, **overrides: object) -> LocalRecallCandidate:
    snapshot = query.adapter_snapshot
    payload: dict[str, object] = {
        "candidate_id": candidate_id,
        "adapter_id": snapshot.adapter_id,
        "adapter_kind": snapshot.adapter_kind,
        "adapter_snapshot_id": snapshot.snapshot_id,
        "adapter_snapshot_digest": snapshot.snapshot_digest,
        "source_type": query.source_type,
        "evidence_role": query.evidence_role,
        "document_id": "nvda-10k",
        "document_version": "v1",
        "source_artifact_ref": "source:nvda-10k",
        "source_artifact_digest": _digest(f"source-{candidate_id}"),
        "parser_artifact_ref": "parser:fixture",
        "parser_artifact_digest": _digest(f"parser-{candidate_id}"),
        "index_or_graph_coordinate": "fixture:0",
        "entity_ref": "NVDA",
        "period_ref": "2025-01-26",
        "form_type": "10-K",
        "source_tier": "primary_sec",
        "source_policy_ref": query.source_policy_ref,
        "route_id": query.selected_route_id,
        "source_role": query.source_role,
        "source_authority_rank": 100,
        "source_family": "sec",
        "candidate_kind": "top_k_seed",
        "section_or_table_ref": "table:income_statement",
        "content_ref": f"fixture-content:{candidate_id}",
        "recall_score": 1.0,
        "metadata_rank": rank,
    }
    if snapshot.adapter_kind == "exact_value_sql":
        assert query.exact_value_filters is not None
        payload.update(
            {
                "metric_ref": query.exact_value_filters.metric_ref,
                "row_selector_ref": query.exact_value_filters.row_selector_ref,
                "unit_ref": query.exact_value_filters.unit_ref,
                "scale_ref": query.exact_value_filters.scale_ref,
            }
        )
    payload.update(overrides)
    return LocalRecallCandidate.model_validate(payload)


class _FakeReadOnlyAdapter:
    adapter_id = "injected-fake"

    def __init__(self) -> None:
        self.recall_calls = 0

    def recall(self, query: LocalRetrievalQuery) -> tuple[LocalRecallCandidate, ...]:
        self.recall_calls += 1
        raise AssertionError("R.1 must not invoke a local adapter")


def test_real_m6_1_legacy_3_12_5_12_1_1_have_explicit_mapping_or_terminal_behavior() -> None:
    frozen_registry = LegacyTopKMappingRegistry.model_validate(json.loads(REGISTRY_CONFIG.read_text(encoding="utf-8")))
    assert frozen_registry.model_dump(mode="json") == _registry().model_dump(mode="json")
    issuer, _, issuer_request, issuer_result = _resolved(role="issuer_metric")
    assert issuer_result.resolution.status == "resolved"
    assert issuer_result.resolution.resolved_quantities == TopKQuantities(candidate_bundle_top_k=12, rerank_top_k=8, evidence_gate_candidate_top_k=3)
    assert issuer_request.request_digest == issuer.request_digest
    assert issuer.topk_policy == EvidenceRequestTopKPolicy(top_k=3, candidate_limit=12)

    _, _, _, relationship_result = _resolved(role="relationship_signal")
    assert relationship_result.resolution.status == "resolved"
    assert relationship_result.resolution.resolved_quantities == TopKQuantities(candidate_bundle_top_k=12, rerank_top_k=8, evidence_gate_candidate_top_k=5)

    _, _, _, commercial_result = _resolved(role="commercial_tracker_metric")
    assert commercial_result.resolution.status == "typed_commercial_gap"
    assert commercial_result.resolution.terminal_reason == "commercial_gap_not_retrieval"
    assert commercial_result.resolution.resolved_profile is None


def test_agent_profile_selection_role_spoof_and_unregistered_route_fail_closed() -> None:
    legacy, registry, request, _ = _resolved()
    payload = request.model_dump(mode="json")
    payload["request_origin"] = "agent"
    with pytest.raises(ValidationError):
        TopKPolicyRequest.model_validate(payload)
    assert "profile_id" not in TopKPolicyRequest.model_fields
    assert "source_type" not in TopKPolicyRequest.model_fields

    spoofed = legacy.model_dump(mode="json")
    spoofed["accepted_evidence_role"] = "context"
    with pytest.raises(ValueError, match="legacy_evidence_request_digest_mismatch"):
        LegacyEvidenceRequestTopKAdapter().map(EvidenceRequest.model_validate(spoofed), registry=registry)

    unknown = legacy.model_dump(mode="json")
    unknown["preferred_routes"] = ["unregistered-route"]
    unknown_digest_payload = dict(unknown)
    unknown_digest_payload.pop("request_id")
    unknown_digest_payload.pop("request_digest")
    digest = canonical_digest(unknown_digest_payload)
    unknown["request_digest"] = digest
    unknown["request_id"] = f"evidence_request_{digest[:20]}"
    result = TopKPolicyResolver().resolve(
        request=LegacyEvidenceRequestTopKAdapter().map(EvidenceRequest.model_validate(unknown), registry=registry),
        registry=registry,
    )
    assert result.resolution.status == "typed_policy_upgrade_required"
    assert result.resolution.terminal_reason == "legacy_topk_mapping_not_registered"


def test_legacy_adapter_accepts_complete_immutable_request_not_free_role_or_profile_fields() -> None:
    parameters = tuple(inspect.signature(LegacyEvidenceRequestTopKAdapter.map).parameters)
    assert parameters == ("self", "legacy", "registry")
    request = _evidence_request(role="issuer_metric")
    registry = _registry()
    mapped = LegacyEvidenceRequestTopKAdapter().map(request, registry=registry)
    assert mapped.evidence_request.model_dump(mode="json") == request.model_dump(mode="json")
    assert mapped.compiler_policy_ref == request.compiler_policy_ref
    assert mapped.compiler_policy_digest == registry.compiler_policy_digest


def test_registry_or_compiler_digest_mismatch_is_rejected_without_profile_fallback() -> None:
    _, registry, request, _ = _resolved()
    tampered = request.model_dump(mode="json")
    tampered["policy_registry_digest"] = _digest("wrong-registry")
    result = TopKPolicyResolver().resolve(request=TopKPolicyRequest.model_validate(tampered), registry=registry)
    assert result.resolution.status == "rejected"
    assert result.resolution.terminal_reason == "topk_policy_registry_ref_or_digest_mismatch"


def test_sha256_refs_and_owned_audit_query_projection_digest_replay_are_fail_closed() -> None:
    with pytest.raises(ValidationError):
        LocalAdapterSnapshot(
            snapshot_id="bad",
            snapshot_registry_ref="registry",
            snapshot_registry_version="v1",
            snapshot_digest="not-a-sha",
            adapter_id="adapter",
            adapter_kind="bm25",
            source_type="local_bm25",
        )
    query = _query()
    replay = query.model_dump(mode="json")
    replay["query_digest"] = _digest("forged-query")
    with pytest.raises(ValidationError, match="owned_contract_digest_mismatch"):
        LocalRetrievalQuery.model_validate(replay)

    audit_replay = query.topk_audit.model_dump(mode="json")
    audit_replay["clamp_or_reject_reason"] = "forged"
    with pytest.raises(ValidationError, match="owned_contract_digest_mismatch"):
        type(query.topk_audit).model_validate(audit_replay)

    projection = CandidateBundleProjection.create(query=query, candidates=(_candidate(query),))
    projection_replay = projection.model_dump(mode="json")
    projection_replay["projection_digest"] = _digest("forged-projection")
    with pytest.raises(ValidationError, match="owned_contract_digest_mismatch"):
        CandidateBundleProjection.model_validate(projection_replay)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("adapter_id", "WRONG"),
        ("adapter_snapshot_id", "WRONG"),
        ("adapter_snapshot_digest", _digest("wrong-snapshot")),
        ("entity_ref", "WRONG"),
        ("period_ref", "WRONG"),
        ("source_policy_ref", "WRONG"),
        ("route_id", "WRONG"),
        ("source_type", "WRONG"),
        ("evidence_role", "WRONG"),
        ("candidate_kind", "WRONG"),
    ],
)
def test_candidate_projection_binds_adapter_snapshot_compiler_scope_and_kind(field: str, value: str) -> None:
    query = _query()
    candidate_payload = _candidate(query).model_dump(mode="json")
    candidate_payload[field] = value
    candidate = LocalRecallCandidate.model_validate(candidate_payload)
    with pytest.raises(ValidationError):
        CandidateBundleProjection.create(query=query, candidates=(candidate,))


def test_exact_value_sql_candidate_requires_exact_filter_and_source_parser_lineage() -> None:
    query = _query(kind="exact_value_sql")
    candidate = _candidate(query)
    projection = CandidateBundleProjection.create(query=query, candidates=(candidate,))
    assert projection.candidates[0].candidate_provenance == "fixture_supplied_not_retrieved"

    payload = candidate.model_dump(mode="json")
    payload["metric_ref"] = "wrong_metric"
    with pytest.raises(ValidationError, match="exact_value_sql_candidate_filters_or_lineage_unbound"):
        CandidateBundleProjection.create(query=query, candidates=(LocalRecallCandidate.model_validate(payload),))
    payload = candidate.model_dump(mode="json")
    payload["parser_artifact_digest"] = "not-a-sha"
    with pytest.raises(ValidationError):
        LocalRecallCandidate.model_validate(payload)


def test_exact_value_sql_filters_are_compiled_from_request_plan_and_versioned_policy_only() -> None:
    query = _query(kind="exact_value_sql")
    scope = query.exact_value_execution_scope
    assert scope is not None
    assert query.exact_value_filters == ExactValueSqlFilters(
        entity_ref="NVDA",
        period_ref="2025-01-26",
        metric_ref="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        row_selector_ref="row:consolidated_income_revenue",
        unit_ref="USD",
        scale_ref="millions",
        form_type="10-K",
        source_tier="primary_sec",
    )
    assert scope.tool_selection_plan.registry_read_status == "registry_not_read"
    assert scope.execution_admission == "not_admitted"

    with pytest.raises(TypeError, match="exact_value_filters"):
        LocalRetrievalQuery.create(  # type: ignore[call-arg]
            tool_selection_plan_id=query.tool_selection_plan_id,
            tool_selection_plan_digest=query.tool_selection_plan_digest,
            adapter_snapshot=query.adapter_snapshot,
            topk=_resolved(source_policy="official_first")[3],
            exact_value_filters=query.exact_value_filters,
            tool_invocation_receipt_ref=query.tool_invocation_receipt_ref,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("metric_ref", "TotallyWrongMetric"),
        ("unit_ref", "JPY"),
        ("scale_ref", "ones"),
        ("row_selector_ref", "row:wrong"),
        ("form_type", "8-K"),
        ("source_tier", "untrusted_web"),
    ],
)
def test_exact_value_sql_execution_scope_rejects_caller_filter_rewrites(field: str, value: str) -> None:
    scope = _query(kind="exact_value_sql").exact_value_execution_scope
    assert scope is not None
    replay = scope.model_dump(mode="json")
    replay["filters"][field] = value
    with pytest.raises(ValidationError, match="exact_value_sql_filters_not_deterministically_bound_to_request_and_plan"):
        ExactValueSqlExecutionScope.model_validate(replay)


def test_exact_value_sql_missing_metric_or_unit_mapping_is_typed_policy_upgrade_required() -> None:
    request, _, _, resolved = _resolved(source_policy="official_first")
    snapshot = _snapshot(kind="exact_value_sql", source_type="exact_value_sql")
    compiler = ExactValueSqlBindingCompiler()
    for override, expected_reason in (
        ({"metric_intent": ("unknown_metric",)}, "exact_value_sql_metric_mapping_not_registered"),
        ({"unit": "JPY"}, "exact_value_sql_unit_mapping_not_registered"),
    ):
        altered = _reowned_evidence_request(request, **override)
        result = compiler.compile(
            evidence_request=altered,
            tool_selection_plan=_sql_plan_scope(),
            adapter_snapshot=snapshot,
            binding_policy=_sql_binding_policy(),
        )
        assert result.status == "typed_policy_upgrade_required"
        assert result.execution_scope is None
        assert result.terminal_reason == expected_reason
    assert resolved.resolution.status == "resolved"


@pytest.mark.parametrize(
    ("receipt_field", "wrong_value"),
    [
        ("tool_selection_plan_digest", _digest("wrong-plan")),
        ("adapter_snapshot_digest", _digest("wrong-snapshot")),
        ("execution_scope_digest", _digest("wrong-execution-scope")),
        ("exact_filter_selector_contract_digest", _digest("wrong-filter-contract")),
    ],
)
def test_exact_value_sql_receipt_binds_request_plan_snapshot_and_filter_execution_scope(
    receipt_field: str,
    wrong_value: str,
) -> None:
    query = _query(kind="exact_value_sql")
    replay = query.model_dump(mode="json")
    replay["tool_invocation_receipt_ref"][receipt_field] = wrong_value
    with pytest.raises(ValidationError, match="exact_value_sql_tool_invocation_receipt_execution_scope_unbound"):
        LocalRetrievalQuery.model_validate(replay)


def test_exact_value_sql_plan_route_and_scope_replay_tamper_fail_closed() -> None:
    query = _query(kind="exact_value_sql")
    scope = query.exact_value_execution_scope
    assert scope is not None
    wrong_plan = scope.model_dump(mode="json")
    wrong_plan["tool_selection_plan"]["selected_route_id"] = "unapproved-route"
    with pytest.raises(ValidationError, match="exact_value_sql_plan_route_policy_mismatch"):
        ExactValueSqlExecutionScope.model_validate(wrong_plan)

    forged = scope.model_dump(mode="json")
    forged["execution_scope_digest"] = _digest("forged-execution-scope")
    with pytest.raises(ValidationError, match="owned_contract_digest_mismatch"):
        ExactValueSqlExecutionScope.model_validate(forged)


def test_gate_projection_requires_unique_stable_subset_and_recomputed_digest() -> None:
    query = _query()
    candidates = (_candidate(query, candidate_id="candidate:1", rank=0), _candidate(query, candidate_id="candidate:2", rank=1))
    projection = CandidateBundleProjection.create(query=query, candidates=candidates)
    gate = EvidenceGateCandidateProjection.create(bundle_projection=projection, candidate_ids=("candidate:1", "candidate:2"))
    assert gate.evidence_gate_candidate_top_k == 3
    with pytest.raises(ValidationError, match="evidence_gate_candidate_projection_duplicate_candidate_id"):
        EvidenceGateCandidateProjection.create(bundle_projection=projection, candidate_ids=("candidate:1", "candidate:1"))
    with pytest.raises(ValidationError, match="evidence_gate_candidate_projection_not_stable_eligible_bundle_subset"):
        EvidenceGateCandidateProjection.create(bundle_projection=projection, candidate_ids=("candidate:2", "candidate:1"))
    replay = gate.model_dump(mode="json")
    replay["candidate_ids"] = ["candidate:2"]
    with pytest.raises(ValidationError, match="owned_contract_digest_mismatch"):
        EvidenceGateCandidateProjection.model_validate(replay)


def test_projection_maps_only_to_existing_candidate_bundle_and_fixture_state_is_explicit() -> None:
    query = _query()
    adapter = _FakeReadOnlyAdapter()
    skeleton = NonExecutingLocalRetrievalSkeleton(adapter=adapter)
    projection = skeleton.project_from_supplied_candidates(query=query, candidates=(_candidate(query),))
    bundle = projection.to_existing_candidate_bundle(retrieval_policy_ref="point01-m6-3r-skeleton-policy-v1")
    assert isinstance(bundle, CandidateBundle)
    assert bundle.status == "fixture_supplied_not_retrieved"
    assert adapter.recall_calls == 0

    payload = projection.model_dump(mode="json")
    payload["retrieval_status"] = "not_executed"
    with pytest.raises(ValidationError):
        CandidateBundleProjection.model_validate(payload)


def test_second_state_persistence_and_missing_injected_adapter_fail_closed() -> None:
    query = _query()
    projection = CandidateBundleProjection.create(query=query, candidates=(_candidate(query),))
    payload = projection.model_dump(mode="json")
    payload["persistence_authorized"] = True
    with pytest.raises(ValidationError):
        CandidateBundleProjection.model_validate(payload)
    with pytest.raises(LocalRetrievalSkeletonError, match="injected_read_only_adapter_required"):
        NonExecutingLocalRetrievalSkeleton(adapter=None)  # type: ignore[arg-type]


def test_module_import_contract_constructor_and_schema_export_are_side_effect_free() -> None:
    tree = ast.parse(MODULE.read_text(encoding="utf-8"))
    imports = {
        alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names
    } | {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    forbidden = {"duckdb", "requests", "sqlite3", "sec_agent.ledger_store", "retrieval.bm25_retriever", "sec_agent.mcp_tool_registry"}
    assert not forbidden & imports
    adapter = _FakeReadOnlyAdapter()
    NonExecutingLocalRetrievalSkeleton(adapter=adapter)
    assert adapter.recall_calls == 0
    exported = build_schema_bundle()["models"]
    for model in LOCAL_RETRIEVAL_SKELETON_MODELS:
        assert model.__name__ in exported


def test_owner_mapping_and_r2_fixture_plan_preserve_repair_and_nonexecution_boundary() -> None:
    mapping = json.loads((ROOT / "configs/engineering_handoff/point01_m6_3r_1_skeleton_api_owner_mapping_v1_0.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "configs/engineering_handoff/point01_m6_3r_1_skeleton_test_manifest_v1_0.json").read_text(encoding="utf-8"))
    assert mapping["execution_stage"] == "skeleton_independently_accepted_non_authoritative"
    assert any("agent profile selection" in item for item in mapping["repair_scope"])
    assert any("request/plan -> filter" in item for item in mapping["repair_scope"])
    assert manifest["binding_coverage"]["request_plan_to_filter"].startswith("M6.1 request")
    assert any("candidate -> SQL filter" in item for item in manifest["required_regressions"])
    assert manifest["r2_fixture_plan"]["status"] == "not_implemented_pending_separate_approval"
    assert manifest["expected_counts"]["adapter_execution_count"] == 0


def test_skeleton_gate_reports_schema_hashes_and_zero_side_effect_counts(tmp_path: Path) -> None:
    output = tmp_path / "m6_3r_1_gate.json"
    completed = subprocess.run([sys.executable, str(GATE), "--output", str(output)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert len(result["schema_hashes"]) == len(LOCAL_RETRIEVAL_SKELETON_MODELS)
    assert result["legacy_topk_mapping_registry_digest"] == json.loads(REGISTRY_CONFIG.read_text(encoding="utf-8"))["registry_digest"]
    assert all(value == 0 for value in result["zero_execution_counts"].values())
