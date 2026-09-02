from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from sec_agent.agent_runtime.dell_agentic_contracts import (
    AvailableNextAction,
    ModelNodeAuthorityEntry,
    ModelNodeAuthorityMatrix,
    RuntimePolicySnapshot,
    RuntimeScope,
    RuntimeScopeAuthorizationRecord,
    research_objective_digest,
    task_assignment_authority_digest,
    validate_zero_model_runtime_boundary,
)
from sec_agent.agent_runtime.progressive_disclosure import (
    CapabilityDescriptor,
    CurrentModelContextSnapshot,
    DisclosureAuthorityRule,
    DisclosureCatalogSnapshot,
    DisclosureGrantLedgerView,
    DisclosureReceipt,
    DisclosureRequest,
    DisclosureResource,
    DisclosureRuntimeContext,
    assemble_model_visible_manifest,
    build_current_model_context_snapshot,
    build_disclosure_catalog,
    build_disclosure_grant_ledger_view,
    build_disclosure_policy,
    canonical_digest,
    current_model_context_state_digest,
    decide_disclosure,
    derive_runtime_governance_summary,
    provider_visible_disclosure_schema,
)
from sec_agent.canonical_runtime.contracts_v1_2 import (
    append_session_event_v1_2,
    create_canonical_event_ledger_snapshot,
)


NOW = datetime(2026, 9, 3, tzinfo=timezone.utc)
_ASSIGNED_OBJECTIVE = (
    "Assess Dell demand with source-bound evidence and uncertainty."
)
_LEDGER_SNAPSHOTS_BY_VIEW_DIGEST = {}
_DEFAULT_RESOLVER = object()


def _digest(label: str) -> str:
    return canonical_digest({"label": label})


def _default_model_context_state() -> dict:
    return {
        "latest_plan_delta_refs": ("delta:current",),
        "observation_refs": ("observation:current",),
        "unresolved_feedback_refs": (),
        "available_next_actions": (
            AvailableNextAction(
                action="request_data_inventory",
                reason="Read only the inventory bound to this current action scope.",
            ),
        ),
        "budget_status": "within_budget",
        "stop_status": "continue",
        "intervention_status": "none",
        "context_checkpoint_ref": "checkpoint:current",
    }


def _capability(ref: str = "cap:s1-local-search") -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_ref=ref,
        kind="capability",
        name="Local candidate search",
        purpose="Find bounded issuer material without exposing case answers in L0.",
        authority_summary="Candidate retrieval only; no Evidence promotion authority.",
        cost_tier="low",
        latency_tier="local",
        maximum_disclosure_level="L4",
        action_names=("request_local_evidence",),
    )


def _resource(
    level: str,
    *,
    ref: str = "cap:s1-local-search",
    kind: str = "capability",
    parent_ref: str | None = None,
    tokens: int = 100,
) -> DisclosureResource:
    return DisclosureResource(
        ref=ref,
        kind=kind,
        level=level,
        resource_uri=f"fin://disclosure/{level}/{ref}",
        resource_digest=_digest(f"{ref}-{level}"),
        estimated_context_tokens=tokens,
        parent_ref=parent_ref,
        operator_only=level == "L4",
        answer_free=level in {"L1", "L2"} or kind == "skill",
    )


def _catalog(*, resources: tuple[DisclosureResource, ...] | None = None):
    return build_disclosure_catalog(
        snapshot_id="snapshot:dell-zero-model-01",
        inventory_snapshot_digest=_digest("inventory"),
        capabilities=(_capability(),),
        resources=resources
        or (
            _resource("L1"),
            _resource("L2"),
            _resource("L3"),
            _resource("L4"),
        ),
    )


def _catalog_with_rewritten_l1(
    catalog: DisclosureCatalogSnapshot,
    *,
    suffix: str,
) -> DisclosureCatalogSnapshot:
    resources = []
    for resource in catalog.resources:
        values = resource.model_dump(mode="python")
        if resource.ref == "cap:s1-local-search" and resource.level == "L1":
            values["resource_uri"] = f"memory://caller-{suffix}/private-resource"
            values["resource_digest"] = _digest(f"caller-{suffix}-private-content")
        resources.append(DisclosureResource(**values))
    return build_disclosure_catalog(
        snapshot_id=f"snapshot:dell-{suffix}",
        inventory_snapshot_digest=catalog.inventory_snapshot_digest,
        capabilities=catalog.capabilities,
        resources=tuple(resources),
    )


def _policy(*, max_receipt: int = 500, max_task: int = 2_000, recursion: int = 4):
    return build_disclosure_policy(
        policy_snapshot_id="policy:dell-zero-model-01",
        rules=(
            DisclosureAuthorityRule(
                ref="cap:s1-local-search",
                allowed_roles=("evidence_specialist",),
                allowed_task_kinds=("dell_demand_analysis",),
                maximum_level="L4",
                allow_recursive_children=True,
            ),
        ),
        maximum_tokens_per_receipt=max_receipt,
        maximum_tokens_per_task=max_task,
        maximum_recursive_depth=recursion,
    )


def _request(catalog, policy, *, depth: str = "contract", **overrides):
    values = {
        "catalog_digest": catalog.catalog_digest,
        "inventory_snapshot_digest": catalog.inventory_snapshot_digest,
        "policy_digest": policy.policy_digest,
        "kind": "capability",
        "ref": "cap:s1-local-search",
        "depth": depth,
        "reason": "Need the bounded contract for Dell issuer evidence retrieval.",
        "expected_use": "Select a legal retrieval route for the current obligation.",
    }
    values.update(overrides)
    return DisclosureRequest(**values)


def _runtime_policy(catalog, disclosure_policy) -> RuntimePolicySnapshot:
    body = {
        "contract_version": "1.2",
        "policy_snapshot_id": "policy:dell:wave0a:default",
        "case_id": "case:dell",
        "case_version": "FIN-0.1.3",
        "research_as_of": "2026-09-03",
        "data_snapshot_digest": catalog.inventory_snapshot_digest,
        "catalog_digest": catalog.catalog_digest,
        "disclosure_policy_digest": disclosure_policy.policy_digest,
        "allowed_branch_refs": ("branch:dell",),
        "allowed_authority_class_refs": ("permission:read-candidate",),
        "paid_execution_authority_status": "not_authorized",
        "paid_execution_owner_decision_ref": None,
        "hitl_may_grant_or_elevate_paid_authority": False,
        "evidence_promotion_policy": "qualified_reviewer_only",
        "s2_write_policy": "not_authorized",
        "public_gap_policy": "gap_eligibility_receipt_required",
    }
    return RuntimePolicySnapshot(
        **body,
        policy_digest=canonical_digest(body),
    )


def _runtime_scope(
    catalog,
    policy,
    *,
    role: str = "evidence_specialist",
    task_kind: str = "dell_demand_analysis",
    action_attempt_id: str = "action-attempt:01",
    runtime_policy_digest: str | None = None,
    authority_matrix_digest: str | None = None,
) -> RuntimeScope:
    body = {
        "contract_version": "1.2",
        "sealed": True,
        "provider_visible": False,
        "case_id": "case:dell",
        "session_id": "session:dell",
        "research_run_id": "research-run:dell",
        "run_invocation_id": "run-invocation:01",
        "action_attempt_id": action_attempt_id,
        "agent_id": "agent:evidence-specialist",
        "agent_role": role,
        "task_id": "task:dell-demand",
        "task_kind": task_kind,
        "case_version": "FIN-0.1.3",
        "research_as_of": "2026-09-03",
        "data_snapshot_digest": catalog.inventory_snapshot_digest,
        "policy_digest": (
            runtime_policy_digest
            or _runtime_policy(catalog, policy).policy_digest
        ),
        "disclosure_policy_digest": policy.policy_digest,
        "authority_matrix_digest": (
            authority_matrix_digest or _digest("authority-matrix")
        ),
        "branch_scope_refs": ("branch:dell",),
        "permission_refs": ("permission:read-candidate",),
        "canonical_issuer_selectors": ("DELL",),
        "physical_source_role_selectors": (),
        "physical_route_selectors": (),
        "physical_lane_selectors": (),
        "method_digest": _digest("method"),
        "skill_digests": (),
        "may_promote_evidence": False,
        "may_write_s2": False,
        "may_assert_public_gap_without_receipt": False,
        "paid_model_transport_authorized": False,
        "idempotency_key": "disclosure-test-idempotency-01",
        "timeout_ms": 30_000,
        "rate_and_cost_boundary_digest": _digest("cost-boundary"),
    }
    body["model_context_state_digest"] = current_model_context_state_digest(
        context_snapshot_id="context-snapshot:dell-current",
        resolver_ref="resolver:host-current-model-context",
        store_revision=1,
        session_id=body["session_id"],
        research_run_id=body["research_run_id"],
        run_invocation_id=body["run_invocation_id"],
        action_attempt_id=body["action_attempt_id"],
        task_id=body["task_id"],
        **_default_model_context_state(),
    )
    return RuntimeScope(**body, scope_digest=canonical_digest(body))


def _authority_material(scope) -> dict[str, str]:
    accepted_plan_digest = _digest("accepted-plan")
    research_graph_digest = _digest("accepted-plan-graph")
    objective_digest = research_objective_digest(_ASSIGNED_OBJECTIVE)
    return {
        "action_attempt_digest": _digest(f"action:{scope.action_attempt_id}"),
        "accepted_plan_digest": accepted_plan_digest,
        "research_graph_digest": research_graph_digest,
        "objective_digest": objective_digest,
        "task_assignment_digest": task_assignment_authority_digest(
            agent_id=scope.agent_id,
            agent_role=scope.agent_role,
            task_id=scope.task_id,
            task_kind=scope.task_kind,
            objective_digest=objective_digest,
            accepted_plan_digest=accepted_plan_digest,
            research_graph_digest=research_graph_digest,
        ),
    }


