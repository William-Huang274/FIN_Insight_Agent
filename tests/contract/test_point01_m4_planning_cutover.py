from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope, DecisionSurfaceContractVersion, ShadowComparisonRecord, canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.planning_cutover import (
    CUTOVER_FLAG_ID,
    CutoverApprovalError,
    CutoverApprovalReceipt,
    CutoverEligibilityError,
    CutoverScope,
    LaneCutoverRequest,
    LaneEligibilityPolicy,
    LegacyProjectionMapping,
    PlanningCutoverError,
    PlanningLaneCutoverService,
)
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry(
        {
            "default_deny": True,
            "flags": [
                {
                    "flag_id": "decision_surface_shadow_v0_1",
                    "default_mode": "off",
                    "allowed_modes": ["off", "shadow"],
                    "required_capability_grants": ["point01.shadow.write"],
                    "allowed_consumers": ["point01_shadow_compiler"],
                    "forbidden_consumers": [],
                },
                {
                    "flag_id": CUTOVER_FLAG_ID,
                    "default_mode": "off",
                    "allowed_modes": ["off", "case_scoped"],
                    "required_capability_grants": ["point01.cutover.execute"],
                    "allowed_consumers": ["planning_authority_cutover", "planning_authority_read_projection"],
                    "forbidden_consumers": ["evidence_runtime", "memo_writer"],
                },
            ],
        }
    )


def _command(command_type: str, payload: dict, *, expected: int = 0, idem: str | None = None) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=f"cmd-{command_type}-{idem or '1'}",
        command_type=command_type,
        tenant_id="tenant-cutover",
        project_id="project-cutover",
        case_id="case-cutover",
        actor_snapshot_ref="actor-cutover",
        permission_snapshot_ref="permission-cutover",
        policy_config_refs=("policy-cutover",),
        idempotency_key=idem or command_type,
        expected_state_version=expected,
        correlation_id="correlation-cutover",
        requested_at=datetime.now(timezone.utc),
        payload=payload,
    )


def _bundle() -> dict:
    now = datetime.now(timezone.utc).isoformat()
    scope = {
        "schema_version": "finsight_point01_canonical_runtime_v1_0",
        "tenant_id": "tenant-cutover",
        "project_id": "project-cutover",
        "case_id": "case-cutover",
        "created_at": now,
        "recorded_at": now,
        "actor_snapshot_ref": "actor-cutover",
        "permission_snapshot_ref": "permission-cutover",
        "policy_config_refs": ["policy-cutover"],
        "correlation_id": "correlation-cutover",
    }
    return {
        "contract": {
            **scope,
            "current_status": "shadow_compiled",
            "contract_id": "contract-cutover",
            "contract_version_id": "contract-cutover:v1",
            "contract_version": 1,
            "query": "Assess durable demand quality.",
            "as_of": now,
            "universe": ["AAA"],
            "language": "en",
            "compiler_policy_ref": "compiler-cutover",
            "required_cell_ids": ["cell-cutover"],
        },
        "cells": [
            {
                **scope,
                "current_status": "shadow_compiled",
                "contract_version_id": "contract-cutover:v1",
                "cell_id": "cell-cutover",
                "cell_version_id": "cell-cutover:v1",
                "cell_version": 1,
                "decision_question": "Can demand remain durable?",
                "origin_type": "universal",
                "owner_role": "fundamental_analyst",
                "materiality": "high",
                "stop_rule": "accepted evidence or typed gap",
            }
        ],
        "slots": [
            {
                **scope,
                "current_status": "shadow_required",
                "cell_version_id": "cell-cutover:v1",
                "evidence_slot_id": "slot-cutover",
                "slot_version_id": "slot-cutover:v1",
                "slot_version": 1,
                "evidence_role": "demand_quality",
                "entity_scope": ["AAA"],
                "period_scope": "latest_quarter",
                "source_policy_ref": "issuer_first",
                "acceptance_role": "primary_or_context",
                "required": True,
            }
        ],
        "gaps": [],
    }


