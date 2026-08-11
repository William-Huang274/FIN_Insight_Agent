from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope, ShadowComparisonRecord, canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.planning_cutover import (
    CutoverApprovalError,
    CutoverApprovalReceipt,
    CutoverScope,
    LaneCutoverRequest,
    LaneEligibilityPolicy,
    LegacyProjectionMapping,
    PlanningCutoverError,
    PlanningLaneCutoverService,
)
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


DEFAULT_OUTPUT_DIR = ROOT / "data/manifests"
POINTS = tuple(f"M4.{number}" for number in range(1, 8))


def _command(command_type: str, payload: dict[str, Any], *, expected: int = 0, idem: str | None = None) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=f"m4-{command_type.lower()}-{idem or '1'}",
        command_type=command_type,
        tenant_id="tenant-m4-fixture",
        project_id="project-m4-fixture",
        case_id="case-m4-fixture",
        actor_snapshot_ref="actor-m4-fixture",
        permission_snapshot_ref="permission-m4-fixture",
        policy_config_refs=("point01-m4-policy-v1",),
        idempotency_key=idem or command_type,
        expected_state_version=expected,
        correlation_id="correlation-m4-fixture",
        requested_at=datetime.now(timezone.utc),
        payload=payload,
    )


def _bundle() -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    scope = {"schema_version": "finsight_point01_canonical_runtime_v1_0", "tenant_id": "tenant-m4-fixture", "project_id": "project-m4-fixture", "case_id": "case-m4-fixture", "created_at": now, "recorded_at": now, "actor_snapshot_ref": "actor-m4-fixture", "permission_snapshot_ref": "permission-m4-fixture", "policy_config_refs": ["point01-m4-policy-v1"], "correlation_id": "correlation-m4-fixture"}
    return {
        "contract": {**scope, "current_status": "shadow_compiled", "contract_id": "contract-m4-fixture", "contract_version_id": "contract-m4-fixture:v1", "contract_version": 1, "query": "Assess durable demand quality.", "as_of": now, "universe": ["M4"], "language": "en", "compiler_policy_ref": "compiler-m4-fixture", "required_cell_ids": ["cell-m4-fixture"]},
        "cells": [{**scope, "current_status": "shadow_compiled", "contract_version_id": "contract-m4-fixture:v1", "cell_id": "cell-m4-fixture", "cell_version_id": "cell-m4-fixture:v1", "cell_version": 1, "decision_question": "Can demand remain durable?", "origin_type": "universal", "owner_role": "fundamental_analyst", "materiality": "high", "stop_rule": "accepted evidence or typed gap"}],
        "slots": [{**scope, "current_status": "shadow_required", "cell_version_id": "cell-m4-fixture:v1", "evidence_slot_id": "slot-m4-fixture", "slot_version_id": "slot-m4-fixture:v1", "slot_version": 1, "evidence_role": "demand_quality", "entity_scope": ["M4"], "period_scope": "latest_quarter", "source_policy_ref": "issuer_first", "acceptance_role": "primary_or_context", "required": True}],
        "gaps": [],
    }


