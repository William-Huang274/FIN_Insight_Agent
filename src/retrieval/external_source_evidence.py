from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from .public_context_source import (
    PUBLIC_CONTEXT_CANDIDATE_SCHEMA_VERSION,
    PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION,
    PUBLIC_PDF_SOURCE_OBJECT_SCHEMA_VERSION,
    compile_public_context_candidate,
)
from .query_plan import canonical_digest
from .source_use_policy import SourceUsePolicy


EXTERNAL_SOURCE_REVIEW_PLAN_SCHEMA_VERSION = (
    "fin_ia_s1_external_source_candidate_review_plan_v1_0"
)
EXTERNAL_SOURCE_REVIEW_RESULT_SCHEMA_VERSION = (
    "fin_ia_s1_external_source_candidate_review_result_v1_0"
)
EXTERNAL_SOURCE_EVIDENCE_PLAN_SCHEMA_VERSION = (
    "fin_ia_s1_external_source_evidence_adjudication_plan_v1_0"
)
EXTERNAL_SOURCE_EVIDENCE_RESULT_SCHEMA_VERSION = (
    "fin_ia_s1_external_source_evidence_gate_result_v1_0"
)

_SOURCE_OBJECT_SCHEMAS = {
    PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION,
    PUBLIC_PDF_SOURCE_OBJECT_SCHEMA_VERSION,
}
_REVIEWABLE_LADDER_TERMINAL_STATUSES = {
    "dell_external_source_ladder_exact_once_complete",
    "dell_external_capture_replay_complete",
}
_PROPOSAL_ACTIONS = {
    "accept_as_reviewed_candidate",
    "replace_with_capture_bound_reviewed_candidate",
    "reject_duplicate_or_out_of_scope",
}
_EVIDENCE_ACTIONS = {"accept_as_evidence", "reject_from_current_pack"}
_DIRECT_CLAIM_USES = {
    "target_company_exact_fact",
    "target_company_exact_numeric_fact",
}


