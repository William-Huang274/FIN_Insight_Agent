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

from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.hitl_governance import ApprovalRegistryRecord, HITLApprovalError, HITLGovernanceService
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


DEFAULT_POLICY = ROOT / "configs/engineering_handoff/point01_m5_6_hitl_governance_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m5_6_hitl_governance_fixture_result_v1_0.json"
NOW = datetime(2026, 7, 12, 16, 15, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry({"default_deny": True, "flags": [{"flag_id": "decision_surface_shadow_v0_1", "default_mode": "off", "allowed_modes": ["off", "shadow"], "required_capability_grants": ["point01.shadow.write"], "allowed_consumers": ["point01_shadow_compiler"], "forbidden_consumers": ["memo_writer", "evidence_runtime"]}]})


def _command(command_type: str, payload: dict[str, Any], *, idem: str, expected: int = 0, at: datetime = NOW) -> CommandEnvelope:
    return CommandEnvelope(command_id=f"cmd-{idem}", command_type=command_type, tenant_id="tenant-m5-6-fixture", project_id="project-m5-6-fixture", case_id="case-m5-6-fixture", actor_snapshot_ref="actor-m5-6-fixture", permission_snapshot_ref="permission-m5-6-fixture", policy_config_refs=("policy-m5-6",), idempotency_key=idem, expected_state_version=expected, correlation_id="correlation-m5-6-fixture", requested_at=at, payload=payload)


def _setup(root: Path) -> RuntimeFacade:
    facade = RuntimeFacade(SQLiteCanonicalStore(root / "canonical.sqlite"), FileCanonicalObjectStore(root / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.6 fixture", "accountable_owner_ref": "lead-m5-6"}, idem="case"))
    scheduler = DurableSchedulerService(facade)
    scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-hitl", "input_version_refs": ["summary-v1"], "queue_name": "hitl-shadow", "max_attempts": 2, "retry_budget": 1, "retry_policy_ref": "retry:bounded", "retryable_failure_types": ["transient"]}, idem="enqueue"))
    scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "hitl-shadow", "work_unit_id": "wu-hitl", "worker_ref": "worker-hitl", "attempt_id": "attempt-hitl-1", "lease_duration_seconds": 120}, idem="claim"))
    facade.create_checkpoint_version(_command("CREATE_CHECKPOINT_VERSION", {"work_unit_id": "wu-hitl", "attempt_id": "attempt-hitl-1", "worker_ref": "worker-hitl", "lease_fencing_token": 1, "checkpoint_id": "checkpoint-hitl", "expected_checkpoint_version": 0, "supersedes_version_id": None, "checkpoint_schema_ref": "checkpoint-schema-v1", "snapshot": {"cursor": "pause"}}, expected=1, idem="checkpoint", at=NOW + timedelta(seconds=1)))
    return facade


def _pause_command(scope_digest: str, *, approval_id: str, at: datetime = NOW + timedelta(seconds=2)) -> CommandEnvelope:
    return _command("HITL_PAUSE", {"approval_id": approval_id, "work_unit_id": "wu-hitl", "attempt_id": "attempt-hitl-1", "checkpoint_ref": "checkpoint-hitl:v1", "scope_digest": scope_digest, "worker_ref": "worker-hitl", "lease_fencing_token": 1}, expected=1, idem=f"pause-{approval_id}", at=at)


def _scope_digest(approval_id: str) -> str:
    draft = _pause_command("draft", approval_id=approval_id)
    return HITLGovernanceService._scope_digest(draft, work_unit_id="wu-hitl", attempt_id="attempt-hitl-1", checkpoint_ref="checkpoint-hitl:v1")


def _registry(scope_digest: str, *, approval_id: str, state: str = "active") -> dict[str, ApprovalRegistryRecord]:
    return {approval_id: ApprovalRegistryRecord(approval_id=approval_id, approval_registry_ref="registry:hitl-fixture", scope_digest=scope_digest, approval_state=state, expires_at=NOW + timedelta(minutes=10))}


