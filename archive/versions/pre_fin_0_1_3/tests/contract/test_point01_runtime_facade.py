from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from sec_agent.canonical_runtime.facade import (
    ArtifactValidationError,
    IllegalStateTransition,
    LeaseValidationError,
    LegacyBindingConflict,
    RuntimeFacade,
    StaleInputHead,
    UnknownEventSchema,
)
from sec_agent.canonical_runtime.feature_flags import FeatureFlagError, FeatureFlagRegistry
from sec_agent.canonical_runtime.models import CommandEnvelope, EventEnvelope, canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import IdempotencyConflict, SQLiteCanonicalStore, StaleStateVersion


pytestmark = pytest.mark.fast_contract


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
                    "allowed_consumers": ["point01_shadow_compiler", "point01_shadow_comparator", "point01_reviewer_report"],
                    "forbidden_consumers": ["memo_writer", "evidence_runtime"],
                }
            ],
        }
    )


def _facade(tmp_path, *, mode: str = "shadow") -> RuntimeFacade:
    return RuntimeFacade(
        SQLiteCanonicalStore(tmp_path / "canonical.sqlite"),
        FileCanonicalObjectStore(tmp_path / "objects"),
        _flags(),
        mode=mode,
        grants={"point01.shadow.write"},
    )


def _command(command_type: str, payload: dict, *, case_id: str | None = "case-1", expected: int = 0, idem: str | None = None) -> CommandEnvelope:
    return CommandEnvelope(
        command_id=f"cmd-{command_type.lower()}-{idem or '1'}",
        command_type=command_type,
        tenant_id="tenant-test",
        project_id="project-test",
        case_id=case_id,
        actor_snapshot_ref="actor-1",
        permission_snapshot_ref="permission-1",
        policy_config_refs=("policy-point01",),
        idempotency_key=idem or f"idem-{command_type.lower()}",
        expected_state_version=expected,
        correlation_id="correlation-1",
        requested_at=datetime.now(timezone.utc),
        payload=payload,
    )


def _create_case(facade: RuntimeFacade) -> None:
    facade.create_research_case(
        _command(
            "CREATE_RESEARCH_CASE",
            {
                "query": "Compare software demand quality.",
                "universe": ["CRM", "NOW"],
                "accountable_owner_ref": "lead-1",
                "legacy_system": "legacy-test",
                "legacy_task_id": "legacy-task-1",
                "legacy_run_id": "legacy-run-1",
            },
        )
    )


def _start_work(facade: RuntimeFacade) -> None:
    facade.create_work_unit(
        _command(
            "CREATE_WORK_UNIT",
            {"work_unit_id": "wu-1", "work_unit_type": "decision_surface_compile", "input_version_refs": ["summary-1"]},
        )
    )
    facade.start_attempt(
        _command("START_ATTEMPT", {"work_unit_id": "wu-1", "attempt_id": "attempt-1", "worker_ref": "fixture-worker"})
    )


def _audit_scope(status: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": "finsight_point01_canonical_runtime_v1_0",
        "tenant_id": "tenant-test",
        "project_id": "project-test",
        "case_id": "case-1",
        "created_at": now,
        "recorded_at": now,
        "actor_snapshot_ref": "actor-1",
        "permission_snapshot_ref": "permission-1",
        "policy_config_refs": ["policy-point01"],
        "correlation_id": "correlation-1",
        "current_status": status,
    }


def _bundle() -> dict:
    contract = {
        **_audit_scope("shadow_compiled"),
        "contract_id": "contract-1",
        "contract_version_id": "contract-1:v1",
        "contract_version": 1,
        "query": "Compare software demand quality.",
        "as_of": datetime.now(timezone.utc).isoformat(),
        "universe": ["CRM", "NOW"],
        "language": "en",
        "compiler_policy_ref": "compiler-policy-1",
        "required_cell_ids": ["cell-1"],
    }
    cell = {
        **_audit_scope("shadow_compiled"),
        "contract_version_id": "contract-1:v1",
        "cell_id": "cell-1",
        "cell_version_id": "cell-1:v1",
        "cell_version": 1,
        "decision_question": "Is demand durable?",
        "origin_type": "universal",
        "owner_role": "software_operator",
        "materiality": "high",
        "stop_rule": "one issuer fact and one counterevidence route",
    }
    slot = {
        **_audit_scope("shadow_required"),
        "cell_version_id": "cell-1:v1",
        "evidence_slot_id": "slot-1",
        "slot_version_id": "slot-1:v1",
        "slot_version": 1,
        "evidence_role": "demand_quality",
        "entity_scope": ["CRM", "NOW"],
        "period_scope": "latest_fiscal_quarter",
        "source_policy_ref": "issuer_first",
        "acceptance_role": "primary_or_context",
        "required": True,
    }
    return {"contract": contract, "cells": [cell], "slots": [slot], "gaps": []}


