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
if str(ROOT / "src") not in sys.path: sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.observability_ops import ObservabilityError, ObservabilityOpsService
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore

DEFAULT_POLICY = ROOT / "configs/engineering_handoff/point01_m5_8_observability_ops_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m5_8_observability_ops_fixture_result_v1_0.json"
NOW = datetime(2026, 7, 12, 17, 15, tzinfo=timezone.utc)


def _sha256(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry({"default_deny": True, "flags": [{"flag_id": "decision_surface_shadow_v0_1", "default_mode": "off", "allowed_modes": ["off", "shadow"], "required_capability_grants": ["point01.shadow.write"], "allowed_consumers": ["point01_shadow_compiler"], "forbidden_consumers": ["memo_writer", "evidence_runtime"]}]})


def _command(kind: str, payload: dict[str, Any], *, idem: str, expected: int = 0, at: datetime = NOW) -> CommandEnvelope:
    return CommandEnvelope(command_id=f"cmd-{idem}", command_type=kind, tenant_id="tenant-m5-8-fixture", project_id="project-m5-8-fixture", case_id="case-m5-8-fixture", actor_snapshot_ref="actor-m5-8-fixture", permission_snapshot_ref="permission-m5-8-fixture", policy_config_refs=("policy-m5-8",), idempotency_key=idem, expected_state_version=expected, correlation_id="correlation-m5-8-fixture", requested_at=at, payload=payload)


def _runtime(root: Path) -> RuntimeFacade:
    facade = RuntimeFacade(SQLiteCanonicalStore(root / "canonical.sqlite"), FileCanonicalObjectStore(root / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.8 fixture", "accountable_owner_ref": "lead"}, idem="case"))
    scheduler = DurableSchedulerService(facade)
    scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-ops", "input_version_refs": ["summary-v1"], "queue_name": "ops-shadow", "max_attempts": 2, "retry_budget": 1, "retry_policy_ref": "retry:bounded", "retryable_failure_types": ["transient"]}, idem="enqueue"))
    scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "ops-shadow", "work_unit_id": "wu-ops", "worker_ref": "worker", "attempt_id": "attempt-ops-1", "lease_duration_seconds": 120}, idem="claim"))
    return facade


def build_result(policy: dict[str, Any], *, policy_path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    errors: list[str] = []
    if policy.get("policy_version") != "finsight_point01_m5_8_observability_ops_policy_v1_0" or policy.get("status") != "approved_for_deterministic_implementation": errors.append("policy_invalid")
    with TemporaryDirectory(prefix="point01_m5_8_ops_") as directory:
        facade = _runtime(Path(directory)); ops = ObservabilityOpsService(facade)
        initial = ops.stream(case_id="case-m5-8-fixture")
        result = ops.materialize(_command("OBS_MATERIALIZE", {"alert_event_type": "WORK_UNIT_STARTED", "alert_threshold": 1}, idem="materialize", at=NOW + timedelta(seconds=1)))
        reconnect = ops.stream(case_id="case-m5-8-fixture", after_event_id=initial["next_cursor_event_id"])
        admin = ops.admin_view(case_id="case-m5-8-fixture")
        raw_rejected = False
        try: ops.materialize(_command("OBS_MATERIALIZE", {"alert_event_type": "WORK_UNIT_STARTED", "alert_threshold": 1, "trace_annotations": {"raw_reasoning": "forbidden"}}, idem="raw"))
        except ObservabilityError: raw_rejected = True
        initial_ids = {event["event_id"] for event in initial["events"]}; reconnect_ids = {event["event_id"] for event in reconnect["events"]}
        if result.status != "succeeded": errors.append("trace_materialization_failed")
        if initial_ids.intersection(reconnect_ids): errors.append("reconnect_duplicated_events")
        if admin["metrics"]["trace_span_count"] < len(initial["events"]) or admin["metrics"]["open_alert_count"] != 1: errors.append("trace_or_alert_not_inspectable")
        if not raw_rejected or admin["raw_reasoning_persisted"]: errors.append("raw_reasoning_boundary_failed")
        evidence = {"initial_event_count": len(initial["events"]), "reconnect_event_count": len(reconnect["events"]), "reconnect_has_no_duplicate": not bool(initial_ids.intersection(reconnect_ids)), "trace_span_count": admin["metrics"]["trace_span_count"], "open_alert_count": admin["metrics"]["open_alert_count"], "raw_reasoning_rejected": raw_rejected, "raw_reasoning_persisted": admin["raw_reasoning_persisted"]}
    return {"result_version": "finsight_point01_m5_8_observability_ops_fixture_result_v1_0", "generated_at": datetime.now(timezone.utc).isoformat(), "scope": "Point01_M5_8_observability_operations_control_plane_only", "status": "pass" if not errors else "fail_closed", "errors": errors, "evidence": evidence, "worker_started": False, "model_call_count": 0, "external_call_count": 0, "fixed_input_sha256": {str(policy_path.relative_to(ROOT)).replace("\\", "/"): _sha256(policy_path), "scripts/engineering/run_point01_m5_8_observability_ops_fixtures.py": _sha256(Path(__file__).resolve()), "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md")}, "boundary": "This fixture proves a store-backed event stream, redacted trace projection, threshold alert and admin inspection only. It uses no external observability service and starts no worker/service/provider/tool/Evidence/Writer/full-chain/business Case mutation/legacy authority change."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M5.8 observability fixtures."); parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY); parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(); policy_path = args.policy if args.policy.is_absolute() else ROOT / args.policy; output_path = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result(json.loads(policy_path.read_text(encoding="utf-8")), policy_path=policy_path); output_path.parent.mkdir(parents=True, exist_ok=True); output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output_path), "errors": result["errors"]}, ensure_ascii=False)); return 0 if result["status"] == "pass" else 1


if __name__ == "__main__": raise SystemExit(main())
