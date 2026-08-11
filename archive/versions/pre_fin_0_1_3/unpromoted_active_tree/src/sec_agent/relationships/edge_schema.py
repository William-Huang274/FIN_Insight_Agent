from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping


RELATIONSHIP_EDGE_DIRECT_SCHEMA_VERSION = "fin_agent_relationship_edge_v0.1"

RELATION_TYPES = {
    "direct_customer_supplier",
    "contractual_relationship",
    "partner_channel",
    "shipment_inferred",
    "news_reported",
    "sector_exposure",
}
CONFIDENCE_LEVELS = {"high", "medium", "low", "rejected"}
VERIFIER_STATUSES = {"candidate", "verified", "rejected"}
EDGE_DIRECTIONS = {
    "source_sells_to_target",
    "target_sells_to_source",
    "bidirectional",
    "unclear",
}
HIGH_CONFIDENCE_SOURCE_TIERS = {
    "primary_sec_filing",
    "company_authored_unaudited_sec_filing",
    "company_official_announcement",
    "contract_or_exhibit",
    "sec_exhibit",
}
RELATIONSHIP_FACT_CLAIM_SCOPE = "relationship_fact_not_financial_fact"
GEOGRAPHIC_OR_GENERIC_TARGET_TERMS = {
    "asia",
    "canada",
    "china",
    "china-based",
    "europe",
    "japan",
    "korea",
    "south korea",
    "u.s",
    "u.s.",
    "us",
    "united states",
}
GENERIC_TARGET_PHRASES = {
    "certain key",
    "end customer",
    "end customers",
    "key supplier",
    "key suppliers",
    "major customer",
    "major customers",
    "online sales",
    "sales",
    "net sales",
    "table of contents",
}


