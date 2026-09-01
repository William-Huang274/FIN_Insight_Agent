from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC)]
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from ingestion.official_source_capture import (  # noqa: E402
    CAPTURE_PLAN_GENERIC_SCHEMA_VERSION,
    TransportFetcher,
    capture_plan,
    materialize_response_body_capture,
)
from scripts.data_retrieval.build_dell_reference_knowledge_package import (  # noqa: E402
    _parse as parse_with_qualified_knowledge_stack,
)
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    REVIEWED_EVIDENCE_PACK_CONTRACT,
    REVIEWED_EVIDENCE_PACK_SCHEMA,
    canonical_digest,
    validate_reviewed_evidence_pack,
)
from sec_agent.research_foundation.contracts import (  # noqa: E402
    bind_dell_research_method,
    load_dell_reference_vertical_foundation,
)
from sec_agent.research_foundation.data_ports import (  # noqa: E402
    CurrentReviewedEvidenceReader,
)


REVIEW_SCHEMA = "fin_ia_dell_fy27_q2_reviewed_evidence_overlay_review_v1_0"
PACK_STATUS = "case_only_reviewed_sec_exhibit_evidence_overlay"
PROJECTION_SCHEMA = "fin_ia_dell_case_only_reviewed_evidence_projection_v1_0"
RECEIPT_SCHEMA = "fin_ia_dell_fy27_q2_reviewed_evidence_overlay_receipt_v1_0"
NUMERIC_USE_BOUNDARY = (
    "Only values visible verbatim in this reviewed SEC Exhibit 99.1 excerpt may "
    "be quoted as issuer-disclosed textual evidence. This item is not an S2 "
    "NumericFact; current-Q2 derived arithmetic, normalization, ratios, deltas, "
    "or formula outputs remain blocked until a typed structured source is admitted."
)
_SEC_EXHIBIT_URL = re.compile(
    r"^https://www\.sec\.gov/Archives/edgar/data/1571996/"
    r"(?P<accession>[0-9]{18})/(?P<document>[A-Za-z0-9_.-]+)$"
)
_ITEM_FIELDS = {
    "item_id",
    "target_id",
    "topic",
    "reviewed_quote",
    "slot_id",
    "facet_ids",
    "qualification_id",
    "business_meaning_zh",
    "claim_boundary_zh",
}


def _canonical_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical_bytes(dict(value)))


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("q2_overlay_review_input_not_object")
    return value


