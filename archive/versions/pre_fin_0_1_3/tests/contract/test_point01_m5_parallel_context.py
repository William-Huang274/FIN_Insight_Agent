from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.hitl_governance import ApprovalRegistryRecord, HITLGovernanceService
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.parallel_context import ParallelContextError, ParallelContextService
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract

BASE_TIME = datetime(2026, 7, 12, 16, 30, tzinfo=timezone.utc)


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry({"default_deny": True, "flags": [{"flag_id": "decision_surface_shadow_v0_1", "default_mode": "off", "allowed_modes": ["off", "shadow"], "required_capability_grants": ["point01.shadow.write"], "allowed_consumers": ["point01_shadow_compiler"], "forbidden_consumers": ["memo_writer", "evidence_runtime"]}]})


def _command(command_type: str, payload: dict, *, idem: str, expected: int = 0, at: datetime = BASE_TIME) -> CommandEnvelope:
    return CommandEnvelope(command_id=f"cmd-{idem}", command_type=command_type, tenant_id="tenant-m5-7", project_id="project-m5-7", case_id="case-m5-7", actor_snapshot_ref="actor-m5-7", permission_snapshot_ref="permission-m5-7", policy_config_refs=("policy-m5-7",), idempotency_key=idem, expected_state_version=expected, correlation_id="correlation-m5-7", requested_at=at, payload=payload)


def _runtime(tmp_path) -> RuntimeFacade:
    facade = RuntimeFacade(SQLiteCanonicalStore(tmp_path / "canonical.sqlite"), FileCanonicalObjectStore(tmp_path / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.7 fixture", "accountable_owner_ref": "lead-m5-7"}, idem="case"))
    scheduler = DurableSchedulerService(facade)
    scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-parallel", "input_version_refs": ["summary-v1"], "queue_name": "parallel-shadow", "max_attempts": 2, "retry_budget": 1, "retry_policy_ref": "retry:bounded", "retryable_failure_types": ["transient"]}, idem="enqueue"))
    scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "parallel-shadow", "work_unit_id": "wu-parallel", "worker_ref": "worker-parallel", "attempt_id": "attempt-parallel-1", "lease_duration_seconds": 120}, idem="claim"))
    facade.create_checkpoint_version(_command("CREATE_CHECKPOINT_VERSION", {"work_unit_id": "wu-parallel", "attempt_id": "attempt-parallel-1", "worker_ref": "worker-parallel", "lease_fencing_token": 1, "checkpoint_id": "checkpoint-parallel", "expected_checkpoint_version": 0, "supersedes_version_id": None, "checkpoint_schema_ref": "checkpoint-schema-v1", "snapshot": {"cursor": "parallel"}}, expected=1, idem="checkpoint", at=BASE_TIME + timedelta(seconds=1)))
    return facade


def _snapshot_command(*, snapshot_id: str = "snapshot-main", branch_id: str = "branch-main", context: dict | None = None) -> CommandEnvelope:
    return _command("PARALLEL_CREATE_SNAPSHOT", {"snapshot_id": snapshot_id, "branch_id": branch_id, "work_unit_id": "wu-parallel", "attempt_id": "attempt-parallel-1", "worker_ref": "worker-parallel", "lease_fencing_token": 1, "checkpoint_ref": "checkpoint-parallel:v1", "dependency_refs": ["dep:product", "dep:financial"], "context_snapshot": context or {"role": "fundamental", "facts": ["f1"]}}, expected=1, idem=f"snapshot-{snapshot_id}", at=BASE_TIME + timedelta(seconds=2))


def _assessment(reference: str, impact: str) -> list[dict[str, str]]:
    return [{"dependency_ref": reference, "semantic_impact": impact, "rationale": f"fixture:{impact}:{reference}"}]


def test_snapshot_isolation_and_irrelevant_delta_continue(tmp_path) -> None:
    facade = _runtime(tmp_path)
    service = ParallelContextService(facade)
    source_context = {"role": "fundamental", "facts": ["f1"]}
    service.create_snapshot(_snapshot_command(context=source_context))
    source_context["facts"].append("mutated-after-snapshot")
    stored = facade.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-main")
    assert stored["context_snapshot"] == {"role": "fundamental", "facts": ["f1"]}

    result = service.apply_delta(_command("PARALLEL_APPLY_DELTA", {"snapshot_id": "snapshot-main", "delta_id": "delta-unrelated", "changed_dependency_refs": ["dep:market"], "impact_assessments": _assessment("dep:market", "immaterial"), "requested_action": "cancel"}, expected=1, idem="irrelevant", at=BASE_TIME + timedelta(seconds=3)))
    assert result.state_version_after == 1
    decision = facade.store.get_latest("canonical_parallel_impact_decisions", "impact:snapshot-main:delta-unrelated")
    assert decision["action"] == "continue"
    assert facade.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-main")["branch_state"] == "active"


