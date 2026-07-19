from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.budget_control import BudgetControlService, BudgetPolicy, BudgetReservationRequest
from sec_agent.canonical_runtime.facade import LeaseValidationError, RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope, canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore

DEFAULT_POLICY = ROOT / "configs/engineering_handoff/point01_m5_calibration_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m5_calibration_result_v1_0.json"
NOW = datetime(2026, 7, 13, 9, 0, tzinfo=timezone.utc)
CASE_ID = "case-m5-calibration"
WORK_UNIT_ID = "wu-calibration"
ATTEMPT_ID = "attempt-calibration-1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry({"default_deny": True, "flags": [{"flag_id": "decision_surface_shadow_v0_1", "default_mode": "off", "allowed_modes": ["off", "shadow"], "required_capability_grants": ["point01.shadow.write"], "allowed_consumers": ["point01_shadow_compiler"], "forbidden_consumers": ["memo_writer", "evidence_runtime"]}]})


def _command(kind: str, payload: dict[str, Any], *, idem: str, expected: int = 0, at: datetime = NOW) -> CommandEnvelope:
    return CommandEnvelope(command_id=f"cmd-{idem}", command_type=kind, tenant_id="tenant-m5-calibration", project_id="project-m5-calibration", case_id=CASE_ID, actor_snapshot_ref="actor-m5-calibration", permission_snapshot_ref="permission-m5-calibration", policy_config_refs=("policy-m5-calibration",), idempotency_key=idem, expected_state_version=expected, correlation_id="correlation-m5-calibration", requested_at=at, payload=payload)


def _facade(root: Path) -> RuntimeFacade:
    return RuntimeFacade(SQLiteCanonicalStore(root / "canonical.sqlite"), FileCanonicalObjectStore(root / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})


def _bootstrap(root: Path) -> None:
    facade = _facade(root)
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5 local calibration fixture", "accountable_owner_ref": "lead-m5-calibration"}, idem="case"))
    DurableSchedulerService(facade).enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": WORK_UNIT_ID, "input_version_refs": ["summary-v1"], "queue_name": "calibration-shadow"}, idem="enqueue"))


def _child_claim_and_exit(root: Path) -> None:
    scheduler = DurableSchedulerService(_facade(root))
    scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "calibration-shadow", "work_unit_id": WORK_UNIT_ID, "worker_ref": "worker-a", "attempt_id": ATTEMPT_ID, "lease_duration_seconds": 1}, idem="claim-worker-a"))
    # Intentionally avoid Python cleanup to model an unexpected worker process death.
    os._exit(71)


def _child_reopen_and_reclaim(root: Path) -> None:
    facade = _facade(root)
    work_unit = facade.store.get_latest("canonical_work_units", WORK_UNIT_ID) or {}
    DurableSchedulerService(facade).reclaim_expired(_command("SCHEDULER_RECLAIM_EXPIRED_LEASE", {"work_unit_id": WORK_UNIT_ID, "attempt_id": ATTEMPT_ID, "worker_ref": "worker-b", "lease_duration_seconds": 30}, expected=int(work_unit.get("state_version", 0)), idem="reclaim-worker-b", at=NOW + timedelta(seconds=2)))


def _child_uncommitted_transaction_exit(root: Path) -> None:
    facade = _facade(root)
    probe = "calibration-uncommitted-crash-probe"
    with facade.store.transaction() as tx:
        row = {"tenant_id": "tenant-m5-calibration", "project_id": "project-m5-calibration", "case_id": CASE_ID, "reservation_id": probe, "reservation_version": 1, "state_version": 1, "request": {"probe": True}, "remaining_token_units": 1, "remaining_tool_calls": 0, "remaining_time_seconds": 0, "reservation_state": "reserved", "current_status": "reserved"}
        row["content_digest"] = canonical_digest(row)
        tx.insert("canonical_budget_reservation_versions", probe, 1, row)
        # This is deliberately inside an open SQLite transaction: reopening in
        # the orchestrator must prove no physical partial row survived.
        os._exit(73)


