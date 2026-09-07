from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping, Sequence

from .dell_report_r14_common import (
    TARGET_IDS,
    canonical_digest,
    canonical_json_bytes,
    domain_rows_digest,
    require,
    require_identifier,
    with_result_digest,
)


REBUILDER_SCHEMA_VERSION = (
    "fin_ia_dell_03B_R14_input_population_independent_rebuild_v1_0"
)
REBUILDER_ID = "R14_population_independent_rebuilder_v1"
_SOURCE_SLICE_MODES = (
    "balanced_table",
    "exact_text",
    "offset_bound_text",
    "parent_context",
)
_PARENT_CONTEXT_FIELDS = (
    "ticker",
    "company",
    "source_type",
    "source_tier",
    "publication_date",
    "period_end",
    "fiscal_year",
    "section",
    "subsection",
)
_PARENT_DOCUMENT_IDENTITY_FIELDS = (
    "ticker",
    "company",
    "source_type",
    "source_url",
    "publication_date",
    "period_end",
    "fiscal_year",
    "accession_number",
    "primary_document",
    "source_capture_sha256",
    "source_text_digest",
    "local_path",
)
_PARENT_DOCUMENT_AUTHORITY_ANCHORS = frozenset(
    {
        "source_url",
        "accession_number",
        "primary_document",
        "source_capture_sha256",
        "source_text_digest",
        "local_path",
    }
)
_EMPTY_PARENT_DOCUMENT_RECEIPT_DIGEST = canonical_digest(
    {"parent_document_receipt": None}
)


def _parent_binding(row: Mapping[str, Any]) -> str:
    metadata = dict(row.get("metadata") or {})
    parent = str(metadata.get("parent_document_id") or "").strip()
    return canonical_digest({"parent_document_id": parent or None})


def _document_identity_value(row: Mapping[str, Any], field: str) -> Any:
    metadata = dict(row.get("metadata") or {})
    value = row.get(field) if field in row else metadata.get(field)
    return value.strip() if isinstance(value, str) else value


