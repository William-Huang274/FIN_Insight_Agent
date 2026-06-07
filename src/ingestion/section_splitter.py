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
    SectionDefinition(
        "1",
        "Item 1. Business",
        (
            "item1business",
            "items1and2business",
            "item1and2business",
            "item1generalcorporatestructureandbusiness",
            "item1generalbusiness",
            "item1corporatestructureandbusiness",
            "em1business",
            "tem1business",
            "m1business",
        ),
    ),
    SectionDefinition(
        "1A",
        "Item 1A. Risk Factors",
        ("item1ariskfactors", "em1ariskfactors", "tem1ariskfactors", "m1ariskfactors"),
    ),
    SectionDefinition("1B", "Item 1B. Unresolved Staff Comments", ("item1bunresolvedstaffcomments",)),
    SectionDefinition("1C", "Item 1C. Cybersecurity", ("item1ccybersecurity",)),
    SectionDefinition("2", "Item 2. Properties", ("item2properties",)),
    SectionDefinition("3", "Item 3. Legal Proceedings", ("item3legalproceedings",)),
    SectionDefinition("4", "Item 4. Mine Safety Disclosures", ("item4minesafety",)),
    SectionDefinition("5", "Item 5. Market for Registrant's Common Equity", ("item5marketforregistrants",)),
    SectionDefinition("6", "Item 6. Reserved", ("item6reserved",)),
    SectionDefinition(
        "7",
        "Item 7. Management's Discussion and Analysis",
        (
            "item7management",
            "items7and7amanagement",
            "item7and7amanagement",
            "em7management",
            "tem7management",
            "m7management",
        ),
    ),
    SectionDefinition(
        "7A",
        "Item 7A. Quantitative and Qualitative Disclosures About Market Risk",
        (
            "item7aquantitativeandqualitative",
            "em7aquantitativeandqualitative",
            "tem7aquantitativeandqualitative",
        ),
    ),
    SectionDefinition(
        "8",
        "Item 8. Financial Statements and Supplementary Data",
        (
            "item8financialstatements",
            "item8consolidatedfinancialstatements",
            "em8financialstatements",
            "em8consolidatedfinancialstatements",
            "tem8financialstatements",
            "tem8consolidatedfinancialstatements",
            "m8financialstatements",
            "m8consolidatedfinancialstatements",
        ),
    ),
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

QUARTERLY_SECTION_DEFINITIONS: tuple[SectionDefinition, ...] = (
    SectionDefinition(
        "1",
        "Item 1. Financial Statements",
        (
            "item1financialstatements",
            "item1condensedconsolidatedfinancialstatements",
        ),
    ),
    SectionDefinition(
        "2",
        "Item 2. Management's Discussion and Analysis",
        (
            "item2management",
            "items2and3management",
            "item2and3management",
            "financialreview",
        ),
    ),
    SectionDefinition("3", "Item 3. Quantitative and Qualitative Disclosures About Market Risk", ("item3quantitativeandqualitative",)),
    SectionDefinition("4", "Item 4. Controls and Procedures", ("item4controlsandprocedures",)),
    SectionDefinition("1A", "Item 1A. Risk Factors", ("item1ariskfactors",)),
)
QUARTERLY_SECTION_DEFINITION_BY_ITEM = {
    definition.item_code: definition for definition in QUARTERLY_SECTION_DEFINITIONS
}
DEFAULT_10Q_OUTPUT_ITEMS = ("1", "2", "3", "4", "1A")
DEFAULT_20F_OUTPUT_ITEMS = DEFAULT_OUTPUT_ITEMS
DEFAULT_40F_OUTPUT_ITEMS = ("1", "1A", "7", "8")
FOREIGN_ANNUAL_SECTION_TITLES = {
    "1": "Form 20-F Item 4. Information on the Company",
    "1A": "Form 20-F Item 3.D. Risk Factors",
    "7": "Form 20-F Item 5. Operating and Financial Review and Prospects",
    "7A": "Form 20-F Item 11. Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Form 20-F Item 18. Financial Statements",
}
CANADIAN_ANNUAL_SECTION_TITLES = {
    "1": "Form 40-F Annual Information Form - Business",
    "1A": "Form 40-F Annual Information Form - Risk Factors",
    "7": "Form 40-F Management's Discussion and Analysis",
    "7A": "Form 40-F Market Risk and Financial Instruments",
    "8": "Form 40-F Audited Financial Statements",
}


class SecFilingSection(BaseModel):
    item_code: str
    section: str
    char_start: int
    char_end: int
    text: str


class SecSemanticBlock(BaseModel):
    item_code: str
    section: str
    block_index: int
    block_heading: str
    block_type: str
    char_start: int
    char_end: int
    text: str = Field(min_length=1)


class SecFilingChunk(BaseModel):
    chunk_id: str
    ticker: str
    company: str | None = None
    fiscal_year: int
    category: str | None = None
    category_slug: str | None = None
    source_type: str
    form_type: str
    source_tier: str = "primary_sec_filing"
    period_end: str | None = None
    period_type: str | None = None
    duration_months: int | None = None
    fiscal_period: str | None = None
    section: str
    item_code: str
    chunk_index: int
    block_id: str
    block_index: int
    block_heading: str
    block_type: str
    block_char_start: int
    block_char_end: int
    block_part_index: int
    block_part_count: int
    contains_table: bool = False
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
    if sections:
        missing_required = _missing_required_items(
            sections,
            required_items=_required_items_for_output_filter(
                output_item_set,
                default_items=DEFAULT_OUTPUT_ITEMS,
            ),
        )
        if missing_required:
            sections = _merge_missing_sections(
                primary_sections=sections,
                fallback_sections=_find_nontraditional_10k_sections(
                    text=text,
                    output_item_set=output_item_set,
                    min_section_chars=min_section_chars,
                ),
                missing_items=missing_required,
            )
        return sections

    return _find_nontraditional_10k_sections(
        text=text,
        output_item_set=output_item_set,
        min_section_chars=min_section_chars,
    )


