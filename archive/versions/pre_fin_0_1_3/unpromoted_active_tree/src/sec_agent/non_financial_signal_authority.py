from __future__ import annotations

from typing import Any, Iterable, Mapping


NON_FINANCIAL_SIGNAL_AUTHORITY_SCHEMA_VERSION = "finsight_non_financial_signal_authority_v0_1"

EXACT_FINANCIAL_FORBIDDEN_CLAIMS = {
    "reported_financial_fact",
    "company_reported_financial_fact",
    "company_reported_product_fact",
    "company_disclosed_product_kpi",
    "product_kpi",
    "product_revenue",
    "product_sales",
    "sku_revenue",
    "unit_sales",
    "shipments",
    "ASP",
    "asp",
    "average_selling_price",
    "market_share",
    "sell_through",
    "channel_inventory",
    "customer_order_value",
    "backlog",
}

NON_FINANCIAL_THESIS_CLAIM_TYPES = {
    "technical_product_spec",
    "product_comparison_context",
    "product_capability_signal",
    "product_generation_signal",
    "benchmark_signal",
    "deployment_signal",
    "customer_adoption_signal",
    "official_customer_order_or_deployment_event",
    "customer_order_or_deployment_event_signal",
    "demand_proxy_context",
    "ecosystem_deployment_signal",
    "developer_ecosystem_signal",
    "supply_chain_signal",
    "industry_operating_signal",
    "business_mix_signal",
    "regulatory_signal",
    "public_order_signal",
    "hiring_capacity_signal",
    "technology_research_signal",
    "macro_driver_signal",
    "market_expectation_signal",
    "relationship_hypothesis",
    "business_observation",
}

ROLE_TO_SIGNAL_AUTHORITY: dict[str, tuple[str, list[str]]] = {
    "technical_product_spec": (
        "technical_fact",
        ["technical_product_spec", "product_comparison_context", "product_capability_signal"],
    ),
    "product_generation_edge": (
        "technical_generation_signal",
        ["product_generation_signal", "product_comparison_context", "product_capability_signal"],
    ),
    "product_benchmark_proxy": (
        "technical_benchmark_signal",
        ["benchmark_signal", "product_capability_signal", "product_comparison_context"],
    ),
    "customer_deployment_proxy": (
        "customer_deployment_signal",
        ["deployment_signal", "customer_adoption_signal", "demand_proxy_context"],
    ),
    "product_ecosystem_deployment_context": (
        "ecosystem_deployment_signal",
        ["ecosystem_deployment_signal", "supply_chain_signal", "demand_proxy_context"],
    ),
    "industry_operating_metric": (
        "industry_operating_signal",
        ["industry_operating_signal", "business_observation"],
    ),
    "business_mix_operating_metric": (
        "business_mix_signal",
        ["business_mix_signal", "industry_operating_signal", "business_observation"],
    ),
    "supply_chain_official_relationship": (
        "supply_chain_signal",
        ["supply_chain_signal", "relationship_hypothesis", "business_observation"],
    ),
    "official_customer_order_or_deployment_event": (
        "customer_order_or_deployment_event_signal",
        [
            "official_customer_order_or_deployment_event",
            "deployment_signal",
            "customer_adoption_signal",
            "demand_proxy_context",
            "supply_chain_signal",
            "business_observation",
        ],
    ),
    "official_product_surface": (
        "technical_fact",
        ["technical_product_spec", "product_comparison_context", "product_capability_signal", "business_observation"],
    ),
    "trusted_external_context": (
        "market_or_industry_context_signal",
        ["market_expectation_signal", "business_observation"],
    ),
    "macro_official_context": (
        "macro_driver_signal",
        ["macro_driver_signal", "business_observation"],
    ),
    "energy_utility_context": (
        "energy_utility_signal",
        ["macro_driver_signal", "business_observation"],
    ),
    "financial_regulatory_context": (
        "financial_regulatory_signal",
        ["macro_driver_signal", "business_observation"],
    ),
    "developer_ecosystem_proxy": (
        "developer_ecosystem_signal",
        ["developer_ecosystem_signal", "product_capability_signal", "business_observation"],
    ),
    "hiring_capacity_proxy": (
        "hiring_capacity_signal",
        ["hiring_capacity_signal", "business_observation"],
    ),
    "public_order_proxy": (
        "public_order_signal",
        ["public_order_signal", "demand_proxy_context", "business_observation"],
    ),
    "regulated_product_context": (
        "regulatory_signal",
        ["regulatory_signal", "business_observation"],
    ),
    "auto_product_identity_context": (
        "auto_product_identity_signal",
        ["regulatory_signal", "product_capability_signal", "business_observation"],
    ),
    "channel_offer_proxy": (
        "channel_presence_signal",
        ["business_observation", "demand_proxy_context"],
    ),
    "app_rank_store_proxy": (
        "app_marketplace_signal",
        ["business_observation", "demand_proxy_context"],
    ),
    "platform_review_proxy": (
        "platform_review_signal",
        ["business_observation", "demand_proxy_context"],
    ),
    "technology_research_proxy": (
        "technology_research_signal",
        ["technology_research_signal", "product_capability_signal", "business_observation"],
    ),
    "macro_driver": (
        "macro_driver_signal",
        ["macro_driver_signal", "business_observation"],
    ),
    "market_expectation_proxy": (
        "market_expectation_signal",
        ["market_expectation_signal", "business_observation"],
    ),
}

