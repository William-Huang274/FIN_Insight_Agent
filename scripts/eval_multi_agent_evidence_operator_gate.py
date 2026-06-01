from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.agent_registry import agent_registry_by_id  # noqa: E402
from sec_agent.langgraph_orchestrator import build_multi_agent_orchestration_graph, make_multi_agent_smoke_state  # noqa: E402
from sec_agent.multi_agent_runtime import ROUTE_OPERATOR_TOOL  # noqa: E402
from sec_agent.tool_call_ledger import LoopBudget, ToolCallLedger  # noqa: E402


DEFAULT_ACTIVATION_SUMMARY = (
    REPO_ROOT
    / "eval"
    / "sec_cases"
    / "outputs"
    / "multi_agent_activation_diagnostic"
    / "20260601_fin_agent_s1_research_lead_quality_gate_deepseek_v0_1"
    / "activation_diagnostic.json"
)
DEFAULT_RELATIONSHIP_SUMMARY = (
    REPO_ROOT
    / "eval"
    / "sec_cases"
    / "outputs"
    / "multi_agent_universe_relationship_diagnostic"
    / "20260601_fin_agent_s2_economic_link_map_quality_gate_deepseek_v0_2"
    / "universe_relationship_diagnostic.json"
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "multi_agent_evidence_operator_diagnostic"
DEFAULT_SECTOR_DEPTH_MANIFEST = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "manifests"
    / "sector_depth_full238_us_v0_2_mixed_with_8k_manifest_fy2023_2027.jsonl"
)
DEFAULT_SECTOR_DEPTH_BM25 = REPO_ROOT / "data" / "indexes" / "bm25" / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027"
DEFAULT_SECTOR_DEPTH_OBJECT_BM25 = REPO_ROOT / "data" / "indexes" / "bm25" / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects"
DEFAULT_LEDGER_STORE = REPO_ROOT / "data" / "processed_private" / "ledger" / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_core_ledger.duckdb"
DEFAULT_MARKET_EVIDENCE = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "market"
    / "evidence_packs"
    / "20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1_3m_market_evidence.jsonl"
)
DEFAULT_INDUSTRY_EVIDENCE = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "industry_data"
    / "20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales"
    / "industry_evidence_rows.jsonl"
)
DEFAULT_SECTOR_DEPTH_PACK = REPO_ROOT / "configs" / "sector_depth_packs_v0_2.yaml"
DEFAULT_BGE_MODEL = Path("D:/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/snapshots/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e")
DEFAULT_MARKET_SNAPSHOT_ID = "20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1"
DEFAULT_MARKET_AS_OF_DATE = "2026-05-29"
SUMMARY_SCHEMA_VERSION = "sec_agent_evidence_operator_diagnostic_v0.1"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run S3 Evidence Operator / RAG gate from passed S1/S2 artifacts.")
    parser.add_argument("--activation-summary", type=Path, default=DEFAULT_ACTIVATION_SUMMARY)
    parser.add_argument("--relationship-summary", type=Path, default=DEFAULT_RELATIONSHIP_SUMMARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--manifest-path", type=Path, default=Path(os.environ.get("MANIFEST_PATH", str(DEFAULT_SECTOR_DEPTH_MANIFEST))))
    parser.add_argument("--bm25-index-dir", type=Path, default=Path(os.environ.get("BM25_INDEX_DIR", str(DEFAULT_SECTOR_DEPTH_BM25))))
    parser.add_argument("--object-bm25-index-dir", type=Path, default=Path(os.environ.get("OBJECT_BM25_INDEX_DIR", str(DEFAULT_SECTOR_DEPTH_OBJECT_BM25))))
    parser.add_argument("--ledger-store-path", type=Path, default=Path(os.environ.get("LEDGER_STORE_PATH", str(DEFAULT_LEDGER_STORE))))
    parser.add_argument("--market-evidence-path", type=Path, default=Path(os.environ.get("MARKET_EVIDENCE_PATH", str(DEFAULT_MARKET_EVIDENCE))))
    parser.add_argument("--industry-evidence-path", type=Path, default=Path(os.environ.get("INDUSTRY_EVIDENCE_PATH", str(DEFAULT_INDUSTRY_EVIDENCE))))
    parser.add_argument("--sector-depth-pack-path", type=Path, default=Path(os.environ.get("SECTOR_DEPTH_PACK_PATH", str(DEFAULT_SECTOR_DEPTH_PACK))))
    parser.add_argument("--market-snapshot-id", default=os.environ.get("MARKET_SNAPSHOT_ID", DEFAULT_MARKET_SNAPSHOT_ID))
    parser.add_argument("--market-as-of-date", default=os.environ.get("MARKET_AS_OF_DATE", DEFAULT_MARKET_AS_OF_DATE))
    parser.add_argument("--bge-model", type=Path, default=Path(os.environ.get("BGE_MODEL", str(DEFAULT_BGE_MODEL))))
    parser.add_argument("--bge-device", default=os.environ.get("BGE_DEVICE", "auto"))
    parser.add_argument("--context-runner", default=os.environ.get("SEC_AGENT_CONTEXT_RUNNER", os.environ.get("CONTEXT_RUNNER", "in_process")))
    parser.add_argument("--evidence-top-k", type=int, default=int(os.environ.get("EVIDENCE_TOP_K", "0")))
    parser.add_argument("--object-top-k", type=int, default=int(os.environ.get("OBJECT_TOP_K", "0")))
    parser.add_argument("--reranker-candidate-limit", type=int, default=int(os.environ.get("RERANKER_CANDIDATE_LIMIT", "0")))
    parser.add_argument("--reranker-top-k", type=int, default=int(os.environ.get("RERANKER_TOP_K", "0")))
    parser.add_argument("--reranker-batch-size", type=int, default=int(os.environ.get("RERANKER_BATCH_SIZE", "8")))
    parser.add_argument("--reranker-max-length", type=int, default=int(os.environ.get("RERANKER_MAX_LENGTH", "512")))
    parser.add_argument("--reranker-doc-max-chars", type=int, default=int(os.environ.get("RERANKER_DOC_MAX_CHARS", "0")))
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    activation_summary = _read_json(args.activation_summary)
    relationship_summary = _read_json(args.relationship_summary) if args.relationship_summary.exists() else {}
    relationship_artifact_root = Path(relationship_summary.get("output_dir") or args.relationship_summary.parent)
    cases = _selected_cases(_operator_cases(activation_summary), args.case_id)
    run_id = args.run_id or _default_run_id()
    output_dir = args.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    graph = build_multi_agent_orchestration_graph(
        use_checkpointer=False,
        entry_node="route_by_execution_mode",
        stop_after_node="execute_evidence_operators",
    )
    started = time.time()
    scores: list[dict[str, Any]] = []

    for ordinal, case in enumerate(cases, start=1):
        case_started = time.time()
        case_id = str(case.get("case_id") or f"case_{ordinal}")
        case_dir = output_dir / case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        relationship_artifacts = _relationship_artifacts(case_id, relationship_artifact_root)
        state = _initial_state(case, relationship_artifacts, case_dir, run_id=run_id, args=args)
        result = graph.invoke(state, config={"configurable": {"thread_id": f"{run_id}-{case_id}"}})
        score = _score_case(
            case,
            result,
            relationship_artifacts=relationship_artifacts,
            elapsed_sec=round(time.time() - case_started, 4),
            ordinal=ordinal,
            total=len(cases),
            args=args,
        )
        (case_dir / "evidence_operator_case_score.json").write_text(
            json.dumps(score, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "evidence_operator_result_summary.json").write_text(
            json.dumps(_result_summary(result), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        scores.append(score)

    summary = _aggregate(
        run_id=run_id,
        args=args,
        activation_summary=activation_summary,
        relationship_summary=relationship_summary,
        cases=cases,
        scores=scores,
        elapsed_sec=round(time.time() - started, 4),
        output_dir=output_dir,
    )
    summary_path = output_dir / "evidence_operator_diagnostic.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_stdout_summary(summary, summary_path), ensure_ascii=False, indent=2))
    if args.strict and summary["gate_status"] != "pass":
        return 1
    return 0


def _operator_cases(activation_summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    cases = []
    operator_agents = {"sec_operator", "eight_k_operator", "market_operator", "industry_operator"}
    for case in activation_summary.get("cases") or []:
        if not isinstance(case, Mapping) or str(case.get("status") or "") != "pass":
            continue
        activation = case.get("activation_plan") if isinstance(case.get("activation_plan"), Mapping) else {}
        active = set(_string_list(activation.get("activate_agents")))
        if active & operator_agents:
            cases.append(dict(case))
    return cases


def _selected_cases(cases: list[dict[str, Any]], selected_ids: list[str]) -> list[dict[str, Any]]:
    if not selected_ids:
        return cases
    selected = {str(item) for item in selected_ids}
    return [case for case in cases if str(case.get("case_id") or "") in selected]


def _relationship_artifacts(case_id: str, relationship_root: Path) -> dict[str, Any]:
    case_dir = relationship_root / case_id
    result_path = case_dir / "universe_relationship_result.json"
    lookup_path = case_dir / "relationship_lookup.json"
    route = _read_json(result_path) if result_path.exists() else {}
    lookup = _read_json(lookup_path) if lookup_path.exists() else {}
    return {
        "route": route,
        "lookup": lookup,
        "plan": route.get("universe_relationship_plan") if isinstance(route.get("universe_relationship_plan"), Mapping) else {},
        "validation": route.get("universe_relationship_validation") if isinstance(route.get("universe_relationship_validation"), Mapping) else {},
    }


def _initial_state(
    case: Mapping[str, Any],
    relationship_artifacts: Mapping[str, Any],
    case_dir: Path,
    *,
    run_id: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    activation = case.get("activation_plan") if isinstance(case.get("activation_plan"), Mapping) else {}
    evidence_plan = case.get("evidence_requirement_plan") if isinstance(case.get("evidence_requirement_plan"), Mapping) else {}
    relationship_plan = relationship_artifacts.get("plan") if isinstance(relationship_artifacts.get("plan"), Mapping) else {}
    focus_tickers = _unique_upper(activation.get("focus_tickers") or _scope(evidence_plan).get("focus_tickers"))
    search_scope_tickers = _unique_upper(
        [
            *_string_list(activation.get("search_scope_tickers") or _scope(evidence_plan).get("search_scope_tickers")),
            *_string_list(relationship_plan.get("included_tickers")),
        ]
    )
    query_contract = _query_contract_from_artifacts(
        case,
        activation=activation,
        evidence_plan=evidence_plan,
        focus_tickers=focus_tickers,
        search_scope_tickers=search_scope_tickers,
    )
    state = make_multi_agent_smoke_state(
        user_query=str(case.get("prompt") or ""),
        output_dir=case_dir,
        query_contract=query_contract,
        focus_tickers=focus_tickers,
        search_scope_tickers=search_scope_tickers,
    )
    state["run_id"] = f"{run_id}_{case.get('case_id')}"
    state["agent_activation_plan"] = dict(activation)
    state["agent_activation_validation"] = dict(case.get("validation") or {})
    state["evidence_requirement_plan"] = dict(evidence_plan)
    if relationship_artifacts.get("lookup"):
        state["relationship_graph_observation"] = dict(relationship_artifacts.get("lookup") or {})
    if relationship_plan:
        state["universe_relationship_plan"] = dict(relationship_plan)
    if relationship_artifacts.get("validation"):
        state["universe_relationship_validation"] = dict(relationship_artifacts.get("validation") or {})
    budget = LoopBudget(
        max_tool_calls_total=int(activation.get("max_tool_calls_total") or 12),
        max_second_pass_rounds=int(activation.get("max_second_pass_rounds") or 2),
        max_repair_rounds=int(activation.get("max_repair_rounds") or 2),
    )
    state["loop_budget_state"] = budget.to_dict()
    state["tool_call_ledger"] = ToolCallLedger(budget=budget).to_dict()
    state["project_inventory"] = {
        "source_families": _string_list(activation.get("allowed_source_families")),
        "companies": [{"ticker": ticker} for ticker in search_scope_tickers],
        "evaluation_inventory": "summary_only_no_private_paths",
    }
    state["multi_agent_context"] = {
        "evidence_operator_mode": "real",
        "build_runtime_ledger": True,
        "manifest_path": str(args.manifest_path),
        "bm25_index_dir": str(args.bm25_index_dir),
        "object_bm25_index_dir": str(args.object_bm25_index_dir),
        "ledger_store_path": str(args.ledger_store_path),
        "market_evidence_path": str(args.market_evidence_path),
        "industry_evidence_path": str(args.industry_evidence_path),
        "sector_depth_pack_path": str(args.sector_depth_pack_path),
        "market_snapshot": {"snapshot_id": args.market_snapshot_id, "as_of_date": args.market_as_of_date},
        "market_snapshot_id": args.market_snapshot_id,
        "market_as_of_date": args.market_as_of_date,
        "industry_source_families": ["industry_snapshot"],
        "expected_relationship_pack_ids": _expected_pack_ids(relationship_plan),
        "bge_model": str(args.bge_model),
        "bge_device": args.bge_device,
        "context_runner": args.context_runner,
        "evidence_top_k": args.evidence_top_k,
        "object_top_k": args.object_top_k,
        "reranker_candidate_limit": args.reranker_candidate_limit,
        "reranker_top_k": args.reranker_top_k,
        "reranker_batch_size": args.reranker_batch_size,
        "reranker_max_length": args.reranker_max_length,
        "reranker_doc_max_chars": args.reranker_doc_max_chars,
        "focus_tickers": focus_tickers,
        "search_scope_tickers": search_scope_tickers,
    }
    return state


def _query_contract_from_artifacts(
    case: Mapping[str, Any],
    *,
    activation: Mapping[str, Any],
    evidence_plan: Mapping[str, Any],
    focus_tickers: list[str],
    search_scope_tickers: list[str],
) -> dict[str, Any]:
    requirements = [req for req in evidence_plan.get("requirements") or [] if isinstance(req, Mapping)]
    scope = _scope(evidence_plan)
    years = _unique_ints([*_list_from_requirements(requirements, "years"), *_list(scope.get("years"))])
    filing_types = _unique_strings([*_list_from_requirements(requirements, "filing_types"), *_list(scope.get("filing_types"))])
    metric_families = _unique_strings([*_list_from_requirements(requirements, "metric_families"), *_list(case.get("metric_families"))])
    source_tiers = _unique_strings(scope.get("source_tiers") or activation.get("allowed_source_families"))
    return {
        "task_type": "open_analysis",
        "search_scope_tickers": search_scope_tickers or focus_tickers,
        "focus_tickers": focus_tickers or search_scope_tickers,
        "years": years or [2026],
        "filing_types": filing_types,
        "source_tiers": source_tiers,
        "metric_families": metric_families,
        "evidence_requirements": requirements,
        "scope": {
            "focus_tickers": focus_tickers,
            "universe_tickers": search_scope_tickers or focus_tickers,
            "years": years or [2026],
            "filing_types": filing_types,
            "source_tiers": source_tiers,
        },
    }


def _score_case(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    relationship_artifacts: Mapping[str, Any],
    elapsed_sec: float,
    ordinal: int,
    total: int,
    args: argparse.Namespace,
) -> dict[str, Any]:
    retrieval_plan = result.get("retrieval_plan") if isinstance(result.get("retrieval_plan"), Mapping) else {}
    routes = [route for route in retrieval_plan.get("routes") or [] if isinstance(route, Mapping)]
    route_tools = [_route_tool(route) for route in routes]
    tool_calls = _tool_calls(result)
    called_agents = {str(call.get("agent_id") or "") for call in tool_calls if str(call.get("status") or "") != "blocked"}
    called_tools = {str(call.get("tool_name") or "") for call in tool_calls if str(call.get("status") or "") != "blocked"}
    expected_agents = {agent for agent, _tool in route_tools if agent}
    expected_tools = {tool for _agent, tool in route_tools if tool}
    sec_calls = [call for call in tool_calls if call.get("tool_name") == "sec_search_filings"]
    ledger_calls = [call for call in tool_calls if call.get("tool_name") == "sec_query_exact_value_ledger"]
    market_expected = "market_get_snapshot" in expected_tools
    industry_expected = "industry_get_snapshot" in expected_tools
    sec_expected = "sec_search_filings" in expected_tools
    ledger_expected = "sec_query_exact_value_ledger" in expected_tools
    universe_expected = "universe_relationship" in _string_list((case.get("activation_plan") or {}).get("activate_agents") if isinstance(case.get("activation_plan"), Mapping) else [])
    candidate_counts = [_candidate_counts(call) for call in sec_calls]
    cuda_available = _cuda_available()
    bge_policy = _bge_policy(sec_calls)
    checks = {
        "graph_stopped_after_evidence_operators": result.get("status") == "stopped_after_node"
        and result.get("native_stop_after_node") == "execute_evidence_operators",
        "retrieval_plan_compiled": bool(routes),
        "real_retrieval_mode_required": True,
        "expected_operator_agents_called": expected_agents <= called_agents,
        "expected_tool_names_called": expected_tools <= called_tools,
        "tool_ownership_valid": _tool_ownership_valid(tool_calls),
        "tool_budget_lte": len([call for call in tool_calls if str(call.get("status") or "") != "blocked"]) <= int((case.get("activation_plan") or {}).get("max_tool_calls_total") or 12)
        if isinstance(case.get("activation_plan"), Mapping)
        else True,
        "no_budget_loop_break": str(result.get("loop_break_reason") or "") not in {"tool_budget_exhausted", "agent_tool_budget_exhausted"},
        "no_duplicate_loop_break": str(result.get("loop_break_reason") or "") != "duplicate_tool_call_blocked",
        "sec_search_not_dry_run": (not sec_expected) or all(str(call.get("status") or "") != "dry_run" for call in sec_calls),
        "sec_search_errors_absent": (not sec_expected) or all(str(call.get("status") or "") != "error" for call in sec_calls),
        "sec_search_context_rows_present": (not sec_expected) or bool(result.get("context_rows")),
        "sec_search_bm25_candidates_present": (not sec_expected) or any(_positive_count(item.get("candidate_row_count_pre_rerank")) for item in candidate_counts),
        "sec_search_bge_rerank_present": (not sec_expected) or any(_positive_count(item.get("candidate_sent_to_bge")) for item in candidate_counts),
        "bge_cuda_when_auto_and_available": (not sec_expected)
        or str(args.bge_device).lower() not in {"auto", "default"}
        or not cuda_available
        or bge_policy.get("bge_device") == "cuda",
        "exact_value_ledger_rows_present": (not ledger_expected) or bool(result.get("runtime_ledger_rows")) or any(int(call.get("row_count") or 0) > 0 for call in ledger_calls),
        "market_rows_present": (not market_expected) or bool(result.get("market_snapshot_rows")),
        "industry_rows_present": (not industry_expected) or bool(result.get("industry_snapshot_rows")),
        "relationship_rows_available": (not universe_expected)
        or bool((relationship_artifacts.get("lookup") or {}).get("relationships"))
        and bool((relationship_artifacts.get("plan") or {}).get("relationships")),
        "row_payload_usable": _row_payload_usable(result),
    }
    status = "pass" if all(checks.values()) else "fail"
    return {
        "case_id": case.get("case_id"),
        "ordinal": ordinal,
        "total": total,
        "prompt": case.get("prompt"),
        "status": status,
        "checks": checks,
        "elapsed_sec": elapsed_sec,
        "execution_mode": (case.get("activation_plan") or {}).get("execution_mode") if isinstance(case.get("activation_plan"), Mapping) else "",
        "route_count": len(routes),
        "tool_call_count": len(tool_calls),
        "expected_operator_agents": sorted(expected_agents),
        "called_operator_agents": sorted(called_agents),
        "expected_tool_names": sorted(expected_tools),
        "called_tool_names": sorted(called_tools),
        "row_counts": {
            "context_rows": len(result.get("context_rows") or []),
            "runtime_ledger_rows": len(result.get("runtime_ledger_rows") or []),
            "market_snapshot_rows": len(result.get("market_snapshot_rows") or []),
            "industry_snapshot_rows": len(result.get("industry_snapshot_rows") or []),
            "relationship_lookup_rows": len((relationship_artifacts.get("lookup") or {}).get("relationships") or []),
            "relationship_plan_rows": len((relationship_artifacts.get("plan") or {}).get("relationships") or []),
        },
        "retrieval_runtime": {
            "cuda_available": cuda_available,
            "bge_device_requested": args.bge_device,
            "bge_policy": bge_policy,
            "sec_candidate_count_pre_rerank": sum(_int_value(item.get("candidate_row_count_pre_rerank")) for item in candidate_counts),
            "sec_candidate_sent_to_bge": sum(_int_value(item.get("candidate_sent_to_bge")) for item in candidate_counts),
        },
        "tool_calls": [_tool_call_summary(call) for call in tool_calls],
        "source_gaps": [_sanitize_gap(gap) for gap in result.get("source_gaps") or [] if isinstance(gap, Mapping)][:12],
        "elapsed_ms": int(elapsed_sec * 1000),
    }


def _aggregate(
    *,
    run_id: str,
    args: argparse.Namespace,
    activation_summary: Mapping[str, Any],
    relationship_summary: Mapping[str, Any],
    cases: list[Mapping[str, Any]],
    scores: list[Mapping[str, Any]],
    elapsed_sec: float,
    output_dir: Path,
) -> dict[str, Any]:
    total = len(scores)
    pass_count = sum(1 for score in scores if score.get("status") == "pass")
    check_counts: dict[str, int] = {}
    for score in scores:
        for name, value in dict(score.get("checks") or {}).items():
            if value:
                check_counts[name] = check_counts.get(name, 0) + 1
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "run_id": run_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_sec": elapsed_sec,
        "gate_status": "pass" if total > 0 and pass_count == total else "fail",
        "diagnostic_only": True,
        "activation_summary": str(args.activation_summary.resolve()),
        "activation_run_id": str(activation_summary.get("run_id") or ""),
        "relationship_summary": str(args.relationship_summary.resolve()) if args.relationship_summary.exists() else "",
        "relationship_run_id": str(relationship_summary.get("run_id") or ""),
        "output_dir": str(output_dir.resolve()),
        "retrieval_runtime_config": {
            "manifest_path_ref": _path_ref(args.manifest_path),
            "bm25_index_ref": _path_ref(args.bm25_index_dir),
            "object_bm25_index_ref": _path_ref(args.object_bm25_index_dir),
            "ledger_store_ref": _path_ref(args.ledger_store_path),
            "market_evidence_ref": _path_ref(args.market_evidence_path),
            "industry_evidence_ref": _path_ref(args.industry_evidence_path),
            "sector_depth_pack_ref": _path_ref(args.sector_depth_pack_path),
            "bge_model_ref": _path_ref(args.bge_model),
            "bge_device": args.bge_device,
            "context_runner": args.context_runner,
            "reranker_candidate_limit": args.reranker_candidate_limit,
            "reranker_top_k": args.reranker_top_k,
        },
        "metrics": {
            "case_count": total,
            "pass_count": pass_count,
            "failed_count": total - pass_count,
            "check_counts": check_counts,
            "total_tool_calls": sum(int(score.get("tool_call_count") or 0) for score in scores),
            "context_rows": sum(int((score.get("row_counts") or {}).get("context_rows") or 0) for score in scores),
            "runtime_ledger_rows": sum(int((score.get("row_counts") or {}).get("runtime_ledger_rows") or 0) for score in scores),
            "market_snapshot_rows": sum(int((score.get("row_counts") or {}).get("market_snapshot_rows") or 0) for score in scores),
            "industry_snapshot_rows": sum(int((score.get("row_counts") or {}).get("industry_snapshot_rows") or 0) for score in scores),
            "sec_candidate_count_pre_rerank": sum(int((score.get("retrieval_runtime") or {}).get("sec_candidate_count_pre_rerank") or 0) for score in scores),
            "sec_candidate_sent_to_bge": sum(int((score.get("retrieval_runtime") or {}).get("sec_candidate_sent_to_bge") or 0) for score in scores),
        },
        "cases": [dict(score) for score in scores],
    }


def _result_summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status") or "",
        "native_stop_after_node": result.get("native_stop_after_node") or "",
        "loop_break_reason": result.get("loop_break_reason") or "",
        "retrieval_plan_summary": (result.get("retrieval_plan") or {}).get("summary") if isinstance(result.get("retrieval_plan"), Mapping) else {},
        "tool_observations": [dict(row) for row in result.get("tool_observations") or [] if isinstance(row, Mapping)],
        "tool_call_ledger": result.get("tool_call_ledger") if isinstance(result.get("tool_call_ledger"), Mapping) else {},
        "row_counts": {
            "context_rows": len(result.get("context_rows") or []),
            "runtime_ledger_rows": len(result.get("runtime_ledger_rows") or []),
            "market_snapshot_rows": len(result.get("market_snapshot_rows") or []),
            "industry_snapshot_rows": len(result.get("industry_snapshot_rows") or []),
        },
        "context_row_sample": [_row_sample(row) for row in result.get("context_rows") or [] if isinstance(row, Mapping)][:5],
        "runtime_ledger_row_sample": [_row_sample(row) for row in result.get("runtime_ledger_rows") or [] if isinstance(row, Mapping)][:5],
        "market_row_sample": [_row_sample(row) for row in result.get("market_snapshot_rows") or [] if isinstance(row, Mapping)][:5],
        "industry_row_sample": [_row_sample(row) for row in result.get("industry_snapshot_rows") or [] if isinstance(row, Mapping)][:5],
    }


def _tool_calls(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    ledger = result.get("tool_call_ledger") if isinstance(result.get("tool_call_ledger"), Mapping) else {}
    return [dict(item) for item in ledger.get("records") or [] if isinstance(item, Mapping)]


def _route_tool(route: Mapping[str, Any]) -> tuple[str, str]:
    return ROUTE_OPERATOR_TOOL.get(str(route.get("retrieval_route") or ""), ("", ""))


def _tool_ownership_valid(tool_calls: list[Mapping[str, Any]]) -> bool:
    registry = agent_registry_by_id()
    for call in tool_calls:
        agent_id = str(call.get("agent_id") or "")
        tool_name = str(call.get("tool_name") or "")
        allowed = set(_string_list((registry.get(agent_id) or {}).get("allowed_tools")))
        if tool_name not in allowed:
            return False
    return True


def _candidate_counts(call: Mapping[str, Any]) -> dict[str, Any]:
    metadata = call.get("metadata") if isinstance(call.get("metadata"), Mapping) else {}
    runtime = metadata.get("runtime_summary") if isinstance(metadata.get("runtime_summary"), Mapping) else {}
    return dict(runtime.get("candidate_counts") or {}) if isinstance(runtime.get("candidate_counts"), Mapping) else {}


def _bge_policy(sec_calls: list[Mapping[str, Any]]) -> dict[str, Any]:
    for call in sec_calls:
        metadata = call.get("metadata") if isinstance(call.get("metadata"), Mapping) else {}
        arguments = metadata.get("argument_summary") if isinstance(metadata.get("argument_summary"), Mapping) else {}
        policy = arguments.get("retrieval_runtime_policy") if isinstance(arguments.get("retrieval_runtime_policy"), Mapping) else {}
        if policy:
            return {
                "bge_device": arguments.get("bge_device") or "",
                "bge_first": arguments.get("bge_first"),
                "runtime_policy": dict(policy),
            }
    return {}


def _row_payload_usable(result: Mapping[str, Any]) -> bool:
    rows = [
        *(result.get("context_rows") or []),
        *(result.get("runtime_ledger_rows") or []),
        *(result.get("market_snapshot_rows") or []),
        *(result.get("industry_snapshot_rows") or []),
    ]
    if not rows:
        return False
    usable = 0
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        if row.get("evidence_ref") or row.get("evidence_id") or row.get("metric_id") or row.get("ticker") or row.get("series_id"):
            usable += 1
    return usable > 0


def _tool_call_summary(call: Mapping[str, Any]) -> dict[str, Any]:
    metadata = call.get("metadata") if isinstance(call.get("metadata"), Mapping) else {}
    return {
        "agent_id": call.get("agent_id") or "",
        "tool_name": call.get("tool_name") or "",
        "status": call.get("status") or "",
        "row_count": call.get("row_count") or 0,
        "source_gap_count": call.get("source_gap_count") or 0,
        "elapsed_ms": call.get("elapsed_ms") or 0,
        "argument_summary": metadata.get("argument_summary") if isinstance(metadata.get("argument_summary"), Mapping) else {},
        "runtime_summary": metadata.get("runtime_summary") if isinstance(metadata.get("runtime_summary"), Mapping) else {},
        "error": str(metadata.get("error") or "")[:300],
    }


def _row_sample(row: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "evidence_ref",
        "evidence_id",
        "metric_id",
        "ticker",
        "related_ticker",
        "source_family",
        "source_tier",
        "fiscal_year",
        "form_type",
        "metric_family",
        "metric_name",
        "value",
        "unit",
        "section",
        "snapshot_id",
        "as_of_date",
        "series_id",
        "summary",
        "text_preview",
    )
    return {key: row.get(key) for key in allowed if key in row and row.get(key) not in (None, "")}


def _sanitize_gap(gap: Mapping[str, Any]) -> dict[str, Any]:
    blocked = {"path", "private_path", "raw_text"}
    return {str(key): value for key, value in gap.items() if str(key) not in blocked and "path" not in str(key).lower()}


def _expected_pack_ids(relationship_plan: Mapping[str, Any]) -> list[str]:
    refs = [
        ref
        for rel in relationship_plan.get("relationships") or []
        if isinstance(rel, Mapping)
        for ref in _string_list(rel.get("evidence_refs"))
    ]
    packs = []
    for ref in refs:
        parts = ref.split(":")
        if len(parts) >= 2 and parts[0] == "sector_depth_pack":
            packs.append(parts[1])
    return _unique_strings(packs)


def _scope(plan: Mapping[str, Any]) -> dict[str, Any]:
    return dict(plan.get("scope") or {}) if isinstance(plan.get("scope"), Mapping) else {}


def _list_from_requirements(requirements: list[Mapping[str, Any]], key: str) -> list[Any]:
    out: list[Any] = []
    for req in requirements:
        out.extend(_list(req.get(key)))
    return out


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _string_list(value: Any) -> list[str]:
    return [str(item).strip() for item in _list(value) if str(item).strip()]


def _unique_strings(value: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in _string_list(value):
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _unique_upper(value: Any) -> list[str]:
    return _unique_strings([str(item).upper() for item in _list(value) if str(item).strip()])


def _unique_ints(value: Any) -> list[int]:
    out: list[int] = []
    seen: set[int] = set()
    for item in _list(value):
        try:
            parsed = int(item)
        except (TypeError, ValueError):
            continue
        if parsed not in seen:
            seen.add(parsed)
            out.append(parsed)
    return out


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _positive_count(value: Any) -> bool:
    return _int_value(value) > 0


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


def _path_ref(path: Path) -> str:
    text = str(path).replace("\\", "/")
    if len(text) <= 96:
        return text
    return ".../" + "/".join(text.split("/")[-4:])


def _stdout_summary(summary: Mapping[str, Any], output_path: Path) -> dict[str, Any]:
    return {
        "run_id": summary.get("run_id"),
        "gate_status": summary.get("gate_status"),
        "output_path": str(output_path.resolve()),
        "metrics": summary.get("metrics"),
        "failed_cases": [
            {
                "case_id": case.get("case_id"),
                "failed_checks": [name for name, value in dict(case.get("checks") or {}).items() if not value],
            }
            for case in summary.get("cases") or []
            if isinstance(case, Mapping) and case.get("status") != "pass"
        ],
    }


def _default_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_fin_agent_s3_evidence_operator_gate_%H%M%S")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