def _scope_authority_output_refs(scope) -> tuple[str, ...]:
    authority = _authority_material(scope)
    return (
        f"runtime-scope://sha256/{scope.scope_digest}",
        f"action-attempt://sha256/{authority['action_attempt_digest']}",
        f"accepted-plan://sha256/{authority['accepted_plan_digest']}",
        f"research-graph://sha256/{authority['research_graph_digest']}",
        f"objective://sha256/{authority['objective_digest']}",
        f"task-assignment://sha256/{authority['task_assignment_digest']}",
        f"runtime-policy://sha256/{scope.policy_digest}",
        f"disclosure-policy://sha256/{scope.disclosure_policy_digest}",
        f"authority-matrix://sha256/{scope.authority_matrix_digest}",
    )


def _resource_binding_ref(receipt: DisclosureReceipt) -> str:
    body = {
        "ref": receipt.ref,
        "kind": receipt.kind,
        "granted_level": receipt.granted_level,
        "resource_uri": receipt.resource_uri,
        "resource_digest": receipt.resource_digest,
    }
    return "disclosure-resource-binding://sha256/" + canonical_digest(body)


class _StaticLedgerReader:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    def read_current_session_ledger(self, session_id: str):
        assert session_id == self.snapshot.session_id
        return self.snapshot


class _StaticCatalogResolver:
    def __init__(self, *, runtime_scope_digest: str, catalog):
        self.runtime_scope_digest = runtime_scope_digest
        self.catalog = catalog

    def resolve_current_catalog(self, *, runtime_scope_digest: str):
        if runtime_scope_digest != self.runtime_scope_digest:
            return None
        return self.catalog


class _StaticAuthorityResolver:
    def __init__(self, record):
        self.record = record

    def resolve_current_scope_authorization(self, runtime_scope_digest: str):
        if runtime_scope_digest != self.record.runtime_scope_digest:
            return None
        return self.record


class _StaticModelContextResolver:
    def __init__(self, snapshot: CurrentModelContextSnapshot):
        self.snapshot = snapshot

    def resolve_current_model_context(self, *, runtime_scope_digest: str):
        if runtime_scope_digest != self.snapshot.runtime_scope_digest:
            return None
        return self.snapshot


class _NullLedgerReader:
    def read_current_session_ledger(self, session_id: str):
        return None


class _NullCatalogResolver:
    def resolve_current_catalog(self, *, runtime_scope_digest: str):
        return None


class _NullAuthorityResolver:
    def resolve_current_scope_authorization(self, runtime_scope_digest: str):
        return None


def _authority_record(scope, ledger_snapshot):
    authority = _authority_material(scope)
    body = {
        "contract_version": "1.2",
        "authorization_record_id": (
            f"scope-authorization:{scope.action_attempt_id.split(':')[-1]}"
        ),
        "runtime_scope_digest": scope.scope_digest,
        "session_id": scope.session_id,
        "research_run_id": scope.research_run_id,
        "run_invocation_id": scope.run_invocation_id,
        "action_attempt_id": scope.action_attempt_id,
        "action_attempt_digest": authority["action_attempt_digest"],
        "agent_id": scope.agent_id,
        "agent_role": scope.agent_role,
        "task_id": scope.task_id,
        "task_kind": scope.task_kind,
        "accepted_plan_digest": authority["accepted_plan_digest"],
        "research_graph_digest": authority["research_graph_digest"],
        "objective_digest": authority["objective_digest"],
        "task_assignment_digest": authority["task_assignment_digest"],
        "policy_digest": scope.policy_digest,
        "disclosure_policy_digest": scope.disclosure_policy_digest,
        "authority_matrix_digest": scope.authority_matrix_digest,
        "canonical_event_ledger_snapshot_digest": (
            ledger_snapshot.ledger_snapshot_digest
        ),
        "authority_store_revision": ledger_snapshot.store_revision,
        "issued_by": "host_runtime_authority_resolver",
    }
    return RuntimeScopeAuthorizationRecord(
        **body,
        authorization_record_digest=canonical_digest(body),
    )


def _grant_ledger_events(
    *,
    scope,
    receipt: DisclosureReceipt,
    include_scope_authority: bool = True,
    include_request: bool = True,
    request_after_grant: bool = False,
    include_grant_request_binding: bool = True,
    include_resource_binding: bool = True,
    scope_actor: str = "runtime",
    request_actor: str = "runtime",
    grant_actor: str = "runtime",
    scope_output_refs: tuple[str, ...] | None = None,
):
    events = [
        append_session_event_v1_2(
            (),
            session_id=scope.session_id,
            event_type="session_created",
            actor_id="runtime",
            occurred_at=NOW,
        )
    ]
    if include_scope_authority:
        events.append(
            append_session_event_v1_2(
                events,
                session_id=scope.session_id,
                run_id=scope.research_run_id,
                run_invocation_id=scope.run_invocation_id,
                action_attempt_id=scope.action_attempt_id,
                event_type="action_intent_committed",
                actor_id=scope_actor,
                occurred_at=NOW + timedelta(seconds=1),
                output_refs=(
                    scope_output_refs
                    if scope_output_refs is not None
                    else _scope_authority_output_refs(scope)
                ),
            )
        )

    request_ref = f"disclosure-request://sha256/{receipt.request_digest}"

    def append_request(second: int) -> None:
        events.append(
            append_session_event_v1_2(
                events,
                session_id=scope.session_id,
                run_id=scope.research_run_id,
                run_invocation_id=scope.run_invocation_id,
                action_attempt_id=scope.action_attempt_id,
                event_type="disclosure_requested",
                actor_id=request_actor,
                occurred_at=NOW + timedelta(seconds=second),
                input_refs=(request_ref,),
            )
        )

    def append_grant(second: int) -> None:
        output_refs = [
            f"disclosure-receipt://sha256/{receipt.receipt_digest}",
            f"disclosure-resource://sha256/{receipt.resource_digest}",
        ]
        if include_resource_binding:
            output_refs.append(_resource_binding_ref(receipt))
        events.append(
            append_session_event_v1_2(
                events,
                session_id=scope.session_id,
                run_id=scope.research_run_id,
                run_invocation_id=scope.run_invocation_id,
                action_attempt_id=scope.action_attempt_id,
                event_type="disclosure_granted",
                actor_id=grant_actor,
                occurred_at=NOW + timedelta(seconds=second),
                input_refs=(request_ref,) if include_grant_request_binding else (),
                output_refs=tuple(output_refs),
            )
        )

    if request_after_grant:
        append_grant(2)
        if include_request:
            append_request(3)
    else:
        if include_request:
            append_request(2)
            append_grant(3)
        else:
            append_grant(2)
    return tuple(events)


def _ledger_snapshot(scope, events, *, revision: int = 1, suffix: str = "fixture"):
    return create_canonical_event_ledger_snapshot(
        ledger_snapshot_id=f"ledger-snapshot:{suffix}",
        repository_ref="repository:canonical-session-events",
        session_id=scope.session_id,
        store_revision=revision,
        events=tuple(events),
        canonical_tip_digest=events[-1].event_digest,
    )


def _context(
    *,
    catalog=None,
    policy=None,
    grants=(),
    role: str = "evidence_specialist",
    action_attempt_id: str = "action-attempt:01",
    runtime_policy_digest: str | None = None,
    authority_matrix_digest: str | None = None,
):
    catalog = catalog or _catalog()
    policy = policy or _policy()
    scope = _runtime_scope(
        catalog,
        policy,
        role=role,
        action_attempt_id=action_attempt_id,
        runtime_policy_digest=runtime_policy_digest,
        authority_matrix_digest=authority_matrix_digest,
    )
    grant_tuple = tuple(grants)
    events = []
    events.append(
        append_session_event_v1_2(
            events,
            session_id=scope.session_id,
            event_type="session_created",
            actor_id="runtime",
            occurred_at=NOW,
        )
    )
    events.append(
        append_session_event_v1_2(
            events,
            session_id=scope.session_id,
            run_id=scope.research_run_id,
            run_invocation_id=scope.run_invocation_id,
            action_attempt_id=scope.action_attempt_id,
            event_type="action_intent_committed",
            actor_id="runtime",
            occurred_at=NOW + timedelta(seconds=1),
            output_refs=_scope_authority_output_refs(scope),
        )
    )
    for index, receipt in enumerate(grant_tuple, start=1):
        events.append(
            append_session_event_v1_2(
                events,
                session_id=scope.session_id,
                run_id=scope.research_run_id,
                run_invocation_id=scope.run_invocation_id,
                action_attempt_id=scope.action_attempt_id,
                event_type="disclosure_requested",
                actor_id="runtime",
                occurred_at=NOW + timedelta(seconds=index * 2),
                input_refs=(
                    f"disclosure-request://sha256/{receipt.request_digest}",
                ),
            )
        )
        events.append(
            append_session_event_v1_2(
                events,
                session_id=scope.session_id,
                run_id=scope.research_run_id,
                run_invocation_id=scope.run_invocation_id,
                action_attempt_id=scope.action_attempt_id,
                event_type="disclosure_granted",
                actor_id="runtime",
                occurred_at=NOW + timedelta(seconds=index * 2 + 1),
                input_refs=(
                    f"disclosure-request://sha256/{receipt.request_digest}",
                ),
                output_refs=(
                    f"disclosure-receipt://sha256/{receipt.receipt_digest}",
                    f"disclosure-resource://sha256/{receipt.resource_digest}",
                    _resource_binding_ref(receipt),
                ),
            )
        )
    ledger_snapshot = create_canonical_event_ledger_snapshot(
        ledger_snapshot_id=f"ledger-snapshot:{action_attempt_id.split(':')[-1]}",
        repository_ref="repository:canonical-session-events",
        session_id=scope.session_id,
        store_revision=1,
        events=tuple(events),
        canonical_tip_digest=events[-1].event_digest,
    )
    authority_record = _authority_record(scope, ledger_snapshot)
    ledger_reader = _StaticLedgerReader(ledger_snapshot)
    authority_resolver = _StaticAuthorityResolver(authority_record)
    ledger = build_disclosure_grant_ledger_view(
        ledger_view_id=f"ledger-view:{action_attempt_id.split(':')[-1]}",
        runtime_scope=scope,
        ledger_reader=ledger_reader,
        authority_resolver=authority_resolver,
        verified_receipts=grant_tuple,
    )
    context = DisclosureRuntimeContext(
        runtime_scope=scope,
        scope_authorization_record=authority_record,
        role=role,
        task_kind="dell_demand_analysis",
        consumed_disclosure_tokens=sum(
            receipt.estimated_context_tokens for receipt in grant_tuple
        ),
        grants=grant_tuple,
        grant_ledger_view=ledger,
    )
    _LEDGER_SNAPSHOTS_BY_VIEW_DIGEST[ledger.ledger_view_digest] = ledger_snapshot
    return context