HIGH_STRENGTH_SOURCE_HINTS = {
    "official",
    "company_ir",
    "company_product",
    "issuer",
    "regulator",
    "sec",
    "exchange",
    "government",
    "api",
    "patentsview",
    "openalex",
}


def attach_non_financial_signal_authority(row: Mapping[str, Any]) -> dict[str, Any]:
    """Return a row with explicit non-financial signal authority metadata."""
    output = dict(row)
    authority = classify_non_financial_signal_authority(output)
    output["non_financial_signal_authority"] = authority
    output["signal_authority_type"] = authority["signal_authority_type"]
    output["thesis_driver_authority"] = bool(authority["thesis_driver_authority"])
    output["signal_promotion_level"] = authority["promotion_level"]
    output["allowed_non_financial_claims"] = list(authority["allowed_claim_types"])
    output["forbidden_claims"] = _unique_strings(
        [
            *(_strings(output.get("forbidden_claims")) or []),
            *authority["forbidden_claim_types"],
        ]
    )
    output["exact_financial_fact_authority"] = bool(authority["exact_financial_fact_authority"])
    return output


def attach_non_financial_signal_authority_to_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [attach_non_financial_signal_authority(row) for row in rows]


def classify_non_financial_signal_authority(row: Mapping[str, Any]) -> dict[str, Any]:
    source_role = _first_text(row, "source_role", "source_entity_role", "record_type", "structured_context_type").lower()
    source_family = _first_text(row, "source_family", "runtime_source_family").lower()
    source_layer = _first_text(row, "source_layer_id", "layer_id", "source_layer").upper()
    source_id = _first_text(row, "source_id", "source_class", "runtime_source_context_source_key").lower()
    runtime_contract = _first_text(row, "runtime_contract").lower()
    signal_type, allowed_claim_types = _signal_type_and_claims(source_role, runtime_contract, source_family)
    source_strength_tier = _source_strength_tier(row, source_id=source_id, source_family=source_family)
    binding_status = _binding_status(row)
    has_citation = _has_citation(row)
    weak_signal = source_layer == "L4" or signal_type == "weak_lead" or _contains_any(source_id, ("forum", "reddit", "xhs", "social"))
    thesis_driver_authority = (
        not weak_signal
        and signal_type != "context_only"
        and source_strength_tier in {"L1_company_disclosed", "L2_official_or_regulatory", "L3_bound_trusted_proxy"}
        and has_citation
        and binding_status in {"issuer_bound", "industry_bound", "macro_or_market_bound"}
    )
    promotion_level = "thesis_driver_allowed" if thesis_driver_authority else "analyst_context_allowed"
    if weak_signal:
        promotion_level = "weak_lead_only"
        allowed_claim_types = ["weak_lead"]
    elif signal_type == "context_only":
        promotion_level = "analyst_context_allowed"
    exact_financial_fact_authority = _has_exact_financial_fact_authority(row)
    forbidden = sorted(EXACT_FINANCIAL_FORBIDDEN_CLAIMS - set(allowed_claim_types))
    return {
        "schema_version": NON_FINANCIAL_SIGNAL_AUTHORITY_SCHEMA_VERSION,
        "evidence_ref": str(row.get("evidence_ref") or row.get("fact_id") or row.get("source_id") or ""),
        "signal_authority_type": signal_type,
        "source_strength_tier": source_strength_tier,
        "binding_status": binding_status,
        "promotion_level": promotion_level,
        "thesis_driver_authority": thesis_driver_authority,
        "exact_financial_fact_authority": exact_financial_fact_authority,
        "allowed_claim_types": _unique_strings(allowed_claim_types),
        "forbidden_claim_types": forbidden,
        "required_caveats": _required_caveats(signal_type, exact_financial_fact_authority=exact_financial_fact_authority),
        "verification_requirements": _verification_requirements(signal_type),
        "confidence_floor": "medium" if thesis_driver_authority else "low",
        "claim_boundary": _claim_boundary(signal_type, exact_financial_fact_authority=exact_financial_fact_authority),
        "reason": _reason(signal_type, source_strength_tier, binding_status, has_citation, thesis_driver_authority),
    }


