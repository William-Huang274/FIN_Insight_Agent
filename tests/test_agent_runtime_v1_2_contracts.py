from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import shutil

import pytest
from pydantic import ValidationError

from sec_agent.canonical_runtime import contracts_v1_2 as canonical_contracts
from sec_agent.canonical_runtime.contracts_v1_2 import (
    LEGACY_A01_PAID_FULL_CHAIN_EXECUTION_ID,
    LEGACY_A01_RUN_ID,
    LEGACY_A02_CANONICAL_SESSION_ID,
    LEGACY_A02_INITIAL_INVOCATION_ID,
    LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID,
    LEGACY_A02_PLANNER_ACTION_ATTEMPT_ID,
    LEGACY_A02_RUN_ID,
    LEGACY_A02_SOURCE_BUNDLE_REF,
    ActionAttempt,
    CanonicalV1_2Error,
    CurrentContextMaterialSnapshotV1_2,
    LegacyA02IdentityMapping,
    RunEventAclSnapshot,
    RunEventAuthorizationView,
    adapt_legacy_agent_session_v1_0,
    adapt_legacy_v1_1_event_log,
    append_session_event_v1_2,
    canonical_json_sha256,
    create_action_attempt,
    create_agent_session_v1_2,
    create_artifact_acl_grant,
    create_canonical_event_ledger_snapshot,
    create_context_checkpoint_v1_2,
    create_current_context_material_snapshot_v1_2,
    create_recovery_disposition,
    create_required_material_ref_sources,
    create_research_run,
    create_run_invocation,
    derive_required_material_ref_sources_v1_2,
    load_legacy_a02_source_bundle,
    load_runtime_contract_v1_2,
    map_legacy_a02_identity,
    project_run_events,
    resolve_run_event_authorization_view,
    validate_context_checkpoint_v1_2,
    validate_recovery_disposition_v1_2,
    validate_run_event_authorization_view,
    validate_run_event_projection,
    validate_session_event_sequence,
)
from sec_agent.canonical_runtime.session import (
    append_session_event,
    canonical_digest as legacy_canonical_digest,
    create_agent_session,
)


NOW = datetime(2026, 9, 3, 1, 2, 3, tzinfo=timezone.utc)


def _digest(value: str) -> str:
    return canonical_json_sha256({"value": value})


class _HostRunEventAclResolver:
    """Test host boundary: principal and ACL state are not request fields."""

    def __init__(
        self,
        *,
        principal_ref: str,
        session_id: str,
        run_id: str,
        projection_policy_digest: str,
        grants: tuple,
        store_revision: int = 1,
    ) -> None:
        self.principal_ref = principal_ref
        self.session_id = session_id
        self.run_id = run_id
        self.projection_policy_digest = projection_policy_digest
        self.grants = grants
        self.store_revision = store_revision

    def resolve_current_snapshot(
        self,
        *,
        session_id: str,
        run_id: str,
    ) -> RunEventAclSnapshot:
        if (
            session_id != self.session_id
            or run_id != self.run_id
        ):
            raise CanonicalV1_2Error("test_host_acl_snapshot_not_found")
        body = {
            "schema_version": "fin_ia_run_event_acl_snapshot_v1_2",
            "acl_snapshot_id": "ACL-SNAPSHOT::DELL::CURRENT",
            "resolver_ref": "resolver://host/test/current-request",
            "store_revision": self.store_revision,
            "principal_ref": self.principal_ref,
            "session_id": self.session_id,
            "run_id": self.run_id,
            "projection_policy_digest": self.projection_policy_digest,
            "grants": tuple(sorted(self.grants, key=lambda grant: grant.ref_id)),
            "issued_by": "host_acl_resolver",
        }
        return RunEventAclSnapshot(
            **body,
            acl_snapshot_digest=canonical_json_sha256(body),
        )


class _StaticRunEventAclResolver:
    def __init__(self, snapshot: RunEventAclSnapshot) -> None:
        self.snapshot = snapshot

    def resolve_current_snapshot(
        self,
        *,
        session_id: str,
        run_id: str,
    ) -> RunEventAclSnapshot:
        return self.snapshot


class _HostCurrentContextMaterialResolver:
    """Test composition root for the host-owned checkpoint material port."""

    def __init__(
        self,
        *,
        session_id: str,
        run_id: str,
        accepted_plan_ref: str,
        accepted_plan_digest: str,
        events: tuple,
        research_graph_digest: str,
        open_finding_refs: tuple[str, ...],
        coverage_state_refs: tuple[str, ...] = ("coverage://Q1",),
        minimum_route_obligation_refs: tuple[str, ...] = ("minimum-route://Q1",),
        accepted_evidence_refs: tuple[str, ...] = (),
        numeric_fact_refs: tuple[str, ...] = (),
        claim_ledger_refs: tuple[str, ...] = ("claim-ledger://branch/1",),
        calculation_receipt_refs: tuple[str, ...] = (),
        disclosure_receipt_refs: tuple[str, ...] = ("disclosure://1",),
        skill_consumption_receipt_refs: tuple[str, ...] = (),
        open_gap_refs: tuple[str, ...] = (),
        unresolved_feedback_refs: tuple[str, ...] = (),
        counterevidence_refs: tuple[str, ...] = (),
        open_question_refs: tuple[str, ...] = (),
        pending_intervention_refs: tuple[str, ...] = (),
        authority_refs: tuple[str, ...] = ("authority://zero-model",),
        active_stop_decision_ref: str = "stop://continue/1",
        budget_state_ref: str = "budget://run/1",
        context_projection_ref: str = "context-projection://1",
        langgraph_checkpoint_ref: str = "langgraph://thread/checkpoint/1",
        store_revision: int = 1,
        notebook_revision: int = 1,
    ) -> None:
        self.session_id = session_id
        self.run_id = run_id
        self.accepted_plan_ref = accepted_plan_ref
        self.accepted_plan_digest = accepted_plan_digest
        self.events = events
        self.research_graph_digest = research_graph_digest
        self.open_finding_refs = open_finding_refs
        self.coverage_state_refs = coverage_state_refs
        self.minimum_route_obligation_refs = minimum_route_obligation_refs
        self.accepted_evidence_refs = accepted_evidence_refs
        self.numeric_fact_refs = numeric_fact_refs
        self.claim_ledger_refs = claim_ledger_refs
        self.calculation_receipt_refs = calculation_receipt_refs
        self.disclosure_receipt_refs = disclosure_receipt_refs
        self.skill_consumption_receipt_refs = skill_consumption_receipt_refs
        self.open_gap_refs = open_gap_refs
        self.unresolved_feedback_refs = unresolved_feedback_refs
        self.counterevidence_refs = counterevidence_refs
        self.open_question_refs = open_question_refs
        self.pending_intervention_refs = pending_intervention_refs
        self.authority_refs = authority_refs
        self.active_stop_decision_ref = active_stop_decision_ref
        self.budget_state_ref = budget_state_ref
        self.context_projection_ref = context_projection_ref
        self.langgraph_checkpoint_ref = langgraph_checkpoint_ref
        self.store_revision = store_revision
        self.notebook_revision = notebook_revision

    def resolve_current_snapshot(
        self,
        *,
        session_id: str,
        run_id: str,
    ) -> CurrentContextMaterialSnapshotV1_2:
        if session_id != self.session_id or run_id != self.run_id:
            raise CanonicalV1_2Error("test_current_context_material_not_found")
        ledger = create_canonical_event_ledger_snapshot(
            ledger_snapshot_id=f"LEDGER-SNAPSHOT::{self.store_revision}",
            repository_ref="repository://canonical-events/test",
            session_id=self.session_id,
            store_revision=self.store_revision,
            events=self.events,
            canonical_tip_digest=self.events[-1].event_digest,
        )
        return create_current_context_material_snapshot_v1_2(
            material_snapshot_id=f"MATERIAL-SNAPSHOT::{self.store_revision}",
            resolver_ref="resolver://host/current-context/test",
            store_revision=self.store_revision,
            session_id=self.session_id,
            run_id=self.run_id,
            accepted_plan_ref=self.accepted_plan_ref,
            accepted_plan_digest=self.accepted_plan_digest,
            research_graph_digest=self.research_graph_digest,
            canonical_event_ledger=ledger,
            notebook_revision=self.notebook_revision,
            open_finding_refs=self.open_finding_refs,
            coverage_state_refs=self.coverage_state_refs,
            minimum_route_obligation_refs=self.minimum_route_obligation_refs,
            accepted_evidence_refs=self.accepted_evidence_refs,
            numeric_fact_refs=self.numeric_fact_refs,
            claim_ledger_refs=self.claim_ledger_refs,
            calculation_receipt_refs=self.calculation_receipt_refs,
            disclosure_receipt_refs=self.disclosure_receipt_refs,
            skill_consumption_receipt_refs=self.skill_consumption_receipt_refs,
            open_gap_refs=self.open_gap_refs,
            unresolved_feedback_refs=self.unresolved_feedback_refs,
            counterevidence_refs=self.counterevidence_refs,
            open_question_refs=self.open_question_refs,
            pending_intervention_refs=self.pending_intervention_refs,
            authority_refs=self.authority_refs,
            active_stop_decision_ref=self.active_stop_decision_ref,
            budget_state_ref=self.budget_state_ref,
            context_projection_ref=self.context_projection_ref,
            langgraph_checkpoint_ref=self.langgraph_checkpoint_ref,
        )