def _authority_resolver(context: DisclosureRuntimeContext):
    return _StaticAuthorityResolver(context.scope_authorization_record)


def _ledger_reader(context: DisclosureRuntimeContext):
    return _StaticLedgerReader(
        _LEDGER_SNAPSHOTS_BY_VIEW_DIGEST[
            context.grant_ledger_view.ledger_view_digest
        ]
    )


def _catalog_resolver(context: DisclosureRuntimeContext, catalog):
    return _StaticCatalogResolver(
        runtime_scope_digest=context.runtime_scope.scope_digest,
        catalog=catalog,
    )


def _model_context_resolver(
    context: DisclosureRuntimeContext,
    runtime_policy: RuntimePolicySnapshot,
):
    ledger = _LEDGER_SNAPSHOTS_BY_VIEW_DIGEST[
        context.grant_ledger_view.ledger_view_digest
    ]
    authorization = context.scope_authorization_record
    state = _default_model_context_state()
    snapshot = build_current_model_context_snapshot(
        runtime_policy=runtime_policy,
        context_snapshot_id="context-snapshot:dell-current",
        resolver_ref="resolver:host-current-model-context",
        store_revision=1,
        runtime_scope_digest=context.runtime_scope.scope_digest,
        scope_authorization_record_digest=(
            authorization.authorization_record_digest
        ),
        session_id=context.runtime_scope.session_id,
        research_run_id=context.runtime_scope.research_run_id,
        run_invocation_id=context.runtime_scope.run_invocation_id,
        action_attempt_id=context.runtime_scope.action_attempt_id,
        task_id=context.runtime_scope.task_id,
        accepted_plan_digest=authorization.accepted_plan_digest,
        research_graph_digest=authorization.research_graph_digest,
        canonical_event_ledger_snapshot_digest=ledger.ledger_snapshot_digest,
        canonical_event_ledger_tip_digest=ledger.canonical_tip_digest,
        canonical_event_ledger_store_revision=ledger.store_revision,
        disclosure_policy_digest=context.runtime_scope.disclosure_policy_digest,
        **state,
    )
    return _StaticModelContextResolver(snapshot)


def _decide(
    *,
    request,
    catalog,
    policy,
    context,
    ledger_reader=None,
    catalog_resolver=_DEFAULT_RESOLVER,
):
    return decide_disclosure(
        request=request,
        catalog=catalog,
        policy=policy,
        context=context,
        ledger_reader=ledger_reader or _ledger_reader(context),
        catalog_resolver=(
            _catalog_resolver(context, catalog)
            if catalog_resolver is _DEFAULT_RESOLVER
            else catalog_resolver
        ),
        authority_resolver=_authority_resolver(context),
    )


def _grant_level(catalog, policy, level: str, context: DisclosureRuntimeContext):
    depth = {
        "L1": "contract",
        "L2": "resource_index",
        "L3": "content",
    }[level]
    parent = context.grants[-1].receipt_digest if context.grants and level != "L1" else None
    request = _request(
        catalog,
        policy,
        depth=depth,
        parent_receipt_digest=parent,
    )
    receipt = _decide(
        request=request, catalog=catalog, policy=policy, context=context
    )
    return receipt


@pytest.mark.fast_contract
def test_l1_grant_is_content_addressed_frozen_and_has_next_actions() -> None:
    catalog = _catalog()
    policy = _policy()
    request = _request(catalog, policy)

    receipt = _decide(
        request=request,
        catalog=catalog,
        policy=policy,
        context=_context(catalog=catalog, policy=policy),
    )

    assert receipt.status == "granted"
    assert receipt.granted_level == "L1"
    assert receipt.resource_digest == _digest("cap:s1-local-search-L1")
    assert receipt.available_next_actions
    assert receipt.receipt_digest == canonical_digest(
        receipt.model_dump(mode="json", exclude={"receipt_digest"})
    )
    with pytest.raises(ValidationError):
        receipt.status = "denied"


@pytest.mark.fast_contract
@pytest.mark.parametrize(
    ("field", "error_code", "remedy"),
    (
        ("catalog_digest", "stale_catalog_digest", "request_data_inventory"),
        (
            "inventory_snapshot_digest",
            "stale_inventory_snapshot_digest",
            "request_data_inventory",
        ),
        ("policy_digest", "stale_policy_digest", "request_human_review"),
    ),
)
def test_stale_digest_fails_closed_without_resource_leak(field, error_code, remedy) -> None:
    catalog = _catalog()
    policy = _policy()
    request = _request(catalog, policy, **{field: _digest(f"stale-{field}")})

    receipt = _decide(
        request=request,
        catalog=catalog,
        policy=policy,
        context=_context(),
    )

    assert receipt.status == "denied"
    assert receipt.error_code == error_code
    assert receipt.resource_uri is None
    assert receipt.resource_digest is None
    assert receipt.estimated_context_tokens == 0
    assert receipt.available_next_actions[0].action == remedy


@pytest.mark.fast_contract
def test_sealed_role_and_task_authority_cannot_be_supplied_by_provider() -> None:
    catalog = _catalog()
    policy = _policy()
    request = _request(catalog, policy)

    denied = _decide(
        request=request,
        catalog=catalog,
        policy=policy,
        context=_context(role="writer"),
    )
    assert denied.error_code == "disclosure_role_or_task_not_authorized"
    assert {item.action for item in denied.available_next_actions} == {
        "submit_plan_delta",
        "request_human_review",
    }

    with pytest.raises(ValidationError):
        DisclosureRequest(**request.model_dump(), role="evidence_specialist")
    schema = provider_visible_disclosure_schema()
    serialized = str(schema).lower()
    for sealed_name in (
        "case_id",
        "session_id",
        "research_run_id",
        "task_id",
        "operator_authorized",
        "runtime_scope",
    ):
        assert sealed_name not in serialized


@pytest.mark.fast_contract
def test_depth_must_escalate_one_current_receipt_at_a_time() -> None:
    catalog = _catalog()
    policy = _policy()

    direct_l2 = _grant_level(catalog, policy, "L2", _context(catalog=catalog, policy=policy))
    assert direct_l2.error_code == "disclosure_depth_escalation_required"
    assert direct_l2.available_next_actions[0].action == "request_disclosure"

    l1 = _grant_level(catalog, policy, "L1", _context(catalog=catalog, policy=policy))
    context = _context(catalog=catalog, policy=policy, grants=(l1,))
    l2 = _grant_level(catalog, policy, "L2", context)
    assert l2.status == "granted"
    assert l2.granted_level == "L2"

    stale_body = l1.model_dump(mode="python", exclude={"receipt_digest"})
    stale_body["catalog_digest"] = _digest("other-catalog")
    stale_parent = DisclosureReceipt(
        **stale_body,
        receipt_digest=canonical_digest(stale_body),
    )
    stale_context = _context(catalog=catalog, policy=policy, grants=(stale_parent,))
    stale = _grant_level(catalog, policy, "L2", stale_context)
    assert stale.error_code == "disclosure_depth_escalation_required"


@pytest.mark.fast_contract
def test_token_budget_never_silently_truncates_or_completes() -> None:
    catalog = _catalog(
        resources=(
            _resource("L1", tokens=75),
            _resource("L2", tokens=100),
            _resource("L3", tokens=100),
            _resource("L4", tokens=100),
        )
    )
    policy = _policy(max_receipt=100, max_task=150)
    l1 = _grant_level(catalog, policy, "L1", _context(catalog=catalog, policy=policy))
    context = _context(catalog=catalog, policy=policy, grants=(l1,))
    request = _request(
        catalog,
        policy,
        depth="resource_index",
        parent_receipt_digest=l1.receipt_digest,
    )
    receipt = _decide(
        request=request,
        catalog=catalog,
        policy=policy,
        context=context,
    )

    assert receipt.status == "denied"
    assert receipt.error_code == "disclosure_token_budget_exceeded"
    assert {action.action for action in receipt.available_next_actions} == {
        "request_deeper_inventory",
        "submit_plan_delta",
        "request_human_review",
    }
    assert "complete" not in receipt.decision_reason.lower()


