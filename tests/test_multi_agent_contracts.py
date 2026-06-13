from __future__ import annotations

from sec_agent.multi_agent_contracts import (
    _unknown_numeric_tokens as _contracts_unknown_numeric_tokens,
    aggregate_focused_answer_judgment_plan,
    aggregate_specialist_judgment_plan,
    build_multi_agent_memo_draft,
    normalize_universe_relationship_plan,
    refresh_judgment_plan_after_governance_filter,
    repair_multi_agent_memo_draft,
    validate_specialist_memolet,
    validate_universe_relationship_plan,
    verify_multi_agent_memo_draft,
    verify_specialist_outputs_for_memo,
)


def test_numeric_fidelity_accepts_chinese_usd_yi_converted_from_usd_millions() -> None:
    unknown = _contracts_unknown_numeric_tokens(
        "AMZN capex 为 -1510.03亿美元，DELL ISG 产品收入为 290.09亿美元。",
        "AMZN reported capital expenditures of -151003.0 usd_millions; DELL Total ISG net revenue was 29009.0 usd_millions.",
    )

    assert "-1510.03亿美元" not in unknown
    assert "290.09亿美元" not in unknown


def test_specialist_memolet_requires_evidence_refs_for_supported_claims() -> None:
    result = validate_specialist_memolet(
        {
            "agent_id": "fundamental_analyst",
            "observations": [{"claim": "Revenue growth improved.", "confidence": "high"}],
        }
    )

    assert result["status"] == "fail"
    assert result["errors"][0]["type"] == "supported_claim_without_evidence_refs"


def test_specialist_memolet_rejects_tool_calls_and_unknown_refs() -> None:
    result = validate_specialist_memolet(
        {
            "agent_id": "market_valuation_analyst",
            "tool_calls": [{"name": "market_get_snapshot"}],
            "observations": [{"claim": "Market reacted positively.", "evidence_refs": ["bad_ref"], "source_families": ["market_snapshot"]}],
        },
        known_evidence_refs={"market_ref_1"},
    )
    error_types = {item["type"] for item in result["errors"]}

    assert result["status"] == "fail"
    assert "specialist_tool_calls_forbidden" in error_types
    assert "unknown_evidence_ref" in error_types


def test_relationship_graph_business_observation_is_normalized_to_hypothesis() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "industry_supply_chain_analyst",
                "observations": [
                    {
                        "claim": "Relationship graph supports an AI infrastructure readthrough path.",
                        "claim_type": "business_observation",
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
    judgment["memo_thesis_plan"]["status"] = "ready"
    judgment["memo_thesis_pack"]["status"] = "ready"
    memo = build_multi_agent_memo_draft(judgment)
    verification = verify_multi_agent_memo_draft(memo, judgment)

    relationship_claim = next(claim for claim in judgment["supported_claims"] if claim["agent_id"] == "industry_supply_chain_analyst")
    assert relationship_claim["claim_type"] == "relationship_hypothesis"
    assert any(claim["claim_type"] == "relationship_hypothesis" for claim in memo["memo_claims"])
    assert verification["status"] == "pass"


def test_product_technology_claim_card_uses_product_memo_slot() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "product_technology_analyst",
                "observations": [
                    {
                        "claim": "Company-disclosed product KPI supports the product evidence section.",
                        "claim_type": "company_disclosed_product_kpi",
                        "evidence_refs": ["product_ref_1"],
                        "source_families": ["company_product_evidence_graph"],
                        "memo_slot": "product_technology",
                        "ticker_scope": ["AAPL"],
                        "metric_scope": ["product_revenue"],
                        "materiality": "high",
                        "confidence": "high",
                    }
                ],
            }
        ]
    )
    draft = build_multi_agent_memo_draft(judgment)
    outline = {row["memo_slot"]: row for row in judgment["memo_outline"]}

    assert judgment["supported_claims"][0]["agent_id"] == "product_technology_analyst"
    assert judgment["supported_claims"][0]["memo_slot"] == "product_technology"
    assert outline["product_technology"]["status"] == "supported"
    assert draft["memo_claims"][0]["memo_slot"] == "product_technology"


