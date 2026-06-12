from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
KG_MINIMAL_REGISTRY_SCHEMA_VERSION = "fin_agent_kg_minimal_p0_k1_k2_k3_registry_v0.1"
DEFAULT_KG_MINIMAL_REGISTRY_PATH = REPO_ROOT / "configs" / "kg_minimal_p0_k1_k2_k3_v0_1.yaml"

REQUIRED_INDUSTRIES = {
    "semiconductors",
    "consumer_electronics",
    "software_saas",
    "banks",
    "pharma_biotech",
    "autos_ev",
    "energy_oil_gas",
    "retail_cpg",
}


def load_kg_minimal_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path else DEFAULT_KG_MINIMAL_REGISTRY_PATH
    if not registry_path.exists():
        return _fallback_registry()
    with registry_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, Mapping):
        return _fallback_registry()
    return normalize_kg_minimal_registry(payload)


def normalize_kg_minimal_registry(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": str(payload.get("schema_version") or KG_MINIMAL_REGISTRY_SCHEMA_VERSION),
        "registry_id": str(payload.get("registry_id") or "kg_minimal_p0_k1_k2_k3_v0_1"),
        "p0_business_product_kpi_graph": dict(payload.get("p0_business_product_kpi_graph") or {}),
        "k1_industry_kpi_dictionary": {
            str(key): dict(value)
            for key, value in dict(payload.get("k1_industry_kpi_dictionary") or {}).items()
            if isinstance(value, Mapping)
        },
        "k2_product_spec_ontology": dict(payload.get("k2_product_spec_ontology") or {}),
        "k3_source_policy_minimal": dict(payload.get("k3_source_policy_minimal") or {}),
    }


def validate_kg_minimal_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if str(registry.get("schema_version") or "") != KG_MINIMAL_REGISTRY_SCHEMA_VERSION:
        errors.append({"type": "invalid_schema_version", "schema_version": registry.get("schema_version")})

    p0 = registry.get("p0_business_product_kpi_graph") if isinstance(registry.get("p0_business_product_kpi_graph"), Mapping) else {}
    object_types = p0.get("object_types") if isinstance(p0.get("object_types"), Mapping) else {}
    edge_types = p0.get("edge_types") if isinstance(p0.get("edge_types"), Mapping) else {}
    for object_type in ("Company", "Segment", "ProductFamily", "ProductKPI"):
        item = object_types.get(object_type) if isinstance(object_types.get(object_type), Mapping) else {}
        if not item:
            errors.append({"type": "p0_object_type_missing", "object_type": object_type})
        elif not _strings(item.get("required_fields")):
            errors.append({"type": "p0_object_required_fields_missing", "object_type": object_type})
    for edge_type in ("reports_segment", "segment_contains_product", "product_has_kpi"):
        item = edge_types.get(edge_type) if isinstance(edge_types.get(edge_type), Mapping) else {}
        if not item:
            errors.append({"type": "p0_edge_type_missing", "edge_type": edge_type})
        elif not _strings(item.get("required_gates")):
            errors.append({"type": "p0_edge_required_gates_missing", "edge_type": edge_type})
    promotion_policy = p0.get("promotion_policy") if isinstance(p0.get("promotion_policy"), Mapping) else {}
    if "public_proxy_to_company_sales" not in _strings(promotion_policy.get("forbidden_promotions")):
        errors.append({"type": "p0_forbidden_public_proxy_promotion_missing"})

    k1 = registry.get("k1_industry_kpi_dictionary") if isinstance(registry.get("k1_industry_kpi_dictionary"), Mapping) else {}
    missing_industries = sorted(REQUIRED_INDUSTRIES - set(k1))
    if missing_industries:
        errors.append({"type": "k1_required_industries_missing", "industries": missing_industries})
    for industry, item in k1.items():
        if not _strings(item.get("financial_metrics")):
            errors.append({"type": "k1_financial_metrics_missing", "industry": industry})
        if not _strings(item.get("product_kpis")):
            warnings.append({"type": "k1_product_kpis_empty", "industry": industry})
        if not _strings(item.get("commercial_gap_metrics")):
            warnings.append({"type": "k1_commercial_gap_metrics_empty", "industry": industry})

    k2 = registry.get("k2_product_spec_ontology") if isinstance(registry.get("k2_product_spec_ontology"), Mapping) else {}
    if not _strings(k2.get("common_required_fields")):
        errors.append({"type": "k2_common_required_fields_missing"})
    spec_dimensions = k2.get("industry_spec_dimensions") if isinstance(k2.get("industry_spec_dimensions"), Mapping) else {}
    missing_spec_industries = sorted((REQUIRED_INDUSTRIES - {"banks", "energy_oil_gas"}) - set(spec_dimensions))
    if missing_spec_industries:
        warnings.append({"type": "k2_spec_dimensions_missing_for_industries", "industries": missing_spec_industries})
    channel_boundary = k2.get("channel_offer_boundary") if isinstance(k2.get("channel_offer_boundary"), Mapping) else {}
    if "company_sales" not in _strings(channel_boundary.get("forbidden_claims")):
        errors.append({"type": "k2_channel_offer_company_sales_boundary_missing"})

    k3 = registry.get("k3_source_policy_minimal") if isinstance(registry.get("k3_source_policy_minimal"), Mapping) else {}
    public_buyer = k3.get("public_buyer_observer") if isinstance(k3.get("public_buyer_observer"), Mapping) else {}
    if not _strings(public_buyer.get("allowed_source_classes")):
        errors.append({"type": "k3_public_buyer_allowed_source_classes_missing"})
    if "impersonate_credentials_or_authorization" not in _strings(public_buyer.get("forbidden_actions")):
        errors.append({"type": "k3_public_buyer_impersonation_boundary_missing"})
    source_boundaries = k3.get("source_family_claim_boundaries") if isinstance(k3.get("source_family_claim_boundaries"), Mapping) else {}
    for family in ("primary_sec_filing", "company_product_evidence_graph", "public_source_context", "live_public_web_context"):
        if family not in source_boundaries:
            errors.append({"type": "k3_source_family_boundary_missing", "source_family": family})
    commercial = source_boundaries.get("commercial_market_tracker") if isinstance(source_boundaries.get("commercial_market_tracker"), Mapping) else {}
    if commercial.get("gap_policy") != "expose_commercial_gap_do_not_proxy":
        errors.append({"type": "k3_commercial_gap_policy_missing"})

    return {
        "schema_version": "fin_agent_kg_minimal_p0_k1_k2_k3_validation_v0.1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
    }