def find_sec_filing_sections(
    text: str,
    form_type: str = "10-K",
    output_items: Iterable[str] | None = None,
    min_start_span_chars: int = 3000,
    min_section_chars: int = 100,
) -> list[SecFilingSection]:
    normalized_form = str(form_type or "").upper().strip()
    if normalized_form == "10-Q":
        return find_10q_sections(
            text=text,
            output_items=output_items,
            min_section_chars=min_section_chars,
        )
    if normalized_form == "20-F":
        return find_20f_sections(
            text=text,
            output_items=output_items if output_items is not None else DEFAULT_20F_OUTPUT_ITEMS,
            min_section_chars=min_section_chars,
        )
    if normalized_form == "40-F":
        return find_40f_sections(
            text=text,
            output_items=output_items if output_items is not None else DEFAULT_40F_OUTPUT_ITEMS,
            min_section_chars=min_section_chars,
        )
    return find_10k_sections(
        text=text,
        output_items=output_items if output_items is not None else DEFAULT_OUTPUT_ITEMS,
        min_start_span_chars=min_start_span_chars,
        min_section_chars=min_section_chars,
    )


def find_10q_sections(
    text: str,
    output_items: Iterable[str] | None = DEFAULT_10Q_OUTPUT_ITEMS,
    min_start_span_chars: int = 1000,
    min_section_chars: int = 100,
) -> list[SecFilingSection]:
    output_item_set = _normalize_item_filter(output_items)
    candidates = _dedupe_close_candidates(
        _find_section_candidates_with_definitions(
            text=text,
            definitions_by_item=QUARTERLY_SECTION_DEFINITION_BY_ITEM,
        )
    )
    if candidates:
        actual_start = _find_actual_item_start(
            candidates=candidates,
            text=text,
            preferred_item_code="1",
            min_start_span_chars=min_start_span_chars,
        )
        candidates = [candidate for candidate in candidates if candidate["start"] >= actual_start]

    sections = _sections_from_10q_candidates(
        candidates=candidates,
        text=text,
        output_item_set=output_item_set,
        min_section_chars=min_section_chars,
    )
    if _has_primary_10q_section_coverage(sections, text):
        return sections

    nontraditional_sections = _find_nontraditional_10q_sections(
        text=text,
        output_item_set=output_item_set,
        min_section_chars=min_section_chars,
    )
    if nontraditional_sections:
        return _merge_missing_sections(
            primary_sections=sections,
            fallback_sections=nontraditional_sections,
            missing_items=_missing_required_items(
                sections,
                required_items=_required_items_for_output_filter(
                    output_item_set,
                    default_items=("1", "2"),
                ),
            ),
        )
    return sections


def find_20f_sections(
    text: str,
    output_items: Iterable[str] | None = DEFAULT_20F_OUTPUT_ITEMS,
    min_section_chars: int = 100,
) -> list[SecFilingSection]:
    output_item_set = _normalize_item_filter(output_items)
    lines = _line_offsets(text)
    table_start_by_line_idx = _table_start_by_line_index(lines)
    lower_bound = max(8000, int(len(text) * 0.01))

    risk = _find_foreign_annual_marker(
        lines,
        markers=(
            "item 3.d. risk factors",
            "item 3.d risk factors",
            "3.d. risk factors",
            "d. risk factors",
            "risk factors",
            "risks relating to our business",
        ),
        after=lower_bound,
    )
    business = _find_foreign_annual_marker(
        lines,
        markers=(
            "item 4. information on the company",
            "item 4 information on the company",
            "4. information on the company",
            "b. business overview",
            "business overview of the company",
            "business overview",
            "at a glance",
        ),
        after=lower_bound,
    )
    operating_review_after = min(
        marker["start"] for marker in (risk, business) if marker is not None
    ) if risk is not None or business is not None else lower_bound
    operating_review = _find_foreign_annual_marker(
        lines,
        markers=(
            "item 5. operating and financial review and prospects",
            "item 5 operating and financial review and prospects",
            "item 5 operating and financial reviews and prospects",
            "5 operating and financial review and prospects",
            "5 operating and financial reviews and prospects",
            "operating and financial review and prospects",
            "operating and financial reviews and prospects",
            "operating results",
            "financial performance",
        ),
        after=operating_review_after + 1,
    )
    market_risk = _find_foreign_annual_marker(
        lines,
        markers=(
            "item 11. quantitative and qualitative disclosures about market risk",
            "item 11 quantitative and qualitative disclosures about market risk",
            "quantitative and qualitative disclosures about market risk",
            "market risk",
        ),
        after=(operating_review["start"] + 1) if operating_review is not None else lower_bound,
    )
    financial_after = max(
        marker["start"] for marker in (operating_review, market_risk, business, risk) if marker is not None
    ) if any(marker is not None for marker in (operating_review, market_risk, business, risk)) else lower_bound
    financials = _find_foreign_annual_marker(
        lines,
        markers=(
            "item 18. financial statements",
            "item 18 financial statements",
            "18. financial statements",
            "consolidated financial statements",
            "report of independent registered public accounting firm",
        ),
        after=financial_after + 1,
        allow_table_lines=True,
    )
    end_marker = _find_foreign_annual_marker(
        lines,
        markers=("signatures", "exhibits", "index to exhibits"),
        after=(financials["start"] + 1) if financials is not None else financial_after + 1,
    )

    candidates = [
        candidate
        for candidate in [
            _foreign_annual_candidate("1A", risk, table_start_by_line_idx),
            _foreign_annual_candidate("1", business, table_start_by_line_idx),
            _foreign_annual_candidate("7", operating_review, table_start_by_line_idx),
            _foreign_annual_candidate("7A", market_risk, table_start_by_line_idx),
            _foreign_annual_candidate("8", financials, table_start_by_line_idx),
            _end_boundary_candidate(end_marker, table_start_by_line_idx),
        ]
        if candidate is not None
    ]
    candidates.sort(key=lambda candidate: candidate["start"])
    candidates = _dedupe_nontraditional_boundaries(candidates)
    if not any(candidate["item_code"] in {"1", "1A", "7", "8"} for candidate in candidates):
        return []

    sections: list[SecFilingSection] = []
    for idx, candidate in enumerate(candidates):
        item_code = candidate["item_code"]
        if item_code == "__END__":
            continue
        if output_item_set is not None and item_code not in output_item_set:
            continue
        start = candidate["start"]
        end = candidates[idx + 1]["start"] if idx + 1 < len(candidates) else len(text)
        section_text = text[start:end].strip()
        if len(section_text) < min_section_chars:
            continue
        sections.append(
            SecFilingSection(
                item_code=item_code,
                section=str(candidate.get("section") or FOREIGN_ANNUAL_SECTION_TITLES[item_code]),
                char_start=start,
                char_end=end,
                text=section_text,
            )
        )
    return sections