def test_thesis_driver_pack_structures_verified_claims_for_memo_surface() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "Revenue growth and margin expansion support the core thesis.",
                        "claim_type": "company_reported_financial_fact",
                        "evidence_refs": ["fund_ref_1"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "fundamentals",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["revenue", "gross_margin"],
                        "materiality": "high",
                        "confidence": "high",
                    }
                ],
            },
            {
                "agent_id": "product_technology_analyst",
                "observations": [
                    {
                        "claim": "Company product evidence supports demand for the accelerator platform.",
                        "claim_type": "company_disclosed_product_kpi",
                        "evidence_refs": ["product_ref_1"],
                        "source_families": ["company_product_evidence_graph"],
                        "memo_slot": "product_technology",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["accelerator_product"],
                        "materiality": "high",
                        "confidence": "medium",
                        "missing_confirmations": ["Commercial tracker sell-through remains unavailable."],
                    }
                ],
            },
            {
                "agent_id": "risk_counterevidence_analyst",
                "observations": [
                    {
                        "claim": "Supply concentration remains a constraint on confidence.",
                        "claim_type": "risk_factor",
                        "evidence_refs": ["risk_ref_1"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "risk_counterevidence",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["supply_risk"],
                        "materiality": "medium",
                        "confidence": "medium",
                    }
                ],
            },
        ],
        source_gaps=[{"source_family": "commercial_market_tracker", "reason": "Sell-through unavailable from public sources."}],
    )
    draft = build_multi_agent_memo_draft(judgment)
    pack = judgment["thesis_driver_pack"]

    assert pack["schema_version"] == "sec_agent_thesis_driver_pack_v0.1"
    assert pack["status"] == "ready"
    assert pack["thesis_cards"]
    assert any(card["memo_slot"] == "fundamentals" for card in pack["driver_cards"])
    assert any(card["memo_slot"] == "product_technology" for card in pack["driver_cards"])
    assert pack["counter_driver_cards"][0]["memo_slot"] == "risk_counterevidence"
    assert any(card["gap_type"] == "missing_confirmation" for card in pack["gap_cards"])
    assert {row["dimension_id"] for row in pack["dimension_sections"]} >= {
        "fundamentals",
        "product_and_production",
        "risk_and_counterevidence",
    }
    assert draft["thesis_driver_pack"]["source_claim_refs"]
    assert draft["dimension_analyses"]
    assert draft["dimension_analyses"][0]["business_mechanism"]


def test_thesis_driver_pack_keeps_risk_claims_in_risk_dimension_when_they_mention_capex_or_valuation() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "market_valuation_analyst",
                "observations": [
                    {
                        "claim": "The stock's EV/Sales multiple embeds elevated growth expectations.",
                        "claim_type": "market_snapshot_context",
                        "evidence_refs": ["market_ref_1"],
                        "source_families": ["market_snapshot"],
                        "memo_slot": "market_valuation",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["valuation"],
                        "materiality": "medium",
                        "confidence": "medium",
                    }
                ],
            },
            {
                "agent_id": "risk_counterevidence_analyst",
                "observations": [
                    {
                        "claim": "The EV/Sales multiple creates repricing risk if hyperscaler capex slows.",
                        "claim_type": "risk_factor",
                        "evidence_refs": ["risk_ref_1"],
                        "source_families": ["market_snapshot"],
                        "memo_slot": "risk_counterevidence",
                        "ticker_scope": ["NVDA", "MSFT"],
                        "metric_scope": ["valuation", "capex"],
                        "materiality": "high",
                        "confidence": "medium",
                    }
                ],
            },
        ]
    )

    pack = judgment["thesis_driver_pack"]
    dimensions = {row["dimension_id"]: row for row in pack["dimension_sections"]}

    assert "risk_and_counterevidence" in dimensions
    assert dimensions["risk_and_counterevidence"]["primary_claim_ids"]
    assert dimensions["risk_and_counterevidence"]["primary_claim_ids"][0].startswith("risk_counterevidence_analyst")
    assert "capital_and_financing" not in dimensions


def test_thesis_driver_pack_keeps_gap_only_product_and_risk_dimensions_traceable() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "Reported revenue supports the baseline fundamental setup.",
                        "claim_type": "company_reported_financial_fact",
                        "evidence_refs": ["fund_ref_1"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "fundamentals",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["revenue"],
                        "materiality": "high",
                        "confidence": "high",
                    }
                ],
            },
            {
                "agent_id": "product_technology_analyst",
                "status": "partial",
                "observations": [],
                "unsupported_claims": [
                    {
                        "claim": "Product revenue and order backlog are not available from public exact-authority rows.",
                        "reason": "commercial tracker or company product source is required",
                    }
                ],
            },
            {
                "agent_id": "risk_counterevidence_analyst",
                "status": "partial",
                "observations": [],
                "conflicts": [
                    {
                        "claim": "Hyperscaler capex visibility is missing, which weakens the demand-transmission thesis.",
                        "reason": "no bounded capex evidence",
                    }
                ],
            },
        ]
    )
    draft = build_multi_agent_memo_draft(judgment)
    dimensions = {row["dimension_id"]: row for row in judgment["thesis_driver_pack"]["dimension_sections"]}
    draft_dimensions = {row["dimension_id"]: row for row in draft["dimension_analyses"]}

    assert dimensions["product_and_production"]["status"] == "gap_or_counterevidence"
    assert dimensions["risk_and_counterevidence"]["status"] == "gap_or_counterevidence"
    assert dimensions["product_and_production"]["gap_ids"]
    assert "product_and_production" in draft_dimensions
    assert "risk_and_counterevidence" in draft_dimensions
    assert draft_dimensions["product_and_production"]["gap_ids"]