def _self_signed_authorization_view(
    *,
    authorization_view_id: str,
    acl_snapshot_digest: str,
    principal_ref: str,
    session_id: str,
    run_id: str,
    projection_policy_digest: str,
    visible_ref_ids: tuple[str, ...],
) -> RunEventAuthorizationView:
    body = {
        "schema_version": "fin_ia_run_event_authorization_view_v1_2",
        "authorization_view_id": authorization_view_id,
        "principal_ref": principal_ref,
        "session_id": session_id,
        "run_id": run_id,
        "projection_policy_digest": projection_policy_digest,
        "acl_snapshot_digest": acl_snapshot_digest,
        "authorization_basis_refs": ("acl://caller/self-signed",),
        "visible_ref_ids": visible_ref_ids,
    }
    return RunEventAuthorizationView(
        **body,
        authorization_view_digest=canonical_json_sha256(body),
    )


def _session(**overrides):
    fields = {
        "session_id": "SESSION::DELL::001",
        "thread_id": "THREAD::DELL::001",
        "case_id": "DELL_AI_INFRA_REFERENCE_VERTICAL",
        "case_version": "FIN_0_1_3",
        "as_of_date": date(2026, 9, 3),
        "objective_ref": "objective://dell/complete-vertical",
        "objective_digest": _digest("objective"),
        "data_snapshot_ref": "snapshot://dell/frozen-inputs",
        "data_snapshot_digest": _digest("snapshot"),
        "runtime_policy_ref": "policy://dell/runtime/v1",
        "runtime_policy_digest": _digest("policy"),
        "authority_refs": ("authority://zero-model",),
        "active_plan_ref": "plan://dell/revision/1",
        "active_plan_digest": _digest("plan-1"),
        "status": "ACTIVE",
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return create_agent_session_v1_2(**fields)


def _run(session=None, **overrides):
    session = session or _session()
    fields = {
        "run_id": "RUN::DELL::001",
        "session_id": session.session_id,
        "parent_run_id": None,
        "origin_kind": "INITIAL",
        "legacy_paid_full_chain_execution_label": None,
        "status": "RUNNING",
        "base_plan_ref": session.active_plan_ref,
        "base_plan_digest": session.active_plan_digest,
        "current_plan_ref": session.active_plan_ref,
        "current_plan_digest": session.active_plan_digest,
        "last_session_sequence": 0,
        "created_at": NOW,
        "terminal_at": None,
    }
    fields.update(overrides)
    return create_research_run(**fields)


def _invocation(session=None, run=None, **overrides):
    session = session or _session()
    run = run or _run(session)
    fields = {
        "invocation_id": "INVOCATION::DELL::001",
        "session_id": session.session_id,
        "run_id": run.run_id,
        "ordinal": 1,
        "invocation_kind": "START",
        "status": "RUNNING",
        "trigger_ref": "command://start/1",
        "lease_ref": "lease://worker/1",
        "started_at": NOW,
        "finished_at": None,
    }
    fields.update(overrides)
    return create_run_invocation(**fields)


def _applied_action(session=None, run=None, invocation=None, **overrides):
    session = session or _session()
    run = run or _run(session)
    invocation = invocation or _invocation(session, run)
    fields = {
        "action_attempt_id": "ACTION::DELL::001",
        "session_id": session.session_id,
        "run_id": run.run_id,
        "run_invocation_id": invocation.invocation_id,
        "actor_id": "agent://specialist/demand",
        "action_kind": "TOOL",
        "action_name": "request_local_evidence",
        "request_ref": "request://tool/1",
        "request_digest": _digest("request"),
        "state": "TERMINAL",
        "outcome": "APPLIED",
        "was_dispatched": True,
        "potentially_chargeable": False,
        "receipt_kind": "SUCCESS",
        "receipt_ref": "receipt://tool/1",
        "receipt_digest": _digest("receipt"),
        "failure_code": None,
        "parent_action_attempt_id": None,
        "created_at": NOW,
        "terminal_at": NOW + timedelta(seconds=1),
    }
    fields.update(overrides)
    return create_action_attempt(**fields)


def test_v1_2_contract_binds_immutable_predecessors_and_forbids_a03() -> None:
    contract = load_runtime_contract_v1_2()

    assert contract["identity"]["legacy_A02_mapping"]["research_runs"] == 1
    assert contract["identity"]["legacy_A02_mapping"]["run_id"] == LEGACY_A02_RUN_ID
    assert (
        contract["identity"]["legacy_A02_mapping"]["source_bundle_digest"]
        == load_legacy_a02_source_bundle().source_bundle_digest
    )
    assert contract["identity"]["forbidden_legacy_labels"] == ["A03"]
    assert contract["authority"]["A03_exists"] is False
    assert contract["authority"]["A03_placeholder_allowed"] is False
    assert [item["schema_version"] for item in contract["immutable_predecessors"]] == [
        "fin_ia_agent_runtime_reflection_context_continuity_contract_v1_0",
        "fin_ia_agent_runtime_reflection_context_continuity_contract_v1_1",
    ]


@pytest.mark.parametrize(
    ("path", "invalid_value"),
    [
        (("identity", "legacy_A02_mapping", "research_run_status"), "COMPLETED"),
        (("identity", "legacy_A02_mapping", "source_bundle_digest"), _digest("forged")),
        (
            (
                "authorization_projection",
                "caller_authored_visible_ref_list_authoritative",
            ),
            True,
        ),
        (("implementation_boundary", "model_calls"), True),
        (("zero_model_transport", "provider_client_surface_exposed"), True),
        (("immutable_A02_offline_replay", "provider_calls"), 1),
        (("identity", "phantom_identity_policy"), "A03_placeholder_allowed"),
        (("action_attempt", "rules"), ["old_attempt_may_be_retried"]),
        (("session_event_envelope", "digest_chain"), False),
        (
            ("context_checkpoint", "required_material_refs_rule"),
            "caller_supplied",
        ),
        (("unexpected_paid_authority",), True),
    ],
)
def test_runtime_contract_loader_rejects_critical_boundary_drift(
    tmp_path: Path,
    path: tuple[str, ...],
    invalid_value: object,
) -> None:
    repo_root = Path(__file__).parents[1]
    config_dir = tmp_path / "configs" / "research"
    config_dir.mkdir(parents=True)
    for filename in (
        "fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_0.json",
        "fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_1.json",
        "fin_ia_0_1_3_agent_runtime_reflection_context_continuity_contract_v1_2.json",
    ):
        shutil.copy2(repo_root / "configs" / "research" / filename, config_dir / filename)

    contract_path = config_dir / Path(canonical_contracts.CONTRACT_V1_2_REF).name
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    target = contract
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = invalid_value
    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(CanonicalV1_2Error, match="runtime_contract_"):
        load_runtime_contract_v1_2(tmp_path)


def test_identity_models_are_strict_frozen_and_digest_bound() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)
    action = _applied_action(session, run, invocation)

    assert session.thread_id != run.run_id
    assert run.session_id == session.session_id
    assert invocation.run_id == run.run_id
    assert action.run_invocation_id == invocation.invocation_id
    assert len({session.session_digest, run.run_digest, invocation.invocation_digest,
                action.action_attempt_digest}) == 4

    with pytest.raises(ValidationError, match="frozen"):
        action.outcome = "FAILED_BEFORE_DISPATCH"  # type: ignore[misc]

    tampered = action.model_dump()
    tampered["action_name"] = "changed_after_digest"
    with pytest.raises(ValidationError, match="action_attempt_digest_invalid"):
        ActionAttempt.model_validate(tampered)

    with pytest.raises(ValidationError):
        create_run_invocation(
            **{
                **invocation.model_dump(exclude={"schema_version", "invocation_digest"}),
                "ordinal": "1",
            }
        )


