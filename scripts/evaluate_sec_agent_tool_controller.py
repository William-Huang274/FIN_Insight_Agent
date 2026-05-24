from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.tool_controller import ControllerConfig, DeepSeekToolController  # noqa: E402
from sec_agent.tool_harness import DEFAULT_SESSION_ROOT, SecAgentToolHarness  # noqa: E402


DEFAULT_EVAL_SET = REPO_ROOT / "eval_sets" / "sec_agent_multiturn_tool_harness_eval_reviewed_v1.json"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "quality" / "local_tool_controller_reviewed_v1_route_heuristic.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate SEC agent tool controller routing on reviewed multi-turn cases.")
    parser.add_argument("--eval-set", default=str(DEFAULT_EVAL_SET))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--route-only", action="store_true", default=True)
    parser.add_argument("--dispatch", dest="route_only", action="store_false")
    parser.add_argument("--execute-tools", action="store_true")
    parser.add_argument("--strict-execute", action="store_true", help="Compare expected execute arguments in route-only mode.")
    parser.add_argument("--session-root", default=str(DEFAULT_SESSION_ROOT))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument(
        "--controller-backend",
        default=os.environ.get("TOOL_CONTROLLER_BACKEND", "heuristic"),
        choices=("deepseek", "openai_compatible", "qwen_vllm", "heuristic"),
    )
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument(
        "--chat-completions-path",
        default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"),
    )
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=1024)
    parser.add_argument("--timeout-s", type=int, default=180)
    parser.add_argument("--max-steps", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    eval_path = Path(args.eval_set)
    scenarios = json.loads(eval_path.read_text(encoding="utf-8"))
    if not isinstance(scenarios, list):
        raise ValueError("eval set must be a JSON array")

    harness = SecAgentToolHarness(session_root=args.session_root, python=args.python)
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
            max_steps=args.max_steps,
            execute_tools=bool(args.execute_tools),
        ),
    )

    turn_results = []
    prior_by_scenario: dict[str, list[dict[str, Any]]] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        scenario_id = str(scenario.get("scenario_id") or "")
        initial_state = scenario.get("initial_state") if isinstance(scenario.get("initial_state"), dict) else {}
        prior_by_scenario.setdefault(scenario_id, [])
        for turn in scenario.get("turns") or []:
            if not isinstance(turn, dict):
                continue
            expected_args = turn.get("expected_arguments") if isinstance(turn.get("expected_arguments"), dict) else {}
            expected_context = turn.get("expected_context") if isinstance(turn.get("expected_context"), dict) else {}
            runtime_session_id = str(expected_args.get("session_id") or initial_state.get("session_id") or "")
            runtime_user_id = str(expected_args.get("user_id") or initial_state.get("user_id") or "")
            runtime_active_answer_id = str(
                expected_args.get("answer_id")
                or expected_context.get("active_answer_id")
                or initial_state.get("active_answer_id")
                or ""
            )
            runtime_context = {
                "initial_state": initial_state,
                "expected_context": expected_context,
                "prior_tool_calls": prior_by_scenario[scenario_id],
            }
            controller_result = controller.run_turn(
                user_message=str(turn.get("user_message") or ""),
                session_id=runtime_session_id,
                user_id=runtime_user_id,
                tenant_id=str(initial_state.get("tenant_id") or ""),
                active_answer_id=runtime_active_answer_id,
                runtime_context=runtime_context,
                route_only=bool(args.route_only),
            )
            actual_call = (controller_result.get("tool_calls") or [{}])[0]
            actual_tool = str(actual_call.get("name") or "")
            actual_args = actual_call.get("arguments") if isinstance(actual_call.get("arguments"), dict) else {}
            expected_tool = str(turn.get("expected_tool") or "")
            arg_mismatches = _compare_expected_subset(
                expected=expected_args,
                actual=actual_args,
                ignore_execute=bool(args.route_only and not args.strict_execute),
            )
            row = {
                "scenario_id": scenario_id,
                "category": scenario.get("category", ""),
                "turn_id": turn.get("turn_id", ""),
                "expected_intent": turn.get("expected_intent", ""),
                "expected_tool": expected_tool,
                "actual_tool": actual_tool,
                "tool_pass": actual_tool == expected_tool,
                "arg_pass": not arg_mismatches,
                "arg_mismatches": arg_mismatches,
                "actual_arguments": actual_args,
                "controller_status": controller_result.get("status"),
                "route_only": controller_result.get("route_only"),
            }
            turn_results.append(row)
            prior_by_scenario[scenario_id].append(
                {
                    "turn_id": turn.get("turn_id", ""),
                    "tool_name": actual_tool,
                    "arguments": actual_args,
                }
            )

    failures = [row for row in turn_results if not row["tool_pass"] or not row["arg_pass"]]
    summary = {
        "schema_version": "sec_agent_tool_controller_eval_result_v0.1",
        "run_id": f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_tool_controller_reviewed_v1_{args.controller_backend}",
        "eval_set": str(eval_path.resolve()),
        "controller_backend": args.controller_backend,
        "route_only": bool(args.route_only),
        "execute_tools": bool(args.execute_tools),
        "strict_execute": bool(args.strict_execute),
        "scenario_count": len(scenarios),
        "turn_count": len(turn_results),
        "tool_pass_count": sum(1 for row in turn_results if row["tool_pass"]),
        "arg_pass_count": sum(1 for row in turn_results if row["arg_pass"]),
        "all_pass": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "turn_results": turn_results,
    }

    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in _SUMMARY_KEYS}, ensure_ascii=False, indent=2))
    return 0 if summary["all_pass"] else 1


_SUMMARY_KEYS = (
    "run_id",
    "eval_set",
    "controller_backend",
    "route_only",
    "execute_tools",
    "strict_execute",
    "scenario_count",
    "turn_count",
    "tool_pass_count",
    "arg_pass_count",
    "all_pass",
    "failure_count",
)


def _compare_expected_subset(*, expected: dict[str, Any], actual: dict[str, Any], ignore_execute: bool) -> list[dict[str, Any]]:
    mismatches = []
    for key, expected_value in expected.items():
        if ignore_execute and key == "execute":
            continue
        if key not in actual:
            mismatches.append({"key": key, "expected": expected_value, "actual": "<missing>"})
            continue
        actual_value = actual.get(key)
        if _normalize_value(actual_value) != _normalize_value(expected_value):
            mismatches.append({"key": key, "expected": expected_value, "actual": actual_value})
    return mismatches


def _normalize_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in sorted(value.items())}
    if isinstance(value, str):
        return value.strip()
    return value


if __name__ == "__main__":
    raise SystemExit(main())
