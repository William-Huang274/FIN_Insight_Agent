from __future__ import annotations

import base64
import json
from typing import Any, TypeVar

import pytest
from pydantic import ValidationError

from sec_agent.agent_runtime.dell_agentic_contracts import (
    DELL_COVERAGE_OBLIGATION_IDS,
    AddTaskAction,
    AgenticPlanDeltaV1_2,
    AuthorityImpact,
    AvailableNextAction,
    BaselineSourcePlan,
    BudgetDelta,
    CancelTaskAction,
    CoverageObligation,
    CoverageStateSnapshot,
    DecisionArtifact,
    ExternalSourceIntent,
    GapEligibilityRequest,
    GapEligibilityReceipt,
    LocalEvidenceIntent,
    MinimumRouteObligation,
    ModelNodeAuthorityEntry,
    ModelNodeAuthorityMatrix,
    ModelVisibleContextManifest,
    ModifyTaskAction,
    ResearchPlan,
    ResearchTaskSpec,
    ReviewedEvidenceIntent,
    RuntimePolicySnapshot,
    RuntimeScope,
    RuntimeScopeAuthorizationRecord,
    RouteReplacement,
    TokenBudgetBasis,
    VerifiedArtifactRef,
    VerifiedArtifactRegistrySnapshot,
    ToolFailureReceipt,
    ZeroModelTransportAuditEvent,
    authorize_gap_eligibility,
    canonical_digest,
    coverage_state_snapshot,
    issue_runtime_scope_authorization_record,
    payload_without,
    prepare_provider_envelope_for_persistence,
    research_plan_graph_digest,
    research_objective_digest,
    sanitize_provider_envelope,
    task_assignment_authority_digest,
    validate_public_narrative_text,
    validate_runtime_scope_authorization,
    validate_agentic_plan_delta_reference_integrity,
    validate_research_plan_reference_integrity,
    validate_zero_model_runtime_boundary,
    wave0a_zero_model_transport_gateway,
)


ZERO = "0" * 64
D1 = "1" * 64
D2 = "2" * 64
D3 = "3" * 64
D4 = "4" * 64
D5 = "5" * 64
REGISTRY_RESOLVER_REF = "resolver:host:test:verified-artifacts"
M = TypeVar("M")


def _signed(model: type[M], digest_field: str, **values: Any) -> M:
    provisional = model.model_construct(**values, **{digest_field: ZERO})
    digest = canonical_digest(payload_without(provisional, digest_field))
    return model(**values, **{digest_field: digest})


def _model_values(model: Any, *excluded: str) -> dict[str, Any]:
    return {
        field_name: getattr(model, field_name)
        for field_name in type(model).model_fields
        if field_name not in excluded
    }


class _StaticVerifiedArtifactRegistryResolver:
    resolver_ref = REGISTRY_RESOLVER_REF

    def __init__(
        self,
        snapshot: VerifiedArtifactRegistrySnapshot | None,
    ) -> None:
        self.snapshot = snapshot
        self.calls: list[str] = []

    def resolve_current_verified_artifact_registry(
        self,
        *,
        case_id: str,
    ) -> VerifiedArtifactRegistrySnapshot | None:
        self.calls.append(case_id)
        return self.snapshot


def _registry_resolver(
    snapshot: VerifiedArtifactRegistrySnapshot | None,
) -> _StaticVerifiedArtifactRegistryResolver:
    return _StaticVerifiedArtifactRegistryResolver(snapshot)


def _coverage(
    *,
    reachable_task_id: str = "task:dell:all",
    satisfaction: str = "uncovered",
) -> tuple[CoverageObligation, ...]:
    return tuple(
        CoverageObligation(
            obligation_id=obligation_id,
            title=f"Dell coverage {obligation_id}",
            research_surface=f"Research surface for {obligation_id}",
            minimum_completion_semantics=(
                f"Complete {obligation_id} with source-bound research artifacts"
            ),
            materiality="high",
            registered=True,
            plan_reachable=True,
            reachable_task_ids=(reachable_task_id,),
            evidence_satisfaction=satisfaction,
        )
        for obligation_id in DELL_COVERAGE_OBLIGATION_IDS
    )


def _task(*, status: str = "planned", objective_suffix: str = "base") -> ResearchTaskSpec:
    return ResearchTaskSpec(
        task_id="task:dell:all",
        owner_role="role:lead_specialist",
        objective=f"Research all Dell obligations in a bounded vertical: {objective_suffix}",
        dependency_ids=(),
        coverage_obligation_ids=DELL_COVERAGE_OBLIGATION_IDS,
        success_criteria=("Every material assertion is bound to a typed source",),
        requested_capability_refs=("cap:s1-search", "cap:s2-facts"),
        required_authority_refs=("authority:research-read",),
        expected_output_kinds=("branch_notebook", "claim_ledger"),
        materiality="high",
        status=status,
    )


def _source_plan(
    *,
    route_suffix: str = "base",
    policy_digest: str = D3,
) -> BaselineSourcePlan:
    routes: list[MinimumRouteObligation] = []
    for obligation_id in DELL_COVERAGE_OBLIGATION_IDS:
        routes.append(
            _signed(
                MinimumRouteObligation,
                "route_digest",
                route_obligation_id=f"route:{obligation_id}:{route_suffix}",
                coverage_obligation_id=obligation_id,
                requirement="required",
                route_kind="reviewed_evidence",
                semantic_source_family_refs=("family:issuer-primary",),
                entity_refs=("issuer:DELL",),
                period_intents=("latest-reported-quarter",),
                metric_refs=(),
                required_authority_refs=("authority:reviewed-read",),
                substitution_policy="qualified_replacement",
                acceptable_replacement_route_kinds=(
                    "reviewed_evidence",
                    "local_candidate",
                ),
                replacement_conditions=(
                    "Replacement preserves issuer, period, and source authority",
                ),
                answer_free=True,
            )
        )
    return _signed(
        BaselineSourcePlan,
        "source_plan_digest",
        source_plan_id=f"source-plan:dell:{route_suffix}",
        case_id="case:dell:vertical",
        case_version="FIN-0.1.3",
        research_as_of="2026-09-03",
        coverage_obligation_ids=DELL_COVERAGE_OBLIGATION_IDS,
        route_obligations=tuple(routes),
        inventory_snapshot_digest=D1,
        catalog_digest=D2,
        policy_digest=policy_digest,
        answer_free=True,
    )


def _plan(
    *,
    revision: int = 0,
    task: ResearchTaskSpec | None = None,
    coverage: tuple[CoverageObligation, ...] | None = None,
    prior_plan_digest: str | None = None,
    source_plan: BaselineSourcePlan | None = None,
    status: str = "accepted",
) -> ResearchPlan:
    source_plan = source_plan or _source_plan()
    return _signed(
        ResearchPlan,
        "plan_digest",
        plan_id="plan:dell:vertical",
        revision=revision,
        status=status,
        case_id="case:dell:vertical",
        baseline_source_plan_digest=source_plan.source_plan_digest,
        catalog_digest=D2,
        policy_digest=D3,
        authority_matrix_digest=D4,
        budget_basis_digest=D5,
        prior_plan_digest=prior_plan_digest,
        coverage_obligations=coverage or _coverage(),
        tasks=(task or _task(),),
    )


def _no_authority_impact() -> AuthorityImpact:
    return AuthorityImpact(effect="none", reason="No authority change")


def _zero_budget_delta() -> BudgetDelta:
    return BudgetDelta(reason="No budget change")


def _authority_entries() -> tuple[ModelNodeAuthorityEntry, ...]:
    kinds = (
        "lead",
        "specialist",
        "counter",
        "semantic_research_verifier",
        "writer",
        "final_semantic_verifier",
    )
    return tuple(
        ModelNodeAuthorityEntry(
            node_id=f"node:{kind}",
            node_kind=kind,
            node_purpose=f"Perform the bounded {kind} responsibility",
            input_scale="No model input is authorized in Wave 0A",
            required_outputs=(f"artifact:{kind}",),
            schema_burden="Strict typed output is required",
            materiality_quality_risk="Material Dell research risk remains gated",
            comparable_run_evidence_refs=(),
            reasoning_profile="unassigned",
            stop_and_truncation_behavior="Fail before provider transport",
            repair_policy="No model-assisted repair is authorized",
            retry_policy="Do not retry a non-authorized node",
        )
        for kind in kinds
    )


def _runtime_policy() -> RuntimePolicySnapshot:
    return _signed(
        RuntimePolicySnapshot,
        "policy_digest",
        policy_snapshot_id="policy:dell:wave0a",
        case_id="case:dell:vertical",
        case_version="FIN-0.1.3",
        research_as_of="2026-09-03",
        data_snapshot_digest=D1,
        catalog_digest=D2,
        disclosure_policy_digest=D4,
        allowed_branch_refs=("branch:dell",),
        allowed_authority_class_refs=(
            "authority:research-read",
            "authority:boundary-acceptance",
        ),
    )


def test_canonical_digest_is_key_order_stable_and_bare_hex() -> None:
    left = canonical_digest({"b": [2, 1], "a": "Dell"})
    right = canonical_digest({"a": "Dell", "b": [2, 1]})
    assert left == right
    assert len(left) == 64
    assert not left.startswith("sha256:")


def test_coverage_registration_reachability_and_evidence_are_separate() -> None:
    obligation = _coverage()[0]
    assert obligation.registered is True
    assert obligation.plan_reachable is True
    assert obligation.evidence_satisfaction == "uncovered"

    with pytest.raises(ValidationError, match="covered_obligation_requires"):
        CoverageObligation(
            **{
                **obligation.model_dump(mode="python"),
                "evidence_satisfaction": "covered",
            }
        )


def test_accepted_dell_plan_requires_all_nine_reachable_obligations() -> None:
    plan = _plan()
    assert len(plan.coverage_obligations) == 9
    assert all(item.plan_reachable for item in plan.coverage_obligations)
    assert all(item.evidence_satisfaction == "uncovered" for item in plan.coverage_obligations)

    partial_coverage = plan.coverage_obligations[:-1]
    partial_task = _task().model_copy(
        update={"coverage_obligation_ids": DELL_COVERAGE_OBLIGATION_IDS[:-1]}
    )
    with pytest.raises(ValidationError, match="coverage_catalog_incomplete"):
        _plan(task=partial_task, coverage=partial_coverage)


