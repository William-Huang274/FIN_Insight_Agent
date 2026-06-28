from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_r18_data_source_admission_ledger.py"
)
SPEC = importlib.util.spec_from_file_location("build_r18_data_source_admission_ledger", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_parser_backed_context_row_can_enter_evidence_bundle() -> None:
    rows = MODULE.build_data_source_admission_ledger_rows(
        company_coverage_rows=[
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "primary_lane_id": "V1",
                "source_role_matrix": [
                    {
                        "requirement_id": "official_product_surface",
                        "dimension": "product_and_production",
                        "status": "pass",
                        "source_ids": ["company_product_pages"],
                        "route_sources": {
                            "company_product_pages": {
                                "layer_id": "L2",
                                "status": "structured_not_promoted",
                            }
                        },
                        "parser_row_count": 2,
                        "observed_row_count": 2,
                        "entity_bound_row_count": 1,
                        "exact_authority_violation_count": 0,
                        "claim_boundary": "Official product specs only; no sales or share inference.",
                    }
                ],
            }
        ],
        exact_slot_rows=[],
        attempt_rows=[],
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["availability_status"] == "runtime_ready_context_or_signal"
    assert rows[0]["adapter_parser_status"] == "parser_verified_context_ready"
    assert rows[0]["can_enter_evidence_bundle"] is True


def test_registered_route_without_parser_backed_company_row_stays_planning_only() -> None:
    rows = MODULE.build_data_source_admission_ledger_rows(
        company_coverage_rows=[
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "primary_lane_id": "V1",
                "source_role_matrix": [
                    {
                        "requirement_id": "channel_offer_proxy",
                        "dimension": "product_and_production",
                        "status": "gap",
                        "source_ids": ["channel_pricing_quotations"],
                        "route_sources": {
                            "channel_pricing_quotations": {
                                "layer_id": "L3",
                                "status": "runtime_ready_context",
                            }
                        },
                        "parser_row_count": 0,
                        "observed_row_count": 0,
                        "entity_bound_row_count": 0,
                        "exact_authority_violation_count": 0,
                        "claim_boundary": "Channel availability proxy only; no ASP.",
                    }
                ],
            }
        ],
        exact_slot_rows=[],
        attempt_rows=[],
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["availability_status"] == "planning_only_route_registered_no_company_row"
    assert rows[0]["can_enter_evidence_bundle"] is False


def test_attempt_backed_public_boundary_stays_out_of_evidence() -> None:
    rows = MODULE.build_data_source_admission_ledger_rows(
        company_coverage_rows=[
            {
                "ticker": "BYD",
                "company_name": "BYD",
                "primary_lane_id": "V5",
                "source_role_matrix": [
                    {
                        "requirement_id": "public_order_proxy",
                        "dimension": "industry_supply_chain",
                        "status": "gap",
                        "source_ids": ["public_tenders_contracts_orders"],
                        "route_sources": {
                            "public_tenders_contracts_orders": {
                                "layer_id": "L3",
                                "status": "runtime_ready_context",
                            }
                        },
                        "parser_row_count": 0,
                        "observed_row_count": 0,
                        "entity_bound_row_count": 0,
                        "exact_authority_violation_count": 0,
                        "claim_boundary": "Public order proxy only.",
                    }
                ],
            }
        ],
        exact_slot_rows=[],
        attempt_rows=[
            {
                "ticker": "BYD",
                "source_role": "public_order_proxy",
                "gate_status": "attempt_backed_public_boundary",
                "final_boundary_allowed": True,
                "attempt_count": 2,
            }
        ],
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["availability_status"] == "attempt_backed_public_boundary"
    assert rows[0]["adapter_parser_status"] == "attempt_backed_final_boundary"
    assert rows[0]["can_enter_evidence_bundle"] is False


def test_exact_slot_samples_are_backfilled_into_admission_row() -> None:
    rows = MODULE.build_data_source_admission_ledger_rows(
        company_coverage_rows=[
            {
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "primary_lane_id": "V1",
                "source_role_matrix": [
                    {
                        "requirement_id": "primary_company_disclosure",
                        "dimension": "fundamentals",
                        "status": "gap",
                        "source_ids": ["sec_edgar_apis"],
                        "route_sources": {
                            "sec_edgar_apis": {
                                "layer_id": "L1",
                                "status": "exact_authority_ready",
                            }
                        },
                        "parser_row_count": 0,
                        "observed_row_count": 0,
                        "entity_bound_row_count": 0,
                        "exact_authority_violation_count": 0,
                        "claim_boundary": "Company-disclosed facts only.",
                    }
                ],
            }
        ],
        exact_slot_rows=[
            {
                "ticker": "NVDA",
                "source_role_exact_slot_matrix": [
                    {
                        "requirement_id": "primary_company_disclosure",
                        "status": "exact_slot_ready",
                        "exact_slot_count": 1,
                        "sample_exact_slot_refs": ["exact_slot:abc"],
                        "sample_urls": ["https://www.sec.gov/Archives/example"],
                    }
                ],
            }
        ],
        attempt_rows=[],
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["availability_status"] == "runtime_ready_exact_or_bounded_slot"
    assert rows[0]["sample_evidence_refs"] == ["exact_slot:abc"]
    assert rows[0]["sample_urls"] == ["https://www.sec.gov/Archives/example"]


def test_passed_multi_source_requirement_only_admits_observed_source_id() -> None:
    rows = MODULE.build_data_source_admission_ledger_rows(
        company_coverage_rows=[
            {
                "ticker": "PCRFY",
                "company_name": "Panasonic Holdings Corporation",
                "primary_lane_id": "V7",
                "source_role_matrix": [
                    {
                        "requirement_id": "channel_offer_proxy",
                        "dimension": "product_and_production",
                        "status": "pass",
                        "source_ids": [
                            "channel_distributor_locator",
                            "channel_pricing_quotations",
                            "ecommerce_major_platforms",
                        ],
                        "observed_source_ids": ["channel_distributor_locator"],
                        "route_sources": {
                            "channel_distributor_locator": {
                                "layer_id": "L3",
                                "status": "runtime_ready_context",
                            },
                            "channel_pricing_quotations": {
                                "layer_id": "L3",
                                "status": "runtime_ready_context",
                            },
                            "ecommerce_major_platforms": {
                                "layer_id": "L3",
                                "status": "runtime_ready_context",
                            },
                        },
                        "parser_row_count": 1,
                        "observed_row_count": 1,
                        "entity_bound_row_count": 1,
                        "exact_authority_violation_count": 0,
                        "claim_boundary": "Channel/distributor presence proxy only; no ASP.",
                    }
                ],
            }
        ],
        exact_slot_rows=[],
        attempt_rows=[],
        generated_at="2026-06-23T00:00:00Z",
    )

    assert len(rows) == 1
    assert rows[0]["source_id"] == "channel_distributor_locator"
    assert rows[0]["availability_status"] == "runtime_ready_context_or_signal"
    assert rows[0]["can_enter_evidence_bundle"] is True
