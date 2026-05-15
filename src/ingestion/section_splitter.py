from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class SectionDefinition:
    item_code: str
    canonical_title: str
    markers: tuple[str, ...]


SECTION_DEFINITIONS: tuple[SectionDefinition, ...] = (
    SectionDefinition("1", "Item 1. Business", ("item1business",)),
    SectionDefinition("1A", "Item 1A. Risk Factors", ("item1ariskfactors",)),
    SectionDefinition("1B", "Item 1B. Unresolved Staff Comments", ("item1bunresolvedstaffcomments",)),
    SectionDefinition("1C", "Item 1C. Cybersecurity", ("item1ccybersecurity",)),
    SectionDefinition("2", "Item 2. Properties", ("item2properties",)),
    SectionDefinition("3", "Item 3. Legal Proceedings", ("item3legalproceedings",)),
    SectionDefinition("4", "Item 4. Mine Safety Disclosures", ("item4minesafety",)),
    SectionDefinition("5", "Item 5. Market for Registrant's Common Equity", ("item5marketforregistrants",)),
    SectionDefinition("6", "Item 6. Reserved", ("item6reserved",)),
    SectionDefinition("7", "Item 7. Management's Discussion and Analysis", ("item7management",)),
    SectionDefinition("7A", "Item 7A. Quantitative and Qualitative Disclosures About Market Risk", ("item7aquantitativeandqualitative",)),
    SectionDefinition("8", "Item 8. Financial Statements and Supplementary Data", ("item8financialstatements",)),
    SectionDefinition("9", "Item 9. Changes in and Disagreements With Accountants", ("item9changesinanddisagreements",)),
    SectionDefinition("9A", "Item 9A. Controls and Procedures", ("item9acontrolsandprocedures",)),
    SectionDefinition("9B", "Item 9B. Other Information", ("item9botherinformation",)),
    SectionDefinition("9C", "Item 9C. Disclosure Regarding Foreign Jurisdictions", ("item9cdisclosure",)),
    SectionDefinition("10", "Item 10. Directors, Executive Officers and Corporate Governance", ("item10directors", "item10director")),
    SectionDefinition("11", "Item 11. Executive Compensation", ("item11executivecompensation",)),
    SectionDefinition("12", "Item 12. Security Ownership", ("item12securityownership",)),
    SectionDefinition("13", "Item 13. Certain Relationships and Related Transactions", ("item13certainrelationships",)),
    SectionDefinition("14", "Item 14. Principal Accountant Fees and Services", ("item14principalaccountant",)),
    SectionDefinition("15", "Item 15. Exhibits and Financial Statement Schedules", ("item15exhibits",)),
)

SECTION_DEFINITION_BY_ITEM = {
    definition.item_code: definition for definition in SECTION_DEFINITIONS
}
DEFAULT_OUTPUT_ITEMS = ("1", "1A", "7", "7A", "8")


class SecFilingSection(BaseModel):
    item_code: str
    section: str
    char_start: int
    char_end: int
    text: str


class SecFilingChunk(BaseModel):
    chunk_id: str
    ticker: str
    company: str | None = None
    fiscal_year: int
    category: str | None = None
    category_slug: str | None = None
    source_type: str
    form_type: str
    section: str
    item_code: str
    chunk_index: int
    text: str = Field(min_length=1)
    char_start: int
    char_end: int
    source_url: str | None = None
    local_path: str
    metadata: dict = Field(default_factory=dict)

    def to_jsonl_line(self) -> str:
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False)


def find_10k_sections(
    text: str,
    output_items: Iterable[str] | None = DEFAULT_OUTPUT_ITEMS,
    min_start_span_chars: int = 3000,
    min_section_chars: int = 100,
) -> list[SecFilingSection]:
    output_item_set = _normalize_item_filter(output_items)
    candidates = _dedupe_close_candidates(_find_section_candidates(text))
    if not candidates:
        return []

    actual_start = _find_actual_item1_start(candidates, text, min_start_span_chars)
    boundary_candidates = [candidate for candidate in candidates if candidate["start"] >= actual_start]
    if not boundary_candidates:
        return []

    sections: list[SecFilingSection] = []
    for idx, candidate in enumerate(boundary_candidates):
        item_code = candidate["item_code"]
        if output_item_set is not None and item_code not in output_item_set:
            continue

        start = candidate["start"]
        end = (
            boundary_candidates[idx + 1]["start"]
            if idx + 1 < len(boundary_candidates)
            else len(text)
        )
        section_text = text[start:end].strip()
        if len(section_text) < min_section_chars:
            continue

        definition = SECTION_DEFINITION_BY_ITEM[item_code]
        sections.append(
            SecFilingSection(
                item_code=item_code,
                section=definition.canonical_title,
                char_start=start,
                char_end=end,
                text=section_text,
            )
        )
    return sections