def _validate_review_input(value: Mapping[str, Any]) -> dict[str, Any]:
    review = json.loads(json.dumps(dict(value), ensure_ascii=False))
    expected_top = {
        "schema_version",
        "status",
        "reviewed_at",
        "reviewer_id",
        "case_key",
        "research_as_of",
        "source",
        "items",
        "residual_gap",
        "authority",
    }
    if set(review) != expected_top:
        raise ValueError("q2_overlay_review_fields_invalid")
    source = review.get("source")
    items = review.get("items")
    authority = review.get("authority")
    residual_gap = review.get("residual_gap")
    if not (
        review.get("schema_version") == REVIEW_SCHEMA
        and review.get("status") == "case_only_author_review_complete"
        and review.get("case_key") == "DELL"
        and str(review.get("reviewer_id") or "").strip()
        and isinstance(source, dict)
        and isinstance(items, list)
        and 5 <= len(items) <= 10
        and isinstance(authority, dict)
        and isinstance(residual_gap, dict)
    ):
        raise ValueError("q2_overlay_review_shape_invalid")
    reviewed_at = datetime.fromisoformat(str(review["reviewed_at"]))
    research_as_of = datetime.fromisoformat(str(review["research_as_of"]))
    publication_date = datetime.fromisoformat(str(source.get("publication_date")))
    if not publication_date.date() <= research_as_of.date() <= reviewed_at.date():
        raise ValueError("q2_overlay_review_temporal_boundary_invalid")

    expected_source = {
        "accession_number",
        "exhibit_document",
        "publication_date",
        "reporting_period_end",
        "source_url",
        "source_type",
        "source_tier",
        "expected_raw_body_sha256",
        "expected_raw_body_bytes",
        "required_document_title",
    }
    match = _SEC_EXHIBIT_URL.fullmatch(str(source.get("source_url") or ""))
    if not (
        set(source) == expected_source
        and match is not None
        and match.group("accession")
        == str(source.get("accession_number") or "").replace("-", "")
        and match.group("document") == source.get("exhibit_document")
        and source.get("source_type") == "8-K"
        and source.get("source_tier") == "company_authored_unaudited_sec_filing"
        and re.fullmatch(r"[0-9a-f]{64}", str(source.get("expected_raw_body_sha256") or ""))
        and int(source.get("expected_raw_body_bytes") or 0) > 0
        and str(source.get("required_document_title") or "").strip()
    ):
        raise ValueError("q2_overlay_source_identity_invalid")
    if urlsplit(str(source["source_url"])).hostname != "www.sec.gov":
        raise ValueError("q2_overlay_source_host_invalid")

    expected_authority = {
        "case_only_reviewed_evidence",
        "writer_citable_within_case",
        "source_visible_exact_values_quoteable",
        "automatic_evidence_promotion",
        "qualified_human_review",
        "s2_numeric_fact_authority",
        "derived_current_q2_arithmetic_authorized",
        "product_pack_mutation_authorized",
        "method_or_planner_answer_injection",
    }
    if not (
        set(authority) == expected_authority
        and authority.get("case_only_reviewed_evidence") is True
        and authority.get("writer_citable_within_case") is True
        and authority.get("source_visible_exact_values_quoteable") is True
        and authority.get("automatic_evidence_promotion") is False
        and authority.get("qualified_human_review") is False
        and authority.get("s2_numeric_fact_authority") is False
        and authority.get("derived_current_q2_arithmetic_authorized") is False
        and authority.get("product_pack_mutation_authorized") is False
        and authority.get("method_or_planner_answer_injection") is False
    ):
        raise ValueError("q2_overlay_authority_boundary_invalid")
    if not (
        set(residual_gap)
        == {"gap_id", "gap_code", "slot_id", "detail_zh"}
        and all(str(residual_gap.get(key) or "").strip() for key in residual_gap)
    ):
        raise ValueError("q2_overlay_residual_gap_invalid")

    item_ids: list[str] = []
    target_ids: list[str] = []
    quotes: list[str] = []
    for item in items:
        if not isinstance(item, dict) or set(item) != _ITEM_FIELDS:
            raise ValueError("q2_overlay_item_fields_invalid")
        quote = _collapse_whitespace(str(item.get("reviewed_quote") or ""))
        facets = item.get("facet_ids")
        if not (
            re.fullmatch(r"[A-Z0-9_]{3,80}", str(item.get("item_id") or ""))
            and str(item.get("target_id") or "").strip()
            and str(item.get("topic") or "").strip()
            and 50 <= len(quote) <= 1_200
            and str(item.get("slot_id") or "").strip()
            and isinstance(facets, list)
            and facets
            and len(facets) == len(set(str(value) for value in facets))
            and all(str(value).strip() for value in facets)
            and str(item.get("qualification_id") or "").strip()
            and str(item.get("business_meaning_zh") or "").strip()
            and str(item.get("claim_boundary_zh") or "").strip()
        ):
            raise ValueError("q2_overlay_item_shape_invalid")
        item["reviewed_quote"] = quote
        item_ids.append(str(item["item_id"]))
        target_ids.append(str(item["target_id"]))
        quotes.append(quote)
    if (
        len(item_ids) != len(set(item_ids))
        or len(target_ids) != len(set(target_ids))
        or len(quotes) != len(set(quotes))
    ):
        raise ValueError("q2_overlay_item_identity_duplicate")
    return review


def _capture_source(review: Mapping[str, Any]) -> dict[str, Any]:
    source = dict(review["source"])
    return {
        "schema_version": CAPTURE_PLAN_GENERIC_SCHEMA_VERSION,
        "status": "official_source_capture_plan",
        "policy": {
            "capture_before_parse": True,
            "https_only": True,
            "credentials_forbidden": True,
        },
        "sources": [
            {
                "case_key": "DELL",
                "route_id": "dell_fy27_q2_sec_exhibit_991",
                "url": source["source_url"],
                "allowed_hosts": ["www.sec.gov"],
                "expected_content_types": ["text/html"],
                "byte_ceiling": 2_000_000,
                "timeout_seconds": 60,
                "transport": "requests",
                "max_transport_retries": 0,
            }
        ],
    }


