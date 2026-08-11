from __future__ import annotations

from sec_agent.multi_agent_contracts import (
    _unknown_numeric_tokens as _contracts_unknown_numeric_tokens,
    aggregate_focused_answer_judgment_plan,
    aggregate_specialist_judgment_plan,
    build_judgment_state,
    build_multi_agent_memo_draft,
    ledger_metric_display_value,
    normalize_universe_relationship_plan,
    refresh_judgment_plan_after_governance_filter,
    repair_multi_agent_memo_draft,
    validate_specialist_memolet,
    validate_universe_relationship_plan,
    verify_multi_agent_memo_draft,
    verify_specialist_outputs_for_memo,
)


def test_ledger_metric_display_value_prefers_display_value_lineage_over_raw_value() -> None:
    row = {
        "metric_family": "revenue",
        "metric_name": "Revenue",
        "display_value": "$366M",
        "raw_value_text": "366",
        "value": "1",
        "display_value_lineage": {"schema_version": "sec_agent_display_value_lineage_v0.1"},
    }

    assert ledger_metric_display_value(row) == "$366M"


def test_numeric_fidelity_accepts_chinese_usd_yi_converted_from_usd_millions() -> None:
    unknown = _contracts_unknown_numeric_tokens(
        "AMZN capex 为 -1510.03亿美元，DELL ISG 产品收入为 290.09亿美元。",
        "AMZN reported capital expenditures of -151003.0 usd_millions; DELL Total ISG net revenue was 29009.0 usd_millions.",
    )

    assert "-1510.03亿美元" not in unknown
    assert "290.09亿美元" not in unknown


