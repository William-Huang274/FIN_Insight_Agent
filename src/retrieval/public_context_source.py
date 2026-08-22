from __future__ import annotations

import base64
from copy import deepcopy
from datetime import date, datetime
import hashlib
from io import BytesIO
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from pypdf import PdfReader

from ingestion.official_source_capture import CAPTURE_SCHEMA_VERSION
from ingestion.parse_sec_filing import extract_sec_html_text_content

from .query_plan import canonical_digest
from .source_use_policy import SourceUsePolicy, evaluate_source_claim_use


PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION = (
    "fin_ia_s1_public_html_source_object_v1_0"
)
PUBLIC_CONTEXT_CANDIDATE_SCHEMA_VERSION = (
    "fin_ia_s1_public_context_candidate_v1_0"
)
PUBLIC_PDF_SOURCE_OBJECT_SCHEMA_VERSION = (
    "fin_ia_s1_public_pdf_source_object_v1_0"
)
PUBLICATION_DATE_RECEIPT_SCHEMA_VERSION = (
    "fin_ia_s1_publication_date_adjudication_receipt_v1_0"
)
_PARSER_PROFILES = {"article_main_html", "sec_filing_html"}
_GENERIC_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "p", "li", "tr")


class PublicContextSourceError(ValueError):
    """A captured public source failed identity, temporal or parse controls."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PublicContextSourceError(code)


def _normalized(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _valid_iso_date(value: object) -> bool:
    try:
        date.fromisoformat(str(value or ""))
    except ValueError:
        return False
    return True


def _decode_capture_body(response_capture: Mapping[str, Any]) -> bytes:
    _require(
        response_capture.get("schema_version") == CAPTURE_SCHEMA_VERSION
        and response_capture.get("capture_kind") == "source_response"
        and response_capture.get("capture_before_parse") is True
        and response_capture.get("credential_cookie_authorization_present") is False
        and 200 <= int(response_capture.get("status_code") or 0) < 300,
        "public_context_response_capture_invalid",
    )
    try:
        body = base64.b64decode(
            str(response_capture.get("body_base64") or ""), validate=True
        )
    except (TypeError, ValueError) as exc:
        raise PublicContextSourceError(
            "public_context_response_body_invalid"
        ) from exc
    _require(
        body
        and hashlib.sha256(body).hexdigest()
        == str(response_capture.get("body_sha256") or "")
        and len(body) == int(response_capture.get("body_bytes") or 0),
        "public_context_response_body_digest_mismatch",
    )
    return body


def _json_ld_publication_dates(soup: BeautifulSoup) -> list[str]:
    values: set[str] = set()

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if str(key) in {"datePublished", "dateCreated"}:
                    candidate = str(child or "")[:10]
                    if _valid_iso_date(candidate):
                        values.add(candidate)
                else:
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            visit(json.loads(node.get_text(" ", strip=True)))
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return sorted(values)


def _normalized_date_candidate(value: object) -> str | None:
    text = _normalized(value)
    if not text:
        return None
    iso = text[:10]
    if _valid_iso_date(iso):
        return iso
    matched = re.search(r"(?<!\d)(20\d{2})[/-](\d{1,2})[/-](\d{1,2})(?!\d)", text)
    if matched:
        try:
            return date(
                int(matched.group(1)),
                int(matched.group(2)),
                int(matched.group(3)),
            ).isoformat()
        except ValueError:
            return None
    month_date = re.search(
        r"(?i)\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:st|nd|rd|th)?[,]?\s+(20\d{2})\b",
        text,
    )
    if month_date:
        try:
            return datetime.strptime(
                f"{month_date.group(1)} {month_date.group(2)} {month_date.group(3)}",
                "%B %d %Y",
            ).date().isoformat()
        except ValueError:
            return None
    return None


def adjudicate_publication_date_from_capture(
    *,
    response_capture: Mapping[str, Any],
    research_as_of: str,
    provider_date_telemetry: str | None = None,
) -> dict[str, Any]:
    """Resolve a publication date from the original body, never provider metadata alone."""

    _require(_valid_iso_date(research_as_of), "public_context_research_as_of_invalid")
    body = _decode_capture_body(response_capture)
    content_type = str(
        (response_capture.get("headers") or {}).get("content-type") or ""
    ).split(";", 1)[0].lower()
    final_url = str(response_capture.get("final_url") or "")
    candidates: list[dict[str, Any]] = []

    def add(value: object, source: str, priority: int) -> None:
        normalized = _normalized_date_candidate(value)
        if normalized is None:
            return
        candidates.append(
            {
                "date": normalized,
                "source": source,
                "priority": priority,
                "after_research_as_of": normalized > research_as_of,
            }
        )

    if content_type in {"text/html", "application/xhtml+xml"}:
        html = body.decode("utf-8", errors="replace")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
            soup = BeautifulSoup(html, "lxml")
        for value in _json_ld_publication_dates(soup):
            add(value, "original_html_json_ld", 1)
        for node in soup.find_all("meta"):
            key = str(
                node.get("property") or node.get("name") or node.get("itemprop") or ""
            ).casefold()
            if key in {
                "article:published_time",
                "datepublished",
                "datecreated",
                "publication_date",
                "publishdate",
                "pubdate",
            }:
                add(node.get("content"), f"original_html_meta:{key}", 1)
        for node in soup.find_all("time"):
            if node.get("datetime"):
                add(node.get("datetime"), "original_html_time_datetime", 2)
        for node in soup.find_all(True):
            marker = " ".join(
                [
                    str(node.get("id") or ""),
                    " ".join(str(value) for value in node.get("class") or ()),
                    str(node.get("itemprop") or ""),
                ]
            ).casefold()
            if not any(token in marker for token in ("date", "publish", "news-time")):
                continue
            visible = _normalized(node.get_text(" ", strip=True))
            if 0 < len(visible) <= 160:
                add(visible, "original_html_visible_date_marker", 2)
    elif content_type == "application/pdf" or body[:1024].find(b"%PDF-") >= 0:
        try:
            reader = PdfReader(BytesIO(body))
            metadata = reader.metadata or {}
            creation = str(metadata.get("/CreationDate") or "")
            matched = re.search(r"D:(20\d{2})(\d{2})(\d{2})", creation)
            if matched:
                add("-".join(matched.groups()), "original_pdf_creation_date", 2)
            first_pages = "\n".join(
                (reader.pages[index].extract_text() or "")
                for index in range(min(4, len(reader.pages)))
            )
            for value in re.findall(
                r"(?<!\d)20\d{2}[/-]\d{1,2}[/-]\d{1,2}(?!\d)", first_pages
            )[:20]:
                add(value, "original_pdf_visible_date", 3)
        except Exception:
            pass
    for value in re.findall(
        r"(?<!\d)20\d{2}[/-]\d{1,2}[/-]\d{1,2}(?!\d)", final_url
    ):
        add(value, "original_url_date", 4)

    telemetry = _normalized_date_candidate(provider_date_telemetry)
    eligible = [row for row in candidates if not row["after_research_as_of"]]
    selected: str | None = None
    state = "unresolved_original_publication_date"
    if eligible:
        best_priority = min(int(row["priority"]) for row in eligible)
        best_dates = sorted(
            {str(row["date"]) for row in eligible if row["priority"] == best_priority}
        )
        if len(best_dates) == 1:
            selected = best_dates[0]
            state = "resolved_from_original_source"
        else:
            state = "conflicting_original_publication_dates"
    body_without_digest = {
        "schema_version": PUBLICATION_DATE_RECEIPT_SCHEMA_VERSION,
        "status": state,
        "research_as_of": research_as_of,
        "final_url": final_url,
        "content_type": content_type,
        "provider_date_telemetry": telemetry,
        "provider_date_is_authority": False,
        "selected_publication_date": selected,
        "provider_date_corroborates_selected": bool(selected and telemetry == selected),
        "original_source_candidates": sorted(
            candidates,
            key=lambda row: (int(row["priority"]), str(row["date"]), str(row["source"])),
        ),
    }
    return {
        **body_without_digest,
        "receipt_digest": canonical_digest(body_without_digest),
    }


def _clean_soup(html: str) -> BeautifulSoup:
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html, "lxml")
    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "template",
            "nav",
            "header",
            "footer",
            "form",
        ]
    ):
        tag.decompose()
    return soup


def _generic_blocks(soup: BeautifulSoup) -> tuple[str, list[str], dict[str, Any]]:
    candidates = [
        *(soup.find_all("article")),
        *(soup.find_all("main")),
        *(soup.find_all(attrs={"role": "main"})),
    ]
    if soup.body is not None:
        candidates.append(soup.body)
    unique: list[Any] = []
    seen_nodes: set[int] = set()
    for node in candidates:
        identity = id(node)
        if identity not in seen_nodes:
            unique.append(node)
            seen_nodes.add(identity)
    _require(bool(unique), "public_context_content_root_missing")
    root = max(unique, key=lambda node: len(_normalized(node.get_text(" "))))

    blocks: list[str] = []
    seen_text: set[str] = set()
    rejected_link_heavy = 0
    for node in root.find_all(_GENERIC_BLOCK_TAGS):
        text = _normalized(node.get_text(" ", strip=True))
        if len(text) < 40 or text in seen_text:
            continue
        link_text = _normalized(" ".join(a.get_text(" ", strip=True) for a in node.find_all("a")))
        if link_text and len(link_text) / max(len(text), 1) > 0.8:
            rejected_link_heavy += 1
            continue
        blocks.append(text)
        seen_text.add(text)
    _require(
        len(blocks) >= 2 and sum(len(value) for value in blocks) >= 500,
        "public_context_article_body_too_thin",
    )
    return (
        "article_or_main_largest_visible_root",
        blocks,
        {"link_heavy_blocks_rejected": rejected_link_heavy},
    )


def _sec_blocks(html: str) -> tuple[str, list[str], dict[str, Any]]:
    text = extract_sec_html_text_content(html)
    blocks = [
        _normalized(value)
        for value in re.split(r"\n\s*\n", text)
        if len(_normalized(value)) >= 40
    ]
    _require(
        len(blocks) >= 10 and sum(len(value) for value in blocks) >= 5000,
        "public_context_sec_body_too_thin",
    )
    return "sec_filing_semantic_text", blocks, {"link_heavy_blocks_rejected": 0}


def _pack_segments(blocks: Sequence[str], *, character_target: int) -> list[str]:
    segments: list[str] = []
    current: list[str] = []
    size = 0
    for block in blocks:
        if current and size + len(block) + 2 > character_target:
            segments.append("\n\n".join(current))
            current = []
            size = 0
        current.append(block)
        size += len(block) + 2
    if current:
        segments.append("\n\n".join(current))
    return segments


def compile_public_html_source_object(
    *,
    response_capture: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    capture_ref: str,
    capture_sha256: str,
) -> dict[str, Any]:
    """Compile captured HTML into a speaker-bound, non-Evidence source object."""

    body = _decode_capture_body(response_capture)
    html = body.decode("utf-8", errors="replace")
    replacement_ratio = html.count("\ufffd") / max(len(html), 1)
    parser_profile = str(source_spec.get("parser_profile") or "")
    source_url = str(source_spec.get("source_url") or "")
    final_url = str(response_capture.get("final_url") or "")
    publication_date = str(source_spec.get("publication_date") or "")
    research_as_of = str(source_spec.get("research_as_of") or "")
    relationship_directions = sorted(
        {str(value) for value in source_spec.get("relationship_directions") or ()}
    )
    _require(
        parser_profile in _PARSER_PROFILES
        and str(source_spec.get("source_id") or "")
        and str(source_spec.get("case_key") or "").upper()
        and str(source_spec.get("speaker_entity") or "")
        and str(source_spec.get("source_class") or "")
        and str(source_spec.get("source_role") or "")
        and str(source_spec.get("source_type") or "")
        and _valid_iso_date(publication_date)
        and _valid_iso_date(research_as_of)
        and date.fromisoformat(publication_date) <= date.fromisoformat(research_as_of)
        and source_url == final_url
        and urlparse(source_url).scheme == "https"
        and relationship_directions
        and len(capture_sha256) == 64
        and replacement_ratio <= 0.005,
        "public_context_source_spec_invalid",
    )
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        metadata_soup = BeautifulSoup(html, "lxml")
    json_ld_dates = _json_ld_publication_dates(metadata_soup)
    soup = _clean_soup(html)
    title = _normalized(soup.title.get_text(" ", strip=True) if soup.title else "")
    if parser_profile == "sec_filing_html":
        root_kind, blocks, quality = _sec_blocks(html)
    else:
        root_kind, blocks, quality = _generic_blocks(soup)
    segments = _pack_segments(
        blocks,
        character_target=int(source_spec.get("segment_character_target") or 2400),
    )
    _require(segments, "public_context_segments_empty")
    segment_rows: list[dict[str, Any]] = []
    for index, text in enumerate(segments, start=1):
        seed = {
            "source_id": str(source_spec["source_id"]),
            "segment_index": index,
            "text_digest": canonical_digest(text),
        }
        segment_rows.append(
            {
                "segment_id": "PUBSEG::" + canonical_digest(seed)[:20].upper(),
                "segment_index": index,
                "text": text,
                "text_digest": seed["text_digest"],
                "candidate_not_evidence": True,
                "numeric_authority": False,
            }
        )
    unsigned = {
        "schema_version": PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION,
        "status": "captured_public_source_compiled_not_evidence",
        "source_id": str(source_spec["source_id"]),
        "case_key": str(source_spec["case_key"]).upper(),
        "speaker_entity": str(source_spec["speaker_entity"]),
        "speaker_ticker": str(source_spec.get("speaker_ticker") or "").upper() or None,
        "source_class": str(source_spec["source_class"]),
        "source_role": str(source_spec["source_role"]),
        "source_type": str(source_spec["source_type"]),
        "relationship_directions": relationship_directions,
        "publication_date": publication_date,
        "research_as_of": research_as_of,
        "source_url": source_url,
        "title": title,
        "capture_ref": capture_ref,
        "capture_sha256": capture_sha256,
        "body_sha256": str(response_capture["body_sha256"]),
        "body_bytes": len(body),
        "parser_profile": parser_profile,
        "content_root_kind": root_kind,
        "segments": segment_rows,
        "parse_quality_receipt": {
            "decoded_as_utf8": True,
            "replacement_character_ratio": replacement_ratio,
            "visible_block_count": len(blocks),
            "segment_count": len(segment_rows),
            "visible_text_characters": sum(len(value) for value in blocks),
            "json_ld_publication_date_candidates": json_ld_dates,
            "bound_publication_date_present_in_json_ld": publication_date
            in json_ld_dates,
            "navigation_header_footer_removed": parser_profile
            == "article_main_html",
            **quality,
        },
        "authority": {
            "candidate_not_evidence": True,
            "source_strength_does_not_prove_claim": True,
            "speaker_is_not_target_company_unless_identity_matches": True,
            "exact_target_numeric_authority": False,
        },
    }
    return {**unsigned, "source_object_digest": canonical_digest(unsigned)}


def compile_public_pdf_source_object(
    *,
    response_capture: Mapping[str, Any],
    source_spec: Mapping[str, Any],
    capture_ref: str,
    capture_sha256: str,
) -> dict[str, Any]:
    """Compile a capture-bound public PDF into bounded text segments, not Evidence."""

    body = _decode_capture_body(response_capture)
    _require(body[:1024].find(b"%PDF-") >= 0, "public_context_pdf_signature_invalid")
    source_url = str(source_spec.get("source_url") or "")
    final_url = str(response_capture.get("final_url") or "")
    publication_date = str(source_spec.get("publication_date") or "")
    research_as_of = str(source_spec.get("research_as_of") or "")
    relationship_directions = sorted(
        {str(value) for value in source_spec.get("relationship_directions") or ()}
    )
    _require(
        str(source_spec.get("source_id") or "")
        and str(source_spec.get("case_key") or "").upper()
        and str(source_spec.get("speaker_entity") or "")
        and str(source_spec.get("source_class") or "")
        and str(source_spec.get("source_role") or "")
        and str(source_spec.get("source_type") or "")
        and _valid_iso_date(publication_date)
        and _valid_iso_date(research_as_of)
        and date.fromisoformat(publication_date) <= date.fromisoformat(research_as_of)
        and source_url == final_url
        and urlparse(source_url).scheme == "https"
        and relationship_directions
        and len(capture_sha256) == 64,
        "public_context_source_spec_invalid",
    )
    try:
        reader = PdfReader(BytesIO(body))
        page_texts = [_normalized(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise PublicContextSourceError("public_context_pdf_parse_failed") from exc
    visible_pages = [value for value in page_texts if len(value) >= 40]
    _require(
        visible_pages and sum(len(value) for value in visible_pages) >= 500,
        "public_context_pdf_body_too_thin",
    )
    segments = _pack_segments(
        visible_pages,
        character_target=int(source_spec.get("segment_character_target") or 2400),
    )
    segment_rows: list[dict[str, Any]] = []
    for index, text in enumerate(segments, start=1):
        seed = {
            "source_id": str(source_spec["source_id"]),
            "segment_index": index,
            "text_digest": canonical_digest(text),
        }
        segment_rows.append(
            {
                "segment_id": "PUBPDFSEG::" + canonical_digest(seed)[:20].upper(),
                "segment_index": index,
                "text": text,
                "text_digest": seed["text_digest"],
                "candidate_not_evidence": True,
                "numeric_authority": False,
            }
        )
    metadata = reader.metadata or {}
    title = _normalized(source_spec.get("title") or metadata.get("/Title") or "")
    unsigned = {
        "schema_version": PUBLIC_PDF_SOURCE_OBJECT_SCHEMA_VERSION,
        "status": "captured_public_source_compiled_not_evidence",
        "source_id": str(source_spec["source_id"]),
        "case_key": str(source_spec["case_key"]).upper(),
        "speaker_entity": str(source_spec["speaker_entity"]),
        "speaker_ticker": str(source_spec.get("speaker_ticker") or "").upper() or None,
        "source_class": str(source_spec["source_class"]),
        "source_role": str(source_spec["source_role"]),
        "source_type": str(source_spec["source_type"]),
        "relationship_directions": relationship_directions,
        "publication_date": publication_date,
        "research_as_of": research_as_of,
        "source_url": source_url,
        "title": title,
        "capture_ref": capture_ref,
        "capture_sha256": capture_sha256,
        "body_sha256": str(response_capture["body_sha256"]),
        "body_bytes": len(body),
        "parser_profile": "pypdf_bounded_page_text",
        "content_root_kind": "pdf_pages",
        "segments": segment_rows,
        "parse_quality_receipt": {
            "page_count": len(page_texts),
            "visible_page_count": len(visible_pages),
            "segment_count": len(segment_rows),
            "visible_text_characters": sum(len(value) for value in visible_pages),
            "empty_or_thin_page_count": len(page_texts) - len(visible_pages),
            "ocr_executed": False,
        },
        "authority": {
            "candidate_not_evidence": True,
            "source_strength_does_not_prove_claim": True,
            "speaker_is_not_target_company_unless_identity_matches": True,
            "exact_target_numeric_authority": False,
        },
    }
    return {**unsigned, "source_object_digest": canonical_digest(unsigned)}


def compile_public_context_candidate(
    *,
    source_object: Mapping[str, Any],
    candidate_spec: Mapping[str, Any],
    source_use_policy: SourceUsePolicy,
) -> dict[str, Any]:
    """Bind an exact captured excerpt to one proposition and source-use decision."""

    excerpt = _normalized(candidate_spec.get("excerpt"))
    proposition_id = str(candidate_spec.get("proposition_id") or "")
    source_id = str(source_object.get("source_id") or "")
    _require(
        source_object.get("schema_version")
        in {
            PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION,
            PUBLIC_PDF_SOURCE_OBJECT_SCHEMA_VERSION,
        }
        and source_object.get("status")
        == "captured_public_source_compiled_not_evidence"
        and source_object.get("authority", {}).get("candidate_not_evidence") is True
        and proposition_id
        and excerpt,
        "public_context_candidate_input_invalid",
    )
    matching_segments = [
        row
        for row in source_object.get("segments") or ()
        if excerpt in _normalized(row.get("text"))
    ]
    _require(
        matching_segments,
        "public_context_candidate_excerpt_not_capture_bound",
    )
    decision = evaluate_source_claim_use(
        policy=source_use_policy,
        source_class=str(source_object.get("source_class") or ""),
        claim_use=str(candidate_spec.get("claim_use") or ""),
        original_capture_bound=True,
        speaker_bound=candidate_spec.get("speaker_bound") is True,
        subject_bound=candidate_spec.get("subject_bound") is True,
        independent_source_count=int(
            candidate_spec.get("independent_source_count") or 0
        ),
        license_entitled=candidate_spec.get("license_entitled") is True,
        requested_rights=("internal_analysis", "citation"),
    )
    seed = {
        "source_object_digest": str(source_object.get("source_object_digest") or ""),
        "proposition_id": proposition_id,
        "excerpt": excerpt,
        "claim_use": str(candidate_spec.get("claim_use") or ""),
    }
    body = {
        "schema_version": PUBLIC_CONTEXT_CANDIDATE_SCHEMA_VERSION,
        "candidate_id": "PUBCAND::" + canonical_digest(seed)[:20].upper(),
        "case_key": str(source_object.get("case_key") or ""),
        "source_id": source_id,
        "source_object_digest": str(source_object.get("source_object_digest") or ""),
        "proposition_id": proposition_id,
        "excerpt": excerpt,
        "excerpt_digest": canonical_digest(excerpt),
        "segment_ids": sorted(str(row["segment_id"]) for row in matching_segments),
        "speaker_entity": source_object.get("speaker_entity"),
        "source_class": source_object.get("source_class"),
        "source_role": source_object.get("source_role"),
        "publication_date": source_object.get("publication_date"),
        "relationship_directions": deepcopy(
            source_object.get("relationship_directions") or []
        ),
        "claim_use": str(candidate_spec.get("claim_use") or ""),
        "source_use_decision": decision,
        "candidate_not_evidence": True,
        "evidence_admission_required": decision.get("evidence_promotion_allowed")
        is True,
        "target_company_exact_numeric_authority": False,
    }
    return {**body, "candidate_digest": canonical_digest(body)}


__all__ = [
    "PUBLIC_CONTEXT_CANDIDATE_SCHEMA_VERSION",
    "PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION",
    "PUBLIC_PDF_SOURCE_OBJECT_SCHEMA_VERSION",
    "PUBLICATION_DATE_RECEIPT_SCHEMA_VERSION",
    "PublicContextSourceError",
    "adjudicate_publication_date_from_capture",
    "compile_public_context_candidate",
    "compile_public_html_source_object",
    "compile_public_pdf_source_object",
]
