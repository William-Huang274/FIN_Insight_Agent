from __future__ import annotations

from typing import Any, Mapping

from .financial_objects import (
    FinancialObjectError,
    validate_source_object_manifest as validate_legacy_source_object_manifest,
)


QUALIFICATION_SOURCE_MANIFEST_SCHEMA_VERSION = (
    "fin_ia_qualification_source_object_manifest_v1_0"
)
_QUALIFICATION_INPUT_KINDS = {
    "parsed_sec_capture",
    "raw_sec_html_capture",
    "parsed_official_pdf_document",
    "parsed_pdf_layout_document",
}


def validate_object_store_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate legacy product or split-safe qualification source manifests.

    The adapter deliberately lives outside the preregistered financial object
    compiler.  Qualification can therefore select an acceptance profile and a
    layout-document input without changing the bound parent/child compilers.
    """

    value = dict(payload)
    if value.get("schema_version") != QUALIFICATION_SOURCE_MANIFEST_SCHEMA_VERSION:
        legacy = validate_legacy_source_object_manifest(value)
        legacy["acceptance_profile"] = "current_product"
        return legacy

    if (
        value.get("status") != "qualification_source_object_manifest"
        or value.get("acceptance_profile") != "qualification_candidate"
    ):
        raise FinancialObjectError("source_object_manifest_profile_invalid")
    policy = value.get("policy")
    if not (
        isinstance(policy, Mapping)
        and policy.get("immutable_capture_precedes_parse") is True
        and policy.get("document_parent_precedes_retrieval_child") is True
        and policy.get("candidate_is_not_evidence") is True
        and policy.get("market_snapshot_is_not_valuation") is True
        and policy.get("hidden_labels_forbidden") is True
        and policy.get("source_period_and_owner_fail_closed") is True
        and policy.get("numeric_fact_authority_granted") is False
    ):
        raise FinancialObjectError("source_object_manifest_policy_invalid")
    allowed = value.get("allowed_tickers")
    cases = value.get("case_tickers")
    sources = value.get("sources")
    if not (
        isinstance(allowed, list)
        and allowed
        and len(allowed) == len(set(allowed))
        and isinstance(cases, list)
        and cases
        and len(cases) == len(set(cases))
        and set(cases).issubset(set(allowed))
        and isinstance(sources, list)
        and sources
    ):
        raise FinancialObjectError("source_object_manifest_shape_invalid")
    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, Mapping):
            raise FinancialObjectError("source_object_manifest_source_invalid")
        source_id = str(source.get("source_id") or "").strip()
        input_kind = str(source.get("input_kind") or "").strip()
        if (
            not source_id
            or source_id in source_ids
            or input_kind not in _QUALIFICATION_INPUT_KINDS
            or not str(source.get("path") or "").strip()
            or source.get("required") is not True
        ):
            raise FinancialObjectError("source_object_manifest_source_invalid")
        source_ids.add(source_id)
    return value


__all__ = [
    "QUALIFICATION_SOURCE_MANIFEST_SCHEMA_VERSION",
    "validate_object_store_manifest",
]
