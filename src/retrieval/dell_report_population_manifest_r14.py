from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .dell_report_r14_common import (
    TARGET_IDS,
    canonical_digest,
    canonical_json_bytes,
    domain_rows_digest,
    file_sha256,
    require,
    require_identifier,
    require_sha256,
    resolve_repo_relative_path,
    validate_result_digest,
    with_result_digest,
)


MANIFEST_SCHEMA_VERSION = "fin_ia_dell_03B_R14_input_population_manifest_v1_0"
COMMITMENT_SCHEMA_VERSION = (
    "fin_ia_dell_03B_R14_input_population_manifest_commitment_v1_0"
)
CANONICALIZATION_VERSION = "R14_population_canonical_order_v1"
ENUMERATOR_VERSION = "R14_population_producer_v1"
INDEPENDENT_REBUILDER_ID = "R14_population_independent_rebuilder_v1"
SOURCE_SLICE_MODES = (
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


def _source_record_id(row: Mapping[str, Any]) -> str:
    return require_identifier(row.get("evidence_id"), field="source_record_id")


def _source_family_id(row: Mapping[str, Any]) -> str:
    source_id = _source_record_id(row)
    metadata = dict(row.get("metadata") or {})
    page_id = str(metadata.get("source_page_record_id") or "").strip()
    if page_id:
        return page_id
    if "::SLICE::" in source_id:
        return source_id.split("::SLICE::", 1)[0]
    return source_id


def _source_parent_document_binding_digest(row: Mapping[str, Any]) -> str:
    metadata = dict(row.get("metadata") or {})
    parent_document_id = str(metadata.get("parent_document_id") or "").strip()
    return canonical_digest({"parent_document_id": parent_document_id or None})


def _parent_document_identity_value(
    row: Mapping[str, Any], field: str
) -> Any:
    metadata = dict(row.get("metadata") or {})
    value = row.get(field) if field in row else metadata.get(field)
    if isinstance(value, str):
        value = value.strip()
    return value


def _parent_document_receipts(
    source_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Bind a parent document to the complete immutable source membership.

    A repeated ``parent_document_id`` is not evidence by itself.  The receipt
    binds the identifier to an invariant document identity surface and to the
    complete set of source-record digests present in the committed population.
    Cross-family lineage is allowed only through a PROVED receipt.
    """
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in source_rows:
        row = dict(raw)
        metadata = dict(row.get("metadata") or {})
        parent_document_id = str(
            metadata.get("parent_document_id") or ""
        ).strip()
        if parent_document_id:
            grouped[parent_document_id].append(row)

    receipts: list[dict[str, Any]] = []
    receipt_by_source: dict[str, dict[str, Any]] = {}
    for parent_document_id, rows in sorted(grouped.items()):
        identity_surface: dict[str, Any] = {}
        for field in _PARENT_DOCUMENT_IDENTITY_FIELDS:
            values = [_parent_document_identity_value(row, field) for row in rows]
            normalized = [
                value for value in values if value is not None and value != ""
            ]
            if normalized and len(normalized) == len(values) and all(
                value == normalized[0] for value in normalized
            ):
                identity_surface[field] = normalized[0]
        authority_anchors = tuple(
            sorted(set(identity_surface).intersection(_PARENT_DOCUMENT_AUTHORITY_ANCHORS))
        )
        source_members = sorted(
            (
                {
                    "source_record_id": _source_record_id(row),
                    "canonical_source_family_id": _source_family_id(row),
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
        source_membership_root = domain_rows_digest(
            b"FIN_IA_R14_PARENT_DOCUMENT_SOURCE_MEMBERSHIP_V1\0",
            (canonical_json_bytes(row) for row in source_members),
        )
        family_ids = sorted(
            {row["canonical_source_family_id"] for row in source_members}
        )
        body = {
            "parent_document_id": parent_document_id,
            "document_identity_surface": identity_surface,
            "document_identity_digest": canonical_digest(
                {
                    "parent_document_id": parent_document_id,
                    "document_identity_surface": identity_surface,
                }
            ),
            "authority_anchor_fields": list(authority_anchors),
            "authority_state": "PROVED" if authority_anchors else "INSUFFICIENT",
            "source_members": source_members,
            "source_membership_root": source_membership_root,
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
        for row in source_members:
            source_id = str(row["source_record_id"])
            require(
                source_id not in receipt_by_source,
                f"R14_parent_document_source_membership_duplicate:{source_id}",
            )
            receipt_by_source[source_id] = receipt
    return receipts, receipt_by_source


def _project_parent_context_value(
    source_row: Mapping[str, Any], field: str
) -> Any:
    metadata = dict(source_row.get("metadata") or {})
    if field == "fiscal_year" and metadata.get("reported_fiscal_year") is not None:
        return metadata["reported_fiscal_year"]
    if field == "period_end" and metadata.get("reported_period_end") is not None:
        return metadata["reported_period_end"]
    if field in source_row:
        return source_row[field]
    return metadata.get(field)


def _compiled_object_id(row: Mapping[str, Any]) -> str:
    return require_identifier(row.get("compiled_object_id"), field="compiled_object_id")


def _source_slice_contract(
    *, row: Mapping[str, Any], source_row: Mapping[str, Any]
) -> dict[str, str]:
    object_id = _compiled_object_id(row)
    base = dict(row.get("base_object_view") or {})
    source_id = require_identifier(
        base.get("source_record_id"), field="compiled_object_primary_source_id"
    )
    require(
        source_id == _source_record_id(source_row),
        f"R14_compiled_object_source_record_rebind:{object_id}",
    )
    source_record_digest = canonical_digest(dict(source_row))
    declared_source_digest = base.get("source_record_digest")
    require(
        declared_source_digest is None or declared_source_digest == source_record_digest,
        f"R14_compiled_object_source_record_digest_mismatch:{object_id}",
    )
    surface_text = base.get("surface_text")
    require(
        isinstance(surface_text, str),
        f"R14_compiled_object_source_slice_text_invalid:{object_id}",
    )
    surface_digest = canonical_digest(surface_text)
    declared_surface_digest = base.get("surface_digest")
    require(
        declared_surface_digest is None or declared_surface_digest == surface_digest,
        f"R14_compiled_object_source_slice_digest_mismatch:{object_id}",
    )
    focus = dict(base.get("focus_binding") or {})
    mode = str(focus.get("mode") or "")
    require(
        mode in SOURCE_SLICE_MODES,
        f"R14_compiled_object_source_slice_mode_invalid:{object_id}",
    )
    if mode == "parent_context":
        require(
            set(focus) == {"mode", "parent_context"}
            and isinstance(focus.get("parent_context"), dict),
            f"R14_compiled_object_parent_context_binding_invalid:{object_id}",
        )
        context = dict(focus["parent_context"])
        projected_context = {
            field: _project_parent_context_value(source_row, field)
            for field in context
        }
        require(
            bool(context)
            and set(context).issubset(_PARENT_CONTEXT_FIELDS)
            and context == projected_context
            and surface_text
            == "\n".join(
                f"{field}: {context[field]}"
                for field in _PARENT_CONTEXT_FIELDS
                if field in context
                and context[field] is not None
                and context[field] != ""
            ),
            f"R14_compiled_object_parent_context_surface_mismatch:{object_id}",
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
            f"R14_compiled_object_source_slice_offset_mismatch:{object_id}",
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


def _object_family_id(row: Mapping[str, Any]) -> str:
    base = dict(row.get("base_object_view") or {})
    lineage = dict(base.get("source_lineage") or {})
    page_id = str(lineage.get("source_page_record_id") or "").strip()
    if page_id:
        return page_id
    source_id = str(base.get("source_record_id") or "").strip()
    require(bool(source_id), "R14_compiled_object_source_record_id_missing")
    if "::SLICE::" in source_id:
        return source_id.split("::SLICE::", 1)[0]
    return source_id


def _source_entries(
    source_rows: Sequence[Mapping[str, Any]],
    *,
    parent_receipt_by_source: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    ids: list[str] = []
    for raw in source_rows:
        row = dict(raw)
        source_id = _source_record_id(row)
        ids.append(source_id)
        prepared.append(
            {
                "source_record_id": source_id,
                "canonical_source_family_id": _source_family_id(row),
                "input_digest": canonical_digest(row),
                "metadata_digest": canonical_digest(dict(row.get("metadata") or {})),
                "parent_document_binding_digest": (
                    _source_parent_document_binding_digest(row)
                ),
                "parent_document_receipt_digest": (
                    parent_receipt_by_source.get(source_id, {}).get(
                        "receipt_digest",
                        _EMPTY_PARENT_DOCUMENT_RECEIPT_DIGEST,
                    )
                ),
            }
        )
    duplicate_ids = sorted(key for key, count in Counter(ids).items() if count > 1)
    require(not duplicate_ids, f"R14_source_duplicate:{duplicate_ids[:3]}")
    prepared.sort(
        key=lambda row: (
            row["canonical_source_family_id"],
            row["source_record_id"],
            row["input_digest"],
        )
    )
    occurrence_by_family: defaultdict[str, int] = defaultdict(int)
    output: list[dict[str, Any]] = []
    for manifest_index, row in enumerate(prepared):
        family_id = str(row["canonical_source_family_id"])
        occurrence_index = occurrence_by_family[family_id]
        occurrence_by_family[family_id] += 1
        output.append(
            {
                "manifest_index": manifest_index,
                **row,
                "occurrence_index": occurrence_index,
            }
        )
    return output


def _object_entries(
    object_rows: Sequence[Mapping[str, Any]],
    *,
    source_family_ids: set[str],
    source_id_to_family: Mapping[str, str],
    source_by_id: Mapping[str, Mapping[str, Any]],
    parent_receipt_by_source: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    ids: list[str] = []
    for raw in object_rows:
        row = dict(raw)
        object_id = _compiled_object_id(row)
        family_id = _object_family_id(row)
        require(
            family_id in source_family_ids,
            f"R14_compiled_object_family_missing:{family_id}",
        )
        base = dict(row.get("base_object_view") or {})
        primary_source_id = require_identifier(
            base.get("source_record_id"), field="compiled_object_primary_source_id"
        )
        require(
            source_id_to_family.get(primary_source_id) == family_id,
            f"R14_compiled_object_primary_family_rebind:{object_id}",
        )
        lineage_source_ids = tuple(
            sorted(
                {
                    require_identifier(value, field="compiled_object_lineage_source_id")
                    for value in row.get("lineage_source_record_ids") or ()
                }
            )
        )
        require(
            primary_source_id in lineage_source_ids
            and set(lineage_source_ids).issubset(source_id_to_family),
            f"R14_compiled_object_lineage_invalid:{object_id}",
        )
        primary_parent_digest = _source_parent_document_binding_digest(
            source_by_id[primary_source_id]
        )
        primary_parent_receipt = parent_receipt_by_source.get(primary_source_id)
        primary_parent_receipt_digest = (
            primary_parent_receipt.get("receipt_digest")
            if primary_parent_receipt is not None
            else _EMPTY_PARENT_DOCUMENT_RECEIPT_DIGEST
        )
        empty_parent_digest = canonical_digest({"parent_document_id": None})
        lineage_bindings: list[dict[str, Any]] = []
        for lineage_source_id in lineage_source_ids:
            lineage_family_id = source_id_to_family[lineage_source_id]
            lineage_parent_digest = _source_parent_document_binding_digest(
                source_by_id[lineage_source_id]
            )
            lineage_parent_receipt = parent_receipt_by_source.get(
                lineage_source_id
            )
            lineage_parent_receipt_digest = (
                lineage_parent_receipt.get("receipt_digest")
                if lineage_parent_receipt is not None
                else _EMPTY_PARENT_DOCUMENT_RECEIPT_DIGEST
            )
            relationship = (
                "same_canonical_family"
                if lineage_family_id == family_id
                else "shared_parent_document"
                if lineage_parent_digest == primary_parent_digest
                and lineage_parent_digest != empty_parent_digest
                and lineage_parent_receipt_digest
                == primary_parent_receipt_digest
                and lineage_parent_receipt_digest
                != _EMPTY_PARENT_DOCUMENT_RECEIPT_DIGEST
                and lineage_parent_receipt is not None
                and lineage_parent_receipt.get("authority_state") == "PROVED"
                else ""
            )
            require(
                bool(relationship),
                f"R14_compiled_object_lineage_relationship_unproved:{object_id}:{lineage_source_id}",
            )
            relationship_evidence_digest = canonical_digest(
                {
                    "relationship": relationship,
                    "primary_source_record_id": primary_source_id,
                    "lineage_source_record_id": lineage_source_id,
                    "primary_family_id": family_id,
                    "lineage_family_id": lineage_family_id,
                    "primary_parent_document_binding_digest": primary_parent_digest,
                    "lineage_parent_document_binding_digest": lineage_parent_digest,
                    "primary_parent_document_receipt_digest": primary_parent_receipt_digest,
                    "lineage_parent_document_receipt_digest": lineage_parent_receipt_digest,
                }
            )
            lineage_bindings.append(
                {
                    "source_record_id": lineage_source_id,
                    "canonical_source_family_id": lineage_family_id,
                    "source_record_input_digest": canonical_digest(
                        dict(source_by_id[lineage_source_id])
                    ),
                    "parent_document_binding_digest": lineage_parent_digest,
                    "parent_document_receipt_digest": lineage_parent_receipt_digest,
                    "relationship_to_primary": relationship,
                    "relationship_evidence_digest": relationship_evidence_digest,
                }
            )
        ids.append(object_id)
        slice_contract = _source_slice_contract(
            row=row, source_row=source_by_id[primary_source_id]
        )
        prepared.append(
            {
                "compiled_object_id": object_id,
                "canonical_source_family_id": family_id,
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
                **slice_contract,
            }
        )
    duplicate_ids = sorted(key for key, count in Counter(ids).items() if count > 1)
    require(not duplicate_ids, f"R14_compiled_object_duplicate:{duplicate_ids[:3]}")
    prepared.sort(
        key=lambda row: (
            row["canonical_source_family_id"],
            row["compiled_object_id"],
            row["input_digest"],
        )
    )
    return [
        {"manifest_index": index, **row}
        for index, row in enumerate(prepared)
    ]


def _population_roots(
    *,
    source_entries: Sequence[Mapping[str, Any]],
    object_entries: Sequence[Mapping[str, Any]],
    parent_document_receipts: Sequence[Mapping[str, Any]],
    target_ids: Sequence[str],
) -> dict[str, str]:
    source_root = domain_rows_digest(
        b"FIN_IA_R14_SOURCE_KEYSET_V1\0",
        (canonical_json_bytes(row) for row in source_entries),
    )
    object_root = domain_rows_digest(
        b"FIN_IA_R14_OBJECT_KEYSET_V1\0",
        (canonical_json_bytes(row) for row in object_entries),
    )
    parent_document_receipt_root = domain_rows_digest(
        b"FIN_IA_R14_PARENT_DOCUMENT_RECEIPTS_V1\0",
        (canonical_json_bytes(row) for row in parent_document_receipts),
    )
    family_occurrence_root = domain_rows_digest(
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
            for row in source_entries
        ),
    )
    cross_product_root = domain_rows_digest(
        b"FIN_IA_R14_TARGET_CROSS_PRODUCT_V1\0",
        (
            canonical_json_bytes(
                {
                    "lane": lane,
                    "manifest_index": row["manifest_index"],
                    "input_digest": row["input_digest"],
                    "target_id": target_id,
                }
            )
            for lane, entries in (
                ("source", source_entries),
                ("compiled", object_entries),
            )
            for target_id in target_ids
            for row in entries
        ),
    )
    manifest_root = domain_rows_digest(
        b"FIN_IA_R14_POPULATION_MANIFEST_ROOT_V1\0",
        (
            canonical_json_bytes(row)
            for row in (
                {
                    "source_keyset_digest": source_root,
                    "object_keyset_digest": object_root,
                    "parent_document_receipt_root": parent_document_receipt_root,
                    "canonical_family_occurrence_digest": family_occurrence_root,
                    "target_cross_product_digest": cross_product_root,
                    "target_ids": list(target_ids),
                },
            )
        ),
    )
    return {
        "source_keyset_digest": source_root,
        "object_keyset_digest": object_root,
        "parent_document_receipt_root": parent_document_receipt_root,
        "canonical_family_occurrence_digest": family_occurrence_root,
        "target_cross_product_digest": cross_product_root,
        "manifest_root": manifest_root,
    }


def _validate_parent_document_receipts(
    *,
    receipts: Sequence[Mapping[str, Any]],
    source_entries: Sequence[Mapping[str, Any]],
) -> None:
    source_by_id = {
        str(row["source_record_id"]): row for row in source_entries
    }
    require(
        len(source_by_id) == len(source_entries),
        "R14_parent_document_receipt_source_identity_duplicate",
    )
    seen_parent_ids: set[str] = set()
    seen_member_ids: set[str] = set()
    receipt_by_digest: dict[str, Mapping[str, Any]] = {}
    expected_order = sorted(
        receipts, key=lambda row: str(row.get("parent_document_id") or "")
    )
    require(
        list(receipts) == expected_order,
        "R14_parent_document_receipt_order_invalid",
    )
    for raw in receipts:
        receipt = dict(raw)
        require(
            set(receipt)
            == {
                "parent_document_id",
                "document_identity_surface",
                "document_identity_digest",
                "authority_anchor_fields",
                "authority_state",
                "source_members",
                "source_membership_root",
                "canonical_source_family_ids",
                "family_membership_root",
                "receipt_digest",
            },
            "R14_parent_document_receipt_keyset_invalid",
        )
        parent_document_id = require_identifier(
            receipt.get("parent_document_id"), field="parent_document_id"
        )
        require(
            parent_document_id not in seen_parent_ids,
            "R14_parent_document_receipt_parent_duplicate",
        )
        seen_parent_ids.add(parent_document_id)
        identity_surface = receipt.get("document_identity_surface")
        require(
            isinstance(identity_surface, dict)
            and bool(identity_surface)
            and set(identity_surface).issubset(_PARENT_DOCUMENT_IDENTITY_FIELDS),
            "R14_parent_document_identity_surface_invalid",
        )
        anchors = tuple(receipt.get("authority_anchor_fields") or ())
        expected_anchors = tuple(
            sorted(
                set(identity_surface).intersection(
                    _PARENT_DOCUMENT_AUTHORITY_ANCHORS
                )
            )
        )
        require(
            anchors == expected_anchors
            and receipt.get("authority_state")
            == ("PROVED" if expected_anchors else "INSUFFICIENT")
            and receipt.get("document_identity_digest")
            == canonical_digest(
                {
                    "parent_document_id": parent_document_id,
                    "document_identity_surface": identity_surface,
                }
            ),
            "R14_parent_document_identity_authority_invalid",
        )
        members = list(receipt.get("source_members") or ())
        require(bool(members), "R14_parent_document_membership_empty")
        require(
            members
            == sorted(
                members,
                key=lambda row: (
                    str(row.get("source_record_id") or ""),
                    str(row.get("canonical_source_family_id") or ""),
                    str(row.get("source_record_input_digest") or ""),
                ),
            ),
            "R14_parent_document_membership_order_invalid",
        )
        member_ids: list[str] = []
        for member in members:
            require(
                isinstance(member, dict)
                and set(member)
                == {
                    "source_record_id",
                    "canonical_source_family_id",
                    "source_record_input_digest",
                },
                "R14_parent_document_member_keyset_invalid",
            )
            source_id = require_identifier(
                member.get("source_record_id"), field="parent_member_source_id"
            )
            source = source_by_id.get(source_id)
            require(
                source is not None
                and source_id not in seen_member_ids
                and member.get("canonical_source_family_id")
                == source.get("canonical_source_family_id")
                and member.get("source_record_input_digest")
                == source.get("input_digest"),
                "R14_parent_document_member_source_binding_invalid",
            )
            seen_member_ids.add(source_id)
            member_ids.append(source_id)
        family_ids = sorted(
            {str(row["canonical_source_family_id"]) for row in members}
        )
        require(
            receipt.get("source_membership_root")
            == domain_rows_digest(
                b"FIN_IA_R14_PARENT_DOCUMENT_SOURCE_MEMBERSHIP_V1\0",
                (canonical_json_bytes(row) for row in members),
            )
            and receipt.get("canonical_source_family_ids") == family_ids
            and receipt.get("family_membership_root")
            == domain_rows_digest(
                b"FIN_IA_R14_PARENT_DOCUMENT_FAMILY_MEMBERSHIP_V1\0",
                (
                    canonical_json_bytes(
                        {"canonical_source_family_id": family_id}
                    )
                    for family_id in family_ids
                ),
            ),
            "R14_parent_document_membership_root_invalid",
        )
        body = {
            key: value
            for key, value in receipt.items()
            if key != "receipt_digest"
        }
        receipt_digest = require_sha256(
            receipt.get("receipt_digest"), field="parent_document_receipt"
        )
        require(
            receipt_digest == canonical_digest(body)
            and receipt_digest not in receipt_by_digest,
            "R14_parent_document_receipt_digest_invalid",
        )
        receipt_by_digest[receipt_digest] = receipt
        require(
            all(
                source_by_id[source_id].get("parent_document_receipt_digest")
                == receipt_digest
                for source_id in member_ids
            ),
            "R14_parent_document_source_receipt_rebind",
        )
    empty_parent_binding = canonical_digest({"parent_document_id": None})
    for source in source_entries:
        receipt_digest = source.get("parent_document_receipt_digest")
        require_sha256(
            receipt_digest, field="source_parent_document_receipt"
        )
        if source.get("parent_document_binding_digest") == empty_parent_binding:
            require(
                receipt_digest == _EMPTY_PARENT_DOCUMENT_RECEIPT_DIGEST,
                "R14_empty_parent_document_receipt_invalid",
            )
        else:
            require(
                receipt_digest in receipt_by_digest
                and source.get("source_record_id") in seen_member_ids,
                "R14_parent_document_receipt_missing",
            )


def build_input_population_manifest_r14(
    *,
    source_rows: Sequence[Mapping[str, Any]],
    object_rows: Sequence[Mapping[str, Any]],
    source_ref: str,
    source_sha256: str,
    object_ref: str,
    object_sha256: str,
    implementation_identity: str,
    changed_path_digest: str,
    recorded_at: str,
    target_ids: Iterable[str] = TARGET_IDS,
) -> dict[str, Any]:
    targets = tuple(sorted(str(value) for value in target_ids))
    require(targets == TARGET_IDS, "R14_population_target_set_invalid")
    parent_document_receipts, parent_receipt_by_source = (
        _parent_document_receipts(source_rows)
    )
    source_entries = _source_entries(
        source_rows,
        parent_receipt_by_source=parent_receipt_by_source,
    )
    source_families = {
        str(row["canonical_source_family_id"]) for row in source_entries
    }
    source_id_to_family = {
        str(row["source_record_id"]): str(row["canonical_source_family_id"])
        for row in source_entries
    }
    source_by_id = {
        _source_record_id(row): dict(row)
        for row in source_rows
    }
    object_entries = _object_entries(
        object_rows,
        source_family_ids=source_families,
        source_id_to_family=source_id_to_family,
        source_by_id=source_by_id,
        parent_receipt_by_source=parent_receipt_by_source,
    )
    roots = _population_roots(
        source_entries=source_entries,
        object_entries=object_entries,
        parent_document_receipts=parent_document_receipts,
        target_ids=targets,
    )
    body = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_id": "FIN-0.1.3-S1-DELL-03B-R14-INPUT-POPULATION-V1",
        "recorded_at": require_identifier(recorded_at, field="recorded_at"),
        "generator_version": ENUMERATOR_VERSION,
        "source_records": {
            "ref": require_identifier(source_ref, field="source_ref"),
            "sha256": require_sha256(source_sha256, field="source"),
            "count": len(source_entries),
        },
        "compiled_objects": {
            "ref": require_identifier(object_ref, field="object_ref"),
            "sha256": require_sha256(object_sha256, field="object"),
            "count": len(object_entries),
        },
        "target_ids": list(targets),
        "source_canonical_order": source_entries,
        "object_canonical_order": object_entries,
        "parent_document_receipts": parent_document_receipts,
        "checks": {
            "source_duplicate_count": 0,
            "object_duplicate_count": 0,
            "missing_or_empty_id_count": 0,
            "object_missing_source_family_count": 0,
        },
        "canonical_source_family_count": len(source_families),
        "expected_lane_counts": {
            "source_per_target": len(source_entries),
            "compiled_per_target": len(object_entries),
            "source_all_targets": len(source_entries) * len(targets),
            "compiled_all_targets": len(object_entries) * len(targets),
            "total": (len(source_entries) + len(object_entries)) * len(targets),
        },
        **roots,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "enumerator_version": ENUMERATOR_VERSION,
        "builder_module_identity": require_identifier(
            implementation_identity, field="implementation_identity"
        ),
        "builder_changed_path_digest": require_sha256(
            changed_path_digest, field="changed_path_digest"
        ),
        "independent_rebuilder_identity": INDEPENDENT_REBUILDER_ID,
    }
    output = with_result_digest(body)
    validate_input_population_manifest_r14(output)
    return output


def validate_input_population_manifest_r14(value: Mapping[str, Any]) -> None:
    validate_result_digest(value, code="R14_population_manifest")
    require(
        set(value)
        == {
            "schema_version",
            "manifest_id",
            "recorded_at",
            "generator_version",
            "source_records",
            "compiled_objects",
            "target_ids",
            "source_canonical_order",
            "object_canonical_order",
            "parent_document_receipts",
            "checks",
            "canonical_source_family_count",
            "expected_lane_counts",
            "source_keyset_digest",
            "object_keyset_digest",
            "parent_document_receipt_root",
            "canonical_family_occurrence_digest",
            "target_cross_product_digest",
            "manifest_root",
            "canonicalization_version",
            "enumerator_version",
            "builder_module_identity",
            "builder_changed_path_digest",
            "independent_rebuilder_identity",
            "result_digest",
        },
        "R14_population_manifest_keyset_invalid",
    )
    require(
        value.get("schema_version") == MANIFEST_SCHEMA_VERSION
        and value.get("manifest_id")
        == "FIN-0.1.3-S1-DELL-03B-R14-INPUT-POPULATION-V1"
        and value.get("canonicalization_version") == CANONICALIZATION_VERSION
        and value.get("generator_version") == ENUMERATOR_VERSION
        and value.get("enumerator_version") == ENUMERATOR_VERSION
        and value.get("independent_rebuilder_identity")
        == INDEPENDENT_REBUILDER_ID,
        "R14_population_manifest_identity_invalid",
    )
    require_identifier(value.get("recorded_at"), field="recorded_at")
    require_identifier(
        value.get("builder_module_identity"), field="builder_module_identity"
    )
    require_sha256(
        value.get("builder_changed_path_digest"), field="builder_changed_path_digest"
    )
    source_binding = value.get("source_records")
    object_binding = value.get("compiled_objects")
    require(
        isinstance(source_binding, dict)
        and set(source_binding) == {"ref", "sha256", "count"}
        and isinstance(object_binding, dict)
        and set(object_binding) == {"ref", "sha256", "count"},
        "R14_population_manifest_input_binding_schema_invalid",
    )
    require_identifier(source_binding.get("ref"), field="source_ref")
    require_identifier(object_binding.get("ref"), field="object_ref")
    require_sha256(source_binding.get("sha256"), field="source")
    require_sha256(object_binding.get("sha256"), field="object")
    targets = tuple(value.get("target_ids") or ())
    require(targets == TARGET_IDS, "R14_population_manifest_target_set_invalid")
    source_entries = list(value.get("source_canonical_order") or ())
    object_entries = list(value.get("object_canonical_order") or ())
    parent_document_receipts = list(
        value.get("parent_document_receipts") or ()
    )
    require(
        int(source_binding.get("count", -1)) == len(source_entries)
        and int(object_binding.get("count", -1)) == len(object_entries),
        "R14_population_manifest_bound_count_invalid",
    )
    require(
        [row.get("manifest_index") for row in source_entries]
        == list(range(len(source_entries)))
        and [row.get("manifest_index") for row in object_entries]
        == list(range(len(object_entries))),
        "R14_population_manifest_index_invalid",
    )
    require(
        all(
            set(row)
            == {
                "manifest_index",
                "source_record_id",
                "canonical_source_family_id",
                "input_digest",
                "metadata_digest",
                "parent_document_binding_digest",
                "parent_document_receipt_digest",
                "occurrence_index",
            }
            and bool(require_identifier(row["source_record_id"], field="source_record_id"))
            and bool(require_identifier(row["canonical_source_family_id"], field="source_family_id"))
            and require_sha256(row["input_digest"], field="source_input_digest")
            and require_sha256(row["metadata_digest"], field="source_metadata_digest")
            and require_sha256(
                row["parent_document_binding_digest"],
                field="source_parent_document_binding",
            )
            and require_sha256(
                row["parent_document_receipt_digest"],
                field="source_parent_document_receipt",
            )
            and isinstance(row["occurrence_index"], int)
            and row["occurrence_index"] >= 0
            for row in source_entries
        ),
        "R14_population_manifest_source_entry_invalid",
    )
    require(
        all(
            set(row)
            == {
                "manifest_index",
                "compiled_object_id",
                "canonical_source_family_id",
                "primary_source_record_id",
                "lineage_source_record_ids",
                "lineage_bindings",
                "lineage_source_keyset_digest",
                "source_record_input_digest",
                "source_slice_mode",
                "source_slice_digest",
                "source_slice_binding_digest",
                "input_digest",
                "metadata_digest",
            }
            and bool(require_identifier(row["compiled_object_id"], field="compiled_object_id"))
            and bool(require_identifier(row["canonical_source_family_id"], field="object_family_id"))
            and bool(require_identifier(row["primary_source_record_id"], field="object_primary_source_id"))
            and isinstance(row["lineage_source_record_ids"], list)
            and bool(row["lineage_source_record_ids"])
            and row["lineage_source_record_ids"]
            == sorted(set(row["lineage_source_record_ids"]))
            and row["primary_source_record_id"] in row["lineage_source_record_ids"]
            and isinstance(row["lineage_bindings"], list)
            and [value.get("source_record_id") for value in row["lineage_bindings"]]
            == row["lineage_source_record_ids"]
            and require_sha256(row["lineage_source_keyset_digest"], field="object_lineage_root")
            and require_sha256(row["source_record_input_digest"], field="object_source_record_input")
            and row["source_slice_mode"] in SOURCE_SLICE_MODES
            and require_sha256(row["source_slice_digest"], field="object_source_slice")
            and require_sha256(row["source_slice_binding_digest"], field="object_source_slice_binding")
            and require_sha256(row["input_digest"], field="object_input_digest")
            and require_sha256(row["metadata_digest"], field="object_metadata_digest")
            for row in object_entries
        ),
        "R14_population_manifest_object_entry_invalid",
    )
    _validate_parent_document_receipts(
        receipts=parent_document_receipts,
        source_entries=source_entries,
    )
    source_ids = [row["source_record_id"] for row in source_entries]
    object_ids = [row["compiled_object_id"] for row in object_entries]
    source_families = {
        row["canonical_source_family_id"] for row in source_entries
    }
    require(
        len(source_ids) == len(set(source_ids))
        and len(object_ids) == len(set(object_ids))
        and all(
            row["canonical_source_family_id"] in source_families
            for row in object_entries
        ),
        "R14_population_manifest_identity_bijection_invalid",
    )
    source_id_to_family = {
        row["source_record_id"]: row["canonical_source_family_id"]
        for row in source_entries
    }
    source_id_to_digest = {
        row["source_record_id"]: row["input_digest"] for row in source_entries
    }
    source_id_to_parent_digest = {
        row["source_record_id"]: row["parent_document_binding_digest"]
        for row in source_entries
    }
    source_id_to_parent_receipt_digest = {
        row["source_record_id"]: row["parent_document_receipt_digest"]
        for row in source_entries
    }
    parent_receipt_by_digest = {
        row["receipt_digest"]: row for row in parent_document_receipts
    }
    for row in object_entries:
        primary_source_id = row["primary_source_record_id"]
        primary_family_id = source_id_to_family[primary_source_id]
        primary_parent_digest = source_id_to_parent_digest[primary_source_id]
        primary_parent_receipt_digest = source_id_to_parent_receipt_digest[
            primary_source_id
        ]
        expected_lineage_bindings = []
        for source_id in row["lineage_source_record_ids"]:
            family_id = source_id_to_family[source_id]
            parent_digest = source_id_to_parent_digest[source_id]
            parent_receipt_digest = source_id_to_parent_receipt_digest[source_id]
            relationship = (
                "same_canonical_family"
                if family_id == primary_family_id
                else "shared_parent_document"
                if parent_digest == primary_parent_digest
                and parent_digest
                != canonical_digest({"parent_document_id": None})
                and parent_receipt_digest == primary_parent_receipt_digest
                and parent_receipt_digest
                != _EMPTY_PARENT_DOCUMENT_RECEIPT_DIGEST
                and parent_receipt_by_digest.get(
                    parent_receipt_digest, {}
                ).get("authority_state")
                == "PROVED"
                else ""
            )
            require(
                bool(relationship),
                "R14_population_manifest_lineage_relationship_unproved",
            )
            expected_lineage_bindings.append(
                {
                    "source_record_id": source_id,
                    "canonical_source_family_id": family_id,
                    "source_record_input_digest": source_id_to_digest[source_id],
                    "parent_document_binding_digest": parent_digest,
                    "parent_document_receipt_digest": parent_receipt_digest,
                    "relationship_to_primary": relationship,
                    "relationship_evidence_digest": canonical_digest(
                        {
                            "relationship": relationship,
                            "primary_source_record_id": primary_source_id,
                            "lineage_source_record_id": source_id,
                            "primary_family_id": primary_family_id,
                            "lineage_family_id": family_id,
                            "primary_parent_document_binding_digest": primary_parent_digest,
                            "lineage_parent_document_binding_digest": parent_digest,
                            "primary_parent_document_receipt_digest": primary_parent_receipt_digest,
                            "lineage_parent_document_receipt_digest": parent_receipt_digest,
                        }
                    ),
                }
            )
        require(
            set(row["lineage_source_record_ids"]).issubset(source_id_to_family)
            and row["canonical_source_family_id"] == primary_family_id
            and row["lineage_bindings"] == expected_lineage_bindings
            and row["lineage_source_keyset_digest"]
            == domain_rows_digest(
                b"FIN_IA_R14_OBJECT_LINEAGE_SOURCE_KEYSET_V1\0",
                (
                    canonical_json_bytes(value)
                    for value in expected_lineage_bindings
                ),
            )
            and row["source_record_input_digest"]
            == source_id_to_digest[row["primary_source_record_id"]]
            and row["source_slice_binding_digest"]
            == canonical_digest(
                {
                    "source_record_id": row["primary_source_record_id"],
                    "source_record_input_digest": row[
                        "source_record_input_digest"
                    ],
                    "source_slice_mode": row["source_slice_mode"],
                    "source_slice_digest": row["source_slice_digest"],
                    "object_metadata_digest": row["metadata_digest"],
                }
            ),
            "R14_population_manifest_object_lineage_recomputation_failed",
        )
    occurrence: defaultdict[str, int] = defaultdict(int)
    for row in source_entries:
        family = row["canonical_source_family_id"]
        require(
            row["occurrence_index"] == occurrence[family],
            "R14_population_manifest_occurrence_index_invalid",
        )
        occurrence[family] += 1
    require(
        source_entries
        == sorted(
            source_entries,
            key=lambda row: (
                row["canonical_source_family_id"],
                row["source_record_id"],
                row["input_digest"],
            ),
        )
        and object_entries
        == sorted(
            object_entries,
            key=lambda row: (
                row["canonical_source_family_id"],
                row["compiled_object_id"],
                row["input_digest"],
            ),
        ),
        "R14_population_manifest_canonical_order_invalid",
    )
    require(
        value.get("checks")
        == {
            "source_duplicate_count": 0,
            "object_duplicate_count": 0,
            "missing_or_empty_id_count": 0,
            "object_missing_source_family_count": 0,
        },
        "R14_population_manifest_checks_invalid",
    )
    expected_counts = {
        "source_per_target": len(source_entries),
        "compiled_per_target": len(object_entries),
        "source_all_targets": len(source_entries) * len(targets),
        "compiled_all_targets": len(object_entries) * len(targets),
        "total": (len(source_entries) + len(object_entries)) * len(targets),
    }
    require(
        value.get("canonical_source_family_count") == len(source_families)
        and value.get("expected_lane_counts") == expected_counts,
        "R14_population_manifest_derived_counts_invalid",
    )
    roots = _population_roots(
        source_entries=source_entries,
        object_entries=object_entries,
        parent_document_receipts=parent_document_receipts,
        target_ids=targets,
    )
    require(
        all(value.get(key) == digest for key, digest in roots.items()),
        "R14_population_manifest_root_recomputation_failed",
    )


def build_input_population_manifest_from_bound_files_r14(
    *,
    root: Path,
    source_binding: Mapping[str, Any],
    object_binding: Mapping[str, Any],
    implementation_identity: str,
    changed_path_digest: str,
    recorded_at: str,
) -> dict[str, Any]:
    source_path = resolve_repo_relative_path(
        root, source_binding.get("ref"), field="source_ref"
    )
    object_path = resolve_repo_relative_path(
        root, object_binding.get("ref"), field="object_ref"
    )
    require(
        file_sha256(source_path) == require_sha256(source_binding.get("sha256"), field="source"),
        "R14_population_source_SHA_mismatch",
    )
    require(
        file_sha256(object_path) == require_sha256(object_binding.get("sha256"), field="object"),
        "R14_population_object_SHA_mismatch",
    )
    source_rows = [
        json.loads(line)
        for line in source_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    object_rows = [
        json.loads(line)
        for line in object_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    require(
        len(source_rows) == int(source_binding.get("count") or -1),
        "R14_population_source_count_mismatch",
    )
    require(
        len(object_rows) == int(object_binding.get("count") or -1),
        "R14_population_object_count_mismatch",
    )
    return build_input_population_manifest_r14(
        source_rows=source_rows,
        object_rows=object_rows,
        source_ref=str(source_binding["ref"]),
        source_sha256=str(source_binding["sha256"]),
        object_ref=str(object_binding["ref"]),
        object_sha256=str(object_binding["sha256"]),
        implementation_identity=implementation_identity,
        changed_path_digest=changed_path_digest,
        recorded_at=recorded_at,
    )


def build_population_commitment_r14(
    manifest: Mapping[str, Any], *, private_sha256: str, private_bytes: int
) -> dict[str, Any]:
    validate_input_population_manifest_r14(manifest)
    require(
        int(private_bytes) > 0,
        "R14_population_commitment_private_bytes_invalid",
    )
    body = {
        "schema_version": COMMITMENT_SCHEMA_VERSION,
        "manifest_id": manifest["manifest_id"],
        "manifest_result_digest": manifest["result_digest"],
        "source_records": dict(manifest["source_records"]),
        "compiled_objects": dict(manifest["compiled_objects"]),
        "target_ids": list(manifest["target_ids"]),
        "canonical_source_family_count": manifest[
            "canonical_source_family_count"
        ],
        "expected_lane_counts": dict(manifest["expected_lane_counts"]),
        "source_keyset_digest": manifest["source_keyset_digest"],
        "object_keyset_digest": manifest["object_keyset_digest"],
        "canonical_family_occurrence_digest": manifest[
            "canonical_family_occurrence_digest"
        ],
        "target_cross_product_digest": manifest["target_cross_product_digest"],
        "manifest_root": manifest["manifest_root"],
        "canonicalization_version": manifest["canonicalization_version"],
        "enumerator_version": manifest["enumerator_version"],
        "builder_module_identity": manifest["builder_module_identity"],
        "builder_changed_path_digest": manifest["builder_changed_path_digest"],
        "independent_rebuilder_identity": manifest[
            "independent_rebuilder_identity"
        ],
        "private_artifact_sha256": require_sha256(
            private_sha256, field="private_manifest"
        ),
        "private_artifact_bytes": int(private_bytes),
        "privacy_contract": {
            "contains_raw_text": False,
            "contains_private_locator": False,
            "contains_source_or_object_ID_rows": False,
        },
    }
    output = with_result_digest(body)
    validate_population_commitment_r14(output)
    return output


def validate_population_commitment_r14(value: Mapping[str, Any]) -> None:
    validate_result_digest(value, code="R14_population_commitment")
    require(
        set(value)
        == {
            "schema_version",
            "manifest_id",
            "manifest_result_digest",
            "source_records",
            "compiled_objects",
            "target_ids",
            "canonical_source_family_count",
            "expected_lane_counts",
            "source_keyset_digest",
            "object_keyset_digest",
            "canonical_family_occurrence_digest",
            "target_cross_product_digest",
            "manifest_root",
            "canonicalization_version",
            "enumerator_version",
            "builder_module_identity",
            "builder_changed_path_digest",
            "independent_rebuilder_identity",
            "private_artifact_sha256",
            "private_artifact_bytes",
            "privacy_contract",
            "result_digest",
        },
        "R14_population_commitment_keyset_invalid",
    )
    require(
        value.get("schema_version") == COMMITMENT_SCHEMA_VERSION
        and value.get("manifest_id")
        == "FIN-0.1.3-S1-DELL-03B-R14-INPUT-POPULATION-V1"
        and value.get("canonicalization_version") == CANONICALIZATION_VERSION
        and value.get("enumerator_version") == ENUMERATOR_VERSION
        and value.get("independent_rebuilder_identity")
        == INDEPENDENT_REBUILDER_ID,
        "R14_population_commitment_schema_invalid",
    )
    require_identifier(
        value.get("builder_module_identity"), field="population_builder_identity"
    )
    require(
        value.get("privacy_contract")
        == {
            "contains_raw_text": False,
            "contains_private_locator": False,
            "contains_source_or_object_ID_rows": False,
        },
        "R14_population_commitment_privacy_contract_invalid",
    )
    require_sha256(
        value.get("manifest_result_digest"), field="population_manifest_result_digest"
    )
    source = value.get("source_records")
    compiled = value.get("compiled_objects")
    require(
        isinstance(source, dict)
        and set(source) == {"ref", "sha256", "count"}
        and isinstance(compiled, dict)
        and set(compiled) == {"ref", "sha256", "count"},
        "R14_population_commitment_input_binding_schema_invalid",
    )
    require_identifier(source.get("ref"), field="population_source_ref")
    require_identifier(compiled.get("ref"), field="population_object_ref")
    require_sha256(source.get("sha256"), field="population_source")
    require_sha256(compiled.get("sha256"), field="population_object")
    require(
        type(source.get("count")) is int
        and source["count"] > 0
        and type(compiled.get("count")) is int
        and compiled["count"] > 0
        and type(value.get("canonical_source_family_count")) is int
        and 0 < value["canonical_source_family_count"] <= source["count"]
        and tuple(value.get("target_ids") or ()) == TARGET_IDS,
        "R14_population_commitment_population_invalid",
    )
    lane_counts = value.get("expected_lane_counts")
    expected_lane_counts = {
        "source_per_target": source["count"],
        "compiled_per_target": compiled["count"],
        "source_all_targets": source["count"] * len(TARGET_IDS),
        "compiled_all_targets": compiled["count"] * len(TARGET_IDS),
        "total": (source["count"] + compiled["count"]) * len(TARGET_IDS),
    }
    require(
        lane_counts == expected_lane_counts,
        "R14_population_commitment_lane_counts_invalid",
    )
    for field in (
        "source_keyset_digest",
        "object_keyset_digest",
        "canonical_family_occurrence_digest",
        "target_cross_product_digest",
        "manifest_root",
        "builder_changed_path_digest",
        "private_artifact_sha256",
    ):
        require_sha256(value.get(field), field=f"population_commitment_{field}")
    require(
        isinstance(value.get("private_artifact_bytes"), int)
        and value["private_artifact_bytes"] > 0,
        "R14_population_commitment_private_bytes_invalid",
    )


__all__ = [
    "CANONICALIZATION_VERSION",
    "COMMITMENT_SCHEMA_VERSION",
    "ENUMERATOR_VERSION",
    "INDEPENDENT_REBUILDER_ID",
    "MANIFEST_SCHEMA_VERSION",
    "build_input_population_manifest_from_bound_files_r14",
    "build_input_population_manifest_r14",
    "build_population_commitment_r14",
    "validate_input_population_manifest_r14",
    "validate_population_commitment_r14",
]