@pytest.mark.fast_contract
def test_l4_is_operator_only_even_after_valid_l1_to_l3_chain() -> None:
    catalog = _catalog()
    policy = _policy()
    grants = []
    context = _context(catalog=catalog, policy=policy)
    for level in ("L1", "L2", "L3"):
        receipt = _grant_level(catalog, policy, level, context)
        assert receipt.status == "granted"
        grants.append(receipt)
        context = _context(catalog=catalog, policy=policy, grants=grants)

    with pytest.raises(ValidationError):
        _request(catalog, policy, depth="restricted_diagnostic")
    provider_schema = str(provider_visible_disclosure_schema()).lower()
    assert "restricted_diagnostic" not in provider_schema
    assert "diagnostic" not in provider_schema


@pytest.mark.fast_contract
def test_recursive_skill_reference_is_bounded_and_never_grants_authority() -> None:
    skill_ref = "skill:dell-demand-method"
    child_ref = "skill:dell-demand-method/reference/cycle-check"
    resources = (
        _resource("L1"),
        _resource("L1", ref=skill_ref, kind="skill"),
        _resource("L2", ref=skill_ref, kind="skill"),
        _resource("L3", ref=child_ref, kind="skill", parent_ref=skill_ref),
    )
    catalog = build_disclosure_catalog(
        snapshot_id="snapshot:dell-skill-01",
        inventory_snapshot_digest=_digest("inventory"),
        capabilities=(
            _capability(),
            CapabilityDescriptor(
                capability_ref=skill_ref,
                kind="skill",
                name="Dell demand method",
                purpose="Teach a demand-analysis method without supplying an answer.",
                authority_summary="Method only; no tool, Evidence, or policy authority.",
                cost_tier="none",
                latency_tier="local",
                maximum_disclosure_level="L3",
            ),
        ),
        resources=resources,
    )
    policy = _policy(recursion=0)
    request = _request(
        catalog,
        policy,
        depth="content",
        kind="skill",
        ref=child_ref,
        parent_receipt_digest=_digest("synthetic-parent"),
    )

    receipt = _decide(
        request=request,
        catalog=catalog,
        policy=policy,
        context=_context(catalog=catalog, policy=policy),
    )
    assert receipt.error_code == "disclosure_recursive_depth_exceeded"
    assert receipt.resource_uri is None
    skill = next(resource for resource in catalog.resources if resource.kind == "skill")
    assert skill.grants_tool_authority is False
    assert skill.grants_evidence_authority is False
    assert skill.grants_policy_authority is False


@pytest.mark.fast_contract
def test_manifest_contains_only_refs_and_rejects_denied_or_stale_receipts() -> None:
    catalog = _catalog()
    policy = _policy()
    runtime_policy = _runtime_policy(catalog, policy)
    granted = _decide(
        request=_request(catalog, policy),
        catalog=catalog,
        policy=policy,
        context=_context(),
    )
    manifest_context = _context(catalog=catalog, policy=policy, grants=(granted,))
    action = AvailableNextAction(
        action="submit_plan_delta",
        reason="Revise the plan after consuming the newly disclosed contract.",
        target_ref="task:dell-demand",
    )
    manifest = assemble_model_visible_manifest(
        manifest_id="manifest:dell-turn-01",
        objective=_ASSIGNED_OBJECTIVE,
        runtime_policy=runtime_policy,
        catalog=catalog,
        policy=policy,
        context=manifest_context,
        ledger_reader=_ledger_reader(manifest_context),
        catalog_resolver=_catalog_resolver(manifest_context, catalog),
        authority_resolver=_authority_resolver(manifest_context),
        model_context_resolver=_model_context_resolver(
            manifest_context,
            runtime_policy,
        ),
        granted_receipts=(granted,),
    )

    assert manifest.granted_disclosure_receipt_refs == (granted.receipt_digest,)
    assert manifest.disclosure_policy_digest == policy.policy_digest
    assert manifest.objective_digest == research_objective_digest(_ASSIGNED_OBJECTIVE)
    assert (
        manifest.task_assignment_digest
        == manifest_context.scope_authorization_record.task_assignment_digest
    )
    assert (
        manifest.research_graph_digest
        == manifest_context.scope_authorization_record.research_graph_digest
    )
    assert manifest.plan_digest == manifest_context.scope_authorization_record.accepted_plan_digest
    assert manifest.governance_summary == derive_runtime_governance_summary(runtime_policy)
    assert len(manifest.current_model_context_snapshot_digest) == 64
    assert manifest.public_content_only is True
    dumped = manifest.model_dump_json()
    assert granted.resource_uri not in dumped
    for sealed_name in ("session_id", "operator_authorized", "physical_route_selectors"):
        assert sealed_name not in dumped
    assert manifest.manifest_digest == canonical_digest(
        manifest.model_dump(mode="json", exclude={"manifest_digest"})
    )

    denied_context = _context(catalog=catalog, policy=policy)
    denied = _decide(
        request=_request(catalog, policy, catalog_digest=_digest("stale")),
        catalog=catalog,
        policy=policy,
        context=denied_context,
    )
    with pytest.raises(ValueError, match="denied_disclosure_receipt"):
        assemble_model_visible_manifest(
            manifest_id="manifest:dell-turn-02",
            objective=_ASSIGNED_OBJECTIVE,
            runtime_policy=runtime_policy,
            catalog=catalog,
            policy=policy,
            context=denied_context,
            ledger_reader=_ledger_reader(denied_context),
            catalog_resolver=_catalog_resolver(denied_context, catalog),
            authority_resolver=_authority_resolver(denied_context),
            model_context_resolver=_model_context_resolver(
                denied_context,
                runtime_policy,
            ),
            granted_receipts=(denied,),
        )


@pytest.mark.fast_contract
def test_one_scope_composes_zero_model_authority_disclosure_and_manifest() -> None:
    """One real scope must bind both policy layers without digest aliasing."""

    catalog = _catalog()
    disclosure_policy = _policy()
    runtime_policy_body = {
        "contract_version": "1.2",
        "policy_snapshot_id": "policy:dell:wave0a:composed",
        "case_id": "case:dell",
        "case_version": "FIN-0.1.3",
        "research_as_of": "2026-09-03",
        "data_snapshot_digest": catalog.inventory_snapshot_digest,
        "catalog_digest": catalog.catalog_digest,
        "disclosure_policy_digest": disclosure_policy.policy_digest,
        "allowed_branch_refs": ("branch:dell",),
        "allowed_authority_class_refs": ("permission:read-candidate",),
        "paid_execution_authority_status": "not_authorized",
        "paid_execution_owner_decision_ref": None,
        "hitl_may_grant_or_elevate_paid_authority": False,
        "evidence_promotion_policy": "qualified_reviewer_only",
        "s2_write_policy": "not_authorized",
        "public_gap_policy": "gap_eligibility_receipt_required",
    }
    runtime_policy = RuntimePolicySnapshot(
        **runtime_policy_body,
        policy_digest=canonical_digest(runtime_policy_body),
    )
    node_kinds = (
        "lead",
        "specialist",
        "counter",
        "semantic_research_verifier",
        "writer",
        "final_semantic_verifier",
    )
    matrix_body = {
        "contract_version": "1.2",
        "matrix_id": "authority-matrix:dell:wave0a:composed",
        "policy_digest": runtime_policy.policy_digest,
        "entries": tuple(
            ModelNodeAuthorityEntry(
                node_id=f"node:{kind}:composed",
                node_kind=kind,
                node_purpose=f"Exercise the bounded {kind} contract without a model call",
                input_scale="No provider input is authorized",
                required_outputs=(f"artifact:{kind}",),
                schema_burden="Strict typed contracts",
                materiality_quality_risk="Material Dell research remains gated",
                reasoning_profile="unassigned",
                stop_and_truncation_behavior="Stop before provider transport",
                repair_policy="No model repair is authorized",
                retry_policy="No model retry is authorized",
            )
            for kind in node_kinds
        ),
        "authority_source": "owner_decision_only",
        "hitl_may_grant_or_elevate_paid_authority": False,
    }
    authority_matrix = ModelNodeAuthorityMatrix(
        **matrix_body,
        matrix_digest=canonical_digest(matrix_body),
    )
    context = _context(
        catalog=catalog,
        policy=disclosure_policy,
        runtime_policy_digest=runtime_policy.policy_digest,
        authority_matrix_digest=authority_matrix.matrix_digest,
    )

    boundary = validate_zero_model_runtime_boundary(
        policy=runtime_policy,
        authority_matrix=authority_matrix,
        runtime_scope=context.runtime_scope,
        scope_authorization=context.scope_authorization_record,
    )
    assert boundary.policy_digest == runtime_policy.policy_digest
    assert boundary.disclosure_policy_digest == disclosure_policy.policy_digest

    grant = _decide(
        request=_request(catalog, disclosure_policy),
        catalog=catalog,
        policy=disclosure_policy,
        context=context,
    )
    assert grant.status == "granted"
    manifest_context = _context(
        catalog=catalog,
        policy=disclosure_policy,
        grants=(grant,),
        runtime_policy_digest=runtime_policy.policy_digest,
        authority_matrix_digest=authority_matrix.matrix_digest,
    )
    assert manifest_context.runtime_scope == context.runtime_scope

    manifest = assemble_model_visible_manifest(
        manifest_id="manifest:dell:composed-policy-scope",
        objective=_ASSIGNED_OBJECTIVE,
        runtime_policy=runtime_policy,
        catalog=catalog,
        policy=disclosure_policy,
        context=manifest_context,
        ledger_reader=_ledger_reader(manifest_context),
        catalog_resolver=_catalog_resolver(manifest_context, catalog),
        authority_resolver=_authority_resolver(manifest_context),
        model_context_resolver=_model_context_resolver(
            manifest_context,
            runtime_policy,
        ),
        granted_receipts=(grant,),
    )
    assert manifest.granted_disclosure_receipt_refs == (grant.receipt_digest,)