def validate_signal_claim_authority(claim: Mapping[str, Any], evidence_rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    claim_type = str(claim.get("claim_type") or "").strip()
    rows = [dict(row) for row in evidence_rows if isinstance(row, Mapping)]
    authorities = [
        row.get("non_financial_signal_authority")
        if isinstance(row.get("non_financial_signal_authority"), Mapping)
        else classify_non_financial_signal_authority(row)
        for row in rows
    ]
    if claim_type in EXACT_FINANCIAL_FORBIDDEN_CLAIMS:
        if any(_has_exact_financial_fact_authority(row) for row in rows):
            return {"status": "pass", "authority": "exact_fact_authority", "claim_type": claim_type}
        return {
            "status": "fail",
            "reason": "non_financial_signal_cannot_support_exact_financial_or_product_kpi_claim",
            "claim_type": claim_type,
            "available_signal_authority_types": _unique_strings(auth.get("signal_authority_type") for auth in authorities),
        }
    if claim_type in NON_FINANCIAL_THESIS_CLAIM_TYPES or claim_type in _all_allowed_claims(authorities):
        if any(bool(auth.get("thesis_driver_authority")) for auth in authorities):
            return {"status": "pass", "authority": "non_financial_thesis_driver_authority", "claim_type": claim_type}
        return {
            "status": "warn",
            "reason": "claim_supported_as_context_but_not_core_thesis_driver",
            "claim_type": claim_type,
            "available_signal_authority_types": _unique_strings(auth.get("signal_authority_type") for auth in authorities),
        }
    return {
        "status": "warn",
        "reason": "claim_type_not_registered_for_signal_authority",
        "claim_type": claim_type,
    }


def _signal_type_and_claims(source_role: str, runtime_contract: str, source_family: str) -> tuple[str, list[str]]:
    if source_role in ROLE_TO_SIGNAL_AUTHORITY:
        return ROLE_TO_SIGNAL_AUTHORITY[source_role]
    if "productspec" in runtime_contract or "product_spec" in source_role:
        return ROLE_TO_SIGNAL_AUTHORITY["technical_product_spec"]
    if "deployment" in runtime_contract:
        return ROLE_TO_SIGNAL_AUTHORITY["customer_deployment_proxy"]
    if "industryoperatingmetric" in runtime_contract:
        return ROLE_TO_SIGNAL_AUTHORITY["industry_operating_metric"]
    if source_family == "relationship_graph":
        return "relationship_graph_signal", ["relationship_hypothesis", "business_observation"]
    if source_family in {"market_snapshot", "industry_snapshot"}:
        return "market_or_industry_context_signal", ["market_expectation_signal", "business_observation"]
    if source_family in {"public_source_context", "live_public_web_context"}:
        return "context_only", ["business_observation"]
    return "context_only", ["business_observation"]


def _source_strength_tier(row: Mapping[str, Any], *, source_id: str, source_family: str) -> str:
    source_layer = _first_text(row, "source_layer_id", "layer_id", "source_layer").upper()
    source_role = _first_text(row, "source_role", "source_entity_role", "record_type", "structured_context_type").lower()
    if source_layer == "L1" or source_role == "primary_company_disclosure":
        return "L1_company_disclosed"
    if source_layer == "L2":
        return "L2_official_or_regulatory"
    if source_layer == "L3" and bool(row.get("can_enter_evidence_bundle", True)):
        return "L3_bound_trusted_proxy"
    if source_family == "company_product_evidence_graph":
        return "L1_company_disclosed"
    if source_family in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}:
        return "L1_company_disclosed"
    if source_family in {"public_source_context", "live_public_web_context"} and (
        _contains_any(source_id, HIGH_STRENGTH_SOURCE_HINTS) or str(row.get("source_layer_id") or "").upper() == "L2"
    ):
        return "L2_official_or_regulatory"
    if source_family in {"public_source_context", "live_public_web_context"}:
        return "L3_bound_trusted_proxy"
    if source_family in {"market_snapshot", "industry_snapshot", "relationship_graph"}:
        return "L3_bound_trusted_proxy"
    return "unscored_context"