def test_action_attempt_outcome_and_recovery_are_fail_closed() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)

    with pytest.raises(ValidationError, match="action_attempt_applied_receipt_missing"):
        _applied_action(
            session, run, invocation,
            receipt_kind=None, receipt_ref=None, receipt_digest=None,
        )

    ambiguous = create_action_attempt(
        action_attempt_id="ACTION::DELL::AMBIGUOUS",
        session_id=session.session_id,
        run_id=run.run_id,
        run_invocation_id=invocation.invocation_id,
        actor_id="agent://lead",
        action_kind="MODEL",
        action_name="lead_reflect",
        request_ref="request://model/ambiguous",
        request_digest=_digest("ambiguous-request"),
        state="TERMINAL",
        outcome="AMBIGUOUS_AFTER_DISPATCH",
        was_dispatched=True,
        potentially_chargeable=True,
        receipt_kind=None,
        receipt_ref=None,
        receipt_digest=None,
        failure_code=None,
        parent_action_attempt_id=None,
        created_at=NOW,
        terminal_at=NOW + timedelta(seconds=2),
    )
    recovery_run = _run(session, status="RECOVERY_REQUIRED")
    next_invocation = create_run_invocation(
        invocation_id="INVOCATION::DELL::002",
        session_id=session.session_id,
        run_id=run.run_id,
        ordinal=2,
        invocation_kind="RECOVERY",
        status="SCHEDULED",
        trigger_ref="RECOVERY::DELL::001",
        lease_ref=None,
        started_at=NOW + timedelta(minutes=2),
        finished_at=None,
    )
    replacement = create_action_attempt(
        action_attempt_id="ACTION::DELL::RETRY::002",
        session_id=session.session_id,
        run_id=run.run_id,
        run_invocation_id=next_invocation.invocation_id,
        actor_id="agent://lead",
        action_kind="MODEL",
        action_name="lead_reflect",
        request_ref="request://model/recovery",
        request_digest=_digest("recovery-request"),
        state="INTENT_COMMITTED",
        outcome=None,
        was_dispatched=False,
        potentially_chargeable=False,
        receipt_kind=None,
        receipt_ref=None,
        receipt_digest=None,
        failure_code=None,
        parent_action_attempt_id=ambiguous.action_attempt_id,
        created_at=NOW + timedelta(minutes=2),
        terminal_at=None,
    )
    recovery = create_recovery_disposition(
        recovery_disposition_id="RECOVERY::DELL::001",
        session_id=session.session_id,
        run_id=run.run_id,
        research_run_digest=recovery_run.run_digest,
        ambiguous_action_attempt_id=ambiguous.action_attempt_id,
        ambiguous_action_attempt_digest=ambiguous.action_attempt_digest,
        source_run_invocation_id=invocation.invocation_id,
        source_run_invocation_digest=invocation.invocation_digest,
        investigation_receipt_refs=("receipt://reconciliation/1",),
        potentially_duplicate_cost=True,
        decision="RETRY_AS_NEW_ACTION",
        decision_authority_ref="authority://human/recovery",
        next_run_invocation_id=next_invocation.invocation_id,
        next_run_invocation_digest=next_invocation.invocation_digest,
        replacement_action_attempt_id=replacement.action_attempt_id,
        replacement_action_attempt_digest=replacement.action_attempt_digest,
        created_at=NOW + timedelta(minutes=1),
    )

    assert recovery.ambiguous_action_attempt_id == ambiguous.action_attempt_id
    assert recovery.replacement_action_attempt_id != ambiguous.action_attempt_id
    validate_recovery_disposition_v1_2(
        recovery,
        ambiguous_action=ambiguous,
        run=recovery_run,
        source_invocation=invocation,
        next_invocation=next_invocation,
        replacement_action=replacement,
    )
    forged_recovery_body = recovery.model_dump(
        mode="json",
        exclude={"recovery_disposition_digest"},
    )
    forged_recovery_body["decision"] = "RESUME_WITHOUT_RETRY"
    forged_recovery = recovery.model_copy(
        update={
            "decision": "RESUME_WITHOUT_RETRY",
            "recovery_disposition_digest": canonical_json_sha256(
                forged_recovery_body
            ),
        }
    )
    with pytest.raises(CanonicalV1_2Error, match="recovery_disposition_invalid"):
        validate_recovery_disposition_v1_2(
            forged_recovery,
            ambiguous_action=ambiguous,
            run=recovery_run,
            source_invocation=invocation,
            next_invocation=next_invocation,
            replacement_action=replacement,
        )
    changed_recovery_run = _run(
        session,
        status="RECOVERY_REQUIRED",
        current_plan_ref="plan://dell/revision/2",
        current_plan_digest=_digest("plan-2"),
    )
    with pytest.raises(CanonicalV1_2Error, match="recovery_research_run_state_invalid"):
        validate_recovery_disposition_v1_2(
            recovery,
            ambiguous_action=ambiguous,
            run=changed_recovery_run,
            source_invocation=invocation,
            next_invocation=next_invocation,
            replacement_action=replacement,
        )
    retroactive_recovery = create_recovery_disposition(
        **{
            **recovery.model_dump(exclude={
                "schema_version",
                "recovery_disposition_digest",
                "created_at",
            }),
            "created_at": NOW + timedelta(seconds=1),
        }
    )
    with pytest.raises(CanonicalV1_2Error, match="recovery_disposition_time_invalid"):
        validate_recovery_disposition_v1_2(
            retroactive_recovery,
            ambiguous_action=ambiguous,
            run=recovery_run,
            source_invocation=invocation,
            next_invocation=next_invocation,
            replacement_action=replacement,
        )
    same_id_recovery_invocation = create_run_invocation(
        invocation_id=invocation.invocation_id,
        session_id=session.session_id,
        run_id=run.run_id,
        ordinal=2,
        invocation_kind="RECOVERY",
        status="SCHEDULED",
        trigger_ref="RECOVERY::DELL::SAME-ID",
        lease_ref=None,
        started_at=NOW + timedelta(minutes=2),
        finished_at=None,
    )
    same_id_recovery = create_recovery_disposition(
        recovery_disposition_id="RECOVERY::DELL::SAME-ID",
        session_id=session.session_id,
        run_id=run.run_id,
        research_run_digest=recovery_run.run_digest,
        ambiguous_action_attempt_id=ambiguous.action_attempt_id,
        ambiguous_action_attempt_digest=ambiguous.action_attempt_digest,
        source_run_invocation_id=invocation.invocation_id,
        source_run_invocation_digest=invocation.invocation_digest,
        investigation_receipt_refs=("receipt://reconciliation/same-id",),
        potentially_duplicate_cost=True,
        decision="RESUME_WITHOUT_RETRY",
        decision_authority_ref="authority://human/recovery",
        next_run_invocation_id=same_id_recovery_invocation.invocation_id,
        next_run_invocation_digest=same_id_recovery_invocation.invocation_digest,
        replacement_action_attempt_id=None,
        replacement_action_attempt_digest=None,
        created_at=NOW + timedelta(minutes=1),
    )
    with pytest.raises(CanonicalV1_2Error, match="recovery_next_invocation_invalid"):
        validate_recovery_disposition_v1_2(
            same_id_recovery,
            ambiguous_action=ambiguous,
            run=recovery_run,
            source_invocation=invocation,
            next_invocation=same_id_recovery_invocation,
            replacement_action=None,
        )
    with pytest.raises(ValidationError, match="recovery_disposition_new_invocation_mismatch"):
        create_recovery_disposition(
            **{
                **recovery.model_dump(exclude={"schema_version", "recovery_disposition_digest"}),
                "next_run_invocation_id": None,
                "next_run_invocation_digest": None,
            }
        )

    with pytest.raises(ValidationError, match="progress_state_has_terminal_fields"):
        create_action_attempt(
            **{
                **ambiguous.model_dump(exclude={"schema_version", "action_attempt_digest"}),
                "state": "DISPATCHED",
                "outcome": "AMBIGUOUS_AFTER_DISPATCH",
                "terminal_at": None,
            }
        )
    with pytest.raises(ValidationError, match="applied_without_dispatch"):
        _applied_action(session, run, invocation, was_dispatched=False)
    with pytest.raises(ValidationError, match="intent_has_receipt_or_chargeability"):
        _applied_action(
            session,
            run,
            invocation,
            state="INTENT_COMMITTED",
            outcome=None,
            was_dispatched=False,
            potentially_chargeable=False,
            terminal_at=None,
        )
    with pytest.raises(ValidationError, match="dispatched_has_receipt"):
        _applied_action(
            session,
            run,
            invocation,
            state="DISPATCHED",
            outcome=None,
            terminal_at=None,
        )
    with pytest.raises(ValidationError, match="before_dispatch_has_receipt_or_chargeability"):
        _applied_action(
            session,
            run,
            invocation,
            outcome="FAILED_BEFORE_DISPATCH",
            was_dispatched=False,
            potentially_chargeable=True,
            receipt_kind="FAILURE",
            failure_code="local-validation-failed",
        )
    with pytest.raises(CanonicalV1_2Error, match="source_action_not_ambiguous"):
        validate_recovery_disposition_v1_2(
            recovery,
            ambiguous_action=_applied_action(session, run, invocation),
            run=recovery_run,
            source_invocation=invocation,
            next_invocation=next_invocation,
            replacement_action=replacement,
        )