def test_judgment_state_removes_resolved_false_capex_gap_dimension() -> None:
    judgment_state = build_judgment_state(
        {
            "supported_claims": [
                {
                    "claim_id": "amzn_capex",
                    "claim": "AMZN reported capital expenditure cash outflow/proxy of $151B.",
                    "claim_type": "company_reported_financial_fact",
                    "analysis_dimension": "capital_and_financing",
                    "memo_slot": "capital_allocation",
                    "ticker_scope": ["AMZN"],
                    "metric_scope": ["financial_metric:capex"],
                    "evidence_refs": ["amzn_capex_ref"],
                    "source_families": ["primary_sec_filing"],
                    "claim_rank_score": 90,
                },
                {
                    "claim_id": "googl_capex",
                    "claim": "GOOGL reported capital expenditure cash outflow/proxy of $110B.",
                    "claim_type": "company_reported_financial_fact",
                    "analysis_dimension": "capital_and_financing",
                    "memo_slot": "capital_allocation",
                    "ticker_scope": ["GOOGL"],
                    "metric_scope": ["financial_metric:capex"],
                    "evidence_refs": ["googl_capex_ref"],
                    "source_families": ["primary_sec_filing"],
                    "claim_rank_score": 89,
                },
                {
                    "claim_id": "msft_capex",
                    "claim": "MSFT reported capital expenditures of $9.1B.",
                    "claim_type": "company_reported_financial_fact",
                    "analysis_dimension": "capital_and_financing",
                    "memo_slot": "capital_allocation",
                    "ticker_scope": ["MSFT"],
                    "metric_scope": ["financial_metric:capex"],
                    "evidence_refs": ["msft_capex_ref"],
                    "source_families": ["primary_sec_filing"],
                    "claim_rank_score": 88,
                },
            ],
            "thesis_driver_pack": {
                "thesis_cards": [{"core_thesis": "Cloud capex supports AI infrastructure demand.", "stance": "supported"}],
                "driver_cards": [
                    {
                        "driver_id": "capital_driver",
                        "source_claim_id": "amzn_capex",
                        "memo_slot": "capital_allocation",
                        "statement": "AMZN capex is available.",
                        "evidence_refs": ["amzn_capex_ref"],
                    }
                ],
                "gap_cards": [
                    {
                        "gap_id": "obsolete_capex_gap",
                        "analysis_dimension": "risk_and_counterevidence",
                        "statement": "No capex data for MSFT, AMZN, or GOOGL in bounded evidence.",
                        "evidence_refs": [],
                    }
                ],
            },
        }
    )

    texts = " ".join(
        str(row.get("summary") or "") + " " + str(row.get("counter_read") or "")
        for row in judgment_state["dimension_judgments"]
    )
    assert "No capex data" not in texts
    assert not any(
        row["dimension_id"] == "risk_and_counterevidence" and not row.get("claim_ids") and not row.get("gap_ids")
        for row in judgment_state["dimension_judgments"]
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


def test_judgment_candidate_becomes_writer_ready_judgment_card() -> None:
    memolet = {
        "agent_id": "product_technology_analyst",
        "status": "pass",
        "judgment_candidates": [
            {
                "judgment": (
                    "NVDA Blackwell architecture and deployment evidence support a bounded accelerator "
                    "capability judgment, but not SKU revenue or shipment share."
                ),
                "required_item_answered": "product_architecture_competition",
                "supported_by_evidence_refs": ["pig_spec:blackwell", "pig_deploy:cloud"],
                "graph_edge_refs": ["pig_edge:nvda_dell_supply"],
                "product_or_financial_bridge": (
                    "Supports product capability and demand validation; margin/revenue require exact financial bridge."
                ),
                "business_mechanism": "Higher accelerator capability can raise adoption pull through server OEM configurations.",
                "counter_read": "No company-disclosed SKU revenue, ASP, shipment, or customer order value.",
                "confidence": "medium",
                "cannot_infer": ["product revenue", "shipment share", "customer order value"],
                "what_would_change_view": ["issuer-bound deployment volume", "product KPI exact row"],
                "ticker_scope": ["NVDA"],
                "metric_scope": ["architecture", "deployment"],
                "source_families": ["company_product_evidence_graph"],
            }
        ],
    }

    validation = validate_specialist_memolet(
        memolet,
        known_evidence_refs={"pig_spec:blackwell", "pig_deploy:cloud"},
    )
    judgment = aggregate_specialist_judgment_plan([memolet])

    assert validation["status"] == "pass"
    supported = [claim for claim in judgment["supported_claims"] if claim.get("judgment_candidate")]
    assert supported
    claim = supported[0]
    assert claim["claim_card_version"] == "v0.4_judgment_candidate"
    assert claim["required_item_answered"] == "product_architecture_competition"
    assert claim["analyst_depth"]["graph_edge_refs"] == ["pig_edge:nvda_dell_supply"]
    card = next(item for item in judgment["judgment_cards"] if item["source_claim_id"] == claim["claim_id"])
    assert card["writer_use"] == "bounded_judgment_unit_not_raw_evidence_inventory"
    assert "Higher accelerator capability" in card["business_mechanism"]
    assert any("product KPI exact row" in item for item in card["what_would_change_view"])


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


def test_official_issuer_source_coverage_does_not_become_dimension_primary_claim() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": (
                            "AMZN targeted web repair reached official issuer sources. This supports issuer coverage "
                            "and disclosure-path analysis, but it does not promote exact sales, orders, backlog, "
                            "shipments, share, ASP, or inventory values."
                        ),
                        "claim_type": "official_issuer_context",
                        "evidence_refs": ["official_issuer:amzn"],
                        "source_families": ["live_public_web_context"],
                        "memo_slot": "fundamentals",
                        "ticker_scope": ["AMZN"],
                        "metric_scope": ["issuer_official_context", "issuer identity", "filing coverage"],
                        "materiality": "medium",
                        "confidence": "medium",
                    },
                    {
                        "claim": "AMZN reported capital expenditures increased, supporting AI infrastructure demand-pool intensity.",
                        "claim_type": "company_reported_financial_fact",
                        "evidence_refs": ["amzn_capex_ref"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "fundamentals",
                        "analysis_dimension": "fundamentals",
                        "ticker_scope": ["AMZN"],
                        "metric_scope": ["financial_metric:capex"],
                        "materiality": "high",
                        "confidence": "high",
                    },
                ],
            }
        ]
    )

    coverage_claim = next(
        claim for claim in judgment["supported_claims"] if claim["claim_type"] == "official_issuer_context"
    )
    assert coverage_claim["claim_rank_bucket"] == "evidence_summary_or_gap"
    assert "source_coverage_context_not_main_claim" in coverage_claim["claim_rank_reasons"]

    section = next(
        item for item in judgment["thesis_driver_pack"]["dimension_sections"] if item["dimension_id"] == "capital_and_financing"
    )
    assert "capital expenditures" in section["section_thesis"]
    assert "targeted web repair" not in section["section_thesis"]
    assert not any("issuer_official" in basis.lower() for basis in section.get("comparison_basis") or [])
    assert not any(
        item["dimension_id"] == "product_and_production"
        and "targeted web repair" in str(item.get("section_thesis") or "")
        for item in judgment["thesis_driver_pack"]["dimension_sections"]
    )


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