def test_analyst_depth_gate_requires_dimension_analyses_for_standard_memo() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "Revenue growth supports the fundamental setup.",
                        "claim_type": "company_reported_financial_fact",
                        "evidence_refs": ["fund_ref_1"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "fundamentals",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["revenue"],
                        "materiality": "high",
                        "confidence": "high",
                    }
                ],
            },
            {
                "agent_id": "product_technology_analyst",
                "observations": [
                    {
                        "claim": "Product evidence supports the accelerator platform read-through.",
                        "claim_type": "company_disclosed_product_kpi",
                        "evidence_refs": ["product_ref_1"],
                        "source_families": ["company_product_evidence_graph"],
                        "memo_slot": "product_technology",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["accelerator_product"],
                        "materiality": "high",
                        "confidence": "high",
                    }
                ],
            },
        ]
    )
    memo = build_multi_agent_memo_draft(judgment)
    memo["memo_profile"] = {"profile": "standard", "memo_claims_min_when_thesis_ready": 3}
    memo["investment_implications"] = [{"text": "Revenue and product evidence jointly support the thesis."}]
    memo["what_would_change_view"] = [{"text": "Opposite same-scope filings would reduce conviction."}]
    memo["monitoring_items"] = [{"text": "Track revenue and product evidence in the next filing."}]
    memo["dimension_analyses"] = []

    verification = verify_multi_agent_memo_draft(memo, judgment)

    assert verification["analyst_depth_gate"]["status"] == "fail"
    assert any(error["type"] == "analyst_depth_missing_dimension_analyses" for error in verification["errors"])


def test_verifier_enforces_profile_minimum_claim_count_when_thesis_ready() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": f"Supported financial claim {index}.",
                        "claim_type": "company_reported_financial_fact",
                        "evidence_refs": [f"fund_ref_{index}"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "fundamentals",
                        "materiality": "high",
                        "confidence": "high",
                    }
                    for index in range(5)
                ],
            }
        ]
    )
    judgment["memo_thesis_plan"]["status"] = "ready"
    judgment["memo_thesis_pack"]["status"] = "ready"
    memo = build_multi_agent_memo_draft(judgment)
    memo["memo_profile"] = {"profile": "expanded", "memo_claims_min_when_thesis_ready": 5}
    memo["memo_claims"] = memo["memo_claims"][:3]

    verification = verify_multi_agent_memo_draft(memo, judgment)

    assert verification["status"] == "fail"
    assert any(error["type"] == "memo_too_few_claims_for_ready_thesis_pack" for error in verification["errors"])


def test_governance_filter_refresh_rebuilds_memo_pack_without_blocked_claims() -> None:
    kept = {
        "claim_id": "claim_context",
        "agent_id": "focused_answer_synthesizer",
        "claim": "Company-authored context can be used only as management commentary.",
        "claim_type": "business_observation",
        "memo_slot": "fundamentals",
        "evidence_refs": ["context_ref"],
        "source_families": ["company_authored_unaudited_sec_filing"],
        "materiality": "medium",
        "confidence": "medium",
    }
    blocked = {
        "claim_id": "claim_blocked",
        "agent_id": "focused_answer_synthesizer",
        "claim": "Revenue was 19,799 million dollars.",
        "claim_type": "company_reported_financial_fact",
        "memo_slot": "fundamentals",
        "evidence_refs": ["blocked_ref"],
        "source_families": ["primary_sec_filing"],
        "materiality": "high",
        "confidence": "high",
    }
    original = {
        "schema_version": "sec_agent_judgment_plan_v0.1",
        "source_agent_ids": ["focused_answer_synthesizer"],
        "supported_claims": [kept, blocked],
        "unsupported_claims": [],
        "conflicts": [],
        "blocked_specialist_agents": [],
        "source_boundary_notes": [],
    }
    original["memo_outline"] = [{"memo_slot": "fundamentals", "status": "supported", "claim_ids": ["claim_context", "claim_blocked"]}]
    original["memo_thesis_pack"] = {
        "status": "ready",
        "core_thesis": {"claim": "Revenue was 19,799 million dollars.", "evidence_refs": ["blocked_ref"]},
        "supporting_drivers": [{"driver": blocked}],
    }
    filtered = {
        **original,
        "supported_claims": [kept],
        "unsupported_claims": [
            {
                "claim_id": "claim_blocked",
                "claim": "claim text withheld because pre-memo governance blocked this fact; use bounded gap metadata instead",
                "reason": "blocked_by_pre_memo_fact_selection",
            }
        ],
    }

    refreshed = refresh_judgment_plan_after_governance_filter(filtered)
    packed_text = str(refreshed["memo_thesis_pack"])
    driver_packed_text = str(refreshed["thesis_driver_pack"])

    assert "19,799" not in packed_text
    assert "19,799" not in driver_packed_text
    assert refreshed["memo_thesis_pack"]["core_thesis"]["claim_id"] == "claim_context"
    assert refreshed["thesis_driver_pack"]["thesis_cards"][0]["source_claim_id"] == "claim_context"
    assert refreshed["claim_card_stats"]["supported_claim_count"] == 1


