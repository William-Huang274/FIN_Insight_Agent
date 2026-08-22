from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.session import canonical_digest


QUANTITATIVE_AUTHORITY_SCHEMA_VERSION = (
    "fin_ia_research_quantitative_authority_state_v1_0"
)
RESEARCH_ESTIMATE_SCHEMA_VERSION = "fin_ia_research_estimate_v1_0"
RESEARCH_SCENARIO_SCHEMA_VERSION = "fin_ia_research_scenario_v1_0"


class QuantitativeAuthorityError(ValueError):
    """Raised when facts, derivations, estimates and scenarios are conflated."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise QuantitativeAuthorityError(code)


def _decimal(value: object, code: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise QuantitativeAuthorityError(code) from exc
    _require(parsed.is_finite(), code)
    return parsed


def _decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    return "0" if text in {"-0", ""} else text


def _refs(value: Sequence[object], code: str, *, required: bool = True) -> list[str]:
    refs = [str(item).strip() for item in value]
    _require(
        (bool(refs) or not required)
        and all(refs)
        and len(refs) == len(set(refs)),
        code,
    )
    return refs


def _reported_fact(
    raw: Mapping[str, Any], *, allowed_tickers: set[str]
) -> dict[str, Any]:
    ticker = str(raw.get("ticker") or "").upper()
    numeric_ref = str(raw.get("numeric_fact_id") or "")
    metric_id = str(raw.get("metric_id") or "")
    unit = str(raw.get("unit") or "")
    fiscal_period = str(raw.get("fiscal_period") or "")
    period_role = str(raw.get("period_role") or "")
    fiscal_year = raw.get("fiscal_year")
    citation_urls = _refs(
        raw.get("citation_urls") or (),
        "quantitative_reported_fact_citation_missing",
    )
    source_digests = _refs(
        raw.get("source_digests") or (),
        "quantitative_reported_fact_source_digest_missing",
    )
    _require(
        raw.get("schema_version") == "fin_ia_numeric_fact_v1_0"
        and raw.get("numeric_fact_authority") is True
        and str(raw.get("authority_mode") or "").startswith("source_bound_")
        and ticker in allowed_tickers
        and numeric_ref.startswith("NUMFACT::")
        and metric_id
        and unit
        and fiscal_period
        and period_role
        and isinstance(fiscal_year, int),
        "quantitative_reported_fact_invalid",
    )
    value = _decimal(raw.get("value_decimal"), "quantitative_reported_fact_value_invalid")
    body = {
        "authority_ref": numeric_ref,
        "quantitative_kind": "reported_fact",
        "ticker": ticker,
        "metric_id": metric_id,
        "value_decimal": _decimal_text(value),
        "unit": unit,
        "unit_family": str(raw.get("unit_family") or ""),
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "period_role": period_role,
        "period_start": str(raw.get("period_start") or ""),
        "period_end": str(raw.get("period_end") or ""),
        "research_as_of": str(raw.get("research_as_of") or ""),
        "authority_mode": str(raw.get("authority_mode") or ""),
        "citation_urls": citation_urls,
        "source_digests": source_digests,
        "source_observation_ids": [
            str(value) for value in raw.get("source_observation_ids") or ()
        ],
        "numeric_fact_authority": True,
        "model_generated": False,
    }
    return {**body, "fact_digest": canonical_digest(body)}


def _existing_derived_fact(
    raw: Mapping[str, Any], *, allowed_tickers: set[str]
) -> dict[str, Any]:
    """Project an already compiled NumericFact formula into the derived lane.

    The legacy NumericFact contract intentionally permits both source-bound facts and
    locally computed ratios.  The research-facing contract must keep their authority
    while making that distinction visible to every downstream consumer.
    """

    ticker = str(raw.get("ticker") or "").upper()
    authority_ref = str(raw.get("numeric_fact_id") or "")
    metric_id = str(raw.get("metric_id") or "")
    unit = str(raw.get("unit") or "")
    fiscal_period = str(raw.get("fiscal_period") or "")
    period_role = str(raw.get("period_role") or "")
    fiscal_year = raw.get("fiscal_year")
    formula_trace = dict(raw.get("formula_trace") or {})
    input_refs = _refs(
        formula_trace.get("input_numeric_fact_ids") or (),
        "quantitative_derived_fact_input_refs_missing",
    )
    citation_urls = _refs(
        raw.get("citation_urls") or (),
        "quantitative_derived_fact_citation_missing",
    )
    source_digests = _refs(
        raw.get("source_digests") or (),
        "quantitative_derived_fact_source_digest_missing",
    )
    _require(
        raw.get("schema_version") == "fin_ia_numeric_fact_v1_0"
        and raw.get("numeric_fact_authority") is True
        and raw.get("authority_mode") == "deterministically_derived_numeric_fact"
        and ticker in allowed_tickers
        and authority_ref.startswith("NUMFACT::")
        and metric_id
        and unit
        and fiscal_period
        and period_role
        and isinstance(fiscal_year, int)
        and str(formula_trace.get("formula") or "")
        and str(formula_trace.get("operation") or ""),
        "quantitative_derived_fact_invalid",
    )
    value = _decimal(raw.get("value_decimal"), "quantitative_derived_fact_value_invalid")
    body = {
        "authority_ref": authority_ref,
        "quantitative_kind": "deterministic_derived_metric",
        "ticker": ticker,
        "metric_id": metric_id,
        "derived_metric_id": metric_id,
        "value_decimal": _decimal_text(value),
        "unit": unit,
        "unit_family": str(raw.get("unit_family") or ""),
        "fiscal_year": fiscal_year,
        "fiscal_period": fiscal_period,
        "period_role": period_role,
        "period_start": str(raw.get("period_start") or ""),
        "period_end": str(raw.get("period_end") or ""),
        "formula": str(formula_trace["formula"]),
        "operation": str(formula_trace["operation"]),
        "input_metrics": [
            str(value) for value in formula_trace.get("input_metrics") or ()
        ],
        "input_authority_refs": input_refs,
        "citation_urls": citation_urls,
        "source_digests": source_digests,
        "source_observation_ids": [
            str(value) for value in raw.get("source_observation_ids") or ()
        ],
        "reported_fact_authority": False,
        "numeric_fact_authority": False,
        "upstream_numeric_fact_authority": True,
        "deterministic_formula_authority": True,
        "model_generated": False,
    }
    return {**body, "derived_metric_digest": canonical_digest(body)}


def _same_basis_relations(
    reported_facts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = (
        defaultdict(list)
    )
    for raw in reported_facts:
        row = dict(raw)
        if row.get("period_role") not in {"quarter_discrete", "fiscal_year"}:
            continue
        key = (
            str(row["ticker"]),
            str(row["metric_id"]),
            str(row["unit"]),
            str(row["fiscal_period"]),
            str(row["period_role"]),
        )
        groups[key].append(row)
    relations: list[dict[str, Any]] = []
    for key, rows in sorted(groups.items()):
        by_year = {int(row["fiscal_year"]): row for row in rows}
        for current_year in sorted(by_year):
            prior_year = current_year - 1
            if prior_year not in by_year:
                continue
            current = by_year[current_year]
            prior = by_year[prior_year]
            prior_value = _decimal(
                prior["value_decimal"], "quantitative_relation_prior_value_invalid"
            )
            if prior_value == 0:
                continue
            current_value = _decimal(
                current["value_decimal"],
                "quantitative_relation_current_value_invalid",
            )
            ratio = (current_value - prior_value) / abs(prior_value)
            seed = {
                "relation_kind": "same_basis_year_over_year_growth",
                "current_ref": current["authority_ref"],
                "prior_ref": prior["authority_ref"],
            }
            body = {
                "authority_ref": "DERIVED::" + canonical_digest(seed)[:24].upper(),
                "quantitative_kind": "deterministic_derived_metric",
                "ticker": key[0],
                "metric_id": key[1],
                "derived_metric_id": key[1] + "_year_over_year_growth",
                "value_decimal": _decimal_text(ratio),
                "unit": "ratio",
                "display_percent_decimal": _decimal_text(ratio * Decimal("100")),
                "fiscal_year": current_year,
                "fiscal_period": key[3],
                "period_role": key[4],
                "formula": "(current_value - prior_value) / abs(prior_value)",
                "input_authority_refs": [
                    str(current["authority_ref"]),
                    str(prior["authority_ref"]),
                ],
                "same_basis_checks": {
                    "ticker_equal": True,
                    "metric_equal": True,
                    "unit_equal": True,
                    "fiscal_period_equal": True,
                    "period_role_equal": True,
                    "consecutive_fiscal_years": True,
                },
                "reported_fact_authority": False,
                "numeric_fact_authority": False,
                "deterministic_formula_authority": True,
                "model_generated": False,
            }
            relations.append(
                {**body, "derived_metric_digest": canonical_digest(body)}
            )
    return relations


def compile_research_estimate(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate an analyst estimate without ever upgrading it to NumericFact."""

    assumption_refs = _refs(
        payload.get("assumption_refs") or (),
        "research_estimate_assumption_refs_invalid",
    )
    supporting_refs = _refs(
        payload.get("supporting_authority_refs") or (),
        "research_estimate_supporting_refs_invalid",
    )
    lower = _decimal(payload.get("lower_bound"), "research_estimate_lower_invalid")
    upper = _decimal(payload.get("upper_bound"), "research_estimate_upper_invalid")
    _require(lower <= upper, "research_estimate_range_invalid")
    body = {
        "schema_version": RESEARCH_ESTIMATE_SCHEMA_VERSION,
        "quantitative_kind": "research_estimate",
        "case_key": str(payload.get("case_key") or "").upper(),
        "metric_id": str(payload.get("metric_id") or ""),
        "period_label": str(payload.get("period_label") or ""),
        "unit": str(payload.get("unit") or ""),
        "lower_bound": _decimal_text(lower),
        "upper_bound": _decimal_text(upper),
        "central_value": (
            _decimal_text(
                _decimal(
                    payload.get("central_value"),
                    "research_estimate_central_invalid",
                )
            )
            if payload.get("central_value") is not None
            else None
        ),
        "method": str(payload.get("method") or ""),
        "assumption_refs": assumption_refs,
        "supporting_authority_refs": supporting_refs,
        "authored_by": str(payload.get("authored_by") or ""),
        "confidence": str(payload.get("confidence") or ""),
        "numeric_fact_authority": False,
        "citation_as_reported_fact_forbidden": True,
    }
    _require(
        body["case_key"]
        and body["metric_id"]
        and body["period_label"]
        and body["unit"]
        and body["method"]
        and body["authored_by"]
        and body["confidence"] in {"low", "medium", "high"},
        "research_estimate_shape_invalid",
    )
    if body["central_value"] is not None:
        central = _decimal(
            body["central_value"], "research_estimate_central_invalid"
        )
        _require(lower <= central <= upper, "research_estimate_central_outside_range")
    identity = {
        key: body[key]
        for key in (
            "case_key",
            "metric_id",
            "period_label",
            "assumption_refs",
            "supporting_authority_refs",
        )
    }
    body["estimate_id"] = "ESTIMATE::" + canonical_digest(identity)[:24].upper()
    return {**body, "estimate_digest": canonical_digest(body)}


