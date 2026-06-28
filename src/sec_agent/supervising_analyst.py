from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from typing import Any, Mapping

from sec_agent.dimension_evidence_portfolio import (
    build_dimension_evidence_portfolio,
    compact_dimension_evidence_portfolio,
)
from sec_agent.product_intelligence_runtime import (
    compact_product_intelligence_pack_refs,
    product_intelligence_packs_from_state,
)
from sec_agent.product_intelligence_depth import compact_ai_semis_product_evidence_pack_refs


SUPERVISING_ANALYST_PACK_SCHEMA_VERSION = "sec_agent_supervising_analyst_pack_v0.1"


CAPITAL_METRIC_FAMILIES = {
    "capex",
    "capital_expenditure_proxy",
    "debt",
    "cash",
    "fcf",
    "free_cash_flow",
    "operating_cash_flow",
}
PRODUCT_METRIC_FAMILIES = {
    "product_revenue",
    "cloud_revenue",
    "data_center_revenue",
    "orders_backlog",
    "backlog",
    "shipments",
    "units",
    "capacity",
    "subscribers",
    "volume",
}
REVENUE_METRIC_FAMILIES = {"revenue", "product_revenue", "cloud_revenue", "data_center_revenue"}
HYPERSCALER_TICKERS = {"MSFT", "AMZN", "GOOGL", "META", "ORCL", "AAPL"}


def build_supervising_analyst_pack(state: Mapping[str, Any]) -> dict[str, Any]:
    """Build the pre-memo Research Lead supervision object.

    The pack is intentionally deterministic. It does not promote new facts. It
    reorganizes already-approved facts and verified claims into the analyst
    structures the writer needs: financial model, product bridge, capital graph,
    and synthesis plan.
    """

    judgment = _mapping(state.get("verified_judgment_plan") or state.get("judgment_plan"))
    fundamental_pack = _mapping(state.get("fundamental_statement_pack"))
    pre_memo = _mapping(state.get("pre_memo_fact_selection"))
    lead_checkpoint = _mapping(state.get("lead_review_checkpoint"))
    memo_logic_plan = _mapping(state.get("memo_logic_plan"))
    line_items = _collect_line_items(fundamental_pack=fundamental_pack, pre_memo=pre_memo)
    supported_claims = [dict(item) for item in _list(judgment.get("supported_claims")) if isinstance(item, Mapping)]
    gaps = _collect_gap_rows(state, judgment=judgment, fundamental_pack=fundamental_pack, pre_memo=pre_memo)
    product_intelligence_autoload = bool(state.get("product_intelligence_runtime_autoload"))
    product_intelligence_packs = product_intelligence_packs_from_state(state, autoload=product_intelligence_autoload)
    product_intelligence_ref = compact_product_intelligence_pack_refs(state, autoload=product_intelligence_autoload)
    product_evidence_depth_ref = compact_ai_semis_product_evidence_pack_refs(
        state,
        autoload=product_intelligence_autoload,
    )
    dimension_portfolio = build_dimension_evidence_portfolio(state, autoload=product_intelligence_autoload)

    financial_model = _build_financial_analysis_model(line_items, fundamental_pack=fundamental_pack, pre_memo=pre_memo)
    product_bridge = _build_product_bridge_pack(
        line_items,
        supported_claims=supported_claims,
        lead_checkpoint=lead_checkpoint,
        gaps=gaps,
        product_intelligence_packs=product_intelligence_packs,
        product_intelligence_ref=product_intelligence_ref,
        product_evidence_depth_ref=product_evidence_depth_ref,
    )
    capital_graph = _build_capital_transmission_graph(
        line_items,
        supported_claims=supported_claims,
        product_bridge=product_bridge,
    )
    synthesis_plan = _build_research_lead_synthesis_plan(
        state=state,
        financial_model=financial_model,
        product_bridge=product_bridge,
        capital_graph=capital_graph,
        judgment=judgment,
        memo_logic_plan=memo_logic_plan,
        dimension_portfolio=dimension_portfolio,
    )
    supervision_findings = _build_supervision_findings(
        financial_model=financial_model,
        product_bridge=product_bridge,
        capital_graph=capital_graph,
        gaps=gaps,
    )
    validation = _validate_pack(
        financial_model=financial_model,
        product_bridge=product_bridge,
        capital_graph=capital_graph,
        synthesis_plan=synthesis_plan,
    )
    return {
        "schema_version": SUPERVISING_ANALYST_PACK_SCHEMA_VERSION,
        "policy": "research_lead_supervises_evidence_to_thesis_before_writer_v0_1",
        "run_id": str(state.get("run_id") or ""),
        "query": _truncate(str(state.get("user_query") or ""), 360),
        "financial_analysis_model": financial_model,
        "product_bridge_pack": product_bridge,
        "capital_transmission_graph": capital_graph,
        "dimension_evidence_portfolio": dimension_portfolio,
        "dimension_evidence_portfolio_ref": compact_dimension_evidence_portfolio(dimension_portfolio, agent_id="research_lead"),
        "research_lead_synthesis_plan": synthesis_plan,
        "supervision_findings": supervision_findings,
        "writer_contract": {
            "primary_input": "research_lead_synthesis_plan",
            "supporting_inputs": [
                "financial_analysis_model",
                "product_bridge_pack",
                "capital_transmission_graph",
                "dimension_evidence_portfolio_ref",
                "verified_judgment_plan.supported_claims",
            ],
            "forbidden_surface": [
                "internal_field_labels",
                "gap_first_opening",
                "claimcard_dump",
                "driver_by_driver_listing",
                "how_to_judge_without_current_judgment",
            ],
            "gap_budget_policy": "surface gaps only after a positive or negative judgment path has been stated",
        },
        "validation": validation,
        "summary": {
            "line_item_count": len(line_items),
            "financial_metric_count": len(financial_model.get("key_line_items") or []),
            "product_kpi_count": len(product_bridge.get("company_disclosed_product_kpis") or []),
            "capital_edge_count": len(capital_graph.get("edges") or []),
            "dimension_ready_count": int((dimension_portfolio.get("status_counts") or {}).get("ready") or 0),
            "finding_count": len(supervision_findings.get("findings") or []),
            "status": "ready" if validation.get("status") == "pass" else "needs_attention",
        },
    }


