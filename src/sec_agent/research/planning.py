from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import json
from typing import Any, Mapping

from retrieval.contracts import (
    EVIDENCE_REQUEST_SCHEMA_VERSION,
    EvidenceRequest,
    FinancialResearchKernel,
    RetrievalContractError,
    load_evidence_request,
)
from retrieval.query_plan import canonical_digest
from retrieval.route_compiler import QueryObjectFactRoutePolicy


RESEARCH_PLANNING_POLICY_SCHEMA_VERSION = "fin_ia_research_planning_policy_v1_1"
RESEARCH_PLANNING_POLICY_SUCCESSOR_SCHEMA_VERSION = (
    "fin_ia_research_planning_policy_v1_2"
)
SUPPORTED_RESEARCH_PLANNING_POLICY_SCHEMA_VERSIONS = frozenset(
    {
        RESEARCH_PLANNING_POLICY_SCHEMA_VERSION,
        RESEARCH_PLANNING_POLICY_SUCCESSOR_SCHEMA_VERSION,
    }
)
RESEARCH_OBJECTIVE_DRAFT_SCHEMA_VERSION = "fin_ia_research_objective_draft_v1_0"
RESEARCH_OBJECTIVE_SCHEMA_VERSION = "fin_ia_research_objective_v1_0"
PLANNER_ATOMS_SCHEMA_VERSION = "fin_ia_research_planner_atoms_v1_0"
COMPILED_RESEARCH_PLAN_SCHEMA_VERSION = "fin_ia_compiled_research_plan_v1_1"

_REQUIRED_AUTHORITY = {
    "model_may_select_bounded_atoms_only": True,
    "harness_owns_identity_dates_sources_budgets_and_lineage": True,
    "canonical_metric_ids_required": True,
    "database_lane_required_for_exact_numeric_authority": True,
    "candidate_is_not_evidence": True,
    "planner_output_is_not_research_judgment": True,
}


