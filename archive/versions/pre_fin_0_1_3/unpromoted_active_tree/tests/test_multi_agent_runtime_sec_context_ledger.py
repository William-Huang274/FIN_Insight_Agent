from __future__ import annotations

from sec_agent.financial_statement_analysis import build_fundamental_statement_pack
from sec_agent.multi_agent_runtime import _runtime_ledger_rows_from_sec_context


def test_sec_context_table_rows_backfill_runtime_ledger_and_fundamental_pack() -> None:
    context_rows = [
        {
            "ticker": "LLY",
            "source_family": "primary_sec_filing",
            "form_type": "10-Q",
            "evidence_id": "LLY_2026_10Q_ITEM1_BLOCK_0001",
            "text": """
Item 1. Financial Statements
Consolidated Condensed Statements of Operations
(Dollars and shares in millions, except per-share data)
[TABLE_START id=8 rows=6]
Three Months Ended March 31,
2026 | 2025
Revenue | $ | 19,799 | $ | 12,729
Cost of sales | 3,577 | 2,225
Research and development | 3,510 | 2,734
Net income | $ | 7,396 | $ | 2,759
[TABLE_END]
Selected Revenue Highlights
[TABLE_START id=10 rows=4]
(Dollars in millions) | First-Quarter
Selected Products | 2026 | 2025 | % Change
Mounjaro | $ | 8,662 | $ | 3,842 | 125%
Zepbound (1) | 4,160 | 2,312 | 80%
[TABLE_END]
""",
        }
    ]

    ledger_rows = _runtime_ledger_rows_from_sec_context(context_rows, state_context={"run_id": "unit-sec-context-ledger"})

    assert any(row["metric_name"] == "Revenue" and row["value"] == "19799.0" for row in ledger_rows)
    assert any(row["metric_name"] == "Revenue" and row["value"] == "12729.0" and row["fiscal_year"] == "2025" for row in ledger_rows)
    assert any(row["metric_family"] == "product_revenue" and row["product_or_segment"] == "Mounjaro" for row in ledger_rows)
    assert not any(row["raw_value_text"] == "125%" for row in ledger_rows)
    assert {row["source_family"] for row in ledger_rows} == {"primary_sec_filing"}
    assert any(row["fiscal_period"] == "Q1" for row in ledger_rows)

    pack = build_fundamental_statement_pack(
        {
            "run_id": "unit-sec-context-ledger",
            "user_query": "分析 LLY GLP-1 产品收入、收入质量和研发投入。",
            "query_contract": {
                "industry_schema": "healthcare_pharma",
                "focus_tickers": ["LLY"],
                "search_scope_tickers": ["LLY", "NVO"],
                "metric_families": ["revenue", "product_revenue", "rd_expense"],
            },
            "focus_tickers": ["LLY"],
            "search_scope_tickers": ["LLY", "NVO"],
            "runtime_ledger_rows": ledger_rows,
        }
    )

    assert pack["validation"]["status"] == "pass"
    assert pack["summary"]["line_item_count"] >= 2
    assert any(item["canonical_metric_id"] == "financial_metric:revenue" for item in pack["statement_line_items"])
    assert any(item["canonical_metric_id"] == "product_kpi:product_revenue" for item in pack["statement_line_items"])