def _interleaved_events(session, run, invocation):
    other_run = _run(session, run_id="RUN::DELL::FOLLOWUP")
    events = []
    events.append(append_session_event_v1_2(
        events, session_id=session.session_id, event_type="session_created",
        actor_id="runtime", occurred_at=NOW,
    ))
    events.append(append_session_event_v1_2(
        events, session_id=session.session_id, run_id=run.run_id,
        event_type="run_created", actor_id="runtime", occurred_at=NOW + timedelta(seconds=1),
        input_refs=("ref://public/input", "ref://restricted/input"),
        output_refs=("ref://public/output", "ref://restricted/output"),
        feedback_refs=("ref://public/feedback", "ref://restricted/feedback"),
    ))
    events.append(append_session_event_v1_2(
        events, session_id=session.session_id, run_id=other_run.run_id,
        event_type="run_created", actor_id="runtime", occurred_at=NOW + timedelta(seconds=2),
    ))
    events.append(append_session_event_v1_2(
        events, session_id=session.session_id, run_id=run.run_id,
        run_invocation_id=invocation.invocation_id,
        event_type="run_invocation_started", actor_id="runtime",
        occurred_at=NOW + timedelta(seconds=3),
    ))
    return tuple(events)


def test_session_sequence_is_truth_and_run_projection_is_rebuildable() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)
    events = _interleaved_events(session, run, invocation)

    validate_session_event_sequence(events, expected_session_id=session.session_id)
    assert [event.session_sequence for event in events] == [1, 2, 3, 4]

    policy = _digest("projection-policy")
    public_refs = (
        "ref://public/input",
        "ref://public/output",
        "ref://public/feedback",
    )
    grants = tuple(
        create_artifact_acl_grant(
            ref_id=ref,
            allowed_principal_refs=("principal://reviewer/1",),
            authorization_basis_refs=(
                "acl://dell/reviewer/2",
                "acl://dell/reviewer/1",
            ),
        )
        for ref in public_refs
    ) + (
        create_artifact_acl_grant(
            ref_id="ref://restricted/input",
            allowed_principal_refs=("principal://operator/1",),
            authorization_basis_refs=("acl://dell/operator/1",),
        ),
    )
    assert "RunEventAclResolver" in canonical_contracts.__all__
    assert "resolve_run_event_authorization_view" in canonical_contracts.__all__
    assert "validate_run_event_authorization_view" in canonical_contracts.__all__
    assert "create_run_event_acl_snapshot" not in canonical_contracts.__all__
    assert "create_run_event_authorization_view" not in canonical_contracts.__all__
    assert not hasattr(canonical_contracts, "create_run_event_acl_snapshot")
    assert not hasattr(canonical_contracts, "create_run_event_authorization_view")

    resolver = _HostRunEventAclResolver(
        principal_ref="principal://reviewer/1",
        session_id=session.session_id,
        run_id=run.run_id,
        projection_policy_digest=policy,
        grants=grants,
    )
    auth = resolve_run_event_authorization_view(
        authorization_view_id="AUTH-VIEW::DELL::001",
        session_id=session.session_id,
        run_id=run.run_id,
        projection_policy_digest=policy,
        acl_resolver=resolver,
        requested_ref_ids=public_refs,
    )
    assert auth.principal_ref == "principal://reviewer/1"
    assert auth.authorization_basis_refs == (
        "acl://dell/reviewer/1",
        "acl://dell/reviewer/2",
    )

    reordered_resolver = _HostRunEventAclResolver(
        principal_ref="principal://reviewer/1",
        session_id=session.session_id,
        run_id=run.run_id,
        projection_policy_digest=policy,
        grants=tuple(reversed(grants)),
    )
    reordered_auth = resolve_run_event_authorization_view(
        authorization_view_id="AUTH-VIEW::DELL::001",
        session_id=session.session_id,
        run_id=run.run_id,
        projection_policy_digest=policy,
        acl_resolver=reordered_resolver,
        requested_ref_ids=(
            "ref://public/feedback",
            "ref://public/output",
            "ref://public/input",
        ),
    )
    assert reordered_auth == auth
    with pytest.raises(CanonicalV1_2Error, match="run_event_acl_ref_not_authorized"):
        resolve_run_event_authorization_view(
            authorization_view_id="AUTH-VIEW::DELL::FORGED",
            session_id=session.session_id,
            run_id=run.run_id,
            projection_policy_digest=policy,
            acl_resolver=resolver,
            requested_ref_ids=("ref://restricted/input",),
        )
    with pytest.raises(CanonicalV1_2Error, match="run_event_acl_snapshot_boundary_mismatch"):
        resolve_run_event_authorization_view(
            authorization_view_id="AUTH-VIEW::DELL::STALE-POLICY",
            session_id=session.session_id,
            run_id=run.run_id,
            projection_policy_digest=_digest("stale-projection-policy"),
            acl_resolver=resolver,
            requested_ref_ids=public_refs,
        )

    current_snapshot = resolver.resolve_current_snapshot(
        session_id=session.session_id,
        run_id=run.run_id,
    )
    forged_snapshot_body = current_snapshot.model_dump(
        mode="json",
        exclude={"acl_snapshot_digest"},
    )
    forged_snapshot_body["issued_by"] = "caller_supplied_snapshot"
    forged_snapshot = current_snapshot.model_copy(
        update={
            "issued_by": "caller_supplied_snapshot",
            "acl_snapshot_digest": canonical_json_sha256(forged_snapshot_body),
        }
    )
    with pytest.raises(
        CanonicalV1_2Error,
        match="run_event_acl_resolver_snapshot_invalid",
    ):
        resolve_run_event_authorization_view(
            authorization_view_id="AUTH-VIEW::DELL::FORGED-HOST-SNAPSHOT",
            session_id=session.session_id,
            run_id=run.run_id,
            projection_policy_digest=policy,
            acl_resolver=_StaticRunEventAclResolver(forged_snapshot),
            requested_ref_ids=public_refs,
        )
    with pytest.raises(TypeError):
        resolve_run_event_authorization_view(
            authorization_view_id="AUTH-VIEW::DELL::CALLER-SNAPSHOT",
            session_id=session.session_id,
            run_id=run.run_id,
            projection_policy_digest=policy,
            acl_resolver=resolver,
            requested_ref_ids=public_refs,
            acl_snapshot=current_snapshot,
        )

    copied_snapshot_forgery = _self_signed_authorization_view(
        authorization_view_id="AUTH-VIEW::DELL::COPIED-SNAPSHOT-FORGERY",
        acl_snapshot_digest=current_snapshot.acl_snapshot_digest,
        principal_ref="principal://reviewer/1",
        session_id=session.session_id,
        run_id=run.run_id,
        projection_policy_digest=policy,
        visible_ref_ids=("ref://restricted/input",),
    )
    with pytest.raises(CanonicalV1_2Error, match="run_event_acl_ref_not_authorized"):
        project_run_events(
            events,
            run_id=run.run_id,
            projection_policy_digest=policy,
            authorization_view=copied_snapshot_forgery,
            acl_resolver=resolver,
        )

    caller_grant = create_artifact_acl_grant(
        ref_id="ref://restricted/input",
        allowed_principal_refs=("principal://reviewer/1",),
        authorization_basis_refs=("acl://caller/self-signed",),
    )
    caller_snapshot_body = {
        "schema_version": "fin_ia_run_event_acl_snapshot_v1_2",
        "acl_snapshot_id": "ACL-SNAPSHOT::CALLER::SELF-SIGNED",
        "resolver_ref": "resolver://caller/self-signed",
        "store_revision": 999,
        "principal_ref": "principal://reviewer/1",
        "session_id": session.session_id,
        "run_id": run.run_id,
        "projection_policy_digest": policy,
        "grants": (caller_grant,),
        "issued_by": "host_acl_resolver",
    }
    caller_snapshot = RunEventAclSnapshot(
        **caller_snapshot_body,
        acl_snapshot_digest=canonical_json_sha256(caller_snapshot_body),
    )
    caller_snapshot_forgery = _self_signed_authorization_view(
        authorization_view_id="AUTH-VIEW::DELL::CALLER-SNAPSHOT-FORGERY",
        acl_snapshot_digest=caller_snapshot.acl_snapshot_digest,
        principal_ref="principal://reviewer/1",
        session_id=session.session_id,
        run_id=run.run_id,
        projection_policy_digest=policy,
        visible_ref_ids=("ref://restricted/input",),
    )
    with pytest.raises(
        CanonicalV1_2Error,
        match="run_event_authorization_view_snapshot_stale",
    ):
        project_run_events(
            events,
            run_id=run.run_id,
            projection_policy_digest=policy,
            authorization_view=caller_snapshot_forgery,
            acl_resolver=resolver,
        )

    projection = project_run_events(
        events, run_id=run.run_id,
        projection_policy_digest=policy,
        authorization_view=auth,
        acl_resolver=resolver,
    )
    assert [item.projection_sequence for item in projection] == [1, 2]
    assert [item.source_session_sequence for item in projection] == [2, 4]
    assert projection[0].visible_input_refs == ("ref://public/input",)
    assert projection[0].visible_output_refs == ("ref://public/output",)
    assert projection[0].visible_feedback_refs == ("ref://public/feedback",)
    assert project_run_events(
        events, run_id=run.run_id,
        projection_policy_digest=policy,
        authorization_view=auth,
        acl_resolver=resolver,
    ) == projection

    validate_run_event_projection(
        projection, events, run_id=run.run_id,
        expected_projection_policy_digest=policy,
        expected_authorization_view=auth,
        acl_resolver=resolver,
    )
    with pytest.raises(CanonicalV1_2Error, match="projection_policy_stale"):
        validate_run_event_projection(
            projection, events, run_id=run.run_id,
            expected_projection_policy_digest=_digest("new-policy"),
            expected_authorization_view=auth,
            acl_resolver=resolver,
        )

    resolver.store_revision += 1
    with pytest.raises(
        CanonicalV1_2Error,
        match="run_event_authorization_view_snapshot_stale",
    ):
        validate_run_event_authorization_view(auth, acl_resolver=resolver)
    with pytest.raises(
        CanonicalV1_2Error,
        match="run_event_authorization_view_snapshot_stale",
    ):
        validate_run_event_projection(
            projection,
            events,
            run_id=run.run_id,
            expected_projection_policy_digest=policy,
            expected_authorization_view=auth,
            acl_resolver=resolver,
        )

    other_session = _session(session_id="SESSION::DELL::OTHER")
    with pytest.raises(CanonicalV1_2Error, match="session_mismatch"):
        append_session_event_v1_2(
            events,
            session_id=other_session.session_id,
            run_id=run.run_id,
            event_type="run_started",
            actor_id="runtime",
            occurred_at=NOW + timedelta(seconds=4),
        )