def test_verifier_blocks_ownership_filing_as_realtime_flow_and_repair_removes_it() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "industry_supply_chain_analyst",
                "observations": [
                    {
                        "claim": "13F holdings show real-time money inflow into NVDA.",
                        "claim_type": "realtime_flow",
                        "evidence_refs": ["nvda_13f_ref"],
                        "source_families": ["public_source_context"],
                        "memo_slot": "industry_relationship",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["ownership"],
                        "materiality": "high",
                        "confidence": "medium",
                    }
                ],
            }
        ]
    )
    memo = build_multi_agent_memo_draft(judgment)

    verification = verify_multi_agent_memo_draft(memo, judgment)
    repaired = repair_multi_agent_memo_draft(memo, verification, judgment)

    error_types = {item["type"] for item in verification["errors"]}
    assert verification["status"] == "fail"
    assert "ownership_filing_used_as_realtime_flow" in error_types
    assert not repaired["memo_claims"]
    assert repaired["removed_claims"][0]["reason"] == "ownership_filing_used_as_realtime_flow"


def test_verifier_blocks_macro_context_as_company_fact_and_repair_removes_it() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "industry_supply_chain_analyst",
                "observations": [
                    {
                        "claim": "FRED macro rate data proves JPM company revenue growth.",
                        "claim_type": "company_revenue",
                        "evidence_refs": ["fred_rate_ref"],
                        "source_families": ["industry_snapshot"],
                        "memo_slot": "industry_relationship",
                        "ticker_scope": ["JPM"],
                        "metric_scope": ["revenue"],
                        "materiality": "high",
                        "confidence": "medium",
                    }
                ],
            }
        ]
    )
    memo = build_multi_agent_memo_draft(judgment)

    verification = verify_multi_agent_memo_draft(memo, judgment)
    repaired = repair_multi_agent_memo_draft(memo, verification, judgment)

    error_types = {item["type"] for item in verification["errors"]}
    assert verification["status"] == "fail"
    assert "macro_or_public_context_used_as_company_fact" in error_types
    assert not repaired["memo_claims"]
    assert repaired["removed_claims"][0]["reason"] == "macro_or_public_context_used_as_company_fact"


def test_verifier_blocks_public_proxy_as_product_kpi_fact_and_repair_removes_it() -> None:
    claim = {
        "claim_id": "product_claim_1",
        "agent_id": "product_technology_analyst",
        "claim": "A commerce listing proves product sales for the model.",
        "claim_type": "product_sales",
        "evidence_refs": ["commerce_listing_ref"],
        "source_families": ["live_public_web_context"],
        "memo_slot": "product_technology",
        "ticker_scope": ["NVDA"],
        "metric_scope": ["product_sales"],
        "materiality": "high",
        "confidence": "medium",
    }
    judgment = {"supported_claims": [claim], "unsupported_claims": []}
    memo = {
        "answer_status": "draft",
        "direct_answer": "A commerce listing proves product sales for the model.",
        "memo_generation_policy": "thesis_led_claim_cards_v0_1",
        "memo_claims": [claim],
    }

    verification = verify_multi_agent_memo_draft(memo, judgment)
    repaired = repair_multi_agent_memo_draft(memo, verification, judgment)

    error_types = {item["type"] for item in verification["errors"]}
    assert verification["status"] == "fail"
    assert "public_proxy_used_as_product_kpi_fact" in error_types
    assert repaired["removed_claims"][0]["reason"] == "public_proxy_used_as_product_kpi_fact"


def test_verifier_blocks_public_proxy_product_sales_after_claim_type_normalization() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "product_technology_analyst",
                "observations": [
                    {
                        "claim": "The official product page proves model sales.",
                        "claim_type": "product_sales",
                        "evidence_refs": ["official_product_page_ref"],
                        "source_families": ["live_public_web_context"],
                        "memo_slot": "product_technology",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["product_sales"],
                        "materiality": "high",
                        "confidence": "medium",
                    }
                ],
            }
        ]
    )
    memo = build_multi_agent_memo_draft(judgment)

    verification = verify_multi_agent_memo_draft(memo, judgment)
    repaired = repair_multi_agent_memo_draft(memo, verification, judgment)

    assert judgment["supported_claims"][0]["claim_type"] == "public_proxy_context"
    assert judgment["supported_claims"][0]["raw_claim_type"] == "product_sales"
    assert verification["status"] == "fail"
    assert {item["type"] for item in verification["errors"]} >= {"public_proxy_used_as_product_kpi_fact"}
    assert repaired["removed_claims"][0]["reason"] == "public_proxy_used_as_product_kpi_fact"


