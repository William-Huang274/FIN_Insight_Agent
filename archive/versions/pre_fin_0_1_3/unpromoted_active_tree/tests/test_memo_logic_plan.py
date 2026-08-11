from __future__ import annotations

from sec_agent.langgraph_orchestrator import (
    _memo_logic_plan_judgment_state_input,
    _required_question_items_for_contract,
    build_multi_agent_summary_artifact_payload,
)
from sec_agent.memo_logic_plan import build_memo_logic_plan
from sec_agent.memo_llm import _compact_memo_logic_plan


def test_memo_logic_plan_carries_answer_first_evidence_to_thesis_bridge() -> None:
    plan = build_memo_logic_plan(
        judgment_state={
            "dimension_judgments": [
                {
                    "dimension_id": "fundamentals",
                    "title": "Fundamentals",
                    "claim_ids": ["claim_revenue_quality"],
                    "evidence_refs": ["ev_revenue", "ev_margin"],
                    "summary": "Revenue quality improved but margin bridge still matters.",
                },
                {
                    "dimension_id": "risk_and_counterevidence",
                    "title": "Risk And Counterevidence",
                    "claim_ids": [],
                    "evidence_refs": [],
                },
            ]
        },
        lead_review_checkpoint={
            "dimension_reviews": [
                {"dimension": "fundamentals", "status": "sufficient"},
                {"dimension": "risk_and_counterevidence", "status": "bounded_gap", "gap_ids": ["gap_price_in"]},
            ],
            "memo_directive": {
                "memo_stance": "The memo should lead with the operating thesis, then explain what would change it.",
                "gap_budget_policy": {"max_body_gap_sentences": 2},
            },
        },
    )

    assert plan["validation"]["status"] == "pass"
    assert plan["answer_first_outline"]["thesis_statement"].startswith("The memo should lead")
    assert plan["answer_first_outline"]["decision_changing_evidence_refs"] == ["ev_revenue", "ev_margin"]
    bridge = {row["dimension_id"]: row for row in plan["evidence_to_thesis_bridge"]}
    assert bridge["fundamentals"]["thesis_role"] == "supporting_thesis"
    assert bridge["fundamentals"]["evidence_refs"] == ["ev_revenue", "ev_margin"]
    assert bridge["risk_and_counterevidence"]["thesis_role"] == "boundary_or_counter_thesis"
    assert bridge["risk_and_counterevidence"]["gap_refs"] == ["gap_price_in"]
    assert plan["writer_thesis_skeleton"]["opening_judgment"].startswith("The memo should lead")
    assert plan["writer_thesis_skeleton"]["dimension_moves"][0]["required_writer_move"].startswith("make_a_bounded_judgment")
    assert plan["thesis_density_contract"]["minimum_supported_insight_sentences"] >= 3

    compact = _compact_memo_logic_plan(plan)
    assert compact["answer_first_outline"]["decision_changing_evidence_refs"] == ["ev_revenue", "ev_margin"]
    assert compact["evidence_to_thesis_bridge"][0]["claim_ids"] == ["claim_revenue_quality"]
    assert compact["writer_thesis_skeleton"]["opening_judgment"].startswith("The memo should lead")
    assert compact["thesis_density_contract"]["forbidden_low_density_patterns"]


def test_memo_logic_plan_product_frame_adds_product_thesis_moves() -> None:
    plan = build_memo_logic_plan(
        judgment_state={
            "dimension_judgments": [
                {
                    "dimension_id": "product_and_production",
                    "title": "Product",
                    "claim_ids": ["claim_product_spec"],
                    "evidence_refs": ["ev_h100_spec"],
                    "summary": "Product evidence supports demand read-through.",
                }
            ]
        },
        product_reasoning_frame={
            "coverage_roles": ["technical_product_spec", "customer_deployment"],
            "required_reasoning_edges": ["GPU architecture -> cloud deployment -> server demand"],
            "product_spec_refs": ["ev_h100_spec"],
            "deployment_refs": ["ev_cloud_deployment"],
        },
        required_question_items=[
            {
                "question_item_id": "nvda_gpu_supply_generation",
                "dimension": "product_and_production",
                "required_tickers": ["NVDA"],
                "required_evidence_roles": ["product_spec", "generation_edge"],
                "terms_any": ["NVDA", "GPU", "Blackwell"],
            }
        ],
    )

    assert plan["validation"]["status"] == "pass"
    product_move = plan["writer_thesis_skeleton"]["product_reasoning_move"]
    assert "technical_product_spec" in product_move["coverage_roles"]
    assert "GPU architecture -> cloud deployment -> server demand" in product_move["required_reasoning_edges"]
    assert "state_product_capability_or_line" in plan["thesis_density_contract"]["required_product_moves"]
    assert plan["required_item_answer_plan"][0]["question_item_id"] == "nvda_gpu_supply_generation"
    assert "product capability" in plan["required_item_answer_plan"][0]["answer_first_judgment_prompt"]
    assert plan["writer_thesis_skeleton"]["dimension_moves"][0]["required_item_ids"] == ["nvda_gpu_supply_generation"]
    assert plan["writer_thesis_skeleton"]["dimension_moves"][0]["required_item_answer_moves"][0]["answer_role"] == "product_generation_capability"
    compact = _compact_memo_logic_plan(plan)
    assert compact["required_item_answer_plan"][0]["question_item_id"] == "nvda_gpu_supply_generation"
    assert compact["writer_thesis_skeleton"]["dimension_moves"][0]["required_item_answer_move_count"] == 1
    assert "required_item_answer_moves" not in compact["writer_thesis_skeleton"]["dimension_moves"][0]