def test_checkpoint_derives_material_closure_and_detects_stale_state() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)
    base_events = _interleaved_events(session, run, invocation)
    finding_opened = append_session_event_v1_2(
        base_events,
        session_id=session.session_id,
        run_id=run.run_id,
        event_type="finding_opened",
        actor_id="verifier",
        occurred_at=NOW + timedelta(seconds=4),
        output_refs=("finding://verifier/1",),
    )
    events = (*base_events, finding_opened)
    resolver = _HostCurrentContextMaterialResolver(
        session_id=session.session_id,
        run_id=run.run_id,
        accepted_plan_ref=run.current_plan_ref,
        accepted_plan_digest=run.current_plan_digest,
        events=events,
        research_graph_digest=_digest("graph"),
        open_finding_refs=("finding://verifier/1",),
    )
    sources = derive_required_material_ref_sources_v1_2(
        run=run,
        material_resolver=resolver,
    )
    checkpoint = create_context_checkpoint_v1_2(
        session=session,
        run=run,
        invocation=invocation,
        material_resolver=resolver,
        checkpoint_id="CHECKPOINT::DELL::001",
        created_at=NOW + timedelta(minutes=2),
    )

    assert run.current_plan_ref in checkpoint.required_material_refs
    assert any(ref.startswith("event-ledger://") for ref in checkpoint.required_material_refs)
    assert checkpoint.material_ref_sources == sources
    assert checkpoint.minimum_route_obligation_refs == ("minimum-route://Q1",)
    assert checkpoint.unresolved_verifier_finding_refs == ("finding://verifier/1",)
    validate_context_checkpoint_v1_2(
        checkpoint,
        session=session,
        run=run,
        invocation=invocation,
        material_resolver=resolver,
    )

    with pytest.raises(
        CanonicalV1_2Error,
        match="caller_authority_fields_forbidden",
    ):
        create_context_checkpoint_v1_2(
            session=session,
            run=run,
            invocation=invocation,
            material_resolver=resolver,
            checkpoint_id="CHECKPOINT::DELL::CALLER-AUTHORITY",
            research_graph_digest=_digest("caller-graph"),
        )
    for field_name, value in (
        ("authority_refs", ()),
        ("active_stop_decision_ref", "stop://caller/arbitrary"),
        ("budget_state_ref", "budget://caller/arbitrary"),
        ("context_projection_ref", "context-projection://caller/arbitrary"),
        ("langgraph_checkpoint_ref", "langgraph://caller/arbitrary"),
    ):
        with pytest.raises(
            CanonicalV1_2Error,
            match="caller_authority_fields_forbidden",
        ):
            create_context_checkpoint_v1_2(
                session=session,
                run=run,
                invocation=invocation,
                material_resolver=resolver,
                checkpoint_id=f"CHECKPOINT::DELL::CALLER::{field_name}",
                **{field_name: value},
            )

    forged_checkpoint_body = checkpoint.model_dump(
        mode="json",
        exclude={"checkpoint_digest"},
    )
    forged_checkpoint_body["research_graph_digest"] = "not-a-sha256"
    forged_checkpoint = checkpoint.model_copy(
        update={
            "research_graph_digest": "not-a-sha256",
            "checkpoint_digest": canonical_json_sha256(forged_checkpoint_body),
        }
    )
    with pytest.raises(CanonicalV1_2Error, match="context_checkpoint_invalid"):
        validate_context_checkpoint_v1_2(
            forged_checkpoint,
            session=session,
            run=run,
            invocation=invocation,
            material_resolver=resolver,
        )

    later = append_session_event_v1_2(
        events, session_id=session.session_id, run_id=run.run_id,
        event_type="finding_opened", actor_id="verifier",
        occurred_at=NOW + timedelta(minutes=3), output_refs=("finding://verifier/2",),
    )
    resolver.events = (*events, later)
    resolver.open_finding_refs = ("finding://verifier/1", "finding://verifier/2")
    resolver.store_revision += 1
    with pytest.raises(CanonicalV1_2Error, match="not_latest"):
        validate_context_checkpoint_v1_2(
            checkpoint,
            session=session,
            run=run,
            invocation=invocation,
            material_resolver=resolver,
        )

    graph_changed_resolver = _HostCurrentContextMaterialResolver(
        session_id=session.session_id,
        run_id=run.run_id,
        accepted_plan_ref=run.current_plan_ref,
        accepted_plan_digest=run.current_plan_digest,
        events=events,
        research_graph_digest=_digest("graph-revision-2"),
        open_finding_refs=("finding://verifier/1",),
        store_revision=2,
    )
    with pytest.raises(CanonicalV1_2Error, match="research_graph_stale"):
        validate_context_checkpoint_v1_2(
            checkpoint,
            session=session,
            run=run,
            invocation=invocation,
            material_resolver=graph_changed_resolver,
        )

    stale_invocation = _invocation(
        session,
        run,
        invocation_id="INVOCATION::DELL::STALE",
    )
    with pytest.raises(CanonicalV1_2Error, match="run_invocation_stale"):
        validate_context_checkpoint_v1_2(
            checkpoint,
            session=session,
            run=run,
            invocation=stale_invocation,
            material_resolver=graph_changed_resolver,
        )

    invocation_2 = _invocation(
        session,
        run,
        invocation_id="INVOCATION::DELL::002",
    )
    invocation_2_started = append_session_event_v1_2(
        events,
        session_id=session.session_id,
        run_id=run.run_id,
        run_invocation_id=invocation_2.invocation_id,
        event_type="run_invocation_started",
        actor_id="runtime",
        occurred_at=NOW + timedelta(minutes=1),
    )
    events_with_new_invocation = (*events, invocation_2_started)
    invocation_2_resolver = _HostCurrentContextMaterialResolver(
        session_id=session.session_id,
        run_id=run.run_id,
        accepted_plan_ref=run.current_plan_ref,
        accepted_plan_digest=run.current_plan_digest,
        events=events_with_new_invocation,
        research_graph_digest=_digest("graph"),
        open_finding_refs=("finding://verifier/1",),
        store_revision=2,
    )
    with pytest.raises(CanonicalV1_2Error, match="run_invocation_not_current"):
        create_context_checkpoint_v1_2(
            session=session,
            run=run,
            invocation=invocation,
            material_resolver=invocation_2_resolver,
            checkpoint_id="CHECKPOINT::DELL::STALE-INVOCATION",
        )

    same_id_changed_invocation = _invocation(
        session,
        run,
        trigger_ref="command://different-trigger",
        lease_ref="lease://different-worker",
    )
    assert same_id_changed_invocation.invocation_id == invocation.invocation_id
    assert same_id_changed_invocation.invocation_digest != invocation.invocation_digest
    with pytest.raises(CanonicalV1_2Error, match="run_invocation_stale"):
        validate_context_checkpoint_v1_2(
            checkpoint,
            session=session,
            run=run,
            invocation=same_id_changed_invocation,
            material_resolver=graph_changed_resolver,
        )

    with pytest.raises(ValidationError):
        create_required_material_ref_sources(
            accepted_plan_refs=(), event_ledger_refs=(),
            notebook_refs=(), open_finding_refs=(),
        )

    with pytest.raises(
        CanonicalV1_2Error,
        match="caller_authority_fields_forbidden",
    ):
        create_context_checkpoint_v1_2(
            session=session,
            run=run,
            invocation=invocation,
            material_resolver=graph_changed_resolver,
            checkpoint_id="CHECKPOINT::DELL::CALLER-EXTRA-CLAIM",
            claim_ledger_refs=("claim-ledger://caller/forged",),
        )

    ledger = create_canonical_event_ledger_snapshot(
        ledger_snapshot_id="LEDGER-SNAPSHOT::OMITTED-FINDING",
        repository_ref="repository://canonical-events/test",
        session_id=session.session_id,
        store_revision=1,
        events=events,
        canonical_tip_digest=events[-1].event_digest,
    )
    snapshot_state = {
        "material_snapshot_id": "MATERIAL-SNAPSHOT::NEGATIVE",
        "resolver_ref": "resolver://host/current-context/test",
        "store_revision": 1,
        "session_id": session.session_id,
        "run_id": run.run_id,
        "accepted_plan_ref": run.current_plan_ref,
        "accepted_plan_digest": run.current_plan_digest,
        "research_graph_digest": _digest("graph"),
        "canonical_event_ledger": ledger,
        "notebook_revision": 1,
        "open_finding_refs": ("finding://verifier/1",),
        "coverage_state_refs": ("coverage://Q1",),
        "minimum_route_obligation_refs": ("minimum-route://Q1",),
        "accepted_evidence_refs": (),
        "numeric_fact_refs": (),
        "claim_ledger_refs": ("claim-ledger://branch/1",),
        "calculation_receipt_refs": (),
        "disclosure_receipt_refs": ("disclosure://1",),
        "skill_consumption_receipt_refs": (),
        "open_gap_refs": (),
        "unresolved_feedback_refs": (),
        "counterevidence_refs": (),
        "open_question_refs": (),
        "pending_intervention_refs": (),
        "authority_refs": ("authority://zero-model",),
        "active_stop_decision_ref": "stop://continue/1",
        "budget_state_ref": "budget://run/1",
        "context_projection_ref": "context-projection://1",
        "langgraph_checkpoint_ref": "langgraph://thread/checkpoint/1",
    }
    with pytest.raises(ValidationError, match="open_finding_state_mismatch"):
        create_current_context_material_snapshot_v1_2(
            **{
                **snapshot_state,
                "material_snapshot_id": "MATERIAL-SNAPSHOT::OMITTED-FINDING",
                "open_finding_refs": (),
            }
        )
    with pytest.raises(ValidationError):
        create_current_context_material_snapshot_v1_2(
            **{
                **snapshot_state,
                "material_snapshot_id": "MATERIAL-SNAPSHOT::NO-MINIMUM-ROUTE",
                "minimum_route_obligation_refs": (),
            }
        )


