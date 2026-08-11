from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from sec_agent.canonical_runtime.candidate_bundle import (
    CandidateBundle,
    CandidateBundleCompiler,
    CandidateBundlePolicy,
    CandidateMetadata,
    CandidateMetadataSnapshot,
)
from sec_agent.canonical_runtime.evidence_request import (
    EvidenceRequest,
    EvidenceRequestCompiler,
    EvidenceRequestPolicy,
)
from sec_agent.canonical_runtime.models import (
    DecisionSurfaceCellVersion,
    DecisionSurfaceContractVersion,
    EvidenceReviewActionVersion,
    EvidenceSlotVersion,
    EvidenceWorkbenchProjectionVersion,
    EventEnvelope,
    StrictModel,
    canonical_digest,
    utc_now,
)
from sec_agent.canonical_runtime.planning_service import (
    FIN01_S3_PROGRAM_CELL_CONTRACTS,
)
from sec_agent.canonical_runtime.store import IdempotencyConflict, TransactionConflict
from sec_agent.canonical_runtime.tool_planner import (
    BoundedToolPlanner,
    PlannerPermissionContext,
    PlannerPolicy,
    ToolRegistryEntry,
    ToolRegistrySnapshot,
    ToolSelectionPlan,
)
from sec_agent.s4_case_runtime import (
    S4CaseEvidenceSlotAlignmentReceipt,
    S4CaseRuntimeBinding,
    compile_s4_case_evidence_role_group_mapping,
    compile_s4_case_evidence_slot_alignment,
    consume_s4_case_runtime_binding,
)
from sec_agent.runtime_resource_registry import read_registered_runtime_json

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
CONTRACT_RESOURCE_ID = "application.contract.evidence_workbench"
S3_EVIDENCE_ROUTE_PLAN_CONTRACT_REF = "fin01.s3.evidence_route_plan_three_cell:v1"
S3_EVIDENCE_SERVICE_OWNER_REF = (
    "apps.workbench.backend.application.evidence_service:EvidenceService"
)
S3_SOURCEHUNTER_BOUNDARY_REF = "fin01.s3.sourcehunter_separate_exact_admission:v1"


class S3ToolGatewayPreflightDecision(StrictModel):
    preflight_id: str
    preflight_digest: str
    evidence_request_id: str
    tool_selection_plan_id: str
    planner_step_id: str
    selected_tool_id: str
    selected_route_id: str
    tool_registry_check: Literal["pass"] = "pass"
    permission_check: Literal["pass_planning_allowlist_only"] = (
        "pass_planning_allowlist_only"
    )
    network_check: Literal["not_required_local_route"] = "not_required_local_route"
    data_scope_check: Literal["pass_fixture_metadata_only"] = (
        "pass_fixture_metadata_only"
    )
    budget_check: Literal["pass"] = "pass"
    input_contract_check: Literal["pass"] = "pass"
    decision: Literal["checks_pass_execution_not_admitted"] = (
        "checks_pass_execution_not_admitted"
    )
    invocation_status: Literal["not_executed"] = "not_executed"


class S3EvidencePromotionAssessment(StrictModel):
    assessment_id: str
    assessment_digest: str
    evidence_request_id: str
    candidate_bundle_id: str
    decision: Literal[
        "candidate_only_pending_claim_source_content_and_corroboration",
        "candidate_only_pending_T04_parser_numeric_lineage",
        "context_only_graph_observation_source_followup_required",
        "typed_gap_local_route_exhausted",
    ]
    candidate_refs: tuple[str, ...]
    context_refs: tuple[str, ...]
    rejected_refs: tuple[str, ...]
    typed_gap_codes: tuple[str, ...]
    accepted_evidence_refs: tuple[str, ...] = ()
    evidence_gate_owner_ref: str = S3_EVIDENCE_SERVICE_OWNER_REF
    runtime_promotion_authorized: Literal[False] = False
    writer_citable: Literal[False] = False
    judgment_eligible: Literal[False] = False
    persistence_authorized: Literal[False] = False


class S3GraphObservationVersion(StrictModel):
    observation_id: str
    observation_digest: str
    program_cell_id: str
    branch_version_ref: str
    evidence_request_id: str
    candidate_id: str
    observation_class: Literal["navigation_hypothesis_only"] = (
        "navigation_hypothesis_only"
    )
    relation_hypothesis: str
    source_followup_required: Literal[True] = True
    direct_evidence_authorized: Literal[False] = False
    numeric_authority: Literal[False] = False


class S3SourceFollowupRequestVersion(StrictModel):
    followup_request_id: str
    followup_request_digest: str
    program_cell_id: str
    branch_version_ref: str
    originating_graph_observation_ref: str
    parent_evidence_request_id: str
    target_route_id: str
    objective: str
    status: Literal["planned_local_followup_not_executed"] = (
        "planned_local_followup_not_executed"
    )
    execution_admission: Literal["not_admitted"] = "not_admitted"


class S3SourceHunterBoundaryVersion(StrictModel):
    boundary_id: str
    boundary_digest: str
    program_cell_id: str
    branch_version_ref: str
    evidence_request_id: str
    source_followup_request_ref: str | None = None
    status: Literal[
        "not_needed_local_candidate_route_available",
        "not_eligible_until_parser_or_claim_binding",
        "proposal_only_blocked_missing_separate_network_admission",
    ]
    trigger_reason: str
    boundary_contract_ref: str = S3_SOURCEHUNTER_BOUNDARY_REF
    exact_network_admission_required: Literal[True] = True
    network_execution_authorized: Literal[False] = False
    external_tool_execution_authorized: Literal[False] = False
    model_execution_authorized: Literal[False] = False
    request_executed: Literal[False] = False
    network_calls: Literal[0] = 0


class S3CellEvidenceRouteVersion(StrictModel):
    program_cell_id: str
    evidence_role: str
    branch_version_ref: str
    evidence_operator_context_plan_ref: str
    research_run_id: str
    evidence_request: EvidenceRequest
    tool_selection_plan: ToolSelectionPlan
    candidate_snapshot: CandidateMetadataSnapshot
    candidate_bundle: CandidateBundle
    tool_gateway_preflights: tuple[S3ToolGatewayPreflightDecision, ...]
    promotion_assessment: S3EvidencePromotionAssessment
    graph_observation: S3GraphObservationVersion | None = None
    source_followup_request: S3SourceFollowupRequestVersion | None = None
    sourcehunter_boundary: S3SourceHunterBoundaryVersion
    route_outcome: Literal[
        "candidate_observed_promotion_blocked",
        "graph_context_observed_source_followup_required",
        "typed_gap_sourcehunter_not_admitted",
    ]
    cell_route_digest: str


