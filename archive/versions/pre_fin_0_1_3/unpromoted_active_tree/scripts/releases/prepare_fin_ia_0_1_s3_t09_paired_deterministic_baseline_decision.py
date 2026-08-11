from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.case_service import CasePrincipal, CaseService
from apps.workbench.backend.application.evidence_service import EvidenceService
from apps.workbench.backend.application.execution_service import (
    VT1_WORK_UNIT_TYPE,
    predict_work_unit_id,
)
from apps.workbench.backend.application.local_research_service import P36LocalResearchService
from apps.workbench.backend.application.bounded_agent_executor import (
    S3ThreeCellBoundedAgentAdmission,
    resolve_s4_case_runtime_binding_for_admission,
)
from apps.workbench.backend.application.research_runtime import (
    FIN01_DETERMINISTIC_ARTIFACT_TYPE,
    FIN01_DETERMINISTIC_PROFILE_REF,
    FIN01_S3_REPORT_ARTIFACT_TYPE,
    FIN01_S3_TRACE_REVIEW_ARTIFACT_TYPE,
    FIN01_S3_WORKPAPER_ARTIFACT_TYPE,
    Fin01ResearchRuntime,
    ProfileExecutionContext,
    _fin01_artifact_id,
    compile_fin01_s3_three_cell_runtime_plan,
    compile_profile_evidence_dispatch,
    predict_fin01_attempt_and_run_ids,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s4_case_runtime import (
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)


BASELINE_EXECUTION_IDENTITY = (
    "fin01-s3-t09-paired-deterministic-baseline-materialization-r1"
)
EXPECTED_ARTIFACT_TYPES = (
    FIN01_DETERMINISTIC_ARTIFACT_TYPE,
    FIN01_S3_WORKPAPER_ARTIFACT_TYPE,
    FIN01_S3_REPORT_ARTIFACT_TYPE,
    FIN01_S3_TRACE_REVIEW_ARTIFACT_TYPE,
)
EXPECTED_CELLS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)
TENANT_ID = "tenant-fin01-s3-t09-eval"
PROJECT_ID = "project-fin01-s3-t09-eval"
ACTOR_ID = "analyst-fin01-s3-t09-eval"


class BaselineDecisionPreflightError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise BaselineDecisionPreflightError(code)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(_sha256(path).encode("ascii"))
    return digest.hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else str(resolved)
    )