def normalize_relationship_edge(payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
    raw = dict(payload or {})
    relation_type = _normalize_relation_type(raw.get("relation_type") or raw.get("relationship_type"))
    direction = _normalize_direction(raw.get("direction") or raw.get("edge_direction"))
    confidence = _normalize_confidence(raw.get("confidence"))
    verifier_status = _normalize_verifier_status(raw.get("verifier_status"))
    source_ticker = _upper(raw.get("source_ticker") or raw.get("ticker") or raw.get("from_ticker"))
    target_ticker = _upper(raw.get("target_ticker") or raw.get("related_ticker") or raw.get("to_ticker"))
    target_name_raw = str(raw.get("target_name_raw") or raw.get("counterparty") or raw.get("target_name") or "").strip()
    evidence_id = str(raw.get("evidence_id") or raw.get("source_record_ref") or "").strip()
    evidence_refs = _unique_strings(raw.get("evidence_refs") or raw.get("refs") or evidence_id)
    if evidence_id and evidence_id not in evidence_refs:
        evidence_refs.insert(0, evidence_id)
    edge = {
        "schema_version": RELATIONSHIP_EDGE_DIRECT_SCHEMA_VERSION,
        "edge_id": str(raw.get("edge_id") or "").strip(),
        "source_entity_id": str(raw.get("source_entity_id") or "").strip(),
        "source_ticker": source_ticker,
        "source_cik": _normalize_cik(raw.get("source_cik") or raw.get("cik")),
        "source_company_name": str(raw.get("source_company_name") or raw.get("company") or "").strip(),
        "target_entity_id": str(raw.get("target_entity_id") or "").strip(),
        "target_ticker": target_ticker,
        "target_cik": _normalize_cik(raw.get("target_cik")),
        "target_name_raw": target_name_raw,
        "relation_type": relation_type,
        "relationship_type": _relationship_type_for_graph(relation_type, direction),
        "direction": direction,
        "confidence": confidence,
        "evidence_tier": str(raw.get("evidence_tier") or raw.get("source_tier") or "").strip(),
        "source_doc_type": str(raw.get("source_doc_type") or raw.get("source_type") or raw.get("form_type") or "").strip(),
        "source_url_or_filing_id": str(raw.get("source_url_or_filing_id") or raw.get("source_url") or raw.get("accession_number") or "").strip(),
        "fiscal_year": _int_or_none(raw.get("fiscal_year")),
        "report_date": str(raw.get("report_date") or raw.get("period_end") or raw.get("publication_date") or "").strip(),
        "evidence_id": evidence_id,
        "evidence_refs": evidence_refs,
        "evidence_text": _compact_text(raw.get("evidence_text") or raw.get("text"), limit=2200),
        "amount": _float_or_none(raw.get("amount")),
        "percentage": _float_or_none(raw.get("percentage")),
        "metric_name": str(raw.get("metric_name") or "").strip(),
        "product_or_segment": str(raw.get("product_or_segment") or "").strip(),
        "geography": str(raw.get("geography") or "").strip(),
        "valid_from": str(raw.get("valid_from") or raw.get("report_date") or raw.get("period_end") or "").strip(),
        "valid_to": str(raw.get("valid_to") or "").strip(),
        "extraction_method": str(raw.get("extraction_method") or "deterministic_sec_pattern_v0_1").strip(),
        "verifier_status": verifier_status,
        "reject_reason": str(raw.get("reject_reason") or "").strip(),
        "entity_resolution_status": str(raw.get("entity_resolution_status") or _entity_resolution_status(raw)).strip(),
        "entity_resolution_confidence": str(raw.get("entity_resolution_confidence") or "").strip(),
        "source_family": "relationship_edge",
        "claim_scope": RELATIONSHIP_FACT_CLAIM_SCOPE,
        "metadata": dict(raw.get("metadata") or {}) if isinstance(raw.get("metadata"), Mapping) else {},
    }
    if not edge["edge_id"]:
        edge["edge_id"] = stable_relationship_edge_id(edge)
    return edge


def validate_relationship_edge(payload: Mapping[str, Any] | None = None, *, strict: bool = True) -> dict[str, Any]:
    edge = normalize_relationship_edge(payload)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    _required(edge, "edge_id", errors)
    if edge["relation_type"] not in RELATION_TYPES:
        errors.append({"type": "invalid_relation_type", "value": edge["relation_type"]})
    if edge["confidence"] not in CONFIDENCE_LEVELS:
        errors.append({"type": "invalid_confidence", "value": edge["confidence"]})
    if edge["verifier_status"] not in VERIFIER_STATUSES:
        errors.append({"type": "invalid_verifier_status", "value": edge["verifier_status"]})
    if edge["direction"] not in EDGE_DIRECTIONS:
        errors.append({"type": "invalid_direction", "value": edge["direction"]})
    if not edge["source_ticker"] and not edge["source_cik"] and not edge["source_entity_id"]:
        errors.append({"type": "source_entity_required"})
    if not edge["evidence_id"]:
        errors.append({"type": "evidence_id_required"})
    if not edge["evidence_text"]:
        errors.append({"type": "evidence_text_required"})
    if not edge["evidence_tier"]:
        errors.append({"type": "evidence_tier_required"})
    if not edge["source_doc_type"]:
        warnings.append({"type": "source_doc_type_missing"})

    if edge["relation_type"] == "sector_exposure":
        if edge["confidence"] == "high":
            errors.append({"type": "sector_exposure_cannot_be_high_confidence_direct_fact"})
        if edge["relationship_type"] in {"customer", "supplier"}:
            errors.append({"type": "sector_exposure_cannot_be_customer_supplier"})

    if edge["relation_type"] == "direct_customer_supplier":
        if edge["direction"] not in {"source_sells_to_target", "target_sells_to_source"}:
            errors.append({"type": "direct_customer_supplier_direction_required", "value": edge["direction"]})
        if not (edge["target_name_raw"] or edge["target_ticker"] or edge["target_cik"] or edge["target_entity_id"]):
            errors.append({"type": "direct_customer_supplier_target_required"})
        if _target_name_is_generic_or_geographic(edge["target_name_raw"]):
            errors.append({"type": "direct_customer_supplier_target_is_generic_or_geographic", "target_name_raw": edge["target_name_raw"]})
    elif edge["relation_type"] in {"contractual_relationship", "partner_channel", "news_reported", "shipment_inferred"}:
        if not (edge["target_name_raw"] or edge["target_ticker"] or edge["target_cik"] or edge["target_entity_id"]):
            errors.append({"type": "counterparty_target_required", "relation_type": edge["relation_type"]})
        if _target_name_is_generic_or_geographic(edge["target_name_raw"]):
            errors.append({"type": "counterparty_target_is_generic_or_geographic", "target_name_raw": edge["target_name_raw"]})

    if edge["confidence"] == "high":
        if edge["evidence_tier"] not in HIGH_CONFIDENCE_SOURCE_TIERS:
            errors.append({"type": "high_confidence_source_tier_not_allowed", "evidence_tier": edge["evidence_tier"]})
        if edge["relation_type"] in {"direct_customer_supplier", "contractual_relationship"}:
            if edge["entity_resolution_status"] != "resolved":
                errors.append({"type": "high_confidence_direct_edge_requires_resolved_target"})

    if edge["verifier_status"] == "verified" and edge["confidence"] == "rejected":
        errors.append({"type": "verified_edge_cannot_have_rejected_confidence"})
    if edge["verifier_status"] == "verified" and errors:
        errors.append({"type": "verified_edge_has_contract_errors"})
    if strict and edge["verifier_status"] == "rejected" and not edge["reject_reason"]:
        errors.append({"type": "rejected_edge_requires_reject_reason"})

    return {
        "status": "fail" if errors else "pass",
        "schema_version": RELATIONSHIP_EDGE_DIRECT_SCHEMA_VERSION,
        "edge": edge,
        "errors": errors,
        "warnings": warnings,
    }


def relationship_edge_to_graph_row(payload: Mapping[str, Any]) -> dict[str, Any]:
    edge = normalize_relationship_edge(payload)
    related_ticker = edge["target_ticker"] or edge["target_name_raw"]
    evidence_refs = edge["evidence_refs"] or [edge["evidence_id"]]
    return {
        "edge_schema_version": "sec_agent_relationship_edge_v0.3",
        "edge_id": edge["edge_id"],
        "ticker": edge["source_ticker"],
        "related_ticker": related_ticker,
        "from_ticker": edge["source_ticker"],
        "to_ticker": related_ticker,
        "relationship_type": edge["relationship_type"],
        "direction": edge["direction"],
        "financial_link_type": edge["relation_type"],
        "mechanism": _mechanism(edge),
        "metrics_to_check": _unique_strings([edge["metric_name"]]),
        "metric_links": _unique_strings([edge["metric_name"]]),
        "evidence_source_needed": [edge["evidence_tier"]] if edge["evidence_tier"] else [],
        "evidence_refs": evidence_refs,
        "source_record_ref": edge["evidence_id"],
        "confidence": edge["confidence"],
        "inference_level": "confirmed_direct" if edge["verifier_status"] == "verified" else "curated_input_unverified",
        "confirmation_status": "verified_direct_edge" if edge["verifier_status"] == "verified" else "candidate_needs_verification",
        "evidence_basis": ["relationship_edge_direct"],
        "missing_confirmations": [] if edge["verifier_status"] == "verified" else ["relationship verifier approval"],
        "source_limitations": [
            "This edge supports a relationship fact only; it does not by itself support company financial metrics."
        ],
        "inclusion_rationale": _inclusion_rationale(edge),
        "claim_scope": "scope_or_hypothesis_only",
        "relationship_source": "verified_relationship_edge" if edge["verifier_status"] == "verified" else "candidate_relationship_edge",
        "source_family": "relationship_graph",
        "notes": edge["evidence_text"][:600],
    }


def stable_relationship_edge_id(edge: Mapping[str, Any]) -> str:
    seed = "|".join(
        [
            str(edge.get("source_ticker") or edge.get("ticker") or ""),
            str(edge.get("source_cik") or edge.get("cik") or ""),
            str(edge.get("target_ticker") or edge.get("related_ticker") or ""),
            str(edge.get("target_cik") or ""),
            str(edge.get("target_name_raw") or edge.get("counterparty") or ""),
            str(edge.get("relation_type") or edge.get("relationship_type") or ""),
            str(edge.get("direction") or ""),
            str(edge.get("evidence_id") or edge.get("source_record_ref") or ""),
        ]
    )
    return "rel_edge_direct_" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:18]


