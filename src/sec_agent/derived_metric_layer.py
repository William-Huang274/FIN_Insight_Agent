from __future__ import annotations

import hashlib
from collections.abc import Iterable
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping

from sec_agent.gate_registry import build_gate_registry_eval_matrix
from sec_agent.reconciliation_ledger import build_reconciliation_ledger


DERIVED_METRIC_LAYER_SCHEMA_VERSION = "sec_agent_derived_metric_layer_v0.1"
DERIVED_METRIC_CALCULATION_VERSION = "deterministic_reconciled_fact_formula_v0.1"


FactMap = dict[str, dict[str, Any]]


def build_derived_metric_layer(state: Mapping[str, Any]) -> dict[str, Any]:
    reconciliation = (
        state.get("reconciliation_ledger")
        if isinstance(state.get("reconciliation_ledger"), Mapping)
        else build_reconciliation_ledger(state)
    )
    gate_matrix = (
        state.get("gate_registry_eval_matrix")
        if isinstance(state.get("gate_registry_eval_matrix"), Mapping)
        else build_gate_registry_eval_matrix({**state, "reconciliation_ledger": reconciliation})
    )
    gate_index = _gate_index(gate_matrix)
    facts = _reconciled_facts(reconciliation, gate_index=gate_index)
    derived_metrics: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    facts_by_context = _facts_by_context(facts)

    for context_key, metrics in sorted(facts_by_context.items()):
        derived, skips = _derive_same_period_metrics(context_key, metrics)
        derived_metrics.extend(derived)
        skipped.extend(skips)

    derived, skips = _derive_period_change_metrics(facts)
    derived_metrics.extend(derived)
    skipped.extend(skips)

    derived_metrics = _dedupe_by_id(derived_metrics, id_field="derived_metric_id")
    skipped = _dedupe_by_id(skipped, id_field="skipped_derivation_id")
    payload = {
        "schema_version": DERIVED_METRIC_LAYER_SCHEMA_VERSION,
        "policy": "derive_only_from_reconciled_exact_facts_with_gate_status_v0_1",
        "run_id": str(state.get("run_id") or ""),
        "calculation_version": DERIVED_METRIC_CALCULATION_VERSION,
        "input_fact_count": len(facts),
        "derived_metric_count": len(derived_metrics),
        "skipped_derivation_count": len(skipped),
        "input_facts": facts,
        "derived_metrics": derived_metrics,
        "skipped_derivations": skipped,
        "summary": {
            "by_derived_metric_family": dict(
                sorted(Counter(row.get("derived_metric_family") or "unknown" for row in derived_metrics).items())
            ),
            "by_gate_status": dict(sorted(Counter(row.get("gate_status") or "unknown" for row in derived_metrics).items())),
            "by_skip_reason": dict(sorted(Counter(row.get("skip_reason") or "unknown" for row in skipped).items())),
            "blocked_derivation_count": len([row for row in skipped if row.get("skip_reason") == "input_gate_blocked"]),
            "formula_family_count": len({row.get("formula_id") for row in derived_metrics if row.get("formula_id")}),
        },
    }
    payload["validation"] = validate_derived_metric_layer(payload)
    return _jsonable(payload)


