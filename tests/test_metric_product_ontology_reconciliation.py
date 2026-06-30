from __future__ import annotations

import json
from pathlib import Path

from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state
from sec_agent.metric_product_ontology import (
    METRIC_PRODUCT_ONTOLOGY_SCHEMA_VERSION,
    build_metric_product_ontology_snapshot,
    resolve_metric_for_row,
)
from sec_agent.reconciliation_ledger import RECONCILIATION_LEDGER_SCHEMA_VERSION, build_reconciliation_ledger


def test_metric_product_ontology_maps_financial_and_product_metrics_without_proxy_authority() -> None:
    ontology = build_metric_product_ontology_snapshot(
        {
            "runtime_ledger_rows": [
                {"evidence_ref": "rev", "ticker": "MSFT", "metric_family": "revenue"},
                {"evidence_ref": "growth", "ticker": "MSFT", "metric_family": "revenue growth"},
            ],
            "product_evidence_rows": [
                {"evidence_ref": "deliveries", "ticker": "TSLA", "metric_family": "deliveries"},
            ],
        }
    )
    revenue = resolve_metric_for_row({"metric_family": "revenue"}, ontology)
    deliveries = resolve_metric_for_row({"metric_family": "deliveries"}, ontology)
    capex_proxy = resolve_metric_for_row({"metric_family": "capital_expenditure_proxy"}, ontology)
    ai_servers = resolve_metric_for_row({"metric_family": "ai_optimized_servers"}, ontology)
    gross_margin = resolve_metric_for_row({"metric_family": "gross_margin", "unit": "percent"}, ontology)
    gross_profit = resolve_metric_for_row({"metric_family": "gross_margin", "unit": "usd_millions"}, ontology)
    rejected = resolve_metric_for_row({"metric_family": "revenue growth"}, ontology)

    assert ontology["schema_version"] == METRIC_PRODUCT_ONTOLOGY_SCHEMA_VERSION
    assert ontology["validation"]["status"] == "pass"
    assert revenue["canonical_metric_id"] == "financial_metric:revenue"
    assert deliveries["canonical_metric_id"] == "product_kpi:deliveries"
    assert capex_proxy["canonical_metric_id"] == "financial_metric:capex"
    assert ai_servers["canonical_metric_id"] == "product_kpi:product_revenue"
    assert gross_margin["canonical_metric_id"] == "financial_metric:gross_margin"
    assert gross_profit["canonical_metric_id"] == "financial_metric:gross_profit"
    assert "public_source_context" in deliveries["cannot_infer_from"]
    assert "market_snapshot" not in deliveries["exact_authority_source_families"]
    assert rejected["match_status"] == "rejected_alias"
    assert ontology["summary"]["observed_mapped_count"] == 2
    assert ontology["summary"]["observed_rejected_alias_count"] == 1


def test_metric_product_ontology_consumes_minimal_kg_registry_boundaries() -> None:
    ontology = build_metric_product_ontology_snapshot(
        {
            "runtime_ledger_rows": [
                {"evidence_ref": "share", "ticker": "AAPL", "metric_family": "market share"},
            ],
        }
    )
    market_share = resolve_metric_for_row({"metric_family": "market share"}, ontology)

    assert ontology["registry_schema_version"] == "fin_agent_kg_minimal_p0_k1_k2_k3_registry_v0.1"
    assert ontology["registry_validation_status"] == "pass"
    assert ontology["product_spec_ontology"]["channel_offer_boundary"]["forbidden_claims"]
    assert "consumer_electronics" in ontology["industry_kpi_overrides"]
    assert market_share["canonical_metric_id"] == "product_kpi:market_share"
    metric = next(row for row in ontology["metrics"] if row["canonical_metric_id"] == "product_kpi:market_share")
    assert metric["period_rule"] == "commercial_tracker_required_for_exact_company_claim"
    assert metric["allowed_source_families"] == ["commercial_market_tracker"]
    assert metric["exact_authority_source_families"] == []
    assert metric["claim_boundary"] == "commercial_gap_metric_expose_gap_do_not_proxy"


