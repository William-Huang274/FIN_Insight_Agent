from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class SecFilingManifestRecord(BaseModel):
    ticker: str
    company: str | None = None
    cik: str | None = None
    fiscal_year: int
    fiscal_year_source: str | None = None
    document_fiscal_year_focus: int | None = None
    category: str
    category_slug: str
    form_type: str
    source_type: str = "10-K"
    source_tier: str = "primary_sec_filing"

    filing_date: str | None = None
    report_date: str | None = None
    period_end: str | None = None
    period_type: str | None = None
    duration_months: int | None = None
    fiscal_period: str | None = None
    fiscal_period_source: str | None = None
    document_fiscal_period_focus: str | None = None
    accession_number: str | None = None
    primary_document: str | None = None
    document_description: str | None = None
    filing_url: str | None = None

    html_path: str
    metadata_path: str
    cache_layout: str = "year/category/ticker"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_jsonl_line(self) -> str:
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False)


def iter_sec_filing_manifest(
    root: str | Path,
    years: Iterable[int | str] | None = None,
    tickers: Iterable[str] | None = None,
    categories: Iterable[str] | None = None,
    form_types: Iterable[str] | None = None,
    require_html: bool = True,
) -> Iterator[SecFilingManifestRecord]:
    root_path = Path(root)
    year_filter = _normalize_years(years)
    ticker_filter = _normalize_tickers(tickers)
    category_filter = _normalize_strings(categories)
    form_type_filter = _normalize_strings(form_types, upper=True)

    if not root_path.exists():
        return

    for year_dir in sorted(root_path.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue

        for category_dir in sorted(year_dir.iterdir()):
            if not category_dir.is_dir():
                continue
            if category_filter is not None and category_dir.name not in category_filter:
                continue

            for ticker_dir in sorted(category_dir.iterdir()):
                if not ticker_dir.is_dir():
                    continue
                ticker = ticker_dir.name.upper()
                if ticker_filter is not None and ticker not in ticker_filter:
                    continue

                for metadata_path in sorted(ticker_dir.glob("*.metadata.json")):
                    form_type = metadata_path.name.removesuffix(".metadata.json")
                    if (
                        form_type_filter is not None
                        and form_type.upper() not in form_type_filter
                    ):
                        continue

                    html_path = ticker_dir / f"{form_type}.html"
                    if require_html and not html_path.exists():
                        continue

                    metadata = _read_json(metadata_path)
                    record = _build_record(
                        year=int(year_dir.name),
                        category_slug=category_dir.name,
                        ticker=ticker,
                        form_type=form_type,
                        html_path=html_path,
                        metadata_path=metadata_path,
                        metadata=metadata,
                    )
                    if year_filter is not None and str(record.fiscal_year) not in year_filter:
                        continue
                    yield record


def collect_sec_filing_manifest(
    root: str | Path,
    years: Iterable[int | str] | None = None,
    tickers: Iterable[str] | None = None,
    categories: Iterable[str] | None = None,
    form_types: Iterable[str] | None = None,
    require_html: bool = True,
) -> list[SecFilingManifestRecord]:
    return list(
        iter_sec_filing_manifest(
            root=root,
            years=years,
            tickers=tickers,
            categories=categories,
            form_types=form_types,
            require_html=require_html,
        )
    )


def write_sec_filing_manifest_jsonl(
    records: Iterable[SecFilingManifestRecord], path: str | Path
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.to_jsonl_line())
            f.write("\n")


def read_sec_filing_manifest_jsonl(path: str | Path) -> list[SecFilingManifestRecord]:
    input_path = Path(path)
    records: list[SecFilingManifestRecord] = []
    with input_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(SecFilingManifestRecord.model_validate_json(stripped))
            except ValueError as exc:
                raise ValueError(
                    f"Invalid SEC filing manifest JSONL at {input_path}:{line_number}"
                ) from exc
    return records


def _build_record(
    year: int,
    category_slug: str,
    ticker: str,
    form_type: str,
    html_path: Path,
    metadata_path: Path,
    metadata: dict[str, Any],
) -> SecFilingManifestRecord:
    document_year, document_period = _document_fiscal_focus(html_path)
    metadata_document_year = metadata.get("document_fiscal_year_focus")
    document_year = metadata_document_year or document_year
    document_period = metadata.get("document_fiscal_period_focus") or document_period
    normalized_form = str(metadata.get("form_type") or form_type).upper().strip()
    metadata_fiscal_year = _normalize_document_fiscal_year_focus(metadata.get("fiscal_year"))
    ignored_document_year = None
    if (
        normalized_form == "10-K"
        and metadata_document_year is None
        and metadata_fiscal_year is not None
        and document_year is not None
        and document_year != metadata_fiscal_year
    ):
        ignored_document_year = document_year
        document_year = None
    period = _filing_period_metadata(
        form_type=normalized_form,
        report_date=metadata.get("report_date"),
        fiscal_period_focus=document_period,
        fiscal_year_focus=document_year,
    )
    if ignored_document_year is not None:
        period = {
            **period,
            "fiscal_year_source": metadata.get("fiscal_year_source")
            or "metadata_fiscal_year_conflict_with_document_focus",
            "document_fiscal_year_focus": ignored_document_year,
        }
    merged_metadata = {**metadata, **period}
    return SecFilingManifestRecord(
        ticker=ticker,
        company=merged_metadata.get("company"),
        cik=merged_metadata.get("cik"),
        fiscal_year=int(merged_metadata.get("fiscal_year") or year),
        fiscal_year_source=merged_metadata.get("fiscal_year_source"),
        document_fiscal_year_focus=merged_metadata.get("document_fiscal_year_focus"),
        category=merged_metadata.get("category") or category_slug,
        category_slug=merged_metadata.get("category_slug") or category_slug,
        form_type=merged_metadata.get("form_type") or form_type,
        source_type=merged_metadata.get("form_type") or form_type,
        source_tier=merged_metadata.get("source_tier") or "primary_sec_filing",
        filing_date=merged_metadata.get("filing_date"),
        report_date=merged_metadata.get("report_date"),
        period_end=merged_metadata.get("period_end"),
        period_type=merged_metadata.get("period_type"),
        duration_months=merged_metadata.get("duration_months"),
        fiscal_period=merged_metadata.get("fiscal_period"),
        fiscal_period_source=merged_metadata.get("fiscal_period_source"),
        document_fiscal_period_focus=merged_metadata.get("document_fiscal_period_focus"),
        accession_number=merged_metadata.get("accession_number"),
        primary_document=merged_metadata.get("primary_document"),
        document_description=merged_metadata.get("document_description"),
        filing_url=merged_metadata.get("filing_url"),
        html_path=str(html_path),
        metadata_path=str(metadata_path),
        cache_layout=merged_metadata.get("cache_layout") or "year/category/ticker",
        metadata=merged_metadata,
    )


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_years(values: Iterable[int | str] | None) -> set[str] | None:
    if values is None:
        return None
    return {str(value) for value in values}


def _normalize_tickers(values: Iterable[str] | None) -> set[str] | None:
    if values is None:
        return None
    return {value.upper() for value in values}


def _normalize_strings(
    values: Iterable[str] | None, upper: bool = False
) -> set[str] | None:
    if values is None:
        return None
    if upper:
        return {value.upper() for value in values}
    return set(values)


def _filing_period_metadata(
    form_type: str,
    report_date: str | None,
    fiscal_period_focus: str | None = None,
    fiscal_year_focus: int | str | None = None,
) -> dict[str, Any]:
    normalized_form = str(form_type or "").upper().strip()
    period_end = str(report_date or "").strip() or None
    document_period = _normalize_document_fiscal_period_focus(fiscal_period_focus)
    document_year = _normalize_document_fiscal_year_focus(fiscal_year_focus)
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
            "fiscal_period": _calendar_quarter(period_end),
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


def _document_fiscal_focus(html_path: Path) -> tuple[int | None, str | None]:
    if not html_path.exists():
        return None, None
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    year_match = re.search(r"DocumentFiscalYearFocus\b[^>]*>\s*(20\d{2}|19\d{2})\s*<", text, flags=re.I)
    period_match = re.search(r"DocumentFiscalPeriodFocus\b[^>]*>\s*(FY|Q[1-4])\s*<", text, flags=re.I)
    fiscal_year = _normalize_document_fiscal_year_focus(year_match.group(1)) if year_match else None
    fiscal_period = _normalize_document_fiscal_period_focus(period_match.group(1)) if period_match else None
    return fiscal_year, fiscal_period


def _normalize_document_fiscal_period_focus(value: str | None) -> str | None:
    normalized = str(value or "").upper().strip()
    return normalized if normalized in {"FY", "Q1", "Q2", "Q3", "Q4"} else None


def _normalize_document_fiscal_year_focus(value: int | str | None) -> int | None:
    if value is None:
        return None
    match = re.search(r"(20\d{2}|19\d{2})", str(value))
    if not match:
        return None
    return int(match.group(1))


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