def validate_derived_metric_layer(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    facts = {
        str(row.get("fact_id") or ""): row
        for row in payload.get("input_facts") or []
        if isinstance(row, Mapping) and str(row.get("fact_id") or "").strip()
    }
    seen_metric_ids: set[str] = set()
    for index, row in enumerate([item for item in payload.get("derived_metrics") or [] if isinstance(item, Mapping)]):
        derived_id = str(row.get("derived_metric_id") or "").strip()
        if not derived_id:
            errors.append({"type": "derived_metric_id_required", "index": index})
        elif derived_id in seen_metric_ids:
            errors.append({"type": "duplicate_derived_metric_id", "derived_metric_id": derived_id})
        seen_metric_ids.add(derived_id)
        for field in ("formula", "calculation_version", "value", "unit", "gate_status", "explainability_trace"):
            if field == "explainability_trace":
                if not row.get(field):
                    errors.append({"type": "derived_metric_required_field_missing", "derived_metric_id": derived_id, "field": field})
            elif not str(row.get(field) or "").strip():
                errors.append({"type": "derived_metric_required_field_missing", "derived_metric_id": derived_id, "field": field})
        if row.get("gate_status") not in {"pass", "warn"}:
            errors.append(
                {
                    "type": "derived_metric_with_nonpassing_gate_status",
                    "derived_metric_id": derived_id,
                    "gate_status": row.get("gate_status"),
                }
            )
        for fact_id in _string_list(row.get("input_fact_ids")):
            if fact_id not in facts and not fact_id.startswith("derived_metric:"):
                errors.append({"type": "derived_metric_unknown_input_fact", "derived_metric_id": derived_id, "fact_id": fact_id})
    for index, row in enumerate([item for item in payload.get("skipped_derivations") or [] if isinstance(item, Mapping)]):
        if not str(row.get("skipped_derivation_id") or "").strip():
            errors.append({"type": "skipped_derivation_id_required", "index": index})
        if not str(row.get("skip_reason") or "").strip():
            errors.append({"type": "skipped_derivation_reason_required", "index": index})
    if not payload.get("derived_metrics"):
        warnings.append({"type": "no_derived_metrics_generated"})
    return {
        "schema_version": "sec_agent_derived_metric_layer_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def _reconciled_facts(reconciliation: Mapping[str, Any], *, gate_index: Mapping[str, list[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    candidates = {
        str(row.get("candidate_id") or ""): row
        for row in reconciliation.get("candidates") or []
        if isinstance(row, Mapping) and str(row.get("candidate_id") or "").strip()
    }
    facts: list[dict[str, Any]] = []
    for group in reconciliation.get("reconciliation_groups") or []:
        if not isinstance(group, Mapping):
            continue
        if not str(group.get("resolution_status") or "").startswith("resolved"):
            continue
        preferred = group.get("preferred_value") if isinstance(group.get("preferred_value"), Mapping) else {}
        candidate_id = str(preferred.get("candidate_id") or "")
        candidate = candidates.get(candidate_id, {})
        value = _decimal_value(preferred.get("numeric_value") or preferred.get("value"))
        if value is None:
            continue
        gate_status = _input_gate_status(group=group, preferred=preferred, candidate=candidate, gate_index=gate_index)
        fact = {
            "fact_id": candidate_id or str(group.get("group_id") or ""),
            "reconciliation_group_id": str(group.get("group_id") or ""),
            "ticker": str(group.get("ticker") or candidate.get("ticker") or "").upper(),
            "canonical_metric_id": str(group.get("canonical_metric_id") or candidate.get("canonical_metric_id") or ""),
            "product_or_segment": str(group.get("product_or_segment") or candidate.get("product_or_segment") or ""),
            "product_key": str((group.get("group_key") or {}).get("product_key") or candidate.get("product_key") or "__company_total__")
            if isinstance(group.get("group_key"), Mapping)
            else str(candidate.get("product_key") or "__company_total__"),
            "period_key": str(group.get("period_key") or candidate.get("period_key") or ""),
            "fiscal_year": str(candidate.get("fiscal_year") or ""),
            "fiscal_period": str(candidate.get("fiscal_period") or ""),
            "fiscal_period_end": str(candidate.get("fiscal_period_end") or ""),
            "value": str(preferred.get("value") or ""),
            "numeric_value": _decimal_text(value),
            "unit": str(preferred.get("unit") or candidate.get("unit") or ""),
            "unit_family": str(preferred.get("unit_family") or candidate.get("unit_family") or ""),
            "source_id": str(preferred.get("source_id") or candidate.get("source_id") or ""),
            "evidence_ref": str(preferred.get("evidence_ref") or candidate.get("evidence_ref") or ""),
            "source_family": str(preferred.get("source_family") or candidate.get("source_family") or ""),
            "resolution_rule": str(preferred.get("resolution_rule") or ""),
            "resolution_confidence": str(preferred.get("confidence") or ""),
            "gate_status_detail": gate_status,
        }
        facts.append(fact)
    return sorted(facts, key=lambda row: (row["ticker"], row["product_key"], row["period_key"], row["canonical_metric_id"]))


def _derive_same_period_metrics(context_key: tuple[str, str, str], metrics: FactMap) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ticker, product_key, period_key = context_key
    derived: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    revenue = _first_metric(metrics, ["product_kpi:product_revenue", "financial_metric:revenue"])
    gross_profit = _first_metric(metrics, ["financial_metric:gross_profit"])
    operating_income = _first_metric(metrics, ["financial_metric:operating_income"])
    operating_cash_flow = _first_metric(metrics, ["financial_metric:operating_cash_flow"])
    capex = _first_metric(metrics, ["financial_metric:capex"])
    direct_fcf = _first_metric(metrics, ["financial_metric:fcf"])
    debt = _first_metric(metrics, ["financial_metric:debt"])
    cash = _first_metric(metrics, ["financial_metric:cash"])
    inventory = _first_metric(metrics, ["financial_metric:inventory"])
    cost_of_revenue = _first_metric(metrics, ["financial_metric:cost_of_revenue"])
    gmv = _first_metric(metrics, ["product_kpi:gmv"])
    subscribers = _first_metric(metrics, ["product_kpi:subscribers"])
    deliveries = _first_metric(metrics, ["product_kpi:deliveries"])
    shipments = _first_metric(metrics, ["product_kpi:shipments"])

    _append_formula(
        derived,
        skipped,
        context=(ticker, product_key, period_key),
        family="gross_margin",
        formula_id="gross_margin",
        formula="gross_profit / revenue * 100",
        inputs={"gross_profit": gross_profit, "revenue": revenue},
        unit="percent",
        unit_family="percent",
        calculator=lambda values: _safe_ratio(values["gross_profit"], values["revenue"], scale=Decimal("100")),
    )
    _append_formula(
        derived,
        skipped,
        context=(ticker, product_key, period_key),
        family="operating_margin",
        formula_id="operating_margin",
        formula="operating_income / revenue * 100",
        inputs={"operating_income": operating_income, "revenue": revenue},
        unit="percent",
        unit_family="percent",
        calculator=lambda values: _safe_ratio(values["operating_income"], values["revenue"], scale=Decimal("100")),
    )
    _append_formula(
        derived,
        skipped,
        context=(ticker, product_key, period_key),
        family="free_cash_flow",
        formula_id="free_cash_flow",
        formula="operating_cash_flow - abs(capex)",
        inputs={"operating_cash_flow": operating_cash_flow, "capex": capex},
        unit=_unit_from(operating_cash_flow, capex, default="currency"),
        unit_family="currency",
        calculator=lambda values: values["operating_cash_flow"] - abs(values["capex"]),
    )
    fcf_input = direct_fcf
    fcf_formula = "fcf / revenue * 100"
    fcf_inputs = {"fcf": direct_fcf, "revenue": revenue}
    if not fcf_input and operating_cash_flow and capex:
        fcf_formula = "(operating_cash_flow - abs(capex)) / revenue * 100"
        fcf_inputs = {"operating_cash_flow": operating_cash_flow, "capex": capex, "revenue": revenue}
    _append_formula(
        derived,
        skipped,
        context=(ticker, product_key, period_key),
        family="free_cash_flow_margin",
        formula_id="free_cash_flow_margin",
        formula=fcf_formula,
        inputs=fcf_inputs,
        unit="percent",
        unit_family="percent",
        calculator=lambda values: _safe_ratio(
            values["fcf"] if "fcf" in values else values["operating_cash_flow"] - abs(values["capex"]),
            values["revenue"],
            scale=Decimal("100"),
        ),
    )
    _append_formula(
        derived,
        skipped,
        context=(ticker, product_key, period_key),
        family="net_debt",
        formula_id="net_debt",
        formula="debt - cash",
        inputs={"debt": debt, "cash": cash},
        unit=_unit_from(debt, cash, default="currency"),
        unit_family="currency",
        calculator=lambda values: values["debt"] - values["cash"],
    )
    _append_formula(
        derived,
        skipped,
        context=(ticker, product_key, period_key),
        family="inventory_days",
        formula_id="inventory_days",
        formula="inventory / abs(cost_of_revenue) * period_days",
        inputs={"inventory": inventory, "cost_of_revenue": cost_of_revenue},
        unit="days",
        unit_family="days",
        calculator=lambda values: _safe_ratio(
            values["inventory"], abs(values["cost_of_revenue"]), scale=Decimal(str(_period_days(inventory or cost_of_revenue)))
        ),
    )
    _append_formula(
        derived,
        skipped,
        context=(ticker, product_key, period_key),
        family="take_rate",
        formula_id="take_rate",
        formula="revenue / GMV * 100",
        inputs={"revenue": revenue, "gmv": gmv},
        unit="percent",
        unit_family="percent",
        calculator=lambda values: _safe_ratio(values["revenue"], values["gmv"], scale=Decimal("100")),
    )
    _append_formula(
        derived,
        skipped,
        context=(ticker, product_key, period_key),
        family="arpu",
        formula_id="arpu",
        formula="revenue / subscribers",
        inputs={"revenue": revenue, "subscribers": subscribers},
        unit="currency_per_user",
        unit_family="currency_per_user",
        calculator=lambda values: _safe_ratio(values["revenue"], values["subscribers"]),
    )
    denominator = deliveries or shipments
    denominator_name = "deliveries" if deliveries else "shipments"
    _append_formula(
        derived,
        skipped,
        context=(ticker, product_key, period_key),
        family="asp",
        formula_id=f"asp_from_{denominator_name}",
        formula=f"revenue / {denominator_name}",
        inputs={"revenue": revenue, denominator_name: denominator},
        unit="currency_per_unit",
        unit_family="currency_per_unit",
        calculator=lambda values, name=denominator_name: _safe_ratio(values["revenue"], values[name]),
    )
    return derived, skipped


def _derive_period_change_metrics(facts: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    derived: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, str, str, str], dict[tuple[int, str], dict[str, Any]]] = defaultdict(dict)
    for fact in facts:
        fiscal_year = _int_text(fact.get("fiscal_year"))
        fiscal_period = str(fact.get("fiscal_period") or "").upper()
        if fiscal_year is None or fiscal_period not in {"FY", "Q1", "Q2", "Q3", "Q4"}:
            continue
        key = (
            str(fact.get("ticker") or ""),
            str(fact.get("product_key") or "__company_total__"),
            str(fact.get("canonical_metric_id") or ""),
            str(fact.get("unit_family") or ""),
            str(fact.get("unit") or ""),
        )
        by_key[key][(fiscal_year, fiscal_period)] = fact
    for (_, _, _, _, _), period_facts in sorted(by_key.items()):
        for (year, period), current in sorted(period_facts.items()):
            prior_yoy = period_facts.get((year - 1, period))
            if prior_yoy:
                _append_period_change(derived, skipped, family="yoy_growth", current=current, prior=prior_yoy, formula="(current - prior_year) / abs(prior_year) * 100")
            prior_qoq_key = _prior_quarter(year, period)
            prior_qoq = period_facts.get(prior_qoq_key) if prior_qoq_key else None
            if prior_qoq:
                _append_period_change(derived, skipped, family="qoq_growth", current=current, prior=prior_qoq, formula="(current - prior_quarter) / abs(prior_quarter) * 100")
    return derived, skipped