def test_plan_rejects_cycle_and_stale_digest() -> None:
    source_plan = _source_plan()
    task_a = _task().model_copy(
        update={"task_id": "task:a", "dependency_ids": ("task:b",)}
    )
    task_b = _task().model_copy(
        update={"task_id": "task:b", "dependency_ids": ("task:a",)}
    )
    coverage = tuple(
        item.model_copy(update={"reachable_task_ids": ("task:a",)})
        for item in _coverage()
    )
    values = {
        "plan_id": "plan:dell:vertical",
        "revision": 0,
        "status": "draft",
        "case_id": "case:dell:vertical",
        "baseline_source_plan_digest": source_plan.source_plan_digest,
        "catalog_digest": D2,
        "policy_digest": D3,
        "authority_matrix_digest": D4,
        "budget_basis_digest": D5,
        "prior_plan_digest": None,
        "coverage_obligations": coverage,
        "tasks": (task_a, task_b),
    }
    provisional = ResearchPlan.model_construct(**values, plan_digest=ZERO)
    with pytest.raises(ValidationError, match="dependency_cycle"):
        ResearchPlan(
            **values,
            plan_digest=canonical_digest(payload_without(provisional, "plan_digest")),
        )

    valid = _plan()
    with pytest.raises(ValidationError, match="plan_digest_mismatch"):
        ResearchPlan(**{**valid.model_dump(mode="python"), "plan_digest": ZERO})


def test_agentic_delta_binds_explicit_successor_and_all_digests() -> None:
    source_plan = _source_plan()
    base = _plan(source_plan=source_plan)
    successor_task = _task(status="completed", objective_suffix="completed")
    successor = _plan(
        revision=1,
        task=successor_task,
        prior_plan_digest=base.plan_digest,
        source_plan=source_plan,
    )
    before = tuple(coverage_state_snapshot(item) for item in base.coverage_obligations)
    after = tuple(coverage_state_snapshot(item) for item in successor.coverage_obligations)
    action = ModifyTaskAction(
        action_id="delta-action:modify:1",
        reason="The task reached its typed completion criteria",
        feedback_receipt_refs=("feedback:completion",),
        coverage_before=before,
        coverage_after=after,
        authority_impact=_no_authority_impact(),
        budget_delta=_zero_budget_delta(),
        target_task_id="task:dell:all",
        changed_fields=("objective", "status"),
        successor_task=successor_task,
    )
    delta = _signed(
        AgenticPlanDeltaV1_2,
        "delta_digest",
        delta_id="plan-delta:dell:1",
        base_plan=base,
        successor_plan=successor,
        baseline_source_plan_before=source_plan,
        baseline_source_plan_after=source_plan,
        add_actions=(),
        modify_actions=(action,),
        defer_actions=(),
        cancel_actions=(),
        coverage_before=before,
        coverage_after=after,
        route_replacements=(),
        authority_impact=_no_authority_impact(),
        budget_delta=_zero_budget_delta(),
        catalog_digest=D2,
        policy_digest=D3,
        authority_matrix_digest=D4,
        budget_basis_digest=D5,
        accepted_plan_digest=successor.plan_digest,
        resulting_graph_digest=research_plan_graph_digest(successor),
    )
    assert delta.successor_plan.prior_plan_digest == base.plan_digest
    assert delta.accepted_plan_digest == successor.plan_digest

    with pytest.raises(ValidationError, match="accepted_plan_digest_mismatch"):
        _signed(
            AgenticPlanDeltaV1_2,
            "delta_digest",
            **{
                **_model_values(delta, "delta_digest"),
                "accepted_plan_digest": ZERO,
            },
        )


def test_plan_delta_route_proofs_are_resolved_from_current_host_registry() -> None:
    before_source = _source_plan(route_suffix="before")
    removed = before_source.route_obligations[0]
    successor_route = _signed(
        MinimumRouteObligation,
        "route_digest",
        **{
            **_model_values(
                removed,
                "route_digest",
                "route_obligation_id",
            ),
            "route_obligation_id": "route:Q1_ISSUER_TRUTH:qualified-successor",
        },
    )
    after_source = _signed(
        BaselineSourcePlan,
        "source_plan_digest",
        **{
            **_model_values(
                before_source,
                "source_plan_digest",
                "source_plan_id",
                "route_obligations",
            ),
            "source_plan_id": "source-plan:dell:after-qualified-replacement",
            "route_obligations": (
                successor_route,
                *before_source.route_obligations[1:],
            ),
        },
    )
    base = _plan(source_plan=before_source)
    successor = _plan(
        revision=1,
        prior_plan_digest=base.plan_digest,
        source_plan=after_source,
    )
    replacement = RouteReplacement(
        removed_route_obligation_id=removed.route_obligation_id,
        successor_route_obligation_ids=(successor_route.route_obligation_id,),
        reason="Replace the required route only after host-verified disposition.",
        disposition_receipt_refs=("receipt:route-replacement:disposition",),
        condition_proof_receipt_refs=("receipt:route-replacement:condition",),
    )
    delta = _signed(
        AgenticPlanDeltaV1_2,
        "delta_digest",
        delta_id="plan-delta:dell:route-replacement",
        base_plan=base,
        successor_plan=successor,
        baseline_source_plan_before=before_source,
        baseline_source_plan_after=after_source,
        add_actions=(),
        modify_actions=(),
        defer_actions=(),
        cancel_actions=(),
        coverage_before=tuple(
            coverage_state_snapshot(item) for item in base.coverage_obligations
        ),
        coverage_after=tuple(
            coverage_state_snapshot(item) for item in successor.coverage_obligations
        ),
        route_replacements=(replacement,),
        authority_impact=_no_authority_impact(),
        budget_delta=_zero_budget_delta(),
        catalog_digest=successor.catalog_digest,
        policy_digest=successor.policy_digest,
        authority_matrix_digest=successor.authority_matrix_digest,
        budget_basis_digest=successor.budget_basis_digest,
        accepted_plan_digest=successor.plan_digest,
        resulting_graph_digest=research_plan_graph_digest(successor),
    )
    route_digests = (removed.route_digest, successor_route.route_digest)

    def artifact(
        *,
        artifact_ref: str,
        artifact_kind: str,
        bound_artifact_digests: tuple[str, ...],
    ) -> VerifiedArtifactRef:
        return _signed(
            VerifiedArtifactRef,
            "artifact_digest",
            artifact_ref=artifact_ref,
            artifact_kind=artifact_kind,
            case_id=after_source.case_id,
            baseline_source_plan_digest=after_source.source_plan_digest,
            inventory_snapshot_digest=after_source.inventory_snapshot_digest,
            catalog_digest=after_source.catalog_digest,
            policy_digest=after_source.policy_digest,
            coverage_obligation_ids=(removed.coverage_obligation_id,),
            task_ids=("task:dell:all",),
            route_obligation_ids=(
                removed.route_obligation_id,
                successor_route.route_obligation_id,
            ),
            bound_artifact_digests=bound_artifact_digests,
            canonical_artifact_digest=canonical_digest(
                {"canonical": artifact_ref}
            ),
            outcome="qualified",
            terminal=True,
        )

    host_current_registry = _signed(
        VerifiedArtifactRegistrySnapshot,
        "registry_digest",
        registry_id="registry:dell:host-current-with-proofs",
        resolver_ref=REGISTRY_RESOLVER_REF,
        store_revision=1,
        canonical_tip_digest=canonical_digest({"registry": "host-current-with-proofs"}),
        case_id=after_source.case_id,
        baseline_source_plan_digest=after_source.source_plan_digest,
        inventory_snapshot_digest=after_source.inventory_snapshot_digest,
        catalog_digest=after_source.catalog_digest,
        policy_digest=after_source.policy_digest,
        artifacts=(
            artifact(
                artifact_ref=replacement.disposition_receipt_refs[0],
                artifact_kind="route_replacement_disposition",
                bound_artifact_digests=route_digests,
            ),
            artifact(
                artifact_ref=replacement.condition_proof_receipt_refs[0],
                artifact_kind="route_replacement_condition",
                bound_artifact_digests=(
                    *route_digests,
                    *(canonical_digest(item) for item in removed.replacement_conditions),
                ),
            ),
        ),
    )
    current_resolver = _registry_resolver(host_current_registry)
    assert (
        validate_agentic_plan_delta_reference_integrity(
            delta,
            registry_resolver=current_resolver,
        )
        == delta
    )
    assert current_resolver.calls == [after_source.case_id]

    forged_delta = delta.model_copy(update={"route_replacements": ()})
    with pytest.raises(
        ValidationError,
        match=(
            "required_minimum_route_silently_removed|"
            "agentic_plan_delta_digest_mismatch"
        ),
    ):
        validate_agentic_plan_delta_reference_integrity(
            forged_delta,
            registry_resolver=_registry_resolver(host_current_registry),
        )

    valid_disposition = host_current_registry.artifacts[0]
    forged_artifact_body = {
        **_model_values(
            valid_disposition,
            "artifact_digest",
            "canonical_artifact_digest",
        ),
        "canonical_artifact_digest": None,
    }
    forged_artifact = VerifiedArtifactRef.model_construct(
        **forged_artifact_body,
        artifact_digest=canonical_digest(forged_artifact_body),
    )
    forged_registry_body = {
        **_model_values(
            host_current_registry,
            "registry_digest",
            "artifacts",
        ),
        "artifacts": (
            forged_artifact,
            *host_current_registry.artifacts[1:],
        ),
    }
    forged_registry = VerifiedArtifactRegistrySnapshot.model_construct(
        **forged_registry_body,
        registry_digest=canonical_digest(forged_registry_body),
    )
    with pytest.raises(ValidationError, match="canonical_artifact_digest"):
        validate_agentic_plan_delta_reference_integrity(
            delta,
            registry_resolver=_registry_resolver(forged_registry),
        )

    with pytest.raises(TypeError, match="verified_artifact_registry_resolver_required"):
        validate_agentic_plan_delta_reference_integrity(
            delta,
            registry_resolver=host_current_registry,  # type: ignore[arg-type]
        )

    current_without_caller_proofs = _signed(
        VerifiedArtifactRegistrySnapshot,
        "registry_digest",
        **{
            **_model_values(
                host_current_registry,
                "registry_digest",
                "registry_id",
                "store_revision",
                "canonical_tip_digest",
                "artifacts",
            ),
            "registry_id": "registry:dell:host-current",
            "store_revision": 2,
            "canonical_tip_digest": canonical_digest({"registry": "current"}),
            "artifacts": (),
        },
    )
    with pytest.raises(ValueError, match="missing_or_wrong_kind"):
        validate_agentic_plan_delta_reference_integrity(
            delta,
            registry_resolver=_registry_resolver(current_without_caller_proofs),
        )


