from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore


EXPECTED_ARTIFACT_TYPES = {
    "agent_fallback_comparison",
    "bounded_agent_evidence",
    "bounded_agent_judgment",
    "bounded_agent_manifest",
    "bounded_agent_numeric",
    "bounded_agent_report",
    "bounded_agent_trace",
    "bounded_agent_verification",
    "bounded_agent_workpaper",
}
EXPECTED_CELLS = [
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
]
EXPECTED_TOPOLOGY = [
    *(f"domain_specialist:{cell}" for cell in EXPECTED_CELLS),
    "research_lead",
    "memo_writer",
    "verifier",
]
AGENT_PROFILE = "fin01.execution_profile.bounded_agent_internal_three_cell:v1"
BASELINE_PROFILE = "fin01.execution_profile.p36_local_deterministic:v1"


class T09ReadOnlyValidationError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T09ReadOnlyValidationError(code)


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


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


def _latest_rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for logical_id, payload_json in connection.execute(
        f"select logical_id, payload_json from {table} order by row_id"
    ):
        latest[str(logical_id)] = json.loads(str(payload_json))
    return list(latest.values())


def _open_read_only(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.execute("pragma query_only = on")
    return connection


def _one(rows: list[dict[str, Any]], code: str) -> dict[str, Any]:
    _require(len(rows) == 1, code)
    return rows[0]


def load_exact_artifacts(
    runtime_root: Path,
    *,
    work_unit_id: str,
    attempt_id: str,
    research_run_id: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    _require(database_path.is_file(), "t09_canonical_database_required")
    _require(object_root.is_dir(), "t09_canonical_object_root_required")
    object_store = FileCanonicalObjectStore(object_root)

    connection = _open_read_only(database_path)
    try:
        work_unit = _one(
            [
                row
                for row in _latest_rows(connection, "canonical_work_units")
                if row.get("work_unit_id") == work_unit_id
            ],
            "t09_exact_work_unit_required",
        )
        attempt = _one(
            [
                row
                for row in _latest_rows(connection, "canonical_attempts")
                if row.get("attempt_id") == attempt_id
            ],
            "t09_exact_attempt_required",
        )
        research_run = _one(
            [
                row
                for row in _latest_rows(connection, "canonical_research_run_versions")
                if row.get("research_run_id") == research_run_id
            ],
            "t09_exact_research_run_required",
        )
        artifact_rows = [
            row
            for row in _latest_rows(connection, "canonical_artifact_versions")
            if row.get("producer_attempt_id") == attempt_id
        ]
    finally:
        connection.close()

    for item, code in (
        (work_unit, "t09_work_unit_must_be_succeeded"),
        (attempt, "t09_attempt_must_be_succeeded"),
        (research_run, "t09_research_run_must_be_succeeded"),
    ):
        _require(item.get("state") == "succeeded", code)
    _require(attempt.get("work_unit_id") == work_unit_id, "t09_attempt_work_unit_mismatch")
    _require(research_run.get("attempt_id") == attempt_id, "t09_run_attempt_mismatch")
    _require(research_run.get("work_unit_id") == work_unit_id, "t09_run_work_unit_mismatch")

    artifacts: dict[str, dict[str, Any]] = {}
    for metadata in artifact_rows:
        artifact_type = str(metadata.get("artifact_type") or "")
        _require(artifact_type not in artifacts, "t09_duplicate_artifact_type")
        artifacts[artifact_type] = {
            "metadata": metadata,
            "payload": object_store.get_json(
                str(metadata["object_key"]),
                expected_digest=str(metadata["object_digest"]),
            ),
        }
    _require(set(artifacts) == EXPECTED_ARTIFACT_TYPES, "t09_exact_nine_artifact_types_required")
    return artifacts, {
        "work_unit": work_unit,
        "attempt": attempt,
        "research_run": research_run,
    }


def classify_owner_grade_findings(payloads: Mapping[str, Mapping[str, Any]]) -> list[dict[str, str]]:
    judgment = _mapping(payloads["bounded_agent_judgment"], "t09_judgment_payload_required")
    report = _mapping(payloads["bounded_agent_report"], "t09_report_payload_required")
    lead = _mapping(judgment.get("cross_cell_lead"), "t09_cross_cell_lead_required")
    report_body = _mapping(report.get("report"), "t09_report_body_required")
    sections = report_body.get("sections")
    _require(isinstance(sections, list), "t09_report_sections_required")
    value_text = " ".join(
        str(row.get("content_zh_cn") or "")
        for row in sections
        if isinstance(row, Mapping) and row.get("program_cell_id") == EXPECTED_CELLS[1]
    )
    conflict_text = " ".join(str(item) for item in lead.get("conflict_adjudications", []))
    summary = str(report_body.get("executive_summary_zh_cn") or "")
    specialists = judgment.get("specialist_outputs")
    _require(isinstance(specialists, list), "t09_specialist_outputs_required")
    wwc_is_structured = all(
        isinstance(item, Mapping)
        for row in specialists
        if isinstance(row, Mapping)
        for item in row.get("what_would_change", [])
    )

    findings: list[dict[str, str]] = []
    if "NVDA通过数据中心部门捕获AI基础设施需求收入" in value_text:
        findings.append(
            {
                "finding_id": "unsupported_declarative_segment_revenue_claim",
                "severity": "high",
                "earliest_artifact": "bounded_agent_judgment.value_and_profit_capture.judgment_layer",
                "reason": "No promoted Evidence or segment/product Numeric fact authorizes a declarative segment revenue-capture statement; Writer propagated it without candidate/hypothesis qualification.",
            }
        )
    if "All cells are in non-fact states" in conflict_text:
        findings.append(
            {
                "finding_id": "lead_non_fact_state_wording_conflicts_with_numeric_fact_row",
                "severity": "medium",
                "earliest_artifact": "bounded_agent_judgment.cross_cell_lead.conflict_adjudications",
                "reason": "The Value cell contains one company-total Numeric fact row; the Lead should distinguish unresolved terminal class from absence of facts.",
            }
        )
    if "图表假设" in summary:
        findings.append(
            {
                "finding_id": "graph_hypothesis_mistranslated_as_chart_hypothesis",
                "severity": "medium",
                "earliest_artifact": "bounded_agent_report.report.executive_summary_zh_cn",
                "reason": "Graph navigation context was rendered as chart hypothesis, reducing domain precision.",
            }
        )
    if not wwc_is_structured:
        findings.append(
            {
                "finding_id": "what_would_change_lacks_actionable_source_metric_threshold_time_contract",
                "severity": "medium",
                "earliest_artifact": "fin01.s3.bounded_agent_three_cell_output:v2",
                "reason": "WWC is free text rather than an actionable source/metric/threshold/time tuple, so it cannot directly become an analyst follow-up task.",
            }
        )
    return findings


def validate_artifacts(
    artifacts: Mapping[str, Mapping[str, Any]],
    terminal: Mapping[str, Any],
    *,
    expected_input_digest: str,
    expected_input_head_digest: str,
    expected_attempt_id: str,
    expected_research_run_id: str,
    expected_artifact_refs: Mapping[str, str],
) -> dict[str, Any]:
    payloads: dict[str, Mapping[str, Any]] = {}
    object_digests: dict[str, str] = {}
    for artifact_type, item in artifacts.items():
        metadata = _mapping(item.get("metadata"), "t09_artifact_metadata_required")
        payload = _mapping(item.get("payload"), "t09_artifact_payload_required")
        version_id = str(metadata.get("artifact_version_id") or "")
        _require(version_id == expected_artifact_refs[artifact_type], "t09_artifact_ref_mismatch")
        _require(metadata.get("producer_attempt_id") == expected_attempt_id, "t09_artifact_attempt_mismatch")
        _require(payload.get("artifact_version_id") == version_id, "t09_payload_version_mismatch")
        _require(payload.get("research_run_id") == expected_research_run_id, "t09_payload_run_mismatch")
        payloads[artifact_type] = payload
        object_digests[artifact_type] = str(metadata.get("object_digest") or "")

    expected_manifest = dict(expected_artifact_refs)
    for payload in payloads.values():
        _require(payload.get("artifact_manifest") == expected_manifest, "t09_cross_artifact_manifest_mismatch")

    manifest = payloads["bounded_agent_manifest"]
    _require(manifest.get("input_digest") == expected_input_digest, "t09_manifest_input_digest_mismatch")
    _require(manifest.get("input_head_digest") == expected_input_head_digest, "t09_manifest_input_head_mismatch")
    _require(manifest.get("execution_profile_version_ref") == AGENT_PROFILE, "t09_agent_profile_mismatch")
    _require(manifest.get("output_contract_ref") == "fin01.s3.bounded_agent_three_cell_output:v2", "t09_output_v2_required")
    _require(manifest.get("program_cell_ids") == EXPECTED_CELLS, "t09_exact_cells_required")
    _require(manifest.get("node_topology") == EXPECTED_TOPOLOGY, "t09_exact_six_node_topology_required")
    observed = _mapping(manifest.get("observed_counts"), "t09_observed_counts_required")
    for field, expected in {
        "model_calls": 6,
        "provider_calls": 6,
        "network_calls": 6,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "live_case_head_writes": 0,
        "evaluation_evidence_promotions": 0,
    }.items():
        _require(observed.get(field) == expected, f"t09_observed_count_mismatch:{field}")
    boundaries = _mapping(manifest.get("hard_boundaries"), "t09_boundaries_required")
    _require(all(value == 0 for value in boundaries.values()), "t09_hard_boundary_nonzero")
    receipts = manifest.get("node_receipts")
    _require(isinstance(receipts, list) and len(receipts) == 6, "t09_exact_six_node_receipts_required")
    _require([row.get("node_id") for row in receipts] == EXPECTED_TOPOLOGY, "t09_receipt_topology_mismatch")
    for receipt in receipts[:3]:
        bindings = _mapping(receipt.get("version_bindings"), "t09_specialist_bindings_required")
        _require(bindings.get("model_view_contract_ref") == "fin01.s3.specialist_model_view:v1", "t09_specialist_model_view_required")

    evidence = payloads["bounded_agent_evidence"]
    _require(evidence.get("agent_fact_rows") == [], "t09_unpromoted_agent_fact_forbidden")
    _require(evidence.get("live_evidence_head_promoted") is False, "t09_live_evidence_promotion_forbidden")
    numeric = payloads["bounded_agent_numeric"]
    numeric_rows = numeric.get("agent_numeric_fact_rows")
    _require(isinstance(numeric_rows, list) and len(numeric_rows) == 1, "t09_exact_company_total_numeric_row_required")
    numeric_row = _mapping(numeric_rows[0], "t09_numeric_row_required")
    _require(numeric_row.get("boundary") == "Company-total only; no segment or product attribution.", "t09_numeric_boundary_mismatch")
    _require(len(numeric_row.get("support_refs", [])) == 5, "t09_numeric_support_refs_mismatch")

    judgment = payloads["bounded_agent_judgment"]
    specialists = judgment.get("specialist_outputs")
    _require(isinstance(specialists, list) and len(specialists) == 3, "t09_exact_three_specialists_required")
    terminal_classes = {row["program_cell_id"]: row["terminal_class"] for row in specialists}
    _require(
        terminal_classes
        == {
            EXPECTED_CELLS[0]: "typed_cannot_infer",
            EXPECTED_CELLS[1]: "value_capture_unattributed",
            EXPECTED_CELLS[2]: "typed_gap_source_followup_required",
        },
        "t09_specialist_terminal_classes_mismatch",
    )
    _require(specialists[0].get("fact_layer") == [], "t09_demand_fact_layer_must_be_empty")
    _require(specialists[2].get("fact_layer") == [], "t09_bottleneck_fact_layer_must_be_empty")
    _require(specialists[1].get("fact_layer") == numeric_rows, "t09_value_fact_layer_numeric_mismatch")

    report = payloads["bounded_agent_report"]
    _require(report.get("writer_source_calls") == 0, "t09_writer_source_call_forbidden")
    _require(report.get("writer_tool_calls") == 0, "t09_writer_tool_call_forbidden")
    verification = payloads["bounded_agent_verification"]
    verifier = _mapping(verification.get("verification"), "t09_verifier_payload_required")
    _require(verifier.get("decision") == "accept_for_internal_review", "t09_machine_internal_review_decision_required")
    findings = verifier.get("findings")
    _require(isinstance(findings, list) and len(findings) == 4, "t09_four_verifier_layers_required")
    _require(all(row.get("status") == "pass" for row in findings), "t09_machine_verifier_nonpass")
    _require(verification.get("machine_verifier_is_human_acceptance") is False, "t09_machine_must_not_sign_human_acceptance")

    comparison = payloads["agent_fallback_comparison"]
    _require(comparison.get("comparison_status") == "pending_distinct_terminal_deterministic_run", "t09_comparison_must_remain_pending")
    _require(comparison.get("deterministic_research_run_id") is None, "t09_unproven_baseline_run_forbidden")
    _require(comparison.get("owner_review_status") == "not_performed", "t09_owner_review_must_not_be_claimed")

    owner_findings = classify_owner_grade_findings(payloads)
    return {
        "status": "artifact_integrity_pass_owner_grade_repair_required",
        "terminal_states": [
            terminal["work_unit"]["state"],
            terminal["attempt"]["state"],
            terminal["research_run"]["state"],
        ],
        "artifact_count": len(artifacts),
        "artifact_object_digests": object_digests,
        "cross_artifact_manifest_equal": True,
        "node_receipt_count": len(receipts),
        "specialist_terminal_classes": terminal_classes,
        "evidence_fact_row_count": 0,
        "live_evidence_head_promoted": False,
        "numeric_fact_row_count": 1,
        "numeric_boundary": numeric_row["boundary"],
        "machine_verifier_decision": verifier["decision"],
        "machine_verifier_issue_count": sum(len(row.get("issues", [])) for row in findings),
        "owner_grade_findings": owner_findings,
        "owner_grade_disposition": "repair_before_final_acceptance",
    }


def search_minimum_gate_baselines(
    search_root: Path,
    *,
    case_id: str,
    input_head_digest: str,
    agent_research_run_id: str,
) -> dict[str, Any]:
    databases = sorted(search_root.rglob("canonical.sqlite"))
    matches: list[dict[str, Any]] = []
    minimum_gate_candidates: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for database_path in databases:
        try:
            connection = _open_read_only(database_path)
            tables = {
                str(row[0])
                for row in connection.execute(
                    "select name from sqlite_master where type = 'table'"
                )
            }
            if "canonical_research_run_versions" not in tables:
                connection.close()
                continue
            runs = _latest_rows(connection, "canonical_research_run_versions")
            connection.close()
            for run in runs:
                if (
                    run.get("case_id") != case_id
                    or run.get("input_refs_digest") != input_head_digest
                ):
                    continue
                item = {
                    "database": database_path.as_posix(),
                    "research_run_id": run.get("research_run_id"),
                    "attempt_id": run.get("attempt_id"),
                    "state": run.get("state"),
                    "execution_profile_version_ref": run.get("execution_profile_version_ref"),
                    "input_refs": run.get("input_refs"),
                }
                matches.append(item)
                if (
                    run.get("research_run_id") != agent_research_run_id
                    and run.get("state") == "succeeded"
                    and run.get("execution_profile_version_ref") == BASELINE_PROFILE
                ):
                    minimum_gate_candidates.append(item)
        except (OSError, sqlite3.Error, json.JSONDecodeError) as exc:
            errors.append(
                {
                    "database": database_path.as_posix(),
                    "error_type": type(exc).__name__,
                }
            )
    return {
        "searched_canonical_database_count": len(databases),
        "matching_case_and_input_head_runs": matches,
        "minimum_gate_terminal_deterministic_candidate_count": len(minimum_gate_candidates),
        "minimum_gate_terminal_deterministic_candidates": minimum_gate_candidates,
        "query_errors": errors,
        "decision": (
            "no_qualifying_baseline_exists_materialization_decision_required"
            if not minimum_gate_candidates
            else "candidate_exists_exact_artifact_validation_required"
        ),
    }


def run_read_only_validation(
    *,
    runtime_root: Path,
    search_root: Path,
    result_contract_path: Path,
) -> dict[str, Any]:
    result_contract = json.loads(result_contract_path.read_text(encoding="utf-8"))
    identity = _mapping(result_contract.get("identity"), "t09_result_identity_required")
    artifact_validation = _mapping(result_contract.get("artifact_validation"), "t09_result_artifacts_required")
    expected_refs = _mapping(artifact_validation.get("artifact_refs"), "t09_result_artifact_refs_required")
    database_path = runtime_root / "canonical-runtime" / "canonical.sqlite"
    object_root = runtime_root / "canonical-runtime" / "objects"
    databases = sorted(search_root.rglob("canonical.sqlite"))
    before_database_digests = {path.as_posix(): _sha256(path) for path in databases}
    before_target_object_digest = _tree_digest(object_root)

    artifacts, terminal = load_exact_artifacts(
        runtime_root,
        work_unit_id=str(identity["work_unit_id"]),
        attempt_id=str(identity["attempt_id"]),
        research_run_id=str(identity["research_run_id"]),
    )
    attempt = terminal["attempt"]
    artifact_result = validate_artifacts(
        artifacts,
        terminal,
        expected_input_digest=str(result_contract["preflight"]["input_digest"]),
        expected_input_head_digest=str(attempt["input_head_digest"]),
        expected_attempt_id=str(identity["attempt_id"]),
        expected_research_run_id=str(identity["research_run_id"]),
        expected_artifact_refs=expected_refs,
    )
    baseline_result = search_minimum_gate_baselines(
        search_root,
        case_id=str(identity["case_id"]),
        input_head_digest=str(attempt["input_head_digest"]),
        agent_research_run_id=str(identity["research_run_id"]),
    )

    after_database_digests = {path.as_posix(): _sha256(path) for path in databases}
    after_target_object_digest = _tree_digest(object_root)
    _require(before_database_digests == after_database_digests, "t09_read_only_changed_canonical_database")
    _require(before_target_object_digest == after_target_object_digest, "t09_read_only_changed_object_tree")
    return {
        "schema_version": "fin_ia_0_1_s3_t09_replacement_artifact_baseline_read_only_audit_v1_0",
        "status": "artifact_integrity_pass_owner_grade_repair_required_no_paired_baseline",
        "input_binding": {
            "case_id": identity["case_id"],
            "case_version": identity["case_version"],
            "analysis_as_of": identity["as_of"],
            "research_run_id": identity["research_run_id"],
            "attempt_id": identity["attempt_id"],
            "input_digest": result_contract["preflight"]["input_digest"],
            "input_head_digest": attempt["input_head_digest"],
        },
        "artifact_validation": artifact_result,
        "paired_baseline_search": baseline_result,
        "read_only_audit": {
            "canonical_database_sha256": before_database_digests[database_path.as_posix()],
            "target_object_tree_sha256": before_target_object_digest,
            "all_canonical_database_digests_unchanged": True,
            "target_object_tree_digest_unchanged": True,
            "new_model_calls": 0,
            "new_provider_calls": 0,
            "new_network_calls": 0,
            "new_source_or_tool_calls": 0,
            "canonical_writes": 0,
            "human_review_writes": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--search-root", type=Path, default=ROOT / ".codex_runtime")
    parser.add_argument(
        "--result-contract",
        type=Path,
        default=ROOT
        / "configs"
        / "releases"
        / "fin_ia_0_1_s3_t09_replacement_output_v2_live_execution_result_v1_0.json",
    )
    args = parser.parse_args()
    print(
        json.dumps(
            run_read_only_validation(
                runtime_root=args.runtime_root,
                search_root=args.search_root,
                result_contract_path=args.result_contract,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
