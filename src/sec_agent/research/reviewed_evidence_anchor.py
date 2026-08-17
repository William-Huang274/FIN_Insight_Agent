from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
from typing import Any, Mapping, Sequence

from .reviewed_evidence_pack import canonical_digest


REVIEWED_EVIDENCE_ANCHOR_CATALOG_SCHEMA = (
    "fin_ia_reviewed_evidence_anchor_catalog_v1_0"
)
REVIEWED_EVIDENCE_ANCHOR_CATALOG_STATUS = (
    "reviewed_claim_surfaces_bound_to_current_evidence_items"
)


class ReviewedEvidenceAnchorError(ValueError):
    """Fail-closed error at the reviewed source-anchor boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReviewedEvidenceAnchorError(code)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReviewedEvidenceAnchorCatalog:
    case_pack_bindings: Mapping[str, Mapping[str, str]]
    entries: tuple[Mapping[str, Any], ...]
    catalog_digest: str

    def by_target(self) -> dict[tuple[str, str], Mapping[str, Any]]:
        return {
            (str(row["case_key"]), str(row["target_id"])): row
            for row in self.entries
        }


def load_reviewed_evidence_anchor_catalog(
    payload: Mapping[str, Any],
) -> ReviewedEvidenceAnchorCatalog:
    """Load an immutable catalog of reviewer-selected source-text anchors.

    An anchor is a verbatim substring of the already-bound source material. It
    does not promote new Evidence or replace a reviewer decision. Its sole job
    is to prevent a generic document-prefix projection from hiding the exact
    source surface that a reviewed claim was based on.
    """

    expected = {
        "schema_version",
        "status",
        "case_pack_bindings",
        "entries",
        "authority",
        "known_boundary",
        "catalog_digest",
    }
    _require(set(payload) == expected, "reviewed_anchor_catalog_fields_invalid")
    body = deepcopy(dict(payload))
    digest = str(body.pop("catalog_digest", ""))
    _require(
        payload.get("schema_version")
        == REVIEWED_EVIDENCE_ANCHOR_CATALOG_SCHEMA
        and payload.get("status")
        == REVIEWED_EVIDENCE_ANCHOR_CATALOG_STATUS
        and digest == canonical_digest(body),
        "reviewed_anchor_catalog_identity_invalid",
    )
    raw_bindings = payload.get("case_pack_bindings")
    _require(
        isinstance(raw_bindings, Mapping) and bool(raw_bindings),
        "reviewed_anchor_catalog_case_bindings_invalid",
    )
    bindings: dict[str, dict[str, str]] = {}
    for raw_case_key, raw in raw_bindings.items():
        case_key = str(raw_case_key).strip().upper()
        _require(
            isinstance(raw, Mapping)
            and set(raw) == {"artifact_digest", "pack_payload_digest"}
            and case_key
            and len(str(raw.get("artifact_digest") or "")) == 64
            and len(str(raw.get("pack_payload_digest") or "")) == 64,
            "reviewed_anchor_catalog_case_binding_invalid",
        )
        bindings[case_key] = {
            "artifact_digest": str(raw["artifact_digest"]),
            "pack_payload_digest": str(raw["pack_payload_digest"]),
        }

    raw_entries = payload.get("entries")
    _require(
        isinstance(raw_entries, list) and bool(raw_entries),
        "reviewed_anchor_catalog_entries_invalid",
    )
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    required_fields = {
        "case_key",
        "target_id",
        "source_record_id",
        "evidence_item_digest",
        "source_text_digest",
        "anchor_kind",
        "anchor_text",
        "anchor_start",
        "anchor_end",
        "anchor_digest",
        "review_status",
    }
    for raw in raw_entries:
        _require(
            isinstance(raw, Mapping) and set(raw) == required_fields,
            "reviewed_anchor_catalog_entry_fields_invalid",
        )
        row = deepcopy(dict(raw))
        case_key = str(row.get("case_key") or "").strip().upper()
        target_id = str(row.get("target_id") or "").strip()
        source_record_id = str(row.get("source_record_id") or "").strip()
        anchor_text = str(row.get("anchor_text") or "")
        start = row.get("anchor_start")
        end = row.get("anchor_end")
        key = (case_key, target_id)
        _require(
            case_key in bindings
            and target_id
            and source_record_id
            and key not in seen
            and len(str(row.get("evidence_item_digest") or "")) == 64
            and len(str(row.get("source_text_digest") or "")) == 64
            and row.get("anchor_kind")
            in {
                "structured_claim_text",
                "reviewed_current_document_passage",
            }
            and 24 <= len(anchor_text) <= 1600
            and type(start) is int
            and type(end) is int
            and 0 <= start < end
            and end - start == len(anchor_text)
            and row.get("anchor_digest") == _sha256_text(anchor_text)
            and row.get("review_status") == "reviewed_exact_source_surface",
            "reviewed_anchor_catalog_entry_invalid",
        )
        seen.add(key)
        row["case_key"] = case_key
        entries.append(row)

    authority = payload.get("authority")
    _require(
        isinstance(authority, Mapping)
        and dict(authority)
        == {
            "anchor_is_verbatim_source_substring": True,
            "anchor_is_not_new_evidence": True,
            "reviewer_business_meaning_is_not_source_text": True,
            "generic_prefix_may_not_replace_claim_anchor": True,
            "claim_anchor_binding_fails_closed": True,
            "model_or_network_calls": 0,
        }
        and str(payload.get("known_boundary") or "").strip(),
        "reviewed_anchor_catalog_authority_invalid",
    )
    return ReviewedEvidenceAnchorCatalog(
        case_pack_bindings=bindings,
        entries=tuple(entries),
        catalog_digest=digest,
    )


def validate_anchor_catalog_pack_binding(
    catalog: ReviewedEvidenceAnchorCatalog,
    *,
    case_key: str,
    artifact_digest: str,
    pack_payload_digest: str,
) -> None:
    normalized = str(case_key).strip().upper()
    binding = catalog.case_pack_bindings.get(normalized)
    _require(
        binding is not None
        and binding["artifact_digest"] == str(artifact_digest)
        and binding["pack_payload_digest"] == str(pack_payload_digest),
        "reviewed_anchor_catalog_pack_binding_drift",
    )


def project_reviewed_claim_anchor(
    *,
    catalog: ReviewedEvidenceAnchorCatalog,
    item: Mapping[str, Any],
    source: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the exact source anchor for one reviewed claim item."""

    case_key = str(item.get("case_key") or "").strip().upper()
    target_id = str(item.get("target_id") or "").strip()
    row = catalog.by_target().get((case_key, target_id))
    _require(row is not None, "reviewed_claim_anchor_missing")
    source_text = str(source.get("source_text") or "")
    start = int(row["anchor_start"])
    end = int(row["anchor_end"])
    _require(
        str(item.get("object_type") or "") == "claim"
        and str(item.get("source_record_id") or "")
        == str(row["source_record_id"])
        and str(item.get("evidence_item_digest") or "")
        == str(row["evidence_item_digest"])
        and str(source.get("source_text_digest") or "")
        == str(row["source_text_digest"])
        and end <= len(source_text)
        and source_text[start:end] == str(row["anchor_text"])
        and _sha256_text(source_text[start:end]) == str(row["anchor_digest"]),
        "reviewed_claim_anchor_binding_drift",
    )
    return {
        "reviewed_source_excerpt": str(row["anchor_text"]),
        "excerpt_truncated": len(source_text) != len(row["anchor_text"]),
        "excerpt_projection_kind": "reviewed_claim_anchor",
        "reviewed_anchor_bound": True,
        "reviewed_anchor_start": start,
        "reviewed_anchor_end": end,
        "reviewed_anchor_digest": str(row["anchor_digest"]),
        "reviewed_anchor_catalog_digest": catalog.catalog_digest,
    }


