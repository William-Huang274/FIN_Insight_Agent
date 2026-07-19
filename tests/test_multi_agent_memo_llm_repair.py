from __future__ import annotations

import json
from typing import Any

from sec_agent.langgraph_orchestrator import (
    _judgment_with_product_bridge_claims,
    _node_multi_agent_renderer,
    _render_memo_answer,
    _with_projected_specialist_input_pack,
    build_multi_agent_orchestration_graph,
    make_multi_agent_smoke_state,
)
from sec_agent.memo_llm import (
    MEMO_ROUTE_SOURCE,
    MEMO_ROUTER_ENV,
    MemoLLMConfig,
    _compact_judgment_for_memo,
    _compact_memo_logic_plan,
    _compact_memo_logic_plan_for_writer_prompt,
    _compact_shared_memo_context_for_prompt,
    _compact_supervising_analyst_pack,
    _complete_memo_contract_from_judgment,
    _memo_profile_spec_from_name,
    _memo_writer_budget_spec_from_profile,
    _verifier_minimal_projection,
    _select_memo_supported_claims,
    _salvage_action_items,
    _salvage_direct_claim_sentence,
    _unknown_numeric_tokens as _memo_unknown_numeric_tokens,
    build_shared_memo_context,
    extract_json_object,
    memo_writer_from_env,
    _localize_dimension_analyses,
    _normalize_zh_punctuation,
    route_memo_writer_llm,
    route_verifier_llm,
    _zh_salvage_claim_summary,
    verifier_from_env,
)
from sec_agent.multi_agent_contracts import (
    aggregate_focused_answer_judgment_plan,
    aggregate_specialist_judgment_plan,
    refresh_judgment_plan_after_governance_filter,
    repair_multi_agent_memo_draft,
    verify_multi_agent_memo_draft,
)


def test_mock_specialist_route_projects_role_specific_input_fingerprint(tmp_path) -> None:
    state = make_multi_agent_smoke_state(
        user_query="分析 NVDA 产品与供应链证据",
        output_dir=tmp_path,
        focus_tickers=["NVDA"],
        search_scope_tickers=["NVDA", "AMD"],
    )
    state["agent_activation_plan"] = {
        "execution_mode": "deep_research",
        "focus_tickers": ["NVDA"],
        "search_scope_tickers": ["NVDA", "AMD"],
        "activate_agents": ["product_technology_analyst"],
    }
    state["context_rows"] = [
        {
            "evidence_ref": "official_product_surface::NVDA::H100",
            "ticker": "NVDA",
            "summary": "NVIDIA H100 product page identifies the accelerator product family.",
            "source_family": "official_product_surface",
            "memo_slot": "product_technology",
        }
    ]

    route = _with_projected_specialist_input_pack(
        {"agent_id": "product_technology_analyst", "status": "run"},
        state,
    )

    fingerprint = route["input_pack_fingerprint"]
    assert route["input_projection_source"] == "deterministic_mock_projected_specialist_request"
    assert fingerprint["schema_version"] == "sec_agent_specialist_input_pack_fingerprint_v0_1"
    assert fingerprint["capture_source"] == "deterministic_mock_projected_specialist_request"
    assert fingerprint["agent_id"] == "product_technology_analyst"
    assert fingerprint["component_summaries"]["bounded_evidence_rows"]["item_count"] >= 1
    assert fingerprint["approx_prompt_payload_chars"] > 0


def test_stub_memo_and_verifier_routes_persist_input_fingerprints(tmp_path) -> None:
    graph = build_multi_agent_orchestration_graph()
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="分析 NVDA 产品、财务和供应链证据。",
            output_dir=tmp_path,
            focus_tickers=["NVDA"],
            search_scope_tickers=["NVDA", "AMD"],
        ),
        config={"configurable": {"thread_id": "unit-stub-memo-verifier-fingerprint"}},
    )

    memo_fp = result["memo_route_result"]["input_pack_fingerprint"]
    verifier_fp = result["claim_verification"]["verifier_input_projection"]["input_pack_fingerprint"]
    summary_routes = result["multi_agent_summary"]["llm_routes"]

    assert memo_fp["agent_id"] == "memo_writer"
    assert memo_fp["capture_source"] == "deterministic_stub_using_memo_writer_input_contract"
    assert memo_fp["approx_prompt_payload_chars"] > 0
    assert "raw_prompt" not in json.dumps(memo_fp, ensure_ascii=False)
    assert verifier_fp["agent_id"] == "verifier"
    assert verifier_fp["capture_source"] == "deterministic_stub_using_verifier_projection_contract"
    assert verifier_fp["approx_prompt_payload_chars"] > 0
    assert summary_routes["memo_writer"]["route_result"]["input_pack_fingerprint"]["agent_id"] == "memo_writer"
    assert summary_routes["verifier"]["input_projection"]["input_pack_fingerprint"]["agent_id"] == "verifier"


def test_memo_writer_prompt_projection_compacts_supervising_and_shared_context() -> None:
    compact_pack = _compact_supervising_analyst_pack(
        {
            "product_bridge_pack": {
                "company_disclosed_product_kpis": [
                    {
                        "ticker": "NVDA",
                        "metric_family": f"metric_{idx}",
                        "product_or_segment": f"platform_{idx}",
                        "period_key": "FY2026",
                        "display_value": "" if idx == 0 else f"value_{idx}",
                        "evidence_refs": [f"ref_{idx}", f"ref_extra_{idx}"],
                    }
                    for idx in range(6)
                ],
                "official_product_context": [
                    {
                        "claim_id": "",
                        "ticker_scope": ["NVDA", "AMD", "INTC", "GOOGL", "MSFT"],
                        "products_or_platforms": ["H100", "H200", "B200", "GB200"],
                        "claim_boundary": "official product context " * 8,
                    }
                    for _ in range(6)
                ],
                "coverage": {
                    "has_product_intelligence_graph": True,
                    "has_customer_deployment_signal": True,
                    "has_official_context_without_exact_kpi": True,
                    "product_evidence_depth_status_counts": {"exact_ready": 3, "proxy_ready": 7},
                    "product_evidence_layer_status_counts": {
                        "product_profile": {"ready": True},
                        "customer_deployment": {"ready": True},
                        "exact_product_kpi": {"ready": False},
                    },
                    "gap_count": 11,
                },
            },
            "research_lead_synthesis_plan": {
                "core_judgment": "core " * 120,
                "argument_order": [{"dimension_id": f"d{idx}", "purpose": "purpose " * 30} for idx in range(6)],
                "proven": [f"proven {idx} " * 15 for idx in range(5)],
                "supported_inference": [f"inference {idx} " * 15 for idx in range(5)],
                "not_proven": [f"not proven {idx} " * 15 for idx in range(5)],
                "writer_directives": [f"directive {idx} " * 15 for idx in range(6)],
            },
            "supervision_findings": {
                "findings": [{"type": "gap", "owner_agent": "product", "message": "message " * 50} for _ in range(6)],
                "required_followups": [
                    {"owner_agent": "product", "action": "inspect customer deployment " * 10},
                    {"owner_agent": "product", "action": "inspect customer deployment " * 10},
                    {"owner_agent": "market", "action": "inspect demand proxy " * 10},
                ],
            },
        }
    )

    product_pack = compact_pack["product_bridge_pack"]
    assert len(product_pack["company_disclosed_product_kpis"]) == 3
    assert product_pack["company_disclosed_product_kpis"][0]["display_value"] == "value_1"
    assert "evidence_refs" not in json.dumps(compact_pack, ensure_ascii=False)
    assert len(product_pack["official_product_context"]) == 3
    assert product_pack["coverage"]["exact_ready_count"] == 3
    assert product_pack["coverage"]["proxy_ready_count"] == 7
    assert "product_evidence_layer_status_counts" not in product_pack["coverage"]
    assert len(compact_pack["research_lead_synthesis_plan"]["argument_order"]) == 4
    assert len(compact_pack["supervision_findings"]["findings"]) == 3
    assert len(compact_pack["supervision_findings"]["required_followups"]) == 2

    shared = _compact_shared_memo_context_for_prompt(
        {
            "schema_version": "shared",
            "lead_review": {
                "memo_directive": {
                    "memo_stance": "answer_first",
                    "objective_satisfaction": {
                        "status": "partial",
                        "missing_required_item_count": 1,
                        "verbose_debug_rows": ["x"] * 20,
                    },
                    "gap_budget_policy": {
                        "max_gap_share_in_user_memo": 0.25,
                        "allowed_gap_placement": "after_judgment",
                        "internal_debug_policy": "drop me",
                    },
                    "product_output_contract": {
                        "required_user_facing_shape": ["profile", "spec", "deployment", "relationship", "extra"],
                        "missing_source_boundary": "boundary " * 40,
                        "forbidden_fallback": "fallback " * 40,
                    },
                    "issuer_targeted_repair_required": True,
                    "issuer_targeted_repair_tickers": ["ASML", "LRCX", "AMAT", "KLAC", "NVDA", "AMD", "INTC"],
                    "lead_targeted_repair_result": {"raw_rows": ["drop"]},
                },
                "supervising_analyst": {"status": "pass", "stance": "mixed", "core_judgment": "judgment " * 80},
            },
            "prompt_policy": {
                "shared_context_policy": "scope_only",
                "memo_payload_policy": "skeleton_first",
                "allowed_input_views": ["shared_memo_context", "supervising_analyst_pack"],
                "raw_evidence_rows": "excluded",
                "bounded_gap_policy": "bounded only",
            },
        }
    )

    serialized = json.dumps(shared, ensure_ascii=False)
    assert "allowed_input_views" not in serialized
    assert "verbose_debug_rows" not in serialized
    assert "lead_targeted_repair_result" not in serialized
    assert len(shared["lead_review"]["issuer_targeted_repair_tickers"]) == 6


def test_memo_claim_selection_skips_official_issuer_source_coverage_when_better_claims_exist() -> None:
    claims = [
        {
            "claim_id": "lead_targeted_repair_claim:issuer_official:amzn:test",
            "claim": (
                "AMZN targeted web repair reached official issuer sources. This supports issuer coverage and "
                "disclosure-path analysis, but it does not promote exact sales, orders, backlog, shipments, share, ASP, or inventory values."
            ),
            "claim_type": "official_issuer_context",
            "ticker_scope": ["AMZN"],
            "metric_scope": ["issuer_official_context", "issuer identity", "filing coverage"],
            "memo_slot": "fundamentals",
            "analysis_dimension": "fundamentals",
            "source_families": ["live_public_web_context"],
            "evidence_refs": ["official_issuer:amzn"],
            "claim_rank_score": 95,
            "memo_readiness": "memo_ready",
        },
        {
            "claim_id": "amzn_capex",
            "claim": "AMZN capex supports AI infrastructure demand-pool intensity but not named supplier orders.",
            "claim_type": "company_reported_financial_fact",
            "ticker_scope": ["AMZN"],
            "metric_scope": ["financial_metric:capex"],
            "memo_slot": "fundamentals",
            "analysis_dimension": "capital_and_financing",
            "source_families": ["primary_sec_filing"],
            "evidence_refs": ["amzn_capex_ref"],
            "claim_rank_score": 80,
        },
        {
            "claim_id": "dell_margin",
            "claim": "DELL gross margin evidence anchors AI server quality, but mix-specific margin remains unverified.",
            "claim_type": "company_reported_financial_fact",
            "ticker_scope": ["DELL"],
            "metric_scope": ["financial_metric:gross_margin"],
            "memo_slot": "fundamentals",
            "analysis_dimension": "fundamentals",
            "source_families": ["primary_sec_filing"],
            "evidence_refs": ["dell_margin_ref"],
            "claim_rank_score": 78,
        },
    ]

    selected = _select_memo_supported_claims(
        claims,
        [{"memo_slot": "fundamentals", "status": "supported"}],
        max_claims=2,
    )

    selected_ids = {claim["claim_id"] for claim in selected}
    assert "lead_targeted_repair_claim:issuer_official:amzn:test" not in selected_ids
    assert selected_ids == {"amzn_capex", "dell_margin"}


def test_deep_research_memo_fails_short_direct_answer_and_template_surface() -> None:
    judgment = {
        "supported_claims": [
            {
                "claim_id": "amzn_capex",
                "claim": "AMZN capex supports AI infrastructure demand-pool intensity but not named supplier orders.",
                "claim_type": "company_reported_financial_fact",
                "ticker_scope": ["AMZN"],
                "metric_scope": ["financial_metric:capex"],
                "source_families": ["primary_sec_filing"],
                "evidence_refs": ["amzn_capex_ref"],
            }
        ],
        "thesis_driver_pack": {
            "dimension_sections": [
                {
                    "dimension_id": "fundamentals",
                    "section_thesis": "AMZN capex supports AI infrastructure demand-pool intensity.",
                    "business_mechanism": "Capex can indicate data-center demand.",
                    "financial_bridge": "Capex does not equal named supplier orders.",
                    "evidence_refs": ["amzn_capex_ref"],
                    "primary_claim_ids": ["amzn_capex"],
                }
            ]
        },
    }
    memo = {
        "schema_version": "sec_agent_multi_agent_memo_draft_v0.1",
        "answer_status": "draft",
        "direct_answer": "AMZN capex 是一个需求线索。",
        "memo_profile": {"profile": "deep_research"},
        "raw_rows_consumed": False,
        "tool_calls_requested": [],
        "memo_claims": [
            {
                "claim_id": "amzn_capex",
                "claim": "AMZN capex supports AI infrastructure demand-pool intensity but not named supplier orders.",
                "evidence_refs": ["amzn_capex_ref"],
            }
        ],
        "dimension_analyses": [
            {
                "dimension_id": "fundamentals",
                "summary": "AMZN capex supports AI infrastructure demand-pool intensity.",
                "business_mechanism": "Capex can indicate data-center demand.",
                "financial_bridge": "Capex does not equal named supplier orders.",
                "evidence_refs": ["amzn_capex_ref"],
                "claim_ids": ["amzn_capex"],
            }
        ],
        "investment_implications": [
            {
                "text": "基本面 / capex 只回答一个投资问题：当前披露是否已经能支撑收入、利润率或现金流传导；不能用它外推未验证的订单、份额或销量。",
                "evidence_refs": ["amzn_capex_ref"],
            }
        ],
    }

    verification = verify_multi_agent_memo_draft(memo, judgment)
    error_types = {item["type"] for item in verification["errors"]}

    assert verification["status"] == "fail"
    assert "analyst_depth_direct_answer_too_thin_for_profile" in error_types
    assert "analyst_depth_generic_template_language" in error_types


def test_memo_writer_budget_projection_removes_plan_refs_and_claim_debug_fields() -> None:
    profile = _memo_profile_spec_from_name("deep_research")
    budget = _memo_writer_budget_spec_from_profile(profile)
    long_ref = "INTERACTIVE_run_case_primary_filing_text_grouped_sec_search::AMAT::2026::revenue::" + ("x" * 120)
    compact_plan = _compact_memo_logic_plan(
        {
            "sections": [
                {
                    "section_id": f"s{idx}",
                    "title": "section",
                    "required_claim_ids": [f"claim_{idx}"],
                    "required_evidence_refs": [long_ref],
                    "writing_instruction": "Use this section to explain mechanism and bridge.",
                }
                for idx in range(8)
            ],
            "evidence_to_thesis_bridge": [
                {"dimension_id": "fundamentals", "claim_ids": ["claim_1"], "evidence_refs": [long_ref]}
                for _ in range(8)
            ],
            "economic_role_summary": {
                "role_rows": [
                    {
                        "claim_id": f"claim_{idx}",
                        "memo_use_role": "Use as issuer financial quality anchor and do not over-read it.",
                        "evidence_refs": [long_ref],
                    }
                    for idx in range(8)
                ]
            },
            "required_question_items": [{"question_item_id": f"q{idx}", "answer_contract": "answer"} for idx in range(8)],
            "required_item_answer_plan": [
                {"question_item_id": f"q{idx}", "answer_first_judgment_prompt": "state judgment"}
                for idx in range(8)
            ],
        },
        budget=budget,
    )
    compact_judgment = _compact_judgment_for_memo(
        {
            "supported_claims": [
                {
                    "claim_id": f"claim_{idx}",
                    "agent_id": "fundamental_analyst",
                    "claim": "A supported issuer fact with enough detail for writer selection.",
                    "claim_type": "company_reported_financial_fact",
                    "evidence_refs": [long_ref],
                    "analyst_depth": {"business_mechanism": "large duplicate field"},
                    "parser_diagnosis": {"exact_fact_parser_failure_reasons": ["duplicate diagnostic"]},
                }
                for idx in range(8)
            ]
        },
        memo_profile=profile,
        budget=budget,
    )

    assert long_ref not in json.dumps(compact_plan, ensure_ascii=False)
    assert len(compact_plan["sections"]) == budget.sections_cap
    assert len(compact_plan["required_item_answer_plan"]) == min(8, budget.required_item_cap)
    assert len(compact_judgment["supported_claims"]) == budget.supported_claim_cap
    assert compact_judgment["supported_claims"][0]["evidence_refs"] == [long_ref]
    assert "analyst_depth" not in compact_judgment["supported_claims"][0]
    assert "parser_diagnosis" not in compact_judgment["supported_claims"][0]


def test_memo_writer_prompt_plan_projection_removes_duplicate_thesis_path_and_judgment_cards() -> None:
    profile = _memo_profile_spec_from_name("deep_research")
    budget = _memo_writer_budget_spec_from_profile(profile)
    long_ref = "INTERACTIVE_run_case_primary_filing_text_grouped_sec_search::DELL::AI_SERVER::" + ("x" * 160)
    plan = {
        "schema_version": "finsight_memo_logic_plan_v0_1",
        "plan_id": "unit_plan",
        "memo_intent": "answer_first_deep_research",
        "answer_first_outline": {
            "schema_version": "outline_v1",
            "thesis_statement": "AI server demand improves DELL upside but margin and supply-chain transmission remain the key judgment.",
            "supporting_dimension_ids": ["product_technology", "fundamentals"],
            "decision_changing_evidence_refs": [long_ref],
            "opening_instruction": "state the judgment before gaps",
        },
        "writer_thesis_skeleton": {
            "schema_version": "thesis_v1",
            "opening_judgment": "DELL is better positioned if AI server demand translates into margin-accretive backlog.",
            "judgment_card_moves": [
                {
                    "judgment_card_id": "jc_product",
                    "source_claim_id": "claim_product",
                    "dimension_id": "product_technology",
                    "judgment": "duplicate judgment text should not be sent twice",
                    "evidence_refs": [long_ref],
                }
            ],
            "thesis_path_move": {
                "primary_thesis": "AI infrastructure demand read-through.",
                "required_sequence": [
                    {
                        "dimension_id": "product_technology",
                        "judgment_card_ids": ["jc_product"],
                        "claim_ids": ["claim_product"],
                        "business_mechanism": "duplicate mechanism field",
                        "financial_bridge": "duplicate bridge field",
                        "evidence_refs": [long_ref],
                    }
                ],
            },
        },
        "judgment_cards": [
            {
                "judgment_card_id": "jc_product",
                "source_claim_id": "claim_product",
                "dimension_id": "product_technology",
                "judgment": "Product demand exists.",
                "evidence_refs": [long_ref],
            }
        ],
        "thesis_path": {
            "status": "ready",
            "path_nodes": [{"dimension_id": "product_technology", "claim_ids": ["claim_product"], "evidence_refs": [long_ref]}],
        },
        "required_item_answer_plan": [
            {
                "question_item_id": "ai_server_margin",
                "answer_first_judgment_prompt": "Judge whether AI servers are margin accretive.",
                "evidence_bridge_prompt": "Use product, margin, and deployment evidence.",
            }
        ],
    }

    compact_full = _compact_memo_logic_plan(plan, budget=budget)
    prompt_projection = _compact_memo_logic_plan_for_writer_prompt(plan, budget=budget)
    prompt_text = json.dumps(prompt_projection, ensure_ascii=False, sort_keys=True)

    assert compact_full["judgment_cards"]
    assert compact_full["thesis_path"]
    assert "judgment_cards" not in prompt_projection
    assert "thesis_path" not in prompt_projection
    assert "judgment_card_moves" not in prompt_projection["writer_thesis_skeleton"]
    assert "required_item_answer_plan" in prompt_projection
    assert long_ref not in prompt_text
    assert prompt_projection["answer_first_outline"]["decision_changing_evidence_ref_count"] == 1
    assert prompt_projection["answer_first_outline"]["exact_ref_source"] == "verified_judgment_plan.supported_claims"
    assert prompt_projection["writer_prompt_projection_policy"].startswith("memo_logic_plan_answer_contract_only")