def test_material_cancellation_without_replacement_or_disposition_fails() -> None:
    task = _task(status="cancelled")
    before = (
        CoverageStateSnapshot(
            obligation_id="Q1_ISSUER_TRUTH",
            materiality="high",
            registered=True,
            plan_reachable=True,
            evidence_satisfaction="uncovered",
        ),
    )
    after = (
        before[0].model_copy(update={"plan_reachable": False}),
    )
    values = {
        "action_id": "delta-action:cancel:1",
        "reason": "The original task must be cancelled after a material defect",
        "feedback_receipt_refs": ("feedback:material-defect",),
        "coverage_before": before,
        "coverage_after": after,
        "authority_impact": _no_authority_impact(),
        "budget_delta": _zero_budget_delta(),
        "target_task_id": task.task_id,
        "successor_task": task,
        "replacement_task_ids": (),
        "human_or_verifier_disposition_receipt_refs": (),
    }
    with pytest.raises(ValidationError, match="cancellation_without_disposition"):
        CancelTaskAction(**values)

    accepted = CancelTaskAction(
        **{
            **values,
            "human_or_verifier_disposition_receipt_refs": ("verifier:cancel-ok",),
        }
    )
    assert accepted.successor_task.status == "cancelled"


def test_required_minimum_route_cannot_be_silently_removed() -> None:
    before_source = _source_plan(route_suffix="before")
    after_source = _source_plan(route_suffix="after")
    base = _plan(source_plan=before_source)
    successor = _plan(
        revision=1,
        prior_plan_digest=base.plan_digest,
        source_plan=after_source,
    )
    before = tuple(coverage_state_snapshot(item) for item in base.coverage_obligations)
    after = tuple(coverage_state_snapshot(item) for item in successor.coverage_obligations)
    with pytest.raises(ValidationError, match="required_minimum_route_silently_removed"):
        _signed(
            AgenticPlanDeltaV1_2,
            "delta_digest",
            delta_id="plan-delta:dell:routes",
            base_plan=base,
            successor_plan=successor,
            baseline_source_plan_before=before_source,
            baseline_source_plan_after=after_source,
            add_actions=(),
            modify_actions=(),
            defer_actions=(),
            cancel_actions=(),
            coverage_before=before,
            coverage_after=after,
            route_replacements=(),
            authority_impact=_no_authority_impact(),
            budget_delta=_zero_budget_delta(),
            catalog_digest=D2,
            policy_digest=D3,
            authority_matrix_digest=D4,
            budget_basis_digest=D5,
            accepted_plan_digest=successor.plan_digest,
            resulting_graph_digest=research_plan_graph_digest(successor),
        )


def test_runtime_policy_and_authority_matrix_default_deny_paid_execution() -> None:
    policy = _runtime_policy()
    assert policy.paid_execution_authority_status == "not_authorized"
    assert policy.paid_execution_owner_decision_ref is None
    assert policy.hitl_may_grant_or_elevate_paid_authority is False

    matrix = _signed(
        ModelNodeAuthorityMatrix,
        "matrix_digest",
        matrix_id="authority-matrix:dell:wave0a",
        policy_digest=policy.policy_digest,
        entries=_authority_entries(),
    )
    assert all(entry.status == "not_authorized" for entry in matrix.entries)
    assert matrix.hitl_may_grant_or_elevate_paid_authority is False
    assert "A03" not in json.dumps(
        RuntimePolicySnapshot.model_json_schema(), sort_keys=True
    )

    with pytest.raises(ValidationError, match="paid_transport_binding"):
        ModelNodeAuthorityEntry(
            **{
                **_authority_entries()[0].model_dump(mode="python"),
                "provider_ref": "provider:deepseek",
            }
        )


def test_sealed_scope_and_provider_intents_make_lane_mixing_unrepresentable() -> None:
    scope = _signed(
        RuntimeScope,
        "scope_digest",
        case_id="case:dell:vertical",
        session_id="session:dell:1",
        research_run_id="research-run:dell:1",
        run_invocation_id="run-invocation:dell:1",
        action_attempt_id="action-attempt:dell:1",
        agent_id="agent:specialist:1",
        agent_role="evidence_specialist",
        task_id="task:dell:all",
        task_kind="dell_full_vertical_research",
        case_version="FIN-0.1.3",
        research_as_of="2026-09-03",
        data_snapshot_digest=D1,
        policy_digest=D3,
        disclosure_policy_digest=D4,
        authority_matrix_digest=D4,
        branch_scope_refs=("branch:dell",),
        permission_refs=("authority:research-read",),
        canonical_issuer_selectors=("issuer:DELL",),
        physical_source_role_selectors=("role:issuer-primary",),
        physical_route_selectors=("route:sec-html",),
        physical_lane_selectors=("lane:prose",),
        method_digest=D5,
        skill_digests=(),
        idempotency_key="idempotency:dell:attempt:1",
        timeout_ms=60_000,
        rate_and_cost_boundary_digest=D2,
    )
    assert scope.sealed is True and scope.provider_visible is False

    reviewed_values = {
        "query": "Dell latest AI server orders",
        "purpose": "Find reviewed issuer evidence for the latest quarter",
        "entity_refs": ("issuer:DELL",),
        "period_intents": ("latest-quarter",),
        "expected_information_gain": "Confirm the reported demand baseline",
        "topic_refs": ("topic:orders",),
    }
    ReviewedEvidenceIntent(**reviewed_values)
    with pytest.raises(ValidationError, match="Extra inputs"):
        ReviewedEvidenceIntent(**reviewed_values, route_ids=("route:sec",))

    local_values = {
        "query": "Dell backlog and orders",
        "purpose": "Retrieve bounded local Candidate passages",
        "entity_refs": ("issuer:DELL",),
        "period_intents": ("latest-quarter",),
        "expected_information_gain": "Locate candidate primary statements",
        "semantic_source_family_refs": ("family:issuer-primary",),
    }
    LocalEvidenceIntent(**local_values)
    with pytest.raises(ValidationError, match="Extra inputs"):
        LocalEvidenceIntent(**local_values, domain_allowlist=("sec.gov",))

    external_values = {
        "query": "GB300 production availability",
        "purpose": "Discover current external supplier evidence",
        "entity_refs": ("issuer:NVDA",),
        "period_intents": ("current",),
        "expected_information_gain": "Establish architecture ramp timing",
        "semantic_source_family_refs": ("family:supplier-primary",),
        "domain_allowlist": ("nvidia.com",),
    }
    ExternalSourceIntent(**external_values)
    with pytest.raises(ValidationError, match="Extra inputs"):
        ExternalSourceIntent(
            **external_values,
            physical_route_selectors=("route:local",),
        )

    for intent in (ReviewedEvidenceIntent, LocalEvidenceIntent, ExternalSourceIntent):
        schema = json.dumps(intent.model_json_schema(), sort_keys=True)
        assert "action_attempt_id" not in schema
        assert "physical_route_selectors" not in schema
        assert "paid_model_transport_authorized" not in schema


def test_tool_failure_empty_and_scope_exhausted_never_become_public_gap() -> None:
    action = AvailableNextAction(
        action="request_data_inventory",
        reason="Inspect the answer-free source inventory",
        expected_information_gain="high",
    )
    for outcome in ("tool_failure", "empty", "scope_exhausted"):
        receipt = _signed(
            ToolFailureReceipt,
            "receipt_digest",
            failure_receipt_id=f"failure:{outcome}",
            action_attempt_id=f"action-attempt:{outcome}",
            observed_outcome=outcome,
            failure_code="NO_ELIGIBLE_SELECTOR",
            category="semantic_validation",
            owning_plane="runtime_data_binding",
            owning_stage="selector_compilation",
            retryability="correctable_with_new_information",
            permitted_next_actions=(action,),
        )
        assert receipt.public_gap_eligible is False
        assert "public_information_absent" in receipt.forbidden_interpretations

    with pytest.raises(ValidationError, match="cannot_directly_request_public_gap"):
        _signed(
            ToolFailureReceipt,
            "receipt_digest",
            failure_receipt_id="failure:bad-gap-action",
            action_attempt_id="action-attempt:bad-gap-action",
            observed_outcome="empty",
            failure_code="EMPTY",
            category="semantic_validation",
            owning_plane="runtime_data_binding",
            owning_stage="search",
            retryability="correctable_with_new_information",
            permitted_next_actions=(
                AvailableNextAction(
                    action="request_gap_eligibility",
                    reason="Incorrectly jump to a gap",
                    target_ref="need:dell:1",
                ),
            ),
        )


