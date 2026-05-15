from __future__ import annotations

import re
from collections.abc import Iterable

from ingestion import SecFilingChunk

from .schema import EvidenceObject


EVIDENCE_TYPE_BY_ITEM = {
    "1": "business_description",
    "1A": "risk_disclosure",
    "7": "management_discussion",
    "7A": "market_risk_disclosure",
    "8": "financial_statement_or_note",
}


def build_evidence_from_chunks(
    chunks: Iterable[SecFilingChunk],
) -> list[EvidenceObject]:
    return [build_evidence_from_chunk(chunk) for chunk in chunks]


def build_evidence_from_chunk(chunk: SecFilingChunk) -> EvidenceObject:
    evidence_type = EVIDENCE_TYPE_BY_ITEM.get(chunk.item_code, "filing_disclosure")
    topics = infer_topics(chunk)
    return EvidenceObject(
        evidence_id=chunk.chunk_id,
        source_type=chunk.source_type,
        ticker=chunk.ticker,
        company=chunk.company,
        fiscal_year=chunk.fiscal_year,
        publication_date=chunk.metadata.get("filing_date"),
        section=chunk.section,
        subsection=chunk.block_heading,
        evidence_type=evidence_type,
        topics=topics,
        text=chunk.text,
        source_url=chunk.source_url,
        local_path=chunk.local_path,
        metadata={
            "category": chunk.category,
            "category_slug": chunk.category_slug,
            "form_type": chunk.form_type,
            "item_code": chunk.item_code,
            "chunk_index": chunk.chunk_index,
            "char_start": chunk.char_start,
            "char_end": chunk.char_end,
            "block_id": chunk.block_id,
            "block_index": chunk.block_index,
            "block_heading": chunk.block_heading,
            "block_type": chunk.block_type,
            "block_char_start": chunk.block_char_start,
            "block_char_end": chunk.block_char_end,
            "block_part_index": chunk.block_part_index,
            "block_part_count": chunk.block_part_count,
            "contains_table": chunk.contains_table,
            **chunk.metadata,
        },
    )


def infer_topics(chunk: SecFilingChunk) -> list[str]:
    candidates = [chunk.block_heading, chunk.section]
    text = " ".join(value for value in candidates if value)
    raw_terms = re.findall(r"[A-Za-z][A-Za-z0-9&'/-]{2,}", text)
    stopwords = {
        "item",
        "management",
        "discussion",
        "analysis",
        "financial",
        "statements",
        "supplementary",
        "data",
        "risk",
        "factors",
        "business",
        "and",
        "the",
        "with",
        "for",
        "about",
        "our",
    }
    topics: list[str] = []
    for term in raw_terms:
        normalized = term.strip("-/").lower()
        if normalized in stopwords or len(normalized) < 3:
            continue
        if normalized not in topics:
            topics.append(normalized)
    return topics[:8]
