from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

import yaml

from sec_agent.kg_minimal_registry import load_kg_minimal_registry, validate_kg_minimal_registry


METRIC_PRODUCT_ONTOLOGY_SCHEMA_VERSION = "sec_agent_metric_product_ontology_v0.1"

DEFAULT_PRODUCT_METRIC_ONTOLOGY_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "data_sources" / "company_product_operating_metric_ontology_v0_1.yaml"
)

CONTEXT_ONLY_SOURCE_FAMILIES = {
    "public_source_context",
    "live_public_web_context",
    "market_snapshot",
    "industry_snapshot",
    "relationship_graph",
    "milvus_semantic",
    "run_artifact",
}

PRIMARY_EXACT_SOURCE_FAMILIES = {
    "primary_sec_filing",
    "sec_companyfacts_api",
    "sec_financial_statement_data_sets",
    "company_authored_unaudited_sec_filing",
}

PRODUCT_EXACT_SOURCE_FAMILIES = {
    "company_product_evidence_graph",
    "primary_sec_filing",
    "company_authored_unaudited_sec_filing",
}

REGISTRY_ALIAS_CANONICAL_REUSE = {
    "product_sales": "product_kpi:product_revenue",
    "accounts": "product_kpi:subscribers",
}


def build_metric_product_ontology_snapshot(state: Mapping[str, Any]) -> dict[str, Any]:
    kg_registry = _kg_minimal_registry(state)
    kg_validation = validate_kg_minimal_registry(kg_registry)
    definitions = _default_metric_definitions()
    definitions.extend(_product_metric_definitions_from_config(_product_ontology_config(state)))
    definitions.extend(_industry_metric_definitions_from_registry(kg_registry))
    metrics = _dedupe_metric_definitions(definitions)
    alias_index = _alias_index(metrics)
    observed = [_observed_metric(row, alias_index=alias_index) for _, row in _iter_metric_rows(state)]
    observed = [row for row in observed if row.get("raw_metric_text")]
    payload = {
        "schema_version": METRIC_PRODUCT_ONTOLOGY_SCHEMA_VERSION,
        "policy": "metric_product_ontology_no_string_similarity_promotion_v0_1",
        "registry_schema_version": str(kg_registry.get("schema_version") or ""),
        "registry_validation_status": kg_validation.get("status") or "",
        "metric_count": len(metrics),
        "metrics": metrics,
        "alias_index": {
            key: {
                "canonical_metric_id": value.get("canonical_metric_id") or "",
                "metric_type": value.get("metric_type") or "",
                "alias_status": value.get("alias_status") or "accepted",
            }
            for key, value in sorted(alias_index.items())
        },
        "industry_kpi_overrides": _industry_kpi_overrides(kg_registry),
        "product_spec_ontology": _product_spec_ontology_summary(kg_registry),
        "observed_metric_mappings": observed,
        "summary": {
            "by_metric_type": dict(sorted(Counter(row.get("metric_type") or "unknown" for row in metrics).items())),
            "financial_metric_count": len([row for row in metrics if row.get("metric_type") == "financial_metric"]),
            "product_kpi_count": len([row for row in metrics if row.get("metric_type") == "product_kpi"]),
            "observed_metric_count": len(observed),
            "observed_mapped_count": len([row for row in observed if row.get("match_status") == "mapped"]),
            "observed_rejected_alias_count": len([row for row in observed if row.get("match_status") == "rejected_alias"]),
            "observed_unmapped_count": len([row for row in observed if row.get("match_status") == "unmapped"]),
            "industry_kpi_override_count": sum(
                len(_string_list(row.get("financial_metrics")))
                + len(_string_list(row.get("product_kpis")))
                + len(_string_list(row.get("commercial_gap_metrics")))
                for row in _industry_kpi_overrides(kg_registry).values()
                if isinstance(row, Mapping)
            ),
            "product_spec_industry_count": len(
                ((_product_spec_ontology_summary(kg_registry).get("industry_spec_dimensions") or {}))
                if isinstance(_product_spec_ontology_summary(kg_registry).get("industry_spec_dimensions"), Mapping)
                else {}
            ),
        },
    }
    payload["validation"] = validate_metric_product_ontology(payload)
    return _jsonable(payload)


