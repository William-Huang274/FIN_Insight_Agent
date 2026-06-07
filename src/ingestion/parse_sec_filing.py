from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

from connectors import SecFilingManifestRecord
from .section_splitter import (
    SecFilingChunk,
    build_semantic_blocks,
    chunk_semantic_block,
    find_sec_filing_sections,
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
    for table_index, table in enumerate(list(soup.find_all("table")), start=1):
        table_text = _serialize_html_table(table, table_index)
        replacement = soup.new_tag("div")
        replacement.string = f"\n{table_text}\n"
        table.replace_with(replacement)

    raw_text = soup.get_text("\n")
    return _normalize_extracted_text(raw_text)


def build_chunks_for_filing(
    manifest_record: SecFilingManifestRecord,
    output_items: Iterable[str] | None = None,
    target_words: int = 900,
    overlap_words: int = 150,
    min_words: int = 80,
) -> list[SecFilingChunk]:
    text = extract_sec_html_text(manifest_record.html_path)
    sections = find_sec_filing_sections(
        text,
        form_type=manifest_record.form_type,
        output_items=output_items,
    )
    chunks: list[SecFilingChunk] = []
    block_id_occurrences: dict[str, int] = {}

    for section in sections:
        blocks = build_semantic_blocks(section)
        for block in blocks:
            block_id = _unique_block_id(
                _build_block_id(
                    ticker=manifest_record.ticker,
                    fiscal_year=manifest_record.fiscal_year,
                    source_type=manifest_record.source_type,
                    item_code=section.item_code,
                    block_index=block.block_index,
                ),
                block_id_occurrences,
            )
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
                chunk_index = len(
                    [
                        chunk
                        for chunk in chunks
                        if chunk.item_code == section.item_code
                    ]
                ) + 1
                chunk_id = _build_chunk_id(
                    block_id=block_id,
                    block_part_index=block_part_index,
                    block_part_count=block_part_count,
                )
                chunks.append(
                    SecFilingChunk(
                        chunk_id=chunk_id,
                        ticker=manifest_record.ticker,
                        company=manifest_record.company,
                        fiscal_year=manifest_record.fiscal_year,
                        category=manifest_record.category,
                        category_slug=manifest_record.category_slug,
                        source_type=manifest_record.source_type,
                        form_type=manifest_record.form_type,
                        source_tier=manifest_record.source_tier,
                        period_end=manifest_record.period_end,
                        period_type=manifest_record.period_type,
                        duration_months=manifest_record.duration_months,
                        fiscal_period=manifest_record.fiscal_period,
                        section=section.section,
                        item_code=section.item_code,
                        chunk_index=chunk_index,
                        block_id=block_id,
                        block_index=block.block_index,
                        block_heading=block.block_heading,
                        block_type=block.block_type,
                        block_char_start=block.char_start,
                        block_char_end=block.char_end,
                        block_part_index=block_part_index,
                        block_part_count=block_part_count,
                        contains_table=_contains_table_block(chunk_text),
                        text=chunk_text,
                        char_start=char_start,
                        char_end=char_end,
                        source_url=manifest_record.filing_url,
                        local_path=manifest_record.html_path,
                        metadata={
                            "accession_number": manifest_record.accession_number,
                            "filing_date": manifest_record.filing_date,
                            "report_date": manifest_record.report_date,
                            "period_end": manifest_record.period_end,
                            "period_type": manifest_record.period_type,
                            "duration_months": manifest_record.duration_months,
                            "fiscal_period": manifest_record.fiscal_period,
                            "fiscal_period_source": manifest_record.metadata.get("fiscal_period_source"),
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


def _serialize_html_table(table, table_index: int) -> str:
    rows: list[list[str]] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if not cells:
            cells = row.find_all(["th", "td"])
        values = [_clean_cell_text(cell.get_text(" ", strip=True)) for cell in cells]
        values = [value for value in values if value]
        if values:
            rows.append(values)

    lines = [f"[TABLE_START id={table_index} rows={len(rows)}]"]
    for row in rows:
        lines.append(" | ".join(row))
    lines.append("[TABLE_END]")
    return "\n".join(lines)


def _clean_cell_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def _contains_table_block(text: str) -> bool:
    return "[TABLE_START" in text and "[TABLE_END]" in text


def _build_chunk_id(
    block_id: str,
    block_part_index: int,
    block_part_count: int,
) -> str:
    if block_part_count <= 1:
        return f"{block_id}_CHUNK_0001"
    return f"{block_id}_PART_{block_part_index:02d}_OF_{block_part_count:02d}"


def _build_block_id(
    ticker: str,
    fiscal_year: int,
    source_type: str,
    item_code: str,
    block_index: int,
) -> str:
    source_key = re.sub(r"[^A-Z0-9]", "", source_type.upper())
    item_key = f"ITEM{item_code.upper()}"
    return f"{ticker.upper()}_{fiscal_year}_{source_key}_{item_key}_BLOCK_{block_index:04d}"


def _unique_block_id(base_block_id: str, occurrences: dict[str, int]) -> str:
    occurrence = occurrences.get(base_block_id, 0) + 1
    occurrences[base_block_id] = occurrence
    if occurrence == 1:
        return base_block_id
    return f"{base_block_id}_OCC_{occurrence:02d}"
