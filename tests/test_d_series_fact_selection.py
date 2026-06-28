from __future__ import annotations

from sec_agent.d_series_fact_selection import (
    PRE_MEMO_FACT_SELECTION_SCHEMA_VERSION,
    apply_pre_memo_fact_selection_to_judgment,
    build_pre_memo_fact_selection,
)


def test_pre_memo_fact_selection_blocks_unresolved_or_gate_failed_facts() -> None:
    selection = build_pre_memo_fact_selection(
        {
            "run_id": "unit-d6-d9-d10",
            "reconciliation_ledger": {
                "candidates": [
                    {
                        "candidate_id": "candidate_good",
                        "evidence_ref": "good_ev",
                    },
                    {
                        "candidate_id": "candidate_bad",
                        "evidence_ref": "bad_ev",
                    },
                ],
                "reconciliation_groups": [
                    {
                        "group_id": "group_good",
                        "ticker": "MSFT",
                        "canonical_metric_id": "financial:revenue",
                        "period_key": "FY2025",
                        "resolution_status": "resolved_exact",
                        "candidate_ids": ["candidate_good"],
                        "preferred_value": {
                            "candidate_id": "candidate_good",
                            "value": "100",
                            "numeric_value": "100",
                            "unit": "USD",
                            "source_id": "sec-msft-revenue",
                            "evidence_ref": "good_ev",
                            "source_family": "primary_sec_filing",
                        },
                    },
                    {
                        "group_id": "group_bad",
                        "ticker": "MSFT",
                        "canonical_metric_id": "product_kpi:shipments",
                        "period_key": "FY2025",
                        "resolution_status": "unresolved_conflict",
                        "candidate_ids": ["candidate_bad"],
                        "conflict_gap_id": "gap_shipments_conflict",
                    },
                ],
            },
            "gate_registry_eval_matrix": {
                "gate_history": [
                    {
                        "gate_result_id": "gate_bad",
                        "gate_id": "source_boundary_gate",
                        "target_object_id": "group_bad",
                        "status": "fail",
                        "blocks_claim_fact_layer": True,
                    }
                ]
            },
            "derived_metric_layer": {
                "derived_metrics": [
                    {
                        "derived_metric_id": "gross_margin_msft",
                        "derived_metric_family": "margin",
                        "ticker": "MSFT",
                        "value": "25",
                        "unit": "%",
                        "period_key": "FY2025",
                        "input_fact_ids": ["candidate_good"],
                        "gate_status": "pass",
                    },
                    {
                        "derived_metric_id": "asp_msft",
                        "derived_metric_family": "asp",
                        "ticker": "MSFT",
                        "input_fact_ids": ["candidate_bad"],
                        "gate_status": "pass",
                    },
                ]
            },
            "typed_gap_ledger": {
                "gaps": [
                    {
                        "gap_id": "gap_commercial_share",
                        "gap_type": "commercial_gap",
                        "ticker": "MSFT",
                        "metric": "market_share",
                    }
                ]
            },
        }
    )

    assert selection["schema_version"] == PRE_MEMO_FACT_SELECTION_SCHEMA_VERSION
    assert selection["validation"]["status"] == "pass"
    assert [row["fact_id"] for row in selection["approved_facts"]] == ["candidate_good"]
    assert selection["rejected_facts"][0]["reconciliation_group_id"] == "group_bad"
    assert selection["blocked_evidence_refs"] == ["bad_ev"]
    assert selection["approved_derived_metrics"][0]["derived_metric_id"] == "gross_margin_msft"
    assert selection["rejected_derived_metrics"][0]["derived_metric_id"] == "asp_msft"
    assert {row["gap_id"] for row in selection["bounded_gap_links"]} == {
        "gap_commercial_share",
        "gap_shipments_conflict",
    }


