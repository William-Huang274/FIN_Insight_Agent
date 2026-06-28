from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


PRODUCT_SPEC_PACK_SCHEMA_VERSION = "sec_agent_product_spec_pack_v0.1"

CHANNEL_OFFER_CLAIM_SCOPE = "price_availability_configuration_context_only"
FIELD_INQUIRY_CLAIM_SCOPE = "qualitative_channel_lead_only"
PRODUCT_SPEC_CLAIM_SCOPE = "parser_gated_product_spec_context"
PRODUCT_TAXONOMY_CLAIM_SCOPE = "product_taxonomy_context"
COMPETITIVE_COMPARABLE_CLAIM_SCOPE = "competitive_comparable_context_only"
GENERATION_EDGE_CLAIM_SCOPE = "product_generation_context_only"
CUSTOMER_DEPLOYMENT_CLAIM_SCOPE = "official_customer_deployment_context_only"
SUPPLY_CHAIN_SIGNAL_CLAIM_SCOPE = "supply_chain_context_only"

CHANNEL_SOURCE_CLASSES = {
    "commerce_product_surface",
    "distributor_public_catalog",
    "pricing_page",
    "company_official_product_surface",
}
CHANNEL_ALLOWED_CLAIMS = [
    "price_context",
    "availability_context",
    "configuration_context",
    "delivery_lead_time_context",
]
CHANNEL_FORBIDDEN_CLAIMS = [
    "company_sales",
    "market_share",
    "sell_through",
    "company_ASP",
    "channel_inventory",
]
FIELD_INQUIRY_ALLOWED_CLAIMS = [
    "qualitative_channel_lead",
    "price_or_lead_time_sample",
    "verification_lead",
]
FIELD_INQUIRY_FORBIDDEN_CLAIMS = [
    "authority_fact",
    "company_sales",
    "market_share",
    "sell_through",
    "company_ASP",
    "channel_inventory",
]
DEPLOYMENT_SIGNAL_FORBIDDEN_CLAIMS = [
    "company_sales",
    "market_share",
    "sell_through",
    "company_ASP",
    "channel_inventory",
    "order_value",
    "backlog",
]
SUPPLY_CHAIN_SIGNAL_FORBIDDEN_CLAIMS = [
    "shipments",
    "allocation",
    "company_sales",
    "market_share",
    "sell_through",
    "company_ASP",
    "channel_inventory",
    "customer_concentration",
]


