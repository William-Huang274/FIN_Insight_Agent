from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
KG_MATRIX_REGISTRY_SCHEMA_VERSION = "fin_agent_kg_matrix_registry_v0.1"
DEFAULT_KG_MATRIX_REGISTRY_PATH = REPO_ROOT / "configs" / "kg_matrix_registry_v0_1.yaml"

KG_MINIMAL_REGISTRY_SCHEMA_VERSION = "fin_agent_kg_minimal_p0_k1_k2_k3_registry_v0.1"

REQUIRED_LAYERS = {
    "layer0_entity_identifier",
    "layer1_business_operating",
    "layer2_capital_ownership",
    "layer3_macro_industry_driver",
    "layer4_evidence_claim_gap",
    "layer5_workflow_runtime",
}

REQUIRED_K1_NODE_TYPES = {
    "Company",
    "Segment",
    "ProductFamily",
    "ProductModel",
    "ProductSpec",
    "ProductKPI",
    "ChannelOffer",
    "FieldInquiryNote",
    "CapitalStructure",
    "DebtInstrument",
    "CreditFacility",
    "EquityOffering",
    "OwnershipPosition",
    "InsiderTransaction",
    "MacroDriver",
    "CompanyExposureToDriver",
    "SourceArtifact",
    "AtomicFact",
    "Claim",
    "Gap",
    "GateResult",
}

REQUIRED_K1_EDGE_TYPES = {
    "company_reports_segment",
    "segment_contains_product_family",
    "product_family_has_model",
    "product_model_has_spec",
    "product_model_supersedes_model",
    "product_model_competes_with_model",
    "product_model_has_channel_offer",
    "product_model_has_field_inquiry",
    "product_has_kpi",
    "company_has_capital_structure",
    "company_has_debt_instrument",
    "investor_holds_company",
    "company_exposed_to_macro_driver",
    "claim_supported_by_evidence",
    "claim_exposes_gap",
}

REQUIRED_INDUSTRIES = {
    "semiconductors",
    "consumer_electronics",
    "software_saas",
    "banks",
    "pharma_biotech",
    "autos_ev",
    "energy_oil_gas",
    "retail_cpg",
    "defense_gov_it",
}


def load_kg_matrix_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path else DEFAULT_KG_MATRIX_REGISTRY_PATH
    if not registry_path.exists():
        return _fallback_registry()
    with registry_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, Mapping):
        return _fallback_registry()
    return normalize_kg_matrix_registry(payload)


def normalize_kg_matrix_registry(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": str(payload.get("schema_version") or KG_MATRIX_REGISTRY_SCHEMA_VERSION),
        "registry_id": str(payload.get("registry_id") or "kg_matrix_registry_v0_1"),
        "layers": _mapping_dict(payload.get("layers")),
        "node_types": _mapping_dict(payload.get("node_types")),
        "edge_types": _mapping_dict(payload.get("edge_types")),
        "industry_kpi_dictionary": _mapping_dict(payload.get("industry_kpi_dictionary")),
        "product_spec_ontology": _mapping_dict(payload.get("product_spec_ontology")),
        "source_policy": _mapping_dict(payload.get("source_policy")),
        "promotion_policy": _mapping_dict(payload.get("promotion_policy")),
        "subagent_slices": _mapping_dict(payload.get("subagent_slices")),
        "capital_ownership_policy": _mapping_dict(payload.get("capital_ownership_policy")),
        "macro_exposure_policy": _mapping_dict(payload.get("macro_exposure_policy")),
    }