def _load_bound_response_capture(
    capture_result: Mapping[str, Any], *, attempt_root: Path
) -> dict[str, Any]:
    sources = capture_result.get("sources")
    if not (
        capture_result.get("status") == "official_sources_captured"
        and isinstance(sources, list)
        and len(sources) == 1
        and sources[0].get("status") == "captured"
    ):
        raise ValueError("q2_overlay_source_capture_failed")
    binding = dict(sources[0].get("response_capture") or {})
    path = Path(str(binding.get("object_ref") or "")).resolve()
    try:
        path.relative_to(attempt_root.resolve())
    except ValueError as exc:
        raise ValueError("q2_overlay_capture_object_escape") from exc
    if not (
        path.is_file()
        and _sha256_file(path) == str(binding.get("sha256") or "")
        and path.stat().st_size == int(binding.get("bytes") or -1)
    ):
        raise ValueError("q2_overlay_capture_object_binding_invalid")
    value = _load_json(path)
    return value


def _locate_reviewed_quotes(
    *, review: Mapping[str, Any], searchable_text: str, parsed_sha256: str, raw_sha256: str
) -> list[dict[str, Any]]:
    located: list[dict[str, Any]] = []
    for item in review["items"]:
        quote = str(item["reviewed_quote"])
        positions = [match.start() for match in re.finditer(re.escape(quote), searchable_text)]
        if len(positions) != 1:
            raise ValueError(
                f"q2_overlay_quote_not_unique:{item['item_id']}:{len(positions)}"
            )
        start = positions[0]
        located.append(
            {
                **dict(item),
                "source_locator": {
                    "mode": "normalized_parsed_text_char_span",
                    "char_start": start,
                    "char_end": start + len(quote),
                    "quote_sha256": _sha256_bytes(quote.encode("utf-8")),
                    "parsed_search_text_sha256": parsed_sha256,
                    "raw_body_sha256": raw_sha256,
                },
            }
        )
    return located