def test_memo_logic_plan_projects_judgment_cards_and_thesis_path_to_writer_skeleton() -> None:
    plan = build_memo_logic_plan(
        judgment_state={
            "dimension_judgments": [
                {
                    "dimension_id": "product_and_production",
                    "title": "Product",
                    "claim_ids": ["claim_product"],
                    "evidence_refs": ["ev_product"],
                    "summary": "Product adoption evidence supports but does not prove SKU revenue.",
                },
                {
                    "dimension_id": "fundamentals",
                    "title": "Fundamentals",
                    "claim_ids": ["claim_financial"],
                    "evidence_refs": ["ev_financial"],
                    "summary": "Reported revenue and margin facts define financial quality.",
                },
            ],
            "judgment_cards": [
                {
                    "judgment_card_id": "judgment_claim_product",
                    "source_claim_id": "claim_product",
                    "dimension_id": "product_and_production",
                    "memo_slot": "product_technology",
                    "judgment": "Product family evidence is usable for adoption judgment but not SKU revenue.",
                    "evidence_bridge": "Use ev_product as product evidence.",
                    "business_mechanism": "Product adoption can support server demand.",
                    "financial_bridge": "Bridge only to revenue or margin when verified.",
                    "counter_read": "SKU revenue remains undisclosed.",
                    "what_would_change_view": ["Named deployment would upgrade confidence."],
                    "evidence_refs": ["ev_product"],
                    "mechanism_bridge_status": "pass",
                }
            ],
            "thesis_path": {
                "status": "ready",
                "primary_thesis": "Product evidence supports a bounded adoption thesis.",
                "mechanism_bridge_status": "pass",
                "path_nodes": [
                    {
                        "node_id": "dimension::product_and_production",
                        "dimension_id": "product_and_production",
                        "judgment_card_ids": ["judgment_claim_product"],
                        "claim_ids": ["claim_product"],
                        "evidence_refs": ["ev_product"],
                        "business_mechanism": "Product adoption can support server demand.",
                        "financial_bridge": "Bridge only to revenue or margin when verified.",
                        "counter_read": "SKU revenue remains undisclosed.",
                    }
                ],
                "path_edges": [],
            },
        },
        product_reasoning_frame={
            "coverage_roles": ["official_product_surface"],
            "required_reasoning_edges": ["product_family_to_adoption_signal"],
        },
    )

    assert plan["validation"]["status"] == "pass"
    assert plan["judgment_cards"][0]["judgment_card_id"] == "judgment_claim_product"
    assert plan["writer_thesis_skeleton"]["opening_judgment"] == "Product evidence supports a bounded adoption thesis."
    assert plan["writer_thesis_skeleton"]["dimension_moves"][0]["judgment_card_ids"] == ["judgment_claim_product"]
    assert plan["writer_thesis_skeleton"]["thesis_path_move"]["mechanism_bridge_status"] == "pass"

    compact = _compact_memo_logic_plan(plan)
    assert compact["judgment_cards"][0]["judgment_card_id"] == "judgment_claim_product"
    assert compact["writer_thesis_skeleton"]["judgment_card_moves"][0]["judgment_card_id"] == "judgment_claim_product"
    assert compact["writer_thesis_skeleton"]["thesis_path_move"]["primary_thesis"].startswith("Product evidence")


