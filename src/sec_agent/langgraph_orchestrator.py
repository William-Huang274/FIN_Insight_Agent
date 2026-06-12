from __future__ import annotations

import hashlib
import json
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
)
from sec_agent.derived_metric_layer import build_derived_metric_layer
from sec_agent.entity_master import build_entity_security_master
from sec_agent.gate_registry import build_gate_registry_eval_matrix
from sec_agent.mcp_tool_registry import invoke_mcp_tool
from sec_agent.metric_product_ontology import build_metric_product_ontology_snapshot
from sec_agent.multi_agent_contracts import (
    aggregate_focused_answer_judgment_plan,
    aggregate_specialist_judgment_plan,
    build_multi_agent_memo_draft,
    ledger_metric_display_value,
    build_stub_specialist_memolets,
    normalize_universe_relationship_plan,
    repair_multi_agent_memo_draft,
    validate_universe_relationship_plan,
    verify_multi_agent_memo_draft,
    verify_specialist_outputs_for_memo,
)
from sec_agent.multi_agent_router import route_multi_agent_activation
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
    reflection_report_from_tool_observations,
    should_execute_second_pass,
    specialist_activation_decisions,
    validate_operator_tool_call,
)
from sec_agent.provenance_vintage import build_provenance_vintage_layers
from sec_agent.reconciliation_ledger import build_metric_ontology_and_reconciliation_layers, build_reconciliation_ledger
from sec_agent.relationship_graph import relationship_plan_from_lookup
from sec_agent.source_capability_router import build_source_capability_router
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
    "raw_source_provenance_store",
    "asof_vintage_layer",
    "metric_product_ontology_snapshot",
    "reconciliation_ledger",
    "gate_registry_eval_matrix",
    "derived_metric_layer",
    "analyst_view_research_memory",
    "d_series_database_materialization",
    "d_series_database_materialization_report",
    "d_series_claim_gap_gate_reader_context",
    "d_series_database_closeout_gate",
    "evidence_sufficiency_report",
    "second_pass_result",
    "second_pass_evidence_requirement_plan",
    "second_pass_retrieval_plan",
    "second_pass_reflection_diagnosis",
    "second_pass_repair_plan",
    "second_pass_hard_gate",
    "second_pass_delta_audit",
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
    "specialist_verification",
    "specialist_fanout_barrier",
    "claim_card_store_barrier",
    "adjudicator_barrier",
    "research_lead_route_status",
    "research_lead_failure_reason",
    "research_lead_validation",
    "research_lead_rejected_plan",
    "research_lead_model_diagnostics",
    "universe_relationship_model_diagnostics",
    "universe_relationship_routing_trace",
    "specialist_route_results",
    "memo_route_result",
    "multi_agent_summary",
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
    "raw_source_provenance_store",
    "asof_vintage_layer",
    "metric_product_ontology_snapshot",
    "reconciliation_ledger",
    "gate_registry_eval_matrix",
    "derived_metric_layer",
    "analyst_view_research_memory",
    "d_series_database_materialization_report",
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
    output_dir: str
    query_contract: dict[str, Any]
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
    plan_reflection_report: dict[str, Any]
    multi_agent_routing_trace: dict[str, Any]
    agent_registry_snapshot: dict[str, Any]
    research_lead_route_status: str
    research_lead_failure_reason: str
    research_lead_validation: dict[str, Any]
    research_lead_rejected_plan: dict[str, Any]
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
    raw_source_provenance_store: dict[str, Any]
    asof_vintage_layer: dict[str, Any]
    metric_product_ontology_snapshot: dict[str, Any]
    reconciliation_ledger: dict[str, Any]
    gate_registry_eval_matrix: dict[str, Any]
    derived_metric_layer: dict[str, Any]
    analyst_view_research_memory: dict[str, Any]
    d_series_governance_db_path: str
    d_series_database_path: str
    d_series_database_materialization: dict[str, Any]
    d_series_database_materialization_report: dict[str, Any]
    d_series_claim_gap_gate_reader_context: dict[str, Any]
    d_series_database_closeout_gate: dict[str, Any]
    claim_evidence_ledger: dict[str, Any]
    typed_gap_ledger: dict[str, Any]
    evidence_operator_fanout_plan: dict[str, Any]
    evidence_operator_fanout_barrier: dict[str, Any]
    specialist_outputs: list[dict[str, Any]]
    specialist_verification: dict[str, Any]
    specialist_fanout_barrier: dict[str, Any]
    claim_card_store_barrier: dict[str, Any]
    adjudicator_barrier: dict[str, Any]
    relationship_graph_observation: dict[str, Any]
    universe_relationship_plan: dict[str, Any]
    universe_relationship_validation: dict[str, Any]
    research_lead_model_diagnostics: dict[str, Any]
    universe_relationship_model_diagnostics: dict[str, Any]
    universe_relationship_routing_trace: dict[str, Any]
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
    return _record_node(
        next_state,
        "load_session_state",
        metadata={
            "d_series_reader_status": reader_context.get("reader_default_status") if isinstance(reader_context, dict) else "",
            "d_series_reader_claim_count": (reader_context.get("summary") or {}).get("claim_count")
            if isinstance(reader_context, dict) and isinstance(reader_context.get("summary"), dict)
            else 0,
        },
    )


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
    next_state: SecAgentGraphRuntimeState = {
        **state,
        "agent_activation_plan": dict(plan or {}),
        "agent_registry_snapshot": {"agents": agent_registry_by_id()},
        "research_lead_route_status": result.get("status") or "",
        "research_lead_failure_reason": result.get("failure_reason") or "",
        "research_lead_validation": dict(result.get("validation") or {}) if isinstance(result.get("validation"), dict) else {},
        "research_lead_rejected_plan": dict(result.get("rejected_plan") or {}) if isinstance(result.get("rejected_plan"), dict) else {},
        "loop_budget_state": dict(result.get("loop_budget") or state.get("loop_budget_state") or LoopBudget().to_dict()),
        "tool_call_ledger": dict(state.get("tool_call_ledger") or ToolCallLedger().to_dict()),
        "agent_trace": [
            *(state.get("agent_trace") or []),
            {
                "node": "research_lead_plan",
                "agent_id": "research_lead",
                "execution_mode": (plan or {}).get("execution_mode") if isinstance(plan, dict) else "",
                "source": result.get("source") or "injected",
            },
        ],
    }
    if isinstance(result.get("evidence_requirement_plan"), dict) and result.get("evidence_requirement_plan"):
        next_state["evidence_requirement_plan"] = result["evidence_requirement_plan"]  # type: ignore[literal-required]
    if isinstance(result.get("routing_trace"), dict):
        next_state["multi_agent_routing_trace"] = result["routing_trace"]  # type: ignore[literal-required]
    if isinstance(result.get("model_diagnostics"), dict):
        next_state["research_lead_model_diagnostics"] = result["model_diagnostics"]  # type: ignore[literal-required]
    return _record_node(next_state, "research_lead_plan", metadata={"mode": "injected" if route_activation else "deterministic_mock"})


