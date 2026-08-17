from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Mapping, Sequence

from ingestion.pdf_layout import PARSED_PDF_LAYOUT_SCHEMA_VERSION

from .financial_objects import (
    FINANCIAL_OBJECT_SCHEMA_VERSION,
    FinancialObjectError,
    content_digest,
    document_parent_id,
)


PDF_LAYOUT_OBJECT_SET_SCHEMA_VERSION = "fin_ia_pdf_layout_object_set_v1_0"


def compile_pdf_layout_document(
    parsed: Mapping[str, Any],
    *,
    source_spec: Mapping[str, Any],
    parsed_ref: str,
    parsed_sha256: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Compile layout observations into candidate financial objects.

    This is deliberately an S1 object compiler, not an Evidence or NumericFact
    producer.  It preserves page/bbox/table/footnote/revision lineage while
    allowing the same lexical/dense/rerank stack to consume heterogeneous PDF
    objects without learning parser-specific wire formats.
    """

    _validate_inputs(parsed, source_spec)
    ticker = str(source_spec["ticker"]).strip().upper()
    company = str(source_spec["company"]).strip()
    source_type = str(source_spec["source_type"]).strip().upper()
    source_tier = str(source_spec["source_tier"]).strip()
    period_end = str(source_spec["period_end"]).strip()
    publication_date = str(source_spec["publication_date"]).strip()
    fiscal_year = int(source_spec["fiscal_year"])
    source_url = str(source_spec["source_url"]).strip()
    parent_id = document_parent_id(
        ticker=ticker,
        source_type=source_type,
        source_url=source_url,
    )

    common = {
        "source_type": source_type,
        "source_tier": source_tier,
        "license_scope": str(source_spec["license_scope"]),
        "redistributable": False,
        "ticker": ticker,
        "company": company,
        "fiscal_year": fiscal_year,
        "period_end": period_end,
        "publication_date": publication_date,
        "source_url": source_url,
    }
    metadata_common = {
        "object_schema_version": FINANCIAL_OBJECT_SCHEMA_VERSION,
        "object_level": "retrieval_child",
        "parent_document_id": parent_id,
        "route_id": str(parsed.get("route_id") or ""),
        "parse_method": str(parsed.get("parser_adapter") or ""),
        "source_capture_ref": str(parsed.get("raw_object_ref") or ""),
        "source_capture_sha256": str(parsed.get("raw_object_sha256") or ""),
        "parsed_artifact_ref": parsed_ref,
        "parsed_artifact_sha256": parsed_sha256,
        "source_text_digest": str(parsed.get("source_text_digest") or ""),
        "publication_date_source": "bound_official_source_metadata",
        "period_end_source": "bound_source_policy",
        "candidate_is_not_evidence": True,
        "numeric_fact_authority": False,
    }

    children: list[dict[str, Any]] = []
    table_rows_by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)
    page_ids: dict[int, str] = {}
    table_ids: dict[tuple[int, int], str] = {}
    for raw_page in parsed.get("pages") or ():
        if not isinstance(raw_page, Mapping):
            raise FinancialObjectError("pdf_layout_page_object_invalid")
        page_number = int(raw_page.get("page_number") or 0)
        page_text = str(raw_page.get("text") or "").strip()
        if page_number < 1 or not page_text:
            raise FinancialObjectError("pdf_layout_page_object_invalid")
        if content_digest(page_text) != str(raw_page.get("text_sha256") or ""):
            raise FinancialObjectError("pdf_layout_page_text_digest_mismatch")

        page_id = f"{parent_id}::PAGE_{page_number:03d}::CONTEXT"
        page_ids[page_number] = page_id
        children.append(
            _object(
                evidence_id=page_id,
                common=common,
                section=str(parsed.get("title") or source_type),
                subsection=f"Page {page_number} context",
                evidence_type="pdf_page_context",
                text=page_text,
                metadata={
                    **metadata_common,
                    "page_number": page_number,
                    "locator_type": "page",
                    "locator_value": str(page_number),
                    "page_text_sha256": raw_page["text_sha256"],
                    "page_status": raw_page.get("page_status"),
                    "extraction_mode": raw_page.get("extraction_mode"),
                    "candidate_role": "page_context",
                },
            )
        )

        for raw_block in raw_page.get("text_blocks") or ():
            block = _mapping(raw_block, "pdf_layout_text_block_invalid")
            if block.get("block_role") != "revision_or_restatement_context":
                continue
            block_text = str(block.get("text") or "").strip()
            if not block_text:
                continue
            block_id = (
                f"{parent_id}::PAGE_{page_number:03d}::REVISION_"
                f"{int(block.get('block_index') or 0):02d}"
            )
            children.append(
                _object(
                    evidence_id=block_id,
                    common=common,
                    section="Revision and restatement context",
                    subsection=f"Page {page_number} revision context",
                    evidence_type="revision_or_restatement_context",
                    text=block_text,
                    metadata={
                        **metadata_common,
                        "page_number": page_number,
                        "bbox": deepcopy(block.get("bbox")),
                        "locator_type": "page_bbox",
                        "locator_value": _page_bbox_locator(page_number, block.get("bbox")),
                        "candidate_role": "revision_or_restatement_context",
                        "parent_page_object_id": page_id,
                    },
                )
            )

        for raw_table in raw_page.get("table_regions") or ():
            table = _mapping(raw_table, "pdf_layout_table_invalid")
            table_index = int(table.get("table_index") or 0)
            rows = [
                deepcopy(dict(_mapping(row, "pdf_layout_table_row_invalid")))
                for row in table.get("rows") or ()
            ]
            if table_index < 1 or not rows:
                raise FinancialObjectError("pdf_layout_table_invalid")
            table_text = "\n".join(str(row.get("text") or "").strip() for row in rows)
            table_id = (
                f"{parent_id}::PAGE_{page_number:03d}::TABLE_{table_index:02d}"
            )
            table_ids[(page_number, table_index)] = table_id
            children.append(
                _object(
                    evidence_id=table_id,
                    common=common,
                    section="Financial statement table",
                    subsection=f"Page {page_number} table {table_index}",
                    evidence_type="financial_table_region",
                    text=table_text,
                    metadata={
                        **metadata_common,
                        "page_number": page_number,
                        "table_index": table_index,
                        "bbox": deepcopy(table.get("bbox")),
                        "locator_type": "page_bbox",
                        "locator_value": _page_bbox_locator(page_number, table.get("bbox")),
                        "candidate_role": "financial_table_region",
                        "table_binding_status": table.get("table_binding_status"),
                        "detection_method": table.get("detection_method"),
                        "parent_page_object_id": page_id,
                        "row_count": len(rows),
                    },
                )
            )
            for row in rows:
                row_text = str(row.get("text") or "").strip()
                numeric_tokens = [str(value) for value in row.get("numeric_tokens") or ()]
                if not row_text:
                    continue
                row_id = (
                    f"{table_id}::ROW_{int(row.get('row_index') or 0):03d}"
                )
                row_object = _object(
                    evidence_id=row_id,
                    common=common,
                    section="Financial statement metric row",
                    subsection=(
                        f"Page {page_number} table {table_index} row "
                        f"{int(row.get('row_index') or 0)}"
                    ),
                    evidence_type="financial_table_metric_row",
                    text=_row_context_text(table_text, row_text),
                    metadata={
                        **metadata_common,
                        "page_number": page_number,
                        "table_index": table_index,
                        "row_index": int(row.get("row_index") or 0),
                        "bbox": deepcopy(row.get("bbox")),
                        "locator_type": "table_cell",
                        "locator_value": (
                            f"page={page_number};table={table_index};"
                            f"row={int(row.get('row_index') or 0)}"
                        ),
                        "candidate_role": "financial_table_metric_row",
                        "row_binding_status": row.get("row_binding_status"),
                        "numeric_tokens": numeric_tokens,
                        "parent_table_object_id": table_id,
                        "parent_page_object_id": page_id,
                    },
                )
                children.append(row_object)
                table_rows_by_page[page_number].append(
                    {
                        "evidence_id": row_id,
                        "row_text": row_text,
                        "numeric_tokens": numeric_tokens,
                        "table_index": table_index,
                    }
                )

        for raw_note in raw_page.get("footnotes") or ():
            note = _mapping(raw_note, "pdf_layout_footnote_invalid")
            note_text = str(note.get("text") or "").strip()
            if not note_text:
                continue
            note_index = int(note.get("footnote_index") or 0)
            note_id = f"{parent_id}::PAGE_{page_number:03d}::FOOTNOTE_{note_index:02d}"
            linked_tables = [
                table_id
                for (table_page, _), table_id in table_ids.items()
                if table_page == page_number
            ]
            children.append(
                _object(
                    evidence_id=note_id,
                    common=common,
                    section="Financial statement footnote",
                    subsection=f"Page {page_number} footnote {note.get('marker')}",
                    evidence_type="financial_table_footnote",
                    text=note_text,
                    metadata={
                        **metadata_common,
                        "page_number": page_number,
                        "footnote_index": note_index,
                        "footnote_marker": str(note.get("marker") or ""),
                        "bbox": deepcopy(note.get("bbox")),
                        "locator_type": "page_bbox",
                        "locator_value": _page_bbox_locator(page_number, note.get("bbox")),
                        "candidate_role": "financial_table_footnote",
                        "binding_status": note.get("binding_status"),
                        "linked_table_object_ids": linked_tables,
                        "parent_page_object_id": page_id,
                    },
                )
            )

    cross_page = _cross_page_relations(table_rows_by_page)
    for relation_index, relation in enumerate(cross_page, start=1):
        relation_id = f"{parent_id}::CROSS_PAGE_RELATION_{relation_index:02d}"
        children.append(
            _object(
                evidence_id=relation_id,
                common=common,
                section="Cross-page financial table continuation",
                subsection=(
                    f"Pages {relation['left_page']}–{relation['right_page']}"
                ),
                evidence_type="cross_page_table_continuation_candidate",
                text=(
                    "Cross-page table continuation candidate. Previous page row: "
                    f"{relation['left_row_text']}. Following page row: "
                    f"{relation['right_row_text']}. Matching reported values: "
                    f"{' / '.join(relation['matching_numeric_tokens'])}."
                ),
                metadata={
                    **metadata_common,
                    "locator_type": "object_id",
                    "locator_value": (
                        f"{relation['left_object_id']}->{relation['right_object_id']}"
                    ),
                    "candidate_role": "cross_page_table_continuation_candidate",
                    "left_page": relation["left_page"],
                    "right_page": relation["right_page"],
                    "left_object_id": relation["left_object_id"],
                    "right_object_id": relation["right_object_id"],
                    "matching_numeric_tokens": relation["matching_numeric_tokens"],
                    "continuation_status": "candidate_needs_financial_header_review",
                },
            )
        )

    if not children:
        raise FinancialObjectError("pdf_layout_children_missing")
    object_types: dict[str, int] = defaultdict(int)
    for child in children:
        object_types[str(child["evidence_type"])] += 1
    object_set = {
        "schema_version": PDF_LAYOUT_OBJECT_SET_SCHEMA_VERSION,
        "status": "complex_pdf_candidate_objects_materialized",
        "document_id": parent_id,
        "source_owner_ticker": ticker,
        "source_type": source_type,
        "selected_page_numbers": list(parsed.get("selected_page_numbers") or ()),
        "object_count": len(children),
        "object_type_counts": dict(sorted(object_types.items())),
        "cross_page_relation_count": len(cross_page),
        "candidate_is_not_evidence": True,
        "numeric_fact_authority_granted": False,
        "object_ids": [str(row["evidence_id"]) for row in children],
    }
    object_set["object_set_digest"] = content_digest(object_set)
    parent = {
        "schema_version": FINANCIAL_OBJECT_SCHEMA_VERSION,
        "object_type": "source_document_parent",
        "document_id": parent_id,
        "ticker": ticker,
        "company": company,
        "source_type": source_type,
        "source_tier": source_tier,
        "publication_date": publication_date,
        "period_end": period_end,
        "fiscal_year": fiscal_year,
        "accession_number": None,
        "source_url": source_url,
        "capture_ref": str(parsed.get("raw_object_ref") or ""),
        "capture_sha256": str(parsed.get("raw_object_sha256") or ""),
        "source_text_digest": str(parsed.get("source_text_digest") or ""),
        "source_text_characters": sum(len(str(page.get("text") or "")) for page in parsed.get("pages") or ()),
        "section_count": len(parsed.get("pages") or ()),
        "child_count": len(children),
        "parse_method": str(parsed.get("parser_adapter") or ""),
        "lineage_state": "immutable_capture_bound",
        "route_id": str(parsed.get("route_id") or ""),
        "license_scope": str(source_spec["license_scope"]),
        "redistributable": False,
        "parsed_artifact_ref": parsed_ref,
        "parsed_artifact_sha256": parsed_sha256,
        "quality_receipt_digest": str((parsed.get("quality_receipt") or {}).get("quality_digest") or ""),
    }
    return parent, children, object_set


def _validate_inputs(parsed: Mapping[str, Any], source_spec: Mapping[str, Any]) -> None:
    required_spec = (
        "ticker",
        "company",
        "source_type",
        "source_tier",
        "period_end",
        "publication_date",
        "fiscal_year",
        "source_url",
        "license_scope",
    )
    quality = parsed.get("quality_receipt")
    if not (
        parsed.get("schema_version") == PARSED_PDF_LAYOUT_SCHEMA_VERSION
        and parsed.get("parsed_document_is_evidence") is False
        and parsed.get("promotion_status") == "parsed_layout_candidates_only_not_evidence"
        and parsed.get("capture_before_parse") is True
        and isinstance(quality, Mapping)
        and quality.get("complete_document_page_count_verified") is True
        and quality.get("accepted_evidence_authority_granted") is False
        and quality.get("numeric_fact_authority_granted") is False
        and all(source_spec.get(key) not in (None, "") for key in required_spec)
        and str(parsed.get("source_owner_ticker") or "").upper()
        == str(source_spec.get("ticker") or "").upper()
        and str(parsed.get("source_url") or "") == str(source_spec.get("source_url") or "")
        and str(parsed.get("publication_date") or "")
        == str(source_spec.get("publication_date") or "")
    ):
        raise FinancialObjectError("pdf_layout_source_contract_invalid")


def _object(
    *,
    evidence_id: str,
    common: Mapping[str, Any],
    section: str,
    subsection: str,
    evidence_type: str,
    text: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    if not text.strip():
        raise FinancialObjectError("pdf_layout_object_text_missing")
    return {
        "evidence_id": evidence_id,
        **deepcopy(dict(common)),
        "section": section,
        "subsection": subsection,
        "evidence_type": evidence_type,
        "topics": [],
        "text": text.strip(),
        "metadata": deepcopy(dict(metadata)),
    }


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FinancialObjectError(code)
    return value


def _page_bbox_locator(page_number: int, bbox: object) -> str:
    if not isinstance(bbox, Sequence) or isinstance(bbox, (str, bytes)) or len(bbox) != 4:
        raise FinancialObjectError("pdf_layout_bbox_invalid")
    return "page={};bbox={}".format(
        page_number,
        ",".join(f"{float(value):.4f}" for value in bbox),
    )


def _row_context_text(table_text: str, row_text: str) -> str:
    header = "\n".join(table_text.splitlines()[:3])
    return f"Table header/context:\n{header}\nSelected metric row:\n{row_text}"


def _cross_page_relations(
    rows_by_page: Mapping[int, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    relations: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    pages = sorted(rows_by_page)
    for left_page, right_page in zip(pages, pages[1:]):
        if right_page != left_page + 1:
            continue
        for left in rows_by_page[left_page]:
            left_tokens = tuple(
                value
                for value in (
                    str(raw) for raw in left.get("numeric_tokens") or ()
                )
                if _cross_page_value_token(value)
            )
            if len(left_tokens) < 2:
                continue
            for right in rows_by_page[right_page]:
                right_tokens = tuple(
                    value
                    for value in (
                        str(raw) for raw in right.get("numeric_tokens") or ()
                    )
                    if _cross_page_value_token(value)
                )
                matching = [value for value in left_tokens if value in set(right_tokens)]
                if len(set(matching)) < 2:
                    continue
                pair = (str(left["evidence_id"]), str(right["evidence_id"]))
                if pair in seen:
                    continue
                seen.add(pair)
                relations.append(
                    {
                        "left_page": left_page,
                        "right_page": right_page,
                        "left_object_id": pair[0],
                        "right_object_id": pair[1],
                        "left_row_text": str(left.get("row_text") or ""),
                        "right_row_text": str(right.get("row_text") or ""),
                        "matching_numeric_tokens": sorted(set(matching)),
                    }
                )
    return relations


def _cross_page_value_token(value: str) -> bool:
    token = value.strip().strip("()")
    if token in {"€", "$", "£", "¥", "-", "–", "—"}:
        return False
    digits = token.replace(",", "").replace(".", "").rstrip("%")
    if not digits.isdigit():
        return False
    if token.isdigit() and len(token) == 4 and 1900 <= int(token) <= 2200:
        return False
    return True


__all__ = [
    "PDF_LAYOUT_OBJECT_SET_SCHEMA_VERSION",
    "compile_pdf_layout_document",
]
