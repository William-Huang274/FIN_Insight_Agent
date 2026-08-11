from __future__ import annotations

import re
from typing import Any, Mapping

from .edge_schema import normalize_relationship_edge, validate_relationship_edge


DIRECT_CUSTOMER_TERMS = ("customer", "customers", "client", "clients", "revenue", "sales")
DIRECT_SUPPLIER_TERMS = ("supplier", "suppliers", "vendor", "vendors", "supply", "single source")
CONTRACT_TERMS = ("agreement", "contract", "purchase order", "supply agreement", "customer agreement")
PARTNER_TERMS = ("partner", "partnership", "channel", "reseller", "collaboration", "alliance")


def verify_relationship_edge(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    edge = normalize_relationship_edge(payload)
    contract_result = validate_relationship_edge(edge, strict=False)
    reject_reasons = [str(item.get("type") or "") for item in contract_result["errors"]]
    evidence_text = str(edge.get("evidence_text") or "").lower()

    if edge["relation_type"] == "direct_customer_supplier":
        if edge["direction"] == "source_sells_to_target" and not _contains_any(evidence_text, DIRECT_CUSTOMER_TERMS):
            reject_reasons.append("evidence_missing_customer_language")
        if edge["direction"] == "target_sells_to_source" and not _contains_any(evidence_text, DIRECT_SUPPLIER_TERMS):
            reject_reasons.append("evidence_missing_supplier_language")
    elif edge["relation_type"] == "contractual_relationship":
        if not _contains_any(evidence_text, CONTRACT_TERMS):
            reject_reasons.append("evidence_missing_contract_language")
    elif edge["relation_type"] == "partner_channel":
        if not _contains_any(evidence_text, PARTNER_TERMS):
            reject_reasons.append("evidence_missing_partner_language")
    elif edge["relation_type"] == "sector_exposure":
        if edge.get("relationship_type") in {"customer", "supplier"}:
            reject_reasons.append("sector_exposure_misclassified_as_customer_supplier")

    verified = not reject_reasons and edge["confidence"] != "rejected"
    edge["verifier_status"] = "verified" if verified else "rejected"
    edge["reject_reason"] = "; ".join(_unique_strings(reject_reasons))
    if not verified and edge["confidence"] == "high":
        edge["confidence"] = "medium"
    final_result = validate_relationship_edge(edge, strict=True)
    if final_result["status"] == "fail" and verified:
        edge["verifier_status"] = "rejected"
        edge["reject_reason"] = "; ".join(
            _unique_strings([edge["reject_reason"], *[item["type"] for item in final_result["errors"]]])
        )
        final_result = validate_relationship_edge(edge, strict=True)
    return {
        "status": "pass" if edge["verifier_status"] == "verified" and final_result["status"] == "pass" else "fail",
        "edge": final_result["edge"],
        "errors": final_result["errors"],
        "warnings": final_result["warnings"],
        "reject_reasons": _unique_strings(reject_reasons),
    }


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) for term in terms)


def _unique_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