def _budget_checkpoint_command(*, expected: int) -> CommandEnvelope:
    return _command(
        "CREATE_CHECKPOINT_VERSION",
        {
            "work_unit_id": WORK_UNIT_ID,
            "attempt_id": ATTEMPT_ID,
            "worker_ref": "worker-b",
            "lease_fencing_token": 2,
            "checkpoint_id": "checkpoint-calibration-budget",
            "expected_checkpoint_version": 0,
            "supersedes_version_id": None,
            "checkpoint_schema_ref": "checkpoint-schema-v1",
            "snapshot": {"cursor": "budget-crash-recovery"},
        },
        expected=expected,
        idem="budget-crash-checkpoint",
        at=NOW + timedelta(seconds=4),
    )


def _child_commit_checkpoint_before_budget_consume_exit(root: Path) -> None:
    facade = _facade(root)
    work_unit = facade.store.get_latest("canonical_work_units", WORK_UNIT_ID) or {}
    # This deliberately models the legacy two-transaction crash point that the
    # current atomic finalizer removes: a checkpoint commits while a previously
    # durable reservation is still checkpoint_pending.
    facade.create_checkpoint_version(_budget_checkpoint_command(expected=int(work_unit.get("state_version", 0))))
    os._exit(74)


def _run_child(mode: str, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(Path(__file__).resolve()), mode, "--root", str(root)], cwd=ROOT, capture_output=True, text=True, check=False)


