from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Mapping, Sequence

from .public_context_source import (
    PUBLIC_CONTEXT_CANDIDATE_SCHEMA_VERSION,
    PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION,
    PUBLIC_PDF_SOURCE_OBJECT_SCHEMA_VERSION,
)
from .query_plan import canonical_digest


PUBLIC_CONTEXT_EVIDENCE_PLAN_SCHEMA_VERSION = (
    "fin_ia_s1_public_context_evidence_adjudication_plan_v1_0"
)
PUBLIC_CONTEXT_EVIDENCE_RESULT_SCHEMA_VERSION = (
    "fin_ia_s1_public_context_evidence_gate_result_v1_0"
)
_ACTIONS = {"accept_as_bounded_context", "reject_from_current_scope"}


class PublicContextEvidenceError(ValueError):
    """A public context candidate lost source, proposition or use boundaries."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise PublicContextEvidenceError(code)


def _validated_digest(value: Mapping[str, Any], field: str, code: str) -> None:
    body = deepcopy(dict(value))
    digest = str(body.pop(field, ""))
    _require(digest == canonical_digest(body), code)


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


def _speaker_authority_id(source: Mapping[str, Any]) -> str:
    ticker = str(source.get("speaker_ticker") or "").strip().upper()
    if ticker:
        return ticker
    entity = str(source.get("speaker_entity") or "").strip()
    _require(entity, "public_context_evidence_speaker_identity_missing")
    return "ORG::" + canonical_digest({"speaker_entity": entity})[:16].upper()


def adjudicate_public_context_evidence(
    *,
    compiled_result: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> dict[str, Any]:
    """Turn reviewed public-source candidates into bounded context Evidence.

    This is an internal engineering adjudication, not qualified-human acceptance.
    It may preserve exact industry or speaker facts, but it never grants the
    external source Dell-specific numeric, causal, allocation or profit authority.
    """

    _validated_digest(compiled_result, "result_digest", "public_context_compiled_result_digest_invalid")
    _validated_digest(plan, "plan_digest", "public_context_evidence_plan_digest_invalid")
    case_key = str(plan.get("case_key") or "").upper()
    research_as_of = str(plan.get("research_as_of") or "")
    _require(
        compiled_result.get("schema_version")
        == "fin_ia_s1_public_context_admission_result_v1_0"
        and compiled_result.get("status")
        == "public_context_candidates_compiled_evidence_admission_pending"
        and plan.get("schema_version")
        == PUBLIC_CONTEXT_EVIDENCE_PLAN_SCHEMA_VERSION
        and plan.get("status") == "approved_internal_engineering_adjudication"
        and str(compiled_result.get("case_key") or "").upper() == case_key
        and str(compiled_result.get("research_as_of") or "") == research_as_of
        and str(plan.get("compiled_result_digest") or "")
        == str(compiled_result.get("result_digest") or "")
        and plan.get("qualified_human_review") is False
        and plan.get("S1_qualification_authorized") is False
        and plan.get("product_publication_authorized") is False,
        "public_context_evidence_plan_binding_invalid",
    )
    sources = {
        str(row.get("source_id") or ""): dict(row)
        for row in compiled_result.get("source_objects") or ()
    }
    candidates = {
        str(row.get("candidate_id") or ""): dict(row)
        for row in compiled_result.get("candidates") or ()
    }
    _require(
        sources
        and candidates
        and len(sources) == len(compiled_result.get("source_objects") or ())
        and len(candidates) == len(compiled_result.get("candidates") or ()),
        "public_context_evidence_compiled_identity_duplicate",
    )
    decisions = [dict(row) for row in plan.get("decisions") or ()]
    decision_by_id = {
        str(row.get("candidate_id") or ""): row for row in decisions
    }
    _require(
        len(decisions) == len(decision_by_id)
        and set(decision_by_id) == set(candidates),
        "public_context_evidence_decision_coverage_invalid",
    )

    accepted_items: list[dict[str, Any]] = []
    source_materials: list[dict[str, Any]] = []
    rejected_items: list[dict[str, Any]] = []
    decision_receipts: list[dict[str, Any]] = []
    gap_ids_narrowed: set[str] = set()
    gap_ids_satisfied: set[str] = set()
    for candidate_id in sorted(candidates):
        candidate = candidates[candidate_id]
        decision = decision_by_id[candidate_id]
        source_id = str(candidate.get("source_id") or "")
        source = sources.get(source_id)
        action = str(decision.get("action") or "")
        _require(
            source is not None
            and candidate.get("schema_version")
            == PUBLIC_CONTEXT_CANDIDATE_SCHEMA_VERSION
            and source.get("schema_version")
            in {
                PUBLIC_HTML_SOURCE_OBJECT_SCHEMA_VERSION,
                PUBLIC_PDF_SOURCE_OBJECT_SCHEMA_VERSION,
            }
            and str(candidate.get("candidate_digest") or "")
            == str(decision.get("candidate_digest") or "")
            and str(candidate.get("source_object_digest") or "")
            == str(source.get("source_object_digest") or "")
            and str(candidate.get("source_object_digest") or "")
            == str(decision.get("source_object_digest") or "")
            and str(candidate.get("proposition_id") or "")
            == str(decision.get("proposition_id") or "")
            and candidate.get("candidate_not_evidence") is True
            and action in _ACTIONS,
            "public_context_evidence_candidate_binding_invalid",
        )
        _validated_digest(
            candidate,
            "candidate_digest",
            "public_context_evidence_candidate_digest_invalid",
        )
        _validated_digest(
            source,
            "source_object_digest",
            "public_context_evidence_source_digest_invalid",
        )
        use_decision = dict(candidate.get("source_use_decision") or {})
        _validated_digest(
            use_decision,
            "decision_digest",
            "public_context_evidence_source_use_digest_invalid",
        )
        narrowed = {
            str(value) for value in decision.get("gap_ids_narrowed") or () if str(value)
        }
        satisfied = {
            str(value) for value in decision.get("gap_ids_satisfied") or () if str(value)
        }
        _require(
            not satisfied,
            "public_context_evidence_target_gap_closure_forbidden",
        )
        gap_ids_narrowed.update(narrowed)
        gap_ids_satisfied.update(satisfied)

        if action == "reject_from_current_scope":
            _require(
                not decision.get("slot_bindings")
                and str(decision.get("reason_zh") or ""),
                "public_context_evidence_rejection_invalid",
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
                use_decision.get("evidence_promotion_allowed") is True
                and bindings
                and all(_valid_slot_binding(binding) for binding in bindings)
                and str(decision.get("numeric_use_boundary_zh") or "")
                and decision.get("causal_attribution_authorized") is False,
                "public_context_evidence_acceptance_invalid",
            )
            source_text = str(candidate.get("excerpt") or "")
            source_content_digest = hashlib.sha256(
                source_text.encode("utf-8")
            ).hexdigest()
            material_ref = "source_material_public_" + canonical_digest(
                {
                    "candidate_id": candidate_id,
                    "source_content_digest": source_content_digest,
                }
            )[:24]
            source_materials.append(
                {
                    "material_ref": material_ref,
                    "source_record_id": source_id,
                    "source_text": source_text,
                    "source_text_digest": source_content_digest,
                    "source_url": source.get("source_url"),
                    "source_type": source.get("source_type"),
                    "source_tier": source.get("source_class"),
                    "publication_date": source.get("publication_date"),
                    "period_end": None,
                    # This legacy consumer key carries the disclosure-owner
                    # identity.  Untickered industry bodies receive a stable
                    # ORG identifier so their facts cannot drift to Dell.
                    "evidence_owner_ticker": _speaker_authority_id(source),
                    "speaker_entity": source.get("speaker_entity"),
                    "license_scope": "public_web_private_research_capture",
                    "redistributable": False,
                    "raw_capture_sha256": source.get("capture_sha256"),
                    "body_sha256": source.get("body_sha256"),
                }
            )
            bound_rows = []
            for binding in bindings:
                bound_rows.append(
                    {
                        **binding,
                        "binding_kind": "request_context",
                        "qualification_id": str(plan.get("plan_id") or ""),
                        "proposition_id": candidate.get("proposition_id"),
                        "claim_use": candidate.get("claim_use"),
                    }
                )
            item_body = {
                "case_key": case_key,
                "causal_attribution_authorized": False,
                "disposition": "accepted_bounded_context_evidence",
                "evidence_role": "counterparty_or_ecosystem_readthrough",
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
                "source_record_id": source_id,
                "source_reporting_period_end": None,
                "target_id": "PUBEV::" + canonical_digest(
                    {
                        "candidate_id": candidate_id,
                        "plan_id": plan.get("plan_id"),
                    }
                )[:20].upper(),
                "writer_citable": True,
                "speaker_entity": source.get("speaker_entity"),
                "proposition_id": candidate.get("proposition_id"),
                "claim_use": candidate.get("claim_use"),
            }
            accepted_items.append(
                {
                    **item_body,
                    "evidence_item_digest": canonical_digest(item_body),
                }
            )

        receipt_body = {
            "candidate_id": candidate_id,
            "candidate_digest": candidate.get("candidate_digest"),
            "source_id": source_id,
            "source_object_digest": source.get("source_object_digest"),
            "proposition_id": candidate.get("proposition_id"),
            "action": action,
            "gap_ids_narrowed": sorted(narrowed),
            "gap_ids_satisfied": sorted(satisfied),
            "adjudicator_class": "internal_engineering_not_qualified_human",
            "target_company_numeric_authority_granted": False,
            "causal_attribution_authorized": False,
            "S1_qualification_authorized": False,
        }
        decision_receipts.append(
            {**receipt_body, "receipt_digest": canonical_digest(receipt_body)}
        )

    _require(accepted_items, "public_context_evidence_no_accepted_items")
    body = {
        "schema_version": PUBLIC_CONTEXT_EVIDENCE_RESULT_SCHEMA_VERSION,
        "status": "public_context_evidence_gate_passed_internal_engineering",
        "consumer_case_key": case_key,
        "research_as_of": research_as_of,
        "plan_id": plan.get("plan_id"),
        "plan_digest": plan.get("plan_digest"),
        "compiled_result_digest": compiled_result.get("result_digest"),
        "accepted_evidence_items": accepted_items,
        "source_materials": source_materials,
        "rejected_items": rejected_items,
        "decision_receipts": decision_receipts,
        "gap_ids_narrowed": sorted(gap_ids_narrowed),
        "gap_ids_satisfied": sorted(gap_ids_satisfied),
        "gap_satisfied": False,
        "evidence_qualified": True,
        "candidate_is_not_evidence": False,
        "causal_attribution_authorized": False,
        "authority": {
            "internal_engineering_adjudication": True,
            "qualified_human_review": False,
            "S1_qualification": False,
            "product_publication": False,
            "target_company_exact_numeric_authority": False,
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


__all__ = [
    "PUBLIC_CONTEXT_EVIDENCE_PLAN_SCHEMA_VERSION",
    "PUBLIC_CONTEXT_EVIDENCE_RESULT_SCHEMA_VERSION",
    "PublicContextEvidenceError",
    "adjudicate_public_context_evidence",
]
