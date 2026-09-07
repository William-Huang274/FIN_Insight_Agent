from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


REVIEWED_EVIDENCE_PACK_SCHEMA = "fin_ia_0_1_3_s1_local_evidence_pack_v1_0"
REVIEWED_EVIDENCE_PACK_CONTRACT = (
    "fin_0_1_3.S1.candidate_to_local_evidence_pack:v1"
)


class ReviewedEvidencePackError(ValueError):
    """A reviewed Evidence Pack failed its immutable product contract."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ReviewedEvidencePackError(code)


def validate_reviewed_evidence_pack(pack: Mapping[str, Any]) -> None:
    """Validate the product-facing, immutable reviewed Evidence Pack surface.

    Generation and historical experiment code deliberately live outside this
    module.  The current Workbench depends only on this compact read contract.
    """

    normalized = deepcopy(dict(pack))
    digest = str(normalized.pop("pack_payload_digest", ""))
    _require(
        normalized.get("schema_version") == REVIEWED_EVIDENCE_PACK_SCHEMA
        and normalized.get("contract_ref") == REVIEWED_EVIDENCE_PACK_CONTRACT
        and digest == canonical_digest(normalized),
        "reviewed_evidence_pack_payload_digest_invalid",
    )
    evidence = [dict(row) for row in normalized.get("evidence_items") or ()]
    rejected = [dict(row) for row in normalized.get("rejected_items") or ()]
    gaps = [dict(row) for row in normalized.get("residual_gaps") or ()]
    evidence_targets = [str(row.get("target_id") or "") for row in evidence]
    rejected_targets = [str(row.get("target_id") or "") for row in rejected]
    _require(
        evidence
        and gaps
        and len(evidence_targets) == len(set(evidence_targets))
        and len(rejected_targets) == len(set(rejected_targets))
        and not (set(evidence_targets) & set(rejected_targets)),
        "reviewed_evidence_pack_target_partition_invalid",
    )
    for row in evidence:
        _require(
            row.get("writer_citable") is True
            and row.get("causal_attribution_authorized") is False
            and row.get("slot_bindings")
            and str(row.get("publication_date") or "")
            <= str(row.get("research_as_of") or ""),
            "reviewed_evidence_pack_evidence_boundary_invalid",
        )
        if row.get("disposition") == "accepted_bounded_context_evidence":
            _require(
                row.get("evidence_role")
                == "counterparty_or_ecosystem_readthrough"
                and all(
                    str(binding.get("claim_boundary_zh") or "")
                    for binding in row["slot_bindings"]
                ),
                "reviewed_evidence_pack_context_boundary_invalid",
            )
        elif row.get("disposition") == "accepted_direct_source_evidence":
            _require(
                row.get("evidence_role") == "issuer_direct_source",
                "reviewed_evidence_pack_direct_source_boundary_invalid",
            )
        else:
            _require(False, "reviewed_evidence_pack_disposition_invalid")
        if row.get("object_type") == "metric":
            metric = dict(row.get("structured_metric") or {})
            authority = dict(metric.get("currency_unit_authority") or {})
            _require(
                metric.get("table_path")
                and str(metric.get("raw_value") or "")
                and authority.get("status")
                in {
                    "source_and_child_consistent",
                    "non_monetary_dimension_preserved",
                },
                "reviewed_evidence_pack_metric_authority_invalid",
            )
    _require(
        all(row.get("writer_citable") is False for row in rejected)
        and all(row.get("gap_code") and row.get("slot_id") for row in gaps),
        "reviewed_evidence_pack_rejection_or_gap_boundary_invalid",
    )


def build_reviewed_evidence_pack_successor(
    *,
    predecessor: Mapping[str, Any],
    evidence_result: Mapping[str, Any],
    accepted_result_statuses: Sequence[str],
    gap_ids_satisfied: Sequence[str],
    successor_lineage: Mapping[str, Any],
    content_gate_basis: str,
    known_boundary_suffix: str,
) -> dict[str, Any]:
    """Append source-specific, already-gated Evidence to one reviewed Pack.

    Source adapters remain responsible for capture, identity, date, claim-use and
    proposition checks.  This shared step only performs immutable Pack composition
    and therefore prevents every new source family from inventing another Pack
    successor implementation.
    """

    validate_reviewed_evidence_pack(predecessor)
    normalized_result = deepcopy(dict(evidence_result))
    result_digest = str(normalized_result.pop("result_digest", ""))
    allowed_statuses = {str(value) for value in accepted_result_statuses if str(value)}
    _require(
        allowed_statuses
        and result_digest == canonical_digest(normalized_result)
        and predecessor.get("case_key") == evidence_result.get("consumer_case_key")
        and evidence_result.get("status") in allowed_statuses
        and evidence_result.get("evidence_qualified") is True
        and evidence_result.get("accepted_evidence_items")
        and evidence_result.get("candidate_is_not_evidence") is False
        and evidence_result.get("causal_attribution_authorized") is False,
        "reviewed_evidence_pack_successor_input_invalid",
    )
    gaps = [dict(row) for row in predecessor.get("residual_gaps") or ()]
    existing_gap_ids = {str(row.get("gap_id") or "") for row in gaps}
    requested = {str(value) for value in gap_ids_satisfied if str(value)}
    _require(
        requested <= existing_gap_ids,
        "reviewed_evidence_pack_successor_gap_unknown",
    )
    qualified_gap_ids = {
        str(value) for value in evidence_result.get("gap_ids_satisfied") or ()
    }
    _require(
        requested <= qualified_gap_ids,
        "reviewed_evidence_pack_successor_gap_not_qualified",
    )

    body = deepcopy(dict(predecessor))
    body.pop("pack_payload_digest", None)
    existing_targets = {
        str(row.get("target_id") or "") for row in body.get("evidence_items") or ()
    }
    additions = [dict(row) for row in evidence_result["accepted_evidence_items"]]
    _require(
        not any(str(row.get("target_id") or "") in existing_targets for row in additions),
        "reviewed_evidence_pack_successor_target_collision",
    )
    existing_materials = {
        str(row.get("material_ref") or "")
        for row in body.get("source_materials") or ()
    }
    materials = [dict(row) for row in evidence_result.get("source_materials") or ()]
    _require(
        len(materials) == len(additions)
        and not any(
            str(row.get("material_ref") or "") in existing_materials
            for row in materials
        ),
        "reviewed_evidence_pack_successor_material_collision",
    )

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
    body["content_gate_basis"] = str(content_gate_basis)
    body["successor_lineage"] = deepcopy(dict(successor_lineage))
    gap_statement = (
        "This successor closes only the explicitly declared gap IDs: "
        + ", ".join(sorted(requested))
        + ". "
        if requested
        else (
            "This successor adds qualified Evidence without closing any residual "
            "gap. "
        )
    )
    body["known_boundary"] = gap_statement + str(known_boundary_suffix)
    successor = {**body, "pack_payload_digest": canonical_digest(body)}
    validate_reviewed_evidence_pack(successor)
    return successor


def build_reviewed_evidence_pack_correction_successor(
    *,
    predecessor: Mapping[str, Any],
    evidence_result: Mapping[str, Any],
    accepted_result_statuses: Sequence[str],
    gap_ids_satisfied: Sequence[str],
    retirements: Sequence[Mapping[str, Any]],
    successor_lineage: Mapping[str, Any],
    content_gate_basis: str,
    known_boundary_suffix: str,
) -> dict[str, Any]:
    """Retire exactly bound stale identities before adding corrected Evidence."""

    validate_reviewed_evidence_pack(predecessor)
    rows = [dict(row) for row in retirements]
    target_ids = [str(row.get("target_id") or "") for row in rows]
    replacement_candidate_ids = [
        str(row.get("replacement_candidate_id") or "") for row in rows
    ]
    _require(
        rows
        and len(target_ids) == len(set(target_ids))
        and all(target_ids)
        and len(replacement_candidate_ids)
        == len(set(replacement_candidate_ids))
        and all(replacement_candidate_ids)
        and all(str(row.get("reason_zh") or "") for row in rows),
        "reviewed_evidence_pack_correction_retirement_shape_invalid",
    )
    existing_items = {
        str(row.get("target_id") or ""): dict(row)
        for row in predecessor.get("evidence_items") or ()
    }
    existing_materials = {
        str(row.get("material_ref") or ""): dict(row)
        for row in predecessor.get("source_materials") or ()
    }
    accepted_items = {
        str(row.get("target_id") or ""): dict(row)
        for row in evidence_result.get("accepted_evidence_items") or ()
    }
    expected_replacement_targets = {
        "EXTEV::"
        + canonical_digest(
            {
                "candidate_id": candidate_id,
                "plan_id": evidence_result.get("plan_id"),
            }
        )[:20].upper()
        for candidate_id in replacement_candidate_ids
    }
    _require(
        expected_replacement_targets <= set(accepted_items),
        "reviewed_evidence_pack_correction_replacement_missing",
    )
    retired_material_refs: set[str] = set()
    for retirement in rows:
        target_id = str(retirement["target_id"])
        item = existing_items.get(target_id)
        material_ref = str(retirement.get("source_material_ref") or "")
        material = existing_materials.get(material_ref)
        _require(
            item is not None
            and material is not None
            and str(item.get("evidence_item_digest") or "")
            == str(retirement.get("evidence_item_digest") or "")
            and str(item.get("source_record_id") or "")
            == str(retirement.get("source_record_id") or "")
            and str(item.get("source_material_ref") or "") == material_ref
            and str(material.get("source_record_id") or "")
            == str(retirement.get("source_record_id") or ""),
            "reviewed_evidence_pack_correction_retirement_binding_invalid",
        )
        retired_material_refs.add(material_ref)
    kept_items = [
        deepcopy(dict(row))
        for row in predecessor.get("evidence_items") or ()
        if str(row.get("target_id") or "") not in set(target_ids)
    ]
    _require(
        kept_items
        and not any(
            str(row.get("source_material_ref") or "") in retired_material_refs
            for row in kept_items
        ),
        "reviewed_evidence_pack_correction_shared_material_invalid",
    )
    corrected_body = deepcopy(dict(predecessor))
    corrected_body.pop("pack_payload_digest", None)
    corrected_body["evidence_items"] = kept_items
    corrected_body["source_materials"] = [
        deepcopy(dict(row))
        for row in predecessor.get("source_materials") or ()
        if str(row.get("material_ref") or "") not in retired_material_refs
    ]
    counts = dict(corrected_body.get("observed_counts") or {})
    counts["accepted_evidence_items"] = len(corrected_body["evidence_items"])
    counts["bounded_context_items"] = sum(
        row.get("disposition") == "accepted_bounded_context_evidence"
        for row in corrected_body["evidence_items"]
    )
    counts["direct_evidence_items"] = sum(
        row.get("disposition") == "accepted_direct_source_evidence"
        for row in corrected_body["evidence_items"]
    )
    counts["source_materials"] = len(corrected_body["source_materials"])
    corrected_body["observed_counts"] = counts
    corrected_body["known_boundary"] = (
        "Intermediate correction view retires only digest-bound stale Evidence "
        "and source materials before replacement admission."
    )
    corrected_predecessor = {
        **corrected_body,
        "pack_payload_digest": canonical_digest(corrected_body),
    }
    validate_reviewed_evidence_pack(corrected_predecessor)
    return build_reviewed_evidence_pack_successor(
        predecessor=corrected_predecessor,
        evidence_result=evidence_result,
        accepted_result_statuses=accepted_result_statuses,
        gap_ids_satisfied=gap_ids_satisfied,
        successor_lineage=successor_lineage,
        content_gate_basis=content_gate_basis,
        known_boundary_suffix=known_boundary_suffix,
    )


__all__ = [
    "REVIEWED_EVIDENCE_PACK_CONTRACT",
    "REVIEWED_EVIDENCE_PACK_SCHEMA",
    "ReviewedEvidencePackError",
    "canonical_bytes",
    "canonical_digest",
    "build_reviewed_evidence_pack_correction_successor",
    "build_reviewed_evidence_pack_successor",
    "file_sha256",
    "validate_reviewed_evidence_pack",
]
