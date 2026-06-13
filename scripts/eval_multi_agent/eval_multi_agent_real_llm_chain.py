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


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

from sec_agent.agent_registry import agent_registry_by_id  # noqa: E402
from sec_agent.multi_agent_contracts import validate_specialist_memolet  # noqa: E402
from sec_agent.multi_agent_runtime import build_agent_data_view, milvus_runtime_capability  # noqa: E402
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
DEFAULT_LEDGER_STORE = (
    REPO_ROOT
    / "data"
    / "processed_private"
    / "ledger"
    / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_core_ledger.duckdb"
)
DEFAULT_BGE_MODEL = Path("D:/hf_cache/hub/models--BAAI--bge-reranker-v2-m3/snapshots/953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e")
DEFAULT_MARKET_SNAPSHOT_ID = "20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1"
DEFAULT_MARKET_AS_OF_DATE = "2026-05-29"


def _path_env_or_default(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else default


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
    parser.add_argument("--memo-max-tokens", type=int, default=int(os.environ.get("MEMO_MAX_TOKENS", "3600")))
    parser.add_argument("--verifier-max-tokens", type=int, default=int(os.environ.get("VERIFIER_MAX_TOKENS", "1000")))
    parser.add_argument("--timeout-s", type=int, default=int(os.environ.get("MULTI_AGENT_REAL_CHAIN_TIMEOUT_S", "180")))
    parser.add_argument("--real-evidence-operators", action="store_true", help="Execute MCP/interactive retrieval instead of dry-run operator rows.")
    parser.add_argument("--manifest-path", type=Path, default=Path(os.environ.get("MANIFEST_PATH", str(DEFAULT_SECTOR_DEPTH_MANIFEST))))
    parser.add_argument("--bm25-index-dir", type=Path, default=Path(os.environ.get("BM25_INDEX_DIR", str(DEFAULT_SECTOR_DEPTH_BM25))))
    parser.add_argument("--object-bm25-index-dir", type=Path, default=Path(os.environ.get("OBJECT_BM25_INDEX_DIR", str(DEFAULT_SECTOR_DEPTH_OBJECT_BM25))))
    parser.add_argument("--market-evidence-path", type=Path, default=Path(os.environ.get("MARKET_EVIDENCE_PATH", str(DEFAULT_MARKET_EVIDENCE))))
    parser.add_argument("--industry-evidence-path", type=Path, default=Path(os.environ.get("INDUSTRY_EVIDENCE_PATH", str(DEFAULT_INDUSTRY_EVIDENCE))))
    parser.add_argument("--sector-depth-pack-path", type=Path, default=Path(os.environ.get("SECTOR_DEPTH_PACK_PATH", str(DEFAULT_SECTOR_DEPTH_PACK))))
    parser.add_argument("--ledger-store-path", type=Path, default=_path_env_or_default("LEDGER_STORE_PATH", DEFAULT_LEDGER_STORE))
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
    parser.add_argument("--summary-output-path", type=Path, default=None, help="Optional compact summary JSON for Workbench eval jobs.")
    parser.add_argument(
        "--run-audit-db-path",
        type=Path,
        default=Path(os.environ["RUN_AUDIT_DB_PATH"]) if os.environ.get("RUN_AUDIT_DB_PATH") else None,
        help="Optional SQLite run audit store. Redis remains coordination-only; this is the final audit source.",
    )
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
    if args.summary_output_path:
        _write_workbench_eval_summary(aggregate, args.summary_output_path, source_summary_path=summary_path)
    print(json.dumps(_stdout_summary(aggregate, summary_path), ensure_ascii=False, indent=2))
    if args.strict and aggregate["gate_status"] != "pass":
        return 1
    return 0


def _write_workbench_eval_summary(
    summary: Mapping[str, Any],
    output_path: Path,
    *,
    source_summary_path: Path,
) -> None:
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), Mapping) else {}
    case_count = int(metrics.get("case_count") or 0)
    pass_count = int(metrics.get("passed") or 0)
    failure_count = int(metrics.get("failed") or max(0, case_count - pass_count))
    payload = {
        "schema_version": "sec_agent_workbench_eval_summary_v0.1",
        "source_schema_version": summary.get("schema_version") or "",
        "run_id": summary.get("run_id") or "",
        "status": "pass" if summary.get("gate_status") == "pass" else "fail",
        "gate_status": summary.get("gate_status") or "",
        "diagnostic_only": bool(summary.get("diagnostic_only", True)),
        "case_count": case_count,
        "pass_count": pass_count,
        "failure_count": failure_count,
        "all_pass": summary.get("gate_status") == "pass" and case_count > 0,
        "failed_cases": list(metrics.get("failed_cases") or []),
        "source_summary_path": str(source_summary_path.resolve()),
        "output_dir": summary.get("output_dir") or "",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    activation_validation = result.get("agent_activation_validation") if isinstance(result.get("agent_activation_validation"), Mapping) else {}
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
    budgeted_tool_call_count = _budgeted_tool_call_count(tool_calls)
    activated_scope = set(_string_list(activation.get("focus_tickers")) + _string_list(activation.get("search_scope_tickers")))
    forbidden_scope_hits = sorted(activated_scope & set(_string_list(case.get("forbidden_scope_tickers"))))
    rendered_answer = str(result.get("rendered_answer") or "")
    memo_claim_count = len([row for row in memo.get("memo_claims") or [] if isinstance(row, Mapping)])
    expected_response_language = _expected_response_language(case)
    memo_response_language = _memo_response_language(memo)
    rendered_has_claim_section = _rendered_has_claim_section(rendered_answer)
    rendered_has_evidence_refs = _rendered_has_evidence_refs(rendered_answer)
    rendered_has_dimension_section = _rendered_has_dimension_section(rendered_answer)
    memo_dimension_analyses = [row for row in memo.get("dimension_analyses") or [] if isinstance(row, Mapping)]
    analyst_depth_gate = claim_verification.get("analyst_depth_gate") if isinstance(claim_verification.get("analyst_depth_gate"), Mapping) else {}
    thesis_driver_pack = (
        (result.get("verified_judgment_plan") or {}).get("thesis_driver_pack")
        if isinstance(result.get("verified_judgment_plan"), Mapping)
        else {}
    )
    if not isinstance(thesis_driver_pack, Mapping):
        thesis_driver_pack = {}
    vnext_contract = _vnext_contract_audit(case, result=result, summary=summary, tool_calls=tool_calls)
    run_audit = _run_audit_checks(case, result)
    analyst_depth = _analyst_depth_checks(
        case,
        memo_dimension_analyses=memo_dimension_analyses,
        analyst_depth_gate=analyst_depth_gate,
        rendered_has_dimension_section=rendered_has_dimension_section,
        thesis_driver_pack=thesis_driver_pack,
    )

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
            "tool_budget_lte": budgeted_tool_call_count <= max_tool_calls,
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
            "rendered_answer_has_memo_claims": rendered_has_claim_section if case.get("require_rendered_memo_claims") else True,
            "rendered_answer_has_evidence_refs": rendered_has_evidence_refs if case.get("require_rendered_evidence_refs") else True,
            "rendered_answer_has_dimension_section": rendered_has_dimension_section if case.get("require_dimension_memo_surface") else True,
            "response_language_matches_query": (
                memo_response_language == expected_response_language
                if case.get("require_response_language_match")
                else True
            ),
            "rendered_user_language_ok": (
                _rendered_user_language_ok(rendered_answer, expected_response_language)
                if case.get("require_response_language_match")
                else True
            ),
        },
        "payload_safety": {
            "raw_payload_not_in_summary": (summary.get("payload_policy") or {}).get("raw_evidence") == "not_included",
            "no_api_key_marker": "sk-" not in json.dumps(summary, ensure_ascii=False),
            "no_private_path_marker": "raw_private" not in json.dumps(summary, ensure_ascii=False),
        },
        "analyst_depth": analyst_depth["checks"],
        "run_audit": run_audit["checks"],
        "vnext_contract": vnext_contract["checks"],
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
        "budgeted_tool_call_count": budgeted_tool_call_count,
        "cached_tool_call_count": len(tool_calls) - budgeted_tool_call_count,
        "loop_break_reason": result.get("loop_break_reason") or "",
        "memo_status": memo_status,
        "memo_response_language": memo_response_language,
        "expected_response_language": expected_response_language,
        "memo_claim_count": memo_claim_count,
        "memo_dimension_analysis_count": len(memo_dimension_analyses),
        "analyst_depth_gate_status": analyst_depth_gate.get("status") or "",
        "rendered_answer_chars": len(rendered_answer),
        "rendered_answer_has_claim_section": rendered_has_claim_section,
        "rendered_answer_has_evidence_refs": rendered_has_evidence_refs,
        "rendered_answer_has_dimension_section": rendered_has_dimension_section,
        "claim_verification": claim_verification.get("status") or "",
        "specialist_verification": specialist_verification.get("status") or "",
        "universe_validation": universe_validation.get("status") or ("skipped" if "universe_relationship" not in active_agents else ""),
        "relationship_lookup_status": relationship_lookup.get("status") or "",
        "agent_activation_validation_errors": activation_validation.get("errors") or [],
        "research_lead_failure_reason": result.get("research_lead_failure_reason") or "",
        "research_lead_routing_trace": result.get("multi_agent_routing_trace") or {},
        "real_retrieval_required": real_retrieval_required,
        "real_specialist_quality_required": real_specialist_quality_required,
        "specialist_real_evidence_quality": specialist_quality,
        "analyst_depth_audit": analyst_depth,
        "run_audit": run_audit,
        "vnext_contract_audit": vnext_contract,
        "layer_checks": layer_checks,
        "checks": checks,
        "agent_audit": _agent_audit(result, summary, tool_calls=tool_calls, specialist_routes=specialist_routes, specialist_quality=specialist_quality),
        "node_trace": [row.get("node") for row in result.get("node_trace") or [] if isinstance(row, Mapping)],
        "summary_artifact_present": bool(summary),
        "native_summary_artifact_present": bool(native),
        "rendered_answer_preview": rendered_answer[:640],
    }


