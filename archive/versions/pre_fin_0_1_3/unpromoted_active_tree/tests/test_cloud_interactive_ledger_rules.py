from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"


def _load_interactive_module():
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_under_test", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_8k_segment_table_inherits_revenue_group_and_keeps_product_revenue_rows() -> None:
    module = _load_interactive_module()
    record = {
        "object_id": "dell_8k_segment_table",
        "object_type": "table",
        "ticker": "DELL",
        "fiscal_year": 2026,
        "source_type": "8-K",
        "form_type": "8-K",
        "source_tier": "company_authored_unaudited_sec_filing",
        "period_type": "current_report",
        "title": "Operating Segments Results",
        "rows": [
            ["Three Months Ended"],
            ["May 1, 2026", "May 2, 2025", "Change"],
            ["Infrastructure Solutions Group (ISG):"],
            ["Net revenue:"],
            ["AI-optimized servers", "$", "16,132", "$", "1,882", "757%"],
        ],
        "cells": [
            {
                "row_index": 5,
                "row_label": "AI-optimized servers",
                "column_label": "May 1, 2026",
                "period": "2026",
                "raw_value": "$ 16,132",
                "value": 16132.0,
                "unit": "usd_millions",
                "cell_kind": "period_value",
            },
            {
                "row_index": 5,
                "row_label": "AI-optimized servers",
                "column_label": "Change",
                "raw_value": "757%",
                "value": 757.0,
                "unit": "percent",
                "cell_kind": "change_value",
            },
        ],
    }

    rows = module._ledger_rows_from_table("unit", record, {2026})
    product_rows = [row for row in rows if row["metric_family"] == "product_revenue"]

    assert product_rows
    assert product_rows[0]["metric_name"] == "Net revenue AI-optimized servers"
    assert product_rows[0]["period_role"] == "qtd"
    assert module._ledger_row_allowed(
        product_rows[0],
        {"task_type": "ai_industry_financial_trend", "focus_tickers": ["DELL"], "metric_families": ["product_revenue"]},
        None,
    )


def test_rpo_debt_noise_and_capex_percent_are_blocked_by_ledger_gate() -> None:
    module = _load_interactive_module()
    contract = {"metric_families": ["rpo", "capital_expenditure_proxy"]}
    bad_rpo = {
        "metric_family": "rpo",
        "metric_name": "Total face value of long-term debt",
        "row_label": "Total face value of long-term debt",
        "source_text": "Remaining performance obligation query hit a debt table: total face value of long-term debt.",
        "raw_value_text": "10,652",
        "value": 10652.0,
        "unit": "usd_millions",
        "ticker": "MSFT",
        "fiscal_year": 2026,
    }
    bad_rpo_assets = {
        "metric_family": "rpo",
        "metric_name": "Corporate and other assets",
        "row_label": "Corporate and other assets",
        "source_text": "Corporate and other assets are not backlog or RPO.",
        "raw_value_text": "14,463",
        "value": 14463.0,
        "unit": "usd_millions",
        "ticker": "GOOGL",
        "fiscal_year": 2026,
    }
    bad_rpo_expenses = {
        "metric_family": "rpo",
        "metric_name": "Other corporate expenses",
        "row_label": "Other corporate expenses",
        "source_text": "Remaining performance obligation query hit other corporate expenses.",
        "raw_value_text": "288",
        "value": 288.0,
        "unit": "usd_millions",
        "ticker": "DELL",
        "fiscal_year": 2026,
    }
    bad_rpo_corporate = {
        "metric_family": "rpo",
        "metric_name": "Corporate",
        "row_label": "Corporate",
        "source_text": "Remaining performance obligation query hit a corporate table row.",
        "raw_value_text": "299,692",
        "value": 299692.0,
        "unit": "usd_millions",
        "ticker": "AMZN",
        "fiscal_year": 2026,
    }
    bad_capex = {
        "metric_family": "capital_expenditure_proxy",
        "metric_name": "Capital expenditures change",
        "source_text": "Capital expenditures increased year over year.",
        "raw_value_text": "12%",
        "value": 12.0,
        "unit": "percent",
        "ticker": "MSFT",
        "fiscal_year": 2026,
    }

    assert module._ledger_row_allowed(bad_rpo, contract, None) is False
    assert module._ledger_row_allowed(bad_rpo_assets, contract, None) is False
    assert module._ledger_row_allowed(bad_rpo_expenses, contract, None) is False
    assert module._ledger_row_allowed(bad_rpo_corporate, contract, None) is False
    assert module._ledger_row_allowed(bad_capex, contract, None) is False