def _service(tmp_path, *, approval_resolver=None):
    store = SQLiteCanonicalStore(tmp_path / "canonical.sqlite")
    flags = _flags()
    facade = RuntimeFacade(
        store,
        FileCanonicalObjectStore(tmp_path / "objects"),
        flags,
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    facade.create_research_case(
        _command(
            "CREATE_RESEARCH_CASE",
            {"query": "Assess durable demand quality.", "universe": ["AAA"], "accountable_owner_ref": "lead", "legacy_task_id": "legacy-task", "legacy_run_id": "legacy-run"},
        )
    )
    facade.create_work_unit(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-cutover", "input_version_refs": ["summary-v1"]}))
    facade.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-cutover", "attempt_id": "attempt-cutover"}))
    facade.commit_decision_surface_bundle(
        _command(
            "COMMIT_DECISION_SURFACE_BUNDLE",
            {"work_unit_id": "wu-cutover", "attempt_id": "attempt-cutover", "artifact_id": "artifact-cutover", "bundle": _bundle()},
            expected=1,
        )
    )
    comparison_time = datetime.now(timezone.utc)
    comparison = ShadowComparisonRecord(
        tenant_id="tenant-cutover",
        project_id="project-cutover",
        case_id="case-cutover",
        created_at=comparison_time,
        recorded_at=comparison_time,
        actor_snapshot_ref="comparison-cutover",
        permission_snapshot_ref="permission-cutover",
        correlation_id="comparison-cutover",
        current_status="shadow_compared",
        comparison_id="comparison-cutover",
        comparison_version=1,
        legacy_plan_ref="legacy-task",
        canonical_contract_version_id="contract-cutover:v1",
        rubric_version="m3-fixture-v1",
        summary_metrics={"semantic_coverage": 1.0},
        details_artifact_ref="artifact-cutover:v1",
    )
    with store.transaction() as tx:
        tx.insert("canonical_shadow_comparisons", comparison.comparison_id, comparison.comparison_version, comparison.model_dump(mode="json"))
    service = PlanningLaneCutoverService(
        store,
        flags,
        LaneEligibilityPolicy(policy_ref="m4-cutover-policy-v1"),
        grants={"point01.cutover.execute"},
        approval_resolver=approval_resolver,
    )
    return store, facade, service


def _request(store: SQLiteCanonicalStore, now: datetime) -> LaneCutoverRequest:
    scope = CutoverScope(tenant_id="tenant-cutover", project_id="project-cutover", case_id="case-cutover", lane_id="planning")
    contract = next(row for row in store.list_latest("canonical_decision_surface_contract_versions", case_id=scope.case_id) if row["contract_version_id"] == "contract-cutover:v1")
    artifact = next(row for row in store.list_latest("canonical_artifact_versions", case_id=scope.case_id) if row["artifact_version_id"] == "artifact-cutover:v1")
    comparison = next(row for row in store.list_latest("canonical_shadow_comparisons", case_id=scope.case_id) if row["comparison_id"] == "comparison-cutover")
    values = {
        "schema": "schema-digest",
        "policy": "policy-digest",
        "store": store.store_identity(),
        "contract_version": contract["contract_version_id"],
        "contract": canonical_digest(contract),
        "artifact_version": artifact["artifact_version_id"],
        "artifact": artifact["object_digest"],
        "comparison_id": comparison["comparison_id"],
        "comparison": canonical_digest(comparison),
    }
    receipt = CutoverApprovalReceipt(
        approval_id="approval-cutover",
        approval_registry_ref="fixture-hil-registry-cutover",
        status="approved",
        approver_type="fixture_human",
        schema_digest=values["schema"],
        policy_digest=values["policy"],
        store_identity=values["store"],
        contract_version_id=values["contract_version"],
        contract_digest=values["contract"],
        artifact_version_id=values["artifact_version"],
        artifact_digest=values["artifact"],
        comparison_id=values["comparison_id"],
        comparison_digest=values["comparison"],
        issued_at=now - timedelta(minutes=1),
        expires_at=now + timedelta(minutes=5),
    )
    return LaneCutoverRequest(
        cutover_id="cutover-case-1",
        scope=scope,
        expected_authority_version=1,
        schema_digest=values["schema"],
        policy_digest=values["policy"],
        store_identity=values["store"],
        contract_version_id=values["contract_version"],
        contract_digest=values["contract"],
        artifact_version_id=values["artifact_version"],
        artifact_digest=values["artifact"],
        comparison_id=values["comparison_id"],
        comparison_digest=values["comparison"],
        approval=receipt,
        gate_evidence_refs=tuple(str(value) for value in values.values()),
    )


def test_m4_case_scoped_cutover_is_atomic_readable_and_legacy_projection_is_read_only(tmp_path) -> None:
    store, facade, service = _service(tmp_path)
    now = datetime.now(timezone.utc)
    request = _request(store, now)
    eligibility = service.evaluate_eligibility(request.scope, consumer_inventory_complete=True, legacy_projection_ready=True)
    requested = service.request_cutover(request, eligibility, actor_snapshot_ref="cutover-actor", permission_snapshot_ref="cutover-permission", correlation_id="cutover-correlation", now=now)
    assert requested.current_status == "requested"
    executed = service.execute_cutover(request, actor_snapshot_ref="cutover-actor", permission_snapshot_ref="cutover-permission", correlation_id="cutover-correlation", now=now)
    assert executed.current_status == "executed"
    assert facade.get_case_execution_view("case-cutover")["planning_authority"] == "canonical_for_lane"
    assert facade.get_work_unit_execution_view("wu-cutover")["planning_authority"] == "canonical_for_lane"
    read = service.get_read_model(request.scope, mappings=(LegacyProjectionMapping(legacy_required_item_id="legacy_demand", canonical_cell_key="cell-cutover", information_loss_tags=("semantic_projection",)),))
    assert read.authority == "canonical_for_lane"
    assert read.legacy_projection and read.legacy_projection.read_only is True
    assert read.legacy_projection.required_items[0]["required_item_id"] == "legacy_demand"
    workbench = service.workbench_projection(request.scope, mappings=(LegacyProjectionMapping(legacy_required_item_id="legacy_demand", canonical_cell_key="cell-cutover", information_loss_tags=("semantic_projection",)),))
    assert workbench.authority_label == "canonical_for_lane"
    assert workbench.read_only is True


def test_m4_rejects_ineligible_and_stale_hash_bound_approval(tmp_path) -> None:
    store, _, service = _service(tmp_path)
    now = datetime.now(timezone.utc)
    request = _request(store, now)
    ineligible = service.evaluate_eligibility(request.scope, consumer_inventory_complete=False, legacy_projection_ready=True)
    with pytest.raises(CutoverEligibilityError):
        service.request_cutover(request, ineligible, actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now)
    stale = request.model_copy(update={"approval": request.approval.model_copy(update={"artifact_digest": "wrong"})})
    eligible = service.evaluate_eligibility(stale.scope, consumer_inventory_complete=True, legacy_projection_ready=True)
    with pytest.raises(CutoverApprovalError):
        service.request_cutover(stale, eligible, actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now)


def test_m4_kill_switch_allows_only_rollback_control_and_preserves_history(tmp_path) -> None:
    store, facade, service = _service(tmp_path)
    now = datetime.now(timezone.utc)
    request = _request(store, now)
    eligibility = service.evaluate_eligibility(request.scope, consumer_inventory_complete=True, legacy_projection_ready=True)
    service.request_cutover(request, eligibility, actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now)
    service.execute_cutover(request, actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now)
    store.set_kill_switch(True)
    rolled_back = service.rollback_cutover(request, reason="fixture_kill_switch", actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now)
    assert rolled_back.current_status == "rolled_back"
    report = service.recover_cutover(request.scope)
    assert report.status == "pass"
    assert report.authority == "legacy"
    assert report.decision_count == 1
    assert "PLANNING_ROLLBACK_EXECUTED" in report.event_types
    assert facade.get_case_execution_view("case-cutover")["planning_authority"] == "legacy"
    events = [event for event in store.list_events() if (event.get("payload") or {}).get("cutover_id") == request.cutover_id]
    assert [event["event_type"] for event in events] == [
        "PLANNING_CUTOVER_REQUESTED",
        "PLANNING_CUTOVER_DECIDED",
        "PLANNING_AUTHORITY_CHANGED",
        "PLANNING_ROLLBACK_EXECUTED",
    ]
    assert [(event["state_version_before"], event["state_version_after"]) for event in events] == [(0, 1), (1, 2), (1, 2), (2, 3)]
    assert [event["payload"]["state_subject"] for event in events] == [
        "lane_cutover_decision",
        "lane_cutover_decision",
        "case_control_summary",
        "case_control_summary",
    ]


def test_m4_tenant_scope_isolation_rejects_cross_tenant_read(tmp_path) -> None:
    _, _, service = _service(tmp_path)
    wrong_scope = CutoverScope(tenant_id="other-tenant", project_id="project-cutover", case_id="case-cutover", lane_id="planning")
    with pytest.raises(PlanningCutoverError, match="tenant_project_case_scope_mismatch"):
        service.get_read_model(wrong_scope)


def test_m4_execute_rechecks_expiry_and_human_revocation_at_transaction_time(tmp_path) -> None:
    store, _, service = _service(tmp_path)
    now = datetime.now(timezone.utc)
    expired = _request(store, now)
    eligible = service.evaluate_eligibility(expired.scope, consumer_inventory_complete=True, legacy_projection_ready=True)
    service.request_cutover(expired, eligible, actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now)
    with pytest.raises(CutoverApprovalError, match="approval_missing_expired_revoked_or_hash_mismatch"):
        service.execute_cutover(expired, actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now + timedelta(minutes=6))

    approval_state = {}
    human = _request(store, now).model_copy(update={"cutover_id": "cutover-human", "approval": _request(store, now).approval.model_copy(update={"approval_id": "approval-human", "approver_type": "human"})})
    approval_state["current"] = human.approval
    human_service = PlanningLaneCutoverService(
        store,
        _flags(),
        LaneEligibilityPolicy(policy_ref="m4-cutover-policy-v1"),
        grants={"point01.cutover.execute"},
        approval_resolver=lambda approval_id: approval_state["current"],
    )
    human_service.request_cutover(human, eligible, actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now)
    approval_state["current"] = human.approval.model_copy(update={"revoked_at": now})
    with pytest.raises(CutoverApprovalError, match="approval_missing_expired_revoked_or_hash_mismatch"):
        human_service.execute_cutover(human, actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now)

    registry_mismatch = _request(store, now).model_copy(
        update={
            "cutover_id": "cutover-human-registry-mismatch",
            "approval": _request(store, now).approval.model_copy(
                update={"approval_id": "approval-human-registry-mismatch", "approver_type": "human", "approval_registry_ref": "registry-original"}
            ),
        }
    )
    approval_state["current"] = registry_mismatch.approval.model_copy(update={"approval_registry_ref": "registry-replaced"})
    with pytest.raises(CutoverApprovalError, match="approval_resolver_identity_mismatch"):
        human_service.request_cutover(registry_mismatch, eligible, actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now)


def test_m4_rechecks_exact_store_entities_and_pins_canonical_read_to_approved_contract(tmp_path) -> None:
    store, _, service = _service(tmp_path)
    now = datetime.now(timezone.utc)
    request = _request(store, now)
    eligible = service.evaluate_eligibility(request.scope, consumer_inventory_complete=True, legacy_projection_ready=True)
    tampered = request.model_copy(
        update={
            "artifact_digest": "tampered-artifact-digest",
            "approval": request.approval.model_copy(update={"artifact_digest": "tampered-artifact-digest"}),
            "gate_evidence_refs": tuple("tampered-artifact-digest" if value == request.artifact_digest else value for value in request.gate_evidence_refs),
        }
    )
    with pytest.raises(CutoverApprovalError, match="approved_artifact_digest_mismatch"):
        service.request_cutover(tampered, eligible, actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now)

    service.request_cutover(request, eligible, actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now)
    service.execute_cutover(request, actor_snapshot_ref="actor", permission_snapshot_ref="permission", correlation_id="correlation", now=now)
    approved_contract = next(row for row in store.list_versions("canonical_decision_surface_contract_versions", case_id="case-cutover") if row["contract_version_id"] == "contract-cutover:v1")
    newer_contract = DecisionSurfaceContractVersion.model_validate(
        {
            **approved_contract,
            "contract_version": 2,
            "contract_version_id": "contract-cutover:v2",
            "recorded_at": now + timedelta(seconds=1),
            "supersedes_version_id": "contract-cutover:v1",
        }
    )
    with store.transaction() as tx:
        tx.insert("canonical_decision_surface_contract_versions", "contract-cutover", 2, newer_contract.model_dump(mode="json"))
    read = service.get_read_model(request.scope, mappings=(LegacyProjectionMapping(legacy_required_item_id="legacy_demand", canonical_cell_key="cell-cutover", information_loss_tags=("semantic_projection",)),))
    assert read.contract["contract_version_id"] == "contract-cutover:v1"
    assert all(cell["contract_version_id"] == "contract-cutover:v1" for cell in read.cells)


def test_m4_read_only_preflight_returns_exact_bindings_and_rejects_downstream_consumers(tmp_path) -> None:
    store, _, service = _service(tmp_path)
    scope = CutoverScope(tenant_id="tenant-cutover", project_id="project-cutover", case_id="case-cutover", lane_id="planning")
    preflight = service.read_only_preflight(scope)
    assert preflight.store_identity == store.store_identity()
    assert preflight.contract_version_id == "contract-cutover:v1"
    assert preflight.artifact_version_id == "artifact-cutover:v1"
    assert preflight.comparison_id == "comparison-cutover"
    with pytest.raises(CutoverEligibilityError, match="downstream_consumers_must_be_empty"):
        service.read_only_preflight(scope, downstream_consumer_ids=("memo_writer",))
