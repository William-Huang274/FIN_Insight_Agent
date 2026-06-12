from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

import download_public_source_normalized_snapshots as normalized
import probe_public_source_access as access_probe
from env_loader import load_env_file


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "fin_agent_public_source_full_availability_audit_v0.1"
SUMMARY_SCHEMA_VERSION = "fin_agent_public_source_full_availability_audit_summary_v0.1"

COMMON_REQUIRED_RECORD_FIELDS = {
    "schema_version",
    "source_id",
    "provider",
    "record_type",
    "source_family",
    "source_families",
    "claim_scope",
    "claim_boundary",
    "source_policy",
    "api_route",
}

SOURCE_REQUIRED_RECORD_FIELDS: dict[str, set[str]] = {
    "fred_api": {"series_id", "observation_date", "value", "unit"},
    "bls_public_api": {"series_id", "period", "observation_date", "value", "unit"},
    "bea_data_api": {"series_id", "metric_name", "period", "observation_date", "value", "unit"},
    "census_data_api": {"series_id", "metric_name", "entity_name", "period", "value", "unit"},
    "eia_open_data": {"series_id", "period", "observation_date", "value", "unit"},
    "fdic_bankfind_api": {"entity_name", "identifier", "identifier_type", "status"},
    "sec_edgar_apis": {"entity_name", "identifier", "identifier_type", "observation_date", "status"},
    "kr_dart_openapi": {"entity_name", "identifier", "identifier_type", "status"},
    "gleif_api": {"entity_name", "identifier", "identifier_type", "status"},
    "openfigi_api": {"entity_name", "identifier", "identifier_type", "status"},
    "clinicaltrials_api": {"entity_name", "identifier", "identifier_type", "observation_date", "product_name", "status"},
    "openfda_api": {"entity_name", "identifier", "identifier_type", "product_name", "status"},
    "nhtsa_vpic_api": {"entity_name", "identifier", "identifier_type", "product_name"},
}