@pytest.mark.fast_contract
@pytest.mark.parametrize(
    ("field_name", "forged_value"),
    (
        ("plan_digest", _digest("forged-unaccepted-plan")),
        ("authority_matrix_digest", _digest("forged-authority-matrix")),
        ("governance_summary", "Caller-authored governance override."),
        ("latest_plan_delta_refs", ("delta:caller-fabricated",)),
        ("observation_refs", ("observation:caller-fabricated",)),
        ("unresolved_feedback_refs", ("feedback:caller-fabricated",)),
        (
            "available_next_actions",
            (
                AvailableNextAction(
                    action="pause",
                    reason="Caller claims the case is already complete.",
                ),
            ),
        ),
        ("budget_status", "exhausted"),
        ("stop_status", "stop_sufficient"),
        ("intervention_status", "applied"),
        ("context_checkpoint_ref", "checkpoint:caller-fabricated"),
    ),
)
def test_manifest_signature_rejects_caller_authored_current_state(
    field_name: str,
    forged_value,
) -> None:
    catalog = _catalog()
    policy = _policy()
    runtime_policy = _runtime_policy(catalog, policy)
    context = _context(catalog=catalog, policy=policy)
    action = AvailableNextAction(
        action="submit_plan_delta",
        reason="Revise only the current accepted plan after validation.",
        target_ref=context.runtime_scope.task_id,
    )
    values = {
        "manifest_id": f"manifest:dell:forged-{field_name}",
        "objective": _ASSIGNED_OBJECTIVE,
        "runtime_policy": runtime_policy,
        "catalog": catalog,
        "policy": policy,
        "context": context,
        "ledger_reader": _ledger_reader(context),
        "catalog_resolver": _catalog_resolver(context, catalog),
        "authority_resolver": _authority_resolver(context),
        "model_context_resolver": _model_context_resolver(
            context,
            runtime_policy,
        ),
        "granted_receipts": (),
    }
    values[field_name] = forged_value

    with pytest.raises(TypeError, match="unexpected keyword argument"):
        assemble_model_visible_manifest(**values)


@pytest.mark.fast_contract
def test_manifest_requires_host_current_model_context_resolver() -> None:
    catalog = _catalog()
    policy = _policy()
    runtime_policy = _runtime_policy(catalog, policy)
    context = _context(catalog=catalog, policy=policy)

    with pytest.raises(ValueError, match="current_model_context_resolver_required"):
        assemble_model_visible_manifest(
            manifest_id="manifest:dell:missing-current-context-resolver",
            objective=_ASSIGNED_OBJECTIVE,
            runtime_policy=runtime_policy,
            catalog=catalog,
            policy=policy,
            context=context,
            ledger_reader=_ledger_reader(context),
            catalog_resolver=_catalog_resolver(context, catalog),
            authority_resolver=_authority_resolver(context),
            model_context_resolver=None,
            granted_receipts=(),
        )


@pytest.mark.fast_contract
def test_manifest_rejects_re_signed_current_context_with_stale_plan_binding() -> None:
    catalog = _catalog()
    policy = _policy()
    runtime_policy = _runtime_policy(catalog, policy)
    context = _context(catalog=catalog, policy=policy)
    action = AvailableNextAction(
        action="submit_plan_delta",
        reason="Revise only the current accepted plan after validation.",
        target_ref=context.runtime_scope.task_id,
    )
    current_resolver = _model_context_resolver(
        context,
        runtime_policy,
    )
    forged_body = current_resolver.snapshot.model_dump(
        mode="python",
        exclude={"context_snapshot_digest"},
    )
    forged_body["accepted_plan_digest"] = _digest("caller-re-signed-stale-plan")
    forged_snapshot = CurrentModelContextSnapshot(
        **forged_body,
        context_snapshot_digest=canonical_digest(forged_body),
    )

    with pytest.raises(
        ValueError,
        match="current_model_context_binding_stale:accepted_plan_digest",
    ):
        assemble_model_visible_manifest(
            manifest_id="manifest:dell:re-signed-stale-current-context",
            objective=_ASSIGNED_OBJECTIVE,
            runtime_policy=runtime_policy,
            catalog=catalog,
            policy=policy,
            context=context,
            ledger_reader=_ledger_reader(context),
            catalog_resolver=_catalog_resolver(context, catalog),
            authority_resolver=_authority_resolver(context),
            model_context_resolver=_StaticModelContextResolver(forged_snapshot),
            granted_receipts=(),
        )


@pytest.mark.fast_contract
def test_manifest_rejects_re_signed_current_payload_not_bound_to_runtime_scope() -> None:
    catalog = _catalog()
    policy = _policy()
    runtime_policy = _runtime_policy(catalog, policy)
    context = _context(catalog=catalog, policy=policy)
    current = _model_context_resolver(context, runtime_policy).snapshot
    forged_fields = current.model_dump(
        mode="python",
        exclude={
            "contract_version",
            "runtime_policy_digest",
            "governance_summary_digest",
            "current_state_digest",
            "issued_by",
            "context_snapshot_digest",
        },
    )
    forged_fields.update(
        {
            "latest_plan_delta_refs": ("delta:caller-fabricated",),
            "observation_refs": ("observation:caller-fabricated",),
            "unresolved_feedback_refs": ("feedback:caller-fabricated",),
            "available_next_actions": (
                AvailableNextAction(
                    action="pause",
                    reason="Caller claims the current action must stop.",
                ),
            ),
            "budget_status": "exhausted",
            "stop_status": "pause_required",
            "intervention_status": "applied",
            "context_checkpoint_ref": "checkpoint:caller-fabricated",
        }
    )
    forged = build_current_model_context_snapshot(
        runtime_policy=runtime_policy,
        **forged_fields,
    )
    assert (
        forged.current_state_digest
        != context.runtime_scope.model_context_state_digest
    )

    with pytest.raises(
        ValueError,
        match="current_model_context_binding_stale:current_state_digest",
    ):
        assemble_model_visible_manifest(
            manifest_id="manifest:dell:re-signed-forged-current-payload",
            objective=_ASSIGNED_OBJECTIVE,
            runtime_policy=runtime_policy,
            catalog=catalog,
            policy=policy,
            context=context,
            ledger_reader=_ledger_reader(context),
            catalog_resolver=_catalog_resolver(context, catalog),
            authority_resolver=_authority_resolver(context),
            model_context_resolver=_StaticModelContextResolver(forged),
            granted_receipts=(),
        )


@pytest.mark.fast_contract
@pytest.mark.parametrize(
    ("field_name", "forged_value", "error_code"),
    (
        (
            "case_id",
            "case:other",
            "manifest_runtime_policy_identity_or_snapshot_mismatch",
        ),
        (
            "case_version",
            "FIN-9.9.9",
            "manifest_runtime_policy_identity_or_snapshot_mismatch",
        ),
        (
            "research_as_of",
            "2030-01-01",
            "manifest_runtime_policy_identity_or_snapshot_mismatch",
        ),
        (
            "data_snapshot_digest",
            _digest("other-data-snapshot"),
            "manifest_runtime_policy_identity_or_snapshot_mismatch",
        ),
        (
            "catalog_digest",
            _digest("other-catalog"),
            "manifest_runtime_policy_catalog_mismatch",
        ),
        (
            "disclosure_policy_digest",
            _digest("other-disclosure-policy"),
            "manifest_runtime_policy_disclosure_policy_mismatch",
        ),
        (
            "allowed_branch_refs",
            ("branch:other",),
            "manifest_runtime_policy_branch_scope_not_allowed",
        ),
        (
            "allowed_authority_class_refs",
            ("permission:other",),
            "manifest_runtime_policy_permission_not_allowed",
        ),
    ),
)
def test_manifest_rejects_runtime_policy_internal_boundary_mismatch(
    field_name: str,
    forged_value,
    error_code: str,
) -> None:
    catalog = _catalog()
    disclosure_policy = _policy()
    policy_body = _runtime_policy(catalog, disclosure_policy).model_dump(
        mode="python",
        exclude={"policy_digest"},
    )
    policy_body[field_name] = forged_value
    runtime_policy = RuntimePolicySnapshot(
        **policy_body,
        policy_digest=canonical_digest(policy_body),
    )
    context = _context(
        catalog=catalog,
        policy=disclosure_policy,
        runtime_policy_digest=runtime_policy.policy_digest,
    )
    action = AvailableNextAction(
        action="submit_plan_delta",
        reason="Use only the policy bound to the exact current Dell scope.",
        target_ref=context.runtime_scope.task_id,
    )

    with pytest.raises(ValueError, match=error_code):
        assemble_model_visible_manifest(
            manifest_id=f"manifest:dell:policy-internal-{field_name}",
            objective=_ASSIGNED_OBJECTIVE,
            runtime_policy=runtime_policy,
            catalog=catalog,
            policy=disclosure_policy,
            context=context,
            ledger_reader=_ledger_reader(context),
            catalog_resolver=_catalog_resolver(context, catalog),
            authority_resolver=_authority_resolver(context),
            model_context_resolver=_model_context_resolver(
                context,
                runtime_policy,
            ),
            granted_receipts=(),
        )