def find_40f_sections(
    text: str,
    output_items: Iterable[str] | None = DEFAULT_40F_OUTPUT_ITEMS,
    min_section_chars: int = 100,
) -> list[SecFilingSection]:
    output_item_set = _normalize_item_filter(output_items)
    lines = _line_offsets(text)
    table_start_by_line_idx = _table_start_by_line_index(lines)
    is_materialized_package = _compact_text(text[:3000]).startswith("fin40fannualpackage")
    lower_bound = 0 if is_materialized_package else max(2500, int(len(text) * 0.005))

    aif_heading = _find_canadian_annual_marker(
        lines,
        markers=("fin 40-f annual information form",),
        after=lower_bound,
    ) if is_materialized_package else None
    financials_heading = _find_canadian_annual_marker(
        lines,
        markers=("fin 40-f financial statements",),
        after=(aif_heading["start"] + 1) if aif_heading is not None else lower_bound,
    ) if is_materialized_package else None
    mda_heading = _find_canadian_annual_marker(
        lines,
        markers=("fin 40-f mda", "fin 40-f management discussion and analysis"),
        after=(financials_heading["start"] + 1) if financials_heading is not None else (
            (aif_heading["start"] + 1) if aif_heading is not None else lower_bound
        ),
    ) if is_materialized_package else None
    aif_upper_bound = min(
        marker["start"]
        for marker in (financials_heading, mda_heading)
        if marker is not None
    ) if financials_heading is not None or mda_heading is not None else None

    business_markers = (
        "description of the business",
        "business overview",
        "our business",
        "operations",
    )
    if not is_materialized_package:
        business_markers = ("annual information form", *business_markers)
    aif = _find_canadian_annual_marker(
        lines,
        markers=business_markers,
        after=(aif_heading["start"] + 1) if aif_heading is not None else lower_bound,
        before=aif_upper_bound,
    ) or aif_heading
    risk = _find_canadian_annual_marker(
        lines,
        markers=(
            "risks that can affect our business",
            "risk factors",
            "risks and uncertainties",
            "risk factors and other key information",
            "principal risks",
        ),
        after=(aif_heading["start"] + 1) if aif_heading is not None else (
            (aif["start"] + 1) if aif is not None else lower_bound
        ),
        before=aif_upper_bound,
    )
    financials = financials_heading or _find_canadian_annual_marker(
        lines,
        markers=(
            "audited financial statements",
            "consolidated financial statements",
            "financial statements",
            "independent auditor's report",
            "independent auditors report",
        ),
        after=lower_bound,
        allow_table_lines=True,
    )
    mda = mda_heading or _find_canadian_annual_marker(
        lines,
        markers=(
            "management's discussion and analysis",
            "managements discussion and analysis",
            "management discussion and analysis",
            "md&a",
            "mda",
        ),
        after=lower_bound,
    )
    market_risk = None
    if output_item_set is None or "7A" in output_item_set:
        market_risk = _find_canadian_annual_marker(
            lines,
            markers=(
                "market risk",
                "financial instruments",
                "liquidity risk",
                "foreign exchange risk",
                "commodity price risk",
            ),
            after=(mda["start"] + 1) if mda is not None else lower_bound,
        )
    latest_section_start = max(
        marker["start"] for marker in (aif, risk, mda, financials, market_risk) if marker is not None
    ) if any(marker is not None for marker in (aif, risk, mda, financials, market_risk)) else lower_bound
    end_marker = _find_canadian_annual_marker(
        lines,
        markers=("signatures", "exhibit index", "list of exhibits"),
        after=latest_section_start + 1,
    )

    candidates = [
        candidate
        for candidate in [
            _canadian_annual_candidate("1", aif, table_start_by_line_idx),
            _canadian_annual_candidate("1A", risk, table_start_by_line_idx),
            _canadian_annual_candidate("8", financials, table_start_by_line_idx),
            _canadian_annual_candidate("7", mda, table_start_by_line_idx),
            _canadian_annual_candidate("7A", market_risk, table_start_by_line_idx),
            _end_boundary_candidate(end_marker, table_start_by_line_idx),
        ]
        if candidate is not None
    ]
    candidates.sort(key=lambda candidate: candidate["start"])
    candidates = _dedupe_nontraditional_boundaries(candidates)
    if not any(candidate["item_code"] in {"1", "1A", "7", "8"} for candidate in candidates):
        return []

    sections: list[SecFilingSection] = []
    for idx, candidate in enumerate(candidates):
        item_code = candidate["item_code"]
        if item_code == "__END__":
            continue
        if output_item_set is not None and item_code not in output_item_set:
            continue
        start = candidate["start"]
        end = candidates[idx + 1]["start"] if idx + 1 < len(candidates) else len(text)
        section_text = text[start:end].strip()
        if len(section_text) < min_section_chars:
            continue
        sections.append(
            SecFilingSection(
                item_code=item_code,
                section=str(candidate.get("section") or CANADIAN_ANNUAL_SECTION_TITLES[item_code]),
                char_start=start,
                char_end=end,
                text=section_text,
            )
        )
    return sections


