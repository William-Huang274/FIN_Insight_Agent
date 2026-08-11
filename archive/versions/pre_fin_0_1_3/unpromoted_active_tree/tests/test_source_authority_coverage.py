from __future__ import annotations

from pathlib import Path

from sec_agent.lead_supervision import (
    build_lead_review_checkpoint,
    build_research_objective_contract,
    build_targeted_repair_plan,
)
from sec_agent.source_authority_coverage import (
    build_source_authority_coverage,
    dimension_source_authority_candidates,
    summarize_dimension_authority,
)


def test_source_authority_coverage_maps_product_dimension_to_thesis_driver() -> None:
    coverage = build_source_authority_coverage(
        [
            _matrix_row(
                ticker="NVDA",
                source_role="official_product_surface",
                source_id="company_product_pages",
                support_surface="product_and_technology",
                signal_authority_type="technical_fact",
                authority_mode="bounded_thesis_driver_authority",
                thesis=True,
            ),
            _matrix_row(
                ticker="NVDA",
                source_role="primary_company_disclosure",
                source_id="sec_edgar_apis",
                support_surface="fundamental_company_disclosure",
                signal_authority_type="company_disclosure_fact",
                authority_mode="exact_company_fact_authority",
                exact=True,
            ),
        ],
        focus_tickers=["NVDA"],
        search_scope_tickers=["NVDA"],
    )

    candidates = dimension_source_authority_candidates(coverage, "product_and_production")
    summary = summarize_dimension_authority(candidates, "product_and_production")

    assert coverage["summary"]["evidence_bundle_allowed_count"] == 2
    assert "official_product_surface" in {row["source_role"] for row in candidates}
    assert summary["thesis_driver_authority_count"] == 1
    assert summary["gap_classification"] == "evidence_available_not_yet_claimed"


def test_lead_review_uses_source_authority_matrix_before_bounded_gap() -> None:
    contract = build_research_objective_contract(
        query="分析 NVDA Blackwell 产品和 AI 需求传导。",
        required_dimensions=["product_and_production"],
    )
    coverage = build_source_authority_coverage(
        [
            _matrix_row(
                ticker="NVDA",
                source_role="official_product_surface",
                source_id="company_product_pages",
                support_surface="product_and_technology",
                signal_authority_type="technical_fact",
                authority_mode="bounded_thesis_driver_authority",
                thesis=True,
            )
        ],
        focus_tickers=["NVDA"],
        search_scope_tickers=["NVDA"],
    )

    checkpoint = build_lead_review_checkpoint(
        objective_contract=contract,
        claim_cards=[],
        gaps=[],
        source_authority_coverage=coverage,
    )
    review = checkpoint["dimension_reviews"][0]
    repair = build_targeted_repair_plan(checkpoint)

    assert review["status"] == "retrievable_gap"
    assert review["source_authority_coverage"]["evidence_bundle_allowed_count"] == 1
    assert review["source_authority_roles"] == ["official_product_surface"]
    assert checkpoint["memo_directive"]["source_authority_write_policy"]["repair_first_dimensions"] == [
        "product_and_production"
    ]
    assert repair["status"] == "ready"
    assert repair["repairs"][0]["source_authority_source_ids"] == ["company_product_pages"]


def test_source_authority_coverage_loader_missing_path_fails_closed(tmp_path: Path) -> None:
    from sec_agent.source_authority_coverage import load_source_authority_coverage

    payload = load_source_authority_coverage(path=tmp_path / "missing.jsonl", focus_tickers=["NVDA"])

    assert payload["status"] == "not_loaded"
    assert payload["rows"] == []


def _matrix_row(
    *,
    ticker: str,
    source_role: str,
    source_id: str,
    support_surface: str,
    signal_authority_type: str,
    authority_mode: str,
    thesis: bool = False,
    exact: bool = False,
) -> dict:
    return {
        "ticker": ticker,
        "company_name": ticker,
        "primary_lane_id": "V1",
        "source_role": source_role,
        "source_id": source_id,
        "source_layer": "L2" if not exact else "L1",
        "support_surface": support_surface,
        "can_enter_evidence_bundle": True,
        "availability_status": "runtime_ready_exact_or_bounded_slot",
        "adapter_parser_status": "parser_verified_exact_slot_ready",
        "claim_boundary": "bounded test row",
        "sample_urls": [f"https://example.com/{ticker}/{source_id}"],
        "sample_evidence_refs": [f"ref:{ticker}:{source_id}"],
        "authority": {
            "source_role": source_role,
            "source_id": source_id,
            "support_surface": support_surface,
            "authority_mode": authority_mode,
            "signal_authority_type": signal_authority_type,
            "exact_company_fact_authority": exact,
            "thesis_driver_authority": thesis,
            "can_enter_evidence_bundle": True,
            "admission_decision": "evidence_bundle_allowed",
            "claim_scope": "test scope",
            "forbidden_claim_types": ["product_revenue"] if thesis else [],
        },
    }
