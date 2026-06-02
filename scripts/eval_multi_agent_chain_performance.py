from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state  # noqa: E402


DEFAULT_CASES_PATH = REPO_ROOT / "tests" / "fixtures" / "multi_agent_chain_performance_cases_v0_1.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "reports" / "eval" / "multi_agent_chain_performance" / "current"


def run_eval(
    *,
    cases_path: Path = DEFAULT_CASES_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    limit: int = 0,
    fail_on_gate: bool = False,
) -> dict[str, Any]:
    cases = _read_jsonl(cases_path)
    if limit > 0:
        cases = cases[:limit]
    output_dir.mkdir(parents=True, exist_ok=True)

    scores: list[dict[str, Any]] = []
    for case in cases:
        case_dir = output_dir / str(case["case_id"])
        case_dir.mkdir(parents=True, exist_ok=True)
        started = time.time()
        result = _run_case(case, case_dir)
        elapsed_ms = int((time.time() - started) * 1000)
        summary = _read_json(case_dir / "multi_agent_summary.json")
        native = _read_json(case_dir / "langgraph_native_summary.json")
        score = _score_case(case, result, summary, native, elapsed_ms)
        (case_dir / "chain_performance_score.json").write_text(
            json.dumps(score, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        scores.append(score)

    aggregate = _aggregate(scores, output_dir=output_dir, cases_path=cases_path)
    _write_jsonl(output_dir / "chain_performance_scores.jsonl", scores)
    (output_dir / "chain_performance_summary.json").write_text(
        json.dumps(aggregate, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if fail_on_gate and aggregate["gate_status"] != "pass":
        raise SystemExit(1)
    return aggregate


def _run_case(case: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    fixture_mode = str(case.get("fixture_mode") or "default")
    graph = _graph_for_mode(fixture_mode)
    state = make_multi_agent_smoke_state(
        user_query=str(case.get("prompt") or ""),
        output_dir=output_dir,
        query_contract=_query_contract(case),
        focus_tickers=_string_list(case.get("focus_tickers")),
        search_scope_tickers=_string_list(case.get("search_scope_tickers")),
    )
    state["project_inventory"] = {
        "source_families": _string_list(case.get("source_tiers")),
        "tickers": _string_list(case.get("search_scope_tickers")),
    }
    state["multi_agent_context"] = {
        "run_dir": "eval/sec_cases/outputs/example_run" if fixture_mode == "run_artifact" else "",
        "market_snapshot": {"snapshot_id": "chain_perf_market_snapshot", "as_of_date": "2026-05-30"},
        "market_snapshot_id": "chain_perf_market_snapshot",
        "market_as_of_date": "2026-05-30",
        "industry_source_families": ["industry_snapshot"],
    }
    return graph.invoke(
        state,
        config={"configurable": {"thread_id": f"chain-performance-{case['case_id']}"}},
    )


def _graph_for_mode(fixture_mode: str):
    if fixture_mode == "inject_unsupported_specialist":
        return build_multi_agent_orchestration_graph(run_specialist_analysts=_unsupported_specialists)
    if fixture_mode == "inject_bad_memo_repair":
        return build_multi_agent_orchestration_graph(
            run_specialist_analysts=_supported_specialists,
            memo_writer=_bad_memo_writer,
        )
    return build_multi_agent_orchestration_graph()


def _unsupported_specialists(_state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "specialist_outputs": [
            {
                "agent_id": "risk_counterevidence_analyst",
                "unsupported_claims": [{"claim": "A named customer changed orders.", "reason": "not in bounded evidence"}],
            }
        ]
    }


def _supported_specialists(_state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "specialist_outputs": [
            {
                "agent_id": "fundamental_analyst",
                "observations": [
                    {
                        "claim": "Supported capex claim.",
                        "evidence_refs": ["capex_ref"],
                        "source_families": ["primary_sec_filing"],
                    }
                ],
            }
        ]
    }


def _bad_memo_writer(_state: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "memo_answer": {
            "answer_status": "draft",
            "direct_answer": "Supported capex claim.",
            "raw_rows_consumed": True,
            "tool_calls_requested": [{"tool": "sec_search_filings"}],
            "memo_claims": [
                {"claim": "Supported capex claim.", "evidence_refs": ["capex_ref"], "source_families": ["primary_sec_filing"]}
            ],
        }
    }


def _query_contract(case: Mapping[str, Any]) -> dict[str, Any]:
    tickers = _string_list(case.get("search_scope_tickers"))
    focus = _string_list(case.get("focus_tickers")) or tickers[:2]
    source_tiers = _string_list(case.get("source_tiers")) or ["primary_sec_filing"]
    if source_tiers == ["run_artifact"]:
        years: list[int] = []
        filing_types: list[str] = []
    else:
        years = [2026]
        filing_types = ["10-Q", "8-K"]
    return {
        "task_type": "open_analysis",
        "search_scope_tickers": tickers,
        "focus_tickers": focus,
        "years": years,
        "filing_types": filing_types,
        "source_tiers": source_tiers,
        "metric_families": ["revenue", "capex", "margin"],
        "decomposed_tasks": [
            {
                "task_id": "chain_performance_primary",
                "question_zh": str(case.get("prompt") or "")[:120],
                "priority": "primary",
                "required_tickers": tickers or focus,
                "required_metric_families": ["revenue", "capex", "margin"],
            }
        ],
    }


def _score_case(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
    summary: Mapping[str, Any],
    native: Mapping[str, Any],
    elapsed_ms: int,
) -> dict[str, Any]:
    activation = result.get("agent_activation_plan") if isinstance(result.get("agent_activation_plan"), Mapping) else {}
    active = set(_string_list(activation.get("activate_agents")))
    required = set(_string_list(case.get("required_agents")))
    forbidden = set(_string_list(case.get("forbidden_agents")))
    claim = result.get("claim_verification") if isinstance(result.get("claim_verification"), Mapping) else {}
    specialist = result.get("specialist_verification") if isinstance(result.get("specialist_verification"), Mapping) else {}
    memo = result.get("memo_answer") if isinstance(result.get("memo_answer"), Mapping) else {}
    universe = result.get("universe_relationship_validation") if isinstance(result.get("universe_relationship_validation"), Mapping) else {}
    route_budget = result.get("retrieval_plan") if isinstance(result.get("retrieval_plan"), Mapping) else {}
    route_pruning = route_budget.get("route_budget_pruning") if isinstance(route_budget.get("route_budget_pruning"), Mapping) else {}
    expected_universe = str(case.get("expected_universe_validation") or "")
    actual_universe = str(universe.get("status") or "skipped")
    expected_specialist = str(case.get("expected_specialist_verification") or "")
    actual_specialist = str(specialist.get("status") or "")
    expected_memo = str(case.get("expected_memo_status") or "")
    actual_memo = str(memo.get("answer_status") or "")
    tool_call_count = int(summary.get("tool_call_count") or (native.get("state_summary") or {}).get("tool_call_count") or 0)
    max_tool_calls = int(case.get("max_tool_calls_total_lte") or 999)
    rendered = str(result.get("rendered_answer") or "")
    summary_payload = json.dumps(summary, ensure_ascii=False)

    checks = {
        "status_completed": result.get("status") == "completed",
        "execution_mode_match": activation.get("execution_mode") == case.get("expected_execution_mode"),
        "activation_validation_pass": (result.get("agent_activation_validation") or {}).get("status") == "pass",
        "required_agents_present": required <= active,
        "forbidden_agents_absent": not (forbidden & active),
        "universe_validation_match": not expected_universe or actual_universe == expected_universe,
        "specialist_verification_match": not expected_specialist or actual_specialist == expected_specialist,
        "memo_status_match": not expected_memo or actual_memo == expected_memo,
        "claim_verification_pass": str(claim.get("status") or "pass") == "pass",
        "unsupported_claims_blocked_or_zero": int(claim.get("unsupported_claim_count") or 0) == 0,
        "tool_budget_lte": tool_call_count <= max_tool_calls,
        "no_budget_loop_break": str(result.get("loop_break_reason") or "") not in {"tool_budget_exhausted", "agent_tool_budget_exhausted"},
        "raw_payload_not_in_summary": (summary.get("payload_policy") or {}).get("raw_evidence") == "not_included",
        "no_private_path_or_secret": "raw_private" not in summary_payload and "sk-" not in summary_payload,
        "rendered_answer_not_empty": bool(rendered.strip()),
    }
    return {
        "case_id": case.get("case_id"),
        "category": case.get("category"),
        "gate_status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "elapsed_ms": elapsed_ms,
        "execution_mode": activation.get("execution_mode"),
        "activated_agents": sorted(active),
        "missing_required_agents": sorted(required - active),
        "forbidden_activated_agents": sorted(forbidden & active),
        "tool_call_count": tool_call_count,
        "max_tool_calls_total_lte": max_tool_calls,
        "loop_break_reason": result.get("loop_break_reason") or "",
        "memo_status": actual_memo,
        "claim_verification": claim.get("status") or "",
        "specialist_verification": actual_specialist,
        "universe_validation": actual_universe,
        "route_budget_pruning": {
            "dropped_route_count": int(route_pruning.get("dropped_route_count") or 0),
            "kept_route_count": int(route_pruning.get("kept_route_count") or 0),
        },
        "rendered_answer_preview": rendered[:240],
    }


def _aggregate(scores: list[dict[str, Any]], *, output_dir: Path, cases_path: Path) -> dict[str, Any]:
    passed = sum(1 for score in scores if score.get("gate_status") == "pass")
    failed = len(scores) - passed
    categories: dict[str, dict[str, int]] = {}
    for score in scores:
        category = str(score.get("category") or "unknown")
        bucket = categories.setdefault(category, {"case_count": 0, "passed": 0, "failed": 0})
        bucket["case_count"] += 1
        if score.get("gate_status") == "pass":
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1
    return {
        "schema_version": "sec_agent_multi_agent_chain_performance_eval_v0.1",
        "cases_path": str(cases_path),
        "output_dir": str(output_dir),
        "case_count": len(scores),
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / len(scores) if scores else 0.0,
        "gate_status": "pass" if failed == 0 else "fail",
        "categories": categories,
        "failed_cases": [score["case_id"] for score in scores if score.get("gate_status") != "pass"],
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _string_list(value: Any) -> list[str]:
    if value is None:
        items: list[Any] = []
    elif isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate deterministic multi-agent chain performance gates.")
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--fail-on-gate", action="store_true")
    args = parser.parse_args(argv)
    aggregate = run_eval(
        cases_path=args.cases_path,
        output_dir=args.output_dir,
        limit=args.limit,
        fail_on_gate=args.fail_on_gate,
    )
    print(json.dumps(aggregate, ensure_ascii=False, indent=2))
    return 0 if aggregate["gate_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
