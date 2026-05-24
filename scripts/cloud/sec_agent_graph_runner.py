from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
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
        "--state-smoke-dir",
        default="",
        help="Run a tiny LangGraph state write/read smoke in this directory instead of the SEC pipeline.",
    )
    return parser.parse_known_args()


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
    if not args.prompt and not args.state_smoke_dir and not args.inspect_state and not args.resume_state:
        print("--prompt is required unless --state-smoke-dir, --inspect-state, or --resume-state is set", file=sys.stderr)
        return 2

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


def run_interactive_pipeline(state: GraphRunnerState) -> GraphRunnerState:
    module = _load_interactive_module()
    prompt = str(state.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    forwarded_args = list(state.get("forwarded_args") or [])
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
    forwarded_args = list(state.get("forwarded_args") or [])
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
