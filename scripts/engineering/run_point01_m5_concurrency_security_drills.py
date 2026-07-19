from __future__ import annotations

import argparse
import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.budget_control import BudgetControlService, BudgetExceededError, BudgetPolicy, BudgetReservationRequest
from sec_agent.canonical_runtime.capability_security import CapabilityGrant, CapabilitySecurityService, SandboxAdmissionRequest, ToolManifest
from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore

DEFAULT_POLICY = ROOT / "configs/engineering_handoff/point01_m5_concurrency_security_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m5_concurrency_security_result_v1_0.json"
NOW = datetime(2026, 7, 13, 9, 30, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry({"default_deny": True, "flags": [{"flag_id": "decision_surface_shadow_v0_1", "default_mode": "off", "allowed_modes": ["off", "shadow"], "required_capability_grants": ["point01.shadow.write"], "allowed_consumers": ["point01_shadow_compiler"], "forbidden_consumers": ["memo_writer", "evidence_runtime"]}]})


def _command(kind: str, payload: dict[str, Any], *, idem: str, expected: int = 0, at: datetime = NOW) -> CommandEnvelope:
    return CommandEnvelope(command_id=f"cmd-{idem}", command_type=kind, tenant_id="tenant-m5-concurrency", project_id="project-m5-concurrency", case_id="case-m5-concurrency", actor_snapshot_ref="actor-m5-concurrency", permission_snapshot_ref="permission-m5-concurrency", policy_config_refs=("policy-m5-concurrency",), idempotency_key=idem, expected_state_version=expected, correlation_id="correlation-m5-concurrency", requested_at=at, payload=payload)


def _runtime(root: Path) -> RuntimeFacade:
    facade = RuntimeFacade(SQLiteCanonicalStore(root / "canonical.sqlite"), FileCanonicalObjectStore(root / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5 concurrency security fixture", "accountable_owner_ref": "lead-m5-concurrency"}, idem="case"))
    scheduler = DurableSchedulerService(facade)
    for suffix in ("a", "b"):
        scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": f"wu-{suffix}", "input_version_refs": ["summary-v1"], "queue_name": "concurrency-shadow"}, idem=f"enqueue-{suffix}"))
        scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "concurrency-shadow", "work_unit_id": f"wu-{suffix}", "worker_ref": f"worker-{suffix}", "attempt_id": f"attempt-{suffix}", "lease_duration_seconds": 60}, idem=f"claim-{suffix}"))
    return facade


def _grant(*, revoked_at: datetime | None = None) -> CapabilityGrant:
    return CapabilityGrant(grant_id="grant-concurrency", tenant_id="tenant-m5-concurrency", project_id="project-m5-concurrency", case_id="case-m5-concurrency", permission_snapshot_ref="permission-m5-concurrency", capabilities=("checkpoint.write",), allowed_tool_ids=("canonical_checkpoint_store",), allowed_path_prefixes=("artifact_store/point01",), allowed_data_classifications=("internal",), issued_at=NOW - timedelta(minutes=1), expires_at=NOW + timedelta(minutes=10), revoked_at=revoked_at)


def _manifest() -> ToolManifest:
    return ToolManifest(tool_id="canonical_checkpoint_store", capabilities=("checkpoint.write",), allowed_path_prefixes=("artifact_store/point01",), allowed_data_classifications=("internal",))


def _request(*, path: str = "artifact_store/point01/checkpoint", tenant_id: str = "tenant-m5-concurrency") -> SandboxAdmissionRequest:
    return SandboxAdmissionRequest(capability_grant_id="grant-concurrency", capability="checkpoint.write", tool_id="canonical_checkpoint_store", target_tenant_id=tenant_id, target_project_id="project-m5-concurrency", target_case_id="case-m5-concurrency", data_classification="internal", path=path)