def compile_research_scenario(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a named scenario as assumptions plus outputs, never as fact."""

    assumption_refs = _refs(
        payload.get("assumption_refs") or (),
        "research_scenario_assumption_refs_invalid",
    )
    output_refs = _refs(
        payload.get("output_estimate_refs") or (),
        "research_scenario_output_refs_invalid",
    )
    body = {
        "schema_version": RESEARCH_SCENARIO_SCHEMA_VERSION,
        "quantitative_kind": "scenario",
        "case_key": str(payload.get("case_key") or "").upper(),
        "scenario_name": str(payload.get("scenario_name") or ""),
        "scenario_type": str(payload.get("scenario_type") or ""),
        "time_horizon": str(payload.get("time_horizon") or ""),
        "assumption_refs": assumption_refs,
        "output_estimate_refs": output_refs,
        "authored_by": str(payload.get("authored_by") or ""),
        "numeric_fact_authority": False,
        "reported_fact_language_forbidden": True,
    }
    _require(
        body["case_key"]
        and body["scenario_name"]
        and body["scenario_type"] in {"downside", "base", "upside", "stress"}
        and body["time_horizon"]
        and body["authored_by"],
        "research_scenario_shape_invalid",
    )
    identity = {
        key: body[key]
        for key in (
            "case_key",
            "scenario_name",
            "scenario_type",
            "time_horizon",
            "assumption_refs",
            "output_estimate_refs",
        )
    }
    body["scenario_id"] = "SCENARIO::" + canonical_digest(identity)[:24].upper()
    return {**body, "scenario_digest": canonical_digest(body)}


def compile_quantitative_authority_state(
    *,
    case_key: str,
    request_results: Sequence[Mapping[str, Any]],
    recorded_at: str,
    research_estimates: Sequence[Mapping[str, Any]] = (),
    scenarios: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Compile current S2 results into four explicitly separated categories."""

    normalized_case = str(case_key).strip().upper()
    _require(normalized_case and request_results, "quantitative_state_input_invalid")
    reported_by_ref: dict[str, dict[str, Any]] = {}
    derived_by_ref: dict[str, dict[str, Any]] = {}
    request_states: list[dict[str, Any]] = []
    for raw_request in request_results:
        request = dict(raw_request)
        request_payload = dict(request.get("request") or {})
        request_id = str(request_payload.get("request_id") or "")
        allowed_tickers = {
            normalized_case,
            str(request_payload.get("subject_ticker") or "").upper(),
            *(
                str(value).upper()
                for value in request_payload.get("target_entities") or ()
            ),
        }
        allowed_tickers.discard("")
        typed_results = request.get("typed_fact_results")
        _require(
            request.get("case_key") == normalized_case
            and request_id
            and isinstance(typed_results, list),
            "quantitative_state_request_invalid",
        )
        state_counts = {"resolved": 0, "typed_gap": 0, "typed_conflict": 0}
        facts_for_request: list[str] = []
        gap_rows: list[dict[str, Any]] = []
        conflict_rows: list[dict[str, Any]] = []
        for raw_result in typed_results:
            result = dict(raw_result)
            status = str(result.get("status") or "")
            _require(
                result.get("schema_version")
                == "fin_ia_typed_fact_execution_result_v1_0"
                and status in state_counts
                and str(result.get("ticker") or "").upper() in allowed_tickers,
                "quantitative_state_typed_result_invalid",
            )
            state_counts[status] += 1
            if status == "resolved":
                for raw_fact in result.get("facts") or ():
                    fact_payload = dict(raw_fact)
                    if (
                        fact_payload.get("authority_mode")
                        == "deterministically_derived_numeric_fact"
                    ):
                        fact = _existing_derived_fact(
                            fact_payload, allowed_tickers=allowed_tickers
                        )
                        target = derived_by_ref
                    else:
                        fact = _reported_fact(
                            fact_payload, allowed_tickers=allowed_tickers
                        )
                        target = reported_by_ref
                    existing = target.get(fact["authority_ref"])
                    _require(
                        existing is None or existing == fact,
                        "quantitative_state_fact_identity_conflict",
                    )
                    target[fact["authority_ref"]] = fact
                    facts_for_request.append(fact["authority_ref"])
            elif status == "typed_gap":
                gap = dict(result.get("typed_gap") or {})
                gap_rows.append(
                    {
                        "fact_request_id": str(result.get("fact_request_id") or ""),
                        "metric_id": str(result.get("metric_id") or ""),
                        "gap_code": str(gap.get("gap_code") or "typed_fact_gap"),
                        "public_information_gap_authority": False,
                    }
                )
            else:
                conflict = dict(result.get("typed_conflict") or {})
                conflict_rows.append(
                    {
                        "fact_request_id": str(result.get("fact_request_id") or ""),
                        "metric_id": str(result.get("metric_id") or ""),
                        "conflict_code": str(
                            conflict.get("conflict_code") or "typed_fact_conflict"
                        ),
                        "model_may_choose_value": False,
                    }
                )
        request_states.append(
            {
                "request_id": request_id,
                "slot_id": str(request_payload.get("slot_id") or ""),
                "subject_ticker": str(
                    request_payload.get("subject_ticker") or normalized_case
                ).upper(),
                "allowed_tickers": sorted(allowed_tickers),
                "facet_ids": sorted(
                    str(value) for value in request_payload.get("requested_facet_ids") or ()
                ),
                "state_counts": state_counts,
                "reported_fact_refs": sorted(set(facts_for_request)),
                "typed_gaps": gap_rows,
                "typed_conflicts": conflict_rows,
            }
        )

    reported_facts = [reported_by_ref[ref] for ref in sorted(reported_by_ref)]
    derived = [derived_by_ref[ref] for ref in sorted(derived_by_ref)]
    for relation in _same_basis_relations(reported_facts):
        existing = derived_by_ref.get(str(relation["authority_ref"]))
        _require(
            existing is None or existing == relation,
            "quantitative_state_derived_identity_conflict",
        )
        if existing is None:
            derived.append(relation)
    estimates = [compile_research_estimate(dict(row)) for row in research_estimates]
    scenario_rows = [compile_research_scenario(dict(row)) for row in scenarios]
    unsigned = {
        "schema_version": QUANTITATIVE_AUTHORITY_SCHEMA_VERSION,
        "status": "current_s2_authority_compiled",
        "case_key": normalized_case,
        "recorded_at": str(recorded_at),
        "reported_facts": reported_facts,
        "deterministic_derived_metrics": derived,
        "research_estimates": estimates,
        "scenarios": scenario_rows,
        "request_states": request_states,
        "summary": {
            "reported_fact_count": len(reported_facts),
            "deterministic_derived_metric_count": len(derived),
            "research_estimate_count": len(estimates),
            "scenario_count": len(scenario_rows),
            "typed_gap_count": sum(
                len(row["typed_gaps"]) for row in request_states
            ),
            "typed_conflict_count": sum(
                len(row["typed_conflicts"]) for row in request_states
            ),
        },
        "authority_boundary": {
            "reported_fact_is_source_bound": True,
            "derived_metric_requires_formula_and_input_refs": True,
            "estimate_requires_assumptions_range_method_and_author": True,
            "scenario_requires_named_assumptions_and_estimate_outputs": True,
            "estimate_or_scenario_becomes_numeric_fact": False,
            "model_may_choose_between_typed_conflicts": False,
        },
    }
    return {**unsigned, "quantitative_authority_digest": canonical_digest(unsigned)}


__all__ = [
    "QUANTITATIVE_AUTHORITY_SCHEMA_VERSION",
    "RESEARCH_ESTIMATE_SCHEMA_VERSION",
    "RESEARCH_SCENARIO_SCHEMA_VERSION",
    "QuantitativeAuthorityError",
    "compile_quantitative_authority_state",
    "compile_research_estimate",
    "compile_research_scenario",
]