def test_product_revenue_observation_is_routed_to_product_surface_even_from_fundamental_agent() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": (
                            "DELL's AI-optimized server revenue of $16.1B represents over 55% "
                            "of total ISG net revenue ($29.0B)."
                        ),
                        "claim_type": "business_observation",
                        "evidence_refs": [
                            "interactive::DELL::2026::product_revenue::total_value::ai_optimized_servers",
                            "interactive::DELL::2026::product_revenue::total_value::total_isg_net_revenue",
                        ],
                        "source_families": ["company_authored_unaudited_sec_filing"],
                        "memo_slot": "fundamentals",
                        "ticker_scope": ["DELL"],
                        "metric_scope": ["product_revenue"],
                        "materiality": "high",
                        "confidence": "high",
                    }
                ],
            }
        ]
    )
    claim = judgment["supported_claims"][0]
    outline = {row["memo_slot"]: row for row in judgment["memo_outline"]}
    pack = judgment["thesis_driver_pack"]
    product_section = next(row for row in pack["dimension_sections"] if row["dimension_id"] == "product_and_production")

    assert claim["memo_slot"] == "product_technology"
    assert claim["analysis_dimension"] == "product_and_production"
    assert outline["product_technology"]["status"] == "supported"
    assert claim["claim_id"] in product_section["primary_claim_ids"]


def test_judgment_cards_and_thesis_path_bridge_product_to_financial_judgment() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "DELL reported revenue growth and gross margin facts define earnings quality.",
                        "claim_type": "company_reported_financial_fact",
                        "evidence_refs": ["dell_revenue", "dell_gross_margin"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "fundamentals",
                        "ticker_scope": ["DELL"],
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
                        "claim": "DELL AI server product family evidence supports product adoption but does not prove SKU-level margin.",
                        "claim_type": "product_taxonomy_context",
                        "evidence_refs": ["dell_ai_server_product_family"],
                        "source_families": ["company_product_evidence_graph"],
                        "memo_slot": "product_technology",
                        "ticker_scope": ["DELL"],
                        "metric_scope": ["product_family", "server_configuration"],
                        "materiality": "medium",
                        "confidence": "medium",
                        "missing_confirmations": ["Named customer deployment or order-scale evidence would upgrade the read-through."],
                    }
                ],
            },
        ]
    )

    judgment_cards = judgment["judgment_cards"]
    thesis_path = judgment["thesis_path"]
    product_card = next(card for card in judgment_cards if card["dimension_id"] == "product_and_production")

    assert product_card["mechanism_bridge_status"] == "pass"
    assert product_card["evidence_bridge"]
    assert "SKU-level margin" in product_card["judgment"]
    assert thesis_path["mechanism_bridge_status"] == "pass"
    assert any(edge["edge_type"] == "product_to_financial_bridge" for edge in thesis_path["path_edges"])

    judgment_state = build_judgment_state(judgment)
    assert judgment_state["judgment_cards"][0]["judgment_card_id"]
    assert judgment_state["thesis_path"]["path_nodes"]


