from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from evidence.schema import EvidenceObject  # noqa: E402
from evidence.structured_extractor import extract_structured_objects  # noqa: E402
from sec_agent.ledger_store import query_ledger_facts, write_ledger_store  # noqa: E402


def _load_interactive_module():
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_ledger_store_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_ledger_store_rehydrates_case_scoped_metric_ids(tmp_path: Path) -> None:
    store_path = tmp_path / "ledger.duckdb"
    write_ledger_store([_fact_row(case_id="store_case")], store_path)

    rows = query_ledger_facts(
        store_path,
        case_id="case_live",
        tickers=["NVDA"],
        years=[2026],
        filing_types=["10-Q"],
        metric_families=["revenue"],
    )

    assert len(rows) == 1
    assert rows[0]["case_id"] == "case_live"
    assert rows[0]["metric_id"].startswith("case_live::NVDA::2026::revenue::total_value")
    assert rows[0]["value"] == 12000.0


def test_runtime_ledger_uses_duckdb_store_without_object_records(tmp_path: Path) -> None:
    interactive = _load_interactive_module()
    store_path = tmp_path / "ledger.duckdb"
    write_ledger_store([_fact_row(case_id="store_case")], store_path)
    case = {
        "case_id": "case_live",
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "query_contract": {
            "focus_tickers": ["NVDA"],
            "ledger_rules": {
                "allowed_metric_families": ["revenue"],
                "prefer_focus_tickers": True,
            },
        },
    }
    context_rows = [
        {
            "source_kind": "structured_object",
            "object_id": "obj_nvda_revenue",
            "ticker": "NVDA",
            "fiscal_year": 2026,
            "form_type": "10-Q",
        }
    ]
    args = Namespace(ledger_store_path=str(store_path), object_bm25_index_dir="missing", ledger_max_rows=10)

    rows = interactive._build_runtime_ledger(case, context_rows, args)

    assert len(rows) == 1
    assert rows[0]["metric_id"].startswith("case_live::")
    assert rows[0]["object_id"] == "obj_nvda_revenue"


def test_runtime_ledger_extracts_metrics_from_context_evidence_rows(tmp_path: Path) -> None:
    interactive = _load_interactive_module()
    case = {
        "case_id": "context_case",
        "years": [2026],
        "filing_types": ["8-K"],
        "source_tiers": ["company_authored_unaudited_sec_filing"],
        "query_contract": {
            "focus_tickers": ["DELL"],
            "search_scope_tickers": ["DELL"],
            "years": [2026],
            "filing_types": ["8-K"],
            "source_tiers": ["company_authored_unaudited_sec_filing"],
            "metric_families": ["revenue", "gross_margin"],
        },
    }
    context_rows = [
        {
            "source_kind": "evidence_object",
            "evidence_id": "8K_EARNINGS::DELL::Q1FY27::BLOCK_0001",
            "ticker": "DELL",
            "fiscal_year": 2026,
            "source_type": "8-K",
            "form_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "period_end": "2026-05-01",
            "period_type": "current_report",
            "section": "Exhibit 99.1 Earnings Release",
            "text": (
                "DELL TECHNOLOGIES INC. Condensed Consolidated Statements "
                "(in millions, except percentages; unaudited)\n"
                "[TABLE_START id=1 rows=3]\n"
                "Three Months Ended | May 1, 2026 | May 2, 2025\n"
                "Net revenue | $31,000 | $22,000\n"
                "Gross margin | 57% | 52%\n"
                "[TABLE_END]"
            ),
        }
    ]
    args = Namespace(ledger_store_path="", object_bm25_index_dir=str(tmp_path / "missing"), ledger_max_rows=10)

    rows = interactive._build_runtime_ledger(case, context_rows, args)

    assert rows
    assert {row["ticker"] for row in rows} == {"DELL"}
    assert {"revenue", "gross_margin"} & {row["metric_family"] for row in rows}
    assert all(row["ledger_extraction_source"] == "context_evidence_object_structured_extractor" for row in rows)


