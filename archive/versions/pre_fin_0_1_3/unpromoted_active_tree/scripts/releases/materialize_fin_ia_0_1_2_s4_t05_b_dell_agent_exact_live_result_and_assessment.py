from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    BOUNDED_AGENT_ARTIFACT_TYPES,
)
from scripts.releases.run_fin_ia_0_1_2_s4_t05_b_dell_agent_exact_live import (  # noqa: E402
    AGENT_INPUT,
    DEFAULT_RUNTIME_ROOT,
    EVIDENCE_PACK,
    EXECUTION_IDENTITY,
)
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


EXACT_RESULT = DEFAULT_RUNTIME_ROOT / "execution-result.json"
EXPECTED_EXACT_RESULT_SHA256 = (
    "b4edc0927e958b812c5e5dd04d982defa97e64255d24e3a569e5311b78f5dd32"
)
EXPECTED_TERMINAL_DIGEST = (
    "b22f6faac7149ff7b9b437b8f1e1d2e82ce3c81b497e95f2fa97f2feba01b5a6"
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t05_b_dell_agent_exact_live_"
    "result_and_independent_assessment_v1_0.json"
)


class T05BDellExactAssessmentError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T05BDellExactAssessmentError(code)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t05_b_assessment_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_map(result: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    artifacts = result.get("artifacts") or ()
    mapped = {
        str(row["artifact_type"]): row["payload"]
        for row in artifacts
        if isinstance(row, Mapping) and isinstance(row.get("payload"), Mapping)
    }
    _require(
        set(mapped) == set(BOUNDED_AGENT_ARTIFACT_TYPES),
        "s4_t05_b_exact_artifact_topology_invalid",
    )
    return mapped


def _capture_assessment(result: Mapping[str, Any]) -> dict[str, Any]:
    captures = list(result.get("capture_objects") or ())
    _require(len(captures) == 9, "s4_t05_b_exact_capture_count_invalid")
    rows: list[dict[str, Any]] = []
    for ref in captures:
        path = DEFAULT_RUNTIME_ROOT / "restricted-audit-objects" / ref["object_key"]
        _require(_sha256(path) == ref["digest"], "s4_t05_b_capture_digest_mismatch")
        payload = _load(path)
        _require(
            payload.get("finish_reason") == "stop"
            and payload.get("transport_attempt_count") == 1
            and payload.get("capture_before_local_parse_or_validation") is True
            and bool(payload.get("model_visible_request"))
            and bool(payload.get("assistant_output_text")),
            "s4_t05_b_capture_completion_or_capture_first_invalid",
        )
        _require(
            not any(
                payload.get(key)
                for key in (
                    "authorization_headers_included",
                    "cookies_included",
                    "credentials_included",
                    "private_reasoning_included",
                    "raw_provider_response_included",
                )
            ),
            "s4_t05_b_capture_secret_or_private_surface_invalid",
        )
        usage = payload["usage"]
        rows.append(
            {
                "capture_sequence": payload["capture_sequence"],
                "stage": payload["stage"],
                "finish_reason": payload["finish_reason"],
                "transport_attempt_count": payload["transport_attempt_count"],
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "latency_ms": payload["latency_ms"],
                "capture_digest": ref["digest"],
            }
        )
    rows.sort(key=lambda row: row["capture_sequence"])
    _require(
        [row["capture_sequence"] for row in rows] == list(range(1, 10)),
        "s4_t05_b_capture_sequence_invalid",
    )
    return {
        "all_finish_reason_stop": True,
        "all_transport_attempt_count_one": True,
        "capture_first_and_readback_verified": True,
        "credential_cookie_private_reasoning_raw_envelope_persisted": False,
        "stages": [row["stage"] for row in rows],
        "input_tokens": sum(row["input_tokens"] for row in rows),
        "output_tokens": sum(row["output_tokens"] for row in rows),
        "provider_latency_ms": sum(row["latency_ms"] for row in rows),
        "capture_digests": [row["capture_digest"] for row in rows],
    }


def materialize() -> dict[str, Any]:
    _require(EXACT_RESULT.is_file(), "s4_t05_b_exact_result_missing")
    _require(
        _sha256(EXACT_RESULT) == EXPECTED_EXACT_RESULT_SHA256,
        "s4_t05_b_exact_result_drift",
    )
    result = _load(EXACT_RESULT)
    input_pack = _load(AGENT_INPUT)
    evidence_pack = _load(EVIDENCE_PACK)
    terminal = result["terminal"]
    _require(
        result.get("status") == "success"
        and result.get("business_promotable") is True
        and terminal.get("status") == "success"
        and terminal.get("phase") == "complete"
        and terminal.get("code") == "s3_t03_success_nine_artifacts"
        and terminal.get("artifact_count") == 9
        and terminal.get("capture_count") == 9
        and len(terminal.get("local_fact_receipts") or ()) == 3
        and result["terminal_object"]["digest"] == EXPECTED_TERMINAL_DIGEST,
        "s4_t05_b_exact_terminal_invalid",
    )
    capture = _capture_assessment(result)
    _require(
        capture["input_tokens"] == terminal["observed_budget"]["input_tokens"]
        and capture["output_tokens"]
        == terminal["observed_budget"]["output_tokens"],
        "s4_t05_b_usage_recomputation_mismatch",
    )
    artifacts = _artifact_map(result)
    manifest = artifacts["bounded_agent_manifest"]
    numeric = artifacts["bounded_agent_numeric"]
    judgment = artifacts["bounded_agent_judgment"]
    report = artifacts["bounded_agent_report"]
    verification = artifacts["bounded_agent_verification"]
    comparison = artifacts["agent_fallback_comparison"]
    topology = manifest["interaction_topology"]
    _require(
        manifest["case_ticker"] == "DELL"
        and manifest["input_digest"] == input_pack["input_digest"]
        and manifest["s4_case_runtime"]["source_grounded_input_digest"]
        == evidence_pack["evidence_pack_digest"]
        and [
            topology["provider_interaction_count"],
            topology["local_fact_interaction_count"],
            topology["provider_capture_count"],
            topology["business_artifact_count"],
        ]
        == [9, 3, 9, 9],
        "s4_t05_b_manifest_identity_or_topology_invalid",
    )
    numeric_rows = {
        (row["metric_family"], row["numeric_ref"]): row["exact_value"]
        for projection in numeric["case_numeric_authority_projections"]
        for row in projection["rows"]
        if row["authority_kind"] == "financial_row"
    }
    expected_numeric = {
        (row["metric_family"], row["numeric_ref"]): row["value"]
        for row in evidence_pack["numeric_rows"]
    }
    _require(numeric_rows == expected_numeric, "s4_t05_b_numeric_authority_drift")
    findings = verification["verification"]["findings"]
    _require(
        verification["entity_label"] == "DELL"
        and verification["input_digest"] == input_pack["input_digest"]
        and verification["machine_verifier_is_human_acceptance"] is False
        and len(findings) == 4
        and all(row["status"] == "pass" for row in findings),
        "s4_t05_b_verification_binding_invalid",
    )
    specialists = judgment["specialist_outputs"]
    what_would_change = [
        row for specialist in specialists for row in specialist["what_would_change"]
    ]
    generic_wwc = sum(
        "绑定权威观察" in row["decision_rule"]["threshold_or_observation"]
        for row in what_would_change
    )
    report_payload = report["report"]
    delivery_text = json.dumps(report_payload, ensure_ascii=False)
    delivery_findings = {
        "internal_scope_token": "__company_total__" in delivery_text,
        "internal_period_token": "FY2025-FY" in delivery_text,
        "duplicated_currency_unit": bool(
            re.search(r"USD\s+[0-9]+(?:\.[0-9]+)?\s+USD", delivery_text)
        ),
        "mixed_language_limitation": any(
            str(row).startswith("Issuer disclosure")
            for row in report_payload["limitations_zh_cn"]
        ),
        "final_delivery_preview_digest_missing": (
            "final_delivery_preview_digest" not in verification
        ),
    }
    _require(
        all(delivery_findings.values()),
        "s4_t05_b_expected_delivery_surface_finding_drift",
    )
    lead = judgment["cross_cell_lead"]
    assessment = {
        "L1_deterministic_integrity": "pass_independent_readback_recomputation",
        "L2_authority_coverage": "pass_three_cells_evidence_or_exact_numeric",
        "L3_agent_gain": "pass_with_known_generic_WWC_quality_finding",
        "L4_final_delivery": "fail_current_raw_delivery_surface",
        "claim_count": sum(len(row["judgment_layer"]) for row in specialists),
        "what_would_change_task_count": len(what_would_change),
        "generic_what_would_change_task_count": generic_wwc,
        "cross_cell_dependency_conflict_gap_counts": [
            len(lead["cross_cell_dependencies"]),
            len(lead["conflict_adjudications"]),
            len(lead["remaining_gaps"]),
        ],
        "machine_verifier_four_layers_self_pass": True,
        "machine_verifier_is_human_acceptance": False,
        "delivery_surface_findings": delivery_findings,
    }
    body = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t05_b_dell_agent_exact_live_result_and_"
            "independent_assessment_v1_0"
        ),
        "result_id": "FIN-0.1.2-S4-T05-B-DELL-AGENT-EXACT-LIVE-R1",
        "recorded_at": "2026-08-05T11:48:00+08:00",
        "status": "exact_live_success_independent_L1_pass_product_L4_blocked",
        "source_exact_result": {
            "ref": EXACT_RESULT.relative_to(ROOT).as_posix(),
            "sha256": EXPECTED_EXACT_RESULT_SHA256,
            "terminal_digest": EXPECTED_TERMINAL_DIGEST,
            "execution_identity": EXECUTION_IDENTITY,
            "immutable": True,
        },
        "execution": {
            "provider_model": "deepseek-v4-pro",
            "provider_calls": 9,
            "local_fact_receipts": 3,
            "captures": 9,
            "business_artifacts": 9,
            "input_tokens": capture["input_tokens"],
            "output_tokens": capture["output_tokens"],
            "estimated_cost_usd": terminal["observed_budget"][
                "estimated_cost_usd"
            ],
            "provider_latency_ms": capture["provider_latency_ms"],
            "retry_count": 0,
            "second_exact_live": 0,
            "all_finish_reason_stop": True,
        },
        "capture_audit": capture,
        "artifact_payload_digests": {
            key: canonical_digest(value) for key, value in artifacts.items()
        },
        "independent_assessment": assessment,
        "paired_and_owner_boundary": {
            "comparison_status": comparison["comparison_status"],
            "formal_distinct_deterministic_baseline_materialized": False,
            "formal_paired_assessment_performed": False,
            "owner_acceptance": False,
            "DELL_current_R2": False,
        },
        "root_cause_disposition": {
            "issue_id": (
                "RC-P36-120-fin-0-1-2-s4-t05-transfer-final-delivery-"
                "renderer-and-preview-binding-not-case-generic"
            ),
            "model_or_provider_fault_established": False,
            "runtime_L1_failure_established": False,
            "product_L4_failure_established": True,
            "automatic_model_rerun_required": False,
            "owned_zero_call_successor_required": True,
        },
        "next_action": (
            "FIN-0.1.2-S4-T05-B-DELL-FINAL-DELIVERY-GENERIC-CURRENT-CASE-"
            "RENDERER-PREVIEW-BINDING-AND-PAIRED-READINESS-ZERO-CALL-DISPOSITION"
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def _write_atomic(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encoded, encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = materialize()
    _write_atomic(args.output.resolve(), result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "result_digest": result["result_digest"],
                "execution": result["execution"],
                "independent_assessment": result["independent_assessment"],
                "next_action": result["next_action"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