def validate_kg_matrix_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_kg_matrix_registry(registry)
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if normalized.get("schema_version") != KG_MATRIX_REGISTRY_SCHEMA_VERSION:
        errors.append({"type": "invalid_schema_version", "schema_version": normalized.get("schema_version")})

    layers = _mapping_dict(normalized.get("layers"))
    missing_layers = sorted(REQUIRED_LAYERS - set(layers))
    if missing_layers:
        errors.append({"type": "required_layers_missing", "layers": missing_layers})

    node_types = _mapping_dict(normalized.get("node_types"))
    edge_types = _mapping_dict(normalized.get("edge_types"))
    missing_nodes = sorted(REQUIRED_K1_NODE_TYPES - set(node_types))
    missing_edges = sorted(REQUIRED_K1_EDGE_TYPES - set(edge_types))
    if missing_nodes:
        errors.append({"type": "required_node_types_missing", "node_types": missing_nodes})
    if missing_edges:
        errors.append({"type": "required_edge_types_missing", "edge_types": missing_edges})

    for node_type, spec in node_types.items():
        if not isinstance(spec, Mapping):
            errors.append({"type": "invalid_node_type_spec", "node_type": node_type})
            continue
        if not _strings(spec.get("required_fields")):
            errors.append({"type": "node_required_fields_missing", "node_type": node_type})
        layer = str(spec.get("layer") or "")
        if layer and layer not in layers:
            errors.append({"type": "node_layer_unknown", "node_type": node_type, "layer": layer})
    for edge_type, spec in edge_types.items():
        if not isinstance(spec, Mapping):
            errors.append({"type": "invalid_edge_type_spec", "edge_type": edge_type})
            continue
        from_type = str(spec.get("from") or "")
        to_type = str(spec.get("to") or "")
        if from_type not in node_types or to_type not in node_types:
            errors.append({"type": "edge_endpoint_unknown", "edge_type": edge_type, "from": from_type, "to": to_type})
        if not _strings(spec.get("required_gates")):
            errors.append({"type": "edge_required_gates_missing", "edge_type": edge_type})

    industry_kpis = _mapping_dict(normalized.get("industry_kpi_dictionary"))
    missing_industries = sorted(REQUIRED_INDUSTRIES - set(industry_kpis))
    if missing_industries:
        errors.append({"type": "required_industries_missing", "industries": missing_industries})
    for industry, spec in industry_kpis.items():
        if not isinstance(spec, Mapping):
            errors.append({"type": "invalid_industry_kpi_spec", "industry": industry})
            continue
        if not _strings(spec.get("financial_metrics")):
            errors.append({"type": "industry_financial_metrics_missing", "industry": industry})
        if not _strings(spec.get("product_kpis")):
            warnings.append({"type": "industry_product_kpis_empty", "industry": industry})
        if not _strings(spec.get("commercial_gap_metrics")):
            warnings.append({"type": "industry_commercial_gap_metrics_empty", "industry": industry})

    product_spec = _mapping_dict(normalized.get("product_spec_ontology"))
    _validate_required_contains(
        product_spec.get("common_required_fields"),
        {"source_id", "unit", "region", "effective_date", "claim_scope"},
        "product_spec_common_fields_missing",
        errors,
    )
    _validate_required_contains(
        product_spec.get("channel_offer_required_fields"),
        {"price", "currency", "availability", "region", "observed_at", "source_id", "claim_scope"},
        "channel_offer_fields_missing",
        errors,
    )
    _validate_required_contains(
        product_spec.get("field_inquiry_required_fields"),
        {"provider_role", "inquiry_target", "inquiry_time", "raw_record_ref", "confidence", "claim_scope"},
        "field_inquiry_fields_missing",
        errors,
    )
    channel_boundary = _mapping_dict(product_spec.get("channel_offer_boundary"))
    if not {"company_sales", "sell_through", "market_share", "company_ASP", "channel_inventory"} <= set(
        _strings(channel_boundary.get("forbidden_claims"))
    ):
        errors.append({"type": "channel_offer_forbidden_claim_boundary_incomplete"})
    inquiry_boundary = _mapping_dict(product_spec.get("field_inquiry_boundary"))
    if "authority_fact" not in _strings(inquiry_boundary.get("forbidden_claims")):
        errors.append({"type": "field_inquiry_authority_fact_boundary_missing"})
    dimensions = _mapping_dict(product_spec.get("industry_spec_dimensions"))
    missing_dimensions = sorted((REQUIRED_INDUSTRIES - {"banks", "energy_oil_gas"}) - set(dimensions))
    if missing_dimensions:
        warnings.append({"type": "industry_spec_dimensions_missing", "industries": missing_dimensions})

    source_policy = _mapping_dict(normalized.get("source_policy"))
    public_buyer = _mapping_dict(source_policy.get("public_buyer_observer"))
    if "impersonate_credentials_or_authorization" not in _strings(public_buyer.get("forbidden_actions")):
        errors.append({"type": "public_buyer_impersonation_boundary_missing"})
    if "submit_false_forms_or_orders" not in _strings(public_buyer.get("forbidden_actions")):
        errors.append({"type": "public_buyer_false_order_boundary_missing"})
    source_classes = _mapping_dict(source_policy.get("source_class_claim_boundaries"))
    for source_class in (
        "company_official_product_surface",
        "commerce_product_surface",
        "distributor_public_catalog",
        "pricing_page",
        "field_inquiry_note",
        "commercial_market_tracker",
    ):
        if source_class not in source_classes:
            errors.append({"type": "source_class_boundary_missing", "source_class": source_class})
    commerce = _mapping_dict(source_classes.get("commerce_product_surface"))
    if "sell_through" not in _strings(commerce.get("forbidden_claims")):
        errors.append({"type": "commerce_surface_sell_through_boundary_missing"})
    source_families = _mapping_dict(source_policy.get("source_family_claim_boundaries"))
    for family in ("primary_sec_filing", "company_product_evidence_graph", "public_source_context", "live_public_web_context", "commercial_market_tracker"):
        if family not in source_families:
            errors.append({"type": "source_family_boundary_missing", "source_family": family})
    commercial = _mapping_dict(source_families.get("commercial_market_tracker"))
    if commercial.get("gap_policy") != "expose_commercial_gap_do_not_proxy":
        errors.append({"type": "commercial_gap_policy_missing"})

    promotion = _mapping_dict(normalized.get("promotion_policy"))
    for forbidden in (
        "channel_offer_to_sell_through",
        "channel_offer_to_company_ASP",
        "field_inquiry_to_authority_fact",
        "macro_series_to_company_fact",
        "ownership_filing_to_realtime_flow",
    ):
        if forbidden not in _strings(promotion.get("forbidden_promotions")):
            errors.append({"type": "forbidden_promotion_missing", "promotion": forbidden})

    capital_policy = _mapping_dict(normalized.get("capital_ownership_policy"))
    _validate_required_contains(
        capital_policy.get("ownership_lag_required_fields"),
        {"report_period", "filing_date", "lag_days", "not_realtime_flag"},
        "ownership_lag_policy_fields_missing",
        errors,
    )
    macro_policy = _mapping_dict(normalized.get("macro_exposure_policy"))
    if macro_policy.get("exposure_bridge_required") is not True:
        errors.append({"type": "macro_exposure_bridge_required_missing"})
    if "macro_series_to_company_revenue" not in _strings(macro_policy.get("forbidden_promotions")):
        errors.append({"type": "macro_company_fact_boundary_missing"})

    subagents = _mapping_dict(normalized.get("subagent_slices"))
    product_subagent = _mapping_dict(subagents.get("product_technology_subagent"))
    if "ProductSpecPack" not in _strings(product_subagent.get("outputs")):
        errors.append({"type": "product_subagent_product_spec_pack_output_missing"})
    if "channel_offer_as_sell_through" not in _strings(product_subagent.get("forbidden")):
        errors.append({"type": "product_subagent_channel_offer_boundary_missing"})

    return {
        "schema_version": "fin_agent_kg_matrix_registry_validation_v0.1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
    }