def test_public_gap_requires_complete_route_and_independent_review_proof() -> None:
    policy = _runtime_policy()
    baseline = _source_plan(policy_digest=policy.policy_digest)
    proposition = "proposition:dell:units"
    coverage_id = "Q3_UNITS_ASP_PVM"
    route = next(
        item
        for item in baseline.route_obligations
        if item.coverage_obligation_id == coverage_id
    )
    refs = {
        "need": "need:dell:units",
        "plan": "requirement-plan:dell",
        "local": "receipt:local-integrity",
        "compiler": "receipt:compiler",
        "terminal": "receipt:route-terminal",
        "discovery": "receipt:route-discovery",
        "capture": "receipt:route-capture",
        "execution": "receipt:route-execution",
        "route_candidate": "receipt:route-candidate-disposition",
        "candidate": "receipt:candidate-disposition",
        "transport": "receipt:transport",
        "budget": "receipt:budget-stop",
        "defects": "receipt:owned-defect-snapshot",
        "qualification": "receipt:reviewer-qualification",
        "review": "receipt:independent-review",
    }
    request = _signed(
        GapEligibilityRequest,
        "request_digest",
        gap_request_id="gap-request:dell:1",
        material_proposition_ref=proposition,
        original_actor_ref="agent:specialist:1",
        evidence_need_refs=(refs["need"],),
        material_requirement_plan_refs=(refs["plan"],),
        coverage_obligation_ids=(coverage_id,),
        local_integrity_receipt_refs=(refs["local"],),
        source_family_compilation_receipt_refs=(refs["compiler"],),
        required_route_terminal_receipt_refs=(refs["terminal"],),
        candidate_disposition_receipt_refs=(refs["candidate"],),
        transport_and_alternative_disposition_refs=(refs["transport"],),
        budget_stop_disposition_refs=(refs["budget"],),
        owned_defect_snapshot_receipt_ref=refs["defects"],
        reviewer_qualification_receipt_ref=refs["qualification"],
        independent_review_receipt_ref=refs["review"],
    )

    def artifact(
        ref: str,
        kind: str,
        *,
        outcome: str = "qualified",
        bound: tuple[str, ...] = (),
        routes: tuple[str, ...] = (),
        actor: str | None = None,
        producers: tuple[str, ...] = ("agent:specialist:1",),
        reviewed_producers: tuple[str, ...] = (),
        independent_of: tuple[str, ...] = (),
        owner_classes: tuple[str, ...] = (),
        open_defects: tuple[str, ...] = (),
        authority_class: str | None = None,
        discovery_ref: str | None = None,
        capture_ref: str | None = None,
        execution_ref: str | None = None,
        route_candidate_ref: str | None = None,
    ) -> VerifiedArtifactRef:
        return _signed(
            VerifiedArtifactRef,
            "artifact_digest",
            artifact_ref=ref,
            artifact_kind=kind,
            case_id=baseline.case_id,
            baseline_source_plan_digest=baseline.source_plan_digest,
            inventory_snapshot_digest=baseline.inventory_snapshot_digest,
            catalog_digest=baseline.catalog_digest,
            policy_digest=baseline.policy_digest,
            coverage_obligation_ids=(coverage_id,),
            task_ids=("task:dell:all",),
            route_obligation_ids=routes,
            material_proposition_refs=(proposition,),
            bound_artifact_digests=bound,
            canonical_artifact_digest=canonical_digest({"canonical_artifact": ref}),
            conflict_group_ref=None,
            conflict_side=None,
            actor_ref=actor,
            producer_actor_refs=producers,
            independent_of_actor_refs=independent_of,
            reviewed_producer_actor_refs=reviewed_producers,
            checked_owner_classes=owner_classes,
            open_owned_defect_refs=open_defects,
            outcome=outcome,
            terminal=True,
            defect_status="not_applicable",
            authority_class_ref=authority_class,
            route_discovery_receipt_ref=discovery_ref,
            route_capture_receipt_ref=capture_ref,
            route_execution_receipt_ref=execution_ref,
            route_candidate_disposition_receipt_ref=route_candidate_ref,
        )

    non_review = (
        artifact(refs["need"], "evidence_need"),
        artifact(
            refs["plan"],
            "material_requirement_plan",
            bound=(baseline.source_plan_digest,),
        ),
        artifact(refs["local"], "local_integrity"),
        artifact(refs["compiler"], "source_family_compilation"),
        artifact(refs["candidate"], "candidate_disposition"),
        artifact(refs["transport"], "transport_alternative_disposition"),
        artifact(refs["budget"], "budget_stop_disposition"),
        artifact(
            refs["discovery"],
            "route_discovery",
            bound=(route.route_digest,),
            routes=(route.route_obligation_id,),
        ),
        artifact(
            refs["capture"],
            "route_capture",
            bound=(route.route_digest,),
            routes=(route.route_obligation_id,),
        ),
        artifact(
            refs["execution"],
            "route_execution",
            bound=(route.route_digest,),
            routes=(route.route_obligation_id,),
        ),
        artifact(
            refs["route_candidate"],
            "route_candidate_disposition",
            bound=(route.route_digest,),
            routes=(route.route_obligation_id,),
        ),
        artifact(
            refs["terminal"],
            "required_route_terminal",
            outcome="exhausted_no_qualifying_result",
            bound=(route.route_digest,),
            routes=(route.route_obligation_id,),
            discovery_ref=refs["discovery"],
            capture_ref=refs["capture"],
            execution_ref=refs["execution"],
            route_candidate_ref=refs["route_candidate"],
        ),
        artifact(
            refs["defects"],
            "owned_defect_snapshot",
            routes=(route.route_obligation_id,),
            producers=("runtime:integrity",),
            owner_classes=(
                "local_data",
                "retrieval",
                "transport",
                "evidence_admission",
                "permission_configuration",
            ),
        ),
    )
    qualification = artifact(
        refs["qualification"],
        "reviewer_qualification",
        actor="reviewer:independent:1",
        producers=("runtime:governance",),
        authority_class="authority:boundary-acceptance",
    )
    proof_set_digest = canonical_digest(
        sorted((item.artifact_ref, item.artifact_digest) for item in non_review)
    )
    review = artifact(
        refs["review"],
        "independent_gap_review",
        actor="reviewer:independent:1",
        producers=("reviewer:independent:1",),
        reviewed_producers=("agent:specialist:1", "runtime:integrity"),
        independent_of=("agent:specialist:1", "runtime:integrity"),
        bound=(request.request_digest, proof_set_digest, qualification.artifact_digest),
    )
    registry = _signed(
        VerifiedArtifactRegistrySnapshot,
        "registry_digest",
        registry_id="registry:dell:gap:1",
        resolver_ref=REGISTRY_RESOLVER_REF,
        store_revision=1,
        canonical_tip_digest=canonical_digest({"registry": "dell:gap:1"}),
        case_id=baseline.case_id,
        baseline_source_plan_digest=baseline.source_plan_digest,
        inventory_snapshot_digest=baseline.inventory_snapshot_digest,
        catalog_digest=baseline.catalog_digest,
        policy_digest=baseline.policy_digest,
        artifacts=(*non_review, qualification, review),
    )

    eligible = authorize_gap_eligibility(
        request,
        baseline_source_plan=baseline,
        registry_resolver=_registry_resolver(registry),
        policy=policy,
        gap_receipt_id="gap:dell:1",
    )
    assert isinstance(eligible, GapEligibilityReceipt)
    assert eligible.public_gap_eligible is True
    assert eligible.proof_set_digest == proof_set_digest

    with pytest.raises(TypeError, match="verified_artifact_registry_resolver_required"):
        authorize_gap_eligibility(
            request,
            baseline_source_plan=baseline,
            registry_resolver=registry,  # type: ignore[arg-type]
            policy=policy,
            gap_receipt_id="gap:dell:caller-supplied-registry",
        )

    open_owned_defect = _signed(
        VerifiedArtifactRef,
        "artifact_digest",
        artifact_ref="defect:dell:retrieval-open",
        artifact_kind="owned_defect",
        case_id=baseline.case_id,
        baseline_source_plan_digest=baseline.source_plan_digest,
        inventory_snapshot_digest=baseline.inventory_snapshot_digest,
        catalog_digest=baseline.catalog_digest,
        policy_digest=baseline.policy_digest,
        coverage_obligation_ids=(),
        task_ids=("task:dell:all",),
        route_obligation_ids=(route.route_obligation_id,),
        material_proposition_refs=(),
        bound_artifact_digests=(),
        canonical_artifact_digest=canonical_digest(
            {"canonical_artifact": "open-retrieval-defect"}
        ),
        conflict_group_ref=None,
        conflict_side=None,
        actor_ref=None,
        producer_actor_refs=("runtime:retrieval",),
        independent_of_actor_refs=(),
        reviewed_producer_actor_refs=(),
        checked_owner_classes=(),
        open_owned_defect_refs=(),
        outcome="open",
        terminal=False,
        defect_status="open",
        authority_class_ref=None,
        route_discovery_receipt_ref=None,
        route_capture_receipt_ref=None,
        route_execution_receipt_ref=None,
        route_candidate_disposition_receipt_ref=None,
    )
    registry_with_open_defect = _signed(
        VerifiedArtifactRegistrySnapshot,
        "registry_digest",
        registry_id="registry:dell:gap:open-defect",
        resolver_ref=REGISTRY_RESOLVER_REF,
        store_revision=2,
        canonical_tip_digest=canonical_digest({"registry": "dell:gap:open-defect"}),
        case_id=baseline.case_id,
        baseline_source_plan_digest=baseline.source_plan_digest,
        inventory_snapshot_digest=baseline.inventory_snapshot_digest,
        catalog_digest=baseline.catalog_digest,
        policy_digest=baseline.policy_digest,
        artifacts=(*non_review, qualification, review, open_owned_defect),
    )
    with pytest.raises(ValueError, match="public_gap_has_unresolved_owned_defect"):
        authorize_gap_eligibility(
            request,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(registry_with_open_defect),
            policy=policy,
            gap_receipt_id="gap:dell:blocked-by-owned-defect",
        )

    empty_registry = _signed(
        VerifiedArtifactRegistrySnapshot,
        "registry_digest",
        registry_id="registry:dell:gap:empty",
        resolver_ref=REGISTRY_RESOLVER_REF,
        store_revision=2,
        canonical_tip_digest=canonical_digest({"registry": "dell:gap:empty"}),
        case_id=baseline.case_id,
        baseline_source_plan_digest=baseline.source_plan_digest,
        inventory_snapshot_digest=baseline.inventory_snapshot_digest,
        catalog_digest=baseline.catalog_digest,
        policy_digest=baseline.policy_digest,
        artifacts=(),
    )
    with pytest.raises(ValueError, match="missing_or_wrong_kind"):
        authorize_gap_eligibility(
            request,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(empty_registry),
            policy=policy,
            gap_receipt_id="gap:dell:forged",
        )

    not_applicable_local = artifact(
        refs["local"],
        "local_integrity",
        outcome="qualified_not_applicable",
    )
    registry_with_not_applicable_required_proof = _signed(
        VerifiedArtifactRegistrySnapshot,
        "registry_digest",
        registry_id="registry:dell:gap:not-applicable-proof",
        resolver_ref=REGISTRY_RESOLVER_REF,
        store_revision=2,
        canonical_tip_digest=canonical_digest(
            {"registry": "dell:gap:not-applicable-proof"}
        ),
        case_id=baseline.case_id,
        baseline_source_plan_digest=baseline.source_plan_digest,
        inventory_snapshot_digest=baseline.inventory_snapshot_digest,
        catalog_digest=baseline.catalog_digest,
        policy_digest=baseline.policy_digest,
        artifacts=(
            *(
                not_applicable_local
                if item.artifact_ref == refs["local"]
                else item
                for item in non_review
            ),
            qualification,
            review,
        ),
    )
    with pytest.raises(ValueError, match="gap_proof_outcome_not_qualified"):
        authorize_gap_eligibility(
            request,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(
                registry_with_not_applicable_required_proof
            ),
            policy=policy,
            gap_receipt_id="gap:dell:not-applicable-proof",
        )

    unbound_discovery = artifact(
        refs["discovery"],
        "route_discovery",
        routes=(route.route_obligation_id,),
    )
    registry_with_unbound_route_lifecycle = _signed(
        VerifiedArtifactRegistrySnapshot,
        "registry_digest",
        registry_id="registry:dell:gap:unbound-route-lifecycle",
        resolver_ref=REGISTRY_RESOLVER_REF,
        store_revision=2,
        canonical_tip_digest=canonical_digest(
            {"registry": "dell:gap:unbound-route-lifecycle"}
        ),
        case_id=baseline.case_id,
        baseline_source_plan_digest=baseline.source_plan_digest,
        inventory_snapshot_digest=baseline.inventory_snapshot_digest,
        catalog_digest=baseline.catalog_digest,
        policy_digest=baseline.policy_digest,
        artifacts=(
            *(
                unbound_discovery
                if item.artifact_ref == refs["discovery"]
                else item
                for item in non_review
            ),
            qualification,
            review,
        ),
    )
    with pytest.raises(ValueError, match="route_lifecycle_digest_binding_mismatch"):
        authorize_gap_eligibility(
            request,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(
                registry_with_unbound_route_lifecycle
            ),
            policy=policy,
            gap_receipt_id="gap:dell:unbound-route-lifecycle",
        )

    stale_policy = _signed(
        RuntimePolicySnapshot,
        "policy_digest",
        **{
            **_model_values(policy, "policy_digest", "research_as_of"),
            "research_as_of": "2026-09-02",
        },
    )
    with pytest.raises(ValueError, match="gap_runtime_policy_baseline_mismatch"):
        authorize_gap_eligibility(
            request,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(registry),
            policy=stale_policy,
            gap_receipt_id="gap:dell:stale-policy",
        )

    policy_without_boundary_authority = policy.model_copy(
        update={"allowed_authority_class_refs": ("authority:research-read",)}
    )
    with pytest.raises(ValueError, match="runtime_policy_digest_mismatch"):
        authorize_gap_eligibility(
            request,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(registry),
            policy=policy_without_boundary_authority,
            gap_receipt_id="gap:dell:reviewer-authority-not-allowed",
        )

    stale_request = request.model_copy(
        update={"original_actor_ref": "agent:substituted-after-signing"}
    )
    with pytest.raises(ValueError, match="gap_eligibility_request_digest_mismatch"):
        authorize_gap_eligibility(
            stale_request,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(registry),
            policy=policy,
            gap_receipt_id="gap:dell:stale-request",
        )

    review_by_original_producer = artifact(
        refs["review"],
        "independent_gap_review",
        actor="reviewer:independent:1",
        producers=("agent:specialist:1",),
        reviewed_producers=("agent:specialist:1", "runtime:integrity"),
        independent_of=("agent:specialist:1", "runtime:integrity"),
        bound=(request.request_digest, proof_set_digest, qualification.artifact_digest),
    )
    registry_with_nonindependent_review_producer = _signed(
        VerifiedArtifactRegistrySnapshot,
        "registry_digest",
        registry_id="registry:dell:gap:review-produced-by-original",
        resolver_ref=REGISTRY_RESOLVER_REF,
        store_revision=2,
        canonical_tip_digest=canonical_digest(
            {"registry": "dell:gap:review-produced-by-original"}
        ),
        case_id=baseline.case_id,
        baseline_source_plan_digest=baseline.source_plan_digest,
        inventory_snapshot_digest=baseline.inventory_snapshot_digest,
        catalog_digest=baseline.catalog_digest,
        policy_digest=baseline.policy_digest,
        artifacts=(*non_review, qualification, review_by_original_producer),
    )
    with pytest.raises(
        ValueError,
        match="public_gap_reviewer_not_independent_or_authorized",
    ):
        authorize_gap_eligibility(
            request,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(
                registry_with_nonindependent_review_producer
            ),
            policy=policy,
            gap_receipt_id="gap:dell:review-produced-by-original",
        )