def _sections_from_10q_candidates(
    candidates: list[dict],
    text: str,
    output_item_set: set[str] | None,
    min_section_chars: int,
) -> list[SecFilingSection]:
    if not candidates:
        return []

    sections: list[SecFilingSection] = []
    for idx, candidate in enumerate(candidates):
        item_code = candidate["item_code"]
        if item_code not in QUARTERLY_SECTION_DEFINITION_BY_ITEM:
            continue
        if output_item_set is not None and item_code not in output_item_set:
            continue

        start = candidate["start"]
        end = candidates[idx + 1]["start"] if idx + 1 < len(candidates) else len(text)
        section_text = text[start:end].strip()
        if len(section_text) < min_section_chars:
            continue

        definition = QUARTERLY_SECTION_DEFINITION_BY_ITEM[item_code]
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


def _has_primary_10q_section_coverage(sections: list[SecFilingSection], text: str) -> bool:
    if not sections:
        return False
    item_codes = {section.item_code for section in sections}
    if {"1", "2"}.issubset(item_codes):
        return True
    return False


def build_semantic_blocks(
    section: SecFilingSection,
) -> list[SecSemanticBlock]:
    paragraphs = _section_paragraphs(section)
    if not paragraphs:
        return []

    heading_indices = _find_semantic_heading_indices(paragraphs, section.item_code)
    boundaries = _build_block_boundaries(paragraphs, heading_indices, section)
    blocks: list[SecSemanticBlock] = []

    for block_index, boundary in enumerate(boundaries, start=1):
        start_idx = boundary["start_idx"]
        end_idx = (
            boundaries[block_index]["start_idx"]
            if block_index < len(boundaries)
            else len(paragraphs)
        )
        block_paragraphs = paragraphs[start_idx:end_idx]
        if not block_paragraphs:
            continue

        block_text = "\n".join(paragraph[0] for paragraph in block_paragraphs).strip()
        if not block_text:
            continue

        blocks.append(
            SecSemanticBlock(
                item_code=section.item_code,
                section=section.section,
                block_index=len(blocks) + 1,
                block_heading=boundary["heading"],
                block_type=_block_type_for_item(section.item_code, block_text),
                char_start=block_paragraphs[0][1],
                char_end=block_paragraphs[-1][2],
                text=block_text,
            )
        )

    return _merge_tiny_blocks(blocks)


def chunk_semantic_block(
    block: SecSemanticBlock,
    target_words: int = 900,
    overlap_words: int = 150,
    min_words: int = 80,
) -> list[tuple[str, int, int]]:
    paragraphs = _block_paragraphs(block)
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


def chunk_section(
    section: SecFilingSection,
    target_words: int = 900,
    overlap_words: int = 150,
    min_words: int = 80,
) -> list[tuple[str, int, int]]:
    chunks: list[tuple[str, int, int]] = []
    for block in build_semantic_blocks(section):
        chunks.extend(
            chunk_semantic_block(
                block,
                target_words=target_words,
                overlap_words=overlap_words,
                min_words=min_words,
            )
        )
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
    return _find_section_candidates_with_definitions(
        text=text,
        definitions_by_item=SECTION_DEFINITION_BY_ITEM,
    )


def _find_section_candidates_with_definitions(
    text: str,
    definitions_by_item: dict[str, SectionDefinition],
) -> list[dict]:
    lines = _line_offsets(text)
    table_start_by_line_idx = _table_start_by_line_index(lines)
    candidates: list[dict] = []
    for line_idx, (start, line) in enumerate(lines):
        combined = " ".join(
            candidate_line
            for _, candidate_line in lines[line_idx : line_idx + 12]
            if not _is_table_start(candidate_line) and not _is_table_end(candidate_line)
        )
        item_code = _parse_line_item_code(combined) or _parse_line_item_code(line)
        if item_code not in definitions_by_item:
            continue

        compact = _compact_text(combined)
        definition = definitions_by_item[item_code]
        if any(marker in compact[:260] for marker in definition.markers):
            candidate_start = table_start_by_line_idx.get(line_idx, start)
            candidates.append(
                {
                    "item_code": item_code,
                    "section": definition.canonical_title,
                    "start": candidate_start,
                    "line_idx": line_idx,
                }
            )
    return candidates