def test_zh_punctuation_normalization_separates_concatenated_ticker_sentence() -> None:
    text = "WMT季度收入同比增长显示稳健增长TGT 3个月相对基准跑输10个百分点。"

    normalized = _normalize_zh_punctuation(text)

    assert "增长TGT" not in normalized
    assert "增长；TGT" in normalized
    assert "来自；DELL" not in _normalize_zh_punctuation("毛利率6%直接来自；DELL 10-Q披露。")


def test_zh_salvage_claim_summary_avoids_direction_limited_template() -> None:
    summary = _zh_salvage_claim_summary(
        {
            "ticker_scope": ["DELL"],
            "memo_slot": "capital_and_financing",
            "metric_scope": ["financial_metric:capex"],
            "claim": "DELL reported capital expenditures of $0.67B.",
        }
    )

    assert "方向有限" not in summary
    assert "适合作为该维度判断的事实基础" not in summary
    assert "不能直接证明供应商订单或份额" in summary


def test_memo_numeric_fidelity_accepts_chinese_usd_yi_converted_from_usd_millions() -> None:
    unknown = _memo_unknown_numeric_tokens(
        "AMZN capex 为 -1510.03亿美元，DELL ISG 产品收入为 290.09亿美元。",
        "AMZN reported capital expenditures of -151003.0 usd_millions; DELL Total ISG net revenue was 29009.0 usd_millions.",
    )

    assert "-1510.03亿美元" not in unknown
    assert "290.09亿美元" not in unknown


def test_memo_supported_claim_selection_keeps_product_dimension_under_claim_cap() -> None:
    claims = [
        {
            "claim_id": f"capex_{index}",
            "memo_slot": "fundamentals",
            "analysis_dimension": "capital_and_financing",
            "claim": f"Capex fact {index}",
        }
        for index in range(5)
    ]
    claims.append(
        {
            "claim_id": "product_fact",
            "memo_slot": "product_technology",
            "analysis_dimension": "product_and_production",
            "claim": "DELL AI-optimized servers product revenue fact.",
        }
    )

    selected = _select_memo_supported_claims(
        claims,
        [{"memo_slot": "fundamentals", "status": "supported"}],
        max_claims=3,
    )

    assert "product_fact" in {row["claim_id"] for row in selected}


def test_memo_supported_claim_selection_prioritizes_official_product_context_over_gap_claim() -> None:
    claims = [
        {
            "claim_id": "product_gap",
            "memo_slot": "product_technology",
            "analysis_dimension": "product_and_production",
            "claim_type": "source_gap",
            "claim": "No company product evidence graph rows with runtime_fact_allowed status exist for ASML.",
            "evidence_refs": ["product_source_gap::ASML::company_product_evidence_graph"],
            "source_families": ["company_product_evidence_graph"],
            "claim_rank_score": 95,
        },
        {
            "claim_id": "asml_official_product_context",
            "memo_slot": "product_technology",
            "analysis_dimension": "product_and_production",
            "claim_type": "product_taxonomy_context",
            "claim": "ASML official-source repair reached issuer sources and identified EUV and DUV product-surface leads.",
            "evidence_refs": ["official_asml:product_surface:euv"],
            "source_families": ["live_public_web_context"],
            "metric_scope": ["product_surface_context", "net bookings", "backlog"],
            "ticker_scope": ["ASML"],
            "claim_rank_score": 72,
            "memo_readiness": "memo_ready",
        },
    ]

    selected = _select_memo_supported_claims(
        claims,
        [{"memo_slot": "product_technology", "status": "supported"}],
        max_claims=1,
    )

    assert [row["claim_id"] for row in selected] == ["asml_official_product_context"]


def test_memo_supported_claim_selection_prioritizes_exact_product_fact_over_negative_context() -> None:
    claims = [
        {
            "claim_id": "dell_negative_product_context",
            "memo_slot": "product_technology",
            "analysis_dimension": "product_and_production",
            "claim_type": "business_observation",
            "claim": "DELL's product taxonomy is visible, but no runtime facts confirm AI-optimized server revenue or ISG performance.",
            "evidence_refs": ["company_product_evidence_graph:DELL:scope_hypothesis"],
            "source_families": ["company_product_evidence_graph"],
            "metric_scope": ["product_context"],
            "ticker_scope": ["DELL"],
            "claim_rank_score": 99,
            "memo_readiness": "memo_ready",
        },
        {
            "claim_id": "dell_isg_product_revenue",
            "memo_slot": "product_technology",
            "analysis_dimension": "product_and_production",
            "claim_type": "company_reported_product_operating_fact",
            "claim": "DELL reported ISG revenue and AI-optimized server revenue, giving a product-level operating bridge for AI server exposure.",
            "evidence_refs": ["sec_product_kpi:DELL:ISG:AI_server_revenue"],
            "source_families": ["primary_sec_filing"],
            "metric_scope": ["product_kpi:product_revenue", "segment_revenue", "AI-optimized server"],
            "ticker_scope": ["DELL"],
            "display_value": "$16.1B AI-optimized server annual revenue",
            "claim_rank_score": 70,
            "memo_readiness": "memo_ready",
        },
    ]

    selected = _select_memo_supported_claims(
        claims,
        [{"memo_slot": "product_technology", "status": "supported"}],
        max_claims=1,
    )

    assert [row["claim_id"] for row in selected] == ["dell_isg_product_revenue"]


def test_salvage_public_proxy_without_role_is_not_rendered_as_product_revenue() -> None:
    public_proxy_claim = {
        "claim_id": "lead_targeted_repair_claim:product_surface:amzn",
        "memo_slot": "product_technology",
        "analysis_dimension": "product_and_production",
        "claim_type": "product_taxonomy_context",
        "claim": "AMZN official product surface identified AWS revenue, operating income, and capital expenditures context.",
        "metric_scope": ["product_surface_context", "AWS revenue", "operating income", "capital expenditures"],
        "ticker_scope": ["AMZN"],
        "evidence_refs": ["official_product_surface:AMZN:AWS"],
        "source_families": ["live_public_web_context"],
        "claim_rank_score": 99,
        "memo_readiness": "memo_ready",
    }

    sentence = _salvage_direct_claim_sentence(public_proxy_claim, response_language="zh-CN")

    assert "只能说明公开产品页、官方页面或外部 proxy" in sentence
    assert "产品收入" in sentence
    assert "供应商订单" in sentence
    assert "承接需求" not in sentence
    assert "供应商端已有产品收入" not in sentence


def test_memo_supported_claim_selection_demotes_unroled_public_proxy_below_exact_role_fact() -> None:
    claims = [
        {
            "claim_id": "lead_targeted_repair_claim:product_surface:amzn",
            "memo_slot": "product_technology",
            "analysis_dimension": "product_and_production",
            "claim_type": "product_taxonomy_context",
            "claim": "AMZN official product surface identified AWS revenue and operating income context.",
            "metric_scope": ["product_surface_context", "AWS revenue", "operating income"],
            "ticker_scope": ["AMZN"],
            "evidence_refs": ["official_product_surface:AMZN:AWS"],
            "source_families": ["live_public_web_context"],
            "claim_rank_score": 99,
            "memo_readiness": "memo_ready",
        },
        {
            "claim_id": "dell_isg_product_revenue",
            "memo_slot": "product_technology",
            "analysis_dimension": "product_and_production",
            "claim_type": "company_reported_product_operating_fact",
            "claim": "DELL reported ISG revenue and AI-optimized server revenue.",
            "metric_scope": ["product_kpi:product_revenue", "segment_revenue", "AI-optimized server"],
            "ticker_scope": ["DELL"],
            "evidence_refs": ["sec_product_kpi:DELL:ISG:AI_server_revenue"],
            "source_families": ["primary_sec_filing"],
            "economic_role": "issuer_product_revenue_signal",
            "claim_rank_score": 60,
            "memo_readiness": "memo_ready",
        },
    ]

    selected = _select_memo_supported_claims(
        claims,
        [{"memo_slot": "product_technology", "status": "supported"}],
        max_claims=1,
    )

    assert [row["claim_id"] for row in selected] == ["dell_isg_product_revenue"]


def test_memo_supported_claim_selection_keeps_cross_ticker_capex_facts_before_context_fillers() -> None:
    claims = [
        {
            "claim_id": "dell_product",
            "memo_slot": "product_technology",
            "analysis_dimension": "product_and_production",
            "claim_type": "company_reported_product_operating_fact",
            "claim": "DELL reported ISG product revenue.",
            "metric_scope": ["product_kpi:product_revenue"],
            "ticker_scope": ["DELL"],
            "evidence_refs": ["dell_product_ref"],
            "source_families": ["primary_sec_filing"],
            "claim_rank_score": 95,
        },
        {
            "claim_id": "dell_margin",
            "memo_slot": "fundamentals",
            "analysis_dimension": "fundamentals",
            "claim_type": "company_reported_financial_fact",
            "claim": "DELL reported gross margin.",
            "metric_scope": ["financial_metric:gross_margin"],
            "ticker_scope": ["DELL"],
            "evidence_refs": ["dell_margin_ref"],
            "source_families": ["primary_sec_filing"],
            "claim_rank_score": 90,
        },
        {
            "claim_id": "dell_contract_context",
            "memo_slot": "industry_relationship",
            "analysis_dimension": "industry_supply_chain",
            "claim_type": "industry_context_only",
            "claim": "DELL has public contract award context.",
            "metric_scope": ["public_contract_award"],
            "ticker_scope": ["DELL"],
            "evidence_refs": ["dell_contract_ref"],
            "source_families": ["public_source_context"],
            "claim_rank_score": 88,
        },
        {
            "claim_id": "market_context",
            "memo_slot": "market_valuation",
            "analysis_dimension": "competition_and_market_position",
            "claim_type": "market_context",
            "claim": "AMZN, GOOGL and MSFT market reactions diverged.",
            "metric_scope": ["market_reaction"],
            "ticker_scope": ["AMZN", "GOOGL", "MSFT"],
            "evidence_refs": ["market_ref"],
            "source_families": ["market_snapshot"],
            "claim_rank_score": 86,
        },
        {
            "claim_id": "amzn_capex",
            "memo_slot": "capital_allocation",
            "analysis_dimension": "capital_and_financing",
            "claim_type": "company_reported_financial_fact",
            "claim": "AMZN reported capital expenditure cash outflow/proxy.",
            "metric_scope": ["financial_metric:capex"],
            "ticker_scope": ["AMZN"],
            "evidence_refs": ["amzn_capex_ref"],
            "source_families": ["primary_sec_filing"],
            "claim_rank_score": 80,
        },
        {
            "claim_id": "googl_capex",
            "memo_slot": "capital_allocation",
            "analysis_dimension": "capital_and_financing",
            "claim_type": "company_reported_financial_fact",
            "claim": "GOOGL reported capital expenditure cash outflow/proxy.",
            "metric_scope": ["financial_metric:capex"],
            "ticker_scope": ["GOOGL"],
            "evidence_refs": ["googl_capex_ref"],
            "source_families": ["primary_sec_filing"],
            "claim_rank_score": 79,
        },
        {
            "claim_id": "msft_capex",
            "memo_slot": "capital_allocation",
            "analysis_dimension": "capital_and_financing",
            "claim_type": "company_reported_financial_fact",
            "claim": "MSFT reported capital expenditures.",
            "metric_scope": ["financial_metric:capex"],
            "ticker_scope": ["MSFT"],
            "evidence_refs": ["msft_capex_ref"],
            "source_families": ["primary_sec_filing"],
            "claim_rank_score": 78,
        },
        {
            "claim_id": "nvda_margin",
            "memo_slot": "fundamentals",
            "analysis_dimension": "fundamentals",
            "claim_type": "company_reported_financial_fact",
            "claim": "NVDA reported gross margin.",
            "metric_scope": ["financial_metric:gross_margin"],
            "ticker_scope": ["NVDA"],
            "evidence_refs": ["nvda_margin_ref"],
            "source_families": ["primary_sec_filing"],
            "claim_rank_score": 77,
        },
    ]

    selected = _select_memo_supported_claims(
        claims,
        [{"memo_slot": "product_technology", "status": "supported"}],
        max_claims=8,
    )

    selected_ids = {row["claim_id"] for row in selected}
    assert {"amzn_capex", "googl_capex", "msft_capex"} <= selected_ids
    assert "nvda_margin" in selected_ids


def test_salvage_action_items_are_dimension_specific_not_generic_template() -> None:
    items = _salvage_action_items(
        [
            {
                "claim_id": "product_fact",
                "analysis_dimension": "product_and_production",
                "ticker_scope": ["DELL"],
                "metric_scope": ["product_kpi:product_revenue"],
                "evidence_refs": ["dell_product_ref"],
            }
        ],
        response_language="zh-CN",
        kind="monitoring_items",
        max_items=1,
    )

    assert "用该补充论据交叉验证核心判断" not in items[0]["text"]
    assert "DELL" in items[0]["text"]
    assert "产品与产线" in items[0]["text"]


def test_salvage_action_items_do_not_dump_relationship_graph_peer_tickers() -> None:
    items = _salvage_action_items(
        [
            {
                "claim_id": "relationship_fact",
                "analysis_dimension": "industry_supply_chain",
                "ticker_scope": ["ASML", "DELL", "HPE", "SMCI"],
                "metric_scope": ["capital expenditures", "orders_backlog"],
                "source_families": ["relationship_graph"],
                "evidence_refs": ["sector_depth_pack:technology_ai_infrastructure_depth:LRCX"],
            }
        ],
        response_language="zh-CN",
        kind="investment_implications",
        max_items=1,
    )

    assert "ASML 相关行业关系图" in items[0]["text"]
    assert "DELL" not in items[0]["text"]
    assert "HPE" not in items[0]["text"]


def test_zh_gap_only_dimension_localization_avoids_english_fallback_template() -> None:
    rows = _localize_dimension_analyses(
        [
            {
                "dimension_id": "product_and_production",
                "status": "gap_or_counterevidence",
                "summary": "Bounded evidence contains only product_source_gap rows; no company_product_evidence_graph rows are present.",
                "business_mechanism": "The evidence links product adoption, capacity, units, backlog, usage, or product mix to the operating line being evaluated.",
                "financial_bridge": "Bridge product evidence to revenue, margin, inventory, capacity, or backlog only when the verified ClaimCard states the metric.",
            }
        ]
    )

    assert "当前产品/产线维度只有公开证据缺口" in rows[0]["summary"]
    assert "Bounded evidence" not in rows[0]["summary"]
    assert "exact-authority" in rows[0]["financial_bridge"]


def test_standard_memo_renderer_surfaces_more_than_five_dimensions() -> None:
    memo = {
        "response_language": {"language": "zh-CN"},
        "memo_profile": {"profile": "standard"},
        "direct_answer": "有边界的核心判断。",
        "dimension_analyses": [
            {
                "dimension_id": dimension_id,
                "title": title,
                "summary": f"{title} 有可追踪分析。",
                "claim_ids": [f"claim_{index}"],
            }
            for index, (dimension_id, title) in enumerate(
                [
                    ("fundamentals", "基本面"),
                    ("product_and_production", "产品"),
                    ("capital_and_financing", "资本"),
                    ("competition_and_market_position", "竞争"),
                    ("industry_supply_chain", "行业"),
                    ("risk_and_counterevidence", "风险"),
                ],
                start=1,
            )
        ],
    }

    rendered = _render_memo_answer(memo, bounded=False)

    assert "6. 风险" in rendered


def test_memo_renderer_filters_internal_thesis_synthesis_dimension() -> None:
    memo = {
        "response_language": {"language": "zh-CN"},
        "memo_profile": {"profile": "standard"},
        "direct_answer": "有边界的核心判断。",
        "dimension_analyses": [
            {
                "dimension_id": "thesis_synthesis",
                "title": "Synthesis",
                "summary": "primary_sec_filing",
                "claim_ids": ["internal_claim"],
            },
            {
                "dimension_id": "fundamentals",
                "title": "基本面",
                "summary": "基本面事实有可追踪证据。",
                "evidence_refs": ["ref_1"],
            },
        ],
    }

    rendered = _render_memo_answer(memo, bounded=False)

    assert "Synthesis" not in rendered
    assert "primary_sec_filing" not in rendered
    assert "基本面事实" in rendered


def test_memo_renderer_drops_english_template_sentences_in_chinese_surface() -> None:
    memo = {
        "response_language": {"language": "zh-CN"},
        "memo_profile": {"profile": "standard"},
        "direct_answer": "结论先落在已披露链条上：DELL 产品收入支撑 AI 服务器需求传导。",
        "dimension_analyses": [
            {
                "dimension_id": "product_and_production",
                "title": "产品与产线",
                "summary": "DELL AI 优化服务器收入可作为产品传导的公司披露锚点。",
                "business_mechanism": "The evidence supports or pressures earnings power through reported growth.",
                "financial_bridge": "Caveat: Non-GAAP measure; GAAP gross margin not directly provided.",
                "counter_read": "Missing confirmation: company-reported orders/backlog are absent.",
                "evidence_refs": ["dell_product_ref"],
            }
        ],
        "memo_claims": [
            {
                "claim": "DELL AI 优化服务器收入可作为产品传导的公司披露锚点。",
                "evidence_refs": ["dell_product_ref"],
            }
        ],
    }

    rendered = _render_memo_answer(memo, bounded=False)

    assert "DELL AI 优化服务器收入" in rendered
    assert "The evidence supports" not in rendered
    assert "Caveat:" not in rendered
    assert "Missing confirmation:" not in rendered
    assert "[C1]" in rendered


def test_memo_renderer_hides_inline_internal_refs_and_metric_ids() -> None:
    memo = {
        "response_language": {"language": "zh-CN"},
        "memo_profile": {"profile": "standard"},
        "direct_answer": "结论先落在已披露链条上。",
        "memo_claims": [
            {
                "claim": (
                    "KLAC 的产品与产线证据涉及 product_kpi:product_revenue；"
                    "可对应 KLAC_2026_10Q_ITEM2_BLOCK_0005_PART_02_OF_02::METRIC_TABLE_B4EF38DE；"
                    "AMAT 涉及 financial_metric:capex。"
                ),
                "evidence_refs": ["klac_ref", "amat_ref"],
            }
        ],
    }

    rendered = _render_memo_answer(memo, bounded=False)

    assert "product_kpi:" not in rendered
    assert "financial_metric:" not in rendered
    assert "KLAC_2026" not in rendered
    assert "METRIC_TABLE" not in rendered
    assert "产品收入" in rendered
    assert "资本开支" in rendered
    assert "[C1]" in rendered


def test_deep_memo_renderer_keeps_short_claim_audit_section_with_dimension_surface() -> None:
    memo = {
        "response_language": {"language": "zh-CN"},
        "memo_profile": {"profile": "deep_research"},
        "direct_answer": "当前判断更偏向产品和财务分层验证。",
        "dimension_analyses": [
            {"dimension_id": "fundamentals", "summary": "AMAT 毛利率支撑盈利质量判断。", "evidence_refs": ["amat_margin"]},
            {"dimension_id": "product_and_production", "summary": "KLAC 产品收入支撑过程控制业务规模判断。", "evidence_refs": ["klac_product"]},
            {"dimension_id": "capital_and_financing", "summary": "发行人自身 capex 不能等同客户订单。", "evidence_refs": ["amat_capex"]},
        ],
        "memo_claims": [
            {
                "claim": "KLAC reported product 收入 of $7B in fiscal:2026:Q3:qtd.",
                "evidence_refs": ["klac_product"],
            }
        ],
    }

    rendered = _render_memo_answer(memo, bounded=False)

    assert "分维度分析" in rendered
    assert "关键论据" in rendered
    assert "reported product" not in rendered
    assert "fiscal:2026" not in rendered
    assert "KLAC 产品收入" in rendered


