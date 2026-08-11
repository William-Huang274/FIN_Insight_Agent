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
from sec_agent.canonical_runtime.hitl_governance import ApprovalRegistryRecord, HITLGovernanceService
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.parallel_context import ParallelContextError, ParallelContextService
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore

DEFAULT_POLICY = ROOT / "configs/engineering_handoff/point01_m5_7_parallel_context_policy_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m5_7_parallel_context_fixture_result_v1_0.json"
NOW = datetime(2026, 7, 12, 16, 45, tzinfo=timezone.utc)


def _sha256(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry({"default_deny": True, "flags": [{"flag_id": "decision_surface_shadow_v0_1", "default_mode": "off", "allowed_modes": ["off", "shadow"], "required_capability_grants": ["point01.shadow.write"], "allowed_consumers": ["point01_shadow_compiler"], "forbidden_consumers": ["memo_writer", "evidence_runtime"]}]})


def _command(kind: str, payload: dict[str, Any], *, idem: str, expected: int = 0, at: datetime = NOW) -> CommandEnvelope:
    return CommandEnvelope(command_id=f"cmd-{idem}", command_type=kind, tenant_id="tenant-m5-7-fixture", project_id="project-m5-7-fixture", case_id="case-m5-7-fixture", actor_snapshot_ref="actor-m5-7-fixture", permission_snapshot_ref="permission-m5-7-fixture", policy_config_refs=("policy-m5-7",), idempotency_key=idem, expected_state_version=expected, correlation_id="correlation-m5-7-fixture", requested_at=at, payload=payload)


def _runtime(root: Path) -> RuntimeFacade:
    facade = RuntimeFacade(SQLiteCanonicalStore(root / "canonical.sqlite"), FileCanonicalObjectStore(root / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.7 fixture", "accountable_owner_ref": "lead"}, idem="case"))
    scheduler = DurableSchedulerService(facade)
    scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-parallel", "input_version_refs": ["summary-v1"], "queue_name": "parallel-shadow", "max_attempts": 2, "retry_budget": 1, "retry_policy_ref": "retry:bounded", "retryable_failure_types": ["transient"]}, idem="enqueue"))
    scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "parallel-shadow", "work_unit_id": "wu-parallel", "worker_ref": "worker", "attempt_id": "attempt-parallel-1", "lease_duration_seconds": 120}, idem="claim"))
    facade.create_checkpoint_version(_command("CREATE_CHECKPOINT_VERSION", {"work_unit_id": "wu-parallel", "attempt_id": "attempt-parallel-1", "worker_ref": "worker", "lease_fencing_token": 1, "checkpoint_id": "checkpoint-parallel", "expected_checkpoint_version": 0, "supersedes_version_id": None, "checkpoint_schema_ref": "checkpoint-schema-v1", "snapshot": {"cursor": "parallel"}}, expected=1, idem="checkpoint", at=NOW + timedelta(seconds=1)))
    return facade


def _snapshot(snapshot_id: str, branch_id: str, context: dict[str, Any]) -> CommandEnvelope:
    return _command("PARALLEL_CREATE_SNAPSHOT", {"snapshot_id": snapshot_id, "branch_id": branch_id, "work_unit_id": "wu-parallel", "attempt_id": "attempt-parallel-1", "worker_ref": "worker", "lease_fencing_token": 1, "checkpoint_ref": "checkpoint-parallel:v1", "dependency_refs": ["dep:product", "dep:financial"], "context_requirements": [{"context_block_id": "financial", "dependency_refs": ["dep:financial"], "context_key": "financial"}, {"context_block_id": "product", "dependency_refs": ["dep:product"], "context_key": "product"}], "context_snapshot": context}, expected=1, idem=f"snapshot-{snapshot_id}", at=NOW + timedelta(seconds=2))


