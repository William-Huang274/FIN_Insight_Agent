from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
SCRIPT_ROOT = REPO_ROOT / "scripts"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from sec_agent.context_manager import ContextBudget, SecAgentContextManager  # noqa: E402
from sec_agent.tool_controller import ControllerConfig, DeepSeekToolController  # noqa: E402
from sec_agent.tool_harness import SecAgentToolHarness  # noqa: E402

from evaluate_sec_agent_context_state_replay import (  # noqa: E402
    _prepare_fixture_root,
    _write_completed_fixture,
    _write_partial_fixture,
)


DEFAULT_EVAL_SET = REPO_ROOT / "eval_sets" / "sec_agent_multiturn_noncontiguous_followup_eval_v1.json"
DEFAULT_FIXTURE_ROOT = REPO_ROOT / "reports" / "quality" / "local_context_managed_tool_controller_fixture_runtime"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "quality" / "local_context_managed_tool_controller_route_heuristic_v1.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate tool routing using ContextManager-built controller snapshots.")
    parser.add_argument("--eval-set", default=str(DEFAULT_EVAL_SET))
    parser.add_argument("--fixture-root", default=str(DEFAULT_FIXTURE_ROOT))
    parser.add_argument("--output-path", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--keep-fixtures", action="store_true", default=True)
    parser.add_argument("--clean-fixtures", dest="keep_fixtures", action="store_false")
    parser.add_argument(
        "--controller-backend",
        default=os.environ.get("TOOL_CONTROLLER_BACKEND", "heuristic"),
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
    parser.add_argument("--max-steps", type=int, default=1)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    eval_path = Path(args.eval_set)
    scenarios = json.loads(eval_path.read_text(encoding="utf-8"))
    if not isinstance(scenarios, list):
        raise ValueError("eval set must be a JSON array")

    fixture_root = Path(args.fixture_root).resolve()
    _prepare_fixture_root(fixture_root)
    _write_eval_fixture_world(fixture_root)
    session_root = fixture_root / "session_harness"
    context_root = fixture_root / "context_store"
    context_manager = SecAgentContextManager(
        session_root=session_root,
        context_root=context_root,
        budget=ContextBudget(target_controller_tokens=3000, caution_controller_tokens=6000, max_recent_turns=5, max_candidate_sessions=3),
    )
    context_manager.ingest_sessions()

    harness = SecAgentToolHarness(
        session_root=session_root,
        python="__sec_agent_context_managed_fixture_should_not_execute__",
        repo_root=REPO_ROOT,
    )
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
            execute_tools=False,
        ),
    )

    turn_results = []
    prior_by_scenario: dict[str, list[dict[str, Any]]] = {}
    snapshot_failures: list[dict[str, Any]] = []
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
            expected_raw = turn.get("expected_arguments_raw") if isinstance(turn.get("expected_arguments_raw"), dict) else {}
            runtime_session_id = str(expected_args.get("session_id") or initial_state.get("session_id") or "")
            runtime_user_id = str(
                expected_args.get("user_id")
                or expected_context.get("user_id")
                or expected_raw.get("user_id")
                or _fixture_user_for_session(runtime_session_id)
                or initial_state.get("user_id")
                or ""
            )
            runtime_tenant_id = str(initial_state.get("tenant_id") or "tenant_demo")
            snapshot = context_manager.build_controller_context(
                tenant_id=runtime_tenant_id,
                user_id=runtime_user_id,
                session_id=runtime_session_id,
                user_message=str(turn.get("user_message") or ""),
            )
            if snapshot.get("status") != "ready" or snapshot.get("validation_errors"):
                snapshot_failures.append(
                    {
                        "scenario_id": scenario_id,
                        "turn_id": turn.get("turn_id", ""),
                        "status": snapshot.get("status"),
                        "reason": snapshot.get("reason", ""),
                        "validation_errors": snapshot.get("validation_errors") or [],
                    }
                )
            lossless = snapshot.get("lossless_fields") if isinstance(snapshot.get("lossless_fields"), dict) else {}
            runtime_active_answer_id = str(lossless.get("active_answer_id") or expected_args.get("answer_id") or expected_context.get("active_answer_id") or "")
            runtime_context = {
                "context_snapshot": snapshot,
                "expected_context": expected_context,
                "prior_tool_calls": prior_by_scenario[scenario_id],
            }
            controller_result = controller.run_turn(
                user_message=str(turn.get("user_message") or ""),
                session_id=runtime_session_id,
                user_id=runtime_user_id,
                tenant_id=runtime_tenant_id,
                active_answer_id=runtime_active_answer_id,
                runtime_context=runtime_context,
                route_only=True,
            )
            actual_call = (controller_result.get("tool_calls") or [{}])[0]
            actual_tool = str(actual_call.get("name") or "")
            actual_args = actual_call.get("arguments") if isinstance(actual_call.get("arguments"), dict) else {}
            expected_tool = str(turn.get("expected_tool") or "")
            arg_mismatches = _compare_expected_subset(
                expected=expected_args,
                actual=actual_args,
                ignore_execute=True,
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
                "snapshot_status": snapshot.get("status"),
                "snapshot_validation_errors": snapshot.get("validation_errors") or [],
                "snapshot_estimated_tokens": (snapshot.get("compression") or {}).get("estimated_tokens"),
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
        "schema_version": "sec_agent_context_managed_tool_controller_eval_result_v0.1",
        "run_id": f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_context_managed_tool_controller_{args.controller_backend}",
        "eval_set": str(eval_path.resolve()),
        "fixture_root": str(fixture_root),
        "controller_backend": args.controller_backend,
        "route_only": True,
        "scenario_count": len(scenarios),
        "turn_count": len(turn_results),
        "tool_pass_count": sum(1 for row in turn_results if row["tool_pass"]),
        "arg_pass_count": sum(1 for row in turn_results if row["arg_pass"]),
        "snapshot_pass_count": len(turn_results) - len(snapshot_failures),
        "all_pass": not failures and not snapshot_failures,
        "failure_count": len(failures) + len(snapshot_failures),
        "failures": failures,
        "snapshot_failures": snapshot_failures,
        "turn_results": turn_results,
    }
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.keep_fixtures:
        _safe_rmtree(fixture_root)
    print(json.dumps({key: summary[key] for key in _SUMMARY_KEYS}, ensure_ascii=False, indent=2))
    return 0 if summary["all_pass"] else 1