def compact_kg_matrix_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_kg_matrix_registry(registry)
    node_types = _mapping_dict(normalized.get("node_types"))
    edge_types = _mapping_dict(normalized.get("edge_types"))
    product_spec = _mapping_dict(normalized.get("product_spec_ontology"))
    source_policy = _mapping_dict(normalized.get("source_policy"))
    source_classes = _mapping_dict(source_policy.get("source_class_claim_boundaries"))
    source_families = _mapping_dict(source_policy.get("source_family_claim_boundaries"))
    return {
        "schema_version": normalized.get("schema_version"),
        "registry_id": normalized.get("registry_id"),
        "layer_count": len(_mapping_dict(normalized.get("layers"))),
        "node_type_count": len(node_types),
        "edge_type_count": len(edge_types),
        "node_types": sorted(node_types),
        "edge_types": sorted(edge_types),
        "product_spec_node_types": [
            node_type
            for node_type in ("ProductFamily", "ProductModel", "ProductSpec", "ChannelOffer", "FieldInquiryNote")
            if node_type in node_types
        ],
        "capital_ownership_node_types": [
            node_type
            for node_type in ("CapitalStructure", "DebtInstrument", "CreditFacility", "EquityOffering", "OwnershipPosition", "InsiderTransaction")
            if node_type in node_types
        ],
        "macro_exposure_node_types": [
            node_type for node_type in ("MacroDriver", "TradeDriver", "IndustryDriver", "CompanyExposureToDriver") if node_type in node_types
        ],
        "industries": sorted(_mapping_dict(normalized.get("industry_kpi_dictionary"))),
        "product_spec_industries": sorted(_mapping_dict(product_spec.get("industry_spec_dimensions"))),
        "channel_offer_forbidden_claims": _strings(_mapping_dict(product_spec.get("channel_offer_boundary")).get("forbidden_claims")),
        "field_inquiry_forbidden_claims": _strings(_mapping_dict(product_spec.get("field_inquiry_boundary")).get("forbidden_claims")),
        "source_class_boundaries": sorted(source_classes),
        "source_family_boundaries": sorted(source_families),
        "public_buyer_observer_allowed_source_classes": _strings(
            _mapping_dict(source_policy.get("public_buyer_observer")).get("allowed_source_classes")
        ),
        "subagent_ids": sorted(_mapping_dict(normalized.get("subagent_slices"))),
    }


