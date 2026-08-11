from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
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

from sec_agent.context_api import SecAgentContextRequestHandler  # noqa: E402
from sec_agent.context_manager import ContextBudget, SecAgentContextManager  # noqa: E402
from sec_agent.tool_controller import ControllerConfig, DeepSeekToolController  # noqa: E402
from sec_agent.tool_harness import SecAgentToolHarness  # noqa: E402

from evaluate_sec_agent_context_managed_tool_controller import _safe_rmtree  # noqa: E402
from evaluate_sec_agent_context_state_replay import _prepare_fixture_root, _write_completed_fixture  # noqa: E402


DEFAULT_FIXTURE_ROOT = REPO_ROOT / "reports" / "quality" / "local_context_api_smoke_fixture_runtime"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "quality" / "local_context_api_smoke_heuristic_v1.json"
TENANT_ID = "tenant_demo"
USER_ID = "u_api_multi"
OTHER_USER_ID = "u_api_other"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke-test request-level ContextManager API flow.")
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
    parser.add_argument("--disable-handler-lock", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    fixture_root = Path(args.fixture_root).resolve()
    _prepare_fixture_root(fixture_root)
    _write_api_fixture_world(fixture_root)
    handler = _build_handler(args=args, fixture_root=fixture_root)
    handler.context_manager.ingest_sessions()
    handler.context_manager.clear_active_session(tenant_id=TENANT_ID, user_id=USER_ID)

    cases = _api_smoke_cases()
    case_results = []
    for case in cases:
        result = handler.handle_turn(**case["request"])
        row = _evaluate_case(case=case, result=result)
        case_results.append(row)

    failures = [row for row in case_results if not row["all_pass"]]
    summary = {
        "schema_version": "sec_agent_context_api_smoke_result_v0.1",
        "run_id": f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_context_api_smoke_{args.controller_backend}",
        "fixture_root": str(fixture_root),
        "controller_backend": args.controller_backend,
        "handler_lock_enabled": not args.disable_handler_lock,
        "case_count": len(case_results),
        "pass_count": sum(1 for row in case_results if row["all_pass"]),
        "all_pass": not failures,
        "failure_count": len(failures),
        "failures": failures,
        "case_results": case_results,
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
    "fixture_root",
    "controller_backend",
    "handler_lock_enabled",
    "case_count",
    "pass_count",
    "all_pass",
    "failure_count",
)


def _write_api_fixture_world(fixture_root: Path) -> None:
    _write_completed_fixture(
        fixture_root=fixture_root,
        run_name="api_smoke_multi_nvda",
        session_id="s_api_multi_nvda",
        user_id=USER_ID,
        tenant_id=TENANT_ID,
        answer_id="ans_api_multi_nvda_2024_2025",
        query="API smoke completed NVDA 2024-2025 memo",
        tickers=["NVDA"],
        years=[2024, 2025],
        metrics=[
            {
                "metric_id": "api_nvda_data_center_revenue_2025",
                "evidence_id": "api_ev_nvda_data_center_2025",
                "ticker": "NVDA",
                "year": 2025,
                "metric_name": "data center revenue",
                "value": 47500,
                "unit": "usd_millions",
                "claim": "NVDA data center revenue supports the AI infrastructure thesis.",
            },
            {
                "metric_id": "api_nvda_gross_margin_2025",
                "evidence_id": "api_ev_nvda_margin_2025",
                "ticker": "NVDA",
                "year": 2025,
                "metric_name": "gross margin",
                "value": 73.8,
                "unit": "percent",
                "claim": "NVDA gross margin supports profitability quality.",
            },
        ],
    )
    _write_completed_fixture(
        fixture_root=fixture_root,
        run_name="api_smoke_multi_amzn_meta",
        session_id="s_api_multi_amzn_meta",
        user_id=USER_ID,
        tenant_id=TENANT_ID,
        answer_id="ans_api_multi_amzn_meta_2025",
        query="API smoke completed AMZN/META 2025 memo",
        tickers=["AMZN", "META"],
        years=[2025],
        metrics=[
            {
                "metric_id": "api_amzn_advertising_revenue_2025",
                "evidence_id": "api_ev_amzn_ads_2025",
                "ticker": "AMZN",
                "year": 2025,
                "metric_name": "advertising services revenue",
                "value": 56000,
                "unit": "usd_millions",
                "claim": "AMZN advertising business growth broadens monetization beyond retail.",
            },
            {
                "metric_id": "api_meta_advertising_revenue_2025",
                "evidence_id": "api_ev_meta_ads_2025",
                "ticker": "META",
                "year": 2025,
                "metric_name": "advertising revenue",
                "value": 164000,
                "unit": "usd_millions",
                "claim": "META advertising revenue scale is the core peer readthrough.",
            },
        ],
    )


def _build_handler(*, args: argparse.Namespace, fixture_root: Path) -> SecAgentContextRequestHandler:
    session_root = fixture_root / "session_harness"
    context_manager = SecAgentContextManager(
        session_root=session_root,
        context_root=fixture_root / "context_store",
        budget=ContextBudget(
            target_controller_tokens=3000,
            caution_controller_tokens=6000,
            max_recent_turns=5,
            max_candidate_sessions=3,
        ),
    )
    harness = SecAgentToolHarness(
        session_root=session_root,
        python="__sec_agent_context_api_smoke_should_not_execute__",
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
    return SecAgentContextRequestHandler(
        context_manager=context_manager,
        controller=controller,
        harness=harness,
        lock_requests=not args.disable_handler_lock,
    )


def _api_smoke_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "api_no_active_ambiguous_returns_clarification",
            "request": {
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "session_id": "",
                "user_message": "继续刚才那个 memo。",
            },
            "expected_status": "clarification_required",
            "expected_reason": "ambiguous_session_reference",
            "min_candidate_count": 2,
        },
        {
            "case_id": "api_explicit_session_inspect_coverage_sets_active",
            "request": {
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "session_id": "s_api_multi_nvda",
                "user_message": "覆盖完整吗？",
            },
            "expected_status": "completed",
            "expected_tool": "inspect_coverage",
            "expected_post_session_id": "s_api_multi_nvda",
        },
        {
            "case_id": "api_followup_uses_active_session_for_evidence",
            "request": {
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "session_id": "",
                "user_message": "第二个 why_it_matters 的证据是什么？",
            },
            "expected_status": "completed",
            "expected_tool": "explain_evidence",
            "expected_post_session_id": "s_api_multi_nvda",
            "expected_payload_nonempty": True,
        },
        {
            "case_id": "api_explicit_switch_changes_active_session",
            "request": {
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "session_id": "s_api_multi_amzn_meta",
                "user_message": "切到 AMZN/META 这个，确认一下当前状态。",
            },
            "expected_status": "completed",
            "expected_tool": "get_session_state",
            "expected_post_session_id": "s_api_multi_amzn_meta",
        },
        {
            "case_id": "api_followup_reformat_invalidates_render_only",
            "request": {
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "session_id": "",
                "user_message": "改成 PM 5 bullets，保留引用。",
            },
            "expected_status": "completed",
            "expected_tool": "reformat_answer",
            "expected_post_session_id": "s_api_multi_amzn_meta",
            "expected_invalidated_artifacts": ["rendered_answer"],
        },
        {
            "case_id": "api_cross_user_session_denied",
            "request": {
                "tenant_id": TENANT_ID,
                "user_id": OTHER_USER_ID,
                "session_id": "s_api_multi_nvda",
                "user_message": "当前状态是什么？",
            },
            "expected_status": "access_denied",
            "expected_no_tool_call": True,
        },
    ]