def test_metric_product_ontology_accepts_full_kg_matrix_registry_path() -> None:
    ontology = build_metric_product_ontology_snapshot(
        {
            "kg_matrix_registry_path": "configs/kg_matrix_registry_v0_1.yaml",
            "runtime_ledger_rows": [
                {"evidence_ref": "contract_awards", "ticker": "LMT", "metric_family": "contract awards"},
            ],
        }
    )
    contract_awards = resolve_metric_for_row({"metric_family": "contract awards"}, ontology)
    product_spec = ontology["product_spec_ontology"]

    assert ontology["registry_schema_version"] == "fin_agent_kg_minimal_p0_k1_k2_k3_registry_v0.1"
    assert ontology["registry_validation_status"] == "pass"
    assert "ProductModel" not in ontology["product_spec_ontology"].get("node_types", [])
    assert "product_model_id" in product_spec["product_model_required_fields"]
    assert "comparable_dimensions" in product_spec["comparable_edge_required_fields"]
    assert "observed_at" in product_spec["channel_offer_required_fields"]
    assert "authority_fact" in product_spec["field_inquiry_boundary"]["forbidden_claims"]
    assert contract_awards["canonical_metric_id"] == "product_kpi:contract_awards"


def test_reconciliation_resolves_source_priority_and_blocks_unit_and_taxonomy_conflicts() -> None:
    ontology = build_metric_product_ontology_snapshot({})
    ledger = build_reconciliation_ledger(
        {
            "run_id": "unit-d6",
            "metric_product_ontology_snapshot": ontology,
            "runtime_ledger_rows": [
                {
                    "evidence_ref": "rev_sec",
                    "source_id": "sec-rev",
                    "ticker": "MSFT",
                    "metric_family": "revenue",
                    "value": "100",
                    "unit": "USD",
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "fiscal_period_end": "2025-06-30",
                    "source_family": "primary_sec_filing",
                },
                {
                    "evidence_ref": "rev_ir",
                    "source_id": "ir-rev",
                    "ticker": "MSFT",
                    "metric_family": "revenue",
                    "value": "98",
                    "unit": "USD",
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "fiscal_period_end": "2025-06-30",
                    "source_family": "company_authored_unaudited_sec_filing",
                },
                {
                    "evidence_ref": "capex_usd",
                    "source_id": "sec-capex-usd",
                    "ticker": "MSFT",
                    "metric_family": "capex",
                    "value": "10",
                    "unit": "usd_billions",
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "source_family": "primary_sec_filing",
                },
                {
                    "evidence_ref": "capex_shares",
                    "source_id": "sec-capex-shares",
                    "ticker": "MSFT",
                    "metric_family": "capex",
                    "value": "10",
                    "unit": "shares",
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "source_family": "primary_sec_filing",
                },
                {
                    "evidence_ref": "market_share",
                    "source_id": "sec-share",
                    "ticker": "MSFT",
                    "metric_family": "unmapped operating metric",
                    "value": "12",
                    "unit": "%",
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "source_family": "primary_sec_filing",
                },
                {
                    "evidence_ref": "public_context_value",
                    "source_id": "public-context",
                    "ticker": "MSFT",
                    "metric_family": "revenue",
                    "value": "101",
                    "unit": "USD",
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "source_family": "public_source_context",
                },
            ],
        }
    )
    groups = {row["canonical_metric_id"]: row for row in ledger["reconciliation_groups"]}
    revenue = groups["financial_metric:revenue"]
    capex = groups["financial_metric:capex"]

    assert ledger["schema_version"] == RECONCILIATION_LEDGER_SCHEMA_VERSION
    assert ledger["validation"]["status"] == "pass"
    assert revenue["resolution_status"] == "resolved_by_rule"
    assert revenue["preferred_value"]["source_family"] == "primary_sec_filing"
    assert revenue["preferred_value"]["resolution_rule"] == "source_priority_highest_authority_wins"
    assert capex["resolution_status"] == "resolved_single_candidate"
    assert capex["preferred_value"]["unit_family"] == "currency"
    assert {row["evidence_ref"]: row["candidate_status"] for row in ledger["excluded_candidates"]}["capex_shares"] == "excluded_metric_unit_mismatch"
    assert any("taxonomy_conflict" in row["conflict_types"] for row in ledger["reconciliation_groups"])
    assert ledger["summary"]["unresolved_conflict_count"] == 1
    assert ledger["excluded_candidate_count"] == 2
    assert ledger["conflict_gap_count"] == 1


