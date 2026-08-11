from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field

from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.models import CommandEnvelope, canonical_digest, utc_now
from sec_agent.canonical_runtime.parser_numeric import (
    S3FinancialNumericAndFundamentalPackVersion,
    compile_s3_financial_numeric_and_fundamental_pack,
    consume_s3_financial_numeric_and_fundamental_pack,
)
from sec_agent.canonical_runtime.planning_service import (
    FIN01_S3_PROGRAM_CELL_CONTRACTS,
)
from sec_agent.research_graph_store import (
    S3BoundedGraphDecisionCellPackVersion,
    compile_s3_bounded_graph_decision_cell_pack,
    consume_s3_bounded_graph_decision_cell_pack,
)
from sec_agent.s4_case_runtime import (
    S4CaseEvidenceSlotAlignmentReceipt,
    S4CaseRuntimeBinding,
    S4CaseRuntimeResearchProfileOverlay,
    S4SourceGroundedInputPack,
    compile_s4_case_evidence_role_group_mapping,
    load_s4_source_grounded_input_pack,
)

from .case_service import CasePrincipal, CaseService
from .evidence_service import (
    EvidenceService,
    S3ThreeCellEvidenceRoutePlanVersion,
    consume_s3_three_cell_evidence_route_plan,
)
from .execution_service import (
    AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE,
    BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
    VT1_WORK_UNIT_TYPE,
    predict_work_unit_id,
)
from .local_research_service import P36LocalResearchService
from .bounded_agent_contract_policies import (
    ProfileAwareArtifactLineageError,
    validate_profile_aware_artifact_lineage_projection,
)
from .bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    BOUNDED_AGENT_PROFILE_REF,
    BOUNDED_AGENT_WORKER_REF,
    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
    S3_THREE_CELL_BOUNDED_AGENT_WORKER_REF,
    BoundedAgentAdmission,
    BoundedAgentExecutionError,
    BoundedAgentExecutorPort,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutorPort,
    S3ThreeCellBoundedAgentInputPack,
    build_s3_post_provider_failure_error,
    build_bounded_agent_input_pack,
    build_s4_source_grounded_bounded_agent_input,
    build_s3_three_cell_bounded_agent_input_pack,
    resolve_s4_case_runtime_binding_for_admission,
)


FIN01_DETERMINISTIC_PROFILE_REF = "fin01.execution_profile.p36_local_deterministic:v1"
FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF = "fin01.execution_profile.agent_fixture_shadow:v1"
FIN01_DETERMINISTIC_WORKER_REF = "fin01.runtime.local_deterministic.v1"
FIN01_AGENT_FIXTURE_SHADOW_WORKER_REF = "fin01.runtime.agent_fixture_shadow.v1"
FIN01_DETERMINISTIC_ARTIFACT_TYPE = "deterministic_research_result"
FIN01_AGENT_FIXTURE_SHADOW_ARTIFACT_TYPE = "agent_fixture_shadow_result"
FIN01_AGENT_FIXTURE_EVIDENCE_ARTIFACT_TYPE = "agent_fixture_evidence"
FIN01_AGENT_FIXTURE_NUMERIC_ARTIFACT_TYPE = "agent_fixture_numeric"
FIN01_AGENT_FIXTURE_JUDGMENT_ARTIFACT_TYPE = "agent_fixture_judgment"
FIN01_AGENT_FIXTURE_WORKPAPER_ARTIFACT_TYPE = "agent_fixture_workpaper"
FIN01_AGENT_FIXTURE_REPORT_ARTIFACT_TYPE = "agent_fixture_report"
FIN01_AGENT_FIXTURE_TRACE_ARTIFACT_TYPE = "agent_fixture_trace"
FIN01_S3_WORKPAPER_ARTIFACT_TYPE = "s3_three_cell_workpaper"
FIN01_S3_REPORT_ARTIFACT_TYPE = "s3_three_cell_report"
FIN01_S3_TRACE_REVIEW_ARTIFACT_TYPE = "s3_three_cell_trace_review"
FIN01_S3_RUNTIME_PLAN_CONTRACT_REF = "fin01.s3.runtime_plan_three_cell:v1"
FIN01_S4_DETERMINISTIC_BASELINE_CONTRACT_REF = (
    "fin01.s4.source_grounded_deterministic_baseline:v1"
)
FIN01_S3_RUNTIME_FAMILY_REF = (
    "apps.workbench.backend.application.research_runtime:Fin01ResearchRuntime"
)
_BOUNDED_AGENT_PROFILE_REFS = frozenset(
    (BOUNDED_AGENT_PROFILE_REF, S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF)
)

_AGENT_FIXTURE_CELL_ARTIFACT_TYPES = (
    FIN01_AGENT_FIXTURE_EVIDENCE_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_NUMERIC_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_JUDGMENT_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_WORKPAPER_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_REPORT_ARTIFACT_TYPE,
    FIN01_AGENT_FIXTURE_TRACE_ARTIFACT_TYPE,
)

_AGENT_FIXTURE_SHADOW_ACTIVE_AGENT_IDS = (
    "research_lead",
    "universe_relationship",
    "coverage_reflection",
    "industry_supply_chain_analyst",
    "judgment_plan_aggregator",
    "memo_writer",
    "verifier",
    "renderer",
)


def _fin01_artifact_id(research_run_id: str, artifact_type: str) -> str:
    return "artifact_fin01_" + canonical_digest(
        {
            "research_run_id": research_run_id,
            "artifact_type": artifact_type,
        }
    )[:24]