def _rebuild_parent_document_receipts(
    values: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in values:
        row = dict(raw)
        parent = str(
            (row.get("metadata") or {}).get("parent_document_id") or ""
        ).strip()
        if parent:
            grouped[parent].append(row)
    receipts: list[dict[str, Any]] = []
    by_source: dict[str, dict[str, Any]] = {}
    for parent, rows in sorted(grouped.items()):
        identity_surface: dict[str, Any] = {}
        for field in _PARENT_DOCUMENT_IDENTITY_FIELDS:
            values_for_field = [_document_identity_value(row, field) for row in rows]
            present = [
                value
                for value in values_for_field
                if value is not None and value != ""
            ]
            if present and len(present) == len(values_for_field) and all(
                value == present[0] for value in present
            ):
                identity_surface[field] = present[0]
        anchors = tuple(
            sorted(
                set(identity_surface).intersection(
                    _PARENT_DOCUMENT_AUTHORITY_ANCHORS
                )
            )
        )
        members = sorted(
            (
                {
                    "source_record_id": _raw_source_identity(row)[0],
                    "canonical_source_family_id": _raw_source_identity(row)[1],
                    "source_record_input_digest": canonical_digest(dict(row)),
                }
                for row in rows
            ),
            key=lambda row: (
                row["source_record_id"],
                row["canonical_source_family_id"],
                row["source_record_input_digest"],
            ),
        )
        family_ids = sorted(
            {row["canonical_source_family_id"] for row in members}
        )
        body = {
            "parent_document_id": parent,
            "document_identity_surface": identity_surface,
            "document_identity_digest": canonical_digest(
                {
                    "parent_document_id": parent,
                    "document_identity_surface": identity_surface,
                }
            ),
            "authority_anchor_fields": list(anchors),
            "authority_state": "PROVED" if anchors else "INSUFFICIENT",
            "source_members": members,
            "source_membership_root": domain_rows_digest(
                b"FIN_IA_R14_PARENT_DOCUMENT_SOURCE_MEMBERSHIP_V1\0",
                (canonical_json_bytes(row) for row in members),
            ),
            "canonical_source_family_ids": family_ids,
            "family_membership_root": domain_rows_digest(
                b"FIN_IA_R14_PARENT_DOCUMENT_FAMILY_MEMBERSHIP_V1\0",
                (
                    canonical_json_bytes(
                        {"canonical_source_family_id": family_id}
                    )
                    for family_id in family_ids
                ),
            ),
        }
        receipt = {**body, "receipt_digest": canonical_digest(body)}
        receipts.append(receipt)
        for member in members:
            source_id = str(member["source_record_id"])
            require(
                source_id not in by_source,
                f"R14_rebuild_parent_document_source_duplicate:{source_id}",
            )
            by_source[source_id] = receipt
    return receipts, by_source


def _context_value(row: Mapping[str, Any], field: str) -> Any:
    metadata = dict(row.get("metadata") or {})
    if field == "fiscal_year" and metadata.get("reported_fiscal_year") is not None:
        return metadata["reported_fiscal_year"]
    if field == "period_end" and metadata.get("reported_period_end") is not None:
        return metadata["reported_period_end"]
    return row[field] if field in row else metadata.get(field)


def _raw_source_identity(value: Mapping[str, Any]) -> tuple[str, str]:
    source_id = require_identifier(value.get("evidence_id"), field="rebuild_source_id")
    metadata = dict(value.get("metadata") or {})
    page = str(metadata.get("source_page_record_id") or "").strip()
    if page:
        family = page
    elif "::SLICE::" in source_id:
        family = source_id.partition("::SLICE::")[0]
    else:
        family = source_id
    return source_id, family


def _raw_object_identity(value: Mapping[str, Any]) -> tuple[str, str]:
    object_id = require_identifier(
        value.get("compiled_object_id"), field="rebuild_object_id"
    )
    base = dict(value.get("base_object_view") or {})
    lineage = dict(base.get("source_lineage") or {})
    family = str(lineage.get("source_page_record_id") or "").strip()
    if not family:
        family = str(base.get("source_record_id") or "").strip()
        require(bool(family), "R14_rebuild_object_source_missing")
        if "::SLICE::" in family:
            family = family.partition("::SLICE::")[0]
    return object_id, family


def _rebuild_slice_contract(
    *, row: Mapping[str, Any], source_row: Mapping[str, Any]
) -> dict[str, str]:
    object_id = require_identifier(row.get("compiled_object_id"), field="rebuild_object_id")
    base = dict(row.get("base_object_view") or {})
    source_id = require_identifier(
        base.get("source_record_id"), field="rebuild_object_primary_source_id"
    )
    require(
        source_id == require_identifier(source_row.get("evidence_id"), field="rebuild_source_id"),
        f"R14_rebuild_object_source_record_rebind:{object_id}",
    )
    source_record_digest = canonical_digest(dict(source_row))
    declared_source_digest = base.get("source_record_digest")
    require(
        declared_source_digest is None or declared_source_digest == source_record_digest,
        f"R14_rebuild_object_source_record_digest_mismatch:{object_id}",
    )
    surface_text = base.get("surface_text")
    require(
        isinstance(surface_text, str),
        f"R14_rebuild_object_source_slice_text_invalid:{object_id}",
    )
    surface_digest = canonical_digest(surface_text)
    declared_surface_digest = base.get("surface_digest")
    require(
        declared_surface_digest is None or declared_surface_digest == surface_digest,
        f"R14_rebuild_object_source_slice_digest_mismatch:{object_id}",
    )
    focus = dict(base.get("focus_binding") or {})
    mode = str(focus.get("mode") or "")
    require(
        mode in _SOURCE_SLICE_MODES,
        f"R14_rebuild_object_source_slice_mode_invalid:{object_id}",
    )
    if mode == "parent_context":
        require(
            set(focus) == {"mode", "parent_context"}
            and isinstance(focus.get("parent_context"), dict),
            f"R14_rebuild_object_parent_context_binding_invalid:{object_id}",
        )
        context = dict(focus["parent_context"])
        independently_projected = {
            field: _context_value(source_row, field) for field in context
        }
        require(
            bool(context)
            and set(context).issubset(_PARENT_CONTEXT_FIELDS)
            and context == independently_projected
            and surface_text
            == "\n".join(
                f"{field}: {context[field]}"
                for field in _PARENT_CONTEXT_FIELDS
                if field in context
                and context[field] is not None
                and context[field] != ""
            ),
            f"R14_rebuild_object_parent_context_surface_mismatch:{object_id}",
        )
    else:
        expected_keys = {"mode", "char_start", "char_end"}
        if mode == "balanced_table":
            expected_keys.add("table_id")
        start = focus.get("char_start")
        end = focus.get("char_end")
        source_text = source_row.get("text")
        require(
            set(focus) == expected_keys
            and type(start) is int
            and type(end) is int
            and isinstance(source_text, str)
            and 0 <= start <= end <= len(source_text)
            and source_text[start:end] == surface_text,
            f"R14_rebuild_object_source_slice_offset_mismatch:{object_id}",
        )
    metadata_digest = canonical_digest(
        {
            "base_object_view": dict(row.get("base_object_view") or {}),
            "object_kind": row.get("object_kind"),
            "lineage_source_record_ids": row.get("lineage_source_record_ids"),
        }
    )
    return {
        "source_record_input_digest": source_record_digest,
        "source_slice_mode": mode,
        "source_slice_digest": surface_digest,
        "source_slice_binding_digest": canonical_digest(
            {
                "source_record_id": source_id,
                "source_record_input_digest": source_record_digest,
                "source_slice_mode": mode,
                "source_slice_digest": surface_digest,
                "object_metadata_digest": metadata_digest,
            }
        ),
    }


def _rebuild_source_rows(
    values: Sequence[Mapping[str, Any]],
    *,
    parent_receipt_by_source: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    staged: list[dict[str, Any]] = []
    identities: list[str] = []
    for raw in values:
        row = dict(raw)
        identity, family = _raw_source_identity(row)
        identities.append(identity)
        staged.append(
            {
                "source_record_id": identity,
                "canonical_source_family_id": family,
                "input_digest": canonical_digest(row),
                "metadata_digest": canonical_digest(dict(row.get("metadata") or {})),
                "parent_document_binding_digest": _parent_binding(row),
                "parent_document_receipt_digest": (
                    parent_receipt_by_source.get(identity, {}).get(
                        "receipt_digest",
                        _EMPTY_PARENT_DOCUMENT_RECEIPT_DIGEST,
                    )
                ),
            }
        )
    duplicate = sorted(k for k, n in Counter(identities).items() if n != 1)
    require(not duplicate, f"R14_rebuild_source_duplicate:{duplicate[:3]}")
    staged = sorted(
        staged,
        key=lambda row: (
            row["canonical_source_family_id"],
            row["source_record_id"],
            row["input_digest"],
        ),
    )
    next_occurrence: defaultdict[str, int] = defaultdict(int)
    rebuilt: list[dict[str, Any]] = []
    for index, row in enumerate(staged):
        family = str(row["canonical_source_family_id"])
        occurrence = next_occurrence[family]
        next_occurrence[family] = occurrence + 1
        rebuilt.append(
            {
                "manifest_index": index,
                **row,
                "occurrence_index": occurrence,
            }
        )
    return rebuilt


def _rebuild_object_rows(
    values: Sequence[Mapping[str, Any]],
    *,
    families: set[str],
    source_id_to_family: Mapping[str, str],
    source_by_id: Mapping[str, Mapping[str, Any]],
    parent_receipt_by_source: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    staged: list[dict[str, Any]] = []
    identities: list[str] = []
    for raw in values:
        row = dict(raw)
        identity, family = _raw_object_identity(row)
        identities.append(identity)
        require(family in families, f"R14_rebuild_object_family_missing:{family}")
        base = dict(row.get("base_object_view") or {})
        primary_source_id = require_identifier(
            base.get("source_record_id"), field="rebuild_object_primary_source_id"
        )
        require(
            source_id_to_family.get(primary_source_id) == family,
            f"R14_rebuild_object_primary_family_rebind:{identity}",
        )
        lineage_source_ids = tuple(
            sorted(
                {
                    require_identifier(value, field="rebuild_object_lineage_source_id")
                    for value in row.get("lineage_source_record_ids") or ()
                }
            )
        )
        require(
            primary_source_id in lineage_source_ids
            and set(lineage_source_ids).issubset(source_id_to_family),
            f"R14_rebuild_object_lineage_invalid:{identity}",
        )
        primary_parent = _parent_binding(source_by_id[primary_source_id])
        primary_receipt = parent_receipt_by_source.get(primary_source_id)
        primary_receipt_digest = (
            primary_receipt.get("receipt_digest")
            if primary_receipt is not None
            else _EMPTY_PARENT_DOCUMENT_RECEIPT_DIGEST
        )
        empty_parent = canonical_digest({"parent_document_id": None})
        lineage_bindings: list[dict[str, Any]] = []
        for lineage_source_id in lineage_source_ids:
            lineage_family = source_id_to_family[lineage_source_id]
            lineage_parent = _parent_binding(source_by_id[lineage_source_id])
            lineage_receipt = parent_receipt_by_source.get(lineage_source_id)
            lineage_receipt_digest = (
                lineage_receipt.get("receipt_digest")
                if lineage_receipt is not None
                else _EMPTY_PARENT_DOCUMENT_RECEIPT_DIGEST
            )
            relationship = (
                "same_canonical_family"
                if lineage_family == family
                else "shared_parent_document"
                if lineage_parent == primary_parent and lineage_parent != empty_parent
                and lineage_receipt_digest == primary_receipt_digest
                and lineage_receipt_digest
                != _EMPTY_PARENT_DOCUMENT_RECEIPT_DIGEST
                and lineage_receipt is not None
                and lineage_receipt.get("authority_state") == "PROVED"
                else ""
            )
            require(
                bool(relationship),
                f"R14_rebuild_object_lineage_relationship_unproved:{identity}:{lineage_source_id}",
            )
            lineage_bindings.append(
                {
                    "source_record_id": lineage_source_id,
                    "canonical_source_family_id": lineage_family,
                    "source_record_input_digest": canonical_digest(
                        dict(source_by_id[lineage_source_id])
                    ),
                    "parent_document_binding_digest": lineage_parent,
                    "parent_document_receipt_digest": lineage_receipt_digest,
                    "relationship_to_primary": relationship,
                    "relationship_evidence_digest": canonical_digest(
                        {
                            "relationship": relationship,
                            "primary_source_record_id": primary_source_id,
                            "lineage_source_record_id": lineage_source_id,
                            "primary_family_id": family,
                            "lineage_family_id": lineage_family,
                            "primary_parent_document_binding_digest": primary_parent,
                            "lineage_parent_document_binding_digest": lineage_parent,
                            "primary_parent_document_receipt_digest": primary_receipt_digest,
                            "lineage_parent_document_receipt_digest": lineage_receipt_digest,
                        }
                    ),
                }
            )
        staged.append(
            {
                "compiled_object_id": identity,
                "canonical_source_family_id": family,
                "primary_source_record_id": primary_source_id,
                "lineage_source_record_ids": list(lineage_source_ids),
                "lineage_bindings": lineage_bindings,
                "lineage_source_keyset_digest": domain_rows_digest(
                    b"FIN_IA_R14_OBJECT_LINEAGE_SOURCE_KEYSET_V1\0",
                    (canonical_json_bytes(value) for value in lineage_bindings),
                ),
                "input_digest": canonical_digest(row),
                "metadata_digest": canonical_digest(
                    {
                        "base_object_view": dict(row.get("base_object_view") or {}),
                        "object_kind": row.get("object_kind"),
                        "lineage_source_record_ids": row.get(
                            "lineage_source_record_ids"
                        ),
                    }
                ),
                **_rebuild_slice_contract(
                    row=row, source_row=source_by_id[primary_source_id]
                ),
            }
        )
    duplicate = sorted(k for k, n in Counter(identities).items() if n != 1)
    require(not duplicate, f"R14_rebuild_object_duplicate:{duplicate[:3]}")
    staged = sorted(
        staged,
        key=lambda row: (
            row["canonical_source_family_id"],
            row["compiled_object_id"],
            row["input_digest"],
        ),
    )
    return [{"manifest_index": i, **row} for i, row in enumerate(staged)]


def rebuild_input_population_r14(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    target_ids: Iterable[str] = TARGET_IDS,
) -> dict[str, Any]:
    targets = tuple(sorted(str(value) for value in target_ids))
    require(targets == TARGET_IDS, "R14_rebuild_target_set_invalid")
    parent_document_receipts, parent_receipt_by_source = (
        _rebuild_parent_document_receipts(source_rows)
    )
    sources = _rebuild_source_rows(
        source_rows,
        parent_receipt_by_source=parent_receipt_by_source,
    )
    families = {str(row["canonical_source_family_id"]) for row in sources}
    source_id_to_family = {
        str(row["source_record_id"]): str(row["canonical_source_family_id"])
        for row in sources
    }
    source_by_id = {
        require_identifier(row.get("evidence_id"), field="rebuild_source_id"): dict(row)
        for row in source_rows
    }
    objects = _rebuild_object_rows(
        object_rows,
        families=families,
        source_id_to_family=source_id_to_family,
        source_by_id=source_by_id,
        parent_receipt_by_source=parent_receipt_by_source,
    )

    source_root = domain_rows_digest(
        b"FIN_IA_R14_SOURCE_KEYSET_V1\0",
        (canonical_json_bytes(row) for row in sources),
    )
    object_root = domain_rows_digest(
        b"FIN_IA_R14_OBJECT_KEYSET_V1\0",
        (canonical_json_bytes(row) for row in objects),
    )
    parent_document_receipt_root = domain_rows_digest(
        b"FIN_IA_R14_PARENT_DOCUMENT_RECEIPTS_V1\0",
        (canonical_json_bytes(row) for row in parent_document_receipts),
    )
    family_root = domain_rows_digest(
        b"FIN_IA_R14_FAMILY_OCCURRENCE_V1\0",
        (
            canonical_json_bytes(
                {
                    "canonical_source_family_id": row[
                        "canonical_source_family_id"
                    ],
                    "occurrence_index": row["occurrence_index"],
                    "source_record_id": row["source_record_id"],
                }
            )
            for row in sources
        ),
    )
    cross_root = domain_rows_digest(
        b"FIN_IA_R14_TARGET_CROSS_PRODUCT_V1\0",
        (
            canonical_json_bytes(
                {
                    "lane": lane,
                    "manifest_index": row["manifest_index"],
                    "input_digest": row["input_digest"],
                    "target_id": target,
                }
            )
            for lane, entries in (("source", sources), ("compiled", objects))
            for target in targets
            for row in entries
        ),
    )
    manifest_root = domain_rows_digest(
        b"FIN_IA_R14_POPULATION_MANIFEST_ROOT_V1\0",
        (
            canonical_json_bytes(
                {
                    "source_keyset_digest": source_root,
                    "object_keyset_digest": object_root,
                    "parent_document_receipt_root": parent_document_receipt_root,
                    "canonical_family_occurrence_digest": family_root,
                    "target_cross_product_digest": cross_root,
                    "target_ids": list(targets),
                }
            )
            for _ in (0,)
        ),
    )
    return with_result_digest(
        {
            "schema_version": REBUILDER_SCHEMA_VERSION,
            "rebuilder_id": REBUILDER_ID,
            "target_ids": list(targets),
            "source_canonical_order": sources,
            "object_canonical_order": objects,
            "parent_document_receipts": parent_document_receipts,
            "source_record_count": len(sources),
            "compiled_object_count": len(objects),
            "canonical_source_family_count": len(families),
            "expected_lane_counts": {
                "source_per_target": len(sources),
                "compiled_per_target": len(objects),
                "source_all_targets": len(sources) * len(targets),
                "compiled_all_targets": len(objects) * len(targets),
                "total": (len(sources) + len(objects)) * len(targets),
            },
            "source_keyset_digest": source_root,
            "object_keyset_digest": object_root,
            "parent_document_receipt_root": parent_document_receipt_root,
            "canonical_family_occurrence_digest": family_root,
            "target_cross_product_digest": cross_root,
            "manifest_root": manifest_root,
        }
    )


__all__ = [
    "REBUILDER_ID",
    "REBUILDER_SCHEMA_VERSION",
    "rebuild_input_population_r14",
]
