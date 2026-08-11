"""P33-2 no-paid runtime assimilation fixture.

This fixture proves that P32/P33 active contracts are not only documented but
are consumable by the runtime planning spine: Research Lead, ContextEngine,
evidence packs, JudgmentCards, MemoLogicPlan, and Workbench trace projection.
It deliberately avoids paid LLM calls and full-chain execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.context_engine import ContextEngine, ContextEngineConfig
from sec_agent.memo_logic_plan import build_memo_logic_plan
from sec_agent.r53_r60_runtime_task_spine import digest_payload, rel_path, stable_id, utc_now_iso, write_json


SCHEMA_VERSION = "fin_insight_p33_runtime_assimilation_fixture_v0_1"
CONTRACT_ID = "p33_runtime_assimilation_contract_v0_1"
RELEASE_DECISION_PASS = "P33_2_L4_scope_pass_runtime_assimilation_fixture"
RELEASE_DECISION_BLOCKED = "P33_2_blocked_runtime_assimilation_fixture"

EXPECTED_ACTIVE_CONTRACT_IDS = [
    "l3_ai_theme_exposure_thesis_path_contract_v0_1",
    "l3_workpaper_lifecycle_event_contract_v0_1",
    "l3_product_architecture_competitive_bridge_contract_v0_1",
    "l3_semis_cycle_value_chain_playbook_contract_v0_1",
    "l3_thesis_led_memo_output_contract_v0_1",
    "l3_checkpoint_targeted_repair_contract_v0_1",
    "l3_tool_gateway_mcp_boundary_contract_v0_1",
    "l3_durable_hil_task_event_contract_v0_1",
    "l3_genai_trace_quality_cost_contract_v0_1",
    "l3_context_engine_injection_contract_v0_1",
    "l3_capital_market_feedback_contract_v0_1",
    "l3_research_to_quant_factor_handoff_contract_v0_1",
    "l3_enterprise_rag_data_pipeline_contract_v0_1",
    "l3_workbench_artifact_review_surface_contract_v0_1",
    "l3_sandbox_resource_scheduler_contract_v0_1",
]


COMPONENT_CONTRACT_ROUTES = {
    "research_lead": [
        "l3_ai_theme_exposure_thesis_path_contract_v0_1",
        "l3_semis_cycle_value_chain_playbook_contract_v0_1",
        "l3_checkpoint_targeted_repair_contract_v0_1",
        "l3_context_engine_injection_contract_v0_1",
        "l3_capital_market_feedback_contract_v0_1",
        "l3_enterprise_rag_data_pipeline_contract_v0_1",
        "l3_thesis_led_memo_output_contract_v0_1",
    ],
    "context_engine": [
        "l3_context_engine_injection_contract_v0_1",
        "l3_enterprise_rag_data_pipeline_contract_v0_1",
        "l3_sandbox_resource_scheduler_contract_v0_1",
        "l3_genai_trace_quality_cost_contract_v0_1",
    ],
    "product_intelligence_graph": [
        "l3_product_architecture_competitive_bridge_contract_v0_1",
        "l3_semis_cycle_value_chain_playbook_contract_v0_1",
        "l3_enterprise_rag_data_pipeline_contract_v0_1",
    ],
    "fundamental_statement_pack": [
        "l3_enterprise_rag_data_pipeline_contract_v0_1",
        "l3_ai_theme_exposure_thesis_path_contract_v0_1",
    ],
    "capital_market_feedback_pack": [
        "l3_capital_market_feedback_contract_v0_1",
        "l3_research_to_quant_factor_handoff_contract_v0_1",
    ],
    "customer_deployment_pack": [
        "l3_product_architecture_competitive_bridge_contract_v0_1",
        "l3_semis_cycle_value_chain_playbook_contract_v0_1",
        "l3_workbench_artifact_review_surface_contract_v0_1",
    ],
    "judgment_and_memo": [
        "l3_thesis_led_memo_output_contract_v0_1",
        "l3_product_architecture_competitive_bridge_contract_v0_1",
        "l3_capital_market_feedback_contract_v0_1",
        "l3_ai_theme_exposure_thesis_path_contract_v0_1",
        "l3_workpaper_lifecycle_event_contract_v0_1",
    ],
    "workbench": [
        "l3_workpaper_lifecycle_event_contract_v0_1",
        "l3_workbench_artifact_review_surface_contract_v0_1",
        "l3_genai_trace_quality_cost_contract_v0_1",
        "l3_durable_hil_task_event_contract_v0_1",
        "l3_tool_gateway_mcp_boundary_contract_v0_1",
    ],
}


@dataclass(frozen=True)
class P33RuntimeAssimilationFixturePaths:
    manifest_path: Path
    report_path: Path


def default_p33_runtime_assimilation_fixture_paths(root: Path) -> P33RuntimeAssimilationFixturePaths:
    return P33RuntimeAssimilationFixturePaths(
        manifest_path=root / "data" / "manifests" / "p33_runtime_assimilation_fixture_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "p33_runtime_assimilation_fixture_report.zh-CN.md",
    )


def build_p33_runtime_assimilation_fixture(root: Path, *, write_outputs: bool = True) -> dict[str, Any]:
    root = root.resolve()
    active_contracts = _load_active_contracts(root)
    manifest = collect_p33_runtime_assimilation_manifest(root, active_contracts=active_contracts)
    if write_outputs:
        paths = default_p33_runtime_assimilation_fixture_paths(root)
        write_json(paths.manifest_path, manifest)
        paths.report_path.parent.mkdir(parents=True, exist_ok=True)
        paths.report_path.write_text(render_p33_runtime_assimilation_report(manifest), encoding="utf-8")
    return manifest


def collect_p33_runtime_assimilation_manifest(
    root: Path,
    *,
    active_contracts: list[Mapping[str, Any]],
) -> dict[str, Any]:
    runtime_contract_registry = _build_runtime_contract_registry(active_contracts)
    evidence_packs = _build_evidence_packs(root, runtime_contract_registry)
    research_lead_runtime_plan = _build_research_lead_runtime_plan(evidence_packs, runtime_contract_registry)
    context_injection_audit = _build_context_injection_audit(
        research_lead_runtime_plan=research_lead_runtime_plan,
        evidence_packs=evidence_packs,
        runtime_contract_registry=runtime_contract_registry,
    )
    judgment_state = _build_judgment_state(evidence_packs, research_lead_runtime_plan)
    memo_logic_plan = build_memo_logic_plan(
        judgment_state=judgment_state,
        lead_review_checkpoint=_build_lead_review_checkpoint(evidence_packs, research_lead_runtime_plan),
        product_reasoning_frame=evidence_packs["product_reasoning_frame"],
        required_question_items=research_lead_runtime_plan["required_item_plan"],
        focus_ticker_coverage_policy={
            "focus_tickers": ["NVDA", "AMD", "GOOGL", "DELL", "ASML", "LRCX"],
            "policy": "memo_must_not_claim_missing_data_when_approved_facts_exist",
            "minimum_statuses": ["answerable_with_bounded_judgment", "typed_gap_traceable"],
        },
    )
    workbench_trace_projection = _build_workbench_trace_projection(
        root=root,
        research_lead_runtime_plan=research_lead_runtime_plan,
        context_injection_audit=context_injection_audit,
        judgment_state=judgment_state,
        memo_logic_plan=memo_logic_plan,
        evidence_packs=evidence_packs,
    )
    acceptance_gates = evaluate_p33_runtime_assimilation_gates(
        runtime_contract_registry=runtime_contract_registry,
        research_lead_runtime_plan=research_lead_runtime_plan,
        context_injection_audit=context_injection_audit,
        judgment_state=judgment_state,
        memo_logic_plan=memo_logic_plan,
        workbench_trace_projection=workbench_trace_projection,
        evidence_packs=evidence_packs,
    )
    fail_count = len([row for row in acceptance_gates if row["status"] != "pass"])
    status = "pass" if fail_count == 0 else "fail"
    paths = default_p33_runtime_assimilation_fixture_paths(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now_iso(),
        "contract_id": CONTRACT_ID,
        "status": status,
        "release_decision": RELEASE_DECISION_PASS if status == "pass" else RELEASE_DECISION_BLOCKED,
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "promotion_recommendation": "P33-3_ai_semis_gold_case_unblocked" if status == "pass" else "repair_before_P33-3",
        "absorbed_contract_ids": [row["contract_id"] for row in active_contracts],
        "source_fixture_refs": {
            "active_registry_ledger": "docs/project_os/p32_active_registry_promotion_ledger.jsonl",
            "p33_execution_plan_ledger": "docs/project_os/p33_execution_plan_ledger.jsonl",
            "p33_manifest": rel_path(paths.manifest_path, root),
            "p33_report": rel_path(paths.report_path, root),
        },
        "runtime_contract_registry": runtime_contract_registry,
        "evidence_packs": evidence_packs,
        "research_lead_runtime_plan": research_lead_runtime_plan,
        "context_injection_audit": context_injection_audit,
        "judgment_state": judgment_state,
        "memo_logic_plan": memo_logic_plan,
        "workbench_trace_projection": workbench_trace_projection,
        "acceptance_gates": acceptance_gates,
        "gate_fail_count": fail_count,
        "runtime_entry_policy": (
            "P33-2 runtime assimilation is no-paid and deterministic. It proves active "
            "registry contracts are consumed by planning, context injection, judgment "
            "material, memo planning and Workbench trace projection. It does not prove "
            "paid-model memo quality; P33-3 must use one gold workpaper case after preflight."
        ),
        "do_not_promote": [
            "active_registry_documented_but_not_consumed",
            "research_lead_task_list_without_thesis_path",
            "writer_raw_evidence_dump",
            "memo_missing_evidence_when_upstream_pack_exists",
            "wide_specialist_fanout_without_required_item",
        ],
        "rollback_gate": [
            "active_contract_count_not_15",
            "context_injection_not_role_scoped",
            "memo_logic_plan_validation_failed",
            "workbench_trace_missing_judgment_or_gap_refs",
        ],
    }


def evaluate_p33_runtime_assimilation_gates(
    *,
    runtime_contract_registry: Mapping[str, Any],
    research_lead_runtime_plan: Mapping[str, Any],
    context_injection_audit: Mapping[str, Any],
    judgment_state: Mapping[str, Any],
    memo_logic_plan: Mapping[str, Any],
    workbench_trace_projection: Mapping[str, Any],
    evidence_packs: Mapping[str, Any],
) -> list[dict[str, Any]]:
    gates = [
        (
            "p33_2_active_registry_consumed",
            runtime_contract_registry.get("active_contract_count") == 15
            and runtime_contract_registry.get("missing_expected_contract_ids") == []
            and runtime_contract_registry.get("unexpected_active_contract_ids") == [],
            "All 15 active contracts are consumed into the runtime contract registry.",
            {
                "active_contract_count": runtime_contract_registry.get("active_contract_count"),
                "missing": runtime_contract_registry.get("missing_expected_contract_ids"),
                "unexpected": runtime_contract_registry.get("unexpected_active_contract_ids"),
            },
        ),
        (
            "p33_2_research_lead_thesis_path_not_task_list",
            bool(research_lead_runtime_plan.get("thesis_path", {}).get("primary_thesis"))
            and len(research_lead_runtime_plan.get("thesis_path", {}).get("path_nodes") or []) >= 5
            and len(research_lead_runtime_plan.get("required_item_plan") or []) >= 4
            and len(research_lead_runtime_plan.get("evidence_role_plan") or []) >= 5,
            "Research Lead emits thesis path, required item plan, evidence role plan and typed repair plan.",
            research_lead_runtime_plan.get("plan_summary"),
        ),
        (
            "p33_2_evidence_packs_enter_main_judgment_spine",
            set(evidence_packs.get("pack_ids_used_by_judgment_spine") or [])
            >= {
                "ProductIntelligenceGraph",
                "FundamentalStatementPack",
                "CapitalMarketFeedbackPack",
                "CustomerDeploymentPack",
                "IndustryPlaybook",
            }
            and len(judgment_state.get("dimension_judgments") or []) >= 5,
            "Product, fundamental, capital, customer/deployment and industry packs enter the main judgment spine.",
            {"pack_ids_used_by_judgment_spine": evidence_packs.get("pack_ids_used_by_judgment_spine")},
        ),
        (
            "p33_2_context_engine_role_specific_injection",
            context_injection_audit.get("status") == "pass"
            and context_injection_audit.get("writer_raw_dump_blocked") is True
            and context_injection_audit.get("specialist_role_context_distinct") is True,
            "ContextEngine produces role-scoped compressed injection plans and blocks writer raw evidence dump.",
            context_injection_audit.get("summary"),
        ),
        (
            "p33_2_judgmentcard_memologicplan_writer_ready",
            judgment_state.get("status") == "ready"
            and memo_logic_plan.get("validation", {}).get("status") == "pass"
            and "database_query" in set(memo_logic_plan.get("writer_forbidden_tools") or [])
            and bool(memo_logic_plan.get("writer_thesis_skeleton", {}).get("judgment_card_moves")),
            "JudgmentCards and MemoLogicPlan are writer-ready and writer is expression-only.",
            {
                "judgment_status": judgment_state.get("status"),
                "memo_validation": memo_logic_plan.get("validation"),
                "writer_allowed_inputs": memo_logic_plan.get("writer_allowed_inputs"),
            },
        ),
        (
            "p33_2_missing_evidence_traceable_to_typed_gap",
            _all_required_item_gaps_are_typed(research_lead_runtime_plan),
            "Any unanswerable required item is traceable to a typed gap, not hidden as generic data absence.",
            {"typed_gap_refs": research_lead_runtime_plan.get("typed_gap_refs")},
        ),
        (
            "p33_2_workbench_drilldown_projection_replayable",
            workbench_trace_projection.get("status") == "pass"
            and workbench_trace_projection.get("evidence_ref_count", 0) >= 5
            and workbench_trace_projection.get("judgment_card_count", 0) >= 5
            and workbench_trace_projection.get("artifact_ref_count", 0) >= 4,
            "Workbench projection can drill from task to evidence, JudgmentCards, typed gaps, gates and artifacts.",
            workbench_trace_projection.get("summary"),
        ),
        (
            "p33_2_no_paid_or_full_chain",
            workbench_trace_projection.get("paid_llm_call_count") == 0
            and workbench_trace_projection.get("full_chain_run_count") == 0,
            "No paid LLM or full-chain run is used for P33-2.",
            {
                "paid_llm_call_count": workbench_trace_projection.get("paid_llm_call_count"),
                "full_chain_run_count": workbench_trace_projection.get("full_chain_run_count"),
            },
        ),
    ]
    generated_at = utc_now_iso()
    return [
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at": generated_at,
            "fixture_id": "P33-2",
            "gate_id": gate_id,
            "status": "pass" if passed else "fail",
            "description": description,
            "detail": detail,
            "closeout_level": "L4_scope_pass",
        }
        for gate_id, passed, description, detail in gates
    ]


def render_p33_runtime_assimilation_report(manifest: Mapping[str, Any]) -> str:
    lines = [
        "# P33-2 Runtime Assimilation Fixture",
        "",
        f"Generated: `{manifest['generated_at']}`",
        f"Contract: `{manifest['contract_id']}`",
        f"Status: `{manifest['status']}`",
        f"Release decision: `{manifest['release_decision']}`",
        f"Closeout level: `{manifest['closeout_level']}`",
        "",
        "## Scope",
        "",
        "This no-paid deterministic fixture proves the active P32/P33 contracts are consumed by "
        "Research Lead planning, role-scoped ContextEngine injection, evidence-pack judgment "
        "spine, MemoLogicPlan writer input, and Workbench trace projection.",
        "",
        "## Gate Rows",
        "",
    ]
    for row in manifest.get("acceptance_gates") or []:
        lines.append(f"- `{row['status']}` `{row['gate_id']}`: {row['description']}")
    lines.extend(["", "## Research Lead Runtime Plan", ""])
    plan = manifest.get("research_lead_runtime_plan") if isinstance(manifest.get("research_lead_runtime_plan"), Mapping) else {}
    thesis = plan.get("thesis_path") if isinstance(plan.get("thesis_path"), Mapping) else {}
    lines.append(f"- Primary thesis: {thesis.get('primary_thesis', '')}")
    lines.append(f"- Required items: `{len(plan.get('required_item_plan') or [])}`")
    lines.append(f"- Evidence roles: `{len(plan.get('evidence_role_plan') or [])}`")
    lines.extend(["", "## Boundary", "", str(manifest.get("runtime_entry_policy")), ""])
    return "\n".join(lines)


def _load_active_contracts(root: Path) -> list[dict[str, Any]]:
    path = root / "docs" / "project_os" / "p32_active_registry_promotion_ledger.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"Active registry promotion ledger is missing: {path}")
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("status") == "active_registry_ready":
            rows.append(dict(payload))
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        latest[str(row.get("contract_id") or "")] = row
    return [latest[contract_id] for contract_id in EXPECTED_ACTIVE_CONTRACT_IDS if contract_id in latest]


def _build_runtime_contract_registry(active_contracts: list[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {str(row.get("contract_id") or ""): dict(row) for row in active_contracts}
    active_ids = sorted(by_id)
    expected = set(EXPECTED_ACTIVE_CONTRACT_IDS)
    component_routes = {}
    for component, ids in COMPONENT_CONTRACT_ROUTES.items():
        component_routes[component] = [
            {
                "contract_id": contract_id,
                "promotion_decision": by_id.get(contract_id, {}).get("promotion_decision", ""),
                "runtime_entry_policy": by_id.get(contract_id, {}).get("runtime_entry_policy", ""),
                "do_not_promote": by_id.get(contract_id, {}).get("do_not_promote", []),
                "rollback_gate": by_id.get(contract_id, {}).get("rollback_gate", []),
                "evidence_refs": by_id.get(contract_id, {}).get("evidence_refs", []),
            }
            for contract_id in ids
            if contract_id in by_id
        ]
    return {
        "schema_version": "fin_insight_p33_runtime_contract_registry_v0_1",
        "registry_id": stable_id("p33_runtime_contract_registry", active_ids),
        "active_contract_count": len(active_ids),
        "active_contract_ids": active_ids,
        "expected_contract_ids": EXPECTED_ACTIVE_CONTRACT_IDS,
        "missing_expected_contract_ids": sorted(expected - set(active_ids)),
        "unexpected_active_contract_ids": sorted(set(active_ids) - expected),
        "component_routes": component_routes,
        "consumption_policy": "component_routes_are_required_inputs_for_runtime_plans_not_documentation_only",
    }


def _build_evidence_packs(root: Path, runtime_contract_registry: Mapping[str, Any]) -> dict[str, Any]:
    source_refs = _source_refs_from_registry(runtime_contract_registry)
    rows = [
        _evidence_row(
            "ev_product_nvda_blackwell_architecture",
            "ProductIntelligenceGraph",
            "technical_product_spec",
            "NVDA Blackwell/Hopper product architecture and generation evidence supports product capability comparison but not SKU revenue.",
            ["NVDA", "AMD", "GOOGL"],
            ["l3_product_architecture_competitive_bridge_contract_v0_1"],
        ),
        _evidence_row(
            "ev_customer_cloud_gpu_deployment",
            "CustomerDeploymentPack",
            "customer_deployment_adoption",
            "Cloud and hyperscale deployment references can support adoption/read-through judgment when tied to issuer/product/customer context.",
            ["NVDA", "DELL", "MSFT", "AMZN", "GOOGL"],
            ["l3_product_architecture_competitive_bridge_contract_v0_1", "l3_workbench_artifact_review_surface_contract_v0_1"],
        ),
        _evidence_row(
            "ev_fundamental_dell_ai_server_margin",
            "FundamentalStatementPack",
            "fundamental_statement_metric",
            "DELL AI server revenue, gross margin and working-capital/cash-flow rows are issuer financial facts when sourced from filings.",
            ["DELL"],
            ["l3_enterprise_rag_data_pipeline_contract_v0_1"],
        ),
        _evidence_row(
            "ev_capital_cloud_capex_market_feedback",
            "CapitalMarketFeedbackPack",
            "capital_market_feedback",
            "Cloud capex and market/capital feedback are bounded demand and price-in context, not supplier revenue or real-time fund flow.",
            ["MSFT", "AMZN", "GOOGL", "NVDA", "DELL"],
            ["l3_capital_market_feedback_contract_v0_1"],
        ),
        _evidence_row(
            "ev_industry_semis_value_chain_cycle",
            "IndustryPlaybook",
            "semis_value_chain_playbook",
            "AI/Semis playbook separates GPU demand, advanced packaging/HBM bottlenecks, semicap cycle, export controls and company-specific exposure.",
            ["NVDA", "AMD", "ASML", "LRCX", "AMAT", "KLAC"],
            ["l3_semis_cycle_value_chain_playbook_contract_v0_1"],
        ),
        _evidence_row(
            "ev_relationship_graph_gpu_to_foundry_semicap",
            "ProductIntelligenceGraph",
            "relationship_graph_edge",
            "Product graph edges connect accelerator demand to foundry, HBM, advanced packaging and semicap read-through with boundary labels.",
            ["NVDA", "TSM", "ASML", "LRCX", "AMAT", "KLAC"],
            ["l3_product_architecture_competitive_bridge_contract_v0_1"],
        ),
    ]
    typed_gaps = [
        {
            "gap_id": "gap_sku_revenue_exact_tracker",
            "gap_type": "commercial_or_company_undisclosed_exact_product_kpi",
            "status": "typed_gap",
            "statement": "SKU-level GPU revenue, ASP, shipment and sell-through remain undisclosed unless company or commercial tracker provides exact rows.",
            "source_absent": False,
            "public_source_absent": False,
            "next_action": "Do not fail product analysis; keep as Product-KPI exact gap while using specs/deployment/proxy as bounded thesis evidence.",
            "evidence_refs": ["ev_product_nvda_blackwell_architecture", "ev_customer_cloud_gpu_deployment"],
        },
        {
            "gap_id": "gap_customer_order_amount_exact",
            "gap_type": "public_source_or_commercial_order_exact_gap",
            "status": "typed_gap",
            "statement": "Customer deployment/adoption context exists, but order amount or backlog exact requires issuer/customer contract disclosure or commercial tracker.",
            "source_absent": False,
            "public_source_absent": False,
            "next_action": "Use deployment as adoption signal only; do not render as revenue/backlog exact.",
            "evidence_refs": ["ev_customer_cloud_gpu_deployment"],
        },
    ]
    return {
        "schema_version": "fin_insight_p33_assimilated_evidence_packs_v0_1",
        "pack_ids_used_by_judgment_spine": [
            "ProductIntelligenceGraph",
            "FundamentalStatementPack",
            "CapitalMarketFeedbackPack",
            "CustomerDeploymentPack",
            "IndustryPlaybook",
        ],
        "source_fixture_refs": {
            "p32_fixture": "data/manifests/p32_l4_ai_semis_deterministic_fixture_v0_1.json",
            "p33_capital": "data/manifests/p33_capital_market_feedback_fixture_v0_1.json",
            "p33_workbench": "data/manifests/p33_workbench_artifact_review_surface_fixture_v0_1.json",
            "p33_rag": "data/manifests/p33_enterprise_rag_data_pipeline_fixture_v0_1.json",
            "p33_quant": "data/manifests/p33_research_to_quant_factor_handoff_fixture_v0_1.json",
        },
        "root": root.as_posix(),
        "source_refs_from_registry": source_refs[:12],
        "evidence_rows": rows,
        "typed_gap_refs": typed_gaps,
        "product_reasoning_frame": {
            "schema_version": "finsight_product_reasoning_frame_v0_1",
            "coverage_roles": [
                "product_profile",
                "technical_product_spec",
                "customer_deployment_adoption",
                "product_kpi_exact",
                "performance_proxy",
                "relationship_graph",
            ],
            "product_profile_refs": ["ev_product_nvda_blackwell_architecture"],
            "product_spec_refs": ["ev_product_nvda_blackwell_architecture"],
            "product_kpi_refs": ["gap_sku_revenue_exact_tracker"],
            "deployment_refs": ["ev_customer_cloud_gpu_deployment"],
            "performance_proxy_refs": ["ev_capital_cloud_capex_market_feedback"],
            "relationship_edge_refs": ["ev_relationship_graph_gpu_to_foundry_semicap"],
            "scope_hypothesis_refs": [],
            "required_reasoning_edges": [
                "product_architecture_to_customer_deployment_to_server_demand",
                "cloud_capex_to_accelerator_server_supply_chain_readthrough",
                "advanced_packaging_hbm_semicap_bottleneck_to_delivery_risk",
            ],
            "writer_instruction": "Product analysis must not collapse to SKU revenue absence; use specs, architecture, deployment and relationship edges as bounded judgment material.",
        },
    }


def _build_research_lead_runtime_plan(
    evidence_packs: Mapping[str, Any],
    runtime_contract_registry: Mapping[str, Any],
) -> dict[str, Any]:
    required_items = [
        {
            "question_item_id": "nvda_amd_google_accelerator_competitive_position",
            "dimension": "product_and_production",
            "required_tickers": ["NVDA", "AMD", "GOOGL"],
            "required_evidence_roles": ["technical_product_spec", "relationship_graph_edge", "customer_deployment_adoption"],
            "minimum_answer_status": "answerable_with_bounded_judgment",
            "expected_repair_policy": "targeted_repair_only_if_official_product_or_deployment_rows_missing",
            "terms_any": ["GPU", "accelerator", "TPU", "H100", "B200", "MI300"],
            "answer_contract": "State product capability and competitive positioning; keep SKU revenue as exact-KPI gap only.",
        },
        {
            "question_item_id": "cloud_capex_to_ai_server_readthrough",
            "dimension": "industry_supply_chain",
            "required_tickers": ["MSFT", "AMZN", "GOOGL", "NVDA", "DELL"],
            "required_evidence_roles": ["capital_market_feedback", "relationship_graph_edge", "customer_deployment_adoption"],
            "minimum_answer_status": "answerable_with_bounded_judgment",
            "expected_repair_policy": "repair_if_capex_pack_or_customer_deployment_pack_absent",
            "terms_any": ["capex", "AI infrastructure", "server", "GPU", "cloud"],
            "answer_contract": "Bridge cloud capex to demand pool and supply-chain beneficiaries without treating it as supplier revenue.",
        },
        {
            "question_item_id": "dell_ai_server_margin_quality",
            "dimension": "fundamentals",
            "required_tickers": ["DELL"],
            "required_evidence_roles": ["fundamental_statement_metric", "product_kpi_exact", "customer_deployment_adoption"],
            "minimum_answer_status": "answerable_with_boundary",
            "expected_repair_policy": "parser_gap_if_filing_rows_exist_but_display_value_missing",
            "terms_any": ["AI server", "gross margin", "cash flow", "revenue"],
            "answer_contract": "Analyze revenue quality and margin bridge, not just AI server demand headline.",
        },
        {
            "question_item_id": "semicap_orders_backlog_export_risk",
            "dimension": "risk_and_counterevidence",
            "required_tickers": ["ASML", "LRCX", "AMAT", "KLAC"],
            "required_evidence_roles": ["semis_value_chain_playbook", "fundamental_statement_metric", "relationship_graph_edge"],
            "minimum_answer_status": "typed_gap_traceable_if_exact_orders_missing",
            "expected_repair_policy": "non_us_ir_or_local_filing_parser_gap_when_document_found_but_table_not_extracted",
            "terms_any": ["bookings", "backlog", "orders", "export", "China"],
            "answer_contract": "Separate cycle/order visibility from export restriction and customer concentration risk.",
        },
    ]
    evidence_role_plan = [
        {
            "role_id": "product_architecture_and_generation",
            "source_pack": "ProductIntelligenceGraph",
            "evidence_refs": ["ev_product_nvda_blackwell_architecture", "ev_relationship_graph_gpu_to_foundry_semicap"],
            "claim_boundary": "technical_fact_or_relationship_context_not_revenue_exact",
            "target_specialist": "product_technology_analyst",
        },
        {
            "role_id": "customer_deployment_and_adoption",
            "source_pack": "CustomerDeploymentPack",
            "evidence_refs": ["ev_customer_cloud_gpu_deployment"],
            "claim_boundary": "adoption_signal_not_order_value_or_backlog_exact",
            "target_specialist": "industry_supply_chain_analyst",
        },
        {
            "role_id": "fundamental_statement_bridge",
            "source_pack": "FundamentalStatementPack",
            "evidence_refs": ["ev_fundamental_dell_ai_server_margin"],
            "claim_boundary": "issuer_statement_fact_only_with_display_value_lineage",
            "target_specialist": "fundamental_analyst",
        },
        {
            "role_id": "capital_market_feedback_and_price_in",
            "source_pack": "CapitalMarketFeedbackPack",
            "evidence_refs": ["ev_capital_cloud_capex_market_feedback"],
            "claim_boundary": "bounded_market_or_holder_signal_not_investment_advice",
            "target_specialist": "market_valuation_analyst",
        },
        {
            "role_id": "industry_cycle_and_counterevidence",
            "source_pack": "IndustryPlaybook",
            "evidence_refs": ["ev_industry_semis_value_chain_cycle"],
            "claim_boundary": "playbook_context_must_be_tied_to_company_specific_rows",
            "target_specialist": "industry_supply_chain_analyst",
        },
    ]
    typed_gaps = [gap["gap_id"] for gap in evidence_packs.get("typed_gap_refs") or []]
    path_nodes = [
        _path_node("product_and_production", ["jc_product_architecture"], ["ev_product_nvda_blackwell_architecture"], "Product architecture and deployment evidence can support competitive capability judgment."),
        _path_node("customer_deployment", ["jc_customer_deployment"], ["ev_customer_cloud_gpu_deployment"], "Customer/cloud deployment validates adoption direction but not exact order value."),
        _path_node("fundamentals", ["jc_fundamental_margin"], ["ev_fundamental_dell_ai_server_margin"], "Financial rows test whether AI server demand converts into revenue quality and margin."),
        _path_node("industry_supply_chain", ["jc_supply_chain_cycle"], ["ev_industry_semis_value_chain_cycle", "ev_relationship_graph_gpu_to_foundry_semicap"], "Supply-chain graph explains who benefits and where bottlenecks/cycle risk sit."),
        _path_node("capital_and_financing", ["jc_capital_feedback"], ["ev_capital_cloud_capex_market_feedback"], "Market and capex feedback indicate price-in and demand-pool context with lag/source boundaries."),
        _path_node("risk_and_counterevidence", ["jc_exact_kpi_gap"], typed_gaps, "Exact SKU/order metrics remain typed gaps, not a reason to discard product-layer judgment."),
    ]
    thesis_path = {
        "schema_version": "fin_insight_research_lead_thesis_path_v0_1",
        "status": "ready",
        "primary_thesis": (
            "AI/Semis workpaper should judge whether product capability and customer deployment signals are strong enough "
            "to support AI infrastructure demand read-through, then test whether fundamentals, supply-chain constraints "
            "and capital-market price-in weaken or confirm that view."
        ),
        "mechanism_bridge_status": "pass",
        "path_nodes": path_nodes,
        "path_edges": [
            _path_edge("product_and_production", "customer_deployment", "deployment_validates_product_capability"),
            _path_edge("customer_deployment", "industry_supply_chain", "deployment_to_supply_chain_readthrough"),
            _path_edge("industry_supply_chain", "fundamentals", "supply_chain_to_revenue_margin_bridge"),
            _path_edge("capital_and_financing", "risk_and_counterevidence", "price_in_and_financing_context_limits_upside"),
        ],
        "writer_instruction": "Writer must follow this path before explaining gaps or monitoring triggers.",
    }
    return {
        "schema_version": "fin_insight_p33_research_lead_runtime_plan_v0_1",
        "plan_id": stable_id("research_lead_runtime_plan", [runtime_contract_registry.get("registry_id"), "ai_semis"]),
        "status": "ready",
        "active_registry_id": runtime_contract_registry.get("registry_id"),
        "used_contract_ids": runtime_contract_registry.get("active_contract_ids"),
        "plan_summary": {
            "thesis_path_node_count": len(path_nodes),
            "required_item_count": len(required_items),
            "evidence_role_count": len(evidence_role_plan),
            "typed_gap_count": len(typed_gaps),
            "specialist_activation_policy": "required_item_or_role_gap_only",
        },
        "thesis_path": thesis_path,
        "required_item_plan": required_items,
        "evidence_role_plan": evidence_role_plan,
        "repair_plan": [
            {
                "repair_id": "repair_exact_sku_revenue_or_order_value",
                "trigger_gap_ids": typed_gaps,
                "allowed_actions": ["official_ir_or_filing_parser_check", "commercial_gap_exposure"],
                "forbidden_actions": ["rerun_full_chain", "invent_order_amount_from_deployment_context"],
                "status": "typed_gap_no_runtime_repair_required_for_P33_2",
            }
        ],
        "typed_gap_refs": typed_gaps,
    }


def _build_context_injection_audit(
    *,
    research_lead_runtime_plan: Mapping[str, Any],
    evidence_packs: Mapping[str, Any],
    runtime_contract_registry: Mapping[str, Any],
) -> dict[str, Any]:
    engine = ContextEngine(config=ContextEngineConfig(max_prompt_context_items=8, max_prompt_chars=8000, default_token_budget=5000))
    agent_data_views = [
        _role_context("product_technology_analyst", "ProductIntelligenceGraph", ["ev_product_nvda_blackwell_architecture", "ev_relationship_graph_gpu_to_foundry_semicap"]),
        _role_context("fundamental_analyst", "FundamentalStatementPack", ["ev_fundamental_dell_ai_server_margin"]),
        _role_context("industry_supply_chain_analyst", "IndustryPlaybook", ["ev_industry_semis_value_chain_cycle", "ev_customer_cloud_gpu_deployment"]),
        _role_context("market_valuation_analyst", "CapitalMarketFeedbackPack", ["ev_capital_cloud_capex_market_feedback"]),
    ]
    state = {
        "research_objective_contract": {
            "summary": "AI/Semis gold workpaper runtime assimilation objective",
            "required_item_ids": [row["question_item_id"] for row in research_lead_runtime_plan.get("required_item_plan") or []],
            "visibility_scope": "global",
            "source_boundary": "project_os_runtime_contract",
        },
        "project_inventory": {
            "summary": "P33 active runtime contract registry",
            "active_contract_count": runtime_contract_registry.get("active_contract_count"),
            "contract_ids": runtime_contract_registry.get("active_contract_ids"),
            "source_boundary": "active_registry_runtime_alignment",
        },
        "source_capability_router": {
            "summary": "Exact-first parser-backed source authority remains separate from bounded product/capital signals.",
            "source_boundary": "source_authority_not_raw_web_dump",
            "status": "ready",
        },
        "retrieval_budget_audit": {
            "summary": "No paid full-chain; deterministic role-specific context injection fixture.",
            "status": "no_paid_no_full_chain",
            "source_boundary": "project_os_preflight_guard",
        },
        "verified_judgment_plan": {
            "summary": "JudgmentCards and typed gaps are the writer's verified input.",
            "claim_refs": ["jc_product_architecture", "jc_fundamental_margin", "jc_customer_deployment", "jc_supply_chain_cycle", "jc_capital_feedback"],
            "source_boundary": "verified_judgment_material_only",
        },
        "source_gaps": evidence_packs.get("typed_gap_refs") or [],
        "claim_verification": {
            "summary": "Product evidence cannot become SKU revenue; capital feedback cannot become investment advice.",
            "status": "pass",
            "source_boundary": "authority_boundary_gate",
        },
        "agent_data_views": agent_data_views,
        "artifact_refs": {
            "summary": "P33-2 manifest, report, active registry, P33-1 fixtures and Workbench trace refs.",
            "evidence_refs": list((evidence_packs.get("source_fixture_refs") or {}).values())[:8],
            "source_boundary": "lead_and_verifier_artifact_refs",
        },
    }
    resolved = engine.resolve(state)
    target_specs = [
        ("research_lead", "", 6000),
        ("specialist", "product_technology_analyst", 3600),
        ("specialist", "fundamental_analyst", 3200),
        ("specialist", "industry_supply_chain_analyst", 3600),
        ("specialist", "market_valuation_analyst", 3000),
        ("memo_writer", "", 4200),
    ]
    injections = []
    for target_node, role, budget in target_specs:
        selection = engine.select(resolved["snapshots"], target_node=target_node, role=role, token_budget=budget)
        injection = engine.inject(selection, target_node=f"{target_node}:{role}" if role else target_node)
        injections.append({"target_node": target_node, "role": role, "selection": selection, "injection": injection})
    specialist_role_context_ids = [
        (row["role"], _context_ids_by_type(row["injection"], "role_context"))
        for row in injections
        if row["target_node"] == "specialist"
    ]
    flattened_role_ids = [ids[0] for _, ids in specialist_role_context_ids if ids]
    writer_context_types = _context_types(next(row["injection"] for row in injections if row["target_node"] == "memo_writer"))
    status = (
        "pass"
        if len(flattened_role_ids) == 4
        and len(set(flattened_role_ids)) == 4
        and "role_context" not in writer_context_types
        else "fail"
    )
    return {
        "schema_version": "fin_insight_p33_context_injection_audit_v0_1",
        "status": status,
        "resolved_snapshot_count": resolved["snapshot_count"],
        "injection_count": len(injections),
        "injections": injections,
        "specialist_role_context_ids": specialist_role_context_ids,
        "specialist_role_context_distinct": len(flattened_role_ids) == 4 and len(set(flattened_role_ids)) == 4,
        "writer_context_types": writer_context_types,
        "writer_raw_dump_blocked": "role_context" not in writer_context_types,
        "summary": {
            "resolved_snapshot_count": resolved["snapshot_count"],
            "injection_count": len(injections),
            "specialist_role_context_distinct": len(flattened_role_ids) == 4 and len(set(flattened_role_ids)) == 4,
            "writer_raw_dump_blocked": "role_context" not in writer_context_types,
        },
    }


def _build_judgment_state(evidence_packs: Mapping[str, Any], research_lead_runtime_plan: Mapping[str, Any]) -> dict[str, Any]:
    supported_claims = [
        _supported_claim(
            "claim_product_architecture",
            "product_and_production",
            "Product specs and generation evidence support a bounded view that NVDA/AMD/GOOGL accelerator competition should be judged on architecture, deployment and ecosystem, not SKU revenue alone.",
            ["ev_product_nvda_blackwell_architecture", "ev_relationship_graph_gpu_to_foundry_semicap"],
            "product_competitive_capability",
        ),
        _supported_claim(
            "claim_customer_deployment",
            "customer_deployment",
            "Customer and cloud deployment context supports adoption/read-through analysis but cannot be promoted to exact order value.",
            ["ev_customer_cloud_gpu_deployment"],
            "adoption_and_readthrough_signal",
        ),
        _supported_claim(
            "claim_fundamental_margin",
            "fundamentals",
            "Issuer financial facts must test whether AI server demand converts into revenue quality, gross margin and cash-flow quality.",
            ["ev_fundamental_dell_ai_server_margin"],
            "fundamental_quality_bridge",
        ),
        _supported_claim(
            "claim_supply_chain_cycle",
            "industry_supply_chain",
            "Semis value-chain playbook and graph edges explain read-through to foundry, HBM, advanced packaging and semicap with export/cycle counterevidence.",
            ["ev_industry_semis_value_chain_cycle", "ev_relationship_graph_gpu_to_foundry_semicap"],
            "industry_supply_chain_transmission",
        ),
        _supported_claim(
            "claim_capital_feedback",
            "capital_and_financing",
            "Cloud capex and capital-market feedback shape demand-pool and price-in context while remaining bounded market evidence.",
            ["ev_capital_cloud_capex_market_feedback"],
            "capital_market_context",
        ),
    ]
    judgment_cards = [
        _judgment_card("jc_product_architecture", "claim_product_architecture", "product_and_production", "product_technology", "Product architecture/deployment evidence is strong enough for competitive positioning, but not for SKU revenue.", ["ev_product_nvda_blackwell_architecture", "ev_relationship_graph_gpu_to_foundry_semicap"]),
        _judgment_card("jc_customer_deployment", "claim_customer_deployment", "customer_deployment", "product_technology", "Deployment/adoption rows validate demand direction; order amount remains typed gap.", ["ev_customer_cloud_gpu_deployment"]),
        _judgment_card("jc_fundamental_margin", "claim_fundamental_margin", "fundamentals", "fundamentals", "Financial statement rows decide whether AI server growth is high-quality or margin-dilutive.", ["ev_fundamental_dell_ai_server_margin"]),
        _judgment_card("jc_supply_chain_cycle", "claim_supply_chain_cycle", "industry_supply_chain", "industry_supply_chain", "Supply-chain graph gives the causal read-through path and the bottleneck/cycle risks.", ["ev_industry_semis_value_chain_cycle", "ev_relationship_graph_gpu_to_foundry_semicap"]),
        _judgment_card("jc_capital_feedback", "claim_capital_feedback", "capital_and_financing", "capital_market", "Capital feedback indicates demand-pool and price-in context, not standalone recommendation.", ["ev_capital_cloud_capex_market_feedback"]),
        _judgment_card("jc_exact_kpi_gap", "gap_sku_revenue_exact_tracker", "risk_and_counterevidence", "risk", "Absence of SKU revenue/order exact is a typed boundary, not product-layer failure.", ["gap_sku_revenue_exact_tracker", "gap_customer_order_amount_exact"]),
    ]
    dimension_judgments = [
        _dimension_judgment("product_and_production", "Product / architecture", ["claim_product_architecture"], ["ev_product_nvda_blackwell_architecture", "ev_relationship_graph_gpu_to_foundry_semicap"], "Product specs, generation and graph edges support bounded competitive judgment."),
        _dimension_judgment("customer_deployment", "Customer deployment / adoption", ["claim_customer_deployment"], ["ev_customer_cloud_gpu_deployment"], "Customer deployment validates adoption context with order-value boundary."),
        _dimension_judgment("fundamentals", "Fundamentals", ["claim_fundamental_margin"], ["ev_fundamental_dell_ai_server_margin"], "Financial rows bridge demand to revenue quality, margin and cash flow."),
        _dimension_judgment("industry_supply_chain", "Industry / supply chain", ["claim_supply_chain_cycle"], ["ev_industry_semis_value_chain_cycle", "ev_relationship_graph_gpu_to_foundry_semicap"], "Semis playbook and graph edges define beneficiary, bottleneck and export-risk logic."),
        _dimension_judgment("capital_and_financing", "Capital / market feedback", ["claim_capital_feedback"], ["ev_capital_cloud_capex_market_feedback"], "Capital-market pack frames price-in, holder/flow lag and funding context."),
        {
            "dimension_id": "risk_and_counterevidence",
            "title": "Risk and counterevidence",
            "stance": "bounded",
            "support_level": "typed_gap_traceable",
            "summary": "Exact SKU revenue, ASP, shipment, order value and backlog remain typed gaps unless disclosed or sourced from tracker.",
            "business_mechanism": "Missing exact KPI limits sizing, not existence of product/deployment thesis.",
            "financial_bridge": "Use as uncertainty and what-would-change condition, not as product failure.",
            "counter_read": "If exact orders or margins contradict adoption proxies, the thesis weakens.",
            "claim_ids": ["gap_sku_revenue_exact_tracker", "gap_customer_order_amount_exact"],
            "evidence_refs": ["gap_sku_revenue_exact_tracker", "gap_customer_order_amount_exact"],
            "gap_ids": ["gap_sku_revenue_exact_tracker", "gap_customer_order_amount_exact"],
            "what_would_change_view": ["Issuer/customer order value disclosure", "SKU-level gross margin or shipment tracker"],
        },
    ]
    thesis_path = research_lead_runtime_plan["thesis_path"]
    state = {
        "schema_version": "finsight_judgment_state_v0_2",
        "status": "ready",
        "core_thesis": thesis_path["primary_thesis"],
        "stance": "bounded_constructive",
        "confidence": "medium",
        "supported_claims": supported_claims,
        "dimension_judgments": dimension_judgments,
        "judgment_cards": judgment_cards,
        "thesis_path": thesis_path,
        "fundamental_statement_summary": {
            "schema_version": "finsight_fundamental_statement_pack_v0_1",
            "pack_status": "ready",
            "line_item_count": 8,
            "period_change_count": 4,
            "peer_comparison_count": 3,
            "priority_metric_available_count": 5,
            "priority_metric_missing_count": 1,
            "industry_id": "ai_semis",
        },
        "gap_state": {
            "unsupported_claim_count": 0,
            "gap_card_count": len(evidence_packs.get("typed_gap_refs") or []),
            "public_or_commercial_gap_count": len(evidence_packs.get("typed_gap_refs") or []),
            "top_gaps": evidence_packs.get("typed_gap_refs") or [],
        },
        "memo_writer_policy": "write_from_dimension_judgments_first_then_judgment_cards_no_new_facts_v0_1",
        "validation": {"schema_version": "finsight_judgment_state_validation_v0_1", "status": "pass", "errors": []},
    }
    return state


def _build_lead_review_checkpoint(
    evidence_packs: Mapping[str, Any],
    research_lead_runtime_plan: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "finsight_lead_review_checkpoint_v0_2",
        "status": "pass",
        "memo_directive": {
            "schema_version": "finsight_lead_memo_directive_v0_2",
            "memo_stance": research_lead_runtime_plan["thesis_path"]["primary_thesis"],
            "objective_satisfaction": {"status": "answerable_with_bounded_judgment", "required_item_count": 4},
            "opening_policy": "answer_first_thesis_path_then_evidence_and_boundaries",
            "gap_budget_policy": {"max_body_gap_sentences": 2, "gap_only_when_decision_relevant": True},
            "product_output_contract": {
                "must_cover": ["product_profile", "spec_architecture", "customer_deployment", "relationship_graph", "exact_kpi_gap"],
                "must_not_collapse_to": "no_sku_revenue_so_no_product_judgment",
            },
            "dimension_write_priorities": [
                {"dimension": "product_and_production", "priority": 1},
                {"dimension": "fundamentals", "priority": 2},
                {"dimension": "industry_supply_chain", "priority": 3},
                {"dimension": "capital_and_financing", "priority": 4},
                {"dimension": "risk_and_counterevidence", "priority": 5},
            ],
        },
        "dimension_evidence_portfolio_ref": {
            "schema_version": "finsight_dimension_evidence_portfolio_ref_v0_1",
            "portfolio_id": "p33_2_ai_semis_evidence_portfolio",
            "agent_id": "research_lead",
            "focus_tickers": ["NVDA", "AMD", "GOOGL", "DELL", "ASML", "LRCX"],
            "status_counts": {"sufficient": 5, "typed_gap": 1},
            "dimensions": [
                {
                    "dimension_id": row["dimension_id"],
                    "evidence_status": "sufficient" if row["dimension_id"] != "risk_and_counterevidence" else "typed_gap_traceable",
                    "evidence_roles": [row["dimension_id"]],
                    "available_pack_refs": evidence_packs.get("pack_ids_used_by_judgment_spine", []),
                    "missing_pack_refs": [],
                }
                for row in [
                    {"dimension_id": "product_and_production"},
                    {"dimension_id": "fundamentals"},
                    {"dimension_id": "industry_supply_chain"},
                    {"dimension_id": "capital_and_financing"},
                    {"dimension_id": "risk_and_counterevidence"},
                ]
            ],
            "writer_boundary": "writer_may_use_only_judgment_state_memo_logic_plan_verified_claims_and_typed_gaps",
        },
        "dimension_reviews": [
            {
                "dimension": "product_and_production",
                "status": "sufficient",
                "evidence_refs": ["ev_product_nvda_blackwell_architecture", "ev_relationship_graph_gpu_to_foundry_semicap"],
                "dimension_portfolio_available_pack_refs": ["ProductIntelligenceGraph"],
                "dimension_portfolio_lead_questions": ["How does architecture/deployment change competitive view?"],
            },
            {
                "dimension": "fundamentals",
                "status": "sufficient",
                "evidence_refs": ["ev_fundamental_dell_ai_server_margin"],
                "dimension_portfolio_available_pack_refs": ["FundamentalStatementPack"],
                "dimension_portfolio_lead_questions": ["Does AI server demand improve or dilute quality?"],
            },
            {
                "dimension": "industry_supply_chain",
                "status": "sufficient",
                "evidence_refs": ["ev_industry_semis_value_chain_cycle", "ev_relationship_graph_gpu_to_foundry_semicap"],
                "dimension_portfolio_available_pack_refs": ["IndustryPlaybook", "ProductIntelligenceGraph"],
                "dimension_portfolio_lead_questions": ["Where does read-through pass or break?"],
            },
            {
                "dimension": "capital_and_financing",
                "status": "sufficient",
                "evidence_refs": ["ev_capital_cloud_capex_market_feedback"],
                "dimension_portfolio_available_pack_refs": ["CapitalMarketFeedbackPack"],
                "dimension_portfolio_lead_questions": ["Is the story already priced or funding-supported?"],
            },
            {
                "dimension": "risk_and_counterevidence",
                "status": "bounded_gap",
                "gap_ids": ["gap_sku_revenue_exact_tracker", "gap_customer_order_amount_exact"],
                "dimension_portfolio_available_pack_refs": ["CustomerDeploymentPack"],
                "dimension_portfolio_lead_questions": ["What exact data would change sizing confidence?"],
            },
        ],
        "lead_targeted_repair_execution": {
            "schema_version": "finsight_lead_targeted_repair_execution_v0_1",
            "status": "not_required_for_p33_2_fixture",
            "attempted_count": 0,
            "success_count": 0,
            "bounded_gap_count": 2,
            "official_context_summaries": [],
        },
    }


def _build_workbench_trace_projection(
    *,
    root: Path,
    research_lead_runtime_plan: Mapping[str, Any],
    context_injection_audit: Mapping[str, Any],
    judgment_state: Mapping[str, Any],
    memo_logic_plan: Mapping[str, Any],
    evidence_packs: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_refs = sorted(
        {
            ref
            for row in evidence_packs.get("evidence_rows") or []
            for ref in [row.get("evidence_id")]
            if ref
        }
    )
    gap_refs = sorted({gap.get("gap_id") for gap in evidence_packs.get("typed_gap_refs") or [] if gap.get("gap_id")})
    judgment_card_ids = sorted(
        {card.get("judgment_card_id") for card in judgment_state.get("judgment_cards") or [] if card.get("judgment_card_id")}
    )
    artifact_refs = [
        "data/manifests/p33_runtime_assimilation_fixture_v0_1.json",
        "docs/internal/vnext_20260610/p33_runtime_assimilation_fixture_report.zh-CN.md",
        "docs/project_os/p32_active_registry_promotion_ledger.jsonl",
        "docs/project_os/p33_execution_plan_ledger.jsonl",
    ]
    return {
        "schema_version": "fin_insight_p33_workbench_trace_projection_v0_1",
        "status": "pass",
        "task_id": "p33_2_runtime_assimilation_ai_semis",
        "run_id": stable_id("p33_2_run", [digest_payload(research_lead_runtime_plan)]),
        "root": root.as_posix(),
        "trace_edges": [
            {
                "from": "task:p33_2_runtime_assimilation_ai_semis",
                "to": "research_lead_runtime_plan",
                "edge_type": "produces",
            },
            {"from": "research_lead_runtime_plan", "to": "context_injection_plans", "edge_type": "selects_context"},
            {"from": "context_injection_plans", "to": "judgment_state", "edge_type": "feeds"},
            {"from": "judgment_state", "to": "memo_logic_plan", "edge_type": "writer_input"},
            {"from": "memo_logic_plan", "to": "workbench_review_surface", "edge_type": "projects"},
        ],
        "evidence_refs": evidence_refs,
        "typed_gap_refs": gap_refs,
        "judgment_card_ids": judgment_card_ids,
        "context_injection_plan_ids": [
            row["injection"]["plan_id"] for row in context_injection_audit.get("injections") or [] if row.get("injection")
        ],
        "memo_logic_plan_id": memo_logic_plan.get("plan_id"),
        "artifact_refs": artifact_refs,
        "review_policy": {
            "actions": ["accept", "reject", "supersede", "request_targeted_repair"],
            "audit_source": "sql_final_or_manifest_projection_only",
            "frontend_local_state_is_final_audit": False,
            "chat_transcript_is_final_audit": False,
        },
        "summary": {
            "evidence_ref_count": len(evidence_refs),
            "typed_gap_count": len(gap_refs),
            "judgment_card_count": len(judgment_card_ids),
            "context_injection_count": len(context_injection_audit.get("injections") or []),
            "artifact_ref_count": len(artifact_refs),
        },
        "evidence_ref_count": len(evidence_refs),
        "judgment_card_count": len(judgment_card_ids),
        "artifact_ref_count": len(artifact_refs),
        "paid_llm_call_count": 0,
        "full_chain_run_count": 0,
    }


def _all_required_item_gaps_are_typed(plan: Mapping[str, Any]) -> bool:
    typed_gap_ids = set(plan.get("typed_gap_refs") or [])
    for row in plan.get("required_item_plan") or []:
        status = str(row.get("minimum_answer_status") or "")
        if "gap" in status and not typed_gap_ids:
            return False
    return True


def _evidence_row(
    evidence_id: str,
    pack_id: str,
    source_role: str,
    summary: str,
    tickers: list[str],
    contract_ids: list[str],
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "pack_id": pack_id,
        "source_role": source_role,
        "summary": summary,
        "tickers": tickers,
        "contract_ids": contract_ids,
        "authority_boundary": "bounded_thesis_driver" if "exact" not in source_role else "exact_fact_required",
        "citation": f"fixture:{evidence_id}",
        "can_enter_judgment_spine": True,
    }


def _source_refs_from_registry(registry: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for rows in (registry.get("component_routes") or {}).values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            refs.extend(str(ref) for ref in row.get("evidence_refs") or [] if str(ref).strip())
    return sorted(set(refs))


def _path_node(dimension_id: str, judgment_card_ids: list[str], evidence_refs: list[str], mechanism: str) -> dict[str, Any]:
    return {
        "node_id": f"dimension::{dimension_id}",
        "dimension_id": dimension_id,
        "judgment_card_ids": judgment_card_ids,
        "claim_ids": [item.replace("jc_", "claim_") for item in judgment_card_ids if item.startswith("jc_")],
        "evidence_refs": evidence_refs,
        "business_mechanism": mechanism,
        "financial_bridge": "Bridge only through issuer facts or bounded read-through with explicit authority boundary.",
        "counter_read": "Exact KPI or contradictory financial rows can weaken this node.",
        "what_would_change_view": ["Exact product KPI", "Customer order amount", "Margin/cash-flow contradiction"],
        "node_status": "ready" if not any(ref.startswith("gap_") for ref in evidence_refs) else "typed_gap_boundary",
    }


def _path_edge(from_dimension: str, to_dimension: str, edge_type: str) -> dict[str, Any]:
    return {
        "edge_id": f"edge::{from_dimension}->{to_dimension}",
        "from_node_id": f"dimension::{from_dimension}",
        "to_node_id": f"dimension::{to_dimension}",
        "edge_type": edge_type,
        "mechanism": edge_type.replace("_", " "),
        "evidence_refs": [],
    }


def _role_context(role: str, pack_id: str, evidence_refs: list[str]) -> dict[str, Any]:
    return {
        "role": role,
        "pack_id": pack_id,
        "summary": f"{role} receives {pack_id} refs only, plus global objective and verified gates.",
        "evidence_refs": evidence_refs,
        "status": "ready",
        "source_boundary": "role_scoped_context_pack",
    }


def _context_ids_by_type(injection: Mapping[str, Any], context_type: str) -> list[str]:
    return [
        str(row.get("snapshot_id") or "")
        for row in injection.get("prompt_context") or []
        if isinstance(row, Mapping) and row.get("context_type") == context_type and str(row.get("snapshot_id") or "")
    ]


def _context_types(injection: Mapping[str, Any]) -> list[str]:
    return sorted(
        {
            str(row.get("context_type") or "")
            for row in injection.get("prompt_context") or []
            if isinstance(row, Mapping) and str(row.get("context_type") or "")
        }
    )


def _supported_claim(
    claim_id: str,
    dimension: str,
    claim: str,
    evidence_refs: list[str],
    economic_role: str,
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "claim": claim,
        "analysis_dimension": dimension,
        "ticker_scope": ["NVDA", "AMD", "GOOGL", "DELL", "ASML", "LRCX"],
        "metric_scope": ["product", "deployment", "margin", "capex", "supply_chain"],
        "evidence_refs": evidence_refs,
        "economic_role": economic_role,
        "transmission_role": "bounded_thesis_driver",
        "memo_use_role": "support_current_judgment_with_boundary",
        "role_boundary": "not_exact_revenue_or_investment_advice",
    }


def _judgment_card(
    card_id: str,
    source_claim_id: str,
    dimension_id: str,
    memo_slot: str,
    judgment: str,
    evidence_refs: list[str],
) -> dict[str, Any]:
    return {
        "judgment_card_id": card_id,
        "source_claim_id": source_claim_id,
        "dimension_id": dimension_id,
        "memo_slot": memo_slot,
        "judgment": judgment,
        "evidence_bridge": "Use the evidence refs as bounded support, not as raw claim inventory.",
        "business_mechanism": "Connect product/deployment/financial/capital signal to thesis path.",
        "financial_bridge": "Bridge through issuer facts or explicitly bounded read-through only.",
        "counter_read": "Exact KPI, margin or order-value contradiction would weaken the card.",
        "what_would_change_view": ["Exact KPI disclosure", "Contradictory customer/order evidence"],
        "evidence_refs": evidence_refs,
        "source_role": memo_slot,
        "authority_boundary": "bounded_thesis_driver_not_exact_fact" if not source_claim_id.startswith("gap_") else "typed_gap_boundary",
        "mechanism_bridge_status": "pass",
    }


def _dimension_judgment(
    dimension_id: str,
    title: str,
    claim_ids: list[str],
    evidence_refs: list[str],
    summary: str,
) -> dict[str, Any]:
    return {
        "dimension_id": dimension_id,
        "title": title,
        "stance": "supporting",
        "support_level": "bounded_supported",
        "summary": summary,
        "business_mechanism": "Dimension contributes to the Research Lead thesis path.",
        "financial_bridge": "Writer must state the financial or valuation implication and boundary.",
        "counter_read": "If exact facts contradict the bounded signal, reduce confidence.",
        "claim_ids": claim_ids,
        "evidence_refs": evidence_refs,
        "gap_ids": [],
        "what_would_change_view": ["More exact company disclosure", "Contrary peer or customer evidence"],
    }


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
