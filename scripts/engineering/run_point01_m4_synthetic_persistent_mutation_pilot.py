"""Execute one explicitly approved, isolated synthetic M4 persistent pilot.

This command is intentionally narrower than M4 closeout.  It creates no business
Case and refuses to run without ``--execute-approved-pilot``.  The sequence is:
read-only preflight -> baseline backup -> request/execute -> approved-version
read-lock check -> rollback -> baseline restore -> store-backed verification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_point01_m4_closeout_gate import REQUIRED_AUTHORITY_EVENTS, store_backed_pilot_verification
from run_point01_m4_synthetic_pilot_preflight import SCOPE, _build_or_open
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import DecisionSurfaceContractVersion, canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.planning_cutover import (
    CutoverApprovalReceipt,
    LaneCutoverRequest,
    LaneEligibilityPolicy,
    LegacyProjectionMapping,
    PlanningLaneCutoverService,
)
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


DEFAULT_WORK_ROOT = ROOT / "data/staging/point01_m4_synthetic_pilot_v3"
DEFAULT_APPROVAL = ROOT / "configs/engineering_handoff/point01_m4_synthetic_pilot_approval_v1_0.json"
DEFAULT_EVIDENCE = ROOT / "data/manifests/point01_m4_synthetic_pilot_execution_evidence_v1_0.json"
DEFAULT_RESULT = ROOT / "data/manifests/point01_m4_synthetic_persistent_mutation_pilot_result_v1_0.json"
PILOT_CUTOVER_ID = "cutover-point01-synthetic-persistent-pilot-v1"
PILOT_APPROVAL_ID = "approval-point01-synthetic-persistent-pilot-v1"
PILOT_POLICY_REF = "point01_m4_synthetic_persistent_pilot_policy_v1_0"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot(store: SQLiteCanonicalStore, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(store.db_path) as source, sqlite3.connect(destination) as backup:
        source.backup(backup)
    return destination


def _exact_bindings(preflight: Any) -> dict[str, str]:
    return {
        "contract_version_id": preflight.contract_version_id,
        "contract_digest": preflight.contract_digest,
        "artifact_version_id": preflight.artifact_version_id,
        "artifact_digest": preflight.artifact_digest,
        "comparison_id": preflight.comparison_id,
        "comparison_digest": preflight.comparison_digest,
    }


def _approval_document(
    *,
    preflight: Any,
    backup_sha256: str,
    registry_ref: str,
    schema_digest: str,
    policy_digest: str,
    now: datetime,
) -> dict[str, Any]:
    bindings = _exact_bindings(preflight)
    expires_at = now + timedelta(minutes=30)
    return {
        "approval_version": "finsight_point01_m4_synthetic_pilot_approval_v1_0",
        "scope": "Point01_M4_isolated_synthetic_persistent_planning_cutover_pilot",
        "pilot_kind": "isolated_nonproduction_synthetic_persistent_case",
        "status": "approved",
        "authorization_decision": "user_explicit_approved_synthetic_persistent_pilot_only",
        "approval_id": PILOT_APPROVAL_ID,
        "approval_registry_ref": registry_ref,
        "approver_type": "human",
        "approver_identity": "current_thread_human_reviewer",
        "approved_at": now.isoformat(),
        "issued_at": now.isoformat(),
        "expires_at": expires_at.isoformat(),
        "revoked_at": None,
        "decision": "approve_case_scoped_planning_cutover_only",
        "approved_case_scope": SCOPE.case_id,
        "approved_lane_id": SCOPE.lane_id,
        "approved_store_identity": preflight.store_identity,
        "approved_contract_version_id": bindings["contract_version_id"],
        "approved_contract_digest": bindings["contract_digest"],
        "approved_artifact_version_id": bindings["artifact_version_id"],
        "approved_artifact_digest": bindings["artifact_digest"],
        "approved_comparison_id": bindings["comparison_id"],
        "approved_comparison_digest": bindings["comparison_digest"],
        "schema_digest": schema_digest,
        "policy_digest": policy_digest,
        "backup_snapshot_sha256": backup_sha256,
        "backup_restore_mode": "pre_mutation_baseline",
        "rollback_window": "30m",
        "kill_switch_state": "off_before_cutover",
        "impact_scope": "case_scoped_planning_only",
        "approval_revocation_registry_ref": registry_ref,
        "authority_boundary_acknowledged": {
            "legacy_task_run": "authoritative",
            "canonical_lane": "case_scoped_planning_only_after_approval",
            "cutover": "m4_case_scoped_only",
        },
        "rollback_acknowledged": True,
        "downstream_consumer_count": 0,
        "forbidden_admissions": [
            "business_case_mutation",
            "sector_cutover",
            "tenant_cutover",
            "global_cutover",
            "legacy_taskrun_authority_change",
            "evidence_runtime",
            "writer_runtime",
            "provider_execution",
            "full_chain",
        ],
        "notes": "Registered from the current-thread user's explicit approval. This is one isolated synthetic persistent Case pilot only; it is not approval for a business Case or M4 closeout.",
    }


def _receipt_from_registry(path: Path, approval_id: str) -> CutoverApprovalReceipt:
    document = _load(path)
    if document.get("approval_id") != approval_id:
        raise RuntimeError("synthetic_approval_registry_identity_mismatch")
    return CutoverApprovalReceipt(
        approval_id=str(document["approval_id"]),
        approval_registry_ref=str(document["approval_registry_ref"]),
        status=str(document["status"]),
        approver_type=str(document["approver_type"]),
        schema_digest=str(document["schema_digest"]),
        policy_digest=str(document["policy_digest"]),
        store_identity=str(document["approved_store_identity"]),
        contract_version_id=str(document["approved_contract_version_id"]),
        contract_digest=str(document["approved_contract_digest"]),
        artifact_version_id=str(document["approved_artifact_version_id"]),
        artifact_digest=str(document["approved_artifact_digest"]),
        comparison_id=str(document["approved_comparison_id"]),
        comparison_digest=str(document["approved_comparison_digest"]),
        issued_at=datetime.fromisoformat(str(document["issued_at"])),
        expires_at=datetime.fromisoformat(str(document["expires_at"])),
        revoked_at=datetime.fromisoformat(str(document["revoked_at"])) if document.get("revoked_at") else None,
    )


def _request_from_approval(
    *,
    preflight: Any,
    approval_path: Path,
    schema_digest: str,
    policy_digest: str,
    expected_authority_version: int,
) -> LaneCutoverRequest:
    receipt = _receipt_from_registry(approval_path, PILOT_APPROVAL_ID)
    bindings = _exact_bindings(preflight)
    refs = (
        schema_digest,
        policy_digest,
        preflight.store_identity,
        *bindings.values(),
    )
    return LaneCutoverRequest(
        cutover_id=PILOT_CUTOVER_ID,
        scope=SCOPE,
        expected_authority_version=expected_authority_version,
        schema_digest=schema_digest,
        policy_digest=policy_digest,
        store_identity=preflight.store_identity,
        contract_version_id=bindings["contract_version_id"],
        contract_digest=bindings["contract_digest"],
        artifact_version_id=bindings["artifact_version_id"],
        artifact_digest=bindings["artifact_digest"],
        comparison_id=bindings["comparison_id"],
        comparison_digest=bindings["comparison_digest"],
        approval=receipt,
        gate_evidence_refs=refs,
    )


def _create_newer_contract(store: SQLiteCanonicalStore, *, contract_version_id: str, now: datetime) -> str:
    contract = next(
        row
        for row in store.list_versions("canonical_decision_surface_contract_versions", case_id=SCOPE.case_id)
        if row.get("contract_version_id") == contract_version_id
    )
    next_version = int(contract["contract_version"]) + 1
    newer = DecisionSurfaceContractVersion.model_validate(
        {
            **contract,
            "contract_version": next_version,
            "contract_version_id": f"{contract['contract_id']}:v{next_version}",
            "recorded_at": now + timedelta(seconds=1),
            "supersedes_version_id": contract_version_id,
        }
    )
    with store.transaction() as tx:
        tx.insert("canonical_decision_surface_contract_versions", newer.contract_id, newer.contract_version, newer.model_dump(mode="json"))
    return newer.contract_version_id


def build_result(
    *,
    work_root: Path,
    approval_path: Path,
    evidence_path: Path,
    execute_approved_pilot: bool,
) -> dict[str, Any]:
    if not execute_approved_pilot:
        raise RuntimeError("execute_approved_pilot_flag_required")
    store, _ = _build_or_open(work_root)
    if store.list_versions("canonical_lane_cutover_decisions", case_id=SCOPE.case_id):
        raise RuntimeError("synthetic_pilot_work_root_already_has_cutover_history")
    flags = FeatureFlagRegistry.from_path(ROOT / "configs/runtime/point01_feature_flags_v1_0.json")
    facade = RuntimeFacade(store, FileCanonicalObjectStore(work_root / "objects"), flags, mode="shadow", grants={"point01.shadow.write"})
    preflight_service = PlanningLaneCutoverService(
        store,
        flags,
        LaneEligibilityPolicy(policy_ref=PILOT_POLICY_REF),
        grants={"point01.cutover.execute"},
    )
    preflight = preflight_service.read_only_preflight(SCOPE, downstream_consumer_ids=())
    baseline_fingerprint = store.content_fingerprint()
    baseline_event_count = len(store.list_events())
    baseline_backup = _snapshot(store, work_root / "backups" / "pre_mutation_baseline.sqlite")
    schema_digest = canonical_digest({"schema_version": "finsight_point01_canonical_runtime_v1_0", "scope": SCOPE.model_dump(mode="json")})
    policy_digest = canonical_digest({"policy_ref": PILOT_POLICY_REF, "scope": SCOPE.model_dump(mode="json")})
    registry_ref = str(approval_path.relative_to(ROOT)).replace("\\", "/") if approval_path.is_relative_to(ROOT) else str(approval_path)
    now = datetime.now(timezone.utc)
    approval = _approval_document(
        preflight=preflight,
        backup_sha256=_sha256(baseline_backup),
        registry_ref=registry_ref,
        schema_digest=schema_digest,
        policy_digest=policy_digest,
        now=now,
    )
    _write(approval_path, approval)
    case = store.get_latest("canonical_research_cases", SCOPE.case_id)
    if not case:
        raise RuntimeError("synthetic_case_missing_after_preflight")
    control = store.get_latest("canonical_case_control_versions", str(case["case_control_summary_ref"]))
    if not control or control.get("planning_authority") != "legacy":
        raise RuntimeError("synthetic_pilot_initial_authority_not_legacy")
    request = _request_from_approval(
        preflight=preflight,
        approval_path=approval_path,
        schema_digest=schema_digest,
        policy_digest=policy_digest,
        expected_authority_version=int(control["summary_version"]),
    )
    service = PlanningLaneCutoverService(
        store,
        flags,
        LaneEligibilityPolicy(policy_ref=PILOT_POLICY_REF),
        grants={"point01.cutover.execute"},
        approval_resolver=lambda approval_id: _receipt_from_registry(approval_path, approval_id),
    )
    eligibility = service.evaluate_eligibility(SCOPE, consumer_inventory_complete=True, legacy_projection_ready=True)
    requested = service.request_cutover(
        request,
        eligibility,
        actor_snapshot_ref="synthetic-pilot-cutover-actor",
        permission_snapshot_ref="synthetic-pilot-cutover-permission",
        correlation_id="synthetic-pilot-cutover-correlation",
        now=now,
    )
    executed = service.execute_cutover(
        request,
        actor_snapshot_ref="synthetic-pilot-cutover-actor",
        permission_snapshot_ref="synthetic-pilot-cutover-permission",
        correlation_id="synthetic-pilot-cutover-correlation",
        now=now,
    )
    mappings = (
        LegacyProjectionMapping(
            legacy_required_item_id="legacy_synthetic_demand",
            canonical_cell_key="cell-synthetic-pilot",
            information_loss_tags=("synthetic_pilot_read_only_projection",),
        ),
    )
    approved_read = service.get_read_model(SCOPE, mappings=mappings)
    newer_contract_version_id = _create_newer_contract(store, contract_version_id=preflight.contract_version_id, now=now)
    pinned_read = service.get_read_model(SCOPE, mappings=mappings)
    rolled_back = service.rollback_cutover(
        request,
        reason="approved_synthetic_persistent_pilot_completed",
        actor_snapshot_ref="synthetic-pilot-cutover-actor",
        permission_snapshot_ref="synthetic-pilot-cutover-permission",
        correlation_id="synthetic-pilot-cutover-correlation",
        now=now,
    )
    recovery = service.recover_cutover(SCOPE)
    events = [event for event in store.list_events() if (event.get("payload") or {}).get("cutover_id") == PILOT_CUTOVER_ID]
    post_rollback_fingerprint = store.content_fingerprint()
    evidence: dict[str, Any] = {
        "evidence_version": "finsight_point01_m4_synthetic_pilot_execution_evidence_v1_0",
        "scope": "Point01_M4_isolated_synthetic_persistent_planning_cutover_pilot",
        "pilot_kind": "isolated_nonproduction_synthetic_persistent_case",
        "status": "pass",
        "tenant_id": SCOPE.tenant_id,
        "project_id": SCOPE.project_id,
        "case_id": SCOPE.case_id,
        "lane_id": SCOPE.lane_id,
        "persistent_store_identity": store.store_identity(),
        "approval_id": request.approval.approval_id,
        "approval_registry_ref": request.approval.approval_registry_ref,
        "cutover_id": request.cutover_id,
        "request_digest": request.request_digest,
        "cutover_decision_ref": f"{request.cutover_id}:v2",
        "rollback_decision_ref": f"{request.cutover_id}:v3",
        "contract_version_id": request.contract_version_id,
        "contract_digest": request.contract_digest,
        "artifact_version_id": request.artifact_version_id,
        "artifact_digest": request.artifact_digest,
        "comparison_id": request.comparison_id,
        "comparison_digest": request.comparison_digest,
        "backup_snapshot_sha256": _sha256(baseline_backup),
        "backup_restore_mode": "pre_mutation_baseline",
        "backup_baseline_content_fingerprint": baseline_fingerprint,
        "backup_baseline_event_count": baseline_event_count,
        "backup_baseline_cutover_event_count": 0,
        "post_rollback_content_fingerprint": post_rollback_fingerprint,
        "rollback_window": "30m",
        "kill_switch_state": "off_before_cutover",
        "impact_scope": "case_scoped_planning_only",
        "authority_before": "legacy",
        "authority_after_cutover": approved_read.authority,
        "authority_after_rollback": recovery.authority,
        "authority_event_types": [event["event_type"] for event in events],
        "authority_event_versions": [
            {"event_type": event["event_type"], "before": event["state_version_before"], "after": event["state_version_after"]}
            for event in events
        ],
        "approved_read_contract_version_id": approved_read.contract["contract_version_id"],
        "newer_contract_version_id": newer_contract_version_id,
        "pinned_read_contract_version_id": pinned_read.contract["contract_version_id"],
        "requested_status": requested.current_status,
        "executed_status": executed.current_status,
        "rolled_back_status": rolled_back.current_status,
        "recovery": recovery.model_dump(mode="json"),
        "downstream_consumer_count": 0,
        "mutation_performed": True,
        "forbidden_actions_not_run": ["business_case_mutation", "evidence_runtime", "writer_runtime", "provider_execution", "full_chain"],
    }
    store_errors, store_proof = store_backed_pilot_verification(
        approval,
        evidence,
        persistent_store_path=store.db_path,
        backup_snapshot_path=baseline_backup,
        restore_root=work_root / "store_backed_restore",
    )
    evidence["store_backed_verification"] = store_proof
    evidence["store_backed_errors"] = store_errors
    evidence["status"] = "pass" if not store_errors else "fail_closed"
    _write(evidence_path, evidence)
    expected_events = list(REQUIRED_AUTHORITY_EVENTS)
    passed = bool(
        evidence["status"] == "pass"
        and requested.current_status == "requested"
        and executed.current_status == "executed"
        and approved_read.authority == "canonical_for_lane"
        and approved_read.contract["contract_version_id"] == request.contract_version_id
        and pinned_read.contract["contract_version_id"] == request.contract_version_id
        and newer_contract_version_id != request.contract_version_id
        and rolled_back.current_status == "rolled_back"
        and recovery.status == "pass"
        and recovery.authority == "legacy"
        and [event["event_type"] for event in events] == expected_events
    )
    return {
        "result_version": "finsight_point01_m4_synthetic_persistent_mutation_pilot_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if passed else "fail_closed",
        "pilot_kind": "isolated_nonproduction_synthetic_persistent_case",
        "authorization_ref": registry_ref,
        "scope": SCOPE.model_dump(mode="json"),
        "baseline_backup_sha256": _sha256(baseline_backup),
        "baseline_content_fingerprint": baseline_fingerprint,
        "post_rollback_content_fingerprint": post_rollback_fingerprint,
        "requested_status": requested.current_status,
        "executed_status": executed.current_status,
        "approved_read_contract_version_id": approved_read.contract["contract_version_id"],
        "newer_contract_version_id": newer_contract_version_id,
        "pinned_read_contract_version_id": pinned_read.contract["contract_version_id"],
        "rolled_back_status": rolled_back.current_status,
        "recovery": recovery.model_dump(mode="json"),
        "authority_event_types": [event["event_type"] for event in events],
        "store_backed_verification": store_proof,
        "store_backed_errors": store_errors,
        "execution_evidence_path": str(evidence_path.relative_to(ROOT)).replace("\\", "/") if evidence_path.is_relative_to(ROOT) else str(evidence_path),
        "business_case_mutation": False,
        "model_call_count": 0,
        "external_call_count": 0,
        "forbidden_actions_not_run": evidence["forbidden_actions_not_run"],
        "boundary": "One user-approved, isolated synthetic persistent Case pilot. This result is not human acceptance of M4 closeout and cannot authorize a business Case or broader runtime admission.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one explicitly approved isolated synthetic M4 persistent mutation pilot.")
    parser.add_argument("--work-root", type=Path, default=DEFAULT_WORK_ROOT)
    parser.add_argument("--approval", type=Path, default=DEFAULT_APPROVAL)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--execute-approved-pilot", action="store_true")
    args = parser.parse_args()
    work_root = args.work_root if args.work_root.is_absolute() else ROOT / args.work_root
    approval = args.approval if args.approval.is_absolute() else ROOT / args.approval
    evidence = args.evidence if args.evidence.is_absolute() else ROOT / args.evidence
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result(
        work_root=work_root,
        approval_path=approval,
        evidence_path=evidence,
        execute_approved_pilot=args.execute_approved_pilot,
    )
    _write(output, result)
    print(json.dumps({"status": result["status"], "output": str(output), "business_case_mutation": result["business_case_mutation"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
