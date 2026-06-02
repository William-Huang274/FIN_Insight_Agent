from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from sec_agent.coverage_matrix import build_coverage_matrix
from sec_agent.query_contract import validate_query_contract
from connectors import SecEdgarConnector, SecEdgarConnectorError
from connectors.sec_filing_manifest import _build_record, collect_sec_filing_manifest
from evidence.schema import EvidenceObject
from evidence.structured_extractor import _parse_table_rows, extract_structured_objects
from ingestion.section_splitter import find_10q_sections
from retrieval.bm25_retriever import _record_matches as evidence_record_matches
from retrieval.object_bm25_retriever import _record_matches as object_record_matches


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_interactive_module():
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_synthesis_module():
    path = REPO_ROOT / "scripts" / "eval_sec_benchmark" / "run_sec_eval_synthesis_qwen9b_backend.py"
    scripts_root = str(REPO_ROOT / "scripts")
    if scripts_root not in sys.path:
        sys.path.insert(0, scripts_root)
    spec = importlib.util.spec_from_file_location("sec_agent_synthesis_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_ledger_missing_gate_module():
    path = REPO_ROOT / "scripts" / "eval_sec_benchmark" / "validate_sec_benchmark_ledger_missing_consistency.py"
    spec = importlib.util.spec_from_file_location("ledger_missing_gate_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_semantic_contract_gate_module():
    path = REPO_ROOT / "scripts" / "eval_sec_benchmark" / "validate_sec_benchmark_v2_semantic_contracts.py"
    spec = importlib.util.spec_from_file_location("semantic_contract_gate_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_query_contract_records_10q_inventory_gap_for_selected_ticker() -> None:
    inventory = {
        "inventory_digest": "inv-test",
        "companies": [
            {
                "ticker": "MSFT",
                "company": "Microsoft",
                "category": "tech",
                "filings": [
                    {
                        "year": 2026,
                        "form_type": "10-Q",
                        "source_type": "10-Q",
                        "source_tier": "primary_sec_filing",
                        "period_type": "quarterly",
                    }
                ],
            },
            {
                "ticker": "NVDA",
                "company": "NVIDIA",
                "category": "tech",
                "filings": [],
            },
        ],
        "categories": [{"category": "tech", "tickers": ["MSFT", "NVDA"]}],
    }
    contract = {
        "task_type": "general_sec_financial_question",
        "search_scope_tickers": ["MSFT", "NVDA"],
        "focus_tickers": ["MSFT", "NVDA"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["cloud_revenue"],
        "required_caveats": [
            "精确数值必须从运行时Exact-Value Ledger提取，本协议不包含具体数字。",
            "所有精确数值必须来自运行时Exact-Value Ledger，本协议不包含具体数字。",
        ],
        "decomposed_tasks": [
            {
                "task_id": "cloud_latest_quarter",
                "question_zh": "Use latest quarterly cloud evidence.",
                "priority": "primary",
                "required_tickers": ["MSFT", "NVDA"],
                "required_metric_families": ["cloud_revenue"],
            }
        ],
    }

    result = validate_query_contract(
        contract,
        selected_tickers=["MSFT", "NVDA"],
        selected_years=[2026],
        project_inventory=inventory,
    )

    clean = result["contract"]
    assert clean["source_policy"] == "SEC_PRIMARY_MIXED_RECENT"
    assert clean["scope"]["source_tiers"] == ["primary_sec_filing"]
    assert any(
        gap["ticker"] == "NVDA"
        and gap["form_type"] == "10-Q"
        and gap["reason"] == "10q_not_in_inventory"
        for gap in clean["source_coverage_gaps"]
    )
    assert not any("不包含具体数字" in caveat for caveat in clean["required_caveats"])
    assert any("不得使用模型记忆或未授权来源补数" in caveat for caveat in clean["required_caveats"])
    assert any("10-Q evidence is unaudited quarterly" in caveat for caveat in clean["required_caveats"])


def test_query_contract_source_gaps_are_scoped_to_focus_and_tasks() -> None:
    inventory = {
        "inventory_digest": "inv-focus-gap",
        "companies": [
            {
                "ticker": "MSFT",
                "company": "Microsoft",
                "category": "tech",
                "filings": [
                    {
                        "year": 2026,
                        "form_type": "10-Q",
                        "source_type": "10-Q",
                        "source_tier": "primary_sec_filing",
                    }
                ],
            },
            {
                "ticker": "NVDA",
                "company": "NVIDIA",
                "category": "tech",
                "filings": [],
            },
        ],
        "categories": [{"category": "tech", "tickers": ["MSFT", "NVDA"]}],
    }
    contract = {
        "task_type": "general_sec_financial_question",
        "search_scope_tickers": ["MSFT", "NVDA"],
        "focus_tickers": ["MSFT"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["cloud_revenue"],
        "decomposed_tasks": [
            {
                "task_id": "msft_latest_quarter",
                "question_zh": "Use MSFT latest quarterly cloud evidence.",
                "priority": "primary",
                "required_tickers": ["MSFT"],
                "required_metric_families": ["cloud_revenue"],
            }
        ],
    }

    result = validate_query_contract(
        contract,
        selected_tickers=["MSFT", "NVDA"],
        selected_years=[2026],
        project_inventory=inventory,
    )

    assert result["contract"]["source_coverage_gaps"] == []


def test_manifest_prefers_document_fiscal_period_focus_over_calendar_quarter(tmp_path: Path) -> None:
    html_path = tmp_path / "10-Q.html"
    metadata_path = tmp_path / "10-Q.metadata.json"
    html_path.write_text(
        '<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="ctx">2026</ix:nonNumeric>'
        '<ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="ctx">Q3</ix:nonNumeric>',
        encoding="utf-8",
    )
    metadata = {
        "ticker": "MSFT",
        "company": "MICROSOFT CORP",
        "cik": "0000789019",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "fiscal_year": 2026,
        "filing_date": "2026-04-29",
        "report_date": "2026-03-31",
        "period_end": "2026-03-31",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q1",
        "fiscal_period_source": "calendar_quarter_from_period_end",
        "accession_number": "0001193125-26-191507",
        "primary_document": "msft-20260331.htm",
    }

    record = _build_record(2026, "mega-cap_software_cloud", "MSFT", "10-Q", html_path, metadata_path, metadata)

    assert record.fiscal_period == "Q3"
    assert record.fiscal_year == 2026
    assert record.fiscal_year_source == "document_fiscal_year_focus"
    assert record.metadata["fiscal_period"] == "Q3"
    assert record.metadata["fiscal_period_source"] == "document_fiscal_period_focus"


def test_manifest_preserves_10k_metadata_year_when_parsed_focus_conflicts(tmp_path: Path) -> None:
    html_path = tmp_path / "10-K.html"
    metadata_path = tmp_path / "10-K.metadata.json"
    html_path.write_text(
        '<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="ctx">2024</ix:nonNumeric>'
        '<ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="ctx">FY</ix:nonNumeric>',
        encoding="utf-8",
    )
    metadata = {
        "ticker": "CRWD",
        "company": "CrowdStrike Holdings, Inc.",
        "cik": "0001535527",
        "form_type": "10-K",
        "source_tier": "primary_sec_filing",
        "fiscal_year": 2025,
        "filing_date": "2025-03-10",
        "report_date": "2025-01-31",
        "period_end": "2025-01-31",
        "period_type": "annual",
        "duration_months": 12,
        "fiscal_period": "FY",
        "accession_number": "0001535527-25-000009",
        "primary_document": "crwd-20250131.htm",
    }

    record = _build_record(2025, "cybersecurity", "CRWD", "10-K", html_path, metadata_path, metadata)

    assert record.fiscal_year == 2025
    assert record.fiscal_year_source == "metadata_fiscal_year_conflict_with_document_focus"
    assert record.document_fiscal_year_focus == 2024
    assert record.fiscal_period == "FY"
    assert record.period_type == "annual"


def test_manifest_filters_by_document_fiscal_year_not_cache_directory(tmp_path: Path) -> None:
    ticker_dir = tmp_path / "2026" / "consumer_retail" / "WMT"
    ticker_dir.mkdir(parents=True)
    (ticker_dir / "10-Q.html").write_text(
        '<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="ctx">2027</ix:nonNumeric>'
        '<ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="ctx">Q1</ix:nonNumeric>',
        encoding="utf-8",
    )
    (ticker_dir / "10-Q.metadata.json").write_text(
        """{
  "ticker": "WMT",
  "company": "Walmart Inc.",
  "cik": "0000104169",
  "form_type": "10-Q",
  "source_tier": "primary_sec_filing",
  "fiscal_year": 2026,
  "filing_date": "2026-06-05",
  "report_date": "2026-04-30",
  "period_end": "2026-04-30",
  "period_type": "quarterly",
  "duration_months": 3,
  "fiscal_period": "Q2",
  "fiscal_period_source": "calendar_quarter_from_period_end"
}
""",
        encoding="utf-8",
    )

    fy2027 = collect_sec_filing_manifest(tmp_path, years=[2027], form_types=["10-Q"])
    fy2026 = collect_sec_filing_manifest(tmp_path, years=[2026], form_types=["10-Q"])

    assert len(fy2027) == 1
    assert fy2027[0].fiscal_year == 2027
    assert fy2027[0].fiscal_period == "Q1"
    assert fy2027[0].fiscal_year_source == "document_fiscal_year_focus"
    assert fy2026 == []


def test_connector_selects_10q_by_document_fiscal_year_focus(monkeypatch, tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "Walmart Inc.",
        "filings": {
            "recent": {
                "form": ["10-Q", "10-Q"],
                "accessionNumber": ["0000104169-26-000111", "0000104169-25-000222"],
                "primaryDocument": ["wmt-20260430.htm", "wmt-20250430.htm"],
                "filingDate": ["2026-06-05", "2025-06-06"],
                "reportDate": ["2026-04-30", "2025-04-30"],
                "acceptanceDateTime": ["2026-06-05T18:00:00.000Z", "2025-06-06T18:00:00.000Z"],
                "primaryDocDescription": ["10-Q", "10-Q"],
            }
        },
    }

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)

    def fake_request_text(url: str) -> str:
        if "wmt-20260430" in url:
            return (
                '<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="ctx">2027</ix:nonNumeric>'
                '<ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="ctx">Q1</ix:nonNumeric>'
            )
        return (
            '<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="ctx">2026</ix:nonNumeric>'
            '<ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="ctx">Q1</ix:nonNumeric>'
        )

    monkeypatch.setattr(connector, "_request_text", fake_request_text)

    filing = connector.find_filing("104169", "10-Q", 2027)

    assert filing["fiscal_year"] == 2027
    assert filing["fiscal_year_source"] == "document_fiscal_year_focus"
    assert filing["fiscal_period"] == "Q1"
    assert filing["report_date"] == "2026-04-30"
    assert "DocumentFiscalYearFocus" in filing["_prefetched_html"]


def test_download_refreshes_stale_cache_when_cached_html_period_differs(tmp_path: Path) -> None:
    connector = SecEdgarConnector(
        user_agent="FinSight-Agent/0.1 test@example.com",
        cache_dir=tmp_path,
        log_path=tmp_path / "download_log.jsonl",
    )
    ticker_dir = tmp_path / "2026" / "mega-cap_software_cloud" / "MSFT"
    ticker_dir.mkdir(parents=True)
    html_path = ticker_dir / "10-Q.html"
    metadata_path = ticker_dir / "10-Q.metadata.json"
    html_path.write_text(
        '<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="ctx">2026</ix:nonNumeric>'
        '<ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="ctx">Q2</ix:nonNumeric>',
        encoding="utf-8",
    )
    metadata_path.write_text(
        """{
  "ticker": "MSFT",
  "form_type": "10-Q",
  "fiscal_year": 2026,
  "fiscal_period": "Q3",
  "document_fiscal_year_focus": 2026,
  "document_fiscal_period_focus": "Q3",
  "accession_number": "0001193125-26-222222",
  "primary_document": "msft-20260331.htm",
  "filing_url": "https://www.sec.gov/Archives/edgar/data/789019/new/msft-20260331.htm"
}
""",
        encoding="utf-8",
    )

    result = connector.download_filing_html(
        {
            "ticker": None,
            "company": "MICROSOFT CORP",
            "cik": "0000789019",
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "requested_fiscal_year": 2026,
            "fiscal_year": 2026,
            "filing_date": "2026-04-29",
            "report_date": "2026-03-31",
            "period_end": "2026-03-31",
            "period_type": "quarterly",
            "duration_months": 3,
            "fiscal_period": "Q3",
            "fiscal_period_source": "document_fiscal_period_focus",
            "accession_number": "0001193125-26-222222",
            "primary_document": "msft-20260331.htm",
            "filing_url": "https://www.sec.gov/Archives/edgar/data/789019/new/msft-20260331.htm",
            "_prefetched_html": (
                '<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="ctx">2026</ix:nonNumeric>'
                '<ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="ctx">Q3</ix:nonNumeric>'
            ),
        },
        ticker="MSFT",
        category="mega-cap software/cloud",
    )

    assert result["cache_status"] == "downloaded"
    assert result["accession_number"] == "0001193125-26-222222"
    assert result["fiscal_period"] == "Q3"
    assert "Q3" in html_path.read_text(encoding="utf-8")


def test_connector_rejects_filing_date_match_when_document_fiscal_year_differs(monkeypatch, tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "Alphabet Inc.",
        "filings": {
            "recent": {
                "form": ["10-K"],
                "accessionNumber": ["0001652044-26-000018"],
                "primaryDocument": ["goog-20251231.htm"],
                "filingDate": ["2026-02-05"],
                "reportDate": ["2025-12-31"],
                "acceptanceDateTime": ["2026-02-05T02:56:03.000Z"],
                "primaryDocDescription": ["10-K"],
            }
        },
    }

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(
        connector,
        "_request_text",
        lambda url: '<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="ctx">2025</ix:nonNumeric>',
    )

    try:
        connector.find_filing("1652044", "10-K", 2026)
    except SecEdgarConnectorError as exc:
        assert "fiscal year 2026" in str(exc)
    else:
        raise AssertionError("Expected fiscal-year mismatch to be rejected")


def test_connector_uses_10k_report_date_when_document_fiscal_year_is_stale(
    monkeypatch, tmp_path: Path
) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "Freeport-McMoRan Inc.",
        "filings": {
            "recent": {
                "form": ["10-K"],
                "accessionNumber": ["0000831259-25-000006"],
                "primaryDocument": ["fcx-20241231.htm"],
                "filingDate": ["2025-02-14"],
                "reportDate": ["2024-12-31"],
                "acceptanceDateTime": ["2025-02-14T22:00:48.000Z"],
                "primaryDocDescription": ["10-K"],
            }
        },
    }

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(
        connector,
        "_request_text",
        lambda url: (
            '<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="ctx">2023</ix:nonNumeric>'
            '<ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="ctx">FY</ix:nonNumeric>'
        ),
    )

    filing = connector.find_filing("831259", "10-K", 2024)

    assert filing["fiscal_year"] == 2024
    assert filing["fiscal_year_source"] == "annual_report_date_over_document_fiscal_year_focus"
    assert filing["document_fiscal_year_focus"] == 2023


def test_connector_preserves_retail_10k_prior_fiscal_year_for_january_report_date(
    monkeypatch, tmp_path: Path
) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "Home Depot, Inc.",
        "filings": {
            "recent": {
                "form": ["10-K"],
                "accessionNumber": ["0000354950-24-000062"],
                "primaryDocument": ["hd-20240202.htm"],
                "filingDate": ["2024-03-15"],
                "reportDate": ["2024-02-02"],
                "acceptanceDateTime": ["2024-03-15T12:00:00.000Z"],
                "primaryDocDescription": ["10-K"],
            }
        },
    }

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(
        connector,
        "_request_text",
        lambda url: (
            '<ix:nonNumeric name="dei:DocumentFiscalYearFocus" contextRef="ctx">2023</ix:nonNumeric>'
            '<ix:nonNumeric name="dei:DocumentFiscalPeriodFocus" contextRef="ctx">FY</ix:nonNumeric>'
        ),
    )

    filing = connector.find_filing("354950", "10-K", 2023)

    assert filing["fiscal_year"] == 2023
    assert filing["fiscal_year_source"] == "document_fiscal_year_focus"
    assert filing["report_date"] == "2024-02-02"


def test_api_memo_normalization_drops_unsupported_optional_claims() -> None:
    module = _load_synthesis_module()
    answer = {
        "direct_answer": "test",
        "investment_thesis": "test",
        "what_changed": [
            {"claim": "supported fact", "metric_ids": ["m1"], "evidence_ids": []}
        ],
        "why_it_matters": [
            {
                "insight": "unsupported insight",
                "business_implication": "unsupported implication",
                "metric_ids": [],
                "evidence_ids": [],
            }
        ],
        "peer_readthrough": [
            {
                "peer_or_group": "AMZN",
                "role": "direct competitor",
                "readthrough": "unsupported peer claim",
                "metric_ids": [],
                "evidence_ids": [],
            }
        ],
        "counterarguments": [
            {
                "claim": "future risk without current evidence",
                "why_it_could_weaken_thesis": "watch later",
                "metric_ids": [],
                "evidence_ids": [],
            }
        ],
        "watch_items": [
            {
                "item": "future 10-K margin",
                "why_it_matters": "profitability check",
                "source_to_watch": "future_10k",
                "metric_family": "gross_margin",
            }
        ],
        "source_limitations": ["SEC boundary"],
    }

    normalized = module._normalize_answer(
        answer,
        ledger_rows=[{"metric_id": "m1"}],
        context_rows=[],
        case={},
    )

    assert normalized["what_changed"]
    assert normalized["why_it_matters"] == []
    assert normalized["peer_readthrough"] == []
    assert normalized["counterarguments"] == []
    assert normalized["watch_items"]
    assert normalized["source_limitations"] == ["SEC boundary"]


def test_api_memo_normalization_drops_peer_readthrough_without_peer_contract() -> None:
    module = _load_synthesis_module()
    answer = {
        "direct_answer": "test",
        "investment_thesis": "test",
        "peer_readthrough": [
            {
                "peer_or_group": "AMZN",
                "role": "direct competitor",
                "readthrough": "supported but out-of-contract peer claim",
                "metric_ids": ["m1"],
                "evidence_ids": ["e1"],
            }
        ],
    }
    case = {
        "task_type": "single_or_multi_company_interactive",
        "query_contract": {
            "focus_tickers": ["MSFT"],
            "decomposed_tasks": [
                {
                    "task_id": "msft_period_compare",
                    "question_zh": "Compare MSFT 10-K and 10-Q cloud evidence.",
                    "required_tickers": ["MSFT"],
                    "required_metric_families": ["cloud_revenue"],
                }
            ],
        },
    }

    normalized = module._normalize_answer(
        answer,
        ledger_rows=[{"metric_id": "m1"}],
        context_rows=[{"evidence_id": "e1"}],
        case=case,
    )

    assert normalized["peer_readthrough"] == []
    assert normalized["_peer_readthrough_contract_sanitized_count"] == 1


def test_interactive_ledger_recognizes_10q_cash_flow_and_capex_rows() -> None:
    interactive = _load_interactive_module()
    contract = {
        "focus_tickers": ["MSFT"],
        "ledger_rules": {
            "allowed_metric_families": [
                "operating_cash_flow",
                "capital_expenditure_proxy",
                "free_cash_flow_proxy",
            ]
        },
    }
    ocf_record = {
        "object_id": "ocf1",
        "object_type": "metric",
        "source_evidence_id": "MSFT_2026_10Q_ITEM1_BLOCK_0004_CHUNK_0001",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_end": "2026-03-31",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q3",
        "section": "Item 1. Financial Statements",
        "subsection": "CASH FLOWS",
        "metric_name": "Net cash from operations",
        "row_label": "Net cash from operations",
        "column_label": "Nine Months Ended March 31, 2026",
        "raw_value": "127,494",
        "value": 127494.0,
        "unit": "usd_millions",
        "period": "2026",
        "period_role": "ytd",
        "context": "STATEMENTS",
        "metadata": {"column_index": 3, "logical_column_index": 2, "period_role": "ytd"},
    }
    capex_record = {
        "object_id": "capex1",
        "object_type": "metric",
        "source_evidence_id": "MSFT_2026_10Q_ITEM1_BLOCK_0004_CHUNK_0001",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_end": "2026-03-31",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q3",
        "section": "Item 1. Financial Statements",
        "subsection": "CASH FLOWS",
        "metric_name": "Additions to property and equipment",
        "row_label": "Additions to property and equipment",
        "column_label": None,
        "raw_value": "( 80,146",
        "value": 80146.0,
        "unit": "usd_millions",
        "period": None,
        "period_role": None,
        "context": "STATEMENTS",
        "metadata": {"column_index": 5, "logical_column_index": 4},
    }

    ocf = interactive._ledger_row_from_metric("case", ocf_record)
    capex = interactive._ledger_row_from_metric("case", capex_record)

    assert ocf["metric_family"] == "operating_cash_flow"
    assert ocf["period_role"] == "ytd"
    assert interactive._ledger_row_allowed(ocf, contract, None)
    assert capex["metric_family"] == "capital_expenditure_proxy"
    assert capex["period_role"] == "ytd"
    assert capex["fiscal_year"] == 2026
    assert capex["value"] == -80146.0
    assert capex["display_value_zh"] == "(80,146)（百万美元）"
    assert interactive._ledger_row_allowed(capex, contract, None)


def test_generic_runtime_ledger_cap_balances_decomposed_task_metric_families() -> None:
    interactive = _load_interactive_module()
    contract = {
        "task_type": "general_sec_financial_question",
        "decomposed_tasks": [
            {"required_metric_families": ["cloud_revenue", "data_center_revenue"]},
            {"required_metric_families": ["capital_expenditure_proxy", "operating_cash_flow", "research_and_development"]},
        ],
    }
    rows = []
    for idx in range(8):
        rows.append(
            {
                "ticker": "MSFT",
                "fiscal_year": 2026,
                "metric_family": "cloud_revenue",
                "metric_role": "total_value",
                "period_role": "qtd",
                "raw_value_text": str(idx),
                "object_id": f"cloud_{idx}",
            }
        )
    for idx, family in enumerate(["capital_expenditure_proxy", "operating_cash_flow", "research_and_development"]):
        rows.append(
            {
                "ticker": "MSFT",
                "fiscal_year": 2026,
                "metric_family": family,
                "metric_role": "total_value",
                "period_role": "qtd",
                "raw_value_text": str(idx),
                "object_id": f"investment_{idx}",
            }
        )

    capped = interactive._cap_ledger_rows(rows, contract, 4)
    families = {row["metric_family"] for row in capped}

    assert len(capped) == 4
    assert "cloud_revenue" in families
    assert {"capital_expenditure_proxy", "operating_cash_flow", "research_and_development"} & families


def test_interactive_ledger_defaults_10q_sentence_metrics_to_qtd() -> None:
    interactive = _load_interactive_module()
    record = {
        "object_id": "growth1",
        "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_04_OF_04",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_end": "2026-03-31",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q3",
        "section": "Item 2. Management's Discussion and Analysis",
        "metric_name": "Azure revenue growth",
        "raw_value": "40%",
        "value": 40.0,
        "unit": "percent",
        "period": "2026",
        "context": "Azure and other cloud services revenue grew 40%.",
    }

    row = interactive._ledger_row_from_metric("case", record)

    assert row["period_role"] == "qtd"


def test_interactive_ledger_derives_free_cash_flow_proxy_from_ocf_and_capex() -> None:
    interactive = _load_interactive_module()
    contract = {
        "focus_tickers": ["MSFT"],
        "metric_families": ["operating_cash_flow", "capital_expenditure_proxy", "free_cash_flow_proxy"],
        "ledger_rules": {
            "allowed_metric_families": [
                "operating_cash_flow",
                "capital_expenditure_proxy",
                "free_cash_flow_proxy",
            ]
        },
    }
    rows = [
        {
            "metric_id": "ocf",
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "source_fiscal_year": 2026,
            "period": "2026",
            "period_role": "ytd",
            "source_type": "10-Q",
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "period_end": "2026-03-31",
            "period_type": "quarterly",
            "duration_months": 3,
            "fiscal_period": "Q3",
            "metric_family": "operating_cash_flow",
            "metric_role": "total_value",
            "metric_name": "Net cash from operations",
            "value": 127494.0,
            "unit": "usd_millions",
            "source_evidence_id": "e1",
        },
        {
            "metric_id": "capex",
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "source_fiscal_year": 2026,
            "period": "2026",
            "period_role": "ytd",
            "source_type": "10-Q",
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "period_end": "2026-03-31",
            "period_type": "quarterly",
            "duration_months": 3,
            "fiscal_period": "Q3",
            "metric_family": "capital_expenditure_proxy",
            "metric_role": "total_value",
            "metric_name": "Additions to property and equipment",
            "value": -80146.0,
            "unit": "usd_millions",
            "source_evidence_id": "e1",
        },
    ]
    seen = {interactive._ledger_dedupe_key(row) for row in rows}

    interactive._supplement_free_cash_flow_proxy({"case_id": "case"}, rows, seen, contract)

    fcf_rows = [row for row in rows if row.get("metric_family") == "free_cash_flow_proxy"]
    assert len(fcf_rows) == 1
    assert fcf_rows[0]["value"] == 47348.0
    assert fcf_rows[0]["period_role"] == "ytd"


def test_table_parser_joins_standalone_parenthesis_cells() -> None:
    rows = _parse_table_rows("Additions to property and equipment | ( 80,146 | ) | ( 47,472 | )")

    assert rows == [["Additions to property and equipment", "( 80,146)", "( 47,472)"]]


def test_synthesis_cleanup_removes_unsupported_ratio_placeholders() -> None:
    module = _load_synthesis_module()

    cleaned = module._cleanup_unsupported_value_text(
        "Azure增速从当前引用未保留的精确比例跃升至当前引用未保留的精确比例，"
        "同比增长当前引用未保留的精确金额。"
    )

    assert "当前引用未保留" not in cleaned
    assert "较前期进一步提升" in cleaned
    assert "具体金额未进入当前引用" in cleaned


def test_api_memo_normalization_drops_final_unsupported_value_placeholders() -> None:
    module = _load_synthesis_module()
    answer = {
        "direct_answer": "test",
        "investment_thesis": "test",
        "decision_drivers": [
            {
                "driver_claim": "RPO从具体金额未进入当前引用增至具体金额未进入当前引用。",
                "why_it_matters": "visibility read",
                "supporting_metric_ids": ["m1"],
                "supporting_evidence_ids": ["e1"],
            }
        ],
        "why_it_matters": [
            {
                "insight": "资本支出从具体金额未进入当前引用降至具体金额未进入当前引用。",
                "business_implication": "cash-flow read",
                "metric_ids": ["m1"],
                "evidence_ids": ["e1"],
            }
        ],
        "counterarguments": [
            {
                "claim": "毛利率仅为具体比例未进入当前 ledger。",
                "why_it_could_weaken_thesis": "profitability risk",
                "metric_ids": ["m1"],
                "evidence_ids": ["e1"],
            }
        ],
        "limitations": ["具体金额未进入当前引用的候选比较已降级。"],
    }

    normalized = module._normalize_answer(
        answer,
        ledger_rows=[{"metric_id": "m1"}],
        context_rows=[{"evidence_id": "e1"}],
        case={},
    )
    payload = str(normalized)

    assert normalized["decision_drivers"] == []
    assert normalized["why_it_matters"] == []
    assert normalized["counterarguments"] == []
    assert "具体金额未进入当前引用" not in payload
    assert "具体比例未进入当前 ledger" not in payload


def test_api_memo_normalization_downgrades_recurring_quality_overclaim() -> None:
    module = _load_synthesis_module()
    answer = {
        "direct_answer": "test",
        "investment_thesis": "test",
        "why_it_matters": [
            {
                "insight": "服务业务呈现经常性收入特征。",
                "business_implication": "云化订阅模式具有高粘性和持续变现能力。",
                "metric_ids": ["m1"],
                "evidence_ids": [],
            }
        ],
        "decision_drivers": [
            {
                "driver_claim": "服务收入增长。",
                "why_it_matters": "经常性收入特征优于硬件厂商。",
                "metric_ids": ["m1"],
                "evidence_ids": [],
            }
        ],
    }

    normalized = module._normalize_answer(
        answer,
        ledger_rows=[{"metric_id": "m1", "metric_family": "services_revenue"}],
        context_rows=[],
        case={},
    )

    text = " ".join(
        str(item.get("insight") or "") + " " + str(item.get("business_implication") or "")
        for item in normalized["why_it_matters"]
    )
    text += " " + " ".join(
        str(item.get("driver_claim") or "") + " " + str(item.get("why_it_matters") or "")
        for item in normalized["decision_drivers"]
    )
    assert "经常性收入特征" not in text
    assert "高粘性" not in text
    assert normalized["_metric_role_term_sanitized_count"] >= 1


def test_query_contract_does_not_cross_product_10k_and_latest_10q_years() -> None:
    inventory = {
        "inventory_digest": "inv-mixed",
        "companies": [
            {
                "ticker": "MSFT",
                "company": "Microsoft",
                "category": "tech",
                "filings": [
                    {
                        "year": 2025,
                        "form_type": "10-K",
                        "source_tier": "primary_sec_filing",
                    },
                    {
                        "year": 2026,
                        "form_type": "10-Q",
                        "source_tier": "primary_sec_filing",
                    },
                ],
            }
        ],
        "categories": [{"category": "tech", "tickers": ["MSFT"]}],
    }
    contract = {
        "task_type": "general_sec_financial_question",
        "search_scope_tickers": ["MSFT"],
        "focus_tickers": ["MSFT"],
        "years": [2025, 2026],
        "filing_types": ["10-K", "10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["cloud_revenue"],
        "decomposed_tasks": [
            {
                "task_id": "mixed_recent",
                "question_zh": "Use annual and latest quarterly SEC evidence.",
                "priority": "primary",
                "required_tickers": ["MSFT"],
                "required_metric_families": ["cloud_revenue"],
            }
        ],
    }

    result = validate_query_contract(
        contract,
        selected_tickers=["MSFT"],
        selected_years=[2025, 2026],
        project_inventory=inventory,
    )

    clean = result["contract"]
    assert clean["source_policy"] == "SEC_PRIMARY_MIXED_RECENT"
    assert clean["source_coverage_gaps"] == []


def test_interactive_mixed_policy_keeps_10q_when_planner_returns_10k_only(monkeypatch) -> None:
    interactive = _load_interactive_module()
    monkeypatch.setenv("SEC_AGENT_SOURCE_POLICY", "SEC_PRIMARY_MIXED_RECENT")
    inventory = {
        "inventory_digest": "inv-mixed",
        "companies": [
            {
                "ticker": "MSFT",
                "company": "Microsoft",
                "category": "tech",
                "filings": [
                    {
                        "year": 2025,
                        "form_type": "10-K",
                        "source_tier": "primary_sec_filing",
                    },
                    {
                        "year": 2026,
                        "form_type": "10-Q",
                        "source_tier": "primary_sec_filing",
                    },
                ],
            }
        ],
        "categories": [{"category": "tech", "tickers": ["MSFT"]}],
    }
    stale_planner_contract = {
        "task_type": "general_sec_financial_question",
        "search_scope_tickers": ["MSFT"],
        "focus_tickers": ["MSFT"],
        "years": [2025, 2026],
        "filing_types": ["10-K"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["cloud_revenue"],
        "decomposed_tasks": [
            {
                "task_id": "cloud_mixed",
                "question_zh": "Compare annual and quarterly cloud evidence.",
                "priority": "primary",
                "required_tickers": ["MSFT"],
                "required_metric_families": ["cloud_revenue"],
            }
        ],
    }

    repaired = interactive._repair_query_contract_from_prompt(
        stale_planner_contract,
        "比较MSFT 2025年10-K和2026年10-Q的云业务表现",
        ["MSFT"],
        [2025, 2026],
        inventory,
    )
    clean = interactive._validate_query_contract(repaired, ["MSFT"], [2025, 2026], inventory)

    assert clean["filing_types"] == ["10-K", "10-Q"]
    assert clean["source_policy"] == "SEC_PRIMARY_MIXED_RECENT"
    assert not any(
        task.get("task_id") == "peer_competition_mapping" or task.get("peer_tickers")
        for task in clean["decomposed_tasks"]
    )


def test_interactive_period_compare_is_not_peer_case_for_broad_search_scope() -> None:
    interactive = _load_interactive_module()
    query_contract = {
        "task_type": "general_sec_financial_question",
        "source_policy": "SEC_PRIMARY_MIXED_RECENT",
        "focus_tickers": ["MSFT"],
        "search_scope_tickers": ["MSFT", "AMZN", "GOOGL"],
        "years": [2025, 2026],
        "filing_types": ["10-K", "10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "decomposed_tasks": [
            {
                "task_id": "msft_annual_quarter_compare",
                "question_zh": "Compare MSFT 2025 10-K and 2026 10-Q cloud evidence.",
                "priority": "primary",
                "required_tickers": ["MSFT"],
                "required_metric_families": ["cloud_revenue"],
            }
        ],
    }

    case = interactive._build_case(
        "比较MSFT 2025年10-K和2026年10-Q的云业务表现",
        ["MSFT", "AMZN", "GOOGL"],
        [2025, 2026],
        "peer_scope_test",
        query_contract,
    )

    assert case["task_type"] == "single_or_multi_company_interactive"
    assert "entity_bleed_between_peers" not in case["failure_types"]


def test_broad_full30_peer_compare_does_not_require_every_company_mention() -> None:
    interactive = _load_interactive_module()
    gate = _load_semantic_contract_gate_module()
    tickers = [
        "AAPL",
        "MSFT",
        "NVDA",
        "AMD",
        "AVGO",
        "AMAT",
        "MU",
        "INTC",
        "QCOM",
        "GOOGL",
        "AMZN",
        "META",
        "ADBE",
        "SNOW",
        "CRM",
        "ORCL",
        "JPM",
        "BAC",
        "GS",
        "MS",
        "LLY",
        "PFE",
        "JNJ",
        "CVX",
        "XOM",
        "WMT",
        "PG",
        "CAT",
        "GE",
        "TXN",
    ]
    query_contract = {
        "task_type": "general_sec_financial_question",
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT",
        "focus_tickers": tickers,
        "search_scope_tickers": tickers,
        "years": [2025, 2026],
        "filing_types": ["10-K", "10-Q", "8-K"],
        "source_tiers": [
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "market_snapshot",
        ],
        "decomposed_tasks": [
            {
                "task_id": "peer_market_fundamental_divergence",
                "question_zh": "比较当前full30公司中哪些公司的市场反应与基本面最一致。",
                "priority": "primary",
                "required_tickers": tickers[:8],
                "peer_tickers": tickers[8:16],
                "required_metric_families": ["revenue", "operating_income"],
            }
        ],
    }

    case = interactive._build_case(
        "比较当前full30公司中哪些公司的市场反应与已披露基本面最一致，哪些可能存在分歧。",
        tickers,
        [2025, 2026],
        "full30_peer_scan",
        query_contract,
    )

    assert case["semantic_gate"]["company_coverage"] == "selected_companies"
    assert case["semantic_gate"]["require_company_coverage"] is False
    assert "entity_bleed_between_peers" in case["failure_types"]

    result = gate._validate_agent_row(
        {
            "case_id": case["case_id"],
            "mode": "pipeline_context",
            "status": "answered",
            "answer_status": "answered_api_model",
            "answer": {
                "direct_answer": "NVDA and MSFT show stronger market-fundamental confirmation; AMD shows a weaker setup.",
                "decision_drivers": [],
                "key_points": [],
                "source_limitations": [],
            },
        },
        case,
        [],
    )

    assert result["status"] == "pass"
    assert not result["failures"]
    assert any(
        warning.get("type") == "selected_company_coverage_not_all_focus_tickers"
        for warning in result["warnings"]
    )


def test_small_peer_compare_still_requires_all_focus_mentions() -> None:
    interactive = _load_interactive_module()
    tickers = ["NVDA", "AMD", "MSFT"]
    case = interactive._build_case(
        "请具体比较NVDA、AMD和MSFT的AI业务表现。",
        tickers,
        [2025, 2026],
        "small_peer_compare",
        {
            "task_type": "general_sec_financial_question",
            "source_policy": "SEC_PRIMARY_MIXED_RECENT",
            "focus_tickers": tickers,
            "search_scope_tickers": tickers,
            "years": [2025, 2026],
            "filing_types": ["10-K", "10-Q"],
            "source_tiers": ["primary_sec_filing"],
            "decomposed_tasks": [
                {
                    "task_id": "peer_comparison",
                    "question_zh": "比较NVDA、AMD和MSFT的AI业务表现。",
                    "priority": "primary",
                    "required_tickers": tickers,
                    "peer_tickers": ["AMD", "MSFT"],
                    "required_metric_families": ["revenue"],
                }
            ],
        },
    )

    assert case["semantic_gate"]["company_coverage"] == "all_focus"
    assert case["semantic_gate"]["require_company_coverage"] is True


def test_coverage_matrix_does_not_count_10k_rows_for_10q_scope() -> None:
    query_contract = {
        "source_policy": "SEC_PRIMARY_MIXED_RECENT",
        "search_scope_tickers": ["MSFT"],
        "focus_tickers": ["MSFT"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["cloud_revenue"],
        "decomposed_tasks": [
            {
                "task_id": "cloud_latest_quarter",
                "question_zh": "Compare latest quarterly cloud revenue.",
                "priority": "primary",
                "required_tickers": ["MSFT"],
                "required_metric_families": ["cloud_revenue"],
            }
        ],
    }
    wrong_form_context = [
        {
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "10-K",
            "source_tier": "primary_sec_filing",
            "text": "Microsoft cloud revenue.",
            "source_evidence_id": "MSFT_2026_10K_ITEM7_BLOCK_1",
        }
    ]
    wrong_form_ledger = [
        {
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "10-K",
            "source_tier": "primary_sec_filing",
            "metric_family": "cloud_revenue",
            "metric_id": "m1",
            "source_evidence_id": "MSFT_2026_10K_ITEM7_BLOCK_1",
        }
    ]

    matrix = build_coverage_matrix(
        case={"case_id": "case_10q_scope"},
        query_contract=query_contract,
        context_rows=wrong_form_context,
        ledger_rows=wrong_form_ledger,
    )

    task = matrix["tasks"][0]
    assert task["support_level"] == "insufficient"
    assert task["ledger_row_count"] == 0
    assert task["context_row_count"] == 0
    assert task["missing_filing_types"] == ["10-Q"]
    assert "10-Q" in " ".join(task["must_caveat"])


def test_coverage_matrix_counts_matching_10q_source_scope() -> None:
    query_contract = {
        "source_policy": "SEC_PRIMARY_MIXED_RECENT",
        "search_scope_tickers": ["MSFT"],
        "focus_tickers": ["MSFT"],
        "years": [2026],
        "filing_types": ["10-Q"],
        "source_tiers": ["primary_sec_filing"],
        "metric_families": ["cloud_revenue"],
        "decomposed_tasks": [
            {
                "task_id": "cloud_latest_quarter",
                "question_zh": "Compare latest quarterly cloud revenue.",
                "priority": "primary",
                "required_tickers": ["MSFT"],
                "required_metric_families": ["cloud_revenue"],
            }
        ],
    }
    context_rows = [
        {
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "text": "Microsoft cloud revenue.",
            "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_1",
        }
    ]
    ledger_rows = [
        {
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "metric_family": "cloud_revenue",
            "metric_id": "m1",
            "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_1",
        }
    ]

    matrix = build_coverage_matrix(
        case={"case_id": "case_10q_scope"},
        query_contract=query_contract,
        context_rows=context_rows,
        ledger_rows=ledger_rows,
    )

    task = matrix["tasks"][0]
    assert task["support_level"] == "medium"
    assert task["covered_filing_types"] == ["10-Q"]
    assert task["covered_source_tiers"] == ["primary_sec_filing"]
    assert task["missing_filing_types"] == []


def test_runtime_ledger_preserves_10q_source_metadata_and_rejects_false_rows() -> None:
    interactive = _load_interactive_module()
    record = {
        "object_id": "obj_amzn_aws_operating_income",
        "source_evidence_id": "AMZN_2026_10Q_ITEM2_BLOCK_1",
        "ticker": "AMZN",
        "fiscal_year": 2026,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_end": "2026-03-31",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q1",
        "metric_name": "AWS operating income",
        "raw_value": "$11,531",
        "value": 11531,
        "unit": "usd_millions",
        "period": "2026",
        "context": "Operating income by segment. AWS operating income was $11,531 million.",
    }

    row = interactive._ledger_row_from_metric("case", record)

    assert row is not None
    assert row["form_type"] == "10-Q"
    assert row["source_tier"] == "primary_sec_filing"
    assert row["period_type"] == "quarterly"
    assert row["period_role"] == "qtd"
    assert interactive._ledger_row_allowed(row, {"focus_tickers": ["AMZN"]}, None)

    false_operating_income = dict(row)
    false_operating_income.update(
        {
            "metric_name": "Revenue",
            "row_label": "Revenue",
            "metric_family": "operating_income",
            "record_title": "Operating income by segment",
        }
    )
    assert not interactive._ledger_row_allowed(false_operating_income, {"focus_tickers": ["AMZN"]}, None)

    operating_income_change = interactive._ledger_row_from_metric(
        "case",
        {
            "object_id": "MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04_METRIC_SENT_D017C4E9",
            "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04",
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "source_type": "10-Q",
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "metric_name": "operating income",
            "raw_value": "$6.4 billion",
            "value": 6.4,
            "unit": "usd_billions",
            "period": "2026",
            "context": "Operating income increased $6.4 billion or 20% driven by growth in Productivity and Business Processes and Intelligent Cloud.",
        },
    )
    assert operating_income_change is not None
    assert operating_income_change["metric_role"] == "period_change_amount"
    assert not interactive._ledger_row_allowed(operating_income_change, {"focus_tickers": ["MSFT"]}, None)

    gross_margin_change = {
        "ticker": "MSFT",
        "metric_family": "gross_margin",
        "metric_role": "percentage_rate",
        "metric_name": "Gross margin growth rate",
        "raw_value_text": "17%",
        "value": 17,
        "unit": "percent",
        "source_text": "Gross margin increased 17% driven by cloud services.",
    }
    assert not interactive._ledger_row_allowed(gross_margin_change, {"focus_tickers": ["MSFT"]}, None)

    gross_margin_change_cell = interactive._ledger_row_from_metric(
        "case",
        {
            "object_id": "MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04_METRIC_TABLE_9D476233",
            "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04",
            "ticker": "MSFT",
            "fiscal_year": 2026,
            "source_type": "10-Q",
            "form_type": "10-Q",
            "source_tier": "primary_sec_filing",
            "metric_name": "Gross margin",
            "row_label": "Gross margin",
            "raw_value": "17%",
            "value": 17,
            "unit": "percent",
            "period": "2026",
            "context": "SUMMARY RESULTS OF OPERATIONS",
            "metadata": {"cell_kind": "change_value", "table_object_id": "table_msft_summary"},
        },
    )
    assert gross_margin_change_cell is not None
    assert gross_margin_change_cell["cell_kind"] == "change_value"
    assert not interactive._ledger_row_allowed(gross_margin_change_cell, {"focus_tickers": ["MSFT"]}, None)

    stale_gross_margin_change_cell = dict(gross_margin_change_cell)
    stale_gross_margin_change_cell["cell_kind"] = "period_value"
    stale_gross_margin_change_cell["column_label"] = None
    assert not interactive._ledger_row_allowed(stale_gross_margin_change_cell, {"focus_tickers": ["MSFT"]}, None)


def test_runtime_ledger_extracts_growth_rate_without_losing_source_metadata() -> None:
    interactive = _load_interactive_module()
    record = {
        "object_id": "obj_msft_cloud_revenue",
        "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_1",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q1",
        "metric_name": "Microsoft Cloud revenue",
        "raw_value": "$42.4 billion",
        "value": 42.4,
        "unit": "usd_billions",
        "period": "2026",
        "context": "Microsoft Cloud revenue increased $9.8 billion or 31% driven by Azure.",
    }
    base_row = interactive._ledger_row_from_metric("case", record)
    assert base_row is not None

    growth_rows = interactive._ledger_growth_rate_rows_from_metric("case", record, base_row)

    assert len(growth_rows) == 1
    assert growth_rows[0]["metric_role"] == "percentage_rate"
    assert growth_rows[0]["raw_value_text"] == "31%"
    assert growth_rows[0]["form_type"] == "10-Q"
    assert growth_rows[0]["period_role"] == "qtd"
    assert interactive._ledger_row_allowed(growth_rows[0], {"focus_tickers": ["MSFT"]}, None)


def test_heuristic_banking_contract_sets_source_tiers_without_planner_state() -> None:
    interactive = _load_interactive_module()
    inventory = {
        "inventory_digest": "inv-bank",
        "companies": [
            {
                "ticker": "JPM",
                "company": "JPMorgan Chase",
                "category": "banking",
                "filings": [
                    {
                        "year": 2026,
                        "form_type": "10-Q",
                        "source_tier": "primary_sec_filing",
                    }
                ],
            }
        ],
        "categories": [{"category": "banking", "tickers": ["JPM"]}],
    }

    contract = interactive._build_heuristic_query_contract("JPM银行净息差和存贷款表现如何", ["JPM"], [2026], inventory)

    assert contract["source_tiers"] == ["primary_sec_filing"]


def test_retriever_source_filters_infer_form_type_from_legacy_ids() -> None:
    evidence_record = {
        "evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_1",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "metadata": {},
    }
    object_record = {
        "object_id": "MSFT_2026_10Q_ITEM2_BLOCK_1_TABLE_1",
        "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_1",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "metadata": {},
    }

    source_filters = {"form_type": ["10-Q"], "source_tier": ["primary_sec_filing"]}
    wrong_form_filters = {"form_type": ["10-K"], "source_tier": ["primary_sec_filing"]}

    assert evidence_record_matches(evidence_record, source_filters)
    assert object_record_matches(object_record, source_filters)
    assert not evidence_record_matches(evidence_record, wrong_form_filters)
    assert not object_record_matches(object_record, wrong_form_filters)


def test_synthesis_removes_protocol_has_no_numbers_limitation_when_ledger_exists() -> None:
    synthesis = _load_synthesis_module()
    answer = {
        "not_found": ["NVDA 2026 10-Q still missing"],
        "source_limitations": [
            "精确数值必须从运行时Exact-Value Ledger提取，本协议不提供最终数字。",
            "10-Q evidence is unaudited quarterly evidence.",
        ],
        "limitations": [
            "精确数值必须来自运行时Exact-Value Ledger，本协议不包含具体数字。",
            "所有精确数值必须来自运行时Exact-Value Ledger，本协议不包含任何具体数字。",
            "精确数值必须从运行时Exact-Value Ledger提取，本协议不提供最终数字。",
            "Evidence Coverage Matrix records source inventory gaps.",
        ],
    }
    ledger_rows = [
        {
            "ticker": "NVDA",
            "fiscal_year": 2026,
            "metric_family": "data_center_revenue",
            "metric_id": "m_nvda_2026_q1_dc",
        }
    ]

    cleaned = synthesis._remove_false_missing_ledger_claims(answer, ledger_rows)

    assert cleaned["not_found"] == ["NVDA 2026 10-Q still missing"]
    assert cleaned["source_limitations"] == ["10-Q evidence is unaudited quarterly evidence."]
    assert cleaned["limitations"] == ["Evidence Coverage Matrix records source inventory gaps."]


def test_ledger_missing_gate_flags_protocol_no_final_numbers_with_ledger() -> None:
    gate = _load_ledger_missing_gate_module()
    answer = {
        "source_limitations": [
            "精确数值必须从运行时Exact-Value Ledger提取，本协议不提供最终数字。"
        ],
        "limitations": [],
        "not_found": [],
    }
    locations = gate._missing_statement_locations(answer)
    available = {("AMZN", 2026, "cloud_revenue")}

    assert locations == [
        {
            "location": "source_limitations[1]",
            "text": "精确数值必须从运行时Exact-Value Ledger提取，本协议不提供最终数字。",
        }
    ]
    assert gate._false_missing_matches(locations[0]["text"], available) == [("AMZN", 2026, "cloud_revenue")]


def test_structured_extractor_aligns_multirow_percentage_change_columns() -> None:
    evidence = EvidenceObject(
        evidence_id="MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04",
        source_type="10-Q",
        source_tier="primary_sec_filing",
        ticker="MSFT",
        fiscal_year=2026,
        period_end="2026-03-31",
        period_type="quarterly",
        duration_months=3,
        fiscal_period="Q1",
        section="Item 2. Management's Discussion and Analysis",
        subsection="Productivity and Business Processes and Intelligent Cloud",
        evidence_type="section_text",
        text=(
            "SUMMARY RESULTS OF OPERATIONS\n"
            "[TABLE_START id=47 rows=4]\n"
            "(In millions, except percentages and per share amounts)|Three Months Ended March 31,|Percentage Change|Nine Months Ended March 31,|Percentage Change\n"
            "2026|2025|2026|2025\n"
            "Revenue|$|82,886|$|70,066|18%|$|241,832|$|205,283|18%\n"
            "Gross margin|56,058|48,147|16%|164,983|141,466|17%\n"
            "[TABLE_END]"
        ),
        metadata={"form_type": "10-Q", "block_id": "MSFT_2026_10Q_ITEM2_BLOCK_0004"},
    )

    result = extract_structured_objects(evidence)
    table = result.tables[0]
    gross_cells = [cell for cell in table.cells if cell["row_label"] == "Gross margin"]
    amount_cell = next(cell for cell in gross_cells if cell["raw_value"] == "56,058")
    change_cell = next(cell for cell in gross_cells if cell["raw_value"] == "17%")

    assert amount_cell["unit"] == "usd_millions"
    assert amount_cell["cell_kind"] == "period_value"
    assert amount_cell["period_role"] == "qtd"
    assert change_cell["column_label"] == "Percentage Change"
    assert change_cell["cell_kind"] == "change_value"

    ytd_cell = next(cell for cell in gross_cells if cell["raw_value"] == "164,983")
    assert ytd_cell["period_role"] == "ytd"

    amount_metric = next(metric for metric in result.metrics if metric.raw_value == "56,058")
    ytd_metric = next(metric for metric in result.metrics if metric.raw_value == "164,983")
    assert amount_metric.period_role == "qtd"
    assert ytd_metric.period_role == "ytd"


def test_structured_extractor_expands_two_row_period_headers_without_change_columns() -> None:
    evidence = EvidenceObject(
        evidence_id="MSFT_2026_10Q_ITEM1_BLOCK_0026_PART_01_OF_02",
        source_type="10-Q",
        source_tier="primary_sec_filing",
        ticker="MSFT",
        fiscal_year=2026,
        period_end="2026-03-31",
        period_type="quarterly",
        duration_months=3,
        fiscal_period="Q1",
        section="Item 1. Financial Statements",
        subsection="Revenue",
        evidence_type="section_text",
        text=(
            "Revenue, classified by significant product and service offerings, was as follows:\n"
            "[TABLE_START id=26 rows=5]\n"
            "(In millions, except per share amounts) (Unaudited)|Three Months Ended March 31,|Nine Months Ended March 31,\n"
            "2026|2025|2026|2025\n"
            "Server products and cloud services|$|32,592|$|24,761|$|92,329|$|70,557\n"
            "Microsoft 365 Commercial products and cloud services|25,593|21,883|74,083|63,449\n"
            "[TABLE_END]"
        ),
        metadata={"form_type": "10-Q", "block_id": "MSFT_2026_10Q_ITEM1_BLOCK_0026"},
    )

    result = extract_structured_objects(evidence)
    table = result.tables[0]
    cells = [cell for cell in table.cells if cell["row_label"] == "Server products and cloud services"]

    assert [cell["period_role"] for cell in cells] == ["qtd", "qtd", "ytd", "ytd"]
    assert [cell["period"] for cell in cells] == ["2026", "2025", "2026", "2025"]
    assert "Three Months Ended March 31, 2026" == cells[0]["column_label"]
    assert "Nine Months Ended March 31, 2025" == cells[3]["column_label"]
    assert not any(metric.row_label == "2026" for metric in result.metrics)
    metric = next(
        item
        for item in result.metrics
        if item.row_label == "Server products and cloud services" and item.raw_value == "$ 32,592"
    )
    assert metric.period_role == "qtd"


def test_runtime_ledger_and_renderer_surface_period_role() -> None:
    interactive = _load_interactive_module()
    table_record = {
        "object_id": "MSFT_2026_10Q_ITEM2_TABLE",
        "object_type": "table",
        "source_evidence_id": "MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_end": "2026-03-31",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q1",
        "title": "SUMMARY RESULTS OF OPERATIONS",
        "cells": [
            {
                "row_label": "Revenue",
                "column_label": "Three Months Ended March 31, 2026",
                "period": "2026",
                "period_role": "qtd",
                "raw_value": "$82,886",
                "value": 82886,
                "unit": "usd_millions",
                "cell_kind": "period_value",
                "row_index": 3,
            },
            {
                "row_label": "Revenue",
                "column_label": "Nine Months Ended March 31, 2026",
                "period": "2026",
                "period_role": "ytd",
                "raw_value": "$241,832",
                "value": 241832,
                "unit": "usd_millions",
                "cell_kind": "period_value",
                "row_index": 3,
            },
        ],
    }

    rows = interactive._ledger_rows_from_table("case", table_record, {2026})

    assert [row["period_role"] for row in rows] == ["qtd", "ytd"]
    assert [row["source_fiscal_year"] for row in rows] == [2026, 2026]
    metric_rows = {row["metric_id"]: row for row in rows}
    answer = {
        "key_points": [
            {
                "point": "MSFT revenue uses separate period roles.",
                "metric_ids": [rows[0]["metric_id"], rows[1]["metric_id"]],
                "evidence_ids": ["MSFT_2026_10Q_ITEM2_BLOCK_0004_PART_01_OF_04"],
            }
        ],
    }
    rendered = interactive._rendered_answer_markdown("test", answer, metric_rows)

    assert "10-Q Q1 QTD period_end=2026-03-31" in rendered
    assert "10-Q Q1 YTD period_end=2026-03-31" in rendered


def test_renderer_uses_metric_role_for_percentage_rate_labels() -> None:
    interactive = _load_interactive_module()
    row = {
        "metric_id": "m_cloud_growth",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "form_type": "10-Q",
        "fiscal_period": "Q3",
        "period_role": "qtd",
        "period_end": "2026-03-31",
        "metric_family": "cloud_revenue",
        "metric_role": "percentage_rate",
        "metric_name": "Server products and cloud services growth rate",
        "display_value_zh": "17%",
    }

    rendered = interactive._rendered_answer_markdown(
        "test",
        {"what_changed": [{"claim": "Cloud growth rate is supported.", "metric_ids": ["m_cloud_growth"]}]},
        {"m_cloud_growth": row},
    )

    assert "云业务收入增长率" in rendered
    assert "云业务收入: 17%" not in rendered


def test_sentence_amount_before_growth_rate_stays_total_value() -> None:
    interactive = _load_interactive_module()
    record = {
        "object_id": "AMD_2026_10Q_ITEM2_BLOCK_0004_CHUNK_0001_METRIC_SENT",
        "source_evidence_id": "AMD_2026_10Q_ITEM2_BLOCK_0004_CHUNK_0001",
        "ticker": "AMD",
        "fiscal_year": 2026,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_end": "2026-03-28",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q1",
        "metric_name": "Data Center net revenue",
        "raw_value": "$5.8 billion",
        "value": 5.8,
        "unit": "usd_billions",
        "context": (
            "Data Center net revenue of $5.8 billion for the three months ended "
            "March 28, 2026 increased by 57%, compared to net revenue of $3.7 billion "
            "for the prior year period."
        ),
    }

    row = interactive._ledger_row_from_metric("case", record)

    assert row is not None
    assert row["metric_family"] == "data_center_revenue"
    assert row["metric_role"] == "total_value"


def test_sentence_amount_after_increased_by_is_period_change() -> None:
    interactive = _load_interactive_module()
    record = {
        "object_id": "AMD_2026_10Q_ITEM2_BLOCK_0004_CHUNK_0001_METRIC_SENT",
        "source_evidence_id": "AMD_2026_10Q_ITEM2_BLOCK_0004_CHUNK_0001",
        "ticker": "AMD",
        "fiscal_year": 2026,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_end": "2026-03-28",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q1",
        "metric_name": "Data Center net revenue",
        "raw_value": "$2.1 billion",
        "value": 2.1,
        "unit": "usd_billions",
        "context": "Data Center net revenue increased by $2.1 billion from the prior year period.",
    }

    row = interactive._ledger_row_from_metric("case", record)

    assert row is not None
    assert row["metric_role"] == "period_change_amount"


def test_renderer_marks_prior_year_comparable_columns_from_current_10q() -> None:
    interactive = _load_interactive_module()
    table_record = {
        "object_id": "MSFT_2026_10Q_ITEM1_TABLE",
        "object_type": "table",
        "source_evidence_id": "MSFT_2026_10Q_ITEM1_BLOCK_0026_PART_01_OF_02",
        "ticker": "MSFT",
        "fiscal_year": 2026,
        "source_type": "10-Q",
        "form_type": "10-Q",
        "source_tier": "primary_sec_filing",
        "period_end": "2026-03-31",
        "period_type": "quarterly",
        "duration_months": 3,
        "fiscal_period": "Q3",
        "title": "Revenue",
        "cells": [
            {
                "row_label": "Server products and cloud services",
                "column_label": "Nine Months Ended March 31, 2025",
                "period": "2025",
                "period_role": "ytd",
                "raw_value": "$70,557",
                "value": 70557,
                "unit": "usd_millions",
                "cell_kind": "period_value",
                "row_index": 3,
            }
        ],
    }

    rows = interactive._ledger_rows_from_table("case", table_record, {2025, 2026})

    assert rows[0]["fiscal_year"] == 2025
    assert rows[0]["source_fiscal_year"] == 2026
    rendered = interactive._rendered_answer_markdown(
        "test",
        {
            "key_points": [
                {
                    "point": "Prior-year comparable is sourced from the current 10-Q.",
                    "metric_ids": [rows[0]["metric_id"]],
                    "evidence_ids": ["MSFT_2026_10Q_ITEM1_BLOCK_0026_PART_01_OF_02"],
                }
            ],
        },
        {rows[0]["metric_id"]: rows[0]},
    )

    assert "MSFT FY2025 comparable in FY2026 filing 10-Q Q3 YTD period_end=2026-03-31" in rendered


def test_10q_splitter_uses_readable_ge_style_headings_before_cross_reference() -> None:
    text = "\n".join(
        [
            "FORM 10-Q",
            "Table of Contents",
            "Forward-Looking Statements",
            "filler " * 900,
            "MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS (MD&A).",
            "Revenue increased because services demand improved. " * 40,
            "CONTROLS AND PROCEDURES",
            "Management evaluated disclosure controls and procedures. " * 20,
            "[TABLE_START id=21 rows=30]",
            "STATEMENT OF OPERATIONS (UNAUDITED) | Three months ended March 31",
            "(In millions) | 2026 | 2025",
            "Total revenue | $ | 12,392 | $ | 9,935",
            "[TABLE_END]",
            "Financial statements and notes continue here. " * 60,
            "EXHIBITS",
            "[TABLE_START id=55 rows=15]",
            "FORM 10-Q CROSS REFERENCE INDEX | Page(s)",
            "Item 1. | Financial Statements | 13 -30",
            "Item 2. | Management's Discussion and Analysis of Financial Condition and Results of Operations | 4 -12",
            "Item 3. | Quantitative and Qualitative Disclosures About Market Risk | 9, 26-27",
            "Item 4. | Controls and Procedures | 12",
            "Item 1A. | Risk Factors | Not applicable(a)",
            "[TABLE_END]",
        ]
    )

    sections = find_10q_sections(text)

    assert [section.item_code for section in sections] == ["2", "4", "1"]
    assert sections[0].text.startswith("MANAGEMENT'S DISCUSSION")
    assert "STATEMENT OF OPERATIONS (UNAUDITED)" in sections[-1].text
    assert "FORM 10-Q CROSS REFERENCE INDEX" not in sections[-1].text


def test_10q_splitter_handles_intc_style_reader_friendly_layout() -> None:
    text = "\n".join(
        [
            "FORM 10-Q",
            "Table of Contents",
            "Organization of Our Form 10-Q",
            "filler " * 900,
            "[TABLE_START id=9 rows=1]",
            "Consolidated Condensed Statements of Operations",
            "[TABLE_END]",
            "[TABLE_START id=10 rows=22]",
            "Three Months Ended",
            "(In Millions; Unaudited) | Mar 28, 2026 | Mar 29, 2025",
            "Net revenue | $ | 13,577 | $ | 12,667",
            "[TABLE_END]",
            "Notes to Consolidated Condensed Financial Statements",
            "Interim notes continue here. " * 80,
            "[TABLE_START id=80 rows=1]",
            "Management's Discussion and Analysis",
            "[TABLE_END]",
            "Operating segment trends and results. " * 80,
            "Risk Factors and Other Key Information",
            "Risk Factors",
            "The risks in our annual report remain applicable. " * 20,
            "Quantitative and Qualitative Disclosures About Market Risk",
            "Market risk discussion. " * 20,
            "Controls and Procedures",
            "Management evaluated disclosure controls and procedures. " * 20,
            "Exhibits",
            "[TABLE_START id=137 rows=20]",
            "Item Number | Item",
            "Item 1. | Financial Statements | Pages 3 - 25",
            "Item 2. | Management's Discussion and Analysis of Financial Condition and Results of Operations",
            "Item 1A. | Risk Factors | Page 39",
            "[TABLE_END]",
        ]
    )

    sections = find_10q_sections(text)

    assert [section.item_code for section in sections] == ["1", "2", "1A", "3", "4"]
    assert sections[0].text.startswith("[TABLE_START id=9")
    assert "Management's Discussion and Analysis" in sections[1].text
    assert "Item 1. | Financial Statements" not in sections[-1].text