def test_relevant_delta_requires_rebase_or_cancels_isolated_branch(tmp_path) -> None:
    facade = _runtime(tmp_path)
    service = ParallelContextService(facade)
    service.create_snapshot(_snapshot_command())
    rebase = service.apply_delta(_command("PARALLEL_APPLY_DELTA", {"snapshot_id": "snapshot-main", "delta_id": "delta-financial", "changed_dependency_refs": ["dep:financial"], "impact_assessments": _assessment("dep:financial", "material"), "requested_action": "rebase"}, expected=1, idem="rebase", at=BASE_TIME + timedelta(seconds=3)))
    assert rebase.state_version_after == 2
    rebased = facade.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-main")
    assert rebased["branch_state"] == "rebase_required"
    decision = facade.store.get_latest("canonical_parallel_impact_decisions", "impact:snapshot-main:delta-financial")
    assert decision["context_recompile_requested"] is True
    with pytest.raises(Exception, match="parallel_delta_requires_active_branch"):
        service.apply_delta(_command("PARALLEL_APPLY_DELTA", {"snapshot_id": "snapshot-main", "delta_id": "delta-repeat", "changed_dependency_refs": ["dep:financial"], "impact_assessments": _assessment("dep:financial", "material"), "requested_action": "cancel"}, expected=2, idem="repeat", at=BASE_TIME + timedelta(seconds=4)))

    second = _runtime(tmp_path / "cancel")
    cancellation = ParallelContextService(second)
    cancellation.create_snapshot(_snapshot_command(snapshot_id="snapshot-cancel", branch_id="branch-cancel"))
    cancellation.apply_delta(_command("PARALLEL_APPLY_DELTA", {"snapshot_id": "snapshot-cancel", "delta_id": "delta-product", "changed_dependency_refs": ["dep:product"], "impact_assessments": _assessment("dep:product", "material"), "requested_action": "cancel"}, expected=1, idem="cancel", at=BASE_TIME + timedelta(seconds=3)))
    assert second.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-cancel")["branch_state"] == "cancelled"
    assert cancellation.branch_view(case_id="case-m5-7")["active_branch_count"] == 0


def test_context_snapshot_bounds_fail_before_store_mutation(tmp_path) -> None:
    facade = _runtime(tmp_path)
    service = ParallelContextService(facade)
    with pytest.raises(ParallelContextError, match="parallel_context_snapshot_size_exceeded"):
        service.create_snapshot(_snapshot_command(context={"oversize": "x" * 40000}))
    assert facade.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-main") is None


def test_material_rebase_compiles_new_context_snapshot_and_ambiguous_delta_requires_review(tmp_path) -> None:
    facade = _runtime(tmp_path)
    service = ParallelContextService(facade)
    snapshot = _snapshot_command(context={"financial": {"eps": 1}, "product": {"sku": "v1"}}).model_copy(update={"payload": {**_snapshot_command(context={"financial": {"eps": 1}, "product": {"sku": "v1"}}).payload, "context_requirements": [{"context_block_id": "financial", "dependency_refs": ["dep:financial"], "context_key": "financial"}, {"context_block_id": "product", "dependency_refs": ["dep:product"], "context_key": "product"}]}})
    service.create_snapshot(snapshot)
    service.apply_delta(_command("PARALLEL_APPLY_DELTA", {"snapshot_id": "snapshot-main", "delta_id": "delta-financial-v2", "changed_dependency_refs": ["dep:financial"], "impact_assessments": _assessment("dep:financial", "material"), "requested_action": "rebase"}, expected=1, idem="semantic-rebase", at=BASE_TIME + timedelta(seconds=3)))
    recompiled = service.recompile_context(_command("PARALLEL_RECOMPILE_CONTEXT", {"snapshot_id": "snapshot-main", "decision_id": "impact:snapshot-main:delta-financial-v2", "context_block_updates": {"financial": {"eps": 2}}, "dependency_ref_replacements": {"dep:financial": "dep:financial:v2"}}, expected=2, idem="compile-context", at=BASE_TIME + timedelta(seconds=4)))
    current = facade.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-main")
    original = facade.store.get_version("canonical_parallel_snapshot_versions", "snapshot-main", 1)
    assert recompiled.state_version_after == 3
    assert current["branch_state"] == "active"
    assert current["context_snapshot"]["financial"] == {"eps": 2}
    assert current["dependency_refs"] == ["dep:financial:v2", "dep:product"]
    assert original["context_snapshot"]["financial"] == {"eps": 1}

    second = _runtime(tmp_path / "ambiguous")
    ambiguous = ParallelContextService(second)
    ambiguous.create_snapshot(_snapshot_command(snapshot_id="snapshot-ambiguous", branch_id="branch-ambiguous"))
    review = ambiguous.apply_delta(_command("PARALLEL_APPLY_DELTA", {"snapshot_id": "snapshot-ambiguous", "delta_id": "delta-ambiguous", "changed_dependency_refs": ["dep:financial"], "impact_assessments": _assessment("dep:financial", "ambiguous")}, expected=1, idem="ambiguous", at=BASE_TIME + timedelta(seconds=3)))
    assert review.state_version_after == 2
    assert second.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-ambiguous")["branch_state"] == "review_required"
    resolution = _command("PARALLEL_RESOLVE_AMBIGUOUS_IMPACT", {"snapshot_id": "snapshot-ambiguous", "decision_id": "impact:snapshot-ambiguous:delta-ambiguous", "resolution_action": "rebase", "approval_id": "approval-ambiguous", "review_receipt_ref": "manual-review:fixture"}, expected=2, idem="resolve-ambiguous", at=BASE_TIME + timedelta(seconds=4))
    with pytest.raises(ParallelContextError, match="parallel_review_receipt_not_found"):
        ambiguous.resolve_ambiguous_impact(resolution)
    review_snapshot = second.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-ambiguous")
    review_decision = second.store.get_latest("canonical_parallel_impact_decisions", "impact:snapshot-ambiguous:delta-ambiguous")
    scope_digest = ambiguous.review_scope_digest(resolution, snapshot=review_snapshot, decision=review_decision, resolution_action="rebase")
    registry = HITLGovernanceService(second, approval_registry={})
    registry.register_authority(_command("HITL_REGISTER_AUTHORITY", {}, idem="register-ambiguous-review", at=BASE_TIME + timedelta(seconds=3)), ApprovalRegistryRecord(approval_id="approval-ambiguous", approval_registry_ref="manual-review:fixture", scope_digest=scope_digest, approval_state="active", expires_at=BASE_TIME + timedelta(minutes=5)))
    ambiguous.resolve_ambiguous_impact(resolution)
    assert second.store.get_latest("canonical_parallel_snapshot_versions", "snapshot-ambiguous")["branch_state"] == "rebase_required"
    stored_resolution = second.store.get_latest("canonical_parallel_impact_decisions", "impact:snapshot-ambiguous:delta-ambiguous:resolution")
    assert stored_resolution["review_scope_digest"] == scope_digest