class S3ThreeCellEvidenceRoutePlanVersion(StrictModel):
    evidence_route_plan_id: str
    evidence_route_plan_version_ref: str
    evidence_route_plan_contract_ref: str = S3_EVIDENCE_ROUTE_PLAN_CONTRACT_REF
    evidence_service_owner_ref: str = S3_EVIDENCE_SERVICE_OWNER_REF
    case_id: str
    work_unit_id: str
    attempt_id: str
    research_run_id: str
    execution_profile_version_ref: str
    decision_surface_contract_ref: str
    runtime_plan_version_ref: str
    runtime_plan_digest: str
    cell_routes: tuple[S3CellEvidenceRouteVersion, ...]
    evidence_route_plan_digest: str
    model_calls: Literal[0] = 0
    provider_calls: Literal[0] = 0
    execution_network_calls: Literal[0] = 0
    source_network_calls: Literal[0] = 0
    external_tool_calls: Literal[0] = 0
    live_business_writes: Literal[0] = 0
    runtime_evidence_promotions: Literal[0] = 0


def _s3_recomputed_digest(model: StrictModel, *identity_fields: str) -> str:
    payload = model.model_dump(mode="json")
    for field in identity_fields:
        payload.pop(field, None)
    return canonical_digest(payload)


def consume_s3_three_cell_evidence_route_plan(
    plan: S3ThreeCellEvidenceRoutePlanVersion,
    *,
    runtime_plan_version_ref: str,
    runtime_plan_digest: str,
) -> tuple[dict[str, Any], ...]:
    """Validate T03 lineage/digests and emit zero-call node consumption receipts."""

    if (
        plan.runtime_plan_version_ref != runtime_plan_version_ref
        or plan.runtime_plan_digest != runtime_plan_digest
    ):
        raise ValueError("s3_evidence_route_runtime_plan_lineage_mismatch")
    if any(
        (
            plan.model_calls,
            plan.provider_calls,
            plan.execution_network_calls,
            plan.source_network_calls,
            plan.external_tool_calls,
            plan.live_business_writes,
            plan.runtime_evidence_promotions,
        )
    ):
        raise ValueError("s3_evidence_route_zero_call_boundary_violated")
    expected_plan_digest = _s3_recomputed_digest(
        plan,
        "evidence_route_plan_id",
        "evidence_route_plan_version_ref",
        "evidence_route_plan_digest",
    )
    if expected_plan_digest != plan.evidence_route_plan_digest:
        raise ValueError("s3_evidence_route_plan_digest_mismatch")
    expected_plan_id = (
        f"evidence_route_plan_fin01_s3_{plan.evidence_route_plan_digest[:24]}"
    )
    if (
        plan.evidence_route_plan_id != expected_plan_id
        or plan.evidence_route_plan_version_ref != f"{expected_plan_id}:v1"
    ):
        raise ValueError("s3_evidence_route_plan_identity_mismatch")
    expected_cells = tuple(
        row.program_cell_id for row in FIN01_S3_PROGRAM_CELL_CONTRACTS
    )
    if (
        tuple(row.program_cell_id for row in plan.cell_routes) != expected_cells
        or len({row.branch_version_ref for row in plan.cell_routes}) != 3
        or {row.research_run_id for row in plan.cell_routes}
        != {plan.research_run_id}
    ):
        raise ValueError("s3_evidence_route_cell_lineage_invalid")

    selected_route_sets: list[tuple[str, ...]] = []
    receipts: list[dict[str, Any]] = []
    for cell in plan.cell_routes:
        if _s3_recomputed_digest(cell, "cell_route_digest") != cell.cell_route_digest:
            raise ValueError("s3_cell_evidence_route_digest_mismatch")
        request = cell.evidence_request
        if _s3_recomputed_digest(request, "request_id", "request_digest") != request.request_digest:
            raise ValueError("s3_evidence_request_digest_mismatch")
        if request.request_id != f"evidence_request_{request.request_digest[:20]}":
            raise ValueError("s3_evidence_request_identity_mismatch")
        tool_plan = cell.tool_selection_plan
        if _s3_recomputed_digest(tool_plan, "plan_id", "plan_digest") != tool_plan.plan_digest:
            raise ValueError("s3_tool_selection_plan_digest_mismatch")
        if tool_plan.plan_id != f"tool_selection_plan_{tool_plan.plan_digest[:20]}":
            raise ValueError("s3_tool_selection_plan_identity_mismatch")
        snapshot = cell.candidate_snapshot
        snapshot_digest = canonical_digest(
            {
                "snapshot_id": snapshot.snapshot_id,
                "fixture_only": snapshot.fixture_only,
                "candidates": [
                    row.model_dump(mode="json") for row in snapshot.candidates
                ],
            }
        )
        if snapshot_digest != snapshot.snapshot_digest:
            raise ValueError("s3_candidate_snapshot_digest_mismatch")
        bundle = cell.candidate_bundle
        if _s3_recomputed_digest(bundle, "bundle_id", "bundle_digest") != bundle.bundle_digest:
            raise ValueError("s3_candidate_bundle_digest_mismatch")
        if bundle.bundle_id != f"candidate_bundle_{bundle.bundle_digest[:20]}":
            raise ValueError("s3_candidate_bundle_identity_mismatch")
        if (
            tool_plan.request_id != request.request_id
            or tool_plan.request_digest != request.request_digest
            or bundle.request_id != request.request_id
            or bundle.request_digest != request.request_digest
            or bundle.tool_selection_plan_id != tool_plan.plan_id
            or bundle.tool_selection_plan_digest != tool_plan.plan_digest
            or bundle.metadata_snapshot_id != snapshot.snapshot_id
            or bundle.metadata_snapshot_digest != snapshot.snapshot_digest
        ):
            raise ValueError("s3_request_plan_bundle_lineage_mismatch")
        if len(cell.tool_gateway_preflights) != len(tool_plan.steps):
            raise ValueError("s3_tool_gateway_preflight_cardinality_mismatch")
        for preflight, step in zip(
            cell.tool_gateway_preflights, tool_plan.steps, strict=True
        ):
            if (
                _s3_recomputed_digest(
                    preflight, "preflight_id", "preflight_digest"
                )
                != preflight.preflight_digest
                or preflight.preflight_id
                != f"s3_tool_gateway_preflight_{preflight.preflight_digest[:24]}"
                or preflight.planner_step_id != step.planner_step_id
                or preflight.selected_tool_id != step.selected_tool_id
                or preflight.selected_route_id != step.selected_route_id
                or preflight.invocation_status != "not_executed"
            ):
                raise ValueError("s3_tool_gateway_preflight_invalid")
        promotion = cell.promotion_assessment
        if (
            _s3_recomputed_digest(
                promotion, "assessment_id", "assessment_digest"
            )
            != promotion.assessment_digest
            or promotion.assessment_id
            != f"s3_promotion_assessment_{promotion.assessment_digest[:24]}"
            or promotion.evidence_request_id != request.request_id
            or promotion.candidate_bundle_id != bundle.bundle_id
            or promotion.accepted_evidence_refs
            or promotion.runtime_promotion_authorized
            or promotion.writer_citable
            or promotion.judgment_eligible
            or promotion.persistence_authorized
        ):
            raise ValueError("s3_evidence_promotion_boundary_invalid")
        graph = cell.graph_observation
        followup = cell.source_followup_request
        if graph is not None:
            if (
                _s3_recomputed_digest(
                    graph, "observation_id", "observation_digest"
                )
                != graph.observation_digest
                or graph.observation_id
                != f"s3_graph_observation_{graph.observation_digest[:24]}"
                or graph.direct_evidence_authorized
                or graph.numeric_authority
                or followup is None
            ):
                raise ValueError("s3_graph_observation_boundary_invalid")
        if followup is not None:
            if (
                _s3_recomputed_digest(
                    followup,
                    "followup_request_id",
                    "followup_request_digest",
                )
                != followup.followup_request_digest
                or followup.followup_request_id
                != f"s3_source_followup_{followup.followup_request_digest[:24]}"
                or graph is None
                or followup.originating_graph_observation_ref
                != graph.observation_id
                or followup.execution_admission != "not_admitted"
            ):
                raise ValueError("s3_source_followup_boundary_invalid")
        sourcehunter = cell.sourcehunter_boundary
        if (
            _s3_recomputed_digest(
                sourcehunter, "boundary_id", "boundary_digest"
            )
            != sourcehunter.boundary_digest
            or sourcehunter.boundary_id
            != f"s3_sourcehunter_boundary_{sourcehunter.boundary_digest[:24]}"
            or sourcehunter.network_execution_authorized
            or sourcehunter.external_tool_execution_authorized
            or sourcehunter.model_execution_authorized
            or sourcehunter.request_executed
            or sourcehunter.network_calls
        ):
            raise ValueError("s3_sourcehunter_boundary_invalid")
        selected_routes = tuple(
            str(step.selected_route_id) for step in tool_plan.steps
        )
        selected_route_sets.append(selected_routes)
        receipts.append(
            {
                "program_cell_id": cell.program_cell_id,
                "branch_version_ref": cell.branch_version_ref,
                "evidence_operator_context_plan_ref": (
                    cell.evidence_operator_context_plan_ref
                ),
                "evidence_request_id": request.request_id,
                "tool_selection_plan_id": tool_plan.plan_id,
                "candidate_bundle_id": bundle.bundle_id,
                "promotion_assessment_id": promotion.assessment_id,
                "sourcehunter_boundary_id": sourcehunter.boundary_id,
                "cell_route_digest": cell.cell_route_digest,
                "consumption_mode": (
                    "deterministic_evidence_service_node_contract_validation"
                ),
                "model_calls": 0,
                "source_network_calls": 0,
                "external_tool_calls": 0,
                "runtime_evidence_promotions": 0,
            }
        )
    if len(set(selected_route_sets)) != 3:
        raise ValueError("s3_cell_route_sets_must_be_distinct")
    counter = next(
        row
        for row in plan.cell_routes
        if row.program_cell_id
        == "bottleneck_counterevidence_and_what_would_change"
    )
    if counter.tool_selection_plan.status == "await_execution_admission":
        if (
            counter.graph_observation is None
            or counter.source_followup_request is None
            or counter.sourcehunter_boundary.status
            != "proposal_only_blocked_missing_separate_network_admission"
        ):
            raise ValueError("s3_graph_followup_sourcehunter_boundary_missing")
    elif (
        counter.tool_selection_plan.status != "stopped"
        or counter.route_outcome != "typed_gap_sourcehunter_not_admitted"
    ):
        raise ValueError("s3_counter_route_or_typed_stop_invalid")
    return tuple(receipts)


