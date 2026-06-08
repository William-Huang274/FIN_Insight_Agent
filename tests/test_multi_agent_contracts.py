from __future__ import annotations

from sec_agent.multi_agent_contracts import (
    aggregate_focused_answer_judgment_plan,
    aggregate_specialist_judgment_plan,
    build_multi_agent_memo_draft,
    normalize_specialist_memolet,
    normalize_universe_relationship_plan,
    validate_specialist_memolet,
    validate_universe_relationship_plan,
    verify_multi_agent_memo_draft,
    verify_specialist_outputs_for_memo,
)


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


def test_specialist_memolet_preserves_structured_evidence_gap_requests() -> None:
    memolet = normalize_specialist_memolet(
        {
            "agent_id": "industry_supply_chain_analyst",
            "status": "partial",
            "evidence_gap_requests": [
                {
                    "request_type": "relationship_confirmation",
                    "owner_agent": "universe_relationship",
                    "tickers": ["nvda", "vrt"],
                    "source_family": "relationship_graph",
                    "reason": "Need bounded relationship evidence for AI infrastructure demand transmission.",
                    "blocking_level": "material",
                    "can_answer_bounded_without": True,
                }
            ],
        }
    )
    result = validate_specialist_memolet(memolet)

    assert result["status"] == "pass"
    gap = result["memolet"]["evidence_gap_requests"][0]
    assert gap["tickers"] == ["NVDA", "VRT"]
    assert gap["owner_agent"] == "universe_relationship"


def test_judgment_and_memo_preserve_specialist_evidence_gap_requests() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "industry_supply_chain_analyst",
                "status": "partial",
                "observations": [
                    {
                        "claim": "Relationship evidence only supports a hypothesis-grade AI infrastructure readthrough.",
                        "claim_type": "relationship_hypothesis",
                        "evidence_refs": ["rel_ref_1"],
                        "source_families": ["relationship_graph"],
                        "memo_slot": "industry_relationship",
                        "materiality": "medium",
                    }
                ],
                "evidence_gap_requests": [
                    {
                        "request_type": "relationship_confirmation",
                        "owner_agent": "universe_relationship",
                        "tickers": ["NVDA", "VRT"],
                        "source_family": "relationship_graph",
                        "reason": "Need company-confirming evidence before treating VRT as more than a hypothesis.",
                        "blocking_level": "material",
                        "can_answer_bounded_without": True,
                    }
                ],
            }
        ]
    )
    memo = build_multi_agent_memo_draft(judgment)

    assert judgment["status"] == "partial"
    assert judgment["evidence_gap_requests"][0]["request_type"] == "relationship_confirmation"
    assert judgment["memo_constraints"]["evidence_gap_request_count"] == 1
    assert "preserve_specialist_evidence_gap_requests_for_coverage_reflection" in judgment["memo_constraints"]["required_caveats"]
    assert memo["evidence_gap_requests"][0]["owner_agent"] == "universe_relationship"


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
    memo = build_multi_agent_memo_draft(judgment)
    verification = verify_multi_agent_memo_draft(memo, judgment)

    relationship_claim = next(claim for claim in judgment["supported_claims"] if claim["agent_id"] == "industry_supply_chain_analyst")
    assert relationship_claim["claim_type"] == "relationship_hypothesis"
    assert any(claim["claim_type"] == "relationship_hypothesis" for claim in memo["memo_claims"])
    assert verification["status"] == "pass"


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