def test_runtime_ledger_keeps_banking_rows_when_context_table_has_income_tax(tmp_path: Path) -> None:
    interactive = _load_interactive_module()
    case = {
        "case_id": "banking_context_case",
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "query_contract": {
            "focus_tickers": ["JPM"],
            "search_scope_tickers": ["JPM"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "metric_families": [
                "net_interest_income",
                "provision_for_credit_losses",
                "capital_ratio",
            ],
            "decomposed_tasks": [
                {
                    "task_id": "bank_metrics",
                    "required_tickers": ["JPM"],
                    "required_metric_families": [
                        "net_interest_income",
                        "provision_for_credit_losses",
                        "capital_ratio",
                    ],
                }
            ],
        },
    }
    context_rows = [
        {
            "source_kind": "evidence_object",
            "evidence_id": "JPM_2026_10Q_BANKING_TABLE",
            "ticker": "JPM",
            "fiscal_year": 2026,
            "source_type": "10-Q",
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "period_end": "2026-03-31",
            "period_type": "quarterly",
            "section": "Item 2. Management's Discussion and Analysis",
            "text": (
                "Selected income statement data\n"
                "[TABLE_START id=1 rows=5]\n"
                "Three months ended March 31 | 2026 | 2025 | Change\n"
                "Net interest income | 25,366 | 23,273 | 9\n"
                "Provision for credit losses | 2,507 | 3,305 | (24)\n"
                "Income tax expense | 3,985 | 3,765 | 6\n"
                "Common equity Tier 1 (CET1) capital ratio - Standardized | 14.3 | 15.4\n"
                "[TABLE_END]"
            ),
        }
    ]
    args = Namespace(ledger_store_path="", object_bm25_index_dir=str(tmp_path / "missing"), ledger_max_rows=10)

    rows = interactive._build_runtime_ledger(case, context_rows, args)

    by_family = {row["metric_family"]: row for row in rows}
    assert by_family["net_interest_income"]["value"] == 25366.0
    assert by_family["provision_for_credit_losses"]["value"] == 2507.0
    assert by_family["capital_ratio"]["value"] == 14.3
    assert by_family["capital_ratio"]["raw_value_text"] != "1"
    assert all(row["source_evidence_id"] == "JPM_2026_10Q_BANKING_TABLE" for row in by_family.values())


def test_runtime_ledger_expands_sector_depth_banking_scope_from_evidence_requirements(tmp_path: Path) -> None:
    interactive = _load_interactive_module()
    case = {
        "case_id": "banking_sector_depth_case",
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "query_contract": {
            "focus_tickers": ["JPM", "C", "GS"],
            "search_scope_tickers": ["JPM", "C", "GS"],
            "years": [2026],
            "filing_types": ["10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "metric_families": ["net_interest_income", "provision_for_credit_losses"],
            "decomposed_tasks": [
                {
                    "task_id": "representative_bank_metrics",
                    "required_tickers": ["JPM"],
                    "required_metric_families": ["net_interest_income", "provision_for_credit_losses"],
                }
            ],
            "evidence_requirements": [
                {
                    "requirement_id": "sector_depth_banking",
                    "tickers": ["JPM", "C", "GS"],
                    "metric_families": ["net_interest_income", "provision_for_credit_losses"],
                }
            ],
            "ledger_rules": {
                "allowed_metric_families": ["net_interest_income", "provision_for_credit_losses"],
                "banking_metric_tickers": ["JPM"],
                "drop_human_capital_tables": True,
                "prefer_focus_tickers": True,
            },
            "project_inventory": {
                "categories": [
                    {"category": "banking/financial services", "tickers": ["JPM", "C"]},
                    {"category": "capital markets/investment bank", "tickers": ["GS"]},
                ]
            },
        },
    }
    context_rows = [
        _banking_context_row("JPM", "JPM_2026_BANKING", "Net interest income | 25,366 | 23,273\nProvision for credit losses | 2,507 | 3,305"),
        _banking_context_row("C", "C_2026_BANKING", "Net interest income | 15,741 | 14,012\nProvision for credit losses | 2,805 | 2,723"),
        _banking_context_row("GS", "GS_2026_BANKING", "Net interest income | 2,880 | 2,451\nProvision for credit losses | 287 | 203"),
    ]
    args = Namespace(ledger_store_path="", object_bm25_index_dir=str(tmp_path / "missing"), ledger_max_rows=12)

    rows = interactive._build_runtime_ledger(case, context_rows, args)

    by_ticker_family = {(row["ticker"], row["metric_family"]): row for row in rows}
    assert by_ticker_family[("C", "net_interest_income")]["value"] == 15741.0
    assert by_ticker_family[("GS", "provision_for_credit_losses")]["value"] == 287.0
    assert {row["ticker"] for row in rows} >= {"JPM", "C", "GS"}


def test_structured_extractor_keeps_mixed_bank_table_default_unit_millions() -> None:
    evidence = EvidenceObject(
        evidence_id="C_2026_MIXED_UNIT_TABLE",
        source_type="10-Q",
        source_tier="primary_sec_filing",
        ticker="C",
        fiscal_year=2026,
        period_end="2026-03-31",
        period_type="quarterly",
        duration_months=3,
        fiscal_period="Q1",
        section="Item 1. Financial Statements",
        evidence_type="filing_text",
        text=(
            "[TABLE_START id=106 rows=6]\n"
            "Three Months Ended March 31,\n"
            "In millions of dollars, except end-of-period assets, average loans and average deposits in billions | Total Citi\n"
            "2026 | 2025\n"
            "Net interest income | $ | 15,741 | $ | 14,012\n"
            "Average loans | 755 | 691\n"
            "Average deposits | 1,446 | 1,305\n"
            "[TABLE_END]"
        ),
    )

    metrics = extract_structured_objects(evidence).metrics
    by_label = {metric.row_label: metric for metric in metrics if metric.period == "2026"}

    assert by_label["Net interest income"].unit == "usd_millions"
    assert by_label["Average loans"].unit == "usd_billions"
    assert by_label["Average deposits"].unit == "usd_billions"


def _banking_context_row(ticker: str, evidence_id: str, body: str) -> dict:
    return {
        "source_kind": "evidence_object",
        "evidence_id": evidence_id,
        "ticker": ticker,
        "fiscal_year": 2026,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_end": "2026-03-31",
        "period_type": "quarterly",
        "section": "Item 2. Management's Discussion and Analysis",
        "text": (
            "Selected banking metrics\n"
            "[TABLE_START id=1 rows=3]\n"
            "Three months ended March 31 | 2026 | 2025\n"
            f"{body}\n"
            "[TABLE_END]"
        ),
    }


def _fact_row(*, case_id: str) -> dict:
    return {
        "metric_id": f"{case_id}::NVDA::2026::revenue::total_value::qtd",
        "case_id": case_id,
        "ticker": "NVDA",
        "fiscal_year": 2026,
        "source_fiscal_year": 2026,
        "period": "2026",
        "period_role": "qtd",
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "metric_family": "revenue",
        "metric_role": "total_value",
        "metric_name": "Revenue",
        "raw_value_text": "$12,000",
        "display_value_zh": "12,000（百万美元）",
        "value": 12000.0,
        "unit": "usd_millions",
        "object_id": "obj_nvda_revenue",
        "source_evidence_id": "NVDA_2026_10Q_ITEM2",
        "section": "Item 2",
        "source_text": "Revenue was $12,000 million.",
    }