def _relationship_type_for_graph(relation_type: str, direction: str) -> str:
    if relation_type == "direct_customer_supplier":
        if direction == "source_sells_to_target":
            return "customer"
        if direction == "target_sells_to_source":
            return "supplier"
    if relation_type == "sector_exposure":
        return "sector"
    return "other"


def _target_name_is_generic_or_geographic(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    compact = re.sub(r"[^a-z0-9]+", "", text)
    if compact in {"us", "usa"}:
        return True
    if text.startswith("certain "):
        return True
    if "-based" in text:
        return True
    if any(phrase in text for phrase in GENERIC_TARGET_PHRASES):
        return True
    has_legal_suffix = re.search(r"\b(inc|corp|corporation|company|co|ltd|limited|llc|plc|ag|a/s)\b\.?", text) is not None
    geo_hits = {
        term
        for term in GEOGRAPHIC_OR_GENERIC_TARGET_TERMS
        if re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text)
    }
    return (text in GEOGRAPHIC_OR_GENERIC_TARGET_TERMS or len(geo_hits) >= 2) and not has_legal_suffix


def _mechanism(edge: Mapping[str, Any]) -> str:
    relation_type = str(edge.get("relation_type") or "")
    direction = str(edge.get("direction") or "")
    if relation_type == "direct_customer_supplier" and direction == "source_sells_to_target":
        return "source company sells to or serves the named customer"
    if relation_type == "direct_customer_supplier" and direction == "target_sells_to_source":
        return "source company relies on the named supplier"
    if relation_type == "contractual_relationship":
        return "disclosed contract or agreement relationship"
    if relation_type == "partner_channel":
        return "commercial partnership or channel relationship"
    if relation_type == "shipment_inferred":
        return "shipping or transaction lead requiring verification"
    if relation_type == "news_reported":
        return "news or public report lead requiring verification"
    return "sector exposure or economic transmission context"


