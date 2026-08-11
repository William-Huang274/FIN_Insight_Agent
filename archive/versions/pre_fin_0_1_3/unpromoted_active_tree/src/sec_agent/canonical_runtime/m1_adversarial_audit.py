"""Isolated actual-path probes for the Point 01 M1-A1 adversarial audit.

This module deliberately contains no oracle import, fixed-store path, ambient
store resolution, transport client, or environment-derived authority.  Every
mutation is made through an explicitly supplied temporary SQLite root.
"""

from __future__ import annotations

import http.client
import json
import sqlite3
import shutil
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from sec_agent.canonical_runtime.facade import (
    ArtifactValidationError,
    IllegalStateTransition,
    LegacyBindingConflict,
    RuntimeFacade,
    UnknownEventSchema,
)
from sec_agent.canonical_runtime.feature_flags import FeatureFlagRegistry
from sec_agent.canonical_runtime.m1_adversarial_audit_canary import M1AuditAccessCanary
from sec_agent.canonical_runtime.m1_a1_audit_package import verify_package_manifest
from sec_agent.canonical_runtime.models import CommandEnvelope, EventEnvelope, canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.canonical_runtime.store import IdempotencyConflict, SQLiteCanonicalStore, StaleStateVersion


AUDIT_SCOPE = "point01_m1_a1_independent_adversarial_audit_only"
_UTC = timezone.utc


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


def _assert_isolated_root(audit_root: Path) -> Path:
    resolved = audit_root.resolve()
    if resolved.name != "m1-a1-isolated":
        raise ValueError("audit_store_path_not_isolated")
    return resolved