def test_decision_and_manifest_are_audit_safe_not_hidden_reasoning() -> None:
    next_action = AvailableNextAction(
        action="request_disclosure",
        reason="Load the S1 contract before choosing a query",
        capability_ref="cap:s1-search",
        expected_information_gain="medium",
    )
    artifact_values = {
        "decision_artifact_id": "decision:dell:1",
        "revision": 0,
        "task_id": "task:dell:all",
        "goal": "Determine the next bounded evidence action",
        "observation_refs": ("observation:dell:1",),
        "chosen_action": "Request the S1 capability contract",
        "concise_rationale": "The capability contract is needed before a valid tool request",
        "rejected_alternatives": (),
        "uncertainty": "Exact local source families are not yet disclosed",
        "confidence": "medium",
        "next_actions": (next_action,),
        "validator_receipt_refs": (),
        "verifier_receipt_refs": (),
        "context_manifest_digest": D1,
    }
    artifact = _signed(DecisionArtifact, "artifact_digest", **artifact_values)
    assert artifact.contains_private_reasoning is False
    with pytest.raises(ValidationError, match="Extra inputs"):
        DecisionArtifact(
            **artifact.model_dump(mode="python"),
            reasoning_content="private chain of thought",
        )

    manifest_values = {
        "manifest_id": "manifest:dell:1",
        "task_id": "task:dell:all",
        "objective": "Research the Dell case with source-bound evidence",
        "objective_digest": research_objective_digest(
            "Research the Dell case with source-bound evidence"
        ),
        "task_assignment_digest": D5,
        "governance_summary": "Use only granted capabilities and bind claims to evidence",
        "runtime_policy_digest": D1,
        "disclosure_policy_digest": D5,
        "authority_matrix_digest": D2,
        "plan_digest": D3,
        "research_graph_digest": D1,
        "latest_plan_delta_refs": (),
        "observation_refs": ("observation:dell:1",),
        "unresolved_feedback_refs": (),
        "l0_catalog_digest": D4,
        "l0_capability_refs": ("cap:s1-search",),
        "granted_disclosure_receipt_refs": (),
        "available_next_actions": (next_action,),
        "budget_status": "within_budget",
        "stop_status": "continue",
        "intervention_status": "none",
        "context_checkpoint_ref": None,
        "current_model_context_snapshot_digest": D2,
    }
    manifest = _signed(
        ModelVisibleContextManifest,
        "manifest_digest",
        **manifest_values,
    )
    assert manifest.public_content_only is True
    forged_manifest = manifest.model_copy(
        update={"objective": "Analyze an unrelated issuer instead"}
    )
    with pytest.raises(
        ValidationError,
        match="context_manifest_objective_digest_mismatch",
    ):
        ModelVisibleContextManifest.model_validate(
            forged_manifest.model_dump(mode="python")
        )
    with pytest.raises(ValidationError, match="Extra inputs"):
        ModelVisibleContextManifest(
            **manifest.model_dump(mode="python"),
            runtime_scope={"paid": True},
        )


def test_models_are_frozen_and_extra_fields_fail_closed() -> None:
    policy = _runtime_policy()
    with pytest.raises(ValidationError, match="frozen"):
        policy.case_version = "mutated"  # type: ignore[misc]
    with pytest.raises(ValidationError, match="Extra inputs"):
        RuntimePolicySnapshot(
            **policy.model_dump(mode="python"),
            paid_execution_id="A03",
        )


