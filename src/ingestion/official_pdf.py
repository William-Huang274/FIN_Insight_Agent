from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping
import unicodedata

from pypdf import PdfReader


PARSED_OFFICIAL_PDF_SCHEMA_VERSION = "fin_ia_parsed_official_pdf_document_v1_0"
SOURCE_INTAKE_ATTEMPT_SCHEMA_VERSION = "fin_ia_source_intake_attempt_v1_0"


class OfficialPdfParseError(ValueError):
    """A captured official PDF could not be parsed without weakening lineage."""


def parse_captured_official_pdf(
    attempt: Mapping[str, Any],
    *,
    private_source_intake_root: str | Path,
) -> dict[str, Any]:
    """Parse an immutable Source Intake PDF into page-bounded private text.

    This function deliberately grants no retrieval or Evidence authority.  It
    only validates the capture lineage and extracts text while preserving page
    locators and digests.
    """

    if not (
        attempt.get("schema_version") == SOURCE_INTAKE_ATTEMPT_SCHEMA_VERSION
        and attempt.get("status") == "captured_ready_for_parse"
        and attempt.get("capture_before_parse") is True
        and attempt.get("source_body_is_evidence") is False
        and attempt.get("promotion_status") == "source_only_not_evidence"
        and attempt.get("pdf_signature_valid") is True
        and attempt.get("pdf_eof_valid") is True
        and attempt.get("pdf_encrypted") is False
    ):
        raise OfficialPdfParseError("official_pdf_capture_boundary_invalid")

    root = Path(private_source_intake_root).resolve()
    raw_ref = str(attempt.get("raw_object_ref") or "").strip()
    raw_path = _safe_relative_path(root, raw_ref)
    if not raw_path.is_file():
        raise OfficialPdfParseError("official_pdf_raw_object_missing")
    body = raw_path.read_bytes()
    body_digest = hashlib.sha256(body).hexdigest()
    if (
        not body
        or body_digest != str(attempt.get("raw_object_sha256") or "")
        or len(body) != int(attempt.get("raw_object_bytes") or -1)
    ):
        raise OfficialPdfParseError("official_pdf_raw_object_digest_mismatch")

    try:
        reader = PdfReader(BytesIO(body))
    except Exception as exc:  # pragma: no cover - pypdf exception family varies
        raise OfficialPdfParseError("official_pdf_reader_failed") from exc
    if reader.is_encrypted:
        raise OfficialPdfParseError("official_pdf_encrypted")
    expected_pages = int(attempt.get("pdf_page_count") or 0)
    if expected_pages < 1 or len(reader.pages) != expected_pages:
        raise OfficialPdfParseError("official_pdf_page_count_mismatch")

    pages: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        try:
            raw_text = page.extract_text() or ""
        except Exception as exc:  # pragma: no cover - parser backends vary
            raise OfficialPdfParseError(
                f"official_pdf_page_extract_failed:{page_number}"
            ) from exc
        text = _normalize_extracted_text(raw_text)
        pages.append(
            {
                "page_number": page_number,
                "text": text,
                "text_characters": len(text),
                "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    nonempty_pages = sum(bool(page["text"]) for page in pages)
    text_characters = sum(int(page["text_characters"]) for page in pages)
    if nonempty_pages == 0 or text_characters < 200:
        raise OfficialPdfParseError("official_pdf_text_empty_or_too_short")

    text_identity = "\n".join(
        f"PAGE:{page['page_number']}:{page['text_sha256']}" for page in pages
    )
    return {
        "schema_version": PARSED_OFFICIAL_PDF_SCHEMA_VERSION,
        "parser_adapter": "pypdf_page_text_v1",
        "attempt_id": str(attempt["attempt_id"]),
        "route_id": str(attempt["route_id"]),
        "case_key": str(attempt["case_key"]),
        "issuer_name": str(attempt["issuer_name"]),
        "document_type": str(attempt["document_type"]),
        "title": str(attempt["title"]),
        "publication_date": str(attempt["publication_date"]),
        "source_url": str(attempt["source_url"]),
        "raw_object_ref": raw_ref,
        "raw_object_sha256": body_digest,
        "raw_object_bytes": len(body),
        "page_count": len(pages),
        "nonempty_page_count": nonempty_pages,
        "text_characters": text_characters,
        "source_text_digest": hashlib.sha256(text_identity.encode("utf-8")).hexdigest(),
        "pages": pages,
        "capture_before_parse": True,
        "parsed_document_is_evidence": False,
        "promotion_status": "parsed_source_only_not_evidence",
    }


def public_parsed_official_pdf_projection(
    parsed: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": parsed.get("schema_version"),
        "parser_adapter": parsed.get("parser_adapter"),
        "attempt_id": parsed.get("attempt_id"),
        "route_id": parsed.get("route_id"),
        "case_key": parsed.get("case_key"),
        "issuer_name": parsed.get("issuer_name"),
        "document_type": parsed.get("document_type"),
        "title": parsed.get("title"),
        "publication_date": parsed.get("publication_date"),
        "source_url": parsed.get("source_url"),
        "raw_object_sha256": parsed.get("raw_object_sha256"),
        "raw_object_bytes": parsed.get("raw_object_bytes"),
        "page_count": parsed.get("page_count"),
        "nonempty_page_count": parsed.get("nonempty_page_count"),
        "text_characters": parsed.get("text_characters"),
        "source_text_digest": parsed.get("source_text_digest"),
        "promotion_status": parsed.get("promotion_status"),
    }


def _safe_relative_path(root: Path, value: str) -> Path:
    if not value or Path(value).is_absolute():
        raise OfficialPdfParseError("official_pdf_raw_object_ref_invalid")
    resolved = (root / value).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise OfficialPdfParseError("official_pdf_raw_object_ref_invalid") from exc
    return resolved


def _normalize_extracted_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).replace("\x00", "")
    lines = [" ".join(line.split()) for line in normalized.splitlines()]
    return "\n".join(line for line in lines if line).strip()


__all__ = [
    "OfficialPdfParseError",
    "PARSED_OFFICIAL_PDF_SCHEMA_VERSION",
    "parse_captured_official_pdf",
    "public_parsed_official_pdf_projection",
]
