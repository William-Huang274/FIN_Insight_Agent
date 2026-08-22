from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Mapping, Sequence

from .object_view_compiler_v2 import compile_record_object_views
from .query_plan import canonical_digest
from .route_compiler import QueryObjectFactRoutePolicy


REVIEWED_PUBLIC_COMPILATION_SCHEMA_VERSION = (
    "fin_ia_reviewed_public_source_object_compilation_v1_0"
)


class ReviewedPublicObjectCompilationError(ValueError):
    """A reviewed public source cannot be represented as a candidate object."""


@dataclass(frozen=True)
class ReviewedPublicObjectCompilation:
    source_records: tuple[Mapping[str, Any], ...]
    objects: tuple[Mapping[str, Any], ...]
    diagnostics: tuple[Mapping[str, Any], ...]
    summary: Mapping[str, Any]

    def as_dict(self, *, include_objects: bool = False) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schema_version": REVIEWED_PUBLIC_COMPILATION_SCHEMA_VERSION,
            "summary": dict(self.summary),
            "diagnostics": [dict(row) for row in self.diagnostics],
        }
        if include_objects:
            value["source_records"] = [dict(row) for row in self.source_records]
        if include_objects:
            value["objects"] = [dict(row) for row in self.objects]
        return value


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReviewedPublicObjectCompilationError(code)


def _material_ref(value: Mapping[str, Any]) -> str:
    return str(value.get("material_ref") or "").strip()


def _source_record_id(value: Mapping[str, Any]) -> str:
    return str(value.get("source_record_id") or "").strip()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _slice_record_id(source_page_record_id: str, source_content_digest: str) -> str:
    return (
        source_page_record_id
        + "::SLICE::"
        + source_content_digest[:20].upper()
    )


