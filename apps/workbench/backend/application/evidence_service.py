from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.canonical_runtime.candidate_bundle import (
    CandidateBundleCompiler,
    CandidateBundlePolicy,
    CandidateMetadata,
    CandidateMetadataSnapshot,
)
from sec_agent.canonical_runtime.evidence_request import EvidenceRequestCompiler, EvidenceRequestPolicy
from sec_agent.canonical_runtime.models import (
    DecisionSurfaceCellVersion,
    DecisionSurfaceContractVersion,
    EvidenceReviewActionVersion,
    EvidenceSlotVersion,
    EvidenceWorkbenchProjectionVersion,
    EventEnvelope,
    canonical_digest,
    utc_now,
)
from sec_agent.canonical_runtime.store import IdempotencyConflict, TransactionConflict
from sec_agent.canonical_runtime.tool_planner import (
    BoundedToolPlanner,
    PlannerPermissionContext,
    PlannerPolicy,
    ToolRegistryEntry,
    ToolRegistrySnapshot,
)

from .case_service import (
    P36_CANDIDATE_PROFILE,
    CasePrincipal,
    CaseService,
    load_p36_candidate_profile,
)


WORK_UNIT_TYPE = "p36_evidence_fixture_entry"
PROJECTION_TABLE = "canonical_evidence_workbench_projection_versions"
REVIEW_TABLE = "canonical_evidence_review_action_versions"
REPAIR_OUTCOME_TABLE = "canonical_evidence_repair_outcome_versions"
CONTRACT_RELATIVE_PATH = "configs/releases/point03_vt1_evidence_workbench_contract_v1_0.json"


@dataclass(frozen=True)
class CompileEvidenceFixtureDraft:
    expected_workspace_version: int
    actor_ref: str
    idempotency_key: str


@dataclass(frozen=True)
class EvidenceReviewDraft:
    expected_workspace_version: int
    reason: str
    actor_ref: str
    idempotency_key: str


class EvidenceServiceError(RuntimeError):
    def __init__(self, error_code: str, status_code: int, **detail: Any):
        super().__init__(error_code)
        self.error_code = error_code
        self.status_code = status_code
        self.detail = {"reason": error_code, **detail}