def build_product_spec_pack(state: Mapping[str, Any], *, max_items: int = 24) -> dict[str, Any]:
    rows = _candidate_rows(state)
    product_families: dict[str, dict[str, Any]] = {}
    product_models: dict[str, dict[str, Any]] = {}
    product_specs: list[dict[str, Any]] = []
    product_kpis: list[dict[str, Any]] = []
    generation_edges: list[dict[str, Any]] = []
    comparable_edges: list[dict[str, Any]] = []
    channel_offers: list[dict[str, Any]] = []
    field_inquiry_notes: list[dict[str, Any]] = []
    customer_deployment_signals: list[dict[str, Any]] = []
    supply_chain_signals: list[dict[str, Any]] = []
    commercial_gaps: list[dict[str, Any]] = []
    rejected_objects: list[dict[str, Any]] = []

    for index, row in enumerate(rows, start=1):
        ref = _evidence_ref(row, index)
        source_family = _source_family(row)
        source_class = _source_class(row)

        family = _product_family_from_row(row, ref=ref)
        if family:
            _merge_object(product_families, family, "product_family_id")

        if _is_commercial_gap_row(row):
            commercial_gaps.append(_commercial_gap_from_row(row, ref=ref))

        kpi = _product_kpi_ref_from_row(row, ref=ref)
        if kpi:
            product_kpis.append(kpi)

        if _has_model_signal(row):
            model = _product_model_from_row(row, ref=ref, allow_family_fallback=True)
            if model:
                _merge_object(product_models, model, "product_model_id")

        if _is_product_spec_candidate(row):
            model = _product_model_from_row(row, ref=ref, allow_family_fallback=True)
            spec, rejection = _product_spec_from_row(row, model=model, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif spec:
                product_specs.append(spec)
                if model:
                    _merge_object(product_models, model, "product_model_id")

        if _is_generation_edge_candidate(row):
            edge, rejection = _generation_edge_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif edge:
                generation_edges.append(edge)

        if _is_comparable_edge_candidate(row):
            edge, rejection = _comparable_edge_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif edge:
                comparable_edges.append(edge)

        if _is_channel_offer_candidate(row, source_class=source_class):
            offer, rejection = _channel_offer_from_row(row, source_family=source_family, source_class=source_class, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif offer:
                channel_offers.append(offer)
                model = _product_model_from_row(row, ref=ref, allow_family_fallback=True)
                if model:
                    _merge_object(product_models, model, "product_model_id")

        if _is_field_inquiry_candidate(row, source_class=source_class):
            note, rejection = _field_inquiry_note_from_row(row, source_family=source_family, source_class=source_class, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif note:
                field_inquiry_notes.append(note)
                model = _product_model_from_row(row, ref=ref, allow_inquiry_target=True)
                if model:
                    _merge_object(product_models, model, "product_model_id")

        if _is_customer_deployment_candidate(row, source_class=source_class):
            signal, rejection = _customer_deployment_signal_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif signal:
                customer_deployment_signals.append(signal)
                model = _product_model_from_row(row, ref=ref, allow_family_fallback=True)
                if model:
                    _merge_object(product_models, model, "product_model_id")

        if _is_supply_chain_signal_candidate(row):
            signal, rejection = _supply_chain_signal_from_row(row, ref=ref)
            if rejection:
                rejected_objects.append(rejection)
            elif signal:
                supply_chain_signals.append(signal)

    product_families_list = _cap_objects(product_families.values(), max_items=max_items)
    product_models_list = _cap_objects(product_models.values(), max_items=max_items)
    pack = {
        "schema_version": PRODUCT_SPEC_PACK_SCHEMA_VERSION,
        "pack_id": _stable_id("ProductSpecPack", [_state_run_id(state), str(len(rows)), _refs_digest(rows)]),
        "status": "pass",
        "policy": "parser_gated_product_objects_no_public_proxy_financial_promotion",
        "boundary_policy": {
            "channel_offer_claim_scope": CHANNEL_OFFER_CLAIM_SCOPE,
            "channel_offer_allowed_claims": CHANNEL_ALLOWED_CLAIMS,
            "channel_offer_forbidden_claims": CHANNEL_FORBIDDEN_CLAIMS,
            "field_inquiry_claim_scope": FIELD_INQUIRY_CLAIM_SCOPE,
            "field_inquiry_allowed_claims": FIELD_INQUIRY_ALLOWED_CLAIMS,
            "field_inquiry_forbidden_claims": FIELD_INQUIRY_FORBIDDEN_CLAIMS,
            "customer_deployment_claim_scope": CUSTOMER_DEPLOYMENT_CLAIM_SCOPE,
            "customer_deployment_forbidden_claims": DEPLOYMENT_SIGNAL_FORBIDDEN_CLAIMS,
            "supply_chain_signal_claim_scope": SUPPLY_CHAIN_SIGNAL_CLAIM_SCOPE,
            "supply_chain_signal_forbidden_claims": SUPPLY_CHAIN_SIGNAL_FORBIDDEN_CLAIMS,
            "public_proxy_financial_promotion": "forbidden",
        },
        "product_families": product_families_list,
        "product_models": product_models_list,
        "product_specs": _cap_objects(product_specs, max_items=max_items),
        "product_kpi_refs": _cap_objects(product_kpis, max_items=max_items),
        "generation_edges": _cap_objects(generation_edges, max_items=max_items),
        "competitive_comparable_edges": _cap_objects(comparable_edges, max_items=max_items),
        "channel_offers": _cap_objects(channel_offers, max_items=max_items),
        "field_inquiry_notes": _cap_objects(field_inquiry_notes, max_items=max_items),
        "customer_deployment_signals": _cap_objects(customer_deployment_signals, max_items=max_items),
        "supply_chain_signals": _cap_objects(supply_chain_signals, max_items=max_items),
        "commercial_gaps": _cap_objects(commercial_gaps, max_items=max_items),
        "rejected_objects": _cap_objects(rejected_objects, max_items=max_items),
    }
    pack["summary"] = _summary(pack, input_row_count=len(rows))
    validation = validate_product_spec_pack(pack)
    pack["validation"] = validation
    pack["status"] = validation["status"]
    return pack


def validate_product_spec_pack(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if str(payload.get("schema_version") or "") != PRODUCT_SPEC_PACK_SCHEMA_VERSION:
        errors.append({"type": "invalid_schema_version", "schema_version": str(payload.get("schema_version") or "")})

    for index, spec in enumerate(_mapping_items(payload.get("product_specs")), start=1):
        missing = _missing_fields(
            spec,
            ["spec_id", "product_model_id", "spec_name", "value", "unit", "region", "effective_date", "source_id", "claim_scope"],
        )
        if missing:
            errors.append({"type": "product_spec_required_fields_missing", "index": index, "missing_fields": missing})
        if str(spec.get("claim_scope") or "") not in {PRODUCT_SPEC_CLAIM_SCOPE, "parser_verified_product_spec"}:
            warnings.append({"type": "product_spec_unexpected_claim_scope", "index": index, "claim_scope": str(spec.get("claim_scope") or "")})

    for index, edge in enumerate(_mapping_items(payload.get("competitive_comparable_edges")), start=1):
        missing = _missing_fields(edge, ["comparable_edge_id", "product_model_id", "competitor_product_model_id", "comparable_dimensions", "region", "source_id"])
        if missing:
            errors.append({"type": "competitive_comparable_edge_required_fields_missing", "index": index, "missing_fields": missing})

    for index, offer in enumerate(_mapping_items(payload.get("channel_offers")), start=1):
        missing = _missing_fields(
            offer,
            [
                "channel_offer_id",
                "product_model_id",
                "channel_name",
                "source_class",
                "price",
                "currency",
                "availability",
                "region",
                "observed_at",
                "source_id",
                "claim_scope",
            ],
        )
        if missing:
            errors.append({"type": "channel_offer_required_fields_missing", "index": index, "missing_fields": missing})
        if bool(offer.get("exact_value_authority")):
            errors.append({"type": "channel_offer_exact_authority_forbidden", "index": index})
        if _contains_forbidden_claim_scope(offer, CHANNEL_FORBIDDEN_CLAIMS):
            errors.append({"type": "channel_offer_forbidden_claim_scope", "index": index})
        if not set(CHANNEL_FORBIDDEN_CLAIMS) <= set(_strings(offer.get("forbidden_claims"))):
            errors.append({"type": "channel_offer_forbidden_claims_incomplete", "index": index})

    for index, note in enumerate(_mapping_items(payload.get("field_inquiry_notes")), start=1):
        missing = _missing_fields(
            note,
            [
                "field_inquiry_id",
                "product_model_id",
                "provider_role",
                "inquiry_target",
                "inquiry_time",
                "region",
                "raw_record_ref",
                "confidence",
                "source_id",
                "claim_scope",
            ],
        )
        if missing:
            errors.append({"type": "field_inquiry_required_fields_missing", "index": index, "missing_fields": missing})
        if bool(note.get("exact_value_authority")):
            errors.append({"type": "field_inquiry_exact_authority_forbidden", "index": index})
        if _contains_forbidden_claim_scope(note, FIELD_INQUIRY_FORBIDDEN_CLAIMS):
            errors.append({"type": "field_inquiry_forbidden_claim_scope", "index": index})
        if "authority_fact" not in _strings(note.get("forbidden_claims")):
            errors.append({"type": "field_inquiry_authority_boundary_missing", "index": index})

    for index, signal in enumerate(_mapping_items(payload.get("customer_deployment_signals")), start=1):
        missing = _missing_fields(signal, ["deployment_signal_id", "ticker", "source_id", "claim_scope", "claim_boundary"])
        if missing:
            errors.append({"type": "customer_deployment_signal_required_fields_missing", "index": index, "missing_fields": missing})
        if bool(signal.get("exact_value_authority")):
            errors.append({"type": "customer_deployment_signal_exact_authority_forbidden", "index": index})
        if not set(DEPLOYMENT_SIGNAL_FORBIDDEN_CLAIMS) <= set(_strings(signal.get("forbidden_claims"))):
            errors.append({"type": "customer_deployment_signal_forbidden_claims_incomplete", "index": index})

    for index, signal in enumerate(_mapping_items(payload.get("supply_chain_signals")), start=1):
        missing = _missing_fields(signal, ["supply_chain_signal_id", "relationship_type", "source_id", "claim_scope", "claim_boundary"])
        if missing:
            errors.append({"type": "supply_chain_signal_required_fields_missing", "index": index, "missing_fields": missing})
        if bool(signal.get("exact_value_authority")):
            errors.append({"type": "supply_chain_signal_exact_authority_forbidden", "index": index})
        if not set(SUPPLY_CHAIN_SIGNAL_FORBIDDEN_CLAIMS) <= set(_strings(signal.get("forbidden_claims"))):
            errors.append({"type": "supply_chain_signal_forbidden_claims_incomplete", "index": index})

    return {
        "schema_version": "sec_agent_product_spec_pack_validation_v0.1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
    }


def compact_product_spec_pack(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    validation = payload.get("validation") if isinstance(payload.get("validation"), Mapping) else {}
    return {
        "schema_version": str(payload.get("schema_version") or PRODUCT_SPEC_PACK_SCHEMA_VERSION),
        "pack_id": str(payload.get("pack_id") or ""),
        "status": str(payload.get("status") or validation.get("status") or "pass"),
        "summary": dict(summary),
        "boundary_policy": dict(payload.get("boundary_policy") or {}) if isinstance(payload.get("boundary_policy"), Mapping) else {},
    }


def _candidate_rows(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_mapping_items(state.get("product_evidence_rows")))
    rows.extend(_mapping_items(state.get("public_source_context_rows")))
    rows.extend(_mapping_items(state.get("product_intelligence_context_rows")))
    rows.extend(
        row
        for row in _mapping_items(state.get("context_rows"))
        if _source_family(row) in {"company_product_evidence_graph", "public_source_context", "live_public_web_context"}
    )
    return rows


def _product_family_from_row(row: Mapping[str, Any], *, ref: str) -> dict[str, Any] | None:
    family_name = _first_text(row, "product_family", "product_family_name", "product_or_segment", "product", "normalized_product_label", "canonical_name")
    if not family_name:
        return None
    ticker = _first_text(row, "ticker", "company_ticker")
    family_id = _first_text(row, "product_family_id", "product_node_id") or _stable_id("ProductFamily", [ticker, family_name])
    return {
        "product_family_id": family_id,
        "ticker": ticker,
        "family_name": family_name,
        "source_id": _source_id(row, ref=ref),
        "source_family": _source_family(row),
        "claim_scope": PRODUCT_TAXONOMY_CLAIM_SCOPE,
        "evidence_refs": [ref],
        "exact_value_authority": _source_family(row) == "company_product_evidence_graph"
        and _promotion_status(row) in {"runtime_fact_allowed", "runtime_context_taxonomy_only"},
    }


def _product_model_from_row(
    row: Mapping[str, Any],
    *,
    ref: str,
    allow_family_fallback: bool = False,
    allow_inquiry_target: bool = False,
) -> dict[str, Any] | None:
    model_name = _model_name(row)
    if not model_name and allow_inquiry_target:
        model_name = _first_text(row, "inquiry_target")
    if not model_name and allow_family_fallback:
        model_name = _first_text(row, "product_or_segment", "product", "sku")
    if not model_name:
        return None
    ticker = _first_text(row, "ticker", "company_ticker")
    family_name = _first_text(row, "product_family", "product_family_name", "product_or_segment", "product") or model_name
    family_id = _first_text(row, "product_family_id", "product_node_id") or _stable_id("ProductFamily", [ticker, family_name])
    model_id = _first_text(row, "product_model_id", "model_id") or _stable_id("ProductModel", [ticker, family_id, model_name])
    return {
        "product_model_id": model_id,
        "product_family_id": family_id,
        "ticker": ticker,
        "model_name": model_name,
        "configuration": _first_text(row, "configuration", "sku_configuration", "trim", "edition") or "not_disclosed",
        "region": _region(row),
        "generation": _first_text(row, "generation", "model_generation", "version") or "not_disclosed",
        "launch_status": _first_text(row, "launch_status", "status", "regulatory_status") or "not_disclosed",
        "source_id": _source_id(row, ref=ref),
        "source_family": _source_family(row),
        "evidence_refs": [ref],
        "claim_scope": PRODUCT_TAXONOMY_CLAIM_SCOPE,
    }


def _product_spec_from_row(row: Mapping[str, Any], *, model: Mapping[str, Any] | None, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not model:
        return None, _rejection(row, ref=ref, object_type="ProductSpec", reason="product_model_required_fields_missing", missing_fields=["product_model_id", "model_name"])
    spec_name = _first_text(row, "spec_name", "product_spec_name", "spec_dimension", "dimension", "spec_type")
    value = _first_scalar(row, "spec_value", "value", "display_value", "numeric_value")
    unit = _first_text(row, "unit", "spec_unit")
    effective_date = _effective_date(row)
    missing = []
    if not spec_name:
        missing.append("spec_name")
    if value == "":
        missing.append("value")
    if not unit:
        missing.append("unit")
    if not effective_date:
        missing.append("effective_date")
    if missing:
        return None, _rejection(row, ref=ref, object_type="ProductSpec", reason="product_spec_required_fields_missing", missing_fields=missing)
    spec_id = _first_text(row, "spec_id", "product_spec_id") or _stable_id(
        "ProductSpec",
        [str(model.get("product_model_id") or ""), spec_name, str(value), unit, _region(row), effective_date],
    )
    return (
        {
            "spec_id": spec_id,
            "product_model_id": str(model.get("product_model_id") or ""),
            "spec_name": spec_name,
            "value": value,
            "unit": unit,
            "configuration": str(model.get("configuration") or "not_disclosed"),
            "region": _region(row),
            "effective_date": effective_date,
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "claim_scope": _first_text(row, "claim_scope") if _first_text(row, "claim_scope") == "parser_verified_product_spec" else PRODUCT_SPEC_CLAIM_SCOPE,
            "evidence_refs": [ref],
            "exact_value_authority": False,
        },
        None,
    )


def _product_kpi_ref_from_row(row: Mapping[str, Any], *, ref: str) -> dict[str, Any] | None:
    if _source_family(row) != "company_product_evidence_graph":
        return None
    if _promotion_status(row) != "runtime_fact_allowed" or not bool(row.get("exact_value_authority", False)):
        return None
    product = _first_text(row, "product_or_segment", "product", "product_family", "normalized_product_label")
    metric = _first_text(row, "metric_family", "metric", "metric_name")
    value = _first_scalar(row, "value", "numeric_value", "display_value")
    if not product or not metric or value == "":
        return None
    return {
        "product_kpi_ref_id": _stable_id("ProductKPIRef", [ref, product, metric]),
        "ticker": _first_text(row, "ticker", "company_ticker"),
        "product_or_segment": product,
        "metric": metric,
        "value": value,
        "unit": _first_text(row, "unit"),
        "period": _first_text(row, "period", "period_role", "fiscal_year", "source_fiscal_year"),
        "source_id": _source_id(row, ref=ref),
        "source_family": "company_product_evidence_graph",
        "evidence_refs": [ref],
        "claim_scope": "company_disclosed_product_kpi",
        "exact_value_authority": True,
    }


def _generation_edge_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    prior = _first_text(row, "prior_product_model_id", "prior_model_id", "previous_product_model_id", "prior_model", "previous_model")
    current = _first_text(row, "current_product_model_id", "current_model_id", "product_model_id", "current_model", "model_name")
    dimensions = _strings(row.get("comparable_dimensions") or row.get("comparison_dimensions") or row.get("spec_dimensions")) or ["generation"]
    if not prior or not current:
        return None, _rejection(row, ref=ref, object_type="ProductGenerationEdge", reason="generation_edge_required_fields_missing", missing_fields=["prior_product_model_id", "current_product_model_id"])
    return (
        {
            "generation_edge_id": _first_text(row, "generation_edge_id") or _stable_id("ProductGenerationEdge", [prior, current, ",".join(dimensions)]),
            "prior_product_model_id": prior,
            "current_product_model_id": current,
            "comparable_dimensions": dimensions,
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "claim_scope": GENERATION_EDGE_CLAIM_SCOPE,
            "evidence_refs": [ref],
            "exact_value_authority": False,
        },
        None,
    )


def _comparable_edge_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    model_id = _first_text(row, "product_model_id", "model_id", "model_name")
    competitor_id = _first_text(row, "competitor_product_model_id", "competitor_model_id", "competitor_model", "peer_model")
    dimensions = _strings(row.get("comparable_dimensions") or row.get("comparison_dimensions") or row.get("spec_dimensions"))
    missing = []
    if not model_id:
        missing.append("product_model_id")
    if not competitor_id:
        missing.append("competitor_product_model_id")
    if not dimensions:
        missing.append("comparable_dimensions")
    if missing:
        return None, _rejection(row, ref=ref, object_type="CompetitiveComparableEdge", reason="competitive_comparable_required_fields_missing", missing_fields=missing)
    return (
        {
            "comparable_edge_id": _first_text(row, "comparable_edge_id") or _stable_id("CompetitiveComparableEdge", [model_id, competitor_id, ",".join(dimensions), _region(row)]),
            "product_model_id": model_id,
            "competitor_product_model_id": competitor_id,
            "comparable_dimensions": dimensions,
            "region": _region(row),
            "source_id": _source_id(row, ref=ref),
            "source_family": _source_family(row),
            "claim_scope": COMPETITIVE_COMPARABLE_CLAIM_SCOPE,
            "evidence_refs": [ref],
            "exact_value_authority": False,
        },
        None,
    )


def _channel_offer_from_row(
    row: Mapping[str, Any],
    *,
    source_family: str,
    source_class: str,
    ref: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if _forbidden_promotion_attempt(row, CHANNEL_FORBIDDEN_CLAIMS):
        return None, _rejection(row, ref=ref, object_type="ChannelOffer", reason="channel_offer_forbidden_promotion_attempt")
    model = _product_model_from_row(row, ref=ref, allow_family_fallback=True)
    if not model:
        return None, _rejection(row, ref=ref, object_type="ChannelOffer", reason="product_model_required_fields_missing", missing_fields=["product_model_id", "model_name"])
    price = _first_scalar(row, "price", "listed_price", "offer_price", "display_price")
    availability = _first_text(row, "availability", "stock_status", "lead_time", "delivery_lead_time")
    configuration = _first_text(row, "configuration", "sku_configuration", "trim", "edition")
    if price == "" and not availability and not configuration:
        return None, _rejection(row, ref=ref, object_type="ChannelOffer", reason="observable_channel_offer_field_missing", missing_fields=["price_or_availability_or_configuration"])
    channel_name = _first_text(row, "channel_name", "source_name", "domain", "underlying_source_id", "source_id") or source_class or source_family
    observed_at = _observed_at(row)
    if not observed_at:
        return None, _rejection(row, ref=ref, object_type="ChannelOffer", reason="channel_offer_observed_at_missing", missing_fields=["observed_at"])
    return (
        {
            "channel_offer_id": _first_text(row, "channel_offer_id") or _stable_id("ChannelOffer", [str(model.get("product_model_id") or ""), channel_name, observed_at, ref]),
            "product_model_id": str(model.get("product_model_id") or ""),
            "channel_name": channel_name,
            "source_class": source_class or "commerce_product_surface",
            "price": price if price != "" else "not_disclosed",
            "currency": _first_text(row, "currency", "price_currency") or _infer_currency(price) or "not_disclosed",
            "availability": availability or "not_disclosed",
            "configuration": configuration or str(model.get("configuration") or "not_disclosed"),
            "region": _region(row),
            "observed_at": observed_at,
            "source_id": _source_id(row, ref=ref),
            "source_family": source_family,
            "claim_scope": CHANNEL_OFFER_CLAIM_SCOPE,
            "allowed_claims": CHANNEL_ALLOWED_CLAIMS,
            "forbidden_claims": CHANNEL_FORBIDDEN_CLAIMS,
            "evidence_refs": [ref],
            "exact_value_authority": False,
            "context_only": True,
        },
        None,
    )


def _field_inquiry_note_from_row(
    row: Mapping[str, Any],
    *,
    source_family: str,
    source_class: str,
    ref: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if _forbidden_promotion_attempt(row, FIELD_INQUIRY_FORBIDDEN_CLAIMS):
        return None, _rejection(row, ref=ref, object_type="FieldInquiryNote", reason="field_inquiry_forbidden_promotion_attempt")
    model = _product_model_from_row(row, ref=ref, allow_inquiry_target=True)
    if not model:
        return None, _rejection(row, ref=ref, object_type="FieldInquiryNote", reason="product_model_required_fields_missing", missing_fields=["product_model_id", "inquiry_target"])
    inquiry_time = _first_text(row, "inquiry_time", "observed_at", "as_of_date", "source_date")
    if not inquiry_time:
        return None, _rejection(row, ref=ref, object_type="FieldInquiryNote", reason="field_inquiry_time_missing", missing_fields=["inquiry_time"])
    inquiry_target = _first_text(row, "inquiry_target", "product_model_name", "model_name", "product_or_segment") or str(model.get("model_name") or "")
    return (
        {
            "field_inquiry_id": _first_text(row, "field_inquiry_id") or _stable_id("FieldInquiryNote", [str(model.get("product_model_id") or ""), inquiry_time, ref]),
            "product_model_id": str(model.get("product_model_id") or ""),
            "provider_role": _first_text(row, "provider_role", "respondent_role", "source_role") or "unknown_public_contact",
            "inquiry_target": inquiry_target,
            "inquiry_time": inquiry_time,
            "region": _region(row),
            "raw_record_ref": _first_text(row, "raw_record_ref") or ref,
            "confidence": _first_text(row, "confidence", "confidence_score") or "low",
            "source_id": _source_id(row, ref=ref),
            "source_family": source_family,
            "source_class": source_class or "field_inquiry_note",
            "claim_scope": FIELD_INQUIRY_CLAIM_SCOPE,
            "allowed_claims": FIELD_INQUIRY_ALLOWED_CLAIMS,
            "forbidden_claims": FIELD_INQUIRY_FORBIDDEN_CLAIMS,
            "evidence_refs": [ref],
            "exact_value_authority": False,
            "context_only": True,
        },
        None,
    )


def _customer_deployment_signal_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if _forbidden_promotion_attempt(row, DEPLOYMENT_SIGNAL_FORBIDDEN_CLAIMS):
        return None, _rejection(row, ref=ref, object_type="CustomerDeploymentSignal", reason="customer_deployment_forbidden_promotion_attempt")
    ticker = _first_text(row, "ticker", "company_ticker")
    product = _first_text(row, "product_or_segment", "product_family", "product", "model_name")
    source_id = _source_id(row, ref=ref)
    if not ticker or not source_id:
        return None, _rejection(row, ref=ref, object_type="CustomerDeploymentSignal", reason="customer_deployment_required_fields_missing", missing_fields=["ticker", "source_id"])
    return (
        {
            "deployment_signal_id": _first_text(row, "deployment_signal_id") or _stable_id("CustomerDeploymentSignal", [ticker, product, source_id]),
            "ticker": ticker,
            "product_model_id": _first_text(row, "product_model_id") or _stable_id("ProductModel", [ticker, product or "product_context"]),
            "product_or_segment": product or "not_disclosed",
            "counterparty": _first_text(row, "counterparty", "customer", "recipient") or "not_disclosed",
            "deployment_signal": _first_text(row, "deployment_signal", "summary", "metric", "metric_name") or "official deployment/order context",
            "period": _first_text(row, "period", "observed_at", "as_of_date", "source_date") or "not_disclosed",
            "region": _region(row),
            "source_id": source_id,
            "source_family": _source_family(row),
            "claim_scope": CUSTOMER_DEPLOYMENT_CLAIM_SCOPE,
            "claim_boundary": _first_text(row, "claim_boundary") or "deployment context only; no revenue, sales, ASP, share, backlog, or order-value authority",
            "forbidden_claims": DEPLOYMENT_SIGNAL_FORBIDDEN_CLAIMS,
            "evidence_refs": [ref],
            "exact_value_authority": False,
            "context_only": True,
        },
        None,
    )


def _supply_chain_signal_from_row(row: Mapping[str, Any], *, ref: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if _forbidden_promotion_attempt(row, SUPPLY_CHAIN_SIGNAL_FORBIDDEN_CLAIMS):
        return None, _rejection(row, ref=ref, object_type="ProductSupplyChainSignal", reason="supply_chain_forbidden_promotion_attempt")
    relationship_type = _first_text(row, "relationship_type", "edge_type", "authority_type")
    source_id = _source_id(row, ref=ref)
    if not relationship_type or not source_id:
        return None, _rejection(row, ref=ref, object_type="ProductSupplyChainSignal", reason="supply_chain_required_fields_missing", missing_fields=["relationship_type", "source_id"])
    return (
        {
            "supply_chain_signal_id": _first_text(row, "supply_chain_signal_id") or _stable_id("ProductSupplyChainSignal", [relationship_type, source_id]),
            "ticker": _first_text(row, "ticker", "company_ticker"),
            "relationship_type": relationship_type,
            "from_product_node_id": _first_text(row, "from_product_node_id", "from_node_id", "product_model_id"),
            "to_product_node_id": _first_text(row, "to_product_node_id", "to_node_id", "competitor_product_model_id"),
            "source_id": source_id,
            "source_family": _source_family(row),
            "claim_scope": SUPPLY_CHAIN_SIGNAL_CLAIM_SCOPE,
            "claim_boundary": _first_text(row, "claim_boundary") or "supply-chain context only; no shipment, allocation, revenue, customer-concentration, or order-volume authority",
            "forbidden_claims": SUPPLY_CHAIN_SIGNAL_FORBIDDEN_CLAIMS,
            "evidence_refs": [ref],
            "exact_value_authority": False,
            "context_only": True,
        },
        None,
    )


def _commercial_gap_from_row(row: Mapping[str, Any], *, ref: str) -> dict[str, Any]:
    return {
        "gap_id": _first_text(row, "gap_id") or _stable_id("CommercialGap", [ref, _first_text(row, "missing_metric", "metric")]),
        "ticker": _first_text(row, "ticker", "company_ticker"),
        "missing_metric": _first_text(row, "missing_metric", "metric", "metric_family"),
        "gap_type": _first_text(row, "gap_type") or "commercial_market_tracker_gap",
        "why_public_sources_do_not_fill": _truncate(_first_text(row, "why_public_sources_do_not_fill", "summary", "description"), 500),
        "commercial_sources_that_would_fill": _strings(row.get("commercial_sources_that_would_fill")),
        "source_id": _source_id(row, ref=ref),
        "source_family": _source_family(row),
        "evidence_refs": [ref],
        "claim_scope": "bounded_gap_not_fallback",
    }


def _rejection(
    row: Mapping[str, Any],
    *,
    ref: str,
    object_type: str,
    reason: str,
    missing_fields: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "object_type": object_type,
        "evidence_ref": ref,
        "reason": reason,
        "missing_fields": list(missing_fields or []),
        "source_family": _source_family(row),
        "source_class": _source_class(row),
        "claim_scope": _first_text(row, "claim_scope", "allowed_claim_scope"),
    }


def _summary(pack: Mapping[str, Any], *, input_row_count: int) -> dict[str, Any]:
    return {
        "input_row_count": input_row_count,
        "product_family_count": len(pack.get("product_families") or []),
        "product_model_count": len(pack.get("product_models") or []),
        "product_spec_count": len(pack.get("product_specs") or []),
        "product_kpi_ref_count": len(pack.get("product_kpi_refs") or []),
        "generation_edge_count": len(pack.get("generation_edges") or []),
        "competitive_comparable_edge_count": len(pack.get("competitive_comparable_edges") or []),
        "channel_offer_count": len(pack.get("channel_offers") or []),
        "field_inquiry_note_count": len(pack.get("field_inquiry_notes") or []),
        "customer_deployment_signal_count": len(pack.get("customer_deployment_signals") or []),
        "supply_chain_signal_count": len(pack.get("supply_chain_signals") or []),
        "commercial_gap_count": len(pack.get("commercial_gaps") or []),
        "rejected_object_count": len(pack.get("rejected_objects") or []),
    }


def _merge_object(target: dict[str, dict[str, Any]], item: Mapping[str, Any], key: str) -> None:
    object_id = str(item.get(key) or "").strip()
    if not object_id:
        return
    if object_id not in target:
        target[object_id] = dict(item)
        return
    refs = [*(_strings(target[object_id].get("evidence_refs"))), *(_strings(item.get("evidence_refs")))]
    target[object_id]["evidence_refs"] = _dedupe(refs)


def _cap_objects(values: Any, *, max_items: int) -> list[dict[str, Any]]:
    return [dict(item) for item in values if isinstance(item, Mapping)][: max(0, int(max_items or 0))]


def _mapping_items(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]


def _missing_fields(item: Mapping[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if _empty_value(item.get(field))]


def _contains_forbidden_claim_scope(item: Mapping[str, Any], forbidden_claims: list[str]) -> bool:
    return _text_has_any(
        " ".join(
            [
                str(item.get("claim_scope") or ""),
                " ".join(_strings(item.get("allowed_claims"))),
                " ".join(_strings(item.get("claim_types"))),
                str(item.get("claim_type") or ""),
            ]
        ),
        forbidden_claims,
    )


def _forbidden_promotion_attempt(row: Mapping[str, Any], forbidden_claims: list[str]) -> bool:
    if bool(row.get("exact_value_authority")):
        return True
    return _contains_forbidden_claim_scope(row, forbidden_claims)


def _is_product_spec_candidate(row: Mapping[str, Any]) -> bool:
    if any(_first_text(row, key) for key in ("spec_name", "product_spec_name", "spec_dimension", "dimension", "spec_type")):
        return True
    return _row_type(row) == "productspec" or _first_text(row, "claim_scope") in {"parser_verified_product_spec", PRODUCT_SPEC_CLAIM_SCOPE}


def _is_generation_edge_candidate(row: Mapping[str, Any]) -> bool:
    return bool(_first_text(row, "prior_product_model_id", "prior_model_id", "previous_model", "prior_model")) and bool(
        _first_text(row, "current_product_model_id", "current_model_id", "current_model")
        or _first_text(row, "product_model_id", "model_name")
    )


def _is_comparable_edge_candidate(row: Mapping[str, Any]) -> bool:
    return bool(_first_text(row, "competitor_product_model_id", "competitor_model_id", "competitor_model", "peer_model")) or _row_type(row) in {
        "competitivecomparableedge",
        "comparableedge",
    }


def _is_channel_offer_candidate(row: Mapping[str, Any], *, source_class: str) -> bool:
    if source_class in {"commerce_product_surface", "distributor_public_catalog", "pricing_page"}:
        return True
    if source_class == "company_official_product_surface" and any(
        _first_text(row, key) for key in ("price", "listed_price", "offer_price", "availability", "stock_status", "delivery_lead_time", "channel_name")
    ):
        return True
    if _row_type(row) == "channeloffer":
        return True
    if any(_first_text(row, key) for key in ("price", "listed_price", "offer_price", "availability", "stock_status", "delivery_lead_time")):
        return True
    return bool(set(_strings(row.get("claim_types"))) & {"sku", "price", "listed_price", "availability", "sku_configuration"})


def _is_field_inquiry_candidate(row: Mapping[str, Any], *, source_class: str) -> bool:
    if source_class == "field_inquiry_note":
        return True
    if _row_type(row) == "fieldinquirynote":
        return True
    return bool(_first_text(row, "provider_role", "inquiry_target", "inquiry_time", "raw_record_ref"))


def _is_customer_deployment_candidate(row: Mapping[str, Any], *, source_class: str) -> bool:
    if source_class in {"official_customer_deployment_event", "public_order_or_tender_context"}:
        return True
    if _row_type(row) in {"customerdeploymentsignal", "officialcustomerdeploymentevent"}:
        return True
    claim_scope = _first_text(row, "claim_scope")
    if claim_scope == CUSTOMER_DEPLOYMENT_CLAIM_SCOPE:
        return True
    return bool(_first_text(row, "deployment_signal", "counterparty", "customer")) and _text_has_any(
        " ".join([source_class, claim_scope, _first_text(row, "source_class")]),
        ["deployment", "customer", "order", "tender"],
    )


def _is_supply_chain_signal_candidate(row: Mapping[str, Any]) -> bool:
    if _row_type(row) in {"productsupplychainsignal", "supplychainsignal"}:
        return True
    if _first_text(row, "claim_scope") == SUPPLY_CHAIN_SIGNAL_CLAIM_SCOPE:
        return True
    authority = _first_text(row, "authority_type")
    return authority == "supply_chain_signal" or _text_has_any(
        " ".join([_first_text(row, "relationship_type", "edge_type"), _first_text(row, "summary")]),
        ["supply", "supplier", "component_input", "enables_production", "manufacturing_dependency"],
    )


def _is_commercial_gap_row(row: Mapping[str, Any]) -> bool:
    return _promotion_status(row) == "gap_exposed_not_fallback" or _text_has_any(
        " ".join([_first_text(row, "gap_type"), _first_text(row, "missing_metric"), _first_text(row, "summary")]),
        ["commercial_market_tracker_gap", "sell_through", "market_share", "channel_inventory", "ASP", "POS", "prescription_volume"],
    )


def _has_model_signal(row: Mapping[str, Any]) -> bool:
    if _model_name(row):
        return True
    if _row_type(row) == "productmodel":
        return True
    return any(
        (
            _is_product_spec_candidate(row),
            _is_channel_offer_candidate(row, source_class=_source_class(row)),
            _is_field_inquiry_candidate(row, source_class=_source_class(row)),
        )
    )


def _row_type(row: Mapping[str, Any]) -> str:
    text = _first_text(row, "object_type", "row_type", "record_type", "node_type", "edge_type")
    return text.replace("_", "").replace("-", "").lower()


def _model_name(row: Mapping[str, Any]) -> str:
    return _first_text(row, "product_model_name", "model_name", "model", "sku", "sku_name", "product_sku")


def _evidence_ref(row: Mapping[str, Any], index: int) -> str:
    return (
        _first_text(row, "evidence_ref", "evidence_id", "metric_id", "fact_id", "gap_id", "source_id", "id")
        or f"product_spec_pack_row_{index}"
    )


def _source_id(row: Mapping[str, Any], *, ref: str) -> str:
    return _first_text(row, "source_id", "underlying_source_id", "snapshot_id", "url", "snapshot_url") or ref


def _source_family(row: Mapping[str, Any]) -> str:
    family = _first_text(row, "source_family")
    runtime_family = _first_text(row, "runtime_source_family")
    tier = _first_text(row, "source_tier")
    if family:
        return family
    if runtime_family:
        return runtime_family
    if tier:
        return tier
    return ""


def _source_class(row: Mapping[str, Any]) -> str:
    source_class = _first_text(row, "source_class")
    if source_class:
        return source_class
    if any(_first_text(row, key) for key in ("price", "listed_price", "availability", "stock_status", "delivery_lead_time")):
        return "commerce_product_surface"
    if _source_family(row) == "live_public_web_context" and set(_strings(row.get("claim_types"))) & {"sku", "price", "availability"}:
        return "commerce_product_surface"
    if _first_text(row, "underlying_source_family") == "official_product_status":
        return "official_regulatory_or_scientific"
    return ""


def _promotion_status(row: Mapping[str, Any]) -> str:
    return _first_text(row, "promotion_status", "runtime_promotion_status", "node_promotion_status")


def _region(row: Mapping[str, Any]) -> str:
    return _first_text(row, "region", "market", "country", "geography") or "global_or_not_disclosed"


def _effective_date(row: Mapping[str, Any]) -> str:
    return _first_text(row, "effective_date", "observed_at", "as_of_date", "period_end", "source_date", "period", "fiscal_year")


def _observed_at(row: Mapping[str, Any]) -> str:
    return _first_text(row, "observed_at", "as_of_date", "snapshot_time", "source_date", "period_end")


def _infer_currency(value: Any) -> str:
    text = str(value or "")
    if "$" in text or "usd" in text.lower():
        return "USD"
    if "eur" in text.lower() or "EUR" in text:
        return "EUR"
    if "gbp" in text.lower() or "GBP" in text or "£" in text:
        return "GBP"
    if "jpy" in text.lower() or "JPY" in text or "¥" in text:
        return "JPY"
    return ""


def _first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            for item in value:
                text = str(item or "").strip()
                if text:
                    return text
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _first_scalar(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple, set, dict)):
            continue
        text = str(value).strip()
        if text or value == 0:
            return text
    return ""


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple, set)):
        raw = [str(item or "").strip() for item in value]
    else:
        raw = [str(value or "").strip()]
    return _dedupe(item for item in raw if item)


def _dedupe(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _text_has_any(text: str, needles: list[str]) -> bool:
    lower = str(text or "").lower()
    return any(str(needle or "").lower() in lower for needle in needles if str(needle or "").strip())


def _empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _truncate(text: str, limit: int) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)].rstrip() + "..."


def _stable_id(prefix: str, parts: list[str]) -> str:
    raw = json.dumps([prefix, *[str(part or "") for part in parts]], ensure_ascii=True, sort_keys=True)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}::{digest}"


def _refs_digest(rows: list[Mapping[str, Any]]) -> str:
    refs = [_evidence_ref(row, index) for index, row in enumerate(rows, start=1)]
    return hashlib.sha1(json.dumps(refs, ensure_ascii=True).encode("utf-8")).hexdigest()[:16]


def _state_run_id(state: Mapping[str, Any]) -> str:
    return str(state.get("run_id") or state.get("trace_id") or "runtime_state")
