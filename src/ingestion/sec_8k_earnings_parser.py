from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from connectors import SecFilingManifestRecord

from .parse_sec_filing import extract_sec_html_text
from .section_splitter import (
    SecFilingChunk,
    SecFilingSection,
    SecSemanticBlock,
    build_semantic_blocks,
    chunk_semantic_block,
)


EARNINGS_RELEASE_ITEM_CODE = "exhibit_99_1"
EARNINGS_RELEASE_SECTION = "Exhibit 99.1 Earnings Release"


def build_8k_earnings_chunks(
    manifest_record: SecFilingManifestRecord,
    *,
    target_words: int = 650,
    overlap_words: int = 100,
    min_words: int = 40,
) -> list[SecFilingChunk]:
    text = extract_sec_html_text(manifest_record.html_path)
    if not text:
        return []

    section = SecFilingSection(
        item_code=EARNINGS_RELEASE_ITEM_CODE,
        section=EARNINGS_RELEASE_SECTION,
        char_start=0,
        char_end=len(text),
        text=text,
    )
    blocks = _earnings_blocks(section)
    period_metadata = _reported_period_metadata(text)
    chunks: list[SecFilingChunk] = []

    for block in blocks:
        block_id = _build_8k_block_id(manifest_record, block)
        block_chunks = chunk_semantic_block(
            block,
            target_words=target_words,
            overlap_words=overlap_words,
            min_words=min_words,
        )
        block_part_count = len(block_chunks)
        for block_part_index, (chunk_text, char_start, char_end) in enumerate(
            block_chunks,
            start=1,
        ):
            chunk_index = len(chunks) + 1
            chunks.append(
                SecFilingChunk(
                    chunk_id=_build_8k_chunk_id(block_id, block_part_index, block_part_count),
                    ticker=manifest_record.ticker,
                    company=manifest_record.company,
                    fiscal_year=manifest_record.fiscal_year,
                    category=manifest_record.category,
                    category_slug=manifest_record.category_slug,
                    source_type="8-K",
                    form_type="8-K",
                    source_tier="company_authored_unaudited_sec_filing",
                    period_end=manifest_record.period_end,
                    period_type=manifest_record.period_type or "current_report",
                    duration_months=manifest_record.duration_months,
                    fiscal_period=manifest_record.fiscal_period,
                    section=EARNINGS_RELEASE_SECTION,
                    item_code=EARNINGS_RELEASE_ITEM_CODE,
                    chunk_index=chunk_index,
                    block_id=block_id,
                    block_index=block.block_index,
                    block_heading=block.block_heading,
                    block_type=block.block_type,
                    block_char_start=block.char_start,
                    block_char_end=block.char_end,
                    block_part_index=block_part_index,
                    block_part_count=block_part_count,
                    contains_table="[TABLE_START" in chunk_text and "[TABLE_END]" in chunk_text,
                    text=chunk_text,
                    char_start=char_start,
                    char_end=char_end,
                    source_url=_source_url(manifest_record),
                    local_path=manifest_record.html_path,
                    metadata={
                        "source_policy": "SEC_PRIMARY_MIXED_WITH_8K_EARNINGS",
                        "source_boundary": "company_authored_unaudited_sec_filing",
                        "unaudited": True,
                        "management_view": True,
                        "exclude_from_exact_value_ledger": True,
                        "numeric_basis": _numeric_basis(chunk_text),
                        "accession_number": manifest_record.accession_number,
                        "filing_date": manifest_record.filing_date,
                        "report_date": manifest_record.report_date,
                        "period_end": manifest_record.period_end,
                        "period_type": manifest_record.period_type or "current_report",
                        "duration_months": manifest_record.duration_months,
                        "fiscal_period": manifest_record.fiscal_period,
                        "fiscal_period_source": manifest_record.fiscal_period_source,
                        "primary_document": manifest_record.primary_document,
                        "metadata_path": manifest_record.metadata_path,
                        "exhibit_document": manifest_record.metadata.get("exhibit_document"),
                        "exhibit_type": manifest_record.metadata.get("exhibit_type"),
                        "exhibit_description": manifest_record.metadata.get("exhibit_description"),
                        "exhibit_url": manifest_record.metadata.get("exhibit_url"),
                        **period_metadata,
                    },
                )
            )
    return chunks


