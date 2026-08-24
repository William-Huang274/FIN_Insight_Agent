from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation, getcontext
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.session import canonical_digest


getcontext().prec = 36

PRODUCT_VALUE_BRIDGE_PROGRAM_SCHEMA = "fin_ia_s2_product_value_bridge_program_v1_0"
PRODUCT_VALUE_BRIDGE_RESULT_SCHEMA = "fin_ia_s2_product_value_bridge_result_v1_0"


class ProductValueBridgeError(ValueError):
    """Raised when a product PVM or profit bridge crosses an authority boundary."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ProductValueBridgeError(code)


def _mapping(value: object, code: str) -> dict[str, Any]:
    _require(isinstance(value, Mapping), code)
    return deepcopy(dict(value))


def _rows(value: object, code: str) -> list[dict[str, Any]]:
    _require(isinstance(value, list), code)
    return [_mapping(row, code) for row in value]


def _strings(
    value: object, code: str, *, allow_empty: bool = False
) -> list[str]:
    _require(isinstance(value, list), code)
    rows = [str(row).strip() for row in value]
    _require(
        (allow_empty or bool(rows))
        and all(rows)
        and len(rows) == len(set(rows)),
        code,
    )
    return rows


def _decimal(value: object, code: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProductValueBridgeError(code) from exc
    _require(result.is_finite(), code)
    return result


def _decimal_string(value: Decimal) -> str:
    rendered = format(value.normalize(), "f")
    return "0" if rendered in {"-0", ""} else rendered


def _as_date(value: object, code: str) -> date:
    try:
        return date.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise ProductValueBridgeError(code) from exc


def _slot_facets(item: Mapping[str, Any], slot_id: str) -> set[str]:
    return {
        str(facet)
        for row in item.get("slot_bindings") or ()
        if isinstance(row, Mapping) and str(row.get("slot_id") or "") == slot_id
        for facet in row.get("facet_ids") or ()
    }


def _select_quantitative_row(
    *,
    rows: Sequence[Mapping[str, Any]],
    selector: Mapping[str, Any],
) -> dict[str, Any]:
    quantitative_kind = str(selector.get("quantitative_kind") or "")
    metric_id = str(selector.get("metric_id") or "")
    derived_metric_id = str(selector.get("derived_metric_id") or "")
    fiscal_year = int(selector.get("fiscal_year") or 0)
    fiscal_period = str(selector.get("fiscal_period") or "")
    period_role = str(selector.get("period_role") or "")
    matches = [
        dict(row)
        for row in rows
        if str(row.get("quantitative_kind") or "") == quantitative_kind
        and str(row.get("metric_id") or "") == metric_id
        and (not derived_metric_id or row.get("derived_metric_id") == derived_metric_id)
        and int(row.get("fiscal_year") or 0) == fiscal_year
        and str(row.get("fiscal_period") or "") == fiscal_period
        and str(row.get("period_role") or "") == period_role
    ]
    _require(matches, "product_bridge_quantitative_selector_unresolved")
    identity = {
        (
            str(row.get("value_decimal") or ""),
            str(row.get("unit") or ""),
            str(row.get("period_start") or ""),
            str(row.get("period_end") or ""),
        )
        for row in matches
    }
    _require(
        len(identity) == 1,
        "product_bridge_quantitative_selector_conflict",
    )
    matches.sort(key=lambda row: str(row.get("authority_ref") or ""))
    selected = matches[0]
    return {
        "selector_id": str(selector.get("selector_id") or ""),
        "quantitative_kind": quantitative_kind,
        "metric_id": metric_id,
        "derived_metric_id": derived_metric_id or None,
        "value_decimal": str(selected.get("value_decimal") or ""),
        "unit": str(selected.get("unit") or ""),
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "period_role": period_role,
        "period_start": selected.get("period_start"),
        "period_end": selected.get("period_end"),
        "authority_ref": selected.get("authority_ref"),
        "equivalent_authority_refs": sorted(
            str(row.get("authority_ref") or "") for row in matches
        ),
        "numeric_fact_authority": selected.get("numeric_fact_authority") is True,
        "deterministic_formula_authority": selected.get(
            "deterministic_formula_authority"
        )
        is True,
    }


def compile_product_value_bridge(
    *,
    program: Mapping[str, Any],
    evidence_pack: Mapping[str, Any],
    quantitative_projection: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    payload = deepcopy(dict(program))
    _require(
        payload.get("schema_version") == PRODUCT_VALUE_BRIDGE_PROGRAM_SCHEMA
        and payload.get("status") == "approved_zero_call_product_value_bridge",
        "product_bridge_program_header_invalid",
    )
    case_key = str(payload.get("case_key") or "").upper()
    research_as_of = str(payload.get("research_as_of") or "")
    pack_digest = str(evidence_pack.get("pack_payload_digest") or "")
    _require(
        case_key
        and str(evidence_pack.get("case_key") or "").upper() == case_key
        and str(evidence_pack.get("research_as_of") or "") == research_as_of
        and pack_digest == payload.get("evidence_pack_payload_digest")
        and quantitative_projection.get("case_key") == case_key
        and quantitative_projection.get("evidence_pack_binding", {}).get(
            "pack_payload_digest"
        )
        == pack_digest
        and quantitative_projection.get("task_readiness", {}).get("ready") is True
        and quantitative_projection.get("task_quantitative_projection_digest")
        == payload.get("task_quantitative_projection_digest"),
        "product_bridge_input_binding_invalid",
    )

    materials = {
        str(row.get("material_ref") or ""): _mapping(
            row, "product_bridge_source_material_invalid"
        )
        for row in evidence_pack.get("source_materials") or ()
        if isinstance(row, Mapping)
    }
    evidence_by_digest = {
        str(row.get("evidence_item_digest") or ""): _mapping(
            row, "product_bridge_evidence_item_invalid"
        )
        for row in evidence_pack.get("evidence_items") or ()
        if isinstance(row, Mapping)
    }
    support_catalog: dict[str, dict[str, Any]] = {}
    for support in _rows(
        payload.get("evidence_supports"),
        "product_bridge_evidence_supports_invalid",
    ):
        support_id = str(support.get("support_id") or "")
        digest = str(support.get("evidence_item_digest") or "")
        item = evidence_by_digest.get(digest)
        _require(
            support_id
            and support_id not in support_catalog
            and item is not None
            and item.get("target_id") == support.get("target_id")
            and item.get("writer_citable") is True
            and str(item.get("disposition") or "").startswith("accepted_")
            and item.get("causal_attribution_authorized") is False,
            "product_bridge_evidence_support_binding_invalid",
        )
        slot_id = str(support.get("required_slot_id") or "")
        required_facets = set(
            _strings(
                support.get("required_facet_ids"),
                "product_bridge_support_facets_invalid",
            )
        )
        _require(
            required_facets.issubset(_slot_facets(item, slot_id)),
            "product_bridge_evidence_support_slot_invalid",
        )
        material = materials.get(str(item.get("source_material_ref") or ""))
        terms = _strings(
            support.get("required_source_text_terms"),
            "product_bridge_support_terms_invalid",
        )
        source_text = str((material or {}).get("source_text") or "")
        _require(
            material is not None
            and material.get("source_text_digest") == item.get("source_content_digest")
            and _as_date(material.get("publication_date"), "product_bridge_date_invalid")
            <= _as_date(research_as_of, "product_bridge_as_of_invalid")
            and all(term in source_text for term in terms),
            "product_bridge_evidence_support_source_invalid",
        )
        support_catalog[support_id] = {
            "support_id": support_id,
            "evidence_item_digest": digest,
            "target_id": item.get("target_id"),
            "source_record_id": item.get("source_record_id"),
            "source_material_ref": item.get("source_material_ref"),
            "source_url": material.get("source_url"),
            "source_tier": material.get("source_tier"),
            "publication_date": material.get("publication_date"),
            "required_slot_id": slot_id,
            "required_facet_ids": sorted(required_facets),
            "numeric_fact_authority": False,
            "causal_attribution_authorized": False,
        }

    source_observations: dict[str, dict[str, Any]] = {}
    for observation in _rows(
        payload.get("source_numeric_observations"),
        "product_bridge_source_observations_invalid",
    ):
        observation_id = str(observation.get("observation_id") or "")
        support_id = str(observation.get("support_id") or "")
        support = support_catalog.get(support_id)
        _require(
            observation_id
            and observation_id not in source_observations
            and support is not None,
            "product_bridge_source_observation_binding_invalid",
        )
        material = materials[str(support["source_material_ref"])]
        surface = str(observation.get("source_text_term") or "")
        value_surface = str(observation.get("value_surface") or "")
        value = _decimal(
            observation.get("value_decimal"),
            "product_bridge_source_observation_value_invalid",
        )
        surface_value = _decimal(
            value_surface.replace(",", "").replace("$", "").strip(),
            "product_bridge_source_observation_surface_value_invalid",
        )
        _require(
            surface
            and surface in str(material.get("source_text") or "")
            and value_surface in surface
            and value == surface_value
            and observation.get("numeric_fact_authority") is False
            and observation.get("target_company_aggregate_authority") is False,
            "product_bridge_source_observation_surface_invalid",
        )
        source_observations[observation_id] = {
            "observation_id": observation_id,
            "support_id": support_id,
            "metric_id": str(observation.get("metric_id") or ""),
            "value_decimal": _decimal_string(value),
            "unit": str(observation.get("unit") or ""),
            "period_label": str(observation.get("period_label") or ""),
            "observation_scope": str(observation.get("observation_scope") or ""),
            "authority_mode": "source_visible_exact_observation_not_numeric_fact",
            "numeric_fact_authority": False,
            "target_company_aggregate_authority": False,
        }

    qualitative_observations = []
    for observation in _rows(
        payload.get("qualitative_observations"),
        "product_bridge_qualitative_observations_invalid",
    ):
        support_id = str(observation.get("support_id") or "")
        support = support_catalog.get(support_id)
        surface = str(observation.get("source_text_term") or "")
        _require(
            support is not None
            and surface
            and surface in str(
                materials[str(support["source_material_ref"])].get("source_text")
                or ""
            ),
            "product_bridge_qualitative_observation_surface_invalid",
        )
        qualitative_observations.append(
            {
                "observation_id": str(observation.get("observation_id") or ""),
                "support_id": support_id,
                "observation_role": str(observation.get("observation_role") or ""),
                "source_text_term": surface,
                "numeric_fact_authority": False,
                "causal_attribution_authorized": False,
            }
        )
    _require(
        len(qualitative_observations)
        == len({row["observation_id"] for row in qualitative_observations})
        and all(row["observation_id"] for row in qualitative_observations),
        "product_bridge_qualitative_observation_identity_invalid",
    )

    required_observation_ids = set(
        _strings(
            payload.get("required_source_observation_ids"),
            "product_bridge_required_observations_invalid",
        )
    )
    _require(
        required_observation_ids == set(source_observations),
        "product_bridge_source_observation_coverage_invalid",
    )

    quantitative = _mapping(
        quantitative_projection.get("quantitative_authority"),
        "product_bridge_quantitative_authority_missing",
    )
    quantitative_rows = [
        *[
            _mapping(row, "product_bridge_reported_fact_invalid")
            for row in quantitative.get("reported_facts") or ()
        ],
        *[
            _mapping(row, "product_bridge_derived_metric_invalid")
            for row in quantitative.get("deterministic_derived_metrics") or ()
        ],
    ]
    company_context = [
        _select_quantitative_row(rows=quantitative_rows, selector=selector)
        for selector in _rows(
            payload.get("company_context_selectors"),
            "product_bridge_company_selectors_invalid",
        )
    ]
    _require(
        len(company_context)
        == len({row["selector_id"] for row in company_context})
        and all(row["selector_id"] for row in company_context),
        "product_bridge_company_selector_identity_invalid",
    )

    estimates = {
        str(row.get("estimate_key") or ""): row
        for row in quantitative_projection.get("research_estimate_bindings") or ()
        if isinstance(row, Mapping)
    }
    required_estimate_keys = _strings(
        payload.get("required_industry_estimate_keys"),
        "product_bridge_required_estimates_invalid",
    )
    _require(
        set(required_estimate_keys).issubset(estimates),
        "product_bridge_required_estimate_missing",
    )

    def obs(observation_id: str) -> Decimal:
        _require(
            observation_id in source_observations,
            "product_bridge_required_observation_missing",
        )
        return Decimal(source_observations[observation_id]["value_decimal"])

    ai_current = obs("dell_ai_server_revenue_q1_fy27")
    ai_prior = obs("dell_ai_server_revenue_q1_fy26")
    isg_current = obs("dell_isg_revenue_q1_fy27")
    isg_prior = obs("dell_isg_revenue_q1_fy26")
    company_current = obs("dell_company_revenue_q1_fy27")
    company_prior = obs("dell_company_revenue_q1_fy26")
    isg_oi_current = obs("dell_isg_operating_income_q1_fy27")
    isg_oi_prior = obs("dell_isg_operating_income_q1_fy26")
    derived_values = [
        {
            "derived_metric_id": "dell_ai_server_revenue_yoy_growth",
            "value_decimal": _decimal_string((ai_current - ai_prior) / ai_prior),
            "unit": "ratio",
            "formula": "(current_ai_server_revenue - prior_ai_server_revenue) / prior_ai_server_revenue",
            "input_observation_ids": [
                "dell_ai_server_revenue_q1_fy27",
                "dell_ai_server_revenue_q1_fy26",
            ],
        },
        {
            "derived_metric_id": "dell_ai_server_share_of_isg_revenue_q1_fy27",
            "value_decimal": _decimal_string(ai_current / isg_current),
            "unit": "ratio",
            "formula": "ai_server_revenue / isg_revenue",
            "input_observation_ids": [
                "dell_ai_server_revenue_q1_fy27",
                "dell_isg_revenue_q1_fy27",
            ],
        },
        {
            "derived_metric_id": "dell_ai_server_share_of_isg_revenue_q1_fy26",
            "value_decimal": _decimal_string(ai_prior / isg_prior),
            "unit": "ratio",
            "formula": "ai_server_revenue / isg_revenue",
            "input_observation_ids": [
                "dell_ai_server_revenue_q1_fy26",
                "dell_isg_revenue_q1_fy26",
            ],
        },
        {
            "derived_metric_id": "dell_ai_server_share_of_company_revenue_q1_fy27",
            "value_decimal": _decimal_string(ai_current / company_current),
            "unit": "ratio",
            "formula": "ai_server_revenue / company_revenue",
            "input_observation_ids": [
                "dell_ai_server_revenue_q1_fy27",
                "dell_company_revenue_q1_fy27",
            ],
        },
        {
            "derived_metric_id": "dell_ai_server_share_of_company_revenue_q1_fy26",
            "value_decimal": _decimal_string(ai_prior / company_prior),
            "unit": "ratio",
            "formula": "ai_server_revenue / company_revenue",
            "input_observation_ids": [
                "dell_ai_server_revenue_q1_fy26",
                "dell_company_revenue_q1_fy26",
            ],
        },
        {
            "derived_metric_id": "dell_isg_operating_margin_recalculated_q1_fy27",
            "value_decimal": _decimal_string(isg_oi_current / isg_current * 100),
            "unit": "percent",
            "formula": "isg_operating_income / isg_revenue * 100",
            "input_observation_ids": [
                "dell_isg_operating_income_q1_fy27",
                "dell_isg_revenue_q1_fy27",
            ],
        },
        {
            "derived_metric_id": "dell_isg_operating_margin_recalculated_q1_fy26",
            "value_decimal": _decimal_string(isg_oi_prior / isg_prior * 100),
            "unit": "percent",
            "formula": "isg_operating_income / isg_revenue * 100",
            "input_observation_ids": [
                "dell_isg_operating_income_q1_fy26",
                "dell_isg_revenue_q1_fy26",
            ],
        },
    ]
    for row in derived_values:
        row.update(
            {
                "authority_mode": "deterministic_source_surface_derivation",
                "numeric_fact_authority": False,
                "product_profit_attribution_authorized": False,
            }
        )
        row["derived_metric_digest"] = canonical_digest(row)

    residual_gaps = {
        str(row.get("gap_id") or ""): dict(row)
        for row in evidence_pack.get("residual_gaps") or ()
        if isinstance(row, Mapping)
    }
    required_pack_gap_ids = set(
        _strings(
            payload.get("required_pack_gap_ids"),
            "product_bridge_required_pack_gaps_invalid",
        )
    )
    _require(
        required_pack_gap_ids.issubset(residual_gaps),
        "product_bridge_required_pack_gap_missing",
    )
    bridge_gap = _mapping(
        payload.get("product_profit_bridge_gap"),
        "product_bridge_profit_gap_missing",
    )
    _require(
        bridge_gap.get("gap_id") not in residual_gaps
        and bridge_gap.get("owning_stage") == "S2"
        and bridge_gap.get("closed") is False
        and bridge_gap.get("public_information_gap_authority") is False,
        "product_bridge_profit_gap_invalid",
    )
    bridge_gap_receipts = [
        {
            "gap_id": gap_id,
            "owning_stage": "S1_S2_boundary"
            if gap_id in {"dell-gap-pricing-asp", "dell-gap-pricing-units"}
            else "S2",
            "gap_code": residual_gaps[gap_id].get("gap_code"),
            "source": "evidence_pack_residual_gap",
            "closed": False,
            "public_information_gap_authority": False,
        }
        for gap_id in sorted(required_pack_gap_ids)
    ]
    bridge_gap_receipts.append(bridge_gap)

    pvm_bridge = {
        "state": "not_calculable_typed_input_gaps",
        "reported_product_revenue_current_available": True,
        "reported_product_revenue_prior_available": True,
        "target_company_asp_available": False,
        "target_company_units_available": False,
        "comparable_configuration_weights_available": False,
        "price_effect_value": None,
        "volume_effect_value": None,
        "mix_effect_value": None,
        "unexplained_residual_value": None,
        "formula_contract": {
            "revenue_identity": "sum_i(price_i * volume_i)",
            "price_effect": "sum_i((price_current_i - price_prior_i) * volume_prior_i)",
            "volume_effect": "sum_i((volume_current_i - volume_prior_i) * price_prior_i)",
            "mix_effect": "revenue_change - price_effect - volume_effect",
        },
        "bounded_price_observation_ids": [
            "dell_public_recommended_bundle_price_sample",
            "dell_public_procurement_contract_value_sample",
        ],
        "bounded_unit_observation_ids": ["dell_public_procurement_system_count_sample"],
        "industry_estimate_keys": required_estimate_keys,
        "required_open_gap_ids": sorted(
            {
                "dell-gap-pricing-asp",
                "dell-gap-pricing-units",
                "dell-gap-price-volume-mix-bridge",
            }
        ),
        "claim_boundary_zh": (
            "已披露产品收入可建立收入边界；公开报价、采购数量和行业增速仅是异质样本或外部情景，"
            "不能代替 Dell 公司级 ASP、units 或配置权重，因此不得生成伪精确 PVM 分解。"
        ),
    }
    profit_bridge = {
        "state": "not_calculable_product_profit_attribution_gap",
        "reported_product_revenue_available": True,
        "segment_revenue_and_operating_income_available": True,
        "management_product_profitability_target_available": True,
        "realized_product_gross_profit_available": False,
        "realized_product_operating_profit_available": False,
        "product_cost_and_opex_allocation_available": False,
        "implied_product_operating_profit_value": None,
        "formula_contract": {
            "product_gross_profit": "product_revenue - product_cost_of_revenue",
            "product_operating_profit": "product_gross_profit - attributable_product_operating_expense",
            "company_profit_contribution": "product_operating_profit / company_operating_income",
        },
        "required_open_gap_ids": [str(bridge_gap["gap_id"])],
        "claim_boundary_zh": (
            "AI server 收入、ISG 收入和 ISG 经营利润可同表观察；管理层的中个位数目标是定性目标带，"
            "不是已审计产品利润率。没有产品成本和费用分配时，禁止把 ISG 经营利润归因给 AI server，"
            "也禁止用目标带乘收入生成产品利润。"
        ),
    }

    checks = {
        "all_program_evidence_supports_bound": len(support_catalog)
        == len(payload.get("evidence_supports") or ()),
        "all_source_numeric_observations_surface_bound": set(source_observations)
        == required_observation_ids,
        "company_context_quantitative_rows_bound": bool(company_context),
        "industry_scenarios_bound_without_target_company_authority": all(
            estimates[key].get("target_company_direct_metric") is False
            for key in required_estimate_keys
        ),
        "pvm_values_remain_null_while_inputs_missing": all(
            pvm_bridge[key] is None
            for key in (
                "price_effect_value",
                "volume_effect_value",
                "mix_effect_value",
                "unexplained_residual_value",
            )
        ),
        "product_profit_value_remains_null_while_attribution_missing": profit_bridge[
            "implied_product_operating_profit_value"
        ]
        is None,
        "bounded_bundle_not_divided_into_asp": not any(
            "per_system" in row["derived_metric_id"]
            or "asp" in row["derived_metric_id"]
            for row in derived_values
        ),
        "all_bridge_gaps_open_without_public_gap_authority": all(
            row.get("closed") is False
            and row.get("public_information_gap_authority") is False
            for row in bridge_gap_receipts
        ),
    }
    _require(all(checks.values()), "product_bridge_readiness_checks_failed")
    unsigned = {
        "schema_version": PRODUCT_VALUE_BRIDGE_RESULT_SCHEMA,
        "status": "bounded_product_value_bridge_with_typed_gaps",
        "case_key": case_key,
        "research_as_of": research_as_of,
        "recorded_at": str(recorded_at),
        "evidence_pack_payload_digest": pack_digest,
        "task_quantitative_projection_digest": quantitative_projection.get(
            "task_quantitative_projection_digest"
        ),
        "evidence_support_catalog": list(support_catalog.values()),
        "source_numeric_observations": list(source_observations.values()),
        "qualitative_observations": qualitative_observations,
        "deterministic_source_surface_derivations": derived_values,
        "company_context": company_context,
        "pvm_bridge": pvm_bridge,
        "product_profit_bridge": profit_bridge,
        "bridge_gap_receipts": bridge_gap_receipts,
        "bridge_readiness": {
            "safe_for_bounded_dynamic_research": True,
            "reported_product_revenue_bridge_available": True,
            "target_company_pvm_calculable": False,
            "product_profit_bridge_calculable": False,
            "s2_stage_qualified": False,
            "checks": checks,
        },
        "authority": {
            "source_visible_values_are_not_automatically_numeric_facts": True,
            "deterministic_ratios_are_not_product_profit_attribution": True,
            "management_target_is_not_realized_margin": True,
            "bounded_quotes_are_not_company_asp": True,
            "procurement_units_are_not_company_shipments": True,
            "candidate_or_model_numbers_created": False,
            "public_information_gap_claimed": False,
            "product_publication": False,
        },
        "known_boundary": str(payload.get("known_boundary") or ""),
    }
    return {**unsigned, "product_value_bridge_digest": canonical_digest(unsigned)}


__all__ = [
    "PRODUCT_VALUE_BRIDGE_PROGRAM_SCHEMA",
    "PRODUCT_VALUE_BRIDGE_RESULT_SCHEMA",
    "ProductValueBridgeError",
    "compile_product_value_bridge",
]