def test_reconciliation_excludes_large_bare_usd_currency_scale_before_approval() -> None:
    ontology = build_metric_product_ontology_snapshot({})
    ledger = build_reconciliation_ledger(
        {
            "run_id": "unit-ambiguous-usd-scale",
            "metric_product_ontology_snapshot": ontology,
            "runtime_ledger_rows": [
                {
                    "evidence_ref": "amzn_capex_ambiguous_unit",
                    "source_id": "amzn-capex-8k-table",
                    "ticker": "AMZN",
                    "metric_family": "capex",
                    "metric_name": "Property and equipment additions",
                    "value": "77658.0",
                    "unit": "usd",
                    "fiscal_year": 2024,
                    "fiscal_period": "FY",
                    "source_family": "company_authored_unaudited_sec_filing",
                }
            ],
        }
    )

    assert not ledger["reconciliation_groups"]
    assert ledger["excluded_candidate_count"] == 1
    assert ledger["excluded_candidates"][0]["candidate_status"] == "excluded_ambiguous_currency_scale"


def test_reconciliation_splits_period_role_and_segment_labels_for_sec_table_rows() -> None:
    ontology = build_metric_product_ontology_snapshot({})
    ledger = build_reconciliation_ledger(
        {
            "run_id": "unit-period-role",
            "metric_product_ontology_snapshot": ontology,
            "runtime_ledger_rows": [
                {
                    "evidence_ref": "aapl_total_ytd",
                    "source_id": "sec-aapl",
                    "ticker": "AAPL",
                    "metric_family": "revenue",
                    "metric_name": "Total net sales",
                    "value": "254940",
                    "unit": "usd_millions",
                    "fiscal_year": 2026,
                    "fiscal_period": "Q2",
                    "period_role": "ytd",
                    "source_family": "primary_sec_filing",
                },
                {
                    "evidence_ref": "aapl_iphone_qtd",
                    "source_id": "sec-aapl",
                    "ticker": "AAPL",
                    "metric_family": "revenue",
                    "metric_name": "iPhone",
                    "value": "95359",
                    "unit": "usd_millions",
                    "fiscal_year": 2026,
                    "fiscal_period": "Q2",
                    "period_role": "qtd",
                    "source_family": "primary_sec_filing",
                },
                {
                    "evidence_ref": "aapl_services_qtd",
                    "source_id": "sec-aapl",
                    "ticker": "AAPL",
                    "metric_family": "revenue",
                    "metric_name": "Services",
                    "value": "26645",
                    "unit": "usd_millions",
                    "fiscal_year": 2026,
                    "fiscal_period": "Q2",
                    "period_role": "qtd",
                    "source_family": "primary_sec_filing",
                },
            ],
        }
    )
    by_key = {
        (
            row["canonical_metric_id"],
            row["product_or_segment"],
            row["period_key"],
        ): row
        for row in ledger["reconciliation_groups"]
    }

    assert ledger["validation"]["status"] == "pass"
    assert by_key[("financial_metric:revenue", "", "fiscal:2026:Q2:ytd")]["resolution_status"] == "resolved_single_candidate"
    assert by_key[("financial_metric:revenue", "iPhone", "fiscal:2026:Q2:qtd")]["resolution_status"] == "resolved_single_candidate"
    assert by_key[("financial_metric:revenue", "Services", "fiscal:2026:Q2:qtd")]["resolution_status"] == "resolved_single_candidate"


