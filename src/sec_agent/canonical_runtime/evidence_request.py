from __future__ import annotations

from typing import Mapping

from pydantic import Field

from .models import (
    DecisionSurfaceCellVersion,
    DecisionSurfaceContractVersion,
    EvidenceSlotVersion,
    StrictModel,
    canonical_digest,
)


class EvidenceRequestCompileError(ValueError):
    """Raised when a Cell/Slot cannot be compiled into a bounded EvidenceRequest."""


class EvidenceRequestRoleRule(StrictModel):
    accepted_evidence_role: str = Field(min_length=1)
    evidence_domain: str = Field(min_length=1)
    allowed_source_policy_refs: tuple[str, ...] = Field(min_length=1)
    allowed_acceptance_roles: tuple[str, ...] = Field(min_length=1)
    required_forbidden_substitutions: tuple[str, ...] = ()
    metadata_binding_requirements: tuple[str, ...] = Field(min_length=1)
    numeric_binding_requirements: tuple[str, ...] = ()
    acceptable_proxy: tuple[str, ...] = ()
    preferred_routes: tuple[str, ...] = Field(min_length=1)
    fallback_routes: tuple[str, ...] = ()
    top_k: int = Field(ge=1)
    candidate_limit: int = Field(ge=1)
    tool_call_limit: int = Field(ge=0)
    elapsed_seconds_limit: int = Field(ge=1)


class EvidenceRequestPolicy(StrictModel):
    policy_ref: str = Field(min_length=1)
    role_rules: dict[str, EvidenceRequestRoleRule]


class EvidenceRequestCompileOverrides(StrictModel):
    """Bounded annotations; no free-search query or executable-tool field is accepted."""

    requester_role: str | None = None
    product_intent: tuple[str, ...] = ()
    granularity: str = "cell_slot"
    unit: str | None = None


class EvidenceRequestTopKPolicy(StrictModel):
    top_k: int = Field(ge=1)
    candidate_limit: int = Field(ge=1)


class EvidenceRequestBudget(StrictModel):
    tool_call_limit: int = Field(ge=0)
    elapsed_seconds_limit: int = Field(ge=1)


class EvidenceRequest(StrictModel):
    request_id: str = Field(min_length=1)
    request_digest: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    decision_surface_id: str = Field(min_length=1)
    decision_surface_contract_version_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    cell_version_id: str = Field(min_length=1)
    evidence_slot_id: str = Field(min_length=1)
    evidence_slot_version_id: str = Field(min_length=1)
    requester_role: str = Field(min_length=1)
    accepted_evidence_role: str = Field(min_length=1)
    evidence_domain: str = Field(min_length=1)
    target_entities: tuple[str, ...] = Field(min_length=1)
    target_periods: tuple[str, ...] = Field(min_length=1)
    metric_intent: tuple[str, ...] = ()
    product_intent: tuple[str, ...] = ()
    granularity: str = Field(min_length=1)
    unit: str | None = None
    source_policy: str = Field(min_length=1)
    metadata_binding_requirements: tuple[str, ...] = Field(min_length=1)
    numeric_binding_requirements: tuple[str, ...] = ()
    acceptable_proxy: tuple[str, ...] = ()
    forbidden_substitutions: tuple[str, ...] = ()
    preferred_routes: tuple[str, ...] = Field(min_length=1)
    fallback_routes: tuple[str, ...] = ()
    topk_policy: EvidenceRequestTopKPolicy
    budget: EvidenceRequestBudget
    stop_condition: str = Field(min_length=1)
    required: bool
    compiler_policy_ref: str = Field(min_length=1)
    compiled_from_refs: tuple[str, ...] = Field(min_length=1)
    planning_authority: str = "shadow"
    execution_admission: str = "not_admitted"


class EvidenceRequestCompilationResult(StrictModel):
    status: str
    request: EvidenceRequest
    input_lineage_digest: str
    model_call_count: int = 0
    external_call_count: int = 0
    store_write_count: int = 0


