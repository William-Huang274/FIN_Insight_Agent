from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from .product_pack_readiness import PRODUCT_DECISION_LEDGER_SCHEMA_VERSION
from .query_plan import canonical_digest


PRODUCT_CANDIDATE_REVIEW_PACKET_SCHEMA_VERSION = (
    "fin_ia_s1_product_candidate_review_packet_v1_0"
)
DEFAULT_REVIEW_EXCERPT_CHARS = 560
MAX_REVIEW_EXCERPT_CHARS = 800
MAX_CONTEXT_ONLY_ITEMS_PER_REQUEST = 2


class ProductCandidateReviewError(ValueError):
    """Raised when a Candidate review projection cannot preserve lineage."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ProductCandidateReviewError(code)


def _mapping(value: object, code: str) -> Mapping[str, Any]:
    _require(isinstance(value, Mapping), code)
    return value


def _bounded_excerpt(value: object, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    _require(bool(text), "product_candidate_review_excerpt_missing")
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _safe_source_url(value: object) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    parsed = urlparse(url)
    _require(
        parsed.scheme in {"http", "https"} and bool(parsed.netloc),
        "product_candidate_review_source_url_invalid",
    )
    return url


def _issue_classes(decision: Mapping[str, Any]) -> list[str]:
    if decision.get("decision_state") == "accepted":
        return ["existing_reviewed_evidence_reuse"]
    reasons = set(str(value) for value in decision.get("reason_codes") or ())
    issues: list[str] = []
    if "new_candidate_requires_evidence_gate" in reasons:
        issues.append("new_candidate_evidence_adjudication")
    if "reviewed_item_not_bound_to_exact_compiled_object" in reasons:
        issues.append("reviewed_pack_exact_object_binding")
    if reasons.intersection(
        {
            "reviewed_item_outside_compiled_slot",
            "reviewed_item_facet_not_bound_to_current_request",
        }
    ):
        issues.append("reviewed_pack_slot_facet_binding")
    if reasons.intersection(
        {
            "cross_case_reviewed_item",
            "reviewed_item_owner_outside_compiled_lane",
            "reviewed_item_source_type_mismatch",
            "reviewed_item_source_type_outside_compiled_lane",
            "reviewed_item_after_research_as_of",
            "reviewed_item_relationship_direction_mismatch",
            "reviewed_item_before_request_period",
            "reviewed_item_after_request_period",
        }
    ):
        issues.append("reviewed_pack_hard_boundary_mismatch")
    if reasons.intersection(
        {
            "reviewed_evidence_recalled_outside_current_material_review",
            "query_or_material_binding_requires_adjudication",
        }
    ):
        issues.append("request_material_binding")
    return sorted(set(issues or ["manual_candidate_review_required"]))


def _next_action(issue_classes: Sequence[str], decision_state: str) -> str:
    issues = set(issue_classes)
    if decision_state == "accepted":
        return "no_action_existing_reviewed_evidence_reuse"
    if "reviewed_pack_hard_boundary_mismatch" in issues:
        return "reject_or_rebind_only_after_source_boundary_review"
    if issues.intersection(
        {
            "reviewed_pack_exact_object_binding",
            "reviewed_pack_slot_facet_binding",
        }
    ):
        return "review_exact_object_and_pack_binding"
    if "new_candidate_evidence_adjudication" in issues:
        return "perform_human_evidence_gate"
    if "request_material_binding" in issues:
        return "review_requirement_alignment"
    return "perform_manual_candidate_review"


def _requirement_context(
    requirement: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "requirement_id": requirement.get("requirement_id"),
        "facet_id": requirement.get("facet_id"),
        "role": requirement.get("role"),
        "product_ids": list(requirement.get("product_ids") or ()),
        "metric_ids": list(requirement.get("metric_ids") or ()),
        "target_entities": list(requirement.get("target_entities") or ()),
        "candidate_set_complete_in_bounded_union": receipt.get("complete") is True,
        "missing_required_product_ids": list(
            receipt.get("missing_required_product_ids") or ()
        ),
        "missing_required_metric_ids": list(
            receipt.get("missing_required_metric_ids") or ()
        ),
    }


def compile_product_candidate_review_packet(
    *,
    product_projection: Mapping[str, Any],
    candidate_decision_ledgers: Sequence[Mapping[str, Any]],
    compiled_objects_by_id: Mapping[str, Mapping[str, Any]],
    source_records_by_id: Mapping[str, Mapping[str, Any]],
    recorded_at: str,
    excerpt_char_limit: int = DEFAULT_REVIEW_EXCERPT_CHARS,
) -> dict[str, Any]:
    """Join selected Candidate decisions to immutable object/source lineage.

    The packet is an internal human-review surface.  It never promotes text to
    Evidence and never grants S1, NumericFact, gap, or publication authority.
    """

    _require(
        120 <= excerpt_char_limit <= MAX_REVIEW_EXCERPT_CHARS,
        "product_candidate_review_excerpt_limit_invalid",
    )
    case_key = str(product_projection.get("case_key") or "").upper()
    _require(bool(case_key), "product_candidate_review_case_missing")
    request_results = [
        _mapping(row, "product_candidate_review_request_result_invalid")
        for row in product_projection.get("request_results") or ()
    ]
    ledger_by_request = {
        str(row.get("request_id") or ""): _mapping(
            row, "product_candidate_review_ledger_invalid"
        )
        for row in candidate_decision_ledgers
    }
    _require(
        len(request_results) == len(ledger_by_request),
        "product_candidate_review_ledger_cardinality_mismatch",
    )

    request_rows: list[dict[str, Any]] = []
    all_items: list[dict[str, Any]] = []
    for request_result in request_results:
        request = _mapping(
            request_result.get("request"),
            "product_candidate_review_request_missing",
        )
        request_id = str(request.get("request_id") or "")
        ledger = _mapping(
            ledger_by_request.get(request_id),
            f"product_candidate_review_ledger_missing:{request_id}",
        )
        _require(
            ledger.get("schema_version") == PRODUCT_DECISION_LEDGER_SCHEMA_VERSION
            and str(ledger.get("case_key") or "").upper() == case_key,
            "product_candidate_review_ledger_contract_invalid",
        )
        hybrid = _mapping(
            request_result.get("hybrid_object_retrieval"),
            "product_candidate_review_hybrid_missing",
        )
        material = _mapping(
            hybrid.get("material_evidence"),
            "product_candidate_review_material_missing",
        )
        plan = _mapping(
            material.get("requirement_plan"),
            "product_candidate_review_requirement_plan_missing",
        )
        selection = _mapping(
            material.get("selection"),
            "product_candidate_review_selection_missing",
        )
        requirements = {
            str(row.get("requirement_id") or ""): _mapping(
                row, "product_candidate_review_requirement_invalid"
            )
            for row in plan.get("requirement_groups") or ()
        }
        receipts = {
            str(row.get("requirement_id") or ""): _mapping(
                row, "product_candidate_review_requirement_receipt_invalid"
            )
            for row in selection.get("requirement_receipts") or ()
        }
        _require(
            requirements and set(requirements) == set(receipts),
            "product_candidate_review_requirement_set_invalid",
        )

        scope_ready = material.get("runtime_scope_ready") is True
        selected_ids = {
            str(value) for value in selection.get("selected_candidate_ids") or ()
        }
        decisions = [
            _mapping(row, "product_candidate_review_decision_invalid")
            for row in ledger.get("decisions") or ()
        ]
        primary = [
            row
            for row in decisions
            if row.get("decision_state") in {"accepted", "needs_human_review"}
            and bool(row.get("selected_requirement_ids"))
        ]
        context_only = sorted(
            (
                row
                for row in decisions
                if row.get("decision_state") == "needs_human_review"
                and not row.get("selected_requirement_ids")
                and str(row.get("compiled_object_id") or "") in selected_ids
            ),
            key=lambda row: (
                int(
                    _mapping(
                        row.get("rank_trace"),
                        "product_candidate_review_rank_trace_invalid",
                    ).get("review_priority_rank")
                    or 10**9
                ),
                str(row.get("candidate_ref") or ""),
            ),
        )[:MAX_CONTEXT_ONLY_ITEMS_PER_REQUEST]
        review_decisions = [] if not scope_ready else primary + context_only
        review_items: list[dict[str, Any]] = []
        for decision in review_decisions:
            object_id = str(decision.get("compiled_object_id") or "")
            compiled = _mapping(
                compiled_objects_by_id.get(object_id),
                f"product_candidate_review_compiled_object_missing:{object_id}",
            )
            base = _mapping(
                compiled.get("base_object_view"),
                "product_candidate_review_base_object_missing",
            )
            _require(
                compiled.get("candidate_not_evidence") is True
                and compiled.get("evidence_promoted") is False
                and compiled.get("numeric_authority") is False,
                "product_candidate_review_compiled_object_authority_invalid",
            )
            source_id = str(base.get("source_record_id") or "")
            source = _mapping(
                source_records_by_id.get(source_id),
                f"product_candidate_review_source_record_missing:{source_id}",
            )
            _require(
                str(source.get("ticker") or "").upper()
                == str(decision.get("evidence_owner_ticker") or "").upper(),
                "product_candidate_review_source_owner_mismatch",
            )
            requirement_ids = sorted(
                str(value) for value in decision.get("selected_requirement_ids") or ()
            )
            requirement_contexts = [
                _requirement_context(requirements[value], receipts[value])
                for value in requirement_ids
            ]
            role = _mapping(
                decision.get("advisory_evidence_role") or {},
                "product_candidate_review_role_invalid",
            )
            issues = _issue_classes(decision)
            lineage_body = {
                "compiled_object_id": object_id,
                "source_record_id": source_id,
                "source_record_digest": base.get("source_record_digest"),
                "surface_digest": base.get("surface_digest"),
                "lineage_source_record_ids": list(
                    compiled.get("lineage_source_record_ids") or ()
                ),
            }
            item_body = {
                "review_item_ref": decision.get("candidate_ref"),
                "request_id": request_id,
                "review_scope": (
                    "requirement_bound" if requirement_ids else "material_review_context"
                ),
                "compiled_object_id": object_id,
                "source_record_id": source_id,
                "source_lineage_digest": canonical_digest(lineage_body),
                "subject_ticker": decision.get("subject_ticker"),
                "evidence_owner_ticker": decision.get("evidence_owner_ticker"),
                "object_kind": decision.get("object_kind"),
                "source": {
                    "company": source.get("company"),
                    "source_type": source.get("source_type"),
                    "source_tier": source.get("source_tier"),
                    "publication_date": source.get("publication_date"),
                    "period_end": source.get("period_end"),
                    "section": source.get("section"),
                    "subsection": source.get("subsection"),
                    "source_url": _safe_source_url(source.get("source_url")),
                    "license_scope": source.get("license_scope"),
                    "redistributable": source.get("redistributable") is True,
                    "surface_digest": base.get("surface_digest"),
                    "bounded_excerpt": _bounded_excerpt(
                        compiled.get("model_text") or base.get("surface_text"),
                        excerpt_char_limit,
                    ),
                },
                "requirement_contexts": requirement_contexts,
                "advisory_evidence_role": {
                    "compatibility": role.get("compatibility"),
                    "labels": list(role.get("labels") or ()),
                    "reason_codes": list(role.get("reason_codes") or ()),
                    "advisory_only": True,
                },
                "rank_trace": deepcopy(decision.get("rank_trace") or {}),
                "route_membership": list(decision.get("route_membership") or ()),
                "decision_state": decision.get("decision_state"),
                "reason_codes": list(decision.get("reason_codes") or ()),
                "issue_classes": issues,
                "next_legal_action": _next_action(
                    issues, str(decision.get("decision_state") or "")
                ),
                "human_review_required": decision.get("decision_state")
                == "needs_human_review",
                "candidate_is_not_evidence": True,
                "candidate_text_promoted": False,
                "new_evidence_created": False,
                "numeric_authority": False,
            }
            review_items.append(
                {**item_body, "review_item_digest": canonical_digest(item_body)}
            )

        issue_counts = Counter(
            issue
            for item in review_items
            for issue in item.get("issue_classes") or ()
        )
        requirement_rows = [
            _requirement_context(requirement, receipts[requirement_id])
            for requirement_id, requirement in requirements.items()
        ]
        request_body = {
            "request_id": request_id,
            "slot_id": ledger.get("slot_id"),
            "facet_id": ledger.get("facet_id"),
            "business_question_zh": _mapping(
                (request_result.get("lanes") or [{}])[0],
                "product_candidate_review_lane_projection_invalid",
            ).get("lane", {}).get("business_question_zh"),
            "material_scope_ready": scope_ready,
            "requirement_count": len(requirement_rows),
            "requirements": requirement_rows,
            "review_item_count": len(review_items),
            "human_review_required_count": sum(
                item["human_review_required"] for item in review_items
            ),
            "issue_class_counts": dict(sorted(issue_counts.items())),
            "review_items": review_items,
        }
        request_rows.append(
            {**request_body, "request_review_digest": canonical_digest(request_body)}
        )
        all_items.extend(review_items)

    issue_counts = Counter(
        issue for item in all_items for issue in item.get("issue_classes") or ()
    )
    body = {
        "schema_version": PRODUCT_CANDIDATE_REVIEW_PACKET_SCHEMA_VERSION,
        "status": "candidate_review_packet_materialized_no_promotion",
        "recorded_at": recorded_at,
        "case_key": case_key,
        "request_count": len(request_rows),
        "review_item_count": len(all_items),
        "human_review_required_count": sum(
            item["human_review_required"] for item in all_items
        ),
        "issue_class_counts": dict(sorted(issue_counts.items())),
        "requests": request_rows,
        "authority": {
            "internal_human_review_surface_only": True,
            "candidate_is_not_evidence": True,
            "automatic_evidence_promotion": False,
            "numeric_fact_authority": False,
            "public_information_gap_authority": False,
            "S1_qualification_claimed": False,
            "product_publication": False,
        },
        "known_boundary": (
            "This packet joins selected Candidate decisions to bounded official-source "
            "excerpts and immutable object lineage for authenticated internal review. "
            "It does not promote Evidence, authorize NumericFact, declare a public "
            "information gap, qualify S1 or authorize publication."
        ),
    }
    return {**body, "review_packet_digest": canonical_digest(body)}


__all__ = [
    "DEFAULT_REVIEW_EXCERPT_CHARS",
    "MAX_REVIEW_EXCERPT_CHARS",
    "PRODUCT_CANDIDATE_REVIEW_PACKET_SCHEMA_VERSION",
    "ProductCandidateReviewError",
    "compile_product_candidate_review_packet",
]
