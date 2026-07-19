from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Mapping


PRE_MEMO_FACT_SELECTION_SCHEMA_VERSION = "sec_agent_pre_memo_fact_selection_v0.1"
DISPLAY_VALUE_LINEAGE_SCHEMA_VERSION = "sec_agent_display_value_lineage_v0.1"
_STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "how",
    "into",
    "the",
    "this",
    "that",
    "with",
    "是否",
    "什么",
    "公司",
    "研究",
}


def build_pre_memo_fact_selection(state: Mapping[str, Any]) -> dict[str, Any]:
    """Select memo-eligible base and derived facts after D6/D9/D10 governance."""

    reconciliation = state.get("reconciliation_ledger") if isinstance(state.get("reconciliation_ledger"), Mapping) else {}
    gate_matrix = state.get("gate_registry_eval_matrix") if isinstance(state.get("gate_registry_eval_matrix"), Mapping) else {}
    derived_layer = state.get("derived_metric_layer") if isinstance(state.get("derived_metric_layer"), Mapping) else {}
    typed_gap_ledger = state.get("typed_gap_ledger") if isinstance(state.get("typed_gap_ledger"), Mapping) else {}
    bounded_gap_register = state.get("bounded_gap_register") if isinstance(state.get("bounded_gap_register"), Mapping) else {}

    blocking_gate_index = _blocking_gate_index(gate_matrix)
    objective_text = _fact_selection_objective_text(state)
    approved_facts: list[dict[str, Any]] = []
    rejected_facts: list[dict[str, Any]] = []
    conflict_gap_links: list[dict[str, Any]] = []
    candidates_by_id = _candidate_index(reconciliation)
    focus_tickers = set(_scope_tickers_from_state(state, "focus_tickers"))
    search_scope_tickers = set(_scope_tickers_from_state(state, "search_scope_tickers"))
    demand_proxy_tickers = set(_demand_proxy_tickers_from_state(state))

    for group in _mapping_rows(reconciliation.get("reconciliation_groups")):
        group_id = _text(group.get("group_id"))
        blocking_gates = blocking_gate_index.get(group_id, [])
        status = _text(group.get("resolution_status"))
        preferred = group.get("preferred_value") if isinstance(group.get("preferred_value"), Mapping) else {}
        candidate_ids = _strings(group.get("candidate_ids"))
        base = {
            "selection_id": _stable_id("pre_memo_fact", group_id),
            "reconciliation_group_id": group_id,
            "ticker": _text(group.get("ticker")).upper(),
            "canonical_metric_id": _text(group.get("canonical_metric_id")),
            "product_or_segment": _text(group.get("product_or_segment")),
            "period_key": _text(group.get("period_key")),
            "candidate_ids": candidate_ids,
            "blocking_gate_result_ids": [_text(row.get("gate_result_id")) for row in blocking_gates],
            "source_layer": "reconciliation_ledger",
        }
        base["scope_role"] = _scope_role_for_ticker(
            base["ticker"],
            focus_tickers=focus_tickers,
            search_scope_tickers=search_scope_tickers,
            demand_proxy_tickers=demand_proxy_tickers,
        )
        memo_reject_reason = _resolved_group_memo_reject_reason(group, preferred)
        if status.startswith("resolved") and preferred and not blocking_gates and not memo_reject_reason:
            approved_facts.append(
                _with_fact_selection_relevance(
                    {
                        **base,
                        "fact_id": _text(preferred.get("candidate_id")) or group_id,
                        "value": _text(preferred.get("value")),
                        "numeric_value": _text(preferred.get("numeric_value")),
                        "unit": _text(preferred.get("unit")),
                        "source_id": _text(preferred.get("source_id")),
                        "evidence_ref": _text(preferred.get("evidence_ref")),
                        "source_family": _text(preferred.get("source_family")),
                        "resolution_rule": _text(preferred.get("resolution_rule")),
                        "resolution_confidence": _text(preferred.get("confidence")),
                        "selection_status": "approved",
                        "claim_boundary": "resolved_reconciliation_fact_memo_eligible",
                    },
                    objective_text=objective_text,
                )
            )
        else:
            reason = memo_reject_reason or ("blocking_gate_failed" if blocking_gates else status or "missing_resolution")
            rejected_facts.append(
                {
                    **base,
                    "selection_status": "rejected",
                    "reject_reason": reason,
                    "conflict_gap_id": _text(group.get("conflict_gap_id")),
                    "conflict_types": _strings(group.get("conflict_types")),
                    "claim_boundary": "unresolved_or_blocked_reconciliation_group_not_memo_eligible",
                }
            )
        gap_id = _text(group.get("conflict_gap_id"))
        if gap_id:
            conflict_gap_links.append(
                {
                    "gap_id": gap_id,
                    "gap_type": "conflict_gap",
                    "reconciliation_group_id": group_id,
                    "candidate_ids": candidate_ids,
                    "resolution_status": status,
                    "treatment_action": "expose_conflict_gap_until_reconciliation_resolves",
                }
            )

    approved_derived_metrics: list[dict[str, Any]] = []
    rejected_derived_metrics: list[dict[str, Any]] = []
    rejected_fact_ids = {fact_id for row in rejected_facts for fact_id in _strings(row.get("candidate_ids"))}
    for row in _mapping_rows(derived_layer.get("derived_metrics")):
        input_fact_ids = _strings(row.get("input_fact_ids"))
        blocked_inputs = sorted(set(input_fact_ids) & rejected_fact_ids)
        blocking_gates = _strings((row.get("gate_status_detail") or {}).get("blocking_gate_result_ids")) if isinstance(row.get("gate_status_detail"), Mapping) else []
        if _text(row.get("gate_status")) in {"pass", "warn"} and not blocked_inputs and not blocking_gates:
            approved_derived_metrics.append(
                _with_display_value_lineage(
                    {
                        "derived_metric_id": _text(row.get("derived_metric_id")),
                        "derived_metric_family": _text(row.get("derived_metric_family")),
                        "ticker": _text(row.get("ticker")).upper(),
                        "value": _text(row.get("value")),
                        "numeric_value": _text(row.get("numeric_value") or row.get("value")),
                        "unit": _text(row.get("unit")),
                        "period_key": _text(row.get("period_key")),
                        "input_fact_ids": input_fact_ids,
                        "input_reconciliation_group_ids": _strings(row.get("input_reconciliation_group_ids")),
                        "gate_status": _text(row.get("gate_status")),
                        "selection_status": "approved",
                        "source_layer": "derived_metric_layer",
                        "claim_boundary": "derived_metric_memo_eligible_only_with_formula_and_input_lineage",
                    }
                )
            )
        else:
            rejected_derived_metrics.append(
                {
                    "derived_metric_id": _text(row.get("derived_metric_id")),
                    "derived_metric_family": _text(row.get("derived_metric_family")),
                    "ticker": _text(row.get("ticker")).upper(),
                    "input_fact_ids": input_fact_ids,
                    "blocked_input_fact_ids": blocked_inputs,
                    "blocking_gate_result_ids": blocking_gates,
                    "gate_status": _text(row.get("gate_status")),
                    "selection_status": "rejected",
                    "reject_reason": "input_gate_blocked" if blocking_gates or blocked_inputs else "nonpassing_gate_status",
                    "source_layer": "derived_metric_layer",
                }
            )

    bounded_gap_links = _bounded_gap_links(typed_gap_ledger, bounded_gap_register, conflict_gap_links)
    payload = {
        "schema_version": PRE_MEMO_FACT_SELECTION_SCHEMA_VERSION,
        "policy": "memo_consumes_only_reconciled_facts_and_gate_passing_derived_metrics_v0_1",
        "run_id": _text(state.get("run_id")),
        "approved_facts": approved_facts,
        "rejected_facts": rejected_facts,
        "approved_derived_metrics": approved_derived_metrics,
        "rejected_derived_metrics": rejected_derived_metrics,
        "bounded_gap_links": bounded_gap_links,
        "blocked_evidence_refs": sorted(
            {
                ref
                for row in rejected_facts
                for candidate_id in _strings(row.get("candidate_ids"))
                for ref in [_text(candidates_by_id.get(candidate_id, {}).get("evidence_ref"))]
                if ref
            }
        ),
        "blocked_candidate_ids": sorted(rejected_fact_ids),
        "blocking_gate_result_ids": sorted(
            {
                gate_id
                for row in [*rejected_facts, *rejected_derived_metrics]
                for gate_id in _strings(row.get("blocking_gate_result_ids"))
            }
        ),
        "summary": {
            "approved_fact_count": len(approved_facts),
            "rejected_fact_count": len(rejected_facts),
            "approved_derived_metric_count": len(approved_derived_metrics),
            "rejected_derived_metric_count": len(rejected_derived_metrics),
            "bounded_gap_link_count": len(bounded_gap_links),
            "blocking_gate_result_count": len(
                {
                    gate_id
                    for row in [*rejected_facts, *rejected_derived_metrics]
                    for gate_id in _strings(row.get("blocking_gate_result_ids"))
                }
            ),
            "by_rejected_fact_reason": dict(sorted(Counter(row.get("reject_reason") or "unknown" for row in rejected_facts).items())),
            "by_bounded_gap_type": dict(sorted(Counter(row.get("gap_type") or "unknown" for row in bounded_gap_links).items())),
        },
    }
    payload["validation"] = validate_pre_memo_fact_selection(payload)
    return payload