def test_add_action_cannot_smuggle_an_unreceipted_task_change() -> None:
    source_plan = _source_plan()
    base = _plan(source_plan=source_plan)
    added_task = _task().model_copy(
        update={
            "task_id": "task:dell:new",
            "objective": "Add a bounded counterevidence task for Dell",
            "status": "deferred",
        }
    )
    # The successor keeps the original task and includes the new task.  Build a
    # draft so coverage may continue to point only at the original task.
    successor = _signed(
        ResearchPlan,
        "plan_digest",
        plan_id=base.plan_id,
        revision=1,
        status="draft",
        case_id=base.case_id,
        baseline_source_plan_digest=source_plan.source_plan_digest,
        catalog_digest=D2,
        policy_digest=D3,
        authority_matrix_digest=D4,
        budget_basis_digest=D5,
        prior_plan_digest=base.plan_digest,
        coverage_obligations=base.coverage_obligations,
        tasks=(base.tasks[0], added_task),
    )
    before = tuple(coverage_state_snapshot(item) for item in base.coverage_obligations)
    after = tuple(coverage_state_snapshot(item) for item in successor.coverage_obligations)
    add = AddTaskAction(
        action_id="delta-action:add:1",
        reason="Add an explicit counterevidence research responsibility",
        feedback_receipt_refs=(),
        coverage_before=before,
        coverage_after=after,
        authority_impact=_no_authority_impact(),
        budget_delta=_zero_budget_delta(),
        successor_task=added_task,
    )
    tampered_successor = successor.model_copy(
        update={
            "tasks": (
                base.tasks[0].model_copy(update={"objective": "Unreceipted mutation"}),
                added_task,
            )
        }
    )
    # Re-sign the tampered plan so the delta validator, not the plan digest,
    # owns the failure.
    tampered_successor = _signed(
        ResearchPlan,
        "plan_digest",
        **_model_values(tampered_successor, "plan_digest"),
    )
    with pytest.raises(ValidationError, match="unreceipted_successor_task_change"):
        _signed(
            AgenticPlanDeltaV1_2,
            "delta_digest",
            delta_id="plan-delta:dell:tampered",
            base_plan=base,
            successor_plan=tampered_successor,
            baseline_source_plan_before=source_plan,
            baseline_source_plan_after=source_plan,
            add_actions=(add,),
            modify_actions=(),
            defer_actions=(),
            cancel_actions=(),
            coverage_before=before,
            coverage_after=after,
            route_replacements=(),
            authority_impact=_no_authority_impact(),
            budget_delta=_zero_budget_delta(),
            catalog_digest=D2,
            policy_digest=D3,
            authority_matrix_digest=D4,
            budget_basis_digest=D5,
            accepted_plan_digest=tampered_successor.plan_digest,
            resulting_graph_digest=research_plan_graph_digest(tampered_successor),
        )


def test_nonzero_coverage_resolver_requires_every_ref_to_be_current_and_reachable() -> None:
    baseline = _source_plan()
    base_coverage = _coverage()
    obligation = CoverageObligation(
        **{
            **_model_values(
                base_coverage[0],
                "evidence_satisfaction",
                "evidence_refs",
            ),
            "evidence_satisfaction": "partial",
            "evidence_refs": ("evidence:dell:current", "evidence:dell:second"),
        }
    )
    plan = _plan(
        source_plan=baseline,
        coverage=(obligation, *base_coverage[1:]),
    )

    def evidence(ref: str, task_id: str) -> VerifiedArtifactRef:
        return _signed(
            VerifiedArtifactRef,
            "artifact_digest",
            artifact_ref=ref,
            artifact_kind="evidence",
            case_id=baseline.case_id,
            baseline_source_plan_digest=baseline.source_plan_digest,
            inventory_snapshot_digest=baseline.inventory_snapshot_digest,
            catalog_digest=baseline.catalog_digest,
            policy_digest=baseline.policy_digest,
            coverage_obligation_ids=(obligation.obligation_id,),
            task_ids=(task_id,),
            route_obligation_ids=(),
            material_proposition_refs=(),
            bound_artifact_digests=(),
            canonical_artifact_digest=canonical_digest({"evidence_ref": ref}),
            outcome="qualified",
            terminal=True,
        )

    current = evidence("evidence:dell:current", "task:dell:all")
    second_current = evidence("evidence:dell:second", "task:dell:all")
    valid_registry = _signed(
        VerifiedArtifactRegistrySnapshot,
        "registry_digest",
        registry_id="registry:dell:coverage:current",
        resolver_ref=REGISTRY_RESOLVER_REF,
        store_revision=1,
        canonical_tip_digest=canonical_digest({"registry": "dell:coverage:current"}),
        case_id=baseline.case_id,
        baseline_source_plan_digest=baseline.source_plan_digest,
        inventory_snapshot_digest=baseline.inventory_snapshot_digest,
        catalog_digest=baseline.catalog_digest,
        policy_digest=baseline.policy_digest,
        artifacts=(current, second_current),
    )
    assert validate_research_plan_reference_integrity(
        plan,
        baseline_source_plan=baseline,
        registry_resolver=_registry_resolver(valid_registry),
        zero_model=False,
    ) == plan

    with pytest.raises(TypeError, match="verified_artifact_registry_resolver_required"):
        validate_research_plan_reference_integrity(
            plan,
            baseline_source_plan=baseline,
            registry_resolver=valid_registry,  # type: ignore[arg-type]
            zero_model=False,
        )
    with pytest.raises(
        ValueError,
        match="verified_artifact_registry_absent_from_authoritative_store",
    ):
        validate_research_plan_reference_integrity(
            plan,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(None),
            zero_model=False,
        )
    mismatched_resolver_snapshot = _signed(
        VerifiedArtifactRegistrySnapshot,
        "registry_digest",
        **{
            **_model_values(valid_registry, "registry_digest", "resolver_ref"),
            "resolver_ref": "resolver:host:other",
        },
    )
    with pytest.raises(
        ValueError,
        match="verified_artifact_registry_resolver_identity_mismatch",
    ):
        validate_research_plan_reference_integrity(
            plan,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(mismatched_resolver_snapshot),
            zero_model=False,
        )

    wrong_task = evidence("evidence:dell:second", "task:not-reachable")
    mixed_registry = _signed(
        VerifiedArtifactRegistrySnapshot,
        "registry_digest",
        registry_id="registry:dell:coverage:mixed-task",
        resolver_ref=REGISTRY_RESOLVER_REF,
        store_revision=2,
        canonical_tip_digest=canonical_digest(
            {"registry": "dell:coverage:mixed-task"}
        ),
        case_id=baseline.case_id,
        baseline_source_plan_digest=baseline.source_plan_digest,
        inventory_snapshot_digest=baseline.inventory_snapshot_digest,
        catalog_digest=baseline.catalog_digest,
        policy_digest=baseline.policy_digest,
        artifacts=(current, wrong_task),
    )
    with pytest.raises(ValueError, match="coverage_reference_unreachable_task"):
        validate_research_plan_reference_integrity(
            plan,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(mixed_registry),
            zero_model=False,
        )

    stale_plan = plan.model_copy(
        update={
            "coverage_obligations": (
                obligation.model_copy(
                    update={"evidence_refs": ("evidence:dell:current",)}
                ),
                *plan.coverage_obligations[1:],
            )
        }
    )
    with pytest.raises(ValueError, match="research_plan_digest_mismatch"):
        validate_research_plan_reference_integrity(
            stale_plan,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(valid_registry),
            zero_model=False,
        )


def test_zero_model_plan_gate_rejects_any_claimed_evidence() -> None:
    baseline = _source_plan()
    clean = _plan(source_plan=baseline)
    assert validate_research_plan_reference_integrity(
        clean,
        baseline_source_plan=baseline,
        registry_resolver=None,
        zero_model=True,
    ) == clean

    covered = clean.coverage_obligations[0].model_copy(
        update={
            "evidence_satisfaction": "covered",
            "evidence_refs": ("evidence:does-not-exist",),
            "counter_finding_refs": ("finding:does-not-exist",),
            "material_requirement_receipt_refs": (
                "receipt:material-requirement:does-not-exist",
            ),
            "verifier_transition_receipt_refs": (
                "receipt:verifier-transition:does-not-exist",
            ),
        }
    )
    claimed = _signed(
        ResearchPlan,
        "plan_digest",
        **{
            **_model_values(clean, "plan_digest", "coverage_obligations"),
            "coverage_obligations": (covered, *clean.coverage_obligations[1:]),
        },
    )
    with pytest.raises(ValueError, match="zero_model_plan_claims_evidence"):
        validate_research_plan_reference_integrity(
            claimed,
            baseline_source_plan=baseline,
            registry_resolver=None,
            zero_model=True,
        )

    empty_registry = _signed(
        VerifiedArtifactRegistrySnapshot,
        "registry_digest",
        registry_id="registry:dell:coverage:empty",
        resolver_ref=REGISTRY_RESOLVER_REF,
        store_revision=1,
        canonical_tip_digest=canonical_digest({"registry": "dell:coverage:empty"}),
        case_id=baseline.case_id,
        baseline_source_plan_digest=baseline.source_plan_digest,
        inventory_snapshot_digest=baseline.inventory_snapshot_digest,
        catalog_digest=baseline.catalog_digest,
        policy_digest=baseline.policy_digest,
        artifacts=(),
    )
    with pytest.raises(ValueError, match="missing_or_wrong_kind"):
        validate_research_plan_reference_integrity(
            claimed,
            baseline_source_plan=baseline,
            registry_resolver=_registry_resolver(empty_registry),
            zero_model=False,
        )


