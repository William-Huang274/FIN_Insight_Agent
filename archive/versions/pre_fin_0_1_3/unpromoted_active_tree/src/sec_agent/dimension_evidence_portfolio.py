from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from sec_agent.capital_macro_pack import compact_capital_macro_pack
from sec_agent.financial_statement_analysis import compact_fundamental_statement_pack
from sec_agent.product_intelligence_depth import compact_ai_semis_product_evidence_pack_refs
from sec_agent.product_intelligence_runtime import compact_product_intelligence_pack_refs


DIMENSION_EVIDENCE_PORTFOLIO_SCHEMA_VERSION = "finsight_dimension_evidence_portfolio_v0_1"
DIMENSION_EVIDENCE_PORTFOLIO_REF_SCHEMA_VERSION = "finsight_dimension_evidence_portfolio_ref_v0_1"


DIMENSION_ORDER = (
    "fundamentals",
    "product_and_production",
    "capital_and_financing",
    "competition_and_market_position",
    "industry_supply_chain",
    "risk_and_counterevidence",
)


ROLE_DIMENSION_MAP = {
    "research_lead": set(DIMENSION_ORDER),
    "fundamental_analyst": {"fundamentals", "capital_and_financing", "risk_and_counterevidence"},
    "product_technology_analyst": {"product_and_production", "competition_and_market_position", "industry_supply_chain"},
    "industry_supply_chain_analyst": {"industry_supply_chain", "product_and_production", "capital_and_financing"},
    "market_valuation_analyst": {"competition_and_market_position", "capital_and_financing"},
    "risk_counterevidence_analyst": set(DIMENSION_ORDER),
    "coverage_reflection": set(DIMENSION_ORDER),
    "judgment_plan_aggregator": set(DIMENSION_ORDER),
    "verifier": set(DIMENSION_ORDER),
}