class EvidenceService:
    """Point 3 VT1 metadata-only compiler and append-only review boundary."""

    def __init__(
        self,
        facade: Any | None,
        *,
        contract: Mapping[str, Any] | None = None,
        p36_profile: Mapping[str, Any] | None = None,
        unavailable_reason: str | None = None,
    ):
        self._facade = facade
        self._unavailable_reason = unavailable_reason
        self._contract = dict(contract or {})
        self._p36_profile = dict(p36_profile or {})
        if facade is not None:
            self._configure_contract()

    @classmethod
    def from_case_service(cls, service: CaseService, *, repo_root: str | Path) -> "EvidenceService":
        facade = getattr(service, "_facade", None)
        if facade is None:
            return cls(None, unavailable_reason="explicit_fixture_root_required")
        contract_path = Path(repo_root) / CONTRACT_RELATIVE_PATH
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        return cls(
            facade,
            contract=contract,
            p36_profile=load_p36_candidate_profile(repo_root),
        )

    @classmethod
    def unavailable(cls, reason: str = "explicit_fixture_root_required") -> "EvidenceService":
        return cls(None, unavailable_reason=reason)

    def _configure_contract(self) -> None:
        if self._contract.get("schema_version") != "fin_point03_vt1_evidence_workbench_contract_v1_0":
            raise ValueError("point03_fixture_contract_version_invalid")
        boundaries = self._contract.get("hard_boundaries", {})
        for key in (
            "retrieval_execution",
            "tool_invocation",
            "network_calls",
            "model_calls",
            "provider_calls",
            "paid_full_chain",
            "attempts",
            "artifacts",
        ):
            if boundaries.get(key) != 0:
                raise ValueError(f"point03_hard_boundary_open:{key}")
        request_policy = deepcopy(self._contract["evidence_request_policy"])
        self._fixture_candidate_sets = deepcopy(self._contract["fixture_candidate_sets"])
        extensions = self._p36_profile.get("evidence_role_extensions", {})
        if extensions and not isinstance(extensions, Mapping):
            raise ValueError("p36_evidence_role_extensions_invalid")
        for role, raw_extension in extensions.items():
            if not isinstance(raw_extension, Mapping):
                raise ValueError("p36_evidence_role_extension_invalid")
            request_policy["role_rules"][role] = deepcopy(raw_extension["request_policy"])
            self._fixture_candidate_sets[role] = deepcopy(
                raw_extension.get("fixture_candidates", [])
            )
        self._request_compiler = EvidenceRequestCompiler(
            EvidenceRequestPolicy.model_validate(request_policy)
        )
        entries = tuple(
            ToolRegistryEntry.model_validate(row) for row in self._contract["tool_registry"]["tools"]
        )
        self._registry = ToolRegistrySnapshot.create(
            registry_id=self._contract["tool_registry"]["registry_id"],
            registry_version=self._contract["tool_registry"]["registry_version"],
            entries=entries,
        )
        self._planner = BoundedToolPlanner(
            registry=self._registry,
            policy=PlannerPolicy.model_validate(self._contract["planner_policy"]),
        )
        self._candidate_compiler = CandidateBundleCompiler(
            policy=CandidateBundlePolicy.model_validate(self._contract["candidate_policy"])
        )
        self._contract_digest = canonical_digest(self._contract)
        planning_profile = self._p36_profile.get("planning_profile", {})
        self._p36_compiler_policy_ref = str(
            planning_profile.get("compiler_policy_ref") or ""
        )
        self._p36_active_roles = tuple(
            self._p36_profile.get("workpaper_profile", {}).get(
                "required_judgment_roles", ()
            )
        )
        self._p36_profile_digest = (
            canonical_digest(self._p36_profile) if self._p36_profile else ""
        )

    def compile_fixture(
        self,
        case_id: str,
        draft: CompileEvidenceFixtureDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_permission(principal, "evidence:write")
        self._require_actor(draft.actor_ref, principal)
        self._require_request(case_id, draft.idempotency_key, trace_id)
        store = self._facade_or_raise().store
        payload_digest = canonical_digest(
            {
                "operation": "compile_evidence_fixture",
                "case_id": case_id,
                **draft.__dict__,
            }
        )
        scope_key = self._idempotency_scope(case_id, draft.idempotency_key, principal)
        reused = False
        try:
            with store.transaction() as tx:
                reused = self._check_idempotency(tx, scope_key, payload_digest)
                if not reused:
                    self._case_row(tx, case_id, principal)
                    self._actor_snapshot(tx, draft.actor_ref, principal)
                    existing = self._projection_row(tx, case_id, principal, required=False)
                    current_version = self._workspace_version(tx, existing) if existing else 0
                    if draft.expected_workspace_version != current_version:
                        raise EvidenceServiceError(
                            "version_conflict",
                            409,
                            expected_version=draft.expected_workspace_version,
                            current_version=current_version,
                        )
                    if existing:
                        raise EvidenceServiceError("evidence_workspace_already_compiled", 409)
                    context = self._entry_context(tx, case_id, principal)
                    slots, counts = self._compile_slots(context, principal)
                    workspace_id = "evidence_workspace_" + canonical_digest(
                        {
                            "tenant_id": principal.tenant_id,
                            "project_id": principal.project_id,
                            "case_id": case_id,
                            "contract_version_id": context["contract"].contract_version_id,
                        }
                    )[:24]
                    projection = EvidenceWorkbenchProjectionVersion(
                        tenant_id=principal.tenant_id,
                        project_id=principal.project_id,
                        case_id=case_id,
                        actor_snapshot_ref=f"fixture_actor:{draft.actor_ref}",
                        permission_snapshot_ref=self._permission_ref(principal),
                        policy_config_refs=(
                            "point03.vt1.fixture.shadow.internal",
                            f"contract:{self._contract_digest}",
                        ),
                        correlation_id=trace_id,
                        current_status="compiled_fixture",
                        workspace_id=workspace_id,
                        projection_version_id=f"{workspace_id}:v1",
                        projection_version=1,
                        workspace_version=1,
                        contract_version_id=context["contract"].contract_version_id,
                        checkpoint_version_id=str(context["checkpoint"]["checkpoint_version_id"]),
                        checkpoint_version=int(context["checkpoint"]["checkpoint_version"]),
                        work_unit_id=str(context["work_unit"]["work_unit_id"]),
                        work_unit_version=int(context["work_unit"]["work_unit_version"]),
                        work_unit_state_version=int(context["work_unit"]["state_version"]),
                        fixture_contract_ref=str(context["fixture_contract_ref"]),
                        fixture_contract_digest=str(context["fixture_contract_digest"]),
                        evidence_slots=tuple(slots),
                        compiled_counts=counts,
                        hard_boundaries=dict(self._contract["hard_boundaries"]),
                    )
                    projection = self._with_content_digest(projection)
                    tx.insert(PROJECTION_TABLE, workspace_id, 1, projection.model_dump(mode="json"))
                    event = self._event(
                        tx,
                        event_type="EVIDENCE_FIXTURE_COMPILED",
                        actor_ref=draft.actor_ref,
                        trace_id=trace_id,
                        work_unit_id=projection.work_unit_id,
                        state_before=0,
                        state_after=1,
                        payload={
                            "workspace_id": workspace_id,
                            "projection_version_id": projection.projection_version_id,
                            "contract_version_id": projection.contract_version_id,
                            "checkpoint_version_id": projection.checkpoint_version_id,
                            "compiled_counts": counts,
                        },
                    )
                    tx.append_event(event)
                    tx.put_idempotency(
                        scope_key,
                        payload_digest,
                        {"workspace_id": workspace_id, "workspace_version": 1, "event_id": event.event_id},
                    )
        except Exception as exc:
            raise self._service_error(exc) from exc
        return self._view(case_id, principal)

    def get_workbench(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        self._require_permission(principal, "evidence:read")
        try:
            self._case_row(self._facade_or_raise().store, case_id, principal)
            return self._view(case_id, principal)
        except Exception as exc:
            raise self._service_error(exc) from exc

    def reject_candidate(
        self,
        case_id: str,
        candidate_id: str,
        draft: EvidenceReviewDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        return self._record_review(
            case_id,
            action_type="reject_candidate",
            candidate_id=candidate_id,
            evidence_slot_id=None,
            draft=draft,
            principal=principal,
            trace_id=trace_id,
        )

    def request_repair(
        self,
        case_id: str,
        evidence_slot_id: str,
        draft: EvidenceReviewDraft,
        principal: CasePrincipal,
        *,
        trace_id: str,
    ) -> dict[str, Any]:
        return self._record_review(
            case_id,
            action_type="request_repair",
            candidate_id=None,
            evidence_slot_id=evidence_slot_id,
            draft=draft,
            principal=principal,
            trace_id=trace_id,
        )

    def _record_review(
        self,
        case_id: str,
        *,
        action_type: str,
        candidate_id: str | None,
        evidence_slot_id: str | None,
        draft: EvidenceReviewDraft,
        principal: CasePrincipal,
        trace_id: str,
    ) -> dict[str, Any]:
        self._require_permission(principal, "evidence:review")
        self._require_actor(draft.actor_ref, principal)
        self._require_request(case_id, draft.idempotency_key, trace_id)
        if not draft.reason.strip():
            raise EvidenceServiceError("review_reason_required", 422)
        target_id = candidate_id or evidence_slot_id or ""
        if not target_id.strip():
            raise EvidenceServiceError("request_validation_error", 422)
        payload_digest = canonical_digest(
            {
                "operation": action_type,
                "case_id": case_id,
                "target_id": target_id,
                **draft.__dict__,
            }
        )
        scope_key = self._idempotency_scope(case_id, draft.idempotency_key, principal)
        store = self._facade_or_raise().store
        try:
            with store.transaction() as tx:
                reused = self._check_idempotency(tx, scope_key, payload_digest)
                if not reused:
                    self._case_row(tx, case_id, principal)
                    self._actor_snapshot(tx, draft.actor_ref, principal)
                    projection = self._projection_row(tx, case_id, principal)
                    current_version = self._workspace_version(tx, projection)
                    if draft.expected_workspace_version != current_version:
                        raise EvidenceServiceError(
                            "version_conflict",
                            409,
                            expected_version=draft.expected_workspace_version,
                            current_version=current_version,
                        )
                    slot_id = self._resolve_target(
                        projection,
                        action_type=action_type,
                        candidate_id=candidate_id,
                        evidence_slot_id=evidence_slot_id,
                    )
                    action_id = "evidence_review_" + canonical_digest(
                        {
                            "tenant_id": principal.tenant_id,
                            "project_id": principal.project_id,
                            "case_id": case_id,
                            "idempotency_key": draft.idempotency_key,
                        }
                    )[:24]
                    action = EvidenceReviewActionVersion(
                        tenant_id=principal.tenant_id,
                        project_id=principal.project_id,
                        case_id=case_id,
                        actor_snapshot_ref=f"fixture_actor:{draft.actor_ref}",
                        permission_snapshot_ref=self._permission_ref(principal),
                        policy_config_refs=("point03.vt1.review.fixture.internal",),
                        correlation_id=trace_id,
                        current_status="recorded",
                        review_action_id=action_id,
                        review_action_version_id=f"{action_id}:v1",
                        review_action_version=1,
                        workspace_id=str(projection["workspace_id"]),
                        workspace_projection_version_id=str(projection["projection_version_id"]),
                        workspace_version_before=current_version,
                        workspace_version_after=current_version + 1,
                        action_type=action_type,
                        evidence_slot_id=slot_id,
                        candidate_id=candidate_id,
                        reason=draft.reason.strip(),
                    )
                    action = self._with_content_digest(action)
                    tx.insert(REVIEW_TABLE, action_id, 1, action.model_dump(mode="json"))
                    event_type = (
                        "EVIDENCE_CANDIDATE_REJECTED"
                        if action_type == "reject_candidate"
                        else "EVIDENCE_REPAIR_REQUESTED"
                    )
                    event = self._event(
                        tx,
                        event_type=event_type,
                        actor_ref=draft.actor_ref,
                        trace_id=trace_id,
                        work_unit_id=str(projection["work_unit_id"]),
                        state_before=current_version,
                        state_after=current_version + 1,
                        payload={
                            "workspace_id": projection["workspace_id"],
                            "review_action_id": action_id,
                            "action_type": action_type,
                            "evidence_slot_id": slot_id,
                            "candidate_id": candidate_id,
                            "reason": action.reason,
                        },
                    )
                    tx.append_event(event)
                    tx.put_idempotency(
                        scope_key,
                        payload_digest,
                        {
                            "workspace_id": projection["workspace_id"],
                            "workspace_version": current_version + 1,
                            "event_id": event.event_id,
                        },
                    )
        except Exception as exc:
            raise self._service_error(exc) from exc
        return self._view(case_id, principal)

    def _entry_context(self, catalog: Any, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        checkpoints = [
            row
            for row in catalog.list_latest("canonical_planning_checkpoint_versions", case_id=case_id)
            if self._matches_scope(row, case_id, principal)
        ]
        if len(checkpoints) != 1 or checkpoints[0].get("review_status") != "accepted":
            raise EvidenceServiceError("accepted_latest_planning_checkpoint_required", 409)
        checkpoint = checkpoints[0]
        contracts = [
            row
            for row in catalog.list_latest("canonical_decision_surface_contract_versions", case_id=case_id)
            if self._matches_scope(row, case_id, principal)
        ]
        if len(contracts) != 1 or contracts[0].get("contract_version_id") != checkpoint.get("contract_version_id"):
            raise EvidenceServiceError("accepted_latest_planning_checkpoint_required", 409)
        contract = DecisionSurfaceContractVersion.model_validate(contracts[0])
        work_units = [
            row
            for row in catalog.list_latest("canonical_work_units", case_id=case_id)
            if self._matches_scope(row, case_id, principal) and row.get("work_unit_type") == WORK_UNIT_TYPE
        ]
        if len(work_units) != 1 or work_units[0].get("state") != "pending":
            raise EvidenceServiceError("exactly_one_pending_evidence_fixture_work_unit_required", 409)
        work_unit = work_units[0]
        if tuple(work_unit.get("input_version_refs") or ()) != (contract.contract_version_id,):
            raise EvidenceServiceError("evidence_work_unit_planning_lineage_mismatch", 409)
        if catalog.list_latest("canonical_attempts", case_id=case_id):
            raise EvidenceServiceError("evidence_fixture_attempt_count_must_be_zero", 409)
        if catalog.list_latest("canonical_artifact_versions", case_id=case_id):
            raise EvidenceServiceError("evidence_fixture_artifact_count_must_be_zero", 409)

        cell_rows = [
            row
            for row in catalog.list_versions("canonical_decision_surface_cell_versions", case_id=case_id)
            if row.get("contract_version_id") == contract.contract_version_id
            and self._matches_scope(row, case_id, principal)
        ]
        cells = [DecisionSurfaceCellVersion.model_validate(row) for row in cell_rows]
        cell_by_version = {cell.cell_version_id: cell for cell in cells}
        slot_rows = [
            row
            for row in catalog.list_versions("canonical_evidence_slot_versions", case_id=case_id)
            if row.get("cell_version_id") in cell_by_version and self._matches_scope(row, case_id, principal)
        ]
        use_p36_profile = (
            bool(self._p36_active_roles)
            and contract.compiler_policy_ref == self._p36_compiler_policy_ref
        )
        active_roles = (
            self._p36_active_roles
            if use_p36_profile
            else tuple(self._contract["active_slot_roles"])
        )
        slots_by_role: dict[str, tuple[DecisionSurfaceCellVersion, EvidenceSlotVersion]] = {}
        for row in slot_rows:
            slot = EvidenceSlotVersion.model_validate(row)
            if slot.evidence_role not in active_roles:
                continue
            if slot.evidence_role in slots_by_role:
                raise EvidenceServiceError("active_evidence_slot_cardinality_violation", 409)
            slots_by_role[slot.evidence_role] = (cell_by_version[slot.cell_version_id], slot)
        if set(slots_by_role) != set(active_roles):
            raise EvidenceServiceError("active_evidence_slot_missing", 409)
        return {
            "checkpoint": checkpoint,
            "contract": contract,
            "work_unit": work_unit,
            "slots_by_role": slots_by_role,
            "active_roles": active_roles,
            "fixture_contract_ref": (
                P36_CANDIDATE_PROFILE if use_p36_profile else CONTRACT_RELATIVE_PATH
            ),
            "fixture_contract_digest": (
                self._p36_profile_digest if use_p36_profile else self._contract_digest
            ),
        }

    def _compile_slots(self, context: Mapping[str, Any], principal: CasePrincipal) -> tuple[list[dict[str, Any]], dict[str, int]]:
        compiled: list[dict[str, Any]] = []
        fixture_sets = self._fixture_candidate_sets
        display_by_id = {
            row["metadata"]["candidate_id"]: row["display"]
            for rows in fixture_sets.values()
            for row in rows
        }
        authority_by_route = {
            route_id: entry.source_authority
            for entry in self._registry.entries
            for route_id in entry.declared_route_ids
        }
        for role in context["active_roles"]:
            cell, slot = context["slots_by_role"][role]
            request_result = self._request_compiler.compile(
                contract=context["contract"],
                cell=cell,
                slot=slot,
            )
            plan_result = self._planner.plan(
                request=request_result.request,
                permissions=PlannerPermissionContext(
                    permission_snapshot_ref=self._permission_ref(principal),
                    allowed_tool_ids=tuple(entry.tool_id for entry in self._registry.entries),
                    required_permission_scope=self._planner.policy.required_permission_scope,
                ),
            )
            metadata = tuple(
                CandidateMetadata.model_validate(row["metadata"]) for row in fixture_sets[role]
            )
            snapshot = CandidateMetadataSnapshot.create(
                snapshot_id=f"point03:{context['contract'].contract_version_id}:{slot.evidence_slot_id}",
                candidates=metadata,
            )
            bundle_result = self._candidate_compiler.compile(
                request=request_result.request,
                plan=plan_result.plan,
                snapshot=snapshot,
            )
            if any(
                (
                    request_result.model_call_count,
                    request_result.external_call_count,
                    plan_result.model_call_count,
                    plan_result.external_call_count,
                    plan_result.tool_invocation_count,
                    bundle_result.model_call_count,
                    bundle_result.retrieval_call_count,
                    bundle_result.external_call_count,
                )
            ):
                raise EvidenceServiceError("fixture_execution_boundary_violated", 409)
            candidates = []
            for item in bundle_result.bundle.candidates:
                display = display_by_id[item.candidate_id]
                candidates.append(
                    {
                        "candidate_id": item.candidate_id,
                        "display_state": "candidate" if item.candidate_kind == "top_k_seed" else "context_only",
                        "candidate_kind": item.candidate_kind,
                        "title": display["title"],
                        "source_name": display["source_name"],
                        "source_type": display["source_type"],
                        "published_at": display["published_at"],
                        "citation": display["citation"],
                        "excerpt": display["excerpt"],
                        "authority_label": display["authority_label"],
                        "source_authority": authority_by_route[item.route_id],
                        "source_role": item.source_role,
                        "source_authority_rank": item.source_authority_rank,
                        "source_policy_ref": item.source_policy_ref,
                        "route_id": item.route_id,
                        "document_id": item.document_id,
                        "document_version": item.document_version,
                        "entity_ref": item.entity_ref,
                        "period_ref": item.period_ref,
                        "section_or_table_ref": item.section_or_table_ref,
                        "content_ref": item.content_ref,
                        "applicability_boundary": display["applicability_boundary"],
                        "promotion_boundary": "not_in_Point03_VT1",
                    }
                )
            compiled.append(
                {
                    "evidence_slot_id": slot.evidence_slot_id,
                    "evidence_role": role,
                    "cell_id": cell.cell_id,
                    "decision_question": cell.decision_question,
                    "owner": cell.owner_role,
                    "required": slot.required,
                    "display_state": "typed_gap" if bundle_result.bundle.typed_gap_codes else "candidate",
                    "request_id": request_result.request.request_id,
                    "request_digest": request_result.request.request_digest,
                    "request_contract": request_result.request.model_dump(mode="json"),
                    "tool_plan_id": plan_result.plan.plan_id,
                    "tool_plan_status": plan_result.plan.status,
                    "bundle_id": bundle_result.bundle.bundle_id,
                    "candidate_bundle_contract": bundle_result.bundle.model_dump(mode="json"),
                    "bundle_status": bundle_result.bundle.status,
                    "exhaustion_status": bundle_result.bundle.exhaustion_status,
                    "typed_gap_codes": list(bundle_result.bundle.typed_gap_codes),
                    "candidates": candidates,
                }
            )
        counts = self._counts(compiled, [])
        return compiled, counts

    def _view(self, case_id: str, principal: CasePrincipal) -> dict[str, Any]:
        store = self._facade_or_raise().store
        projection = self._projection_row(store, case_id, principal)
        actions = self._actions(store, case_id, principal, str(projection["workspace_id"]))
        outcomes = self._repair_outcomes(store, case_id, principal, str(projection["workspace_id"]))
        slots = deepcopy(list(projection["evidence_slots"]))
        rejected = {str(row["candidate_id"]): row for row in actions if row["action_type"] == "reject_candidate"}
        repairs = {str(row["evidence_slot_id"]): row for row in actions if row["action_type"] == "request_repair"}
        for slot in slots:
            slot.pop("request_contract", None)
            slot.pop("candidate_bundle_contract", None)
            if slot["evidence_slot_id"] in repairs:
                slot["display_state"] = "repair_requested"
            outcome = next(
                (row for row in outcomes if row["evidence_slot_id"] == slot["evidence_slot_id"]),
                None,
            )
            if outcome:
                slot["display_state"] = "candidate"
                slot["typed_gap_codes"] = []
                slot["candidates"].append(deepcopy(outcome["candidate"]))
            for candidate in slot["candidates"]:
                action = rejected.get(candidate["candidate_id"])
                if action:
                    candidate["display_state"] = "rejected"
                    candidate["review_reason"] = action["reason"]
            slot["candidates"] = [self._candidate_view(candidate) for candidate in slot["candidates"]]
        return {
            "case_id": case_id,
            "workspace_id": projection["workspace_id"],
            "workspace_version": self._workspace_version(store, projection),
            "projection_version_id": projection["projection_version_id"],
            "status": projection["current_status"],
            "fixture_mode": "fixture_shadow_internal_only",
            "decision_surface_contract_version_id": projection["contract_version_id"],
            "planning_checkpoint_version_id": projection["checkpoint_version_id"],
            "work_unit_id": projection["work_unit_id"],
            "counts": self._counts(slots, actions, outcomes),
            "slots": slots,
            "review_actions": [self._action_view(row) for row in actions],
            "repair_outcomes": [self._repair_outcome_view(row) for row in outcomes],
            "available_actions": ["reject_candidate", "request_repair", "execute_repair"],
            "hard_boundaries": dict(projection["hard_boundaries"]),
        }

    @staticmethod
    def _counts(
        slots: list[dict[str, Any]],
        actions: list[Mapping[str, Any]],
        outcomes: list[Mapping[str, Any]] | None = None,
    ) -> dict[str, int]:
        candidates = [candidate for slot in slots for candidate in slot["candidates"]]
        completed_slots = {str(row["evidence_slot_id"]) for row in outcomes or []}
        return {
            "slot_count": len(slots),
            "total_candidate_count": len(candidates),
            "candidate_count": sum(item["display_state"] == "candidate" for item in candidates),
            "context_only_count": sum(item["display_state"] == "context_only" for item in candidates),
            "rejected_count": sum(item["display_state"] == "rejected" for item in candidates),
            "typed_gap_count": sum(bool(slot["typed_gap_codes"]) for slot in slots),
            "repair_requested_count": len(
                {row["evidence_slot_id"] for row in actions if row["action_type"] == "request_repair"}
            ),
            "repair_completed_count": len(completed_slots),
            "review_action_count": len(actions),
        }

    @staticmethod
    def _repair_outcome_view(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "repair_outcome_id": row["repair_outcome_id"],
            "evidence_slot_id": row["evidence_slot_id"],
            "request_review_action_id": row["request_review_action_id"],
            "attempt_no": row["attempt_no"],
            "attempt_state": row["attempt_state"],
            "route_id": row["route_id"],
            "candidate_id": row["candidate"]["candidate_id"],
            "completed_at": row["recorded_at"],
            "external_call_count": row["external_call_count"],
            "tool_invocation_count": row["tool_invocation_count"],
            "boundary": row["candidate"]["applicability_boundary"],
        }

    @staticmethod
    def _candidate_view(row: Mapping[str, Any]) -> dict[str, Any]:
        fields = (
            "candidate_id",
            "display_state",
            "candidate_kind",
            "title",
            "source_name",
            "source_type",
            "published_at",
            "citation",
            "excerpt",
            "authority_label",
            "source_authority",
            "source_role",
            "source_authority_rank",
            "source_policy_ref",
            "route_id",
            "document_id",
            "document_version",
            "entity_ref",
            "period_ref",
            "section_or_table_ref",
            "content_ref",
            "applicability_boundary",
            "promotion_boundary",
        )
        candidate = {field: row[field] for field in fields}
        if row.get("review_reason") is not None:
            candidate["review_reason"] = row["review_reason"]
        return candidate

    @staticmethod
    def _action_view(row: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "review_action_id": row["review_action_id"],
            "action_type": row["action_type"],
            "evidence_slot_id": row["evidence_slot_id"],
            "candidate_id": row.get("candidate_id"),
            "reason": row["reason"],
            "actor_ref": row["actor_snapshot_ref"],
            "recorded_at": row["recorded_at"],
            "workspace_version_after": row["workspace_version_after"],
        }

    def _resolve_target(
        self,
        projection: Mapping[str, Any],
        *,
        action_type: str,
        candidate_id: str | None,
        evidence_slot_id: str | None,
    ) -> str:
        for slot in projection["evidence_slots"]:
            if action_type == "request_repair" and slot["evidence_slot_id"] == evidence_slot_id:
                return str(evidence_slot_id)
            if action_type == "reject_candidate" and any(
                candidate["candidate_id"] == candidate_id for candidate in slot["candidates"]
            ):
                return str(slot["evidence_slot_id"])
        code = "candidate_not_found" if action_type == "reject_candidate" else "evidence_slot_not_found"
        raise EvidenceServiceError(code, 404, target_id=candidate_id or evidence_slot_id)

    def _projection_row(
        self,
        catalog: Any,
        case_id: str,
        principal: CasePrincipal,
        *,
        required: bool = True,
    ) -> Mapping[str, Any] | None:
        rows = [
            row
            for row in catalog.list_latest(PROJECTION_TABLE, case_id=case_id)
            if self._matches_scope(row, case_id, principal)
        ]
        if len(rows) > 1:
            raise EvidenceServiceError("evidence_workspace_cardinality_violation", 409)
        if not rows:
            if required:
                raise EvidenceServiceError("evidence_workspace_not_found", 404, case_id=case_id)
            return None
        return rows[0]

    def _actions(self, catalog: Any, case_id: str, principal: CasePrincipal, workspace_id: str) -> list[Mapping[str, Any]]:
        rows = [
            row
            for row in catalog.list_versions(REVIEW_TABLE, case_id=case_id)
            if self._matches_scope(row, case_id, principal) and row.get("workspace_id") == workspace_id
        ]
        return sorted(rows, key=lambda row: int(row["workspace_version_after"]))

    def _repair_outcomes(
        self,
        catalog: Any,
        case_id: str,
        principal: CasePrincipal,
        workspace_id: str,
    ) -> list[Mapping[str, Any]]:
        rows = [
            row
            for row in catalog.list_versions(REPAIR_OUTCOME_TABLE, case_id=case_id)
            if self._matches_scope(row, case_id, principal) and row.get("workspace_id") == workspace_id
        ]
        return sorted(rows, key=lambda row: int(row["workspace_version_after"]))

    def _workspace_version(self, catalog: Any, projection: Mapping[str, Any] | None) -> int:
        if projection is None:
            return 0
        actions = self._actions(
            catalog,
            str(projection["case_id"]),
            CasePrincipal(
                tenant_id=str(projection["tenant_id"]),
                project_id=str(projection["project_id"]),
                actor_id="projection-read",
                permissions=frozenset(),
            ),
            str(projection["workspace_id"]),
        )
        outcomes = self._repair_outcomes(
            catalog,
            str(projection["case_id"]),
            CasePrincipal(
                tenant_id=str(projection["tenant_id"]),
                project_id=str(projection["project_id"]),
                actor_id="projection-read",
                permissions=frozenset(),
            ),
            str(projection["workspace_id"]),
        )
        return max(
            [
                int(projection["workspace_version"]),
                *[int(row["workspace_version_after"]) for row in actions],
                *[int(row["workspace_version_after"]) for row in outcomes],
            ]
        )

    def _case_row(self, catalog: Any, case_id: str, principal: CasePrincipal) -> Mapping[str, Any]:
        row = catalog.get_latest("canonical_research_cases", case_id)
        if not row or not self._matches_scope(row, case_id, principal):
            raise EvidenceServiceError("case_not_found", 404, case_id=case_id)
        return row

    def _actor_snapshot(self, catalog: Any, actor_ref: str, principal: CasePrincipal) -> None:
        row = catalog.get_latest("canonical_actor_snapshots", f"fixture_actor:{actor_ref}")
        if not row or row.get("tenant_id") != principal.tenant_id or row.get("project_id") != principal.project_id:
            raise EvidenceServiceError("actor_snapshot_not_found", 403)

    @staticmethod
    def _matches_scope(row: Mapping[str, Any], case_id: str, principal: CasePrincipal) -> bool:
        return (
            row.get("tenant_id") == principal.tenant_id
            and row.get("project_id") == principal.project_id
            and row.get("case_id") == case_id
        )

    @staticmethod
    def _permission_ref(principal: CasePrincipal) -> str:
        return f"fixture_permissions:{principal.tenant_id}:{principal.actor_id}"

    @staticmethod
    def _idempotency_scope(case_id: str, key: str, principal: CasePrincipal) -> str:
        return f"point03:{principal.tenant_id}:{principal.project_id}:{case_id}:{key}"

    @staticmethod
    def _check_idempotency(catalog: Any, scope_key: str, payload_digest: str) -> bool:
        existing = catalog.get_idempotency(scope_key)
        if not existing:
            return False
        if existing["payload_digest"] != payload_digest:
            raise IdempotencyConflict("point03_idempotency_payload_conflict")
        return True

    @staticmethod
    def _with_content_digest(model: Any) -> Any:
        payload = model.model_dump(mode="json")
        payload["content_digest"] = ""
        return model.model_copy(update={"content_digest": canonical_digest(payload)})

    @staticmethod
    def _event(
        catalog: Any,
        *,
        event_type: str,
        actor_ref: str,
        trace_id: str,
        work_unit_id: str,
        state_before: int,
        state_after: int,
        payload: dict[str, Any],
    ) -> EventEnvelope:
        now = utc_now()
        return EventEnvelope(
            event_id="event_p03_" + canonical_digest(
                {"event_type": event_type, "trace_id": trace_id, "payload": payload}
            )[:24],
            event_type=event_type,
            work_unit_id=work_unit_id,
            sequence_no=catalog.next_event_sequence(None),
            occurred_at=now,
            recorded_at=now,
            actor_snapshot_ref=f"fixture_actor:{actor_ref}",
            correlation_id=trace_id,
            state_version_before=state_before,
            state_version_after=state_after,
            payload_digest=canonical_digest(payload),
            payload=payload,
        )

    def _facade_or_raise(self) -> Any:
        if self._facade is None:
            raise EvidenceServiceError("operation_not_admitted", 403, reason_detail=self._unavailable_reason)
        return self._facade

    @staticmethod
    def _require_permission(principal: CasePrincipal, permission: str) -> None:
        if (
            not principal.tenant_id
            or not principal.project_id
            or not principal.actor_id
            or permission not in principal.permissions
        ):
            raise EvidenceServiceError("permission_denied", 403, required_permission=permission)

    @staticmethod
    def _require_actor(actor_ref: str, principal: CasePrincipal) -> None:
        if actor_ref != principal.actor_id:
            raise EvidenceServiceError("actor_scope_mismatch", 403)

    @staticmethod
    def _require_request(case_id: str, idempotency_key: str, trace_id: str) -> None:
        if not case_id.strip() or not idempotency_key.strip() or not trace_id.strip():
            raise EvidenceServiceError("request_validation_error", 422)

    @staticmethod
    def _service_error(error: Exception) -> EvidenceServiceError:
        if isinstance(error, EvidenceServiceError):
            return error
        if isinstance(error, IdempotencyConflict):
            return EvidenceServiceError("idempotency_conflict", 409)
        if isinstance(error, TransactionConflict):
            return EvidenceServiceError("version_conflict", 409, conflict_reason=str(error))
        if isinstance(error, (KeyError, ValueError)):
            return EvidenceServiceError("evidence_fixture_contract_invalid", 409, cause=str(error))
        return EvidenceServiceError("evidence_backend_unavailable", 503, cause=str(error))