def test_scope_authorization_is_issued_from_current_accepted_plan_task() -> None:
    plan = _plan()
    task = plan.tasks[0]
    scope = _signed(
        RuntimeScope,
        "scope_digest",
        case_id=plan.case_id,
        session_id="session:dell:plan-bound",
        research_run_id="research-run:dell:plan-bound",
        run_invocation_id="run-invocation:dell:plan-bound",
        action_attempt_id="action-attempt:dell:plan-bound",
        agent_id="agent:lead:plan-bound",
        agent_role=task.owner_role,
        task_id=task.task_id,
        task_kind="dell_full_case_research",
        case_version="FIN-0.1.3",
        research_as_of="2026-09-03",
        data_snapshot_digest=D1,
        policy_digest=D3,
        disclosure_policy_digest=D2,
        authority_matrix_digest=plan.authority_matrix_digest,
        branch_scope_refs=("branch:dell",),
        permission_refs=("authority:research-read",),
        canonical_issuer_selectors=("issuer:DELL",),
        physical_source_role_selectors=(),
        physical_route_selectors=(),
        physical_lane_selectors=(),
        method_digest=D5,
        skill_digests=(),
        idempotency_key="idempotency:dell:plan-bound:scope",
        timeout_ms=60_000,
        rate_and_cost_boundary_digest=D4,
    )
    record = issue_runtime_scope_authorization_record(
        authorization_record_id="scope-authorization:dell:plan-bound",
        runtime_scope=scope,
        action_attempt_digest=canonical_digest(
            {"action_attempt_id": scope.action_attempt_id}
        ),
        accepted_plan=plan,
        canonical_event_ledger_snapshot_digest=D1,
        authority_store_revision=1,
    )

    assert record.accepted_plan_digest == plan.plan_digest
    assert record.research_graph_digest == research_plan_graph_digest(plan)
    assert record.objective_digest == research_objective_digest(task.objective)
    assert record.task_assignment_digest == task_assignment_authority_digest(
        agent_id=scope.agent_id,
        agent_role=scope.agent_role,
        task_id=scope.task_id,
        task_kind=scope.task_kind,
        objective_digest=record.objective_digest,
        accepted_plan_digest=plan.plan_digest,
        research_graph_digest=record.research_graph_digest,
    )

    wrong_role_scope = _signed(
        RuntimeScope,
        "scope_digest",
        **{
            **_model_values(scope, "scope_digest", "agent_role"),
            "agent_role": "role:counter_analyst",
        },
    )
    with pytest.raises(
        ValueError,
        match="runtime_scope_authorization_task_owner_role_mismatch",
    ):
        issue_runtime_scope_authorization_record(
            authorization_record_id="scope-authorization:dell:wrong-role",
            runtime_scope=wrong_role_scope,
            action_attempt_digest=canonical_digest(
                {"action_attempt_id": wrong_role_scope.action_attempt_id}
            ),
            accepted_plan=plan,
            canonical_event_ledger_snapshot_digest=D1,
            authority_store_revision=1,
        )

    missing_authority_scope = _signed(
        RuntimeScope,
        "scope_digest",
        **{
            **_model_values(scope, "scope_digest", "permission_refs"),
            "permission_refs": (),
        },
    )
    with pytest.raises(
        ValueError,
        match="runtime_scope_authorization_task_authority_missing",
    ):
        issue_runtime_scope_authorization_record(
            authorization_record_id="scope-authorization:dell:missing-authority",
            runtime_scope=missing_authority_scope,
            action_attempt_digest=canonical_digest(
                {"action_attempt_id": missing_authority_scope.action_attempt_id}
            ),
            accepted_plan=plan,
            canonical_event_ledger_snapshot_digest=D1,
            authority_store_revision=1,
        )

    for field_name, replacement, error_code in (
        (
            "policy_digest",
            canonical_digest({"policy": "unrelated"}),
            "runtime_scope_authorization_plan_policy_mismatch",
        ),
        (
            "authority_matrix_digest",
            canonical_digest({"matrix": "unrelated"}),
            "runtime_scope_authorization_plan_authority_matrix_mismatch",
        ),
    ):
        incompatible_plan = _signed(
            ResearchPlan,
            "plan_digest",
            **{
                **_model_values(plan, "plan_digest", field_name),
                field_name: replacement,
            },
        )
        with pytest.raises(ValueError, match=error_code):
            issue_runtime_scope_authorization_record(
                authorization_record_id=(
                    f"scope-authorization:dell:incompatible-{field_name}"
                ),
                runtime_scope=scope,
                action_attempt_digest=canonical_digest(
                    {"action_attempt_id": scope.action_attempt_id}
                ),
                accepted_plan=incompatible_plan,
                canonical_event_ledger_snapshot_digest=D1,
                authority_store_revision=1,
            )

    forged_objective_digest = research_objective_digest(
        "Analyze an unrelated issuer under the retained assignment digest"
    )
    forged_body = record.model_dump(
        mode="python",
        exclude={"authorization_record_digest"},
    )
    forged_body["objective_digest"] = forged_objective_digest
    forged = record.model_copy(
        update={
            "objective_digest": forged_objective_digest,
            "authorization_record_digest": canonical_digest(forged_body),
        }
    )
    with pytest.raises(
        ValidationError,
        match="runtime_scope_task_assignment_digest_mismatch",
    ):
        validate_runtime_scope_authorization(
            runtime_scope=scope,
            authorization_record=forged,
        )

    with pytest.raises(
        ValidationError,
        match="runtime_scope_task_assignment_digest_mismatch",
    ):
        _signed(
            RuntimeScopeAuthorizationRecord,
            "authorization_record_digest",
            **{
                **_model_values(record, "authorization_record_digest"),
                "task_assignment_digest": ZERO,
            },
        )