def _binding_status(row: Mapping[str, Any]) -> str:
    if str(row.get("ticker") or row.get("company") or "").strip():
        return "issuer_bound"
    binding_values = " ".join(
        _first_text(row, key)
        for key in (
            "issuer_binding_status",
            "product_binding_status",
            "counterparty_binding_status",
            "entity_binding_claim_boundary",
        )
    ).lower()
    if any(token in binding_values for token in ("bound", "matched", "issuer_mentioned", "product_mentioned")):
        return "issuer_bound"
    role = _first_text(row, "source_role", "structured_context_type").lower()
    if any(token in role for token in ("macro", "market", "industry")):
        return "macro_or_market_bound"
    return "unbound_context"


def _has_citation(row: Mapping[str, Any]) -> bool:
    return bool(
        str(row.get("evidence_ref") or "").strip()
        or str(row.get("source_url") or "").strip()
        or str(row.get("citation_span") or "").strip()
        or str(row.get("raw_path") or "").strip()
        or bool(row.get("sample_urls"))
        or bool(row.get("sample_evidence_refs"))
    )


def _has_exact_financial_fact_authority(row: Mapping[str, Any]) -> bool:
    source_family = _first_text(row, "source_family", "runtime_source_family")
    return (
        source_family in {"company_product_evidence_graph", "primary_sec_filing", "company_authored_unaudited_sec_filing"}
        and bool(row.get("exact_value_authority"))
        and str(row.get("promotion_status") or "").strip() == "runtime_fact_allowed"
        and not bool(row.get("context_only"))
    )


