from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .evidence_role import evaluate_evidence_role
from .query_plan import canonical_digest
from sec_agent.research.reviewed_evidence_pack import (
    validate_reviewed_evidence_pack,
)


SUPPLEMENT_RESULT_SCHEMA_VERSION = "fin_ia_s1_supplement_vertical_result_v1_0"
CAPTURE_RECEIPT_SCHEMA_VERSION = "fin_ia_s1_capture_bound_object_receipt_v1_0"
GAP_RECEIPT_SCHEMA_VERSION = "fin_ia_s1_gap_eligibility_receipt_v1_0"
WORKBENCH_SCHEMA_VERSION = "fin_ia_s1_supplement_workbench_projection_v1_0"
SUPPLEMENT_SUMMARY_SCHEMA_VERSION = (
    "fin_ia_s1_vs4_dell_supplement_vertical_summary_v1_0"
)


class SupplementVerticalError(ValueError):
    """A bounded S1 supplement violated evidence or lineage authority."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SupplementVerticalError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalized(value: object) -> str:
    return " ".join(str(value or "").split())


def _as_date(value: object, code: str) -> date:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise SupplementVerticalError(code) from exc


def _legacy_source_ids(source_record: Mapping[str, Any]) -> set[str]:
    metadata = _mapping(
        source_record.get("metadata"), "supplement_source_record_metadata_missing"
    )
    return {
        str(source_record.get("evidence_id") or ""),
        *(
            str(value)
            for value in metadata.get("legacy_source_record_ids") or ()
            if str(value)
        ),
    }


def verify_capture_bound_object(
    *,
    compiled_object: Mapping[str, Any],
    source_record: Mapping[str, Any],
    parent_document: Mapping[str, Any],
    research_as_of: str,
    capture_resolver: Callable[[str], Path],
) -> dict[str, Any]:
    """Prove that a ranked claim is backed by an immutable source capture."""

    base = _mapping(
        compiled_object.get("base_object_view"),
        "supplement_compiled_object_base_missing",
    )
    metadata = _mapping(
        source_record.get("metadata"), "supplement_source_record_metadata_missing"
    )
    object_id = str(compiled_object.get("compiled_object_id") or "")
    source_record_id = str(source_record.get("evidence_id") or "")
    parent_id = str(parent_document.get("document_id") or "")
    _require(object_id.startswith("COBJ::"), "supplement_compiled_object_id_invalid")
    _require(
        compiled_object.get("candidate_not_evidence") is True
        and compiled_object.get("evidence_promoted") is False
        and compiled_object.get("numeric_authority") is False,
        "supplement_candidate_authority_boundary_invalid",
    )
    _require(
        str(base.get("source_record_id") or "") == source_record_id
        and canonical_digest(dict(source_record))
        == str(base.get("source_record_digest") or ""),
        "supplement_source_record_binding_invalid",
    )
    _require(
        str(base.get("parent_document_id") or "") == parent_id
        and str(metadata.get("parent_document_id") or "") == parent_id
        and canonical_digest(dict(parent_document))
        == str(base.get("parent_document_digest") or ""),
        "supplement_parent_document_binding_invalid",
    )
    _require(
        parent_document.get("lineage_state") == "immutable_capture_bound",
        "supplement_parent_not_immutable_capture_bound",
    )
    for key in ("ticker", "source_type", "publication_date", "period_end"):
        _require(
            str(base.get(key) or "") == str(source_record.get(key) or "")
            and str(source_record.get(key) or "")
            == str(parent_document.get(key) or ""),
            f"supplement_{key}_binding_invalid",
        )
    _require(
        _as_date(base.get("publication_date"), "supplement_publication_date_invalid")
        <= _as_date(research_as_of, "supplement_research_as_of_invalid"),
        "supplement_source_after_research_as_of",
    )
    surface = str(base.get("surface_text") or "")
    _require(
        surface
        and canonical_digest(surface) == str(base.get("surface_digest") or "")
        and _normalized(surface) in _normalized(source_record.get("text")),
        "supplement_claim_surface_not_bound_to_source_record",
    )
    capture_ref = str(
        metadata.get("source_capture_ref")
        or parent_document.get("capture_ref")
        or ""
    )
    capture_sha256 = str(
        metadata.get("source_capture_sha256")
        or parent_document.get("capture_sha256")
        or ""
    )
    _require(
        capture_ref
        and capture_sha256
        and capture_sha256 == str(parent_document.get("capture_sha256") or ""),
        "supplement_capture_binding_missing",
    )
    capture_path = capture_resolver(capture_ref)
    _require(capture_path.is_file(), "supplement_capture_file_missing")
    _require(
        _file_sha256(capture_path) == capture_sha256,
        "supplement_capture_sha256_drift",
    )
    body = {
        "schema_version": CAPTURE_RECEIPT_SCHEMA_VERSION,
        "status": "capture_bound_object_verified",
        "compiled_object_id": object_id,
        "source_record_id": source_record_id,
        "source_record_digest": str(base.get("source_record_digest") or ""),
        "parent_document_id": parent_id,
        "parent_document_digest": str(base.get("parent_document_digest") or ""),
        "capture_ref": capture_ref,
        "capture_sha256": capture_sha256,
        "evidence_owner_ticker": str(base.get("ticker") or "").upper(),
        "source_type": base.get("source_type"),
        "publication_date": base.get("publication_date"),
        "period_end": base.get("period_end"),
        "surface_digest": base.get("surface_digest"),
        "checks": {
            "candidate_not_evidence": True,
            "source_record_digest_matched": True,
            "parent_document_digest_matched": True,
            "immutable_capture_sha256_matched": True,
            "identity_period_and_source_matched": True,
            "claim_surface_bound_to_source_record": True,
            "publication_not_after_research_as_of": True,
            "numeric_authority": False,
        },
    }
    return {**body, "receipt_digest": canonical_digest(body)}


def _build_evidence_pair(
    *,
    case_key: str,
    research_as_of: str,
    compiled_object: Mapping[str, Any],
    source_record: Mapping[str, Any],
    capture_receipt: Mapping[str, Any],
    evidence_spec: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = _mapping(
        compiled_object.get("base_object_view"),
        "supplement_compiled_object_base_missing",
    )
    surface = str(base.get("surface_text") or "")
    source_content_digest = _text_sha256(surface)
    material_ref = f"source_material_{source_content_digest[:24]}"
    bounded_context = (
        str(base.get("ticker") or "").upper() != case_key
        or evidence_spec.get("disposition") == "accepted_bounded_context_evidence"
    )
    disposition = (
        "accepted_bounded_context_evidence"
        if bounded_context
        else "accepted_direct_source_evidence"
    )
    evidence_role = (
        "counterparty_or_ecosystem_readthrough"
        if bounded_context
        else "issuer_direct_source"
    )
    slot_bindings = [
        deepcopy(dict(value)) for value in evidence_spec.get("slot_bindings") or ()
    ]
    _require(slot_bindings, "supplement_slot_bindings_missing")
    material = {
        "material_ref": material_ref,
        "source_record_id": source_record.get("evidence_id"),
        "source_text": surface,
        "source_text_digest": source_content_digest,
        "source_url": source_record.get("source_url"),
        "source_type": source_record.get("source_type"),
        "source_tier": source_record.get("source_tier"),
        "evidence_owner_ticker": str(source_record.get("ticker") or "").upper(),
        "publication_date": source_record.get("publication_date"),
        "period_end": source_record.get("period_end"),
        "license_scope": str(source_record.get("license_scope") or ""),
        "redistributable": bool(source_record.get("redistributable") is True),
        "capture_ref": capture_receipt.get("capture_ref"),
        "capture_sha256": capture_receipt.get("capture_sha256"),
        "compiled_object_id": compiled_object.get("compiled_object_id"),
    }
    target_id = (
        f"{source_record.get('evidence_id')}::CLAIM::"
        f"{str(base.get('surface_digest') or '')[:12].upper()}"
    )
    body = {
        "case_key": case_key,
        "target_id": target_id,
        "object_type": "claim",
        "source_record_id": source_record.get("evidence_id"),
        "source_material_ref": material_ref,
        "source_content_digest": source_content_digest,
        "publication_date": source_record.get("publication_date"),
        "source_reporting_period_end": source_record.get("period_end"),
        "research_as_of": research_as_of,
        "disposition": disposition,
        "evidence_role": evidence_role,
        "relationship_directions": list(
            evidence_spec.get("relationship_directions") or ()
        ),
        "slot_bindings": slot_bindings,
        "writer_citable": True,
        "causal_attribution_authorized": False,
        "numeric_use_boundary": (
            "Only source-visible exact values may be quoted; derived arithmetic "
            "requires a separate deterministic numeric program."
        ),
        "compiled_object_id": compiled_object.get("compiled_object_id"),
        "source_record_digest": capture_receipt.get("source_record_digest"),
        "parent_document_digest": capture_receipt.get("parent_document_digest"),
        "capture_receipt_digest": capture_receipt.get("receipt_digest"),
    }
    return (
        {**body, "evidence_item_digest": canonical_digest(body)},
        material,
    )


def _object_evidence_matches(
    *,
    compiled_object: Mapping[str, Any],
    source_record: Mapping[str, Any],
    item: Mapping[str, Any],
    material: Mapping[str, Any],
) -> bool:
    base = _mapping(
        compiled_object.get("base_object_view"),
        "supplement_compiled_object_base_missing",
    )
    source_ids = _legacy_source_ids(source_record)
    return bool(
        str(item.get("source_record_id") or "") in source_ids
        and _normalized(base.get("surface_text"))
        in _normalized(material.get("source_text"))
    )


def build_capture_bound_pack_successor(
    *,
    predecessor: Mapping[str, Any],
    policy: Mapping[str, Any],
    ranked_candidates_by_atom: Mapping[str, Sequence[str]],
    compiled_objects_by_id: Mapping[str, Mapping[str, Any]],
    source_records_by_id: Mapping[str, Mapping[str, Any]],
    parent_documents_by_id: Mapping[str, Mapping[str, Any]],
    capture_resolver: Callable[[str], Path],
    recorded_at: str,
) -> dict[str, Any]:
    """Adjudicate a bounded supplement and materialize an immutable Pack successor."""

    case_key = str(policy.get("case_key") or "").upper()
    research_as_of = str(policy.get("research_as_of") or "")
    _require(
        case_key
        and case_key == str(predecessor.get("case_key") or "").upper()
        and research_as_of,
        "supplement_case_or_as_of_invalid",
    )
    reviews = sorted(
        (dict(value) for value in policy.get("review_relations") or ()),
        key=lambda row: (
            str(row.get("atom_id") or ""),
            str(row.get("compiled_object_id") or ""),
        ),
    )
    _require(reviews, "supplement_review_relations_missing")
    review_keys = [
        (str(row.get("atom_id") or ""), str(row.get("compiled_object_id") or ""))
        for row in reviews
    ]
    _require(
        all(all(value) for value in review_keys)
        and len(review_keys) == len(set(review_keys)),
        "supplement_review_relation_identity_invalid",
    )
    retired_digests = {
        str(value) for value in policy.get("retire_evidence_item_digests") or ()
    }
    predecessor_items = [
        deepcopy(dict(value)) for value in predecessor.get("evidence_items") or ()
    ]
    predecessor_materials = [
        deepcopy(dict(value)) for value in predecessor.get("source_materials") or ()
    ]
    predecessor_by_digest = {
        str(row.get("evidence_item_digest") or ""): row for row in predecessor_items
    }
    _require(
        retired_digests <= set(predecessor_by_digest),
        "supplement_retired_evidence_unknown",
    )
    items = [
        row
        for row in predecessor_items
        if str(row.get("evidence_item_digest") or "") not in retired_digests
    ]
    retired_material_refs = {
        str(predecessor_by_digest[digest].get("source_material_ref") or "")
        for digest in retired_digests
    }
    live_material_refs = {
        str(row.get("source_material_ref") or "") for row in items
    }
    materials = [
        row
        for row in predecessor_materials
        if str(row.get("material_ref") or "") not in (
            retired_material_refs - live_material_refs
        )
    ]
    capture_receipts: list[dict[str, Any]] = []
    review_receipts: list[dict[str, Any]] = []
    additions: list[dict[str, Any]] = []
    material_additions: list[dict[str, Any]] = []

    # Verify every reviewed relation first.  Only positive, explicitly ranked,
    # capture-bound objects may create Evidence; hard negatives stay receipts.
    for review in reviews:
        atom_id = str(review.get("atom_id") or "")
        object_id = str(review.get("compiled_object_id") or "")
        judgement = str(review.get("judgement") or "")
        action = str(review.get("evidence_action") or "")
        _require(
            judgement in {"positive", "hard_negative"},
            "supplement_review_judgement_invalid",
        )
        ranked_ids = tuple(str(value) for value in ranked_candidates_by_atom.get(atom_id, ()))
        _require(ranked_ids, "supplement_ranked_atom_missing")
        in_candidate_pool = object_id in ranked_ids
        compiled_object = compiled_objects_by_id.get(object_id)
        _require(compiled_object is not None, "supplement_compiled_object_missing")
        base = _mapping(
            compiled_object.get("base_object_view"),
            "supplement_compiled_object_base_missing",
        )
        source_record = source_records_by_id.get(str(base.get("source_record_id") or ""))
        _require(source_record is not None, "supplement_source_record_missing")
        metadata = _mapping(
            source_record.get("metadata"), "supplement_source_record_metadata_missing"
        )
        parent = parent_documents_by_id.get(str(metadata.get("parent_document_id") or ""))
        _require(parent is not None, "supplement_parent_document_missing")
        capture = verify_capture_bound_object(
            compiled_object=compiled_object,
            source_record=source_record,
            parent_document=parent,
            research_as_of=research_as_of,
            capture_resolver=capture_resolver,
        )
        capture_receipts.append(capture)
        evidence_spec = _mapping(
            review.get("evidence_spec") or {}, "supplement_evidence_spec_invalid"
        )
        role = evaluate_evidence_role(
            {
                **dict(base),
                "document_text": base.get("surface_text"),
                "object_kind": compiled_object.get("object_kind"),
            },
            slot_id=str(review.get("slot_id") or ""),
            facet_id=str(review.get("facet_id") or ""),
            subject_ticker=case_key,
            evidence_owner_ticker=str(base.get("ticker") or ""),
            relationship_direction=str(review.get("relationship_direction") or ""),
        )
        if judgement == "positive":
            _require(in_candidate_pool, "supplement_positive_not_in_candidate_pool")
            _require(
                role.compatibility == "compatible",
                "supplement_positive_evidence_role_incompatible",
            )
            _require(
                action in {"add_capture_bound_evidence", "reuse_reviewed_evidence"},
                "supplement_positive_action_invalid",
            )
            if action == "add_capture_bound_evidence":
                item, material = _build_evidence_pair(
                    case_key=case_key,
                    research_as_of=research_as_of,
                    compiled_object=compiled_object,
                    source_record=source_record,
                    capture_receipt=capture,
                    evidence_spec=evidence_spec,
                )
                additions.append(item)
                material_additions.append(material)
        else:
            _require(
                action == "reject_candidate",
                "supplement_hard_negative_action_invalid",
            )
        receipt_body = {
            "atom_id": atom_id,
            "compiled_object_id": object_id,
            "judgement": judgement,
            "evidence_action": action,
            "in_candidate_pool": in_candidate_pool,
            "candidate_rank": (
                ranked_ids.index(object_id) + 1 if in_candidate_pool else None
            ),
            "evidence_role": role.as_dict(),
            "capture_receipt_digest": capture.get("receipt_digest"),
            "candidate_text_promoted": False,
            "numeric_authority": False,
        }
        review_receipts.append(
            {**receipt_body, "review_receipt_digest": canonical_digest(receipt_body)}
        )

    target_ids = {str(row.get("target_id") or "") for row in items}
    material_refs = {str(row.get("material_ref") or "") for row in materials}
    for item, material in zip(additions, material_additions, strict=True):
        _require(
            str(item.get("target_id") or "") not in target_ids,
            "supplement_evidence_target_collision",
        )
        _require(
            str(material.get("material_ref") or "") not in material_refs,
            "supplement_source_material_collision",
        )
        target_ids.add(str(item["target_id"]))
        material_refs.add(str(material["material_ref"]))
        items.append(item)
        materials.append(material)

    # Positive reuse must resolve only after all successor additions exist.
    material_by_ref = {
        str(row.get("material_ref") or ""): row for row in materials
    }
    for review in reviews:
        if not (
            review.get("judgement") == "positive"
            and review.get("evidence_action") == "reuse_reviewed_evidence"
        ):
            continue
        object_id = str(review.get("compiled_object_id") or "")
        compiled_object = compiled_objects_by_id[object_id]
        base = _mapping(
            compiled_object.get("base_object_view"),
            "supplement_compiled_object_base_missing",
        )
        source_record = source_records_by_id[str(base.get("source_record_id") or "")]
        matches = [
            item
            for item in items
            if (material := material_by_ref.get(str(item.get("source_material_ref") or "")))
            is not None
            and _object_evidence_matches(
                compiled_object=compiled_object,
                source_record=source_record,
                item=item,
                material=material,
            )
        ]
        _require(matches, "supplement_reused_evidence_not_capture_bound_to_object")

    gaps = [deepcopy(dict(value)) for value in predecessor.get("residual_gaps") or ()]
    gaps_by_id = {str(row.get("gap_id") or ""): row for row in gaps}
    gap_change_receipts: list[dict[str, Any]] = []
    for update in policy.get("gap_updates") or ():
        update = _mapping(update, "supplement_gap_update_invalid")
        gap_id = str(update.get("gap_id") or "")
        _require(gap_id in gaps_by_id, "supplement_gap_update_unknown")
        _require(update.get("action") == "narrow", "supplement_gap_action_invalid")
        before = deepcopy(gaps_by_id[gap_id])
        replacement = deepcopy(dict(update.get("replacement") or {}))
        _require(
            replacement.get("gap_id") == gap_id
            and replacement.get("gap_code")
            and replacement.get("slot_id"),
            "supplement_gap_replacement_invalid",
        )
        gaps_by_id[gap_id] = replacement
        receipt_body = {
            "schema_version": GAP_RECEIPT_SCHEMA_VERSION,
            "gap_id": gap_id,
            "action": "narrow",
            "before": before,
            "after": replacement,
            "classification": str(update.get("classification") or ""),
            "eligible_as_blanket_public_information_absence": False,
            "route_checks": deepcopy(dict(update.get("route_checks") or {})),
            "known_boundary": str(update.get("known_boundary") or ""),
        }
        gap_change_receipts.append(
            {**receipt_body, "receipt_digest": canonical_digest(receipt_body)}
        )
    gaps = [gaps_by_id[str(row.get("gap_id") or "")] for row in gaps]

    successor = deepcopy(dict(predecessor))
    successor.pop("pack_payload_digest", None)
    successor["evidence_items"] = items
    successor["source_materials"] = materials
    successor["residual_gaps"] = gaps
    successor["observed_counts"] = {
        **dict(successor.get("observed_counts") or {}),
        "accepted_evidence_items": len(items),
        "direct_evidence_items": sum(
            row.get("disposition") == "accepted_direct_source_evidence"
            for row in items
        ),
        "bounded_context_items": sum(
            row.get("disposition") == "accepted_bounded_context_evidence"
            for row in items
        ),
        "source_materials": len(materials),
        "residual_gaps": len(gaps),
    }
    successor["content_gate_basis"] = (
        "reviewed_predecessor_plus_ranked_object_capture_bound_successor_gate"
    )
    successor["successor_lineage"] = {
        "recorded_at": recorded_at,
        "policy_id": policy.get("policy_id"),
        "predecessor_pack_payload_digest": predecessor.get("pack_payload_digest"),
        "retired_evidence_item_digests": sorted(retired_digests),
        "added_evidence_item_digests": sorted(
            str(row.get("evidence_item_digest") or "") for row in additions
        ),
        "capture_receipt_digests": sorted(
            str(row.get("receipt_digest") or "") for row in capture_receipts
        ),
        "gap_change_receipt_digests": sorted(
            str(row.get("receipt_digest") or "") for row in gap_change_receipts
        ),
    }
    successor["known_boundary"] = str(policy.get("successor_known_boundary") or "")
    successor["pack_payload_digest"] = canonical_digest(successor)
    validate_reviewed_evidence_pack(successor)

    coverage_delta = {
        "predecessor_evidence_count": len(predecessor_items),
        "successor_evidence_count": len(items),
        "retired_broad_or_legacy_evidence_count": len(retired_digests),
        "added_capture_bound_claim_count": len(additions),
        "predecessor_gap_count": len(predecessor.get("residual_gaps") or ()),
        "successor_gap_count": len(gaps),
        "narrowed_gap_count": len(gap_change_receipts),
        "closed_gap_count": 0,
        "candidate_text_promoted_count": 0,
        "numeric_authority_granted_count": 0,
    }
    result_body = {
        "schema_version": SUPPLEMENT_RESULT_SCHEMA_VERSION,
        "status": "capture_bound_supplement_successor_materialized",
        "recorded_at": recorded_at,
        "case_key": case_key,
        "research_as_of": research_as_of,
        "policy_id": policy.get("policy_id"),
        "predecessor_pack_payload_digest": predecessor.get("pack_payload_digest"),
        "successor_pack": successor,
        "coverage_delta": coverage_delta,
        "capture_receipts": capture_receipts,
        "review_receipts": review_receipts,
        "gap_change_receipts": gap_change_receipts,
        "authority": {
            "candidate_is_not_evidence": True,
            "positive_relation_joined_after_ranking": True,
            "capture_first": True,
            "hard_negative_promoted": False,
            "numeric_authority": False,
            "causal_attribution_authorized": False,
            "network_calls": 0,
            "generation_model_calls": 0,
            "s1_complete_claimed": False,
        },
    }
    return {**result_body, "result_digest": canonical_digest(result_body)}


def compile_supplement_workbench_projection(
    *, result: Mapping[str, Any], proposition_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    body = {
        "schema_version": WORKBENCH_SCHEMA_VERSION,
        "status": "s1_supplement_vertical_ready",
        "case_key": result.get("case_key"),
        "research_as_of": result.get("research_as_of"),
        "coverage_delta": deepcopy(dict(result.get("coverage_delta") or {})),
        "propositions": [deepcopy(dict(row)) for row in proposition_rows],
        "gap_receipts": deepcopy(list(result.get("gap_change_receipts") or ())),
        "authority": deepcopy(dict(result.get("authority") or {})),
        "readiness": {
            "bounded_dell_supplement_ready": True,
            "complete_s1_ready": False,
            "complete_research_ready": False,
            "numeric_fact_ready": False,
        },
    }
    return {**body, "projection_digest": canonical_digest(body)}


def validate_supplement_vertical_summary(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    value = deepcopy(dict(payload))
    storage = _mapping(
        value.get("storage"), "supplement_summary_storage_invalid"
    )
    decision = _mapping(
        value.get("decision"), "supplement_summary_decision_invalid"
    )
    projection = _mapping(
        value.get("workbench_projection"),
        "supplement_summary_projection_invalid",
    )
    bound = _mapping(
        value.get("bound_inputs"), "supplement_summary_bound_inputs_invalid"
    )
    _require(
        value.get("schema_version") == SUPPLEMENT_SUMMARY_SCHEMA_VERSION
        and value.get("status")
        == "vs4_dell_capture_bound_supplement_vertical_materialized"
        and str(projection.get("case_key") or "") == "DELL"
        and decision.get("successor_pack_authorized") is True
        and decision.get("complete_s1_qualified") is False
        and str(value.get("result_digest") or "")
        == str(storage.get("full_result_digest") or "")
        and len(str(storage.get("successor_pack_sha256") or "")) == 64
        and len(str(storage.get("successor_pack_payload_digest") or "")) == 64
        and len(str(bound.get("predecessor_pack_sha256") or "")) == 64
        and len(str(bound.get("predecessor_pack_payload_digest") or "")) == 64,
        "supplement_summary_identity_invalid",
    )
    return value


def project_capture_bound_supplement_lineage(
    *,
    base_projection: Mapping[str, Any] | None,
    supplement_summary: Mapping[str, Any] | None,
    case_key: str,
    artifact_digest: str,
    pack_payload_digest: str,
) -> dict[str, Any] | None:
    if base_projection is None:
        return None
    base = deepcopy(dict(base_projection))
    binding = _mapping(
        base.get("pack_binding"), "supplement_base_pack_binding_invalid"
    )
    if (
        binding.get("case_key") == case_key
        and binding.get("artifact_digest") == artifact_digest
        and binding.get("pack_payload_digest") == pack_payload_digest
    ):
        return base
    _require(
        supplement_summary is not None and case_key == "DELL",
        "supplement_current_pack_binding_drift",
    )
    supplement = validate_supplement_vertical_summary(supplement_summary)
    storage = _mapping(
        supplement["storage"], "supplement_summary_storage_invalid"
    )
    predecessor = _mapping(
        supplement["bound_inputs"], "supplement_summary_bound_inputs_invalid"
    )
    _require(
        binding.get("case_key") == case_key
        and binding.get("artifact_digest")
        == predecessor.get("predecessor_pack_sha256")
        and binding.get("pack_payload_digest")
        == predecessor.get("predecessor_pack_payload_digest")
        and storage.get("successor_pack_sha256") == artifact_digest
        and storage.get("successor_pack_payload_digest") == pack_payload_digest,
        "supplement_current_pack_binding_drift",
    )
    base.pop("workbench_projection_digest", None)
    base["status"] = "canonical_s1_lineage_with_capture_bound_supplement"
    base["recorded_at"] = str(supplement["recorded_at"])
    base["pack_binding"] = {
        "case_key": case_key,
        "artifact_digest": artifact_digest,
        "pack_payload_digest": pack_payload_digest,
    }
    workbench = _mapping(
        supplement["workbench_projection"],
        "supplement_summary_projection_invalid",
    )
    base["supplement_vertical"] = {
        "result_digest": str(supplement["result_digest"]),
        "coverage_delta": deepcopy(dict(supplement["coverage_delta"])),
        "readiness": deepcopy(dict(workbench["readiness"])),
        "candidate_is_not_evidence": True,
        "numeric_fact_authorized": False,
        "complete_s1_qualified": False,
    }
    base["workbench_projection_digest"] = canonical_digest(base)
    return base


__all__ = [
    "CAPTURE_RECEIPT_SCHEMA_VERSION",
    "GAP_RECEIPT_SCHEMA_VERSION",
    "SUPPLEMENT_RESULT_SCHEMA_VERSION",
    "SUPPLEMENT_SUMMARY_SCHEMA_VERSION",
    "SupplementVerticalError",
    "WORKBENCH_SCHEMA_VERSION",
    "build_capture_bound_pack_successor",
    "compile_supplement_workbench_projection",
    "project_capture_bound_supplement_lineage",
    "validate_supplement_vertical_summary",
    "verify_capture_bound_object",
]
