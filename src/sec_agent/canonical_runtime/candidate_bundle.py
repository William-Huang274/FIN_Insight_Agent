from __future__ import annotations

from typing import Iterable

from pydantic import Field

from .evidence_request import EvidenceRequest
from .models import StrictModel, canonical_digest
from .tool_planner import ToolSelectionPlan


class CandidateBundleError(ValueError):
    """Raised when supplied metadata cannot form a bounded M6.3 CandidateBundle."""


class CandidateBundlePolicy(StrictModel):
    policy_ref: str = Field(min_length=1)
    minimum_source_authority_rank_by_evidence_role: dict[str, int]
    required_candidate_kinds_by_evidence_role: dict[str, tuple[str, ...]]
    allowed_candidate_kinds: tuple[str, ...] = Field(min_length=1)
    allowed_bundle_statuses: tuple[str, ...] = Field(min_length=1)


class CandidateMetadata(StrictModel):
    """Metadata reference only. Raw document content and extracted values are deliberately absent."""

    candidate_id: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    document_version: str = Field(min_length=1)
    source_snapshot_ref: str = Field(min_length=1)
    source_policy_ref: str = Field(min_length=1)
    route_id: str = Field(min_length=1)
    source_role: str = Field(min_length=1)
    source_authority_rank: int = Field(ge=0)
    entity_ref: str = Field(min_length=1)
    period_ref: str = Field(min_length=1)
    candidate_kind: str = Field(min_length=1)
    section_or_table_ref: str = Field(min_length=1)
    metadata_rank: int = Field(ge=0)
    content_ref: str = Field(min_length=1)


class CandidateMetadataSnapshot(StrictModel):
    snapshot_id: str = Field(min_length=1)
    snapshot_digest: str = Field(min_length=1)
    fixture_only: bool = True
    candidates: tuple[CandidateMetadata, ...]
    retrieval_call_count: int = 0
    external_call_count: int = 0
    store_write_count: int = 0

    @classmethod
    def create(cls, *, snapshot_id: str, candidates: Iterable[CandidateMetadata], fixture_only: bool = True) -> "CandidateMetadataSnapshot":
        items = tuple(candidates)
        ids = [item.candidate_id for item in items]
        if len(ids) != len(set(ids)):
            raise CandidateBundleError("duplicate_candidate_metadata_id")
        if not fixture_only:
            raise CandidateBundleError("candidate_metadata_snapshot_must_be_fixture_only")
        digest = canonical_digest(
            {
                "snapshot_id": snapshot_id,
                "fixture_only": fixture_only,
                "candidates": [item.model_dump(mode="json") for item in items],
            }
        )
        return cls(snapshot_id=snapshot_id, snapshot_digest=digest, fixture_only=fixture_only, candidates=items)


class CandidateBundle(StrictModel):
    bundle_id: str = Field(min_length=1)
    bundle_digest: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    request_digest: str = Field(min_length=1)
    tool_selection_plan_id: str = Field(min_length=1)
    tool_selection_plan_digest: str = Field(min_length=1)
    metadata_snapshot_id: str = Field(min_length=1)
    metadata_snapshot_digest: str = Field(min_length=1)
    retrieval_policy_ref: str = Field(min_length=1)
    status: str = Field(min_length=1)
    exhaustion_status: str = Field(min_length=1)
    typed_gap_codes: tuple[str, ...] = ()
    candidates: tuple[CandidateMetadata, ...] = ()
    top_k_candidate_ids: tuple[str, ...] = ()
    neighbor_candidate_ids: tuple[str, ...] = ()
    table_context_candidate_ids: tuple[str, ...] = ()
    candidate_count: int = Field(ge=0)
    execution_admission: str = "not_admitted"
    persistence_admission: str = "not_admitted"


class CandidateBundleResult(StrictModel):
    status: str
    bundle: CandidateBundle
    model_call_count: int = 0
    retrieval_call_count: int = 0
    external_call_count: int = 0
    store_write_count: int = 0