def _rendered_has_claim_section(rendered_answer: str) -> bool:
    text = str(rendered_answer or "")
    return "Key memo claims:" in text or "关键论据:" in text


def _rendered_has_evidence_refs(rendered_answer: str) -> bool:
    text = str(rendered_answer or "")
    return "refs=" in text or "证据=" in text


def _rendered_has_dimension_section(rendered_answer: str) -> bool:
    text = str(rendered_answer or "")
    return "Dimension analysis:" in text or "分维度分析:" in text


def _analyst_depth_checks(
    case: Mapping[str, Any],
    *,
    memo_dimension_analyses: list[Mapping[str, Any]],
    analyst_depth_gate: Mapping[str, Any],
    rendered_has_dimension_section: bool,
    thesis_driver_pack: Mapping[str, Any],
) -> dict[str, Any]:
    required = bool(case.get("require_dimension_memo_surface") or case.get("require_analyst_depth_gate"))
    required_dimension_ids = set(_string_list(case.get("required_dimension_ids")))
    memo_dimension_ids = {
        str(row.get("dimension_id") or "")
        for row in memo_dimension_analyses
        if str(row.get("dimension_id") or "").strip()
    }
    pack_dimension_ids = {
        str(row.get("dimension_id") or "")
        for row in thesis_driver_pack.get("dimension_sections") or []
        if isinstance(row, Mapping) and str(row.get("dimension_id") or "").strip()
    }
    traceable_count = 0
    for row in memo_dimension_analyses:
        summary = str(row.get("summary") or row.get("section_thesis") or "").strip()
        refs = _string_list(row.get("evidence_refs") or row.get("refs"))
        claim_ids = _string_list(row.get("claim_ids") or row.get("primary_claim_ids"))
        counter_claim_ids = _string_list(row.get("counter_claim_ids"))
        gap_ids = _string_list(row.get("gap_ids"))
        if summary and (refs or claim_ids or counter_claim_ids or gap_ids):
            traceable_count += 1
    checks = {
        "dimension_pack_present": bool(pack_dimension_ids) if required else True,
        "dimension_analyses_present": bool(memo_dimension_analyses) if required else True,
        "dimension_analyses_traceable": traceable_count >= min(2, len(memo_dimension_analyses)) if required else True,
        "rendered_dimension_section_present": rendered_has_dimension_section if case.get("require_dimension_memo_surface") else True,
        "analyst_depth_gate_pass": str(analyst_depth_gate.get("status") or "") == "pass" if case.get("require_analyst_depth_gate") else True,
        "required_dimensions_present": required_dimension_ids <= (memo_dimension_ids | pack_dimension_ids) if required_dimension_ids else True,
    }
    return {
        "schema_version": "sec_agent_analyst_depth_eval_audit_v0.1",
        "required": required,
        "memo_dimension_ids": sorted(memo_dimension_ids),
        "pack_dimension_ids": sorted(pack_dimension_ids),
        "required_dimension_ids": sorted(required_dimension_ids),
        "traceable_dimension_count": traceable_count,
        "analyst_depth_gate_status": analyst_depth_gate.get("status") or "",
        "checks": checks,
    }