def test_salvage_direct_answer_tail_is_judgment_frame_not_internal_instruction() -> None:
    rendered = _render_memo_answer(
        {
            "response_language": {"language": "zh-CN"},
            "memo_profile": {"profile": "deep_research"},
            "direct_answer": "投资判断应先区分客户/需求侧 capex、供应商自身 capex、产品收入/订单与毛利锚点，再判断供应链传导是否被客户部署、订单或利润质量证据验证。",
            "dimension_analyses": [
                {"dimension_id": "fundamentals", "summary": "AMAT 毛利率支撑盈利质量判断。", "evidence_refs": ["amat_margin"]},
                {"dimension_id": "product_and_production", "summary": "KLAC 产品收入支撑过程控制业务规模判断。", "evidence_refs": ["klac_product"]},
                {"dimension_id": "capital_and_financing", "summary": "发行人自身 capex 不能等同客户订单。", "evidence_refs": ["amat_capex"]},
            ],
        },
        bounded=False,
    )

    assert "投资判断应先" not in rendered


def test_required_item_projection_uses_user_facing_evidence_phrase() -> None:
    rendered = _render_memo_answer(
        {
            "response_language": {"language": "zh-CN"},
            "memo_profile": {"profile": "deep_research"},
            "direct_answer": "当前判断集中在财务、产品和供应链传导。",
            "dimension_analyses": [
                {"dimension_id": "fundamentals", "summary": "AMAT 毛利率支撑盈利质量判断。", "evidence_refs": ["amat_margin"]},
                {"dimension_id": "product_and_production", "summary": "KLAC 产品收入支撑过程控制业务规模判断。", "evidence_refs": ["klac_product"]},
                {"dimension_id": "capital_and_financing", "summary": "发行人自身 capex 不能等同客户订单。", "evidence_refs": ["amat_capex"]},
            ],
            "memo_claims": [
                {
                    "claim": "出口限制风险方向明确，但缺地区收入和许可证状态披露。",
                    "evidence_refs": ["export_risk"],
                    "claim_type": "risk_context",
                    "source_family": "official_disclosure",
                }
            ],
            "memo_logic_plan": {
                "required_item_answer_plan": [
                    {
                        "question_item_id": "export_restriction_context",
                        "dimension": "risk_counter_thesis",
                        "terms_any": ["export restriction", "出口限制"],
                        "required_evidence_roles": ["risk_context"],
                    }
                ]
            },
        },
        bounded=False,
    )

    assert "关键问题回应" in rendered
    assert "当前可确认的是" in rendered
    assert "证据锚点" not in rendered
    assert "artifact" not in rendered.lower()


def test_zh_salvage_claim_summary_hides_internal_metric_ids_and_evidence_refs() -> None:
    summary = _zh_salvage_claim_summary(
        {
            "ticker_scope": ["KLAC"],
            "metric_scope": ["product_kpi:product_revenue", "financial_metric:capex"],
            "memo_slot": "product_technology",
            "direction": "positive",
            "materiality": "high",
            "claim": "KLAC product revenue was 23% in 2025.",
            "evidence_refs": [
                "INTERACTIVE_20260702_case::KLAC_2026_10Q_ITEM2_BLOCK_0005_PART_02_OF_02::METRIC_TABLE_B4EF38DE"
            ],
        }
    )

    assert "产品收入" in summary
    assert "资本开支" in summary
    assert "23%" in summary
    assert "product_kpi:" not in summary
    assert "financial_metric:" not in summary
    assert "INTERACTIVE_" not in summary
    assert "BLOCK_0005" not in summary


def test_repair_multi_agent_memo_removes_raw_tool_and_bad_claims() -> None:
    judgment = _judgment()
    bad_memo = {
        "answer_status": "draft",
        "direct_answer": "Supported capex claim. Unsupported customer claim.",
        "raw_rows_consumed": True,
        "tool_calls_requested": [{"tool": "sec_search_filings"}],
        "memo_claims": [
            {"claim": "Supported capex claim.", "evidence_refs": ["capex_ref"], "source_families": ["primary_sec_filing"]},
            {"claim": "No refs claim."},
        ],
    }
    verification = verify_multi_agent_memo_draft(bad_memo, judgment)

    repaired = repair_multi_agent_memo_draft(bad_memo, verification, judgment)
    repaired_verification = verify_multi_agent_memo_draft(repaired, judgment)

    assert repaired["raw_rows_consumed"] is False
    assert repaired["tool_calls_requested"] == []
    assert repaired["removed_claims"][0]["reason"] == "missing_evidence_refs"
    assert repaired_verification["status"] == "pass"


def test_graph_verifier_repairs_once_then_reverifies(tmp_path) -> None:
    def injected_specialists(_state: dict) -> dict:
        return {
            "specialist_outputs": [
                {
                    "agent_id": "fundamental_analyst",
                    "observations": [
                        {
                            "claim": "Supported capex claim.",
                            "evidence_refs": ["capex_ref"],
                            "source_families": ["primary_sec_filing"],
                        }
                    ],
                }
            ]
        }

    def bad_memo(_state: dict) -> dict:
        return {
            "memo_answer": {
                "answer_status": "draft",
                "direct_answer": "Supported capex claim.",
                "raw_rows_consumed": True,
                "tool_calls_requested": [{"tool": "sec_search_filings"}],
                "memo_claims": [
                    {"claim": "Supported capex claim.", "evidence_refs": ["capex_ref"], "source_families": ["primary_sec_filing"]}
                ],
            }
        }

    graph = build_multi_agent_orchestration_graph(run_specialist_analysts=injected_specialists, memo_writer=bad_memo)
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="写一段投研 memo，比较 NVDA 和 AMD 的基本面。",
            output_dir=tmp_path,
            query_contract=_query_contract(["NVDA", "AMD"]),
            focus_tickers=["NVDA", "AMD"],
            search_scope_tickers=["NVDA", "AMD"],
        ),
        config={"configurable": {"thread_id": "unit-verifier-repair"}},
    )

    assert result["claim_verification"]["status"] == "pass"
    assert result["claim_verification"]["repair"]["status"] == "pass"
    assert result["memo_answer"]["verifier_repair_attempted"] is True
    assert result["memo_answer"]["tool_calls_requested"] == []


def test_graph_renderer_surfaces_memo_claims_and_evidence_refs(tmp_path) -> None:
    def injected_specialists(_state: dict) -> dict:
        return {
            "specialist_outputs": [
                {
                    "agent_id": "fundamental_analyst",
                    "observations": [
                        {
                            "claim": "Supported capex claim.",
                            "evidence_refs": ["capex_ref"],
                            "source_families": ["primary_sec_filing"],
                        }
                    ],
                }
            ]
        }

    def memo_writer(_state: dict) -> dict:
        return {
            "memo_answer": {
                "answer_status": "draft",
                "direct_answer": "Supported capex claim.",
                "raw_rows_consumed": False,
                "tool_calls_requested": [],
                "memo_claims": [
                    {
                        "claim_id": "claim_capex",
                        "claim": "Supported capex claim.",
                        "evidence_refs": ["capex_ref"],
                        "source_families": ["primary_sec_filing"],
                    }
                ],
                "caveats": [{"text": "Scope is bounded to verified claim cards."}],
                "source_boundary": "verified ClaimCards only",
            }
        }

    graph = build_multi_agent_orchestration_graph(run_specialist_analysts=injected_specialists, memo_writer=memo_writer)
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="写一段投研 memo，比较 NVDA 和 AMD 的基本面。",
            output_dir=tmp_path,
            query_contract=_query_contract(["NVDA", "AMD"]),
            focus_tickers=["NVDA", "AMD"],
            search_scope_tickers=["NVDA", "AMD"],
        ),
        config={"configurable": {"thread_id": "unit-renderer-claims"}},
    )

    rendered = result["rendered_answer"]
    assert "Core thesis:" in rendered
    assert "Key memo claims:" in rendered
    assert "[C1]" in rendered
    assert "refs=capex_ref" not in rendered
    assert "Evidence index:" in rendered
    assert "Caveats:" in rendered
    assert "Source boundary: verified ClaimCards only" in rendered
    rendered_ref = result["artifact_refs"]["rendered_answer"].replace("\\", "/")
    assert rendered_ref.endswith("qwen/rendered_answer.md")
    assert (tmp_path / "qwen" / "rendered_answer.md").exists()
    assert (tmp_path / "memo_answer.json").exists()
    assert (tmp_path / "verified_judgment_plan.json").exists()
    assert (tmp_path / "claim_cards.json").exists()
    assert (tmp_path / "thesis_driver_pack.json").exists()


def test_memo_writer_llm_accepts_valid_memo_json() -> None:
    fake = _FakeChat([json.dumps(_memo())])

    result = route_memo_writer_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["memo_route_result"]["status"] == "pass", result["memo_route_result"]
    assert result["memo_route_result"]["finish_reasons"] == ["stop"]
    assert result["memo_answer"]["llm_route_source"] == MEMO_ROUTE_SOURCE
    assert result["memo_answer"]["raw_rows_consumed"] is False
    assert result["memo_answer"]["memo_outline"]
    assert "Memo Writer Skill" in fake.calls[0]["messages"][0]["content"]
    assert "ClaimCard" in fake.calls[0]["messages"][1]["content"]
    assert "memo_outline" in fake.calls[0]["messages"][1]["content"]
    assert "memo_thesis_plan" in fake.calls[0]["messages"][1]["content"]
    assert "memo_thesis_pack" in fake.calls[0]["messages"][1]["content"]
    assert "thesis_driver_pack" in fake.calls[0]["messages"][1]["content"]
    assert result["memo_answer"]["thesis_driver_pack"]["schema_version"] == "sec_agent_thesis_driver_pack_v0.1"
    assert "memo_writer_data_view" not in fake.calls[0]["messages"][1]["content"]
    assert "shared_memo_context" in fake.calls[0]["messages"][1]["content"]
    assert "memo_writer_v0_10_minimal_judgment_surface_programmatic_projection" in fake.calls[0]["messages"][1]["content"]
    assert "writer_thesis_skeleton" in fake.calls[0]["messages"][1]["content"]
    assert "thesis_density_contract" in fake.calls[0]["messages"][1]["content"]
    assert "do_not_emit_supported_claims" in fake.calls[0]["messages"][1]["content"]
    assert fake.calls[0]["messages"][1]["content"].find("Input JSON:") < 4500


def test_memo_writer_minimal_model_output_is_programmatically_projected() -> None:
    observations = [
        {
            "agent_id": "fundamental_analyst",
            "observations": [
                {
                    "claim_id": "claim_financial_quality",
                    "claim": "DELL AI server revenue and gross margin evidence support a bounded product-quality bridge.",
                    "claim_type": "company_reported_financial_fact",
                    "memo_slot": "fundamentals",
                    "analysis_dimension": "fundamentals",
                    "evidence_refs": ["ev_financial_quality"],
                    "source_families": ["primary_sec_filing"],
                    "ticker_scope": ["DELL"],
                    "metric_scope": ["product_revenue", "gross_margin"],
                    "materiality": "high",
                    "confidence": "high",
                    "claim_rank_score": 92,
                    "claim_rank_bucket": "memo_ready",
                },
            ],
        },
        {
            "agent_id": "product_technology_analyst",
            "observations": [
                {
                    "claim_id": "claim_product_bridge",
                    "claim": "NVDA GPU generation and DELL AI server product family evidence support product capability analysis without needing SKU revenue.",
                    "claim_type": "product_taxonomy_context",
                    "memo_slot": "product_technology",
                    "analysis_dimension": "product_and_production",
                    "evidence_refs": ["ev_product_bridge"],
                    "source_families": ["company_product_evidence_graph"],
                    "ticker_scope": ["NVDA", "DELL"],
                    "metric_scope": ["product_family", "product_spec"],
                    "materiality": "high",
                    "confidence": "medium",
                    "claim_rank_score": 88,
                    "claim_rank_bucket": "memo_ready",
                },
            ],
        },
        {
            "agent_id": "industry_supply_chain_analyst",
            "observations": [
                {
                    "claim_id": "claim_cloud_demand_pool",
                    "claim": "AMZN MSFT and GOOGL capex evidence supports AI data center demand-pool context but not direct supplier orders.",
                    "claim_type": "industry_context_only",
                    "memo_slot": "industry_relationship",
                    "analysis_dimension": "industry_supply_chain",
                    "evidence_refs": ["ev_cloud_capex"],
                    "source_families": ["primary_sec_filing"],
                    "ticker_scope": ["AMZN", "MSFT", "GOOGL"],
                    "metric_scope": ["capex"],
                    "materiality": "medium",
                    "confidence": "medium",
                    "claim_rank_score": 82,
                    "claim_rank_bucket": "memo_ready",
                },
            ],
        },
        {
            "agent_id": "risk_counterevidence_analyst",
            "observations": [
                {
                    "claim_id": "claim_margin_risk",
                    "claim": "The remaining risk is that demand-pool capex does not prove DELL customer deployment or supplier order conversion.",
                    "claim_type": "risk_counterevidence",
                    "memo_slot": "risk_counterevidence",
                    "analysis_dimension": "risk_and_counterevidence",
                    "evidence_refs": ["ev_margin_risk"],
                    "source_families": ["primary_sec_filing"],
                    "ticker_scope": ["DELL"],
                    "metric_scope": ["customer_deployment_gap"],
                    "materiality": "high",
                    "confidence": "medium",
                    "claim_rank_score": 80,
                    "claim_rank_bucket": "memo_ready",
                },
            ],
        },
    ]
    judgment = aggregate_specialist_judgment_plan(observations)
    judgment["memo_thesis_plan"]["status"] = "ready"
    judgment["memo_thesis_pack"]["status"] = "ready"
    judgment["claim_card_stats"] = {
        "supported_claim_count": 4,
        "memo_ready_claim_count": 4,
        "memo_slot_supported_count": 4,
    }
    judgment["required_dimension_ids"] = ["fundamentals", "product_and_production"]
    judgment["thesis_driver_pack"] = {
        "schema_version": "sec_agent_thesis_driver_pack_v0.1",
        "status": "ready",
        "dimension_sections": [
            {
                "dimension_id": "fundamentals",
                "title": "Fundamentals",
                "summary": "Financial evidence supports a bounded margin-quality read.",
                "business_mechanism": "AI server revenue must translate through product mix and service economics.",
                "financial_bridge": "Gross margin and product revenue are the key bridge to earnings quality.",
                "counter_read": "Capex demand pool alone does not prove supplier orders.",
                "claim_ids": ["claim_financial_quality"],
                "evidence_refs": ["ev_financial_quality"],
            },
            {
                "dimension_id": "product_and_production",
                "title": "Product",
                "summary": "Product family and GPU generation evidence support product capability analysis.",
                "business_mechanism": "GPU generation and AI server configuration drive deployment relevance.",
                "financial_bridge": "Product capability matters only if it converts into mix, margin, or deployments.",
                "counter_read": "Absence of SKU revenue keeps the conclusion bounded.",
                "claim_ids": ["claim_product_bridge"],
                "evidence_refs": ["ev_product_bridge"],
            },
        ],
    }
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                        "direct_answer": (
                            "当前证据支持一个有边界但可执行的判断：DELL 的 AI server 质量不能只看云厂商 capex，"
                            "必须同时看 AI server 收入、ISG 毛利率、NVDA GPU 供给/代际、服务器配置和客户部署证据。"
                            "云厂商 capex 可以说明数据中心需求池和资本开支强度，但它不是 DELL 的直接订单，也不能自动证明毛利改善。"
                            "因此主线应写成：需求端投入为 AI server 链条提供背景，NVDA GPU 供给和产品代际决定服务器 OEM 的配置能力，"
                            "DELL 是否真正受益取决于 AI server mix、GPU pass-through cost、服务收入和现金流是否共同改善。"
                            "反向风险是收入放量但毛利被 GPU 成本和竞争压缩，或者客户部署没有转化为可验证 backlog。"
                            "这个判断的边界是：现有证据支持需求和产品传导路径，但还不能把需求池写成 DELL 订单或 SKU revenue。"
                            "如果后续看到 DELL AI server backlog、客户部署、ISG 毛利率和经营现金流同步改善，才可以把该链条上调为更高置信度。"
                        ),
                    "memo_thesis_plan": judgment["memo_thesis_plan"],
                    "raw_rows_consumed": False,
                    "tool_calls_requested": [],
                    "memo_generation_policy": "thesis_led_claim_cards_v0_1",
                }
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "分析 DELL AI server 质量和 NVDA 供应链传导。",
            "response_language": "zh-CN",
            "multi_agent_context": {"response_language": "zh-CN"},
            "agent_activation_plan": {"execution_mode": "standard_memo"},
            "verified_judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    memo = result["memo_answer"]
    diagnostics = memo.get("memo_writer_diagnostics") or {}
    assert result["memo_route_result"]["status"] == "pass", result["memo_route_result"]
    assert result["memo_route_result"]["attempt_count"] == 1
    assert diagnostics["memo_claims_completed_from_verified_judgment"] >= 2
    raw_audit = result["memo_route_result"]["raw_output_audit"]
    assert raw_audit["raw_dimension_count"] == 0
    assert raw_audit["normalized_dimension_count"] >= 2
    assert len(memo["memo_claims"]) >= 4
    assert len(memo["dimension_analyses"]) >= 2
    assert memo["investment_implications"]
    assert "minimal_judgment_surface_programmatic_projection_v0_1" in fake.calls[0]["messages"][1]["content"]