class CandidateBundleCompiler:
    """M6.3 metadata-only compiler; it never invokes a route or retrieves document content."""

    def __init__(self, *, policy: CandidateBundlePolicy):
        self.policy = policy

    def _validate_lineage(self, *, request: EvidenceRequest, plan: ToolSelectionPlan, snapshot: CandidateMetadataSnapshot) -> None:
        if request.execution_admission != "not_admitted":
            raise CandidateBundleError("request_execution_admission_must_be_not_admitted")
        if plan.request_id != request.request_id or plan.request_digest != request.request_digest:
            raise CandidateBundleError("tool_selection_plan_request_lineage_mismatch")
        if plan.persistence_admission != "not_admitted":
            raise CandidateBundleError("tool_selection_plan_persistence_must_be_not_admitted")
        if not snapshot.fixture_only or snapshot.retrieval_call_count or snapshot.external_call_count or snapshot.store_write_count:
            raise CandidateBundleError("candidate_snapshot_must_be_execution_free_fixture")

    def _typed_stop(self, *, request: EvidenceRequest, plan: ToolSelectionPlan, snapshot: CandidateMetadataSnapshot) -> CandidateBundleResult:
        payload = {
            "request_id": request.request_id,
            "request_digest": request.request_digest,
            "tool_selection_plan_id": plan.plan_id,
            "tool_selection_plan_digest": plan.plan_digest,
            "metadata_snapshot_id": snapshot.snapshot_id,
            "metadata_snapshot_digest": snapshot.snapshot_digest,
            "retrieval_policy_ref": self.policy.policy_ref,
            "status": "not_attempted_typed_stop",
            "exhaustion_status": "not_attempted",
            "typed_gap_codes": (plan.stop_reason or "tool_selection_stopped",),
            "candidates": (),
            "top_k_candidate_ids": (),
            "neighbor_candidate_ids": (),
            "table_context_candidate_ids": (),
            "candidate_count": 0,
            "execution_admission": "not_admitted",
            "persistence_admission": "not_admitted",
        }
        digest = canonical_digest(payload)
        bundle = CandidateBundle(bundle_id=f"candidate_bundle_{digest[:20]}", bundle_digest=digest, **payload)
        return CandidateBundleResult(status="pass", bundle=bundle)

    def compile(
        self,
        *,
        request: EvidenceRequest,
        plan: ToolSelectionPlan,
        snapshot: CandidateMetadataSnapshot,
    ) -> CandidateBundleResult:
        self._validate_lineage(request=request, plan=plan, snapshot=snapshot)
        if plan.status == "stopped":
            return self._typed_stop(request=request, plan=plan, snapshot=snapshot)
        if plan.status != "await_execution_admission" or not plan.steps:
            raise CandidateBundleError("tool_selection_plan_not_eligible_for_metadata_bundle")
        if any(step.invocation_status != "not_executed" for step in plan.steps):
            raise CandidateBundleError("tool_invocation_receipt_or_execution_not_admitted")
        minimum_rank = self.policy.minimum_source_authority_rank_by_evidence_role.get(request.accepted_evidence_role)
        required_kinds = self.policy.required_candidate_kinds_by_evidence_role.get(request.accepted_evidence_role)
        if minimum_rank is None or required_kinds is None:
            raise CandidateBundleError(f"candidate_policy_missing_evidence_role:{request.accepted_evidence_role}")
        selected_routes = {str(step.selected_route_id) for step in plan.steps if step.selected_route_id}
        valid: list[CandidateMetadata] = []
        rejected_codes: set[str] = set()
        for item in snapshot.candidates:
            if item.candidate_kind not in self.policy.allowed_candidate_kinds:
                rejected_codes.add(f"candidate_kind_not_allowed:{item.candidate_kind}")
                continue
            if item.route_id not in selected_routes:
                rejected_codes.add("candidate_route_not_selected")
                continue
            if item.source_policy_ref != request.source_policy:
                rejected_codes.add("candidate_source_policy_mismatch")
                continue
            if item.entity_ref not in request.target_entities or item.period_ref not in request.target_periods:
                rejected_codes.add("candidate_scope_mismatch")
                continue
            if item.source_authority_rank < minimum_rank:
                rejected_codes.add("candidate_source_authority_below_minimum")
                continue
            valid.append(item)
        ordered = tuple(sorted(valid, key=lambda item: (-item.source_authority_rank, item.metadata_rank, item.candidate_id))[: request.topk_policy.candidate_limit])
        present_kinds = {item.candidate_kind for item in ordered}
        missing_kinds = tuple(sorted(set(required_kinds) - present_kinds))
        if not ordered:
            gaps = tuple(sorted(rejected_codes or {"candidate_metadata_absent"}))
            status, exhaustion = "retrieval_exhausted", "metadata_candidate_absent"
        elif missing_kinds:
            gaps = tuple(f"required_context_kind_missing:{kind}" for kind in missing_kinds)
            status, exhaustion = "retrieval_exhausted", "required_context_expansion_missing"
        else:
            gaps = ()
            status, exhaustion = "metadata_fixture_compiled", "not_exhausted"
        top_k = tuple(item.candidate_id for item in ordered if item.candidate_kind == "top_k_seed")[: request.topk_policy.top_k]
        neighbors = tuple(item.candidate_id for item in ordered if item.candidate_kind == "neighbor_section")
        tables = tuple(item.candidate_id for item in ordered if item.candidate_kind == "table_context")
        payload = {
            "request_id": request.request_id,
            "request_digest": request.request_digest,
            "tool_selection_plan_id": plan.plan_id,
            "tool_selection_plan_digest": plan.plan_digest,
            "metadata_snapshot_id": snapshot.snapshot_id,
            "metadata_snapshot_digest": snapshot.snapshot_digest,
            "retrieval_policy_ref": self.policy.policy_ref,
            "status": status,
            "exhaustion_status": exhaustion,
            "typed_gap_codes": gaps,
            "candidates": [item.model_dump(mode="json") for item in ordered],
            "top_k_candidate_ids": top_k,
            "neighbor_candidate_ids": neighbors,
            "table_context_candidate_ids": tables,
            "candidate_count": len(ordered),
            "execution_admission": "not_admitted",
            "persistence_admission": "not_admitted",
        }
        digest = canonical_digest(payload)
        bundle = CandidateBundle(bundle_id=f"candidate_bundle_{digest[:20]}", bundle_digest=digest, **payload)
        return CandidateBundleResult(status="pass", bundle=bundle)
