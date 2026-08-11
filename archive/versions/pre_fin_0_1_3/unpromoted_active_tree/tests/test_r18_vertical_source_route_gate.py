from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_r18_vertical_source_route_gate.py"
)
SPEC = importlib.util.spec_from_file_location("build_r18_vertical_source_route_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_vertical_gate_passes_when_all_required_roles_have_evidence_rows() -> None:
    rows, summary = MODULE.build_vertical_source_route_gate(
        company_coverage_rows=[
            _company(
                "NVDA",
                [
                    _requirement("primary_company_disclosure", status="pass"),
                    _requirement("official_product_surface", status="pass"),
                ],
            )
        ],
        data_mart_rows=[
            _mart("NVDA", "primary_company_disclosure"),
            _mart("NVDA", "official_product_surface"),
        ],
        registry_payload=_registry(["primary_company_disclosure", "official_product_surface"]),
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["status"] == "pass"
    assert summary["status"] == "pass"
    assert summary["missing_requirement_count"] == 0


def test_vertical_gate_exposes_source_gap_when_required_role_has_no_evidence_row() -> None:
    rows, summary = MODULE.build_vertical_source_route_gate(
        company_coverage_rows=[
            _company(
                "NVDA",
                [
                    _requirement("primary_company_disclosure", status="pass"),
                    _requirement("developer_ecosystem_proxy", status="gap", gap_class="source_gap"),
                ],
            )
        ],
        data_mart_rows=[_mart("NVDA", "primary_company_disclosure")],
        registry_payload=_registry(["primary_company_disclosure", "developer_ecosystem_proxy"]),
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["status"] == "action_required"
    assert rows[0]["missing_source_roles"] == ["developer_ecosystem_proxy"]
    assert rows[0]["requirement_results"][1]["root_cause"] == "source_or_adapter_gap"
    assert summary["by_missing_source_role"]["developer_ecosystem_proxy"] == 1


def test_vertical_gate_flags_coverage_pass_without_data_mart_evidence() -> None:
    rows, summary = MODULE.build_vertical_source_route_gate(
        company_coverage_rows=[_company("NVDA", [_requirement("official_product_surface", status="pass")])],
        data_mart_rows=[],
        registry_payload=_registry(["official_product_surface"]),
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["status"] == "action_required"
    result = rows[0]["requirement_results"][0]
    assert result["root_cause"] == "mart_sync_or_authority_mapping_debt"
    assert "coverage_matrix_pass_without_data_mart_evidence" in result["hard_gate_flags"]
    assert summary["hard_gate"]["by_flag"]["coverage_matrix_pass_without_data_mart_evidence"] == 1


def test_vertical_gate_allows_official_customer_event_for_public_order_requirement() -> None:
    rows, summary = MODULE.build_vertical_source_route_gate(
        company_coverage_rows=[_company("AEHR", [_requirement("public_order_proxy", status="gap", gap_class="source_gap")])],
        data_mart_rows=[_mart("AEHR", "official_customer_order_or_deployment_event")],
        registry_payload=_registry(["public_order_proxy", "official_customer_order_or_deployment_event"]),
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["status"] == "pass"
    result = rows[0]["requirement_results"][0]
    assert result["candidate_source_roles"] == ["public_order_proxy", "official_customer_order_or_deployment_event"]
    assert result["satisfied_source_roles"] == ["official_customer_order_or_deployment_event"]
    assert summary["status"] == "pass"


def test_vertical_gate_does_not_allow_generic_supply_chain_relationship_for_public_order_requirement() -> None:
    rows, summary = MODULE.build_vertical_source_route_gate(
        company_coverage_rows=[_company("AEHR", [_requirement("public_order_proxy", status="gap", gap_class="source_gap")])],
        data_mart_rows=[_mart("AEHR", "supply_chain_official_relationship")],
        registry_payload=_registry(["public_order_proxy", "official_customer_order_or_deployment_event", "supply_chain_official_relationship"]),
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["status"] == "action_required"
    result = rows[0]["requirement_results"][0]
    assert result["candidate_source_roles"] == ["public_order_proxy", "official_customer_order_or_deployment_event"]
    assert result["satisfied_source_roles"] == []
    assert summary["status"] == "action_required"


def _company(ticker: str, requirements: list[dict]) -> dict:
    return {
        "ticker": ticker,
        "company_name": ticker,
        "primary_lane_id": "V1",
        "primary_lane_name": "Semiconductors / AI Infrastructure",
        "coverage_status": "partial_public_interface",
        "source_role_matrix": requirements,
    }


def _requirement(role: str, *, status: str, gap_class: str = "pass") -> dict:
    return {
        "requirement_id": role,
        "status": status,
        "gap_class": gap_class,
        "source_ids": [f"{role}_source"],
        "claim_boundary": "Boundary.",
    }


def _mart(ticker: str, role: str) -> dict:
    return {
        "ticker": ticker,
        "source_role": role,
        "source_id": f"{role}_source",
        "can_enter_evidence_bundle": True,
    }


def _registry(roles: list[str]) -> dict:
    return {"contracts": [{"source_role": role} for role in roles]}
