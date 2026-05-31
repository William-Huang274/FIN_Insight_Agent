from __future__ import annotations

import argparse
import json
import os
import re
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
from sec_agent.multi_agent_contracts import validate_specialist_memolet  # noqa: E402
from sec_agent.multi_agent_runtime import build_agent_data_view  # noqa: E402
from sec_agent.langgraph_orchestrator import (  # noqa: E402
    build_multi_agent_orchestration_graph_from_env,
    make_multi_agent_smoke_state,
)


DEFAULT_CASES_PATH = REPO_ROOT / "tests" / "fixtures" / "multi_agent_real_llm_chain_cases_v0_1.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "multi_agent_real_llm_chain_eval"
DEFAULT_SECTOR_DEPTH_MANIFEST = REPO_ROOT / "data" / "processed_private" / "manifests" / "sector_depth_full238_us_v0_2_mixed_with_8k_manifest_fy2023_2027.jsonl"
DEFAULT_SECTOR_DEPTH_BM25 = REPO_ROOT / "data" / "indexes" / "bm25" / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027"
DEFAULT_SECTOR_DEPTH_OBJECT_BM25 = REPO_ROOT / "data" / "indexes" / "bm25" / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects"
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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real-LLM multi-agent full-chain diagnostics.")
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--case-id", action="append", default=[], help="Run only selected case_id values. Repeatable.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--category", action="append", default=[], help="Run selected categories. Repeatable.")
    parser.add_argument("--llm-backend", default=os.environ.get("LLM_BACKEND", "deepseek"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--chat-completions-path", default=os.environ.get("CHAT_COMPLETIONS_PATH", "/chat/completions"))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--research-lead-max-tokens", type=int, default=int(os.environ.get("RESEARCH_LEAD_MAX_TOKENS", "2400")))
    parser.add_argument("--specialist-max-tokens", type=int, default=int(os.environ.get("SPECIALIST_MAX_TOKENS", "2000")))
    parser.add_argument("--universe-max-tokens", type=int, default=int(os.environ.get("UNIVERSE_MAX_TOKENS", "3000")))
    parser.add_argument("--memo-max-tokens", type=int, default=int(os.environ.get("MEMO_MAX_TOKENS", "1800")))
    parser.add_argument("--verifier-max-tokens", type=int, default=int(os.environ.get("VERIFIER_MAX_TOKENS", "1000")))
    parser.add_argument("--timeout-s", type=int, default=int(os.environ.get("MULTI_AGENT_REAL_CHAIN_TIMEOUT_S", "180")))
    parser.add_argument("--real-evidence-operators", action="store_true", help="Execute MCP/interactive retrieval instead of dry-run operator rows.")
    parser.add_argument("--manifest-path", type=Path, default=Path(os.environ.get("MANIFEST_PATH", str(DEFAULT_SECTOR_DEPTH_MANIFEST))))
    parser.add_argument("--bm25-index-dir", type=Path, default=Path(os.environ.get("BM25_INDEX_DIR", str(DEFAULT_SECTOR_DEPTH_BM25))))
    parser.add_argument("--object-bm25-index-dir", type=Path, default=Path(os.environ.get("OBJECT_BM25_INDEX_DIR", str(DEFAULT_SECTOR_DEPTH_OBJECT_BM25))))
    parser.add_argument("--market-evidence-path", type=Path, default=Path(os.environ.get("MARKET_EVIDENCE_PATH", str(DEFAULT_MARKET_EVIDENCE))))
    parser.add_argument("--industry-evidence-path", type=Path, default=Path(os.environ.get("INDUSTRY_EVIDENCE_PATH", str(DEFAULT_INDUSTRY_EVIDENCE))))
    parser.add_argument("--sector-depth-pack-path", type=Path, default=Path(os.environ.get("SECTOR_DEPTH_PACK_PATH", str(DEFAULT_SECTOR_DEPTH_PACK))))
    parser.add_argument("--market-snapshot-id", default=os.environ.get("MARKET_SNAPSHOT_ID", DEFAULT_MARKET_SNAPSHOT_ID))
    parser.add_argument("--market-as-of-date", default=os.environ.get("MARKET_AS_OF_DATE", DEFAULT_MARKET_AS_OF_DATE))
    parser.add_argument("--bge-model", type=Path, default=Path(os.environ.get("BGE_MODEL", str(DEFAULT_BGE_MODEL))))
    parser.add_argument("--bge-device", default=os.environ.get("BGE_DEVICE", "cpu"))
    parser.add_argument("--context-runner", default=os.environ.get("SEC_AGENT_CONTEXT_RUNNER", os.environ.get("CONTEXT_RUNNER", "in_process")))
    parser.add_argument("--evidence-top-k", type=int, default=int(os.environ.get("EVIDENCE_TOP_K", "4")))
    parser.add_argument("--object-top-k", type=int, default=int(os.environ.get("OBJECT_TOP_K", "4")))
    parser.add_argument("--reranker-candidate-limit", type=int, default=int(os.environ.get("RERANKER_CANDIDATE_LIMIT", "160")))
    parser.add_argument("--reranker-top-k", type=int, default=int(os.environ.get("RERANKER_TOP_K", "32")))
    parser.add_argument("--reranker-batch-size", type=int, default=int(os.environ.get("RERANKER_BATCH_SIZE", "8")))
    parser.add_argument("--reranker-max-length", type=int, default=int(os.environ.get("RERANKER_MAX_LENGTH", "512")))
    parser.add_argument("--reranker-doc-max-chars", type=int, default=int(os.environ.get("RERANKER_DOC_MAX_CHARS", "1800")))
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless all hard gates pass.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases = _selected_cases(_read_jsonl(args.cases_path), args)
    run_id = args.run_id or _default_run_id(args)
    output_dir = args.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    env = _graph_env(args)
    graph = build_multi_agent_orchestration_graph_from_env(env=env, use_checkpointer=False)
    conversation_summaries: dict[str, dict[str, Any]] = {}
    scores: list[dict[str, Any]] = []
    started = time.time()

    for ordinal, case in enumerate(cases, start=1):
        case_started = time.time()
        case_dir = output_dir / str(case["case_id"])
        case_dir.mkdir(parents=True, exist_ok=True)
        previous_turn_summary = _previous_turn_summary(case, conversation_summaries)
        state = _initial_state(case, case_dir, run_id=run_id, previous_turn_summary=previous_turn_summary, args=args)
        result = graph.invoke(
            state,
            config={"configurable": {"thread_id": f"{run_id}-{case['case_id']}"}},
        )
        elapsed_ms = int((time.time() - case_started) * 1000)
        summary = _read_json(case_dir / "multi_agent_summary.json")
        native = _read_json(case_dir / "langgraph_native_summary.json")
        score = score_case(case, result, summary, native, elapsed_ms=elapsed_ms, ordinal=ordinal, total=len(cases))
        (case_dir / "real_chain_case_score.json").write_text(
            json.dumps(score, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        scores.append(score)
        _update_conversation_summary(case, score, result, conversation_summaries)

    aggregate = _aggregate(
        run_id=run_id,
        args=args,
        cases=cases,
        scores=scores,
        elapsed_ms=int((time.time() - started) * 1000),
        output_dir=output_dir,
    )
    output_quality_audit = _write_output_quality_audit(aggregate, output_dir)
    aggregate["output_quality_audit"] = {
        "schema_version": output_quality_audit.get("schema_version") or "",
        "diagnostic_only": True,
        "issue_counts": output_quality_audit.get("issue_counts") or {},
        "run_hypotheses": output_quality_audit.get("run_hypotheses") or [],
        "case_risk_levels": {
            str(case.get("case_id") or ""): str(case.get("quality_risk_level") or "")
            for case in output_quality_audit.get("cases") or []
            if isinstance(case, Mapping)
        },
    }
    _write_jsonl(output_dir / "real_chain_case_scores.jsonl", scores)
    summary_path = output_dir / "real_chain_eval_summary.json"
    summary_path.write_text(json.dumps(aggregate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_stdout_summary(aggregate, summary_path), ensure_ascii=False, indent=2))
    if args.strict and aggregate["gate_status"] != "pass":
        return 1
    return 0


def _write_output_quality_audit(aggregate: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    audit_summary, render_markdown = _load_quality_audit_helpers()
    audit = audit_summary(aggregate, artifact_root=output_dir)
    (output_dir / "multi_agent_output_quality_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "multi_agent_output_quality_audit.md").write_text(render_markdown(audit), encoding="utf-8")
    return audit


def _load_quality_audit_helpers():
    try:
        from audit_multi_agent_output_quality import audit_summary, render_markdown

        return audit_summary, render_markdown
    except ImportError:
        import importlib.util

        path = Path(__file__).with_name("audit_multi_agent_output_quality.py")
        spec = importlib.util.spec_from_file_location("audit_multi_agent_output_quality_local", path)
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.audit_summary, module.render_markdown


def score_case(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
    summary: Mapping[str, Any],
    native: Mapping[str, Any],
    *,
    elapsed_ms: int,
    ordinal: int = 1,
    total: int = 1,
) -> dict[str, Any]:
    activation = result.get("agent_activation_plan") if isinstance(result.get("agent_activation_plan"), Mapping) else {}
    active_agents = set(_string_list(activation.get("activate_agents")))
    required_agents = set(_string_list(case.get("required_agents")))
    forbidden_agents = set(_string_list(case.get("forbidden_agents")))
    required_specialists = set(_string_list(case.get("expected_specialist_agents")))
    tool_calls = _tool_calls(result, summary)
    llm_routes = summary.get("llm_routes") if isinstance(summary.get("llm_routes"), Mapping) else {}
    memo = result.get("memo_answer") if isinstance(result.get("memo_answer"), Mapping) else {}
    claim_verification = result.get("claim_verification") if isinstance(result.get("claim_verification"), Mapping) else {}
    specialist_verification = result.get("specialist_verification") if isinstance(result.get("specialist_verification"), Mapping) else {}
    universe_validation = result.get("universe_relationship_validation") if isinstance(result.get("universe_relationship_validation"), Mapping) else {}
    relationship_lookup = result.get("relationship_graph_observation") if isinstance(result.get("relationship_graph_observation"), Mapping) else {}
    specialist_routes = _specialist_route_results(result, summary)
    real_retrieval_required = bool(case.get("require_real_retrieval_pass"))
    real_specialist_quality_required = bool(case.get("require_real_evidence_quality_pass"))
    real_operator_checks = _real_operator_checks(case, result, tool_calls, required=real_retrieval_required)
    specialist_quality = _specialist_real_evidence_quality(case, result, required_specialists, required=real_specialist_quality_required)
    memo_status_allowed = _string_list(case.get("memo_status_allowed"))
    memo_status = str(memo.get("answer_status") or "")
    accept_bounded_block = bool(case.get("accept_bounded_block"))
    max_tool_calls = int(case.get("max_tool_calls_total_lte") or 999)
    activated_scope = set(_string_list(activation.get("focus_tickers")) + _string_list(activation.get("search_scope_tickers")))
    forbidden_scope_hits = sorted(activated_scope & set(_string_list(case.get("forbidden_scope_tickers"))))

    layer_checks = {
        "research_lead": {
            "llm_invoked": _diag_call_count(_route(llm_routes, "research_lead")) >= 1 if case.get("require_lead_llm_pass") else True,
            "llm_calls_ok": _diag_calls_ok(_route(llm_routes, "research_lead")) if case.get("require_lead_llm_pass") else True,
            "validation_pass": (result.get("agent_activation_validation") or {}).get("status") == "pass",
            "execution_mode_match": activation.get("execution_mode") == case.get("expected_execution_mode"),
            "required_agents_present": required_agents <= active_agents,
            "forbidden_agents_absent": not (forbidden_agents & active_agents),
            "forbidden_scope_absent": not forbidden_scope_hits,
        },
        "universe_relationship": _universe_checks(
            case,
            result=result,
            route=_route(llm_routes, "universe_relationship"),
            lookup=relationship_lookup,
            validation=universe_validation,
            tool_calls=tool_calls,
        ),
        "evidence_operators": {
            "expected_operator_agents_called": set(_string_list(case.get("expected_operator_agents"))) <= {str(call.get("agent_id") or "") for call in tool_calls},
            "expected_tool_names_called": _expected_tool_names_called(case, tool_calls),
            "tool_ownership_valid": _tool_ownership_valid(tool_calls),
            "tool_budget_lte": len(tool_calls) <= max_tool_calls,
            "no_budget_loop_break": str(result.get("loop_break_reason") or "") not in {"tool_budget_exhausted", "agent_tool_budget_exhausted"},
            "no_duplicate_loop_break": str(result.get("loop_break_reason") or "") != "duplicate_tool_call_blocked",
            **real_operator_checks,
        },
        "specialists": {
            "expected_routes_present": required_specialists <= {str(row.get("agent_id") or "") for row in specialist_routes},
            "expected_routes_valid": _specialist_routes_valid(required_specialists, specialist_routes) if case.get("require_specialist_llm_pass") else True,
            "route_success_distinct_from_real_evidence_quality": specialist_quality["route_success_distinct_from_real_evidence_quality"],
            "real_evidence_quality_pass": specialist_quality["quality_pass"],
            "verification_status_valid": _specialist_verification_valid(specialist_verification, accept_bounded_block),
            "unsupported_block_is_bounded": _bounded_block_valid(specialist_verification, memo, claim_verification, accept_bounded_block),
        },
        "memo_verifier": {
            "memo_status_allowed": (memo_status in memo_status_allowed) if memo_status_allowed and memo_status_allowed != [""] else True,
            "memo_llm_pass": _memo_llm_pass(result, summary) if case.get("require_memo_llm_pass") else True,
            "verifier_llm_pass": _verifier_llm_pass(result, summary) if case.get("require_verifier_llm_pass") else True,
            "claim_verification_pass": (
                claim_verification.get("status") == "pass"
                if claim_verification or "verifier" in active_agents or case.get("require_verifier_llm_pass")
                else True
            ),
            "rendered_answer_not_empty": bool(str(result.get("rendered_answer") or "").strip()),
        },
        "payload_safety": {
            "raw_payload_not_in_summary": (summary.get("payload_policy") or {}).get("raw_evidence") == "not_included",
            "no_api_key_marker": "sk-" not in json.dumps(summary, ensure_ascii=False),
            "no_private_path_marker": "raw_private" not in json.dumps(summary, ensure_ascii=False),
        },
    }
    checks = _flatten_checks(layer_checks)
    hard_gate_status = "pass" if all(checks.values()) and result.get("status") == "completed" else "fail"
    return {
        "schema_version": "sec_agent_multi_agent_real_llm_chain_case_score_v0.1",
        "case_id": case.get("case_id"),
        "category": case.get("category"),
        "conversation_id": case.get("conversation_id") or "",
        "turn_index": int(case.get("turn_index") or 0),
        "ordinal": ordinal,
        "total": total,
        "gate_status": hard_gate_status,
        "elapsed_ms": elapsed_ms,
        "status": result.get("status") or "",
        "execution_mode": activation.get("execution_mode") or "",
        "expected_execution_mode": case.get("expected_execution_mode") or "",
        "activated_agents": sorted(active_agents),
        "missing_required_agents": sorted(required_agents - active_agents),
        "forbidden_activated_agents": sorted(forbidden_agents & active_agents),
        "forbidden_scope_hits": forbidden_scope_hits,
        "tool_call_count": len(tool_calls),
        "loop_break_reason": result.get("loop_break_reason") or "",
        "memo_status": memo_status,
        "claim_verification": claim_verification.get("status") or "",
        "specialist_verification": specialist_verification.get("status") or "",
        "universe_validation": universe_validation.get("status") or ("skipped" if "universe_relationship" not in active_agents else ""),
        "relationship_lookup_status": relationship_lookup.get("status") or "",
        "real_retrieval_required": real_retrieval_required,
        "real_specialist_quality_required": real_specialist_quality_required,
        "specialist_real_evidence_quality": specialist_quality,
        "layer_checks": layer_checks,
        "checks": checks,
        "agent_audit": _agent_audit(result, summary, tool_calls=tool_calls, specialist_routes=specialist_routes, specialist_quality=specialist_quality),
        "node_trace": [row.get("node") for row in result.get("node_trace") or [] if isinstance(row, Mapping)],
        "summary_artifact_present": bool(summary),
        "native_summary_artifact_present": bool(native),
        "rendered_answer_preview": str(result.get("rendered_answer") or "")[:320],
    }


def _selected_cases(rows: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    cases = rows
    if args.case_id:
        selected = {str(case_id) for case_id in args.case_id}
        cases = [case for case in cases if str(case.get("case_id") or "") in selected]
    if args.category:
        selected_categories = {str(category) for category in args.category}
        cases = [case for case in cases if str(case.get("category") or "") in selected_categories]
    if args.limit > 0:
        cases = cases[: args.limit]
    return cases


def _graph_env(args: argparse.Namespace) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "LLM_BACKEND": args.llm_backend,
            "BASE_URL": args.base_url,
            "CHAT_COMPLETIONS_PATH": args.chat_completions_path,
            "MODEL_NAME": args.model,
            "API_KEY_ENV": args.api_key_env,
            "SEC_AGENT_MULTI_AGENT_LEAD_ROUTER": "llm",
            "SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER": "llm",
            "SEC_AGENT_MULTI_AGENT_UNIVERSE_ROUTER": "llm",
            "SEC_AGENT_MULTI_AGENT_MEMO_ROUTER": "llm",
            "SEC_AGENT_MULTI_AGENT_EVIDENCE_OPERATOR_MODE": "real" if args.real_evidence_operators else "dry_run",
            "RESEARCH_LEAD_REQUIRE_EVIDENCE_REQUIREMENTS": "1",
            "MANIFEST_PATH": str(args.manifest_path),
            "BM25_INDEX_DIR": str(args.bm25_index_dir),
            "OBJECT_BM25_INDEX_DIR": str(args.object_bm25_index_dir),
            "MARKET_EVIDENCE_PATH": str(args.market_evidence_path),
            "INDUSTRY_EVIDENCE_PATH": str(args.industry_evidence_path),
            "SECTOR_DEPTH_PACK_PATH": str(args.sector_depth_pack_path),
            "MARKET_SNAPSHOT_ID": args.market_snapshot_id,
            "MARKET_AS_OF_DATE": args.market_as_of_date,
            "BGE_MODEL": str(args.bge_model),
            "BGE_DEVICE": args.bge_device,
            "SEC_AGENT_CONTEXT_RUNNER": args.context_runner,
            "RESEARCH_LEAD_MAX_TOKENS": str(args.research_lead_max_tokens),
            "SPECIALIST_MAX_TOKENS": str(args.specialist_max_tokens),
            "UNIVERSE_MAX_TOKENS": str(args.universe_max_tokens),
            "MEMO_MAX_TOKENS": str(args.memo_max_tokens),
            "VERIFIER_MAX_TOKENS": str(args.verifier_max_tokens),
            "RESEARCH_LEAD_TIMEOUT_S": str(args.timeout_s),
            "SPECIALIST_TIMEOUT_S": str(args.timeout_s),
            "UNIVERSE_TIMEOUT_S": str(args.timeout_s),
            "MEMO_TIMEOUT_S": str(args.timeout_s),
        }
    )
    return env


def _initial_state(
    case: Mapping[str, Any],
    case_dir: Path,
    *,
    run_id: str,
    previous_turn_summary: Mapping[str, Any] | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    state = make_multi_agent_smoke_state(
        user_query=str(case.get("prompt") or ""),
        output_dir=case_dir,
        query_contract=_query_contract(case),
        focus_tickers=_string_list(case.get("focus_tickers")),
        search_scope_tickers=_string_list(case.get("search_scope_tickers")),
    )
    state["run_id"] = f"{run_id}_{case.get('case_id')}"
    inventory_companies = _string_list(case.get("source_inventory_companies"))
    project_inventory: dict[str, Any] = {
        "source_families": _string_list(case.get("source_tiers")),
        "evaluation_inventory": "summary_only_no_private_paths",
    }
    if inventory_companies:
        project_inventory["companies"] = [{"ticker": ticker} for ticker in inventory_companies]
    state["project_inventory"] = project_inventory
    context = {
        "evidence_operator_mode": "real" if args.real_evidence_operators else "dry_run",
        "build_runtime_ledger": bool(args.real_evidence_operators),
        "manifest_path": str(args.manifest_path),
        "bm25_index_dir": str(args.bm25_index_dir),
        "object_bm25_index_dir": str(args.object_bm25_index_dir),
        "market_evidence_path": str(args.market_evidence_path),
        "industry_evidence_path": str(args.industry_evidence_path),
        "sector_depth_pack_path": str(case.get("sector_depth_pack_path") or args.sector_depth_pack_path),
        "market_snapshot": {"snapshot_id": args.market_snapshot_id, "as_of_date": args.market_as_of_date},
        "market_snapshot_id": args.market_snapshot_id,
        "market_as_of_date": args.market_as_of_date,
        "industry_source_families": ["industry_snapshot"],
        "expected_relationship_pack_ids": _string_list(case.get("expected_relationship_pack_ids")),
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
        "focus_tickers": _string_list(case.get("focus_tickers")),
        "search_scope_tickers": _string_list(case.get("search_scope_tickers")),
        "conversation_id": case.get("conversation_id") or "",
        "turn_index": int(case.get("turn_index") or 0),
        "previous_turn_summary": dict(previous_turn_summary or {}),
    }
    state["multi_agent_context"] = context
    return state


def _query_contract(case: Mapping[str, Any]) -> dict[str, Any]:
    tickers = _string_list(case.get("search_scope_tickers"))
    focus = _string_list(case.get("focus_tickers")) or tickers[:2]
    source_tiers = _string_list(case.get("source_tiers")) or ["primary_sec_filing"]
    metric_families = _string_list(case.get("metric_families")) or ["revenue", "capex", "margin"]
    return {
        "task_type": "open_analysis",
        "search_scope_tickers": tickers,
        "focus_tickers": focus,
        "years": [int(year) for year in (case.get("years") or [2026])],
        "filing_types": _string_list(case.get("filing_types")) or ["10-Q", "8-K"],
        "source_tiers": source_tiers,
        "metric_families": metric_families,
        "decomposed_tasks": [
            {
                "task_id": f"{case.get('case_id')}_primary",
                "question_zh": str(case.get("prompt") or "")[:160],
                "priority": "primary",
                "required_tickers": tickers or focus,
                "required_metric_families": metric_families,
            }
        ],
    }


def _universe_checks(
    case: Mapping[str, Any],
    *,
    result: Mapping[str, Any],
    route: Mapping[str, Any],
    lookup: Mapping[str, Any],
    validation: Mapping[str, Any],
    tool_calls: list[dict[str, Any]],
) -> dict[str, bool]:
    active = set(_string_list((result.get("agent_activation_plan") or {}).get("activate_agents") if isinstance(result.get("agent_activation_plan"), Mapping) else []))
    universe_expected = "universe_relationship" in active or bool(case.get("require_universe_llm_pass"))
    if not universe_expected:
        return {
            "skipped_when_not_expected": not validation,
            "llm_invoked_when_expected": True,
            "llm_calls_ok": True,
            "validation_pass_when_expected": True,
            "relationship_lookup_called": True,
            "relationship_claim_scope_bounded": True,
        }
    relationships = lookup.get("relationships") if isinstance(lookup.get("relationships"), list) else []
    return {
        "skipped_when_not_expected": True,
        "llm_invoked_when_expected": _diag_call_count(route) >= 1,
        "llm_calls_ok": _diag_calls_ok(route),
        "validation_pass_when_expected": validation.get("status") == "pass",
        "relationship_lookup_called": any(call.get("tool_name") == "relationship_graph_lookup" for call in tool_calls),
        "relationship_claim_scope_bounded": all(str(item.get("claim_scope") or "") == "scope_or_hypothesis_only" for item in relationships if isinstance(item, Mapping)),
    }


def _real_operator_checks(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
    tool_calls: list[dict[str, Any]],
    *,
    required: bool,
) -> dict[str, bool]:
    expected_tools = set(_string_list(case.get("expected_tool_names")))
    sec_expected = "sec_search_filings" in expected_tools
    market_expected = "market_get_snapshot" in expected_tools
    industry_expected = "industry_get_snapshot" in expected_tools
    relationship_expected = "relationship_graph_lookup" in expected_tools
    sec_calls = [call for call in tool_calls if call.get("tool_name") == "sec_search_filings"]
    sec_success_calls = [call for call in sec_calls if str(call.get("status") or "") not in {"dry_run", "error"}]
    sec_runtime = [_runtime_summary(call) for call in sec_calls]
    candidate_counts = [item.get("candidate_counts") or {} for item in sec_runtime if isinstance(item, Mapping)]
    if not required:
        return {
            "real_retrieval_mode_required": True,
            "sec_search_not_dry_run": True,
            "sec_search_context_rows_present": True,
            "sec_search_bm25_candidates_present": True,
            "sec_search_bge_rerank_present": True,
            "sec_search_runtime_ledger_rows_present": True,
            "market_rows_present": True,
            "industry_rows_present": True,
            "relationship_lookup_rows_present": True,
        }
    return {
        "real_retrieval_mode_required": True,
        "sec_search_not_dry_run": (not sec_expected) or bool(sec_success_calls and all(str(call.get("status") or "") != "dry_run" for call in sec_calls)),
        "sec_search_errors_absent": (not sec_expected) or all(str(call.get("status") or "") != "error" for call in sec_calls),
        "sec_search_context_rows_present": (not sec_expected) or bool(result.get("context_rows")),
        "sec_search_bm25_candidates_present": (not sec_expected) or any(_positive_count(counts.get("candidate_row_count_pre_rerank")) for counts in candidate_counts),
        "sec_search_bge_rerank_present": (not sec_expected) or any(_positive_count(counts.get("candidate_sent_to_bge")) for counts in candidate_counts),
        "sec_search_runtime_ledger_rows_present": (not bool(case.get("require_runtime_ledger_rows"))) or bool(result.get("runtime_ledger_rows")),
        "market_rows_present": (not market_expected) or bool(result.get("market_snapshot_rows")),
        "industry_rows_present": (not industry_expected) or bool(result.get("industry_snapshot_rows")),
        "relationship_lookup_rows_present": (not relationship_expected) or bool((result.get("relationship_graph_observation") or {}).get("relationships")),
    }


def _specialist_real_evidence_quality(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
    required_specialists: set[str],
    *,
    required: bool,
) -> dict[str, Any]:
    route_results = _specialist_route_results(result, {})
    route_status_by_agent = {str(row.get("agent_id") or ""): str(row.get("status") or "") for row in route_results}
    memolets = {
        str(row.get("agent_id") or ""): dict(row)
        for row in result.get("specialist_outputs") or []
        if isinstance(row, Mapping)
    }
    details: dict[str, dict[str, Any]] = {}
    for agent_id in sorted(required_specialists):
        data_view = build_agent_data_view(agent_id, result)
        rows = [dict(row) for row in data_view.get("bounded_evidence_rows") or [] if isinstance(row, Mapping)]
        known_refs = {str(row.get("evidence_ref") or "") for row in rows if str(row.get("evidence_ref") or "").strip()}
        memolet = memolets.get(agent_id, {})
        validation = validate_specialist_memolet(memolet, known_evidence_refs=known_refs)
        observations = [dict(row) for row in memolet.get("observations") or [] if isinstance(row, Mapping)]
        observed_refs = {
            str(ref)
            for observation in observations
            if not observation.get("unsupported")
            for ref in observation.get("evidence_refs") or []
            if str(ref or "").strip()
        }
        observed_sources = {
            str(source)
            for observation in observations
            for source in observation.get("source_families") or []
            if str(source or "").strip()
        }
        allowed_sources = _allowed_specialist_source_families(agent_id)
        row_source_families = {str(row.get("source_family") or "") for row in rows if str(row.get("source_family") or "").strip()}
        relationship_gate_required = _industry_relationship_gate_required(case, agent_id)
        relationship_refs = {
            str(row.get("evidence_ref") or "")
            for row in rows
            if str(row.get("source_family") or "") == "relationship_graph" and str(row.get("evidence_ref") or "").strip()
        }
        cited_relationship_refs = observed_refs & relationship_refs
        relationship_pack_gate = _relationship_pack_relevance_gate(
            case,
            available_refs=relationship_refs,
            cited_refs=cited_relationship_refs,
            relationship_gate_required=relationship_gate_required,
        )
        relationship_summary = data_view.get("relationship_summary") if isinstance(data_view.get("relationship_summary"), Mapping) else {}
        checks = {
            "route_pass": route_status_by_agent.get(agent_id) == "pass",
            "validation_pass": validation.get("status") == "pass",
            "bounded_rows_present": bool(rows),
            "bounded_rows_not_dry_run_placeholders": all(not str(row.get("evidence_ref") or "").startswith("bounded_row_") for row in rows),
            "bounded_row_source_family_owned": bool(row_source_families) and row_source_families <= allowed_sources,
            "observation_refs_known": observed_refs <= known_refs,
            "observation_source_family_owned": (not observed_sources) or observed_sources <= allowed_sources,
            "relationship_input_present_when_required": (not relationship_gate_required) or "relationship_graph" in row_source_families,
            "relationship_summary_present_when_required": (not relationship_gate_required)
            or bool(relationship_summary.get("relationships")),
            "relationship_observation_source_used_when_required": (not relationship_gate_required)
            or "relationship_graph" in observed_sources,
            "relationship_evidence_ref_cited_when_required": (not relationship_gate_required)
            or bool(observed_refs & relationship_refs),
            **relationship_pack_gate["checks"],
        }
        details[agent_id] = {
            "status": "pass" if all(checks.values()) else "fail",
            "checks": checks,
            "input_row_count": len(rows),
            "input_source_families": sorted(row_source_families),
            "observed_source_families": sorted(observed_sources),
            "unknown_evidence_refs": sorted(observed_refs - known_refs),
            "relationship_gate_required": relationship_gate_required,
            "relationship_evidence_refs_available": sorted(relationship_refs),
            "relationship_evidence_refs_cited": sorted(cited_relationship_refs),
            **relationship_pack_gate["details"],
            "route_status": route_status_by_agent.get(agent_id, ""),
        }
    route_success = all(route_status_by_agent.get(agent_id) == "pass" for agent_id in required_specialists)
    quality_pass = (not required) or (bool(required_specialists) and all(detail.get("status") == "pass" for detail in details.values()))
    return {
        "route_success": route_success,
        "quality_pass": quality_pass,
        "route_success_distinct_from_real_evidence_quality": True,
        "details": details,
    }


def _allowed_specialist_source_families(agent_id: str) -> set[str]:
    if agent_id == "fundamental_analyst":
        return {"primary_sec_filing", "company_authored_unaudited_sec_filing"}
    if agent_id == "market_valuation_analyst":
        return {"market_snapshot"}
    if agent_id == "industry_supply_chain_analyst":
        return {"industry_snapshot", "relationship_graph"}
    if agent_id == "risk_counterevidence_analyst":
        return {
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "market_snapshot",
            "industry_snapshot",
            "relationship_graph",
            "run_artifact",
        }
    return {"primary_sec_filing", "company_authored_unaudited_sec_filing", "market_snapshot", "industry_snapshot", "relationship_graph"}


def _industry_relationship_gate_required(case: Mapping[str, Any], agent_id: str) -> bool:
    if agent_id != "industry_supply_chain_analyst":
        return False
    if bool(case.get("require_industry_relationship_evidence")):
        return True
    source_tiers = set(_string_list(case.get("source_tiers")))
    expected_tools = set(_string_list(case.get("expected_tool_names")))
    category = str(case.get("category") or "")
    return "relationship_graph" in source_tiers and (
        category == "sector_depth" or "relationship_graph_lookup" in expected_tools
    )


def _relationship_pack_relevance_gate(
    case: Mapping[str, Any],
    *,
    available_refs: set[str],
    cited_refs: set[str],
    relationship_gate_required: bool,
) -> dict[str, Any]:
    expected_pack_ids = set(_string_list(case.get("expected_relationship_pack_ids")))
    gate_required = bool(relationship_gate_required and expected_pack_ids)
    cross_sector_pack_ids = set(_string_list(case.get("allowed_cross_sector_relationship_pack_ids")))
    cross_sector_query_allowed = _query_allows_cross_sector_relationship(case)
    effective_allowed = set(expected_pack_ids)
    if cross_sector_query_allowed:
        effective_allowed |= cross_sector_pack_ids
    available_pack_ids = _sector_depth_pack_ids_from_refs(available_refs)
    cited_pack_ids = _sector_depth_pack_ids_from_refs(cited_refs)
    available_relevant = (not gate_required) or (
        bool(available_pack_ids)
        and expected_pack_ids <= available_pack_ids
        and available_pack_ids <= effective_allowed
    )
    cited_relevant = (not gate_required) or (
        bool(cited_pack_ids) and cited_pack_ids <= effective_allowed
    )
    return {
        "checks": {
            "relationship_available_pack_relevance_when_required": available_relevant,
            "relationship_cited_pack_relevance_when_required": cited_relevant,
        },
        "details": {
            "relationship_pack_gate_required": gate_required,
            "expected_relationship_pack_ids": sorted(expected_pack_ids),
            "allowed_cross_sector_relationship_pack_ids": sorted(cross_sector_pack_ids),
            "cross_sector_relationship_query_allowed": cross_sector_query_allowed,
            "effective_allowed_relationship_pack_ids": sorted(effective_allowed),
            "relationship_pack_ids_available": sorted(available_pack_ids),
            "relationship_pack_ids_cited": sorted(cited_pack_ids),
        },
    }


def _sector_depth_pack_ids_from_refs(refs: set[str]) -> set[str]:
    pack_ids: set[str] = set()
    for ref in refs:
        parts = str(ref or "").split(":")
        if len(parts) >= 3 and parts[0] == "sector_depth_pack" and parts[1]:
            pack_ids.add(parts[1])
    return pack_ids


def _query_allows_cross_sector_relationship(case: Mapping[str, Any]) -> bool:
    prompt = str(case.get("prompt") or "").lower()
    if not prompt:
        return False
    ai_terms = (
        "ai",
        "artificial intelligence",
        "ai infrastructure",
        "gpu",
        "cloud capex",
        "data center",
        "datacenter",
        "数据中心",
        "算力",
        "云",
    )
    power_terms = (
        "power",
        "electric",
        "electricity",
        "utility",
        "utilities",
        "load",
        "电力",
        "负荷",
        "公用事业",
    )
    transmission_terms = (
        "demand transmission",
        "readthrough",
        "supply chain",
        "产业链",
        "传导",
        "读通",
    )
    has_ai_signal = any(_contains_query_term(prompt, term) for term in ai_terms)
    has_power_signal = any(_contains_query_term(prompt, term) for term in power_terms)
    has_transmission_signal = any(_contains_query_term(prompt, term) for term in transmission_terms)
    return has_ai_signal and (has_power_signal or has_transmission_signal)


def _contains_query_term(text: str, term: str) -> bool:
    value = str(term or "").strip().lower()
    if not value:
        return False
    if re.fullmatch(r"[a-z0-9][a-z0-9 ._-]*", value):
        pattern = r"(?<![a-z0-9])" + re.escape(value) + r"(?![a-z0-9])"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    return value in text


def _expected_tool_names_called(case: Mapping[str, Any], tool_calls: list[dict[str, Any]]) -> bool:
    expected = set(_string_list(case.get("expected_tool_names")))
    if not expected:
        return True
    called = {str(call.get("tool_name") or "") for call in tool_calls}
    return bool(expected & called) if expected == {"sec_search_filings", "sec_query_exact_value_ledger"} else expected <= called


def _tool_ownership_valid(tool_calls: list[dict[str, Any]]) -> bool:
    registry = agent_registry_by_id()
    for call in tool_calls:
        agent_id = str(call.get("agent_id") or "")
        tool_name = str(call.get("tool_name") or "")
        allowed = set(_string_list((registry.get(agent_id) or {}).get("allowed_tools")))
        if tool_name not in allowed:
            return False
    return True


def _specialist_routes_valid(required_specialists: set[str], route_results: list[dict[str, Any]]) -> bool:
    by_agent = {str(row.get("agent_id") or ""): row for row in route_results}
    return all(str((by_agent.get(agent_id) or {}).get("status") or "") == "pass" for agent_id in required_specialists)


def _specialist_verification_valid(verification: Mapping[str, Any], accept_bounded_block: bool) -> bool:
    status = str(verification.get("status") or "")
    if not status:
        return True
    return status == "pass" or (accept_bounded_block and status == "fail")


def _bounded_block_valid(
    specialist_verification: Mapping[str, Any],
    memo: Mapping[str, Any],
    claim_verification: Mapping[str, Any],
    accept_bounded_block: bool,
) -> bool:
    if str(specialist_verification.get("status") or "") != "fail":
        return True
    return bool(
        accept_bounded_block
        and str(memo.get("answer_status") or "") == "blocked_by_specialist_verification"
        and bool(memo.get("bounded_answer_allowed"))
        and claim_verification.get("status") == "pass"
    )


def _memo_llm_pass(result: Mapping[str, Any], summary: Mapping[str, Any]) -> bool:
    memo_route = result.get("memo_route_result") if isinstance(result.get("memo_route_result"), Mapping) else {}
    if memo_route:
        return str(memo_route.get("status") or "") == "pass"
    route = _route(summary.get("llm_routes") if isinstance(summary.get("llm_routes"), Mapping) else {}, "memo_writer")
    return _diag_call_count(route) >= 1 and _diag_calls_ok(route)


def _verifier_llm_pass(result: Mapping[str, Any], summary: Mapping[str, Any]) -> bool:
    route = _route(summary.get("llm_routes") if isinstance(summary.get("llm_routes"), Mapping) else {}, "verifier")
    claim = result.get("claim_verification") if isinstance(result.get("claim_verification"), Mapping) else {}
    return claim.get("status") == "pass" and (_diag_call_count(route) >= 1 and _diag_calls_ok(route))


def _agent_audit(
    result: Mapping[str, Any],
    summary: Mapping[str, Any],
    *,
    tool_calls: list[dict[str, Any]],
    specialist_routes: list[dict[str, Any]],
    specialist_quality: Mapping[str, Any],
) -> dict[str, Any]:
    llm_routes = summary.get("llm_routes") if isinstance(summary.get("llm_routes"), Mapping) else {}
    return {
        "research_lead": {
            "validation_status": (result.get("agent_activation_validation") or {}).get("status")
            if isinstance(result.get("agent_activation_validation"), Mapping)
            else "",
            "execution_mode": (result.get("agent_activation_plan") or {}).get("execution_mode")
            if isinstance(result.get("agent_activation_plan"), Mapping)
            else "",
            "diagnostics": _route(llm_routes, "research_lead").get("diagnostics") or {},
        },
        "universe_relationship": {
            "lookup_status": (result.get("relationship_graph_observation") or {}).get("status")
            if isinstance(result.get("relationship_graph_observation"), Mapping)
            else "",
            "validation_status": (result.get("universe_relationship_validation") or {}).get("status")
            if isinstance(result.get("universe_relationship_validation"), Mapping)
            else "",
            "diagnostics": _route(llm_routes, "universe_relationship").get("diagnostics") or {},
        },
        "evidence_operators": {
            "tool_calls": [
                {
                    "agent_id": call.get("agent_id") or "",
                    "tool_name": call.get("tool_name") or "",
                    "status": call.get("status") or "",
                    "row_count": call.get("row_count") or 0,
                    "source_gap_count": call.get("source_gap_count") or 0,
                    "error": _tool_call_metadata(call).get("error") or "",
                    "argument_summary": _tool_call_metadata(call).get("argument_summary") or {},
                    "runtime_summary": _runtime_summary(call),
                }
                for call in tool_calls
            ]
        },
        "specialists": {
            "route_results": specialist_routes,
            "real_evidence_quality": dict(specialist_quality or {}),
            "verification_status": (result.get("specialist_verification") or {}).get("status")
            if isinstance(result.get("specialist_verification"), Mapping)
            else "",
        },
        "memo_writer": {
            "memo_status": (result.get("memo_answer") or {}).get("answer_status")
            if isinstance(result.get("memo_answer"), Mapping)
            else "",
            "route_result": result.get("memo_route_result") if isinstance(result.get("memo_route_result"), Mapping) else {},
            "diagnostics": _route(llm_routes, "memo_writer").get("diagnostics") or {},
        },
        "verifier": {
            "claim_verification": (result.get("claim_verification") or {}).get("status")
            if isinstance(result.get("claim_verification"), Mapping)
            else "",
            "diagnostics": _route(llm_routes, "verifier").get("diagnostics") or {},
        },
    }


def _aggregate(
    *,
    run_id: str,
    args: argparse.Namespace,
    cases: list[Mapping[str, Any]],
    scores: list[dict[str, Any]],
    elapsed_ms: int,
    output_dir: Path,
) -> dict[str, Any]:
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
        "schema_version": "sec_agent_multi_agent_real_llm_chain_eval_v0.1",
        "run_id": run_id,
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "elapsed_ms": elapsed_ms,
        "diagnostic_only": True,
        "gate_status": "pass" if failed == 0 and scores else "fail",
        "cases_path": str(args.cases_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "model_config": {
            "llm_backend": args.llm_backend,
            "base_url": args.base_url,
            "chat_completions_path": args.chat_completions_path,
            "model": args.model,
            "api_key_env": args.api_key_env,
            "api_key_present": bool(args.api_key_env and os.environ.get(str(args.api_key_env))),
            "raw_llm_response_saved": False,
            "api_key_saved": False,
        },
        "retrieval_runtime_config": {
            "real_evidence_operators": bool(args.real_evidence_operators),
            "context_runner": args.context_runner,
            "bge_device": args.bge_device,
            "bge_model_ref": _model_ref(args.bge_model),
            "reranker_candidate_limit": args.reranker_candidate_limit,
            "reranker_top_k": args.reranker_top_k,
            "reranker_batch_size": args.reranker_batch_size,
            "reranker_max_length": args.reranker_max_length,
            "reranker_doc_max_chars": args.reranker_doc_max_chars,
        },
        "metrics": {
            "case_count": len(scores),
            "passed": passed,
            "failed": failed,
            "pass_rate": passed / len(scores) if scores else 0.0,
            "total_tool_calls": sum(int(score.get("tool_call_count") or 0) for score in scores),
            "real_retrieval_required_cases": sum(1 for score in scores if score.get("real_retrieval_required")),
            "real_specialist_quality_required_cases": sum(1 for score in scores if score.get("real_specialist_quality_required")),
            "real_specialist_quality_passed": sum(
                1
                for score in scores
                if score.get("real_specialist_quality_required")
                and ((score.get("specialist_real_evidence_quality") or {}).get("quality_pass") is True)
            ),
            "failed_cases": [score["case_id"] for score in scores if score.get("gate_status") != "pass"],
        },
        "categories": categories,
        "cases": scores,
        "fixture_case_ids": [case.get("case_id") for case in cases],
    }


def _stdout_summary(summary: Mapping[str, Any], output_path: Path) -> dict[str, Any]:
    return {
        "run_id": summary.get("run_id"),
        "gate_status": summary.get("gate_status"),
        "diagnostic_only": summary.get("diagnostic_only"),
        "output_path": str(output_path.resolve()),
        "metrics": summary.get("metrics"),
        "failures": [
            {
                "case_id": case.get("case_id"),
                "category": case.get("category"),
                "execution_mode": case.get("execution_mode"),
                "expected_execution_mode": case.get("expected_execution_mode"),
                "checks": {key: value for key, value in (case.get("checks") or {}).items() if not value},
                "missing_required_agents": case.get("missing_required_agents"),
                "forbidden_activated_agents": case.get("forbidden_activated_agents"),
                "loop_break_reason": case.get("loop_break_reason"),
            }
            for case in summary.get("cases") or []
            if case.get("gate_status") != "pass"
        ],
    }


def _flatten_checks(layer_checks: Mapping[str, Any]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for layer_name, layer in layer_checks.items():
        if not isinstance(layer, Mapping):
            continue
        for check_name, value in layer.items():
            checks[f"{layer_name}.{check_name}"] = bool(value)
    return checks


def _route(routes: Mapping[str, Any], name: str) -> dict[str, Any]:
    value = routes.get(name) if isinstance(routes, Mapping) else {}
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _diag_call_count(route: Mapping[str, Any]) -> int:
    diagnostics = route.get("diagnostics") if isinstance(route.get("diagnostics"), Mapping) else route
    try:
        return int((diagnostics or {}).get("call_count") or 0)
    except (TypeError, ValueError):
        return 0


def _diag_calls_ok(route: Mapping[str, Any]) -> bool:
    diagnostics = route.get("diagnostics") if isinstance(route.get("diagnostics"), Mapping) else route
    if not diagnostics:
        return False
    return bool(diagnostics.get("all_calls_ok")) and int(diagnostics.get("direct_tool_call_count") or 0) == 0


def _tool_calls(result: Mapping[str, Any], summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    ledger = result.get("tool_call_ledger") if isinstance(result.get("tool_call_ledger"), Mapping) else {}
    records = [dict(item) for item in ledger.get("records") or [] if isinstance(item, Mapping)]
    if records:
        return records
    return [dict(item) for item in summary.get("tool_calls") or [] if isinstance(item, Mapping)]


def _runtime_summary(call: Mapping[str, Any]) -> dict[str, Any]:
    metadata = _tool_call_metadata(call)
    runtime = metadata.get("runtime_summary") if isinstance(metadata.get("runtime_summary"), Mapping) else {}
    if runtime:
        return dict(runtime)
    return dict(call.get("runtime_summary") or {}) if isinstance(call.get("runtime_summary"), Mapping) else {}


def _tool_call_metadata(call: Mapping[str, Any]) -> dict[str, Any]:
    return dict(call.get("metadata") or {}) if isinstance(call.get("metadata"), Mapping) else {}


def _positive_count(value: Any) -> bool:
    try:
        return int(value or 0) > 0
    except (TypeError, ValueError):
        return False


def _model_ref(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text:
        return ""
    if "/" in text and ":" in text[:4]:
        return text.rstrip("/").split("/")[-1]
    return text


def _specialist_route_results(result: Mapping[str, Any], summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    routes = [dict(item) for item in result.get("specialist_route_results") or [] if isinstance(item, Mapping)]
    if routes:
        return routes
    specialists = summary.get("specialists") if isinstance(summary.get("specialists"), Mapping) else {}
    return [dict(item) for item in specialists.get("route_results") or [] if isinstance(item, Mapping)]


def _previous_turn_summary(case: Mapping[str, Any], conversations: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    conversation_id = str(case.get("conversation_id") or "")
    turn_index = int(case.get("turn_index") or 0)
    if not conversation_id or turn_index <= 1:
        return {}
    return dict(conversations.get(conversation_id) or {})


def _update_conversation_summary(
    case: Mapping[str, Any],
    score: Mapping[str, Any],
    result: Mapping[str, Any],
    conversations: dict[str, dict[str, Any]],
) -> None:
    conversation_id = str(case.get("conversation_id") or "")
    if not conversation_id:
        return
    activation = result.get("agent_activation_plan") if isinstance(result.get("agent_activation_plan"), Mapping) else {}
    conversations[conversation_id] = {
        "previous_case_id": score.get("case_id"),
        "previous_execution_mode": score.get("execution_mode"),
        "previous_focus_tickers": list(activation.get("focus_tickers") or case.get("focus_tickers") or []),
        "previous_search_scope_tickers": list(activation.get("search_scope_tickers") or case.get("search_scope_tickers") or []),
        "previous_rendered_answer_preview": str(result.get("rendered_answer") or "")[:300],
        "previous_gate_status": score.get("gate_status"),
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def _default_run_id(args: argparse.Namespace) -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_multi_agent_real_llm_chain_{_safe_id(args.model)}_v0_1"


def _safe_id(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in str(value or "")).strip("_") or "model"


if __name__ == "__main__":
    raise SystemExit(main())