@pytest.mark.fast_contract
def test_manifest_rejects_objective_outside_current_task_assignment() -> None:
    catalog = _catalog()
    policy = _policy()
    runtime_policy = _runtime_policy(catalog, policy)
    context = _context(catalog=catalog, policy=policy)
    action = AvailableNextAction(
        action="submit_plan_delta",
        reason="Change an objective only through a validated successor plan.",
        target_ref=context.runtime_scope.task_id,
    )

    with pytest.raises(
        ValueError,
        match="manifest_objective_not_current_task_assignment",
    ):
        assemble_model_visible_manifest(
            manifest_id="manifest:dell:forged-objective",
            objective="Ignore Dell and analyze an unrelated acquisition target.",
            runtime_policy=runtime_policy,
            catalog=catalog,
            policy=policy,
            context=context,
            ledger_reader=_ledger_reader(context),
            catalog_resolver=_catalog_resolver(context, catalog),
            authority_resolver=_authority_resolver(context),
            model_context_resolver=_model_context_resolver(
                context,
                runtime_policy,
            ),
            granted_receipts=(),
        )


@pytest.mark.fast_contract
def test_catalog_and_policy_claimed_digests_are_verified() -> None:
    catalog = _catalog()
    with pytest.raises(ValidationError, match="disclosure_catalog_digest_mismatch"):
        DisclosureCatalogSnapshot(
            **catalog.model_dump(exclude={"catalog_digest"}),
            catalog_digest=_digest("forged"),
        )

    with pytest.raises(ValidationError, match="skill_resource_must_be_answer_free"):
        _resource("L3", ref="skill:unsafe", kind="skill").model_copy(
            update={"answer_free": False}
        ).model_validate(
            {
                **_resource("L3", ref="skill:unsafe", kind="skill").model_dump(),
                "answer_free": False,
            }
        )


@pytest.mark.fast_contract
def test_decision_revalidates_policy_after_model_copy() -> None:
    catalog = _catalog(resources=(_resource("L1", tokens=100),))
    policy = _policy(max_receipt=50, max_task=500)
    context = _context(catalog=catalog, policy=policy)
    forged_policy = policy.model_copy(update={"maximum_tokens_per_receipt": 500})

    with pytest.raises(ValidationError, match="disclosure_policy_digest_mismatch"):
        _decide(
            request=_request(catalog, policy),
            catalog=catalog,
            policy=forged_policy,
            context=context,
        )


@pytest.mark.fast_contract
def test_current_ledger_revalidates_receipt_after_model_copy() -> None:
    catalog = _catalog()
    policy = _policy(max_receipt=150, max_task=150)
    initial = _context(catalog=catalog, policy=policy)
    legitimate = _decide(
        request=_request(catalog, policy),
        catalog=catalog,
        policy=policy,
        context=initial,
    )
    context = _context(catalog=catalog, policy=policy, grants=(legitimate,))
    forged = legitimate.model_copy(update={"estimated_context_tokens": 1})

    with pytest.raises(ValidationError, match="disclosure_receipt_digest_mismatch"):
        build_disclosure_grant_ledger_view(
            ledger_view_id=context.grant_ledger_view.ledger_view_id,
            runtime_scope=context.runtime_scope,
            ledger_reader=_ledger_reader(context),
            authority_resolver=_authority_resolver(context),
            verified_receipts=(forged,),
        )

    forged_context = context.model_copy(
        update={
            "grants": (forged,),
            "consumed_disclosure_tokens": 1,
        }
    )
    with pytest.raises(ValidationError, match="disclosure_receipt_digest_mismatch"):
        _decide(
            request=_request(
                catalog,
                policy,
                depth="resource_index",
                parent_receipt_digest=legitimate.receipt_digest,
            ),
            catalog=catalog,
            policy=policy,
            context=forged_context,
        )


@pytest.mark.fast_contract
def test_current_ledger_revalidates_snapshot_after_model_copy() -> None:
    catalog = _catalog()
    policy = _policy()
    context = _context(catalog=catalog, policy=policy)
    snapshot = _LEDGER_SNAPSHOTS_BY_VIEW_DIGEST[
        context.grant_ledger_view.ledger_view_digest
    ]
    forged_snapshot = snapshot.model_copy(
        update={"repository_ref": "repository:forged-current-ledger"}
    )

    with pytest.raises(
        ValidationError,
        match="canonical_event_ledger_snapshot_digest_invalid",
    ):
        build_disclosure_grant_ledger_view(
            ledger_view_id=context.grant_ledger_view.ledger_view_id,
            runtime_scope=context.runtime_scope,
            ledger_reader=_StaticLedgerReader(forged_snapshot),
            authority_resolver=_authority_resolver(context),
            verified_receipts=(),
        )

@pytest.mark.fast_contract
def test_manifest_binds_disclosure_policy_even_without_grants() -> None:
    catalog = _catalog()
    active_policy = _policy()
    stale_policy = _policy(max_receipt=400, max_task=1_800)
    context = _context(catalog=catalog, policy=active_policy)
    runtime_policy = _runtime_policy(catalog, active_policy)
    action = AvailableNextAction(
        action="request_data_inventory",
        reason="Refresh only from the policy bound to the current scope.",
    )

    with pytest.raises(ValueError, match="manifest_disclosure_policy_scope_mismatch"):
        assemble_model_visible_manifest(
            manifest_id="manifest:dell:stale-disclosure-policy",
            objective=_ASSIGNED_OBJECTIVE,
            runtime_policy=runtime_policy,
            catalog=catalog,
            policy=stale_policy,
            context=context,
            ledger_reader=_ledger_reader(context),
            catalog_resolver=_catalog_resolver(context, catalog),
            authority_resolver=_authority_resolver(context),
            model_context_resolver=_model_context_resolver(
                context,
                runtime_policy,
            ),
            granted_receipts=(),
        )

@pytest.mark.fast_contract
@pytest.mark.parametrize("current_is_rewritten", (False, True))
def test_decision_rejects_self_signed_or_stale_catalog_from_same_snapshot(
    current_is_rewritten: bool,
) -> None:
    catalog = _catalog()
    rewritten = _catalog_with_rewritten_l1(catalog, suffix="rewritten")
    policy = _policy()
    context = _context(catalog=catalog, policy=policy)
    current = rewritten if current_is_rewritten else catalog
    supplied = catalog if current_is_rewritten else rewritten

    assert current.inventory_snapshot_digest == supplied.inventory_snapshot_digest
    assert current.resources[0].ref == supplied.resources[0].ref
    assert current.resources[0].resource_uri != supplied.resources[0].resource_uri
    assert current.resources[0].resource_digest != supplied.resources[0].resource_digest

    with pytest.raises(ValueError, match="disclosure_catalog_stale_or_self_signed"):
        _decide(
            request=_request(supplied, policy),
            catalog=supplied,
            policy=policy,
            context=context,
            catalog_resolver=_catalog_resolver(context, current),
        )


@pytest.mark.fast_contract
def test_decision_revalidates_nested_current_catalog_semantics() -> None:
    catalog = _catalog()
    policy = _policy()
    context = _context(catalog=catalog, policy=policy)
    resources = list(catalog.resources)
    resources[0] = resources[0].model_copy(update={"answer_free": False})
    forged_body = {
        "contract_version": catalog.contract_version,
        "snapshot_id": catalog.snapshot_id,
        "inventory_snapshot_digest": catalog.inventory_snapshot_digest,
        "capabilities": catalog.capabilities,
        "resources": tuple(resources),
    }
    forged = DisclosureCatalogSnapshot.model_construct(
        **forged_body,
        catalog_digest=canonical_digest(forged_body),
    )

    with pytest.raises(ValidationError, match="l1_resource_must_be_answer_free"):
        _decide(
            request=_request(forged, policy),
            catalog=forged,
            policy=policy,
            context=context,
            catalog_resolver=_catalog_resolver(context, forged),
        )


@pytest.mark.fast_contract
def test_manifest_rejects_self_signed_catalog_from_same_snapshot() -> None:
    catalog = _catalog()
    forged = _catalog_with_rewritten_l1(catalog, suffix="forged")
    policy = _policy()
    runtime_policy = _runtime_policy(catalog, policy)
    context = _context(catalog=catalog, policy=policy)
    action = AvailableNextAction(
        action="request_data_inventory",
        reason="Refresh only from the host-current disclosure catalog.",
    )

    with pytest.raises(ValueError, match="disclosure_catalog_stale_or_self_signed"):
        assemble_model_visible_manifest(
            manifest_id="manifest:dell:forged-catalog",
            objective=_ASSIGNED_OBJECTIVE,
            runtime_policy=runtime_policy,
            catalog=forged,
            policy=policy,
            context=context,
            ledger_reader=_ledger_reader(context),
            catalog_resolver=_catalog_resolver(context, catalog),
            authority_resolver=_authority_resolver(context),
            model_context_resolver=_model_context_resolver(
                context,
                runtime_policy,
            ),
            granted_receipts=(),
        )


@pytest.mark.fast_contract
@pytest.mark.parametrize(
    ("catalog_resolver", "error_code"),
    (
        (None, "disclosure_catalog_resolver_required"),
        (
            _NullCatalogResolver(),
            "disclosure_catalog_absent_from_authoritative_store",
        ),
    ),
)
def test_decision_requires_host_current_catalog_resolver(
    catalog_resolver,
    error_code: str,
) -> None:
    catalog = _catalog()
    policy = _policy()
    context = _context(catalog=catalog, policy=policy)

    with pytest.raises(ValueError, match=error_code):
        _decide(
            request=_request(catalog, policy),
            catalog=catalog,
            policy=policy,
            context=context,
            catalog_resolver=catalog_resolver,
        )