def _find_nontraditional_10k_sections(
    text: str,
    output_item_set: set[str] | None,
    min_section_chars: int,
) -> list[SecFilingSection]:
    """Handle readable 10-K layouts where formal Item labels only appear in an index."""
    lines = _line_offsets(text)
    table_start_by_line_idx = _table_start_by_line_index(lines)
    lower_bound = max(4500, int(len(text) * 0.01))

    item1_markers = (
        "a year in review",
        "about honeywell",
        "item 1 business",
        "item 1. business",
        "item 1 - business",
        "fundamentals of our business",
        "fundamental of our business",
        "business summary",
        "business overview",
        "business and properties",
        "corporate structure and business",
        "corporate structure and business and other information",
        "description of the business",
        "our business",
        "overview",
    )
    item1_probe = _find_nontraditional_marker(
        lines,
        markers=item1_markers,
        after=lower_bound,
    )
    item7_markers = (
        "item 7 management",
        "item 7. management",
        "item 7 - management",
        "items 7 and 7a management",
        "items 7. and 7a. management",
        "management's discussion and analysis",
        "managements discussion and analysis",
    )
    item7 = _find_nontraditional_marker(
        lines,
        markers=item7_markers,
        after=(item1_probe["start"] + 1) if item1_probe is not None else lower_bound,
    )
    if item7 is None:
        item7 = _find_nontraditional_marker(
            lines,
            markers=item7_markers,
            after=lower_bound,
        )
    if item7 is None:
        return []

    item1 = item1_probe if item1_probe is not None and item1_probe["start"] < item7["start"] else None
    if item1 is None:
        item1 = _find_nontraditional_marker(
            lines,
            markers=item1_markers,
            after=lower_bound,
            before=item7["start"],
        )
    item1a = _find_nontraditional_marker(
        lines,
        markers=("risk factors and other key information", "risk factors"),
        after=(item1["start"] + 1) if item1 is not None else lower_bound,
        before=item7["start"],
    )
    if item1a is None:
        item1a = _find_nontraditional_marker(
            lines,
            markers=("risk factors and other key information", "risk factors"),
            after=item7["start"] + 1,
        )
    item7a = _find_nontraditional_marker(
        lines,
        markers=("quantitative and qualitative disclosures about market risk",),
        after=item7["start"] + 1,
    )
    latest_before_item8 = max(
        marker["start"] for marker in (item7, item1a, item7a) if marker is not None
    )
    item8 = _find_nontraditional_marker(
        lines,
        markers=(
            "financial statements and supplemental details",
            "financial statements and supplementary data",
            "consolidated financial statements and supplementary data",
            "consolidated financial statements",
            "index to financial statements",
            "index to consolidated financial statements",
            "report of independent registered public accounting firm",
            "managements report on internal control over financial reporting",
        ),
        after=latest_before_item8 + 1,
    )

    candidates = [
        candidate
        for candidate in [
            _nontraditional_candidate("1", item1, table_start_by_line_idx),
            _nontraditional_candidate("7", item7, table_start_by_line_idx),
            _nontraditional_candidate("1A", item1a, table_start_by_line_idx),
            _nontraditional_candidate("7A", item7a, table_start_by_line_idx),
            _nontraditional_candidate("8", item8, table_start_by_line_idx),
        ]
        if candidate is not None
    ]
    candidates.sort(key=lambda candidate: candidate["start"])
    if not candidates:
        return []

    sections: list[SecFilingSection] = []
    for idx, candidate in enumerate(candidates):
        item_code = candidate["item_code"]
        if output_item_set is not None and item_code not in output_item_set:
            continue
        start = candidate["start"]
        end = candidates[idx + 1]["start"] if idx + 1 < len(candidates) else len(text)
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


def _find_nontraditional_10q_sections(
    text: str,
    output_item_set: set[str] | None,
    min_section_chars: int,
) -> list[SecFilingSection]:
    """Handle 10-Q layouts whose readable headings omit formal Item labels."""
    lines = _line_offsets(text)
    table_start_by_line_idx = _table_start_by_line_index(lines)
    lower_bound = max(2500, int(len(text) * 0.005))

    item2 = _find_nontraditional_marker(
        lines,
        markers=(
            "financial review",
            "item 2 management",
            "item 2 managements discussion",
            "item 2 management discussion",
            "items 2 and 3 management",
            "items 2. and 3. management",
            "item 2 and 3 management",
            "2 managements discussion",
            "2 management discussion",
            "managements discussion and analysis",
            "management discussion and analysis",
            "managements discussion and analysis of financial condition and results of operations",
        ),
        after=lower_bound,
    )
    item1_markers = (
        "consolidated condensed financial statements",
        "consolidated condensed statements of operations",
        "consolidated statements of operations",
        "consolidated statements of income",
        "consolidated balance sheets",
        "statement of operations unaudited",
        "financial statements and notes",
        "financial statements",
        "notes to consolidated financial statements",
        "notes to the consolidated financial statements",
        "notes to condensed consolidated financial statements",
        "notes to the condensed consolidated financial statements",
    )
    item1 = _find_nontraditional_marker(
        lines,
        markers=item1_markers,
        after=lower_bound,
        before=item2["start"] if item2 is not None else None,
        allow_table_lines=True,
    )
    if (
        item1 is not None
        and item2 is not None
        and item1["line_idx"] in table_start_by_line_idx
    ):
        actual_item1 = _find_nontraditional_marker(
            lines,
            markers=item1_markers,
            after=item2["start"] + 1,
            allow_table_lines=True,
        )
        if actual_item1 is not None:
            item1 = actual_item1
    if item1 is None and item2 is not None:
        item1 = _find_nontraditional_marker(
            lines,
            markers=item1_markers,
            after=item2["start"] + 1,
            allow_table_lines=True,
        )
    earliest_primary_start = min(
        marker["start"] for marker in (item1, item2) if marker is not None
    ) if item1 is not None or item2 is not None else lower_bound
    item1a = _find_nontraditional_marker(
        lines,
        markers=("risk factors and other key information", "risk factors"),
        after=earliest_primary_start + 1,
    )
    item3 = _find_nontraditional_marker(
        lines,
        markers=("quantitative and qualitative disclosures about market risk",),
        after=earliest_primary_start + 1,
    )
    item4 = _find_nontraditional_marker(
        lines,
        markers=("controls and procedures",),
        after=earliest_primary_start + 1,
    )
    latest_section_start = max(
        marker["start"]
        for marker in (item1, item2, item1a, item3, item4)
        if marker is not None
    ) if any(marker is not None for marker in (item1, item2, item1a, item3, item4)) else earliest_primary_start
    end_marker = _find_nontraditional_marker(
        lines,
        markers=("exhibits", "signatures", "form 10 q cross reference index"),
        after=latest_section_start + 1,
    )

    candidates = [
        candidate
        for candidate in [
            _nontraditional_candidate("1", item1, table_start_by_line_idx),
            _nontraditional_candidate("2", item2, table_start_by_line_idx),
            _nontraditional_candidate("1A", item1a, table_start_by_line_idx),
            _nontraditional_candidate("3", item3, table_start_by_line_idx),
            _nontraditional_candidate("4", item4, table_start_by_line_idx),
            _end_boundary_candidate(end_marker, table_start_by_line_idx),
        ]
        if candidate is not None
    ]
    candidates.sort(key=lambda candidate: candidate["start"])
    candidates = _dedupe_nontraditional_boundaries(candidates)
    if not any(candidate["item_code"] in {"1", "2"} for candidate in candidates):
        return []

    return _sections_from_10q_candidates(
        candidates=candidates,
        text=text,
        output_item_set=output_item_set,
        min_section_chars=min_section_chars,
    )


