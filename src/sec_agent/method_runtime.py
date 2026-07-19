from __future__ import annotations

from typing import Any, Mapping


METHOD_RUNTIME_PACK_SCHEMA_VERSION = "fin_insight_method_runtime_pack_v0_1"

AI_SEMIS_TICKERS = {
    "NVDA",
    "AMD",
    "INTC",
    "GOOGL",
    "GOOG",
    "MSFT",
    "AMZN",
    "DELL",
    "SMCI",
    "HPE",
    "ASML",
    "TSM",
    "AMAT",
    "LRCX",
    "KLAC",
    "AVGO",
    "MU",
    "MRVL",
    "ARM",
    "QCOM",
}

AI_SEMIS_KEYWORDS = (
    "ai server",
    "accelerator",
    "blackwell",
    "gpu",
    "tpu",
    "hbm",
    "cowos",
    "semicap",
    "wafer fab",
    "hyperscaler",
    "data center",
    "server oem",
    "半导体",
    "人工智能",
    "算力",
    "数据中心",
)

METHOD_LIFECYCLE_STAGES = (
    "documented",
    "registry_only",
    "contract_translated",
    "fixture_proven",
    "runtime_injected",
    "node_level_consumed",
    "paid_artifact_proven",
    "dogfood_accepted",
)

METHOD_TO_RUNTIME_GAP_TAXONOMY = {
    "business_method_gap": "The financial research method itself is underspecified or wrong.",
    "method_to_runtime_gap": "The method exists in docs/registry but is not injected into prompts, schema, or node payloads.",
    "model_instruction_following_gap": "Runtime contract is present, but the model ignores or misuses it.",
    "engineering_projection_gap": "Upstream data exists, but projection into JudgmentCards/MemoLogicPlan loses it.",
    "data_evidence_gap": "The public or internal evidence is absent for the requested claim.",
    "parser_retrieval_gap": "The evidence should be retrievable, but locator/parser/extractor failed.",
}

ANALYST_REQUIRED_ITEMS = [
    {
        "required_item": "product_architecture_competition",
        "question": "What product/spec/generation change matters, and how does it compare with substitutes?",
        "primary_agents": ["product_technology_analyst"],
        "writer_role": "Explain product capability and competitive implication before financial extrapolation.",
    },
    {
        "required_item": "customer_deployment_adoption",
        "question": "Who deploys, adopts, configures, distributes, or validates the product?",
        "primary_agents": ["product_technology_analyst", "industry_supply_chain_analyst"],
        "writer_role": "Use adoption as bounded demand validation, not as exact sales or share.",
    },
    {
        "required_item": "supply_chain_readthrough",
        "question": "Which upstream/downstream chain transmits demand, bottlenecks, or pricing pressure?",
        "primary_agents": ["industry_supply_chain_analyst"],
        "writer_role": "Map the economic chain before claiming a beneficiary or pressure point.",
    },
    {
        "required_item": "fundamental_financial_bridge",
        "question": "How does the product or cycle reach revenue, margin, cash flow, working capital, capex, or backlog?",
        "primary_agents": ["fundamental_analyst"],
        "writer_role": "Turn accounting facts into quality-of-growth and margin/cash-flow judgment.",
    },
    {
        "required_item": "capital_market_price_in",
        "question": "What is already priced, funded, crowded, or constrained by capital-market/credit/liquidity evidence?",
        "primary_agents": ["market_valuation_analyst", "fundamental_analyst"],
        "writer_role": "Separate business improvement from market expectation and capital feedback.",
    },
    {
        "required_item": "risk_and_counterevidence",
        "question": "What would make the thesis wrong, weaker, delayed, or commercially bounded?",
        "primary_agents": ["risk_counterevidence_analyst"],
        "writer_role": "State counter-read and evidence boundary after giving a bounded judgment.",
    },
]

