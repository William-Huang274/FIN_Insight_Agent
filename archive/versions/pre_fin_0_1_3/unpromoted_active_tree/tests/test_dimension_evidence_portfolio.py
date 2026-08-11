from __future__ import annotations

from sec_agent.dimension_evidence_portfolio import (
    build_dimension_evidence_portfolio,
    compact_dimension_evidence_portfolio,
)
from sec_agent.lead_supervision import build_lead_review_checkpoint, build_research_objective_contract
from sec_agent.multi_agent_runtime import build_agent_data_view


def _product_state() -> dict:
    return {
        "run_id": "unit_dimension_portfolio",
        "focus_tickers": ["NVDA"],
        "product_intelligence_runtime_autoload": False,
        "fundamental_statement_pack": {
            "schema_version": "fundamental_pack_test",
            "summary": {"line_item_count": 1},
            "statement_line_items": [
                {
                    "ticker": "NVDA",
                    "statement_type": "income_statement",
                    "canonical_metric_id": "financial_metric:revenue",
                    "value": "130.5",
                    "unit": "usd_billions",
                    "period_key": "FY2026",
                    "source_family": "primary_sec_filing",
                    "evidence_refs": ["sec:nvda:revenue"],
                }
            ],
        },
        "product_intelligence_company_pack": {
            "schema_version": "finsight_product_intelligence_company_pack_v0_1",
            "ticker": "NVDA",
            "company_name": "NVIDIA Corporation",
            "status": "pass_with_gaps",
            "representative_product_profile_or_specs": [
                {
                    "source_row_id": "pig_spec:blackwell",
                    "ticker": "NVDA",
                    "product_family": "GPU / Accelerator",
                    "product_or_segment": "Blackwell GPU",
                    "metric_name": "architecture",
                    "value": "Blackwell",
                    "period": "2025",
                    "claim_boundary": "official technical context only",
                }
            ],
            "representative_deployment_rows": [
                {
                    "source_row_id": "pig_deploy:cloud",
                    "ticker": "NVDA",
                    "product_or_segment": "Blackwell GPU",
                    "counterparty": "cloud customer",
                    "claim_boundary": "official deployment context only",
                }
            ],
            "representative_relationship_edges": [
                {
                    "edge_id": "pig_edge:nvda_amd",
                    "authority_type": "competitive_context_candidate",
                    "can_enter_evidence_bundle": True,
                    "edge_type": "COMPETES_WITH",
                }
            ],
        },
        "ai_semis_product_evidence_pack": {
            "schema_version": "finsight_ai_semis_product_evidence_pack_v0_2",
            "ticker": "NVDA",
            "company_name": "NVIDIA Corporation",
            "family_ids": ["gpu_accelerator"],
            "depth_status": "pass",
            "strict_depth_status": "pass",
            "evidence_role_count": 5,
            "layers": {
                "product_spec_architecture": {"status": "present"},
                "customer_deployment_adoption": {"status": "present"},
                "product_performance_proxy": {"status": "present"},
                "product_kpi_exact": {"status": "gap"},
                "product_relationship_graph": {"status": "present"},
            },
            "memo_writer_boundary": "spec/deployment/proxy evidence cannot become undisclosed sales facts",
        },
    }


def test_dimension_evidence_portfolio_separates_product_authority_from_exact_kpi() -> None:
    portfolio = build_dimension_evidence_portfolio(_product_state(), autoload=False)

    assert portfolio["schema_version"] == "finsight_dimension_evidence_portfolio_v0_1"
    product = next(row for row in portfolio["dimensions"] if row["dimension_id"] == "product_and_production")
    assert product["evidence_status"] == "ready"
    assert "product_intelligence_pack_ref" in product["available_pack_refs"]
    assert "product_evidence_pack_ref" in product["available_pack_refs"]
    assert "exact_product_kpi" in product["evidence_roles"]
    assert "technical_fact" in product["evidence_roles"]
    assert "only exact KPI rows support sales/share/backlog claims" in product["promotion_boundary"]


def test_research_lead_and_product_agent_get_role_scoped_dimension_portfolio() -> None:
    state = _product_state()
    lead_view = build_agent_data_view("research_lead", state)
    product_view = build_agent_data_view("product_technology_analyst", state)

    lead_ref = lead_view["dimension_evidence_portfolio_ref"]
    product_ref = product_view["dimension_evidence_portfolio_ref"]
    assert lead_ref["schema_version"] == "finsight_dimension_evidence_portfolio_ref_v0_1"
    assert len(lead_ref["dimensions"]) >= 5
    assert any(row["dimension_id"] == "product_and_production" for row in product_ref["dimensions"])
    assert product_view["role_context"]["dimension_evidence_portfolio_ref"]["dimensions"]


def test_lead_review_marks_unused_available_dimension_pack_as_retrievable_gap() -> None:
    portfolio = build_dimension_evidence_portfolio(_product_state(), autoload=False)
    contract = build_research_objective_contract(
        query="Assess NVDA product competitiveness",
        required_dimensions=["product_and_production"],
    )
    checkpoint = build_lead_review_checkpoint(
        objective_contract=contract,
        packs={"dimension_evidence_portfolio": portfolio},
        claim_cards=[],
        gaps=[],
    )

    review = checkpoint["dimension_reviews"][0]
    assert review["dimension"] == "product_and_production"
    assert review["status"] == "retrievable_gap"
    assert review["pack_present"] is True
    assert "product_evidence_pack_ref" in review["dimension_portfolio_available_pack_refs"]
    assert checkpoint["dimension_evidence_portfolio_ref"]["dimensions"]


def test_dimension_portfolio_compaction_is_role_scoped() -> None:
    portfolio = build_dimension_evidence_portfolio(_product_state(), autoload=False)
    ref = compact_dimension_evidence_portfolio(portfolio, agent_id="fundamental_analyst")
    dimension_ids = {row["dimension_id"] for row in ref["dimensions"]}

    assert "fundamentals" in dimension_ids
    assert "product_and_production" not in dimension_ids