def compact_kg_minimal_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_kg_minimal_registry(registry)
    p0 = normalized.get("p0_business_product_kpi_graph") if isinstance(normalized.get("p0_business_product_kpi_graph"), Mapping) else {}
    k1 = normalized.get("k1_industry_kpi_dictionary") if isinstance(normalized.get("k1_industry_kpi_dictionary"), Mapping) else {}
    k2 = normalized.get("k2_product_spec_ontology") if isinstance(normalized.get("k2_product_spec_ontology"), Mapping) else {}
    k3 = normalized.get("k3_source_policy_minimal") if isinstance(normalized.get("k3_source_policy_minimal"), Mapping) else {}
    source_boundaries = k3.get("source_family_claim_boundaries") if isinstance(k3.get("source_family_claim_boundaries"), Mapping) else {}
    return {
        "schema_version": normalized.get("schema_version"),
        "registry_id": normalized.get("registry_id"),
        "p0_object_types": sorted((p0.get("object_types") or {}).keys()) if isinstance(p0.get("object_types"), Mapping) else [],
        "p0_edge_types": sorted((p0.get("edge_types") or {}).keys()) if isinstance(p0.get("edge_types"), Mapping) else [],
        "industry_count": len(k1),
        "industries": sorted(k1.keys()),
        "product_spec_industries": sorted((k2.get("industry_spec_dimensions") or {}).keys())
        if isinstance(k2.get("industry_spec_dimensions"), Mapping)
        else [],
        "source_family_boundaries": sorted(source_boundaries.keys()),
        "public_buyer_observer_allowed_source_classes": _strings(
            (k3.get("public_buyer_observer") or {}).get("allowed_source_classes")
            if isinstance(k3.get("public_buyer_observer"), Mapping)
            else []
        ),
    }


def _fallback_registry() -> dict[str, Any]:
    return {
        "schema_version": KG_MINIMAL_REGISTRY_SCHEMA_VERSION,
        "registry_id": "fallback_kg_minimal_registry",
        "p0_business_product_kpi_graph": {},
        "k1_industry_kpi_dictionary": {},
        "k2_product_spec_ontology": {},
        "k3_source_policy_minimal": {},
    }


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
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