def build_dimension_evidence_portfolio(
    state: Mapping[str, Any],
    *,
    tickers: Sequence[str] | None = None,
    repo_root: str | None = None,
    autoload: bool | None = None,
) -> dict[str, Any]:
    """Build Research Lead's compact dimension-first evidence map.

    This object is not a fact promoter. It only tells the Research Lead and
    specialist agents which already-gated packs can support each analysis
    dimension and which gaps should trigger targeted repair before memo writing.
    """

    state = dict(state or {})
    focus_tickers = _tickers(tickers) or _focus_tickers_from_state(state)
    if autoload is None and "product_intelligence_runtime_autoload" not in state:
        runtime_autoload: bool | None = None
    else:
        runtime_autoload = bool(state.get("product_intelligence_runtime_autoload")) if autoload is None else bool(autoload)

    fundamental_ref = _fundamental_ref(state)
    product_intelligence_ref = compact_product_intelligence_pack_refs(
        state,
        tickers=focus_tickers,
        repo_root=repo_root,
        autoload=runtime_autoload,
    )
    product_evidence_ref = compact_ai_semis_product_evidence_pack_refs(
        state,
        tickers=focus_tickers,
        repo_root=repo_root,
        autoload=runtime_autoload,
    )
    capital_ref = _capital_ref(state)
    source_authority_ref = _source_authority_ref(state)
    gap_ref = _gap_ref(state)

    dimensions = [
        _dimension(
            "fundamentals",
            title="Fundamentals",
            agent_roles=["research_lead", "fundamental_analyst"],
            evidence_roles=["fundamental_statement", "peer_three_statement_panel", "derived_metric"],
            pack_refs={"fundamental_statement_pack_ref": fundamental_ref},
            lead_questions=[
                "三大表和同行/可比公司是否足以解释经营变化？",
                "产品线、资本开支或营运资本变化是否能和财务科目联动？",
            ],
            repair_triggers=[
                "income_statement_missing",
                "balance_sheet_missing",
                "cash_flow_statement_missing",
                "peer_metric_panel_missing",
            ],
        ),
        _dimension(
            "product_and_production",
            title="Product And Production",
            agent_roles=["research_lead", "product_technology_analyst"],
            evidence_roles=[
                "exact_product_kpi",
                "technical_fact",
                "deployment_signal",
                "performance_proxy",
                "relationship_graph",
            ],
            pack_refs={
                "product_intelligence_pack_ref": product_intelligence_ref,
                "product_evidence_pack_ref": product_evidence_ref,
            },
            lead_questions=[
                "产品/服务/业务线是否已归槽到 family 和 product slot？",
                "规格、架构、客户部署、渠道/可得性和 exact KPI 哪些可支撑判断，哪些只能做边界？",
            ],
            repair_triggers=[
                "product_family_slot_missing",
                "technical_spec_missing_for_applicable_lane",
                "deployment_or_adoption_signal_missing_for_deep_research",
                "exact_product_kpi_missing_but_not_required_for_all_product_theses",
            ],
        ),
        _dimension(
            "capital_and_financing",
            title="Capital And Financing",
            agent_roles=["research_lead", "fundamental_analyst", "market_valuation_analyst"],
            evidence_roles=["capital_structure", "ownership", "liquidity", "working_capital", "macro_exposure"],
            pack_refs={"capital_macro_pack_ref": capital_ref, "fundamental_statement_pack_ref": fundamental_ref},
            lead_questions=[
                "债务、现金、营运资本、持仓/流动性和利率环境是否改变判断？",
                "资本市场数据是公司特定事实、市场 proxy，还是只能作为背景？",
            ],
            repair_triggers=[
                "debt_cash_working_capital_missing",
                "ownership_or_liquidity_missing",
                "capital_event_missing_for_financing_query",
            ],
        ),
        _dimension(
            "competition_and_market_position",
            title="Competition And Market Position",
            agent_roles=["research_lead", "product_technology_analyst", "market_valuation_analyst"],
            evidence_roles=["competitive_context_candidate", "substitution", "channel_presence", "market_proxy"],
            pack_refs={
                "product_intelligence_pack_ref": product_intelligence_ref,
                "product_evidence_pack_ref": product_evidence_ref,
                "source_authority_ref": source_authority_ref,
            },
            lead_questions=[
                "产品之间是竞争、替代、互补、上下游还是同族 comparable candidate？",
                "哪些竞争结论有 parser-backed/spec/deployment/benchmark 支持，哪些只是导航边？",
            ],
            repair_triggers=[
                "relationship_edge_is_template_candidate_only",
                "benchmark_or_spec_proxy_missing",
                "commercial_tracker_required_for_share_or_sellthrough",
            ],
        ),
        _dimension(
            "industry_supply_chain",
            title="Industry Supply Chain",
            agent_roles=["research_lead", "industry_supply_chain_analyst", "product_technology_analyst"],
            evidence_roles=["supply_chain_signal", "customer_deployment", "public_order_proxy", "macro_driver"],
            pack_refs={
                "product_evidence_pack_ref": product_evidence_ref,
                "source_authority_ref": source_authority_ref,
                "capital_macro_pack_ref": capital_ref,
            },
            lead_questions=[
                "客户部署、订单/项目、供应链边和宏观 driver 是否形成可解释的传导链？",
                "链条中哪一段是官方事件、哪一段是 proxy，哪一段需要商业 tracker？",
            ],
            repair_triggers=[
                "customer_deployment_signal_missing",
                "supply_chain_edge_missing_or_low_authority",
                "public_order_proxy_not_company_bound",
            ],
        ),
        _dimension(
            "risk_and_counterevidence",
            title="Risk And Counterevidence",
            agent_roles=["research_lead", "risk_counterevidence_analyst", "verifier"],
            evidence_roles=["counter_thesis", "numeric_conflict", "source_boundary", "gap_ledger"],
            pack_refs={"gap_ref": gap_ref, "source_authority_ref": source_authority_ref},
            lead_questions=[
                "哪些证据会推翻主判断，哪些只是公开源边界？",
                "缺口是否应该 targeted repair，还是确认为 bounded/commercial gap？",
            ],
            repair_triggers=[
                "retrievable_gap_unrepaired",
                "numeric_conflict_unresolved",
                "source_boundary_overpromotion_risk",
            ],
        ),
    ]

    portfolio = {
        "schema_version": DIMENSION_EVIDENCE_PORTFOLIO_SCHEMA_VERSION,
        "portfolio_id": f"dimension_portfolio:{_digest({'tickers': focus_tickers, 'dimensions': dimensions})[:20]}",
        "focus_tickers": focus_tickers,
        "dimensions": dimensions,
        "status_counts": _status_counts(dimensions),
        "lead_policy": (
            "Research Lead must audit goal coverage by dimension, trigger targeted repair only for retrievable gaps, "
            "and pass a dimension-led MemoLogicPlan to the writer."
        ),
        "writer_boundary": (
            "Memo Writer consumes judgment_state, memo_logic_plan, verified ClaimCards and bounded gaps only; "
            "raw retrieval rows and tool calls stay outside the writer surface."
        ),
    }
    return _jsonable(portfolio)


