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
from sec_agent.canonical_runtime.facade import IllegalStateTransition, RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import ArtifactVersionEnvelope, CommandEnvelope, canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.recovery_lifecycle import RecoveryLifecycleService
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


DEFAULT_POLICY = ROOT / "configs/engineering_handoff/point01_m5_2_recovery_lifecycle_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m5_2_recovery_lifecycle_fixture_result_v1_0.json"
NOW = datetime(2026, 7, 12, 14, 15, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
                    "forbidden_consumers": ["memo_writer", "evidence_runtime"],
                }
            ],
        }
    )


def _command(command_type: str, payload: dict[str, Any], *, idem: str, expected: int = 0, at: datetime = NOW) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=f"cmd-{idem}",
        command_type=command_type,
        tenant_id="tenant-m5-2-fixture",
        project_id="project-m5-2-fixture",
        case_id="case-m5-2-fixture",
        actor_snapshot_ref="actor-m5-2-fixture",
        permission_snapshot_ref="permission-m5-2-fixture",
        policy_config_refs=("policy-m5-2",),
        idempotency_key=idem,
        expected_state_version=expected,
        correlation_id="correlation-m5-2-fixture",
        requested_at=at,
        payload=payload,
    )


def _enqueue(scheduler: DurableSchedulerService, work_unit_id: str, *, max_attempts: int = 3, retry_budget: int = 2) -> None:
    scheduler.enqueue(
        _command(
            "CREATE_WORK_UNIT",
            {
                "work_unit_id": work_unit_id,
                "work_unit_type": "decision_surface_compile",
                "input_version_refs": ["summary-v1"],
                "queue_name": "recovery-shadow",
                "max_attempts": max_attempts,
                "retry_budget": retry_budget,
                "retry_policy_ref": "retry:bounded",
                "retryable_failure_types": ["transient"],
                "poison_failure_types": ["poison_payload"],
            },
            idem=f"enqueue-{work_unit_id}",
        )
    )


def _checkpoint(facade: RuntimeFacade, *, artifact_id: str, producer_attempt_id: str) -> str:
    snapshot = {"checkpoint": artifact_id, "producer_attempt_id": producer_attempt_id}
    checkpoint_state_digest = canonical_digest(snapshot)
    checkpoint_payload = {
        "checkpoint_schema_ref": "checkpoint-schema-v1",
        "checkpoint_id": artifact_id,
        "checkpoint_version": 1,
        "checkpoint_version_id": f"{artifact_id}:v1",
        "producer_attempt_id": producer_attempt_id,
        "input_head_digest": canonical_digest(("summary-v1",)),
        "checkpoint_state_digest": checkpoint_state_digest,
        "snapshot": snapshot,
    }
    object_ref = facade.object_store.put_json(
        checkpoint_payload,
        namespace="point01/recovery-checkpoint-fixture",
        artifact_type="runtime_checkpoint",
    )
    artifact = ArtifactVersionEnvelope(
        tenant_id="tenant-m5-2-fixture",
        project_id="project-m5-2-fixture",
        case_id="case-m5-2-fixture",
        actor_snapshot_ref="actor-m5-2-fixture",
        permission_snapshot_ref="permission-m5-2-fixture",
        policy_config_refs=("policy-m5-2",),
        correlation_id="correlation-m5-2-fixture",
        created_at=NOW,
        recorded_at=NOW,
        current_status="checkpoint_available",
        artifact_id=artifact_id,
        artifact_version_id=f"{artifact_id}:v1",
        artifact_version=1,
        artifact_type="runtime_checkpoint",
        payload_business_owner="recovery_lifecycle_owner",
        producer_attempt_id=producer_attempt_id,
        input_refs=("summary-v1",),
        input_refs_digest=canonical_digest(("summary-v1",)),
        object_key=object_ref["object_key"],
        object_digest=object_ref["digest"],
        byte_size=object_ref["byte_size"],
        media_type=object_ref["media_type"],
        checkpoint_schema_ref="checkpoint-schema-v1",
        checkpoint_state_digest=checkpoint_state_digest,
        checkpoint_sequence_no=1,
    )
    with facade.store.transaction() as tx:
        tx.insert("canonical_artifact_versions", artifact_id, 1, artifact.model_dump(mode="json"))
    return artifact.artifact_version_id