def test_verifier_blocks_channel_offer_as_sell_through_and_field_inquiry_authority_fact() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "product_technology_analyst",
                "observations": [
                    {
                        "claim": "Channel offer price availability proves sell-through and market share.",
                        "claim_type": "business_observation",
                        "evidence_refs": ["channel_offer_ref"],
                        "source_families": ["live_public_web_context"],
                        "memo_slot": "product_technology",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["sell_through"],
                        "materiality": "high",
                        "confidence": "medium",
                    },
                    {
                        "claim": "Field inquiry note from a dealer quote is an authority fact for sales.",
                        "claim_type": "business_observation",
                        "evidence_refs": ["field_inquiry_ref"],
                        "source_families": ["public_source_context"],
                        "memo_slot": "product_technology",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["sales"],
                        "materiality": "high",
                        "confidence": "medium",
                    },
                ],
            }
        ]
    )
    memo = build_multi_agent_memo_draft(judgment)

    verification = verify_multi_agent_memo_draft(memo, judgment)
    repaired = repair_multi_agent_memo_draft(memo, verification, judgment)

    error_types = {item["type"] for item in verification["errors"]}
    removed_reasons = {item["reason"] for item in repaired["removed_claims"]}
    assert verification["status"] == "fail"
    assert "channel_offer_used_as_sell_through" in error_types
    assert "field_inquiry_note_used_as_authority_fact" in error_types
    assert {"channel_offer_used_as_sell_through", "field_inquiry_note_used_as_authority_fact"} <= removed_reasons


def test_judgment_plan_preserves_conflicts_without_averaging() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "Margins improved on cost control.",
                        "evidence_refs": ["sec_ref_1"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": 0.8,
                    }
                ],
            },
            {
                "agent_id": "risk_counterevidence_analyst",
                "conflicts": [{"claim": "Management commentary points to demand uncertainty.", "reason": "8-K commentary"}],
            },
        ]
    )

    assert judgment["status"] == "partial"
    assert judgment["aggregation_policy"] == "rank_supported_claim_cards_preserve_conflicts_no_average"
    assert len(judgment["supported_claims"]) == 1
    assert len(judgment["conflicts"]) == 1


def test_specialist_claim_card_fields_flow_into_judgment_and_memo_claims() -> None:
    memolet = {
        "agent_id": "fundamental_analyst",
        "observations": [
            {
                "claim": "NVDA revenue growth is a high-materiality demand signal.",
                "claim_type": "company_reported_financial_fact",
                "ticker_scope": ["nvda"],
                "metric_scope": ["revenue"],
                "memo_slot": "fundamentals",
                "materiality": "high",
                "direction": "positive",
                "evidence_refs": ["sec_ref_1"],
                "source_families": ["primary_sec_filing"],
                "missing_confirmations": ["margin bridge"],
            }
        ],
    }

    judgment = aggregate_specialist_judgment_plan([memolet])
    draft = build_multi_agent_memo_draft(judgment)

    claim = judgment["supported_claims"][0]
    memo_claim = draft["memo_claims"][0]
    assert claim["ticker_scope"] == ["NVDA"]
    assert claim["memo_slot"] == "fundamentals"
    assert claim["materiality"] == "high"
    assert memo_claim["metric_scope"] == ["revenue"]
    assert memo_claim["missing_confirmations"] == ["margin bridge"]


def test_judgment_plan_ranks_claim_cards_by_materiality_and_builds_outline() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "Low materiality evidence.",
                        "evidence_refs": ["sec_ref_low"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "fundamentals",
                        "materiality": "low",
                        "confidence": "high",
                    },
                    {
                        "claim": "High materiality evidence.",
                        "evidence_refs": ["sec_ref_high"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "fundamentals",
                        "materiality": "high",
                        "confidence": "medium",
                    },
                ],
            },
            {"agent_id": "market_valuation_analyst", "observations": []},
        ]
    )

    assert judgment["supported_claims"][0]["claim"] == "High materiality evidence."
    outline_by_slot = {row["memo_slot"]: row for row in judgment["memo_outline"]}
    assert outline_by_slot["fundamentals"]["status"] == "supported"
    assert outline_by_slot["market_valuation"]["status"] == "missing_or_partial"
    assert judgment["claim_card_stats"]["supported_claim_count"] == 2


