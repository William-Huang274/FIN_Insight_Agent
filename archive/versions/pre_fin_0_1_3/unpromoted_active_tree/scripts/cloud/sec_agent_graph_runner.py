from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

try:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.graph import END, START, StateGraph
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without optional dependency.
    InMemorySaver = None  # type: ignore[assignment]
    END = None  # type: ignore[assignment]
    START = None  # type: ignore[assignment]
    StateGraph = None  # type: ignore[assignment]
    LANGGRAPH_IMPORT_ERROR = exc
else:
    LANGGRAPH_IMPORT_ERROR = None

from sec_agent.graph_state import SecAgentState  # noqa: E402
from sec_agent.graph_nodes import state_resume_report  # noqa: E402


class GraphRunnerState(TypedDict, total=False):
    prompt: str
    forwarded_args: list[str]
    thread_id: str
    run_root: str
    sec_agent_state_path: str
    sec_agent_state: dict[str, object]
    resume_report: dict[str, object]
    graph_runner_summary_path: str
    checkpoint_mode: str
    elapsed_sec: float
    error: str


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(
        description="LangGraph orchestration wrapper for one constrained SEC agent ask run.",
        epilog=(
            "Unknown flags are forwarded to scripts/cloud/sec_agent_interactive.py, "
            "for example --llm-backend deepseek --query-planner llm --quiet."
        ),
    )
    parser.add_argument("--prompt", default="")
    parser.add_argument("--thread-id", default="")
    parser.add_argument("--state-path", default="", help="Existing sec_agent_state.json to inspect for resume readiness.")
    parser.add_argument("--inspect-state", action="store_true", help="Inspect an existing sec_agent_state.json without rerunning.")
    parser.add_argument("--resume-state", action="store_true", help="Resume an existing run when the next ready node is supported.")
    parser.add_argument("--no-checkpointer", action="store_true")
    parser.add_argument(
        "--checkpoint-mode",
        choices=("memory", "sqlite", "none"),
        default=os.environ.get("SEC_AGENT_CHECKPOINTER", "memory"),
        help="Native LangGraph checkpoint backend. Legacy state/resume paths keep their existing behavior.",
    )
    parser.add_argument(
        "--checkpoint-db-path",
        default=os.environ.get("SEC_AGENT_CHECKPOINT_DB_PATH", ""),
        help="SQLite checkpoint DB path for --checkpoint-mode sqlite. Defaults to <native-run-dir>/langgraph_checkpoints.sqlite.",
    )
    parser.add_argument(
        "--state-smoke-dir",
        default="",
        help="Run a tiny LangGraph state write/read smoke in this directory instead of the SEC pipeline.",
    )
    parser.add_argument(
        "--native-state-smoke-dir",
        default="",
        help="Run the LangGraph-native orchestration skeleton smoke in this directory without calling retrieval or LLMs.",
    )
    parser.add_argument(
        "--native-plan-smoke-dir",
        default="",
        help="Run the LangGraph-native skeleton with the legacy planner adapter, then stop after smoke nodes.",
    )
    parser.add_argument(
        "--native-retrieval-smoke-dir",
        default="",
        help="Run the LangGraph-native skeleton with planner and retrieval adapters, without LLM synthesis.",
    )
    parser.add_argument(
        "--native-ledger-smoke-dir",
        default="",
        help="Run the LangGraph-native skeleton through planner, retrieval, market attach, ledger, and coverage adapters.",
    )
    parser.add_argument(
        "--native-full-run-dir",
        default="",
        help="Run the LangGraph-native pipeline through synthesis, gates, and renderer. Requires a configured LLM backend.",
    )
    parser.add_argument(
        "--inspect-native-checkpoints",
        default="",
        help="Inspect a LangGraph-native langgraph_node_checkpoints.json file or its run directory without rerunning.",
    )
    parser.add_argument(
        "--hydrate-native-checkpoints",
        default="",
        help="Hydrate minimal native graph state from a LangGraph-native checkpoint artifact without rerunning.",
    )
    parser.add_argument(
        "--resume-native-checkpoint",
        default="",
        help="Resume a LangGraph-native run from a hydrated checkpoint artifact.",
    )
    parser.add_argument(
        "--native-resume-include-synthesis",
        action="store_true",
        help="Allow resumed native checkpoint runs to execute synthesis, verification, gates, and renderer adapters.",
    )
    parser.add_argument(
        "--native-stop-after-node",
        default="",
        help="Stop a native graph run immediately after this node and write a partial checkpoint artifact.",
    )
    return parser.parse_known_args()


def _strip_arg_separator(args: list[str]) -> list[str]:
    if args and args[0] == "--":
        return args[1:]
    return args