def build_result(policy: dict[str, Any], *, policy_path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    errors: list[str] = []
    if policy.get("policy_version") != "finsight_point01_m5_2_recovery_lifecycle_policy_v1_0":
        errors.append("policy_identity_invalid")
    if policy.get("status") != "approved_for_deterministic_implementation":
        errors.append("policy_status_invalid")
    with TemporaryDirectory(prefix="point01_m5_2_recovery_") as directory:
        temp_root = Path(directory)
        facade = RuntimeFacade(
            SQLiteCanonicalStore(temp_root / "canonical.sqlite"),
            FileCanonicalObjectStore(temp_root / "objects"),
            _flags(),
            mode="shadow",
            grants={"point01.shadow.write"},
        )
        scheduler = DurableSchedulerService(facade)
        recovery = RecoveryLifecycleService(facade, scheduler=scheduler)
        facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.2 fixture", "accountable_owner_ref": "lead-m5-2"}, idem="case"))
        _enqueue(scheduler, "wu-recovery", max_attempts=2, retry_budget=1)
        scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "recovery-shadow", "work_unit_id": "wu-recovery", "worker_ref": "worker-1", "attempt_id": "attempt-1"}, idem="claim-1"))
        facade.fail_attempt(
            _command(
                "FAIL_ATTEMPT",
                {"work_unit_id": "wu-recovery", "attempt_id": "attempt-1", "worker_ref": "worker-1", "lease_fencing_token": 1, "failure_type": "transient", "retryable": True},
                expected=1,
                idem="fail-1",
                at=NOW + timedelta(seconds=1),
            )
        )
        checkpoint_ref = _checkpoint(facade, artifact_id="checkpoint-1", producer_attempt_id="attempt-1")
        resume = recovery.resume(
            _command(
                "RECOVERY_RESUME",
                {"work_unit_id": "wu-recovery", "queue_name": "recovery-shadow", "worker_ref": "worker-2", "attempt_id": "attempt-2", "resume_checkpoint_ref": checkpoint_ref},
                expected=2,
                idem="resume-2",
                at=NOW + timedelta(seconds=2),
            )
        )
        facade.fail_attempt(
            _command(
                "FAIL_ATTEMPT",
                {"work_unit_id": "wu-recovery", "attempt_id": "attempt-2", "worker_ref": "worker-2", "lease_fencing_token": 2, "failure_type": "transient", "retryable": True},
                expected=3,
                idem="fail-2",
                at=NOW + timedelta(seconds=3),
            )
        )
        budget_terminated = facade.store.get_latest("canonical_work_units", "wu-recovery") or {}
        retry_blocked = False
        try:
            recovery.retry(
                _command(
                    "RECOVERY_RETRY",
                    {"work_unit_id": "wu-recovery", "queue_name": "recovery-shadow", "worker_ref": "worker-3"},
                    expected=4,
                    idem="retry-after-budget",
                )
            )
        except IllegalStateTransition:
            retry_blocked = True
        recovery.dead_letter(
            _command(
                "RECOVERY_DEAD_LETTER",
                {"work_unit_id": "wu-recovery", "source_attempt_id": "attempt-2", "dead_letter_reason": "retry_budget_exhausted"},
                expected=4,
                idem="dead-letter",
                at=NOW + timedelta(seconds=4),
            )
        )
        dead_letter_view = recovery.dead_letter_view(case_id="case-m5-2-fixture")
        replay = facade.replay_projection()
        resumed_attempt = facade.store.get_latest("canonical_attempts", "attempt-2") or {}
        if resumed_attempt.get("resume_checkpoint_ref") != checkpoint_ref:
            errors.append("exact_checkpoint_resume_failed")
        if budget_terminated.get("state") != "failed" or not retry_blocked:
            errors.append("retry_budget_termination_failed")
        if dead_letter_view.get("dead_letter_count") != 1:
            errors.append("dead_letter_not_inspectable")
        if replay != facade.replay_projection():
            errors.append("recovery_replay_not_deterministic")
        evidence = {
            "resume_projection_refs": list(resume.projection_refs),
            "resume_checkpoint_ref": resumed_attempt.get("resume_checkpoint_ref"),
            "budget_terminated_state": budget_terminated.get("state"),
            "retry_after_budget_blocked": retry_blocked,
            "dead_letter_records": dead_letter_view.get("records"),
            "recovery_event_types": [event["event_type"] for event in facade.store.list_events() if event["event_type"].startswith("RECOVERY_")],
            "replay_event_count": replay["event_count"],
        }
    return {
        "result_version": "finsight_point01_m5_2_recovery_lifecycle_fixture_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Point01_M5_2_recovery_lifecycle_control_plane_only",
        "status": "pass" if not errors else "fail_closed",
        "errors": errors,
        "evidence": evidence,
        "worker_started": False,
        "model_call_count": 0,
        "external_call_count": 0,
        "fixed_input_sha256": {
            str(policy_path.relative_to(ROOT)).replace("\\", "/"): _sha256(policy_path),
            "scripts/engineering/run_point01_m5_2_recovery_lifecycle_fixtures.py": _sha256(Path(__file__).resolve()),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
        },
        "boundary": "This fixture proves only a temporary-store M5.2 recovery control plane. It creates no checkpoint storage lifecycle, starts no worker/service and admits no provider, external tool, Evidence/Writer, full-chain, business Case mutation or legacy authority change.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M5.2 recovery lifecycle fixtures.")
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