SOURCE_CONTRACTS: dict[str, dict[str, Any]] = {
    "fred_api": {
        "availability_scope": "FRED series observations by allowlisted series_id.",
        "time_span_status": "validated_by_earliest_observation_probe",
        "pagination_status": "validated_by_offset_probe",
        "target_universe_mapping": "series_id_allowlist_required",
        "batch_or_backfill_mode": "series-by-series API backfill with limit/offset windows",
        "entity_mapping_status": "not_company_entity_source",
        "readiness_if_live_pass": "ready_for_context_inventory_after_boundary_gate",
        "required_before_agent_use": [
            "source inventory adapter behind feature flag",
            "series allowlist and claim-boundary gate",
        ],
    },
    "bls_public_api": {
        "availability_scope": "BLS time-series windows for selected series IDs.",
        "time_span_status": "validated_by_multi_year_window_probe",
        "pagination_status": "not_applicable_year_window_api",
        "target_universe_mapping": "series_id_allowlist_required",
        "batch_or_backfill_mode": "bounded series batches and year windows",
        "entity_mapping_status": "not_company_entity_source",
        "readiness_if_live_pass": "ready_for_context_inventory_after_boundary_gate",
        "required_before_agent_use": [
            "source inventory adapter behind feature flag",
            "series allowlist and claim-boundary gate",
        ],
    },
    "bea_data_api": {
        "availability_scope": "BEA dataset/table/year slices selected by datasetname/TableName/Frequency.",
        "time_span_status": "validated_by_prior_year_probe",
        "pagination_status": "not_applicable_table_slice_api",
        "target_universe_mapping": "dataset_table_allowlist_required",
        "batch_or_backfill_mode": "dataset/table/year parameter sweep",
        "entity_mapping_status": "not_company_entity_source",
        "readiness_if_live_pass": "ready_for_context_inventory_after_boundary_gate",
        "required_before_agent_use": [
            "source inventory adapter behind feature flag",
            "BEA dataset/table allowlist and unit metadata",
        ],
    },
    "census_data_api": {
        "availability_scope": "Census dataset-year endpoints selected per survey/table/geography.",
        "time_span_status": "validated_by_prior_dataset_year_probe",
        "pagination_status": "not_applicable_dataset_slice_api",
        "target_universe_mapping": "dataset_table_geography_allowlist_required",
        "batch_or_backfill_mode": "dataset-year and table/geography parameter sweep",
        "entity_mapping_status": "not_company_entity_source",
        "readiness_if_live_pass": "partial_requires_dataset_table_contract",
        "required_before_agent_use": [
            "dataset/table/geography allowlist",
            "source inventory adapter behind feature flag",
            "context-only claim-boundary gate",
        ],
    },
    "eia_open_data": {
        "availability_scope": "EIA v2 routes selected by route/frequency/data fields.",
        "time_span_status": "validated_by_ascending_history_probe",
        "pagination_status": "validated_by_offset_probe",
        "target_universe_mapping": "route_series_allowlist_required",
        "batch_or_backfill_mode": "offset/length route backfill",
        "entity_mapping_status": "entity_mapping_required_for_company_or_asset_context",
        "readiness_if_live_pass": "partial_requires_route_and_entity_mapping",
        "required_before_agent_use": [
            "route/series allowlist and unit metadata",
            "entity or asset mapping gate for company-adjacent claims",
            "source inventory adapter behind feature flag",
        ],
    },
    "fdic_bankfind_api": {
        "availability_scope": "FDIC BankFind institution reference slices.",
        "time_span_status": "current_reference_dataset_only",
        "pagination_status": "validated_by_offset_probe",
        "target_universe_mapping": "institution_to_issuer_mapping_required",
        "batch_or_backfill_mode": "limit/offset institution sweeps",
        "entity_mapping_status": "required_before_company_claims",
        "readiness_if_live_pass": "partial_requires_entity_mapping",
        "required_before_agent_use": [
            "FDIC institution to listed issuer resolver",
            "context-only source-boundary gate",
        ],
    },
    "sec_edgar_apis": {
        "availability_scope": "SEC submissions metadata for CIK-selected issuers.",
        "time_span_status": "validated_by_submissions_recent_and_archive_metadata",
        "pagination_status": "archive_files_metadata_available",
        "target_universe_mapping": "cik_ticker_registry_required",
        "batch_or_backfill_mode": "CIK submissions plus archive file fetches",
        "entity_mapping_status": "implemented_for_current_us_pipeline",
        "readiness_if_live_pass": "ready_for_primary_disclosure_inventory",
        "required_before_agent_use": [
            "keep current SEC citation and parser authority path",
            "do not replace filing parser with metadata-only rows",
        ],
    },
    "kr_dart_openapi": {
        "availability_scope": "DART company reference currently validated; filing-list/package path still pending.",
        "time_span_status": "not_validated_for_filings",
        "pagination_status": "not_validated_for_filings",
        "target_universe_mapping": "corp_code_mapping_required",
        "batch_or_backfill_mode": "requires DART list/document parser before evidence promotion",
        "entity_mapping_status": "corp_code_mapping_required",
        "readiness_if_live_pass": "partial_company_reference_only",
        "required_before_agent_use": [
            "DART list.json date-window audit",
            "document/package parser",
            "corp_code to issuer mapping gate",
        ],
    },
    "gleif_api": {
        "availability_scope": "GLEIF LEI records and legal entity relationship metadata.",
        "time_span_status": "current_reference_dataset_with_entity_events",
        "pagination_status": "validated_by_page_number_probe",
        "target_universe_mapping": "lei_to_issuer_mapping_required",
        "batch_or_backfill_mode": "page[number]/page[size] sweeps",
        "entity_mapping_status": "required_before_company_claims",
        "readiness_if_live_pass": "partial_requires_entity_mapping",
        "required_before_agent_use": [
            "LEI to issuer/ticker mapping",
            "relationship evidence must stay legal-entity-only",
        ],
    },
    "openfigi_api": {
        "availability_scope": "OpenFIGI security identifier mapping batches.",
        "time_span_status": "not_time_series",
        "pagination_status": "not_applicable_batch_mapping_api",
        "target_universe_mapping": "ticker_exchange_or_id_batch_required",
        "batch_or_backfill_mode": "bounded mapping batches",
        "entity_mapping_status": "security_identifier_mapping_only",
        "readiness_if_live_pass": "ready_for_identifier_mapping_after_rate_gate",
        "required_before_agent_use": [
            "batch-size and rate-limit guard",
            "identifier-only claim-boundary gate",
        ],
    },
    "clinicaltrials_api": {
        "availability_scope": "ClinicalTrials.gov study search over query terms and status fields.",
        "time_span_status": "validated_by_date_filtered_probe",
        "pagination_status": "validated_by_next_page_token_when_available",
        "target_universe_mapping": "sponsor_product_condition_query_mapping_required",
        "batch_or_backfill_mode": "query/date/status slices with page tokens",
        "entity_mapping_status": "sponsor_and_product_mapping_required",
        "readiness_if_live_pass": "partial_requires_healthcare_entity_mapping",
        "required_before_agent_use": [
            "sponsor/product/condition resolver",
            "trial facts remain non-sales and non-approval claims",
        ],
    },
    "openfda_api": {
        "availability_scope": "openFDA endpoint slices selected by endpoint/search/limit/skip.",
        "time_span_status": "endpoint_specific_date_filters_required",
        "pagination_status": "validated_by_skip_probe",
        "target_universe_mapping": "product_application_sponsor_mapping_required",
        "batch_or_backfill_mode": "endpoint-specific search and skip windows",
        "entity_mapping_status": "required_before_company_or_product_claims",
        "readiness_if_live_pass": "partial_requires_endpoint_and_product_mapping",
        "required_before_agent_use": [
            "endpoint allowlist",
            "product/application/sponsor resolver",
            "regulatory-status-only claim-boundary gate",
        ],
    },
    "nhtsa_vpic_api": {
        "availability_scope": "NHTSA vPIC vehicle make/model identity routes.",
        "time_span_status": "model_year_routes_require_separate_profile",
        "pagination_status": "not_applicable_make_route",
        "target_universe_mapping": "make_model_year_mapping_required",
        "batch_or_backfill_mode": "make/model/year route sweeps",
        "entity_mapping_status": "manufacturer_to_issuer_mapping_required",
        "readiness_if_live_pass": "partial_requires_auto_entity_mapping",
        "required_before_agent_use": [
            "manufacturer/make/model to issuer resolver",
            "vehicle identity only; no sales/profit claims",
        ],
    },
    "fred_graph_csv": {
        "availability_scope": "FRED graph CSV full series download by id.",
        "time_span_status": "covered_by_existing_industry_snapshot_path",
        "pagination_status": "not_applicable_csv_download",
        "target_universe_mapping": "series_id_allowlist_required",
        "batch_or_backfill_mode": "one CSV per series",
        "entity_mapping_status": "not_company_entity_source",
        "readiness_if_live_pass": "available_but_not_in_public_normalized_collector",
        "required_before_agent_use": [
            "reuse existing industry snapshot or add normalized CSV adapter",
            "series allowlist and context-only gate",
        ],
    },
    "openalex_api": {
        "availability_scope": "OpenAlex works search for research/technology signals.",
        "time_span_status": "query_filter_contract_required",
        "pagination_status": "cursor_or_page_contract_required",
        "target_universe_mapping": "institution_author_topic_company_mapping_required",
        "batch_or_backfill_mode": "query/cursor sweeps after endpoint contract",
        "entity_mapping_status": "required_before_company_or_product_claims",
        "readiness_if_live_pass": "available_but_not_normalized",
        "required_before_agent_use": [
            "topic/institution/company resolver",
            "technology signal only; no product-sales claims",
            "normalized collector/parser",
        ],
    },
}

