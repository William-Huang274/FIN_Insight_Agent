from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SCRIPT_ROOT = REPO_ROOT / "scripts" / "eval_multi_agent"
for root in (SRC_ROOT, SCRIPT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph_from_env  # noqa: E402
from sec_agent.multi_agent_runtime import active_specialists_for_state, build_agent_data_view  # noqa: E402
from sec_agent.multi_agent_contracts import validate_specialist_memolet  # noqa: E402
from sec_agent.specialist_llm import build_shared_specialist_context, build_specialist_request_from_state  # noqa: E402


DEFAULT_INPUT = (
    REPO_ROOT
    / "eval"
    / "sec_cases"
    / "outputs"
    / "p33_gold_case_runs"
    / "p33_stepwise_coverage_reflection_enriched_state_after_fusion_fix_20260705_r3"
    / "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"
    / "coverage_reflection_compact_state.json"
)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "p33_gold_case_runs"
SUMMARY_SCHEMA_VERSION = "p33_optional_specialist_subgraph_stepwise_summary_v0_1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run only P33 optional_specialist_subgraph from an accepted coverage_reflection compact state. "
            "This is a node-level paid runner, not a full-chain runner."
        )
    )
    parser.add_argument("--input-state", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--chat-completions-path", default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("SPECIALIST_TEMPERATURE", "0")))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("SPECIALIST_MAX_TOKENS", "1800")))
    parser.add_argument("--timeout-s", type=int, default=int(os.environ.get("SPECIALIST_TIMEOUT_S", "180")))
    parser.add_argument("--max-repair-attempts", type=int, default=int(os.environ.get("SPECIALIST_MAX_REPAIR_ATTEMPTS", "0")))
    parser.add_argument("--fanout", action="store_true", help="Allow parallel specialist calls. Defaults to sequential for cost/debuggability.")
    parser.add_argument("--fanout-workers", type=int, default=int(os.environ.get("SEC_AGENT_SPECIALIST_FANOUT_WORKERS", "3")))
    parser.add_argument(
        "--only-agent",
        action="append",
        default=[],
        help="Run only the selected specialist agent(s) for targeted node repair. Can be repeated.",
    )
    parser.add_argument("--preflight-only", action="store_true", help="Write preflight and input-size diagnostics without calling the model.")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    raw_state = _read_json(args.input_state)
    run_id = args.run_id or _default_run_id()
    case_id = str(raw_state.get("case_id") or args.input_state.parent.name or "p33_case")
    case_dir = args.output_root / run_id / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    state = _hydrate_state(raw_state, run_id=run_id, case_id=case_id, case_dir=case_dir, only_agents=args.only_agent)
    expected_specialists = active_specialists_for_state(state)
    preflight = _preflight_state(state, expected_specialists=expected_specialists, args=args)
    if preflight["status"] != "pass" or args.preflight_only:
        summary = _summary(
            state=state,
            result={},
            preflight=preflight,
            elapsed_sec=round(time.time() - started, 4),
            args=args,
            run_id=run_id,
            case_id=case_id,
            case_dir=case_dir,
        )
        _write_summary(case_dir, summary)
        print(json.dumps(_stdout_summary(summary, case_dir), ensure_ascii=False, indent=2))
        if args.preflight_only:
            return 0 if preflight["status"] == "pass" else 1
        return 1

    graph = build_multi_agent_orchestration_graph_from_env(
        env=_graph_env(args),
        use_checkpointer=False,
        entry_node="optional_specialist_subgraph",
        stop_after_node="optional_specialist_subgraph",
    )
    result = graph.invoke(state, config={"configurable": {"thread_id": f"{run_id}-{case_id}-specialists"}})
    summary = _summary(
        state=state,
        result=result,
        preflight=preflight,
        elapsed_sec=round(time.time() - started, 4),
        args=args,
        run_id=run_id,
        case_id=case_id,
        case_dir=case_dir,
    )
    _write_summary(case_dir, summary, result=result)
    print(json.dumps(_stdout_summary(summary, case_dir), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def _hydrate_state(
    raw_state: Mapping[str, Any],
    *,
    run_id: str,
    case_id: str,
    case_dir: Path,
    only_agents: list[str] | None = None,
) -> dict[str, Any]:
    state = dict(raw_state)
    activation = state.get("agent_activation_plan") if isinstance(state.get("agent_activation_plan"), Mapping) else {}
    activation = dict(activation)
    selected_agents = [str(item).strip() for item in only_agents or [] if str(item).strip()]
    if selected_agents:
        selected = set(selected_agents)
        original_agents = _string_list(activation.get("activate_agents"))
        activation["activate_agents"] = [agent_id for agent_id in original_agents if agent_id in selected] or selected_agents
        activation["targeted_specialist_repair"] = {
            "schema_version": "p33_targeted_specialist_repair_v0_1",
            "selected_agents": selected_agents,
            "original_activate_agents": original_agents,
            "policy": "rerun_only_selected_specialists_to_avoid_repeating_unrelated_paid_calls",
        }
    roc = activation.get("research_objective_contract") if isinstance(activation.get("research_objective_contract"), Mapping) else {}
    thesis_path = activation.get("thesis_path") if isinstance(activation.get("thesis_path"), Mapping) else {}
    user_query = str(state.get("user_query") or roc.get("core_question") or thesis_path.get("primary_question") or "")
    focus_tickers = _string_list(state.get("focus_tickers") or activation.get("focus_tickers"))
    search_scope_tickers = _string_list(state.get("search_scope_tickers") or activation.get("search_scope_tickers"))
    query_contract = dict(state.get("query_contract") or {})
    query_contract.setdefault("focus_tickers", focus_tickers)
    query_contract.setdefault("search_scope_tickers", search_scope_tickers)
    query_contract.setdefault("user_query", user_query)
    return {
        **state,
        "run_id": run_id,
        "case_id": case_id,
        "output_dir": str(case_dir.resolve()),
        "status": "running",
        "native_stop_after_node": "",
        "user_query": user_query,
        "query_contract": query_contract,
        "agent_activation_plan": activation,
        "focus_tickers": focus_tickers,
        "search_scope_tickers": search_scope_tickers,
    }


def _preflight_state(state: Mapping[str, Any], *, expected_specialists: list[str], args: argparse.Namespace) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not expected_specialists:
        errors.append({"type": "no_active_specialists"})
    if not os.environ.get(str(args.api_key_env or "")):
        errors.append({"type": "missing_api_key_env", "api_key_env": args.api_key_env})
    fusion_rows = (state.get("evidence_fusion_bundle") or {}).get("authority_rows") if isinstance(state.get("evidence_fusion_bundle"), Mapping) else []
    if not fusion_rows:
        errors.append({"type": "missing_fused_authority_rows"})
    if not state.get("user_query"):
        warnings.append({"type": "user_query_empty_after_hydration"})
    role_views: dict[str, Any] = {}
    shared_context = build_shared_specialist_context(state)
    for agent_id in expected_specialists:
        view = build_agent_data_view(agent_id, state)
        request = build_specialist_request_from_state(agent_id, state, shared_context=shared_context)
        rows = [row for row in view.get("bounded_evidence_rows") or [] if isinstance(row, Mapping)]
        if not rows:
            errors.append({"type": "specialist_has_no_bounded_rows", "agent_id": agent_id})
        role_views[agent_id] = {
            "status": view.get("status") or "",
            "row_count": len(rows),
            "required_claim_slot_count": len(view.get("required_claim_slots") or []),
            "counterclaim_slot_count": len(view.get("counterclaim_slots") or []),
            "relationship_summary_count": len((view.get("relationship_summary") or {}).get("relationships") or [])
            if isinstance(view.get("relationship_summary"), Mapping)
            else 0,
            "request_json_chars": len(json.dumps(request, ensure_ascii=False, default=str)),
            "bounded_prompt_row_count": len(request.get("bounded_evidence_rows") or []),
            "known_evidence_ref_count": len(request.get("known_evidence_refs") or []),
        }
    return {
        "schema_version": "p33_optional_specialist_subgraph_preflight_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "expected_specialists": expected_specialists,
        "fusion_authority_row_count": len(fusion_rows or []),
        "role_views": role_views,
        "provider": {
            "llm_backend": args.llm_backend,
            "base_url": args.base_url,
            "model": args.model,
            "api_key_env": args.api_key_env,
            "api_key_present": bool(args.api_key_env and os.environ.get(str(args.api_key_env))),
            "api_key_saved": False,
        },
    }


def _summary(
    *,
    state: Mapping[str, Any],
    result: Mapping[str, Any],
    preflight: Mapping[str, Any],
    elapsed_sec: float,
    args: argparse.Namespace,
    run_id: str,
    case_id: str,
    case_dir: Path,
) -> dict[str, Any]:
    expected = list(preflight.get("expected_specialists") or [])
    route_results = [dict(row) for row in result.get("specialist_route_results") or [] if isinstance(row, Mapping)]
    outputs = [dict(row) for row in result.get("specialist_outputs") or [] if isinstance(row, Mapping)]
    output_by_agent = {str(row.get("agent_id") or ""): row for row in outputs}
    route_by_agent = {str(row.get("agent_id") or ""): row for row in route_results}
    agent_scores = {
        agent_id: _agent_score(agent_id, output_by_agent.get(agent_id) or {}, route_by_agent.get(agent_id) or {})
        for agent_id in expected
    }
    checks = {
        "preflight_pass": preflight.get("status") == "pass",
        "stopped_after_specialists": result.get("status") == "stopped_after_node"
        and result.get("native_stop_after_node") == "optional_specialist_subgraph",
        "all_expected_routes_present": set(expected) <= set(route_by_agent),
        "all_expected_routes_pass": all(str((route_by_agent.get(agent_id) or {}).get("status") or "") == "pass" for agent_id in expected),
        "all_expected_outputs_present": set(expected) <= set(output_by_agent),
        "all_outputs_have_judgment_candidates": all(agent_scores.get(agent_id, {}).get("judgment_candidate_count", 0) > 0 for agent_id in expected),
        "risk_output_has_counter_material": (
            "risk_counterevidence_analyst" not in set(expected)
        ) or bool(
            agent_scores.get("risk_counterevidence_analyst", {}).get("unsupported_claim_count", 0)
            or agent_scores.get("risk_counterevidence_analyst", {}).get("conflict_count", 0)
            or agent_scores.get("risk_counterevidence_analyst", {}).get("judgment_candidate_count", 0)
        ),
    }
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "created_at": _utc_now(),
        "gate_status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "elapsed_sec": elapsed_sec,
        "provider": preflight.get("provider") or {},
        "input_state": {
            "case_id": state.get("case_id"),
            "source_run_id": state.get("run_id"),
            "fusion_authority_row_count": preflight.get("fusion_authority_row_count"),
            "bounded_gap_count": len(state.get("bounded_gap_register") or []),
            "coverage_sufficiency_level": (state.get("multi_agent_reflection_report") or {}).get("sufficiency_level")
            if isinstance(state.get("multi_agent_reflection_report"), Mapping)
            else "",
        },
        "preflight": preflight,
        "node": {
            "status": result.get("status") or "",
            "native_stop_after_node": result.get("native_stop_after_node") or "",
            "node_trace": result.get("node_trace") or [],
        },
        "expected_specialists": expected,
        "agent_scores": agent_scores,
        "token_usage": _token_usage(route_results),
        "artifact_refs": {
            "case_dir": str(case_dir.resolve()),
            "summary": str((case_dir / "optional_specialist_subgraph_summary.json").resolve()),
            "node_result": str((case_dir / "optional_specialist_subgraph_node_result.json").resolve()),
        },
        "boundary": {
            "scope": "node_level_optional_specialist_subgraph_only",
            "not_run": ["aggregate_judgment_plan", "memo_writer", "verifier", "renderer", "broad_full_chain", "model_comparison"],
            "acceptance_meaning": "specialists consumed role-specific fused evidence and produced accepted SpecialistMemolets/JudgmentCandidates; this does not prove final memo quality.",
        },
    }


def _agent_score(agent_id: str, memolet: Mapping[str, Any], route: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_specialist_memolet(memolet)
    observations = [row for row in memolet.get("observations") or [] if isinstance(row, Mapping)]
    judgments = [row for row in memolet.get("judgment_candidates") or [] if isinstance(row, Mapping)]
    unsupported = [row for row in memolet.get("unsupported_claims") or [] if isinstance(row, Mapping)]
    conflicts = [row for row in memolet.get("conflicts") or [] if isinstance(row, Mapping)]
    return {
        "agent_id": agent_id,
        "route_status": route.get("status") or "",
        "validation_status": validation.get("status") or "",
        "validation_error_count": len(validation.get("errors") or []),
        "validation_warning_count": len(validation.get("warnings") or []),
        "status": memolet.get("status") or "",
        "summary_chars": len(str(memolet.get("summary") or "")),
        "observation_count": len(observations),
        "judgment_candidate_count": len(judgments),
        "unsupported_claim_count": len(unsupported),
        "conflict_count": len(conflicts),
        "required_items_answered": sorted(
            {
                str(row.get("required_item_answered") or "")
                for row in judgments
                if str(row.get("required_item_answered") or "").strip()
            }
        ),
        "confidence": memolet.get("confidence") or "",
        "repair_attempts": int(route.get("repair_attempts") or 0),
        "input_tokens": int(route.get("input_tokens") or 0),
        "output_tokens": int(route.get("output_tokens") or 0),
        "total_tokens": int(route.get("total_tokens") or 0),
        "failure_reason": str(route.get("failure_reason") or "")[:500],
    }


def _write_summary(case_dir: Path, summary: Mapping[str, Any], *, result: Mapping[str, Any] | None = None) -> None:
    (case_dir / "optional_specialist_subgraph_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if result:
        compact_result = {
            "status": result.get("status") or "",
            "native_stop_after_node": result.get("native_stop_after_node") or "",
            "node_trace": result.get("node_trace") or [],
            "specialist_activation_decisions": result.get("specialist_activation_decisions") or [],
            "specialist_route_results": result.get("specialist_route_results") or [],
            "specialist_outputs": result.get("specialist_outputs") or [],
            "specialist_fanout_barrier": result.get("specialist_fanout_barrier") or {},
        }
        (case_dir / "optional_specialist_subgraph_node_result.json").write_text(
            json.dumps(compact_result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _stdout_summary(summary: Mapping[str, Any], case_dir: Path) -> dict[str, Any]:
    return {
        "schema_version": summary.get("schema_version"),
        "run_id": summary.get("run_id"),
        "case_id": summary.get("case_id"),
        "gate_status": summary.get("gate_status"),
        "checks": summary.get("checks"),
        "token_usage": summary.get("token_usage"),
        "agent_scores": {
            agent_id: {
                "route_status": row.get("route_status"),
                "judgment_candidate_count": row.get("judgment_candidate_count"),
                "observation_count": row.get("observation_count"),
                "unsupported_claim_count": row.get("unsupported_claim_count"),
                "conflict_count": row.get("conflict_count"),
                "total_tokens": row.get("total_tokens"),
                "failure_reason": row.get("failure_reason"),
            }
            for agent_id, row in (summary.get("agent_scores") or {}).items()
            if isinstance(row, Mapping)
        },
        "summary_path": str((case_dir / "optional_specialist_subgraph_summary.json").resolve()),
    }


def _graph_env(args: argparse.Namespace) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "LLM_BACKEND": args.llm_backend,
            "BASE_URL": args.base_url,
            "CHAT_COMPLETIONS_PATH": args.chat_completions_path,
            "MODEL_NAME": args.model,
            "API_KEY_ENV": args.api_key_env,
            "SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER": "llm",
            "SPECIALIST_TEMPERATURE": str(args.temperature),
            "SPECIALIST_MAX_TOKENS": str(args.max_tokens),
            "SPECIALIST_TIMEOUT_S": str(args.timeout_s),
            "SPECIALIST_MAX_REPAIR_ATTEMPTS": str(args.max_repair_attempts),
            "SEC_AGENT_SPECIALIST_FANOUT": "1" if args.fanout else "0",
            "SEC_AGENT_SPECIALIST_FANOUT_WORKERS": str(args.fanout_workers),
        }
    )
    return env


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _token_usage(route_results: list[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in route_results),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in route_results),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in route_results),
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _default_run_id() -> str:
    return f"p33_stepwise_optional_specialist_subgraph_deepseek_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