def _public_material_record(
    material: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_page_record_id = _source_record_id(material)
    material_ref = _material_ref(material)
    source_text = str(material.get("source_text") or "").strip()
    owner = str(material.get("evidence_owner_ticker") or "").strip().upper()
    speaker = str(material.get("speaker_entity") or "").strip()
    source_type = str(material.get("source_type") or "").strip().upper()
    source_tier = str(material.get("source_tier") or "").strip()
    publication_date = str(material.get("publication_date") or "").strip()
    source_text_digest = str(material.get("source_text_digest") or "").strip()
    _require(
        source_page_record_id.startswith("PUBLIC::"),
        "public_source_record_id_invalid",
    )
    _require(material_ref, "public_source_material_ref_missing")
    _require(source_type == "PUBLIC_WEB", "public_source_type_invalid")
    _require(owner and speaker and source_tier, "public_source_identity_missing")
    _require(publication_date, "public_source_publication_date_missing")
    _require(source_text, "public_source_text_missing")
    _require(
        source_text_digest == _text_sha256(source_text),
        "public_source_text_digest_mismatch",
    )

    source_record_id = _slice_record_id(
        source_page_record_id, source_text_digest
    )
    parent_document_id = "PUBLIC_DOC::" + canonical_digest(
        {
            "source_page_record_id": source_page_record_id,
            "source_url": str(material.get("source_url") or ""),
        }
    )[:24]
    section = "Reviewed public source"
    subsection = speaker
    parent = {
        "document_id": parent_document_id,
        "ticker": owner,
        "company": speaker,
        "source_type": source_type,
        "source_tier": source_tier,
        "publication_date": publication_date,
        "period_end": str(material.get("period_end") or ""),
        "fiscal_year": material.get("fiscal_year"),
        "section": section,
        "subsection": subsection,
        "source_url": str(material.get("source_url") or ""),
        "source_content_digest": source_text_digest,
        "raw_capture_sha256": str(material.get("raw_capture_sha256") or ""),
        "license_scope": str(material.get("license_scope") or ""),
        "redistributable": material.get("redistributable") is True,
    }
    record = {
        "evidence_id": source_record_id,
        "ticker": owner,
        "company": speaker,
        "source_type": source_type,
        "source_tier": source_tier,
        "publication_date": publication_date,
        "period_end": str(material.get("period_end") or ""),
        "fiscal_year": material.get("fiscal_year"),
        "section": section,
        "subsection": subsection,
        "source_url": str(material.get("source_url") or ""),
        "license_scope": str(material.get("license_scope") or ""),
        "redistributable": material.get("redistributable") is True,
        "text": source_text,
        "metadata": {
            "parent_document_id": parent_document_id,
            "source_page_record_id": source_page_record_id,
            "material_ref": material_ref,
            "source_url": str(material.get("source_url") or ""),
            "source_content_digest": source_text_digest,
            "raw_capture_sha256": str(material.get("raw_capture_sha256") or ""),
            "license_scope": str(material.get("license_scope") or ""),
            "redistributable": material.get("redistributable") is True,
        },
    }
    return record, parent


def _public_page_records(
    slice_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build one lineage parent for every captured page.

    A page identifier and a reviewed content-slice identifier are different
    identities.  Keeping both prevents two excerpts from the same URL from
    masquerading as one canonical source record while still allowing an exact
    join back to the page-bound Evidence Pack.
    """

    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in slice_records:
        metadata = row.get("metadata") or {}
        page_id = str(metadata.get("source_page_record_id") or "")
        _require(page_id, "public_source_page_record_id_missing")
        grouped.setdefault(page_id, []).append(row)

    output: list[dict[str, Any]] = []
    for page_id in sorted(grouped):
        rows = sorted(
            grouped[page_id],
            key=lambda row: str((row.get("metadata") or {}).get("material_ref") or ""),
        )
        first = rows[0]
        identity_fields = (
            "ticker",
            "company",
            "source_type",
            "source_tier",
            "publication_date",
            "period_end",
            "fiscal_year",
            "source_url",
        )
        for row in rows[1:]:
            _require(
                all(row.get(field) == first.get(field) for field in identity_fields),
                "public_source_page_identity_drift",
            )
        text = "\n\n".join(str(row.get("text") or "") for row in rows)
        slice_ids = [str(row["evidence_id"]) for row in rows]
        slice_digests = [
            str((row.get("metadata") or {}).get("source_content_digest") or "")
            for row in rows
        ]
        output.append(
            {
                "evidence_id": page_id,
                "ticker": first["ticker"],
                "company": first["company"],
                "source_type": first["source_type"],
                "source_tier": first["source_tier"],
                "publication_date": first["publication_date"],
                "period_end": first.get("period_end"),
                "fiscal_year": first.get("fiscal_year"),
                "section": "Reviewed public source page lineage",
                "subsection": first["company"],
                "source_url": first.get("source_url"),
                "text": text,
                "license_scope": str(
                    (first.get("metadata") or {}).get("license_scope") or ""
                ),
                "redistributable": (
                    (first.get("metadata") or {}).get("redistributable") is True
                ),
                "metadata": {
                    "object_level": "source_page_lineage_parent",
                    "parent_document_id": str(
                        (first.get("metadata") or {}).get("parent_document_id") or ""
                    ),
                    "source_content_slice_ids": slice_ids,
                    "source_content_slice_digests": slice_digests,
                    "source_content_digest": _text_sha256(text),
                    "raw_capture_sha256": str(
                        (first.get("metadata") or {}).get("raw_capture_sha256") or ""
                    ),
                    "candidate_is_not_evidence": True,
                },
            }
        )
    return output


def compile_reviewed_public_source_objects(
    *,
    evidence_pack: Mapping[str, Any],
    route_policy: QueryObjectFactRoutePolicy,
) -> ReviewedPublicObjectCompilation:
    """Compile capture-bound reviewed public sources into label-free candidates.

    The reviewed Pack decides which immutable source materials are eligible to
    enter the current object/index surface.  Its relevance labels, proposition
    bindings and acceptance outcomes are deliberately *not* copied into the
    candidate objects.  Authority is only recovered later by exact lineage join
    against the immutable reviewed Pack.
    """

    case_key = str(evidence_pack.get("case_key") or "").strip().upper()
    _require(case_key, "reviewed_public_pack_case_missing")
    raw_items = evidence_pack.get("evidence_items")
    raw_materials = evidence_pack.get("source_materials")
    _require(isinstance(raw_items, Sequence), "reviewed_public_items_invalid")
    _require(isinstance(raw_materials, Sequence), "reviewed_public_materials_invalid")

    eligible_material_refs = {
        str(item.get("source_material_ref") or "")
        for item in raw_items
        if isinstance(item, Mapping)
        and item.get("writer_citable") is True
        and str(item.get("source_record_id") or "").startswith("PUBLIC::")
    }
    _require(eligible_material_refs, "reviewed_public_material_refs_empty")
    materials_by_ref: dict[str, Mapping[str, Any]] = {}
    for raw_material in raw_materials:
        _require(isinstance(raw_material, Mapping), "reviewed_public_material_invalid")
        material = raw_material
        material_ref = _material_ref(material)
        if material_ref not in eligible_material_refs:
            continue
        _require(material_ref not in materials_by_ref, "reviewed_public_material_duplicate")
        materials_by_ref[material_ref] = material
    _require(
        set(materials_by_ref) == eligible_material_refs,
        "reviewed_public_material_binding_incomplete",
    )

    output: list[dict[str, Any]] = []
    slice_records: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    source_record_ids: set[str] = set()
    source_content_identities: set[tuple[str, str]] = set()
    for material_ref in sorted(materials_by_ref):
        material = materials_by_ref[material_ref]
        record, parent = _public_material_record(material)
        source_record_id = str(record["evidence_id"])
        source_page_record_id = str(
            (record.get("metadata") or {})["source_page_record_id"]
        )
        source_content_digest = str(material["source_text_digest"])
        source_content_identity = (source_record_id, source_content_digest)
        _require(
            source_content_identity not in source_content_identities,
            "reviewed_public_source_content_identity_duplicate",
        )
        source_content_identities.add(source_content_identity)
        source_record_ids.add(source_page_record_id)
        slice_records.append(record)
        compiled, row_diagnostics = compile_record_object_views(
            record=record,
            parent=parent,
            policy=route_policy,
        )
        _require(compiled, "reviewed_public_source_compilation_empty")
        for raw_object in compiled:
            row = dict(raw_object)
            base = dict(row["base_object_view"])
            # Capture and licensing metadata are source lineage, not relevance
            # labels.  They remain private and never grant Evidence authority.
            base["source_lineage"] = {
                "source_page_record_id": source_page_record_id,
                "source_slice_record_id": source_record_id,
                "material_ref": material_ref,
                "source_content_digest": source_content_digest,
                "source_url": str(material.get("source_url") or ""),
                "raw_capture_sha256": str(material.get("raw_capture_sha256") or ""),
                "license_scope": str(material.get("license_scope") or ""),
                "redistributable": material.get("redistributable") is True,
            }
            row["base_object_view"] = base
            row["lineage_source_record_ids"] = [
                source_page_record_id,
                source_record_id,
            ]
            row["duplicate_lineage_count"] = 0
            output.append(row)
        diagnostics.extend(
            {"material_ref": material_ref, **dict(row)}
            for row in row_diagnostics
        )

    object_ids = [str(row.get("compiled_object_id") or "") for row in output]
    _require(
        all(object_ids) and len(object_ids) == len(set(object_ids)),
        "reviewed_public_compiled_object_identity_invalid",
    )
    claim_source_ids = {
        str(
            (row["base_object_view"].get("source_lineage") or {}).get(
                "source_page_record_id"
            )
            or ""
        )
        for row in output
        if row.get("object_kind") == "claim"
    }
    _require(
        claim_source_ids == source_record_ids,
        "reviewed_public_claim_source_coverage_incomplete",
    )

    kind_counts: dict[str, int] = {}
    for row in output:
        kind = str(row.get("object_kind") or "")
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    page_records = _public_page_records(slice_records)
    canonical_records = [*page_records, *slice_records]
    canonical_record_ids = [str(row.get("evidence_id") or "") for row in canonical_records]
    _require(
        all(canonical_record_ids)
        and len(canonical_record_ids) == len(set(canonical_record_ids)),
        "reviewed_public_canonical_source_record_identity_invalid",
    )
    summary = {
        "case_key": case_key,
        "eligible_reviewed_item_count": sum(
            1
            for item in raw_items
            if isinstance(item, Mapping)
            and item.get("writer_citable") is True
            and str(item.get("source_record_id") or "").startswith("PUBLIC::")
        ),
        "unique_public_source_count": len(source_record_ids),
        "public_source_content_slice_count": len(source_content_identities),
        "compiled_object_count": len(output),
        "object_kind_counts": dict(sorted(kind_counts.items())),
        "diagnostic_count": len(diagnostics),
        "source_record_ids": sorted(source_record_ids),
        "source_page_record_ids": sorted(source_record_ids),
        "source_slice_record_ids": sorted(
            str(row["evidence_id"]) for row in slice_records
        ),
        "canonical_source_record_count": len(canonical_records),
        "candidate_not_evidence": True,
        "numeric_authority": False,
        "relevance_labels_copied_into_candidates": False,
        "network_calls": 0,
        "model_calls": 0,
    }
    return ReviewedPublicObjectCompilation(
        source_records=tuple(canonical_records),
        objects=tuple(output),
        diagnostics=tuple(diagnostics),
        summary=summary,
    )


__all__ = [
    "REVIEWED_PUBLIC_COMPILATION_SCHEMA_VERSION",
    "ReviewedPublicObjectCompilation",
    "ReviewedPublicObjectCompilationError",
    "compile_reviewed_public_source_objects",
]