@pytest.mark.parametrize(
    ("label", "approval_state", "scope_override", "ref_override", "expiry", "error"),
    [
        ("wrong-scope", "active", "forged-scope", None, BASE_TIME + timedelta(minutes=5), "parallel_review_receipt_ref_or_scope_mismatch"),
        ("wrong-ref", "active", None, "forged-ref", BASE_TIME + timedelta(minutes=5), "parallel_review_receipt_ref_or_scope_mismatch"),
        ("revoked", "revoked", None, None, BASE_TIME + timedelta(minutes=5), "parallel_review_receipt_not_active"),
        ("expired", "active", None, None, BASE_TIME + timedelta(seconds=3), "parallel_review_receipt_expired"),
    ],
)
def test_ambiguous_resolution_rejects_forged_revoked_or_expired_registry_receipt(tmp_path, label, approval_state, scope_override, ref_override, expiry, error) -> None:
    facade = _runtime(tmp_path / label)
    service = ParallelContextService(facade)
    service.create_snapshot(_snapshot_command(snapshot_id=f"snapshot-{label}", branch_id=f"branch-{label}"))
    decision_id = f"impact:snapshot-{label}:delta-{label}"
    service.apply_delta(_command("PARALLEL_APPLY_DELTA", {"snapshot_id": f"snapshot-{label}", "delta_id": f"delta-{label}", "changed_dependency_refs": ["dep:financial"], "impact_assessments": _assessment("dep:financial", "ambiguous")}, expected=1, idem=f"ambiguous-{label}", at=BASE_TIME + timedelta(seconds=3)))
    resolution = _command("PARALLEL_RESOLVE_AMBIGUOUS_IMPACT", {"snapshot_id": f"snapshot-{label}", "decision_id": decision_id, "resolution_action": "cancel", "approval_id": f"approval-{label}", "review_receipt_ref": "review:expected"}, expected=2, idem=f"resolution-{label}", at=BASE_TIME + timedelta(seconds=4))
    snapshot = facade.store.get_latest("canonical_parallel_snapshot_versions", f"snapshot-{label}")
    decision = facade.store.get_latest("canonical_parallel_impact_decisions", decision_id)
    scope = service.review_scope_digest(resolution, snapshot=snapshot, decision=decision, resolution_action="cancel")
    HITLGovernanceService(facade, approval_registry={}).register_authority(_command("HITL_REGISTER_AUTHORITY", {}, idem=f"registry-{label}", at=BASE_TIME + timedelta(seconds=3)), ApprovalRegistryRecord(approval_id=f"approval-{label}", approval_registry_ref=ref_override or "review:expected", scope_digest=scope_override or scope, approval_state=approval_state, expires_at=expiry))
    with pytest.raises(ParallelContextError, match=error):
        service.resolve_ambiguous_impact(resolution)