def apply_pre_memo_fact_selection_to_judgment(
    judgment_plan: Mapping[str, Any],
    fact_selection: Mapping[str, Any],
) -> dict[str, Any]:
    judgment = dict(judgment_plan or {})
    supported = [dict(row) for row in judgment.get("supported_claims") or [] if isinstance(row, Mapping)]
    unsupported = [dict(row) for row in judgment.get("unsupported_claims") or [] if isinstance(row, Mapping)]
    blocked_refs = set(_strings(fact_selection.get("blocked_evidence_refs")))
    blocked_candidates = set(_strings(fact_selection.get("blocked_candidate_ids")))
    approved_fact_ids = {
        _text(row.get("fact_id"))
        for row in fact_selection.get("approved_facts") or []
        if isinstance(row, Mapping) and _text(row.get("fact_id"))
    }
    approved_derived_ids = {
        _text(row.get("derived_metric_id"))
        for row in fact_selection.get("approved_derived_metrics") or []
        if isinstance(row, Mapping) and _text(row.get("derived_metric_id"))
    }
    filtered_supported: list[dict[str, Any]] = []
    moved_to_unsupported: list[dict[str, Any]] = []
    for claim in supported:
        if _text(claim.get("agent_id")) == "pre_memo_fact_selector":
            continue
        evidence_refs = set(_strings(claim.get("evidence_refs") or claim.get("supporting_evidence_ids")))
        fact_refs = set(_strings(claim.get("fact_ids") or claim.get("input_fact_ids")))
        derived_refs = set(_strings(claim.get("derived_metric_ids")))
        blocked = sorted((evidence_refs & blocked_refs) | (fact_refs & blocked_candidates))
        unapproved_derived = sorted(derived_refs - approved_derived_ids) if derived_refs else []
        if blocked or unapproved_derived:
            moved = {
                "claim_id": _text(claim.get("claim_id")),
                "agent_id": _text(claim.get("agent_id")),
                "claim": "claim text withheld because pre-memo governance blocked this fact; use bounded gap metadata instead",
                "reason": "blocked_by_pre_memo_fact_selection",
                "blocked_evidence_refs": blocked,
                "unapproved_derived_metric_ids": unapproved_derived,
                "source_claim": claim,
            }
            moved_to_unsupported.append(moved)
            unsupported.append(moved)
        else:
            filtered_supported.append(claim)

    deterministic_fact_claims = _deterministic_fact_claims_from_approved_facts(
        fact_selection.get("approved_facts") or [],
        existing_supported_claims=filtered_supported,
    )
    filtered_supported.extend(deterministic_fact_claims)

    constraints = dict(judgment.get("memo_constraints") or {}) if isinstance(judgment.get("memo_constraints"), Mapping) else {}
    missing_evidence = [dict(row) for row in constraints.get("missing_evidence") or [] if isinstance(row, Mapping)]
    for row in fact_selection.get("bounded_gap_links") or []:
        if not isinstance(row, Mapping):
            continue
        missing_evidence.append(
            {
                "gap_id": _text(row.get("gap_id")),
                "gap_type": _text(row.get("gap_type")),
                "reason": _text(row.get("treatment_action")) or "bounded_gap_not_memo_fact",
                "source_layer": _text(row.get("source_layer")),
            }
        )
    constraints["missing_evidence"] = _dedupe_dicts(missing_evidence)
    if moved_to_unsupported and "pre_memo_fact_selection_blocked_claims" not in constraints.get("blocked_reasons", []):
        constraints["blocked_reasons"] = [*list(constraints.get("blocked_reasons") or []), "pre_memo_fact_selection_blocked_claims"]
    constraints["approved_fact_count"] = len(approved_fact_ids)
    constraints["approved_derived_metric_count"] = len(approved_derived_ids)

    stats = dict(judgment.get("claim_card_stats") or {}) if isinstance(judgment.get("claim_card_stats"), Mapping) else {}
    stats["supported_claim_count"] = len(filtered_supported)
    stats["pre_memo_blocked_claim_count"] = len(moved_to_unsupported)
    stats["pre_memo_deterministic_fact_claim_count"] = len(deterministic_fact_claims)
    stats["approved_fact_count"] = len(approved_fact_ids)
    stats["approved_derived_metric_count"] = len(approved_derived_ids)

    return {
        **judgment,
        "supported_claims": filtered_supported,
        "unsupported_claims": unsupported,
        "memo_constraints": constraints,
        "claim_card_stats": stats,
        "pre_memo_fact_selection": {
            "schema_version": fact_selection.get("schema_version") or PRE_MEMO_FACT_SELECTION_SCHEMA_VERSION,
            "approved_fact_ids": sorted(approved_fact_ids),
            "approved_derived_metric_ids": sorted(approved_derived_ids),
            "blocked_claims": moved_to_unsupported,
            "deterministic_fact_claim_ids": [row["claim_id"] for row in deterministic_fact_claims],
            "bounded_gap_links": [dict(row) for row in fact_selection.get("bounded_gap_links") or [] if isinstance(row, Mapping)],
            "summary": dict(fact_selection.get("summary") or {}) if isinstance(fact_selection.get("summary"), Mapping) else {},
        },
        "memo_writer_allowed": bool(judgment.get("memo_writer_allowed", True)) and not (moved_to_unsupported and not filtered_supported),
        "governance_filter_policy": "pre_memo_governance_filtered_claim_cards_v0_1",
    }