def chunk_section(
    section: SecFilingSection,
    target_words: int = 900,
    overlap_words: int = 150,
    min_words: int = 80,
) -> list[tuple[str, int, int]]:
    paragraphs = _section_paragraphs(section)
    if not paragraphs:
        return []

    chunks: list[tuple[str, int, int]] = []
    current: list[tuple[str, int, int, int]] = []
    current_words = 0

    for paragraph in paragraphs:
        current.append(paragraph)
        current_words += paragraph[3]
        if current_words >= target_words:
            _append_chunk(chunks, current, min_words=min_words, force=True)
            current = _overlap_tail(current, overlap_words)
            current_words = sum(item[3] for item in current)

    if current:
        _append_chunk(chunks, current, min_words=min_words, force=not chunks)
    return chunks


def write_chunks_jsonl(chunks: Iterable[SecFilingChunk], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(chunk.to_jsonl_line())
            f.write("\n")


def read_chunks_jsonl(path: str | Path) -> list[SecFilingChunk]:
    input_path = Path(path)
    chunks: list[SecFilingChunk] = []
    with input_path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                chunks.append(SecFilingChunk.model_validate_json(stripped))
            except ValueError as exc:
                raise ValueError(
                    f"Invalid SEC filing chunk JSONL at {input_path}:{line_number}"
                ) from exc
    return chunks


def _find_section_candidates(text: str) -> list[dict]:
    lines = _line_offsets(text)
    candidates: list[dict] = []
    for line_idx, (start, line) in enumerate(lines):
        item_code = _parse_line_item_code(line)
        if item_code not in SECTION_DEFINITION_BY_ITEM:
            continue

        combined = " ".join(candidate_line for _, candidate_line in lines[line_idx : line_idx + 12])
        compact = _compact_text(combined)
        definition = SECTION_DEFINITION_BY_ITEM[item_code]
        if any(marker in compact[:260] for marker in definition.markers):
            candidates.append(
                {
                    "item_code": item_code,
                    "section": definition.canonical_title,
                    "start": start,
                    "line_idx": line_idx,
                }
            )
    return candidates


def _dedupe_close_candidates(candidates: list[dict], close_chars: int = 80) -> list[dict]:
    deduped: list[dict] = []
    for candidate in candidates:
        if (
            deduped
            and deduped[-1]["item_code"] == candidate["item_code"]
            and candidate["start"] - deduped[-1]["start"] <= close_chars
        ):
            deduped[-1] = candidate
        else:
            deduped.append(candidate)
    return deduped


def _find_actual_item1_start(
    candidates: list[dict], text: str, min_start_span_chars: int
) -> int:
    for idx, candidate in enumerate(candidates):
        if candidate["item_code"] != "1":
            continue
        next_start = candidates[idx + 1]["start"] if idx + 1 < len(candidates) else len(text)
        if next_start - candidate["start"] >= min_start_span_chars:
            return candidate["start"]

    lower_bound = max(1000, int(len(text) * 0.05))
    for candidate in candidates:
        if candidate["start"] >= lower_bound:
            return candidate["start"]
    return candidates[0]["start"]


def _parse_line_item_code(line: str) -> str | None:
    match = re.match(r"(?i)^item\s+(\d{1,2}[a-z]?)\b", line.strip())
    if not match:
        return None
    return match.group(1).upper()


def _line_offsets(text: str) -> list[tuple[int, str]]:
    offsets: list[tuple[int, str]] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped:
            offsets.append((pos + line.find(stripped), stripped))
        pos += len(line)
    return offsets


def _section_paragraphs(section: SecFilingSection) -> list[tuple[str, int, int, int]]:
    paragraphs: list[tuple[str, int, int, int]] = []
    for match in re.finditer(r"[^\n]+", section.text):
        paragraph = match.group(0).strip()
        if not paragraph:
            continue
        start = section.char_start + match.start()
        end = section.char_start + match.end()
        paragraphs.append((paragraph, start, end, _word_count(paragraph)))
    return paragraphs


def _append_chunk(
    chunks: list[tuple[str, int, int]],
    paragraphs: list[tuple[str, int, int, int]],
    min_words: int,
    force: bool = False,
) -> None:
    if not paragraphs:
        return
    word_count = sum(item[3] for item in paragraphs)
    if word_count < min_words and not force:
        return
    text = "\n".join(item[0] for item in paragraphs).strip()
    chunks.append((text, paragraphs[0][1], paragraphs[-1][2]))


def _overlap_tail(
    paragraphs: list[tuple[str, int, int, int]], overlap_words: int
) -> list[tuple[str, int, int, int]]:
    if overlap_words <= 0:
        return []
    tail: list[tuple[str, int, int, int]] = []
    total = 0
    for paragraph in reversed(paragraphs):
        if tail and total + paragraph[3] > overlap_words:
            break
        tail.append(paragraph)
        total += paragraph[3]
    return list(reversed(tail))


def _normalize_item_filter(values: Iterable[str] | None) -> set[str] | None:
    if values is None:
        return None
    return {value.upper() for value in values}


def _compact_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _word_count(value: str) -> int:
    return len(re.findall(r"\S+", value))
