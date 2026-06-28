from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "build_public_official_api_context_rows.py"
SPEC = importlib.util.spec_from_file_location("build_public_official_api_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_public_official_api_context_rows_bind_nhtsa_make_to_issuer_and_product() -> None:
    rows = MODULE.build_public_official_api_context_rows(
        [
            {
                "record_id": "PUBLICSOURCE::nhtsa_vpic_api::vehicle_model_identity_record::Tesla:Model S",
                "source_id": "nhtsa_vpic_api",
                "record_type": "vehicle_model_identity_record",
                "provider": "NHTSA",
                "entity_name": "Tesla",
                "product_name": "Model S",
                "identifier": "Tesla:Model S",
                "api_route": "https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/Tesla?format=json",
                "claim_boundary": "Vehicle model identity only.",
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        issuer_index={"tesla": {"ticker": "TSLA", "company_name": "Tesla, Inc."}},
    )
    assert len(rows) == 1
    assert rows[0]["ticker"] == "TSLA"
    assert rows[0]["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert rows[0]["product_binding_status"] == "product_mentioned_in_snapshot"
    assert rows[0]["exact_value_authority"] is False

    coverage = MODULE.build_source_coverage_gate(
        industry_schema="auto_mobility",
        phase="runtime_case",
        source_layer_capability={
            "rows": [
                _source("nhtsa_vpic_api", "L2", "structured_not_promoted"),
            ]
        },
        observed_rows=rows,
        specialist_visible_rows={"product_technology_analyst": rows, "risk_counterevidence_analyst": rows},
        required_dimensions=["auto_product_identity_context"],
        generated_at="2026-06-16T00:00:00Z",
    )
    req = coverage["requirements"][0]
    assert req["requirement_id"] == "auto_product_identity_context"
    assert req["status"] == "pass"


def test_public_official_api_context_rows_keep_openfda_unresolved_as_entity_gap() -> None:
    rows = MODULE.build_public_official_api_context_rows(
        [
            {
                "record_id": "PUBLICSOURCE::openfda_api::fda_product_status_record::ANDA076444",
                "source_id": "openfda_api",
                "record_type": "fda_product_status_record",
                "provider": "openFDA",
                "entity_name": "BARR",
                "product_name": "HYDROMORPHONE HYDROCHLORIDE",
                "identifier": "ANDA076444",
                "api_route": "https://api.fda.gov/drug/drugsfda.json?limit=1",
                "claim_boundary": "Regulatory status context only.",
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        issuer_index={},
    )
    assert rows[0]["issuer_binding_status"] == "regulatory_entity_unresolved"
    assert rows[0]["product_binding_status"] == "product_mentioned_in_snapshot"

    coverage = MODULE.build_source_coverage_gate(
        industry_schema="healthcare_pharma_medtech",
        phase="runtime_case",
        source_layer_capability={"rows": [_source("openfda_api", "L2", "structured_not_promoted")]},
        observed_rows=rows,
        specialist_visible_rows={"product_technology_analyst": rows, "risk_counterevidence_analyst": rows},
        required_dimensions=["regulated_product_context"],
        generated_at="2026-06-16T00:00:00Z",
    )
    req = coverage["requirements"][0]
    assert req["status"] == "gap"
    assert any(gap["gap_type"] == "runtime_case_entity_binding_missing" for gap in req["gaps"])


def test_public_official_api_context_rows_does_not_fuzzy_match_single_letter_ticker() -> None:
    rows = MODULE.build_public_official_api_context_rows(
        [
            {
                "record_id": "PUBLICSOURCE::fdic_bankfind_api::institution_reference_record::10004",
                "source_id": "fdic_bankfind_api",
                "record_type": "institution_reference_record",
                "provider": "FDIC",
                "entity_name": "Ergo Bank",
                "identifier": "10004",
                "api_route": "https://api.fdic.gov/banks/institutions",
                "claim_boundary": "Institution reference context only.",
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        issuer_index={"a": {"ticker": "A", "company_name": "Agilent Technologies"}},
    )
    assert rows[0]["ticker"] == ""
    assert rows[0]["issuer_binding_status"] == "regulatory_entity_unresolved"
    assert rows[0]["product_binding_status"] == "not_bound"
    assert rows[0]["resolver_status"] == "unresolved"


def test_public_official_api_context_rows_bind_fdic_holding_company_to_listed_issuer() -> None:
    rows = MODULE.build_public_official_api_context_rows(
        [
            {
                "record_id": "PUBLICSOURCE::fdic_bankfind_api::institution_reference_record::628",
                "source_id": "fdic_bankfind_api",
                "record_type": "institution_reference_record",
                "provider": "FDIC",
                "entity_name": "JPMorgan Chase Bank, National Association",
                "identifier": "628",
                "identifier_type": "FDIC_CERT",
                "attributes_json": '{"holding_company_name": "JPMorgan Chase & Co.", "name": "JPMorgan Chase Bank, National Association"}',
                "api_route": "https://api.fdic.gov/banks/institutions",
                "claim_boundary": "Institution reference context only.",
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        issuer_index={"jpmorgan chase": {"ticker": "JPM", "company_name": "JPMorgan Chase"}},
    )
    assert rows[0]["ticker"] == "JPM"
    assert rows[0]["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert rows[0]["product_binding_status"] == "not_bound"
    assert rows[0]["resolver_status"] == "issuer_bound"

    coverage = MODULE.build_source_coverage_gate(
        industry_schema="financials_banks",
        phase="runtime_case",
        source_layer_capability={"rows": [_source("fdic_bankfind_api", "L2", "structured_not_promoted")]},
        observed_rows=rows,
        specialist_visible_rows={
            "fundamental_analyst": rows,
            "capital_ownership_macro_analyst": rows,
            "industry_supply_chain_analyst": rows,
        },
        required_dimensions=["financial_regulatory_context"],
        generated_at="2026-06-16T00:00:00Z",
    )
    assert coverage["status"] == "pass"


def test_public_official_api_context_rows_eia_generic_driver_stays_unresolved() -> None:
    rows = MODULE.build_public_official_api_context_rows(
        [
            {
                "record_id": "PUBLICSOURCE::eia_open_data::macro_time_series_observation::ZWCDPC1:2026-05:value",
                "source_id": "eia_open_data",
                "record_type": "macro_time_series_observation",
                "provider": "EIA",
                "series_id": "ZWCDPC1",
                "metric_name": "value",
                "value": 5.0,
                "unit": "Number",
                "period": "2026-05",
                "attributes_json": '{"series_description": "Cooling Degree-Days, New England in Number"}',
                "api_route": "https://api.eia.gov/v2/total-energy/data/",
                "claim_boundary": "Energy and utility context only.",
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        issuer_index={},
    )
    assert rows[0]["issuer_binding_status"] == "regulatory_entity_unresolved"
    assert rows[0]["product_binding_status"] == "product_mentioned_in_snapshot"
    assert rows[0]["resolver_status"] == "driver_only"

    coverage = MODULE.build_source_coverage_gate(
        industry_schema="energy_utilities",
        phase="runtime_case",
        source_layer_capability={"rows": [_source("eia_open_data", "L2", "structured_not_promoted")]},
        observed_rows=rows,
        specialist_visible_rows={
            "industry_supply_chain_analyst": rows,
            "capital_ownership_macro_analyst": rows,
            "product_technology_analyst": rows,
        },
        required_dimensions=["energy_utility_context"],
        generated_at="2026-06-16T00:00:00Z",
    )
    req = coverage["requirements"][0]
    assert req["status"] == "gap"
    assert any(gap["gap_type"] == "runtime_case_entity_binding_missing" for gap in req["gaps"])


def test_public_official_api_context_rows_bind_eia_utility_to_issuer_and_driver() -> None:
    rows = MODULE.build_public_official_api_context_rows(
        [
            {
                "record_id": "PUBLICSOURCE::eia_open_data::utility_generation::XEL:2026-05",
                "source_id": "eia_open_data",
                "record_type": "utility_generation_observation",
                "provider": "EIA",
                "entity_name": "",
                "series_id": "EIA_XCEL_NET_GENERATION",
                "metric_name": "net_generation",
                "value": 123.0,
                "unit": "MWh",
                "period": "2026-05",
                "attributes_json": '{"utility_name": "Xcel Energy", "series_description": "Net generation, electric utility, monthly"}',
                "api_route": "https://api.eia.gov/v2/electricity/",
                "claim_boundary": "Energy/utility official operating context only.",
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        issuer_index={"xcel energy": {"ticker": "XEL", "company_name": "Xcel Energy"}},
    )
    assert rows[0]["ticker"] == "XEL"
    assert rows[0]["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert rows[0]["product_binding_status"] == "product_mentioned_in_snapshot"
    assert rows[0]["resolver_status"] == "issuer_product_bound"

    coverage = MODULE.build_source_coverage_gate(
        industry_schema="energy_utilities",
        phase="runtime_case",
        source_layer_capability={"rows": [_source("eia_open_data", "L2", "structured_not_promoted")]},
        observed_rows=rows,
        specialist_visible_rows={
            "industry_supply_chain_analyst": rows,
            "capital_ownership_macro_analyst": rows,
            "product_technology_analyst": rows,
        },
        required_dimensions=["energy_utility_context"],
        generated_at="2026-06-16T00:00:00Z",
    )
    assert coverage["status"] == "pass"


def test_public_official_api_context_rows_openalex_topic_only_does_not_pass_issuer_product_gate() -> None:
    rows = MODULE.build_public_official_api_context_rows(
        [
            {
                "record_id": "PUBLICSOURCE::openalex_api::research_work_lead_record::https://openalex.org/W1",
                "source_id": "openalex_api",
                "record_type": "research_work_lead_record",
                "provider": "OpenAlex",
                "entity_name": "",
                "product_name": "Physics of Semiconductor Devices",
                "identifier": "https://openalex.org/W1",
                "identifier_type": "OpenAlexWork",
                "metric_name": "cited_by_count",
                "value": 100,
                "attributes_json": '{"title": "Physics of Semiconductor Devices", "top_concepts": [{"display_name": "Semiconductor"}]}',
                "api_route": "https://api.openalex.org/works?search=semiconductor",
                "claim_boundary": "Research trend signal; not company financial evidence.",
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        issuer_index={},
    )
    assert rows[0]["ticker"] == ""
    assert rows[0]["product_binding_status"] == "technology_topic_bound"
    assert rows[0]["resolver_status"] == "topic_only"

    coverage = MODULE.build_source_coverage_gate(
        industry_schema="semiconductors_hardware",
        phase="runtime_case",
        source_layer_capability={"rows": [_source("openalex_api", "L3", "structured_not_promoted")]},
        observed_rows=rows,
        specialist_visible_rows={"product_technology_analyst": rows},
        required_dimensions=["technology_research_proxy"],
        generated_at="2026-06-16T00:00:00Z",
    )
    req = coverage["requirements"][0]
    assert req["status"] == "gap"
    assert any(gap["gap_type"] == "runtime_case_entity_binding_missing" for gap in req["gaps"])


def test_public_official_api_context_rows_openalex_issuer_and_topic_can_pass_proxy_gate() -> None:
    rows = MODULE.build_public_official_api_context_rows(
        [
            {
                "record_id": "PUBLICSOURCE::openalex_api::research_work_lead_record::https://openalex.org/W2",
                "source_id": "openalex_api",
                "record_type": "research_work_lead_record",
                "provider": "OpenAlex",
                "entity_name": "",
                "identifier": "https://openalex.org/W2",
                "identifier_type": "OpenAlexWork",
                "metric_name": "cited_by_count",
                "value": 10,
                "attributes_json": '{"title": "GPU cluster scheduling for AI accelerators", "authorships": [{"institutions": [{"display_name": "Nvidia"}]}], "top_concepts": [{"display_name": "GPU"}]}',
                "api_route": "https://api.openalex.org/works?search=gpu",
                "claim_boundary": "Research trend signal; not company financial evidence.",
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        issuer_index={"nvidia": {"ticker": "NVDA", "company_name": "Nvidia"}},
    )
    assert rows[0]["ticker"] == "NVDA"
    assert rows[0]["issuer_binding_status"] == "issuer_mentioned_in_snapshot"
    assert rows[0]["product_binding_status"] == "technology_topic_bound"
    assert rows[0]["resolver_status"] == "issuer_product_bound"

    coverage = MODULE.build_source_coverage_gate(
        industry_schema="semiconductors_hardware",
        phase="runtime_case",
        source_layer_capability={"rows": [_source("openalex_api", "L3", "structured_not_promoted")]},
        observed_rows=rows,
        specialist_visible_rows={"product_technology_analyst": rows},
        required_dimensions=["technology_research_proxy"],
        generated_at="2026-06-16T00:00:00Z",
    )
    assert coverage["status"] == "pass"


def test_public_official_api_context_rows_macro_context_gate_passes_without_issuer_binding() -> None:
    rows = MODULE.build_public_official_api_context_rows(
        [
            {
                "record_id": "PUBLICSOURCE::fred_api::macro_time_series_observation::2026-05-01",
                "source_id": "fred_api",
                "record_type": "macro_time_series_observation",
                "provider": "FRED",
                "series_id": "FEDFUNDS",
                "value": 3.63,
                "unit": "percent",
                "observation_date": "2026-05-01",
                "api_route": "https://api.stlouisfed.org/fred/series/observations",
                "claim_boundary": "Macro context only.",
            }
        ],
        generated_at="2026-06-16T00:00:00Z",
        issuer_index={},
    )
    coverage = MODULE.build_source_coverage_gate(
        industry_schema="generic_public_research",
        phase="runtime_case",
        source_layer_capability={"rows": [_source("fred_api", "L2", "structured_not_promoted")]},
        observed_rows=rows,
        specialist_visible_rows={
            "market_valuation_analyst": rows,
            "capital_ownership_macro_analyst": rows,
            "industry_supply_chain_analyst": rows,
        },
        required_dimensions=["macro_official_context"],
        generated_at="2026-06-16T00:00:00Z",
    )
    assert coverage["status"] == "pass"


def _source(source_id: str, layer_id: str, status: str) -> dict[str, object]:
    return {
        "source_id": source_id,
        "layer_id": layer_id,
        "evidence_graph_status": status,
        "runtime_ready_context": status in {"runtime_ready_context", "exact_authority_ready"},
        "can_crawl_or_download": True,
        "can_structure": True,
        "exact_value_authority_ready": False,
        "can_support_company_exact_fact": False,
    }