def test_feature_flag_defaults_off_and_shadow_is_permissioned(tmp_path) -> None:
    assert _flags().default_mode("decision_surface_shadow_v0_1") == "off"
    facade = _facade(tmp_path, mode="off")
    with pytest.raises(FeatureFlagError, match="feature_flag_off"):
        _create_case(facade)
    with pytest.raises(FeatureFlagError, match="shadow_authority_violation"):
        _flags().authorize(
            "decision_surface_shadow_v0_1",
            mode="shadow",
            consumer="memo_writer",
            grants={"point01.shadow.write"},
        )


def test_case_creation_is_idempotent_and_conflicting_payload_is_rejected(tmp_path) -> None:
    facade = _facade(tmp_path)
    command = _command(
        "CREATE_RESEARCH_CASE",
        {"query": "Question", "accountable_owner_ref": "lead-1"},
        idem="same",
    )
    first = facade.create_research_case(command)
    second = facade.create_research_case(command)
    assert first.status == "succeeded"
    assert second.reused_idempotent_result is True
    changed = command.model_copy(update={"payload": {"query": "Different", "accountable_owner_ref": "lead-1"}})
    with pytest.raises(IdempotencyConflict):
        facade.create_research_case(changed)


def test_stale_state_rejected_and_bundle_commits_atomically(tmp_path) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    facade.create_work_unit(
        _command("CREATE_WORK_UNIT", {"work_unit_id": "wu-1", "input_version_refs": []})
    )
    with pytest.raises(StaleStateVersion):
        facade.start_attempt(
            _command("START_ATTEMPT", {"work_unit_id": "wu-1", "attempt_id": "attempt-x"}, expected=9)
        )
    facade.start_attempt(
        _command("START_ATTEMPT", {"work_unit_id": "wu-1", "attempt_id": "attempt-1", "worker_ref": "fixture"})
    )
    with pytest.raises(IllegalStateTransition, match="work_unit_must_be_pending"):
        facade.start_attempt(
            _command(
                "START_ATTEMPT",
                {"work_unit_id": "wu-1", "attempt_id": "attempt-2", "worker_ref": "fixture"},
                expected=1,
                idem="second-attempt",
            )
        )
    result = facade.commit_decision_surface_bundle(
        _command(
            "COMMIT_DECISION_SURFACE_BUNDLE",
            {"work_unit_id": "wu-1", "attempt_id": "attempt-1", "artifact_id": "artifact-1", "bundle": _bundle()},
            expected=1,
        )
    )
    assert result.status == "succeeded"
    assert result.artifact_refs == ("artifact-1:v1",)
    assert facade.store.get_latest("canonical_decision_surface_contract_versions", "contract-1") is not None
    assert facade.store.get_latest("canonical_work_units", "wu-1")["state"] == "succeeded"


