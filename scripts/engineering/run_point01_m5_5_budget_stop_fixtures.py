from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.budget_control import BudgetControlService, BudgetExceededError, BudgetPolicy, BudgetReservationRequest
from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import IllegalStateTransition, RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.recovery_lifecycle import RecoveryLifecycleService
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


DEFAULT_POLICY = ROOT / "configs/engineering_handoff/point01_m5_5_budget_stop_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m5_5_budget_stop_fixture_result_v1_0.json"
NOW = datetime(2026, 7, 12, 15, 45, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry({"default_deny": True, "flags": [{"flag_id": "decision_surface_shadow_v0_1", "default_mode": "off", "allowed_modes": ["off", "shadow"], "required_capability_grants": ["point01.shadow.write"], "allowed_consumers": ["point01_shadow_compiler"], "forbidden_consumers": ["memo_writer", "evidence_runtime"]}]})


def _command(command_type: str, payload: dict[str, Any], *, idem: str, expected: int = 0, at: datetime = NOW) -> CommandEnvelope:
    return CommandEnvelope(command_id=f"cmd-{idem}", command_type=command_type, tenant_id="tenant-m5-5-fixture", project_id="project-m5-5-fixture", case_id="case-m5-5-fixture", actor_snapshot_ref="actor-m5-5-fixture", permission_snapshot_ref="permission-m5-5-fixture", policy_config_refs=("policy-m5-5",), idempotency_key=idem, expected_state_version=expected, correlation_id="correlation-m5-5-fixture", requested_at=at, payload=payload)


def _reservation(reservation_id: str, *, tokens: int, tools: int = 0, seconds: int = 1, fallback: bool = False) -> BudgetReservationRequest:
    return BudgetReservationRequest(reservation_id=reservation_id, work_unit_id="wu-budget", attempt_id="attempt-budget-1", token_units=tokens, tool_calls=tools, time_seconds=seconds, is_fallback=fallback)


def build_result(policy: dict[str, Any], *, policy_path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    errors: list[str] = []
    if policy.get("policy_version") != "finsight_point01_m5_5_budget_stop_policy_v1_0":
        errors.append("policy_identity_invalid")
    if policy.get("status") != "approved_for_deterministic_implementation":
        errors.append("policy_status_invalid")
    with TemporaryDirectory(prefix="point01_m5_5_budget_") as directory:
        root = Path(directory)
        facade = RuntimeFacade(SQLiteCanonicalStore(root / "canonical.sqlite"), FileCanonicalObjectStore(root / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
        scheduler = DurableSchedulerService(facade)
        facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.5 fixture", "accountable_owner_ref": "lead-m5-5"}, idem="case"))
        scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-budget", "input_version_refs": ["summary-v1"], "queue_name": "budget-shadow", "max_attempts": 2, "retry_budget": 1, "retry_policy_ref": "retry:bounded", "retryable_failure_types": ["transient"]}, idem="enqueue"))
        scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "budget-shadow", "work_unit_id": "wu-budget", "worker_ref": "worker-budget", "attempt_id": "attempt-budget-1", "lease_duration_seconds": 60}, idem="claim"))
        budget_policy = BudgetPolicy(policy_id="budget-fixture", case_token_units=10, work_unit_token_units=10, attempt_token_units=10, case_tool_calls=2, work_unit_tool_calls=2, attempt_tool_calls=2, case_time_seconds=10, work_unit_time_seconds=10, attempt_time_seconds=10)
        budgets = BudgetControlService(facade, policy=budget_policy)
        checkpoint = budgets.execute_checkpoint_write(_command("CREATE_CHECKPOINT_VERSION", {"work_unit_id": "wu-budget", "attempt_id": "attempt-budget-1", "worker_ref": "worker-budget", "lease_fencing_token": 1, "checkpoint_id": "checkpoint-budget", "expected_checkpoint_version": 0, "supersedes_version_id": None, "checkpoint_schema_ref": "checkpoint-schema-v1", "snapshot": {"cursor": "budget"}}, expected=1, idem="checkpoint", at=NOW + timedelta(seconds=1)), _reservation("checkpoint-reservation", tokens=4, tools=1, seconds=4))
        budgets.reserve(_reservation("primary", tokens=4, tools=1, seconds=4))
        fallback_blocked = False
        try:
            budgets.reserve(_reservation("fallback", tokens=3, tools=1, seconds=3, fallback=True))
        except BudgetExceededError:
            fallback_blocked = True
        budgets.refund("primary", token_units=2, tool_calls=1, time_seconds=2, reason="unused_tail")
        restarted = RuntimeFacade(SQLiteCanonicalStore(root / "canonical.sqlite"), FileCanonicalObjectStore(root / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
        recovered_ledger = BudgetControlService(restarted, policy=budget_policy).ledger_view()
        ledger_survives_restart = [entry["action"] for entry in recovered_ledger["ledger"]] == ["reserved", "consumed", "reserved", "terminal_stop", "refunded"]
        stopper = BudgetControlService(facade, policy=BudgetPolicy(policy_id="stopper", case_token_units=1, work_unit_token_units=1, attempt_token_units=1, case_tool_calls=1, work_unit_tool_calls=1, attempt_tool_calls=1, case_time_seconds=10, work_unit_time_seconds=10, attempt_time_seconds=10))
        terminal_stop_applied = False
        try:
            stopper.reserve(_reservation("over-budget", tokens=2))
        except BudgetExceededError as exc:
            stopper.apply_terminal_stop(_command("BUDGET_STOP", {"work_unit_id": "wu-budget", "attempt_id": "attempt-budget-1", "worker_ref": "worker-budget", "lease_fencing_token": 1}, expected=1, idem="terminal-stop", at=NOW + timedelta(seconds=2)), exc)
            terminal_stop_applied = True
        retry_blocked = False
        try:
            RecoveryLifecycleService(facade, scheduler=scheduler).retry(_command("RECOVERY_RETRY", {"work_unit_id": "wu-budget", "queue_name": "budget-shadow", "worker_ref": "worker-retry"}, expected=2, idem="retry"))
        except IllegalStateTransition:
            retry_blocked = True
        ledger = budgets.ledger_view()
        if checkpoint.artifact_refs != ("checkpoint-budget:v1",):
            errors.append("reservation_before_admission_failed")
        if not fallback_blocked:
            errors.append("fallback_overrun_not_blocked")
        if ledger["slo_observation"]["refund_count"] != 1:
            errors.append("refund_not_traceable")
        if not ledger_survives_restart:
            errors.append("budget_ledger_not_recovered_after_restart")
        if not terminal_stop_applied or not retry_blocked or facade.store.get_latest("canonical_work_units", "wu-budget")["state"] != "failed":
            errors.append("terminal_stop_did_not_prevent_retry")
        evidence = {"checkpoint_ref": list(checkpoint.artifact_refs), "fallback_blocked": fallback_blocked, "refund_count": ledger["slo_observation"]["refund_count"], "budget_ledger_survives_restart": ledger_survives_restart, "terminal_stop_applied": terminal_stop_applied, "retry_blocked": retry_blocked, "work_unit_state": facade.store.get_latest("canonical_work_units", "wu-budget")["state"], "budget_ledger_actions": [entry["action"] for entry in ledger["ledger"]]}
    return {"result_version": "finsight_point01_m5_5_budget_stop_fixture_result_v1_0", "generated_at": datetime.now(timezone.utc).isoformat(), "scope": "Point01_M5_5_budget_stop_control_plane_only", "status": "pass" if not errors else "fail_closed", "errors": errors, "evidence": evidence, "worker_started": False, "model_call_count": 0, "external_call_count": 0, "fixed_input_sha256": {str(policy_path.relative_to(ROOT)).replace("\\", "/"): _sha256(policy_path), "scripts/engineering/run_point01_m5_5_budget_stop_fixtures.py": _sha256(Path(__file__).resolve()), "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md")}, "boundary": "This fixture proves deterministic M5.5 reservation/refund/typed stop only. It executes no provider or external tool, starts no worker/service, and admits no paid model, Evidence/Writer, full-chain, business Case mutation or legacy authority change."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M5.5 budget/stop fixtures.")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    policy_path = args.policy if args.policy.is_absolute() else ROOT / args.policy
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result(json.loads(policy_path.read_text(encoding="utf-8")), policy_path=policy_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output_path), "errors": result["errors"]}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
