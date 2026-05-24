from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from connectors import SecEdgarConnector, SecEdgarConnectorError, SecFilingManifestRecord  # noqa: E402
from evidence import build_evidence_from_chunks  # noqa: E402
from evidence.schema import EvidenceObject  # noqa: E402
from ingestion import build_8k_earnings_chunks  # noqa: E402
from sec_agent.query_contract import validate_query_contract  # noqa: E402
from sec_agent.tool_harness import SecAgentToolHarness  # noqa: E402
from sec_agent.context_api import _default_source_policy  # noqa: E402


def _load_8k_manifest_module():
    path = REPO_ROOT / "scripts" / "build_sec_8k_earnings_manifest.py"
    spec = importlib.util.spec_from_file_location("build_sec_8k_earnings_manifest_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_interactive_module():
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_8k_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_evidence_object_accepts_8k_earnings_source_tier() -> None:
    evidence = EvidenceObject(
        evidence_id="8K_EARNINGS::MSFT::000000::EX99_1::0001",
        source_type="8-K",
        source_tier="company_authored_unaudited_sec_filing",
        ticker="MSFT",
        fiscal_year=2026,
        evidence_type="management_commentary",
        text="Microsoft reported quarterly results in an earnings release.",
    )

    assert evidence.source_tier == "company_authored_unaudited_sec_filing"
    assert evidence.source_type == "8-K"


def test_query_contract_recognizes_mixed_with_8k_earnings_policy() -> None:
    inventory = {
        "inventory_digest": "inv-8k",
        "companies": [
            {
                "ticker": "MSFT",
                "company": "Microsoft",
                "category": "mega-cap software/cloud",
                "filings": [
                    {"year": 2025, "form_type": "10-K", "source_tier": "primary_sec_filing"},
                    {"year": 2026, "form_type": "10-Q", "source_tier": "primary_sec_filing"},
                    {
                        "year": 2026,
                        "form_type": "8-K",
                        "source_tier": "company_authored_unaudited_sec_filing",
                    },
                ],
            }
        ],
        "categories": [{"category": "mega-cap software/cloud", "tickers": ["MSFT"]}],
    }
    contract = {
        "task_type": "general_sec_financial_question",
        "search_scope_tickers": ["MSFT"],
        "focus_tickers": ["MSFT"],
        "years": [2025, 2026],
        "filing_types": ["10-K", "10-Q", "8-K"],
        "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
        "metric_families": ["cloud_revenue"],
        "decomposed_tasks": [
            {
                "task_id": "cloud_management_commentary",
                "question_zh": "Use 10-Q values and 8-K earnings release commentary.",
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

    assert clean["source_policy"] == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"
    assert clean["source_tiers"] == ["primary_sec_filing", "company_authored_unaudited_sec_filing"]
    assert any("8-K earnings-release evidence" in caveat for caveat in clean["required_caveats"])
    assert result["report"]["status"] == "pass"


def test_context_and_harness_accept_mixed_with_8k_policy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SEC_AGENT_SOURCE_POLICY", "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS")

    assert _default_source_policy() == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"

    harness = SecAgentToolHarness(session_root=tmp_path)
    result = harness.start_memo_analysis(
        query="结合MSFT最新10-Q和8-K业绩新闻稿解释云业务表现",
        user_id="u1",
        tenant_id="t1",
        session_id="s1",
        source_policy="SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
        execute=False,
    )

    assert result.status == "planned"
    session_path = tmp_path / "s1" / "session_state.json"
    assert session_path.exists()
    assert "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS" in session_path.read_text(encoding="utf-8")


def test_runtime_case_adds_8k_source_boundary_gate() -> None:
    interactive = _load_interactive_module()
    case = interactive._build_case(
        "结合10-Q和8-K业绩新闻稿解释MSFT云业务表现",
        ["MSFT"],
        [2026],
        "run_8k",
        {
            "task_type": "general_sec_financial_question",
            "focus_tickers": ["MSFT"],
            "filing_types": ["10-K", "10-Q", "8-K"],
            "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
            "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
            "required_caveats": [
                "8-K earnings-release evidence is company-authored unaudited management material."
            ],
        },
    )

    assert "Label 8-K earnings-release evidence as company-authored unaudited material." in case["gold_points"]
    assert any("Do not treat company-authored 8-K" in trap for trap in case["hallucination_traps"])
    assert case["required_caveats"][0]["required"] is True


def test_connector_selects_earnings_release_exhibit_99_1(monkeypatch, tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "MICROSOFT CORP",
        "filings": {
            "recent": {
                "form": ["8-K", "8-K"],
                "accessionNumber": ["0000789019-26-000111", "0000789019-26-000222"],
                "primaryDocument": ["msft-20260424.htm", "msft-20260201.htm"],
                "filingDate": ["2026-04-24", "2026-02-01"],
                "reportDate": ["", ""],
                "acceptanceDateTime": ["2026-04-24T20:00:00.000Z", "2026-02-01T20:00:00.000Z"],
                "primaryDocDescription": ["8-K", "8-K"],
                "items": ["2.02,9.01", "8.01,9.01"],
            }
        },
    }
    detail_index = {
        "directory": {
            "item": [
                {"name": "msft-20260424.htm", "type": "text/html"},
                {"name": "ex991.htm", "type": "text/html"},
                {"name": "ex992.htm", "type": "text/html"},
            ]
        }
    }
    primary_html = """
    <html><body><table>
      <tr><td>EX-99.1</td><td><a href="ex991.htm">ex991.htm</a></td><td>Press Release dated April 24, 2026 announcing quarterly financial results</td></tr>
      <tr><td>EX-99.2</td><td><a href="ex992.htm">ex992.htm</a></td><td>Investor presentation</td></tr>
    </table></body></html>
    """

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(connector, "_request_json", lambda url: detail_index)
    monkeypatch.setattr(connector, "_request_text", lambda url: primary_html)

    filing = connector.find_earnings_release_8k("789019", 2026)

    assert filing["form_type"] == "8-K"
    assert filing["source_tier"] == "company_authored_unaudited_sec_filing"
    assert filing["source_policy"] == "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS"
    assert filing["accession_number"] == "0000789019-26-000111"
    assert filing["exhibit_document"] == "ex991.htm"
    assert filing["exhibit_type"] == "EX-99.1"
    assert "Press Release" in filing["exhibit_description"]
    assert filing["earnings_release_candidate_reason"]
    assert filing["exhibit_url"].endswith("/000078901926000111/ex991.htm")


def test_connector_downloads_8k_earnings_release_exhibit(tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    filing_meta = {
        "company": "MICROSOFT CORP",
        "cik": "0000789019",
        "form_type": "8-K",
        "source_type": "8-K",
        "source_tier": "company_authored_unaudited_sec_filing",
        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
        "filing_year": 2026,
        "fiscal_year": 2026,
        "fiscal_year_source": "filing_year",
        "filing_date": "2026-04-24",
        "report_date": "",
        "period_end": "2026-04-24",
        "period_type": "current_report",
        "accession_number": "0000789019-26-000111",
        "primary_document": "msft-20260424.htm",
        "filing_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000111/msft-20260424.htm",
        "exhibit_document": "ex991.htm",
        "exhibit_type": "EX-99.1",
        "exhibit_description": "Press Release dated April 24, 2026 announcing quarterly financial results",
        "exhibit_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000111/ex991.htm",
        "_prefetched_primary_html": "<html>primary</html>",
        "_prefetched_exhibit_html": "<html>earnings release</html>",
    }

    result = connector.download_earnings_release_8k(
        filing_meta,
        ticker="MSFT",
        category="mega-cap software/cloud",
        category_slug="mega-cap_software_cloud",
    )

    exhibit_path = Path(result["local_exhibit_path"])
    metadata_path = Path(result["local_metadata_path"])
    assert exhibit_path.exists()
    assert metadata_path.exists()
    assert exhibit_path.read_text(encoding="utf-8") == "<html>earnings release</html>"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["ticker"] == "MSFT"
    assert metadata["source_tier"] == "company_authored_unaudited_sec_filing"
    assert "_prefetched_exhibit_html" not in metadata


def test_connector_does_not_select_generic_9_01_press_release(monkeypatch, tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "MICROSOFT CORP",
        "filings": {
            "recent": {
                "form": ["8-K"],
                "accessionNumber": ["0001193125-26-224155"],
                "primaryDocument": ["d125909d8k.htm"],
                "filingDate": ["2026-05-14"],
                "reportDate": ["2026-05-13"],
                "acceptanceDateTime": ["2026-05-14T20:28:48.000Z"],
                "primaryDocDescription": ["8-K"],
                "items": ["5.02,9.01"],
            }
        },
    }
    primary_html = """
    <html><body><table>
      <tr><td>EX-99.1</td><td><a href="d125909dex991.htm">d125909dex991.htm</a></td><td>Press Release of Microsoft Corporation dated May 14, 2026</td></tr>
    </table></body></html>
    """

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(connector, "_request_json", lambda url: {"directory": {"item": []}})
    monkeypatch.setattr(connector, "_request_text", lambda url: primary_html)

    try:
        connector.find_earnings_release_8k("789019", 2026)
    except SecEdgarConnectorError as exc:
        assert "No earnings-release 8-K exhibit found" in str(exc)
    else:
        raise AssertionError("expected SecEdgarConnectorError")


def test_connector_rejects_8k_without_earnings_release_exhibit(monkeypatch, tmp_path: Path) -> None:
    connector = SecEdgarConnector(user_agent="FinSight-Agent/0.1 test@example.com", cache_dir=tmp_path)
    submissions = {
        "name": "MICROSOFT CORP",
        "filings": {
            "recent": {
                "form": ["8-K"],
                "accessionNumber": ["0000789019-26-000111"],
                "primaryDocument": ["msft-20260424.htm"],
                "filingDate": ["2026-04-24"],
                "reportDate": [""],
                "acceptanceDateTime": ["2026-04-24T20:00:00.000Z"],
                "primaryDocDescription": ["8-K"],
                "items": ["2.02,9.01"],
            }
        },
    }
    detail_index = {"directory": {"item": [{"name": "ex991.htm", "type": "text/html"}]}}
    primary_html = """
    <html><body><table>
      <tr><td>EX-99.1</td><td><a href="ex991.htm">ex991.htm</a></td><td>Investor presentation</td></tr>
    </table></body></html>
    """

    monkeypatch.setattr(connector, "get_company_submissions", lambda cik: submissions)
    monkeypatch.setattr(connector, "_request_json", lambda url: detail_index)
    monkeypatch.setattr(connector, "_request_text", lambda url: primary_html)

    try:
        connector.find_earnings_release_8k("789019", 2026)
    except SecEdgarConnectorError as exc:
        assert "No earnings-release 8-K exhibit found" in str(exc)
    else:
        raise AssertionError("expected SecEdgarConnectorError")


def test_8k_earnings_manifest_builder_collects_exhibit_paths(tmp_path: Path) -> None:
    manifest = _load_8k_manifest_module()
    cache_root = tmp_path / "sec_8k_earnings"
    filing_dir = cache_root / "2026" / "mega-cap_software_cloud" / "MSFT" / "000078901926000111"
    filing_dir.mkdir(parents=True)
    exhibit_path = filing_dir / "ex991.htm"
    exhibit_path.write_text("<html>Microsoft quarterly financial results</html>", encoding="utf-8")
    metadata_path = filing_dir / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "ticker": "MSFT",
                "company": "MICROSOFT CORP",
                "cik": "0000789019",
                "fiscal_year": 2026,
                "fiscal_year_source": "filing_year",
                "category": "mega-cap software/cloud",
                "category_slug": "mega-cap_software_cloud",
                "form_type": "8-K",
                "source_type": "8-K",
                "source_tier": "company_authored_unaudited_sec_filing",
                "filing_date": "2026-04-24",
                "report_date": "",
                "period_end": "2026-04-24",
                "period_type": "current_report",
                "fiscal_period_source": "not_applicable",
                "filing_items": "2.02,9.01",
                "accession_number": "0000789019-26-000111",
                "primary_document": "msft-20260424.htm",
                "filing_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000111/msft-20260424.htm",
                "exhibit_document": "ex991.htm",
                "local_html_path": "ex991.htm",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    records = manifest.collect_8k_earnings_manifest(
        cache_root,
        years=[2026],
        tickers=["MSFT"],
        categories=["mega-cap_software_cloud"],
    )

    assert len(records) == 1
    record = records[0]
    assert record.form_type == "8-K"
    assert record.source_tier == "company_authored_unaudited_sec_filing"
    assert record.period_type == "current_report"
    assert record.html_path == str(exhibit_path.resolve())
    assert record.metadata_path == str(metadata_path)


def test_8k_manifest_builder_rejects_cached_non_202_item_press_release(tmp_path: Path) -> None:
    manifest = _load_8k_manifest_module()
    cache_root = tmp_path / "sec_8k_earnings"
    filing_dir = cache_root / "2026" / "mega-cap_software_cloud" / "MSFT" / "000119312526224155"
    filing_dir.mkdir(parents=True)
    (filing_dir / "ex991.htm").write_text("<html>Generic press release</html>", encoding="utf-8")
    (filing_dir / "metadata.json").write_text(
        json.dumps(
            {
                "ticker": "MSFT",
                "company": "MICROSOFT CORP",
                "fiscal_year": 2026,
                "category": "mega-cap software/cloud",
                "category_slug": "mega-cap_software_cloud",
                "form_type": "8-K",
                "source_type": "8-K",
                "source_tier": "company_authored_unaudited_sec_filing",
                "filing_items": "5.02,9.01",
                "period_type": "current_report",
                "accession_number": "0001193125-26-224155",
                "exhibit_document": "ex991.htm",
                "local_html_path": "ex991.htm",
            }
        ),
        encoding="utf-8",
    )

    records = manifest.collect_8k_earnings_manifest(cache_root, years=[2026], tickers=["MSFT"])

    assert records == []


def test_8k_earnings_parser_builds_source_bounded_chunks_and_evidence(tmp_path: Path) -> None:
    html_path = tmp_path / "ex991.htm"
    html_path.write_text(
        """
        <html><body>
        <h1>Microsoft Reports Fiscal 2026 First Quarter Results</h1>
        <p>Microsoft Corp. today announced results for the quarter ended March 31, 2026.</p>
        <h2>Business Highlights</h2>
        <p>Cloud revenue increased as Azure and AI services remained in demand.</p>
        <table>
          <tr><th>Metric</th><th>Amount</th></tr>
          <tr><td>Revenue</td><td>$70.0 billion</td></tr>
        </table>
        <h2>Forward-Looking Statements</h2>
        <p>This release contains forward-looking statements about future business conditions.</p>
        <h2>Non-GAAP Reconciliation</h2>
        <p>Non-GAAP operating income excludes certain items and should not be viewed as audited.</p>
        </body></html>
        """,
        encoding="utf-8",
    )
    record = SecFilingManifestRecord(
        ticker="MSFT",
        company="MICROSOFT CORP",
        cik="0000789019",
        fiscal_year=2026,
        fiscal_year_source="filing_year",
        category="mega-cap software/cloud",
        category_slug="mega-cap_software_cloud",
        form_type="8-K",
        source_type="8-K",
        source_tier="company_authored_unaudited_sec_filing",
        filing_date="2026-04-24",
        period_end="2026-04-24",
        period_type="current_report",
        fiscal_period_source="not_applicable",
        accession_number="0000789019-26-000111",
        primary_document="msft-20260424.htm",
        filing_url="https://www.sec.gov/Archives/edgar/data/789019/000078901926000111/msft-20260424.htm",
        html_path=str(html_path),
        metadata_path=str(tmp_path / "metadata.json"),
        metadata={
            "exhibit_document": "ex991.htm",
            "exhibit_type": "EX-99.1",
            "exhibit_description": "Press Release dated April 24, 2026 announcing quarterly financial results",
            "exhibit_url": "https://www.sec.gov/Archives/edgar/data/789019/000078901926000111/ex991.htm",
        },
    )

    chunks = build_8k_earnings_chunks(record, target_words=35, overlap_words=5, min_words=5)
    evidence = build_evidence_from_chunks(chunks)

    assert chunks
    assert all(chunk.form_type == "8-K" for chunk in chunks)
    assert all(chunk.source_tier == "company_authored_unaudited_sec_filing" for chunk in chunks)
    assert all(chunk.metadata["exclude_from_exact_value_ledger"] is True for chunk in chunks)
    assert any(chunk.contains_table for chunk in chunks)
    assert chunks[0].chunk_id.startswith("8K_EARNINGS::MSFT::000078901926000111::EX991HTM::")
    assert chunks[0].metadata["reported_period_end"] == "2026-03-31"
    assert chunks[0].metadata["reported_fiscal_period"] == "Q1"
    assert chunks[0].metadata["reported_fiscal_year"] == 2026
    assert evidence[0].evidence_type == "management_commentary"
    assert evidence[0].source_url.endswith("/ex991.htm")
    assert evidence[0].metadata["source_boundary"] == "company_authored_unaudited_sec_filing"
