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
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_ROOT = REPO_ROOT / "src"
SCRIPT_ROOT = REPO_ROOT / "scripts"
for root in (SRC_ROOT, SCRIPT_DIR, SCRIPT_ROOT):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

import eval_multi_agent_coverage_reflection_gate as s4  # noqa: E402
import eval_multi_agent_evidence_operator_gate as s3  # noqa: E402
from eval_multi_agent_real_llm_chain import _specialist_real_evidence_quality  # noqa: E402
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph_from_env  # noqa: E402
from sec_agent.multi_agent_runtime import SPECIALIST_EXECUTION_ORDER, build_agent_data_view, specialist_activation_decisions  # noqa: E402


DEFAULT_COVERAGE_SUMMARY = (
    REPO_ROOT
    / "eval"
    / "sec_cases"
    / "outputs"
    / "multi_agent_coverage_reflection_diagnostic"
    / "20260601_fin_agent_s4_after_8k_second_pass_routefix_v0_1"
    / "coverage_reflection_diagnostic.json"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "multi_agent_specialist_layer_diagnostic"
SUMMARY_SCHEMA_VERSION = "sec_agent_specialist_layer_diagnostic_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run S5 Specialist layer gate from passed S1-S4 artifacts.")
    parser.add_argument("--activation-summary", type=Path, default=s3.DEFAULT_ACTIVATION_SUMMARY)
    parser.add_argument("--relationship-summary", type=Path, default=s3.DEFAULT_RELATIONSHIP_SUMMARY)
    parser.add_argument("--evidence-summary", type=Path, required=True)
    parser.add_argument("--coverage-summary", type=Path, default=Path(os.environ.get("COVERAGE_REFLECTION_SUMMARY", str(DEFAULT_COVERAGE_SUMMARY))))
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--chat-completions-path", default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("SPECIALIST_TEMPERATURE", "0")))
    parser.add_argument("--max-tokens", type=int, default=int(os.environ.get("SPECIALIST_MAX_TOKENS", "2200")))
    parser.add_argument("--timeout-s", type=int, default=int(os.environ.get("SPECIALIST_TIMEOUT_S", "180")))
    parser.add_argument("--max-repair-attempts", type=int, default=int(os.environ.get("SPECIALIST_MAX_REPAIR_ATTEMPTS", "1")))
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    activation_summary = _read_json(args.activation_summary)
    relationship_summary = _read_json(args.relationship_summary) if args.relationship_summary.exists() else {}
    evidence_summary = _read_json(args.evidence_summary)
    coverage_summary = _read_json(args.coverage_summary)
    relationship_artifact_root = Path(relationship_summary.get("output_dir") or args.relationship_summary.parent)
    evidence_artifact_root = Path(evidence_summary.get("output_dir") or args.evidence_summary.parent)
    coverage_artifact_root = Path(coverage_summary.get("output_dir") or args.coverage_summary.parent)
    cases = _selected_cases(_specialist_cases(activation_summary, coverage_summary), args.case_id)
    run_id = args.run_id or _default_run_id()
    output_dir = args.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    graph = build_multi_agent_orchestration_graph_from_env(
        env=_graph_env(args),
        use_checkpointer=False,
        entry_node="optional_specialist_subgraph",
        stop_after_node="optional_specialist_subgraph",
    )

    started = time.time()
    scores: list[dict[str, Any]] = []
    for ordinal, case in enumerate(cases, start=1):
        case_started = time.time()
        case_id = str(case.get("case_id") or f"case_{ordinal}")
        case_dir = output_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        relationship_artifacts = s3._relationship_artifacts(case_id, relationship_artifact_root)
        state = s3._initial_state(case, relationship_artifacts, case_dir, run_id=run_id, args=s4._s3_args_from_summary(evidence_summary))
        state = s4._inject_s3_artifacts(state, evidence_artifact_root, case_id)
        state = _inject_s4_artifacts(state, coverage_artifact_root, case_id)
        expected_specialists = _expected_specialists(state)
        result = graph.invoke(state, config={"configurable": {"thread_id": f"{run_id}-{case_id}-s5-specialists"}})
        score = _score_case(
            _augment_case_for_quality(case, state, relationship_artifacts),
            result,
            expected_specialists=expected_specialists,
            elapsed_sec=round(time.time() - case_started, 4),
            ordinal=ordinal,
            total=len(cases),
        )
        (case_dir / "specialist_layer_case_score.json").write_text(
            json.dumps(score, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "specialist_layer_result_summary.json").write_text(
            json.dumps(_result_summary(result, score), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        scores.append(score)

    summary = _aggregate(
        run_id=run_id,
        args=args,
        activation_summary=activation_summary,
        relationship_summary=relationship_summary,
        evidence_summary=evidence_summary,
        coverage_summary=coverage_summary,
        scores=scores,
        elapsed_sec=round(time.time() - started, 4),
        output_dir=output_dir,
    )
    summary_path = output_dir / "specialist_layer_diagnostic.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_stdout_summary(summary, summary_path), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def _specialist_cases(activation_summary: Mapping[str, Any], coverage_summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    coverage_pass = {
        str(case.get("case_id") or "")
        for case in coverage_summary.get("cases") or []
        if isinstance(case, Mapping) and str(case.get("status") or "") == "pass"
    }
    specialists = set(SPECIALIST_EXECUTION_ORDER)
    cases: list[dict[str, Any]] = []
    for case in activation_summary.get("cases") or []:
        if not isinstance(case, Mapping) or str(case.get("status") or "") != "pass":
            continue
        case_id = str(case.get("case_id") or "")
        if case_id not in coverage_pass:
            continue
        activation = case.get("activation_plan") if isinstance(case.get("activation_plan"), Mapping) else {}
        if set(_string_list(activation.get("activate_agents"))) & specialists:
            cases.append(dict(case))
    return cases


def _selected_cases(cases: list[dict[str, Any]], selected_ids: list[str]) -> list[dict[str, Any]]:
    if not selected_ids:
        return cases
    selected = {str(item) for item in selected_ids}
    return [case for case in cases if str(case.get("case_id") or "") in selected]


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
        }
    )
    return env


