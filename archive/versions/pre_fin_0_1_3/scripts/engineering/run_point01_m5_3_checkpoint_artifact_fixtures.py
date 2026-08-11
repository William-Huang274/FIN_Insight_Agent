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

from sec_agent.canonical_runtime.checkpoint_artifacts import CheckpointArtifactService
from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore, StaleStateVersion


DEFAULT_POLICY = ROOT / "configs/engineering_handoff/point01_m5_3_checkpoint_artifact_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m5_3_checkpoint_artifact_fixture_result_v1_0.json"
NOW = datetime(2026, 7, 12, 14, 45, tzinfo=timezone.utc)


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
        tenant_id="tenant-m5-3-fixture",
        project_id="project-m5-3-fixture",
        case_id="case-m5-3-fixture",
        actor_snapshot_ref="actor-m5-3-fixture",
        permission_snapshot_ref="permission-m5-3-fixture",
        policy_config_refs=("policy-m5-3",),
        idempotency_key=idem,
        expected_state_version=expected,
        correlation_id="correlation-m5-3-fixture",
        requested_at=at,
        payload=payload,
    )


def _checkpoint_command(
    *,
    snapshot: dict[str, Any],
    expected_checkpoint_version: int,
    supersedes_version_id: str | None,
    idem: str,
    at: datetime,
) -> CommandEnvelope:
    return _command(
        "CREATE_CHECKPOINT_VERSION",
        {
            "work_unit_id": "wu-checkpoint",
            "attempt_id": "attempt-checkpoint-1",
            "worker_ref": "worker-checkpoint",
            "lease_fencing_token": 1,
            "checkpoint_id": "checkpoint-fixture",
            "expected_checkpoint_version": expected_checkpoint_version,
            "supersedes_version_id": supersedes_version_id,
            "checkpoint_schema_ref": "checkpoint-schema-v1",
            "snapshot": snapshot,
        },
        expected=1,
        idem=idem,
        at=at,
    )


