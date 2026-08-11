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

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE,
    BOUNDED_AGENT_EVIDENCE_ARTIFACT_TYPE,
    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE,
    BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
    BOUNDED_AGENT_TRACE_ARTIFACT_TYPE,
    BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE,
    BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE,
)
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore


EXPECTED_CALL_STAGES = {
    "bounded_specialist",
    "bounded_lead_adjudication",
    "bounded_writer_no_source",
    "bounded_semantic_financial_verifier",
}


class T04ValidationError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T04ValidationError(code)


def _mapping(value: Any, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _nonempty_strings(value: Any, code: str) -> list[str]:
    _require(isinstance(value, list) and bool(value), code)
    result = [str(item) for item in value]
    _require(all(item.strip() for item in result), code)
    return result


def validate_t04_artifacts(
    artifacts: Mapping[str, Mapping[str, Any]],
    *,
    expected_input_digest: str,
    expected_research_run_id: str,
    expected_attempt_id: str,
) -> dict[str, Any]:
    _require(
        set(artifacts) == set(BOUNDED_AGENT_ARTIFACT_TYPES),
        "t04_exact_artifact_type_set_required",
    )

    artifact_manifest: dict[str, str] = {}
    payloads: dict[str, Mapping[str, Any]] = {}
    for artifact_type, item in artifacts.items():
        metadata = _mapping(item.get("metadata"), "t04_artifact_metadata_required")
        payload = _mapping(item.get("payload"), "t04_artifact_payload_required")
        _require(metadata.get("artifact_type") == artifact_type, "t04_artifact_type_mismatch")
        _require(
            metadata.get("producer_attempt_id") == expected_attempt_id,
            "t04_artifact_attempt_binding_mismatch",
        )
        _require(
            payload.get("research_run_id") == expected_research_run_id,
            "t04_artifact_run_binding_mismatch",
        )
        version_id = str(metadata.get("artifact_version_id") or "")
        _require(version_id != "", "t04_artifact_version_id_required")
        _require(payload.get("artifact_version_id") == version_id, "t04_payload_version_mismatch")
        artifact_manifest[artifact_type] = version_id
        payloads[artifact_type] = payload

    for payload in payloads.values():
        _require(
            payload.get("artifact_manifest") == artifact_manifest,
            "t04_cross_artifact_manifest_mismatch",
        )

    manifest = payloads[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE]
    _require(manifest.get("input_digest") == expected_input_digest, "t04_manifest_input_mismatch")
    observed = _mapping(manifest.get("observed_counts"), "t04_observed_counts_required")
    _require(observed.get("model_calls") == 4, "t04_exact_four_model_calls_required")
    _require(observed.get("provider_calls") == 4, "t04_exact_four_provider_calls_required")
    _require(observed.get("network_calls") == 4, "t04_exact_four_network_calls_required")
    _require(observed.get("source_network_calls") == 0, "t04_source_network_forbidden")
    _require(observed.get("external_tool_calls") == 0, "t04_external_tools_forbidden")
    _require(observed.get("live_case_head_writes") == 0, "t04_live_case_write_forbidden")
    _require(
        observed.get("evaluation_evidence_promotions") == 1,
        "t04_one_run_scoped_evidence_promotion_required",
    )
    boundaries = _mapping(manifest.get("hard_boundaries"), "t04_hard_boundaries_required")
    for field in (
        "candidate_is_evidence",
        "graph_edge_is_evidence",
        "writer_source_or_tool_calls",
        "adapter_direct_canonical_writes",
        "live_business_case_head_writes",
        "release_admission",
    ):
        _require(boundaries.get(field) == 0, f"t04_hard_boundary_failed:{field}")

    evidence = payloads[BOUNDED_AGENT_EVIDENCE_ARTIFACT_TYPE]
    _require(evidence.get("input_digest") == expected_input_digest, "t04_evidence_input_mismatch")
    _require(
        evidence.get("status") == "run_scoped_evaluation_evidence_version",
        "t04_run_scoped_evaluation_promotion_required",
    )
    _require(
        evidence.get("live_evidence_head_promoted") is False,
        "t04_live_evidence_head_promotion_forbidden",
    )
    candidate_refs = set(_nonempty_strings(evidence.get("candidate_refs"), "t04_candidate_refs_required"))
    findings = evidence.get("findings")
    _require(isinstance(findings, list) and bool(findings), "t04_evidence_findings_required")
    finding_refs = {
        str(_mapping(row, "t04_evidence_finding_object_required").get("candidate_id") or "")
        for row in findings
    }
    _require("" not in finding_refs and finding_refs == candidate_refs, "t04_promoted_finding_refs_mismatch")
    for row in findings:
        finding = _mapping(row, "t04_evidence_finding_object_required")
        _require(bool(str(finding.get("supported_claim") or "").strip()), "t04_supported_claim_required")
        _require(bool(str(finding.get("boundary") or "").strip()), "t04_claim_boundary_required")

    numeric = payloads[BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE]
    _require(numeric.get("status") == "typed_gap", "t04_numeric_typed_gap_required")
    _require(numeric.get("metric") == "demand_sustainability", "t04_numeric_metric_mismatch")
    _require(numeric.get("value") is None, "t04_unsupported_numeric_precision_forbidden")
    _require(bool(str(numeric.get("reason") or "").strip()), "t04_numeric_gap_reason_required")

    judgment = payloads[BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE]
    specialist = _mapping(judgment.get("specialist_judgment"), "t04_specialist_judgment_required")
    lead = _mapping(judgment.get("lead_adjudication"), "t04_lead_adjudication_required")
    _require(bool(str(specialist.get("thesis") or "").strip()), "t04_thesis_required")
    _require(bool(str(specialist.get("counter_thesis") or "").strip()), "t04_counter_thesis_required")
    specialist_findings = specialist.get("evidence_findings")
    _require(specialist_findings == findings, "t04_judgment_evidence_mismatch")
    lead_refs = set(_nonempty_strings(lead.get("evidence_refs"), "t04_lead_evidence_refs_required"))
    _require(lead_refs.issubset(candidate_refs), "t04_lead_ref_outside_promoted_evidence")
    _require(lead.get("decision") in {"accept", "repair", "reject"}, "t04_lead_decision_invalid")
    remaining_gaps = _nonempty_strings(lead.get("remaining_gaps"), "t04_remaining_gaps_required")
    _nonempty_strings(lead.get("what_would_change"), "t04_what_would_change_required")

    workpaper = payloads[BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE]
    _require(workpaper.get("evidence_ref") == artifact_manifest[BOUNDED_AGENT_EVIDENCE_ARTIFACT_TYPE], "t04_workpaper_evidence_ref_mismatch")
    _require(workpaper.get("numeric_ref") == artifact_manifest[BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE], "t04_workpaper_numeric_ref_mismatch")
    _require(workpaper.get("judgment_ref") == artifact_manifest[BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE], "t04_workpaper_judgment_ref_mismatch")
    _require(workpaper.get("remaining_gaps") == remaining_gaps, "t04_workpaper_gap_mismatch")

    report_artifact = payloads[BOUNDED_AGENT_REPORT_ARTIFACT_TYPE]
    _require(report_artifact.get("mode") == "model_no_source_internal_writer", "t04_writer_mode_mismatch")
    _require(report_artifact.get("writer_source_calls") == 0, "t04_writer_source_call_forbidden")
    _require(report_artifact.get("writer_tool_calls") == 0, "t04_writer_tool_call_forbidden")
    report = _mapping(report_artifact.get("report"), "t04_report_required")
    _require(bool(str(report.get("title_zh_cn") or "").strip()), "t04_report_title_required")
    _require(bool(str(report.get("executive_summary_zh_cn") or "").strip()), "t04_report_summary_required")
    sections = report.get("sections")
    _require(isinstance(sections, list) and bool(sections), "t04_report_sections_required")
    report_refs: set[str] = set()
    for row in sections:
        section = _mapping(row, "t04_report_section_object_required")
        _require(bool(str(section.get("heading_zh_cn") or "").strip()), "t04_report_heading_required")
        _require(bool(str(section.get("content_zh_cn") or "").strip()), "t04_report_content_required")
        refs = set(_nonempty_strings(section.get("evidence_refs"), "t04_report_evidence_refs_required"))
        _require(refs.issubset(candidate_refs), "t04_report_ref_outside_promoted_evidence")
        report_refs.update(refs)
    _require(bool(report_refs), "t04_report_must_consume_evidence")
    limitations = _nonempty_strings(report.get("limitations_zh_cn"), "t04_report_limitations_required")

    verification = payloads[BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE]
    deterministic = _mapping(verification.get("deterministic_integrity"), "t04_deterministic_verifier_required")
    _require(deterministic.get("status") == "pass", "t04_deterministic_verifier_failed")
    _require(deterministic.get("exact_input_digest_bound") is True, "t04_verifier_input_binding_failed")
    _require(deterministic.get("evidence_refs_are_supplied_candidates") is True, "t04_verifier_evidence_binding_failed")
    for field in (
        "writer_source_calls",
        "writer_tool_calls",
        "specialist_output_tool_calls",
        "external_tool_executions",
    ):
        _require(deterministic.get(field) == 0, f"t04_deterministic_boundary_failed:{field}")
    _require(deterministic.get("private_reasoning_persisted") is False, "t04_private_reasoning_persistence_forbidden")

    semantic = _mapping(verification.get("semantic_fidelity"), "t04_semantic_verifier_required")
    financial = _mapping(verification.get("financial_coherence"), "t04_financial_verifier_required")
    for name, layer in (("semantic", semantic), ("financial", financial)):
        _require(layer.get("status") == "pass", f"t04_{name}_verifier_failed")
        score = layer.get("score")
        _require(isinstance(score, int) and score >= 80, f"t04_{name}_score_below_internal_review_floor")
        _require(layer.get("issues") == [], f"t04_{name}_issues_unresolved")

    visual = _mapping(verification.get("visual_delivery"), "t04_visual_verifier_required")
    _require(visual.get("status") == "pass", "t04_visual_verifier_failed")
    _require(visual.get("title_present") is True, "t04_visual_title_missing")
    _require(visual.get("section_count") == len(sections), "t04_visual_section_count_mismatch")
    _require(visual.get("limitations_present") is True and bool(limitations), "t04_visual_limitations_missing")
    _require(
        verification.get("recommendation") == "accept_for_internal_review",
        "t04_internal_review_recommendation_required",
    )

    trace = payloads[BOUNDED_AGENT_TRACE_ARTIFACT_TYPE]
    _require(trace.get("input_digest") == expected_input_digest, "t04_trace_input_mismatch")
    _require(trace.get("raw_provider_response_persisted") is False, "t04_raw_provider_response_forbidden")
    _require(trace.get("private_reasoning_persisted") is False, "t04_trace_private_reasoning_forbidden")
    _require(trace.get("specialist_external_tool_executed") is False, "t04_specialist_tool_execution_forbidden")
    receipts = trace.get("usage_receipts")
    _require(isinstance(receipts, list) and len(receipts) == 4, "t04_exact_four_usage_receipts_required")
    receipt_stages = {str(_mapping(row, "t04_usage_receipt_object_required").get("stage") or "") for row in receipts}
    _require(receipt_stages == EXPECTED_CALL_STAGES, "t04_usage_receipt_stage_set_mismatch")
    for row in receipts:
        receipt = _mapping(row, "t04_usage_receipt_object_required")
        _require(receipt.get("status") == "ok", "t04_usage_receipt_not_ok")
        _require(receipt.get("transport_attempt_count") == 1, "t04_single_transport_attempt_required")

    comparison = payloads[BOUNDED_AGENT_COMPARISON_ARTIFACT_TYPE]
    _require(comparison.get("owner_review_status") == "not_performed_in_t03", "t04_must_not_claim_t05_owner_review")
    _require(comparison.get("material_gain_accepted") is False, "t04_must_not_accept_material_gain_before_t05")

    return {
        "status": "pass",
        "research_run_id": expected_research_run_id,
        "attempt_id": expected_attempt_id,
        "input_digest": expected_input_digest,
        "artifact_count": len(artifacts),
        "artifact_manifest": artifact_manifest,
        "promotion": {
            "status": "pass_run_scoped_evaluation_evidence_version",
            "candidate_count": len(candidate_refs),
            "live_evidence_head_promoted": False,
        },
        "numeric": {"status": "pass_typed_gap", "metric": numeric["metric"], "value": None},
        "judgment": {
            "status": "pass",
            "lead_decision": lead["decision"],
            "remaining_gap_count": len(remaining_gaps),
            "counter_thesis_present": True,
        },
        "writer": {
            "status": "pass_no_source",
            "section_count": len(sections),
            "limitation_count": len(limitations),
            "evidence_ref_count": len(report_refs),
        },
        "four_layer_verifier": {
            "deterministic_integrity": "pass",
            "semantic_fidelity": "pass",
            "financial_coherence": "pass",
            "visual_delivery": "pass",
            "semantic_score": semantic["score"],
            "financial_score": financial["score"],
            "recommendation": verification["recommendation"],
        },
        "boundary": {
            "new_model_calls": 0,
            "new_provider_calls": 0,
            "new_network_calls": 0,
            "canonical_writes": 0,
            "T05_owner_review_performed": False,
        },
    }


def load_exact_run_artifacts(
    runtime_root: Path,
    *,
    expected_research_run_id: str,
    expected_attempt_id: str,
) -> dict[str, dict[str, Any]]:
    canonical_root = runtime_root / "canonical-runtime"
    database_path = canonical_root / "canonical.sqlite"
    object_root = canonical_root / "objects"
    _require(database_path.is_file(), "t04_canonical_database_required")
    _require(object_root.is_dir(), "t04_canonical_object_root_required")
    object_store = FileCanonicalObjectStore(object_root)

    def read_latest(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            f"select logical_id, payload_json from {table} order by row_id"
        ).fetchall()
        latest: dict[str, dict[str, Any]] = {}
        for logical_id, payload_json in rows:
            latest[str(logical_id)] = json.loads(str(payload_json))
        return list(latest.values())

    uri = database_path.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    try:
        connection.execute("pragma query_only = on")
        runs = [
            row
            for row in read_latest(connection, "canonical_research_run_versions")
            if row.get("research_run_id") == expected_research_run_id
        ]
        attempts = [
            row
            for row in read_latest(connection, "canonical_attempts")
            if row.get("attempt_id") == expected_attempt_id
        ]
        rows = [
            row
            for row in read_latest(connection, "canonical_artifact_versions")
            if row.get("producer_attempt_id") == expected_attempt_id
        ]
    finally:
        connection.close()
    _require(len(runs) == 1, "t04_exact_research_run_required")
    _require(runs[0].get("state") == "succeeded", "t04_research_run_must_be_succeeded")
    _require(len(attempts) == 1, "t04_exact_attempt_required")
    _require(attempts[0].get("state") == "succeeded", "t04_attempt_must_be_succeeded")
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        artifact_type = str(row.get("artifact_type") or "")
        _require(artifact_type not in result, "t04_duplicate_artifact_type")
        payload = object_store.get_json(
            str(row["object_key"]), expected_digest=str(row["object_digest"])
        )
        result[artifact_type] = {
            "metadata": row,
            "payload": payload,
        }
    return result


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _object_tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(_file_digest(path).encode("ascii"))
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--research-run-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--input-digest", required=True)
    args = parser.parse_args()
    database_path = args.runtime_root / "canonical-runtime" / "canonical.sqlite"
    object_root = args.runtime_root / "canonical-runtime" / "objects"
    _require(database_path.is_file(), "t04_canonical_database_required")
    _require(object_root.is_dir(), "t04_canonical_object_root_required")
    before_database_digest = _file_digest(database_path)
    before_object_digest = _object_tree_digest(object_root)
    artifacts = load_exact_run_artifacts(
        args.runtime_root,
        expected_research_run_id=args.research_run_id,
        expected_attempt_id=args.attempt_id,
    )
    after_database_digest = _file_digest(database_path)
    after_object_digest = _object_tree_digest(object_root)
    _require(
        before_database_digest == after_database_digest,
        "t04_read_only_validation_changed_canonical_database",
    )
    _require(
        before_object_digest == after_object_digest,
        "t04_read_only_validation_changed_canonical_objects",
    )
    result = validate_t04_artifacts(
        artifacts,
        expected_input_digest=args.input_digest,
        expected_research_run_id=args.research_run_id,
        expected_attempt_id=args.attempt_id,
    )
    result["read_only_audit"] = {
        "canonical_database_digest_unchanged": True,
        "canonical_object_tree_digest_unchanged": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