def test_memo_contract_completion_fills_actions_after_projecting_claims() -> None:
    judgment = {
        "memo_thesis_plan": {"schema_version": "sec_agent_memo_thesis_plan_v0.1", "status": "ready"},
        "memo_thesis_pack": {"schema_version": "sec_agent_memo_thesis_pack_v0.1", "status": "ready"},
        "supported_claims": [
            {
                "claim_id": "claim_product_bridge",
                "claim": "DELL AI server revenue and gross margin evidence support a bounded product-quality bridge.",
                "claim_type": "company_reported_financial_fact",
                "memo_slot": "fundamentals",
                "analysis_dimension": "fundamentals",
                "evidence_refs": ["ev_financial_quality"],
                "source_families": ["primary_sec_filing"],
                "metric_scope": ["product_revenue", "gross_margin"],
            },
            {
                "claim_id": "claim_customer_boundary",
                "claim": "Cloud capex evidence supports demand-pool context but not direct supplier orders.",
                "claim_type": "industry_context_only",
                "memo_slot": "industry_relationship",
                "analysis_dimension": "industry_supply_chain",
                "evidence_refs": ["ev_cloud_capex"],
                "source_families": ["primary_sec_filing"],
                "metric_scope": ["capex"],
            },
        ],
        "memo_outline": [{"memo_slot": "fundamentals", "status": "supported"}],
    }

    completed = _complete_memo_contract_from_judgment(
        {
            "answer_status": "draft",
            "direct_answer": "当前证据支持有边界的产品质量判断。",
            "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        },
        judgment,
        memo_profile=_memo_profile_spec_from_name("standard"),
        response_language="zh-CN",
    )

    diagnostics = completed["memo_writer_diagnostics"]
    assert diagnostics["memo_claims_completed_from_verified_judgment"] == 2
    assert set(diagnostics["action_items_completed_from_projected_claims"]) == {
        "investment_implications",
        "what_would_change_view",
        "monitoring_items",
    }
    assert completed["investment_implications"]
    assert completed["what_would_change_view"]
    assert completed["monitoring_items"]


def test_memo_contract_promotes_supported_dimensions_from_blocked_provider_shape() -> None:
    memo = {
        "answer_status": "blocked_by_judgment_plan",
        "bounded_answer_allowed": False,
        "response_language": {"language": "zh-CN"},
        "memo_profile": {"profile": "deep_research"},
        "direct_answer": "结论先行：当前证据支持有限成立的 AI 基础设施判断。",
        "memo_claims": [],
        "dimension_analyses": [
            {
                "dimension_id": "product_and_production",
                "title": "产品与产线",
                "status": "supported",
                "summary": "DELL 已有产品线收入锚点，支持其承接基础设施需求，但不能外推为 SKU 收入。",
                "business_mechanism": "产品线收入可以支撑业务结构判断，但仍缺客户订单和 backlog 验证。",
                "claim_ids": ["pre_memo_fact_claim:product"],
                "evidence_refs": ["dell_product_revenue_ref"],
            },
            {
                "dimension_id": "capital_and_financing",
                "title": "投融资与资本开支",
                "status": "supported",
                "summary": "DELL capex 说明发行人自身再投资存在，但不能直接当作客户采购确认。",
                "claim_ids": ["pre_memo_fact_claim:capex"],
                "evidence_refs": ["dell_capex_ref"],
            },
            {
                "dimension_id": "competition_and_market_position",
                "title": "竞争格局",
                "status": "gap_or_counterevidence",
                "summary": "当前缺少可验证份额和渠道数据。",
                "evidence_refs": [],
            },
        ],
    }

    completed = _complete_memo_contract_from_judgment(
        memo,
        {"memo_thesis_plan": {"status": "ready"}, "memo_thesis_pack": {"status": "ready"}},
        memo_profile=_memo_profile_spec_from_name("deep_research"),
        response_language="zh-CN",
    )

    assert completed["answer_status"] == "draft"
    assert completed["bounded_answer_allowed"] is False
    assert completed["memo_writer_diagnostics"]["answer_status_restored_from"] == "blocked_by_judgment_plan"
    assert completed["memo_writer_diagnostics"]["memo_claims_completed_from_dimension_analyses"] == 2
    assert len(completed["memo_claims"]) == 2
    assert {claim["claim_id"] for claim in completed["memo_claims"]} == {
        "pre_memo_fact_claim:product",
        "pre_memo_fact_claim:capex",
    }
    assert all(claim.get("evidence_refs") for claim in completed["memo_claims"])
    assert "competition" not in json.dumps(completed["memo_claims"], ensure_ascii=False).lower()

    rendered = _render_memo_answer(completed, bounded=False)
    assert "Bounded answer only" not in rendered
    assert "分维度分析" in rendered
    assert "关键论据" in rendered
    assert "[C1]" in rendered
    assert "证据索引" in rendered


def test_memo_writer_respects_configured_token_budget_without_floor() -> None:
    fake = _FakeChat(
        [
            {"content": "{\"answer_status\": \"draft\"", "finish_reason": "length", "output_tokens": 900},
            json.dumps(_memo()),
        ]
    )

    result = route_memo_writer_llm(
        _state(),
        config=MemoLLMConfig(**{**_config().__dict__, "memo_max_tokens": 1200, "max_repair_attempts": 1}),
        call_chat_completion=fake,
    )

    assert result["memo_route_result"]["status"] == "pass"
    assert len(fake.calls) == 2
    assert [call["max_tokens"] for call in fake.calls] == [1200, 1200]


def test_memo_writer_route_records_input_pack_fingerprint_without_prompt_text() -> None:
    fake = _FakeChat([json.dumps(_memo())])

    result = route_memo_writer_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    fingerprint = result["memo_route_result"]["input_pack_fingerprint"]
    serialized = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True)
    assert fingerprint["schema_version"] == "sec_agent_memo_writer_input_pack_fingerprint_v0_1"
    assert fingerprint["agent_id"] == "memo_writer"
    assert fingerprint["digest"].startswith("sha256:")
    assert fingerprint["component_summaries"]["verified_judgment_plan"]["digest"].startswith("sha256:")
    assert fingerprint["component_summaries"]["memo_logic_plan"]["item_count"] == 0
    assert fingerprint["known_evidence_ref_count"] >= 1
    assert "capex_ref" in fingerprint["known_evidence_refs"]
    scaffold = fingerprint["static_prompt_scaffold_summary"]
    assert scaffold["schema_version"] == "sec_agent_memo_writer_static_scaffold_fingerprint_v0_1"
    assert scaffold["policy_id"] == "memo_writer_compact_instruction_scaffold_v0_1"
    assert scaffold["user_instruction_chars"] < 4500
    assert fingerprint["approx_total_prompt_chars_with_scaffold"] > fingerprint["approx_prompt_payload_chars"]
    assert fingerprint["fingerprint_policy"] == "fingerprint_only_no_prompt_text_persisted_v0_1"
    assert "Write one MemoDraft" not in serialized
    assert "Supported capex claim" not in serialized


def test_memo_logic_plan_compaction_does_not_duplicate_required_item_prompts() -> None:
    compact = _compact_memo_logic_plan(
        {
            "schema_version": "finsight_memo_logic_plan_v0_1",
            "writer_thesis_skeleton": {
                "dimension_moves": [
                    {
                        "dimension_id": "product_technology",
                        "required_item_ids": ["gpu_supply"],
                        "required_item_answer_moves": [
                            {
                                "question_item_id": "gpu_supply",
                                "answer_first_judgment_prompt": "this detailed prompt should live only in the required-item answer plan",
                                "evidence_bridge_prompt": "bridge prompt",
                                "counter_read_prompt": "counter prompt",
                                "what_would_change_prompt": "what changes prompt",
                            }
                        ],
                    }
                ]
            },
            "required_item_answer_plan": [
                {
                    "question_item_id": "gpu_supply",
                    "answer_first_judgment_prompt": "this detailed prompt should live only in the required-item answer plan",
                    "evidence_bridge_prompt": "bridge prompt",
                    "counter_read_prompt": "counter prompt",
                    "what_would_change_prompt": "what changes prompt",
                }
            ],
        }
    )

    move = compact["writer_thesis_skeleton"]["dimension_moves"][0]
    serialized_move = json.dumps(move, ensure_ascii=False)
    serialized_plan = json.dumps(compact["required_item_answer_plan"], ensure_ascii=False)
    assert move["required_item_answer_move_count"] == 1
    assert "required_item_answer_moves" not in move
    assert "detailed prompt" not in serialized_move
    assert "detailed prompt" in serialized_plan


def test_verifier_projection_does_not_duplicate_memo_supported_claims_when_memo_claims_exist() -> None:
    state = {
        "memo_answer": {
            "answer_status": "draft",
            "direct_answer": "Readable conclusion.",
            "memo_claims": [
                {
                    "claim_id": "claim_1",
                    "claim": "Memo claim one.",
                    "evidence_refs": ["ref_1"],
                    "source_families": ["primary_sec_filing"],
                }
            ],
            "supported_claims": [
                {
                    "claim_id": "claim_1",
                    "claim": "Memo claim one duplicated from supported claims.",
                    "evidence_refs": ["ref_1"],
                    "source_families": ["primary_sec_filing"],
                }
            ],
        },
        "verified_judgment_plan": {
            "supported_claims": [
                {
                    "claim_id": "claim_1",
                    "claim": "Verified claim one.",
                    "evidence_refs": ["ref_1"],
                    "source_families": ["primary_sec_filing"],
                }
            ],
        },
    }

    projection = _verifier_minimal_projection(
        state,
        deterministic={"status": "pass", "bounded_answer_allowed": False},
    )

    assert len(projection["memo_answer"]["memo_claims"]) == 1
    assert projection["memo_answer"]["supported_claims"] == []
    assert projection["memo_claim_ref_inventory"][0]["claim_id"] == "claim_1"


def test_memo_writer_llm_infers_chinese_response_language_from_query() -> None:
    judgment = _judgment_without_unsupported()
    memo = {
        "answer_status": "draft",
        "direct_answer": "基于已验证的 capex 证据，当前 memo 只能给出有边界的正向判断，不能扩展到未验证客户或订单假设。",
        "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        "memo_thesis_plan": judgment["memo_thesis_plan"],
        "raw_rows_consumed": False,
        "tool_calls_requested": [],
        "memo_claims": [
            {
                "claim_id": "fundamental_analyst_claim_1",
                "claim": "已验证 capex 证据支持当前投资判断，但证据边界仍限于已验证 ClaimCard。",
                "evidence_refs": ["capex_ref"],
                "source_families": ["primary_sec_filing"],
            }
        ],
        "dimension_analyses": [
            {
                "dimension_id": "fundamentals",
                "status": "supported",
                "summary": "已验证 capex 证据构成当前判断的可追溯基本面约束。",
                "business_mechanism": "资本开支事实限定再投资强度和业务扩张判断。",
                "financial_bridge": "仅通过已验证 capex ClaimCard 桥接到投资判断。",
                "claim_ids": ["fundamental_analyst_claim_1"],
                "evidence_refs": ["capex_ref"],
            }
        ],
        "source_boundary": "仅限已验证 judgment plan；不包含原始检索行。",
    }
    fake = _FakeChat([json.dumps(memo, ensure_ascii=False)])

    result = route_memo_writer_llm(
        {
            "user_query": "请用中文写一段投研 memo。",
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    prompt = fake.calls[0]["messages"][1]["content"]
    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_answer"]["response_language"]["language"] == "zh-CN"
    assert "response_language.language exactly to zh-CN" in prompt
    assert "Simplified Chinese" in prompt


def test_memo_writer_llm_rewrites_template_gap_first_chinese_opening() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "product_technology_analyst",
                "observations": [
                    {
                        "claim": "DELL AI optimized server product revenue was $16.1B.",
                        "claim_type": "reported_product_kpi",
                        "ticker_scope": ["DELL"],
                        "metric_scope": ["product revenue"],
                        "analysis_dimension": "product_and_production",
                        "memo_slot": "product_and_production",
                        "direction": "positive",
                        "evidence_refs": ["dell_product_ref"],
                        "source_families": ["company_authored_unaudited_sec_filing"],
                    },
                ],
            },
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "GOOGL capital expenditures were $5.1B.",
                        "claim_type": "reported_financial_fact",
                        "ticker_scope": ["GOOGL"],
                        "metric_scope": ["capex"],
                        "analysis_dimension": "capital_and_financing",
                        "memo_slot": "capital_and_financing",
                        "direction": "neutral",
                        "evidence_refs": ["googl_capex_ref"],
                        "source_families": ["primary_sec_filing"],
                    },
                ],
            },
        ]
    )
    memo = {
        "answer_status": "draft",
        "direct_answer": "当前证据更适合形成一份谨慎的分维度判断：产品与产线上，DELL / product revenue / $16.1B 指向正向影响；缺失的订单、份额或商业 tracker 只作为后续验证项。",
        "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        "raw_rows_consumed": False,
        "tool_calls_requested": [],
        "memo_claims": [
            {
                "claim": "DELL AI 优化服务器收入为 $16.1B。",
                "evidence_refs": ["dell_product_ref"],
                "source_families": ["company_authored_unaudited_sec_filing"],
            },
            {
                "claim": "GOOGL 资本开支为 $5.1B。",
                "evidence_refs": ["googl_capex_ref"],
                "source_families": ["primary_sec_filing"],
            },
        ],
        "dimension_analyses": [
            {
                "dimension_id": "product_and_production",
                "summary": "DELL AI 优化服务器收入为 $16.1B，可作为产品传导锚点。",
                "evidence_refs": ["dell_product_ref"],
            },
            {
                "dimension_id": "capital_and_financing",
                "summary": "GOOGL 资本开支为 $5.1B，约束云资本开支判断。",
                "evidence_refs": ["googl_capex_ref"],
            },
        ],
    }
    fake = _FakeChat([json.dumps(memo, ensure_ascii=False)])

    result = route_memo_writer_llm(
        {
            "user_query": "请分析 AI 基础设施 capex 和供应链传导。",
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    direct = result["memo_answer"]["direct_answer"]
    assert result["memo_route_result"]["status"] == "pass"
    assert "当前证据更适合形成一份谨慎的分维度判断" not in direct
    assert "缺失的订单、份额或商业 tracker" not in direct
    assert "已披露事实给出的主线" in direct
    assert "产品收入" in direct


def test_memo_writer_llm_wraps_english_claims_for_chinese_response_gate() -> None:
    judgment = _judgment_without_unsupported()
    memo = {
        "answer_status": "draft",
        "direct_answer": "Supported capex evidence constrains the current investment view.",
        "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        "memo_thesis_plan": judgment["memo_thesis_plan"],
        "raw_rows_consumed": False,
        "tool_calls_requested": [],
        "memo_claims": [
            {
                "claim_id": "fundamental_analyst_claim_1",
                "claim": "Supported capex evidence constrains the current investment view.",
                "evidence_refs": ["capex_ref"],
                "source_families": ["primary_sec_filing"],
            }
        ],
        "dimension_analyses": [
            {
                "dimension_id": "fundamentals",
                "status": "supported",
                "summary": "Supported capex evidence constrains the current investment view.",
                "business_mechanism": "Capex evidence bounds the reinvestment mechanism.",
                "financial_bridge": "Bridge only through the verified capex ClaimCard.",
                "claim_ids": ["fundamental_analyst_claim_1"],
                "evidence_refs": ["capex_ref"],
            }
        ],
    }
    fake = _FakeChat([json.dumps(memo)])

    result = route_memo_writer_llm(
        {
            "user_query": "请用中文写一段投研 memo。",
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    verification = verify_multi_agent_memo_draft(result["memo_answer"], judgment)
    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_answer"]["response_language"]["language"] == "zh-CN"
    assert result["memo_answer"]["response_language_normalized_user_text"] is True
    assert "原文" not in result["memo_answer"]["direct_answer"]
    assert "原始表述" not in result["memo_answer"]["direct_answer"]
    assert "原文" not in result["memo_answer"]["memo_claims"][0]["claim"]
    assert "Supported capex evidence" not in result["memo_answer"]["memo_claims"][0]["claim"]
    assert "概括为" not in result["memo_answer"]["memo_claims"][0]["claim"]
    assert verification["status"] == "pass"


def test_memo_writer_llm_localizes_english_heavy_chinese_dimension_counter_read() -> None:
    judgment = _judgment_without_unsupported()
    memo = {
        "answer_status": "draft",
        "direct_answer": "Supported capex evidence constrains the current investment view.",
        "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        "memo_thesis_plan": judgment["memo_thesis_plan"],
        "raw_rows_consumed": False,
        "tool_calls_requested": [],
        "memo_claims": [
            {
                "claim_id": "fundamental_analyst_claim_1",
                "claim": "Supported capex evidence constrains the current investment view.",
                "evidence_refs": ["capex_ref"],
                "source_families": ["primary_sec_filing"],
            }
        ],
        "dimension_analyses": [
            {
                "dimension_id": "industry_supply_chain",
                "status": "supported",
                "summary": (
                    "NVDA and DELL are co-exposed to AI infrastructure demand as sector-depth peers, "
                    "with DELL's Servers and Networking segment positioned to benefit from NVDA GPU-driven server builds."
                ),
                "business_mechanism": (
                    "The evidence traces external demand or supply-chain exposure to the company's relevant products, "
                    "segments, or counterparties."
                ),
                "financial_bridge": (
                    "Bridge the claim through sector, product_or_business_line_profile; direction=positive; "
                    "do not infer unverified sales, share, or forecast values."
                ),
                "counter_read": (
                    "Missing confirmation: DELL ISG or AI-optimized server revenue or order data not in bounded evidence.; "
                    "No direct NVDA-DELL supplier-customer edge in relationship graph."
                ),
                "claim_ids": ["fundamental_analyst_claim_1"],
                "evidence_refs": ["capex_ref"],
            }
        ],
    }
    fake = _FakeChat([json.dumps(memo)])

    result = route_memo_writer_llm(
        {
            "user_query": "请用中文分析 AI 基础设施需求传导。",
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    verification = verify_multi_agent_memo_draft(result["memo_answer"], judgment)
    row = result["memo_answer"]["dimension_analyses"][0]
    assert result["memo_route_result"]["status"] == "pass"
    assert verification["status"] == "pass"
    assert "Missing confirmation" not in row["counter_read"]
    assert "supplier-customer edge" not in row["counter_read"]
    assert "缺少确认" in row["counter_read"] or "缺少可直接提权" in row["counter_read"]
    assert row["response_language_normalized_user_text"] is True


def test_memo_writer_llm_flattens_nested_memo_draft_json() -> None:
    fake = _FakeChat([json.dumps({"memo_draft": _memo()})])

    result = route_memo_writer_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_answer"]["direct_answer"] == "Supported capex claim."
    assert "memo_draft" not in result["memo_answer"]


def test_memo_writer_llm_normalizes_non_contract_status_with_claims() -> None:
    memo = {**_memo(), "answer_status": "partial"}
    fake = _FakeChat([json.dumps(memo)])

    result = route_memo_writer_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_answer"]["answer_status"] == "draft"
    assert result["memo_answer"]["memo_writer_diagnostics"]["normalized_answer_status_from"] == "partial"


def test_memo_writer_llm_normalizes_internal_policy_and_compact_plan() -> None:
    memo = {
        **_memo(),
        "memo_generation_policy": "model_custom_policy",
        "memo_thesis_plan": {
            "schema_version": "sec_agent_memo_thesis_plan_v0.1",
            "status": "ready",
            "primary_thesis_claim_id": "fundamental_analyst_claim_1",
            "primary_thesis": "Supported capex claim.",
            "thesis_direction": "positive",
            "section_sequence": [{"memo_slot": "fundamentals", "claim_ids": ["fundamental_analyst_claim_1"]}],
        },
    }
    fake = _FakeChat([json.dumps(memo)])

    result = route_memo_writer_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_answer"]["memo_generation_policy"] == "thesis_led_claim_cards_v0_1"
    assert "section_sequence" not in result["memo_answer"]["memo_thesis_plan"]


def test_verifier_rejects_numeric_drift_from_source_claim() -> None:
    judgment = _market_judgment()
    memo = {
        "answer_status": "draft",
        "direct_answer": "AMD valuation risk is elevated.",
        "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        "memo_thesis_plan": judgment["memo_thesis_plan"],
        "raw_rows_consumed": False,
        "tool_calls_requested": [],
        "memo_claims": [
            {
                "claim_id": "market_valuation_analyst_claim_1",
                "claim": "AMD EV/Sales is 2.8x, indicating valuation risk.",
                "evidence_refs": ["MARKET::AMD::2026-05-29"],
                "source_families": ["market_snapshot"],
            }
        ],
    }

    verification = verify_multi_agent_memo_draft(memo, judgment)

    assert verification["status"] == "fail"
    assert any(error["type"] == "memo_claim_numeric_token_not_in_source_claim" for error in verification["errors"])


def test_verifier_warns_on_non_material_numeric_tokens_from_source_claim() -> None:
    judgment = _market_judgment()
    memo = {
        "answer_status": "draft",
        "direct_answer": "AMD valuation risk is elevated.",
        "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        "memo_thesis_plan": judgment["memo_thesis_plan"],
        "raw_rows_consumed": False,
        "tool_calls_requested": [],
        "memo_claims": [
            {
                "claim_id": "market_valuation_analyst_claim_1",
                "claim": "As of 2026, AMD EV/Sales is 22.1x; date fragments 29 and 5 do not change the valuation point.",
                "evidence_refs": ["MARKET::AMD::2026-05-29"],
                "source_families": ["market_snapshot"],
            }
        ],
    }

    verification = verify_multi_agent_memo_draft(memo, judgment)

    assert verification["status"] == "pass"
    assert not any(error["type"] == "memo_claim_numeric_token_not_in_source_claim" for error in verification["errors"])
    assert any(warning["type"] == "memo_claim_numeric_token_not_in_source_claim" for warning in verification["warnings"])


def test_memo_writer_normalizes_relationship_graph_claim_type_to_hypothesis() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "industry_supply_chain_analyst",
                "observations": [
                    {
                        "claim": "Relationship graph supports a sector readthrough hypothesis.",
                        "claim_type": "relationship_hypothesis",
                        "evidence_refs": ["rel_ref_1"],
                        "source_families": ["relationship_graph"],
                        "memo_slot": "industry_relationship",
                        "materiality": "medium",
                        "confidence": "medium",
                    }
                ],
            }
        ]
    )
    source_claim = next(claim for claim in judgment["supported_claims"] if claim["agent_id"] == "industry_supply_chain_analyst")
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": "Relationship graph supports a sector readthrough hypothesis.",
                    "memo_generation_policy": "thesis_led_claim_cards_v0_1",
                    "memo_thesis_plan": judgment["memo_thesis_plan"],
                    "raw_rows_consumed": False,
                    "tool_calls_requested": [],
                    "memo_claims": [
                        {
                            "claim_id": source_claim["claim_id"],
                            "claim": "Relationship graph supports a sector readthrough hypothesis.",
                            "claim_type": "business_observation",
                            "evidence_refs": ["rel_ref_1"],
                            "source_families": ["relationship_graph"],
                        }
                    ],
                }
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "Write a memo.",
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    claim = result["memo_answer"]["memo_claims"][0]
    assert result["memo_route_result"]["status"] == "pass"
    assert claim["claim_type"] == "relationship_hypothesis"
    assert claim["relationship_claim_type_normalized"] is True


def test_memo_writer_normalizes_numeric_drift_to_source_claim() -> None:
    judgment = _market_judgment()
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": "AMD valuation risk is elevated.",
                    "memo_generation_policy": "model_custom_policy",
                    "memo_thesis_plan": judgment["memo_thesis_plan"],
                    "raw_rows_consumed": False,
                    "tool_calls_requested": [],
                    "memo_claims": [
                        {
                            "claim_id": "market_valuation_analyst_claim_1",
                            "claim": "AMD EV/Sales is 2.8x, indicating valuation risk.",
                            "evidence_refs": ["MARKET::AMD::2026-05-29"],
                        }
                    ],
                }
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "Write a memo.",
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["memo_route_result"]["status"] == "pass"
    claim = result["memo_answer"]["memo_claims"][0]
    assert "22.1x" in claim["claim"]
    assert claim["numeric_fidelity_normalized"] is True


def test_memo_writer_infers_market_as_of_boundary_when_ref_lacks_date() -> None:
    judgment = _market_judgment()
    for claim in judgment["supported_claims"]:
        if claim.get("claim_id") == "market_valuation_analyst_claim_1":
            claim["evidence_refs"] = ["MARKET::AMD::latest"]
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": "AMD valuation risk is elevated.",
                    "memo_generation_policy": "thesis_led_claim_cards_v0_1",
                    "memo_thesis_plan": judgment["memo_thesis_plan"],
                    "raw_rows_consumed": False,
                    "tool_calls_requested": [],
                    "memo_claims": [
                        {
                            "claim_id": "market_valuation_analyst_claim_1",
                            "claim": "AMD EV/Sales is 22.1x, indicating valuation risk.",
                            "evidence_refs": ["MARKET::AMD::latest"],
                            "source_families": ["market_snapshot"],
                        }
                    ],
                }
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "Write a memo.",
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    claim = result["memo_answer"]["memo_claims"][0]
    assert result["memo_route_result"]["status"] == "pass"
    assert claim["as_of_date"] == "latest_available_market_snapshot"
    assert claim["market_as_of_date_inferred"] is True


