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

from sec_agent.canonical_runtime.capability_security import (
    CapabilityGrant,
    CapabilitySecurityError,
    CapabilitySecurityService,
    SandboxAdmissionRequest,
    ToolManifest,
)
from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


DEFAULT_POLICY = ROOT / "configs/engineering_handoff/point01_m5_4_capability_security_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m5_4_capability_security_fixture_result_v1_0.json"
NOW = datetime(2026, 7, 12, 15, 15, tzinfo=timezone.utc)


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
        tenant_id="tenant-m5-4-fixture",
        project_id="project-m5-4-fixture",
        case_id="case-m5-4-fixture",
        actor_snapshot_ref="actor-m5-4-fixture",
        permission_snapshot_ref="permission-m5-4-fixture",
        policy_config_refs=("policy-m5-4",),
        idempotency_key=idem,
        expected_state_version=expected,
        correlation_id="correlation-m5-4-fixture",
        requested_at=at,
        payload=payload,
    )


def _grant(*, expires_at: datetime = NOW + timedelta(hours=1), revoked_at: datetime | None = None) -> CapabilityGrant:
    return CapabilityGrant(
        grant_id="grant-fixture",
        tenant_id="tenant-m5-4-fixture",
        project_id="project-m5-4-fixture",
        case_id="case-m5-4-fixture",
        permission_snapshot_ref="permission-m5-4-fixture",
        capabilities=("checkpoint.write",),
        allowed_tool_ids=("canonical_checkpoint_store",),
        allowed_network_hosts=("checkpoint-safe.example",),
        allowed_path_prefixes=("artifact_store/point01",),
        allowed_data_classifications=("internal",),
        issued_at=NOW - timedelta(minutes=1),
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


def _manifest() -> ToolManifest:
    return ToolManifest(
        tool_id="canonical_checkpoint_store",
        capabilities=("checkpoint.write",),
        allowed_network_hosts=("checkpoint-safe.example",),
        allowed_path_prefixes=("artifact_store/point01",),
        allowed_data_classifications=("internal",),
    )


def _request(**updates: Any) -> SandboxAdmissionRequest:
    request = SandboxAdmissionRequest(
        capability_grant_id="grant-fixture",
        capability="checkpoint.write",
        tool_id="canonical_checkpoint_store",
        target_tenant_id="tenant-m5-4-fixture",
        target_project_id="project-m5-4-fixture",
        target_case_id="case-m5-4-fixture",
        data_classification="internal",
        path="artifact_store/point01/checkpoints",
    )
    return request.model_copy(update=updates)


def _checkpoint_command(*, checkpoint_id: str, idem: str, at: datetime) -> CommandEnvelope:
    return _command(
        "CREATE_CHECKPOINT_VERSION",
        {
            "work_unit_id": "wu-secure",
            "attempt_id": "attempt-secure-1",
            "worker_ref": "worker-security",
            "lease_fencing_token": 1,
            "checkpoint_id": checkpoint_id,
            "expected_checkpoint_version": 0,
            "supersedes_version_id": None,
            "checkpoint_schema_ref": "checkpoint-schema-v1",
            "snapshot": {"cursor": "secure-phase"},
        },
        expected=1,
        idem=idem,
        at=at,
    )


def build_result(policy: dict[str, Any], *, policy_path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    errors: list[str] = []
    if policy.get("policy_version") != "finsight_point01_m5_4_capability_security_policy_v1_0":
        errors.append("policy_identity_invalid")
    if policy.get("status") != "approved_for_deterministic_implementation":
        errors.append("policy_status_invalid")
    with TemporaryDirectory(prefix="point01_m5_4_security_") as directory:
        temp_root = Path(directory)
        facade = RuntimeFacade(
            SQLiteCanonicalStore(temp_root / "canonical.sqlite"),
            FileCanonicalObjectStore(temp_root / "objects"),
            _flags(),
            mode="shadow",
            grants={"point01.shadow.write"},
        )
        scheduler = DurableSchedulerService(facade)
        facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.4 fixture", "accountable_owner_ref": "lead-m5-4"}, idem="case"))
        scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-secure", "input_version_refs": ["summary-v1"], "queue_name": "security-shadow"}, idem="enqueue"))
        scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "security-shadow", "work_unit_id": "wu-secure", "worker_ref": "worker-security", "attempt_id": "attempt-secure-1", "lease_duration_seconds": 60}, idem="claim"))
        security = CapabilitySecurityService(facade, grants=(_grant(),), tool_manifests=(_manifest(),))
        security.register_authority(_command("CAPABILITY_GRANT_RECORDED", {}, idem="grant-fixture-record"), _grant())
        allowed = security.execute_checkpoint_write(_checkpoint_command(checkpoint_id="checkpoint-secure", idem="allowed-checkpoint", at=NOW + timedelta(seconds=1)), _request())
        denials = {
            "unknown_capability": security.admit(_checkpoint_command(checkpoint_id="checkpoint-unknown", idem="unknown", at=NOW + timedelta(seconds=2)), _request(capability="unknown.capability")).denial_code,
            "tenant_cross_read": security.admit(_checkpoint_command(checkpoint_id="checkpoint-cross", idem="cross", at=NOW + timedelta(seconds=2)), _request(target_tenant_id="tenant-other")).denial_code,
            "network_scope": security.admit(_checkpoint_command(checkpoint_id="checkpoint-network", idem="network", at=NOW + timedelta(seconds=2)), _request(network_host="evil.example")).denial_code,
            "path_scope": security.admit(_checkpoint_command(checkpoint_id="checkpoint-path", idem="path", at=NOW + timedelta(seconds=2)), _request(path="workspace/private")).denial_code,
            "privacy_scope": security.admit(_checkpoint_command(checkpoint_id="checkpoint-privacy", idem="privacy", at=NOW + timedelta(seconds=2)), _request(data_classification="restricted")).denial_code,
        }
        restarted = RuntimeFacade(SQLiteCanonicalStore(temp_root / "canonical.sqlite"), FileCanonicalObjectStore(temp_root / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
        recovered_security = CapabilitySecurityService(restarted, grants=(), tool_manifests=(_manifest(),))
        recovered_allowed = recovered_security.admit(_checkpoint_command(checkpoint_id="checkpoint-restart", idem="restart-authority", at=NOW + timedelta(seconds=2)), _request()).allowed
        expired = CapabilitySecurityService(facade, grants=(_grant(expires_at=NOW),), tool_manifests=(_manifest(),))
        expired.register_authority(_command("CAPABILITY_GRANT_RECORDED", {}, idem="grant-fixture-expired", at=NOW + timedelta(seconds=2)), _grant(expires_at=NOW))
        expired_blocked = False
        try:
            expired.execute_checkpoint_write(_checkpoint_command(checkpoint_id="checkpoint-expired", idem="expired", at=NOW + timedelta(seconds=2)), _request())
        except CapabilitySecurityError:
            expired_blocked = True
        checkpoint_rows = [row for row in facade.store.list_versions("canonical_artifact_versions", case_id="case-m5-4-fixture") if row["artifact_type"] == "runtime_checkpoint"]
        audit = security.audit_view()
        expected_denials = {
            "unknown_capability": "unknown_capability",
            "tenant_cross_read": "tenant_cross_read_denied",
            "network_scope": "network_scope_denied",
            "path_scope": "path_scope_denied",
            "privacy_scope": "privacy_classification_denied",
        }
        if allowed.artifact_refs != ("checkpoint-secure:v1",):
            errors.append("protected_checkpoint_write_not_allowed")
        if denials != expected_denials:
            errors.append("security_denial_matrix_invalid")
        if not expired_blocked or len(checkpoint_rows) != 1:
            errors.append("expired_grant_did_not_revoke_checkpoint_write")
        if audit["allowed_count"] != 2 or audit["denied_count"] != len(expected_denials) + 1:
            errors.append("sandbox_trace_audit_invalid")
        evidence = {
            "allowed_checkpoint_ref": list(allowed.artifact_refs),
            "denials": denials,
            "expired_grant_blocked": expired_blocked,
            "persisted_grant_authority_survives_restart": recovered_allowed,
            "canonical_checkpoint_artifact_count": len(checkpoint_rows),
            "audit_allowed_count": audit["allowed_count"],
            "audit_denied_count": audit["denied_count"],
        }
    return {
        "result_version": "finsight_point01_m5_4_capability_security_fixture_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Point01_M5_4_capability_security_sandbox_control_plane_only",
        "status": "pass" if not errors else "fail_closed",
        "errors": errors,
        "evidence": evidence,
        "worker_started": False,
        "model_call_count": 0,
        "external_call_count": 0,
        "fixed_input_sha256": {
            str(policy_path.relative_to(ROOT)).replace("\\", "/"): _sha256(policy_path),
            "scripts/engineering/run_point01_m5_4_capability_security_fixtures.py": _sha256(Path(__file__).resolve()),
            "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"),
        },
        "boundary": "This fixture proves M5.4 admission only. It executes no network/path/tool/provider action: the sole protected mutation is the existing temporary-store checkpoint write. It admits no worker/service, Evidence/Writer, full-chain, business Case mutation or legacy authority change.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M5.4 capability security fixtures.")
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