def main() -> int:
    args, forwarded = parse_args()
    if LANGGRAPH_IMPORT_ERROR is not None:
        print(
            "LangGraph is not installed. Install project requirements or run: "
            "python -m pip install 'langgraph>=1.0.0'",
            file=sys.stderr,
        )
        print(f"import_error={type(LANGGRAPH_IMPORT_ERROR).__name__}: {LANGGRAPH_IMPORT_ERROR}", file=sys.stderr)
        return 2

    if args.inspect_state and not args.state_path:
        print("--state-path is required with --inspect-state", file=sys.stderr)
        return 2
    if args.resume_state and not args.state_path:
        print("--state-path is required with --resume-state", file=sys.stderr)
        return 2
    if (
        not args.prompt
        and not args.state_smoke_dir
        and not args.native_state_smoke_dir
        and not args.native_plan_smoke_dir
        and not args.native_retrieval_smoke_dir
        and not args.native_ledger_smoke_dir
        and not args.native_full_run_dir
        and not args.inspect_native_checkpoints
        and not args.hydrate_native_checkpoints
        and not args.resume_native_checkpoint
        and not args.inspect_state
        and not args.resume_state
    ):
        print("--prompt is required unless --state-smoke-dir, --inspect-state, or --resume-state is set", file=sys.stderr)
        return 2

    if args.resume_native_checkpoint:
        return run_resume_native_checkpoint(args, forwarded)
    if args.hydrate_native_checkpoints:
        return run_hydrate_native_checkpoints(args.hydrate_native_checkpoints)
    if args.inspect_native_checkpoints:
        return run_inspect_native_checkpoints(args.inspect_native_checkpoints)
    if args.native_full_run_dir:
        return run_native_ledger_smoke(args, forwarded, include_synthesis=True)
    if args.native_ledger_smoke_dir:
        return run_native_ledger_smoke(args, forwarded)
    if args.native_retrieval_smoke_dir:
        return run_native_retrieval_smoke(args, forwarded)
    if args.native_plan_smoke_dir:
        return run_native_plan_smoke(args, forwarded)
    if args.native_state_smoke_dir:
        return run_native_state_smoke(args)

    thread_id = args.thread_id or _thread_id(args.prompt or args.state_path or "state-smoke")
    if args.resume_state:
        graph = build_state_resume_graph(use_checkpointer=not args.no_checkpointer)
        run_root = str(Path(args.state_path).resolve().parent)
    elif args.inspect_state:
        graph = build_state_inspect_graph(use_checkpointer=not args.no_checkpointer)
        run_root = str(Path(args.state_path).resolve().parent)
    elif args.state_smoke_dir:
        graph = build_state_smoke_graph(use_checkpointer=not args.no_checkpointer)
        run_root = str(Path(args.state_smoke_dir).resolve())
    else:
        graph = build_graph(use_checkpointer=not args.no_checkpointer)
        run_root = ""
    started = time.time()
    result = graph.invoke(
        {
            "prompt": args.prompt,
            "forwarded_args": forwarded,
            "thread_id": thread_id,
            "run_root": run_root,
            "sec_agent_state_path": str(Path(args.state_path).resolve()) if args.state_path else "",
            "checkpoint_mode": "disabled" if args.no_checkpointer else "in_memory",
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    result["elapsed_sec"] = round(time.time() - started, 4)
    _write_graph_runner_summary(result)
    print(json.dumps(_public_summary(result), ensure_ascii=False, indent=2))
    return 0


def build_graph(*, use_checkpointer: bool = True):
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed.")
    builder = StateGraph(GraphRunnerState)
    builder.add_node("run_interactive_pipeline", run_interactive_pipeline)
    builder.add_node("load_sec_agent_state", load_sec_agent_state)
    builder.add_edge(START, "run_interactive_pipeline")
    builder.add_edge("run_interactive_pipeline", "load_sec_agent_state")
    builder.add_edge("load_sec_agent_state", END)
    checkpointer = InMemorySaver() if use_checkpointer and InMemorySaver is not None else None
    return builder.compile(checkpointer=checkpointer)


def build_state_smoke_graph(*, use_checkpointer: bool = True):
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed.")
    builder = StateGraph(GraphRunnerState)
    builder.add_node("write_smoke_state", write_smoke_state)
    builder.add_node("load_sec_agent_state", load_sec_agent_state)
    builder.add_edge(START, "write_smoke_state")
    builder.add_edge("write_smoke_state", "load_sec_agent_state")
    builder.add_edge("load_sec_agent_state", END)
    checkpointer = InMemorySaver() if use_checkpointer and InMemorySaver is not None else None
    return builder.compile(checkpointer=checkpointer)


def build_state_inspect_graph(*, use_checkpointer: bool = True):
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed.")
    builder = StateGraph(GraphRunnerState)
    builder.add_node("load_sec_agent_state", load_sec_agent_state)
    builder.add_node("inspect_resume_readiness", inspect_resume_readiness)
    builder.add_edge(START, "load_sec_agent_state")
    builder.add_edge("load_sec_agent_state", "inspect_resume_readiness")
    builder.add_edge("inspect_resume_readiness", END)
    checkpointer = InMemorySaver() if use_checkpointer and InMemorySaver is not None else None
    return builder.compile(checkpointer=checkpointer)


def build_state_resume_graph(*, use_checkpointer: bool = True):
    if StateGraph is None:
        raise RuntimeError("LangGraph is not installed.")
    builder = StateGraph(GraphRunnerState)
    builder.add_node("load_sec_agent_state", load_sec_agent_state)
    builder.add_node("inspect_resume_readiness", inspect_resume_readiness)
    builder.add_node("resume_supported_stage", resume_supported_stage)
    builder.add_node("load_resumed_sec_agent_state", load_sec_agent_state)
    builder.add_edge(START, "load_sec_agent_state")
    builder.add_edge("load_sec_agent_state", "inspect_resume_readiness")
    builder.add_edge("inspect_resume_readiness", "resume_supported_stage")
    builder.add_edge("resume_supported_stage", "load_resumed_sec_agent_state")
    builder.add_edge("load_resumed_sec_agent_state", END)
    checkpointer = InMemorySaver() if use_checkpointer and InMemorySaver is not None else None
    return builder.compile(checkpointer=checkpointer)


@contextmanager
def _native_checkpointer_context(args: argparse.Namespace, output_dir: Path):
    from sec_agent.langgraph_orchestrator import wrap_checkpoint_saver_for_sec_agent_state

    mode = "none" if args.no_checkpointer else str(args.checkpoint_mode or "memory")
    if mode == "none":
        yield None, {"checkpoint_mode": "none", "checkpoint_db_path": ""}
        return
    if mode == "memory":
        saver = InMemorySaver() if InMemorySaver is not None else None
        if saver is None:
            raise RuntimeError("LangGraph InMemorySaver is unavailable.")
        yield wrap_checkpoint_saver_for_sec_agent_state(saver), {"checkpoint_mode": "memory", "checkpoint_db_path": ""}
        return
    if mode == "sqlite":
        try:
            from langgraph.checkpoint.sqlite import SqliteSaver
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "SQLite checkpointer requires langgraph-checkpoint-sqlite. "
                "Install project requirements before using --checkpoint-mode sqlite."
            ) from exc
        db_path = Path(str(args.checkpoint_db_path or "")).resolve() if args.checkpoint_db_path else (output_dir / "langgraph_checkpoints.sqlite").resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with SqliteSaver.from_conn_string(str(db_path)) as saver:
            saver.setup()
            yield wrap_checkpoint_saver_for_sec_agent_state(saver), {"checkpoint_mode": "sqlite", "checkpoint_db_path": str(db_path)}
        return
    raise RuntimeError(f"Unsupported native checkpoint mode: {mode}")


def _native_initial_state(args: argparse.Namespace, *, user_query: str, output_dir: Path, checkpoint_info: dict[str, str]) -> dict[str, Any]:
    from sec_agent.langgraph_orchestrator import make_native_smoke_state

    state = make_native_smoke_state(user_query=user_query, output_dir=output_dir)
    state["checkpoint_mode"] = checkpoint_info.get("checkpoint_mode", "")
    state["checkpoint_db_path"] = checkpoint_info.get("checkpoint_db_path", "")
    return state


def run_native_state_smoke(args: argparse.Namespace) -> int:
    from sec_agent.langgraph_orchestrator import build_native_state_smoke_graph

    thread_id = args.thread_id or _thread_id(args.prompt or "native-state-smoke")
    output_dir = Path(args.native_state_smoke_dir).resolve()
    with _native_checkpointer_context(args, output_dir) as (checkpointer, checkpoint_info):
        graph = build_native_state_smoke_graph(
            use_checkpointer=checkpoint_info["checkpoint_mode"] != "none",
            checkpointer=checkpointer,
            stop_after_node=args.native_stop_after_node,
        )
        result = graph.invoke(
            _native_initial_state(
                args,
                user_query=args.prompt or "native LangGraph state smoke",
                output_dir=output_dir,
                checkpoint_info=checkpoint_info,
            ),
            config={"configurable": {"thread_id": thread_id}},
        )
    summary = {
        "thread_id": thread_id,
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "native_stop_after_node": result.get("native_stop_after_node") or "",
        "checkpoint_mode": result.get("checkpoint_mode") or "",
        "checkpoint_db_path": result.get("checkpoint_db_path") or "",
        "node_count": len(result.get("node_trace") or []),
        "nodes": [row.get("node") for row in result.get("node_trace") or []],
        "artifact_refs": result.get("artifact_refs") or {},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def run_native_plan_smoke(args: argparse.Namespace, forwarded: list[str]) -> int:
    from sec_agent.langgraph_orchestrator import build_native_state_smoke_graph

    if "--prompt" in forwarded:
        raise ValueError("do not pass --prompt through forwarded args; use graph runner --prompt")
    forwarded = _strip_arg_separator(forwarded)
    module = _load_interactive_module()
    old_argv = sys.argv[:]
    try:
        sys.argv = ["sec_agent_interactive.py", *forwarded]
        interactive_args = module.parse_args()
    finally:
        sys.argv = old_argv

    def planner(state: dict[str, Any]) -> dict[str, Any]:
        return module.build_query_plan_for_graph(interactive_args, str(state.get("user_query") or ""))

    thread_id = args.thread_id or _thread_id(args.prompt or "native-plan-smoke")
    output_dir = Path(args.native_plan_smoke_dir).resolve()
    with _native_checkpointer_context(args, output_dir) as (checkpointer, checkpoint_info):
        graph = build_native_state_smoke_graph(
            use_checkpointer=checkpoint_info["checkpoint_mode"] != "none",
            checkpointer=checkpointer,
            plan_query=planner,
            stop_after_node=args.native_stop_after_node,
        )
        result = graph.invoke(
            _native_initial_state(
                args,
                user_query=args.prompt or "native LangGraph planner smoke",
                output_dir=output_dir,
                checkpoint_info=checkpoint_info,
            ),
            config={"configurable": {"thread_id": thread_id}},
        )
    contract = result.get("query_contract") or {}
    retrieval_plan = result.get("retrieval_plan") or {}
    plan_summary = retrieval_plan.get("summary") if isinstance(retrieval_plan, dict) else {}
    summary = {
        "thread_id": thread_id,
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "native_stop_after_node": result.get("native_stop_after_node") or "",
        "checkpoint_mode": result.get("checkpoint_mode") or "",
        "checkpoint_db_path": result.get("checkpoint_db_path") or "",
        "node_count": len(result.get("node_trace") or []),
        "scope_mode": contract.get("scope_mode"),
        "search_scope_count": len(contract.get("search_scope_tickers") or []),
        "focus_count": len(contract.get("focus_tickers") or []),
        "planner": f"{contract.get('planner_backend', '<unset>')}:{contract.get('planner_status', '<unset>')}",
        "retrieval_routes": plan_summary.get("route_counts") or {},
        "artifact_refs": result.get("artifact_refs") or {},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def run_native_retrieval_smoke(args: argparse.Namespace, forwarded: list[str]) -> int:
    from sec_agent.langgraph_orchestrator import build_native_state_smoke_graph

    if "--prompt" in forwarded:
        raise ValueError("do not pass --prompt through forwarded args; use graph runner --prompt")
    forwarded = _strip_arg_separator(forwarded)
    module = _load_interactive_module()
    old_argv = sys.argv[:]
    try:
        sys.argv = ["sec_agent_interactive.py", *forwarded]
        interactive_args = module.parse_args()
    finally:
        sys.argv = old_argv

    def planner(state: dict[str, Any]) -> dict[str, Any]:
        return module.build_query_plan_for_graph(interactive_args, str(state.get("user_query") or ""))

    def retrieve_context(state: dict[str, Any]) -> dict[str, Any]:
        return module.retrieve_context_for_graph(interactive_args, state)

    thread_id = args.thread_id or _thread_id(args.prompt or "native-retrieval-smoke")
    output_dir = Path(args.native_retrieval_smoke_dir).resolve()
    with _native_checkpointer_context(args, output_dir) as (checkpointer, checkpoint_info):
        graph = build_native_state_smoke_graph(
            use_checkpointer=checkpoint_info["checkpoint_mode"] != "none",
            checkpointer=checkpointer,
            plan_query=planner,
            retrieve_context=retrieve_context,
            stop_after_node=args.native_stop_after_node,
        )
        result = graph.invoke(
            _native_initial_state(
                args,
                user_query=args.prompt or "native LangGraph retrieval smoke",
                output_dir=output_dir,
                checkpoint_info=checkpoint_info,
            ),
            config={"configurable": {"thread_id": thread_id}},
        )
    contract = result.get("query_contract") or {}
    retrieval_plan = result.get("retrieval_plan") or {}
    plan_summary = retrieval_plan.get("summary") if isinstance(retrieval_plan, dict) else {}
    runtime = result.get("context_runtime") if isinstance(result.get("context_runtime"), dict) else {}
    summary = {
        "thread_id": thread_id,
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "native_stop_after_node": result.get("native_stop_after_node") or "",
        "checkpoint_mode": result.get("checkpoint_mode") or "",
        "checkpoint_db_path": result.get("checkpoint_db_path") or "",
        "node_count": len(result.get("node_trace") or []),
        "scope_mode": contract.get("scope_mode"),
        "search_scope_count": len(contract.get("search_scope_tickers") or []),
        "focus_count": len(contract.get("focus_tickers") or []),
        "planner": f"{contract.get('planner_backend', '<unset>')}:{contract.get('planner_status', '<unset>')}",
        "retrieval_routes": plan_summary.get("route_counts") or {},
        "context_row_count": len(result.get("context_rows") or []),
        "context_runtime": runtime,
        "artifact_refs": result.get("artifact_refs") or {},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def run_native_ledger_smoke(args: argparse.Namespace, forwarded: list[str], *, include_synthesis: bool = False) -> int:
    from sec_agent.langgraph_orchestrator import build_native_state_smoke_graph

    if "--prompt" in forwarded:
        raise ValueError("do not pass --prompt through forwarded args; use graph runner --prompt")
    forwarded = _strip_arg_separator(forwarded)
    module = _load_interactive_module()
    old_argv = sys.argv[:]
    try:
        sys.argv = ["sec_agent_interactive.py", *forwarded]
        interactive_args = module.parse_args()
    finally:
        sys.argv = old_argv

    def planner(state: dict[str, Any]) -> dict[str, Any]:
        return module.build_query_plan_for_graph(interactive_args, str(state.get("user_query") or ""))

    def retrieve_context(state: dict[str, Any]) -> dict[str, Any]:
        return module.retrieve_context_for_graph(interactive_args, state)

    def attach_market_snapshot(state: dict[str, Any]) -> dict[str, Any]:
        return module.attach_market_snapshot_for_graph(interactive_args, state)

    def attach_industry_snapshot(state: dict[str, Any]) -> dict[str, Any]:
        return module.attach_industry_snapshot_for_graph(interactive_args, state)

    def build_runtime_ledger(state: dict[str, Any]) -> dict[str, Any]:
        return module.build_runtime_ledger_for_graph(interactive_args, state)

    def build_coverage_matrix(state: dict[str, Any]) -> dict[str, Any]:
        return module.build_coverage_matrix_for_graph(interactive_args, state)

    def execute_second_pass_retrieval(state: dict[str, Any]) -> dict[str, Any]:
        return module.execute_second_pass_retrieval_for_graph(interactive_args, state)

    def build_judgment_plan(state: dict[str, Any]) -> dict[str, Any]:
        return module.build_judgment_plan_for_graph(interactive_args, state)

    def synthesize_answer(state: dict[str, Any]) -> dict[str, Any]:
        return module.synthesize_answer_for_graph(interactive_args, state)

    def verify_claims(state: dict[str, Any]) -> dict[str, Any]:
        return module.verify_claims_for_graph(interactive_args, state)

    def run_deterministic_gates(state: dict[str, Any]) -> dict[str, Any]:
        return module.run_deterministic_gates_for_graph(interactive_args, state)

    def render_answer(state: dict[str, Any]) -> dict[str, Any]:
        return module.render_answer_for_graph(interactive_args, state)

    mode_name = "native-full-run" if include_synthesis else "native-ledger-smoke"
    output_dir = Path(args.native_full_run_dir if include_synthesis else args.native_ledger_smoke_dir).resolve()
    thread_id = args.thread_id or _thread_id(args.prompt or mode_name)
    with _native_checkpointer_context(args, output_dir) as (checkpointer, checkpoint_info):
        graph = build_native_state_smoke_graph(
            use_checkpointer=checkpoint_info["checkpoint_mode"] != "none",
            checkpointer=checkpointer,
            plan_query=planner,
            retrieve_context=retrieve_context,
            attach_market_snapshot=attach_market_snapshot,
            attach_industry_snapshot=attach_industry_snapshot,
            build_runtime_ledger=build_runtime_ledger,
            build_coverage_matrix=build_coverage_matrix,
            execute_second_pass_retrieval=execute_second_pass_retrieval,
            build_judgment_plan=build_judgment_plan,
            synthesize_answer=synthesize_answer if include_synthesis else None,
            verify_claims=verify_claims if include_synthesis else None,
            run_deterministic_gates=run_deterministic_gates if include_synthesis else None,
            render_answer=render_answer if include_synthesis else None,
            stop_after_node=args.native_stop_after_node,
        )
        result = graph.invoke(
            _native_initial_state(
                args,
                user_query=args.prompt or ("native LangGraph full run" if include_synthesis else "native LangGraph ledger smoke"),
                output_dir=output_dir,
                checkpoint_info=checkpoint_info,
            ),
            config={"configurable": {"thread_id": thread_id}},
        )
    contract = result.get("query_contract") or {}
    retrieval_plan = result.get("retrieval_plan") or {}
    plan_summary = retrieval_plan.get("summary") if isinstance(retrieval_plan, dict) else {}
    runtime = result.get("context_runtime") if isinstance(result.get("context_runtime"), dict) else {}
    coverage_summary = (
        (result.get("coverage_matrix") or {}).get("summary")
        if isinstance(result.get("coverage_matrix"), dict)
        else {}
    )
    summary = {
        "thread_id": thread_id,
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "mode": mode_name,
        "native_stop_after_node": result.get("native_stop_after_node") or "",
        "checkpoint_mode": result.get("checkpoint_mode") or "",
        "checkpoint_db_path": result.get("checkpoint_db_path") or "",
        "node_count": len(result.get("node_trace") or []),
        "scope_mode": contract.get("scope_mode"),
        "search_scope_count": len(contract.get("search_scope_tickers") or []),
        "focus_count": len(contract.get("focus_tickers") or []),
        "planner": f"{contract.get('planner_backend', '<unset>')}:{contract.get('planner_status', '<unset>')}",
        "retrieval_routes": plan_summary.get("route_counts") or {},
        "context_row_count": len(result.get("context_rows") or []),
        "market_context_row_count": len(result.get("market_snapshot_rows") or []),
        "industry_context_row_count": len(result.get("industry_snapshot_rows") or []),
        "ledger_row_count": len(result.get("runtime_ledger_rows") or []),
        "coverage": coverage_summary or {},
        "second_pass": result.get("second_pass_result") or {},
        "judgment_plan": {
            "has_plan": bool(result.get("judgment_plan")),
            "driver_count": len((result.get("judgment_plan") or {}).get("drivers") or [])
            if isinstance(result.get("judgment_plan"), dict)
            else 0,
        },
        "memo_answer": {
            "answer_status": (result.get("memo_answer") or {}).get("answer_status")
            if isinstance(result.get("memo_answer"), dict)
            else "",
            "claim_status": (result.get("memo_answer") or {}).get("claim_status")
            if isinstance(result.get("memo_answer"), dict)
            else "",
        },
        "deterministic_gates": result.get("deterministic_gates") or {},
        "rendered_answer_chars": len(str(result.get("rendered_answer") or "")),
        "context_runtime": runtime,
        "artifact_refs": result.get("artifact_refs") or {},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def run_inspect_native_checkpoints(path: str) -> int:
    from sec_agent.langgraph_orchestrator import inspect_node_checkpoint_artifact

    report = inspect_node_checkpoint_artifact(path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def run_hydrate_native_checkpoints(path: str) -> int:
    from sec_agent.langgraph_orchestrator import hydrate_native_state_from_checkpoint_artifact

    report = hydrate_native_state_from_checkpoint_artifact(path)
    state = report.get("state") if isinstance(report.get("state"), dict) else {}
    compact = {
        "schema_version": report.get("schema_version"),
        "checkpoint_path": report.get("checkpoint_path"),
        "latest_completed_node": report.get("latest_completed_node"),
        "next_recoverable_node": report.get("next_recoverable_node"),
        "resume_supported": report.get("resume_supported"),
        "blocked_reasons": report.get("blocked_reasons"),
        "state_summary": report.get("state_summary"),
        "artifact_keys": sorted((state.get("artifact_refs") or {}).keys()) if isinstance(state.get("artifact_refs"), dict) else [],
    }
    print(json.dumps(compact, ensure_ascii=False, indent=2))
    return 0


def run_resume_native_checkpoint(args: argparse.Namespace, forwarded: list[str]) -> int:
    from sec_agent.langgraph_orchestrator import (
        NATIVE_NODE_ORDER,
        build_native_state_smoke_graph,
        hydrate_native_state_from_checkpoint_artifact,
    )

    if "--prompt" in forwarded:
        raise ValueError("do not pass --prompt through forwarded args when resuming native checkpoints")
    report = hydrate_native_state_from_checkpoint_artifact(args.resume_native_checkpoint)
    if not report.get("resume_supported"):
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    next_node = str(report.get("next_recoverable_node") or "")
    if not args.native_resume_include_synthesis and _native_resume_requires_synthesis(next_node, NATIVE_NODE_ORDER):
        print(
            json.dumps(
                {
                    "schema_version": "sec_agent_native_resume_rejection_v0.1",
                    "status": "blocked",
                    "reason": "synthesis_required_for_resume",
                    "next_recoverable_node": next_node,
                    "hint": "pass --native-resume-include-synthesis when resuming before or at synthesize_answer",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    state = dict(report.get("state") or {})
    output_dir = Path(str(state.get("output_dir") or Path(args.resume_native_checkpoint).resolve().parent)).resolve()

    forwarded = _strip_arg_separator(forwarded)
    module = _load_interactive_module()
    old_argv = sys.argv[:]
    try:
        sys.argv = ["sec_agent_interactive.py", *forwarded]
        interactive_args = module.parse_args()
    finally:
        sys.argv = old_argv

    def planner(graph_state: dict[str, Any]) -> dict[str, Any]:
        return module.build_query_plan_for_graph(interactive_args, str(graph_state.get("user_query") or ""))

    def retrieve_context(graph_state: dict[str, Any]) -> dict[str, Any]:
        return module.retrieve_context_for_graph(interactive_args, graph_state)

    def attach_market_snapshot(graph_state: dict[str, Any]) -> dict[str, Any]:
        return module.attach_market_snapshot_for_graph(interactive_args, graph_state)

    def attach_industry_snapshot(graph_state: dict[str, Any]) -> dict[str, Any]:
        return module.attach_industry_snapshot_for_graph(interactive_args, graph_state)

    def build_runtime_ledger(graph_state: dict[str, Any]) -> dict[str, Any]:
        return module.build_runtime_ledger_for_graph(interactive_args, graph_state)

    def build_coverage_matrix(graph_state: dict[str, Any]) -> dict[str, Any]:
        return module.build_coverage_matrix_for_graph(interactive_args, graph_state)

    def execute_second_pass_retrieval(graph_state: dict[str, Any]) -> dict[str, Any]:
        return module.execute_second_pass_retrieval_for_graph(interactive_args, graph_state)

    def build_judgment_plan(graph_state: dict[str, Any]) -> dict[str, Any]:
        return module.build_judgment_plan_for_graph(interactive_args, graph_state)

    def synthesize_answer(graph_state: dict[str, Any]) -> dict[str, Any]:
        return module.synthesize_answer_for_graph(interactive_args, graph_state)

    def verify_claims(graph_state: dict[str, Any]) -> dict[str, Any]:
        return module.verify_claims_for_graph(interactive_args, graph_state)

    def run_deterministic_gates(graph_state: dict[str, Any]) -> dict[str, Any]:
        return module.run_deterministic_gates_for_graph(interactive_args, graph_state)

    def render_answer(graph_state: dict[str, Any]) -> dict[str, Any]:
        return module.render_answer_for_graph(interactive_args, graph_state)

    thread_id = args.thread_id or f"{state.get('run_id', 'native')}_resume"
    with _native_checkpointer_context(args, output_dir) as (checkpointer, checkpoint_info):
        state["checkpoint_mode"] = checkpoint_info.get("checkpoint_mode", "")
        state["checkpoint_db_path"] = checkpoint_info.get("checkpoint_db_path", "")
        graph = build_native_state_smoke_graph(
            use_checkpointer=checkpoint_info["checkpoint_mode"] != "none",
            checkpointer=checkpointer,
            entry_node=next_node,
            plan_query=planner,
            retrieve_context=retrieve_context,
            attach_market_snapshot=attach_market_snapshot,
            attach_industry_snapshot=attach_industry_snapshot,
            build_runtime_ledger=build_runtime_ledger,
            build_coverage_matrix=build_coverage_matrix,
            execute_second_pass_retrieval=execute_second_pass_retrieval,
            build_judgment_plan=build_judgment_plan,
            synthesize_answer=synthesize_answer if args.native_resume_include_synthesis else None,
            verify_claims=verify_claims,
            run_deterministic_gates=run_deterministic_gates,
            render_answer=render_answer,
            stop_after_node=args.native_stop_after_node,
        )
        result = graph.invoke(state, config={"configurable": {"thread_id": thread_id}})

    coverage_summary = (
        (result.get("coverage_matrix") or {}).get("summary")
        if isinstance(result.get("coverage_matrix"), dict)
        else {}
    )
    summary = {
        "thread_id": thread_id,
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "resume_from_checkpoint": str(Path(args.resume_native_checkpoint).resolve()),
        "entry_node": next_node,
        "native_stop_after_node": result.get("native_stop_after_node") or "",
        "checkpoint_mode": result.get("checkpoint_mode") or "",
        "checkpoint_db_path": result.get("checkpoint_db_path") or "",
        "node_count": len(result.get("node_trace") or []),
        "context_row_count": len(result.get("context_rows") or []),
        "market_context_row_count": len(result.get("market_snapshot_rows") or []),
        "ledger_row_count": len(result.get("runtime_ledger_rows") or []),
        "coverage": coverage_summary or {},
        "second_pass": result.get("second_pass_result") or {},
        "judgment_plan": {
            "has_plan": bool(result.get("judgment_plan")),
            "driver_count": len((result.get("judgment_plan") or {}).get("drivers") or [])
            if isinstance(result.get("judgment_plan"), dict)
            else 0,
        },
        "rendered_answer_chars": len(str(result.get("rendered_answer") or "")),
        "artifact_refs": result.get("artifact_refs") or {},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _native_resume_requires_synthesis(next_node: str, node_order: tuple[str, ...]) -> bool:
    if next_node == "execute_second_pass_retrieval":
        return True
    try:
        return node_order.index(next_node) <= node_order.index("synthesize_answer")
    except ValueError:
        return False


def run_interactive_pipeline(state: GraphRunnerState) -> GraphRunnerState:
    module = _load_interactive_module()
    prompt = str(state.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    forwarded_args = _strip_arg_separator(list(state.get("forwarded_args") or []))
    if "--prompt" in forwarded_args:
        raise ValueError("do not pass --prompt through forwarded args; use graph runner --prompt")

    old_argv = sys.argv[:]
    try:
        sys.argv = ["sec_agent_interactive.py", *forwarded_args, "--prompt", prompt]
        interactive_args = module.parse_args()
    finally:
        sys.argv = old_argv
    run_root = module.run_one(interactive_args, interactive_args.prompt)
    return {
        **state,
        "run_root": str(Path(run_root).resolve()),
        "sec_agent_state_path": str((Path(run_root) / "sec_agent_state.json").resolve()),
    }


def write_smoke_state(state: GraphRunnerState) -> GraphRunnerState:
    run_root = Path(str(state.get("run_root") or "")).resolve()
    if not str(run_root):
        raise ValueError("run_root is required for state smoke")
    run_root.mkdir(parents=True, exist_ok=True)
    query_path = run_root / "query_contract.json"
    query_path.write_text(
        json.dumps(
            {
                "schema_version": "sec_agent_query_contract_smoke_v0.1",
                "task_type": "state_smoke",
                "focus_tickers": [],
                "years": [],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    sec_state = SecAgentState.create(
        run_id=str(state.get("thread_id") or _thread_id("state-smoke")),
        user_query=str(state.get("prompt") or "state smoke"),
        output_dir=run_root,
        metadata={
            "runner": "scripts/cloud/sec_agent_graph_runner.py",
            "mode": "state_smoke",
            "checkpoint_mode": str(state.get("checkpoint_mode") or ""),
        },
    )
    sec_state.with_artifact("query_contract", query_path.resolve(), metadata={"smoke": True})
    sec_state.mark_stage("plan_query", "completed", metadata={"smoke": True})
    sec_state.status = "completed"
    state_path = sec_state.write_json(run_root / "sec_agent_state.json")
    return {
        **state,
        "run_root": str(run_root),
        "sec_agent_state_path": str(state_path.resolve()),
    }


def load_sec_agent_state(state: GraphRunnerState) -> GraphRunnerState:
    path = Path(str(state.get("sec_agent_state_path") or ""))
    if not path.exists():
        raise RuntimeError(f"sec_agent_state.json not found: {path}")
    sec_state = SecAgentState.read_json(path)
    return {**state, "sec_agent_state": sec_state.to_dict()}


def inspect_resume_readiness(state: GraphRunnerState) -> GraphRunnerState:
    path = Path(str(state.get("sec_agent_state_path") or ""))
    sec_state = SecAgentState.read_json(path)
    report = state_resume_report(sec_state)
    report_path = Path(sec_state.output_dir) / "graph_resume_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        **state,
        "run_root": str(Path(sec_state.output_dir).resolve()),
        "resume_report": report,
    }


def resume_supported_stage(state: GraphRunnerState) -> GraphRunnerState:
    report = state.get("resume_report") or {}
    next_node = str(report.get("next_ready_node") or "")
    if not next_node:
        return {
            **state,
            "resume_report": {**report, "resume_action": "no_op", "resume_reason": "state already has no ready missing node"},
        }
    supported_nodes = {
        "retrieve_context",
        "build_runtime_ledger",
        "build_coverage_matrix",
        "build_judgment_plan",
        "synthesize_memo",
        "run_deterministic_gates",
        "render_answer",
    }
    if next_node not in supported_nodes:
        raise RuntimeError(f"stage-level resume currently does not support next_ready_node={next_node}")

    module = _load_interactive_module()
    forwarded_args = _strip_arg_separator(list(state.get("forwarded_args") or []))
    if "--prompt" in forwarded_args:
        raise ValueError("do not pass --prompt through forwarded args when resuming")
    old_argv = sys.argv[:]
    try:
        sys.argv = ["sec_agent_interactive.py", *forwarded_args]
        interactive_args = module.parse_args()
    finally:
        sys.argv = old_argv
    state_path = Path(str(state.get("sec_agent_state_path") or ""))
    run_root = module.resume_from_state(interactive_args, state_path)
    resumed_state_path = str((Path(run_root) / "sec_agent_state.json").resolve())
    return {
        **state,
        "run_root": str(Path(run_root).resolve()),
        "sec_agent_state_path": resumed_state_path,
        "resume_report": {**report, "resume_action": "executed", "resumed_from_node": next_node},
    }


def _load_interactive_module():
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_runtime", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load interactive module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _thread_id(prompt: str) -> str:
    digest = hashlib.sha1(prompt.encode("utf-8", errors="ignore")).hexdigest()[:10]
    return datetime.now().strftime("sec-agent-%Y%m%d-%H%M%S-") + digest


def _write_graph_runner_summary(result: GraphRunnerState) -> None:
    run_root = Path(str(result.get("run_root") or ""))
    if not run_root:
        return
    run_root.mkdir(parents=True, exist_ok=True)
    summary_path = run_root / "graph_runner_summary.json"
    result["graph_runner_summary_path"] = str(summary_path.resolve())
    payload = _public_summary(result)
    payload["created_at"] = datetime.now().isoformat(timespec="seconds")
    payload["checkpoint_mode"] = result.get("checkpoint_mode")
    if result.get("resume_report"):
        payload["resume_report_path"] = str((run_root / "graph_resume_report.json").resolve())
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _public_summary(result: GraphRunnerState) -> dict[str, Any]:
    sec_state = result.get("sec_agent_state") or {}
    artifacts = sec_state.get("artifacts") or {}
    stages = sec_state.get("stages") or []
    resume_report = result.get("resume_report") or {}
    return {
        "thread_id": result.get("thread_id"),
        "run_root": result.get("run_root"),
        "sec_agent_state_path": result.get("sec_agent_state_path"),
        "status": sec_state.get("status"),
        "stage_count": len(stages),
        "artifact_keys": sorted(artifacts),
        "checkpoint_mode": result.get("checkpoint_mode"),
        "graph_runner_summary_path": result.get("graph_runner_summary_path"),
        "resume": {
            "next_ready_node": resume_report.get("next_ready_node"),
            "ready_nodes": resume_report.get("ready_nodes"),
            "missing_artifacts": resume_report.get("missing_artifacts"),
            "digest_mismatch_artifacts": resume_report.get("digest_mismatch_artifacts"),
            "resume_action": resume_report.get("resume_action"),
            "resumed_from_node": resume_report.get("resumed_from_node"),
        } if resume_report else None,
        "elapsed_sec": result.get("elapsed_sec"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