def test_replay_is_deterministic_and_kill_switch_preserves_history(tmp_path) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    _start_work(facade)
    facade.commit_decision_surface_bundle(
        _command(
            "COMMIT_DECISION_SURFACE_BUNDLE",
            {"work_unit_id": "wu-1", "attempt_id": "attempt-1", "artifact_id": "artifact-rollback", "bundle": _bundle()},
            expected=1,
            idem="rollback-fixture",
        )
    )
    before = facade.replay_projection()
    assert before == facade.replay_projection()
    binding_identity = {
        "legacy_system": "legacy-test",
        "legacy_store_id": "default",
        "legacy_task_id": "legacy-task-1",
        "legacy_run_id": "legacy-run-1",
    }
    binding_id = f"binding_{canonical_digest(binding_identity)[:24]}"
    legacy_authority_before = facade.store.get_latest("canonical_task_run_bindings", binding_id)
    assert legacy_authority_before["legacy_authority_status"] == "authoritative"
    facade.store.set_kill_switch(True)
    with pytest.raises(Exception, match="kill_switch"):
        facade.create_work_unit(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-after-kill"}))
    assert facade.replay_projection() == before
    assert facade.store.get_latest("canonical_task_run_bindings", binding_id) == legacy_authority_before
    assert facade.store.get_latest("canonical_artifact_versions", "artifact-rollback") is not None


def test_object_store_failure_publishes_no_sql_rows(tmp_path) -> None:
    class FailingObjectStore:
        def put_json(self, payload, *, namespace, artifact_type):
            raise OSError("fixture_object_store_failure")

        def get_json(self, object_key, *, expected_digest=None):
            raise AssertionError("not called")

    base = _facade(tmp_path)
    _create_case(base)
    _start_work(base)
    failing = RuntimeFacade(
        base.store,
        FailingObjectStore(),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    with pytest.raises(OSError, match="fixture_object_store_failure"):
        failing.commit_decision_surface_bundle(
            _command(
                "COMMIT_DECISION_SURFACE_BUNDLE",
                {"work_unit_id": "wu-1", "attempt_id": "attempt-1", "artifact_id": "artifact-fail", "bundle": _bundle()},
                expected=1,
            )
        )
    assert base.store.get_latest("canonical_artifact_versions", "artifact-fail") is None
    assert base.store.get_latest("canonical_work_units", "wu-1")["state"] == "running"


def test_bind_legacy_task_run_is_idempotent_and_rejects_cross_case_identity(tmp_path) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    bind = _command(
        "BIND_LEGACY_TASK_RUN",
        {
            "binding_id": "binding-2",
            "legacy_system": "legacy-test",
            "legacy_task_id": "legacy-task-2",
            "legacy_run_id": "legacy-run-2",
        },
        idem="bind-2",
    )
    first = facade.bind_legacy_task_run(bind)
    assert facade.bind_legacy_task_run(bind).reused_idempotent_result is True
    assert first.status == "succeeded"
    with pytest.raises(IdempotencyConflict):
        facade.bind_legacy_task_run(
            bind.model_copy(update={"payload": {**bind.payload, "legacy_task_id": "other"}})
        )

    facade.create_research_case(
        _command("CREATE_RESEARCH_CASE", {"query": "Second", "accountable_owner_ref": "lead-2"}, case_id="case-2", idem="case-2")
    )
    with pytest.raises(LegacyBindingConflict, match="legacy_binding_conflict"):
        facade.bind_legacy_task_run(
            _command(
                "BIND_LEGACY_TASK_RUN",
                {"legacy_system": "legacy-test", "legacy_task_id": "legacy-task-2", "legacy_run_id": "legacy-run-2"},
                case_id="case-2",
                idem="cross-case",
            )
        )


def test_complete_attempt_and_execution_views_preserve_legacy_authority(tmp_path) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    _start_work(facade)
    result = facade.complete_attempt(
        _command(
            "COMPLETE_ATTEMPT",
            {"work_unit_id": "wu-1", "attempt_id": "attempt-1", "terminal_reason": "fixture_complete"},
            expected=1,
        )
    )
    assert result.status == "succeeded"
    assert facade.store.get_latest("canonical_attempts", "attempt-1")["state"] == "succeeded"
    assert facade.store.get_latest("canonical_work_units", "wu-1")["state"] == "succeeded"
    with pytest.raises(IllegalStateTransition):
        facade.complete_attempt(
            _command("COMPLETE_ATTEMPT", {"work_unit_id": "wu-1", "attempt_id": "attempt-1"}, expected=2, idem="again")
        )
    case_view = facade.get_case_execution_view("case-1")
    work_view = facade.get_work_unit_execution_view("wu-1")
    assert case_view["planning_authority"] == "legacy"
    assert case_view["output_usability"]["attempt-1"]["usable"] is True
    assert work_view["terminal_reason"]["attempt-1"] == "fixture_complete"
    replay = facade.replay_projection()
    assert replay["work_units"]["wu-1"]["state"] == "succeeded"
    assert replay["attempts"]["attempt-1"]["state"] == "succeeded"
    assert replay["external_call_count"] == 0


def test_fail_and_cancel_are_terminal_append_only_transitions(tmp_path) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    _start_work(facade)
    failed = facade.fail_attempt(
        _command(
            "FAIL_ATTEMPT",
            {
                "work_unit_id": "wu-1",
                "attempt_id": "attempt-1",
                "failure_type": "compiler_input_invalid",
                "retryable": True,
                "terminal_reason": "missing_required_cell",
            },
            expected=1,
        )
    )
    assert len(failed.event_ids) == 2
    attempt = facade.store.get_latest("canonical_attempts", "attempt-1")
    assert attempt["failure_type"] == "compiler_input_invalid"
    assert attempt["retryable"] is False
    with pytest.raises(IllegalStateTransition):
        facade.fail_attempt(
            _command(
                "FAIL_ATTEMPT",
                {"work_unit_id": "wu-1", "attempt_id": "attempt-1", "failure_type": "again", "retryable": False},
                expected=2,
                idem="fail-again",
            )
        )

    facade.create_work_unit(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-2", "input_version_refs": []}, idem="wu-2"))
    facade.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-2", "attempt_id": "attempt-2"}, idem="attempt-2"))
    cancelled = facade.cancel_work_unit(
        _command("CANCEL_WORK_UNIT", {"work_unit_id": "wu-2", "terminal_reason": "operator_cancelled"}, expected=1)
    )
    assert cancelled.status == "succeeded"
    assert facade.store.get_latest("canonical_work_units", "wu-2")["state"] == "cancelled"
    assert facade.store.get_latest("canonical_attempts", "attempt-2")["state"] == "cancelled"
    assert facade.replay_projection()["work_units"]["wu-2"]["state"] == "cancelled"


def test_retryable_failure_creates_immutable_attempt_n_plus_one(tmp_path) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    facade.create_work_unit(
        _command(
            "CREATE_WORK_UNIT",
            {
                "work_unit_id": "wu-retry",
                "max_attempts": 2,
                "retry_budget": 1,
                "retry_policy_ref": "retry:bounded",
                "retryable_failure_types": ["timeout"],
            },
            idem="wu-retry",
        )
    )
    facade.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-retry", "attempt_id": "attempt-1"}, idem="retry-1"))
    facade.fail_attempt(_command("FAIL_ATTEMPT", {"work_unit_id": "wu-retry", "attempt_id": "attempt-1", "failure_type": "timeout", "retryable": True}, expected=1, idem="retry-fail"))
    assert facade.store.get_latest("canonical_work_units", "wu-retry")["current_status"] == "failed_retryable"
    assert facade.store.get_latest("canonical_work_units", "wu-retry")["state"] == "retryable_failed"
    assert facade.replay_projection()["work_units"]["wu-retry"]["state"] == "retryable_failed"
    facade.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-retry", "attempt_id": "attempt-2"}, expected=2, idem="retry-2"))
    assert facade.store.get_latest("canonical_attempts", "attempt-1")["state"] == "failed"
    assert facade.store.get_latest("canonical_attempts", "attempt-2")["attempt_no"] == 2
    with sqlite3.connect(facade.store.db_path) as connection:
        assert connection.execute("select count(*) from canonical_attempts where logical_id = 'attempt-1'").fetchone()[0] == 2
    facade.fail_attempt(
        _command(
            "FAIL_ATTEMPT",
            {"work_unit_id": "wu-retry", "attempt_id": "attempt-2", "failure_type": "timeout", "retryable": True},
            expected=3,
            idem="retry-exhausted",
        )
    )
    assert facade.store.get_latest("canonical_work_units", "wu-retry")["state"] == "failed"
    with pytest.raises(IllegalStateTransition, match="work_unit_must_be_pending_or_retryable_failed"):
        facade.start_attempt(
            _command("START_ATTEMPT", {"work_unit_id": "wu-retry", "attempt_id": "attempt-3"}, expected=4, idem="retry-3")
        )


@pytest.mark.parametrize(
    ("failure_type", "requested_retryable", "expected_state"),
    [
        ("transient_network", True, "retryable_failed"),
        ("permanent_contract", False, "failed"),
        ("poison_payload", True, "failed"),
    ],
)
def test_retry_policy_distinguishes_transient_permanent_and_poison_failures(
    tmp_path, failure_type: str, requested_retryable: bool, expected_state: str
) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    facade.create_work_unit(
        _command(
            "CREATE_WORK_UNIT",
            {
                "work_unit_id": "wu-policy",
                "max_attempts": 2,
                "retry_budget": 1,
                "retry_policy_ref": "retry:bounded",
                "retryable_failure_types": ["transient_network", "poison_payload"],
                "poison_failure_types": ["poison_payload"],
            },
            idem="wu-policy",
        )
    )
    facade.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-policy", "attempt_id": "attempt-policy"}, idem="attempt-policy"))
    facade.fail_attempt(
        _command(
            "FAIL_ATTEMPT",
            {"work_unit_id": "wu-policy", "attempt_id": "attempt-policy", "failure_type": failure_type, "retryable": requested_retryable},
            expected=1,
            idem=f"fail-{failure_type}",
        )
    )
    work_unit = facade.store.get_latest("canonical_work_units", "wu-policy")
    assert work_unit["state"] == expected_state
    assert facade.store.get_latest("canonical_attempts", "attempt-policy")["retryable"] is (expected_state == "retryable_failed")


def test_concurrent_start_has_one_winner_and_one_stale_loser(tmp_path) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    facade.create_work_unit(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-race"}, idem="wu-race"))

    def start(index: int) -> str:
        try:
            facade.start_attempt(
                _command(
                    "START_ATTEMPT",
                    {"work_unit_id": "wu-race", "attempt_id": f"attempt-race-{index}"},
                    expected=0,
                    idem=f"race-{index}",
                )
            )
            return "winner"
        except StaleStateVersion:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(start, range(2)))
    assert sorted(outcomes) == ["stale", "winner"]
    assert len([row for row in facade.store.list_latest("canonical_attempts", case_id="case-1") if row["work_unit_id"] == "wu-race"]) == 1


def test_bounded_sqlite_start_load_serializes_independent_work_units(tmp_path) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    work_unit_ids = [f"wu-load-{index}" for index in range(8)]
    for work_unit_id in work_unit_ids:
        facade.create_work_unit(_command("CREATE_WORK_UNIT", {"work_unit_id": work_unit_id}, idem=work_unit_id))

    def start(work_unit_id: str) -> str:
        facade.start_attempt(
            _command(
                "START_ATTEMPT",
                {"work_unit_id": work_unit_id, "attempt_id": f"attempt-{work_unit_id}"},
                idem=f"start-{work_unit_id}",
            )
        )
        return work_unit_id

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(pool.map(start, work_unit_ids)) == work_unit_ids
    assert len([row for row in facade.store.list_latest("canonical_attempts", case_id="case-1") if row["work_unit_id"].startswith("wu-load-")]) == 8


def test_legacy_bridge_recovery_after_restart_preserves_replay_and_authority(tmp_path) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    facade.create_work_unit(
        _command(
            "CREATE_WORK_UNIT",
            {
                "work_unit_id": "wu-recovery",
                "max_attempts": 2,
                "retry_budget": 1,
                "retry_policy_ref": "retry:bounded",
                "retryable_failure_types": ["transient_network"],
            },
            idem="wu-recovery",
        )
    )
    facade.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-recovery", "attempt_id": "attempt-recovery-1"}, idem="start-recovery-1"))
    facade.fail_attempt(
        _command(
            "FAIL_ATTEMPT",
            {"work_unit_id": "wu-recovery", "attempt_id": "attempt-recovery-1", "failure_type": "transient_network", "retryable": True},
            expected=1,
            idem="fail-recovery-1",
        )
    )
    before = facade.replay_projection()
    recovered = RuntimeFacade(
        SQLiteCanonicalStore(facade.store.db_path),
        FileCanonicalObjectStore(tmp_path / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    report = recovered.recover_case_execution("case-1")
    assert report["status"] == "pass"
    assert report["projection_digest"] == before["projection_digest"]
    assert report["planning_authority"] == "legacy"
    assert recovered.get_case_execution_view("case-1")["legacy_bindings"][0]["legacy_authority_status"] == "authoritative"
    recovered.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-recovery", "attempt_id": "attempt-recovery-2"}, expected=2, idem="start-recovery-2"))
    recovered.complete_attempt(
        _command("COMPLETE_ATTEMPT", {"work_unit_id": "wu-recovery", "attempt_id": "attempt-recovery-2"}, expected=3, idem="complete-recovery-2")
    )
    assert recovered.get_work_unit_execution_view("wu-recovery")["work_unit"]["state"] == "succeeded"


def test_m1_rollback_recovery_drill_preserves_legacy_authority_and_audit_history(tmp_path) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    facade.create_work_unit(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-drill"}, idem="wu-drill"))
    facade.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-drill", "attempt_id": "attempt-drill"}, idem="attempt-drill"))
    before = facade.recover_case_execution("case-1")
    facade.store.set_kill_switch(True)
    with pytest.raises(Exception, match="kill_switch"):
        facade.complete_attempt(
            _command("COMPLETE_ATTEMPT", {"work_unit_id": "wu-drill", "attempt_id": "attempt-drill"}, expected=1, idem="blocked-after-kill")
        )
    after = facade.recover_case_execution("case-1")
    assert after["status"] == "pass"
    assert after["projection_digest"] == before["projection_digest"]
    assert facade.get_case_execution_view("case-1")["legacy_bindings"][0]["legacy_authority_status"] == "authoritative"


@pytest.mark.parametrize(
    ("error", "expected_code", "expected_status"),
    [
        (KeyError("work_unit_id"), "validation_error", "rejected"),
        (OSError("object_store_down"), "artifact_write_failed", "rejected"),
        (FeatureFlagError("permission_denied"), "permission_denied", "rejected"),
    ],
)
def test_project_error_covers_api_validation_artifact_and_permission_taxonomy(error, expected_code: str, expected_status: str) -> None:
    projected = RuntimeFacade.project_error(_command("COMPLETE_ATTEMPT", {"work_unit_id": "wu-1", "attempt_id": "attempt-1"}), error)
    assert projected.error == {"code": expected_code}
    assert projected.status == expected_status


def test_stale_input_head_and_expired_lease_leave_no_committed_artifact(tmp_path) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    facade.create_work_unit(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-lease", "input_version_refs": ["summary-v1"]}, idem="wu-lease"))
    start = _command(
        "START_ATTEMPT",
        {"work_unit_id": "wu-lease", "attempt_id": "attempt-lease", "worker_ref": "worker-a", "lease_duration_seconds": 1},
        idem="start-lease",
    )
    facade.start_attempt(start)
    with pytest.raises(StaleInputHead, match="stale_input_head"):
        facade.commit_decision_surface_bundle(
            _command(
                "COMMIT_DECISION_SURFACE_BUNDLE",
                {"work_unit_id": "wu-lease", "attempt_id": "attempt-lease", "artifact_id": "artifact-stale-head", "bundle": _bundle(), "input_head_digest": "not-current"},
                expected=1,
                idem="stale-head",
            )
        )
    assert facade.store.get_latest("canonical_artifact_versions", "artifact-stale-head") is None
    assert any(path.is_file() for path in (tmp_path / "objects").rglob("*"))
    expired = _command(
        "COMPLETE_ATTEMPT",
        {"work_unit_id": "wu-lease", "attempt_id": "attempt-lease", "worker_ref": "worker-a"},
        expected=1,
        idem="expired-lease",
    ).model_copy(update={"requested_at": start.requested_at + timedelta(seconds=2)})
    with pytest.raises(LeaseValidationError, match="attempt_lease_expired"):
        facade.complete_attempt(expired)
    assert facade.store.get_latest("canonical_attempts", "attempt-lease")["state"] == "running"


def test_artifact_read_digest_check_and_unknown_event_replay_fail_closed(tmp_path) -> None:
    facade = _facade(tmp_path)
    _create_case(facade)
    _start_work(facade)
    facade.commit_decision_surface_bundle(
        _command(
            "COMMIT_DECISION_SURFACE_BUNDLE",
            {"work_unit_id": "wu-1", "attempt_id": "attempt-1", "artifact_id": "artifact-read", "bundle": _bundle()},
            expected=1,
        )
    )
    loaded = facade.get_artifact_version("artifact-read:v1", include_payload=True)
    assert loaded["artifact"]["object_key"].startswith("point01/")
    assert loaded["payload"]["contract"]["contract_id"] == "contract-1"
    object_path = tmp_path / "objects" / Path(loaded["artifact"]["object_key"])
    object_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ArtifactValidationError, match="artifact_digest_validation_failed"):
        facade.get_artifact_version("artifact-read:v1", include_payload=True)
    facade.create_work_unit(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-2", "input_version_refs": []}, idem="wu-2"))
    facade.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-2", "attempt_id": "attempt-2"}, idem="attempt-2"))
    with pytest.raises(ArtifactValidationError, match="artifact_digest_validation_failed"):
        facade.complete_attempt(
            _command(
                "COMPLETE_ATTEMPT",
                {"work_unit_id": "wu-2", "attempt_id": "attempt-2", "output_artifact_refs": ["artifact-read:v1"]},
                expected=1,
            )
        )
    assert facade.store.get_latest("canonical_attempts", "attempt-2")["state"] == "running"

    with facade.store.transaction() as tx:
        tx.append_event(
            EventEnvelope(
                event_id="event-unknown",
                event_type="UNKNOWN_STATE_MUTATION",
                sequence_no=999,
                occurred_at=datetime.now(timezone.utc),
                recorded_at=datetime.now(timezone.utc),
                actor_snapshot_ref="actor-1",
                correlation_id="correlation-1",
                state_version_before=0,
                state_version_after=0,
                payload_digest="unknown",
            )
        )
    with pytest.raises(UnknownEventSchema, match="unknown_state_mutating_event"):
        facade.replay_projection()