LIVE_TEST_OVERRIDES: dict[str, list[dict[str, Any]]] = {
    "fred_api": [
        {"name": "latest_window", "params": {"limit": "12", "sort_order": "desc"}},
        {"name": "earliest_observation", "params": {"limit": "1", "sort_order": "asc"}},
        {"name": "offset_page", "params": {"limit": "1", "offset": "1", "sort_order": "desc"}},
    ],
    "bls_public_api": [
        {"name": "latest_window", "json_body": {"startyear": "2025", "endyear": "2026"}},
        {"name": "prior_year_window", "json_body": {"startyear": "2014", "endyear": "2015"}},
    ],
    "bea_data_api": [
        {"name": "latest_table_year", "params": {"Year": "2025"}},
        {"name": "prior_table_year", "params": {"Year": "2020"}},
    ],
    "census_data_api": [
        {"name": "latest_dataset_year"},
        {"name": "prior_dataset_year", "url": "https://api.census.gov/data/2022/acs/acs5"},
    ],
    "eia_open_data": [
        {"name": "latest_window", "params": {"offset": "0", "length": "12", "sort[0][direction]": "desc"}},
        {"name": "history_window", "params": {"offset": "0", "length": "1", "sort[0][direction]": "asc"}},
        {"name": "offset_page", "params": {"offset": "12", "length": "1", "sort[0][direction]": "desc"}},
    ],
    "fdic_bankfind_api": [
        {"name": "first_page", "params": {"limit": "5"}},
        {"name": "offset_page", "params": {"limit": "1", "offset": "5"}},
    ],
    "sec_edgar_apis": [{"name": "submissions_metadata"}],
    "kr_dart_openapi": [{"name": "company_reference"}],
    "gleif_api": [
        {"name": "first_page", "params": {"page[size]": "5"}},
        {"name": "second_page", "params": {"page[size]": "1", "page[number]": "2"}},
    ],
    "openfigi_api": [{"name": "single_batch_mapping"}],
    "clinicaltrials_api": [
        {"name": "first_page", "params": {"pageSize": "5"}},
        {"name": "date_filtered_page", "params": {"pageSize": "5", "query.term": "AREA[StartDate]RANGE[2020-01-01,MAX] cancer"}},
    ],
    "openfda_api": [
        {"name": "first_page", "params": {"limit": "5"}},
        {"name": "skip_page", "params": {"limit": "1", "skip": "5"}},
    ],
    "nhtsa_vpic_api": [{"name": "make_models"}],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit full availability/readiness for public source plans.")
    parser.add_argument("--access-plan", default="data/manifests/public_source_access_plan_v0_1.jsonl")
    parser.add_argument("--normalized-summary", default="data/manifests/public_source_normalized_snapshot_summary_v0_1.json")
    parser.add_argument("--output", default="data/manifests/public_source_full_availability_audit_v0_1.jsonl")
    parser.add_argument("--summary-output", default="data/manifests/public_source_full_availability_audit_summary_v0_1.json")
    parser.add_argument("--source-id-filter", default="", help="Comma-separated source_id filter.")
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--env-file", default=".env")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    loaded_env_keys = load_env_file(_resolve(args.env_file))
    access_plan_path = _resolve(args.access_plan)
    plan_rows = _read_jsonl(access_plan_path)
    normalized_summary_path = _resolve(args.normalized_summary)
    normalized_summary = _read_json_if_exists(normalized_summary_path)
    source_filter = set(_split_csv(args.source_id_filter))
    fetched_at = datetime.now(timezone.utc).isoformat()

    audit_rows = [
        audit_source(
            plan_row,
            normalized_summary=normalized_summary,
            fetched_at=fetched_at,
            timeout_s=args.timeout_s,
            skip_live=args.skip_live,
        )
        for plan_row in plan_rows
        if not source_filter or plan_row.get("source_id") in source_filter
    ]

    output_path = _resolve(args.output)
    summary_path = _resolve(args.summary_output)
    _write_jsonl(output_path, audit_rows)
    summary = build_summary(
        audit_rows=audit_rows,
        access_plan_path=access_plan_path,
        normalized_summary_path=normalized_summary_path,
        output_path=output_path,
        summary_path=summary_path,
        loaded_env_keys=loaded_env_keys,
        skip_live=args.skip_live,
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))

    hard_failures = [row for row in audit_rows if row.get("audit_status") == "live_error"]
    if hard_failures and not args.allow_partial:
        return 2
    return 0


