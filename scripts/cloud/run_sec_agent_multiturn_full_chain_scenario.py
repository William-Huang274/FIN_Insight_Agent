from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.tool_controller import ControllerConfig, DeepSeekToolController  # noqa: E402
from sec_agent.tool_harness import SecAgentToolHarness  # noqa: E402


EXECUTE_CAPABLE_TOOLS = {
    "start_memo_analysis",
    "revise_memo_scope",
    "reformat_answer",
    "resume_analysis",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run one reviewed multi-turn tool scenario through controller routing and real harness execution."
    )
    parser.add_argument("--eval-path", default="eval_sets/sec_agent_multiturn_tool_harness_eval_reviewed_v1.json")
    parser.add_argument("--scenario-id", default="multiturn_tool_scope_revision_001")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--session-root", default="")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--controller-backend",
        default=os.environ.get("TOOL_CONTROLLER_BACKEND", "deepseek"),
        choices=("deepseek", "openai_compatible", "qwen_vllm", "heuristic"),
    )
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--chat-completions-path", default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--query-planner", default="llm")
    parser.add_argument("--bge-device", default="cuda")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    session_root = _resolve(args.session_root) if args.session_root else output_dir / "session_harness"
    session_root.mkdir(parents=True, exist_ok=True)

    scenario = _load_scenario(_resolve(args.eval_path), args.scenario_id)
    initial_state = scenario.get("initial_state") if isinstance(scenario.get("initial_state"), dict) else {}
    session_id = str(initial_state.get("session_id") or args.scenario_id)
    user_id = str(initial_state.get("user_id") or "default_user")
    tenant_id = str(initial_state.get("tenant_id") or "default_tenant")

    harness = SecAgentToolHarness(session_root=session_root, python=args.python, repo_root=REPO_ROOT)
    controller = DeepSeekToolController(
        harness=harness,
        config=ControllerConfig(
            controller_backend=args.controller_backend,
            llm_backend=args.llm_backend,
            base_url=args.base_url,
            chat_completions_path=args.chat_completions_path,
            model=args.model,
            api_key_env=args.api_key_env,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout_s=args.timeout_s,
            max_steps=1,
            execute_tools=False,
        ),
    )
    graph_args = _graph_args(args)

    run_started = time.time()
    turns: list[dict[str, Any]] = []
    prior_tool_calls: list[dict[str, Any]] = []
    active_answer_id = str(initial_state.get("active_answer_id") or "")
    failure_count = 0

    for index, turn in enumerate(scenario.get("turns") or [], start=1):
        turn_started = time.time()
        message = str(turn.get("user_message") or "")
        expected_tool = str(turn.get("expected_tool") or "")
        expected_args = turn.get("expected_arguments") if isinstance(turn.get("expected_arguments"), dict) else {}
        route_result = controller.run_turn(
            user_message=message,
            session_id=session_id,
            user_id=user_id,
            tenant_id=tenant_id,
            active_answer_id=active_answer_id,
            runtime_context={
                "initial_state": initial_state,
                "prior_tool_calls": prior_tool_calls,
            },
            route_only=True,
        )
        tool_call = _first_tool_call(route_result)
        selected_tool = str(tool_call.get("name") or "")
        selected_args = dict(tool_call.get("arguments") or {})
        should_execute = bool(expected_args.get("execute")) if selected_tool in EXECUTE_CAPABLE_TOOLS else False
        dispatch_args = dict(selected_args)
        if selected_tool in EXECUTE_CAPABLE_TOOLS:
            dispatch_args["execute"] = should_execute
        if selected_tool in {"start_memo_analysis", "revise_memo_scope"} and should_execute:
            dispatch_args["graph_args"] = graph_args

        dispatch_result = None
        dispatch_error = ""
        if selected_tool:
            try:
                dispatch_result = harness.dispatch(selected_tool, dispatch_args).to_dict()
            except Exception as exc:  # noqa: BLE001 - eval runner should capture full turn failure.
                dispatch_error = f"{type(exc).__name__}: {exc}"
        else:
            dispatch_error = "controller returned no tool call"

        session_state = _load_session_state(session_root, session_id)
        active_answer_id = str(session_state.get("active_answer_id") or active_answer_id)
        compact_dispatch = _compact_dispatch_result(dispatch_result)
        tool_pass = bool(selected_tool == expected_tool)
        dispatch_pass = bool(
            dispatch_result
            and dispatch_result.get("status") == "completed"
            and not dispatch_error
            and _execution_ok(dispatch_result)
        )
        expected_scope = _scope_expectation(turn)
        scope_pass = _scope_matches(expected_scope, session_state.get("active_scope") or {})
        if not tool_pass or not dispatch_pass or not scope_pass:
            failure_count += 1

        turn_record = {
            "turn_index": index,
            "turn_id": turn.get("turn_id"),
            "user_message": message,
            "expected_tool": expected_tool,
            "selected_tool": selected_tool,
            "tool_pass": tool_pass,
            "selected_arguments": selected_args,
            "dispatch_arguments": _redact_dispatch_args(dispatch_args),
            "dispatch_pass": dispatch_pass,
            "scope_pass": scope_pass,
            "expected_scope": expected_scope,
            "active_scope": session_state.get("active_scope") or {},
            "dispatch_error": dispatch_error,
            "dispatch_result": compact_dispatch,
            "active_answer_id_after_turn": active_answer_id,
            "elapsed_sec": round(time.time() - turn_started, 4),
            "route_result": _compact_route_result(route_result),
        }
        turns.append(turn_record)
        prior_tool_calls.append(
            {
                "turn_id": turn.get("turn_id"),
                "tool_name": selected_tool,
                "arguments": selected_args,
                "status": (dispatch_result or {}).get("status") if isinstance(dispatch_result, dict) else "error",
            }
        )
        _write_json(output_dir / "in_progress_summary.json", _summary_payload(args, scenario, turns, failure_count, session_root, run_started, True))
        print(json.dumps({"turn": turn.get("turn_id"), "tool": selected_tool, "tool_pass": tool_pass, "dispatch_pass": dispatch_pass}, ensure_ascii=False))

    summary = _summary_payload(args, scenario, turns, failure_count, session_root, run_started, False)
    _write_json(output_dir / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if failure_count == 0 else 1


def _summary_payload(
    args: argparse.Namespace,
    scenario: dict[str, Any],
    turns: list[dict[str, Any]],
    failure_count: int,
    session_root: Path,
    run_started: float,
    in_progress: bool,
) -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_multiturn_full_chain_result_v0.1",
        "run_id": Path(args.output_dir).name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "in_progress": in_progress,
        "scenario_id": scenario.get("scenario_id"),
        "category": scenario.get("category"),
        "purpose": scenario.get("purpose"),
        "controller_backend": args.controller_backend,
        "llm_backend": args.llm_backend,
        "model": args.model,
        "source_policy": "SEC_ONLY_10K",
        "session_root": str(session_root.resolve()),
        "turn_count": len(turns),
        "tool_pass_count": sum(1 for item in turns if item.get("tool_pass")),
        "dispatch_pass_count": sum(1 for item in turns if item.get("dispatch_pass")),
        "failure_count": failure_count,
        "all_pass": failure_count == 0 and len(turns) == len(scenario.get("turns") or []),
        "elapsed_sec": round(time.time() - run_started, 4),
        "turns": turns,
        "final_session_state": _load_session_state(session_root, str((scenario.get("initial_state") or {}).get("session_id") or "")),
    }