def _collect_line_items(*, fundamental_pack: Mapping[str, Any], pre_memo: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in _list(fundamental_pack.get("statement_line_items")):
        if not isinstance(row, Mapping):
            continue
        item = _normalize_line_item(row, source_layer=str(row.get("source_layer") or "fundamental_statement_pack"))
        key = _line_item_key(item)
        if key in seen:
            continue
        seen.add(key)
        rows.append(item)
    for row in _list(pre_memo.get("approved_facts")):
        if not isinstance(row, Mapping):
            continue
        item = _normalize_line_item(row, source_layer=str(row.get("source_layer") or "pre_memo_fact_selection"))
        key = _line_item_key(item)
        if key in seen:
            continue
        seen.add(key)
        rows.append(item)
    rows.sort(key=_line_item_sort_key)
    return rows


def _normalize_line_item(row: Mapping[str, Any], *, source_layer: str) -> dict[str, Any]:
    canonical_metric = str(row.get("canonical_metric_id") or row.get("metric_id") or "")
    metric_family = str(row.get("metric_family") or _metric_family_from_id(canonical_metric) or "").strip()
    value = row.get("numeric_value") if row.get("numeric_value") not in (None, "") else row.get("value")
    evidence_refs = _string_list(row.get("evidence_refs"))
    evidence_ref = str(row.get("evidence_ref") or "")
    if evidence_ref and evidence_ref not in evidence_refs:
        evidence_refs.append(evidence_ref)
    line_item_id = str(
        row.get("line_item_id")
        or row.get("selection_id")
        or row.get("fact_id")
        or _stable_id("line_item", row)
    )
    return {
        "line_item_id": line_item_id,
        "source_fact_id": str(row.get("source_fact_id") or row.get("fact_id") or ""),
        "source_layer": source_layer,
        "ticker": str(row.get("ticker") or "").upper(),
        "canonical_metric_id": canonical_metric,
        "metric_family": metric_family,
        "statement_type": str(row.get("statement_type") or _statement_type_from_metric(metric_family)),
        "level1": str(row.get("level1") or ""),
        "level2": str(row.get("level2") or ""),
        "level3": str(row.get("level3") or ""),
        "analysis_role": str(row.get("analysis_role") or ""),
        "product_or_segment": str(row.get("product_or_segment") or ""),
        "product_key": str(row.get("product_key") or ""),
        "period_key": str(row.get("period_key") or ""),
        "period_role": str(row.get("period_role") or _period_role_from_key(row.get("period_key"))),
        "value": str(value or ""),
        "numeric_value": _to_float(value),
        "unit": str(row.get("unit") or ""),
        "source_family": str(row.get("source_family") or ""),
        "evidence_refs": evidence_refs[:8],
        "gate_status": str(row.get("gate_status") or row.get("selection_status") or ""),
        "claim_boundary": str(row.get("claim_boundary") or ""),
        "comparison_scope": str(row.get("comparison_scope") or ""),
    }


def _build_financial_analysis_model(
    line_items: list[dict[str, Any]],
    *,
    fundamental_pack: Mapping[str, Any],
    pre_memo: Mapping[str, Any],
) -> dict[str, Any]:
    key_rows = [_public_line_item_view(row) for row in _rank_line_items(line_items)[:24]]
    by_statement = Counter(str(row.get("statement_type") or "unknown") for row in line_items)
    by_ticker_metric: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in line_items:
        by_ticker_metric[(str(row.get("ticker") or ""), str(row.get("metric_family") or ""))].append(row)
    metric_snapshots = []
    for (ticker, metric), rows in sorted(by_ticker_metric.items()):
        if not ticker or not metric:
            continue
        selected = _select_best_row(rows)
        metric_snapshots.append(
            {
                "ticker": ticker,
                "metric_family": metric,
                "selected_value": _line_item_value_label(selected),
                "selected_period_key": str(selected.get("period_key") or ""),
                "row_count": len(rows),
                "alternate_period_keys": sorted({str(row.get("period_key") or "") for row in rows if row is not selected})[:6],
                "evidence_refs": _string_list(selected.get("evidence_refs"))[:4],
                "claim_boundary": str(selected.get("claim_boundary") or "approved_public_fact"),
            }
        )
    derived_ratios = _build_derived_ratios(line_items)
    numeric_reconciler = _build_numeric_reconciler(line_items, pre_memo=pre_memo)
    period_changes = [
        _clean_period_change(row)
        for row in _list(fundamental_pack.get("period_changes"))
        if isinstance(row, Mapping)
    ][:12]
    peer_comparisons = [
        _clean_peer_comparison(row)
        for row in _list(fundamental_pack.get("peer_comparisons"))
        if isinstance(row, Mapping)
    ][:12]
    analysis_gaps = [
        _clean_gap(row)
        for row in _list(fundamental_pack.get("analysis_gaps"))
        if isinstance(row, Mapping)
    ][:16]
    return {
        "schema_version": "sec_agent_financial_analysis_model_v0.1",
        "policy": "three_statement_and_peer_first_financial_backbone_v0_1",
        "statement_coverage": {
            "by_statement_type": dict(sorted(by_statement.items())),
            "has_income_statement": by_statement.get("income_statement", 0) > 0,
            "has_balance_sheet": by_statement.get("balance_sheet", 0) > 0,
            "has_cash_flow_statement": by_statement.get("cash_flow_statement", 0) > 0,
        },
        "industry_focus_policy": _compact_industry_focus_policy(fundamental_pack.get("industry_focus_policy")),
        "key_line_items": key_rows,
        "metric_snapshots": metric_snapshots[:24],
        "derived_ratios": derived_ratios,
        "period_changes": period_changes,
        "peer_comparisons": peer_comparisons,
        "numeric_reconciler": numeric_reconciler,
        "analysis_gaps": analysis_gaps,
        "writer_directive": (
            "Use this as the financial backbone. Discuss income statement, cash flow, and balance sheet coverage when available; "
            "when a statement is missing, say what cannot be tested without letting the memo become a gap ledger."
        ),
    }


def _build_product_bridge_pack(
    line_items: list[dict[str, Any]],
    *,
    supported_claims: list[dict[str, Any]],
    lead_checkpoint: Mapping[str, Any],
    gaps: list[dict[str, Any]],
    product_intelligence_packs: list[dict[str, Any]] | None = None,
    product_intelligence_ref: Mapping[str, Any] | None = None,
    product_evidence_depth_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    product_intelligence_packs = product_intelligence_packs or []
    product_rows = [
        row
        for row in line_items
        if _is_product_line_item(row)
    ]
    product_claims = [
        claim
        for claim in supported_claims
        if _claim_mentions_product(claim)
    ]
    company_kpis = _dedupe_product_bridge_rows(
        [*_product_intelligence_exact_kpi_views(product_intelligence_packs), *[_public_line_item_view(row) for row in _rank_line_items(product_rows)]],
        max_items=24,
    )
    official_context = []
    for claim in product_claims:
        if _claim_has_exact_numeric_fact(claim):
            continue
        official_context.append(
            {
                "claim_id": str(claim.get("claim_id") or ""),
                "ticker_scope": _string_list(claim.get("ticker_scope"))[:8],
                "products_or_platforms": _extract_product_terms_from_claim(claim),
                "claim": _truncate(str(claim.get("claim") or ""), 260),
                "source_families": _string_list(claim.get("source_families") or claim.get("source_family"))[:6],
                "evidence_refs": _string_list(claim.get("evidence_refs"))[:4],
                "claim_boundary": "context_only_unless_exact_company_reported_kpi_is_present",
            }
        )
    product_mix = _build_product_mix_rows(product_rows)
    pig_official_context = _product_intelligence_official_context(product_intelligence_packs, max_items=16)
    pig_deployment_context = _product_intelligence_deployment_context(product_intelligence_packs, max_items=16)
    pig_relationship_context = _product_intelligence_relationship_context(product_intelligence_packs, max_items=16)
    product_gaps = [
        gap
        for gap in gaps
        if _text_has_any(
            " ".join(str(gap.get(key) or "") for key in ("gap_type", "metric", "metric_id", "reason", "claim_boundary")),
            ["product", "orders", "backlog", "shipment", "unit", "capacity", "tracker", "sell-through"],
        )
    ][:16]
    product_contract = {}
    memo_directive = _mapping(lead_checkpoint.get("memo_directive"))
    if isinstance(memo_directive.get("product_output_contract"), Mapping):
        product_contract = dict(memo_directive.get("product_output_contract") or {})
    depth_ref = dict(product_evidence_depth_ref or {})
    depth_packs = [dict(item) for item in _list(depth_ref.get("packs")) if isinstance(item, Mapping)]
    depth_layer_statuses = _depth_layer_status_counts(depth_packs)
    return {
        "schema_version": "sec_agent_product_bridge_pack_v0.1",
        "policy": "product_line_evidence_must_bridge_to_financial_or_operating_judgment_v0_1",
        "product_output_contract": product_contract,
        "product_intelligence_pack_ref": dict(product_intelligence_ref or {}),
        "product_evidence_pack_ref": depth_ref,
        "company_disclosed_product_kpis": company_kpis,
        "product_mix": product_mix,
        "official_product_context": [*pig_official_context, *official_context][:24],
        "customer_deployment_context": pig_deployment_context,
        "product_relationship_context": pig_relationship_context,
        "product_gaps": product_gaps,
        "coverage": {
            "has_company_disclosed_product_kpi": bool(company_kpis),
            "has_product_mix": bool(product_mix),
            "has_product_intelligence_graph": bool(product_intelligence_packs),
            "has_technical_spec_context": bool(pig_official_context),
            "has_customer_deployment_signal": bool(pig_deployment_context),
            "has_supply_chain_signal": any(row.get("authority_type") == "supply_chain_signal" for row in pig_relationship_context),
            "has_competitive_context": any(row.get("authority_type") == "competitive_context_candidate" for row in pig_relationship_context),
            "has_official_context_without_exact_kpi": bool(official_context or pig_official_context),
            "has_product_evidence_pack": bool(depth_packs),
            "product_evidence_depth_status_counts": dict(Counter(str(item.get("depth_status") or "") for item in depth_packs)),
            "product_evidence_layer_status_counts": depth_layer_statuses,
            "gap_count": len(product_gaps),
        },
        "writer_directive": (
            "Use ProductEvidencePack first to separate product profile, specs/architecture, customer deployment/adoption, "
            "performance proxy, exact Product-KPI, and relationship graph. Anchor exact financial/operating claims on "
            "company-disclosed product KPI rows. Use specs, deployments, channel, ecosystem, and relationship rows as "
            "bounded thesis-driver evidence only."
        ),
    }


def _depth_layer_status_counts(depth_packs: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, Counter] = defaultdict(Counter)
    for pack in depth_packs:
        statuses = pack.get("layer_statuses") if isinstance(pack.get("layer_statuses"), Mapping) else {}
        for layer_id, status in statuses.items():
            counts[str(layer_id)][str(status or "")] += 1
    return {key: dict(sorted(value.items())) for key, value in sorted(counts.items())}


def _product_intelligence_exact_kpi_views(packs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pack in packs:
        for item in [*_list(pack.get("representative_exact_kpis")), *_list(pack.get("representative_operating_metrics"))]:
            if not isinstance(item, Mapping):
                continue
            metric_family = str(item.get("metric_name") or _metric_family_from_id(str(item.get("fact_type") or "")) or "")
            rows.append(
                {
                    "line_item_id": str(item.get("source_row_id") or item.get("gold_row_id") or _stable_id("pig_kpi", item)),
                    "ticker": str(item.get("ticker") or pack.get("ticker") or ""),
                    "metric_family": metric_family,
                    "canonical_metric_id": str(item.get("fact_type") or metric_family),
                    "statement_type": "product_or_operating_metric",
                    "product_or_segment": str(item.get("product_or_segment") or item.get("product_family") or ""),
                    "period_key": str(item.get("period") or ""),
                    "value": f"{item.get('value') or ''} {item.get('unit') or ''}".strip(),
                    "raw_value": str(item.get("value") or ""),
                    "unit": str(item.get("unit") or ""),
                    "source_family": "company_product_evidence_graph",
                    "evidence_refs": [str(item.get("source_row_id") or item.get("gold_row_id") or "")],
                    "claim_boundary": str(
                        item.get("claim_boundary")
                        or "ProductIntelligenceGraph exact product/business-line row; no market share, sell-through, channel inventory, undisclosed SKU economics, or commercial tracker authority."
                    ),
                }
            )
    return rows


def _product_intelligence_official_context(packs: list[dict[str, Any]], *, max_items: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pack in packs:
        ticker = str(pack.get("ticker") or "")
        for item in [*_list(pack.get("representative_product_slots")), *_list(pack.get("representative_product_profile_or_specs"))]:
            if not isinstance(item, Mapping):
                continue
            source_id = str(item.get("source_row_id") or item.get("product_slot_id") or item.get("gold_row_id") or _stable_id("pig_product_context", item))
            rows.append(
                {
                    "context_id": source_id,
                    "ticker": str(item.get("ticker") or ticker),
                    "product_family": str(item.get("product_family") or item.get("family_name") or ""),
                    "products_or_platforms": [
                        value
                        for value in (
                            str(item.get("product_or_segment") or ""),
                            str(item.get("product_slot_name") or ""),
                            str(item.get("metric_name") or ""),
                        )
                        if value
                    ][:4],
                    "source_layer": str(item.get("source_layer") or ""),
                    "source_role": str(item.get("source_role") or "official_product_profile_spec"),
                    "citation_url": str(item.get("citation_url") or ""),
                    "evidence_refs": [source_id],
                    "claim_boundary": str(item.get("claim_boundary") or "official product context only; no sales/share/ASP/order-value authority"),
                }
            )
    return _dedupe_product_bridge_rows(rows, max_items=max_items)


def _product_intelligence_deployment_context(packs: list[dict[str, Any]], *, max_items: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pack in packs:
        ticker = str(pack.get("ticker") or "")
        for item in _list(pack.get("representative_deployment_rows")):
            if not isinstance(item, Mapping):
                continue
            source_id = str(item.get("source_row_id") or item.get("gold_row_id") or _stable_id("pig_deployment", item))
            rows.append(
                {
                    "deployment_context_id": source_id,
                    "ticker": str(item.get("ticker") or ticker),
                    "product_or_segment": str(item.get("product_or_segment") or item.get("product_family") or ""),
                    "counterparty": str(item.get("counterparty") or item.get("customer") or item.get("recipient") or ""),
                    "signal": str(item.get("metric_name") or item.get("fact_type") or item.get("value") or ""),
                    "period": str(item.get("period") or ""),
                    "citation_url": str(item.get("citation_url") or ""),
                    "evidence_refs": [source_id],
                    "claim_boundary": str(item.get("claim_boundary") or "official deployment/order context only; no order-value, backlog, revenue, or sales authority"),
                }
            )
    return _dedupe_product_bridge_rows(rows, max_items=max_items)


def _product_intelligence_relationship_context(packs: list[dict[str, Any]], *, max_items: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pack in packs:
        ticker = str(pack.get("ticker") or "")
        for item in _list(pack.get("representative_relationship_edges")):
            if not isinstance(item, Mapping) or not bool(item.get("can_enter_evidence_bundle")):
                continue
            authority = str(item.get("authority_type") or "")
            if authority not in {"competitive_context_candidate", "supply_chain_signal", "deployment_signal_authority", "channel_presence_signal"}:
                continue
            edge_id = str(item.get("edge_id") or _stable_id("pig_relationship", item))
            rows.append(
                {
                    "relationship_context_id": edge_id,
                    "ticker": ticker,
                    "authority_type": authority,
                    "edge_type": str(item.get("edge_type") or ""),
                    "from_node_id": str(item.get("from_node_id") or ""),
                    "to_node_id": str(item.get("to_node_id") or ""),
                    "evidence_refs": [edge_id],
                    "claim_boundary": str(item.get("claim_boundary") or "relationship context only; no sales/share/shipment/order-value authority"),
                }
            )
    return _dedupe_product_bridge_rows(rows, max_items=max_items)


def _dedupe_product_bridge_rows(rows: list[dict[str, Any]], *, max_items: int) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = "|".join(
            str(row.get(field) or "")
            for field in (
                "line_item_id",
                "context_id",
                "deployment_context_id",
                "relationship_context_id",
                "ticker",
                "product_or_segment",
                "period_key",
            )
        )
        if not key.strip("|"):
            key = _stable_id("product_bridge_row", row)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
        if len(deduped) >= max_items:
            break
    return deduped


def _build_capital_transmission_graph(
    line_items: list[dict[str, Any]],
    *,
    supported_claims: list[dict[str, Any]],
    product_bridge: Mapping[str, Any],
) -> dict[str, Any]:
    edges: list[dict[str, Any]] = []
    for row in line_items:
        ticker = str(row.get("ticker") or "")
        metric = str(row.get("metric_family") or "")
        if metric in {"capex", "capital_expenditure_proxy"} and ticker in HYPERSCALER_TICKERS:
            edges.append(
                _edge(
                    source=ticker,
                    target="AI infrastructure demand pool",
                    edge_type="buyer_capex_demand_signal",
                    direction="positive_demand_signal",
                    strength=_strength_from_amount(row, high=20000, medium=5000),
                    evidence_refs=_string_list(row.get("evidence_refs")),
                    claim_boundary="capex supports buyer demand intensity, not supplier revenue attribution",
                    proves="capital spending intensity",
                    row=row,
                )
            )
        if metric in {"capex", "capital_expenditure_proxy"} and ticker not in HYPERSCALER_TICKERS:
            edges.append(
                _edge(
                    source=ticker,
                    target=f"{ticker} capacity investment",
                    edge_type="supplier_own_capex_capacity_proxy",
                    direction="capacity_proxy",
                    strength=_strength_from_amount(row, high=1000, medium=100),
                    evidence_refs=_string_list(row.get("evidence_refs")),
                    claim_boundary="supplier capex is own investment, not direct customer order evidence",
                    proves="supplier reinvestment scale",
                    row=row,
                )
            )
        if metric in REVENUE_METRIC_FAMILIES and _is_product_line_item(row):
            target = f"{ticker} {row.get('product_or_segment') or metric}".strip()
            edges.append(
                _edge(
                    source="AI infrastructure demand pool",
                    target=target,
                    edge_type="supplier_product_revenue_readthrough",
                    direction="demand_to_supplier_revenue_readthrough",
                    strength=_strength_from_amount(row, high=10000, medium=1000),
                    evidence_refs=_string_list(row.get("evidence_refs")),
                    claim_boundary="company disclosed product revenue supports readthrough, not customer-specific attribution",
                    proves="supplier product revenue exposure",
                    row=row,
                )
            )
    for claim in supported_claims:
        claim_type = str(claim.get("claim_type") or claim.get("raw_claim_type") or "")
        if "relationship" not in claim_type and "supply" not in str(claim.get("memo_slot") or ""):
            continue
        tickers = _string_list(claim.get("ticker_scope"))[:8]
        if len(tickers) < 2:
            continue
        edges.append(
            {
                "edge_id": _stable_id("capital_edge", claim),
                "source": tickers[0],
                "target": " / ".join(tickers[1:4]),
                "edge_type": "relationship_hypothesis_only",
                "direction": "scope_or_hypothesis",
                "strength": "low",
                "evidence_refs": _string_list(claim.get("evidence_refs"))[:6],
                "claim_ids": [str(claim.get("claim_id") or "")],
                "claim_boundary": "relationship graph supports universe/scope, not confirmed revenue transmission",
                "proves": "relationship research scope",
            }
        )
    deduped = _dedupe_edges(edges)
    return {
        "schema_version": "sec_agent_capital_transmission_graph_v0.1",
        "policy": "directed_edges_separate_reported_spend_product_revenue_and_hypothesis_v0_1",
        "nodes": _graph_nodes(deduped),
        "edges": deduped[:32],
        "edge_counts_by_type": dict(Counter(str(edge.get("edge_type") or "") for edge in deduped)),
        "relationship_boundary": {
            "reported_spend": "can support buyer demand intensity",
            "reported_product_revenue": "can support supplier readthrough",
            "relationship_hypothesis": "can guide research scope only",
            "commercial_gap": "customer-specific orders/share usually require commercial tracker or company disclosure",
        },
        "writer_directive": (
            "Describe the transmission path as a directed chain: who is spending, which product or supplier line shows readthrough, "
            "and where the customer-specific link is still unproven."
        ),
    }


def _build_research_lead_synthesis_plan(
    *,
    state: Mapping[str, Any],
    financial_model: Mapping[str, Any],
    product_bridge: Mapping[str, Any],
    capital_graph: Mapping[str, Any],
    judgment: Mapping[str, Any],
    memo_logic_plan: Mapping[str, Any],
    dimension_portfolio: Mapping[str, Any],
) -> dict[str, Any]:
    user_query = str(state.get("user_query") or "")
    product_kpis = _list(product_bridge.get("company_disclosed_product_kpis"))
    product_context = _list(product_bridge.get("official_product_context"))
    capital_edges = _list(capital_graph.get("edges"))
    line_items = _list(financial_model.get("key_line_items"))
    thesis_claim = _primary_thesis_claim(judgment)
    if product_kpis and capital_edges:
        core = (
            "The strongest public-evidence judgment is a qualified readthrough: reported buyer capex or sector demand signals are "
            "visible, and at least one company-disclosed product KPI shows supplier-side exposure, but customer-specific attribution "
            "still needs direct company disclosure or a commercial tracker."
        )
    elif line_items:
        core = (
            "The strongest public-evidence judgment is financial-backbone first: use approved statement and product rows to explain "
            "business momentum, then keep any market-share, sell-through, or direct customer attribution as an explicit boundary."
        )
    elif product_context:
        core = (
            "The strongest public-evidence judgment is taxonomy-only: official product context can name the business lines, but it "
            "does not yet prove product revenue, orders, share, or customer demand."
        )
    else:
        core = "The public evidence is not sufficient for a thesis-led memo; expose the missing retrievable routes before writing."
    if thesis_claim:
        core = _truncate(f"{core} Primary verified thesis card: {thesis_claim}", 620)

    return {
        "schema_version": "sec_agent_research_lead_synthesis_plan_v0.1",
        "plan_id": _stable_id("research_lead_synthesis_plan", {"query": user_query, "core": core}),
        "core_judgment": core,
        "stance": _stance_from_plan(core, judgment),
        "dimension_evidence_portfolio_ref": compact_dimension_evidence_portfolio(dimension_portfolio, agent_id="research_lead"),
        "argument_order": [
            {
                "dimension_id": "fundamentals",
                "purpose": "Start from approved financial line items, peer comparisons, period changes, and statement coverage.",
                "input_refs": ["financial_analysis_model.key_line_items", "financial_analysis_model.peer_comparisons"],
            },
            {
                "dimension_id": "product_and_production",
                "purpose": "Bridge product or segment KPIs to revenue, backlog, capacity, or mix before using product context.",
                "input_refs": ["product_bridge_pack.company_disclosed_product_kpis", "product_bridge_pack.product_mix"],
            },
            {
                "dimension_id": "capital_transmission",
                "purpose": "Turn capex, supplier product revenue, and relationship hypotheses into a directed transmission chain.",
                "input_refs": ["capital_transmission_graph.edges"],
            },
            {
                "dimension_id": "risk_and_counterevidence",
                "purpose": "State what would break the thesis, including numeric conflicts, missing direct attribution, and commercial tracker gaps.",
                "input_refs": ["financial_analysis_model.numeric_reconciler", "product_bridge_pack.product_gaps"],
            },
        ],
        "proven": _proven_points(financial_model, product_bridge, capital_graph),
        "supported_inference": _supported_inferences(financial_model, product_bridge, capital_graph),
        "not_proven": _not_proven_points(financial_model, product_bridge, capital_graph),
        "writer_directives": [
            "Open with the current judgment and the evidence transmission path; do not open with gaps.",
            "Investment implications must be the agent's present judgment, not a checklist for the user.",
            "Use a dimension-led narrative: fundamentals, product/product line, capital or supply-chain transmission, risks.",
            "Use gaps as decision boundaries after the main argument, not as the dominant body text.",
            "When graph edges are low-confidence relationship hypotheses, label them as research scope rather than proof.",
        ],
        "memo_logic_plan_alignment": {
            "memo_logic_plan_id": str(memo_logic_plan.get("plan_id") or ""),
            "section_order": _string_list(memo_logic_plan.get("section_order"))[:12],
            "override_policy": "research_lead_synthesis_plan_is_primary_writer_order_when_present",
        },
    }


def _build_supervision_findings(
    *,
    financial_model: Mapping[str, Any],
    product_bridge: Mapping[str, Any],
    capital_graph: Mapping[str, Any],
    gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    findings = []
    coverage = _mapping(financial_model.get("statement_coverage"))
    if not coverage.get("has_income_statement"):
        findings.append(_finding("financial_statement_gap", "No income statement line item reached the memo backbone.", "fundamental_specialist"))
    if not coverage.get("has_cash_flow_statement"):
        findings.append(_finding("financial_statement_gap", "No cash flow statement line item reached the memo backbone.", "fundamental_specialist"))
    if not coverage.get("has_balance_sheet"):
        findings.append(_finding("financial_statement_gap", "No balance sheet line item reached the memo backbone.", "fundamental_specialist"))
    if not product_bridge.get("company_disclosed_product_kpis"):
        findings.append(
            _finding(
                "product_bridge_gap",
                "Product section has no company-disclosed product KPI; product pages or official context can enrich taxonomy only.",
                "product_technology_specialist",
            )
        )
    edge_counts = _mapping(capital_graph.get("edge_counts_by_type"))
    if not edge_counts.get("supplier_product_revenue_readthrough"):
        findings.append(
            _finding(
                "transmission_graph_gap",
                "Capital graph has no supplier product-revenue readthrough edge; capex and relationship rows cannot prove supplier revenue.",
                "industry_supply_chain_specialist",
            )
        )
    numeric = _mapping(financial_model.get("numeric_reconciler"))
    if numeric.get("attention_required_count"):
        findings.append(
            _finding(
                "numeric_reconciler_required",
                "Multiple periods, units, or blocked candidate groups need a display choice before writing a single headline number.",
                "fundamental_specialist",
            )
        )
    if gaps:
        findings.append(
            _finding(
                "bounded_gap_budget",
                f"{len(gaps)} gap rows remain; writer should surface only decision-changing gaps.",
                "research_lead",
            )
        )
    return {
        "schema_version": "sec_agent_supervision_findings_v0.1",
        "findings": findings,
        "required_followups": _required_followups_from_findings(findings),
    }


def _validate_pack(
    *,
    financial_model: Mapping[str, Any],
    product_bridge: Mapping[str, Any],
    capital_graph: Mapping[str, Any],
    synthesis_plan: Mapping[str, Any],
) -> dict[str, Any]:
    errors = []
    warnings = []
    if not synthesis_plan.get("core_judgment"):
        errors.append({"type": "missing_core_judgment"})
    if not financial_model.get("key_line_items"):
        warnings.append({"type": "financial_model_empty"})
    if not product_bridge.get("company_disclosed_product_kpis") and not product_bridge.get("official_product_context"):
        warnings.append({"type": "product_bridge_empty"})
    if not capital_graph.get("edges"):
        warnings.append({"type": "capital_graph_empty"})
    return {
        "schema_version": "sec_agent_supervising_analyst_pack_validation_v0.1",
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
    }


def _build_derived_ratios(line_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ratios = []
    by_ticker = defaultdict(list)
    for row in line_items:
        by_ticker[str(row.get("ticker") or "")].append(row)
    for ticker, rows in sorted(by_ticker.items()):
        if not ticker:
            continue
        revenue_rows = [row for row in rows if str(row.get("metric_family") or "") in REVENUE_METRIC_FAMILIES]
        capex_rows = [row for row in rows if str(row.get("metric_family") or "") in {"capex", "capital_expenditure_proxy"}]
        for capex in capex_rows[:3]:
            revenue = _best_comparable_denominator(capex, revenue_rows)
            if not revenue:
                continue
            ratio = _ratio_from_rows(capex, revenue, absolute_numerator=True)
            if ratio is None:
                continue
            ratios.append(
                {
                    "ratio_id": _stable_id("derived_ratio", {"n": capex.get("line_item_id"), "d": revenue.get("line_item_id")}),
                    "ticker": ticker,
                    "ratio_name": "capex_to_revenue",
                    "numerator": _line_item_value_label(capex),
                    "denominator": _line_item_value_label(revenue),
                    "value": round(ratio, 4),
                    "display_value": f"{ratio * 100:.1f}%",
                    "evidence_refs": _string_list(capex.get("evidence_refs"))[:2] + _string_list(revenue.get("evidence_refs"))[:2],
                    "claim_boundary": "derived_from_same_ticker_public_rows_not_a_management_disclosed_metric",
                }
            )
        product_revenue_rows = [
            row
            for row in revenue_rows
            if str(row.get("product_or_segment") or "") and str(row.get("metric_family") or "") in REVENUE_METRIC_FAMILIES
        ]
        total_candidates = [row for row in product_revenue_rows if _segment_looks_total(str(row.get("product_or_segment") or ""))]
        for total in total_candidates[:2]:
            for child in product_revenue_rows:
                if child is total or _segment_looks_total(str(child.get("product_or_segment") or "")):
                    continue
                ratio = _ratio_from_rows(child, total)
                if ratio is None or ratio > 1.5:
                    continue
                ratios.append(
                    {
                        "ratio_id": _stable_id("derived_ratio", {"n": child.get("line_item_id"), "d": total.get("line_item_id")}),
                        "ticker": ticker,
                        "ratio_name": "product_revenue_mix",
                        "numerator": _line_item_value_label(child),
                        "denominator": _line_item_value_label(total),
                        "value": round(ratio, 4),
                        "display_value": f"{ratio * 100:.1f}%",
                        "evidence_refs": _string_list(child.get("evidence_refs"))[:2] + _string_list(total.get("evidence_refs"))[:2],
                        "claim_boundary": "mix_derived_from_company_disclosed_product_rows_same_ticker",
                    }
                )
    return ratios[:24]


def _build_product_mix_rows(product_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ratios = [
        row
        for row in _build_derived_ratios(product_rows)
        if str(row.get("ratio_name") or "") == "product_revenue_mix"
    ]
    return ratios[:16]


def _build_numeric_reconciler(line_items: list[dict[str, Any]], *, pre_memo: Mapping[str, Any]) -> dict[str, Any]:
    groups = defaultdict(list)
    for row in line_items:
        groups[(str(row.get("ticker") or ""), str(row.get("metric_family") or ""), str(row.get("product_or_segment") or ""))].append(row)
    attention = []
    for (ticker, metric, product), rows in sorted(groups.items()):
        period_keys = sorted({str(row.get("period_key") or "") for row in rows if str(row.get("period_key") or "")})
        units = sorted({str(row.get("unit") or "") for row in rows if str(row.get("unit") or "")})
        if len(period_keys) <= 1 and len(units) <= 1:
            continue
        selected = _select_best_row(rows)
        attention.append(
            {
                "reconciler_id": _stable_id("numeric_reconciler", {"ticker": ticker, "metric": metric, "product": product}),
                "ticker": ticker,
                "metric_family": metric,
                "product_or_segment": product,
                "selected_for_display": _line_item_value_label(selected),
                "selection_reason": "prefer_qtd_or_ytd_then_ttm_with_exact_authority",
                "alternate_period_keys": period_keys[:8],
                "units": units[:6],
                "row_count": len(rows),
                "claim_boundary": "do_not_average_mixed_period_or_unit_rows",
            }
        )
    rejected = [
        row
        for row in _list(pre_memo.get("rejected_facts"))
        if isinstance(row, Mapping)
    ]
    blocked = []
    for row in rejected[:16]:
        blocked.append(
            {
                "selection_id": str(row.get("selection_id") or ""),
                "ticker": str(row.get("ticker") or "").upper(),
                "canonical_metric_id": str(row.get("canonical_metric_id") or ""),
                "product_or_segment": str(row.get("product_or_segment") or ""),
                "period_key": str(row.get("period_key") or ""),
                "reject_reason": str(row.get("reject_reason") or ""),
                "conflict_types": _string_list(row.get("conflict_types"))[:6],
                "claim_boundary": str(row.get("claim_boundary") or "not_memo_eligible"),
            }
        )
    return {
        "schema_version": "sec_agent_numeric_display_reconciler_v0.1",
        "attention_required": attention[:16],
        "attention_required_count": len(attention),
        "blocked_fact_examples": blocked,
        "blocked_fact_count": len(rejected),
        "writer_directive": "Use selected_for_display when a metric has multiple periods or units; never average blocked or mixed-period rows.",
    }


def _proven_points(
    financial_model: Mapping[str, Any],
    product_bridge: Mapping[str, Any],
    capital_graph: Mapping[str, Any],
) -> list[str]:
    points = []
    if financial_model.get("key_line_items"):
        points.append("Approved public financial/product rows provide the numeric backbone.")
    if product_bridge.get("company_disclosed_product_kpis"):
        points.append("At least one company-disclosed product KPI can support product-to-financial bridge.")
    edge_counts = _mapping(capital_graph.get("edge_counts_by_type"))
    if edge_counts.get("buyer_capex_demand_signal"):
        points.append("Buyer capex rows can support infrastructure demand intensity.")
    if edge_counts.get("supplier_product_revenue_readthrough"):
        points.append("Supplier product revenue rows can support supplier-side readthrough.")
    return points[:8]


def _supported_inferences(
    financial_model: Mapping[str, Any],
    product_bridge: Mapping[str, Any],
    capital_graph: Mapping[str, Any],
) -> list[str]:
    inferences = []
    if product_bridge.get("product_mix"):
        inferences.append("Product mix ratios can help explain which product line carries the financial signal.")
    if capital_graph.get("edges"):
        inferences.append("Directed graph edges can explain a demand-to-supplier transmission path with explicit confidence.")
    if financial_model.get("peer_comparisons"):
        inferences.append("Peer comparisons can frame relative intensity when period/unit gates match.")
    return inferences[:8]


def _not_proven_points(
    financial_model: Mapping[str, Any],
    product_bridge: Mapping[str, Any],
    capital_graph: Mapping[str, Any],
) -> list[str]:
    missing = []
    coverage = _mapping(financial_model.get("statement_coverage"))
    if not coverage.get("has_balance_sheet"):
        missing.append("Balance-sheet effects are not testable from the current approved rows.")
    if product_bridge.get("official_product_context") and not product_bridge.get("company_disclosed_product_kpis"):
        missing.append("Official product context does not prove product revenue, order volume, or market share.")
    edge_counts = _mapping(capital_graph.get("edge_counts_by_type"))
    if edge_counts.get("relationship_hypothesis_only") and not edge_counts.get("supplier_product_revenue_readthrough"):
        missing.append("Relationship graph rows do not prove direct customer/supplier revenue attribution.")
    numeric = _mapping(financial_model.get("numeric_reconciler"))
    if numeric.get("blocked_fact_count"):
        missing.append("Blocked facts remain unavailable for memo promotion until the parser/schema gate is fixed.")
    return missing[:8]


def _primary_thesis_claim(judgment: Mapping[str, Any]) -> str:
    for claim in _list(judgment.get("supported_claims")):
        if not isinstance(claim, Mapping):
            continue
        if str(claim.get("memo_slot") or "") == "thesis" or "thesis" in str(claim.get("claim_type") or ""):
            return _truncate(str(claim.get("claim") or ""), 260)
    return ""


def _stance_from_plan(core: str, judgment: Mapping[str, Any]) -> str:
    text = " ".join([core, str(judgment.get("status") or "")]).lower()
    if any(term in text for term in ["qualified", "mixed", "boundary", "not prove", "unproven"]):
        return "qualified_positive_or_mixed"
    if "not sufficient" in text:
        return "insufficient_public_evidence"
    if "positive" in text:
        return "positive"
    if "negative" in text:
        return "negative"
    return "bounded_judgment"


def _rank_line_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=_line_item_rank_key)


def _line_item_rank_key(row: Mapping[str, Any]) -> tuple[int, int, str, str]:
    metric = str(row.get("metric_family") or "")
    score = 0
    if metric in {"revenue", "product_revenue", "cloud_revenue", "data_center_revenue"}:
        score -= 50
    if metric in {"capex", "capital_expenditure_proxy"}:
        score -= 45
    if metric in {"gross_margin", "operating_margin", "fcf", "free_cash_flow", "operating_cash_flow"}:
        score -= 35
    if str(row.get("product_or_segment") or ""):
        score -= 20
    if str(row.get("source_family") or "") in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}:
        score -= 15
    period_score = {"qtd": 0, "ytd": 1, "ttm": 2, "instant": 3, "": 4}.get(str(row.get("period_role") or ""), 5)
    return (score, period_score, str(row.get("ticker") or ""), str(row.get("line_item_id") or ""))


def _select_best_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ranked = _rank_line_items(rows)
    return ranked[0] if ranked else {}


def _line_item_sort_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("ticker") or ""),
        str(row.get("metric_family") or ""),
        str(row.get("period_key") or ""),
        str(row.get("product_or_segment") or ""),
    )


def _line_item_key(row: Mapping[str, Any]) -> str:
    key_parts = [
        str(row.get("source_fact_id") or ""),
        str(row.get("line_item_id") or ""),
        str(row.get("ticker") or ""),
        str(row.get("metric_family") or ""),
        str(row.get("product_or_segment") or ""),
        str(row.get("period_key") or ""),
        str(row.get("value") or ""),
        str(row.get("unit") or ""),
    ]
    return "|".join(key_parts)


def _public_line_item_view(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "line_item_id": str(row.get("line_item_id") or ""),
        "ticker": str(row.get("ticker") or ""),
        "metric_family": str(row.get("metric_family") or ""),
        "canonical_metric_id": str(row.get("canonical_metric_id") or ""),
        "statement_type": str(row.get("statement_type") or ""),
        "product_or_segment": str(row.get("product_or_segment") or ""),
        "period_key": str(row.get("period_key") or ""),
        "value": _line_item_value_label(row),
        "raw_value": str(row.get("value") or ""),
        "unit": str(row.get("unit") or ""),
        "source_family": str(row.get("source_family") or ""),
        "evidence_refs": _string_list(row.get("evidence_refs"))[:4],
        "claim_boundary": str(row.get("claim_boundary") or "approved_public_fact"),
    }


def _line_item_value_label(row: Mapping[str, Any]) -> str:
    value = str(row.get("value") or "")
    unit = str(row.get("unit") or "")
    if not value:
        return ""
    return f"{value} {unit}".strip()


def _clean_period_change(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "change_id": str(row.get("change_id") or ""),
        "ticker": str(row.get("ticker") or ""),
        "canonical_metric_id": str(row.get("canonical_metric_id") or ""),
        "current_period_key": str(row.get("current_period_key") or ""),
        "prior_period_key": str(row.get("prior_period_key") or ""),
        "absolute_change": str(row.get("absolute_change") or ""),
        "pct_change": str(row.get("pct_change") or ""),
        "unit": str(row.get("unit") or ""),
        "evidence_refs": _string_list(row.get("evidence_refs"))[:4],
        "claim_boundary": str(row.get("claim_boundary") or ""),
    }


def _clean_peer_comparison(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "comparison_id": str(row.get("comparison_id") or ""),
        "ticker": str(row.get("ticker") or ""),
        "canonical_metric_id": str(row.get("canonical_metric_id") or ""),
        "period_key": str(row.get("period_key") or ""),
        "focus_value": str(row.get("focus_value") or ""),
        "peer_average": str(row.get("peer_average") or ""),
        "rank_within_scope": row.get("rank_within_scope"),
        "scope_count": row.get("scope_count"),
        "peer_values": [
            {
                "ticker": str(peer.get("ticker") or ""),
                "value": str(peer.get("value") or ""),
                "unit": str(peer.get("unit") or ""),
                "evidence_refs": _string_list(peer.get("evidence_refs"))[:2],
            }
            for peer in _list(row.get("peer_values"))
            if isinstance(peer, Mapping)
        ][:8],
        "unit": str(row.get("unit") or ""),
        "evidence_refs": _string_list(row.get("evidence_refs"))[:4],
        "claim_boundary": str(row.get("claim_boundary") or ""),
    }


def _clean_gap(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "gap_id": str(row.get("gap_id") or row.get("selection_id") or ""),
        "gap_type": str(row.get("gap_type") or row.get("reject_reason") or ""),
        "ticker": str(row.get("ticker") or ""),
        "metric_id": str(row.get("metric_id") or row.get("canonical_metric_id") or row.get("metric") or ""),
        "reason": _truncate(str(row.get("reason") or row.get("reject_reason") or ""), 220),
        "claim_boundary": str(row.get("claim_boundary") or ""),
    }


def _collect_gap_rows(
    state: Mapping[str, Any],
    *,
    judgment: Mapping[str, Any],
    fundamental_pack: Mapping[str, Any],
    pre_memo: Mapping[str, Any],
) -> list[dict[str, Any]]:
    gaps = []
    for row in _list(fundamental_pack.get("analysis_gaps")):
        if isinstance(row, Mapping):
            gaps.append(_clean_gap(row))
    for row in _list(pre_memo.get("rejected_facts")):
        if isinstance(row, Mapping):
            gaps.append(_clean_gap(row))
    for row in _list(state.get("source_gaps")):
        if isinstance(row, Mapping):
            gaps.append(_clean_gap(row))
    for claim in _list(judgment.get("supported_claims")):
        if not isinstance(claim, Mapping):
            continue
        for missing in _string_list(claim.get("missing_confirmations")):
            gaps.append(
                {
                    "gap_id": _stable_id("claim_missing_confirmation", {"claim": claim.get("claim_id"), "missing": missing}),
                    "gap_type": "missing_confirmation",
                    "ticker": ",".join(_string_list(claim.get("ticker_scope"))[:6]),
                    "metric_id": ",".join(_string_list(claim.get("metric_scope"))[:6]),
                    "reason": _truncate(missing, 220),
                    "claim_boundary": "missing_confirmation_from_verified_claim",
                }
            )
    deduped = []
    seen = set()
    for gap in gaps:
        key = "|".join(str(gap.get(k) or "") for k in ("gap_type", "ticker", "metric_id", "reason"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(gap)
    return deduped


def _compact_industry_focus_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "industry_id": str(value.get("industry_id") or ""),
        "priority_metrics": _string_list(value.get("priority_metrics"))[:12],
        "statement_weights": dict(value.get("statement_weights") or {}) if isinstance(value.get("statement_weights"), Mapping) else {},
        "analysis_questions": _string_list(value.get("analysis_questions"))[:6],
        "commercial_tracker_boundary": _truncate(str(value.get("commercial_tracker_boundary") or ""), 260),
    }


def _best_comparable_denominator(numerator: Mapping[str, Any], denominators: list[dict[str, Any]]) -> dict[str, Any] | None:
    ticker = str(numerator.get("ticker") or "")
    period_role = str(numerator.get("period_role") or "")
    same_ticker = [row for row in denominators if str(row.get("ticker") or "") == ticker]
    if not same_ticker:
        return None
    same_period_role = [row for row in same_ticker if str(row.get("period_role") or "") == period_role]
    if same_period_role:
        return _select_best_row(same_period_role)
    return _select_best_row(same_ticker)


def _ratio_from_rows(numerator: Mapping[str, Any], denominator: Mapping[str, Any], *, absolute_numerator: bool = False) -> float | None:
    n = _scaled_numeric_value(numerator)
    d = _scaled_numeric_value(denominator)
    if n is None or d in (None, 0):
        return None
    if absolute_numerator:
        n = abs(n)
    return n / d


def _scaled_numeric_value(row: Mapping[str, Any]) -> float | None:
    value = row.get("numeric_value")
    if value is None:
        value = _to_float(row.get("value"))
    if value is None:
        return None
    unit = str(row.get("unit") or "").lower()
    scale = 1.0
    if unit in {"usd_billions", "billions", "billion", "usd_billion"}:
        scale = 1000.0
    elif unit in {"usd_thousands", "thousands", "usd_thousand"}:
        scale = 0.001
    return float(value) * scale


def _segment_looks_total(value: str) -> bool:
    text = value.lower()
    return any(term in text for term in ["total", "consolidated", "net revenue"]) and not any(
        term in text for term in ["traditional", "ai-optimized", "ai optimized", "product"]
    )


def _is_product_line_item(row: Mapping[str, Any]) -> bool:
    metric = str(row.get("metric_family") or "")
    canonical = str(row.get("canonical_metric_id") or "")
    product = str(row.get("product_or_segment") or "")
    return bool(product) or metric in PRODUCT_METRIC_FAMILIES or canonical.startswith("product_kpi:")


def _claim_mentions_product(claim: Mapping[str, Any]) -> bool:
    text = " ".join(
        [
            str(claim.get("claim") or ""),
            str(claim.get("memo_slot") or ""),
            str(claim.get("analysis_dimension") or ""),
            " ".join(_string_list(claim.get("metric_scope"))),
            " ".join(_string_list(claim.get("source_families") or claim.get("source_family"))),
        ]
    ).lower()
    return _text_has_any(text, ["product", "server", "cloud", "euv", "duv", "ai-optimized", "platform", "capacity", "backlog", "orders"])


def _claim_has_exact_numeric_fact(claim: Mapping[str, Any]) -> bool:
    return bool(_string_list(claim.get("fact_ids"))) or str(claim.get("claim_boundary") or "").startswith("approved_reconciliation")


def _extract_product_terms_from_claim(claim: Mapping[str, Any]) -> list[str]:
    text = str(claim.get("claim") or "")
    terms = []
    patterns = [
        r"\bEUV\b",
        r"\bDUV\b",
        r"\bInstalled Base Management\b",
        r"\bAI-optimized servers?\b",
        r"\bTraditional servers and networking\b",
        r"\bTotal ISG net revenue\b",
        r"\bdata center\b",
        r"\bGoogle Cloud\b",
        r"\bAWS\b",
        r"\bAzure\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            term = match.group(0)
            if term not in terms:
                terms.append(term)
    return terms[:8]


def _edge(
    *,
    source: str,
    target: str,
    edge_type: str,
    direction: str,
    strength: str,
    evidence_refs: list[str],
    claim_boundary: str,
    proves: str,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "edge_id": _stable_id("capital_edge", {"s": source, "t": target, "type": edge_type, "row": row.get("line_item_id")}),
        "source": source,
        "target": target,
        "edge_type": edge_type,
        "direction": direction,
        "strength": strength,
        "metric_family": str(row.get("metric_family") or ""),
        "value": _line_item_value_label(row),
        "period_key": str(row.get("period_key") or ""),
        "evidence_refs": evidence_refs[:6],
        "claim_ids": [],
        "claim_boundary": claim_boundary,
        "proves": proves,
    }


def _strength_from_amount(row: Mapping[str, Any], *, high: float, medium: float) -> str:
    value = _scaled_numeric_value(row)
    if value is None:
        return "unknown"
    value = abs(value)
    if value >= high:
        return "high"
    if value >= medium:
        return "medium"
    return "low"


def _dedupe_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = []
    seen = set()
    for edge in edges:
        key = "|".join(str(edge.get(k) or "") for k in ("source", "target", "edge_type", "value"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(edge)
    return deduped


def _graph_nodes(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = sorted({str(edge.get("source") or "") for edge in edges} | {str(edge.get("target") or "") for edge in edges})
    nodes = []
    for name in names:
        if not name:
            continue
        node_type = "ticker" if re.fullmatch(r"[A-Z]{1,5}", name) else "concept_or_product"
        nodes.append({"node_id": _stable_id("node", name), "label": name, "node_type": node_type})
    return nodes


def _finding(finding_type: str, message: str, owner_agent: str) -> dict[str, Any]:
    return {
        "finding_id": _stable_id("supervision_finding", {"type": finding_type, "message": message, "owner": owner_agent}),
        "type": finding_type,
        "severity": "warning",
        "owner_agent": owner_agent,
        "message": message,
        "repair_policy": "repair_if_retrievable_otherwise_expose_as_bounded_or_commercial_gap",
    }


def _required_followups_from_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    followups = []
    for finding in findings:
        finding_type = str(finding.get("type") or "")
        if finding_type == "numeric_reconciler_required":
            followups.append({"owner_agent": "fundamental_specialist", "action": "select_display_period_and_unit_before_writer"})
        elif finding_type == "product_bridge_gap":
            followups.append({"owner_agent": "product_technology_specialist", "action": "run_official_product_or_order_repair_if_scope_allows"})
        elif finding_type == "transmission_graph_gap":
            followups.append({"owner_agent": "industry_supply_chain_specialist", "action": "seek_direct_supplier_or_product_revenue_readthrough"})
        elif finding_type == "financial_statement_gap":
            followups.append({"owner_agent": "fundamental_specialist", "action": "attempt_statement_line_item_repair_or_mark_statement_gap"})
    return followups


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item or "").strip()]
    return [str(value)] if str(value or "").strip() else []


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _metric_family_from_id(value: str) -> str:
    raw = str(value or "")
    if ":" in raw:
        return raw.split(":", 1)[1]
    return raw


def _statement_type_from_metric(metric_family: str) -> str:
    metric = str(metric_family or "")
    if metric in {"capex", "capital_expenditure_proxy", "fcf", "free_cash_flow", "operating_cash_flow"}:
        return "cash_flow_statement"
    if metric in {"debt", "cash", "inventory"}:
        return "balance_sheet"
    if metric:
        return "income_statement"
    return ""


def _period_role_from_key(value: Any) -> str:
    text = str(value or "").lower()
    for role in ("qtd", "ytd", "ttm", "instant"):
        if text.endswith(f":{role}") or f":{role}:" in text:
            return role
    return ""


def _stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha1(repr(value).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _truncate(value: str, limit: int) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _text_has_any(text: str, terms: list[str]) -> bool:
    value = str(text or "").lower()
    return any(term.lower() in value for term in terms)