def _open_read_only(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("pragma query_only = on")
    return connection


def _latest_payloads(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for logical_id, payload_json in connection.execute(
        f"select logical_id, payload_json from {table} order by row_id"
    ):
        latest[str(logical_id)] = json.loads(str(payload_json))
    return list(latest.values())


def _logical_snapshot(database_path: Path, case_id: str) -> dict[str, Any]:
    connection = _open_read_only(database_path)
    try:
        tables = (
            "canonical_work_units",
            "canonical_attempts",
            "canonical_research_run_versions",
            "canonical_artifact_versions",
            "canonical_events",
            "canonical_idempotency",
        )
        counts = {
            table: int(connection.execute(f"select count(*) from {table}").fetchone()[0])
            for table in tables
        }
        cases = [
            row
            for row in _latest_payloads(connection, "canonical_research_cases")
            if row.get("case_id") == case_id
        ]
        controls = [
            row
            for row in _latest_payloads(connection, "canonical_case_control_versions")
            if row.get("case_id") == case_id
        ]
        work_units = [
            row
            for row in _latest_payloads(connection, "canonical_work_units")
            if row.get("case_id") == case_id
        ]
        attempts = [
            row
            for row in _latest_payloads(connection, "canonical_attempts")
            if row.get("case_id") == case_id
        ]
        runs = [
            row
            for row in _latest_payloads(connection, "canonical_research_run_versions")
            if row.get("case_id") == case_id
        ]
        artifacts = [
            row
            for row in _latest_payloads(connection, "canonical_artifact_versions")
            if row.get("case_id") == case_id
        ]
    finally:
        connection.close()
    _require(len(cases) == 1, "baseline_case_required")
    _require(len(controls) == 1, "baseline_case_control_required")
    return {
        "counts": counts,
        "case": cases[0],
        "case_control": controls[0],
        "work_unit_ids": sorted(str(row["work_unit_id"]) for row in work_units),
        "attempt_ids": sorted(str(row["attempt_id"]) for row in attempts),
        "research_run_ids": sorted(str(row["research_run_id"]) for row in runs),
        "artifact_refs": sorted(
            f"{row['artifact_id']}:v{row['artifact_version']}" for row in artifacts
        ),
    }


def _principal() -> CasePrincipal:
    return CasePrincipal(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        actor_id=ACTOR_ID,
        permissions=frozenset({"case:read", "execution:read", "evidence:read"}),
    )


def prepare(
    *,
    runtime_root: Path,
    source_decision_path: Path,
) -> dict[str, Any]:
    runtime_root = runtime_root.resolve()
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    source = json.loads(source_decision_path.read_text(encoding="utf-8"))
    binding = source["input_binding"]
    agent_run_id = str(binding["research_run_id"])
    case_id = str(binding["case_id"])
    decision_surface_ref = str(binding["decision_surface_ref"])
    s4_case_ticker = str(binding.get("s4_case_ticker") or "").strip()

    before_database_digest = _sha256(database_path)
    before_object_digest = _tree_digest(object_root)
    before_snapshot = _logical_snapshot(database_path, case_id)
    case = before_snapshot["case"]
    case_control = before_snapshot["case_control"]
    _require(int(case["case_version"]) == int(binding["case_version"]), "case_version_mismatch")
    _require(str(case_control["as_of"]) == str(binding["analysis_as_of"]), "case_as_of_mismatch")

    work_unit_id = predict_work_unit_id(
        tenant_id=TENANT_ID,
        project_id=PROJECT_ID,
        case_id=case_id,
        contract_version_id=decision_surface_ref,
        work_unit_type=VT1_WORK_UNIT_TYPE,
        execution_identity=BASELINE_EXECUTION_IDENTITY,
    )
    attempt_id, research_run_id = predict_fin01_attempt_and_run_ids(
        work_unit_id=work_unit_id,
        execution_profile_version_ref=FIN01_DETERMINISTIC_PROFILE_REF,
    )
    artifact_refs = {
        artifact_type: f"{_fin01_artifact_id(research_run_id, artifact_type)}:v1"
        for artifact_type in EXPECTED_ARTIFACT_TYPES
    }
    _require(work_unit_id not in before_snapshot["work_unit_ids"], "baseline_work_unit_not_fresh")
    _require(attempt_id not in before_snapshot["attempt_ids"], "baseline_attempt_not_fresh")
    _require(research_run_id not in before_snapshot["research_run_ids"], "baseline_run_not_fresh")
    _require(
        not set(artifact_refs.values()).intersection(before_snapshot["artifact_refs"]),
        "baseline_artifacts_not_fresh",
    )
    _require(research_run_id != agent_run_id, "baseline_run_must_be_distinct_from_agent")

    with tempfile.TemporaryDirectory(prefix="fin01-s3-t09-baseline-decision-") as temp_dir:
        clone_root = Path(temp_dir) / "canonical-runtime"
        shutil.copytree(canonical_root, clone_root)
        case_service = CaseService.for_fixture_root(clone_root, repo_root=ROOT)
        local_service = P36LocalResearchService.from_case_service(case_service, repo_root=ROOT)
        evidence_service = EvidenceService.from_case_service(case_service, repo_root=ROOT)
        s4_overlay = None
        if s4_case_ticker:
            admission_ref = str(
                binding.get("source_agent_admission_ref") or ""
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
        else:
            s4_binding = None
        s4_source_pack = (
            load_s4_source_grounded_input_pack(ROOT, s4_case_ticker)
            if s4_case_ticker
            else None
        )
        runtime = Fin01ResearchRuntime(
            case_service._facade,
            local_service,
            evidence_service,
            s4_deterministic_binding=s4_binding,
            s4_deterministic_source_pack=s4_source_pack,
            s4_deterministic_research_profile_overlay=s4_overlay,
        )
        profile = runtime.execution_profile
        plan = compile_fin01_s3_three_cell_runtime_plan(
            case_id=case_id,
            work_unit_id=work_unit_id,
            attempt_id=attempt_id,
            research_run_id=research_run_id,
            execution_profile_version_ref=FIN01_DETERMINISTIC_PROFILE_REF,
            decision_surface_contract_ref=decision_surface_ref,
        )
        evidence_dispatch = compile_profile_evidence_dispatch(
            evidence_service,
            runtime_plan=plan,
            principal=_principal(),
            s4_binding=s4_binding,
            prospective_execution_lineage=True,
        )
        plan = evidence_dispatch.runtime_plan
        route = evidence_dispatch.s3_evidence_route_plan
        context = ProfileExecutionContext(
            case_id=case_id,
            case_query=str(case_control["query"]),
            work_unit_id=work_unit_id,
            attempt_id=attempt_id,
            research_run_id=research_run_id,
            causation_event_id="prospective:no-canonical-event",
            execution_profile_version_ref=FIN01_DETERMINISTIC_PROFILE_REF,
            s3_runtime_plan=plan,
            s3_evidence_route_plan=route,
            s4_evidence_slot_alignment=(
                evidence_dispatch.s4_evidence_slot_alignment
            ),
            evidence_dispatch_digest=(
                evidence_dispatch.evidence_dispatch_digest
            ),
        )
        adapter = runtime._adapters[FIN01_DETERMINISTIC_PROFILE_REF]
        first = adapter.execute(context, _principal())
        second = adapter.execute(context, _principal())
        runtime._validate_profile_result(profile, first, case_id=case_id)
        first_payload = first.model_dump(mode="json")
        second_payload = second.model_dump(mode="json")
        _require(first_payload == second_payload, "baseline_double_prepare_parity_failed")
        _require(
            (first.artifact_type, *(row.artifact_type for row in first.artifacts))
            == EXPECTED_ARTIFACT_TYPES,
            "baseline_artifact_type_contract_mismatch",
        )
        _require(
            tuple(row.program_cell_id for row in plan.cell_branches) == EXPECTED_CELLS,
            "baseline_three_cell_contract_mismatch",
        )
        payload_digest = canonical_digest(first_payload)
        execution_counts = dict(first.payload["result"]["execution_counts"])
        hard_boundaries = dict(first.payload["result"]["hard_boundaries"])

    after_snapshot = _logical_snapshot(database_path, case_id)
    after_database_digest = _sha256(database_path)
    after_object_digest = _tree_digest(object_root)
    _require(before_snapshot == after_snapshot, "target_canonical_logical_state_changed")
    _require(before_database_digest == after_database_digest, "target_canonical_file_changed")
    _require(before_object_digest == after_object_digest, "target_object_tree_changed")
    paired_input_head_digest = (
        str(first.payload["input_head_digest"])
        if s4_case_ticker
        else canonical_digest((decision_surface_ref,))
    )
    input_head_digest = canonical_digest((decision_surface_ref,))
    _require(
        input_head_digest == str(binding["input_head_digest"]),
        "baseline_canonical_input_head_mismatch",
    )
    _require(
        paired_input_head_digest
        == str(
            binding.get(
                "paired_input_head_digest",
                binding["input_head_digest"],
            )
        ),
        "baseline_agent_paired_input_head_mismatch",
    )
    for key in ("model_calls", "provider_calls", "network_calls", "external_tool_calls"):
        _require(int(execution_counts[key]) == 0, f"baseline_nonzero_{key}")
    for key in (
        "case_mutations",
        "canonical_store_writes",
        "evidence_promotions",
        "network_calls",
        "model_calls",
        "release_admission",
    ):
        _require(int(hard_boundaries[key]) == 0, f"baseline_boundary_violation_{key}")

    return {
        "status": "pass_prospective_baseline_double_prepared_on_disposable_clone",
        "contract_ref": "fin01.s3.paired_three_cell_deterministic_baseline:v1",
        "baseline_variant": (
            "s4_source_grounded_case_local"
            if s4_case_ticker
            else "s3_legacy_three_cell"
        ),
        "source_decision_ref": _display_path(source_decision_path),
        "runtime_root": _display_path(runtime_root),
        "identity": {
            "execution_identity": BASELINE_EXECUTION_IDENTITY,
            "case_id": case_id,
            "case_version": int(binding["case_version"]),
            "analysis_as_of": binding["analysis_as_of"],
            "decision_surface_ref": decision_surface_ref,
            "input_head_digest": input_head_digest,
            "paired_input_head_digest": paired_input_head_digest,
            "work_unit_id": work_unit_id,
            "attempt_id": attempt_id,
            "research_run_id": research_run_id,
            "execution_profile_version_ref": FIN01_DETERMINISTIC_PROFILE_REF,
            "artifact_refs": artifact_refs,
        },
        "double_prepare": {
            "equal": True,
            "payload_digest": payload_digest,
            "program_cell_ids": list(EXPECTED_CELLS),
            "artifact_types": list(EXPECTED_ARTIFACT_TYPES),
        },
        "freshness": {
            "work_unit_absent": True,
            "attempt_absent": True,
            "research_run_absent": True,
            "artifact_refs_absent": True,
            "distinct_from_agent_research_run": True,
        },
        "target_read_only_audit": {
            "canonical_database_sha256": before_database_digest,
            "canonical_object_tree_sha256": before_object_digest,
            "logical_snapshot_unchanged": True,
            "canonical_database_file_unchanged": True,
            "canonical_object_tree_unchanged": True,
        },
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "target_canonical_writes": 0,
            "target_object_writes": 0,
            "baseline_materializations": 0,
            "agent_reruns": 0,
            "human_review_writes": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=ROOT
        / ".codex_runtime"
        / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1",
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
    print(
        json.dumps(
            prepare(
                runtime_root=args.runtime_root,
                source_decision_path=args.source_decision.resolve(),
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
