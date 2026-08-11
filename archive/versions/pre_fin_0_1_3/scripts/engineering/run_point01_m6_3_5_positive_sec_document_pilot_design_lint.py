"""Fail-closed design lint for the next positive M6.3/M6.5 SEC document pilot.

This validates only an approval-pending design.  It cannot fetch a document,
register a receipt, or execute a parser.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DESIGN = ROOT / "configs/engineering_handoff/point01_m6_3_5_positive_sec_document_pilot_design_v1_0.json"
DEFAULT_OUTPUT = ROOT / "data/manifests/point01_m6_3_5_positive_sec_document_pilot_design_lint_result_v1_0.json"
PLAN_PATH = ROOT / "docs/architecture/repository/POINT_01_CONTROL_DECISION_SURFACE_RUNTIME_MIGRATION_FULL_PLAN_DRAFT_20260711.zh-CN.md"

REQUIRED_LOCATOR_FIELDS = {
    "cik",
    "accession_number",
    "primary_document_path",
    "form_type",
    "report_period",
    "target_table_selector",
}
REQUIRED_PROHIBITED = {
    "generic_external_execution",
    "additional_sec_metadata_request",
    "directory_listing",
    "web_search",
    "rag_sql_graph_recall",
    "sourcehunter_execution",
    "evidence_promotion",
    "writer_runtime",
    "domain_judgment",
    "m6_7_execution",
    "full_chain",
    "provider_or_paid_model",
    "business_case_mutation",
    "legacy_authority_change",
    "compound_writer",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("design_not_mapping")
    return value


def validate_design(design: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if design.get("design_version") != "finsight_point01_m6_3_5_positive_sec_document_pilot_design_v1_0":
        errors.append("design_version_invalid")
    if design.get("scope") != "Point01_M6_3_M6_5_single_document_positive_retrieval_parser_design_only":
        errors.append("scope_invalid")
    if design.get("status") != "immutable_runtime_contract_external_total_reviewer_decision_required":
        errors.append("status_must_describe_immutable_external_decision_boundary")

    authorization = design.get("authorization") or {}
    if authorization.get("design_authorization") != "immutable_runtime_contract_only":
        errors.append("immutable_runtime_contract_authorization_invalid")
    if authorization.get("external_execution") != "requires_active_exact_receipt_in_fixed_approval_store":
        errors.append("external_execution_exact_receipt_boundary_invalid")
    if authorization.get("receipt_registration") != "requires_external_exact_digest_total_reviewer_decision":
        errors.append("receipt_registration_external_decision_boundary_invalid")
    if authorization.get("required_human_approval_ref") != "approve_m6_3_5_single_sec_document_positive_retrieval_parser_pilot_only":
        errors.append("required_human_approval_invalid")
    if authorization.get("prior_m6_2_one_shot_receipt") != "consumed_and_not_reusable":
        errors.append("prior_receipt_reuse_not_denied")

    prerequisites = design.get("prerequisites") or {}
    if prerequisites.get("m6_2_metadata_receipt") != "tool_invocation_a80a2cc063561dcca1c1e3c6:v4_consumed_not_reusable":
        errors.append("consumed_metadata_receipt_not_bound")
    if prerequisites.get("target_document_locator") != "approved_nvda_10k_exact_locator_v1":
        errors.append("exact_locator_prerequisite_missing")
    target = design.get("target_document") or {}
    if (
        target.get("issuer") != "NVIDIA"
        or target.get("ticker") != "NVDA"
        or target.get("cik") != "0001045810"
        or target.get("accession_number") != "0001045810-25-000023"
        or target.get("form_type") != "10-K"
        or target.get("report_period") != "2025-01-26"
        or target.get("exact_path") != "/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm"
        or target.get("exact_url") != "https://www.sec.gov/Archives/edgar/data/1045810/000104581025000023/nvda-20250126.htm"
    ):
        errors.append("fixed_nvda_document_locator_invalid")
    selector = target.get("target_table_selector") or {}
    expected_selector = {
        "table_heading_normalized": "CONSOLIDATED STATEMENTS OF INCOME",
        "unit_caption_normalized": "In millions, except per share data",
        "row_label_normalized": "Revenue",
        "column_period_normalized": "Year Ended January 26, 2025",
        "xbrl_concept_hint": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "financial_statement_role": "consolidated_primary_financial_statement",
    }
    if selector != expected_selector:
        errors.append("fixed_nvda_target_table_selector_invalid")
    oracle = target.get("reviewer_blind_oracle") or {}
    if oracle != {"allowed_runtime_use": False, "allowed_post_execution_use": True, "value_oracle_injected_into_retrieval_parser": False}:
        errors.append("reviewer_blind_oracle_boundary_invalid")

    receipt = design.get("new_receipt_requirements") or {}
    required_receipt_values = {
        "approval_id": "new_unique_approval_id_required",
        "approval_nonce": "new_unique_one_shot_nonce_required",
        "expires_at_utc": "new_future_utc_expiry_required",
        "package_digest": "exact_positive_pilot_package_digest_required",
        "scope_digest": "exact_document_locator_and_policy_digest_required",
    }
    for key, expected in required_receipt_values.items():
        if receipt.get(key) != expected:
            errors.append(f"new_receipt_field_invalid:{key}")
    if receipt.get("atomic_consume_before_send") is not True or receipt.get("receipt_reuse") != "forbidden":
        errors.append("new_receipt_atomic_one_shot_missing")

    source = design.get("source_boundary") or {}
    if source.get("allowed_host") != "www.sec.gov" or source.get("allowed_path_prefix") != "/Archives/edgar/data/":
        errors.append("sec_archive_source_boundary_invalid")
    for key, expected in (("max_external_calls", 1), ("max_fallback_calls", 0), ("max_retry_calls", 0)):
        if source.get(key) != expected:
            errors.append(f"call_budget_invalid:{key}")
    if source.get("directory_listing") != "forbidden" or source.get("web_search") != "forbidden":
        errors.append("discovery_execution_not_denied")
    if set(source.get("document_locator_fields") or ()) != REQUIRED_LOCATOR_FIELDS:
        errors.append("exact_document_locator_fields_invalid")
    if source.get("document_content_digest") != "must_be_recorded_after_single_fetch_before_candidate_or_parser_write":
        errors.append("source_digest_boundary_invalid")
    if source.get("raw_document_git_persistence") != "forbidden" or source.get("raw_document_retention") != "isolated_temporary_store_only":
        errors.append("raw_document_storage_boundary_invalid")
    if source.get("reviewer_local_compatibility") != "read_only_hash_and_post_parse_output_only":
        errors.append("reviewer_local_compatibility_boundary_invalid")

    execution = design.get("execution_boundary") or {}
    if execution.get("case_scope") != "isolated_nonproduction_synthetic_case_only":
        errors.append("case_scope_invalid")
    if execution.get("capability_readmission_in_send_transaction") is not True:
        errors.append("send_transaction_readmission_missing")
    if execution.get("budget_reservation") != "one_call_exact_reservation_required":
        errors.append("budget_reservation_boundary_invalid")
    if execution.get("restart_reconciliation") != "no_resend_after_send_started":
        errors.append("restart_no_resend_boundary_invalid")

    isolation = design.get("incident_remediation_isolation") or {}
    required_isolation = {
        "incident_disposition": "v3_consumed_receipt_and_http_200_quarantined_not_retrospectively_authorized",
        "importable_package_builder": "no_fixed_authority_store_or_transport_access",
        "library_execution": "explicit_authority_service_and_client_injection_required",
        "default_transport": "fail_closed_no_network",
        "real_transport": "explicit_cli_live_entrypoint_only_after_exact_active_receipt_preflight",
        "contract_fixture_authority": "temporary_injected_store_only",
        "contract_fixture_transport": "injected_non_network_client_only",
        "production_store_during_contract_suite": "state_and_fingerprint_must_remain_unchanged",
    }
    for key, expected in required_isolation.items():
        if isolation.get(key) != expected:
            errors.append(f"incident_isolation_invalid:{key}")

    artifact = design.get("artifact_boundary") or {}
    required_artifact_values = {
        "candidate_bundle": "real_source_coordinate_candidate_allowed_but_unpromoted",
        "parser_candidate": "real_bounded_table_parse_allowed_but_unpromoted",
        "normalized_numeric_fact": "real_single_table_fact_allowed_but_unpromoted",
        "numeric_program_trace": "exact_source_coordinate_unit_scale_period_trace_required",
        "evidence_promotion": "forbidden",
        "formal_evidence_persistence": "forbidden",
        "writer_domain_judgment_full_chain": "forbidden",
        "table_selection": "table_local_exact_heading_and_unit_with_primary_statement_role_required",
        "period_semantics": "month_token_normalized_to_iso_date_with_year_ended_group",
        "currency_numeric_binding": "same_period_group_currency_marker_and_single_numeric_cell_required",
        "xbrl_concept_hint": "auxiliary_only_never_primary_selection_authority",
    }
    for key, expected in required_artifact_values.items():
        if artifact.get(key) != expected:
            errors.append(f"artifact_boundary_invalid:{key}")
    if artifact.get("writer_citable") is not False or artifact.get("domain_judgment_eligible") is not False:
        errors.append("downstream_consumer_boundary_invalid")

    repair = design.get("m6_4_repair_boundary") or {}
    if repair.get("successful_primary_candidate") != "no_repair_ticket_or_sourcehunter_execution":
        errors.append("successful_candidate_repair_boundary_invalid")
    if repair.get("retrieval_or_parse_failure") != "typed_terminal_stop_only" or repair.get("repair_attempt_budget") != 0:
        errors.append("repair_stop_boundary_invalid")
    if repair.get("sourcehunter") != "not_admitted":
        errors.append("sourcehunter_not_denied")

    acceptance = design.get("acceptance_contract") or {}
    required_positive = {
        "exact_locator_and_receipt_scope_match",
        "one_terminal_tool_receipt_with_redacted_user_agent_fingerprint",
        "one_candidate_with_exact_table_coordinate_and_source_digest",
        "one_parser_candidate_with_layout_and_table_lineage",
        "one_unpromoted_numeric_fact_with_unit_scale_iso_period",
        "one_numeric_program_trace_bound_to_all_parent_digests",
    }
    required_negative = {
        "wrong_cik_accession_or_path_fails_before_send",
        "locator_scope_or_package_digest_mismatch_fails_before_send",
        "second_send_or_retry_fails_closed",
        "missing_table_selector_or_source_coordinate_fails_closed",
        "unit_scale_period_mismatch_fails_closed",
        "promotion_or_writer_consumer_fails_closed",
        "send_started_crash_reconciles_without_resend",
        "wrong_table_with_same_revenue_is_rejected",
        "duplicate_primary_statement_is_ambiguous",
        "malformed_colspan_cannot_shift_period_group",
        "month_abbreviation_normalizes_without_literal_month_match",
        "currency_only_cell_cannot_be_promoted_as_numeric",
        "importable_package_builder_cannot_open_production_authority_or_real_transport",
        "missing_injected_authority_or_client_fails_before_receipt_or_runtime_access",
        "active_temporary_canary_receipt_uses_only_fake_transport_and_temporary_store",
        "production_authority_state_and_fingerprint_unchanged_across_contract_suite",
    }
    if required_positive - set(acceptance.get("positive_required") or ()) or required_negative - set(acceptance.get("negative_required") or ()):
        errors.append("acceptance_contract_incomplete")
    compatibility = design.get("parser_compatibility_gate") or {}
    if compatibility.get("sanitized_actual_shape_fixture") != "tests/fixtures/point01_m6_3_5_nvda_10k_actual_shape_sanitized.html":
        errors.append("actual_shape_fixture_binding_invalid")
    if compatibility.get("reviewer_local_source") != "read_only_not_runtime_input_or_git_artifact":
        errors.append("reviewer_local_source_boundary_invalid")
    if compatibility.get("package_disposition") != "immutable_parser_contract_v2":
        errors.append("immutable_parser_contract_disposition_invalid")
    missing = REQUIRED_PROHIBITED - set(design.get("prohibited") or ())
    errors.extend(f"prohibition_missing:{item}" for item in sorted(missing))
    return sorted(set(errors))


def build_result(design: Mapping[str, Any], *, design_path: Path = DEFAULT_DESIGN) -> dict[str, Any]:
    errors = validate_design(design)
    return {
        "result_version": "finsight_point01_m6_3_5_positive_sec_document_pilot_design_lint_result_v1_0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": design.get("scope"),
        "status": "pass" if not errors else "fail_closed",
        "errors": errors,
        "design_status": design.get("status"),
        "external_call_count": 0,
        "tool_invocation_count": 0,
        "parser_execution_count": 0,
        "numeric_fact_count": 0,
        "evidence_promotion_count": 0,
        "model_call_count": 0,
        "fixed_input_sha256": {
            str(design_path.relative_to(ROOT)).replace("\\", "/"): _sha256(design_path),
            "scripts/engineering/run_point01_m6_3_5_positive_sec_document_pilot_design_lint.py": _sha256(Path(__file__).resolve()),
            str(PLAN_PATH.relative_to(ROOT)).replace("\\", "/"): _sha256(PLAN_PATH),
        },
        "boundary": "This pass freezes an approval-pending design only. It does not register a receipt, perform a network request, read a document, create a candidate/parser/fact/trace, promote Evidence, execute M6.4 SourceHunter, enter M6.7, run a model, run Writer/full-chain, mutate a business Case, or change legacy authority.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint Point01 M6.3/M6.5 positive SEC document pilot design.")
    parser.add_argument("--design", type=Path, default=DEFAULT_DESIGN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    design_path = args.design if args.design.is_absolute() else ROOT / args.design
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        design = _read_json(design_path)
        result = build_result(design, design_path=design_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result = {"status": "fail_closed", "errors": [str(exc)], "external_call_count": 0, "tool_invocation_count": 0}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output_path), "errors": result.get("errors", [])}, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