def test_memo_writer_normalizes_direct_answer_numeric_drift() -> None:
    judgment = _market_judgment()
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": "AMD EV/Sales is 2.8x.",
                    "memo_generation_policy": "thesis_led_claim_cards_v0_1",
                    "memo_thesis_plan": judgment["memo_thesis_plan"],
                    "raw_rows_consumed": False,
                    "tool_calls_requested": [],
                    "memo_claims": [
                        {
                            "claim_id": "market_valuation_analyst_claim_1",
                            "claim": "AMD EV/Sales is 22.1x, indicating valuation risk.",
                            "evidence_refs": ["MARKET::AMD::2026-05-29"],
                        }
                    ],
                }
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "Write a memo.",
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["memo_route_result"]["status"] == "pass"
    assert "2.8x" not in result["memo_answer"]["direct_answer"]
    assert result["memo_answer"]["direct_answer_numeric_fidelity_normalized"] is True


def test_memo_writer_falls_back_to_safe_chinese_direct_answer_when_numeric_removal_damages_sentence() -> None:
    judgment = aggregate_focused_answer_judgment_plan(
        runtime_ledger_rows=[
            {
                "ticker": "AMZN",
                "fiscal_year": 2026,
                "period_role": "qtd",
                "metric_family": "operating_income",
                "metric_name": "营业利润",
                "display_value_zh": "347（百万美元）",
                "source_tier": "primary_sec_filing",
                "form_type": "10-Q",
                "metric_id": "amzn_operating_income_qtd_ref",
            },
            {
                "ticker": "AMZN",
                "fiscal_year": 2026,
                "period_role": "qtd",
                "metric_family": "revenue",
                "metric_name": "营收",
                "display_value_zh": "155,667（百万美元）",
                "source_tier": "primary_sec_filing",
                "form_type": "10-Q",
                "metric_id": "amzn_revenue_qtd_ref",
            },
        ],
        context_rows=[],
        evidence_requirement_plan={"requirements": [{"tickers": ["AMZN"], "metric_families": ["revenue", "margin"]}]},
        response_language="zh-CN",
    )
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": "亚马逊2026年第一季度营业利润为3.47亿美元，营收为1556.67亿美元，管理层强调成本控制。",
                    "memo_generation_policy": "thesis_led_claim_cards_v0_1",
                    "memo_thesis_plan": judgment["memo_thesis_plan"],
                    "raw_rows_consumed": False,
                    "tool_calls_requested": [],
                    "memo_claims": [
                        {
                            "claim_id": "focused_answer_synthesizer_fundamentals_1",
                            "claim": "本轮 primary SEC filing 证据为 AMZN 的利润率分析提供了关键数值锚点：营业利润=347（百万美元）；营收=155,667（百万美元）。",
                            "evidence_refs": ["amzn_operating_income_qtd_ref", "amzn_revenue_qtd_ref"],
                        }
                    ],
                },
                ensure_ascii=False,
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "分析 AMZN 最近披露的利润率变化。",
            "response_language": "zh-CN",
            "multi_agent_context": {"response_language": "zh-CN"},
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    direct = result["memo_answer"]["direct_answer"]
    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_answer"]["direct_answer_numeric_fidelity_normalized"] is True
    assert "营业利润为营收为" not in direct
    assert "347（百万美元）" in direct
    assert "155,667（百万美元）" in direct
    assert "。." not in direct


def test_memo_writer_falls_back_when_numeric_removal_leaves_zh_dangling_value_phrase() -> None:
    judgment = aggregate_focused_answer_judgment_plan(
        runtime_ledger_rows=[
            {
                "ticker": "LLY",
                "fiscal_year": 2026,
                "period_role": "qtd",
                "metric_family": "gross_margin",
                "metric_name": "毛利率",
                "metric_role": "percentage_rate",
                "display_value_zh": "54%",
                "source_tier": "primary_sec_filing",
                "form_type": "10-Q",
                "metric_id": "lly_gross_margin_qtd_ref",
            },
            {
                "ticker": "LLY",
                "fiscal_year": 2026,
                "period_role": "qtd",
                "metric_family": "revenue",
                "metric_name": "营收",
                "metric_role": "total_value",
                "display_value_zh": "19,799（百万美元）",
                "source_tier": "primary_sec_filing",
                "form_type": "10-Q",
                "metric_id": "lly_revenue_qtd_ref",
            },
        ],
        context_rows=[],
        evidence_requirement_plan={"requirements": [{"tickers": ["LLY"], "metric_families": ["revenue", "gross_margin"]}]},
        response_language="zh-CN",
    )
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": "LLY 2026年QTD毛利率为54%，营收为197.99亿美元，这些数据来自公司申报文件。",
                    "memo_generation_policy": "thesis_led_claim_cards_v0_1",
                    "memo_thesis_plan": judgment["memo_thesis_plan"],
                    "raw_rows_consumed": False,
                    "tool_calls_requested": [],
                    "memo_claims": [
                        {
                            "claim_id": "focused_answer_synthesizer_fundamentals_1",
                            "claim": "本轮主要 SEC 披露证据为 LLY 的利润率分析提供了关键数值锚点：毛利率=54%；营收=19,799（百万美元）。",
                            "evidence_refs": ["lly_gross_margin_qtd_ref", "lly_revenue_qtd_ref"],
                        }
                    ],
                },
                ensure_ascii=False,
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "用本地披露证据分析 LLY 最近的研发投入和产品周期风险。",
            "response_language": "zh-CN",
            "multi_agent_context": {"response_language": "zh-CN"},
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    direct = result["memo_answer"]["direct_answer"]
    assert result["memo_answer"]["direct_answer_numeric_fidelity_normalized"] is True
    assert "营收为这些数据" not in direct
    assert "19,799（百万美元）" in direct


def test_memo_writer_llm_uses_compact_repair_prompt_after_length() -> None:
    fake = _FakeChat(
        [
            {"content": '{"answer_status": "draft", "memo_claims": [', "finish_reason": "length", "output_tokens": 2600},
            json.dumps(_memo()),
        ]
    )

    result = route_memo_writer_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    repair_prompt = fake.calls[1]["messages"][1]["content"]
    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_route_result"]["repair_attempts"] == 1
    assert "Use this compact input JSON only" in repair_prompt
    assert "memo_writer_data_view" not in repair_prompt
    assert "memo_profile must stay compact" in repair_prompt
    assert "direct_answer <= 420 characters" in repair_prompt
    assert "unsupported_claims_excluded <= 2" in repair_prompt


def test_memo_writer_llm_accepts_complete_json_even_when_finish_reason_length() -> None:
    fake = _FakeChat(
        [
            {
                "content": json.dumps(_memo()),
                "finish_reason": "length",
                "output_tokens": 2600,
            }
        ]
    )

    result = route_memo_writer_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_route_result"]["attempt_count"] == 1
    assert result["memo_route_result"]["finish_reasons"] == ["length"]


def test_memo_writer_salvages_repeated_length_failures_as_verifiable_memo() -> None:
    fake = _FakeChat(
        [
            {"content": '{"answer_status": "draft", "memo_claims": [', "finish_reason": "length", "output_tokens": 3600},
            {"content": '{"answer_status": "draft", "memo_claims": [', "finish_reason": "length", "output_tokens": 3600},
            {"content": '{"answer_status": "draft", "memo_claims": [', "finish_reason": "length", "output_tokens": 3600},
        ]
    )

    state = _state()
    result = route_memo_writer_llm(
        state,
        config=_config(),
        call_chat_completion=fake,
    )

    memo = result["memo_answer"]
    verification = verify_multi_agent_memo_draft(memo, state["verified_judgment_plan"])
    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_route_result"]["deterministic_salvage_used"] is True
    assert result["memo_route_result"]["deterministic_salvage_verification"] == "pass"
    assert result["memo_route_result"]["attempt_count"] == 2
    assert verification["status"] == "pass"
    assert "supported_claims" not in memo
    assert 1 <= len(memo["memo_claims"]) <= 5
    rendered = _render_memo_answer(memo, bounded=True, state={"memo_logic_plan": {}})
    assert "证据锚点" not in rendered
    assert "投资判断只能沿" not in rendered
    assert "If the fact conflicts with another approved row" not in rendered
    assert "ClaimCard" not in rendered


def test_memo_writer_salvage_uses_required_item_answer_plan_for_product_depth() -> None:
    fake = _FakeChat(
        [
            {"content": '{"answer_status": "draft", "memo_claims": [', "finish_reason": "length", "output_tokens": 3600},
            {"content": '{"answer_status": "draft", "memo_claims": [', "finish_reason": "length", "output_tokens": 3600},
            {"content": '{"answer_status": "draft", "memo_claims": [', "finish_reason": "length", "output_tokens": 3600},
        ]
    )
    judgment = {
        "status": "pass",
        "supported_claims": [
            {
                "claim_id": "claim_dell_ai_server_quality",
                "claim": "DELL AI server revenue and gross margin bridge support product quality analysis.",
                "ticker_scope": ["DELL"],
                "analysis_dimension": "product_and_production",
                "metric_scope": ["product_kpi:product_revenue", "financial_metric:gross_margin"],
                "evidence_refs": ["ev_dell_ai_server"],
                "source_families": ["primary_sec_filing"],
                "economic_role": "issuer_product_revenue_signal",
            },
            {
                "claim_id": "claim_nvda_gpu_supply",
                "claim": "NVDA GPU H100 H200 B200 GB200 Blackwell generation supports product capability and supply analysis.",
                "ticker_scope": ["NVDA"],
                "analysis_dimension": "product_and_production",
                "metric_scope": ["product_spec:architecture"],
                "evidence_refs": ["ev_nvda_gpu"],
                "source_families": ["official_product_surface"],
            },
            {
                "claim_id": "claim_cloud_capex",
                "claim": "AMZN MSFT GOOGL cloud capex supports data center demand pool but not direct supplier orders.",
                "ticker_scope": ["AMZN", "MSFT", "GOOGL"],
                "analysis_dimension": "capital_and_financing",
                "metric_scope": ["financial_metric:capex"],
                "evidence_refs": ["ev_cloud_capex"],
                "source_families": ["primary_sec_filing"],
                "economic_role": "customer_or_demand_side_capex_signal",
            },
            {
                "claim_id": "claim_customer_deployment",
                "claim": "Customer deployment and order adoption signal supports product uptake analysis.",
                "ticker_scope": ["NVDA", "DELL"],
                "analysis_dimension": "product_and_production",
                "metric_scope": ["customer_deployment"],
                "evidence_refs": ["ev_customer_deployment"],
                "source_families": ["official_customer_deployment"],
            },
        ],
        "memo_outline": [
            {"memo_slot": "product_and_production", "status": "supported"},
            {"memo_slot": "capital_and_financing", "status": "supported"},
        ],
        "memo_thesis_plan": {"primary_thesis": ""},
        "memo_writer_allowed": True,
    }
    required_plan = [
        {
            "question_item_id": "dell_ai_server_quality_margin_bridge",
            "dimension": "product_and_production",
            "terms_any": ["dell", "ai server", "gross margin"],
            "required_tickers": ["DELL"],
        },
        {
            "question_item_id": "nvda_gpu_supply_generation",
            "dimension": "product_and_production",
            "terms_any": ["nvda", "gpu", "h100", "h200", "b200", "gb200", "blackwell"],
            "required_tickers": ["NVDA"],
        },
        {
            "question_item_id": "cloud_capex_read_through",
            "dimension": "capital_and_financing",
            "terms_any": ["capex", "amzn", "msft", "googl", "cloud"],
            "required_tickers": ["AMZN", "MSFT", "GOOGL"],
        },
        {
            "question_item_id": "customer_deployment_or_order_signal",
            "dimension": "product_and_production",
            "terms_any": ["deployment", "customer", "order", "adoption"],
            "required_tickers": ["NVDA", "DELL"],
        },
    ]
    state = {
        "user_query": "请用中文分析 NVDA/DELL AI infrastructure 的产品、客户部署和云厂商 capex 传导。",
        "verified_judgment_plan": judgment,
        "judgment_plan": judgment,
        "specialist_verification": {"memo_writer_allowed": True},
        "memo_logic_plan": {
            "schema_version": "finsight_memo_logic_plan_v0_1",
            "validation": {"status": "pass"},
            "required_item_answer_plan": required_plan,
            "section_order": ["product_and_production", "capital_and_financing"],
        },
        "response_language": "zh-CN",
    }

    result = route_memo_writer_llm(state, config=_config(), call_chat_completion=fake)
    memo = result["memo_answer"]
    rendered = _render_memo_answer(memo, bounded=True, state=state)

    assert result["memo_route_result"]["deterministic_salvage_used"] is True
    assert memo["memo_writer_diagnostics"]["salvage_required_item_answer_count"] >= 4
    assert memo["memo_logic_plan"]["required_item_answer_plan"][0]["question_item_id"] == "dell_ai_server_quality_margin_bridge"
    assert "DELL AI server" in rendered
    assert "gross margin" in rendered
    assert "NVDA GPU" in rendered
    assert "Blackwell" in rendered
    assert "AMZN/MSFT/GOOGL" in rendered
    assert "capex" in rendered.lower() or "资本开支" in rendered
    assert "customer deployment" in rendered
    assert "说明" in rendered or "支撑" in rendered or "传导" in rendered


def test_renderer_projects_required_item_answers_from_product_graph_pack() -> None:
    memo = {
        "answer_status": "draft",
        "response_language": {"language": "zh-CN"},
        "direct_answer": "云厂商 capex 支撑 AI 基础设施需求池，但需要连接供应链和产品证据后再判断供应商传导。",
        "dimension_analyses": [
            {
                "dimension_id": "capital_and_financing",
                "title": "投融资与资本开支",
                "summary": "AMZN/MSFT/GOOGL cloud capex 是需求池信号，不等于供应商订单。",
                "evidence_refs": ["ev_cloud_capex"],
            }
        ],
        "memo_claims": [
            {
                "claim_id": "cloud_capex",
                "claim": "AMZN/MSFT/GOOGL cloud capex supports demand-pool context but not direct supplier orders.",
                "evidence_refs": ["ev_cloud_capex"],
            }
        ],
    }
    required_plan = [
        {
            "question_item_id": "nvda_gpu_supply_generation",
            "dimension": "product_and_production",
            "terms_any": ["nvda", "gpu", "h100", "h200", "b200", "gb200", "blackwell"],
            "required_evidence_roles": ["product_spec", "generation_edge"],
        }
    ]
    state = {
        "memo_logic_plan": {
            "schema_version": "finsight_memo_logic_plan_v0_1",
            "validation": {"status": "pass"},
            "required_item_answer_plan": required_plan,
        },
        "supervising_analyst_pack": {
            "product_bridge_pack": {
                "official_product_context": [
                    {
                        "ticker": "NVDA",
                        "product_family": "GPU / Accelerator",
                        "products_or_platforms": ["H100", "H200", "B200", "GB200", "Blackwell GPU architecture"],
                        "source_role": "official_product_profile_spec",
                        "claim_boundary": "Official product surface slot; supports product existence/spec/taxonomy, not sales/share/ASP/inventory.",
                        "evidence_refs": ["ev_nvda_blackwell_spec"],
                    }
                ],
                "product_relationship_context": [
                    {
                        "ticker": "NVDA",
                        "authority_type": "supply_chain_signal",
                        "edge_type": "COMPONENT_INPUT_TO",
                        "from_node_id": "company_product_family:NVDA:gpu_accelerator",
                        "to_node_id": "company_product_family:DELL:server_oem",
                        "claim_boundary": "Accelerators are core inputs to AI server systems; not shipment, revenue, allocation, or customer concentration proof.",
                        "evidence_refs": ["ev_nvda_dell_supply_chain_edge"],
                    }
                ],
            }
        },
    }

    rendered = _render_memo_answer(memo, bounded=False, state=state)

    assert "关键问题回应" in rendered
    assert "NVDA GPU" in rendered
    assert "H100/H200/B200/GB200/Blackwell" in rendered
    assert "支撑其产品能力" in rendered
    assert "不能替代 SKU revenue" in rendered
    assert "ev_nvda_blackwell_spec" not in rendered
    assert "ev_nvda_dell_supply_chain_edge" not in rendered
    assert "C2" in rendered or "C3" in rendered


def test_renderer_projects_required_item_boundary_when_no_promotable_evidence() -> None:
    memo = {
        "answer_status": "draft",
        "response_language": {"language": "zh-CN"},
        "direct_answer": "ASML 订单和设备周期需要分开看，公开证据不足时必须写清边界。",
        "dimension_analyses": [],
        "memo_claims": [],
    }
    required_plan = [
        {
            "question_item_id": "export_restriction_context",
            "dimension": "risk_and_counterevidence",
            "terms_any": ["export", "china", "restriction", "license", "出口", "中国", "限制", "许可证", "管制"],
            "required_evidence_roles": ["regulatory_export_control"],
            "evidence_bridge_prompt": "Use official filing risk, regional exposure, license, or export-control context.",
        }
    ]
    state = {
        "memo_logic_plan": {
            "schema_version": "finsight_memo_logic_plan_v0_1",
            "validation": {"status": "pass"},
            "required_item_answer_plan": required_plan,
        }
    }

    rendered = _render_memo_answer(memo, bounded=False, state=state)

    assert "关键问题回应" in rendered
    assert "出口限制与中国暴露风险" in rendered
    assert "export restriction" in rendered
    assert "许可证" in rendered
    assert "方向性风险判断" in rendered
    assert "不能量化具体收入影响" in rendered
    assert "[C" not in rendered