class EvidenceRequestCompiler:
    """M6.1 pure compiler: exact planning inputs -> immutable request contract, never retrieval/execution."""

    def __init__(self, policy: EvidenceRequestPolicy):
        self.policy = policy

    @staticmethod
    def _require_exact_lineage(
        contract: DecisionSurfaceContractVersion,
        cell: DecisionSurfaceCellVersion,
        slot: EvidenceSlotVersion,
    ) -> None:
        if (contract.tenant_id, contract.project_id, contract.case_id) != (cell.tenant_id, cell.project_id, cell.case_id):
            raise EvidenceRequestCompileError("contract_cell_scope_mismatch")
        if (cell.tenant_id, cell.project_id, cell.case_id) != (slot.tenant_id, slot.project_id, slot.case_id):
            raise EvidenceRequestCompileError("cell_slot_scope_mismatch")
        if cell.contract_version_id != contract.contract_version_id:
            raise EvidenceRequestCompileError("cell_parent_contract_version_mismatch")
        if slot.cell_version_id != cell.cell_version_id:
            raise EvidenceRequestCompileError("slot_parent_cell_version_mismatch")

    def compile(
        self,
        *,
        contract: DecisionSurfaceContractVersion,
        cell: DecisionSurfaceCellVersion,
        slot: EvidenceSlotVersion,
        overrides: EvidenceRequestCompileOverrides | None = None,
    ) -> EvidenceRequestCompilationResult:
        self._require_exact_lineage(contract, cell, slot)
        options = overrides or EvidenceRequestCompileOverrides()
        rule = self.policy.role_rules.get(slot.evidence_role)
        if rule is None:
            raise EvidenceRequestCompileError(f"evidence_role_not_allowed:{slot.evidence_role}")
        if slot.source_policy_ref not in rule.allowed_source_policy_refs:
            raise EvidenceRequestCompileError(f"source_policy_not_allowed:{slot.source_policy_ref}")
        if slot.acceptance_role not in rule.allowed_acceptance_roles:
            raise EvidenceRequestCompileError(f"acceptance_role_not_allowed:{slot.acceptance_role}")
        missing_forbidden = sorted(set(rule.required_forbidden_substitutions) - set(slot.forbidden_substitutions))
        if missing_forbidden:
            raise EvidenceRequestCompileError(f"required_forbidden_substitution_missing:{missing_forbidden[0]}")
        if not slot.entity_scope:
            raise EvidenceRequestCompileError("target_entity_required")
        if not slot.period_scope.strip():
            raise EvidenceRequestCompileError("target_period_required")
        if rule.numeric_binding_requirements and not slot.metric_scope:
            raise EvidenceRequestCompileError("numeric_metric_intent_required")
        requester_role = options.requester_role or cell.owner_role
        if requester_role != cell.owner_role:
            raise EvidenceRequestCompileError("requester_role_must_match_cell_owner")
        if not options.granularity.strip():
            raise EvidenceRequestCompileError("granularity_required")
        if any(not item.strip() for item in options.product_intent):
            raise EvidenceRequestCompileError("product_intent_blank")

        lineage_refs = (
            contract.contract_version_id,
            cell.cell_version_id,
            slot.slot_version_id,
            self.policy.policy_ref,
        )
        request_payload = {
            "tenant_id": contract.tenant_id,
            "project_id": contract.project_id,
            "case_id": str(contract.case_id),
            "decision_surface_id": contract.contract_id,
            "decision_surface_contract_version_id": contract.contract_version_id,
            "cell_id": cell.cell_id,
            "cell_version_id": cell.cell_version_id,
            "evidence_slot_id": slot.evidence_slot_id,
            "evidence_slot_version_id": slot.slot_version_id,
            "requester_role": requester_role,
            "accepted_evidence_role": rule.accepted_evidence_role,
            "evidence_domain": rule.evidence_domain,
            "target_entities": slot.entity_scope,
            "target_periods": (slot.period_scope,),
            "metric_intent": slot.metric_scope,
            "product_intent": options.product_intent,
            "granularity": options.granularity,
            "unit": options.unit,
            "source_policy": slot.source_policy_ref,
            "metadata_binding_requirements": rule.metadata_binding_requirements,
            "numeric_binding_requirements": rule.numeric_binding_requirements,
            "acceptable_proxy": rule.acceptable_proxy,
            "forbidden_substitutions": slot.forbidden_substitutions,
            "preferred_routes": rule.preferred_routes,
            "fallback_routes": rule.fallback_routes,
            "topk_policy": {"top_k": rule.top_k, "candidate_limit": rule.candidate_limit},
            "budget": {"tool_call_limit": rule.tool_call_limit, "elapsed_seconds_limit": rule.elapsed_seconds_limit},
            "stop_condition": cell.stop_rule,
            "required": slot.required,
            "compiler_policy_ref": self.policy.policy_ref,
            "compiled_from_refs": lineage_refs,
            "planning_authority": "shadow",
            "execution_admission": "not_admitted",
        }
        request_digest = canonical_digest(request_payload)
        request = EvidenceRequest(
            request_id=f"evidence_request_{request_digest[:20]}",
            request_digest=request_digest,
            **request_payload,
        )
        return EvidenceRequestCompilationResult(
            status="pass",
            request=request,
            input_lineage_digest=canonical_digest({"refs": lineage_refs, "request_digest": request_digest}),
        )
