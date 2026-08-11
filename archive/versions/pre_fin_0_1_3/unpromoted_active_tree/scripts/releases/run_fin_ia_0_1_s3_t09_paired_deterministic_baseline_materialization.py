from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
import sys
import time
from typing import Any, Mapping

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(SCRIPT_ROOT))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    resolve_s4_case_runtime_binding_for_admission,
)
from apps.workbench.backend.application.execution_service import VT1_WORK_UNIT_TYPE
from apps.workbench.backend.application.local_research_service import P36LocalResearchService
from apps.workbench.backend.application.research_runtime import FIN01_DETERMINISTIC_PROFILE_REF
from sec_agent.s4_case_runtime import (
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)
from prepare_fin_ia_0_1_s3_t09_paired_deterministic_baseline_decision import (
    ACTOR_ID,
    BASELINE_EXECUTION_IDENTITY,
    EXPECTED_ARTIFACT_TYPES,
    EXPECTED_CELLS,
    PROJECT_ID,
    TENANT_ID,
    _logical_snapshot,
    _sha256,
    _tree_digest,
    prepare,
)


PERMISSIONS = frozenset(
    {
        "activity:read",
        "case:read",
        "evidence:read",
        "execution:read",
        "execution:write",
        "planning:read",
    }
)


class BaselineMaterializationError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BaselineMaterializationError(code)


def _headers() -> dict[str, str]:
    return {
        "X-Fin-Case-Tenant": TENANT_ID,
        "X-Fin-Case-Project": PROJECT_ID,
        "X-Fin-Case-Actor": ACTOR_ID,
        "X-Fin-Case-Permissions": ",".join(sorted(PERMISSIONS)),
    }