def test_pre_memo_fact_selection_moves_blocked_supported_claims_to_unsupported() -> None:
    selection = build_pre_memo_fact_selection(
        {
            "reconciliation_ledger": {
                "candidates": [{"candidate_id": "candidate_bad", "evidence_ref": "bad_ev"}],
                "reconciliation_groups": [
                    {
                        "group_id": "group_bad",
                        "ticker": "MSFT",
                        "canonical_metric_id": "product_kpi:shipments",
                        "resolution_status": "unresolved_conflict",
                        "candidate_ids": ["candidate_bad"],
                        "conflict_gap_id": "gap_shipments_conflict",
                    }
                ],
            }
        }
    )
    judgment = {
        "aggregation_policy": "rank_supported_claim_cards_preserve_conflicts_no_average",
        "memo_writer_allowed": True,
        "supported_claims": [
            {
                "claim_id": "claim_bad",
                "claim": "MSFT shipments grew.",
                "evidence_refs": ["bad_ev"],
                "fact_ids": ["candidate_bad"],
            }
        ],
        "unsupported_claims": [],
    }

    filtered = apply_pre_memo_fact_selection_to_judgment(judgment, selection)

    assert filtered["supported_claims"] == []
    assert filtered["unsupported_claims"][0]["reason"] == "blocked_by_pre_memo_fact_selection"
    assert "MSFT shipments grew" not in filtered["unsupported_claims"][0]["claim"]
    assert filtered["unsupported_claims"][0]["source_claim"]["claim"] == "MSFT shipments grew."
    assert filtered["memo_writer_allowed"] is False
    assert filtered["aggregation_policy"] == "rank_supported_claim_cards_preserve_conflicts_no_average"
    assert filtered["governance_filter_policy"] == "pre_memo_governance_filtered_claim_cards_v0_1"


def test_pre_memo_fact_selection_adds_deterministic_claim_cards_for_approved_financial_facts() -> None:
    selection = build_pre_memo_fact_selection(
        {
            "reconciliation_ledger": {
                "candidates": [
                    {"candidate_id": "msft_capex", "evidence_ref": "msft_capex_ref"},
                    {"candidate_id": "aapl_margin", "evidence_ref": "aapl_margin_ref"},
                    {"candidate_id": "dell_ai_server_revenue", "evidence_ref": "dell_ai_server_ref"},
                ],
                "reconciliation_groups": [
                    {
                        "group_id": "group_msft_capex",
                        "ticker": "MSFT",
                        "canonical_metric_id": "financial_metric:capex",
                        "period_key": "fiscal:2026:Q3:ytd",
                        "resolution_status": "resolved_single_candidate",
                        "candidate_ids": ["msft_capex"],
                        "preferred_value": {
                            "candidate_id": "msft_capex",
                            "value": "9.1",
                            "numeric_value": "9.1",
                            "unit": "usd_billions",
                            "source_id": "sec-msft-capex",
                            "evidence_ref": "msft_capex_ref",
                            "source_family": "primary_sec_filing",
                            "resolution_rule": "single_exact_authority_candidate",
                            "confidence": "high",
                        },
                    },
                    {
                        "group_id": "group_aapl_margin",
                        "ticker": "AAPL",
                        "canonical_metric_id": "financial_metric:gross_margin",
                        "period_key": "fiscal:2026:Q2:qtd",
                        "resolution_status": "resolved_single_candidate",
                        "candidate_ids": ["aapl_margin"],
                        "preferred_value": {
                            "candidate_id": "aapl_margin",
                            "value": "39.9",
                            "numeric_value": "39.9",
                            "unit": "percent",
                            "source_id": "sec-aapl-margin",
                            "evidence_ref": "aapl_margin_ref",
                            "source_family": "primary_sec_filing",
                            "resolution_rule": "single_exact_authority_candidate",
                            "confidence": "high",
                        },
                    },
                    {
                        "group_id": "group_dell_ai_server_revenue",
                        "ticker": "DELL",
                        "canonical_metric_id": "product_kpi:product_revenue",
                        "product_or_segment": "AI-optimized servers",
                        "period_key": "fiscal:2026:Q1:qtd",
                        "resolution_status": "resolved_single_candidate",
                        "candidate_ids": ["dell_ai_server_revenue"],
                        "preferred_value": {
                            "candidate_id": "dell_ai_server_revenue",
                            "value": "16132",
                            "numeric_value": "16132",
                            "unit": "usd_millions",
                            "source_id": "dell-8k-ai-server",
                            "evidence_ref": "dell_ai_server_ref",
                            "source_family": "company_authored_unaudited_sec_filing",
                            "resolution_rule": "single_exact_authority_candidate",
                            "confidence": "high",
                        },
                    },
                ],
            }
        }
    )
    filtered = apply_pre_memo_fact_selection_to_judgment(
        {"memo_writer_allowed": True, "supported_claims": [], "unsupported_claims": []},
        selection,
    )
    by_metric = {
        row["metric_scope"][0]: row
        for row in filtered["supported_claims"]
        if row.get("agent_id") == "pre_memo_fact_selector"
    }

    assert selection["summary"]["approved_fact_count"] == 3
    assert by_metric["financial_metric:capex"]["analysis_dimension"] == "capital_and_financing"
    assert "9.1 usd_billions" in by_metric["financial_metric:capex"]["claim"]
    assert by_metric["financial_metric:gross_margin"]["evidence_refs"] == ["aapl_margin_ref"]
    assert by_metric["product_kpi:product_revenue"]["analysis_dimension"] == "product_and_production"
    assert by_metric["product_kpi:product_revenue"]["memo_slot"] == "product_technology"
    assert by_metric["product_kpi:product_revenue"]["claim_type"] == "company_reported_product_operating_fact"
    assert "AI-optimized servers" in by_metric["product_kpi:product_revenue"]["claim"]
    assert filtered["claim_card_stats"]["pre_memo_deterministic_fact_claim_count"] == 3


