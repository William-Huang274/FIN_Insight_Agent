from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "data_expansion" / "download_global_public_disclosures.py"
SPEC = importlib.util.spec_from_file_location("download_global_public_disclosures", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_global_public_download_tasks_are_profile_dispatched() -> None:
    tasks, issues = MODULE.build_global_public_disclosure_download_tasks(
        plan_rows=[
            {
                "plan_id": "GLOBALDISC::005930_KS::KR_DART_BUSINESS_REPORT::2024::ANNUAL_REPORT",
                "ticker": "005930.KS",
                "issuer_id": "KR-005930",
                "exchange_symbol": "005930",
                "company_name": "Samsung Electronics Co., Ltd.",
                "disclosure_profile": "kr_dart_business_report",
                "locator_strategy": "official_locator_then_disclosure_search",
                "parser_profile": "kr_dart_business_report_v0_1",
                "fiscal_year": 2024,
                "report_type": "annual_report",
                "source_tier": "primary_company_disclosure",
                "source_family": "global_public_annual_report",
                "source_locator_urls": ["https://englishdart.fss.or.kr/"],
                "preferred_source_kinds": ["regulator"],
                "cache_dir": "data/raw_private/global_public_disclosures/kr_dart/005930_KS/2024/ANNUAL_REPORT",
                "source_boundary": "primary_company_disclosure_not_news_lead",
            }
        ],
        profiles_config={"profiles": {"kr_dart_business_report": {"locator_strategy": "official_locator_then_disclosure_search"}}},
    )

    assert issues == []
    assert len(tasks) == 1
    assert tasks[0]["download_strategy"] == "official_locator_then_disclosure_search"
    assert tasks[0]["download_status"] == "dry_run_ready"
    assert tasks[0]["document_downloaded"] is False
    assert tasks[0]["profile_dispatch_status"] == "ready_for_profile_strategy"


def test_global_public_download_tasks_report_missing_profile() -> None:
    tasks, issues = MODULE.build_global_public_disclosure_download_tasks(
        plan_rows=[
            {
                "plan_id": "GLOBALDISC::UNKNOWN::MISSING::2024::ANNUAL_REPORT",
                "ticker": "UNKNOWN.KS",
                "disclosure_profile": "missing_profile",
                "source_locator_urls": ["https://example.com/"],
            }
        ],
        profiles_config={"profiles": {}},
    )

    assert tasks == []
    assert issues == [{"type": "missing_profile", "plan_id": "GLOBALDISC::UNKNOWN::MISSING::2024::ANNUAL_REPORT", "ticker": "UNKNOWN.KS", "disclosure_profile": "missing_profile"}]


def test_materialize_locator_metadata_writes_only_locator_file(tmp_path: Path) -> None:
    metadata_path = tmp_path / "locator_metadata.json"
    materialized = MODULE.materialize_locator_metadata(
        [
            {
                "task_id": "DOWNLOAD::GLOBALDISC::005930",
                "plan_id": "GLOBALDISC::005930",
                "ticker": "005930.KS",
                "company_name": "Samsung Electronics Co., Ltd.",
                "disclosure_profile": "kr_dart_business_report",
                "fiscal_year": 2024,
                "report_type": "annual_report",
                "source_locator_urls": ["https://englishdart.fss.or.kr/"],
                "metadata_path": str(metadata_path),
            }
        ]
    )

    assert metadata_path.exists()
    assert materialized[0]["download_status"] == "locator_metadata_written"
    assert materialized[0]["document_downloaded"] is False


def test_select_best_report_candidate_prefers_matching_year_and_annual_report() -> None:
    selected = MODULE.select_best_report_candidate(
        [
            {"url": "https://example.com/2023-annual-report.pdf", "display_name": "Annual Report 2023"},
            {"url": "https://example.com/2024-annual-report.pdf", "display_name": "Annual Report 2024"},
            {"url": "https://example.com/2024-agm.pdf", "display_name": "Annual General Meeting 2024"},
            {"url": "https://example.com/2024-sustainability-at-example.pdf", "display_name": "Sustainability at Example, Supplementing the Annual Report 2024"},
        ],
        fiscal_year=2024,
        report_type="annual_report",
    )

    assert selected is not None
    assert selected["url"] == "https://example.com/2024-annual-report.pdf"
    assert selected["score"] > 30


def test_select_best_report_candidate_rejects_interim_pdf_for_annual_report() -> None:
    selected = MODULE.select_best_report_candidate(
        [
            {"url": "https://example.com/2024_Half_Interim_Report.pdf", "display_name": "2024 Half Interim Report"},
            {"url": "https://example.com/2024-business-report.pdf", "display_name": "Business Report 2024"},
        ],
        fiscal_year=2024,
        report_type="annual_report",
    )

    assert selected is not None
    assert selected["url"] == "https://example.com/2024-business-report.pdf"


def test_candidate_links_from_json_text_extracts_asset_dam_pdf_url() -> None:
    candidates = MODULE._candidate_links_from_json_text(
        "https://www.infineon.com/dataApi/report.json",
        """
        {
          "documents": [
            {
              "documentDisplayName": "Annual Report 2024 with the Group Consolidated Financial Statements",
              "filename": "2024-infineon-annual-report-01-00-en.pdf",
              "assetDamPath": "/documents/corporate/investors/annual-reports/2024",
              "releasedDate": "Nov 26, 2024"
            }
          ]
        }
        """,
    )

    assert candidates == [
        {
            "url": "https://www.infineon.com/assets/row/public/documents/corporate/investors/annual-reports/2024/2024-infineon-annual-report-01-00-en.pdf",
            "text": "",
            "display_name": "Annual Report 2024 with the Group Consolidated Financial Statements",
            "file_name": "2024-infineon-annual-report-01-00-en.pdf",
            "released_date": "Nov 26, 2024",
            "source_stage": "api_json",
            "candidate_source": "document_json",
        }
    ]


def test_candidate_links_from_json_text_keeps_full_asset_dam_pdf_path() -> None:
    candidates = MODULE._candidate_links_from_json_text(
        "https://www.infineon.com/dataApi/report.json",
        """
        {
          "documents": [
            {
              "documentDisplayName": "Annual Report 2023 with the Group Consolidated Financial Statements",
              "filename": "2023-infineon-annual-report-v01-00-en.pdf",
              "assetDamPath": "/assets/row/public/documents/corporate/investors/annual-reports/2023/2023-infineon-annual-report-v01-00-en.pdf",
              "releasedDate": "Nov 24, 2023"
            }
          ]
        }
        """,
    )

    assert candidates[0]["url"] == "https://www.infineon.com/assets/row/public/documents/corporate/investors/annual-reports/2023/2023-infineon-annual-report-v01-00-en.pdf"


def test_execute_download_tasks_reuses_locator_candidates_for_same_ir_page(tmp_path: Path, monkeypatch) -> None:
    calls = {"discover": 0}

    def fake_discover(task, *, timeout, user_agent):
        calls["discover"] += 1
        return [
            {"url": "https://issuer.example/reports/2023-annual-report.pdf", "display_name": "Annual Report 2023", "file_name": "2023-annual-report.pdf"},
            {"url": "https://issuer.example/reports/2024-annual-report.pdf", "display_name": "Annual Report 2024", "file_name": "2024-annual-report.pdf"},
        ]

    def fake_fetch_bytes(url, *, timeout, user_agent, accept=""):
        return b"%PDF-1.4 test", {"content-type": "application/pdf"}

    monkeypatch.setattr(MODULE, "discover_company_ir_report_candidates", fake_discover)
    monkeypatch.setattr(MODULE, "_fetch_bytes", fake_fetch_bytes)
    tasks = []
    for fiscal_year in (2023, 2024):
        cache_dir = tmp_path / str(fiscal_year)
        tasks.append(
            {
                "task_id": f"DOWNLOAD::TEST::{fiscal_year}",
                "plan_id": f"GLOBALDISC::TEST::{fiscal_year}",
                "ticker": "TEST.DE",
                "company_name": "Test AG",
                "disclosure_profile": "eu_regulated_annual_report",
                "fiscal_year": fiscal_year,
                "report_type": "annual_report",
                "download_strategy": "company_ir_official_report_download",
                "source_locator_urls": ["https://issuer.example/investor/"],
                "cache_dir": str(cache_dir),
                "metadata_path": str(cache_dir / "locator_metadata.json"),
            }
        )

    executed, issues = MODULE.execute_download_tasks(tasks)

    assert issues == []
    assert calls["discover"] == 1
    assert [row["download_status"] for row in executed] == ["document_downloaded", "document_downloaded"]
    assert executed[0]["document_url"].endswith("2023-annual-report.pdf")
    assert executed[1]["document_url"].endswith("2024-annual-report.pdf")


def test_execute_download_tasks_can_use_company_ir_fallback_for_pending_profile(tmp_path: Path, monkeypatch) -> None:
    def fake_discover(task, *, timeout, user_agent):
        return [
            {"url": "https://issuer.example/reports/2024-annual-report.pdf", "display_name": "Annual Report 2024", "file_name": "2024-annual-report.pdf"}
        ]

    def fake_fetch_bytes(url, *, timeout, user_agent, accept=""):
        return b"%PDF-1.4 fallback", {"content-type": "application/pdf"}

    monkeypatch.setattr(MODULE, "discover_company_ir_report_candidates", fake_discover)
    monkeypatch.setattr(MODULE, "_fetch_bytes", fake_fetch_bytes)
    cache_dir = tmp_path / "fallback"
    task = {
        "task_id": "DOWNLOAD::GLOBALDISC::005930",
        "plan_id": "GLOBALDISC::005930",
        "ticker": "005930.KS",
        "company_name": "Samsung Electronics Co., Ltd.",
        "disclosure_profile": "kr_dart_business_report",
        "fiscal_year": 2024,
        "report_type": "annual_report",
        "download_strategy": "official_locator_then_disclosure_search",
        "preferred_source_kinds": ["regulator", "company_ir"],
        "source_locator_urls": ["https://englishdart.fss.or.kr/", "https://issuer.example/investor/"],
        "cache_dir": str(cache_dir),
        "metadata_path": str(cache_dir / "locator_metadata.json"),
    }

    blocked, blocked_issues = MODULE.execute_download_tasks([task])
    executed, issues = MODULE.execute_download_tasks([task], allow_company_ir_fallback=True)

    assert blocked[0]["download_status"] == "profile_strategy_not_implemented"
    assert blocked_issues[0]["type"] == "profile_strategy_not_implemented"
    assert issues == []
    assert executed[0]["download_status"] == "document_downloaded"
    assert executed[0]["primary_download_strategy"] == "official_locator_then_disclosure_search"
    assert executed[0]["download_strategy"] == "company_ir_official_report_fallback"
    assert executed[0]["source_policy"] == "profile_strategy_pending_company_ir_fallback"


def test_download_company_ir_official_report_writes_no_candidate_metadata(tmp_path: Path, monkeypatch) -> None:
    def fake_discover(task, *, timeout, user_agent):
        return [{"url": "https://issuer.example/2024-half-interim.pdf", "display_name": "2024 Half Interim Report"}]

    monkeypatch.setattr(MODULE, "discover_company_ir_report_candidates", fake_discover)
    metadata_path = tmp_path / "locator_metadata.json"

    result, issue = MODULE.download_company_ir_official_report(
        {
            "task_id": "DOWNLOAD::TEST",
            "plan_id": "GLOBALDISC::TEST",
            "ticker": "TEST.KS",
            "company_name": "Test Co",
            "disclosure_profile": "kr_dart_business_report",
            "fiscal_year": 2024,
            "report_type": "annual_report",
            "download_strategy": "company_ir_official_report_fallback",
            "source_locator_urls": ["https://issuer.example/investor/"],
            "cache_dir": str(tmp_path),
            "metadata_path": str(metadata_path),
        }
    )

    assert result["download_status"] == "no_matching_document_candidate"
    assert issue and issue["type"] == "no_matching_document_candidate"
    assert metadata_path.exists()
    assert "no_matching_document_candidate" in metadata_path.read_text(encoding="utf-8")


def test_execute_download_tasks_records_profile_specific_blocker_metadata(tmp_path: Path) -> None:
    cache_dir = tmp_path / "dart"
    task = {
        "task_id": "DOWNLOAD::GLOBALDISC::005930",
        "plan_id": "GLOBALDISC::005930",
        "ticker": "005930.KS",
        "company_name": "Samsung Electronics Co., Ltd.",
        "disclosure_profile": "kr_dart_business_report",
        "fiscal_year": 2024,
        "report_type": "business_report",
        "download_strategy": "official_locator_then_disclosure_search",
        "download_implementation_status": "blocked_requires_official_api_key",
        "download_blocker": "DART Open API key required.",
        "api_key_env": "DART_API_KEY",
        "parser_implementation_status": "blocked_until_profile_downloader_pass",
        "parser_blocker": "Parser requires downloaded document.",
        "source_locator_urls": ["https://englishdart.fss.or.kr/"],
        "cache_dir": str(cache_dir),
        "metadata_path": str(cache_dir / "locator_metadata.json"),
    }

    executed, issues = MODULE.execute_download_tasks([task])
    metadata = json.loads((cache_dir / "locator_metadata.json").read_text(encoding="utf-8"))

    assert executed[0]["download_status"] == "blocked_requires_official_api_key"
    assert issues[0]["type"] == "blocked_requires_official_api_key"
    assert metadata["download_status"] == "blocked_requires_official_api_key"
    assert metadata["api_key_env"] == "DART_API_KEY"
    assert metadata["parser_implementation_status"] == "blocked_until_profile_downloader_pass"
