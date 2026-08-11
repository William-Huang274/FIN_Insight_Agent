from __future__ import annotations

from typing import Any, Mapping, Protocol

from .full_serializer import DecisionSurfaceArtifactEnvelope
from .models import StrictModel, canonical_digest


class CompilerModelAdapterProtocol(Protocol):
    """Provider-neutral boundary; M2.8 does not invoke it while admission is denied."""

    def compile(self, prompt_context: Mapping[str, Any]) -> Mapping[str, Any]: ...


class ModelAdmissionPolicy(StrictModel):
    policy_ref: str
    allowed_provider_families: tuple[str, ...]
    model_execution_permitted: bool = False
    require_feature_flag: bool = True
    require_explicit_approved_scoped_node: bool = True
    require_provider_preflight: bool = True
    require_budget_preflight: bool = True
    require_permission_snapshot: bool = True


class CompilerPromptContextSnapshot(StrictModel):
    snapshot_version: str
    envelope_digest: str
    contract_version_id: str
    policy_config_refs: tuple[str, ...]
    provider_family: str
    prompt_context_digest: str
    prompt_body_included: bool = False


class ModelAdmissionRequest(StrictModel):
    envelope: DecisionSurfaceArtifactEnvelope
    provider_family: str
    feature_flag_enabled: bool
    explicit_approved_scoped_node: bool
    provider_preflight_status: str
    budget_preflight_status: str
    permission_snapshot_ref: str | None = None


class ModelAdmissionDecision(StrictModel):
    status: str
    model_execution_permitted: bool
    provider_family: str
    denial_reasons: tuple[str, ...] = ()
    permission_snapshot_ref: str | None = None
    decision_digest: str
    planning_authority: str = "shadow"
    model_call_count: int = 0
    external_call_count: int = 0


class StructuredOutputRepairTrace(StrictModel):
    status: str
    repair_attempt_count: int = 0
    reason: str
    input_digest: str
    output_digest: str | None = None


class ModelCompilationProposal(StrictModel):
    status: str
    prompt_context_snapshot: CompilerPromptContextSnapshot
    admission_decision: ModelAdmissionDecision
    structured_output_repair_trace: StructuredOutputRepairTrace
    proposal_payload: dict[str, Any] | None = None
    planning_authority: str = "shadow"
    model_call_count: int = 0
    external_call_count: int = 0


class ModelAdmissionAuditTrace(StrictModel):
    policy_ref: str
    prompt_context_snapshot: CompilerPromptContextSnapshot
    admission_decision: ModelAdmissionDecision
    proposal_status: str
    audit_digest: str
    model_call_count: int = 0
    external_call_count: int = 0


class CompilerModelAdmissionService:
    """M2.8 admission and trace contract; policy remains hard-denied until a future approved node run."""

    def __init__(self, policy: ModelAdmissionPolicy):
        self.policy = policy

    def snapshot(self, request: ModelAdmissionRequest) -> CompilerPromptContextSnapshot:
        contract = request.envelope.bundle["contract"]
        refs = tuple(sorted(set(contract.get("policy_config_refs", ())) | {self.policy.policy_ref}))
        payload = {
            "envelope_digest": request.envelope.envelope_digest,
            "contract_version_id": contract["contract_version_id"],
            "policy_config_refs": refs,
            "provider_family": request.provider_family,
            "case_id": contract["case_id"],
            "query_digest": canonical_digest(contract["query"]),
        }
        return CompilerPromptContextSnapshot(
            snapshot_version="finsight_point01_compiler_prompt_context_snapshot_v1",
            envelope_digest=request.envelope.envelope_digest,
            contract_version_id=str(contract["contract_version_id"]),
            policy_config_refs=refs,
            provider_family=request.provider_family,
            prompt_context_digest=canonical_digest(payload),
        )

    def evaluate(self, request: ModelAdmissionRequest) -> ModelAdmissionDecision:
        reasons: list[str] = []
        if request.provider_family not in self.policy.allowed_provider_families:
            reasons.append("provider_family_not_allowed")
        if self.policy.require_feature_flag and not request.feature_flag_enabled:
            reasons.append("feature_flag_not_enabled")
        if self.policy.require_explicit_approved_scoped_node and not request.explicit_approved_scoped_node:
            reasons.append("explicit_approved_scoped_node_missing")
        if self.policy.require_provider_preflight and request.provider_preflight_status != "pass":
            reasons.append("provider_preflight_not_pass")
        if self.policy.require_budget_preflight and request.budget_preflight_status != "pass":
            reasons.append("budget_preflight_not_pass")
        if self.policy.require_permission_snapshot and not (request.permission_snapshot_ref or "").strip():
            reasons.append("permission_snapshot_missing")
        if not self.policy.model_execution_permitted:
            reasons.append("policy_model_execution_disabled")
        payload = {
            "policy_ref": self.policy.policy_ref,
            "envelope_digest": request.envelope.envelope_digest,
            "provider_family": request.provider_family,
            "feature_flag_enabled": request.feature_flag_enabled,
            "explicit_approved_scoped_node": request.explicit_approved_scoped_node,
            "provider_preflight_status": request.provider_preflight_status,
            "budget_preflight_status": request.budget_preflight_status,
            "permission_snapshot_ref": request.permission_snapshot_ref,
            "denial_reasons": sorted(set(reasons)),
        }
        return ModelAdmissionDecision(
            status="admitted" if not reasons else "denied",
            model_execution_permitted=not reasons,
            provider_family=request.provider_family,
            denial_reasons=tuple(sorted(set(reasons))),
            permission_snapshot_ref=request.permission_snapshot_ref,
            decision_digest=canonical_digest(payload),
        )

    def propose(
        self,
        request: ModelAdmissionRequest,
        *,
        adapter: CompilerModelAdapterProtocol | None = None,
    ) -> tuple[ModelCompilationProposal, ModelAdmissionAuditTrace]:
        snapshot = self.snapshot(request)
        decision = self.evaluate(request)
        # M2.8 deliberately does not reach this adapter: the policy is hard-denied.
        # Retaining the protocol here allows a later, explicitly approved node to reuse
        # the exact snapshot and admission trace without exposing provider specifics.
        del adapter
        repair = StructuredOutputRepairTrace(
            status="not_attempted",
            repair_attempt_count=0,
            reason="admission_denied" if decision.status == "denied" else "model_execution_not_implemented",
            input_digest=snapshot.prompt_context_digest,
        )
        proposal = ModelCompilationProposal(
            status="not_created_admission_denied" if decision.status == "denied" else "not_created_model_execution_not_implemented",
            prompt_context_snapshot=snapshot,
            admission_decision=decision,
            structured_output_repair_trace=repair,
        )
        audit = ModelAdmissionAuditTrace(
            policy_ref=self.policy.policy_ref,
            prompt_context_snapshot=snapshot,
            admission_decision=decision,
            proposal_status=proposal.status,
            audit_digest=canonical_digest(
                {
                    "policy_ref": self.policy.policy_ref,
                    "snapshot": snapshot.model_dump(mode="json"),
                    "decision": decision.model_dump(mode="json"),
                    "proposal_status": proposal.status,
                }
            ),
        )
        return proposal, audit