def test_claim_card_ranker_prefers_memo_ready_role_claim_over_row_summary() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "The table shows net interest income.",
                        "claim_type": "company_reported_financial_fact",
                        "evidence_refs": ["sec_ref_summary"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "fundamentals",
                        "materiality": "high",
                        "confidence": "high",
                    },
                    {
                        "claim": "JPM's higher net interest income supports a positive fundamentals read because earning-asset yield is still offsetting funding cost pressure.",
                        "claim_type": "company_reported_financial_fact",
                        "ticker_scope": ["JPM"],
                        "metric_scope": ["net_interest_income"],
                        "memo_slot": "fundamentals",
                        "materiality": "high",
                        "direction": "positive",
                        "evidence_refs": ["sec_ref_ready"],
                        "source_families": ["primary_sec_filing"],
                        "confidence": "high",
                    },
                ],
            }
        ]
    )

    first, second = judgment["supported_claims"][:2]
    assert first["claim_id"] == "fundamental_analyst_claim_2"
    assert first["claim_card_version"] == "v0.3"
    assert first["claim_rank_bucket"] == "memo_ready"
    assert first["claim_rank_score"] > second["claim_rank_score"]
    assert judgment["claim_card_stats"]["memo_ready_claim_count"] == 1


def test_judgment_plan_synthesizes_thesis_from_supported_business_slots() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "Bank net interest income has bounded filing support.",
                        "claim_type": "company_reported_financial_fact",
                        "evidence_refs": ["sec_ref_1"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "fundamentals",
                        "materiality": "high",
                        "confidence": "high",
                    }
                ],
            },
            {
                "agent_id": "industry_supply_chain_analyst",
                "observations": [
                    {
                        "claim": "Relationship pack supports a sector-scope banking readthrough hypothesis.",
                        "claim_type": "relationship_hypothesis",
                        "evidence_refs": ["rel_ref_1"],
                        "source_families": ["relationship_graph"],
                        "memo_slot": "industry_relationship",
                        "materiality": "medium",
                        "confidence": "medium",
                    }
                ],
            },
            {
                "agent_id": "risk_counterevidence_analyst",
                "observations": [
                    {
                        "claim": "Credit-risk evidence keeps the thesis caveated.",
                        "claim_type": "risk_or_counterevidence",
                        "evidence_refs": ["risk_ref_1"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "risk_counterevidence",
                        "materiality": "high",
                        "confidence": "medium",
                    }
                ],
            },
        ]
    )
    memo = build_multi_agent_memo_draft(judgment)
    verification = verify_multi_agent_memo_draft(memo, judgment)
    outline = {row["memo_slot"]: row for row in judgment["memo_outline"]}

    thesis = judgment["supported_claims"][0]
    thesis_plan = judgment["memo_thesis_plan"]
    thesis_pack = judgment["memo_thesis_pack"]
    known_refs = {ref for claim in judgment["supported_claims"] for ref in claim.get("evidence_refs", [])}
    assert judgment["thesis_synthesis"]["status"] == "synthesized"
    assert thesis["claim_id"] == "judgment_plan_aggregator_thesis_1"
    assert thesis["memo_slot"] == "thesis"
    assert thesis["claim_type"] == "investment_thesis_synthesis"
    assert set(thesis["derived_from_claim_ids"]) == {
        "fundamental_analyst_claim_1",
        "industry_supply_chain_analyst_claim_2",
        "risk_counterevidence_analyst_claim_3",
    }
    assert thesis_plan["schema_version"] == "sec_agent_memo_thesis_plan_v0.1"
    assert thesis_plan["status"] == "ready"
    assert thesis_plan["primary_thesis_claim_id"] == "judgment_plan_aggregator_thesis_1"
    assert thesis_plan["risk_or_counter_claim_ids"] == ["risk_counterevidence_analyst_claim_3"]
    assert thesis_pack["schema_version"] == "sec_agent_memo_thesis_pack_v0.1"
    assert thesis_pack["core_thesis"]["claim_id"] == "judgment_plan_aggregator_thesis_1"
    assert {row["memo_slot"] for row in thesis_pack["supporting_drivers"]} == {
        "fundamentals",
        "industry_relationship",
        "risk_counterevidence",
    }
    assert set(thesis_pack["source_claim_refs"]) <= known_refs
    assert memo["memo_thesis_plan"]["primary_thesis_claim_id"] == "judgment_plan_aggregator_thesis_1"
    assert memo["memo_thesis_pack"]["core_thesis"]["claim_id"] == "judgment_plan_aggregator_thesis_1"
    assert memo["memo_generation_policy"] == "thesis_led_claim_cards_v0_1"
    assert memo["direct_answer"].startswith("Bank net interest income has bounded filing support.")
    assert outline["thesis"]["status"] == "supported"
    assert memo["memo_claims"][0]["claim_id"] == "judgment_plan_aggregator_thesis_1"
    assert verification["status"] == "pass"