def _node_validate_activation_plan(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    validation = validate_agent_activation_plan(
        state.get("agent_activation_plan") or {},
        known_agent_ids=set(agent_registry_by_id()),
        allowed_source_families=allowed_source_families(),
        agent_registry=agent_registry_by_id(),
        global_limits=state.get("loop_budget_state") or {},
    )
    next_state: SecAgentGraphRuntimeState = {
        **state,
        "agent_activation_validation": validation,
        "agent_activation_plan": dict(validation.get("plan") or state.get("agent_activation_plan") or {}),
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
    lookup_args = {
        "focus_tickers": activation.get("focus_tickers") or contract.get("focus_tickers") or state.get("selected_tickers") or [],
        "search_scope_tickers": activation.get("search_scope_tickers") or contract.get("search_scope_tickers") or state.get("selected_tickers") or [],
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

    if expand_universe_relationship is not None:
        result = expand_universe_relationship(state_with_lookup)
        plan = result.get("universe_relationship_plan") if isinstance(result.get("universe_relationship_plan"), dict) else result.get("plan")
        validation = result.get("universe_relationship_validation") if isinstance(result.get("universe_relationship_validation"), dict) else {}
        source = result.get("source") or "injected"
        model_diagnostics = result.get("model_diagnostics") if isinstance(result.get("model_diagnostics"), dict) else {}
        routing_trace = result.get("routing_trace") if isinstance(result.get("routing_trace"), dict) else {}
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
    if validation.get("status") != "pass":
        next_state["bounded_answer_allowed"] = True
        next_state["loop_break_reason"] = "invalid_universe_relationship_plan"
    return _record_node(
        next_state,
        "universe_relationship_expand",
        metadata={"mode": source, "validation_status": validation.get("status"), "relationship_count": len(accepted_plan.get("relationships") or [])},
    )


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
    if not entity_master:
        entity_master = build_entity_security_master(state)
    if not source_router:
        source_router = build_source_capability_router(state)
    return {**state, "entity_security_master": entity_master, "source_capability_router": source_router}


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
        "source_gaps": [*(state.get("source_gaps") or []), *(result.get("source_gaps") or [])],
        "evidence_operator_fanout_plan": result.get("evidence_operator_fanout_plan") or state.get("evidence_operator_fanout_plan") or {},
        "evidence_operator_fanout_barrier": result.get("fanout_barrier") or state.get("evidence_operator_fanout_barrier") or {},
        "loop_break_reason": str(result.get("loop_break_reason") or state.get("loop_break_reason") or ""),
        "bounded_answer_allowed": bool(result.get("bounded_answer_allowed") or state.get("bounded_answer_allowed") or False),
    }
    return _record_node(
        next_state,
        "execute_evidence_operators",
        metadata={
            "tool_observation_count": len(result.get("tool_observations") or []),
            "evidence_operator_mode": "dry_run" if dry_run else "real",
            "fanout_enabled": bool(result.get("fanout_barrier")),
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
        next_state = {
            **next_state_for_fusion,
            "evidence_fusion_bundle": after_fusion,
            "bounded_gap_register": after_fusion.get("bounded_gap_register") if isinstance(after_fusion.get("bounded_gap_register"), dict) else {},
            "second_pass_delta_audit": delta_audit,
            "quality_second_pass_attempted": bool(compiled_state.get("quality_second_pass_attempted") or quality_triggered),
        }
        return _record_node(
            next_state,
            "optional_second_pass",
            metadata={
                "mode": "injected",
                "delta_status": delta_audit.get("status"),
                "added_authority_bearing_row_count": delta_audit.get("added_authority_bearing_row_count"),
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
        {
            "agent_id": row.get("agent_id") or "",
            "status": row.get("decision") or "",
            "priority": row.get("priority") or "",
            "failure_reason": "" if row.get("decision") == "run" else str(row.get("reason") or "")[:500],
            "activation_policy": row.get("policy") or "",
            "signal_count": row.get("signal_count"),
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


def _specialist_fanout_barrier(route_results: Any, outputs: Any, *, execution_mode: str) -> dict[str, Any]:
    routes = [dict(item) for item in route_results or [] if isinstance(item, Mapping)]
    output_rows = [dict(item) for item in outputs or [] if isinstance(item, Mapping)]
    failed = [
        row
        for row in routes
        if str(row.get("status") or "") not in {"pass", "run", "stubbed", "skipped"}
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
    result = {
        **result,
        **governance_ledgers,
        "claim_card_store_barrier": _claim_card_store_barrier(
            result.get("specialist_outputs") or specialist_outputs,
            result.get("specialist_verification") or specialist_verification,
            result.get("verified_judgment_plan") or result.get("judgment_plan") or judgment,
            governance_ledgers.get("claim_evidence_ledger") if isinstance(governance_ledgers, Mapping) else {},
        ),
        "adjudicator_barrier": _adjudicator_barrier(result.get("verified_judgment_plan") or result.get("judgment_plan") or judgment),
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


def _claim_card_store_barrier(
    outputs: Any,
    verification: Mapping[str, Any],
    judgment: Mapping[str, Any],
    claim_evidence_ledger: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    output_rows = [dict(item) for item in outputs or [] if isinstance(item, Mapping)]
    supported = [dict(item) for item in judgment.get("supported_claims") or [] if isinstance(item, Mapping)]
    unsupported = [dict(item) for item in judgment.get("unsupported_claims") or [] if isinstance(item, Mapping)]
    conflicts = [dict(item) for item in judgment.get("conflicts") or [] if isinstance(item, Mapping)]
    ledger = claim_evidence_ledger if isinstance(claim_evidence_ledger, Mapping) else {}
    ledger_summary = ledger.get("summary") if isinstance(ledger.get("summary"), Mapping) else {}
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


def _render_memo_answer(memo: Mapping[str, Any], *, bounded: bool) -> str:
    parts: list[str] = []
    direct = str(memo.get("direct_answer") or "No deterministic memo text was generated.").strip()
    profile = memo.get("memo_profile") if isinstance(memo.get("memo_profile"), Mapping) else {}
    labels = _memo_render_labels(memo)
    rendered_claim_max = int(profile.get("rendered_claim_max") or (5 if bounded else 8))
    if direct:
        parts.append(direct)

    claim_lines = _render_memo_claim_lines(
        memo.get("memo_claims") or memo.get("supported_claims") or [],
        max_items=rendered_claim_max,
        ref_label=labels["refs"],
    )
    if claim_lines:
        parts.append(f"{labels['claims']}:\n" + "\n".join(claim_lines))

    implications = _render_loose_memo_items(memo.get("investment_implications") or [], max_items=5)
    if implications:
        parts.append(f"{labels['investment_implications']}:\n" + "\n".join(f"- {item}" for item in implications))

    change_view = _render_loose_memo_items(memo.get("what_would_change_view") or [], max_items=4)
    if change_view:
        parts.append(f"{labels['what_would_change_view']}:\n" + "\n".join(f"- {item}" for item in change_view))

    monitoring = _render_loose_memo_items(memo.get("monitoring_items") or [], max_items=5)
    if monitoring:
        parts.append(f"{labels['monitoring_items']}:\n" + "\n".join(f"- {item}" for item in monitoring))

    evidence_gaps = _render_loose_memo_items(memo.get("evidence_gaps_but_actionable") or [], max_items=4)
    if evidence_gaps:
        parts.append(f"{labels['evidence_gaps']}:\n" + "\n".join(f"- {item}" for item in evidence_gaps))

    caveats = _render_loose_memo_items(memo.get("caveats") or [], max_items=3)
    if caveats:
        parts.append(f"{labels['caveats']}:\n" + "\n".join(f"- {item}" for item in caveats))

    excluded = _render_loose_memo_items(memo.get("unsupported_claims_excluded") or [], max_items=2)
    if excluded:
        parts.append(f"{labels['unsupported_claims_excluded']}:\n" + "\n".join(f"- {item}" for item in excluded))

    boundary = str(memo.get("source_boundary") or "verified judgment plan only").strip()
    if boundary:
        parts.append(f"{labels['source_boundary']}: {boundary}")

    if bounded and str(memo.get("answer_status") or "") == "draft" and claim_lines:
        parts.append(labels["bounded_note"])
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
            "claims": "关键论据",
            "investment_implications": "投资含义",
            "what_would_change_view": "什么会改变判断",
            "monitoring_items": "后续跟踪",
            "evidence_gaps": "可行动的证据缺口",
            "caveats": "限制与注意事项",
            "unsupported_claims_excluded": "已排除的未证实说法",
            "source_boundary": "证据边界",
            "bounded_note": "边界说明：verifier 已在当前证据边界内接受该 thesis-led memo。",
            "refs": "证据",
        }
    return {
        "claims": "Key memo claims",
        "investment_implications": "Investment implications",
        "what_would_change_view": "What would change the view",
        "monitoring_items": "Monitoring items",
        "evidence_gaps": "Evidence gaps but actionable",
        "caveats": "Caveats",
        "unsupported_claims_excluded": "Unsupported claims excluded",
        "source_boundary": "Source boundary",
        "bounded_note": "Bounded evidence note: verifier accepted the thesis-led memo claims under the current source boundary.",
        "refs": "refs",
    }


def _render_memo_claim_lines(value: Any, *, max_items: int = 5, ref_label: str = "refs") -> list[str]:
    lines: list[str] = []
    for index, claim in enumerate(value if isinstance(value, list) else [], start=1):
        if not isinstance(claim, Mapping):
            continue
        text = str(claim.get("claim") or claim.get("text") or "").strip()
        if not text:
            continue
        claim_id = str(claim.get("claim_id") or "").strip()
        refs = [str(ref) for ref in claim.get("evidence_refs") or claim.get("refs") or [] if str(ref or "").strip()]
        id_text = f" [{claim_id}]" if claim_id else ""
        ref_text = f" {ref_label}={', '.join(refs[:4])}" if refs else ""
        lines.append(f"{index}. {text}{id_text}{ref_text}")
        if len(lines) >= max(1, max_items):
            break
    return lines


def _render_loose_memo_items(value: Any, *, max_items: int) -> list[str]:
    items: list[str] = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, Mapping):
            text = str(item.get("text") or item.get("claim") or item.get("reason") or item.get("type") or "").strip()
        else:
            text = str(item or "").strip()
        if text:
            items.append(text)
        if len(items) >= max_items:
            break
    return items


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
            result = {"rendered_answer": "Bounded answer only: memo verification failed under current evidence constraints."}
        elif bounded:
            if str(memo.get("answer_status") or "") == "draft" and memo.get("memo_claims"):
                result = {"rendered_answer": _render_memo_answer(memo, bounded=True)}
            else:
                result = {
                    "rendered_answer": "Bounded answer only: "
                    + str(memo.get("direct_answer") or "current evidence constraints block full memo generation.")
                }
        else:
            result = {"rendered_answer": _render_memo_answer(memo, bounded=False)}
    return _record_node({**state, **result}, "renderer", metadata={"mode": "injected" if renderer else "stub"})


def _node_multi_agent_persist_session_state(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    state_with_refs = _with_multi_agent_artifact_refs(_with_native_artifact_refs({**state, "status": "completed"}))
    state_with_layers = _state_with_d4_d5_layers(state_with_refs)
    state_with_reconciliation = _state_with_d6_d7_layers(state_with_layers)
    state_with_gates = _state_with_d9_gate_matrix(state_with_reconciliation)
    state_with_derived_metrics = _state_with_d10_derived_metric_layer(state_with_gates)
    state_with_analyst_views = _state_with_d11_analyst_view_layer(state_with_derived_metrics)
    state_with_materialization = _state_with_d12_1_database_materialization(state_with_analyst_views)
    state_with_closeout_gate = _state_with_d12_database_closeout_gate(state_with_materialization)
    final_state = _record_node(state_with_closeout_gate, "persist_session_state")
    _write_native_state_artifacts(final_state)
    _write_multi_agent_governance_ledger_artifacts(final_state)
    _write_multi_agent_summary_artifact(final_state)
    return final_state


def _state_with_d4_d5_layers(state: SecAgentGraphRuntimeState) -> SecAgentGraphRuntimeState:
    provenance_store = state.get("raw_source_provenance_store") if isinstance(state.get("raw_source_provenance_store"), dict) else {}
    vintage_layer = state.get("asof_vintage_layer") if isinstance(state.get("asof_vintage_layer"), dict) else {}
    if provenance_store and vintage_layer:
        return state
    layers = build_provenance_vintage_layers(state)
    if not provenance_store:
        provenance_store = layers.get("raw_source_provenance_store") if isinstance(layers.get("raw_source_provenance_store"), dict) else {}
    if not vintage_layer:
        vintage_layer = layers.get("asof_vintage_layer") if isinstance(layers.get("asof_vintage_layer"), dict) else {}
    return {**state, "raw_source_provenance_store": provenance_store, "asof_vintage_layer": vintage_layer}


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
    if isinstance(state.get("d_series_claim_gap_gate_reader_context"), dict):
        return state
    db_path = _d_series_governance_db_path(state)
    if db_path is None or not db_path.exists():
        return state
    tickers = _d_series_reader_tickers(state)
    try:
        reader_context = read_claim_gap_gate_research_context(db_path, tickers=tickers, limit=100)
    except Exception as exc:  # pragma: no cover - defensive against manually edited local sqlite files.
        reader_context = {
            "schema_version": "sec_agent_d_series_claim_gap_gate_reader_v0.1",
            "db_path": str(db_path.resolve()),
            "reader_default_status": "database_unavailable",
            "failure_reason": str(exc)[:500],
            "summary": {"claim_count": 0, "typed_gap_count": 0, "gate_history_count": 0},
        }
    context = dict(state.get("multi_agent_context") or {}) if isinstance(state.get("multi_agent_context"), Mapping) else {}
    context["d_series_claim_gap_gate_reader_context"] = reader_context
    return {**state, "multi_agent_context": context, "d_series_claim_gap_gate_reader_context": reader_context}


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
    if _multi_agent_specialists_active(state):
        return "specialists"
    return "aggregate"


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
        refs["multi_agent_summary"] = str((output_dir / "multi_agent_summary.json").resolve())
        refs["claim_evidence_ledger"] = str((output_dir / "claim_evidence_ledger.json").resolve())
        refs["typed_gap_ledger"] = str((output_dir / "typed_gap_ledger.json").resolve())
        refs["entity_security_master"] = str((output_dir / "entity_security_master.json").resolve())
        refs["source_capability_router"] = str((output_dir / "source_capability_router.json").resolve())
        refs["raw_source_provenance_store"] = str((output_dir / "raw_source_provenance_store.json").resolve())
        refs["asof_vintage_layer"] = str((output_dir / "asof_vintage_layer.json").resolve())
        refs["metric_product_ontology_snapshot"] = str((output_dir / "metric_product_ontology_snapshot.json").resolve())
        refs["reconciliation_ledger"] = str((output_dir / "reconciliation_ledger.json").resolve())
        refs["gate_registry_eval_matrix"] = str((output_dir / "gate_registry_eval_matrix.json").resolve())
        refs["derived_metric_layer"] = str((output_dir / "derived_metric_layer.json").resolve())
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


def _write_multi_agent_summary_artifact(state: SecAgentGraphRuntimeState) -> None:
    output_dir = Path(str(state.get("output_dir") or ""))
    if not output_dir:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "multi_agent_summary.json"
    payload = build_multi_agent_summary_artifact_payload(state)
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
    provenance_store = state.get("raw_source_provenance_store") if isinstance(state.get("raw_source_provenance_store"), dict) else {}
    vintage_layer = state.get("asof_vintage_layer") if isinstance(state.get("asof_vintage_layer"), dict) else {}
    ontology = state.get("metric_product_ontology_snapshot") if isinstance(state.get("metric_product_ontology_snapshot"), dict) else {}
    reconciliation = state.get("reconciliation_ledger") if isinstance(state.get("reconciliation_ledger"), dict) else {}
    gate_matrix = state.get("gate_registry_eval_matrix") if isinstance(state.get("gate_registry_eval_matrix"), dict) else {}
    derived_layer = state.get("derived_metric_layer") if isinstance(state.get("derived_metric_layer"), dict) else {}
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
    closeout_summary = closeout_gate.get("summary") if isinstance(closeout_gate.get("summary"), dict) else {}
    closeout_validation = closeout_gate.get("validation") if isinstance(closeout_gate.get("validation"), dict) else {}
    evidence_fanout_barrier = state.get("evidence_operator_fanout_barrier") if isinstance(state.get("evidence_operator_fanout_barrier"), dict) else {}
    specialist_fanout_barrier = state.get("specialist_fanout_barrier") if isinstance(state.get("specialist_fanout_barrier"), dict) else {}
    claim_card_store_barrier = state.get("claim_card_store_barrier") if isinstance(state.get("claim_card_store_barrier"), dict) else {}
    adjudicator_barrier = state.get("adjudicator_barrier") if isinstance(state.get("adjudicator_barrier"), dict) else {}
    project_inventory = state.get("project_inventory") if isinstance(state.get("project_inventory"), dict) else {}
    milvus_runtime = project_inventory.get("milvus_runtime") if isinstance(project_inventory.get("milvus_runtime"), dict) else {}
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
            },
            "universe_relationship": {
                "validation_status": universe_validation.get("status") if isinstance(universe_validation, dict) else "",
                "routing_trace": dict(state.get("universe_relationship_routing_trace") or {}),
                "diagnostics": _model_diagnostics_summary(state.get("universe_relationship_model_diagnostics")),
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
    analyst_views = state.get("analyst_view_research_memory") or {}
    closeout_gate = state.get("d_series_database_closeout_gate") or {}
    materialization_report = state.get("d_series_database_materialization_report") or {}
    materialized_layers = (
        materialization_report.get("layers") if isinstance(materialization_report, dict) and isinstance(materialization_report.get("layers"), dict) else {}
    )
    reader_context = state.get("d_series_claim_gap_gate_reader_context") or {}
    reader_summary = reader_context.get("summary") if isinstance(reader_context, dict) and isinstance(reader_context.get("summary"), dict) else {}
    second_pass_diagnosis = state.get("second_pass_reflection_diagnosis") or {}
    second_pass_repair_plan = state.get("second_pass_repair_plan") or {}
    second_pass_hard_gate = state.get("second_pass_hard_gate") or {}
    second_pass_delta_audit = state.get("second_pass_delta_audit") or {}
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
