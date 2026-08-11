from __future__ import annotations

import importlib.util
import io
import json
import zipfile
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


def test_select_best_report_candidate_accepts_chinese_annual_report_with_minguo_year() -> None:
    selected = MODULE.select_best_report_candidate(
        [
            {"url": "https://image.example/upload/R1305000090issuer112英文年報.pdf", "text": ""},
            {"url": "https://image.example/upload/2023-quarterly-report.pdf", "text": ""},
        ],
        fiscal_year=2023,
        report_type="annual_report",
    )

    assert selected is not None
    assert selected["url"].endswith("issuer112英文年報.pdf")


def test_select_best_report_candidate_prefers_integrated_full_report() -> None:
    selected = MODULE.select_best_report_candidate(
        [
            {"url": "https://issuer.example/ir2025_chapter1_en.pdf", "text": "Integrated Report 2025 Chapter 1"},
            {"url": "https://issuer.example/ir2025_all_en.pdf", "text": "Integrated Report 2025"},
        ],
        fiscal_year=2025,
        report_type="integrated_report",
    )

    assert selected is not None
    assert selected["url"].endswith("ir2025_all_en.pdf")


def test_dedupe_candidates_merges_anchor_text_for_same_pdf_url() -> None:
    candidates = MODULE._dedupe_candidates(
        [
            {"url": "https://issuer.example/report.pdf", "text": "", "candidate_source": "html_link"},
            {"url": "https://issuer.example/report.pdf", "text": "Integrated Report 2025", "candidate_source": "html_link_text"},
        ]
    )

    assert candidates == [{"url": "https://issuer.example/report.pdf", "text": "Integrated Report 2025", "candidate_source": "html_link"}]


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
        "task_id": "DOWNLOAD::GLOBALDISC::1211",
        "plan_id": "GLOBALDISC::1211",
        "ticker": "1211.HK",
        "company_name": "BYD Company Limited",
        "disclosure_profile": "hkex_annual_report",
        "fiscal_year": 2024,
        "report_type": "annual_report",
        "download_strategy": "hkexnews_issuer_report_search",
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
    assert executed[0]["primary_download_strategy"] == "hkexnews_issuer_report_search"
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
    cache_dir = tmp_path / "edinet"
    task = {
        "task_id": "DOWNLOAD::GLOBALDISC::8035",
        "plan_id": "GLOBALDISC::8035",
        "ticker": "8035.T",
        "company_name": "Tokyo Electron Limited",
        "disclosure_profile": "jp_edinet_annual_securities_report",
        "fiscal_year": 2024,
        "report_type": "annual_securities_report",
        "download_strategy": "edinet_document_search",
        "download_implementation_status": "blocked_requires_official_api_key",
        "download_blocker": "EDINET API key required.",
        "api_key_env": "EDINET_API_KEY",
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
    assert metadata["api_key_env"] == "EDINET_API_KEY"
    assert metadata["parser_implementation_status"] == "blocked_until_profile_downloader_pass"


def test_select_dart_business_report_prefers_matching_fiscal_year() -> None:
    selected = MODULE.select_dart_business_report(
        [
            {"rcept_no": "20250319000665", "report_nm": "사업보고서 (2024.12)", "rcept_dt": "20250319"},
            {"rcept_no": "20250515000123", "report_nm": "분기보고서 (2025.03)", "rcept_dt": "20250515"},
            {"rcept_no": "20260317000635", "report_nm": "사업보고서 (2025.12)", "rcept_dt": "20260317"},
        ],
        fiscal_year=2025,
        report_type="business_report",
    )

    assert selected is not None
    assert selected["rcept_no"] == "20260317000635"
    assert selected["selection_score"] >= 150


def test_redact_url_masks_dart_api_key() -> None:
    redacted = MODULE.redact_url("https://opendart.fss.or.kr/api/document.xml?crtfc_key=secret&rcept_no=20260317000635")

    assert "secret" not in redacted
    assert "crtfc_key=REDACTED" in redacted
    assert "rcept_no=20260317000635" in redacted


def test_clean_dart_extracted_package_writes_clean_text(tmp_path: Path) -> None:
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    xml_path = extracted / "20260317000635.xml"
    xml_path.write_text("<DOCUMENT><TITLE>사업보고서</TITLE><P>Revenue text</P><script>ignore</script></DOCUMENT>", encoding="utf-8")

    result = MODULE.clean_dart_extracted_package(cache_dir=tmp_path, extracted_paths=[xml_path], rcept_no="20260317000635")

    cleaned_path = tmp_path / "processed" / "20260317000635_cleaned_text.txt"
    assert result["cleaned_text_status"] == "cleaned_text_written"
    assert cleaned_path.exists()
    text = cleaned_path.read_text(encoding="utf-8")
    assert "사업보고서" in text
    assert "Revenue text" in text
    assert "ignore" not in text


def test_execute_download_tasks_downloads_and_cleans_dart_package(tmp_path: Path, monkeypatch) -> None:
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("20260317000635.xml", "<DOCUMENT><TITLE>사업보고서</TITLE><P>Cleaned DART body</P></DOCUMENT>")

    monkeypatch.setenv("DART_API_KEY", "unit-test-key")
    monkeypatch.setattr(MODULE, "resolve_dart_corp_code", lambda task, *, api_key, timeout, user_agent: ("00164779", "unit_test"))
    monkeypatch.setattr(
        MODULE,
        "download_dart_filings_for_year",
        lambda *, api_key, corp_code, fiscal_year, timeout, user_agent: (
            [{"rcept_no": "20260317000635", "report_nm": "사업보고서 (2025.12)", "rcept_dt": "20260317"}],
            "https://opendart.fss.or.kr/api/list.json?crtfc_key=REDACTED",
        ),
    )
    monkeypatch.setattr(
        MODULE,
        "download_dart_document_package",
        lambda *, api_key, rcept_no, timeout, user_agent: {
            "payload": package.getvalue(),
            "headers": {"content-type": "application/x-msdownload;charset=UTF-8"},
            "source_url_logged": "https://opendart.fss.or.kr/api/document.xml?crtfc_key=REDACTED&rcept_no=20260317000635",
        },
    )
    cache_dir = tmp_path / "kr_dart" / "000660_KS" / "2025" / "BUSINESS_REPORT"
    task = {
        "task_id": "DOWNLOAD::GLOBALDISC::000660",
        "plan_id": "GLOBALDISC::000660",
        "ticker": "000660.KS",
        "company_name": "SK hynix Inc.",
        "disclosure_profile": "kr_dart_business_report",
        "fiscal_year": 2025,
        "report_type": "business_report",
        "download_strategy": "official_locator_then_disclosure_search",
        "source_locator_urls": ["https://englishdart.fss.or.kr/"],
        "cache_dir": str(cache_dir),
        "metadata_path": str(cache_dir / "locator_metadata.json"),
    }

    executed, issues = MODULE.execute_download_tasks([task])
    metadata = json.loads((cache_dir / "locator_metadata.json").read_text(encoding="utf-8"))

    assert issues == []
    assert executed[0]["download_status"] == "document_downloaded_cleaned"
    assert executed[0]["document_downloaded"] is True
    assert executed[0]["cleaned_text_char_count"] > 0
    assert "unit-test-key" not in json.dumps(metadata, ensure_ascii=False)
    assert (cache_dir / "20260317000635.zip").exists()
    assert (cache_dir / "processed" / "20260317000635_cleaned_text.txt").exists()


def test_cache_root_and_processed_root_remap_plan_cache_dir(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw_global_public"
    processed_root = tmp_path / "processed_global_public"
    MODULE.configure_disclosure_storage(cache_root=raw_root, processed_root=processed_root)
    try:
        tasks, issues = MODULE.build_global_public_disclosure_download_tasks(
            plan_rows=[
                {
                    "plan_id": "GLOBALDISC::8035_T::JP::2024::ANNUAL_SECURITIES_REPORT",
                    "ticker": "8035.T",
                    "company_name": "Tokyo Electron Limited",
                    "disclosure_profile": "jp_edinet_annual_securities_report",
                    "fiscal_year": 2024,
                    "report_type": "annual_securities_report",
                    "source_locator_urls": ["https://disclosure2.edinet-fsa.go.jp/", "https://www.tel.com/ir/"],
                    "cache_dir": "data/raw_private/global_public_disclosures/jp_edinet/8035_T/2024/ANNUAL_SECURITIES_REPORT",
                }
            ],
            profiles_config={"profiles": {"jp_edinet_annual_securities_report": {"locator_strategy": "edinet_document_search"}}},
        )
        cache_dir = Path(tasks[0]["cache_dir"])

        assert issues == []
        assert cache_dir == raw_root / "jp_edinet" / "8035_T" / "2024" / "ANNUAL_SECURITIES_REPORT"
        assert Path(tasks[0]["metadata_path"]) == cache_dir / "locator_metadata.json"
        assert MODULE._processed_dir_for_cache(cache_dir) == processed_root / "jp_edinet" / "8035_T" / "2024" / "ANNUAL_SECURITIES_REPORT"
    finally:
        MODULE.configure_disclosure_storage(cache_root=None, processed_root=None)
