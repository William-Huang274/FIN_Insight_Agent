from __future__ import annotations

import base64
from copy import deepcopy
from datetime import date
import hashlib
import json
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

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
        == PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION
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
    "PublicContextSourceError",
    "compile_public_context_candidate",
    "compile_public_html_source_object",
]