def _append_formula(
    derived: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    *,
    context: tuple[str, str, str],
    family: str,
    formula_id: str,
    formula: str,
    inputs: Mapping[str, Mapping[str, Any] | None],
    unit: str,
    unit_family: str,
    calculator: Callable[[dict[str, Decimal]], Decimal | None],
) -> None:
    present = {name: fact for name, fact in inputs.items() if isinstance(fact, Mapping) and fact}
    if not present:
        return
    missing = sorted(name for name, fact in inputs.items() if not isinstance(fact, Mapping) or not fact)
    if missing:
        skipped.append(_skip(context, family=family, formula_id=formula_id, skip_reason="missing_inputs", inputs=present, missing_inputs=missing))
        return
    input_facts = [dict(fact) for fact in present.values()]
    gate = _combined_gate_status(input_facts)
    if gate["status"] == "blocked":
        skipped.append(_skip(context, family=family, formula_id=formula_id, skip_reason="input_gate_blocked", inputs=present, gate_status=gate))
        return
    values = {name: _decimal_value(fact.get("numeric_value")) for name, fact in present.items()}
    if any(value is None for value in values.values()):
        skipped.append(_skip(context, family=family, formula_id=formula_id, skip_reason="non_numeric_input", inputs=present))
        return
    calculated = calculator({name: value for name, value in values.items() if value is not None})
    if calculated is None:
        skipped.append(_skip(context, family=family, formula_id=formula_id, skip_reason="invalid_formula_domain", inputs=present))
        return
    ticker, product_key, period_key = context
    sample_fact = input_facts[0]
    derived.append(
        _derived_row(
            family=family,
            formula_id=formula_id,
            formula=formula,
            ticker=ticker,
            product_key=product_key,
            product_or_segment=_display_product(input_facts),
            period_key=period_key,
            fiscal_year=str(sample_fact.get("fiscal_year") or ""),
            fiscal_period=str(sample_fact.get("fiscal_period") or ""),
            value=calculated,
            unit=unit,
            unit_family=unit_family,
            input_facts=input_facts,
            gate_status=gate,
        )
    )