def _earnings_blocks(section: SecFilingSection) -> list[SecSemanticBlock]:
    blocks = build_semantic_blocks(section)
    if not blocks:
        blocks = [
            SecSemanticBlock(
                item_code=section.item_code,
                section=section.section,
                block_index=1,
                block_heading=section.section,
                block_type="management_commentary",
                char_start=0,
                char_end=len(section.text),
                text=section.text,
            )
        ]
    return [
        block.model_copy(update={"block_type": _earnings_block_type(block.text)})
        for block in blocks
    ]


def _earnings_block_type(text: str) -> str:
    lowered = text.lower()
    if "[table_start" in lowered:
        return "unaudited_company_table"
    if "non-gaap" in lowered or "non gaap" in lowered or "reconciliation" in lowered:
        return "non_gaap_reconciliation_or_disclaimer"
    if "forward-looking" in lowered or "safe harbor" in lowered:
        return "forward_looking_statement"
    if any(term in lowered for term in ("outlook", "guidance", "expects", "forecast")):
        return "outlook_or_guidance"
    if any(term in lowered for term in ("highlights", "results", "revenue", "earnings")):
        return "earnings_highlights"
    return "management_commentary"


def _reported_period_metadata(text: str) -> dict[str, Any]:
    fiscal_period = _reported_fiscal_period(text)
    fiscal_year = _reported_fiscal_year(text)
    period_end = _reported_period_end(text)
    metadata: dict[str, Any] = {}
    if period_end:
        metadata["reported_period_end"] = period_end
    if fiscal_period:
        metadata["reported_fiscal_period"] = fiscal_period
    if fiscal_year:
        metadata["reported_fiscal_year"] = fiscal_year
    return metadata


def _reported_fiscal_period(text: str) -> str | None:
    lowered = text.lower()
    quarter_words = {
        "first": "Q1",
        "second": "Q2",
        "third": "Q3",
        "fourth": "Q4",
    }
    for word, quarter in quarter_words.items():
        if re.search(rf"\b{word}\s+quarter\b", lowered):
            return quarter
    match = re.search(r"\bq([1-4])\b", lowered)
    if match:
        return f"Q{match.group(1)}"
    return None


def _reported_fiscal_year(text: str) -> int | None:
    match = re.search(r"\b(?:fiscal\s+year|fiscal|fy)\s*(20\d{2}|19\d{2})\b", text, flags=re.I)
    if match:
        return int(match.group(1))
    return None


def _reported_period_end(text: str) -> str | None:
    date_pattern = (
        r"(January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?)"
        r"\s+\d{1,2},\s+(?:20|19)\d{2}"
    )
    match = re.search(
        rf"\b(?:quarter|three months|six months|nine months|year)\s+ended\s+({date_pattern})",
        text,
        flags=re.I,
    )
    if not match:
        return None
    return _parse_month_day_year(match.group(1))


def _parse_month_day_year(value: str) -> str | None:
    cleaned = value.replace(".", "")
    cleaned = re.sub(r"^Sept\b", "Sep", cleaned, flags=re.I)
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _numeric_basis(text: str) -> str | None:
    lowered = text.lower()
    if "non-gaap" in lowered or "non gaap" in lowered:
        return "non_gaap"
    return None


def _source_url(record: SecFilingManifestRecord) -> str | None:
    return str(record.metadata.get("exhibit_url") or record.filing_url or "") or None


def _build_8k_block_id(record: SecFilingManifestRecord, block: SecSemanticBlock) -> str:
    accession = re.sub(r"[^A-Z0-9]", "", str(record.accession_number or "NOACCESSION").upper())
    exhibit = re.sub(
        r"[^A-Z0-9]",
        "",
        str(record.metadata.get("exhibit_document") or Path(record.html_path).name or "EXHIBIT").upper(),
    )
    return f"8K_EARNINGS::{record.ticker.upper()}::{accession}::{exhibit}::BLOCK_{block.block_index:04d}"


def _build_8k_chunk_id(block_id: str, block_part_index: int, block_part_count: int) -> str:
    if block_part_count <= 1:
        return f"{block_id}::CHUNK_0001"
    return f"{block_id}::PART_{block_part_index:02d}_OF_{block_part_count:02d}"