def test_memo_logic_plan_semicap_required_items_build_answer_contracts() -> None:
    plan = build_memo_logic_plan(
        judgment_state={
            "dimension_judgments": [
                {
                    "dimension_id": "product_and_production",
                    "title": "Product and orders",
                    "claim_ids": ["claim_asml_backlog"],
                    "evidence_refs": ["ev_asml_backlog"],
                    "summary": "ASML order visibility matters for the cycle.",
                },
                {
                    "dimension_id": "risk_and_counterevidence",
                    "title": "Export risk",
                    "claim_ids": ["claim_export_risk"],
                    "evidence_refs": ["ev_export"],
                    "summary": "Export restrictions affect China exposure.",
                },
            ]
        },
        product_reasoning_frame={
            "coverage_roles": ["official_product_surface", "company_disclosed_product_kpi"],
            "product_kpi_refs": ["ev_asml_backlog"],
            "required_reasoning_edges": ["orders_backlog_to_semicap_cycle_visibility"],
        },
        required_question_items=[
            {
                "question_item_id": "asml_orders_or_backlog",
                "dimension": "product_and_production",
                "required_tickers": ["ASML"],
                "required_evidence_roles": ["orders_backlog", "non_us_disclosure"],
                "terms_any": ["ASML", "orders", "backlog"],
            },
            {
                "question_item_id": "export_restriction_context",
                "dimension": "risk_and_counterevidence",
                "required_tickers": ["ASML", "AMAT", "LRCX", "KLAC"],
                "required_evidence_roles": ["regulatory_export_control"],
                "terms_any": ["export", "China", "restriction"],
            },
        ],
    )

    assert plan["validation"]["status"] == "pass"
    by_id = {row["question_item_id"]: row for row in plan["required_item_answer_plan"]}
    assert by_id["asml_orders_or_backlog"]["answer_role"] == "orders_backlog_cycle_signal"
    assert "semicap cycle visibility" in by_id["asml_orders_or_backlog"]["answer_first_judgment_prompt"]
    assert by_id["export_restriction_context"]["answer_role"] == "export_control_risk"
    moves = {row["dimension_id"]: row for row in plan["writer_thesis_skeleton"]["dimension_moves"]}
    assert "asml_orders_or_backlog" in moves["product_and_production"]["required_item_ids"]
    assert "export_restriction_context" in moves["risk_and_counterevidence"]["required_item_ids"]


def test_memo_logic_plan_accepts_dimension_owned_gap_ids_as_section_trace() -> None:
    plan = build_memo_logic_plan(
        judgment_state={
            "dimension_judgments": [
                {
                    "dimension_id": "thesis_synthesis",
                    "title": "Synthesis",
                    "claim_ids": [],
                    "evidence_refs": [],
                    "gap_ids": ["gap_orders_backlog"],
                    "summary": "Synthesis remains bounded by missing orders/backlog confirmation.",
                }
            ]
        },
        lead_review_checkpoint={
            "memo_directive": {
                "memo_stance": "Lead with the bounded thesis.",
                "gap_budget_policy": {"max_body_gap_sentences": 2},
            }
        },
    )

    assert plan["validation"]["status"] == "pass"
    assert plan["sections"][0]["required_gap_refs"] == ["gap_orders_backlog"]


def test_multi_agent_summary_projects_required_item_answer_plan() -> None:
    plan = build_memo_logic_plan(
        judgment_state={
            "dimension_judgments": [
                {
                    "dimension_id": "product_and_production",
                    "title": "Product",
                    "claim_ids": ["claim_dell_ai_server"],
                    "evidence_refs": ["ev_dell_ai_server"],
                    "summary": "DELL AI server revenue supports product quality analysis.",
                }
            ]
        },
        lead_review_checkpoint={"memo_directive": {"memo_stance": "Lead with product-quality judgment."}},
        required_question_items=[
            {
                "question_item_id": "dell_ai_server_quality_margin_bridge",
                "dimension": "product_and_production",
                "required_tickers": ["DELL"],
                "required_evidence_roles": ["product_kpi_exact", "financial_margin_bridge"],
                "terms_any": ["DELL", "AI server", "gross margin"],
            }
        ],
    )

    summary = build_multi_agent_summary_artifact_payload(
        {
            "run_id": "unit_summary_projection",
            "status": "completed",
            "memo_logic_plan": plan,
        }
    )

    projected = summary["memo_logic_plan"]
    assert projected["required_question_item_count"] == 1
    assert projected["required_item_answer_plan_count"] == 1
    assert projected["required_item_answer_plan"][0]["question_item_id"] == "dell_ai_server_quality_margin_bridge"
    assert projected["writer_thesis_skeleton_present"] is True


