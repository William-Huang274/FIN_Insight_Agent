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
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


DEFAULT_POLICY = ROOT / "configs/engineering_handoff/point01_m5_1_scheduler_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m5_1_scheduler_fixture_result_v1_0.json"
NOW = datetime(2026, 7, 12, 13, 35, tzinfo=timezone.utc)


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
        tenant_id="tenant-m5-fixture",
        project_id="project-m5-fixture",
        case_id="case-m5-fixture",
        actor_snapshot_ref="actor-m5-fixture",
        permission_snapshot_ref="permission-m5-fixture",
        policy_config_refs=("policy-m5-1",),
        idempotency_key=idem,
        expected_state_version=expected,
        correlation_id="correlation-m5-fixture",
        requested_at=at,
        payload=payload,
    )


def build_result(policy: dict[str, Any], *, policy_path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    errors: list[str] = []
    if policy.get("policy_version") != "finsight_point01_m5_1_scheduler_policy_v1_0":
        errors.append("policy_identity_invalid")
    if policy.get("status") != "approved_for_deterministic_implementation":
        errors.append("policy_status_invalid")
    with TemporaryDirectory(prefix="point01_m5_1_scheduler_") as directory:
        temp_root = Path(directory)
        facade = RuntimeFacade(
            SQLiteCanonicalStore(temp_root / "canonical.sqlite"),
            FileCanonicalObjectStore(temp_root / "objects"),
            _flags(),
            mode="shadow",
            grants={"point01.shadow.write"},
        )
        scheduler = DurableSchedulerService(facade)
        facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.1 fixture", "accountable_owner_ref": "lead-m5"}, idem="case"))
        for work_unit_id, priority in (("wu-low", 1), ("wu-high", 9)):
            scheduler.enqueue(
                _command(
                    "CREATE_WORK_UNIT",
                    {"work_unit_id": work_unit_id, "queue_name": "planning-shadow", "queue_priority": priority, "input_version_refs": ["summary-v1"]},
                    idem=f"enqueue-{work_unit_id}",
                )
            )
        claim = scheduler.claim_next(
            _command(
                "SCHEDULER_CLAIM_NEXT",
                {"queue_name": "planning-shadow", "worker_ref": "worker-a", "attempt_id": "attempt-high", "lease_duration_seconds": 2},
                idem="claim",
            )
        )
        heartbeat_at = NOW + timedelta(seconds=1)
        scheduler.heartbeat(
            _command(
                "SCHEDULER_HEARTBEAT",
                {"work_unit_id": "wu-high", "attempt_id": "attempt-high", "worker_ref": "worker-a", "lease_fencing_token": 1, "lease_duration_seconds": 1},
                expected=1,
                idem="heartbeat",
                at=heartbeat_at,
            )
        )
        reclaim_at = NOW + timedelta(seconds=3)
        scheduler.reclaim_expired(
            _command(
                "SCHEDULER_RECLAIM_EXPIRED_LEASE",
                {"work_unit_id": "wu-high", "attempt_id": "attempt-high", "worker_ref": "worker-b", "lease_duration_seconds": 30},
                expected=1,
                idem="reclaim",
                at=reclaim_at,
            )
        )
        scheduler.cancel(_command("CANCEL_WORK_UNIT", {"work_unit_id": "wu-low"}, idem="cancel-low"))
        queue_view = scheduler.queue_view(case_id="case-m5-fixture", queue_name="planning-shadow", observed_at=reclaim_at)
        attempt = facade.store.get_latest("canonical_attempts", "attempt-high") or {}
        replay = facade.replay_projection()
        if claim.projection_refs != ("wu-high", "attempt-high"):
            errors.append("priority_claim_failed")
        if attempt.get("lease_owner_ref") != "worker-b" or attempt.get("lease_fencing_token") != 2:
            errors.append("expired_lease_reclaim_failed")
        if queue_view["counts"].get("cancelled") != 1 or queue_view["counts"].get("leased") != 1:
            errors.append("queue_or_cancellation_projection_failed")
        if replay != facade.replay_projection():
            errors.append("scheduler_event_replay_not_deterministic")
        evidence = {
            "claim_projection_refs": list(claim.projection_refs),
            "queue_counts": queue_view["counts"],
            "reclaimed_lease_owner_ref": attempt.get("lease_owner_ref"),
            "reclaimed_lease_fencing_token": attempt.get("lease_fencing_token"),
            "scheduler_event_types": [event["event_type"] for event in facade.store.list_events() if event["event_type"].startswith("SCHEDULER_")],
            "replay_event_count": replay["event_count"],
        }
    return {
        "result_version": "finsight_point01_m5_1_scheduler_fixture_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Point01_M5_1_durable_scheduler_control_plane_only",
        "status": "pass" if not errors else "fail_closed",
        "errors": errors,
        "evidence": evidence,
        "worker_started": False,
        "model_call_count": 0,
        "external_call_count": 0,
        "fixed_input_sha256": {
            str(policy_path.relative_to(ROOT)).replace("\\", "/"): _sha256(policy_path),
            "scripts/engineering/run_point01_m5_1_scheduler_fixtures.py": _sha256(Path(__file__).resolve()),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
        },
        "boundary": "This fixture proves only a temporary-store M5.1 scheduler control plane. It starts no worker/service and admits no provider, external tool, Evidence/Writer, full-chain, business Case mutation or legacy authority change.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M5.1 durable scheduler fixtures.")
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
