from __future__ import annotations

from collections import Counter
import base64
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from ingestion.section_splitter import (
    SecFilingSection,
    build_semantic_blocks,
    chunk_semantic_block,
    find_sec_filing_sections,
)


FINANCIAL_OBJECT_SCHEMA_VERSION = "fin_ia_financial_retrieval_object_v1_0"
SOURCE_MANIFEST_SCHEMA_VERSION = "fin_ia_s1b_source_object_manifest_v1_0"
MAX_NON_TABLE_CHILD_CHARACTERS = 12_000
MAX_TABLE_CHILD_CHARACTERS = 50_000


class FinancialObjectError(ValueError):
    """Raised when a source cannot be projected without weakening lineage."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def content_digest(value: object) -> str:
    if isinstance(value, str):
        payload = value.encode("utf-8")
    else:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_source_object_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    if value.get("schema_version") != SOURCE_MANIFEST_SCHEMA_VERSION:
        raise FinancialObjectError("source_object_manifest_schema_invalid")
    if value.get("status") != "s1b_current_source_object_manifest":
        raise FinancialObjectError("source_object_manifest_status_invalid")
    policy = value.get("policy")
    if not (
        isinstance(policy, Mapping)
        and policy.get("immutable_capture_precedes_parse") is True
        and policy.get("document_parent_precedes_retrieval_child") is True
        and policy.get("candidate_is_not_evidence") is True
        and policy.get("market_snapshot_is_not_valuation") is True
    ):
        raise FinancialObjectError("source_object_manifest_policy_invalid")
    allowed = value.get("allowed_tickers")
    sources = value.get("sources")
    if not (
        isinstance(allowed, list)
        and allowed
        and len(allowed) == len(set(allowed))
        and isinstance(sources, list)
        and sources
    ):
        raise FinancialObjectError("source_object_manifest_shape_invalid")
    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, Mapping):
            raise FinancialObjectError("source_object_manifest_source_invalid")
        source_id = str(source.get("source_id") or "").strip()
        kind = str(source.get("input_kind") or "").strip()
        if (
            not source_id
            or source_id in source_ids
            or kind
            not in {
                "legacy_candidate_jsonl",
                "legacy_qrel_alias_jsonl",
                "parsed_sec_capture",
                "raw_sec_html_capture",
                "market_evidence_jsonl",
            }
            or not str(source.get("path") or "").strip()
        ):
            raise FinancialObjectError("source_object_manifest_source_invalid")
        source_ids.add(source_id)
    return value


def document_parent_id(
    *,
    ticker: str,
    source_type: str,
    accession_number: str | None = None,
    source_url: str | None = None,
    snapshot_id: str | None = None,
) -> str:
    owner = _identifier(ticker)
    kind = _identifier(source_type)
    if snapshot_id:
        authority = _identifier(snapshot_id)
    elif accession_number:
        authority = _identifier(accession_number)
    elif source_url:
        authority = content_digest(source_url)[:20].upper()
    else:
        raise FinancialObjectError("document_parent_authority_missing")
    return f"CURRENT_DOC::{owner}::{kind}::{authority}"


def compile_parsed_sec_capture(
    payload: Mapping[str, Any],
    *,
    source_spec: Mapping[str, Any],
    capture_ref: str,
    capture_sha256: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    ticker = str(payload.get("ticker") or "").strip().upper()
    form_type = str(payload.get("form_type") or "").strip().upper()
    text = str(payload.get("text") or "")
    accession = str(payload.get("accession_number") or "").strip()
    publication_date = str(payload.get("filing_date") or "").strip()
    period_end = str(payload.get("report_date") or "").strip()
    source_url = str(payload.get("source_url") or "").strip()
    company = str(source_spec.get("company") or ticker).strip()
    source_tier = str(source_spec.get("source_tier") or "primary_sec_filing")
    if not (
        ticker
        and form_type in {"10-K", "10-Q", "8-K", "6-K", "20-F", "40-F"}
        and accession
        and text
        and source_url
        and _valid_iso_date(publication_date)
        and _valid_iso_date(period_end)
    ):
        raise FinancialObjectError("parsed_sec_capture_contract_invalid")
    parser_digest = str(payload.get("parser_text_digest") or "")
    if parser_digest and parser_digest != content_digest(text):
        raise FinancialObjectError("parsed_sec_capture_text_digest_mismatch")

    if form_type in {"10-K", "10-Q", "20-F", "40-F"}:
        sections = find_sec_filing_sections(text, form_type=form_type)
        parse_method = "sec_item_semantic_blocks"
    else:
        sections = [
            SecFilingSection(
                item_code="current_report",
                section=f"{form_type} current official disclosure",
                char_start=0,
                char_end=len(text),
                text=text,
            )
        ]
        parse_method = "current_report_semantic_blocks"
    if not sections:
        raise FinancialObjectError(f"parsed_sec_sections_missing:{ticker}:{form_type}")

    parent_id = document_parent_id(
        ticker=ticker,
        source_type=form_type,
        accession_number=accession,
        source_url=source_url,
    )
    children: list[dict[str, Any]] = []
    for section in sections:
        blocks = build_semantic_blocks(section)
        if not blocks:
            continue
        for block in blocks:
            chunks = chunk_semantic_block(
                block,
                target_words=int(source_spec.get("target_words") or 700),
                overlap_words=int(source_spec.get("overlap_words") or 100),
                min_words=int(source_spec.get("min_words") or 50),
            )
            for part_index, (chunk_text, char_start, char_end) in enumerate(
                chunks,
                start=1,
            ):
                block_id = (
                    f"{parent_id}::ITEM_{_identifier(section.item_code)}"
                    f"::BLOCK_{block.block_index:04d}"
                )
                evidence_id = (
                    f"{block_id}::PART_{part_index:02d}_OF_{len(chunks):02d}"
                )
                children.append(
                    {
                        "evidence_id": evidence_id,
                        "source_type": form_type,
                        "source_tier": source_tier,
                        "license_scope": "public_official_source_research_use",
                        "redistributable": False,
                        "ticker": ticker,
                        "company": company,
                        "fiscal_year": _int_or_none(
                            payload.get("reporting_fiscal_year")
                        ),
                        "period_end": period_end,
                        "publication_date": publication_date,
                        "section": section.section,
                        "subsection": block.block_heading,
                        "evidence_type": block.block_type,
                        "topics": [],
                        "text": chunk_text,
                        "source_url": source_url,
                        "metadata": {
                            "object_schema_version": FINANCIAL_OBJECT_SCHEMA_VERSION,
                            "object_level": "retrieval_child",
                            "parent_document_id": parent_id,
                            "accession_number": accession,
                            "item_code": section.item_code,
                            "block_id": block_id,
                            "block_index": block.block_index,
                            "block_part_index": part_index,
                            "block_part_count": len(chunks),
                            "block_char_start": block.char_start,
                            "block_char_end": block.char_end,
                            "char_start": char_start,
                            "char_end": char_end,
                            "contains_table": _contains_balanced_table(chunk_text),
                            "parse_method": parse_method,
                            "source_capture_ref": capture_ref,
                            "source_capture_sha256": capture_sha256,
                            "source_text_digest": content_digest(text),
                            "parser_adapter": payload.get("parser_adapter"),
                            "publication_date_source": "sec_filing_date",
                            "period_end_source": "sec_report_date",
                        },
                    }
                )
    if not children:
        raise FinancialObjectError(f"parsed_sec_children_missing:{ticker}:{form_type}")
    _require_balanced_tables(children)
    parent = {
        "schema_version": FINANCIAL_OBJECT_SCHEMA_VERSION,
        "object_type": "source_document_parent",
        "document_id": parent_id,
        "ticker": ticker,
        "company": company,
        "source_type": form_type,
        "source_tier": source_tier,
        "publication_date": publication_date,
        "period_end": period_end,
        "fiscal_year": _int_or_none(payload.get("reporting_fiscal_year")),
        "accession_number": accession,
        "source_url": source_url,
        "capture_ref": capture_ref,
        "capture_sha256": capture_sha256,
        "source_text_digest": content_digest(text),
        "source_text_characters": len(text),
        "section_count": len(sections),
        "child_count": len(children),
        "parse_method": parse_method,
        "lineage_state": "immutable_capture_bound",
    }
    return parent, children


def compile_raw_sec_html_capture(
    payload: Mapping[str, Any],
    *,
    source_spec: Mapping[str, Any],
    capture_ref: str,
    capture_sha256: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from ingestion.parse_sec_filing import extract_sec_html_text_content

    if not (
        payload.get("capture_before_parse") is True
        and int(payload.get("status_code") or 0) == 200
        and payload.get("credential_cookie_authorization_present") is False
    ):
        raise FinancialObjectError("raw_sec_capture_boundary_invalid")
    try:
        body = base64.b64decode(str(payload.get("body_base64") or ""), validate=True)
    except (ValueError, TypeError) as exc:
        raise FinancialObjectError("raw_sec_capture_body_invalid") from exc
    body_digest = hashlib.sha256(body).hexdigest()
    if (
        not body
        or body_digest != str(payload.get("body_sha256") or "")
        or len(body) != int(payload.get("body_bytes") or 0)
    ):
        raise FinancialObjectError("raw_sec_capture_body_digest_mismatch")
    html = body.decode("utf-8", errors="replace")
    text = extract_sec_html_text_content(html)
    if not text:
        raise FinancialObjectError("raw_sec_capture_parse_empty")
    final_url = str(payload.get("final_url") or "").strip()
    expected_url = str(
        source_spec.get("capture_url") or source_spec.get("source_url") or ""
    ).strip()
    if expected_url and expected_url != final_url:
        raise FinancialObjectError("raw_sec_capture_final_url_mismatch")
    parsed_payload = {
        "ticker": source_spec.get("ticker"),
        "form_type": source_spec.get("form_type"),
        "text": text,
        "accession_number": source_spec.get("accession_number"),
        "filing_date": source_spec.get("publication_date"),
        "report_date": source_spec.get("period_end"),
        "reporting_fiscal_year": source_spec.get("fiscal_year"),
        "source_url": str(source_spec.get("source_url") or final_url).strip(),
        "parser_text_digest": content_digest(text),
        "parser_adapter": "ingestion.parse_sec_filing.extract_sec_html_text_content",
    }
    parent, children = compile_parsed_sec_capture(
        parsed_payload,
        source_spec=source_spec,
        capture_ref=capture_ref,
        capture_sha256=capture_sha256,
    )
    parent.update(
        {
            "raw_body_sha256": body_digest,
            "raw_body_bytes": len(body),
            "parse_method": f"raw_html_capture_reparsed::{parent['parse_method']}",
        }
    )
    for child in children:
        metadata = child["metadata"]
        metadata.update(
            {
                "raw_body_sha256": body_digest,
                "raw_body_bytes": len(body),
                "parse_source": "immutable_raw_html_capture_reparsed",
            }
        )
    return parent, children


def normalize_legacy_candidate(
    record: Mapping[str, Any],
    *,
    source_ref: str,
    source_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    value = dict(record)
    metadata = dict(value.get("metadata") or {})
    ticker = str(value.get("ticker") or "").strip().upper()
    source_type = str(value.get("source_type") or "").strip().upper()
    evidence_id = str(value.get("evidence_id") or "").strip()
    text = str(value.get("text") or "").strip()
    publication_date = str(value.get("publication_date") or "").strip()
    accession = str(metadata.get("accession_number") or "").strip() or None
    source_url = str(value.get("source_url") or "").strip() or None
    if not (
        ticker
        and source_type
        and evidence_id
        and text
        and _valid_iso_date(publication_date)
        and (accession or source_url)
    ):
        raise FinancialObjectError("legacy_candidate_contract_invalid")
    parent_id = document_parent_id(
        ticker=ticker,
        source_type=source_type,
        accession_number=accession,
        source_url=source_url,
    )
    metadata.update(
        {
            "object_schema_version": FINANCIAL_OBJECT_SCHEMA_VERSION,
            "object_level": "retrieval_child",
            "parent_document_id": parent_id,
            "source_object_origin": "legacy_semantic_child_reused",
            "source_store_ref": source_ref,
            "source_store_sha256": source_sha256,
        }
    )
    value.update(
        {
            "ticker": ticker,
            "source_type": source_type,
            "text": text,
            "metadata": metadata,
        }
    )
    parent = {
        "schema_version": FINANCIAL_OBJECT_SCHEMA_VERSION,
        "object_type": "source_document_parent",
        "document_id": parent_id,
        "ticker": ticker,
        "company": value.get("company"),
        "source_type": source_type,
        "source_tier": value.get("source_tier"),
        "publication_date": publication_date,
        "period_end": value.get("period_end"),
        "fiscal_year": value.get("fiscal_year"),
        "accession_number": accession,
        "source_url": source_url,
        "capture_ref": None,
        "capture_sha256": None,
        "source_text_digest": None,
        "source_text_characters": None,
        "section_count": None,
        "child_count": 0,
        "parse_method": "legacy_semantic_child_reused",
        "lineage_state": "local_candidate_store_lineage_only",
        "source_store_ref": source_ref,
        "source_store_sha256": source_sha256,
    }
    return parent, value


def project_market_snapshot(
    record: Mapping[str, Any],
    *,
    source_ref: str,
    source_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    ticker = str(record.get("ticker") or "").strip().upper()
    as_of_date = str(record.get("as_of_date") or "").strip()
    snapshot_id = str(record.get("snapshot_id") or "").strip()
    evidence_id = str(record.get("evidence_id") or "").strip()
    text = str(record.get("text") or "").strip()
    if not (
        ticker
        and snapshot_id
        and evidence_id
        and text
        and _valid_iso_date(as_of_date)
    ):
        raise FinancialObjectError("market_snapshot_contract_invalid")
    parent_id = document_parent_id(
        ticker=ticker,
        source_type="MARKET_SNAPSHOT",
        snapshot_id=snapshot_id,
    )
    fields = dict(record.get("field_status") or {})
    missing_fields = list(record.get("missing_fields") or ())
    child = {
        "evidence_id": evidence_id,
        "source_type": "MARKET_SNAPSHOT",
        "source_tier": "market_snapshot",
        "license_scope": "provider_terms_research_use",
        "redistributable": False,
        "ticker": ticker,
        "company": ticker,
        "fiscal_year": int(as_of_date[:4]),
        "period_end": as_of_date,
        "publication_date": as_of_date,
        "section": "Point-in-time market snapshot",
        "subsection": "Price, returns and valuation-field availability",
        "evidence_type": "point_in_time_market_snapshot",
        "topics": ["market price", "valuation"],
        "text": text,
        "source_url": None,
        "metadata": {
            "object_schema_version": FINANCIAL_OBJECT_SCHEMA_VERSION,
            "object_level": "retrieval_child",
            "parent_document_id": parent_id,
            "snapshot_id": snapshot_id,
            "provider": record.get("provider"),
            "as_of_date": as_of_date,
            "field_status": fields,
            "missing_fields": missing_fields,
            "valuation_context": record.get("valuation_context"),
            "market_reaction": record.get("market_reaction"),
            "source_boundary": record.get("source_boundary"),
            "source_store_ref": source_ref,
            "source_store_sha256": source_sha256,
            "market_snapshot_is_not_valuation": any(
                fields.get(name) != "provided"
                for name in (
                    "market_cap",
                    "enterprise_value",
                    "pe_ttm",
                    "ev_sales_ttm",
                    "ev_ebitda_ttm",
                )
            ),
        },
    }
    parent = {
        "schema_version": FINANCIAL_OBJECT_SCHEMA_VERSION,
        "object_type": "source_document_parent",
        "document_id": parent_id,
        "ticker": ticker,
        "company": ticker,
        "source_type": "MARKET_SNAPSHOT",
        "source_tier": "market_snapshot",
        "publication_date": as_of_date,
        "period_end": as_of_date,
        "fiscal_year": int(as_of_date[:4]),
        "accession_number": None,
        "source_url": None,
        "capture_ref": source_ref,
        "capture_sha256": source_sha256,
        "source_text_digest": content_digest(text),
        "source_text_characters": len(text),
        "section_count": 1,
        "child_count": 1,
        "parse_method": "market_snapshot_projection",
        "lineage_state": "immutable_local_snapshot_bound",
    }
    return parent, child


def attach_legacy_aliases(
    alias_records: Iterable[Mapping[str, Any]],
    children: Iterable[dict[str, Any]],
    *,
    minimum_coverage: float = 0.72,
    maximum_targets: int = 3,
) -> list[dict[str, Any]]:
    """Bind retired chunk IDs to current semantic children without retrieving them.

    The old deterministic segments may cross more than one semantic child, so a
    bounded greedy union is used.  This crosswalk is evaluation/lineage data;
    the retired segment itself never re-enters the candidate corpus.
    """

    child_rows = list(children)
    results: list[dict[str, Any]] = []
    for alias in alias_records:
        alias_id = str(alias.get("evidence_id") or "").strip()
        ticker = str(alias.get("ticker") or "").strip().upper()
        source_url = str(alias.get("source_url") or "").strip()
        alias_text = str(alias.get("text") or "").strip()
        old_tokens = Counter(_alias_tokens(alias_text))
        eligible = [
            row
            for row in child_rows
            if str(row.get("ticker") or "").strip().upper() == ticker
            and str(row.get("source_url") or "").strip() == source_url
            and str(row.get("evidence_id") or "").startswith("CURRENT_DOC::")
        ]
        selected: list[dict[str, Any]] = []
        covered: Counter[str] = Counter()
        total = sum(old_tokens.values())
        while eligible and len(selected) < maximum_targets and total:
            before = sum((old_tokens & covered).values())
            best: tuple[int, dict[str, Any], Counter[str]] | None = None
            for row in eligible:
                combined = covered | Counter(_alias_tokens(str(row.get("text") or "")))
                gain = sum((old_tokens & combined).values()) - before
                if best is None or gain > best[0] or (
                    gain == best[0]
                    and str(row.get("evidence_id") or "")
                    < str(best[1].get("evidence_id") or "")
                ):
                    best = (gain, row, combined)
            if best is None or best[0] <= 0:
                break
            _, row, covered = best
            selected.append(row)
            eligible.remove(row)
            if sum((old_tokens & covered).values()) / total >= minimum_coverage:
                break
        coverage = (
            sum((old_tokens & covered).values()) / total if total else 0.0
        )
        status = "alias_mapped" if coverage >= minimum_coverage else "alias_unmapped"
        if status == "alias_mapped":
            for row in selected:
                metadata = row.setdefault("metadata", {})
                aliases = list(metadata.get("legacy_source_record_ids") or ())
                if alias_id not in aliases:
                    aliases.append(alias_id)
                    aliases.sort()
                metadata["legacy_source_record_ids"] = aliases
                metadata["legacy_alias_crosswalk_method"] = (
                    "same_source_url_bounded_token_multiset_coverage"
                )
        results.append(
            {
                "legacy_source_record_id": alias_id,
                "ticker": ticker,
                "source_url": source_url,
                "status": status,
                "coverage": round(coverage, 6),
                "current_source_record_ids": [
                    str(row.get("evidence_id") or "") for row in selected
                ]
                if status == "alias_mapped"
                else [],
            }
        )
    return results


def summarize_object_store(
    *,
    parents: Iterable[Mapping[str, Any]],
    children: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    parent_rows = list(parents)
    child_rows = list(children)
    by_ticker = Counter(str(row.get("ticker") or "") for row in child_rows)
    by_source_type = Counter(
        str(row.get("source_type") or "") for row in child_rows
    )
    current_capture_children = sum(
        bool((row.get("metadata") or {}).get("source_capture_ref"))
        and (row.get("metadata") or {}).get("source_object_origin")
        != "legacy_semantic_child_reused"
        for row in child_rows
    )
    tables = [
        row
        for row in child_rows
        if "[TABLE_START" in str(row.get("text") or "")
        or "[TABLE_END]" in str(row.get("text") or "")
    ]
    valuation_missing = [
        str(row.get("ticker") or "")
        for row in child_rows
        if row.get("source_type") == "MARKET_SNAPSHOT"
        and (row.get("metadata") or {}).get("market_snapshot_is_not_valuation")
    ]
    oversized_non_table = [
        str(row.get("evidence_id") or "")
        for row in child_rows
        if not (row.get("metadata") or {}).get("contains_table")
        and len(str(row.get("text") or "")) > MAX_NON_TABLE_CHILD_CHARACTERS
    ]
    oversized_table = [
        str(row.get("evidence_id") or "")
        for row in child_rows
        if (row.get("metadata") or {}).get("contains_table")
        and len(str(row.get("text") or "")) > MAX_TABLE_CHILD_CHARACTERS
    ]
    return {
        "document_parents": len(parent_rows),
        "retrieval_children": len(child_rows),
        "children_from_immutable_current_capture": current_capture_children,
        "children_by_ticker": dict(sorted(by_ticker.items())),
        "children_by_source_type": dict(sorted(by_source_type.items())),
        "table_children": len(tables),
        "unbalanced_table_children": sum(
            not _contains_balanced_table(str(row.get("text") or ""))
            for row in tables
        ),
        "max_retrieval_child_characters": max(
            (len(str(row.get("text") or "")) for row in child_rows),
            default=0,
        ),
        "oversized_non_table_children": oversized_non_table,
        "oversized_table_children": oversized_table,
        "market_snapshots_missing_valuation_fields": sorted(set(valuation_missing)),
    }


def _contains_balanced_table(text: str) -> bool:
    starts = text.count("[TABLE_START")
    ends = text.count("[TABLE_END]")
    return starts == ends and starts > 0


def _require_balanced_tables(children: Iterable[Mapping[str, Any]]) -> None:
    for row in children:
        text = str(row.get("text") or "")
        if ("[TABLE_START" in text or "[TABLE_END]" in text) and not _contains_balanced_table(text):
            raise FinancialObjectError(
                f"financial_object_table_boundary_invalid:{row.get('evidence_id')}"
            )


def _identifier(value: object) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip("_")
    return normalized or "UNKNOWN"


def _alias_tokens(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:[.$%-][a-z0-9]+)*", value.casefold())


def _valid_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _int_or_none(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


__all__ = [
    "FINANCIAL_OBJECT_SCHEMA_VERSION",
    "FinancialObjectError",
    "MAX_NON_TABLE_CHILD_CHARACTERS",
    "MAX_TABLE_CHILD_CHARACTERS",
    "SOURCE_MANIFEST_SCHEMA_VERSION",
    "attach_legacy_aliases",
    "compile_parsed_sec_capture",
    "compile_raw_sec_html_capture",
    "content_digest",
    "document_parent_id",
    "normalize_legacy_candidate",
    "project_market_snapshot",
    "sha256_file",
    "summarize_object_store",
    "validate_source_object_manifest",
]
