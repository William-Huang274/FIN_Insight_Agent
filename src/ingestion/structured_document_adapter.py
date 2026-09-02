"""Thin adapters from mature document parsers into FIN's canonical tree.

The module owns projection and lineage only.  It does not decide whether a
retrieved chunk is Evidence or a NumericFact.  SEC filing structure is
delegated to ``sec2md``; ordinary HTML extraction is delegated to
``trafilatura``; born-digital PDF text is delegated to ``pypdf``; and generic
section splitting is delegated to Haystack's ``DocumentSplitter``.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
import re
from typing import Any, Iterable, Mapping, Sequence
from xml.etree import ElementTree


DOCUMENT_SCHEMA = "fin_ia_structured_document_v1_0"
SECTION_SCHEMA = "fin_ia_structured_section_v1_0"
BLOCK_SCHEMA = "fin_ia_structured_block_v1_0"
CHUNK_SCHEMA = "fin_ia_structured_retrieval_chunk_v1_1"

_SEC_PROFILES = frozenset(
    {"sec2md_10k", "sec2md_10q", "sec2md_exhibit"}
)
_IMAGE_MARKDOWN_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


class StructuredDocumentError(ValueError):
    """A source or parser result violates the canonical projection contract."""


@dataclass(frozen=True)
class StructuredSourceDescriptor:
    route_id: str
    title: str
    publisher: str
    issuer_id: str
    ticker: str
    company: str
    publication_date: str
    fiscal_period: str
    period_end: str
    source_role: str
    document_kind: str
    stable_url: str
    branches: tuple[str, ...]
    raw_body_sha256: str

    @classmethod
    def from_mapping(
        cls,
        value: Mapping[str, Any],
        *,
        raw_body_sha256: str,
    ) -> "StructuredSourceDescriptor":
        branches_value = value.get("branches")
        if not isinstance(branches_value, list):
            raise StructuredDocumentError("structured_source_branches_invalid")
        branches = tuple(str(item).strip() for item in branches_value)
        fields = {
            "route_id": str(value.get("route_id") or "").strip(),
            "title": str(value.get("title") or "").strip(),
            "publisher": str(value.get("publisher") or "").strip(),
            "issuer_id": str(value.get("issuer_id") or "").strip(),
            "ticker": str(value.get("ticker") or "").strip().upper(),
            "company": str(value.get("company") or "").strip(),
            "publication_date": str(value.get("publication_date") or "").strip(),
            "fiscal_period": str(value.get("fiscal_period") or "").strip(),
            "period_end": str(value.get("period_end") or "").strip(),
            "source_role": str(value.get("source_role") or "").strip(),
            "document_kind": str(value.get("document_kind") or "").strip(),
            "stable_url": str(value.get("stable_url") or "").strip(),
            "raw_body_sha256": raw_body_sha256.strip().lower(),
        }
        if (
            any(
                not fields[name]
                for name in (
                    "route_id",
                    "title",
                    "publisher",
                    "issuer_id",
                    "company",
                    "publication_date",
                    "source_role",
                    "document_kind",
                    "stable_url",
                    "raw_body_sha256",
                )
            )
            or fields["document_kind"] not in {"html", "pdf"}
            or not fields["stable_url"].startswith("https://")
            or not re.fullmatch(r"[0-9a-f]{64}", fields["raw_body_sha256"])
            or not branches
            or any(not item for item in branches)
            or len(set(branches)) != len(branches)
        ):
            raise StructuredDocumentError("structured_source_descriptor_invalid")
        return cls(**fields, branches=branches)


@dataclass(frozen=True)
class _RawBlock:
    kind: str
    content: str
    page_start: int | None = None
    page_end: int | None = None
    element_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class _RawSection:
    path: tuple[str, ...]
    blocks: tuple[_RawBlock, ...]
    part: str | None = None
    item: str | None = None
    item_title: str | None = None
    page_start: int | None = None
    page_end: int | None = None


def _package_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError as exc:
        raise StructuredDocumentError(
            f"structured_parser_dependency_unavailable:{name}"
        ) from exc


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}::{sha256(payload).hexdigest()[:24].upper()}"


def _content_sha256(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _clean_text(text: Any) -> str:
    value = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _image_references(text: str) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    rows: list[dict[str, str]] = []
    for alt, target in _IMAGE_MARKDOWN_RE.findall(text):
        identity = (alt.strip(), target.strip())
        if identity in seen:
            continue
        seen.add(identity)
        rows.append({"alt": identity[0], "target": identity[1]})
    return rows


def _markdown_table_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [
            cell.strip().replace("\\|", "|")
            for cell in re.split(r"(?<!\\)\|", stripped[1:-1])
        ]
        if cells and not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            rows.append(cells)
    return rows


def _footnote_markers(text: str) -> list[str]:
    # A parenthesized negative value such as ``(13)%`` or ``$(66)`` is not a
    # footnote marker.  Parenthesized numeric cells are ambiguous in plain
    # Markdown and overwhelmingly represent accounting negatives in this
    # corpus.  Numeric table markers are handled separately by requiring a
    # corresponding explanatory row in the same source document.
    markers = set(
        re.findall(r"(?<!\w)\(([a-z])\)(?!\w)", text, flags=re.IGNORECASE)
    )
    return sorted(markers)


def _table_footnote_candidates(text: str) -> tuple[set[str], set[str]]:
    """Return table label references and explicit explanatory-row markers.

    A numeric marker is not promoted merely because ``(n)`` appears.  It must
    occur at the end of an alphabetic label cell and be backed by a table row
    whose first non-empty cell is exactly ``(n)`` and whose remaining cells
    contain explanatory prose.  The definition may live in a separate table
    block in the same source document (as in Amazon and Micron releases).
    """

    references: set[str] = set()
    definitions: set[str] = set()
    for row in _markdown_table_rows(text):
        nonempty = [cell.strip() for cell in row if cell.strip()]
        if not nonempty:
            continue
        definition_match = re.fullmatch(r"\((\d{1,3})\)", nonempty[0])
        explanation = " ".join(nonempty[1:])
        if (
            definition_match
            and len(explanation) >= 16
            and re.search(r"[A-Za-z]", explanation)
        ):
            definitions.add(definition_match.group(1))
        for cell in nonempty:
            if "$" in cell or not re.search(r"[A-Za-z]", cell):
                continue
            reference_match = re.search(r"\((\d{1,3})\)\s*$", cell)
            if reference_match:
                references.add(reference_match.group(1))
    return references, definitions


def _element_tag(element: ElementTree.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].casefold()


def _xml_table_markdown(element: ElementTree.Element) -> str:
    """Project Trafilatura's row/cell XML without re-parsing source HTML.

    Trafilatura already owns extraction.  This helper only retains the row
    boundary and declared spans that would otherwise be flattened by
    ``itertext``.  Colspans are represented by empty cells so the resulting
    Markdown remains useful to a table-node retriever.
    """

    rows: list[list[str]] = []
    for row in element.iter():
        if _element_tag(row) != "row":
            continue
        cells: list[str] = []
        for cell in row:
            if _element_tag(cell) != "cell":
                continue
            content = _clean_text(" ".join(cell.itertext())).replace("|", "\\|")
            try:
                colspan = max(1, int(cell.attrib.get("colspan") or 1))
            except (TypeError, ValueError):
                colspan = 1
            cells.append(content)
            cells.extend("" for _ in range(colspan - 1))
        if cells and any(cells):
            rows.append(cells)
    if not rows:
        return _clean_text(" ".join(element.itertext()))
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    separator = ["---"] * width

    def render(row: Sequence[str]) -> str:
        return "| " + " | ".join(row) + " |"

    return "\n".join(
        [render(normalized[0]), render(separator)]
        + [render(row) for row in normalized[1:]]
    )


def _section_text(blocks: Sequence[_RawBlock]) -> tuple[str, list[tuple[int, int]]]:
    pieces: list[str] = []
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for block in blocks:
        if pieces:
            pieces.append("\n\n")
            cursor += 2
        start = cursor
        pieces.append(block.content)
        cursor += len(block.content)
        offsets.append((start, cursor))
    return "".join(pieces), offsets


def _ordered_chunk_block_indices(
    candidate_block_ids: Iterable[str],
    section_block_ids: Sequence[str],
) -> list[int]:
    """Return a unique canonical block order for one retrieval chunk.

    Parser chunkers may repeat the same element in their payload while
    applying overlap.  Retrieval lineage is block-occurrence based, so a
    canonical source block must be projected at most once inside one chunk.
    """

    candidate_set = {str(value) for value in candidate_block_ids if value}
    return [
        index
        for index, block_id in enumerate(section_block_ids)
        if block_id in candidate_set
    ]


def _deduplicate_sec_chunk_blocks(blocks: Sequence[Any]) -> tuple[Any, ...]:
    """Remove only exact duplicate sec2md block occurrences inside one chunk.

    sec2md 0.1.23 can append the same table-context element twice because its
    context check looks only at the start of the current chunk.  Deduplication
    is deliberately narrower than element-ID deduplication: if one source
    element is legitimately split into two different text fragments, both
    fragments remain.
    """

    seen: set[tuple[str, tuple[str, ...], str]] = set()
    output: list[Any] = []
    for block in blocks:
        content = str(getattr(block, "content", "") or "")
        normalized = re.sub(r"\s+", " ", content).strip().casefold()
        element_ids = tuple(
            sorted(
                str(value)
                for value in (getattr(block, "element_ids", None) or ())
                if str(value)
            )
        )
        # Without source-element lineage, identical text may represent two real
        # occurrences rather than sec2md's duplicated table-context append.
        # Fail closed: keep it and let downstream review see the repetition.
        if not element_ids:
            if normalized:
                output.append(block)
            continue
        identity = (
            str(getattr(block, "block_type", "text") or "text").casefold(),
            element_ids,
            normalized,
        )
        if not normalized or identity in seen:
            continue
        seen.add(identity)
        output.append(block)
    return tuple(output)


def _overlapping_block_indices(
    offsets: Sequence[tuple[int, int]], *, start: int, raw_length: int
) -> list[int]:
    """Map an unmodified splitter character span back to canonical blocks."""

    if start < 0 or raw_length <= 0:
        return []
    end = start + raw_length
    return [
        index
        for index, (block_start, block_end) in enumerate(offsets)
        if block_start < end and block_end > start
    ]


def _generic_sections_from_html(body: bytes, title: str) -> list[_RawSection]:
    import trafilatura

    xml = trafilatura.extract(
        body,
        output_format="xml",
        include_comments=False,
        include_tables=True,
        # Trafilatura 2.2 can split an inline anchor into a sibling ``ref``
        # node and thereby fragment the surrounding sentence.  The document
        # stable URL is already retained separately, so link targets are not
        # worth sacrificing prose integrity here.
        include_links=False,
        include_images=True,
        favor_precision=True,
    )
    if not xml:
        raise StructuredDocumentError("trafilatura_xml_empty")
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise StructuredDocumentError("trafilatura_xml_invalid") from exc

    sections: list[_RawSection] = []
    heading = title
    blocks: list[_RawBlock] = []
    seen_content: set[tuple[str, str]] = set()
    parent_by_element = {
        child: parent for parent in root.iter() for child in parent
    }

    def ancestor_tags(element: ElementTree.Element) -> set[str]:
        values: set[str] = set()
        parent = parent_by_element.get(element)
        while parent is not None:
            values.add(_element_tag(parent))
            parent = parent_by_element.get(parent)
        return values

    def extend_previous_block(content: str) -> None:
        nonlocal blocks
        content = _clean_text(content)
        if not content:
            return
        if not blocks:
            identity = ("p", content)
            if identity not in seen_content:
                seen_content.add(identity)
                blocks.append(_RawBlock(kind="p", content=content))
            return
        previous = blocks[-1]
        merged = _clean_text(f"{previous.content} {content}")
        blocks[-1] = _RawBlock(
            kind=previous.kind,
            content=merged,
            page_start=previous.page_start,
            page_end=previous.page_end,
            element_ids=previous.element_ids,
            tags=previous.tags,
        )
        seen_content.add((previous.kind, merged))

    def flush() -> None:
        nonlocal blocks
        if blocks:
            sections.append(_RawSection(path=(heading,), blocks=tuple(blocks)))
            blocks = []

    for element in root.iter():
        tag = _element_tag(element)
        ancestors = ancestor_tags(element)
        if tag != "table" and "table" in ancestors:
            # The owning table is emitted once with row boundaries below.
            continue
        if tag == "head":
            candidate = _clean_text(" ".join(element.itertext()))
            if candidate:
                flush()
                heading = candidate
            continue
        if tag == "graphic":
            target = str(
                element.attrib.get("src")
                or element.attrib.get("target")
                or ""
            ).strip()
            alt = str(element.attrib.get("alt") or "").strip()
            if target:
                content = f"![{alt}]({target})"
                identity = ("image", content)
                if identity not in seen_content:
                    seen_content.add(identity)
                    blocks.append(_RawBlock(kind="image", content=content))
            continue
        if tag == "ref":
            # Trafilatura can emit an inline anchor as a sibling between two
            # paragraph fragments: <p>has selected</p><ref>product</ref> tail.
            # A ref nested inside a paragraph is already included by
            # ``itertext``; only repair the top-level sibling form.
            if not ancestors.intersection({"p", "quote", "code"}):
                extend_previous_block(
                    " ".join(element.itertext()) + " " + str(element.tail or "")
                )
            continue
        if tag not in {"p", "quote", "code", "item", "table"}:
            continue
        if tag != "table" and ancestors.intersection({"p", "quote", "code"}):
            continue
        if tag == "item" and any(
            _element_tag(child)
            in {"p", "item", "list", "table", "head"}
            for child in element
        ):
            continue
        content = (
            _xml_table_markdown(element)
            if tag == "table"
            else _clean_text(" ".join(element.itertext()))
        )
        if not content:
            continue
        kind = "table" if tag == "table" else "list" if tag == "item" else tag
        identity = (kind, content)
        if identity in seen_content:
            continue
        seen_content.add(identity)
        blocks.append(_RawBlock(kind=kind, content=content))
    flush()
    if not sections:
        raise StructuredDocumentError("trafilatura_no_structured_sections")
    return sections


def _generic_sections_from_pdf(body: bytes, title: str) -> list[_RawSection]:
    from io import BytesIO
    from pypdf import PdfReader

    reader = PdfReader(BytesIO(body), strict=False)
    sections: list[_RawSection] = []
    for page_number, page in enumerate(reader.pages, start=1):
        # Default extraction is materially cleaner for earnings-call prose
        # than pypdf's layout mode (which inserts intra-word spacing to mimic
        # columns).  Page boundaries remain the citation locator.
        text = _clean_text(page.extract_text() or "")
        if not text:
            continue
        sections.append(
            _RawSection(
                path=(title, f"Page {page_number}"),
                blocks=(
                    _RawBlock(
                        kind="page_text",
                        content=text,
                        page_start=page_number,
                        page_end=page_number,
                    ),
                ),
                page_start=page_number,
                page_end=page_number,
            )
        )
    if not sections:
        raise StructuredDocumentError("pypdf_no_text_pages")
    return sections


def _markdown_page_blocks(content: str, page_number: int) -> list[_RawBlock]:
    """Create section-owned blocks from an already parsed Markdown page slice.

    ``sec2md`` correctly slices ``Page.content`` at an intra-page Item boundary,
    but version 0.1.23 leaves the original full-page ``elements`` attached to
    both resulting Page objects.  On those shared boundary pages we therefore
    use its sliced Markdown as the authority and retain table runs explicitly.
    """

    blocks: list[_RawBlock] = []
    pending_text: list[str] = []
    pending_table: list[str] = []

    def flush_text() -> None:
        nonlocal pending_text
        value = _clean_text("\n".join(pending_text))
        if value:
            blocks.append(
                _RawBlock(
                    kind="text",
                    content=value,
                    page_start=page_number,
                    page_end=page_number,
                )
            )
        pending_text = []

    def flush_table() -> None:
        nonlocal pending_table
        value = _clean_text("\n".join(pending_table))
        if value:
            blocks.append(
                _RawBlock(
                    kind="table",
                    content=value,
                    page_start=page_number,
                    page_end=page_number,
                )
            )
        pending_table = []

    for line in str(content or "").splitlines():
        stripped = line.strip()
        is_table_line = stripped.startswith("|") and stripped.endswith("|")
        if is_table_line:
            flush_text()
            pending_table.append(stripped)
        else:
            flush_table()
            pending_text.append(line)
    flush_table()
    flush_text()
    return blocks


def _strip_sec_repeating_navigation(content: str) -> str:
    """Remove only the exact SEC page breadcrumb repeated on every page."""

    return _clean_text(
        "\n".join(
            line
            for line in str(content or "").splitlines()
            if line.strip().casefold() != "table of contents"
        )
    )


def _sec_sections(
    body: bytes,
    *,
    profile: str,
    title: str,
) -> tuple[list[_RawSection], list[Any], list[Any]]:
    from sec2md import extract_sections, parse_filing
    from sec2md.models import Element

    pages = parse_filing(body, include_elements=True, embed_images=False)
    if not pages:
        raise StructuredDocumentError("sec2md_no_pages")
    filing_type = {"sec2md_10k": "10-K", "sec2md_10q": "10-Q"}.get(profile)
    parsed_sections = extract_sections(pages, filing_type) if filing_type else []
    if filing_type and not parsed_sections:
        raise StructuredDocumentError("sec2md_no_filing_sections")
    if not parsed_sections:
        parsed_sections = [
            type(
                "SyntheticSecSection",
                (),
                {
                    "part": None,
                    "item": "EXHIBIT 99.1",
                    "item_title": title,
                    "pages": pages,
                },
            )()
        ]

    page_use_count: dict[int, int] = {}
    for parsed in parsed_sections:
        for page in parsed.pages:
            page_number = int(page.number)
            page_use_count[page_number] = page_use_count.get(page_number, 0) + 1

    # Keep sec2md as the filing parser, while repairing its 0.1.23 boundary
    # projection: Page.content is section-owned, Page.elements is not.  A page
    # shared by adjacent Items must use the sliced content and text/table
    # fallback rather than duplicating the full page's elements into both.
    owned_parsed_sections: list[Any] = []
    for parsed in parsed_sections:
        owned_pages = []
        for page in parsed.pages:
            shared_boundary = page_use_count[int(page.number)] > 1
            clean_content = _strip_sec_repeating_navigation(page.content)
            clean_elements = []
            for element in page.elements or ():
                element_content = _strip_sec_repeating_navigation(element.content)
                if element_content:
                    clean_elements.append(
                        element.model_copy(update={"content": element_content})
                    )
            if shared_boundary:
                clean_elements = [
                    Element(
                        id=_stable_id(
                            "SEC2MD_BOUNDARY",
                            getattr(parsed, "part", None),
                            getattr(parsed, "item", None),
                            int(page.number),
                            block_index,
                            _content_sha256(block.content),
                        ),
                        content=block.content,
                        kind=block.kind,
                        page_start=int(page.number),
                        page_end=int(page.number),
                        tags=[],
                    )
                    for block_index, block in enumerate(
                        _markdown_page_blocks(clean_content, int(page.number))
                    )
                ]
            update: dict[str, Any] = {
                "content": clean_content,
                "elements": clean_elements,
            }
            if shared_boundary:
                update["text_blocks"] = []
            owned_pages.append(page.model_copy(update=update))
        if hasattr(parsed, "model_copy"):
            owned = parsed.model_copy(update={"pages": owned_pages})
        else:
            owned = type(
                "OwnedSyntheticSecSection",
                (),
                {
                    "part": getattr(parsed, "part", None),
                    "item": getattr(parsed, "item", None),
                    "item_title": getattr(parsed, "item_title", None),
                    "pages": owned_pages,
                },
            )()
        owned_parsed_sections.append(owned)

    sections: list[_RawSection] = []
    for parsed in owned_parsed_sections:
        part = str(parsed.part).strip() if parsed.part else None
        item = str(parsed.item).strip() if parsed.item else None
        item_title = str(parsed.item_title).strip() if parsed.item_title else None
        path = tuple(value for value in (part, item, item_title) if value)
        page_numbers = [int(page.number) for page in parsed.pages]
        blocks: list[_RawBlock] = []
        for page in parsed.pages:
            if page.elements:
                for element in page.elements or ():
                    content = _clean_text(element.content)
                    if not content:
                        continue
                    blocks.append(
                        _RawBlock(
                            kind=str(element.kind or "text").casefold(),
                            content=content,
                            page_start=int(element.page_start),
                            page_end=int(element.page_end),
                            element_ids=(str(element.id),),
                            tags=tuple(str(tag) for tag in (element.tags or ())),
                        )
                    )
            else:
                blocks.extend(
                    _markdown_page_blocks(str(page.content or ""), int(page.number))
                )
            for image_index, image in enumerate(
                _image_references(str(page.content or ""))
            ):
                blocks.append(
                    _RawBlock(
                        kind="image",
                        content=f"![{image['alt']}]({image['target']})",
                        page_start=int(page.number),
                        page_end=int(page.number),
                        element_ids=(
                            f"sec2md-p{int(page.number)}-image-{image_index}",
                        ),
                    )
                )
        if not blocks:
            content = _clean_text("\n\n".join(page.content for page in parsed.pages))
            blocks = [
                _RawBlock(
                    kind="text",
                    content=content,
                    page_start=min(page_numbers),
                    page_end=max(page_numbers),
                )
            ]
        sections.append(
            _RawSection(
                path=path or (title,),
                blocks=tuple(blocks),
                part=part,
                item=item,
                item_title=item_title,
                page_start=min(page_numbers),
                page_end=max(page_numbers),
            )
        )
    return sections, pages, owned_parsed_sections


def _base_chunk(
    *,
    source: StructuredSourceDescriptor,
    document_id: str,
    section_id: str,
    section: _RawSection,
    global_chunk_index: int,
    section_chunk_index: int,
    parser: str,
    splitter: str,
    text: str,
    block_ids: Sequence[str],
    block_kinds: Iterable[str],
    page_start: int | None,
    page_end: int | None,
    retrieval_spans: Sequence[Mapping[str, Any]],
    source_char_start: int | None = None,
    source_char_raw_length: int | None = None,
    element_ids: Iterable[str] = (),
    tags: Iterable[str] = (),
) -> dict[str, Any]:
    text = _clean_text(text)
    content_digest = _content_sha256(text)
    chunk_id = _stable_id(
        "CHUNK",
        source.route_id,
        source.raw_body_sha256,
        section_id,
        section_chunk_index,
        content_digest,
    )
    kinds = sorted(set(str(kind).casefold() for kind in block_kinds if kind))
    element_id_values = sorted(set(str(value) for value in element_ids if value))
    tag_values = sorted(set(str(value) for value in tags if value))
    images = _image_references(text)
    span_rows: list[dict[str, Any]] = []
    for span_index, raw_span in enumerate(retrieval_spans):
        span_kind = str(raw_span.get("span_kind") or "").strip().casefold()
        span_content = _clean_text(raw_span.get("content"))
        source_block_ids = list(
            dict.fromkeys(
                str(value)
                for value in raw_span.get("source_block_ids") or []
                if str(value)
            )
        )
        if not span_kind or not span_content or not source_block_ids:
            raise StructuredDocumentError(
                f"structured_chunk_retrieval_span_invalid:{source.route_id}:"
                f"{section_id}:{section_chunk_index}:{span_index}"
            )
        if not set(source_block_ids).issubset(set(block_ids)):
            raise StructuredDocumentError(
                f"structured_chunk_retrieval_span_block_drift:{source.route_id}:"
                f"{section_id}:{section_chunk_index}:{span_index}"
            )
        span_rows.append(
            {
                "span_index": span_index,
                "span_kind": span_kind,
                "source_block_ids": source_block_ids,
                "content_sha256": _content_sha256(span_content),
                "content": span_content,
            }
        )
    if not span_rows:
        raise StructuredDocumentError(
            f"structured_chunk_retrieval_spans_empty:{source.route_id}:"
            f"{section_id}:{section_chunk_index}"
        )
    span_digest = sha256(
        (
            json.dumps(
                span_rows,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": CHUNK_SCHEMA,
        "authority_state": "retrieval_candidate",
        "chunk_id": chunk_id,
        "route_id": source.route_id,
        "parent_document_id": document_id,
        "parent_section_id": section_id,
        "section_path": list(section.path),
        "part": section.part,
        "item": section.item,
        "item_title": section.item_title,
        "chunk_index": global_chunk_index,
        "section_chunk_index": section_chunk_index,
        "block_ids": list(block_ids),
        "block_kinds": kinds,
        "retrieval_spans": span_rows,
        "retrieval_span_count": len(span_rows),
        "retrieval_spans_sha256": span_digest,
        "retrieval_span_text_sha256": _content_sha256(
            _clean_text("\n".join(row["content"] for row in span_rows))
        ),
        "source_char_start": source_char_start,
        "source_char_raw_length": source_char_raw_length,
        "page": page_start if page_start == page_end else None,
        "page_start": page_start,
        "page_end": page_end,
        "element_ids": element_id_values,
        "xbrl_tags": tag_values,
        "image_references": images,
        "contains_table": "table" in kinds,
        "contains_image": bool(images) or "image" in kinds,
        "title": source.title,
        "publisher": source.publisher,
        "issuer_id": source.issuer_id,
        "ticker": source.ticker,
        "company": source.company,
        "publication_date": source.publication_date,
        "fiscal_period": source.fiscal_period,
        "period_end": source.period_end,
        "source_role": source.source_role,
        "document_kind": source.document_kind,
        "branches": list(source.branches),
        "stable_url": source.stable_url,
        "numeric_authority": False,
        "candidate_is_not_evidence": True,
        "citation_eligible": False,
        "parser": parser,
        "splitter": splitter,
        "raw_body_sha256": source.raw_body_sha256,
        "text_sha256": content_digest,
        "text": text,
    }


def build_structured_document_tree(
    *,
    source: StructuredSourceDescriptor,
    body: bytes,
    parser_profile: str,
    generic_split_length_words: int = 350,
    generic_split_overlap_words: int = 50,
    generic_split_threshold_words: int = 80,
    sec_chunk_size_tokens: int = 512,
    sec_chunk_overlap_tokens: int = 64,
    sec_max_table_tokens: int = 2048,
) -> dict[str, Any]:
    """Parse one immutable body and return canonical document-tree rows."""

    if sha256(body).hexdigest() != source.raw_body_sha256:
        raise StructuredDocumentError("structured_source_body_digest_mismatch")
    if parser_profile not in _SEC_PROFILES | {
        "trafilatura_xml",
        "pypdf_pages",
    }:
        raise StructuredDocumentError("structured_parser_profile_unknown")
    if not 128 <= generic_split_length_words <= 800:
        raise StructuredDocumentError("generic_split_length_invalid")
    if not 0 <= generic_split_overlap_words < generic_split_length_words:
        raise StructuredDocumentError("generic_split_overlap_invalid")
    if not 0 <= generic_split_threshold_words <= generic_split_length_words:
        raise StructuredDocumentError("generic_split_threshold_invalid")
    if not 128 <= sec_chunk_size_tokens <= 2048:
        raise StructuredDocumentError("sec_chunk_size_invalid")
    if not 0 <= sec_chunk_overlap_tokens < sec_chunk_size_tokens:
        raise StructuredDocumentError("sec_chunk_overlap_invalid")
    if not sec_chunk_size_tokens <= sec_max_table_tokens <= 8192:
        raise StructuredDocumentError("sec_max_table_tokens_invalid")

    document_id = _stable_id(
        "DOC", source.route_id, source.raw_body_sha256
    )
    sec_pages: list[Any] = []
    sec_parsed_sections: list[Any] = []
    if parser_profile in _SEC_PROFILES:
        sections, sec_pages, sec_parsed_sections = _sec_sections(
            body,
            profile=parser_profile,
            title=source.title,
        )
        parser = f"sec2md_{_package_version('sec2md')}"
    elif parser_profile == "trafilatura_xml":
        sections = _generic_sections_from_html(body, source.title)
        parser = f"trafilatura_{_package_version('trafilatura')}_xml"
    else:
        sections = _generic_sections_from_pdf(body, source.title)
        parser = f"pypdf_{_package_version('pypdf')}_layout"

    section_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    chunk_rows: list[dict[str, Any]] = []
    global_chunk_index = 0

    for section_index, section in enumerate(sections):
        section_id = _stable_id(
            "SECTION",
            source.route_id,
            source.raw_body_sha256,
            section_index,
            "/".join(section.path),
        )
        section_text, offsets = _section_text(section.blocks)
        section_block_ids: list[str] = []
        for block_index, (block, (char_start, char_end)) in enumerate(
            zip(section.blocks, offsets, strict=True)
        ):
            block_id = _stable_id(
                "BLOCK",
                section_id,
                block_index,
                _content_sha256(block.content),
            )
            section_block_ids.append(block_id)
            alphabetic_footnotes = _footnote_markers(block.content)
            numeric_footnote_references, numeric_footnote_definitions = (
                _table_footnote_candidates(block.content)
                if block.kind == "table"
                else (set(), set())
            )
            block_rows.append(
                {
                    "schema_version": BLOCK_SCHEMA,
                    "authority_state": "retrieval_candidate_source_block",
                    "candidate_is_not_evidence": True,
                    "numeric_authority": False,
                    "citation_eligible": False,
                    "block_id": block_id,
                    "parent_document_id": document_id,
                    "parent_section_id": section_id,
                    "route_id": source.route_id,
                    "raw_body_sha256": source.raw_body_sha256,
                    "block_index": block_index,
                    "block_kind": block.kind,
                    "table_id": block_id if block.kind == "table" else None,
                    "image_id": block_id if block.kind == "image" else None,
                    "table_rows": (
                        _markdown_table_rows(block.content)
                        if block.kind == "table"
                        else []
                    ),
                    "table_row_count": (
                        len(_markdown_table_rows(block.content))
                        if block.kind == "table"
                        else 0
                    ),
                    "table_column_count": (
                        max(
                            (
                                len(row)
                                for row in _markdown_table_rows(block.content)
                            ),
                            default=0,
                        )
                        if block.kind == "table"
                        else 0
                    ),
                    "footnote_markers": alphabetic_footnotes,
                    "footnote_relation_state": (
                        "unresolved_requires_source_review"
                        if alphabetic_footnotes
                        else "not_observed"
                    ),
                    "_numeric_footnote_references": sorted(
                        numeric_footnote_references
                    ),
                    "_numeric_footnote_definitions": sorted(
                        numeric_footnote_definitions
                    ),
                    "image_asset_captured": False,
                    "page_start": block.page_start,
                    "page_end": block.page_end,
                    "char_start": char_start,
                    "char_end": char_end,
                    "element_ids": list(block.element_ids),
                    "xbrl_tags": list(block.tags),
                    "image_references": _image_references(block.content),
                    "content_sha256": _content_sha256(block.content),
                    "content": block.content,
                }
            )
        section_rows.append(
            {
                "schema_version": SECTION_SCHEMA,
                "authority_state": "retrieval_candidate_parent",
                "citation_eligible": False,
                "section_id": section_id,
                "parent_document_id": document_id,
                "route_id": source.route_id,
                "raw_body_sha256": source.raw_body_sha256,
                "section_index": section_index,
                "section_path": list(section.path),
                "part": section.part,
                "item": section.item,
                "item_title": section.item_title,
                "page_start": section.page_start,
                "page_end": section.page_end,
                "block_ids": section_block_ids,
                "content_sha256": _content_sha256(section_text),
                "content": section_text,
                "candidate_is_not_evidence": True,
                "numeric_authority": False,
            }
        )

        if parser_profile in _SEC_PROFILES:
            from sec2md import chunk_pages, chunk_section

            parsed = sec_parsed_sections[section_index]
            chunks = (
                chunk_pages(
                    parsed.pages,
                    chunk_size=sec_chunk_size_tokens,
                    chunk_overlap=sec_chunk_overlap_tokens,
                    max_table_tokens=sec_max_table_tokens,
                    header=" > ".join(section.path),
                )
                if parser_profile == "sec2md_exhibit"
                else chunk_section(
                    parsed,
                    chunk_size=sec_chunk_size_tokens,
                    chunk_overlap=sec_chunk_overlap_tokens,
                    max_table_tokens=sec_max_table_tokens,
                    header=" > ".join(section.path),
                )
            )
            splitter = (
                f"sec2md_chunk_{sec_chunk_size_tokens}_overlap_"
                f"{sec_chunk_overlap_tokens}_max_table_{sec_max_table_tokens}"
            )
            element_to_block = {
                element_id: block_id
                for block_id, block in zip(
                    section_block_ids, section.blocks, strict=True
                )
                for element_id in block.element_ids
            }
            for section_chunk_index, chunk in enumerate(chunks):
                elements = tuple(chunk.elements or ())
                chunk_blocks = _deduplicate_sec_chunk_blocks(
                    tuple(chunk.blocks or ())
                )
                element_ids = list(
                    dict.fromkeys(
                        [
                            str(value)
                            for block in chunk_blocks
                            for value in (getattr(block, "element_ids", None) or ())
                            if str(value)
                        ]
                        + [str(element.id) for element in elements]
                    )
                )
                matching_blocks = [
                    element_to_block[element_id]
                    for element_id in element_ids
                    if element_id in element_to_block
                ]
                matching_indices = _ordered_chunk_block_indices(
                    matching_blocks, section_block_ids
                )
                if not matching_indices:
                    # On a shared Item-boundary page sec2md's original
                    # elements are intentionally removed (they represent the
                    # full page, not the sliced section).  Rebind the resulting
                    # text-fallback chunk to the section-owned raw blocks by
                    # page and normalized text containment.
                    page_values = [
                        int(value)
                        for block in chunk_blocks
                        for value in (getattr(block, "page", None),)
                        if value is not None
                    ]
                    if not page_values:
                        page_values = [
                            int(element.page_start) for element in elements
                        ] + [int(element.page_end) for element in elements]
                    chunk_block_texts = [
                        _clean_text(getattr(value, "content", "")).casefold()
                        for value in chunk_blocks
                        if _clean_text(getattr(value, "content", ""))
                    ]
                    page_set = set(page_values)
                    page_candidates = [
                        (index, block)
                        for index, block in enumerate(section.blocks)
                        if not page_set
                        or any(
                            value in page_set
                            for value in (block.page_start, block.page_end)
                            if value is not None
                        )
                    ]
                    matched_indices = [
                        index
                        for index, block in page_candidates
                        if (
                            (block_text := _clean_text(block.content).casefold())
                            and any(
                                block_text in chunk_block_text
                                or chunk_block_text in block_text
                                for chunk_block_text in chunk_block_texts
                            )
                        )
                    ]
                    if not matched_indices and len(page_candidates) == 1:
                        matched_indices = [page_candidates[0][0]]
                    matching_indices = sorted(set(matched_indices))
                if not matching_indices:
                    raise StructuredDocumentError(
                        "structured_sec_chunk_block_lineage_missing:"
                        f"{source.route_id}:{section_id}:"
                        f"{section_chunk_index}"
                    )
                matching_blocks = [
                    section_block_ids[index] for index in matching_indices
                ]
                canonical_blocks = [section.blocks[index] for index in matching_indices]
                page_values = [
                    int(value)
                    for block in chunk_blocks
                    for value in (getattr(block, "page", None),)
                    if value is not None
                ]
                if not page_values:
                    page_values = [
                        int(value)
                        for block in canonical_blocks
                        for value in (block.page_start, block.page_end)
                        if value is not None
                    ]
                chunk_text = _clean_text(
                    "\n".join(
                        str(getattr(block, "content", "") or "")
                        for block in chunk_blocks
                    )
                )
                if not chunk_text:
                    raise StructuredDocumentError(
                        "structured_sec_chunk_text_empty:"
                        f"{source.route_id}:{section_id}:{section_chunk_index}"
                    )
                retrieval_spans: list[dict[str, Any]] = []
                for chunk_block in chunk_blocks:
                    span_content = _clean_text(
                        str(getattr(chunk_block, "content", "") or "")
                    )
                    if not span_content:
                        continue
                    span_kind = str(
                        getattr(chunk_block, "block_type", "text") or "text"
                    ).casefold()
                    span_element_ids = {
                        str(value)
                        for value in (
                            getattr(chunk_block, "element_ids", None) or ()
                        )
                        if str(value)
                    }
                    span_block_ids = list(
                        dict.fromkeys(
                            element_to_block[element_id]
                            for element_id in span_element_ids
                            if element_id in element_to_block
                            and element_to_block[element_id] in matching_blocks
                        )
                    )
                    if not span_block_ids:
                        normalized_span = re.sub(
                            r"\s+", " ", span_content
                        ).strip().casefold()
                        compatible: list[str] = []
                        content_matches: list[str] = []
                        for index in matching_indices:
                            canonical = section.blocks[index]
                            canonical_kind = str(canonical.kind or "text").casefold()
                            compatible_kind = (
                                canonical_kind == span_kind
                                if span_kind in {"table", "image"}
                                else canonical_kind not in {"table", "image"}
                            )
                            if not compatible_kind:
                                continue
                            canonical_id = section_block_ids[index]
                            compatible.append(canonical_id)
                            normalized_canonical = re.sub(
                                r"\s+", " ", canonical.content
                            ).strip().casefold()
                            if (
                                normalized_canonical
                                and (
                                    normalized_span in normalized_canonical
                                    or normalized_canonical in normalized_span
                                )
                            ):
                                content_matches.append(canonical_id)
                        span_block_ids = content_matches or compatible
                    if not span_block_ids:
                        raise StructuredDocumentError(
                            "structured_sec_chunk_span_block_lineage_missing:"
                            f"{source.route_id}:{section_id}:"
                            f"{section_chunk_index}:{len(retrieval_spans)}"
                        )
                    retrieval_spans.append(
                        {
                            "span_kind": span_kind,
                            "source_block_ids": span_block_ids,
                            "content": span_content,
                        }
                    )
                if _clean_text(
                    "\n".join(span["content"] for span in retrieval_spans)
                ) != chunk_text:
                    raise StructuredDocumentError(
                        "structured_sec_chunk_span_reconstruction_drift:"
                        f"{source.route_id}:{section_id}:{section_chunk_index}"
                    )
                chunk_rows.append(
                    _base_chunk(
                        source=source,
                        document_id=document_id,
                        section_id=section_id,
                        section=section,
                        global_chunk_index=global_chunk_index,
                        section_chunk_index=section_chunk_index,
                        parser=parser,
                        splitter=splitter,
                        text=chunk_text,
                        block_ids=matching_blocks,
                        block_kinds=[
                            str(getattr(block, "block_type", "text"))
                            for block in chunk_blocks
                        ],
                        page_start=min(page_values) if page_values else section.page_start,
                        page_end=max(page_values) if page_values else section.page_end,
                        retrieval_spans=retrieval_spans,
                        element_ids=element_ids,
                        tags=[
                            value for block in canonical_blocks for value in block.tags
                        ],
                    )
                )
                global_chunk_index += 1
        else:
            from haystack import Document
            from haystack.components.preprocessors import DocumentSplitter

            splitter_component = DocumentSplitter(
                split_by="word",
                split_length=generic_split_length_words,
                split_overlap=generic_split_overlap_words,
                split_threshold=generic_split_threshold_words,
            )
            split_documents = splitter_component.run(
                documents=[Document(content=section_text)]
            )["documents"]
            splitter = (
                "haystack_document_splitter_word_"
                f"{generic_split_length_words}_overlap_{generic_split_overlap_words}"
            )
            for section_chunk_index, chunk in enumerate(split_documents):
                raw_chunk_text = str(chunk.content or "")
                text = _clean_text(raw_chunk_text)
                start = int(chunk.meta.get("split_idx_start") or 0)
                matching_indices = _overlapping_block_indices(
                    offsets,
                    start=start,
                    raw_length=len(raw_chunk_text),
                )
                matching_blocks = [section.blocks[index] for index in matching_indices]
                page_values = [
                    int(value)
                    for block in matching_blocks
                    for value in (block.page_start, block.page_end)
                    if value is not None
                ]
                chunk_end = start + len(raw_chunk_text)
                retrieval_spans = []
                for index in matching_indices:
                    block_start, block_end = offsets[index]
                    fragment_start = max(start, block_start)
                    fragment_end = min(chunk_end, block_end)
                    fragment = _clean_text(
                        section_text[fragment_start:fragment_end]
                    )
                    if not fragment:
                        continue
                    retrieval_spans.append(
                        {
                            "span_kind": section.blocks[index].kind,
                            "source_block_ids": [section_block_ids[index]],
                            "content": fragment,
                        }
                    )
                normalized_span_text = re.sub(
                    r"\s+",
                    " ",
                    " ".join(span["content"] for span in retrieval_spans),
                ).strip()
                normalized_chunk_text = re.sub(r"\s+", " ", text).strip()
                if normalized_span_text != normalized_chunk_text:
                    raise StructuredDocumentError(
                        "structured_generic_chunk_span_reconstruction_drift:"
                        f"{source.route_id}:{section_id}:{section_chunk_index}"
                    )
                chunk_rows.append(
                    _base_chunk(
                        source=source,
                        document_id=document_id,
                        section_id=section_id,
                        section=section,
                        global_chunk_index=global_chunk_index,
                        section_chunk_index=section_chunk_index,
                        parser=parser,
                        splitter=splitter,
                        text=text,
                        block_ids=[section_block_ids[index] for index in matching_indices],
                        block_kinds=[block.kind for block in matching_blocks],
                        page_start=min(page_values) if page_values else section.page_start,
                        page_end=max(page_values) if page_values else section.page_end,
                        retrieval_spans=retrieval_spans,
                        source_char_start=start,
                        source_char_raw_length=len(raw_chunk_text),
                        element_ids=[
                            value
                            for block in matching_blocks
                            for value in block.element_ids
                        ],
                        tags=[
                            value for block in matching_blocks for value in block.tags
                        ],
                    )
                )
                global_chunk_index += 1

    document_numeric_footnote_definitions = {
        marker
        for row in block_rows
        for marker in row.get("_numeric_footnote_definitions", [])
    }
    for row in block_rows:
        references = set(row.pop("_numeric_footnote_references", []))
        definitions = set(row.pop("_numeric_footnote_definitions", []))
        resolved_numeric = (references | definitions).intersection(
            document_numeric_footnote_definitions
        )
        ambiguous_numeric = references - document_numeric_footnote_definitions
        alphabetic = set(str(value) for value in row["footnote_markers"])
        row["footnote_markers"] = sorted(alphabetic | resolved_numeric)
        row["ambiguous_numeric_footnote_references"] = sorted(
            ambiguous_numeric
        )
        if alphabetic:
            row["footnote_relation_state"] = (
                "unresolved_requires_source_review"
            )
        elif resolved_numeric:
            row["footnote_relation_state"] = (
                "resolved_same_table"
                if resolved_numeric.issubset(definitions)
                else "resolved_same_document_table"
            )
        elif ambiguous_numeric:
            row["footnote_relation_state"] = (
                "ambiguous_numeric_reference_not_promoted"
            )
        else:
            row["footnote_relation_state"] = "not_observed"

    all_image_references = [
        image
        for block in block_rows
        for image in block["image_references"]
    ]
    known_block_ids = {row["block_id"] for row in block_rows}
    orphan_chunk_ids = [
        str(row["chunk_id"]) for row in chunk_rows if not row["block_ids"]
    ]
    if orphan_chunk_ids:
        raise StructuredDocumentError(
            "structured_chunk_block_lineage_missing:"
            + ",".join(orphan_chunk_ids[:8])
        )
    if any(
        not set(row["block_ids"]).issubset(known_block_ids)
        for row in chunk_rows
    ):
        raise StructuredDocumentError("structured_chunk_block_lineage_invalid")
    document = {
        "schema_version": DOCUMENT_SCHEMA,
        "authority_state": "retrieval_candidate_source_document",
        "document_id": document_id,
        "route_id": source.route_id,
        "title": source.title,
        "publisher": source.publisher,
        "issuer_id": source.issuer_id,
        "ticker": source.ticker,
        "company": source.company,
        "publication_date": source.publication_date,
        "fiscal_period": source.fiscal_period,
        "period_end": source.period_end,
        "source_role": source.source_role,
        "document_kind": source.document_kind,
        "stable_url": source.stable_url,
        "branches": list(source.branches),
        "raw_body_sha256": source.raw_body_sha256,
        "parser_profile": parser_profile,
        "parser": parser,
        "section_ids": [row["section_id"] for row in section_rows],
        "section_count": len(section_rows),
        "block_count": len(block_rows),
        "chunk_count": len(chunk_rows),
        "table_block_count": sum(
            row["block_kind"] == "table" for row in block_rows
        ),
        "image_reference_count": len(all_image_references),
        "page_count": len(sec_pages) if sec_pages else max(
            (row["page_end"] or 0 for row in section_rows), default=0
        ),
        "candidate_is_not_evidence": True,
        "numeric_authority": False,
    }
    if not section_rows or not block_rows or not chunk_rows:
        raise StructuredDocumentError("structured_tree_empty")
    return {
        "document": document,
        "sections": section_rows,
        "blocks": block_rows,
        "chunks": chunk_rows,
    }


__all__ = [
    "BLOCK_SCHEMA",
    "CHUNK_SCHEMA",
    "DOCUMENT_SCHEMA",
    "SECTION_SCHEMA",
    "StructuredDocumentError",
    "StructuredSourceDescriptor",
    "build_structured_document_tree",
]