def audit_source(
    plan_row: dict[str, Any],
    *,
    normalized_summary: dict[str, Any],
    fetched_at: str,
    timeout_s: float,
    skip_live: bool,
) -> dict[str, Any]:
    source_id = str(plan_row.get("source_id") or "")
    if source_id in normalized.COLLECTOR_PROFILES:
        return audit_normalized_profile(
            source_id,
            plan_row,
            normalized_summary=normalized_summary,
            fetched_at=fetched_at,
            timeout_s=timeout_s,
            skip_live=skip_live,
        )
    if source_id in access_probe.PROBE_PROFILES:
        return audit_probe_only_profile(source_id, plan_row, fetched_at=fetched_at, timeout_s=timeout_s, skip_live=skip_live)
    return build_plan_only_row(source_id, plan_row, fetched_at=fetched_at)


def audit_normalized_profile(
    source_id: str,
    plan_row: dict[str, Any],
    *,
    normalized_summary: dict[str, Any],
    fetched_at: str,
    timeout_s: float,
    skip_live: bool,
) -> dict[str, Any]:
    profile = normalized.COLLECTOR_PROFILES[source_id]
    contract = SOURCE_CONTRACTS.get(source_id, {})
    base = base_row(source_id, plan_row, fetched_at=fetched_at, contract=contract)
    normalized_counts = normalized_summary.get("source_record_counts") or {}
    if skip_live:
        return {
            **base,
            "audit_status": "skipped_live",
            "availability_decision": "not_confirmed_skip_live",
            "normalized_smoke_record_count": normalized_counts.get(source_id, 0),
            "live_tests": [],
        }
    try:
        live_tests = [
            run_collector_live_test(source_id, profile, plan_row, test, fetched_at=fetched_at, timeout_s=timeout_s)
            for test in live_tests_for(source_id)
        ]
    except Exception as exc:  # noqa: BLE001
        return {
            **base,
            "audit_status": "live_error",
            "availability_decision": "blocked_live_audit_error",
            "error": normalized._redact_text(str(exc)),
            "normalized_smoke_record_count": normalized_counts.get(source_id, 0),
            "live_tests": [],
            "agent_promotion_allowed": False,
        }

    failed_tests = [test for test in live_tests if test.get("status") != "pass"]
    base_test = live_tests[0] if live_tests else {}
    records = base_test.get("sample_normalized_records") or []
    field_audit = field_completeness(source_id, records)
    availability_decision = classify_live_decision(
        source_id=source_id,
        failed_tests=failed_tests,
        field_audit=field_audit,
        contract=contract,
    )
    return {
        **base,
        "audit_status": "live_pass" if not failed_tests else "live_partial",
        "availability_decision": availability_decision,
        "agent_promotion_allowed": False,
        "agent_promotion_blocker": "public sources are audited candidates only until source inventory adapter and source-boundary gate are wired",
        "normalized_smoke_record_count": normalized_counts.get(source_id, 0),
        "normalized_smoke_status": "pass" if normalized_counts.get(source_id, 0) else "not_in_normalized_smoke",
        "field_completeness": field_audit,
        "live_tests": strip_sample_records(live_tests),
        "capability_evidence": capability_evidence(live_tests),
    }


