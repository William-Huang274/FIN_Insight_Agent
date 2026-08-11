from __future__ import annotations

import json
from pathlib import Path

import yaml

from sec_agent.source_layer_capability_audit import (
    build_source_layer_capability_audit,
    validate_source_layer_capability_audit,
)
from sec_agent.lead_supervision import (
    build_lead_review_checkpoint,
    build_research_objective_contract,
    build_targeted_repair_plan,
)


def test_source_layer_capability_audit_preserves_expected_proxy_sources(tmp_path: Path) -> None:
    coverage_path = tmp_path / "coverage.yaml"
    availability_path = tmp_path / "availability.jsonl"
    materialization_path = tmp_path / "materialization.jsonl"
    inventory_path = tmp_path / "inventory.json"

    coverage_path.write_text(
        yaml.safe_dump(
            {
                "sources": [
                    {
                        "source_id": "company_product_pages",
                        "provider": "Company official web",
                        "source_families": ["official_product_status"],
                        "claim_scope": "product_existence_spec_or_launch_context",
                        "collector_status": "implemented_bounded_official_page_samples",
                        "parser_status": "pending_product_page_parser",
                        "priority": "P1_product_evidence",
                    },
                    {
                        "source_id": "sec_edgar_apis",
                        "provider": "SEC",
                        "source_families": ["sec_primary_filing"],
                        "claim_scope": "company_reported_financial_fact",
                        "collector_status": "implemented_for_sec_primary_companyfacts_submissions",
                        "parser_status": "implemented_for_current_us_pipeline",
                        "priority": "P0_keep_core",
                    },
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    availability_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "source_id": "company_product_pages",
                        "audit_status": "not_audited_source_plan_only",
                        "availability_decision": "not_ready_source_plan_only",
                        "claim_scope": "product_existence_spec_or_launch_context",
                    }
                ),
                json.dumps(
                    {
                        "source_id": "sec_edgar_apis",
                        "audit_status": "live_pass",
                        "availability_decision": "ready_for_context_inventory_after_boundary_gate",
                        "field_completeness": {"status": "pass"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    materialization_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "source_id": "company_product_pages",
                        "information_strength_tier": "S4_company_authored_operating_context",
                        "materialization_status": "materialized_context_snapshot_gate_pending",
                        "runtime_promotion_status": "staging_only_parser_citation_boundary_gate_pending",
                        "cleaned_text_row_count": 3,
                    }
                ),
                json.dumps(
                    {
                        "source_id": "sec_edgar_apis",
                        "information_strength_tier": "S5_primary_authority",
                        "materialization_status": "materialized_existing_core",
                        "runtime_promotion_status": "accepted_core",
                        "sec_structured_fact_row_count": 10,
                        "sec_annual_ledger_fact_count": 8,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    inventory_path.write_text(json.dumps({"promoted_sources": ["sec_edgar_apis"]}), encoding="utf-8")

    payload = build_source_layer_capability_audit(
        coverage_config_path=coverage_path,
        availability_audit_path=availability_path,
        materialization_matrix_path=materialization_path,
        inventory_summary_path=inventory_path,
        generated_at="2026-06-15T00:00:00Z",
    )

    rows = {row["source_id"]: row for row in payload["rows"]}
    assert rows["company_product_pages"]["layer_id"] == "L2"
    assert rows["company_product_pages"]["evidence_graph_status"] == "staging_parser_gate_pending"
    assert rows["company_product_pages"]["can_support_company_exact_fact"] is False
    assert rows["sec_edgar_apis"]["layer_id"] == "L1"
    assert rows["sec_edgar_apis"]["runtime_ready_context"] is True
    assert rows["mainstream_financial_news"]["layer_id"] == "L2"
    assert rows["mainstream_financial_news"]["evidence_graph_status"] == "runtime_ready_context"
    assert rows["mainstream_financial_news"]["parser_status"] == "article_parser_smoke_pass"
    assert rows["mainstream_financial_news"]["can_support_company_exact_fact"] is False
    assert rows["supplier_customer_official_news"]["layer_id"] == "L2"
    assert rows["supplier_customer_official_news"]["evidence_graph_status"] == "runtime_ready_context"
    assert rows["supplier_customer_official_news"]["parser_status"] == "article_parser_smoke_pass"
    assert rows["supplier_customer_official_news"]["can_support_company_exact_fact"] is False
    assert rows["ecommerce_major_platforms"]["layer_id"] == "L3"
    assert rows["ecommerce_major_platforms"]["evidence_graph_status"] == "not_registered"
    assert payload["validation"]["status"] == "pass"


def test_source_layer_capability_audit_rejects_non_l1_exact_authority() -> None:
    validation = validate_source_layer_capability_audit(
        [
            {
                "source_id": "ecommerce_major_platforms",
                "layer_id": "L3",
                "evidence_graph_status": "runtime_ready_context",
                "context_or_proxy_allowed": True,
                "memo_usage": "directional proxy",
                "exact_value_authority_ready": False,
                "parser_gate_passed": False,
                "can_support_company_exact_fact": True,
            }
        ]
    )
    assert validation["status"] == "fail"
    assert validation["errors"][0]["type"] == "non_l1_company_exact_fact_authority"


def test_lead_review_uses_source_layer_candidates_before_bounded_gap() -> None:
    contract = build_research_objective_contract(
        query="分析某公司产品线和公开产品 proxy 能支持哪些判断。",
        required_dimensions=["product_and_production"],
    )
    source_layer_capability = {
        "rows": [
            {
                "source_id": "company_product_pages",
                "layer_id": "L2",
                "evidence_graph_status": "structured_not_promoted",
                "claim_scope": "product_existence_spec_or_launch_context",
                "context_or_proxy_allowed": True,
                "exact_value_authority_ready": False,
                "blocking_reason": "product_page_parser_pending",
                "next_action": "expand official domain allowlist and parse product pages",
                "memo_usage": "trusted product context",
                "specialist_slots": ["product_technology"],
            },
            {
                "source_id": "ecommerce_major_platforms",
                "layer_id": "L3",
                "evidence_graph_status": "not_registered",
                "claim_scope": "price_availability_channel_proxy",
                "context_or_proxy_allowed": False,
                "exact_value_authority_ready": False,
                "blocking_reason": "not registered",
                "next_action": "add channel parser",
                "memo_usage": "directional channel proxy",
                "specialist_slots": ["product_technology"],
            },
        ]
    }

    checkpoint = build_lead_review_checkpoint(
        objective_contract=contract,
        claim_cards=[],
        gaps=[],
        source_layer_capability=source_layer_capability,
    )

    review = checkpoint["dimension_reviews"][0]
    assert review["status"] == "retrievable_gap"
    assert review["candidate_source_layers"][0]["source_id"] == "company_product_pages"
    assert review["source_layer_repairability"]["repairable_candidate_count"] == 1
    assert review["source_layer_repairability"]["missing_runtime_route_sources"] == ["ecommerce_major_platforms"]

    repair_plan = build_targeted_repair_plan(checkpoint)
    assert repair_plan["status"] == "ready"
    assert repair_plan["repairs"][0]["repair_type"] == "product_surface"