def compile_reviewed_evidence_anchor_catalog(
    *,
    case_pack_bindings: Mapping[str, Mapping[str, str]],
    entries: Sequence[Mapping[str, Any]],
    known_boundary: str,
) -> dict[str, Any]:
    body = {
        "schema_version": REVIEWED_EVIDENCE_ANCHOR_CATALOG_SCHEMA,
        "status": REVIEWED_EVIDENCE_ANCHOR_CATALOG_STATUS,
        "case_pack_bindings": deepcopy(dict(case_pack_bindings)),
        "entries": [deepcopy(dict(row)) for row in entries],
        "authority": {
            "anchor_is_verbatim_source_substring": True,
            "anchor_is_not_new_evidence": True,
            "reviewer_business_meaning_is_not_source_text": True,
            "generic_prefix_may_not_replace_claim_anchor": True,
            "claim_anchor_binding_fails_closed": True,
            "model_or_network_calls": 0,
        },
        "known_boundary": str(known_boundary),
    }
    payload = {**body, "catalog_digest": canonical_digest(body)}
    load_reviewed_evidence_anchor_catalog(payload)
    return payload


__all__ = [
    "REVIEWED_EVIDENCE_ANCHOR_CATALOG_SCHEMA",
    "ReviewedEvidenceAnchorCatalog",
    "ReviewedEvidenceAnchorError",
    "compile_reviewed_evidence_anchor_catalog",
    "load_reviewed_evidence_anchor_catalog",
    "project_reviewed_claim_anchor",
    "validate_anchor_catalog_pack_binding",
]
