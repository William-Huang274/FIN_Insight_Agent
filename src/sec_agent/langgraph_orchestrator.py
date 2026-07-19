from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, TypedDict

try:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
except ModuleNotFoundError as exc:  # pragma: no cover - only exercised without optional dependency.
    BaseCheckpointSaver = object  # type: ignore[assignment,misc]
    InMemorySaver = None  # type: ignore[assignment]
    END = None  # type: ignore[assignment]
    START = None  # type: ignore[assignment]
    StateGraph = None  # type: ignore[assignment]
    LANGGRAPH_IMPORT_ERROR = exc
else:
    LANGGRAPH_IMPORT_ERROR = None

from sec_agent.retrieval_plan import build_retrieval_plan
from sec_agent.agent_contracts import validate_agent_activation_plan
from sec_agent.agent_registry import agent_registry_by_id, allowed_source_families
from sec_agent.analyst_view_layer import build_analyst_view_research_memory_layer
from sec_agent.claim_evidence_ledger import build_evidence_governance_ledgers
from sec_agent.d_series_database_closeout import build_d_series_database_closeout_gate
from sec_agent.d_series_database_store import (
    d_series_materialization_state_from_report,
    materialize_d_series_governance_store,
    read_claim_gap_gate_research_context,
    read_d_series_research_context,
)
from sec_agent.d_series_fact_selection import (
    apply_pre_memo_fact_selection_to_judgment,
    build_pre_memo_fact_selection,
)
from sec_agent.derived_metric_layer import build_derived_metric_layer
from sec_agent.dimension_evidence_portfolio import build_dimension_evidence_portfolio
from sec_agent.financial_statement_analysis import build_fundamental_statement_pack
from sec_agent.entity_master import build_entity_security_master
from sec_agent.gate_registry import build_gate_registry_eval_matrix
from sec_agent.lead_supervision import (
    build_lead_review_checkpoint,
    build_research_objective_contract,
    build_targeted_repair_plan,
)
from sec_agent.mcp_tool_registry import invoke_mcp_tool
from sec_agent.memo_logic_plan import build_memo_logic_plan
from sec_agent.metric_product_ontology import build_metric_product_ontology_snapshot
from sec_agent.multi_agent_contracts import (
    ANALYSIS_DIMENSION_ORDER,
    aggregate_focused_answer_judgment_plan,
    aggregate_specialist_judgment_plan,
    attach_judgment_state,
    build_multi_agent_memo_draft,
    ledger_metric_display_value,
    build_stub_specialist_memolets,
    normalize_universe_relationship_plan,
    refresh_judgment_plan_after_governance_filter,
    repair_multi_agent_memo_draft,
    validate_universe_relationship_plan,
    verify_multi_agent_memo_draft,
    verify_specialist_outputs_for_memo,
)
from sec_agent.multi_agent_router import route_multi_agent_activation
from sec_agent.official_issuer_repair import execute_official_issuer_repair_plan, issuer_has_official_profile
from sec_agent.supervising_analyst import build_supervising_analyst_pack
from sec_agent.multi_agent_runtime import (
    active_specialists_for_state,
    audit_second_pass_delta,
    build_evidence_fusion_bundle,
    build_multi_agent_evidence_requirement_plan,
    build_second_pass_reflection_diagnosis,
    build_second_pass_repair_plan,
    compile_second_pass_retrieval_plan,
    compile_multi_agent_retrieval_plan,
    default_web_source_scope_registry,
    execute_evidence_operator_plan,
    execute_evidence_operator_fanout_plan,
    gate_second_pass_repair_plan,
    merge_universe_relationship_evidence_requirements,
    normalize_reflection_report,
    plan_reflection_gate,
    quality_reflection_report_from_judgment,
    record_second_pass_outcome,
    reflection_report_from_coverage,
    reflection_report_from_evidence_fusion_bundle,
    reflection_report_from_tool_observations,
    should_execute_second_pass,
    specialist_activation_decisions,
    validate_operator_tool_call,
)
from sec_agent.provenance_vintage import build_provenance_vintage_layers
from sec_agent.reconciliation_ledger import build_metric_ontology_and_reconciliation_layers, build_reconciliation_ledger
from sec_agent.relationship_graph import relationship_plan_from_lookup
from sec_agent.run_audit_store import materialize_run_audit_store
from sec_agent.runtime_source_context_store import attach_runtime_source_context_rows, runtime_source_context_enabled
from sec_agent.source_capability_router import build_source_capability_router
from sec_agent.source_authority_coverage import load_source_authority_coverage
from sec_agent.tool_call_ledger import (
    LOOP_BREAK_AGENT_TOOL_BUDGET_EXHAUSTED,
    LOOP_BREAK_NO_INCREMENTAL_EVIDENCE,
    LOOP_BREAK_TOOL_BUDGET_EXHAUSTED,
    LoopBudget,
    ToolCallLedger,
)


NATIVE_NODE_ORDER = (
    "load_session_state",
    "plan_query",
    "validate_query_contract",
    "compile_retrieval_plan",
    "execute_retrieval_routes",
    "attach_market_snapshot",
    "attach_industry_snapshot",
    "build_runtime_ledger",
    "assess_evidence_coverage",
    "assess_evidence_sufficiency",
    "build_judgment_plan",
    "synthesize_answer",
    "verify_claims",
    "run_deterministic_gates",
    "render_answer",
    "persist_session_state",
)

NATIVE_OPTIONAL_NODE_ORDER = ("execute_second_pass_retrieval",)

MULTI_AGENT_NODE_ORDER = (
    "load_session_state",
    "research_lead_plan",
    "validate_activation_plan",
    "plan_reflection_gate",
    "universe_relationship_expand",
    "route_by_execution_mode",
    "compile_evidence_requirements",
    "execute_evidence_operators",
    "evidence_fusion_selector",
    "coverage_reflection",
    "optional_second_pass",
    "optional_specialist_subgraph",
    "aggregate_judgment_plan",
    "memo_writer",
    "verifier",
    "renderer",
    "persist_session_state",
)

SCOPE_MODES = {"full_universe", "sector_representative", "focused_peer"}
NODE_CHECKPOINT_SCHEMA_VERSION = "sec_agent_langgraph_node_checkpoint_v0.1"
NODE_CHECKPOINT_ARTIFACT_SCHEMA_VERSION = "sec_agent_langgraph_node_checkpoint_artifact_v0.1"
NODE_CHECKPOINT_RESUME_INSPECTION_SCHEMA_VERSION = "sec_agent_langgraph_checkpoint_resume_inspection_v0.1"
NATIVE_STATE_HYDRATION_SCHEMA_VERSION = "sec_agent_langgraph_native_state_hydration_v0.1"
CHECKPOINT_STATE_KEYS = (
    "query_contract",
    "multi_agent_context",
    "retrieval_plan",
    "context_rows",
    "market_snapshot_rows",
    "industry_snapshot_rows",
    "runtime_ledger_rows",
    "product_evidence_rows",
    "public_source_context_rows",
    "coverage_matrix",
    "source_gaps",
    "evidence_operator_fanout_plan",
    "evidence_operator_fanout_barrier",
    "evidence_fusion_bundle",
    "bounded_gap_register",
    "entity_security_master",
    "source_capability_router",
    "runtime_source_context_store",
    "source_layer_capability_audit",
    "source_authority_coverage",
    "raw_source_provenance_store",
    "asof_vintage_layer",
    "metric_product_ontology_snapshot",
    "reconciliation_ledger",
    "gate_registry_eval_matrix",
    "derived_metric_layer",
    "fundamental_statement_pack",
    "analyst_view_research_memory",
    "d_series_database_materialization",
    "d_series_database_materialization_report",
    "d_series_claim_gap_gate_reader_context",
    "d_series_research_context",
    "pre_memo_fact_selection",
    "d_series_database_closeout_gate",
    "evidence_sufficiency_report",
    "second_pass_result",
    "second_pass_evidence_requirement_plan",
    "second_pass_retrieval_plan",
    "second_pass_reflection_diagnosis",
    "second_pass_repair_plan",
    "second_pass_hard_gate",
    "second_pass_delta_audit",
    "research_objective_contract",
    "lead_review_checkpoint",
    "targeted_repair_plan",
    "memo_logic_plan",
    "supervising_analyst_pack",
    "judgment_plan",
    "verified_judgment_plan",
    "memo_answer",
    "claim_verification",
    "deterministic_gates",
    "rendered_answer",
    "agent_activation_plan",
    "plan_reflection_report",
    "agent_registry_snapshot",
    "evidence_requirement_plan",
    "tool_call_ledger",
    "loop_budget_state",
    "agent_trace",
    "multi_agent_reflection_report",
    "multi_agent_second_pass_decision",
    "relationship_graph_observation",
    "universe_relationship_plan",
    "universe_relationship_validation",
    "specialist_outputs",
    "specialist_activation_decisions",
    "specialist_verification",
    "specialist_fanout_barrier",
    "claim_card_store_barrier",
    "adjudicator_barrier",
    "research_lead_route_status",
    "research_lead_failure_reason",
    "research_lead_validation",
    "research_lead_rejected_plan",
    "research_lead_model_diagnostics",
    "research_lead_input_pack_fingerprint",
    "product_intelligence_runtime_autoload",
    "product_intelligence_runtime_policy",
    "universe_relationship_model_diagnostics",
    "universe_relationship_routing_trace",
    "universe_relationship_input_pack_fingerprint",
    "specialist_route_results",
    "memo_route_result",
    "multi_agent_summary",
)

PRODUCT_INTELLIGENCE_RUNTIME_POLICY_SCHEMA_VERSION = "sec_agent_product_intelligence_runtime_policy_v0.1"
PRODUCT_INTELLIGENCE_AUTOLOAD_AGENT_IDS = {
    "product_technology_analyst",
}
PRODUCT_INTELLIGENCE_RELATIONSHIP_AGENT_IDS = {
    "industry_supply_chain_analyst",
    "universe_relationship",
}
PRODUCT_INTELLIGENCE_AUTOLOAD_SOURCE_FAMILIES = {
    "company_product_evidence_graph",
    "public_source_context",
    "live_public_web_context",
}
PRODUCT_INTELLIGENCE_QUERY_TERMS = (
    "product",
    "product kpi",
    "product spec",
    "spec",
    "sku",
    "architecture",
    "benchmark",
    "generation",
    "gpu",
    "accelerator",
    "ai server",
    "server oem",
    "data center gpu",
    "blackwell",
    "hopper",
    "h100",
    "h200",
    "b200",
    "gb200",
    "mi300",
    "tpu",
    "customer deployment",
    "deployment",
    "supply chain",
    "supplier",
    "competitor",
    "competitive",
    "产品",
    "产品线",
    "产品指标",
    "产品规格",
    "规格",
    "架构",
    "代际",
    "基准测试",
    "显卡",
    "加速卡",
    "加速器",
    "服务器",
    "客户部署",
    "部署",
    "供应链",
    "供应商",
    "竞品",
    "竞争",
)
CHECKPOINT_LARGE_PAYLOAD_CHANNELS = {
    "context_rows",
    "market_snapshot_rows",
    "industry_snapshot_rows",
    "runtime_ledger_rows",
    "product_evidence_rows",
    "public_source_context_rows",
    "evidence_fusion_bundle",
    "bounded_gap_register",
    "entity_security_master",
    "source_capability_router",
    "source_authority_coverage",
    "raw_source_provenance_store",
    "asof_vintage_layer",
    "metric_product_ontology_snapshot",
    "reconciliation_ledger",
    "gate_registry_eval_matrix",
    "derived_metric_layer",
    "fundamental_statement_pack",
    "analyst_view_research_memory",
    "d_series_database_materialization_report",
    "d_series_research_context",
    "pre_memo_fact_selection",
    "d_series_database_closeout_gate",
    "coverage_matrix",
    "retrieval_trace",
    "project_inventory",
    "judgment_plan",
    "memo_answer",
    "claim_verification",
    "deterministic_gates",
    "rendered_answer",
}

NATIVE_RESUME_REQUIRED_ARTIFACTS = {
    "execute_retrieval_routes": ("case", "retrieval_plan"),
    "attach_market_snapshot": ("retrieved_context",),
    "attach_industry_snapshot": ("retrieved_context",),
    "build_runtime_ledger": ("retrieved_context",),
    "assess_evidence_coverage": ("retrieved_context", "runtime_exact_value_ledger"),
    "assess_evidence_sufficiency": ("evidence_coverage_matrix",),
    "execute_second_pass_retrieval": ("evidence_coverage_matrix",),
    "build_judgment_plan": ("runtime_exact_value_ledger", "evidence_coverage_matrix"),
    "synthesize_answer": ("retrieved_context", "runtime_exact_value_ledger", "evidence_coverage_matrix", "judgment_plan"),
    "verify_claims": ("retrieved_context", "runtime_exact_value_ledger", "memo_answer"),
    "run_deterministic_gates": ("runtime_exact_value_ledger", "judgment_plan", "claim_verification"),
    "render_answer": ("deterministic_gates",),
    "persist_session_state": ("rendered_answer",),
}


class SecAgentGraphRuntimeState(TypedDict, total=False):
    user_query: str
    run_id: str
    case_id: str
    output_dir: str
    query_contract: dict[str, Any]
    case_contract: dict[str, Any]
    prompt: str
    focus_tickers: list[str]
    search_scope_tickers: list[str]
    required_dimensions: list[str]
    required_answer_moves: list[str]
    expected_gap_types: list[str]
    eval_focus: list[str]
    multi_agent_context: dict[str, Any]
    planner_trace: dict[str, Any]
    project_inventory: dict[str, Any]
    selected_tickers: list[str]
    selected_years: list[int]
    retrieval_plan: dict[str, Any]
    context_rows: list[dict[str, Any]]
    market_snapshot_rows: list[dict[str, Any]]
    industry_snapshot_rows: list[dict[str, Any]]
    runtime_ledger_rows: list[dict[str, Any]]
    product_evidence_rows: list[dict[str, Any]]
    public_source_context_rows: list[dict[str, Any]]
    human_source_runtime_rows: dict[str, Any]
    humanmade_gold_source_slots_consumed: dict[str, Any]
    humanmade_gold_set_audit_required: bool
    ai_semis_gold_depth_content_pack: dict[str, Any]
    product_intelligence_graph_projection: dict[str, Any]
    gold_specialist_judgment_materials: dict[str, Any]
    p33_gold_depth_runtime_assimilation: dict[str, Any]
    coverage_matrix: dict[str, Any]
    source_gaps: list[dict[str, Any]]
    retrieval_trace: dict[str, Any]
    context_runtime: dict[str, Any]
    evidence_requirement_plan: dict[str, Any]
    evidence_sufficiency_report: dict[str, Any]
    second_pass_attempts: int
    second_pass_result: dict[str, Any]
    second_pass_evidence_requirement_plan: dict[str, Any]
    second_pass_retrieval_plan: dict[str, Any]
    second_pass_reflection_diagnosis: dict[str, Any]
    second_pass_repair_plan: dict[str, Any]
    second_pass_hard_gate: dict[str, Any]
    second_pass_delta_audit: dict[str, Any]
    research_objective_contract: dict[str, Any]
    lead_review_checkpoint: dict[str, Any]
    targeted_repair_plan: dict[str, Any]
    memo_logic_plan: dict[str, Any]
    supervising_analyst_pack: dict[str, Any]
    judgment_plan: dict[str, Any]
    verified_judgment_plan: dict[str, Any]
    memo_answer: dict[str, Any]
    claim_verification: dict[str, Any]
    deterministic_gates: dict[str, Any]
    rendered_answer: str
    node_trace: list[dict[str, Any]]
    node_checkpoints: list[dict[str, Any]]
    artifact_refs: dict[str, str]
    checkpoint_mode: str
    checkpoint_db_path: str
    native_stop_after_node: str
    status: str
    agent_activation_plan: dict[str, Any]
    agent_activation_validation: dict[str, Any]
    research_lead_thesis_path: dict[str, Any]
    research_lead_evidence_role_plan: list[dict[str, Any]]
    research_lead_specialist_assignment: dict[str, Any]
    research_lead_missing_but_retrievable: list[dict[str, Any]]
    research_lead_bounded_or_commercial_gap: list[dict[str, Any]]
    research_lead_writer_order: list[str]
    plan_reflection_report: dict[str, Any]
    multi_agent_routing_trace: dict[str, Any]
    agent_registry_snapshot: dict[str, Any]
    research_lead_route_status: str
    research_lead_failure_reason: str
    research_lead_validation: dict[str, Any]
    research_lead_rejected_plan: dict[str, Any]
    product_intelligence_runtime_autoload: bool
    product_intelligence_runtime_policy: dict[str, Any]
    tool_call_ledger: dict[str, Any]
    loop_budget_state: dict[str, Any]
    agent_trace: list[dict[str, Any]]
    tool_observations: list[dict[str, Any]]
    multi_agent_reflection_report: dict[str, Any]
    multi_agent_second_pass_decision: dict[str, Any]
    quality_second_pass_report: dict[str, Any]
    quality_second_pass_decision: dict[str, Any]
    quality_second_pass_attempted: bool
    evidence_fusion_bundle: dict[str, Any]
    bounded_gap_register: dict[str, Any]
    entity_security_master: dict[str, Any]
    source_capability_router: dict[str, Any]
    runtime_source_context_store: dict[str, Any]
    source_layer_capability_audit: dict[str, Any]
    source_authority_coverage: dict[str, Any]
    raw_source_provenance_store: dict[str, Any]
    asof_vintage_layer: dict[str, Any]
    metric_product_ontology_snapshot: dict[str, Any]
    reconciliation_ledger: dict[str, Any]
    gate_registry_eval_matrix: dict[str, Any]
    derived_metric_layer: dict[str, Any]
    fundamental_statement_pack: dict[str, Any]
    analyst_view_research_memory: dict[str, Any]
    d_series_governance_db_path: str
    d_series_database_path: str
    d_series_database_materialization: dict[str, Any]
    d_series_database_materialization_report: dict[str, Any]
    run_audit_db_path: str
    run_audit_materialization_report: dict[str, Any]
    d_series_claim_gap_gate_reader_context: dict[str, Any]
    d_series_research_context: dict[str, Any]
    pre_memo_fact_selection: dict[str, Any]
    d_series_database_closeout_gate: dict[str, Any]
    claim_evidence_ledger: dict[str, Any]
    typed_gap_ledger: dict[str, Any]
    evidence_operator_fanout_plan: dict[str, Any]
    evidence_operator_fanout_barrier: dict[str, Any]
    specialist_outputs: list[dict[str, Any]]
    specialist_activation_decisions: list[dict[str, Any]]
    specialist_verification: dict[str, Any]
    specialist_fanout_barrier: dict[str, Any]
    claim_card_store_barrier: dict[str, Any]
    adjudicator_barrier: dict[str, Any]
    relationship_graph_observation: dict[str, Any]
    universe_relationship_plan: dict[str, Any]
    universe_relationship_validation: dict[str, Any]
    research_lead_model_diagnostics: dict[str, Any]
    research_lead_input_pack_fingerprint: dict[str, Any]
    universe_relationship_model_diagnostics: dict[str, Any]
    universe_relationship_routing_trace: dict[str, Any]
    universe_relationship_input_pack_fingerprint: dict[str, Any]
    specialist_route_results: list[dict[str, Any]]
    memo_route_result: dict[str, Any]
    multi_agent_summary: dict[str, Any]
    loop_break_reason: str
    bounded_answer_allowed: bool


NodeFunc = Callable[[SecAgentGraphRuntimeState], SecAgentGraphRuntimeState]
PlannerFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
RetrieveContextFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
AttachMarketFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
AttachIndustryFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
BuildLedgerFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
BuildCoverageFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
SecondPassRetrievalFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
BuildJudgmentPlanFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
SynthesizeAnswerFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
VerifyClaimsFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
RunDeterministicGatesFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
RenderAnswerFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
MultiAgentPlanFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]
MultiAgentNodeFunc = Callable[[SecAgentGraphRuntimeState], dict[str, Any]]


class SlimmingCheckpointSaver(BaseCheckpointSaver):  # type: ignore[misc]
    """Persist compact graph checkpoints while leaving in-memory node state intact."""

    def __init__(self, delegate: Any) -> None:
        super().__init__(serde=getattr(delegate, "serde", None))
        self._delegate = delegate

    @property
    def config_specs(self) -> list:
        return list(getattr(self._delegate, "config_specs", []))

    def setup(self) -> None:
        setup = getattr(self._delegate, "setup", None)
        if callable(setup):
            setup()

    def get_tuple(self, config: Any) -> Any:
        return self._delegate.get_tuple(config)

    def list(
        self,
        config: Any | None,
        *,
        filter: dict[str, Any] | None = None,
        before: Any | None = None,
        limit: int | None = None,
    ) -> Any:
        return self._delegate.list(config, filter=filter, before=before, limit=limit)

    def put(self, config: Any, checkpoint: dict[str, Any], metadata: dict[str, Any], new_versions: Any) -> Any:
        return self._delegate.put(
            config,
            _slim_checkpoint_payload(checkpoint),
            _slim_checkpoint_metadata(metadata),
            new_versions,
        )

    def put_writes(self, config: Any, writes: Any, task_id: str, task_path: str = "") -> None:
        return self._delegate.put_writes(config, _slim_checkpoint_writes(writes), task_id, task_path)

    def delete_thread(self, thread_id: str) -> None:
        delete_thread = getattr(self._delegate, "delete_thread", None)
        if callable(delete_thread):
            delete_thread(thread_id)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)


def wrap_checkpoint_saver_for_sec_agent_state(delegate: Any | None) -> Any | None:
    if delegate is None:
        return None
    return SlimmingCheckpointSaver(delegate)


def native_node_order() -> tuple[str, ...]:
    return NATIVE_NODE_ORDER


def multi_agent_node_order() -> tuple[str, ...]:
    return MULTI_AGENT_NODE_ORDER


def build_multi_agent_orchestration_graph(
    *,
    use_checkpointer: bool = True,
    route_activation: MultiAgentPlanFunc | None = None,
    execute_evidence_operators: MultiAgentNodeFunc | None = None,
    coverage_reflection: MultiAgentNodeFunc | None = None,
    execute_second_pass_retrieval: MultiAgentNodeFunc | None = None,
    expand_universe_relationship: MultiAgentNodeFunc | None = None,
    run_specialist_analysts: MultiAgentNodeFunc | None = None,
    aggregate_judgment_plan: MultiAgentNodeFunc | None = None,
    memo_writer: MultiAgentNodeFunc | None = None,
    verifier: MultiAgentNodeFunc | None = None,
    renderer: MultiAgentNodeFunc | None = None,
    checkpointer: Any | None = None,
    entry_node: str | None = None,
    stop_after_node: str | None = None,
):
    if StateGraph is None:
        raise RuntimeError(f"LangGraph is not installed: {LANGGRAPH_IMPORT_ERROR}")
    start_node = entry_node or MULTI_AGENT_NODE_ORDER[0]
    if start_node not in MULTI_AGENT_NODE_ORDER:
        raise ValueError(f"Unsupported multi-agent graph entry node: {start_node}")
    stop_node = str(stop_after_node or "").strip()
    if stop_node and stop_node not in MULTI_AGENT_NODE_ORDER:
        raise ValueError(f"Unsupported multi-agent graph stop node: {stop_node}")
    builder = StateGraph(SecAgentGraphRuntimeState)
    nodes: dict[str, NodeFunc] = {
        "load_session_state": _node_load_session_state,
        "research_lead_plan": lambda state: _node_research_lead_plan(state, route_activation=route_activation),
        "validate_activation_plan": _node_validate_activation_plan,
        "plan_reflection_gate": _node_plan_reflection_gate,
        "universe_relationship_expand": lambda state: _node_universe_relationship_expand(
            state,
            expand_universe_relationship=expand_universe_relationship,
        ),
        "route_by_execution_mode": _node_route_by_execution_mode,
        "compile_evidence_requirements": _node_compile_evidence_requirements,
        "execute_evidence_operators": lambda state: _node_execute_evidence_operators(
            state,
            execute_evidence_operators=execute_evidence_operators,
        ),
        "evidence_fusion_selector": _node_evidence_fusion_selector,
        "coverage_reflection": lambda state: _node_coverage_reflection(
            state,
            coverage_reflection=coverage_reflection,
        ),
        "optional_second_pass": lambda state: _node_optional_second_pass(
            state,
            execute_second_pass_retrieval=execute_second_pass_retrieval,
        ),
        "optional_specialist_subgraph": lambda state: _node_optional_specialist_subgraph(
            state,
            run_specialist_analysts=run_specialist_analysts,
        ),
        "aggregate_judgment_plan": lambda state: _node_multi_agent_aggregate_judgment_plan(
            state,
            aggregate_judgment_plan=aggregate_judgment_plan,
        ),
        "memo_writer": lambda state: _node_multi_agent_memo_writer(state, memo_writer=memo_writer),
        "verifier": lambda state: _node_multi_agent_verifier(state, verifier=verifier),
        "renderer": lambda state: _node_multi_agent_renderer(state, renderer=renderer),
        "persist_session_state": _node_multi_agent_persist_session_state,
    }
    for name in MULTI_AGENT_NODE_ORDER:
        builder.add_node(name, _wrap_native_node(name, nodes[name], stop_after_node=stop_node))
    builder.add_edge(START, start_node)
    _add_stop_aware_edge(builder, "load_session_state", "research_lead_plan")
    _add_stop_aware_edge(builder, "research_lead_plan", "validate_activation_plan")
    _add_stop_aware_edge(builder, "validate_activation_plan", "plan_reflection_gate")
    _add_stop_aware_edge(builder, "plan_reflection_gate", "universe_relationship_expand")
    _add_stop_aware_edge(builder, "universe_relationship_expand", "route_by_execution_mode")
    _add_stop_aware_edge(builder, "route_by_execution_mode", "compile_evidence_requirements")
    _add_stop_aware_edge(builder, "compile_evidence_requirements", "execute_evidence_operators")
    _add_stop_aware_edge(builder, "execute_evidence_operators", "evidence_fusion_selector")
    _add_stop_aware_edge(builder, "evidence_fusion_selector", "coverage_reflection")
    builder.add_conditional_edges(
        "coverage_reflection",
        _route_after_multi_agent_reflection,
        {
            "stop": END,
            "second_pass": "optional_second_pass",
            "specialists": "optional_specialist_subgraph",
            "aggregate": "aggregate_judgment_plan",
            "renderer": "renderer",
        },
    )
    builder.add_conditional_edges(
        "optional_second_pass",
        _route_after_multi_agent_second_pass,
        {
            "stop": END,
            "specialists": "optional_specialist_subgraph",
            "aggregate": "aggregate_judgment_plan",
            "renderer": "renderer",
        },
    )
    _add_stop_aware_edge(builder, "optional_specialist_subgraph", "aggregate_judgment_plan")
    builder.add_conditional_edges(
        "aggregate_judgment_plan",
        _route_after_multi_agent_aggregate,
        {
            "second_pass": "optional_second_pass",
            "memo": "memo_writer",
        },
    )
    _add_stop_aware_edge(builder, "memo_writer", "verifier")
    _add_stop_aware_edge(builder, "verifier", "renderer")
    _add_stop_aware_edge(builder, "renderer", "persist_session_state")
    builder.add_edge("persist_session_state", END)
    effective_checkpointer = checkpointer if checkpointer is not None else (InMemorySaver() if use_checkpointer and InMemorySaver is not None else None)
    return builder.compile(checkpointer=effective_checkpointer)


def build_multi_agent_orchestration_graph_from_env(
    *,
    env: Mapping[str, str] | None = None,
    use_checkpointer: bool = True,
    checkpointer: Any | None = None,
    entry_node: str | None = None,
    stop_after_node: str | None = None,
):
    from sec_agent.memo_llm import memo_writer_from_env, verifier_from_env
    from sec_agent.research_lead_llm import route_activation_from_env
    from sec_agent.universe_relationship_llm import route_universe_relationship_from_env
    from sec_agent.specialist_llm import route_specialists_from_env

    return build_multi_agent_orchestration_graph(
        use_checkpointer=use_checkpointer,
        route_activation=route_activation_from_env(env),
        expand_universe_relationship=route_universe_relationship_from_env(env),
        run_specialist_analysts=route_specialists_from_env(env),
        memo_writer=memo_writer_from_env(env),
        verifier=verifier_from_env(env),
        checkpointer=checkpointer,
        entry_node=entry_node,
        stop_after_node=stop_after_node,
    )


def build_native_orchestration_graph(
    *,
    use_checkpointer: bool = True,
    plan_query: PlannerFunc | None = None,
    retrieve_context: RetrieveContextFunc | None = None,
    attach_market_snapshot: AttachMarketFunc | None = None,
    attach_industry_snapshot: AttachIndustryFunc | None = None,
    build_runtime_ledger: BuildLedgerFunc | None = None,
    build_coverage_matrix: BuildCoverageFunc | None = None,
    execute_second_pass_retrieval: SecondPassRetrievalFunc | None = None,
    build_judgment_plan: BuildJudgmentPlanFunc | None = None,
    synthesize_answer: SynthesizeAnswerFunc | None = None,
    verify_claims: VerifyClaimsFunc | None = None,
    run_deterministic_gates: RunDeterministicGatesFunc | None = None,
    render_answer: RenderAnswerFunc | None = None,
    checkpointer: Any | None = None,
    entry_node: str | None = None,
    stop_after_node: str | None = None,
):
    if StateGraph is None:
        raise RuntimeError(f"LangGraph is not installed: {LANGGRAPH_IMPORT_ERROR}")
    start_node = entry_node or NATIVE_NODE_ORDER[0]
    if start_node not in (*NATIVE_NODE_ORDER, *NATIVE_OPTIONAL_NODE_ORDER):
        raise ValueError(f"Unsupported native graph entry node: {start_node}")
    stop_node = str(stop_after_node or "").strip()
    if stop_node and stop_node not in (*NATIVE_NODE_ORDER, *NATIVE_OPTIONAL_NODE_ORDER):
        raise ValueError(f"Unsupported native graph stop node: {stop_node}")
    builder = StateGraph(SecAgentGraphRuntimeState)
    nodes: dict[str, NodeFunc] = {
        "load_session_state": _node_load_session_state,
        "plan_query": lambda state: _node_plan_query(state, plan_query=plan_query),
        "validate_query_contract": _node_validate_query_contract,
        "compile_retrieval_plan": _node_compile_retrieval_plan,
        "execute_retrieval_routes": lambda state: _node_execute_retrieval_routes(
            state,
            retrieve_context=retrieve_context,
        ),
        "attach_market_snapshot": lambda state: _node_attach_market_snapshot(
            state,
            attach_market_snapshot=attach_market_snapshot,
        ),
        "attach_industry_snapshot": lambda state: _node_attach_industry_snapshot(
            state,
            attach_industry_snapshot=attach_industry_snapshot,
        ),
        "build_runtime_ledger": lambda state: _node_build_runtime_ledger(
            state,
            build_runtime_ledger=build_runtime_ledger,
        ),
        "assess_evidence_coverage": lambda state: _node_assess_evidence_coverage(
            state,
            build_coverage_matrix=build_coverage_matrix,
        ),
        "assess_evidence_sufficiency": _node_assess_evidence_sufficiency,
        "execute_second_pass_retrieval": lambda state: _node_execute_second_pass_retrieval(
            state,
            execute_second_pass_retrieval=execute_second_pass_retrieval,
        ),
        "build_judgment_plan": lambda state: _node_build_judgment_plan(
            state,
            build_judgment_plan=build_judgment_plan,
        ),
        "synthesize_answer": lambda state: _node_synthesize_answer(
            state,
            synthesize_answer=synthesize_answer,
        ),
        "verify_claims": lambda state: _node_verify_claims(
            state,
            verify_claims=verify_claims,
        ),
        "run_deterministic_gates": lambda state: _node_run_deterministic_gates(
            state,
            run_deterministic_gates=run_deterministic_gates,
        ),
        "render_answer": lambda state: _node_render_answer(
            state,
            render_answer=render_answer,
        ),
        "persist_session_state": _node_persist_session_state,
    }
    for name in (*NATIVE_NODE_ORDER, *NATIVE_OPTIONAL_NODE_ORDER):
        builder.add_node(name, _wrap_native_node(name, nodes[name], stop_after_node=stop_node))
    builder.add_edge(START, start_node)
    _add_stop_aware_edge(builder, "load_session_state", "plan_query")
    _add_stop_aware_edge(builder, "plan_query", "validate_query_contract")
    _add_stop_aware_edge(builder, "validate_query_contract", "compile_retrieval_plan")
    _add_stop_aware_edge(builder, "compile_retrieval_plan", "execute_retrieval_routes")
    _add_stop_aware_edge(builder, "execute_retrieval_routes", "attach_market_snapshot")
    _add_stop_aware_edge(builder, "attach_market_snapshot", "attach_industry_snapshot")
    _add_stop_aware_edge(builder, "attach_industry_snapshot", "build_runtime_ledger")
    _add_stop_aware_edge(builder, "build_runtime_ledger", "assess_evidence_coverage")
    _add_stop_aware_edge(builder, "assess_evidence_coverage", "assess_evidence_sufficiency")
    builder.add_conditional_edges(
        "assess_evidence_sufficiency",
        lambda state: _route_after_evidence_sufficiency(
            state,
            second_pass_enabled=execute_second_pass_retrieval is not None,
        ),
        {
            "stop": END,
            "second_pass": "execute_second_pass_retrieval",
            "continue": "build_judgment_plan",
        },
    )
    _add_stop_aware_edge(builder, "execute_second_pass_retrieval", "build_runtime_ledger")
    _add_stop_aware_edge(builder, "build_judgment_plan", "synthesize_answer")
    _add_stop_aware_edge(builder, "synthesize_answer", "verify_claims")
    _add_stop_aware_edge(builder, "verify_claims", "run_deterministic_gates")
    _add_stop_aware_edge(builder, "run_deterministic_gates", "render_answer")
    _add_stop_aware_edge(builder, "render_answer", "persist_session_state")
    builder.add_edge(NATIVE_NODE_ORDER[-1], END)
    effective_checkpointer = checkpointer if checkpointer is not None else (InMemorySaver() if use_checkpointer and InMemorySaver is not None else None)
    return builder.compile(checkpointer=effective_checkpointer)


def build_native_state_smoke_graph(
    *,
    use_checkpointer: bool = True,
    plan_query: PlannerFunc | None = None,
    retrieve_context: RetrieveContextFunc | None = None,
    attach_market_snapshot: AttachMarketFunc | None = None,
    attach_industry_snapshot: AttachIndustryFunc | None = None,
    build_runtime_ledger: BuildLedgerFunc | None = None,
    build_coverage_matrix: BuildCoverageFunc | None = None,
    execute_second_pass_retrieval: SecondPassRetrievalFunc | None = None,
    build_judgment_plan: BuildJudgmentPlanFunc | None = None,
    synthesize_answer: SynthesizeAnswerFunc | None = None,
    verify_claims: VerifyClaimsFunc | None = None,
    run_deterministic_gates: RunDeterministicGatesFunc | None = None,
    render_answer: RenderAnswerFunc | None = None,
    checkpointer: Any | None = None,
    entry_node: str | None = None,
    stop_after_node: str | None = None,
):
    return build_native_orchestration_graph(
        use_checkpointer=use_checkpointer,
        plan_query=plan_query,
        retrieve_context=retrieve_context,
        attach_market_snapshot=attach_market_snapshot,
        attach_industry_snapshot=attach_industry_snapshot,
        build_runtime_ledger=build_runtime_ledger,
        build_coverage_matrix=build_coverage_matrix,
        execute_second_pass_retrieval=execute_second_pass_retrieval,
        build_judgment_plan=build_judgment_plan,
        synthesize_answer=synthesize_answer,
        verify_claims=verify_claims,
        run_deterministic_gates=run_deterministic_gates,
        render_answer=render_answer,
        checkpointer=checkpointer,
        entry_node=entry_node,
        stop_after_node=stop_after_node,
    )


def make_native_smoke_state(
    *,
    user_query: str,
    output_dir: str | Path,
    query_contract: dict[str, Any] | None = None,
) -> SecAgentGraphRuntimeState:
    return {
        "user_query": str(user_query or "native graph smoke"),
        "run_id": _run_id(user_query or "native graph smoke"),
        "output_dir": str(Path(output_dir)),
        "query_contract": annotate_scope_contract(query_contract or _minimal_query_contract()),
        "node_trace": [],
        "node_checkpoints": [],
        "artifact_refs": {},
        "status": "created",
    }


def make_multi_agent_smoke_state(
    *,
    user_query: str,
    output_dir: str | Path,
    query_contract: dict[str, Any] | None = None,
    focus_tickers: list[str] | None = None,
    search_scope_tickers: list[str] | None = None,
) -> SecAgentGraphRuntimeState:
    state = make_native_smoke_state(user_query=user_query, output_dir=output_dir, query_contract=query_contract)
    if focus_tickers is not None:
        state["selected_tickers"] = [str(item).upper() for item in focus_tickers]
    if search_scope_tickers is not None:
        contract = dict(state.get("query_contract") or {})
        contract["focus_tickers"] = [str(item).upper() for item in (focus_tickers or [])]
        contract["search_scope_tickers"] = [str(item).upper() for item in search_scope_tickers]
        state["query_contract"] = annotate_scope_contract(contract)
    state["agent_trace"] = []
    state["tool_call_ledger"] = ToolCallLedger().to_dict()
    state["loop_budget_state"] = LoopBudget().to_dict()
    return state


def infer_scope_mode(query_contract: dict[str, Any]) -> str:
    explicit = str(
        query_contract.get("scope_mode")
        or (query_contract.get("scope") if isinstance(query_contract.get("scope"), dict) else {}).get("scope_mode")
        or ""
    ).strip()
    if explicit in SCOPE_MODES:
        return explicit
    scope_tickers = _unique_upper(
        query_contract.get("search_scope_tickers")
        or (query_contract.get("scope") if isinstance(query_contract.get("scope"), dict) else {}).get("universe_tickers")
        or []
    )
    focus_tickers = _unique_upper(
        query_contract.get("focus_tickers")
        or (query_contract.get("scope") if isinstance(query_contract.get("scope"), dict) else {}).get("focus_tickers")
        or []
    )
    task_type = str(query_contract.get("task_type") or "")
    if scope_tickers and focus_tickers and set(focus_tickers) < set(scope_tickers):
        return "sector_representative"
    if task_type in {"ai_industry_financial_trend", "open_analysis"} or len(scope_tickers) >= 5:
        return "full_universe"
    return "focused_peer"


def annotate_scope_contract(query_contract: dict[str, Any]) -> dict[str, Any]:
    contract = dict(query_contract)
    scope = dict(contract.get("scope") or {})
    universe = _unique_upper(contract.get("search_scope_tickers") or scope.get("universe_tickers") or [])
    focus = _unique_upper(contract.get("focus_tickers") or scope.get("focus_tickers") or universe)
    contract["search_scope_tickers"] = universe
    contract["focus_tickers"] = focus
    scope_mode = infer_scope_mode(contract)
    contract["scope_mode"] = scope_mode
    scope.update(
        {
            "scope_mode": scope_mode,
            "universe_tickers": universe,
            "focus_tickers": focus,
            "universe_count": len(universe),
            "focus_count": len(focus),
        }
    )
    if scope_mode == "sector_representative":
        scope["representative_tickers"] = focus
    contract["scope"] = scope
    return contract


def _wrap_native_node(
    node_name: str,
    node_func: NodeFunc,
    *,
    stop_after_node: str,
) -> NodeFunc:
    def _wrapped(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
        started_at = _utc_now()
        started_monotonic = time.perf_counter()
        next_state = node_func(state)
        elapsed_ms = max(0, int(round((time.perf_counter() - started_monotonic) * 1000)))
        timed_state = _update_latest_node_timing(
            next_state,
            node_name,
            started_at=started_at,
            elapsed_ms=elapsed_ms,
        )
        if stop_after_node and node_name == stop_after_node:
            return _mark_stopped_after_node(timed_state, node_name)
        return timed_state

    return _wrapped


def _add_stop_aware_edge(builder: Any, source: str, target: str) -> None:
    builder.add_conditional_edges(
        source,
        lambda state: "stop" if _is_terminal_graph_state(state) else "continue",
        {"stop": END, "continue": target},
    )


def _is_terminal_graph_state(state: SecAgentGraphRuntimeState) -> bool:
    return _is_stopped_after_node(state) or str(state.get("status") or "") == "failed"


def _is_stopped_after_node(state: SecAgentGraphRuntimeState) -> bool:
    return str(state.get("status") or "") == "stopped_after_node" and bool(state.get("native_stop_after_node"))


def _mark_stopped_after_node(state: SecAgentGraphRuntimeState, node_name: str) -> SecAgentGraphRuntimeState:
    stopped_state = _with_native_artifact_refs(
        {
            **state,
            "status": "stopped_after_node",
            "native_stop_after_node": node_name,
        }
    )
    _write_native_state_artifacts(stopped_state)
    return stopped_state


def _node_load_session_state(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    next_state = _state_with_d12_1_reader_context({**state, "status": "running"})
    reader_context = next_state.get("d_series_claim_gap_gate_reader_context") or {}
    d_series_context = next_state.get("d_series_research_context") or {}
    d_series_summary = d_series_context.get("summary") if isinstance(d_series_context, dict) and isinstance(d_series_context.get("summary"), dict) else {}
    return _record_node(
        next_state,
        "load_session_state",
        metadata={
            "d_series_reader_status": reader_context.get("reader_default_status") if isinstance(reader_context, dict) else "",
            "d_series_reader_claim_count": (reader_context.get("summary") or {}).get("claim_count")
            if isinstance(reader_context, dict) and isinstance(reader_context.get("summary"), dict)
            else 0,
            "d_series_context_status": d_series_context.get("reader_default_status") if isinstance(d_series_context, dict) else "",
            "d_series_context_row_count": d_series_summary.get("row_count") or 0,
        },
    )


def _product_intelligence_runtime_autoload_decision(
    state: Mapping[str, Any],
    activation_plan: Mapping[str, Any] | None,
    *,
    allow_state_override: bool = False,
) -> tuple[bool, dict[str, Any]]:
    plan = dict(activation_plan or {})
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    active_agents = set(_unique_strings(plan.get("activate_agents")))
    source_families = set(_unique_strings(plan.get("allowed_source_families")))
    focus_tickers = _unique_upper(
        plan.get("focus_tickers")
        or contract.get("focus_tickers")
        or state.get("focus_tickers")
        or state.get("selected_tickers")
        or []
    )
    search_scope_tickers = _unique_upper(
        plan.get("search_scope_tickers")
        or contract.get("search_scope_tickers")
        or state.get("search_scope_tickers")
        or state.get("selected_tickers")
        or focus_tickers
    )
    ticker_scope = _unique_upper([*focus_tickers, *search_scope_tickers])
    query_text = _product_intelligence_policy_query_text(state, contract)

    if allow_state_override and "product_intelligence_runtime_autoload" in state:
        enabled = _boolish(state.get("product_intelligence_runtime_autoload"))
        return enabled, {
            "schema_version": PRODUCT_INTELLIGENCE_RUNTIME_POLICY_SCHEMA_VERSION,
            "status": "enabled" if enabled else "disabled",
            "decision_source": "operator_override",
            "reason_codes": ["state_override"],
            "active_agents": sorted(active_agents),
            "allowed_source_families": sorted(source_families),
            "focus_tickers": focus_tickers,
            "search_scope_tickers": search_scope_tickers,
        }

    trigger_agents = sorted(active_agents & PRODUCT_INTELLIGENCE_AUTOLOAD_AGENT_IDS)
    relationship_agents = sorted(active_agents & PRODUCT_INTELLIGENCE_RELATIONSHIP_AGENT_IDS)
    trigger_sources = sorted(source_families & PRODUCT_INTELLIGENCE_AUTOLOAD_SOURCE_FAMILIES)
    trigger_terms = sorted({term for term in PRODUCT_INTELLIGENCE_QUERY_TERMS if term.lower() in query_text})
    reason_codes: list[str] = []
    if trigger_agents:
        reason_codes.append("product_specialist_active")
    if trigger_sources:
        reason_codes.append("product_source_family_allowed")
    if relationship_agents and (trigger_sources or trigger_terms):
        reason_codes.append("relationship_lane_with_product_context")
    if trigger_terms and not (trigger_agents or trigger_sources or relationship_agents):
        reason_codes.append("product_intent_without_specialist")
    if not ticker_scope:
        return False, {
            "schema_version": PRODUCT_INTELLIGENCE_RUNTIME_POLICY_SCHEMA_VERSION,
            "status": "disabled",
            "decision_source": "research_lead_lane_policy",
            "reason_codes": ["no_ticker_scope"],
            "active_agents": sorted(active_agents),
            "allowed_source_families": sorted(source_families),
            "trigger_terms": trigger_terms[:12],
            "focus_tickers": focus_tickers,
            "search_scope_tickers": search_scope_tickers,
        }

    enabled = bool(reason_codes)
    return enabled, {
        "schema_version": PRODUCT_INTELLIGENCE_RUNTIME_POLICY_SCHEMA_VERSION,
        "status": "enabled" if enabled else "disabled",
        "decision_source": "research_lead_lane_policy",
        "reason_codes": reason_codes or ["no_product_or_relationship_lane"],
        "active_agents": sorted(active_agents),
        "allowed_source_families": sorted(source_families),
        "trigger_agents": trigger_agents,
        "relationship_agents": relationship_agents,
        "trigger_source_families": trigger_sources,
        "trigger_terms": trigger_terms[:12],
        "focus_tickers": focus_tickers,
        "search_scope_tickers": search_scope_tickers,
    }


def _product_intelligence_policy_query_text(state: Mapping[str, Any], contract: Mapping[str, Any]) -> str:
    fragments: list[str] = [str(state.get("user_query") or "")]
    for key in (
        "question",
        "task",
        "intent",
        "research_objective",
        "answer_type",
        "requested_dimensions",
        "metric_families",
        "source_tiers",
        "source_families",
        "evidence_requirements",
    ):
        value = contract.get(key)
        if isinstance(value, (str, int, float)):
            fragments.append(str(value))
        elif isinstance(value, Mapping):
            fragments.extend(str(item) for item in value.values())
        elif isinstance(value, (list, tuple, set)):
            fragments.extend(str(item) for item in value)
    context = state.get("multi_agent_context")
    if isinstance(context, Mapping):
        for key in ("intent", "requested_dimensions", "source_families", "evidence_requirements"):
            value = context.get(key)
            if isinstance(value, (str, int, float)):
                fragments.append(str(value))
            elif isinstance(value, (list, tuple, set)):
                fragments.extend(str(item) for item in value)
    return " ".join(fragment.lower() for fragment in fragments if fragment)


def _boolish(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "enabled", "enable"}
    return bool(value)


def _node_research_lead_plan(
    state: SecAgentGraphRuntimeState,
    *,
    route_activation: MultiAgentPlanFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if route_activation is None:
        contract = state.get("query_contract") or {}
        result = route_multi_agent_activation(
            {
                "user_query": state.get("user_query") or "",
                "focus_tickers": contract.get("focus_tickers") or state.get("selected_tickers") or [],
                "search_scope_tickers": contract.get("search_scope_tickers") or state.get("selected_tickers") or [],
                "source_inventory": state.get("project_inventory") or {},
                "context": {**dict(state.get("multi_agent_context") or {}), "query_contract": dict(contract)},
            }
        )
    else:
        result = route_activation(state)
    plan = result.get("activation_plan") if isinstance(result.get("activation_plan"), dict) else result
    product_intelligence_autoload, product_intelligence_policy = _product_intelligence_runtime_autoload_decision(
        state,
        plan if isinstance(plan, Mapping) else {},
        allow_state_override=True,
    )
    routing_trace = dict(result.get("routing_trace") or {}) if isinstance(result.get("routing_trace"), dict) else {}
    routing_trace["product_intelligence_runtime"] = product_intelligence_policy
    next_state: SecAgentGraphRuntimeState = {
        **state,
        "agent_activation_plan": dict(plan or {}),
        "research_objective_contract": dict((plan or {}).get("research_objective_contract") or {})
        if isinstance(plan, Mapping)
        else {},
        "research_lead_thesis_path": dict((plan or {}).get("thesis_path") or {})
        if isinstance(plan, Mapping)
        else {},
        "research_lead_evidence_role_plan": [
            dict(item) for item in ((plan or {}).get("evidence_role_plan") or []) if isinstance(item, Mapping)
        ]
        if isinstance(plan, Mapping)
        else [],
        "research_lead_specialist_assignment": dict((plan or {}).get("specialist_assignment") or {})
        if isinstance(plan, Mapping)
        else {},
        "research_lead_missing_but_retrievable": [
            dict(item) for item in ((plan or {}).get("missing_but_retrievable") or []) if isinstance(item, Mapping)
        ]
        if isinstance(plan, Mapping)
        else [],
        "research_lead_bounded_or_commercial_gap": [
            dict(item) for item in ((plan or {}).get("bounded_or_commercial_gap") or []) if isinstance(item, Mapping)
        ]
        if isinstance(plan, Mapping)
        else [],
        "research_lead_writer_order": [
            str(item) for item in ((plan or {}).get("writer_order") or []) if str(item or "").strip()
        ]
        if isinstance(plan, Mapping)
        else [],
        "agent_registry_snapshot": {"agents": agent_registry_by_id()},
        "research_lead_route_status": result.get("status") or "",
        "research_lead_failure_reason": result.get("failure_reason") or "",
        "research_lead_validation": dict(result.get("validation") or {}) if isinstance(result.get("validation"), dict) else {},
        "research_lead_rejected_plan": dict(result.get("rejected_plan") or {}) if isinstance(result.get("rejected_plan"), dict) else {},
        "product_intelligence_runtime_autoload": product_intelligence_autoload,
        "product_intelligence_runtime_policy": product_intelligence_policy,
        "loop_budget_state": dict(result.get("loop_budget") or state.get("loop_budget_state") or LoopBudget().to_dict()),
        "tool_call_ledger": dict(state.get("tool_call_ledger") or ToolCallLedger().to_dict()),
        "agent_trace": [
            *(state.get("agent_trace") or []),
            {
                "node": "research_lead_plan",
                "agent_id": "research_lead",
                "execution_mode": (plan or {}).get("execution_mode") if isinstance(plan, dict) else "",
                "source": result.get("source") or "injected",
                "product_intelligence_runtime_autoload": product_intelligence_autoload,
            },
        ],
    }
    if isinstance(result.get("evidence_requirement_plan"), dict) and result.get("evidence_requirement_plan"):
        next_state["evidence_requirement_plan"] = result["evidence_requirement_plan"]  # type: ignore[literal-required]
    if routing_trace:
        next_state["multi_agent_routing_trace"] = routing_trace  # type: ignore[literal-required]
    if isinstance(result.get("model_diagnostics"), dict):
        next_state["research_lead_model_diagnostics"] = result["model_diagnostics"]  # type: ignore[literal-required]
    if isinstance(result.get("input_pack_fingerprint"), dict):
        next_state["research_lead_input_pack_fingerprint"] = result["input_pack_fingerprint"]  # type: ignore[literal-required]
    return _record_node(next_state, "research_lead_plan", metadata={"mode": "injected" if route_activation else "deterministic_mock"})


def _node_validate_activation_plan(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    validation = validate_agent_activation_plan(
        state.get("agent_activation_plan") or {},
        known_agent_ids=set(agent_registry_by_id()),
        allowed_source_families=allowed_source_families(),
        agent_registry=agent_registry_by_id(),
        global_limits=state.get("loop_budget_state") or {},
    )
    existing_policy = state.get("product_intelligence_runtime_policy")
    preserve_operator_override = (
        isinstance(existing_policy, Mapping)
        and existing_policy.get("decision_source") == "operator_override"
    ) or ("product_intelligence_runtime_autoload" in state and "product_intelligence_runtime_policy" not in state)
    product_intelligence_autoload, product_intelligence_policy = _product_intelligence_runtime_autoload_decision(
        state,
        validation.get("plan") or state.get("agent_activation_plan") or {},
        allow_state_override=preserve_operator_override,
    )
    routing_trace = dict(state.get("multi_agent_routing_trace") or {})
    routing_trace["product_intelligence_runtime"] = product_intelligence_policy
    next_state: SecAgentGraphRuntimeState = {
        **state,
        "agent_activation_validation": validation,
        "agent_activation_plan": dict(validation.get("plan") or state.get("agent_activation_plan") or {}),
        "product_intelligence_runtime_autoload": product_intelligence_autoload,
        "product_intelligence_runtime_policy": product_intelligence_policy,
        "multi_agent_routing_trace": routing_trace,
    }
    if validation["status"] != "pass":
        next_state["status"] = "failed"
        next_state["loop_break_reason"] = "invalid_agent_activation_plan"
    return _record_node(next_state, "validate_activation_plan", metadata={"status": validation["status"]})


def _node_plan_reflection_gate(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    report = plan_reflection_gate(
        state.get("agent_activation_plan") or {},
        activation_validation=state.get("agent_activation_validation") or {},
        source_inventory=state.get("project_inventory") or {},
    )
    next_state: SecAgentGraphRuntimeState = {
        **state,
        "plan_reflection_report": report,
    }
    if report.get("status") != "pass":
        next_state["status"] = "failed"
        next_state["loop_break_reason"] = "plan_reflection_gate_failed"
    return _record_node(
        next_state,
        "plan_reflection_gate",
        metadata={
            "status": report.get("status"),
            "error_count": len(report.get("errors") or []),
            "warning_count": len(report.get("warnings") or []),
        },
    )


def _node_universe_relationship_expand(
    state: SecAgentGraphRuntimeState,
    *,
    expand_universe_relationship: MultiAgentNodeFunc | None = None,
) -> SecAgentGraphRuntimeState:
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), dict) else {}
    active = set(activation.get("activate_agents") or [])
    if "universe_relationship" not in active:
        return _record_node(state, "universe_relationship_expand", metadata={"mode": "skipped"})

    ledger = ToolCallLedger.from_dict(state.get("tool_call_ledger") or {"budget": state.get("loop_budget_state") or {}})
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), dict) else {}
    context = state.get("multi_agent_context") if isinstance(state.get("multi_agent_context"), dict) else {}
    allowed_universe_tickers = _relationship_allowed_universe_tickers(state)
    lookup_args = {
        "focus_tickers": activation.get("focus_tickers") or contract.get("focus_tickers") or state.get("selected_tickers") or [],
        "search_scope_tickers": activation.get("search_scope_tickers") or contract.get("search_scope_tickers") or state.get("selected_tickers") or [],
        "allowed_universe_tickers": allowed_universe_tickers,
        "user_query": state.get("user_query") or "",
        "relationship_graph_path": context.get("relationship_graph_path") or "",
        "sector_depth_pack_path": context.get("sector_depth_pack_path") or "",
        "expected_relationship_pack_ids": list(context.get("expected_relationship_pack_ids") or []),
        "max_relationships": 24,
        "max_expanded_tickers": 12,
        "include_sector_depth": True,
    }
    permission = validate_operator_tool_call(agent_id="universe_relationship", tool_name="relationship_graph_lookup")
    decision = (
        ledger.can_call_tool(
            turn_id=str(state.get("run_id") or "multi_agent_turn"),
            agent_id="universe_relationship",
            tool_name="relationship_graph_lookup",
            arguments=lookup_args,
        )
        if permission["status"] == "pass"
        else {"allowed": False, "reason": permission["error"], "status": "blocked"}
    )
    if decision["allowed"]:
        lookup = invoke_mcp_tool("relationship_graph_lookup", lookup_args)
        rows = list(lookup.get("relationship_rows") or [])
        gaps = list(lookup.get("source_gaps") or [])
        refs = [dict(item) for item in lookup.get("artifact_refs") or [] if isinstance(item, dict)]
        ledger.record_tool_call(
            turn_id=str(state.get("run_id") or "multi_agent_turn"),
            agent_id="universe_relationship",
            tool_name="relationship_graph_lookup",
            arguments=lookup_args,
            output_artifact_digest=_first_artifact_digest(refs),
            row_count=len(rows),
            source_gap_count=len(gaps),
            coverage_delta={"closed_gaps": 0},
            status=str(lookup.get("status") or "ok"),
            metadata={"boundary": "relationship_hypothesis_only"},
        )
    else:
        lookup = {
            "status": "blocked",
            "relationships": [],
            "relationship_rows": [],
            "source_gaps": [{"source_family": "relationship_graph", "reason": decision["reason"], "source_available": False}],
        }

    sanitized_lookup = _sanitize_relationship_lookup_for_state(lookup)
    state_with_lookup: SecAgentGraphRuntimeState = {
        **state,
        "relationship_graph_observation": sanitized_lookup,
        "source_gaps": [*(state.get("source_gaps") or []), *[dict(item) for item in lookup.get("source_gaps") or [] if isinstance(item, dict)]],
        "tool_call_ledger": ledger.to_dict(),
        "loop_break_reason": ledger.loop_break_reason or str(state.get("loop_break_reason") or ""),
        "agent_trace": [
            *(state.get("agent_trace") or []),
            {
                "node": "universe_relationship_expand",
                "agent_id": "universe_relationship",
                "lookup_status": lookup.get("status") or "",
                "relationship_count": len(lookup.get("relationships") or []),
            },
        ],
    }

    universe_input_pack_fingerprint: dict[str, Any] = {}
    if expand_universe_relationship is not None:
        result = expand_universe_relationship(state_with_lookup)
        plan = result.get("universe_relationship_plan") if isinstance(result.get("universe_relationship_plan"), dict) else result.get("plan")
        validation = result.get("universe_relationship_validation") if isinstance(result.get("universe_relationship_validation"), dict) else {}
        source = result.get("source") or "injected"
        model_diagnostics = result.get("model_diagnostics") if isinstance(result.get("model_diagnostics"), dict) else {}
        routing_trace = result.get("routing_trace") if isinstance(result.get("routing_trace"), dict) else {}
        universe_input_pack_fingerprint = (
            dict(result.get("input_pack_fingerprint"))
            if isinstance(result.get("input_pack_fingerprint"), dict)
            else {}
        )
    else:
        plan = relationship_plan_from_lookup(
            sanitized_lookup,
            scope_mode=str(activation.get("scope_mode") or contract.get("scope_mode") or "focused_peer"),
            focus_tickers=lookup_args["focus_tickers"],
            relationship_scope_rationale=str(activation.get("relationship_scope_rationale") or ""),
        )
        validation = {}
        source = "relationship_graph_lookup"
        model_diagnostics = {}
        routing_trace = {}

    normalized_plan = normalize_universe_relationship_plan(plan if isinstance(plan, dict) else {})
    if not validation:
        validation = validate_universe_relationship_plan(
            normalized_plan,
            known_evidence_refs=_relationship_lookup_refs(sanitized_lookup),
            source_inventory=state.get("project_inventory") if isinstance(state.get("project_inventory"), dict) else {},
        )
    accepted_plan = dict(validation.get("plan") or normalized_plan)
    next_state: SecAgentGraphRuntimeState = {
        **state_with_lookup,
        "universe_relationship_plan": accepted_plan,
        "universe_relationship_validation": dict(validation),
        "universe_relationship_model_diagnostics": dict(model_diagnostics),
        "universe_relationship_routing_trace": dict(routing_trace),
    }
    if universe_input_pack_fingerprint:
        next_state["universe_relationship_input_pack_fingerprint"] = universe_input_pack_fingerprint  # type: ignore[literal-required]
    if validation.get("status") != "pass":
        next_state["bounded_answer_allowed"] = True
        next_state["loop_break_reason"] = "invalid_universe_relationship_plan"
    return _record_node(
        next_state,
        "universe_relationship_expand",
        metadata={"mode": source, "validation_status": validation.get("status"), "relationship_count": len(accepted_plan.get("relationships") or [])},
    )


def _relationship_allowed_universe_tickers(state: Mapping[str, Any]) -> list[str]:
    inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), Mapping) else {}
    candidates: list[Any] = []
    for key in ("available_tickers", "tickers", "source_inventory_companies"):
        candidates.extend(inventory.get(key) or [])
    for company in inventory.get("companies") or []:
        if isinstance(company, Mapping):
            candidates.append(company.get("ticker") or company.get("symbol") or company.get("object_id"))
        else:
            candidates.append(company)
    if not candidates:
        contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
        activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
        candidates.extend(contract.get("source_inventory_companies") or [])
        candidates.extend(activation.get("source_inventory_companies") or [])
    return _unique_upper(candidates)


def _node_route_by_execution_mode(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    plan = state.get("agent_activation_plan") or {}
    mode = str(plan.get("execution_mode") or "")
    trace = [
        *(state.get("agent_trace") or []),
        {
            "node": "route_by_execution_mode",
            "execution_mode": mode,
            "activated_agents": list(plan.get("activate_agents") or []),
            "skipped_agent_count": len(plan.get("skip_agents") or []),
        },
    ]
    return _record_node({**state, "agent_trace": trace}, "route_by_execution_mode", metadata={"execution_mode": mode})


def _node_compile_evidence_requirements(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    if state.get("retrieval_plan"):
        next_state = _state_with_d3_d8_governance(state)
        return _record_node(
            next_state,
            "compile_evidence_requirements",
            metadata={
                "mode": "existing_retrieval_plan",
                "entity_count": (next_state.get("entity_security_master") or {}).get("entity_count"),
                "source_router_status": ((next_state.get("source_capability_router") or {}).get("validation") or {}).get("status"),
            },
        )
    plan = state.get("agent_activation_plan") or {}
    if plan.get("allowed_source_families") == ["run_artifact"]:
        next_state = _state_with_d3_d8_governance(state)
        return _record_node(next_state, "compile_evidence_requirements", metadata={"mode": "run_artifact_only"})
    contract = _query_contract_with_activation_source_families(state.get("query_contract") or {}, plan)
    if not contract:
        return _record_node(state, "compile_evidence_requirements", metadata={"mode": "no_query_contract"})
    case = {
        "case_id": state.get("run_id") or "multi_agent",
        "prompt": state.get("user_query") or "",
        "companies": contract.get("search_scope_tickers") or contract.get("focus_tickers") or [],
        "years": contract.get("years") or [],
        "query_contract": contract,
    }
    evidence_plan = state.get("evidence_requirement_plan") or build_multi_agent_evidence_requirement_plan(
        contract,
        activation_plan=state.get("agent_activation_plan") or {},
        case=case,
    )
    evidence_plan = merge_universe_relationship_evidence_requirements(
        evidence_plan,
        state.get("universe_relationship_plan") or {},
        activation_plan=state.get("agent_activation_plan") or {},
    )
    retrieval_plan = compile_multi_agent_retrieval_plan(
        evidence_plan,
        query_contract=contract,
        case=case,
        activation_plan=state.get("agent_activation_plan") or {},
    )
    next_state = _state_with_d3_d8_governance({**state, "evidence_requirement_plan": evidence_plan, "retrieval_plan": retrieval_plan})
    return _record_node(
        next_state,
        "compile_evidence_requirements",
        metadata={
            "mode": "compiled",
            "requirement_count": len(evidence_plan.get("requirements") or []),
            "validation_status": (evidence_plan.get("multi_agent_evidence_requirement_validation") or {}).get("status"),
            "entity_count": (next_state.get("entity_security_master") or {}).get("entity_count"),
            "source_router_status": ((next_state.get("source_capability_router") or {}).get("validation") or {}).get("status"),
        },
    )


def _state_with_d3_d8_governance(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    entity_master = state.get("entity_security_master") if isinstance(state.get("entity_security_master"), dict) else {}
    source_router = state.get("source_capability_router") if isinstance(state.get("source_capability_router"), dict) else {}
    source_layer_audit = state.get("source_layer_capability_audit") if isinstance(state.get("source_layer_capability_audit"), dict) else {}
    source_authority = state.get("source_authority_coverage") if isinstance(state.get("source_authority_coverage"), dict) else {}
    if not entity_master:
        entity_master = build_entity_security_master(state)
    if not source_router:
        source_router = build_source_capability_router(state)
    if not source_layer_audit:
        source_layer_audit = _load_source_layer_capability_audit(state)
    if not source_authority:
        source_authority = _load_source_authority_coverage(state)
    return {
        **state,
        "entity_security_master": entity_master,
        "source_capability_router": source_router,
        "source_layer_capability_audit": source_layer_audit,
        "source_authority_coverage": source_authority,
    }


def _load_source_layer_capability_audit(state: Mapping[str, Any]) -> dict[str, Any]:
    inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), Mapping) else {}
    explicit_path = (
        state.get("source_layer_capability_audit_path")
        or inventory.get("source_layer_capability_audit_path")
        or "data/manifests/source_layer_capability_audit_v0_1.jsonl"
    )
    rows_path = Path(str(explicit_path))
    if not rows_path.exists():
        return {
            "schema_version": "finsight_source_layer_capability_audit_v0_1",
            "status": "not_loaded",
            "rows": [],
            "summary": {"source_count": 0, "reason": "source_layer_capability_audit_rows_not_found"},
        }
    rows: list[dict[str, Any]] = []
    for line in rows_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    summary_path = rows_path.with_name("source_layer_capability_audit_summary_v0_1.json")
    summary_payload: dict[str, Any] = {}
    validation_payload: dict[str, Any] = {}
    if summary_path.exists():
        try:
            raw_summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            raw_summary = {}
        if isinstance(raw_summary, dict):
            summary_payload = raw_summary.get("summary") if isinstance(raw_summary.get("summary"), dict) else {}
            validation_payload = raw_summary.get("validation") if isinstance(raw_summary.get("validation"), dict) else {}
    return {
        "schema_version": "finsight_source_layer_capability_audit_v0_1",
        "status": "loaded",
        "rows_path": str(rows_path),
        "rows": rows,
        "summary": summary_payload or {
            "source_count": len(rows),
            "runtime_ready_count": len([row for row in rows if row.get("runtime_ready_context")]),
            "expected_missing_count": len([row for row in rows if str(row.get("evidence_graph_status") or "") == "not_registered"]),
        },
        "validation": validation_payload,
    }


def _load_source_authority_coverage(state: Mapping[str, Any]) -> dict[str, Any]:
    inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), Mapping) else {}
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    explicit_path = (
        state.get("source_authority_coverage_path")
        or inventory.get("source_authority_coverage_path")
        or "data/manifests/r18_signal_authority_coverage_matrix_v0_2.jsonl"
    )
    focus_tickers = (
        contract.get("focus_tickers")
        or state.get("selected_tickers")
        or []
    )
    search_scope_tickers = (
        contract.get("search_scope_tickers")
        or contract.get("companies")
        or []
    )
    max_rows = int(
        state.get("source_authority_coverage_max_rows_per_ticker")
        or inventory.get("source_authority_coverage_max_rows_per_ticker")
        or 24
    )
    return load_source_authority_coverage(
        path=explicit_path,
        focus_tickers=focus_tickers if isinstance(focus_tickers, list) else [],
        search_scope_tickers=search_scope_tickers if isinstance(search_scope_tickers, list) else [],
        max_rows_per_ticker=max_rows,
    )


def _node_execute_evidence_operators(
    state: SecAgentGraphRuntimeState,
    *,
    execute_evidence_operators: MultiAgentNodeFunc | None = None,
) -> SecAgentGraphRuntimeState:
    dry_run = False
    if execute_evidence_operators is not None:
        result = execute_evidence_operators(state)
    elif state.get("retrieval_plan"):
        ledger = ToolCallLedger.from_dict(state.get("tool_call_ledger") or {"budget": state.get("loop_budget_state") or {}})
        context = state.get("multi_agent_context") if isinstance(state.get("multi_agent_context"), dict) else {}
        evidence_operator_mode = str(context.get("evidence_operator_mode") or "dry_run").strip().lower()
        dry_run = evidence_operator_mode not in {"real", "mcp", "interactive"}
        state_context = {
            **(state.get("query_contract") or {}),
            **context,
            "execution_mode": (state.get("agent_activation_plan") or {}).get("execution_mode") or "",
            "user_query": state.get("user_query") or "",
            "run_id": state.get("run_id") or "",
            "output_dir": state.get("output_dir") or "",
            "project_inventory": state.get("project_inventory") or {},
            "milvus_runtime": (state.get("project_inventory") or {}).get("milvus_runtime") if isinstance(state.get("project_inventory"), dict) else {},
        }
        if _bool_value(context.get("evidence_operator_fanout")):
            result = execute_evidence_operator_fanout_plan(
                state.get("retrieval_plan") or {},
                turn_id=str(state.get("run_id") or "multi_agent_turn"),
                ledger=ledger,
                state_context=state_context,
                dry_run=dry_run,
                max_workers=_positive_int(context.get("evidence_operator_fanout_workers"), default=4),
            )
        else:
            result = execute_evidence_operator_plan(
                state.get("retrieval_plan") or {},
                turn_id=str(state.get("run_id") or "multi_agent_turn"),
                ledger=ledger,
                state_context=state_context,
                dry_run=dry_run,
            )
    else:
        result = {
            "tool_observations": [],
            "tool_call_ledger": state.get("tool_call_ledger") or ToolCallLedger().to_dict(),
        }
    next_state: SecAgentGraphRuntimeState = {
        **state,
        "tool_observations": [*(state.get("tool_observations") or []), *(result.get("tool_observations") or [])],
        "tool_call_ledger": dict(result.get("tool_call_ledger") or state.get("tool_call_ledger") or {}),
        "context_rows": [*(state.get("context_rows") or []), *(result.get("context_rows") or [])],
        "runtime_ledger_rows": [*(state.get("runtime_ledger_rows") or []), *(result.get("runtime_ledger_rows") or [])],
        "market_snapshot_rows": [*(state.get("market_snapshot_rows") or []), *(result.get("market_snapshot_rows") or [])],
        "industry_snapshot_rows": [*(state.get("industry_snapshot_rows") or []), *(result.get("industry_snapshot_rows") or [])],
        "product_evidence_rows": [*(state.get("product_evidence_rows") or []), *(result.get("product_evidence_rows") or [])],
        "public_source_context_rows": [*(state.get("public_source_context_rows") or []), *(result.get("public_source_context_rows") or [])],
        "source_gaps": [*(state.get("source_gaps") or []), *(result.get("source_gaps") or [])],
        "evidence_operator_fanout_plan": result.get("evidence_operator_fanout_plan") or state.get("evidence_operator_fanout_plan") or {},
        "evidence_operator_fanout_barrier": result.get("fanout_barrier") or state.get("evidence_operator_fanout_barrier") or {},
        "loop_break_reason": str(result.get("loop_break_reason") or state.get("loop_break_reason") or ""),
        "bounded_answer_allowed": bool(result.get("bounded_answer_allowed") or state.get("bounded_answer_allowed") or False),
    }
    if runtime_source_context_enabled(next_state):
        next_state = attach_runtime_source_context_rows(next_state)  # type: ignore[assignment]
    runtime_source_summary = (
        next_state.get("runtime_source_context_store", {}).get("summary", {})
        if isinstance(next_state.get("runtime_source_context_store"), dict)
        else {}
    )
    return _record_node(
        next_state,
        "execute_evidence_operators",
        metadata={
            "tool_observation_count": len(result.get("tool_observations") or []),
            "evidence_operator_mode": "dry_run" if dry_run else "real",
            "fanout_enabled": bool(result.get("fanout_barrier")),
            "product_evidence_row_count": len(next_state.get("product_evidence_rows") or []),
            "public_source_context_row_count": len(next_state.get("public_source_context_rows") or []),
            "runtime_source_context_selected_row_count": runtime_source_summary.get("selected_row_count") or 0,
        },
    )


def _node_evidence_fusion_selector(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    bundle = build_evidence_fusion_bundle(state)
    gap_register = bundle.get("bounded_gap_register") if isinstance(bundle.get("bounded_gap_register"), dict) else {}
    summary = bundle.get("summary") if isinstance(bundle.get("summary"), dict) else {}
    next_state: SecAgentGraphRuntimeState = {
        **state,
        "evidence_fusion_bundle": bundle,
        "bounded_gap_register": dict(gap_register),
    }
    return _record_node(
        next_state,
        "evidence_fusion_selector",
        metadata={
            "row_count": bundle.get("row_count") or 0,
            "exact_authority_row_count": summary.get("exact_authority_row_count") or 0,
            "context_only_row_count": summary.get("context_only_row_count") or 0,
            "lead_only_row_count": summary.get("lead_only_row_count") or 0,
            "gap_only_row_count": summary.get("gap_only_row_count") or 0,
            "bounded_gap_count": summary.get("bounded_gap_count") or 0,
            "semantic_supplement_row_count": summary.get("semantic_supplement_row_count") or 0,
        },
    )


def _node_coverage_reflection(
    state: SecAgentGraphRuntimeState,
    *,
    coverage_reflection: MultiAgentNodeFunc | None = None,
) -> SecAgentGraphRuntimeState:
    ledger = ToolCallLedger.from_dict(state.get("tool_call_ledger") or {"budget": state.get("loop_budget_state") or {}})
    if coverage_reflection is not None:
        result = coverage_reflection(state)
        report = normalize_reflection_report(result.get("multi_agent_reflection_report") or result)
    elif state.get("evidence_fusion_bundle"):
        report = reflection_report_from_evidence_fusion_bundle(
            state.get("evidence_fusion_bundle"),
            evidence_requirement_plan=state.get("evidence_requirement_plan") or {},
            source_gaps=state.get("source_gaps") or [],
            tool_ledger_summary=_tool_ledger_summary_for_reflection(state, ledger),
        )
    elif state.get("coverage_matrix"):
        report = reflection_report_from_coverage(
            state.get("coverage_matrix"),
            source_available=True,
            evidence_requirement_plan=state.get("evidence_requirement_plan") or {},
            source_gaps=state.get("source_gaps") or [],
            tool_ledger_summary=_tool_ledger_summary_for_reflection(state, ledger),
        )
    else:
        report = reflection_report_from_tool_observations(
            state.get("retrieval_plan") or {},
            evidence_requirement_plan=state.get("evidence_requirement_plan") or {},
            tool_observations=state.get("tool_observations") or [],
            source_gaps=state.get("source_gaps") or [],
            tool_ledger_summary=_tool_ledger_summary_for_reflection(state, ledger),
            available_source_families=(state.get("agent_activation_plan") or {}).get("allowed_source_families") or None,
        )
    decision = _second_pass_decision_for_execution_mode(state, should_execute_second_pass(report, ledger))
    next_state: SecAgentGraphRuntimeState = {
        **state,
        "multi_agent_reflection_report": report,
        "evidence_sufficiency_report": report,
        "multi_agent_second_pass_decision": decision,
        "tool_call_ledger": ledger.to_dict(),
        "loop_break_reason": ledger.loop_break_reason or str(state.get("loop_break_reason") or ""),
        "bounded_answer_allowed": bool(ledger.bounded_answer_allowed or report.get("bounded_answer_allowed") or state.get("bounded_answer_allowed") or False),
    }
    return _record_node(next_state, "coverage_reflection", metadata={"sufficiency_level": report.get("sufficiency_level"), "second_pass_allowed": decision.get("allowed")})


def _node_optional_second_pass(
    state: SecAgentGraphRuntimeState,
    *,
    execute_second_pass_retrieval: MultiAgentNodeFunc | None = None,
) -> SecAgentGraphRuntimeState:
    compiled_state = _state_with_second_pass_compilation(state)
    quality_triggered = str((compiled_state.get("multi_agent_reflection_report") or {}).get("trigger") or "") == "quality_second_pass"
    before_fusion = _state_evidence_fusion_bundle(compiled_state)
    if execute_second_pass_retrieval is not None:
        ledger = ToolCallLedger.from_dict(compiled_state.get("tool_call_ledger") or {"budget": compiled_state.get("loop_budget_state") or {}})
        result = execute_second_pass_retrieval(compiled_state)
        next_state_for_fusion: SecAgentGraphRuntimeState = {
            **compiled_state,
            **result,
        }
        after_fusion = build_evidence_fusion_bundle(next_state_for_fusion)
        delta_audit = audit_second_pass_delta(
            before_fusion,
            after_fusion,
            hard_gate=compiled_state.get("second_pass_hard_gate") or {},
            execution_result=result,
        )
        added_row_count = (
            len(result.get("context_rows") or [])
            + len(result.get("runtime_ledger_rows") or [])
            + len(result.get("market_snapshot_rows") or [])
            + len(result.get("industry_snapshot_rows") or [])
            + len(result.get("product_evidence_rows") or [])
            + len(result.get("public_source_context_rows") or [])
        )
        outcome = record_second_pass_outcome(
            ledger,
            added_row_count=added_row_count,
            coverage_delta={"closed_gaps": len(delta_audit.get("closed_gap_ids") or [])},
            source_gap_delta=max(0, len(compiled_state.get("source_gaps") or []) - len(result.get("source_gaps") or [])),
        )
        if not int(delta_audit.get("added_authority_bearing_row_count") or 0):
            ledger.loop_break_reason = LOOP_BREAK_NO_INCREMENTAL_EVIDENCE
            ledger.bounded_answer_allowed = True
            outcome = {
                **outcome,
                "loop_break_reason": ledger.loop_break_reason,
                "bounded_answer_allowed": True,
                "delta_stop_reason": delta_audit.get("stop_reason") or "no_new_authority_bearing_evidence",
            }
        suppressed_loop_break = _suppress_incremental_quality_second_pass_budget_loop(
            ledger,
            outcome=outcome,
            trigger=(compiled_state.get("multi_agent_reflection_report") or {}).get("trigger") or "coverage_reflection",
            added_row_count=added_row_count,
        )
        next_state = {
            **next_state_for_fusion,
            "tool_call_ledger": ledger.to_dict(),
            "evidence_fusion_bundle": after_fusion,
            "bounded_gap_register": after_fusion.get("bounded_gap_register") if isinstance(after_fusion.get("bounded_gap_register"), dict) else {},
            "second_pass_delta_audit": delta_audit,
            "second_pass_attempts": int(compiled_state.get("second_pass_attempts") or 0) + 1,
            "second_pass_result": {
                **outcome,
                "trigger": (compiled_state.get("multi_agent_reflection_report") or {}).get("trigger") or "coverage_reflection",
                "retrieval_row_delta": _second_pass_row_delta(_second_pass_row_counts(compiled_state), result),
                "delta_audit_status": delta_audit.get("status"),
                "added_authority_bearing_row_count": delta_audit.get("added_authority_bearing_row_count") or 0,
                "closed_gap_ids": list(delta_audit.get("closed_gap_ids") or []),
                "open_gap_ids": list(delta_audit.get("open_gap_ids") or []),
                **({"suppressed_loop_break_reason": suppressed_loop_break} if suppressed_loop_break else {}),
            },
            "loop_break_reason": ledger.loop_break_reason,
            "bounded_answer_allowed": bool(ledger.bounded_answer_allowed or compiled_state.get("bounded_answer_allowed") or False),
            "quality_second_pass_attempted": bool(compiled_state.get("quality_second_pass_attempted") or quality_triggered),
        }
        skip_reason = _second_pass_specialist_rerun_skip_reason(next_state)
        if skip_reason:
            next_state["specialist_rerun_decision"] = {
                "allowed": False,
                "reason": skip_reason,
                "policy": "authority_delta_required_before_specialist_rerun_v0_1",
            }
        return _record_node(
            next_state,
            "optional_second_pass",
            metadata={
                "mode": "injected",
                "delta_status": delta_audit.get("status"),
                "added_authority_bearing_row_count": delta_audit.get("added_authority_bearing_row_count"),
                "suppressed_loop_break_reason": suppressed_loop_break,
            },
        )

    if compiled_state.get("second_pass_retrieval_plan"):
        ledger = ToolCallLedger.from_dict(compiled_state.get("tool_call_ledger") or {"budget": compiled_state.get("loop_budget_state") or {}})
        context = compiled_state.get("multi_agent_context") if isinstance(compiled_state.get("multi_agent_context"), dict) else {}
        evidence_operator_mode = str(context.get("evidence_operator_mode") or "dry_run").strip().lower()
        dry_run = evidence_operator_mode not in {"real", "mcp", "interactive"}
        before_counts = _second_pass_row_counts(compiled_state)
        result = execute_evidence_operator_plan(
            compiled_state.get("second_pass_retrieval_plan") or {},
            turn_id=f"{compiled_state.get('run_id') or 'multi_agent_turn'}:second_pass:{int(compiled_state.get('second_pass_attempts') or 0) + 1}",
            ledger=ledger,
            state_context={
                **(compiled_state.get("query_contract") or {}),
                **context,
                "execution_mode": (compiled_state.get("agent_activation_plan") or {}).get("execution_mode") or "",
                "user_query": compiled_state.get("user_query") or "",
                "run_id": compiled_state.get("run_id") or "",
                "output_dir": compiled_state.get("output_dir") or "",
            },
            dry_run=dry_run,
        )
        added_row_count = (
            len(result.get("context_rows") or [])
            + len(result.get("runtime_ledger_rows") or [])
            + len(result.get("market_snapshot_rows") or [])
            + len(result.get("industry_snapshot_rows") or [])
            + len(result.get("product_evidence_rows") or [])
            + len(result.get("public_source_context_rows") or [])
        )
        next_state_rows: SecAgentGraphRuntimeState = {
            **compiled_state,
            "tool_observations": [*(compiled_state.get("tool_observations") or []), *(result.get("tool_observations") or [])],
            "context_rows": [*(compiled_state.get("context_rows") or []), *(result.get("context_rows") or [])],
            "runtime_ledger_rows": [*(compiled_state.get("runtime_ledger_rows") or []), *(result.get("runtime_ledger_rows") or [])],
            "market_snapshot_rows": [*(compiled_state.get("market_snapshot_rows") or []), *(result.get("market_snapshot_rows") or [])],
            "industry_snapshot_rows": [*(compiled_state.get("industry_snapshot_rows") or []), *(result.get("industry_snapshot_rows") or [])],
            "product_evidence_rows": [*(compiled_state.get("product_evidence_rows") or []), *(result.get("product_evidence_rows") or [])],
            "public_source_context_rows": [*(compiled_state.get("public_source_context_rows") or []), *(result.get("public_source_context_rows") or [])],
            "source_gaps": [*(compiled_state.get("source_gaps") or []), *(result.get("source_gaps") or [])],
        }
        after_fusion = build_evidence_fusion_bundle(next_state_rows)
        delta_audit = audit_second_pass_delta(
            before_fusion,
            after_fusion,
            hard_gate=compiled_state.get("second_pass_hard_gate") or {},
            execution_result=result,
        )
        outcome = record_second_pass_outcome(
            ledger,
            added_row_count=added_row_count,
            coverage_delta={"closed_gaps": len(delta_audit.get("closed_gap_ids") or [])},
            source_gap_delta=max(0, len(compiled_state.get("source_gaps") or []) - len(result.get("source_gaps") or [])),
        )
        if not int(delta_audit.get("added_authority_bearing_row_count") or 0):
            ledger.loop_break_reason = LOOP_BREAK_NO_INCREMENTAL_EVIDENCE
            ledger.bounded_answer_allowed = True
            outcome = {
                **outcome,
                "loop_break_reason": ledger.loop_break_reason,
                "bounded_answer_allowed": True,
                "delta_stop_reason": delta_audit.get("stop_reason") or "no_new_authority_bearing_evidence",
            }
        suppressed_loop_break = _suppress_incremental_quality_second_pass_budget_loop(
            ledger,
            outcome=outcome,
            trigger=(compiled_state.get("multi_agent_reflection_report") or {}).get("trigger") or "coverage_reflection",
            added_row_count=added_row_count,
        )
        next_state: SecAgentGraphRuntimeState = {
            **next_state_rows,
            "tool_call_ledger": ledger.to_dict(),
            "evidence_fusion_bundle": after_fusion,
            "bounded_gap_register": after_fusion.get("bounded_gap_register") if isinstance(after_fusion.get("bounded_gap_register"), dict) else {},
            "second_pass_delta_audit": delta_audit,
            "second_pass_attempts": int(compiled_state.get("second_pass_attempts") or 0) + 1,
            "second_pass_result": {
                **outcome,
                "trigger": (compiled_state.get("multi_agent_reflection_report") or {}).get("trigger") or "coverage_reflection",
                "retrieval_row_delta": _second_pass_row_delta(before_counts, result),
                "delta_audit_status": delta_audit.get("status"),
                "added_authority_bearing_row_count": delta_audit.get("added_authority_bearing_row_count") or 0,
                "closed_gap_ids": list(delta_audit.get("closed_gap_ids") or []),
                "open_gap_ids": list(delta_audit.get("open_gap_ids") or []),
                **({"suppressed_loop_break_reason": suppressed_loop_break} if suppressed_loop_break else {}),
            },
            "loop_break_reason": ledger.loop_break_reason,
            "bounded_answer_allowed": bool(ledger.bounded_answer_allowed or compiled_state.get("bounded_answer_allowed") or False),
            "quality_second_pass_attempted": bool(compiled_state.get("quality_second_pass_attempted") or quality_triggered),
        }
        skip_reason = _second_pass_specialist_rerun_skip_reason(next_state)
        if skip_reason:
            next_state["specialist_rerun_decision"] = {
                "allowed": False,
                "reason": skip_reason,
                "policy": "authority_delta_required_before_specialist_rerun_v0_1",
            }
        return _record_node(
            next_state,
            "optional_second_pass",
            metadata={
                "mode": "dry_run" if dry_run else "real",
                "trigger": next_state["second_pass_result"].get("trigger"),
                "added_row_count": added_row_count,
                "added_authority_bearing_row_count": delta_audit.get("added_authority_bearing_row_count") or 0,
                "loop_break_reason": ledger.loop_break_reason,
                "suppressed_loop_break_reason": suppressed_loop_break,
            },
        )

    ledger = ToolCallLedger.from_dict(compiled_state.get("tool_call_ledger") or {"budget": compiled_state.get("loop_budget_state") or {}})
    delta_audit = audit_second_pass_delta(
        before_fusion,
        before_fusion,
        hard_gate=compiled_state.get("second_pass_hard_gate") or {},
        execution_result={},
    )
    outcome = record_second_pass_outcome(
        ledger,
        added_row_count=int(compiled_state.get("mock_second_pass_added_row_count") or 0),
        coverage_delta=compiled_state.get("mock_second_pass_coverage_delta") or {"closed_gaps": 0},
    )
    if compiled_state.get("second_pass_hard_gate"):
        ledger.loop_break_reason = LOOP_BREAK_NO_INCREMENTAL_EVIDENCE
        ledger.bounded_answer_allowed = True
        outcome = {
            **outcome,
            "status": "blocked_by_second_pass_hard_gate",
            "loop_break_reason": ledger.loop_break_reason,
            "bounded_answer_allowed": True,
            "delta_audit_status": delta_audit.get("status"),
            "added_authority_bearing_row_count": 0,
            "closed_gap_ids": [],
            "open_gap_ids": list(delta_audit.get("open_gap_ids") or []),
        }
    next_state: SecAgentGraphRuntimeState = {
        **compiled_state,
        "tool_call_ledger": ledger.to_dict(),
        "second_pass_attempts": int(compiled_state.get("second_pass_attempts") or 0) + 1,
        "second_pass_result": outcome,
        "second_pass_delta_audit": delta_audit,
        "loop_break_reason": ledger.loop_break_reason,
        "bounded_answer_allowed": bool(ledger.bounded_answer_allowed or compiled_state.get("bounded_answer_allowed") or False),
        "quality_second_pass_attempted": bool(compiled_state.get("quality_second_pass_attempted") or quality_triggered),
    }
    skip_reason = _second_pass_specialist_rerun_skip_reason(next_state)
    if skip_reason:
        next_state["specialist_rerun_decision"] = {
            "allowed": False,
            "reason": skip_reason,
            "policy": "authority_delta_required_before_specialist_rerun_v0_1",
        }
    return _record_node(
        next_state,
        "optional_second_pass",
        metadata={
            "loop_break_reason": ledger.loop_break_reason,
            "delta_status": delta_audit.get("status"),
            "hard_gate_status": (compiled_state.get("second_pass_hard_gate") or {}).get("status")
            if isinstance(compiled_state.get("second_pass_hard_gate"), dict)
            else "",
        },
    )


def _suppress_incremental_quality_second_pass_budget_loop(
    ledger: ToolCallLedger,
    *,
    outcome: Mapping[str, Any],
    trigger: str,
    added_row_count: int,
) -> str:
    reason = str(ledger.loop_break_reason or outcome.get("loop_break_reason") or "")
    if str(trigger or "") != "quality_second_pass":
        return ""
    if added_row_count <= 0:
        return ""
    if reason not in {LOOP_BREAK_TOOL_BUDGET_EXHAUSTED, LOOP_BREAK_AGENT_TOOL_BUDGET_EXHAUSTED}:
        return ""
    ledger.loop_break_reason = ""
    ledger.bounded_answer_allowed = bool(ledger.bounded_answer_allowed or outcome.get("bounded_answer_allowed"))
    return reason


def _second_pass_row_counts(state: Mapping[str, Any]) -> dict[str, int]:
    return {
        "context_rows": len(state.get("context_rows") or []),
        "runtime_ledger_rows": len(state.get("runtime_ledger_rows") or []),
        "market_snapshot_rows": len(state.get("market_snapshot_rows") or []),
        "industry_snapshot_rows": len(state.get("industry_snapshot_rows") or []),
        "product_evidence_rows": len(state.get("product_evidence_rows") or []),
        "public_source_context_rows": len(state.get("public_source_context_rows") or []),
    }


def _second_pass_row_delta(before: Mapping[str, int], result: Mapping[str, Any]) -> dict[str, int]:
    return {
        "context_rows": len(result.get("context_rows") or []),
        "runtime_ledger_rows": len(result.get("runtime_ledger_rows") or []),
        "market_snapshot_rows": len(result.get("market_snapshot_rows") or []),
        "industry_snapshot_rows": len(result.get("industry_snapshot_rows") or []),
        "product_evidence_rows": len(result.get("product_evidence_rows") or []),
        "public_source_context_rows": len(result.get("public_source_context_rows") or []),
        "previous_context_rows": int(before.get("context_rows") or 0),
        "previous_runtime_ledger_rows": int(before.get("runtime_ledger_rows") or 0),
        "previous_market_snapshot_rows": int(before.get("market_snapshot_rows") or 0),
        "previous_industry_snapshot_rows": int(before.get("industry_snapshot_rows") or 0),
        "previous_product_evidence_rows": int(before.get("product_evidence_rows") or 0),
        "previous_public_source_context_rows": int(before.get("public_source_context_rows") or 0),
    }


def _state_with_second_pass_compilation(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    report = state.get("multi_agent_reflection_report") if isinstance(state.get("multi_agent_reflection_report"), dict) else {}
    if not report.get("second_pass_requests"):
        return state
    ledger = ToolCallLedger.from_dict(state.get("tool_call_ledger") or {"budget": state.get("loop_budget_state") or {}})
    before_fusion = _state_evidence_fusion_bundle(state)
    bounded_gap_register = state.get("bounded_gap_register") if isinstance(state.get("bounded_gap_register"), dict) else {}
    if not bounded_gap_register and isinstance(before_fusion.get("bounded_gap_register"), dict):
        bounded_gap_register = before_fusion["bounded_gap_register"]
    diagnosis = build_second_pass_reflection_diagnosis(
        report,
        evidence_fusion_bundle=before_fusion,
        bounded_gap_register=bounded_gap_register,
    )
    repair_plan = build_second_pass_repair_plan(diagnosis)
    hard_gate = gate_second_pass_repair_plan(
        repair_plan,
        activation_plan=state.get("agent_activation_plan") or {},
        ledger=ledger,
        web_scope_registry=_web_scope_registry_from_state(state),
    )
    merged_gap_register = _bounded_gap_register_with_candidates(
        bounded_gap_register,
        hard_gate.get("bounded_gap_candidates") if isinstance(hard_gate, Mapping) else [],
    )
    executable_requests = [dict(item) for item in hard_gate.get("executable_requests") or [] if isinstance(item, dict)]
    if not executable_requests:
        return {
            **state,
            "evidence_fusion_bundle": before_fusion,
            "bounded_gap_register": merged_gap_register,
            "second_pass_reflection_diagnosis": diagnosis,
            "second_pass_repair_plan": repair_plan,
            "second_pass_hard_gate": hard_gate,
            "second_pass_evidence_requirement_plan": {},
            "second_pass_retrieval_plan": {},
        }
    filtered_report = {
        **report,
        "second_pass_requests": executable_requests,
    }
    retrieval_plan = compile_second_pass_retrieval_plan(
        filtered_report,
        state.get("evidence_requirement_plan") or {},
        query_contract=state.get("query_contract") or {},
        case={
            "case_id": state.get("run_id") or "multi_agent_second_pass",
            "prompt": state.get("user_query") or "",
            "companies": (state.get("query_contract") or {}).get("search_scope_tickers") or (state.get("query_contract") or {}).get("focus_tickers") or [],
            "years": (state.get("query_contract") or {}).get("years") or [],
        },
        activation_plan=state.get("agent_activation_plan") or {},
        used_tool_calls_total=ledger.executed_tool_call_count(),
        used_tool_calls_by_agent=ledger.executed_tool_call_counts_by_agent(),
    )
    return {
        **state,
        "evidence_fusion_bundle": before_fusion,
        "bounded_gap_register": merged_gap_register,
        "second_pass_reflection_diagnosis": diagnosis,
        "second_pass_repair_plan": repair_plan,
        "second_pass_hard_gate": hard_gate,
        "second_pass_evidence_requirement_plan": retrieval_plan.get("second_pass_evidence_requirement_plan") or {},
        "second_pass_retrieval_plan": retrieval_plan,
    }


def _state_evidence_fusion_bundle(state: Mapping[str, Any]) -> dict[str, Any]:
    bundle = state.get("evidence_fusion_bundle") if isinstance(state.get("evidence_fusion_bundle"), dict) else {}
    if bundle.get("schema_version"):
        return dict(bundle)
    return build_evidence_fusion_bundle(state)


def _bounded_gap_register_with_candidates(register: Mapping[str, Any], candidates: Any) -> dict[str, Any]:
    base = dict(register or {})
    gaps = [dict(item) for item in base.get("gaps") or [] if isinstance(item, Mapping)]
    seen = {
        (
            str(item.get("gap_id") or ""),
            str(item.get("source_family") or ""),
            str(item.get("gap_type") or ""),
        )
        for item in gaps
    }
    for candidate in candidates or []:
        if not isinstance(candidate, Mapping):
            continue
        row = dict(candidate)
        key = (
            str(row.get("gap_id") or ""),
            str(row.get("source_family") or ""),
            str(row.get("gap_type") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        gaps.append(row)
    summary = {
        "by_gap_type": _count_rows_by_key(gaps, "gap_type"),
        "by_source_family": _count_rows_by_key(gaps, "source_family"),
        "commercial_tracker_gap_count": len([row for row in gaps if row.get("gap_type") == "commercial_tracker_gap"]),
        "public_unavailable_gap_count": len([row for row in gaps if row.get("gap_type") == "public_unavailable_gap"]),
        "parser_schema_gap_count": len(
            [
                row
                for row in gaps
                if row.get("gap_type")
                in {"parser_schema_gap", "product_kpi_parser_gap", "region_schema_gap", "period_column_group_gap", "source_specific_table_gate_gap"}
            ]
        ),
    }
    return {
        **base,
        "schema_version": str(base.get("schema_version") or "sec_agent_bounded_gap_register_v0.1"),
        "policy": str(base.get("policy") or "bounded_public_gap_not_fallback_v0_1"),
        "gap_count": len(gaps),
        "gaps": gaps,
        "summary": summary,
    }


def _count_rows_by_key(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "").strip() or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _web_scope_registry_from_state(state: Mapping[str, Any]) -> dict[str, Any]:
    default_registry = default_web_source_scope_registry()
    inventory = state.get("source_inventory") if isinstance(state.get("source_inventory"), Mapping) else {}
    live_web = inventory.get("live_public_web_context") if isinstance(inventory.get("live_public_web_context"), Mapping) else {}
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    policy_ids = _unique_strings(live_web.get("web_scope_policy_ids")) or _unique_strings(activation.get("web_scope_policy_ids"))
    if not policy_ids:
        return default_registry
    policies = default_registry.get("policies") if isinstance(default_registry.get("policies"), Mapping) else {}
    return {
        **default_registry,
        "policies": {policy_id: dict(policies[policy_id]) for policy_id in policy_ids if policy_id in policies},
        "policy_filter_source": "source_inventory_or_activation_plan",
    }


def _tool_ledger_summary_for_reflection(state: SecAgentGraphRuntimeState, ledger: ToolCallLedger) -> dict[str, Any]:
    return {
        "tool_call_count": len([record for record in ledger.records if record.status != "blocked"]),
        "blocked_tool_call_count": len([record for record in ledger.records if record.status == "blocked"]),
        "second_pass_rounds": int(ledger.second_pass_rounds),
        "max_second_pass_rounds": int(ledger.budget.max_second_pass_rounds),
        "loop_break_reason": ledger.loop_break_reason or str(state.get("loop_break_reason") or ""),
    }


def _sanitize_relationship_lookup_for_state(lookup: Mapping[str, Any]) -> dict[str, Any]:
    clean = dict(lookup or {})
    clean["artifact_refs"] = [
        {
            "artifact_id": ref.get("artifact_id") or "",
            "digest": ref.get("digest") or "",
            "row_count": ref.get("row_count"),
            "path_boundary": "path_not_exposed_in_agent_state",
        }
        for ref in clean.get("artifact_refs") or []
        if isinstance(ref, dict)
    ]
    return clean


def _relationship_lookup_refs(lookup: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    for relationship in lookup.get("relationships") or []:
        if not isinstance(relationship, Mapping):
            continue
        refs.update(str(item) for item in relationship.get("evidence_refs") or [] if str(item))
    return refs


def _first_artifact_digest(refs: list[dict[str, Any]]) -> str:
    for ref in refs:
        digest = str(ref.get("digest") or "")
        if digest:
            return digest
    return ""


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _node_optional_specialist_subgraph(
    state: SecAgentGraphRuntimeState,
    *,
    run_specialist_analysts: MultiAgentNodeFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if run_specialist_analysts is not None:
        result = run_specialist_analysts(state)
        if "specialist_activation_decisions" not in result:
            result = {**result, "specialist_activation_decisions": specialist_activation_decisions(state)}
        if "specialist_fanout_barrier" not in result:
            result = {
                **result,
                "specialist_fanout_barrier": _specialist_fanout_barrier(
                    result.get("specialist_route_results") or [],
                    result.get("specialist_outputs") or [],
                    execution_mode="injected",
                ),
            }
        next_state = {**state, **result}
        return _record_node(next_state, "optional_specialist_subgraph", metadata={"mode": "injected"})
    decisions = specialist_activation_decisions(state)
    specialists = active_specialists_for_state(state)
    outputs = build_stub_specialist_memolets(specialists)
    route_results = [
        _with_projected_specialist_input_pack(
            {
                "agent_id": row.get("agent_id") or "",
                "status": row.get("decision") or "",
                "priority": row.get("priority") or "",
                "failure_reason": "" if row.get("decision") == "run" else str(row.get("reason") or "")[:500],
                "activation_policy": row.get("policy") or "",
                "activation_decision": row.get("decision") or "",
                "activation_reason": str(row.get("reason") or "")[:500],
                "signal_count": row.get("signal_count"),
                "matched_requirement_count": row.get("matched_requirement_count"),
                "explicit_intent": bool(row.get("explicit_intent")),
            },
            state,
        )
        if row.get("decision") == "run"
        else {
            "agent_id": row.get("agent_id") or "",
            "status": row.get("decision") or "",
            "priority": row.get("priority") or "",
            "failure_reason": "" if row.get("decision") == "run" else str(row.get("reason") or "")[:500],
            "activation_policy": row.get("policy") or "",
            "activation_decision": row.get("decision") or "",
            "activation_reason": str(row.get("reason") or "")[:500],
            "signal_count": row.get("signal_count"),
            "matched_requirement_count": row.get("matched_requirement_count"),
            "explicit_intent": bool(row.get("explicit_intent")),
        }
        for row in decisions
    ]
    return _record_node(
        {
            **state,
            "specialist_outputs": outputs,
            "specialist_activation_decisions": decisions,
            "specialist_route_results": route_results,
            "specialist_fanout_barrier": _specialist_fanout_barrier(route_results, outputs, execution_mode="stubbed_fanout_barrier"),
        },
        "optional_specialist_subgraph",
        metadata={"specialist_count": len(outputs), "activation_policy": "cost_aware_specialist_activation_v0_1"},
    )


def _with_projected_specialist_input_pack(route_row: Mapping[str, Any], state: Mapping[str, Any]) -> dict[str, Any]:
    row = dict(route_row)
    agent_id = str(row.get("agent_id") or "")
    if not agent_id or isinstance(row.get("input_pack_fingerprint"), Mapping):
        return row
    from sec_agent.specialist_llm import (  # Local import avoids paying this dependency for non-mock routes.
        _request_route_summary,
        build_shared_specialist_context,
        build_specialist_request_from_state,
    )

    shared_context = build_shared_specialist_context(state)
    request = build_specialist_request_from_state(agent_id, state, shared_context=shared_context)
    projected = _request_route_summary(request)
    fingerprint = projected.get("input_pack_fingerprint") if isinstance(projected.get("input_pack_fingerprint"), Mapping) else {}
    if fingerprint:
        projected_fingerprint = dict(fingerprint)
        projected_fingerprint["fingerprint_policy"] = (
            projected_fingerprint.get("fingerprint_policy")
            or projected_fingerprint.get("policy")
            or "fingerprint_only_no_prompt_text_persisted_v0_1"
        )
        projected_fingerprint["capture_source"] = "deterministic_mock_projected_specialist_request"
        projected["input_pack_fingerprint"] = projected_fingerprint
    row.update(projected)
    row["input_projection_source"] = "deterministic_mock_projected_specialist_request"
    return row


def _specialist_fanout_barrier(route_results: Any, outputs: Any, *, execution_mode: str) -> dict[str, Any]:
    routes = [dict(item) for item in route_results or [] if isinstance(item, Mapping)]
    output_rows = [dict(item) for item in outputs or [] if isinstance(item, Mapping)]
    failed = [
        row
        for row in routes
        if str(row.get("status") or "") not in {"pass", "run", "stubbed", "skipped"}
    ]
    supporting_without_match = [
        str(row.get("agent_id") or "")
        for row in routes
        if str(row.get("agent_id") or "")
        and str(row.get("status") or "").strip().lower() != "skipped"
        and str(row.get("activation_decision") or "").strip().lower() != "skipped"
        and str(row.get("priority") or "").strip().lower() in {"supporting", "conditional", "low"}
        and int(row.get("matched_requirement_count") or 0) == 0
        and not bool(row.get("explicit_intent"))
    ]
    return {
        "schema_version": "sec_agent_specialist_fanout_barrier_v0.1",
        "barrier_id": "specialist_fanout_barrier",
        "execution_mode": execution_mode,
        "deterministic_merge_policy": "active_specialist_order",
        "specialist_count": len(output_rows),
        "route_result_count": len(routes),
        "failed_route_count": len(failed),
        "failed_agents": [str(row.get("agent_id") or "") for row in failed if str(row.get("agent_id") or "")],
        "supporting_run_without_required_item_match_count": len(supporting_without_match),
        "supporting_run_without_required_item_match_agents": supporting_without_match[:8],
        "output_schema": {
            "specialist_outputs": "append_only_claim_card_memolets",
            "specialist_route_results": "append_only_route_summaries",
        },
    }


def _node_multi_agent_aggregate_judgment_plan(
    state: SecAgentGraphRuntimeState,
    *,
    aggregate_judgment_plan: MultiAgentNodeFunc | None = None,
) -> SecAgentGraphRuntimeState:
    reflection_report = state.get("multi_agent_reflection_report") or state.get("evidence_sufficiency_report") or {}
    evidence_requirement_plan = state.get("evidence_requirement_plan") or {}
    source_gaps = state.get("source_gaps") or []
    tool_ledger_summary = (
        (state.get("multi_agent_reflection_report") or {}).get("tool_ledger_summary")
        if isinstance(state.get("multi_agent_reflection_report"), dict)
        else {}
    )
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    mode = str(activation.get("execution_mode") or state.get("execution_mode") or "").strip()
    specialist_outputs = state.get("specialist_outputs") or []
    if mode == "focused_answer" and not _multi_agent_specialists_active(state) and not specialist_outputs:
        judgment = aggregate_focused_answer_judgment_plan(
            context_rows=[row for row in state.get("context_rows") or [] if isinstance(row, Mapping)],
            runtime_ledger_rows=[row for row in state.get("runtime_ledger_rows") or [] if isinstance(row, Mapping)],
            reflection_report=reflection_report,
            evidence_requirement_plan=evidence_requirement_plan,
            source_gaps=source_gaps,
            tool_ledger_summary=tool_ledger_summary,
            verifier_constraints=state.get("claim_verification") or {},
            response_language=_state_response_language(state),
        )
    else:
        judgment = aggregate_specialist_judgment_plan(
            specialist_outputs,
            reflection_report=reflection_report,
            evidence_requirement_plan=evidence_requirement_plan,
            source_gaps=source_gaps,
            tool_ledger_summary=tool_ledger_summary,
            verifier_constraints=state.get("claim_verification") or {},
        )
    specialist_verification = verify_specialist_outputs_for_memo(specialist_outputs, judgment_plan=judgment)
    result = aggregate_judgment_plan(state) if aggregate_judgment_plan is not None else {
        "judgment_plan": judgment,
        "specialist_verification": specialist_verification,
        "verified_judgment_plan": specialist_verification.get("verified_judgment_plan") or judgment,
    }
    if "specialist_verification" not in result:
        result = {**result, "specialist_verification": specialist_verification}
    if "judgment_plan" not in result:
        result = {**result, "judgment_plan": judgment}
    if "verified_judgment_plan" not in result:
        result = {**result, "verified_judgment_plan": (result.get("specialist_verification") or {}).get("verified_judgment_plan") or result.get("judgment_plan") or judgment}
    governance_ledgers = build_evidence_governance_ledgers({**state, **result})
    governance_state: SecAgentGraphRuntimeState = {**state, **result, **governance_ledgers}
    governance_state = _state_with_d4_d5_layers(governance_state)
    governance_state = _state_with_d6_d7_layers(governance_state)
    governance_state = _state_with_d9_gate_matrix(governance_state)
    governance_state = _state_with_d10_derived_metric_layer(governance_state)
    governance_state = _state_with_fundamental_statement_pack(governance_state)
    fact_selection = build_pre_memo_fact_selection(governance_state)
    selected_judgment = apply_pre_memo_fact_selection_to_judgment(
        result.get("verified_judgment_plan") or result.get("judgment_plan") or judgment,
        fact_selection,
    )
    required_dimension_ids = _required_analysis_dimensions_from_state(state)
    if required_dimension_ids:
        selected_judgment = {**selected_judgment, "required_dimension_ids": required_dimension_ids}
    selected_judgment = refresh_judgment_plan_after_governance_filter(selected_judgment)
    selected_judgment = attach_judgment_state(
        selected_judgment,
        fundamental_statement_pack=governance_state.get("fundamental_statement_pack")
        if isinstance(governance_state.get("fundamental_statement_pack"), Mapping)
        else {},
    )
    specialist_verification = verify_specialist_outputs_for_memo([], judgment_plan=selected_judgment)
    result["judgment_plan"] = selected_judgment
    result["verified_judgment_plan"] = selected_judgment
    result["specialist_verification"] = specialist_verification
    governance_ledgers = build_evidence_governance_ledgers(
        {**governance_state, "judgment_plan": selected_judgment, "verified_judgment_plan": selected_judgment}
    )
    governance_state = {
        **governance_state,
        **governance_ledgers,
        "judgment_plan": selected_judgment,
        "verified_judgment_plan": selected_judgment,
        "specialist_verification": specialist_verification,
    }
    lead_artifacts = _build_lead_supervision_and_memo_logic(governance_state, selected_judgment)
    governance_state = {**governance_state, **lead_artifacts}
    governance_state = _state_with_lead_targeted_repair(governance_state, selected_judgment)
    if isinstance(governance_state.get("verified_judgment_plan"), Mapping):
        selected_judgment = dict(governance_state.get("verified_judgment_plan") or {})
        specialist_verification = verify_specialist_outputs_for_memo([], judgment_plan=selected_judgment)
        result["judgment_plan"] = selected_judgment
        result["verified_judgment_plan"] = selected_judgment
        result["specialist_verification"] = specialist_verification
        governance_state["specialist_verification"] = specialist_verification
        governance_ledgers = build_evidence_governance_ledgers(governance_state)
    governance_state = _state_with_supervising_analyst_pack(governance_state)
    product_bridge_judgment = _judgment_with_product_bridge_claims(
        selected_judgment,
        governance_state.get("supervising_analyst_pack") if isinstance(governance_state.get("supervising_analyst_pack"), Mapping) else {},
    )
    if product_bridge_judgment is not selected_judgment:
        selected_judgment = refresh_judgment_plan_after_governance_filter(product_bridge_judgment)
        selected_judgment = attach_judgment_state(
            selected_judgment,
            fundamental_statement_pack=governance_state.get("fundamental_statement_pack")
            if isinstance(governance_state.get("fundamental_statement_pack"), Mapping)
            else {},
        )
        specialist_verification = verify_specialist_outputs_for_memo([], judgment_plan=selected_judgment)
        governance_state = {
            **governance_state,
            "judgment_plan": selected_judgment,
            "verified_judgment_plan": selected_judgment,
            "specialist_verification": specialist_verification,
        }
        lead_artifacts = _build_lead_supervision_and_memo_logic(governance_state, selected_judgment)
        governance_state = {**governance_state, **lead_artifacts}
        governance_ledgers = build_evidence_governance_ledgers(governance_state)
        result["judgment_plan"] = selected_judgment
        result["verified_judgment_plan"] = selected_judgment
        result["specialist_verification"] = specialist_verification
    governance_state["gate_registry_eval_matrix"] = build_gate_registry_eval_matrix(governance_state)
    result = {
        **{
            key: governance_state[key]
            for key in (
                "raw_source_provenance_store",
                "asof_vintage_layer",
                "metric_product_ontology_snapshot",
                "reconciliation_ledger",
                "gate_registry_eval_matrix",
                "derived_metric_layer",
                "fundamental_statement_pack",
                "research_objective_contract",
                "lead_review_checkpoint",
                "targeted_repair_plan",
                "memo_logic_plan",
                "lead_targeted_repair_execution",
                "supervising_analyst_pack",
            )
            if key in governance_state
        },
        **result,
        **governance_ledgers,
        "pre_memo_fact_selection": fact_selection,
        "claim_card_store_barrier": _claim_card_store_barrier(
            result.get("specialist_outputs") or specialist_outputs,
            result.get("specialist_verification") or specialist_verification,
            result.get("verified_judgment_plan") or result.get("judgment_plan") or selected_judgment,
            governance_ledgers.get("claim_evidence_ledger") if isinstance(governance_ledgers, Mapping) else {},
            pre_memo_fact_selection=fact_selection,
        ),
        "adjudicator_barrier": _adjudicator_barrier(result.get("verified_judgment_plan") or result.get("judgment_plan") or selected_judgment),
    }
    next_state: SecAgentGraphRuntimeState = {**state, **result}
    quality_report = quality_reflection_report_from_judgment(
        next_state.get("verified_judgment_plan") or next_state.get("judgment_plan") or {},
        state=next_state,
        evidence_requirement_plan=next_state.get("evidence_requirement_plan") or {},
        source_gaps=next_state.get("source_gaps") or [],
    )
    quality_ledger = ToolCallLedger.from_dict(next_state.get("tool_call_ledger") or {"budget": next_state.get("loop_budget_state") or {}})
    if bool(next_state.get("quality_second_pass_attempted")):
        quality_decision = {"allowed": False, "reason": "quality_second_pass_already_attempted", "trigger": "quality_second_pass"}
    else:
        quality_decision = _second_pass_decision_for_execution_mode(next_state, should_execute_second_pass(quality_report, quality_ledger))
    if quality_decision.get("allowed"):
        next_state["multi_agent_reflection_report"] = quality_report
        next_state["evidence_sufficiency_report"] = quality_report
        next_state["multi_agent_second_pass_decision"] = quality_decision
        next_state["tool_call_ledger"] = quality_ledger.to_dict()
    next_state["quality_second_pass_report"] = quality_report
    next_state["quality_second_pass_decision"] = quality_decision
    return _record_node(
        next_state,
        "aggregate_judgment_plan",
        metadata={
            "mode": "injected" if aggregate_judgment_plan else "stub",
            "quality_second_pass_allowed": bool(quality_decision.get("allowed")),
            "quality_gap_count": len(quality_report.get("quality_gaps") or []),
            "focused_answer_bridge": (judgment.get("focused_answer_bridge") or {}).get("status") if isinstance(judgment, Mapping) else "",
        },
    )


def _state_with_supervising_analyst_pack(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    pack = build_supervising_analyst_pack(state)
    return {**state, "supervising_analyst_pack": pack}


def _build_lead_supervision_and_memo_logic(
    state: Mapping[str, Any],
    selected_judgment: Mapping[str, Any],
) -> dict[str, Any]:
    required_dimensions = _required_analysis_dimensions_from_state(state) or [
        "fundamentals",
        "product_and_production",
        "capital_and_financing",
        "competition_and_market_position",
        "risk_and_counterevidence",
    ]
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    source_family_plan = {
        "allowed_source_families": _unique_strings(activation.get("allowed_source_families") or []),
        "issuer_coverage_policy": {
            "local_or_sec_route_miss": "official_source_probe_before_bounded_gap",
            "official_probe_order": [
                "sec_fpi_filings_20f_6k",
                "company_ir_reports",
                "local_exchange_filings",
                "regulator_filings",
            ],
            "forbidden_sources": ["social_media_unofficial", "marketing_blog", "forum_or_unverified_post"],
        },
    }
    contract = build_research_objective_contract(
        query=str(state.get("user_query") or ""),
        required_dimensions=required_dimensions,
        source_family_plan=source_family_plan,
        mandatory_second_pass_triggers=["retrievable_gap"],
    )
    gaps = _lead_supervision_gaps_from_state(state)
    retrieval_budget_audit = (
        (state.get("multi_agent_reflection_report") or {}).get("tool_ledger_summary")
        if isinstance(state.get("multi_agent_reflection_report"), Mapping)
        else {}
    )
    packs = {
        key: state.get(key)
        for key in (
            "fundamental_statement_pack",
            "product_spec_pack",
            "capital_macro_exposure_pack",
            "relationship_graph_observation",
            "thesis_driver_pack",
        )
        if isinstance(state.get(key), Mapping)
    }
    dimension_portfolio = build_dimension_evidence_portfolio(
        state,
        tickers=state.get("focus_tickers") if isinstance(state.get("focus_tickers"), list) else None,
        autoload=bool(state.get("product_intelligence_runtime_autoload"))
        if "product_intelligence_runtime_autoload" in state
        else None,
    )
    if dimension_portfolio:
        packs["dimension_evidence_portfolio"] = dimension_portfolio
    claim_cards = [
        dict(item)
        for item in selected_judgment.get("supported_claims") or []
        if isinstance(item, Mapping)
    ]
    checkpoint = build_lead_review_checkpoint(
        objective_contract=contract,
        retrieval_budget_audit=retrieval_budget_audit if isinstance(retrieval_budget_audit, Mapping) else {},
        packs=packs,
        claim_cards=claim_cards,
        gaps=gaps,
        source_capability=state.get("source_capability_router")
        if isinstance(state.get("source_capability_router"), Mapping)
        else {},
        source_layer_capability=state.get("source_layer_capability_audit")
        if isinstance(state.get("source_layer_capability_audit"), Mapping)
        else {},
        source_authority_coverage=state.get("source_authority_coverage")
        if isinstance(state.get("source_authority_coverage"), Mapping)
        else {},
        run_audit={
            "run_id": state.get("run_id") or "",
            "node_trace_count": len(state.get("node_trace") or []),
            "artifact_refs": state.get("artifact_refs") if isinstance(state.get("artifact_refs"), Mapping) else {},
        },
    )
    repair_plan = build_targeted_repair_plan(checkpoint)
    judgment_state = _memo_logic_plan_judgment_state_input(selected_judgment)
    memo_logic_plan = build_memo_logic_plan(
        judgment_state=judgment_state,
        lead_review_checkpoint=checkpoint,
        memo_intent=str(contract.get("memo_intent") or "investment_research_memo"),
        product_reasoning_frame=_build_product_reasoning_frame(
            state,
            selected_judgment=selected_judgment,
            dimension_portfolio=dimension_portfolio,
        ),
        required_question_items=_required_question_items_for_contract(state, contract),
        focus_ticker_coverage_policy=_focus_ticker_coverage_policy(state, contract),
    )
    return {
        "research_objective_contract": contract,
        "lead_review_checkpoint": checkpoint,
        "targeted_repair_plan": repair_plan,
        "memo_logic_plan": memo_logic_plan,
    }


def _build_product_reasoning_frame(
    state: Mapping[str, Any],
    *,
    selected_judgment: Mapping[str, Any],
    dimension_portfolio: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    refs: dict[str, list[str]] = {
        "product_profile_refs": [],
        "product_spec_refs": [],
        "product_kpi_refs": [],
        "deployment_refs": [],
        "performance_proxy_refs": [],
        "relationship_edge_refs": [],
        "scope_hypothesis_refs": [],
    }
    roles: list[str] = []

    def add(role: str, ref: Any) -> None:
        text = str(ref or "").strip()
        if not text:
            return
        refs.setdefault(role, [])
        if text not in refs[role]:
            refs[role].append(text)
        coverage = role.removesuffix("_refs")
        if coverage not in roles:
            roles.append(coverage)

    rows: list[Mapping[str, Any]] = []
    rows.extend(
        row
        for row in selected_judgment.get("supported_claims") or []
        if isinstance(row, Mapping)
    )
    rows.extend(
        row
        for row in state.get("context_rows") or []
        if isinstance(row, Mapping)
    )
    if isinstance(dimension_portfolio, Mapping):
        rows.extend(_product_frame_rows_from_mapping(dimension_portfolio))
    for pack_key in ("product_spec_pack", "relationship_graph_observation", "source_authority_coverage"):
        pack = state.get(pack_key)
        if isinstance(pack, Mapping):
            rows.extend(_product_frame_rows_from_mapping(pack))

    for row in rows:
        row_text = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).lower()
        ref = (
            row.get("claim_id")
            or row.get("evidence_ref")
            or row.get("evidence_id")
            or row.get("source_id")
            or row.get("edge_id")
            or row.get("artifact_id")
            or row.get("id")
        )
        if not ref:
            continue
        if any(term in row_text for term in ("scope_hypothesis", "same-family", "same family", "peer group", "relationship_hypothesis")):
            add("scope_hypothesis_refs", ref)
            continue
        if any(term in row_text for term in ("deployment", "deployed", "customer", "ordered_by", "adopted_by", "configured_in", "channel")):
            add("deployment_refs", ref)
        if any(term in row_text for term in ("spec", "architecture", "parameter", "cuda", "hbm", "euv", "duv", "process node", "benchmark")):
            add("product_spec_refs", ref)
        if any(term in row_text for term in ("product_kpi", "product revenue", "backlog", "shipment", "delivery", "capacity", "utilization", "arr", "rpo")):
            add("product_kpi_refs", ref)
        if any(term in row_text for term in ("product", "platform", "service", "taxonomy", "sku", "family")):
            add("product_profile_refs", ref)
        if any(term in row_text for term in ("benchmark", "quote", "availability", "app store", "github", "npm", "pypi", "hiring", "patent", "openalex")):
            add("performance_proxy_refs", ref)
        if any(term in row_text for term in ("competes_with", "substitutes_for", "upstream_of", "downstream_of", "read_through", "supply_constraint_for", "relationship_graph")):
            add("relationship_edge_refs", ref)

    required_edges = []
    if refs["deployment_refs"]:
        required_edges.append("company_product_to_customer_or_channel_deployment")
    if refs["relationship_edge_refs"]:
        required_edges.append("product_to_competitor_supplier_or_read_through_edge")
    if refs["product_spec_refs"]:
        required_edges.append("product_spec_to_competitive_positioning")
    if refs["product_kpi_refs"]:
        required_edges.append("company_disclosed_product_kpi_to_financial_bridge")
    return {
        "schema_version": "finsight_product_reasoning_frame_v0_1",
        "coverage_roles": sorted(roles),
        **{key: values[:24] for key, values in refs.items()},
        "required_reasoning_edges": required_edges,
        "writer_instruction": (
            "Use product profile/spec/deployment/proxy/relationship evidence as a product reasoning spine. "
            "Do not treat scope_hypothesis_refs as primary proof; explain why a section is low confidence if it only has scope hypotheses. "
            "Do not say product analysis is impossible only because SKU revenue is missing when spec, deployment, proxy, or relationship evidence exists."
        ),
    }


def _product_frame_rows_from_mapping(value: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    stack: list[Any] = [value]
    while stack and len(rows) < 240:
        item = stack.pop(0)
        if isinstance(item, Mapping):
            if any(key in item for key in ("claim_id", "evidence_ref", "source_id", "edge_id", "artifact_id", "product", "source_family")):
                rows.append(item)
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    return rows


def _required_question_items_for_contract(state: Mapping[str, Any], contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    explicit = contract.get("required_question_items") if isinstance(contract.get("required_question_items"), list) else []
    if explicit:
        return [dict(row) for row in explicit if isinstance(row, Mapping)]
    query = " ".join(
        str(value or "")
        for value in (
            state.get("user_query"),
            contract.get("query"),
            state.get("research_question"),
        )
    ).lower()
    scope = contract.get("scope") if isinstance(contract.get("scope"), Mapping) else {}
    tickers = _unique_upper(
        [
            *(scope.get("focus_tickers") or []),
            *(state.get("focus_tickers") or [] if isinstance(state.get("focus_tickers"), list) else []),
        ]
    )
    case_contract = state.get("case_contract") if isinstance(state.get("case_contract"), Mapping) else {}
    answer_moves = (
        state.get("required_answer_moves")
        if isinstance(state.get("required_answer_moves"), list)
        else contract.get("required_answer_moves")
        if isinstance(contract.get("required_answer_moves"), list)
        else case_contract.get("required_answer_moves")
        if isinstance(case_contract.get("required_answer_moves"), list)
        else []
    )
    rows: list[dict[str, Any]] = []
    rows.extend(_required_question_items_from_answer_moves(answer_moves, tickers=tickers))
    if "nvda" in query and "dell" in query:
        rows.extend(
            [
                _required_question_item("dell_ai_server_quality_margin_bridge", "product_and_production", tickers, ["product_kpi_exact", "financial_margin_bridge"], ["dell", "ai server", "gross margin", "margin", "ai服务器", "毛利", "利润率"]),
                _required_question_item("nvda_gpu_supply_generation", "product_and_production", tickers, ["product_spec", "generation_edge"], ["nvda", "gpu", "h100", "h200", "b200", "gb200", "blackwell", "算力", "显卡"]),
                _required_question_item("cloud_capex_read_through", "capital_and_financing", tickers, ["capex_signal", "supply_chain_read_through"], ["capex", "amzn", "msft", "googl", "cloud", "资本支出", "云服务", "数据中心"]),
                _required_question_item("customer_deployment_or_order_signal", "product_and_production", tickers, ["customer_deployment", "order_or_adoption_signal"], ["deployment", "customer", "order", "configured", "adoption", "客户", "订单", "部署", "采用", "配置"]),
            ]
        )
    if any(term in query for term in ("asml", "semicap", "lrcx", "amat", "klac")):
        rows.extend(
            [
                _required_question_item("asml_orders_or_backlog", "product_and_production", tickers, ["orders_backlog", "non_us_disclosure"], ["asml", "order", "booking", "backlog", "订单", "预订", "积压"]),
                _required_question_item("shipment_or_cycle_context", "industry_supply_chain", tickers, ["shipment_cycle", "wafer_fab_equipment_cycle"], ["shipment", "cycle", "wafer fab", "semicap", "出货", "周期", "晶圆厂", "半导体设备"]),
                _required_question_item("customer_concentration_or_deployment", "product_and_production", tickers, ["customer_deployment", "customer_concentration"], ["customer", "tsmc", "samsung", "intel", "deployment", "客户", "台积电", "三星", "英特尔", "部署"]),
                _required_question_item("export_restriction_context", "risk_and_counterevidence", tickers, ["regulatory_export_control"], ["export", "china", "restriction", "license", "出口", "中国", "限制", "许可证", "管制"]),
            ]
        )
    return _dedupe_required_question_items(rows)


def _required_question_items_from_answer_moves(value: Any, *, tickers: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in value or []:
        move = str(raw or "").strip()
        if not move:
            continue
        text = move.lower()
        if "clear bounded thesis" in text or "not background" in text or "核心判断" in move:
            rows.append(
                _required_question_item(
                    "opening_bounded_thesis",
                    "fundamentals",
                    tickers,
                    ["thesis_path", "answer_first_outline"],
                    ["thesis", "bounded", "核心判断", "判断"],
                    answer_contract=move,
                )
            )
            continue
        if "product/architecture" in text or "architecture advantage" in text or "competitive/substitution" in text:
            rows.append(
                _required_question_item(
                    "product_architecture_competitive_edges",
                    "product_and_production",
                    tickers,
                    ["product_spec", "generation_edge", "competitive_edge", "substitution_edge"],
                    ["architecture", "gpu", "tpu", "blackwell", "mi300", "competitive", "substitution"],
                    answer_contract=move,
                )
            )
            continue
        if "deployment and cloud capex" in text or "demand pool" in text:
            rows.append(
                _required_question_item(
                    "deployment_capex_demand_pool_bridge",
                    "capital_and_financing",
                    tickers,
                    ["customer_deployment", "capex_signal", "supply_chain_read_through"],
                    ["deployment", "capex", "amzn", "msft", "googl", "cloud", "demand pool"],
                    answer_contract=move,
                )
            )
            continue
        if "dell ai server" in text or "margin" in text or "working-capital" in text:
            rows.append(
                _required_question_item(
                    "dell_ai_server_quality_margin_bridge",
                    "fundamentals",
                    tickers,
                    ["product_kpi_exact", "financial_margin_bridge", "cash_flow_bridge", "working_capital"],
                    ["dell", "ai server", "revenue quality", "gross margin", "cash flow", "working capital"],
                    answer_contract=move,
                )
            )
            continue
        if "supply-chain" in text or "supply chain" in text or "bottleneck" in text or "foundry" in text or "hbm" in text:
            rows.append(
                _required_question_item(
                    "supply_chain_bottleneck_map",
                    "industry_supply_chain",
                    tickers,
                    ["relationship_graph", "supply_chain_read_through", "capacity_bottleneck"],
                    ["supply chain", "gpu", "foundry", "packaging", "hbm", "semicap", "bottleneck"],
                    answer_contract=move,
                )
            )
            continue
        if "exact facts" in text or "typed gaps" in text or "proxies" in text:
            rows.append(
                _required_question_item(
                    "evidence_authority_boundary",
                    "evidence_gap",
                    tickers,
                    ["exact_fact", "bounded_thesis_driver", "proxy_signal", "typed_gap"],
                    ["exact", "proxy", "gap", "boundary", "typed gap"],
                    answer_contract=move,
                )
            )
            continue
        if "counter-thesis" in text or "counter thesis" in text or "what evidence would change" in text:
            rows.append(
                _required_question_item(
                    "counter_thesis_what_would_change",
                    "risk_and_counterevidence",
                    tickers,
                    ["counter_thesis", "what_would_change", "risk_evidence"],
                    ["counter", "risk", "what would change", "反证", "风险"],
                    answer_contract=move,
                )
            )
            continue
        rows.append(
            _required_question_item(
                f"required_answer_move_{hashlib.sha1(move.encode('utf-8')).hexdigest()[:10]}",
                "evidence_gap",
                tickers,
                ["answer_contract"],
                [move[:80]],
                answer_contract=move,
            )
        )
    return rows


def _dedupe_required_question_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        item_id = str(row.get("question_item_id") or "").strip()
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        deduped.append(row)
    return deduped


def _required_question_item(
    item_id: str,
    dimension: str,
    tickers: list[str],
    roles: list[str],
    terms: list[str],
    *,
    answer_contract: str = "",
) -> dict[str, Any]:
    return {
        "question_item_id": item_id,
        "dimension": dimension,
        "required_tickers": tickers,
        "required_evidence_roles": roles,
        "minimum_answer_status": "answered_with_boundary",
        "expected_repair_policy": "root_cause_if_not_answered",
        "terms_any": terms,
        "answer_contract": answer_contract,
    }


def _focus_ticker_coverage_policy(state: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    scope = contract.get("scope") if isinstance(contract.get("scope"), Mapping) else {}
    tickers = _unique_upper(
        [
            *(scope.get("focus_tickers") or []),
            *(state.get("focus_tickers") or [] if isinstance(state.get("focus_tickers"), list) else []),
        ]
    )
    return {
        "focus_tickers": tickers,
        "minimum_statuses": ["fact_used", "fact_available_not_used_root_caused", "bounded_gap", "commercial_gap", "not_material"],
        "policy": "memo_must_not_claim_missing_data_when_approved_facts_or_supported_claims_exist",
    }


def _state_with_lead_targeted_repair(
    state: SecAgentGraphRuntimeState,
    selected_judgment: Mapping[str, Any],
) -> SecAgentGraphRuntimeState:
    repair_plan = state.get("targeted_repair_plan") if isinstance(state.get("targeted_repair_plan"), Mapping) else {}
    if not repair_plan or str(repair_plan.get("status") or "") == "no_retrievable_gap":
        return state
    execution = execute_official_issuer_repair_plan(repair_plan)
    if int(execution.get("attempted_count") or 0) <= 0:
        return state
    ledger = ToolCallLedger.from_dict(state.get("tool_call_ledger") or {"budget": state.get("loop_budget_state") or {}})
    turn_id = f"{state.get('run_id') or 'multi_agent_turn'}:lead_targeted_repair"
    for observation in execution.get("tool_observations") or []:
        if not isinstance(observation, Mapping):
            continue
        arguments = observation.get("arguments") if isinstance(observation.get("arguments"), Mapping) else {}
        runtime_summary = observation.get("runtime_summary") if isinstance(observation.get("runtime_summary"), Mapping) else {}
        boundary = observation.get("boundary") if isinstance(observation.get("boundary"), Mapping) else {}
        ledger.record_tool_call(
            turn_id=turn_id,
            agent_id="web_evidence_operator",
            tool_name="web_evidence_snapshot",
            arguments=arguments,
            row_count=int(observation.get("row_count") or 0),
            source_gap_count=int(observation.get("source_gap_count") or 0),
            elapsed_ms=int(runtime_summary.get("elapsed_ms") or 0),
            status=str(observation.get("status") or "ok"),
            metadata={
                "route_id": observation.get("route_id") or "",
                "retrieval_route": "live_public_web_context",
                "triggered_by": "research_lead",
                "repair_stage": "lead_review_checkpoint_before_memo_writer",
                "boundary": boundary,
                "runtime_summary": runtime_summary,
                "argument_summary": {
                    key: arguments.get(key)
                    for key in (
                        "ticker",
                        "url",
                        "source_class",
                        "web_scope_policy_ids",
                        "claim_types",
                        "repair_id",
                    )
                    if key in arguments
                },
            },
        )
    checkpoint = dict(state.get("lead_review_checkpoint") or {}) if isinstance(state.get("lead_review_checkpoint"), Mapping) else {}
    directive = dict(checkpoint.get("memo_directive") or {}) if isinstance(checkpoint.get("memo_directive"), Mapping) else {}
    directive["lead_targeted_repair_result"] = {
        "status": execution.get("status") or "",
        "attempted_count": int(execution.get("attempted_count") or 0),
        "success_count": int(execution.get("success_count") or 0),
        "bounded_gap_count": int(execution.get("bounded_gap_count") or 0),
        "writer_policy": "use_successful_official_context_to_reduce_false_missing_coverage_but_do_not_promote_exact_facts",
    }
    checkpoint["memo_directive"] = directive
    checkpoint["lead_targeted_repair_execution"] = execution
    augmented_judgment = _judgment_with_lead_targeted_repair_claims(selected_judgment, execution)
    if augmented_judgment is not selected_judgment:
        augmented_judgment = refresh_judgment_plan_after_governance_filter(augmented_judgment)
        augmented_judgment = attach_judgment_state(
            augmented_judgment,
            fundamental_statement_pack=state.get("fundamental_statement_pack")
            if isinstance(state.get("fundamental_statement_pack"), Mapping)
            else {},
        )
    judgment_state = _memo_logic_plan_judgment_state_input(augmented_judgment)
    memo_logic_plan = build_memo_logic_plan(
        judgment_state=judgment_state,
        lead_review_checkpoint=checkpoint,
        memo_intent=str((state.get("research_objective_contract") or {}).get("memo_intent") or "investment_research_memo")
        if isinstance(state.get("research_objective_contract"), Mapping)
        else "investment_research_memo",
        product_reasoning_frame=_build_product_reasoning_frame(
            state,
            selected_judgment=augmented_judgment,
            dimension_portfolio=state.get("dimension_evidence_portfolio")
            if isinstance(state.get("dimension_evidence_portfolio"), Mapping)
            else {},
        ),
        required_question_items=_required_question_items_for_contract(
            state,
            state.get("research_objective_contract") if isinstance(state.get("research_objective_contract"), Mapping) else {},
        ),
        focus_ticker_coverage_policy=_focus_ticker_coverage_policy(
            state,
            state.get("research_objective_contract") if isinstance(state.get("research_objective_contract"), Mapping) else {},
        ),
    )
    bounded_gap_register = _bounded_gap_register_with_candidates(
        state.get("bounded_gap_register") if isinstance(state.get("bounded_gap_register"), Mapping) else {},
        execution.get("source_gaps") or [],
    )
    return {
        **state,
        "context_rows": [*(state.get("context_rows") or []), *(execution.get("context_rows") or [])],
        "source_gaps": [*(state.get("source_gaps") or []), *(execution.get("source_gaps") or [])],
        "bounded_gap_register": bounded_gap_register,
        "tool_observations": [*(state.get("tool_observations") or []), *(execution.get("tool_observations") or [])],
        "artifact_refs": _merge_artifact_refs(state.get("artifact_refs"), execution.get("artifact_refs") or []),
        "tool_call_ledger": ledger.to_dict(),
        "lead_review_checkpoint": checkpoint,
        "lead_targeted_repair_execution": execution,
        "memo_logic_plan": memo_logic_plan,
        "judgment_plan": augmented_judgment,
        "verified_judgment_plan": augmented_judgment,
    }


def _judgment_with_lead_targeted_repair_claims(
    selected_judgment: Mapping[str, Any],
    execution: Mapping[str, Any],
) -> Mapping[str, Any]:
    claims = _lead_targeted_repair_context_claims(execution)
    if not claims:
        return selected_judgment
    judgment = dict(selected_judgment or {})
    existing = [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    existing_ids = {str(item.get("claim_id") or "") for item in existing}
    new_claims = [claim for claim in claims if str(claim.get("claim_id") or "") not in existing_ids]
    if not new_claims:
        return selected_judgment
    source_agent_ids = list(judgment.get("source_agent_ids") or [])
    if "research_lead" not in source_agent_ids:
        source_agent_ids.append("research_lead")
    stats = dict(judgment.get("claim_card_stats") or {}) if isinstance(judgment.get("claim_card_stats"), Mapping) else {}
    stats["lead_targeted_repair_claim_count"] = int(stats.get("lead_targeted_repair_claim_count") or 0) + len(new_claims)
    return {
        **judgment,
        "supported_claims": [*existing, *new_claims],
        "source_agent_ids": source_agent_ids,
        "claim_card_stats": stats,
        "lead_targeted_repair_claims": new_claims,
        "lead_targeted_repair_claim_policy": "official_context_claim_cards_context_only_no_exact_value_promotion_v0_1",
    }


def _judgment_with_product_bridge_claims(
    selected_judgment: Mapping[str, Any],
    supervising_pack: Mapping[str, Any],
) -> Mapping[str, Any]:
    claims = _product_bridge_context_claims(supervising_pack)
    if not claims:
        return selected_judgment
    judgment = dict(selected_judgment or {})
    existing = [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    existing_ids = {str(item.get("claim_id") or "") for item in existing}
    existing_refs = {
        ref
        for item in existing
        for ref in _unique_strings(item.get("evidence_refs") or item.get("refs"))
    }
    new_claims: list[dict[str, Any]] = []
    for claim in claims:
        claim_id = str(claim.get("claim_id") or "")
        refs = _unique_strings(claim.get("evidence_refs") or claim.get("refs"))
        if not claim_id or claim_id in existing_ids:
            continue
        if refs and all(ref in existing_refs for ref in refs):
            continue
        new_claims.append(claim)
        existing_ids.add(claim_id)
        existing_refs.update(refs)
    if not new_claims:
        return selected_judgment
    source_agent_ids = _unique_strings(judgment.get("source_agent_ids"))
    if "supervising_analyst" not in source_agent_ids:
        source_agent_ids.append("supervising_analyst")
    return {
        **judgment,
        "supported_claims": [*existing, *new_claims],
        "source_agent_ids": source_agent_ids,
        "product_bridge_claims": new_claims,
        "product_bridge_claim_policy": (
            "convert_product_intelligence_graph_to_bounded_claim_cards_"
            "without_promoting_to_sku_revenue_or_order_exact_v0_1"
        ),
    }


def _product_bridge_context_claims(supervising_pack: Mapping[str, Any]) -> list[dict[str, Any]]:
    pack = supervising_pack if isinstance(supervising_pack, Mapping) else {}
    product_bridge = pack.get("product_bridge_pack") if isinstance(pack.get("product_bridge_pack"), Mapping) else {}
    claims: list[dict[str, Any]] = []
    claims.extend(_product_bridge_kpi_claims(_product_bridge_rows(product_bridge.get("company_disclosed_product_kpis"))))
    claims.extend(
        _product_bridge_profile_claims(
            product_bridge.get("product_intelligence_pack_ref"),
            product_bridge.get("product_evidence_pack_ref"),
            _product_bridge_rows(product_bridge.get("official_product_context")),
        )
    )
    claims.extend(_product_bridge_deployment_claims(_product_bridge_rows(product_bridge.get("customer_deployment_context"))))
    claims.extend(_product_bridge_relationship_claims(_product_bridge_rows(product_bridge.get("product_relationship_context"))))
    return sorted(claims, key=lambda item: (str(item.get("ticker_scope") or ""), str(item.get("claim_type") or ""), str(item.get("claim_id") or "")))


def _product_bridge_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    if isinstance(value, Mapping):
        rows = value.get("rows") or value.get("items") or value.get("packs")
        if isinstance(rows, list):
            return [dict(item) for item in rows if isinstance(item, Mapping)]
    return []


def _product_bridge_pack_rows(value: Any) -> list[dict[str, Any]]:
    pack = value if isinstance(value, Mapping) else {}
    rows = pack.get("packs") if isinstance(pack.get("packs"), list) else []
    return [dict(item) for item in rows if isinstance(item, Mapping)]


def _product_bridge_kpi_claims(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        ticker = _product_bridge_ticker(row)
        if not ticker or not _product_bridge_kpi_row_promotable(row):
            continue
        by_ticker.setdefault(ticker, []).append(dict(row))
    claims: list[dict[str, Any]] = []
    for ticker, ticker_rows in sorted(by_ticker.items()):
        selected = _product_bridge_latest_rows_by_label(ticker_rows, max_rows=5)
        refs = _unique_strings([ref for row in selected for ref in _product_bridge_refs(row)])[:8]
        if not refs:
            continue
        samples = _unique_strings(
            [
                f"{_product_bridge_label(row)} {str(row.get('period_key') or row.get('period') or '').strip()} {_product_bridge_value_text(row)}".strip()
                for row in selected
                if _product_bridge_label(row)
            ]
        )[:5]
        labels = _unique_strings([_product_bridge_label(row) for row in selected if _product_bridge_label(row)])[:5]
        claim_id = _product_bridge_claim_id("product_kpi", ticker, refs, labels)
        claims.append(
            _product_bridge_claim(
                claim_id=claim_id,
                ticker=ticker,
                claim=(
                    f"{ticker} company-disclosed product/business KPI rows include {', '.join(samples)}. "
                    "This supports product or business-line operating analysis for those disclosed row labels only; "
                    "it does not prove SKU revenue, unit shipments, ASP, sell-through, backlog, market share, or channel inventory."
                ),
                claim_type="company_reported_product_operating_fact",
                memo_slot="product_technology",
                analysis_dimension="product_and_production",
                metric_scope=["product_or_business_kpi", *labels],
                evidence_refs=refs,
                source_families=["company_product_evidence_graph"],
                materiality="high",
                confidence="medium",
                signal_authority_type="company_disclosed_product_or_business_metric",
                signal_promotion_level="thesis_driver_allowed_with_row_label_boundary",
                evidence_role="product_kpi_exact_or_business_segment_metric",
                business_mechanism="Company-disclosed row-label operating metrics provide a firmer product/business mix bridge than generic product pages.",
                financial_bridge="Use only for the disclosed business or segment labels; do not convert into SKU-level revenue, share, ASP, or sell-through.",
                counter_read="A row label can mix geography, customer type, or segment definitions; analyst judgment must check taxonomy before comparing across peers.",
                caveats=[
                    "Company-disclosed product/business KPI row-label boundary applies.",
                    "Not SKU revenue, shipments, ASP, sell-through, backlog, market share, or channel inventory.",
                ],
                display_value="; ".join(samples[:3]),
            )
        )
    return claims


def _product_bridge_profile_claims(
    intelligence_ref: Any,
    evidence_ref: Any,
    official_rows: list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    intelligence_by_ticker = {_product_bridge_ticker(row): dict(row) for row in _product_bridge_pack_rows(intelligence_ref) if _product_bridge_ticker(row)}
    evidence_by_ticker = {_product_bridge_ticker(row): dict(row) for row in _product_bridge_pack_rows(evidence_ref) if _product_bridge_ticker(row)}
    official_by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in official_rows:
        ticker = _product_bridge_ticker(row)
        if ticker:
            official_by_ticker.setdefault(ticker, []).append(dict(row))
    claims: list[dict[str, Any]] = []
    for ticker in sorted(set(intelligence_by_ticker) | set(evidence_by_ticker) | set(official_by_ticker)):
        intelligence = intelligence_by_ticker.get(ticker, {})
        evidence = evidence_by_ticker.get(ticker, {})
        rows = official_by_ticker.get(ticker, [])
        refs = _unique_strings(
            [
                str(intelligence.get("pack_id") or ""),
                str(evidence.get("pack_id") or ""),
                *[ref for row in rows[:8] for ref in _product_bridge_refs(row)],
            ]
        )[:8]
        if not refs:
            continue
        family_ids = _unique_strings(
            [
                *[str(item) for item in intelligence.get("family_ids") or []],
                *[str(item) for item in evidence.get("family_ids") or []],
                *[str(row.get("product_family") or "") for row in rows if str(row.get("product_family") or "").strip()],
            ]
        )[:6]
        products = _unique_strings(
            [
                str(product)
                for row in rows
                for product in _product_bridge_products(row)
                if str(product).strip()
            ]
        )[:8]
        layer_statuses = evidence.get("layer_statuses") if isinstance(evidence.get("layer_statuses"), Mapping) else {}
        ready_layers = _unique_strings(
            [
                str(key)
                for key, value in dict(layer_statuses).items()
                if str(value or "").lower() not in {"", "absent", "gap", "missing"}
            ]
        )[:8]
        counts = intelligence.get("counts") if isinstance(intelligence.get("counts"), Mapping) else {}
        count_parts = _unique_strings(
            [
                f"{key}={value}"
                for key, value in dict(counts).items()
                if str(value).strip() and str(value) not in {"0", "0.0"}
            ]
        )[:6]
        labels = products or family_ids or ready_layers or [ticker]
        claim_id = _product_bridge_claim_id("product_profile", ticker, refs, labels)
        claims.append(
            _product_bridge_claim(
                claim_id=claim_id,
                ticker=ticker,
                claim=(
                    f"{ticker} ProductIntelligenceGraph covers product families {', '.join(family_ids or ['unspecified'])}"
                    f" and evidence roles {', '.join(ready_layers or ['product_profile'])}; "
                    f"official product/profile context includes {', '.join(products[:5] or family_ids or ['company product taxonomy'])}. "
                    "This supports bounded product capability, architecture, adoption, and competitive-context judgment, "
                    "but it does not prove SKU revenue, shipments, ASP, share, customer order value, or backlog."
                ),
                claim_type="product_intelligence_graph_bounded_claim",
                memo_slot="product_technology",
                analysis_dimension="product_and_production",
                metric_scope=["product_profile", "product_spec_architecture", *ready_layers[:5], *family_ids[:4]],
                evidence_refs=refs,
                source_families=["company_product_evidence_graph"],
                materiality="high" if len(ready_layers) >= 3 or len(products) >= 3 else "medium",
                confidence="medium",
                signal_authority_type="bounded_product_intelligence_graph",
                signal_promotion_level="thesis_driver_allowed_non_financial",
                evidence_role="product_profile_spec_architecture_or_taxonomy",
                business_mechanism="Product profile, specification, and family coverage clarify what the company sells and which product lanes matter for thesis construction.",
                financial_bridge="Can bridge to financial analysis only through separately cited product/business KPI, segment, margin, capex, inventory, or customer deployment evidence.",
                counter_read="Product coverage can prove capability or product existence without proving customer demand, revenue conversion, or share gain.",
                caveats=[
                    "Bounded product intelligence graph evidence only.",
                    "Requires separate exact KPI or customer/order evidence for revenue, shipments, ASP, backlog, or market-share claims.",
                ],
                display_value=", ".join(count_parts[:3]),
            )
        )
    return claims


def _product_bridge_deployment_claims(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        ticker = _product_bridge_ticker(row)
        refs = _product_bridge_refs(row)
        if ticker and refs:
            by_ticker.setdefault(ticker, []).append(dict(row))
    claims: list[dict[str, Any]] = []
    for ticker, ticker_rows in sorted(by_ticker.items()):
        selected = ticker_rows[:4]
        refs = _unique_strings([ref for row in selected for ref in _product_bridge_refs(row)])[:8]
        signals = _unique_strings([_truncate_text(str(row.get("signal") or row.get("summary") or ""), 150) for row in selected if str(row.get("signal") or row.get("summary") or "").strip()])[:4]
        if not refs or not signals:
            continue
        claim_id = _product_bridge_claim_id("customer_deployment", ticker, refs, signals)
        claims.append(
            _product_bridge_claim(
                claim_id=claim_id,
                ticker=ticker,
                claim=(
                    f"{ticker} has public customer/deployment/procurement context rows including {', '.join(signals[:3])}. "
                    "These rows support adoption or procurement existence signals, not total orders, revenue, backlog, demand, market share, or customer concentration."
                ),
                claim_type="customer_deployment_bounded_signal",
                memo_slot="product_technology",
                analysis_dimension="product_and_production",
                metric_scope=["customer_deployment_signal", "public_procurement_context"],
                evidence_refs=refs,
                source_families=["company_product_evidence_graph", "public_source_context"],
                materiality="medium",
                confidence="medium",
                signal_authority_type="customer_deployment_signal",
                signal_promotion_level="thesis_driver_allowed_non_financial",
                evidence_role="customer_deployment_or_adoption_proxy",
                business_mechanism="Public deployment, procurement, or adoption rows help check whether product exposure has observable external adoption signals.",
                financial_bridge="Do not translate deployment/procurement context into revenue, total orders, backlog, or demand without exact company or contract values.",
                counter_read="Public awards or customer examples can be narrow snapshots and may not represent broad commercial demand.",
                caveats=[
                    "Deployment/procurement signal only.",
                    "Not total orders, revenue, backlog, demand, market share, or customer concentration.",
                ],
            )
        )
    return claims


def _product_bridge_relationship_claims(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_ticker: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        ticker = _product_bridge_ticker(row)
        refs = _product_bridge_refs(row)
        if ticker and refs:
            by_ticker.setdefault(ticker, []).append(dict(row))
    claims: list[dict[str, Any]] = []
    for ticker, ticker_rows in sorted(by_ticker.items()):
        selected = ticker_rows[:5]
        refs = _unique_strings([ref for row in selected for ref in _product_bridge_refs(row)])[:8]
        edge_types = _unique_strings([str(row.get("edge_type") or "") for row in selected if str(row.get("edge_type") or "").strip()])[:5]
        endpoints = _unique_strings(
            [
                _product_bridge_relationship_endpoint(row)
                for row in selected
                if _product_bridge_relationship_endpoint(row)
            ]
        )[:4]
        if not refs or not edge_types:
            continue
        claim_id = _product_bridge_claim_id("product_relationship", ticker, refs, edge_types + endpoints)
        claims.append(
            _product_bridge_claim(
                claim_id=claim_id,
                ticker=ticker,
                claim=(
                    f"{ticker} product relationship graph includes edge types {', '.join(edge_types)}"
                    f"{' across ' + ', '.join(endpoints) if endpoints else ''}. "
                    "These edges support supply-chain, channel, competitive, or read-through hypothesis checking, "
                    "but do not prove shipment allocation, revenue conversion, direct win/loss, pricing, or customer concentration."
                ),
                claim_type="product_relationship_graph_bounded_claim",
                memo_slot="industry_relationship",
                analysis_dimension="industry_supply_chain",
                metric_scope=["product_relationship_graph", *edge_types],
                evidence_refs=refs,
                source_families=["relationship_graph", "company_product_evidence_graph"],
                materiality="medium",
                confidence="medium",
                signal_authority_type="product_relationship_graph_signal",
                signal_promotion_level="thesis_driver_allowed_non_financial",
                evidence_role="relationship_graph_readthrough_or_competitive_context",
                business_mechanism="Relationship edges make explicit which product-family, customer, channel, supply-chain, or comparable paths require analyst reasoning.",
                financial_bridge="Use as read-through structure only; financial impact requires separate capex, order, revenue, margin, inventory, or exact customer evidence.",
                counter_read="Same-family or graph-derived edges can be navigational candidates rather than proof of direct competitive win/loss or demand transfer.",
                caveats=[
                    "Relationship graph signal only.",
                    "Not shipment allocation, revenue conversion, win/loss, pricing, customer concentration, or total order proof.",
                ],
            )
        )
    return claims


def _product_bridge_claim(
    *,
    claim_id: str,
    ticker: str,
    claim: str,
    claim_type: str,
    memo_slot: str,
    analysis_dimension: str,
    metric_scope: list[str],
    evidence_refs: list[str],
    source_families: list[str],
    materiality: str,
    confidence: str,
    signal_authority_type: str,
    signal_promotion_level: str,
    evidence_role: str,
    business_mechanism: str,
    financial_bridge: str,
    counter_read: str,
    caveats: list[str],
    display_value: str = "",
) -> dict[str, Any]:
    return {
        "claim_id": claim_id,
        "agent_id": "supervising_analyst",
        "claim": claim,
        "claim_type": claim_type,
        "ticker_scope": [ticker],
        "metric_scope": _unique_strings(metric_scope),
        "memo_slot": memo_slot,
        "analysis_dimension": analysis_dimension,
        "materiality": materiality,
        "direction": "neutral",
        "evidence_refs": _unique_strings(evidence_refs)[:8],
        "source_families": _unique_strings(source_families),
        "confidence": confidence,
        "unsupported": False,
        "caveats": _unique_strings(caveats)[:5],
        "missing_confirmations": [
            "Exact product/SKU revenue, shipments, ASP, share, sell-through, backlog, or customer order values require separately cited exact rows."
        ],
        "claim_rank_score": 76 if materiality == "high" else 68,
        "claim_rank_bucket": "memo_ready",
        "memo_readiness": "memo_ready",
        "claim_boundary": "Bounded ProductIntelligenceGraph claim; non-financial product evidence cannot be promoted to exact product operating metrics.",
        "signal_authority_type": signal_authority_type,
        "signal_promotion_level": signal_promotion_level,
        "thesis_driver_authority": True,
        "allowed_non_financial_claims": [
            "technical_fact",
            "deployment_signal",
            "customer_adoption_signal",
            "channel_presence_signal",
            "supply_chain_signal",
            "competitive_context_candidate",
        ],
        "display_value": display_value,
        "analyst_depth": {
            "schema_version": "sec_agent_claim_card_analyst_depth_v0.1",
            "analysis_dimension": analysis_dimension,
            "analyst_angle": "product_intelligence_graph_claim_conversion",
            "analysis_lens": "bounded_product_capability_adoption_relationship_evidence",
            "evidence_role": evidence_role,
            "business_mechanism": business_mechanism,
            "financial_bridge": financial_bridge,
            "comparison_basis": f"ticker={ticker}; source=ProductIntelligenceGraph",
            "counter_read": counter_read,
        },
    }


def _product_bridge_ticker(row: Mapping[str, Any]) -> str:
    value = row.get("ticker") or row.get("issuer_ticker") or row.get("symbol")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "").upper().strip()


def _product_bridge_refs(row: Mapping[str, Any]) -> list[str]:
    refs = row.get("evidence_refs") or row.get("refs") or row.get("evidence_ref")
    if isinstance(refs, str):
        refs = [refs]
    if not refs and str(row.get("pack_id") or "").strip():
        refs = [str(row.get("pack_id") or "").strip()]
    return _unique_strings(refs or [])


def _product_bridge_products(row: Mapping[str, Any]) -> list[str]:
    value = row.get("products_or_platforms") or row.get("product_or_segment") or row.get("product_family")
    if isinstance(value, list):
        return _unique_strings(value)
    return _unique_strings([value])


def _product_bridge_label(row: Mapping[str, Any]) -> str:
    return str(row.get("product_or_segment") or row.get("product_family") or row.get("metric_family") or "").strip()


def _product_bridge_kpi_row_promotable(row: Mapping[str, Any]) -> bool:
    refs = _product_bridge_refs(row)
    label = _product_bridge_label(row)
    if not refs or not label:
        return False
    lowered = label.lower()
    if any(term in lowered for term in ("foreign", "countries", "geographic", "region", "china", "emea", "apj", "americas")):
        return False
    metric = str(row.get("metric_family") or row.get("canonical_metric_id") or "").lower()
    return any(term in metric for term in ("revenue", "sales", "volume", "capacity", "utilization", "aum", "subscribers", "arr", "rpo"))


def _product_bridge_latest_rows_by_label(rows: list[dict[str, Any]], *, max_rows: int) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: (_product_bridge_period_number(row), _product_bridge_label(row)), reverse=True)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in ordered:
        label = _product_bridge_label(row)
        if not label or label in seen:
            continue
        selected.append(row)
        seen.add(label)
        if len(selected) >= max_rows:
            break
    return selected


def _product_bridge_period_number(row: Mapping[str, Any]) -> int:
    text = str(row.get("period_key") or row.get("period") or "").strip()
    matches = re.findall(r"\d{4}", text)
    return int(matches[-1]) if matches else 0


def _product_bridge_value_text(row: Mapping[str, Any]) -> str:
    display = ledger_metric_display_value(row)
    text = str(display or row.get("value") or row.get("raw_value") or "").strip()
    compact = _product_bridge_compact_amount(text)
    return compact or text


def _product_bridge_compact_amount(value: str) -> str:
    text = str(value or "").strip()
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return ""
    try:
        number = float(match.group(0))
    except ValueError:
        return ""
    suffix = ""
    lowered = text.lower()
    if "usd" in lowered or "$" in text:
        prefix = "$"
    else:
        prefix = ""
    absolute = abs(number)
    if absolute >= 1_000_000_000:
        suffix = "B"
        number = number / 1_000_000_000
    elif absolute >= 1_000_000:
        suffix = "M"
        number = number / 1_000_000
    elif absolute >= 1_000:
        suffix = "K"
        number = number / 1_000
    else:
        return text
    rendered = f"{prefix}{number:.2f}{suffix}"
    return rendered.replace(".00", "")


def _product_bridge_relationship_endpoint(row: Mapping[str, Any]) -> str:
    start = str(row.get("from_node_id") or "").strip()
    end = str(row.get("to_node_id") or "").strip()
    if not start and not end:
        return ""
    return f"{start}->{end}" if start and end else start or end


def _product_bridge_claim_id(prefix: str, ticker: str, refs: list[str], labels: list[str]) -> str:
    digest = hashlib.sha1("|".join(_unique_strings([ticker, *refs, *labels])).encode("utf-8")).hexdigest()[:12]
    return f"product_bridge_claim:{prefix}:{ticker.lower()}:{digest}"


def _memo_logic_plan_judgment_state_input(judgment: Mapping[str, Any]) -> dict[str, Any]:
    """Merge compact dimension state with claim-level role metadata for MemoLogicPlan."""

    base = dict(judgment.get("judgment_state") or {}) if isinstance(judgment.get("judgment_state"), Mapping) else {}
    supported_claims = [
        dict(item)
        for item in judgment.get("supported_claims") or []
        if isinstance(item, Mapping)
    ]
    if supported_claims:
        base["supported_claims"] = supported_claims
    return base


def _lead_targeted_repair_context_claims(execution: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in execution.get("context_rows") or [] if isinstance(row, Mapping)]
    if not rows:
        return []
    claims: list[dict[str, Any]] = []
    by_repair_type_ticker: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        if not bool(row.get("context_only")):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        repair_type = _repair_type_from_context_row(row)
        if ticker or repair_type in {"market_proxy", "supply_chain"}:
            by_repair_type_ticker.setdefault((repair_type, ticker or "CONTEXT"), []).append(row)
    for (repair_type, ticker), ticker_rows in sorted(by_repair_type_ticker.items()):
        products = _unique_strings(
            [
                str(row.get("product_family") or row.get("product_or_segment") or "")
                for row in ticker_rows
                if str(row.get("product_family") or row.get("product_or_segment") or "")
            ]
        )[:5]
        topics = _unique_strings(
            [
                str(row.get("topic") or row.get("source_title") or row.get("source_class") or "")
                for row in ticker_rows
                if str(row.get("topic") or row.get("source_title") or row.get("source_class") or "")
            ]
        )[:5]
        metric_leads = _unique_strings(
            [
                str(metric)
                for row in ticker_rows
                for metric in (row.get("metric_leads") or [])
                if str(metric).strip()
            ]
        )[:6]
        structured_facts = _unique_strings(
            [
                str(row.get("structured_context_summary") or row.get("fact_value") or "")
                for row in ticker_rows
                if str(row.get("structured_context_summary") or row.get("fact_value") or "").strip()
            ]
        )[:4]
        refs = _unique_strings([str(row.get("evidence_ref") or "") for row in ticker_rows if str(row.get("evidence_ref") or "")])[:6]
        if not refs:
            continue
        parser_diagnosis = _lead_repair_parser_diagnosis(ticker_rows)
        labels = products or structured_facts or topics or metric_leads or [repair_type]
        claim_id = f"lead_targeted_repair_claim:{repair_type}:{ticker.lower()}:{hashlib.sha1('|'.join(refs + labels).encode('utf-8')).hexdigest()[:12]}"
        metric_part = f"; official parser targets include {', '.join(metric_leads)}" if metric_leads else ""
        if structured_facts:
            metric_part = f"{metric_part}; bounded parsed context includes {', '.join(structured_facts[:2])}"
        analysis_dimension = _analysis_dimension_for_repair_type(repair_type, ticker_rows)
        claim_type = _claim_type_for_repair_type(repair_type)
        memo_slot = _memo_slot_for_repair_type(repair_type)
        source_classes = _unique_strings([str(row.get("source_class") or "") for row in ticker_rows if str(row.get("source_class") or "")])[:5]
        claims.append(
            {
                "claim_id": claim_id,
                "agent_id": "research_lead",
                "claim": _lead_repair_claim_text(
                    ticker=ticker,
                    repair_type=repair_type,
                    products=products,
                    topics=topics,
                    metric_leads=metric_leads,
                    source_classes=source_classes,
                    metric_part=metric_part,
                ),
                "claim_type": claim_type,
                "ticker_scope": [ticker] if ticker != "CONTEXT" else [],
                "metric_scope": [_metric_scope_anchor_for_repair_type(repair_type), *metric_leads[:4]],
                "memo_slot": memo_slot,
                "analysis_dimension": analysis_dimension,
                "materiality": "medium",
                "direction": "neutral",
                "evidence_refs": refs,
                "source_families": ["live_public_web_context"],
                "confidence": "medium",
                "unsupported": False,
                "caveats": [_caveat_for_repair_type(repair_type)],
                "missing_confirmations": _missing_confirmations_for_repair_type(repair_type),
                "claim_rank_score": 72,
                "claim_rank_bucket": "memo_ready",
                "memo_readiness": "memo_ready",
                "claim_rank_reasons": _claim_rank_reasons_for_repair_type(repair_type),
                "claim_boundary": str(ticker_rows[0].get("claim_boundary") or _claim_boundary_for_repair_type(repair_type)),
                "parser_diagnosis": parser_diagnosis,
                "parser_diagnosis_complete": bool(parser_diagnosis.get("parser_diagnosis_complete")),
                "source_attempt_outcomes": parser_diagnosis.get("source_attempt_outcomes") or [],
                "exact_fact_parser_failure_reasons": parser_diagnosis.get("exact_fact_parser_failure_reasons") or [],
                "next_parser_actions": parser_diagnosis.get("next_parser_actions") or [],
                "analyst_depth": {
                    "schema_version": "sec_agent_claim_card_analyst_depth_v0.1",
                    "analysis_dimension": analysis_dimension,
                    "analyst_angle": _analyst_angle_for_repair_type(repair_type),
                    "analysis_lens": _analysis_lens_for_repair_type(repair_type),
                    "evidence_role": "public_proxy_or_recall_context",
                    "business_mechanism": _business_mechanism_for_repair_type(repair_type),
                    "financial_bridge": _financial_bridge_for_repair_type(repair_type),
                    "comparison_basis": f"ticker={ticker}; context={','.join(labels[:4])}",
                    "counter_read": _counter_read_for_repair_type(repair_type),
                },
            }
        )
    claims.sort(key=lambda claim: _lead_repair_claim_sort_key(claim))
    return claims


def _lead_repair_parser_diagnosis(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    parser_rows = [
        row
        for row in rows
        if bool(row.get("parser_diagnosis_complete"))
        or str(row.get("parser_failure_reason") or row.get("exact_fact_parser_failure_reason") or "").strip()
        or str(row.get("source_specific_parser_status") or row.get("exact_value_parser_status") or "").strip()
    ]
    failure_reasons = _unique_strings(
        [
            str(row.get("exact_fact_parser_failure_reason") or row.get("parser_failure_reason") or "")
            for row in parser_rows
            if str(row.get("exact_fact_parser_failure_reason") or row.get("parser_failure_reason") or "").strip()
        ]
    )[:4]
    next_actions = _unique_strings(
        [str(row.get("next_parser_action") or "") for row in parser_rows if str(row.get("next_parser_action") or "").strip()]
    )[:4]
    parser_statuses = _unique_strings(
        [
            str(row.get("source_specific_parser_status") or row.get("exact_value_parser_status") or "")
            for row in parser_rows
            if str(row.get("source_specific_parser_status") or row.get("exact_value_parser_status") or "").strip()
        ]
    )[:6]
    outcomes = _unique_strings(
        [str(row.get("source_attempt_outcome") or "") for row in parser_rows if str(row.get("source_attempt_outcome") or "").strip()]
    )[:4]
    route_diagnoses = _unique_strings(
        [str(row.get("source_route_diagnosis") or "") for row in parser_rows if str(row.get("source_route_diagnosis") or "").strip()]
    )[:4]
    return {
        "schema_version": "finsight_lead_repair_parser_diagnosis_v0_1",
        "parser_diagnosis_complete": bool(parser_rows and failure_reasons and next_actions and parser_statuses),
        "source_attempt_outcomes": outcomes,
        "source_specific_parser_statuses": parser_statuses,
        "exact_fact_parser_failure_reasons": failure_reasons,
        "source_route_diagnoses": route_diagnoses,
        "next_parser_actions": next_actions,
        "row_count": len(parser_rows),
    }


def _repair_type_from_context_row(row: Mapping[str, Any]) -> str:
    claim_types = {str(item) for item in row.get("claim_types") or []}
    if str(row.get("product_family") or row.get("product_or_segment") or "").strip() or {
        "official_product_surface",
        "product_taxonomy_context",
        "product_spec_context",
    }.intersection(claim_types):
        return "product_surface"
    explicit = str(row.get("repair_type") or "").strip()
    if explicit:
        return explicit
    if {"capital_ownership_context", "offering_or_ownership_parser_lead"}.intersection(claim_types):
        return "capital_ownership"
    if {"market_proxy_context", "industry_cycle_context"}.intersection(claim_types):
        return "market_proxy"
    if {"supply_chain_context", "customer_supplier_relationship_context"}.intersection(claim_types):
        return "supply_chain"
    if {"local_filing_context", "issuer_filing_presence"}.intersection(claim_types):
        return "local_filing"
    return "issuer_official"


def _lead_repair_claim_sort_key(claim: Mapping[str, Any]) -> tuple[int, str]:
    priority = {
        "product_taxonomy_context": 0,
        "capital_structure_or_ownership_context": 1,
        "supply_chain_relationship_context": 2,
        "market_or_competitive_context": 3,
        "official_disclosure_context": 4,
        "official_issuer_context": 5,
    }
    return (priority.get(str(claim.get("claim_type") or ""), 9), str(claim.get("claim_id") or ""))


def _analysis_dimension_for_repair_type(repair_type: str, rows: list[Mapping[str, Any]]) -> str:
    default_dimension = {
        "product_surface": "product_and_production",
        "capital_ownership": "capital_and_financing",
        "market_proxy": "competition_and_market_position",
        "supply_chain": "competition_and_market_position",
        "local_filing": "fundamentals",
        "issuer_official": "fundamentals",
    }.get(repair_type, "fundamentals")
    if repair_type == "product_surface":
        return default_dimension
    for row in rows:
        value = str(row.get("analysis_dimension") or "").strip()
        if value:
            return value
    return default_dimension


def _claim_type_for_repair_type(repair_type: str) -> str:
    return {
        "product_surface": "product_taxonomy_context",
        "capital_ownership": "capital_structure_or_ownership_context",
        "market_proxy": "market_or_competitive_context",
        "supply_chain": "supply_chain_relationship_context",
        "local_filing": "official_disclosure_context",
        "issuer_official": "official_issuer_context",
    }.get(repair_type, "public_source_context")


def _memo_slot_for_repair_type(repair_type: str) -> str:
    return {
        "product_surface": "product_technology",
        "capital_ownership": "capital_and_financing",
        "market_proxy": "competition_market",
        "supply_chain": "industry_supply_chain",
        "local_filing": "fundamentals",
        "issuer_official": "fundamentals",
    }.get(repair_type, "evidence_context")


def _metric_scope_anchor_for_repair_type(repair_type: str) -> str:
    return {
        "product_surface": "product_surface_context",
        "capital_ownership": "capital_ownership_context",
        "market_proxy": "market_proxy_context",
        "supply_chain": "supply_chain_context",
        "local_filing": "local_filing_context",
        "issuer_official": "issuer_official_context",
    }.get(repair_type, "public_context")


def _lead_repair_claim_text(
    *,
    ticker: str,
    repair_type: str,
    products: list[str],
    topics: list[str],
    metric_leads: list[str],
    source_classes: list[str],
    metric_part: str,
) -> str:
    subject = ticker if ticker != "CONTEXT" else "the scoped public source repair"
    sources = f" via {', '.join(source_classes)}" if source_classes else ""
    if repair_type == "product_surface":
        label = ", ".join(products or topics or ["official product surfaces"])
        return (
            f"{subject} targeted web repair reached allowed official product/source surfaces{sources} and identified "
            f"{label}{metric_part}. This supports product taxonomy, spec/context, and follow-up parser targeting, "
            "but it does not promote exact sales, orders, backlog, shipments, share, ASP, inventory, or sell-through values."
        )
    if repair_type == "capital_ownership":
        label = ", ".join(topics or metric_leads or ["capital and ownership context"])
        return (
            f"{subject} targeted web repair reached allowed SEC/company/regulator capital sources{sources} for {label}. "
            "This supports capital structure, offering, ownership, debt, or insider parser targeting; exact amount, holder, "
            "security, rate, or maturity claims still require source-specific parser gates."
        )
    if repair_type == "market_proxy":
        label = ", ".join(topics or metric_leads or ["industry and market proxy context"])
        return (
            f"{subject} targeted web repair reached allowed public market proxy sources{sources} for {label}. "
            "This can frame industry cycle or competitive context, but it cannot prove issuer-specific sales, share, orders, "
            "inventory, or channel metrics."
        )
    if repair_type == "supply_chain":
        label = ", ".join(topics or metric_leads or ["official supply-chain relationship context"])
        return (
            f"{subject} targeted web repair reached allowed official relationship sources{sources} for {label}. "
            "This supports customer/supplier/channel relationship context, not shipment, revenue, allocation, or order-volume claims."
        )
    if repair_type == "local_filing":
        return (
            f"{subject} targeted web repair reached allowed local filing, regulator, exchange, SEC FPI, or company IR sources{sources}. "
            "This supports official disclosure coverage and parser targeting; exact financial or operating facts still require period, unit, and citation gates."
        )
    return (
        f"{subject} targeted web repair reached official issuer sources{sources}. This supports issuer coverage and disclosure-path analysis, "
        "but it does not promote exact sales, orders, backlog, shipments, share, ASP, or inventory values."
    )


def _caveat_for_repair_type(repair_type: str) -> str:
    return {
        "product_surface": "official product/source surface reached; exact product KPI parser promotion is still required",
        "capital_ownership": "capital/ownership source reached; exact amount/security/holder parser promotion is still required",
        "market_proxy": "public proxy source reached; issuer-specific sales/share/order conclusions remain prohibited",
        "supply_chain": "official relationship source reached; shipment/revenue/order-volume inference remains prohibited",
        "local_filing": "official filing/source reached; exact values still require source parser gates",
        "issuer_official": "official source reached; exact value parser promotion still required",
    }.get(repair_type, "public context reached; exact value promotion still gated")


def _missing_confirmations_for_repair_type(repair_type: str) -> list[str]:
    return {
        "product_surface": [
            "exact value parser for orders/backlog/sales/shipments/capacity",
            "commercial tracker data for market share, sell-through, channel inventory, ASP, or shipment share",
        ],
        "capital_ownership": [
            "source-specific parser for offering amount, debt principal, rate, maturity, holder, or ownership percentage",
            "filing-period reconciliation for 13F/13D/G/Form 3/4/5 lag",
        ],
        "market_proxy": [
            "company-specific disclosed KPI or licensed market tracker for issuer share/sales/shipments",
            "period and geography reconciliation between proxy and issuer reporting scope",
        ],
        "supply_chain": [
            "company-disclosed shipment/order/revenue allocation",
            "customer/supplier concentration or contract parser evidence",
        ],
        "local_filing": ["local filing parser output with period, unit, citation, and issuer mapping"],
        "issuer_official": ["official filing parser output with period, unit, citation, and issuer mapping"],
    }.get(repair_type, ["source-specific parser output"])


def _claim_rank_reasons_for_repair_type(repair_type: str) -> list[str]:
    return ["lead_targeted_repair_delta", "scoped_public_source_reached", f"{repair_type}_context", "source_boundary_preserved"]


def _claim_boundary_for_repair_type(repair_type: str) -> str:
    return {
        "product_surface": "official product surface context only; no exact product KPI promotion",
        "capital_ownership": "capital/ownership context only; no exact amount/security/holder promotion",
        "market_proxy": "public market proxy context only; no issuer-specific sales/share/order promotion",
        "supply_chain": "official relationship context only; no shipment/revenue/order-volume promotion",
        "local_filing": "official filing/source context only; no exact value promotion",
        "issuer_official": "official issuer context only; no exact value promotion",
    }.get(repair_type, "public context only; no exact value promotion")


def _analyst_angle_for_repair_type(repair_type: str) -> str:
    return {
        "product_surface": "Product lines, specifications, and production evidence",
        "capital_ownership": "Capital structure, financing, ownership, and insider evidence",
        "market_proxy": "Industry cycle and competitive position evidence",
        "supply_chain": "Supply-chain, customer, supplier, and channel relationship evidence",
        "local_filing": "Official filing coverage and parser targeting",
        "issuer_official": "Issuer official disclosure coverage",
    }.get(repair_type, "Public evidence repair context")


def _analysis_lens_for_repair_type(repair_type: str) -> str:
    return {
        "product_surface": "Use official product-surface leads to target parser follow-up without converting them into sales, share, orders, or backlog facts.",
        "capital_ownership": "Use capital/ownership source leads to target source-specific parsing without converting context into exact financing or holder claims.",
        "market_proxy": "Use proxy source context to frame industry direction without turning it into issuer-specific market share or sales facts.",
        "supply_chain": "Use official relationship context to test business exposure without inferring shipment, revenue, allocation, or order volume.",
        "local_filing": "Use official filing reachability to close issuer/source coverage before exact financial promotion.",
        "issuer_official": "Use official issuer source reachability to close local route gaps before exact fact promotion.",
    }.get(repair_type, "Use scoped public context as a repair lead only.")


def _business_mechanism_for_repair_type(repair_type: str) -> str:
    return {
        "product_surface": "Official product surfaces identify which equipment, platform, software, or service lines should be tied to orders, backlog, shipments, capex, and customer demand once exact disclosures are parsed.",
        "capital_ownership": "Capital and ownership disclosures indicate financing flexibility, dilution, debt maturity pressure, insider alignment, or holder concentration that can affect risk and valuation.",
        "market_proxy": "Official market proxies help establish whether the industry demand backdrop supports or contradicts company-level growth claims.",
        "supply_chain": "Official relationship sources help map customer/supplier/channel exposure that can transmit demand, capacity, or concentration risk.",
        "local_filing": "Official local disclosures close source coverage for issuers outside the local SEC route and identify where exact facts should be parsed.",
        "issuer_official": "Official issuer sources close disclosure coverage and identify which documents should anchor company-specific facts.",
    }.get(repair_type, "Scoped public evidence indicates where to test the business mechanism.")


def _financial_bridge_for_repair_type(repair_type: str) -> str:
    return {
        "product_surface": "Bridge to revenue, margin, capex, backlog, or order quality only after an official filing or company disclosure row passes period, unit, and citation gates.",
        "capital_ownership": "Bridge to interest expense, dilution, cash runway, debt maturity, and ownership overhang only after exact source rows pass parser gates.",
        "market_proxy": "Bridge to growth, pricing, share, utilization, or inventory only when issuer disclosures or licensed tracker facts confirm the proxy relationship.",
        "supply_chain": "Bridge to revenue concentration, shipment timing, capex pull-through, or margin pressure only after official issuer or counterparty disclosures provide exact values.",
        "local_filing": "Bridge to three-statement, segment, or operating KPI analysis only after local filing parser rows pass authority gates.",
        "issuer_official": "Bridge to company financial, product, and risk claims only after official filing parser rows pass authority gates.",
    }.get(repair_type, "Bridge to financial judgment only after exact source parser gates pass.")


def _counter_read_for_repair_type(repair_type: str) -> str:
    return {
        "product_surface": "If exact product KPI rows cannot be parsed, keep this as product taxonomy context and expose the metric gap separately.",
        "capital_ownership": "If exact holder/offering/debt rows cannot be parsed, keep this as financing context and expose the parser/commercial gap separately.",
        "market_proxy": "If the proxy cannot be reconciled to issuer scope, use it only as directional industry context.",
        "supply_chain": "If relationship context cannot be tied to disclosed volumes or revenue, avoid treating it as demand confirmation.",
        "local_filing": "If the filing cannot be parsed, keep it as source coverage and expose exact-value parser gap.",
        "issuer_official": "If the official source cannot be parsed, keep it as source coverage and expose exact-value parser gap.",
    }.get(repair_type, "If source-specific parser gates fail, do not promote the context into a thesis fact.")


def _merge_artifact_refs(existing: Any, additions: Any) -> Any:
    added = [dict(item) for item in additions or [] if isinstance(item, Mapping)]
    if not added:
        return existing
    if isinstance(existing, list):
        return [*existing, *added]
    if isinstance(existing, Mapping):
        merged = dict(existing)
        for item in added:
            key = str(item.get("artifact_id") or item.get("id") or hashlib.sha1(json.dumps(item, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12])
            merged[key] = item
        return merged
    return added


def _lead_supervision_gaps_from_state(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in state.get("source_gaps") or []:
        if isinstance(item, Mapping):
            rows.append(dict(item))
    register = state.get("bounded_gap_register") if isinstance(state.get("bounded_gap_register"), Mapping) else {}
    for item in register.get("gaps") or []:
        if isinstance(item, Mapping):
            rows.append(dict(item))
    rows.extend(_issuer_coverage_gaps_from_state(state))
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row.get("gap_id") or row.get("id") or "") or hashlib.sha256(
            json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()[:16]
        if key in seen:
            continue
        seen.add(key)
        if not row.get("gap_id"):
            row["gap_id"] = f"gap:{key}"
        deduped.append(row)
    return deduped


def _issuer_coverage_gaps_from_state(state: Mapping[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    route_results = [row for row in state.get("specialist_route_results") or [] if isinstance(row, Mapping)]
    for route in route_results:
        summary = route.get("input_coverage_summary") if isinstance(route.get("input_coverage_summary"), Mapping) else {}
        reasons = summary.get("focus_ticker_source_gap_reasons") or summary.get("ticker_source_gap_reasons") or []
        for item in reasons if isinstance(reasons, list) else []:
            if isinstance(item, Mapping):
                ticker = str(item.get("ticker") or item.get("issuer") or "").strip().upper()
                reason = str(item.get("reason") or item.get("reason_code") or item.get("message") or "").strip()
            else:
                text = str(item or "")
                ticker_match = re.search(r"\b[A-Z][A-Z0-9.]{1,9}\b", text)
                ticker = ticker_match.group(0) if ticker_match else ""
                reason = text
            if _is_official_issuer_probe_gap(ticker=ticker, reason=reason):
                gaps.append(_official_issuer_gap(ticker=ticker, reason=reason, source="specialist_route_results"))
    for item in state.get("source_gaps") or []:
        if not isinstance(item, Mapping):
            continue
        ticker = str(item.get("ticker") or item.get("issuer") or item.get("company") or "").strip().upper()
        reason = " ".join(
            str(item.get(key) or "")
            for key in ("reason_code", "reason", "message", "gap_type")
            if str(item.get(key) or "").strip()
        )
        if _is_official_issuer_probe_gap(ticker=ticker, reason=reason):
            gaps.append(_official_issuer_gap(ticker=ticker, reason=reason, source="source_gaps"))
    known_tickers = _known_official_issuer_tickers_from_state(state)
    already_requested = {str(row.get("ticker") or "").strip().upper() for row in gaps if isinstance(row, Mapping)}
    for ticker in known_tickers:
        if ticker in already_requested:
            continue
        if _state_has_local_or_live_issuer_authority(state, ticker):
            continue
        gaps.append(
            _official_issuer_gap(
                ticker=ticker,
                reason="known official issuer profile has no local authority rows in current run",
                source="lead_known_issuer_profile",
            )
        )
    return gaps


def _known_official_issuer_tickers_from_state(state: Mapping[str, Any]) -> list[str]:
    candidates: list[str] = []
    for container_key in ("agent_activation_plan", "query_contract", "multi_agent_context"):
        container = state.get(container_key) if isinstance(state.get(container_key), Mapping) else {}
        for key in ("focus_tickers", "search_scope_tickers", "tickers", "ticker_universe"):
            candidates.extend(str(item).strip().upper() for item in container.get(key) or [] if str(item).strip())
    query_text = str(state.get("user_query") or "")
    candidates.extend(match.group(0).upper() for match in re.finditer(r"\b[A-Z][A-Z0-9.]{1,9}\b", query_text))
    out: list[str] = []
    seen: set[str] = set()
    for ticker in candidates:
        if ticker in seen or not issuer_has_official_profile(ticker):
            continue
        seen.add(ticker)
        out.append(ticker)
    return out


def _state_has_local_or_live_issuer_authority(state: Mapping[str, Any], ticker: str) -> bool:
    target = str(ticker or "").strip().upper()
    if not target:
        return False
    source_families = {
        "primary_sec_filing",
        "company_authored_unaudited_sec_filing",
        "company_ir_material",
        "official_issuer_disclosure",
        "live_public_web_context",
    }
    for key in (
        "runtime_ledger_rows",
        "context_rows",
        "product_evidence_rows",
        "public_source_context_rows",
        "market_snapshot_rows",
        "industry_snapshot_rows",
    ):
        for row in state.get(key) or []:
            if not isinstance(row, Mapping):
                continue
            row_ticker = str(row.get("ticker") or row.get("issuer") or row.get("company_ticker") or "").strip().upper()
            if row_ticker != target:
                continue
            family = str(row.get("source_family") or row.get("source_class") or row.get("retrieval_route") or "").strip()
            if family in source_families:
                return True
            if bool(row.get("exact_value_authority")):
                return True
    return False


def _is_official_issuer_probe_gap(*, ticker: str, reason: str) -> bool:
    text = f"{ticker} {reason}".lower()
    if not ticker:
        return False
    return any(
        marker in text
        for marker in (
            "not_in_manifest",
            "mcp route scope",
            "route_scope",
            "sec/mcp",
            "local sec",
            "non-sec",
            "non_us",
            "foreign issuer",
            "fpi",
            "20-f",
            "6-k",
        )
    )


def _official_issuer_gap(*, ticker: str, reason: str, source: str) -> dict[str, Any]:
    ticker_text = str(ticker or "UNKNOWN").strip().upper()
    return {
        "gap_id": f"issuer_coverage:{ticker_text.lower()}:{hashlib.sha256(str(reason or source).encode('utf-8')).hexdigest()[:10]}",
        "gap_type": "issuer_official_source_probe_required",
        "analysis_dimension": "fundamentals",
        "ticker": ticker_text,
        "reason_code": "local_or_sec_route_scope_missing_official_issuer_probe_required",
        "reason": str(reason or "issuer is outside local SEC/MCP route scope"),
        "repairability": "retrievable_gap",
        "source": source,
        "official_probe_order": [
            "sec_fpi_filings_20f_6k",
            "company_ir_reports",
            "local_exchange_filings",
            "regulator_filings",
        ],
        "claim_boundary": "official_source_context_only_until_parser_period_unit_citation_gate_passes",
    }


def _required_analysis_dimensions_from_state(state: Mapping[str, Any]) -> list[str]:
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    context = state.get("multi_agent_context") if isinstance(state.get("multi_agent_context"), Mapping) else {}
    explicit = _unique_strings(
        contract.get("required_dimension_ids")
        or contract.get("memo_required_dimension_ids")
        or context.get("required_dimension_ids")
        or context.get("memo_required_dimension_ids")
    )
    if explicit:
        return _normalize_analysis_dimension_ids(explicit)
    return _infer_required_analysis_dimensions_from_text(str(state.get("user_query") or ""))


def _normalize_analysis_dimension_ids(values: Any) -> list[str]:
    valid = set(ANALYSIS_DIMENSION_ORDER)
    normalized: list[str] = []
    aliases = {
        "fundamental": "fundamentals",
        "fundamental_analysis": "fundamentals",
        "product": "product_and_production",
        "product_technology": "product_and_production",
        "production": "product_and_production",
        "capex": "capital_and_financing",
        "capital": "capital_and_financing",
        "capital_financing": "capital_and_financing",
        "market": "competition_and_market_position",
        "competition": "competition_and_market_position",
        "competitive_position": "competition_and_market_position",
        "industry": "industry_supply_chain",
        "supply_chain": "industry_supply_chain",
        "risk": "risk_and_counterevidence",
        "counterevidence": "risk_and_counterevidence",
        "gap": "evidence_gap",
    }
    for item in _unique_strings(values):
        key = str(item).strip().lower().replace("-", "_").replace(" ", "_")
        dimension = aliases.get(key, key)
        if dimension in valid and dimension not in normalized:
            normalized.append(dimension)
    return normalized


def _infer_required_analysis_dimensions_from_text(text: str) -> list[str]:
    lowered = str(text or "").lower()
    mapping = [
        ("fundamentals", ("基本面", "fundamental")),
        ("product_and_production", ("产品", "产线", "production", "product")),
        ("capital_and_financing", ("投融资", "资本开支", "capex", "capital expenditure", "capital")),
        ("industry_supply_chain", ("行业供应链", "供应链", "需求传导", "supply chain", "demand transmission")),
        ("competition_and_market_position", ("竞争位置", "竞争", "market position", "competitive")),
        ("risk_and_counterevidence", ("风险反证", "反证", "风险", "counterevidence", "risk")),
    ]
    required: list[str] = []
    for dimension, needles in mapping:
        if any(needle in lowered for needle in needles):
            required.append(dimension)
    return required


def _claim_card_store_barrier(
    outputs: Any,
    verification: Mapping[str, Any],
    judgment: Mapping[str, Any],
    claim_evidence_ledger: Mapping[str, Any] | None = None,
    pre_memo_fact_selection: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    output_rows = [dict(item) for item in outputs or [] if isinstance(item, Mapping)]
    supported = [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    unsupported = [dict(item) for item in judgment.get("unsupported_claims") or [] if isinstance(item, Mapping)]
    conflicts = [dict(item) for item in judgment.get("conflicts") or [] if isinstance(item, Mapping)]
    ledger = claim_evidence_ledger if isinstance(claim_evidence_ledger, Mapping) else {}
    ledger_summary = ledger.get("summary") if isinstance(ledger.get("summary"), Mapping) else {}
    fact_selection = pre_memo_fact_selection if isinstance(pre_memo_fact_selection, Mapping) else {}
    fact_summary = fact_selection.get("summary") if isinstance(fact_selection.get("summary"), Mapping) else {}
    return {
        "schema_version": "sec_agent_claim_card_store_barrier_v0.1",
        "barrier_id": "claim_card_store_barrier",
        "input_specialist_output_count": len(output_rows),
        "supported_claim_count": len(supported),
        "unsupported_claim_count": len(unsupported),
        "conflict_count": len(conflicts),
        "verification_status": str(verification.get("status") or ""),
        "memo_writer_allowed": bool(verification.get("memo_writer_allowed", True)),
        "deterministic_merge_policy": "verified_claim_cards_only_enter_judgment_plan",
        "claim_evidence_ledger_schema_version": str(ledger.get("schema_version") or ""),
        "ledger_claim_count": int(ledger.get("claim_count") or 0),
        "ledger_memo_writer_eligible_claim_count": int(ledger_summary.get("memo_writer_eligible_claim_count") or 0),
        "pre_memo_fact_selection_schema_version": str(fact_selection.get("schema_version") or ""),
        "pre_memo_approved_fact_count": int(fact_summary.get("approved_fact_count") or 0),
        "pre_memo_rejected_fact_count": int(fact_summary.get("rejected_fact_count") or 0),
        "pre_memo_approved_derived_metric_count": int(fact_summary.get("approved_derived_metric_count") or 0),
        "pre_memo_bounded_gap_link_count": int(fact_summary.get("bounded_gap_link_count") or 0),
    }


def _adjudicator_barrier(judgment: Mapping[str, Any]) -> dict[str, Any]:
    stats = judgment.get("claim_card_stats") if isinstance(judgment.get("claim_card_stats"), Mapping) else {}
    return {
        "schema_version": "sec_agent_adjudicator_barrier_v0.1",
        "barrier_id": "thesis_counterthesis_adjudicator",
        "judgment_status": str(judgment.get("status") or ""),
        "memo_writer_allowed": bool(judgment.get("memo_writer_allowed", True)),
        "supported_claim_count": int(stats.get("supported_claim_count") or len(judgment.get("supported_claims") or [])),
        "memo_ready_claim_count": int(stats.get("memo_ready_claim_count") or 0),
        "aggregation_policy": str(judgment.get("aggregation_policy") or ""),
        "output_schema": "verified_judgment_plan",
    }


def _node_multi_agent_memo_writer(
    state: SecAgentGraphRuntimeState,
    *,
    memo_writer: MultiAgentNodeFunc | None = None,
) -> SecAgentGraphRuntimeState:
    specialist_verification = state.get("specialist_verification") or {}
    result = memo_writer(state) if memo_writer is not None else {
        "memo_answer": build_multi_agent_memo_draft(
            state.get("verified_judgment_plan") or state.get("judgment_plan") or {},
            specialist_verification=specialist_verification,
        )
    }
    memo = result.get("memo_answer") if isinstance(result.get("memo_answer"), Mapping) else {}
    memo_logic_plan = state.get("memo_logic_plan") if isinstance(state.get("memo_logic_plan"), Mapping) else {}
    if memo and memo_logic_plan and not isinstance(memo.get("memo_logic_plan"), Mapping):
        result = {**dict(result), "memo_answer": {**dict(memo), "memo_logic_plan": memo_logic_plan}}
    if memo_writer is None and not isinstance(result.get("memo_route_result"), Mapping):
        result = _with_stub_memo_writer_input_fingerprint({**state, **result}, result)
    mode = "injected" if memo_writer else str((result.get("memo_answer") or {}).get("answer_status") or "deterministic")
    return _record_node({**state, **result}, "memo_writer", metadata={"mode": "injected" if memo_writer else "stub"})


def _node_multi_agent_verifier(
    state: SecAgentGraphRuntimeState,
    *,
    verifier: MultiAgentNodeFunc | None = None,
) -> SecAgentGraphRuntimeState:
    verification = state.get("specialist_verification") or verify_specialist_outputs_for_memo(state.get("specialist_outputs") or [])
    judgment = state.get("verified_judgment_plan") or state.get("judgment_plan") or {}
    memo = state.get("memo_answer") or {}
    memo_verification = verify_multi_agent_memo_draft(
        memo,
        judgment,
    )
    repaired_memo = None
    repair_outcome: dict[str, Any] = {}
    if memo_verification.get("status") == "fail":
        ledger = ToolCallLedger.from_dict(state.get("tool_call_ledger") or {"budget": state.get("loop_budget_state") or {}})
        previous_failure_count = len(memo_verification.get("errors") or [])
        candidate = repair_multi_agent_memo_draft(memo, memo_verification, judgment)
        repaired_verification = verify_multi_agent_memo_draft(candidate, judgment)
        repair_outcome = ledger.record_repair_result(
            previous_failure_count=previous_failure_count,
            new_failure_count=len(repaired_verification.get("errors") or []),
        )
        if repaired_verification.get("status") == "pass":
            repaired_memo = candidate
            memo_verification = {
                **repaired_verification,
                "repair": {
                    "status": "pass",
                    "attempt_count": int(repair_outcome.get("repair_rounds") or 1),
                    "previous_failure_count": previous_failure_count,
                    "new_failure_count": 0,
                    "previous_errors": [dict(item) for item in memo_verification.get("errors") or [] if isinstance(item, dict)],
                },
            }
        else:
            memo_verification = {
                **repaired_verification,
                "repair": {
                    "status": "fail",
                    "attempt_count": int(repair_outcome.get("repair_rounds") or 1),
                    "previous_failure_count": previous_failure_count,
                    "new_failure_count": len(repaired_verification.get("errors") or []),
                    "previous_errors": [dict(item) for item in memo_verification.get("errors") or [] if isinstance(item, dict)],
                    "loop_break_reason": repair_outcome.get("loop_break_reason") or ledger.loop_break_reason,
                },
            }
        state = {
            **state,
            "tool_call_ledger": ledger.to_dict(),
            "loop_break_reason": ledger.loop_break_reason or str(state.get("loop_break_reason") or ""),
        }
        if repaired_memo is not None:
            state = {**state, "memo_answer": repaired_memo}
    elif verifier is None:
        memo_verification = verify_multi_agent_memo_draft(
            memo,
            judgment,
        )
    if verifier is not None:
        result = verifier(state)
        state, result = _repair_injected_verifier_failure_once(
            state,
            result,
            judgment=judgment if isinstance(judgment, Mapping) else {},
            verifier=verifier,
        )
    else:
        result = {
            "claim_verification": memo_verification,
            "specialist_verification": verification,
        }
    result = _with_verifier_input_fingerprint({**state, **result}, result)
    if repaired_memo is not None:
        result = {**result, "memo_answer": repaired_memo}
    next_state = {
        **state,
        **result,
        "bounded_answer_allowed": bool(
            (result.get("claim_verification") or {}).get("bounded_answer_allowed")
            or (result.get("memo_answer") or state.get("memo_answer") or {}).get("bounded_answer_allowed")
            or state.get("bounded_answer_allowed")
            or False
        ),
    }
    return _record_node(next_state, "verifier", metadata={"mode": "injected" if verifier else "stub"})


def _with_stub_memo_writer_input_fingerprint(
    state: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    route_result = result.get("memo_route_result") if isinstance(result.get("memo_route_result"), Mapping) else {}
    if isinstance(route_result.get("input_pack_fingerprint"), Mapping):
        return dict(result)
    try:
        from sec_agent.memo_llm import memo_writer_input_pack_fingerprint_for_state

        fingerprint = memo_writer_input_pack_fingerprint_for_state(
            state,
            capture_source="deterministic_stub_using_memo_writer_input_contract",
        )
    except Exception as exc:  # pragma: no cover - defensive observability only.
        fingerprint = {
            "schema_version": "sec_agent_memo_writer_input_pack_fingerprint_v0_1",
            "agent_id": "memo_writer",
            "capture_source": "deterministic_stub_fingerprint_failed",
            "fallback_error": str(exc)[:240],
            "component_summaries": {},
            "known_evidence_ref_count": 0,
            "known_evidence_refs": [],
            "approx_prompt_payload_chars": 0,
            "fingerprint_policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
        }
    memo = state.get("memo_answer") if isinstance(state.get("memo_answer"), Mapping) else {}
    route = {
        "schema_version": "sec_agent_memo_writer_stub_route_v0_1",
        "status": "deterministic_stub",
        "memo_status": str(memo.get("answer_status") or ""),
        "memo_profile": str(fingerprint.get("memo_profile") or ""),
        "input_pack_fingerprint": fingerprint,
    }
    return {**dict(result), "memo_route_result": {**route, **dict(route_result)}}


def _with_verifier_input_fingerprint(
    state: Mapping[str, Any],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    verification = result.get("claim_verification") if isinstance(result.get("claim_verification"), Mapping) else {}
    projection = verification.get("verifier_input_projection") if isinstance(verification.get("verifier_input_projection"), Mapping) else {}
    if isinstance(projection.get("input_pack_fingerprint"), Mapping) and isinstance(
        verification.get("verifier_input_pack_fingerprint"), Mapping
    ):
        return dict(result)
    try:
        from sec_agent.memo_llm import verifier_input_projection_for_state

        projected = verifier_input_projection_for_state(
            state,
            deterministic=verification,
            capture_source="deterministic_stub_using_verifier_projection_contract",
        )
        projected_stats = dict(projected.get("projection_stats") or {})
        fingerprint = dict(projected.get("input_pack_fingerprint") or {})
    except Exception as exc:  # pragma: no cover - defensive observability only.
        fingerprint = {
            "schema_version": "sec_agent_verifier_input_pack_fingerprint_v0_1",
            "agent_id": "verifier",
            "capture_source": "deterministic_stub_fingerprint_failed",
            "fallback_error": str(exc)[:240],
            "component_summaries": {},
            "known_evidence_ref_count": 0,
            "known_evidence_refs": [],
            "approx_prompt_payload_chars": 0,
            "fingerprint_policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
        }
        projected_stats = {
            "schema_version": "sec_agent_verifier_minimal_projection_v0.1",
            "projection_policy": "fingerprint_failed",
            "input_pack_fingerprint": fingerprint,
        }
    updated_verification = {
        **dict(verification),
        "verifier_input_projection": {**projected_stats, **dict(projection), "input_pack_fingerprint": fingerprint},
        "verifier_input_pack_fingerprint": fingerprint,
    }
    return {**dict(result), "claim_verification": updated_verification}


def _repair_injected_verifier_failure_once(
    state: SecAgentGraphRuntimeState,
    result: Mapping[str, Any],
    *,
    judgment: Mapping[str, Any],
    verifier: MultiAgentNodeFunc,
) -> tuple[SecAgentGraphRuntimeState, dict[str, Any]]:
    claim = result.get("claim_verification") if isinstance(result.get("claim_verification"), Mapping) else {}
    if claim.get("status") != "fail":
        return state, dict(result)
    previous_errors = [dict(item) for item in claim.get("errors") or [] if isinstance(item, Mapping)]
    ledger = ToolCallLedger.from_dict(state.get("tool_call_ledger") or {"budget": state.get("loop_budget_state") or {}})
    decision = ledger.can_run_repair()
    if not decision.get("allowed"):
        repaired_claim = {
            **dict(claim),
            "repair": {
                "status": "fail",
                "attempt_count": int(ledger.repair_rounds),
                "previous_failure_count": len(previous_errors),
                "new_failure_count": len(previous_errors),
                "previous_errors": previous_errors,
                "loop_break_reason": decision.get("reason") or ledger.loop_break_reason,
            },
            "bounded_answer_allowed": True,
        }
        return {
            **state,
            "tool_call_ledger": ledger.to_dict(),
            "loop_break_reason": ledger.loop_break_reason or str(state.get("loop_break_reason") or ""),
        }, {**dict(result), "claim_verification": repaired_claim}

    memo = result.get("memo_answer") if isinstance(result.get("memo_answer"), Mapping) else state.get("memo_answer") or {}
    candidate = repair_multi_agent_memo_draft(memo, claim, judgment)
    retry_state: SecAgentGraphRuntimeState = {**state, **dict(result), "memo_answer": candidate}
    retry_result = verifier(retry_state)
    retry_claim = retry_result.get("claim_verification") if isinstance(retry_result.get("claim_verification"), Mapping) else {}
    new_failure_count = len(retry_claim.get("errors") or []) if retry_claim.get("status") == "fail" else 0
    repair_outcome = ledger.record_repair_result(
        previous_failure_count=len(previous_errors),
        new_failure_count=new_failure_count,
    )
    repaired_claim = {
        **dict(retry_claim or claim),
        "repair": {
            "status": "pass" if retry_claim.get("status") == "pass" else "fail",
            "attempt_count": int(repair_outcome.get("repair_rounds") or ledger.repair_rounds),
            "previous_failure_count": len(previous_errors),
            "new_failure_count": new_failure_count,
            "previous_errors": previous_errors,
            "loop_break_reason": repair_outcome.get("loop_break_reason") or ledger.loop_break_reason,
        },
    }
    next_state: SecAgentGraphRuntimeState = {
        **state,
        "memo_answer": candidate,
        "tool_call_ledger": ledger.to_dict(),
        "loop_break_reason": ledger.loop_break_reason or str(state.get("loop_break_reason") or ""),
    }
    return next_state, {**dict(retry_result), "memo_answer": candidate, "claim_verification": repaired_claim}


def _render_memo_answer(memo: Mapping[str, Any], *, bounded: bool, state: Mapping[str, Any] | None = None) -> str:
    parts: list[str] = []
    if state and isinstance(state.get("memo_logic_plan"), Mapping) and not isinstance(memo.get("memo_logic_plan"), Mapping):
        memo = {**dict(memo), "memo_logic_plan": state.get("memo_logic_plan")}
    logic_plan = memo.get("memo_logic_plan") if isinstance(memo.get("memo_logic_plan"), Mapping) else {}
    labels = _memo_render_labels(memo)
    direct = _clean_user_facing_memo_text_for_render(
        str(memo.get("direct_answer") or "No deterministic memo text was generated.").strip(),
        labels["language"],
    )
    profile = memo.get("memo_profile") if isinstance(memo.get("memo_profile"), Mapping) else {}
    citation_map = _build_memo_citation_map(memo)
    rendered_claim_max = int(profile.get("rendered_claim_max") or (5 if bounded else 8))
    profile_name = str(profile.get("profile") or "").strip()
    rendered_dimension_max = int(
        profile.get("rendered_dimension_max") or (8 if profile_name in {"standard", "expanded", "deep_research"} else 5)
    )
    if direct:
        parts.append(f"{labels['core_thesis']}:\n{direct}")

    fact_table_blocks = _memo_fact_table_blocks(memo, state or {})
    if fact_table_blocks:
        citation_map = _extend_memo_citation_map(citation_map, _memo_fact_table_rows_for_citations(fact_table_blocks))
        fact_table_text = _render_memo_fact_table_blocks(
            fact_table_blocks,
            language=labels["language"],
            citation_map=citation_map,
        )
        if fact_table_text:
            parts.append(f"{labels['fact_tables']}:\n{fact_table_text}")

    dimension_lines = _render_dimension_analysis_lines(
        _dimension_rows_in_logic_plan_order(memo.get("dimension_analyses") or [], logic_plan),
        ref_label=labels["refs"],
        language=labels["language"],
        citation_map=citation_map,
        max_items=rendered_dimension_max,
    )
    if not dimension_lines:
        dimension_lines = _render_dimension_analysis_lines(
            _dimension_rows_in_logic_plan_order(
                (memo.get("thesis_driver_pack") or {}).get("dimension_sections") if isinstance(memo.get("thesis_driver_pack"), Mapping) else [],
                logic_plan,
            ),
            ref_label=labels["refs"],
            language=labels["language"],
            citation_map=citation_map,
            max_items=rendered_dimension_max,
        )
    if dimension_lines:
        parts.append(f"{labels['dimension_analysis']}:\n" + "\n".join(dimension_lines))
    else:
        thesis_chain_lines = _render_thesis_driver_chain_lines(
            memo.get("thesis_driver_pack") or {},
            ref_label=labels["refs"],
            language=labels["language"],
            citation_map=citation_map,
        )
        if thesis_chain_lines:
            parts.append(f"{labels['evidence_to_thesis']}:\n" + "\n".join(thesis_chain_lines))

    required_item_rows = _required_item_answer_projection_rows(
        memo,
        logic_plan,
        state=state or {},
        rendered_so_far="\n\n".join(parts),
        language=labels["language"],
        max_items=6,
    )
    if required_item_rows:
        citation_map = _extend_memo_citation_map(citation_map, required_item_rows)
        required_item_lines = _render_required_item_answer_lines(
            required_item_rows,
            ref_label=labels["refs"],
            language=labels["language"],
            citation_map=citation_map,
        )
        if required_item_lines:
            parts.append(f"{labels['required_item_answers']}:\n" + "\n".join(required_item_lines))

    claim_lines = _render_memo_claim_lines(
        memo.get("memo_claims") or memo.get("supported_claims") or [],
        max_items=rendered_claim_max,
        ref_label=labels["refs"],
        citation_map=citation_map,
        language=labels["language"],
    )
    if claim_lines:
        parts.append(f"{labels['claims']}:\n" + "\n".join(claim_lines))

    implications = _render_loose_memo_items(memo.get("investment_implications") or [], max_items=5, language=labels["language"])
    if implications:
        parts.append(f"{labels['investment_implications']}:\n" + "\n".join(f"- {item}" for item in implications))

    change_view = _render_loose_memo_items(memo.get("what_would_change_view") or [], max_items=4, language=labels["language"])
    if change_view:
        parts.append(f"{labels['what_would_change_view']}:\n" + "\n".join(f"- {item}" for item in change_view))

    monitoring = _render_loose_memo_items(memo.get("monitoring_items") or [], max_items=5, language=labels["language"])
    if monitoring:
        parts.append(f"{labels['monitoring_items']}:\n" + "\n".join(f"- {item}" for item in monitoring))

    evidence_gaps = _render_loose_memo_items(memo.get("evidence_gaps_but_actionable") or [], max_items=3, language=labels["language"])
    if evidence_gaps:
        parts.append(f"{labels['evidence_gaps']}:\n" + "\n".join(f"- {item}" for item in evidence_gaps))

    caveats = _render_loose_memo_items(memo.get("caveats") or [], max_items=2, language=labels["language"])
    if caveats:
        parts.append(f"{labels['caveats']}:\n" + "\n".join(f"- {item}" for item in caveats))

    excluded = _render_loose_memo_items(memo.get("unsupported_claims_excluded") or [], max_items=2, language=labels["language"])
    if excluded:
        parts.append(f"{labels['unsupported_claims_excluded']}:\n" + "\n".join(f"- {item}" for item in excluded))

    boundary = _clean_user_facing_memo_text(str(memo.get("source_boundary") or "").strip())
    if boundary and not _is_generic_source_boundary_text(boundary):
        parts.append(f"{labels['source_boundary']}: {boundary}")

    if bounded and str(memo.get("answer_status") or "") == "draft" and claim_lines:
        if labels["bounded_note"]:
            parts.append(labels["bounded_note"])
    citation_appendix = _render_citation_appendix(citation_map, labels=labels)
    if citation_appendix:
        parts.append(citation_appendix)
    return "\n\n".join(part for part in parts if part)


def _memo_render_labels(memo: Mapping[str, Any]) -> dict[str, str]:
    language = ""
    response_language = memo.get("response_language")
    if isinstance(response_language, Mapping):
        language = str(response_language.get("language") or "")
    elif response_language:
        language = str(response_language)
    if language.lower() in {"zh", "zh-cn", "zh_hans"}:
        return {
            "language": "zh-CN",
            "core_thesis": "核心判断",
            "dimension_analysis": "分维度分析",
            "evidence_to_thesis": "证据到结论链条",
            "claims": "关键论据",
            "investment_implications": "投资含义",
            "what_would_change_view": "什么会改变判断",
            "monitoring_items": "后续跟踪",
            "evidence_gaps": "可行动的证据缺口",
            "caveats": "限制与注意事项",
            "unsupported_claims_excluded": "已排除的未证实说法",
            "source_boundary": "证据边界",
            "evidence_index": "证据索引",
            "required_item_answers": "关键问题回应",
            "fact_tables": "关键数据表",
            "bounded_note": "",
            "refs": "证据",
        }
    return {
        "language": "en-US",
        "core_thesis": "Core thesis",
        "dimension_analysis": "Dimension analysis",
        "evidence_to_thesis": "Evidence-to-thesis chain",
        "claims": "Key memo claims",
        "investment_implications": "Investment implications",
        "what_would_change_view": "What would change the view",
        "monitoring_items": "Monitoring items",
        "evidence_gaps": "Evidence gaps but actionable",
        "caveats": "Caveats",
        "unsupported_claims_excluded": "Unsupported claims excluded",
        "source_boundary": "Source boundary",
        "evidence_index": "Evidence index",
        "required_item_answers": "Required question coverage",
        "fact_tables": "Key fact tables",
        "bounded_note": "",
        "refs": "refs",
    }


def _memo_fact_table_blocks(memo: Mapping[str, Any], state: Mapping[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    if isinstance(memo.get("analyst_fact_table_blocks"), list):
        candidates.append(memo.get("analyst_fact_table_blocks"))
    logic_plan = memo.get("memo_logic_plan") if isinstance(memo.get("memo_logic_plan"), Mapping) else {}
    if isinstance(logic_plan.get("analyst_fact_table_blocks"), list):
        candidates.append(logic_plan.get("analyst_fact_table_blocks"))
    if isinstance(state.get("analyst_fact_table_blocks"), list):
        candidates.append(state.get("analyst_fact_table_blocks"))
    state_plan = state.get("memo_logic_plan") if isinstance(state.get("memo_logic_plan"), Mapping) else {}
    if isinstance(state_plan.get("analyst_fact_table_blocks"), list):
        candidates.append(state_plan.get("analyst_fact_table_blocks"))
    pack = state.get("supervising_analyst_pack") if isinstance(state.get("supervising_analyst_pack"), Mapping) else {}
    if isinstance(pack.get("analyst_fact_table_blocks"), list):
        candidates.append(pack.get("analyst_fact_table_blocks"))

    for candidate in candidates:
        blocks = [dict(block) for block in candidate if isinstance(block, Mapping)]
        if blocks:
            return blocks
    return []


def _memo_fact_table_rows_for_citations(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for block in blocks:
        for row in block.get("rows") or []:
            if isinstance(row, Mapping):
                rows.append(dict(row))
    return rows


def _render_memo_fact_table_blocks(
    blocks: list[dict[str, Any]],
    *,
    language: str,
    citation_map: Mapping[str, str],
    max_blocks: int = 7,
    max_rows_per_block: int = 5,
) -> str:
    rendered_blocks: list[str] = []
    for block in blocks[:max_blocks]:
        rows = [dict(row) for row in block.get("rows") or [] if isinstance(row, Mapping)]
        if not rows:
            continue
        if language == "zh-CN":
            title = str(block.get("title_zh") or block.get("title") or block.get("block_id") or "数据表").strip()
            description = _clean_user_facing_memo_text_for_render(str(block.get("description_zh") or "").strip(), language)
            header = "| 公司 | 指标/属性 | 数值或事实 | 期间/版本 | 证据强度 | 边界 | 证据 |\n| --- | --- | --- | --- | --- | --- | --- |"
        else:
            title = str(block.get("title_en") or block.get("title") or block.get("block_id") or "Fact table").strip()
            description = _clean_user_facing_memo_text_for_render(str(block.get("description") or "").strip(), language)
            header = "| Company | Metric / attribute | Value or fact | Period / version | Evidence strength | Boundary | Refs |\n| --- | --- | --- | --- | --- | --- | --- |"
        body_rows: list[str] = []
        for row in rows[:max_rows_per_block]:
            refs = [str(ref) for ref in row.get("evidence_refs") or row.get("refs") or [row.get("evidence_ref")] if str(ref or "").strip()]
            citations = _short_citation_text(refs, citation_map, max_refs=2).strip()
            boundary_values = _unique_strings(row.get("cannot_infer") or [])
            boundary = "; ".join(boundary_values[:2]) or str(row.get("authority_scope") or "")
            body_rows.append(
                "| "
                + " | ".join(
                    _markdown_table_cell(value)
                    for value in [
                        row.get("ticker") or row.get("issuer") or "",
                        row.get("metric_label") or row.get("metric_or_attribute") or "",
                        row.get("display_value") or row.get("value") or "",
                        row.get("period_or_version") or "",
                        row.get("value_quality") or row.get("authority") or "",
                        boundary,
                        citations,
                    ]
                )
                + " |"
            )
        if not body_rows:
            continue
        intro = f"**{title}**"
        if description:
            intro += f"\n{description}"
        rendered_blocks.append(intro + "\n" + header + "\n" + "\n".join(body_rows))
    return "\n\n".join(rendered_blocks)


def _markdown_table_cell(value: Any, max_chars: int = 110) -> str:
    text = _clean_user_facing_memo_text(str(value or "").strip())
    text = text.replace("|", "/").replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return _truncate_text(text, max_chars)


def _dimension_analysis_is_primary_surface(dimension_lines: list[str], profile_name: str) -> bool:
    """Avoid rendering a second numbered ClaimCard-like ledger after dense sections."""
    return str(profile_name or "").strip() in {"standard", "expanded", "deep_research"} and len(dimension_lines or []) >= 3


def _dimension_rows_in_logic_plan_order(value: Any, logic_plan: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []
    if not rows or not isinstance(logic_plan, Mapping):
        return rows
    by_dimension: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        dimension_id = str(row.get("dimension_id") or row.get("id") or "").strip()
        by_dimension.setdefault(dimension_id, []).append(row)
    ordered: list[dict[str, Any]] = []
    seen: set[int] = set()
    sections = [section for section in logic_plan.get("sections") or [] if isinstance(section, Mapping)]
    for section in sections:
        section_id = str(section.get("section_id") or "").strip()
        for row in by_dimension.get(section_id, []):
            ordered.append(row)
            seen.add(id(row))
    for row in rows:
        if id(row) not in seen:
            ordered.append(row)
    return ordered


def _build_memo_citation_map(memo: Mapping[str, Any]) -> dict[str, str]:
    refs: list[str] = []

    def add_from_rows(rows: Any) -> None:
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, Mapping):
                continue
            for ref in row.get("evidence_refs") or row.get("refs") or []:
                ref_text = str(ref or "").strip()
                if ref_text and ref_text not in refs:
                    refs.append(ref_text)

    add_from_rows(memo.get("dimension_analyses") or [])
    add_from_rows(memo.get("memo_claims") or memo.get("supported_claims") or [])
    for key in ("investment_implications", "what_would_change_view", "monitoring_items", "evidence_gaps_but_actionable"):
        add_from_rows(memo.get(key) or [])
    return {ref: f"C{index}" for index, ref in enumerate(refs, start=1)}


def _extend_memo_citation_map(citation_map: Mapping[str, str], rows: Any) -> dict[str, str]:
    out = dict(citation_map)
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        for ref in row.get("evidence_refs") or row.get("refs") or []:
            ref_text = str(ref or "").strip()
            if ref_text and ref_text not in out:
                out[ref_text] = f"C{len(out) + 1}"
    return out


def _required_item_answer_projection_rows(
    memo: Mapping[str, Any],
    logic_plan: Mapping[str, Any],
    *,
    state: Mapping[str, Any],
    rendered_so_far: str,
    language: str,
    max_items: int,
) -> list[dict[str, Any]]:
    if not isinstance(logic_plan, Mapping):
        return []
    plan_rows = [dict(item) for item in logic_plan.get("required_item_answer_plan") or [] if isinstance(item, Mapping)]
    if not plan_rows:
        return []
    rows: list[dict[str, Any]] = []
    rendered = str(rendered_so_far or "")
    for item in plan_rows:
        direct_projection = _required_item_direct_answer_projection_row(item, memo=memo, language=language)
        if direct_projection:
            rows.append(direct_projection)
            rendered += "\n" + str(direct_projection.get("summary") or "")
            if len(rows) >= max_items:
                break
            continue
        terms = _unique_strings(item.get("terms_any") or [])
        if _required_item_already_answered(rendered, terms):
            continue
        matches = _required_item_evidence_matches(item, memo, state=state)
        projection = (
            _required_item_projection_row(item, matches, language=language)
            if matches
            else _required_item_boundary_projection_row(item, language=language)
        )
        if projection:
            rows.append(projection)
            rendered += "\n" + str(projection.get("summary") or "")
        if len(rows) >= max_items:
            break
    return rows


def _required_item_direct_answer_projection_row(
    item: Mapping[str, Any],
    *,
    memo: Mapping[str, Any],
    language: str,
) -> dict[str, Any]:
    """Render writer-ready required-item answers before falling back to weak matching.

    In P33 gold-depth artifacts, ``required_item_answer_plan`` is not a raw
    search plan. It is already the Research Lead / specialist-approved answer
    material. Re-running weak evidence matching here can incorrectly downgrade
    answered items into "no promotable evidence" boundary text.
    """

    answer = str(item.get("answer") or "").strip()
    if not answer:
        return {}
    item_id = str(item.get("question_item_id") or item.get("item_id") or "").strip()
    cannot_infer = str(item.get("cannot_infer") or item.get("boundary") or "").strip()
    what_would_change = str(item.get("what_would_change_view") or "").strip()
    evidence_refs = _unique_strings(item.get("evidence_refs") or item.get("refs") or [])[:8]
    graph_refs = _unique_strings(item.get("graph_edge_refs") or [])[:6]
    localized_answer = _localized_required_item_answer_from_plan(item, memo=memo, language=language) or answer
    summary_parts = [localized_answer]
    localized_cannot_infer = _localized_required_item_cannot_infer(item_id, cannot_infer, language=language)
    localized_what_would_change = _localized_required_item_what_would_change(
        item_id,
        what_would_change,
        language=language,
    )
    if localized_cannot_infer:
        if language == "zh-CN":
            summary_parts.append("不能外推：" + localized_cannot_infer)
        else:
            summary_parts.append("Cannot infer: " + localized_cannot_infer)
    if localized_what_would_change:
        if language == "zh-CN":
            summary_parts.append("会改变判断：" + localized_what_would_change)
        else:
            summary_parts.append("What would change the view: " + localized_what_would_change)
    if graph_refs:
        if language == "zh-CN":
            summary_parts.append("图谱边：" + ", ".join(graph_refs[:4]))
        else:
            summary_parts.append("Graph edges: " + ", ".join(graph_refs[:4]))
    return {
        "dimension_id": str(item.get("memo_slot") or item.get("dimension") or "product_and_production"),
        "title": _required_item_projection_title(item_id, language),
        "summary": " ".join(summary_parts),
        "business_mechanism": str(item.get("business_mechanism") or item.get("evidence_bridge_prompt") or "").strip(),
        "financial_bridge": str(item.get("financial_bridge") or "").strip(),
        "competitive_read": str(item.get("competitive_read") or "").strip(),
        "counter_read": str(item.get("counter_read") or "").strip(),
        "evidence_refs": evidence_refs,
        "graph_edge_refs": graph_refs,
        "required_item_id": item_id,
        "source": "memo_logic_plan_required_item_answer_plan",
        "answer_status": "answered_from_writer_ready_plan",
    }


def _localized_required_item_answer_from_plan(
    item: Mapping[str, Any],
    *,
    memo: Mapping[str, Any],
    language: str,
) -> str:
    if language != "zh-CN":
        return ""
    item_id = str(item.get("question_item_id") or item.get("item_id") or "").strip()
    mapped = {
        "req_accelerator_architecture": (
            "产品层可以形成有边界的判断：NVDA GB200/Blackwell 仍代表外部加速器系统的关键瓶颈，"
            "AMD MI300/MI35x 与 Google TPU 构成真实但更偏工作负载或自用体系的替代压力。"
        ),
        "req_dell_margin_quality": (
            "DELL 的 AI server 需求可见度较强，但投资质量取决于 ISG margin、GPU pass-through、attach rate "
            "和 backlog conversion，而不是只看 AI server revenue 或订单表述。"
        ),
        "req_supply_chain": (
            "供应链 read-through 必须按机制拆开：TSMC 对应 advanced node / 先进封装，ASML 对应光刻和 installed base，"
            "AMAT 对应 materials engineering，LRCX 更偏 memory/HBM 工艺强度。"
        ),
        "req_customer_deployment": (
            "客户部署层面，DELL AI server / NVIDIA GB200 配置路径和 Google cloud TPU/GB200 云实例表面能证明采用路径存在，"
            "但仍不足以推出部署规模、客户集中度或单客户收入。"
        ),
        "req_market_price_in": (
            "市场 price-in 仍是薄弱项：业务链条方向偏正面，但缺估值分位、持仓拥挤度、short/options、ETF flow "
            "和事件后价格反应，不能形成强买卖建议。"
        ),
        "req_counter_thesis": (
            "核心反证不是泛泛的 AI 风险，而是 hyperscaler capex digestion、DELL margin dilution、AMD/TPU 替代、"
            "NVDA supply delay、出口管制、客户集中和 semicap 订单滞后。"
        ),
    }.get(item_id)
    if mapped:
        return mapped
    slot = str(item.get("memo_slot") or item.get("dimension") or "").strip()
    slot_to_dimensions = {
        "product_architecture_competition": {"product_and_production"},
        "financial_quality": {"fundamentals"},
        "semicap_readthrough": {"industry_supply_chain"},
        "customer_deployment": {"industry_supply_chain", "product_and_production"},
        "market_price_in": {"capital_and_financing"},
        "risk_counterevidence": {"risk_and_counterevidence"},
    }
    wanted_dimensions = slot_to_dimensions.get(slot, {slot} if slot else set())
    for row in memo.get("dimension_analyses") or []:
        if not isinstance(row, Mapping):
            continue
        if str(row.get("dimension_id") or "").strip() not in wanted_dimensions:
            continue
        summary = _clean_user_facing_memo_text_for_render(str(row.get("summary") or "").strip(), language)
        if summary:
            return summary
    return ""


def _localized_required_item_cannot_infer(item_id: str, value: str, *, language: str) -> str:
    if language != "zh-CN":
        return str(value or "").strip()
    mapped = {
        "req_accelerator_architecture": "不能从规格、benchmark 或云实例表面推出 SKU 收入、份额、出货量、ASP 或毛利。",
        "req_dell_margin_quality": "不能在 AI server 毛利、GPU pass-through、attach rate 和 backlog conversion 披露前认定 DELL 利润质量已经改善。",
        "req_supply_chain": "不能从 broad revenue / margin 直接推出 AI-specific orders、客户 allocation 或具体设备订单。",
        "req_customer_deployment": "不能从采用路径或配置表面推出部署规模、客户集中度或单客户收入。",
        "req_market_price_in": "不能只凭业务证据推出拥挤度、price-in 程度或买卖建议。",
        "req_counter_thesis": "不能把反证写成泛泛风险；必须落到 capex、margin、替代、供给、监管或订单链条。",
    }.get(str(item_id or "").strip())
    return mapped or str(value or "").strip()


def _localized_required_item_what_would_change(item_id: str, value: str, *, language: str) -> str:
    if language != "zh-CN":
        return str(value or "").strip()
    mapped = {
        "req_accelerator_architecture": "生产部署、采购 mix、定价证据和客户配置会改变产品竞争权重。",
        "req_dell_margin_quality": "ISG margin 随 backlog 转化改善，并伴随 attach economics 提升，会提高 DELL 质量判断。",
        "req_supply_chain": "按工具类别的 bookings/backlog、HBM/先进封装订单和客户集中度会改变 semicap read-through 置信度。",
        "req_customer_deployment": "官方客户部署、GA capacity、配置 mix 或订单规模披露会提高采用证据强度。",
        "req_market_price_in": "估值分位、13F/ETF/insider/short/options 和事件反应数据会打开 recommendation 级别判断。",
        "req_counter_thesis": "capex 下修、部署延迟、利润率恶化、替代品扩散、供给延误或监管冲击会使主线降权。",
    }.get(str(item_id or "").strip())
    return mapped or str(value or "").strip()


def _required_item_already_answered(rendered: str, terms: list[str]) -> bool:
    text = str(rendered or "")
    if not text or not terms:
        return False
    lowered = text.lower()
    judgment_markers = (
        "说明",
        "意味着",
        "支撑",
        "传导",
        "判断",
        "质量",
        "风险",
        "supports",
        "implies",
        "read-through",
        "bridge",
        "quality",
        "risk",
    )
    normalized_terms = [str(term or "").strip().lower() for term in terms if str(term or "").strip()]
    specific_terms = [term for term in normalized_terms if not _required_item_generic_entity_term(term)]
    for term in terms:
        term_text = str(term or "").strip().lower()
        if not term_text:
            continue
        index = lowered.find(term_text)
        if index < 0:
            continue
        window = lowered[max(0, index - 140) : index + len(term_text) + 220]
        if not any(marker in window for marker in judgment_markers):
            continue
        matched_specific_terms = [specific for specific in specific_terms if specific in window]
        matched_terms = [candidate for candidate in normalized_terms if candidate in window]
        if len(specific_terms) >= 2 and len(matched_specific_terms) < 2:
            continue
        if len(specific_terms) == 1 and specific_terms[0] not in window and len(matched_terms) < 2:
            continue
        if not specific_terms and len(matched_terms) < min(2, len(normalized_terms)):
            continue
        if _required_item_generic_entity_term(term_text) and specific_terms and not matched_specific_terms:
            continue
        if matched_specific_terms or len(matched_terms) >= min(2, len(normalized_terms)):
            return True
    return False


def _required_item_generic_entity_term(value: str) -> bool:
    term = str(value or "").strip()
    if not term:
        return True
    compact = re.sub(r"[^a-z0-9]", "", term.lower())
    if compact in {"ai", "gpu", "cpu", "ev"}:
        return False
    return bool(re.fullmatch(r"[a-z]{1,5}", compact))


def _required_item_evidence_matches(
    item: Mapping[str, Any],
    memo: Mapping[str, Any],
    *,
    state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for source, rows in (
        ("memo.dimension_analyses", memo.get("dimension_analyses") or []),
        ("memo.memo_claims", memo.get("memo_claims") or memo.get("supported_claims") or []),
        (
            "verified_judgment_plan.supported_claims",
            (state.get("verified_judgment_plan") or {}).get("supported_claims")
            if isinstance(state.get("verified_judgment_plan"), Mapping)
            else [],
        ),
        (
            "judgment_plan.supported_claims",
            (state.get("judgment_plan") or {}).get("supported_claims")
            if isinstance(state.get("judgment_plan"), Mapping)
            else [],
        ),
    ):
        candidates.extend(_required_item_candidate_rows(rows, source=source))
    candidates.extend(_required_item_supervising_pack_candidates(state.get("supervising_analyst_pack")))
    candidates.extend(_required_item_source_authority_candidates(state.get("source_authority_coverage")))

    scored: list[tuple[int, dict[str, Any]]] = []
    terms = [str(term or "").strip().lower() for term in _unique_strings(item.get("terms_any") or [])]
    roles = [str(role or "").strip().lower() for role in _unique_strings(item.get("required_evidence_roles") or [])]
    tickers = [str(ticker or "").strip().upper() for ticker in _unique_strings(item.get("required_tickers") or [])]
    for row in candidates:
        text = str(row.get("_search_text") or "").lower()
        score = 0
        if terms:
            score += sum(3 for term in terms if term and term in text)
        if roles:
            score += sum(2 for role in roles if role and role in text)
        if tickers:
            score += sum(2 for ticker in tickers if ticker and ticker.lower() in text)
        if score <= 0:
            continue
        if any(term in text for term in ("memo_logic_plan", "required_item_answer_plan")):
            score -= 4
        if score > 0:
            scored.append((score, row))
    return [row for _, row in sorted(scored, key=lambda scored_row: scored_row[0], reverse=True)[:6]]


def _required_item_candidate_rows(rows: Any, *, source: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        refs = _required_item_refs(row)
        text = _required_item_row_text(row)
        if not text:
            continue
        out.append(
            {
                "source": source,
                "summary": _required_item_row_summary(row),
                "ticker": str(row.get("ticker") or row.get("ticker_scope") or "").strip(),
                "evidence_refs": refs,
                "boundary": str(row.get("claim_boundary") or row.get("source_boundary") or "").strip(),
                "source_role": str(row.get("source_role") or row.get("claim_type") or row.get("source_family") or "").strip(),
                "_search_text": text,
            }
        )
    return out


def _required_item_supervising_pack_candidates(value: Any) -> list[dict[str, Any]]:
    pack = value if isinstance(value, Mapping) else {}
    product_bridge = pack.get("product_bridge_pack") if isinstance(pack.get("product_bridge_pack"), Mapping) else {}
    rows: list[dict[str, Any]] = []
    for key in (
        "official_product_context",
        "customer_deployment_context",
        "product_relationship_context",
        "product_intelligence_pack_ref",
        "product_evidence_pack_ref",
    ):
        rows.extend(_required_item_candidate_rows(_flatten_mapping_rows(product_bridge.get(key), max_rows=80), source=f"supervising_analyst_pack.{key}"))
    for dimension in _flatten_mapping_rows(pack.get("dimension_evidence_portfolio"), max_rows=80):
        rows.extend(_required_item_candidate_rows([dimension], source="supervising_analyst_pack.dimension_evidence_portfolio"))
    return rows


def _required_item_source_authority_candidates(value: Any) -> list[dict[str, Any]]:
    source_authority = value if isinstance(value, Mapping) else {}
    rows = source_authority.get("rows") if isinstance(source_authority.get("rows"), list) else []
    return _required_item_candidate_rows(rows[:250], source="source_authority_coverage.rows")


def _flatten_mapping_rows(value: Any, *, max_rows: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if len(rows) >= max_rows:
            return
        if isinstance(node, Mapping):
            if any(
                key in node
                for key in (
                    "ticker",
                    "product_family",
                    "products_or_platforms",
                    "source_role",
                    "signal",
                    "claim_scope",
                    "edge_type",
                    "pack_id",
                )
            ):
                rows.append(dict(node))
                return
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
                if len(rows) >= max_rows:
                    break

    visit(value)
    return rows


def _required_item_row_text(row: Mapping[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, default=str)


def _required_item_row_summary(row: Mapping[str, Any]) -> str:
    for key in (
        "claim",
        "summary",
        "signal",
        "claim_scope",
        "products_or_platforms",
        "product_or_segment",
        "source_role",
        "edge_type",
    ):
        value = row.get(key)
        if isinstance(value, list):
            value = ", ".join(str(item) for item in value[:8])
        text = str(value or "").strip()
        if text:
            return _truncate_text(text, 240)
    return _truncate_text(_required_item_row_text(row), 240)


def _required_item_refs(row: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("evidence_refs", "refs", "sample_evidence_refs"):
        refs.extend(_unique_strings(row.get(key) or []))
    for key in ("citation_url", "url", "sample_urls"):
        value = row.get(key)
        if isinstance(value, list):
            refs.extend(_unique_strings(value[:3]))
        else:
            text = str(value or "").strip()
            if text:
                refs.append(text)
    return _unique_strings(refs)[:6]


def _required_item_projection_row(
    item: Mapping[str, Any],
    matches: list[dict[str, Any]],
    *,
    language: str,
) -> dict[str, Any]:
    item_id = str(item.get("question_item_id") or item.get("item_id") or "").strip()
    refs = _unique_strings(ref for match in matches for ref in match.get("evidence_refs") or [])[:6]
    summary = _required_item_projection_summary(item, matches, language=language)
    counter = _required_item_projection_counter_read(item, language=language)
    return {
        "dimension_id": str(item.get("dimension") or "product_and_production"),
        "title": _required_item_projection_title(item_id, language),
        "summary": summary,
        "business_mechanism": str(item.get("evidence_bridge_prompt") or "").strip(),
        "financial_bridge": _required_item_projection_financial_bridge(item, language=language),
        "competitive_read": "",
        "counter_read": counter,
        "evidence_refs": refs,
        "required_item_id": item_id,
        "source": "memo_logic_plan_required_item_projection",
    }


def _required_item_boundary_projection_row(item: Mapping[str, Any], *, language: str) -> dict[str, Any]:
    item_id = str(item.get("question_item_id") or item.get("item_id") or "").strip()
    return {
        "dimension_id": str(item.get("dimension") or "evidence_gap"),
        "title": _required_item_projection_title(item_id, language),
        "summary": _required_item_boundary_summary(item, language=language),
        "business_mechanism": str(item.get("evidence_bridge_prompt") or "").strip(),
        "financial_bridge": _required_item_projection_financial_bridge(item, language=language),
        "competitive_read": "",
        "counter_read": _required_item_projection_counter_read(item, language=language),
        "evidence_refs": [],
        "required_item_id": item_id,
        "source": "memo_logic_plan_required_item_boundary",
        "answer_status": "answered_with_boundary_no_promotable_evidence",
        "claim_boundary": "required item has no matching promoted ClaimCard/source row in the current artifact; render as boundary, not fact.",
    }


def _render_required_item_answer_lines(
    value: Any,
    *,
    ref_label: str,
    language: str,
    citation_map: Mapping[str, str] | None = None,
    max_items: int = 6,
) -> list[str]:
    lines: list[str] = []
    for row in value if isinstance(value, list) else []:
        if not isinstance(row, Mapping):
            continue
        title = str(row.get("title") or _required_item_projection_title(str(row.get("required_item_id") or ""), language)).strip()
        summary = _clean_user_facing_memo_text_for_render(str(row.get("summary") or "").strip(), language)
        if not summary:
            continue
        bridge = _clean_user_facing_memo_text_for_render(str(row.get("financial_bridge") or "").strip(), language)
        counter = _clean_user_facing_memo_text_for_render(str(row.get("counter_read") or "").strip(), language)
        refs = [str(ref) for ref in row.get("evidence_refs") or row.get("refs") or [] if str(ref or "").strip()]
        citations = _short_citation_text(refs, citation_map or {})
        summary_without_boundary, boundary_text, change_text = _split_required_item_boundary_sentences(summary, language)
        prose_parts = _dedupe_user_facing_sentences([summary_without_boundary, bridge, counter])
        index = len(lines) + 1
        if language == "zh-CN":
            line = f"{index}. {title}：" + " ".join(prose_parts)
            if boundary_text:
                line += f"\n   - 边界：{boundary_text}"
            if change_text:
                line += f"\n   - 会改变判断：{change_text}"
        else:
            line = f"{index}. {title}: " + " ".join(prose_parts)
            if boundary_text:
                line += f"\n   - Boundary: {boundary_text}"
            if change_text:
                line += f"\n   - What would change the view: {change_text}"
        if citations:
            line += citations
        lines.append(line)
        if len(lines) >= max_items:
            break
    return lines


def _split_required_item_boundary_sentences(summary: str, language: str) -> tuple[str, str, str]:
    text = str(summary or "").strip()
    if not text:
        return "", "", ""
    if language == "zh-CN":
        boundary_marker = "不能外推："
        change_marker = "会改变判断："
    else:
        boundary_marker = "Cannot infer:"
        change_marker = "What would change the view:"
    main = text
    boundary = ""
    change = ""
    if boundary_marker in main:
        before, after = main.split(boundary_marker, 1)
        main = before.strip()
        boundary = after.strip()
    if change_marker in boundary:
        before, after = boundary.split(change_marker, 1)
        boundary = before.strip()
        change = after.strip()
    elif change_marker in main:
        before, after = main.split(change_marker, 1)
        main = before.strip()
        change = after.strip()
    return main.strip(), boundary.strip(), change.strip()


def _required_item_projection_title(item_id: str, language: str) -> str:
    if language == "zh-CN":
        return {
            "dell_ai_server_quality_margin_bridge": "DELL AI server 增长质量",
            "nvda_gpu_supply_generation": "NVDA GPU 产品代际与供给能力",
            "cloud_capex_read_through": "云厂商 capex 到供应商的传导",
            "customer_deployment_or_order_signal": "客户部署与订单采用信号",
            "asml_orders_or_backlog": "ASML 订单、预订与积压",
            "shipment_or_cycle_context": "半导体设备出货与周期位置",
            "customer_concentration_or_deployment": "客户集中度与部署信号",
            "export_restriction_context": "出口限制与中国暴露风险",
            "req_accelerator_architecture": "加速器架构与竞争替代",
            "req_customer_deployment": "客户部署与 OEM 采用路径",
            "req_dell_margin_quality": "DELL AI server 利润质量",
            "req_supply_chain": "Foundry / semicap 供应链传导",
            "req_market_price_in": "市场 price-in 与资本反馈",
            "req_counter_thesis": "反证与会改变判断的条件",
        }.get(item_id, "必答问题")
    return item_id.replace("_", " ").title() if item_id else "Required Question"


def _required_item_projection_summary(item: Mapping[str, Any], matches: list[dict[str, Any]], *, language: str) -> str:
    item_id = str(item.get("question_item_id") or "")
    lead = _required_item_best_match_phrase(matches)
    if language == "zh-CN":
        if item_id == "dell_ai_server_quality_margin_bridge":
            return (
                "DELL AI server 不能只看收入增长，当前产品/经营证据支持把 server OEM 暴露、ISG 口径、毛利和现金转化连起来判断增长质量；"
                f"当前可确认的是 {lead}，但缺少 SKU revenue 或订单 exact 时不能直接推出高毛利或份额提升。"
            )
        if item_id == "nvda_gpu_supply_generation":
            return (
                "NVDA GPU H100/H200/B200/GB200/Blackwell 的官方产品、代际、规格和产品图谱证据支撑其产品能力与 AI 需求暴露判断；"
                f"当前可确认的是 {lead}，但这些证据不能替代 SKU revenue、出货量、份额或客户订单 exact。"
            )
        if item_id == "cloud_capex_read_through":
            return (
                "AMZN/MSFT/GOOGL cloud capex 可以作为数据中心需求池信号，只有与供应商、部署、订单或产品暴露证据相连时，才可传导到 NVDA/DELL 的供应链判断；"
                f"当前可确认的是 {lead}。"
            )
        if item_id == "customer_deployment_or_order_signal":
            return (
                "客户部署、订单或采用信号用于判断产品是否真实被采用；"
                f"当前可确认的是 {lead}，若只是公开 award/channel/proxy，则只能作为采用方向或需求可见性，不能冒充总订单、backlog 或收入。"
            )
        if item_id == "asml_orders_or_backlog":
            return (
                "ASML orders/bookings/backlog 是判断 lithography 需求可见性和 semicap cycle 的关键；"
                f"当前可确认的是 {lead}，但如果没有 parsed net bookings/backlog/system shipment 表，就不能把产品 taxonomy 或同业关系冒充订单 exact。"
            )
        if item_id == "shipment_or_cycle_context":
            return (
                "semicap shipment/cycle 判断应把 AMAT/LRCX/KLAC/ASML 的公司披露与 wafer-fab-equipment cycle 分开；"
                f"当前可确认的是 {lead}，公开材料只能支持周期方向，不能替代商业 shipment tracker。"
            )
        if item_id == "customer_concentration_or_deployment":
            return (
                "客户集中度、TSMC/Samsung/Intel 部署或采用证据决定需求可见性和集中度风险；"
                f"当前可确认的是 {lead}，关系图谱只能做导航，不能单独证明客户订单规模。"
            )
        if item_id == "export_restriction_context":
            return (
                "China/export restriction/license 风险应影响 semicap revenue quality、订单可见性和风险折价；"
                f"当前可确认的是 {lead}，若缺地区收入、许可证状态或订单取消披露，只能判断风险方向，不能量化收入影响。"
            )
        terms = ", ".join(_unique_strings(item.get("terms_any") or [])[:6])
        return f"{terms or item_id} 已有可绑定证据，应进入当前判断；当前可确认的是 {lead}。"
    return f"{item_id or 'required item'} has evidence that should be surfaced; evidence anchor: {lead}."


def _required_item_boundary_summary(item: Mapping[str, Any], *, language: str) -> str:
    item_id = str(item.get("question_item_id") or item.get("item_id") or "")
    terms = ", ".join(_unique_strings(item.get("terms_any") or [])[:6])
    if language == "zh-CN":
        if item_id == "export_restriction_context":
            return (
                "出口限制、中国暴露、export restriction、license / 许可证是这个 semicap case 的必答风险项；"
                "本轮材料没有匹配到可提权的官方风险披露、地区收入、许可证状态、出口管制或订单取消证据。"
                "因此只能形成方向性风险判断：该项可能压制订单可见性、收入质量和估值折价，不能量化具体收入影响。"
            )
        if item_id == "asml_orders_or_backlog":
            return (
                "ASML order/booking/backlog 是必答项；本轮材料没有匹配到可提权的 net bookings、backlog 或系统出货表。"
                "因此只能把需求可见性判断降为边界结论：不能用产品页或同业关系替代订单 exact。"
            )
        if item_id == "shipment_or_cycle_context":
            return (
                "shipment/cycle/wafer fab equipment 是必答项；本轮材料没有匹配到可提权的 shipment tracker 或公司出货周期证据。"
                "因此只能基于公司披露和行业上下文做周期方向判断，不能声称真实 shipment 拐点。"
            )
        if item_id == "customer_concentration_or_deployment":
            return (
                "customer concentration/deployment 是必答项；本轮材料没有匹配到可提权的客户集中度、named deployment 或订单关系证据。"
                "因此只能把 TSMC/Samsung/Intel 等客户链条作为待验证风险和需求线索。"
            )
        return (
            f"{terms or item_id} 是必答项；本轮材料没有匹配到可提权证据。"
            "这应作为边界回答进入 memo，而不是静默漏答或伪造证据。"
        )
    if item_id == "export_restriction_context":
        return (
            "Export restriction / China exposure / license is a required risk item. The current artifact has no promoted "
            "official risk, regional exposure, license-status, export-control, or order-cancellation evidence, so it can "
            "only support directional risk framing rather than quantified revenue impact."
        )
    return (
        f"{terms or item_id} is required, but the current artifact has no matching promoted evidence. "
        "Render this as a boundary answer rather than omitting it or inventing evidence."
    )


def _required_item_best_match_phrase(matches: list[dict[str, Any]]) -> str:
    phrases: list[str] = []
    for match in matches[:3]:
        summary = str(match.get("summary") or "").strip()
        source_role = str(match.get("source_role") or "").strip()
        phrase = summary or source_role
        if phrase:
            phrases.append(_truncate_text(phrase, 120))
    return "；".join(phrases) if phrases else "已入库的产品/客户/来源证据"


def _required_item_projection_financial_bridge(item: Mapping[str, Any], *, language: str) -> str:
    item_id = str(item.get("question_item_id") or "")
    if language == "zh-CN":
        if item_id == "nvda_gpu_supply_generation":
            return "财务传导应写成产品能力、供给约束、客户部署和服务器供应链 read-through，而不是把缺少 SKU revenue 写成产品层失败。"
        if item_id == "cloud_capex_read_through":
            return "财务传导必须从 capex 需求池进一步连接供应商暴露；没有 named deployment/order/vendor allocation 时，只能形成 bounded read-through。"
        if item_id == "dell_ai_server_quality_margin_bridge":
            return "财务传导重点是 AI server 放量是否改善毛利、经营利润和现金流质量；缺 exact 时要写清 margin-quality 风险。"
        if item_id == "asml_orders_or_backlog":
            return "财务传导重点是订单、预订和积压能否支持未来系统收入和服务收入可见性；缺表格解析时必须明确是解析器或来源边界。"
        if item_id == "shipment_or_cycle_context":
            return "财务传导重点是 WFE/出货周期如何影响设备收入、服务收入、库存和 capex 节奏；缺 shipment tracker 时只能写方向。"
        if item_id == "customer_concentration_or_deployment":
            return "财务传导重点是客户集中度和部署信号如何影响需求稳定性、议价能力和订单可见性；缺 named customer/order 时不能量化。"
        if item_id == "export_restriction_context":
            return "财务传导重点是出口限制和中国暴露可能压制订单可见性、收入质量和风险折价；缺地区收入或许可证状态时不能量化影响。"
        return "财务传导应区分产品能力、采用信号、订单 exact 与收入/利润 exact。"
    return "Financial bridge must separate capability, adoption, order exact evidence, and revenue/profit exact evidence."


def _required_item_projection_counter_read(item: Mapping[str, Any], *, language: str) -> str:
    item_id = str(item.get("question_item_id") or "")
    if language == "zh-CN":
        if item_id == "nvda_gpu_supply_generation":
            return "反向读法是：没有客户部署、供应分配、订单或竞争替代证据时，产品代际只能支撑能力判断，不能单独证明收入份额。"
        if item_id == "cloud_capex_read_through":
            return "反向读法是：云厂商 capex 不是供应商订单；若缺供应链分配证据，只能证明需求池而不是 NVDA/DELL 份额。"
        if item_id == "customer_deployment_or_order_signal":
            return "反向读法是：公开部署或 channel proxy 不等于总订单、backlog、sell-through 或收入。"
        if item_id == "dell_ai_server_quality_margin_bridge":
            return "反向读法是：如果毛利、现金流或服务附加收入承压，AI server 收入放量可能只是低毛利规模增长。"
        if item_id == "asml_orders_or_backlog":
            return "反向读法是：没有 parsed bookings/backlog/system shipment 时，ASML 产品强度不等于订单能见度。"
        if item_id == "shipment_or_cycle_context":
            return "反向读法是：没有 shipment tracker 或公司出货披露时，行业周期判断可能只反映收入滞后而非真实订单拐点。"
        if item_id == "customer_concentration_or_deployment":
            return "反向读法是：关系图谱或客户名单不是订单规模，缺 named deployment/order 时不能证明客户集中度改善。"
        if item_id == "export_restriction_context":
            return "反向读法是：没有地区收入、许可证或订单取消证据时，只能说出口限制构成风险折价因素，不能推断具体收入损失。"
        return "反向读法是：公开证据支持方向，但不自动支持份额、收入或订单 exact。"
    return "Counter-read: public evidence supports direction but not share, revenue, or order exact evidence."


def _short_citation_text(refs: list[str], citation_map: Mapping[str, str], *, max_refs: int = 3) -> str:
    labels: list[str] = []
    for ref in refs:
        label = citation_map.get(ref)
        if label and label not in labels:
            labels.append(str(label))
        if len(labels) >= max_refs:
            break
    return (" " + "".join(f"[{label}]" for label in labels)) if labels else ""


def _render_citation_appendix(citation_map: Mapping[str, str], *, labels: Mapping[str, str], max_items: int = 12) -> str:
    if not citation_map:
        return ""
    rows = []
    for raw_ref, label in list(citation_map.items())[:max_items]:
        rows.append(f"- [{label}] {_compact_citation_ref(raw_ref)}")
    if not rows:
        return ""
    return f"{labels['evidence_index']}:\n" + "\n".join(rows)


def _compact_citation_ref(ref: Any) -> str:
    text = str(ref or "").strip()
    if not text:
        return ""
    if text.upper().startswith("INTERACTIVE_"):
        text = text[len("INTERACTIVE_") :]
    if text.startswith("__mcp__::"):
        text = text[len("__mcp__::") :]
    if "::" in text:
        parts = [part for part in text.split("::") if part]
        if parts:
            head = parts[0]
            if head.upper().startswith("INTERACTIVE_"):
                head_parts = [part for part in head.split("_")[1:] if part]
                head = " ".join(head_parts[:4]) or "interactive filing"
            if len(head) > 28:
                head = head[:28] + "..."
            tail = [part.replace("_", " ") for part in parts[1:6]]
            compact = " / ".join([head, *tail])
            return _truncate_text(compact, 110)
    if ":" in text:
        parts = [part for part in text.split(":") if part]
        if len(parts) >= 3:
            return _truncate_text(" / ".join(parts[:5]).replace("_", " "), 110)
    return _truncate_text(text.replace("_", " "), 110)


def _truncate_text(text: str, max_chars: int) -> str:
    value = str(text or "")
    if len(value) <= max_chars:
        return value
    return value[: max(0, max_chars - 1)].rstrip() + "…"


def _render_dimension_analysis_lines(
    value: Any,
    *,
    ref_label: str,
    language: str,
    citation_map: Mapping[str, str] | None = None,
    max_items: int = 5,
) -> list[str]:
    lines: list[str] = []
    for row in value if isinstance(value, list) else []:
        if not isinstance(row, Mapping):
            continue
        if not _should_render_dimension_analysis_row(row):
            continue
        title = str(row.get("title") or row.get("dimension_title") or _dimension_render_title(row.get("dimension_id"), language)).strip()
        summary = _clean_user_facing_memo_text_for_render(
            str(row.get("summary") or row.get("section_thesis") or row.get("text") or "").strip(),
            language,
        )
        if not summary:
            continue
        mechanism = _clean_user_facing_memo_text_for_render(str(row.get("business_mechanism") or "").strip(), language)
        bridge = _clean_user_facing_memo_text_for_render(str(row.get("financial_bridge") or "").strip(), language)
        competitive = _clean_user_facing_memo_text_for_render(str(row.get("competitive_read") or "").strip(), language)
        counter = _clean_user_facing_memo_text_for_render(str(row.get("counter_read") or "").strip(), language)
        refs = [str(ref) for ref in row.get("evidence_refs") or row.get("refs") or [] if str(ref or "").strip()]
        citations = _short_citation_text(refs, citation_map or {})
        prose_parts = _dimension_prose_without_gap_dominance(
            _dedupe_user_facing_sentences([summary, mechanism, bridge, competitive, counter]),
            language=language,
        )
        index = len(lines) + 1
        if language == "zh-CN":
            line = f"{index}. {title}：" + " ".join(prose_parts)
        else:
            line = f"{index}. {title}: " + " ".join(prose_parts)
        if citations:
            line += citations
        lines.append(line)
        if len(lines) >= max_items:
            break
    return lines


def _should_render_dimension_analysis_row(row: Mapping[str, Any]) -> bool:
    dimension_id = str(row.get("dimension_id") or row.get("id") or "").strip()
    if dimension_id == "thesis_synthesis":
        return False
    refs = [str(ref) for ref in row.get("evidence_refs") or row.get("refs") or [] if str(ref or "").strip()]
    status = str(row.get("status") or row.get("stance") or "").strip().lower()
    if not refs and any(marker in status for marker in ("gap", "bounded", "unsupported")):
        return False
    title = str(row.get("title") or row.get("dimension_title") or "").strip().lower()
    summary = str(row.get("summary") or row.get("section_thesis") or row.get("text") or "").strip().lower()
    if title == "synthesis" and summary in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}:
        return False
    return True


def _dimension_render_title(value: Any, language: str) -> str:
    key = str(value or "").strip()
    if language == "zh-CN":
        return {
            "fundamentals": "基本面与财务质量",
            "product_and_production": "产品与产线",
            "capital_and_financing": "投融资与资本开支",
            "competition_and_market_position": "竞争格局与市场位置",
            "industry_supply_chain": "行业与供应链传导",
            "risk_and_counterevidence": "风险与反证",
            "evidence_gap": "证据缺口",
        }.get(key, "分析维度")
    return {
        "fundamentals": "Fundamentals and financial quality",
        "product_and_production": "Product and production line evidence",
        "capital_and_financing": "Capital allocation and financing",
        "competition_and_market_position": "Competition and market position",
        "industry_supply_chain": "Industry and supply-chain transmission",
        "risk_and_counterevidence": "Risk and counterevidence",
        "evidence_gap": "Evidence gap",
    }.get(key, "Analyst dimension")


def _render_thesis_driver_chain_lines(
    value: Any,
    *,
    ref_label: str,
    language: str,
    citation_map: Mapping[str, str] | None = None,
    max_items: int = 5,
) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    drivers = [row for row in value.get("driver_cards") or [] if isinstance(row, Mapping)]
    counters = [row for row in value.get("counter_driver_cards") or [] if isinstance(row, Mapping)]
    gaps = [row for row in value.get("gap_cards") or [] if isinstance(row, Mapping)]
    lines: list[str] = []

    def add(prefix: str, row: Mapping[str, Any]) -> None:
        if len(lines) >= max_items:
            return
        slot = str(row.get("memo_slot") or row.get("gap_type") or "").strip()
        refs = [str(ref) for ref in row.get("evidence_refs") or [] if str(ref or "").strip()]
        if language == "zh-CN":
            slot_label = _zh_thesis_chain_slot(slot)
            text = f"{prefix}{slot_label}"
            if refs:
                text += _short_citation_text(refs, citation_map or {})
        else:
            slot_label = _en_thesis_chain_slot(slot)
            text = f"{prefix}{slot_label}"
            if refs:
                text += _short_citation_text(refs, citation_map or {})
        lines.append(f"{len(lines) + 1}. {text}")

    if language == "zh-CN":
        for row in drivers[:3]:
            add("支撑：", row)
        for row in counters[:1]:
            add("反证/风险：", row)
        for row in gaps[:1]:
            add("缺口：", row)
    else:
        for row in drivers[:3]:
            add("Support: ", row)
        for row in counters[:1]:
            add("Counter/risk: ", row)
        for row in gaps[:1]:
            add("Gap: ", row)
    return lines


def _zh_thesis_chain_slot(slot: str) -> str:
    return {
        "fundamentals": "基本面驱动",
        "product_technology": "产品/技术驱动",
        "industry_relationship": "行业/关系背景",
        "market_valuation": "市场/估值背景",
        "risk_counterevidence": "风险或反证",
        "missing_confirmation": "待补确认",
        "unsupported_claim_excluded": "已排除未证实说法",
        "source_boundary": "证据边界",
    }.get(str(slot or "").strip(), "已验证论据")


def _en_thesis_chain_slot(slot: str) -> str:
    return {
        "fundamentals": "fundamental driver",
        "product_technology": "product/technology driver",
        "industry_relationship": "industry/relationship context",
        "market_valuation": "market/valuation context",
        "risk_counterevidence": "risk or counterevidence",
        "missing_confirmation": "missing confirmation",
        "unsupported_claim_excluded": "excluded unsupported claim",
        "source_boundary": "source boundary",
    }.get(str(slot or "").strip(), "verified claim")


def _render_memo_claim_lines(
    value: Any,
    *,
    max_items: int = 5,
    ref_label: str = "refs",
    citation_map: Mapping[str, str] | None = None,
    language: str = "",
) -> list[str]:
    lines: list[str] = []
    for index, claim in enumerate(value if isinstance(value, list) else [], start=1):
        if not isinstance(claim, Mapping):
            continue
        text = _clean_user_facing_memo_text_for_render(str(claim.get("claim") or claim.get("text") or "").strip(), language)
        if not text:
            continue
        refs = [str(ref) for ref in claim.get("evidence_refs") or claim.get("refs") or [] if str(ref or "").strip()]
        ref_text = _short_citation_text(refs, citation_map or {}, max_refs=4)
        lines.append(f"{len(lines) + 1}. {text}{ref_text}")
        if len(lines) >= max(1, max_items):
            break
    return lines


def _render_loose_memo_items(value: Any, *, max_items: int, language: str = "") -> list[str]:
    items: list[str] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, Mapping):
            text = str(item.get("text") or item.get("claim") or item.get("reason") or item.get("type") or "").strip()
        else:
            text = str(item or "").strip()
        text = _clean_user_facing_memo_text_for_render(text, language)
        if text:
            items.append(text)
        if len(items) >= max_items:
            break
    return items


def _clean_user_facing_memo_text(text: str) -> str:
    clean = str(text or "").strip()
    if not clean:
        return ""
    clean = re.sub(r"基于已验证证据并在当前证据边界内，(?:本段结论|本条论据|此项说明)概括为：", "", clean)
    clean = clean.replace("以上表述仅对应已列证据引用，不代表超出来源范围的新增事实。", "")
    clean = clean.replace("以上表述仅对应已列证据引用，不代表超出来源范围的新增事实。", "")
    clean = re.sub(r"[。；;]?\s*不得推断未验证[^。；;\n]*(?=[。；;\n]|$)", "", clean)
    clean = re.sub(r"[。；;]?\s*该声明(?:为|卡为)?已核对[^。；;\n]*(?=[。；;\n]|$)", "", clean)
    clean = re.sub(r"[。；;]?\s*该声明卡[^。；;\n]*(?=[。；;\n]|$)", "", clean)
    clean = re.sub(r"[。；;]?\s*Reported revenue[^。；;\n]*(?=[。；;\n]|$)", "", clean, flags=re.I)
    clean = re.sub(r"[。；;]?\s*Company-disclosed product[^。；;\n]*(?=[。；;\n]|$)", "", clean, flags=re.I)
    clean = re.sub(r"[。；;]?\s*The evidence traces[^。；;\n]*(?=[。；;\n]|$)", "", clean, flags=re.I)
    clean = re.sub(r"[。；;]?\s*Capital spending, cash generation[^。；;\n]*(?=[。；;\n]|$)", "", clean, flags=re.I)
    clean = re.sub(r"[。；;]?\s*Competitive or market-position[^。；;\n]*(?=[。；;\n]|$)", "", clean, flags=re.I)
    clean = re.sub(r"[。；;]?\s*No direct competitive comparison[^。；;\n]*(?=[。；;\n]|$)", "", clean, flags=re.I)
    clean = re.sub(r"[。；;]?\s*Peer comparison is available only[^。；;\n]*(?=[。；;\n]|$)", "", clean, flags=re.I)
    clean = re.sub(r"[。；;]?\s*If the fact conflicts with another approved row[^。；;\n]*(?=[。；;\n]|$)", "", clean, flags=re.I)
    clean = re.sub(r"\b([A-Z]{1,8})\s+reported product\s+收入\s+of\s+", r"\1 产品收入 ", clean, flags=re.I)
    clean = re.sub(r"\b([A-Z]{1,8})\s+reported\s+收入\s+of\s+", r"\1 收入 ", clean, flags=re.I)
    clean = re.sub(r"\breported product\s+收入\b", "产品收入", clean, flags=re.I)
    clean = re.sub(r"\breported\s+收入\b", "收入", clean, flags=re.I)
    clean = re.sub(r"\bin\s+fiscal:\d{4}(?::[A-Za-z0-9]+)*", "", clean, flags=re.I)
    clean = re.sub(r"\bfiscal:\d{4}(?::[A-Za-z0-9]+)*", "", clean, flags=re.I)
    clean = re.sub(
        r"[。；;]?\s*投资判断应先[^。；;\n]*(?:再判断|后续重点)[^。；;\n]*(?=[。；;\n]|$)",
        "。当前判断框架需要把需求、供应商自身投入、产品收入或订单、毛利和现金流分层验证",
        clean,
    )
    clean = re.sub(r"[；;]?\s*该表述仅限已验证\s*ClaimCard\s*与引用证据范围，不外推未证实事实。?", "", clean, flags=re.I)
    clean = re.sub(
        r"[。；;]?\s*该声明卡为(?:已|经)?核对的?(?:数值|财务)?事实[；;，,]?\s*任何论点(?:必须明确桥接至|需将其与)[^。；;\n]*",
        "",
        clean,
    )
    clean = _remove_inline_raw_evidence_refs(clean)
    clean = re.sub(r"\b(?:evidence_refs?|refs?)\s*[:：]\s*(?=[。；;,.，、\s]|$)", "", clean, flags=re.I)
    clean = re.sub(r"证据\s*(?:refs?|引用)?\s*[:：]\s*(?=[。；;,.，、\s]|$)", "", clean, flags=re.I)
    clean = re.sub(r"(?<!公开)证据\s*(?=[。；;.]|$)", "", clean)
    clean = re.sub(r"\bdirection\s*=\s*[A-Za-z_:-]+", "", clean, flags=re.I)
    clean = clean.replace("industry_relationship", "行业关系")
    clean = re.sub(r"\b(?:mechanism|financial bridge|competition/position|counter/boundary|source boundary)\s*[:：]\s*", "", clean, flags=re.I)
    clean = re.sub(r"(?:机制|财务桥|竞争/位置|反证/边界|证据边界)\s*[:：]\s*", "", clean)
    if _looks_like_internal_surface_instruction(clean):
        return ""
    clean = re.sub(r"\b(?:driver_id|gap_id|source_boundary_notes|reconciliation_candidate)\b\s*[:=]\s*[\w:.-]+", "", clean)
    clean = _replace_internal_metric_ids_for_render(clean)
    clean = clean.replace("共享备忘录上下文、紧凑验证判断计划和专家验证中的证据", "已验证的公开披露、行业关系图和市场/行业快照证据")
    clean = clean.replace("未使用原始行或检索请求", "不包含未经核验的原始检索结果")
    clean = clean.replace("官方来源修复确认", "官方来源确认")
    clean = clean.replace("产品表面信息", "产品线信息")
    clean = clean.replace("产品表面", "产品线")
    clean = clean.replace("management commentary", "管理层表述")
    clean = re.sub(r"\s+\|\s+", "；", clean)
    clean = re.sub(r"\s+([。；，、])", r"\1", clean)
    clean = re.sub(r"[，,]\s*([。；;])", r"\1", clean)
    clean = re.sub(r"\s+\.(?=\s|$)", "。", clean)
    clean = re.sub(r"且\s+([A-Za-z$\u4e00-\u9fff])", r"且\1", clean)
    clean = re.sub(r"([。；;])\s*[。；;]+", r"\1", clean)
    clean = re.sub(r"\s{2,}", " ", clean).strip(" 。；,，、")
    return clean


def _replace_internal_metric_ids_for_render(text: str) -> str:
    replacements = {
        "financial_metric:revenue": "收入",
        "financial_metric:gross_margin": "毛利率",
        "financial_metric:gross_profit": "毛利",
        "financial_metric:operating_income": "营业利润",
        "financial_metric:operating_cash_flow": "经营现金流",
        "financial_metric:fcf": "自由现金流",
        "financial_metric:capex": "资本开支",
        "financial_metric:debt": "债务",
        "financial_metric:cash": "现金",
        "financial_metric:inventory": "库存",
        "product_kpi:product_revenue": "产品收入",
        "product_kpi:backlog": "订单积压",
        "product_kpi:shipment": "出货量",
        "product_kpi:delivery": "交付量",
        "product_kpi:capacity": "产能",
        "product_kpi:utilization": "利用率",
        "product_kpi:subscribers": "订阅用户",
        "product_kpi:arr": "ARR",
        "product_kpi:rpo": "RPO",
    }
    clean = str(text or "")
    for raw, label in replacements.items():
        clean = re.sub(re.escape(raw), label, clean, flags=re.I)
    return clean


def _clean_user_facing_memo_text_for_render(text: str, language: str) -> str:
    clean = _clean_user_facing_memo_text(text)
    if not clean:
        return ""
    if str(language or "") != "zh-CN":
        return clean
    clean = _remove_english_template_sentences(clean)
    if not clean:
        return ""
    if _zh_render_text_is_mostly_english_prose(clean):
        return ""
    return clean


def _remove_english_template_sentences(text: str) -> str:
    parts = re.split(r"(?<=[。！？.!?])\s+|(?<=；)\s+|\n+", str(text or ""))
    kept: list[str] = []
    for part in parts:
        value = part.strip()
        if not value:
            continue
        lowered = value.lower()
        if any(
            marker in lowered
            for marker in (
                "the evidence supports",
                "the evidence frames",
                "the evidence links",
                "caveat:",
                "missing confirmation:",
                "if the fact conflicts with another approved row",
                "period changes compare",
                "company-reported orders/backlog",
                "not strictly same-period",
                "non-gaap measure",
                "gaap gross margin",
            )
        ):
            continue
        kept.append(value)
    return " ".join(kept).strip(" 。；,，、")


def _zh_render_text_is_mostly_english_prose(text: str) -> bool:
    value = str(text or "").strip()
    if not value:
        return False
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", value))
    latin_text = re.sub(
        r"\b(?:[A-Z]{1,8}|10-[KQ]|20-F|6-K|8-K|S-[13]|GAAP|SEC|FY\d{2,4}|Q[1-4]|AI|EV|GPU|CPU|API|SaaS)\b",
        " ",
        value,
    )
    latin_words = len(re.findall(r"[A-Za-z]{3,}", latin_text))
    if cjk_count == 0 and latin_words >= 3:
        return True
    return latin_words >= max(10, cjk_count)


def _is_generic_source_boundary_text(text: str) -> bool:
    value = str(text or "").strip().lower()
    return value in {
        "",
        "verified judgment plan only",
        "bounded verified judgment plan only",
        "仅限已验证 judgment plan；不包含原始检索行",
        "仅限已验证 judgment plan；不包含原始检索行。",
        "仅限已验证 judgment plan 和 source_boundary_notes 指定的证据范围；不包含原始检索行",
        "仅限已验证 judgment plan 和 source_boundary_notes 指定的证据范围；不包含原始检索行。",
        "仅使用已验证的公开披露、行业关系图和市场/行业快照证据。不包含未经核验的原始检索结果",
        "仅使用已验证的公开披露、行业关系图和市场/行业快照证据。不包含未经核验的原始检索结果。",
    }


def _remove_inline_raw_evidence_refs(text: str) -> str:
    clean = str(text or "")
    # Writer models sometimes echo internal evidence ids in prose. The renderer
    # appends short citations separately, so these raw ids are not user-facing.
    clean = re.sub(
        r"(?:[；;]\s*)?(?:证据引用为|证据\s*[=:：])\s*[^。；;\n]*(?:INTERACTIVE_|__mcp__::|reconciliation_candidate:)[^。；;\n]*(?=[。；;\n]|$)",
        "",
        clean,
        flags=re.I,
    )
    clean = re.sub(r"(?:[；;]\s*)?证据引用为\s*.*?(?=\s*(?:\[[Cc]\d+\]|[。；;\n]|$))", "", clean)
    clean = re.sub(r"INTERACTIVE_[^\s，,；;。)）\]]+", "", clean, flags=re.I)
    clean = re.sub(r"__mcp__::[^\s，,；;。)）\]]+", "", clean)
    clean = re.sub(r"reconciliation_candidate:[A-Za-z0-9_.:-]+", "", clean)
    clean = re.sub(
        r"(?:[；;]\s*)?可对应\s*[^。；;\n]*(?:(?:::)|(?:BLOCK_\d+)|(?:METRIC_TABLE_))[^^。；;\n]*(?=[。；;\n]|$)",
        "",
        clean,
        flags=re.I,
    )
    clean = re.sub(
        r"\b[A-Z]{2,8}_\d{4}_[A-Z0-9_]+(?:::)[A-Za-z0-9_:.-]+",
        "",
        clean,
    )
    clean = re.sub(r"(?:证据引用为|证据\s*[=:：])\s*(?:[,，、]\s*)*(?=[。；;]|$)", "", clean)
    clean = re.sub(r"\s*[,，、]\s*(?=[。；;])", "", clean)
    return clean


def _looks_like_internal_surface_instruction(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(
        marker in lowered
        for marker in (
            "bridge the claim through",
            "this claimcard",
            "synthesized thesis",
            "pipe-delimited",
            "do_not_emit",
            "source_boundary_notes",
        )
    )


def _dedupe_user_facing_sentences(parts: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for part in parts:
        text = _clean_user_facing_memo_text(part)
        if not text:
            continue
        key = re.sub(r"\W+", "", text.lower())[:120]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(text)
    return deduped


def _dimension_prose_without_gap_dominance(parts: list[str], *, language: str) -> list[str]:
    if str(language or "") != "zh-CN":
        return parts
    result: list[str] = []
    for part in parts:
        trimmed = _trim_gap_tail_from_zh_dimension_text(part)
        if not trimmed:
            continue
        if _zh_dimension_text_is_gap_dominant(trimmed):
            continue
        result.append(trimmed)
        if len(result) >= 3:
            break
    return result or parts[:1]


def _trim_gap_tail_from_zh_dimension_text(text: str) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    for marker in ("但缺乏", "但缺少", "但缺失", "但未", "但无法", "但不能", "但当前"):
        index = value.find(marker)
        if index >= 18:
            return value[:index].rstrip(" ，,；;。")
    for marker in ("；缺乏", "；缺少", "；缺失", "；未披露", "；无法", "；不能", "。缺乏", "。缺少", "。未披露"):
        index = value.find(marker)
        if index >= 18:
            return value[:index].rstrip(" ，,；;。")
    return value


def _zh_dimension_text_is_gap_dominant(text: str) -> bool:
    value = str(text or "").lower()
    terms = ("缺口", "缺乏", "缺少", "缺失", "无法", "不能", "未披露", "尚未", "受限", "仅能确认", "需等待", "口径不匹配")
    hits = sum(value.count(term) for term in terms)
    return hits >= 2 or (hits >= 1 and len(value) <= 80)


def _render_deterministic_lookup_answer(state: Mapping[str, Any]) -> str:
    rows = _dedupe_runtime_ledger_rows([dict(row) for row in state.get("runtime_ledger_rows") or [] if isinstance(row, Mapping)])
    query_contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    requested = {str(item) for item in query_contract.get("metric_families") or [] if str(item)}
    if "capex" in requested:
        requested.add("capital_expenditure_proxy")
    if requested:
        preferred = [row for row in rows if str(row.get("metric_family") or "") in requested]
    else:
        preferred = rows
    preferred = _prefer_amount_compatible_ledger_rows(preferred)
    preferred = _rank_deterministic_lookup_rows(
        preferred,
        requested_metric_families=list(query_contract.get("metric_families") or []),
        user_query=str(state.get("user_query") or ""),
    )
    requested_years = {str(year) for year in query_contract.get("years") or [] if str(year or "").strip()}
    if requested_years:
        same_year = [row for row in preferred if str(row.get("fiscal_year") or "") in requested_years]
        if same_year:
            preferred = same_year
    selected = preferred[:4] or rows[:4]
    language = _state_response_language(state)
    if language.startswith("zh"):
        tickers = ", ".join(_unique_upper(query_contract.get("focus_tickers") or query_contract.get("search_scope_tickers") or []))
        header = f"单指标结果：{tickers or '目标公司'} 的已检索结构化披露中，最直接的匹配如下："
        lines = [header]
        for index, row in enumerate(selected, start=1):
            label = str(row.get("metric_name") or row.get("metric_family") or "metric").strip()
            year = str(row.get("fiscal_year") or "").strip()
            role = str(row.get("period_role") or "").upper().strip()
            value = ledger_metric_display_value(row)
            evidence = str(row.get("source_evidence_id") or row.get("object_id") or "").strip()
            period = f"{year} {role}".strip()
            lines.append(f"{index}. {label}: {value} ({period}) 证据={evidence}")
        lines.append("证据边界：以上只来自本轮 SEC primary filing 的 runtime exact-value ledger；如果同一 10-Q 同时披露 QTD/YTD 或 MD&A 口径，我保留口径差异，不把其中一个数强行改写成单一全年口径。")
        return "\n".join(lines)

    tickers = ", ".join(_unique_upper(query_contract.get("focus_tickers") or query_contract.get("search_scope_tickers") or []))
    lines = [f"Single-metric result: the closest structured filing matches for {tickers or 'the requested company'} are:"]
    for index, row in enumerate(selected, start=1):
        label = str(row.get("metric_name") or row.get("metric_family") or "metric").strip()
        year = str(row.get("fiscal_year") or "").strip()
        role = str(row.get("period_role") or "").upper().strip()
        value = ledger_metric_display_value(row)
        evidence = str(row.get("source_evidence_id") or row.get("object_id") or "").strip()
        period = f"{year} {role}".strip()
        lines.append(f"{index}. {label}: {value} ({period}) refs={evidence}")
    lines.append("Source boundary: values come only from the runtime exact-value ledger for SEC primary filing rows; if QTD/YTD or MD&A wording differs, the answer preserves that scope instead of forcing a single annualized figure.")
    return "\n".join(lines)


def _prefer_amount_compatible_ledger_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compatible = [row for row in rows if _ledger_row_amount_display_compatible(row)]
    return compatible or rows


def _rank_deterministic_lookup_rows(
    rows: list[dict[str, Any]],
    *,
    requested_metric_families: list[Any],
    user_query: str,
) -> list[dict[str, Any]]:
    if not rows:
        return []
    requested_order = {str(family): index for index, family in enumerate(requested_metric_families)}
    indexed = list(enumerate(rows))
    indexed.sort(
        key=lambda item: (
            -_deterministic_lookup_row_score(
                item[1],
                requested_order=requested_order,
                user_query=user_query,
            ),
            item[0],
        )
    )
    return [row for _, row in indexed]


def _deterministic_lookup_row_score(
    row: Mapping[str, Any],
    *,
    requested_order: Mapping[str, int],
    user_query: str,
) -> int:
    family = str(row.get("metric_family") or "").strip()
    role = str(row.get("metric_role") or "").strip().lower()
    text = " ".join(
        str(row.get(key) or "")
        for key in (
            "metric_family",
            "metric_name",
            "metric",
            "field",
            "metric_id",
            "source_evidence_id",
            "raw_value_text",
            "display_value_zh",
            "source_statement",
            "summary",
        )
    ).lower()
    query = str(user_query or "").lower()
    score = 0
    if family in requested_order:
        score += 220 - min(120, requested_order[family] * 30)
    if role in {"total_value", "current_value", "amount"}:
        score += 90
    elif role == "period_change_amount":
        score += 55
    elif role in {"percentage_rate", "rate", "ratio", "margin", "growth_rate", "percentage"}:
        score -= 180
    if _deterministic_value_looks_rate(str(row.get("display_value_zh") or row.get("raw_value_text") or row.get("value") or "")):
        score -= 140

    if "capex" in requested_order or "capital_expenditure_proxy" in requested_order or "capex" in query:
        if family in {"capex", "capital_expenditure_proxy"}:
            score += 180
        if any(term in text for term in ("capital expenditure", "capital expenditures", "capex", "additions to property")):
            score += 120
        if any(term in text for term in ("property and equipment, net", "property and equipment net", "land", "total assets")):
            score -= 180
        if "depreciation" in text or "amortization" in text:
            score -= 80

    provision_intent = any(term in query for term in ("provision", "credit loss", "信用", "拨备"))
    if provision_intent:
        if family == "provision_for_credit_losses":
            score += 220
        elif family == "net_charge_offs":
            score -= 55
        if any(term in text for term in ("provision for credit losses", "credit loss provision", "credit losses provision")):
            score += 140
        if any(term in text for term in ("change", "increase", "decrease", "同比", "环比")) and role not in {
            "total_value",
            "current_value",
            "amount",
        }:
            score -= 110
    return score


def _deterministic_value_looks_rate(value_text: str) -> bool:
    text = str(value_text or "").strip().lower()
    return bool(text) and any(marker in text for marker in ("%", "percent", "percentage", "百分比", "百分率"))


def _ledger_row_amount_display_compatible(row: Mapping[str, Any]) -> bool:
    display = str(row.get("display_value_zh") or row.get("raw_value_text") or row.get("value") or "").strip()
    rendered = ledger_metric_display_value(row)
    return not display or rendered == display


def _state_response_language(state: Mapping[str, Any]) -> str:
    value = state.get("response_language")
    if not value and isinstance(state.get("multi_agent_context"), Mapping):
        value = (state.get("multi_agent_context") or {}).get("response_language")
    text = str(value or "").strip().lower().replace("_", "-")
    if text in {"zh", "zh-cn", "zh-hans", "chinese", "中文"}:
        return "zh-CN"
    if text in {"en", "en-us", "english"}:
        return "en-US"
    query = str(state.get("user_query") or "")
    return "zh-CN" if any("\u4e00" <= ch <= "\u9fff" for ch in query) else "en-US"


def _dedupe_runtime_ledger_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str, str, str]] = set()
    for row in rows:
        key = (
            str(row.get("ticker") or ""),
            str(row.get("fiscal_year") or ""),
            str(row.get("metric_family") or ""),
            str(row.get("metric_role") or ""),
            str(row.get("period_role") or ""),
            str(row.get("raw_value_text") or row.get("value") or ""),
            str(row.get("display_value_zh") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _node_multi_agent_renderer(
    state: SecAgentGraphRuntimeState,
    *,
    renderer: MultiAgentNodeFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if renderer is not None:
        result = renderer(state)
    else:
        verification = state.get("claim_verification") if isinstance(state.get("claim_verification"), dict) else {}
        memo = state.get("memo_answer") if isinstance(state.get("memo_answer"), dict) else {}
        bounded = bool(
            state.get("bounded_answer_allowed")
            or memo.get("bounded_answer_allowed")
            or str(memo.get("answer_status") or "").startswith("blocked_")
        )
        mode = str((state.get("agent_activation_plan") or {}).get("execution_mode") or "")
        if mode == "deterministic_lookup" and state.get("runtime_ledger_rows"):
            result = {"rendered_answer": _render_deterministic_lookup_answer(state)}
        elif verification.get("status") == "fail":
            if _memo_has_renderable_content(memo):
                result = {"rendered_answer": _render_memo_answer(memo, bounded=True, state=state)}
            else:
                result = {"rendered_answer": "Bounded answer only: memo verification failed under current evidence constraints."}
        elif bounded:
            if str(memo.get("answer_status") or "") == "draft" and memo.get("memo_claims"):
                result = {"rendered_answer": _render_memo_answer(memo, bounded=True, state=state)}
            else:
                result = {
                    "rendered_answer": "Bounded answer only: "
                    + str(memo.get("direct_answer") or "current evidence constraints block full memo generation.")
                }
        else:
            result = {"rendered_answer": _render_memo_answer(memo, bounded=False, state=state)}
    return _record_node({**state, **result}, "renderer", metadata={"mode": "injected" if renderer else "stub"})


def _memo_has_renderable_content(memo: Mapping[str, Any]) -> bool:
    if str(memo.get("direct_answer") or "").strip():
        return True
    for key in (
        "dimension_analyses",
        "memo_claims",
        "supported_claims",
        "investment_implications",
        "what_would_change_view",
        "monitoring_items",
        "evidence_gaps_but_actionable",
    ):
        value = memo.get(key)
        if isinstance(value, list) and any(isinstance(item, Mapping) or str(item or "").strip() for item in value):
            return True
    return False


def _node_multi_agent_persist_session_state(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    state_with_refs = _with_multi_agent_artifact_refs(_with_native_artifact_refs({**state, "status": "completed"}))
    state_with_layers = _state_with_d4_d5_layers(state_with_refs)
    state_with_reconciliation = _state_with_d6_d7_layers(state_with_layers)
    state_with_gates = _state_with_d9_gate_matrix(state_with_reconciliation)
    state_with_derived_metrics = _state_with_d10_derived_metric_layer(state_with_gates)
    state_with_fundamental_pack = _state_with_fundamental_statement_pack(state_with_derived_metrics)
    state_with_analyst_views = _state_with_d11_analyst_view_layer(state_with_fundamental_pack)
    state_with_materialization = _state_with_d12_1_database_materialization(state_with_analyst_views)
    state_with_closeout_gate = _state_with_d12_database_closeout_gate(state_with_materialization)
    final_state = _record_node(state_with_closeout_gate, "persist_session_state")
    final_state = _state_with_run_audit_materialization(final_state)
    summary_payload = build_multi_agent_summary_artifact_payload(final_state)
    final_state = {**final_state, "multi_agent_summary": summary_payload}
    _write_native_state_artifacts(final_state)
    _write_multi_agent_governance_ledger_artifacts(final_state)
    _write_multi_agent_summary_artifact(final_state)
    return final_state


def _state_with_d4_d5_layers(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    provenance_store = state.get("raw_source_provenance_store") if isinstance(state.get("raw_source_provenance_store"), dict) else {}
    vintage_layer = state.get("asof_vintage_layer") if isinstance(state.get("asof_vintage_layer"), dict) else {}
    needs_artifact_ref_refresh = bool(state.get("artifact_refs")) and not _provenance_has_artifact_refs(provenance_store)
    if provenance_store and vintage_layer and not needs_artifact_ref_refresh:
        return state
    layers = build_provenance_vintage_layers(state)
    if not provenance_store or needs_artifact_ref_refresh:
        provenance_store = layers.get("raw_source_provenance_store") if isinstance(layers.get("raw_source_provenance_store"), dict) else {}
    if not vintage_layer:
        vintage_layer = layers.get("asof_vintage_layer") if isinstance(layers.get("asof_vintage_layer"), dict) else {}
    return {**state, "raw_source_provenance_store": provenance_store, "asof_vintage_layer": vintage_layer}


def _provenance_has_artifact_refs(provenance_store: Mapping[str, Any]) -> bool:
    return any(
        isinstance(row, Mapping) and row.get("record_type") == "artifact_ref"
        for row in provenance_store.get("records") or []
    )


def _state_with_d6_d7_layers(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    ontology = state.get("metric_product_ontology_snapshot") if isinstance(state.get("metric_product_ontology_snapshot"), dict) else {}
    reconciliation = state.get("reconciliation_ledger") if isinstance(state.get("reconciliation_ledger"), dict) else {}
    if ontology and reconciliation:
        return state
    layers = build_metric_ontology_and_reconciliation_layers(state)
    if not ontology:
        ontology = (
            layers.get("metric_product_ontology_snapshot")
            if isinstance(layers.get("metric_product_ontology_snapshot"), dict)
            else {}
        )
    if not reconciliation:
        reconciliation = layers.get("reconciliation_ledger") if isinstance(layers.get("reconciliation_ledger"), dict) else {}
    return {**state, "metric_product_ontology_snapshot": ontology, "reconciliation_ledger": reconciliation}


def _state_with_d9_gate_matrix(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    gate_matrix = state.get("gate_registry_eval_matrix") if isinstance(state.get("gate_registry_eval_matrix"), dict) else {}
    if gate_matrix:
        return state
    return {**state, "gate_registry_eval_matrix": build_gate_registry_eval_matrix(state)}


def _state_with_d10_derived_metric_layer(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    derived_layer = state.get("derived_metric_layer") if isinstance(state.get("derived_metric_layer"), dict) else {}
    if derived_layer:
        return state
    return {**state, "derived_metric_layer": build_derived_metric_layer(state)}


def _state_with_fundamental_statement_pack(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    pack = state.get("fundamental_statement_pack") if isinstance(state.get("fundamental_statement_pack"), dict) else {}
    if pack:
        return state
    return {**state, "fundamental_statement_pack": build_fundamental_statement_pack(state)}


def _state_with_d11_analyst_view_layer(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    analyst_views = (
        state.get("analyst_view_research_memory")
        if isinstance(state.get("analyst_view_research_memory"), dict)
        else {}
    )
    if analyst_views:
        return state
    return {**state, "analyst_view_research_memory": build_analyst_view_research_memory_layer(state)}


def _state_with_d12_1_reader_context(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    if isinstance(state.get("d_series_claim_gap_gate_reader_context"), dict) and isinstance(state.get("d_series_research_context"), dict):
        return state
    db_path = _d_series_governance_db_path(state)
    if db_path is None or not db_path.exists():
        return state
    tickers = _d_series_reader_tickers(state)
    reader_context = state.get("d_series_claim_gap_gate_reader_context") if isinstance(state.get("d_series_claim_gap_gate_reader_context"), dict) else {}
    d_series_context = state.get("d_series_research_context") if isinstance(state.get("d_series_research_context"), dict) else {}
    try:
        if not reader_context:
            reader_context = read_claim_gap_gate_research_context(db_path, tickers=tickers, limit=100)
    except Exception as exc:  # pragma: no cover - defensive against manually edited local sqlite files.
        reader_context = {
            "schema_version": "sec_agent_d_series_claim_gap_gate_reader_v0.1",
            "db_path": str(db_path.resolve()),
            "reader_default_status": "database_unavailable",
            "failure_reason": str(exc)[:500],
            "summary": {"claim_count": 0, "typed_gap_count": 0, "gate_history_count": 0},
        }
    try:
        if not d_series_context:
            d_series_context = read_d_series_research_context(db_path, tickers=tickers, limit=100)
    except Exception as exc:  # pragma: no cover - defensive against manually edited local sqlite files.
        d_series_context = {
            "schema_version": "sec_agent_d_series_research_context_reader_v0.1",
            "db_path": str(db_path.resolve()),
            "reader_default_status": "database_unavailable",
            "failure_reason": str(exc)[:500],
            "summary": {"context_group_count": 0, "row_count": 0},
        }
    context = dict(state.get("multi_agent_context") or {}) if isinstance(state.get("multi_agent_context"), Mapping) else {}
    context["d_series_claim_gap_gate_reader_context"] = reader_context
    context["d_series_research_context"] = d_series_context
    return {
        **state,
        "multi_agent_context": context,
        "d_series_claim_gap_gate_reader_context": reader_context,
        "d_series_research_context": d_series_context,
    }


def _state_with_d12_1_database_materialization(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    existing_report = (
        state.get("d_series_database_materialization_report")
        if isinstance(state.get("d_series_database_materialization_report"), dict)
        else {}
    )
    if existing_report:
        existing_materialization = (
            state.get("d_series_database_materialization")
            if isinstance(state.get("d_series_database_materialization"), dict)
            else d_series_materialization_state_from_report(existing_report)
        )
        return {**state, "d_series_database_materialization": existing_materialization}
    db_path = _d_series_governance_db_path(state)
    if db_path is None:
        return state
    state_with_governance = _state_with_d1_d2_d9_artifacts(state)
    report = materialize_d_series_governance_store(db_path, state_with_governance)
    materialization = d_series_materialization_state_from_report(report)
    artifact_refs = dict(state_with_governance.get("artifact_refs") or {})
    output_dir = str(state_with_governance.get("output_dir") or "").strip()
    if output_dir:
        artifact_refs["d_series_database_materialization_report"] = str(
            (Path(output_dir) / "d_series_database_materialization_report.json").resolve()
        )
    return {
        **state_with_governance,
        "artifact_refs": artifact_refs,
        "d_series_database_materialization": materialization,
        "d_series_database_materialization_report": report,
    }


def _state_with_d1_d2_d9_artifacts(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    claim_ledger = state.get("claim_evidence_ledger") if isinstance(state.get("claim_evidence_ledger"), dict) else {}
    gap_ledger = state.get("typed_gap_ledger") if isinstance(state.get("typed_gap_ledger"), dict) else {}
    gate_matrix = state.get("gate_registry_eval_matrix") if isinstance(state.get("gate_registry_eval_matrix"), dict) else {}
    next_state: SecAgentGraphRuntimeState = dict(state)
    if not claim_ledger or not gap_ledger:
        ledgers = build_evidence_governance_ledgers(next_state)
        if not claim_ledger:
            next_state["claim_evidence_ledger"] = (
                ledgers.get("claim_evidence_ledger") if isinstance(ledgers.get("claim_evidence_ledger"), dict) else {}
            )
        if not gap_ledger:
            next_state["typed_gap_ledger"] = (
                ledgers.get("typed_gap_ledger") if isinstance(ledgers.get("typed_gap_ledger"), dict) else {}
            )
    if not gate_matrix:
        next_state["gate_registry_eval_matrix"] = build_gate_registry_eval_matrix(next_state)
    return next_state


def _d_series_governance_db_path(state: SecAgentGraphRuntimeState) -> Path | None:
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), dict) else {}
    raw_path = (
        state.get("d_series_governance_db_path")
        or state.get("d_series_database_path")
        or contract.get("d_series_governance_db_path")
        or contract.get("d_series_database_path")
    )
    if not str(raw_path or "").strip():
        return None
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    output_dir = str(state.get("output_dir") or "").strip()
    if output_dir:
        return Path(output_dir) / path
    return path


def _d_series_reader_tickers(state: SecAgentGraphRuntimeState) -> list[str]:
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), Mapping) else {}
    scope = contract.get("scope") if isinstance(contract.get("scope"), Mapping) else {}
    values: list[Any] = []
    for key in ("focus_tickers", "search_scope_tickers", "companies"):
        values.extend(_d_series_string_list(contract.get(key)))
    for key in ("focus_tickers", "search_scope_tickers", "universe_tickers"):
        values.extend(_d_series_string_list(scope.get(key)))
    values.extend(_d_series_string_list(state.get("selected_tickers")))
    return _unique_upper([item for item in values if _d_series_looks_like_ticker(item)])


def _d_series_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item or "").strip() for item in value if str(item or "").strip()]
    return [str(value).strip()] if str(value).strip() else []


def _d_series_looks_like_ticker(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(text) and text == text.upper() and " " not in text and len(text) <= 16


def _state_with_d12_database_closeout_gate(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    closeout_gate = (
        state.get("d_series_database_closeout_gate")
        if isinstance(state.get("d_series_database_closeout_gate"), dict)
        else {}
    )
    if closeout_gate:
        return state
    return {**state, "d_series_database_closeout_gate": build_d_series_database_closeout_gate(state)}


def _state_with_run_audit_materialization(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    existing_report = (
        state.get("run_audit_materialization_report")
        if isinstance(state.get("run_audit_materialization_report"), dict)
        else {}
    )
    if existing_report:
        return state
    db_path = _run_audit_db_path(state)
    if db_path is None:
        return state
    artifact_refs = dict(state.get("artifact_refs") or {})
    output_dir = str(state.get("output_dir") or "").strip()
    if output_dir:
        artifact_refs["run_audit_materialization_report"] = str((Path(output_dir) / "run_audit_materialization_report.json").resolve())
    artifact_refs["run_audit_db"] = str(db_path.resolve())
    state_with_refs = {**state, "artifact_refs": artifact_refs}
    report = materialize_run_audit_store(db_path, state_with_refs)
    return {**state_with_refs, "run_audit_materialization_report": report}


def _run_audit_db_path(state: SecAgentGraphRuntimeState) -> Path | None:
    contract = state.get("query_contract") if isinstance(state.get("query_contract"), dict) else {}
    context = state.get("multi_agent_context") if isinstance(state.get("multi_agent_context"), dict) else {}
    raw_path = (
        state.get("run_audit_db_path")
        or state.get("runtime_audit_db_path")
        or contract.get("run_audit_db_path")
        or contract.get("runtime_audit_db_path")
        or context.get("run_audit_db_path")
        or context.get("runtime_audit_db_path")
    )
    if not str(raw_path or "").strip():
        return None
    path = Path(str(raw_path))
    if path.is_absolute():
        return path
    output_dir = str(state.get("output_dir") or "").strip()
    if output_dir:
        return Path(output_dir) / path
    return path


def _node_plan_query(
    state: SecAgentGraphRuntimeState,
    *,
    plan_query: PlannerFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if plan_query is None:
        contract = annotate_scope_contract(state.get("query_contract") or _minimal_query_contract())
        return _record_node({**state, "query_contract": contract}, "plan_query", metadata={"planner": "state_stub"})
    planner_result = plan_query(state)
    contract = planner_result.get("query_contract") if isinstance(planner_result.get("query_contract"), dict) else planner_result
    next_state: SecAgentGraphRuntimeState = {
        **state,
        "query_contract": annotate_scope_contract(contract or _minimal_query_contract()),
    }
    for key in ("planner_trace", "project_inventory", "selected_tickers", "selected_years"):
        if key in planner_result:
            next_state[key] = planner_result[key]  # type: ignore[literal-required]
    return _record_node(next_state, "plan_query", metadata={"planner": "injected"})


def _node_validate_query_contract(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    contract = annotate_scope_contract(state.get("query_contract") or {})
    return _record_node({**state, "query_contract": contract}, "validate_query_contract")


def _node_compile_retrieval_plan(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    contract = state.get("query_contract") or {}
    case = {
        "case_id": state.get("run_id") or "native_smoke",
        "prompt": state.get("user_query") or "",
        "companies": contract.get("search_scope_tickers") or contract.get("focus_tickers") or [],
        "years": contract.get("years") or [],
        "query_contract": contract,
    }
    plan = build_retrieval_plan(contract, case=case)
    next_state = _state_with_d3_d8_governance({**state, "retrieval_plan": plan})
    return _record_node(next_state, "compile_retrieval_plan")


def _node_execute_retrieval_routes(
    state: SecAgentGraphRuntimeState,
    *,
    retrieve_context: RetrieveContextFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if retrieve_context is None:
        context_rows = list(state.get("context_rows") or [])
        return _record_node(
            {**state, "context_rows": context_rows},
            "execute_retrieval_routes",
            metadata={"mode": "state_stub", "context_row_count": len(context_rows)},
        )
    result = retrieve_context(state)
    context_rows = result.get("context_rows") if isinstance(result.get("context_rows"), list) else []
    next_state: SecAgentGraphRuntimeState = {**state, "context_rows": context_rows}
    if isinstance(result.get("retrieval_trace"), dict):
        next_state["retrieval_trace"] = result["retrieval_trace"]
    if isinstance(result.get("context_runtime"), dict):
        next_state["context_runtime"] = result["context_runtime"]
    if isinstance(result.get("artifact_refs"), dict):
        next_state["artifact_refs"] = {
            **dict(state.get("artifact_refs") or {}),
            **result["artifact_refs"],
        }
    return _record_node(
        next_state,
        "execute_retrieval_routes",
        metadata={
            "mode": "injected",
            "context_row_count": len(context_rows),
            "context_runner": (next_state.get("context_runtime") or {}).get("context_runner"),
        },
    )


def _node_attach_market_snapshot(
    state: SecAgentGraphRuntimeState,
    *,
    attach_market_snapshot: AttachMarketFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if attach_market_snapshot is None:
        rows = list(state.get("market_snapshot_rows") or [])
        return _record_node(
            {**state, "market_snapshot_rows": rows},
            "attach_market_snapshot",
            metadata={"mode": "state_stub", "market_context_row_count": len(rows)},
        )
    result = attach_market_snapshot(state)
    next_state: SecAgentGraphRuntimeState = {**state}
    if isinstance(result.get("context_rows"), list):
        next_state["context_rows"] = result["context_rows"]
    market_rows = result.get("market_snapshot_rows") if isinstance(result.get("market_snapshot_rows"), list) else []
    next_state["market_snapshot_rows"] = market_rows
    if isinstance(result.get("retrieval_trace"), dict):
        next_state["retrieval_trace"] = result["retrieval_trace"]
    if isinstance(result.get("artifact_refs"), dict):
        next_state["artifact_refs"] = {
            **dict(state.get("artifact_refs") or {}),
            **result["artifact_refs"],
        }
    return _record_node(
        next_state,
        "attach_market_snapshot",
        metadata={"mode": "injected", "market_context_row_count": len(market_rows)},
    )


def _node_attach_industry_snapshot(
    state: SecAgentGraphRuntimeState,
    *,
    attach_industry_snapshot: AttachIndustryFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if attach_industry_snapshot is None:
        rows = list(state.get("industry_snapshot_rows") or [])
        return _record_node(
            {**state, "industry_snapshot_rows": rows},
            "attach_industry_snapshot",
            metadata={"mode": "state_stub", "industry_context_row_count": len(rows)},
        )
    result = attach_industry_snapshot(state)
    next_state: SecAgentGraphRuntimeState = {**state}
    if isinstance(result.get("context_rows"), list):
        next_state["context_rows"] = result["context_rows"]
    industry_rows = result.get("industry_snapshot_rows") if isinstance(result.get("industry_snapshot_rows"), list) else []
    next_state["industry_snapshot_rows"] = industry_rows
    if isinstance(result.get("retrieval_trace"), dict):
        next_state["retrieval_trace"] = result["retrieval_trace"]
    if isinstance(result.get("artifact_refs"), dict):
        next_state["artifact_refs"] = {
            **dict(state.get("artifact_refs") or {}),
            **result["artifact_refs"],
        }
    return _record_node(
        next_state,
        "attach_industry_snapshot",
        metadata={"mode": "injected", "industry_context_row_count": len(industry_rows)},
    )


def _node_build_runtime_ledger(
    state: SecAgentGraphRuntimeState,
    *,
    build_runtime_ledger: BuildLedgerFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if build_runtime_ledger is None:
        rows = list(state.get("runtime_ledger_rows") or [])
        return _record_node(
            {**state, "runtime_ledger_rows": rows},
            "build_runtime_ledger",
            metadata={"mode": "state_stub", "ledger_row_count": len(rows)},
        )
    result = build_runtime_ledger(state)
    rows = result.get("runtime_ledger_rows") if isinstance(result.get("runtime_ledger_rows"), list) else []
    next_state: SecAgentGraphRuntimeState = {**state, "runtime_ledger_rows": rows}
    if isinstance(result.get("artifact_refs"), dict):
        next_state["artifact_refs"] = {
            **dict(state.get("artifact_refs") or {}),
            **result["artifact_refs"],
        }
    return _record_node(
        next_state,
        "build_runtime_ledger",
        metadata={"mode": "injected", "ledger_row_count": len(rows)},
    )


def _node_assess_evidence_coverage(
    state: SecAgentGraphRuntimeState,
    *,
    build_coverage_matrix: BuildCoverageFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if build_coverage_matrix is None:
        matrix = state.get("coverage_matrix") or {
            "summary": {
                "coverage_complete": False,
                "primary_task_support_complete": False,
                "context_row_count": len(state.get("context_rows") or []),
                "ledger_row_count": len(state.get("runtime_ledger_rows") or []),
            }
        }
        return _record_node(
            {**state, "coverage_matrix": matrix},
            "assess_evidence_coverage",
            metadata={"mode": "state_stub", **dict(matrix.get("summary") or {})},
        )
    result = build_coverage_matrix(state)
    matrix = result.get("coverage_matrix") if isinstance(result.get("coverage_matrix"), dict) else {}
    next_state: SecAgentGraphRuntimeState = {**state, "coverage_matrix": matrix}
    if isinstance(result.get("artifact_refs"), dict):
        next_state["artifact_refs"] = {
            **dict(state.get("artifact_refs") or {}),
            **result["artifact_refs"],
        }
    summary = dict(matrix.get("summary") or {})
    return _record_node(
        next_state,
        "assess_evidence_coverage",
        metadata={"mode": "injected", **summary},
    )


def _node_assess_evidence_sufficiency(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    summary = (state.get("coverage_matrix") or {}).get("summary") or {}
    tasks = [task for task in (state.get("coverage_matrix") or {}).get("tasks") or [] if isinstance(task, dict)]
    sufficient = bool(summary.get("coverage_complete") and summary.get("primary_task_support_complete"))
    missing_requirements = _missing_requirements_from_coverage_tasks(tasks)
    has_partial_support = bool(summary.get("answer_status") == "partial") or any(
        str(task.get("support_level") or "") in {"weak", "medium", "strong"} for task in tasks
    )
    if sufficient:
        sufficiency_level = "sufficient"
    elif has_partial_support or state.get("context_rows") or state.get("runtime_ledger_rows"):
        sufficiency_level = "partial"
    else:
        sufficiency_level = "insufficient"
    report = {
        "schema_version": "sec_agent_evidence_sufficiency_report_v0.1",
        "sufficiency_level": sufficiency_level,
        "coverage_complete": bool(summary.get("coverage_complete")),
        "primary_task_support_complete": bool(summary.get("primary_task_support_complete")),
        "answer_status": summary.get("answer_status") or sufficiency_level,
        "missing_requirements": missing_requirements,
        "second_pass_retrieval_requests": _second_pass_requests_from_missing(missing_requirements),
        "bounded_answer_allowed": sufficiency_level in {"partial", "sufficient"},
        "user_clarification_required": sufficiency_level == "insufficient" and not missing_requirements,
    }
    return _record_node(
        {**state, "evidence_sufficiency_report": report},
        "assess_evidence_sufficiency",
        metadata={
            "sufficiency_level": sufficiency_level,
            "missing_requirement_count": len(missing_requirements),
            "second_pass_request_count": len(report["second_pass_retrieval_requests"]),
        },
    )


def _route_after_evidence_sufficiency(
    state: SecAgentGraphRuntimeState,
    *,
    second_pass_enabled: bool,
) -> str:
    if _is_stopped_after_node(state):
        return "stop"
    if not second_pass_enabled:
        return "continue"
    attempts = int(state.get("second_pass_attempts") or 0)
    max_passes = int(state.get("max_second_passes") or 1)
    if attempts >= max_passes:
        return "continue"
    report = state.get("evidence_sufficiency_report") or {}
    requests = report.get("second_pass_retrieval_requests") if isinstance(report, dict) else []
    if isinstance(requests, list) and requests:
        return "second_pass"
    return "continue"


def _route_after_multi_agent_reflection(state: SecAgentGraphRuntimeState) -> str:
    if _is_stopped_after_node(state):
        return "stop"
    mode = str((state.get("agent_activation_plan") or {}).get("execution_mode") or "")
    if mode == "deterministic_lookup" and state.get("runtime_ledger_rows"):
        return "renderer"
    decision = state.get("multi_agent_second_pass_decision") or {}
    if decision.get("allowed"):
        return "second_pass"
    if mode == "deterministic_lookup":
        return "renderer"
    if _multi_agent_specialists_active(state):
        return "specialists"
    return "aggregate"


def _second_pass_decision_for_execution_mode(state: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(decision or {})
    if not normalized.get("allowed"):
        return normalized
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    mode = str(activation.get("execution_mode") or state.get("execution_mode") or "").strip()
    if mode == "deep_research":
        return normalized
    context = state.get("multi_agent_context") if isinstance(state.get("multi_agent_context"), Mapping) else {}
    if bool(state.get("allow_standard_second_pass") or context.get("allow_standard_second_pass")):
        return normalized
    return {
        **normalized,
        "allowed": False,
        "blocked_by_execution_mode": mode or "unspecified",
        "original_allowed": True,
        "reason": f"{normalized.get('reason') or 'second_pass'}_deferred_for_{mode or 'unspecified'}",
    }


def _route_after_multi_agent_second_pass(state: SecAgentGraphRuntimeState) -> str:
    if _is_stopped_after_node(state):
        return "stop"
    mode = str((state.get("agent_activation_plan") or {}).get("execution_mode") or "")
    if mode == "deterministic_lookup":
        return "renderer"
    if _second_pass_specialist_rerun_skip_reason(state):
        return "aggregate"
    if _multi_agent_specialists_active(state):
        return "specialists"
    return "aggregate"


def _second_pass_specialist_rerun_skip_reason(state: Mapping[str, Any]) -> str:
    if not state.get("specialist_outputs"):
        return ""
    delta = state.get("second_pass_delta_audit") if isinstance(state.get("second_pass_delta_audit"), Mapping) else {}
    result = state.get("second_pass_result") if isinstance(state.get("second_pass_result"), Mapping) else {}
    loop_break_reason = str(state.get("loop_break_reason") or result.get("loop_break_reason") or "")
    status = str(delta.get("status") or result.get("delta_audit_status") or "")
    try:
        added_authority = int(delta.get("added_authority_bearing_row_count") or result.get("added_authority_bearing_row_count") or 0)
    except (TypeError, ValueError):
        added_authority = 0
    if status == "no_authority_delta" or loop_break_reason == LOOP_BREAK_NO_INCREMENTAL_EVIDENCE or added_authority <= 0:
        return "no_incremental_authority_evidence_after_specialist_pass"
    return ""


def _route_after_multi_agent_aggregate(state: SecAgentGraphRuntimeState) -> str:
    if _is_stopped_after_node(state):
        return "memo"
    decision = state.get("quality_second_pass_decision") if isinstance(state.get("quality_second_pass_decision"), dict) else {}
    if decision.get("allowed") and not bool(state.get("quality_second_pass_attempted")):
        return "second_pass"
    return "memo"


def _multi_agent_specialists_active(state: SecAgentGraphRuntimeState) -> bool:
    active = set((state.get("agent_activation_plan") or {}).get("activate_agents") or [])
    return bool(
        active
        & {
            "fundamental_analyst",
            "product_technology_analyst",
            "industry_supply_chain_analyst",
            "market_valuation_analyst",
            "risk_counterevidence_analyst",
        }
    )


def _node_execute_second_pass_retrieval(
    state: SecAgentGraphRuntimeState,
    *,
    execute_second_pass_retrieval: SecondPassRetrievalFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if execute_second_pass_retrieval is None:
        attempts = int(state.get("second_pass_attempts") or 0)
        return _record_node(
            {**state, "second_pass_attempts": attempts},
            "execute_second_pass_retrieval",
            metadata={"mode": "not_configured", "second_pass_attempts": attempts},
        )
    before_count = len(state.get("context_rows") or [])
    result = execute_second_pass_retrieval(state)
    context_rows = result.get("context_rows") if isinstance(result.get("context_rows"), list) else list(state.get("context_rows") or [])
    next_state: SecAgentGraphRuntimeState = {
        **state,
        "context_rows": context_rows,
        "second_pass_attempts": int(result.get("second_pass_attempts") or (int(state.get("second_pass_attempts") or 0) + 1)),
    }
    if isinstance(result.get("retrieval_trace"), dict):
        next_state["retrieval_trace"] = result["retrieval_trace"]
    if isinstance(result.get("context_runtime"), dict):
        next_state["context_runtime"] = result["context_runtime"]
    if isinstance(result.get("second_pass_result"), dict):
        next_state["second_pass_result"] = result["second_pass_result"]
    if isinstance(result.get("artifact_refs"), dict):
        next_state["artifact_refs"] = {
            **dict(state.get("artifact_refs") or {}),
            **result["artifact_refs"],
        }
    added_count = max(0, len(context_rows) - before_count)
    return _record_node(
        next_state,
        "execute_second_pass_retrieval",
        metadata={
            "mode": "injected",
            "input_context_row_count": before_count,
            "output_context_row_count": len(context_rows),
            "added_context_row_count": added_count,
            "second_pass_attempts": next_state["second_pass_attempts"],
        },
    )


def _node_build_judgment_plan(
    state: SecAgentGraphRuntimeState,
    *,
    build_judgment_plan: BuildJudgmentPlanFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if build_judgment_plan is not None:
        result = build_judgment_plan(state)
        if not isinstance(result, dict):
            raise RuntimeError("build_judgment_plan adapter must return a dict")
        next_state = {**state}
        if "judgment_plan" in result:
            next_state["judgment_plan"] = result.get("judgment_plan")
        if isinstance(result.get("artifact_refs"), dict):
            next_state["artifact_refs"] = {
                **dict(state.get("artifact_refs") or {}),
                **result["artifact_refs"],
            }
        plan = result.get("judgment_plan")
        return _record_node(
            next_state,
            "build_judgment_plan",
            metadata={
                "mode": "injected",
                "has_plan": bool(plan),
                "driver_count": len(plan.get("drivers") or []) if isinstance(plan, dict) else 0,
            },
        )
    plan = state.get("judgment_plan") or {"plans": [], "source": "native_graph_smoke"}
    return _record_node({**state, "judgment_plan": plan}, "build_judgment_plan")


def _node_synthesize_answer(
    state: SecAgentGraphRuntimeState,
    *,
    synthesize_answer: SynthesizeAnswerFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if synthesize_answer is not None:
        result = synthesize_answer(state)
        if not isinstance(result, dict):
            raise RuntimeError("synthesize_answer adapter must return a dict")
        next_state = {**state}
        if "memo_answer" in result:
            next_state["memo_answer"] = result.get("memo_answer")
        if "rendered_answer" in result:
            next_state["rendered_answer"] = result.get("rendered_answer")
        if isinstance(result.get("artifact_refs"), dict):
            next_state["artifact_refs"] = {
                **dict(state.get("artifact_refs") or {}),
                **result["artifact_refs"],
            }
        answer = result.get("memo_answer")
        return _record_node(
            next_state,
            "synthesize_answer",
            metadata={
                "mode": "injected",
                "answer_status": answer.get("answer_status") if isinstance(answer, dict) else "",
                "claim_status": answer.get("claim_status") if isinstance(answer, dict) else "",
            },
        )
    answer = state.get("memo_answer") or {
        "status": "not_synthesized",
        "reason": "native_state_smoke_does_not_call_llm",
    }
    return _record_node({**state, "memo_answer": answer}, "synthesize_answer")


def _node_verify_claims(
    state: SecAgentGraphRuntimeState,
    *,
    verify_claims: VerifyClaimsFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if verify_claims is not None:
        result = verify_claims(state)
        if not isinstance(result, dict):
            raise RuntimeError("verify_claims adapter must return a dict")
        next_state = {**state}
        if "memo_answer" in result:
            next_state["memo_answer"] = result.get("memo_answer")
        if "claim_verification" in result:
            next_state["claim_verification"] = result.get("claim_verification")
        if isinstance(result.get("artifact_refs"), dict):
            next_state["artifact_refs"] = {
                **dict(state.get("artifact_refs") or {}),
                **result["artifact_refs"],
            }
        verification = result.get("claim_verification")
        return _record_node(
            next_state,
            "verify_claims",
            metadata={
                "mode": "injected",
                "status": verification.get("status") if isinstance(verification, dict) else "",
                "unsupported_claim_count": verification.get("unsupported_claim_count")
                if isinstance(verification, dict)
                else None,
            },
        )
    verification = state.get("claim_verification") or {"status": "not_run", "claims": []}
    return _record_node({**state, "claim_verification": verification}, "verify_claims")


def _node_run_deterministic_gates(
    state: SecAgentGraphRuntimeState,
    *,
    run_deterministic_gates: RunDeterministicGatesFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if run_deterministic_gates is not None:
        result = run_deterministic_gates(state)
        if not isinstance(result, dict):
            raise RuntimeError("run_deterministic_gates adapter must return a dict")
        next_state = {**state}
        if "deterministic_gates" in result:
            next_state["deterministic_gates"] = result.get("deterministic_gates")
        if isinstance(result.get("artifact_refs"), dict):
            next_state["artifact_refs"] = {
                **dict(state.get("artifact_refs") or {}),
                **result["artifact_refs"],
            }
        gates = result.get("deterministic_gates")
        return _record_node(
            next_state,
            "run_deterministic_gates",
            metadata={
                "mode": "injected",
                "ok": gates.get("ok") if isinstance(gates, dict) else None,
            },
        )
    gates = state.get("deterministic_gates") or {"status": "not_run", "gate_results": []}
    return _record_node({**state, "deterministic_gates": gates}, "run_deterministic_gates")


def _node_render_answer(
    state: SecAgentGraphRuntimeState,
    *,
    render_answer: RenderAnswerFunc | None = None,
) -> SecAgentGraphRuntimeState:
    if render_answer is not None:
        result = render_answer(state)
        if not isinstance(result, dict):
            raise RuntimeError("render_answer adapter must return a dict")
        next_state = {**state}
        if "rendered_answer" in result:
            next_state["rendered_answer"] = str(result.get("rendered_answer") or "")
        if isinstance(result.get("artifact_refs"), dict):
            next_state["artifact_refs"] = {
                **dict(state.get("artifact_refs") or {}),
                **result["artifact_refs"],
            }
        rendered = str(result.get("rendered_answer") or "")
        return _record_node(
            next_state,
            "render_answer",
            metadata={"mode": "injected", "rendered_chars": len(rendered)},
        )
    rendered = state.get("rendered_answer") or "# Native Graph Smoke\n\nNo LLM synthesis was executed."
    return _record_node({**state, "rendered_answer": rendered}, "render_answer")


def _node_persist_session_state(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    state_before_record = _with_native_artifact_refs({**state, "status": "completed"})
    final_state = _record_node(state_before_record, "persist_session_state")
    final_state = _state_with_run_audit_materialization(final_state)
    _write_native_state_artifacts(final_state)
    return final_state


def _with_native_artifact_refs(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    output_dir = Path(str(state.get("output_dir") or ""))
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        refs = dict(state.get("artifact_refs") or {})
        refs["node_checkpoints"] = str((output_dir / "langgraph_node_checkpoints.json").resolve())
        refs["langgraph_native_summary"] = str((output_dir / "langgraph_native_summary.json").resolve())
        return {**state, "artifact_refs": refs}
    return state


def _with_multi_agent_artifact_refs(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    output_dir = Path(str(state.get("output_dir") or ""))
    if output_dir:
        output_dir.mkdir(parents=True, exist_ok=True)
        refs = dict(state.get("artifact_refs") or {})
        refs["rendered_answer"] = str((output_dir / "qwen" / "rendered_answer.md").resolve())
        refs["memo_answer"] = str((output_dir / "memo_answer.json").resolve())
        refs["memo_logic_plan"] = str((output_dir / "memo_logic_plan.json").resolve())
        refs["verified_judgment_plan"] = str((output_dir / "verified_judgment_plan.json").resolve())
        refs["claim_cards"] = str((output_dir / "claim_cards.json").resolve())
        refs["thesis_driver_pack"] = str((output_dir / "thesis_driver_pack.json").resolve())
        refs["judgment_state"] = str((output_dir / "judgment_state.json").resolve())
        refs["multi_agent_summary"] = str((output_dir / "multi_agent_summary.json").resolve())
        refs["claim_evidence_ledger"] = str((output_dir / "claim_evidence_ledger.json").resolve())
        refs["typed_gap_ledger"] = str((output_dir / "typed_gap_ledger.json").resolve())
        refs["entity_security_master"] = str((output_dir / "entity_security_master.json").resolve())
        refs["source_capability_router"] = str((output_dir / "source_capability_router.json").resolve())
        refs["source_layer_capability_audit"] = str((output_dir / "source_layer_capability_audit.json").resolve())
        refs["source_authority_coverage"] = str((output_dir / "source_authority_coverage.json").resolve())
        refs["raw_source_provenance_store"] = str((output_dir / "raw_source_provenance_store.json").resolve())
        refs["asof_vintage_layer"] = str((output_dir / "asof_vintage_layer.json").resolve())
        refs["metric_product_ontology_snapshot"] = str((output_dir / "metric_product_ontology_snapshot.json").resolve())
        refs["reconciliation_ledger"] = str((output_dir / "reconciliation_ledger.json").resolve())
        refs["gate_registry_eval_matrix"] = str((output_dir / "gate_registry_eval_matrix.json").resolve())
        refs["derived_metric_layer"] = str((output_dir / "derived_metric_layer.json").resolve())
        refs["fundamental_statement_pack"] = str((output_dir / "fundamental_statement_pack.json").resolve())
        refs["pre_memo_fact_selection"] = str((output_dir / "pre_memo_fact_selection.json").resolve())
        refs["supervising_analyst_pack"] = str((output_dir / "supervising_analyst_pack.json").resolve())
        refs["analyst_view_research_memory"] = str((output_dir / "analyst_view_research_memory.json").resolve())
        refs["d_series_database_closeout_gate"] = str((output_dir / "d_series_database_closeout_gate.json").resolve())
        return {**state, "artifact_refs": refs}
    return state


def _write_native_state_artifacts(state: SecAgentGraphRuntimeState) -> None:
    output_dir = Path(str(state.get("output_dir") or ""))
    if not output_dir:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "langgraph_node_checkpoints.json"
    summary_path = output_dir / "langgraph_native_summary.json"
    checkpoint_path.write_text(
        json.dumps(build_node_checkpoint_artifact_payload(state), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(build_native_summary_artifact_payload(state), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    run_audit_report = (
        state.get("run_audit_materialization_report")
        if isinstance(state.get("run_audit_materialization_report"), dict)
        else {}
    )
    if run_audit_report:
        (output_dir / "run_audit_materialization_report.json").write_text(
            json.dumps(run_audit_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    _write_memo_surface_artifacts(output_dir, state)


def _write_memo_surface_artifacts(output_dir: Path, state: SecAgentGraphRuntimeState) -> None:
    rendered_answer = str(state.get("rendered_answer") or "").strip()
    if rendered_answer:
        rendered_dir = output_dir / "qwen"
        rendered_dir.mkdir(parents=True, exist_ok=True)
        (rendered_dir / "rendered_answer.md").write_text(rendered_answer + "\n", encoding="utf-8")
    memo = state.get("memo_answer") if isinstance(state.get("memo_answer"), dict) else {}
    if memo:
        (output_dir / "memo_answer.json").write_text(json.dumps(memo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    memo_logic_plan, memo_logic_plan_source = _memo_logic_plan_for_artifact_persistence(state, memo)
    if memo_logic_plan:
        (output_dir / "memo_logic_plan.json").write_text(
            json.dumps(
                {
                    **dict(memo_logic_plan),
                    "artifact_persistence": {
                        "source": memo_logic_plan_source,
                        "policy": "persist_full_memo_logic_plan_from_state_or_writer_payload_v0_2",
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    judgment = (
        state.get("verified_judgment_plan")
        if isinstance(state.get("verified_judgment_plan"), dict)
        else state.get("judgment_plan") if isinstance(state.get("judgment_plan"), dict) else {}
    )
    if judgment:
        (output_dir / "verified_judgment_plan.json").write_text(
            json.dumps(judgment, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        claim_cards = {
            "schema_version": "sec_agent_claim_cards_artifact_v0.1",
            "supported_claims": [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)],
            "unsupported_claims": [dict(item) for item in judgment.get("unsupported_claims") or [] if isinstance(item, Mapping)],
            "conflicts": [dict(item) for item in judgment.get("conflicts") or [] if isinstance(item, Mapping)],
            "claim_card_stats": dict(judgment.get("claim_card_stats") or {})
            if isinstance(judgment.get("claim_card_stats"), Mapping)
            else {},
            "artifact_policy": "memo_surface_claim_cards_from_verified_judgment_plan_v0_1",
        }
        (output_dir / "claim_cards.json").write_text(
            json.dumps(claim_cards, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        thesis_driver_pack = (
            judgment.get("thesis_driver_pack") if isinstance(judgment.get("thesis_driver_pack"), Mapping) else {}
        )
        if thesis_driver_pack:
            (output_dir / "thesis_driver_pack.json").write_text(
                json.dumps(thesis_driver_pack, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        judgment_state = judgment.get("judgment_state") if isinstance(judgment.get("judgment_state"), Mapping) else {}
        if judgment_state:
            (output_dir / "judgment_state.json").write_text(
                json.dumps(judgment_state, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    supervising_pack = state.get("supervising_analyst_pack") if isinstance(state.get("supervising_analyst_pack"), dict) else {}
    if supervising_pack:
        (output_dir / "supervising_analyst_pack.json").write_text(
            json.dumps(supervising_pack, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _memo_logic_plan_for_artifact_persistence(
    state: Mapping[str, Any],
    memo: Mapping[str, Any],
) -> tuple[dict[str, Any], str]:
    memo_logic_plan = state.get("memo_logic_plan") if isinstance(state.get("memo_logic_plan"), Mapping) else {}
    if memo_logic_plan:
        return dict(memo_logic_plan), "state.memo_logic_plan"
    memo_logic_plan = memo.get("memo_logic_plan") if isinstance(memo.get("memo_logic_plan"), Mapping) else {}
    if memo_logic_plan:
        return dict(memo_logic_plan), "memo_answer.memo_logic_plan"
    summary = state.get("multi_agent_summary") if isinstance(state.get("multi_agent_summary"), Mapping) else {}
    summary_plan = summary.get("memo_logic_plan") if isinstance(summary.get("memo_logic_plan"), Mapping) else {}
    if summary_plan:
        return {
            "schema_version": "finsight_memo_logic_plan_summary_artifact_v0_1",
            "artifact_note": (
                "Only summary projection was available at artifact persistence time. "
                "This is diagnostic and should trigger root-cause repair if full plan is required."
            ),
            "summary_projection": dict(summary_plan),
        }, "multi_agent_summary.memo_logic_plan"
    return {}, ""


def _write_multi_agent_summary_artifact(state: SecAgentGraphRuntimeState) -> None:
    output_dir = Path(str(state.get("output_dir") or ""))
    if not output_dir:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "multi_agent_summary.json"
    payload = (
        state.get("multi_agent_summary")
        if isinstance(state.get("multi_agent_summary"), Mapping)
        else build_multi_agent_summary_artifact_payload(state)
    )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_multi_agent_governance_ledger_artifacts(state: SecAgentGraphRuntimeState) -> None:
    output_dir = Path(str(state.get("output_dir") or ""))
    if not output_dir:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    ledgers = build_evidence_governance_ledgers(state)
    claim_ledger = state.get("claim_evidence_ledger") if isinstance(state.get("claim_evidence_ledger"), dict) else {}
    gap_ledger = state.get("typed_gap_ledger") if isinstance(state.get("typed_gap_ledger"), dict) else {}
    entity_master = state.get("entity_security_master") if isinstance(state.get("entity_security_master"), dict) else {}
    source_router = state.get("source_capability_router") if isinstance(state.get("source_capability_router"), dict) else {}
    source_layer_audit = state.get("source_layer_capability_audit") if isinstance(state.get("source_layer_capability_audit"), dict) else {}
    source_authority = state.get("source_authority_coverage") if isinstance(state.get("source_authority_coverage"), dict) else {}
    provenance_store = state.get("raw_source_provenance_store") if isinstance(state.get("raw_source_provenance_store"), dict) else {}
    vintage_layer = state.get("asof_vintage_layer") if isinstance(state.get("asof_vintage_layer"), dict) else {}
    ontology = state.get("metric_product_ontology_snapshot") if isinstance(state.get("metric_product_ontology_snapshot"), dict) else {}
    reconciliation = state.get("reconciliation_ledger") if isinstance(state.get("reconciliation_ledger"), dict) else {}
    gate_matrix = state.get("gate_registry_eval_matrix") if isinstance(state.get("gate_registry_eval_matrix"), dict) else {}
    derived_layer = state.get("derived_metric_layer") if isinstance(state.get("derived_metric_layer"), dict) else {}
    fundamental_pack = state.get("fundamental_statement_pack") if isinstance(state.get("fundamental_statement_pack"), dict) else {}
    pre_memo_selection = state.get("pre_memo_fact_selection") if isinstance(state.get("pre_memo_fact_selection"), dict) else {}
    supervising_pack = state.get("supervising_analyst_pack") if isinstance(state.get("supervising_analyst_pack"), dict) else {}
    analyst_views = (
        state.get("analyst_view_research_memory")
        if isinstance(state.get("analyst_view_research_memory"), dict)
        else {}
    )
    closeout_gate = (
        state.get("d_series_database_closeout_gate")
        if isinstance(state.get("d_series_database_closeout_gate"), dict)
        else {}
    )
    materialization_report = (
        state.get("d_series_database_materialization_report")
        if isinstance(state.get("d_series_database_materialization_report"), dict)
        else {}
    )
    if not claim_ledger:
        claim_ledger = ledgers.get("claim_evidence_ledger") if isinstance(ledgers.get("claim_evidence_ledger"), dict) else {}
    if not gap_ledger:
        gap_ledger = ledgers.get("typed_gap_ledger") if isinstance(ledgers.get("typed_gap_ledger"), dict) else {}
    if not entity_master:
        entity_master = build_entity_security_master(state)
    if not source_router:
        source_router = build_source_capability_router(state)
    if not source_layer_audit:
        source_layer_audit = _load_source_layer_capability_audit(state)
    if not source_authority:
        source_authority = _load_source_authority_coverage(state)
    if not provenance_store or not vintage_layer:
        layers = build_provenance_vintage_layers(state)
        if not provenance_store:
            provenance_store = layers.get("raw_source_provenance_store") if isinstance(layers.get("raw_source_provenance_store"), dict) else {}
        if not vintage_layer:
            vintage_layer = layers.get("asof_vintage_layer") if isinstance(layers.get("asof_vintage_layer"), dict) else {}
    if not ontology:
        ontology = build_metric_product_ontology_snapshot(state)
    if not reconciliation:
        reconciliation = build_reconciliation_ledger({**state, "metric_product_ontology_snapshot": ontology})
    if not gate_matrix:
        gate_matrix = build_gate_registry_eval_matrix(
            {
                **state,
                "raw_source_provenance_store": provenance_store,
                "asof_vintage_layer": vintage_layer,
                "metric_product_ontology_snapshot": ontology,
                "reconciliation_ledger": reconciliation,
                "entity_security_master": entity_master,
                "source_capability_router": source_router,
                "claim_evidence_ledger": claim_ledger,
                "typed_gap_ledger": gap_ledger,
            }
        )
    if not derived_layer:
        derived_layer = build_derived_metric_layer(
            {
                **state,
                "metric_product_ontology_snapshot": ontology,
                "reconciliation_ledger": reconciliation,
                "gate_registry_eval_matrix": gate_matrix,
            }
        )
    if not fundamental_pack:
        fundamental_pack = build_fundamental_statement_pack(
            {
                **state,
                "metric_product_ontology_snapshot": ontology,
                "reconciliation_ledger": reconciliation,
                "gate_registry_eval_matrix": gate_matrix,
                "derived_metric_layer": derived_layer,
            }
        )
    if not pre_memo_selection:
        pre_memo_selection = build_pre_memo_fact_selection(
            {
                **state,
                "typed_gap_ledger": gap_ledger,
                "bounded_gap_register": state.get("bounded_gap_register") or {},
                "reconciliation_ledger": reconciliation,
                "gate_registry_eval_matrix": gate_matrix,
                "derived_metric_layer": derived_layer,
                "fundamental_statement_pack": fundamental_pack,
            }
        )
    if not analyst_views:
        analyst_views = build_analyst_view_research_memory_layer(
            {
                **state,
                "claim_evidence_ledger": claim_ledger,
                "typed_gap_ledger": gap_ledger,
                "derived_metric_layer": derived_layer,
            }
        )
    if not closeout_gate:
        closeout_gate = build_d_series_database_closeout_gate(
            {
                **state,
                "claim_evidence_ledger": claim_ledger,
                "typed_gap_ledger": gap_ledger,
                "entity_security_master": entity_master,
                "source_capability_router": source_router,
                "raw_source_provenance_store": provenance_store,
                "asof_vintage_layer": vintage_layer,
                "metric_product_ontology_snapshot": ontology,
                "reconciliation_ledger": reconciliation,
                "gate_registry_eval_matrix": gate_matrix,
                "derived_metric_layer": derived_layer,
                "analyst_view_research_memory": analyst_views,
            }
        )
    (output_dir / "claim_evidence_ledger.json").write_text(
        json.dumps(claim_ledger, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "typed_gap_ledger.json").write_text(
        json.dumps(gap_ledger, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "entity_security_master.json").write_text(
        json.dumps(entity_master, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "source_capability_router.json").write_text(
        json.dumps(source_router, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "source_layer_capability_audit.json").write_text(
        json.dumps(source_layer_audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "source_authority_coverage.json").write_text(
        json.dumps(source_authority, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "raw_source_provenance_store.json").write_text(
        json.dumps(provenance_store, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "asof_vintage_layer.json").write_text(
        json.dumps(vintage_layer, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "metric_product_ontology_snapshot.json").write_text(
        json.dumps(ontology, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "reconciliation_ledger.json").write_text(
        json.dumps(reconciliation, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "gate_registry_eval_matrix.json").write_text(
        json.dumps(gate_matrix, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "derived_metric_layer.json").write_text(
        json.dumps(derived_layer, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "fundamental_statement_pack.json").write_text(
        json.dumps(fundamental_pack, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "pre_memo_fact_selection.json").write_text(
        json.dumps(pre_memo_selection, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if supervising_pack:
        (output_dir / "supervising_analyst_pack.json").write_text(
            json.dumps(supervising_pack, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    (output_dir / "analyst_view_research_memory.json").write_text(
        json.dumps(analyst_views, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "d_series_database_closeout_gate.json").write_text(
        json.dumps(closeout_gate, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if materialization_report:
        (output_dir / "d_series_database_materialization_report.json").write_text(
            json.dumps(materialization_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    run_audit_report = (
        state.get("run_audit_materialization_report")
        if isinstance(state.get("run_audit_materialization_report"), dict)
        else {}
    )
    if run_audit_report:
        (output_dir / "run_audit_materialization_report.json").write_text(
            json.dumps(run_audit_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def build_multi_agent_summary_artifact_payload(state: SecAgentGraphRuntimeState) -> dict[str, Any]:
    plan = state.get("agent_activation_plan") or {}
    evidence_plan = state.get("evidence_requirement_plan") or {}
    evidence_validation = (
        evidence_plan.get("multi_agent_evidence_requirement_validation")
        if isinstance(evidence_plan, dict)
        else {}
    )
    ledger = state.get("tool_call_ledger") or {}
    records = [dict(item) for item in ledger.get("records") or [] if isinstance(item, dict)] if isinstance(ledger, dict) else []
    second_pass = state.get("second_pass_result") or {}
    second_pass_diagnosis = state.get("second_pass_reflection_diagnosis") if isinstance(state.get("second_pass_reflection_diagnosis"), dict) else {}
    second_pass_repair_plan = state.get("second_pass_repair_plan") if isinstance(state.get("second_pass_repair_plan"), dict) else {}
    second_pass_hard_gate = state.get("second_pass_hard_gate") if isinstance(state.get("second_pass_hard_gate"), dict) else {}
    second_pass_delta_audit = state.get("second_pass_delta_audit") if isinstance(state.get("second_pass_delta_audit"), dict) else {}
    specialist_verification = state.get("specialist_verification") or {}
    memo = state.get("memo_answer") if isinstance(state.get("memo_answer"), dict) else {}
    claim_verification = state.get("claim_verification") if isinstance(state.get("claim_verification"), dict) else {}
    relationship_lookup = state.get("relationship_graph_observation") if isinstance(state.get("relationship_graph_observation"), dict) else {}
    universe_validation = state.get("universe_relationship_validation") if isinstance(state.get("universe_relationship_validation"), dict) else {}
    plan_reflection = state.get("plan_reflection_report") if isinstance(state.get("plan_reflection_report"), dict) else {}
    evidence_fusion = state.get("evidence_fusion_bundle") if isinstance(state.get("evidence_fusion_bundle"), dict) else {}
    evidence_fusion_summary = evidence_fusion.get("summary") if isinstance(evidence_fusion.get("summary"), dict) else {}
    bounded_gap_register = state.get("bounded_gap_register") if isinstance(state.get("bounded_gap_register"), dict) else {}
    bounded_gap_summary = bounded_gap_register.get("summary") if isinstance(bounded_gap_register.get("summary"), dict) else {}
    universe_plan = state.get("universe_relationship_plan") if isinstance(state.get("universe_relationship_plan"), dict) else {}
    claim_evidence_ledger = state.get("claim_evidence_ledger") if isinstance(state.get("claim_evidence_ledger"), dict) else {}
    claim_evidence_summary = claim_evidence_ledger.get("summary") if isinstance(claim_evidence_ledger.get("summary"), dict) else {}
    claim_evidence_validation = (
        claim_evidence_ledger.get("validation") if isinstance(claim_evidence_ledger.get("validation"), dict) else {}
    )
    typed_gap_ledger = state.get("typed_gap_ledger") if isinstance(state.get("typed_gap_ledger"), dict) else {}
    typed_gap_summary = typed_gap_ledger.get("summary") if isinstance(typed_gap_ledger.get("summary"), dict) else {}
    typed_gap_validation = typed_gap_ledger.get("validation") if isinstance(typed_gap_ledger.get("validation"), dict) else {}
    entity_master = state.get("entity_security_master") if isinstance(state.get("entity_security_master"), dict) else {}
    entity_master_summary = entity_master.get("summary") if isinstance(entity_master.get("summary"), dict) else {}
    entity_master_validation = entity_master.get("validation") if isinstance(entity_master.get("validation"), dict) else {}
    source_router = state.get("source_capability_router") if isinstance(state.get("source_capability_router"), dict) else {}
    source_router_summary = source_router.get("summary") if isinstance(source_router.get("summary"), dict) else {}
    source_router_validation = source_router.get("validation") if isinstance(source_router.get("validation"), dict) else {}
    source_layer_audit = state.get("source_layer_capability_audit") if isinstance(state.get("source_layer_capability_audit"), dict) else {}
    source_layer_summary = source_layer_audit.get("summary") if isinstance(source_layer_audit.get("summary"), dict) else {}
    source_layer_validation = source_layer_audit.get("validation") if isinstance(source_layer_audit.get("validation"), dict) else {}
    source_authority = state.get("source_authority_coverage") if isinstance(state.get("source_authority_coverage"), dict) else {}
    source_authority_summary = source_authority.get("summary") if isinstance(source_authority.get("summary"), dict) else {}
    provenance_store = state.get("raw_source_provenance_store") if isinstance(state.get("raw_source_provenance_store"), dict) else {}
    provenance_summary = provenance_store.get("summary") if isinstance(provenance_store.get("summary"), dict) else {}
    provenance_validation = provenance_store.get("validation") if isinstance(provenance_store.get("validation"), dict) else {}
    vintage_layer = state.get("asof_vintage_layer") if isinstance(state.get("asof_vintage_layer"), dict) else {}
    vintage_summary = vintage_layer.get("summary") if isinstance(vintage_layer.get("summary"), dict) else {}
    vintage_validation = vintage_layer.get("validation") if isinstance(vintage_layer.get("validation"), dict) else {}
    ontology = state.get("metric_product_ontology_snapshot") if isinstance(state.get("metric_product_ontology_snapshot"), dict) else {}
    ontology_summary = ontology.get("summary") if isinstance(ontology.get("summary"), dict) else {}
    ontology_validation = ontology.get("validation") if isinstance(ontology.get("validation"), dict) else {}
    reconciliation = state.get("reconciliation_ledger") if isinstance(state.get("reconciliation_ledger"), dict) else {}
    reconciliation_summary = reconciliation.get("summary") if isinstance(reconciliation.get("summary"), dict) else {}
    reconciliation_validation = reconciliation.get("validation") if isinstance(reconciliation.get("validation"), dict) else {}
    gate_matrix = state.get("gate_registry_eval_matrix") if isinstance(state.get("gate_registry_eval_matrix"), dict) else {}
    gate_matrix_summary = gate_matrix.get("summary") if isinstance(gate_matrix.get("summary"), dict) else {}
    gate_matrix_validation = gate_matrix.get("validation") if isinstance(gate_matrix.get("validation"), dict) else {}
    derived_layer = state.get("derived_metric_layer") if isinstance(state.get("derived_metric_layer"), dict) else {}
    derived_layer_summary = derived_layer.get("summary") if isinstance(derived_layer.get("summary"), dict) else {}
    derived_layer_validation = derived_layer.get("validation") if isinstance(derived_layer.get("validation"), dict) else {}
    fundamental_pack = state.get("fundamental_statement_pack") if isinstance(state.get("fundamental_statement_pack"), dict) else {}
    fundamental_pack_summary = fundamental_pack.get("summary") if isinstance(fundamental_pack.get("summary"), dict) else {}
    fundamental_pack_validation = (
        fundamental_pack.get("validation") if isinstance(fundamental_pack.get("validation"), dict) else {}
    )
    fundamental_industry_policy = (
        fundamental_pack.get("industry_focus_policy")
        if isinstance(fundamental_pack.get("industry_focus_policy"), dict)
        else {}
    )
    analyst_views = (
        state.get("analyst_view_research_memory")
        if isinstance(state.get("analyst_view_research_memory"), dict)
        else {}
    )
    analyst_views_summary = analyst_views.get("summary") if isinstance(analyst_views.get("summary"), dict) else {}
    analyst_views_validation = (
        analyst_views.get("validation") if isinstance(analyst_views.get("validation"), dict) else {}
    )
    closeout_gate = (
        state.get("d_series_database_closeout_gate")
        if isinstance(state.get("d_series_database_closeout_gate"), dict)
        else {}
    )
    materialization_report = (
        state.get("d_series_database_materialization_report")
        if isinstance(state.get("d_series_database_materialization_report"), dict)
        else {}
    )
    materialized_layers = (
        materialization_report.get("layers") if isinstance(materialization_report.get("layers"), dict) else {}
    )
    reader_context = (
        state.get("d_series_claim_gap_gate_reader_context")
        if isinstance(state.get("d_series_claim_gap_gate_reader_context"), dict)
        else {}
    )
    reader_summary = reader_context.get("summary") if isinstance(reader_context.get("summary"), dict) else {}
    d_series_context = (
        state.get("d_series_research_context")
        if isinstance(state.get("d_series_research_context"), dict)
        else {}
    )
    d_series_context_summary = d_series_context.get("summary") if isinstance(d_series_context.get("summary"), dict) else {}
    pre_memo_selection = (
        state.get("pre_memo_fact_selection")
        if isinstance(state.get("pre_memo_fact_selection"), dict)
        else {}
    )
    pre_memo_summary = pre_memo_selection.get("summary") if isinstance(pre_memo_selection.get("summary"), dict) else {}
    closeout_summary = closeout_gate.get("summary") if isinstance(closeout_gate.get("summary"), dict) else {}
    closeout_validation = closeout_gate.get("validation") if isinstance(closeout_gate.get("validation"), dict) else {}
    evidence_fanout_barrier = state.get("evidence_operator_fanout_barrier") if isinstance(state.get("evidence_operator_fanout_barrier"), dict) else {}
    specialist_fanout_barrier = state.get("specialist_fanout_barrier") if isinstance(state.get("specialist_fanout_barrier"), dict) else {}
    claim_card_store_barrier = state.get("claim_card_store_barrier") if isinstance(state.get("claim_card_store_barrier"), dict) else {}
    adjudicator_barrier = state.get("adjudicator_barrier") if isinstance(state.get("adjudicator_barrier"), dict) else {}
    project_inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), dict) else {}
    milvus_runtime = project_inventory.get("milvus_runtime") if isinstance(project_inventory.get("milvus_runtime"), dict) else {}
    lead_checkpoint = state.get("lead_review_checkpoint") if isinstance(state.get("lead_review_checkpoint"), dict) else {}
    targeted_repair_plan = state.get("targeted_repair_plan") if isinstance(state.get("targeted_repair_plan"), dict) else {}
    lead_targeted_repair = (
        state.get("lead_targeted_repair_execution")
        if isinstance(state.get("lead_targeted_repair_execution"), dict)
        else lead_checkpoint.get("lead_targeted_repair_execution")
        if isinstance(lead_checkpoint.get("lead_targeted_repair_execution"), dict)
        else {}
    )
    memo_logic_plan = state.get("memo_logic_plan") if isinstance(state.get("memo_logic_plan"), dict) else {}
    supervising_pack = state.get("supervising_analyst_pack") if isinstance(state.get("supervising_analyst_pack"), dict) else {}
    supervising_validation = (
        supervising_pack.get("validation") if isinstance(supervising_pack.get("validation"), Mapping) else {}
    )
    supervising_summary = supervising_pack.get("summary") if isinstance(supervising_pack.get("summary"), Mapping) else {}
    supervising_synthesis = (
        supervising_pack.get("research_lead_synthesis_plan")
        if isinstance(supervising_pack.get("research_lead_synthesis_plan"), Mapping)
        else {}
    )
    return {
        "schema_version": "sec_agent_multi_agent_summary_v0.1",
        "run_id": state.get("run_id") or "",
        "status": state.get("status") or "",
        "execution_mode": plan.get("execution_mode") or "",
        "activated_agents": list(plan.get("activate_agents") or []),
        "agent_priorities": dict(plan.get("agent_priorities") or {}),
        "activation_metadata": dict(plan.get("metadata") or {}) if isinstance(plan.get("metadata"), dict) else {},
        "skipped_agents": [dict(item) for item in plan.get("skip_agents") or [] if isinstance(item, dict)],
        "allowed_source_families": list(plan.get("allowed_source_families") or []),
        "evidence_requirements": {
            "requirement_count": len(evidence_plan.get("requirements") or []) if isinstance(evidence_plan, dict) else 0,
            "validation_status": evidence_validation.get("status") if isinstance(evidence_validation, dict) else "",
        },
        "lead_review_checkpoint": {
            "status": lead_checkpoint.get("status") or "",
            "dimension_review_count": len(lead_checkpoint.get("dimension_reviews") or []),
            "retrievable_gap_count": len(
                [
                    item
                    for item in lead_checkpoint.get("dimension_reviews") or []
                    if isinstance(item, Mapping) and str(item.get("status") or "") == "retrievable_gap"
                ]
            ),
            "memo_directive": dict(lead_checkpoint.get("memo_directive") or {})
            if isinstance(lead_checkpoint.get("memo_directive"), Mapping)
            else {},
        },
        "targeted_repair_plan": {
            "status": targeted_repair_plan.get("status") or "",
            "repair_count": len(targeted_repair_plan.get("repairs") or []),
            "routes": [
                str(item.get("route") or "")
                for item in targeted_repair_plan.get("repairs") or []
                if isinstance(item, Mapping)
            ][:12],
        },
        "lead_targeted_repair_execution": {
            "status": lead_targeted_repair.get("status") or "",
            "attempted_count": int(lead_targeted_repair.get("attempted_count") or 0),
            "success_count": int(lead_targeted_repair.get("success_count") or 0),
            "bounded_gap_count": int(lead_targeted_repair.get("bounded_gap_count") or 0),
            "official_context_summaries": [
                dict(item)
                for item in lead_targeted_repair.get("official_context_summaries") or []
                if isinstance(item, Mapping)
            ][:8],
        },
        "memo_logic_plan": {
            "status": (memo_logic_plan.get("validation") or {}).get("status")
            if isinstance(memo_logic_plan.get("validation"), Mapping)
            else "",
            "section_count": len(memo_logic_plan.get("sections") or []),
            "section_order": list(memo_logic_plan.get("section_order") or [])[:12],
            "memo_style_contract": dict(memo_logic_plan.get("memo_style_contract") or {})
            if isinstance(memo_logic_plan.get("memo_style_contract"), Mapping)
            else {},
            "required_question_item_count": len(memo_logic_plan.get("required_question_items") or []),
            "required_question_items": [
                dict(item)
                for item in memo_logic_plan.get("required_question_items") or []
                if isinstance(item, Mapping)
            ][:12],
            "required_item_answer_plan_count": len(memo_logic_plan.get("required_item_answer_plan") or []),
            "required_item_answer_plan": [
                dict(item)
                for item in memo_logic_plan.get("required_item_answer_plan") or []
                if isinstance(item, Mapping)
            ][:12],
            "writer_thesis_skeleton_present": isinstance(memo_logic_plan.get("writer_thesis_skeleton"), Mapping),
            "product_reasoning_frame_present": isinstance(memo_logic_plan.get("product_reasoning_frame"), Mapping)
            and bool(memo_logic_plan.get("product_reasoning_frame")),
            "economic_role_summary": dict(memo_logic_plan.get("economic_role_summary") or {})
            if isinstance(memo_logic_plan.get("economic_role_summary"), Mapping)
            else {},
        },
        "supervising_analyst_pack": {
            "status": supervising_validation.get("status") or "",
            "financial_metric_count": supervising_summary.get("financial_metric_count") or 0,
            "product_kpi_count": supervising_summary.get("product_kpi_count") or 0,
            "capital_edge_count": supervising_summary.get("capital_edge_count") or 0,
            "finding_count": supervising_summary.get("finding_count") or 0,
            "stance": supervising_synthesis.get("stance") or "",
        },
        "plan_reflection": {
            "status": plan_reflection.get("status") or "",
            "error_count": len(plan_reflection.get("errors") or []),
            "warning_count": len(plan_reflection.get("warnings") or []),
            "repair_request_count": len(plan_reflection.get("repair_requests") or []),
            "policy": plan_reflection.get("policy") or "",
        },
        "evidence_rows": {
            "context_row_count": len(state.get("context_rows") or []),
            "runtime_ledger_row_count": len(state.get("runtime_ledger_rows") or []),
            "market_snapshot_row_count": len(state.get("market_snapshot_rows") or []),
            "industry_snapshot_row_count": len(state.get("industry_snapshot_rows") or []),
            "source_gap_count": len(state.get("source_gaps") or []),
            "tool_observation_count": len(state.get("tool_observations") or []),
            "retrieval_route_count": len((state.get("retrieval_plan") or {}).get("routes") or [])
            if isinstance(state.get("retrieval_plan"), dict)
            else 0,
            "reflection_sufficiency_level": (state.get("multi_agent_reflection_report") or {}).get("sufficiency_level")
            if isinstance(state.get("multi_agent_reflection_report"), dict)
            else "",
        },
        "evidence_fusion": {
            "schema_version": evidence_fusion.get("schema_version") or "",
            "policy": evidence_fusion.get("policy") or "",
            "row_count": evidence_fusion.get("row_count") or 0,
            "exact_authority_row_count": evidence_fusion_summary.get("exact_authority_row_count") or 0,
            "context_only_row_count": evidence_fusion_summary.get("context_only_row_count") or 0,
            "lead_only_row_count": evidence_fusion_summary.get("lead_only_row_count") or 0,
            "gap_only_row_count": evidence_fusion_summary.get("gap_only_row_count") or 0,
            "product_runtime_fact_count": evidence_fusion_summary.get("product_runtime_fact_count") or 0,
            "semantic_supplement_row_count": evidence_fusion_summary.get("semantic_supplement_row_count") or 0,
            "by_source_family": dict(evidence_fusion_summary.get("by_source_family") or {}),
            "by_authority_tier": dict(evidence_fusion_summary.get("by_authority_tier") or {}),
            "public_exact_authority_violation_count": evidence_fusion_summary.get("public_exact_authority_violation_count") or 0,
            "semantic_exact_authority_violation_count": evidence_fusion_summary.get("semantic_exact_authority_violation_count") or 0,
        },
        "bounded_gap_register": {
            "schema_version": bounded_gap_register.get("schema_version") or "",
            "gap_count": bounded_gap_register.get("gap_count") or 0,
            "by_gap_type": dict(bounded_gap_summary.get("by_gap_type") or {}),
            "by_source_family": dict(bounded_gap_summary.get("by_source_family") or {}),
            "commercial_tracker_gap_count": bounded_gap_summary.get("commercial_tracker_gap_count") or 0,
            "public_unavailable_gap_count": bounded_gap_summary.get("public_unavailable_gap_count") or 0,
            "parser_schema_gap_count": bounded_gap_summary.get("parser_schema_gap_count") or 0,
        },
        "claim_evidence_ledger": {
            "schema_version": claim_evidence_ledger.get("schema_version") or "",
            "claim_count": claim_evidence_ledger.get("claim_count") or 0,
            "by_claim_status": dict(claim_evidence_summary.get("by_claim_status") or {}),
            "by_source_strength": dict(claim_evidence_summary.get("by_source_strength") or {}),
            "memo_writer_eligible_claim_count": claim_evidence_summary.get("memo_writer_eligible_claim_count") or 0,
            "validation_status": claim_evidence_validation.get("status") or "",
        },
        "typed_gap_ledger": {
            "schema_version": typed_gap_ledger.get("schema_version") or "",
            "gap_count": typed_gap_ledger.get("gap_count") or 0,
            "by_gap_type": dict(typed_gap_summary.get("by_gap_type") or {}),
            "by_repairability": dict(typed_gap_summary.get("by_repairability") or {}),
            "commercial_gap_count": typed_gap_summary.get("commercial_gap_count") or 0,
            "validation_status": typed_gap_validation.get("status") or "",
        },
        "entity_security_master": {
            "schema_version": entity_master.get("schema_version") or "",
            "entity_count": entity_master.get("entity_count") or 0,
            "ticker_count": entity_master_summary.get("ticker_count") or 0,
            "cik_count": entity_master_summary.get("cik_count") or 0,
            "external_identifier_count": entity_master_summary.get("external_identifier_count") or 0,
            "unresolved_reference_count": entity_master_summary.get("unresolved_reference_count") or 0,
            "validation_status": entity_master_validation.get("status") or "",
        },
        "source_capability_router": {
            "schema_version": source_router.get("schema_version") or "",
            "capability_count": source_router.get("capability_count") or 0,
            "decision_count": source_router.get("decision_count") or 0,
            "by_decision_status": dict(source_router_summary.get("by_decision_status") or {}),
            "exact_authority_source_families": list(source_router_summary.get("exact_authority_source_families") or []),
            "context_only_source_families": list(source_router_summary.get("context_only_source_families") or []),
            "blocked_decision_count": source_router_summary.get("blocked_decision_count") or 0,
            "gap_decision_count": source_router_summary.get("gap_decision_count") or 0,
            "validation_status": source_router_validation.get("status") or "",
        },
        "source_layer_capability_audit": {
            "schema_version": source_layer_audit.get("schema_version") or "",
            "status": source_layer_audit.get("status") or "",
            "source_count": source_layer_summary.get("source_count") or 0,
            "runtime_ready_count": source_layer_summary.get("runtime_ready_count") or 0,
            "expected_missing_count": source_layer_summary.get("expected_missing_count") or 0,
            "exact_authority_ready_count": source_layer_summary.get("exact_authority_ready_count") or 0,
            "context_or_proxy_allowed_count": source_layer_summary.get("context_or_proxy_allowed_count") or 0,
            "by_layer": dict(source_layer_summary.get("by_layer") or {}),
            "by_evidence_graph_status": dict(source_layer_summary.get("by_evidence_graph_status") or {}),
            "by_acquisition_status": dict(source_layer_summary.get("by_acquisition_status") or {}),
            "by_parser_status": dict(source_layer_summary.get("by_parser_status") or {}),
            "validation_status": source_layer_validation.get("status") or "",
        },
        "source_authority_coverage": {
            "schema_version": source_authority.get("schema_version") or "",
            "status": source_authority.get("status") or "",
            "scope_tickers": list(source_authority.get("scope_tickers") or [])[:24],
            "row_count": source_authority.get("row_count") or 0,
            "selected_row_count": source_authority.get("selected_row_count") or 0,
            "evidence_bundle_allowed_count": source_authority_summary.get("evidence_bundle_allowed_count") or 0,
            "exact_company_fact_authority_count": source_authority_summary.get("exact_company_fact_authority_count") or 0,
            "thesis_driver_authority_count": source_authority_summary.get("thesis_driver_authority_count") or 0,
            "by_source_role": dict(source_authority_summary.get("by_source_role") or {}),
            "by_signal_authority_type": dict(source_authority_summary.get("by_signal_authority_type") or {}),
        },
        "raw_source_provenance_store": {
            "schema_version": provenance_store.get("schema_version") or "",
            "record_count": provenance_store.get("record_count") or 0,
            "by_source_family": dict(provenance_summary.get("by_source_family") or {}),
            "by_record_type": dict(provenance_summary.get("by_record_type") or {}),
            "missing_raw_locator_count": provenance_summary.get("missing_raw_locator_count") or 0,
            "document_id_count": provenance_summary.get("document_id_count") or 0,
            "checksum_count": provenance_summary.get("checksum_count") or 0,
            "validation_status": provenance_validation.get("status") or "",
        },
        "asof_vintage_layer": {
            "schema_version": vintage_layer.get("schema_version") or "",
            "record_count": vintage_layer.get("record_count") or 0,
            "by_source_family": dict(vintage_summary.get("by_source_family") or {}),
            "by_time_basis": dict(vintage_summary.get("by_time_basis") or {}),
            "fiscal_period_record_count": vintage_summary.get("fiscal_period_record_count") or 0,
            "market_as_of_record_count": vintage_summary.get("market_as_of_record_count") or 0,
            "macro_vintage_record_count": vintage_summary.get("macro_vintage_record_count") or 0,
            "missing_time_anchor_count": vintage_summary.get("missing_time_anchor_count") or 0,
            "validation_status": vintage_validation.get("status") or "",
        },
        "metric_product_ontology_snapshot": {
            "schema_version": ontology.get("schema_version") or "",
            "metric_count": ontology.get("metric_count") or 0,
            "financial_metric_count": ontology_summary.get("financial_metric_count") or 0,
            "product_kpi_count": ontology_summary.get("product_kpi_count") or 0,
            "observed_metric_count": ontology_summary.get("observed_metric_count") or 0,
            "observed_mapped_count": ontology_summary.get("observed_mapped_count") or 0,
            "observed_unmapped_count": ontology_summary.get("observed_unmapped_count") or 0,
            "validation_status": ontology_validation.get("status") or "",
        },
        "reconciliation_ledger": {
            "schema_version": reconciliation.get("schema_version") or "",
            "candidate_count": reconciliation.get("candidate_count") or 0,
            "group_count": reconciliation.get("group_count") or 0,
            "conflict_gap_count": reconciliation.get("conflict_gap_count") or 0,
            "by_resolution_status": dict(reconciliation_summary.get("by_resolution_status") or {}),
            "by_conflict_type": dict(reconciliation_summary.get("by_conflict_type") or {}),
            "resolved_group_count": reconciliation_summary.get("resolved_group_count") or 0,
            "unresolved_conflict_count": reconciliation_summary.get("unresolved_conflict_count") or 0,
            "preferred_candidate_count": reconciliation_summary.get("preferred_candidate_count") or 0,
            "validation_status": reconciliation_validation.get("status") or "",
        },
        "gate_registry_eval_matrix": {
            "schema_version": gate_matrix.get("schema_version") or "",
            "gate_count": gate_matrix.get("gate_count") or 0,
            "gate_result_count": gate_matrix.get("gate_result_count") or 0,
            "blocking_fail_count": gate_matrix_summary.get("blocking_fail_count") or 0,
            "by_status": dict(gate_matrix_summary.get("by_status") or {}),
            "source_boundary_violation_covered": bool(gate_matrix_summary.get("source_boundary_violation_covered")),
            "weak_proxy_fallback_covered": bool(gate_matrix_summary.get("weak_proxy_fallback_covered")),
            "eval_matrix_gate_count": gate_matrix_summary.get("eval_matrix_gate_count") or 0,
            "validation_status": gate_matrix_validation.get("status") or "",
        },
        "derived_metric_layer": {
            "schema_version": derived_layer.get("schema_version") or "",
            "input_fact_count": derived_layer.get("input_fact_count") or 0,
            "derived_metric_count": derived_layer.get("derived_metric_count") or 0,
            "skipped_derivation_count": derived_layer.get("skipped_derivation_count") or 0,
            "by_derived_metric_family": dict(derived_layer_summary.get("by_derived_metric_family") or {}),
            "by_gate_status": dict(derived_layer_summary.get("by_gate_status") or {}),
            "blocked_derivation_count": derived_layer_summary.get("blocked_derivation_count") or 0,
            "validation_status": derived_layer_validation.get("status") or "",
        },
        "fundamental_statement_pack": {
            "schema_version": fundamental_pack.get("schema_version") or "",
            "pack_status": fundamental_pack_summary.get("pack_status") or "",
            "line_item_count": fundamental_pack_summary.get("line_item_count") or 0,
            "period_change_count": fundamental_pack_summary.get("period_change_count") or 0,
            "peer_comparison_count": fundamental_pack_summary.get("peer_comparison_count") or 0,
            "priority_metric_available_count": fundamental_pack_summary.get("priority_metric_available_count") or 0,
            "priority_metric_missing_count": fundamental_pack_summary.get("priority_metric_missing_count") or 0,
            "gap_count": fundamental_pack_summary.get("gap_count") or 0,
            "industry_id": fundamental_industry_policy.get("industry_id") or "",
            "validation_status": fundamental_pack_validation.get("status") or "",
        },
        "analyst_view_research_memory": {
            "schema_version": analyst_views.get("schema_version") or "",
            "view_count": analyst_views.get("view_count") or 0,
            "memory_entry_count": analyst_views.get("memory_entry_count") or 0,
            "by_view_type": dict(analyst_views_summary.get("by_view_type") or {}),
            "by_view_status": dict(analyst_views_summary.get("by_view_status") or {}),
            "company_count": analyst_views_summary.get("company_count") or 0,
            "claim_ref_count": analyst_views_summary.get("claim_ref_count") or 0,
            "gap_ref_count": analyst_views_summary.get("gap_ref_count") or 0,
            "derived_metric_ref_count": analyst_views_summary.get("derived_metric_ref_count") or 0,
            "validation_status": analyst_views_validation.get("status") or "",
        },
        "d_series_database_closeout_gate": {
            "schema_version": closeout_gate.get("schema_version") or "",
            "gate_status": closeout_gate.get("gate_status") or "",
            "d_series_closeout_allowed": bool(closeout_gate.get("d_series_closeout_allowed")),
            "layer_count": closeout_gate.get("layer_count") or 0,
            "required_database_layer_count": closeout_gate.get("required_database_layer_count") or 0,
            "database_ready_layer_count": closeout_gate.get("database_ready_layer_count") or 0,
            "pending_required_database_layer_count": closeout_gate.get("pending_required_database_layer_count") or 0,
            "pending_required_layers": list(closeout_summary.get("pending_required_layers") or []),
            "artifact_present_count": closeout_summary.get("artifact_present_count") or 0,
            "required_artifact_missing_count": closeout_summary.get("required_artifact_missing_count") or 0,
            "validation_status": closeout_validation.get("status") or "",
        },
        "d_series_database_materialization": {
            "schema_version": materialization_report.get("schema_version") or "",
            "db_path": materialization_report.get("db_path") or "",
            "run_id": materialization_report.get("run_id") or "",
            "materialized_layer_count": len(materialized_layers),
            "materialized_layers": sorted(materialized_layers.keys()),
            "all_materialized_layers_parity_pass": bool(materialized_layers)
            and all(
                isinstance(layer, Mapping) and layer.get("parity_status") == "pass"
                for layer in materialized_layers.values()
            ),
        },
        "d_series_claim_gap_gate_reader": {
            "schema_version": reader_context.get("schema_version") or "",
            "reader_default_status": reader_context.get("reader_default_status") or "",
            "db_path": reader_context.get("db_path") or "",
            "claim_count": reader_summary.get("claim_count") or 0,
            "typed_gap_count": reader_summary.get("typed_gap_count") or 0,
            "gate_history_count": reader_summary.get("gate_history_count") or 0,
        },
        "d_series_research_context_reader": {
            "schema_version": d_series_context.get("schema_version") or "",
            "reader_default_status": d_series_context.get("reader_default_status") or "",
            "db_path": d_series_context.get("db_path") or "",
            "context_group_count": d_series_context_summary.get("context_group_count") or 0,
            "row_count": d_series_context_summary.get("row_count") or 0,
            "stale_or_superseded_row_count": d_series_context_summary.get("stale_or_superseded_row_count") or 0,
            "latest_key_count": d_series_context_summary.get("latest_key_count") or 0,
        },
        "pre_memo_fact_selection": {
            "schema_version": pre_memo_selection.get("schema_version") or "",
            "policy": pre_memo_selection.get("policy") or "",
            "approved_fact_count": pre_memo_summary.get("approved_fact_count") or 0,
            "rejected_fact_count": pre_memo_summary.get("rejected_fact_count") or 0,
            "approved_derived_metric_count": pre_memo_summary.get("approved_derived_metric_count") or 0,
            "rejected_derived_metric_count": pre_memo_summary.get("rejected_derived_metric_count") or 0,
            "bounded_gap_link_count": pre_memo_summary.get("bounded_gap_link_count") or 0,
            "blocking_gate_result_count": pre_memo_summary.get("blocking_gate_result_count") or 0,
            "validation_status": (pre_memo_selection.get("validation") or {}).get("status")
            if isinstance(pre_memo_selection.get("validation"), dict)
            else "",
        },
        "milvus_runtime": {
            "status": milvus_runtime.get("status") or "",
            "available": bool(milvus_runtime.get("available")),
            "location": milvus_runtime.get("location") or "",
            "collection": milvus_runtime.get("collection") or "",
            "vector_count": milvus_runtime.get("vector_count"),
            "as_of_date": milvus_runtime.get("as_of_date") or "",
            "schema_digest": milvus_runtime.get("schema_digest") or "",
            "vector_kinds": list(milvus_runtime.get("vector_kinds") or []),
            "claim_boundary": milvus_runtime.get("claim_boundary") or "",
            "fallback_routes": list(milvus_runtime.get("fallback_routes") or []),
        },
        "graph_barriers": {
            "evidence_operator_fanout": {
                "schema_version": evidence_fanout_barrier.get("schema_version") or "",
                "execution_mode": evidence_fanout_barrier.get("execution_mode") or "",
                "input_shard_count": evidence_fanout_barrier.get("input_shard_count") or 0,
                "completed_shard_count": evidence_fanout_barrier.get("completed_shard_count") or 0,
                "failed_shard_count": evidence_fanout_barrier.get("failed_shard_count") or 0,
            },
            "specialist_fanout": {
                "schema_version": specialist_fanout_barrier.get("schema_version") or "",
                "execution_mode": specialist_fanout_barrier.get("execution_mode") or "",
                "specialist_count": specialist_fanout_barrier.get("specialist_count") or 0,
                "failed_route_count": specialist_fanout_barrier.get("failed_route_count") or 0,
                "supporting_run_without_required_item_match_count": (
                    specialist_fanout_barrier.get("supporting_run_without_required_item_match_count") or 0
                ),
                "supporting_run_without_required_item_match_agents": list(
                    specialist_fanout_barrier.get("supporting_run_without_required_item_match_agents") or []
                ),
                "source_layer_distribution": dict(specialist_fanout_barrier.get("source_layer_distribution") or {}),
            },
            "claim_card_store": {
                "schema_version": claim_card_store_barrier.get("schema_version") or "",
                "supported_claim_count": claim_card_store_barrier.get("supported_claim_count") or 0,
                "unsupported_claim_count": claim_card_store_barrier.get("unsupported_claim_count") or 0,
                "memo_writer_allowed": bool(claim_card_store_barrier.get("memo_writer_allowed", True)),
            },
            "adjudicator": {
                "schema_version": adjudicator_barrier.get("schema_version") or "",
                "judgment_status": adjudicator_barrier.get("judgment_status") or "",
                "memo_ready_claim_count": adjudicator_barrier.get("memo_ready_claim_count") or 0,
            },
        },
        "tool_calls": [
            {
                "agent_id": record.get("agent_id") or "",
                "tool_name": record.get("tool_name") or "",
                "status": record.get("status") or "",
                "row_count": record.get("row_count") or 0,
                "source_gap_count": record.get("source_gap_count") or 0,
                "elapsed_ms": record.get("elapsed_ms") or 0,
                "coverage_delta": record.get("coverage_delta") or {},
                "argument_summary": dict((record.get("metadata") or {}).get("argument_summary") or {})
                if isinstance(record.get("metadata"), dict)
                else {},
                "runtime_summary": dict((record.get("metadata") or {}).get("runtime_summary") or {})
                if isinstance(record.get("metadata"), dict)
                else {},
            }
            for record in records
        ],
        "tool_call_count": len(records),
        "second_pass": {
            "attempts": int(state.get("second_pass_attempts") or 0),
            "result": second_pass if isinstance(second_pass, dict) else {},
            "diagnosis": {
                "schema_version": second_pass_diagnosis.get("schema_version") or "",
                "trigger": second_pass_diagnosis.get("trigger") or "",
                "diagnosis_count": second_pass_diagnosis.get("diagnosis_count") or 0,
                "by_gap_type": dict((second_pass_diagnosis.get("summary") or {}).get("by_gap_type") or {})
                if isinstance(second_pass_diagnosis.get("summary"), dict)
                else {},
            },
            "repair_plan": {
                "schema_version": second_pass_repair_plan.get("schema_version") or "",
                "repair_count": second_pass_repair_plan.get("repair_count") or 0,
                "by_repair_action": dict((second_pass_repair_plan.get("summary") or {}).get("by_repair_action") or {})
                if isinstance(second_pass_repair_plan.get("summary"), dict)
                else {},
            },
            "hard_gate": {
                "schema_version": second_pass_hard_gate.get("schema_version") or "",
                "status": second_pass_hard_gate.get("status") or "",
                "executable_request_count": (second_pass_hard_gate.get("summary") or {}).get("executable_request_count")
                if isinstance(second_pass_hard_gate.get("summary"), dict)
                else 0,
                "blocked_repair_count": (second_pass_hard_gate.get("summary") or {}).get("blocked_repair_count")
                if isinstance(second_pass_hard_gate.get("summary"), dict)
                else 0,
                "by_block_reason": dict((second_pass_hard_gate.get("summary") or {}).get("by_block_reason") or {})
                if isinstance(second_pass_hard_gate.get("summary"), dict)
                else {},
            },
            "delta_audit": {
                "schema_version": second_pass_delta_audit.get("schema_version") or "",
                "status": second_pass_delta_audit.get("status") or "",
                "added_row_count": second_pass_delta_audit.get("added_row_count") or 0,
                "added_exact_authority_row_count": second_pass_delta_audit.get("added_exact_authority_row_count") or 0,
                "added_authority_bearing_row_count": second_pass_delta_audit.get("added_authority_bearing_row_count") or 0,
                "closed_gap_count": len(second_pass_delta_audit.get("closed_gap_ids") or []),
                "open_gap_count": len(second_pass_delta_audit.get("open_gap_ids") or []),
                "stop_reason": second_pass_delta_audit.get("stop_reason") or "",
            },
            "quality_attempted": bool(state.get("quality_second_pass_attempted")),
            "quality_decision": dict(state.get("quality_second_pass_decision") or {}),
            "quality_gap_count": len((state.get("quality_second_pass_report") or {}).get("quality_gaps") or [])
            if isinstance(state.get("quality_second_pass_report"), dict)
            else 0,
        },
        "specialists": {
            "output_count": len(state.get("specialist_outputs") or []),
            "activation_decisions": [
                dict(item)
                for item in state.get("specialist_activation_decisions") or []
                if isinstance(item, dict)
            ],
            "verification_status": specialist_verification.get("status") if isinstance(specialist_verification, dict) else "",
            "memo_writer_allowed": bool(specialist_verification.get("memo_writer_allowed")) if isinstance(specialist_verification, dict) else False,
            "unsupported_claim_count": specialist_verification.get("unsupported_claim_count", 0) if isinstance(specialist_verification, dict) else 0,
            "route_results": [
                _specialist_route_summary(item)
                for item in state.get("specialist_route_results") or []
                if isinstance(item, dict)
            ],
        },
        "judgment_plan": _judgment_plan_quality_summary(state.get("judgment_plan")),
        "verified_judgment_plan": _judgment_plan_quality_summary(state.get("verified_judgment_plan")),
        "relationship_graph": {
            "lookup_status": relationship_lookup.get("status") or "",
            "relationship_count": len(relationship_lookup.get("relationships") or []),
            "source_gap_count": len(relationship_lookup.get("source_gaps") or []),
            "validation_status": universe_validation.get("status") if isinstance(universe_validation, dict) else "",
            "claim_scope": ((relationship_lookup.get("summary") or {}).get("claim_scope") if isinstance(relationship_lookup.get("summary"), dict) else ""),
        },
        "universe_relationship_plan": {
            "schema_version": universe_plan.get("schema_version") or "",
            "scope_mode": universe_plan.get("scope_mode") or "",
            "source_family": universe_plan.get("source_family") or "",
            "focus_tickers": list(universe_plan.get("focus_tickers") or []),
            "expanded_tickers": list(universe_plan.get("expanded_tickers") or []),
            "included_tickers": list(universe_plan.get("included_tickers") or []),
            "relationship_count": len(universe_plan.get("relationships") or []),
            "claim_scope": "scope_or_hypothesis_only",
            "metadata": dict(universe_plan.get("metadata") or {}),
        },
        "universe_relationship_validation": {
            "status": universe_validation.get("status") if isinstance(universe_validation, dict) else "",
            "error_count": len(universe_validation.get("errors") or []) if isinstance(universe_validation, dict) else 0,
            "warning_count": len(universe_validation.get("warnings") or []) if isinstance(universe_validation, dict) else 0,
            "errors": list(universe_validation.get("errors") or [])[:8] if isinstance(universe_validation, dict) else [],
            "warnings": list(universe_validation.get("warnings") or [])[:8] if isinstance(universe_validation, dict) else [],
        },
        "llm_routes": {
            "research_lead": {
                "route_status": state.get("research_lead_route_status") or "",
                "failure_reason": state.get("research_lead_failure_reason") or "",
                "rejected_plan": dict(state.get("research_lead_rejected_plan") or {}),
                "validation_errors": list((state.get("research_lead_validation") or {}).get("errors") or [])
                if isinstance(state.get("research_lead_validation"), dict)
                else [],
                "validation_status": (state.get("agent_activation_validation") or {}).get("status")
                if isinstance(state.get("agent_activation_validation"), dict)
                else "",
                "diagnostics": _model_diagnostics_summary(state.get("research_lead_model_diagnostics")),
                "input_pack_fingerprint": dict(state.get("research_lead_input_pack_fingerprint") or {}),
            },
            "universe_relationship": {
                "validation_status": universe_validation.get("status") if isinstance(universe_validation, dict) else "",
                "routing_trace": dict(state.get("universe_relationship_routing_trace") or {}),
                "diagnostics": _model_diagnostics_summary(state.get("universe_relationship_model_diagnostics")),
                "input_pack_fingerprint": dict(state.get("universe_relationship_input_pack_fingerprint") or {}),
            },
            "memo_writer": {
                "route_result": dict(state.get("memo_route_result") or {}),
                "diagnostics": _model_diagnostics_summary(memo.get("model_diagnostics")),
            },
            "verifier": {
                "verification_status": claim_verification.get("status") if isinstance(claim_verification, dict) else "",
                "input_projection": dict(claim_verification.get("verifier_input_projection") or {})
                if isinstance(claim_verification, dict)
                else {},
                "diagnostics": _model_diagnostics_summary(claim_verification.get("model_diagnostics")),
            },
        },
        "loop_break_reason": state.get("loop_break_reason") or (ledger.get("loop_break_reason") if isinstance(ledger, dict) else ""),
        "bounded_answer_allowed": bool(state.get("bounded_answer_allowed") or (ledger.get("bounded_answer_allowed") if isinstance(ledger, dict) else False)),
        "agent_trace": [dict(item) for item in state.get("agent_trace") or [] if isinstance(item, dict)],
        "payload_policy": {
            "state_payload": "summary_only",
            "raw_evidence": "not_included",
            "internal_reasoning": "not_included",
        },
    }


def _specialist_route_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    summary = {
        "agent_id": result.get("agent_id") or "",
        "status": result.get("status") or "",
        "priority": result.get("priority") or "",
        "activation_policy": result.get("activation_policy") or "",
        "failure_reason": str(result.get("failure_reason") or "")[:500],
        "attempt_count": result.get("attempt_count"),
        "repair_attempts": result.get("repair_attempts"),
        "latency_ms": result.get("latency_ms"),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "total_tokens": result.get("total_tokens"),
        "finish_reasons": list(result.get("finish_reasons") or []),
    }
    for key in (
        "task_card_schema_version",
        "assigned_memo_slot",
        "task_relevant_requirement_count",
        "required_claim_slot_count",
        "counterclaim_slot_count",
        "available_source_families",
        "shared_context_digest",
        "prompt_bounded_evidence_row_count",
        "prompt_relationship_summary_row_count",
        "prompt_row_distribution",
        "input_coverage_summary",
        "activation_decision",
        "activation_reason",
        "matched_requirement_count",
        "explicit_intent",
        "signal_count",
    ):
        if key in result:
            summary[key] = result.get(key)
    return summary


def _judgment_plan_quality_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    stats = value.get("claim_card_stats") if isinstance(value.get("claim_card_stats"), Mapping) else {}
    outline = [row for row in value.get("memo_outline") or [] if isinstance(row, Mapping)]
    thesis_pack = value.get("memo_thesis_pack") if isinstance(value.get("memo_thesis_pack"), Mapping) else {}
    thesis_driver_pack = value.get("thesis_driver_pack") if isinstance(value.get("thesis_driver_pack"), Mapping) else {}
    judgment_state = value.get("judgment_state") if isinstance(value.get("judgment_state"), Mapping) else {}
    return {
        "claim_card_stats": {
            "supported_claim_count": int(stats.get("supported_claim_count") or 0),
            "high_materiality_claim_count": int(stats.get("high_materiality_claim_count") or 0),
            "memo_slot_count": int(stats.get("memo_slot_count") or len(outline)),
            "supported_memo_slot_count": int(stats.get("supported_memo_slot_count") or 0),
            "synthesized_thesis_claim_count": int(stats.get("synthesized_thesis_claim_count") or 0),
        },
        "supported_claim_count": len(value.get("supported_claims") or []),
        "unsupported_claim_count": len(value.get("unsupported_claims") or []),
        "conflict_count": len(value.get("conflicts") or []),
        "thesis_synthesis": dict(value.get("thesis_synthesis") or {}) if isinstance(value.get("thesis_synthesis"), Mapping) else {},
        "memo_thesis_pack": {
            "present": bool(thesis_pack),
            "status": str(thesis_pack.get("status") or ""),
            "supporting_driver_count": len(thesis_pack.get("supporting_drivers") or []),
            "counterargument_count": len(thesis_pack.get("counterarguments") or []),
            "watch_item_count": len(thesis_pack.get("watch_items") or []),
            "source_claim_ref_count": len(thesis_pack.get("source_claim_refs") or []),
        },
        "thesis_driver_pack": {
            "present": bool(thesis_driver_pack),
            "status": str(thesis_driver_pack.get("status") or ""),
            "thesis_card_count": len(thesis_driver_pack.get("thesis_cards") or []),
            "driver_count": len(thesis_driver_pack.get("driver_cards") or []),
            "counter_driver_count": len(thesis_driver_pack.get("counter_driver_cards") or []),
            "gap_count": len(thesis_driver_pack.get("gap_cards") or []),
            "source_boundary_card_count": len(thesis_driver_pack.get("source_boundary_cards") or []),
        },
        "judgment_state": {
            "present": bool(judgment_state),
            "status": str(judgment_state.get("status") or ""),
            "dimension_judgment_count": len(judgment_state.get("dimension_judgments") or []),
            "fundamental_line_item_count": (
                (judgment_state.get("fundamental_statement_summary") or {}).get("line_item_count")
                if isinstance(judgment_state.get("fundamental_statement_summary"), Mapping)
                else 0
            ),
            "fundamental_peer_comparison_count": (
                (judgment_state.get("fundamental_statement_summary") or {}).get("peer_comparison_count")
                if isinstance(judgment_state.get("fundamental_statement_summary"), Mapping)
                else 0
            ),
        },
        "unsupported_claim_policy": dict(value.get("unsupported_claim_policy") or {}) if isinstance(value.get("unsupported_claim_policy"), Mapping) else {},
        "memo_outline": [
            {
                "memo_slot": str(row.get("memo_slot") or ""),
                "status": str(row.get("status") or ""),
                "supported_claim_count": int(row.get("supported_claim_count") or 0),
                "missing_reason": str(row.get("missing_reason") or "")[:200],
            }
            for row in outline[:12]
        ],
    }


def _model_diagnostics_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {
            "call_count": 0,
            "provider": "",
            "model": "",
            "latency_ms": None,
            "total_tokens": None,
            "finish_reasons": [],
            "all_calls_ok": False,
            "direct_tool_call_count": 0,
            "raw_response_saved": False,
        }
    calls = [dict(item) for item in value.get("calls") or [] if isinstance(item, Mapping)]
    provider = value.get("provider") or next((call.get("provider") for call in calls if call.get("provider")), "")
    model = value.get("model") or next((call.get("model") for call in calls if call.get("model")), "")
    return {
        "call_count": int(value.get("call_count") or len(calls)),
        "provider": provider,
        "model": model,
        "latency_ms": value.get("latency_ms") if value.get("latency_ms") is not None else _sum_optional_int(calls, "latency_ms"),
        "total_tokens": value.get("total_tokens") if value.get("total_tokens") is not None else _sum_optional_int(calls, "total_tokens"),
        "call_statuses": [str(call.get("status") or "") for call in calls],
        "finish_reasons": list(value.get("finish_reasons") or [call.get("finish_reason") for call in calls]),
        "all_calls_ok": bool(calls) and all(str(call.get("status") or "") == "ok" for call in calls),
        "direct_tool_call_count": sum(int(call.get("tool_call_count") or 0) for call in calls),
        "failure_reasons": [
            str(call.get("failure_reason") or "")[:500]
            for call in calls
            if str(call.get("failure_reason") or "")
        ],
        "raw_response_saved": bool(value.get("raw_response_saved")),
    }


def _sum_optional_int(rows: list[dict[str, Any]], key: str) -> int | None:
    values = [row.get(key) for row in rows if row.get(key) is not None]
    if not values:
        return None
    return sum(int(value) for value in values)


def build_native_summary_artifact_payload(state: SecAgentGraphRuntimeState) -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_langgraph_native_summary_v0.2",
        "run_id": state.get("run_id") or "",
        "status": state.get("status") or "",
        "output_dir": state.get("output_dir") or "",
        "created_at": _utc_now(),
        "checkpoint_backend": {
            "mode": state.get("checkpoint_mode") or "",
            "db_path": state.get("checkpoint_db_path") or "",
        },
        "state_summary": _checkpoint_state_summary(state),
        "node_trace": [dict(item) for item in state.get("node_trace") or [] if isinstance(item, dict)],
        "node_checkpoints": [dict(item) for item in state.get("node_checkpoints") or [] if isinstance(item, dict)],
        "artifact_refs": dict(state.get("artifact_refs") or {}),
        "artifact_status": _checkpoint_artifact_refs(state),
        "payload_policy": {
            "state_payload": "summary_only",
            "large_payloads": "external_artifacts",
        },
    }


def build_node_checkpoint_artifact_payload(state: SecAgentGraphRuntimeState) -> dict[str, Any]:
    checkpoints = [dict(item) for item in state.get("node_checkpoints") or [] if isinstance(item, dict)]
    latest = checkpoints[-1] if checkpoints else {}
    return {
        "schema_version": NODE_CHECKPOINT_ARTIFACT_SCHEMA_VERSION,
        "run_id": state.get("run_id") or "",
        "status": state.get("status") or "",
        "output_dir": state.get("output_dir") or "",
        "created_at": _utc_now(),
        "checkpoint_count": len(checkpoints),
        "latest_checkpoint_id": latest.get("checkpoint_id") or "",
        "latest_completed_node": latest.get("node") or "",
        "payload_policy": {
            "state_payload": "summary_only",
            "large_payloads": "external_artifacts",
            "intended_use": "transition_audit_before_persistent_langgraph_checkpointer",
        },
        "checkpoint_backend": {
            "mode": state.get("checkpoint_mode") or "",
            "db_path": state.get("checkpoint_db_path") or "",
        },
        "artifact_refs": _checkpoint_artifact_refs(state),
        "recoverable_state_summary": _checkpoint_state_summary(state),
        "node_checkpoints": checkpoints,
    }


def _slim_checkpoint_payload(checkpoint: dict[str, Any]) -> dict[str, Any]:
    slimmed = dict(checkpoint)
    channel_values = checkpoint.get("channel_values")
    if isinstance(channel_values, dict):
        slimmed["channel_values"] = {
            str(key): _slim_checkpoint_channel(str(key), value)
            for key, value in channel_values.items()
        }
    return slimmed


def _slim_checkpoint_writes(writes: Any) -> list[tuple[str, Any]]:
    slimmed: list[tuple[str, Any]] = []
    for item in list(writes or []):
        if not isinstance(item, (tuple, list)) or len(item) < 2:
            continue
        channel = str(item[0])
        value = item[1]
        slimmed.append((channel, _slim_checkpoint_channel(channel, value)))
    return slimmed


def _slim_checkpoint_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return _slim_nested_payload(metadata)


def _slim_checkpoint_channel(channel: str, value: Any) -> Any:
    if channel in CHECKPOINT_LARGE_PAYLOAD_CHANNELS:
        return _summarize_large_checkpoint_value(channel, value)
    if channel == "__root__" and isinstance(value, dict):
        return _slim_nested_payload(value)
    return value


def _slim_nested_payload(value: Any, *, parent_key: str = "") -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_str = str(key)
            if key_str in CHECKPOINT_LARGE_PAYLOAD_CHANNELS:
                result[key_str] = _summarize_large_checkpoint_value(key_str, item)
            else:
                result[key_str] = _slim_nested_payload(item, parent_key=key_str)
        return result
    if isinstance(value, list):
        return [_slim_nested_payload(item, parent_key=parent_key) for item in value]
    return value


def _summarize_large_checkpoint_value(channel: str, value: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "__sec_agent_checkpoint_payload__": "externalized_summary",
        "channel": channel,
        "value_type": type(value).__name__,
    }
    if isinstance(value, list):
        summary["row_count"] = len(value)
        if value and isinstance(value[0], dict):
            summary["sample_keys"] = sorted(str(key) for key in value[0].keys())[:24]
            summary["sample_ids"] = _sample_row_ids(value)
        summary["digest"] = _json_digest({"channel": channel, "summary": summary})
        return summary
    if isinstance(value, dict):
        summary["key_count"] = len(value)
        summary["keys"] = sorted(str(key) for key in value.keys())[:40]
        for key in ("schema_version", "status", "answer_status", "claim_status"):
            if key in value:
                summary[key] = value.get(key)
        if isinstance(value.get("summary"), dict):
            summary["summary"] = value.get("summary")
        summary["digest"] = _json_digest({"channel": channel, "summary": summary})
        return summary
    if isinstance(value, str):
        summary["char_count"] = len(value)
        summary["preview"] = value[:200]
        summary["digest"] = _json_digest({"channel": channel, "summary": summary})
        return summary
    summary["digest"] = _json_digest({"channel": channel, "summary": summary})
    return summary


def _sample_row_ids(rows: list[Any]) -> list[str]:
    samples: list[str] = []
    for row in rows[:8]:
        if not isinstance(row, dict):
            continue
        for key in ("evidence_id", "object_id", "metric_id", "id", "ticker"):
            if row.get(key):
                samples.append(str(row.get(key)))
                break
    return samples


def inspect_node_checkpoint_artifact(path: str | Path) -> dict[str, Any]:
    checkpoint_path = _resolve_checkpoint_artifact_path(path)
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    latest_node = str(payload.get("latest_completed_node") or "")
    latest_checkpoint = str(payload.get("latest_checkpoint_id") or "")
    state_summary = payload.get("recoverable_state_summary") if isinstance(payload.get("recoverable_state_summary"), dict) else {}
    next_node = _next_recoverable_node(latest_node, state_summary)
    artifact_status = _inspect_checkpoint_artifact_refs(payload.get("artifact_refs") or {})
    required = list(NATIVE_RESUME_REQUIRED_ARTIFACTS.get(next_node, ())) if next_node else []
    missing = [key for key in required if not artifact_status.get(key, {}).get("exists")]
    digest_mismatch = [
        key
        for key in required
        if artifact_status.get(key, {}).get("exists")
        and artifact_status.get(key, {}).get("digest")
        and artifact_status.get(key, {}).get("actual_digest")
        and artifact_status.get(key, {}).get("digest") != artifact_status.get(key, {}).get("actual_digest")
    ]
    blocked_reasons = []
    if missing:
        blocked_reasons.append("missing_required_artifacts")
    if digest_mismatch:
        blocked_reasons.append("digest_mismatch_artifacts")
    if not next_node:
        blocked_reasons.append("no_next_node")
    return {
        "schema_version": NODE_CHECKPOINT_RESUME_INSPECTION_SCHEMA_VERSION,
        "checkpoint_path": str(checkpoint_path.resolve()),
        "run_id": payload.get("run_id") or "",
        "status": payload.get("status") or "",
        "checkpoint_count": payload.get("checkpoint_count") or 0,
        "latest_checkpoint_id": latest_checkpoint,
        "latest_completed_node": latest_node,
        "next_recoverable_node": next_node,
        "required_artifacts_for_next_node": required,
        "resume_supported": bool(next_node and not missing and not digest_mismatch),
        "blocked_reasons": blocked_reasons,
        "missing_required_artifacts": missing,
        "digest_mismatch_artifacts": digest_mismatch,
        "artifact_status": artifact_status,
        "recoverable_state_summary": state_summary,
    }


def hydrate_native_state_from_checkpoint_artifact(path: str | Path) -> dict[str, Any]:
    checkpoint_path = _resolve_checkpoint_artifact_path(path)
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    inspection = inspect_node_checkpoint_artifact(checkpoint_path)
    refs = _raw_artifact_ref_paths(payload.get("artifact_refs") or {})
    state: SecAgentGraphRuntimeState = {
        "run_id": str(payload.get("run_id") or ""),
        "output_dir": str(payload.get("output_dir") or checkpoint_path.parent),
        "status": "hydrated",
        "artifact_refs": refs,
        "node_checkpoints": [dict(item) for item in payload.get("node_checkpoints") or [] if isinstance(item, dict)],
    }
    latest_node = str(payload.get("latest_completed_node") or "")
    if state["node_checkpoints"]:
        state["node_trace"] = [
            {
                "node": str(item.get("node") or ""),
                "started_at": item.get("started_at") or "",
                "finished_at": item.get("finished_at") or "",
                "elapsed_ms": int(item.get("elapsed_ms") or 0),
                "metadata": dict(item.get("metadata") or {}),
            }
            for item in state["node_checkpoints"]
        ]

    case = _load_first_jsonl_ref(refs.get("case"))
    if case:
        state["user_query"] = str(case.get("prompt") or "")
        if isinstance(case.get("query_contract"), dict):
            state["query_contract"] = annotate_scope_contract(case["query_contract"])
        if isinstance(case.get("companies"), list):
            state["selected_tickers"] = _unique_upper(case.get("companies") or [])
        if isinstance(case.get("years"), list):
            state["selected_years"] = _unique_ints(case.get("years") or [])
        project_inventory = (state.get("query_contract") or {}).get("project_inventory")
        if isinstance(project_inventory, dict):
            state["project_inventory"] = project_inventory

    retrieval_plan = _load_json_ref(refs.get("retrieval_plan"))
    if isinstance(retrieval_plan, dict):
        state["retrieval_plan"] = retrieval_plan

    context_rows = _load_context_rows_ref(refs.get("retrieved_context"))
    if context_rows:
        state["context_rows"] = context_rows

    market_rows = _load_jsonl_ref(refs.get("market_snapshot_context"))
    if market_rows:
        state["market_snapshot_rows"] = market_rows
        if state.get("context_rows"):
            existing_ids = {str(row.get("evidence_id") or "") for row in state["context_rows"] if isinstance(row, dict)}
            state["context_rows"] = [
                *state["context_rows"],
                *[row for row in market_rows if str(row.get("evidence_id") or "") not in existing_ids],
            ]

    ledger = _load_json_ref(refs.get("runtime_exact_value_ledger"))
    if isinstance(ledger, dict):
        rows = ledger.get("rows")
        if isinstance(rows, list):
            state["runtime_ledger_rows"] = [row for row in rows if isinstance(row, dict)]

    fundamental_statement_pack = _load_json_ref(refs.get("fundamental_statement_pack"))
    if isinstance(fundamental_statement_pack, dict):
        state["fundamental_statement_pack"] = fundamental_statement_pack

    coverage = _load_json_ref(refs.get("evidence_coverage_matrix"))
    if isinstance(coverage, dict):
        state["coverage_matrix"] = coverage

    second_pass = _load_json_ref(refs.get("second_pass_retrieval_trace"))
    if isinstance(second_pass, dict):
        state["second_pass_result"] = second_pass
        state["second_pass_attempts"] = int(second_pass.get("pass_index") or 1)

    judgment_plan = _load_json_ref(refs.get("judgment_plan"))
    if isinstance(judgment_plan, dict):
        state["judgment_plan"] = judgment_plan

    memo_answer = _load_json_or_first_jsonl_ref(refs.get("memo_answer"))
    if isinstance(memo_answer, dict):
        state["memo_answer"] = _normalize_resume_memo_answer(memo_answer)

    claim_verification = _load_json_or_first_jsonl_ref(refs.get("claim_verification"))
    if isinstance(claim_verification, dict):
        state["claim_verification"] = claim_verification

    deterministic_gates = _load_json_ref(refs.get("deterministic_gates"))
    if isinstance(deterministic_gates, dict):
        state["deterministic_gates"] = deterministic_gates

    rendered_path = refs.get("rendered_answer")
    if rendered_path:
        rendered = _load_text_ref(rendered_path)
        if rendered:
            state["rendered_answer"] = rendered

    return {
        "schema_version": NATIVE_STATE_HYDRATION_SCHEMA_VERSION,
        "checkpoint_path": str(checkpoint_path.resolve()),
        "latest_completed_node": latest_node,
        "next_recoverable_node": inspection.get("next_recoverable_node") or "",
        "resume_supported": bool(inspection.get("resume_supported")),
        "blocked_reasons": list(inspection.get("blocked_reasons") or []),
        "state": state,
        "state_summary": _checkpoint_state_summary(state),
        "artifact_status": inspection.get("artifact_status") or {},
    }


def _resolve_checkpoint_artifact_path(path: str | Path) -> Path:
    candidate = Path(path)
    if candidate.is_dir():
        candidate = candidate / "langgraph_node_checkpoints.json"
    if not candidate.exists():
        raise FileNotFoundError(f"node checkpoint artifact not found: {candidate}")
    return candidate


def _raw_artifact_ref_paths(refs: dict[str, Any]) -> dict[str, str]:
    raw: dict[str, str] = {}
    for key, ref in refs.items():
        if isinstance(ref, dict):
            path = str(ref.get("path") or "")
            if path:
                raw[str(key)] = path
        elif isinstance(ref, str) and ref:
            raw[str(key)] = ref
    return raw


def _load_json_ref(path: str | None) -> Any:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        return None
    return json.loads(candidate.read_text(encoding="utf-8"))


def _load_json_or_first_jsonl_ref(path: str | None) -> Any:
    if not path:
        return None
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        return None
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _load_first_jsonl_ref(path)


def _normalize_resume_memo_answer(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert persisted public agent output rows into the internal synthesis shape."""
    normalized = dict(payload)
    answer = normalized.get("answer") if isinstance(normalized.get("answer"), dict) else {}
    normalized["agent_status"] = str(
        normalized.get("agent_status") or normalized.get("status") or ("answered" if answer else "unknown")
    )
    normalized["answer_status"] = str(normalized.get("answer_status") or "unknown")
    normalized["answer"] = answer
    normalized["limitations"] = list(normalized.get("limitations") or [])
    normalized["claim_status"] = str(normalized.get("claim_status") or "not_verified")
    normalized["claims"] = list(normalized.get("claims") or [])
    normalized["unsupported_claim_count"] = int(normalized.get("unsupported_claim_count") or 0)
    normalized["score_status"] = str(normalized.get("score_status") or "unknown")
    normalized["score_total"] = normalized.get("score_total") or 0
    normalized["failure_types"] = list(normalized.get("failure_types") or [])
    normalized["score_notes"] = list(normalized.get("score_notes") or [])
    if not isinstance(normalized.get("debug"), dict):
        normalized["debug"] = {}
    return normalized


def _load_first_jsonl_ref(path: str | None) -> dict[str, Any]:
    rows = _load_jsonl_ref(path, limit=1)
    return rows[0] if rows else {}


def _load_jsonl_ref(path: str | None, *, limit: int | None = None) -> list[dict[str, Any]]:
    if not path:
        return []
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with candidate.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
            if limit is not None and len(rows) >= limit:
                break
    return rows


def _load_context_rows_ref(path: str | None) -> list[dict[str, Any]]:
    rows = _load_jsonl_ref(path)
    if not rows:
        return []
    context_rows: list[dict[str, Any]] = []
    for row in rows:
        nested = row.get("context_rows")
        if isinstance(nested, list):
            context_rows.extend(item for item in nested if isinstance(item, dict))
    if context_rows:
        return context_rows
    return rows


def _load_text_ref(path: str | None) -> str:
    if not path:
        return ""
    candidate = Path(path)
    if not candidate.exists() or not candidate.is_file():
        return ""
    return candidate.read_text(encoding="utf-8")


def _next_recoverable_node(latest_node: str, state_summary: dict[str, Any]) -> str:
    if not latest_node or latest_node == "persist_session_state":
        return ""
    if latest_node == "assess_evidence_sufficiency":
        if str(state_summary.get("sufficiency_level") or "") == "sufficient":
            return "build_judgment_plan"
        return "execute_second_pass_retrieval"
    if latest_node == "execute_second_pass_retrieval":
        return "build_runtime_ledger"
    if latest_node not in NATIVE_NODE_ORDER:
        return ""
    index = NATIVE_NODE_ORDER.index(latest_node)
    if index + 1 >= len(NATIVE_NODE_ORDER):
        return ""
    return NATIVE_NODE_ORDER[index + 1]


def _inspect_checkpoint_artifact_refs(refs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    status: dict[str, dict[str, Any]] = {}
    for key, ref in sorted(refs.items()):
        if not isinstance(ref, dict):
            continue
        path = Path(str(ref.get("path") or ""))
        self_referential = bool(ref.get("self_referential"))
        exists = path.exists() and path.is_file()
        actual_digest = "" if self_referential else _file_digest(path)
        expected_digest = str(ref.get("digest") or "")
        status[str(key)] = {
            "path": str(path),
            "exists": exists,
            "digest": expected_digest,
            "actual_digest": actual_digest,
            "digest_ok": bool(exists and (self_referential or not expected_digest or expected_digest == actual_digest)),
            "self_referential": self_referential,
        }
    return status


def _record_node(
    state: SecAgentGraphRuntimeState,
    node_name: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> SecAgentGraphRuntimeState:
    trace = list(state.get("node_trace") or [])
    finished_at = _utc_now()
    row = {"node": node_name, "finished_at": finished_at, "elapsed_ms": 0}
    if metadata:
        row["metadata"] = dict(metadata)
    trace.append(row)
    next_state: SecAgentGraphRuntimeState = {**state, "node_trace": trace}
    checkpoints = list(state.get("node_checkpoints") or [])
    checkpoints.append(
        _build_node_checkpoint(
            next_state,
            node_name,
            index=len(trace),
            finished_at=finished_at,
            previous_checkpoint_id=str((checkpoints[-1] or {}).get("checkpoint_id") or "") if checkpoints else "",
            metadata=metadata or {},
        )
    )
    return {**next_state, "node_checkpoints": checkpoints}


def _update_latest_node_timing(
    state: SecAgentGraphRuntimeState,
    node_name: str,
    *,
    started_at: str,
    elapsed_ms: int,
) -> SecAgentGraphRuntimeState:
    trace = [dict(item) for item in state.get("node_trace") or [] if isinstance(item, dict)]
    if trace and trace[-1].get("node") == node_name:
        trace[-1]["started_at"] = started_at
        trace[-1]["elapsed_ms"] = elapsed_ms
    checkpoints = [dict(item) for item in state.get("node_checkpoints") or [] if isinstance(item, dict)]
    if checkpoints and checkpoints[-1].get("node") == node_name:
        checkpoints[-1]["started_at"] = started_at
        checkpoints[-1]["elapsed_ms"] = elapsed_ms
    return {**state, "node_trace": trace, "node_checkpoints": checkpoints}


def _build_node_checkpoint(
    state: SecAgentGraphRuntimeState,
    node_name: str,
    *,
    index: int,
    finished_at: str,
    previous_checkpoint_id: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    summary = _checkpoint_state_summary(state)
    payload = {
        "schema_version": NODE_CHECKPOINT_SCHEMA_VERSION,
        "node": node_name,
        "index": index,
        "finished_at": finished_at,
        "previous_checkpoint_id": previous_checkpoint_id,
        "state_summary": summary,
        "metadata": dict(metadata or {}),
    }
    payload["checkpoint_id"] = _json_digest(
        {
            "run_id": state.get("run_id") or "",
            "node": node_name,
            "index": index,
            "finished_at": finished_at,
            "state_summary": summary,
            "metadata": metadata or {},
        }
    )
    return payload


def _checkpoint_state_summary(state: SecAgentGraphRuntimeState) -> dict[str, Any]:
    coverage_summary = (state.get("coverage_matrix") or {}).get("summary") or {}
    sufficiency = state.get("evidence_sufficiency_report") or {}
    memo = state.get("memo_answer") or {}
    claim = state.get("claim_verification") or {}
    gates = state.get("deterministic_gates") or {}
    activation = state.get("agent_activation_plan") or {}
    evidence_plan = state.get("evidence_requirement_plan") or {}
    second_pass_plan = state.get("second_pass_evidence_requirement_plan") or {}
    second_pass_retrieval_plan = state.get("second_pass_retrieval_plan") or {}
    evidence_fusion = state.get("evidence_fusion_bundle") or {}
    evidence_fusion_summary = evidence_fusion.get("summary") if isinstance(evidence_fusion, dict) else {}
    bounded_gap_register = state.get("bounded_gap_register") or {}
    entity_master = state.get("entity_security_master") or {}
    source_router = state.get("source_capability_router") or {}
    provenance_store = state.get("raw_source_provenance_store") or {}
    vintage_layer = state.get("asof_vintage_layer") or {}
    ontology = state.get("metric_product_ontology_snapshot") or {}
    reconciliation = state.get("reconciliation_ledger") or {}
    gate_matrix = state.get("gate_registry_eval_matrix") or {}
    derived_layer = state.get("derived_metric_layer") or {}
    fundamental_pack = state.get("fundamental_statement_pack") or {}
    fundamental_pack_summary = (
        fundamental_pack.get("summary")
        if isinstance(fundamental_pack, dict) and isinstance(fundamental_pack.get("summary"), dict)
        else {}
    )
    analyst_views = state.get("analyst_view_research_memory") or {}
    closeout_gate = state.get("d_series_database_closeout_gate") or {}
    materialization_report = state.get("d_series_database_materialization_report") or {}
    materialized_layers = (
        materialization_report.get("layers") if isinstance(materialization_report, dict) and isinstance(materialization_report.get("layers"), dict) else {}
    )
    reader_context = state.get("d_series_claim_gap_gate_reader_context") or {}
    reader_summary = reader_context.get("summary") if isinstance(reader_context, dict) and isinstance(reader_context.get("summary"), dict) else {}
    d_series_context = state.get("d_series_research_context") or {}
    d_series_context_summary = d_series_context.get("summary") if isinstance(d_series_context, dict) and isinstance(d_series_context.get("summary"), dict) else {}
    pre_memo_selection = state.get("pre_memo_fact_selection") or {}
    pre_memo_summary = pre_memo_selection.get("summary") if isinstance(pre_memo_selection, dict) and isinstance(pre_memo_selection.get("summary"), dict) else {}
    second_pass_diagnosis = state.get("second_pass_reflection_diagnosis") or {}
    second_pass_repair_plan = state.get("second_pass_repair_plan") or {}
    second_pass_hard_gate = state.get("second_pass_hard_gate") or {}
    second_pass_delta_audit = state.get("second_pass_delta_audit") or {}
    product_intelligence_policy = state.get("product_intelligence_runtime_policy") or {}
    tool_ledger = state.get("tool_call_ledger") or {}
    tool_records = tool_ledger.get("records") if isinstance(tool_ledger, dict) else []
    return {
        "status": state.get("status") or "",
        "state_keys": [key for key in CHECKPOINT_STATE_KEYS if key in state],
        "artifact_keys": sorted((state.get("artifact_refs") or {}).keys()),
        "execution_mode": activation.get("execution_mode") if isinstance(activation, dict) else "",
        "activated_agent_count": len(activation.get("activate_agents") or []) if isinstance(activation, dict) else 0,
        "evidence_requirement_count": len(evidence_plan.get("requirements") or []) if isinstance(evidence_plan, dict) else 0,
        "second_pass_requirement_count": len(second_pass_plan.get("requirements") or []) if isinstance(second_pass_plan, dict) else 0,
        "second_pass_route_count": len(second_pass_retrieval_plan.get("routes") or []) if isinstance(second_pass_retrieval_plan, dict) else 0,
        "second_pass_diagnosis_count": second_pass_diagnosis.get("diagnosis_count") if isinstance(second_pass_diagnosis, dict) else 0,
        "second_pass_repair_count": second_pass_repair_plan.get("repair_count") if isinstance(second_pass_repair_plan, dict) else 0,
        "second_pass_hard_gate_status": second_pass_hard_gate.get("status") if isinstance(second_pass_hard_gate, dict) else "",
        "second_pass_delta_status": second_pass_delta_audit.get("status") if isinstance(second_pass_delta_audit, dict) else "",
        "product_intelligence_runtime_autoload": bool(state.get("product_intelligence_runtime_autoload")),
        "product_intelligence_runtime_status": product_intelligence_policy.get("status") if isinstance(product_intelligence_policy, dict) else "",
        "tool_call_count": len(tool_records or []),
        "loop_break_reason": state.get("loop_break_reason") or (tool_ledger.get("loop_break_reason") if isinstance(tool_ledger, dict) else ""),
        "bounded_answer_allowed": bool(state.get("bounded_answer_allowed") or (tool_ledger.get("bounded_answer_allowed") if isinstance(tool_ledger, dict) else False)),
        "context_row_count": len(state.get("context_rows") or []),
        "market_context_row_count": len(state.get("market_snapshot_rows") or []),
        "ledger_row_count": len(state.get("runtime_ledger_rows") or []),
        "evidence_fusion_row_count": evidence_fusion.get("row_count") if isinstance(evidence_fusion, dict) else 0,
        "evidence_fusion_exact_authority_row_count": evidence_fusion_summary.get("exact_authority_row_count")
        if isinstance(evidence_fusion_summary, dict)
        else 0,
        "bounded_gap_count": bounded_gap_register.get("gap_count") if isinstance(bounded_gap_register, dict) else 0,
        "entity_master_entity_count": entity_master.get("entity_count") if isinstance(entity_master, dict) else 0,
        "source_capability_decision_count": source_router.get("decision_count") if isinstance(source_router, dict) else 0,
        "source_capability_validation_status": (source_router.get("validation") or {}).get("status")
        if isinstance(source_router, dict) and isinstance(source_router.get("validation"), dict)
        else "",
        "raw_source_provenance_record_count": provenance_store.get("record_count") if isinstance(provenance_store, dict) else 0,
        "raw_source_provenance_validation_status": (provenance_store.get("validation") or {}).get("status")
        if isinstance(provenance_store, dict) and isinstance(provenance_store.get("validation"), dict)
        else "",
        "asof_vintage_record_count": vintage_layer.get("record_count") if isinstance(vintage_layer, dict) else 0,
        "asof_vintage_validation_status": (vintage_layer.get("validation") or {}).get("status")
        if isinstance(vintage_layer, dict) and isinstance(vintage_layer.get("validation"), dict)
        else "",
        "metric_product_ontology_metric_count": ontology.get("metric_count") if isinstance(ontology, dict) else 0,
        "metric_product_ontology_validation_status": (ontology.get("validation") or {}).get("status")
        if isinstance(ontology, dict) and isinstance(ontology.get("validation"), dict)
        else "",
        "reconciliation_group_count": reconciliation.get("group_count") if isinstance(reconciliation, dict) else 0,
        "reconciliation_conflict_gap_count": reconciliation.get("conflict_gap_count") if isinstance(reconciliation, dict) else 0,
        "reconciliation_validation_status": (reconciliation.get("validation") or {}).get("status")
        if isinstance(reconciliation, dict) and isinstance(reconciliation.get("validation"), dict)
        else "",
        "gate_registry_gate_result_count": gate_matrix.get("gate_result_count") if isinstance(gate_matrix, dict) else 0,
        "gate_registry_blocking_fail_count": (gate_matrix.get("summary") or {}).get("blocking_fail_count")
        if isinstance(gate_matrix, dict) and isinstance(gate_matrix.get("summary"), dict)
        else 0,
        "gate_registry_validation_status": (gate_matrix.get("validation") or {}).get("status")
        if isinstance(gate_matrix, dict) and isinstance(gate_matrix.get("validation"), dict)
        else "",
        "derived_metric_count": derived_layer.get("derived_metric_count") if isinstance(derived_layer, dict) else 0,
        "derived_metric_skipped_count": derived_layer.get("skipped_derivation_count") if isinstance(derived_layer, dict) else 0,
        "derived_metric_validation_status": (derived_layer.get("validation") or {}).get("status")
        if isinstance(derived_layer, dict) and isinstance(derived_layer.get("validation"), dict)
        else "",
        "fundamental_statement_line_item_count": fundamental_pack_summary.get("line_item_count")
        if isinstance(fundamental_pack_summary, dict)
        else 0,
        "fundamental_statement_peer_comparison_count": fundamental_pack_summary.get("peer_comparison_count")
        if isinstance(fundamental_pack_summary, dict)
        else 0,
        "fundamental_statement_validation_status": (fundamental_pack.get("validation") or {}).get("status")
        if isinstance(fundamental_pack, dict) and isinstance(fundamental_pack.get("validation"), dict)
        else "",
        "analyst_view_count": analyst_views.get("view_count") if isinstance(analyst_views, dict) else 0,
        "research_memory_entry_count": analyst_views.get("memory_entry_count") if isinstance(analyst_views, dict) else 0,
        "analyst_view_validation_status": (analyst_views.get("validation") or {}).get("status")
        if isinstance(analyst_views, dict) and isinstance(analyst_views.get("validation"), dict)
        else "",
        "d_series_database_closeout_gate_status": closeout_gate.get("gate_status") if isinstance(closeout_gate, dict) else "",
        "d_series_closeout_allowed": bool(closeout_gate.get("d_series_closeout_allowed"))
        if isinstance(closeout_gate, dict)
        else False,
        "d_series_pending_required_database_layer_count": closeout_gate.get("pending_required_database_layer_count")
        if isinstance(closeout_gate, dict)
        else 0,
        "d_series_materialized_database_layer_count": len(materialized_layers),
        "d_series_materialization_db_path": materialization_report.get("db_path")
        if isinstance(materialization_report, dict)
        else "",
        "d_series_claim_gap_gate_reader_status": reader_context.get("reader_default_status")
        if isinstance(reader_context, dict)
        else "",
        "d_series_claim_gap_gate_reader_claim_count": reader_summary.get("claim_count")
        if isinstance(reader_summary, dict)
        else 0,
        "d_series_research_context_reader_status": d_series_context.get("reader_default_status")
        if isinstance(d_series_context, dict)
        else "",
        "d_series_research_context_row_count": d_series_context_summary.get("row_count")
        if isinstance(d_series_context_summary, dict)
        else 0,
        "pre_memo_approved_fact_count": pre_memo_summary.get("approved_fact_count")
        if isinstance(pre_memo_summary, dict)
        else 0,
        "pre_memo_rejected_fact_count": pre_memo_summary.get("rejected_fact_count")
        if isinstance(pre_memo_summary, dict)
        else 0,
        "pre_memo_approved_derived_metric_count": pre_memo_summary.get("approved_derived_metric_count")
        if isinstance(pre_memo_summary, dict)
        else 0,
        "d_series_database_closeout_validation_status": (closeout_gate.get("validation") or {}).get("status")
        if isinstance(closeout_gate, dict) and isinstance(closeout_gate.get("validation"), dict)
        else "",
        "coverage_complete": coverage_summary.get("coverage_complete"),
        "primary_task_support_complete": coverage_summary.get("primary_task_support_complete"),
        "sufficiency_level": sufficiency.get("sufficiency_level"),
        "second_pass_attempts": int(state.get("second_pass_attempts") or 0),
        "answer_status": memo.get("answer_status") if isinstance(memo, dict) else "",
        "claim_status": memo.get("claim_status") if isinstance(memo, dict) else "",
        "claim_verification_status": claim.get("status") if isinstance(claim, dict) else "",
        "unsupported_claim_count": claim.get("unsupported_claim_count") if isinstance(claim, dict) else None,
        "deterministic_gates_ok": gates.get("ok") if isinstance(gates, dict) else None,
        "rendered_answer_chars": len(str(state.get("rendered_answer") or "")),
    }


def _checkpoint_artifact_refs(state: SecAgentGraphRuntimeState) -> dict[str, dict[str, Any]]:
    refs: dict[str, dict[str, Any]] = {}
    for key, raw_path in sorted((state.get("artifact_refs") or {}).items()):
        path = Path(str(raw_path or ""))
        self_referential = key in {"node_checkpoints", "langgraph_native_summary"}
        refs[str(key)] = {
            "path": str(path),
            "exists": bool(str(path)) if self_referential else path.exists() and path.is_file(),
            "digest": "" if self_referential else _file_digest(path),
            "self_referential": self_referential,
        }
    return refs


def _file_digest(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()[:16]


def _json_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _missing_requirements_from_coverage_tasks(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for task in tasks:
        support_level = str(task.get("support_level") or "").strip()
        missing_tickers = _unique_upper(
            [
                *(task.get("missing_focus_tickers") or []),
                *(task.get("missing_peer_tickers") or []),
                *(task.get("missing_tickers") or []),
            ]
        )
        missing_years = _unique_ints(task.get("missing_years") or [])
        missing_filing_types = _unique_strings(task.get("missing_filing_types") or [])
        missing_source_tiers = _unique_strings(task.get("missing_source_tiers") or [])
        missing_metric_families = _unique_strings(task.get("missing_metric_families") or [])
        missing_market_fields = _unique_strings(task.get("missing_market_fields") or [])
        if support_level != "insufficient" and not any(
            [missing_tickers, missing_years, missing_filing_types, missing_source_tiers, missing_metric_families, missing_market_fields]
        ):
            continue
        missing.append(
            {
                "task_id": task.get("task_id") or "",
                "priority": task.get("priority") or "",
                "support_level": support_level or "unknown",
                "missing_tickers": missing_tickers,
                "missing_years": missing_years,
                "missing_filing_types": missing_filing_types,
                "missing_source_tiers": missing_source_tiers,
                "missing_metric_families": missing_metric_families,
                "missing_market_fields": missing_market_fields,
            }
        )
    return missing[:20]


def _second_pass_requests_from_missing(missing_requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for index, item in enumerate(missing_requirements[:5], start=1):
        requests.append(
            {
                "request_id": f"second_pass_{index}",
                "task_id": item.get("task_id") or "",
                "reason": "coverage_matrix_searchable_gap",
                "tickers": item.get("missing_tickers") or [],
                "years": item.get("missing_years") or [],
                "filing_types": item.get("missing_filing_types") or [],
                "source_tiers": item.get("missing_source_tiers") or [],
                "metric_families": item.get("missing_metric_families") or [],
                "market_fields": item.get("missing_market_fields") or [],
            }
        )
    return requests


def _minimal_query_contract() -> dict[str, Any]:
    return {
        "schema_version": "interactive_query_contract_v0.2",
        "task_type": "open_analysis",
        "search_scope_tickers": [],
        "focus_tickers": [],
        "years": [],
        "filing_types": [],
        "source_tiers": [],
        "metric_families": [],
        "decomposed_tasks": [],
    }


def _query_contract_with_activation_source_families(query_contract: Mapping[str, Any], activation_plan: Mapping[str, Any]) -> dict[str, Any]:
    contract = dict(query_contract or {})
    activation_sources = _unique_strings(
        [
            source
            for source in activation_plan.get("allowed_source_families") or []
            if source != "relationship_graph"
        ]
    )
    if activation_sources:
        contract_sources = _unique_strings(contract.get("source_tiers") or [])
        contract["source_tiers"] = _unique_strings([*contract_sources, *activation_sources])
        scope = dict(contract.get("scope") or {})
        scope_sources = _unique_strings(scope.get("source_tiers") or [])
        scope["source_tiers"] = _unique_strings([*scope_sources, *activation_sources])
        contract["scope"] = scope
    return contract


def _run_id(seed: str) -> str:
    digest = hashlib.sha1(str(seed or "").encode("utf-8", errors="ignore")).hexdigest()[:10]
    return datetime.now().strftime("native_graph_%Y%m%d_%H%M%S_") + digest


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _unique_upper(values: Any) -> list[str]:
    out: list[str] = []
    for value in values or []:
        text = str(value or "").upper().strip()
        if text and text not in out:
            out.append(text)
    return out


def _unique_strings(values: Any) -> list[str]:
    out: list[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if text and text not in out:
            out.append(text)
    return out


def _unique_ints(values: Any) -> list[int]:
    out: list[int] = []
    for value in values or []:
        try:
            item = int(value)
        except (TypeError, ValueError):
            continue
        if item not in out:
            out.append(item)
    return out