def test_memo_logic_plan_projects_economic_role_summary_to_writer_payload() -> None:
    plan = build_memo_logic_plan(
        judgment_state={
            "dimension_judgments": [
                {
                    "dimension_id": "capital_and_financing",
                    "title": "Capital",
                    "claim_ids": ["claim_msft_capex", "claim_lrcx_capex"],
                    "evidence_refs": ["ev_msft_capex", "ev_lrcx_capex"],
                    "summary": "Separate customer demand capex from supplier own capex.",
                }
            ],
            "supported_claims": [
                {
                    "claim_id": "claim_msft_capex",
                    "ticker_scope": ["MSFT"],
                    "metric_scope": ["financial_metric:capex"],
                    "analysis_dimension": "capital_and_financing",
                    "scope_role": "peer_context_ticker",
                    "economic_role": "customer_or_demand_side_capex_signal",
                    "transmission_role": "demand_pool_or_customer_infrastructure_spend_proxy",
                    "memo_use_role": "Use as demand-side spending context only.",
                    "role_boundary": "capex_peer_context_not_supplier_revenue_or_order",
                    "evidence_refs": ["ev_msft_capex"],
                },
                {
                    "claim_id": "claim_lrcx_capex",
                    "ticker_scope": ["LRCX"],
                    "metric_scope": ["financial_metric:capex"],
                    "analysis_dimension": "capital_and_financing",
                    "scope_role": "focus_ticker",
                    "economic_role": "issuer_own_capital_investment",
                    "transmission_role": "supplier_or_issuer_reinvestment_capacity_and_asset_intensity",
                    "memo_use_role": "Use as issuer reinvestment.",
                    "role_boundary": "issuer_capex_not_customer_demand_without_counterparty",
                    "evidence_refs": ["ev_lrcx_capex"],
                },
            ],
        }
    )

    assert plan["validation"]["status"] == "pass"
    role_counts = plan["economic_role_summary"]["role_counts"]
    assert role_counts["customer_or_demand_side_capex_signal"] == 1
    assert role_counts["issuer_own_capital_investment"] == 1
    assert "Peer/customer capex is demand-pool context" in plan["economic_role_summary"]["writer_instruction"]
    assert plan["writer_thesis_skeleton"]["economic_role_move"]["role_boundary_counts"][
        "capex_peer_context_not_supplier_revenue_or_order"
    ] == 1
    compact = _compact_memo_logic_plan(plan)
    assert compact["economic_role_summary"]["role_rows"][0]["economic_role"] == "customer_or_demand_side_capex_signal"
    assert compact["writer_thesis_skeleton"]["economic_role_move"]["role_counts"]["issuer_own_capital_investment"] == 1


def test_required_answer_moves_compile_into_required_question_items() -> None:
    rows = _required_question_items_for_contract(
        {
            "focus_tickers": ["NVDA", "AMD", "GOOGL", "DELL"],
            "required_answer_moves": [
                "Start with a clear bounded thesis, not background.",
                "Explain product/architecture advantage and competitive/substitution edges.",
                "Bridge deployment and cloud capex to demand pool without treating it as supplier exact revenue.",
                "Assess DELL AI server revenue quality through margin, cash flow and working-capital implications.",
                "Map supply-chain dependencies and bottlenecks from GPU to foundry/packaging/HBM/semicap.",
                "Separate exact facts, bounded thesis drivers, proxies and typed gaps.",
                "State counter-thesis and what evidence would change the view.",
            ],
        },
        {},
    )

    by_id = {row["question_item_id"]: row for row in rows}
    assert set(by_id) >= {
        "opening_bounded_thesis",
        "product_architecture_competitive_edges",
        "deployment_capex_demand_pool_bridge",
        "dell_ai_server_quality_margin_bridge",
        "supply_chain_bottleneck_map",
        "evidence_authority_boundary",
        "counter_thesis_what_would_change",
    }
    assert by_id["dell_ai_server_quality_margin_bridge"]["dimension"] == "fundamentals"
    assert "financial_margin_bridge" in by_id["dell_ai_server_quality_margin_bridge"]["required_evidence_roles"]
    assert "answer_contract" in by_id["counter_thesis_what_would_change"]


def test_orchestrator_memo_logic_plan_input_preserves_claim_level_roles() -> None:
    payload = _memo_logic_plan_judgment_state_input(
        {
            "judgment_state": {
                "schema_version": "sec_agent_judgment_state_v0.1",
                "dimension_judgments": [{"dimension_id": "capital_and_financing", "claim_ids": ["claim_msft_capex"]}],
            },
            "supported_claims": [
                {
                    "claim_id": "claim_msft_capex",
                    "ticker_scope": ["MSFT"],
                    "metric_scope": ["financial_metric:capex"],
                    "economic_role": "customer_or_demand_side_capex_signal",
                    "role_boundary": "capex_peer_context_not_supplier_revenue_or_order",
                }
            ],
        }
    )

    assert payload["dimension_judgments"][0]["dimension_id"] == "capital_and_financing"
    assert payload["supported_claims"][0]["economic_role"] == "customer_or_demand_side_capex_signal"