def test_pre_memo_fact_selection_formats_negative_capex_as_cash_outflow_proxy() -> None:
    selection = build_pre_memo_fact_selection(
        {
            "reconciliation_ledger": {
                "candidates": [{"candidate_id": "amzn_capex", "evidence_ref": "amzn_capex_ref"}],
                "reconciliation_groups": [
                    {
                        "group_id": "group_amzn_capex",
                        "ticker": "AMZN",
                        "canonical_metric_id": "financial_metric:capex",
                        "period_key": "fiscal:2026:ttm",
                        "resolution_status": "resolved_single_candidate",
                        "candidate_ids": ["amzn_capex"],
                        "preferred_value": {
                            "candidate_id": "amzn_capex",
                            "value": "-151003.0",
                            "numeric_value": "-151003.0",
                            "unit": "usd_millions",
                            "source_id": "source-amzn-capex",
                            "evidence_ref": "amzn_capex_ref",
                            "source_family": "company_authored_unaudited_sec_filing",
                            "resolution_rule": "single_exact_authority_candidate",
                            "confidence": "high",
                        },
                    }
                ],
            }
        }
    )
    filtered = apply_pre_memo_fact_selection_to_judgment(
        {"memo_writer_allowed": True, "supported_claims": [], "unsupported_claims": []},
        selection,
    )
    claim = next(row for row in filtered["supported_claims"] if row.get("agent_id") == "pre_memo_fact_selector")

    assert "capital expenditure cash outflow/proxy of 151003 usd_millions" in claim["claim"]
    assert "reported value -151003.0 usd_millions" in claim["claim"]
    assert any("negative sign reflects cash-flow convention" in caveat for caveat in claim["caveats"])