@pytest.mark.fast_contract
def test_receipt_requires_canonical_event_membership_and_exact_scope() -> None:
    catalog = _catalog()
    policy = _policy()
    initial = _context(catalog=catalog, policy=policy)
    legitimate = _decide(
        request=_request(catalog, policy),
        catalog=catalog,
        policy=policy,
        context=initial,
    )
    forged_body = legitimate.model_dump(mode="python", exclude={"receipt_digest"})
    forged_body["resource_digest"] = _digest("forged-resource")
    forged = DisclosureReceipt(
        **forged_body,
        receipt_digest=canonical_digest(forged_body),
    )

    scope = initial.runtime_scope
    events = [
        append_session_event_v1_2(
            (),
            session_id=scope.session_id,
            event_type="session_created",
            actor_id="runtime",
            occurred_at=NOW,
        )
    ]
    events.append(
        append_session_event_v1_2(
            events,
            session_id=scope.session_id,
            run_id=scope.research_run_id,
            run_invocation_id=scope.run_invocation_id,
            action_attempt_id=scope.action_attempt_id,
            event_type="action_intent_committed",
            actor_id="runtime",
            occurred_at=NOW + timedelta(seconds=1),
            output_refs=_scope_authority_output_refs(scope),
        )
    )
    events.append(
        append_session_event_v1_2(
            events,
            session_id=scope.session_id,
            run_id=scope.research_run_id,
            run_invocation_id=scope.run_invocation_id,
            action_attempt_id=scope.action_attempt_id,
            event_type="disclosure_requested",
            actor_id="runtime",
            occurred_at=NOW + timedelta(seconds=2),
            input_refs=(
                f"disclosure-request://sha256/{legitimate.request_digest}",
            ),
        )
    )
    events.append(
        append_session_event_v1_2(
            events,
            session_id=scope.session_id,
            run_id=scope.research_run_id,
            run_invocation_id=scope.run_invocation_id,
            action_attempt_id=scope.action_attempt_id,
            event_type="disclosure_granted",
            actor_id="runtime",
            occurred_at=NOW + timedelta(seconds=3),
            input_refs=(
                f"disclosure-request://sha256/{legitimate.request_digest}",
            ),
            output_refs=(
                f"disclosure-receipt://sha256/{legitimate.receipt_digest}",
                f"disclosure-resource://sha256/{legitimate.resource_digest}",
                _resource_binding_ref(legitimate),
            ),
        )
    )
    snapshot = create_canonical_event_ledger_snapshot(
        ledger_snapshot_id="ledger-snapshot:forged-test",
        repository_ref="repository:canonical-session-events",
        session_id=scope.session_id,
        store_revision=2,
        events=tuple(events),
        canonical_tip_digest=events[-1].event_digest,
    )
    authority_record = _authority_record(scope, snapshot)
    with pytest.raises(ValueError, match="absent_from_canonical_event_ledger"):
        build_disclosure_grant_ledger_view(
            ledger_view_id="ledger-view:forged",
            runtime_scope=scope,
            ledger_reader=_StaticLedgerReader(snapshot),
            authority_resolver=_StaticAuthorityResolver(authority_record),
            verified_receipts=(forged,),
        )

    with pytest.raises(ValidationError, match="scope_mismatch"):
        _context(
            catalog=catalog,
            policy=policy,
            grants=(legitimate,),
            action_attempt_id="action-attempt:02",
        )


@pytest.mark.fast_contract
def test_caller_self_signed_grant_view_cannot_unlock_disclosure_or_manifest() -> None:
    catalog = _catalog()
    policy = _policy()
    initial = _context(catalog=catalog, policy=policy)
    unrecorded_l1 = _decide(
        request=_request(catalog, policy),
        catalog=catalog,
        policy=policy,
        context=initial,
    )

    forged_body = initial.grant_ledger_view.model_dump(
        mode="python",
        exclude={"ledger_view_digest"},
    )
    forged_body["source_request_event_digests"] = ("a" * 64,)
    forged_body["source_grant_event_digests"] = ("b" * 64,)
    forged_body["verified_receipt_digests"] = (unrecorded_l1.receipt_digest,)
    forged_view = DisclosureGrantLedgerView(
        **forged_body,
        ledger_view_digest=canonical_digest(forged_body),
    )
    forged_context = DisclosureRuntimeContext(
        runtime_scope=initial.runtime_scope,
        scope_authorization_record=initial.scope_authorization_record,
        role=initial.role,
        task_kind=initial.task_kind,
        consumed_disclosure_tokens=unrecorded_l1.estimated_context_tokens,
        grants=(unrecorded_l1,),
        grant_ledger_view=forged_view,
    )
    current_reader = _ledger_reader(initial)
    current_authority = _authority_resolver(forged_context)

    with pytest.raises(
        ValueError,
        match="disclosure_receipt_absent_from_canonical_event_ledger",
    ):
        forged_context.validate_current_grant_view(
            ledger_reader=current_reader,
            authority_resolver=current_authority,
        )

    l2_request = _request(
        catalog,
        policy,
        depth="resource_index",
        parent_receipt_digest=unrecorded_l1.receipt_digest,
    )
    with pytest.raises(
        ValueError,
        match="disclosure_receipt_absent_from_canonical_event_ledger",
    ):
        decide_disclosure(
            request=l2_request,
            catalog=catalog,
            policy=policy,
            context=forged_context,
            ledger_reader=current_reader,
            catalog_resolver=_catalog_resolver(forged_context, catalog),
            authority_resolver=current_authority,
        )

    action = AvailableNextAction(
        action="submit_plan_delta",
        reason="Do not consume a disclosure absent from the canonical ledger.",
        target_ref="task:dell-demand",
    )
    runtime_policy = _runtime_policy(catalog, policy)
    with pytest.raises(
        ValueError,
        match="disclosure_receipt_absent_from_canonical_event_ledger",
    ):
        assemble_model_visible_manifest(
            manifest_id="manifest:dell:self-signed-ledger-view",
            objective=_ASSIGNED_OBJECTIVE,
            runtime_policy=runtime_policy,
            catalog=catalog,
            policy=policy,
            context=forged_context,
            ledger_reader=current_reader,
            catalog_resolver=_catalog_resolver(forged_context, catalog),
            authority_resolver=current_authority,
            model_context_resolver=None,
            granted_receipts=(unrecorded_l1,),
        )


@pytest.mark.fast_contract
def test_current_ledger_rebuild_rejects_stale_grant_view_metadata() -> None:
    catalog = _catalog()
    policy = _policy()
    initial = _context(catalog=catalog, policy=policy)
    l1 = _decide(
        request=_request(catalog, policy),
        catalog=catalog,
        policy=policy,
        context=initial,
    )
    old_context = _context(catalog=catalog, policy=policy, grants=(l1,))
    old_snapshot = _LEDGER_SNAPSHOTS_BY_VIEW_DIGEST[
        old_context.grant_ledger_view.ledger_view_digest
    ]
    current_events = tuple(old_snapshot.events)
    current_events = (
        *current_events,
        append_session_event_v1_2(
            current_events,
            session_id=old_context.runtime_scope.session_id,
            run_id=old_context.runtime_scope.research_run_id,
            run_invocation_id=old_context.runtime_scope.run_invocation_id,
            action_attempt_id=old_context.runtime_scope.action_attempt_id,
            event_type="finding_opened",
            actor_id="runtime",
            occurred_at=NOW + timedelta(seconds=10),
            output_refs=("finding:current-ledger-advanced",),
        ),
    )
    current_snapshot = create_canonical_event_ledger_snapshot(
        ledger_snapshot_id="ledger-snapshot:current-after-finding",
        repository_ref="repository:canonical-session-events",
        session_id=old_context.runtime_scope.session_id,
        store_revision=old_snapshot.store_revision + 1,
        events=current_events,
        canonical_tip_digest=current_events[-1].event_digest,
    )
    current_authorization = _authority_record(
        old_context.runtime_scope,
        current_snapshot,
    )

    stale_body = old_context.grant_ledger_view.model_dump(
        mode="python",
        exclude={"ledger_view_digest"},
    )
    stale_body["canonical_event_ledger_snapshot_digest"] = (
        current_snapshot.ledger_snapshot_digest
    )
    stale_body["runtime_scope_authorization_record_digest"] = (
        current_authorization.authorization_record_digest
    )
    stale_view = DisclosureGrantLedgerView(
        **stale_body,
        ledger_view_digest=canonical_digest(stale_body),
    )
    stale_context = DisclosureRuntimeContext(
        runtime_scope=old_context.runtime_scope,
        scope_authorization_record=current_authorization,
        role=old_context.role,
        task_kind=old_context.task_kind,
        consumed_disclosure_tokens=old_context.consumed_disclosure_tokens,
        grants=old_context.grants,
        grant_ledger_view=stale_view,
    )
    current_reader = _StaticLedgerReader(current_snapshot)
    current_authority = _StaticAuthorityResolver(current_authorization)

    with pytest.raises(
        ValueError,
        match="runtime_context_disclosure_ledger_view_stale_or_self_signed",
    ):
        stale_context.validate_current_grant_view(
            ledger_reader=current_reader,
            authority_resolver=current_authority,
        )
    with pytest.raises(
        ValueError,
        match="runtime_context_disclosure_ledger_view_stale_or_self_signed",
    ):
        decide_disclosure(
            request=_request(
                catalog,
                policy,
                depth="resource_index",
                parent_receipt_digest=l1.receipt_digest,
            ),
            catalog=catalog,
            policy=policy,
            context=stale_context,
            ledger_reader=current_reader,
            catalog_resolver=_catalog_resolver(stale_context, catalog),
            authority_resolver=current_authority,
        )