def _append_period_change(
    derived: list[dict[str, Any]],
    skipped: list[dict[str, Any]],
    *,
    family: str,
    current: Mapping[str, Any],
    prior: Mapping[str, Any],
    formula: str,
) -> None:
    gate = _combined_gate_status([current, prior])
    context = (
        str(current.get("ticker") or ""),
        str(current.get("product_key") or "__company_total__"),
        str(current.get("period_key") or ""),
    )
    formula_id = f"{family}:{current.get('canonical_metric_id')}"
    if gate["status"] == "blocked":
        skipped.append(
            _skip(
                context,
                family=family,
                formula_id=formula_id,
                skip_reason="input_gate_blocked",
                inputs={"current": current, "prior": prior},
                gate_status=gate,
            )
        )
        return
    current_value = _decimal_value(current.get("numeric_value"))
    prior_value = _decimal_value(prior.get("numeric_value"))
    if current_value is None or prior_value is None:
        skipped.append(_skip(context, family=family, formula_id=formula_id, skip_reason="non_numeric_input", inputs={"current": current, "prior": prior}))
        return
    rate_metric = _period_change_is_rate_metric(current)
    if prior_value == 0 and not rate_metric:
        skipped.append(_skip(context, family=family, formula_id=formula_id, skip_reason="zero_prior_period", inputs={"current": current, "prior": prior}))
        return
    if rate_metric:
        output_family = "yoy_change_pp" if family == "yoy_growth" else "qoq_change_pp" if family == "qoq_growth" else f"{family}_pp"
        output_formula = "current_rate - prior_rate"
        output_formula_id = f"{output_family}:{current.get('canonical_metric_id')}"
        value = current_value - prior_value
        unit = "percentage_points"
        unit_family = "percentage_points"
    else:
        output_family = family
        output_formula = formula
        output_formula_id = formula_id
        value = (current_value - prior_value) / abs(prior_value) * Decimal("100")
        unit = "percent"
        unit_family = "percent"
    derived.append(
        _derived_row(
            family=output_family,
            formula_id=output_formula_id,
            formula=output_formula,
            ticker=str(current.get("ticker") or ""),
            product_key=str(current.get("product_key") or "__company_total__"),
            product_or_segment=str(current.get("product_or_segment") or ""),
            period_key=str(current.get("period_key") or ""),
            fiscal_year=str(current.get("fiscal_year") or ""),
            fiscal_period=str(current.get("fiscal_period") or ""),
            value=value,
            unit=unit,
            unit_family=unit_family,
            input_facts=[dict(current), dict(prior)],
            gate_status=gate,
        )
    )