def audit_probe_only_profile(
    source_id: str,
    plan_row: dict[str, Any],
    *,
    fetched_at: str,
    timeout_s: float,
    skip_live: bool,
) -> dict[str, Any]:
    contract = SOURCE_CONTRACTS.get(source_id, {})
    base = base_row(source_id, plan_row, fetched_at=fetched_at, contract=contract)
    probe_row = access_probe.probe_source(plan_row, timeout_s=timeout_s, skip_live=skip_live)
    probe_status = probe_row.get("probe_status")
    live_pass = probe_status in {"pass", "skipped_live"}
    return {
        **base,
        "audit_status": "skipped_live" if skip_live else ("live_pass_probe_only" if live_pass else "live_error"),
        "availability_decision": "not_ready_probe_only_requires_normalized_collector" if live_pass else "blocked_probe_failed",
        "agent_promotion_allowed": False,
        "agent_promotion_blocker": "source has live probe coverage but no normalized collector/parser contract in this audit",
        "normalized_smoke_status": "not_in_normalized_smoke",
        "field_completeness": {
            "status": "not_checked_probe_only",
            "required_fields": [],
            "sample_record_count": 0,
            "missing_required_fields": [],
        },
        "live_tests": [
            {
                "name": "probe_only_smoke",
                "status": "pass" if live_pass else "fail",
                "probe_status": probe_status,
                "probe_url": probe_row.get("probe_url"),
                "http_status": probe_row.get("http_status"),
                "normalized_row_count": probe_row.get("normalized_row_count"),
                "latest_observation_date": probe_row.get("latest_observation_date"),
                "sample_fields": probe_row.get("sample_fields") or [],
                "error": normalized._redact_text(str(probe_row.get("error") or "")) or None,
            }
        ],
        "capability_evidence": {
            "time_span_status": contract.get("time_span_status", "not_confirmed"),
            "pagination_status": contract.get("pagination_status", "not_confirmed"),
            "batch_or_backfill_mode": contract.get("batch_or_backfill_mode", "not_confirmed"),
        },
    }


def build_plan_only_row(source_id: str, plan_row: dict[str, Any], *, fetched_at: str) -> dict[str, Any]:
    contract = SOURCE_CONTRACTS.get(source_id, {})
    base = base_row(source_id, plan_row, fetched_at=fetched_at, contract=contract)
    env_var = str(plan_row.get("env_var") or "")
    env_present = bool(env_var and os.environ.get(env_var, "").strip())
    if str(plan_row.get("auth_status") or "") == "commercial_deferred":
        decision = "commercial_deferred"
        status = "not_audited_deferred"
    elif env_var and not env_present:
        decision = "blocked_missing_credential"
        status = "not_audited_blocked"
    elif plan_row.get("live_probe_supported"):
        decision = "blocked_missing_audit_profile"
        status = "not_audited_no_profile"
    else:
        decision = "not_ready_source_plan_only"
        status = "not_audited_source_plan_only"
    return {
        **base,
        "audit_status": status,
        "availability_decision": decision,
        "agent_promotion_allowed": False,
        "agent_promotion_blocker": "no full availability audit ran for this source",
        "normalized_smoke_status": "not_in_normalized_smoke",
        "field_completeness": {
            "status": "not_checked_no_live_profile",
            "required_fields": [],
            "sample_record_count": 0,
            "missing_required_fields": [],
        },
        "live_tests": [],
        "capability_evidence": {
            "time_span_status": contract.get("time_span_status", "not_confirmed"),
            "pagination_status": contract.get("pagination_status", "not_confirmed"),
            "batch_or_backfill_mode": contract.get("batch_or_backfill_mode", "not_confirmed"),
        },
    }


def base_row(source_id: str, plan_row: dict[str, Any], *, fetched_at: str, contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "audited_at": fetched_at,
        "source_id": source_id,
        "provider": plan_row.get("provider"),
        "phase": plan_row.get("phase"),
        "auth_status": plan_row.get("auth_status"),
        "env_var": plan_row.get("env_var"),
        "env_present": bool(plan_row.get("env_var") and os.environ.get(str(plan_row.get("env_var")), "").strip()),
        "optional_key_env": plan_row.get("optional_key_env"),
        "optional_key_present": bool(plan_row.get("optional_key_env") and os.environ.get(str(plan_row.get("optional_key_env")), "").strip()),
        "source_families": plan_row.get("source_families") or [],
        "claim_scope": plan_row.get("claim_scope"),
        "claim_boundary": plan_row.get("boundary_notes"),
        "collector_status": plan_row.get("collector_status"),
        "parser_status": plan_row.get("parser_status"),
        "gap_type": plan_row.get("gap_type"),
        "priority": plan_row.get("priority"),
        "official_url": plan_row.get("official_url"),
        "current_repo_status": plan_row.get("current_repo_status"),
        "availability_scope": contract.get("availability_scope", "not_defined"),
        "target_universe_mapping": contract.get("target_universe_mapping", "not_confirmed"),
        "entity_mapping_status": contract.get("entity_mapping_status", "not_confirmed"),
        "required_before_agent_use": contract.get("required_before_agent_use", []),
    }