def test_zero_model_authority_gate_emits_receipt_and_rejects_phantom_paid_node() -> None:
    policy = _runtime_policy()
    matrix = _signed(
        ModelNodeAuthorityMatrix,
        "matrix_digest",
        matrix_id="authority-matrix:dell:wave0a:gate",
        policy_digest=policy.policy_digest,
        entries=_authority_entries(),
    )
    scope = _signed(
        RuntimeScope,
        "scope_digest",
        case_id=policy.case_id,
        session_id="session:dell:zero-model",
        research_run_id="research-run:dell:zero-model",
        run_invocation_id="run-invocation:dell:zero-model",
        action_attempt_id="action-attempt:dell:zero-model",
        agent_id="agent:lead:zero-model",
        agent_role="lead",
        task_id="task:dell:zero-model",
        task_kind="zero_model_contract_qualification",
        case_version=policy.case_version,
        research_as_of=policy.research_as_of,
        data_snapshot_digest=policy.data_snapshot_digest,
        policy_digest=policy.policy_digest,
        disclosure_policy_digest=policy.disclosure_policy_digest,
        authority_matrix_digest=matrix.matrix_digest,
        branch_scope_refs=("branch:dell",),
        permission_refs=("authority:research-read",),
        canonical_issuer_selectors=("issuer:DELL",),
        physical_source_role_selectors=(),
        physical_route_selectors=(),
        physical_lane_selectors=(),
        method_digest=D5,
        skill_digests=(),
        idempotency_key="idempotency:dell:zero-model:gate",
        timeout_ms=60_000,
        rate_and_cost_boundary_digest=D2,
    )

    def authorization_for(current_scope: RuntimeScope) -> RuntimeScopeAuthorizationRecord:
        objective_digest = canonical_digest(
            {"objective": "Qualify the zero-model runtime boundary"}
        )
        graph_digest = canonical_digest({"graph": "wave0a-zero-model"})
        return _signed(
            RuntimeScopeAuthorizationRecord,
            "authorization_record_digest",
            authorization_record_id=(
                f"scope-authorization:{current_scope.scope_digest[:16]}"
            ),
            runtime_scope_digest=current_scope.scope_digest,
            session_id=current_scope.session_id,
            research_run_id=current_scope.research_run_id,
            run_invocation_id=current_scope.run_invocation_id,
            action_attempt_id=current_scope.action_attempt_id,
            action_attempt_digest=canonical_digest(
                {"action_attempt_id": current_scope.action_attempt_id}
            ),
            agent_id=current_scope.agent_id,
            agent_role=current_scope.agent_role,
            task_id=current_scope.task_id,
            task_kind=current_scope.task_kind,
            accepted_plan_digest=D5,
            research_graph_digest=graph_digest,
            objective_digest=objective_digest,
            task_assignment_digest=task_assignment_authority_digest(
                agent_id=current_scope.agent_id,
                agent_role=current_scope.agent_role,
                task_id=current_scope.task_id,
                task_kind=current_scope.task_kind,
                objective_digest=objective_digest,
                accepted_plan_digest=D5,
                research_graph_digest=graph_digest,
            ),
            policy_digest=current_scope.policy_digest,
            disclosure_policy_digest=current_scope.disclosure_policy_digest,
            authority_matrix_digest=current_scope.authority_matrix_digest,
            canonical_event_ledger_snapshot_digest=D1,
            authority_store_revision=1,
            issued_by="host_runtime_authority_resolver",
        )

    scope_authorization = authorization_for(scope)
    receipt = validate_zero_model_runtime_boundary(
        policy=policy,
        authority_matrix=matrix,
        runtime_scope=scope,
        scope_authorization=scope_authorization,
    )
    assert receipt.paid_transport_authorized is False
    assert receipt.all_model_nodes_not_authorized is True

    forged_entry = matrix.entries[0].model_copy(
        update={"provider_ref": "provider:phantom-paid"}
    )
    forged_matrix_body = {
        **_model_values(matrix, "matrix_digest", "entries"),
        "entries": (forged_entry, *matrix.entries[1:]),
    }
    forged_matrix = ModelNodeAuthorityMatrix.model_construct(
        **forged_matrix_body,
        matrix_digest=canonical_digest(forged_matrix_body),
    )
    with pytest.raises(
        ValidationError,
        match="not_authorized_node_has_paid_transport_binding",
    ):
        ModelNodeAuthorityMatrix.model_validate(
            forged_matrix.model_dump(mode="python")
        )
    forged_scope = _signed(
        RuntimeScope,
        "scope_digest",
        **{
            **_model_values(scope, "scope_digest", "authority_matrix_digest"),
            "authority_matrix_digest": forged_matrix.matrix_digest,
        },
    )
    forged_scope_authorization = authorization_for(forged_scope)
    with pytest.raises(
        ValidationError,
        match="not_authorized_node_has_paid_transport_binding",
    ):
        validate_zero_model_runtime_boundary(
            policy=policy,
            authority_matrix=forged_matrix,
            runtime_scope=forged_scope,
            scope_authorization=forged_scope_authorization,
        )

    class MemoryZeroModelTransportAuditPort:
        def __init__(self) -> None:
            self.events: list[ZeroModelTransportAuditEvent] = []

        def append_zero_model_transport_audit_event(
            self,
            event: ZeroModelTransportAuditEvent,
        ) -> None:
            assert isinstance(event, ZeroModelTransportAuditEvent)
            self.events.append(event)

    audit_port = MemoryZeroModelTransportAuditPort()
    zero_model_event = wave0a_zero_model_transport_gateway(
        audit_event_id="audit-event:dell:zero-model:valid",
        action_attempt_id=scope.action_attempt_id,
        audit_port=audit_port,
        policy=policy,
        authority_matrix=matrix,
        runtime_scope=scope,
        scope_authorization=scope_authorization,
        boundary_receipt=receipt,
    )
    assert zero_model_event.block_reason == "wave0a_zero_model"

    missing_event = wave0a_zero_model_transport_gateway(
        audit_event_id="audit-event:dell:zero-model:missing",
        action_attempt_id=scope.action_attempt_id,
        audit_port=audit_port,
        policy=policy,
        authority_matrix=None,
        runtime_scope=scope,
        scope_authorization=scope_authorization,
        boundary_receipt=receipt,
    )
    assert missing_event.block_reason == "authority_material_missing"

    stale_boundary_receipt = receipt.model_copy(
        update={"runtime_scope_digest": ZERO}
    )
    stale_receipt_event = wave0a_zero_model_transport_gateway(
        audit_event_id="audit-event:dell:zero-model:stale-receipt",
        action_attempt_id=scope.action_attempt_id,
        audit_port=audit_port,
        policy=policy,
        authority_matrix=matrix,
        runtime_scope=scope,
        scope_authorization=scope_authorization,
        boundary_receipt=stale_boundary_receipt,
    )
    assert (
        stale_receipt_event.block_reason
        == "authority_material_stale_or_invalid"
    )

    mismatched_action_event = wave0a_zero_model_transport_gateway(
        audit_event_id="audit-event:dell:zero-model:mismatched-action",
        action_attempt_id="action-attempt:dell:different",
        audit_port=audit_port,
        policy=policy,
        authority_matrix=matrix,
        runtime_scope=scope,
        scope_authorization=scope_authorization,
        boundary_receipt=receipt,
    )
    assert (
        mismatched_action_event.block_reason
        == "authority_material_stale_or_invalid"
    )

    for updates, error in (
        ({"case_id": "case:nvda:wrong"}, "identity_or_snapshot_mismatch"),
        ({"case_version": "WRONG"}, "identity_or_snapshot_mismatch"),
        ({"research_as_of": "1999-01-01"}, "identity_or_snapshot_mismatch"),
        ({"data_snapshot_digest": ZERO}, "identity_or_snapshot_mismatch"),
        (
            {"disclosure_policy_digest": ZERO},
            "runtime_scope_disclosure_policy_mismatch",
        ),
        ({"branch_scope_refs": ("branch:not-allowed",)}, "branch_not_allowed"),
        ({"permission_refs": ("authority:not-allowed",)}, "permission_not_allowed"),
        ({"may_promote_evidence": True}, "evidence_promotion_authority_forbidden"),
        ({"may_write_s2": True}, "s2_write_authority_forbidden"),
    ):
        invalid_scope = _signed(
            RuntimeScope,
            "scope_digest",
            **{
                **_model_values(scope, "scope_digest", *updates),
                **updates,
            },
        )
        with pytest.raises(ValueError, match=error):
            validate_zero_model_runtime_boundary(
                policy=policy,
                authority_matrix=matrix,
                runtime_scope=invalid_scope,
                scope_authorization=authorization_for(invalid_scope),
            )

    stale_event = wave0a_zero_model_transport_gateway(
        audit_event_id="audit-event:dell:zero-model:stale",
        action_attempt_id=invalid_scope.action_attempt_id,
        audit_port=audit_port,
        policy=policy,
        authority_matrix=matrix,
        runtime_scope=invalid_scope,
        scope_authorization=authorization_for(invalid_scope),
        boundary_receipt=receipt,
    )
    assert stale_event.block_reason == "authority_material_stale_or_invalid"

    basis = _signed(
        TokenBudgetBasis,
        "basis_digest",
        node_purpose="Attempt a paid planner model call",
        input_scale="One Dell planning manifest",
        required_outputs=("research_plan",),
        schema_burden="Strict plan schema",
        materiality_quality_risk="Material research plan risk",
        comparable_run_evidence_refs=(),
        reasoning_profile="high",
        stop_behavior="Stop before transport when authority is absent",
        truncation_behavior="Never silently truncate required planning output",
        max_input_tokens=10_000,
        max_output_tokens=4_000,
        max_action_attempts=1,
    )
    paid_entry = ModelNodeAuthorityEntry(
        **{
            **_authority_entries()[0].model_dump(mode="python"),
            "status": "authorized",
            "token_budget_basis": basis,
            "provider_ref": "provider:deepseek",
            "model_ref": "model:deepseek-chat",
            "paid_execution_owner_decision_ref": "decision:phantom-paid-successor",
        }
    )
    paid_matrix = _signed(
        ModelNodeAuthorityMatrix,
        "matrix_digest",
        matrix_id="authority-matrix:dell:phantom",
        policy_digest=policy.policy_digest,
        entries=(paid_entry, *_authority_entries()[1:]),
    )
    paid_scope = _signed(
        RuntimeScope,
        "scope_digest",
        **{
            **_model_values(scope, "scope_digest", "authority_matrix_digest"),
            "authority_matrix_digest": paid_matrix.matrix_digest,
        },
    )
    with pytest.raises(ValueError, match="authorized_model_node_forbidden"):
        validate_zero_model_runtime_boundary(
            policy=policy,
            authority_matrix=paid_matrix,
            runtime_scope=paid_scope,
            scope_authorization=authorization_for(paid_scope),
        )

    phantom_event = wave0a_zero_model_transport_gateway(
        audit_event_id="audit-event:dell:zero-model:phantom",
        action_attempt_id=paid_scope.action_attempt_id,
        audit_port=audit_port,
        policy=policy,
        authority_matrix=paid_matrix,
        runtime_scope=paid_scope,
        scope_authorization=authorization_for(paid_scope),
        boundary_receipt=receipt,
    )
    assert phantom_event.block_reason == "phantom_paid_authority"

    assert len(audit_port.events) == 6
    assert all(
        event.client_construction_count == 0
        and event.structured_output_bind_count == 0
        and event.invoke_count == 0
        and event.provider_call_attempted is False
        for event in audit_port.events
    )

    with pytest.raises(TypeError, match="typed_audit_port_required"):
        wave0a_zero_model_transport_gateway(
            audit_event_id="audit-event:dell:zero-model:raw-mapping-port",
            action_attempt_id=scope.action_attempt_id,
            audit_port={},  # type: ignore[arg-type]
            policy=policy,
            authority_matrix=matrix,
            runtime_scope=scope,
            scope_authorization=scope_authorization,
            boundary_receipt=receipt,
        )


def test_provider_envelope_persistence_rejects_cot_and_scrubs_secrets() -> None:
    persisted = prepare_provider_envelope_for_persistence(
        {
            "assistant_output": "Management analysis: revenue rose year over year.",
            "tool_calls": (
                {
                    "id": "call-1",
                    "type": "function",
                    "name": "external_search",
                    "arguments": '{"x-api-key":"hunter2","access_token":"abcdefghijk","q":"Dell"}',
                },
            ),
            "usage": {"input_tokens": 10, "output_tokens": 5},
        }
    )
    assert "hunter2" not in persisted.sanitized_payload_json
    assert "abcdefghijk" not in persisted.sanitized_payload_json
    assert persisted.sanitized_payload_json.count("[REDACTED]") == 2
    assert validate_public_narrative_text(
        "Management analysis: revenue rose year over year.",
        field_name="concise_rationale",
    )

    with pytest.raises(ValueError, match="forbidden_key"):
        prepare_provider_envelope_for_persistence(
            {"reasoning_content": "private chain of thought"}
        )
    with pytest.raises(ValueError, match="forbidden_key"):
        prepare_provider_envelope_for_persistence(
            {"ｒｅａｓｏｎｉｎｇ＿ｃｏｎｔｅｎｔ": "private chain of thought"}
        )
    with pytest.raises(ValueError, match="forbidden_key"):
        prepare_provider_envelope_for_persistence(
            {
                "tool_calls": (
                    {
                        "id": "call-2",
                        "type": "function",
                        "name": "x",
                        "arguments": {
                            "cmVhc29uaW5nX2NvbnRlbnQ=": "private chain"
                        },
                    },
                )
            }
        )
    repeatedly_encoded_key = "reasoning_content"
    for _ in range(3):
        repeatedly_encoded_key = base64.b64encode(
            repeatedly_encoded_key.encode("utf-8")
        ).decode("ascii")
    with pytest.raises(ValueError, match="forbidden_key"):
        prepare_provider_envelope_for_persistence(
            {
                "tool_calls": (
                    {
                        "id": "call-fixed-point-key",
                        "type": "function",
                        "name": "x",
                        "arguments": {repeatedly_encoded_key: "private chain"},
                    },
                )
            }
        )
    deeply_percent_encoded_key = "reasoning%5Fcontent"
    for _ in range(8):
        deeply_percent_encoded_key = deeply_percent_encoded_key.replace("%", "%25")
    with pytest.raises(ValueError, match="forbidden_key"):
        prepare_provider_envelope_for_persistence(
            {deeply_percent_encoded_key: "private chain"}
        )

    with pytest.raises(ValueError, match="secret_value"):
        prepare_provider_envelope_for_persistence(
            {"assistant_output": "postgresql://admin:hunter2@db.internal/prod"}
        )

    opaque = prepare_provider_envelope_for_persistence(
        {
            "tool_calls": (
                {
                    "id": "call-3",
                    "type": "function",
                    "name": "x",
                    "arguments": "not valid json with private operational text",
                },
            )
        }
    )
    assert "private operational text" not in opaque.sanitized_payload_json
    assert "unparseable_json_not_persisted" in opaque.sanitized_payload_json

    nested = prepare_provider_envelope_for_persistence(
        {
            "tool_calls": (
                {
                    "id": "call-4",
                    "type": "function",
                    "name": "x",
                    "arguments": json.dumps(
                        {
                            "wrapper": json.dumps(
                                {
                                    "deeper": json.dumps(
                                        {"x-api-key": "hunter2", "q": "Dell"}
                                    )
                                }
                            )
                        }
                    ),
                },
            )
        }
    )
    assert "hunter2" not in nested.sanitized_payload_json
    assert "[REDACTED]" in nested.sanitized_payload_json
    fixed_point = json.loads(nested.sanitized_payload_json)
    assert sanitize_provider_envelope(fixed_point) == fixed_point
