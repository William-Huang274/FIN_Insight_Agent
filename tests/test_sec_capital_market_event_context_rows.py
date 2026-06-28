from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "data_expansion"
    / "build_sec_capital_market_event_context_rows.py"
)
SPEC = importlib.util.spec_from_file_location("build_sec_capital_market_event_context_rows", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_sec_capital_market_event_rows_split_filing_event_roles() -> None:
    rows, summary = MODULE.build_sec_capital_market_event_context_rows(
        submissions=[
            {
                "cik": "0000320193",
                "name": "Apple Inc.",
                "tickers": ["AAPL"],
                "exchanges": ["Nasdaq"],
                "filings": {
                    "recent": {
                        "accessionNumber": ["0001", "0002", "0003", "0004", "0005"],
                        "filingDate": ["2026-01-05", "2026-01-04", "2026-01-03", "2026-01-02", "2026-01-01"],
                        "reportDate": ["", "", "", "", ""],
                        "acceptanceDateTime": ["", "", "", "", ""],
                        "form": ["4", "S-3ASR", "SC 13G/A", "DEF 14A", "10-K"],
                        "primaryDocument": ["form4.xml", "s3.htm", "sc13g.htm", "def14a.htm", "aapl.htm"],
                        "primaryDocDescription": ["FORM 4", "S-3ASR", "SC 13G/A", "DEF 14A", "10-K"],
                        "items": ["", "", "", "", ""],
                    }
                },
            }
        ],
        generated_at="2026-06-24T00:00:00Z",
    )

    by_role = {row["source_role"]: row for row in rows}
    assert summary["row_count"] == 4
    assert {
        "insider_transaction_filing_event",
        "securities_offering_filing_event",
        "beneficial_ownership_filing_event",
        "proxy_governance_filing_event",
    } <= set(by_role)
    assert by_role["insider_transaction_filing_event"]["source_id"] == "sec_form_3_4_5_metadata"
    assert by_role["securities_offering_filing_event"]["source_id"] == "sec_offering_filing_metadata"
    assert by_role["beneficial_ownership_filing_event"]["source_id"] == "sec_schedule_13d_13g_metadata"
    assert by_role["proxy_governance_filing_event"]["source_id"] == "sec_proxy_governance_metadata"
    assert by_role["securities_offering_filing_event"]["exact_value_authority"] is False
    assert "offering_amount_without_filing_text_or_xml" in by_role["securities_offering_filing_event"]["forbidden_claims"]
    assert "beneficial_ownership_percentage_without_schedule_parser" in by_role["beneficial_ownership_filing_event"]["forbidden_claims"]


def test_sec_capital_market_event_rows_support_targeted_multi_ticker_issuer() -> None:
    rows, _ = MODULE.build_sec_capital_market_event_context_rows(
        submissions=[
            {
                "cik": "0000014693",
                "name": "Brown-Forman Corp",
                "tickers": ["BF-A", "BF-B"],
                "filings": {
                    "recent": {
                        "accessionNumber": ["0001", "0002"],
                        "filingDate": ["2026-01-05", "2026-01-04"],
                        "form": ["DEF 14A", "4"],
                        "primaryDocument": ["def14a.htm", "form4.xml"],
                    }
                },
            }
        ],
        target_tickers=["BF-B"],
        generated_at="2026-06-24T00:00:00Z",
    )

    assert {row["ticker"] for row in rows} == {"BF-B"}
    assert {row["source_role"] for row in rows} == {"proxy_governance_filing_event", "insider_transaction_filing_event"}


def test_fetch_missing_sec_submissions_materializes_only_sec_mappable_tickers(tmp_path, monkeypatch) -> None:
    calls: list[str] = []

    def fake_download(url: str, *, user_agent: str) -> dict[str, object]:
        calls.append(url)
        return {
            "cik": "0000001234",
            "name": "Test Issuer",
            "tickers": ["TEST"],
            "filings": {"recent": {"form": ["DEF 14A"], "accessionNumber": ["0001"], "filingDate": ["2026-01-01"], "primaryDocument": ["def14a.htm"]}},
        }

    monkeypatch.setattr(MODULE, "_download_json", fake_download)
    ledger = MODULE.fetch_missing_submissions_for_universe(
        submissions_dir=tmp_path,
        company_universe_rows=[{"ticker": "TEST"}, {"ticker": "000660.KS"}],
        company_ticker_map={"TEST": "0000001234"},
        request_sleep_seconds=0,
    )

    assert ledger["fetched_count"] == 1
    assert ledger["non_sec_mappable_tickers"] == ["000660.KS"]
    assert calls == ["https://data.sec.gov/submissions/CIK0000001234.json"]
    assert (tmp_path / "CIK0000001234.json").exists()