@pytest.mark.fast_contract
@pytest.mark.parametrize(
    ("event_overrides", "error_code"),
    (
        (
            {"include_request": False},
            "disclosure_grant_missing_canonical_request_event",
        ),
        (
            {"request_after_grant": True},
            "disclosure_canonical_request_not_before_grant",
        ),
        (
            {"include_grant_request_binding": False},
            "disclosure_grant_request_binding_missing",
        ),
        (
            {"include_resource_binding": False},
            "disclosure_grant_resource_binding_missing",
        ),
    ),
)
def test_canonical_grant_requires_prior_request_and_exact_resource_bindings(
    event_overrides,
    error_code: str,
) -> None:
    catalog = _catalog()
    policy = _policy()
    initial = _context(catalog=catalog, policy=policy)
    receipt = _decide(
        request=_request(catalog, policy),
        catalog=catalog,
        policy=policy,
        context=initial,
    )
    scope = initial.runtime_scope
    events = _grant_ledger_events(
        scope=scope,
        receipt=receipt,
        **event_overrides,
    )
    snapshot = _ledger_snapshot(scope, events, suffix=error_code[-24:])
    authority_record = _authority_record(scope, snapshot)

    with pytest.raises(ValueError, match=error_code):
        build_disclosure_grant_ledger_view(
            ledger_view_id="ledger-view:invalid-grant-binding",
            runtime_scope=scope,
            ledger_reader=_StaticLedgerReader(snapshot),
            authority_resolver=_StaticAuthorityResolver(authority_record),
            verified_receipts=(receipt,),
        )


@pytest.mark.fast_contract
@pytest.mark.parametrize(
    ("event_overrides", "error_code"),
    (
        (
            {"scope_actor": "provider"},
            "disclosure_scope_authority_event_issuer_invalid",
        ),
        (
            {"request_actor": "provider"},
            "disclosure_request_event_issuer_invalid",
        ),
        (
            {"grant_actor": "provider"},
            "disclosure_grant_event_issuer_invalid",
        ),
    ),
)
def test_canonical_disclosure_events_reject_wrong_actor(
    event_overrides,
    error_code: str,
) -> None:
    catalog = _catalog()
    policy = _policy()
    initial = _context(catalog=catalog, policy=policy)
    receipt = _decide(
        request=_request(catalog, policy),
        catalog=catalog,
        policy=policy,
        context=initial,
    )
    scope = initial.runtime_scope
    events = _grant_ledger_events(
        scope=scope,
        receipt=receipt,
        **event_overrides,
    )
    snapshot = _ledger_snapshot(scope, events, suffix=error_code[-24:])
    authority_record = _authority_record(scope, snapshot)

    with pytest.raises(ValueError, match=error_code):
        build_disclosure_grant_ledger_view(
            ledger_view_id="ledger-view:wrong-actor",
            runtime_scope=scope,
            ledger_reader=_StaticLedgerReader(snapshot),
            authority_resolver=_StaticAuthorityResolver(authority_record),
            verified_receipts=(receipt,),
        )


@pytest.mark.fast_contract
def test_current_ledger_snapshot_and_scope_authority_are_exactly_bound() -> None:
    catalog = _catalog()
    policy = _policy()
    initial = _context(catalog=catalog, policy=policy)
    receipt = _decide(
        request=_request(catalog, policy),
        catalog=catalog,
        policy=policy,
        context=initial,
    )
    scope = initial.runtime_scope
    current_events = _grant_ledger_events(scope=scope, receipt=receipt)
    current_snapshot = _ledger_snapshot(
        scope,
        current_events,
        revision=2,
        suffix="current",
    )
    stale_snapshot = _ledger_snapshot(
        scope,
        current_events[:-1],
        revision=1,
        suffix="stale",
    )
    stale_authority = _authority_record(scope, stale_snapshot)
    with pytest.raises(
        ValueError,
        match="disclosure_canonical_ledger_snapshot_stale_or_unbound",
    ):
        build_disclosure_grant_ledger_view(
            ledger_view_id="ledger-view:stale-snapshot",
            runtime_scope=scope,
            ledger_reader=_StaticLedgerReader(current_snapshot),
            authority_resolver=_StaticAuthorityResolver(stale_authority),
            verified_receipts=(receipt,),
        )

    current_authority = _authority_record(scope, current_snapshot)
    missing_scope_events = _grant_ledger_events(
        scope=scope,
        receipt=receipt,
        include_scope_authority=False,
    )
    missing_scope_snapshot = _ledger_snapshot(
        scope,
        missing_scope_events,
        revision=3,
        suffix="scope-missing",
    )
    missing_scope_authority = _authority_record(scope, missing_scope_snapshot)
    with pytest.raises(ValueError, match="disclosure_scope_authority_event_missing"):
        build_disclosure_grant_ledger_view(
            ledger_view_id="ledger-view:scope-event-missing",
            runtime_scope=scope,
            ledger_reader=_StaticLedgerReader(missing_scope_snapshot),
            authority_resolver=_StaticAuthorityResolver(missing_scope_authority),
            verified_receipts=(receipt,),
        )

    mismatched_refs = list(_scope_authority_output_refs(scope))
    mismatched_refs[3] = f"task-assignment://sha256/{_digest('wrong-assignment')}"
    mismatched_events = _grant_ledger_events(
        scope=scope,
        receipt=receipt,
        scope_output_refs=tuple(mismatched_refs),
    )
    mismatched_snapshot = _ledger_snapshot(
        scope,
        mismatched_events,
        revision=4,
        suffix="scope-mismatch",
    )
    mismatched_authority = _authority_record(scope, mismatched_snapshot)
    with pytest.raises(ValueError, match="disclosure_scope_authority_binding_mismatch"):
        build_disclosure_grant_ledger_view(
            ledger_view_id="ledger-view:scope-binding-mismatch",
            runtime_scope=scope,
            ledger_reader=_StaticLedgerReader(mismatched_snapshot),
            authority_resolver=_StaticAuthorityResolver(mismatched_authority),
            verified_receipts=(receipt,),
        )

    assert current_authority.canonical_event_ledger_snapshot_digest == (
        current_snapshot.ledger_snapshot_digest
    )


@pytest.mark.fast_contract
def test_missing_host_ledger_or_authority_resolver_fails_closed() -> None:
    catalog = _catalog()
    policy = _policy()
    initial = _context(catalog=catalog, policy=policy)
    receipt = _decide(
        request=_request(catalog, policy),
        catalog=catalog,
        policy=policy,
        context=initial,
    )
    scope = initial.runtime_scope
    events = _grant_ledger_events(scope=scope, receipt=receipt)
    snapshot = _ledger_snapshot(scope, events, suffix="resolver-required")
    authority_record = _authority_record(scope, snapshot)

    with pytest.raises(ValueError, match="runtime_scope_authority_resolver_required"):
        build_disclosure_grant_ledger_view(
            ledger_view_id="ledger-view:no-authority-resolver",
            runtime_scope=scope,
            ledger_reader=_StaticLedgerReader(snapshot),
            authority_resolver=None,
            verified_receipts=(receipt,),
        )
    with pytest.raises(ValueError, match="runtime_scope_absent_from_authoritative_store"):
        build_disclosure_grant_ledger_view(
            ledger_view_id="ledger-view:null-authority-resolution",
            runtime_scope=scope,
            ledger_reader=_StaticLedgerReader(snapshot),
            authority_resolver=_NullAuthorityResolver(),
            verified_receipts=(receipt,),
        )
    with pytest.raises(ValueError, match="canonical_event_ledger_reader_required"):
        build_disclosure_grant_ledger_view(
            ledger_view_id="ledger-view:no-ledger-reader",
            runtime_scope=scope,
            ledger_reader=None,
            authority_resolver=_StaticAuthorityResolver(authority_record),
            verified_receipts=(receipt,),
        )
    with pytest.raises(ValueError, match="canonical_event_ledger_snapshot_missing"):
        build_disclosure_grant_ledger_view(
            ledger_view_id="ledger-view:null-ledger-snapshot",
            runtime_scope=scope,
            ledger_reader=_NullLedgerReader(),
            authority_resolver=_StaticAuthorityResolver(authority_record),
            verified_receipts=(receipt,),
        )


@pytest.mark.fast_contract
def test_context_role_and_task_are_derived_from_sealed_scope() -> None:
    catalog = _catalog()
    policy = _policy()
    scope = _runtime_scope(catalog, policy, role="writer")
    events = (
        append_session_event_v1_2(
            (),
            session_id=scope.session_id,
            event_type="session_created",
            actor_id="runtime",
            occurred_at=NOW,
        ),
    )
    events = (
        *events,
        append_session_event_v1_2(
            events,
            session_id=scope.session_id,
            run_id=scope.research_run_id,
            run_invocation_id=scope.run_invocation_id,
            action_attempt_id=scope.action_attempt_id,
            event_type="action_intent_committed",
            actor_id="runtime",
            occurred_at=NOW + timedelta(seconds=1),
            output_refs=_scope_authority_output_refs(scope),
        ),
    )
    snapshot = create_canonical_event_ledger_snapshot(
        ledger_snapshot_id="ledger-snapshot:writer",
        repository_ref="repository:canonical-session-events",
        session_id=scope.session_id,
        store_revision=1,
        events=events,
        canonical_tip_digest=events[-1].event_digest,
    )
    authority_record = _authority_record(scope, snapshot)
    ledger = build_disclosure_grant_ledger_view(
        ledger_view_id="ledger-view:writer",
        runtime_scope=scope,
        ledger_reader=_StaticLedgerReader(snapshot),
        authority_resolver=_StaticAuthorityResolver(authority_record),
        verified_receipts=(),
    )
    with pytest.raises(ValidationError, match="role_or_task_not_scope_bound"):
        DisclosureRuntimeContext(
            runtime_scope=scope,
            scope_authorization_record=authority_record,
            role="evidence_specialist",
            task_kind=scope.task_kind,
            consumed_disclosure_tokens=0,
            grants=(),
            grant_ledger_view=ledger,
        )
