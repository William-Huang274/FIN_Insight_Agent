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

from sec_agent.context_manager import ContextBudget, SecAgentContextManager  # noqa: E402
from sec_agent.graph_state import SecAgentState  # noqa: E402
from sec_agent.tool_controller import ControllerConfig, DeepSeekToolController  # noqa: E402
from sec_agent.tool_harness import SecAgentToolHarness  # noqa: E402

from evaluate_sec_agent_context_managed_tool_controller import (  # noqa: E402
    DEFAULT_EVAL_SET,
    _compare_expected_subset,
    _fixture_user_for_session,
    _safe_rmtree,
    _write_eval_fixture_world,
)
from evaluate_sec_agent_context_state_replay import _prepare_fixture_root  # noqa: E402


DEFAULT_FIXTURE_ROOT = REPO_ROOT / "reports" / "quality" / "local_context_managed_dispatch_replay_fixture_runtime"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "quality" / "local_context_managed_dispatch_replay_heuristic_v1.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay ContextManager -> controller route -> harness dispatch -> context update.")
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
    context_manager = SecAgentContextManager(
        session_root=session_root,
        context_root=fixture_root / "context_store",
        budget=ContextBudget(target_controller_tokens=3000, caution_controller_tokens=6000, max_recent_turns=5, max_candidate_sessions=3),
    )
    context_manager.ingest_sessions()

    harness = SecAgentToolHarness(
        session_root=session_root,
        python="__sec_agent_context_managed_dispatch_fixture_should_not_execute__",
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
    failures = []
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        scenario_id = str(scenario.get("scenario_id") or "")
        initial_state = scenario.get("initial_state") if isinstance(scenario.get("initial_state"), dict) else {}
        prior_by_scenario.setdefault(scenario_id, [])
        for turn in scenario.get("turns") or []:
            if not isinstance(turn, dict):
                continue
            row = _run_turn(
                scenario_id=scenario_id,
                scenario=scenario,
                turn=turn,
                initial_state=initial_state,
                prior_tool_calls=prior_by_scenario[scenario_id],
                context_manager=context_manager,
                controller=controller,
                harness=harness,
            )
            turn_results.append(row)
            prior_by_scenario[scenario_id].append(
                {
                    "turn_id": turn.get("turn_id", ""),
                    "tool_name": row.get("actual_tool", ""),
                    "arguments": row.get("actual_arguments") or {},
                    "dispatch_status": row.get("dispatch_status", ""),
                }
            )
            if not row["all_pass"]:
                failures.append(row)

    summary = {
        "schema_version": "sec_agent_context_managed_dispatch_replay_result_v0.1",
        "run_id": f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_context_managed_dispatch_replay_{args.controller_backend}",
        "eval_set": str(eval_path.resolve()),
        "fixture_root": str(fixture_root),
        "controller_backend": args.controller_backend,
        "scenario_count": len(scenarios),
        "turn_count": len(turn_results),
        "tool_pass_count": sum(1 for row in turn_results if row["tool_pass"]),
        "arg_pass_count": sum(1 for row in turn_results if row["arg_pass"]),
        "snapshot_pass_count": sum(1 for row in turn_results if row["snapshot_pass"]),
        "dispatch_pass_count": sum(1 for row in turn_results if row["dispatch_pass"]),
        "context_update_pass_count": sum(1 for row in turn_results if row["context_update_pass"]),
        "all_pass": not failures,
        "failure_count": len(failures),
        "failures": failures,
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
    "scenario_count",
    "turn_count",
    "tool_pass_count",
    "arg_pass_count",
    "snapshot_pass_count",
    "dispatch_pass_count",
    "context_update_pass_count",
    "all_pass",
    "failure_count",
)


def _run_turn(
    *,
    scenario_id: str,
    scenario: dict[str, Any],
    turn: dict[str, Any],
    initial_state: dict[str, Any],
    prior_tool_calls: list[dict[str, Any]],
    context_manager: SecAgentContextManager,
    controller: DeepSeekToolController,
    harness: SecAgentToolHarness,
) -> dict[str, Any]:
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
    user_message = str(turn.get("user_message") or "")
    snapshot = context_manager.build_controller_context(
        tenant_id=runtime_tenant_id,
        user_id=runtime_user_id,
        session_id=runtime_session_id,
        user_message=user_message,
    )
    snapshot_pass = snapshot.get("status") == "ready" and not snapshot.get("validation_errors")
    lossless = snapshot.get("lossless_fields") if isinstance(snapshot.get("lossless_fields"), dict) else {}
    runtime_active_answer_id = str(
        lossless.get("active_answer_id")
        or expected_args.get("answer_id")
        or expected_context.get("active_answer_id")
        or ""
    )
    runtime_context = {
        "context_snapshot": snapshot,
        "expected_context": expected_context,
        "prior_tool_calls": prior_tool_calls,
    }
    controller_result = controller.run_turn(
        user_message=user_message,
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
    arg_mismatches = _compare_expected_subset(expected=expected_args, actual=actual_args, ignore_execute=True)
    tool_pass = actual_tool == expected_tool
    arg_pass = not arg_mismatches

    tool_result = harness.dispatch(actual_tool, actual_args).to_dict()
    dispatch_pass, dispatch_checks = _dispatch_pass(tool_name=actual_tool, result=tool_result)
    update_result = context_manager.apply_tool_result(tool_call=actual_call, tool_result=tool_result)
    if actual_tool == "resume_analysis" and tool_result.get("status") == "completed":
        _simulate_fixture_resume_completion(actual_args=actual_args, tool_result=tool_result)
    post_snapshot = context_manager.build_controller_context(
        tenant_id=runtime_tenant_id,
        user_id=runtime_user_id,
        session_id=runtime_session_id,
        user_message=user_message,
    )
    context_update_pass, context_checks = _context_update_pass(
        tool_name=actual_tool,
        tool_result=tool_result,
        update_result=update_result,
        post_snapshot=post_snapshot,
    )
    return {
        "scenario_id": scenario_id,
        "category": scenario.get("category", ""),
        "turn_id": turn.get("turn_id", ""),
        "expected_intent": turn.get("expected_intent", ""),
        "expected_tool": expected_tool,
        "actual_tool": actual_tool,
        "tool_pass": tool_pass,
        "arg_pass": arg_pass,
        "arg_mismatches": arg_mismatches,
        "snapshot_pass": snapshot_pass,
        "snapshot_status": snapshot.get("status"),
        "snapshot_validation_errors": snapshot.get("validation_errors") or [],
        "snapshot_estimated_tokens": (snapshot.get("compression") or {}).get("estimated_tokens"),
        "actual_arguments": actual_args,
        "controller_status": controller_result.get("status"),
        "dispatch_status": tool_result.get("status"),
        "dispatch_pass": dispatch_pass,
        "dispatch_checks": dispatch_checks,
        "context_update_status": update_result.get("status"),
        "context_update_pass": context_update_pass,
        "context_checks": context_checks,
        "post_snapshot_status": post_snapshot.get("status"),
        "post_snapshot_validation_errors": post_snapshot.get("validation_errors") or [],
        "all_pass": bool(tool_pass and arg_pass and snapshot_pass and dispatch_pass and context_update_pass),
    }


def _dispatch_pass(*, tool_name: str, result: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    checks = []
    status = str(result.get("status") or "")
    payload = result.get("payload") if isinstance(result.get("payload"), dict) else {}
    allowed_statuses = {"completed"}
    if tool_name == "reformat_answer":
        allowed_statuses.add("planned")
    checks.append({"name": "status_allowed", "passed": status in allowed_statuses, "actual": status})
    if tool_name in {"inspect_coverage", "explain_evidence"}:
        checks.append({"name": "no_rerun_required", "passed": payload.get("rerun_required") is False})
    if tool_name == "resume_analysis":
        checks.append({"name": "execute_false", "passed": payload.get("execute") is False})
        checks.append({"name": "no_graph_spawn", "passed": "returncode" not in payload})
    if tool_name == "reformat_answer":
        checks.append({"name": "rendered_only_invalidated", "passed": payload.get("invalidated_artifacts") == ["rendered_answer"]})
    if tool_name == "explain_evidence":
        metric_ids = payload.get("metric_ids") or []
        evidence_ids = payload.get("evidence_ids") or []
        checks.append({"name": "evidence_payload_nonempty", "passed": bool(metric_ids or evidence_ids)})
    return all(check["passed"] for check in checks), checks


def _context_update_pass(
    *,
    tool_name: str,
    tool_result: dict[str, Any],
    update_result: dict[str, Any],
    post_snapshot: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]]]:
    checks = [
        {"name": "update_accepted", "passed": update_result.get("status") in {"updated", "ignored"}},
        {"name": "post_snapshot_ready", "passed": post_snapshot.get("status") == "ready"},
        {"name": "post_snapshot_valid", "passed": not post_snapshot.get("validation_errors")},
    ]
    lossless = post_snapshot.get("lossless_fields") if isinstance(post_snapshot.get("lossless_fields"), dict) else {}
    artifact_state = lossless.get("artifact_state") if isinstance(lossless.get("artifact_state"), dict) else {}
    user_profile = post_snapshot.get("user_profile") if isinstance(post_snapshot.get("user_profile"), dict) else {}
    last_refs = user_profile.get("last_references") if isinstance(user_profile.get("last_references"), dict) else {}
    if tool_name == "reformat_answer":
        checks.append(
            {
                "name": "context_rendered_only_invalidated",
                "passed": artifact_state.get("invalidated_artifacts") == ["rendered_answer"],
                "actual": artifact_state.get("invalidated_artifacts"),
            }
        )
    if tool_name == "explain_evidence":
        payload = tool_result.get("payload") if isinstance(tool_result.get("payload"), dict) else {}
        checks.append(
            {
                "name": "last_reference_updated",
                "passed": bool(last_refs.get("last_metric_ids") or last_refs.get("last_evidence_ids")),
                "actual": {
                    "last_metric_ids": last_refs.get("last_metric_ids") or [],
                    "payload_metric_ids": payload.get("metric_ids") or [],
                },
            }
        )
    if tool_name == "resume_analysis":
        checks.append(
            {
                "name": "resume_cursor_visible",
                "passed": "next_ready_node" in (lossless.get("resume") or {}),
                "actual": lossless.get("resume") or {},
            }
        )
    return all(check["passed"] for check in checks), checks


def _simulate_fixture_resume_completion(*, actual_args: dict[str, Any], tool_result: dict[str, Any]) -> None:
    session_id = str(actual_args.get("session_id") or "")
    answer_id = str(actual_args.get("answer_id") or "")
    if session_id != "s_tool_005" or answer_id != "ans_tool_005_amzn_meta_2024_2025_partial":
        return
    payload = tool_result.get("payload") if isinstance(tool_result.get("payload"), dict) else {}
    state_path = Path(str(payload.get("state_path") or ""))
    if not state_path.exists():
        return
    run_root = state_path.parent
    (run_root / "qwen").mkdir(parents=True, exist_ok=True)
    files = {
        "evidence_coverage_matrix": _write_json(
            run_root / "runtime_evidence_coverage_matrix.json",
            {
                "schema_version": "sec_agent_evidence_coverage_matrix_v0.1",
                "case_id": answer_id,
                "tasks": [
                    {
                        "task_id": "task_s_tool_005_amzn_ads",
                        "required_tickers": ["AMZN"],
                        "covered_tickers": ["AMZN"],
                        "missing_tickers": [],
                        "covered_metric_families": ["advertising"],
                        "missing_metric_families": [],
                        "coverage_complete": True,
                        "answer_status": "complete",
                    }
                ],
                "summary": {
                    "task_count": 1,
                    "coverage_complete": True,
                    "answer_status": "complete",
                    "covered_focus_tickers": ["AMZN", "META"],
                    "missing_metric_families": [],
                    "ledger_row_count": 1,
                    "context_row_count": 2,
                },
            },
        ),
        "judgment_plan": _write_json(
            run_root / "runtime_judgment_plan.json",
            {
                "schema_version": "fixture_runtime_judgment_plan_v0.1",
                "plans": [
                    {
                        "case_id": answer_id,
                        "decision_drivers": [
                            {
                                "driver_id": "driver_s_tool_005_amzn_ads",
                                "driver_claim": "AMZN advertising revenue growth is supported by SEC 10-K evidence.",
                                "supporting_metric_ids": ["ctx_partial_amzn_ads_2025"],
                                "supporting_evidence_ids": ["ctx_ev_partial_amzn_ads_2025"],
                            }
                        ],
                    }
                ],
            },
        ),
        "evidence_pack": _write_json(run_root / "evidence_pack.json", {"schema_version": "fixture_evidence_pack_v0.1"}),
        "memo_answer": _write_jsonl(
            run_root / "qwen" / "agent_outputs.jsonl",
            [
                {
                    "schema_version": "fixture_agent_output_v0.1",
                    "case_id": answer_id,
                    "status": "answered",
                    "answer": {
                        "summary": "Fixture resumed AMZN/META memo.",
                        "decision_drivers": [
                            {
                                "driver_claim": "AMZN advertising revenue growth supports the monetization driver.",
                                "why_it_matters": "AMZN advertising growth broadens monetization beyond online stores.",
                                "supporting_metric_ids": ["ctx_partial_amzn_ads_2025"],
                                "supporting_evidence_ids": ["ctx_ev_partial_amzn_ads_2025"],
                                "conclusion_strength": "medium",
                            }
                        ],
                        "why_it_matters": [
                            {
                                "insight": "AMZN advertising business growth broadens monetization beyond retail.",
                                "business_implication": "Advertising revenue can support AMZN mix if SEC-reported scale continues.",
                                "metric_ids": ["ctx_partial_amzn_ads_2025"],
                                "evidence_ids": ["ctx_ev_partial_amzn_ads_2025"],
                                "confidence": "high",
                            }
                        ],
                        "what_changed": [
                            {
                                "claim": "AMZN advertising revenue increased in the fixture period.",
                                "metric_ids": ["ctx_partial_amzn_ads_2025"],
                                "evidence_ids": ["ctx_ev_partial_amzn_ads_2025"],
                                "confidence": "high",
                            }
                        ],
                        "key_points": [],
                        "not_found": [],
                        "limitations": [],
                    },
                }
            ],
        ),
        "claim_verification": _write_json(run_root / "claim_verification.json", {"schema_version": "fixture_claim_verification_v0.1"}),
        "deterministic_gates": _write_json(run_root / "deterministic_gates.json", {"schema_version": "fixture_gates_v0.1", "all_pass": True}),
        "rendered_answer": _write_text(run_root / "rendered_answer.md", "# Fixture resumed memo\n"),
    }
    state = SecAgentState.read_json(state_path)
    for key, path in files.items():
        state.with_artifact(key, path, schema_version=f"fixture_{key}_v0.1")
    for stage in ("build_coverage_matrix", "build_judgment_plan", "synthesize_memo", "verify_claims", "run_deterministic_gates", "render_answer"):
        state.mark_stage(stage, "completed", message="fixture resume completion")
    state.status = "completed"
    state.write_json(state_path)

    session_path = state_path.parents[2] / "session_harness" / session_id / "session_state.json"
    if not session_path.exists():
        # Fixture run roots live under reports/quality/.../runs, while session_harness
        # is a sibling of runs.
        session_path = state_path.parents[1].parent / "session_harness" / session_id / "session_state.json"
    if session_path.exists():
        session = json.loads(session_path.read_text(encoding="utf-8"))
        analysis = session.get("analyses", {}).get(answer_id)
        if isinstance(analysis, dict):
            analysis["status"] = "completed"
            analysis["artifact_refs"] = {key: ref.to_dict() for key, ref in state.artifacts.items()}
            analysis["execution"] = {"execute": True, "returncode": 0, "elapsed_sec": 0.0}
        session["updated_at"] = datetime.now().isoformat(timespec="seconds")
        session_path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