SPECIALIST_RUBRICS = {
    "product_technology_analyst": {
        "role_runtime_mission": "Convert product evidence into bounded product capability, adoption, and competitive judgment.",
        "must_answer": [
            "what_product_or_service",
            "architecture_spec_generation_change",
            "competitor_or_substitute_comparison",
            "customer_deployment_or_configuration",
            "supply_chain_constraint_or_dependency",
            "product_capability_judgment",
        ],
        "must_not_infer": [
            "product_revenue_without_exact_kpi",
            "shipment_or_share_without_company_disclosed_metric",
            "customer_order_value_without_order_or_contract_fact",
        ],
        "writer_ready_bridge": "Product/spec/deployment evidence can support capability, adoption, and demand-validation judgments; it cannot alone prove revenue, margin, share, or shipment.",
    },
    "fundamental_analyst": {
        "role_runtime_mission": "Bridge product and industry evidence into three-statement and peer-relative financial quality judgment.",
        "must_answer": [
            "revenue_or_segment_exposure",
            "margin_quality_or_dilution",
            "working_capital_inventory_backlog",
            "capex_cash_flow_funding",
            "peer_or_period_comparison",
            "product_to_financial_bridge",
        ],
        "must_not_infer": [
            "margin_improvement_from_revenue_growth_alone",
            "peer_advantage_without_same_metric_period_unit",
            "AI_server_profitability_without_gross_margin_or_mix_bridge",
        ],
        "writer_ready_bridge": "Financial claims must explain whether product/cycle evidence improves quality of growth, pressures margins, consumes working capital, or changes cash conversion.",
    },
    "industry_supply_chain_analyst": {
        "role_runtime_mission": "Map economic transmission across demand source, supplier bottleneck, customer adoption, and peer cycle.",
        "must_answer": [
            "demand_source",
            "supply_bottleneck",
            "chain_transmission_validity",
            "semicap_cycle_driver",
            "customer_supplier_or_peer_role",
            "metric_needed_to_confirm",
        ],
        "must_not_infer": [
            "direct_customer_supplier_fact_from_scope_hypothesis",
            "orders_or_backlog_from_peer_group_membership",
            "revenue_or_margin_from_relationship_graph_alone",
        ],
        "writer_ready_bridge": "Relationship and industry rows support chain hypotheses and read-through tests; company or official evidence is needed for direct customer/order/fact claims.",
    },
    "risk_counterevidence_analyst": {
        "role_runtime_mission": "Stress-test the thesis path and identify bounded counter-read, not a generic risk list.",
        "must_answer": [
            "capex_digestion_risk",
            "export_control_or_regulatory_risk",
            "customer_concentration",
            "margin_dilution_or_pricing_pressure",
            "supply_bottleneck_or_product_delay",
            "missing_but_retrievable_evidence",
        ],
        "must_not_infer": [
            "risk_from_memory_without_bounded_ref",
            "commercial_gap_as_public_source_absent",
            "generic_caution_without_thesis_constraint",
        ],
        "writer_ready_bridge": "Risk output must constrain a named thesis component and say what would change the view.",
    },
    "market_valuation_analyst": {
        "role_runtime_mission": "Bridge business evidence to market expectation, valuation, positioning, and price-in risk.",
        "must_answer": [
            "valuation_or_market_expectation_context",
            "capital_flow_or_positioning_signal",
            "price_in_or_event_reaction",
            "liquidity_or_crowding_risk",
        ],
        "must_not_infer": [
            "fundamental_improvement_from_price_action_alone",
            "realtime_flow_without_authorized_source",
        ],
        "writer_ready_bridge": "Market evidence informs price-in and risk appetite, not company operating facts.",
    },
}

GRAPH_EDGE_INVESTMENT_ROLES = {
    "deployed_by": "adoption_signal",
    "adopted_by": "adoption_signal",
    "ordered_by": "demand_validation",
    "configured_in": "channel_or_oem_validation",
    "distributed_by": "channel_presence",
    "sold_through": "channel_presence",
    "supplies": "supply_constraint",
    "supplier": "supply_constraint",
    "upstream_of": "supply_constraint",
    "downstream_of": "read_through",
    "read_through_to": "read_through",
    "competes_with": "competitive_substitution",
    "substitutes_for": "competitive_substitution",
    "generation_successor": "product_cycle_transition",
    "complements": "ecosystem_dependency",
}