def _replace_exact_artifact_refs(value: Any, replacements: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return replacements.get(value, value)
    if isinstance(value, Mapping):
        return {
            str(key): _replace_exact_artifact_refs(item, replacements)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_exact_artifact_refs(item, replacements) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_exact_artifact_refs(item, replacements) for item in value)
    return value


class ExecutionProfileVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_profile_id: str
    execution_profile_version: int
    execution_profile_version_ref: str
    work_unit_type: str
    execution_mode: str
    worker_ref: str
    artifact_type: str
    model_calls_allowed: bool
    network_calls_allowed: bool
    external_tool_calls_allowed: bool
    direct_canonical_writes_allowed: bool
    model_ref: str | None = None
    tool_refs: tuple[str, ...] = ()


class S3CellBranchObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_type: Literal[
        "no_runtime_observation",
        "candidate_available_not_evidence",
        "accepted_evidence_available",
        "route_exhausted",
        "material_counterevidence_available",
        "decision_surface_revision_required",
    ]
    refs: tuple[str, ...] = ()
    rationale: str


class S3CellBranchPlanVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    program_cell_id: str
    legacy_cell_key: str
    evidence_role: str
    owner_role: str
    decision_question: str
    mandatory_judgment_chain: str
    stop_rule: str
    what_would_change: str
    cell_version_ref: str
    branch_version_ref: str
    research_run_id: str
    observation: S3CellBranchObservation
    lead_branch_decision: Literal[
        "continue_to_evidence_request",
        "continue_to_specialist",
        "continue_to_specialist_counterevidence_first",
        "typed_stop_cannot_infer",
        "stop_for_human_decision_surface_revision",
    ]
    branch_state: Literal["planned", "active", "stopped"]
    terminal_reason: str | None = None


class S3ContextSelectionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context_ref: str
    decision: Literal["selected", "dropped"]
    reason: str


class S3RoleContextPlanVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context_plan_id: str
    context_plan_version_ref: str
    target_node: Literal[
        "research_lead",
        "domain_specialist",
        "evidence_operator",
        "memo_writer",
        "verifier",
    ]
    program_cell_id: str | None = None
    case_id: str
    research_run_id: str
    decision_surface_contract_ref: str
    dependency_refs: tuple[str, ...]
    selection_decisions: tuple[S3ContextSelectionDecision, ...]
    context_payload: dict[str, Any]
    authority: dict[str, bool]
    context_input_digest: str


class S3ThreeCellRuntimePlanVersion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    runtime_plan_id: str
    runtime_plan_version_ref: str
    runtime_plan_contract_ref: str = FIN01_S3_RUNTIME_PLAN_CONTRACT_REF
    runtime_family_ref: str = FIN01_S3_RUNTIME_FAMILY_REF
    case_id: str
    work_unit_id: str
    attempt_id: str
    research_run_id: str
    execution_profile_version_ref: str
    decision_surface_contract_ref: str
    cell_branches: tuple[S3CellBranchPlanVersion, ...]
    role_context_plans: tuple[S3RoleContextPlanVersion, ...]
    s4_evidence_role_group_mapping_ref: str | None = None
    s4_evidence_role_group_mapping_digest: str | None = None
    runtime_plan_digest: str
    model_calls: int = 0
    provider_calls: int = 0
    network_calls: int = 0
    external_tool_calls: int = 0
    canonical_business_writes: int = 0


class ProfileExecutionContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    case_query: str
    work_unit_id: str
    attempt_id: str
    research_run_id: str
    causation_event_id: str
    execution_profile_version_ref: str
    s3_runtime_plan: S3ThreeCellRuntimePlanVersion
    s3_evidence_route_plan: S3ThreeCellEvidenceRoutePlanVersion | None = None
    s4_evidence_slot_alignment: (
        S4CaseEvidenceSlotAlignmentReceipt | None
    ) = None
    evidence_dispatch_digest: str


class ProfileEvidenceDispatch(BaseModel):
    """Mutually exclusive legacy-S3 or S4 evidence alignment dispatch."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dispatch_mode: Literal["legacy_s3_fixture_routes", "s4_case_role_alignment"]
    runtime_plan: S3ThreeCellRuntimePlanVersion
    s3_evidence_route_plan: S3ThreeCellEvidenceRoutePlanVersion | None = None
    s4_evidence_slot_alignment: (
        S4CaseEvidenceSlotAlignmentReceipt | None
    ) = None
    role_group_mapping_digest: str | None = None
    evidence_dispatch_digest: str


class ProfileExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution_profile_version_ref: str
    case_id: str
    artifact_type: str
    payload: dict[str, Any]
    artifacts: tuple["ProfileArtifactResult", ...] = ()
    trace_events: tuple[dict[str, Any], ...] = ()
    provider_output_captures: tuple[dict[str, Any], ...] = ()
    execution_observation: dict[str, Any] = Field(default_factory=dict)
    terminal_reason: str = "completed"


class ProfileArtifactResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_type: str
    payload: dict[str, Any]


def _s3_branch_decision(
    observation: S3CellBranchObservation,
) -> tuple[str, str, str | None]:
    if observation.observation_type in {
        "no_runtime_observation",
        "candidate_available_not_evidence",
    }:
        return "continue_to_evidence_request", "planned", None
    if observation.observation_type == "accepted_evidence_available":
        return "continue_to_specialist", "active", None
    if observation.observation_type == "material_counterevidence_available":
        return "continue_to_specialist_counterevidence_first", "active", None
    if observation.observation_type == "route_exhausted":
        return (
            "typed_stop_cannot_infer",
            "stopped",
            "route_exhausted_without_required_authoritative_evidence",
        )
    return (
        "stop_for_human_decision_surface_revision",
        "stopped",
        "decision_surface_revision_requires_human_versioned_authority",
    )


def _s3_context_plan(
    *,
    target_node: str,
    program_cell_id: str | None,
    case_id: str,
    research_run_id: str,
    decision_surface_contract_ref: str,
    dependency_refs: tuple[str, ...],
    selected_refs: tuple[str, ...],
    dropped_categories: tuple[str, ...],
    context_payload: Mapping[str, Any],
    authority: Mapping[str, bool],
) -> S3RoleContextPlanVersion:
    selection_decisions = tuple(
        S3ContextSelectionDecision(
            context_ref=ref,
            decision="selected",
            reason=f"required_by_{target_node}_contract",
        )
        for ref in selected_refs
    ) + tuple(
        S3ContextSelectionDecision(
            context_ref=category,
            decision="dropped",
            reason=f"forbidden_or_unnecessary_for_{target_node}",
        )
        for category in dropped_categories
    )
    digest_payload = {
        "target_node": target_node,
        "program_cell_id": program_cell_id,
        "case_id": case_id,
        "research_run_id": research_run_id,
        "decision_surface_contract_ref": decision_surface_contract_ref,
        "dependency_refs": dependency_refs,
        "selection_decisions": [row.model_dump(mode="json") for row in selection_decisions],
        "context_payload": dict(context_payload),
        "authority": dict(authority),
    }
    digest = canonical_digest(digest_payload)
    context_plan_id = f"context_plan_fin01_s3_{digest[:24]}"
    return S3RoleContextPlanVersion(
        context_plan_id=context_plan_id,
        context_plan_version_ref=f"{context_plan_id}:v1",
        target_node=target_node,
        program_cell_id=program_cell_id,
        case_id=case_id,
        research_run_id=research_run_id,
        decision_surface_contract_ref=decision_surface_contract_ref,
        dependency_refs=dependency_refs,
        selection_decisions=selection_decisions,
        context_payload=dict(context_payload),
        authority=dict(authority),
        context_input_digest=digest,
    )


def compile_fin01_s3_three_cell_runtime_plan(
    *,
    case_id: str,
    work_unit_id: str,
    attempt_id: str,
    research_run_id: str,
    execution_profile_version_ref: str,
    decision_surface_contract_ref: str,
    observations: Mapping[str, S3CellBranchObservation | Mapping[str, Any]] | None = None,
) -> S3ThreeCellRuntimePlanVersion:
    """Compile one immutable three-cell plan without model, network, tool or business writes."""

    if not all(
        value.strip()
        for value in (
            case_id,
            work_unit_id,
            attempt_id,
            research_run_id,
            execution_profile_version_ref,
            decision_surface_contract_ref,
        )
    ):
        raise ValueError("s3_runtime_plan_identity_required")
    observations = observations or {}
    allowed_cell_ids = {
        row.program_cell_id for row in FIN01_S3_PROGRAM_CELL_CONTRACTS
    }
    if set(observations) - allowed_cell_ids:
        raise ValueError("s3_runtime_plan_unknown_cell_observation")
    branches: list[S3CellBranchPlanVersion] = []
    for cell in FIN01_S3_PROGRAM_CELL_CONTRACTS:
        raw_observation = observations.get(cell.program_cell_id)
        observation = (
            S3CellBranchObservation.model_validate(raw_observation)
            if raw_observation is not None
            else S3CellBranchObservation(
                observation_type="no_runtime_observation",
                rationale="T02 contract has no EvidenceRequest or accepted Evidence yet.",
            )
        )
        decision, branch_state, terminal_reason = _s3_branch_decision(observation)
        cell_id = "cell_fin01_s3_" + canonical_digest(
            (decision_surface_contract_ref, cell.program_cell_id)
        )[:24]
        branch_id = "branch_fin01_s3_" + canonical_digest(
            (research_run_id, cell_id, observation.model_dump(mode="json"))
        )[:24]
        branches.append(
            S3CellBranchPlanVersion(
                **cell.model_dump(mode="json"),
                cell_version_ref=f"{cell_id}:v1",
                branch_version_ref=f"{branch_id}:v1",
                research_run_id=research_run_id,
                observation=observation,
                lead_branch_decision=decision,
                branch_state=branch_state,
                terminal_reason=terminal_reason,
            )
        )

    branch_refs = tuple(row.branch_version_ref for row in branches)
    common_refs = (decision_surface_contract_ref, *branch_refs)
    context_plans: list[S3RoleContextPlanVersion] = []
    context_plans.append(
        _s3_context_plan(
            target_node="research_lead",
            program_cell_id=None,
            case_id=case_id,
            research_run_id=research_run_id,
            decision_surface_contract_ref=decision_surface_contract_ref,
            dependency_refs=common_refs,
            selected_refs=common_refs,
            dropped_categories=("all_raw_rows", "specialist_private_drafts"),
            context_payload={
                "case_objective_ref": decision_surface_contract_ref,
                "branch_summaries": [
                    {
                        "program_cell_id": row.program_cell_id,
                        "branch_version_ref": row.branch_version_ref,
                        "lead_branch_decision": row.lead_branch_decision,
                        "branch_state": row.branch_state,
                    }
                    for row in branches
                ],
                "cross_cell_dependency_refs": list(branch_refs),
            },
            authority={
                "may_create_evidence_request": True,
                "may_adjudicate_cross_cell": True,
                "may_promote_evidence": False,
                "may_write_report": False,
                "may_mutate_case": False,
            },
        )
    )
    for branch in branches:
        cell_refs = (decision_surface_contract_ref, branch.branch_version_ref)
        context_plans.append(
            _s3_context_plan(
                target_node="domain_specialist",
                program_cell_id=branch.program_cell_id,
                case_id=case_id,
                research_run_id=research_run_id,
                decision_surface_contract_ref=decision_surface_contract_ref,
                dependency_refs=cell_refs,
                selected_refs=cell_refs,
                dropped_categories=("unrelated_cell_raw_rows", "other_specialist_private_context"),
                context_payload={
                    "branch_version_ref": branch.branch_version_ref,
                    "decision_question": branch.decision_question,
                    "mandatory_judgment_chain": branch.mandatory_judgment_chain,
                    "evidence_role": branch.evidence_role,
                    "stop_rule": branch.stop_rule,
                    "what_would_change": branch.what_would_change,
                    "accepted_evidence_refs": [],
                    "numeric_refs": [],
                    "typed_gap_refs": [],
                },
                authority={
                    "may_request_evidence": True,
                    "may_form_cell_judgment": True,
                    "may_search_privately": False,
                    "may_promote_evidence": False,
                    "may_mutate_case": False,
                },
            )
        )
        context_plans.append(
            _s3_context_plan(
                target_node="evidence_operator",
                program_cell_id=branch.program_cell_id,
                case_id=case_id,
                research_run_id=research_run_id,
                decision_surface_contract_ref=decision_surface_contract_ref,
                dependency_refs=cell_refs,
                selected_refs=cell_refs,
                dropped_categories=("expected_conclusion", "final_judgment", "unrelated_thesis_narrative"),
                context_payload={
                    "branch_version_ref": branch.branch_version_ref,
                    "evidence_role": branch.evidence_role,
                    "decision_question": branch.decision_question,
                    "source_policy": "unbound_until_S3_T03",
                    "acceptance_criteria": "unbound_until_S3_T03",
                },
                authority={
                    "may_execute_local_route": False,
                    "may_use_source_network": False,
                    "may_promote_evidence": False,
                    "may_form_final_judgment": False,
                    "may_mutate_case": False,
                },
            )
        )
    context_plans.extend(
        (
            _s3_context_plan(
                target_node="memo_writer",
                program_cell_id=None,
                case_id=case_id,
                research_run_id=research_run_id,
                decision_surface_contract_ref=decision_surface_contract_ref,
                dependency_refs=common_refs,
                selected_refs=common_refs,
                dropped_categories=("raw_candidates", "retrieval_tools", "private_reasoning"),
                context_payload={
                    "adjudicated_judgment_refs": [],
                    "what_would_change_by_cell": {
                        row.program_cell_id: row.what_would_change for row in branches
                    },
                    "writer_brief_status": "unbound_until_S3_T07",
                },
                authority={
                    "may_write_report": False,
                    "may_retrieve_sources": False,
                    "may_use_tools": False,
                    "may_promote_evidence": False,
                    "may_mutate_case": False,
                },
            ),
            _s3_context_plan(
                target_node="verifier",
                program_cell_id=None,
                case_id=case_id,
                research_run_id=research_run_id,
                decision_surface_contract_ref=decision_surface_contract_ref,
                dependency_refs=common_refs,
                selected_refs=common_refs,
                dropped_categories=("new_retrieval_authority", "evidence_write_authority", "judgment_write_authority"),
                context_payload={
                    "draft_ref": None,
                    "claim_evidence_numeric_refs": [],
                    "forbidden_claims": [
                        "candidate_as_evidence",
                        "graph_edge_as_fact",
                        "unsupported_numeric_precision",
                    ],
                    "authorized_drilldown": "exact_refs_only",
                },
                authority={
                    "may_verify": True,
                    "may_request_targeted_repair": True,
                    "may_retrieve_sources": False,
                    "may_promote_evidence": False,
                    "may_mutate_case": False,
                },
            ),
        )
    )
    payload = {
        "runtime_plan_contract_ref": FIN01_S3_RUNTIME_PLAN_CONTRACT_REF,
        "runtime_family_ref": FIN01_S3_RUNTIME_FAMILY_REF,
        "case_id": case_id,
        "work_unit_id": work_unit_id,
        "attempt_id": attempt_id,
        "research_run_id": research_run_id,
        "execution_profile_version_ref": execution_profile_version_ref,
        "decision_surface_contract_ref": decision_surface_contract_ref,
        "cell_branches": [row.model_dump(mode="json") for row in branches],
        "role_context_plans": [row.model_dump(mode="json") for row in context_plans],
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "external_tool_calls": 0,
        "canonical_business_writes": 0,
    }
    digest = canonical_digest(payload)
    runtime_plan_id = f"runtime_plan_fin01_s3_{digest[:24]}"
    return S3ThreeCellRuntimePlanVersion(
        runtime_plan_id=runtime_plan_id,
        runtime_plan_version_ref=f"{runtime_plan_id}:v1",
        case_id=case_id,
        work_unit_id=work_unit_id,
        attempt_id=attempt_id,
        research_run_id=research_run_id,
        execution_profile_version_ref=execution_profile_version_ref,
        decision_surface_contract_ref=decision_surface_contract_ref,
        cell_branches=tuple(branches),
        role_context_plans=tuple(context_plans),
        runtime_plan_digest=digest,
    )


def _runtime_plan_digest_payload(
    plan: S3ThreeCellRuntimePlanVersion,
) -> dict[str, Any]:
    payload = {
        "runtime_plan_contract_ref": plan.runtime_plan_contract_ref,
        "runtime_family_ref": plan.runtime_family_ref,
        "case_id": plan.case_id,
        "work_unit_id": plan.work_unit_id,
        "attempt_id": plan.attempt_id,
        "research_run_id": plan.research_run_id,
        "execution_profile_version_ref": plan.execution_profile_version_ref,
        "decision_surface_contract_ref": plan.decision_surface_contract_ref,
        "cell_branches": [
            row.model_dump(mode="json") for row in plan.cell_branches
        ],
        "role_context_plans": [
            row.model_dump(mode="json") for row in plan.role_context_plans
        ],
        "model_calls": plan.model_calls,
        "provider_calls": plan.provider_calls,
        "network_calls": plan.network_calls,
        "external_tool_calls": plan.external_tool_calls,
        "canonical_business_writes": plan.canonical_business_writes,
    }
    if plan.s4_evidence_role_group_mapping_ref is not None:
        payload["s4_evidence_role_group_mapping_ref"] = (
            plan.s4_evidence_role_group_mapping_ref
        )
        payload["s4_evidence_role_group_mapping_digest"] = (
            plan.s4_evidence_role_group_mapping_digest
        )
    return payload


def bind_s4_evidence_role_groups_to_runtime_plan(
    plan: S3ThreeCellRuntimePlanVersion,
    binding: S4CaseRuntimeBinding,
) -> S3ThreeCellRuntimePlanVersion:
    """Bind the derived case-role contract while preserving one Runtime family."""

    mapping = compile_s4_case_evidence_role_group_mapping(binding)
    branches = {row.program_cell_id: row for row in plan.cell_branches}
    if set(branches) != set(binding.program_cell_ids):
        raise ValueError("s4_runtime_plan_program_cell_axis_mismatch")
    if any(
        branches[group.program_cell_id].owner_role != group.owner_role
        for group in mapping.role_groups
    ):
        raise ValueError("s4_runtime_plan_role_group_owner_mismatch")
    if (
        plan.s4_evidence_role_group_mapping_ref is not None
        and (
            plan.s4_evidence_role_group_mapping_ref != mapping.contract_ref
            or plan.s4_evidence_role_group_mapping_digest
            != mapping.role_group_mapping_digest
        )
    ):
        raise ValueError("s4_runtime_plan_role_group_digest_mismatch")
    draft = plan.model_copy(
        update={
            "s4_evidence_role_group_mapping_ref": mapping.contract_ref,
            "s4_evidence_role_group_mapping_digest": (
                mapping.role_group_mapping_digest
            ),
        }
    )
    digest = canonical_digest(_runtime_plan_digest_payload(draft))
    runtime_plan_id = f"runtime_plan_fin01_s3_{digest[:24]}"
    return draft.model_copy(
        update={
            "runtime_plan_id": runtime_plan_id,
            "runtime_plan_version_ref": f"{runtime_plan_id}:v1",
            "runtime_plan_digest": digest,
        }
    )


def compile_profile_evidence_dispatch(
    evidence_service: EvidenceService,
    *,
    runtime_plan: S3ThreeCellRuntimePlanVersion,
    principal: CasePrincipal,
    s4_binding: S4CaseRuntimeBinding | None = None,
    prospective_execution_lineage: bool = False,
) -> ProfileEvidenceDispatch:
    """Shared actual-Runtime and exact-preflight evidence-plan dispatcher."""

    if s4_binding is None:
        route_plan = (
            evidence_service.compile_s3_three_cell_preflight_evidence_plan(
                runtime_plan=runtime_plan.model_dump(mode="json"),
                principal=principal,
            )
            if prospective_execution_lineage
            else evidence_service.compile_s3_three_cell_runtime_evidence_plan(
                runtime_plan=runtime_plan.model_dump(mode="json"),
                principal=principal,
            )
        )
        payload = {
            "dispatch_mode": "legacy_s3_fixture_routes",
            "runtime_plan_digest": runtime_plan.runtime_plan_digest,
            "s3_evidence_route_plan_digest": (
                route_plan.evidence_route_plan_digest
            ),
            "s4_evidence_slot_alignment_digest": None,
            "role_group_mapping_digest": None,
        }
        return ProfileEvidenceDispatch(
            dispatch_mode="legacy_s3_fixture_routes",
            runtime_plan=runtime_plan,
            s3_evidence_route_plan=route_plan,
            role_group_mapping_digest=None,
            evidence_dispatch_digest=canonical_digest(payload),
        )

    bound_plan = bind_s4_evidence_role_groups_to_runtime_plan(
        runtime_plan, s4_binding
    )
    alignment = evidence_service.compile_s4_case_evidence_slot_alignment(
        runtime_plan=bound_plan.model_dump(mode="json"),
        binding=s4_binding,
        principal=principal,
        _allow_prospective_execution_lineage=prospective_execution_lineage,
    )
    payload = {
        "dispatch_mode": "s4_case_role_alignment",
        "runtime_plan_digest": bound_plan.runtime_plan_digest,
        "s3_evidence_route_plan_digest": None,
        "s4_evidence_slot_alignment_digest": alignment.alignment_digest,
        "role_group_mapping_digest": (
            bound_plan.s4_evidence_role_group_mapping_digest
        ),
    }
    return ProfileEvidenceDispatch(
        dispatch_mode="s4_case_role_alignment",
        runtime_plan=bound_plan,
        s4_evidence_slot_alignment=alignment,
        role_group_mapping_digest=(
            bound_plan.s4_evidence_role_group_mapping_digest
        ),
        evidence_dispatch_digest=canonical_digest(payload),
    )


def consume_fin01_s3_role_context_plans(
    plan: S3ThreeCellRuntimePlanVersion,
) -> tuple[dict[str, Any], ...]:
    """Deterministically prove node-scoped context consumption without invoking nodes."""

    plan_digest_payload = _runtime_plan_digest_payload(plan)
    if canonical_digest(plan_digest_payload) != plan.runtime_plan_digest:
        raise ValueError("s3_runtime_plan_digest_mismatch")
    expected_plan_id = f"runtime_plan_fin01_s3_{plan.runtime_plan_digest[:24]}"
    if (
        plan.runtime_plan_id != expected_plan_id
        or plan.runtime_plan_version_ref != f"{expected_plan_id}:v1"
    ):
        raise ValueError("s3_runtime_plan_identity_mismatch")
    expected = {
        "research_lead": 1,
        "domain_specialist": 3,
        "evidence_operator": 3,
        "memo_writer": 1,
        "verifier": 1,
    }
    observed = {
        node: sum(1 for row in plan.role_context_plans if row.target_node == node)
        for node in expected
    }
    if observed != expected:
        raise ValueError("s3_role_context_plan_cardinality_invalid")
    receipts = []
    for row in plan.role_context_plans:
        if row.case_id != plan.case_id or row.research_run_id != plan.research_run_id:
            raise ValueError("s3_role_context_plan_scope_mismatch")
        if not row.context_payload or not row.selection_decisions:
            raise ValueError("s3_role_context_plan_not_reconstructable")
        context_digest_payload = {
            "target_node": row.target_node,
            "program_cell_id": row.program_cell_id,
            "case_id": row.case_id,
            "research_run_id": row.research_run_id,
            "decision_surface_contract_ref": row.decision_surface_contract_ref,
            "dependency_refs": row.dependency_refs,
            "selection_decisions": [
                decision.model_dump(mode="json")
                for decision in row.selection_decisions
            ],
            "context_payload": row.context_payload,
            "authority": row.authority,
        }
        if canonical_digest(context_digest_payload) != row.context_input_digest:
            raise ValueError("s3_role_context_plan_digest_mismatch")
        expected_context_plan_id = (
            f"context_plan_fin01_s3_{row.context_input_digest[:24]}"
        )
        if (
            row.context_plan_id != expected_context_plan_id
            or row.context_plan_version_ref != f"{expected_context_plan_id}:v1"
        ):
            raise ValueError("s3_role_context_plan_identity_mismatch")
        receipts.append(
            {
                "target_node": row.target_node,
                "program_cell_id": row.program_cell_id,
                "context_plan_version_ref": row.context_plan_version_ref,
                "context_input_digest": row.context_input_digest,
                "consumption_mode": "deterministic_node_contract_validation",
                "model_calls": 0,
                "network_calls": 0,
            }
        )
    return tuple(receipts)


class _DeterministicP36Adapter:
    def __init__(
        self,
        service: P36LocalResearchService,
        profile: ExecutionProfileVersion,
        *,
        s4_binding: S4CaseRuntimeBinding | None = None,
        s4_source_pack: S4SourceGroundedInputPack | None = None,
        s4_research_profile_overlay: (
            S4CaseRuntimeResearchProfileOverlay | None
        ) = None,
    ):
        if (s4_binding is None) != (s4_source_pack is None):
            raise ValueError(
                "s4_deterministic_binding_and_source_pack_must_be_paired"
            )
        if s4_research_profile_overlay is not None and s4_binding is None:
            raise ValueError(
                "s4_deterministic_overlay_requires_binding"
            )
        self._service = service
        self.profile = profile
        self.s4_binding = s4_binding
        self._s4_source_pack = s4_source_pack
        self._s4_research_profile_overlay = (
            s4_research_profile_overlay
        )

    def execute(
        self,
        context: ProfileExecutionContext,
        principal: CasePrincipal,
    ) -> ProfileExecutionResult:
        if self.s4_binding is not None:
            return self._execute_s4_source_grounded(
                context,
                principal,
            )
        if context.s3_evidence_route_plan is None:
            raise ValueError("s3_evidence_route_plan_required_for_deterministic_profile")
        preview = self._service.analysis_preview(context.case_id, principal)
        financial_pack = compile_s3_financial_numeric_and_fundamental_pack(
            runtime_plan=context.s3_runtime_plan.model_dump(mode="json"),
            evidence_route_plan=context.s3_evidence_route_plan.model_dump(mode="json"),
            numeric_preview=preview["numeric"],
        )
        graph_pack = compile_s3_bounded_graph_decision_cell_pack(
            runtime_plan=context.s3_runtime_plan.model_dump(mode="json"),
            evidence_route_plan=context.s3_evidence_route_plan.model_dump(mode="json"),
            financial_pack=financial_pack.model_dump(mode="json"),
            analysis_preview=preview,
        )
        from sec_agent.langgraph_orchestrator import (
            compile_s3_specialist_lead_cross_cell_pack,
            consume_s3_specialist_lead_cross_cell_pack,
        )

        judgment_pack = compile_s3_specialist_lead_cross_cell_pack(
            runtime_plan=context.s3_runtime_plan.model_dump(mode="json"),
            evidence_route_plan=context.s3_evidence_route_plan.model_dump(mode="json"),
            financial_pack=financial_pack.model_dump(mode="json"),
            graph_pack=graph_pack.model_dump(mode="json"),
        )
        from sec_agent.memo_llm import (
            compile_s3_three_cell_presentation_pack,
            consume_s3_three_cell_presentation_pack,
            s3_presentation_artifact_payloads,
        )

        presentation_pack = compile_s3_three_cell_presentation_pack(
            runtime_plan=context.s3_runtime_plan.model_dump(mode="json"),
            evidence_route_plan=context.s3_evidence_route_plan.model_dump(
                mode="json"
            ),
            financial_pack=financial_pack.model_dump(mode="json"),
            graph_pack=graph_pack.model_dump(mode="json"),
            judgment_pack=judgment_pack.model_dump(mode="json"),
            artifact_refs={
                "workpaper": (
                    f"{_fin01_artifact_id(context.research_run_id, FIN01_S3_WORKPAPER_ARTIFACT_TYPE)}:v1"
                ),
                "report": (
                    f"{_fin01_artifact_id(context.research_run_id, FIN01_S3_REPORT_ARTIFACT_TYPE)}:v1"
                ),
                "trace": (
                    f"{_fin01_artifact_id(context.research_run_id, FIN01_S3_TRACE_REVIEW_ARTIFACT_TYPE)}:v1"
                ),
            },
        )
        payload = {
            "execution_profile_version_ref": self.profile.execution_profile_version_ref,
            "execution_mode": self.profile.execution_mode,
            "case_id": context.case_id,
            "result": preview,
            "s3_runtime_plan": context.s3_runtime_plan.model_dump(mode="json"),
            "s3_context_consumption_receipts": list(
                consume_fin01_s3_role_context_plans(context.s3_runtime_plan)
            ),
            "s3_evidence_route_plan": context.s3_evidence_route_plan.model_dump(
                mode="json"
            ),
            "s3_evidence_route_consumption_receipts": list(
                consume_s3_three_cell_evidence_route_plan(
                    context.s3_evidence_route_plan,
                    runtime_plan_version_ref=(
                        context.s3_runtime_plan.runtime_plan_version_ref
                    ),
                    runtime_plan_digest=context.s3_runtime_plan.runtime_plan_digest,
                )
            ),
            "s3_financial_numeric_and_fundamental_pack": financial_pack.model_dump(
                mode="json"
            ),
            "s3_financial_numeric_consumption_receipts": list(
                consume_s3_financial_numeric_and_fundamental_pack(
                    financial_pack,
                    runtime_plan_version_ref=(
                        context.s3_runtime_plan.runtime_plan_version_ref
                    ),
                    runtime_plan_digest=context.s3_runtime_plan.runtime_plan_digest,
                    evidence_route_plan=context.s3_evidence_route_plan.model_dump(
                        mode="json"
                    ),
                )
            ),
            "s3_bounded_graph_product_market_risk_pack": graph_pack.model_dump(
                mode="json"
            ),
            "s3_bounded_graph_consumption_receipts": list(
                consume_s3_bounded_graph_decision_cell_pack(
                    graph_pack,
                    runtime_plan=context.s3_runtime_plan.model_dump(mode="json"),
                    evidence_route_plan=context.s3_evidence_route_plan.model_dump(
                        mode="json"
                    ),
                    financial_pack=financial_pack.model_dump(mode="json"),
                    analysis_preview=preview,
                )
            ),
            "s3_specialist_lead_cross_cell_pack": judgment_pack.model_dump(
                mode="json"
            ),
            "s3_specialist_lead_consumption_receipts": list(
                consume_s3_specialist_lead_cross_cell_pack(
                    judgment_pack,
                    runtime_plan=context.s3_runtime_plan.model_dump(mode="json"),
                    evidence_route_plan=context.s3_evidence_route_plan.model_dump(
                        mode="json"
                    ),
                    financial_pack=financial_pack.model_dump(mode="json"),
                    graph_pack=graph_pack.model_dump(mode="json"),
                )
            ),
            "s3_three_cell_presentation_pack": presentation_pack.model_dump(
                mode="json"
            ),
            "s3_presentation_consumption_receipts": list(
                consume_s3_three_cell_presentation_pack(
                    presentation_pack,
                    runtime_plan=context.s3_runtime_plan.model_dump(mode="json"),
                    evidence_route_plan=context.s3_evidence_route_plan.model_dump(
                        mode="json"
                    ),
                    financial_pack=financial_pack.model_dump(mode="json"),
                    graph_pack=graph_pack.model_dump(mode="json"),
                    judgment_pack=judgment_pack.model_dump(mode="json"),
                )
            ),
            "adapter_direct_canonical_writes": 0,
        }
        return ProfileExecutionResult(
            execution_profile_version_ref=self.profile.execution_profile_version_ref,
            case_id=context.case_id,
            artifact_type=self.profile.artifact_type,
            payload=payload,
            artifacts=tuple(
                ProfileArtifactResult(artifact_type=artifact_type, payload=row)
                for artifact_type, row in s3_presentation_artifact_payloads(
                    presentation_pack
                )
            ),
        )

    def _execute_s4_source_grounded(
        self,
        context: ProfileExecutionContext,
        principal: CasePrincipal,
    ) -> ProfileExecutionResult:
        """Compose the case-local zero-model comparison floor from frozen S4 inputs."""

        binding = self.s4_binding
        source_pack = self._s4_source_pack
        alignment = context.s4_evidence_slot_alignment
        if (
            binding is None
            or source_pack is None
            or alignment is None
            or context.s3_evidence_route_plan is not None
            or context.s3_runtime_plan.s4_evidence_role_group_mapping_digest
            is None
        ):
            raise ValueError("s4_deterministic_evidence_alignment_required")
        case = self._service._case_service.get_case(
            context.case_id,
            principal,
        )
        input_pack = build_s4_source_grounded_bounded_agent_input(
            binding,
            source_pack,
            case_id=context.case_id,
            decision_surface_contract_ref=(
                context.s3_runtime_plan.decision_surface_contract_ref
            ),
            case_version=int(case["case_version"]),
            query=context.case_query,
            research_profile_overlay=(
                self._s4_research_profile_overlay
            ),
        )
        cells: list[dict[str, Any]] = []
        for cell in input_pack.cell_inputs:
            cell_id = str(cell["program_cell_id"])
            branch = dict(cell["runtime_branch"])
            evidence = list(
                cell["evidence_input"]["candidate_bundle"]["candidates"]
            )
            numeric = list(
                cell["numeric_input"]["selected_financial_rows"]
            )
            derived = list(cell["numeric_input"]["derived_metrics"])
            typed_gaps = list(
                cell["numeric_input"]["fundamental_decision_cell"][
                    "typed_cannot_infer"
                ]
            )
            accepted_refs = list(
                cell["authority_refs"]["accepted_evidence_refs"]
            )
            numeric_refs = list(cell["authority_refs"]["numeric_refs"])
            graph_refs = list(
                cell["authority_refs"]["graph_context_refs_not_evidence"]
            )
            cells.append(
                {
                    "program_cell_id": cell_id,
                    "decision_question": branch["decision_question"],
                    "accepted_evidence_refs": accepted_refs,
                    "numeric_refs": numeric_refs,
                    "graph_context_refs_not_evidence": graph_refs,
                    "typed_gap_codes": typed_gaps,
                    "evidence_rows": evidence,
                    "numeric_rows": numeric,
                    "derived_metrics": derived,
                    "deterministic_boundary_statement": (
                        f"{binding.case_ticker} {cell_id}: "
                        f"{len(accepted_refs)} issuer-bound evidence rows, "
                        f"{len(numeric_refs)} exact numeric rows, "
                        f"{len(graph_refs)} context-only graph rows, and "
                        f"{len(typed_gaps)} retained typed gaps. "
                        "No causal or forward-looking judgment is inferred."
                    ),
                }
            )
        result_core = {
            "case_id": context.case_id,
            "case_version": int(case["case_version"]),
            "as_of": binding.as_of,
            "company": binding.case_ticker,
            "analysis_mode": "s4_source_grounded_deterministic_baseline",
            "status": "internal_analysis_preview_ready",
            "input_digest": input_pack.input_digest,
            "input_head_digest": input_pack.input_head_digest,
            "source_pack_digest": source_pack.source_pack_digest,
            "runtime_binding_digest": binding.runtime_binding_digest,
            "evidence_alignment_digest": alignment.alignment_digest,
            "cells": cells,
            "execution_counts": {
                "model_calls": 0,
                "provider_calls": 0,
                "network_calls": 0,
                "source_network_calls": 0,
                "external_tool_calls": 0,
                "canonical_store_writes": 0,
                "case_mutations": 0,
                "evidence_promotions": 0,
            },
            "hard_boundaries": {
                "case_mutations": 0,
                "canonical_store_writes": 0,
                "evidence_promotions": 0,
                "network_calls": 0,
                "model_calls": 0,
                "release_admission": 0,
                "baseline_body_exposed_to_agent": 0,
            },
            "boundary": (
                "Same-input, issuer-bound deterministic comparison floor. "
                "It is not an Agent output, causal conclusion, human review, "
                "evidence promotion, release admission, or production result."
            ),
        }
        result = {
            **result_core,
            "analysis_digest": canonical_digest(result_core),
        }
        artifact_refs = {
            artifact_type: (
                f"{_fin01_artifact_id(context.research_run_id, artifact_type)}:v1"
            )
            for artifact_type in (
                FIN01_S3_WORKPAPER_ARTIFACT_TYPE,
                FIN01_S3_REPORT_ARTIFACT_TYPE,
                FIN01_S3_TRACE_REVIEW_ARTIFACT_TYPE,
            )
        }
        workpaper = {
            "artifact_ref": artifact_refs[
                FIN01_S3_WORKPAPER_ARTIFACT_TYPE
            ],
            "contract_ref": FIN01_S4_DETERMINISTIC_BASELINE_CONTRACT_REF,
            "case_id": context.case_id,
            "research_run_id": context.research_run_id,
            "input_digest": input_pack.input_digest,
            "cells": cells,
        }
        report = {
            "artifact_ref": artifact_refs[FIN01_S3_REPORT_ARTIFACT_TYPE],
            "contract_ref": FIN01_S4_DETERMINISTIC_BASELINE_CONTRACT_REF,
            "case_id": context.case_id,
            "research_run_id": context.research_run_id,
            "title": (
                f"{binding.case_ticker} source-grounded deterministic baseline"
            ),
            "sections": [
                {
                    "program_cell_id": row["program_cell_id"],
                    "content": row["deterministic_boundary_statement"],
                    "numeric_rows": row["numeric_rows"],
                    "typed_gap_codes": row["typed_gap_codes"],
                }
                for row in cells
            ],
            "source_calls": 0,
            "tool_calls": 0,
            "model_calls": 0,
        }
        trace_review = {
            "artifact_ref": artifact_refs[
                FIN01_S3_TRACE_REVIEW_ARTIFACT_TYPE
            ],
            "contract_ref": FIN01_S4_DETERMINISTIC_BASELINE_CONTRACT_REF,
            "case_id": context.case_id,
            "research_run_id": context.research_run_id,
            "input_digest": input_pack.input_digest,
            "input_head_digest": input_pack.input_head_digest,
            "runtime_plan_digest": (
                context.s3_runtime_plan.runtime_plan_digest
            ),
            "evidence_alignment_digest": alignment.alignment_digest,
            "role_group_mapping_digest": (
                context.s3_runtime_plan.s4_evidence_role_group_mapping_digest
            ),
            "baseline_body_exposed_to_agent": False,
            "human_review_status": "not_performed",
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
        }
        payload = {
            "execution_profile_version_ref": (
                self.profile.execution_profile_version_ref
            ),
            "execution_mode": (
                "s4_source_grounded_deterministic_baseline"
            ),
            "case_id": context.case_id,
            "result": result,
            "s3_runtime_plan": context.s3_runtime_plan.model_dump(
                mode="json"
            ),
            "s3_context_consumption_receipts": list(
                consume_fin01_s3_role_context_plans(
                    context.s3_runtime_plan
                )
            ),
            "s4_evidence_slot_alignment": alignment.model_dump(mode="json"),
            "evidence_dispatch_digest": context.evidence_dispatch_digest,
            "input_digest": input_pack.input_digest,
            "input_head_digest": input_pack.input_head_digest,
            "adapter_direct_canonical_writes": 0,
        }
        return ProfileExecutionResult(
            execution_profile_version_ref=(
                self.profile.execution_profile_version_ref
            ),
            case_id=context.case_id,
            artifact_type=FIN01_DETERMINISTIC_ARTIFACT_TYPE,
            payload=payload,
            artifacts=(
                ProfileArtifactResult(
                    artifact_type=FIN01_S3_WORKPAPER_ARTIFACT_TYPE,
                    payload=workpaper,
                ),
                ProfileArtifactResult(
                    artifact_type=FIN01_S3_REPORT_ARTIFACT_TYPE,
                    payload=report,
                ),
                ProfileArtifactResult(
                    artifact_type=FIN01_S3_TRACE_REVIEW_ARTIFACT_TYPE,
                    payload=trace_review,
                ),
            ),
            terminal_reason="s4_source_grounded_deterministic_baseline_succeeded",
        )


class _AgentFixtureShadowAdapter:
    def __init__(self, profile: ExecutionProfileVersion):
        self.profile = profile

    def execute(
        self,
        context: ProfileExecutionContext,
        principal: CasePrincipal,
    ) -> ProfileExecutionResult:
        del principal
        if "NVDA" not in context.case_query.upper():
            raise ValueError("agent_fixture_shadow_nvda_case_required")

        # Lazy imports keep the deterministic mainline independent of the
        # optional historical LangGraph dependency.
        from sec_agent.agent_registry import select_agent_definition_versions
        from sec_agent.langgraph_orchestrator import run_fin01_agent_fixture_shadow_cell
        from sec_agent.research_skills import select_skill_pack_version

        agent_versions = select_agent_definition_versions(
            list(_AGENT_FIXTURE_SHADOW_ACTIVE_AGENT_IDS)
        )
        skill_packs = []
        for agent_version in agent_versions:
            contract = dict(agent_version["contract"])
            skill_packs.append(
                select_skill_pack_version(
                    agent_id=str(agent_version["agent_id"]),
                    registered_skill_ids=tuple(contract.get("skill_ids") or ()),
                    execution_profile_version_ref=self.profile.execution_profile_version_ref,
                    allowed_execution_profile_refs=(
                        self.profile.execution_profile_version_ref,
                    ),
                )
            )
        graph_slice = run_fin01_agent_fixture_shadow_cell(
            case_id=context.case_id,
            work_unit_id=context.work_unit_id,
            attempt_id=context.attempt_id,
            research_run_id=context.research_run_id,
            causation_event_id=context.causation_event_id,
            execution_profile_version_ref=self.profile.execution_profile_version_ref,
            selected_agent_versions=agent_versions,
            selected_skill_packs=skill_packs,
        )
        payload = {
            "execution_profile_version_ref": self.profile.execution_profile_version_ref,
            "execution_mode": self.profile.execution_mode,
            "case_id": context.case_id,
            "work_unit_id": context.work_unit_id,
            "attempt_id": context.attempt_id,
            "research_run_id": context.research_run_id,
            "graph_slice": graph_slice,
            "agent_definition_versions": [
                {
                    "agent_id": row["agent_id"],
                    "agent_definition_version_ref": row[
                        "agent_definition_version_ref"
                    ],
                    "canonical_digest": row["canonical_digest"],
                }
                for row in agent_versions
            ],
            "skill_pack_versions": [
                {
                    "agent_id": row["agent_id"],
                    "skill_pack_version_ref": row["skill_pack_version_ref"],
                    "canonical_digest": row["canonical_digest"],
                    "skill_definition_version_refs": row[
                        "skill_definition_version_refs"
                    ],
                    "authority_grants": row["authority_grants"],
                }
                for row in skill_packs
            ],
            "adapter_direct_canonical_writes": 0,
            "hard_boundaries": {
                "case_mutations": 0,
                "canonical_business_writes": 0,
                "evidence_promotions": 0,
                "network_calls": 0,
                "model_calls": 0,
                "provider_calls": 0,
                "external_tool_calls": 0,
                "release_admission": 0,
            },
        }
        return ProfileExecutionResult(
            execution_profile_version_ref=self.profile.execution_profile_version_ref,
            case_id=context.case_id,
            artifact_type=self.profile.artifact_type,
            payload=payload,
            artifacts=tuple(
                ProfileArtifactResult(
                    artifact_type=artifact_type,
                    payload=dict(graph_slice["artifacts"][artifact_key]),
                )
                for artifact_key, artifact_type in zip(
                    ("evidence", "numeric", "judgment", "workpaper", "report", "trace"),
                    _AGENT_FIXTURE_CELL_ARTIFACT_TYPES,
                    strict=True,
                )
            ),
            terminal_reason="agent_fixture_shadow_complete_cell_succeeded",
        )


class _BoundedAgentAdapter:
    def __init__(
        self,
        service: P36LocalResearchService,
        profile: ExecutionProfileVersion,
        admission: BoundedAgentAdmission,
        executor: BoundedAgentExecutorPort,
    ) -> None:
        self._service = service
        self.profile = profile
        self.admission = admission
        self.executor = executor

    def execute(
        self,
        context: ProfileExecutionContext,
        principal: CasePrincipal,
    ) -> ProfileExecutionResult:
        input_pack = build_bounded_agent_input_pack(
            self._service, context.case_id, principal
        )
        if self.admission.execution_enabled and (
            self.admission.case_id != input_pack.case_id
            or self.admission.case_version != input_pack.case_version
            or self.admission.as_of != input_pack.as_of
            or self.admission.input_digest != input_pack.input_digest
        ):
            raise ValueError("bounded_admission_exact_input_mismatch")
        output = self.executor.execute(
            input_pack,
            self.admission,
            run_identity={
                "case_id": context.case_id,
                "work_unit_id": context.work_unit_id,
                "attempt_id": context.attempt_id,
                "research_run_id": context.research_run_id,
            },
        )
        rows = {row.artifact_type: row for row in output.artifacts}
        if set(rows) != set(BOUNDED_AGENT_ARTIFACT_TYPES):
            raise ValueError("bounded_agent_artifact_set_mismatch")
        manifest = dict(rows[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE].payload)
        manifest.update(
            {
                "execution_profile_version_ref": self.profile.execution_profile_version_ref,
                "execution_mode": self.profile.execution_mode,
                "case_id": context.case_id,
                "input_digest": input_pack.input_digest,
                "adapter_direct_canonical_writes": 0,
                "evidence_dispatch_digest": (
                    context.evidence_dispatch_digest
                ),
                "s4_evidence_role_group_mapping_digest": (
                    context.s3_runtime_plan.s4_evidence_role_group_mapping_digest
                ),
                "s4_evidence_slot_alignment_digest": (
                    context.s4_evidence_slot_alignment.alignment_digest
                    if context.s4_evidence_slot_alignment is not None
                    else None
                ),
            }
        )
        return ProfileExecutionResult(
            execution_profile_version_ref=self.profile.execution_profile_version_ref,
            case_id=context.case_id,
            artifact_type=BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
            payload=manifest,
            artifacts=tuple(
                ProfileArtifactResult(
                    artifact_type=artifact_type,
                    payload=dict(rows[artifact_type].payload),
                )
                for artifact_type in BOUNDED_AGENT_ARTIFACT_TYPES[1:]
            ),
            trace_events=output.trace_events,
            provider_output_captures=output.provider_output_captures,
            terminal_reason=output.terminal_reason,
        )


class S3ThreeCellPreparedExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    case_version: int
    decision_surface_contract_ref: str
    work_unit_id: str
    attempt_id: str
    research_run_id: str
    execution_identity: str
    input_digest: str
    input_pack: S3ThreeCellBoundedAgentInputPack
    role_group_mapping_digest: str | None = None
    evidence_alignment_digest: str | None = None
    evidence_dispatch_digest: str | None = None
    preparation_digest: str
    observed_counts: dict[str, int]


def predict_fin01_attempt_and_run_ids(
    *,
    work_unit_id: str,
    execution_profile_version_ref: str,
    attempt_no: int = 1,
) -> tuple[str, str]:
    """Predict the exact canonical Attempt/ResearchRun identity without state writes."""

    if not work_unit_id.strip() or not execution_profile_version_ref.strip():
        raise ValueError("fin01_execution_identity_inputs_required")
    if attempt_no <= 0:
        raise ValueError("fin01_attempt_no_must_be_positive")
    attempt_id = "attempt_fin01_" + canonical_digest(
        {
            "work_unit_id": work_unit_id,
            "attempt_no": attempt_no,
            "execution_profile_version_ref": execution_profile_version_ref,
        }
    )[:24]
    research_run_id = "research_run_fin01_" + canonical_digest(
        {
            "attempt_id": attempt_id,
            "execution_profile_version_ref": execution_profile_version_ref,
        }
    )[:24]
    return attempt_id, research_run_id


def _compile_s3_three_cell_bounded_agent_input_from_plans(
    service: P36LocalResearchService,
    case_id: str,
    principal: CasePrincipal,
    *,
    runtime_plan: Mapping[str, Any],
    evidence_route_plan: Mapping[str, Any],
    research_run_id: str,
) -> S3ThreeCellBoundedAgentInputPack:
    preview = service.analysis_preview(case_id, principal)
    financial_pack = compile_s3_financial_numeric_and_fundamental_pack(
        runtime_plan=runtime_plan,
        evidence_route_plan=evidence_route_plan,
        numeric_preview=preview["numeric"],
    )
    graph_pack = compile_s3_bounded_graph_decision_cell_pack(
        runtime_plan=runtime_plan,
        evidence_route_plan=evidence_route_plan,
        financial_pack=financial_pack.model_dump(mode="json"),
        analysis_preview=preview,
    )
    from sec_agent.langgraph_orchestrator import (
        compile_s3_specialist_lead_cross_cell_pack,
    )

    judgment_pack = compile_s3_specialist_lead_cross_cell_pack(
        runtime_plan=runtime_plan,
        evidence_route_plan=evidence_route_plan,
        financial_pack=financial_pack.model_dump(mode="json"),
        graph_pack=graph_pack.model_dump(mode="json"),
    )
    from sec_agent.memo_llm import compile_s3_three_cell_presentation_pack

    presentation_pack = compile_s3_three_cell_presentation_pack(
        runtime_plan=runtime_plan,
        evidence_route_plan=evidence_route_plan,
        financial_pack=financial_pack.model_dump(mode="json"),
        graph_pack=graph_pack.model_dump(mode="json"),
        judgment_pack=judgment_pack.model_dump(mode="json"),
        artifact_refs={
            "workpaper": (
                f"{_fin01_artifact_id(research_run_id, FIN01_S3_WORKPAPER_ARTIFACT_TYPE)}:v1"
            ),
            "report": (
                f"{_fin01_artifact_id(research_run_id, FIN01_S3_REPORT_ARTIFACT_TYPE)}:v1"
            ),
            "trace": (
                f"{_fin01_artifact_id(research_run_id, FIN01_S3_TRACE_REVIEW_ARTIFACT_TYPE)}:v1"
            ),
        },
    )
    return build_s3_three_cell_bounded_agent_input_pack(
        service,
        case_id,
        principal,
        runtime_plan=runtime_plan,
        evidence_route_plan=evidence_route_plan,
        financial_pack=financial_pack.model_dump(mode="json"),
        graph_pack=graph_pack.model_dump(mode="json"),
        judgment_pack=judgment_pack.model_dump(mode="json"),
        presentation_pack=presentation_pack.model_dump(mode="json"),
    )


def prepare_s3_three_cell_bounded_agent_exact_input(
    service: P36LocalResearchService,
    evidence_service: EvidenceService,
    case_id: str,
    principal: CasePrincipal,
    *,
    decision_surface_contract_ref: str,
    execution_identity: str,
    attempt_no: int = 1,
) -> S3ThreeCellPreparedExecution:
    """Compile the exact S3 input twice before any WorkUnit or provider call."""

    if not decision_surface_contract_ref.strip() or not execution_identity.strip():
        raise ValueError("s3_exact_prepare_decision_surface_and_identity_required")
    source = service.preview(case_id, principal)
    work_unit_id = predict_work_unit_id(
        tenant_id=principal.tenant_id,
        project_id=principal.project_id,
        case_id=case_id,
        contract_version_id=decision_surface_contract_ref,
        work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        execution_identity=execution_identity,
    )
    attempt_id, research_run_id = predict_fin01_attempt_and_run_ids(
        work_unit_id=work_unit_id,
        execution_profile_version_ref=S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
        attempt_no=attempt_no,
    )
    runtime_plan = compile_fin01_s3_three_cell_runtime_plan(
        case_id=case_id,
        work_unit_id=work_unit_id,
        attempt_id=attempt_id,
        research_run_id=research_run_id,
        execution_profile_version_ref=S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
        decision_surface_contract_ref=decision_surface_contract_ref,
    )
    evidence_route_plan = evidence_service.compile_s3_three_cell_preflight_evidence_plan(
        runtime_plan=runtime_plan.model_dump(mode="json"),
        principal=principal,
    )
    compile_args = {
        "runtime_plan": runtime_plan.model_dump(mode="json"),
        "evidence_route_plan": evidence_route_plan.model_dump(mode="json"),
        "research_run_id": research_run_id,
    }
    first = _compile_s3_three_cell_bounded_agent_input_from_plans(
        service, case_id, principal, **compile_args
    )
    second = _compile_s3_three_cell_bounded_agent_input_from_plans(
        service, case_id, principal, **compile_args
    )
    if first.model_dump(mode="json") != second.model_dump(mode="json"):
        raise ValueError("s3_exact_prepare_double_compile_parity_failed")
    if (
        first.case_id != str(source["case_id"])
        or first.case_version != int(source["case_version"])
        or first.decision_surface_contract_ref != decision_surface_contract_ref
    ):
        raise ValueError("s3_exact_prepare_case_or_surface_binding_mismatch")
    digest_payload = {
        "case_id": first.case_id,
        "case_version": first.case_version,
        "decision_surface_contract_ref": decision_surface_contract_ref,
        "work_unit_id": work_unit_id,
        "attempt_id": attempt_id,
        "research_run_id": research_run_id,
        "execution_identity": execution_identity,
        "input_digest": first.input_digest,
    }
    return S3ThreeCellPreparedExecution(
        **digest_payload,
        input_pack=first,
        preparation_digest=canonical_digest(digest_payload),
        observed_counts={
            "canonical_writes": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
        },
    )


def prepare_s4_source_grounded_exact_input(
    case_service: CaseService,
    evidence_service: EvidenceService,
    binding: S4CaseRuntimeBinding,
    source_pack: S4SourceGroundedInputPack,
    case_id: str,
    principal: CasePrincipal,
    *,
    decision_surface_contract_ref: str,
    execution_identity: str,
    attempt_no: int = 1,
    research_profile_overlay: (
        S4CaseRuntimeResearchProfileOverlay | None
    ) = None,
) -> S3ThreeCellPreparedExecution:
    """Compile one source-grounded S4 head twice without execution writes."""

    if not decision_surface_contract_ref.strip() or not execution_identity.strip():
        raise ValueError("s4_exact_prepare_surface_and_identity_required")
    source = case_service.get_case(case_id, principal)
    if (
        binding.case_ticker != source_pack.case_ticker
        or int(source["case_version"]) <= 0
        or str(source["as_of"]) != binding.as_of
    ):
        raise ValueError("s4_exact_prepare_case_or_source_binding_mismatch")
    work_unit_id = predict_work_unit_id(
        tenant_id=principal.tenant_id,
        project_id=principal.project_id,
        case_id=case_id,
        contract_version_id=decision_surface_contract_ref,
        work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
        execution_identity=execution_identity,
    )
    attempt_id, research_run_id = predict_fin01_attempt_and_run_ids(
        work_unit_id=work_unit_id,
        execution_profile_version_ref=S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
        attempt_no=attempt_no,
    )
    runtime_plan = compile_fin01_s3_three_cell_runtime_plan(
        case_id=case_id,
        work_unit_id=work_unit_id,
        attempt_id=attempt_id,
        research_run_id=research_run_id,
        execution_profile_version_ref=S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
        decision_surface_contract_ref=decision_surface_contract_ref,
    )
    evidence_dispatch = compile_profile_evidence_dispatch(
        evidence_service,
        runtime_plan=runtime_plan,
        principal=principal,
        s4_binding=binding,
        prospective_execution_lineage=True,
    )
    alignment = evidence_dispatch.s4_evidence_slot_alignment
    if (
        alignment is None
        or evidence_dispatch.s3_evidence_route_plan is not None
        or evidence_dispatch.role_group_mapping_digest is None
    ):
        raise ValueError("s4_exact_prepare_evidence_dispatch_invalid")
    compile_args = {
        "case_id": case_id,
        "case_version": int(source["case_version"]),
        "query": str(source["query"]),
        "decision_surface_contract_ref": decision_surface_contract_ref,
    }
    first = build_s4_source_grounded_bounded_agent_input(
        binding,
        source_pack,
        research_profile_overlay=research_profile_overlay,
        **compile_args,
    )
    second = build_s4_source_grounded_bounded_agent_input(
        binding,
        source_pack,
        research_profile_overlay=research_profile_overlay,
        **compile_args,
    )
    if first.model_dump(mode="json") != second.model_dump(mode="json"):
        raise ValueError("s4_exact_prepare_double_compile_parity_failed")
    digest_payload = {
        "case_id": first.case_id,
        "case_version": first.case_version,
        "decision_surface_contract_ref": decision_surface_contract_ref,
        "work_unit_id": work_unit_id,
        "attempt_id": attempt_id,
        "research_run_id": research_run_id,
        "execution_identity": execution_identity,
        "input_digest": first.input_digest,
        "role_group_mapping_digest": (
            evidence_dispatch.role_group_mapping_digest
        ),
        "evidence_alignment_digest": alignment.alignment_digest,
        "evidence_dispatch_digest": (
            evidence_dispatch.evidence_dispatch_digest
        ),
    }
    return S3ThreeCellPreparedExecution(
        **digest_payload,
        input_pack=first,
        preparation_digest=canonical_digest(digest_payload),
        observed_counts={
            "canonical_writes": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
        },
    )


class _S3ThreeCellBoundedAgentAdapter:
    def __init__(
        self,
        service: P36LocalResearchService,
        profile: ExecutionProfileVersion,
        admission: S3ThreeCellBoundedAgentAdmission,
        executor: S3ThreeCellBoundedAgentExecutorPort,
        s4_binding: S4CaseRuntimeBinding | None = None,
        s4_source_pack: S4SourceGroundedInputPack | None = None,
        s4_research_profile_overlay: (
            S4CaseRuntimeResearchProfileOverlay | None
        ) = None,
    ) -> None:
        if (s4_binding is None) != (s4_source_pack is None):
            raise ValueError(
                "s4_binding_and_source_grounded_pack_must_be_paired"
            )
        self._service = service
        self.profile = profile
        self.admission = admission
        self.executor = executor
        self._s4_binding = s4_binding
        self._s4_source_pack = s4_source_pack
        self._s4_research_profile_overlay = s4_research_profile_overlay

    @property
    def s4_binding(self) -> S4CaseRuntimeBinding | None:
        return self._s4_binding

    def execute(
        self,
        context: ProfileExecutionContext,
        principal: CasePrincipal,
    ) -> ProfileExecutionResult:
        if self._s4_binding is not None and self._s4_source_pack is not None:
            alignment = context.s4_evidence_slot_alignment
            if (
                context.s3_evidence_route_plan is not None
                or alignment is None
                or alignment.case_id != context.case_id
                or alignment.decision_surface_contract_ref
                != context.s3_runtime_plan.decision_surface_contract_ref
                or alignment.runtime_binding_digest
                != self._s4_binding.runtime_binding_digest
                or alignment.role_group_mapping_digest
                != context.s3_runtime_plan.s4_evidence_role_group_mapping_digest
            ):
                raise ValueError("s4_bounded_evidence_alignment_required")
            input_pack = build_s4_source_grounded_bounded_agent_input(
                self._s4_binding,
                self._s4_source_pack,
                case_id=context.case_id,
                decision_surface_contract_ref=(
                    context.s3_runtime_plan.decision_surface_contract_ref
                ),
                case_version=self.admission.case_version,
                query=context.case_query,
                research_profile_overlay=(
                    self._s4_research_profile_overlay
                ),
            )
            if input_pack.input_digest != self.admission.input_digest:
                raise ValueError(
                    "s4_source_grounded_runtime_input_digest_mismatch"
                )
        else:
            if (
                context.s3_evidence_route_plan is None
                or context.s4_evidence_slot_alignment is not None
            ):
                raise ValueError("s3_bounded_evidence_route_plan_required")
            runtime_plan = context.s3_runtime_plan.model_dump(mode="json")
            evidence_route_plan = context.s3_evidence_route_plan.model_dump(
                mode="json"
            )
            input_pack = _compile_s3_three_cell_bounded_agent_input_from_plans(
                self._service,
                context.case_id,
                principal,
                runtime_plan=runtime_plan,
                evidence_route_plan=evidence_route_plan,
                research_run_id=context.research_run_id,
            )
        output = self.executor.execute(
            input_pack,
            self.admission,
            run_identity={
                "case_id": context.case_id,
                "work_unit_id": context.work_unit_id,
                "attempt_id": context.attempt_id,
                "research_run_id": context.research_run_id,
            },
        )
        try:
            rows = {row.artifact_type: row for row in output.artifacts}
            if set(rows) != set(BOUNDED_AGENT_ARTIFACT_TYPES):
                raise ValueError("s3_bounded_agent_artifact_set_mismatch")
            manifest = dict(
                rows[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE].payload
            )
            manifest.update(
                {
                    "execution_profile_version_ref": (
                        self.profile.execution_profile_version_ref
                    ),
                    "execution_mode": self.profile.execution_mode,
                    "case_id": context.case_id,
                    "input_digest": input_pack.input_digest,
                    "adapter_direct_canonical_writes": 0,
                }
            )
            return ProfileExecutionResult(
                execution_profile_version_ref=(
                    self.profile.execution_profile_version_ref
                ),
                case_id=context.case_id,
                artifact_type=BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
                payload=manifest,
                artifacts=tuple(
                    ProfileArtifactResult(
                        artifact_type=artifact_type,
                        payload=dict(rows[artifact_type].payload),
                    )
                    for artifact_type in BOUNDED_AGENT_ARTIFACT_TYPES[1:]
                ),
                trace_events=output.trace_events,
                provider_output_captures=(
                    output.provider_output_captures
                ),
                execution_observation=output.execution_observation,
                terminal_reason=output.terminal_reason,
            )
        except BoundedAgentExecutionError:
            raise
        except Exception as exc:
            raise build_s3_post_provider_failure_error(
                lifecycle_phase="adapter_output_conversion",
                failure_code=(
                    "s3_bounded_adapter_output_conversion_failed"
                ),
                execution_observation=output.execution_observation,
                provider_output_captures=(
                    output.provider_output_captures
                ),
            ) from exc


class Fin01ResearchRuntime:
    """Single FIN 0.1 execution owner over the existing scheduler and facade."""

    def __init__(
        self,
        facade: RuntimeFacade,
        local_research_service: P36LocalResearchService,
        evidence_service: EvidenceService,
        *,
        scheduler: DurableSchedulerService | None = None,
        bounded_agent_admission: BoundedAgentAdmission | None = None,
        bounded_agent_executor: BoundedAgentExecutorPort | None = None,
        s3_three_cell_bounded_agent_admission: S3ThreeCellBoundedAgentAdmission | None = None,
        s3_three_cell_bounded_agent_executor: S3ThreeCellBoundedAgentExecutorPort | None = None,
        s4_deterministic_binding: S4CaseRuntimeBinding | None = None,
        s4_deterministic_source_pack: S4SourceGroundedInputPack | None = None,
        s4_deterministic_research_profile_overlay: (
            S4CaseRuntimeResearchProfileOverlay | None
        ) = None,
        repo_root: str | Path | None = None,
    ) -> None:
        self._facade = facade
        self._repo_root = (
            Path(repo_root).resolve()
            if repo_root is not None
            else Path(__file__).resolve().parents[4]
        )
        self._scheduler = scheduler or DurableSchedulerService(facade)
        self._evidence_service = evidence_service
        deterministic = ExecutionProfileVersion(
            execution_profile_id="fin01.execution_profile.p36_local_deterministic",
            execution_profile_version=1,
            execution_profile_version_ref=FIN01_DETERMINISTIC_PROFILE_REF,
            work_unit_type=VT1_WORK_UNIT_TYPE,
            execution_mode="bounded_local_deterministic_preview",
            worker_ref=FIN01_DETERMINISTIC_WORKER_REF,
            artifact_type=FIN01_DETERMINISTIC_ARTIFACT_TYPE,
            model_calls_allowed=False,
            network_calls_allowed=False,
            external_tool_calls_allowed=False,
            direct_canonical_writes_allowed=False,
        )
        agent_shadow = ExecutionProfileVersion(
            execution_profile_id="fin01.execution_profile.agent_fixture_shadow",
            execution_profile_version=1,
            execution_profile_version_ref=FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF,
            work_unit_type=AGENT_FIXTURE_SHADOW_WORK_UNIT_TYPE,
            execution_mode="historical_langgraph_registry_validation_fixture_shadow",
            worker_ref=FIN01_AGENT_FIXTURE_SHADOW_WORKER_REF,
            artifact_type=FIN01_AGENT_FIXTURE_SHADOW_ARTIFACT_TYPE,
            model_calls_allowed=False,
            network_calls_allowed=False,
            external_tool_calls_allowed=False,
            direct_canonical_writes_allowed=False,
        )
        self._profiles_by_work_unit_type = {
            deterministic.work_unit_type: deterministic,
            agent_shadow.work_unit_type: agent_shadow,
        }
        self._adapters = {
            deterministic.execution_profile_version_ref: _DeterministicP36Adapter(
                local_research_service,
                deterministic,
                s4_binding=s4_deterministic_binding,
                s4_source_pack=s4_deterministic_source_pack,
                s4_research_profile_overlay=(
                    s4_deterministic_research_profile_overlay
                ),
            ),
            agent_shadow.execution_profile_version_ref: _AgentFixtureShadowAdapter(
                agent_shadow
            ),
        }
        if (bounded_agent_admission is None) != (bounded_agent_executor is None):
            raise ValueError("bounded_agent_admission_and_executor_must_be_paired")
        if (s3_three_cell_bounded_agent_admission is None) != (
            s3_three_cell_bounded_agent_executor is None
        ):
            raise ValueError(
                "s3_three_cell_bounded_agent_admission_and_executor_must_be_paired"
            )
        if bounded_agent_admission is not None and s3_three_cell_bounded_agent_admission is not None:
            raise ValueError("only_one_bounded_agent_profile_may_own_work_unit_type")
        if bounded_agent_admission is not None and bounded_agent_executor is not None:
            bounded_agent_admission.assert_profile_admissible()
            bounded = ExecutionProfileVersion(
                execution_profile_id="fin01.execution_profile.bounded_agent_internal",
                execution_profile_version=1,
                execution_profile_version_ref=BOUNDED_AGENT_PROFILE_REF,
                work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
                execution_mode=bounded_agent_admission.execution_mode,
                worker_ref=BOUNDED_AGENT_WORKER_REF,
                artifact_type=BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
                model_calls_allowed=bounded_agent_admission.execution_enabled,
                network_calls_allowed=bounded_agent_admission.execution_enabled,
                external_tool_calls_allowed=False,
                direct_canonical_writes_allowed=False,
                model_ref=bounded_agent_admission.model_ref,
            )
            self._profiles_by_work_unit_type[bounded.work_unit_type] = bounded
            self._adapters[bounded.execution_profile_version_ref] = _BoundedAgentAdapter(
                local_research_service,
                bounded,
                bounded_agent_admission,
                bounded_agent_executor,
            )
        if (
            s3_three_cell_bounded_agent_admission is not None
            and s3_three_cell_bounded_agent_executor is not None
        ):
            s3_three_cell_bounded_agent_admission.assert_profile_admissible()
            s4_binding: S4CaseRuntimeBinding | None = None
            s4_source_pack: S4SourceGroundedInputPack | None = None
            s4_research_profile_overlay: (
                S4CaseRuntimeResearchProfileOverlay | None
            ) = None
            if s3_three_cell_bounded_agent_admission.execution_mode.startswith(
                "exact_live_s4_"
            ):
                (
                    s4_binding,
                    s4_research_profile_overlay,
                ) = resolve_s4_case_runtime_binding_for_admission(
                    self._repo_root,
                    s3_three_cell_bounded_agent_admission,
                )
                s4_source_pack = load_s4_source_grounded_input_pack(
                    self._repo_root,
                    s3_three_cell_bounded_agent_admission.company,
                )
            bounded_three_cell = ExecutionProfileVersion(
                execution_profile_id="fin01.execution_profile.bounded_agent_internal_three_cell",
                execution_profile_version=1,
                execution_profile_version_ref=S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
                work_unit_type=BOUNDED_AGENT_INTERNAL_WORK_UNIT_TYPE,
                execution_mode=s3_three_cell_bounded_agent_admission.execution_mode,
                worker_ref=S3_THREE_CELL_BOUNDED_AGENT_WORKER_REF,
                artifact_type=BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
                model_calls_allowed=s3_three_cell_bounded_agent_admission.execution_enabled,
                network_calls_allowed=s3_three_cell_bounded_agent_admission.execution_enabled,
                external_tool_calls_allowed=False,
                direct_canonical_writes_allowed=False,
                model_ref=s3_three_cell_bounded_agent_admission.model_ref,
            )
            self._profiles_by_work_unit_type[
                bounded_three_cell.work_unit_type
            ] = bounded_three_cell
            self._adapters[
                bounded_three_cell.execution_profile_version_ref
            ] = _S3ThreeCellBoundedAgentAdapter(
                local_research_service,
                bounded_three_cell,
                s3_three_cell_bounded_agent_admission,
                s3_three_cell_bounded_agent_executor,
                s4_binding=s4_binding,
                s4_source_pack=s4_source_pack,
                s4_research_profile_overlay=(
                    s4_research_profile_overlay
                ),
            )

    @property
    def execution_profile(self) -> ExecutionProfileVersion:
        """Compatibility view for the current deterministic UI default."""

        return self._profiles_by_work_unit_type[VT1_WORK_UNIT_TYPE]

    @property
    def execution_profiles(self) -> tuple[ExecutionProfileVersion, ...]:
        return tuple(self._profiles_by_work_unit_type.values())

    @property
    def admitted_work_unit_types(self) -> frozenset[str]:
        return frozenset(self._profiles_by_work_unit_type)

    def dispatch_once(
        self,
        command: CommandEnvelope,
        principal: CasePrincipal,
    ) -> dict[str, Any]:
        case_id = str(command.case_id or "")
        work_unit_id = str(command.payload.get("work_unit_id") or "")
        work_unit = self._facade.store.get_latest("canonical_work_units", work_unit_id)
        case = self._facade.store.get_latest("canonical_research_cases", case_id)
        case_control = (
            self._facade.store.get_latest(
                "canonical_case_control_versions",
                str(case.get("case_control_summary_ref") or ""),
            )
            if case
            else None
        )
        if (
            not case_id
            or not work_unit
            or not case
            or not case_control
            or work_unit.get("case_id") != case_id
            or work_unit.get("tenant_id") != command.tenant_id
            or work_unit.get("project_id") != command.project_id
            or case.get("tenant_id") != command.tenant_id
            or case.get("project_id") != command.project_id
            or case_control.get("case_id") != case_id
        ):
            raise ValueError("dispatch_work_unit_scope_mismatch")
        profile = self._profiles_by_work_unit_type.get(str(work_unit.get("work_unit_type") or ""))
        if profile is None:
            raise ValueError("dispatch_work_unit_type_not_admitted")
        adapter = self._adapters[profile.execution_profile_version_ref]
        if work_unit.get("state") != "pending":
            return {
                "status": "not_dispatched",
                "work_unit_id": work_unit_id,
                "work_unit_state": str(work_unit.get("state") or "unknown"),
            }

        attempts = [
            row
            for row in self._facade.store.list_latest("canonical_attempts", case_id=case_id)
            if row.get("work_unit_id") == work_unit_id
        ]
        attempt_no = max((int(row.get("attempt_no") or 0) for row in attempts), default=0) + 1
        attempt_id, research_run_id = predict_fin01_attempt_and_run_ids(
            work_unit_id=work_unit_id,
            execution_profile_version_ref=profile.execution_profile_version_ref,
            attempt_no=attempt_no,
        )
        claim = self._derived_command(
            command,
            command_type="CLAIM_NEXT_SCHEDULED_ATTEMPT",
            stage="claim",
            expected_state_version=int(work_unit.get("state_version") or 0),
            profile_ref=profile.execution_profile_version_ref,
            payload={
                "work_unit_id": work_unit_id,
                "attempt_id": attempt_id,
                "task_run_id": research_run_id,
                "queue_name": str(work_unit.get("queue_name") or "point02.vt1.fixture"),
                "worker_ref": profile.worker_ref,
                "lease_duration_seconds": 3600,
                "model_ref": profile.model_ref,
                "tool_refs": profile.tool_refs,
            },
        )
        self._scheduler.claim_next(claim)
        attempt = self._facade.store.get_latest("canonical_attempts", attempt_id)
        if not attempt or attempt.get("state") != "running":
            raise RuntimeError("scheduler_claim_did_not_create_running_attempt")
        common_execution_payload = {
            "work_unit_id": work_unit_id,
            "attempt_id": attempt_id,
            "research_run_id": research_run_id,
            "input_head_digest": str(attempt["input_head_digest"]),
            "lease_owner_ref": str(attempt["lease_owner_ref"]),
            "lease_fencing_token": int(attempt["lease_fencing_token"]),
        }
        start = self._derived_command(
            command,
            command_type="START_RESEARCH_RUN",
            stage="start-run",
            expected_state_version=1,
            profile_ref=profile.execution_profile_version_ref,
            payload={
                **common_execution_payload,
                "execution_profile_version_ref": profile.execution_profile_version_ref,
                "parent_research_run_id": self._parent_research_run_id(work_unit),
            },
        )
        start_result = self._facade.start_research_run(start)
        causation_event_id = start_result.event_ids[0]
        profile_result: ProfileExecutionResult | None = None
        bounded_lifecycle_phase = "adapter_output_conversion"
        bounded_failure_code = (
            "s3_bounded_adapter_output_conversion_failed"
        )
        try:
            input_version_refs = tuple(work_unit.get("input_version_refs") or ())
            if len(input_version_refs) != 1 or not str(input_version_refs[0]).strip():
                raise ValueError("s3_runtime_plan_exact_decision_surface_ref_required")
            s3_runtime_plan = compile_fin01_s3_three_cell_runtime_plan(
                case_id=case_id,
                work_unit_id=work_unit_id,
                attempt_id=attempt_id,
                research_run_id=research_run_id,
                execution_profile_version_ref=(
                    profile.execution_profile_version_ref
                ),
                decision_surface_contract_ref=str(input_version_refs[0]),
            )
            evidence_dispatch = (
                compile_profile_evidence_dispatch(
                    self._evidence_service,
                    runtime_plan=s3_runtime_plan,
                    principal=principal,
                    s4_binding=(
                        adapter.s4_binding
                        if isinstance(
                            adapter,
                            (
                                _S3ThreeCellBoundedAgentAdapter,
                                _DeterministicP36Adapter,
                            ),
                        )
                        else None
                    ),
                )
                if profile.execution_profile_version_ref
                in {
                    FIN01_DETERMINISTIC_PROFILE_REF,
                    S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF,
                }
                else None
            )
            if evidence_dispatch is not None:
                s3_runtime_plan = evidence_dispatch.runtime_plan
            profile_result = adapter.execute(
                ProfileExecutionContext(
                    case_id=case_id,
                    case_query=str(case_control.get("query") or ""),
                    work_unit_id=work_unit_id,
                    attempt_id=attempt_id,
                    research_run_id=research_run_id,
                    causation_event_id=causation_event_id,
                    execution_profile_version_ref=profile.execution_profile_version_ref,
                    s3_runtime_plan=s3_runtime_plan,
                    s3_evidence_route_plan=(
                        evidence_dispatch.s3_evidence_route_plan
                        if evidence_dispatch is not None
                        else None
                    ),
                    s4_evidence_slot_alignment=(
                        evidence_dispatch.s4_evidence_slot_alignment
                        if evidence_dispatch is not None
                        else None
                    ),
                    evidence_dispatch_digest=(
                        evidence_dispatch.evidence_dispatch_digest
                        if evidence_dispatch is not None
                        else canonical_digest(
                            {
                                "dispatch_mode": "not_required_for_profile",
                                "execution_profile_version_ref": (
                                    profile.execution_profile_version_ref
                                ),
                                "runtime_plan_digest": (
                                    s3_runtime_plan.runtime_plan_digest
                                ),
                            }
                        )
                    ),
                ),
                principal,
            )
            bounded_lifecycle_phase = "profile_artifact_ref_binding"
            bounded_failure_code = (
                "s3_bounded_profile_artifact_ref_binding_failed"
            )
            profile_result = self._bind_profile_artifact_refs(
                profile_result,
                research_run_id=research_run_id,
            )
            bounded_lifecycle_phase = "profile_result_validation"
            bounded_failure_code = (
                "s3_bounded_profile_result_validation_failed"
            )
            self._validate_profile_result(profile, profile_result, case_id=case_id)
            bounded_lifecycle_phase = "profile_trace_recording"
            bounded_failure_code = (
                "s3_bounded_profile_trace_recording_failed"
            )
            causation_event_id = self._record_profile_trace_events(
                source=command,
                profile=profile,
                common_execution_payload=common_execution_payload,
                profile_result=profile_result,
                causation_event_id=causation_event_id,
            )
        except Exception as exc:
            if (
                profile.execution_profile_version_ref
                == S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
                and profile_result is not None
            ):
                exc = self._typed_s3_post_provider_failure(
                    exc,
                    lifecycle_phase=bounded_lifecycle_phase,
                    failure_code=bounded_failure_code,
                    profile_result=profile_result,
                )
            failure_prefix = (
                "agent_fixture_shadow_profile_error"
                if profile.execution_profile_version_ref
                == FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF
                else (
                    "bounded_agent_profile_error"
                    if profile.execution_profile_version_ref in _BOUNDED_AGENT_PROFILE_REFS
                    else "deterministic_profile_error"
                )
            )
            failure_type = (
                "agent_fixture_shadow_profile_execution_failed"
                if profile.execution_profile_version_ref
                == FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF
                else (
                    "bounded_agent_profile_execution_failed"
                    if profile.execution_profile_version_ref in _BOUNDED_AGENT_PROFILE_REFS
                    else "deterministic_profile_execution_failed"
                )
            )
            terminal_reason = f"{failure_prefix}:{type(exc).__name__}"
            failure_stage = str(getattr(exc, "stage", "") or "").strip()
            if failure_stage:
                terminal_reason = f"{terminal_reason}:{failure_stage}"
            failure_observation = dict(
                getattr(exc, "failure_observation", {}) or {}
            )
            provider_output_captures = list(
                getattr(exc, "provider_output_captures", ()) or ()
            )
            failed = self._derived_command(
                command,
                command_type="FAIL_RESEARCH_RUN",
                stage="fail-run",
                expected_state_version=1,
                profile_ref=profile.execution_profile_version_ref,
                causation_event_id=causation_event_id,
                payload={
                    **common_execution_payload,
                    "failure_type": failure_type,
                    "terminal_reason": terminal_reason,
                    **(
                        {"provider_output_captures": provider_output_captures}
                        if provider_output_captures
                        else {}
                    ),
                    **(
                        {"failure_observation": failure_observation}
                        if failure_observation
                        else {}
                    ),
                },
            )
            self._facade.fail_research_run(failed)
            return {
                "status": "failed",
                "work_unit_id": work_unit_id,
                "attempt_id": attempt_id,
                "research_run_id": research_run_id,
                "execution_profile_version_ref": profile.execution_profile_version_ref,
                "terminal_reason": terminal_reason,
            }

        artifact_results = (
            ProfileArtifactResult(
                artifact_type=profile_result.artifact_type,
                payload=profile_result.payload,
            ),
            *profile_result.artifacts,
        )
        artifact_payloads = []
        for artifact_result in artifact_results:
            artifact_id = _fin01_artifact_id(
                research_run_id, artifact_result.artifact_type
            )
            artifact_payloads.append(
                {
                    "artifact_id": artifact_id,
                    "artifact_type": artifact_result.artifact_type,
                    "artifact_payload": artifact_result.payload,
                }
            )
        complete = self._derived_command(
            command,
            command_type="COMPLETE_RESEARCH_RUN",
            stage="complete-run",
            expected_state_version=1,
            profile_ref=profile.execution_profile_version_ref,
            causation_event_id=causation_event_id,
            payload={
                **common_execution_payload,
                **artifact_payloads[0],
                "artifacts": artifact_payloads,
                "terminal_reason": profile_result.terminal_reason,
                **(
                    {
                        "provider_output_captures": list(
                            profile_result.provider_output_captures
                        )
                    }
                    if profile_result.provider_output_captures
                    else {}
                ),
            },
        )
        try:
            result = self._facade.complete_research_run(complete)
        except Exception as exc:
            terminal_reason = f"profile_commit_error:{type(exc).__name__}"
            failed = self._derived_command(
                command,
                command_type="FAIL_RESEARCH_RUN",
                stage="fail-after-commit-error",
                expected_state_version=1,
                profile_ref=profile.execution_profile_version_ref,
                causation_event_id=causation_event_id,
                payload={
                    **common_execution_payload,
                    "failure_type": "profile_result_commit_failed",
                    "terminal_reason": terminal_reason,
                },
            )
            current_run = self._facade.store.get_latest(
                "canonical_research_run_versions", research_run_id
            )
            if current_run and current_run.get("state") == "running":
                self._facade.fail_research_run(failed)
                return {
                    "status": "failed",
                    "work_unit_id": work_unit_id,
                    "attempt_id": attempt_id,
                    "research_run_id": research_run_id,
                    "execution_profile_version_ref": profile.execution_profile_version_ref,
                    "terminal_reason": terminal_reason,
                }
            raise
        return {
            "status": "succeeded",
            "work_unit_id": work_unit_id,
            "attempt_id": attempt_id,
            "research_run_id": research_run_id,
            "artifact_version_id": result.artifact_refs[0],
            "artifact_version_ids": list(result.artifact_refs),
            "execution_profile_version_ref": profile.execution_profile_version_ref,
        }

    @staticmethod
    def _typed_s3_post_provider_failure(
        exc: Exception,
        *,
        lifecycle_phase: str,
        failure_code: str,
        profile_result: ProfileExecutionResult,
    ) -> BoundedAgentExecutionError:
        if isinstance(exc, BoundedAgentExecutionError):
            return exc
        profile_artifact_lineage = (
            exc.telemetry
            if isinstance(exc, ProfileAwareArtifactLineageError)
            else None
        )
        return build_s3_post_provider_failure_error(
            lifecycle_phase=lifecycle_phase,
            failure_code=failure_code,
            execution_observation=(
                profile_result.execution_observation
            ),
            provider_output_captures=(
                profile_result.provider_output_captures
            ),
            profile_artifact_lineage=profile_artifact_lineage,
        )

    def _record_profile_trace_events(
        self,
        *,
        source: CommandEnvelope,
        profile: ExecutionProfileVersion,
        common_execution_payload: Mapping[str, Any],
        profile_result: ProfileExecutionResult,
        causation_event_id: str,
    ) -> str:
        if profile.execution_profile_version_ref in _BOUNDED_AGENT_PROFILE_REFS:
            current_causation = causation_event_id
            for index, row in enumerate(profile_result.trace_events, 1):
                event_type = str(row.get("event_type") or "").strip()
                event_payload = row.get("event_payload")
                if not event_type or not isinstance(event_payload, Mapping):
                    raise ValueError("bounded_agent_trace_event_invalid")
                trace = self._derived_command(
                    source,
                    command_type="RECORD_RESEARCH_RUN_TRACE",
                    stage=f"bounded-trace-{index}",
                    expected_state_version=1,
                    profile_ref=profile.execution_profile_version_ref,
                    causation_event_id=current_causation,
                    payload={
                        **common_execution_payload,
                        "event_type": event_type,
                        "event_payload": dict(event_payload),
                    },
                )
                recorded = self._facade.record_research_run_trace(trace)
                current_causation = recorded.event_ids[0]
            return current_causation
        if profile.execution_profile_version_ref != FIN01_AGENT_FIXTURE_SHADOW_PROFILE_REF:
            return causation_event_id
        payload = profile_result.payload
        graph_slice = dict(payload.get("graph_slice") or {})
        specs = (
            (
                "agent-versions-selected",
                "AGENT_DEFINITION_VERSIONS_SELECTED",
                {
                    "execution_profile_version_ref": profile.execution_profile_version_ref,
                    "agent_definition_versions": payload["agent_definition_versions"],
                },
            ),
            (
                "skill-packs-consumed",
                "SKILL_PACK_CONSUMPTION_RECORDED",
                {
                    "execution_profile_version_ref": profile.execution_profile_version_ref,
                    "skill_pack_versions": payload["skill_pack_versions"],
                    "consumption_trace": graph_slice["skill_consumption_trace"],
                },
            ),
            (
                "langgraph-shadow-validated",
                "LANGGRAPH_FIXTURE_SHADOW_VALIDATED",
                {
                    "execution_profile_version_ref": profile.execution_profile_version_ref,
                    "graph_nodes_executed": graph_slice["graph_nodes_executed"],
                    "graph_stop_after_node": graph_slice["graph_stop_after_node"],
                    "activation_validation_status": graph_slice[
                        "activation_validation_status"
                    ],
                    "specialist_task_version_ref": graph_slice["specialist_task"][
                        "specialist_task_version_ref"
                    ],
                    "execution_counts": graph_slice["execution_counts"],
                },
            ),
            (
                "research-lead-completed",
                "RESEARCH_LEAD_FIXTURE_COMPLETED",
                {
                    "agent_id": graph_slice["primary_lead_agent_id"],
                    "specialist_task_version_ref": graph_slice["specialist_task"][
                        "specialist_task_version_ref"
                    ],
                    "handoff_trace": graph_slice["handoff_trace"],
                },
            ),
            (
                "specialist-completed",
                "SPECIALIST_FIXTURE_COMPLETED",
                {
                    "agent_id": graph_slice["primary_specialist_agent_id"],
                    "specialist_task_version_ref": graph_slice["specialist_task"][
                        "specialist_task_version_ref"
                    ],
                    "judgment_artifact_ref": graph_slice["artifacts"]["judgment"][
                        "artifact_ref"
                    ],
                },
            ),
            (
                "tool-observation-recorded",
                "TOOL_FIXTURE_OBSERVATION_RECORDED",
                dict(graph_slice["tool_observation"]),
            ),
            (
                "graph-observation-recorded",
                "GRAPH_FIXTURE_OBSERVATION_RECORDED",
                dict(graph_slice["graph_observation"]),
            ),
            (
                "writer-completed",
                "WRITER_FIXTURE_COMPLETED",
                {
                    "agent_id": "memo_writer",
                    "workpaper_artifact_ref": graph_slice["artifacts"]["workpaper"][
                        "artifact_ref"
                    ],
                    "report_artifact_ref": graph_slice["artifacts"]["report"][
                        "artifact_ref"
                    ],
                    "source_calls": 0,
                    "tool_calls": 0,
                },
            ),
            (
                "verifier-completed",
                "VERIFIER_FIXTURE_COMPLETED",
                {
                    "agent_id": "verifier",
                    "status": graph_slice["verifier_result"]["status"],
                    "trace_artifact_ref": graph_slice["artifacts"]["trace"][
                        "artifact_ref"
                    ],
                    "human_review_status": "not_performed",
                },
            ),
        )
        current_causation = causation_event_id
        for stage, event_type, event_payload in specs:
            trace = self._derived_command(
                source,
                command_type="RECORD_RESEARCH_RUN_TRACE",
                stage=stage,
                expected_state_version=1,
                profile_ref=profile.execution_profile_version_ref,
                causation_event_id=current_causation,
                payload={
                    **common_execution_payload,
                    "event_type": event_type,
                    "event_payload": event_payload,
                },
            )
            result = self._facade.record_research_run_trace(trace)
            current_causation = result.event_ids[0]
        return current_causation

    @staticmethod
    def _bind_profile_artifact_refs(
        result: ProfileExecutionResult,
        *,
        research_run_id: str,
    ) -> ProfileExecutionResult:
        rows = (
            ProfileArtifactResult(
                artifact_type=result.artifact_type,
                payload=result.payload,
            ),
            *result.artifacts,
        )
        manifest = {
            row.artifact_type: f"{_fin01_artifact_id(research_run_id, row.artifact_type)}:v1"
            for row in rows
        }
        replacements = {
            str(row.payload.get("artifact_ref")): manifest[row.artifact_type]
            for row in rows
            if str(row.payload.get("artifact_ref") or "")
        }
        bound_rows = []
        for row in rows:
            payload = _replace_exact_artifact_refs(row.payload, replacements)
            payload.update(
                {
                    "artifact_version_id": manifest[row.artifact_type],
                    "research_run_id": research_run_id,
                    "research_run_version_id": f"{research_run_id}:v1",
                    "artifact_manifest": manifest,
                }
            )
            bound_rows.append(
                ProfileArtifactResult(
                    artifact_type=row.artifact_type,
                    payload=payload,
                )
            )
        return result.model_copy(
            update={
                "payload": bound_rows[0].payload,
                "artifacts": tuple(bound_rows[1:]),
            }
        )

    def _parent_research_run_id(self, work_unit: Mapping[str, Any]) -> str | None:
        parent_attempt_id = str(work_unit.get("forked_from_attempt_id") or "")
        if not parent_attempt_id:
            return None
        matches = [
            row
            for row in self._facade.store.list_latest(
                "canonical_research_run_versions", case_id=str(work_unit["case_id"])
            )
            if row.get("attempt_id") == parent_attempt_id
        ]
        return str(matches[0]["research_run_id"]) if len(matches) == 1 else None

    def _validate_profile_result(
        self,
        profile: ExecutionProfileVersion,
        result: ProfileExecutionResult,
        *,
        case_id: str,
    ) -> None:
        if result.execution_profile_version_ref != profile.execution_profile_version_ref:
            raise ValueError("profile_result_profile_identity_mismatch")
        if result.case_id != case_id or result.artifact_type != profile.artifact_type:
            raise ValueError("profile_result_scope_or_type_mismatch")
        payload = result.payload
        if int(payload.get("adapter_direct_canonical_writes", -1)) != 0:
            raise ValueError("profile_adapter_direct_canonical_write_forbidden")
        if profile.execution_profile_version_ref == FIN01_DETERMINISTIC_PROFILE_REF:
            self._validate_deterministic_result(payload, case_id=case_id)
            self._validate_s3_presentation_artifacts(result)
            return
        if profile.execution_profile_version_ref in _BOUNDED_AGENT_PROFILE_REFS:
            self._validate_bounded_agent_result(profile, result, case_id=case_id)
            if (
                profile.execution_profile_version_ref
                == S3_THREE_CELL_BOUNDED_AGENT_PROFILE_REF
            ):
                self._validate_s3_three_cell_bounded_agent_result(result)
            return
        self._validate_agent_fixture_shadow_result(result, case_id=case_id)

    @staticmethod
    def _validate_bounded_agent_result(
        profile: ExecutionProfileVersion,
        result: ProfileExecutionResult,
        *,
        case_id: str,
    ) -> None:
        rows = (result.payload, *(row.payload for row in result.artifacts))
        types = (result.artifact_type, *(row.artifact_type for row in result.artifacts))
        if types != BOUNDED_AGENT_ARTIFACT_TYPES:
            raise ValueError("bounded_agent_artifact_order_mismatch")
        if result.payload.get("case_id") != case_id:
            raise ValueError("bounded_agent_case_identity_mismatch")
        if not str(result.payload.get("input_digest") or ""):
            raise ValueError("bounded_agent_input_digest_missing")
        counts = result.payload.get("observed_counts")
        boundaries = result.payload.get("hard_boundaries")
        if not isinstance(counts, Mapping) or not isinstance(boundaries, Mapping):
            raise ValueError("bounded_agent_counts_or_boundaries_missing")
        for key in ("external_tool_calls", "source_network_calls", "live_case_head_writes"):
            if int(counts.get(key, -1)) != 0:
                raise ValueError(f"bounded_agent_execution_violation:{key}")
        if not profile.model_calls_allowed:
            for key in ("model_calls", "provider_calls", "network_calls"):
                if int(counts.get(key, -1)) != 0:
                    raise ValueError(f"bounded_agent_zero_call_probe_violation:{key}")
        for key in (
            "candidate_is_evidence",
            "graph_edge_is_evidence",
            "writer_source_or_tool_calls",
            "adapter_direct_canonical_writes",
            "live_business_case_head_writes",
            "release_admission",
        ):
            if int(boundaries.get(key, -1)) != 0:
                raise ValueError(f"bounded_agent_boundary_violation:{key}")
        research_run_id = str(result.payload.get("research_run_id") or "")
        if not research_run_id or any(
            row.get("research_run_id") != research_run_id for row in rows
        ):
            raise ValueError("bounded_agent_artifact_run_mismatch")

    @staticmethod
    def _validate_s3_three_cell_bounded_agent_result(
        result: ProfileExecutionResult,
    ) -> None:
        manifest = result.payload
        if tuple(manifest.get("program_cell_ids") or ()) != tuple(
            row.program_cell_id for row in FIN01_S3_PROGRAM_CELL_CONTRACTS
        ):
            raise ValueError("s3_bounded_agent_exact_three_cell_manifest_required")
        expected_nodes = (
            *(
                f"domain_specialist:{row.program_cell_id}"
                for row in FIN01_S3_PROGRAM_CELL_CONTRACTS
            ),
            "research_lead",
            "memo_writer",
            "verifier",
        )
        if tuple(manifest.get("node_topology") or ()) != expected_nodes:
            raise ValueError("s3_bounded_agent_node_topology_mismatch")
        artifacts = {row.artifact_type: row.payload for row in result.artifacts}
        trace = artifacts.get("bounded_agent_trace")
        report = artifacts.get("bounded_agent_report")
        verification = artifacts.get("bounded_agent_verification")
        judgment = artifacts.get("bounded_agent_judgment")
        if not all(isinstance(row, Mapping) for row in (trace, report, verification, judgment)):
            raise ValueError("s3_bounded_agent_required_artifacts_missing")
        lineage = trace.get("lineage")
        if not isinstance(lineage, Mapping):
            raise ProfileAwareArtifactLineageError(
                "bounded_agent_profile_lineage_contract_mismatch",
                artifact_type="bounded_agent_trace",
                lineage_family="unresolved",
            )
        artifact_payloads = (
            manifest,
            *(row.payload for row in result.artifacts),
        )
        s4_projections = [
            row.get("s4_case_runtime") for row in artifact_payloads
        ]
        s4_projection: Mapping[str, Any] | None = None
        if any(row is not None for row in s4_projections):
            if (
                any(not isinstance(row, Mapping) for row in s4_projections)
                or any(
                    dict(row) != dict(s4_projections[0])
                    for row in s4_projections[1:]
                )
            ):
                raise ProfileAwareArtifactLineageError(
                    "bounded_agent_profile_lineage_contract_mismatch",
                    artifact_type="s4_case_runtime",
                    lineage_family="unresolved",
                )
            s4_projection = s4_projections[0]
        validate_profile_aware_artifact_lineage_projection(
            lineage=lineage,
            manifest_contract_ref=manifest.get(
                "lineage_contract_ref"
            ),
            manifest_lineage_family=manifest.get("lineage_family"),
            manifest_lineage_digest=manifest.get("lineage_digest"),
            s4_case_runtime=s4_projection,
        )
        if int(report.get("writer_source_calls", -1)) != 0 or int(
            report.get("writer_tool_calls", -1)
        ) != 0:
            raise ValueError("s3_bounded_agent_writer_authority_violation")
        verifier = verification.get("verification")
        findings = verifier.get("findings") if isinstance(verifier, Mapping) else None
        if not isinstance(findings, list) or tuple(
            str(row.get("layer")) for row in findings if isinstance(row, Mapping)
        ) != (
            "deterministic_integrity",
            "semantic_fidelity",
            "financial_coherence",
            "visual_delivery",
        ):
            raise ValueError("s3_bounded_agent_four_layer_verification_missing")
        specialist_outputs = judgment.get("specialist_outputs")
        if not isinstance(specialist_outputs, list) or tuple(
            str(row.get("program_cell_id"))
            for row in specialist_outputs
            if isinstance(row, Mapping)
        ) != tuple(row.program_cell_id for row in FIN01_S3_PROGRAM_CELL_CONTRACTS):
            raise ValueError("s3_bounded_agent_three_specialist_outputs_missing")

    @staticmethod
    def _validate_deterministic_result(payload: Mapping[str, Any], *, case_id: str) -> None:
        preview = payload.get("result")
        if not isinstance(preview, Mapping):
            raise ValueError("profile_result_preview_missing")
        if preview.get("case_id") != case_id or preview.get("status") != "internal_analysis_preview_ready":
            raise ValueError("profile_result_preview_identity_mismatch")
        hard_boundaries = preview.get("hard_boundaries")
        execution_counts = preview.get("execution_counts")
        if not isinstance(hard_boundaries, Mapping) or not isinstance(execution_counts, Mapping):
            raise ValueError("profile_result_boundary_evidence_missing")
        for key in (
            "case_mutations",
            "canonical_store_writes",
            "evidence_promotions",
            "network_calls",
            "model_calls",
            "release_admission",
        ):
            if int(hard_boundaries.get(key, -1)) != 0:
                raise ValueError(f"profile_result_boundary_violation:{key}")
        for key in ("network_calls", "model_calls", "provider_calls", "external_tool_calls"):
            if int(execution_counts.get(key, -1)) != 0:
                raise ValueError(f"profile_result_execution_violation:{key}")
        if (
            preview.get("analysis_mode")
            == "s4_source_grounded_deterministic_baseline"
        ):
            Fin01ResearchRuntime._validate_s4_deterministic_result(
                payload,
                case_id=case_id,
            )
            return
        plan = S3ThreeCellRuntimePlanVersion.model_validate(
            payload.get("s3_runtime_plan")
        )
        if (
            plan.case_id != case_id
            or len(plan.cell_branches) != 3
            or len({row.research_run_id for row in plan.cell_branches}) != 1
            or len(plan.role_context_plans) != 9
        ):
            raise ValueError("s3_runtime_plan_scope_or_cardinality_invalid")
        receipts = payload.get("s3_context_consumption_receipts")
        if not isinstance(receipts, list) or len(receipts) != 9:
            raise ValueError("s3_context_consumption_receipts_missing")
        evidence_route_plan = S3ThreeCellEvidenceRoutePlanVersion.model_validate(
            payload.get("s3_evidence_route_plan")
        )
        expected_route_receipts = consume_s3_three_cell_evidence_route_plan(
            evidence_route_plan,
            runtime_plan_version_ref=plan.runtime_plan_version_ref,
            runtime_plan_digest=plan.runtime_plan_digest,
        )
        evidence_route_receipts = payload.get(
            "s3_evidence_route_consumption_receipts"
        )
        if (
            not isinstance(evidence_route_receipts, list)
            or evidence_route_receipts
            != [dict(row) for row in expected_route_receipts]
        ):
            raise ValueError("s3_evidence_route_consumption_receipts_invalid")
        financial_pack = S3FinancialNumericAndFundamentalPackVersion.model_validate(
            payload.get("s3_financial_numeric_and_fundamental_pack")
        )
        expected_financial_receipts = (
            consume_s3_financial_numeric_and_fundamental_pack(
                financial_pack,
                runtime_plan_version_ref=plan.runtime_plan_version_ref,
                runtime_plan_digest=plan.runtime_plan_digest,
                evidence_route_plan=evidence_route_plan.model_dump(mode="json"),
            )
        )
        financial_receipts = payload.get(
            "s3_financial_numeric_consumption_receipts"
        )
        if (
            not isinstance(financial_receipts, list)
            or financial_receipts
            != [dict(row) for row in expected_financial_receipts]
        ):
            raise ValueError("s3_financial_numeric_consumption_receipts_invalid")
        graph_pack = S3BoundedGraphDecisionCellPackVersion.model_validate(
            payload.get("s3_bounded_graph_product_market_risk_pack")
        )
        expected_graph_receipts = consume_s3_bounded_graph_decision_cell_pack(
            graph_pack,
            runtime_plan=plan.model_dump(mode="json"),
            evidence_route_plan=evidence_route_plan.model_dump(mode="json"),
            financial_pack=financial_pack.model_dump(mode="json"),
            analysis_preview=preview,
        )
        graph_receipts = payload.get("s3_bounded_graph_consumption_receipts")
        if (
            not isinstance(graph_receipts, list)
            or graph_receipts != [dict(row) for row in expected_graph_receipts]
        ):
            raise ValueError("s3_bounded_graph_consumption_receipts_invalid")
        from sec_agent.langgraph_orchestrator import (
            S3SpecialistLeadCrossCellPackVersion,
            consume_s3_specialist_lead_cross_cell_pack,
        )

        judgment_pack = S3SpecialistLeadCrossCellPackVersion.model_validate(
            payload.get("s3_specialist_lead_cross_cell_pack")
        )
        expected_judgment_receipts = consume_s3_specialist_lead_cross_cell_pack(
            judgment_pack,
            runtime_plan=plan.model_dump(mode="json"),
            evidence_route_plan=evidence_route_plan.model_dump(mode="json"),
            financial_pack=financial_pack.model_dump(mode="json"),
            graph_pack=graph_pack.model_dump(mode="json"),
        )
        judgment_receipts = payload.get(
            "s3_specialist_lead_consumption_receipts"
        )
        if (
            not isinstance(judgment_receipts, list)
            or judgment_receipts
            != [dict(row) for row in expected_judgment_receipts]
        ):
            raise ValueError("s3_specialist_lead_consumption_receipts_invalid")
        from sec_agent.memo_llm import (
            S3ThreeCellPresentationPackVersion,
            consume_s3_three_cell_presentation_pack,
        )

        presentation_pack = S3ThreeCellPresentationPackVersion.model_validate(
            payload.get("s3_three_cell_presentation_pack")
        )
        expected_presentation_receipts = consume_s3_three_cell_presentation_pack(
            presentation_pack,
            runtime_plan=plan.model_dump(mode="json"),
            evidence_route_plan=evidence_route_plan.model_dump(mode="json"),
            financial_pack=financial_pack.model_dump(mode="json"),
            graph_pack=graph_pack.model_dump(mode="json"),
            judgment_pack=judgment_pack.model_dump(mode="json"),
        )
        presentation_receipts = payload.get(
            "s3_presentation_consumption_receipts"
        )
        if (
            not isinstance(presentation_receipts, list)
            or presentation_receipts
            != [dict(row) for row in expected_presentation_receipts]
        ):
            raise ValueError("s3_presentation_consumption_receipts_invalid")

    @staticmethod
    def _validate_s4_deterministic_result(
        payload: Mapping[str, Any],
        *,
        case_id: str,
    ) -> None:
        preview = payload["result"]
        plan = S3ThreeCellRuntimePlanVersion.model_validate(
            payload.get("s3_runtime_plan")
        )
        alignment = S4CaseEvidenceSlotAlignmentReceipt.model_validate(
            payload.get("s4_evidence_slot_alignment")
        )
        cells = preview.get("cells")
        if (
            plan.case_id != case_id
            or plan.s4_evidence_role_group_mapping_digest is None
            or alignment.case_id != case_id
            or alignment.alignment_digest
            != preview.get("evidence_alignment_digest")
            or not isinstance(cells, list)
            or tuple(
                str(row.get("program_cell_id"))
                for row in cells
                if isinstance(row, Mapping)
            )
            != tuple(
                row.program_cell_id
                for row in FIN01_S3_PROGRAM_CELL_CONTRACTS
            )
        ):
            raise ValueError("s4_deterministic_scope_or_cell_contract_invalid")
        if (
            payload.get("input_digest") != preview.get("input_digest")
            or payload.get("input_head_digest")
            != preview.get("input_head_digest")
            or not str(preview.get("company") or "").strip()
            or not str(preview.get("source_pack_digest") or "").strip()
            or preview.get("analysis_digest")
            != canonical_digest(
                {
                    key: value
                    for key, value in preview.items()
                    if key != "analysis_digest"
                }
            )
        ):
            raise ValueError("s4_deterministic_input_or_digest_invalid")
        for cell in cells:
            if (
                not isinstance(cell, Mapping)
                or not isinstance(cell.get("evidence_rows"), list)
                or not isinstance(cell.get("numeric_rows"), list)
                or not isinstance(cell.get("derived_metrics"), list)
                or not isinstance(cell.get("typed_gap_codes"), list)
                or not str(
                    cell.get("deterministic_boundary_statement") or ""
                ).endswith(
                    "No causal or forward-looking judgment is inferred."
                )
            ):
                raise ValueError("s4_deterministic_cell_payload_invalid")
        receipts = payload.get("s3_context_consumption_receipts")
        if (
            not isinstance(receipts, list)
            or len(receipts) != 9
            or payload.get("adapter_direct_canonical_writes") != 0
        ):
            raise ValueError("s4_deterministic_receipt_or_write_boundary_invalid")

    @staticmethod
    def _validate_s3_presentation_artifacts(result: ProfileExecutionResult) -> None:
        preview = result.payload.get("result")
        if (
            isinstance(preview, Mapping)
            and preview.get("analysis_mode")
            == "s4_source_grounded_deterministic_baseline"
        ):
            Fin01ResearchRuntime._validate_s4_deterministic_artifacts(
                result
            )
            return
        from sec_agent.memo_llm import S3ThreeCellPresentationPackVersion

        pack = S3ThreeCellPresentationPackVersion.model_validate(
            result.payload.get("s3_three_cell_presentation_pack")
        )
        expected = (
            (
                FIN01_S3_WORKPAPER_ARTIFACT_TYPE,
                pack.workpaper.artifact_ref,
                "workpaper",
                pack.workpaper.model_dump(mode="json"),
            ),
            (
                FIN01_S3_REPORT_ARTIFACT_TYPE,
                pack.report.artifact_ref,
                "report",
                pack.report.model_dump(mode="json"),
            ),
            (
                FIN01_S3_TRACE_REVIEW_ARTIFACT_TYPE,
                pack.trace_review.artifact_ref,
                "trace_review",
                pack.trace_review.model_dump(mode="json"),
            ),
        )
        if tuple(row.artifact_type for row in result.artifacts) != tuple(
            row[0] for row in expected
        ):
            raise ValueError("s3_presentation_artifact_type_order_invalid")
        for artifact, (artifact_type, artifact_ref, payload_key, nested) in zip(
            result.artifacts, expected, strict=True
        ):
            if (
                artifact.artifact_type != artifact_type
                or artifact.payload.get("artifact_ref") != artifact_ref
                or artifact.payload.get(payload_key) != nested
                or artifact.payload.get("research_run_id") != pack.research_run_id
                or artifact.payload.get("presentation_pack_version_ref")
                != pack.presentation_pack_version_ref
            ):
                raise ValueError("s3_presentation_artifact_payload_mismatch")

    @staticmethod
    def _validate_s4_deterministic_artifacts(
        result: ProfileExecutionResult,
    ) -> None:
        expected_types = (
            FIN01_S3_WORKPAPER_ARTIFACT_TYPE,
            FIN01_S3_REPORT_ARTIFACT_TYPE,
            FIN01_S3_TRACE_REVIEW_ARTIFACT_TYPE,
        )
        if tuple(row.artifact_type for row in result.artifacts) != expected_types:
            raise ValueError("s4_deterministic_artifact_type_order_invalid")
        for row in result.artifacts:
            payload = row.payload
            if (
                payload.get("contract_ref")
                != FIN01_S4_DETERMINISTIC_BASELINE_CONTRACT_REF
                or payload.get("case_id") != result.case_id
                or not str(payload.get("artifact_ref") or "").strip()
                or not str(payload.get("research_run_id") or "").strip()
            ):
                raise ValueError("s4_deterministic_artifact_payload_invalid")
        report = result.artifacts[1].payload
        trace = result.artifacts[2].payload
        if (
            len(report.get("sections") or ()) != 3
            or any(
                int(report.get(key, -1)) != 0
                for key in ("source_calls", "tool_calls", "model_calls")
            )
            or trace.get("baseline_body_exposed_to_agent") is not False
            or trace.get("human_review_status") != "not_performed"
            or any(
                int(trace.get(key, -1)) != 0
                for key in ("model_calls", "provider_calls", "network_calls")
            )
        ):
            raise ValueError("s4_deterministic_artifact_boundary_invalid")

    @staticmethod
    def _validate_agent_fixture_shadow_result(
        result: ProfileExecutionResult, *, case_id: str
    ) -> None:
        payload = result.payload
        if payload.get("case_id") != case_id:
            raise ValueError("agent_fixture_shadow_case_identity_mismatch")
        graph_slice = payload.get("graph_slice")
        hard_boundaries = payload.get("hard_boundaries")
        if not isinstance(graph_slice, Mapping) or not isinstance(hard_boundaries, Mapping):
            raise ValueError("agent_fixture_shadow_trace_or_boundary_missing")
        if graph_slice.get("activation_validation_status") != "pass":
            raise ValueError("agent_fixture_shadow_activation_validation_failed")
        executed_nodes = set(graph_slice.get("graph_nodes_executed") or [])
        required_nodes = {
            "research_lead_plan",
            "universe_relationship_expand",
            "execute_evidence_operators",
            "optional_specialist_subgraph",
            "aggregate_judgment_plan",
            "memo_writer",
            "verifier",
            "renderer",
            "persist_session_state",
        }
        if not required_nodes.issubset(executed_nodes):
            raise ValueError("agent_fixture_shadow_complete_graph_mismatch")
        if int(graph_slice.get("specialist_to_specialist_hidden_call_count", -1)) != 0:
            raise ValueError("agent_fixture_shadow_hidden_handoff_forbidden")
        counts = graph_slice.get("execution_counts")
        if not isinstance(counts, Mapping):
            raise ValueError("agent_fixture_shadow_execution_counts_missing")
        for key in (
            "model_calls",
            "provider_calls",
            "network_calls",
            "external_tool_calls",
            "business_writes",
        ):
            if int(counts.get(key, -1)) != 0:
                raise ValueError(f"agent_fixture_shadow_execution_violation:{key}")
        for key in (
            "case_mutations",
            "canonical_business_writes",
            "evidence_promotions",
            "network_calls",
            "model_calls",
            "provider_calls",
            "external_tool_calls",
            "release_admission",
        ):
            if int(hard_boundaries.get(key, -1)) != 0:
                raise ValueError(f"agent_fixture_shadow_boundary_violation:{key}")
        if not payload.get("agent_definition_versions") or not payload.get("skill_pack_versions"):
            raise ValueError("agent_fixture_shadow_version_trace_missing")
        if tuple(row.artifact_type for row in result.artifacts) != _AGENT_FIXTURE_CELL_ARTIFACT_TYPES:
            raise ValueError("agent_fixture_shadow_cell_artifact_set_mismatch")
        graph_artifacts = graph_slice.get("artifacts")
        if not isinstance(graph_artifacts, Mapping) or set(graph_artifacts) != {
            "evidence",
            "numeric",
            "judgment",
            "workpaper",
            "report",
            "trace",
        }:
            raise ValueError("agent_fixture_shadow_cell_artifact_payload_missing")
        research_run_id = str(payload.get("research_run_id") or "")
        if not research_run_id or any(
            row.payload.get("research_run_id") != research_run_id
            for row in result.artifacts
        ):
            raise ValueError("agent_fixture_shadow_cell_artifact_run_mismatch")

    @staticmethod
    def _derived_command(
        source: CommandEnvelope,
        *,
        command_type: str,
        stage: str,
        expected_state_version: int,
        profile_ref: str,
        payload: Mapping[str, Any],
        causation_event_id: str | None = None,
    ) -> CommandEnvelope:
        identity = {
            "source_command_id": source.command_id,
            "stage": stage,
            "work_unit_id": payload.get("work_unit_id"),
            "attempt_id": payload.get("attempt_id"),
            "research_run_id": payload.get("research_run_id") or payload.get("task_run_id"),
            "execution_profile_version_ref": profile_ref,
        }
        digest = canonical_digest(identity)
        return CommandEnvelope(
            command_id=f"fin01_runtime_{stage}_{digest[:24]}",
            command_type=command_type,
            tenant_id=source.tenant_id,
            project_id=source.project_id,
            case_id=source.case_id,
            actor_snapshot_ref=source.actor_snapshot_ref,
            permission_snapshot_ref=source.permission_snapshot_ref,
            policy_config_refs=tuple(
                dict.fromkeys((*source.policy_config_refs, profile_ref))
            ),
            idempotency_key=f"{source.idempotency_key}:{stage}:{digest[:16]}",
            expected_state_version=expected_state_version,
            causation_event_id=causation_event_id or source.causation_event_id,
            correlation_id=source.correlation_id,
            requested_at=utc_now(),
            payload=dict(payload),
        )