def test_gross_margin_gate_blocks_non_margin_percent_noise() -> None:
    module = _load_interactive_module()
    for name in ("Operating expenses", "Net income", "Gross margin Cash flow from operations", "Gross margin Earnings per share diluted"):
        row = {
            "metric_family": "gross_margin",
            "metric_name": name,
            "row_label": name,
            "raw_value_text": "16%",
            "value": 16.0,
            "unit": "percent",
            "ticker": "DELL",
            "fiscal_year": 2026,
            "source_text": "Gross margin table with operating expenses as a percent of revenue.",
        }

        assert module._ledger_row_allowed(row, {"metric_families": ["gross_margin"]}, None) is False


def test_product_revenue_gate_allows_specific_product_line_without_revenue_word() -> None:
    module = _load_interactive_module()
    row = {
        "metric_family": "product_revenue",
        "metric_name": "AI-optimized servers",
        "row_label": "AI-optimized servers",
        "raw_value_text": "$16,132",
        "value": 16132.0,
        "unit": "usd_millions",
        "ticker": "DELL",
        "fiscal_year": 2026,
        "form_type": "8-K",
        "source_tier": "company_authored_unaudited_sec_filing",
    }

    assert module._ledger_row_allowed(row, {"metric_families": ["product_revenue"]}, None)


def test_supplier_revenue_contract_expands_to_product_revenue() -> None:
    module = _load_interactive_module()

    expanded = module._expand_metric_family_aliases({"supplier_revenue"})

    assert "supplier_revenue" in expanded
    assert "product_revenue" in expanded
    assert "segment_revenue" in expanded
    assert "ai_optimized_servers" in expanded


def test_ai_ledger_cap_keeps_multiple_high_value_product_rows_after_ticker_cap() -> None:
    module = _load_interactive_module()
    contract = {
        "task_type": "ai_industry_financial_trend",
        "focus_tickers": ["DELL"],
        "metric_families": ["capex", "operating_income", "gross_margin", "revenue", "product_revenue"],
        "decomposed_tasks": [
            {"required_metric_families": ["capital_expenditure_proxy"]},
            {"required_metric_families": ["operating_income"]},
            {"required_metric_families": ["gross_margin", "revenue"]},
        ],
    }
    rows = [
        _ledger_row("DELL", "capital_expenditure_proxy", "Capex", -963.0),
        _ledger_row("DELL", "operating_income", "Non-GAAP operating income", 5855.0),
        _ledger_row("DELL", "gross_margin", "Non-GAAP product gross margin", 2.0, unit="percent"),
        _ledger_row("DELL", "revenue", "Revenue", 16.1, unit="usd_billions"),
        _ledger_row("DELL", "free_cash_flow_proxy", "Free cash flow", 1000.0),
        _ledger_row("DELL", "product_revenue", "Total ISG net revenue", 29009.0),
        _ledger_row("DELL", "product_revenue", "AI-optimized servers", 16132.0),
    ]

    capped = module._cap_ai_industry_ledger_rows(rows, contract, max_rows=8)

    product_names = {row["metric_name"] for row in capped if row["metric_family"] == "product_revenue"}
    assert {"Total ISG net revenue", "AI-optimized servers"} <= product_names


def _ledger_row(ticker: str, family: str, name: str, value: float, *, unit: str = "usd_millions") -> dict:
    slug = name.lower().replace(" ", "_").replace("-", "_")
    return {
        "metric_id": f"unit::{ticker}::2026::{family}::total_value::qtd::{slug}",
        "ticker": ticker,
        "metric_family": family,
        "metric_name": name,
        "row_label": name,
        "value": value,
        "unit": unit,
        "fiscal_year": 2026,
        "form_type": "8-K",
        "source_tier": "company_authored_unaudited_sec_filing",
    }
