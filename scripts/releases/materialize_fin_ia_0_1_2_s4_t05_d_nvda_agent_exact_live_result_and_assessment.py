from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.application.bounded_agent_executor import BOUNDED_AGENT_ARTIFACT_TYPES  # noqa: E402
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


RUNTIME_ROOT = ROOT / ".codex_runtime/fin012-s4-t05d-nvda-post-transfer-agent-exact-live-r1"
EXACT_RESULT = RUNTIME_ROOT / "execution-result.json"
EVIDENCE_PACK = ROOT / "configs/releases/fin_ia_0_1_2_s4_t04_nvda_current_evidence_pack_v1_0.json"
AGENT_INPUT = ROOT / "configs/releases/fin_ia_0_1_2_s4_t05_d_nvda_post_transfer_agent_exact_input_v1_0.json"
EXPECTED_RESULT_SHA256 = "200907cf4c0f6a58748b12f44a4c874ff0b53bd74fe69e22e2d28d117f72bbc4"
EXPECTED_TERMINAL_DIGEST = "bc7a78a77eb7f99aaf805ce699b35fdee8ca76bd532f34d82dc4d3bb7300eb93"
OUTPUT = ROOT / "configs/releases/fin_ia_0_1_2_s4_t05_d_nvda_agent_exact_live_result_and_independent_assessment_v1_0.json"