def _legacy_a02_session():
    return create_agent_session(
        session_id="SESSION::LEGACY::A02",
        run_id=LEGACY_A02_RUN_ID,
        case_id="DELL_AI_INFRA_REFERENCE_VERTICAL",
        case_version="FIN_0_1_3",
        as_of_date="2026-09-02",
        objective_ref="objective://legacy/a02",
        active_plan_ref="plan://legacy/a02",
        created_at="2026-09-02T23:50:00+08:00",
    )


def test_legacy_a02_exact_bundle_maps_four_distinct_identities() -> None:
    source_bundle = load_legacy_a02_source_bundle()
    mapped = map_legacy_a02_identity(source_bundle, imported_at=NOW)

    assert mapped.legacy_paid_full_chain_execution_id == LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID
    assert mapped.legacy_paid_full_chain_execution_id != mapped.research_run.run_id
    assert mapped.research_run.run_id == LEGACY_A02_RUN_ID
    assert mapped.research_run.status == "START_FAILED"
    assert mapped.initial_run_invocation.ordinal == 1
    assert mapped.planner_action_attempt.action_attempt_id == source_bundle.planner_action_attempt_id
    assert mapped.planner_action_attempt.actor_id == source_bundle.planner_actor_id
    assert mapped.planner_action_attempt.receipt_kind == "FAILURE"
    assert mapped.planner_action_attempt.outcome == "APPLIED"
    assert mapped.research_run.legacy_paid_full_chain_execution_label == "A02"
    assert mapped.agent_session.created_at == datetime.fromisoformat(source_bundle.run_started_at)
    assert mapped.agent_session.updated_at == datetime.fromisoformat(source_bundle.run_failed_at)
    assert mapped.research_run.terminal_at == datetime.fromisoformat(source_bundle.run_failed_at)
    assert mapped.planner_action_attempt.created_at == datetime.fromisoformat(
        source_bundle.planner_started_at
    )
    assert mapped.planner_action_attempt.terminal_at.isoformat(timespec="microseconds") == (
        "2026-09-02T23:55:36.631200+08:00"
    )
    assert mapped.imported_at == NOW
    assert mapped.agent_session.updated_at != mapped.imported_at

    tampered = source_bundle.model_dump(mode="python", exclude={"source_bundle_digest"})
    tampered["run_failed_at"] = "2026-09-02T23:56:00+08:00"
    with pytest.raises(ValidationError, match="legacy_a02_exact_source_bundle_required"):
        type(source_bundle)(
            **tampered,
            source_bundle_digest=canonical_json_sha256(tampered),
        )

    with pytest.raises(
        CanonicalV1_2Error,
        match="legacy_a02_import_precedes_historical_failure",
    ):
        map_legacy_a02_identity(
            source_bundle,
            imported_at=datetime.fromisoformat("2026-09-02T23:55:00+08:00"),
        )

    forged_model_copy = source_bundle.model_copy(
        update={"run_failed_at": "2026-09-02T23:56:00+08:00"}
    )
    with pytest.raises(CanonicalV1_2Error, match="legacy_a02_exact_source_bundle_invalid"):
        map_legacy_a02_identity(forged_model_copy, imported_at=NOW)

    for known_a02_identity in (
        LEGACY_A02_RUN_ID,
        LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID,
    ):
        legacy_a02 = dict(_legacy_a02_session())
        legacy_a02["run_id"] = known_a02_identity
        legacy_a02["session_digest"] = legacy_canonical_digest(
            {key: value for key, value in legacy_a02.items() if key != "session_digest"}
        )
        with pytest.raises(CanonicalV1_2Error, match="requires_exact_identity_mapper"):
            adapt_legacy_agent_session_v1_0(
                legacy_a02,
                objective_digest=_digest("legacy-objective"),
                data_snapshot_ref="snapshot://legacy/a02",
                data_snapshot_digest=_digest("legacy-snapshot"),
                runtime_policy_ref="policy://paid-successor/A03",
                runtime_policy_digest=_digest("paid-policy"),
                authority_refs=("authority://paid-successor/A03",),
                active_plan_digest=_digest("legacy-plan"),
            )


