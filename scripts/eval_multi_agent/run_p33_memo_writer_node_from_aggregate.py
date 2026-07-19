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
from sec_agent.humanmade_gold_set_runtime import build_pre_writer_humanmade_gold_set_gate  # noqa: E402
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph_from_env  # noqa: E402
from sec_agent.multi_agent_contracts import verify_multi_agent_memo_draft  # noqa: E402


DEFAULT_AGGREGATE_NODE = (
    REPO_ROOT
    / "eval"
    / "sec_cases"
    / "outputs"
    / "p33_gold_case_runs"
    / "p33_stepwise_aggregate_judgment_plan_after_required_item_gate_hardening_20260705_r7"
    / "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"
    / "aggregate_judgment_plan_node_result.json"
)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "p33_gold_case_runs"
SUMMARY_SCHEMA_VERSION = "p33_memo_writer_node_summary_v0_1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run only the P33 Memo Writer node from an accepted aggregate_judgment_plan checkpoint. "
            "This is node-level execution, not full-chain."
        )
    )
    parser.add_argument("--aggregate-node-result", type=Path, default=DEFAULT_AGGREGATE_NODE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--memo-router", default="deepseek")
    parser.add_argument("--max-prompt-chars", type=int, default=70000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    raw_state = _read_json(args.aggregate_node_result)
    run_id = args.run_id or _default_run_id()
    case_id = _case_id_from_state(raw_state, fallback=args.aggregate_node_result.parent.name)
    case_dir = args.output_root / run_id / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    state = {
        **dict(raw_state),
        "run_id": run_id,
        "case_id": case_id,
        "output_dir": str(case_dir.resolve()),
        "status": "running",
        "native_stop_after_node": "",
    }
    preflight = build_preflight_summary(
        state,
        run_id=run_id,
        case_id=case_id,
        aggregate_node_result=args.aggregate_node_result,
        case_dir=case_dir,
        elapsed_sec=0.0,
        max_prompt_chars=args.max_prompt_chars,
    )
    humanmade_gold_set_gate = build_pre_writer_humanmade_gold_set_gate(state)
    result: dict[str, Any] = {}
    if preflight["gate_status"] == "pass" and humanmade_gold_set_gate.get("status") != "fail":
        env = dict(os.environ)
        env["SEC_AGENT_MULTI_AGENT_MEMO_ROUTER"] = args.memo_router
        graph = build_multi_agent_orchestration_graph_from_env(
            env=env,
            use_checkpointer=False,
            entry_node="memo_writer",
            stop_after_node="memo_writer",
        )
        result = graph.invoke(state, config={"configurable": {"thread_id": f"{run_id}-{case_id}-memo-writer"}})
    summary = _summary(
        state=state,
        result=result,
        preflight=preflight,
        humanmade_gold_set_gate=humanmade_gold_set_gate,
        run_id=run_id,
        case_id=case_id,
        case_dir=case_dir,
        aggregate_node_result=args.aggregate_node_result,
        elapsed_sec=round(time.time() - started, 4),
    )
    _write_summary(case_dir, summary, result=result)
    print(json.dumps(_stdout_summary(summary, case_dir), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def _summary(
    *,
    state: Mapping[str, Any],
    result: Mapping[str, Any],
    preflight: Mapping[str, Any],
    humanmade_gold_set_gate: Mapping[str, Any] | None = None,
    run_id: str,
    case_id: str,
    case_dir: Path,
    aggregate_node_result: Path,
    elapsed_sec: float,
) -> dict[str, Any]:
    memo = result.get("memo_answer") if isinstance(result.get("memo_answer"), Mapping) else {}
    route = result.get("memo_route_result") if isinstance(result.get("memo_route_result"), Mapping) else {}
    humanmade_gold_set_gate = humanmade_gold_set_gate if isinstance(humanmade_gold_set_gate, Mapping) else {"status": "not_applicable"}
    judgment = state.get("verified_judgment_plan") if isinstance(state.get("verified_judgment_plan"), Mapping) else state.get("judgment_plan") or {}
    hard_check = verify_multi_agent_memo_draft(memo, judgment if isinstance(judgment, Mapping) else {}) if memo else {"status": "not_run", "errors": [{"type": "memo_missing"}]}
    response_language = memo.get("response_language") if isinstance(memo.get("response_language"), Mapping) else {}
    memo_profile = memo.get("memo_profile") if isinstance(memo.get("memo_profile"), Mapping) else {}
    dimension_analyses = [row for row in memo.get("dimension_analyses") or [] if isinstance(row, Mapping)]
    memo_claims = [row for row in memo.get("memo_claims") or [] if isinstance(row, Mapping)]
    direct_answer = str(memo.get("direct_answer") or "")
    route_status = str(route.get("status") or "")
    salvage_used = bool(route.get("deterministic_salvage_used"))
    checks = {
        "payload_preflight_pass": preflight.get("gate_status") == "pass",
        "humanmade_gold_set_audit_pass_or_not_applicable": humanmade_gold_set_gate.get("status") in {"pass", "not_applicable"},
        "stopped_after_memo_writer": result.get("status") == "stopped_after_node"
        and result.get("native_stop_after_node") == "memo_writer",
        "memo_route_pass": route_status == "pass",
        "no_deterministic_salvage": not salvage_used,
        "hard_check_pass": hard_check.get("status") == "pass",
        "response_language_zh_cn": response_language.get("language") == "zh-CN",
        "memo_profile_deep_research": memo_profile.get("profile") == "deep_research",
        "raw_rows_not_consumed": memo.get("raw_rows_consumed") is False,
        "tool_calls_not_requested": not memo.get("tool_calls_requested") and not memo.get("tool_calls"),
        "direct_answer_present": len(direct_answer.strip()) >= 120,
        "dimension_analyses_present": len(dimension_analyses) >= 3,
        "memo_claims_present": len(memo_claims) >= 4,
    }
    errors = [{"type": key, "status": "failed"} for key, passed in checks.items() if not passed]
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "created_at": _utc_now(),
        "gate_status": "pass" if not errors else "fail",
        "elapsed_sec": elapsed_sec,
        "checks": checks,
        "errors": errors,
        "preflight": {
            "gate_status": preflight.get("gate_status"),
            "writer_payload": preflight.get("writer_payload") or {},
            "errors": preflight.get("errors") or [],
        },
        "humanmade_gold_set_gate": dict(humanmade_gold_set_gate),
        "memo_route": {
            "status": route_status,
            "memo_profile": route.get("memo_profile"),
            "attempt_count": route.get("attempt_count"),
            "repair_attempts": route.get("repair_attempts"),
            "total_tokens": route.get("total_tokens"),
            "finish_reasons": route.get("finish_reasons") or [],
            "deterministic_salvage_used": salvage_used,
            "failure_reason": route.get("failure_reason") or "",
        },
        "memo_surface": {
            "answer_status": memo.get("answer_status") or "",
            "response_language": response_language,
            "memo_profile": memo_profile,
            "direct_answer_chars": len(direct_answer),
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
            "summary": str((case_dir / "memo_writer_node_summary.json").resolve()),
            "node_result": str((case_dir / "memo_writer_node_result.json").resolve()),
            "aggregate_node_result": str(Path(aggregate_node_result).resolve()),
        },
        "boundary": {
            "scope": "node_level_memo_writer_only",
            "not_run": ["verifier", "renderer", "broad_full_chain", "model_comparison"],
            "acceptance_meaning": "Memo Writer produced a hard-check-passing memo from r7 payload; final verifier/render/workbench quality remains unproven.",
        },
    }


def _write_summary(case_dir: Path, summary: Mapping[str, Any], *, result: Mapping[str, Any]) -> None:
    (case_dir / "memo_writer_node_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if result:
        compact_result = {
            "status": result.get("status") or "",
            "native_stop_after_node": result.get("native_stop_after_node") or "",
            "node_trace": result.get("node_trace") or [],
            "memo_answer": result.get("memo_answer") or {},
            "memo_route_result": result.get("memo_route_result") or {},
            "verified_judgment_plan": result.get("verified_judgment_plan") or result.get("judgment_plan") or {},
            "specialist_verification": result.get("specialist_verification") or {},
            "memo_logic_plan": result.get("memo_logic_plan") or {},
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


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _case_id_from_state(state: Mapping[str, Any], *, fallback: str) -> str:
    case_contract = state.get("case_contract") if isinstance(state.get("case_contract"), Mapping) else {}
    research_contract = (
        state.get("research_objective_contract")
        if isinstance(state.get("research_objective_contract"), Mapping)
        else {}
    )
    return str(
        state.get("case_id")
        or case_contract.get("case_id")
        or research_contract.get("case_id")
        or fallback
        or "p33_case"
    )


def _default_run_id() -> str:
    return f"p33_stepwise_memo_writer_node_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
