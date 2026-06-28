from __future__ import annotations

import importlib.util
from pathlib import Path

from sec_agent.source_route_registry_v2 import (
    get_source_route_contract,
    map_signal_authority_from_admission_row,
)


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_r18_source_route_registry_v2.py"
)
SPEC = importlib.util.spec_from_file_location("build_r18_source_route_registry_v2", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_official_product_surface_contract_is_registered() -> None:
    contract = get_source_route_contract("official_product_surface")

    assert contract is not None
    assert contract.support_surface == "product_and_technology"
    assert contract.authority_mode == "bounded_thesis_driver_authority"
    assert "product_revenue" in contract.forbidden_claim_types


def test_official_customer_order_or_deployment_event_contract_is_registered() -> None:
    contract = get_source_route_contract("official_customer_order_or_deployment_event")

    assert contract is not None
    assert contract.support_surface == "official_customer_order_deployment_event"
    assert contract.signal_authority_type == "customer_order_or_deployment_event_signal"
    assert contract.authority_mode == "bounded_thesis_driver_authority"
    assert "backlog" in contract.forbidden_claim_types
    assert "customer_order_value" in contract.forbidden_claim_types


def test_product_signal_contracts_are_registered() -> None:
    expected = {
        "technical_product_spec": ("product_spec_and_capability", "technical_fact"),
        "product_generation_edge": ("product_spec_and_capability", "product_generation_signal"),
        "product_benchmark_proxy": ("product_spec_and_capability", "product_benchmark_signal"),
        "customer_deployment_proxy": ("official_customer_deployment_signal", "customer_deployment_signal"),
    }

    for source_role, (surface, signal_type) in expected.items():
        contract = get_source_route_contract(source_role)
        assert contract is not None
        assert contract.support_surface == surface
        assert contract.signal_authority_type == signal_type
        assert contract.authority_mode == "bounded_thesis_driver_authority"
        assert "product_revenue" in contract.forbidden_claim_types


def test_capital_funding_ownership_contracts_are_registered() -> None:
    expected = {
        "capital_structure_disclosure": ("exact_company_fact_authority", "capital_structure_fact"),
        "lagged_ownership_context": ("bounded_thesis_driver_authority", "lagged_ownership_signal"),
        "working_capital_liquidity": ("exact_company_fact_authority", "working_capital_liquidity_fact"),
    }

    for source_role, (authority_mode, signal_type) in expected.items():
        contract = get_source_route_contract(source_role)
        assert contract is not None
        assert contract.support_surface == "capital_funding_ownership_market_liquidity"
        assert contract.authority_mode == authority_mode
        assert contract.signal_authority_type == signal_type
    assert "realtime_flow" in get_source_route_contract("lagged_ownership_context").forbidden_claim_types
    assert "product_sales_without_product_kpi" in get_source_route_contract("working_capital_liquidity").forbidden_claim_types


def test_sec_capital_market_event_contracts_are_registered() -> None:
    expected = {
        "securities_offering_filing_event": "capital_market_event_signal",
        "insider_transaction_filing_event": "insider_transaction_event_signal",
        "beneficial_ownership_filing_event": "beneficial_ownership_event_signal",
        "proxy_governance_filing_event": "proxy_governance_event_signal",
    }

    for source_role, signal_type in expected.items():
        contract = get_source_route_contract(source_role)
        assert contract is not None
        assert contract.support_surface == "capital_funding_ownership_market_liquidity"
        assert contract.source_layers == ("L1",)
        assert contract.authority_mode == "bounded_thesis_driver_authority"
        assert contract.signal_authority_type == signal_type
    assert "offering_amount_without_filing_text_or_xml" in get_source_route_contract("securities_offering_filing_event").forbidden_claim_types
    assert "insider_share_count_without_xml" in get_source_route_contract("insider_transaction_filing_event").forbidden_claim_types


def test_admission_row_maps_to_thesis_driver_authority() -> None:
    authority = map_signal_authority_from_admission_row(
        {
            "ticker": "NVDA",
            "company_name": "NVIDIA",
            "source_role": "official_product_surface",
            "source_id": "company_product_pages",
            "availability_status": "runtime_ready_exact_or_bounded_slot",
            "adapter_parser_status": "parser_verified_exact_slot_ready",
            "can_enter_evidence_bundle": True,
            "sample_urls": ["https://www.nvidia.com/en-us/data-center/h100/"],
            "parser_row_count": 1,
            "claim_boundary": "Official product existence and specs only.",
        }
    )

    assert authority["registered_source_role"] is True
    assert authority["thesis_driver_authority"] is True
    assert authority["can_enter_evidence_bundle"] is True
    assert authority["missing_required_fields"] == []


def test_unregistered_source_role_fails_closed() -> None:
    authority = map_signal_authority_from_admission_row(
        {
            "ticker": "NVDA",
            "source_role": "unregistered_route",
            "can_enter_evidence_bundle": True,
        }
    )

    assert authority["registered_source_role"] is False
    assert authority["admission_decision"] == "blocked_unregistered_source_role"


def test_registry_summary_blocks_unregistered_rows() -> None:
    registry, matrix_rows, summary = MODULE.build_registry_and_signal_matrix(
        [
            {
                "ledger_id": "ok",
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "source_role": "official_product_surface",
                "source_id": "company_product_pages",
                "support_surface": "product_and_technology",
                "availability_status": "runtime_ready_exact_or_bounded_slot",
                "adapter_parser_status": "parser_verified_exact_slot_ready",
                "can_enter_evidence_bundle": True,
                "sample_urls": ["https://www.nvidia.com/en-us/data-center/h100/"],
                "parser_row_count": 1,
                "claim_boundary": "Official product existence and specs only.",
            },
            {
                "ledger_id": "bad",
                "ticker": "NVDA",
                "company_name": "NVIDIA",
                "source_role": "unregistered_route",
                "source_id": "unknown",
                "can_enter_evidence_bundle": True,
            },
        ],
        generated_at="2026-06-23T00:00:00Z",
    )

    assert registry["source_role_count"] >= 16
    assert len(matrix_rows) == 2
    assert summary["status"] == "action_required"
    assert summary["hard_gate"]["unregistered_source_role_count"] == 1