def _evaluate_case(*, case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    checks = []
    expected_status = case.get("expected_status")
    checks.append({"name": "status", "passed": result.get("status") == expected_status, "expected": expected_status, "actual": result.get("status")})
    expected_reason = case.get("expected_reason")
    if expected_reason:
        checks.append({"name": "reason", "passed": result.get("reason") == expected_reason, "expected": expected_reason, "actual": result.get("reason")})
    min_candidate_count = int(case.get("min_candidate_count") or 0)
    if min_candidate_count:
        candidates = (result.get("context_snapshot") or {}).get("session_candidates") or []
        checks.append({"name": "candidate_count", "passed": len(candidates) >= min_candidate_count, "expected": min_candidate_count, "actual": len(candidates)})
    expected_tool = case.get("expected_tool")
    if expected_tool:
        checks.append(
            {
                "name": "tool",
                "passed": (result.get("tool_call") or {}).get("name") == expected_tool,
                "expected": expected_tool,
                "actual": (result.get("tool_call") or {}).get("name"),
            }
        )
    if case.get("expected_no_tool_call"):
        checks.append({"name": "no_tool_call", "passed": not (result.get("tool_call") or {}).get("name")})
    expected_post_session_id = case.get("expected_post_session_id")
    if expected_post_session_id:
        post = result.get("post_context_snapshot") or {}
        checks.append(
            {
                "name": "post_session",
                "passed": post.get("session_id") == expected_post_session_id,
                "expected": expected_post_session_id,
                "actual": post.get("session_id"),
            }
        )
        checks.append({"name": "post_snapshot_valid", "passed": not post.get("validation_errors"), "actual": post.get("validation_errors") or []})
    expected_invalidated = case.get("expected_invalidated_artifacts")
    if expected_invalidated is not None:
        post = result.get("post_context_snapshot") or {}
        artifact_state = post.get("artifact_state") if isinstance(post.get("artifact_state"), dict) else {}
        checks.append(
            {
                "name": "invalidated_artifacts",
                "passed": artifact_state.get("invalidated_artifacts") == expected_invalidated,
                "expected": expected_invalidated,
                "actual": artifact_state.get("invalidated_artifacts"),
            }
        )
    if case.get("expected_payload_nonempty"):
        payload = ((result.get("tool_result") or {}).get("payload") or {})
        checks.append({"name": "payload_metric_or_evidence", "passed": bool(payload.get("metric_ids") or payload.get("evidence_ids"))})
    return {
        "case_id": case.get("case_id"),
        "status": result.get("status"),
        "tool": (result.get("tool_call") or {}).get("name", ""),
        "latency_ms": result.get("latency_ms"),
        "checks": checks,
        "all_pass": all(check["passed"] for check in checks),
        "result": result,
    }


if __name__ == "__main__":
    raise SystemExit(main())