def _find_nontraditional_marker(
    lines: list[tuple[int, str]],
    markers: tuple[str, ...],
    after: int,
    before: int | None = None,
    allow_table_lines: bool = False,
) -> dict | None:
    marker_set = {_compact_text(marker) for marker in markers}
    for line_idx, (start, line) in enumerate(lines):
        if start < after:
            continue
        if before is not None and start >= before:
            break
        if "|" in line and not allow_table_lines:
            continue
        compact = _compact_text(line)
        if any(compact == marker or compact.startswith(marker) for marker in marker_set):
            if _is_cross_reference_marker(lines, line_idx):
                continue
            return {"start": start, "line_idx": line_idx, "line": line}
    return None


def _nontraditional_candidate(
    item_code: str,
    marker: dict | None,
    table_start_by_line_idx: dict[int, int] | None = None,
) -> dict | None:
    if marker is None:
        return None
    definition = (
        QUARTERLY_SECTION_DEFINITION_BY_ITEM.get(item_code)
        or SECTION_DEFINITION_BY_ITEM[item_code]
    )
    start = marker["start"]
    if table_start_by_line_idx is not None:
        start = table_start_by_line_idx.get(marker["line_idx"], start)
    return {
        "item_code": item_code,
        "section": definition.canonical_title,
        "start": start,
        "line_idx": marker["line_idx"],
    }


def _foreign_annual_candidate(
    item_code: str,
    marker: dict | None,
    table_start_by_line_idx: dict[int, int] | None = None,
) -> dict | None:
    if marker is None:
        return None
    start = marker["start"]
    if table_start_by_line_idx is not None:
        start = table_start_by_line_idx.get(marker["line_idx"], start)
    return {
        "item_code": item_code,
        "section": FOREIGN_ANNUAL_SECTION_TITLES[item_code],
        "start": start,
        "line_idx": marker["line_idx"],
    }


def _canadian_annual_candidate(
    item_code: str,
    marker: dict | None,
    table_start_by_line_idx: dict[int, int] | None = None,
) -> dict | None:
    if marker is None:
        return None
    start = marker["start"]
    if table_start_by_line_idx is not None:
        start = table_start_by_line_idx.get(marker["line_idx"], start)
    return {
        "item_code": item_code,
        "section": CANADIAN_ANNUAL_SECTION_TITLES[item_code],
        "start": start,
        "line_idx": marker["line_idx"],
    }


def _find_foreign_annual_marker(
    lines: list[tuple[int, str]],
    markers: tuple[str, ...],
    after: int,
    before: int | None = None,
    allow_table_lines: bool = False,
) -> dict | None:
    marker_set = {_compact_text(marker) for marker in markers}
    for line_idx, (start, line) in enumerate(lines):
        if start < after:
            continue
        if before is not None and start >= before:
            break
        if "|" in line and not allow_table_lines:
            continue
        compact = _compact_text(line)
        if any(compact == marker or compact.startswith(marker) or marker in compact[:180] for marker in marker_set):
            if _is_cross_reference_marker(lines, line_idx):
                continue
            return {"start": start, "line_idx": line_idx, "line": line}
    return None


def _find_canadian_annual_marker(
    lines: list[tuple[int, str]],
    markers: tuple[str, ...],
    after: int,
    before: int | None = None,
    allow_table_lines: bool = False,
    allow_contains: bool = False,
) -> dict | None:
    marker_set = {_compact_text(marker) for marker in markers}
    for line_idx, (start, line) in enumerate(lines):
        if start < after:
            continue
        if before is not None and start >= before:
            break
        if "|" in line and not allow_table_lines:
            continue
        compact = _compact_text(line)
        matched = any(
            compact == marker
            or compact.startswith(marker)
            or (allow_contains and marker in compact[:180])
            for marker in marker_set
        )
        if matched:
            if _is_cross_reference_marker(lines, line_idx):
                continue
            return {"start": start, "line_idx": line_idx, "line": line}
    return None


def _is_cross_reference_marker(lines: list[tuple[int, str]], line_idx: int) -> bool:
    previous_text = " ".join(
        line for _, line in lines[max(0, line_idx - 3) : line_idx]
    ).lower()
    next_text = " ".join(
        line for _, line in lines[line_idx + 1 : min(len(lines), line_idx + 4)]
    ).lower()

    previous_compact = _compact_text(previous_text)
    next_compact = _compact_text(next_text)
    if any(
        phrase in previous_compact
        for phrase in (
            "sectiontitled",
            "seethesection",
            "refertothesection",
            "refertothe",
        )
    ):
        return True
    return any(
        phrase in next_compact[:260]
        for phrase in (
            "andinotherpartsofthisreport",
            "foradiscussion",
            "foradditionalinformation",
            "sectionofmanagementsdiscussion",
            "sectionofmanagementsdiscussionandanalysis",
        )
    )


def _end_boundary_candidate(
    marker: dict | None,
    table_start_by_line_idx: dict[int, int] | None = None,
) -> dict | None:
    if marker is None:
        return None
    start = marker["start"]
    if table_start_by_line_idx is not None:
        start = table_start_by_line_idx.get(marker["line_idx"], start)
    return {"item_code": "__END__", "section": "End", "start": start, "line_idx": marker["line_idx"]}


