from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sec_agent.canonical_runtime.budget_control import (
    BudgetControlService,
    BudgetExceededError,
    BudgetPolicy,
    BudgetReservationRequest,
)
from sec_agent.canonical_runtime.durable_scheduler import DurableSchedulerService
from sec_agent.canonical_runtime.facade import IllegalStateTransition, RuntimeFacade
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.recovery_lifecycle import RecoveryLifecycleService
from sec_agent.canonical_runtime.store import SQLiteCanonicalStore


pytestmark = pytest.mark.fast_contract

BASE_TIME = datetime(2026, 7, 12, 15, 30, tzinfo=timezone.utc)


def _flags() -> FeatureFlagRegistry:
    return FeatureFlagRegistry({"default_deny": True, "flags": [{"flag_id": "decision_surface_shadow_v0_1", "default_mode": "off", "allowed_modes": ["off", "shadow"], "required_capability_grants": ["point01.shadow.write"], "allowed_consumers": ["point01_shadow_compiler"], "forbidden_consumers": ["memo_writer", "evidence_runtime"]}]})


def _command(command_type: str, payload: dict, *, idem: str, expected: int = 0, at: datetime = BASE_TIME) -> CommandEnvelope:
    return CommandEnvelope(command_id=f"cmd-{idem}", command_type=command_type, tenant_id="tenant-m5-5", project_id="project-m5-5", case_id="case-m5-5", actor_snapshot_ref="actor-m5-5", permission_snapshot_ref="permission-m5-5", policy_config_refs=("policy-m5-5",), idempotency_key=idem, expected_state_version=expected, correlation_id="correlation-m5-5", requested_at=at, payload=payload)


