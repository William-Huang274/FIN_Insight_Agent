from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .query_plan import canonical_digest


SOURCE_USE_POLICY_SCHEMA_VERSION = "fin_ia_s1_source_use_policy_v1_0"
_CLAIM_USES = {
    "target_company_exact_fact",
    "target_company_exact_numeric_fact",
    "speaker_exact_fact",
    "speaker_attributed_mechanism",
    "market_exact_fact",
    "industry_exact_fact",
    "bounded_target_context",
    "bounded_market_context",
    "mechanism_hypothesis",
    "counterevidence",
    "discovery_locator",
}
_BOOLEAN_FIELDS = {
    "target_company_exact_numeric_fact_allowed",
    "requires_original_capture",
    "requires_speaker_binding",
    "requires_subject_binding",
    "requires_license_entitlement",
}
_RIGHT_FIELDS = {
    "discovery_right",
    "internal_analysis_right",
    "citation_right",
    "redistribution_right",
}
_RIGHT_STATES = {
    "allowed",
    "allowed_after_original_capture",
    "allowed_with_entitlement",
    "bounded_excerpt_only",
    "metadata_and_locator_only",
    "forbidden",
}
_REQUESTABLE_RIGHTS = {
    "discovery",
    "internal_analysis",
    "citation",
    "redistribution",
}
_BOUNDED_CONTEXT_CLAIM_USES = {
    "bounded_target_context",
    "bounded_market_context",
    "mechanism_hypothesis",
}