class ExternalSourceEvidenceError(ValueError):
    """A source review or Evidence Gate lost capture, use or claim boundaries."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ExternalSourceEvidenceError(code)


def _validated_digest(value: Mapping[str, Any], field: str, code: str) -> None:
    body = deepcopy(dict(value))
    digest = str(body.pop(field, ""))
    _require(digest == canonical_digest(body), code)


def _source_family(source: Mapping[str, Any]) -> str:
    host = str(urlsplit(str(source.get("source_url") or "")).hostname or "").lower()
    _require(host, "external_source_review_source_host_missing")
    return host[4:] if host.startswith("www.") else host


def _speaker_authority_id(source: Mapping[str, Any]) -> str:
    ticker = str(source.get("speaker_ticker") or "").strip().upper()
    if ticker:
        return ticker
    entity = str(source.get("speaker_entity") or "").strip()
    _require(entity, "external_source_evidence_speaker_identity_missing")
    return "ORG::" + canonical_digest({"speaker_entity": entity})[:16].upper()


def _valid_slot_binding(value: Any) -> bool:
    return bool(
        isinstance(value, Mapping)
        and str(value.get("slot_id") or "")
        and isinstance(value.get("facet_ids"), list)
        and value["facet_ids"]
        and all(str(facet).strip() for facet in value["facet_ids"])
        and isinstance(value.get("requirement_ids"), list)
        and str(value.get("business_meaning_zh") or "")
        and str(value.get("claim_boundary_zh") or "")
    )


def compile_external_source_candidate_review(
    *,
    ladder_terminal: Mapping[str, Any],
    plan: Mapping[str, Any],
    source_use_policy: SourceUsePolicy,
) -> dict[str, Any]:
    """Compile an exhaustive human-readable review of one captured source ladder.

    Every deterministic proposal receives an explicit disposition.  Reviewed
    candidates may also bind a better exact excerpt from the same immutable
    source object, which allows a weak locator proposal to be replaced without
    treating Harness text selection as research authority.
    """

    _validated_digest(plan, "plan_digest", "external_source_review_plan_digest_invalid")
    _validated_digest(
        ladder_terminal,
        "result_digest",
        "external_source_review_terminal_digest_invalid",
    )
    _require(
        plan.get("schema_version") == EXTERNAL_SOURCE_REVIEW_PLAN_SCHEMA_VERSION
        and plan.get("status") == "approved_internal_engineering_candidate_review"
        and ladder_terminal.get("status") in _REVIEWABLE_LADDER_TERMINAL_STATUSES
        and str(plan.get("case_key") or "").upper() == "DELL"
        and str(plan.get("ladder_terminal_result_digest") or "")
        == str(ladder_terminal.get("result_digest") or ""),
        "external_source_review_plan_binding_invalid",
    )
    compilation = dict(ladder_terminal.get("original_compilation_result") or {})
    source_rows = [dict(row) for row in compilation.get("source_objects") or ()]
    proposal_rows = [
        dict(row) for row in compilation.get("candidate_proposals") or ()
    ]
    sources = {str(row.get("source_id") or ""): row for row in source_rows}
    proposals = {
        str(row.get("candidate_proposal_digest") or ""): row
        for row in proposal_rows
    }
    _require(
        source_rows
        and proposal_rows
        and len(sources) == len(source_rows)
        and len(proposals) == len(proposal_rows),
        "external_source_review_source_or_proposal_identity_invalid",
    )
    for source in source_rows:
        _require(
            source.get("schema_version") in _SOURCE_OBJECT_SCHEMAS,
            "external_source_review_source_schema_invalid",
        )
        _validated_digest(
            source,
            "source_object_digest",
            "external_source_review_source_digest_invalid",
        )
    for proposal in proposal_rows:
        _validated_digest(
            proposal,
            "candidate_proposal_digest",
            "external_source_review_proposal_digest_invalid",
        )

    dispositions = [
        dict(row) for row in plan.get("original_proposal_dispositions") or ()
    ]
    disposition_by_digest = {
        str(row.get("candidate_proposal_digest") or ""): row
        for row in dispositions
    }
    _require(
        len(dispositions) == len(disposition_by_digest)
        and set(disposition_by_digest) == set(proposals)
        and all(
            str(row.get("action") or "") in _PROPOSAL_ACTIONS
            and str(row.get("reason_zh") or "")
            for row in dispositions
        ),
        "external_source_review_proposal_disposition_coverage_invalid",
    )

    specs = [dict(row) for row in plan.get("reviewed_candidate_specs") or ()]
    spec_by_key = {str(row.get("review_candidate_key") or ""): row for row in specs}
    _require(
        specs
        and len(specs) == len(spec_by_key)
        and all(spec_by_key),
        "external_source_review_candidate_key_invalid",
    )
    origin_to_keys: dict[str, list[str]] = {digest: [] for digest in proposals}
    for key, spec in spec_by_key.items():
        origins = [
            str(value)
            for value in spec.get("origin_candidate_proposal_digests") or ()
        ]
        _require(
            len(origins) == len(set(origins))
            and set(origins).issubset(proposals),
            "external_source_review_candidate_origin_invalid",
        )
        for origin in origins:
            origin_to_keys[origin].append(key)
        if not origins:
            _require(
                str(spec.get("supplemental_reason_zh") or ""),
                "external_source_review_supplemental_reason_missing",
            )

    for digest, disposition in disposition_by_digest.items():
        action = str(disposition["action"])
        keys = origin_to_keys[digest]
        if action == "reject_duplicate_or_out_of_scope":
            _require(not keys, "external_source_review_rejected_proposal_reused")
        else:
            _require(
                len(keys) == 1
                and str(disposition.get("review_candidate_key") or "") == keys[0],
                "external_source_review_accepted_proposal_candidate_binding_invalid",
            )
            if action == "accept_as_reviewed_candidate":
                spec = spec_by_key[keys[0]]
                proposal = proposals[digest]
                _require(
                    str(spec.get("source_id") or "")
                    == str(proposal.get("source_id") or "")
                    and str(spec.get("proposition_id") or "")
                    == str(proposal.get("proposition_id") or "")
                    and str(spec.get("excerpt_source_kind") or "")
                    == "original_proposal",
                    "external_source_review_direct_acceptance_binding_invalid",
                )

    compiled_candidates: list[dict[str, Any]] = []
    review_receipts: list[dict[str, Any]] = []
    for key in sorted(spec_by_key):
        spec = spec_by_key[key]
        source_id = str(spec.get("source_id") or "")
        source = sources.get(source_id)
        _require(source is not None, "external_source_review_candidate_source_unknown")
        source_kind = str(spec.get("excerpt_source_kind") or "")
        origins = [
            str(value)
            for value in spec.get("origin_candidate_proposal_digests") or ()
        ]
        if source_kind == "original_proposal":
            _require(
                len(origins) == 1,
                "external_source_review_original_excerpt_origin_invalid",
            )
            excerpt = str(proposals[origins[0]].get("excerpt") or "")
        elif source_kind == "source_segment_substring":
            excerpt = str(spec.get("excerpt") or "")
        else:
            raise ExternalSourceEvidenceError(
                "external_source_review_excerpt_source_kind_invalid"
            )

        corroborating_ids = [
            str(value) for value in spec.get("corroborating_source_ids") or ()
        ]
        _require(
            len(corroborating_ids) == len(set(corroborating_ids))
            and source_id not in corroborating_ids
            and all(value in sources for value in corroborating_ids),
            "external_source_review_corroboration_binding_invalid",
        )
        independent_families = {
            _source_family(source),
            *(_source_family(sources[value]) for value in corroborating_ids),
        }
        _require(
            len(independent_families) == 1 + len(corroborating_ids),
            "external_source_review_corroboration_not_independent",
        )
        candidate = compile_public_context_candidate(
            source_object=source,
            candidate_spec={
                "proposition_id": str(spec.get("proposition_id") or ""),
                "excerpt": excerpt,
                "claim_use": str(spec.get("claim_use") or ""),
                "speaker_bound": spec.get("speaker_bound") is True,
                "subject_bound": spec.get("subject_bound") is True,
                "independent_source_count": len(independent_families),
                "license_entitled": spec.get("license_entitled") is True,
            },
            source_use_policy=source_use_policy,
        )
        _require(
            candidate.get("source_use_decision", {}).get(
                "evidence_promotion_allowed"
            )
            is True,
            "external_source_review_candidate_source_use_rejected",
        )
        compiled_candidates.append(candidate)
        receipt_body = {
            "review_candidate_key": key,
            "candidate_id": candidate["candidate_id"],
            "candidate_digest": candidate["candidate_digest"],
            "source_id": source_id,
            "source_family": _source_family(source),
            "proposition_id": candidate["proposition_id"],
            "claim_use": candidate["claim_use"],
            "origin_candidate_proposal_digests": sorted(origins),
            "corroborating_source_ids": sorted(corroborating_ids),
            "independent_source_count": len(independent_families),
            "business_reason_zh": str(spec.get("business_reason_zh") or ""),
            "candidate_not_evidence": True,
        }
        _require(
            receipt_body["business_reason_zh"],
            "external_source_review_candidate_business_reason_missing",
        )
        review_receipts.append(
            {**receipt_body, "receipt_digest": canonical_digest(receipt_body)}
        )

    body = {
        "schema_version": EXTERNAL_SOURCE_REVIEW_RESULT_SCHEMA_VERSION,
        "status": "external_source_candidates_reviewed_evidence_gate_pending",
        "case_key": "DELL",
        "research_as_of": str(plan.get("research_as_of") or ""),
        "plan_id": str(plan.get("plan_id") or ""),
        "plan_digest": str(plan.get("plan_digest") or ""),
        "ladder_terminal_result_digest": str(ladder_terminal.get("result_digest") or ""),
        "source_use_policy_id": source_use_policy.policy_id,
        "source_objects": source_rows,
        "candidates": compiled_candidates,
        "original_proposal_dispositions": dispositions,
        "candidate_review_receipts": review_receipts,
        "summary": {
            "source_object_count": len(source_rows),
            "original_proposal_count": len(proposal_rows),
            "original_proposal_accepted_or_replaced_count": sum(
                row["action"] != "reject_duplicate_or_out_of_scope"
                for row in dispositions
            ),
            "original_proposal_rejected_count": sum(
                row["action"] == "reject_duplicate_or_out_of_scope"
                for row in dispositions
            ),
            "reviewed_candidate_count": len(compiled_candidates),
            "supplemental_candidate_count": sum(
                not row.get("origin_candidate_proposal_digests") for row in specs
            ),
            "candidate_evidence_promotions": 0,
            "model_calls": 0,
            "network_calls": 0,
        },
        "authority": {
            "candidate_not_evidence": True,
            "internal_engineering_review": True,
            "qualified_human_review": False,
            "S1_qualification": False,
            "product_publication": False,
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


def adjudicate_external_source_evidence(
    *,
    compiled_result: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Promote reviewed external candidates with source-specific Evidence roles."""

    _validated_digest(
        compiled_result,
        "result_digest",
        "external_source_evidence_compiled_digest_invalid",
    )
    _validated_digest(plan, "plan_digest", "external_source_evidence_plan_digest_invalid")
    case_key = str(plan.get("case_key") or "").upper()
    research_as_of = str(plan.get("research_as_of") or "")
    _require(
        compiled_result.get("schema_version")
        == EXTERNAL_SOURCE_REVIEW_RESULT_SCHEMA_VERSION
        and compiled_result.get("status")
        == "external_source_candidates_reviewed_evidence_gate_pending"
        and plan.get("schema_version")
        == EXTERNAL_SOURCE_EVIDENCE_PLAN_SCHEMA_VERSION
        and plan.get("status") == "approved_internal_engineering_evidence_gate"
        and case_key == str(compiled_result.get("case_key") or "").upper()
        and research_as_of == str(compiled_result.get("research_as_of") or "")
        and str(plan.get("compiled_result_digest") or "")
        == str(compiled_result.get("result_digest") or "")
        and plan.get("qualified_human_review") is False
        and plan.get("S1_qualification_authorized") is False
        and plan.get("product_publication_authorized") is False,
        "external_source_evidence_plan_binding_invalid",
    )
    source_rows = [dict(row) for row in compiled_result.get("source_objects") or ()]
    candidate_rows = [dict(row) for row in compiled_result.get("candidates") or ()]
    sources = {str(row.get("source_id") or ""): row for row in source_rows}
    candidates = {str(row.get("candidate_id") or ""): row for row in candidate_rows}
    decisions = [dict(row) for row in plan.get("decisions") or ()]
    decision_by_id = {str(row.get("candidate_id") or ""): row for row in decisions}
    _require(
        len(sources) == len(source_rows)
        and len(candidates) == len(candidate_rows)
        and len(decision_by_id) == len(decisions)
        and set(decision_by_id) == set(candidates),
        "external_source_evidence_decision_coverage_invalid",
    )

    accepted_items: list[dict[str, Any]] = []
    source_materials: list[dict[str, Any]] = []
    rejected_items: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    narrowed_gaps: set[str] = set()
    for candidate_id in sorted(candidates):
        candidate = candidates[candidate_id]
        decision = decision_by_id[candidate_id]
        source = sources.get(str(candidate.get("source_id") or ""))
        action = str(decision.get("action") or "")
        _require(
            source is not None
            and candidate.get("schema_version") == PUBLIC_CONTEXT_CANDIDATE_SCHEMA_VERSION
            and str(candidate.get("candidate_digest") or "")
            == str(decision.get("candidate_digest") or "")
            and str(candidate.get("source_object_digest") or "")
            == str(source.get("source_object_digest") or "")
            and str(candidate.get("source_object_digest") or "")
            == str(decision.get("source_object_digest") or "")
            and str(candidate.get("proposition_id") or "")
            == str(decision.get("proposition_id") or "")
            and action in _EVIDENCE_ACTIONS,
            "external_source_evidence_candidate_binding_invalid",
        )
        _validated_digest(
            candidate,
            "candidate_digest",
            "external_source_evidence_candidate_digest_invalid",
        )
        _validated_digest(
            source,
            "source_object_digest",
            "external_source_evidence_source_digest_invalid",
        )
        source_use = dict(candidate.get("source_use_decision") or {})
        _validated_digest(
            source_use,
            "decision_digest",
            "external_source_evidence_source_use_digest_invalid",
        )
        narrowed = {
            str(value) for value in decision.get("gap_ids_narrowed") or () if str(value)
        }
        satisfied = {
            str(value) for value in decision.get("gap_ids_satisfied") or () if str(value)
        }
        _require(
            not satisfied,
            "external_source_evidence_gap_closure_requires_separate_receipt",
        )
        narrowed_gaps.update(narrowed)

        if action == "reject_from_current_pack":
            _require(
                not decision.get("slot_bindings")
                and str(decision.get("reason_zh") or ""),
                "external_source_evidence_rejection_invalid",
            )
            rejected_items.append(
                {
                    "candidate_id": candidate_id,
                    "proposition_id": candidate.get("proposition_id"),
                    "reason_zh": decision.get("reason_zh"),
                    "writer_citable": False,
                }
            )
        else:
            bindings = [dict(row) for row in decision.get("slot_bindings") or ()]
            _require(
                source_use.get("evidence_promotion_allowed") is True
                and bindings
                and all(_valid_slot_binding(binding) for binding in bindings)
                and str(decision.get("numeric_use_boundary_zh") or "")
                and decision.get("causal_attribution_authorized") is False,
                "external_source_evidence_acceptance_invalid",
            )
            claim_use = str(candidate.get("claim_use") or "")
            direct = bool(
                str(source.get("source_class") or "")
                == "issuer_regulator_or_government_primary"
                and str(source.get("speaker_ticker") or "").upper() == case_key
                and claim_use in _DIRECT_CLAIM_USES
            )
            exact_numeric = direct and claim_use == "target_company_exact_numeric_fact"
            source_text = str(candidate.get("excerpt") or "")
            source_content_digest = hashlib.sha256(
                source_text.encode("utf-8")
            ).hexdigest()
            material_ref = "source_material_external_" + canonical_digest(
                {
                    "candidate_id": candidate_id,
                    "source_content_digest": source_content_digest,
                }
            )[:24]
            source_materials.append(
                {
                    "material_ref": material_ref,
                    "source_record_id": source.get("source_id"),
                    "source_text": source_text,
                    "source_text_digest": source_content_digest,
                    "source_url": source.get("source_url"),
                    "source_type": source.get("source_type"),
                    "source_tier": source.get("source_class"),
                    "publication_date": source.get("publication_date"),
                    "period_end": None,
                    "evidence_owner_ticker": _speaker_authority_id(source),
                    "speaker_entity": source.get("speaker_entity"),
                    "license_scope": "public_web_private_research_capture",
                    "redistributable": False,
                    "raw_capture_sha256": source.get("capture_sha256"),
                    "body_sha256": source.get("body_sha256"),
                }
            )
            bound_rows = [
                {
                    **binding,
                    "binding_kind": "request_context",
                    "qualification_id": str(plan.get("plan_id") or ""),
                    "proposition_id": candidate.get("proposition_id"),
                    "claim_use": claim_use,
                }
                for binding in bindings
            ]
            item_body = {
                "case_key": case_key,
                "causal_attribution_authorized": False,
                "disposition": (
                    "accepted_direct_source_evidence"
                    if direct
                    else "accepted_bounded_context_evidence"
                ),
                "evidence_role": (
                    "issuer_direct_source"
                    if direct
                    else "counterparty_or_ecosystem_readthrough"
                ),
                "numeric_use_boundary": decision.get("numeric_use_boundary_zh"),
                "object_type": "claim",
                "publication_date": source.get("publication_date"),
                "relationship_directions": deepcopy(
                    source.get("relationship_directions") or []
                ),
                "research_as_of": research_as_of,
                "slot_bindings": bound_rows,
                "source_content_digest": source_content_digest,
                "source_material_ref": material_ref,
                "source_record_id": source.get("source_id"),
                "source_reporting_period_end": None,
                "target_id": "EXTEV::" + canonical_digest(
                    {"candidate_id": candidate_id, "plan_id": plan.get("plan_id")}
                )[:20].upper(),
                "writer_citable": True,
                "speaker_entity": source.get("speaker_entity"),
                "proposition_id": candidate.get("proposition_id"),
                "claim_use": claim_use,
                "target_company_exact_numeric_authority": exact_numeric,
            }
            accepted_items.append(
                {**item_body, "evidence_item_digest": canonical_digest(item_body)}
            )

        receipt_body = {
            "candidate_id": candidate_id,
            "candidate_digest": candidate.get("candidate_digest"),
            "source_id": source.get("source_id") if source else None,
            "source_object_digest": source.get("source_object_digest") if source else None,
            "proposition_id": candidate.get("proposition_id"),
            "action": action,
            "gap_ids_narrowed": sorted(narrowed),
            "gap_ids_satisfied": [],
            "adjudicator_class": "internal_engineering_not_qualified_human",
            "causal_attribution_authorized": False,
            "S1_qualification_authorized": False,
        }
        receipts.append(
            {**receipt_body, "receipt_digest": canonical_digest(receipt_body)}
        )

    _require(accepted_items, "external_source_evidence_no_accepted_items")
    body = {
        "schema_version": EXTERNAL_SOURCE_EVIDENCE_RESULT_SCHEMA_VERSION,
        "status": "external_source_evidence_gate_passed_internal_engineering",
        "consumer_case_key": case_key,
        "research_as_of": research_as_of,
        "plan_id": str(plan.get("plan_id") or ""),
        "plan_digest": str(plan.get("plan_digest") or ""),
        "compiled_result_digest": str(compiled_result.get("result_digest") or ""),
        "accepted_evidence_items": accepted_items,
        "source_materials": source_materials,
        "rejected_items": rejected_items,
        "decision_receipts": receipts,
        "gap_ids_narrowed": sorted(narrowed_gaps),
        "gap_ids_satisfied": [],
        "gap_satisfied": False,
        "evidence_qualified": True,
        "candidate_is_not_evidence": False,
        "causal_attribution_authorized": False,
        "authority": {
            "internal_engineering_adjudication": True,
            "qualified_human_review": False,
            "S1_qualification": False,
            "product_publication": False,
            "target_company_exact_numeric_authority_count": sum(
                row.get("target_company_exact_numeric_authority") is True
                for row in accepted_items
            ),
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


__all__ = [
    "EXTERNAL_SOURCE_EVIDENCE_PLAN_SCHEMA_VERSION",
    "EXTERNAL_SOURCE_EVIDENCE_RESULT_SCHEMA_VERSION",
    "EXTERNAL_SOURCE_REVIEW_PLAN_SCHEMA_VERSION",
    "EXTERNAL_SOURCE_REVIEW_RESULT_SCHEMA_VERSION",
    "ExternalSourceEvidenceError",
    "adjudicate_external_source_evidence",
    "compile_external_source_candidate_review",
]