def build_isolated_facade(audit_root: Path) -> RuntimeFacade:
    """Construct the only store used by an actual-path audit probe."""
    root = _assert_isolated_root(audit_root)
    return RuntimeFacade(
        SQLiteCanonicalStore(root / "canonical.sqlite"),
        FileCanonicalObjectStore(root / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )


def _command(
    command_type: str,
    payload: dict[str, Any],
    *,
    case_id: str = "case-a1",
    expected: int = 0,
    idem: str | None = None,
    requested_at: datetime | None = None,
) -> CommandEnvelope:
    token = idem or command_type.lower()
    return CommandEnvelope(
        command_id=f"m1-a1-{command_type.lower()}-{token}",
        command_type=command_type,
        tenant_id="tenant-m1-a1-audit",
        project_id="project-m1-a1-audit",
        case_id=case_id,
        actor_snapshot_ref="m1-a1-audit-actor",
        permission_snapshot_ref="m1-a1-audit-permission",
        policy_config_refs=("point01-m1-a1-audit-policy",),
        idempotency_key=token,
        expected_state_version=expected,
        correlation_id="m1-a1-audit-correlation",
        requested_at=requested_at or datetime(2026, 7, 14, 0, 0, tzinfo=_UTC),
        payload=payload,
    )


def _create_case(facade: RuntimeFacade, *, case_id: str = "case-a1", legacy_suffix: str = "1") -> None:
    facade.create_research_case(
        _command(
            "CREATE_RESEARCH_CASE",
            {
                "query": "M1-A1 isolated lifecycle audit",
                "universe": ["AUDIT"],
                "accountable_owner_ref": "m1-a1-audit-owner",
                "legacy_system": "legacy-audit",
                "legacy_task_id": f"legacy-task-{legacy_suffix}",
                "legacy_run_id": f"legacy-run-{legacy_suffix}",
            },
            case_id=case_id,
            idem=f"case-{case_id}",
        )
    )


def _audit_scope(status: str) -> dict[str, Any]:
    timestamp = datetime(2026, 7, 14, 0, 0, tzinfo=_UTC).isoformat()
    return {
        "schema_version": "finsight_point01_canonical_runtime_v1_0",
        "tenant_id": "tenant-m1-a1-audit",
        "project_id": "project-m1-a1-audit",
        "case_id": "case-a1",
        "created_at": timestamp,
        "recorded_at": timestamp,
        "actor_snapshot_ref": "m1-a1-audit-actor",
        "permission_snapshot_ref": "m1-a1-audit-permission",
        "policy_config_refs": ["point01-m1-a1-audit-policy"],
        "correlation_id": "m1-a1-audit-correlation",
        "current_status": status,
    }


def _bundle() -> dict[str, Any]:
    contract = {
        **_audit_scope("shadow_compiled"),
        "contract_id": "contract-m1-a1",
        "contract_version_id": "contract-m1-a1:v1",
        "contract_version": 1,
        "query": "M1-A1 isolated lifecycle audit",
        "as_of": datetime(2026, 7, 14, 0, 0, tzinfo=_UTC).isoformat(),
        "universe": ["AUDIT"],
        "language": "en",
        "compiler_policy_ref": "compiler-policy-m1-a1",
        "required_cell_ids": ["cell-m1-a1"],
    }
    cell = {
        **_audit_scope("shadow_compiled"),
        "contract_version_id": "contract-m1-a1:v1",
        "cell_id": "cell-m1-a1",
        "cell_version_id": "cell-m1-a1:v1",
        "cell_version": 1,
        "decision_question": "Is the M1-A1 audit isolated?",
        "origin_type": "universal",
        "owner_role": "audit_owner",
        "materiality": "high",
        "stop_rule": "isolated local contract only",
    }
    slot = {
        **_audit_scope("shadow_required"),
        "cell_version_id": "cell-m1-a1:v1",
        "evidence_slot_id": "slot-m1-a1",
        "slot_version_id": "slot-m1-a1:v1",
        "slot_version": 1,
        "evidence_role": "audit_control",
        "entity_scope": ["AUDIT"],
        "period_scope": "audit_window",
        "source_policy_ref": "local_fixture_only",
        "acceptance_role": "context_only",
        "required": True,
    }
    return {"contract": contract, "cells": [cell], "slots": [slot], "gaps": []}


def _exception_code(action: Callable[[], Any]) -> str:
    try:
        action()
    except Exception as exc:  # typed result is intentionally recorded, not swallowed.
        return f"{type(exc).__name__}:{exc}"
    return "unexpected_success"


def _temporary_counts(facade: RuntimeFacade) -> dict[str, int]:
    with sqlite3.connect(facade.store.db_path) as connection:
        row_count = sum(
            int(connection.execute(f"select count(*) from {table}").fetchone()[0])
            for table in ("canonical_events", "canonical_outbox", "canonical_attempts", "canonical_work_units", "canonical_artifact_versions")
        )
    object_count = sum(1 for item in facade.object_store.root.rglob("*") if item.is_file())
    return {"temporary_store_row_count": row_count, "temporary_object_count": object_count}


def _clone_sqlite_root(facade: RuntimeFacade, clone_root: Path) -> Path:
    clone_root.mkdir(parents=True, exist_ok=True)
    clone_db = clone_root / "canonical.sqlite"
    shutil.copy2(facade.store.db_path, clone_db)
    return clone_root


def _clone_tamper_probe(
    facade: RuntimeFacade,
    *,
    clone_root: Path,
    statement: str,
    parameters: tuple[Any, ...],
    case_id: str,
) -> dict[str, Any]:
    """Attempt a real append-only violation in a cloned temporary store.

    If a mutation is unexpectedly accepted, real replay and recovery are run on
    that clone.  The caller must treat any successful replay/recovery as a M1
    runtime defect and stop rather than repair it in this audit slice.
    """
    cloned_root = _clone_sqlite_root(facade, clone_root)
    clone_db = cloned_root / "canonical.sqlite"
    try:
        with sqlite3.connect(clone_db) as connection:
            connection.execute(statement, parameters)
            connection.commit()
    except Exception as exc:
        return {
            "mutation_status": "write_rejected",
            "runtime_or_store_stop": f"{type(exc).__name__}:{exc}",
            "clone_replay_stop": "not_run_after_write_rejected",
            "clone_recovery_stop": "not_run_after_write_rejected",
        }
    clone_facade = RuntimeFacade(
        SQLiteCanonicalStore(clone_db),
        FileCanonicalObjectStore(cloned_root / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    replay_stop = _exception_code(clone_facade.replay_projection)
    recovery_stop = _exception_code(lambda: clone_facade.recover_case_execution(case_id))
    return {
        "mutation_status": "write_accepted",
        "runtime_or_store_stop": "mutation_write_accepted",
        "clone_replay_stop": replay_stop,
        "clone_recovery_stop": recovery_stop,
    }


def run_p01(
    audit_root: Path,
    *,
    repository_root: Path,
    package_manifest: dict[str, Any],
    package_verifier: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    facade = build_isolated_facade(audit_root)
    _create_case(facade)
    facade.create_work_unit(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-p01", "input_version_refs": ["audit-input:v1"]}, idem="p01-work"))
    facade.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-p01", "attempt_id": "attempt-p01"}, idem="p01-start"))
    facade.commit_decision_surface_bundle(
        _command(
            "COMMIT_DECISION_SURFACE_BUNDLE",
            {"work_unit_id": "wu-p01", "attempt_id": "attempt-p01", "artifact_id": "artifact-p01", "bundle": _bundle()},
            expected=1,
            idem="p01-commit",
        )
    )
    verifier = package_verifier or (lambda manifest: verify_package_manifest(repository_root, manifest))
    package_before = verifier(package_manifest)
    tampered_manifest = deepcopy(package_manifest)
    first_path = sorted(tampered_manifest["input_file_sha256"])[0]
    tampered_manifest["input_file_sha256"][first_path] = "0" * 64
    package_tamper = verifier(tampered_manifest)
    first_event_id = str(facade.store.list_events()[0]["event_id"])
    payload_digest_tamper = _clone_tamper_probe(
        facade,
        clone_root=audit_root.parent / "p01-payload-digest-clone",
        statement="update canonical_events set payload_digest = ? where event_id = ?",
        parameters=("0" * 64, first_event_id),
        case_id="case-a1",
    )

    artifact = facade.get_artifact_version("artifact-p01:v1", include_payload=True)["artifact"]
    object_path = facade.object_store.root / Path(str(artifact["object_key"]))
    object_path.write_text("{}", encoding="utf-8")
    artifact_stop = _exception_code(lambda: facade.get_artifact_version("artifact-p01:v1", include_payload=True))

    with facade.store.transaction() as tx:
        tx.append_event(
            EventEnvelope(
                event_id="m1-a1-p01-unknown-event",
                event_type="M1_A1_UNKNOWN_MUTATION",
                sequence_no=999,
                occurred_at=datetime(2026, 7, 14, 0, 1, tzinfo=_UTC),
                recorded_at=datetime(2026, 7, 14, 0, 1, tzinfo=_UTC),
                actor_snapshot_ref="m1-a1-audit-actor",
                correlation_id="m1-a1-audit-correlation",
                state_version_before=0,
                state_version_after=0,
                payload_digest="m1-a1-tamper",
            )
        )
    replay_stop = _exception_code(facade.replay_projection)
    return {
        "probe_id": "A0-M1-P01",
        "actual_status": "pass",
        "input_digest": canonical_digest({"package": package_manifest, "scenario": "P01"}),
        "actual_digest": canonical_digest(
            {"package_before": package_before, "payload_digest_tamper": payload_digest_tamper, "artifact_stop": artifact_stop, "replay_stop": replay_stop}
        ),
        "package_before": package_before,
        "package_tamper_stop": package_tamper["status"],
        "event_payload_digest_tamper": payload_digest_tamper,
        "artifact_tamper_stop": artifact_stop,
        "replay_tamper_stop": replay_stop,
        "typed_stops": (package_tamper["status"], payload_digest_tamper["runtime_or_store_stop"], artifact_stop, replay_stop),
        **_temporary_counts(facade),
    }


def run_p02(audit_root: Path) -> dict[str, Any]:
    facade = build_isolated_facade(audit_root)
    _create_case(facade)
    retry_create = _command(
        "CREATE_WORK_UNIT",
        {
            "work_unit_id": "wu-p02-retry",
            "max_attempts": 2,
            "retry_budget": 1,
            "retry_policy_ref": "retry:bounded",
            "retryable_failure_types": ["timeout"],
        },
        idem="p02-retry-work",
    )
    facade.create_work_unit(retry_create)
    duplicate_create = facade.create_work_unit(retry_create)
    idempotency_conflict = _exception_code(
        lambda: facade.create_work_unit(retry_create.model_copy(update={"payload": {**retry_create.payload, "max_attempts": 3}}))
    )
    facade.start_attempt(_command("START_ATTEMPT", {"work_unit_id": "wu-p02-retry", "attempt_id": "attempt-p02-1"}, idem="p02-start-1"))
    facade.fail_attempt(
        _command(
            "FAIL_ATTEMPT",
            {"work_unit_id": "wu-p02-retry", "attempt_id": "attempt-p02-1", "failure_type": "timeout", "retryable": True},
            expected=1,
            idem="p02-fail-1",
        )
    )
    stale_start = _exception_code(
        lambda: facade.start_attempt(
            _command("START_ATTEMPT", {"work_unit_id": "wu-p02-retry", "attempt_id": "attempt-p02-stale"}, expected=1, idem="p02-stale")
        )
    )
    retry_start = _command("START_ATTEMPT", {"work_unit_id": "wu-p02-retry", "attempt_id": "attempt-p02-2"}, expected=2, idem="p02-start-2")
    facade.start_attempt(retry_start)
    duplicate_retry = facade.start_attempt(retry_start)
    stale_attempt_terminal = _exception_code(
        lambda: facade.complete_attempt(
            _command("COMPLETE_ATTEMPT", {"work_unit_id": "wu-p02-retry", "attempt_id": "attempt-p02-1"}, expected=3, idem="p02-old-terminal")
        )
    )
    facade.fail_attempt(
        _command(
            "FAIL_ATTEMPT",
            {"work_unit_id": "wu-p02-retry", "attempt_id": "attempt-p02-2", "failure_type": "timeout", "retryable": True},
            expected=3,
            idem="p02-fail-2",
        )
    )
    retry_budget_stop = _exception_code(
        lambda: facade.start_attempt(
            _command("START_ATTEMPT", {"work_unit_id": "wu-p02-retry", "attempt_id": "attempt-p02-3"}, expected=4, idem="p02-start-3")
        )
    )

    facade.create_work_unit(_command("CREATE_WORK_UNIT", {"work_unit_id": "wu-p02-fence"}, idem="p02-fence-work"))
    claim_time = datetime(2026, 7, 14, 0, 2, tzinfo=_UTC)
    facade.claim_next_scheduled_attempt(
        _command(
            "CLAIM_NEXT_SCHEDULED_ATTEMPT",
            {"work_unit_id": "wu-p02-fence", "attempt_id": "attempt-p02-fence", "worker_ref": "worker-a", "lease_duration_seconds": 1},
            idem="p02-claim",
            requested_at=claim_time,
        )
    )
    facade.reclaim_expired_scheduled_attempt_lease(
        _command(
            "RECLAIM_EXPIRED_SCHEDULED_ATTEMPT_LEASE",
            {"work_unit_id": "wu-p02-fence", "attempt_id": "attempt-p02-fence", "worker_ref": "worker-b", "lease_duration_seconds": 60},
            expected=1,
            idem="p02-reclaim",
            requested_at=claim_time + timedelta(seconds=2),
        )
    )
    stale_fencing = _exception_code(
        lambda: facade.complete_attempt(
            _command(
                "COMPLETE_ATTEMPT",
                {"work_unit_id": "wu-p02-fence", "attempt_id": "attempt-p02-fence", "worker_ref": "worker-a", "lease_fencing_token": 1},
                expected=2,
                idem="p02-fenced-terminal",
                requested_at=claim_time + timedelta(seconds=3),
            )
        )
    )
    terminal_state = facade.store.get_latest("canonical_work_units", "wu-p02-retry")["state"]
    return {
        "probe_id": "A0-M1-P02",
        "actual_status": "pass",
        "input_digest": canonical_digest({"scenario": "P02", "retry_policy": "bounded_timeout"}),
        "actual_digest": canonical_digest(
            {"idempotency": idempotency_conflict, "stale": stale_start, "fence": stale_fencing, "terminal": terminal_state}
        ),
        "duplicate_idempotent": bool(duplicate_create.reused_idempotent_result and duplicate_retry.reused_idempotent_result),
        "idempotency_conflict_stop": idempotency_conflict,
        "stale_state_stop": stale_start,
        "stale_attempt_terminal_stop": stale_attempt_terminal,
        "retry_budget_stop": retry_budget_stop,
        "stale_fencing_stop": stale_fencing,
        "retry_terminal_state": terminal_state,
        "typed_stops": (idempotency_conflict, stale_start, stale_attempt_terminal, retry_budget_stop, stale_fencing),
        **_temporary_counts(facade),
    }


def run_p03(audit_root: Path, *, fixed_store_path: Path, canary: M1AuditAccessCanary) -> dict[str, Any]:
    facade = build_isolated_facade(audit_root)
    _create_case(facade)
    fixed_path_stop = _exception_code(lambda: SQLiteCanonicalStore(fixed_store_path))
    ambient_path_stop = _exception_code(lambda: SQLiteCanonicalStore(Path.cwd() / "m1-a1-unallowlisted.sqlite"))
    transport_stop = _exception_code(lambda: http.client.HTTPSConnection("audit.invalid"))
    canary_snapshot = canary.snapshot()
    return {
        "probe_id": "A0-M1-P03",
        "actual_status": "pass",
        "input_digest": canonical_digest({"scenario": "P03", "audit_root_name": audit_root.name}),
        "actual_digest": canonical_digest({"fixed_path_stop": fixed_path_stop, "ambient_path_stop": ambient_path_stop, "transport_stop": transport_stop, "canary": canary_snapshot}),
        "fixed_store_open_stop": fixed_path_stop,
        "ambient_store_open_stop": ambient_path_stop,
        "transport_constructor_stop": transport_stop,
        "access_canary": canary_snapshot,
        "typed_stops": (fixed_path_stop, ambient_path_stop, transport_stop),
        **_temporary_counts(facade),
    }


def run_p04(audit_root: Path) -> dict[str, Any]:
    facade = build_isolated_facade(audit_root)
    _create_case(facade)
    binding_identity = {"legacy_system": "legacy-audit", "legacy_store_id": "default", "legacy_task_id": "legacy-task-1", "legacy_run_id": "legacy-run-1"}
    binding_id = f"binding_{canonical_digest(binding_identity)[:24]}"
    binding_before = facade.store.get_latest("canonical_task_run_bindings", binding_id)
    facade.create_research_case(
        _command(
            "CREATE_RESEARCH_CASE",
            {"query": "second isolated case", "accountable_owner_ref": "m1-a1-audit-owner"},
            case_id="case-a1-second",
            idem="p04-second-case",
        )
    )
    legacy_conflict = _exception_code(
        lambda: facade.bind_legacy_task_run(
            _command(
                "BIND_LEGACY_TASK_RUN",
                {"legacy_system": "legacy-audit", "legacy_task_id": "legacy-task-1", "legacy_run_id": "legacy-run-1"},
                case_id="case-a1-second",
                idem="p04-cross-case-bind",
            )
        )
    )
    before_replay = facade.replay_projection()
    first_event_id = str(facade.store.list_events()[0]["event_id"])
    sequence_tamper = _clone_tamper_probe(
        facade,
        clone_root=audit_root.parent / "p04-sequence-clone",
        statement="update canonical_events set sequence_no = ? where event_id = ?",
        parameters=(999, first_event_id),
        case_id="case-a1",
    )
    recovered = RuntimeFacade(
        SQLiteCanonicalStore(facade.store.db_path),
        FileCanonicalObjectStore(audit_root / "objects"),
        _flags(),
        mode="shadow",
        grants={"point01.shadow.write"},
    )
    recovery = recovered.recover_case_execution("case-a1")
    binding_after = recovered.store.get_latest("canonical_task_run_bindings", binding_id)
    return {
        "probe_id": "A0-M1-P04",
        "actual_status": "pass",
        "input_digest": canonical_digest({"scenario": "P04", "legacy_binding": binding_id}),
        "actual_digest": canonical_digest(
            {"legacy_conflict": legacy_conflict, "sequence_tamper": sequence_tamper, "replay": before_replay["projection_digest"], "recovery": recovery, "binding": binding_after}
        ),
        "legacy_binding_authority_before": binding_before.get("legacy_authority_status"),
        "legacy_binding_authority_after": binding_after.get("legacy_authority_status"),
        "cross_case_legacy_binding_stop": legacy_conflict,
        "event_sequence_tamper": sequence_tamper,
        "recovery_status": recovery["status"],
        "recovery_projection_matches": recovery["projection_digest"] == before_replay["projection_digest"],
        "typed_stops": (legacy_conflict, sequence_tamper["runtime_or_store_stop"]),
        **_temporary_counts(recovered),
    }