def build_method_runtime_pack(
    state_or_context: Mapping[str, Any] | None = None,
    *,
    user_query: str = "",
    focus_tickers: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    context = dict(state_or_context or {})
    tickers = _focus_tickers(context, focus_tickers)
    query = str(user_query or context.get("user_query") or context.get("query") or "")
    lane = _detect_lane(query, tickers, context)
    pack = {
        "schema_version": METHOD_RUNTIME_PACK_SCHEMA_VERSION,
        "status": "runtime_injected",
        "method_lifecycle_required": list(METHOD_LIFECYCLE_STAGES),
        "active_method_ids": _active_method_ids(lane),
        "lane": lane,
        "focus_tickers": tickers,
        "research_lead_required_items": ANALYST_REQUIRED_ITEMS,
        "specialist_task_rubric": SPECIALIST_RUBRICS,
        "judgment_candidate_contract": _judgment_candidate_contract(),
        "graph_edge_investment_roles": dict(GRAPH_EDGE_INVESTMENT_ROLES),
        "gap_attribution_taxonomy": dict(METHOD_TO_RUNTIME_GAP_TAXONOMY),
        "runtime_consumption_required": [
            "research_lead_thesis_path",
            "specialist_role_rubric",
            "judgment_candidate_output",
            "product_graph_edge_projection",
            "memo_logic_plan_writer_input",
        ],
    }
    if lane == "ai_semis":
        pack["ai_semis_playbook"] = {
            "core_chain": [
                "product_or_architecture_change",
                "customer_adoption_or_deployment",
                "supply_constraint_or_value_chain",
                "financial_quality_bridge",
                "market_expectation_price_in",
                "counterevidence_and_trigger",
            ],
            "example_questions": [
                "Does AI server growth improve margin quality or create low-margin pass-through?",
                "Does accelerator supply allocation transmit to server OEMs and ODMs?",
                "Does semicap bookings/backlog support a durable wafer-fab equipment cycle?",
            ],
            "forbidden_shortcut": "Do not treat peer group membership or product existence as proof of orders, margin, revenue, or share.",
        }
    return pack


def compact_method_runtime_pack_for_prompt(pack: Mapping[str, Any], *, agent_id: str = "") -> dict[str, Any]:
    if not isinstance(pack, Mapping):
        return {}
    rubrics = pack.get("specialist_task_rubric") if isinstance(pack.get("specialist_task_rubric"), Mapping) else {}
    role_rubric = rubrics.get(agent_id) if isinstance(rubrics.get(agent_id), Mapping) else {}
    compact = {
        "schema_version": pack.get("schema_version") or METHOD_RUNTIME_PACK_SCHEMA_VERSION,
        "status": pack.get("status") or "",
        "lane": pack.get("lane") or "",
        "active_method_ids": list(pack.get("active_method_ids") or [])[:8],
        "research_lead_required_items": list(pack.get("research_lead_required_items") or [])[:8],
        "judgment_candidate_contract": pack.get("judgment_candidate_contract") or {},
        "graph_edge_investment_roles": pack.get("graph_edge_investment_roles") or {},
        "gap_attribution_taxonomy": pack.get("gap_attribution_taxonomy") or {},
    }
    if role_rubric:
        compact["specialist_runtime_rubric"] = role_rubric
    if isinstance(pack.get("ai_semis_playbook"), Mapping):
        compact["ai_semis_playbook"] = pack["ai_semis_playbook"]
    return compact


def specialist_runtime_rubric(method_runtime_pack: Mapping[str, Any], agent_id: str) -> dict[str, Any]:
    rubrics = method_runtime_pack.get("specialist_task_rubric") if isinstance(method_runtime_pack.get("specialist_task_rubric"), Mapping) else {}
    return dict(rubrics.get(agent_id) or {}) if isinstance(rubrics.get(agent_id), Mapping) else {}


def project_graph_edge_investment_role(edge_type: str, authority_type: str = "") -> dict[str, str]:
    edge = str(edge_type or "").strip().lower()
    authority = str(authority_type or "").strip().lower()
    role = GRAPH_EDGE_INVESTMENT_ROLES.get(edge)
    if not role:
        if "deploy" in edge or "adopt" in edge:
            role = "adoption_signal"
        elif "supply" in edge or "upstream" in edge:
            role = "supply_constraint"
        elif "compete" in edge or "substitut" in edge:
            role = "competitive_substitution"
        elif authority == "competitive_context_candidate":
            role = "competitive_context_candidate"
        elif authority in {"deployment_signal_authority", "channel_presence_signal"}:
            role = "adoption_or_channel_context"
        else:
            role = "bounded_context"
    return {
        "edge_investment_role": role,
        "supports_judgment": _edge_supports_judgment(role),
        "cannot_infer": _edge_cannot_infer(role),
        "needed_confirmation": _edge_needed_confirmation(role),
    }


def _judgment_candidate_contract() -> dict[str, Any]:
    return {
        "required_fields": [
            "judgment",
            "required_item_answered",
            "supported_by_evidence_refs",
            "graph_edge_refs",
            "product_or_financial_bridge",
            "business_mechanism",
            "counter_read",
            "confidence",
            "cannot_infer",
            "what_would_change_view",
        ],
        "policy": "specialists produce writer-ready judgment candidates, not row summaries",
        "boundary": "candidate may be bounded/proxy/context-grade, but must say what it supports and cannot infer",
    }


def _active_method_ids(lane: str) -> list[str]:
    base = [
        "thesis_path_first_research",
        "product_to_financial_bridge",
        "three_statement_peer_panel",
        "customer_supplier_readthrough",
        "bounded_leading_signal_promotion",
        "thesis_led_memo_output",
    ]
    if lane == "ai_semis":
        return [
            *base,
            "p32_ai_semis_theme_exposure_thesis_path",
            "p32_product_architecture_competitive_bridge",
            "p32_semis_cycle_value_chain_playbook",
            "p32_ai_semis_counter_thesis_path",
        ]
    return base


def _detect_lane(query: str, tickers: list[str], context: Mapping[str, Any]) -> str:
    if any(ticker in AI_SEMIS_TICKERS for ticker in tickers):
        return "ai_semis"
    text = " ".join(
        [
            query.lower(),
            str(context.get("industry") or "").lower(),
            str(context.get("vertical_lane") or "").lower(),
            str(context.get("playbook_candidates") or "").lower(),
        ]
    )
    if any(term in text for term in AI_SEMIS_KEYWORDS):
        return "ai_semis"
    return "general_financial_research"


def _focus_tickers(context: Mapping[str, Any], focus_tickers: list[str] | tuple[str, ...] | None) -> list[str]:
    values: list[Any] = []
    if focus_tickers:
        values.extend(focus_tickers)
    for key in ("focus_tickers", "tickers", "search_scope_tickers"):
        raw = context.get(key)
        if isinstance(raw, (list, tuple, set)):
            values.extend(raw)
        elif isinstance(raw, str):
            values.extend(raw.replace(",", " ").split())
    out: list[str] = []
    for value in values:
        ticker = str(value or "").upper().strip()
        if ticker and ticker not in out:
            out.append(ticker)
    return out[:24]


def _edge_supports_judgment(role: str) -> str:
    return {
        "demand_validation": "supports bounded customer/order/deployment demand validation",
        "adoption_signal": "supports product adoption or deployment context",
        "channel_or_oem_validation": "supports OEM/channel configuration context",
        "channel_presence": "supports channel availability or distribution context",
        "supply_constraint": "supports supply-chain bottleneck or dependency context",
        "read_through": "supports upstream/downstream read-through hypothesis",
        "competitive_substitution": "supports competitive or substitution framing",
        "product_cycle_transition": "supports product generation transition context",
        "ecosystem_dependency": "supports ecosystem complement/dependency context",
    }.get(role, "supports bounded context only")


def _edge_cannot_infer(role: str) -> str:
    common = "cannot infer exact revenue, shipment, share, backlog, ASP, margin, or order value without exact authority"
    if role in {"competitive_substitution", "product_cycle_transition"}:
        return f"{common}; cannot infer winner/loser without comparable specs, adoption, and financial bridge"
    if role in {"demand_validation", "adoption_signal", "channel_or_oem_validation"}:
        return f"{common}; cannot infer sell-through or customer spend without direct order or disclosure"
    return common


def _edge_needed_confirmation(role: str) -> str:
    return {
        "demand_validation": "official customer/order/deployment disclosure or company-reported backlog/revenue bridge",
        "adoption_signal": "official deployment case, customer reference, channel/OEM listing, or product usage metric",
        "channel_or_oem_validation": "OEM configuration, marketplace listing, or official partner/customer documentation",
        "channel_presence": "issuer-bound channel listing with SKU/price/availability or official store evidence",
        "supply_constraint": "supplier disclosure, capacity/allocation evidence, lead time, or capex/backlog bridge",
        "read_through": "company-specific exposure metric and chain-level demand or constraint evidence",
        "competitive_substitution": "comparable product specs, benchmark/adoption evidence, and financial exposure bridge",
        "product_cycle_transition": "official product generation spec, launch/deployment timing, and adoption signal",
    }.get(role, "company-specific confirming evidence")