def build_result(policy: dict[str, Any], *, policy_path: Path = DEFAULT_POLICY) -> dict[str, Any]:
    errors: list[str] = []
    if policy.get("policy_version") != "finsight_point01_m5_7_parallel_context_policy_v1_0" or policy.get("status") != "approved_for_deterministic_implementation": errors.append("policy_invalid")
    with TemporaryDirectory(prefix="point01_m5_7_parallel_") as directory:
        facade = _runtime(Path(directory))
        service = ParallelContextService(facade)
        mutable_context = {"financial": {"eps": 1}, "product": {"sku": "v1"}}
        service.create_snapshot(_snapshot("snapshot-main", "branch-main", mutable_context))
        mutable_context["financial"]["eps"] = 999
        isolated = facade.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-main")["context_snapshot"] == {"financial": {"eps": 1}, "product": {"sku": "v1"}}
        irrelevant = service.apply_delta(_command("PARALLEL_APPLY_DELTA", {"snapshot_id": "snapshot-main", "delta_id": "delta-market", "changed_dependency_refs": ["dep:market"], "impact_assessments": [{"dependency_ref": "dep:market", "semantic_impact": "immaterial", "rationale": "unbound market delta"}], "requested_action": "cancel"}, expected=1, idem="irrelevant", at=NOW + timedelta(seconds=3)))
        rebase = service.apply_delta(_command("PARALLEL_APPLY_DELTA", {"snapshot_id": "snapshot-main", "delta_id": "delta-financial", "changed_dependency_refs": ["dep:financial"], "impact_assessments": [{"dependency_ref": "dep:financial", "semantic_impact": "material", "rationale": "financial input changes valuation context"}], "requested_action": "rebase"}, expected=1, idem="rebase", at=NOW + timedelta(seconds=4)))
        rebase_requested = facade.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-main")
        recompiled = service.recompile_context(_command("PARALLEL_RECOMPILE_CONTEXT", {"snapshot_id": "snapshot-main", "decision_id": "impact:snapshot-main:delta-financial", "context_block_updates": {"financial": {"eps": 2}}, "dependency_ref_replacements": {"dep:financial": "dep:financial:v2"}}, expected=2, idem="recompile", at=NOW + timedelta(seconds=5)))
        second = _runtime(Path(directory) / "cancel")
        cancel_service = ParallelContextService(second)
        cancel_service.create_snapshot(_snapshot("snapshot-cancel", "branch-cancel", {"financial": {"eps": 1}, "product": {"sku": "p1"}}))
        cancellation = cancel_service.apply_delta(_command("PARALLEL_APPLY_DELTA", {"snapshot_id": "snapshot-cancel", "delta_id": "delta-product", "changed_dependency_refs": ["dep:product"], "impact_assessments": [{"dependency_ref": "dep:product", "semantic_impact": "material", "rationale": "product input changes branch thesis"}], "requested_action": "cancel"}, expected=1, idem="cancel", at=NOW + timedelta(seconds=3)))
        ambiguous_facade = _runtime(Path(directory) / "ambiguous")
        ambiguous_service = ParallelContextService(ambiguous_facade)
        ambiguous_service.create_snapshot(_snapshot("snapshot-ambiguous", "branch-ambiguous", {"financial": {"eps": 1}, "product": {"sku": "a1"}}))
        ambiguous_service.apply_delta(_command("PARALLEL_APPLY_DELTA", {"snapshot_id": "snapshot-ambiguous", "delta_id": "delta-ambiguous", "changed_dependency_refs": ["dep:financial"], "impact_assessments": [{"dependency_ref": "dep:financial", "semantic_impact": "ambiguous", "rationale": "requires accountable reviewer"}]}, expected=1, idem="ambiguous", at=NOW + timedelta(seconds=3)))
        resolution = _command("PARALLEL_RESOLVE_AMBIGUOUS_IMPACT", {"snapshot_id": "snapshot-ambiguous", "decision_id": "impact:snapshot-ambiguous:delta-ambiguous", "resolution_action": "rebase", "approval_id": "approval-ambiguous", "review_receipt_ref": "hitl-review:ambiguous"}, expected=2, idem="resolve-ambiguous", at=NOW + timedelta(seconds=4))
        forged_receipt_rejected = False
        try:
            ambiguous_service.resolve_ambiguous_impact(resolution)
        except ParallelContextError as error:
            forged_receipt_rejected = str(error) == "parallel_review_receipt_not_found"
        review_snapshot = ambiguous_facade.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-ambiguous")
        review_decision = ambiguous_facade.store.get_latest("canonical_parallel_impact_decisions", "impact:snapshot-ambiguous:delta-ambiguous")
        review_scope_digest = ambiguous_service.review_scope_digest(resolution, snapshot=review_snapshot, decision=review_decision, resolution_action="rebase")
        registry = HITLGovernanceService(ambiguous_facade, approval_registry={})
        registry.register_authority(_command("HITL_REGISTER_AUTHORITY", {}, idem="register-ambiguous-review", at=NOW + timedelta(seconds=3)), ApprovalRegistryRecord(approval_id="approval-ambiguous", approval_registry_ref="hitl-review:ambiguous", scope_digest=review_scope_digest, approval_state="active", expires_at=NOW + timedelta(minutes=5)))
        ambiguous_service.resolve_ambiguous_impact(resolution)
        ambiguous_resolved = ambiguous_facade.store.get_latest("canonical_parallel_impact_decisions", "impact:snapshot-ambiguous:delta-ambiguous:resolution")
        main = facade.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-main")
        cancelled = second.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-cancel")
        if not isolated: errors.append("shared_mutable_context_detected")
        if irrelevant.state_version_after != 1: errors.append("irrelevant_delta_changed_branch")
        if rebase_requested["branch_state"] != "rebase_required" or rebase.state_version_after != 2: errors.append("rebase_not_requested")
        if main["branch_state"] != "active" or main["context_snapshot"]["financial"] != {"eps": 2} or main["dependency_refs"] != ["dep:financial:v2", "dep:product"] or recompiled.state_version_after != 3: errors.append("context_recompile_not_materialized")
        if cancelled["branch_state"] != "cancelled" or cancellation.state_version_after != 2: errors.append("relevant_delta_not_cancelled")
        ambiguous_receipt_verified = bool(ambiguous_resolved and ambiguous_resolved.get("review_approval_id") == "approval-ambiguous" and ambiguous_resolved.get("review_receipt_ref") == "hitl-review:ambiguous" and ambiguous_resolved.get("review_scope_digest") == review_scope_digest)
        if not forged_receipt_rejected or not ambiguous_receipt_verified: errors.append("ambiguous_review_receipt_not_authoritatively_verified")
        evidence = {"snapshot_isolated": isolated, "irrelevant_action": facade.store.get_latest("canonical_parallel_impact_decisions", "impact:snapshot-main:delta-market")["action"], "rebase_requested_state": rebase_requested["branch_state"], "rebase_context_recompile_requested": facade.store.get_latest("canonical_parallel_impact_decisions", "impact:snapshot-main:delta-financial")["context_recompile_requested"], "recompiled_snapshot_state": main["branch_state"], "recompiled_context": main["context_snapshot"]["financial"], "cancel_state": cancelled["branch_state"], "forged_ambiguous_receipt_rejected": forged_receipt_rejected, "ambiguous_receipt_verified": ambiguous_receipt_verified}
    return {"result_version": "finsight_point01_m5_7_parallel_context_fixture_result_v1_0", "generated_at": datetime.now(timezone.utc).isoformat(), "scope": "Point01_M5_7_parallel_snapshot_selective_invalidation_control_plane_only", "status": "pass" if not errors else "fail_closed", "errors": errors, "evidence": evidence, "worker_started": False, "model_call_count": 0, "external_call_count": 0, "fixed_input_sha256": {str(policy_path.relative_to(ROOT)).replace("\\", "/"): _sha256(policy_path), "scripts/engineering/run_point01_m5_7_parallel_context_fixtures.py": _sha256(Path(__file__).resolve()), "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md": _sha256(ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md")}, "boundary": "This fixture proves persistent immutable parallel snapshots and selective invalidation only. It starts no parallel worker or service, and admits no provider, external tool, Evidence/Writer, full-chain, business Case mutation or legacy authority change."}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Point 01 M5.7 parallel context fixtures.")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY); parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(); policy_path = args.policy if args.policy.is_absolute() else ROOT / args.policy; output_path = args.output if args.output.is_absolute() else ROOT / args.output
    result = build_result(json.loads(policy_path.read_text(encoding="utf-8")), policy_path=policy_path)
    output_path.parent.mkdir(parents=True, exist_ok=True); output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output_path), "errors": result["errors"]}, ensure_ascii=False)); return 0 if result["status"] == "pass" else 1


if __name__ == "__main__": raise SystemExit(main())