def _deterministic_fact_claims_from_approved_facts(
    approved_facts: Any,
    *,
    existing_supported_claims: list[dict[str, Any]],
    max_claims: int = 18,
) -> list[dict[str, Any]]:
    existing_refs = {
        ref
        for claim in existing_supported_claims
        for ref in _strings(claim.get("evidence_refs") or claim.get("supporting_evidence_ids"))
    }
    rows = [
        dict(row)
        for row in approved_facts
        if isinstance(row, Mapping) and _approved_fact_can_be_claim_card(row)
    ]
    rows = sorted(rows, key=_approved_fact_priority)
    rows = _select_dimension_balanced_fact_rows(rows, max_claims=max_claims, existing_refs=existing_refs)
    claims: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()
    for row in rows:
        evidence_ref = _text(row.get("evidence_ref"))
        key = (
            _text(row.get("ticker")).upper(),
            _text(row.get("canonical_metric_id")),
            _text(row.get("product_or_segment")),
            _text(row.get("period_key")),
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        claim_id = _stable_id("pre_memo_fact_claim", row.get("selection_id"), row.get("fact_id"), evidence_ref)
        canonical_metric = _text(row.get("canonical_metric_id"))
        dimension = _analysis_dimension_for_fact(canonical_metric, row=row)
        claims.append(
            {
                "claim_id": claim_id,
                "agent_id": "pre_memo_fact_selector",
                "claim": _approved_fact_claim_text(row),
                "claim_type": _claim_type_for_fact(canonical_metric),
                "ticker_scope": [_text(row.get("ticker")).upper()] if _text(row.get("ticker")) else [],
                "metric_scope": [canonical_metric] if canonical_metric else [],
                "memo_slot": "product_technology" if dimension == "product_and_production" else "fundamentals",
                "analysis_dimension": dimension,
                "scope_role": _text(row.get("scope_role")),
                "economic_role": _text(row.get("economic_role")),
                "transmission_role": _text(row.get("transmission_role")),
                "memo_use_role": _text(row.get("memo_use_role")),
                "role_boundary": _text(row.get("role_boundary")),
                "materiality": "high" if canonical_metric in {"financial_metric:revenue", "financial_metric:capex", "product_kpi:product_revenue"} else "medium",
                "direction": "unknown",
                "evidence_refs": [evidence_ref] if evidence_ref else [],
                "fact_ids": [_text(row.get("fact_id"))] if _text(row.get("fact_id")) else [],
                "source_families": [_text(row.get("source_family"))] if _text(row.get("source_family")) else [],
                "confidence": _text(row.get("resolution_confidence")) or "high",
                "unsupported": False,
                "caveats": _fact_caveats(row),
                "missing_confirmations": [],
                "claim_card_version": "v0.3",
                "claim_rank_score": 95 if canonical_metric in {"financial_metric:revenue", "financial_metric:capex", "product_kpi:product_revenue"} else 88,
                "claim_rank_bucket": "memo_ready",
                "memo_readiness": "memo_ready",
                "claim_rank_reasons": _dedupe_strings(
                    [
                        "approved_reconciliation_fact",
                        "exact_authority_source",
                        "pre_memo_fact_selector",
                        *_strings(row.get("selection_relevance_reasons")),
                    ]
                ),
                "claim_boundary": "approved_reconciliation_fact_only",
                "pre_memo_fact_selection_id": _text(row.get("selection_id")),
                "selection_relevance_score": row.get("selection_relevance_score", 0),
                "resolution_rule": _text(row.get("resolution_rule")),
                "period_key": _text(row.get("period_key")),
                "product_or_segment": _text(row.get("product_or_segment")),
                "analyst_depth": {
                    "schema_version": "sec_agent_claim_card_analyst_depth_v0.1",
                    "analysis_dimension": dimension,
                    "analyst_angle": _analysis_dimension_title_for_fact(dimension),
                    "analysis_lens": "Use approved reconciled financial facts as the numeric backbone before adding thesis interpretation.",
                    "evidence_role": _text(row.get("economic_role")) or "reported_company_authority",
                    "transmission_role": _text(row.get("transmission_role")),
                    "business_mechanism": _business_mechanism_for_fact(dimension, row=row),
                    "financial_bridge": "Use this verified numeric fact only after linking it to revenue, margin, capex, cash-flow, financing, or valuation mechanism explicitly.",
                    "comparison_basis": "Compare only against facts with the same ticker, metric, period_role, and product/segment key.",
                    "counter_read": "若同口径事实反向变化，或产品/期间口径发生切换，该维度权重需要下调并单独暴露冲突。",
                    "role_boundary": _text(row.get("role_boundary")),
                    "analyst_depth_gate": "period_product_unit_conflict_must_not_be_averaged",
                },
            }
        )
    return claims


def _select_dimension_balanced_fact_rows(
    rows: list[dict[str, Any]],
    *,
    max_claims: int,
    existing_refs: set[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()

    def add(row: Mapping[str, Any]) -> bool:
        if len(selected) >= max_claims:
            return False
        evidence_ref = _text(row.get("evidence_ref"))
        if evidence_ref and evidence_ref in existing_refs:
            return False
        key = (
            _text(row.get("ticker")).upper(),
            _text(row.get("canonical_metric_id")),
            _text(row.get("product_or_segment")),
            _text(row.get("period_key")),
        )
        if key in seen_keys:
            return False
        selected.append(dict(row))
        seen_keys.add(key)
        return True

    # Reserve room for product and capital facts before the general revenue base
    # can consume the compact memo prompt budget.
    dimension_limits = (
        ("product_and_production", 4),
        ("capital_and_financing", 6),
        ("fundamentals", 6),
    )
    for dimension, limit in dimension_limits:
        added = 0
        for row in rows:
            if _analysis_dimension_for_fact(_text(row.get("canonical_metric_id")), row=row) != dimension:
                continue
            if add(row):
                added += 1
            if added >= limit:
                break
    for row in rows:
        add(row)
    return selected


def _approved_fact_can_be_claim_card(row: Mapping[str, Any]) -> bool:
    if _text(row.get("selection_status")) != "approved":
        return False
    canonical = _text(row.get("canonical_metric_id"))
    if _is_unscored_peer_context_total_fact(row, canonical_metric=canonical):
        return False
    if not _approved_fact_unit_is_claim_card_safe(row, canonical_metric=canonical):
        return False
    if canonical not in {
        "financial_metric:revenue",
        "financial_metric:gross_margin",
        "financial_metric:gross_profit",
        "financial_metric:operating_income",
        "financial_metric:operating_cash_flow",
        "financial_metric:fcf",
        "financial_metric:capex",
        "financial_metric:debt",
        "financial_metric:cash",
        "product_kpi:product_revenue",
        "product_kpi:backlog",
    }:
        return False
    if canonical == "financial_metric:revenue" and not _revenue_fact_label_is_claim_card_safe(row):
        return False
    if canonical in {"financial_metric:gross_margin", "financial_metric:gross_profit"} and not _profitability_fact_label_is_claim_card_safe(row):
        return False
    if _text(row.get("source_family")) in {"public_source_context", "live_public_web_context", "market_snapshot", "industry_snapshot", "relationship_graph", "milvus_semantic"}:
        return False
    return bool(_text(row.get("display_value")) and _text(row.get("evidence_ref")))


def _approved_fact_unit_is_claim_card_safe(row: Mapping[str, Any], *, canonical_metric: str) -> bool:
    if _metric_unit_memo_reject_reason(row, canonical_metric=canonical_metric):
        return False
    if canonical_metric not in {
        "financial_metric:revenue",
        "financial_metric:gross_profit",
        "financial_metric:operating_income",
        "financial_metric:operating_cash_flow",
        "financial_metric:fcf",
        "financial_metric:capex",
        "financial_metric:debt",
        "financial_metric:cash",
        "product_kpi:product_revenue",
        "product_kpi:backlog",
    }:
        return True
    unit = _text(row.get("unit")).lower().replace(" ", "_")
    numeric_value = _float_or_none(row.get("numeric_value") or row.get("value"))
    if unit in {"usd", "$", "dollar", "dollars"} and numeric_value is not None and abs(numeric_value) >= 1000:
        return False
    return True


def _metric_unit_memo_reject_reason(row: Mapping[str, Any], *, canonical_metric: str) -> str:
    unit = _text(row.get("unit")).lower().replace(" ", "_")
    unit_category = _text(row.get("unit_category")).lower().replace(" ", "_")
    role = _text(row.get("metric_role") or row.get("value_role")).lower().replace(" ", "_")
    numeric_value = _float_or_none(row.get("numeric_value") or row.get("value"))
    percent_units = {"%", "percent", "percentage", "percent_of_revenue", "percentage_of_revenue"}
    percent_like = unit in percent_units or unit_category in percent_units or role in {
        "percentage_rate",
        "rate",
        "ratio",
        "margin",
        "growth_rate",
        "percentage",
        "period_change_percent",
    }
    if canonical_metric in {"product_kpi:product_revenue", "financial_metric:revenue"} and percent_like:
        return "revenue_percent_or_change_not_exact_revenue_memo_eligible"
    if canonical_metric == "product_kpi:backlog" and percent_like:
        return "backlog_percent_or_change_not_exact_backlog_memo_eligible"
    if canonical_metric == "financial_metric:gross_margin":
        if unit and unit not in percent_units:
            return "gross_margin_unit_mismatch_not_memo_eligible"
        if numeric_value is not None and (numeric_value < -100 or numeric_value > 100):
            return "gross_margin_rate_out_of_bounds_not_memo_eligible"
    if canonical_metric == "financial_metric:gross_profit" and percent_like:
        return "gross_profit_percent_unit_not_memo_eligible"
    return ""


def _is_unscored_peer_context_total_fact(row: Mapping[str, Any], *, canonical_metric: str) -> bool:
    if _text(row.get("scope_role")) != "peer_context_ticker":
        return False
    relevance_reasons = set(_strings(row.get("selection_relevance_reasons")))
    if _int(row.get("selection_relevance_score")) > 0 and relevance_reasons - {"ticker_matches_research_objective"}:
        return False
    if _text(row.get("product_or_segment")):
        return False
    return canonical_metric in {
        "financial_metric:revenue",
        "financial_metric:gross_profit",
        "financial_metric:gross_margin",
        "financial_metric:operating_income",
        "financial_metric:operating_cash_flow",
        "financial_metric:fcf",
    }


def _approved_fact_priority(row: Mapping[str, Any]) -> tuple[int, int, int, int, str, str, str]:
    canonical = _text(row.get("canonical_metric_id"))
    metric_priority = {
        "financial_metric:capex": 0,
        "financial_metric:revenue": 1,
        "financial_metric:gross_margin": 2,
        "financial_metric:gross_profit": 3,
        "financial_metric:operating_income": 4,
        "financial_metric:operating_cash_flow": 5,
        "financial_metric:fcf": 6,
        "financial_metric:debt": 7,
        "financial_metric:cash": 8,
        "product_kpi:product_revenue": 1,
        "product_kpi:backlog": 2,
    }.get(canonical, 50)
    product_penalty = 0 if not _text(row.get("product_or_segment")) else 3
    relevance = _int(row.get("selection_relevance_score"))
    recency = _period_recency_score(_text(row.get("period_key")))
    return (
        metric_priority,
        -relevance,
        -recency,
        product_penalty,
        _text(row.get("ticker")).upper(),
        _text(row.get("period_key")),
        _text(row.get("selection_id")),
    )


def _approved_fact_claim_text(row: Mapping[str, Any]) -> str:
    ticker = _text(row.get("ticker")).upper() or "The company"
    canonical_metric = _text(row.get("canonical_metric_id"))
    metric = _metric_label(canonical_metric)
    product = _text(row.get("product_or_segment"))
    value = _text(row.get("display_value") or row.get("value"))
    unit = _text(row.get("unit"))
    period = _text(row.get("period_key"))
    product_part = f" for {product}" if product else ""
    unit_part = f" {unit}" if unit and unit.lower() not in value.lower() and "$" not in value and "%" not in value else ""
    period_part = f" in {period}" if period else ""
    numeric_value = _float_or_none(row.get("numeric_value") or value)
    if canonical_metric == "financial_metric:capex" and numeric_value is not None and numeric_value < 0:
        magnitude_part = value[1:] if value.startswith("-") else value
        return (
            f"{ticker} reported capital expenditure cash outflow/proxy of {magnitude_part}{period_part} "
            "(cash-flow sign convention: memo display uses the outflow magnitude)."
        )
    return f"{ticker} reported {metric}{product_part} of {value}{unit_part}{period_part}."


def _fact_caveats(row: Mapping[str, Any]) -> list[str]:
    caveats = ["deterministic fact card from approved reconciliation/pre-memo selection"]
    canonical_metric = _text(row.get("canonical_metric_id"))
    numeric_value = _float_or_none(row.get("numeric_value") or row.get("value"))
    if canonical_metric == "financial_metric:capex" and numeric_value is not None and numeric_value < 0:
        caveats.append("negative sign reflects cash-flow convention; use outflow magnitude and verify exact capex line item before inferring investment growth")
    return caveats


def _metric_label(canonical_metric_id: str) -> str:
    return {
        "financial_metric:revenue": "revenue",
        "financial_metric:gross_margin": "gross margin",
        "financial_metric:gross_profit": "gross profit",
        "financial_metric:operating_income": "operating income",
        "financial_metric:operating_cash_flow": "operating cash flow",
        "financial_metric:fcf": "free cash flow",
        "financial_metric:capex": "capital expenditures",
        "financial_metric:debt": "debt",
        "financial_metric:cash": "cash",
        "product_kpi:product_revenue": "product revenue",
        "product_kpi:backlog": "product backlog",
    }.get(canonical_metric_id, canonical_metric_id or "metric")


def _claim_type_for_fact(canonical_metric_id: str) -> str:
    if canonical_metric_id.startswith("product_kpi:"):
        return "company_reported_product_operating_fact"
    return "company_reported_financial_fact"


def _analysis_dimension_for_fact(canonical_metric_id: str, *, row: Mapping[str, Any] | None = None) -> str:
    if canonical_metric_id.startswith("product_kpi:"):
        return "product_and_production"
    if canonical_metric_id == "financial_metric:revenue" and row is not None and _is_product_or_segment_revenue_fact(row):
        return "product_and_production"
    if canonical_metric_id in {"financial_metric:capex", "financial_metric:debt", "financial_metric:cash", "financial_metric:fcf"}:
        return "capital_and_financing"
    return "fundamentals"


def _is_product_or_segment_revenue_fact(row: Mapping[str, Any]) -> bool:
    product = _text(row.get("product_or_segment"))
    if not product:
        return False
    normalized = " ".join(product.lower().replace("—", " ").replace("-", " ").split())
    if not normalized:
        return False
    generic_or_adjustment_labels = {
        "revenue",
        "revenues",
        "total revenue",
        "total revenues",
        "net revenue",
        "net revenues",
        "total net revenue",
        "total net revenues",
        "net sales",
        "total net sales",
        "sales",
        "total sales",
        "other revenue",
        "other revenues",
        "other income",
        "accrued sales incentives and allowance",
        "sales incentives and allowance",
        "allowance",
    }
    if normalized in generic_or_adjustment_labels:
        return False
    if _revenue_label_is_adjustment_or_cost(normalized):
        return False
    geographic_only = {
        "u s",
        "us",
        "united states",
        "row",
        "rest of world",
        "international",
        "north america",
        "europe",
        "asia",
        "china",
        "japan",
    }
    if normalized in geographic_only:
        return False
    return True


def _revenue_fact_label_is_claim_card_safe(row: Mapping[str, Any]) -> bool:
    label_text = " ".join(
        _text(row.get(key))
        for key in (
            "product_or_segment",
            "metric_name",
            "row_label",
            "evidence_ref",
            "source_id",
            "fact_id",
        )
    )
    if not label_text.strip():
        return True
    normalized = " ".join(label_text.lower().replace("—", " ").replace("-", " ").replace("_", " ").split())
    if not normalized:
        return True
    return not _revenue_label_is_adjustment_or_cost(normalized)


def _revenue_label_is_adjustment_or_cost(normalized_label: str) -> bool:
    text = f" {str(normalized_label or '').lower()} "
    bad_exact = {
        "cost of revenue",
        "costs of revenue",
        "cost of revenues",
        "costs of revenues",
        "cost of sales",
        "costs of sales",
        "realized gain on sales and dividends",
        "proceeds from sales and maturities of investments",
    }
    if text.strip() in bad_exact:
        return True
    bad_phrases = (
        "proceeds from sales",
        "maturities of investments",
        "sales and maturities of investments",
        "proceeds",
        "realized gain",
        "realized loss",
        "unrealized gain",
        "unrealized loss",
        "gain on sales",
        "loss on sales",
        "dividends",
        "interest income",
        "investment income",
        "deferred",
        "receivable",
        "receivables",
        "rpo",
        "remaining performance obligation",
        "factoring",
        "letter of credit",
        "letters of credit",
        "customer financing",
        "financing receivable",
        "contract asset",
        "cost of revenue",
        "costs of revenue",
        "cost of revenues",
        "costs of revenues",
        "cost of sales",
        "costs of sales",
        "deferred revenue",
        "contract liabilities",
        "sales incentives",
        "sales allowance",
        "allowance for",
        "provision release",
        "provision release of",
        "release of $",
    )
    return any(phrase in text for phrase in bad_phrases)


def _resolved_group_memo_reject_reason(group: Mapping[str, Any], preferred: Mapping[str, Any]) -> str:
    canonical = _text(group.get("canonical_metric_id"))
    merged = {**dict(group), **dict(preferred)}
    metric_unit_reason = _metric_unit_memo_reject_reason(merged, canonical_metric=canonical)
    if metric_unit_reason:
        return metric_unit_reason
    if not _approved_fact_unit_is_claim_card_safe(merged, canonical_metric=canonical):
        return "ambiguous_currency_scale_not_memo_display_eligible"
    if canonical == "financial_metric:revenue":
        if not _revenue_fact_label_is_claim_card_safe(merged):
            return "revenue_label_not_memo_eligible"
        numeric_value = _float_or_none(preferred.get("numeric_value") or preferred.get("value"))
        if numeric_value is not None and numeric_value < 0:
            return "negative_revenue_adjustment_not_memo_eligible"
    if canonical in {"financial_metric:gross_margin", "financial_metric:gross_profit"} and not _profitability_fact_label_is_claim_card_safe(group):
        return "profitability_label_not_memo_eligible"
    return ""


def _profitability_fact_label_is_claim_card_safe(row: Mapping[str, Any]) -> bool:
    text = " ".join(
        _text(row.get(key))
        for key in (
            "product_or_segment",
            "metric_name",
            "row_label",
            "column_label",
            "group_key",
            "evidence_ref",
            "source_id",
            "fact_id",
        )
    ).lower()
    if not text:
        return True
    bad_phrases = (
        "cash flow",
        "cash_flow",
        "cash provided by",
        "cash from operations",
        "operating activities",
        "operating_activities",
        "financing activities",
        "investing activities",
        "earnings per share",
        "earnings_per_share",
        "diluted",
        "basic",
        "eps",
        "change rate",
        "change_rate",
        "total revenue change",
        "total_revenue",
        "revenue change rate",
        "cost of revenue change",
        "cost_of_revenue",
        "costs of revenue change",
        "cost of sales change",
        "period_change_rate",
        "percentage_rate",
    )
    return not any(phrase in text for phrase in bad_phrases)


def _float_or_none(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _analysis_dimension_title_for_fact(dimension: str) -> str:
    return {
        "capital_and_financing": "Capital allocation and financing",
        "fundamentals": "Fundamentals and financial quality",
        "product_and_production": "Product lines and production evidence",
    }.get(dimension, "Analyst dimension")


def _business_mechanism_for_fact(dimension: str, *, row: Mapping[str, Any] | None = None) -> str:
    economic_role = _text((row or {}).get("economic_role"))
    if economic_role == "customer_or_demand_side_capex_signal":
        return "Customer or demand-side capex can support an end-market demand-pool read-through, but it is not supplier revenue, backlog, or a direct order without a counterparty bridge."
    if economic_role == "issuer_own_capital_investment":
        return "Issuer capex shows its own reinvestment, capacity preparation, or cash-flow pressure; it should not be labeled as customer demand."
    if economic_role == "issuer_product_revenue_signal":
        return "Company-disclosed product or segment revenue connects product activity to reported financial lines, but does not by itself prove SKU share, ASP, or customer deployment."
    if economic_role == "issuer_order_backlog_signal":
        return "Company-disclosed backlog supports order visibility and demand commitment, but does not by itself prove final shipment or sell-through."
    if dimension == "capital_and_financing":
        return "Capital spending, cash generation, debt, and liquidity shape reinvestment capacity and financing risk."
    if dimension == "product_and_production":
        return "Company-disclosed product, segment, backlog, or production facts connect real business activity to reported financial lines."
    return "Reported revenue, gross margin, operating income, and cash-flow facts establish the earnings-quality baseline."


def _fact_selection_objective_text(state: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in (
        "user_query",
        "research_question",
        "query",
        "prompt",
    ):
        value = _text(state.get(key))
        if value:
            parts.append(value)
    for key in (
        "query_contract",
        "research_objective_contract",
        "research_objective",
        "evidence_requirement_plan",
    ):
        value = state.get(key)
        if isinstance(value, Mapping):
            parts.extend(_mapping_text_values(value, limit=40))
    return " ".join(parts)


def _with_fact_selection_relevance(row: Mapping[str, Any], *, objective_text: str) -> dict[str, Any]:
    enriched = _with_display_value_lineage(row)
    enriched = _with_economic_role(enriched)
    score, reasons = _fact_selection_relevance(row, objective_text=objective_text)
    enriched["selection_relevance_score"] = score
    enriched["selection_relevance_reasons"] = reasons
    return enriched


def _with_economic_role(row: Mapping[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    role = _economic_role_for_fact(enriched, canonical_metric=_text(enriched.get("canonical_metric_id")))
    enriched.update(role)
    return enriched


def _economic_role_for_fact(row: Mapping[str, Any], *, canonical_metric: str) -> dict[str, str]:
    scope_role = _text(row.get("scope_role")) or "unknown_scope"
    product = _text(row.get("product_or_segment"))
    is_peer = scope_role == "peer_context_ticker"
    is_demand_proxy = scope_role == "demand_proxy_ticker"
    if canonical_metric == "financial_metric:capex":
        if is_demand_proxy:
            return {
                "economic_role": "customer_or_demand_side_capex_signal",
                "transmission_role": "demand_pool_or_customer_infrastructure_spend_proxy",
                "memo_use_role": "Use as demand-side spending context only; do not treat as supplier revenue, supplier order, or direct purchase order.",
                "role_boundary": "capex_peer_context_not_supplier_revenue_or_order",
            }
        return {
            "economic_role": "issuer_own_capital_investment",
            "transmission_role": "supplier_or_issuer_reinvestment_capacity_and_asset_intensity",
            "memo_use_role": "Use as the issuer's own reinvestment/capacity/cash-flow pressure signal; do not call it demand-side customer spend unless an explicit customer counterparty row exists.",
            "role_boundary": "issuer_capex_not_customer_demand_without_counterparty",
        }
    if canonical_metric == "product_kpi:backlog":
        return {
            "economic_role": "issuer_order_backlog_signal",
            "transmission_role": "order_visibility_or_demand_commitment",
            "memo_use_role": "Use as issuer order/backlog visibility; do not replace customer concentration or shipment facts.",
            "role_boundary": "backlog_supports_visibility_not_full_sell_through",
        }
    if canonical_metric == "product_kpi:product_revenue":
        return {
            "economic_role": "issuer_product_revenue_signal",
            "transmission_role": "product_line_revenue_or_business_mix_bridge",
            "memo_use_role": "Use as company-disclosed product or segment revenue; bridge to margin or mix only with matching profitability/cash-flow facts.",
            "role_boundary": "product_revenue_not_sku_share_or_customer_order",
        }
    if canonical_metric == "financial_metric:gross_margin":
        return {
            "economic_role": "issuer_margin_quality_anchor",
            "transmission_role": "pricing_power_or_cost_structure_anchor",
            "memo_use_role": "Use as issuer profitability quality anchor; connect to product mix only if product facts exist.",
            "role_boundary": "margin_anchor_not_product_adoption_fact",
        }
    if canonical_metric == "financial_metric:revenue" and is_peer:
        return {
            "economic_role": "counterparty_business_context",
            "transmission_role": "counterparty_scale_or_end_market_context",
            "memo_use_role": "Use as peer/customer business context only; do not treat as focus-company supplier-side proof.",
            "role_boundary": "peer_revenue_context_not_focus_company_revenue",
        }
    if canonical_metric.startswith("financial_metric:"):
        if is_peer:
            return {
                "economic_role": "counterparty_financial_context",
                "transmission_role": "peer_or_customer_financial_context",
                "memo_use_role": "Use as context for the relevant counterparty or peer; do not transfer it to focus-company financial quality.",
                "role_boundary": "peer_financial_context_not_focus_company_fact",
            }
        return {
            "economic_role": "issuer_financial_quality_anchor",
            "transmission_role": "issuer_financial_statement_quality_or_capacity",
            "memo_use_role": "Use as focus issuer financial quality or capacity anchor.",
            "role_boundary": "issuer_financial_fact_only",
        }
    if product:
        return {
            "economic_role": "issuer_product_or_segment_context",
            "transmission_role": "product_or_segment_business_context",
            "memo_use_role": "Use as product or segment context with explicit boundary.",
            "role_boundary": "product_context_requires_matching_metric_authority",
        }
    return {
        "economic_role": "unclassified_evidence_context",
        "transmission_role": "requires_contextual_mapping_before_thesis_use",
        "memo_use_role": "Use only after Research Lead maps the fact to a company/product/counterparty role.",
        "role_boundary": "unclassified_role_not_thesis_primary",
    }


def _with_display_value_lineage(row: Mapping[str, Any]) -> dict[str, Any]:
    enriched = dict(row)
    display_value, lineage = _display_value_and_lineage(enriched)
    enriched["display_value"] = display_value
    enriched["display_value_lineage"] = lineage
    enriched["display_lineage_status"] = "pass" if display_value else "missing_display_value"
    return enriched


def _display_value_and_lineage(row: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    existing = _text(row.get("display_value") or row.get("display_value_zh"))
    raw_value = _text(row.get("value"))
    numeric_value = _float_or_none(row.get("numeric_value") or row.get("value"))
    unit = _text(row.get("unit")).lower().replace(" ", "_")
    if existing:
        return existing, _display_value_lineage(
            row,
            transform="source_supplied_display_value",
            raw_value=raw_value,
            numeric_value=numeric_value,
            unit=unit,
        )
    if numeric_value is None:
        return raw_value, _display_value_lineage(
            row,
            transform="non_numeric_value_passthrough",
            raw_value=raw_value,
            numeric_value=None,
            unit=unit,
        )
    value = _format_numeric_display_value(numeric_value, unit=unit)
    return value, _display_value_lineage(
        row,
        transform="deterministic_unit_normalization",
        raw_value=raw_value,
        numeric_value=numeric_value,
        unit=unit,
    )


def _display_value_lineage(
    row: Mapping[str, Any],
    *,
    transform: str,
    raw_value: str,
    numeric_value: float | None,
    unit: str,
) -> dict[str, Any]:
    return {
        "schema_version": DISPLAY_VALUE_LINEAGE_SCHEMA_VERSION,
        "source_value_field": "value",
        "source_numeric_field": "numeric_value",
        "raw_value": raw_value,
        "numeric_value": numeric_value,
        "unit": unit,
        "transform": transform,
        "selection_id": _text(row.get("selection_id") or row.get("derived_metric_id")),
        "fact_id": _text(row.get("fact_id") or row.get("derived_metric_id")),
        "period_key": _text(row.get("period_key")),
        "evidence_ref": _text(row.get("evidence_ref")),
    }


def _format_numeric_display_value(value: float, *, unit: str) -> str:
    unit = unit.lower().replace(" ", "_")
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    magnitude = abs_value
    suffix = ""
    if unit in {"usd_millions", "usd_million", "million_usd", "millions_usd", "$mm", "us$millions"}:
        magnitude = abs_value / 1000
        suffix = "B"
        return f"{sign}${_trim_float(magnitude)}{suffix}"
    if unit in {"usd_thousands", "usd_thousand", "thousand_usd", "thousands_usd"}:
        if abs_value >= 1_000_000:
            return f"{sign}${_trim_float(abs_value / 1_000_000)}B"
        return f"{sign}${_trim_float(abs_value / 1000)}M"
    if unit in {"usd_billions", "usd_billion", "billion_usd", "billions_usd", "$bn"}:
        return f"{sign}${_trim_float(abs_value)}B"
    if unit in {"usd", "$", "dollar", "dollars"}:
        if abs_value >= 1_000_000_000:
            return f"{sign}${_trim_float(abs_value / 1_000_000_000)}B"
        if abs_value >= 1_000_000:
            return f"{sign}${_trim_float(abs_value / 1_000_000)}M"
        if abs_value >= 1_000:
            return f"{sign}${_trim_float(abs_value / 1_000)}K"
        return f"{sign}${_trim_float(abs_value)}"
    if unit in {"%", "percent", "percentage"}:
        return f"{_trim_float(value)}%"
    if unit in {"bps", "basis_points"}:
        return f"{_trim_float(value)} bps"
    if unit in {"shares", "share", "units", "unit", "customers", "subscribers"}:
        return f"{sign}{abs_value:,.0f} {unit.replace('_', ' ')}"
    if unit:
        return f"{_trim_float(value)} {unit.replace('_', ' ')}"
    return _trim_float(value)


def _trim_float(value: float) -> str:
    if abs(value) >= 100:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:,.1f}".rstrip("0").rstrip(".")
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def _fact_selection_relevance(row: Mapping[str, Any], *, objective_text: str) -> tuple[int, list[str]]:
    canonical = _text(row.get("canonical_metric_id"))
    product = _text(row.get("product_or_segment"))
    ticker = _text(row.get("ticker")).upper()
    if not product and not canonical.startswith("product_kpi:"):
        objective_terms = _token_set(objective_text)
        if ticker and ticker.lower() in objective_terms:
            return (2, ["ticker_matches_research_objective"])
        return (0, [])

    product_terms = _expanded_product_terms(product)
    objective_terms = _token_set(objective_text)
    evidence_terms = _token_set(
        " ".join(
            [
                _text(row.get("evidence_ref")),
                _text(row.get("source_id")),
                _text(row.get("fact_id")),
                _text(row.get("canonical_metric_id")),
            ]
        )
    )
    overlap = sorted(product_terms & objective_terms)
    evidence_overlap = sorted(evidence_terms & objective_terms)
    score = 0
    reasons: list[str] = []
    if canonical == "product_kpi:product_revenue":
        score += 4
        reasons.append("company_reported_product_revenue")
    elif canonical.startswith("product_kpi:"):
        score += 2
        reasons.append("company_reported_product_kpi")
    if overlap:
        score += min(18, 6 * len(overlap))
        reasons.append("product_segment_matches_research_objective")
    if _normalized_phrase(product) and _normalized_phrase(product) in _normalized_phrase(objective_text):
        score += 12
        reasons.append("exact_product_phrase_matches_research_objective")
    if evidence_overlap:
        score += min(6, 2 * len(evidence_overlap))
        reasons.append("evidence_ref_matches_research_objective")
    if _high_signal_product_terms(product_terms) & (objective_terms | evidence_terms):
        score += 5
        reasons.append("high_signal_product_line")
    if ticker and ticker.lower() in objective_terms:
        score += 2
        reasons.append("ticker_matches_research_objective")
    return score, _dedupe_strings(reasons)


def _period_recency_score(period_key: str) -> int:
    text = _text(period_key).lower().replace(":", " ").replace("-", " ").replace("_", " ")
    year = 0
    quarter = 0
    for token in text.split():
        if len(token) == 4 and token.isdigit():
            year = max(year, int(token))
        elif len(token) == 2 and token.startswith("q") and token[1:].isdigit():
            quarter = max(quarter, int(token[1:]))
        elif token == "ttm":
            quarter = max(quarter, 6)
        elif token in {"annual", "fy", "year"}:
            quarter = max(quarter, 5)
    return year * 10 + quarter


def _normalized_phrase(value: str) -> str:
    tokens: list[str] = []
    current: list[str] = []
    for ch in str(value or "").lower():
        if ch.isalnum():
            current.append(ch)
        elif current:
            token = "".join(current)
            if len(token) >= 2 and token not in _STOPWORDS:
                tokens.append(token)
            current = []
    if current:
        token = "".join(current)
        if len(token) >= 2 and token not in _STOPWORDS:
            tokens.append(token)
    return " ".join(tokens)


def _expanded_product_terms(product: str) -> set[str]:
    text = product.lower().replace("_", " ").replace("-", " ")
    terms = _token_set(text)
    if "isg" in terms or ("infrastructure" in terms and "solutions" in terms):
        terms.update({"infrastructure", "server", "servers", "storage", "data", "center"})
    if "ai" in terms:
        terms.update({"accelerated", "accelerator", "gpu", "infrastructure", "server", "servers"})
    if "server" in terms or "servers" in terms:
        terms.update({"compute", "infrastructure"})
    if "networking" in terms:
        terms.update({"network", "infrastructure"})
    return terms


def _high_signal_product_terms(terms: set[str]) -> set[str]:
    high_signal = {
        "ai",
        "accelerated",
        "accelerator",
        "gpu",
        "server",
        "servers",
        "infrastructure",
        "network",
        "networking",
        "data",
        "center",
        "backlog",
        "cloud",
        "compute",
        "isg",
    }
    return terms & high_signal


def _scope_tickers_from_state(state: Mapping[str, Any], key: str) -> list[str]:
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    scope = query_contract.get("scope") if isinstance(query_contract.get("scope"), Mapping) else {}
    values: list[str] = []
    for candidate in (
        state.get(key),
        query_contract.get(key),
        activation.get(key),
        scope.get(key),
    ):
        values.extend(_strings(candidate))
    return _dedupe_strings([value.upper() for value in values if value])


def _demand_proxy_tickers_from_state(state: Mapping[str, Any]) -> list[str]:
    values: list[str] = []
    for key in (
        "demand_proxy_tickers",
        "customer_tickers",
        "customer_or_demand_side_tickers",
        "cloud_buyer_tickers",
        "buyer_tickers",
    ):
        values.extend(_scope_tickers_from_state(state, key))

    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    scope = query_contract.get("scope") if isinstance(query_contract.get("scope"), Mapping) else {}
    for container in (state, query_contract, activation, scope):
        if not isinstance(container, Mapping):
            continue
        for key in ("ticker_roles", "company_roles", "role_by_ticker", "ticker_role_map"):
            role_map = container.get(key)
            if not isinstance(role_map, Mapping):
                continue
            for ticker, role in role_map.items():
                role_text = " ".join(_strings(role)) if isinstance(role, (list, tuple, set)) else _text(role)
                if _is_demand_proxy_role(role_text):
                    values.append(_text(ticker).upper())
    return _dedupe_strings([value.upper() for value in values if value])


def _is_demand_proxy_role(role: str) -> bool:
    role_text = _text(role).lower().replace("-", "_").replace(" ", "_")
    if not role_text:
        return False
    markers = (
        "demand_proxy",
        "customer_proxy",
        "customer_ticker",
        "buyer_ticker",
        "cloud_buyer",
        "hyperscaler",
        "customer_capex",
        "demand_side",
        "end_market_customer",
    )
    return any(marker in role_text for marker in markers)


def _scope_role_for_ticker(
    ticker: str,
    *,
    focus_tickers: set[str],
    search_scope_tickers: set[str],
    demand_proxy_tickers: set[str] | None = None,
) -> str:
    ticker = _text(ticker).upper()
    if not ticker:
        return ""
    if ticker in focus_tickers:
        return "focus_ticker"
    if demand_proxy_tickers and ticker in demand_proxy_tickers:
        return "demand_proxy_ticker"
    if search_scope_tickers and ticker in search_scope_tickers:
        return "peer_context_ticker"
    return ""


def _token_set(value: str) -> set[str]:
    tokens: set[str] = set()
    current: list[str] = []
    for ch in str(value or "").lower():
        if ch.isalnum():
            current.append(ch)
        elif current:
            token = "".join(current)
            if len(token) >= 2 and token not in _STOPWORDS:
                tokens.add(token)
            current = []
    if current:
        token = "".join(current)
        if len(token) >= 2 and token not in _STOPWORDS:
            tokens.add(token)
    return tokens


def _mapping_text_values(value: Mapping[str, Any], *, limit: int) -> list[str]:
    skip_keys = {"focus_tickers", "search_scope_tickers", "selected_tickers", "universe_tickers", "tickers"}
    out: list[str] = []
    stack: list[Any] = [value]
    while stack and len(out) < limit:
        item = stack.pop(0)
        if isinstance(item, str):
            text = _text(item)
            if text:
                out.append(text)
        elif isinstance(item, Mapping):
            stack.extend(candidate for key, candidate in item.items() if str(key) not in skip_keys)
        elif isinstance(item, (list, tuple, set)):
            stack.extend(item)
    return out


def validate_pre_memo_fact_selection(payload: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    approved_ids = set()
    for row in payload.get("approved_facts") or []:
        if not isinstance(row, Mapping):
            continue
        fact_id = _text(row.get("fact_id"))
        if not fact_id:
            errors.append({"type": "approved_fact_id_required"})
        if fact_id in approved_ids:
            errors.append({"type": "duplicate_approved_fact_id", "fact_id": fact_id})
        approved_ids.add(fact_id)
        if _text(row.get("selection_status")) != "approved":
            errors.append({"type": "approved_fact_invalid_status", "fact_id": fact_id})
        if _numeric_value_present(row) and not _text(row.get("display_value")):
            errors.append({"type": "approved_fact_missing_display_value", "fact_id": fact_id})
        lineage = row.get("display_value_lineage") if isinstance(row.get("display_value_lineage"), Mapping) else {}
        if _numeric_value_present(row) and lineage.get("schema_version") != DISPLAY_VALUE_LINEAGE_SCHEMA_VERSION:
            errors.append({"type": "approved_fact_missing_display_value_lineage", "fact_id": fact_id})
    for row in payload.get("rejected_facts") or []:
        if not isinstance(row, Mapping):
            continue
        if not _text(row.get("reject_reason")):
            errors.append({"type": "rejected_fact_missing_reason", "selection_id": row.get("selection_id")})
    for row in payload.get("approved_derived_metrics") or []:
        if not isinstance(row, Mapping):
            continue
        if _text(row.get("gate_status")) not in {"pass", "warn"}:
            errors.append({"type": "approved_derived_metric_nonpassing_gate", "derived_metric_id": row.get("derived_metric_id")})
        if _numeric_value_present(row) and not _text(row.get("display_value")):
            errors.append({"type": "approved_derived_metric_missing_display_value", "derived_metric_id": row.get("derived_metric_id")})
        if not _strings(row.get("input_fact_ids")):
            warnings.append({"type": "approved_derived_metric_missing_input_fact_ids", "derived_metric_id": row.get("derived_metric_id")})
    return {
        "schema_version": "sec_agent_pre_memo_fact_selection_validation_v0.1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
    }


def _numeric_value_present(row: Mapping[str, Any]) -> bool:
    if _text(row.get("numeric_value")):
        return _float_or_none(row.get("numeric_value")) is not None
    return _float_or_none(row.get("value")) is not None


def _blocking_gate_index(gate_matrix: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for row in _mapping_rows(gate_matrix.get("gate_history")):
        if row.get("blocks_claim_fact_layer") and _text(row.get("status")) == "fail":
            index.setdefault(_text(row.get("target_object_id")), []).append(row)
    return index


def _candidate_index(reconciliation: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(row.get("candidate_id")): dict(row)
        for row in reconciliation.get("candidates") or []
        if isinstance(row, Mapping) and _text(row.get("candidate_id"))
    }


def _bounded_gap_links(
    typed_gap_ledger: Mapping[str, Any],
    bounded_gap_register: Mapping[str, Any],
    conflict_gap_links: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for row in _mapping_rows(typed_gap_ledger.get("gaps")):
        gap_type = _text(row.get("gap_type"))
        if gap_type in {"commercial_gap", "conflict_gap", "source_boundary_blocked", "staleness_gap", "period_gap", "unit_gap", "alias_gap"}:
            links.append(
                {
                    "gap_id": _text(row.get("gap_id")),
                    "gap_type": gap_type,
                    "ticker": _text(row.get("ticker")).upper(),
                    "metric": _text(row.get("metric")),
                    "source_layer": "typed_gap_ledger",
                    "treatment_action": _text(row.get("treatment_action")) or "expose_gap_do_not_proxy",
                }
            )
    for row in _mapping_rows(bounded_gap_register.get("gaps")):
        links.append(
            {
                "gap_id": _text(row.get("gap_id")),
                "gap_type": _text(row.get("gap_type")),
                "ticker": _text(row.get("ticker")).upper(),
                "metric": _text(row.get("metric")),
                "source_layer": "bounded_gap_register",
                "treatment_action": _text(row.get("treatment_action")) or _text(row.get("reason")) or "bounded_gap",
            }
        )
    links.extend(conflict_gap_links)
    return _dedupe_dicts([row for row in links if _text(row.get("gap_id"))])


def _mapping_rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value or [] if isinstance(row, Mapping)]


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Mapping):
        return [_text(value)] if _text(value) else []
    if isinstance(value, (list, tuple, set)):
        return [_text(item) for item in value if _text(item)]
    return [_text(value)] if _text(value) else []


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return next((_text(item) for item in value if _text(item)), "")
    return str(value or "").strip()


def _dedupe_dicts(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = _stable_id("row", row)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "|".join(str(part or "") for part in parts)
    return f"{prefix}:{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:16]}"