def _graph_args(args: argparse.Namespace) -> list[str]:
    result = [
        "--llm-backend",
        args.llm_backend,
        "--base-url",
        args.base_url,
        "--chat-completions-path",
        args.chat_completions_path,
        "--model",
        args.model,
        "--query-planner",
        args.query_planner,
        "--quiet",
        "--bge-first",
        "--bge-device",
        args.bge_device,
    ]
    if args.api_key_env:
        result.extend(["--api-key-env", args.api_key_env])
    return result


def _load_scenario(eval_path: Path, scenario_id: str) -> dict[str, Any]:
    payload = json.loads(eval_path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("eval file must contain a list of scenarios")
    for scenario in payload:
        if isinstance(scenario, dict) and str(scenario.get("scenario_id") or "") == scenario_id:
            return scenario
    raise KeyError(f"scenario not found: {scenario_id}")


def _first_tool_call(route_result: dict[str, Any]) -> dict[str, Any]:
    calls = route_result.get("tool_calls") if isinstance(route_result, dict) else []
    if isinstance(calls, list) and calls:
        first = calls[0]
        return first if isinstance(first, dict) else {}
    return {}


def _execution_ok(dispatch_result: dict[str, Any]) -> bool:
    payload = dispatch_result.get("payload") if isinstance(dispatch_result.get("payload"), dict) else {}
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    execution = analysis.get("execution") if isinstance(analysis.get("execution"), dict) else {}
    if execution and execution.get("execute") is True:
        return execution.get("returncode") == 0
    execution_result = payload.get("execution_result") if isinstance(payload.get("execution_result"), dict) else {}
    nested_analysis = execution_result.get("analysis") if isinstance(execution_result.get("analysis"), dict) else {}
    nested_execution = nested_analysis.get("execution") if isinstance(nested_analysis.get("execution"), dict) else {}
    if nested_execution and nested_execution.get("execute") is True:
        return nested_execution.get("returncode") == 0
    return True


def _scope_expectation(turn: dict[str, Any]) -> dict[str, Any]:
    raw_args = turn.get("expected_arguments_raw") if isinstance(turn.get("expected_arguments_raw"), dict) else {}
    expected_context = turn.get("expected_context") if isinstance(turn.get("expected_context"), dict) else {}
    active_scope = expected_context.get("active_scope") if isinstance(expected_context.get("active_scope"), dict) else {}
    tickers = (
        active_scope.get("selected_tickers")
        or active_scope.get("tickers")
        or expected_context.get("target_tickers")
        or expected_context.get("tickers")
        or raw_args.get("target_tickers")
        or raw_args.get("tickers")
        or []
    )
    years = active_scope.get("selected_years") or active_scope.get("years") or raw_args.get("years") or []
    result: dict[str, Any] = {}
    if tickers:
        result["selected_tickers"] = _upper_list(tickers)
    if years:
        result["selected_years"] = [int(item) for item in years if str(item).isdigit()]
    return result


def _scope_matches(expected_scope: dict[str, Any], active_scope: dict[str, Any]) -> bool:
    if not expected_scope:
        return True
    if expected_scope.get("selected_tickers"):
        expected_tickers = set(_upper_list(expected_scope.get("selected_tickers") or []))
        active_tickers = set(_upper_list(active_scope.get("selected_tickers") or active_scope.get("tickers") or []))
        if active_tickers != expected_tickers:
            return False
    if expected_scope.get("selected_years"):
        expected_years = {int(item) for item in expected_scope.get("selected_years") or []}
        active_years = {int(item) for item in (active_scope.get("selected_years") or active_scope.get("years") or [])}
        if active_years != expected_years:
            return False
    return True


def _upper_list(values: Any) -> list[str]:
    return [str(item).strip().upper() for item in (values or []) if str(item).strip()]


def _compact_route_result(route_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": route_result.get("status"),
        "route_only": route_result.get("route_only"),
        "execute_tools": route_result.get("execute_tools"),
        "latency_ms": route_result.get("latency_ms"),
        "tool_calls": route_result.get("tool_calls") or [],
        "trace": route_result.get("trace") or [],
    }


def _compact_dispatch_result(dispatch_result: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(dispatch_result, dict):
        return {}
    payload = dispatch_result.get("payload") if isinstance(dispatch_result.get("payload"), dict) else {}
    compact_payload: dict[str, Any] = {}
    for key in (
        "session_id",
        "answer_id",
        "base_answer_id",
        "revised_tickers",
        "revised_years",
        "invalidated_artifacts",
        "preserve_output_style",
        "summary",
        "task_count",
        "driver",
        "metric_ids",
        "evidence_ids",
        "ledger_matches",
        "judgment_plan_matches",
        "rerun_required",
    ):
        if key in payload:
            compact_payload[key] = payload[key]
    if "analysis" in payload:
        compact_payload["analysis"] = payload["analysis"]
    if "execution_result" in payload and isinstance(payload["execution_result"], dict):
        compact_payload["execution_result"] = {
            "answer_id": payload["execution_result"].get("answer_id"),
            "analysis": payload["execution_result"].get("analysis"),
        }
    return {
        "tool_name": dispatch_result.get("tool_name"),
        "status": dispatch_result.get("status"),
        "message": dispatch_result.get("message", ""),
        "payload": compact_payload,
    }


def _load_session_state(session_root: Path, session_id: str) -> dict[str, Any]:
    if not session_id:
        return {}
    path = session_root / _safe_id(session_id) / "session_state.json"
    if not path.exists():
        return {}
    state = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        return {}
    analyses = state.get("analyses") if isinstance(state.get("analyses"), dict) else {}
    compact_analyses = {}
    for answer_id, analysis in analyses.items():
        if not isinstance(analysis, dict):
            continue
        compact_analyses[answer_id] = {
            "answer_id": analysis.get("answer_id"),
            "status": analysis.get("status"),
            "run_root": analysis.get("run_root"),
            "state_path": analysis.get("state_path"),
            "scope": analysis.get("scope"),
            "artifact_keys": sorted((analysis.get("artifact_refs") or {}).keys()),
            "execution": analysis.get("execution"),
        }
    return {
        "session_id": state.get("session_id"),
        "user_id": state.get("user_id"),
        "tenant_id": state.get("tenant_id"),
        "active_answer_id": state.get("active_answer_id"),
        "active_scope": state.get("active_scope"),
        "turn_count": len(state.get("turns") or []),
        "analyses": compact_analyses,
    }


def _redact_dispatch_args(args: dict[str, Any]) -> dict[str, Any]:
    result = dict(args)
    if "graph_args" in result:
        result["graph_args"] = ["<graph-args-redacted>"]
    return result


def _safe_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value or "session"))


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