def _latest_by_id(database_path: Path, table: str) -> dict[str, dict[str, Any]]:
    connection = sqlite3.connect(database_path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("pragma query_only = on")
    try:
        rows: dict[str, dict[str, Any]] = {}
        for logical_id, payload_json in connection.execute(
            f"select logical_id, payload_json from {table} order by row_id"
        ):
            rows[str(logical_id)] = json.loads(str(payload_json))
        return rows
    finally:
        connection.close()


def _object_snapshot(object_root: Path) -> dict[str, str]:
    return {
        path.relative_to(object_root).as_posix(): _sha256(path)
        for path in sorted(item for item in object_root.rglob("*") if item.is_file())
    }


def _artifact_ref(row: Mapping[str, Any]) -> str:
    return f"{row['artifact_id']}:v{row['artifact_version']}"


def _wait_for_exact_run(
    client: TestClient,
    *,
    case_id: str,
    research_run_id: str,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        response = client.get(
            f"/api/v1/cases/{case_id}/execution-projection",
            headers=_headers(),
        )
        _require(response.status_code == 200, "baseline_execution_projection_failed")
        rows = [
            row
            for row in response.json().get("runs", ())
            if row.get("research_run_id") == research_run_id
        ]
        _require(len(rows) <= 1, "baseline_run_projection_cardinality_violation")
        if rows and rows[0].get("state") in {"succeeded", "failed", "cancelled"}:
            return dict(rows[0])
        time.sleep(0.1)
    raise BaselineMaterializationError("baseline_run_terminal_timeout")


def materialize(
    *,
    runtime_root: Path,
    decision_path: Path,
    source_decision_path: Path,
) -> dict[str, Any]:
    """Materialize the frozen S3-T09 baseline once through the production runtime path."""

    runtime_root = runtime_root.resolve()
    decision_path = decision_path.resolve()
    source_decision_path = source_decision_path.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    source = json.loads(source_decision_path.read_text(encoding="utf-8"))

    prospective = prepare(
        runtime_root=runtime_root,
        source_decision_path=source_decision_path,
    )
    frozen = decision["prospective_baseline"]
    binding = decision["source_binding"]
    identity = prospective["identity"]
    _require(
        prospective["double_prepare"]["payload_digest"]
        == frozen["prospective_payload_digest"],
        "baseline_prospective_payload_digest_mismatch",
    )
    for field in ("work_unit_id", "attempt_id", "research_run_id", "artifact_refs"):
        _require(identity[field] == frozen[field], f"baseline_frozen_{field}_mismatch")
    _require(
        identity["execution_identity"] == BASELINE_EXECUTION_IDENTITY,
        "baseline_execution_identity_mismatch",
    )
    _require(
        identity["execution_profile_version_ref"] == FIN01_DETERMINISTIC_PROFILE_REF,
        "baseline_profile_mismatch",
    )
    _require(
        tuple(prospective["double_prepare"]["program_cell_ids"]) == EXPECTED_CELLS,
        "baseline_program_cell_contract_mismatch",
    )
    _require(
        tuple(prospective["double_prepare"]["artifact_types"])
        == EXPECTED_ARTIFACT_TYPES,
        "baseline_artifact_type_contract_mismatch",
    )

    preflight_audit = prospective["target_read_only_audit"]
    frozen_audit = decision["preflight_safety"]
    _require(
        preflight_audit["canonical_database_sha256"]
        == frozen_audit["target_database_sha256_before_and_after"],
        "baseline_target_database_hash_guard_failed",
    )
    _require(
        preflight_audit["canonical_object_tree_sha256"]
        == frozen_audit["target_object_tree_sha256_before_and_after"],
        "baseline_target_object_hash_guard_failed",
    )

    case_id = str(binding["case_id"])
    expected_work_unit_id = str(frozen["work_unit_id"])
    expected_attempt_id = str(frozen["attempt_id"])
    expected_run_id = str(frozen["research_run_id"])
    expected_artifact_refs = dict(frozen["artifact_refs"])
    agent_run_id = str(binding["agent_research_run_id"])
    agent_attempt_id = str(source["input_binding"]["attempt_id"])

    before_database_digest = _sha256(database_path)
    before_object_tree_digest = _tree_digest(object_root)
    before_objects = _object_snapshot(object_root)
    before_logical = _logical_snapshot(database_path, case_id)
    tracked_tables = (
        "canonical_work_units",
        "canonical_attempts",
        "canonical_research_run_versions",
        "canonical_artifact_versions",
    )
    before_latest = {
        table: _latest_by_id(database_path, table) for table in tracked_tables
    }
    agent_run_before = before_latest["canonical_research_run_versions"].get(agent_run_id)
    _require(agent_run_before is not None, "baseline_source_agent_run_missing")
    agent_artifacts_before = {
        logical_id: row
        for logical_id, row in before_latest["canonical_artifact_versions"].items()
        if row.get("producer_attempt_id") == agent_attempt_id
    }
    _require(bool(agent_artifacts_before), "baseline_source_agent_artifacts_missing")

    case_service = CaseService.for_fixture_root(canonical_root, repo_root=ROOT)
    local_service = P36LocalResearchService.from_case_service(
        case_service, repo_root=ROOT
    )
    s4_case_ticker = str(
        source["input_binding"].get("s4_case_ticker") or ""
    ).strip()
    s4_binding = None
    s4_overlay = None
    if s4_case_ticker:
        admission_ref = str(
            source["input_binding"].get(
                "source_agent_admission_ref"
            )
            or ""
        )
        if admission_ref:
            admission = S3ThreeCellBoundedAgentAdmission.model_validate(
                json.loads(
                    (ROOT / admission_ref).read_text(encoding="utf-8")
                )
            )
            s4_binding, s4_overlay = (
                resolve_s4_case_runtime_binding_for_admission(
                    ROOT,
                    admission,
                )
            )
        else:
            s4_binding = load_s4_case_runtime_binding(
                ROOT,
                s4_case_ticker,
            )
    app = create_app(
        runtime_root / "workbench.sqlite",
        p02_case_service=case_service,
        p36_local_research_service=local_service,
        s4_deterministic_binding=s4_binding,
        s4_deterministic_source_pack=(
            load_s4_source_grounded_input_pack(ROOT, s4_case_ticker)
            if s4_case_ticker
            else None
        ),
        s4_deterministic_research_profile_overlay=s4_overlay,
    )
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/cases/{case_id}/work-units",
            headers=_headers(),
            json={
                "work_unit_type": VT1_WORK_UNIT_TYPE,
                "expected_case_version": int(binding["case_version"]),
                "input_head_digest": str(binding["input_head_digest"]),
                "actor_ref": ACTOR_ID,
                "idempotency_key": BASELINE_EXECUTION_IDENTITY,
            },
        )
        _require(
            response.status_code == 202,
            f"baseline_create_work_unit_failed:{response.status_code}:{response.text}",
        )
        terminal = _wait_for_exact_run(
            client,
            case_id=case_id,
            research_run_id=expected_run_id,
        )
    _require(terminal.get("state") == "succeeded", "baseline_run_not_succeeded")

    after_database_digest = _sha256(database_path)
    after_object_tree_digest = _tree_digest(object_root)
    after_objects = _object_snapshot(object_root)
    after_logical = _logical_snapshot(database_path, case_id)
    after_latest = {
        table: _latest_by_id(database_path, table) for table in tracked_tables
    }

    expected_new_ids = {
        "canonical_work_units": {expected_work_unit_id},
        "canonical_attempts": {expected_attempt_id},
        "canonical_research_run_versions": {expected_run_id},
        "canonical_artifact_versions": {
            ref.rsplit(":v", 1)[0] for ref in expected_artifact_refs.values()
        },
    }
    logical_deltas: dict[str, list[str]] = {}
    for table in tracked_tables:
        before_rows = before_latest[table]
        after_rows = after_latest[table]
        _require(
            all(after_rows.get(logical_id) == row for logical_id, row in before_rows.items()),
            f"baseline_existing_{table}_changed",
        )
        added = set(after_rows).difference(before_rows)
        _require(added == expected_new_ids[table], f"baseline_{table}_delta_mismatch")
        logical_deltas[table] = sorted(added)

    work_unit = after_latest["canonical_work_units"][expected_work_unit_id]
    attempt = after_latest["canonical_attempts"][expected_attempt_id]
    run = after_latest["canonical_research_run_versions"][expected_run_id]
    _require(work_unit.get("state") == "succeeded", "baseline_work_unit_not_succeeded")
    _require(work_unit.get("idempotency_key") == BASELINE_EXECUTION_IDENTITY, "baseline_work_unit_key_mismatch")
    _require(int(work_unit.get("max_attempts", -1)) == 1, "baseline_max_attempts_mismatch")
    _require(int(work_unit.get("retry_budget", -1)) == 0, "baseline_retry_budget_mismatch")
    _require(attempt.get("state") == "succeeded", "baseline_attempt_not_succeeded")
    _require(int(attempt.get("attempt_no", -1)) == 1, "baseline_attempt_number_mismatch")
    _require(attempt.get("work_unit_id") == expected_work_unit_id, "baseline_attempt_work_unit_mismatch")
    _require(run.get("state") == "succeeded", "baseline_research_run_not_succeeded")
    _require(run.get("attempt_id") == expected_attempt_id, "baseline_run_attempt_mismatch")
    _require(run.get("work_unit_id") == expected_work_unit_id, "baseline_run_work_unit_mismatch")
    _require(
        run.get("execution_profile_version_ref") == FIN01_DETERMINISTIC_PROFILE_REF,
        "baseline_run_profile_mismatch",
    )
    _require(expected_run_id != agent_run_id, "baseline_agent_run_substitution_detected")

    facade = case_service._facade
    artifact_manifest: dict[str, dict[str, Any]] = {}
    artifact_payloads: dict[str, Mapping[str, Any]] = {}
    for artifact_type in EXPECTED_ARTIFACT_TYPES:
        expected_ref = expected_artifact_refs[artifact_type]
        artifact_id = expected_ref.rsplit(":v", 1)[0]
        row = after_latest["canonical_artifact_versions"][artifact_id]
        _require(_artifact_ref(row) == expected_ref, f"baseline_{artifact_type}_ref_mismatch")
        _require(row.get("artifact_type") == artifact_type, f"baseline_{artifact_type}_type_mismatch")
        _require(row.get("producer_attempt_id") == expected_attempt_id, f"baseline_{artifact_type}_attempt_mismatch")
        loaded = facade.get_artifact_version(expected_ref, include_payload=True)
        payload = loaded["payload"]
        _require(isinstance(payload, Mapping), f"baseline_{artifact_type}_payload_missing")
        artifact_payloads[artifact_type] = payload
        artifact_manifest[artifact_type] = {
            "artifact_ref": expected_ref,
            "object_key": row["object_key"],
            "object_digest": row["object_digest"],
            "content_digest": row["content_digest"],
            "producer_attempt_id": row["producer_attempt_id"],
        }

    primary = artifact_payloads[EXPECTED_ARTIFACT_TYPES[0]]
    result = primary.get("result")
    _require(isinstance(result, Mapping), "baseline_deterministic_result_missing")
    execution_counts = result.get("execution_counts")
    hard_boundaries = result.get("hard_boundaries")
    _require(isinstance(execution_counts, Mapping), "baseline_execution_counts_missing")
    _require(isinstance(hard_boundaries, Mapping), "baseline_hard_boundaries_missing")
    for key in ("model_calls", "provider_calls", "network_calls", "external_tool_calls"):
        _require(int(execution_counts.get(key, -1)) == 0, f"baseline_nonzero_{key}")
    for key in (
        "case_mutations",
        "canonical_store_writes",
        "evidence_promotions",
        "network_calls",
        "model_calls",
        "release_admission",
    ):
        _require(int(hard_boundaries.get(key, -1)) == 0, f"baseline_boundary_violation_{key}")
    plan = primary.get("s3_runtime_plan")
    _require(isinstance(plan, Mapping), "baseline_runtime_plan_missing")
    _require(
        tuple(row.get("program_cell_id") for row in plan.get("cell_branches", ()))
        == EXPECTED_CELLS,
        "baseline_persisted_three_cell_contract_mismatch",
    )

    agent_run_after = after_latest["canonical_research_run_versions"].get(agent_run_id)
    agent_artifacts_after = {
        logical_id: row
        for logical_id, row in after_latest["canonical_artifact_versions"].items()
        if row.get("producer_attempt_id") == agent_attempt_id
    }
    _require(agent_run_after == agent_run_before, "baseline_source_agent_run_changed")
    _require(agent_artifacts_after == agent_artifacts_before, "baseline_source_agent_artifacts_changed")
    _require(before_logical["case"] == after_logical["case"], "baseline_live_case_head_changed")
    _require(before_logical["case_control"] == after_logical["case_control"], "baseline_case_control_changed")

    added_objects = set(after_objects).difference(before_objects)
    changed_existing_objects = {
        key for key, digest in before_objects.items() if after_objects.get(key) != digest
    }
    expected_object_keys = {
        str(row["object_key"]) for row in artifact_manifest.values()
    }
    _require(not changed_existing_objects, "baseline_existing_object_changed")
    _require(added_objects == expected_object_keys, "baseline_object_delta_mismatch")

    count_delta = {
        table: int(after_logical["counts"][table]) - int(before_logical["counts"][table])
        for table in before_logical["counts"]
    }
    return {
        "status": "pass_exact_once_deterministic_baseline_materialized",
        "contract_ref": "fin01.s3.paired_three_cell_deterministic_baseline:v1",
        "runtime_root": runtime_root.relative_to(ROOT).as_posix() if runtime_root.is_relative_to(ROOT) else str(runtime_root),
        "source_decision_ref": source_decision_path.relative_to(ROOT).as_posix() if source_decision_path.is_relative_to(ROOT) else str(source_decision_path),
        "materialization_decision_ref": decision_path.relative_to(ROOT).as_posix() if decision_path.is_relative_to(ROOT) else str(decision_path),
        "identity": {
            "execution_identity": BASELINE_EXECUTION_IDENTITY,
            "case_id": case_id,
            "case_version": int(binding["case_version"]),
            "analysis_as_of": binding["analysis_as_of"],
            "decision_surface_ref": binding["decision_surface_ref"],
            "input_head_digest": binding["input_head_digest"],
            "work_unit_id": expected_work_unit_id,
            "attempt_id": expected_attempt_id,
            "research_run_id": expected_run_id,
            "execution_profile_version_ref": FIN01_DETERMINISTIC_PROFILE_REF,
            "program_cell_ids": list(EXPECTED_CELLS),
        },
        "terminal_states": {
            "work_unit": work_unit["state"],
            "attempt": attempt["state"],
            "research_run": run["state"],
            "attempt_no": int(attempt["attempt_no"]),
            "maximum_attempts": int(work_unit["max_attempts"]),
            "retry_budget": int(work_unit["retry_budget"]),
        },
        "artifact_manifest": artifact_manifest,
        "prospective_parity": {
            "double_prepare_equal": prospective["double_prepare"]["equal"],
            "prospective_payload_digest": prospective["double_prepare"]["payload_digest"],
            "exact_identity_match": True,
            "exact_artifact_ref_match": True,
        },
        "canonical_delta": {
            "logical_ids_added": logical_deltas,
            "row_count_delta": count_delta,
            "object_keys_added": sorted(added_objects),
            "existing_logical_objects_unchanged": True,
            "existing_object_payloads_unchanged": True,
            "database_sha256_before": before_database_digest,
            "database_sha256_after": after_database_digest,
            "object_tree_sha256_before": before_object_tree_digest,
            "object_tree_sha256_after": after_object_tree_digest,
        },
        "observed_counts": {
            "baseline_materializations": 1,
            "new_work_units": 1,
            "new_attempts": 1,
            "new_research_runs": 1,
            "new_artifacts": 4,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "evidence_promotions": 0,
            "live_case_head_writes": 0,
            "agent_reruns": 0,
            "human_review_writes": 0,
        },
        "boundary": {
            "source_agent_run_and_artifacts_unchanged": True,
            "automatic_fallback_or_agent_substitution": False,
            "baseline_body_exposed_to_agent": False,
            "baseline_labeled_as_agent_output": False,
            "paired_comparison_performed": False,
            "human_acceptance_signed": False,
            "T10_or_S4_entered": False,
        },
    }


def verify_materialized(
    *,
    runtime_root: Path,
    decision_path: Path,
    source_decision_path: Path,
) -> dict[str, Any]:
    """Verify the consumed exact-once baseline using read-only SQLite and object reads."""

    runtime_root = runtime_root.resolve()
    decision = json.loads(decision_path.resolve().read_text(encoding="utf-8"))
    source = json.loads(source_decision_path.resolve().read_text(encoding="utf-8"))
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    binding = decision["source_binding"]
    frozen = decision["prospective_baseline"]
    case_id = str(binding["case_id"])
    work_unit_id = str(frozen["work_unit_id"])
    attempt_id = str(frozen["attempt_id"])
    research_run_id = str(frozen["research_run_id"])
    expected_artifact_refs = dict(frozen["artifact_refs"])

    work_units = _latest_by_id(database_path, "canonical_work_units")
    attempts = _latest_by_id(database_path, "canonical_attempts")
    runs = _latest_by_id(database_path, "canonical_research_run_versions")
    artifacts = _latest_by_id(database_path, "canonical_artifact_versions")
    cases = _latest_by_id(database_path, "canonical_research_cases")
    controls = _latest_by_id(database_path, "canonical_case_control_versions")
    work_unit = work_units.get(work_unit_id)
    attempt = attempts.get(attempt_id)
    run = runs.get(research_run_id)
    _require(work_unit is not None, "baseline_materialized_work_unit_missing")
    _require(attempt is not None, "baseline_materialized_attempt_missing")
    _require(run is not None, "baseline_materialized_run_missing")
    _require(work_unit.get("state") == "succeeded", "baseline_materialized_work_unit_not_succeeded")
    _require(attempt.get("state") == "succeeded", "baseline_materialized_attempt_not_succeeded")
    _require(run.get("state") == "succeeded", "baseline_materialized_run_not_succeeded")
    _require(work_unit.get("idempotency_key") == BASELINE_EXECUTION_IDENTITY, "baseline_materialized_key_mismatch")
    _require(int(work_unit.get("max_attempts", -1)) == 1, "baseline_materialized_max_attempts_mismatch")
    _require(int(work_unit.get("retry_budget", -1)) == 0, "baseline_materialized_retry_budget_mismatch")
    _require(int(attempt.get("attempt_no", -1)) == 1, "baseline_materialized_attempt_number_mismatch")
    _require(attempt.get("work_unit_id") == work_unit_id, "baseline_materialized_attempt_binding_mismatch")
    _require(run.get("attempt_id") == attempt_id, "baseline_materialized_run_attempt_mismatch")
    _require(run.get("work_unit_id") == work_unit_id, "baseline_materialized_run_work_unit_mismatch")
    _require(
        run.get("execution_profile_version_ref") == FIN01_DETERMINISTIC_PROFILE_REF,
        "baseline_materialized_profile_mismatch",
    )
    deterministic_runs = [
        row
        for row in runs.values()
        if row.get("case_id") == case_id
        and row.get("execution_profile_version_ref") == FIN01_DETERMINISTIC_PROFILE_REF
    ]
    _require(
        len(deterministic_runs) == 1
        and deterministic_runs[0].get("research_run_id") == research_run_id,
        "baseline_materialized_run_cardinality_mismatch",
    )

    case = cases.get(case_id)
    _require(case is not None, "baseline_materialized_case_missing")
    _require(int(case.get("case_version", -1)) == int(binding["case_version"]), "baseline_materialized_case_version_mismatch")
    control_ref = str(case.get("case_control_summary_ref") or "")
    control = controls.get(control_ref)
    _require(control is not None, "baseline_materialized_case_control_missing")
    _require(str(control.get("as_of")) == str(binding["analysis_as_of"]), "baseline_materialized_as_of_mismatch")
    _require(
        tuple(work_unit.get("input_version_refs") or ())
        == (str(binding["decision_surface_ref"]),),
        "baseline_materialized_decision_surface_mismatch",
    )
    _require(
        str(work_unit.get("input_head_digest")) == str(binding["input_head_digest"]),
        "baseline_materialized_input_head_mismatch",
    )

    manifest: dict[str, dict[str, Any]] = {}
    primary_payload: Mapping[str, Any] | None = None
    for artifact_type in EXPECTED_ARTIFACT_TYPES:
        expected_ref = expected_artifact_refs[artifact_type]
        artifact_id = expected_ref.rsplit(":v", 1)[0]
        row = artifacts.get(artifact_id)
        _require(row is not None, f"baseline_materialized_{artifact_type}_missing")
        _require(_artifact_ref(row) == expected_ref, f"baseline_materialized_{artifact_type}_ref_mismatch")
        _require(row.get("artifact_type") == artifact_type, f"baseline_materialized_{artifact_type}_type_mismatch")
        _require(row.get("producer_attempt_id") == attempt_id, f"baseline_materialized_{artifact_type}_attempt_mismatch")
        object_key = str(row.get("object_key") or "")
        object_path = (object_root / object_key).resolve()
        _require(object_path.is_relative_to(object_root.resolve()), f"baseline_materialized_{artifact_type}_object_path_invalid")
        _require(object_path.is_file(), f"baseline_materialized_{artifact_type}_object_missing")
        _require(_sha256(object_path) == row.get("object_digest"), f"baseline_materialized_{artifact_type}_object_digest_mismatch")
        payload = json.loads(object_path.read_text(encoding="utf-8"))
        _require(isinstance(payload, Mapping), f"baseline_materialized_{artifact_type}_payload_invalid")
        if artifact_type == EXPECTED_ARTIFACT_TYPES[0]:
            primary_payload = payload
        manifest[artifact_type] = {
            "artifact_ref": expected_ref,
            "object_key": object_key,
            "object_digest": row["object_digest"],
            "producer_attempt_id": row["producer_attempt_id"],
        }
    _require(primary_payload is not None, "baseline_materialized_primary_payload_missing")
    result = primary_payload.get("result")
    _require(isinstance(result, Mapping), "baseline_materialized_result_missing")
    execution_counts = result.get("execution_counts")
    hard_boundaries = result.get("hard_boundaries")
    _require(isinstance(execution_counts, Mapping), "baseline_materialized_counts_missing")
    _require(isinstance(hard_boundaries, Mapping), "baseline_materialized_boundaries_missing")
    for key in ("model_calls", "provider_calls", "network_calls", "external_tool_calls"):
        _require(int(execution_counts.get(key, -1)) == 0, f"baseline_materialized_nonzero_{key}")
    for key in ("case_mutations", "evidence_promotions", "network_calls", "model_calls", "release_admission"):
        _require(int(hard_boundaries.get(key, -1)) == 0, f"baseline_materialized_boundary_violation_{key}")
    plan = primary_payload.get("s3_runtime_plan")
    _require(isinstance(plan, Mapping), "baseline_materialized_runtime_plan_missing")
    _require(
        tuple(row.get("program_cell_id") for row in plan.get("cell_branches", ()))
        == EXPECTED_CELLS,
        "baseline_materialized_three_cell_contract_mismatch",
    )

    agent_run_id = str(binding["agent_research_run_id"])
    agent_attempt_id = str(source["input_binding"]["attempt_id"])
    agent_run = runs.get(agent_run_id)
    _require(agent_run is not None and agent_run.get("state") == "succeeded", "baseline_source_agent_terminal_truth_missing")
    agent_artifacts = [
        row for row in artifacts.values() if row.get("producer_attempt_id") == agent_attempt_id
    ]
    _require(len(agent_artifacts) == 9, "baseline_source_agent_artifact_set_changed")

    return {
        "status": "pass_materialized_baseline_read_only_verification",
        "identity": {
            "work_unit_id": work_unit_id,
            "attempt_id": attempt_id,
            "research_run_id": research_run_id,
            "execution_profile_version_ref": FIN01_DETERMINISTIC_PROFILE_REF,
            "program_cell_ids": list(EXPECTED_CELLS),
        },
        "terminal_states": {
            "work_unit": work_unit["state"],
            "attempt": attempt["state"],
            "research_run": run["state"],
            "attempt_no": int(attempt["attempt_no"]),
            "maximum_attempts": int(work_unit["max_attempts"]),
            "retry_budget": int(work_unit["retry_budget"]),
        },
        "artifact_manifest": manifest,
        "target_read_only_audit": {
            "canonical_database_sha256": _sha256(database_path),
            "canonical_object_tree_sha256": _tree_digest(object_root),
            "exact_deterministic_run_cardinality": 1,
            "exact_artifact_count": 4,
            "source_agent_artifact_count": len(agent_artifacts),
        },
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "evidence_promotions": 0,
            "agent_reruns": 0,
            "human_review_writes": 0,
        },
        "boundary": {
            "read_only_verification": True,
            "paired_comparison_performed": False,
            "human_acceptance_signed": False,
            "T10_or_S4_entered": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=ROOT
        / ".codex_runtime"
        / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1",
    )
    parser.add_argument(
        "--decision",
        type=Path,
        default=ROOT
        / "configs"
        / "releases"
        / "fin_ia_0_1_s3_t09_paired_deterministic_baseline_materialization_decision_v1_0.json",
    )
    parser.add_argument(
        "--source-decision",
        type=Path,
        default=ROOT
        / "configs"
        / "releases"
        / "fin_ia_0_1_s3_t09_replacement_live_artifact_paired_baseline_decision_v1_0.json",
    )
    args = parser.parse_args()
    operation = verify_materialized if args.verify_only else materialize
    print(
        json.dumps(
            operation(
                runtime_root=args.runtime_root,
                decision_path=args.decision,
                source_decision_path=args.source_decision,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