def _runtime(tmp_path) -> tuple[RuntimeFacade, DurableSchedulerService]:
    facade = RuntimeFacade(SQLiteCanonicalStore(tmp_path / "canonical.sqlite"), FileCanonicalObjectStore(tmp_path / "objects"), _flags(), mode="shadow", grants={"point01.shadow.write"})
    facade.create_research_case(_command("CREATE_RESEARCH_CASE", {"query": "M5.5 fixture", "accountable_owner_ref": "lead-m5-5"}, idem="case"))
    scheduler = DurableSchedulerService(facade)
    scheduler.enqueue(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-budget", "input_version_refs": ["summary-v1"], "queue_name": "budget-shadow", "max_attempts": 2, "retry_budget": 1, "retry_policy_ref": "retry:bounded", "retryable_failure_types": ["transient"]}, idem="enqueue"))
    scheduler.claim_next(_command("SCHEDULER_CLAIM_NEXT", {"queue_name": "budget-shadow", "work_unit_id": "wu-budget", "worker_ref": "worker-budget", "attempt_id": "attempt-budget-1", "lease_duration_seconds": 60}, idem="claim"))
    return facade, scheduler


def _policy(*, tokens: int = 10, tools: int = 3, seconds: int = 60) -> BudgetPolicy:
    return BudgetPolicy(policy_id="budget-policy-v1", case_token_units=tokens, work_unit_token_units=tokens, attempt_token_units=tokens, case_tool_calls=tools, work_unit_tool_calls=tools, attempt_tool_calls=tools, case_time_seconds=seconds, work_unit_time_seconds=seconds, attempt_time_seconds=seconds)


def _reservation(reservation_id: str, *, tokens: int, tools: int = 0, seconds: int = 1, fallback: bool = False) -> BudgetReservationRequest:
    return BudgetReservationRequest(reservation_id=reservation_id, work_unit_id="wu-budget", attempt_id="attempt-budget-1", token_units=tokens, tool_calls=tools, time_seconds=seconds, is_fallback=fallback)


def _checkpoint_command(*, idem: str) -> CommandEnvelope:
    return _command("CREATE_CHECKPOINT_VERSION", {"work_unit_id": "wu-budget", "attempt_id": "attempt-budget-1", "worker_ref": "worker-budget", "lease_fencing_token": 1, "checkpoint_id": "checkpoint-budget", "expected_checkpoint_version": 0, "supersedes_version_id": None, "checkpoint_schema_ref": "checkpoint-schema-v1", "snapshot": {"cursor": "budget-phase"}}, expected=1, idem=idem, at=BASE_TIME + timedelta(seconds=1))


def test_budget_reserves_before_checkpoint_admission_and_refund_is_traceable(tmp_path) -> None:
    facade, _ = _runtime(tmp_path)
    budgets = BudgetControlService(facade, policy=_policy())
    result = budgets.execute_checkpoint_write(_checkpoint_command(idem="checkpoint"), _reservation("reserve-checkpoint", tokens=4, tools=1, seconds=10))
    assert result.artifact_refs == ("checkpoint-budget:v1",)
    assert [entry["action"] for entry in budgets.ledger_view()["ledger"]] == ["reserved", "consumed"]

    budgets.reserve(_reservation("reserve-refund", tokens=3, seconds=5))
    budgets.refund("reserve-refund", token_units=2, time_seconds=3, reason="unused_tail")
    ledger = budgets.ledger_view()
    assert ledger["ledger"][-1]["action"] == "refunded"
    assert ledger["ledger"][-1]["reason"] == "unused_tail"
    assert ledger["slo_observation"]["refund_count"] == 1


def test_fallback_cannot_overrun_hierarchical_token_tool_or_time_budget(tmp_path) -> None:
    facade, _ = _runtime(tmp_path)
    budgets = BudgetControlService(facade, policy=_policy(tokens=10, tools=2, seconds=10))
    budgets.reserve(_reservation("primary", tokens=8, tools=1, seconds=8))
    for request, scope in [(_reservation("fallback-tokens", tokens=3, fallback=True), "case:token_units"), (_reservation("fallback-tools", tokens=1, tools=2, fallback=True), "case:tool_calls"), (_reservation("fallback-time", tokens=1, seconds=3, fallback=True), "case:time_seconds")]:
        with pytest.raises(BudgetExceededError) as raised:
            budgets.reserve(request)
        assert raised.value.stop.exhausted_scope == scope
    assert budgets.ledger_view()["slo_observation"]["terminal_stop_count"] == 3


def test_budget_exhaustion_applies_terminal_stop_and_prevents_retry(tmp_path) -> None:
    facade, scheduler = _runtime(tmp_path)
    budgets = BudgetControlService(facade, policy=_policy(tokens=1))
    with pytest.raises(BudgetExceededError) as raised:
        budgets.reserve(_reservation("over-budget", tokens=2))
    budgets.apply_terminal_stop(
        _command("BUDGET_STOP", {"work_unit_id": "wu-budget", "attempt_id": "attempt-budget-1", "worker_ref": "worker-budget", "lease_fencing_token": 1}, expected=1, idem="apply-stop", at=BASE_TIME + timedelta(seconds=1)),
        raised.value,
    )
    assert facade.store.get_latest("canonical_work_units", "wu-budget")["state"] == "failed"
    with pytest.raises(IllegalStateTransition, match="recovery_requires_retryable_failed_work_unit"):
        RecoveryLifecycleService(facade, scheduler=scheduler).retry(_command("RECOVERY_RETRY", {"work_unit_id": "wu-budget", "queue_name": "budget-shadow", "worker_ref": "worker-retry"}, expected=2, idem="retry-after-budget"))
    assert budgets.ledger_view()["stops"][0]["code"] == "budget_exhausted"


def test_budget_authority_survives_restart_and_rebuilds_persisted_ledger(tmp_path) -> None:
    facade, _ = _runtime(tmp_path)
    budgets = BudgetControlService(facade, policy=_policy(tokens=10))
    budgets.reserve(_reservation("restart-primary", tokens=8, seconds=4))
    budgets.refund("restart-primary", token_units=3, time_seconds=1, reason="restart-proof")
    with pytest.raises(BudgetExceededError):
        budgets.reserve(_reservation("restart-stop", tokens=6))

    restarted = RuntimeFacade(
        SQLiteCanonicalStore(tmp_path / "canonical.sqlite"),
        FileCanonicalObjectStore(tmp_path / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    recovered = BudgetControlService(restarted, policy=_policy(tokens=10)).ledger_view()
    assert [entry["action"] for entry in recovered["ledger"]] == ["reserved", "refunded", "terminal_stop"]
    assert recovered["ledger"][1]["reason"] == "restart-proof"
    assert recovered["stops"][0]["exhausted_scope"] == "case:token_units"


def test_pending_checkpoint_operation_releases_reservation_when_checkpoint_transaction_fails(tmp_path) -> None:
    facade, _ = _runtime(tmp_path)
    budgets = BudgetControlService(facade, policy=_policy())
    invalid_checkpoint = _checkpoint_command(idem="checkpoint-fails").model_copy(
        update={"payload": {**_checkpoint_command(idem="checkpoint-fails").payload, "expected_checkpoint_version": 1}}
    )
    with pytest.raises(Exception, match="stale_checkpoint_version"):
        budgets.execute_checkpoint_write(invalid_checkpoint, _reservation("pending-release", tokens=3, tools=1, seconds=5))
    reservation = facade.store.get_latest("canonical_budget_reservation_versions", "pending-release")
    assert reservation["reservation_state"] == "released"
    assert reservation["protected_operation_state"] == "reconciled_released"
    assert budgets.ledger_view()["ledger"][-1]["action"] == "reconciled_refund"


def test_reconciliation_consumes_pending_reservation_when_checkpoint_is_already_committed(tmp_path) -> None:
    facade, _ = _runtime(tmp_path)
    budgets = BudgetControlService(facade, policy=_policy())
    reservation = _reservation("pending-consume", tokens=3, tools=1, seconds=5)
    checkpoint = _checkpoint_command(idem="checkpoint-before-reconcile")
    budgets._reserve(reservation, checkpoint_command=checkpoint)
    facade.create_checkpoint_version(checkpoint)
    assert budgets.reconcile_pending_operation("pending-consume") == "reconciled_consumed"
    recovered = facade.store.get_latest("canonical_budget_reservation_versions", "pending-consume")
    assert recovered["reservation_state"] == "consumed"
    assert recovered["protected_operation_state"] == "reconciled_consumed"
    assert recovered["checkpoint_ref"] == "checkpoint-budget:v1"
