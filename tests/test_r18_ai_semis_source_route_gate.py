from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_r18_ai_semis_source_route_gate.py"
)
SPEC = importlib.util.spec_from_file_location("build_r18_ai_semis_source_route_gate", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_ai_semis_gate_passes_parser_backed_gpu_assignment() -> None:
    rows, summary = MODULE.build_ai_semis_source_route_gate(
        matrix_rows=[
            _matrix("NVDA", "primary_company_disclosure"),
            _matrix("NVDA", "official_product_surface"),
            _matrix("NVDA", "technology_research_proxy"),
            _matrix("NVDA", "public_order_proxy"),
        ],
        assignment_rows=[_assignment("NVDA", "gpu_accelerator")],
        route_plan_rows=[],
        registry_payload=_registry(
            [
                "primary_company_disclosure",
                "official_product_surface",
                "technology_research_proxy",
                "public_order_proxy",
            ]
        ),
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["status"] == "pass"
    assert summary["status"] == "pass"
    assert summary["pass_assignment_count"] == 1


def test_ai_semis_gate_exposes_route_or_parser_debt_for_missing_role_group() -> None:
    rows, summary = MODULE.build_ai_semis_source_route_gate(
        matrix_rows=[
            _matrix("NVDA", "primary_company_disclosure"),
            _matrix("NVDA", "official_product_surface"),
        ],
        assignment_rows=[_assignment("NVDA", "gpu_accelerator")],
        route_plan_rows=[
            _route_plan("NVDA", "gpu_accelerator", "technology_research_proxy", "seed_available_not_materialized")
        ],
        registry_payload=_registry(
            [
                "primary_company_disclosure",
                "official_product_surface",
                "technology_research_proxy",
                "public_order_proxy",
            ]
        ),
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["status"] == "action_required"
    assert summary["status"] == "action_required"
    assert rows[0]["missing_groups"][0]["root_cause"] == "route_or_parser_debt"


def test_ai_semis_gate_uses_v1_assignment_scope_not_company_primary_lane() -> None:
    rows, summary = MODULE.build_ai_semis_source_route_gate(
        matrix_rows=[
            _matrix("VRT", "primary_company_disclosure", primary_lane_id="V7"),
            _matrix("VRT", "official_product_surface", primary_lane_id="V7"),
            _matrix("VRT", "macro_official_context", primary_lane_id="V7"),
        ],
        assignment_rows=[_assignment("VRT", "power_cooling")],
        route_plan_rows=[],
        registry_payload=_registry(["primary_company_disclosure", "official_product_surface", "macro_official_context"]),
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["status"] == "pass"
    assert summary["status"] == "pass"
    assert rows[0]["available_source_roles"] == [
        "macro_official_context",
        "official_product_surface",
        "primary_company_disclosure",
    ]


def _matrix(ticker: str, source_role: str, *, primary_lane_id: str = "V1") -> dict:
    return {
        "ticker": ticker,
        "primary_lane_id": primary_lane_id,
        "source_role": source_role,
        "can_enter_evidence_bundle": True,
        "authority": {"can_enter_evidence_bundle": True},
    }


def _assignment(ticker: str, family_id: str) -> dict:
    return {
        "ticker": ticker,
        "company_name": ticker,
        "family_id": family_id,
        "family_name": family_id,
        "family_lane_id": "V1",
    }


def _route_plan(ticker: str, family_id: str, route_id: str, status: str) -> dict:
    return {
        "ticker": ticker,
        "family_id": family_id,
        "family_lane_id": "V1",
        "route_id": route_id,
        "route_status": status,
    }


def _registry(roles: list[str]) -> dict:
    return {"contracts": [{"source_role": role} for role in roles]}