def test_product_bridge_pack_is_converted_to_bounded_claim_cards() -> None:
    judgment = {
        "supported_claims": [
            {
                "claim_id": "existing_capex_claim",
                "agent_id": "fundamental_analyst",
                "claim": "AMZN/MSFT/GOOGL capex creates a demand-pool context.",
                "claim_type": "company_reported_financial_fact",
                "memo_slot": "fundamentals",
                "analysis_dimension": "capital_and_financing",
                "ticker_scope": ["AMZN", "MSFT", "GOOGL"],
                "metric_scope": ["capex"],
                "evidence_refs": ["ev_cloud_capex"],
                "source_families": ["primary_sec_filing"],
            }
        ],
        "source_agent_ids": ["fundamental_analyst"],
    }
    supervising_pack = {
        "product_bridge_pack": {
            "product_intelligence_pack_ref": {
                "packs": [
                    {
                        "pack_id": "pig_company_pack:NVDA",
                        "ticker": "NVDA",
                        "family_ids": ["gpu_accelerator", "networking"],
                        "counts": {"product_slot_count": 35, "technical_spec_count": 4, "customer_deployment_signal_count": 3},
                    }
                ]
            },
            "product_evidence_pack_ref": {
                "packs": [
                    {
                        "pack_id": "ai_semis_product_evidence_pack:NVDA",
                        "ticker": "NVDA",
                        "layer_statuses": {
                            "product_profile": "detailed_profile_ready",
                            "product_spec_architecture": "evidence_ready",
                            "customer_deployment_adoption": "evidence_ready",
                            "product_relationship_graph": "evidence_ready",
                        },
                    }
                ]
            },
            "company_disclosed_product_kpis": [
                {
                    "ticker": "DELL",
                    "metric_family": "product revenue",
                    "product_or_segment": "Servers and Networking",
                    "period_key": "FY2023",
                    "value": "20000000000.0 USD",
                    "evidence_refs": ["ev_dell_servers_networking_revenue"],
                }
            ],
            "official_product_context": [
                {
                    "ticker": "NVDA",
                    "product_family": "GPU / Accelerator",
                    "products_or_platforms": ["H100", "H200", "B200", "GB200", "Blackwell GPU architecture"],
                    "evidence_refs": ["ev_nvda_blackwell_product"],
                }
            ],
            "customer_deployment_context": [
                {
                    "ticker": "NVDA",
                    "signal": "NVIDIA public contract award context",
                    "evidence_refs": ["ev_nvda_public_deployment"],
                }
            ],
            "product_relationship_context": [
                {
                    "ticker": "NVDA",
                    "edge_type": "COMPONENT_INPUT_TO",
                    "from_node_id": "company_product_family:NVDA:gpu_accelerator",
                    "to_node_id": "company_product_family:DELL:server_oem",
                    "evidence_refs": ["ev_nvda_dell_component_edge"],
                }
            ],
        }
    }

    augmented = _judgment_with_product_bridge_claims(judgment, supervising_pack)
    claims = augmented["supported_claims"]
    claim_types = {claim["claim_type"] for claim in claims}
    text = " ".join(claim["claim"] for claim in claims)

    assert len(claims) >= 5
    assert augmented["source_agent_ids"] == ["fundamental_analyst", "supervising_analyst"]
    assert "company_reported_product_operating_fact" in claim_types
    assert "product_intelligence_graph_bounded_claim" in claim_types
    assert "customer_deployment_bounded_signal" in claim_types
    assert "product_relationship_graph_bounded_claim" in claim_types
    assert "Servers and Networking FY2023 $20B" in text
    assert "H100" in text and "Blackwell" in text
    assert "not prove SKU revenue" in text or "does not prove SKU revenue" in text
    assert "shipments" in text


def test_product_bridge_claims_refresh_into_thesis_and_dimension_plan() -> None:
    judgment = {
        "supported_claims": [
            {
                "claim_id": "fundamentals_nvda_data_center",
                "agent_id": "fundamental_analyst",
                "claim": "NVDA data center financial evidence supports AI infrastructure demand exposure.",
                "claim_type": "company_reported_financial_fact",
                "memo_slot": "fundamentals",
                "analysis_dimension": "fundamentals",
                "ticker_scope": ["NVDA"],
                "metric_scope": ["data_center_revenue"],
                "evidence_refs": ["ev_nvda_financial"],
                "source_families": ["primary_sec_filing"],
                "materiality": "high",
                "confidence": "high",
            }
        ],
        "source_agent_ids": ["fundamental_analyst"],
    }
    supervising_pack = {
        "product_bridge_pack": {
            "product_intelligence_pack_ref": {
                "packs": [{"pack_id": "pig_company_pack:NVDA", "ticker": "NVDA", "family_ids": ["gpu_accelerator"]}]
            },
            "product_evidence_pack_ref": {
                "packs": [
                    {
                        "pack_id": "ai_semis_product_evidence_pack:NVDA",
                        "ticker": "NVDA",
                        "layer_statuses": {"product_spec_architecture": "evidence_ready", "product_relationship_graph": "evidence_ready"},
                    }
                ]
            },
            "official_product_context": [
                {
                    "ticker": "NVDA",
                    "product_family": "GPU / Accelerator",
                    "products_or_platforms": ["H100", "B200", "Blackwell GPU architecture"],
                    "evidence_refs": ["ev_nvda_product_profile"],
                }
            ],
        }
    }

    augmented = _judgment_with_product_bridge_claims(judgment, supervising_pack)
    refreshed = refresh_judgment_plan_after_governance_filter(augmented)
    dimensions = {section["dimension_id"]: section for section in refreshed["thesis_driver_pack"]["dimension_sections"]}

    assert refreshed["thesis_synthesis"]["status"] == "synthesized"
    assert refreshed["supported_claims"][0]["claim_id"] == "judgment_plan_aggregator_thesis_1"
    assert "product_and_production" in dimensions
    assert "fundamentals" in dimensions
    assert any(card["memo_slot"] == "product_technology" for card in refreshed["thesis_driver_pack"]["driver_cards"])
    assert refreshed["memo_outline"][0]["memo_slot"] == "thesis"


def test_renderer_preserves_renderable_salvage_memo_when_verifier_fails() -> None:
    result = _node_multi_agent_renderer(
        {
            "claim_verification": {"status": "fail", "errors": ["memo_zh_response_field_not_chinese"]},
            "memo_answer": {
                "answer_status": "draft",
                "response_language": {"language": "zh-CN"},
                "direct_answer": "NVDA 和 DELL 的 AI 基础设施证据支持一个有边界的产品与需求判断。",
                "memo_claims": [
                    {
                        "claim_id": "c1",
                        "claim": "NVDA Blackwell 代际和 DELL AI server revenue 共同支持产品需求判断。",
                        "evidence_refs": ["ev_nvda", "ev_dell"],
                    }
                ],
                "memo_writer_diagnostics": {"deterministic_salvage_used": True},
            },
            "memo_logic_plan": {"validation": {"status": "pass"}},
        }
    )

    rendered = result["rendered_answer"]
    assert "Bounded answer only" not in rendered
    assert "核心判断" in rendered
    assert "关键论据" in rendered
    assert "NVDA" in rendered
    assert "DELL" in rendered


def test_memo_writer_prompt_uses_slot_balanced_v0_3_caps() -> None:
    claims = [
        {
            "claim_id": f"claim_{index}",
            "agent_id": "fundamental_analyst",
            "claim": f"Supported claim {index}.",
            "claim_type": "company_reported_financial_fact",
            "memo_slot": ["thesis", "fundamentals", "industry_relationship", "market_valuation", "risk_counterevidence"][index % 5],
            "evidence_refs": [f"ref_{index}"],
            "source_families": ["primary_sec_filing"],
            "materiality": "high",
        }
        for index in range(12)
    ]
    claims[0]["claim_type"] = "investment_thesis_synthesis"
    judgment = {
        "schema_version": "sec_agent_specialist_judgment_plan_v0.1",
        "status": "pass",
        "supported_claims": claims,
        "unsupported_claims": [
            {"agent_id": "risk_counterevidence_analyst", "claim": f"Unsupported {index}", "reason": "missing evidence"}
            for index in range(5)
        ],
        "conflicts": [
            {"agent_id": "risk_counterevidence_analyst", "claim": f"Conflict {index}", "reason": "mixed evidence"}
            for index in range(4)
        ],
        "memo_outline": [
            {"memo_slot": slot, "status": "supported"}
            for slot in ["thesis", "fundamentals", "industry_relationship", "market_valuation", "risk_counterevidence"]
        ],
        "memo_writer_allowed": True,
    }
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": "Supported claim 0.",
                        "memo_claims": [
                            {
                                "claim_id": "claim_0",
                                "claim": "Supported claim 0.",
                                "claim_type": "investment_thesis_synthesis",
                                "evidence_refs": ["ref_0"],
                                "source_families": ["primary_sec_filing"],
                            },
                            {
                                "claim_id": "claim_1",
                                "claim": "Supported claim 1.",
                                "evidence_refs": ["ref_1"],
                                "source_families": ["primary_sec_filing"],
                            },
                            {
                                "claim_id": "claim_2",
                                "claim": "Supported claim 2.",
                                "evidence_refs": ["ref_2"],
                                "source_families": ["primary_sec_filing"],
                            },
                        ],
                    }
                )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "Write a memo.",
            "verified_judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    payload = extract_json_object(fake.calls[0]["messages"][1]["content"]) or {}
    compact = payload["verified_judgment_plan"]
    assert result["memo_route_result"]["status"] == "pass"
    assert len(compact["supported_claims"]) == 5
    assert compact["supported_claims"][0]["claim_type"] == "company_reported_financial_fact"
    assert "investment_thesis_synthesis" in {row["claim_type"] for row in compact["supported_claims"]}
    assert len(compact["unsupported_claims"]) == 2
    assert len(compact["conflicts"]) == 2
    assert "memo_thesis_plan" in compact
    assert payload["memo_output_contract"]["memo_claims_max"] == 5
    assert payload["shared_memo_context"]["schema_version"] == "sec_agent_shared_memo_context_v0.2"
    assert payload["shared_memo_context"]["context_digest"].startswith("sha256:")


def test_memo_writer_prompt_uses_thesis_pack_as_projection_not_extra_payload() -> None:
    claims = [
        {
            "claim_id": f"claim_{index}",
            "agent_id": "fundamental_analyst",
            "claim": f"Supported claim {index}.",
            "claim_type": "company_reported_financial_fact",
            "memo_slot": "fundamentals",
            "evidence_refs": [f"ref_{index}"],
            "source_families": ["primary_sec_filing"],
            "materiality": "high",
            "claim_rank_score": 80 - index,
            "claim_rank_bucket": "memo_ready",
        }
        for index in range(6)
    ]
    judgment = {
        "schema_version": "sec_agent_specialist_judgment_plan_v0.1",
        "status": "pass",
        "supported_claims": claims,
        "memo_outline": [{"memo_slot": "fundamentals", "status": "supported"}],
        "memo_thesis_plan": {"schema_version": "sec_agent_memo_thesis_plan_v0.1", "status": "ready"},
        "memo_thesis_pack": {
            "schema_version": "sec_agent_memo_thesis_pack_v0.1",
            "status": "ready",
            "core_thesis": claims[0],
            "supporting_drivers": [{"memo_slot": "fundamentals", "driver": claims[1], "supporting_claim_count": 6}],
            "source_claim_refs": ["ref_0", "ref_1"],
        },
        "thesis_driver_pack": {
            "schema_version": "sec_agent_thesis_driver_pack_v0.1",
            "status": "ready",
            "present": True,
            "thesis_cards": [
                {
                    "thesis_id": "thesis_1",
                    "core_thesis": "Supported claim 0.",
                    "supporting_driver_ids": ["driver_claim_1"],
                    "evidence_refs": ["ref_0"],
                }
            ],
            "driver_cards": [
                {
                    "driver_id": "driver_claim_1",
                    "source_claim_id": "claim_1",
                    "memo_slot": "fundamentals",
                    "statement": "Supported claim 1.",
                    "evidence_refs": ["ref_1"],
                    "source_families": ["primary_sec_filing"],
                }
            ],
            "source_claim_refs": ["ref_0", "ref_1"],
        },
        "memo_writer_allowed": True,
    }
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": "Supported claim 0.",
                        "memo_claims": [
                            {
                                "claim_id": "claim_0",
                                "claim": "Supported claim 0.",
                                "evidence_refs": ["ref_0"],
                                "source_families": ["primary_sec_filing"],
                            },
                            {
                                "claim_id": "claim_1",
                                "claim": "Supported claim 1.",
                                "evidence_refs": ["ref_1"],
                                "source_families": ["primary_sec_filing"],
                            },
                            {
                                "claim_id": "claim_2",
                                "claim": "Supported claim 2.",
                                "evidence_refs": ["ref_2"],
                                "source_families": ["primary_sec_filing"],
                            },
                        ],
                    "memo_thesis_plan": judgment["memo_thesis_plan"],
                    "memo_generation_policy": "thesis_led_claim_cards_v0_1",
                }
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "Write a memo.",
            "verified_judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    payload = extract_json_object(fake.calls[0]["messages"][1]["content"]) or {}
    compact = payload["verified_judgment_plan"]
    assert result["memo_route_result"]["status"] == "pass"
    assert compact["memo_thesis_pack"]["schema_version"] == "sec_agent_memo_thesis_pack_v0.1"
    assert compact["thesis_driver_pack"]["schema_version"] == "sec_agent_thesis_driver_pack_v0.1"
    assert payload["memo_output_contract"]["do_not_emit_thesis_driver_pack"] is True
    assert result["memo_answer"]["thesis_driver_pack"]["driver_cards"][0]["source_claim_id"] == "claim_1"
    assert len(compact["supported_claims"]) == 0


def test_memo_writer_uses_expanded_profile_for_standard_memo_with_dense_claims() -> None:
    claims = [
        {
            "claim_id": f"claim_{index}",
            "agent_id": "fundamental_analyst",
            "claim": f"Supported investment claim {index}.",
            "claim_type": "company_reported_financial_fact",
            "memo_slot": ["thesis", "fundamentals", "market_valuation", "risk_counterevidence", "fundamentals"][index % 5],
            "evidence_refs": [f"ref_{index}"],
            "source_families": ["primary_sec_filing" if index % 2 else "market_snapshot"],
            "materiality": "high",
            "claim_rank_score": 80,
            "claim_rank_bucket": "memo_ready",
        }
        for index in range(1, 7)
    ]
    claims[0]["claim_type"] = "investment_thesis_synthesis"
    judgment = {
        "schema_version": "sec_agent_specialist_judgment_plan_v0.1",
        "status": "pass",
        "supported_claims": claims,
        "memo_outline": [{"memo_slot": "fundamentals", "status": "supported"}],
        "claim_card_stats": {"supported_claim_count": 6, "memo_ready_claim_count": 5, "memo_slot_supported_count": 4},
        "memo_thesis_plan": {"schema_version": "sec_agent_memo_thesis_plan_v0.1", "status": "ready"},
        "memo_thesis_pack": {
            "schema_version": "sec_agent_memo_thesis_pack_v0.1",
            "status": "ready",
            "core_thesis": claims[0],
            "supporting_drivers": [{"memo_slot": "fundamentals", "driver": claims[1], "supporting_claim_count": 3}],
            "source_claim_refs": ["ref_1", "ref_2"],
        },
        "memo_writer_allowed": True,
    }
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": " ".join(["Supported profile answer."] * 25),
                    "memo_claims": [
                        {
                            "claim_id": f"claim_{index}",
                            "claim": f"Supported investment claim {index}.",
                            "evidence_refs": [f"ref_{index}"],
                            "source_families": ["primary_sec_filing"],
                        }
                        for index in range(1, 6)
                    ],
                    "investment_implications": [{"text": "Position sizing depends on supported claim density.", "evidence_refs": ["ref_1"]}],
                    "what_would_change_view": [{"text": "Missing metric evidence would weaken the view."}],
                    "monitoring_items": [{"text": "Track next filing metrics.", "evidence_refs": ["ref_2"]}],
                    "evidence_gaps_but_actionable": [{"text": "Some peer metrics remain bounded by local evidence."}],
                    "memo_thesis_plan": judgment["memo_thesis_plan"],
                    "memo_generation_policy": "thesis_led_claim_cards_v0_1",
                }
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "Write a standard memo.",
            "agent_activation_plan": {"execution_mode": "standard_memo"},
            "verified_judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    payload = extract_json_object(fake.calls[0]["messages"][1]["content"]) or {}
    compact = payload["verified_judgment_plan"]
    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_answer"]["memo_profile"]["profile"] == "expanded"
    assert payload["memo_output_contract"]["direct_answer_max_chars"] == 1200
    assert payload["memo_output_contract"]["memo_claims_max"] == 8
    assert len(compact["supported_claims"]) == 6
    assert result["memo_answer"]["investment_implications"]


def test_memo_writer_prompt_exports_surface_caps_and_normalizes_deep_research_width() -> None:
    claims = [
        {
            "claim_id": f"claim_{index}",
            "claim": f"Dense supported claim {index}.",
            "claim_type": "business_observation",
            "memo_slot": ["thesis", "fundamentals", "industry_relationship", "market_valuation", "risk_counterevidence"][index % 5],
            "evidence_refs": [f"ref_{index}"],
            "source_families": [["primary_sec_filing"], ["market_snapshot"], ["industry_snapshot"], ["relationship_graph"]][index % 4],
            "claim_rank_bucket": "memo_ready",
        }
        for index in range(1, 8)
    ]
    judgment = {
        "schema_version": "sec_agent_specialist_judgment_plan_v0.1",
        "status": "pass",
        "supported_claims": claims,
        "claim_card_stats": {"supported_claim_count": 7, "memo_ready_claim_count": 6, "memo_slot_supported_count": 4},
        "memo_thesis_plan": {"schema_version": "sec_agent_memo_thesis_plan_v0.1", "status": "ready"},
        "memo_thesis_pack": {"schema_version": "sec_agent_memo_thesis_pack_v0.1", "status": "ready"},
        "memo_writer_allowed": True,
    }
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": (
                        "The evidence package supports a thesis-led read because the financial, product, market, and risk signals "
                        "point to the same operating path. Product evidence frames adoption quality, financial evidence anchors the "
                        "cash and margin bridge, market evidence checks whether expectations are already reflected, and risk evidence "
                        "keeps the conclusion bounded to verified claim cards rather than unverified extrapolation."
                    ),
                    "dimension_analyses": [
                        {
                            "dimension_id": [
                                "fundamentals",
                                "product_and_production",
                                "industry_supply_chain",
                                "competition_and_market_position",
                                "risk_and_counterevidence",
                                "capital_and_financing",
                            ][index - 1],
                            "title": f"Dimension {index}",
                            "summary": "S" * 900,
                            "business_mechanism": "M" * 600,
                            "financial_bridge": "F" * 600,
                            "counter_read": "C" * 600,
                            "claim_ids": [f"claim_{index}"],
                            "evidence_refs": [f"ref_{index}"],
                        }
                        for index in range(1, 7)
                    ],
                    "memo_claims": [
                        {"claim_id": f"claim_{index}", "claim": f"Dense supported claim {index}.", "evidence_refs": [f"ref_{index}"]}
                        for index in range(1, 7)
                    ],
                    "investment_implications": [{"text": f"Implication {index}.", "evidence_refs": [f"ref_{index}"]} for index in range(1, 6)],
                    "what_would_change_view": [{"text": f"Change view {index}."} for index in range(1, 6)],
                    "monitoring_items": [{"text": f"Monitor {index}.", "evidence_refs": [f"ref_{index}"]} for index in range(1, 6)],
                    "evidence_gaps_but_actionable": [{"text": f"Gap {index}."} for index in range(1, 6)],
                    "memo_thesis_plan": judgment["memo_thesis_plan"],
                    "memo_generation_policy": "thesis_led_claim_cards_v0_1",
                }
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "Write a deep research memo.",
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "verified_judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    payload = extract_json_object(fake.calls[0]["messages"][1]["content"]) or {}
    caps = payload["memo_output_contract"]["surface_caps"]
    memo = result["memo_answer"]
    assert result["memo_route_result"]["status"] == "pass"
    assert memo["memo_profile"]["profile"] == "deep_research"
    assert caps["dimension_analyses_max"] == 5
    assert len(memo["dimension_analyses"]) == 5
    assert len(memo["investment_implications"]) <= caps["investment_implications_max"]
    assert len(memo["what_would_change_view"]) <= caps["what_would_change_view_max"]
    assert len(memo["monitoring_items"]) <= caps["monitoring_items_max"]
    assert len(memo["evidence_gaps_but_actionable"]) <= caps["evidence_gaps_but_actionable_max"]
    assert len(memo["dimension_analyses"][0]["summary"]) <= caps["dimension_summary_max_chars"]
    assert len(memo["dimension_analyses"][0]["business_mechanism"]) <= caps["dimension_detail_max_chars"]