def derive_minimal_kg_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    normalized = normalize_kg_matrix_registry(registry)
    node_types = _mapping_dict(normalized.get("node_types"))
    edge_types = _mapping_dict(normalized.get("edge_types"))
    product_spec = _mapping_dict(normalized.get("product_spec_ontology"))
    source_policy = _mapping_dict(normalized.get("source_policy"))
    source_families = _mapping_dict(source_policy.get("source_family_claim_boundaries"))
    p0_edges = {
        "reports_segment": _minimal_edge(edge_types.get("company_reports_segment")),
        "segment_contains_product": _minimal_edge(edge_types.get("segment_contains_product_family")),
        "product_has_kpi": _minimal_edge(edge_types.get("product_has_kpi")),
    }
    promotion = _mapping_dict(normalized.get("promotion_policy"))
    return {
        "schema_version": KG_MINIMAL_REGISTRY_SCHEMA_VERSION,
        "registry_id": "derived_from_kg_matrix_registry_v0_1",
        "p0_business_product_kpi_graph": {
            "object_types": {
                "Company": _minimal_node(node_types.get("Company")),
                "Segment": _minimal_node(node_types.get("Segment")),
                "ProductFamily": _minimal_node(node_types.get("ProductFamily")),
                "ProductKPI": _minimal_node(node_types.get("ProductKPI")),
            },
            "edge_types": p0_edges,
            "promotion_policy": {
                "product_kpi_exact_authority_sources": _strings(promotion.get("product_kpi_exact_authority_sources")),
                "context_only_sources": _strings(promotion.get("context_only_sources")),
                "forbidden_promotions": _strings(promotion.get("forbidden_promotions")),
            },
        },
        "k1_industry_kpi_dictionary": _mapping_dict(normalized.get("industry_kpi_dictionary")),
        "k2_product_spec_ontology": {
            "common_required_fields": _strings(product_spec.get("common_required_fields")),
            "industry_spec_dimensions": _mapping_dict(product_spec.get("industry_spec_dimensions")),
            "channel_offer_boundary": _mapping_dict(product_spec.get("channel_offer_boundary")),
            "field_inquiry_boundary": _mapping_dict(product_spec.get("field_inquiry_boundary")),
            "product_model_required_fields": _strings(product_spec.get("product_model_required_fields")),
            "generation_edge_required_fields": _strings(product_spec.get("generation_edge_required_fields")),
            "comparable_edge_required_fields": _strings(product_spec.get("comparable_edge_required_fields")),
            "channel_offer_required_fields": _strings(product_spec.get("channel_offer_required_fields")),
            "field_inquiry_required_fields": _strings(product_spec.get("field_inquiry_required_fields")),
        },
        "k3_source_policy_minimal": {
            "public_buyer_observer": _mapping_dict(source_policy.get("public_buyer_observer")),
            "source_family_claim_boundaries": source_families,
            "source_class_claim_boundaries": _mapping_dict(source_policy.get("source_class_claim_boundaries")),
        },
    }


def _minimal_node(value: Any) -> dict[str, Any]:
    item = _mapping_dict(value)
    return {
        "required_fields": _strings(item.get("required_fields")),
        "source_authority": str(item.get("source_authority") or ""),
    }


def _minimal_edge(value: Any) -> dict[str, Any]:
    item = _mapping_dict(value)
    return {
        "from": str(item.get("from") or ""),
        "to": str(item.get("to") or ""),
        "required_gates": _strings(item.get("required_gates")),
    }


def _validate_required_contains(value: Any, required: set[str], error_type: str, errors: list[dict[str, Any]]) -> None:
    missing = sorted(required - set(_strings(value)))
    if missing:
        errors.append({"type": error_type, "fields": missing})


def _mapping_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): dict(item) if isinstance(item, Mapping) else item for key, item in value.items()}


def _fallback_registry() -> dict[str, Any]:
    return {
        "schema_version": KG_MATRIX_REGISTRY_SCHEMA_VERSION,
        "registry_id": "fallback_kg_matrix_registry",
        "layers": {},
        "node_types": {},
        "edge_types": {},
        "industry_kpi_dictionary": {},
        "product_spec_ontology": {},
        "source_policy": {},
        "promotion_policy": {},
        "subagent_slices": {},
        "capital_ownership_policy": {},
        "macro_exposure_policy": {},
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