_SUMMARY_KEYS = (
    "run_id",
    "eval_set",
    "fixture_root",
    "controller_backend",
    "route_only",
    "scenario_count",
    "turn_count",
    "tool_pass_count",
    "arg_pass_count",
    "snapshot_pass_count",
    "all_pass",
    "failure_count",
)


def _write_eval_fixture_world(fixture_root: Path) -> None:
    _write_completed_fixture(
        fixture_root=fixture_root,
        run_name="completed_s_tool_002_msft_aapl",
        session_id="s_tool_002",
        user_id="u_research_002",
        tenant_id="tenant_demo",
        answer_id="ans_tool_002_msft_aapl_2023_2025",
        query="Fixture completed MSFT/AAPL 2023-2025 memo",
        tickers=["MSFT", "AAPL"],
        years=[2023, 2024, 2025],
        metrics=[
            {
                "metric_id": "ctx_msft_cloud_revenue_2025",
                "evidence_id": "ctx_ev_msft_cloud_2025",
                "ticker": "MSFT",
                "year": 2025,
                "metric_name": "cloud revenue",
                "value": 100000,
                "unit": "usd_millions",
                "claim": "MSFT cloud business growth supports the AI demand driver.",
            },
            {
                "metric_id": "ctx_aapl_gross_margin_2025",
                "evidence_id": "ctx_ev_aapl_margin_2025",
                "ticker": "AAPL",
                "year": 2025,
                "metric_name": "gross margin",
                "value": 46.5,
                "unit": "percent",
                "claim": "AAPL gross margin supports profitability context.",
            },
        ],
    )
    _write_completed_fixture(
        fixture_root=fixture_root,
        run_name="completed_s_tool_003_panw_crwd_snow",
        session_id="s_tool_003",
        user_id="u_pm_003",
        tenant_id="tenant_demo",
        answer_id="ans_tool_003_panw_crwd_snow_2024",
        query="Fixture completed PANW/CRWD/SNOW 2024 memo",
        tickers=["PANW", "CRWD", "SNOW"],
        years=[2024],
        metrics=[
            {
                "metric_id": "ctx_panw_revenue_2024",
                "evidence_id": "ctx_ev_panw_revenue_2024",
                "ticker": "PANW",
                "year": 2024,
                "metric_name": "revenue",
                "value": 8027,
                "unit": "usd_millions",
                "claim": "PANW revenue supports cybersecurity growth context.",
            }
        ],
    )
    _write_completed_fixture(
        fixture_root=fixture_root,
        run_name="completed_s_tool_004a_nvda",
        session_id="s_tool_004_a",
        user_id="u_research_004_a",
        tenant_id="tenant_demo",
        answer_id="ans_tool_004a_nvda_2024",
        query="Fixture completed NVDA 2024 memo",
        tickers=["NVDA"],
        years=[2024],
        metrics=[
            {
                "metric_id": "ctx_nvda_gross_margin_2024",
                "evidence_id": "ctx_ev_nvda_margin_2024",
                "ticker": "NVDA",
                "year": 2024,
                "metric_name": "gross margin",
                "value": 73.8,
                "unit": "percent",
                "claim": "NVDA gross margin improvement supports profitability quality.",
            },
            {
                "metric_id": "ctx_nvda_data_center_revenue_2024",
                "evidence_id": "ctx_ev_nvda_data_center_2024",
                "ticker": "NVDA",
                "year": 2024,
                "metric_name": "data center revenue",
                "value": 47500,
                "unit": "usd_millions",
                "claim": "NVDA data center growth supports the AI infrastructure thesis.",
            },
        ],
    )
    _write_completed_fixture(
        fixture_root=fixture_root,
        run_name="completed_s_tool_004b_amzn_meta",
        session_id="s_tool_004_b",
        user_id="u_research_004_b",
        tenant_id="tenant_demo",
        answer_id="ans_tool_004b_amzn_meta_2025",
        query="Fixture completed AMZN/META 2025 memo",
        tickers=["AMZN", "META"],
        years=[2025],
        metrics=[
            {
                "metric_id": "ctx_amzn_advertising_revenue_2025",
                "evidence_id": "ctx_ev_amzn_ads_2025",
                "ticker": "AMZN",
                "year": 2025,
                "metric_name": "advertising services revenue",
                "value": 56000,
                "unit": "usd_millions",
                "claim": "AMZN advertising business growth broadens monetization beyond retail.",
            },
            {
                "metric_id": "ctx_meta_advertising_revenue_2025",
                "evidence_id": "ctx_ev_meta_ads_2025",
                "ticker": "META",
                "year": 2025,
                "metric_name": "advertising revenue",
                "value": 164000,
                "unit": "usd_millions",
                "claim": "META advertising revenue scale is the core peer readthrough.",
            },
        ],
    )
    _write_partial_fixture(
        fixture_root=fixture_root,
        session_root=fixture_root / "session_harness",
    )
    _rename_partial_fixture_ids(fixture_root)


