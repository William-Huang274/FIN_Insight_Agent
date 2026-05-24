from __future__ import annotations

import json
import os
import re
import time
import html as html_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


class SecEdgarConnectorError(RuntimeError):
    pass


class SecEdgarConnector:
    COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    SUBMISSIONS_URL_TEMPLATE = "https://data.sec.gov/submissions/CIK{cik}.json"
    SUBMISSIONS_FILE_URL_TEMPLATE = "https://data.sec.gov/submissions/{file_name}"
    ARCHIVES_BASE_URL = "https://www.sec.gov/Archives/edgar/data"

    def __init__(
        self,
        user_agent: str | None = None,
        cache_dir: str | Path = "data/raw_private/sec",
        log_path: str | Path = "data/logs/download_log.jsonl",
        rate_limit: float = 2.0,
        timeout: int = 30,
    ) -> None:
        self.user_agent = user_agent or os.getenv("SEC_USER_AGENT")
        if not self.user_agent:
            raise SecEdgarConnectorError(
                "SEC_USER_AGENT is required. Set it in the environment or pass "
                "user_agent='FinSight-Agent/0.1 your.email@example.com'."
            )

        self.cache_dir = Path(cache_dir)
        self.log_path = Path(log_path)
        self.timeout = timeout
        self.min_interval = 1.0 / rate_limit if rate_limit > 0 else 0.0
        self._last_request_ts = 0.0

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "application/json,text/html,*/*",
            }
        )

    def get_cik(self, ticker: str) -> str:
        ticker_upper = ticker.upper()
        data = self._get_company_tickers()
        for row in data.values():
            if row.get("ticker", "").upper() == ticker_upper:
                return f"{int(row['cik_str']):010d}"
        raise SecEdgarConnectorError(f"Ticker not found in SEC company tickers: {ticker}")

    def get_company_submissions(self, cik: str) -> dict[str, Any]:
        normalized_cik = self._normalize_cik(cik)
        cache_path = self.cache_dir / "_reference" / "submissions" / f"CIK{normalized_cik}.json"
        if cache_path.exists():
            return self._read_json(cache_path)

        url = self.SUBMISSIONS_URL_TEMPLATE.format(cik=normalized_cik)
        data = self._request_json(url)
        self._write_json(cache_path, data)
        return data

    def find_filing(self, cik: str, form_type: str, year: int) -> dict[str, Any]:
        normalized_cik = self._normalize_cik(cik)
        submissions = self.get_company_submissions(normalized_cik)
        recent = submissions.get("filings", {}).get("recent", {})
        selected_block = recent
        selected_match = self._find_filing_match(
            recent, cik=normalized_cik, form_type=form_type, fiscal_year=year
        )

        if selected_match is None:
            for file_info in submissions.get("filings", {}).get("files", []):
                file_name = file_info.get("name")
                if not file_name:
                    continue
                historical_block = self.get_company_submission_file(
                    normalized_cik, file_name=file_name
                )
                selected_match = self._find_filing_match(
                    historical_block,
                    cik=normalized_cik,
                    form_type=form_type,
                    fiscal_year=year,
                )
                if selected_match is not None:
                    selected_block = historical_block
                    break

        if selected_match is None:
            raise SecEdgarConnectorError(
                f"No {form_type} filing found for CIK {normalized_cik} and fiscal year {year}."
            )

        selected_idx = int(selected_match["idx"])
        accession_number = self._get_recent_value(
            selected_block, "accessionNumber", selected_idx
        )
        primary_document = self._get_recent_value(
            selected_block, "primaryDocument", selected_idx
        )
        filing_url = self._build_filing_url(normalized_cik, accession_number, primary_document)
        report_date = self._get_recent_value(selected_block, "reportDate", selected_idx)
        period = self._filing_period_metadata(
            form_type=form_type,
            report_date=report_date,
            fiscal_period_focus=selected_match.get("document_fiscal_period_focus"),
            fiscal_year_focus=selected_match.get("document_fiscal_year_focus"),
        )
        resolved_fiscal_year = int(period.get("fiscal_year") or year)

        return {
            "ticker": None,
            "company": submissions.get("name"),
            "cik": normalized_cik,
            "form_type": form_type,
            "source_tier": "primary_sec_filing",
            "requested_fiscal_year": year,
            "fiscal_year": resolved_fiscal_year,
            "filing_date": self._get_recent_value(selected_block, "filingDate", selected_idx),
            "report_date": report_date,
            **period,
            "acceptance_datetime": self._get_recent_value(
                selected_block, "acceptanceDateTime", selected_idx
            ),
            "accession_number": accession_number,
            "primary_document": primary_document,
            "document_description": self._get_recent_value(
                selected_block, "primaryDocDescription", selected_idx
            ),
            "filing_url": filing_url,
            "_prefetched_html": selected_match.get("html"),
        }

    def download_filing_html(
        self,
        filing_meta: dict[str, Any],
        ticker: str,
        year: int | None = None,
        category: str | None = None,
        category_slug: str | None = None,
    ) -> dict[str, Any]:
        fiscal_year = int(filing_meta.get("fiscal_year") or year)
        ticker_upper = ticker.upper()
        form_type = filing_meta["form_type"]
        resolved_category = category or "uncategorized"
        resolved_category_slug = self._slugify_category(
            category_slug or resolved_category
        )
        output_dir = (
            self.cache_dir
            / str(fiscal_year)
            / resolved_category_slug
            / ticker_upper
        )
        html_path = output_dir / f"{form_type}.html"
        metadata_path = output_dir / f"{form_type}.metadata.json"

        prefetched_html = str(filing_meta.get("_prefetched_html") or "")
        public_filing_meta = {
            key: value for key, value in filing_meta.items() if not str(key).startswith("_")
        }
        result = {
            **public_filing_meta,
            "ticker": ticker_upper,
            "category": resolved_category,
            "category_slug": resolved_category_slug,
            "cache_layout": "year/category/ticker",
            "local_html_path": str(html_path),
            "local_metadata_path": str(metadata_path),
        }

        if html_path.exists() and metadata_path.exists():
            cached_metadata = self._read_json(metadata_path)
            if self._cached_filing_matches_request(
                cached_metadata, public_filing_meta
            ) and self._cached_html_matches_request(html_path, public_filing_meta):
                result = {**cached_metadata, **result}
                self._apply_document_fiscal_focus(result, html_path)
                result["cache_status"] = "hit"
                self._write_json(metadata_path, result)
                self._append_log(
                    {
                        "event": "sec_download_cache_hit",
                        "ticker": ticker_upper,
                        "year": fiscal_year,
                        "category_slug": resolved_category_slug,
                        "form_type": form_type,
                        "local_html_path": str(html_path),
                    }
                )
                return result
            self._append_log(
                {
                    "event": "sec_download_cache_stale",
                    "ticker": ticker_upper,
                    "year": fiscal_year,
                    "category_slug": resolved_category_slug,
                    "form_type": form_type,
                    "local_html_path": str(html_path),
                    "cached_accession_number": cached_metadata.get("accession_number"),
                    "requested_accession_number": public_filing_meta.get("accession_number"),
                }
            )

        html = prefetched_html or self._request_text(filing_meta["filing_url"])
        output_dir.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")

        self._apply_document_fiscal_focus(result, html_path, html=html)
        result["cache_status"] = "downloaded"
        result["downloaded_at"] = datetime.now(timezone.utc).isoformat()
        self._write_json(metadata_path, result)
        self._append_log(
            {
                "event": "sec_download_success",
                "ticker": ticker_upper,
                "year": fiscal_year,
                "category_slug": resolved_category_slug,
                "form_type": form_type,
                "filing_url": filing_meta["filing_url"],
                "local_html_path": str(html_path),
            }
        )
        return result

    def download_earnings_release_8k(
        self,
        filing_meta: dict[str, Any],
        ticker: str,
        *,
        category: str | None = None,
        category_slug: str | None = None,
    ) -> dict[str, Any]:
        filing_year = int(filing_meta.get("filing_year") or filing_meta.get("fiscal_year"))
        ticker_upper = ticker.upper()
        accession_number = str(filing_meta.get("accession_number") or "")
        accession_safe = accession_number.replace("-", "")
        resolved_category = category or "uncategorized"
        resolved_category_slug = self._slugify_category(category_slug or resolved_category)
        output_dir = self.cache_dir / str(filing_year) / resolved_category_slug / ticker_upper / accession_safe
        primary_document = str(filing_meta.get("primary_document") or "primary.html")
        exhibit_document = str(filing_meta.get("exhibit_document") or "")
        if not exhibit_document:
            raise SecEdgarConnectorError("8-K earnings-release metadata is missing exhibit_document.")
        primary_path = output_dir / primary_document
        exhibit_path = output_dir / exhibit_document
        metadata_path = output_dir / "metadata.json"

        public_filing_meta = {
            key: value for key, value in filing_meta.items() if not str(key).startswith("_")
        }
        result = {
            **public_filing_meta,
            "ticker": ticker_upper,
            "category": resolved_category,
            "category_slug": resolved_category_slug,
            "cache_layout": "filing_year/category/ticker/accession",
            "local_primary_path": str(primary_path),
            "local_exhibit_path": str(exhibit_path),
            "local_html_path": str(exhibit_path),
            "local_metadata_path": str(metadata_path),
        }

        if primary_path.exists() and exhibit_path.exists() and metadata_path.exists():
            cached_metadata = self._read_json(metadata_path)
            if self._cached_earnings_release_matches_request(cached_metadata, public_filing_meta):
                result = {**cached_metadata, **result, "cache_status": "hit"}
                self._write_json(metadata_path, result)
                self._append_log(
                    {
                        "event": "sec_8k_earnings_cache_hit",
                        "ticker": ticker_upper,
                        "year": filing_year,
                        "category_slug": resolved_category_slug,
                        "accession_number": accession_number,
                        "local_exhibit_path": str(exhibit_path),
                    }
                )
                return result

        primary_html = str(filing_meta.get("_prefetched_primary_html") or "") or self._request_text(str(filing_meta["filing_url"]))
        exhibit_html = str(filing_meta.get("_prefetched_exhibit_html") or "") or self._request_text(str(filing_meta["exhibit_url"]))
        output_dir.mkdir(parents=True, exist_ok=True)
        primary_path.write_text(primary_html, encoding="utf-8")
        exhibit_path.write_text(exhibit_html, encoding="utf-8")

        result["cache_status"] = "downloaded"
        result["downloaded_at"] = datetime.now(timezone.utc).isoformat()
        self._write_json(metadata_path, result)
        self._append_log(
            {
                "event": "sec_8k_earnings_download_success",
                "ticker": ticker_upper,
                "year": filing_year,
                "category_slug": resolved_category_slug,
                "accession_number": accession_number,
                "exhibit_url": filing_meta.get("exhibit_url"),
                "local_exhibit_path": str(exhibit_path),
            }
        )
        return result

    def fetch_filing(
        self,
        ticker: str,
        form_type: str = "10-K",
        year: int = 2024,
        category: str | None = None,
        category_slug: str | None = None,
    ) -> dict[str, Any]:
        cik = self.get_cik(ticker)
        filing_meta = self.find_filing(cik=cik, form_type=form_type, year=year)
        return self.download_filing_html(
            filing_meta,
            ticker=ticker,
            year=year,
            category=category,
            category_slug=category_slug,
        )

    def fetch_earnings_release_8k(
        self,
        ticker: str,
        year: int,
        *,
        after_date: str | None = None,
        category: str | None = None,
        category_slug: str | None = None,
    ) -> dict[str, Any]:
        cik = self.get_cik(ticker)
        filing_meta = self.find_earnings_release_8k(cik=cik, year=year, after_date=after_date)
        return self.download_earnings_release_8k(
            filing_meta,
            ticker=ticker,
            category=category,
            category_slug=category_slug,
        )


    def find_earnings_release_8k(
        self,
        cik: str,
        year: int,
        *,
        after_date: str | None = None,
    ) -> dict[str, Any]:
        """Find an earnings-related 8-K and its selected Ex-99.1 release exhibit."""
        normalized_cik = self._normalize_cik(cik)
        submissions = self.get_company_submissions(normalized_cik)
        recent = submissions.get("filings", {}).get("recent", {})
        selected_block = recent
        selected_match = self._find_earnings_release_8k_match(
            recent,
            cik=normalized_cik,
            year=year,
            after_date=after_date,
        )

        if selected_match is None:
            for file_info in submissions.get("filings", {}).get("files", []):
                file_name = file_info.get("name")
                if not file_name:
                    continue
                historical_block = self.get_company_submission_file(
                    normalized_cik, file_name=file_name
                )
                selected_match = self._find_earnings_release_8k_match(
                    historical_block,
                    cik=normalized_cik,
                    year=year,
                    after_date=after_date,
                )
                if selected_match is not None:
                    selected_block = historical_block
                    break

        if selected_match is None:
            raise SecEdgarConnectorError(
                f"No earnings-release 8-K exhibit found for CIK {normalized_cik} and filing year {year}."
            )

        selected_idx = int(selected_match["idx"])
        accession_number = self._get_recent_value(selected_block, "accessionNumber", selected_idx)
        primary_document = self._get_recent_value(selected_block, "primaryDocument", selected_idx)
        filing_url = self._build_filing_url(normalized_cik, accession_number, primary_document)
        filing_date = self._get_recent_value(selected_block, "filingDate", selected_idx)
        report_date = self._get_recent_value(selected_block, "reportDate", selected_idx)
        exhibit = selected_match["exhibit"]
        exhibit_document = str(exhibit.get("name") or "")
        exhibit_url = self._build_filing_url(normalized_cik, accession_number, exhibit_document)
        return {
            "ticker": None,
            "company": submissions.get("name"),
            "cik": normalized_cik,
            "form_type": "8-K",
            "source_type": "8-K",
            "source_tier": "company_authored_unaudited_sec_filing",
            "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
            "requested_year": year,
            "filing_year": year,
            "fiscal_year": year,
            "fiscal_year_source": "filing_year",
            "filing_date": filing_date,
            "report_date": report_date,
            "period_end": report_date or filing_date,
            "period_type": "current_report",
            "duration_months": None,
            "fiscal_period": None,
            "fiscal_period_source": "not_applicable",
            "publication_date": filing_date,
            "acceptance_datetime": self._get_recent_value(selected_block, "acceptanceDateTime", selected_idx),
            "accession_number": accession_number,
            "primary_document": primary_document,
            "document_description": self._get_recent_value(selected_block, "primaryDocDescription", selected_idx),
            "filing_items": self._get_recent_value(selected_block, "items", selected_idx),
            "filing_url": filing_url,
            "filing_detail_url": self._build_filing_detail_index_url(normalized_cik, accession_number),
            "exhibit_document": exhibit_document,
            "exhibit_type": exhibit.get("exhibit_type"),
            "exhibit_description": exhibit.get("description"),
            "exhibit_sequence": exhibit.get("sequence"),
            "exhibit_url": exhibit_url,
            "earnings_release_candidate_reason": exhibit.get("candidate_reason"),
            "_prefetched_primary_html": selected_match.get("primary_html"),
        }

    def _get_company_tickers(self) -> dict[str, Any]:
        cache_path = self.cache_dir / "_reference" / "company_tickers.json"
        if cache_path.exists():
            return self._read_json(cache_path)

        data = self._request_json(self.COMPANY_TICKERS_URL)
        self._write_json(cache_path, data)
        return data

    def get_company_submission_file(
        self, cik: str, file_name: str
    ) -> dict[str, Any]:
        normalized_cik = self._normalize_cik(cik)
        cache_path = self.cache_dir / "_reference" / "submissions" / file_name
        if cache_path.exists():
            return self._read_json(cache_path)

        url = self.SUBMISSIONS_FILE_URL_TEMPLATE.format(file_name=file_name)
        data = self._request_json(url)
        self._write_json(cache_path, data)
        self._append_log(
            {
                "event": "sec_submission_file_cached",
                "cik": normalized_cik,
                "file_name": file_name,
            }
        )
        return data

    def get_filing_detail_index(self, cik: str, accession_number: str) -> dict[str, Any]:
        normalized_cik = self._normalize_cik(cik)
        accession_no_dashes = str(accession_number or "").replace("-", "")
        cache_path = self.cache_dir / "_reference" / "filing_details" / f"{normalized_cik}_{accession_no_dashes}.json"
        if cache_path.exists():
            return self._read_json(cache_path)

        url = self._build_filing_detail_index_url(normalized_cik, accession_number)
        data = self._request_json(url)
        self._write_json(cache_path, data)
        self._append_log(
            {
                "event": "sec_filing_detail_index_cached",
                "cik": normalized_cik,
                "accession_number": accession_number,
            }
        )
        return data

    def _find_filing_match(
        self,
        filing_block: dict[str, list[Any]],
        cik: str,
        form_type: str,
        fiscal_year: int,
    ) -> dict[str, Any] | None:
        forms = filing_block.get("form", [])
        fallback_match: dict[str, Any] | None = None
        for idx, form in enumerate(forms):
            if form != form_type:
                continue
            report_date = self._get_recent_value(filing_block, "reportDate", idx)
            filing_date = self._get_recent_value(filing_block, "filingDate", idx)
            date_matches = report_date.startswith(str(fiscal_year)) or filing_date.startswith(str(fiscal_year))
            if not self._should_probe_document_fiscal_focus(
                report_date=report_date,
                filing_date=filing_date,
                fiscal_year=fiscal_year,
            ):
                continue
            accession_number = self._get_recent_value(filing_block, "accessionNumber", idx)
            primary_document = self._get_recent_value(filing_block, "primaryDocument", idx)
            if not accession_number or not primary_document:
                continue
            filing_url = self._build_filing_url(cik, accession_number, primary_document)
            html = self._request_text(filing_url)
            document_fiscal_year = self._document_fiscal_year_focus_from_html(html)
            document_fiscal_period = self._document_fiscal_period_focus_from_html(html)
            if document_fiscal_year == fiscal_year:
                return {
                    "idx": idx,
                    "html": html,
                    "document_fiscal_year_focus": document_fiscal_year,
                    "document_fiscal_period_focus": document_fiscal_period,
                }
            if document_fiscal_year is None and date_matches and fallback_match is None:
                fallback_match = {
                    "idx": idx,
                    "html": html,
                    "document_fiscal_period_focus": document_fiscal_period,
                }
                continue
            continue

        if fallback_match is not None:
            return fallback_match
        return None

    def _find_earnings_release_8k_match(
        self,
        filing_block: dict[str, list[Any]],
        cik: str,
        year: int,
        after_date: str | None = None,
    ) -> dict[str, Any] | None:
        forms = filing_block.get("form", [])
        for idx, form in enumerate(forms):
            if str(form or "").upper().strip() != "8-K":
                continue
            filing_date = self._get_recent_value(filing_block, "filingDate", idx)
            if not filing_date.startswith(str(year)):
                continue
            if after_date and filing_date and filing_date <= after_date:
                continue
            accession_number = self._get_recent_value(filing_block, "accessionNumber", idx)
            primary_document = self._get_recent_value(filing_block, "primaryDocument", idx)
            if not accession_number or not primary_document:
                continue
            filing_items = self._get_recent_value(filing_block, "items", idx)
            if not self._filing_items_include_earnings_release(filing_items):
                continue
            primary_url = self._build_filing_url(cik, accession_number, primary_document)
            primary_html = self._request_text(primary_url)
            detail_index = self.get_filing_detail_index(cik, accession_number)
            exhibit = self._select_earnings_release_exhibit(
                detail_index,
                primary_html=primary_html,
                filing_items=filing_items,
            )
            if exhibit:
                return {
                    "idx": idx,
                    "primary_html": primary_html,
                    "exhibit": exhibit,
                }
        return None

    @staticmethod
    def _should_probe_document_fiscal_focus(
        report_date: str | None,
        filing_date: str | None,
        fiscal_year: int,
    ) -> bool:
        date_years = {
            year
            for year in (
                SecEdgarConnector._date_year(report_date),
                SecEdgarConnector._date_year(filing_date),
            )
            if year is not None
        }
        if not date_years:
            return True
        return bool(date_years & {fiscal_year - 1, fiscal_year, fiscal_year + 1})

    def _request_json(self, url: str) -> dict[str, Any]:
        response = self._request(url)
        return response.json()

    def _request_text(self, url: str) -> str:
        response = self._request(url)
        return response.text

    def _request(self, url: str) -> requests.Response:
        self._rate_limit()
        response = self.session.get(url, timeout=self.timeout)
        if response.status_code >= 400:
            raise SecEdgarConnectorError(
                f"SEC request failed with status {response.status_code}: {url}"
            )
        return response

    def _rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_ts
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last_request_ts = time.monotonic()

    def _append_log(self, record: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **record,
        }
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False))
            f.write("\n")

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _write_json(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    @staticmethod
    def _cached_filing_matches_request(
        cached_metadata: dict[str, Any],
        requested_metadata: dict[str, Any],
    ) -> bool:
        comparable_fields = ("accession_number", "primary_document", "filing_url")
        matched_any = False
        for field in comparable_fields:
            requested_value = str(requested_metadata.get(field) or "").strip()
            cached_value = str(cached_metadata.get(field) or "").strip()
            if not requested_value:
                continue
            if not cached_value:
                return False
            matched_any = True
            if cached_value != requested_value:
                return False
        return matched_any

    @staticmethod
    def _cached_earnings_release_matches_request(
        cached_metadata: dict[str, Any],
        requested_metadata: dict[str, Any],
    ) -> bool:
        comparable_fields = ("accession_number", "primary_document", "exhibit_document", "exhibit_url")
        for field in comparable_fields:
            requested_value = str(requested_metadata.get(field) or "").strip()
            cached_value = str(cached_metadata.get(field) or "").strip()
            if requested_value and cached_value != requested_value:
                return False
        return bool(str(requested_metadata.get("accession_number") or "").strip())

    @classmethod
    def _cached_html_matches_request(
        cls,
        html_path: Path,
        requested_metadata: dict[str, Any],
    ) -> bool:
        form_type = str(requested_metadata.get("form_type") or "").upper().strip()
        if form_type not in {"10-K", "10-Q"}:
            return True

        text = html_path.read_text(encoding="utf-8", errors="ignore")
        document_year = cls._document_fiscal_year_focus_from_html(text)
        requested_year = cls._normalize_document_fiscal_year_focus(
            requested_metadata.get("document_fiscal_year_focus")
            or requested_metadata.get("fiscal_year")
        )
        if requested_year is not None and document_year != requested_year:
            return False

        if form_type != "10-Q":
            return True
        requested_period = cls._normalize_document_fiscal_period_focus(
            requested_metadata.get("document_fiscal_period_focus")
            or requested_metadata.get("fiscal_period")
        )
        if requested_period is None:
            return True
        document_period = cls._document_fiscal_period_focus_from_html(text)
        return document_period == requested_period

    @staticmethod
    def _get_recent_value(recent: dict[str, list[Any]], key: str, idx: int) -> str:
        values = recent.get(key, [])
        if idx >= len(values) or values[idx] is None:
            return ""
        return str(values[idx])

    @classmethod
    def _select_earnings_release_exhibit(
        cls,
        filing_detail_index: dict[str, Any],
        *,
        primary_html: str = "",
        filing_items: str = "",
    ) -> dict[str, Any] | None:
        descriptions = cls._exhibit_descriptions_from_primary_html(primary_html)
        candidates: list[tuple[int, dict[str, Any]]] = []
        has_earnings_item = cls._filing_items_include_earnings_release(filing_items)
        for sequence, item in enumerate(cls._filing_detail_items(filing_detail_index), start=1):
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            description = descriptions.get(name.lower(), "")
            exhibit_type = cls._infer_exhibit_type(name, description)
            if exhibit_type not in {"EX-99.1", "EX-99.01", "EX-99"}:
                continue
            description_text = description or str(item.get("description") or "")
            if cls._looks_like_non_earnings_exhibit(description_text):
                continue
            score = 0
            reason = []
            if exhibit_type in {"EX-99.1", "EX-99.01"}:
                score += 4
                reason.append("exhibit_99_1")
            elif exhibit_type == "EX-99":
                score += 2
                reason.append("exhibit_99")
            if cls._looks_like_earnings_release_text(description_text):
                score += 5
                reason.append("earnings_description")
            if cls._looks_like_earnings_release_text(name):
                score += 2
                reason.append("earnings_filename")
            if has_earnings_item:
                score += 1
                reason.append("8k_item_2_02_or_9_01")
            if score < 5:
                continue
            candidates.append(
                (
                    score,
                    {
                        **item,
                        "name": name,
                        "sequence": item.get("sequence") or sequence,
                        "exhibit_type": exhibit_type,
                        "description": description_text,
                        "candidate_reason": ",".join(reason),
                    },
                )
            )
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    @staticmethod
    def _filing_detail_items(filing_detail_index: dict[str, Any]) -> list[dict[str, Any]]:
        directory = filing_detail_index.get("directory") if isinstance(filing_detail_index.get("directory"), dict) else {}
        items = directory.get("item") if isinstance(directory.get("item"), list) else []
        return [item for item in items if isinstance(item, dict)]

    @staticmethod
    def _filing_items_include_earnings_release(value: str | None) -> bool:
        normalized = re.sub(r"\s+", "", str(value or "").lower())
        return "2.02" in normalized or "item2.02" in normalized

    @classmethod
    def _exhibit_descriptions_from_primary_html(cls, html: str) -> dict[str, str]:
        descriptions: dict[str, str] = {}
        for row in re.findall(r"<tr\b.*?</tr>", html or "", flags=re.I | re.S):
            names = set(
                name.lower()
                for name in re.findall(r"href=[\"'][^\"']*/([^/\"']+\.(?:htm|html|txt|pdf))[\"']", row, flags=re.I)
            )
            names.update(
                name.lower()
                for name in re.findall(r"\b[\w.-]+\.(?:htm|html|txt|pdf)\b", row, flags=re.I)
            )
            if not names:
                continue
            text = cls._html_to_text(row)
            for name in names:
                descriptions.setdefault(name, text)
        return descriptions

    @staticmethod
    def _html_to_text(value: str) -> str:
        text = re.sub(r"<[^>]+>", " ", value or "")
        text = html_lib.unescape(text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _infer_exhibit_type(name: str, description: str = "") -> str | None:
        text = f"{name} {description}".upper()
        compact = re.sub(r"[^A-Z0-9]+", "", text)
        if re.search(r"EX[-_\s]?99(?:\.|-|_)?0?1\b", text) or "EX991" in compact or "EX9901" in compact:
            return "EX-99.1"
        if re.search(r"EX[-_\s]?99\b", text) or "EX99" in compact:
            return "EX-99"
        return None

    @staticmethod
    def _looks_like_earnings_release_text(value: str) -> bool:
        lowered = str(value or "").lower()
        terms = (
            "earnings",
            "financial results",
            "results of operations",
            "quarterly results",
            "reports results",
            "announces results",
            "shareholder letter",
        )
        return any(term in lowered for term in terms)

    @staticmethod
    def _looks_like_non_earnings_exhibit(value: str) -> bool:
        lowered = str(value or "").lower()
        negative_terms = (
            "investor presentation",
            "presentation",
            "slide",
            "transcript",
            "webcast",
            "conference call transcript",
        )
        return any(term in lowered for term in negative_terms)

    @staticmethod
    def _filing_period_metadata(
        form_type: str,
        report_date: str | None,
        fiscal_period_focus: str | None = None,
        fiscal_year_focus: int | str | None = None,
    ) -> dict[str, Any]:
        normalized_form = str(form_type or "").upper().strip()
        period_end = str(report_date or "").strip() or None
        document_period = SecEdgarConnector._normalize_document_fiscal_period_focus(fiscal_period_focus)
        document_year = SecEdgarConnector._normalize_document_fiscal_year_focus(fiscal_year_focus)
        fiscal_year_fields: dict[str, Any] = {}
        if document_year is not None:
            fiscal_year_fields = {
                "fiscal_year": document_year,
                "fiscal_year_source": "document_fiscal_year_focus",
                "document_fiscal_year_focus": document_year,
            }
        if normalized_form == "10-K":
            return {
                **fiscal_year_fields,
                "period_end": period_end,
                "period_type": "annual",
                "duration_months": 12,
                "fiscal_period": "FY",
                "fiscal_period_source": "form_type",
            }
        if normalized_form == "10-Q":
            if document_period:
                return {
                    **fiscal_year_fields,
                    "period_end": period_end,
                    "period_type": "quarterly",
                    "duration_months": 3,
                    "fiscal_period": document_period,
                    "fiscal_period_source": "document_fiscal_period_focus",
                    "document_fiscal_period_focus": document_period,
                }
            return {
                **fiscal_year_fields,
                "period_end": period_end,
                "period_type": "quarterly",
                "duration_months": 3,
                "fiscal_period": SecEdgarConnector._calendar_quarter(period_end),
                "fiscal_period_source": "calendar_quarter_from_period_end",
            }
        return {
            **fiscal_year_fields,
            "period_end": period_end,
            "period_type": None,
            "duration_months": None,
            "fiscal_period": None,
            "fiscal_period_source": "unknown",
        }

    @classmethod
    def _apply_document_fiscal_focus(
        cls,
        metadata: dict[str, Any],
        html_path: Path,
        html: str | None = None,
    ) -> None:
        if str(metadata.get("form_type") or "").upper().strip() not in {"10-K", "10-Q"}:
            return
        text = html if html is not None else html_path.read_text(encoding="utf-8", errors="ignore")
        document_year = cls._document_fiscal_year_focus_from_html(text)
        document_period = cls._document_fiscal_period_focus_from_html(text)
        if not document_year and not document_period:
            return
        metadata.update(
            cls._filing_period_metadata(
                form_type=str(metadata.get("form_type") or ""),
                report_date=metadata.get("report_date") or metadata.get("period_end"),
                fiscal_period_focus=document_period,
                fiscal_year_focus=document_year,
            )
        )

    @staticmethod
    def _document_fiscal_year_focus_from_html(html: str) -> int | None:
        value = SecEdgarConnector._ixbrl_document_focus_value(html, "DocumentFiscalYearFocus")
        return SecEdgarConnector._normalize_document_fiscal_year_focus(value)

    @staticmethod
    def _document_fiscal_period_focus_from_html(html: str) -> str | None:
        value = SecEdgarConnector._ixbrl_document_focus_value(html, "DocumentFiscalPeriodFocus")
        if value:
            return SecEdgarConnector._normalize_document_fiscal_period_focus(value)

        # Preserve compatibility with older local fixtures that omit the ix: tag prefix.
        match = re.search(
            r"DocumentFiscalPeriodFocus\b[^>]*>\s*(FY|Q[1-4])\s*<",
            html or "",
            flags=re.I,
        )
        if not match:
            return None
        return SecEdgarConnector._normalize_document_fiscal_period_focus(match.group(1))

    @staticmethod
    def _normalize_document_fiscal_period_focus(value: str | None) -> str | None:
        normalized = str(value or "").upper().strip()
        return normalized if normalized in {"FY", "Q1", "Q2", "Q3", "Q4"} else None

    @staticmethod
    def _ixbrl_document_focus_value(html: str, focus_name: str) -> str | None:
        pattern = (
            rf"<ix:nonNumeric\b[^>]*\bname=[\"'][^\"']*{re.escape(focus_name)}[\"'][^>]*>"
            r"(?P<body>.*?)</ix:nonNumeric>"
        )
        match = re.search(pattern, html or "", flags=re.I | re.S)
        if not match:
            return None
        text = re.sub(r"<[^>]+>", " ", match.group("body"))
        text = re.sub(r"\s+", " ", text).strip()
        return text or None

    @staticmethod
    def _normalize_document_fiscal_year_focus(value: int | str | None) -> int | None:
        if value is None:
            return None
        match = re.search(r"(20\d{2}|19\d{2})", str(value))
        if not match:
            return None
        return int(match.group(1))

    @staticmethod
    def _date_year(value: str | None) -> int | None:
        text = str(value or "")
        if len(text) < 4:
            return None
        try:
            return int(text[:4])
        except ValueError:
            return None

    @staticmethod
    def _calendar_quarter(period_end: str | None) -> str | None:
        if not period_end or len(period_end) < 7:
            return None
        try:
            month = int(period_end[5:7])
        except ValueError:
            return None
        if month < 1 or month > 12:
            return None
        return f"Q{((month - 1) // 3) + 1}"

    @staticmethod
    def _normalize_cik(cik: str | int) -> str:
        return f"{int(cik):010d}"

    @staticmethod
    def _slugify_category(category: str) -> str:
        slug = category.strip().lower()
        slug = slug.replace("&", "and")
        slug = re.sub(r"[^a-z0-9-]+", "_", slug)
        slug = re.sub(r"_+", "_", slug).strip("_")
        return slug or "uncategorized"

    @classmethod
    def _build_filing_url(
        cls, cik: str, accession_number: str, primary_document: str
    ) -> str:
        cik_no_leading_zero = str(int(cik))
        accession_no_dashes = accession_number.replace("-", "")
        return (
            f"{cls.ARCHIVES_BASE_URL}/{cik_no_leading_zero}/"
            f"{accession_no_dashes}/{primary_document}"
        )

    @classmethod
    def _build_filing_detail_index_url(cls, cik: str, accession_number: str) -> str:
        cik_no_leading_zero = str(int(cik))
        accession_no_dashes = accession_number.replace("-", "")
        return f"{cls.ARCHIVES_BASE_URL}/{cik_no_leading_zero}/{accession_no_dashes}/index.json"
