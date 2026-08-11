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


DEFAULT_INPUT_STATE = (
    REPO_ROOT
    / "eval"
    / "sec_cases"
    / "outputs"
    / "p33_gold_case_runs"
    / "p33_stepwise_coverage_reflection_enriched_state_after_fusion_fix_20260705_r3"
    / "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"
    / "coverage_reflection_compact_state.json"
)
DEFAULT_SPECIALIST_NODE = (
    REPO_ROOT
    / "eval"
    / "sec_cases"
    / "outputs"
    / "p33_gold_case_runs"
    / "p33_stepwise_optional_specialist_composite_after_targeted_repairs_20260705_r1"
    / "p33_3_ai_semis_accelerator_dell_gold_case_v0_1"
    / "optional_specialist_subgraph_node_result.json"
)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "p33_gold_case_runs"
DEFAULT_CASE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "p33_ai_semis_gold_workpaper_case_v0_1.jsonl"
SUMMARY_SCHEMA_VERSION = "p33_aggregate_judgment_plan_stepwise_summary_v0_1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run only P33 aggregate_judgment_plan from an accepted optional_specialist_subgraph checkpoint. "
            "This is a deterministic node-level runner; it must not call an LLM."
        )
    )
    parser.add_argument("--input-state", type=Path, default=DEFAULT_INPUT_STATE)
    parser.add_argument("--specialist-node-result", type=Path, default=DEFAULT_SPECIALIST_NODE)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    raw_state = _read_json(args.input_state)
    specialist_node = _read_json(args.specialist_node_result)
    run_id = args.run_id or _default_run_id()
    case_id = str(raw_state.get("case_id") or args.input_state.parent.name or "p33_case")
    case_dir = args.output_root / run_id / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    state = _hydrate_state(raw_state, specialist_node, run_id=run_id, case_id=case_id, case_dir=case_dir)
    preflight = _preflight_state(state, specialist_node=specialist_node, args=args)
    result: dict[str, Any] = {}
    if preflight["status"] == "pass":
        graph = build_multi_agent_orchestration_graph_from_env(
            env=dict(os.environ),
            use_checkpointer=False,
            entry_node="aggregate_judgment_plan",
            stop_after_node="aggregate_judgment_plan",
        )
        result = graph.invoke(state, config={"configurable": {"thread_id": f"{run_id}-{case_id}-aggregate"}})
    summary = _summary(
        state=state,
        result=result,
        preflight=preflight,
        elapsed_sec=round(time.time() - started, 4),
        run_id=run_id,
        case_id=case_id,
        case_dir=case_dir,
        args=args,
    )
    _write_summary(case_dir, summary, result=result)
    print(json.dumps(_stdout_summary(summary, case_dir), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def _hydrate_state(
    raw_state: Mapping[str, Any],
    specialist_node: Mapping[str, Any],
    *,
    run_id: str,
    case_id: str,
    case_dir: Path,
) -> dict[str, Any]:
    specialist_outputs = [dict(row) for row in specialist_node.get("specialist_outputs") or [] if isinstance(row, Mapping)]
    specialist_routes = [dict(row) for row in specialist_node.get("specialist_route_results") or [] if isinstance(row, Mapping)]
    case_contract = _case_contract_for_id(case_id)
    state = {
        **dict(raw_state),
        "run_id": run_id,
        "case_id": case_id,
        "output_dir": str(case_dir.resolve()),
        "status": "running",
        "native_stop_after_node": "",
        "specialist_outputs": specialist_outputs,
        "specialist_route_results": specialist_routes,
        "specialist_activation_decisions": specialist_node.get("specialist_activation_decisions") or [],
        "specialist_fanout_barrier": specialist_node.get("specialist_fanout_barrier") or {},
        "specialist_checkpoint_ref": {
            "schema_version": "p33_specialist_checkpoint_ref_v0_1",
            "node_result_path": "",
            "source_run_id": specialist_node.get("composite_repair_provenance", {}).get("base_run_id")
            if isinstance(specialist_node.get("composite_repair_provenance"), Mapping)
            else "",
            "composite_repair_provenance": specialist_node.get("composite_repair_provenance") or {},
        },
    }
    if case_contract:
        state["case_contract"] = case_contract
        case_field_map = {
            "prompt": "prompt",
            "user_query": "prompt",
            "focus_tickers": "focus_tickers",
            "search_scope_tickers": "search_scope_tickers",
            "required_dimensions": "required_dimensions",
            "required_answer_moves": "required_answer_moves",
            "expected_gap_types": "expected_gap_types",
            "eval_focus": "eval_focus",
        }
        for state_key, case_key in case_field_map.items():
            if not state.get(state_key) and case_contract.get(case_key) is not None:
                state[state_key] = case_contract.get(case_key)
    return state


def _case_contract_for_id(case_id: str) -> dict[str, Any]:
    path = DEFAULT_CASE_FIXTURE
    if not path.exists():
        return {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, Mapping) and str(row.get("case_id") or "") == str(case_id):
            return dict(row)
    return {}


def _preflight_state(
    state: Mapping[str, Any],
    *,
    specialist_node: Mapping[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    outputs = [dict(row) for row in state.get("specialist_outputs") or [] if isinstance(row, Mapping)]
    output_agents = {str(row.get("agent_id") or "") for row in outputs}
    expected = {
        "fundamental_analyst",
        "product_technology_analyst",
        "industry_supply_chain_analyst",
        "market_valuation_analyst",
        "risk_counterevidence_analyst",
    }
    if not outputs:
        errors.append({"type": "missing_specialist_outputs"})
    missing = sorted(expected - output_agents)
    if missing:
        errors.append({"type": "missing_expected_specialists", "agent_ids": missing})
    if str(specialist_node.get("status") or "") != "stopped_after_node":
        errors.append({"type": "specialist_checkpoint_not_stopped_after_node", "status": specialist_node.get("status")})
    if str(specialist_node.get("native_stop_after_node") or "") != "optional_specialist_subgraph":
        errors.append(
            {
                "type": "specialist_checkpoint_wrong_node",
                "native_stop_after_node": specialist_node.get("native_stop_after_node"),
            }
        )
    return {
        "schema_version": "p33_aggregate_judgment_plan_preflight_v0_1",
        "status": "fail" if errors else "pass",
        "errors": errors,
        "expected_specialists": sorted(expected),
        "specialist_output_count": len(outputs),
        "specialist_agents": sorted(output_agents),
        "specialist_node_result": str(Path(args.specialist_node_result).resolve()),
    }


def _summary(
    *,
    state: Mapping[str, Any],
    result: Mapping[str, Any],
    preflight: Mapping[str, Any],
    elapsed_sec: float,
    run_id: str,
    case_id: str,
    case_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    judgment = result.get("verified_judgment_plan") if isinstance(result.get("verified_judgment_plan"), Mapping) else result.get("judgment_plan") or {}
    verification = result.get("specialist_verification") if isinstance(result.get("specialist_verification"), Mapping) else {}
    supported = [row for row in judgment.get("supported_claims") or [] if isinstance(row, Mapping)]
    unsupported = [row for row in judgment.get("unsupported_claims") or [] if isinstance(row, Mapping)]
    conflicts = [row for row in judgment.get("conflicts") or [] if isinstance(row, Mapping)]
    memo_logic_plan = result.get("memo_logic_plan") if isinstance(result.get("memo_logic_plan"), Mapping) else {}
    memo_validation = (
        memo_logic_plan.get("validation") if isinstance(memo_logic_plan.get("validation"), Mapping) else {}
    )
    judgment_state = (
        judgment.get("judgment_state") if isinstance(judgment.get("judgment_state"), Mapping) else {}
    )
    checks = {
        "preflight_pass": preflight.get("status") == "pass",
        "stopped_after_aggregate": result.get("status") == "stopped_after_node"
        and result.get("native_stop_after_node") == "aggregate_judgment_plan",
        "judgment_plan_present": bool(judgment),
        "supported_claims_present": bool(supported),
        "specialist_verification_pass": verification.get("status") == "pass",
        "memo_writer_allowed": bool(verification.get("memo_writer_allowed")),
        "memo_logic_plan_present": bool(memo_logic_plan),
        "memo_logic_plan_validation_pass": memo_validation.get("status") == "pass",
        "required_question_items_present": bool(memo_logic_plan.get("required_question_items")),
        "required_item_answer_plan_present": bool(memo_logic_plan.get("required_item_answer_plan")),
    }
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "case_id": case_id,
        "created_at": _utc_now(),
        "gate_status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "elapsed_sec": elapsed_sec,
        "preflight": preflight,
        "node": {
            "status": result.get("status") or "",
            "native_stop_after_node": result.get("native_stop_after_node") or "",
            "node_trace": result.get("node_trace") or [],
        },
        "judgment_stats": {
            "supported_claim_count": len(supported),
            "unsupported_claim_count": len(unsupported),
            "conflict_count": len(conflicts),
            "memo_outline_count": len(judgment.get("memo_outline") or []),
            "judgment_card_count": len(judgment.get("judgment_cards") or []),
            "judgment_state_card_count": len(judgment_state.get("judgment_cards") or []),
            "thesis_path_present": bool(judgment.get("thesis_path")),
            "thesis_driver_pack_present": bool(judgment.get("thesis_driver_pack")),
        },
        "memo_logic_plan_stats": {
            "present": bool(memo_logic_plan),
            "validation_status": str(memo_validation.get("status") or ""),
            "section_count": len(memo_logic_plan.get("sections") or []),
            "section_order": list(memo_logic_plan.get("section_order") or [])[:12],
            "required_question_item_count": len(memo_logic_plan.get("required_question_items") or []),
            "required_item_answer_plan_count": len(memo_logic_plan.get("required_item_answer_plan") or []),
            "writer_thesis_skeleton_present": isinstance(memo_logic_plan.get("writer_thesis_skeleton"), Mapping),
            "product_reasoning_frame_present": isinstance(memo_logic_plan.get("product_reasoning_frame"), Mapping)
            and bool(memo_logic_plan.get("product_reasoning_frame")),
        },
        "artifact_refs": {
            "case_dir": str(case_dir.resolve()),
            "summary": str((case_dir / "aggregate_judgment_plan_summary.json").resolve()),
            "node_result": str((case_dir / "aggregate_judgment_plan_node_result.json").resolve()),
            "input_specialist_node_result": str(Path(args.specialist_node_result).resolve()),
        },
        "boundary": {
            "scope": "node_level_aggregate_judgment_plan_only",
            "not_run": ["memo_writer", "verifier", "renderer", "broad_full_chain", "model_comparison"],
            "acceptance_meaning": "specialist outputs were aggregated into a verified judgment plan; this does not prove final memo quality.",
        },
    }


def _write_summary(case_dir: Path, summary: Mapping[str, Any], *, result: Mapping[str, Any]) -> None:
    (case_dir / "aggregate_judgment_plan_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if result:
        persisted_state_keys = (
            "research_objective_contract",
            "lead_review_checkpoint",
            "targeted_repair_plan",
            "memo_logic_plan",
            "lead_targeted_repair_execution",
            "supervising_analyst_pack",
            "pre_memo_fact_selection",
            "claim_card_store_barrier",
            "adjudicator_barrier",
            "quality_second_pass_report",
            "quality_second_pass_decision",
            "raw_source_provenance_store",
            "asof_vintage_layer",
            "reconciliation_ledger",
            "gate_registry_eval_matrix",
            "derived_metric_layer",
            "fundamental_statement_pack",
            "case_contract",
            "focus_tickers",
            "search_scope_tickers",
            "required_dimensions",
            "required_answer_moves",
            "expected_gap_types",
            "eval_focus",
        )
        compact_result = {
            "status": result.get("status") or "",
            "native_stop_after_node": result.get("native_stop_after_node") or "",
            "node_trace": result.get("node_trace") or [],
            "judgment_plan": result.get("judgment_plan") or {},
            "specialist_verification": result.get("specialist_verification") or {},
            "verified_judgment_plan": result.get("verified_judgment_plan") or {},
            **{
                key: result.get(key)
                for key in persisted_state_keys
                if isinstance(result.get(key), (Mapping, list))
            },
        }
        (case_dir / "aggregate_judgment_plan_node_result.json").write_text(
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
        "judgment_stats": summary.get("judgment_stats"),
        "summary_path": str((case_dir / "aggregate_judgment_plan_summary.json").resolve()),
    }


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _default_run_id() -> str:
    return f"p33_stepwise_aggregate_judgment_plan_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