def compact_dimension_evidence_portfolio(
    portfolio: Mapping[str, Any],
    *,
    agent_id: str | None = None,
    max_dimensions: int = 6,
    max_pack_keys: int = 6,
) -> dict[str, Any]:
    if not isinstance(portfolio, Mapping) or not portfolio:
        return {}
    allowed = ROLE_DIMENSION_MAP.get(str(agent_id or ""), set(DIMENSION_ORDER))
    dimensions = []
    for row in portfolio.get("dimensions") or []:
        if not isinstance(row, Mapping):
            continue
        dimension_id = str(row.get("dimension_id") or "")
        if dimension_id not in allowed:
            continue
        dimensions.append(
            {
                "dimension_id": dimension_id,
                "title": str(row.get("title") or ""),
                "evidence_status": str(row.get("evidence_status") or ""),
                "evidence_roles": _strings(row.get("evidence_roles"))[:8],
                "available_pack_refs": _strings(row.get("available_pack_refs"))[:max_pack_keys],
                "missing_pack_refs": _strings(row.get("missing_pack_refs"))[:max_pack_keys],
                "repair_triggers": _strings(row.get("repair_triggers"))[:6],
                "lead_questions": _strings(row.get("lead_questions"))[:4],
            }
        )
        if len(dimensions) >= max_dimensions:
            break
    return {
        "schema_version": DIMENSION_EVIDENCE_PORTFOLIO_REF_SCHEMA_VERSION,
        "portfolio_id": str(portfolio.get("portfolio_id") or ""),
        "agent_id": str(agent_id or ""),
        "focus_tickers": _strings(portfolio.get("focus_tickers"))[:12],
        "dimensions": dimensions,
        "status_counts": dict(portfolio.get("status_counts") or {}) if isinstance(portfolio.get("status_counts"), Mapping) else {},
        "lead_policy": str(portfolio.get("lead_policy") or ""),
        "writer_boundary": str(portfolio.get("writer_boundary") or ""),
    }


def _dimension(
    dimension_id: str,
    *,
    title: str,
    agent_roles: list[str],
    evidence_roles: list[str],
    pack_refs: Mapping[str, Any],
    lead_questions: list[str],
    repair_triggers: list[str],
) -> dict[str, Any]:
    available = []
    missing = []
    compact_refs = {}
    for key, value in pack_refs.items():
        if _ref_has_payload(value):
            available.append(key)
            compact_refs[key] = value
        else:
            missing.append(key)
    return {
        "dimension_id": dimension_id,
        "title": title,
        "agent_roles": agent_roles,
        "evidence_roles": evidence_roles,
        "pack_refs": compact_refs,
        "available_pack_refs": available,
        "missing_pack_refs": missing,
        "evidence_status": "ready" if available else "missing",
        "lead_questions": lead_questions,
        "repair_triggers": repair_triggers,
        "promotion_boundary": _promotion_boundary(dimension_id),
    }