def _compile_pack_and_projection(
    *,
    review: Mapping[str, Any],
    located_items: list[dict[str, Any]],
    raw_body_sha256: str,
    parsed_search_text_sha256: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = dict(review["source"])
    accession = str(source["accession_number"])
    document = str(source["exhibit_document"])
    materials: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    projected: list[dict[str, Any]] = []
    for item in located_items:
        quote = str(item["reviewed_quote"])
        quote_digest = _sha256_bytes(quote.encode("utf-8"))
        record_id = (
            f"SEC::DELL::{accession}::{document.upper()}::PROP::{item['item_id']}"
        )
        material_ref = "source_material_" + canonical_digest(
            {"source_record_id": record_id, "quote_sha256": quote_digest}
        )[:24]
        material = {
            "material_ref": material_ref,
            "source_record_id": record_id,
            "evidence_owner_ticker": "DELL",
            "source_tier": source["source_tier"],
            "source_type": source["source_type"],
            "source_url": source["source_url"],
            "publication_date": source["publication_date"],
            "period_end": source["reporting_period_end"],
            "license_scope": "public_sec_filing",
            "redistributable": False,
            "source_text": quote,
            "source_text_digest": quote_digest,
            "source_locator": dict(item["source_locator"]),
            "source_identity": {
                "accession_number": accession,
                "exhibit_document": document,
                "raw_body_sha256": raw_body_sha256,
                "parsed_search_text_sha256": parsed_search_text_sha256,
            },
        }
        item_body = {
            "case_key": "DELL",
            "target_id": item["target_id"],
            "source_record_id": record_id,
            "object_type": "claim",
            "disposition": "accepted_direct_source_evidence",
            "evidence_role": "issuer_direct_source",
            "publication_date": source["publication_date"],
            "source_reporting_period_end": source["reporting_period_end"],
            "research_as_of": str(review["research_as_of"])[:10],
            "relationship_directions": ["subject_self_disclosure"],
            "slot_bindings": [
                {
                    "slot_id": item["slot_id"],
                    "facet_ids": list(item["facet_ids"]),
                    "qualification_id": item["qualification_id"],
                    "business_meaning_zh": item["business_meaning_zh"],
                    "claim_boundary_zh": item["claim_boundary_zh"],
                }
            ],
            "numeric_use_boundary": NUMERIC_USE_BOUNDARY,
            "causal_attribution_authorized": False,
            "writer_citable": True,
            "claim_use": "issuer_direct_source_visible_statement",
            "proposition_id": str(item["item_id"]),
            "target_company_exact_numeric_authority": (
                "source_visible_quote_only_not_s2_numeric_fact"
            ),
            "source_material_ref": material_ref,
            "source_content_digest": quote_digest,
        }
        evidence_item = {
            **item_body,
            "evidence_item_digest": canonical_digest(item_body),
        }
        projected_source = {
            key: material[key]
            for key in (
                "material_ref",
                "source_record_id",
                "evidence_owner_ticker",
                "source_tier",
                "source_type",
                "source_url",
                "publication_date",
                "period_end",
                "license_scope",
                "redistributable",
                "source_text_digest",
                "source_locator",
                "source_identity",
            )
        }
        projected_source.update(
            {
                "reviewed_source_excerpt": quote,
                "excerpt_truncated": False,
                "excerpt_use_boundary": (
                    "Case-only reviewed SEC evidence; cite the official URL and "
                    "preserve the S2 NumericFact boundary."
                ),
            }
        )
        projected.append({**evidence_item, "source": projected_source})
        materials.append(material)
        evidence.append(evidence_item)

    gap = dict(review["residual_gap"])
    pack_body = {
        "schema_version": REVIEWED_EVIDENCE_PACK_SCHEMA,
        "contract_ref": REVIEWED_EVIDENCE_PACK_CONTRACT,
        "status": PACK_STATUS,
        "case_key": "DELL",
        "research_as_of": str(review["research_as_of"])[:10],
        "source_materials": materials,
        "evidence_items": evidence,
        "rejected_items": [],
        "residual_gaps": [gap],
        "observed_counts": {
            "accepted_evidence_items": len(evidence),
            "direct_evidence_items": len(evidence),
            "bounded_context_items": 0,
            "rejected_items": 0,
            "residual_gaps": 1,
            "source_materials": len(materials),
        },
        "content_gate_basis": (
            "explicit_case_only_author_review_of_exact_SEC_exhibit_quote_spans"
        ),
        "consumer_contract": {
            "writer_may_quote_source_visible_exact_values": True,
            "writer_must_cite_official_source_url": True,
            "current_q2_s2_numeric_fact_authority": False,
            "current_q2_derived_arithmetic_authority": False,
        },
        "known_boundary": (
            "This isolated overlay is writer-citable only for the DELL reference "
            "case. It does not mutate the current reviewed product Pack, does not "
            "grant qualified-human or product admission, does not create current-Q2 "
            "S2 NumericFacts, and does not authorize derived current-Q2 arithmetic."
        ),
    }
    pack = {**pack_body, "pack_payload_digest": canonical_digest(pack_body)}
    validate_reviewed_evidence_pack(pack)
    projection_body = {
        "schema_version": PROJECTION_SCHEMA,
        "status": "case_only_reviewed_evidence_projection_ready",
        "case_key": "DELL",
        "pack_payload_digest": pack["pack_payload_digest"],
        "evidence_items": projected,
        "authority": {
            "reviewed_evidence": True,
            "automatic_evidence_promotion": False,
            "qualified_human_review": False,
            "s2_numeric_fact_authority": False,
            "derived_current_q2_arithmetic_authorized": False,
            "product_pack_mutation_authorized": False,
        },
    }
    projection = {
        **projection_body,
        "projection_digest": canonical_digest(projection_body),
    }
    return pack, projection


def _validate_mcp_reader_projection(
    projection: Mapping[str, Any], *, review: Mapping[str, Any]
) -> dict[str, Any]:
    branch_id = "Q1_ISSUER_TRUTH"
    research_as_of = datetime.fromisoformat(str(review["research_as_of"]))
    scope = bind_dell_research_method(
        load_dell_reference_vertical_foundation(),
        (branch_id,),
        research_as_of=research_as_of,
        data_snapshot_id="DELL-FY27-Q2-SEC-EVIDENCE-OVERLAY",
        execution_attempt_id="DELL-FY27-Q2-EVIDENCE-OVERLAY-VALIDATION",
    ).run_scope
    reader = CurrentReviewedEvidenceReader(
        case_reader=lambda case_key: (
            projection if case_key == "DELL" else {"evidence_items": []}
        )
    )
    evidence_ids = tuple(
        "EV::"
        + canonical_digest(
            {
                "case_key": "DELL",
                "target_id": item["target_id"],
                "evidence_item_digest": item["evidence_item_digest"],
            }
        )[:16].upper()
        for item in projection["evidence_items"]
    )
    read = reader(
        evidence_ids=evidence_ids,
        branch_id=branch_id,
        run_scope=scope,
    )
    search = reader.search(
        query="Dell fiscal 2027 second quarter AI server guidance",
        branch_id=branch_id,
        limit=min(8, len(evidence_ids)),
        run_scope=scope,
    )
    if (
        len(read.evidence) != len(evidence_ids)
        or read.missing_evidence_ids
        or not search.hits
    ):
        raise ValueError("q2_overlay_mcp_reader_validation_failed")
    return {
        "status": "PASS",
        "branch_id": branch_id,
        "evidence_id_count": len(evidence_ids),
        "read_evidence_count": len(read.evidence),
        "missing_evidence_id_count": len(read.missing_evidence_ids),
        "search_hit_count": len(search.hits),
        "read_digest": read.read_digest,
        "search_digest": search.search_digest,
    }


def compose_case_projection(
    base_case_projection: Mapping[str, Any],
    overlay_case_projection: Mapping[str, Any],
) -> dict[str, Any]:
    """Compose one read-only case view for ``CurrentReviewedEvidenceReader``.

    This is intentionally a pure projection adapter: it performs no Evidence
    admission, retrieval, model call, S2 write, or product-Pack mutation.
    """

    base = json.loads(json.dumps(dict(base_case_projection), ensure_ascii=False))
    overlay = json.loads(
        json.dumps(dict(overlay_case_projection), ensure_ascii=False)
    )
    base_digest = str(base.pop("projection_digest", ""))
    overlay_digest = str(overlay.pop("projection_digest", ""))
    if not (
        base.get("case_key") == "DELL"
        and overlay.get("case_key") == "DELL"
        and overlay.get("schema_version") == PROJECTION_SCHEMA
        and base_digest == canonical_digest(base)
        and overlay_digest == canonical_digest(overlay)
        and isinstance(base.get("evidence_items"), list)
        and isinstance(overlay.get("evidence_items"), list)
        and overlay["evidence_items"]
    ):
        raise ValueError("q2_overlay_composite_projection_input_invalid")
    merged = [*base["evidence_items"], *overlay["evidence_items"]]
    targets = [str(item.get("target_id") or "") for item in merged]
    evidence_ids = [
        "EV::"
        + canonical_digest(
            {
                "case_key": "DELL",
                "target_id": item.get("target_id"),
                "evidence_item_digest": item.get("evidence_item_digest"),
            }
        )[:16].upper()
        for item in merged
    ]
    if (
        any(not target for target in targets)
        or len(targets) != len(set(targets))
        or len(evidence_ids) != len(set(evidence_ids))
    ):
        raise ValueError("q2_overlay_composite_evidence_identity_collision")
    composite_body = {
        **base,
        "evidence_items": merged,
        "case_only_evidence_overlay": {
            "schema_version": "fin_ia_case_only_evidence_overlay_binding_v1_0",
            "base_projection_digest": base_digest,
            "overlay_projection_digest": overlay_digest,
            "base_evidence_count": len(base["evidence_items"]),
            "overlay_evidence_count": len(overlay["evidence_items"]),
            "automatic_evidence_promotion": False,
            "product_pack_mutation_authorized": False,
            "s2_numeric_fact_authority": False,
        },
    }
    return {
        **composite_body,
        "projection_digest": canonical_digest(composite_body),
    }


def materialize_overlay(
    review_input_path: Path,
    output_root: Path,
    attempt_id: str,
    *,
    transport_fetchers: Mapping[str, TransportFetcher] | None = None,
) -> dict[str, Any]:
    review = _validate_review_input(_load_json(review_input_path))
    capture_result = capture_plan(
        _capture_source(review),
        output_root=output_root,
        attempt_id=attempt_id,
        transport_fetchers=transport_fetchers,
    )
    attempt_root = output_root.resolve() / attempt_id
    response_capture = _load_bound_response_capture(
        capture_result, attempt_root=attempt_root
    )
    materialized = materialize_response_body_capture(
        response_capture,
        output_root=attempt_root / "raw_body",
    )
    raw_path = Path(str(materialized["body_path"]))
    raw_body = raw_path.read_bytes()
    source = dict(review["source"])
    if not (
        materialized["body_sha256"] == source["expected_raw_body_sha256"]
        and materialized["body_bytes"] == source["expected_raw_body_bytes"]
    ):
        raise ValueError("q2_overlay_raw_source_identity_drift")

    parsed_units = parse_with_qualified_knowledge_stack(raw_body, "html")
    parsed_text = "\n\n".join(text for _, text in parsed_units).strip()
    searchable_text = _collapse_whitespace(parsed_text)
    if str(source["required_document_title"]) not in searchable_text:
        raise ValueError("q2_overlay_document_title_missing")
    parsed_path = attempt_root / "parsed" / "dell_fy27_q2_sec_exhibit_991.txt"
    parsed_path.parent.mkdir(parents=True, exist_ok=True)
    parsed_path.write_text(parsed_text + "\n", encoding="utf-8")
    search_path = attempt_root / "parsed" / "normalized_search_text.txt"
    search_path.write_text(searchable_text + "\n", encoding="utf-8")
    parsed_search_sha256 = _sha256_bytes(searchable_text.encode("utf-8"))
    located = _locate_reviewed_quotes(
        review=review,
        searchable_text=searchable_text,
        parsed_sha256=parsed_search_sha256,
        raw_sha256=str(materialized["body_sha256"]),
    )
    pack, projection = _compile_pack_and_projection(
        review=review,
        located_items=located,
        raw_body_sha256=str(materialized["body_sha256"]),
        parsed_search_text_sha256=parsed_search_sha256,
    )
    mcp_validation = _validate_mcp_reader_projection(projection, review=review)

    review_copy = attempt_root / "review-input.json"
    _write_json(review_copy, review)
    pack_path = attempt_root / "reviewed-evidence-pack.json"
    projection_path = attempt_root / "reviewed-evidence-case-projection.json"
    _write_json(pack_path, pack)
    _write_json(projection_path, projection)
    artifacts = {}
    for label, path in (
        ("review_input", review_copy),
        ("capture_result", attempt_root / "result.json"),
        ("raw_body", raw_path),
        ("parsed_text", parsed_path),
        ("normalized_search_text", search_path),
        ("reviewed_evidence_pack", pack_path),
        ("case_projection", projection_path),
    ):
        artifacts[label] = {
            "path": path.as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
    receipt_body = {
        "schema_version": RECEIPT_SCHEMA,
        "status": "case_only_reviewed_evidence_overlay_materialized",
        "attempt_id": attempt_id,
        "case_key": "DELL",
        "reviewed_at": review["reviewed_at"],
        "research_as_of": review["research_as_of"],
        "source_identity": {
            "accession_number": source["accession_number"],
            "exhibit_document": source["exhibit_document"],
            "source_url": source["source_url"],
            "raw_body_bytes": materialized["body_bytes"],
            "raw_body_sha256": materialized["body_sha256"],
            "parsed_search_text_sha256": parsed_search_sha256,
            "inline_xbrl_ix_tag_count": len(
                re.findall(rb"<\s*ix:", raw_body, flags=re.IGNORECASE)
            ),
            "us_gaap_tag_count": len(
                re.findall(rb"us-gaap:", raw_body, flags=re.IGNORECASE)
            ),
        },
        "review": {
            "reviewer_id": review["reviewer_id"],
            "item_count": len(located),
            "all_quote_locators_unique": True,
            "all_quotes_bound_to_same_raw_and_parsed_source": True,
            "pack_validator": "PASS",
            "mcp_reviewed_evidence_reader": mcp_validation,
        },
        "authority": dict(review["authority"]),
        "numeric_use_boundary": NUMERIC_USE_BOUNDARY,
        "residual_gap": dict(review["residual_gap"]),
        "artifacts": artifacts,
        "known_boundary": (
            "This receipt proves only an immutable, case-only Reviewed Evidence "
            "overlay over the official SEC Exhibit 99.1. Source-visible exact "
            "values are citable textual evidence; the overlay is not an S2 "
            "NumericFact source, derived current-Q2 arithmetic remains blocked, "
            "and the current product Pack was not mutated."
        ),
    }
    receipt = {
        **receipt_body,
        "receipt_payload_digest": canonical_digest(receipt_body),
    }
    receipt_path = attempt_root / "receipt.json"
    _write_json(receipt_path, receipt)
    return {
        **receipt,
        "receipt_path": receipt_path.as_posix(),
        "receipt_file_sha256": _sha256_file(receipt_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize an immutable, case-only Reviewed Evidence overlay from "
            "the official Dell FY27 Q2 SEC Exhibit 99.1."
        )
    )
    parser.add_argument("--review-input", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args()
    result = materialize_overlay(
        args.review_input,
        args.output_root,
        args.attempt_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