def _inject_s4_artifacts(state: dict[str, Any], coverage_artifact_root: Path, case_id: str) -> dict[str, Any]:
    result = _read_json(coverage_artifact_root / case_id / "coverage_reflection_result_summary.json")
    return {
        **state,
        "status": "running",
        "native_stop_after_node": "",
        "multi_agent_reflection_report": dict(result.get("multi_agent_reflection_report") or {}),
        "multi_agent_second_pass_decision": dict(result.get("multi_agent_second_pass_decision") or {}),
        "second_pass_result": dict(result.get("second_pass_result") or {}),
        "tool_call_ledger": dict(result.get("tool_call_ledger") or state.get("tool_call_ledger") or {}),
    }


def _expected_specialists(state: Mapping[str, Any]) -> set[str]:
    return {
        str(row.get("agent_id") or "")
        for row in specialist_activation_decisions(state)
        if row.get("decision") == "run"
    }


def _augment_case_for_quality(
    case: Mapping[str, Any],
    state: Mapping[str, Any],
    relationship_artifacts: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_plan = state.get("evidence_requirement_plan") if isinstance(state.get("evidence_requirement_plan"), Mapping) else {}
    scope = evidence_plan.get("scope") if isinstance(evidence_plan.get("scope"), Mapping) else {}
    tool_names = sorted({str(row.get("tool_name") or "") for row in state.get("tool_observations") or [] if isinstance(row, Mapping) and row.get("tool_name")})
    relationship_plan = relationship_artifacts.get("plan") if isinstance(relationship_artifacts.get("plan"), Mapping) else {}
    relationship_rows = (relationship_artifacts.get("lookup") or {}).get("relationships") if isinstance(relationship_artifacts.get("lookup"), Mapping) else []
    source_tiers = _string_list(scope.get("source_tiers"))
    active = set(_string_list((state.get("agent_activation_plan") or {}).get("activate_agents") if isinstance(state.get("agent_activation_plan"), Mapping) else []))
    return {
        **dict(case),
        "focus_tickers": _string_list((state.get("query_contract") or {}).get("focus_tickers") if isinstance(state.get("query_contract"), Mapping) else [])
        or _string_list((state.get("agent_activation_plan") or {}).get("focus_tickers") if isinstance(state.get("agent_activation_plan"), Mapping) else []),
        "source_tiers": source_tiers,
        "expected_tool_names": tool_names,
        "category": "sector_depth" if "relationship_graph" in source_tiers else str(case.get("category") or ""),
        "expected_relationship_pack_ids": _relationship_pack_ids_from_plan(relationship_plan),
        "require_industry_relationship_evidence": bool("industry_supply_chain_analyst" in active and relationship_rows),
    }


def _relationship_pack_ids_from_plan(plan: Mapping[str, Any]) -> list[str]:
    refs = [
        str(ref)
        for relationship in plan.get("relationships") or []
        if isinstance(relationship, Mapping)
        for ref in relationship.get("evidence_refs") or []
        if str(ref or "").strip()
    ]
    pack_ids = []
    seen: set[str] = set()
    for ref in refs:
        parts = ref.split(":")
        if len(parts) < 3 or parts[0] != "sector_depth_pack" or not parts[1] or parts[1] in seen:
            continue
        seen.add(parts[1])
        pack_ids.append(parts[1])
    return pack_ids


def _score_case(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    expected_specialists: set[str],
    elapsed_sec: float,
    ordinal: int,
    total: int,
) -> dict[str, Any]:
    route_results = [dict(row) for row in result.get("specialist_route_results") or [] if isinstance(row, Mapping)]
    route_by_agent = {str(row.get("agent_id") or ""): row for row in route_results}
    route_pass_agents = {agent_id for agent_id, row in route_by_agent.items() if str(row.get("status") or "") == "pass"}
    quality = _specialist_real_evidence_quality(case, result, expected_specialists, required=bool(expected_specialists))
    details = quality.get("details") if isinstance(quality.get("details"), Mapping) else {}
    checks = {
        "graph_stopped_after_specialists": result.get("status") == "stopped_after_node"
        and result.get("native_stop_after_node") == "optional_specialist_subgraph",
        "expected_specialists_present": bool(expected_specialists),
        "expected_routes_present": expected_specialists <= set(route_by_agent),
        "expected_routes_pass": expected_specialists <= route_pass_agents,
        "specialist_outputs_present": expected_specialists <= {
            str(row.get("agent_id") or "") for row in result.get("specialist_outputs") or [] if isinstance(row, Mapping)
        },
        "route_success": bool(quality.get("route_success")),
        "real_evidence_quality_pass": bool(quality.get("quality_pass")),
    }
    return {
        "case_id": case.get("case_id"),
        "ordinal": ordinal,
        "total": total,
        "prompt": case.get("prompt") or "",
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "elapsed_sec": elapsed_sec,
        "expected_specialists": sorted(expected_specialists),
        "route_status_by_agent": {agent_id: str(row.get("status") or "") for agent_id, row in sorted(route_by_agent.items())},
        "specialist_real_evidence_quality": quality,
        "specialist_detail_status": {agent_id: str((details.get(agent_id) or {}).get("status") or "") for agent_id in sorted(details)},
        "token_usage": _token_usage(route_results),
        "repair_attempts_by_agent": {
            agent_id: int((row.get("repair_attempts") or 0))
            for agent_id, row in sorted(route_by_agent.items())
            if agent_id in expected_specialists
        },
        "data_view_summary": _data_view_summary(result, expected_specialists),
    }


def _result_summary(result: Mapping[str, Any], score: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status") or "",
        "native_stop_after_node": result.get("native_stop_after_node") or "",
        "node_trace": result.get("node_trace") or [],
        "specialist_activation_decisions": result.get("specialist_activation_decisions") or [],
        "specialist_route_results": result.get("specialist_route_results") or [],
        "specialist_outputs": result.get("specialist_outputs") or [],
        "specialist_real_evidence_quality": score.get("specialist_real_evidence_quality") or {},
        "data_view_summary": score.get("data_view_summary") or {},
    }


def _data_view_summary(result: Mapping[str, Any], expected_specialists: set[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for agent_id in sorted(expected_specialists):
        view = build_agent_data_view(agent_id, result)
        rows = [row for row in view.get("bounded_evidence_rows") or [] if isinstance(row, Mapping)]
        summary[agent_id] = {
            "status": view.get("status") or "",
            "row_count": len(rows),
            "source_families": sorted({str(row.get("source_family") or "") for row in rows if row.get("source_family")}),
            "row_distribution": view.get("bounded_row_distribution") if isinstance(view.get("bounded_row_distribution"), Mapping) else _row_distribution(rows),
            "relationship_summary_count": len((view.get("relationship_summary") or {}).get("relationships") or [])
            if isinstance(view.get("relationship_summary"), Mapping)
            else 0,
            "required_claim_slot_count": len(view.get("required_claim_slots") or []),
            "counterclaim_slot_count": len(view.get("counterclaim_slots") or []),
        }
    return summary


def _token_usage(route_results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "input_tokens": sum(int(row.get("input_tokens") or 0) for row in route_results),
        "output_tokens": sum(int(row.get("output_tokens") or 0) for row in route_results),
        "total_tokens": sum(int(row.get("total_tokens") or 0) for row in route_results),
    }


def _row_distribution(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "sec_agent_prompt_data_view_row_distribution_v0.1",
        "row_count": len(rows),
        "by_ticker": _count_by_key(rows, "ticker"),
        "by_source_family": _count_by_key(rows, "source_family"),
        "by_ticker_source_family": _count_by_composite(rows, ("ticker", "source_family")),
        "by_form_type": _count_by_key(rows, "form_type"),
        "by_metric": _count_by_key(rows, "metric"),
    }


def _count_by_key(rows: list[Mapping[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "").strip() or "unknown"
        if key == "ticker":
            value = value.upper()
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _count_by_composite(rows: list[Mapping[str, Any]], keys: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        parts = []
        for key in keys:
            value = str(row.get(key) or "").strip() or "unknown"
            if key == "ticker":
                value = value.upper()
            parts.append(value)
        label = "|".join(parts)
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def _aggregate(
    *,
    run_id: str,
    args: argparse.Namespace,
    activation_summary: Mapping[str, Any],
    relationship_summary: Mapping[str, Any],
    evidence_summary: Mapping[str, Any],
    coverage_summary: Mapping[str, Any],
    scores: list[dict[str, Any]],
    elapsed_sec: float,
    output_dir: Path,
) -> dict[str, Any]:
    pass_count = sum(1 for score in scores if score.get("status") == "pass")
    route_pass_count = sum(1 for score in scores if (score.get("checks") or {}).get("route_success"))
    quality_pass_count = sum(1 for score in scores if (score.get("checks") or {}).get("real_evidence_quality_pass"))
    token_usage = {
        "input_tokens": sum(int((score.get("token_usage") or {}).get("input_tokens") or 0) for score in scores),
        "output_tokens": sum(int((score.get("token_usage") or {}).get("output_tokens") or 0) for score in scores),
        "total_tokens": sum(int((score.get("token_usage") or {}).get("total_tokens") or 0) for score in scores),
    }
    specialist_count = sum(len(score.get("expected_specialists") or []) for score in scores)
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": elapsed_sec,
        "gate_status": "pass" if scores and pass_count == len(scores) else "fail",
        "diagnostic_only": True,
        "activation_summary": str(args.activation_summary.resolve()),
        "activation_run_id": activation_summary.get("run_id") or "",
        "relationship_summary": str(args.relationship_summary.resolve()),
        "relationship_run_id": relationship_summary.get("run_id") or "",
        "evidence_summary": str(args.evidence_summary.resolve()),
        "evidence_run_id": evidence_summary.get("run_id") or "",
        "coverage_summary": str(args.coverage_summary.resolve()),
        "coverage_run_id": coverage_summary.get("run_id") or "",
        "output_dir": str(output_dir.resolve()),
        "model_config": {
            "llm_backend": args.llm_backend,
            "base_url": args.base_url,
            "chat_completions_path": args.chat_completions_path,
            "model": args.model,
            "api_key_env": args.api_key_env,
            "api_key_saved": False,
            "temperature": args.temperature,
            "max_tokens": args.max_tokens,
            "timeout_s": args.timeout_s,
            "max_repair_attempts": args.max_repair_attempts,
        },
        "metrics": {
            "case_count": len(scores),
            "pass_count": pass_count,
            "failed_count": len(scores) - pass_count,
            "specialist_count": specialist_count,
            "route_pass_case_count": route_pass_count,
            "real_evidence_quality_pass_case_count": quality_pass_count,
            "token_usage": token_usage,
            "repair_attempts_total": sum(
                sum(int(value or 0) for value in (score.get("repair_attempts_by_agent") or {}).values())
                for score in scores
            ),
        },
        "cases": scores,
        "failed_cases": [
            {"case_id": score.get("case_id"), "checks": score.get("checks"), "specialist_detail_status": score.get("specialist_detail_status")}
            for score in scores
            if score.get("status") != "pass"
        ],
    }


def _stdout_summary(summary: Mapping[str, Any], path: Path) -> dict[str, Any]:
    return {
        "run_id": summary.get("run_id"),
        "gate_status": summary.get("gate_status"),
        "output_path": str(path.resolve()),
        "metrics": summary.get("metrics") or {},
        "failed_cases": summary.get("failed_cases") or [],
    }


def _default_run_id() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%d')}_fin_agent_s5_specialist_layer_gate_v0_1"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item or "").strip()]
    return [str(value)] if str(value or "").strip() else []


if __name__ == "__main__":
    raise SystemExit(main())