def _period_change_is_rate_metric(fact: Mapping[str, Any]) -> bool:
    text = " ".join(
        str(fact.get(key) or "").lower()
        for key in (
            "canonical_metric_id",
            "metric_family",
            "metric_name",
            "metric",
            "unit",
            "unit_family",
        )
    )
    if "percentage_points" in text:
        return True
    rate_terms = (
        "margin",
        "rate",
        "ratio",
        "yield",
        "percentage_rate",
        "net_interest_margin",
        "medical_loss_ratio",
    )
    return any(term in text for term in rate_terms)


def _derived_row(
    *,
    family: str,
    formula_id: str,
    formula: str,
    ticker: str,
    product_key: str,
    product_or_segment: str,
    period_key: str,
    fiscal_year: str,
    fiscal_period: str,
    value: Decimal,
    unit: str,
    unit_family: str,
    input_facts: list[Mapping[str, Any]],
    gate_status: Mapping[str, Any],
) -> dict[str, Any]:
    input_fact_ids = [str(fact.get("fact_id") or "") for fact in input_facts if str(fact.get("fact_id") or "")]
    derived_id = _stable_id("derived_metric", ticker, product_key, period_key, formula_id, ",".join(input_fact_ids))
    return {
        "derived_metric_id": derived_id,
        "derived_metric_family": family,
        "formula_id": formula_id,
        "formula": formula,
        "calculation_version": DERIVED_METRIC_CALCULATION_VERSION,
        "ticker": ticker,
        "product_or_segment": product_or_segment,
        "product_key": product_key,
        "period_key": period_key,
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "value": _decimal_text(value),
        "numeric_value": _decimal_text(value),
        "unit": unit,
        "unit_family": unit_family,
        "input_fact_ids": input_fact_ids,
        "input_reconciliation_group_ids": _unique_strings([fact.get("reconciliation_group_id") for fact in input_facts]),
        "input_evidence_refs": _unique_strings([fact.get("evidence_ref") for fact in input_facts]),
        "input_source_ids": _unique_strings([fact.get("source_id") for fact in input_facts]),
        "gate_status": str(gate_status.get("status") or "pass"),
        "gate_status_detail": dict(gate_status),
        "source_policy": "derived_from_reconciled_exact_facts_no_proxy",
        "claim_boundary": "derived metric is usable only with this formula and cited input facts",
        "explainability_trace": [
            {
                "step": "input_fact",
                "fact_id": str(fact.get("fact_id") or ""),
                "canonical_metric_id": str(fact.get("canonical_metric_id") or ""),
                "value": str(fact.get("numeric_value") or fact.get("value") or ""),
                "unit": str(fact.get("unit") or ""),
                "source_id": str(fact.get("source_id") or ""),
                "evidence_ref": str(fact.get("evidence_ref") or ""),
                "resolution_rule": str(fact.get("resolution_rule") or ""),
            }
            for fact in input_facts
        ]
        + [{"step": "calculation", "formula": formula, "value": _decimal_text(value), "unit": unit}],
    }