def test_legacy_a02_source_bundle_loader_fails_closed_on_missing_or_drift(
    tmp_path: Path,
) -> None:
    with pytest.raises(CanonicalV1_2Error, match="legacy_a02_exact_source_bundle_invalid"):
        load_legacy_a02_source_bundle(tmp_path)

    source_bundle = load_legacy_a02_source_bundle()
    payload = source_bundle.model_dump(mode="json")
    payload["run_failed_at"] = "2026-09-02T23:56:00+08:00"
    unsigned = {key: value for key, value in payload.items() if key != "source_bundle_digest"}
    payload["source_bundle_digest"] = canonical_json_sha256(unsigned)
    destination = tmp_path / LEGACY_A02_SOURCE_BUNDLE_REF
    destination.parent.mkdir(parents=True)
    destination.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CanonicalV1_2Error, match="legacy_a02_exact_source_bundle_invalid"):
        load_legacy_a02_source_bundle(tmp_path)


def test_known_a01_identities_require_exact_source_bundle() -> None:
    for known_a01_identity in (
        LEGACY_A01_RUN_ID,
        LEGACY_A01_PAID_FULL_CHAIN_EXECUTION_ID,
    ):
        legacy_a01 = dict(_legacy_a02_session())
        legacy_a01["session_id"] = "SESSION::LEGACY::A01"
        legacy_a01["run_id"] = known_a01_identity
        legacy_a01["session_digest"] = legacy_canonical_digest(
            {key: value for key, value in legacy_a01.items() if key != "session_digest"}
        )
        with pytest.raises(CanonicalV1_2Error, match="legacy_a01_exact_source_bundle_required"):
            adapt_legacy_agent_session_v1_0(
                legacy_a01,
                objective_digest=_digest("legacy-objective"),
                data_snapshot_ref="snapshot://legacy/a01",
                data_snapshot_digest=_digest("legacy-snapshot-a01"),
                runtime_policy_ref="policy://legacy/a01/read-only",
                runtime_policy_digest=_digest("legacy-policy-a01"),
                authority_refs=("authority://legacy/a01/read-only",),
                active_plan_digest=_digest("legacy-plan-a01"),
            )


def test_a02_canonical_session_identity_cannot_enter_generic_adapters() -> None:
    legacy_session = dict(_legacy_a02_session())
    legacy_session["run_id"] = "legacy-ordinary-run"
    legacy_session["session_digest"] = legacy_canonical_digest(
        {key: value for key, value in legacy_session.items() if key != "session_digest"}
    )
    with pytest.raises(CanonicalV1_2Error, match="legacy_a02_requires_exact_identity_mapper"):
        adapt_legacy_agent_session_v1_0(
            legacy_session,
            objective_digest=_digest("forged-objective"),
            data_snapshot_ref="snapshot://forged",
            data_snapshot_digest=_digest("forged-snapshot"),
            runtime_policy_ref="policy://legacy/read-only",
            runtime_policy_digest=_digest("legacy-policy"),
            authority_refs=("authority://legacy/read-only",),
            active_plan_digest=_digest("forged-plan"),
        )

    with pytest.raises(ValidationError, match="agent_session_reserved_a02_profile_mismatch"):
        _session(session_id=LEGACY_A02_CANONICAL_SESSION_ID)

    mapped = map_legacy_a02_identity(load_legacy_a02_source_bundle(), imported_at=NOW)
    legacy_event = append_session_event(
        [],
        session_id=mapped.agent_session.session_id,
        event_type="session_created",
        actor_id="runtime",
        occurred_at="2026-09-02T23:50:00+08:00",
    )
    with pytest.raises(
        CanonicalV1_2Error,
        match="legacy_a02_event_log_requires_exact_identity_mapper",
    ):
        adapt_legacy_v1_1_event_log(
            [legacy_event],
            research_run=mapped.research_run,
            run_invocation=mapped.initial_run_invocation,
            legacy_action_attempt_bindings={},
        )


def test_reserved_legacy_identity_direct_factory_collision_matrix() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)

    for forbidden_run_id in (
        LEGACY_A01_RUN_ID,
        LEGACY_A01_PAID_FULL_CHAIN_EXECUTION_ID,
        LEGACY_A02_PAID_FULL_CHAIN_EXECUTION_ID,
    ):
        with pytest.raises(ValidationError, match="reserved_legacy_identity_surface|reserved_a02_identity_surface"):
            _run(session, run_id=forbidden_run_id)

    with pytest.raises(ValidationError, match="research_run_reserved_a02_profile_mismatch"):
        _run(session, run_id=LEGACY_A02_RUN_ID)
    with pytest.raises(ValidationError, match="run_invocation_reserved_a02_profile_mismatch"):
        _invocation(session, run, invocation_id=LEGACY_A02_INITIAL_INVOCATION_ID)
    with pytest.raises(ValidationError, match="action_attempt_reserved_a02_profile_mismatch"):
        _applied_action(
            session,
            run,
            invocation,
            action_attempt_id=LEGACY_A02_PLANNER_ACTION_ATTEMPT_ID,
        )

    a02_reserved_ids = (
        LEGACY_A02_CANONICAL_SESSION_ID,
        LEGACY_A02_RUN_ID,
        LEGACY_A02_INITIAL_INVOCATION_ID,
        LEGACY_A02_PLANNER_ACTION_ATTEMPT_ID,
    )
    for reserved_id in a02_reserved_ids:
        with pytest.raises(ValidationError, match="reserved_a02|reserved_legacy"):
            _session(session_id=reserved_id)
        with pytest.raises(ValidationError, match="reserved_a02|reserved_legacy"):
            _run(session, run_id=reserved_id)
        with pytest.raises(ValidationError, match="reserved_a02|reserved_legacy"):
            _invocation(session, run, invocation_id=reserved_id)
        with pytest.raises(ValidationError, match="reserved_a02|reserved_legacy"):
            _applied_action(
                session,
                run,
                invocation,
                action_attempt_id=reserved_id,
            )

    exact = map_legacy_a02_identity(load_legacy_a02_source_bundle(), imported_at=NOW)
    assert exact.agent_session.session_id == LEGACY_A02_CANONICAL_SESSION_ID
    assert exact.research_run.run_id == LEGACY_A02_RUN_ID
    assert exact.initial_run_invocation.invocation_id == LEGACY_A02_INITIAL_INVOCATION_ID
    assert exact.planner_action_attempt.action_attempt_id == (
        LEGACY_A02_PLANNER_ACTION_ATTEMPT_ID
    )


def test_legacy_a02_mapping_rejects_phantom_successor_authority() -> None:
    mapped = map_legacy_a02_identity(load_legacy_a02_source_bundle(), imported_at=NOW)
    with pytest.raises(ValidationError, match="phantom_a03_forbidden"):
        create_agent_session_v1_2(
            **{
                **mapped.agent_session.model_dump(exclude={
                    "schema_version",
                    "session_digest",
                    "authority_refs",
                }),
                "authority_refs": ("authority://paid-successor/A03",),
            }
        )
    paid_session = mapped.agent_session.model_copy(
        update={"authority_refs": ("authority://paid-successor/A03",)}
    )
    bad_mapping_body = {
        **mapped.model_dump(exclude={"schema_version", "mapping_digest", "agent_session"}),
        "schema_version": "fin_ia_legacy_a02_identity_mapping_v1_2",
        "agent_session": paid_session,
    }
    with pytest.raises(
        ValidationError,
        match="phantom_a03_forbidden|read_only_authority_required",
    ):
        LegacyA02IdentityMapping(
            **bad_mapping_body,
            mapping_digest=canonical_json_sha256(bad_mapping_body),
        )


def test_phantom_a03_is_rejected_across_every_identity_entry_surface() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)

    with pytest.raises(ValidationError, match="phantom_a03_forbidden"):
        _session(runtime_policy_ref="policy://paid-successor/A03")
    with pytest.raises(ValidationError, match="phantom_a03_forbidden"):
        _invocation(session, run, run_id="20260903-dell-successor-a03")
    with pytest.raises(ValidationError, match="phantom_a03_forbidden"):
        _applied_action(
            session,
            run,
            invocation,
            action_attempt_id="ACTION::DELL::A03::1",
        )
    with pytest.raises(ValidationError, match="phantom_a03_forbidden"):
        append_session_event_v1_2(
            [],
            session_id=session.session_id,
            run_id="20260903-dell-successor-a03",
            event_type="run_created",
            actor_id="runtime",
            occurred_at=NOW,
        )

    legacy = _legacy_a02_session()
    legacy["session_id"] = "SESSION::LEGACY::GENERIC"
    legacy["run_id"] = "legacy-non-a02-run"
    legacy["session_digest"] = legacy_canonical_digest(
        {key: value for key, value in legacy.items() if key != "session_digest"}
    )
    with pytest.raises(ValidationError, match="phantom_a03_forbidden"):
        adapt_legacy_agent_session_v1_0(
            legacy,
            objective_digest=_digest("legacy-objective"),
            data_snapshot_ref="snapshot://legacy/other",
            data_snapshot_digest=_digest("legacy-snapshot"),
            runtime_policy_ref="policy://paid-successor/A03",
            runtime_policy_digest=_digest("paid-policy"),
            authority_refs=("authority://paid-successor/A03",),
            active_plan_digest=_digest("legacy-plan"),
        )


