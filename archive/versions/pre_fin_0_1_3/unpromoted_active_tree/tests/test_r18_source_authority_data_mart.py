from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_r18_source_authority_data_mart.py"
)
SPEC = importlib.util.spec_from_file_location("build_r18_source_authority_data_mart", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_data_mart_joins_authority_and_preserves_claim_boundary() -> None:
    rows, summary = MODULE.build_source_authority_data_mart(
        admission_rows=[
            _admission(
                "NVDA",
                "official_product_surface",
                can_enter=True,
                claim_boundary="Official product spec only; no SKU revenue.",
            )
        ],
        authority_rows=[
            _authority(
                "NVDA",
                "official_product_surface",
                authority_mode="bounded_thesis_driver_authority",
                signal_authority_type="product_spec_signal",
            )
        ],
        company_coverage_rows=[_company("NVDA")],
        generated_at="2026-06-23T00:00:00Z",
    )

    assert summary["status"] == "pass"
    assert summary["evidence_bundle_allowed_count"] == 1
    assert rows[0]["authority_mode"] == "bounded_thesis_driver_authority"
    assert rows[0]["signal_authority_type"] == "product_spec_signal"
    assert rows[0]["claim_boundary"] == "Official product spec only; no SKU revenue."
    assert rows[0]["admission_tier"] == "bounded_thesis_driver_authority"


def test_data_mart_hard_gate_flags_accepted_row_without_citation() -> None:
    rows, summary = MODULE.build_source_authority_data_mart(
        admission_rows=[
            {
                **_admission("NVDA", "official_product_surface", can_enter=True),
                "sample_urls": [],
                "sample_evidence_refs": [],
            }
        ],
        authority_rows=[_authority("NVDA", "official_product_surface")],
        company_coverage_rows=[_company("NVDA")],
        generated_at="2026-06-23T00:00:00Z",
    )

    assert summary["status"] == "action_required"
    assert "accepted_row_missing_url_or_evidence_ref" in rows[0]["source_matrix_hard_gate_flags"]
    assert summary["hard_gate"]["by_flag"]["accepted_row_missing_url_or_evidence_ref"] == 1


def test_data_mart_keeps_non_admitted_rows_out_of_hard_gate() -> None:
    rows, summary = MODULE.build_source_authority_data_mart(
        admission_rows=[_admission("NVDA", "developer_ecosystem_proxy", can_enter=False, claim_boundary="")],
        authority_rows=[],
        company_coverage_rows=[_company("NVDA")],
        generated_at="2026-06-23T00:00:00Z",
    )

    assert rows[0]["can_enter_evidence_bundle"] is False
    assert rows[0]["source_matrix_hard_gate_flags"] == []
    assert summary["status"] == "pass"
    assert summary["planning_or_gap_only_count"] == 1


def _admission(
    ticker: str,
    role: str,
    *,
    can_enter: bool,
    claim_boundary: str = "Boundary.",
) -> dict:
    return {
        "ledger_id": f"ledger:{ticker}:{role}",
        "ticker": ticker,
        "company_name": ticker,
        "primary_lane_id": "V1",
        "primary_lane_name": "Semiconductors / AI Infrastructure",
        "source_role": role,
        "source_id": f"{role}_source",
        "source_layer": "L2",
        "support_surface": "product_and_technology",
        "availability_status": "runtime_ready_context_or_signal" if can_enter else "planning_only",
        "adapter_parser_status": "parser_verified_context_ready",
        "can_enter_evidence_bundle": can_enter,
        "claim_boundary": claim_boundary,
        "parser_row_count": 1 if can_enter else 0,
        "exact_slot_count": 0,
        "sample_urls": ["https://example.com"],
        "sample_evidence_refs": ["ref:1"],
    }


def _authority(
    ticker: str,
    role: str,
    *,
    authority_mode: str = "bounded_thesis_driver_authority",
    signal_authority_type: str = "product_signal",
) -> dict:
    return {
        "ledger_id": f"ledger:{ticker}:{role}",
        "ticker": ticker,
        "source_role": role,
        "source_id": f"{role}_source",
        "can_enter_evidence_bundle": True,
        "authority": {
            "authority_mode": authority_mode,
            "signal_authority_type": signal_authority_type,
            "can_enter_evidence_bundle": True,
            "thesis_driver_authority": True,
            "forbidden_claim_types": ["product_revenue"],
        },
    }


def _company(ticker: str) -> dict:
    return {
        "ticker": ticker,
        "status": "pass",
        "coverage_status": "public_interface_ready",
    }