def consume_s4_case_runtime_evidence_route(
    binding: S4CaseRuntimeBinding,
) -> dict[str, Any]:
    """Inject one frozen S4 Case Pack into the existing Evidence route owner."""

    return consume_s4_case_runtime_binding(
        binding, "evidence_route_plan"
    ).model_dump(mode="json")


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
    """Evidence owner for Point 3 VT1 and FIN 0.1 S3 route/promotion boundaries."""

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
        contract = read_registered_runtime_json(repo_root, CONTRACT_RESOURCE_ID)
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
        self._configure_s3_route_contract()

    def _configure_s3_route_contract(self) -> None:
        request_policy = deepcopy(self._contract["evidence_request_policy"])
        route_overrides = {
            "demand_signal": {
                "preferred_routes": ["local_object_bm25_official_disclosure"],
                "fallback_routes": ["local_materialized_customer_deployment_context"],
            },
            "revenue_capture": {
                "preferred_routes": ["local_gold_sql_financial_table"],
                "fallback_routes": ["local_official_filing_table_address"],
            },
            "thesis_counterevidence": {
                "preferred_routes": ["local_relationship_graph_navigation"],
                "fallback_routes": ["local_official_counterevidence_source_followup"],
                "tool_call_limit": 2,
            },
        }
        role_rules = request_policy["role_rules"]
        for role, override in route_overrides.items():
            role_rules[role] = {**deepcopy(role_rules[role]), **override}
        request_policy["policy_ref"] = "fin01.s3.cell_driven_evidence_request:v1"
        self._s3_request_compiler = EvidenceRequestCompiler(
            EvidenceRequestPolicy.model_validate(request_policy)
        )

        registry_rows = (
            self._s3_registry_row(
                tool_id="s3_local_object_bm25_metadata",
                route_id="local_object_bm25_official_disclosure",
                evidence_role="demand_candidate",
                source_policy_ref="fixture:issuer_filing_first",
                source_role="official_issuer",
                source_authority="local_official_disclosure_index",
                source_authority_rank=5,
                capability="local.object_bm25.metadata.read",
                cost_rank=0,
            ),
            self._s3_registry_row(
                tool_id="s3_local_customer_deployment_context",
                route_id="local_materialized_customer_deployment_context",
                evidence_role="demand_candidate",
                source_policy_ref="fixture:issuer_filing_first",
                source_role="official_customer",
                source_authority="local_materialized_official_context",
                source_authority_rank=4,
                capability="local.materialized_context.read",
                cost_rank=1,
            ),
            self._s3_registry_row(
                tool_id="s3_local_gold_sql_financial_table",
                route_id="local_gold_sql_financial_table",
                evidence_role="revenue_candidate",
                source_policy_ref="fixture:issuer_filing_first",
                source_role="official_issuer",
                source_authority="local_gold_sql_exact_value_locator",
                source_authority_rank=5,
                capability="local.gold_sql.table_address.read",
                cost_rank=0,
            ),
            self._s3_registry_row(
                tool_id="s3_local_official_filing_table_address",
                route_id="local_official_filing_table_address",
                evidence_role="revenue_candidate",
                source_policy_ref="fixture:issuer_filing_first",
                source_role="official_issuer",
                source_authority="local_official_filing_table_address",
                source_authority_rank=5,
                capability="local.filing.table_address.read",
                cost_rank=1,
            ),
            self._s3_registry_row(
                tool_id="s3_local_relationship_graph_navigation",
                route_id="local_relationship_graph_navigation",
                evidence_role="counterevidence_candidate",
                source_policy_ref="fixture:issuer_and_policy_first",
                source_role="relationship_graph",
                source_authority="local_graph_navigation_hypothesis",
                source_authority_rank=1,
                capability="local.relationship_graph.navigation.read",
                cost_rank=0,
            ),
            self._s3_registry_row(
                tool_id="s3_local_official_counterevidence_followup",
                route_id="local_official_counterevidence_source_followup",
                evidence_role="counterevidence_candidate",
                source_policy_ref="fixture:issuer_and_policy_first",
                source_role="official_policy",
                source_authority="local_materialized_official_policy",
                source_authority_rank=5,
                capability="local.official_policy.metadata.read",
                cost_rank=1,
            ),
        )
        self._s3_registry = ToolRegistrySnapshot.create(
            registry_id="fin01-s3-cell-driven-local-route-registry",
            registry_version=1,
            entries=tuple(ToolRegistryEntry.model_validate(row) for row in registry_rows),
        )
        self._s3_planner = BoundedToolPlanner(
            registry=self._s3_registry,
            policy=PlannerPolicy.model_validate(
                {
                    "policy_ref": "fin01.s3.tool_planner_preflight_only:v1",
                    "max_tool_calls": 2,
                    "max_fallback_depth": 1,
                    "required_permission_scope": "s3_fixture_metadata_read_only",
                    "minimum_source_authority_rank_by_evidence_role": {
                        "demand_candidate": 4,
                        "revenue_candidate": 4,
                        "counterevidence_candidate": 1,
                    },
                    "required_execution_admission": (
                        "separate_local_execution_admission_required"
                    ),
                    "stop_rules": [
                        "budget_exhausted_stop_rule",
                        "route_exhaustion_stop_rule",
                        "permission_scope_stop_rule",
                        "source_network_requires_separate_exact_admission",
                    ],
                }
            ),
        )
        self._s3_candidate_compiler = CandidateBundleCompiler(
            policy=CandidateBundlePolicy.model_validate(
                {
                    "policy_ref": "fin01.s3.cell_route_candidate_boundary:v1",
                    "minimum_source_authority_rank_by_evidence_role": {
                        "demand_candidate": 4,
                        "revenue_candidate": 4,
                        "counterevidence_candidate": 1,
                    },
                    "required_candidate_kinds_by_evidence_role": {
                        "demand_candidate": ["top_k_seed", "neighbor_section"],
                        "revenue_candidate": ["top_k_seed", "table_context"],
                        "counterevidence_candidate": ["top_k_seed"],
                    },
                    "allowed_candidate_kinds": [
                        "top_k_seed",
                        "neighbor_section",
                        "table_context",
                    ],
                    "allowed_bundle_statuses": [
                        "metadata_fixture_compiled",
                        "retrieval_exhausted",
                        "not_attempted_typed_stop",
                    ],
                }
            )
        )
        self._s3_fixture_candidate_sets = {
            "demand_signal": self._s3_remap_fixture_candidates(
                "demand_signal",
                {
                    "top_k_seed": "local_object_bm25_official_disclosure",
                    "neighbor_section": "local_materialized_customer_deployment_context",
                },
            ),
            "revenue_capture": self._s3_remap_fixture_candidates(
                "revenue_capture",
                {
                    "top_k_seed": "local_gold_sql_financial_table",
                    "table_context": "local_official_filing_table_address",
                },
            ),
            "thesis_counterevidence": (
                CandidateMetadata(
                    candidate_id="s3_fixture_nvda_tsm_packaging_graph_observation",
                    document_id="fixture_relationship_graph_nvda_tsm",
                    document_version="fixture:v1",
                    source_snapshot_ref="fixture_snapshot:p36_ai_infra_graph:v1",
                    source_policy_ref="fixture:issuer_and_policy_first",
                    route_id="local_relationship_graph_navigation",
                    source_role="relationship_graph",
                    source_authority_rank=1,
                    entity_ref="NVDA",
                    period_ref="latest_two_quarters",
                    candidate_kind="top_k_seed",
                    section_or_table_ref="nvda_to_tsm_packaging_dependency_hypothesis",
                    metadata_rank=1,
                    content_ref="fixture://p36/graph/nvda-tsm-packaging-hypothesis",
                ),
            ),
        }

    @staticmethod
    def _s3_registry_row(
        *,
        tool_id: str,
        route_id: str,
        evidence_role: str,
        source_policy_ref: str,
        source_role: str,
        source_authority: str,
        source_authority_rank: int,
        capability: str,
        cost_rank: int,
    ) -> dict[str, Any]:
        return {
            "tool_id": tool_id,
            "tool_name": tool_id,
            "capabilities": [capability],
            "input_schema_ref": "EvidenceRequest:v1",
            "output_schema_ref": "CandidateMetadata:v1",
            "source_role": source_role,
            "source_authority": source_authority,
            "source_authority_rank": source_authority_rank,
            "can_support": [evidence_role],
            "cannot_support": [
                "promoted_evidence_without_gate",
                "final_judgment",
            ],
            "cost_class": "fixture_zero_cost",
            "cost_rank": cost_rank,
            "latency_class": "local",
            "failure_types": [
                "fixture_candidate_absent",
                "route_exhausted",
            ],
            "fallback_tool_ids": [],
            "permission_scope": "s3_fixture_metadata_read_only",
            "forbidden_claims": [
                "candidate_as_evidence",
                "graph_observation_as_fact",
            ],
            "supported_evidence_roles": [evidence_role],
            "supported_source_policy_refs": [source_policy_ref],
            "declared_route_ids": [route_id],
            "execution_mode": "not_admitted",
        }

    def _s3_remap_fixture_candidates(
        self,
        evidence_role: str,
        route_by_kind: Mapping[str, str],
    ) -> tuple[CandidateMetadata, ...]:
        rows = []
        for raw in self._fixture_candidate_sets[evidence_role]:
            metadata = deepcopy(raw["metadata"])
            metadata["route_id"] = route_by_kind[metadata["candidate_kind"]]
            rows.append(CandidateMetadata.model_validate(metadata))
        return tuple(rows)

    def compile_s3_three_cell_runtime_evidence_plan(
        self,
        *,
        runtime_plan: Mapping[str, Any],
        principal: CasePrincipal,
        allowed_tool_ids_by_program_cell: Mapping[str, tuple[str, ...]] | None = None,
        _allow_prospective_execution_lineage: bool = False,
    ) -> S3ThreeCellEvidenceRoutePlanVersion:
        """Compile the T03 three-cell evidence control plane without executing a route."""

        self._require_permission(principal, "evidence:read")
        context = self._s3_runtime_context(
            runtime_plan,
            principal,
            allow_prospective_execution_lineage=(
                _allow_prospective_execution_lineage
            ),
        )
        permission_overrides = allowed_tool_ids_by_program_cell or {}
        cell_routes: list[S3CellEvidenceRouteVersion] = []
        for program_cell in FIN01_S3_PROGRAM_CELL_CONTRACTS:
            branch = context["branches_by_program_cell"][program_cell.program_cell_id]
            evidence_context = context["contexts_by_program_cell"][
                program_cell.program_cell_id
            ]
            cell, slot = context["slots_by_role"][program_cell.evidence_role]
            request_result = self._s3_request_compiler.compile(
                contract=context["contract"],
                cell=cell,
                slot=slot,
            )
            allowed_tool_ids = permission_overrides.get(
                program_cell.program_cell_id,
                tuple(entry.tool_id for entry in self._s3_registry.entries),
            )
            plan_result = self._s3_planner.plan(
                request=request_result.request,
                permissions=PlannerPermissionContext(
                    permission_snapshot_ref=self._permission_ref(principal),
                    allowed_tool_ids=allowed_tool_ids,
                    required_permission_scope=(
                        self._s3_planner.policy.required_permission_scope
                    ),
                ),
            )
            snapshot = CandidateMetadataSnapshot.create(
                snapshot_id=(
                    "fin01:s3:t03:"
                    f"{context['contract'].contract_version_id}:"
                    f"{program_cell.program_cell_id}"
                ),
                candidates=self._s3_fixture_candidate_sets[
                    program_cell.evidence_role
                ],
            )
            bundle_result = self._s3_candidate_compiler.compile(
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
                    bundle_result.store_write_count,
                )
            ):
                raise EvidenceServiceError("s3_evidence_route_zero_call_boundary_violated", 409)
            preflights = tuple(
                self._s3_gateway_preflight(
                    request=request_result.request,
                    plan=plan_result.plan,
                    planner_step_id=step.planner_step_id,
                )
                for step in plan_result.plan.steps
            )
            graph_observation = self._s3_graph_observation(
                program_cell_id=program_cell.program_cell_id,
                branch_version_ref=str(branch["branch_version_ref"]),
                request=request_result.request,
                bundle=bundle_result.bundle,
            )
            source_followup = self._s3_source_followup(
                graph_observation=graph_observation,
                request=request_result.request,
            )
            promotion = self._s3_promotion_assessment(
                evidence_role=program_cell.evidence_role,
                request=request_result.request,
                bundle=bundle_result.bundle,
                graph_observation=graph_observation,
            )
            sourcehunter = self._s3_sourcehunter_boundary(
                program_cell_id=program_cell.program_cell_id,
                branch_version_ref=str(branch["branch_version_ref"]),
                request=request_result.request,
                bundle=bundle_result.bundle,
                source_followup=source_followup,
            )
            route_outcome: str
            if bundle_result.bundle.status in {
                "retrieval_exhausted",
                "not_attempted_typed_stop",
            }:
                route_outcome = "typed_gap_sourcehunter_not_admitted"
            elif graph_observation is not None:
                route_outcome = "graph_context_observed_source_followup_required"
            else:
                route_outcome = "candidate_observed_promotion_blocked"
            route_payload = {
                "program_cell_id": program_cell.program_cell_id,
                "evidence_role": program_cell.evidence_role,
                "branch_version_ref": str(branch["branch_version_ref"]),
                "evidence_operator_context_plan_ref": str(
                    evidence_context["context_plan_version_ref"]
                ),
                "research_run_id": str(runtime_plan["research_run_id"]),
                "evidence_request": request_result.request.model_dump(mode="json"),
                "tool_selection_plan": plan_result.plan.model_dump(mode="json"),
                "candidate_snapshot": snapshot.model_dump(mode="json"),
                "candidate_bundle": bundle_result.bundle.model_dump(mode="json"),
                "tool_gateway_preflights": [
                    row.model_dump(mode="json") for row in preflights
                ],
                "promotion_assessment": promotion.model_dump(mode="json"),
                "graph_observation": (
                    graph_observation.model_dump(mode="json")
                    if graph_observation
                    else None
                ),
                "source_followup_request": (
                    source_followup.model_dump(mode="json")
                    if source_followup
                    else None
                ),
                "sourcehunter_boundary": sourcehunter.model_dump(mode="json"),
                "route_outcome": route_outcome,
            }
            cell_routes.append(
                S3CellEvidenceRouteVersion(
                    **route_payload,
                    cell_route_digest=canonical_digest(route_payload),
                )
            )

        plan_payload = {
            "evidence_route_plan_contract_ref": S3_EVIDENCE_ROUTE_PLAN_CONTRACT_REF,
            "evidence_service_owner_ref": S3_EVIDENCE_SERVICE_OWNER_REF,
            "case_id": str(runtime_plan["case_id"]),
            "work_unit_id": str(runtime_plan["work_unit_id"]),
            "attempt_id": str(runtime_plan["attempt_id"]),
            "research_run_id": str(runtime_plan["research_run_id"]),
            "execution_profile_version_ref": str(
                runtime_plan["execution_profile_version_ref"]
            ),
            "decision_surface_contract_ref": str(
                runtime_plan["decision_surface_contract_ref"]
            ),
            "runtime_plan_version_ref": str(
                runtime_plan["runtime_plan_version_ref"]
            ),
            "runtime_plan_digest": str(runtime_plan["runtime_plan_digest"]),
            "cell_routes": [row.model_dump(mode="json") for row in cell_routes],
            "model_calls": 0,
            "provider_calls": 0,
            "execution_network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "live_business_writes": 0,
            "runtime_evidence_promotions": 0,
        }
        digest = canonical_digest(plan_payload)
        plan_id = f"evidence_route_plan_fin01_s3_{digest[:24]}"
        return S3ThreeCellEvidenceRoutePlanVersion(
            evidence_route_plan_id=plan_id,
            evidence_route_plan_version_ref=f"{plan_id}:v1",
            evidence_route_plan_digest=digest,
            **plan_payload,
        )

    def compile_s3_three_cell_preflight_evidence_plan(
        self,
        *,
        runtime_plan: Mapping[str, Any],
        principal: CasePrincipal,
    ) -> S3ThreeCellEvidenceRoutePlanVersion:
        """Compile exact prospective lineage only while no execution state exists."""

        return self.compile_s3_three_cell_runtime_evidence_plan(
            runtime_plan=runtime_plan,
            principal=principal,
            _allow_prospective_execution_lineage=True,
        )

    def compile_s4_case_evidence_slot_alignment(
        self,
        *,
        runtime_plan: Mapping[str, Any],
        binding: S4CaseRuntimeBinding,
        principal: CasePrincipal,
        _allow_prospective_execution_lineage: bool = False,
    ) -> S4CaseEvidenceSlotAlignmentReceipt:
        """Align all S4 case roles to accepted Canonical slots without routing."""

        self._require_permission(principal, "evidence:read")
        required_identity_fields = (
            "case_id",
            "work_unit_id",
            "attempt_id",
            "research_run_id",
            "execution_profile_version_ref",
            "decision_surface_contract_ref",
            "runtime_plan_version_ref",
            "runtime_plan_digest",
            "s4_evidence_role_group_mapping_ref",
            "s4_evidence_role_group_mapping_digest",
        )
        if any(
            not str(runtime_plan.get(key) or "").strip()
            for key in required_identity_fields
        ):
            raise EvidenceServiceError(
                "s4_evidence_alignment_runtime_identity_required", 409
            )
        mapping = compile_s4_case_evidence_role_group_mapping(binding)
        if (
            runtime_plan["s4_evidence_role_group_mapping_ref"]
            != mapping.contract_ref
            or runtime_plan["s4_evidence_role_group_mapping_digest"]
            != mapping.role_group_mapping_digest
        ):
            raise EvidenceServiceError(
                "s4_evidence_role_group_mapping_digest_mismatch", 409
            )

        case_id = str(runtime_plan["case_id"])
        catalog = self._facade_or_raise().store
        contract_rows = [
            row
            for row in catalog.list_versions(
                "canonical_decision_surface_contract_versions",
                case_id=case_id,
            )
            if row.get("contract_version_id")
            == runtime_plan["decision_surface_contract_ref"]
            and self._matches_scope(row, case_id, principal)
        ]
        if len(contract_rows) != 1:
            raise EvidenceServiceError(
                "s4_exact_decision_surface_contract_required", 409
            )
        accepted_checkpoints = [
            row
            for row in catalog.list_latest(
                "canonical_planning_checkpoint_versions", case_id=case_id
            )
            if row.get("contract_version_id")
            == runtime_plan["decision_surface_contract_ref"]
            and row.get("review_status") == "accepted"
            and self._matches_scope(row, case_id, principal)
        ]
        if len(accepted_checkpoints) != 1:
            raise EvidenceServiceError(
                "s4_accepted_checkpoint_required", 409
            )

        work_unit = catalog.get_latest(
            "canonical_work_units", str(runtime_plan["work_unit_id"])
        )
        attempt = catalog.get_latest(
            "canonical_attempts", str(runtime_plan["attempt_id"])
        )
        research_run = catalog.get_latest(
            "canonical_research_run_versions",
            str(runtime_plan["research_run_id"]),
        )
        if _allow_prospective_execution_lineage:
            if any((work_unit, attempt, research_run)):
                raise EvidenceServiceError(
                    "s4_preflight_requires_absent_execution_lineage", 409
                )
        elif (
            not work_unit
            or work_unit.get("case_id") != case_id
            or work_unit.get("tenant_id") != principal.tenant_id
            or work_unit.get("project_id") != principal.project_id
            or work_unit.get("state") not in {"pending", "running"}
            or tuple(work_unit.get("input_version_refs") or ())
            != (runtime_plan["decision_surface_contract_ref"],)
            or not attempt
            or attempt.get("case_id") != case_id
            or attempt.get("work_unit_id") != runtime_plan["work_unit_id"]
            or attempt.get("state") != "running"
            or not research_run
            or research_run.get("case_id") != case_id
            or research_run.get("work_unit_id")
            != runtime_plan["work_unit_id"]
            or research_run.get("attempt_id") != runtime_plan["attempt_id"]
            or research_run.get("state") != "running"
            or research_run.get("execution_profile_version_ref")
            != runtime_plan["execution_profile_version_ref"]
        ):
            raise EvidenceServiceError(
                "s4_work_unit_decision_surface_lineage_mismatch", 409
            )

        cell_rows = [
            row
            for row in catalog.list_versions(
                "canonical_decision_surface_cell_versions", case_id=case_id
            )
            if row.get("contract_version_id")
            == runtime_plan["decision_surface_contract_ref"]
            and self._matches_scope(row, case_id, principal)
        ]
        cell_version_refs = {
            str(row.get("cell_version_id") or "") for row in cell_rows
        }
        slot_rows = [
            row
            for row in catalog.list_versions(
                "canonical_evidence_slot_versions", case_id=case_id
            )
            if row.get("cell_version_id") in cell_version_refs
            and self._matches_scope(row, case_id, principal)
        ]
        try:
            return compile_s4_case_evidence_slot_alignment(
                binding,
                case_id=case_id,
                decision_surface_contract_ref=str(
                    runtime_plan["decision_surface_contract_ref"]
                ),
                cells=cell_rows,
                slots=slot_rows,
            )
        except ValueError as exc:
            raise EvidenceServiceError(str(exc), 409) from exc

    def _s3_runtime_context(
        self,
        runtime_plan: Mapping[str, Any],
        principal: CasePrincipal,
        *,
        allow_prospective_execution_lineage: bool = False,
    ) -> dict[str, Any]:
        required_identity_fields = (
            "case_id",
            "work_unit_id",
            "attempt_id",
            "research_run_id",
            "execution_profile_version_ref",
            "decision_surface_contract_ref",
            "runtime_plan_version_ref",
            "runtime_plan_digest",
        )
        if any(not str(runtime_plan.get(key) or "").strip() for key in required_identity_fields):
            raise EvidenceServiceError("s3_runtime_plan_identity_required", 409)
        case_id = str(runtime_plan["case_id"])
        if principal.tenant_id != str(runtime_plan.get("tenant_id") or principal.tenant_id):
            raise EvidenceServiceError("s3_runtime_plan_tenant_scope_mismatch", 409)
        catalog = self._facade_or_raise().store
        contract_rows = [
            row
            for row in catalog.list_versions(
                "canonical_decision_surface_contract_versions", case_id=case_id
            )
            if row.get("contract_version_id")
            == runtime_plan["decision_surface_contract_ref"]
            and self._matches_scope(row, case_id, principal)
        ]
        if len(contract_rows) != 1:
            raise EvidenceServiceError("s3_exact_decision_surface_contract_required", 409)
        contract = DecisionSurfaceContractVersion.model_validate(contract_rows[0])
        accepted_checkpoints = [
            row
            for row in catalog.list_latest(
                "canonical_planning_checkpoint_versions", case_id=case_id
            )
            if row.get("contract_version_id") == contract.contract_version_id
            and row.get("review_status") == "accepted"
            and self._matches_scope(row, case_id, principal)
        ]
        if len(accepted_checkpoints) != 1:
            raise EvidenceServiceError("s3_accepted_checkpoint_required", 409)
        work_unit = catalog.get_latest(
            "canonical_work_units", str(runtime_plan["work_unit_id"])
        )
        if allow_prospective_execution_lineage:
            if (
                work_unit is not None
                or catalog.get_latest(
                    "canonical_attempts", str(runtime_plan["attempt_id"])
                )
                is not None
                or catalog.get_latest(
                    "canonical_research_run_versions",
                    str(runtime_plan["research_run_id"]),
                )
                is not None
            ):
                raise EvidenceServiceError(
                    "s3_preflight_requires_absent_execution_lineage", 409
                )
        elif (
            not work_unit
            or work_unit.get("case_id") != case_id
            or work_unit.get("tenant_id") != principal.tenant_id
            or work_unit.get("project_id") != principal.project_id
            or work_unit.get("state") not in {"pending", "running"}
            or tuple(work_unit.get("input_version_refs") or ())
            != (contract.contract_version_id,)
        ):
            raise EvidenceServiceError("s3_work_unit_decision_surface_lineage_mismatch", 409)
        branch_rows = list(runtime_plan.get("cell_branches") or ())
        context_rows = list(runtime_plan.get("role_context_plans") or ())
        branches_by_program_cell = {
            str(row.get("program_cell_id") or ""): row for row in branch_rows
        }
        contexts_by_program_cell = {
            str(row.get("program_cell_id") or ""): row
            for row in context_rows
            if row.get("target_node") == "evidence_operator"
        }
        required_program_cells = {
            row.program_cell_id for row in FIN01_S3_PROGRAM_CELL_CONTRACTS
        }
        if (
            len(branch_rows) != 3
            or set(branches_by_program_cell) != required_program_cells
            or len(contexts_by_program_cell) != 3
            or set(contexts_by_program_cell) != required_program_cells
        ):
            raise EvidenceServiceError("s3_runtime_branch_or_evidence_context_cardinality", 409)
        cell_rows = [
            row
            for row in catalog.list_versions(
                "canonical_decision_surface_cell_versions", case_id=case_id
            )
            if row.get("contract_version_id") == contract.contract_version_id
            and self._matches_scope(row, case_id, principal)
        ]
        cells = [DecisionSurfaceCellVersion.model_validate(row) for row in cell_rows]
        cells_by_version = {row.cell_version_id: row for row in cells}
        slots_by_role: dict[
            str, tuple[DecisionSurfaceCellVersion, EvidenceSlotVersion]
        ] = {}
        required_roles = {
            row.evidence_role for row in FIN01_S3_PROGRAM_CELL_CONTRACTS
        }
        for raw in catalog.list_versions(
            "canonical_evidence_slot_versions", case_id=case_id
        ):
            if raw.get("cell_version_id") not in cells_by_version:
                continue
            if not self._matches_scope(raw, case_id, principal):
                continue
            slot = EvidenceSlotVersion.model_validate(raw)
            if slot.evidence_role not in required_roles:
                continue
            if slot.evidence_role in slots_by_role:
                raise EvidenceServiceError("s3_evidence_role_slot_cardinality", 409)
            slots_by_role[slot.evidence_role] = (
                cells_by_version[slot.cell_version_id],
                slot,
            )
        if set(slots_by_role) != required_roles:
            raise EvidenceServiceError("s3_required_evidence_role_slot_missing", 409)
        for program_cell in FIN01_S3_PROGRAM_CELL_CONTRACTS:
            branch = branches_by_program_cell[program_cell.program_cell_id]
            cell, slot = slots_by_role[program_cell.evidence_role]
            if (
                branch.get("evidence_role") != program_cell.evidence_role
                or branch.get("owner_role") != program_cell.owner_role
                or cell.owner_role != program_cell.owner_role
                or slot.acceptance_role != program_cell.owner_role
                or branch.get("research_run_id") != runtime_plan["research_run_id"]
            ):
                raise EvidenceServiceError("s3_cell_branch_slot_semantic_mismatch", 409)
        return {
            "contract": contract,
            "branches_by_program_cell": branches_by_program_cell,
            "contexts_by_program_cell": contexts_by_program_cell,
            "slots_by_role": slots_by_role,
        }

    def _s3_gateway_preflight(
        self,
        *,
        request: EvidenceRequest,
        plan: ToolSelectionPlan,
        planner_step_id: str,
    ) -> S3ToolGatewayPreflightDecision:
        step = next(
            (row for row in plan.steps if row.planner_step_id == planner_step_id),
            None,
        )
        if step is None or not step.selected_tool_id or not step.selected_route_id:
            raise EvidenceServiceError("s3_tool_gateway_step_identity_missing", 409)
        entries = [
            row
            for row in self._s3_registry.entries
            if row.tool_id == step.selected_tool_id
            and step.selected_route_id in row.declared_route_ids
        ]
        if len(entries) != 1:
            raise EvidenceServiceError("s3_tool_gateway_registry_check_failed", 409)
        payload = {
            "evidence_request_id": request.request_id,
            "tool_selection_plan_id": plan.plan_id,
            "planner_step_id": planner_step_id,
            "selected_tool_id": step.selected_tool_id,
            "selected_route_id": step.selected_route_id,
            "tool_registry_check": "pass",
            "permission_check": "pass_planning_allowlist_only",
            "network_check": "not_required_local_route",
            "data_scope_check": "pass_fixture_metadata_only",
            "budget_check": "pass",
            "input_contract_check": "pass",
            "decision": "checks_pass_execution_not_admitted",
            "invocation_status": "not_executed",
        }
        digest = canonical_digest(payload)
        return S3ToolGatewayPreflightDecision(
            preflight_id=f"s3_tool_gateway_preflight_{digest[:24]}",
            preflight_digest=digest,
            **payload,
        )

    @staticmethod
    def _s3_graph_observation(
        *,
        program_cell_id: str,
        branch_version_ref: str,
        request: EvidenceRequest,
        bundle: CandidateBundle,
    ) -> S3GraphObservationVersion | None:
        graph_candidate = next(
            (
                row
                for row in bundle.candidates
                if row.source_role == "relationship_graph"
            ),
            None,
        )
        if graph_candidate is None:
            return None
        payload = {
            "program_cell_id": program_cell_id,
            "branch_version_ref": branch_version_ref,
            "evidence_request_id": request.request_id,
            "candidate_id": graph_candidate.candidate_id,
            "observation_class": "navigation_hypothesis_only",
            "relation_hypothesis": (
                "NVDA packaging dependency may require an underlying official-source "
                "counterevidence check; the graph relation is not itself Evidence."
            ),
            "source_followup_required": True,
            "direct_evidence_authorized": False,
            "numeric_authority": False,
        }
        digest = canonical_digest(payload)
        return S3GraphObservationVersion(
            observation_id=f"s3_graph_observation_{digest[:24]}",
            observation_digest=digest,
            **payload,
        )

    @staticmethod
    def _s3_source_followup(
        *,
        graph_observation: S3GraphObservationVersion | None,
        request: EvidenceRequest,
    ) -> S3SourceFollowupRequestVersion | None:
        if graph_observation is None:
            return None
        payload = {
            "program_cell_id": graph_observation.program_cell_id,
            "branch_version_ref": graph_observation.branch_version_ref,
            "originating_graph_observation_ref": graph_observation.observation_id,
            "parent_evidence_request_id": request.request_id,
            "target_route_id": "local_official_counterevidence_source_followup",
            "objective": (
                "Locate an underlying issuer or official-policy source for the "
                "graph navigation hypothesis before any Evidence classification."
            ),
            "status": "planned_local_followup_not_executed",
            "execution_admission": "not_admitted",
        }
        digest = canonical_digest(payload)
        return S3SourceFollowupRequestVersion(
            followup_request_id=f"s3_source_followup_{digest[:24]}",
            followup_request_digest=digest,
            **payload,
        )

    @staticmethod
    def _s3_promotion_assessment(
        *,
        evidence_role: str,
        request: EvidenceRequest,
        bundle: CandidateBundle,
        graph_observation: S3GraphObservationVersion | None,
    ) -> S3EvidencePromotionAssessment:
        candidate_ids = tuple(row.candidate_id for row in bundle.candidates)
        if bundle.status in {"retrieval_exhausted", "not_attempted_typed_stop"}:
            decision = "typed_gap_local_route_exhausted"
            candidate_refs: tuple[str, ...] = ()
            context_refs: tuple[str, ...] = ()
            gap_codes = bundle.typed_gap_codes or (
                bundle.exhaustion_status,
            )
        elif graph_observation is not None:
            decision = "context_only_graph_observation_source_followup_required"
            candidate_refs = ()
            context_refs = candidate_ids
            gap_codes = ("underlying_official_source_followup_required",)
        elif evidence_role == "revenue_capture":
            decision = "candidate_only_pending_T04_parser_numeric_lineage"
            candidate_refs = candidate_ids
            context_refs = ()
            gap_codes = ("T04_parser_numeric_lineage_required",)
        else:
            decision = "candidate_only_pending_claim_source_content_and_corroboration"
            candidate_refs = tuple(bundle.top_k_candidate_ids)
            context_refs = tuple(
                candidate_id
                for candidate_id in candidate_ids
                if candidate_id not in set(candidate_refs)
            )
            gap_codes = (
                "claim_scoped_source_content_and_corroboration_required",
            )
        payload = {
            "evidence_request_id": request.request_id,
            "candidate_bundle_id": bundle.bundle_id,
            "decision": decision,
            "candidate_refs": candidate_refs,
            "context_refs": context_refs,
            "rejected_refs": (),
            "typed_gap_codes": gap_codes,
            "accepted_evidence_refs": (),
            "evidence_gate_owner_ref": S3_EVIDENCE_SERVICE_OWNER_REF,
            "runtime_promotion_authorized": False,
            "writer_citable": False,
            "judgment_eligible": False,
            "persistence_authorized": False,
        }
        digest = canonical_digest(payload)
        return S3EvidencePromotionAssessment(
            assessment_id=f"s3_promotion_assessment_{digest[:24]}",
            assessment_digest=digest,
            **payload,
        )

    @staticmethod
    def _s3_sourcehunter_boundary(
        *,
        program_cell_id: str,
        branch_version_ref: str,
        request: EvidenceRequest,
        bundle: CandidateBundle,
        source_followup: S3SourceFollowupRequestVersion | None,
    ) -> S3SourceHunterBoundaryVersion:
        if program_cell_id == "bottleneck_counterevidence_and_what_would_change":
            status = "proposal_only_blocked_missing_separate_network_admission"
            trigger_reason = (
                "graph_observation_requires_underlying_official_source_and_the_"
                "local_followup_has_no_executed_candidate"
                if source_followup
                else "local_counterevidence_route_stopped_or_exhausted"
            )
        elif bundle.status in {"retrieval_exhausted", "not_attempted_typed_stop"}:
            status = "proposal_only_blocked_missing_separate_network_admission"
            trigger_reason = "local_route_stopped_or_exhausted"
        else:
            status = "not_eligible_until_parser_or_claim_binding"
            trigger_reason = "local_candidates_exist_but_are_not_Evidence"
        payload = {
            "program_cell_id": program_cell_id,
            "branch_version_ref": branch_version_ref,
            "evidence_request_id": request.request_id,
            "source_followup_request_ref": (
                source_followup.followup_request_id if source_followup else None
            ),
            "status": status,
            "trigger_reason": trigger_reason,
            "boundary_contract_ref": S3_SOURCEHUNTER_BOUNDARY_REF,
            "exact_network_admission_required": True,
            "network_execution_authorized": False,
            "external_tool_execution_authorized": False,
            "model_execution_authorized": False,
            "request_executed": False,
            "network_calls": 0,
        }
        digest = canonical_digest(payload)
        return S3SourceHunterBoundaryVersion(
            boundary_id=f"s3_sourcehunter_boundary_{digest[:24]}",
            boundary_digest=digest,
            **payload,
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
