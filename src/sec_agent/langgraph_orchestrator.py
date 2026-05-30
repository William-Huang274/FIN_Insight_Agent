from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypedDict

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

SCOPE_MODES = {"full_universe", "sector_representative", "focused_peer"}
NODE_CHECKPOINT_SCHEMA_VERSION = "sec_agent_langgraph_node_checkpoint_v0.1"
NODE_CHECKPOINT_ARTIFACT_SCHEMA_VERSION = "sec_agent_langgraph_node_checkpoint_artifact_v0.1"
NODE_CHECKPOINT_RESUME_INSPECTION_SCHEMA_VERSION = "sec_agent_langgraph_checkpoint_resume_inspection_v0.1"
NATIVE_STATE_HYDRATION_SCHEMA_VERSION = "sec_agent_langgraph_native_state_hydration_v0.1"
CHECKPOINT_STATE_KEYS = (
    "query_contract",
    "retrieval_plan",
    "context_rows",
    "market_snapshot_rows",
    "industry_snapshot_rows",
    "runtime_ledger_rows",
    "coverage_matrix",
    "evidence_sufficiency_report",
    "second_pass_result",
    "judgment_plan",
    "memo_answer",
    "claim_verification",
    "deterministic_gates",
    "rendered_answer",
)
CHECKPOINT_LARGE_PAYLOAD_CHANNELS = {
    "context_rows",
    "market_snapshot_rows",
    "industry_snapshot_rows",
    "runtime_ledger_rows",
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
    planner_trace: dict[str, Any]
    project_inventory: dict[str, Any]
    selected_tickers: list[str]
    selected_years: list[int]
    retrieval_plan: dict[str, Any]
    context_rows: list[dict[str, Any]]
    market_snapshot_rows: list[dict[str, Any]]
    industry_snapshot_rows: list[dict[str, Any]]
    runtime_ledger_rows: list[dict[str, Any]]
    coverage_matrix: dict[str, Any]
    retrieval_trace: dict[str, Any]
    context_runtime: dict[str, Any]
    evidence_sufficiency_report: dict[str, Any]
    second_pass_attempts: int
    second_pass_result: dict[str, Any]
    judgment_plan: dict[str, Any]
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
        lambda state: "stop" if _is_stopped_after_node(state) else "continue",
        {"stop": END, "continue": target},
    )


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
    return _record_node({**state, "status": "running"}, "load_session_state")


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
    return _record_node({**state, "retrieval_plan": plan}, "compile_retrieval_plan")


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
    return {
        "status": state.get("status") or "",
        "state_keys": [key for key in CHECKPOINT_STATE_KEYS if key in state],
        "artifact_keys": sorted((state.get("artifact_refs") or {}).keys()),
        "context_row_count": len(state.get("context_rows") or []),
        "market_context_row_count": len(state.get("market_snapshot_rows") or []),
        "ledger_row_count": len(state.get("runtime_ledger_rows") or []),
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
