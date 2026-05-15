from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from connectors import SecFilingManifestRecord
from .section_splitter import (
    DEFAULT_OUTPUT_ITEMS,
    SecFilingChunk,
    chunk_section,
    find_10k_sections,
)


def extract_sec_html_text(html_path: str | Path) -> str:
    path = Path(html_path)
    html = path.read_text(encoding="utf-8", errors="ignore")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    for tag in soup.find_all(style=_is_hidden_style):
        tag.decompose()

    raw_text = soup.get_text("\n")
    return _normalize_extracted_text(raw_text)


def build_chunks_for_filing(
    manifest_record: SecFilingManifestRecord,
    output_items: Iterable[str] | None = DEFAULT_OUTPUT_ITEMS,
    target_words: int = 900,
    overlap_words: int = 150,
    min_words: int = 80,
) -> list[SecFilingChunk]:
    text = extract_sec_html_text(manifest_record.html_path)
    sections = find_10k_sections(text, output_items=output_items)
    chunks: list[SecFilingChunk] = []

    for section in sections:
        section_chunks = chunk_section(
            section,
            target_words=target_words,
            overlap_words=overlap_words,
            min_words=min_words,
        )
        for chunk_text, char_start, char_end in section_chunks:
            chunk_index = len(
                [
                    chunk
                    for chunk in chunks
                    if chunk.item_code == section.item_code
                ]
            ) + 1
            chunks.append(
                SecFilingChunk(
                    chunk_id=_build_chunk_id(
                        ticker=manifest_record.ticker,
                        fiscal_year=manifest_record.fiscal_year,
                        source_type=manifest_record.source_type,
                        item_code=section.item_code,
                        chunk_index=chunk_index,
                    ),
                    ticker=manifest_record.ticker,
                    company=manifest_record.company,
                    fiscal_year=manifest_record.fiscal_year,
                    category=manifest_record.category,
                    category_slug=manifest_record.category_slug,
                    source_type=manifest_record.source_type,
                    form_type=manifest_record.form_type,
                    section=section.section,
                    item_code=section.item_code,
                    chunk_index=chunk_index,
                    text=chunk_text,
                    char_start=char_start,
                    char_end=char_end,
                    source_url=manifest_record.filing_url,
                    local_path=manifest_record.html_path,
                    metadata={
                        "accession_number": manifest_record.accession_number,
                        "filing_date": manifest_record.filing_date,
                        "report_date": manifest_record.report_date,
                        "primary_document": manifest_record.primary_document,
                        "metadata_path": manifest_record.metadata_path,
                    },
                )
            )
    return chunks


def _normalize_extracted_text(raw_text: str) -> str:
    lines: list[str] = []
    blank_pending = False
    for raw_line in raw_text.splitlines():
        line = raw_line.replace("\xa0", " ")
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line:
            blank_pending = bool(lines)
            continue
        if blank_pending and lines and lines[-1] != "":
            lines.append("")
        lines.append(line)
        blank_pending = False

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_hidden_style(style: str | None) -> bool:
    if not style:
        return False
    normalized = style.replace(" ", "").lower()
    return "display:none" in normalized or "visibility:hidden" in normalized


def _build_chunk_id(
    ticker: str,
    fiscal_year: int,
    source_type: str,
    item_code: str,
    chunk_index: int,
) -> str:
    source_key = re.sub(r"[^A-Z0-9]", "", source_type.upper())
    item_key = f"ITEM{item_code.upper()}"
    return f"{ticker.upper()}_{fiscal_year}_{source_key}_{item_key}_CHUNK_{chunk_index:04d}"