def test_pre_memo_fact_selection_keeps_product_claim_when_financial_facts_crowd_budget() -> None:
    candidates = []
    groups = []

    def add_group(index: int, ticker: str, metric: str, *, product: str = "") -> None:
        candidate_id = f"candidate_{index}"
        candidates.append({"candidate_id": candidate_id, "evidence_ref": f"ref_{index}"})
        groups.append(
            {
                "group_id": f"group_{index}",
                "ticker": ticker,
                "canonical_metric_id": metric,
                "product_or_segment": product,
                "period_key": f"fiscal:2026:Q{(index % 4) + 1}:qtd",
                "resolution_status": "resolved_single_candidate",
                "candidate_ids": [candidate_id],
                "preferred_value": {
                    "candidate_id": candidate_id,
                    "value": str(100 + index),
                    "numeric_value": str(100 + index),
                    "unit": "usd_millions",
                    "source_id": f"sec_{index}",
                    "evidence_ref": f"ref_{index}",
                    "source_family": "company_authored_unaudited_sec_filing",
                    "resolution_rule": "single_exact_authority_candidate",
                    "confidence": "high",
                },
            }
        )

    for index, ticker in enumerate(["AMZN", "ANET", "DELL", "GOOGL", "MSFT", "VRT", "ETN"], start=1):
        add_group(index, ticker, "financial_metric:capex")
    for index, ticker in enumerate(["AMZN", "DELL", "MSFT", "GOOGL", "VRT", "ANET", "ETN"], start=20):
        add_group(index, ticker, "financial_metric:revenue")
    add_group(90, "DELL", "product_kpi:product_revenue", product="AI-optimized servers")
    add_group(91, "DELL", "product_kpi:product_revenue", product="Traditional servers and networking")

    selection = build_pre_memo_fact_selection(
        {"reconciliation_ledger": {"candidates": candidates, "reconciliation_groups": groups}}
    )
    filtered = apply_pre_memo_fact_selection_to_judgment(
        {"memo_writer_allowed": True, "supported_claims": [], "unsupported_claims": []},
        selection,
    )
    deterministic = [
        row
        for row in filtered["supported_claims"]
        if row.get("agent_id") == "pre_memo_fact_selector"
    ]
    dimensions = {row["analysis_dimension"] for row in deterministic}
    product_claims = [
        row
        for row in deterministic
        if row.get("analysis_dimension") == "product_and_production"
    ]

    assert {"capital_and_financing", "fundamentals", "product_and_production"} <= dimensions
    assert any("AI-optimized servers" in row["claim"] for row in product_claims)
    assert len(deterministic) <= 18


def test_pre_memo_fact_selection_promotes_product_segment_revenue_dimension() -> None:
    candidates = []
    groups = []

    def add_revenue_group(index: int, product: str) -> None:
        candidate_id = f"healthcare_candidate_{index}"
        candidates.append({"candidate_id": candidate_id, "evidence_ref": f"healthcare_ref_{index}"})
        groups.append(
            {
                "group_id": f"healthcare_group_{index}",
                "ticker": "AMGN",
                "canonical_metric_id": "financial_metric:revenue",
                "product_or_segment": product,
                "period_key": "fiscal:2026:Q1:qtd",
                "resolution_status": "resolved_single_candidate",
                "candidate_ids": [candidate_id],
                "preferred_value": {
                    "candidate_id": candidate_id,
                    "value": str(700 + index),
                    "numeric_value": str(700 + index),
                    "unit": "usd_millions",
                    "source_id": f"amgn_product_{index}",
                    "evidence_ref": f"healthcare_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "resolution_rule": "single_exact_authority_candidate",
                    "confidence": "high",
                },
            }
        )

    add_revenue_group(1, "Total Prolia")
    add_revenue_group(2, "EVENITY — U.S.")
    add_revenue_group(3, "Other revenues")

    selection = build_pre_memo_fact_selection(
        {
            "user_query": "Analyze AMGN product revenue, Prolia, EVENITY, and product performance.",
            "reconciliation_ledger": {"candidates": candidates, "reconciliation_groups": groups},
        }
    )
    filtered = apply_pre_memo_fact_selection_to_judgment(
        {"memo_writer_allowed": True, "supported_claims": [], "unsupported_claims": []},
        selection,
    )
    deterministic = [
        row
        for row in filtered["supported_claims"]
        if row.get("agent_id") == "pre_memo_fact_selector"
    ]
    by_product = {row.get("product_or_segment"): row for row in deterministic}

    assert by_product["Total Prolia"]["analysis_dimension"] == "product_and_production"
    assert by_product["Total Prolia"]["memo_slot"] == "product_technology"
    assert by_product["EVENITY — U.S."]["analysis_dimension"] == "product_and_production"
    assert by_product["Other revenues"]["analysis_dimension"] == "fundamentals"