def test_judgment_state_keeps_research_lead_official_product_context_in_product_dimension() -> None:
    judgment_state = build_judgment_state(
        {
            "supported_claims": [
                {
                    "claim_id": "product_fact_lrcx_china_revenue",
                    "claim": "LRCX reported revenue for China.",
                    "claim_type": "company_reported_financial_fact",
                    "analysis_dimension": "product_and_production",
                    "memo_slot": "product_technology",
                    "evidence_refs": ["lrcx_revenue_ref"],
                    "source_families": ["primary_sec_filing"],
                    "metric_scope": ["financial_metric:revenue"],
                },
                {
                    "claim_id": "lead_targeted_repair_claim:asml:official",
                    "agent_id": "research_lead",
                    "claim": (
                        "ASML official-source repair reached company/SEC issuer sources and identified "
                        "product-surface leads including EUV lithography systems, DUV lithography systems, "
                        "Installed Base Management; official parser targets include net bookings, backlog, systems revenue."
                    ),
                    "claim_type": "product_taxonomy_context",
                    "analysis_dimension": "product_and_production",
                    "memo_slot": "product_technology",
                    "ticker_scope": ["ASML"],
                    "metric_scope": ["product_surface_context", "net bookings", "backlog"],
                    "evidence_refs": ["official_asml_euv", "official_asml_duv"],
                    "source_families": ["live_public_web_context"],
                },
            ],
            "thesis_driver_pack": {
                "thesis_cards": [{"core_thesis": "Semicap cycle evidence is mixed.", "stance": "neutral", "confidence": "medium"}],
                "dimension_sections": [
                    {
                        "dimension_id": "product_and_production",
                        "title": "Product and production line evidence",
                        "summary": "LRCX China revenue is visible, but product KPI coverage is incomplete.",
                        "primary_claim_ids": ["product_fact_lrcx_china_revenue"],
                        "evidence_refs": ["lrcx_revenue_ref"],
                    }
                ],
            },
        }
    )

    product_dimension = next(row for row in judgment_state["dimension_judgments"] if row["dimension_id"] == "product_and_production")

    assert "lead_targeted_repair_claim:asml:official" in product_dimension["claim_ids"]
    assert "official_asml_euv" in product_dimension["evidence_refs"]
    assert "ASML official-source repair" in product_dimension["summary"]
    assert "EUV lithography systems" in product_dimension["summary"]
    assert "exact orders, backlog, sales" in product_dimension["financial_bridge"]
    assert "parser-authority facts" in product_dimension["financial_bridge"]


def test_capex_only_observation_is_not_routed_to_product_surface_by_provider_wording() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": (
                            "Supplier capex for DELL, VRT, and ANET is smaller than hyperscaler capex, "
                            "consistent with their role as equipment providers rather than cloud operators."
                        ),
                        "claim_type": "business_observation",
                        "evidence_refs": ["supplier_capex_ref"],
                        "source_families": ["company_authored_unaudited_sec_filing"],
                        "memo_slot": "fundamentals",
                        "ticker_scope": ["DELL", "VRT", "ANET"],
                        "metric_scope": ["capex"],
                        "materiality": "high",
                        "confidence": "high",
                    }
                ],
            }
        ]
    )
    claim = judgment["supported_claims"][0]
    pack = judgment["thesis_driver_pack"]
    product_sections = [row for row in pack["dimension_sections"] if row["dimension_id"] == "product_and_production"]
    capital_section = next(row for row in pack["dimension_sections"] if row["dimension_id"] == "capital_and_financing")

    assert claim["memo_slot"] == "fundamentals"
    assert claim["analysis_dimension"] == "capital_and_financing"
    assert not product_sections
    assert claim["claim_id"] in capital_section["primary_claim_ids"]