class SourceUsePolicyError(ValueError):
    """Raised when source strength and permitted claim use become ambiguous."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise SourceUsePolicyError(code)


@dataclass(frozen=True)
class SourceUseClass:
    source_class: str
    allowed_claim_uses: tuple[str, ...]
    customer_use_mode: str
    target_company_exact_numeric_fact_allowed: bool
    requires_original_capture: bool
    requires_speaker_binding: bool
    requires_subject_binding: bool
    requires_license_entitlement: bool
    minimum_independent_sources: int
    internalization_mode: str
    discovery_right: str
    internal_analysis_right: str
    citation_right: str
    redistribution_right: str


@dataclass(frozen=True)
class SourceUsePolicy:
    policy_id: str
    classes: Mapping[str, SourceUseClass]

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SourceUsePolicy":
        _require(
            payload.get("schema_version") == SOURCE_USE_POLICY_SCHEMA_VERSION,
            "source_use_policy_schema_invalid",
        )
        _require(
            payload.get("status") == "active_source_strength_and_claim_use_policy",
            "source_use_policy_status_invalid",
        )
        policy_id = str(payload.get("policy_id") or "")
        controls = payload.get("policy")
        raw_classes = payload.get("source_classes")
        _require(
            policy_id
            and isinstance(controls, Mapping)
            and controls.get("official_only_is_not_required_for_all_research_context")
            is True
            and controls.get("source_strength_is_not_claim_truth") is True
            and controls.get("discovery_is_not_evidence") is True
            and controls.get("speaker_and_subject_must_remain_distinct") is True
            and controls.get("target_company_exact_numeric_facts_remain_narrow")
            is True
            and controls.get(
                "recurring_free_sources_may_be_internalized_after_capture_and_parser_qualification"
            )
            is True
            and isinstance(raw_classes, list)
            and raw_classes,
            "source_use_policy_shape_invalid",
        )
        classes: dict[str, SourceUseClass] = {}
        for raw in raw_classes:
            _require(isinstance(raw, Mapping), "source_use_policy_class_invalid")
            source_class = str(raw.get("source_class") or "")
            allowed = tuple(str(value) for value in raw.get("allowed_claim_uses") or ())
            minimum = raw.get("minimum_independent_sources")
            _require(
                source_class
                and source_class not in classes
                and allowed
                and len(allowed) == len(set(allowed))
                and set(allowed).issubset(_CLAIM_USES)
                and all(type(raw.get(field)) is bool for field in _BOOLEAN_FIELDS)
                and all(
                    str(raw.get(field) or "") in _RIGHT_STATES
                    for field in _RIGHT_FIELDS
                )
                and isinstance(minimum, int)
                and minimum >= 1,
                "source_use_policy_class_invalid",
            )
            classes[source_class] = SourceUseClass(
                source_class=source_class,
                allowed_claim_uses=allowed,
                customer_use_mode=str(raw.get("customer_use_mode") or ""),
                target_company_exact_numeric_fact_allowed=(
                    raw.get("target_company_exact_numeric_fact_allowed") is True
                ),
                requires_original_capture=raw.get("requires_original_capture") is True,
                requires_speaker_binding=raw.get("requires_speaker_binding") is True,
                requires_subject_binding=raw.get("requires_subject_binding") is True,
                requires_license_entitlement=(
                    raw.get("requires_license_entitlement") is True
                ),
                minimum_independent_sources=minimum,
                internalization_mode=str(raw.get("internalization_mode") or ""),
                discovery_right=str(raw.get("discovery_right") or ""),
                internal_analysis_right=str(
                    raw.get("internal_analysis_right") or ""
                ),
                citation_right=str(raw.get("citation_right") or ""),
                redistribution_right=str(raw.get("redistribution_right") or ""),
            )
            _require(
                classes[source_class].customer_use_mode
                in {
                    "exact_fact_and_citation",
                    "bounded_context_and_citation",
                    "discovery_only_not_customer_citable",
                    "entitlement_bound_fact_or_context",
                }
                and classes[source_class].internalization_mode
                in {
                    "versioned_source_object",
                    "versioned_context_object",
                    "locator_then_fetch_original",
                    "license_and_retention_bound_object",
                },
                "source_use_policy_class_mode_invalid",
            )
            _require(
                (
                    "target_company_exact_numeric_fact" in allowed
                    and classes[source_class].target_company_exact_numeric_fact_allowed
                )
                or (
                    "target_company_exact_numeric_fact" not in allowed
                    and not classes[
                        source_class
                    ].target_company_exact_numeric_fact_allowed
                ),
                "source_use_policy_numeric_permission_inconsistent",
            )
            if classes[source_class].customer_use_mode == (
                "discovery_only_not_customer_citable"
            ):
                _require(
                    allowed == ("discovery_locator",),
                    "source_use_policy_discovery_permissions_invalid",
                )
        return cls(policy_id=policy_id, classes=classes)


def evaluate_source_claim_use(
    *,
    policy: SourceUsePolicy,
    source_class: str,
    claim_use: str,
    original_capture_bound: bool,
    speaker_bound: bool,
    subject_bound: bool,
    independent_source_count: int = 1,
    license_entitled: bool = False,
    requested_rights: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Decide how one source may be used; never decide whether its claim is true.

    Search results, snippets and article popularity do not acquire factual
    authority here.  The result is an input to Evidence Gate and preserves the
    difference between an exact subject fact, a speaker-attributed read-through,
    bounded context, and a discovery locator.
    """

    source = policy.classes.get(source_class)
    _require(source is not None, "source_use_policy_class_unknown")
    _require(independent_source_count >= 0, "source_use_independent_count_invalid")
    _require(
        len(requested_rights) == len(set(requested_rights))
        and set(requested_rights).issubset(_REQUESTABLE_RIGHTS),
        "source_use_requested_rights_invalid",
    )
    blockers: list[str] = []
    if claim_use not in source.allowed_claim_uses:
        blockers.append("claim_use_not_allowed_for_source_class")
    if source.requires_original_capture and not original_capture_bound:
        blockers.append("original_source_capture_missing")
    if source.requires_speaker_binding and not speaker_bound:
        blockers.append("speaker_binding_missing")
    if source.requires_subject_binding and not subject_bound:
        blockers.append("subject_binding_missing")
    if source.requires_license_entitlement and not license_entitled:
        blockers.append("license_entitlement_missing")
    if independent_source_count < source.minimum_independent_sources:
        blockers.append("independent_corroboration_below_policy_minimum")
    if (
        claim_use == "target_company_exact_numeric_fact"
        and not source.target_company_exact_numeric_fact_allowed
    ):
        blockers.append("target_company_exact_numeric_fact_forbidden")

    rights = {
        "discovery": source.discovery_right,
        "internal_analysis": source.internal_analysis_right,
        "citation": source.citation_right,
        "redistribution": source.redistribution_right,
    }
    right_conditions: dict[str, str] = {}
    for requested in requested_rights:
        state = rights[requested]
        if state == "allowed":
            continue
        if state == "allowed_after_original_capture":
            if not original_capture_bound:
                blockers.append(f"{requested}_right_requires_original_capture")
            continue
        if state == "allowed_with_entitlement":
            if not license_entitled:
                blockers.append(f"{requested}_right_requires_entitlement")
            continue
        if state == "bounded_excerpt_only" and requested == "redistribution":
            right_conditions[requested] = "bounded_excerpt_and_attribution_only"
            continue
        blockers.append(f"{requested}_right_forbidden_for_source_class")

    if blockers:
        disposition = "reject_from_evidence_promotion"
    elif source.customer_use_mode == "discovery_only_not_customer_citable":
        disposition = "locator_only_fetch_original_before_evidence_gate"
    elif (
        source.customer_use_mode == "bounded_context_and_citation"
        or claim_use in _BOUNDED_CONTEXT_CLAIM_USES
    ):
        disposition = "admit_as_bounded_context_candidate"
    elif source.customer_use_mode == "entitlement_bound_fact_or_context":
        disposition = "admit_under_license_bound_claim_permissions"
    else:
        disposition = "admit_as_exact_or_speaker_attributed_candidate"

    body = {
        "schema_version": "fin_ia_s1_source_claim_use_decision_v1_0",
        "policy_id": policy.policy_id,
        "source_class": source_class,
        "claim_use": claim_use,
        "customer_use_mode": source.customer_use_mode,
        "internalization_mode": source.internalization_mode,
        "target_company_exact_numeric_fact_allowed": (
            source.target_company_exact_numeric_fact_allowed
        ),
        "rights": rights,
        "requested_rights": list(requested_rights),
        "right_conditions": right_conditions,
        "disposition": disposition,
        "blockers": sorted(set(blockers)),
        "evidence_promotion_allowed": not blockers
        and disposition != "locator_only_fetch_original_before_evidence_gate",
        "source_strength_is_not_claim_truth": True,
        "ranking_score_is_not_evidence_authority": True,
    }
    return {**body, "decision_digest": canonical_digest(body)}


__all__ = [
    "SOURCE_USE_POLICY_SCHEMA_VERSION",
    "SourceUseClass",
    "SourceUsePolicy",
    "SourceUsePolicyError",
    "evaluate_source_claim_use",
]
