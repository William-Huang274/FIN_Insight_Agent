from __future__ import annotations

from typing import Iterable

from pydantic import Field

from .evidence_request import EvidenceRequest
from .models import StrictModel, canonical_digest


class ToolPlannerError(ValueError):
    """Raised for invalid deterministic Tool Registry or plan inputs."""


class ToolRegistryEntry(StrictModel):
    tool_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    capabilities: tuple[str, ...] = Field(min_length=1)
    input_schema_ref: str = Field(min_length=1)
    output_schema_ref: str = Field(min_length=1)
    source_role: str = Field(min_length=1)
    source_authority: str = Field(min_length=1)
    source_authority_rank: int = Field(ge=0)
    can_support: tuple[str, ...] = Field(min_length=1)
    cannot_support: tuple[str, ...] = Field(min_length=1)
    cost_class: str = Field(min_length=1)
    cost_rank: int = Field(ge=0)
    latency_class: str = Field(min_length=1)
    failure_types: tuple[str, ...] = Field(min_length=1)
    fallback_tool_ids: tuple[str, ...] = ()
    permission_scope: str = Field(min_length=1)
    forbidden_claims: tuple[str, ...] = Field(min_length=1)
    supported_evidence_roles: tuple[str, ...] = Field(min_length=1)
    supported_source_policy_refs: tuple[str, ...] = Field(min_length=1)
    declared_route_ids: tuple[str, ...] = Field(min_length=1)
    execution_mode: str = "not_admitted"


class PlannerPolicy(StrictModel):
    policy_ref: str = Field(min_length=1)
    max_tool_calls: int = Field(ge=0)
    max_fallback_depth: int = Field(ge=0)
    required_permission_scope: str = Field(min_length=1)
    minimum_source_authority_rank_by_evidence_role: dict[str, int]
    required_execution_admission: str = Field(min_length=1)
    stop_rules: tuple[str, ...] = Field(min_length=1)


class ToolRegistrySnapshot(StrictModel):
    registry_id: str = Field(min_length=1)
    registry_version: int = Field(ge=1)
    snapshot_id: str = Field(min_length=1)
    snapshot_digest: str = Field(min_length=1)
    entries: tuple[ToolRegistryEntry, ...] = Field(min_length=1)
    execution_admission: str = "not_admitted"

    @classmethod
    def create(cls, *, registry_id: str, registry_version: int, entries: Iterable[ToolRegistryEntry]) -> "ToolRegistrySnapshot":
        items = tuple(entries)
        ids = [item.tool_id for item in items]
        if len(ids) != len(set(ids)):
            raise ToolPlannerError("duplicate_tool_registry_id")
        if any(item.execution_mode != "not_admitted" for item in items):
            raise ToolPlannerError("tool_execution_mode_not_denied")
        snapshot_id = f"{registry_id}:v{registry_version}"
        digest = canonical_digest({"snapshot_id": snapshot_id, "entries": [item.model_dump(mode="json") for item in items]})
        return cls(registry_id=registry_id, registry_version=registry_version, snapshot_id=snapshot_id, snapshot_digest=digest, entries=items)


class PlannerPermissionContext(StrictModel):
    permission_snapshot_ref: str = Field(min_length=1)
    allowed_tool_ids: tuple[str, ...]
    required_permission_scope: str = Field(min_length=1)
    context_kind: str = "declarative_planning_allowlist_not_execution_authority"


class ToolSelectionStep(StrictModel):
    planner_step_id: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    state: str = Field(min_length=1)
    selected_tool_id: str | None = None
    selected_route_id: str | None = None
    selection_rationale: str = Field(min_length=1)
    fallback_if_fail: str | None = None
    budget_before: int = Field(ge=0)
    budget_after: int = Field(ge=0)
    required_capability: str | None = None
    execution_admission: str = "required_m5_4_capability_check"
    invocation_status: str = "not_executed"


class ToolSelectionPlan(StrictModel):
    plan_id: str = Field(min_length=1)
    plan_digest: str = Field(min_length=1)
    request_id: str = Field(min_length=1)
    request_digest: str = Field(min_length=1)
    registry_snapshot_id: str = Field(min_length=1)
    registry_snapshot_digest: str = Field(min_length=1)
    planner_policy_ref: str = Field(min_length=1)
    permission_snapshot_ref: str = Field(min_length=1)
    status: str = Field(min_length=1)
    steps: tuple[ToolSelectionStep, ...] = ()
    planned_tool_call_count: int = Field(ge=0)
    remaining_tool_call_budget: int = Field(ge=0)
    stop_reason: str | None = None
    execution_admission: str = "required_m5_4_capability_check"
    persistence_admission: str = "not_admitted"


class ToolSelectionResult(StrictModel):
    status: str
    plan: ToolSelectionPlan
    model_call_count: int = 0
    external_call_count: int = 0
    tool_invocation_count: int = 0
    store_write_count: int = 0