def test_capex_only_observation_is_not_routed_to_product_surface_by_capacity_wording() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": (
                            "DELL's capex of -$963M in QTD 2026 is significantly higher than peers "
                            "ANET (-$54.5M) and VRT (-$112.6M), reflecting heavy investment in AI "
                            "infrastructure capacity."
                        ),
                        "claim_type": "business_observation",
                        "evidence_refs": ["dell_capex_ref", "anet_capex_ref", "vrt_capex_ref"],
                        "source_families": ["company_authored_unaudited_sec_filing"],
                        "memo_slot": "fundamentals",
                        "ticker_scope": ["DELL", "ANET", "VRT"],
                        "metric_scope": ["capex"],
                        "materiality": "high",
                        "confidence": "high",
                    }
                ],
            }
        ]
    )
    claim = judgment["supported_claims"][0]
    capital_section = next(row for row in judgment["thesis_driver_pack"]["dimension_sections"] if row["dimension_id"] == "capital_and_financing")

    assert claim["analysis_dimension"] == "capital_and_financing"
    assert claim["analyst_depth"]["analysis_dimension"] == "capital_and_financing"
    assert not [row for row in judgment["thesis_driver_pack"]["dimension_sections"] if row["dimension_id"] == "product_and_production"]
    assert claim["claim_id"] in capital_section["primary_claim_ids"]


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


def test_thesis_synthesis_uses_product_technology_as_business_slot() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "NVDA reported data center revenue and gross margin evidence that supports AI demand exposure.",
                        "claim_type": "company_reported_financial_fact",
                        "evidence_refs": ["nvda_financial_ref"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "fundamentals",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["data_center_revenue", "gross_margin"],
                        "materiality": "high",
                        "confidence": "high",
                    }
                ],
            },
            {
                "agent_id": "product_technology_analyst",
                "observations": [
                    {
                        "claim": "NVDA product evidence shows H100/H200/B200/GB200/Blackwell accelerator platform context.",
                        "claim_type": "technical_product_fact",
                        "evidence_refs": ["nvda_product_ref"],
                        "source_families": ["company_product_evidence_graph"],
                        "memo_slot": "product_technology",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["gpu_accelerator", "technical_spec"],
                        "materiality": "high",
                        "confidence": "medium",
                        "claim_boundary": "Product capability context only; not SKU revenue, shipment, ASP, or market share.",
                    }
                ],
            },
        ]
    )

    thesis = judgment["supported_claims"][0]

    assert judgment["thesis_synthesis"]["status"] == "synthesized"
    assert thesis["claim_id"] == "judgment_plan_aggregator_thesis_1"
    assert thesis["memo_slot"] == "thesis"
    assert set(thesis["derived_from_claim_ids"]) >= {"fundamental_analyst_claim_1", "product_technology_analyst_claim_2"}
    assert "nvda_product_ref" in thesis["evidence_refs"]


def test_runtime_memo_slot_aliases_do_not_default_to_thesis() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "industry_supply_chain_analyst",
                "observations": [
                    {
                        "claim": "NVDA GPU accelerators are component inputs to server OEM systems.",
                        "claim_type": "product_relationship_graph_bounded_claim",
                        "evidence_refs": ["ev_nvda_dell_component_edge"],
                        "source_families": ["relationship_graph"],
                        "memo_slot": "industry_supply_chain",
                        "ticker_scope": ["NVDA", "DELL"],
                        "metric_scope": ["COMPONENT_INPUT_TO"],
                        "materiality": "medium",
                        "confidence": "medium",
                    }
                ],
            },
            {
                "agent_id": "market_valuation_analyst",
                "observations": [
                    {
                        "claim": "Market proxy context is useful but bounded.",
                        "claim_type": "market_or_competitive_context",
                        "evidence_refs": ["ev_market_proxy"],
                        "source_families": ["market_snapshot"],
                        "memo_slot": "competition_market",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["valuation_proxy"],
                        "materiality": "medium",
                        "confidence": "medium",
                    }
                ],
            },
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "Capital allocation context is a fundamentals-facing input.",
                        "claim_type": "company_reported_financial_fact",
                        "evidence_refs": ["ev_capital_allocation"],
                        "source_families": ["primary_sec_filing"],
                        "memo_slot": "capital_allocation",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["capex"],
                        "materiality": "medium",
                        "confidence": "medium",
                    }
                ],
            },
        ]
    )
    by_claim = {claim["claim_id"]: claim["memo_slot"] for claim in judgment["supported_claims"]}
    outline_slots = {row["memo_slot"] for row in judgment["memo_outline"]}

    assert by_claim["industry_supply_chain_analyst_claim_1"] == "industry_relationship"
    assert by_claim["market_valuation_analyst_claim_2"] == "market_valuation"
    assert by_claim["fundamental_analyst_claim_3"] == "fundamentals"
    assert "industry_relationship" in outline_slots
    assert "market_valuation" in outline_slots
    assert not any(
        claim["claim_id"] != "judgment_plan_aggregator_thesis_1" and claim["memo_slot"] == "thesis"
        for claim in judgment["supported_claims"]
    )


