from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = REPO_ROOT / "scripts" / "data_expansion" / "build_public_source_inventory_adapter.py"
    spec = importlib.util.spec_from_file_location("public_source_inventory_adapter_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _policy() -> dict:
    module = _load_module()
    return module.load_policy(REPO_ROOT / "configs" / "data_sources" / "public_source_promotion_policy_v0_1.yaml")


def test_policy_validation_loads_source_rules() -> None:
    policy = _policy()

    assert policy["schema_version"] == "fin_agent_public_source_promotion_policy_v0_1"
    assert "sec_universe_identity" in policy["source_policies"]
    assert policy["source_policies"]["census_data_api"]["endpoint_record_rules"][0]["rule_id"] == "census_macro_context_record"


def test_high_confidence_identity_mapping_promotes_and_medium_candidate_rejects(tmp_path: Path) -> None:
    module = _load_module()
    policy = _policy()
    result = module.build_inventory_adapter(
        policy=policy,
        mapping_rows=[
            {
                "source_id": "sec_universe_identity",
                "mapping_type": "sec_cik",
                "status": "mapped",
                "confidence": "high",
                "ticker": "NVDA",
                "company_name": "NVIDIA Corp.",
                "external_id": "CIK0001045810",
            },
            {
                "source_id": "fdic_bankfind_api",
                "mapping_type": "fdic_cert",
                "status": "subsidiary_or_institution_candidate",
                "confidence": "medium",
                "ticker": "JPM",
                "company_name": "JPMorgan Chase & Co.",
                "external_id": "628",
            },
        ],
        endpoint_rows=[],
        source_gap_rows=[],
        source_gate_rows=[
            {"source_id": "sec_universe_identity", "status": "pass", "decision": "ready_for_primary_disclosure_inventory"},
            {"source_id": "fdic_bankfind_api", "status": "pass", "decision": "partial_requires_entity_mapping"},
        ],
        source_gate_summary={"status": "pass_with_gaps", "universe_company_count": 2},
        run_id="test_adapter",
        input_paths={},
        output_paths={"summary": tmp_path / "summary.json"},
        generated_at="2026-06-11T00:00:00+00:00",
    )

    assert len(result["inventory_rows"]) == 1
    assert result["inventory_rows"][0]["runtime_eligible"] is True
    assert result["inventory_rows"][0]["resolver_eligible"] is True
    assert result["inventory_rows"][0]["bounded_evidence_eligible"] is False
    assert result["inventory_rows"][0]["claim_scope"] == "issuer_identity_only"
    assert len(result["rejected_rows"]) == 1
    assert result["rejected_rows"][0]["rejection_reason"] == "fdic_candidate_requires_bank_subsidiary_or_issuer_resolver"


def test_census_endpoint_promotes_as_context_only_evidence() -> None:
    module = _load_module()
    policy = _policy()

    result = module.build_inventory_adapter(
        policy=policy,
        mapping_rows=[],
        endpoint_rows=[
            {
                "source_id": "census_data_api",
                "record_type": "macro_cross_section_observation",
                "external_id": "acs5:2023:B01001_001E:us",
                "external_name": "ACS5 population",
                "attributes": {"period": "2023", "value": "334914895"},
            }
        ],
        source_gap_rows=[],
        source_gate_rows=[
            {"source_id": "census_data_api", "status": "pass", "decision": "ready_for_context_inventory_after_boundary_gate"},
        ],
        source_gate_summary={"status": "pass_with_gaps", "universe_company_count": 603},
        run_id="test_adapter",
        input_paths={},
        output_paths={},
        generated_at="2026-06-11T00:00:00+00:00",
    )

    row = result["inventory_rows"][0]
    assert row["source_family"] == "macro_industry_indicator"
    assert row["runtime_source_family"] == "industry_snapshot"
    assert row["context_only"] is True
    assert row["bounded_evidence_eligible"] is True
    assert row["exact_value_authority"] is False
    assert result["summary"]["bounded_evidence_counts_by_source"] == {"census_data_api": 1}


def test_source_gap_rows_include_original_gap_and_policy_blocker() -> None:
    module = _load_module()
    policy = _policy()
    result = module.build_inventory_adapter(
        policy=policy,
        mapping_rows=[],
        endpoint_rows=[],
        source_gap_rows=[
            {
                "source_id": "openfigi_api",
                "gap_type": "no_figi_match",
                "ticker": "1211.HK",
                "company_name": "BYD Company Limited",
                "detail": "OpenFIGI returned no mapping rows.",
            }
        ],
        source_gate_rows=[
            {"source_id": "openfigi_api", "status": "partial", "decision": "ready_for_identifier_mapping_after_rate_gate"},
            {"source_id": "kr_dart_openapi", "status": "pass", "decision": "partial_requires_dart_document_parser"},
        ],
        source_gate_summary={"status": "pass_with_gaps"},
        run_id="test_adapter",
        input_paths={},
        output_paths={},
        generated_at="2026-06-11T00:00:00+00:00",
    )

    gap_types = {row["gap_type"] for row in result["gap_rows"]}
    assert "no_figi_match" in gap_types
    assert "dart_document_parser_required" in gap_types
    assert result["summary"]["primary_disclosure_evidence_promotion_allowed"] is False
