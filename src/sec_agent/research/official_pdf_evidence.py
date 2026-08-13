from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Mapping, Sequence

from sec_agent.research.reviewed_evidence_pack import canonical_digest


OFFICIAL_PDF_EVIDENCE_POLICY_SCHEMA = (
    "fin_ia_official_pdf_evidence_gate_policy_v1_0"
)
OFFICIAL_PDF_EVIDENCE_RESULT_SCHEMA = (
    "fin_ia_official_pdf_evidence_gate_result_v1_0"
)
OFFICIAL_PDF_EVIDENCE_BUNDLE_RESULT_SCHEMA = (
    "fin_ia_official_pdf_evidence_gate_bundle_result_v1_0"
)

_ALLOWED_EVIDENCE_ROLE_BY_DISPOSITION = {
    "accepted_bounded_context_evidence": "counterparty_or_ecosystem_readthrough",
    "accepted_direct_source_evidence": "issuer_direct_source",
}


class OfficialPdfEvidenceError(ValueError):
    """An official PDF candidate could not be promoted under a bound policy."""


def validate_official_pdf_evidence_policy(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    value.setdefault("disposition", "accepted_bounded_context_evidence")
    value.setdefault(
        "evidence_role", "counterparty_or_ecosystem_readthrough"
    )
    value.setdefault(
        "numeric_use_boundary",
        (
            "Only source-visible exact values may be quoted; derived arithmetic "
            "requires a separate deterministic numeric program."
        ),
    )
    value.setdefault("gap_ids_satisfied", [])
    raw_bindings = value.get("slot_bindings")
    if raw_bindings is None:
        raw_bindings = [
            {
                "slot_id": value.get("slot_id"),
                "facet_ids": [value.get("facet_id")],
                "qualification_id": value.get("qualification_id"),
                "business_meaning_zh": value.get("business_meaning_zh"),
                "claim_boundary_zh": value.get("claim_boundary_zh"),
            }
        ]
    bindings = [deepcopy(dict(row)) for row in raw_bindings]
    value["slot_bindings"] = bindings
    anchors = list(value.get("required_anchor_groups") or ())
    disposition = str(value.get("disposition") or "")
    if not (
        value.get("schema_version") == OFFICIAL_PDF_EVIDENCE_POLICY_SCHEMA
        and value.get("status") == "active_bounded_official_pdf_evidence_gate"
        and str(value.get("policy_id") or "")
        and str(value.get("route_id") or "")
        and str(value.get("consumer_case_key") or "")
        and str(value.get("evidence_owner_ticker") or "")
        and bindings
        and all(_valid_slot_binding(binding) for binding in bindings)
        and isinstance(value.get("allowed_page_numbers"), list)
        and value["allowed_page_numbers"]
        and len(value["allowed_page_numbers"])
        == len(set(value["allowed_page_numbers"]))
        and all(isinstance(page, int) and page > 0 for page in value["allowed_page_numbers"])
        and 1 <= int(value.get("max_accepted_pages") or 0) <= 10
        and 100 <= int(value.get("max_excerpt_characters") or 0) <= 4000
        and anchors
        and all(_valid_anchor_group(group) for group in anchors)
        and isinstance(value.get("relationship_directions"), list)
        and value["relationship_directions"]
        and all(str(direction).strip() for direction in value["relationship_directions"])
        and str(value.get("license_scope") or "")
        and disposition in _ALLOWED_EVIDENCE_ROLE_BY_DISPOSITION
        and value.get("evidence_role")
        == _ALLOWED_EVIDENCE_ROLE_BY_DISPOSITION[disposition]
        and str(value.get("numeric_use_boundary") or "")
        and isinstance(value.get("gap_ids_satisfied"), list)
        and len(value["gap_ids_satisfied"])
        == len(set(value["gap_ids_satisfied"]))
        and all(str(gap_id).strip() for gap_id in value["gap_ids_satisfied"])
        and value.get("causal_attribution_authorized") is False
        and value.get("redistributable") is False
    ):
        raise OfficialPdfEvidenceError("official_pdf_evidence_policy_invalid")
    if disposition == "accepted_direct_source_evidence" and not (
        str(value["evidence_owner_ticker"]).upper()
        == str(value["consumer_case_key"]).upper()
        and "subject_self_disclosure" in value["relationship_directions"]
    ):
        raise OfficialPdfEvidenceError("official_pdf_evidence_policy_invalid")
    value["slot_id"] = str(bindings[0]["slot_id"])
    value["facet_id"] = str(bindings[0]["facet_ids"][0])
    return value


def evaluate_official_pdf_evidence(
    *,
    parent: Mapping[str, Any],
    children: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    research_as_of: str,
) -> dict[str, Any]:
    value = validate_official_pdf_evidence_policy(policy)
    owner = str(value["evidence_owner_ticker"])
    if not (
        str(parent.get("ticker") or "") == owner
        and str(parent.get("route_id") or "") == str(value["route_id"])
        and str(parent.get("publication_date") or "") <= research_as_of
        and str(parent.get("license_scope") or "") == str(value["license_scope"])
        and parent.get("redistributable") is False
    ):
        raise OfficialPdfEvidenceError("official_pdf_evidence_identity_invalid")

    allowed_pages = set(value["allowed_page_numbers"])
    qualifying: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for child in children:
        metadata = dict(child.get("metadata") or {})
        page_number = int(metadata.get("page_number") or 0)
        if (
            str(child.get("ticker") or "") != owner
            or str(metadata.get("route_id") or "") != str(value["route_id"])
            or page_number not in allowed_pages
        ):
            continue
        text = str(child.get("text") or "")
        match_text = _normalized_match_text(text)
        matched = [
            str(group["group_id"])
            for group in value["required_anchor_groups"]
            if any(
                _normalized_match_text(str(literal)) in match_text
                for literal in group["any_literals"]
            )
        ]
        if len(matched) != len(value["required_anchor_groups"]):
            rejected.append(
                {
                    "source_record_id": child.get("evidence_id"),
                    "page_number": page_number,
                    "rejection_code": "required_anchor_group_missing",
                    "matched_anchor_groups": matched,
                }
            )
            continue
        qualifying.append(
            {
                "child": dict(child),
                "page_number": page_number,
                "matched_anchor_groups": matched,
            }
        )
    qualifying.sort(key=lambda row: row["page_number"])
    qualifying = qualifying[: int(value["max_accepted_pages"])]
    if not qualifying:
        return {
            "schema_version": OFFICIAL_PDF_EVIDENCE_RESULT_SCHEMA,
            "status": "typed_gap_no_qualifying_official_pdf_evidence",
            "policy_id": value["policy_id"],
            "accepted_evidence_items": [],
            "source_materials": [],
            "rejected_items": rejected,
            "gap_satisfied": False,
            "candidate_is_not_evidence": True,
        }

    evidence_items: list[dict[str, Any]] = []
    source_materials: list[dict[str, Any]] = []
    for row in qualifying:
        child = row["child"]
        text = str(child["text"])
        excerpt = _bounded_excerpt(
            text,
            anchor_groups=value["required_anchor_groups"],
            maximum=int(value["max_excerpt_characters"]),
        )
        source_digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
        material_ref = f"source_material_{source_digest[:24]}"
        source_material = {
            "evidence_owner_ticker": owner,
            "license_scope": value["license_scope"],
            "material_ref": material_ref,
            "period_end": child.get("period_end"),
            "publication_date": child.get("publication_date"),
            "redistributable": False,
            "source_record_id": child.get("evidence_id"),
            "source_text": excerpt,
            "source_text_digest": source_digest,
            "source_tier": child.get("source_tier"),
            "source_type": child.get("source_type"),
            "source_url": child.get("source_url"),
            "page_number": row["page_number"],
            "raw_capture_sha256": (child.get("metadata") or {}).get(
                "source_capture_sha256"
            ),
        }
        target_id = f"{child['evidence_id']}::CLAIM::{source_digest[:12].upper()}"
        item_without_digest = {
            "case_key": value["consumer_case_key"],
            "causal_attribution_authorized": False,
            "disposition": value["disposition"],
            "evidence_role": value["evidence_role"],
            "numeric_use_boundary": value["numeric_use_boundary"],
            "object_type": "claim",
            "publication_date": child.get("publication_date"),
            "relationship_directions": list(value["relationship_directions"]),
            "research_as_of": research_as_of,
            "slot_bindings": deepcopy(value["slot_bindings"]),
            "source_content_digest": source_digest,
            "source_material_ref": material_ref,
            "source_record_id": child.get("evidence_id"),
            "source_reporting_period_end": child.get("period_end"),
            "target_id": target_id,
            "writer_citable": True,
        }
        evidence_items.append(
            {
                **item_without_digest,
                "evidence_item_digest": canonical_digest(item_without_digest),
            }
        )
        source_materials.append(source_material)

    unsigned = {
        "schema_version": OFFICIAL_PDF_EVIDENCE_RESULT_SCHEMA,
        "status": "official_pdf_evidence_gate_passed",
        "policy_id": value["policy_id"],
        "consumer_case_key": value["consumer_case_key"],
        "evidence_owner_ticker": owner,
        "slot_id": value["slot_id"],
        "facet_id": value["facet_id"],
        "slot_ids": sorted(
            {str(binding["slot_id"]) for binding in value["slot_bindings"]}
        ),
        "facet_ids": sorted(
            {
                str(facet)
                for binding in value["slot_bindings"]
                for facet in binding["facet_ids"]
            }
        ),
        "accepted_evidence_items": evidence_items,
        "source_materials": source_materials,
        "rejected_items": rejected,
        "evidence_qualified": True,
        "gap_ids_satisfied": list(value["gap_ids_satisfied"]),
        "gap_satisfied": bool(value["gap_ids_satisfied"]),
        "candidate_is_not_evidence": False,
        "causal_attribution_authorized": False,
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def combine_official_pdf_evidence_results(
    results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Combine independently gated fragments from one consumer case.

    A document can contain several financially distinct fragments. Each stays
    policy-bound and independently auditable; the bundle only provides the
    atomic input surface needed by a single Pack successor.
    """

    rows = [deepcopy(dict(result)) for result in results]
    if not rows or any(
        row.get("schema_version") != OFFICIAL_PDF_EVIDENCE_RESULT_SCHEMA
        or row.get("status") != "official_pdf_evidence_gate_passed"
        or row.get("evidence_qualified") is not True
        for row in rows
    ):
        raise OfficialPdfEvidenceError("official_pdf_evidence_bundle_input_invalid")
    case_keys = {str(row.get("consumer_case_key") or "") for row in rows}
    if len(case_keys) != 1 or not next(iter(case_keys)):
        raise OfficialPdfEvidenceError("official_pdf_evidence_bundle_case_mismatch")

    evidence_items = [
        deepcopy(dict(item))
        for row in rows
        for item in row.get("accepted_evidence_items") or ()
    ]
    source_materials = [
        deepcopy(dict(item))
        for row in rows
        for item in row.get("source_materials") or ()
    ]
    target_ids = [str(item.get("target_id") or "") for item in evidence_items]
    material_refs = [
        str(item.get("material_ref") or "") for item in source_materials
    ]
    if (
        not evidence_items
        or len(target_ids) != len(set(target_ids))
        or len(material_refs) != len(set(material_refs))
    ):
        raise OfficialPdfEvidenceError("official_pdf_evidence_bundle_collision")

    unsigned = {
        "schema_version": OFFICIAL_PDF_EVIDENCE_BUNDLE_RESULT_SCHEMA,
        "status": "official_pdf_evidence_gate_bundle_passed",
        "consumer_case_key": next(iter(case_keys)),
        "evidence_owner_tickers": sorted(
            {str(row.get("evidence_owner_ticker") or "") for row in rows}
        ),
        "policy_ids": [str(row["policy_id"]) for row in rows],
        "policy_result_digests": [str(row["result_digest"]) for row in rows],
        "accepted_evidence_items": evidence_items,
        "source_materials": source_materials,
        "rejected_items": [
            deepcopy(dict(item))
            for row in rows
            for item in row.get("rejected_items") or ()
        ],
        "slot_ids": sorted(
            {
                str(binding.get("slot_id") or "")
                for item in evidence_items
                for binding in item.get("slot_bindings") or ()
            }
        ),
        "facet_ids": sorted(
            {
                str(facet)
                for item in evidence_items
                for binding in item.get("slot_bindings") or ()
                for facet in binding.get("facet_ids") or ()
            }
        ),
        "evidence_qualified": True,
        "gap_ids_satisfied": sorted(
            {
                str(gap_id)
                for row in rows
                for gap_id in row.get("gap_ids_satisfied") or ()
            }
        ),
        "gap_satisfied": any(
            row.get("gap_ids_satisfied") for row in rows
        ),
        "candidate_is_not_evidence": False,
        "causal_attribution_authorized": False,
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def build_reviewed_pack_successor(
    *,
    predecessor: Mapping[str, Any],
    evidence_result: Mapping[str, Any],
    gap_ids_satisfied: Sequence[str],
    successor_lineage: Mapping[str, Any],
) -> dict[str, Any]:
    if not (
        predecessor.get("case_key") == evidence_result.get("consumer_case_key")
        and evidence_result.get("status")
        in {
            "official_pdf_evidence_gate_passed",
            "official_pdf_evidence_gate_bundle_passed",
        }
        and (
            evidence_result.get("evidence_qualified") is True
            or evidence_result.get("gap_satisfied") is True
        )
        and evidence_result.get("accepted_evidence_items")
    ):
        raise OfficialPdfEvidenceError("reviewed_pack_successor_input_invalid")
    gaps = [dict(row) for row in predecessor.get("residual_gaps") or ()]
    existing_gap_ids = {str(row.get("gap_id") or "") for row in gaps}
    requested = {str(value) for value in gap_ids_satisfied}
    if not requested <= existing_gap_ids:
        raise OfficialPdfEvidenceError("reviewed_pack_successor_gap_unknown")
    qualified_gap_ids = {
        str(value) for value in evidence_result.get("gap_ids_satisfied") or ()
    }
    if not requested <= qualified_gap_ids:
        raise OfficialPdfEvidenceError(
            "reviewed_pack_successor_gap_not_qualified"
        )

    body = deepcopy(dict(predecessor))
    body.pop("pack_payload_digest", None)
    existing_targets = {
        str(row.get("target_id") or "") for row in body.get("evidence_items") or ()
    }
    additions = [dict(row) for row in evidence_result["accepted_evidence_items"]]
    if any(str(row.get("target_id") or "") in existing_targets for row in additions):
        raise OfficialPdfEvidenceError("reviewed_pack_successor_target_collision")
    existing_materials = {
        str(row.get("material_ref") or "") for row in body.get("source_materials") or ()
    }
    materials = [dict(row) for row in evidence_result["source_materials"]]
    if any(str(row.get("material_ref") or "") in existing_materials for row in materials):
        raise OfficialPdfEvidenceError("reviewed_pack_successor_material_collision")

    body["evidence_items"] = list(body["evidence_items"]) + additions
    body["source_materials"] = list(body["source_materials"]) + materials
    body["residual_gaps"] = [
        row for row in gaps if str(row.get("gap_id") or "") not in requested
    ]
    counts = dict(body.get("observed_counts") or {})
    counts["accepted_evidence_items"] = len(body["evidence_items"])
    counts["bounded_context_items"] = sum(
        row.get("disposition") == "accepted_bounded_context_evidence"
        for row in body["evidence_items"]
    )
    counts["direct_evidence_items"] = sum(
        row.get("disposition") == "accepted_direct_source_evidence"
        for row in body["evidence_items"]
    )
    counts["residual_gaps"] = len(body["residual_gaps"])
    counts["source_materials"] = len(body["source_materials"])
    body["observed_counts"] = counts
    body["content_gate_basis"] = (
        "reviewed_local_predecessor_plus_digest_bound_official_pdf_evidence_gate"
    )
    body["successor_lineage"] = deepcopy(dict(successor_lineage))
    if requested:
        gap_statement = (
            "This successor closes only the explicitly declared gap IDs: "
            + ", ".join(sorted(requested))
            + ". "
        )
    else:
        gap_statement = (
            "This successor adds qualified official-PDF Evidence without closing "
            "any residual gap. "
        )
    body["known_boundary"] = (
        gap_statement
        + "It does not establish undeclared attribution, complete research, "
        "NumericFact authority, S3 model readiness or product release."
    )
    return {**body, "pack_payload_digest": canonical_digest(body)}


def _valid_anchor_group(value: Any) -> bool:
    return bool(
        isinstance(value, Mapping)
        and str(value.get("group_id") or "")
        and isinstance(value.get("any_literals"), list)
        and value["any_literals"]
        and all(str(literal).strip() for literal in value["any_literals"])
    )


def _valid_slot_binding(value: Any) -> bool:
    return bool(
        isinstance(value, Mapping)
        and str(value.get("slot_id") or "")
        and isinstance(value.get("facet_ids"), list)
        and value["facet_ids"]
        and all(str(facet).strip() for facet in value["facet_ids"])
        and str(value.get("qualification_id") or "")
        and str(value.get("business_meaning_zh") or "")
        and str(value.get("claim_boundary_zh") or "")
    )


def _bounded_excerpt(
    text: str,
    *,
    anchor_groups: Sequence[Mapping[str, Any]],
    maximum: int,
) -> str:
    normalized = " ".join(text.split())
    positions: list[int] = []
    folded = normalized.casefold()
    for group in anchor_groups:
        hits = [
            folded.find(str(literal).casefold())
            for literal in group["any_literals"]
        ]
        hits = [hit for hit in hits if hit >= 0]
        if hits:
            positions.append(min(hits))
    if not positions:
        return normalized[:maximum]
    center = sum(positions) // len(positions)
    start = max(0, center - maximum // 2)
    end = min(len(normalized), start + maximum)
    start = max(0, end - maximum)
    return normalized[start:end].strip()


def _normalized_match_text(value: str) -> str:
    return " ".join(str(value).split()).casefold()


__all__ = [
    "OfficialPdfEvidenceError",
    "build_reviewed_pack_successor",
    "combine_official_pdf_evidence_results",
    "evaluate_official_pdf_evidence",
    "validate_official_pdf_evidence_policy",
]
