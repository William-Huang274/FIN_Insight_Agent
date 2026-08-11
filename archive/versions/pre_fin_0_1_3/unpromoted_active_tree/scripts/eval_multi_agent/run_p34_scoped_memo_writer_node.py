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

from run_p33_memo_writer_payload_preflight_from_aggregate import build_preflight_summary  # noqa: E402
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph_from_env  # noqa: E402
from sec_agent.multi_agent_contracts import verify_multi_agent_memo_draft  # noqa: E402
from sec_agent.p34_lane_quality_runtime import build_ai_semis_scoped_writer_payload  # noqa: E402


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "p34_ai_semis_scoped_writer_runs"
SUMMARY_SCHEMA_VERSION = "p34_scoped_memo_writer_node_summary_v0_1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run only the scoped P34 AI/Semis Memo Writer node from P34 accepted live route rows. "
            "This is not full-chain."
        )
    )
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--memo-router", default="deepseek")
    parser.add_argument("--max-prompt-chars", type=int, default=70000)
    parser.add_argument("--memo-max-repair-attempts", default="0")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    run_id = args.run_id or _default_run_id(args.memo_router)
    state = build_ai_semis_scoped_writer_payload()
    case_id = str(state.get("case_id") or "p34_ai_semis_scoped_writer_case_v0_1")
    case_dir = args.output_root / run_id / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    input_state_path = case_dir / "p34_scoped_memo_writer_input_state.json"
    input_state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    preflight = build_preflight_summary(
        state,
        run_id=run_id,
        case_id=case_id,
        aggregate_node_result=input_state_path,
        case_dir=case_dir,
        elapsed_sec=0.0,
        max_prompt_chars=args.max_prompt_chars,
    )
    result: dict[str, Any] = {}
    if preflight.get("gate_status") == "pass":
        env = dict(os.environ)
        env["SEC_AGENT_MULTI_AGENT_MEMO_ROUTER"] = args.memo_router
        env.setdefault("MEMO_MAX_REPAIR_ATTEMPTS", str(args.memo_max_repair_attempts))
        graph = build_multi_agent_orchestration_graph_from_env(
            env=env,
            use_checkpointer=False,
            entry_node="memo_writer",
            stop_after_node="memo_writer",
        )
        run_state = {
            **state,
            "run_id": run_id,
            "case_id": case_id,
            "output_dir": str(case_dir.resolve()),
            "status": "running",
            "native_stop_after_node": "",
        }
        result = graph.invoke(run_state, config={"configurable": {"thread_id": f"{run_id}-{case_id}-memo-writer"}})

    summary = _summary(
        source_state=state,
        result=result,
        preflight=preflight,
        run_id=run_id,
        case_id=case_id,
        case_dir=case_dir,
        input_state_path=input_state_path,
        elapsed_sec=round(time.time() - started, 4),
    )
    _write_artifacts(case_dir, summary, result=result)
    print(json.dumps(_stdout_summary(summary, case_dir), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def _summary(
    *,
    source_state: Mapping[str, Any],
    result: Mapping[str, Any],
    preflight: Mapping[str, Any],
    run_id: str,
    case_id: str,
    case_dir: Path,
    input_state_path: Path,
    elapsed_sec: float,
) -> dict[str, Any]:
    memo = result.get("memo_answer") if isinstance(result.get("memo_answer"), Mapping) else {}
    route = result.get("memo_route_result") if isinstance(result.get("memo_route_result"), Mapping) else {}
    judgment = source_state.get("verified_judgment_plan") if isinstance(source_state.get("verified_judgment_plan"), Mapping) else {}
    hard_check = verify_multi_agent_memo_draft(memo, judgment) if memo else {
        "status": "not_run",
        "errors": [{"type": "memo_missing"}],
        "warnings": [],
    }
    text = _memo_user_text(memo)
    response_language = memo.get("response_language") if isinstance(memo.get("response_language"), Mapping) else {}
    memo_profile = memo.get("memo_profile") if isinstance(memo.get("memo_profile"), Mapping) else {}
    dimension_analyses = [row for row in memo.get("dimension_analyses") or [] if isinstance(row, Mapping)]
    memo_claims = [row for row in memo.get("memo_claims") or [] if isinstance(row, Mapping)]
    checks = {
        "payload_preflight_pass": preflight.get("gate_status") == "pass",
        "stopped_after_memo_writer": result.get("status") == "stopped_after_node"
        and result.get("native_stop_after_node") == "memo_writer",
        "memo_route_pass": str(route.get("status") or "") == "pass",
        "hard_check_pass": hard_check.get("status") == "pass",
        "response_language_zh_cn": response_language.get("language") == "zh-CN",
        "memo_profile_deep_research": memo_profile.get("profile") == "deep_research",
        "raw_rows_not_consumed": memo.get("raw_rows_consumed") is False,
        "tool_calls_not_requested": not memo.get("tool_calls_requested") and not memo.get("tool_calls"),
        "direct_answer_present": len(str(memo.get("direct_answer") or "").strip()) >= 120,
        "dimension_analyses_present": len(dimension_analyses) >= 3,
        "memo_claims_present": len(memo_claims) >= 6,
        "dell_margin_boundary_preserved": _contains_any(
            text,
            ["AI server gross margin", "GPU pass-through", "毛利", "利润质量", "pass-through"],
        ),
        "market_price_in_boundary_preserved": _contains_any(
            text,
            ["price-in", "positioning", "拥挤", "期权", "borrow cost", "资金流"],
        ),
        "full_chain_not_run": "full_chain" in set(source_state.get("not_run") or []),
    }
    errors = [{"type": key, "status": "failed"} for key, passed in checks.items() if not passed]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "created_at": _utc_now(),
        "elapsed_sec": elapsed_sec,
        "gate_status": "pass" if not errors else "fail",
        "checks": checks,
        "errors": errors,
        "preflight": {
            "gate_status": preflight.get("gate_status"),
            "writer_payload": preflight.get("writer_payload") or {},
            "errors": preflight.get("errors") or [],
        },
        "memo_route": {
            "status": route.get("status"),
            "memo_profile": route.get("memo_profile"),
            "attempt_count": route.get("attempt_count"),
            "repair_attempts": route.get("repair_attempts"),
            "total_tokens": route.get("total_tokens"),
            "finish_reasons": route.get("finish_reasons") or [],
            "failure_reason": route.get("failure_reason") or "",
            "deterministic_salvage_used": bool(route.get("deterministic_salvage_used")),
        },
        "memo_surface": {
            "answer_status": memo.get("answer_status") or "",
            "response_language": response_language,
            "memo_profile": memo_profile,
            "direct_answer_chars": len(str(memo.get("direct_answer") or "")),
            "dimension_analysis_count": len(dimension_analyses),
            "memo_claim_count": len(memo_claims),
            "investment_implication_count": len(memo.get("investment_implications") or []),
            "what_would_change_count": len(memo.get("what_would_change_view") or []),
            "monitoring_item_count": len(memo.get("monitoring_items") or []),
            "evidence_gap_count": len(memo.get("evidence_gaps_but_actionable") or []),
        },
        "hard_check": {
            "status": hard_check.get("status"),
            "error_count": len(hard_check.get("errors") or []),
            "warning_count": len(hard_check.get("warnings") or []),
            "errors": (hard_check.get("errors") or [])[:8],
            "warnings": (hard_check.get("warnings") or [])[:8],
        },
        "artifact_refs": {
            "case_dir": str(case_dir.resolve()),
            "input_state": str(input_state_path.resolve()),
            "summary": str((case_dir / "memo_writer_node_summary.json").resolve()),
            "node_result": str((case_dir / "memo_writer_node_result.json").resolve()),
            "p33_preflight_summary": str((case_dir / "memo_writer_payload_preflight_summary.json").resolve()),
        },
        "boundary": {
            "scope": "p34_scoped_memo_writer_node_only",
            "not_run": ["broad_full_chain", "model_comparison", "case_expansion", "fresh_retrieval"],
            "acceptance_meaning": "Only the scoped Memo Writer node is tested. Renderer/final verifier/Workbench projection must run next.",
        },
    }


def _write_artifacts(case_dir: Path, summary: Mapping[str, Any], *, result: Mapping[str, Any]) -> None:
    (case_dir / "memo_writer_node_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    compact_result = {
        "status": result.get("status") or "",
        "native_stop_after_node": result.get("native_stop_after_node") or "",
        "node_trace": result.get("node_trace") or [],
        "memo_answer": result.get("memo_answer") or {},
        "memo_route_result": result.get("memo_route_result") or {},
        "verified_judgment_plan": result.get("verified_judgment_plan") or result.get("judgment_plan") or {},
        "specialist_verification": result.get("specialist_verification") or {},
        "memo_logic_plan": result.get("memo_logic_plan") or {},
        "p34_scoped_writer_payload": result.get("p34_scoped_writer_payload") or {},
    }
    (case_dir / "memo_writer_node_result.json").write_text(
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
        "memo_route": summary.get("memo_route"),
        "memo_surface": summary.get("memo_surface"),
        "hard_check": summary.get("hard_check"),
        "summary_path": str((case_dir / "memo_writer_node_summary.json").resolve()),
    }


def _memo_user_text(memo: Mapping[str, Any]) -> str:
    parts: list[str] = [str(memo.get("direct_answer") or "")]
    for key in ("dimension_analyses", "memo_claims", "investment_implications", "what_would_change_view", "monitoring_items", "evidence_gaps_but_actionable"):
        for item in memo.get(key) or []:
            if isinstance(item, Mapping):
                parts.extend(str(value) for value in item.values() if isinstance(value, (str, int, float)))
            else:
                parts.append(str(item))
    return "\n".join(parts)


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _default_run_id(router: str) -> str:
    return f"p34_scoped_memo_writer_node_{router}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