def test_memo_writer_completes_claim_and_required_dimension_contract_from_verified_judgment() -> None:
    dimension_ids = [
        "fundamentals",
        "product_and_production",
        "capital_and_financing",
        "competition_and_market_position",
        "industry_supply_chain",
        "risk_and_counterevidence",
        "evidence_gap",
    ]
    claims = [
        {
            "claim_id": f"claim_{index}",
            "claim": f"Verified claim {index} supports a distinct analyst dimension with traceable evidence.",
            "claim_type": "business_observation",
            "memo_slot": {
                "fundamentals": "fundamentals",
                "product_and_production": "product_technology",
                "capital_and_financing": "capital_allocation",
                "competition_and_market_position": "market_valuation",
                "industry_supply_chain": "industry_relationship",
                "risk_and_counterevidence": "risk_counterevidence",
                "evidence_gap": "risk_counterevidence",
            }[dimension_ids[index - 1]],
            "analysis_dimension": dimension_ids[index - 1],
            "evidence_refs": [f"ref_{index}"],
            "source_families": [["primary_sec_filing"], ["company_product_evidence_graph"], ["market_snapshot"]][index % 3],
            "claim_rank_bucket": "memo_ready",
        }
        for index in range(1, 8)
    ]
    sections = [
        {
            "dimension_id": dimension,
            "dimension_title": f"Dimension {dimension}",
            "required_by_user": dimension in {"industry_supply_chain", "risk_and_counterevidence"},
            "status": "supported",
            "section_thesis": f"{dimension} has verified support and must be carried into the final memo.",
            "analysis_lens": f"{dimension} lens compares evidence strength and boundary.",
            "business_mechanism": f"{dimension} mechanism links the evidence to business quality.",
            "financial_bridge": f"{dimension} bridge links the evidence to revenue, margin, cash flow, or valuation.",
            "competitive_read": f"{dimension} competitive read identifies the relative implication.",
            "counter_read": f"{dimension} counter-read states what could weaken the inference.",
            "primary_claim_ids": [f"claim_{index}"],
            "evidence_refs": [f"ref_{index}"],
        }
        for index, dimension in enumerate(dimension_ids, start=1)
    ]
    judgment = {
        "schema_version": "sec_agent_specialist_judgment_plan_v0.1",
        "status": "pass",
        "supported_claims": claims,
        "claim_card_stats": {"supported_claim_count": 7, "memo_ready_claim_count": 7, "memo_slot_supported_count": 6},
        "memo_thesis_plan": {
            "schema_version": "sec_agent_memo_thesis_plan_v0.1",
            "status": "ready",
            "primary_thesis_claim_id": "claim_1",
            "primary_thesis": "Verified thesis is ready.",
            "thesis_direction": "mixed_positive",
        },
        "memo_thesis_pack": {"schema_version": "sec_agent_memo_thesis_pack_v0.1", "status": "ready"},
        "thesis_driver_pack": {"dimension_sections": sections},
        "required_dimension_ids": ["industry_supply_chain", "risk_and_counterevidence"],
        "memo_writer_allowed": True,
    }
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": (
                            "The current evidence supports a thesis-led view rather than an evidence inventory: financial, product, "
                            "capital-market, supply-chain, competitive, and risk signals are already organized into traceable dimensions, "
                            "so the memo should explain how each dimension changes conviction. The core read is that company-reported "
                            "financial facts anchor the base case, product and production evidence explains whether the business can "
                            "turn demand into deployable capability, capital and liquidity context frames the funding and market-pricing "
                            "environment, and risk/counterevidence limits how far the thesis can be extrapolated. The strongest conclusion "
                            "is not merely that evidence exists; it is that the business bridge, financial bridge, and counter-read must be "
                            "read together before assigning conviction. If a dimension only has context or proxy evidence, it should remain "
                            "bounded and visible, while dimensions with issuer-reported facts and traceable evidence should drive the memo order. "
                            "This is the minimum acceptable deep-research surface because the reader can see what is proven, what is inferred, "
                            "what would change the view, and which evidence path should be audited next."
                        ),
                    "dimension_analyses": [
                        {
                            "dimension_id": dimension,
                            "title": f"Dimension {dimension}",
                            "summary": f"{dimension} summary from model output.",
                            "business_mechanism": f"{dimension} mechanism from model output.",
                            "financial_bridge": f"{dimension} bridge from model output.",
                            "counter_read": f"{dimension} counter-read from model output.",
                            "claim_ids": [f"claim_{index}"],
                            "evidence_refs": [f"ref_{index}"],
                        }
                        for index, dimension in enumerate(dimension_ids[:3], start=1)
                    ],
                    "memo_claims": [
                        {"claim_id": f"claim_{index}", "claim": f"Verified claim {index}.", "evidence_refs": [f"ref_{index}"]}
                        for index in range(1, 6)
                    ],
                    "investment_implications": [{"text": "Positioning should reflect verified thesis strength.", "evidence_refs": ["ref_1"]}],
                    "what_would_change_view": [{"text": "New contrary evidence would reduce conviction.", "evidence_refs": ["ref_6"]}],
                    "monitoring_items": [{"text": "Track the missing and competing evidence paths.", "evidence_refs": ["ref_5"]}],
                    "memo_thesis_plan": judgment["memo_thesis_plan"],
                    "memo_generation_policy": "thesis_led_claim_cards_v0_1",
                }
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "Write a deep research memo.",
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "verified_judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    memo = result["memo_answer"]
    diagnostics = memo.get("memo_writer_diagnostics") or {}
    dimension_ids_out = {str(item.get("dimension_id") or "") for item in memo["dimension_analyses"]}
    claim_ids_out = {str(item.get("claim_id") or "") for item in memo["memo_claims"]}
    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_route_result"]["attempt_count"] == 1
    assert not result["memo_route_result"].get("deterministic_salvage_used")
    assert diagnostics["memo_claims_completed_from_verified_judgment"] == 1
    assert diagnostics["dimension_analyses_completed_from_verified_judgment"] >= 1
    assert {"industry_supply_chain", "risk_and_counterevidence"}.issubset(dimension_ids_out)
    assert len(claim_ids_out) >= 6
    assert "claim_6" in claim_ids_out


def test_memo_writer_contract_completion_localizes_zh_required_dimensions() -> None:
    dimension_ids = [
        "fundamentals",
        "product_and_production",
        "industry_supply_chain",
        "risk_and_counterevidence",
    ]
    claims = [
        {
            "claim_id": f"claim_{index}",
            "claim": f"已验证论据 {index} 支撑该维度的判断，并保留可追溯证据。",
            "claim_type": "business_observation",
            "memo_slot": ["fundamentals", "product_technology", "industry_relationship", "risk_counterevidence"][index % 4],
            "analysis_dimension": dimension_ids[(index - 1) % len(dimension_ids)],
            "evidence_refs": [f"ref_{index}"],
            "source_families": [["primary_sec_filing"], ["company_product_evidence_graph"], ["market_snapshot"]][index % 3],
            "claim_rank_bucket": "memo_ready",
        }
        for index in range(1, 8)
    ]
    sections = [
        {
            "dimension_id": dimension,
            "dimension_title": f"Dimension {dimension}",
            "required_by_user": dimension in {"industry_supply_chain", "risk_and_counterevidence"},
            "status": "supported",
            "section_thesis": f"{dimension} has verified support and must be carried into the Chinese memo.",
            "analysis_lens": f"{dimension} lens compares evidence strength and boundary.",
            "business_mechanism": f"{dimension} mechanism links evidence to business quality.",
            "financial_bridge": f"{dimension} bridge links evidence to revenue, margin, cash flow, or valuation.",
            "competitive_read": f"{dimension} competitive read identifies the relative implication.",
            "counter_read": f"{dimension} counter-read states what could weaken the inference.",
            "primary_claim_ids": [claims[index - 1]["claim_id"]],
            "evidence_refs": [f"ref_{index}"],
        }
        for index, dimension in enumerate(dimension_ids, start=1)
    ]
    judgment = {
        "schema_version": "sec_agent_specialist_judgment_plan_v0.1",
        "status": "pass",
        "supported_claims": claims,
        "claim_card_stats": {"supported_claim_count": 7, "memo_ready_claim_count": 7, "memo_slot_supported_count": 4},
        "memo_thesis_plan": {"schema_version": "sec_agent_memo_thesis_plan_v0.1", "status": "ready"},
        "memo_thesis_pack": {"schema_version": "sec_agent_memo_thesis_pack_v0.1", "status": "ready"},
        "thesis_driver_pack": {"dimension_sections": sections},
        "required_dimension_ids": ["industry_supply_chain", "risk_and_counterevidence"],
        "memo_writer_allowed": True,
    }
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": (
                        "当前证据已经能形成分维度判断：财务锚点、产品证据、供应链传导和风险反证需要一起看，不能只停留在缺口说明。"
                        "主线应先回答公司披露事实能支持什么，再说明产品和客户部署是否让这些事实具有业务含义。"
                        "如果财务证据显示收入、毛利或现金流存在锚点，writer 需要把它和产品线、客户采用、供应链约束连接起来，"
                        "而不是把它写成孤立表格摘要。产品证据如果只有规格、产品页或图谱边，也仍可支持产品能力、代际和竞争定位，"
                        "但不能冒充 SKU revenue、份额或订单金额。供应链证据要说明需求从客户 capex、OEM 配置、关键零部件和产能瓶颈如何传导，"
                        "同时标明哪些边只是 scope hypothesis。风险反证必须作为主判断折价项，包括客户集中、margin dilution、出口限制、周期消化和 parser gap。"
                        "最终备忘录应让 reviewer 能一眼看到：哪些判断已经被证据支持，哪些只是有边界推断，哪些缺口会改变结论。"
                        "如果某个 required item 没被覆盖，系统要能追踪是缺数据、parser 没吃到、specialist 没回答，还是 writer 没正确投影。"
                        "如果有证据却写成没有证据，必须直接 fail 并暴露 claim_id、evidence_ref 和丢失节点。"
                        "如果只有 source coverage 或 scope hypothesis，则应保留为边界或低置信背景，不能冒充主判断。"
                        "因此这个开头不是结论包装，而是把研究路径、证据层级、可提权边界和 reviewer 审计入口同时交代清楚。"
                    ),
                    "dimension_analyses": [
                        {
                            "dimension_id": "fundamentals",
                            "title": "基本面",
                            "summary": "基本面证据可以作为判断锚点。",
                            "business_mechanism": "业务机制来自已验证财务证据。",
                            "financial_bridge": "财务传导连接收入、毛利和现金流质量。",
                            "counter_read": "反证是口径或周期变化会削弱判断。",
                            "claim_ids": ["claim_1"],
                            "evidence_refs": ["ref_1"],
                        }
                    ],
                    "memo_claims": [
                        {"claim_id": f"claim_{index}", "claim": f"已验证论据 {index} 可用于最终备忘录。", "evidence_refs": [f"ref_{index}"]}
                        for index in range(1, 7)
                    ],
                    "investment_implications": [{"text": "投资含义应围绕已验证的业务传导链排序。", "evidence_refs": ["ref_1"]}],
                    "what_would_change_view": [{"text": "如果后续证据否定供应链传导，判断需要下修。", "evidence_refs": ["ref_3"]}],
                    "monitoring_items": [{"text": "继续跟踪产品、客户部署和风险反证。", "evidence_refs": ["ref_4"]}],
                    "memo_thesis_plan": judgment["memo_thesis_plan"],
                    "memo_generation_policy": "thesis_led_claim_cards_v0_1",
                }
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "请用中文写一份 AI 基础设施研究备忘录。",
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "verified_judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=_config(),
        call_chat_completion=fake,
    )

    memo = result["memo_answer"]
    dimensions = memo["dimension_analyses"]
    assert result["memo_route_result"]["status"] == "pass"
    assert not result["memo_route_result"].get("deterministic_salvage_used")
    assert {"industry_supply_chain", "risk_and_counterevidence"}.issubset({row["dimension_id"] for row in dimensions})
    for row in dimensions:
        for key in ("summary", "business_mechanism", "financial_bridge", "counter_read"):
            text = str(row.get(key) or "")
            assert any("\u4e00" <= char <= "\u9fff" for char in text), (row.get("dimension_id"), key, text)


def test_memo_writer_salvage_preserves_counterevidence_dimension_from_verified_judgment() -> None:
    judgment = {
        "schema_version": "sec_agent_specialist_judgment_plan_v0.1",
        "status": "pass",
        "supported_claims": [
            {
                "claim_id": "claim_fund_1",
                "claim": "DELL reported AI server revenue context that anchors the fundamental bridge.",
                "claim_type": "company_reported_financial_fact",
                "memo_slot": "fundamentals",
                "analysis_dimension": "fundamentals",
                "evidence_refs": ["fund_ref_1"],
                "source_families": ["primary_sec_filing"],
                "claim_rank_bucket": "memo_ready",
            }
        ],
        "claim_card_stats": {"supported_claim_count": 1, "memo_ready_claim_count": 1, "memo_slot_supported_count": 1},
        "memo_thesis_plan": {
            "schema_version": "sec_agent_memo_thesis_plan_v0.1",
            "status": "ready",
            "primary_thesis_claim_id": "claim_fund_1",
            "primary_thesis": "AI server quality needs a margin and counterevidence bridge.",
            "thesis_direction": "mixed",
        },
        "memo_thesis_pack": {"schema_version": "sec_agent_memo_thesis_pack_v0.1", "status": "ready"},
        "thesis_driver_pack": {
            "dimension_sections": [
                {
                    "dimension_id": "fundamentals",
                    "dimension_title": "Fundamentals",
                    "required_by_user": True,
                    "status": "supported",
                    "section_thesis": "The fundamental bridge is anchored by issuer evidence.",
                    "business_mechanism": "Revenue and margin evidence anchor the operating quality read.",
                    "financial_bridge": "Bridge through revenue and margin quality.",
                    "primary_claim_ids": ["claim_fund_1"],
                    "evidence_refs": ["fund_ref_1"],
                },
                {
                    "dimension_id": "risk_and_counterevidence",
                    "dimension_title": "Risk and counterevidence",
                    "required_by_user": True,
                    "status": "gap_or_counterevidence",
                    "section_thesis": "Comparable-margin and order visibility caveats limit conviction.",
                    "business_mechanism": "Counterevidence constrains whether demand can be treated as profitable revenue.",
                    "financial_bridge": "Do not infer AI server margin uplift without comparable margin evidence.",
                    "counter_read": "Gross margin mix and order visibility can break the thesis.",
                    "counter_claim_ids": ["counter_conflict_1"],
                    "counter_driver_ids": ["counter_conflict_1"],
                    "what_would_change_view": ["Comparable AI server margin evidence would raise conviction."],
                },
            ]
        },
        "required_dimension_ids": ["fundamentals", "risk_and_counterevidence"],
        "memo_writer_allowed": True,
    }
    fake = _FakeChat([{"content": "not-json", "finish_reason": "stop", "output_tokens": 12}])
    result = route_memo_writer_llm(
        {
            "user_query": "请写 AI server margin 的风险反证。",
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "verified_judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
            "memo_logic_plan": {
                "section_order": ["fundamentals", "risk_and_counterevidence"],
                "required_item_answer_plan": [],
            },
            "multi_agent_context": {"response_language": "zh-CN"},
        },
        config=MemoLLMConfig(
            llm_backend="unit",
            base_url="http://unit.test",
            chat_completions_path="/chat/completions",
            model="unit-model",
            api_key_env="UNIT_API_KEY",
            max_repair_attempts=0,
        ),
        call_chat_completion=fake,
    )

    memo = result["memo_answer"]
    dimension_ids = [row["dimension_id"] for row in memo["dimension_analyses"]]
    risk_row = next(row for row in memo["dimension_analyses"] if row["dimension_id"] == "risk_and_counterevidence")
    assert result["memo_route_result"]["deterministic_salvage_used"] is True
    assert dimension_ids.count("risk_and_counterevidence") == 1
    assert "risk_and_counterevidence" in dimension_ids
    assert risk_row["counter_driver_ids"] == ["counter_conflict_1"]
    assert risk_row["counter_read"]
    assert risk_row["what_would_change_view"]


def test_shared_memo_context_selects_deep_research_profile_when_evidence_dense() -> None:
    claims = [
        {
            "claim_id": f"claim_{index}",
            "claim": f"Dense claim {index}.",
            "claim_type": "business_observation",
            "memo_slot": ["thesis", "fundamentals", "industry_relationship", "market_valuation", "risk_counterevidence"][index % 5],
            "evidence_refs": [f"ref_{index}"],
            "source_families": [["primary_sec_filing"], ["market_snapshot"], ["industry_snapshot"], ["relationship_graph"]][index % 4],
            "claim_rank_bucket": "memo_ready",
        }
        for index in range(1, 8)
    ]
    context = build_shared_memo_context(
        {
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "verified_judgment_plan": {
                "supported_claims": claims,
                "claim_card_stats": {"supported_claim_count": 7, "memo_ready_claim_count": 6, "memo_slot_supported_count": 4},
                "memo_thesis_plan": {"status": "ready"},
                "memo_thesis_pack": {"status": "ready"},
            },
        }
    )

    assert context["memo_profile"]["profile"] == "deep_research"
    assert context["memo_profile"]["memo_claims_max"] == 8
    assert context["memo_profile"]["memo_claims_min_when_thesis_ready"] == 6
    assert context["memo_profile"]["supported_claim_cap_with_thesis_pack"] == 8


def test_shared_memo_context_recovers_gold_case_language_and_profile_from_case_contract() -> None:
    claims = [
        {
            "claim_id": f"claim_{index}",
            "claim": f"Dense claim {index}.",
            "claim_type": "business_observation",
            "memo_slot": ["thesis", "fundamentals", "industry_relationship", "market_valuation", "risk_counterevidence"][index % 5],
            "evidence_refs": [f"ref_{index}"],
            "source_families": [["primary_sec_filing"], ["market_snapshot"], ["industry_snapshot"], ["relationship_graph"]][index % 4],
            "claim_rank_bucket": "memo_ready",
        }
        for index in range(1, 8)
    ]
    context = build_shared_memo_context(
        {
            "case_contract": {
                "case_id": "p33_3_ai_semis_accelerator_dell_gold_case_v0_1",
                "prompt": "围绕 NVDA、AMD、GOOGL TPU 与 DELL AI server，判断客户部署、供应链和 margin quality。",
                "required_answer_moves": [
                    "Start with a clear bounded thesis.",
                    "Explain product/architecture advantage.",
                    "Bridge deployment and cloud capex.",
                    "Assess DELL AI server margin quality.",
                    "Map supply-chain dependencies.",
                    "Separate facts, proxies and gaps.",
                    "State counter-thesis.",
                ],
                "required_dimensions": [
                    "opening_thesis",
                    "fundamentals",
                    "product_architecture",
                    "customer_deployment",
                    "industry_supply_chain",
                    "capital_market_feedback",
                    "counter_thesis_and_what_would_change",
                ],
                "eval_focus": ["p33_gold_workpaper_quality"],
                "focus_tickers": ["NVDA", "DELL"],
                "search_scope_tickers": ["NVDA", "DELL", "AMD", "GOOGL"],
            },
            "verified_judgment_plan": {
                "supported_claims": claims,
                "claim_card_stats": {"supported_claim_count": 7, "memo_ready_claim_count": 6, "memo_slot_supported_count": 4},
                "memo_thesis_plan": {"status": "ready"},
                "memo_thesis_pack": {"status": "ready"},
            },
        }
    )

    assert context["user_query"].startswith("围绕 NVDA")
    assert context["response_language"]["language"] == "zh-CN"
    assert context["execution_mode"] == "deep_research"
    assert context["memo_profile"]["profile"] == "deep_research"
    assert context["focus_tickers"] == ["NVDA", "DELL"]


def test_deep_research_prompt_preserves_required_answer_contract_width() -> None:
    profile = _memo_profile_spec_from_name("deep_research")
    budget = _memo_writer_budget_spec_from_profile(profile)
    plan = {
        "schema_version": "finsight_memo_logic_plan_v0_1",
        "plan_id": "test_plan",
        "memo_intent": "answer_first_deep_research",
        "section_order": [
            "fundamentals",
            "product_and_production",
            "capital_and_financing",
            "competition_and_market_position",
            "industry_supply_chain",
            "risk_and_counterevidence",
            "evidence_gap",
        ],
        "sections": [
            {"section_id": section_id, "title": section_id, "required_item_ids": [f"item_{index}"]}
            for index, section_id in enumerate(
                [
                    "fundamentals",
                    "product_and_production",
                    "capital_and_financing",
                    "competition_and_market_position",
                    "industry_supply_chain",
                    "risk_and_counterevidence",
                    "evidence_gap",
                ],
                start=1,
            )
        ],
        "required_item_answer_plan": [
            {
                "question_item_id": f"required_item_{index}",
                "dimension": "fundamentals" if index % 2 else "product_and_production",
                "answer_role": "bounded_judgment",
                "answer_first_judgment_prompt": f"Answer item {index}",
                "evidence_bridge_prompt": f"Bridge item {index}",
                "counter_read_prompt": f"Counter item {index}",
                "what_would_change_prompt": f"Change item {index}",
            }
            for index in range(1, 11)
        ],
        "validation": {"status": "pass"},
    }

    compact = _compact_memo_logic_plan_for_writer_prompt(plan, budget=budget)

    assert len(compact["required_item_answer_plan"]) == 10
    assert [row["question_item_id"] for row in compact["required_item_answer_plan"]][-1] == "required_item_10"
    assert len(compact["section_order"]) == 7
    assert compact["section_order"][-1] == "evidence_gap"


