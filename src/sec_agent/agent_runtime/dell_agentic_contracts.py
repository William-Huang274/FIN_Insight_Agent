"""Zero-model domain contracts for the Dell agentic research vertical.

This module deliberately contains no provider, MCP, network, storage, or queue
client.  It is the machine-readable boundary between an autonomous planner and
the host-owned integrity controls described by the Dell v1.2 technical design.

Two rules are especially important here:

* provider-visible intent never contains sealed runtime selectors or authority;
* an empty result or a tool failure is never, by itself, a public-information
  gap.

All durable models are strict, frozen, and composed only from JSON-safe scalar
values, tuples, and other frozen models.  Digest-bearing artifacts use the
repository canonical JSON convention (bare, lowercase SHA-256 hex).
"""

from __future__ import annotations

import base64
import binascii
import html
import json
from datetime import date
import re
from typing import Any, Iterable, Literal, Mapping, Protocol, TypeVar
from urllib.parse import unquote
import unicodedata

from pydantic import BaseModel, Field, field_validator, model_validator

from sec_agent.canonical_runtime.contracts_v1_2 import (
    StrictFrozenModel,
    canonical_json,
    canonical_json_sha256,
)


Digest = str
EvidenceSatisfaction = Literal[
    "uncovered",
    "partial",
    "covered",
    "disputed",
    "bounded_gap",
]
Materiality = Literal["high", "medium", "low"]
RouteKind = Literal[
    "reviewed_evidence",
    "local_candidate",
    "s2_numeric_fact",
    "external_source",
    "calculator",
]
TaskStatus = Literal[
    "planned",
    "ready",
    "running",
    "paused",
    "completed",
    "deferred",
    "cancelled",
]
NodeKind = Literal[
    "lead",
    "specialist",
    "counter",
    "semantic_research_verifier",
    "writer",
    "final_semantic_verifier",
    "model_assisted_repair",
]
NextActionKind = Literal[
    "read_evidence",
    "request_data_inventory",
    "request_deeper_inventory",
    "correct_period_intent",
    "replace_source_family_ref",
    "choose_qualified_alternative_route",
    "retry_transport",
    "submit_plan_delta",
    "request_disclosure",
    "request_human_review",
    "pause",
    "request_gap_eligibility",
]

DELL_COVERAGE_OBLIGATION_IDS: tuple[str, ...] = (
    "Q1_ISSUER_TRUTH",
    "Q2_DEMAND_QUALITY",
    "Q3_UNITS_ASP_PVM",
    "Q4_ARCHITECTURE_RAMP",
    "Q5_SUPPLY_AND_PRICE",
    "Q6_MODEL_COMPUTE_DEMAND",
    "Q7_EXPORT_CONTROL_CHINA",
    "Q8_COMPETITION_VALUE_POOL",
    "Q9_COUNTEREVIDENCE_WWC",
)

_DIGEST_PATTERN = r"^[0-9a-f]{64}$"
_REF_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,239}$"
_T = TypeVar("_T", bound="_StrictFrozenModel")


class _StrictFrozenModel(StrictFrozenModel):
    """FIN domain models share the canonical runtime's one strict base."""


