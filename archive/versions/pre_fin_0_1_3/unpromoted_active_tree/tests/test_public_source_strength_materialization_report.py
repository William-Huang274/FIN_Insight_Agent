from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_public_source_strength_materialization_report.py"
SPEC = importlib.util.spec_from_file_location("build_public_source_strength_materialization_report", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_jp_company_ir_fallback_does_not_materialize_edinet_official_source() -> None:
    strength_config = {
        "source_assessments": [
            {
                "source_id": "jp_edinet_api",
                "information_strength_tier": "S5_primary_authority",
                "integration_mode": "primary_evidence_authority",
                "readiness": "blocked_credential",
                "evidence_admissibility": "no_runtime_use_until_key_downloader_and_parser",
            },
            {
                "source_id": "company_ir_reports",
                "information_strength_tier": "S5_primary_authority",
                "integration_mode": "primary_evidence_authority",
                "readiness": "parser_required",
                "evidence_admissibility": "company_fact_evidence_after_official_url_checksum_and_parser_gate",
            },
        ]
    }
    rows = MODULE.build_materialization_rows(
        strength_config=strength_config,
        non_us_source_plan_rows=[
            {"disclosure_profile": "jp_edinet_annual_securities_report", "plan_id": "P1"},
            {"disclosure_profile": "jp_edinet_annual_securities_report", "plan_id": "P2"},
        ],
        download_rows=[
            {
                "plan_id": "P1",
                "ticker": "6857.T",
                "disclosure_profile": "jp_edinet_annual_securities_report",
                "source_policy": "profile_strategy_pending_company_ir_fallback",
                "document_downloaded": True,
                "downloaded_bytes": 100,
                "sha256": "abc",
                "cleaned_text_status": "cleaned_text_written",
                "cleaned_text_char_count": 50,
            }
        ],
        inventory_summary={},
        sec_structured_summary={},
        sec_annual_summary={},
        generated_at="2026-06-11T00:00:00+00:00",
    )
    by_source = {row["source_id"]: row for row in rows}

    assert by_source["jp_edinet_api"]["downloaded_document_row_count"] == 0
    assert by_source["jp_edinet_api"]["fallback_downloaded_for_this_source_count"] == 1
    assert by_source["jp_edinet_api"]["official_non_us_gap_row_count"] == 2
    assert by_source["jp_edinet_api"]["materialization_status"] == "official_source_not_materialized"
    assert by_source["company_ir_reports"]["downloaded_document_row_count"] == 1
    assert by_source["company_ir_reports"]["fallback_to_company_ir_row_count"] == 1


def test_materialization_summary_counts_sec_and_inventory_rows() -> None:
    strength_config = {
        "source_assessments": [
            {
                "source_id": "sec_edgar_apis",
                "information_strength_tier": "S5_primary_authority",
                "integration_mode": "primary_evidence_authority",
                "readiness": "accepted_core",
                "evidence_admissibility": "company_fact_evidence_after_existing_sec_parser_gate",
            },
            {
                "source_id": "openfigi_api",
                "information_strength_tier": "S1_resolver_or_lead",
                "integration_mode": "resolver_registry",
                "readiness": "feature_flag_candidate",
                "evidence_admissibility": "identifier_mapping_not_claim_evidence",
            },
        ]
    }
    rows = MODULE.build_materialization_rows(
        strength_config=strength_config,
        non_us_source_plan_rows=[],
        download_rows=[],
        inventory_summary={"runtime_counts_by_source": {"openfigi_api": 14}},
        sec_structured_summary={"status": "pass", "fact_rows": 1000, "companyfacts_payloads": 2, "submission_rows": 20},
        sec_annual_summary={"status": "staging_only_pass", "chunks": {"count": 30}, "ledger": {"facts": 40}},
        generated_at="2026-06-11T00:00:00+00:00",
    )
    by_source = {row["source_id"]: row for row in rows}

    assert by_source["sec_edgar_apis"]["materialization_status"] == "materialized_existing_core"
    assert by_source["sec_edgar_apis"]["sec_structured_fact_row_count"] == 1000
    assert by_source["openfigi_api"]["materialization_status"] == "materialized_inventory_or_resolver_only"
    assert by_source["openfigi_api"]["inventory_runtime_row_count"] == 14


def test_materialization_counts_normalized_and_extended_sources() -> None:
    strength_config = {
        "source_assessments": [
            {
                "source_id": "fred_api",
                "information_strength_tier": "S2_official_macro_industry_context",
                "integration_mode": "context_snapshot",
                "readiness": "normalized_context_materialized_preferred_path",
                "evidence_admissibility": "context_only_after_series_allowlist",
            },
            {
                "source_id": "sec_financial_statement_data_sets",
                "information_strength_tier": "S5_primary_authority",
                "integration_mode": "structured_fact_authority",
                "readiness": "bulk_download_materialized_parser_gate_pending",
                "evidence_admissibility": "structured_fact_after_bulk_parser_and_ledger_parity_gate",
            },
        ]
    }

    rows = MODULE.build_materialization_rows(
        strength_config=strength_config,
        non_us_source_plan_rows=[],
        download_rows=[],
        inventory_summary={},
        sec_structured_summary={},
        sec_annual_summary={},
        normalized_snapshot_summary={
            "status": "pass",
            "successful_sources": ["fred_api"],
            "source_record_counts": {"fred_api": 12},
        },
        extended_materialization_summary={
            "status": "pass",
            "source_stats": {
                "sec_financial_statement_data_sets": {
                    "record_count": 100,
                    "downloaded_bytes": 200,
                }
            },
        },
        industry_snapshot_metadata={},
        generated_at="2026-06-11T00:00:00+00:00",
    )
    by_source = {row["source_id"]: row for row in rows}

    assert by_source["fred_api"]["materialization_status"] == "materialized_normalized_snapshot_gate_pending"
    assert by_source["fred_api"]["normalized_snapshot_record_count"] == 12
    assert by_source["sec_financial_statement_data_sets"]["materialization_status"] == "materialized_structured_bulk_parser_gate_pending"
    assert by_source["sec_financial_statement_data_sets"]["extended_materialization_record_count"] == 100