def _fixture_user_for_session(session_id: str) -> str:
    return {
        "s_tool_002": "u_research_002",
        "s_tool_003": "u_pm_003",
        "s_tool_004_a": "u_research_004_a",
        "s_tool_004_b": "u_research_004_b",
        "s_tool_005": "u_research_005",
    }.get(str(session_id or ""), "")


def _rename_partial_fixture_ids(fixture_root: Path) -> None:
    source_dir = fixture_root / "session_harness" / "ctx_session_a_partial_amzn_meta"
    target_dir = fixture_root / "session_harness" / "s_tool_005"
    if target_dir.exists():
        shutil.rmtree(target_dir)
    source_dir.rename(target_dir)
    session_path = target_dir / "session_state.json"
    session = json.loads(session_path.read_text(encoding="utf-8"))
    old_answer_id = str(session.get("active_answer_id") or "")
    session["session_id"] = "s_tool_005"
    session["user_id"] = "u_research_005"
    session["tenant_id"] = "tenant_demo"
    session["active_answer_id"] = "ans_tool_005_amzn_meta_2024_2025_partial"
    if old_answer_id in session.get("analyses", {}):
        analysis = session["analyses"].pop(old_answer_id)
        analysis["answer_id"] = "ans_tool_005_amzn_meta_2024_2025_partial"
        analysis["query"] = "Fixture partial AMZN/META 2024-2025 memo"
        session["analyses"]["ans_tool_005_amzn_meta_2024_2025_partial"] = analysis
    session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def _safe_rmtree(path: Path) -> None:
    resolved = path.resolve()
    repo = REPO_ROOT.resolve()
    if not str(resolved).startswith(str(repo)):
        raise AssertionError(f"refusing to remove outside repo: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)


if __name__ == "__main__":
    raise SystemExit(main())