def _dedupe_nontraditional_boundaries(candidates: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    for candidate in candidates:
        if (
            deduped
            and deduped[-1]["item_code"] == candidate["item_code"]
            and candidate["start"] - deduped[-1]["start"] <= 80
        ):
            deduped[-1] = candidate
            continue
        if deduped and deduped[-1]["start"] == candidate["start"]:
            continue
        deduped.append(candidate)
    return deduped


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


def _required_items_for_output_filter(
    output_item_set: set[str] | None,
    default_items: Iterable[str],
) -> set[str]:
    required = set(default_items)
    if output_item_set is None:
        return required
    return required.intersection(output_item_set)


def _missing_required_items(
    sections: list[SecFilingSection],
    required_items: set[str],
) -> set[str]:
    observed = {section.item_code for section in sections}
    return required_items - observed


def _merge_missing_sections(
    *,
    primary_sections: list[SecFilingSection],
    fallback_sections: list[SecFilingSection],
    missing_items: set[str],
) -> list[SecFilingSection]:
    if not missing_items or not fallback_sections:
        return primary_sections

    merged = list(primary_sections)
    observed = {section.item_code for section in merged}
    for section in fallback_sections:
        if section.item_code not in missing_items or section.item_code in observed:
            continue
        merged.append(section)
        observed.add(section.item_code)
    merged.sort(key=lambda section: (section.char_start, section.item_code))
    return merged


def _find_actual_item1_start(
    candidates: list[dict], text: str, min_start_span_chars: int
) -> int:
    return _find_actual_item_start(
        candidates=candidates,
        text=text,
        preferred_item_code="1",
        min_start_span_chars=min_start_span_chars,
    )


def _find_actual_item_start(
    candidates: list[dict],
    text: str,
    preferred_item_code: str,
    min_start_span_chars: int,
) -> int:
    for idx, candidate in enumerate(candidates):
        if candidate["item_code"] != preferred_item_code:
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
    match = re.match(
        r"(?i)^(?:items?|em|tem|m)\s+(\d{1,2})(?:\s*\(?\s*([a-z])\s*\)?)?\b",
        line.strip(),
    )
    if not match:
        return None
    return f"{match.group(1)}{match.group(2) or ''}".upper()


def _line_offsets(text: str) -> list[tuple[int, str]]:
    offsets: list[tuple[int, str]] = []
    pos = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped:
            offsets.append((pos + line.find(stripped), stripped))
        pos += len(line)
    return offsets


def _table_start_by_line_index(lines: list[tuple[int, str]]) -> dict[int, int]:
    table_start_by_line_idx: dict[int, int] = {}
    current_table_start: int | None = None
    for idx, (start, line) in enumerate(lines):
        if _is_table_start(line):
            current_table_start = start
        if current_table_start is not None:
            table_start_by_line_idx[idx] = current_table_start
        if _is_table_end(line):
            current_table_start = None
    return table_start_by_line_idx


def _section_paragraphs(section: SecFilingSection) -> list[tuple[str, int, int, int]]:
    return _paragraphs_with_table_blocks(section.text, section.char_start)


def _block_paragraphs(block: SecSemanticBlock) -> list[tuple[str, int, int, int]]:
    return _paragraphs_with_table_blocks(block.text, block.char_start)


def _paragraphs_with_table_blocks(
    text: str, base_char_start: int
) -> list[tuple[str, int, int, int]]:
    paragraphs: list[tuple[str, int, int, int]] = []
    lines: list[tuple[str, int, int]] = []
    pos = 0
    for raw_line in text.splitlines(keepends=True):
        stripped = raw_line.strip()
        if stripped:
            start = base_char_start + pos + raw_line.find(stripped)
            end = start + len(stripped)
            lines.append((stripped, start, end))
        pos += len(raw_line)

    idx = 0
    while idx < len(lines):
        line, start, end = lines[idx]
        if _is_table_start(line):
            table_lines = [line]
            table_start = start
            table_end = end
            idx += 1
            while idx < len(lines):
                next_line, _, next_end = lines[idx]
                table_lines.append(next_line)
                table_end = next_end
                idx += 1
                if _is_table_end(next_line):
                    break
            paragraph = "\n".join(table_lines).strip()
        else:
            paragraph = line
            table_start = start
            table_end = end
            idx += 1

        if not paragraph:
            continue
        paragraphs.append((paragraph, table_start, table_end, _word_count(paragraph)))
    return paragraphs


def _find_semantic_heading_indices(
    paragraphs: list[tuple[str, int, int, int]], item_code: str
) -> list[int]:
    heading_indices: list[int] = []
    for idx, paragraph in enumerate(paragraphs):
        line = paragraph[0]
        if _contains_table_block(line):
            continue
        prev_line = paragraphs[idx - 1][0] if idx > 0 else None
        next_line = paragraphs[idx + 1][0] if idx + 1 < len(paragraphs) else None
        if _is_semantic_heading(
            line=line,
            item_code=item_code,
            prev_line=prev_line,
            next_line=next_line,
        ):
            heading_indices.append(idx)
    return heading_indices


def _build_block_boundaries(
    paragraphs: list[tuple[str, int, int, int]],
    heading_indices: list[int],
    section: SecFilingSection,
) -> list[dict]:
    if not heading_indices:
        return [{"start_idx": 0, "heading": section.section}]

    boundaries: list[dict] = []
    first_heading_idx = heading_indices[0]
    if paragraphs[first_heading_idx][1] - section.char_start <= 600:
        boundaries.append(
            {
                "start_idx": 0,
                "heading": _clean_heading(paragraphs[first_heading_idx][0]),
            }
        )
        remaining_heading_indices = heading_indices[1:]
    else:
        boundaries.append({"start_idx": 0, "heading": section.section})
        remaining_heading_indices = heading_indices

    for heading_idx in remaining_heading_indices:
        heading = _clean_heading(paragraphs[heading_idx][0])
        if boundaries and heading_idx <= boundaries[-1]["start_idx"]:
            continue
        boundaries.append({"start_idx": heading_idx, "heading": heading})

    return boundaries


def _is_semantic_heading(
    line: str,
    item_code: str,
    prev_line: str | None,
    next_line: str | None,
) -> bool:
    stripped = line.strip()
    if not _is_heading_candidate_shape(stripped):
        return False
    if _is_noise_heading(stripped):
        return False
    if _parse_line_item_code(stripped):
        return False
    if next_line is not None and _is_noise_heading(next_line):
        return False

    word_count = _word_count(stripped)
    upper_ratio = _uppercase_ratio(stripped)
    has_lower = any(char.islower() for char in stripped)

    if item_code == "1A" and _looks_like_risk_heading(stripped, next_line):
        return True
    if item_code == "8":
        return _looks_like_financial_heading(stripped)
    if upper_ratio >= 0.72 and word_count <= 14:
        return True
    if has_lower and word_count <= 9 and _looks_like_title_heading(stripped, next_line):
        return True
    if stripped.endswith(":") and word_count <= 12:
        return True
    return False


def _is_heading_candidate_shape(line: str) -> bool:
    if _contains_table_block(line):
        return False
    if len(line) < 3 or len(line) > 220:
        return False
    if _word_count(line) > 28:
        return False
    if re.fullmatch(r"[\d\s.,$()%/-]+", line):
        return False
    if line.startswith(("•", "-", "*")):
        return False
    if line.count("|") >= 2:
        return False
    return True


def _is_noise_heading(line: str) -> bool:
    compact = _compact_text(line)
    if compact in {"tableofcontents", "parti", "partii", "partiii", "partiv"}:
        return True
    if compact in {"form10k", "annualreport", "index"}:
        return True
    if compact in {
        "inc",
        "usiness",
        "kfactors",
        "mentsandsupplementarydata",
        "financialconditionandresultsofoperations",
    }:
        return True
    if re.fullmatch(r"\d+", line.strip()):
        return True
    if re.search(r"\bpage\b\s*\d+", line, flags=re.IGNORECASE):
        return True
    if re.search(r"\b(year ended|in millions|in thousands|except per share)\b", line, flags=re.IGNORECASE):
        return True
    if _currency_or_number_token_count(line) >= 3:
        return True
    return False


def _looks_like_risk_heading(line: str, next_line: str | None) -> bool:
    if next_line is None or _word_count(next_line) < 12:
        return False
    compact = _compact_text(line)
    if len(compact) < 24:
        return False
    risk_terms = (
        "risk",
        "may",
        "could",
        "adverse",
        "failure",
        "fail",
        "unable",
        "depend",
        "subject",
        "uncertain",
        "competition",
        "regulation",
        "security",
        "privacy",
        "supply",
        "litigation",
        "intellectualproperty",
        "macroeconomic",
    )
    lowered = line.lower()
    return any(term in lowered or term in compact for term in risk_terms)


def _looks_like_financial_heading(line: str) -> bool:
    return bool(
        re.search(
            r"^\s*(note\s+\d+|consolidated\s+statements?|balance\s+sheets?|income\s+statements?|cash\s+flows?|stockholders|liabilities\s+and\s+stockholders)",
            line,
            flags=re.IGNORECASE,
        )
    )


def _looks_like_title_heading(line: str, next_line: str | None) -> bool:
    if next_line is None or _word_count(next_line) < 10:
        return False
    if line.endswith("."):
        return False
    title_terms = (
        "overview",
        "general",
        "revenue",
        "expenses",
        "income",
        "margin",
        "segment",
        "liquidity",
        "capital",
        "cash",
        "cloud",
        "gaming",
        "services",
        "products",
        "operations",
        "customers",
        "competition",
        "research",
        "development",
        "critical",
    )
    lowered = line.lower()
    return any(term in lowered for term in title_terms)


def _merge_tiny_blocks(
    blocks: list[SecSemanticBlock],
    min_words: int = 50,
) -> list[SecSemanticBlock]:
    if not blocks:
        return []
    if len(blocks) > 1 and _word_count(blocks[0].text) < min_words:
        first = blocks[0]
        second = blocks[1]
        blocks = [
            second.model_copy(
                update={
                    "char_start": first.char_start,
                    "text": f"{first.text}\n{second.text}",
                }
            )
        ] + blocks[2:]

    merged: list[SecSemanticBlock] = []
    for block in blocks:
        if merged and _word_count(block.text) < min_words:
            previous = merged[-1]
            merged[-1] = previous.model_copy(
                update={
                    "char_end": block.char_end,
                    "text": f"{previous.text}\n{block.text}",
                }
            )
        else:
            merged.append(block)

    renumbered: list[SecSemanticBlock] = []
    for idx, block in enumerate(merged, start=1):
        renumbered.append(block.model_copy(update={"block_index": idx}))
    return renumbered


def _block_type_for_item(item_code: str, block_text: str = "") -> str:
    if _contains_table_block(block_text):
        if item_code == "8":
            return "financial_table_or_note"
        return "table"
    return {
        "1": "business_subsection",
        "1A": "risk_factor",
        "7": "mdna_subsection",
        "7A": "market_risk_subsection",
        "8": "financial_statement_or_note",
    }.get(item_code, "section_subsection")


def _clean_heading(line: str) -> str:
    heading = re.sub(r"\s+", " ", line).strip()
    return heading.rstrip(":")


def _uppercase_ratio(line: str) -> float:
    letters = [char for char in line if char.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for char in letters if char.isupper()) / len(letters)


def _currency_or_number_token_count(line: str) -> int:
    return len(re.findall(r"[$]?\(?-?\d[\d,]*(?:\.\d+)?%?\)?", line))


def _is_table_start(line: str) -> bool:
    return line.startswith("[TABLE_START")


def _is_table_end(line: str) -> bool:
    return line == "[TABLE_END]"


def _contains_table_block(text: str) -> bool:
    return "[TABLE_START" in text and "[TABLE_END]" in text


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