def build_result(policy: dict[str, Any], *, policy_path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    errors: list[str] = []
    if policy.get("policy_version") != "finsight_point01_m5_concurrent_budget_security_policy_v1_0" or policy.get("status") != "approved_for_deterministic_implementation":
        errors.append("concurrency_policy_invalid")
    with TemporaryDirectory(prefix="point01_m5_concurrency_") as directory:
        facade = _runtime(Path(directory))
        budget = BudgetControlService(facade, policy=BudgetPolicy(policy_id="case-budget-5", case_token_units=5, work_unit_token_units=5, attempt_token_units=5, case_tool_calls=5, work_unit_tool_calls=5, attempt_tool_calls=5, case_time_seconds=20, work_unit_time_seconds=20, attempt_time_seconds=20))

        def reserve(suffix: str) -> str:
            request = BudgetReservationRequest(reservation_id=f"reservation-{suffix}", work_unit_id=f"wu-{suffix}", attempt_id=f"attempt-{suffix}", token_units=4, tool_calls=1, time_seconds=1)
            try:
                budget.reserve(request)
                return "reserved"
            except BudgetExceededError:
                return "terminal_stop"

        with ThreadPoolExecutor(max_workers=2) as pool:
            budget_outcomes = sorted(pool.map(reserve, ("a", "b")))
        ledger = budget.ledger_view()
        security = CapabilitySecurityService(facade, grants=(_grant(),), tool_manifests=(_manifest(),))
        security.register_authority(_command("CAPABILITY_GRANT_RECORDED", {}, idem="grant-active"), _grant())

        def admit(suffix: str) -> str:
            request = _request() if suffix == "allowed" else _request(tenant_id="tenant-other")
            return "allowed" if security.admit(_command("SECURITY_ADMIT", {}, idem=f"security-{suffix}", at=NOW + timedelta(seconds=1)), request).allowed else "denied"

        with ThreadPoolExecutor(max_workers=2) as pool:
            security_outcomes = sorted(pool.map(admit, ("allowed", "denied")))
        security.register_authority(_command("CAPABILITY_GRANT_RECORDED", {}, idem="grant-revoked", at=NOW + timedelta(seconds=2)), _grant(revoked_at=NOW + timedelta(seconds=2)))
        revoked_denial = security.admit(_command("SECURITY_ADMIT", {}, idem="security-revoked", at=NOW + timedelta(seconds=3)), _request()).denial_code
        audit = security.audit_view()
        evidence = {"budget_outcomes": budget_outcomes, "budget_reserved_count": ledger["slo_observation"]["reserved_count"], "budget_terminal_stop_count": ledger["slo_observation"]["terminal_stop_count"], "security_outcomes": security_outcomes, "security_decision_count": audit["decision_count"], "revoked_grant_denial_code": revoked_denial}
        if budget_outcomes != ["reserved", "terminal_stop"] or ledger["slo_observation"]["reserved_count"] != 1 or ledger["slo_observation"]["terminal_stop_count"] != 1:
            errors.append("case_budget_concurrency_not_atomic")
        if security_outcomes != ["allowed", "denied"] or audit["decision_count"] != 3 or revoked_denial != "capability_grant_revoked":
            errors.append("concurrent_security_admission_or_revocation_failed")
    return {"result_version": "finsight_point01_m5_concurrency_security_result_v1_0", "generated_at": datetime.now(timezone.utc).isoformat(), "scope": "Point01_M5_local_synthetic_concurrent_budget_reservation_and_security_admission_only", "status": "pass" if not errors else "fail_closed", "errors": errors, "evidence": evidence, "worker_started": False, "model_call_count": 0, "external_call_count": 0, "fixed_input_sha256": {str(policy_path.relative_to(ROOT)).replace("\\", "/"): _sha256(policy_path), "scripts/engineering/run_point01_m5_concurrency_security_drills.py": _sha256(Path(__file__).resolve()), "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md")}, "boundary": "This local synthetic drill exercises only concurrent temporary-store reservations and security admission/revocation. It starts no worker/service and admits no provider, external tool, Evidence/Writer, full-chain, business Case mutation or legacy authority change."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M5 concurrent budget/security synthetic drill.")
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