def test_market_judgment_candidate_without_explicit_slot_defaults_to_market_slot() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "market_valuation_analyst",
                "status": "pass",
                "judgment_candidates": [
                    {
                        "judgment": (
                            "Hyperscaler capex supports AI infrastructure demand, but market price-in "
                            "cannot be assessed without valuation or positioning rows."
                        ),
                        "required_item_answered": "capital_market_price_in",
                        "supported_by_evidence_refs": ["msft_capex_ref", "amzn_capex_ref"],
                        "product_or_financial_bridge": "Capex is demand context, not supplier revenue.",
                        "business_mechanism": "Large cloud capex can support demand for AI infrastructure suppliers.",
                        "counter_read": "No valuation or positioning rows are present.",
                        "confidence": "medium",
                        "ticker_scope": ["MSFT", "AMZN", "NVDA", "DELL"],
                        "metric_scope": ["capex"],
                    }
                ],
            }
        ]
    )

    market_claim = next(
        claim for claim in judgment["supported_claims"] if claim.get("agent_id") == "market_valuation_analyst"
    )
    outline_slots = {row["memo_slot"] for row in judgment["memo_outline"] if row.get("status") == "supported"}

    assert market_claim["memo_slot"] == "market_valuation"
    assert "market_valuation" in outline_slots
    assert market_claim["memo_slot"] != "evidence_gap"


def test_market_judgment_candidate_with_stale_gap_slot_recovers_to_market_slot() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "market_valuation_analyst",
                "status": "pass",
                "judgment_candidates": [
                    {
                        "judgment": (
                            "Hyperscaler capex from AMZN and MSFT is large and growing, providing "
                            "a supportive demand backdrop for AI infrastructure suppliers."
                        ),
                        "required_item_answered": "capital_market_price_in",
                        "supported_by_evidence_refs": ["msft_capex_ref", "amzn_capex_ref"],
                        "memo_slot": "evidence_gap",
                        "confidence": "medium",
                    }
                ],
                "unsupported_claims": [
                    {
                        "claim": "Market valuation and positioning rows are absent.",
                        "reason": "No market snapshot rows.",
                    }
                ],
            }
        ]
    )

    market_claim = next(
        claim for claim in judgment["supported_claims"] if claim.get("agent_id") == "market_valuation_analyst"
    )
    outline_slots = {row["memo_slot"]: row for row in judgment["memo_outline"]}

    assert market_claim["memo_slot"] == "market_valuation"
    assert outline_slots["market_valuation"]["status"] == "supported"
    assert any(claim.get("agent_id") == "market_valuation_analyst" for claim in judgment["unsupported_claims"])