def _inclusion_rationale(edge: Mapping[str, Any]) -> str:
    target = edge.get("target_ticker") or edge.get("target_name_raw") or "named counterparty"
    return (
        f"{target} is included from {edge.get('evidence_tier') or 'source'} evidence "
        f"as a {edge.get('relation_type')} row with {edge.get('confidence')} confidence."
    )


def _required(edge: Mapping[str, Any], key: str, errors: list[dict[str, Any]]) -> None:
    if not edge.get(key):
        errors.append({"type": f"{key}_required"})


def _normalize_relation_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "customer": "direct_customer_supplier",
        "supplier": "direct_customer_supplier",
        "contract": "contractual_relationship",
        "partner": "partner_channel",
        "sector": "sector_exposure",
    }
    return aliases.get(text, text or "sector_exposure")


def _normalize_direction(value: Any) -> str:
    text = str(value or "").strip().lower()
    aliases = {
        "downstream_customer": "source_sells_to_target",
        "customer": "source_sells_to_target",
        "upstream_supplier": "target_sells_to_source",
        "supplier": "target_sells_to_source",
        "peer": "bidirectional",
        "partnership": "bidirectional",
        "unknown": "unclear",
    }
    return aliases.get(text, text if text in EDGE_DIRECTIONS else "unclear")


def _normalize_confidence(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in CONFIDENCE_LEVELS:
        return text
    if isinstance(value, (int, float)):
        numeric = float(value)
        if numeric >= 0.8:
            return "high"
        if numeric >= 0.45:
            return "medium"
        return "low"
    return "medium"


def _normalize_verifier_status(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in VERIFIER_STATUSES else "candidate"


def _entity_resolution_status(raw: Mapping[str, Any]) -> str:
    explicit = str(raw.get("entity_resolution_status") or "").strip().lower()
    if explicit:
        return explicit
    if raw.get("target_entity_id") or raw.get("target_ticker") or raw.get("target_cik"):
        return "resolved"
    return "unresolved"


def _normalize_cik(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    return digits.zfill(10) if digits else ""


def _upper(value: Any) -> str:
    return str(value or "").upper().strip()


def _int_or_none(value: Any) -> int | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError):
        return None


def _compact_text(value: Any, *, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def _unique_strings(value: Any) -> list[str]:
    if value is None:
        items: list[Any] = []
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