def _runtime(work_root: Path) -> tuple[SQLiteCanonicalStore, RuntimeFacade, PlanningLaneCutoverService]:
    flags = FeatureFlagRegistry.from_path(ROOT / "configs/runtime/point01_feature_flags_v1_0.json")
    store = SQLiteCanonicalStore(work_root / "canonical.sqlite")
    facade = RuntimeFacade(store, FileCanonicalObjectStore(work_root / "objects"), flags, mode="shadow", grants={"point01.shadow.write"})
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "Assess durable demand quality.", "universe": ["M4"], "accountable_owner_ref": "lead-m4", "legacy_task_id": "legacy-task-m4", "legacy_run_id": "legacy-run-m4"}))
    facade.create_work_unit(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-m4", "input_version_refs": ["summary-m4-v1"]}))
    facade.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-m4", "attempt_id": "attempt-m4"}))
    facade.commit_decision_surface_bundle(_command("COMMIT_DECISION_SURFACE_BUNDLE", {"work_unit_id": "wu-m4", "attempt_id": "attempt-m4", "artifact_id": "artifact-m4", "bundle": _bundle()}, expected=1))
    comparison_time = datetime.now(timezone.utc)
    comparison = ShadowComparisonRecord(tenant_id="tenant-m4-fixture", project_id="project-m4-fixture", case_id="case-m4-fixture", created_at=comparison_time, recorded_at=comparison_time, actor_snapshot_ref="comparison-m4-fixture", permission_snapshot_ref="permission-m4-fixture", correlation_id="comparison-m4-fixture", current_status="shadow_compared", comparison_id="comparison-m4-fixture", comparison_version=1, legacy_plan_ref="legacy-task-m4", canonical_contract_version_id="contract-m4-fixture:v1", rubric_version="m3-fixture-v1", summary_metrics={"semantic_coverage": 1.0}, details_artifact_ref="artifact-m4:v1")
    with store.transaction() as tx:
        tx.insert("canonical_shadow_comparisons", comparison.comparison_id, comparison.comparison_version, comparison.model_dump(mode="json"))
    service = PlanningLaneCutoverService(store, flags, LaneEligibilityPolicy(policy_ref="point01_m4_case_scoped_cutover_policy_v1_0"), grants={"point01.cutover.execute"})
    return store, facade, service


def _request(store: SQLiteCanonicalStore, now: datetime) -> LaneCutoverRequest:
    scope = CutoverScope(tenant_id="tenant-m4-fixture", project_id="project-m4-fixture", case_id="case-m4-fixture", lane_id="planning")
    contract = next(row for row in store.list_latest("canonical_decision_surface_contract_versions", case_id=scope.case_id) if row["contract_version_id"] == "contract-m4-fixture:v1")
    artifact = next(row for row in store.list_latest("canonical_artifact_versions", case_id=scope.case_id) if row["artifact_version_id"] == "artifact-m4:v1")
    comparison = next(row for row in store.list_latest("canonical_shadow_comparisons", case_id=scope.case_id) if row["comparison_id"] == "comparison-m4-fixture")
    values = ("schema-m4", "policy-m4", store.store_identity(), contract["contract_version_id"], canonical_digest(contract), artifact["artifact_version_id"], artifact["object_digest"], comparison["comparison_id"], canonical_digest(comparison))
    receipt = CutoverApprovalReceipt(approval_id="fixture-hil-m4", approval_registry_ref="fixture-hil-registry-m4", status="approved", approver_type="fixture_human", schema_digest=values[0], policy_digest=values[1], store_identity=values[2], contract_version_id=values[3], contract_digest=values[4], artifact_version_id=values[5], artifact_digest=values[6], comparison_id=values[7], comparison_digest=values[8], issued_at=now - timedelta(minutes=1), expires_at=now + timedelta(minutes=5))
    return LaneCutoverRequest(cutover_id="cutover-m4-fixture", scope=scope, expected_authority_version=1, schema_digest=values[0], policy_digest=values[1], store_identity=values[2], contract_version_id=values[3], contract_digest=values[4], artifact_version_id=values[5], artifact_digest=values[6], comparison_id=values[7], comparison_digest=values[8], approval=receipt, gate_evidence_refs=values)


def build_results(*, work_root: Path | None = None) -> dict[str, Any]:
    root = work_root or Path(tempfile.mkdtemp(prefix="point01_m4_fixture_"))
    root.mkdir(parents=True, exist_ok=True)
    store, facade, service = _runtime(root)
    now = datetime.now(timezone.utc)
    request = _request(store, now)
    eligible = service.evaluate_eligibility(request.scope, consumer_inventory_complete=True, legacy_projection_ready=True)
    ineligible = service.evaluate_eligibility(request.scope, consumer_inventory_complete=False, legacy_projection_ready=True)
    ineligible_denied = ineligible.status == "ineligible"
    requested = service.request_cutover(request, eligible, actor_snapshot_ref="m4-cutover-actor", permission_snapshot_ref="m4-cutover-permission", correlation_id="m4-cutover-correlation", now=now)
    stale_denied = False
    try:
        stale = request.model_copy(update={"approval": request.approval.model_copy(update={"artifact_digest": "stale"})})
        service.request_cutover(stale, eligible, actor_snapshot_ref="m4-cutover-actor", permission_snapshot_ref="m4-cutover-permission", correlation_id="m4-cutover-correlation", now=now)
    except CutoverApprovalError:
        stale_denied = True
    executed = service.execute_cutover(request, actor_snapshot_ref="m4-cutover-actor", permission_snapshot_ref="m4-cutover-permission", correlation_id="m4-cutover-correlation", now=now)
    facade_authority_after_cutover = facade.get_case_execution_view(request.scope.case_id)["planning_authority"]
    mappings = (LegacyProjectionMapping(legacy_required_item_id="legacy_demand", canonical_cell_key="cell-m4-fixture", information_loss_tags=("semantic_projection",)),)
    read = service.get_read_model(request.scope, mappings=mappings)
    workbench = service.workbench_projection(request.scope, mappings=mappings)
    pre_rollback_recovery = service.recover_cutover(request.scope)
    isolation_denied = False
    try:
        service.get_read_model(request.scope.model_copy(update={"tenant_id": "wrong-tenant"}))
    except PlanningCutoverError:
        isolation_denied = True
    postgres = json.loads((ROOT / "data/manifests/point01_m1_postgresql_conformance_sample_result_v1_0.json").read_text(encoding="utf-8"))
    store.set_kill_switch(True)
    rolled_back = service.rollback_cutover(request, reason="fixture_kill_switch_rollback", actor_snapshot_ref="m4-cutover-actor", permission_snapshot_ref="m4-cutover-permission", correlation_id="m4-cutover-correlation", now=now)
    recovery = service.recover_cutover(request.scope)
    facade_authority_after_rollback = facade.get_case_execution_view(request.scope.case_id)["planning_authority"]
    return {
        "M4.1": {"status": "pass" if eligible.status == "eligible" and ineligible_denied else "fail", "eligible_scope": eligible.model_dump(mode="json"), "ineligible_lane_denied": ineligible_denied},
        "M4.2": {"status": "pass" if requested.current_status == "requested" and stale_denied else "fail", "request_status": requested.current_status, "stale_approval_denied": stale_denied},
        "M4.3": {"status": "pass" if read.authority == "canonical_for_lane" and facade_authority_after_cutover == "canonical_for_lane" and read.legacy_projection and read.legacy_projection.read_only else "fail", "authority": read.authority, "runtime_facade_authority": facade_authority_after_cutover, "legacy_projection_read_only": bool(read.legacy_projection and read.legacy_projection.read_only)},
        "M4.4": {"status": "pass" if executed.current_status == "executed" and pre_rollback_recovery.status == "pass" else "fail", "decision_status": executed.current_status, "recovery": pre_rollback_recovery.model_dump(mode="json")},
        "M4.5": {"status": "pass" if workbench.authority_label == "canonical_for_lane" and workbench.read_only else "fail", "authority_label": workbench.authority_label, "cell_count": len(workbench.cells), "slot_count": len(workbench.slots), "gap_count": len(workbench.gaps)},
        "M4.6": {"status": "pass" if rolled_back.current_status == "rolled_back" and recovery.status == "pass" and recovery.authority == "legacy" and facade_authority_after_rollback == "legacy" else "fail", "rollback_status": rolled_back.current_status, "runtime_facade_authority": facade_authority_after_rollback, "recovery": recovery.model_dump(mode="json")},
        "M4.7": {"status": "pass" if isolation_denied and postgres.get("status") == "pass" and recovery.store_recovery_status == "pass" else "fail", "tenant_isolation_denied": isolation_denied, "postgresql_conformance_status": postgres.get("status"), "backup_recovery_status": recovery.store_recovery_status},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic Point 01 M4.1-M4.7 cutover fixtures.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--work-root", type=Path)
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    work_root = args.work_root if args.work_root is None or args.work_root.is_absolute() else ROOT / args.work_root
    results = build_results(work_root=work_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs: dict[str, str] = {}
    for point_id, payload in results.items():
        document = {"result_version": f"finsight_point01_{point_id.lower().replace('.', '_')}_fixture_result_v1_0", "generated_at": datetime.now(timezone.utc).isoformat(), "point_id": point_id, "status": "pass" if payload["status"] == "pass" else "fail_closed", "payload": payload, "legacy_task_run_authority": "authoritative", "canonical_lane_scope": "case_scoped_fixture_only", "model_call_count": 0, "external_call_count": 0, "boundary": "Deterministic temporary-store M4 cutover fixture; no production lane, Evidence/Writer/provider/full-chain runtime, or legacy TaskRun authority change."}
        path = output_dir / f"point01_{point_id.lower().replace('.', '_')}_fixture_result_v1_0.json"
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        outputs[point_id] = str(path)
    aggregate = {"result_version": "finsight_point01_m4_cutover_fixture_result_v1_0", "generated_at": datetime.now(timezone.utc).isoformat(), "status": "pass" if all(payload["status"] == "pass" for payload in results.values()) else "fail_closed", "point_statuses": {point: payload["status"] for point, payload in results.items()}, "outputs": outputs, "legacy_task_run_authority": "authoritative", "canonical_lane_scope": "case_scoped_fixture_only", "model_call_count": 0, "external_call_count": 0}
    aggregate_path = output_dir / "point01_m4_cutover_fixture_result_v1_0.json"
    aggregate_path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": aggregate["status"], "output": str(aggregate_path), "point_statuses": aggregate["point_statuses"]}, ensure_ascii=False))
    return 0 if aggregate["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