def run_collector_live_test(
    source_id: str,
    profile: dict[str, Any],
    plan_row: dict[str, Any],
    test: dict[str, Any],
    *,
    fetched_at: str,
    timeout_s: float,
) -> dict[str, Any]:
    test_profile = profile_for_test(profile, test)
    request_spec = normalized.prepare_request(test_profile)
    try:
        response = requests.request(
            request_spec["method"],
            request_spec["url"],
            params=request_spec["params"],
            headers=request_spec["headers"],
            json=request_spec["json_body"],
            timeout=timeout_s,
        )
        response.raise_for_status()
        payload = response.json()
        api_route = normalized._redact_url(response.url or request_spec["logged_url"])
        context = {
            "source_id": source_id,
            "profile": test_profile,
            "plan_row": plan_row,
            "snapshot_id": "availability_audit",
            "as_of_date": fetched_at[:10],
            "fetched_at": fetched_at,
            "api_route": api_route,
        }
        records = test_profile["parser"](payload, context)
        payload_stats = payload_statistics(source_id, payload)
        date_span = record_date_span(records)
        return {
            "name": test.get("name") or "base",
            "status": "pass",
            "http_status": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "api_route": api_route,
            "payload_stats": payload_stats,
            "normalized_record_count": len(records),
            "sample_fields": sorted(records[0].keys()) if records else [],
            "record_date_span": date_span,
            "rate_limit_headers_present": sorted(
                key
                for key in response.headers
                if "rate" in key.lower() or key.lower() in {"retry-after", "x-ratelimit-remaining", "x-ratelimit-limit"}
            ),
            "sample_normalized_records": records[:5],
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "name": test.get("name") or "base",
            "status": "fail",
            "api_route": request_spec["logged_url"],
            "error": normalized._redact_text(str(exc)),
        }


def profile_for_test(profile: dict[str, Any], test: dict[str, Any]) -> dict[str, Any]:
    out = dict(profile)
    out["params"] = dict(profile.get("params") or {})
    out["json_body"] = copy.deepcopy(profile.get("json_body"))
    if test.get("url"):
        out["url"] = test["url"]
    if test.get("params"):
        out["params"].update({str(key): value for key, value in test["params"].items()})
    if test.get("json_body"):
        if not isinstance(out.get("json_body"), dict):
            out["json_body"] = {}
        out["json_body"].update(test["json_body"])
    return out


def live_tests_for(source_id: str) -> list[dict[str, Any]]:
    tests = LIVE_TEST_OVERRIDES.get(source_id)
    if tests:
        return tests
    return [{"name": "base"}]


def classify_live_decision(
    *,
    source_id: str,
    failed_tests: list[dict[str, Any]],
    field_audit: dict[str, Any],
    contract: dict[str, Any],
) -> str:
    if failed_tests:
        return "partial_live_audit_failed_tests"
    readiness = str(contract.get("readiness_if_live_pass") or "ready_for_bounded_collector_after_boundary_gate")
    if field_audit.get("status") != "pass":
        if readiness.startswith("partial_"):
            return readiness
        return "partial_normalized_field_gap"
    return readiness