def build_result(policy: dict[str, Any], *, policy_path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    errors: list[str] = []
    if policy.get("policy_version") != "finsight_point01_m5_6_hitl_governance_policy_v1_0":
        errors.append("policy_identity_invalid")
    if policy.get("status") != "approved_for_deterministic_implementation":
        errors.append("policy_status_invalid")
    with TemporaryDirectory(prefix="point01_m5_6_hitl_") as directory:
        root = Path(directory)
        approval_id = "approval-hitl"
        scope_digest = _scope_digest(approval_id)
        facade = _setup(root)
        service = HITLGovernanceService(facade, approval_registry=_registry(scope_digest, approval_id=approval_id))
        service.register_authority(_command("HITL_REGISTRY_RECORD", {}, idem="record-active"), _registry(scope_digest, approval_id=approval_id)[approval_id])
        pause = service.pause(_pause_command(scope_digest, approval_id=approval_id))
        restarted = RuntimeFacade(SQLiteCanonicalStore(root / "canonical.sqlite"), FileCanonicalObjectStore(root / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
        recovered = HITLGovernanceService(restarted, approval_registry={})
        queue = recovered.review_queue(case_id="case-m5-6-fixture", at=NOW + timedelta(seconds=3))
        resume = recovered.resume(_command("HITL_RESUME", {"approval_id": approval_id, "work_unit_id": "wu-hitl", "attempt_id": "attempt-hitl-1", "scope_digest": scope_digest, "worker_ref": "worker-resumed", "lease_duration_seconds": 60}, expected=2, idem="resume", at=NOW + timedelta(seconds=4)))
        resumed_attempt = restarted.store.get_latest("canonical_attempts", "attempt-hitl-1")

        revocation_root = root / "revocation"
        revocation_facade = _setup(revocation_root)
        revocation_scope = _scope_digest("approval-revoked")
        revoked = HITLGovernanceService(revocation_facade, approval_registry=_registry(revocation_scope, approval_id="approval-revoked"))
        revoked.register_authority(_command("HITL_REGISTRY_RECORD", {}, idem="record-revoked-active"), _registry(revocation_scope, approval_id="approval-revoked")["approval-revoked"])
        revoked.pause(_pause_command(revocation_scope, approval_id="approval-revoked"))
        revoked.register_authority(_command("HITL_REGISTRY_RECORD", {}, idem="record-revoked-state", at=NOW + timedelta(seconds=3)), _registry(revocation_scope, approval_id="approval-revoked", state="revoked")["approval-revoked"])
        invalidation = revoked.invalidate(_command("HITL_INVALIDATE", {"approval_id": "approval-revoked", "reason": "reviewer_revoked"}, expected=1, idem="invalidate", at=NOW + timedelta(seconds=3)))
        resume_blocked = False
        try:
            revoked.resume(_command("HITL_RESUME", {"approval_id": "approval-revoked", "work_unit_id": "wu-hitl", "attempt_id": "attempt-hitl-1", "scope_digest": revocation_scope, "worker_ref": "worker-resumed", "lease_duration_seconds": 60}, expected=2, idem="resume-revoked", at=NOW + timedelta(seconds=4)))
        except HITLApprovalError:
            resume_blocked = True
        events = [event["event_type"] for event in restarted.store.list_events() if event.get("work_unit_id") == "wu-hitl"]
        if pause.state_version_after != 2 or resume.state_version_after != 3:
            errors.append("pause_resume_state_transition_invalid")
        if queue["paused_count"] != 1 or not queue["review_queue"][0]["eligible_to_resume"]:
            errors.append("restart_review_queue_not_recovered")
        if resumed_attempt.get("lease_fencing_token") != 2:
            errors.append("resume_did_not_rotate_fencing_token")
        if not resume_blocked or invalidation.state_version_after != 2:
            errors.append("revocation_did_not_fail_closed")
        for event_type in ("HITL_APPROVAL_RECORDED", "HITL_WORK_UNIT_PAUSED", "HITL_WORK_UNIT_RESUMED"):
            if event_type not in events:
                errors.append(f"missing_event:{event_type}")
        # Event ids are intentionally generated by the append-only runtime and
        # therefore cannot be package-stable fixture evidence.  The canonical
        # store retains those ids; this deterministic result records their
        # semantic presence and cardinality instead.
        evidence = {"pause_event_count": len(pause.event_ids), "resume_event_count": len(resume.event_ids), "invalidation_event_count": len(invalidation.event_ids), "persisted_registry_authority_survives_restart": queue["paused_count"] == 1 and not recovered._approval_registry, "pause_survived_restart": queue["paused_count"] == 1, "resumed_fencing_token": resumed_attempt.get("lease_fencing_token"), "revoked_resume_blocked": resume_blocked, "event_types": events}
    return {"result_version": "finsight_point01_m5_6_hitl_governance_fixture_result_v1_0", "generated_at": datetime.now(timezone.utc).isoformat(), "scope": "Point01_M5_6_durable_hitl_approval_control_plane_only", "status": "pass" if not errors else "fail_closed", "errors": errors, "evidence": evidence, "worker_started": False, "model_call_count": 0, "external_call_count": 0, "fixed_input_sha256": {str(policy_path.relative_to(ROOT)).replace("\\", "/"): _sha256(policy_path), "scripts/engineering/run_point01_m5_6_hitl_governance_fixtures.py": _sha256(Path(__file__).resolve()), "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md")}, "boundary": "This fixture proves deterministic persistent-in-temporary-store HITL receipt/pause/resume/revocation only. It starts no worker/service and admits no provider, external tool, Evidence/Writer, full-chain, business Case mutation or legacy authority change."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M5.6 HITL governance fixtures.")
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
