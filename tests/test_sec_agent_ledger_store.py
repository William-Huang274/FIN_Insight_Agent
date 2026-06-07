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
from sec_agent.ledger_store import (  # noqa: E402
    LedgerStoreBulkCsvWriter,
    LedgerStoreWriter,
    query_ledger_facts,
    read_ledger_store_metadata,
    write_ledger_store,
)


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


def test_ledger_store_expands_common_metric_family_aliases(tmp_path: Path) -> None:
    store_path = tmp_path / "ledger.duckdb"
    write_ledger_store(
        [
            _fact_row(
                case_id="store_case",
                metric_family="capital_expenditure_proxy",
                metric_id="store_case::NVDA::2026::capital_expenditure_proxy::total_value::qtd",
            )
        ],
        store_path,
    )

    rows = query_ledger_facts(
        store_path,
        case_id="case_live",
        tickers=["NVDA"],
        years=[2026],
        filing_types=["10-Q"],
        metric_families=["capex"],
    )

    assert len(rows) == 1
    assert rows[0]["metric_family"] == "capital_expenditure_proxy"


def test_ledger_store_margin_alias_matches_gross_margin_rows(tmp_path: Path) -> None:
    store_path = tmp_path / "ledger.duckdb"
    write_ledger_store(
        [
            _fact_row(
                case_id="store_case",
                ticker="AMZN",
                metric_family="gross_margin",
                metric_id="store_case::AMZN::2026::gross_margin::percentage_rate::qtd",
                metric_name="Gross margin",
                raw_value_text="42.1%",
                display_value_zh="42.1%",
                value=42.1,
                unit="percent",
            )
        ],
        store_path,
    )

    rows = query_ledger_facts(
        store_path,
        case_id="case_live",
        tickers=["AMZN"],
        years=[2026],
        filing_types=["10-Q"],
        metric_families=["margin"],
    )

    assert len(rows) == 1
    assert rows[0]["metric_family"] == "gross_margin"


def test_ledger_store_margin_alias_includes_income_statement_base_rows(tmp_path: Path) -> None:
    store_path = tmp_path / "ledger.duckdb"
    write_ledger_store(
        [
            _fact_row(
                case_id="store_case",
                ticker="AMZN",
                metric_family="revenue",
                metric_id="store_case::AMZN::2026::revenue::total_value::qtd",
                metric_name="Net sales",
            ),
            _fact_row(
                case_id="store_case",
                ticker="AMZN",
                metric_family="operating_income",
                metric_id="store_case::AMZN::2026::operating_income::total_value::qtd",
                metric_name="Operating income",
            ),
        ],
        store_path,
    )

    rows = query_ledger_facts(
        store_path,
        case_id="case_live",
        tickers=["AMZN"],
        years=[2026],
        filing_types=["10-Q"],
        metric_families=["margin"],
    )

    assert {row["metric_family"] for row in rows} == {"operating_income", "revenue"}


def test_ledger_store_records_segmented_transaction_commit_rows(tmp_path: Path) -> None:
    store_path = tmp_path / "ledger.duckdb"
    with LedgerStoreWriter(store_path, transaction_commit_rows=2) as writer:
        writer.append_rows([_fact_row(case_id="store_case", ticker="NVDA")])
        writer.append_rows([_fact_row(case_id="store_case", ticker="MSFT", metric_id="store_case::MSFT::2026::revenue::total_value::qtd")])
        writer.append_rows([_fact_row(case_id="store_case", ticker="AMZN", metric_id="store_case::AMZN::2026::revenue::total_value::qtd")])
        writer.finalize(metadata={"purpose": "segmented_commit_smoke"})

    metadata = read_ledger_store_metadata(store_path)
    rows = query_ledger_facts(store_path, case_id="live_case", years=[2026], metric_families=["revenue"])

    assert metadata["row_count"] == 3
    assert metadata["metadata"]["transaction_commit_rows"] == 2
    assert {row["ticker"] for row in rows} == {"AMZN", "MSFT", "NVDA"}


def test_bulk_csv_ledger_writer_rehydrates_queryable_store(tmp_path: Path) -> None:
    store_path = tmp_path / "ledger_csv.duckdb"
    staging_path = tmp_path / "ledger_rows.tsv"
    with LedgerStoreBulkCsvWriter(store_path, staging_path=staging_path, duckdb_threads=1) as writer:
        writer.append_rows([
            _fact_row(case_id="store_case", table_object_id=None),
            _fact_row(
                case_id="store_case",
                ticker="MSFT",
                metric_id="store_case::MSFT::2026::capital_expenditure_proxy::additions",
                metric_family="capital_expenditure_proxy",
                metric_name="Additions to property and equipment",
                row_label="Additions to property and equipment",
                value=-44000.0,
                unit="usd_millions",
                period_role="annual",
                cell_kind="period_value",
                table_object_id="table_cash_flow",
            ),
        ])
        summary = writer.finalize(metadata={"purpose": "csv_copy_smoke"})

    rows = query_ledger_facts(store_path, case_id="live_case", tickers=["MSFT"], years=[2026], metric_families=["capex"])
    metadata = read_ledger_store_metadata(store_path)

    assert summary["row_count"] == 2
    assert rows[0]["row_label"] == "Additions to property and equipment"
    assert metadata["metadata"]["write_mode"] == "csv_copy"
    assert not staging_path.exists()