def field_completeness(source_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    required = sorted(COMMON_REQUIRED_RECORD_FIELDS | SOURCE_REQUIRED_RECORD_FIELDS.get(source_id, set()))
    if not records:
        return {
            "status": "fail",
            "required_fields": required,
            "sample_record_count": 0,
            "missing_required_fields": required,
        }
    present = set().union(*(set(record.keys()) for record in records))
    missing = [field for field in required if field not in present]
    empty_by_field: dict[str, int] = {}
    for field in required:
        empty_count = sum(1 for record in records if _is_empty_required_value(record.get(field)))
        if empty_count:
            empty_by_field[field] = empty_count
    status = "pass" if not missing and not empty_by_field else "partial"
    return {
        "status": status,
        "required_fields": required,
        "sample_record_count": len(records),
        "missing_required_fields": missing,
        "empty_required_field_counts": empty_by_field,
    }


def payload_statistics(source_id: str, payload: Any) -> dict[str, Any]:
    if source_id == "fred_api" and isinstance(payload, dict):
        observations = _list(payload.get("observations"))
        return {
            "raw_row_count": len(observations),
            "provider_total_count": _int_or_none(payload.get("count")),
            "provider_offset": _int_or_none(payload.get("offset")),
            "provider_limit": _int_or_none(payload.get("limit")),
            "date_span": _date_span([row.get("date") for row in observations if isinstance(row, dict)]),
        }
    if source_id == "bls_public_api" and isinstance(payload, dict):
        series = _list((payload.get("Results") or {}).get("series") if isinstance(payload.get("Results"), dict) else [])
        rows = []
        for item in series:
            if isinstance(item, dict):
                rows.extend(_list(item.get("data")))
        return {"raw_row_count": len(rows), "provider_status": payload.get("status"), "date_span": _date_span([_bls_date(row) for row in rows if isinstance(row, dict)])}
    if source_id == "bea_data_api" and isinstance(payload, dict):
        data = ((payload.get("BEAAPI") or {}).get("Results") or {}).get("Data") if isinstance(payload.get("BEAAPI"), dict) else []
        rows = _list(data)
        return {"raw_row_count": len(rows), "date_span": _date_span([_bea_date(row) for row in rows if isinstance(row, dict)])}
    if source_id == "census_data_api" and isinstance(payload, list):
        return {"raw_row_count": max(len(payload) - 1, 0), "sample_fields": payload[0] if payload else []}
    if source_id == "eia_open_data" and isinstance(payload, dict):
        response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
        rows = _list(response.get("data"))
        return {
            "raw_row_count": len(rows),
            "provider_total_count": _int_or_none(response.get("total")),
            "provider_offset": _int_or_none(response.get("offset")),
            "provider_length": _int_or_none(response.get("length")),
            "date_span": _date_span([row.get("period") for row in rows if isinstance(row, dict)]),
        }
    if source_id == "fdic_bankfind_api" and isinstance(payload, dict):
        rows = _list(payload.get("data"))
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        return {"raw_row_count": len(rows), "provider_total_count": _int_or_none(meta.get("total"))}
    if source_id == "sec_edgar_apis" and isinstance(payload, dict):
        recent = payload.get("filings", {}).get("recent", {}) if isinstance(payload.get("filings"), dict) else {}
        files = payload.get("filings", {}).get("files", []) if isinstance(payload.get("filings"), dict) else []
        accession_numbers = _list(recent.get("accessionNumber")) if isinstance(recent, dict) else []
        filing_dates = _list(recent.get("filingDate")) if isinstance(recent, dict) else []
        return {
            "raw_row_count": len(accession_numbers),
            "archive_file_count": len(_list(files)),
            "date_span": _date_span(filing_dates),
        }
    if source_id == "kr_dart_openapi" and isinstance(payload, dict):
        return {"raw_row_count": 1 if payload.get("corp_name") else 0, "provider_status": payload.get("status"), "provider_message": payload.get("message")}
    if source_id == "gleif_api" and isinstance(payload, dict):
        rows = _list(payload.get("data"))
        pagination = ((payload.get("meta") or {}).get("pagination") or {}) if isinstance(payload.get("meta"), dict) else {}
        return {
            "raw_row_count": len(rows),
            "provider_total_count": _int_or_none(pagination.get("total")),
            "provider_current_page": _int_or_none(pagination.get("currentPage")),
            "provider_per_page": _int_or_none(pagination.get("perPage")),
        }
    if source_id == "openfigi_api" and isinstance(payload, list):
        data_rows = []
        for item in payload:
            if isinstance(item, dict):
                data_rows.extend(_list(item.get("data")))
        return {"raw_row_count": len(data_rows), "request_result_count": len(payload)}
    if source_id == "clinicaltrials_api" and isinstance(payload, dict):
        rows = _list(payload.get("studies"))
        return {"raw_row_count": len(rows), "next_page_token_present": bool(payload.get("nextPageToken"))}
    if source_id == "openfda_api" and isinstance(payload, dict):
        rows = _list(payload.get("results"))
        meta_results = ((payload.get("meta") or {}).get("results") or {}) if isinstance(payload.get("meta"), dict) else {}
        return {
            "raw_row_count": len(rows),
            "provider_total_count": _int_or_none(meta_results.get("total")),
            "provider_skip": _int_or_none(meta_results.get("skip")),
            "provider_limit": _int_or_none(meta_results.get("limit")),
        }
    if source_id == "nhtsa_vpic_api" and isinstance(payload, dict):
        return {"raw_row_count": len(_list(payload.get("Results"))), "provider_count": _int_or_none(payload.get("Count"))}
    return {"raw_row_count": len(payload) if isinstance(payload, list) else None}


def capability_evidence(live_tests: list[dict[str, Any]]) -> dict[str, Any]:
    passed_names = {str(test.get("name")) for test in live_tests if test.get("status") == "pass"}
    return {
        "passed_test_names": sorted(passed_names),
        "has_history_or_prior_window_probe": bool(passed_names & {"earliest_observation", "prior_year_window", "prior_table_year", "prior_dataset_year", "history_window", "date_filtered_page"}),
        "has_pagination_or_second_page_probe": bool(passed_names & {"offset_page", "second_page", "skip_page"}),
        "provider_total_count_seen": any((test.get("payload_stats") or {}).get("provider_total_count") is not None for test in live_tests),
        "rate_limit_headers_seen": sorted({header for test in live_tests for header in test.get("rate_limit_headers_present") or []}),
    }


def record_date_span(records: list[dict[str, Any]]) -> dict[str, Any]:
    dates = [record.get("observation_date") or record.get("period") for record in records]
    return _date_span([str(date) for date in dates if date])


def strip_sample_records(live_tests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stripped = []
    for test in live_tests:
        clean = dict(test)
        clean.pop("sample_normalized_records", None)
        stripped.append(clean)
    return stripped


def build_summary(
    *,
    audit_rows: list[dict[str, Any]],
    access_plan_path: Path,
    normalized_summary_path: Path,
    output_path: Path,
    summary_path: Path,
    loaded_env_keys: set[str],
    skip_live: bool,
) -> dict[str, Any]:
    status_counts = Counter(str(row.get("audit_status") or "") for row in audit_rows)
    decision_counts = Counter(str(row.get("availability_decision") or "") for row in audit_rows)
    ready_decisions = {
        "ready_for_context_inventory_after_boundary_gate",
        "ready_for_primary_disclosure_inventory",
        "ready_for_identifier_mapping_after_rate_gate",
    }
    partial_rows = [
        row
        for row in audit_rows
        if str(row.get("availability_decision") or "").startswith("partial_")
        or str(row.get("availability_decision") or "").startswith("not_ready_")
        or str(row.get("availability_decision") or "").startswith("blocked_")
    ]
    ready_rows = [row for row in audit_rows if row.get("availability_decision") in ready_decisions]
    live_errors = [row for row in audit_rows if row.get("audit_status") == "live_error"]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": "skipped" if skip_live else ("fail" if live_errors else "pass_with_blockers"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "access_plan": _repo_path(access_plan_path),
            "normalized_summary": _repo_path(normalized_summary_path),
            "loaded_env_key_names": sorted(loaded_env_keys),
        },
        "outputs": {
            "audit_rows": _repo_path(output_path),
            "summary": _repo_path(summary_path),
        },
        "source_count": len(audit_rows),
        "live_audited_source_count": sum(1 for row in audit_rows if str(row.get("audit_status") or "").startswith("live_")),
        "normalized_profile_source_count": sum(1 for row in audit_rows if row.get("source_id") in normalized.COLLECTOR_PROFILES),
        "status_counts": dict(sorted(status_counts.items())),
        "availability_decision_counts": dict(sorted(decision_counts.items())),
        "ready_after_boundary_gate_sources": [row["source_id"] for row in ready_rows],
        "blocked_or_partial_sources": [
            {
                "source_id": row.get("source_id"),
                "decision": row.get("availability_decision"),
                "required_before_agent_use": row.get("required_before_agent_use") or [],
            }
            for row in partial_rows
        ],
        "live_error_sources": [
            {"source_id": row.get("source_id"), "error": row.get("error")}
            for row in live_errors
        ],
        "agent_promotion_allowed": False,
        "agent_promotion_blocker": "Full availability audit is complete enough to classify sources, but runtime use still requires source inventory wiring, feature flagging, and source-boundary gates.",
    }


def _bls_date(row: dict[str, Any]) -> str:
    year = str(row.get("year") or "")
    period = str(row.get("period") or "")
    month = period[1:] if period.startswith("M") and period[1:].isdigit() else "01"
    return f"{year}-{month.zfill(2)}-01" if year else ""


def _bea_date(row: dict[str, Any]) -> str:
    value = str(row.get("TimePeriod") or "")
    match = re.fullmatch(r"(\d{4})Q([1-4])", value)
    if not match:
        return value
    quarter_month = {"1": "01", "2": "04", "3": "07", "4": "10"}[match.group(2)]
    return f"{match.group(1)}-{quarter_month}-01"


def _date_span(values: list[str]) -> dict[str, Any]:
    clean = sorted({value for value in values if value})
    return {"min": clean[0], "max": clean[-1], "distinct_count": len(clean)} if clean else {"min": None, "max": None, "distinct_count": 0}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_empty_required_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}") from exc
    return rows


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _split_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _resolve(path: str | Path) -> Path:
    path = Path(path)
    return path if path.is_absolute() else REPO_ROOT / path


def _repo_path(path: Path) -> str:
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