def test_shared_memo_context_carries_scope_without_raw_rows() -> None:
    context = build_shared_memo_context(
        {
            "user_query": "Write an AI capex memo.",
            "query_contract": {"focus_tickers": ["NVDA"], "search_scope_tickers": ["NVDA", "AMD"]},
            "agent_activation_plan": {"execution_mode": "deep_research", "allowed_source_families": ["primary_sec_filing"]},
            "runtime_ledger_rows": [{"metric_id": "ledger_ref_1"}],
            "context_rows": [{"evidence_ref": "context_ref_1"}],
            "bounded_gap_register": {
                "schema_version": "sec_agent_bounded_gap_register_v0.1",
                "gap_count": 1,
                "gaps": [
                    {
                        "gap_id": "gap_channel_inventory",
                        "source_family": "public_source_context",
                        "gap_type": "commercial_tracker_gap",
                        "ticker": "NVDA",
                        "metric": "channel_inventory",
                        "repairability": "commercial_tracker_required",
                    }
                ],
                "summary": {"commercial_tracker_gap_count": 1},
            },
            "specialist_route_results": [
                {"agent_id": "fundamental_analyst", "status": "pass"},
                {"agent_id": "risk_counterevidence_analyst", "status": "fail"},
            ],
            "verified_judgment_plan": {
                "claim_card_stats": {
                    "supported_claim_count": 3,
                    "memo_ready_claim_count": 2,
                    "memo_slot_supported_count": 2,
                }
            },
        }
    )

    assert context["execution_mode"] == "deep_research"
    assert context["source_boundaries"]["ledger_row_count"] == 1
    assert context["source_boundaries"]["raw_rows_excluded_from_prompt"] is True
    assert context["source_boundaries"]["private_operator_context_excluded"] is True
    assert context["bounded_gap_register"]["gap_refs"][0]["gap_id"] == "gap_channel_inventory"
    assert context["bounded_gap_register"]["claim_policy"] == "bounded_gaps_may_be_disclosed_as_missing_evidence_but_not_used_as_supporting_facts"
    assert context["prompt_policy"]["allowed_input_views"] == [
        "shared_memo_context",
        "supervising_analyst_pack",
        "memo_logic_plan",
        "verified_judgment_plan",
        "specialist_verification",
    ]
    assert context["prompt_policy"]["bounded_evidence_rows"] == "excluded"
    assert context["specialist_routes"]["passed_agents"] == ["fundamental_analyst"]
    assert context["specialist_routes"]["failed_agents"] == ["risk_counterevidence_analyst"]
    assert context["claim_card_stats"]["memo_ready_claim_count"] == 2
    assert context["context_digest"].startswith("sha256:")
    serialized = json.dumps(context, ensure_ascii=False)
    assert "bounded_evidence_rows" not in serialized or '"bounded_evidence_rows": "excluded"' in serialized


def test_memo_env_router_returns_none_for_mock_mode() -> None:
    assert memo_writer_from_env({MEMO_ROUTER_ENV: "mock"}) is None
    assert verifier_from_env({MEMO_ROUTER_ENV: "mock"}) is None


def test_verifier_llm_cannot_override_deterministic_fail() -> None:
    result = route_verifier_llm(
        {
            **_state(),
            "memo_answer": {
                "answer_status": "draft",
                "raw_rows_consumed": True,
                "memo_claims": [{"claim": "No refs."}],
            },
        },
        config=_config(),
        call_chat_completion=_FakeChat([json.dumps({"status": "pass", "errors": []})]),
    )

    assert result["claim_verification"]["status"] == "fail"
    assert result["claim_verification"]["llm_verifier_skipped"] == "deterministic_gate_failed"


def test_memo_writer_route_ignores_stale_verification_block_after_pre_memo_claim_refresh() -> None:
    judgment = refresh_judgment_plan_after_governance_filter(
        {
            "schema_version": "sec_agent_judgment_plan_v0.1",
            "supported_claims": [
                {
                    "claim_id": "pre_memo_fact_claim:klac_patterning",
                    "agent_id": "pre_memo_fact_selector",
                    "claim": "KLAC reported Patterning revenue of $1.74B.",
                    "claim_type": "company_reported_financial_fact",
                    "memo_slot": "product_technology",
                    "evidence_refs": ["klac_patterning_ref"],
                    "source_families": ["primary_sec_filing"],
                    "confidence": "high",
                    "materiality": "high",
                }
            ],
            "unsupported_claims": [
                {
                    "agent_id": "fundamental_analyst",
                    "type": "specialist_route_failed",
                    "claim": "fundamental_analyst did not produce accepted specialist output.",
                    "reason": "provider_error: insufficient balance",
                }
            ],
            "conflicts": [],
            "blocked_specialist_agents": ["fundamental_analyst"],
            "memo_constraints": {
                "memo_writer_allowed": False,
                "blocked_reasons": ["unsupported_specialist_claims_without_supported_claims"],
            },
            "memo_writer_allowed": False,
        }
    )
    stale_verification = {
        "status": "fail",
        "memo_writer_allowed": False,
        "blocked_reasons": ["unsupported_specialist_claims_without_supported_claims"],
        "verified_judgment_plan": {"supported_claims": [], "unsupported_claims": judgment["unsupported_claims"]},
    }
    fake = _FakeChat(
        [
            json.dumps(
                {
                    "answer_status": "draft",
                    "direct_answer": "KLAC 的 Patterning 收入提供了产品线收入锚点，但供应链专家调用失败需要作为范围边界处理。",
                    "memo_claims": [
                        {
                            "claim_id": "pre_memo_fact_claim:klac_patterning",
                            "claim": "KLAC reported Patterning revenue of $1.74B.",
                            "evidence_refs": ["klac_patterning_ref"],
                            "source_families": ["primary_sec_filing"],
                        }
                    ],
                }
            )
        ]
    )

    result = route_memo_writer_llm(
        {
            "user_query": "分析 ASML/AMAT/LRCX/KLAC 的 semicap cycle。",
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": stale_verification,
        },
        config=_config(),
        call_chat_completion=fake,
    )

    assert fake.calls
    assert result["memo_route_result"]["status"] == "pass"
    assert result["memo_answer"]["answer_status"] == "draft"
    assert result["memo_answer"]["memo_claims"][0]["claim_id"] == "pre_memo_fact_claim:klac_patterning"


def test_verifier_llm_downgrades_bounded_block_completeness_failure() -> None:
    result = route_verifier_llm(
        {
            **_state(),
            "memo_answer": {
                "answer_status": "blocked_by_specialist_verification",
                "direct_answer": "Evidence constraints blocked full memo generation.",
                "raw_rows_consumed": False,
                "tool_calls_requested": [],
                "memo_claims": [],
                "bounded_answer_allowed": True,
            },
        },
        config=_config(),
        call_chat_completion=_FakeChat([json.dumps({"status": "fail", "errors": [{"type": "insufficient_evidence"}]})]),
    )

    assert result["claim_verification"]["status"] == "pass"
    assert result["claim_verification"]["warnings"][0]["type"] == "bounded_block_verifier_warning_downgraded"


def test_verifier_llm_downgrades_soft_failure_after_deterministic_pass() -> None:
    fake = _FakeChat([json.dumps({"status": "fail", "errors": [{"type": "memo_not_detailed_enough"}]})])
    result = route_verifier_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    assert result["claim_verification"]["status"] == "pass"
    assert any(
        item["type"] == "deterministic_pass_verifier_warning_downgraded"
        for item in result["claim_verification"]["warnings"]
    )
    user_prompt = fake.calls[0]["messages"][1]["content"]
    assert "verifier_projection" in user_prompt
    assert "verified_judgment_inventory" not in user_prompt
    assert "verifier_data_view" not in user_prompt
    assert "allowed_evidence_refs" in user_prompt


def test_verifier_llm_uses_minimal_memo_claim_projection() -> None:
    judgment = _judgment_without_unsupported()
    judgment["supported_claims"].append(
        {
            "claim_id": "extra_claim_not_in_memo",
            "agent_id": "market_valuation_analyst",
            "claim": "Extra market claim outside the final memo.",
            "evidence_refs": ["extra_ref_not_in_memo"],
            "source_families": ["market_snapshot"],
        }
    )
    memo = _memo()
    memo["memo_thesis_plan"] = judgment["memo_thesis_plan"]
    memo["memo_generation_policy"] = "thesis_led_claim_cards_v0_1"
    fake = _FakeChat([json.dumps({"status": "pass", "errors": []})])

    result = route_verifier_llm(
        {
            "user_query": "Write a memo.",
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
            "memo_answer": memo,
        },
        config=_config(),
        call_chat_completion=fake,
    )

    payload = extract_json_object(fake.calls[0]["messages"][1]["content"]) or {}
    projection = payload["verifier_projection"]
    projection_json = json.dumps(projection)
    stats = result["claim_verification"]["verifier_input_projection"]
    assert result["claim_verification"]["status"] == "pass"
    assert stats["projection_policy"] == "final_memo_claims_and_referenced_evidence_only"
    assert stats["input_supported_claim_count"] > stats["projected_claim_count"] == 1
    assert projection["allowed_evidence_refs"] == ["capex_ref"]
    assert "extra_ref_not_in_memo" not in projection_json


def test_verifier_route_records_input_pack_fingerprint_without_prompt_text() -> None:
    fake = _FakeChat([json.dumps({"status": "pass", "errors": []})])

    result = route_verifier_llm(
        _state(),
        config=_config(),
        call_chat_completion=fake,
    )

    verification = result["claim_verification"]
    fingerprint = verification["verifier_input_pack_fingerprint"]
    serialized = json.dumps(fingerprint, ensure_ascii=False, sort_keys=True)
    projection_fingerprint = verification["verifier_input_projection"]["input_pack_fingerprint"]
    assert fingerprint == projection_fingerprint
    assert fingerprint["schema_version"] == "sec_agent_verifier_input_pack_fingerprint_v0_1"
    assert fingerprint["agent_id"] == "verifier"
    assert fingerprint["digest"].startswith("sha256:")
    assert fingerprint["component_summaries"]["memo_answer"]["digest"].startswith("sha256:")
    assert fingerprint["known_evidence_ref_count"] >= 1
    assert "capex_ref" in fingerprint["known_evidence_refs"]
    assert fingerprint["fingerprint_policy"] == "fingerprint_only_no_prompt_text_persisted_v0_1"
    assert fingerprint["static_prompt_scaffold_summary"]["policy_id"] == "verifier_compact_instruction_scaffold_v0_1"
    assert fingerprint["static_prompt_scaffold_summary"]["system_prompt_chars"] > 0
    assert fingerprint["static_prompt_scaffold_summary"]["user_instruction_chars"] < 350
    assert fingerprint["approx_total_prompt_chars_with_scaffold"] > fingerprint["approx_prompt_payload_chars"]
    assert "Supported capex claim" not in serialized
    assert "Verifier Skill" not in serialized


def test_graph_repairs_injected_verifier_failure_once(tmp_path) -> None:
    calls: list[dict[str, Any]] = []

    def injected_specialists(_state: dict) -> dict:
        return {
            "specialist_outputs": [
                {
                    "agent_id": "fundamental_analyst",
                    "observations": [
                        {
                            "claim": "Supported capex claim.",
                            "evidence_refs": ["capex_ref"],
                            "source_families": ["primary_sec_filing"],
                        }
                    ],
                }
            ]
        }

    def injected_verifier(state: dict) -> dict:
        calls.append(dict(state.get("memo_answer") or {}))
        if len(calls) == 1:
            return {
                "claim_verification": {
                    "status": "fail",
                    "errors": [{"type": "memo_claim_without_evidence_refs", "index": 1}],
                    "bounded_answer_allowed": True,
                },
                "specialist_verification": state.get("specialist_verification") or {},
            }
        return {
            "claim_verification": {"status": "pass", "errors": [], "warnings": []},
            "specialist_verification": state.get("specialist_verification") or {},
        }

    graph = build_multi_agent_orchestration_graph(run_specialist_analysts=injected_specialists, verifier=injected_verifier)
    result = graph.invoke(
        make_multi_agent_smoke_state(
            user_query="写一段投研 memo，比较 NVDA 和 AMD 的基本面。",
            output_dir=tmp_path,
            query_contract=_query_contract(["NVDA", "AMD"]),
            focus_tickers=["NVDA", "AMD"],
            search_scope_tickers=["NVDA", "AMD"],
        ),
        config={"configurable": {"thread_id": "unit-injected-verifier-repair"}},
    )

    assert len(calls) == 2
    assert result["claim_verification"]["status"] == "pass"
    assert result["claim_verification"]["repair"]["status"] == "pass"


def test_extract_json_object_accepts_fenced_json() -> None:
    payload = {"status": "pass"}
    assert extract_json_object(f"```json\n{json.dumps(payload)}\n```") == payload


class _FakeChat:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        response = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        content = str(response.get("content") if isinstance(response, dict) else response or "")
        tool_calls = response.get("tool_calls") if isinstance(response, dict) else []
        finish_reason = str(response.get("finish_reason") or "stop") if isinstance(response, dict) else "stop"
        output_tokens = int(response.get("output_tokens") or 20) if isinstance(response, dict) else 20
        return {
            "status": "ok",
            "provider": kwargs["llm_backend"],
            "model": kwargs["model"],
            "role": kwargs["role"],
            "profile": kwargs["profile"],
            "content": content,
            "message": {"content": content, "tool_calls": tool_calls},
            "tool_calls": tool_calls or [],
            "finish_reason": finish_reason,
            "latency_ms": 1,
            "input_tokens": 10,
            "output_tokens": output_tokens,
            "total_tokens": 10 + output_tokens,
            "failure_reason": "",
            "raw_response": {},
        }


def _config() -> MemoLLMConfig:
    return MemoLLMConfig(
        llm_backend="unit",
        base_url="http://unit.test",
        chat_completions_path="/chat/completions",
        model="unit-model",
        api_key_env="UNIT_API_KEY",
    )


def _state() -> dict[str, Any]:
    judgment = _judgment_without_unsupported()
    memo = _memo()
    memo["memo_thesis_plan"] = judgment["memo_thesis_plan"]
    memo["memo_generation_policy"] = "thesis_led_claim_cards_v0_1"
    return {
        "user_query": "Write a memo.",
        "verified_judgment_plan": judgment,
        "judgment_plan": judgment,
        "specialist_verification": {"memo_writer_allowed": True},
        "memo_answer": memo,
    }


def test_memo_writer_route_records_raw_output_audit_when_gate_triggers_salvage() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": f"Supported financial claim {idx}.",
                        "claim_type": "company_reported_financial_fact",
                        "memo_slot": "fundamentals",
                        "evidence_refs": [f"fin_ref_{idx}"],
                        "source_families": ["primary_sec_filing"],
                        "ticker_scope": ["DELL"],
                        "metric_scope": ["revenue", "gross_margin"],
                        "materiality": "high",
                        "confidence": "high",
                    }
                    for idx in range(1, 4)
                ],
            },
            {
                "agent_id": "product_technology_analyst",
                "observations": [
                    {
                        "claim": f"Supported product claim {idx}.",
                        "claim_type": "product_taxonomy_context",
                        "memo_slot": "product_technology",
                        "evidence_refs": [f"product_ref_{idx}"],
                        "source_families": ["company_product_evidence_graph"],
                        "ticker_scope": ["DELL"],
                        "metric_scope": ["product_family"],
                        "materiality": "medium",
                        "confidence": "medium",
                    }
                    for idx in range(1, 4)
                ],
            },
        ]
    )
    judgment["memo_thesis_plan"]["status"] = "ready"
    judgment["memo_thesis_pack"]["status"] = "ready"
    judgment["claim_card_stats"] = {
        "supported_claim_count": 7,
        "memo_ready_claim_count": 6,
        "memo_slot_supported_count": 3,
    }
    bad_memo = {
        "answer_status": "draft",
        "direct_answer": (
            "The evidence supports a bounded AI infrastructure read, but this draft intentionally omits the "
            "business mechanism and financial bridge fields that the analyst-depth contract requires for a deep memo."
        ),
        "memo_claims": [
            {"claim": f"Supported financial claim {idx}.", "evidence_refs": [f"fin_ref_{idx}"], "source_families": ["primary_sec_filing"]}
            for idx in range(1, 4)
        ]
        + [
            {
                "claim": f"Supported product claim {idx}.",
                "evidence_refs": [f"product_ref_{idx}"],
                "source_families": ["company_product_evidence_graph"],
            }
            for idx in range(1, 4)
        ],
        "dimension_analyses": [
            {
                "dimension_id": "fundamentals",
                "summary": "Financial evidence is mentioned with enough text length but no mechanism fields.",
                "evidence_refs": ["fin_ref_1"],
            },
            {
                "dimension_id": "product_and_production",
                "summary": "Product evidence is mentioned with enough text length but no bridge fields.",
                "evidence_refs": ["product_ref_1"],
            },
            {
                "dimension_id": "risk_and_counterevidence",
                "summary": "Risk evidence is mentioned with enough text length but no counter-read fields.",
                "evidence_refs": ["fin_ref_2"],
            },
        ],
        "memo_thesis_plan": judgment["memo_thesis_plan"],
        "memo_generation_policy": "thesis_led_claim_cards_v0_1",
    }
    fake = _FakeChat([json.dumps(bad_memo)])

    result = route_memo_writer_llm(
        {
            "user_query": "Write a deep AI infrastructure memo.",
            "agent_activation_plan": {"execution_mode": "deep_research"},
            "verified_judgment_plan": judgment,
            "judgment_plan": judgment,
            "specialist_verification": {"memo_writer_allowed": True},
        },
        config=MemoLLMConfig(**{**_config().__dict__, "max_repair_attempts": 0}),
        call_chat_completion=fake,
    )

    audit = result["memo_route_result"]["raw_output_audit"]
    assert result["memo_route_result"]["deterministic_salvage_used"] is True
    assert audit["raw_text_persisted"] is False
    assert audit["deterministic_gate_status"] == "fail"
    assert "analyst_depth_dimension_missing_mechanism_bridge" in audit["deterministic_gate_error_types"]
    assert audit["salvage_triggered"] is True


def _judgment() -> dict[str, Any]:
    return aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "Supported capex claim.",
                        "evidence_refs": ["capex_ref"],
                        "source_families": ["primary_sec_filing"],
                    }
                ],
                "unsupported_claims": [{"claim": "Unsupported customer claim.", "reason": "not in bounded evidence"}],
            }
        ]
    )


def _judgment_without_unsupported() -> dict[str, Any]:
    return aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "Supported capex claim.",
                        "evidence_refs": ["capex_ref"],
                        "source_families": ["primary_sec_filing"],
                    }
                ],
            }
        ]
    )


def _market_judgment() -> dict[str, Any]:
    return aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "market_valuation_analyst",
                "observations": [
                    {
                        "claim": "AMD EV/Sales is 22.1x, indicating valuation risk.",
                        "claim_type": "market_context",
                        "evidence_refs": ["MARKET::AMD::2026-05-29"],
                        "source_families": ["market_snapshot"],
                        "memo_slot": "market_valuation",
                        "materiality": "high",
                    }
                ],
            }
        ]
    )


def _memo() -> dict[str, Any]:
    return {
        "answer_status": "draft",
        "direct_answer": "Supported capex claim.",
        "memo_claims": [
            {"claim": "Supported capex claim.", "evidence_refs": ["capex_ref"], "source_families": ["primary_sec_filing"]}
        ],
    }


def _query_contract(tickers: list[str]) -> dict[str, Any]:
    return {
        "task_type": "open_analysis",
        "search_scope_tickers": tickers,
        "focus_tickers": tickers,
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["capex"],
    }