class BoundedToolPlanner:
    """M6.2 registry snapshot and planning-only state machine; it cannot invoke tools."""

    def __init__(self, *, registry: ToolRegistrySnapshot, policy: PlannerPolicy):
        self.registry = registry
        self.policy = policy

    def _eligible_entries(
        self,
        *,
        request: EvidenceRequest,
        route_id: str,
        permissions: PlannerPermissionContext,
    ) -> tuple[ToolRegistryEntry, ...]:
        minimum_rank = self.policy.minimum_source_authority_rank_by_evidence_role.get(request.accepted_evidence_role)
        if minimum_rank is None:
            raise ToolPlannerError(f"evidence_role_authority_policy_missing:{request.accepted_evidence_role}")
        entries = [
            entry
            for entry in self.registry.entries
            if route_id in entry.declared_route_ids
            and request.accepted_evidence_role in entry.supported_evidence_roles
            and request.source_policy in entry.supported_source_policy_refs
            and entry.source_authority_rank >= minimum_rank
            and entry.permission_scope == self.policy.required_permission_scope == permissions.required_permission_scope
            and entry.tool_id in permissions.allowed_tool_ids
            and entry.execution_mode == "not_admitted"
        ]
        return tuple(sorted(entries, key=lambda item: (-item.source_authority_rank, item.cost_rank, item.tool_id)))

    def plan(self, *, request: EvidenceRequest, permissions: PlannerPermissionContext) -> ToolSelectionResult:
        if request.execution_admission != "not_admitted":
            raise ToolPlannerError("request_execution_admission_must_be_not_admitted")
        if permissions.context_kind != "declarative_planning_allowlist_not_execution_authority":
            raise ToolPlannerError("planner_permission_context_must_not_claim_execution_authority")
        budget = min(request.budget.tool_call_limit, self.policy.max_tool_calls)
        base_payload = {
            "request_id": request.request_id,
            "request_digest": request.request_digest,
            "registry_snapshot_id": self.registry.snapshot_id,
            "registry_snapshot_digest": self.registry.snapshot_digest,
            "planner_policy_ref": self.policy.policy_ref,
            "permission_snapshot_ref": permissions.permission_snapshot_ref,
        }
        if request.accepted_evidence_role == "gap_evidence":
            return self._stopped(base_payload, budget=budget, reason="commercial_gap_stop_rule")
        if budget == 0:
            return self._stopped(base_payload, budget=0, reason="budget_exhausted_stop_rule")

        routes = tuple(request.preferred_routes) + tuple(request.fallback_routes)
        selected: list[tuple[str, ToolRegistryEntry, str]] = []
        fallback_count = 0
        for route_id in routes:
            entries = self._eligible_entries(request=request, route_id=route_id, permissions=permissions)
            if not entries:
                continue
            phase = "SELECT_TOOL" if not selected else "FALLBACK_OR_STOP"
            if phase == "FALLBACK_OR_STOP":
                fallback_count += 1
                if fallback_count > self.policy.max_fallback_depth:
                    break
            selected.append((route_id, entries[0], phase))
            if len(selected) >= budget:
                break
        if not selected:
            raw_route_entries = [entry for route_id in routes for entry in self.registry.entries if route_id in entry.declared_route_ids]
            reason = "permission_scope_stop_rule" if raw_route_entries else "route_exhaustion_stop_rule"
            return self._stopped(base_payload, budget=budget, reason=reason)

        steps: list[ToolSelectionStep] = []
        remaining = budget
        for index, (route_id, entry, state) in enumerate(selected, 1):
            before = remaining
            remaining -= 1
            fallback = selected[index][0] if index < len(selected) else None
            steps.append(
                ToolSelectionStep(
                    planner_step_id=f"{request.request_id}:step:{index}",
                    request_id=request.request_id,
                    state=state,
                    selected_tool_id=entry.tool_id,
                    selected_route_id=route_id,
                    selection_rationale=f"authority_rank={entry.source_authority_rank};cost_rank={entry.cost_rank};route={route_id}",
                    fallback_if_fail=fallback,
                    budget_before=before,
                    budget_after=remaining,
                    required_capability=entry.capabilities[0],
                    execution_admission=self.policy.required_execution_admission,
                )
            )
        plan_payload = {**base_payload, "status": "await_execution_admission", "steps": [step.model_dump(mode="json") for step in steps], "planned_tool_call_count": len(steps), "remaining_tool_call_budget": remaining, "stop_reason": None, "execution_admission": self.policy.required_execution_admission, "persistence_admission": "not_admitted"}
        digest = canonical_digest(plan_payload)
        plan = ToolSelectionPlan(plan_id=f"tool_selection_plan_{digest[:20]}", plan_digest=digest, **plan_payload)
        return ToolSelectionResult(status="pass", plan=plan)

    def _stopped(self, base_payload: dict[str, str], *, budget: int, reason: str) -> ToolSelectionResult:
        plan_payload = {**base_payload, "status": "stopped", "steps": [], "planned_tool_call_count": 0, "remaining_tool_call_budget": budget, "stop_reason": reason, "execution_admission": self.policy.required_execution_admission, "persistence_admission": "not_admitted"}
        digest = canonical_digest(plan_payload)
        plan = ToolSelectionPlan(plan_id=f"tool_selection_plan_{digest[:20]}", plan_digest=digest, **plan_payload)
        return ToolSelectionResult(status="pass", plan=plan)