def test_focused_answer_judgment_plan_builds_claim_cards_from_bounded_rows() -> None:
    judgment = aggregate_focused_answer_judgment_plan(
        runtime_ledger_rows=[
            {
                "ticker": "AMZN",
                "fiscal_year": 2026,
                "period_role": "qtd",
                "metric_family": "operating_income",
                "metric_name": "operating income",
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
                "metric_name": "revenue",
                "display_value_zh": "155,667（百万美元）",
                "source_tier": "primary_sec_filing",
                "form_type": "10-Q",
                "metric_id": "amzn_revenue_qtd_ref",
            },
        ],
        context_rows=[
            {
                "ticker": "AMZN",
                "form_type": "8-K",
                "source_evidence_id": "amzn_8k_margin_commentary_ref",
                "summary": "Management discussed operating income and cost discipline.",
            }
        ],
        evidence_requirement_plan={
            "requirements": [
                {"tickers": ["AMZN"], "metric_families": ["revenue", "margin", "cash_flow"]}
            ]
        },
        reflection_report={"sufficiency_level": "sufficient"},
        response_language="zh-CN",
    )
    memo = build_multi_agent_memo_draft(judgment)
    verification = verify_multi_agent_memo_draft(memo, judgment)

    assert judgment["aggregation_policy"] == "focused_answer_claim_cards_from_bounded_rows_v0_1"
    assert judgment["memo_thesis_pack"]["status"] == "ready"
    assert judgment["memo_writer_allowed"] is True
    assert len(judgment["supported_claims"]) >= 2
    assert "限定在本轮检索到的" in judgment["memo_thesis_pack"]["core_thesis"]["claim"]
    assert "营业利润" in judgment["memo_thesis_pack"]["core_thesis"]["claim"]
    assert "operating_income" not in judgment["memo_thesis_pack"]["core_thesis"]["claim"]
    assert {ref for claim in judgment["supported_claims"] for ref in claim["evidence_refs"]} >= {
        "amzn_operating_income_qtd_ref",
        "amzn_revenue_qtd_ref",
    }
    assert memo["answer_status"] == "draft"
    assert memo["memo_claims"]
    assert verification["status"] == "pass"


def test_focused_answer_judgment_plan_filters_amount_metric_percentage_role_rows() -> None:
    judgment = aggregate_focused_answer_judgment_plan(
        runtime_ledger_rows=[
            {
                "ticker": "LLY",
                "fiscal_year": 2026,
                "period_role": "qtd",
                "metric_family": "revenue",
                "metric_name": "revenue",
                "metric_role": "percentage_rate",
                "raw_value_text": "$ 19,799",
                "display_value_zh": "19,799%（百分比率）",
                "source_tier": "primary_sec_filing",
                "form_type": "10-Q",
                "metric_id": "__mcp__::LLY::2026::revenue::percentage_rate::qtd",
            },
            {
                "ticker": "LLY",
                "fiscal_year": 2026,
                "period_role": "qtd",
                "metric_family": "revenue",
                "metric_name": "revenue",
                "metric_role": "total_value",
                "raw_value_text": "$ 19,799",
                "display_value_zh": "19,799（百万美元）",
                "source_tier": "primary_sec_filing",
                "form_type": "10-Q",
                "metric_id": "__mcp__::LLY::2026::revenue::total_value::qtd",
            },
        ],
        context_rows=[],
        evidence_requirement_plan={"requirements": [{"tickers": ["LLY"], "metric_families": ["revenue"]}]},
        response_language="zh-CN",
    )
    fundamentals = next(
        claim for claim in judgment["supported_claims"] if claim["claim_id"] == "focused_answer_synthesizer_fundamentals_1"
    )
    joined_refs = " ".join(fundamentals["evidence_refs"])

    assert "19,799（百万美元）" in fundamentals["claim"]
    assert "百分比率" not in fundamentals["claim"]
    assert "percentage_rate" not in joined_refs
    assert "total_value" in joined_refs


def test_judgment_plan_caps_unsupported_claims_per_specialist_with_overflow_guardrail() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "risk_counterevidence_analyst",
                "unsupported_claims": [
                    {"claim": f"Unsupported risk claim {index}", "reason": "not in bounded evidence"}
                    for index in range(1, 5)
                ],
            }
        ]
    )
    verification = verify_specialist_outputs_for_memo([], judgment_plan=judgment)

    assert len(judgment["unsupported_claims"]) == 2
    assert judgment["unsupported_claim_policy"]["overflow_unsupported_claim_count"] == 2
    assert judgment["memo_constraints"]["unsupported_claim_overflow_count"] == 2
    assert "additional_unsupported_claims_summarized_not_expanded" in judgment["memo_constraints"]["required_caveats"]
    assert verification["unsupported_claim_count"] == 2


def test_verifier_blocks_unsupported_specialist_claims_before_memo_writer() -> None:
    report = verify_specialist_outputs_for_memo(
        [
            {
                "agent_id": "risk_counterevidence_analyst",
                "unsupported_claims": [{"claim": "A named customer shifted orders.", "reason": "not in bounded evidence"}],
            }
        ]
    )

    assert report["status"] == "fail"
    assert report["memo_writer_allowed"] is False
    assert report["unsupported_claim_count"] == 1


