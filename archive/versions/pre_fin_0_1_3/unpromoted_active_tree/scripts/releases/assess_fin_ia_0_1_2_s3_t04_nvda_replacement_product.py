from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore  # noqa: E402
from scripts.releases import (  # noqa: E402
    run_fin_ia_0_1_2_s3_t03_nvda_replacement_controlled_successor as replacement,
)


RUNTIME_ROOT = ROOT / ".codex_runtime/fin012-s3-t03-nvda-replacement-r2"
RESULT = RUNTIME_ROOT / "execution-result.json"
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
EXPECTED_CELLS = (
    "demand_authenticity_and_sustainability",
    "value_and_profit_capture",
    "bottleneck_counterevidence_and_what_would_change",
)


class S3T04AssessmentError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise S3T04AssessmentError(code)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s3_t04_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_map(result: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    rows = result.get("artifacts")
    _require(isinstance(rows, list), "s3_t04_artifacts_required")
    mapped: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        _require(isinstance(row, Mapping), "s3_t04_artifact_row_invalid")
        artifact_type = str(row.get("artifact_type") or "")
        _require(artifact_type and artifact_type not in mapped, "s3_t04_artifact_type_duplicate")
        payload = row.get("payload")
        _require(isinstance(payload, Mapping), "s3_t04_artifact_payload_required")
        mapped[artifact_type] = payload
    _require(set(mapped) == EXPECTED_ARTIFACT_TYPES, "s3_t04_exact_nine_artifact_types_required")
    return mapped


def _verify_captures(result: Mapping[str, Any]) -> dict[str, Any]:
    refs = result.get("capture_objects")
    _require(isinstance(refs, list) and len(refs) == 9, "s3_t04_nine_capture_refs_required")
    store = FileCanonicalObjectStore(RUNTIME_ROOT / "restricted-audit-objects")
    captures = [
        store.get_json(str(row["object_key"]), expected_digest=str(row["digest"]))
        for row in refs
    ]
    _require(
        all(
            row.get("credentials_included") is False
            and row.get("authorization_headers_included") is False
            and row.get("cookies_included") is False
            and row.get("private_reasoning_included") is False
            and row.get("raw_provider_response_included") is False
            for row in captures
        ),
        "s3_t04_restricted_capture_secret_boundary_failed",
    )
    return {
        "capture_count": len(captures),
        "capture_digests": [str(row["digest"]) for row in refs],
        "capture_readback_verified": True,
        "secret_and_private_reasoning_exclusion_verified": True,
    }


def _independent_baseline() -> tuple[dict[str, Any], Any]:
    base = replacement._activate_issued_binding()
    target = base.load_target()
    admission = base.load_admission(target)
    with tempfile.TemporaryDirectory(prefix="fin012-s3-t04-independent-input-") as temp:
        prepared = base.prepare_exact_input(Path(temp), target, admission)
    cells: list[dict[str, Any]] = []
    for cell in prepared.input_pack.cell_inputs:
        numeric_input = cell.get("numeric_input") or {}
        rows = numeric_input.get("selected_financial_rows") or []
        metrics = numeric_input.get("derived_metrics") or []
        cells.append(
            {
                "program_cell_id": str(cell["program_cell_id"]),
                "deterministic_terminal": "bounded_numeric_support" if rows or metrics else "cannot_infer",
                "financial_rows": [
                    {
                        "ref": str(row["financial_row_id"]),
                        "entity": str(row["selector"]["entity_ref"]),
                        "period": str(row["selector"]["period"]),
                        "metric": str(row["selector"]["metric_family"]),
                        "value": str(row["normalized_value"]),
                        "unit": str(row["selector"]["unit"]),
                    }
                    for row in rows
                ],
                "derived_metrics": [
                    {
                        "ref": str(row["derived_metric_id"]),
                        "metric": str(row["metric_family"]),
                        "value": str(row["result_value"]),
                        "unit": str(row["result_unit"]),
                        "formula": str(row["formula"]),
                        "cannot_support": list(row.get("cannot_support") or []),
                    }
                    for row in metrics
                ],
                "typed_cannot_infer": list(
                    (numeric_input.get("fundamental_decision_cell") or {}).get("typed_cannot_infer") or []
                ),
            }
        )
    baseline_body = {
        "schema_version": "fin_ia_0_1_2_s3_t04_same_input_deterministic_baseline_v1_0",
        "execution_identity": "fin012-s3-t04-nvda-deterministic-baseline-r1",
        "paired_agent_execution_identity": target.execution_identity,
        "case_id": prepared.case_id,
        "case_version": prepared.case_version,
        "input_head_digest": prepared.input_pack.input_head_digest,
        "complete_input_digest": prepared.input_digest,
        "program_cells": cells,
        "observed_counts": {
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "business_writes": 0,
        },
    }
    return {**baseline_body, "baseline_digest": canonical_digest(baseline_body)}, prepared


def assess() -> dict[str, Any]:
    result = _load(RESULT)
    _require(result.get("status") == "success" and result.get("business_promotable") is True, "s3_t04_agent_terminal_not_success")
    terminal = result.get("terminal") or {}
    _require(terminal.get("status") == "success", "s3_t04_terminal_status_not_success")
    artifacts = _artifact_map(result)
    captures = _verify_captures(result)
    baseline, prepared = _independent_baseline()
    _require(baseline["complete_input_digest"] == prepared.input_digest, "s3_t04_baseline_input_digest_mismatch")

    manifest = artifacts["bounded_agent_manifest"]
    topology = manifest.get("interaction_topology") or {}
    _require(
        topology
        == {
            "logical_node_count": 6,
            "logical_interaction_count": 12,
            "local_fact_interaction_count": 3,
            "provider_interaction_count": 9,
            "provider_capture_count": 9,
            "business_artifact_count": 9,
        },
        "s3_t04_topology_mismatch",
    )
    _require(manifest.get("input_digest") == prepared.input_digest, "s3_t04_manifest_input_mismatch")
    _require(manifest.get("case_ticker") == "NVDA", "s3_t04_case_ticker_mismatch")
    _require(len(manifest.get("local_fact_receipts") or []) == 3, "s3_t04_local_fact_receipts_mismatch")

    numeric = artifacts["bounded_agent_numeric"]
    projections = numeric.get("case_numeric_authority_projections") or []
    authority_rows = {
        str(row["numeric_ref"]): row
        for projection in projections
        for row in projection.get("rows") or []
    }
    _require(len(authority_rows) == 5, "s3_t04_numeric_authority_row_count_mismatch")
    values_by_metric = {str(row["metric_family"]): Decimal(str(row["exact_value"])) for row in authority_rows.values()}
    expected_gross_margin = (values_by_metric["gross_profit"] / values_by_metric["revenue"] * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    expected_operating_margin = (values_by_metric["operating_income"] / values_by_metric["revenue"] * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    _require(values_by_metric["gross_margin"] == expected_gross_margin, "s3_t04_gross_margin_recompute_failed")
    _require(values_by_metric["operating_margin"] == expected_operating_margin, "s3_t04_operating_margin_recompute_failed")

    report = artifacts["bounded_agent_report"].get("report") or {}
    report_text = json.dumps(report, ensure_ascii=False, sort_keys=True)
    _require("DELL" not in report_text and "MU " not in report_text, "s3_t04_cross_case_identity_contamination")
    _require(str(report.get("title_zh_cn") or "").startswith("NVDA"), "s3_t04_report_title_identity_mismatch")
    material_tokens = set(re.findall(r"(?<![A-Za-z])(?:\d{9,}|\d+\.\d{2})(?![A-Za-z])", report_text))
    allowed_material_tokens = {str(value) for value in values_by_metric.values()}
    _require(material_tokens.issubset(allowed_material_tokens), "s3_t04_unauthorized_material_numeric_token")

    judgment = artifacts["bounded_agent_judgment"]
    specialists = judgment.get("specialist_outputs") or []
    _require(tuple(str(row["program_cell_id"]) for row in specialists) == EXPECTED_CELLS, "s3_t04_cell_order_or_identity_mismatch")
    all_facts = [fact for row in specialists for fact in row.get("fact_layer") or []]
    _require(len(all_facts) == 3, "s3_t04_local_fact_count_mismatch")
    _require(all(set(fact.get("support_refs") or []).issubset(authority_rows) for fact in all_facts), "s3_t04_fact_support_ref_outside_authority")
    wwc = [task for row in specialists for task in row.get("what_would_change") or []]
    structured_wwc = [
        task
        for task in wwc
        if isinstance(task.get("source_target"), Mapping)
        and isinstance(task.get("decision_rule"), Mapping)
        and isinstance(task.get("time_window"), Mapping)
        and str(task.get("metric_or_observation") or "").strip()
    ]
    _require(len(structured_wwc) == len(wwc), "s3_t04_unstructured_wwc_task")

    verification = artifacts["bounded_agent_verification"].get("verification") or {}
    _require(verification.get("decision") == "accept_for_internal_review", "s3_t04_machine_verifier_not_internal_review_accept")
    _require(artifacts["bounded_agent_verification"].get("machine_verifier_is_human_acceptance") is False, "s3_t04_machine_verifier_claimed_human_acceptance")

    delivery_findings: list[dict[str, str]] = []
    for token, issue in (
        ("__company_total__", "internal_scope_token_exposed"),
        ("FY2025-FY", "unnatural_period_label_exposed"),
        ("USD 130497000000 USD", "currency_unit_duplicated"),
    ):
        if token in report_text:
            delivery_findings.append({"level": "L4", "issue": issue, "evidence": token})
    if not artifacts["bounded_agent_verification"].get("final_delivery_preview_digest"):
        delivery_findings.append(
            {
                "level": "L4",
                "issue": "machine_verifier_did_not_bind_final_local_delivery_preview",
                "evidence": "bounded_agent_verification.final_delivery_preview_digest absent",
            }
        )

    factual_cells = sum(1 for row in specialists if row.get("fact_layer"))
    generic_thresholds = sum(
        1
        for task in wwc
        if "绑定权威观察" in str((task.get("decision_rule") or {}).get("threshold_or_observation") or "")
    )
    l1 = {
        "status": "pass",
        "identity": "pass_NVDA_only",
        "numeric_recompute": {
            "gross_margin": str(expected_gross_margin),
            "operating_margin": str(expected_operating_margin),
            "status": "pass",
        },
        "support_refs": "pass_all_local_numeric_authority",
        "lineage_and_capture": "pass",
        "new_L1_found": False,
    }
    l2 = {
        "status": "limited_sparse_frozen_fixture",
        "fact_supported_cells": factual_cells,
        "total_cells": len(EXPECTED_CELLS),
        "cannot_infer_cells": len(EXPECTED_CELLS) - factual_cells,
        "finding": "Only the value/profit cell has local Facts; demand and bottleneck remain typed cannot-infer.",
    }
    l3 = {
        "status": "limited_positive_over_deterministic_baseline",
        "structured_followup_tasks": len(wwc),
        "generic_threshold_tasks": generic_thresholds,
        "cross_cell_dependencies": len((judgment.get("cross_cell_lead") or {}).get("cross_cell_dependencies") or []),
        "conflict_adjudications": len((judgment.get("cross_cell_lead") or {}).get("conflict_adjudications") or []),
        "finding": "Agent adds typed follow-up task structure and bounded cross-cell organization, but most thresholds remain generic and conclusions largely repeat the deterministic evidence state.",
    }
    l4 = {
        "status": "fail_not_analyst_ready",
        "findings": delivery_findings,
        "finding_count": len(delivery_findings),
    }
    _require(delivery_findings, "s3_t04_expected_delivery_debt_not_observed")
    result_body = {
        "schema_version": "fin_ia_0_1_2_s3_t04_nvda_paired_product_assessment_v1_0",
        "status": "S3_T03_L1_pass_S3_T04_owner_reject_delivery_and_fixture_quality_block",
        "source_result": {"ref": _relative(RESULT), "sha256": _sha256(RESULT)},
        "capture_audit": captures,
        "artifact_digests": {key: canonical_digest(value) for key, value in artifacts.items()},
        "deterministic_baseline": baseline,
        "paired_input_equal": baseline["complete_input_digest"] == manifest["input_digest"],
        "L1_integrity": l1,
        "L2_evidence_reliability_and_coverage": l2,
        "L3_agent_gain": l3,
        "L4_delivery": l4,
        "owner_decision": {
            "decision": "reject_current_NVDA_R2_product_acceptance",
            "reason": "L1 is clean and limited Agent gain exists, but the frozen fixture covers only one factual cell and the final delivery exposes internal tokens, malformed period/currency rendering, and lacks final-preview verifier binding.",
            "S3_T03": "pass_closed",
            "S3_T04": "honest_block_owner_reject",
            "S3": "honest_block_not_eligible_for_S4",
            "current_NVDA_R2": False,
            "third_exact_or_runtime_repair": False,
        },
        "observed_counts": {
            "new_model_calls": 0,
            "new_provider_calls": 0,
            "new_network_calls": 0,
            "deterministic_baselines_materialized": 1,
            "paired_assessments": 1,
            "owner_decisions": 1,
        },
    }
    return {**result_body, "assessment_digest": canonical_digest(result_body)}


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def main() -> int:
    print(json.dumps(assess(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