def test_reconciliation_excludes_metric_unit_and_rpo_semantic_mismatches() -> None:
    ontology = build_metric_product_ontology_snapshot({})
    ledger = build_reconciliation_ledger(
        {
            "run_id": "unit-metric-unit-gates",
            "metric_product_ontology_snapshot": ontology,
            "runtime_ledger_rows": [
                {
                    "evidence_ref": "googl_revenue_growth_not_revenue",
                    "source_id": "googl-8k",
                    "ticker": "GOOGL",
                    "metric_family": "revenue",
                    "metric_name": "revenue",
                    "value": "19",
                    "unit": "percent",
                    "fiscal_year": 2026,
                    "fiscal_period": "Q1",
                    "period_role": "qtd",
                    "source_family": "company_authored_unaudited_sec_filing",
                },
                {
                    "evidence_ref": "msft_rpo_debt_noise",
                    "source_id": "msft-10q",
                    "ticker": "MSFT",
                    "metric_family": "rpo",
                    "metric_name": "Total face value of long-term debt",
                    "row_label": "Total face value of long-term debt",
                    "source_text": "Remaining performance obligation query hit a debt table: total face value of long-term debt.",
                    "value": "10652",
                    "unit": "usd_millions",
                    "fiscal_year": 2026,
                    "fiscal_period": "Q3",
                    "period_role": "qtd",
                    "source_family": "primary_sec_filing",
                },
                {
                    "evidence_ref": "msft_rpo_valid",
                    "source_id": "msft-10q-rpo",
                    "ticker": "MSFT",
                    "metric_family": "rpo",
                    "metric_name": "Remaining performance obligations",
                    "row_label": "Remaining performance obligations",
                    "source_text": "Remaining performance obligations expected to be recognized as revenue.",
                    "value": "305000",
                    "unit": "usd_millions",
                    "fiscal_year": 2026,
                    "fiscal_period": "Q3",
                    "period_role": "instant",
                    "source_family": "primary_sec_filing",
                },
                {
                    "evidence_ref": "dell_rpo_corporate_expense_noise",
                    "source_id": "dell-8k-rpo-noise",
                    "ticker": "DELL",
                    "metric_family": "rpo",
                    "metric_name": "Other corporate expenses",
                    "row_label": "Other corporate expenses",
                    "source_text": "Remaining performance obligation query hit other corporate expenses.",
                    "value": "288",
                    "unit": "usd_millions",
                    "fiscal_year": 2026,
                    "fiscal_period": "Q1",
                    "period_role": "qtd",
                    "source_family": "company_authored_unaudited_sec_filing",
                },
                {
                    "evidence_ref": "amzn_rpo_corporate_noise",
                    "source_id": "amzn-10q-rpo-noise",
                    "ticker": "AMZN",
                    "metric_family": "rpo",
                    "metric_name": "Corporate",
                    "row_label": "Corporate",
                    "source_text": "Remaining performance obligation query hit a corporate table row.",
                    "value": "299692",
                    "unit": "usd_millions",
                    "fiscal_year": 2026,
                    "fiscal_period": "Q1",
                    "period_role": "qtd",
                    "source_family": "primary_sec_filing",
                },
            ],
        }
    )
    excluded = {row["evidence_ref"]: row["candidate_status"] for row in ledger["excluded_candidates"]}
    groups = {row["canonical_metric_id"]: row for row in ledger["reconciliation_groups"]}

    assert excluded["googl_revenue_growth_not_revenue"] == "excluded_metric_unit_mismatch"
    assert excluded["msft_rpo_debt_noise"] == "excluded_metric_semantic_mismatch"
    assert excluded["dell_rpo_corporate_expense_noise"] == "excluded_metric_semantic_mismatch"
    assert excluded["amzn_rpo_corporate_noise"] == "excluded_metric_semantic_mismatch"
    assert groups["product_kpi:backlog"]["resolution_status"] == "resolved_single_candidate"


def test_reconciliation_product_revenue_strips_metric_prefix_from_product_label() -> None:
    ontology = build_metric_product_ontology_snapshot({})
    ledger = build_reconciliation_ledger(
        {
            "run_id": "unit-product-revenue-label",
            "metric_product_ontology_snapshot": ontology,
            "runtime_ledger_rows": [
                {
                    "evidence_ref": "dell_ai_server_revenue",
                    "source_id": "dell-8k",
                    "ticker": "DELL",
                    "metric_family": "product_revenue",
                    "metric_name": "Net revenue AI-optimized servers",
                    "value": "16132",
                    "unit": "usd_millions",
                    "fiscal_year": 2026,
                    "fiscal_period": "Q1",
                    "period_role": "qtd",
                    "source_family": "company_authored_unaudited_sec_filing",
                },
            ],
        }
    )
    group = ledger["reconciliation_groups"][0]

    assert group["canonical_metric_id"] == "product_kpi:product_revenue"
    assert group["product_or_segment"] == "AI-optimized servers"
    assert group["period_key"] == "fiscal:2026:Q1:qtd"
    assert group["resolution_status"] == "resolved_single_candidate"