def test_pre_memo_fact_selection_rejects_investment_sales_and_cost_labels_as_revenue_claims() -> None:
    candidates = []
    groups = []

    def add_revenue_group(index: int, product: str) -> None:
        candidate_id = f"bad_revenue_candidate_{index}"
        candidates.append({"candidate_id": candidate_id, "evidence_ref": f"bad_revenue_ref_{index}"})
        groups.append(
            {
                "group_id": f"bad_revenue_group_{index}",
                "ticker": "AMAT",
                "canonical_metric_id": "financial_metric:revenue",
                "product_or_segment": product,
                "period_key": "fiscal:2026:Q1:qtd",
                "resolution_status": "resolved_single_candidate",
                "candidate_ids": [candidate_id],
                "preferred_value": {
                    "candidate_id": candidate_id,
                    "value": str(100 + index),
                    "numeric_value": str(100 + index),
                    "unit": "usd_millions",
                    "source_id": f"amat_bad_{index}",
                    "evidence_ref": f"bad_revenue_ref_{index}",
                    "source_family": "company_authored_unaudited_sec_filing",
                    "resolution_rule": "single_exact_authority_candidate",
                    "confidence": "high",
                },
            }
        )

    add_revenue_group(1, "Proceeds from sales and maturities of investments")
    add_revenue_group(2, "Realized gain on sales and dividends")
    add_revenue_group(3, "Costs of revenues")
    add_revenue_group(4, "Deferred system revenue")
    add_revenue_group(5, "Receivables sold under factoring agreements")
    add_revenue_group(6, "Proceeds from sales of LC")
    add_revenue_group(7, "")
    candidates[-1]["evidence_ref"] = "INTERACTIVE::LRCX::2026::deferred_revenue::total_value::qtd"
    groups[-1]["preferred_value"]["evidence_ref"] = "INTERACTIVE::LRCX::2026::deferred_revenue::total_value::qtd"

    selection = build_pre_memo_fact_selection(
        {
            "user_query": "分析 AMAT 产品收入、订单和半导体设备周期。",
            "reconciliation_ledger": {"candidates": candidates, "reconciliation_groups": groups},
        }
    )
    filtered = apply_pre_memo_fact_selection_to_judgment(
        {"memo_writer_allowed": True, "supported_claims": [], "unsupported_claims": []},
        selection,
    )
    deterministic = [
        row
        for row in filtered["supported_claims"]
        if row.get("agent_id") == "pre_memo_fact_selector"
    ]

    assert selection["summary"]["approved_fact_count"] == 0
    assert selection["summary"]["rejected_fact_count"] == 7
    assert selection["summary"]["by_rejected_fact_reason"] == {"revenue_label_not_memo_eligible": 7}
    assert deterministic == []
    assert filtered["claim_card_stats"]["pre_memo_deterministic_fact_claim_count"] == 0