def _run_audit_checks(case: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    report = (
        result.get("run_audit_materialization_report")
        if isinstance(result.get("run_audit_materialization_report"), Mapping)
        else {}
    )
    counts = report.get("table_counts") if isinstance(report.get("table_counts"), Mapping) else {}
    required = bool(case.get("require_run_audit_store"))
    required_tables = _string_list(case.get("required_run_audit_tables")) or [
        "run",
        "node_execution",
        "artifact_ref",
        "evidence_row",
        "claim_card",
        "gap",
        "gate_result",
        "model_call",
    ]
    nonempty_tables = _string_list(case.get("required_run_audit_nonempty_tables")) or [
        "run",
        "node_execution",
        "artifact_ref",
        "gate_result",
        "model_call",
    ]
    checks = {
        "run_audit_report_present": bool(report) if required else True,
        "run_audit_status_pass": str(report.get("status") or "") == "pass" if required else True,
        "required_tables_present": all(table in counts for table in required_tables) if required else True,
        "required_nonempty_tables_nonempty": all(int(counts.get(table) or 0) > 0 for table in nonempty_tables) if required else True,
        "redis_coordination_only": "redis_coordination_only" in str(report.get("run_audit_policy") or "").lower() if required else True,
    }
    return {
        "schema_version": "sec_agent_run_audit_eval_check_v0.1",
        "required": required,
        "db_path": report.get("db_path") or "",
        "table_counts": dict(counts),
        "required_tables": required_tables,
        "required_nonempty_tables": nonempty_tables,
        "checks": checks,
    }


def _budgeted_tool_call_count(tool_calls: list[Mapping[str, Any]]) -> int:
    non_budget_statuses = {"cached", "blocked", "skipped"}
    return sum(1 for call in tool_calls if str(call.get("status") or "").strip().lower() not in non_budget_statuses)


def _expected_response_language(case: Mapping[str, Any]) -> str:
    explicit = str(case.get("response_language") or case.get("output_language") or "").strip().lower().replace("_", "-")
    if explicit in {"zh", "zh-cn", "zh-hans", "chinese", "中文", "简体中文"}:
        return "zh-CN"
    if explicit in {"en", "en-us", "en-gb", "english", "英文"}:
        return "en-US"
    return "zh-CN" if re.search(r"[\u4e00-\u9fff]", str(case.get("prompt") or "")) else "en-US"


def _memo_response_language(memo: Mapping[str, Any]) -> str:
    value = memo.get("response_language")
    if isinstance(value, Mapping):
        value = value.get("language")
    normalized = str(value or "").strip().lower().replace("_", "-")
    if normalized in {"zh", "zh-cn", "zh-hans", "chinese", "中文", "简体中文"}:
        return "zh-CN"
    if normalized in {"en", "en-us", "en-gb", "english", "英文"}:
        return "en-US"
    return ""


def _rendered_user_language_ok(rendered_answer: str, expected_language: str) -> bool:
    if expected_language != "zh-CN":
        return True
    text = str(rendered_answer or "")
    if not text.strip():
        return False
    cjk_count = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin_text = re.sub(r"\b(?:[A-Z]{1,8}|10-[KQ]|8-K|GAAP|SEC|FY\d{2,4}|Q[1-4])\b", " ", text)
    latin_words = len(re.findall(r"[A-Za-z]{3,}", latin_text))
    return cjk_count >= 40 and cjk_count >= latin_words


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


def _vnext_contract_audit(
    case: Mapping[str, Any],
    *,
    result: Mapping[str, Any],
    summary: Mapping[str, Any],
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    required = bool(case.get("require_vnext_contract"))
    require_plan_reflection = required or bool(case.get("require_plan_reflection_gate"))
    require_fusion = required or bool(case.get("require_evidence_fusion_contract"))
    require_gap_register = required or bool(case.get("require_bounded_gap_register"))
    require_graph_barriers = required or bool(case.get("require_graph_barrier_contract"))
    require_milvus = required or bool(case.get("require_milvus_runtime_contract"))
    if not any((required, require_plan_reflection, require_fusion, require_gap_register, require_graph_barriers, require_milvus)):
        return {
            "required": False,
            "checks": {
                "plan_reflection_pass": True,
                "evidence_fusion_contract_present": True,
                "source_boundary_violation_absent": True,
                "bounded_gap_register_contract_present": True,
                "bounded_gaps_are_bounded_not_fallback": True,
                "graph_barrier_contract_present": True,
                "milvus_runtime_contract_present": True,
                "milvus_not_exact_value_authority": True,
                "private_runtime_handles_not_exposed": True,
                "weak_proxy_fallback_absent": True,
            },
            "details": {},
        }
    plan_reflection = summary.get("plan_reflection") if isinstance(summary.get("plan_reflection"), Mapping) else {}
    evidence_fusion = summary.get("evidence_fusion") if isinstance(summary.get("evidence_fusion"), Mapping) else {}
    bounded_gap_summary = summary.get("bounded_gap_register") if isinstance(summary.get("bounded_gap_register"), Mapping) else {}
    bounded_gap_register = result.get("bounded_gap_register") if isinstance(result.get("bounded_gap_register"), Mapping) else {}
    graph_barriers = summary.get("graph_barriers") if isinstance(summary.get("graph_barriers"), Mapping) else {}
    milvus_runtime = summary.get("milvus_runtime") if isinstance(summary.get("milvus_runtime"), Mapping) else {}
    checks = {
        "plan_reflection_pass": (not require_plan_reflection) or str(plan_reflection.get("status") or "") == "pass",
        "evidence_fusion_contract_present": (not require_fusion)
        or str(evidence_fusion.get("schema_version") or "") == "sec_agent_evidence_fusion_bundle_v0.1",
        "source_boundary_violation_absent": _source_boundary_violation_absent(evidence_fusion),
        "bounded_gap_register_contract_present": (not require_gap_register)
        or str(bounded_gap_summary.get("schema_version") or "") == "sec_agent_bounded_gap_register_v0.1",
        "bounded_gaps_are_bounded_not_fallback": _bounded_gaps_are_bounded_not_fallback(bounded_gap_register),
        "graph_barrier_contract_present": (not require_graph_barriers)
        or _graph_barrier_contract_present(case, result=result, graph_barriers=graph_barriers),
        "milvus_runtime_contract_present": (not require_milvus) or _milvus_runtime_contract_present(milvus_runtime),
        "milvus_not_exact_value_authority": _milvus_not_exact_value_authority(result, summary),
        "private_runtime_handles_not_exposed": _private_runtime_handles_not_exposed(summary),
        "weak_proxy_fallback_absent": _weak_proxy_fallback_absent(result=result, summary=summary, tool_calls=tool_calls),
    }
    return {
        "required": required,
        "checks": checks,
        "details": {
            "plan_reflection_status": plan_reflection.get("status") or "",
            "evidence_fusion_schema_version": evidence_fusion.get("schema_version") or "",
            "public_exact_authority_violation_count": evidence_fusion.get("public_exact_authority_violation_count") or 0,
            "semantic_exact_authority_violation_count": evidence_fusion.get("semantic_exact_authority_violation_count") or 0,
            "bounded_gap_count": bounded_gap_summary.get("gap_count") or 0,
            "milvus_runtime_status": milvus_runtime.get("status") or "",
            "milvus_runtime_location": milvus_runtime.get("location") or "",
            "milvus_runtime_claim_boundary": milvus_runtime.get("claim_boundary") or "",
            "graph_barrier_keys": sorted(graph_barriers.keys()),
            "tool_names": sorted({str(call.get("tool_name") or "") for call in tool_calls if str(call.get("tool_name") or "")}),
        },
    }


def _source_boundary_violation_absent(evidence_fusion: Mapping[str, Any]) -> bool:
    return (
        int(evidence_fusion.get("public_exact_authority_violation_count") or 0) == 0
        and int(evidence_fusion.get("semantic_exact_authority_violation_count") or 0) == 0
    )


def _bounded_gaps_are_bounded_not_fallback(register: Mapping[str, Any]) -> bool:
    gaps = [dict(row) for row in register.get("gaps") or [] if isinstance(row, Mapping)]
    if not gaps:
        return True
    for gap in gaps:
        boundary = str(gap.get("claim_boundary") or "").strip()
        if boundary != "do_not_fill_with_generic_fallback_or_proxy_fact":
            return False
        if str(gap.get("gap_type") or "").strip() in {"", "unknown"}:
            return False
        if str(gap.get("bounded_reason") or "").strip() == "":
            return False
    return True


def _graph_barrier_contract_present(
    case: Mapping[str, Any],
    *,
    result: Mapping[str, Any],
    graph_barriers: Mapping[str, Any],
) -> bool:
    if not isinstance(graph_barriers, Mapping) or not graph_barriers:
        return False
    execution_mode = str((result.get("agent_activation_plan") or {}).get("execution_mode") or case.get("expected_execution_mode") or "")
    specialist_expected = bool(_string_list(case.get("expected_specialist_agents")))
    memo_expected = "memo_writer" in set(_string_list(case.get("required_agents")))
    claim_barrier = graph_barriers.get("claim_card_store") if isinstance(graph_barriers.get("claim_card_store"), Mapping) else {}
    adjudicator = graph_barriers.get("adjudicator") if isinstance(graph_barriers.get("adjudicator"), Mapping) else {}
    specialist_barrier = graph_barriers.get("specialist_fanout") if isinstance(graph_barriers.get("specialist_fanout"), Mapping) else {}
    if specialist_expected and str(specialist_barrier.get("schema_version") or "") != "sec_agent_specialist_fanout_barrier_v0.1":
        return False
    if memo_expected or execution_mode in {"focused_answer", "standard_memo", "deep_research"}:
        if str(claim_barrier.get("schema_version") or "") != "sec_agent_claim_card_store_barrier_v0.1":
            return False
        if str(adjudicator.get("schema_version") or "") != "sec_agent_adjudicator_barrier_v0.1":
            return False
    return True


def _milvus_runtime_contract_present(milvus_runtime: Mapping[str, Any]) -> bool:
    status = str(milvus_runtime.get("status") or "").strip()
    location = str(milvus_runtime.get("location") or "").strip()
    boundary = str(milvus_runtime.get("claim_boundary") or "").strip()
    if status not in {"cloud_available", "local_available", "unavailable"}:
        return False
    if location not in {"cloud", "local", "none"}:
        return False
    if boundary != "semantic_recall_supplement_not_exact_value_authority":
        return False
    return bool(milvus_runtime.get("fallback_routes"))


def _milvus_not_exact_value_authority(result: Mapping[str, Any], summary: Mapping[str, Any]) -> bool:
    evidence_fusion = summary.get("evidence_fusion") if isinstance(summary.get("evidence_fusion"), Mapping) else {}
    if int(evidence_fusion.get("semantic_exact_authority_violation_count") or 0) != 0:
        return False
    containers = [
        result.get("context_rows"),
        result.get("runtime_ledger_rows"),
        result.get("market_snapshot_rows"),
        result.get("industry_snapshot_rows"),
        (result.get("evidence_fusion_bundle") or {}).get("rows") if isinstance(result.get("evidence_fusion_bundle"), Mapping) else [],
    ]
    for rows in containers:
        for row in rows or []:
            if not isinstance(row, Mapping):
                continue
            if str(row.get("source_family") or "") == "milvus_semantic" and bool(row.get("exact_value_authority")):
                return False
    for output in result.get("specialist_outputs") or []:
        if not isinstance(output, Mapping):
            continue
        for observation in output.get("observations") or []:
            if not isinstance(observation, Mapping):
                continue
            source_families = {str(item) for item in observation.get("source_families") or []}
            claim_type = str(observation.get("claim_type") or "")
            if "milvus_semantic" in source_families and claim_type in {"exact_value", "product_revenue", "financial_metric"}:
                return False
    return True


def _private_runtime_handles_not_exposed(summary: Mapping[str, Any]) -> bool:
    text = json.dumps(summary, ensure_ascii=False).lower()
    private_markers = (
        "milvus_uri",
        "zilliz_uri",
        "milvus_db_path",
        "api_key",
        "password",
        "bearer ",
        "raw_private",
    )
    return not any(marker in text for marker in private_markers)


def _weak_proxy_fallback_absent(
    *,
    result: Mapping[str, Any],
    summary: Mapping[str, Any],
    tool_calls: list[dict[str, Any]],
) -> bool:
    text = json.dumps(
        {
            "summary_evidence_fusion": summary.get("evidence_fusion"),
            "summary_bounded_gaps": summary.get("bounded_gap_register"),
            "tool_calls": tool_calls,
            "specialist_outputs": result.get("specialist_outputs"),
            "memo_claims": (result.get("memo_answer") or {}).get("memo_claims")
            if isinstance(result.get("memo_answer"), Mapping)
            else [],
        },
        ensure_ascii=False,
    ).lower()
    blocked_markers = ("weak_proxy_fallback", "generic_proxy_fallback", "proxy_as_fact")
    return not any(marker in text for marker in blocked_markers)


def _case_requires_milvus_runtime_contract(case: Mapping[str, Any]) -> bool:
    if case.get("require_vnext_contract") or case.get("require_milvus_runtime_contract"):
        return True
    return "milvus_semantic" in set(_string_list(case.get("expected_tool_names")))


def _milvus_runtime_context_from_env(case: Mapping[str, Any]) -> dict[str, Any]:
    runtime = case.get("milvus_runtime") if isinstance(case.get("milvus_runtime"), Mapping) else {}
    context = {
        "milvus_runtime": dict(runtime),
        "milvus_uri": os.environ.get("MILVUS_URI") or os.environ.get("ZILLIZ_URI") or "",
        "milvus_db_path": os.environ.get("MILVUS_DB_PATH") or "",
        "milvus_collection_name": os.environ.get("MILVUS_COLLECTION_NAME")
        or os.environ.get("MILVUS_COLLECTION")
        or str(runtime.get("collection") or ""),
    }
    return context


def _public_milvus_runtime_for_eval(capability: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": str(capability.get("schema_version") or "sec_agent_milvus_runtime_capability_v0.1"),
        "status": str(capability.get("status") or "unavailable"),
        "available": bool(capability.get("available")),
        "location": str(capability.get("location") or "none"),
        "collection": str(capability.get("collection") or ""),
        "vector_count": capability.get("vector_count"),
        "as_of_date": str(capability.get("as_of_date") or ""),
        "schema_digest": str(capability.get("schema_digest") or ""),
        "vector_kinds": list(capability.get("vector_kinds") or []),
        "fallback_routes": list(capability.get("fallback_routes") or []),
        "claim_boundary": str(capability.get("claim_boundary") or "semantic_recall_supplement_not_exact_value_authority"),
        "exact_value_authority": False,
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
            "LEDGER_STORE_PATH": str(args.ledger_store_path),
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
    state["case_id"] = str(case.get("case_id") or "")
    if args.run_audit_db_path:
        state["run_audit_db_path"] = str(args.run_audit_db_path)
    inventory_companies = _string_list(case.get("source_inventory_companies"))
    project_inventory: dict[str, Any] = {
        "source_families": _string_list(case.get("source_tiers")),
        "evaluation_inventory": "summary_only_no_private_paths",
    }
    if inventory_companies:
        project_inventory["companies"] = [{"ticker": ticker} for ticker in inventory_companies]
    if _case_requires_milvus_runtime_contract(case):
        milvus_context = _milvus_runtime_context_from_env(case)
        capability = milvus_runtime_capability({"project_inventory": project_inventory, **milvus_context})
        project_inventory["milvus_runtime"] = _public_milvus_runtime_for_eval(capability)
    state["project_inventory"] = project_inventory
    response_language = str(case.get("response_language") or case.get("output_language") or "").strip()
    if response_language:
        state["response_language"] = response_language
    context = {
        "evidence_operator_mode": "real" if args.real_evidence_operators else "dry_run",
        "build_runtime_ledger": bool(args.real_evidence_operators),
        "manifest_path": str(args.manifest_path),
        "bm25_index_dir": str(args.bm25_index_dir),
        "object_bm25_index_dir": str(args.object_bm25_index_dir),
        "market_evidence_path": str(args.market_evidence_path),
        "industry_evidence_path": str(args.industry_evidence_path),
        "sector_depth_pack_path": str(case.get("sector_depth_pack_path") or args.sector_depth_pack_path),
        "ledger_store_path": str(args.ledger_store_path) if args.ledger_store_path else "",
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
    if args.run_audit_db_path:
        context["run_audit_db_path"] = str(args.run_audit_db_path)
    if _case_requires_milvus_runtime_contract(case):
        context.update(_milvus_runtime_context_from_env(case))
        context["milvus_runtime"] = project_inventory.get("milvus_runtime") or {}
    if response_language:
        context["response_language"] = response_language
    state["multi_agent_context"] = context
    return state


def _query_contract(case: Mapping[str, Any]) -> dict[str, Any]:
    tickers = _string_list(case.get("search_scope_tickers"))
    focus = _string_list(case.get("focus_tickers")) or tickers[:2]
    source_tiers = _string_list(case.get("source_tiers")) or ["primary_sec_filing"]
    metric_families = _string_list(case.get("metric_families")) or ["revenue", "capex", "margin"]
    required_dimension_ids = _string_list(case.get("required_dimension_ids"))
    return {
        "task_type": "open_analysis",
        "search_scope_tickers": tickers,
        "focus_tickers": focus,
        "years": [int(year) for year in (case.get("years") or [2026])],
        "filing_types": _string_list(case.get("filing_types")) or ["10-Q", "8-K"],
        "source_tiers": source_tiers,
        "metric_families": metric_families,
        "required_dimension_ids": required_dimension_ids,
        "decomposed_tasks": [
            {
                "task_id": f"{case.get('case_id')}_primary",
                "question_zh": str(case.get("prompt") or "")[:160],
                "priority": "primary",
                "required_tickers": tickers or focus,
                "required_metric_families": metric_families,
                "required_dimension_ids": required_dimension_ids,
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
    exact_lookup_mode = str(case.get("expected_execution_mode") or "") == "deterministic_lookup"
    runtime_ledger_required = bool(case.get("require_runtime_ledger_rows"))
    exact_ledger_satisfies_sec = exact_lookup_mode and runtime_ledger_required and bool(result.get("runtime_ledger_rows"))
    sec_expected = "sec_search_filings" in expected_tools and not exact_ledger_satisfies_sec
    market_expected = "market_get_snapshot" in expected_tools
    industry_expected = "industry_get_snapshot" in expected_tools
    relationship_expected = "relationship_graph_lookup" in expected_tools
    sec_calls = [call for call in tool_calls if call.get("tool_name") == "sec_search_filings"]
    sec_success_calls = [call for call in sec_calls if str(call.get("status") or "") not in {"dry_run", "error"}]
    sec_runtime = [_runtime_summary(call) for call in sec_calls]
    candidate_counts = [item.get("candidate_counts") or {} for item in sec_runtime if isinstance(item, Mapping)]
    ledger_first_structured = _ledger_first_structured_route_present(candidate_counts)
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
        "sec_search_bge_rerank_present": (not sec_expected)
        or any(_positive_count(counts.get("candidate_sent_to_bge")) for counts in candidate_counts)
        or (runtime_ledger_required and ledger_first_structured and bool(result.get("runtime_ledger_rows")))
        or exact_ledger_satisfies_sec,
        "sec_search_runtime_ledger_rows_present": (not runtime_ledger_required) or bool(result.get("runtime_ledger_rows")),
        "market_rows_present": (not market_expected) or bool(result.get("market_snapshot_rows")),
        "industry_rows_present": (not industry_expected) or bool(result.get("industry_snapshot_rows")),
        "relationship_lookup_rows_present": (not relationship_expected) or bool((result.get("relationship_graph_observation") or {}).get("relationships")),
    }


def _ledger_first_structured_route_present(candidate_counts: list[Mapping[str, Any]]) -> bool:
    for counts in candidate_counts:
        for stat in counts.get("route_candidate_stats") or []:
            if not isinstance(stat, Mapping):
                continue
            if str(stat.get("retrieval_route") or "") == "ledger_first" and _positive_count(stat.get("candidate_count")):
                return True
    return False


def _specialist_real_evidence_quality(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
    required_specialists: set[str],
    *,
    required: bool,
) -> dict[str, Any]:
    route_results = _specialist_route_results(result, {})
    route_status_by_agent = {str(row.get("agent_id") or ""): str(row.get("status") or "") for row in route_results}
    route_by_agent = {
        str(row.get("agent_id") or ""): dict(row)
        for row in route_results
        if isinstance(row, Mapping)
    }
    memolets = {
        str(row.get("agent_id") or ""): dict(row)
        for row in result.get("specialist_outputs") or []
        if isinstance(row, Mapping)
    }
    details: dict[str, dict[str, Any]] = {}
    for agent_id in sorted(required_specialists):
        data_view = build_agent_data_view(agent_id, result)
        rows = [dict(row) for row in data_view.get("bounded_evidence_rows") or [] if isinstance(row, Mapping)]
        known_refs = _known_row_refs(rows)
        row_by_ref = _row_by_known_ref(rows)
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
        route_row = route_by_agent.get(agent_id) or {}
        comparative_primary_gate_required = _comparative_primary_gate_required(case, agent_id)
        comparative_primary_gate = _comparative_primary_visibility_gate(case, rows, result)
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
            "bounded_rows_not_dry_run_placeholders": _bounded_rows_not_dry_run_placeholders(rows),
            "bounded_row_source_family_owned": bool(row_source_families) and row_source_families <= allowed_sources,
            "observation_refs_known": observed_refs <= known_refs,
            "observation_source_family_owned": (not observed_sources) or observed_sources <= allowed_sources,
            "temporal_claim_ref_depth_valid": _temporal_claim_ref_depth_valid(observations, row_by_ref=row_by_ref),
            "prompt_row_distribution_present": _prompt_row_distribution_present(route_row),
            "comparative_focus_ticker_primary_visible_or_gap": (not comparative_primary_gate_required)
            or comparative_primary_gate["status"],
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
            "temporal_claim_ref_depth_failures": _temporal_claim_ref_depth_failures(observations, row_by_ref=row_by_ref),
            "relationship_gate_required": relationship_gate_required,
            "comparative_primary_gate_required": comparative_primary_gate_required,
            "focus_ticker_primary_visible": comparative_primary_gate["visible_tickers"],
            "focus_ticker_primary_source_gaps": comparative_primary_gate["gap_tickers"],
            "focus_ticker_primary_missing": comparative_primary_gate["missing_tickers"],
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
    if agent_id == "product_technology_analyst":
        return {"company_product_evidence_graph", "public_source_context", "live_public_web_context"}
    if agent_id == "risk_counterevidence_analyst":
        return {
            "primary_sec_filing",
            "company_authored_unaudited_sec_filing",
            "market_snapshot",
            "industry_snapshot",
            "relationship_graph",
            "company_product_evidence_graph",
            "public_source_context",
            "live_public_web_context",
            "run_artifact",
        }
    return {
        "primary_sec_filing",
        "company_authored_unaudited_sec_filing",
        "market_snapshot",
        "industry_snapshot",
        "relationship_graph",
        "company_product_evidence_graph",
        "public_source_context",
        "live_public_web_context",
    }


def _known_row_refs(rows: list[Mapping[str, Any]]) -> set[str]:
    return {ref for row in rows for ref in _row_ref_candidates(row)}


def _row_by_known_ref(rows: list[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        for ref in _row_ref_candidates(row):
            index.setdefault(ref, row)
    return index


def _row_ref_candidates(row: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("evidence_ref", "evidence_id", "ref_id", "id", "metric_id", "source_evidence_id", "object_id", "source_id"):
        value = str(row.get(key) or "").strip()
        if value and value not in refs:
            refs.append(value)
    return refs


def _bounded_rows_not_dry_run_placeholders(rows: list[Mapping[str, Any]]) -> bool:
    for row in rows:
        ref = str(row.get("evidence_ref") or "").strip()
        if not ref.startswith("bounded_row_"):
            continue
        if _bounded_row_has_real_evidence_fields(row):
            continue
        return False
    return True


def _bounded_row_has_real_evidence_fields(row: Mapping[str, Any]) -> bool:
    source_family = str(row.get("source_family") or "").strip()
    if source_family not in {
        "primary_sec_filing",
        "company_authored_unaudited_sec_filing",
        "market_snapshot",
        "industry_snapshot",
        "relationship_graph",
        "company_product_evidence_graph",
        "public_source_context",
        "live_public_web_context",
        "run_artifact",
    }:
        return False
    return any(
        str(row.get(key) or "").strip()
        for key in (
            "ticker",
            "related_ticker",
            "form_type",
            "metric",
            "metric_name",
            "metric_family",
            "product",
            "product_name",
            "source_url",
            "snapshot_url",
            "summary",
            "snapshot_id",
            "as_of_date",
            "edge_id",
        )
    )


def _prompt_row_distribution_present(route_row: Mapping[str, Any]) -> bool:
    distribution = route_row.get("prompt_row_distribution") if isinstance(route_row.get("prompt_row_distribution"), Mapping) else {}
    if not distribution:
        return False
    return bool(distribution.get("by_ticker") or distribution.get("by_source_family"))


def _temporal_claim_ref_depth_valid(
    observations: list[Mapping[str, Any]],
    *,
    row_by_ref: Mapping[str, Mapping[str, Any]],
) -> bool:
    return not _temporal_claim_ref_depth_failures(observations, row_by_ref=row_by_ref)


def _temporal_claim_ref_depth_failures(
    observations: list[Mapping[str, Any]],
    *,
    row_by_ref: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for observation in observations:
        if observation.get("unsupported"):
            continue
        claim = str(observation.get("claim") or "")
        if not _looks_like_temporal_inference(claim):
            continue
        refs = [str(ref) for ref in observation.get("evidence_refs") or [] if str(ref or "").strip()]
        if len(refs) >= 2:
            continue
        if _single_ref_temporal_claim_supported_by_row(refs, row_by_ref):
            continue
        failures.append(
            {
                "claim": claim[:240],
                "evidence_ref_count": len(refs),
                "reason": "temporal_or_trend_inference_requires_at_least_two_relevant_period_refs",
            }
        )
    return failures


def _single_ref_temporal_claim_supported_by_row(
    refs: list[str],
    row_by_ref: Mapping[str, Mapping[str, Any]],
) -> bool:
    if len(refs) != 1:
        return False
    row = row_by_ref.get(refs[0]) or {}
    text = " ".join(
        str(row.get(key) or "").lower()
        for key in (
            "summary",
            "text",
            "preview",
            "metric",
            "metric_name",
            "metric_family",
            "value",
            "raw_value_text",
            "display_value_zh",
            "period_role",
            "source_statement",
        )
    )
    if not text:
        return False
    comparative_markers = (
        "higher than",
        "lower than",
        "compared with",
        "compared to",
        "versus",
        " vs ",
        "year-over-year",
        "year over year",
        "yoy",
        "quarter-over-quarter",
        "quarter over quarter",
        "qoq",
        "increased",
        "decreased",
        "grew",
        "declined",
        "rose",
        "fell",
        "up ",
        "down ",
        "增加",
        "增长",
        "上升",
        "下降",
        "减少",
        "同比",
        "环比",
        "较",
        "高于",
        "低于",
    )
    if not any(marker in text for marker in comparative_markers):
        return False
    return (
        len(re.findall(r"\b20\d{2}\b", text)) >= 2
        or "%" in text
        or "percent" in text
        or any(marker in text for marker in ("同比", "环比", "yoy", "qoq"))
    )


def _looks_like_temporal_inference(claim: str) -> bool:
    text = claim.lower()
    patterns = (
        "sequential",
        "prior quarter",
        "prior period",
        "previous quarter",
        "previous period",
        "year-over-year",
        "year over year",
        "quarter-over-quarter",
        "quarter over quarter",
        "yoy",
        "qoq",
        "grew from",
        "declined from",
        "increased from",
        "decreased from",
        "acceleration",
        "deceleration",
        "trajectory",
    )
    return any(pattern in text for pattern in patterns)


def _comparative_primary_gate_required(case: Mapping[str, Any], agent_id: str) -> bool:
    if agent_id not in {"fundamental_analyst", "risk_counterevidence_analyst"}:
        return False
    return len(_focus_tickers_from_case(case)) >= 2


def _comparative_primary_visibility_gate(
    case: Mapping[str, Any],
    rows: list[Mapping[str, Any]],
    result: Mapping[str, Any],
) -> dict[str, Any]:
    focus = set(_focus_tickers_from_case(case))
    if len(focus) < 2:
        return {"status": True, "visible_tickers": sorted(focus), "gap_tickers": [], "missing_tickers": []}
    visible = {
        str(row.get("ticker") or "").upper()
        for row in rows
        if str(row.get("source_family") or "") in {"", "primary_sec_filing", "company_authored_unaudited_sec_filing"}
        and str(row.get("ticker") or "").strip()
    }
    gap_tickers = {
        str(gap.get("ticker") or "").upper()
        for gap in result.get("source_gaps") or []
        if isinstance(gap, Mapping)
        and str(gap.get("source_family") or "") == "primary_sec_filing"
        and str(gap.get("reason_code") or gap.get("quality_gap_type") or "")
    }
    covered = visible | gap_tickers
    missing = sorted(focus - covered)
    return {
        "status": not missing,
        "visible_tickers": sorted(visible & focus),
        "gap_tickers": sorted(gap_tickers & focus),
        "missing_tickers": missing,
    }


def _focus_tickers_from_case(case: Mapping[str, Any]) -> list[str]:
    activation = case.get("activation_plan") if isinstance(case.get("activation_plan"), Mapping) else {}
    focus = case.get("focus_tickers") or activation.get("focus_tickers")
    if not focus and isinstance(case.get("query_contract"), Mapping):
        focus = case.get("query_contract", {}).get("focus_tickers")
    return _unique_upper(focus)


def _unique_upper(value: Any) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in _string_list(value):
        ticker = str(item or "").upper().strip()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        result.append(ticker)
    return result


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
    route_result = route.get("route_result") if isinstance(route.get("route_result"), Mapping) else {}
    if route_result:
        return str(route_result.get("status") or "") == "pass"
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
            "route_status": result.get("research_lead_route_status")
            or _route(llm_routes, "research_lead").get("route_status")
            or "",
            "failure_reason": result.get("research_lead_failure_reason")
            or _route(llm_routes, "research_lead").get("failure_reason")
            or "",
            "validation_errors": (result.get("research_lead_validation") or {}).get("errors") or [],
            "validation_status": (result.get("agent_activation_validation") or {}).get("status")
            if isinstance(result.get("agent_activation_validation"), Mapping)
            else "",
            "execution_mode": (result.get("agent_activation_plan") or {}).get("execution_mode")
            if isinstance(result.get("agent_activation_plan"), Mapping)
            else "",
            "diagnostics": _route(llm_routes, "research_lead").get("diagnostics") or result.get("research_lead_model_diagnostics") or {},
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
            "input_projection": (result.get("claim_verification") or {}).get("verifier_input_projection")
            if isinstance(result.get("claim_verification"), Mapping)
            else {},
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