def build_result(policy: dict[str, Any], *, policy_path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    errors: list[str] = []
    if policy.get("policy_version") != "finsight_point01_m5_3_checkpoint_artifact_policy_v1_0":
        errors.append("policy_identity_invalid")
    if policy.get("status") != "approved_for_deterministic_implementation":
        errors.append("policy_status_invalid")
    if policy.get("maximum_serialized_snapshot_bytes") != 262144:
        errors.append("checkpoint_snapshot_limit_policy_invalid")
    with TemporaryDirectory(prefix="point01_m5_3_checkpoint_") as directory:
        temp_root = Path(directory)
        database_path = temp_root / "canonical.sqlite"
        objects_path = temp_root / "objects"
        facade = RuntimeFacade(
            SQLiteCanonicalStore(database_path),
            FileCanonicalObjectStore(objects_path),
            _flags(),
            mode="shadow",
            grants={"point01.shadow.write"},
        )
        scheduler = DurableSchedulerService(facade)
        checkpoints = CheckpointArtifactService(facade)
        facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.3 fixture", "accountable_owner_ref": "lead-m5-3"}, idem="case"))
        scheduler.enqueue(
            _command(
                "CREATE_WORK_UNIT",
                {"work_unit_id": "wu-checkpoint", "input_version_refs": ["summary-v1"], "queue_name": "checkpoint-shadow"},
                idem="enqueue",
            )
        )
        scheduler.claim_next(
            _command(
                "SCHEDULER_CLAIM_NEXT",
                {"queue_name": "checkpoint-shadow", "work_unit_id": "wu-checkpoint", "worker_ref": "worker-checkpoint", "attempt_id": "attempt-checkpoint-1", "lease_duration_seconds": 60},
                idem="claim",
            )
        )
        first = checkpoints.write(
            _checkpoint_command(snapshot={"cursor": "phase-1", "accepted_refs": ["summary-v1"]}, expected_checkpoint_version=0, supersedes_version_id=None, idem="checkpoint-v1", at=NOW + timedelta(seconds=1))
        )
        second = checkpoints.write(
            _checkpoint_command(snapshot={"cursor": "phase-2", "repair": "targeted"}, expected_checkpoint_version=1, supersedes_version_id="checkpoint-fixture:v1", idem="checkpoint-v2", at=NOW + timedelta(seconds=2))
        )
        stale_write_blocked = False
        try:
            checkpoints.write(
                _checkpoint_command(snapshot={"cursor": "stale"}, expected_checkpoint_version=1, supersedes_version_id="checkpoint-fixture:v1", idem="checkpoint-stale", at=NOW + timedelta(seconds=3))
            )
        except StaleStateVersion:
            stale_write_blocked = True
        v1 = checkpoints.read_exact(case_id="case-m5-3-fixture", checkpoint_ref="checkpoint-fixture:v1")
        v2 = checkpoints.read_exact(case_id="case-m5-3-fixture", checkpoint_ref="checkpoint-fixture:v2")
        restarted = CheckpointArtifactService(
            RuntimeFacade(
                SQLiteCanonicalStore(database_path),
                FileCanonicalObjectStore(objects_path),
                _flags(),
                mode="shadow",
                grants={"point01.shadow.write"},
            )
        ).require_exact_checkpoint(case_id="case-m5-3-fixture", checkpoint_ref="checkpoint-fixture:v2")
        recovery_view = checkpoints.recovery_view(case_id="case-m5-3-fixture")
        checkpoint_events = [event for event in facade.store.list_events() if event["event_type"] == "CHECKPOINT_VERSION_CREATED"]
        replay = facade.replay_projection()
        if first.artifact_refs != ("checkpoint-fixture:v1",) or second.artifact_refs != ("checkpoint-fixture:v2",):
            errors.append("checkpoint_versions_not_created")
        if len(checkpoint_events) != 2 or recovery_view["checkpoint_count"] != 2:
            errors.append("checkpoint_event_artifact_atomicity_failed")
        if not stale_write_blocked:
            errors.append("stale_checkpoint_write_not_rejected")
        if v1["snapshot"].get("cursor") != "phase-1" or v2["snapshot"].get("cursor") != "phase-2":
            errors.append("checkpoint_history_not_exactly_readable")
        if restarted["snapshot"] != v2["snapshot"]:
            errors.append("checkpoint_restart_recovery_failed")
        if replay != facade.replay_projection():
            errors.append("checkpoint_replay_not_deterministic")
        evidence = {
            "checkpoint_event_count": len(checkpoint_events),
            "checkpoint_artifact_count": recovery_view["checkpoint_count"],
            "checkpoint_refs": [record["checkpoint_ref"] for record in recovery_view["records"]],
            "stale_write_blocked": stale_write_blocked,
            "v1_cursor": v1["snapshot"].get("cursor"),
            "v2_cursor": v2["snapshot"].get("cursor"),
            "restart_snapshot_matches_v2": restarted["snapshot"] == v2["snapshot"],
            "replay_event_count": replay["event_count"],
        }
    return {
        "result_version": "finsight_point01_m5_3_checkpoint_artifact_fixture_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Point01_M5_3_checkpoint_artifact_versioning_control_plane_only",
        "status": "pass" if not errors else "fail_closed",
        "errors": errors,
        "evidence": evidence,
        "worker_started": False,
        "model_call_count": 0,
        "external_call_count": 0,
        "fixed_input_sha256": {
            str(policy_path.relative_to(ROOT)).replace("\\", "/"): _sha256(policy_path),
            "scripts/engineering/run_point01_m5_3_checkpoint_artifact_fixtures.py": _sha256(Path(__file__).resolve()),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
        },
        "boundary": "This fixture proves only temporary-store M5.3 checkpoint artifact versioning. It starts no worker/service, performs no checkpoint compaction, and admits no provider, external tool, Evidence/Writer, full-chain, business Case mutation or legacy authority change.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M5.3 checkpoint artifact fixtures.")
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