def test_source_quality_gap_observation_is_not_promoted_to_supported_claim() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "DELL 8-K segment rows are garbled and cannot be reliably interpreted as revenue or margin.",
                        "claim_type": "company_reported_financial_fact",
                        "memo_slot": "fundamentals",
                        "evidence_refs": ["dell_8k_ref"],
                        "source_families": ["company_authored_unaudited_sec_filing"],
                        "confidence": "medium",
                    }
                ],
            }
        ]
    )

    assert judgment["supported_claims"] == []
    assert judgment["unsupported_claims"][0]["reason"] == "source_quality_gap_not_supported_claim"


def test_required_dimensions_become_visible_gap_only_sections_after_refresh() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "product_technology_analyst",
                "observations": [
                    {
                        "claim": "Company-disclosed product evidence supports a product mix discussion.",
                        "claim_type": "product_kpi",
                        "memo_slot": "product_technology",
                        "evidence_refs": ["product_ref_1"],
                        "source_families": ["company_product_evidence_graph"],
                        "confidence": "high",
                    }
                ],
            }
        ]
    )
    refreshed = refresh_judgment_plan_after_governance_filter(
        {
            **judgment,
            "required_dimension_ids": [
                "fundamentals",
                "product_and_production",
                "capital_and_financing",
            ],
        }
    )
    sections = refreshed["thesis_driver_pack"]["dimension_sections"]
    by_id = {row["dimension_id"]: row for row in sections}

    assert set(by_id) >= {"fundamentals", "product_and_production", "capital_and_financing"}
    assert by_id["product_and_production"]["status"] == "supported"
    assert by_id["fundamentals"]["status"] == "gap_or_counterevidence"
    assert by_id["fundamentals"]["required_by_user"] is True
    assert by_id["capital_and_financing"]["gap_ids"] == ["gap_required_dimension_capital_and_financing"]
    assert refreshed["thesis_driver_pack"]["gap_cards"][0]["gap_type"] == "required_dimension_missing_verified_evidence"


def test_analyst_depth_gate_blocks_missing_user_required_dimension() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "product_technology_analyst",
                "observations": [
                    {
                        "claim": "Product evidence supports the current product and production read.",
                        "claim_type": "product_kpi",
                        "memo_slot": "product_technology",
                        "evidence_refs": ["product_ref_1"],
                        "source_families": ["company_product_evidence_graph"],
                        "confidence": "high",
                    }
                ],
            }
        ]
    )
    judgment = refresh_judgment_plan_after_governance_filter(
        {**judgment, "required_dimension_ids": ["fundamentals", "product_and_production"]}
    )
    memo = build_multi_agent_memo_draft(judgment)
    memo["memo_profile"] = {"profile": "standard"}
    memo["dimension_analyses"] = [
        row for row in memo["dimension_analyses"] if row["dimension_id"] == "product_and_production"
    ]

    result = verify_multi_agent_memo_draft(memo, judgment)

    assert result["status"] == "fail"
    assert {
        error["type"]
        for error in result["analyst_depth_gate"]["errors"]
    } >= {"analyst_depth_required_dimensions_not_carried"}


def test_universe_relationship_plan_requires_relationship_evidence_and_rationale() -> None:
    result = validate_universe_relationship_plan(
        {
            "scope_mode": "full_universe",
            "focus_tickers": ["NVDA"],
            "expanded_tickers": ["NVDA", "AMD"],
            "relationships": [{"ticker": "NVDA", "related_ticker": "AMD", "relationship_type": "competitor"}],
        }
    )
    error_types = {item["type"] for item in result["errors"]}

    assert result["status"] == "fail"
    assert "relationship_scope_rationale_required" in error_types
    assert "relationship_without_evidence_refs" in error_types


def test_universe_relationship_plan_normalizes_valid_relationships() -> None:
    plan = normalize_universe_relationship_plan(
        {
            "scope_mode": "sector_representative",
            "focus_tickers": "nvda",
            "expanded_tickers": ["nvda", "amd"],
            "relationship_scope_rationale": "Peer comparison scope.",
            "relationships": [
                {
                    "ticker": "nvda",
                    "related_ticker": "amd",
                    "relationship_type": "competitor",
                    "evidence_refs": ["rel_ref_1"],
                    "confidence": 0.6,
                    "inclusion_rationale": "AMD is included as a peer comparison hypothesis.",
                }
            ],
        }
    )
    result = validate_universe_relationship_plan(plan, known_evidence_refs={"rel_ref_1"})

    assert result["status"] == "pass"
    assert plan["focus_tickers"] == ["NVDA"]
    assert plan["relationships"][0]["confidence"] == "medium"
