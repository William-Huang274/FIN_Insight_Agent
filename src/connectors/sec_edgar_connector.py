from __future__ import annotations

import json
import os
import time
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
        selected_idx = self._find_filing_index(recent, form_type=form_type, year=year)

        if selected_idx is None:
            for file_info in submissions.get("filings", {}).get("files", []):
                file_name = file_info.get("name")
                if not file_name:
                    continue
                historical_block = self.get_company_submission_file(
                    normalized_cik, file_name=file_name
                )
                selected_idx = self._find_filing_index(
                    historical_block, form_type=form_type, year=year
                )
                if selected_idx is not None:
                    selected_block = historical_block
                    break

        if selected_idx is None:
            raise SecEdgarConnectorError(
                f"No {form_type} filing found for CIK {normalized_cik} and year {year}."
            )

        accession_number = self._get_recent_value(
            selected_block, "accessionNumber", selected_idx
        )
        primary_document = self._get_recent_value(
            selected_block, "primaryDocument", selected_idx
        )
        filing_url = self._build_filing_url(normalized_cik, accession_number, primary_document)

        return {
            "ticker": None,
            "company": submissions.get("name"),
            "cik": normalized_cik,
            "form_type": form_type,
            "fiscal_year": year,
            "filing_date": self._get_recent_value(selected_block, "filingDate", selected_idx),
            "report_date": self._get_recent_value(selected_block, "reportDate", selected_idx),
            "acceptance_datetime": self._get_recent_value(
                selected_block, "acceptanceDateTime", selected_idx
            ),
            "accession_number": accession_number,
            "primary_document": primary_document,
            "document_description": self._get_recent_value(
                selected_block, "primaryDocDescription", selected_idx
            ),
            "filing_url": filing_url,
        }

    def download_filing_html(
        self,
        filing_meta: dict[str, Any],
        ticker: str,
        year: int | None = None,
    ) -> dict[str, Any]:
        fiscal_year = int(year or filing_meta["fiscal_year"])
        ticker_upper = ticker.upper()
        form_type = filing_meta["form_type"]
        output_dir = self.cache_dir / ticker_upper / str(fiscal_year)
        html_path = output_dir / f"{form_type}.html"
        metadata_path = output_dir / f"{form_type}.metadata.json"

        result = {
            **filing_meta,
            "ticker": ticker_upper,
            "local_html_path": str(html_path),
            "local_metadata_path": str(metadata_path),
        }

        if html_path.exists() and metadata_path.exists():
            result["cache_status"] = "hit"
            self._append_log(
                {
                    "event": "sec_download_cache_hit",
                    "ticker": ticker_upper,
                    "year": fiscal_year,
                    "form_type": form_type,
                    "local_html_path": str(html_path),
                }
            )
            return result

        html = self._request_text(filing_meta["filing_url"])
        output_dir.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html, encoding="utf-8")

        result["cache_status"] = "downloaded"
        result["downloaded_at"] = datetime.now(timezone.utc).isoformat()
        self._write_json(metadata_path, result)
        self._append_log(
            {
                "event": "sec_download_success",
                "ticker": ticker_upper,
                "year": fiscal_year,
                "form_type": form_type,
                "filing_url": filing_meta["filing_url"],
                "local_html_path": str(html_path),
            }
        )
        return result

    def fetch_filing(
        self,
        ticker: str,
        form_type: str = "10-K",
        year: int = 2024,
    ) -> dict[str, Any]:
        cik = self.get_cik(ticker)
        filing_meta = self.find_filing(cik=cik, form_type=form_type, year=year)
        return self.download_filing_html(filing_meta, ticker=ticker, year=year)

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

    @classmethod
    def _find_filing_index(
        cls, filing_block: dict[str, list[Any]], form_type: str, year: int
    ) -> int | None:
        forms = filing_block.get("form", [])
        matches = []
        fallback_matches = []
        for idx, form in enumerate(forms):
            if form != form_type:
                continue
            report_date = cls._get_recent_value(filing_block, "reportDate", idx)
            filing_date = cls._get_recent_value(filing_block, "filingDate", idx)
            if report_date.startswith(str(year)):
                matches.append(idx)
            elif filing_date.startswith(str(year)):
                fallback_matches.append(idx)

        if matches:
            return matches[0]
        if fallback_matches:
            return fallback_matches[0]
        return None

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
    def _get_recent_value(recent: dict[str, list[Any]], key: str, idx: int) -> str:
        values = recent.get(key, [])
        if idx >= len(values) or values[idx] is None:
            return ""
        return str(values[idx])

    @staticmethod
    def _normalize_cik(cik: str | int) -> str:
        return f"{int(cik):010d}"

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
