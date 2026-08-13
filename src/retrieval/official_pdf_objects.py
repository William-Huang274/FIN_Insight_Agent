from __future__ import annotations

from typing import Any, Mapping

from ingestion.official_pdf import PARSED_OFFICIAL_PDF_SCHEMA_VERSION

from .financial_objects import (
    FINANCIAL_OBJECT_SCHEMA_VERSION,
    FinancialObjectError,
    content_digest,
    document_parent_id,
)


def compile_official_pdf_document(
    parsed: Mapping[str, Any],
    *,
    source_spec: Mapping[str, Any],
    parsed_ref: str,
    parsed_sha256: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Compile page-bounded official PDF text into candidate financial objects."""

    ticker = str(source_spec.get("ticker") or "").strip().upper()
    company = str(source_spec.get("company") or "").strip()
    source_type = str(source_spec.get("source_type") or "").strip().upper()
    source_tier = str(source_spec.get("source_tier") or "").strip()
    period_end = str(source_spec.get("period_end") or "").strip()
    fiscal_year = source_spec.get("fiscal_year")
    license_scope = str(source_spec.get("license_scope") or "").strip()
    expected = {
        "route_id": str(source_spec.get("route_id") or "").strip(),
        "issuer_name": company,
        "publication_date": str(source_spec.get("publication_date") or "").strip(),
        "source_url": str(source_spec.get("source_url") or "").strip(),
    }
    if not (
        parsed.get("schema_version") == PARSED_OFFICIAL_PDF_SCHEMA_VERSION
        and parsed.get("parsed_document_is_evidence") is False
        and parsed.get("promotion_status") == "parsed_source_only_not_evidence"
        and ticker
        and company
        and source_type
        and source_tier
        and license_scope
        and period_end
        and isinstance(fiscal_year, int)
        and all(str(parsed.get(key) or "") == value for key, value in expected.items())
    ):
        raise FinancialObjectError("official_pdf_source_contract_invalid")

    pages = list(parsed.get("pages") or ())
    if not pages:
        raise FinancialObjectError("official_pdf_pages_missing")
    parent_id = document_parent_id(
        ticker=ticker,
        source_type=source_type,
        source_url=expected["source_url"],
    )
    children: list[dict[str, Any]] = []
    seen_pages: set[int] = set()
    for raw_page in pages:
        if not isinstance(raw_page, Mapping):
            raise FinancialObjectError("official_pdf_page_contract_invalid")
        page_number = int(raw_page.get("page_number") or 0)
        text = str(raw_page.get("text") or "").strip()
        text_sha256 = str(raw_page.get("text_sha256") or "")
        if page_number < 1 or page_number in seen_pages:
            raise FinancialObjectError("official_pdf_page_contract_invalid")
        seen_pages.add(page_number)
        if not text:
            continue
        if content_digest(text) != text_sha256:
            raise FinancialObjectError("official_pdf_page_text_digest_mismatch")
        evidence_id = f"{parent_id}::PAGE_{page_number:03d}"
        children.append(
            {
                "evidence_id": evidence_id,
                "source_type": source_type,
                "source_tier": source_tier,
                "license_scope": license_scope,
                "redistributable": False,
                "ticker": ticker,
                "company": company,
                "fiscal_year": fiscal_year,
                "period_end": period_end,
                "publication_date": expected["publication_date"],
                "section": str(parsed.get("title") or source_type),
                "subsection": f"Transcript page {page_number}",
                "evidence_type": "earnings_call_transcript_page",
                "topics": [],
                "text": text,
                "source_url": expected["source_url"],
                "metadata": {
                    "object_schema_version": FINANCIAL_OBJECT_SCHEMA_VERSION,
                    "object_level": "retrieval_child",
                    "parent_document_id": parent_id,
                    "route_id": expected["route_id"],
                    "page_number": page_number,
                    "page_text_sha256": text_sha256,
                    "parse_method": str(parsed.get("parser_adapter") or ""),
                    "source_capture_ref": str(parsed.get("raw_object_ref") or ""),
                    "source_capture_sha256": str(parsed.get("raw_object_sha256") or ""),
                    "parsed_artifact_ref": parsed_ref,
                    "parsed_artifact_sha256": parsed_sha256,
                    "source_text_digest": str(parsed.get("source_text_digest") or ""),
                    "publication_date_source": "bound_source_intake_route",
                    "period_end_source": "bound_source_policy",
                    "candidate_is_not_evidence": True,
                },
            }
        )
    if not children:
        raise FinancialObjectError("official_pdf_children_missing")
    parent = {
        "schema_version": FINANCIAL_OBJECT_SCHEMA_VERSION,
        "object_type": "source_document_parent",
        "document_id": parent_id,
        "ticker": ticker,
        "company": company,
        "source_type": source_type,
        "source_tier": source_tier,
        "publication_date": expected["publication_date"],
        "period_end": period_end,
        "fiscal_year": fiscal_year,
        "accession_number": None,
        "source_url": expected["source_url"],
        "capture_ref": str(parsed.get("raw_object_ref") or ""),
        "capture_sha256": str(parsed.get("raw_object_sha256") or ""),
        "source_text_digest": str(parsed.get("source_text_digest") or ""),
        "source_text_characters": int(parsed.get("text_characters") or 0),
        "section_count": len(children),
        "child_count": len(children),
        "parse_method": str(parsed.get("parser_adapter") or ""),
        "lineage_state": "immutable_capture_bound",
        "route_id": expected["route_id"],
        "license_scope": license_scope,
        "redistributable": False,
        "parsed_artifact_ref": parsed_ref,
        "parsed_artifact_sha256": parsed_sha256,
    }
    return parent, children


__all__ = ["compile_official_pdf_document"]