@pytest.mark.parametrize(
    "label",
    (
        "A03",
        "a-03",
        "A_03",
        "A.03",
        "A/03",
        "A-0-3",
        "A_0_3",
        "A.0.3",
        "A/0/3",
        "A 0 3",
        "Ａ０３",
        "Ａ．０３",
        "Ａ－０－３",
    ),
)
def test_phantom_a03_normalization_cannot_bypass_identity_guard(label: str) -> None:
    with pytest.raises(ValidationError, match="phantom_a03_forbidden"):
        _session(runtime_policy_ref=f"policy://paid-successor/{label}")


@pytest.mark.parametrize(
    ("event_type", "identity"),
    [
        ("run_completed", {}),
        ("run_invocation_started", {"run_id": "RUN::DELL::001"}),
        (
            "action_intent_committed",
            {
                "run_id": "RUN::DELL::001",
                "run_invocation_id": "INVOCATION::DELL::001",
            },
        ),
        (
            "disclosure_granted",
            {
                "run_id": "RUN::DELL::001",
                "run_invocation_id": "INVOCATION::DELL::001",
            },
        ),
        (
            "publication_completed",
            {
                "run_id": "RUN::DELL::001",
                "run_invocation_id": "INVOCATION::DELL::001",
            },
        ),
    ],
)
def test_discriminated_events_require_their_owner_identity(
    event_type: str,
    identity: dict[str, str],
) -> None:
    with pytest.raises(ValidationError, match="identity_required"):
        append_session_event_v1_2(
            [],
            session_id="SESSION::DELL::001",
            event_type=event_type,  # type: ignore[arg-type]
            actor_id="runtime",
            occurred_at=NOW,
            **identity,
        )


def test_event_sequence_recomputes_each_event_digest_before_using_chain() -> None:
    session = _session()
    run = _run(session)
    invocation = _invocation(session, run)
    events = _interleaved_events(session, run, invocation)[:2]
    events = (
        *events,
        append_session_event_v1_2(
            events,
            session_id=session.session_id,
            run_id=run.run_id,
            run_invocation_id=invocation.invocation_id,
            event_type="run_invocation_started",
            actor_id="runtime",
            occurred_at=NOW + timedelta(seconds=3),
        ),
    )

    for index in range(len(events)):
        forged = list(events)
        forged[index] = forged[index].model_copy(
            update={"output_refs": (f"artifact://forged/{index}",)}
        )
        with pytest.raises(CanonicalV1_2Error, match="event_digest_invalid"):
            validate_session_event_sequence(
                forged,
                expected_session_id=session.session_id,
            )

    validator_only_body = events[1].model_dump(
        mode="json",
        exclude={"event_digest"},
    )
    validator_only_body["event_type"] = "run_invocation_started"
    validator_only_forgery = events[1].model_copy(
        update={
            "event_type": "run_invocation_started",
            "event_digest": canonical_json_sha256(validator_only_body),
        }
    )
    with pytest.raises(CanonicalV1_2Error, match="canonical_session_event_invalid"):
        validate_session_event_sequence(
            (events[0], validator_only_forgery),
            expected_session_id=session.session_id,
        )


def test_legacy_v1_1_event_adapter_preserves_source_identity_and_sequence() -> None:
    legacy = create_agent_session(
        session_id="SESSION::DELL::001",
        run_id="legacy-non-paid-run",
        case_id="DELL_AI_INFRA_REFERENCE_VERTICAL",
        case_version="FIN_0_1_3",
        as_of_date="2026-09-02",
        objective_ref="objective://legacy/generic",
        active_plan_ref="plan://legacy/generic",
        created_at="2026-09-02T23:50:00+08:00",
    )
    first = append_session_event(
        [], session_id=legacy["session_id"], event_type="session_created",
        actor_id="runtime", occurred_at="2026-09-02T23:50:00+08:00",
    )
    second = append_session_event(
        [first], session_id=legacy["session_id"], event_type="provider_attempt_requested",
        actor_id="planner", attempt_id="LEGACY::PLANNER::1",
        occurred_at="2026-09-02T23:50:01+08:00",
    )
    session = _session(session_id=legacy["session_id"])
    run = _run(session, run_id=legacy["run_id"])
    invocation = _invocation(session, run)
    action = _applied_action(
        session,
        run,
        invocation,
        action_attempt_id="ACTION::IMPORTED::PLANNER::1",
        actor_id="planner",
        action_kind="MODEL",
        action_name="planner",
        created_at=datetime.fromisoformat("2026-09-02T23:50:01+08:00"),
        terminal_at=datetime.fromisoformat("2026-09-02T23:50:02+08:00"),
    )
    adapted = adapt_legacy_v1_1_event_log(
        [first, second],
        research_run=run,
        run_invocation=invocation,
        legacy_action_attempt_bindings={"LEGACY::PLANNER::1": action},
    )

    assert [item.session_sequence for item in adapted] == [1, 2]
    assert adapted[0].legacy_source_event_digest == first["event_digest"]
    assert adapted[1].action_attempt_id == action.action_attempt_id
    validate_session_event_sequence(adapted, expected_session_id=legacy["session_id"])

    with pytest.raises(CanonicalV1_2Error, match="legacy_event_action_binding_missing"):
        adapt_legacy_v1_1_event_log(
            [first, second],
            research_run=run,
            run_invocation=invocation,
            legacy_action_attempt_bindings={},
        )

    wrong_actor = _applied_action(
        session,
        run,
        invocation,
        action_attempt_id="ACTION::IMPORTED::WRONG-ACTOR",
        actor_id="agent://specialist/wrong",
        action_kind="MODEL",
        action_name="planner",
        created_at=datetime.fromisoformat("2026-09-02T23:50:01+08:00"),
        terminal_at=datetime.fromisoformat("2026-09-02T23:50:02+08:00"),
    )
    with pytest.raises(CanonicalV1_2Error, match="legacy_event_action_actor_mismatch"):
        adapt_legacy_v1_1_event_log(
            [first, second],
            research_run=run,
            run_invocation=invocation,
            legacy_action_attempt_bindings={"LEGACY::PLANNER::1": wrong_actor},
        )

    wrong_kind = _applied_action(
        session,
        run,
        invocation,
        action_attempt_id="ACTION::IMPORTED::WRONG-KIND",
        actor_id="planner",
        action_kind="TOOL",
        action_name="planner",
        created_at=datetime.fromisoformat("2026-09-02T23:50:01+08:00"),
        terminal_at=datetime.fromisoformat("2026-09-02T23:50:02+08:00"),
    )
    with pytest.raises(CanonicalV1_2Error, match="legacy_provider_event_action_kind_mismatch"):
        adapt_legacy_v1_1_event_log(
            [first, second],
            research_run=run,
            run_invocation=invocation,
            legacy_action_attempt_bindings={"LEGACY::PLANNER::1": wrong_kind},
        )

    future_action = _applied_action(
        session,
        run,
        invocation,
        action_attempt_id="ACTION::IMPORTED::FUTURE",
        actor_id="planner",
        action_kind="MODEL",
        action_name="planner",
        created_at=datetime.fromisoformat("2026-09-02T23:50:02+08:00"),
        terminal_at=datetime.fromisoformat("2026-09-02T23:50:03+08:00"),
    )
    with pytest.raises(CanonicalV1_2Error, match="legacy_event_action_start_time_mismatch"):
        adapt_legacy_v1_1_event_log(
            [first, second],
            research_run=run,
            run_invocation=invocation,
            legacy_action_attempt_bindings={"LEGACY::PLANNER::1": future_action},
        )

    mismatched_invocation = _invocation(session, run, run_id="another-run")
    with pytest.raises(CanonicalV1_2Error, match="legacy_event_invocation_binding_invalid"):
        adapt_legacy_v1_1_event_log(
            [first, second],
            research_run=run,
            run_invocation=mismatched_invocation,
            legacy_action_attempt_bindings={"LEGACY::PLANNER::1": action},
        )