def _required_caveats(signal_type: str, *, exact_financial_fact_authority: bool) -> list[str]:
    caveats = ["state_signal_scope_and_forbidden_exact_financial_inference"]
    if signal_type in {"customer_deployment_signal", "customer_order_or_deployment_event_signal", "public_order_signal"}:
        caveats.append("do_not_convert_units_or_deployments_to_revenue_or_order_value_without_disclosure")
    if signal_type in {"technical_fact", "technical_generation_signal", "technical_benchmark_signal"}:
        caveats.append("technical_capability_does_not_prove_sales_or_market_share")
    if signal_type in {"supply_chain_signal", "ecosystem_deployment_signal"}:
        caveats.append("relationship_or_supply_chain_signal_needs_counterparty_or_capacity_confirmation")
    if exact_financial_fact_authority:
        caveats.append("exact_fact_scope_limited_to_cited_metric_period_unit")
    return caveats


def _verification_requirements(signal_type: str) -> list[str]:
    requirements = ["citation_ref", "source_role", "claim_boundary"]
    if signal_type in {"customer_deployment_signal", "customer_order_or_deployment_event_signal", "supply_chain_signal", "ecosystem_deployment_signal"}:
        requirements.extend(["issuer_or_counterparty_binding", "counterevidence_check"])
    if signal_type in {"technical_fact", "technical_generation_signal", "technical_benchmark_signal"}:
        requirements.extend(["product_or_family_binding", "comparison_basis"])
    if signal_type in {"industry_operating_signal", "business_mix_signal"}:
        requirements.extend(["period", "unit", "company_disclosure_scope"])
    return _unique_strings(requirements)


def _claim_boundary(signal_type: str, *, exact_financial_fact_authority: bool) -> str:
    if exact_financial_fact_authority:
        return "Supports only the cited company-disclosed metric/period/unit; cannot be broadened to SKU revenue, ASP, share, sell-through, backlog, or customer order value."
    if signal_type == "technical_fact":
        return "Can support technical comparison and product capability analysis; cannot support sales, revenue, ASP, share, sell-through, backlog, or market demand as exact facts."
    if signal_type == "customer_deployment_signal":
        return "Can support bounded customer adoption or deployment-signal analysis; cannot support customer order value, revenue, ASP, or total demand without exact disclosure."
    if signal_type == "customer_order_or_deployment_event_signal":
        return (
            "Can support a bounded official customer/order/project/deployment event and its cited counterparty, "
            "product, date, and scale fields where present; cannot support revenue, backlog, ASP, shipment, "
            "sell-through, market share, or complete order-book claims without separate exact disclosure."
        )
    if signal_type in {"supply_chain_signal", "ecosystem_deployment_signal"}:
        return "Can support bounded supply-chain or ecosystem validation; cannot prove company sales, sell-through, share, or financial contribution."
    if signal_type in {"industry_operating_signal", "business_mix_signal"}:
        return "Can support business mix or industry operating analysis inside its cited scope; cannot become product/SKU exact KPI unless product-level value/unit/period is disclosed."
    return "Can support analyst context or a bounded thesis driver when cited and bound; cannot become exact financial fact authority."


def _reason(
    signal_type: str,
    source_strength_tier: str,
    binding_status: str,
    has_citation: bool,
    thesis_driver_authority: bool,
) -> str:
    status = "thesis-driver eligible" if thesis_driver_authority else "context-only or weak-signal bounded"
    return (
        f"{status}: signal_type={signal_type}, source_strength_tier={source_strength_tier}, "
        f"binding_status={binding_status}, citation={'present' if has_citation else 'missing'}"
    )


def _all_allowed_claims(authorities: Iterable[Mapping[str, Any]]) -> set[str]:
    claims: set[str] = set()
    for authority in authorities:
        claims.update(_strings(authority.get("allowed_claim_types")))
    return claims


def _contains_any(value: str, terms: Iterable[str]) -> bool:
    lower = str(value or "").lower()
    return any(str(term).lower() in lower for term in terms)


def _first_text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Mapping):
        return [str(value)] if value else []
    if isinstance(value, Iterable):
        output: list[str] = []
        for item in value:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                output.append(text)
        return output
    text = str(value).strip()
    return [text] if text else []


def _unique_strings(values: Iterable[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in _strings(value):
            if item in seen:
                continue
            seen.add(item)
            output.append(item)
    return output