def test_pre_memo_fact_selection_rejects_profitability_semantic_noise() -> None:
    candidates = []
    groups = []

    def add_group(index: int, metric: str, product: str, *, unit: str = "percent") -> None:
        candidate_id = f"profit_noise_candidate_{index}"
        candidates.append({"candidate_id": candidate_id, "evidence_ref": f"gross_margin_ref_{index}"})
        groups.append(
            {
                "group_id": f"profit_noise_group_{index}",
                "ticker": "DELL",
                "canonical_metric_id": metric,
                "product_or_segment": product,
                "period_key": "fiscal:2026:Q3:qtd",
                "resolution_status": "resolved_consensus",
                "candidate_ids": [candidate_id],
                "preferred_value": {
                    "candidate_id": candidate_id,
                    "value": "65.0" if unit == "percent" else "4.24",
                    "numeric_value": "65.0" if unit == "percent" else "4.24",
                    "unit": unit,
                    "source_id": f"source_{index}",
                    "evidence_ref": f"gross_margin_ref_{index}",
                    "source_family": "primary_sec_filing",
                    "resolution_rule": "same_value_highest_source_priority",
                    "confidence": "high",
                },
            }
        )

    add_group(1, "financial_metric:gross_margin", "Cash flow from operations")
    add_group(2, "financial_metric:gross_margin", "Earnings per share attributable to Dell Technologies diluted")
    add_group(3, "financial_metric:gross_profit", "Earnings per share attributable to Dell Technologies diluted", unit="usd_millions")

    selection = build_pre_memo_fact_selection(
        {
            "user_query": "分析 DELL AI 服务器收入、毛利率和现金流。",
            "reconciliation_ledger": {"candidates": candidates, "reconciliation_groups": groups},
        }
    )
    filtered = apply_pre_memo_fact_selection_to_judgment(
        {"memo_writer_allowed": True, "supported_claims": [], "unsupported_claims": []},
        selection,
    )
    deterministic = [
        row
        for row in filtered["supported_claims"]
        if row.get("agent_id") == "pre_memo_fact_selector"
    ]

    assert selection["summary"]["approved_fact_count"] == 0
    assert selection["summary"]["rejected_fact_count"] == 3
    assert selection["summary"]["by_rejected_fact_reason"] == {"profitability_label_not_memo_eligible": 3}
    assert deterministic == []


def test_pre_memo_fact_selection_prioritizes_query_relevant_product_lines() -> None:
    candidates = []
    groups = []

    def add_product(index: int, product: str) -> None:
        candidate_id = f"product_candidate_{index}"
        candidates.append({"candidate_id": candidate_id, "evidence_ref": f"product_ref_{index}_{product.lower().replace(' ', '_')}"})
        groups.append(
            {
                "group_id": f"product_group_{index}",
                "ticker": "DELL",
                "canonical_metric_id": "product_kpi:product_revenue",
                "product_or_segment": product,
                "period_key": "fiscal:2026:Q1:qtd",
                "resolution_status": "resolved_single_candidate",
                "candidate_ids": [candidate_id],
                "preferred_value": {
                    "candidate_id": candidate_id,
                    "value": str(1000 + index),
                    "numeric_value": str(1000 + index),
                    "unit": "usd_millions",
                    "source_id": f"sec_product_{index}",
                    "evidence_ref": f"product_ref_{index}_{product.lower().replace(' ', '_')}",
                    "source_family": "company_authored_unaudited_sec_filing",
                    "resolution_rule": "single_exact_authority_candidate",
                    "confidence": "high",
                },
            }
        )

    for index, product in enumerate(
        [
            "Consumer",
            "Commercial",
            "Storage",
            "Traditional servers and networking",
            "Total ISG net revenue",
            "AI-optimized servers",
        ],
        start=1,
    ):
        add_product(index, product)

    selection = build_pre_memo_fact_selection(
        {
            "user_query": "Evaluate Dell AI infrastructure demand, server revenue, and ISG exposure.",
            "reconciliation_ledger": {"candidates": candidates, "reconciliation_groups": groups},
        }
    )
    filtered = apply_pre_memo_fact_selection_to_judgment(
        {"memo_writer_allowed": True, "supported_claims": [], "unsupported_claims": []},
        selection,
    )
    product_claims = [
        row
        for row in filtered["supported_claims"]
        if row.get("agent_id") == "pre_memo_fact_selector"
        and row.get("analysis_dimension") == "product_and_production"
    ]
    priority_product_text = "\n".join(row.get("claim", "") for row in product_claims[:4])

    assert len(product_claims) >= 4
    assert "AI-optimized servers" in priority_product_text
    assert "Total ISG net revenue" in priority_product_text
    assert any(row.get("selection_relevance_score", 0) > 0 for row in product_claims)