class ResearchPlanningError(ValueError):
    """Fail-closed error at the S3 planning-to-EvidenceRequest boundary."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ResearchPlanningError(code)


def _strings(value: object, code: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    _require(isinstance(value, list), code)
    rows = tuple(str(item).strip() for item in value)
    _require(
        (allow_empty or bool(rows))
        and all(rows)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


@dataclass(frozen=True)
class FamilyPlanningBinding:
    query_family_id: str
    evidence_domain: str
    requester_role: str


@dataclass(frozen=True)
class ResearchPlanningPolicy:
    family_bindings: tuple[FamilyPlanningBinding, ...]
    allowed_task_types: tuple[str, ...]
    allowed_output_formats: tuple[str, ...]
    allowed_gap_policies: tuple[str, ...]
    allowed_pass_criteria: tuple[str, ...]
    required_pass_criteria: tuple[str, ...]
    forbidden_proxy: tuple[str, ...]
    max_budget: Mapping[str, int]
    max_proposed_atoms: int
    selection_strategy: str
    facet_execution_priority: tuple[str, ...]
    defaults: Mapping[str, str]
    authority: Mapping[str, bool]

    def binding_by_family(self) -> dict[str, FamilyPlanningBinding]:
        return {row.query_family_id: row for row in self.family_bindings}

    def priority_by_facet(self) -> dict[str, int]:
        return {
            facet_id: index
            for index, facet_id in enumerate(self.facet_execution_priority)
        }

    def selection_contract(self) -> dict[str, Any]:
        return {
            "max_proposed_atoms": self.max_proposed_atoms,
            "strategy": self.selection_strategy,
            "facet_execution_priority": list(self.facet_execution_priority),
        }


@dataclass(frozen=True)
class ResearchObjectiveBudget:
    # Historical external name retained for objective-id compatibility.  It is
    # the EvidenceRequest execution ceiling, not the model proposal ceiling.
    max_evidence_requests: int
    max_metric_intents_per_request: int
    max_product_intents_per_request: int
    max_model_calls: int


@dataclass(frozen=True)
class ResearchObjectivePeriod:
    start_date: date | None
    end_date: date
    fiscal_years: tuple[int, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat(),
            "fiscal_years": list(self.fiscal_years),
        }


@dataclass(frozen=True)
class ResearchObjective:
    schema_version: str
    objective_id: str
    raw_question: str
    task_type: str
    case_key: str
    subject_ticker: str
    subject_legal_name: str
    research_as_of: date
    required_slot_ids: tuple[str, ...]
    allowed_source_types: tuple[str, ...]
    forbidden_source_types: tuple[str, ...]
    output_format: str
    gap_policy: str
    reviewer_role: str
    period: ResearchObjectivePeriod
    budget: ResearchObjectiveBudget
    pass_criteria: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["research_as_of"] = self.research_as_of.isoformat()
        value["required_slot_ids"] = list(self.required_slot_ids)
        value["allowed_source_types"] = list(self.allowed_source_types)
        value["forbidden_source_types"] = list(self.forbidden_source_types)
        value["period"] = self.period.as_dict()
        value["pass_criteria"] = list(self.pass_criteria)
        return value


@dataclass(frozen=True)
class PlannerAtom:
    facet_id: str
    target_entity: str
    metric_ids: tuple[str, ...]
    product_intents: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "facet_id": self.facet_id,
            "target_entity": self.target_entity,
            "metric_ids": list(self.metric_ids),
            "product_intents": list(self.product_intents),
        }


@dataclass(frozen=True)
class DeferredPlannerAtom:
    atom: PlannerAtom
    slot_id: str
    execution_priority: int
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "atom": self.atom.as_dict(),
            "slot_id": self.slot_id,
            "execution_priority": self.execution_priority,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CompiledResearchPlan:
    schema_version: str
    objective: ResearchObjective
    proposed_atoms: tuple[PlannerAtom, ...]
    planner_atoms: tuple[PlannerAtom, ...]
    deferred_atoms: tuple[DeferredPlannerAtom, ...]
    selection: Mapping[str, Any]
    evidence_requests: tuple[EvidenceRequest, ...]
    authority: Mapping[str, bool]
    plan_digest: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "objective": self.objective.as_dict(),
            "proposed_atoms": [row.as_dict() for row in self.proposed_atoms],
            "planner_atoms": [row.as_dict() for row in self.planner_atoms],
            "deferred_atoms": [row.as_dict() for row in self.deferred_atoms],
            "selection": dict(self.selection),
            "evidence_requests": [row.as_dict() for row in self.evidence_requests],
            "authority": dict(self.authority),
            "plan_digest": self.plan_digest,
        }


def load_research_planning_policy(
    payload: Mapping[str, Any],
    route_policy: QueryObjectFactRoutePolicy,
) -> ResearchPlanningPolicy:
    """Load the provider-neutral S3 control plane and check S1/S2 coverage."""

    expected_fields = {
        "schema_version",
        "status",
        "allowed_task_types",
        "allowed_output_formats",
        "allowed_gap_policies",
        "allowed_pass_criteria",
        "required_pass_criteria",
        "family_bindings",
        "forbidden_proxy",
        "max_budget",
        "atom_selection",
        "defaults",
        "authority",
    }
    _require(set(payload) == expected_fields, "research_planning_policy_fields_invalid")
    _require(
        payload.get("schema_version")
        in SUPPORTED_RESEARCH_PLANNING_POLICY_SCHEMA_VERSIONS,
        "research_planning_policy_schema_invalid",
    )
    _require(
        payload.get("status") == "provider_neutral_s3_planning_control_plane",
        "research_planning_policy_status_invalid",
    )
    bindings: list[FamilyPlanningBinding] = []
    raw_bindings = payload.get("family_bindings")
    _require(isinstance(raw_bindings, list) and bool(raw_bindings), "research_planning_family_bindings_invalid")
    for raw in raw_bindings:
        _require(
            isinstance(raw, Mapping)
            and set(raw) == {"query_family_id", "evidence_domain", "requester_role"},
            "research_planning_family_binding_invalid",
        )
        row = FamilyPlanningBinding(
            query_family_id=str(raw.get("query_family_id") or "").strip(),
            evidence_domain=str(raw.get("evidence_domain") or "").strip(),
            requester_role=str(raw.get("requester_role") or "").strip(),
        )
        _require(
            row.query_family_id and row.evidence_domain and row.requester_role,
            "research_planning_family_binding_invalid",
        )
        bindings.append(row)
    family_ids = {row.family_id for row in route_policy.query_families}
    bound_ids = [row.query_family_id for row in bindings]
    _require(
        len(bound_ids) == len(set(bound_ids)) and set(bound_ids) == family_ids,
        "research_planning_family_coverage_invalid",
    )

    allowed_pass = _strings(payload.get("allowed_pass_criteria"), "research_planning_pass_criteria_invalid")
    required_pass = _strings(payload.get("required_pass_criteria"), "research_planning_required_pass_criteria_invalid")
    _require(set(required_pass).issubset(allowed_pass), "research_planning_required_pass_criteria_invalid")
    raw_budget = payload.get("max_budget")
    budget_fields = {
        "max_evidence_requests",
        "max_metric_intents_per_request",
        "max_product_intents_per_request",
        "max_model_calls",
    }
    _require(isinstance(raw_budget, Mapping) and set(raw_budget) == budget_fields, "research_planning_budget_invalid")
    max_budget = {key: int(raw_budget[key]) for key in budget_fields}
    _require(
        1 <= max_budget["max_evidence_requests"] <= 20
        and 1 <= max_budget["max_metric_intents_per_request"] <= 12
        and 1 <= max_budget["max_product_intents_per_request"] <= 12
        and 0 <= max_budget["max_model_calls"] <= 8,
        "research_planning_budget_invalid",
    )
    raw_selection = payload.get("atom_selection")
    _require(
        isinstance(raw_selection, Mapping)
        and set(raw_selection)
        == {"max_proposed_atoms", "strategy", "facet_execution_priority"},
        "research_planning_atom_selection_invalid",
    )
    max_proposed_atoms = int(raw_selection["max_proposed_atoms"])
    selection_strategy = str(raw_selection["strategy"] or "").strip()
    facet_execution_priority = _strings(
        raw_selection.get("facet_execution_priority"),
        "research_planning_atom_selection_invalid",
    )
    known_facets = set(route_policy.family_by_facet())
    planned_facets = set(facet_execution_priority)
    # A provider-neutral S1 route policy may add a new explicit-request facet
    # before the S3 planner is authorized to propose it.  The v1.1 planner is
    # therefore backward-compatible with a strict subset of a successor route
    # policy.  A v1.2 planner is the migration contract and must cover the
    # entire mounted route surface.  Unknown planner facets always fail closed.
    facet_contract_valid = (
        planned_facets.issubset(known_facets)
        and (
            payload.get("schema_version")
            == RESEARCH_PLANNING_POLICY_SCHEMA_VERSION
            or planned_facets == known_facets
        )
    )
    _require(
        max_budget["max_evidence_requests"] <= max_proposed_atoms <= 20
        and selection_strategy
        == "required_slot_first_then_provider_neutral_facet_priority"
        and facet_contract_valid,
        "research_planning_atom_selection_invalid",
    )
    defaults = payload.get("defaults")
    _require(
        isinstance(defaults, Mapping)
        and set(defaults) == {"granularity", "unit", "stop_condition"}
        and all(str(value).strip() for value in defaults.values()),
        "research_planning_defaults_invalid",
    )
    authority = payload.get("authority")
    _require(
        isinstance(authority, Mapping) and dict(authority) == _REQUIRED_AUTHORITY,
        "research_planning_authority_invalid",
    )
    return ResearchPlanningPolicy(
        family_bindings=tuple(bindings),
        allowed_task_types=_strings(payload.get("allowed_task_types"), "research_planning_task_types_invalid"),
        allowed_output_formats=_strings(payload.get("allowed_output_formats"), "research_planning_output_formats_invalid"),
        allowed_gap_policies=_strings(payload.get("allowed_gap_policies"), "research_planning_gap_policies_invalid"),
        allowed_pass_criteria=allowed_pass,
        required_pass_criteria=required_pass,
        forbidden_proxy=_strings(payload.get("forbidden_proxy"), "research_planning_forbidden_proxy_invalid"),
        max_budget=max_budget,
        max_proposed_atoms=max_proposed_atoms,
        selection_strategy=selection_strategy,
        facet_execution_priority=facet_execution_priority,
        defaults={key: str(value).strip() for key, value in defaults.items()},
        authority=dict(authority),
    )


def compile_research_objective(
    payload: Mapping[str, Any],
    *,
    kernel: FinancialResearchKernel,
    policy: ResearchPlanningPolicy,
) -> ResearchObjective:
    """Bind a user-facing objective draft to current case identity and as-of."""

    expected_fields = {
        "schema_version",
        "raw_question",
        "task_type",
        "case_key",
        "required_slot_ids",
        "allowed_source_types",
        "forbidden_source_types",
        "output_format",
        "gap_policy",
        "reviewer_role",
        "period",
        "budget",
        "pass_criteria",
    }
    _require(set(payload) == expected_fields, "research_objective_draft_fields_invalid")
    _require(
        payload.get("schema_version") == RESEARCH_OBJECTIVE_DRAFT_SCHEMA_VERSION,
        "research_objective_draft_schema_invalid",
    )
    case_key = str(payload.get("case_key") or "").strip().upper()
    _require(case_key in kernel.cases, "research_objective_case_unknown")
    profile = kernel.cases[case_key]
    raw_question = str(payload.get("raw_question") or "").strip()
    _require(20 <= len(raw_question) <= 2000, "research_objective_question_invalid")
    task_type = str(payload.get("task_type") or "").strip()
    output_format = str(payload.get("output_format") or "").strip()
    gap_policy = str(payload.get("gap_policy") or "").strip()
    _require(task_type in policy.allowed_task_types, "research_objective_task_type_invalid")
    _require(output_format in policy.allowed_output_formats, "research_objective_output_format_invalid")
    _require(gap_policy in policy.allowed_gap_policies, "research_objective_gap_policy_invalid")

    slot_ids = _strings(payload.get("required_slot_ids"), "research_objective_slots_invalid")
    known_slots = {row.slot_id for row in kernel.slots}
    _require(set(slot_ids).issubset(known_slots), "research_objective_slot_unknown")
    known_sources = {source for row in kernel.slots for source in row.source_types}
    allowed_sources = _strings(payload.get("allowed_source_types"), "research_objective_allowed_sources_invalid")
    forbidden_sources = _strings(
        payload.get("forbidden_source_types"),
        "research_objective_forbidden_sources_invalid",
        allow_empty=True,
    )
    _require(
        set(allowed_sources).issubset(known_sources)
        and set(forbidden_sources).issubset(known_sources)
        and not set(allowed_sources).intersection(forbidden_sources),
        "research_objective_source_policy_invalid",
    )

    raw_period = payload.get("period")
    _require(
        isinstance(raw_period, Mapping)
        and set(raw_period) == {"start_date", "fiscal_years"},
        "research_objective_period_invalid",
    )
    try:
        start_date = (
            date.fromisoformat(str(raw_period["start_date"]))
            if raw_period.get("start_date")
            else None
        )
    except ValueError as exc:
        raise ResearchPlanningError("research_objective_period_invalid") from exc
    fiscal_years = tuple(int(value) for value in raw_period.get("fiscal_years") or ())
    _require(
        len(fiscal_years) == len(set(fiscal_years))
        and all(1990 <= value <= profile.research_as_of.year + 1 for value in fiscal_years)
        and (start_date is None or start_date <= profile.research_as_of),
        "research_objective_period_invalid",
    )
    period = ResearchObjectivePeriod(
        start_date=start_date,
        end_date=profile.research_as_of,
        fiscal_years=fiscal_years,
    )

    raw_budget = payload.get("budget")
    budget_fields = set(policy.max_budget)
    _require(isinstance(raw_budget, Mapping) and set(raw_budget) == budget_fields, "research_objective_budget_invalid")
    requested_budget = {key: int(raw_budget[key]) for key in budget_fields}
    _require(
        all(0 <= value <= policy.max_budget[key] for key, value in requested_budget.items())
        and requested_budget["max_evidence_requests"] >= len(slot_ids)
        and requested_budget["max_metric_intents_per_request"] >= 1
        and requested_budget["max_product_intents_per_request"] >= 1,
        "research_objective_budget_invalid",
    )
    budget = ResearchObjectiveBudget(**requested_budget)
    pass_criteria = _strings(payload.get("pass_criteria"), "research_objective_pass_criteria_invalid")
    _require(
        set(pass_criteria).issubset(policy.allowed_pass_criteria)
        and set(policy.required_pass_criteria).issubset(pass_criteria),
        "research_objective_pass_criteria_invalid",
    )
    reviewer_role = str(payload.get("reviewer_role") or "").strip()
    _require(reviewer_role and len(reviewer_role) <= 80, "research_objective_reviewer_invalid")

    unsigned = {
        **dict(payload),
        "case_key": case_key,
        "subject_ticker": profile.subject_ticker,
        "subject_legal_name": profile.subject_legal_name,
        "research_as_of": profile.research_as_of.isoformat(),
        "period": period.as_dict(),
    }
    return ResearchObjective(
        schema_version=RESEARCH_OBJECTIVE_SCHEMA_VERSION,
        objective_id=f"ROC::{canonical_digest(unsigned)[:24]}",
        raw_question=raw_question,
        task_type=task_type,
        case_key=case_key,
        subject_ticker=profile.subject_ticker,
        subject_legal_name=profile.subject_legal_name,
        research_as_of=profile.research_as_of,
        required_slot_ids=slot_ids,
        allowed_source_types=allowed_sources,
        forbidden_source_types=forbidden_sources,
        output_format=output_format,
        gap_policy=gap_policy,
        reviewer_role=reviewer_role,
        period=period,
        budget=budget,
        pass_criteria=pass_criteria,
    )


def compile_research_plan(
    payload: Mapping[str, Any],
    *,
    objective: ResearchObjective,
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
    planning_policy: ResearchPlanningPolicy,
) -> CompiledResearchPlan:
    """Compile bounded model atoms into deterministic S1/S2 EvidenceRequests."""

    _require(
        set(payload) == {"schema_version", "objective_id", "atoms"},
        "research_planner_output_fields_invalid",
    )
    _require(
        payload.get("schema_version") == PLANNER_ATOMS_SCHEMA_VERSION,
        "research_planner_output_schema_invalid",
    )
    _require(payload.get("objective_id") == objective.objective_id, "research_planner_objective_binding_invalid")
    raw_atoms = payload.get("atoms")
    _require(
        isinstance(raw_atoms, list)
        and bool(raw_atoms)
        and len(raw_atoms) <= planning_policy.max_proposed_atoms,
        "research_planner_proposal_budget_invalid",
    )

    facets = {
        facet.facet_id: (slot, facet)
        for slot in kernel.slots
        for facet in slot.facets
    }
    family_by_facet = route_policy.family_by_facet()
    metric_by_id = {row.metric_id: row for row in route_policy.metric_routes}
    binding_by_family = planning_policy.binding_by_family()
    atoms: list[PlannerAtom] = []
    scopes: set[tuple[str, str]] = set()
    for raw in raw_atoms:
        _require(
            isinstance(raw, Mapping)
            and set(raw) == {"facet_id", "target_entity", "metric_ids", "product_intents"},
            "research_planner_atom_fields_invalid",
        )
        facet_id = str(raw.get("facet_id") or "").strip()
        target = str(raw.get("target_entity") or "").strip().upper()
        _require(facet_id in facets, "research_planner_facet_unknown")
        _require(
            target == objective.subject_ticker,
            "research_planner_target_entity_invalid",
        )
        slot, _ = facets[facet_id]
        _require(slot.slot_id in objective.required_slot_ids, "research_planner_scope_expansion_forbidden")
        scope = (facet_id, target)
        _require(scope not in scopes, "research_planner_atom_duplicate_scope")
        scopes.add(scope)
        metric_ids = _strings(raw.get("metric_ids"), "research_planner_metric_ids_invalid", allow_empty=True)
        product_intents = _strings(raw.get("product_intents"), "research_planner_product_intents_invalid", allow_empty=True)
        _require(bool(metric_ids or product_intents), "research_planner_atom_intent_missing")
        _require(
            len(metric_ids) <= objective.budget.max_metric_intents_per_request
            and len(product_intents) <= objective.budget.max_product_intents_per_request,
            "research_planner_atom_intent_budget_invalid",
        )
        family = family_by_facet.get(facet_id)
        _require(family is not None, "research_planner_facet_unrouted")
        _require(family.family_id in binding_by_family, "research_planner_family_unbound")
        for metric_id in metric_ids:
            metric = metric_by_id.get(metric_id)
            _require(metric is not None, "research_planner_metric_id_unknown")
            _require(
                family.family_id in metric.allowed_query_families,
                "research_planner_metric_family_mismatch",
            )
        atoms.append(
            PlannerAtom(
                facet_id=facet_id,
                target_entity=target,
                metric_ids=metric_ids,
                product_intents=product_intents,
            )
        )

    covered_slots = {facets[row.facet_id][0].slot_id for row in atoms}
    _require(
        set(objective.required_slot_ids).issubset(covered_slots),
        "research_planner_required_slot_uncovered",
    )
    priority_by_facet = planning_policy.priority_by_facet()
    proposed_atoms = tuple(
        sorted(
            atoms,
            key=lambda row: (
                objective.required_slot_ids.index(facets[row.facet_id][0].slot_id),
                priority_by_facet[row.facet_id],
                row.target_entity,
            ),
        )
    )

    selected_scopes: set[tuple[str, str]] = set()
    selected_atoms: list[PlannerAtom] = []
    for slot_id in objective.required_slot_ids:
        slot_atoms = [
            row
            for row in proposed_atoms
            if facets[row.facet_id][0].slot_id == slot_id
        ]
        _require(bool(slot_atoms), "research_planner_required_slot_uncovered")
        primary = min(
            slot_atoms,
            key=lambda row: (
                priority_by_facet[row.facet_id],
                row.target_entity,
            ),
        )
        selected_atoms.append(primary)
        selected_scopes.add((primary.facet_id, primary.target_entity))

    remaining_capacity = (
        objective.budget.max_evidence_requests - len(selected_atoms)
    )
    remaining_atoms = sorted(
        (
            row
            for row in proposed_atoms
            if (row.facet_id, row.target_entity) not in selected_scopes
        ),
        key=lambda row: (
            priority_by_facet[row.facet_id],
            objective.required_slot_ids.index(
                facets[row.facet_id][0].slot_id
            ),
            row.target_entity,
        ),
    )
    for atom in remaining_atoms[:remaining_capacity]:
        selected_atoms.append(atom)
        selected_scopes.add((atom.facet_id, atom.target_entity))

    ordered_atoms = tuple(
        sorted(
            selected_atoms,
            key=lambda row: (
                objective.required_slot_ids.index(
                    facets[row.facet_id][0].slot_id
                ),
                priority_by_facet[row.facet_id],
                row.target_entity,
            ),
        )
    )
    deferred_atoms = tuple(
        DeferredPlannerAtom(
            atom=row,
            slot_id=facets[row.facet_id][0].slot_id,
            execution_priority=priority_by_facet[row.facet_id] + 1,
            reason=(
                "execution_budget_exhausted_after_required_slot_and_"
                "provider_neutral_facet_priority_selection"
            ),
        )
        for row in proposed_atoms
        if (row.facet_id, row.target_entity) not in selected_scopes
    )
    selection_contract = planning_policy.selection_contract()
    selection = {
        "strategy": planning_policy.selection_strategy,
        "proposal_ceiling": planning_policy.max_proposed_atoms,
        "proposed_atom_count": len(proposed_atoms),
        "execution_request_budget": objective.budget.max_evidence_requests,
        "selected_atom_count": len(ordered_atoms),
        "deferred_atom_count": len(deferred_atoms),
        "required_slot_ids_preserved": list(objective.required_slot_ids),
        "selection_policy_digest": canonical_digest(selection_contract),
    }

    evidence_requests: list[EvidenceRequest] = []
    profile = kernel.cases[objective.case_key]
    for atom in ordered_atoms:
        slot, facet = facets[atom.facet_id]
        family = family_by_facet[atom.facet_id]
        binding = binding_by_family[family.family_id]
        acceptable_sources = tuple(
            source
            for source in slot.source_types
            if source in objective.allowed_source_types
            and source not in objective.forbidden_source_types
        )
        _require(bool(acceptable_sources), "research_planner_no_acceptable_source")
        target_entities: list[str] = []
        needs_related_context = any(
            role.startswith("related_entity")
            for role in facet.required_source_roles
        )
        needs_issuer_disclosure = (
            "issuer_disclosure" in facet.required_source_roles
        )
        if facet.evidence_owner_scope != "related_only" and (
            needs_issuer_disclosure or not needs_related_context
        ):
            target_entities.append(objective.subject_ticker)
        if (
            facet.evidence_owner_scope in {"subject_and_related", "related_only"}
            and (needs_related_context or not needs_issuer_disclosure)
        ):
            target_entities.extend(
                entity.ticker
                for entity in profile.related_entities
                if not facet.related_economic_roles
                or entity.economic_role in facet.related_economic_roles
            )
        _require(
            bool(target_entities),
            "research_planner_compiled_evidence_owner_targets_missing",
        )
        identity = {
            "objective_id": objective.objective_id,
            "facet_id": atom.facet_id,
            "target_entities": target_entities,
            "metric_ids": atom.metric_ids,
            "product_intents": atom.product_intents,
        }
        identity_digest = canonical_digest(identity)[:24]
        request_payload = {
            "schema_version": EVIDENCE_REQUEST_SCHEMA_VERSION,
            "request_id": f"REQ::{identity_digest}",
            "cell_id": f"CELL::{identity_digest}",
            "requester_role": binding.requester_role,
            "evidence_domain": binding.evidence_domain,
            "case_key": objective.case_key,
            "subject_ticker": objective.subject_ticker,
            "research_as_of": objective.research_as_of.isoformat(),
            "target_entities": target_entities,
            "requested_facet_ids": [atom.facet_id],
            "metric_intents": list(atom.metric_ids),
            "product_intents": list(atom.product_intents),
            "period": objective.period.as_dict(),
            "granularity": planning_policy.defaults["granularity"],
            "unit": planning_policy.defaults["unit"],
            "acceptable_sources": list(acceptable_sources),
            "acceptable_proxy": False,
            "forbidden_proxy": list(planning_policy.forbidden_proxy),
            "stop_condition": planning_policy.defaults["stop_condition"],
            "clarification_policy": objective.gap_policy,
        }
        try:
            evidence_requests.append(load_evidence_request(request_payload, kernel))
        except RetrievalContractError as exc:
            raise ResearchPlanningError(f"research_planner_compiled_request_invalid:{exc}") from exc

    unsigned = {
        "schema_version": COMPILED_RESEARCH_PLAN_SCHEMA_VERSION,
        "objective": objective.as_dict(),
        "proposed_atoms": [row.as_dict() for row in proposed_atoms],
        "planner_atoms": [row.as_dict() for row in ordered_atoms],
        "deferred_atoms": [row.as_dict() for row in deferred_atoms],
        "selection": selection,
        "evidence_requests": [row.as_dict() for row in evidence_requests],
        "authority": dict(planning_policy.authority),
    }
    return CompiledResearchPlan(
        schema_version=COMPILED_RESEARCH_PLAN_SCHEMA_VERSION,
        objective=objective,
        proposed_atoms=proposed_atoms,
        planner_atoms=ordered_atoms,
        deferred_atoms=deferred_atoms,
        selection=selection,
        evidence_requests=tuple(evidence_requests),
        authority=dict(planning_policy.authority),
        plan_digest=canonical_digest(unsigned),
    )


def compile_research_planner_messages(
    *,
    objective: ResearchObjective,
    kernel: FinancialResearchKernel,
    route_policy: QueryObjectFactRoutePolicy,
    planning_policy: ResearchPlanningPolicy,
) -> tuple[dict[str, str], ...]:
    """Compile one small provider-neutral planner prompt from active contracts.

    The model sees only the choices it may make. Identity, dates, sources,
    budgets, request IDs and numeric authority remain outside its output.
    """

    family_by_facet = route_policy.family_by_facet()
    allowed_slots: list[dict[str, Any]] = []
    for slot in kernel.slots:
        if slot.slot_id not in objective.required_slot_ids:
            continue
        facet_rows: list[dict[str, Any]] = []
        for facet in slot.facets:
            family = family_by_facet.get(facet.facet_id)
            _require(family is not None, "research_planner_prompt_facet_unrouted")
            metric_ids = sorted(
                metric.metric_id
                for metric in route_policy.metric_routes
                if family.family_id in metric.allowed_query_families
            )
            facet_rows.append(
                {
                    "facet_id": facet.facet_id,
                    "business_question_zh": facet.business_question_zh,
                    "allowed_metric_ids": metric_ids,
                }
            )
        allowed_slots.append(
            {
                "slot_id": slot.slot_id,
                "business_question_zh": slot.business_question_zh,
                "facets": facet_rows,
            }
        )
    contract = {
        "objective": {
            "objective_id": objective.objective_id,
            "question": objective.raw_question,
            "subject_ticker": objective.subject_ticker,
            "subject_legal_name": objective.subject_legal_name,
            "research_as_of": objective.research_as_of.isoformat(),
            "required_slot_ids": list(objective.required_slot_ids),
            "maximum_proposed_atoms": planning_policy.max_proposed_atoms,
            "maximum_executed_evidence_requests": (
                objective.budget.max_evidence_requests
            ),
            "maximum_metric_ids_per_atom": (
                objective.budget.max_metric_intents_per_request
            ),
            "maximum_product_intents_per_atom": (
                objective.budget.max_product_intents_per_request
            ),
        },
        "allowed_slots_and_facets": allowed_slots,
        "output_contract": {
            "schema_version": PLANNER_ATOMS_SCHEMA_VERSION,
            "objective_id": objective.objective_id,
            "atoms": [
                {
                    "facet_id": "one allowed facet_id",
                    "target_entity": objective.subject_ticker,
                    "metric_ids": ["zero or more allowed canonical metric IDs"],
                    "product_intents": [
                        "zero or more concise company-specific research intents"
                    ],
                }
            ],
        },
        "rules": [
            "Cover every required slot with at least one atom.",
            "You may propose more atoms than the execution budget, up to maximum_proposed_atoms; the harness deterministically selects execution requests and preserves deferred atoms with reasons.",
            "Use only listed facet_id and canonical metric_id values.",
            "Use only the subject ticker as target_entity in this canary.",
            "Choose metrics and product intents needed to answer the question; do not copy every option.",
            "Do not output identity fields, dates, source types, budgets, request IDs, citations, evidence, facts, conclusions or prose.",
            "Return one JSON object only, with no Markdown fence or commentary.",
        ],
    }
    return (
        {
            "role": "system",
            "content": (
                "You are a bounded financial research planner. Select only "
                "research atoms from the supplied contract. You do not own facts, "
                "numbers, dates, sources, citations or conclusions."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                contract,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    )


def parse_research_planner_output(content: str) -> dict[str, Any]:
    """Parse exact JSON only; semantic validation remains compile_research_plan."""

    text = str(content or "").strip()
    _require(bool(text), "research_planner_output_empty")
    _require(
        not text.startswith("```") and not text.endswith("```"),
        "research_planner_output_not_exact_json",
    )
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ResearchPlanningError(
            "research_planner_output_json_invalid"
        ) from exc
    _require(isinstance(payload, dict), "research_planner_output_not_object")
    return payload


__all__ = [
    "COMPILED_RESEARCH_PLAN_SCHEMA_VERSION",
    "DeferredPlannerAtom",
    "PLANNER_ATOMS_SCHEMA_VERSION",
    "RESEARCH_OBJECTIVE_DRAFT_SCHEMA_VERSION",
    "RESEARCH_OBJECTIVE_SCHEMA_VERSION",
    "RESEARCH_PLANNING_POLICY_SCHEMA_VERSION",
    "RESEARCH_PLANNING_POLICY_SUCCESSOR_SCHEMA_VERSION",
    "SUPPORTED_RESEARCH_PLANNING_POLICY_SCHEMA_VERSIONS",
    "CompiledResearchPlan",
    "PlannerAtom",
    "ResearchObjective",
    "ResearchObjectiveBudget",
    "ResearchObjectivePeriod",
    "ResearchPlanningError",
    "ResearchPlanningPolicy",
    "compile_research_objective",
    "compile_research_planner_messages",
    "compile_research_plan",
    "load_research_planning_policy",
    "parse_research_planner_output",
]