def test_ledger_store_prioritizes_capex_table_purchase_rows(tmp_path: Path) -> None:
    store_path = tmp_path / "ledger.duckdb"
    write_ledger_store(
        [
            _fact_row(
                case_id="store_case",
                ticker="MSFT",
                metric_id="store_case::MSFT::2026::capital_expenditure_proxy::narrative",
                metric_family="capital_expenditure_proxy",
                metric_name="Cash used in investing decreased",
                value=24.4,
                unit="usd_billions",
                period_role="annual",
                table_object_id=None,
            ),
            _fact_row(
                case_id="store_case",
                ticker="MSFT",
                metric_id="store_case::MSFT::2026::capital_expenditure_proxy::depreciation",
                metric_family="capital_expenditure_proxy",
                metric_name="Accumulated depreciation",
                row_label="Accumulated depreciation",
                value=-76000.0,
                unit="usd_millions",
                period_role="annual",
                cell_kind="period_value",
                table_object_id="table_ppe",
            ),
            _fact_row(
                case_id="store_case",
                ticker="MSFT",
                metric_id="store_case::MSFT::2026::capital_expenditure_proxy::additions",
                metric_family="capital_expenditure_proxy",
                metric_name="Additions to property and equipment",
                row_label="Additions to property and equipment",
                value=-44000.0,
                unit="usd_millions",
                period_role="annual",
                cell_kind="period_value",
                table_object_id="table_cash_flow",
            ),
        ],
        store_path,
    )

    rows = query_ledger_facts(store_path, case_id="live_case", tickers=["MSFT"], years=[2026], metric_families=["capex"])

    assert rows[0]["row_label"] == "Additions to property and equipment"


def test_ledger_store_prioritizes_revenue_rows_over_tax_noise(tmp_path: Path) -> None:
    store_path = tmp_path / "ledger.duckdb"
    write_ledger_store(
        [
            _fact_row(
                case_id="store_case",
                ticker="NVDA",
                metric_id="store_case::NVDA::2026::revenue::tax_noise",
                metric_family="revenue",
                metric_name="Income tax expense",
                row_label="Income tax expense",
                value=8.6,
                unit="usd_millions",
                period_role="annual",
                cell_kind="period_value",
                table_object_id="table_income_statement",
            ),
            _fact_row(
                case_id="store_case",
                ticker="NVDA",
                metric_id="store_case::NVDA::2026::revenue::net_revenue",
                metric_family="revenue",
                metric_name="Net revenue",
                row_label="Net revenue",
                value=130000.0,
                unit="usd_millions",
                period_role="annual",
                cell_kind="period_value",
                table_object_id="table_revenue",
            ),
        ],
        store_path,
    )

    rows = query_ledger_facts(store_path, case_id="live_case", tickers=["NVDA"], years=[2026], metric_families=["revenue"])

    assert rows[0]["row_label"] == "Net revenue"


def test_mcp_ledger_query_relaxes_filing_type_when_metric_row_exists(tmp_path: Path) -> None:
    from sec_agent.mcp_tool_registry import invoke_mcp_tool

    store_path = tmp_path / "ledger.duckdb"
    write_ledger_store(
        [
            _fact_row(
                case_id="store_case",
                metric_family="capital_expenditure_proxy",
                metric_id="store_case::MSFT::2026::capital_expenditure_proxy::total_value::qtd",
                ticker="MSFT",
                form_type="10-Q",
            )
        ],
        store_path,
    )

    result = invoke_mcp_tool(
        "sec_query_exact_value_ledger",
        {
            "ledger_store_path": str(store_path),
            "tickers": ["MSFT"],
            "years": [2026],
            "filing_types": ["10-K"],
            "source_tiers": ["primary_sec_filing"],
            "metric_families": ["capex"],
            "period_roles": ["ANNUAL"],
            "limit": 10,
        },
    )

    assert result["status"] == "ok"
    assert result["row_count"] == 1
    assert result["fallback_trace"][0]["type"] == "relaxed_filing_type"
    assert result["fallback_trace"][-1]["type"] == "relaxed_filing_type_and_period_role"


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


def _fact_row(*, case_id: str, **overrides) -> dict:
    row = {
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
    row.update(overrides)
    return row