def test_thesis_driver_pack_preserves_non_financial_signal_authority_fields() -> None:
    judgment = aggregate_specialist_judgment_plan(
        [
            {
                "agent_id": "product_technology_analyst",
                "observations": [
                    {
                        "claim": "Official customer deployment evidence supports a bounded accelerator adoption signal.",
                        "claim_type": "deployment_signal",
                        "evidence_refs": ["r17_nvda_xai_colossus"],
                        "source_families": ["public_source_context"],
                        "memo_slot": "product_technology",
                        "ticker_scope": ["NVDA"],
                        "metric_scope": ["deployment_signal"],
                        "materiality": "high",
                        "confidence": "medium",
                        "signal_authority_type": "customer_deployment_signal",
                        "signal_promotion_level": "thesis_driver_allowed",
                        "thesis_driver_authority": True,
                        "allowed_non_financial_claims": ["deployment_signal", "customer_adoption_signal"],
                        "claim_boundary": "Deployment signal only; not revenue, ASP, sales, share, or order value.",
                    }
                ],
            }
        ]
    )

    card = judgment["thesis_driver_pack"]["driver_cards"][0]
    assert card["signal_authority_type"] == "customer_deployment_signal"
    assert card["signal_promotion_level"] == "thesis_driver_allowed"
    assert card["thesis_driver_authority"] is True
    assert "deployment_signal" in card["allowed_non_financial_claims"]
    assert "not revenue" in card["claim_boundary"]


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
    assert dimensions["risk_and_counterevidence"]["counter_claim_ids"] == ["counter_conflict_1"]
    judgment_state = build_judgment_state({**judgment, "required_dimension_ids": ["risk_and_counterevidence"]})
    risk_state = {
        row["dimension_id"]: row for row in judgment_state["dimension_judgments"]
    }["risk_and_counterevidence"]
    assert risk_state["counter_claim_ids"] == ["counter_conflict_1"]
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


def test_refresh_recomputes_stale_no_supported_claim_blocker_after_pre_memo_fact_injection() -> None:
    judgment = {
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
        "source_boundary_notes": [],
        "memo_constraints": {
            "memo_writer_allowed": False,
            "blocked_reasons": ["unsupported_specialist_claims_without_supported_claims"],
            "missing_evidence": [{"gap_id": "bounded_gap_1", "reason": "bounded_gap"}],
            "approved_fact_count": 1,
        },
        "memo_writer_allowed": False,
    }

    refreshed = refresh_judgment_plan_after_governance_filter(judgment)
    verification = verify_specialist_outputs_for_memo([], judgment_plan=refreshed)
    memo = build_multi_agent_memo_draft(refreshed, specialist_verification=verification)

    assert refreshed["memo_writer_allowed"] is True
    assert "unsupported_specialist_claims_without_supported_claims" not in refreshed["memo_constraints"]["blocked_reasons"]
    assert refreshed["memo_constraints"]["approved_fact_count"] == 1
    assert verification["memo_writer_allowed"] is True
    assert memo["answer_status"] == "draft"
    assert memo["memo_claims"][0]["claim_id"] == "pre_memo_fact_claim:klac_patterning"


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


def test_universe_relationship_plan_accepts_external_counterparty_endpoint_without_ticker_expansion() -> None:
    plan = normalize_universe_relationship_plan(
        {
            "scope_mode": "sector_representative",
            "focus_tickers": ["AMD"],
            "included_tickers": ["AMD"],
            "relationship_scope_rationale": "Issuer-official customer/deployment context without a listed counterparty ticker.",
            "relationships": [
                {
                    "ticker": "AMD",
                    "from_ticker": "AMD",
                    "from_node_id": "company_product_family:AMD:gpu_accelerator",
                    "to_node_id": "external_counterparty:counterparty:554a393e45b8b138",
                    "related_entity_id": "external_counterparty:counterparty:554a393e45b8b138",
                    "relationship_type": "supplier",
                    "original_relationship_type": "OFFICIAL_SUPPLY_CHAIN_RELATIONSHIP",
                    "direction": "issuer_to_supply_chain_context",
                    "evidence_refs": ["official_customer_deployment_surface:sample"],
                    "inclusion_rationale": "Official relationship context can support deployment/adoption hypotheses only.",
                    "inference_level": "disclosed_indirect",
                    "confirmation_status": "parser_backed_context_edge",
                }
            ],
        }
    )
    result = validate_universe_relationship_plan(
        plan,
        known_evidence_refs={"official_customer_deployment_surface:sample"},
    )

    assert result["status"] == "pass"
    assert plan["included_tickers"] == ["AMD"]
    assert plan["expanded_tickers"] == ["AMD"]
    assert plan["relationships"][0]["to_ticker"] == ""
    assert plan["relationships"][0]["related_entity_id"].startswith("external_counterparty:")
    assert plan["relationships"][0]["original_relationship_type"] == "OFFICIAL_SUPPLY_CHAIN_RELATIONSHIP"