def _canonical_value(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Return the one canonical JSON representation used by v1.2 receipts."""
    return canonical_json(_canonical_value(value)).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return canonical_json_sha256(_canonical_value(value))


def research_objective_digest(objective: str) -> str:
    """Digest the exact public objective projected into one model turn."""

    return canonical_digest({"objective": objective})


def task_assignment_authority_digest(
    *,
    agent_id: str,
    agent_role: str,
    task_id: str,
    task_kind: str,
    objective_digest: str,
    accepted_plan_digest: str,
    research_graph_digest: str,
) -> str:
    """Bind one task assignment to its current objective, plan and graph."""

    return canonical_digest(
        {
            "agent_id": agent_id,
            "agent_role": agent_role,
            "task_id": task_id,
            "task_kind": task_kind,
            "objective_digest": objective_digest,
            "accepted_plan_digest": accepted_plan_digest,
            "research_graph_digest": research_graph_digest,
        }
    )


def payload_without(model: BaseModel, *field_names: str) -> dict[str, Any]:
    payload = model.model_dump(mode="json")
    for field_name in field_names:
        payload.pop(field_name, None)
    return payload


def _verify_digest(model: BaseModel, field_name: str, code: str) -> None:
    supplied = getattr(model, field_name)
    if canonical_digest(payload_without(model, field_name)) != supplied:
        raise ValueError(code)


def _unique(values: tuple[str, ...], code: str) -> tuple[str, ...]:
    if len(values) != len(set(values)):
        raise ValueError(code)
    return values


def _parse_iso_date(value: str, code: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(code) from exc


class CoverageObligation(_StrictFrozenModel):
    """One product question, with registration, reachability, and proof separate."""

    obligation_id: str = Field(pattern=_REF_PATTERN)
    title: str = Field(min_length=1, max_length=240)
    research_surface: str = Field(min_length=1, max_length=2_000)
    minimum_completion_semantics: str = Field(min_length=1, max_length=2_000)
    materiality: Materiality
    registered: bool
    plan_reachable: bool
    reachable_task_ids: tuple[str, ...] = Field(default=(), max_length=64)
    evidence_satisfaction: EvidenceSatisfaction = "uncovered"
    evidence_refs: tuple[str, ...] = Field(default=(), max_length=256)
    numeric_fact_refs: tuple[str, ...] = Field(default=(), max_length=256)
    calculation_refs: tuple[str, ...] = Field(default=(), max_length=256)
    counter_finding_refs: tuple[str, ...] = Field(default=(), max_length=128)
    material_requirement_receipt_refs: tuple[str, ...] = Field(
        default=(), max_length=64
    )
    verifier_transition_receipt_refs: tuple[str, ...] = Field(
        default=(), max_length=64
    )
    lead_disposition_receipt_refs: tuple[str, ...] = Field(default=(), max_length=64)
    gap_eligibility_receipt_ref: str | None = Field(
        default=None, pattern=_REF_PATTERN
    )
    human_acceptance_receipt_ref: str | None = Field(
        default=None, pattern=_REF_PATTERN
    )

    @model_validator(mode="after")
    def validate_separate_coverage_dimensions(self) -> "CoverageObligation":
        for name in (
            "reachable_task_ids",
            "evidence_refs",
            "numeric_fact_refs",
            "calculation_refs",
            "counter_finding_refs",
            "material_requirement_receipt_refs",
            "verifier_transition_receipt_refs",
            "lead_disposition_receipt_refs",
        ):
            _unique(tuple(getattr(self, name)), f"coverage_{name}_duplicate")

        if not self.registered:
            if self.plan_reachable or self.reachable_task_ids:
                raise ValueError("unregistered_obligation_cannot_be_plan_reachable")
            if self.evidence_satisfaction != "uncovered":
                raise ValueError("unregistered_obligation_cannot_be_evidence_satisfied")
        if self.plan_reachable != bool(self.reachable_task_ids):
            raise ValueError("coverage_plan_reachability_task_mismatch")

        support_refs = (
            self.evidence_refs + self.numeric_fact_refs + self.calculation_refs
        )
        if self.evidence_satisfaction == "uncovered" and any(
            (
                support_refs,
                self.counter_finding_refs,
                self.material_requirement_receipt_refs,
                self.verifier_transition_receipt_refs,
                self.lead_disposition_receipt_refs,
                (self.gap_eligibility_receipt_ref,)
                if self.gap_eligibility_receipt_ref is not None
                else (),
                (self.human_acceptance_receipt_ref,)
                if self.human_acceptance_receipt_ref is not None
                else (),
            )
        ):
            raise ValueError("uncovered_obligation_has_proof_refs")
        if self.evidence_satisfaction == "partial" and not support_refs:
            raise ValueError("partial_coverage_requires_support_ref")
        if self.evidence_satisfaction == "covered":
            if not self.registered or not self.plan_reachable or not support_refs:
                raise ValueError("covered_obligation_requires_reachable_support")
            if (
                not self.material_requirement_receipt_refs
                or not self.verifier_transition_receipt_refs
            ):
                raise ValueError(
                    "covered_obligation_requires_material_and_verifier_closure"
                )
            if self.materiality == "high" and not self.counter_finding_refs:
                raise ValueError("high_materiality_coverage_requires_counter_surface")
        if self.evidence_satisfaction == "disputed":
            if len(support_refs) < 2 or not self.counter_finding_refs:
                raise ValueError("disputed_obligation_requires_conflicting_support")
            if (
                not self.lead_disposition_receipt_refs
                or self.human_acceptance_receipt_ref is None
                or not self.verifier_transition_receipt_refs
            ):
                raise ValueError(
                    "disputed_obligation_requires_disposition_human_and_verifier"
                )
        if self.evidence_satisfaction == "bounded_gap":
            if (
                self.gap_eligibility_receipt_ref is None
                or self.human_acceptance_receipt_ref is None
                or not self.verifier_transition_receipt_refs
            ):
                raise ValueError(
                    "bounded_gap_requires_gap_human_and_verifier_receipts"
                )
        elif self.gap_eligibility_receipt_ref is not None:
            raise ValueError("gap_receipt_only_valid_for_bounded_gap")
        return self


class MinimumRouteObligation(_StrictFrozenModel):
    """Answer-free minimum source route for one coverage obligation."""

    route_obligation_id: str = Field(pattern=_REF_PATTERN)
    coverage_obligation_id: str = Field(pattern=_REF_PATTERN)
    requirement: Literal["required", "optional"]
    route_kind: RouteKind
    semantic_source_family_refs: tuple[str, ...] = Field(default=(), max_length=32)
    entity_refs: tuple[str, ...] = Field(default=(), max_length=16)
    period_intents: tuple[str, ...] = Field(default=(), max_length=16)
    metric_refs: tuple[str, ...] = Field(default=(), max_length=32)
    required_authority_refs: tuple[str, ...] = Field(min_length=1, max_length=16)
    substitution_policy: Literal["none", "qualified_replacement"] = "none"
    acceptable_replacement_route_kinds: tuple[RouteKind, ...] = Field(
        default=(), max_length=5
    )
    replacement_conditions: tuple[str, ...] = Field(default=(), max_length=16)
    answer_free: Literal[True] = True
    route_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_route_contract(self) -> "MinimumRouteObligation":
        for name in (
            "semantic_source_family_refs",
            "entity_refs",
            "period_intents",
            "metric_refs",
            "required_authority_refs",
            "acceptable_replacement_route_kinds",
            "replacement_conditions",
        ):
            _unique(tuple(getattr(self, name)), f"minimum_route_{name}_duplicate")
        if self.route_kind in {
            "reviewed_evidence",
            "local_candidate",
            "external_source",
        } and not self.semantic_source_family_refs:
            raise ValueError("document_route_requires_semantic_source_family")
        if self.route_kind == "s2_numeric_fact" and not self.metric_refs:
            raise ValueError("s2_route_requires_metric_ref")
        if self.route_kind == "calculator" and not self.metric_refs:
            raise ValueError("calculator_route_requires_metric_ref")
        if self.substitution_policy == "none" and (
            self.acceptable_replacement_route_kinds or self.replacement_conditions
        ):
            raise ValueError("non_substitutable_route_has_replacement_contract")
        if self.substitution_policy == "qualified_replacement" and (
            not self.acceptable_replacement_route_kinds
            or not self.replacement_conditions
        ):
            raise ValueError("qualified_replacement_contract_incomplete")
        _verify_digest(self, "route_digest", "minimum_route_digest_mismatch")
        return self


class BaselineSourcePlan(_StrictFrozenModel):
    """Frozen, answer-free minimum route plan against an inventory snapshot."""

    contract_version: Literal["1.2"] = "1.2"
    source_plan_id: str = Field(pattern=_REF_PATTERN)
    case_id: str = Field(pattern=_REF_PATTERN)
    case_version: str = Field(min_length=1, max_length=80)
    research_as_of: str = Field(min_length=10, max_length=10)
    coverage_obligation_ids: tuple[str, ...] = Field(min_length=1, max_length=64)
    route_obligations: tuple[MinimumRouteObligation, ...] = Field(
        min_length=1, max_length=256
    )
    inventory_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    catalog_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    answer_free: Literal[True] = True
    source_plan_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_baseline_source_plan(self) -> "BaselineSourcePlan":
        _parse_iso_date(self.research_as_of, "baseline_research_as_of_invalid")
        _unique(self.coverage_obligation_ids, "baseline_coverage_obligation_duplicate")
        if set(self.coverage_obligation_ids) != set(DELL_COVERAGE_OBLIGATION_IDS):
            raise ValueError("dell_baseline_coverage_catalog_incomplete")
        route_ids = tuple(item.route_obligation_id for item in self.route_obligations)
        _unique(route_ids, "baseline_route_obligation_duplicate")
        allowed = set(self.coverage_obligation_ids)
        if any(
            item.coverage_obligation_id not in allowed
            for item in self.route_obligations
        ):
            raise ValueError("baseline_route_references_unknown_coverage_obligation")
        required_coverage = {
            item.coverage_obligation_id
            for item in self.route_obligations
            if item.requirement == "required"
        }
        if required_coverage != allowed:
            raise ValueError("baseline_each_obligation_requires_required_route")
        _verify_digest(self, "source_plan_digest", "baseline_source_plan_digest_mismatch")
        return self


class ResearchTaskSpec(_StrictFrozenModel):
    """A semantic research task; physical routes never belong in this object."""

    task_id: str = Field(pattern=_REF_PATTERN)
    owner_role: str = Field(pattern=_REF_PATTERN)
    objective: str = Field(min_length=12, max_length=4_000)
    dependency_ids: tuple[str, ...] = Field(default=(), max_length=64)
    coverage_obligation_ids: tuple[str, ...] = Field(min_length=1, max_length=32)
    success_criteria: tuple[str, ...] = Field(min_length=1, max_length=32)
    requested_capability_refs: tuple[str, ...] = Field(min_length=1, max_length=32)
    required_authority_refs: tuple[str, ...] = Field(default=(), max_length=32)
    expected_output_kinds: tuple[
        Literal[
            "branch_notebook",
            "narrative_artifact",
            "claim_ledger",
            "plan_delta",
            "verifier_finding",
        ],
        ...,
    ] = Field(min_length=1, max_length=5)
    materiality: Materiality
    status: TaskStatus = "planned"

    @model_validator(mode="after")
    def validate_semantic_task(self) -> "ResearchTaskSpec":
        for name in (
            "dependency_ids",
            "coverage_obligation_ids",
            "success_criteria",
            "requested_capability_refs",
            "required_authority_refs",
            "expected_output_kinds",
        ):
            _unique(tuple(getattr(self, name)), f"research_task_{name}_duplicate")
        if self.task_id in self.dependency_ids:
            raise ValueError("research_task_self_dependency")
        return self


def _reachable_task_ids(tasks: tuple[ResearchTaskSpec, ...]) -> set[str]:
    active = {
        task.task_id: task
        for task in tasks
        if task.status not in {"deferred", "cancelled"}
    }
    reachable: set[str] = set()
    changed = True
    while changed:
        changed = False
        for task_id, task in active.items():
            if task_id in reachable:
                continue
            if all(dependency in reachable for dependency in task.dependency_ids):
                reachable.add(task_id)
                changed = True
    return reachable


def research_plan_graph_digest(plan: "ResearchPlan") -> str:
    rows = [
        {
            "task_id": task.task_id,
            "dependency_ids": list(task.dependency_ids),
            "status": task.status,
        }
        for task in sorted(plan.tasks, key=lambda item: item.task_id)
    ]
    return canonical_digest(rows)


class ResearchPlan(_StrictFrozenModel):
    contract_version: Literal["1.2"] = "1.2"
    plan_id: str = Field(pattern=_REF_PATTERN)
    revision: int = Field(ge=0)
    status: Literal["draft", "accepted", "superseded"]
    case_id: str = Field(pattern=_REF_PATTERN)
    baseline_source_plan_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    catalog_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    authority_matrix_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    budget_basis_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    prior_plan_digest: Digest | None = Field(default=None, pattern=_DIGEST_PATTERN)
    coverage_obligations: tuple[CoverageObligation, ...] = Field(
        min_length=1, max_length=64
    )
    tasks: tuple[ResearchTaskSpec, ...] = Field(min_length=1, max_length=256)
    plan_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_plan_graph_and_coverage(self) -> "ResearchPlan":
        task_ids = tuple(task.task_id for task in self.tasks)
        _unique(task_ids, "research_plan_task_id_duplicate")
        known_tasks = set(task_ids)
        if any(
            dependency not in known_tasks
            for task in self.tasks
            for dependency in task.dependency_ids
        ):
            raise ValueError("research_plan_dependency_unknown")

        # A dependency graph with a cycle cannot make every active node reachable.
        reachable = _reachable_task_ids(self.tasks)
        active_ids = {
            task.task_id
            for task in self.tasks
            if task.status not in {"deferred", "cancelled"}
        }
        if reachable != active_ids:
            raise ValueError("research_plan_dependency_cycle_or_inactive_dependency")

        obligation_ids = tuple(
            obligation.obligation_id for obligation in self.coverage_obligations
        )
        _unique(obligation_ids, "research_plan_coverage_obligation_duplicate")
        allowed_obligations = set(obligation_ids)
        if any(
            obligation_id not in allowed_obligations
            for task in self.tasks
            for obligation_id in task.coverage_obligation_ids
        ):
            raise ValueError("research_plan_task_coverage_unknown")

        for obligation in self.coverage_obligations:
            if not obligation.registered:
                raise ValueError("research_plan_contains_unregistered_obligation")
            expected = tuple(
                sorted(
                    task.task_id
                    for task in self.tasks
                    if task.task_id in reachable
                    and obligation.obligation_id in task.coverage_obligation_ids
                )
            )
            if obligation.reachable_task_ids != expected:
                raise ValueError("research_plan_coverage_reachable_task_mismatch")
            if obligation.plan_reachable != bool(expected):
                raise ValueError("research_plan_coverage_reachability_mismatch")

        if self.status == "accepted" and any(
            not obligation.plan_reachable for obligation in self.coverage_obligations
        ):
            raise ValueError("accepted_plan_has_unreachable_coverage_obligation")
        if self.status == "accepted" and set(obligation_ids) != set(
            DELL_COVERAGE_OBLIGATION_IDS
        ):
            raise ValueError("accepted_dell_plan_coverage_catalog_incomplete")
        if self.revision == 0 and self.prior_plan_digest is not None:
            raise ValueError("initial_plan_prior_digest_forbidden")
        if self.revision > 0 and self.prior_plan_digest is None:
            raise ValueError("successor_plan_prior_digest_required")
        _verify_digest(self, "plan_digest", "research_plan_digest_mismatch")
        return self


class CoverageStateSnapshot(_StrictFrozenModel):
    obligation_id: str = Field(pattern=_REF_PATTERN)
    materiality: Materiality
    registered: bool
    plan_reachable: bool
    evidence_satisfaction: EvidenceSatisfaction


def coverage_state_snapshot(obligation: CoverageObligation) -> CoverageStateSnapshot:
    obligation = CoverageObligation.model_validate(
        obligation.model_dump(mode="python")
    )
    return CoverageStateSnapshot(
        obligation_id=obligation.obligation_id,
        materiality=obligation.materiality,
        registered=obligation.registered,
        plan_reachable=obligation.plan_reachable,
        evidence_satisfaction=obligation.evidence_satisfaction,
    )


class AuthorityImpact(_StrictFrozenModel):
    effect: Literal["none", "restrict", "request_future_owner_decision"] = "none"
    removed_authority_refs: tuple[str, ...] = Field(default=(), max_length=32)
    requested_authority_refs: tuple[str, ...] = Field(default=(), max_length=32)
    granted_authority_refs: tuple[str, ...] = Field(default=(), max_length=0)
    paid_authority_effect: Literal["none"] = "none"
    reason: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_no_inline_authority_grant(self) -> "AuthorityImpact":
        _unique(self.removed_authority_refs, "authority_impact_removed_duplicate")
        _unique(self.requested_authority_refs, "authority_impact_requested_duplicate")
        if self.effect == "none" and (
            self.removed_authority_refs or self.requested_authority_refs
        ):
            raise ValueError("authority_impact_none_has_changes")
        if self.effect == "restrict" and not self.removed_authority_refs:
            raise ValueError("authority_restriction_requires_removed_ref")
        if self.effect == "request_future_owner_decision" and not self.requested_authority_refs:
            raise ValueError("authority_request_requires_requested_ref")
        return self


class BudgetDelta(_StrictFrozenModel):
    model_input_tokens: int = 0
    model_output_tokens: int = 0
    model_action_attempts: int = 0
    external_tool_calls: int = 0
    wall_clock_seconds: int = 0
    requires_owner_review: bool = False
    reason: str = Field(min_length=1, max_length=1_000)

    @model_validator(mode="after")
    def validate_budget_increase_review(self) -> "BudgetDelta":
        values = (
            self.model_input_tokens,
            self.model_output_tokens,
            self.model_action_attempts,
            self.external_tool_calls,
            self.wall_clock_seconds,
        )
        if any(value > 0 for value in values) and not self.requires_owner_review:
            raise ValueError("budget_increase_requires_owner_review")
        return self


class _PlanDeltaAction(_StrictFrozenModel):
    action_id: str = Field(pattern=_REF_PATTERN)
    reason: str = Field(min_length=12, max_length=2_000)
    feedback_receipt_refs: tuple[str, ...] = Field(default=(), max_length=64)
    coverage_before: tuple[CoverageStateSnapshot, ...] = Field(
        min_length=1, max_length=64
    )
    coverage_after: tuple[CoverageStateSnapshot, ...] = Field(
        min_length=1, max_length=64
    )
    authority_impact: AuthorityImpact
    budget_delta: BudgetDelta

    @model_validator(mode="after")
    def validate_coverage_snapshots(self) -> "_PlanDeltaAction":
        before_ids = tuple(item.obligation_id for item in self.coverage_before)
        after_ids = tuple(item.obligation_id for item in self.coverage_after)
        _unique(before_ids, "plan_delta_action_coverage_before_duplicate")
        _unique(after_ids, "plan_delta_action_coverage_after_duplicate")
        if set(before_ids) != set(after_ids):
            raise ValueError("plan_delta_action_coverage_identity_changed")
        _unique(self.feedback_receipt_refs, "plan_delta_action_feedback_duplicate")
        return self


class AddTaskAction(_PlanDeltaAction):
    action_kind: Literal["add"] = "add"
    successor_task: ResearchTaskSpec


class ModifyTaskAction(_PlanDeltaAction):
    action_kind: Literal["modify"] = "modify"
    target_task_id: str = Field(pattern=_REF_PATTERN)
    changed_fields: tuple[
        Literal[
            "owner_role",
            "objective",
            "dependency_ids",
            "coverage_obligation_ids",
            "success_criteria",
            "requested_capability_refs",
            "required_authority_refs",
            "expected_output_kinds",
            "materiality",
            "status",
        ],
        ...,
    ] = Field(min_length=1, max_length=11)
    successor_task: ResearchTaskSpec

    @model_validator(mode="after")
    def validate_successor_identity(self) -> "ModifyTaskAction":
        _unique(self.changed_fields, "modify_task_changed_field_duplicate")
        if self.successor_task.task_id != self.target_task_id:
            raise ValueError("modify_task_successor_identity_mismatch")
        return self


class DeferTaskAction(_PlanDeltaAction):
    action_kind: Literal["defer"] = "defer"
    target_task_id: str = Field(pattern=_REF_PATTERN)
    defer_until: str = Field(min_length=3, max_length=1_000)
    successor_task: ResearchTaskSpec

    @model_validator(mode="after")
    def validate_deferred_successor(self) -> "DeferTaskAction":
        if self.successor_task.task_id != self.target_task_id:
            raise ValueError("defer_task_successor_identity_mismatch")
        if self.successor_task.status != "deferred":
            raise ValueError("defer_task_successor_status_invalid")
        return self


class CancelTaskAction(_PlanDeltaAction):
    action_kind: Literal["cancel"] = "cancel"
    target_task_id: str = Field(pattern=_REF_PATTERN)
    successor_task: ResearchTaskSpec
    replacement_task_ids: tuple[str, ...] = Field(default=(), max_length=32)
    human_or_verifier_disposition_receipt_refs: tuple[str, ...] = Field(
        default=(), max_length=32
    )

    @model_validator(mode="after")
    def validate_cancelled_successor(self) -> "CancelTaskAction":
        if self.successor_task.task_id != self.target_task_id:
            raise ValueError("cancel_task_successor_identity_mismatch")
        if self.successor_task.status != "cancelled":
            raise ValueError("cancel_task_successor_status_invalid")
        _unique(self.replacement_task_ids, "cancel_task_replacement_duplicate")
        _unique(
            self.human_or_verifier_disposition_receipt_refs,
            "cancel_task_disposition_duplicate",
        )
        lost_material = any(
            before.materiality in {"high", "medium"}
            and before.plan_reachable
            and not next(
                after.plan_reachable
                for after in self.coverage_after
                if after.obligation_id == before.obligation_id
            )
            for before in self.coverage_before
        )
        if lost_material and not (
            self.replacement_task_ids
            or self.human_or_verifier_disposition_receipt_refs
        ):
            raise ValueError("material_obligation_cancellation_without_disposition")
        return self


class RouteReplacement(_StrictFrozenModel):
    removed_route_obligation_id: str = Field(pattern=_REF_PATTERN)
    successor_route_obligation_ids: tuple[str, ...] = Field(min_length=1, max_length=16)
    reason: str = Field(min_length=12, max_length=2_000)
    disposition_receipt_refs: tuple[str, ...] = Field(min_length=1, max_length=32)
    condition_proof_receipt_refs: tuple[str, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_route_replacement(self) -> "RouteReplacement":
        _unique(
            self.successor_route_obligation_ids,
            "route_replacement_successor_duplicate",
        )
        _unique(self.disposition_receipt_refs, "route_replacement_disposition_duplicate")
        _unique(
            self.condition_proof_receipt_refs,
            "route_replacement_condition_proof_duplicate",
        )
        return self


def _coverage_snapshot_tuple(plan: ResearchPlan) -> tuple[CoverageStateSnapshot, ...]:
    return tuple(coverage_state_snapshot(item) for item in plan.coverage_obligations)


class AgenticPlanDeltaV1_2(_StrictFrozenModel):
    """Explicit v1.2 successor adapter for v1 add/modify/defer/cancel actions."""

    contract_version: Literal["1.2"] = "1.2"
    delta_id: str = Field(pattern=_REF_PATTERN)
    base_plan: ResearchPlan
    successor_plan: ResearchPlan
    baseline_source_plan_before: BaselineSourcePlan
    baseline_source_plan_after: BaselineSourcePlan
    add_actions: tuple[AddTaskAction, ...] = Field(default=(), max_length=128)
    modify_actions: tuple[ModifyTaskAction, ...] = Field(default=(), max_length=128)
    defer_actions: tuple[DeferTaskAction, ...] = Field(default=(), max_length=128)
    cancel_actions: tuple[CancelTaskAction, ...] = Field(default=(), max_length=128)
    coverage_before: tuple[CoverageStateSnapshot, ...] = Field(
        min_length=1, max_length=64
    )
    coverage_after: tuple[CoverageStateSnapshot, ...] = Field(
        min_length=1, max_length=64
    )
    route_replacements: tuple[RouteReplacement, ...] = Field(default=(), max_length=128)
    authority_impact: AuthorityImpact
    budget_delta: BudgetDelta
    catalog_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    authority_matrix_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    budget_basis_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    accepted_plan_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    resulting_graph_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    delta_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_explicit_successor(self) -> "AgenticPlanDeltaV1_2":
        all_actions: tuple[_PlanDeltaAction, ...] = (
            self.add_actions
            + self.modify_actions
            + self.defer_actions
            + self.cancel_actions
        )
        if not all_actions and (
            self.baseline_source_plan_before == self.baseline_source_plan_after
        ):
            raise ValueError("plan_delta_has_no_change")
        _unique(
            tuple(action.action_id for action in all_actions),
            "plan_delta_action_id_duplicate",
        )
        targeted = tuple(
            action.target_task_id
            for action in self.modify_actions + self.defer_actions + self.cancel_actions
        )
        _unique(targeted, "plan_delta_task_targeted_more_than_once")

        if self.base_plan.plan_id != self.successor_plan.plan_id:
            raise ValueError("plan_delta_plan_identity_changed")
        if self.successor_plan.revision != self.base_plan.revision + 1:
            raise ValueError("plan_delta_successor_revision_invalid")
        if self.successor_plan.prior_plan_digest != self.base_plan.plan_digest:
            raise ValueError("plan_delta_successor_prior_digest_mismatch")
        if self.accepted_plan_digest != self.successor_plan.plan_digest:
            raise ValueError("plan_delta_accepted_plan_digest_mismatch")
        if self.resulting_graph_digest != research_plan_graph_digest(self.successor_plan):
            raise ValueError("plan_delta_resulting_graph_digest_mismatch")
        if self.catalog_digest != self.successor_plan.catalog_digest:
            raise ValueError("plan_delta_catalog_digest_mismatch")
        if self.policy_digest != self.successor_plan.policy_digest:
            raise ValueError("plan_delta_policy_digest_mismatch")
        if self.authority_matrix_digest != self.successor_plan.authority_matrix_digest:
            raise ValueError("plan_delta_authority_matrix_digest_mismatch")
        if self.budget_basis_digest != self.successor_plan.budget_basis_digest:
            raise ValueError("plan_delta_budget_basis_digest_mismatch")

        expected_before = _coverage_snapshot_tuple(self.base_plan)
        expected_after = _coverage_snapshot_tuple(self.successor_plan)
        if self.coverage_before != expected_before or self.coverage_after != expected_after:
            raise ValueError("plan_delta_top_level_coverage_snapshot_mismatch")
        before_map = {item.obligation_id: item for item in expected_before}
        after_map = {item.obligation_id: item for item in expected_after}
        if set(before_map) != set(after_map):
            raise ValueError("plan_delta_coverage_obligation_identity_changed")
        for action in all_actions:
            for item in action.coverage_before:
                if before_map.get(item.obligation_id) != item:
                    raise ValueError("plan_delta_action_coverage_before_stale")
            for item in action.coverage_after:
                if after_map.get(item.obligation_id) != item:
                    raise ValueError("plan_delta_action_coverage_after_stale")

        base_tasks = {task.task_id: task for task in self.base_plan.tasks}
        successor_tasks = {task.task_id: task for task in self.successor_plan.tasks}
        action_successors: dict[str, ResearchTaskSpec] = {}
        for action in self.add_actions:
            task = action.successor_task
            if task.task_id in base_tasks:
                raise ValueError("plan_delta_add_task_already_exists")
            action_successors[task.task_id] = task
        for action in self.modify_actions + self.defer_actions + self.cancel_actions:
            if action.target_task_id not in base_tasks:
                raise ValueError("plan_delta_target_task_unknown")
            action_successors[action.target_task_id] = action.successor_task
        for action in self.modify_actions:
            base_task = base_tasks[action.target_task_id]
            actual_changes = {
                field_name
                for field_name in ResearchTaskSpec.model_fields
                if getattr(base_task, field_name) != getattr(action.successor_task, field_name)
            }
            if actual_changes != set(action.changed_fields):
                raise ValueError("plan_delta_modify_changed_fields_mismatch")
        for action in self.defer_actions + self.cancel_actions:
            base_task = base_tasks[action.target_task_id]
            actual_changes = {
                field_name
                for field_name in ResearchTaskSpec.model_fields
                if getattr(base_task, field_name) != getattr(action.successor_task, field_name)
            }
            if actual_changes != {"status"}:
                raise ValueError("plan_delta_terminal_action_mutates_task_contract")
        if set(successor_tasks) != set(base_tasks) | {
            action.successor_task.task_id for action in self.add_actions
        }:
            raise ValueError("plan_delta_successor_task_identity_set_invalid")
        for task_id, successor in successor_tasks.items():
            expected = action_successors.get(task_id, base_tasks.get(task_id))
            if successor != expected:
                raise ValueError("plan_delta_unreceipted_successor_task_change")

        if self.baseline_source_plan_before.source_plan_digest != (
            self.base_plan.baseline_source_plan_digest
        ):
            raise ValueError("plan_delta_base_source_plan_digest_mismatch")
        if self.baseline_source_plan_after.source_plan_digest != (
            self.successor_plan.baseline_source_plan_digest
        ):
            raise ValueError("plan_delta_successor_source_plan_digest_mismatch")
        if (
            self.base_plan.case_id != self.baseline_source_plan_before.case_id
            or self.successor_plan.case_id != self.baseline_source_plan_after.case_id
            or self.base_plan.catalog_digest
            != self.baseline_source_plan_before.catalog_digest
            or self.successor_plan.catalog_digest
            != self.baseline_source_plan_after.catalog_digest
            or self.base_plan.policy_digest
            != self.baseline_source_plan_before.policy_digest
            or self.successor_plan.policy_digest
            != self.baseline_source_plan_after.policy_digest
        ):
            raise ValueError("plan_delta_plan_source_boundary_mismatch")
        source_plan_identity_before = (
            self.baseline_source_plan_before.case_id,
            self.baseline_source_plan_before.case_version,
            self.baseline_source_plan_before.research_as_of,
            self.baseline_source_plan_before.inventory_snapshot_digest,
            self.baseline_source_plan_before.catalog_digest,
            self.baseline_source_plan_before.policy_digest,
        )
        source_plan_identity_after = (
            self.baseline_source_plan_after.case_id,
            self.baseline_source_plan_after.case_version,
            self.baseline_source_plan_after.research_as_of,
            self.baseline_source_plan_after.inventory_snapshot_digest,
            self.baseline_source_plan_after.catalog_digest,
            self.baseline_source_plan_after.policy_digest,
        )
        if source_plan_identity_before != source_plan_identity_after:
            raise ValueError("plan_delta_source_plan_boundary_changed")
        before_routes = {
            route.route_obligation_id: route
            for route in self.baseline_source_plan_before.route_obligations
        }
        after_routes = {
            route.route_obligation_id: route
            for route in self.baseline_source_plan_after.route_obligations
        }
        replacement_map = {
            item.removed_route_obligation_id: item for item in self.route_replacements
        }
        _unique(tuple(replacement_map), "plan_delta_route_replacement_duplicate")
        removed_required_route_ids = {
            route_id
            for route_id, route in before_routes.items()
            if route.requirement == "required" and route_id not in after_routes
        }
        if set(replacement_map) != removed_required_route_ids:
            if removed_required_route_ids - set(replacement_map):
                raise ValueError("required_minimum_route_silently_removed")
            raise ValueError("plan_delta_route_replacement_set_mismatch")
        for route_id, route in before_routes.items():
            if route.requirement != "required":
                continue
            if route_id in after_routes:
                if after_routes[route_id] != route:
                    raise ValueError("required_minimum_route_in_place_mutation")
                continue
            replacement = replacement_map.get(route_id)
            if replacement is None:
                raise ValueError("required_minimum_route_silently_removed")
            if route.substitution_policy != "qualified_replacement":
                raise ValueError("non_substitutable_required_route_removed")
            successors = [after_routes.get(item) for item in replacement.successor_route_obligation_ids]
            if any(item is None for item in successors):
                raise ValueError("minimum_route_replacement_unknown")
            if any(
                item.coverage_obligation_id != route.coverage_obligation_id
                or item.route_kind not in route.acceptable_replacement_route_kinds
                for item in successors
                if item is not None
            ):
                raise ValueError("minimum_route_replacement_not_equivalent")

        _verify_digest(self, "delta_digest", "agentic_plan_delta_digest_mismatch")
        return self


class TokenBudgetBasis(_StrictFrozenModel):
    node_purpose: str = Field(min_length=8, max_length=2_000)
    input_scale: str = Field(min_length=3, max_length=1_000)
    required_outputs: tuple[str, ...] = Field(min_length=1, max_length=32)
    schema_burden: str = Field(min_length=3, max_length=1_000)
    materiality_quality_risk: str = Field(min_length=3, max_length=2_000)
    comparable_run_evidence_refs: tuple[str, ...] = Field(default=(), max_length=32)
    reasoning_profile: str = Field(min_length=2, max_length=240)
    stop_behavior: str = Field(min_length=8, max_length=2_000)
    truncation_behavior: str = Field(min_length=8, max_length=2_000)
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    max_action_attempts: int = Field(ge=1)
    basis_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_budget_basis(self) -> "TokenBudgetBasis":
        _unique(self.required_outputs, "token_budget_required_output_duplicate")
        _unique(
            self.comparable_run_evidence_refs,
            "token_budget_comparable_run_ref_duplicate",
        )
        _verify_digest(self, "basis_digest", "token_budget_basis_digest_mismatch")
        return self


class ModelNodeAuthorityEntry(_StrictFrozenModel):
    node_id: str = Field(pattern=_REF_PATTERN)
    node_kind: NodeKind
    status: Literal["not_authorized", "authorized"] = "not_authorized"
    node_purpose: str = Field(min_length=8, max_length=2_000)
    input_scale: str = Field(min_length=3, max_length=1_000)
    required_outputs: tuple[str, ...] = Field(min_length=1, max_length=32)
    schema_burden: str = Field(min_length=3, max_length=1_000)
    materiality_quality_risk: str = Field(min_length=3, max_length=2_000)
    comparable_run_evidence_refs: tuple[str, ...] = Field(default=(), max_length=32)
    reasoning_profile: str = Field(min_length=2, max_length=240)
    stop_and_truncation_behavior: str = Field(min_length=8, max_length=2_000)
    repair_policy: str = Field(min_length=8, max_length=2_000)
    retry_policy: str = Field(min_length=8, max_length=2_000)
    token_budget_basis: TokenBudgetBasis | None = None
    provider_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    model_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    paid_execution_owner_decision_ref: str | None = Field(
        default=None, pattern=_REF_PATTERN
    )

    @model_validator(mode="after")
    def validate_authority_status(self) -> "ModelNodeAuthorityEntry":
        _unique(self.required_outputs, "model_node_required_output_duplicate")
        _unique(
            self.comparable_run_evidence_refs,
            "model_node_comparable_run_ref_duplicate",
        )
        authority_fields = (
            self.token_budget_basis,
            self.provider_ref,
            self.model_ref,
            self.paid_execution_owner_decision_ref,
        )
        if self.status == "not_authorized" and any(
            value is not None for value in authority_fields
        ):
            raise ValueError("not_authorized_node_has_paid_transport_binding")
        if self.status == "authorized" and any(
            value is None for value in authority_fields
        ):
            raise ValueError("authorized_node_authority_contract_incomplete")
        return self


class ModelNodeAuthorityMatrix(_StrictFrozenModel):
    contract_version: Literal["1.2"] = "1.2"
    matrix_id: str = Field(pattern=_REF_PATTERN)
    policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    entries: tuple[ModelNodeAuthorityEntry, ...] = Field(min_length=6, max_length=64)
    authority_source: Literal["owner_decision_only"] = "owner_decision_only"
    hitl_may_grant_or_elevate_paid_authority: Literal[False] = False
    matrix_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_matrix(self) -> "ModelNodeAuthorityMatrix":
        _unique(tuple(item.node_id for item in self.entries), "authority_node_id_duplicate")
        present = {item.node_kind for item in self.entries}
        required = {
            "lead",
            "specialist",
            "counter",
            "semantic_research_verifier",
            "writer",
            "final_semantic_verifier",
        }
        if not required.issubset(present):
            raise ValueError("authority_matrix_required_node_kind_missing")
        _verify_digest(self, "matrix_digest", "authority_matrix_digest_mismatch")
        return self


class RuntimePolicySnapshot(_StrictFrozenModel):
    """Host-owned policy.  Ordinary HITL cannot turn this into paid authority."""

    contract_version: Literal["1.2"] = "1.2"
    policy_snapshot_id: str = Field(pattern=_REF_PATTERN)
    case_id: str = Field(pattern=_REF_PATTERN)
    case_version: str = Field(min_length=1, max_length=80)
    research_as_of: str = Field(min_length=10, max_length=10)
    data_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    catalog_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    disclosure_policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    allowed_branch_refs: tuple[str, ...] = Field(min_length=1, max_length=64)
    allowed_authority_class_refs: tuple[str, ...] = Field(min_length=1, max_length=64)
    paid_execution_authority_status: Literal["not_authorized"] = "not_authorized"
    paid_execution_owner_decision_ref: None = None
    hitl_may_grant_or_elevate_paid_authority: Literal[False] = False
    evidence_promotion_policy: Literal["qualified_reviewer_only"] = (
        "qualified_reviewer_only"
    )
    s2_write_policy: Literal["not_authorized"] = "not_authorized"
    public_gap_policy: Literal["gap_eligibility_receipt_required"] = (
        "gap_eligibility_receipt_required"
    )
    policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_policy_snapshot(self) -> "RuntimePolicySnapshot":
        _parse_iso_date(self.research_as_of, "runtime_policy_research_as_of_invalid")
        _unique(self.allowed_branch_refs, "runtime_policy_branch_ref_duplicate")
        _unique(
            self.allowed_authority_class_refs,
            "runtime_policy_authority_class_ref_duplicate",
        )
        _verify_digest(self, "policy_digest", "runtime_policy_digest_mismatch")
        return self


class RuntimeScope(_StrictFrozenModel):
    """Sealed host scope.  This model must never be exposed as a provider schema."""

    contract_version: Literal["1.2"] = "1.2"
    sealed: Literal[True] = True
    provider_visible: Literal[False] = False
    case_id: str = Field(pattern=_REF_PATTERN)
    session_id: str = Field(pattern=_REF_PATTERN)
    research_run_id: str = Field(pattern=_REF_PATTERN)
    run_invocation_id: str = Field(pattern=_REF_PATTERN)
    action_attempt_id: str = Field(pattern=_REF_PATTERN)
    agent_id: str = Field(pattern=_REF_PATTERN)
    agent_role: str = Field(min_length=1, max_length=120)
    task_id: str = Field(pattern=_REF_PATTERN)
    task_kind: str = Field(min_length=1, max_length=120)
    case_version: str = Field(min_length=1, max_length=80)
    research_as_of: str = Field(min_length=10, max_length=10)
    data_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    disclosure_policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    authority_matrix_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    model_context_state_digest: Digest | None = Field(
        default=None,
        pattern=_DIGEST_PATTERN,
    )
    branch_scope_refs: tuple[str, ...] = Field(min_length=1, max_length=64)
    permission_refs: tuple[str, ...] = Field(default=(), max_length=64)
    canonical_issuer_selectors: tuple[str, ...] = Field(min_length=1, max_length=16)
    physical_source_role_selectors: tuple[str, ...] = Field(default=(), max_length=32)
    physical_route_selectors: tuple[str, ...] = Field(default=(), max_length=64)
    physical_lane_selectors: tuple[str, ...] = Field(default=(), max_length=16)
    method_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    skill_digests: tuple[Digest, ...] = Field(default=(), max_length=32)
    may_promote_evidence: bool = False
    may_write_s2: bool = False
    may_assert_public_gap_without_receipt: Literal[False] = False
    paid_model_transport_authorized: Literal[False] = False
    idempotency_key: str = Field(min_length=16, max_length=240)
    timeout_ms: int = Field(ge=1, le=3_600_000)
    rate_and_cost_boundary_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    scope_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_sealed_scope(self) -> "RuntimeScope":
        _parse_iso_date(self.research_as_of, "runtime_scope_research_as_of_invalid")
        for name in (
            "branch_scope_refs",
            "permission_refs",
            "canonical_issuer_selectors",
            "physical_source_role_selectors",
            "physical_route_selectors",
            "physical_lane_selectors",
            "skill_digests",
        ):
            _unique(tuple(getattr(self, name)), f"runtime_scope_{name}_duplicate")
        _verify_digest(self, "scope_digest", "runtime_scope_digest_mismatch")
        return self


class RuntimeScopeAuthorizationRecord(_StrictFrozenModel):
    """Host-store projection proving who owns one sealed RuntimeScope."""

    contract_version: Literal["1.2"] = "1.2"
    authorization_record_id: str = Field(pattern=_REF_PATTERN)
    runtime_scope_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    session_id: str = Field(pattern=_REF_PATTERN)
    research_run_id: str = Field(pattern=_REF_PATTERN)
    run_invocation_id: str = Field(pattern=_REF_PATTERN)
    action_attempt_id: str = Field(pattern=_REF_PATTERN)
    action_attempt_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    agent_id: str = Field(pattern=_REF_PATTERN)
    agent_role: str = Field(min_length=1, max_length=120)
    task_id: str = Field(pattern=_REF_PATTERN)
    task_kind: str = Field(min_length=1, max_length=120)
    accepted_plan_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    research_graph_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    objective_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    task_assignment_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    disclosure_policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    authority_matrix_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    canonical_event_ledger_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    authority_store_revision: int = Field(ge=1)
    issued_by: Literal["host_runtime_authority_resolver"] = (
        "host_runtime_authority_resolver"
    )
    authorization_record_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_authorization_record(self) -> "RuntimeScopeAuthorizationRecord":
        if self.task_assignment_digest != task_assignment_authority_digest(
            agent_id=self.agent_id,
            agent_role=self.agent_role,
            task_id=self.task_id,
            task_kind=self.task_kind,
            objective_digest=self.objective_digest,
            accepted_plan_digest=self.accepted_plan_digest,
            research_graph_digest=self.research_graph_digest,
        ):
            raise ValueError("runtime_scope_task_assignment_digest_mismatch")
        _verify_digest(
            self,
            "authorization_record_digest",
            "runtime_scope_authorization_record_digest_mismatch",
        )
        return self


def issue_runtime_scope_authorization_record(
    *,
    authorization_record_id: str,
    runtime_scope: RuntimeScope,
    action_attempt_digest: str,
    accepted_plan: ResearchPlan,
    canonical_event_ledger_snapshot_digest: str,
    authority_store_revision: int,
) -> RuntimeScopeAuthorizationRecord:
    """Issue current task authority from a validated accepted plan projection.

    The host adapter remains responsible for resolving the current plan and
    ledger snapshot.  This pure issuer prevents callers from choosing an
    unrelated objective or graph while retaining the same task identifier.
    """

    runtime_scope = RuntimeScope.model_validate(
        runtime_scope.model_dump(mode="python")
    )
    accepted_plan = ResearchPlan.model_validate(
        accepted_plan.model_dump(mode="python")
    )
    if accepted_plan.status != "accepted":
        raise ValueError("runtime_scope_authorization_plan_not_accepted")
    if accepted_plan.case_id != runtime_scope.case_id:
        raise ValueError("runtime_scope_authorization_plan_case_mismatch")
    if accepted_plan.policy_digest != runtime_scope.policy_digest:
        raise ValueError("runtime_scope_authorization_plan_policy_mismatch")
    if accepted_plan.authority_matrix_digest != runtime_scope.authority_matrix_digest:
        raise ValueError("runtime_scope_authorization_plan_authority_matrix_mismatch")
    matching_tasks = tuple(
        task for task in accepted_plan.tasks if task.task_id == runtime_scope.task_id
    )
    if len(matching_tasks) != 1:
        raise ValueError("runtime_scope_authorization_task_not_unique_in_plan")
    task = matching_tasks[0]
    if task.status in {"deferred", "cancelled"}:
        raise ValueError("runtime_scope_authorization_task_not_active")
    if task.owner_role != runtime_scope.agent_role:
        raise ValueError("runtime_scope_authorization_task_owner_role_mismatch")
    if not set(task.required_authority_refs).issubset(
        set(runtime_scope.permission_refs)
    ):
        raise ValueError("runtime_scope_authorization_task_authority_missing")

    objective_digest = research_objective_digest(task.objective)
    graph_digest = research_plan_graph_digest(accepted_plan)
    assignment_digest = task_assignment_authority_digest(
        agent_id=runtime_scope.agent_id,
        agent_role=runtime_scope.agent_role,
        task_id=runtime_scope.task_id,
        task_kind=runtime_scope.task_kind,
        objective_digest=objective_digest,
        accepted_plan_digest=accepted_plan.plan_digest,
        research_graph_digest=graph_digest,
    )
    body: dict[str, Any] = {
        "contract_version": "1.2",
        "authorization_record_id": authorization_record_id,
        "runtime_scope_digest": runtime_scope.scope_digest,
        "session_id": runtime_scope.session_id,
        "research_run_id": runtime_scope.research_run_id,
        "run_invocation_id": runtime_scope.run_invocation_id,
        "action_attempt_id": runtime_scope.action_attempt_id,
        "action_attempt_digest": action_attempt_digest,
        "agent_id": runtime_scope.agent_id,
        "agent_role": runtime_scope.agent_role,
        "task_id": runtime_scope.task_id,
        "task_kind": runtime_scope.task_kind,
        "accepted_plan_digest": accepted_plan.plan_digest,
        "research_graph_digest": graph_digest,
        "objective_digest": objective_digest,
        "task_assignment_digest": assignment_digest,
        "policy_digest": runtime_scope.policy_digest,
        "disclosure_policy_digest": runtime_scope.disclosure_policy_digest,
        "authority_matrix_digest": runtime_scope.authority_matrix_digest,
        "canonical_event_ledger_snapshot_digest": (
            canonical_event_ledger_snapshot_digest
        ),
        "authority_store_revision": authority_store_revision,
        "issued_by": "host_runtime_authority_resolver",
    }
    return RuntimeScopeAuthorizationRecord(
        **body,
        authorization_record_digest=canonical_digest(body),
    )


def validate_runtime_scope_authorization(
    *,
    runtime_scope: RuntimeScope,
    authorization_record: RuntimeScopeAuthorizationRecord,
) -> RuntimeScopeAuthorizationRecord:
    runtime_scope = RuntimeScope.model_validate(
        runtime_scope.model_dump(mode="python")
    )
    authorization_record = RuntimeScopeAuthorizationRecord.model_validate(
        authorization_record.model_dump(mode="python")
    )
    _verify_digest(runtime_scope, "scope_digest", "runtime_scope_digest_mismatch")
    _verify_digest(
        authorization_record,
        "authorization_record_digest",
        "runtime_scope_authorization_record_digest_mismatch",
    )
    exact = (
        (authorization_record.runtime_scope_digest, runtime_scope.scope_digest),
        (authorization_record.session_id, runtime_scope.session_id),
        (authorization_record.research_run_id, runtime_scope.research_run_id),
        (authorization_record.run_invocation_id, runtime_scope.run_invocation_id),
        (authorization_record.action_attempt_id, runtime_scope.action_attempt_id),
        (authorization_record.agent_id, runtime_scope.agent_id),
        (authorization_record.agent_role, runtime_scope.agent_role),
        (authorization_record.task_id, runtime_scope.task_id),
        (authorization_record.task_kind, runtime_scope.task_kind),
        (authorization_record.policy_digest, runtime_scope.policy_digest),
        (
            authorization_record.disclosure_policy_digest,
            runtime_scope.disclosure_policy_digest,
        ),
        (
            authorization_record.authority_matrix_digest,
            runtime_scope.authority_matrix_digest,
        ),
    )
    if any(actual != expected for actual, expected in exact):
        raise ValueError("runtime_scope_authorization_record_scope_mismatch")
    return authorization_record


class ZeroModelRuntimeBoundaryReceipt(_StrictFrozenModel):
    """Host receipt proving that Wave 0A cannot reach model transport."""

    contract_version: Literal["1.2"] = "1.2"
    profile: Literal["wave0a_zero_model"] = "wave0a_zero_model"
    policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    disclosure_policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    authority_matrix_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    runtime_scope_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    runtime_scope_authorization_record_digest: Digest = Field(
        pattern=_DIGEST_PATTERN
    )
    all_model_nodes_not_authorized: Literal[True] = True
    paid_transport_authorized: Literal[False] = False
    boundary_receipt_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_boundary_receipt(self) -> "ZeroModelRuntimeBoundaryReceipt":
        _verify_digest(
            self,
            "boundary_receipt_digest",
            "zero_model_boundary_receipt_digest_mismatch",
        )
        return self


def validate_zero_model_runtime_boundary(
    *,
    policy: RuntimePolicySnapshot,
    authority_matrix: ModelNodeAuthorityMatrix,
    runtime_scope: RuntimeScope,
    scope_authorization: RuntimeScopeAuthorizationRecord,
) -> ZeroModelRuntimeBoundaryReceipt:
    """Fail closed before any transport in the Wave 0A zero-model profile."""

    policy = RuntimePolicySnapshot.model_validate(
        policy.model_dump(mode="python")
    )
    authority_matrix = ModelNodeAuthorityMatrix.model_validate(
        authority_matrix.model_dump(mode="python")
    )
    runtime_scope = RuntimeScope.model_validate(
        runtime_scope.model_dump(mode="python")
    )
    scope_authorization = validate_runtime_scope_authorization(
        runtime_scope=runtime_scope,
        authorization_record=scope_authorization,
    )
    if authority_matrix.policy_digest != policy.policy_digest:
        raise ValueError("zero_model_authority_matrix_policy_mismatch")
    if runtime_scope.policy_digest != policy.policy_digest:
        raise ValueError("zero_model_runtime_scope_policy_mismatch")
    if runtime_scope.disclosure_policy_digest != policy.disclosure_policy_digest:
        raise ValueError("zero_model_runtime_scope_disclosure_policy_mismatch")
    if runtime_scope.authority_matrix_digest != authority_matrix.matrix_digest:
        raise ValueError("zero_model_runtime_scope_authority_matrix_mismatch")
    if (
        runtime_scope.case_id != policy.case_id
        or runtime_scope.case_version != policy.case_version
        or runtime_scope.research_as_of != policy.research_as_of
        or runtime_scope.data_snapshot_digest != policy.data_snapshot_digest
    ):
        raise ValueError("zero_model_runtime_scope_identity_or_snapshot_mismatch")
    if not set(runtime_scope.branch_scope_refs).issubset(policy.allowed_branch_refs):
        raise ValueError("zero_model_runtime_scope_branch_not_allowed")
    if not set(runtime_scope.permission_refs).issubset(
        policy.allowed_authority_class_refs
    ):
        raise ValueError("zero_model_runtime_scope_permission_not_allowed")
    if policy.paid_execution_authority_status != "not_authorized":
        raise ValueError("zero_model_paid_execution_policy_invalid")
    if any(entry.status != "not_authorized" for entry in authority_matrix.entries):
        raise ValueError("zero_model_authorized_model_node_forbidden")
    if runtime_scope.paid_model_transport_authorized is not False:
        raise ValueError("zero_model_paid_transport_forbidden")
    if runtime_scope.may_promote_evidence:
        raise ValueError("zero_model_evidence_promotion_authority_forbidden")
    if runtime_scope.may_write_s2:
        raise ValueError("zero_model_s2_write_authority_forbidden")
    body = {
        "contract_version": "1.2",
        "profile": "wave0a_zero_model",
        "policy_digest": policy.policy_digest,
        "disclosure_policy_digest": policy.disclosure_policy_digest,
        "authority_matrix_digest": authority_matrix.matrix_digest,
        "runtime_scope_digest": runtime_scope.scope_digest,
        "runtime_scope_authorization_record_digest": (
            scope_authorization.authorization_record_digest
        ),
        "all_model_nodes_not_authorized": True,
        "paid_transport_authorized": False,
    }
    return ZeroModelRuntimeBoundaryReceipt(
        **body,
        boundary_receipt_digest=canonical_digest(body),
    )


ZeroModelTransportBlockReason = Literal[
    "authority_material_missing",
    "authority_material_stale_or_invalid",
    "phantom_paid_authority",
    "wave0a_zero_model",
]


class ZeroModelTransportAuditEvent(_StrictFrozenModel):
    """Durable proof that the Wave 0A gateway stopped before provider setup."""

    contract_version: Literal["1.2"] = "1.2"
    audit_event_id: str = Field(pattern=_REF_PATTERN)
    action_attempt_id: str = Field(pattern=_REF_PATTERN)
    gateway_profile: Literal["wave0a_zero_model_transport"] = (
        "wave0a_zero_model_transport"
    )
    emitted_by: Literal["wave0a_zero_model_transport_gateway"] = (
        "wave0a_zero_model_transport_gateway"
    )
    block_reason: ZeroModelTransportBlockReason
    policy_digest: Digest | None = Field(default=None, pattern=_DIGEST_PATTERN)
    authority_matrix_digest: Digest | None = Field(
        default=None, pattern=_DIGEST_PATTERN
    )
    runtime_scope_digest: Digest | None = Field(default=None, pattern=_DIGEST_PATTERN)
    runtime_scope_authorization_record_digest: Digest | None = Field(
        default=None, pattern=_DIGEST_PATTERN
    )
    boundary_receipt_digest: Digest | None = Field(
        default=None, pattern=_DIGEST_PATTERN
    )
    client_construction_count: Literal[0] = 0
    structured_output_bind_count: Literal[0] = 0
    invoke_count: Literal[0] = 0
    provider_call_attempted: Literal[False] = False
    audit_event_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_zero_model_transport_event(self) -> "ZeroModelTransportAuditEvent":
        authority_digests = (
            self.policy_digest,
            self.authority_matrix_digest,
            self.runtime_scope_digest,
            self.runtime_scope_authorization_record_digest,
            self.boundary_receipt_digest,
        )
        has_missing_authority = any(item is None for item in authority_digests)
        if (self.block_reason == "authority_material_missing") != has_missing_authority:
            raise ValueError("zero_model_transport_block_reason_digest_mismatch")
        _verify_digest(
            self,
            "audit_event_digest",
            "zero_model_transport_audit_event_digest_mismatch",
        )
        return self


class ZeroModelTransportAuditPort(Protocol):
    """The only durable Wave 0A transport-audit writer surface."""

    def append_zero_model_transport_audit_event(
        self,
        event: ZeroModelTransportAuditEvent,
    ) -> None: ...


def _write_zero_model_transport_audit_event(
    *,
    audit_port: ZeroModelTransportAuditPort,
    event: ZeroModelTransportAuditEvent,
) -> None:
    if isinstance(audit_port, Mapping):
        raise TypeError("zero_model_transport_typed_audit_port_required")
    append = getattr(audit_port, "append_zero_model_transport_audit_event", None)
    if not callable(append):
        raise TypeError("zero_model_transport_typed_audit_port_required")
    if not isinstance(event, ZeroModelTransportAuditEvent):
        raise TypeError("zero_model_transport_typed_audit_event_required")
    append(event)


def wave0a_zero_model_transport_gateway(
    *,
    audit_event_id: str,
    action_attempt_id: str,
    audit_port: ZeroModelTransportAuditPort,
    policy: RuntimePolicySnapshot | None,
    authority_matrix: ModelNodeAuthorityMatrix | None,
    runtime_scope: RuntimeScope | None,
    scope_authorization: RuntimeScopeAuthorizationRecord | None,
    boundary_receipt: ZeroModelRuntimeBoundaryReceipt | None,
) -> ZeroModelTransportAuditEvent:
    """Record a fail-closed Wave 0A transport decision without a client surface.

    Deliberately, this gateway has no client factory, structured-output binder, or
    invoke callback.  Missing, stale, phantom, and valid zero-model authority all
    therefore share the same structurally enforced zero-side-effect result.
    """

    if isinstance(audit_port, Mapping) or not callable(
        getattr(audit_port, "append_zero_model_transport_audit_event", None)
    ):
        raise TypeError("zero_model_transport_typed_audit_port_required")

    if (
        policy is None
        or authority_matrix is None
        or runtime_scope is None
        or scope_authorization is None
        or boundary_receipt is None
    ):
        block_reason: ZeroModelTransportBlockReason = "authority_material_missing"
    else:
        try:
            policy = RuntimePolicySnapshot.model_validate(
                policy.model_dump(mode="python")
            )
            authority_matrix = ModelNodeAuthorityMatrix.model_validate(
                authority_matrix.model_dump(mode="python")
            )
            runtime_scope = RuntimeScope.model_validate(
                runtime_scope.model_dump(mode="python")
            )
            scope_authorization = RuntimeScopeAuthorizationRecord.model_validate(
                scope_authorization.model_dump(mode="python")
            )
            boundary_receipt = ZeroModelRuntimeBoundaryReceipt.model_validate(
                boundary_receipt.model_dump(mode="python")
            )
        except (AttributeError, TypeError, ValueError):
            block_reason = "authority_material_stale_or_invalid"
        else:
            if action_attempt_id != runtime_scope.action_attempt_id:
                block_reason = "authority_material_stale_or_invalid"
            elif any(
                entry.status == "authorized" for entry in authority_matrix.entries
            ):
                block_reason = "phantom_paid_authority"
            else:
                try:
                    current_receipt = validate_zero_model_runtime_boundary(
                        policy=policy,
                        authority_matrix=authority_matrix,
                        runtime_scope=runtime_scope,
                        scope_authorization=scope_authorization,
                    )
                except ValueError:
                    block_reason = "authority_material_stale_or_invalid"
                else:
                    if (
                        current_receipt.boundary_receipt_digest
                        != boundary_receipt.boundary_receipt_digest
                    ):
                        block_reason = "authority_material_stale_or_invalid"
                    else:
                        block_reason = "wave0a_zero_model"

    body = {
        "contract_version": "1.2",
        "audit_event_id": audit_event_id,
        "action_attempt_id": action_attempt_id,
        "gateway_profile": "wave0a_zero_model_transport",
        "emitted_by": "wave0a_zero_model_transport_gateway",
        "block_reason": block_reason,
        "policy_digest": policy.policy_digest if policy is not None else None,
        "authority_matrix_digest": (
            authority_matrix.matrix_digest if authority_matrix is not None else None
        ),
        "runtime_scope_digest": (
            runtime_scope.scope_digest if runtime_scope is not None else None
        ),
        "runtime_scope_authorization_record_digest": (
            scope_authorization.authorization_record_digest
            if scope_authorization is not None
            else None
        ),
        "boundary_receipt_digest": (
            boundary_receipt.boundary_receipt_digest
            if boundary_receipt is not None
            else None
        ),
        "client_construction_count": 0,
        "structured_output_bind_count": 0,
        "invoke_count": 0,
        "provider_call_attempted": False,
    }
    event = ZeroModelTransportAuditEvent(
        **body,
        audit_event_digest=canonical_digest(body),
    )
    _write_zero_model_transport_audit_event(audit_port=audit_port, event=event)
    return event


class _ProviderIntent(_StrictFrozenModel):
    query: str = Field(min_length=3, max_length=4_000)
    purpose: str = Field(min_length=8, max_length=2_000)
    entity_refs: tuple[str, ...] = Field(default=(), max_length=16)
    period_intents: tuple[str, ...] = Field(default=(), max_length=16)
    expected_information_gain: str = Field(min_length=8, max_length=1_000)
    limit: int = Field(default=8, ge=1, le=32)

    @model_validator(mode="after")
    def validate_shared_intent(self) -> "_ProviderIntent":
        _unique(self.entity_refs, "provider_intent_entity_ref_duplicate")
        _unique(self.period_intents, "provider_intent_period_intent_duplicate")
        return self


class ReviewedEvidenceIntent(_ProviderIntent):
    """Semantic query for the Reviewed Evidence index; no local selectors."""

    intent_kind: Literal["reviewed_evidence"] = "reviewed_evidence"
    topic_refs: tuple[str, ...] = Field(min_length=1, max_length=32)
    evidence_role_refs: tuple[str, ...] = Field(default=(), max_length=16)
    minimum_authority_tier: Literal["reviewed", "primary", "any_reviewed"] = (
        "reviewed"
    )

    @model_validator(mode="after")
    def validate_reviewed_intent(self) -> "ReviewedEvidenceIntent":
        _unique(self.topic_refs, "reviewed_intent_topic_ref_duplicate")
        _unique(self.evidence_role_refs, "reviewed_intent_evidence_role_duplicate")
        return self


class LocalEvidenceIntent(_ProviderIntent):
    """Semantic local Candidate intent; runtime compiles all physical selectors."""

    intent_kind: Literal["local_evidence"] = "local_evidence"
    semantic_source_family_refs: tuple[str, ...] = Field(min_length=1, max_length=32)
    source_role_intents: tuple[str, ...] = Field(default=(), max_length=16)
    content_surface_intents: tuple[
        Literal["prose", "table", "image", "footnote"], ...
    ] = Field(default=("prose", "table"), max_length=4)

    @model_validator(mode="after")
    def validate_local_intent(self) -> "LocalEvidenceIntent":
        _unique(
            self.semantic_source_family_refs,
            "local_intent_source_family_duplicate",
        )
        _unique(self.source_role_intents, "local_intent_source_role_duplicate")
        _unique(self.content_surface_intents, "local_intent_surface_duplicate")
        return self


class ExternalSourceIntent(_ProviderIntent):
    """External discovery intent; local routes, lanes, and roles are impossible."""

    intent_kind: Literal["external_source"] = "external_source"
    semantic_source_family_refs: tuple[str, ...] = Field(min_length=1, max_length=32)
    domain_allowlist: tuple[str, ...] = Field(default=(), max_length=32)
    published_not_before: str | None = Field(default=None, min_length=10, max_length=10)
    published_not_after: str | None = Field(default=None, min_length=10, max_length=10)

    @model_validator(mode="after")
    def validate_external_intent(self) -> "ExternalSourceIntent":
        _unique(
            self.semantic_source_family_refs,
            "external_intent_source_family_duplicate",
        )
        _unique(self.domain_allowlist, "external_intent_domain_duplicate")
        start = (
            _parse_iso_date(self.published_not_before, "external_start_date_invalid")
            if self.published_not_before is not None
            else None
        )
        end = (
            _parse_iso_date(self.published_not_after, "external_end_date_invalid")
            if self.published_not_after is not None
            else None
        )
        if start is not None and end is not None and start > end:
            raise ValueError("external_date_range_invalid")
        return self


class AvailableNextAction(_StrictFrozenModel):
    action: NextActionKind
    reason: str = Field(min_length=4, max_length=1_000)
    target_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    capability_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    requires_human: bool = False
    expected_information_gain: Literal["none", "low", "medium", "high"] | None = None

    @model_validator(mode="after")
    def validate_action_shape(self) -> "AvailableNextAction":
        if self.action == "request_human_review" and not self.requires_human:
            raise ValueError("human_review_action_requires_human_flag")
        if self.requires_human and self.action not in {
            "request_human_review",
            "pause",
        }:
            raise ValueError("non_human_action_has_human_flag")
        if self.action in {"read_evidence", "request_gap_eligibility"} and (
            self.target_ref is None
        ):
            raise ValueError("next_action_target_ref_required")
        if self.action == "request_disclosure" and self.capability_ref is None:
            raise ValueError("disclosure_next_action_capability_ref_required")
        return self


class ToolFailureReceipt(_StrictFrozenModel):
    contract_version: Literal["1.2"] = "1.2"
    failure_receipt_id: str = Field(pattern=_REF_PATTERN)
    action_attempt_id: str = Field(pattern=_REF_PATTERN)
    observed_outcome: Literal["tool_failure", "empty", "scope_exhausted"]
    failure_code: str = Field(pattern=_REF_PATTERN)
    category: Literal[
        "semantic_validation",
        "tool_transport",
        "protocol_integrity",
        "server_integrity",
        "data_integrity",
        "permission",
    ]
    owning_plane: Literal[
        "runtime_data_binding",
        "s1_data",
        "s2_data",
        "tool_adapter",
        "provider_transport",
        "runtime_control",
    ]
    owning_stage: str = Field(pattern=_REF_PATTERN)
    retryability: Literal[
        "not_retryable",
        "transport_retry_only",
        "correctable_with_new_information",
        "owner_repair_required",
    ]
    permitted_next_actions: tuple[AvailableNextAction, ...] = Field(
        min_length=1, max_length=16
    )
    forbidden_interpretations: tuple[
        Literal[
            "issuer_non_disclosure",
            "public_information_absent",
            "evidence_admitted",
            "research_complete",
        ],
        ...,
    ] = (
        "issuer_non_disclosure",
        "public_information_absent",
    )
    public_gap_eligible: Literal[False] = False
    diagnostic_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    receipt_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_failure_is_not_gap(self) -> "ToolFailureReceipt":
        actions = tuple(item.action for item in self.permitted_next_actions)
        _unique(actions, "tool_failure_next_action_duplicate")
        if "request_gap_eligibility" in actions:
            raise ValueError("tool_failure_cannot_directly_request_public_gap")
        _unique(
            self.forbidden_interpretations,
            "tool_failure_forbidden_interpretation_duplicate",
        )
        required = {"issuer_non_disclosure", "public_information_absent"}
        if not required.issubset(self.forbidden_interpretations):
            raise ValueError("tool_failure_gap_forbidden_interpretation_missing")
        _verify_digest(self, "receipt_digest", "tool_failure_receipt_digest_mismatch")
        return self


VerifiedArtifactKind = Literal[
    "evidence",
    "numeric_fact",
    "calculation",
    "counter_finding",
    "lead_disposition",
    "public_gap_authority",
    "human_acceptance",
    "evidence_need",
    "material_requirement_plan",
    "local_integrity",
    "source_family_compilation",
    "required_route_terminal",
    "candidate_disposition",
    "transport_alternative_disposition",
    "budget_stop_disposition",
    "owned_defect_snapshot",
    "reviewer_qualification",
    "independent_gap_review",
    "owned_defect",
    "route_replacement_disposition",
    "route_replacement_condition",
    "material_requirement_satisfaction",
    "coverage_transition_verifier",
    "route_discovery",
    "route_capture",
    "route_execution",
    "route_candidate_disposition",
]


class VerifiedArtifactRef(_StrictFrozenModel):
    """One host-resolved durable artifact, never a provider-authored claim."""

    artifact_ref: str = Field(pattern=_REF_PATTERN)
    artifact_kind: VerifiedArtifactKind
    case_id: str = Field(pattern=_REF_PATTERN)
    baseline_source_plan_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    catalog_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    coverage_obligation_ids: tuple[str, ...] = Field(default=(), max_length=64)
    task_ids: tuple[str, ...] = Field(default=(), max_length=256)
    route_obligation_ids: tuple[str, ...] = Field(default=(), max_length=256)
    material_proposition_refs: tuple[str, ...] = Field(default=(), max_length=64)
    bound_artifact_digests: tuple[Digest, ...] = Field(default=(), max_length=256)
    canonical_artifact_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    conflict_group_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    conflict_side: Literal["supports", "contradicts"] | None = None
    actor_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    producer_actor_refs: tuple[str, ...] = Field(default=(), max_length=64)
    independent_of_actor_refs: tuple[str, ...] = Field(default=(), max_length=64)
    reviewed_producer_actor_refs: tuple[str, ...] = Field(default=(), max_length=64)
    checked_owner_classes: tuple[
        Literal[
            "local_data",
            "retrieval",
            "transport",
            "evidence_admission",
            "permission_configuration",
        ],
        ...,
    ] = Field(default=(), max_length=5)
    open_owned_defect_refs: tuple[str, ...] = Field(default=(), max_length=64)
    outcome: Literal[
        "qualified",
        "qualified_not_applicable",
        "exhausted_no_qualifying_result",
        "verified_public_non_disclosure",
        "open",
        "closed",
    ]
    terminal: bool
    defect_status: Literal["not_applicable", "open", "closed"] = "not_applicable"
    authority_class_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    route_discovery_receipt_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    route_capture_receipt_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    route_execution_receipt_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    route_candidate_disposition_receipt_ref: str | None = Field(
        default=None, pattern=_REF_PATTERN
    )
    artifact_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_verified_artifact(self) -> "VerifiedArtifactRef":
        for name in (
            "coverage_obligation_ids",
            "task_ids",
            "route_obligation_ids",
            "material_proposition_refs",
            "bound_artifact_digests",
            "producer_actor_refs",
            "independent_of_actor_refs",
            "reviewed_producer_actor_refs",
            "checked_owner_classes",
            "open_owned_defect_refs",
        ):
            _unique(tuple(getattr(self, name)), f"verified_artifact_{name}_duplicate")
        if self.artifact_kind == "owned_defect":
            if self.defect_status == "not_applicable":
                raise ValueError("owned_defect_status_required")
        elif self.defect_status != "not_applicable":
            raise ValueError("non_defect_artifact_has_defect_status")
        if self.artifact_kind == "required_route_terminal" and self.outcome not in {
            "exhausted_no_qualifying_result",
            "verified_public_non_disclosure",
        }:
            raise ValueError("required_route_terminal_outcome_invalid")
        if self.artifact_kind == "owned_defect_snapshot":
            required_owner_classes = {
                "local_data", "retrieval", "transport",
                "evidence_admission", "permission_configuration",
            }
            if set(self.checked_owner_classes) != required_owner_classes:
                raise ValueError("owned_defect_snapshot_owner_scope_incomplete")
            if self.outcome != "qualified":
                raise ValueError("owned_defect_snapshot_outcome_invalid")
        elif self.checked_owner_classes or self.open_owned_defect_refs:
            raise ValueError("non_defect_snapshot_has_defect_snapshot_fields")
        if (self.conflict_group_ref is None) != (self.conflict_side is None):
            raise ValueError("verified_artifact_conflict_binding_incomplete")
        lifecycle_refs = (
            self.route_discovery_receipt_ref,
            self.route_capture_receipt_ref,
            self.route_execution_receipt_ref,
            self.route_candidate_disposition_receipt_ref,
        )
        if self.artifact_kind == "required_route_terminal":
            if any(ref is None for ref in lifecycle_refs):
                raise ValueError("required_route_terminal_lifecycle_proof_incomplete")
        elif any(ref is not None for ref in lifecycle_refs):
            raise ValueError("non_route_terminal_has_lifecycle_refs")
        if self.artifact_kind == "reviewer_qualification":
            if self.authority_class_ref != "authority:boundary-acceptance":
                raise ValueError("reviewer_boundary_authority_required")
        elif self.authority_class_ref is not None:
            raise ValueError("non_reviewer_qualification_has_authority_class")
        _verify_digest(self, "artifact_digest", "verified_artifact_digest_mismatch")
        return self


class VerifiedArtifactRegistrySnapshot(_StrictFrozenModel):
    """Immutable output of host storage resolvers for one Dell snapshot."""

    contract_version: Literal["1.2"] = "1.2"
    registry_id: str = Field(pattern=_REF_PATTERN)
    resolver_ref: str = Field(pattern=_REF_PATTERN)
    store_revision: int = Field(ge=1)
    canonical_tip_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    case_id: str = Field(pattern=_REF_PATTERN)
    baseline_source_plan_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    catalog_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    artifacts: tuple[VerifiedArtifactRef, ...] = Field(default=(), max_length=4096)
    issued_by: Literal["host_verified_artifact_registry_resolver"] = (
        "host_verified_artifact_registry_resolver"
    )
    registry_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_registry(self) -> "VerifiedArtifactRegistrySnapshot":
        refs = tuple(item.artifact_ref for item in self.artifacts)
        _unique(refs, "verified_artifact_registry_ref_duplicate")
        for item in self.artifacts:
            _verify_digest(
                item,
                "artifact_digest",
                "verified_artifact_registry_contains_stale_artifact",
            )
        if any(
            item.case_id != self.case_id
            or item.baseline_source_plan_digest != self.baseline_source_plan_digest
            or item.inventory_snapshot_digest != self.inventory_snapshot_digest
            or item.catalog_digest != self.catalog_digest
            or item.policy_digest != self.policy_digest
            for item in self.artifacts
        ):
            raise ValueError("verified_artifact_registry_boundary_mismatch")
        _verify_digest(self, "registry_digest", "verified_artifact_registry_digest_mismatch")
        return self

    def by_ref(self) -> dict[str, VerifiedArtifactRef]:
        return {item.artifact_ref: item for item in self.artifacts}


class VerifiedArtifactRegistryResolver(Protocol):
    """Host trust port for the one current artifact-registry snapshot."""

    resolver_ref: str

    def resolve_current_verified_artifact_registry(
        self,
        *,
        case_id: str,
    ) -> VerifiedArtifactRegistrySnapshot | None: ...


def _resolve_verified_refs(
    *,
    refs: Iterable[str],
    expected_kind: VerifiedArtifactKind,
    registry: VerifiedArtifactRegistrySnapshot,
    coverage_obligation_id: str | None = None,
    material_proposition_ref: str | None = None,
    require_terminal: bool = True,
) -> tuple[VerifiedArtifactRef, ...]:
    index = registry.by_ref()
    resolved: list[VerifiedArtifactRef] = []
    for ref in refs:
        item = index.get(ref)
        if item is None or item.artifact_kind != expected_kind:
            raise ValueError(f"verified_artifact_ref_missing_or_wrong_kind:{ref}")
        if require_terminal and not item.terminal:
            raise ValueError(f"verified_artifact_not_terminal:{ref}")
        if (
            coverage_obligation_id is not None
            and coverage_obligation_id not in item.coverage_obligation_ids
        ):
            raise ValueError(f"verified_artifact_coverage_mismatch:{ref}")
        if (
            material_proposition_ref is not None
            and material_proposition_ref not in item.material_proposition_refs
        ):
            raise ValueError(f"verified_artifact_proposition_mismatch:{ref}")
        resolved.append(item)
    return tuple(resolved)


def _validate_registry_boundary(
    *,
    baseline_source_plan: BaselineSourcePlan,
    registry: VerifiedArtifactRegistrySnapshot,
) -> None:
    _verify_digest(
        baseline_source_plan,
        "source_plan_digest",
        "baseline_source_plan_digest_mismatch",
    )
    _verify_digest(
        registry,
        "registry_digest",
        "verified_artifact_registry_digest_mismatch",
    )
    for item in registry.artifacts:
        _verify_digest(
            item,
            "artifact_digest",
            "verified_artifact_registry_contains_stale_artifact",
        )
    if (
        registry.case_id != baseline_source_plan.case_id
        or registry.baseline_source_plan_digest
        != baseline_source_plan.source_plan_digest
        or registry.inventory_snapshot_digest
        != baseline_source_plan.inventory_snapshot_digest
        or registry.catalog_digest != baseline_source_plan.catalog_digest
        or registry.policy_digest != baseline_source_plan.policy_digest
    ):
        raise ValueError("verified_artifact_registry_stale")


def _resolve_current_verified_artifact_registry(
    *,
    baseline_source_plan: BaselineSourcePlan,
    registry_resolver: VerifiedArtifactRegistryResolver | None,
) -> VerifiedArtifactRegistrySnapshot:
    baseline_source_plan = BaselineSourcePlan.model_validate(
        baseline_source_plan.model_dump(mode="python")
    )
    if registry_resolver is None:
        raise ValueError("verified_artifact_registry_resolver_required")
    if isinstance(registry_resolver, (Mapping, VerifiedArtifactRegistrySnapshot)):
        raise TypeError("verified_artifact_registry_resolver_required")
    resolve = getattr(
        registry_resolver,
        "resolve_current_verified_artifact_registry",
        None,
    )
    resolver_ref = getattr(registry_resolver, "resolver_ref", None)
    if not callable(resolve) or not isinstance(resolver_ref, str):
        raise TypeError("verified_artifact_registry_resolver_required")
    registry = resolve(case_id=baseline_source_plan.case_id)
    if registry is None:
        raise ValueError("verified_artifact_registry_absent_from_authoritative_store")
    if not isinstance(registry, VerifiedArtifactRegistrySnapshot):
        raise TypeError("verified_artifact_registry_snapshot_type_invalid")
    registry = VerifiedArtifactRegistrySnapshot.model_validate(
        registry.model_dump(mode="python")
    )
    if registry.resolver_ref != resolver_ref:
        raise ValueError("verified_artifact_registry_resolver_identity_mismatch")
    _validate_registry_boundary(
        baseline_source_plan=baseline_source_plan,
        registry=registry,
    )
    return registry


def validate_research_plan_reference_integrity(
    plan: ResearchPlan,
    *,
    baseline_source_plan: BaselineSourcePlan,
    registry_resolver: VerifiedArtifactRegistryResolver | None,
    zero_model: bool,
) -> ResearchPlan:
    """Resolve every proof ref; plan shape alone never proves coverage."""

    plan = ResearchPlan.model_validate(plan.model_dump(mode="python"))
    baseline_source_plan = BaselineSourcePlan.model_validate(
        baseline_source_plan.model_dump(mode="python")
    )
    if (
        plan.case_id != baseline_source_plan.case_id
        or plan.baseline_source_plan_digest != baseline_source_plan.source_plan_digest
        or plan.catalog_digest != baseline_source_plan.catalog_digest
        or plan.policy_digest != baseline_source_plan.policy_digest
    ):
        raise ValueError("research_plan_baseline_boundary_mismatch")
    if zero_model:
        for obligation in plan.coverage_obligations:
            if obligation.evidence_satisfaction != "uncovered" or any(
                (
                    obligation.evidence_refs,
                    obligation.numeric_fact_refs,
                    obligation.calculation_refs,
                    obligation.counter_finding_refs,
                    obligation.material_requirement_receipt_refs,
                    obligation.verifier_transition_receipt_refs,
                    obligation.lead_disposition_receipt_refs,
                    (obligation.gap_eligibility_receipt_ref,)
                    if obligation.gap_eligibility_receipt_ref is not None
                    else (),
                    (obligation.human_acceptance_receipt_ref,)
                    if obligation.human_acceptance_receipt_ref is not None
                    else (),
                )
            ):
                raise ValueError("zero_model_plan_claims_evidence")
        return plan
    registry = _resolve_current_verified_artifact_registry(
        baseline_source_plan=baseline_source_plan,
        registry_resolver=registry_resolver,
    )
    for obligation in plan.coverage_obligations:
        obligation_id = obligation.obligation_id
        resolved_support: list[VerifiedArtifactRef] = []
        for refs, kind in (
            (obligation.evidence_refs, "evidence"),
            (obligation.numeric_fact_refs, "numeric_fact"),
            (obligation.calculation_refs, "calculation"),
            (obligation.counter_finding_refs, "counter_finding"),
            (
                obligation.material_requirement_receipt_refs,
                "material_requirement_satisfaction",
            ),
            (
                obligation.verifier_transition_receipt_refs,
                "coverage_transition_verifier",
            ),
            (obligation.lead_disposition_receipt_refs, "lead_disposition"),
        ):
            resolved = _resolve_verified_refs(
                refs=refs,
                expected_kind=kind,
                registry=registry,
                coverage_obligation_id=obligation_id,
            )
            if any(item.outcome != "qualified" for item in resolved):
                raise ValueError("coverage_reference_outcome_not_qualified")
            if any(
                not set(item.task_ids).intersection(obligation.reachable_task_ids)
                for item in resolved
            ):
                raise ValueError("coverage_reference_unreachable_task")
            if kind in {
                "material_requirement_satisfaction",
                "coverage_transition_verifier",
                "lead_disposition",
            } and any(
                plan.plan_digest not in item.bound_artifact_digests
                for item in resolved
            ):
                raise ValueError(f"coverage_{kind}_plan_stale")
            if kind in {"evidence", "numeric_fact", "calculation"}:
                resolved_support.extend(resolved)
        if obligation.evidence_satisfaction == "disputed":
            canonical_supports = {
                item.canonical_artifact_digest for item in resolved_support
            }
            conflict_groups: dict[str, set[str]] = {}
            for item in resolved_support:
                if item.conflict_group_ref is not None and item.conflict_side is not None:
                    conflict_groups.setdefault(item.conflict_group_ref, set()).add(
                        item.conflict_side
                    )
            if len(canonical_supports) < 2:
                raise ValueError("coverage_disputed_support_alias_not_independent")
            if not any(sides == {"supports", "contradicts"} for sides in conflict_groups.values()):
                raise ValueError("coverage_disputed_conflict_binding_incomplete")
        if obligation.gap_eligibility_receipt_ref is not None:
            resolved_gap = _resolve_verified_refs(
                refs=(obligation.gap_eligibility_receipt_ref,),
                expected_kind="public_gap_authority",
                registry=registry,
                coverage_obligation_id=obligation_id,
            )
            if plan.plan_digest not in resolved_gap[0].bound_artifact_digests:
                raise ValueError("coverage_gap_authority_plan_stale")
            if resolved_gap[0].outcome != "qualified":
                raise ValueError("coverage_gap_authority_not_qualified")
        if obligation.human_acceptance_receipt_ref is not None:
            resolved_human = _resolve_verified_refs(
                refs=(obligation.human_acceptance_receipt_ref,),
                expected_kind="human_acceptance",
                registry=registry,
                coverage_obligation_id=obligation_id,
            )
            if plan.plan_digest not in resolved_human[0].bound_artifact_digests:
                raise ValueError("coverage_human_acceptance_plan_stale")
            if resolved_human[0].outcome != "qualified":
                raise ValueError("coverage_human_acceptance_not_qualified")
    return plan


def validate_agentic_plan_delta_reference_integrity(
    delta: AgenticPlanDeltaV1_2,
    *,
    registry_resolver: VerifiedArtifactRegistryResolver | None,
) -> AgenticPlanDeltaV1_2:
    """Resolve route replacement proofs against the current host registry."""

    delta = AgenticPlanDeltaV1_2.model_validate(
        delta.model_dump(mode="python")
    )
    baseline = delta.baseline_source_plan_after
    registry = _resolve_current_verified_artifact_registry(
        baseline_source_plan=baseline,
        registry_resolver=registry_resolver,
    )
    before = {
        item.route_obligation_id: item
        for item in delta.baseline_source_plan_before.route_obligations
    }
    after = {
        item.route_obligation_id: item
        for item in delta.baseline_source_plan_after.route_obligations
    }
    for replacement in delta.route_replacements:
        removed = before[replacement.removed_route_obligation_id]
        successors = [after[item] for item in replacement.successor_route_obligation_ids]
        bound_route_digests = {removed.route_digest} | {
            item.route_digest for item in successors
        }
        dispositions = _resolve_verified_refs(
            refs=replacement.disposition_receipt_refs,
            expected_kind="route_replacement_disposition",
            registry=registry,
            coverage_obligation_id=removed.coverage_obligation_id,
        )
        if not any(
            bound_route_digests.issubset(set(item.bound_artifact_digests))
            for item in dispositions
        ):
            raise ValueError("route_replacement_disposition_not_digest_bound")
        conditions = _resolve_verified_refs(
            refs=replacement.condition_proof_receipt_refs,
            expected_kind="route_replacement_condition",
            registry=registry,
            coverage_obligation_id=removed.coverage_obligation_id,
        )
        required_condition_digests = {
            canonical_digest(condition) for condition in removed.replacement_conditions
        }
        observed_condition_digests = {
            digest for item in conditions for digest in item.bound_artifact_digests
        }
        if not (
            bound_route_digests | required_condition_digests
        ).issubset(observed_condition_digests):
            raise ValueError("route_replacement_condition_proof_incomplete")
    return delta


class GapEligibilityRequest(_StrictFrozenModel):
    contract_version: Literal["1.2"] = "1.2"
    gap_request_id: str = Field(pattern=_REF_PATTERN)
    material_proposition_ref: str = Field(pattern=_REF_PATTERN)
    original_actor_ref: str = Field(pattern=_REF_PATTERN)
    evidence_need_refs: tuple[str, ...] = Field(min_length=1, max_length=64)
    material_requirement_plan_refs: tuple[str, ...] = Field(min_length=1, max_length=64)
    coverage_obligation_ids: tuple[str, ...] = Field(min_length=1, max_length=64)
    local_integrity_receipt_refs: tuple[str, ...] = Field(default=(), max_length=128)
    source_family_compilation_receipt_refs: tuple[str, ...] = Field(
        default=(), max_length=128
    )
    required_route_terminal_receipt_refs: tuple[str, ...] = Field(
        default=(), max_length=256
    )
    candidate_disposition_receipt_refs: tuple[str, ...] = Field(
        default=(), max_length=256
    )
    transport_and_alternative_disposition_refs: tuple[str, ...] = Field(
        default=(), max_length=128
    )
    budget_stop_disposition_refs: tuple[str, ...] = Field(default=(), max_length=64)
    owned_defect_snapshot_receipt_ref: str = Field(pattern=_REF_PATTERN)
    reviewer_qualification_receipt_ref: str = Field(pattern=_REF_PATTERN)
    independent_review_receipt_ref: str = Field(pattern=_REF_PATTERN)
    request_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_gap_request(self) -> "GapEligibilityRequest":
        tuple_fields = (
            "evidence_need_refs",
            "material_requirement_plan_refs",
            "coverage_obligation_ids",
            "local_integrity_receipt_refs",
            "source_family_compilation_receipt_refs",
            "required_route_terminal_receipt_refs",
            "candidate_disposition_receipt_refs",
            "transport_and_alternative_disposition_refs",
            "budget_stop_disposition_refs",
        )
        for name in tuple_fields:
            _unique(tuple(getattr(self, name)), f"gap_eligibility_{name}_duplicate")
        required_nonempty = (
            self.local_integrity_receipt_refs,
            self.source_family_compilation_receipt_refs,
            self.required_route_terminal_receipt_refs,
            self.candidate_disposition_receipt_refs,
            self.transport_and_alternative_disposition_refs,
            self.budget_stop_disposition_refs,
        )
        if any(not value for value in required_nonempty):
            raise ValueError("gap_request_required_proof_receipt_missing")
        _verify_digest(self, "request_digest", "gap_eligibility_request_digest_mismatch")
        return self


class GapEligibilityReceipt(_StrictFrozenModel):
    """Authority receipt emitted only by the host resolver below."""

    contract_version: Literal["1.2"] = "1.2"
    gap_receipt_id: str = Field(pattern=_REF_PATTERN)
    gap_request_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    case_id: str = Field(pattern=_REF_PATTERN)
    baseline_source_plan_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    inventory_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    catalog_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    verified_artifact_registry_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    proof_set_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    material_proposition_ref: str = Field(pattern=_REF_PATTERN)
    coverage_obligation_ids: tuple[str, ...] = Field(min_length=1, max_length=64)
    owned_defect_snapshot_receipt_ref: str = Field(pattern=_REF_PATTERN)
    reviewer_ref: str = Field(pattern=_REF_PATTERN)
    reviewer_qualification_receipt_ref: str = Field(pattern=_REF_PATTERN)
    independent_review_receipt_ref: str = Field(pattern=_REF_PATTERN)
    public_gap_eligible: Literal[True] = True
    receipt_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_gap_authority_receipt(self) -> "GapEligibilityReceipt":
        _unique(self.coverage_obligation_ids, "gap_receipt_coverage_duplicate")
        _verify_digest(self, "receipt_digest", "gap_eligibility_receipt_digest_mismatch")
        return self


def authorize_gap_eligibility(
    request: GapEligibilityRequest,
    *,
    baseline_source_plan: BaselineSourcePlan,
    registry_resolver: VerifiedArtifactRegistryResolver,
    policy: RuntimePolicySnapshot,
    gap_receipt_id: str,
) -> GapEligibilityReceipt:
    """Prove route exhaustion and reviewer independence before granting a gap."""

    request = GapEligibilityRequest.model_validate(
        request.model_dump(mode="python")
    )
    baseline_source_plan = BaselineSourcePlan.model_validate(
        baseline_source_plan.model_dump(mode="python")
    )
    policy = RuntimePolicySnapshot.model_validate(
        policy.model_dump(mode="python")
    )
    if (
        policy.case_id != baseline_source_plan.case_id
        or policy.case_version != baseline_source_plan.case_version
        or policy.research_as_of != baseline_source_plan.research_as_of
        or policy.data_snapshot_digest
        != baseline_source_plan.inventory_snapshot_digest
        or policy.catalog_digest != baseline_source_plan.catalog_digest
        or policy.policy_digest != baseline_source_plan.policy_digest
        or policy.public_gap_policy != "gap_eligibility_receipt_required"
    ):
        raise ValueError("gap_runtime_policy_baseline_mismatch")
    registry = _resolve_current_verified_artifact_registry(
        baseline_source_plan=baseline_source_plan,
        registry_resolver=registry_resolver,
    )
    coverage_ids = set(request.coverage_obligation_ids)
    if not coverage_ids.issubset(baseline_source_plan.coverage_obligation_ids):
        raise ValueError("gap_request_coverage_outside_baseline")

    non_review_proofs: list[VerifiedArtifactRef] = []
    for refs, kind in (
        (request.evidence_need_refs, "evidence_need"),
        (request.material_requirement_plan_refs, "material_requirement_plan"),
        (request.local_integrity_receipt_refs, "local_integrity"),
        (request.source_family_compilation_receipt_refs, "source_family_compilation"),
        (request.candidate_disposition_receipt_refs, "candidate_disposition"),
        (
            request.transport_and_alternative_disposition_refs,
            "transport_alternative_disposition",
        ),
        (request.budget_stop_disposition_refs, "budget_stop_disposition"),
    ):
        resolved = _resolve_verified_refs(
            refs=refs,
            expected_kind=kind,
            registry=registry,
            material_proposition_ref=request.material_proposition_ref,
        )
        if kind == "material_requirement_plan" and any(
            baseline_source_plan.source_plan_digest not in item.bound_artifact_digests
            for item in resolved
        ):
            raise ValueError("gap_material_requirement_not_baseline_bound")
        if any(item.outcome != "qualified" for item in resolved):
            raise ValueError(f"gap_proof_outcome_not_qualified:{kind}")
        covered = {
            obligation_id
            for item in resolved
            for obligation_id in item.coverage_obligation_ids
        }
        if not coverage_ids.issubset(covered):
            raise ValueError(f"gap_proof_coverage_incomplete:{kind}")
        non_review_proofs.extend(resolved)

    terminal_receipts = _resolve_verified_refs(
        refs=request.required_route_terminal_receipt_refs,
        expected_kind="required_route_terminal",
        registry=registry,
        material_proposition_ref=request.material_proposition_ref,
    )
    required_route_ids = {
        route.route_obligation_id
        for route in baseline_source_plan.route_obligations
        if route.requirement == "required"
        and route.coverage_obligation_id in coverage_ids
    }
    observed_route_ids = [
        route_id
        for receipt in terminal_receipts
        for route_id in receipt.route_obligation_ids
    ]
    if (
        set(observed_route_ids) != required_route_ids
        or len(observed_route_ids) != len(required_route_ids)
    ):
        raise ValueError("gap_required_route_terminal_coverage_mismatch")
    route_map = {
        route.route_obligation_id: route
        for route in baseline_source_plan.route_obligations
    }
    for terminal_receipt in terminal_receipts:
        for route_id in terminal_receipt.route_obligation_ids:
            route = route_map[route_id]
            if (
                route.coverage_obligation_id
                not in terminal_receipt.coverage_obligation_ids
                or route.route_digest
                not in terminal_receipt.bound_artifact_digests
            ):
                raise ValueError("gap_required_route_terminal_binding_mismatch")
            lifecycle_specs = (
                (terminal_receipt.route_discovery_receipt_ref, "route_discovery", False),
                (terminal_receipt.route_capture_receipt_ref, "route_capture", True),
                (terminal_receipt.route_execution_receipt_ref, "route_execution", False),
                (
                    terminal_receipt.route_candidate_disposition_receipt_ref,
                    "route_candidate_disposition",
                    True,
                ),
            )
            for lifecycle_ref, lifecycle_kind, may_be_not_applicable in lifecycle_specs:
                if lifecycle_ref is None:
                    raise ValueError("gap_route_lifecycle_reference_missing")
                lifecycle = _resolve_verified_refs(
                    refs=(lifecycle_ref,),
                    expected_kind=lifecycle_kind,
                    registry=registry,
                    coverage_obligation_id=route.coverage_obligation_id,
                    material_proposition_ref=request.material_proposition_ref,
                )[0]
                if route_id not in lifecycle.route_obligation_ids:
                    raise ValueError("gap_route_lifecycle_binding_mismatch")
                if route.route_digest not in lifecycle.bound_artifact_digests:
                    raise ValueError("gap_route_lifecycle_digest_binding_mismatch")
                allowed_outcomes = {"qualified"}
                if may_be_not_applicable and route.route_kind in {
                    "s2_numeric_fact",
                    "calculator",
                }:
                    allowed_outcomes.add("qualified_not_applicable")
                if lifecycle.outcome not in allowed_outcomes:
                    raise ValueError("gap_route_lifecycle_outcome_invalid")
                non_review_proofs.append(lifecycle)
    non_review_proofs.extend(terminal_receipts)
    if any(not item.producer_actor_refs for item in non_review_proofs):
        raise ValueError("public_gap_proof_producer_missing")

    open_owned_defects = [
        item.artifact_ref
        for item in registry.artifacts
        if item.artifact_kind == "owned_defect"
        and item.defect_status == "open"
        and (
            request.material_proposition_ref in item.material_proposition_refs
            or bool(coverage_ids.intersection(item.coverage_obligation_ids))
            or bool(required_route_ids.intersection(item.route_obligation_ids))
        )
    ]
    if open_owned_defects:
        raise ValueError("public_gap_has_unresolved_owned_defect")

    defect_snapshots = _resolve_verified_refs(
        refs=(request.owned_defect_snapshot_receipt_ref,),
        expected_kind="owned_defect_snapshot",
        registry=registry,
        material_proposition_ref=request.material_proposition_ref,
    )
    defect_snapshot = defect_snapshots[0]
    if (
        set(defect_snapshot.coverage_obligation_ids) != coverage_ids
        or set(defect_snapshot.route_obligation_ids) != required_route_ids
        or set(defect_snapshot.open_owned_defect_refs) != set(open_owned_defects)
        or open_owned_defects
    ):
        raise ValueError("public_gap_owned_defect_snapshot_not_clean_or_complete")
    non_review_proofs.append(defect_snapshot)

    proof_set_digest = canonical_digest(
        sorted(
            (item.artifact_ref, item.artifact_digest)
            for item in non_review_proofs
        )
    )
    qualifications = _resolve_verified_refs(
        refs=(request.reviewer_qualification_receipt_ref,),
        expected_kind="reviewer_qualification",
        registry=registry,
        material_proposition_ref=request.material_proposition_ref,
    )
    qualification = qualifications[0]
    reviews = _resolve_verified_refs(
        refs=(request.independent_review_receipt_ref,),
        expected_kind="independent_gap_review",
        registry=registry,
        material_proposition_ref=request.material_proposition_ref,
    )
    review = reviews[0]
    reviewer_ref = qualification.actor_ref
    producer_set = {
        request.original_actor_ref,
        *(
            producer
            for item in non_review_proofs
            for producer in item.producer_actor_refs
        ),
        *(
            item.actor_ref
            for item in non_review_proofs
            if item.actor_ref is not None
        ),
    }
    required_review_bindings = {
        request.request_digest,
        proof_set_digest,
        qualification.artifact_digest,
    }
    if (
        reviewer_ref is None
        or qualification.authority_class_ref != "authority:boundary-acceptance"
        or qualification.authority_class_ref
        not in policy.allowed_authority_class_refs
        or qualification.outcome != "qualified"
        or not qualification.producer_actor_refs
        or reviewer_ref in qualification.producer_actor_refs
        or review.actor_ref != reviewer_ref
        or review.outcome != "qualified"
        or set(review.producer_actor_refs) != {reviewer_ref}
        or reviewer_ref in producer_set
        or set(review.reviewed_producer_actor_refs) != producer_set
        or set(review.independent_of_actor_refs) != producer_set
        or not required_review_bindings.issubset(set(review.bound_artifact_digests))
    ):
        raise ValueError("public_gap_reviewer_not_independent_or_authorized")

    body = {
        "contract_version": "1.2",
        "gap_receipt_id": gap_receipt_id,
        "gap_request_digest": request.request_digest,
        "case_id": baseline_source_plan.case_id,
        "baseline_source_plan_digest": baseline_source_plan.source_plan_digest,
        "inventory_snapshot_digest": baseline_source_plan.inventory_snapshot_digest,
        "catalog_digest": baseline_source_plan.catalog_digest,
        "policy_digest": baseline_source_plan.policy_digest,
        "verified_artifact_registry_digest": registry.registry_digest,
        "proof_set_digest": proof_set_digest,
        "material_proposition_ref": request.material_proposition_ref,
        "coverage_obligation_ids": tuple(sorted(coverage_ids)),
        "owned_defect_snapshot_receipt_ref": request.owned_defect_snapshot_receipt_ref,
        "reviewer_ref": reviewer_ref,
        "reviewer_qualification_receipt_ref": request.reviewer_qualification_receipt_ref,
        "independent_review_receipt_ref": request.independent_review_receipt_ref,
        "public_gap_eligible": True,
    }
    return GapEligibilityReceipt(
        **body,
        receipt_digest=canonical_digest(body),
    )


class RejectedAlternative(_StrictFrozenModel):
    action: str = Field(min_length=1, max_length=240)
    reason_code: str = Field(pattern=_REF_PATTERN)
    supporting_ref_ids: tuple[str, ...] = Field(default=(), max_length=64)

    @model_validator(mode="after")
    def validate_alternative_refs(self) -> "RejectedAlternative":
        _unique(self.supporting_ref_ids, "rejected_alternative_ref_duplicate")
        return self


_FORBIDDEN_PROVIDER_KEYS = {
    "analysis",
    "chainofthought",
    "credential",
    "dsn",
    "privatekey",
    "prompt",
    "rawprompt",
    "reasoning",
    "reasoningcontent",
    "systemprompt",
    "thinking",
}
_SECRET_PROVIDER_KEYS = {
    "apikey",
    "accesstoken",
    "authorization",
    "cookie",
    "credential",
    "dsn",
    "password",
    "privatekey",
    "refreshtoken",
    "secret",
    "token",
}
_SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/-]{8,}", re.IGNORECASE),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s/:]+:[^\s/@]+@", re.IGNORECASE),
    re.compile(
        r"(?i)(?:api[_\s-]*key|password|client[_\s-]*secret|"
        r"access[_\s-]*token|refresh[_\s-]*token|authorization|cookie|dsn)"
        r"[\"']?\s*[:=]\s*[\"']?[^\s,}\]]{4,}"
    ),
)
_FORBIDDEN_TEXT_MARKER = re.compile(
    r"(?i)(?:reasoning[_%\s-]*content|chain[_%\s-]*of[_%\s-]*thought|"
    r"system[_%\s-]*prompt|raw[_%\s-]*prompt)[\"']?\s*[:=]"
)
_BASE64_BLOB = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
_SANITIZER_MAX_PASSES = 12


def _decoded_security_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(str(value)))
    for _ in range(_SANITIZER_MAX_PASSES):
        decoded = unicodedata.normalize("NFKC", html.unescape(unquote(text)))
        if decoded == text:
            return text
        text = decoded
    raise ValueError("provider_envelope_security_decode_not_at_fixed_point")


def _maybe_decode_base64_text(value: str) -> str | None:
    compact = value.strip()
    if len(compact) < 12 or len(compact) % 4 or not _BASE64_BLOB.fullmatch(compact):
        return None
    try:
        decoded = base64.b64decode(compact, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    if not decoded or any(ord(character) < 9 for character in decoded):
        return None
    return _decoded_security_text(decoded)


def _normalized_security_key(key: Any) -> str:
    text = _decoded_security_text(key)
    for _ in range(_SANITIZER_MAX_PASSES):
        decoded_base64 = _maybe_decode_base64_text(text)
        if decoded_base64 is None or decoded_base64 == text:
            break
        text = decoded_base64
    else:
        raise ValueError("provider_envelope_key_decode_not_at_fixed_point")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _is_secret_provider_key(normalized: str) -> bool:
    return any(
        normalized == key or normalized.endswith(key)
        for key in _SECRET_PROVIDER_KEYS
    )


def _assert_no_forbidden_provider_material(
    value: Any,
    *,
    path: str = "$",
    encoded_depth: int = 0,
) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = _normalized_security_key(key)
            if normalized in _FORBIDDEN_PROVIDER_KEYS:
                raise ValueError(f"provider_envelope_forbidden_key:{path}.{key}")
            _assert_no_forbidden_provider_material(
                child,
                path=f"{path}.{key}",
                encoded_depth=encoded_depth,
            )
        return
    if isinstance(value, (tuple, list)):
        for index, child in enumerate(value):
            _assert_no_forbidden_provider_material(
                child,
                path=f"{path}[{index}]",
                encoded_depth=encoded_depth,
            )
        return
    if isinstance(value, str):
        decoded = _decoded_security_text(value)
        stripped = decoded.lstrip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(decoded)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, (Mapping, list)):
                _assert_no_forbidden_provider_material(
                    parsed,
                    path=path,
                    encoded_depth=encoded_depth,
                )
                return
        decoded_base64 = _maybe_decode_base64_text(decoded)
        if decoded_base64 is not None and decoded_base64 != decoded:
            if encoded_depth >= _SANITIZER_MAX_PASSES:
                raise ValueError(
                    f"provider_envelope_encoded_value_depth_exceeded:{path}"
                )
            _assert_no_forbidden_provider_material(
                decoded_base64,
                path=path,
                encoded_depth=encoded_depth + 1,
            )
        if _FORBIDDEN_TEXT_MARKER.search(decoded):
            raise ValueError(f"provider_envelope_private_reasoning_marker:{path}")
        if any(pattern.search(decoded) for pattern in _SECRET_VALUE_PATTERNS):
            raise ValueError(f"provider_envelope_secret_value:{path}")


def _opaque_argument_fragment(value: str, *, error: str) -> dict[str, Any]:
    return {
        "_unparsed_arguments": {
            "sha256": canonical_digest(value),
            "length": len(value.encode("utf-8")),
            "error": error,
        }
    }


def _scrub_tool_arguments(
    value: Any,
    *,
    root: bool = False,
    structured_depth: int = 0,
) -> Any:
    if structured_depth > _SANITIZER_MAX_PASSES:
        return _opaque_argument_fragment(
            canonical_json(value),
            error="nested_structured_arguments_depth_exceeded",
        )
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            normalized = _normalized_security_key(key)
            if _is_secret_provider_key(normalized):
                result[str(key)] = "[REDACTED]"
            else:
                result[str(key)] = _scrub_tool_arguments(
                    child,
                    structured_depth=structured_depth + 1,
                )
        return result
    if isinstance(value, (tuple, list)):
        return [
            _scrub_tool_arguments(item, structured_depth=structured_depth + 1)
            for item in value
        ]
    if isinstance(value, str):
        decoded = _decoded_security_text(value)
        looks_structured = decoded.lstrip().startswith(("{", "["))
        if root or looks_structured:
            try:
                parsed = json.loads(decoded)
            except json.JSONDecodeError:
                if root or looks_structured:
                    return _opaque_argument_fragment(
                        decoded,
                        error="unparseable_json_not_persisted",
                    )
            else:
                return _scrub_tool_arguments(
                    parsed,
                    structured_depth=structured_depth + 1,
                )
        if _maybe_decode_base64_text(decoded) is not None:
            return {
                "_encoded_blob": {
                    "sha256": canonical_digest(decoded),
                    "length": len(decoded.encode("utf-8")),
                    "status": "content_not_persisted",
                }
            }
    return value


def _sanitize_provider_envelope_once(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Apply one threat-first allowlist and recursive scrub pass."""

    _assert_no_forbidden_provider_material(payload)
    sanitized: dict[str, Any] = {}
    for key in ("call_id", "finish_reason", "error_code", "digest"):
        value = payload.get(key)
        if value is not None:
            if not isinstance(value, str):
                raise ValueError(f"provider_envelope_scalar_invalid:{key}")
            sanitized[key] = value
    assistant_output = payload.get("assistant_output")
    if assistant_output is not None:
        if not isinstance(assistant_output, str):
            raise ValueError("provider_envelope_assistant_output_invalid")
        sanitized["assistant_output"] = assistant_output
    usage = payload.get("usage")
    if usage is not None:
        if not isinstance(usage, Mapping):
            raise ValueError("provider_envelope_usage_invalid")
        allowed_usage = {
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "cached_tokens",
            "reasoning_tokens",
        }
        cleaned_usage: dict[str, int] = {}
        for key, value in usage.items():
            if key not in allowed_usage:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"provider_envelope_usage_value_invalid:{key}")
            cleaned_usage[str(key)] = value
        sanitized["usage"] = cleaned_usage
    tool_calls = payload.get("tool_calls")
    if tool_calls is not None:
        if not isinstance(tool_calls, (tuple, list)):
            raise ValueError("provider_envelope_tool_calls_invalid")
        cleaned_calls: list[dict[str, Any]] = []
        for call in tool_calls:
            if not isinstance(call, Mapping):
                raise ValueError("provider_envelope_tool_call_invalid")
            allowed_call = {
                key: call[key]
                for key in ("id", "type", "name")
                if key in call and isinstance(call[key], str)
            }
            if "arguments" in call:
                allowed_call["arguments"] = _scrub_tool_arguments(
                    call["arguments"],
                    root=isinstance(call["arguments"], str),
                )
            cleaned_calls.append(allowed_call)
        sanitized["tool_calls"] = cleaned_calls
    _assert_no_forbidden_provider_material(sanitized)
    return sanitized