def test_graph_persists_metric_product_ontology_and_reconciliation_ledger(tmp_path: Path) -> None:
    def injected_execute(state: dict) -> dict:
        return {
            "tool_observations": [],
            "tool_call_ledger": state.get("tool_call_ledger") or {},
            "runtime_ledger_rows": [
                {
                    "source_id": "sec-msft-revenue",
                    "evidence_ref": "msft-revenue-usd",
                    "source_family": "primary_sec_filing",
                    "ticker": "MSFT",
                    "metric_family": "revenue",
                    "value": "100",
                    "unit": "USD",
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "fiscal_period_end": "2025-06-30",
                    "source_url": "https://www.sec.gov/Archives/edgar/data/789019/msft-2025.htm",
                },
                {
                    "source_id": "sec-msft-revenue-bad-unit",
                    "evidence_ref": "msft-revenue-shares",
                    "source_family": "primary_sec_filing",
                    "ticker": "MSFT",
                    "metric_family": "revenue",
                    "value": "100",
                    "unit": "shares",
                    "fiscal_year": 2025,
                    "fiscal_period": "FY",
                    "fiscal_period_end": "2025-06-30",
                    "source_url": "https://www.sec.gov/Archives/edgar/data/789019/msft-2025.htm",
                },
            ],
        }

    graph = build_multi_agent_orchestration_graph(execute_evidence_operators=injected_execute)
    initial = make_multi_agent_smoke_state(
        user_query="写一段 MSFT revenue 和产品交付表现 memo。",
        output_dir=tmp_path,
        query_contract={
            "companies": ["MSFT"],
            "focus_tickers": ["MSFT"],
            "search_scope_tickers": ["MSFT"],
            "source_tiers": ["primary_sec_filing", "company_product_evidence_graph"],
            "intent": "standard_memo",
        },
        focus_tickers=["MSFT"],
        search_scope_tickers=["MSFT"],
    )
    initial["product_evidence_rows"] = [
        {
            "source_id": "product-msft-deliveries",
            "evidence_ref": "msft-product-deliveries",
            "source_family": "company_product_evidence_graph",
            "ticker": "MSFT",
            "metric_family": "deliveries",
            "product_or_segment": "Cloud",
            "promotion_status": "runtime_fact_allowed",
            "value": "42",
            "unit": "units",
            "fiscal_year": 2025,
            "fiscal_period": "FY",
        }
    ]  # type: ignore[literal-required]

    result = graph.invoke(initial, config={"configurable": {"thread_id": "unit-d6-d7-artifacts"}})
    summary = json.loads((tmp_path / "multi_agent_summary.json").read_text(encoding="utf-8"))
    ontology_artifact = json.loads((tmp_path / "metric_product_ontology_snapshot.json").read_text(encoding="utf-8"))
    reconciliation_artifact = json.loads((tmp_path / "reconciliation_ledger.json").read_text(encoding="utf-8"))
    checkpoint_artifact = json.loads((tmp_path / "langgraph_node_checkpoints.json").read_text(encoding="utf-8"))
    recoverable_summary = checkpoint_artifact["recoverable_state_summary"]

    assert result["metric_product_ontology_snapshot"]["schema_version"] == METRIC_PRODUCT_ONTOLOGY_SCHEMA_VERSION
    assert result["reconciliation_ledger"]["schema_version"] == RECONCILIATION_LEDGER_SCHEMA_VERSION
    assert result["artifact_refs"]["metric_product_ontology_snapshot"].endswith("metric_product_ontology_snapshot.json")
    assert result["artifact_refs"]["reconciliation_ledger"].endswith("reconciliation_ledger.json")
    assert ontology_artifact["validation"]["status"] == "pass"
    assert reconciliation_artifact["validation"]["status"] == "pass"
    assert reconciliation_artifact["summary"]["unit_conflict_count"] == 0
    assert reconciliation_artifact["excluded_candidate_count"] == 1
    assert reconciliation_artifact["conflict_gap_count"] == 0
    assert summary["metric_product_ontology_snapshot"]["schema_version"] == METRIC_PRODUCT_ONTOLOGY_SCHEMA_VERSION
    assert summary["reconciliation_ledger"]["schema_version"] == RECONCILIATION_LEDGER_SCHEMA_VERSION
    assert summary["reconciliation_ledger"]["unresolved_conflict_count"] == 0
    assert recoverable_summary["metric_product_ontology_metric_count"] == ontology_artifact["metric_count"]
    assert recoverable_summary["reconciliation_conflict_gap_count"] == reconciliation_artifact["conflict_gap_count"]