def validate_metric_product_ontology(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    accepted_alias_owner: dict[str, str] = {}
    for index, metric in enumerate([row for row in payload.get("metrics") or [] if isinstance(row, Mapping)]):
        canonical_id = str(metric.get("canonical_metric_id") or "").strip()
        metric_type = str(metric.get("metric_type") or "").strip()
        if not canonical_id:
            errors.append({"type": "canonical_metric_id_required", "index": index})
        elif canonical_id in seen_ids:
            errors.append({"type": "duplicate_canonical_metric_id", "canonical_metric_id": canonical_id})
        seen_ids.add(canonical_id)
        if metric_type not in {"financial_metric", "product_kpi"}:
            errors.append({"type": "invalid_metric_type", "canonical_metric_id": canonical_id, "metric_type": metric_type})
        if not _string_list(metric.get("accepted_aliases")):
            errors.append({"type": "accepted_aliases_required", "canonical_metric_id": canonical_id})
        if not str(metric.get("unit_family") or "").strip():
            errors.append({"type": "unit_family_required", "canonical_metric_id": canonical_id})
        if not str(metric.get("period_rule") or "").strip():
            errors.append({"type": "period_rule_required", "canonical_metric_id": canonical_id})
        if not _string_list(metric.get("allowed_source_families")):
            errors.append({"type": "allowed_source_families_required", "canonical_metric_id": canonical_id})
        if not _string_list(metric.get("cannot_infer_from")):
            warnings.append({"type": "cannot_infer_from_missing", "canonical_metric_id": canonical_id})
        for alias in _string_list(metric.get("accepted_aliases")):
            normalized = normalize_metric_alias(alias)
            if normalized in accepted_alias_owner and accepted_alias_owner[normalized] != canonical_id:
                errors.append(
                    {
                        "type": "accepted_alias_maps_to_multiple_metrics",
                        "alias": alias,
                        "canonical_metric_id": canonical_id,
                        "existing_canonical_metric_id": accepted_alias_owner[normalized],
                    }
                )
            accepted_alias_owner[normalized] = canonical_id
        if metric_type == "product_kpi":
            forbidden_exact_sources = sorted(set(_string_list(metric.get("exact_authority_source_families"))) & CONTEXT_ONLY_SOURCE_FAMILIES)
            if forbidden_exact_sources:
                errors.append(
                    {
                        "type": "product_kpi_context_source_marked_exact_authority",
                        "canonical_metric_id": canonical_id,
                        "source_families": forbidden_exact_sources,
                    }
                )
    return {
        "schema_version": "sec_agent_metric_product_ontology_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def resolve_metric_for_row(row: Mapping[str, Any], ontology: Mapping[str, Any]) -> dict[str, Any]:
    alias_index = ontology.get("alias_index") if isinstance(ontology.get("alias_index"), Mapping) else {}
    metrics = {
        str(item.get("canonical_metric_id") or ""): item
        for item in ontology.get("metrics") or []
        if isinstance(item, Mapping) and str(item.get("canonical_metric_id") or "").strip()
    }
    for text in _metric_text_candidates(row):
        normalized = normalize_metric_alias(text)
        if not normalized:
            continue
        entry = alias_index.get(normalized) if isinstance(alias_index.get(normalized), Mapping) else {}
        if entry:
            canonical_id = str(entry.get("canonical_metric_id") or "")
            metric = metrics.get(canonical_id, {})
            return _resolution_from_metric(
                metric,
                raw_metric_text=text,
                matched_alias=normalized,
                match_status="rejected_alias" if entry.get("alias_status") == "rejected" else "mapped",
            )
        direct = _direct_metric(metrics, text)
        if direct:
            return _resolution_from_metric(direct, raw_metric_text=text, matched_alias=normalize_metric_alias(text), match_status="mapped")
    raw_text = next((text for text in _metric_text_candidates(row) if normalize_metric_alias(text)), "")
    if raw_text:
        return {
            "match_status": "unmapped",
            "raw_metric_text": raw_text,
            "matched_alias": "",
            "canonical_metric_id": f"unmapped:{normalize_metric_alias(raw_text)}",
            "metric_type": "unknown",
            "unit_family": str(row.get("unit_family") or row.get("unit") or ""),
            "period_rule": "unknown",
            "allowed_source_families": [],
            "exact_authority_source_families": [],
            "cannot_infer_from": sorted(CONTEXT_ONLY_SOURCE_FAMILIES),
            "required_gates": ["manual_metric_mapping_required"],
        }
    return {
        "match_status": "missing",
        "raw_metric_text": "",
        "matched_alias": "",
        "canonical_metric_id": "",
        "metric_type": "unknown",
        "unit_family": "",
        "period_rule": "unknown",
        "allowed_source_families": [],
        "exact_authority_source_families": [],
        "cannot_infer_from": sorted(CONTEXT_ONLY_SOURCE_FAMILIES),
        "required_gates": ["metric_required"],
    }


def normalize_metric_alias(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _default_metric_definitions() -> list[dict[str, Any]]:
    common_financial_sources = sorted(PRIMARY_EXACT_SOURCE_FAMILIES)
    common_financial_cannot_infer = sorted(CONTEXT_ONLY_SOURCE_FAMILIES | {"company_product_evidence_graph"})
    return [
        _metric(
            "financial_metric:revenue",
            "financial_metric",
            "revenue",
            ["revenue", "revenues", "net sales", "sales", "operating revenue", "total revenue"],
            rejected_aliases=["revenue growth", "market share", "gross merchandise value"],
            unit_family="currency",
            period_rule="fiscal_period_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
        ),
        _metric(
            "financial_metric:gross_profit",
            "financial_metric",
            "gross_profit",
            ["gross profit", "gross margin dollars"],
            rejected_aliases=["gross margin", "gross margin percentage"],
            unit_family="currency",
            period_rule="fiscal_period_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
        ),
        _metric(
            "financial_metric:cost_of_revenue",
            "financial_metric",
            "cost_of_revenue",
            ["cost of revenue", "cost of goods sold", "cost of sales", "cogs"],
            rejected_aliases=["gross margin", "gross margin percentage"],
            unit_family="currency",
            period_rule="fiscal_period_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
        ),
        _metric(
            "financial_metric:operating_income",
            "financial_metric",
            "operating_income",
            ["operating income", "income from operations", "operating profit"],
            rejected_aliases=["operating margin"],
            unit_family="currency",
            period_rule="fiscal_period_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
        ),
        _metric(
            "financial_metric:net_income",
            "financial_metric",
            "net_income",
            ["net income", "net earnings", "net profit"],
            rejected_aliases=["eps", "earnings per share"],
            unit_family="currency",
            period_rule="fiscal_period_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
        ),
        _metric(
            "financial_metric:operating_cash_flow",
            "financial_metric",
            "operating_cash_flow",
            ["operating cash flow", "cash flow from operations", "net cash provided by operating activities"],
            rejected_aliases=["free cash flow", "cash flow margin"],
            unit_family="currency",
            period_rule="fiscal_period_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
        ),
        _metric(
            "financial_metric:fcf",
            "financial_metric",
            "fcf",
            ["fcf", "free cash flow", "free cash flows"],
            rejected_aliases=["operating cash flow", "cash flow margin"],
            unit_family="currency",
            period_rule="fiscal_period_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
            required_gates=["derived_metric_formula_required"],
        ),
        _metric(
            "financial_metric:capex",
            "financial_metric",
            "capex",
            ["capex", "capital expenditures", "capital expenditure", "payments for property and equipment"],
            rejected_aliases=["capital intensity"],
            unit_family="currency",
            period_rule="fiscal_period_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
        ),
        _metric(
            "financial_metric:debt",
            "financial_metric",
            "debt",
            ["debt", "total debt", "short-term debt", "long-term debt", "borrowings"],
            rejected_aliases=["net debt"],
            unit_family="currency",
            period_rule="balance_sheet_date_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
        ),
        _metric(
            "financial_metric:cash",
            "financial_metric",
            "cash",
            ["cash", "cash and cash equivalents", "cash equivalents", "cash and marketable securities"],
            rejected_aliases=["free cash flow"],
            unit_family="currency",
            period_rule="balance_sheet_date_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
        ),
        _metric(
            "financial_metric:inventory",
            "financial_metric",
            "inventory",
            ["inventory", "inventories", "merchandise inventories"],
            rejected_aliases=["channel inventory"],
            unit_family="currency",
            period_rule="balance_sheet_date_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
        ),
        _metric(
            "financial_metric:shares",
            "financial_metric",
            "shares",
            ["shares", "shares outstanding", "diluted shares", "weighted average shares"],
            rejected_aliases=["share price", "market share"],
            unit_family="shares",
            period_rule="fiscal_period_or_balance_sheet_date_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
        ),
        _metric(
            "financial_metric:eps",
            "financial_metric",
            "eps",
            ["eps", "earnings per share", "diluted eps", "basic eps"],
            rejected_aliases=["net income"],
            unit_family="currency_per_share",
            period_rule="fiscal_period_required",
            allowed_source_families=common_financial_sources,
            exact_authority_source_families=common_financial_sources,
            cannot_infer_from=common_financial_cannot_infer,
        ),
    ]


def _product_metric_definitions_from_config(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    metric_families = config.get("metric_families") if isinstance(config.get("metric_families"), Mapping) else {}
    cannot_infer = sorted(CONTEXT_ONLY_SOURCE_FAMILIES | {"commercial_market_data_and_consensus"})
    definitions = [
        _product_metric(
            "product_revenue",
            ["product revenue", "segment revenue", "segment net sales", "revenue by product category", "product sales"],
            unit_family="currency",
            source_config=metric_families.get("product_revenue") if isinstance(metric_families.get("product_revenue"), Mapping) else {},
            cannot_infer_from=cannot_infer,
        ),
        _product_metric(
            "deliveries",
            ["deliveries", "vehicle deliveries", "units delivered", "unit_sales_or_deliveries", "units sold"],
            unit_family="units",
            source_config=metric_families.get("unit_sales_or_deliveries") if isinstance(metric_families.get("unit_sales_or_deliveries"), Mapping) else {},
            cannot_infer_from=cannot_infer,
        ),
        _product_metric(
            "shipments",
            ["shipments", "shipped volume", "units shipped", "shipment volume"],
            unit_family="units",
            source_config=metric_families.get("shipments") if isinstance(metric_families.get("shipments"), Mapping) else {},
            cannot_infer_from=cannot_infer,
        ),
        _product_metric(
            "subscribers",
            ["subscribers", "paid subscribers", "accounts", "subscriber count"],
            unit_family="subscribers",
            source_config=metric_families.get("subscribers_or_arpu") if isinstance(metric_families.get("subscribers_or_arpu"), Mapping) else {},
            cannot_infer_from=cannot_infer,
        ),
        _product_metric(
            "mau",
            ["mau", "monthly active users", "active users"],
            unit_family="users",
            source_config=metric_families.get("subscribers_or_arpu") if isinstance(metric_families.get("subscribers_or_arpu"), Mapping) else {},
            cannot_infer_from=cannot_infer,
        ),
        _product_metric(
            "dau",
            ["dau", "daily active users"],
            unit_family="users",
            source_config=metric_families.get("subscribers_or_arpu") if isinstance(metric_families.get("subscribers_or_arpu"), Mapping) else {},
            cannot_infer_from=cannot_infer,
        ),
        _product_metric(
            "arpu",
            ["arpu", "average revenue per user", "average revenue per account"],
            unit_family="currency_per_user",
            source_config=metric_families.get("subscribers_or_arpu") if isinstance(metric_families.get("subscribers_or_arpu"), Mapping) else {},
            cannot_infer_from=cannot_infer,
        ),
        _product_metric("asp", ["asp", "average selling price"], unit_family="currency_per_unit", cannot_infer_from=cannot_infer),
        _product_metric(
            "bookings",
            ["bookings", "orders", "order intake"],
            unit_family="currency_or_units",
            source_config=metric_families.get("backlog_or_orders") if isinstance(metric_families.get("backlog_or_orders"), Mapping) else {},
            cannot_infer_from=cannot_infer,
        ),
        _product_metric(
            "backlog",
            ["backlog", "remaining performance obligations", "rpo", "order backlog"],
            unit_family="currency_or_units",
            source_config=metric_families.get("backlog_or_orders") if isinstance(metric_families.get("backlog_or_orders"), Mapping) else {},
            cannot_infer_from=cannot_infer,
        ),
        _product_metric("installed_base", ["installed base", "installed_base"], unit_family="units", cannot_infer_from=cannot_infer),
        _product_metric(
            "production",
            ["production", "throughput", "production volume"],
            unit_family="units_or_volume",
            source_config=metric_families.get("production_or_throughput") if isinstance(metric_families.get("production_or_throughput"), Mapping) else {},
            cannot_infer_from=cannot_infer,
        ),
        _product_metric("capacity", ["capacity", "production capacity"], unit_family="capacity", cannot_infer_from=cannot_infer),
        _product_metric("utilization", ["utilization", "utilization rate"], unit_family="percent", cannot_infer_from=cannot_infer),
        _product_metric("take_rate", ["take rate", "take_rate"], unit_family="percent", cannot_infer_from=cannot_infer),
        _product_metric("gmv", ["gmv", "gross merchandise value"], unit_family="currency", cannot_infer_from=cannot_infer),
        _product_metric(
            "same_store_sales",
            ["same-store sales", "same store sales", "comparable sales", "comps"],
            unit_family="percent",
            source_config=metric_families.get("same_store_sales") if isinstance(metric_families.get("same_store_sales"), Mapping) else {},
            cannot_infer_from=cannot_infer,
        ),
    ]
    return definitions


def _metric(
    canonical_id: str,
    metric_type: str,
    metric_family: str,
    accepted_aliases: list[str],
    *,
    rejected_aliases: list[str],
    unit_family: str,
    period_rule: str,
    allowed_source_families: list[str],
    exact_authority_source_families: list[str],
    cannot_infer_from: list[str],
    required_gates: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "canonical_metric_id": canonical_id,
        "metric_type": metric_type,
        "metric_family": metric_family,
        "accepted_aliases": _unique_strings([metric_family, *accepted_aliases, canonical_id]),
        "rejected_aliases": _unique_strings(rejected_aliases),
        "unit_family": unit_family,
        "period_rule": period_rule,
        "allowed_source_families": _unique_strings(allowed_source_families),
        "exact_authority_source_families": _unique_strings(exact_authority_source_families),
        "cannot_infer_from": _unique_strings(cannot_infer_from),
        "required_gates": _unique_strings(required_gates or ["source_boundary_gate", "unit_period_gate", "citation_gate"]),
    }


def _product_metric(
    metric_family: str,
    aliases: list[str],
    *,
    unit_family: str,
    cannot_infer_from: list[str],
    source_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config = source_config if isinstance(source_config, Mapping) else {}
    return _metric(
        f"product_kpi:{metric_family}",
        "product_kpi",
        metric_family,
        aliases,
        rejected_aliases=_string_list(config.get("forbidden_inferences")),
        unit_family=unit_family,
        period_rule="company_disclosed_product_period_required",
        allowed_source_families=sorted(PRODUCT_EXACT_SOURCE_FAMILIES),
        exact_authority_source_families=sorted(PRODUCT_EXACT_SOURCE_FAMILIES),
        cannot_infer_from=cannot_infer_from,
        required_gates=["product_binding_gate", "value_unit_period_product_parser", "citation_gate", "source_boundary_gate"],
    )


def _product_ontology_config(state: Mapping[str, Any]) -> dict[str, Any]:
    config = state.get("metric_product_ontology_config")
    if isinstance(config, Mapping):
        return dict(config)
    inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), Mapping) else {}
    path = (
        state.get("product_metric_ontology_path")
        or inventory.get("product_metric_ontology_path")
        or str(DEFAULT_PRODUCT_METRIC_ONTOLOGY_PATH)
    )
    candidate = Path(str(path))
    if not candidate.exists() or not candidate.is_file():
        return {}
    with candidate.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _kg_minimal_registry(state: Mapping[str, Any]) -> dict[str, Any]:
    registry = state.get("kg_minimal_registry")
    if isinstance(registry, Mapping):
        return dict(registry)
    inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), Mapping) else {}
    registry = inventory.get("kg_minimal_registry") if isinstance(inventory.get("kg_minimal_registry"), Mapping) else {}
    if registry:
        return dict(registry)
    path = state.get("kg_minimal_registry_path") or inventory.get("kg_minimal_registry_path")
    return load_kg_minimal_registry(path if str(path or "").strip() else None)


def _industry_metric_definitions_from_registry(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    k1 = registry.get("k1_industry_kpi_dictionary") if isinstance(registry.get("k1_industry_kpi_dictionary"), Mapping) else {}
    definitions: list[dict[str, Any]] = []
    cannot_infer = sorted(CONTEXT_ONLY_SOURCE_FAMILIES | {"commercial_market_data_and_consensus"})
    for industry, item in k1.items():
        if not isinstance(item, Mapping):
            continue
        for metric in _string_list(item.get("product_kpis")):
            normalized = normalize_metric_alias(metric)
            if not normalized:
                continue
            if normalized in REGISTRY_ALIAS_CANONICAL_REUSE:
                continue
            row = _product_metric(
                normalized,
                [metric],
                unit_family=_industry_metric_unit_family(normalized),
                cannot_infer_from=cannot_infer,
            )
            row["registry_source"] = "kg_minimal_p0_k1_k2_k3"
            row["industry_overrides"] = _unique_strings([*(row.get("industry_overrides") or []), str(industry)])
            definitions.append(row)
        for metric in _string_list(item.get("commercial_gap_metrics")):
            normalized = normalize_metric_alias(metric)
            if not normalized:
                continue
            if normalized in REGISTRY_ALIAS_CANONICAL_REUSE:
                continue
            row = _metric(
                f"product_kpi:{normalized}",
                "product_kpi",
                normalized,
                [metric],
                rejected_aliases=[],
                unit_family=_industry_metric_unit_family(normalized),
                period_rule="commercial_tracker_required_for_exact_company_claim",
                allowed_source_families=["commercial_market_tracker"],
                exact_authority_source_families=[],
                cannot_infer_from=sorted(CONTEXT_ONLY_SOURCE_FAMILIES | PRODUCT_EXACT_SOURCE_FAMILIES),
                required_gates=["commercial_gap_gate", "source_boundary_gate"],
            )
            row["registry_source"] = "kg_minimal_p0_k1_k2_k3"
            row["industry_overrides"] = _unique_strings([str(industry)])
            row["claim_boundary"] = "commercial_gap_metric_expose_gap_do_not_proxy"
            definitions.append(row)
    return definitions


def _industry_kpi_overrides(registry: Mapping[str, Any]) -> dict[str, dict[str, list[str]]]:
    k1 = registry.get("k1_industry_kpi_dictionary") if isinstance(registry.get("k1_industry_kpi_dictionary"), Mapping) else {}
    return {
        str(industry): {
            "financial_metrics": _string_list(item.get("financial_metrics")),
            "product_kpis": _string_list(item.get("product_kpis")),
            "commercial_gap_metrics": _string_list(item.get("commercial_gap_metrics")),
        }
        for industry, item in k1.items()
        if isinstance(item, Mapping)
    }


def _product_spec_ontology_summary(registry: Mapping[str, Any]) -> dict[str, Any]:
    k2 = registry.get("k2_product_spec_ontology") if isinstance(registry.get("k2_product_spec_ontology"), Mapping) else {}
    dimensions = k2.get("industry_spec_dimensions") if isinstance(k2.get("industry_spec_dimensions"), Mapping) else {}
    boundary = k2.get("channel_offer_boundary") if isinstance(k2.get("channel_offer_boundary"), Mapping) else {}
    return {
        "common_required_fields": _string_list(k2.get("common_required_fields")),
        "industry_spec_dimensions": {
            str(industry): _string_list(values)
            for industry, values in dimensions.items()
        },
        "channel_offer_boundary": {
            "allowed_claims": _string_list(boundary.get("allowed_claims")),
            "forbidden_claims": _string_list(boundary.get("forbidden_claims")),
        },
    }


def _industry_metric_unit_family(metric: str) -> str:
    normalized = normalize_metric_alias(metric)
    if any(token in normalized for token in ("margin", "rate", "share", "utilization", "cet1")):
        return "percent"
    if any(token in normalized for token in ("asp", "arpu", "price")):
        return "currency_per_unit"
    if any(token in normalized for token in ("revenue", "sales", "aum", "gmv", "pos", "rpo")):
        return "currency"
    if any(token in normalized for token in ("subscriber", "customer", "seat", "account", "user", "unit", "delivery", "shipment", "production", "registration")):
        return "units"
    return "unknown_or_industry_specific"


def _dedupe_metric_definitions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        canonical_id = str(row.get("canonical_metric_id") or "").strip()
        if not canonical_id:
            continue
        existing = by_id.get(canonical_id)
        if not existing:
            by_id[canonical_id] = row
            continue
        merged = dict(existing)
        for key in ("accepted_aliases", "rejected_aliases", "allowed_source_families", "exact_authority_source_families", "cannot_infer_from", "required_gates", "industry_overrides"):
            merged[key] = _unique_strings([*(existing.get(key) or []), *(row.get(key) or [])])
        if row.get("registry_source") and not merged.get("registry_source"):
            merged["registry_source"] = row.get("registry_source")
        if row.get("claim_boundary") and not merged.get("claim_boundary"):
            merged["claim_boundary"] = row.get("claim_boundary")
        by_id[canonical_id] = merged
    return sorted(by_id.values(), key=lambda item: str(item.get("canonical_metric_id") or ""))


def _alias_index(metrics: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for metric in metrics:
        canonical_id = str(metric.get("canonical_metric_id") or "")
        for alias in _string_list(metric.get("accepted_aliases")):
            normalized = normalize_metric_alias(alias)
            if normalized:
                index[normalized] = {
                    "canonical_metric_id": canonical_id,
                    "metric_type": str(metric.get("metric_type") or ""),
                    "alias_status": "accepted",
                }
        for alias in _string_list(metric.get("rejected_aliases")):
            normalized = normalize_metric_alias(alias)
            if normalized and normalized not in index:
                index[normalized] = {
                    "canonical_metric_id": canonical_id,
                    "metric_type": str(metric.get("metric_type") or ""),
                    "alias_status": "rejected",
                }
    return index


def _observed_metric(row: Mapping[str, Any], *, alias_index: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    raw_text = next((text for text in _metric_text_candidates(row) if normalize_metric_alias(text)), "")
    normalized = normalize_metric_alias(raw_text)
    entry = alias_index.get(normalized) if isinstance(alias_index.get(normalized), Mapping) else {}
    match_status = "unmapped"
    if entry:
        match_status = "rejected_alias" if entry.get("alias_status") == "rejected" else "mapped"
    return {
        "observed_metric_id": _stable_id("observed_metric", row.get("evidence_ref"), row.get("source_id"), raw_text),
        "raw_metric_text": raw_text,
        "normalized_alias": normalized,
        "match_status": match_status,
        "canonical_metric_id": str(entry.get("canonical_metric_id") or ""),
        "metric_type": str(entry.get("metric_type") or "unknown"),
        "ticker": str(row.get("ticker") or "").upper().strip(),
        "evidence_ref": str(row.get("evidence_ref") or row.get("evidence_id") or row.get("metric_id") or "").strip(),
        "source_family": str(row.get("source_family") or row.get("runtime_source_family") or "").strip(),
    }


def _iter_metric_rows(state: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    rows: list[tuple[str, Mapping[str, Any]]] = []
    for channel in (
        "runtime_ledger_rows",
        "product_evidence_rows",
        "context_rows",
        "market_snapshot_rows",
        "industry_snapshot_rows",
        "public_source_context_rows",
    ):
        for row in state.get(channel) or []:
            if isinstance(row, Mapping):
                rows.append((channel, row))
    return rows


def _metric_text_candidates(row: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key in (
        "canonical_metric_id",
        "metric_family",
        "metric_name",
        "metric",
        "field",
        "line_item",
        "label",
        "metric_id",
    ):
        value = row.get(key)
        if isinstance(value, str) and value.startswith(("fact_", "gap_", "ref_", "node_")):
            continue
        values.extend(_string_list(value))
    return _unique_strings(values)


def _direct_metric(metrics: Mapping[str, Mapping[str, Any]], text: str) -> Mapping[str, Any]:
    raw = str(text or "").strip()
    if raw in metrics:
        return metrics[raw]
    normalized = normalize_metric_alias(raw)
    for metric in metrics.values():
        if normalize_metric_alias(metric.get("canonical_metric_id")) == normalized:
            return metric
    return {}


def _resolution_from_metric(metric: Mapping[str, Any], *, raw_metric_text: str, matched_alias: str, match_status: str) -> dict[str, Any]:
    return {
        "match_status": match_status,
        "raw_metric_text": raw_metric_text,
        "matched_alias": matched_alias,
        "canonical_metric_id": str(metric.get("canonical_metric_id") or ""),
        "metric_type": str(metric.get("metric_type") or "unknown"),
        "unit_family": str(metric.get("unit_family") or ""),
        "period_rule": str(metric.get("period_rule") or ""),
        "allowed_source_families": _string_list(metric.get("allowed_source_families")),
        "exact_authority_source_families": _string_list(metric.get("exact_authority_source_families")),
        "cannot_infer_from": _string_list(metric.get("cannot_infer_from")),
        "required_gates": _string_list(metric.get("required_gates")),
    }


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Mapping):
        return [json.dumps(value, ensure_ascii=False, sort_keys=True)]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()]


def _unique_strings(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _string_list(value):
            if item and item not in seen:
                seen.add(item)
                out.append(item)
    return out


def _stable_id(prefix: str, *values: Any) -> str:
    raw = "|".join(str(value or "") for value in values)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value