def sanitize_provider_envelope(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Return the allowlisted fixed point legal for durable persistence.

    Hidden reasoning, prompts and credential material are rejected before the
    top-level allowlist is applied, so nesting or encoded keys cannot hide them.
    The result is re-sanitized until its canonical digest is unchanged; failure
    to converge within the explicit bound fails closed.
    """

    if not isinstance(payload, Mapping):
        raise TypeError("provider_envelope_mapping_required")
    current: Mapping[str, Any] = payload
    prior_digest: Digest | None = None
    for _ in range(_SANITIZER_MAX_PASSES):
        sanitized = _sanitize_provider_envelope_once(current)
        current_digest = canonical_digest(sanitized)
        if current_digest == prior_digest:
            return sanitized
        current = sanitized
        prior_digest = current_digest
    raise ValueError("provider_envelope_sanitizer_not_at_fixed_point")


def validate_public_narrative_text(value: str, *, field_name: str) -> str:
    decoded = _decoded_security_text(value)
    if any(pattern.search(decoded) for pattern in _SECRET_VALUE_PATTERNS):
        raise ValueError(f"public_narrative_secret_value:$.{field_name}")
    return value


class SanitizedProviderEnvelope(_StrictFrozenModel):
    """The only provider-envelope type legal at a durable writer boundary."""

    contract_version: Literal["1.2"] = "1.2"
    raw_envelope_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    sanitized_payload_json: str = Field(min_length=2, max_length=2_000_000)
    sanitized_payload_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    contains_private_reasoning: Literal[False] = False
    contains_unredacted_secret: Literal[False] = False
    sanitization_receipt_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @model_validator(mode="after")
    def validate_sanitized_envelope(self) -> "SanitizedProviderEnvelope":
        try:
            decoded = json.loads(self.sanitized_payload_json)
        except json.JSONDecodeError as exc:
            raise ValueError("sanitized_provider_payload_json_invalid") from exc
        if canonical_digest(decoded) != self.sanitized_payload_digest:
            raise ValueError("sanitized_provider_payload_digest_mismatch")
        _assert_no_forbidden_provider_material(decoded)
        _verify_digest(
            self,
            "sanitization_receipt_digest",
            "sanitized_provider_envelope_receipt_digest_mismatch",
        )
        return self


def prepare_provider_envelope_for_persistence(
    payload: Mapping[str, Any],
) -> SanitizedProviderEnvelope:
    """Reach the sanitizer fixed point and return the sole durable type."""

    sanitized = sanitize_provider_envelope(payload)
    body = {
        "contract_version": "1.2",
        "raw_envelope_digest": canonical_digest(payload),
        "sanitized_payload_json": canonical_json(sanitized),
        "sanitized_payload_digest": canonical_digest(sanitized),
        "contains_private_reasoning": False,
        "contains_unredacted_secret": False,
    }
    return SanitizedProviderEnvelope(
        **body,
        sanitization_receipt_digest=canonical_digest(body),
    )


class DecisionArtifact(_StrictFrozenModel):
    """Audit-safe research path; never a hidden chain-of-thought transcript."""

    contract_version: Literal["1.2"] = "1.2"
    decision_artifact_id: str = Field(pattern=_REF_PATTERN)
    revision: int = Field(ge=0)
    task_id: str = Field(pattern=_REF_PATTERN)
    goal: str = Field(min_length=8, max_length=4_000)
    observation_refs: tuple[str, ...] = Field(default=(), max_length=256)
    chosen_action: str = Field(min_length=1, max_length=1_000)
    concise_rationale: str = Field(min_length=8, max_length=4_000)
    rejected_alternatives: tuple[RejectedAlternative, ...] = Field(
        default=(), max_length=32
    )
    uncertainty: str = Field(min_length=1, max_length=2_000)
    confidence: Literal["low", "medium", "high", "not_assessed"]
    next_actions: tuple[AvailableNextAction, ...] = Field(default=(), max_length=16)
    validator_receipt_refs: tuple[str, ...] = Field(default=(), max_length=64)
    verifier_receipt_refs: tuple[str, ...] = Field(default=(), max_length=64)
    context_manifest_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    contains_private_reasoning: Literal[False] = False
    artifact_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @field_validator("goal", "chosen_action", "concise_rationale", "uncertainty")
    @classmethod
    def validate_public_text(cls, value: str, info: Any) -> str:
        return validate_public_narrative_text(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_decision_artifact(self) -> "DecisionArtifact":
        for name in (
            "observation_refs",
            "validator_receipt_refs",
            "verifier_receipt_refs",
        ):
            _unique(tuple(getattr(self, name)), f"decision_{name}_duplicate")
        action_kinds = tuple(item.action for item in self.next_actions)
        _unique(action_kinds, "decision_next_action_duplicate")
        _verify_digest(self, "artifact_digest", "decision_artifact_digest_mismatch")
        return self


class ModelVisibleContextManifest(_StrictFrozenModel):
    """Allowlisted public context projected for exactly one model turn."""

    contract_version: Literal["1.2"] = "1.2"
    manifest_id: str = Field(pattern=_REF_PATTERN)
    task_id: str = Field(pattern=_REF_PATTERN)
    objective: str = Field(min_length=8, max_length=4_000)
    objective_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    task_assignment_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    governance_summary: str = Field(min_length=8, max_length=4_000)
    runtime_policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    disclosure_policy_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    authority_matrix_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    plan_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    research_graph_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    latest_plan_delta_refs: tuple[str, ...] = Field(default=(), max_length=32)
    observation_refs: tuple[str, ...] = Field(default=(), max_length=256)
    unresolved_feedback_refs: tuple[str, ...] = Field(default=(), max_length=128)
    l0_catalog_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    l0_capability_refs: tuple[str, ...] = Field(default=(), max_length=128)
    granted_disclosure_receipt_refs: tuple[str, ...] = Field(default=(), max_length=128)
    available_next_actions: tuple[AvailableNextAction, ...] = Field(
        min_length=1, max_length=32
    )
    budget_status: Literal[
        "within_budget",
        "approaching_limit",
        "exhausted",
        "not_applicable",
    ]
    stop_status: Literal[
        "continue",
        "pause_required",
        "human_required",
        "stop_sufficient",
    ]
    intervention_status: Literal["none", "pending", "applied"]
    context_checkpoint_ref: str | None = Field(default=None, pattern=_REF_PATTERN)
    current_model_context_snapshot_digest: Digest = Field(pattern=_DIGEST_PATTERN)
    public_content_only: Literal[True] = True
    manifest_digest: Digest = Field(pattern=_DIGEST_PATTERN)

    @field_validator("objective", "governance_summary")
    @classmethod
    def validate_public_text(cls, value: str, info: Any) -> str:
        return validate_public_narrative_text(value, field_name=info.field_name)

    @model_validator(mode="after")
    def validate_public_manifest(self) -> "ModelVisibleContextManifest":
        if self.objective_digest != research_objective_digest(self.objective):
            raise ValueError("context_manifest_objective_digest_mismatch")
        for name in (
            "latest_plan_delta_refs",
            "observation_refs",
            "unresolved_feedback_refs",
            "l0_capability_refs",
            "granted_disclosure_receipt_refs",
        ):
            _unique(tuple(getattr(self, name)), f"context_manifest_{name}_duplicate")
        action_kinds = tuple(item.action for item in self.available_next_actions)
        _unique(action_kinds, "context_manifest_next_action_duplicate")
        if self.budget_status == "exhausted" and self.stop_status == "continue":
            raise ValueError("exhausted_budget_cannot_silently_continue")
        if self.stop_status == "human_required" and not any(
            action.action == "request_human_review"
            for action in self.available_next_actions
        ):
            raise ValueError("human_required_manifest_lacks_human_action")
        _verify_digest(self, "manifest_digest", "context_manifest_digest_mismatch")
        return self


__all__ = [
    "AddTaskAction",
    "AgenticPlanDeltaV1_2",
    "AuthorityImpact",
    "AvailableNextAction",
    "BaselineSourcePlan",
    "BudgetDelta",
    "CancelTaskAction",
    "CoverageObligation",
    "CoverageStateSnapshot",
    "DecisionArtifact",
    "DELL_COVERAGE_OBLIGATION_IDS",
    "DeferTaskAction",
    "Digest",
    "ExternalSourceIntent",
    "GapEligibilityRequest",
    "GapEligibilityReceipt",
    "LocalEvidenceIntent",
    "MinimumRouteObligation",
    "ModelNodeAuthorityEntry",
    "ModelNodeAuthorityMatrix",
    "ModelVisibleContextManifest",
    "ModifyTaskAction",
    "ResearchPlan",
    "ResearchTaskSpec",
    "RejectedAlternative",
    "ReviewedEvidenceIntent",
    "RouteReplacement",
    "RuntimePolicySnapshot",
    "RuntimeScope",
    "RuntimeScopeAuthorizationRecord",
    "SanitizedProviderEnvelope",
    "TokenBudgetBasis",
    "ToolFailureReceipt",
    "VerifiedArtifactRef",
    "VerifiedArtifactRegistryResolver",
    "VerifiedArtifactRegistrySnapshot",
    "ZeroModelRuntimeBoundaryReceipt",
    "ZeroModelTransportAuditEvent",
    "ZeroModelTransportAuditPort",
    "authorize_gap_eligibility",
    "canonical_digest",
    "canonical_json_bytes",
    "coverage_state_snapshot",
    "issue_runtime_scope_authorization_record",
    "payload_without",
    "prepare_provider_envelope_for_persistence",
    "research_plan_graph_digest",
    "research_objective_digest",
    "sanitize_provider_envelope",
    "task_assignment_authority_digest",
    "validate_agentic_plan_delta_reference_integrity",
    "validate_public_narrative_text",
    "validate_research_plan_reference_integrity",
    "validate_zero_model_runtime_boundary",
    "wave0a_zero_model_transport_gateway",
]