def _skip(
    context: tuple[str, str, str],
    *,
    family: str,
    formula_id: str,
    skip_reason: str,
    inputs: Mapping[str, Mapping[str, Any]],
    missing_inputs: list[str] | None = None,
    gate_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ticker, product_key, period_key = context
    input_facts = [fact for fact in inputs.values() if isinstance(fact, Mapping) and fact]
    return {
        "skipped_derivation_id": _stable_id(
            "skipped_derived_metric",
            ticker,
            product_key,
            period_key,
            formula_id,
            skip_reason,
            ",".join(str(fact.get("fact_id") or "") for fact in input_facts),
            ",".join(missing_inputs or []),
        ),
        "derived_metric_family": family,
        "formula_id": formula_id,
        "ticker": ticker,
        "product_key": product_key,
        "period_key": period_key,
        "skip_reason": skip_reason,
        "missing_inputs": list(missing_inputs or []),
        "input_fact_ids": [str(fact.get("fact_id") or "") for fact in input_facts if str(fact.get("fact_id") or "")],
        "blocking_gate_result_ids": list((gate_status or {}).get("blocking_gate_result_ids") or []),
        "repair_action": "add_missing_reconciled_input_fact_or_repair_blocking_gate",
    }


def _facts_by_context(facts: list[dict[str, Any]]) -> dict[tuple[str, str, str], FactMap]:
    grouped: dict[tuple[str, str, str], FactMap] = defaultdict(dict)
    for fact in facts:
        key = (str(fact.get("ticker") or ""), str(fact.get("product_key") or "__company_total__"), str(fact.get("period_key") or ""))
        grouped[key][str(fact.get("canonical_metric_id") or "")] = fact
    return grouped


def _input_gate_status(
    *,
    group: Mapping[str, Any],
    preferred: Mapping[str, Any],
    candidate: Mapping[str, Any],
    gate_index: Mapping[str, list[Mapping[str, Any]]],
) -> dict[str, Any]:
    target_ids = _unique_strings(
        [
            group.get("group_id"),
            preferred.get("candidate_id"),
            preferred.get("evidence_ref"),
            preferred.get("source_id"),
            candidate.get("candidate_id"),
            candidate.get("evidence_ref"),
            candidate.get("source_id"),
        ]
    )
    rows = [row for target_id in target_ids for row in gate_index.get(target_id, [])]
    blocking = [row for row in rows if row.get("status") == "fail" and row.get("blocks_claim_fact_layer")]
    warnings = [row for row in rows if row.get("status") == "warn"]
    status = "blocked" if blocking else ("warn" if warnings else "pass")
    return {
        "status": status,
        "target_object_ids": target_ids,
        "gate_result_ids": _unique_strings(row.get("gate_result_id") for row in rows),
        "blocking_gate_result_ids": _unique_strings(row.get("gate_result_id") for row in blocking),
        "warning_gate_result_ids": _unique_strings(row.get("gate_result_id") for row in warnings),
    }


def _combined_gate_status(input_facts: list[Mapping[str, Any]]) -> dict[str, Any]:
    blocking: list[str] = []
    warnings: list[str] = []
    gate_result_ids: list[str] = []
    for fact in input_facts:
        detail = fact.get("gate_status_detail") if isinstance(fact.get("gate_status_detail"), Mapping) else {}
        blocking.extend(_string_list(detail.get("blocking_gate_result_ids")))
        warnings.extend(_string_list(detail.get("warning_gate_result_ids")))
        gate_result_ids.extend(_string_list(detail.get("gate_result_ids")))
    status = "blocked" if blocking else ("warn" if warnings else "pass")
    return {
        "status": status,
        "gate_result_ids": _unique_strings(gate_result_ids),
        "blocking_gate_result_ids": _unique_strings(blocking),
        "warning_gate_result_ids": _unique_strings(warnings),
    }


def _gate_index(gate_matrix: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    index: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in gate_matrix.get("gate_history") or []:
        if not isinstance(row, Mapping):
            continue
        target_id = str(row.get("target_object_id") or "").strip()
        if target_id:
            index[target_id].append(row)
    return index


def _first_metric(metrics: FactMap, metric_ids: list[str]) -> dict[str, Any] | None:
    for metric_id in metric_ids:
        fact = metrics.get(metric_id)
        if fact:
            return fact
    return None


def _safe_ratio(numerator: Decimal, denominator: Decimal, *, scale: Decimal = Decimal("1")) -> Decimal | None:
    if denominator == 0:
        return None
    return numerator / denominator * scale


def _period_days(fact: Mapping[str, Any] | None) -> int:
    period = str((fact or {}).get("fiscal_period") or "").upper()
    if period in {"Q1", "Q2", "Q3", "Q4"}:
        return 90
    return 365


def _unit_from(*facts: Mapping[str, Any] | None, default: str) -> str:
    for fact in facts:
        if isinstance(fact, Mapping) and str(fact.get("unit") or "").strip():
            return str(fact.get("unit") or "").strip()
    return default


def _display_product(facts: list[Mapping[str, Any]]) -> str:
    for fact in facts:
        product = str(fact.get("product_or_segment") or "").strip()
        if product:
            return product
    return ""


def _prior_quarter(year: int, period: str) -> tuple[int, str] | None:
    if period == "Q1":
        return (year - 1, "Q4")
    if period == "Q2":
        return (year, "Q1")
    if period == "Q3":
        return (year, "Q2")
    if period == "Q4":
        return (year, "Q3")
    return None


def _int_text(value: Any) -> int | None:
    try:
        return int(str(value or "").strip())
    except ValueError:
        return None


def _decimal_value(value: Any) -> Decimal | None:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _decimal_text(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.0001"))
    return format(normalized.normalize(), "f")


def _dedupe_by_id(rows: list[dict[str, Any]], *, id_field: str) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = str(row.get(id_field) or "")
        if row_id and row_id not in by_id:
            by_id[row_id] = row
    return sorted(by_id.values(), key=lambda row: str(row.get(id_field) or ""))


def _stable_id(prefix: str, *values: Any) -> str:
    raw = "|".join(str(value or "") for value in values)
    return f"{prefix}:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:16]}"


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Mapping):
        return [str(value).strip()] if str(value).strip() else []
    if isinstance(value, Iterable):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()] if str(value).strip() else []


def _unique_strings(values: Any) -> list[str]:
    result: list[str] = []
    for value in _string_list(values):
        if value not in result:
            result.append(value)
    return result


def _jsonable(value: Any) -> Any:
    if isinstance(value, Decimal):
        return _decimal_text(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value
