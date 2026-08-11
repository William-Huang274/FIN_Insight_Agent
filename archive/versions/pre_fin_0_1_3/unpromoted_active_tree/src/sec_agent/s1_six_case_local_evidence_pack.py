from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping


POLICY_SCHEMA = "fin_ia_0_1_3_s1_six_case_local_evidence_pack_policy_v1_0"
PACK_SCHEMA = "fin_ia_0_1_3_s1_local_evidence_pack_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_six_case_local_evidence_pack_result_v1_0"
CONTRACT_REF = "fin_0_1_3.S1.candidate_to_local_evidence_pack:v1"
CASES = ("DELL", "MU", "NVDA", "ORCL", "ASML", "ANET")
KNOWN_CASES = CASES[:3]
HELD_OUT_CASES = CASES[3:]


class SixCaseLocalEvidencePackError(ValueError):
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


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SixCaseLocalEvidencePackError(code)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def _load_bound_json(root: Path, binding: Mapping[str, Any]) -> Any:
    path = _resolve(root, str(binding.get("ref") or ""))
    _require(path.is_file(), "local_evidence_pack_bound_input_missing")
    _require(
        file_sha256(path) == str(binding.get("sha256") or ""),
        "local_evidence_pack_bound_input_digest_drift",
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _decision_index(
    profile: Mapping[str, Any],
    *,
    accepted_key: str,
    rejected_key: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    accepted = {
        str(target): dict(decision)
        for target, decision in dict(profile.get(accepted_key) or {}).items()
    }
    rejected: dict[str, dict[str, Any]] = {}
    for group in profile.get(rejected_key) or ():
        for target in group.get("target_ids") or ():
            _require(
                str(target) not in rejected,
                "local_evidence_pack_duplicate_rejection_decision",
            )
            rejected[str(target)] = {
                "reason_code": str(group.get("reason_code") or ""),
                "business_reason_zh": str(group.get("business_reason_zh") or ""),
            }
    _require(
        not (set(accepted) & set(rejected)),
        "local_evidence_pack_accept_reject_overlap",
    )
    return accepted, rejected


def load_six_case_local_evidence_pack_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = json.loads(Path(path).read_text(encoding="utf-8"))
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("result_schema") == RESULT_SCHEMA
        and policy.get("pack_schema") == PACK_SCHEMA
        and policy.get("contract_ref") == CONTRACT_REF,
        "local_evidence_pack_policy_identity_invalid",
    )
    _require(
        tuple(policy.get("materialization_order") or ()) == CASES,
        "local_evidence_pack_dell_first_order_invalid",
    )
    _require(
        set(policy.get("known_case_bindings") or {}) == set(KNOWN_CASES)
        and set(policy.get("held_out_decisions") or {}) == set(HELD_OUT_CASES),
        "local_evidence_pack_case_set_invalid",
    )
    for binding in (policy.get("immutable_inputs") or {}).values():
        _load_bound_json(root, binding)
    for case_key, binding in policy["known_case_bindings"].items():
        _require(
            binding.get("result_input") in policy["immutable_inputs"],
            "local_evidence_pack_known_result_binding_invalid",
        )
        _require(
            int(binding.get("expected_manifest_candidates") or 0) > 0,
            "local_evidence_pack_known_candidate_count_invalid",
        )
    for case_key, profile in policy["held_out_decisions"].items():
        accepted_metrics, rejected_metrics = _decision_index(
            profile,
            accepted_key="accepted_metrics",
            rejected_key="rejected_metric_groups",
        )
        accepted_claims, rejected_claims = _decision_index(
            profile,
            accepted_key="accepted_claims",
            rejected_key="rejected_claim_groups",
        )
        _require(
            accepted_metrics
            and accepted_claims
            and all(
                row.get("slot_bindings") or row.get("facet_ids")
                for row in accepted_metrics.values()
            )
            and all(
                row.get("slot_bindings") or row.get("facet_ids")
                for row in accepted_claims.values()
            )
            and all(row.get("reason_code") for row in rejected_metrics.values())
            and all(row.get("reason_code") for row in rejected_claims.values()),
            f"local_evidence_pack_held_out_decision_invalid:{case_key}",
        )
    _require(
        set(policy.get("facet_gap_codes") or {}),
        "local_evidence_pack_gap_code_map_missing",
    )
    return policy


def _load_source_records(
    *,
    repo_root: Path,
    refs: Iterable[str],
    wanted: set[str],
) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for ref in refs:
        path = _resolve(repo_root, ref)
        _require(path.is_file(), "local_evidence_pack_source_records_missing")
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                row = json.loads(line)
                record_id = str(row.get("evidence_id") or row.get("record_id") or "")
                if record_id not in wanted:
                    continue
                prior = found.get(record_id)
                if prior is not None:
                    _require(
                        hashlib.sha256(str(prior.get("text") or "").encode("utf-8")).hexdigest()
                        == hashlib.sha256(str(row.get("text") or "").encode("utf-8")).hexdigest(),
                        "local_evidence_pack_duplicate_source_content_conflict",
                    )
                else:
                    found[record_id] = row
                if set(found) == wanted:
                    return found
    _require(set(found) == wanted, "local_evidence_pack_source_record_not_found")
    return found


def _load_private_artifact(
    *,
    repo_root: Path,
    private_root_ref: str,
    reference: Mapping[str, Any],
) -> Any:
    path = _resolve(repo_root, private_root_ref) / str(reference.get("object_key") or "")
    _require(path.is_file(), "local_evidence_pack_private_artifact_missing")
    _require(
        file_sha256(path) == str(reference.get("digest") or ""),
        "local_evidence_pack_private_artifact_digest_drift",
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _known_case_pack(
    *,
    case_key: str,
    specs: list[dict[str, Any]],
    result: Mapping[str, Any],
    source_records: Mapping[str, Mapping[str, Any]],
    generalization_digest: str,
    manifest_digest: str,
    retrieval_result_digest: str,
) -> dict[str, Any]:
    qualification_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in result.get("candidate_qualifications") or ():
        if row.get("qualification_status") == "qualified":
            qualification_index[str(row.get("target_id") or "")].append(dict(row))
    evidence_items: list[dict[str, Any]] = []
    materials: dict[str, dict[str, Any]] = {}
    for spec in sorted(specs, key=lambda row: str(row["target_id"])):
        target_id = str(spec["target_id"])
        rows = qualification_index.get(target_id) or []
        _require(rows, f"local_evidence_pack_known_target_unreviewed:{case_key}")
        source_record_id = str(spec.get("source_record_id") or "")
        source = dict(source_records.get(source_record_id) or {})
        _require(source, f"local_evidence_pack_known_source_missing:{case_key}")
        source_text = str(source.get("text") or "")
        source_text_digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        _require(
            source_text
            and source_text_digest == str(spec.get("source_content_digest") or "")
            and all(
                str(row.get("source_record_id") or "") == source_record_id
                and str(row.get("source_content_digest") or "") == source_text_digest
                for row in rows
            ),
            f"local_evidence_pack_known_source_binding_invalid:{case_key}",
        )
        material_ref = "source_material_" + source_text_digest[:24]
        materials.setdefault(
            material_ref,
            {
                "material_ref": material_ref,
                "source_record_id": source_record_id,
                "source_text": source_text,
                "source_text_digest": source_text_digest,
                "source_url": str(source.get("source_url") or spec.get("source_locator") or ""),
                "source_type": str(source.get("source_type") or ""),
                "source_tier": str(source.get("source_tier") or ""),
                "evidence_owner_ticker": str(source.get("ticker") or spec.get("evidence_owner_ticker") or ""),
                "publication_date": str(source.get("publication_date") or ""),
                "period_end": str(source.get("period_end") or ""),
                "license_scope": str(source.get("license_scope") or ""),
                "redistributable": bool(source.get("redistributable", False)),
            },
        )
        direct = str(spec.get("evidence_owner_ticker") or "") == case_key
        slot_bindings = [
            {
                "qualification_id": str(row["qualification_id"]),
                "slot_id": str(row["slot_id"]),
                "facet_ids": list(row.get("facet_ids") or ()),
                "business_meaning_zh": str(row.get("business_meaning_zh") or ""),
                "claim_boundary_zh": str(row.get("content_limitation_zh") or ""),
            }
            for row in sorted(rows, key=lambda item: str(item["qualification_id"]))
        ]
        body = {
            "case_key": case_key,
            "target_id": target_id,
            "source_record_id": source_record_id,
            "source_material_ref": material_ref,
            "source_content_digest": source_text_digest,
            "object_type": str(spec.get("object_type") or ""),
            "disposition": (
                "accepted_direct_source_evidence"
                if direct
                else "accepted_bounded_context_evidence"
            ),
            "evidence_role": (
                "issuer_direct_source" if direct else "counterparty_or_ecosystem_readthrough"
            ),
            "slot_bindings": slot_bindings,
            "publication_date": str(spec.get("publication_date") or ""),
            "source_reporting_period_end": str(spec.get("source_reporting_period_end") or ""),
            "research_as_of": str(spec.get("research_as_of") or ""),
            "relationship_directions": list(spec.get("relationship_directions") or ()),
            "writer_citable": True,
            "numeric_use_boundary": "Only source-visible exact values may be quoted; derived arithmetic requires a separate deterministic numeric program.",
            "causal_attribution_authorized": False,
        }
        evidence_items.append(
            {**body, "evidence_item_digest": canonical_digest(body)}
        )
    gaps = [dict(row) for row in result.get("declared_residual_gap_business") or ()]
    return _finalize_pack(
        case_key=case_key,
        evidence_items=evidence_items,
        source_materials=list(materials.values()),
        rejected_items=[],
        residual_gaps=gaps,
        generalization_digest=generalization_digest,
        manifest_digest=manifest_digest,
        retrieval_result_digest=retrieval_result_digest,
        content_gate_basis="reviewed_known_case_candidate_qualifications",
    )


def _held_out_pack(
    *,
    case_key: str,
    specs: list[dict[str, Any]],
    queue: list[dict[str, Any]],
    profile: Mapping[str, Any],
    case_result: Mapping[str, Any],
    metrics: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    slot_library: list[dict[str, Any]],
    gap_code_map: Mapping[str, str],
    gap_directions: Mapping[str, str],
    generalization_digest: str,
    manifest_digest: str,
    retrieval_result_digest: str,
) -> dict[str, Any]:
    accepted_metrics, rejected_metrics = _decision_index(
        profile,
        accepted_key="accepted_metrics",
        rejected_key="rejected_metric_groups",
    )
    accepted_claims, rejected_claims = _decision_index(
        profile,
        accepted_key="accepted_claims",
        rejected_key="rejected_claim_groups",
    )
    spec_index = {str(row["target_id"]): row for row in specs}
    queue_index = {str(row["target_id"]): row for row in queue}
    _require(
        set(spec_index) == set(accepted_metrics) | set(rejected_metrics),
        f"local_evidence_pack_metric_adjudication_incomplete:{case_key}",
    )
    _require(
        set(queue_index) == set(accepted_claims) | set(rejected_claims),
        f"local_evidence_pack_claim_adjudication_incomplete:{case_key}",
    )
    metric_index = {str(row.get("object_id") or ""): row for row in metrics}
    claim_index = {str(row.get("object_id") or ""): row for row in claims}
    evidence_items: list[dict[str, Any]] = []
    rejected_items: list[dict[str, Any]] = []
    source_identity = dict(case_result.get("source_identity") or {})
    as_of = str(profile.get("research_as_of") or "")
    for target_id, decision in sorted(accepted_metrics.items()):
        spec = spec_index[target_id]
        metric = dict(metric_index.get(target_id) or {})
        _require(
            metric
            and canonical_digest(metric) == str(spec.get("child_content_digest") or "")
            and str(spec.get("object_type") or "") == "metric"
            and str(spec.get("publication_date") or "") <= as_of
            and bool(spec.get("table_path"))
            and str((spec.get("currency_unit_authority") or {}).get("status") or "")
            in {"source_and_child_consistent", "non_monetary_dimension_preserved"},
            f"local_evidence_pack_metric_lineage_invalid:{case_key}",
        )
        adjudicated_bindings = [
            {
                "slot_id": str(row.get("slot_id") or ""),
                "facet_ids": list(row.get("facet_ids") or ()),
                "business_meaning_zh": (
                    f"{case_key} 在 {spec['table_path']['column_label']} 披露"
                    f"“{metric.get('metric_name') or metric.get('row_label')}”为"
                    f" {metric.get('raw_value')}。"
                ),
                "claim_boundary_zh": str(decision.get("claim_boundary_zh") or ""),
            }
            for row in (
                decision.get("slot_bindings")
                or (
                    {
                        "slot_id": str((spec.get("slot_ids") or [""])[0]),
                        "facet_ids": list(decision.get("facet_ids") or ()),
                    },
                )
            )
        ]
        _require(
            all(row["slot_id"] and row["facet_ids"] for row in adjudicated_bindings),
            f"local_evidence_pack_metric_slot_binding_invalid:{case_key}",
        )
        body = {
            "case_key": case_key,
            "target_id": target_id,
            "source_record_id": str(spec.get("source_record_id") or ""),
            "source_content_digest": str(spec.get("source_content_digest") or ""),
            "child_content_digest": str(spec.get("child_content_digest") or ""),
            "object_type": "metric",
            "disposition": "accepted_direct_source_evidence",
            "evidence_role": "issuer_structured_metric",
            "candidate_slot_ids": list(spec.get("slot_ids") or ()),
            "slot_bindings": adjudicated_bindings,
            "structured_metric": {
                "metric_name": str(metric.get("metric_name") or metric.get("row_label") or ""),
                "raw_value": str(metric.get("raw_value") or ""),
                "value": metric.get("value"),
                "unit": str(metric.get("unit") or ""),
                "period": str(metric.get("period") or ""),
                "table_path": deepcopy(spec.get("table_path")),
                "currency_unit_authority": deepcopy(spec.get("currency_unit_authority")),
            },
            "source_url": str(spec.get("source_locator") or ""),
            "publication_date": str(spec.get("publication_date") or ""),
            "source_reporting_period_end": str(spec.get("source_reporting_period_end") or ""),
            "research_as_of": as_of,
            "writer_citable": True,
            "numeric_use_boundary": "The typed row/column/value/unit surface is authoritative; no adjacent table value or causal attribution may be invented.",
            "causal_attribution_authorized": False,
        }
        evidence_items.append({**body, "evidence_item_digest": canonical_digest(body)})
    for target_id, decision in sorted(accepted_claims.items()):
        claim = dict(claim_index.get(target_id) or {})
        _require(
            claim
            and str(claim.get("claim_text") or "").strip()
            and str(claim.get("ticker") or "") == case_key,
            f"local_evidence_pack_claim_lineage_invalid:{case_key}",
        )
        adjudicated_bindings = [
            {
                "slot_id": str(row.get("slot_id") or ""),
                "facet_ids": list(row.get("facet_ids") or ()),
                "business_meaning_zh": str(decision.get("business_meaning_zh") or ""),
                "claim_boundary_zh": str(decision.get("claim_boundary_zh") or ""),
            }
            for row in (
                decision.get("slot_bindings")
                or (
                    {
                        "slot_id": str(queue_index[target_id].get("slot_id") or ""),
                        "facet_ids": list(decision.get("facet_ids") or ()),
                    },
                )
            )
        ]
        _require(
            all(row["slot_id"] and row["facet_ids"] for row in adjudicated_bindings),
            f"local_evidence_pack_claim_slot_binding_invalid:{case_key}",
        )
        body = {
            "case_key": case_key,
            "target_id": target_id,
            "source_record_id": str(claim.get("source_evidence_id") or ""),
            "object_type": "claim",
            "disposition": "accepted_direct_source_evidence",
            "evidence_role": "issuer_reviewed_narrative_claim",
            "candidate_slot_id": str(queue_index[target_id].get("slot_id") or ""),
            "slot_bindings": adjudicated_bindings,
            "claim_text": str(claim["claim_text"]),
            "claim_type": str(claim.get("claim_type") or ""),
            "source_url": str(claim.get("source_url") or source_identity.get("source_url") or ""),
            "publication_date": str(source_identity.get("publication_date") or ""),
            "source_reporting_period_end": str(source_identity.get("reporting_period_end") or ""),
            "research_as_of": as_of,
            "writer_citable": True,
            "numeric_use_boundary": "Narrative claims cannot authorize a numeric fact unless an accepted structured metric independently supplies it.",
            "causal_attribution_authorized": False,
            "retrieval_lane_provenance": "reviewed_local_supplement_not_ranked_in_r1",
        }
        evidence_items.append({**body, "evidence_item_digest": canonical_digest(body)})
    for target_id, decision in sorted({**rejected_metrics, **rejected_claims}.items()):
        spec = spec_index.get(target_id)
        metric = metric_index.get(target_id)
        claim = claim_index.get(target_id)
        rejected_items.append(
            {
                "case_key": case_key,
                "target_id": target_id,
                "object_type": "metric" if spec is not None else "claim",
                "reason_code": decision["reason_code"],
                "business_reason_zh": decision["business_reason_zh"],
                "observed_surface": (
                    str((metric or {}).get("metric_name") or (metric or {}).get("row_label") or "")
                    if spec is not None
                    else str((claim or {}).get("claim_text") or "")
                ),
                "writer_citable": False,
            }
        )
    covered = {
        (str(binding["slot_id"]), str(facet))
        for item in evidence_items
        for binding in item["slot_bindings"]
        for facet in binding["facet_ids"]
    }
    residual_gaps: list[dict[str, Any]] = []
    for slot in slot_library:
        slot_id = str(slot["slot_id"])
        for facet_id in slot.get("required_facets") or ():
            if (slot_id, str(facet_id)) in covered:
                continue
            gap_code = str(gap_code_map.get(str(facet_id)) or "")
            _require(
                gap_code in set(slot.get("typed_gap_codes") or ()),
                f"local_evidence_pack_gap_code_invalid:{case_key}:{slot_id}:{facet_id}",
            )
            residual_gaps.append(
                {
                    "gap_id": f"{case_key.lower()}-gap-{slot_id}-{facet_id}",
                    "slot_id": slot_id,
                    "facet_id": str(facet_id),
                    "gap_code": gap_code,
                    "required_for_current_research": slot_id
                    != "capital_allocation_and_valuation",
                    "business_reason_zh": (
                        f"当前已审查的 {case_key} 本地官方材料没有形成可用于“{facet_id}”的合格证据。"
                    ),
                    "supplement_direction_zh": str(gap_directions.get(str(facet_id)) or "补充对应的一手官方或合格外部来源。"),
                }
            )
    return _finalize_pack(
        case_key=case_key,
        evidence_items=evidence_items,
        source_materials=[],
        rejected_items=rejected_items,
        residual_gaps=residual_gaps,
        generalization_digest=generalization_digest,
        manifest_digest=manifest_digest,
        retrieval_result_digest=retrieval_result_digest,
        content_gate_basis="held_out_metric_and_narrative_explicit_adjudication",
    )


def _finalize_pack(
    *,
    case_key: str,
    evidence_items: list[dict[str, Any]],
    source_materials: list[dict[str, Any]],
    rejected_items: list[dict[str, Any]],
    residual_gaps: list[dict[str, Any]],
    generalization_digest: str,
    manifest_digest: str,
    retrieval_result_digest: str,
    content_gate_basis: str,
) -> dict[str, Any]:
    direct = sum(
        row["disposition"] == "accepted_direct_source_evidence"
        for row in evidence_items
    )
    context = sum(
        row["disposition"] == "accepted_bounded_context_evidence"
        for row in evidence_items
    )
    body = {
        "schema_version": PACK_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "case_key": case_key,
        "status": "local_evidence_pack_ready_with_declared_residual_gaps",
        "candidate_manifest_digest": manifest_digest,
        "retrieval_result_digest": retrieval_result_digest,
        "generalization_contract_digest": generalization_digest,
        "content_gate_basis": content_gate_basis,
        "evidence_items": sorted(evidence_items, key=lambda row: row["target_id"]),
        "source_materials": sorted(source_materials, key=lambda row: row["material_ref"]),
        "rejected_items": sorted(rejected_items, key=lambda row: row["target_id"]),
        "residual_gaps": sorted(
            residual_gaps,
            key=lambda row: (row["slot_id"], row["facet_id"]),
        ),
        "observed_counts": {
            "accepted_evidence_items": len(evidence_items),
            "direct_evidence_items": direct,
            "bounded_context_items": context,
            "rejected_items": len(rejected_items),
            "residual_gaps": len(residual_gaps),
            "source_materials": len(source_materials),
        },
        "consumer_contract": {
            "writer_may_consume_only_writer_citable_items": True,
            "context_items_must_preserve_claim_boundary": True,
            "rejected_items_must_not_enter_prompt": True,
            "residual_gaps_must_remain_visible": True,
            "exact_numeric_surface_must_be_source_visible_or_typed": True,
            "derived_numeric_claim_requires_deterministic_program": True,
            "model_may_not_change_identity_period_currency_unit_or_relationship_direction": True,
        },
        "known_boundary": (
            "This is a reviewed local Evidence Pack, not a complete investment report. "
            "It preserves direct evidence, bounded read-through, explicit rejections and typed gaps."
        ),
    }
    return {**body, "pack_payload_digest": canonical_digest(body)}


def validate_local_evidence_pack(pack: Mapping[str, Any]) -> None:
    normalized = deepcopy(dict(pack))
    digest = str(normalized.pop("pack_payload_digest", ""))
    _require(
        normalized.get("schema_version") == PACK_SCHEMA
        and normalized.get("contract_ref") == CONTRACT_REF
        and digest == canonical_digest(normalized),
        "local_evidence_pack_payload_digest_invalid",
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
        "local_evidence_pack_target_partition_invalid",
    )
    for row in evidence:
        _require(
            row.get("writer_citable") is True
            and row.get("causal_attribution_authorized") is False
            and row.get("slot_bindings")
            and str(row.get("publication_date") or "")
            <= str(row.get("research_as_of") or ""),
            "local_evidence_pack_evidence_boundary_invalid",
        )
        if row.get("disposition") == "accepted_bounded_context_evidence":
            _require(
                row.get("evidence_role") == "counterparty_or_ecosystem_readthrough"
                and all(
                    str(binding.get("claim_boundary_zh") or "")
                    for binding in row["slot_bindings"]
                ),
                "local_evidence_pack_context_boundary_invalid",
            )
        if row.get("object_type") == "metric":
            metric = dict(row.get("structured_metric") or {})
            authority = dict(metric.get("currency_unit_authority") or {})
            _require(
                metric.get("table_path")
                and str(metric.get("raw_value") or "")
                and authority.get("status")
                in {"source_and_child_consistent", "non_monetary_dimension_preserved"},
                "local_evidence_pack_metric_authority_invalid",
            )
    _require(
        all(row.get("writer_citable") is False for row in rejected)
        and all(row.get("gap_code") and row.get("slot_id") for row in gaps),
        "local_evidence_pack_rejection_or_gap_boundary_invalid",
    )


def compile_six_case_local_evidence_packs(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = Path(repo_root).resolve()
    inputs = {
        name: _load_bound_json(root, binding)
        for name, binding in policy["immutable_inputs"].items()
    }
    manifest = inputs["candidate_manifest"]
    retrieval = inputs["retrieval_result"]
    generalization = inputs["generalization_contract"]
    _require(
        str(manifest.get("manifest_digest") or "")
        == str(policy["expected_digests"]["candidate_manifest"])
        and str(retrieval.get("result_digest") or "")
        == str(policy["expected_digests"]["retrieval_result"]),
        "local_evidence_pack_semantic_digest_drift",
    )
    specs_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for spec in manifest.get("specs") or ():
        specs_by_case[str(spec.get("case_key") or "")].append(dict(spec))
    queue_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in manifest.get("narrative_review_queue") or ():
        queue_by_case[str(row.get("case_key") or "")].append(dict(row))
    _require(
        set(specs_by_case) == set(CASES)
        and sum(map(len, specs_by_case.values())) == 93
        and sum(map(len, queue_by_case.values())) == 19,
        "local_evidence_pack_manifest_population_invalid",
    )
    known_wanted = {
        str(spec["source_record_id"])
        for case_key in KNOWN_CASES
        for spec in specs_by_case[case_key]
    }
    source_records = _load_source_records(
        repo_root=root,
        refs=policy["known_case_source_record_refs"],
        wanted=known_wanted,
    )
    held_result = inputs["held_out_reparse_result"]
    held_index = {
        str(row.get("case_key") or ""): dict(row)
        for row in held_result.get("case_results") or ()
    }
    packs: list[dict[str, Any]] = []
    for case_key in CASES:
        if case_key in KNOWN_CASES:
            binding = policy["known_case_bindings"][case_key]
            result = inputs[str(binding["result_input"])]
            _require(
                str(result.get("case_key") or "") == case_key
                and len(specs_by_case[case_key])
                == int(binding["expected_manifest_candidates"]),
                f"local_evidence_pack_known_case_binding_invalid:{case_key}",
            )
            pack = _known_case_pack(
                case_key=case_key,
                specs=specs_by_case[case_key],
                result=result,
                source_records=source_records,
                generalization_digest=canonical_digest(generalization),
                manifest_digest=str(manifest["manifest_digest"]),
                retrieval_result_digest=str(retrieval["result_digest"]),
            )
        else:
            case_result = held_index.get(case_key) or {}
            private = dict(case_result.get("private_artifacts") or {})
            metrics = _load_private_artifact(
                repo_root=root,
                private_root_ref=str(policy["held_out_private_object_root"]),
                reference=dict(private.get("admitted_metrics") or {}),
            )
            claims = _load_private_artifact(
                repo_root=root,
                private_root_ref=str(policy["held_out_private_object_root"]),
                reference=dict(private.get("claims") or {}),
            )
            pack = _held_out_pack(
                case_key=case_key,
                specs=specs_by_case[case_key],
                queue=queue_by_case[case_key],
                profile=policy["held_out_decisions"][case_key],
                case_result=case_result,
                metrics=[dict(row) for row in metrics],
                claims=[dict(row) for row in claims],
                slot_library=[dict(row) for row in generalization["slot_library"]],
                gap_code_map=policy["facet_gap_codes"],
                gap_directions=policy["facet_supplement_directions_zh"],
                generalization_digest=canonical_digest(generalization),
                manifest_digest=str(manifest["manifest_digest"]),
                retrieval_result_digest=str(retrieval["result_digest"]),
            )
        validate_local_evidence_pack(pack)
        packs.append(pack)
    result_body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "run_scope": str(policy["run_scope"]),
        "recorded_at": str(policy["recorded_at"]),
        "attempt_id": str(policy["attempt_id"]),
        "status": "terminal_succeeded_six_case_local_evidence_packs_with_declared_gaps",
        "materialization_order": list(CASES),
        "candidate_manifest_digest": str(manifest["manifest_digest"]),
        "retrieval_result_digest": str(retrieval["result_digest"]),
        "pack_payload_digests": {
            row["case_key"]: row["pack_payload_digest"] for row in packs
        },
        "case_summaries": [
            {
                "case_key": row["case_key"],
                "status": row["status"],
                **row["observed_counts"],
            }
            for row in packs
        ],
        "observed_counts": {
            "manifest_candidates_adjudicated": 93,
            "narrative_queue_items_adjudicated": 19,
            "evidence_items": sum(row["observed_counts"]["accepted_evidence_items"] for row in packs),
            "rejected_items": sum(row["observed_counts"]["rejected_items"] for row in packs),
            "residual_gaps": sum(row["observed_counts"]["residual_gaps"] for row in packs),
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "embedding_calls": 0,
            "rerank_calls": 0,
        },
        "stage_acceptance": {
            "dell_first_content_gate_proven": packs[0]["case_key"] == "DELL",
            "same_core_transferred_to_five_cases": len(packs) == 6,
            "all_manifest_candidates_adjudicated": True,
            "all_narrative_queue_items_adjudicated": True,
            "source_text_and_structured_metric_lineage_verified": True,
            "rejected_surfaces_blocked_from_writer": True,
            "residual_gaps_visible_for_external_supplement": True,
            "complete_investment_report_claimed": False,
        },
        "known_boundary": (
            "Step 3 establishes reviewed local Evidence Packs. It does not claim full research "
            "coverage, external-source completion or model-analysis quality."
        ),
    }
    return packs, {**result_body, "result_digest": canonical_digest(result_body)}


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def materialize_six_case_local_evidence_packs(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    artifact_root: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    packs, result = compile_six_case_local_evidence_packs(
        policy=policy,
        repo_root=repo_root,
    )
    root = Path(artifact_root).resolve()
    refs: dict[str, dict[str, Any]] = {}
    for pack in packs:
        raw = canonical_bytes(pack)
        digest = hashlib.sha256(raw).hexdigest()
        case_key = str(pack["case_key"])
        object_key = (
            f"fin-0.1.3/s1-six-case-local-evidence-pack/{case_key.lower()}/v1/"
            f"{digest[:2]}/{digest[2:4]}/{digest}.json"
        )
        path = root / object_key
        _atomic_write(path, raw)
        _require(file_sha256(path) == digest, "local_evidence_pack_readback_failed")
        refs[case_key] = {
            "object_key": object_key,
            "digest": digest,
            "byte_size": len(raw),
            "media_type": "application/json",
            "artifact_type": "reviewed_local_evidence_pack_with_declared_gaps",
        }
    public_body = deepcopy(result)
    public_body.pop("result_digest", None)
    public_body["pack_artifacts"] = refs
    public_result = {
        **public_body,
        "result_digest": canonical_digest(public_body),
    }
    output = Path(output_path).resolve()
    _atomic_write(output, json.dumps(public_result, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")
    return public_result


__all__ = [
    "CASES",
    "CONTRACT_REF",
    "PACK_SCHEMA",
    "POLICY_SCHEMA",
    "RESULT_SCHEMA",
    "SixCaseLocalEvidencePackError",
    "canonical_digest",
    "compile_six_case_local_evidence_packs",
    "load_six_case_local_evidence_pack_policy",
    "materialize_six_case_local_evidence_packs",
    "validate_local_evidence_pack",
]
