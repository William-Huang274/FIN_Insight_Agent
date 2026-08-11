"""M6.3R.1 authority-bound local-retrieval contracts.

This module is deliberately data-source inert.  It defines deterministic,
serializable contracts and injected read-only seams only.  It imports no
retriever, graph, database, MCP handler, HTTP client, or canonical store.

R.1 does not select a retrieval profile from agent input.  The only bridge
from M6.1 is a full immutable :class:`EvidenceRequest` plus a separately
injected, digest-bound legacy mapping registry.  R.2/R.3 remain responsible
for fixtures and any real adapter invocation respectively.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import Field, model_validator

from .candidate_bundle import CandidateBundle, CandidateMetadata
from .evidence_request import EvidenceRequest
from .models import StrictModel, canonical_digest


SHA256_PATTERN = r"^[0-9a-f]{64}$"
M6_1_EVIDENCE_REQUEST_POLICY_REF = "point01-m6-1-evidence-request-policy-v1"


class LocalRetrievalSkeletonError(ValueError):
    """Raised when the non-executing M6.3R skeleton contract is violated."""


def _require_owned_identity(*, identifier: str, digest: str, prefix: str, payload: dict[str, Any]) -> None:
    """Reject replay/tamper of a value that this module owns and hashes."""

    expected_digest = canonical_digest(payload)
    if digest != expected_digest:
        raise ValueError("owned_contract_digest_mismatch")
    if identifier != f"{prefix}_{expected_digest[:20]}":
        raise ValueError("owned_contract_id_mismatch")


def _evidence_request_payload(request: EvidenceRequest) -> dict[str, Any]:
    payload = request.model_dump(mode="json")
    payload.pop("request_id")
    payload.pop("request_digest")
    return payload


def _require_exact_m6_1_request(request: EvidenceRequest) -> None:
    """Verify the compiler-owned request without mutating its legacy digest."""

    expected_digest = canonical_digest(_evidence_request_payload(request))
    if request.request_digest != expected_digest:
        raise ValueError("legacy_evidence_request_digest_mismatch")
    if request.request_id != f"evidence_request_{expected_digest[:20]}":
        raise ValueError("legacy_evidence_request_id_mismatch")
    if request.execution_admission != "not_admitted":
        raise ValueError("legacy_evidence_request_execution_admission_must_be_not_admitted")


class TopKQuantities(StrictModel):
    """Three intentionally separate capacities; Evidence Gate is always <= 5."""

    candidate_bundle_top_k: int = Field(ge=1)
    rerank_top_k: int = Field(ge=1)
    evidence_gate_candidate_top_k: int = Field(ge=1, le=5)

    @model_validator(mode="after")
    def require_monotonic_capacity(self) -> "TopKQuantities":
        if self.evidence_gate_candidate_top_k > self.rerank_top_k:
            raise ValueError("evidence_gate_candidate_top_k_exceeds_rerank_top_k")
        if self.rerank_top_k > self.candidate_bundle_top_k:
            raise ValueError("rerank_top_k_exceeds_candidate_bundle_top_k")
        return self


class TopKPolicyProfile(StrictModel):
    """A registry-owned resolved route/profile, never an agent request parameter."""

    profile_id: str = Field(min_length=1)
    profile_version: str = Field(min_length=1)
    accepted_evidence_role: str = Field(min_length=1)
    source_policy: str = Field(min_length=1)
    selected_route_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_role: str = Field(min_length=1)
    allowed_candidate_kinds: tuple[str, ...] = Field(min_length=1)
    quantities: TopKQuantities
    lowering_profile: bool = False
    lowering_authority_ref: str | None = None
    policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_tech02_bounds_or_explicit_lowering(self) -> "TopKPolicyProfile":
        values = self.quantities
        if values.candidate_bundle_top_k > 50 or values.rerank_top_k > 20:
            raise ValueError("topk_profile_may_not_raise_tech02_maximum")
        if self.lowering_profile:
            if not str(self.lowering_authority_ref or "").strip():
                raise ValueError("lowering_profile_authority_ref_required")
            return self
        if not 20 <= values.candidate_bundle_top_k <= 50:
            raise ValueError("candidate_bundle_top_k_outside_standard_20_50_bounds")
        if not 8 <= values.rerank_top_k <= 20:
            raise ValueError("rerank_top_k_outside_standard_8_20_bounds")
        return self


class LegacyTopKMappingEntry(StrictModel):
    """One exact M6.1 compiler role/source/top-k route in the frozen registry."""

    compiler_policy_ref: str = Field(min_length=1)
    compiler_policy_digest: str = Field(pattern=SHA256_PATTERN)
    accepted_evidence_role: str = Field(min_length=1)
    source_policy: str = Field(min_length=1)
    required_preferred_route_id: str = Field(min_length=1)
    legacy_top_k: int = Field(ge=1)
    legacy_candidate_limit: int = Field(ge=1)
    terminal_status: Literal["resolved", "typed_policy_upgrade_required", "typed_commercial_gap"]
    terminal_reason: str = Field(min_length=1)
    profile: TopKPolicyProfile | None = None

    @model_validator(mode="after")
    def require_terminal_profile_consistency(self) -> "LegacyTopKMappingEntry":
        if self.terminal_status == "resolved" and self.profile is None:
            raise ValueError("resolved_legacy_mapping_requires_profile")
        if self.terminal_status != "resolved" and self.profile is not None:
            raise ValueError("terminal_legacy_mapping_must_not_supply_profile")
        if self.profile is not None and (
            self.profile.accepted_evidence_role,
            self.profile.source_policy,
            self.profile.selected_route_id,
        ) != (
            self.accepted_evidence_role,
            self.source_policy,
            self.required_preferred_route_id,
        ):
            raise ValueError("legacy_mapping_profile_scope_mismatch")
        return self


class LegacyTopKMappingRegistry(StrictModel):
    """Immutable mapping authority supplied to R.1; R.1 never opens a registry."""

    registry_ref: str = Field(min_length=1)
    registry_version: str = Field(min_length=1)
    registry_digest: str = Field(pattern=SHA256_PATTERN)
    compiler_policy_ref: str = Field(min_length=1)
    compiler_policy_digest: str = Field(pattern=SHA256_PATTERN)
    entries: tuple[LegacyTopKMappingEntry, ...] = Field(min_length=1)
    admission_state: Literal["compiler_policy_bound_not_resolved"] = "compiler_policy_bound_not_resolved"

    @model_validator(mode="after")
    def require_registry_digest_and_unique_routes(self) -> "LegacyTopKMappingRegistry":
        payload = {
            "registry_ref": self.registry_ref,
            "registry_version": self.registry_version,
            "compiler_policy_ref": self.compiler_policy_ref,
            "compiler_policy_digest": self.compiler_policy_digest,
            "entries": [entry.model_dump(mode="json") for entry in self.entries],
            "admission_state": self.admission_state,
        }
        expected = canonical_digest(payload)
        if self.registry_digest != expected:
            raise ValueError("legacy_topk_mapping_registry_digest_mismatch")
        keys = [
            (
                item.compiler_policy_ref,
                item.compiler_policy_digest,
                item.accepted_evidence_role,
                item.source_policy,
                item.required_preferred_route_id,
                item.legacy_top_k,
                item.legacy_candidate_limit,
            )
            for item in self.entries
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate_legacy_topk_mapping_registry_route")
        if any(
            (entry.compiler_policy_ref, entry.compiler_policy_digest)
            != (self.compiler_policy_ref, self.compiler_policy_digest)
            for entry in self.entries
        ):
            raise ValueError("legacy_topk_mapping_registry_compiler_policy_mismatch")
        return self

    @classmethod
    def create(
        cls,
        *,
        registry_ref: str,
        registry_version: str,
        compiler_policy_ref: str,
        compiler_policy_digest: str,
        entries: tuple[LegacyTopKMappingEntry, ...],
    ) -> "LegacyTopKMappingRegistry":
        payload = {
            "registry_ref": registry_ref,
            "registry_version": registry_version,
            "compiler_policy_ref": compiler_policy_ref,
            "compiler_policy_digest": compiler_policy_digest,
            "entries": [entry.model_dump(mode="json") for entry in entries],
            "admission_state": "compiler_policy_bound_not_resolved",
        }
        return cls(registry_digest=canonical_digest(payload), **payload)

    def lookup(self, request: EvidenceRequest) -> LegacyTopKMappingEntry | None:
        _require_exact_m6_1_request(request)
        matches = tuple(
            entry
            for entry in self.entries
            if (
                entry.compiler_policy_ref == request.compiler_policy_ref
                and entry.accepted_evidence_role == request.accepted_evidence_role
                and entry.source_policy == request.source_policy
                and entry.legacy_top_k == request.topk_policy.top_k
                and entry.legacy_candidate_limit == request.topk_policy.candidate_limit
                and entry.required_preferred_route_id in request.preferred_routes
            )
        )
        if len(matches) > 1:
            raise LocalRetrievalSkeletonError("ambiguous_legacy_topk_mapping_registry_route")
        return matches[0] if matches else None


class TopKPolicyRequest(StrictModel):
    """A compiler-bound R.1 resolution request; agent origin/profile fields do not exist."""

    evidence_request: EvidenceRequest
    request_origin: Literal["legacy_evidence_request"] = "legacy_evidence_request"
    policy_registry_ref: str = Field(min_length=1)
    policy_registry_version: str = Field(min_length=1)
    policy_registry_digest: str = Field(pattern=SHA256_PATTERN)
    compiler_policy_ref: str = Field(min_length=1)
    compiler_policy_digest: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def require_exact_compiler_request(self) -> "TopKPolicyRequest":
        _require_exact_m6_1_request(self.evidence_request)
        if self.compiler_policy_ref != self.evidence_request.compiler_policy_ref:
            raise ValueError("topk_request_compiler_policy_ref_unbound")
        return self

    @property
    def request_id(self) -> str:
        return self.evidence_request.request_id

    @property
    def request_digest(self) -> str:
        return self.evidence_request.request_digest


class TopKPolicyResolution(StrictModel):
    status: Literal["resolved", "rejected", "typed_policy_upgrade_required", "typed_commercial_gap"]
    resolved_profile: TopKPolicyProfile | None = None
    resolved_quantities: TopKQuantities | None = None
    terminal_reason: str | None = None

    @model_validator(mode="after")
    def require_consistent_terminal_state(self) -> "TopKPolicyResolution":
        if self.status == "resolved":
            if self.resolved_profile is None or self.resolved_quantities != self.resolved_profile.quantities:
                raise ValueError("resolved_topk_policy_requires_exact_profile_quantities")
            if self.terminal_reason is not None:
                raise ValueError("resolved_topk_policy_must_not_have_terminal_reason")
        elif self.resolved_profile is not None or self.resolved_quantities is not None or not str(self.terminal_reason or "").strip():
            raise ValueError("terminal_topk_policy_requires_reason_without_profile")
        return self


class TopKPolicyAuditDecision(StrictModel):
    """Create-owned audit object that validates its digest again on replay."""

    audit_id: str = Field(min_length=1)
    audit_digest: str = Field(pattern=SHA256_PATTERN)
    request: TopKPolicyRequest
    resolution: TopKPolicyResolution
    clamp_or_reject_reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_recomputed_owned_digest(self) -> "TopKPolicyAuditDecision":
        payload = {
            "request": self.request.model_dump(mode="json"),
            "resolution": self.resolution.model_dump(mode="json"),
            "clamp_or_reject_reason": self.clamp_or_reject_reason,
        }
        _require_owned_identity(
            identifier=self.audit_id,
            digest=self.audit_digest,
            prefix="topk_policy_audit",
            payload=payload,
        )
        return self

    @classmethod
    def create(cls, *, request: TopKPolicyRequest, resolution: TopKPolicyResolution) -> "TopKPolicyAuditDecision":
        payload = {
            "request": request.model_dump(mode="json"),
            "resolution": resolution.model_dump(mode="json"),
            "clamp_or_reject_reason": resolution.terminal_reason or "none",
        }
        digest = canonical_digest(payload)
        return cls(audit_id=f"topk_policy_audit_{digest[:20]}", audit_digest=digest, **payload)


class TopKResolutionResult(StrictModel):
    resolution: TopKPolicyResolution
    audit: TopKPolicyAuditDecision
    adapter_execution_count: Literal[0] = 0
    external_tool_call_count: Literal[0] = 0
    network_request_count: Literal[0] = 0
    model_call_count: Literal[0] = 0
    canonical_store_write_count: Literal[0] = 0


class LegacyEvidenceRequestTopKAdapter:
    """Maps only a complete immutable M6.1 request through an injected registry."""

    def map(self, legacy: EvidenceRequest, *, registry: LegacyTopKMappingRegistry) -> TopKPolicyRequest:
        _require_exact_m6_1_request(legacy)
        # The registry is not read from disk here; callers inject an immutable value.
        return TopKPolicyRequest(
            evidence_request=legacy,
            policy_registry_ref=registry.registry_ref,
            policy_registry_version=registry.registry_version,
            policy_registry_digest=registry.registry_digest,
            compiler_policy_ref=registry.compiler_policy_ref,
            compiler_policy_digest=registry.compiler_policy_digest,
        )


class TopKPolicyResolver:
    """Pure resolver.  It trusts neither agent fields nor a caller-provided profile."""

    @staticmethod
    def _result(*, request: TopKPolicyRequest, resolution: TopKPolicyResolution) -> TopKResolutionResult:
        return TopKResolutionResult(resolution=resolution, audit=TopKPolicyAuditDecision.create(request=request, resolution=resolution))

    def resolve(self, *, request: TopKPolicyRequest, registry: LegacyTopKMappingRegistry) -> TopKResolutionResult:
        if (
            request.policy_registry_ref,
            request.policy_registry_version,
            request.policy_registry_digest,
            request.compiler_policy_ref,
            request.compiler_policy_digest,
        ) != (
            registry.registry_ref,
            registry.registry_version,
            registry.registry_digest,
            registry.compiler_policy_ref,
            registry.compiler_policy_digest,
        ):
            return self._result(
                request=request,
                resolution=TopKPolicyResolution(status="rejected", terminal_reason="topk_policy_registry_ref_or_digest_mismatch"),
            )
        mapping = registry.lookup(request.evidence_request)
        if mapping is None:
            return self._result(
                request=request,
                resolution=TopKPolicyResolution(status="typed_policy_upgrade_required", terminal_reason="legacy_topk_mapping_not_registered"),
            )
        if mapping.terminal_status != "resolved":
            return self._result(
                request=request,
                resolution=TopKPolicyResolution(status=mapping.terminal_status, terminal_reason=mapping.terminal_reason),
            )
        assert mapping.profile is not None
        return self._result(
            request=request,
            resolution=TopKPolicyResolution(
                status="resolved",
                resolved_profile=mapping.profile,
                resolved_quantities=mapping.profile.quantities,
            ),
        )


class ToolInvocationReceiptReference(StrictModel):
    """Opaque, unconsumed reference only; R.1 neither reads nor invokes a tool."""

    receipt_id: str = Field(min_length=1)
    receipt_version: int = Field(ge=1)
    receipt_digest: str = Field(pattern=SHA256_PATTERN)
    request_id: str = Field(min_length=1)
    request_digest: str = Field(pattern=SHA256_PATTERN)
    tool_selection_plan_id: str = Field(min_length=1)
    tool_selection_plan_digest: str = Field(pattern=SHA256_PATTERN)
    adapter_snapshot_id: str = Field(min_length=1)
    adapter_snapshot_digest: str = Field(pattern=SHA256_PATTERN)
    execution_scope_id: str = Field(min_length=1)
    execution_scope_digest: str = Field(pattern=SHA256_PATTERN)
    exact_filter_selector_contract_digest: str = Field(pattern=SHA256_PATTERN)
    registry_read_status: Literal["registry_not_read"] = "registry_not_read"
    admission_status: Literal["required_not_invoked"] = "required_not_invoked"


class ExactValueSqlFilters(StrictModel):
    entity_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    metric_ref: str = Field(min_length=1)
    row_selector_ref: str = Field(min_length=1)
    unit_ref: str = Field(min_length=1)
    scale_ref: str = Field(min_length=1)
    form_type: str = Field(min_length=1)
    source_tier: str = Field(min_length=1)


class ExactValueSqlMetricBinding(StrictModel):
    """One immutable compiler metric intent to exact SQL metric mapping."""

    metric_intent: str = Field(min_length=1)
    metric_ref: str = Field(min_length=1)


class ExactValueSqlUnitScaleBinding(StrictModel):
    """One immutable compiler unit to normalized SQL unit/scale mapping."""

    request_unit: str = Field(min_length=1)
    unit_ref: str = Field(min_length=1)
    scale_ref: str = Field(min_length=1)


class ExactValueSqlBindingPolicy(StrictModel):
    """Versioned, policy-owned selector contract; it never reads a registry in R.1."""

    policy_ref: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    policy_digest: str = Field(pattern=SHA256_PATTERN)
    compiler_policy_ref: str = Field(min_length=1)
    accepted_evidence_role: str = Field(min_length=1)
    source_policy: str = Field(min_length=1)
    selected_route_id: str = Field(min_length=1)
    source_type: Literal["exact_value_sql"] = "exact_value_sql"
    row_selector_ref: str = Field(min_length=1)
    form_type: str = Field(min_length=1)
    source_tier: str = Field(min_length=1)
    metric_bindings: tuple[ExactValueSqlMetricBinding, ...] = Field(min_length=1)
    unit_scale_bindings: tuple[ExactValueSqlUnitScaleBinding, ...] = Field(min_length=1)
    registry_read_status: Literal["registry_not_read"] = "registry_not_read"
    execution_admission: Literal["not_admitted"] = "not_admitted"

    @model_validator(mode="after")
    def require_recomputed_policy_digest_and_unique_mappings(self) -> "ExactValueSqlBindingPolicy":
        if self.compiler_policy_ref != M6_1_EVIDENCE_REQUEST_POLICY_REF:
            raise ValueError("exact_value_sql_binding_policy_compiler_ref_mismatch")
        if len({binding.metric_intent for binding in self.metric_bindings}) != len(self.metric_bindings):
            raise ValueError("exact_value_sql_metric_binding_must_be_unique")
        if len({binding.request_unit for binding in self.unit_scale_bindings}) != len(self.unit_scale_bindings):
            raise ValueError("exact_value_sql_unit_scale_binding_must_be_unique")
        payload = self.model_dump(mode="json", exclude={"policy_digest"})
        if self.policy_digest != canonical_digest(payload):
            raise ValueError("exact_value_sql_binding_policy_digest_mismatch")
        return self

    @classmethod
    def create(
        cls,
        *,
        policy_ref: str,
        policy_version: str,
        compiler_policy_ref: str,
        accepted_evidence_role: str,
        source_policy: str,
        selected_route_id: str,
        row_selector_ref: str,
        form_type: str,
        source_tier: str,
        metric_bindings: tuple[ExactValueSqlMetricBinding, ...],
        unit_scale_bindings: tuple[ExactValueSqlUnitScaleBinding, ...],
    ) -> "ExactValueSqlBindingPolicy":
        payload = {
            "policy_ref": policy_ref,
            "policy_version": policy_version,
            "compiler_policy_ref": compiler_policy_ref,
            "accepted_evidence_role": accepted_evidence_role,
            "source_policy": source_policy,
            "selected_route_id": selected_route_id,
            "source_type": "exact_value_sql",
            "row_selector_ref": row_selector_ref,
            "form_type": form_type,
            "source_tier": source_tier,
            "metric_bindings": [binding.model_dump(mode="json") for binding in metric_bindings],
            "unit_scale_bindings": [binding.model_dump(mode="json") for binding in unit_scale_bindings],
            "registry_read_status": "registry_not_read",
            "execution_admission": "not_admitted",
        }
        return cls(policy_digest=canonical_digest(payload), **payload)


class LocalAdapterSnapshot(StrictModel):
    """External registry reference only; snapshot bytes are neither opened nor hashed here."""

    snapshot_id: str = Field(min_length=1)
    snapshot_registry_ref: str = Field(min_length=1)
    snapshot_registry_version: str = Field(min_length=1)
    snapshot_digest: str = Field(pattern=SHA256_PATTERN)
    adapter_id: str = Field(min_length=1)
    adapter_kind: Literal["bm25", "object_bm25", "relationship_graph", "exact_value_sql"]
    source_type: str = Field(min_length=1)
    immutable: Literal[True] = True
    read_only: Literal[True] = True
    admission_state: Literal["not_admitted"] = "not_admitted"
    execution_authorized: Literal[False] = False


class ToolSelectionPlanScopeReference(StrictModel):
    """Typed external plan reference, explicitly not resolved from a registry in R.1."""

    tool_selection_plan_id: str = Field(min_length=1)
    tool_selection_plan_digest: str = Field(pattern=SHA256_PATTERN)
    plan_policy_ref: str = Field(min_length=1)
    plan_policy_version: str = Field(min_length=1)
    plan_policy_digest: str = Field(pattern=SHA256_PATTERN)
    selected_route_id: str = Field(min_length=1)
    registry_read_status: Literal["registry_not_read"] = "registry_not_read"
    execution_admission: Literal["not_admitted"] = "not_admitted"


def _resolve_exact_value_sql_filters(
    *,
    evidence_request: EvidenceRequest,
    tool_selection_plan: ToolSelectionPlanScopeReference,
    binding_policy: ExactValueSqlBindingPolicy,
) -> ExactValueSqlFilters:
    """Derive every SQL filter from compiler request + immutable route policy only."""

    _require_exact_m6_1_request(evidence_request)
    if (
        evidence_request.compiler_policy_ref,
        evidence_request.accepted_evidence_role,
        evidence_request.source_policy,
    ) != (
        binding_policy.compiler_policy_ref,
        binding_policy.accepted_evidence_role,
        binding_policy.source_policy,
    ):
        raise LocalRetrievalSkeletonError("exact_value_sql_request_policy_scope_mismatch")
    if binding_policy.selected_route_id not in evidence_request.preferred_routes:
        raise LocalRetrievalSkeletonError("exact_value_sql_policy_route_not_allowed_by_request")
    if tool_selection_plan.selected_route_id != binding_policy.selected_route_id:
        raise LocalRetrievalSkeletonError("exact_value_sql_plan_route_policy_mismatch")
    if len(evidence_request.target_entities) != 1 or len(evidence_request.target_periods) != 1:
        raise LocalRetrievalSkeletonError("exact_value_sql_requires_single_entity_and_period")
    if len(evidence_request.metric_intent) != 1:
        raise LocalRetrievalSkeletonError("exact_value_sql_requires_single_metric_intent")
    metric_intent = evidence_request.metric_intent[0]
    metric_binding = next((item for item in binding_policy.metric_bindings if item.metric_intent == metric_intent), None)
    if metric_binding is None:
        raise LocalRetrievalSkeletonError("exact_value_sql_metric_mapping_not_registered")
    if evidence_request.unit is None:
        raise LocalRetrievalSkeletonError("exact_value_sql_unit_mapping_not_registered")
    unit_binding = next((item for item in binding_policy.unit_scale_bindings if item.request_unit == evidence_request.unit), None)
    if unit_binding is None:
        raise LocalRetrievalSkeletonError("exact_value_sql_unit_mapping_not_registered")
    return ExactValueSqlFilters(
        entity_ref=evidence_request.target_entities[0],
        period_ref=evidence_request.target_periods[0],
        metric_ref=metric_binding.metric_ref,
        row_selector_ref=binding_policy.row_selector_ref,
        unit_ref=unit_binding.unit_ref,
        scale_ref=unit_binding.scale_ref,
        form_type=binding_policy.form_type,
        source_tier=binding_policy.source_tier,
    )


class ExactValueSqlExecutionScope(StrictModel):
    """Create-owned request -> plan -> filter scope.  No registry or SQL access occurs."""

    execution_scope_id: str = Field(min_length=1)
    execution_scope_digest: str = Field(pattern=SHA256_PATTERN)
    evidence_request: EvidenceRequest
    tool_selection_plan: ToolSelectionPlanScopeReference
    adapter_snapshot: LocalAdapterSnapshot
    binding_policy: ExactValueSqlBindingPolicy
    filters: ExactValueSqlFilters
    exact_filter_selector_contract_digest: str = Field(pattern=SHA256_PATTERN)
    registry_read_status: Literal["registry_not_read"] = "registry_not_read"
    execution_admission: Literal["not_admitted"] = "not_admitted"
    persistence_authorized: Literal[False] = False

    @staticmethod
    def _filter_selector_contract_digest(*, binding_policy: ExactValueSqlBindingPolicy, filters: ExactValueSqlFilters) -> str:
        return canonical_digest(
            {
                "binding_policy_ref": binding_policy.policy_ref,
                "binding_policy_version": binding_policy.policy_version,
                "binding_policy_digest": binding_policy.policy_digest,
                "filters": filters.model_dump(mode="json"),
            }
        )

    @model_validator(mode="after")
    def require_request_plan_snapshot_and_filter_binding(self) -> "ExactValueSqlExecutionScope":
        expected_filters = _resolve_exact_value_sql_filters(
            evidence_request=self.evidence_request,
            tool_selection_plan=self.tool_selection_plan,
            binding_policy=self.binding_policy,
        )
        if self.adapter_snapshot.adapter_kind != "exact_value_sql" or self.adapter_snapshot.source_type != self.binding_policy.source_type:
            raise ValueError("exact_value_sql_execution_scope_snapshot_kind_or_source_mismatch")
        if self.adapter_snapshot.admission_state != "not_admitted":
            raise ValueError("exact_value_sql_execution_scope_snapshot_must_be_not_admitted")
        if self.filters != expected_filters:
            raise ValueError("exact_value_sql_filters_not_deterministically_bound_to_request_and_plan")
        expected_contract_digest = self._filter_selector_contract_digest(binding_policy=self.binding_policy, filters=self.filters)
        if self.exact_filter_selector_contract_digest != expected_contract_digest:
            raise ValueError("exact_value_sql_filter_selector_contract_digest_mismatch")
        payload = self.model_dump(
            mode="json",
            exclude={"execution_scope_id", "execution_scope_digest"},
        )
        _require_owned_identity(
            identifier=self.execution_scope_id,
            digest=self.execution_scope_digest,
            prefix="exact_value_sql_execution_scope",
            payload=payload,
        )
        return self

    @classmethod
    def create(
        cls,
        *,
        evidence_request: EvidenceRequest,
        tool_selection_plan: ToolSelectionPlanScopeReference,
        adapter_snapshot: LocalAdapterSnapshot,
        binding_policy: ExactValueSqlBindingPolicy,
    ) -> "ExactValueSqlExecutionScope":
        filters = _resolve_exact_value_sql_filters(
            evidence_request=evidence_request,
            tool_selection_plan=tool_selection_plan,
            binding_policy=binding_policy,
        )
        contract_digest = cls._filter_selector_contract_digest(binding_policy=binding_policy, filters=filters)
        payload = {
            "evidence_request": evidence_request.model_dump(mode="json"),
            "tool_selection_plan": tool_selection_plan.model_dump(mode="json"),
            "adapter_snapshot": adapter_snapshot.model_dump(mode="json"),
            "binding_policy": binding_policy.model_dump(mode="json"),
            "filters": filters.model_dump(mode="json"),
            "exact_filter_selector_contract_digest": contract_digest,
            "registry_read_status": "registry_not_read",
            "execution_admission": "not_admitted",
            "persistence_authorized": False,
        }
        digest = canonical_digest(payload)
        return cls(
            execution_scope_id=f"exact_value_sql_execution_scope_{digest[:20]}",
            execution_scope_digest=digest,
            **payload,
        )


class ExactValueSqlBindingResolution(StrictModel):
    """Explicit terminal result when the frozen policy cannot map a compiler request."""

    status: Literal["resolved", "typed_policy_upgrade_required"]
    execution_scope: ExactValueSqlExecutionScope | None = None
    terminal_reason: str | None = None

    @model_validator(mode="after")
    def require_terminal_consistency(self) -> "ExactValueSqlBindingResolution":
        if self.status == "resolved":
            if self.execution_scope is None or self.terminal_reason is not None:
                raise ValueError("resolved_exact_value_sql_binding_requires_scope_only")
        elif self.execution_scope is not None or not str(self.terminal_reason or "").strip():
            raise ValueError("terminal_exact_value_sql_binding_requires_reason_without_scope")
        return self


class ExactValueSqlBindingCompiler:
    """Pure policy compiler; missing policy coverage produces a typed terminal outcome."""

    def compile(
        self,
        *,
        evidence_request: EvidenceRequest,
        tool_selection_plan: ToolSelectionPlanScopeReference,
        adapter_snapshot: LocalAdapterSnapshot,
        binding_policy: ExactValueSqlBindingPolicy,
    ) -> ExactValueSqlBindingResolution:
        try:
            return ExactValueSqlBindingResolution(
                status="resolved",
                execution_scope=ExactValueSqlExecutionScope.create(
                    evidence_request=evidence_request,
                    tool_selection_plan=tool_selection_plan,
                    adapter_snapshot=adapter_snapshot,
                    binding_policy=binding_policy,
                ),
            )
        except LocalRetrievalSkeletonError as exc:
            if str(exc) in {"exact_value_sql_metric_mapping_not_registered", "exact_value_sql_unit_mapping_not_registered"}:
                return ExactValueSqlBindingResolution(status="typed_policy_upgrade_required", terminal_reason=str(exc))
            raise


class LocalRetrievalQuery(StrictModel):
    """Create-owned query with replay-safe digest and registry-bound scope."""

    query_id: str = Field(min_length=1)
    query_digest: str = Field(pattern=SHA256_PATTERN)
    topk_audit: TopKPolicyAuditDecision
    tool_selection_plan_id: str = Field(min_length=1)
    tool_selection_plan_digest: str = Field(pattern=SHA256_PATTERN)
    adapter_snapshot: LocalAdapterSnapshot
    adapter_snapshot_digest: str = Field(pattern=SHA256_PATTERN)
    evidence_role: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    selected_route_id: str = Field(min_length=1)
    source_role: str = Field(min_length=1)
    eligible_candidate_kinds: tuple[str, ...] = Field(min_length=1)
    target_entities: tuple[str, ...] = Field(min_length=1)
    target_periods: tuple[str, ...] = Field(min_length=1)
    source_policy_ref: str = Field(min_length=1)
    exact_value_execution_scope: ExactValueSqlExecutionScope | None = None
    tool_invocation_receipt_ref: ToolInvocationReceiptReference | None = None
    allow_relaxed_filter_fallback: Literal[False] = False
    execution_admission: Literal["not_admitted"] = "not_admitted"
    persistence_authorized: Literal[False] = False

    @property
    def request_id(self) -> str:
        return self.topk_audit.request.request_id

    @property
    def request_digest(self) -> str:
        return self.topk_audit.request.request_digest

    @property
    def resolved_topk_policy(self) -> TopKQuantities:
        resolution = self.topk_audit.resolution
        if resolution.status != "resolved" or resolution.resolved_quantities is None:
            raise LocalRetrievalSkeletonError("resolved_topk_policy_required_for_query")
        return resolution.resolved_quantities

    @property
    def exact_value_filters(self) -> ExactValueSqlFilters | None:
        """Compatibility read-only view; filters are owned by the execution scope."""

        return self.exact_value_execution_scope.filters if self.exact_value_execution_scope else None

    @model_validator(mode="after")
    def require_recomputed_digest_snapshot_and_sql_contract(self) -> "LocalRetrievalQuery":
        profile = self.topk_audit.resolution.resolved_profile
        if profile is None:
            raise ValueError("local_retrieval_query_requires_resolved_topk_profile")
        if self.adapter_snapshot_digest != self.adapter_snapshot.snapshot_digest:
            raise ValueError("adapter_snapshot_digest_unbound")
        if (
            self.evidence_role,
            self.source_type,
            self.selected_route_id,
            self.source_role,
            self.source_policy_ref,
            self.eligible_candidate_kinds,
        ) != (
            profile.accepted_evidence_role,
            profile.source_type,
            profile.selected_route_id,
            profile.source_role,
            profile.source_policy,
            profile.allowed_candidate_kinds,
        ):
            raise ValueError("local_retrieval_query_registry_profile_scope_mismatch")
        request = self.topk_audit.request.evidence_request
        if (
            self.evidence_role,
            self.source_policy_ref,
            self.target_entities,
            self.target_periods,
        ) != (
            request.accepted_evidence_role,
            request.source_policy,
            request.target_entities,
            request.target_periods,
        ):
            raise ValueError("local_retrieval_query_compiler_request_scope_mismatch")
        if self.source_type != self.adapter_snapshot.source_type:
            raise ValueError("adapter_snapshot_source_type_mismatch")
        if self.adapter_snapshot.admission_state != "not_admitted":
            raise ValueError("adapter_snapshot_must_be_not_admitted")
        if self.adapter_snapshot.adapter_kind == "exact_value_sql":
            if self.exact_value_execution_scope is None:
                raise ValueError("exact_value_sql_execution_scope_required")
            if self.tool_invocation_receipt_ref is None:
                raise ValueError("exact_value_sql_tool_invocation_receipt_ref_required")
            scope = self.exact_value_execution_scope
            if scope.evidence_request.model_dump(mode="json") != request.model_dump(mode="json"):
                raise ValueError("exact_value_sql_execution_scope_request_unbound")
            if (
                self.tool_selection_plan_id,
                self.tool_selection_plan_digest,
                self.adapter_snapshot.model_dump(mode="json"),
            ) != (
                scope.tool_selection_plan.tool_selection_plan_id,
                scope.tool_selection_plan.tool_selection_plan_digest,
                scope.adapter_snapshot.model_dump(mode="json"),
            ):
                raise ValueError("exact_value_sql_execution_scope_query_plan_or_snapshot_unbound")
            if (self.source_type, self.selected_route_id, self.source_policy_ref) != (
                scope.binding_policy.source_type,
                scope.binding_policy.selected_route_id,
                scope.binding_policy.source_policy,
            ):
                raise ValueError("exact_value_sql_execution_scope_query_route_unbound")
            receipt = self.tool_invocation_receipt_ref
            if (
                receipt.request_id,
                receipt.request_digest,
                receipt.tool_selection_plan_id,
                receipt.tool_selection_plan_digest,
                receipt.adapter_snapshot_id,
                receipt.adapter_snapshot_digest,
                receipt.execution_scope_id,
                receipt.execution_scope_digest,
                receipt.exact_filter_selector_contract_digest,
            ) != (
                self.request_id,
                self.request_digest,
                scope.tool_selection_plan.tool_selection_plan_id,
                scope.tool_selection_plan.tool_selection_plan_digest,
                scope.adapter_snapshot.snapshot_id,
                scope.adapter_snapshot.snapshot_digest,
                scope.execution_scope_id,
                scope.execution_scope_digest,
                scope.exact_filter_selector_contract_digest,
            ):
                raise ValueError("exact_value_sql_tool_invocation_receipt_execution_scope_unbound")
        elif self.exact_value_execution_scope is not None or self.tool_invocation_receipt_ref is not None:
            raise ValueError("sql_execution_scope_and_receipt_only_allowed_for_exact_value_sql")
        payload = {
            "topk_audit": self.topk_audit.model_dump(mode="json"),
            "tool_selection_plan_id": self.tool_selection_plan_id,
            "tool_selection_plan_digest": self.tool_selection_plan_digest,
            "adapter_snapshot": self.adapter_snapshot.model_dump(mode="json"),
            "adapter_snapshot_digest": self.adapter_snapshot_digest,
            "evidence_role": self.evidence_role,
            "source_type": self.source_type,
            "selected_route_id": self.selected_route_id,
            "source_role": self.source_role,
            "eligible_candidate_kinds": self.eligible_candidate_kinds,
            "target_entities": self.target_entities,
            "target_periods": self.target_periods,
            "source_policy_ref": self.source_policy_ref,
            "exact_value_execution_scope": self.exact_value_execution_scope.model_dump(mode="json") if self.exact_value_execution_scope else None,
            "tool_invocation_receipt_ref": self.tool_invocation_receipt_ref.model_dump(mode="json") if self.tool_invocation_receipt_ref else None,
            "allow_relaxed_filter_fallback": False,
            "execution_admission": "not_admitted",
            "persistence_authorized": False,
        }
        _require_owned_identity(
            identifier=self.query_id,
            digest=self.query_digest,
            prefix="local_retrieval_query",
            payload=payload,
        )
        return self

    @classmethod
    def create(
        cls,
        *,
        tool_selection_plan_id: str,
        tool_selection_plan_digest: str,
        adapter_snapshot: LocalAdapterSnapshot,
        topk: TopKResolutionResult,
        exact_value_execution_scope: ExactValueSqlExecutionScope | None = None,
        tool_invocation_receipt_ref: ToolInvocationReceiptReference | None = None,
    ) -> "LocalRetrievalQuery":
        resolution = topk.resolution
        profile = resolution.resolved_profile
        request = topk.audit.request.evidence_request
        if resolution.status != "resolved" or resolution.resolved_quantities is None or profile is None:
            raise LocalRetrievalSkeletonError("resolved_topk_policy_required_for_query")
        payload = {
            "topk_audit": topk.audit.model_dump(mode="json"),
            "tool_selection_plan_id": tool_selection_plan_id,
            "tool_selection_plan_digest": tool_selection_plan_digest,
            "adapter_snapshot": adapter_snapshot.model_dump(mode="json"),
            "adapter_snapshot_digest": adapter_snapshot.snapshot_digest,
            "evidence_role": request.accepted_evidence_role,
            "source_type": profile.source_type,
            "selected_route_id": profile.selected_route_id,
            "source_role": profile.source_role,
            "eligible_candidate_kinds": profile.allowed_candidate_kinds,
            "target_entities": request.target_entities,
            "target_periods": request.target_periods,
            "source_policy_ref": request.source_policy,
            "exact_value_execution_scope": exact_value_execution_scope.model_dump(mode="json") if exact_value_execution_scope else None,
            "tool_invocation_receipt_ref": tool_invocation_receipt_ref.model_dump(mode="json") if tool_invocation_receipt_ref else None,
            "allow_relaxed_filter_fallback": False,
            "execution_admission": "not_admitted",
            "persistence_authorized": False,
        }
        digest = canonical_digest(payload)
        return cls(query_id=f"local_retrieval_query_{digest[:20]}", query_digest=digest, **payload)


class LocalRecallCandidate(StrictModel):
    """Supplied fixture metadata only; source bytes and retrieved values are absent."""

    candidate_id: str = Field(min_length=1)
    candidate_provenance: Literal["fixture_supplied_not_retrieved"] = "fixture_supplied_not_retrieved"
    adapter_id: str = Field(min_length=1)
    adapter_kind: Literal["bm25", "object_bm25", "relationship_graph", "exact_value_sql"]
    adapter_snapshot_id: str = Field(min_length=1)
    adapter_snapshot_digest: str = Field(pattern=SHA256_PATTERN)
    source_type: str = Field(min_length=1)
    evidence_role: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    document_version: str = Field(min_length=1)
    source_artifact_ref: str = Field(min_length=1)
    source_artifact_digest: str = Field(pattern=SHA256_PATTERN)
    parser_artifact_ref: str = Field(min_length=1)
    parser_artifact_digest: str = Field(pattern=SHA256_PATTERN)
    index_or_graph_coordinate: str = Field(min_length=1)
    entity_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    form_type: str = Field(min_length=1)
    source_tier: str = Field(min_length=1)
    source_policy_ref: str = Field(min_length=1)
    route_id: str = Field(min_length=1)
    source_role: str = Field(min_length=1)
    source_authority_rank: int = Field(ge=0)
    source_family: str = Field(min_length=1)
    candidate_kind: str = Field(min_length=1)
    metric_ref: str | None = None
    row_selector_ref: str | None = None
    unit_ref: str | None = None
    scale_ref: str | None = None
    section_or_table_ref: str = Field(min_length=1)
    page_ref: str | None = None
    row_ref: str | None = None
    parent_section_ref: str | None = None
    previous_ref: str | None = None
    next_ref: str | None = None
    # ``page_ref``/``row_ref`` identify a candidate coordinate.  They cannot
    # authorize directional expansion.  R.2 fixture relations therefore use
    # the typed direction-specific fields below; R.3 must preserve this
    # distinction when an adapter is eventually admitted.
    previous_page_ref: str | None = None
    next_page_ref: str | None = None
    previous_row_ref: str | None = None
    next_row_ref: str | None = None
    content_ref: str = Field(min_length=1)
    content_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)
    recall_score: float
    metadata_rank: int = Field(ge=0)


class DeterministicRerankDecision(StrictModel):
    candidate_id: str = Field(min_length=1)
    reranker_profile_id: str = Field(min_length=1)
    reranker_profile_version: str = Field(min_length=1)
    reranker_kind: Literal["deterministic_zero_model_baseline"] = "deterministic_zero_model_baseline"
    filter_pass: bool
    rerank_score: float
    score_components: tuple[str, ...] = Field(min_length=1)
    tie_break_key: str = Field(min_length=1)
    exclusion_reason: str | None = None
    model_call_count: Literal[0] = 0


class NeighborExpansionPlan(StrictModel):
    seed_candidate_id: str = Field(min_length=1)
    adapter_snapshot_digest: str = Field(pattern=SHA256_PATTERN)
    previous_section_ref: str | None = None
    next_section_ref: str | None = None
    parent_section_ref: str | None = None
    table_ref: str | None = None
    previous_page_ref: str | None = None
    next_page_ref: str | None = None
    previous_row_refs: tuple[str, ...] = ()
    next_row_refs: tuple[str, ...] = ()
    stop_reason: str = Field(min_length=1)
    expansion_execution_count: Literal[0] = 0


def _require_candidate_matches_query(*, candidate: LocalRecallCandidate, query: LocalRetrievalQuery) -> None:
    snapshot = query.adapter_snapshot
    if (
        candidate.adapter_id,
        candidate.adapter_kind,
        candidate.adapter_snapshot_id,
        candidate.adapter_snapshot_digest,
        candidate.source_type,
        candidate.evidence_role,
        candidate.source_policy_ref,
        candidate.route_id,
        candidate.source_role,
    ) != (
        snapshot.adapter_id,
        snapshot.adapter_kind,
        snapshot.snapshot_id,
        snapshot.snapshot_digest,
        query.source_type,
        query.evidence_role,
        query.source_policy_ref,
        query.selected_route_id,
        query.source_role,
    ):
        raise ValueError("candidate_projection_query_scope_mismatch")
    if candidate.entity_ref not in query.target_entities or candidate.period_ref not in query.target_periods:
        raise ValueError("candidate_projection_entity_or_period_scope_mismatch")
    if candidate.candidate_kind not in query.eligible_candidate_kinds:
        raise ValueError("candidate_projection_kind_not_eligible_for_query")
    if snapshot.adapter_kind == "exact_value_sql":
        filters = query.exact_value_filters
        if filters is None:
            raise ValueError("exact_value_sql_query_filters_missing")
        if (
            candidate.metric_ref,
            candidate.row_selector_ref,
            candidate.unit_ref,
            candidate.scale_ref,
            candidate.form_type,
            candidate.source_tier,
            candidate.entity_ref,
            candidate.period_ref,
        ) != (
            filters.metric_ref,
            filters.row_selector_ref,
            filters.unit_ref,
            filters.scale_ref,
            filters.form_type,
            filters.source_tier,
            filters.entity_ref,
            filters.period_ref,
        ):
            raise ValueError("exact_value_sql_candidate_filters_or_lineage_unbound")


class CandidateBundleProjection(StrictModel):
    """Ephemeral projection that maps only to the existing ``CandidateBundle``."""

    projection_id: str = Field(min_length=1)
    projection_digest: str = Field(pattern=SHA256_PATTERN)
    query: LocalRetrievalQuery
    candidates: tuple[LocalRecallCandidate, ...] = ()
    retrieval_status: Literal["fixture_supplied_not_retrieved"] = "fixture_supplied_not_retrieved"
    execution_admission: Literal["not_admitted"] = "not_admitted"
    persistence_authorized: Literal[False] = False
    promotion_authorized: Literal[False] = False
    writer_citable: Literal[False] = False

    @model_validator(mode="after")
    def require_bound_ephemeral_candidates_and_recomputed_digest(self) -> "CandidateBundleProjection":
        if len(self.candidates) > self.query.resolved_topk_policy.candidate_bundle_top_k:
            raise ValueError("candidate_bundle_projection_over_topk_cap")
        ids = tuple(candidate.candidate_id for candidate in self.candidates)
        if len(ids) != len(set(ids)):
            raise ValueError("candidate_bundle_projection_duplicate_candidate_id")
        if self.candidates != tuple(sorted(self.candidates, key=lambda item: (item.metadata_rank, item.candidate_id))):
            raise ValueError("candidate_bundle_projection_candidates_not_stably_ordered")
        for candidate in self.candidates:
            _require_candidate_matches_query(candidate=candidate, query=self.query)
        payload = {
            "query": self.query.model_dump(mode="json"),
            "candidates": [candidate.model_dump(mode="json") for candidate in self.candidates],
            "retrieval_status": "fixture_supplied_not_retrieved",
            "execution_admission": "not_admitted",
            "persistence_authorized": False,
            "promotion_authorized": False,
            "writer_citable": False,
        }
        _require_owned_identity(
            identifier=self.projection_id,
            digest=self.projection_digest,
            prefix="candidate_bundle_projection",
            payload=payload,
        )
        return self

    @classmethod
    def create(cls, *, query: LocalRetrievalQuery, candidates: tuple[LocalRecallCandidate, ...] = ()) -> "CandidateBundleProjection":
        payload = {
            "query": query.model_dump(mode="json"),
            "candidates": [candidate.model_dump(mode="json") for candidate in candidates],
            "retrieval_status": "fixture_supplied_not_retrieved",
            "execution_admission": "not_admitted",
            "persistence_authorized": False,
            "promotion_authorized": False,
            "writer_citable": False,
        }
        digest = canonical_digest(payload)
        return cls(projection_id=f"candidate_bundle_projection_{digest[:20]}", projection_digest=digest, **payload)

    def to_existing_candidate_bundle(self, *, retrieval_policy_ref: str) -> CandidateBundle:
        metadata = tuple(
            CandidateMetadata(
                candidate_id=candidate.candidate_id,
                document_id=candidate.document_id,
                document_version=candidate.document_version,
                source_snapshot_ref=f"{candidate.source_artifact_ref}:{candidate.source_artifact_digest}",
                source_policy_ref=candidate.source_policy_ref,
                route_id=candidate.route_id,
                source_role=candidate.source_role,
                source_authority_rank=candidate.source_authority_rank,
                entity_ref=candidate.entity_ref,
                period_ref=candidate.period_ref,
                candidate_kind=candidate.candidate_kind,
                section_or_table_ref=candidate.section_or_table_ref,
                metadata_rank=candidate.metadata_rank,
                content_ref=candidate.content_ref,
            )
            for candidate in self.candidates
        )
        top_k_candidate_ids = tuple(
            candidate.candidate_id for candidate in metadata if candidate.candidate_kind == "top_k_seed"
        )[: self.query.resolved_topk_policy.candidate_bundle_top_k]
        neighbor_candidate_ids = tuple(candidate.candidate_id for candidate in metadata if candidate.candidate_kind == "neighbor_section")
        table_context_candidate_ids = tuple(candidate.candidate_id for candidate in metadata if candidate.candidate_kind == "table_context")
        payload = {
            "request_id": self.query.request_id,
            "request_digest": self.query.request_digest,
            "tool_selection_plan_id": self.query.tool_selection_plan_id,
            "tool_selection_plan_digest": self.query.tool_selection_plan_digest,
            "metadata_snapshot_id": self.query.adapter_snapshot.snapshot_id,
            "metadata_snapshot_digest": self.query.adapter_snapshot_digest,
            "retrieval_policy_ref": retrieval_policy_ref,
            "status": "fixture_supplied_not_retrieved",
            "exhaustion_status": "not_attempted",
            "typed_gap_codes": (),
            "candidates": [candidate.model_dump(mode="json") for candidate in metadata],
            "top_k_candidate_ids": top_k_candidate_ids,
            "neighbor_candidate_ids": neighbor_candidate_ids,
            "table_context_candidate_ids": table_context_candidate_ids,
            "candidate_count": len(metadata),
            "execution_admission": "not_admitted",
            "persistence_admission": "not_admitted",
        }
        digest = canonical_digest(payload)
        return CandidateBundle(bundle_id=f"candidate_bundle_{digest[:20]}", bundle_digest=digest, **payload)


class EvidenceGateCandidateProjection(StrictModel):
    """A stable subset of a scoped fixture projection; never an Evidence decision."""

    projection_id: str = Field(min_length=1)
    projection_digest: str = Field(pattern=SHA256_PATTERN)
    bundle_projection: CandidateBundleProjection
    candidate_ids: tuple[str, ...] = ()
    evidence_gate_candidate_top_k: int = Field(ge=1, le=5)
    persistence_authorized: Literal[False] = False
    promotion_authorized: Literal[False] = False
    writer_citable: Literal[False] = False
    domain_judgment_eligible: Literal[False] = False

    @model_validator(mode="after")
    def require_scoped_stable_subset_and_recomputed_digest(self) -> "EvidenceGateCandidateProjection":
        cap = self.bundle_projection.query.resolved_topk_policy.evidence_gate_candidate_top_k
        if self.evidence_gate_candidate_top_k != cap:
            raise ValueError("evidence_gate_candidate_projection_resolved_cap_mismatch")
        if len(self.candidate_ids) > cap:
            raise ValueError("evidence_gate_candidate_projection_over_resolved_cap")
        if len(self.candidate_ids) != len(set(self.candidate_ids)):
            raise ValueError("evidence_gate_candidate_projection_duplicate_candidate_id")
        ordered_bundle_ids = tuple(candidate.candidate_id for candidate in self.bundle_projection.candidates)
        iterator = iter(ordered_bundle_ids)
        if any(candidate_id not in iterator for candidate_id in self.candidate_ids):
            raise ValueError("evidence_gate_candidate_projection_not_stable_eligible_bundle_subset")
        payload = {
            "bundle_projection": self.bundle_projection.model_dump(mode="json"),
            "candidate_ids": self.candidate_ids,
            "evidence_gate_candidate_top_k": cap,
            "persistence_authorized": False,
            "promotion_authorized": False,
            "writer_citable": False,
            "domain_judgment_eligible": False,
        }
        _require_owned_identity(
            identifier=self.projection_id,
            digest=self.projection_digest,
            prefix="evidence_gate_candidate_projection",
            payload=payload,
        )
        return self

    @classmethod
    def create(cls, *, bundle_projection: CandidateBundleProjection, candidate_ids: tuple[str, ...]) -> "EvidenceGateCandidateProjection":
        cap = bundle_projection.query.resolved_topk_policy.evidence_gate_candidate_top_k
        payload = {
            "bundle_projection": bundle_projection.model_dump(mode="json"),
            "candidate_ids": candidate_ids,
            "evidence_gate_candidate_top_k": cap,
            "persistence_authorized": False,
            "promotion_authorized": False,
            "writer_citable": False,
            "domain_judgment_eligible": False,
        }
        digest = canonical_digest(payload)
        return cls(projection_id=f"evidence_gate_candidate_projection_{digest[:20]}", projection_digest=digest, **payload)


@runtime_checkable
class ReadOnlyLocalAdapter(Protocol):
    """Injected seam only. R.1 never invokes ``recall``."""

    adapter_id: str

    def recall(self, query: LocalRetrievalQuery) -> tuple[LocalRecallCandidate, ...]: ...


@runtime_checkable
class BM25ReadOnlyAdapter(ReadOnlyLocalAdapter, Protocol):
    """Future injected lexical adapter; no implementation is imported in R.1."""


@runtime_checkable
class ObjectBM25ReadOnlyAdapter(ReadOnlyLocalAdapter, Protocol):
    """Future injected structured-object adapter; no implementation is imported in R.1."""


@runtime_checkable
class RelationshipGraphReadOnlyAdapter(ReadOnlyLocalAdapter, Protocol):
    """Future injected graph adapter; no graph is opened in R.1."""


@runtime_checkable
class ExactValueSqlReadOnlyAdapter(Protocol):
    """Future SQL seam requires pinned snapshot, exact filters and a receipt reference."""

    adapter_id: str

    def recall_exact_value(
        self,
        query: LocalRetrievalQuery,
        *,
        receipt: ToolInvocationReceiptReference,
    ) -> tuple[LocalRecallCandidate, ...]: ...


class NonExecutingLocalRetrievalSkeleton:
    """Owns fixture projection construction only; adapter invocation is intentionally absent."""

    def __init__(self, *, adapter: ReadOnlyLocalAdapter):
        if adapter is None:
            raise LocalRetrievalSkeletonError("injected_read_only_adapter_required")
        self._adapter = adapter

    def project_from_supplied_candidates(
        self,
        *,
        query: LocalRetrievalQuery,
        candidates: tuple[LocalRecallCandidate, ...] = (),
    ) -> CandidateBundleProjection:
        # Deliberately do not call self._adapter.recall(query). That belongs to R.3.
        return CandidateBundleProjection.create(query=query, candidates=candidates)


LOCAL_RETRIEVAL_SKELETON_MODELS = (
    TopKQuantities,
    TopKPolicyProfile,
    LegacyTopKMappingEntry,
    LegacyTopKMappingRegistry,
    TopKPolicyRequest,
    TopKPolicyResolution,
    TopKPolicyAuditDecision,
    TopKResolutionResult,
    ToolInvocationReceiptReference,
    ExactValueSqlFilters,
    ExactValueSqlMetricBinding,
    ExactValueSqlUnitScaleBinding,
    ExactValueSqlBindingPolicy,
    LocalAdapterSnapshot,
    ToolSelectionPlanScopeReference,
    ExactValueSqlExecutionScope,
    ExactValueSqlBindingResolution,
    LocalRetrievalQuery,
    LocalRecallCandidate,
    DeterministicRerankDecision,
    NeighborExpansionPlan,
    CandidateBundleProjection,
    EvidenceGateCandidateProjection,
)


__all__ = [
    "BM25ReadOnlyAdapter",
    "CandidateBundleProjection",
    "DeterministicRerankDecision",
    "EvidenceGateCandidateProjection",
    "ExactValueSqlBindingCompiler",
    "ExactValueSqlBindingPolicy",
    "ExactValueSqlBindingResolution",
    "ExactValueSqlExecutionScope",
    "ExactValueSqlFilters",
    "ExactValueSqlMetricBinding",
    "ExactValueSqlReadOnlyAdapter",
    "ExactValueSqlUnitScaleBinding",
    "LegacyEvidenceRequestTopKAdapter",
    "LegacyTopKMappingEntry",
    "LegacyTopKMappingRegistry",
    "LOCAL_RETRIEVAL_SKELETON_MODELS",
    "LocalAdapterSnapshot",
    "LocalRecallCandidate",
    "LocalRetrievalQuery",
    "LocalRetrievalSkeletonError",
    "M6_1_EVIDENCE_REQUEST_POLICY_REF",
    "NeighborExpansionPlan",
    "NonExecutingLocalRetrievalSkeleton",
    "ObjectBM25ReadOnlyAdapter",
    "ReadOnlyLocalAdapter",
    "RelationshipGraphReadOnlyAdapter",
    "SHA256_PATTERN",
    "ToolInvocationReceiptReference",
    "TopKPolicyAuditDecision",
    "TopKPolicyProfile",
    "TopKPolicyRequest",
    "TopKPolicyResolution",
    "TopKPolicyResolver",
    "TopKQuantities",
    "TopKResolutionResult",
    "ToolSelectionPlanScopeReference",
]