def build_result(policy: dict[str, Any], *, policy_path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    errors: list[str] = []
    if policy.get("policy_version") != "finsight_point01_m5_local_synthetic_calibration_policy_v1_0" or policy.get("status") != "approved_for_deterministic_implementation":
        errors.append("calibration_policy_invalid")
    with TemporaryDirectory(prefix="point01_m5_calibration_") as directory:
        root = Path(directory)
        _bootstrap(root)
        worker_a = _run_child("--child-claim-exit", root)
        reopened_facade = _facade(root)
        reopened_scheduler = DurableSchedulerService(reopened_facade)
        expired_view = reopened_scheduler.queue_view(case_id=CASE_ID, queue_name="calibration-shadow", observed_at=NOW + timedelta(seconds=2))
        worker_b = _run_child("--child-reopen-and-reclaim", root)
        recovered_facade = _facade(root)
        recovered_attempt = recovered_facade.store.get_latest("canonical_attempts", ATTEMPT_ID) or {}
        recovered_work_unit = recovered_facade.store.get_latest("canonical_work_units", WORK_UNIT_ID) or {}
        stale_fenced = False
        try:
            recovered_facade.complete_attempt(_command("COMPLETE_ATTEMPT", {"work_unit_id": WORK_UNIT_ID, "attempt_id": ATTEMPT_ID, "worker_ref": "worker-a", "lease_fencing_token": 1}, expected=int(recovered_work_unit.get("state_version", 0)), idem="stale-worker-a-complete", at=NOW + timedelta(seconds=3)))
        except LeaseValidationError:
            stale_fenced = True
        transaction_crash = _run_child("--child-uncommitted-transaction-exit", root)
        probe = "calibration-uncommitted-crash-probe"
        after_crash_facade = _facade(root)
        budget_policy = BudgetPolicy(policy_id="calibration-budget", case_token_units=20, work_unit_token_units=20, attempt_token_units=20, case_tool_calls=5, work_unit_tool_calls=5, attempt_tool_calls=5, case_time_seconds=120, work_unit_time_seconds=120, attempt_time_seconds=120)
        budget = BudgetControlService(after_crash_facade, policy=budget_policy)
        budget_command = _budget_checkpoint_command(expected=int((after_crash_facade.store.get_latest("canonical_work_units", WORK_UNIT_ID) or {}).get("state_version", 0)))
        budget.begin_checkpoint_operation(budget_command, BudgetReservationRequest(reservation_id="calibration-budget-pending", work_unit_id=WORK_UNIT_ID, attempt_id=ATTEMPT_ID, token_units=3, tool_calls=1, time_seconds=5))
        budget_crash = _run_child("--child-commit-checkpoint-before-budget-consume-exit", root)
        recovered_budget = BudgetControlService(_facade(root), policy=budget_policy)
        budget_reconciliation = recovered_budget.reconcile_pending_operation("calibration-budget-pending")
        recovered_reservation = recovered_budget.facade.store.get_latest("canonical_budget_reservation_versions", "calibration-budget-pending") or {}
        store_check = after_crash_facade.store.recovery_check()
        evidence = {
            "worker_a_process_started": worker_a.returncode == 71,
            "worker_a_exit_code": worker_a.returncode,
            "worker_loss_observed": expired_view["counts"]["lease_expired"] == 1,
            "worker_b_process_started": worker_b.returncode == 0,
            "worker_b_reclaimed": worker_b.returncode == 0 and recovered_attempt.get("lease_owner_ref") == "worker-b",
            "reclaimed_state_versions": [int(recovered_work_unit.get("state_version", 0)) - 1, recovered_work_unit.get("state_version")],
            "recovered_fencing_token": recovered_attempt.get("lease_fencing_token"),
            "stale_worker_fenced": stale_fenced,
            "transaction_crash_process_started": transaction_crash.returncode == 73,
            "transaction_crash_exit_code": transaction_crash.returncode,
            "partial_row_absent_after_process_crash": after_crash_facade.store.get_latest("canonical_budget_reservation_versions", probe) is None,
            "budget_crash_process_started": budget_crash.returncode == 74,
            "budget_crash_exit_code": budget_crash.returncode,
            "budget_artifact_committed_before_reconcile": recovered_budget.facade.store.get_latest("canonical_artifact_versions", "checkpoint-calibration-budget") is not None,
            "budget_reservation_reconciled_consumed": budget_reconciliation == "reconciled_consumed" and recovered_reservation.get("protected_operation_state") == "reconciled_consumed",
            "source_store_integrity": store_check,
        }
        if not all((evidence["worker_a_process_started"], evidence["worker_loss_observed"], evidence["worker_b_process_started"], evidence["worker_b_reclaimed"], evidence["recovered_fencing_token"] == 2, evidence["stale_worker_fenced"])):
            errors.append("real_worker_loss_restart_fencing_failed")
        if not evidence["transaction_crash_process_started"] or not evidence["partial_row_absent_after_process_crash"]:
            errors.append("real_transaction_atomicity_crash_drill_failed")
        if not all((evidence["budget_crash_process_started"], evidence["budget_artifact_committed_before_reconcile"], evidence["budget_reservation_reconciled_consumed"])):
            errors.append("budget_checkpoint_crash_reconciliation_failed")
        if store_check.get("status") != "pass":
            errors.append("post_crash_store_integrity_failed")
    return {"result_version": "finsight_point01_m5_local_synthetic_calibration_result_v1_1", "generated_at": datetime.now(timezone.utc).isoformat(), "scope": "Point01_M5_local_synthetic_real_child_process_restart_worker_loss_transaction_atomicity_only", "status": "pass" if not errors else "fail_closed", "errors": errors, "evidence": evidence, "worker_started": False, "model_call_count": 0, "external_call_count": 0, "fixed_input_sha256": {str(policy_path.relative_to(ROOT)).replace("\\", "/"): _sha256(policy_path), "scripts/engineering/run_point01_m5_calibration_drills.py": _sha256(Path(__file__).resolve()), "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md")}, "boundary": "This local synthetic calibration starts short-lived child processes only to prove SQLite reopen, lease reclaim/fencing and uncommitted-transaction crash atomicity. It starts no worker service and admits no provider, external tool, Evidence/Writer, full-chain, business Case mutation or legacy authority change."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M5 local synthetic real-process crash calibration.")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--child-claim-exit", action="store_true")
    parser.add_argument("--child-reopen-and-reclaim", action="store_true")
    parser.add_argument("--child-uncommitted-transaction-exit", action="store_true")
    parser.add_argument("--child-commit-checkpoint-before-budget-consume-exit", action="store_true")
    args = parser.parse_args()
    if args.child_claim_exit or args.child_reopen_and_reclaim or args.child_uncommitted_transaction_exit or args.child_commit_checkpoint_before_budget_consume_exit:
        if args.root is None:
            parser.error("--root is required for child process drills")
        if args.child_claim_exit:
            _child_claim_and_exit(args.root)
        elif args.child_reopen_and_reclaim:
            _child_reopen_and_reclaim(args.root)
        elif args.child_commit_checkpoint_before_budget_consume_exit:
            _child_commit_checkpoint_before_budget_consume_exit(args.root)
        else:
            _child_uncommitted_transaction_exit(args.root)
        return 0
    policy_path = args.policy if args.policy.is_absolute() else ROOT / args.policy
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result(json.loads(policy_path.read_text(encoding="utf-8")), policy_path=policy_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output_path), "errors": result["errors"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