def _fundamental_ref(state: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(state.get("fundamental_statement_pack_ref"), Mapping):
        return dict(state.get("fundamental_statement_pack_ref") or {})
    if isinstance(state.get("fundamental_statement_pack"), Mapping):
        return compact_fundamental_statement_pack(state.get("fundamental_statement_pack") or {}, max_line_items=12)
    return {}


def _capital_ref(state: Mapping[str, Any]) -> dict[str, Any]:
    for key in ("capital_macro_pack_ref", "capital_macro_exposure_pack_ref"):
        if isinstance(state.get(key), Mapping):
            return dict(state.get(key) or {})
    for key in ("capital_macro_pack", "capital_macro_exposure_pack"):
        if isinstance(state.get(key), Mapping):
            return compact_capital_macro_pack(state.get(key) or {})
    return {}


def _source_authority_ref(state: Mapping[str, Any]) -> dict[str, Any]:
    value = state.get("source_authority_coverage")
    if not isinstance(value, Mapping):
        value = state.get("source_capability_router") if isinstance(state.get("source_capability_router"), Mapping) else {}
    if not value:
        return {}
    return {
        "schema_version": str(value.get("schema_version") or ""),
        "status": str(value.get("status") or ""),
        "summary": dict(value.get("summary") or {}) if isinstance(value.get("summary"), Mapping) else {},
        "coverage_counts": dict(value.get("coverage_counts") or {}) if isinstance(value.get("coverage_counts"), Mapping) else {},
    }


def _gap_ref(state: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for key in ("bounded_gap_register", "gap_ledger", "gaps"):
        value = state.get(key)
        if isinstance(value, Mapping):
            rows.extend([item for item in value.get("gaps") or value.get("items") or [] if isinstance(item, Mapping)])
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            rows.extend([item for item in value if isinstance(item, Mapping)])
    if not rows:
        return {}
    gap_types = sorted({str(row.get("gap_type") or row.get("type") or "") for row in rows if str(row.get("gap_type") or row.get("type") or "")})
    return {"schema_version": "finsight_gap_ref_v0_1", "gap_count": len(rows), "gap_types": gap_types[:24]}


def _ref_has_payload(value: Any) -> bool:
    if not isinstance(value, Mapping) or not value:
        return False
    if int(value.get("pack_count") or 0) > 0:
        return True
    summary = value.get("summary") if isinstance(value.get("summary"), Mapping) else {}
    if any(int(summary.get(key) or 0) > 0 for key in ("line_item_count", "input_row_count", "row_count", "gap_count")):
        return True
    if value.get("statement_line_items") or value.get("period_changes") or value.get("peer_comparisons"):
        return True
    if int(value.get("gap_count") or 0) > 0:
        return True
    return bool(value.get("status") in {"pass", "ready", "pass_with_gaps"})


def _promotion_boundary(dimension_id: str) -> str:
    return {
        "fundamentals": "only reconciled statement, peer, and derived metric rows support financial facts",
        "product_and_production": "specs/deployments/proxies support product capability and adoption judgments; only exact KPI rows support sales/share/backlog claims",
        "capital_and_financing": "ownership/liquidity/macro rows require issuer/period/source boundaries before investment implication",
        "competition_and_market_position": "relationship edges must disclose whether they are structural, parser-backed, proxy, or hypothesis-only",
        "industry_supply_chain": "supply-chain and customer-deployment rows support read-through only with counterparty/product/source boundary",
        "risk_and_counterevidence": "gaps and conflicts are verifier inputs, not the main memo narrative unless they overturn the thesis",
    }.get(dimension_id, "use source authority and claim boundary before promotion")


def _focus_tickers_from_state(state: Mapping[str, Any]) -> list[str]:
    for key in ("focus_tickers", "tickers", "ticker_scope"):
        values = _tickers(state.get(key))
        if values:
            return values
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    for key in ("focus_tickers", "ticker_scope", "search_scope_tickers"):
        values = _tickers(query_contract.get(key))
        if values:
            return values
    return []


def _tickers(value: Any) -> list[str]:
    return [item.upper() for item in _strings(value) if item.strip()]


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, Mapping):
        return [str(value.get("ticker") or value.get("id") or "")] if (value.get("ticker") or value.get("id")) else []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _status_counts(dimensions: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in dimensions:
        status = str(row.get("evidence_status") or "missing")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _digest(value: Any) -> str:
    return hashlib.sha1(json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, Mapping):
            return {str(k): _jsonable(v) for k, v in value.items()}
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return [_jsonable(item) for item in value]
        return str(value)