class T05DNVDAExactAssessmentError(RuntimeError):
    pass


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise T05DNVDAExactAssessmentError(code)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "s4_t05_d_nvda_exact_json_object_required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize(*, recorded_at: str) -> dict[str, Any]:
    _require(_sha256(EXACT_RESULT) == EXPECTED_RESULT_SHA256, "s4_t05_d_nvda_exact_result_drift")
    result = _load(EXACT_RESULT)
    evidence = _load(EVIDENCE_PACK)
    agent_input = _load(AGENT_INPUT)
    terminal = result["terminal"]
    _require(
        result.get("status") == "success"
        and result.get("business_promotable") is True
        and terminal.get("status") == "success"
        and terminal.get("phase") == "complete"
        and terminal.get("code") == "s3_t03_success_nine_artifacts"
        and terminal.get("artifact_count") == 9
        and terminal.get("capture_count") == 9
        and result["terminal_object"]["digest"] == EXPECTED_TERMINAL_DIGEST,
        "s4_t05_d_nvda_exact_terminal_invalid",
    )
    captures = []
    for ref in result["capture_objects"]:
        path = RUNTIME_ROOT / "restricted-audit-objects" / ref["object_key"]
        _require(_sha256(path) == ref["digest"], "s4_t05_d_nvda_capture_digest_mismatch")
        capture = _load(path)
        _require(
            capture.get("finish_reason") == "stop"
            and capture.get("transport_attempt_count") == 1
            and capture.get("capture_before_local_parse_or_validation") is True
            and not any(capture.get(key) for key in (
                "authorization_headers_included", "cookies_included", "credentials_included",
                "private_reasoning_included", "raw_provider_response_included",
            )),
            "s4_t05_d_nvda_capture_completion_or_secret_boundary_invalid",
        )
        captures.append(capture)
    artifacts = {
        row["artifact_type"]: row["payload"]
        for row in result["artifacts"]
        if isinstance(row, Mapping)
    }
    _require(set(artifacts) == set(BOUNDED_AGENT_ARTIFACT_TYPES), "s4_t05_d_nvda_artifact_topology_invalid")
    manifest = artifacts["bounded_agent_manifest"]
    numeric = artifacts["bounded_agent_numeric"]
    judgment = artifacts["bounded_agent_judgment"]
    report = artifacts["bounded_agent_report"]
    verifier = artifacts["bounded_agent_verification"]
    topology = manifest["interaction_topology"]
    _require(
        manifest["case_ticker"] == verifier["entity_label"] == "NVDA"
        and manifest["lineage_family"] == "legacy_s3"
        and manifest["input_digest"] == agent_input["input_digest"]
        and agent_input["lineage"]["T04_financial_pack"]["digest"] == evidence["evidence_pack_digest"]
        and [topology["provider_interaction_count"], topology["local_fact_interaction_count"], topology["provider_capture_count"], topology["business_artifact_count"]]
        == [9, 3, 9, 9],
        "s4_t05_d_nvda_manifest_identity_lineage_or_topology_invalid",
    )
    projected = {
        (row["metric_family"], row["numeric_ref"]): str(row["exact_value"])
        for projection in numeric["case_numeric_authority_projections"]
        for row in projection["rows"]
        if row["authority_kind"] == "financial_row"
    }
    expected = {(row["metric_family"], row["numeric_ref"]): str(row["value"]) for row in evidence["numeric_rows"]}
    _require(projected == expected, "s4_t05_d_nvda_numeric_authority_drift")
    findings = verifier["verification"]["findings"]
    _require(len(findings) == 4 and all(row["status"] == "pass" for row in findings), "s4_t05_d_nvda_machine_verifier_invalid")
    specialists = judgment["specialist_outputs"]
    lead = judgment["cross_cell_lead"]
    report_text = json.dumps(report["report"], ensure_ascii=False)
    raw_delivery_findings = {
        "internal_scope_token": "__company_total__" in report_text,
        "internal_period_token": "FY2025-FY" in report_text,
        "duplicated_currency_unit": bool(re.search(r"USD\s+[0-9]+(?:\.[0-9]+)?\s+USD", report_text)),
        "mixed_language_limitation": any(
            str(row).startswith("Issuer disclosure")
            for row in report["report"]["limitations_zh_cn"]
        ),
    }
    body = {
        "schema_version": "fin_ia_0_1_2_s4_t05_d_nvda_agent_exact_live_result_and_independent_assessment_v1_0",
        "result_id": "FIN-0.1.2-S4-T05-D-NVDA-AGENT-EXACT-LIVE-R1",
        "recorded_at": recorded_at,
        "status": "exact_live_success_independent_L1_pass_product_surface_pending",
        "source_exact_result": {
            "ref": EXACT_RESULT.relative_to(ROOT).as_posix(),
            "sha256": EXPECTED_RESULT_SHA256,
            "terminal_digest": EXPECTED_TERMINAL_DIGEST,
            "immutable": True,
        },
        "execution": {
            "provider_model": "deepseek-v4-pro",
            "provider_calls": 9,
            "local_fact_receipts": 3,
            "captures": 9,
            "business_artifacts": 9,
            "input_tokens": terminal["observed_budget"]["input_tokens"],
            "output_tokens": terminal["observed_budget"]["output_tokens"],
            "estimated_cost_usd": terminal["observed_budget"]["estimated_cost_usd"],
            "retry_count": 0,
            "all_finish_reason_stop": True,
            "all_transport_attempt_count_one": True,
        },
        "independent_L1": {
            "status": "pass",
            "case_identity_NVDA": True,
            "input_and_current_evidence_lineage": True,
            "exact_numeric_correspondence": True,
            "capture_first_and_content_address_readback": True,
            "credential_cookie_private_reasoning_persisted": False,
            "machine_verifier_four_layers_self_pass": True,
            "machine_verifier_is_owner_acceptance": False,
        },
        "agent_output_counts": {
            "claims": sum(len(row["judgment_layer"]) for row in specialists),
            "what_would_change": sum(len(row["what_would_change"]) for row in specialists),
            "dependencies": len(lead["cross_cell_dependencies"]),
            "conflicts": len(lead["conflict_adjudications"]),
            "gaps": len(lead["remaining_gaps"]),
        },
        "product_surface_boundary": {
            "raw_delivery_findings": raw_delivery_findings,
            "generic_current_case_renderer_already_exists": True,
            "renderer_and_final_preview_binding_executed_this_step": False,
            "formal_paired_assessment_executed": False,
            "owner_acceptance": False,
            "post_transfer_NVDA_R2": False,
        },
        "next_action": "FIN-0.1.2-S4-T05-D-NVDA-VERIFIED-PRODUCT-SURFACE-AND-PAIRED-READINESS-ZERO-CALL",
    }
    return {**body, "assessment_digest": canonical_digest(body)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recorded-at", required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = materialize(recorded_at=args.recorded_at)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    path = args.output.resolve()
    if path.exists() and path.read_text(encoding="utf-8") != rendered:
        raise T05DNVDAExactAssessmentError("s4_t05_d_nvda_assessment_existing_output_mismatch")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "assessment_digest": result["assessment_digest"],
        "execution": result["execution"],
        "independent_L1": result["independent_L1"],
        "agent_output_counts": result["agent_output_counts"],
        "product_surface_boundary": result["product_surface_boundary"],
        "next_action": result["next_action"],
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
