from __future__ import annotations

import argparse
import hashlib
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
from sec_agent.agent_information_economy import (  # noqa: E402
    build_agent_information_economy_summary,
    build_preflight_information_economy,
)
from sec_agent.data_script_quality_audit import (  # noqa: E402
    build_data_script_quality_summary,
    render_data_script_quality_markdown,
)
from sec_agent.eval_case_catalog import expand_case_catalog, load_case_catalog  # noqa: E402
from sec_agent.multi_agent_contracts import validate_specialist_memolet  # noqa: E402
from sec_agent.multi_agent_runtime import build_agent_data_view, milvus_runtime_capability  # noqa: E402
from sec_agent.langgraph_orchestrator import (  # noqa: E402
    build_multi_agent_orchestration_graph_from_env,
    make_multi_agent_smoke_state,
    multi_agent_node_order,
)
from sec_agent.llm_gateway import chat_completion  # noqa: E402
from sec_agent.project_os_preflight import (  # noqa: E402
    compact_preflight_stdout as compact_project_os_preflight_stdout,
    run_project_os_preflight,
)


DEFAULT_CASES_PATH = REPO_ROOT / "tests" / "fixtures" / "multi_agent_real_llm_chain_cases_v0_1.jsonl"
DEFAULT_CASE_CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "fin_agent_vnext_50_case_catalog_v0_1.json"
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


def _int_env_or_default(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _path_env_or_default(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else default


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real-LLM multi-agent full-chain diagnostics.")
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument(
        "--case-catalog-path",
        type=Path,
        default=None,
        help="Optional vNext case catalog JSON. When set, cases are expanded from the catalog instead of --cases-path.",
    )
    parser.add_argument("--case-subset", default="", help="Optional release subset id inside --case-catalog-path.")
    parser.add_argument("--case-family", action="append", default=[], help="Optional catalog case_family filter. Repeatable.")
    parser.add_argument("--dump-expanded-cases-path", type=Path, default=None, help="Write resolved cases as JSONL before running.")
    parser.add_argument("--dry-run-cases", action="store_true", help="Resolve cases and exit without invoking the graph.")
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
    parser.add_argument("--research-lead-max-tokens", type=int, default=int(os.environ.get("RESEARCH_LEAD_MAX_TOKENS", "2200")))
    parser.add_argument("--specialist-max-tokens", type=int, default=int(os.environ.get("SPECIALIST_MAX_TOKENS", "1600")))
    parser.add_argument("--universe-max-tokens", type=int, default=int(os.environ.get("UNIVERSE_MAX_TOKENS", "500")))
    parser.add_argument("--memo-max-tokens", type=int, default=int(os.environ.get("MEMO_MAX_TOKENS", "3000")))
    parser.add_argument("--verifier-max-tokens", type=int, default=int(os.environ.get("VERIFIER_MAX_TOKENS", "800")))
    parser.add_argument("--timeout-s", type=int, default=int(os.environ.get("MULTI_AGENT_REAL_CHAIN_TIMEOUT_S", "180")))
    parser.add_argument(
        "--universe-timeout-s",
        type=int,
        default=int(os.environ.get("UNIVERSE_TIMEOUT_S", "90")),
        help="Independent hard timeout budget for the relationship mechanism-overlay node.",
    )
    parser.add_argument(
        "--universe-llm-overlay",
        action="store_true",
        default=str(os.environ.get("UNIVERSE_LLM_OVERLAY") or "").strip().lower() in {"1", "true", "yes"},
        help=(
            "Allow the universe relationship node to call the model for a short economic-mechanism overlay. "
            "Default keeps relationship edge completion deterministic so graph facts stay program-owned."
        ),
    )
    parser.add_argument(
        "--llm-gateway-proxy-mode",
        default=os.environ.get("LLM_GATEWAY_PROXY_MODE", "auto"),
        help="Transport proxy mode for model calls. auto defaults to direct; use system/explicit only when a proxy is intentionally required.",
    )
    parser.add_argument(
        "--skip-provider-preflight",
        action="store_true",
        help="Skip tiny provider connectivity/auth preflight before paid full-chain execution.",
    )
    parser.add_argument(
        "--provider-preflight-only",
        action="store_true",
        help="Run token budget and provider connectivity/auth preflight, then exit before graph execution.",
    )
    parser.add_argument(
        "--provider-preflight-timeout-s",
        type=int,
        default=int(os.environ.get("PROVIDER_PREFLIGHT_TIMEOUT_S", "45")),
        help="Timeout for the tiny provider preflight call.",
    )
    parser.add_argument("--allow-expensive-llm", action="store_true", help="Permit paid full-chain runs that exceed the preflight token budget.")
    parser.add_argument(
        "--project-os-preflight-only",
        action="store_true",
        help="Run Project OS full-chain blocker preflight and exit before token/provider/model checks.",
    )
    parser.add_argument(
        "--skip-project-os-preflight",
        action="store_true",
        help="Skip Project OS preflight. Intended only for deterministic unit tests or explicitly approved diagnostics.",
    )
    parser.add_argument(
        "--project-os-preflight-allow-open-blockers",
        action="store_true",
        help="Allow an explicitly diagnostic run to continue despite open Project OS full-chain blockers.",
    )
    parser.add_argument(
        "--project-os-run-scope",
        default=os.environ.get("PROJECT_OS_RUN_SCOPE", "broad_full_chain"),
        help=(
            "Project OS blocker scope. Use broad_full_chain by default; controlled single-case evals "
            "can pass a narrower scope such as p33_single_gold_case when root-cause rows allow it."
        ),
    )
    parser.add_argument(
        "--token-budget-preflight-only",
        action="store_true",
        help="Resolve cases, write token_budget_plan.json, and exit before graph/model execution.",
    )
    parser.add_argument(
        "--token-budget-total",
        type=int,
        default=int(os.environ.get("REAL_CHAIN_TOKEN_BUDGET_TOTAL", "180000")),
        help="Estimated total-token ceiling for paid full-chain runs before any model call.",
    )
    parser.add_argument(
        "--token-budget-per-case",
        type=int,
        default=int(os.environ.get("REAL_CHAIN_TOKEN_BUDGET_PER_CASE", "120000")),
        help="Estimated per-case token ceiling for paid full-chain runs before any model call.",
    )
    parser.add_argument(
        "--max-paid-calls",
        type=int,
        default=int(os.environ.get("REAL_CHAIN_MAX_PAID_CALLS", "8")),
        help="Estimated paid model-call ceiling for a run before any model call.",
    )
    parser.add_argument("--token-budget-plan-path", type=Path, default=None, help="Optional explicit token budget plan JSON path.")
    parser.add_argument(
        "--ignore-output-cost-quality",
        action="store_true",
        help="Do not fail the aggregate gate on post-run token-efficiency and claim-yield quality flags.",
    )
    parser.add_argument("--real-evidence-operators", action="store_true", help="Execute MCP/interactive retrieval instead of dry-run operator rows.")
    parser.add_argument(
        "--stop-after-node",
        default=os.environ.get("MULTI_AGENT_STOP_AFTER_NODE", ""),
        choices=["", *multi_agent_node_order()],
        help=(
            "Stop the LangGraph run after a specific multi-agent node and write node checkpoint/native summary artifacts. "
            "Use this for stepwise P33 review instead of running the whole chain."
        ),
    )
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
    parser.add_argument(
        "--evidence-operator-fanout-workers",
        type=int,
        default=_int_env_or_default("SEC_AGENT_EVIDENCE_OPERATOR_FANOUT_WORKERS", 0),
        help=(
            "Max parallel evidence-operator shards. 0 uses a resource-aware default: "
            "local CUDA/in-process runs serialize BGE-backed shards; CPU/subprocess/cloud profiles keep wider fanout."
        ),
    )
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
    cases = [_case_with_runtime_paid_specialists(case) for case in _load_cases(args)]
    run_id = args.run_id or _default_run_id(args)
    output_dir = args.output_dir / run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    gateway_event_log_path = output_dir / "model_call_events.jsonl"
    setattr(args, "_llm_gateway_event_log_path", str(gateway_event_log_path))
    os.environ["LLM_GATEWAY_EVENT_LOG_PATH"] = str(gateway_event_log_path)
    os.environ["LLM_GATEWAY_PROXY_MODE"] = _resolved_llm_gateway_proxy_mode(args)
    if args.dump_expanded_cases_path:
        args.dump_expanded_cases_path.parent.mkdir(parents=True, exist_ok=True)
        _write_jsonl(args.dump_expanded_cases_path, cases)
    if args.dry_run_cases:
        summary = _dry_run_case_summary(args=args, cases=cases, run_id=run_id, output_dir=output_dir)
        if args.summary_output_path:
            args.summary_output_path.parent.mkdir(parents=True, exist_ok=True)
            args.summary_output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
        return 0

    if args.project_os_preflight_only:
        project_os_preflight = _write_project_os_preflight(args=args, run_id=run_id, output_dir=output_dir)
        print(json.dumps(compact_project_os_preflight_stdout(project_os_preflight), ensure_ascii=False, indent=2), flush=True)
        return 0 if project_os_preflight.get("status") in {"pass", "diagnostic_override", "skipped"} else 4

    budget_plan = _write_token_budget_plan(args=args, cases=cases, run_id=run_id, output_dir=output_dir)
    _write_preflight_information_economy(budget_plan, output_dir)
    setattr(args, "_token_budget_plan", budget_plan)
    if args.token_budget_preflight_only:
        print(json.dumps(_token_budget_stdout_summary(budget_plan), ensure_ascii=False, indent=2), flush=True)
        return 0
    if not budget_plan["allowed"]:
        print(json.dumps(_token_budget_stdout_summary(budget_plan), ensure_ascii=False, indent=2), flush=True)
        return 2
    if not args.provider_preflight_only:
        project_os_preflight = _write_project_os_preflight(args=args, run_id=run_id, output_dir=output_dir)
        setattr(args, "_project_os_preflight", project_os_preflight)
        if project_os_preflight.get("status") not in {"pass", "diagnostic_override", "skipped"}:
            print(json.dumps(compact_project_os_preflight_stdout(project_os_preflight), ensure_ascii=False, indent=2), flush=True)
            return 4
    provider_preflight = _write_provider_preflight(args=args, run_id=run_id, output_dir=output_dir)
    setattr(args, "_provider_preflight", provider_preflight)
    if args.provider_preflight_only:
        print(json.dumps(_provider_preflight_stdout_summary(provider_preflight), ensure_ascii=False, indent=2), flush=True)
        return 0 if provider_preflight.get("status") in {"ok", "skipped"} else 3
    if provider_preflight.get("status") not in {"ok", "skipped"}:
        print(json.dumps(_provider_preflight_stdout_summary(provider_preflight), ensure_ascii=False, indent=2), flush=True)
        return 3

    env = _graph_env(args)
    graph = build_multi_agent_orchestration_graph_from_env(
        env=env,
        use_checkpointer=False,
        stop_after_node=(args.stop_after_node or None),
    )
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
        case_for_score = {**dict(case), "_universe_llm_overlay_required": bool(args.universe_llm_overlay)}
        score = score_case(case_for_score, result, summary, native, elapsed_ms=elapsed_ms, ordinal=ordinal, total=len(cases))
        if args.stop_after_node:
            score["stepwise_node_run"] = {
                "enabled": True,
                "requested_stop_after_node": args.stop_after_node,
                "result_status": result.get("status") or "",
                "native_stop_after_node": result.get("native_stop_after_node") or "",
                "node_checkpoint_artifact": str((case_dir / "langgraph_node_checkpoints.json").resolve()),
                "native_summary_artifact": str((case_dir / "langgraph_native_summary.json").resolve()),
                "interpretation": (
                    "diagnostic_node_stop_not_full_chain_pass"
                    if result.get("status") == "stopped_after_node"
                    else "stop_node_not_reached_or_graph_failed"
                ),
            }
            _write_stepwise_node_result(
                case_dir,
                args=args,
                case=case_for_score,
                result=result,
                summary=summary,
                native=native,
                score=score,
            )
        (case_dir / "real_chain_case_score.json").write_text(
            json.dumps(score, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        p30_audit = score.get("p30_root_cause_quality_audit")
        if isinstance(p30_audit, Mapping):
            (case_dir / "p30_root_cause_quality_audit.json").write_text(
                json.dumps(p30_audit, ensure_ascii=False, indent=2) + "\n",
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
    information_economy_audit = _write_agent_information_economy_audit(
        aggregate,
        output_quality_audit=output_quality_audit,
        output_dir=output_dir,
    )
    aggregate["agent_information_economy_audit"] = _compact_agent_information_economy_for_summary(
        information_economy_audit
    )
    data_script_quality_audit = _write_data_script_quality_audit(aggregate, output_dir)
    aggregate["data_script_quality_audit"] = _compact_data_script_quality_for_summary(data_script_quality_audit)
    _apply_output_cost_quality_gate(aggregate, output_quality_audit, ignore=bool(args.ignore_output_cost_quality))
    _apply_data_script_quality_gate(aggregate, data_script_quality_audit)
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


def _write_stepwise_node_result(
    case_dir: Path,
    *,
    args: argparse.Namespace,
    case: Mapping[str, Any],
    result: Mapping[str, Any],
    summary: Mapping[str, Any],
    native: Mapping[str, Any],
    score: Mapping[str, Any],
) -> None:
    """Persist a compact, reviewable node-stop artifact for HITL stepwise runs."""
    node_trace = [row.get("node") for row in result.get("node_trace") or [] if isinstance(row, Mapping)]
    payload = {
        "schema_version": "sec_agent_stepwise_node_result_v0.1",
        "case_id": case.get("case_id") or "",
        "run_id": result.get("run_id") or "",
        "status": result.get("status") or "",
        "requested_stop_after_node": args.stop_after_node or "",
        "native_stop_after_node": result.get("native_stop_after_node") or "",
        "node_trace": node_trace,
        "summary_artifact_present": bool(summary),
        "native_summary_artifact_present": bool(native),
        "gate_semantics": "node_level_diagnostic_only_not_full_chain_pass",
        "artifact_refs": {
            "stepwise_node_result": str((case_dir / "stepwise_node_result.json").resolve()),
            "node_checkpoints": str((case_dir / "langgraph_node_checkpoints.json").resolve()),
            "langgraph_native_summary": str((case_dir / "langgraph_native_summary.json").resolve()),
        },
        "research_lead": {
            "route_status": result.get("research_lead_route_status") or "",
            "failure_reason": result.get("research_lead_failure_reason") or "",
            "validation": result.get("research_lead_validation") if isinstance(result.get("research_lead_validation"), Mapping) else {},
            "rejected_plan": result.get("research_lead_rejected_plan") if isinstance(result.get("research_lead_rejected_plan"), Mapping) else {},
            "diagnostics": result.get("research_lead_model_diagnostics")
            if isinstance(result.get("research_lead_model_diagnostics"), Mapping)
            else {},
            "input_pack_fingerprint": result.get("research_lead_input_pack_fingerprint")
            if isinstance(result.get("research_lead_input_pack_fingerprint"), Mapping)
            else {},
            "routing_trace": result.get("multi_agent_routing_trace") if isinstance(result.get("multi_agent_routing_trace"), Mapping) else {},
        },
        "agent_activation_plan": result.get("agent_activation_plan") if isinstance(result.get("agent_activation_plan"), Mapping) else {},
        "agent_activation_validation": (
            result.get("agent_activation_validation") if isinstance(result.get("agent_activation_validation"), Mapping) else {}
        ),
        "evidence_requirement_plan": (
            result.get("evidence_requirement_plan") if isinstance(result.get("evidence_requirement_plan"), Mapping) else {}
        ),
        "product_intelligence_runtime_policy": (
            result.get("product_intelligence_runtime_policy")
            if isinstance(result.get("product_intelligence_runtime_policy"), Mapping)
            else {}
        ),
        "stepwise_score_focus": {
            "research_lead_checks": {
                key: value for key, value in (score.get("checks") or {}).items() if str(key).startswith("research_lead.")
            },
            "missing_required_agents": score.get("missing_required_agents") or [],
            "activated_agents": score.get("activated_agents") or [],
            "node_stop_interpretation": (score.get("stepwise_node_run") or {}).get("interpretation") or "",
        },
    }
    (case_dir / "stepwise_node_result.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _write_token_budget_plan(
    *,
    args: argparse.Namespace,
    cases: list[Mapping[str, Any]],
    run_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    plan = _token_budget_plan(args=args, cases=cases, run_id=run_id, output_dir=output_dir)
    path = args.token_budget_plan_path or output_dir / "token_budget_plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return plan


def _write_project_os_preflight(*, args: argparse.Namespace, run_id: str, output_dir: Path) -> dict[str, Any]:
    path = output_dir / "project_os_preflight.json"
    if args.skip_project_os_preflight:
        preflight: dict[str, Any] = {
            "schema_version": "fin_insight_project_os_full_chain_preflight_v0_1",
            "run_id": run_id,
            "status": "skipped",
            "policy": "manual_skip_project_os_preflight",
            "reason": "skip_project_os_preflight",
            "warning": "Do not use this for paid product-quality full-chain closeout without explicit user approval.",
        }
    else:
        preflight = run_project_os_preflight(
            REPO_ROOT,
            allow_open_blockers=bool(args.project_os_preflight_allow_open_blockers),
            run_scope=str(args.project_os_run_scope or "broad_full_chain"),
        )
        preflight["run_id"] = run_id
    path.write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return preflight


def _case_with_runtime_paid_specialists(case: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(case)
    paid_specialists = _runtime_paid_specialist_agents(case)
    quality_specialists = _quality_expected_specialist_agents(case)
    if quality_specialists:
        normalized.setdefault("expected_specialist_agents", quality_specialists)
    if paid_specialists:
        normalized["expected_paid_specialist_agents"] = paid_specialists
        normalized["expected_paid_specialist_priorities"] = _expected_paid_specialist_priorities(normalized, paid_specialists)
    return normalized


def _write_provider_preflight(*, args: argparse.Namespace, run_id: str, output_dir: Path) -> dict[str, Any]:
    paid_backend = _llm_backend_is_paid(args.llm_backend)
    proxy_mode = _resolved_llm_gateway_proxy_mode(args)
    path = output_dir / "provider_preflight.json"
    if not paid_backend:
        preflight = {
            "schema_version": "sec_agent_provider_preflight_v0.1",
            "run_id": run_id,
            "status": "skipped",
            "reason": "unpaid_backend",
            "paid_backend": False,
            "llm_backend": args.llm_backend,
            "model": args.model,
            "base_url": args.base_url,
            "chat_completions_path": args.chat_completions_path,
            "api_key_env": args.api_key_env,
            "api_key_present": bool(args.api_key_env and os.environ.get(str(args.api_key_env))),
            "proxy_mode": proxy_mode,
            "api_key_saved": False,
        }
        path.write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return preflight
    if args.skip_provider_preflight:
        preflight = {
            "schema_version": "sec_agent_provider_preflight_v0.1",
            "run_id": run_id,
            "status": "skipped",
            "reason": "skip_provider_preflight",
            "paid_backend": True,
            "llm_backend": args.llm_backend,
            "model": args.model,
            "base_url": args.base_url,
            "chat_completions_path": args.chat_completions_path,
            "api_key_env": args.api_key_env,
            "api_key_present": bool(args.api_key_env and os.environ.get(str(args.api_key_env))),
            "proxy_mode": proxy_mode,
            "api_key_saved": False,
        }
        path.write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return preflight

    started = time.time()
    old_retry_count = os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES")
    os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = os.environ.get("PROVIDER_PREFLIGHT_TRANSPORT_RETRIES", "0")
    try:
        result = chat_completion(
            llm_backend=args.llm_backend,
            base_url=args.base_url,
            chat_completions_path=args.chat_completions_path,
            model=args.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a connectivity preflight endpoint. Return a compact JSON object only.",
                },
                {"role": "user", "content": "{\"status\":\"ok\"}"},
            ],
            response_format={"type": "json_object"},
            api_key_env=args.api_key_env,
            temperature=0.0,
            max_tokens=24,
            timeout_s=max(1, int(args.provider_preflight_timeout_s)),
            role="provider_preflight",
            profile="full_chain_preflight",
            trace_tags={"run_id": run_id, "preflight": True},
        )
    finally:
        if old_retry_count is None:
            os.environ.pop("LLM_GATEWAY_TRANSPORT_RETRIES", None)
        else:
            os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = old_retry_count
    ok = result.get("status") == "ok"
    preflight = {
        "schema_version": "sec_agent_provider_preflight_v0.1",
        "run_id": run_id,
        "status": "ok" if ok else "fail",
        "paid_backend": True,
        "llm_backend": args.llm_backend,
        "model": args.model,
        "base_url": args.base_url,
        "chat_completions_path": args.chat_completions_path,
        "api_key_env": args.api_key_env,
        "api_key_present": bool(args.api_key_env and os.environ.get(str(args.api_key_env))),
        "api_key_saved": False,
        "proxy_mode": result.get("proxy_mode") or proxy_mode,
        "url": result.get("url") or "",
        "call_id": result.get("call_id") or "",
        "latency_ms": int(result.get("latency_ms") or ((time.time() - started) * 1000)),
        "input_tokens": result.get("input_tokens"),
        "output_tokens": result.get("output_tokens"),
        "total_tokens": result.get("total_tokens"),
        "finish_reason": result.get("finish_reason"),
        "failure_reason": str(result.get("failure_reason") or "")[:1000],
        "transport_attempt_count": result.get("transport_attempt_count"),
        "transport_failures": result.get("transport_failures") or [],
        "raw_response_saved": False,
        "policy": "fail_fast_before_paid_full_chain_graph_execution_v0_1",
    }
    path.write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return preflight


def _provider_preflight_stdout_summary(preflight: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": preflight.get("schema_version"),
        "run_id": preflight.get("run_id"),
        "status": preflight.get("status"),
        "paid_backend": preflight.get("paid_backend"),
        "llm_backend": preflight.get("llm_backend"),
        "model": preflight.get("model"),
        "base_url": preflight.get("base_url"),
        "chat_completions_path": preflight.get("chat_completions_path"),
        "api_key_env": preflight.get("api_key_env"),
        "api_key_present": preflight.get("api_key_present"),
        "api_key_saved": False,
        "proxy_mode": preflight.get("proxy_mode"),
        "latency_ms": preflight.get("latency_ms"),
        "total_tokens": preflight.get("total_tokens"),
        "failure_reason": preflight.get("failure_reason"),
    }


def _token_budget_plan(
    *,
    args: argparse.Namespace,
    cases: list[Mapping[str, Any]],
    run_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    case_plans = [_estimate_case_token_budget(case, args=args) for case in cases]
    estimated_total = sum(int(row["estimated_total_tokens"]) for row in case_plans)
    estimated_paid_calls = sum(int(row["estimated_paid_call_count"]) for row in case_plans)
    paid_backend = _llm_backend_is_paid(args.llm_backend)
    violations: list[dict[str, Any]] = []
    if paid_backend and args.token_budget_total > 0 and estimated_total > args.token_budget_total:
        violations.append(
            {
                "type": "run_token_budget_exceeded",
                "estimated_total_tokens": estimated_total,
                "token_budget_total": args.token_budget_total,
            }
        )
    if paid_backend and args.max_paid_calls > 0 and estimated_paid_calls > args.max_paid_calls:
        violations.append(
            {
                "type": "paid_call_budget_exceeded",
                "estimated_paid_call_count": estimated_paid_calls,
                "max_paid_calls": args.max_paid_calls,
            }
        )
    for row in case_plans:
        if paid_backend and args.token_budget_per_case > 0 and int(row["estimated_total_tokens"]) > args.token_budget_per_case:
            violations.append(
                {
                    "type": "case_token_budget_exceeded",
                    "case_id": row["case_id"],
                    "estimated_total_tokens": row["estimated_total_tokens"],
                    "token_budget_per_case": args.token_budget_per_case,
                }
            )
    evidence_mode_violations = _evidence_operator_mode_preflight_violations(
        args=args,
        cases=cases,
        paid_backend=paid_backend,
    )
    violations.extend(evidence_mode_violations)
    token_violations = [row for row in violations if str(row.get("type") or "") != "real_evidence_operators_required"]
    token_budget_allowed = (not paid_backend) or args.allow_expensive_llm or not token_violations
    evidence_mode_allowed = (not paid_backend) or not evidence_mode_violations
    allowed = token_budget_allowed and evidence_mode_allowed
    scheduler_advice = _token_budget_scheduler_advice(
        case_plans,
        paid_backend=paid_backend,
        token_budget_total=int(args.token_budget_total),
        token_budget_per_case=int(args.token_budget_per_case),
        max_paid_calls=int(args.max_paid_calls),
        has_violations=bool(token_violations),
    )
    return {
        "schema_version": "sec_agent_paid_llm_token_budget_plan_v0.1",
        "run_id": run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir.resolve()),
        "paid_backend": paid_backend,
        "llm_backend": args.llm_backend,
        "model": args.model,
        "provider_preflight_required": bool(paid_backend and not args.skip_provider_preflight),
        "provider_preflight_paid_call_count": 1 if paid_backend and not args.skip_provider_preflight else 0,
        "llm_gateway_proxy_mode": _resolved_llm_gateway_proxy_mode(args),
        "budget_policy": "preflight_fail_closed_before_paid_model_calls_v0_1",
        "evidence_operator_mode_policy": "paid_real_retrieval_cases_require_real_evidence_operators_v0_1",
        "allow_expensive_llm": bool(args.allow_expensive_llm),
        "real_evidence_operators": bool(args.real_evidence_operators),
        "allowed": bool(allowed),
        "status": _preflight_block_status(
            allowed=bool(allowed),
            token_violations=token_violations,
            evidence_mode_violations=evidence_mode_violations,
        ),
        "estimated_total_tokens": estimated_total,
        "estimated_paid_call_count": estimated_paid_calls,
        "token_budget_total": int(args.token_budget_total),
        "token_budget_per_case": int(args.token_budget_per_case),
        "max_paid_calls": int(args.max_paid_calls),
        "violations": violations,
        "scheduler_advice": scheduler_advice,
        "cases": case_plans,
        "required_action": _preflight_required_action(
            paid_backend=paid_backend,
            allow_expensive_llm=bool(args.allow_expensive_llm),
            token_violations=token_violations,
            evidence_mode_violations=evidence_mode_violations,
            scheduler_advice=scheduler_advice,
        ),
    }


def _evidence_operator_mode_preflight_violations(
    *,
    args: argparse.Namespace,
    cases: list[Mapping[str, Any]],
    paid_backend: bool,
) -> list[dict[str, Any]]:
    if not paid_backend or bool(getattr(args, "real_evidence_operators", False)):
        return []
    violations: list[dict[str, Any]] = []
    for case in cases:
        requires_real_retrieval = bool(case.get("require_real_retrieval_pass"))
        requires_real_evidence = bool(case.get("require_real_evidence_quality_pass"))
        if not (requires_real_retrieval or requires_real_evidence):
            continue
        violations.append(
            {
                "type": "real_evidence_operators_required",
                "case_id": str(case.get("case_id") or ""),
                "evidence_operator_mode": "dry_run",
                "required_flag": {
                    "require_real_retrieval_pass": requires_real_retrieval,
                    "require_real_evidence_quality_pass": requires_real_evidence,
                },
                "required_action": "Pass --real-evidence-operators or run a no-paid/deterministic diagnostic instead.",
            }
        )
    return violations


def _preflight_block_status(
    *,
    allowed: bool,
    token_violations: list[Mapping[str, Any]],
    evidence_mode_violations: list[Mapping[str, Any]],
) -> str:
    if allowed:
        return "allowed"
    if evidence_mode_violations:
        return "blocked_preflight_evidence_operator_mode"
    if token_violations:
        return "blocked_preflight_token_budget"
    return "blocked_preflight"


def _preflight_required_action(
    *,
    paid_backend: bool,
    allow_expensive_llm: bool,
    token_violations: list[Mapping[str, Any]],
    evidence_mode_violations: list[Mapping[str, Any]],
    scheduler_advice: Mapping[str, Any],
) -> str:
    if not paid_backend:
        return ""
    actions: list[str] = []
    if evidence_mode_violations:
        actions.append(
            "Pass --real-evidence-operators before paid model execution for cases that require real retrieval/evidence quality; do not spend LLM tokens on dry-run evidence."
        )
    if token_violations and not allow_expensive_llm:
        actions.append(
            str(scheduler_advice.get("required_action") or "").strip()
            or "Use deterministic/node-level tests, reduce case count, enable preflight-only, or explicitly pass --allow-expensive-llm after reviewing this plan."
        )
    return " ".join(action for action in actions if action)


def _token_budget_stdout_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "run_id": plan.get("run_id"),
        "status": plan.get("status"),
        "allowed": plan.get("allowed"),
        "estimated_total_tokens": plan.get("estimated_total_tokens"),
        "estimated_paid_call_count": plan.get("estimated_paid_call_count"),
        "provider_preflight_required": plan.get("provider_preflight_required"),
        "provider_preflight_paid_call_count": plan.get("provider_preflight_paid_call_count"),
        "llm_gateway_proxy_mode": plan.get("llm_gateway_proxy_mode"),
        "token_budget_total": plan.get("token_budget_total"),
        "token_budget_per_case": plan.get("token_budget_per_case"),
        "max_paid_calls": plan.get("max_paid_calls"),
        "real_evidence_operators": plan.get("real_evidence_operators"),
        "violations": plan.get("violations") or [],
        "scheduler_advice": plan.get("scheduler_advice") or {},
        "required_action": plan.get("required_action") or "",
    }


def _compact_token_budget_plan_for_summary(plan: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, Mapping) or not plan:
        return {}
    return {
        "schema_version": plan.get("schema_version") or "",
        "status": plan.get("status") or "",
        "allowed": bool(plan.get("allowed")),
        "paid_backend": bool(plan.get("paid_backend")),
        "provider_preflight_required": bool(plan.get("provider_preflight_required")),
        "provider_preflight_paid_call_count": int(plan.get("provider_preflight_paid_call_count") or 0),
        "llm_gateway_proxy_mode": plan.get("llm_gateway_proxy_mode") or "",
        "estimated_total_tokens": int(plan.get("estimated_total_tokens") or 0),
        "estimated_paid_call_count": int(plan.get("estimated_paid_call_count") or 0),
        "token_budget_total": int(plan.get("token_budget_total") or 0),
        "token_budget_per_case": int(plan.get("token_budget_per_case") or 0),
        "max_paid_calls": int(plan.get("max_paid_calls") or 0),
        "violation_count": len(plan.get("violations") or []),
        "budget_policy": plan.get("budget_policy") or "",
        "scheduler_advice": plan.get("scheduler_advice") if isinstance(plan.get("scheduler_advice"), Mapping) else {},
    }


def _compact_provider_preflight_for_summary(preflight: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(preflight, Mapping) or not preflight:
        return {}
    return {
        "schema_version": preflight.get("schema_version") or "",
        "status": preflight.get("status") or "",
        "paid_backend": bool(preflight.get("paid_backend")),
        "llm_backend": preflight.get("llm_backend") or "",
        "model": preflight.get("model") or "",
        "base_url": preflight.get("base_url") or "",
        "chat_completions_path": preflight.get("chat_completions_path") or "",
        "api_key_env": preflight.get("api_key_env") or "",
        "api_key_present": bool(preflight.get("api_key_present")),
        "api_key_saved": False,
        "proxy_mode": preflight.get("proxy_mode") or "",
        "latency_ms": preflight.get("latency_ms"),
        "total_tokens": preflight.get("total_tokens"),
        "failure_reason": preflight.get("failure_reason") or "",
    }


def _token_budget_scheduler_advice(
    case_plans: list[Mapping[str, Any]],
    *,
    paid_backend: bool,
    token_budget_total: int,
    token_budget_per_case: int,
    max_paid_calls: int,
    has_violations: bool,
) -> dict[str, Any]:
    if not paid_backend:
        return {
            "status": "not_required_for_unpaid_backend",
            "recommended_batch_count": 1 if case_plans else 0,
            "batches": [_budget_batch_row(1, case_plans)] if case_plans else [],
            "blocked_case_ids": [],
            "required_action": "",
        }

    blocked_cases: list[Mapping[str, Any]] = []
    runnable_cases: list[Mapping[str, Any]] = []
    for case in case_plans:
        tokens = int(case.get("estimated_total_tokens") or 0)
        calls = int(case.get("estimated_paid_call_count") or 0)
        exceeds_case_tokens = token_budget_per_case > 0 and tokens > token_budget_per_case
        exceeds_case_calls = max_paid_calls > 0 and calls > max_paid_calls
        if exceeds_case_tokens or exceeds_case_calls:
            blocked_cases.append(case)
        else:
            runnable_cases.append(case)

    batches: list[list[Mapping[str, Any]]] = []
    current: list[Mapping[str, Any]] = []
    current_tokens = 0
    current_calls = 0
    for case in runnable_cases:
        tokens = int(case.get("estimated_total_tokens") or 0)
        calls = int(case.get("estimated_paid_call_count") or 0)
        would_exceed_tokens = token_budget_total > 0 and current and current_tokens + tokens > token_budget_total
        would_exceed_calls = max_paid_calls > 0 and current and current_calls + calls > max_paid_calls
        if would_exceed_tokens or would_exceed_calls:
            batches.append(current)
            current = []
            current_tokens = 0
            current_calls = 0
        current.append(case)
        current_tokens += tokens
        current_calls += calls
    if current:
        batches.append(current)

    status = "single_batch_allowed"
    required_action = ""
    if blocked_cases:
        status = "case_budget_repair_required"
        required_action = "Repair or down-scope blocked cases with deterministic/node-level tests before paid execution."
    elif has_violations and len(batches) > 1:
        status = "split_required"
        required_action = "Run the recommended paid batches separately; do not launch this case set as one paid full-chain batch."
    elif has_violations:
        status = "budget_review_required"
        required_action = "Review budget violations before paid execution."

    return {
        "status": status,
        "recommended_batch_count": len(batches),
        "max_cases_per_paid_batch": max([len(batch) for batch in batches] or [0]),
        "blocked_case_ids": [str(case.get("case_id") or "") for case in blocked_cases],
        "batches": [_budget_batch_row(index + 1, batch) for index, batch in enumerate(batches)],
        "required_action": required_action,
        "policy": "split_paid_full_chain_batches_before_model_calls_v0_1",
    }


def _budget_batch_row(index: int, cases: list[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "batch_id": f"budget_batch_{index}",
        "case_ids": [str(case.get("case_id") or "") for case in cases],
        "estimated_total_tokens": sum(int(case.get("estimated_total_tokens") or 0) for case in cases),
        "estimated_paid_call_count": sum(int(case.get("estimated_paid_call_count") or 0) for case in cases),
    }


def _estimate_case_token_budget(case: Mapping[str, Any], *, args: argparse.Namespace) -> dict[str, Any]:
    mode = str(case.get("expected_execution_mode") or case.get("execution_mode") or "").strip()
    required_agents = set(_string_list(case.get("required_agents")))
    quality_expected_specialists = _quality_expected_specialist_agents(case)
    expected_specialists = _estimated_specialist_agents(case)
    paid_specialist_priorities = _expected_paid_specialist_priorities(case, expected_specialists)
    cost_aware_specialists = _cost_aware_estimated_specialist_agents(case, fallback=expected_specialists)
    paid_nodes: list[dict[str, Any]] = []
    if mode not in {"deterministic_lookup"} and ("research_lead" in required_agents or bool(case.get("require_lead_llm_pass", True))):
        paid_nodes.append(_node_token_estimate("research_lead", 8000, args.research_lead_max_tokens))
    if bool(getattr(args, "universe_llm_overlay", False)):
        paid_nodes.append(_node_token_estimate("universe_relationship", 9000, args.universe_max_tokens))
    for agent_id in expected_specialists:
        priority = paid_specialist_priorities.get(agent_id, "primary")
        paid_nodes.append(
            _node_token_estimate(
                agent_id,
                _estimated_specialist_input_tokens(agent_id, case, priority=priority),
                args.specialist_max_tokens,
                priority=priority,
            )
        )
    if "memo_writer" in required_agents or bool(case.get("require_memo_llm_pass", mode in {"focused_answer", "standard_memo", "deep_research"})):
        paid_nodes.append(_node_token_estimate("memo_writer", _estimated_memo_input_tokens(case), args.memo_max_tokens))
    if "verifier" in required_agents or bool(case.get("require_verifier_llm_pass")):
        paid_nodes.append(_node_token_estimate("verifier", 5000, args.verifier_max_tokens))
    pruned_paid_nodes = _replace_specialist_nodes_for_cost_aware_estimate(
        paid_nodes,
        original_specialists=expected_specialists,
        cost_aware_specialists=cost_aware_specialists,
    )
    estimated_total = sum(int(row["estimated_total_tokens"]) for row in pruned_paid_nodes)
    return {
        "case_id": str(case.get("case_id") or ""),
        "execution_mode": mode,
        "estimated_total_tokens": estimated_total,
        "estimated_paid_call_count": len(pruned_paid_nodes),
        "estimated_specialist_count": len(expected_specialists),
        "quality_expected_specialist_agents": quality_expected_specialists,
        "expected_specialist_agents": expected_specialists,
        "expected_paid_specialist_priorities": paid_specialist_priorities,
        "cost_aware_specialist_agents": cost_aware_specialists,
        "pruned_from_quality_expected_specialist_agents": [
            agent for agent in quality_expected_specialists if agent not in set(expected_specialists)
        ],
        "prunable_specialist_agents": [agent for agent in expected_specialists if agent not in set(cost_aware_specialists)],
        "estimated_total_tokens_after_specialist_pruning": sum(
            int(row["estimated_total_tokens"]) for row in pruned_paid_nodes
        ),
        "estimated_paid_call_count_after_specialist_pruning": len(pruned_paid_nodes),
        "nodes": pruned_paid_nodes,
        "unpruned_candidate_nodes": paid_nodes,
        "cost_aware_nodes": pruned_paid_nodes,
        "estimate_policy": "role_projected_compact_prompt_budget_v0_3",
        "estimate_adjustments": {
            "specialist_input": "role_specific_pack_projection_and_priority_scaling",
            "memo_writer_input": "writer_thesis_skeleton_first_compact_verified_inputs",
            "boundary": "preflight_estimate_not_actual_token_meter",
        },
        "cost_aware_boundary": "Preflight uses expected_paid_specialist_agents when present; full-chain runtime activation still must be audited against actual active agents.",
    }


def _node_token_estimate(node: str, input_tokens: int, output_tokens: int, *, priority: str = "") -> dict[str, Any]:
    payload = {
        "node": node,
        "estimated_input_tokens": max(0, int(input_tokens or 0)),
        "max_output_tokens": max(0, int(output_tokens or 0)),
        "estimated_total_tokens": max(0, int(input_tokens or 0)) + max(0, int(output_tokens or 0)),
    }
    if priority:
        payload["priority"] = priority
    return payload


def _estimated_specialist_agents(case: Mapping[str, Any]) -> list[str]:
    explicit_paid = _string_list(case.get("expected_paid_specialist_agents"))
    if explicit_paid:
        return explicit_paid
    explicit = _string_list(case.get("expected_specialist_agents"))
    if explicit:
        return explicit
    required = set(_string_list(case.get("required_agents")))
    specialists = [
        agent
        for agent in (
            "fundamental_analyst",
            "product_technology_analyst",
            "industry_supply_chain_analyst",
            "market_valuation_analyst",
            "risk_counterevidence_analyst",
        )
        if agent in required
    ]
    if specialists:
        return specialists
    mode = str(case.get("expected_execution_mode") or case.get("execution_mode") or "")
    if mode == "deep_research":
        return ["fundamental_analyst", "industry_supply_chain_analyst"]
    if mode == "standard_memo":
        return ["fundamental_analyst"]
    return []


def _quality_expected_specialist_agents(case: Mapping[str, Any]) -> list[str]:
    explicit = _string_list(case.get("expected_specialist_agents"))
    if explicit:
        return explicit
    return _estimated_specialist_agents(case)


def _runtime_required_agents(case: Mapping[str, Any]) -> set[str]:
    required = set(_string_list(case.get("required_agents")))
    quality_specialists = set(_string_list(case.get("expected_specialist_agents")))
    runtime_specialists = set(_string_list(case.get("expected_paid_specialist_agents")))
    if quality_specialists and runtime_specialists:
        required -= quality_specialists
        required |= runtime_specialists
    return required


def _expected_paid_specialist_priorities(case: Mapping[str, Any], specialists: list[str]) -> dict[str, str]:
    explicit = case.get("expected_paid_specialist_priorities")
    values = explicit if isinstance(explicit, Mapping) else {}
    priorities: dict[str, str] = {}
    for agent_id in specialists:
        priority = str(values.get(agent_id) or "").strip().lower()
        if priority not in {"primary", "supporting", "conditional", "low"}:
            priority = "supporting" if agent_id in {"market_valuation_analyst", "risk_counterevidence_analyst"} else "primary"
        priorities[agent_id] = priority
    return priorities


def _cost_aware_estimated_specialist_agents(case: Mapping[str, Any], *, fallback: list[str]) -> list[str]:
    mode = str(case.get("expected_execution_mode") or case.get("execution_mode") or "")
    if mode == "deterministic_lookup":
        return []
    prompt = str(case.get("prompt") or "").lower()
    metrics = {str(item).lower() for item in _string_list(case.get("metric_families"))}
    source_tiers = {str(item).lower() for item in _string_list(case.get("source_tiers"))}
    required_dimensions = {
        str(item).lower()
        for item in (
            _string_list(case.get("required_dimension_ids")) + _string_list(case.get("required_dimensions"))
        )
    }
    eval_focus = {str(item).lower() for item in _string_list(case.get("eval_focus"))}
    agents: list[str] = []

    if metrics & {
        "revenue",
        "segment_revenue",
        "gross_margin",
        "operating_margin",
        "capex",
        "cash_flow",
        "orders_backlog",
        "rpo_deferred_revenue",
        "customer_concentration",
    } or "fundamentals" in required_dimensions:
        agents.append("fundamental_analyst")

    if (
        "product_revenue" in metrics
        or "product_and_production" in required_dimensions
        or any(term in prompt for term in ("product", "产品", "产线", "sku", "h100", "b200", "gb200", "server"))
    ):
        agents.append("product_technology_analyst")

    if (
        "industry_supply_chain" in required_dimensions
        or "relationship_graph" in source_tiers
        or any(term in prompt for term in ("supply", "供应", "需求传导", "shipment", "订单", "积压", "export", "出口"))
    ):
        agents.append("industry_supply_chain_analyst")

    capital_market_feedback_intent = bool(
        required_dimensions
        & {
            "capital_market_feedback",
            "capital_market",
            "capital_and_financing",
            "secondary_market",
            "market_expectation",
            "valuation_price_in",
        }
        or metrics
        & {
            "capital_market_feedback",
            "valuation",
            "market_reaction",
            "liquidity",
            "short_interest",
            "credit_spread",
            "corporate_action",
            "ownership_flow",
            "holder_positioning",
            "derivatives_positioning",
        }
        or eval_focus & {"capital_market_feedback", "market_expectation", "valuation_price_in"}
        or (
            "market_snapshot" in source_tiers
            and any(
                term in prompt
                for term in (
                    "market reaction",
                    "valuation",
                    "price-in",
                    "capital market",
                    "资本市场",
                    "资金面",
                    "估值",
                    "股价",
                    "预期",
                )
            )
        )
    )
    if (
        "competition_and_market_position" in required_dimensions
        and any(term in prompt for term in ("market reaction", "valuation", "估值", "股价", "price-in", "market_snapshot"))
    ) or capital_market_feedback_intent:
        agents.append("market_valuation_analyst")

    explicit_risk_intent = bool(
        "risk_and_counterevidence" in required_dimensions
        or any(
            term in prompt
            for term in (
                "risk",
                "风险",
                "出口限制",
                "监管",
                "geopolitical",
                "export control",
                "sanction",
                "litigation",
                "lawsuit",
                "antitrust",
            )
        )
        or "source_boundary" in eval_focus
    )
    if explicit_risk_intent:
        agents.append("risk_counterevidence_analyst")

    ordered = [agent for agent in _dedupe_preserve_order(agents) if agent in set(fallback)]
    return ordered or fallback


def _replace_specialist_nodes_for_cost_aware_estimate(
    nodes: list[dict[str, Any]],
    *,
    original_specialists: list[str],
    cost_aware_specialists: list[str],
) -> list[dict[str, Any]]:
    original = set(original_specialists)
    keep = set(cost_aware_specialists)
    return [
        dict(row)
        for row in nodes
        if str(row.get("node") or "") not in original or str(row.get("node") or "") in keep
    ]


def _estimated_specialist_input_tokens(agent_id: str, case: Mapping[str, Any], *, priority: str = "primary") -> int:
    mode = str(case.get("expected_execution_mode") or case.get("execution_mode") or "")
    if mode == "deep_research":
        defaults = {
            "fundamental_analyst": 11000,
            "product_technology_analyst": 9500,
            "industry_supply_chain_analyst": 8500,
            "market_valuation_analyst": 6000,
            "risk_counterevidence_analyst": 7000,
        }
        return _priority_scaled_input_tokens(defaults.get(agent_id, 8000), priority=priority, minimum=3000)
    if mode == "standard_memo":
        return _priority_scaled_input_tokens(6500, priority=priority, minimum=3000)
    return _priority_scaled_input_tokens(5200, priority=priority, minimum=2600)


def _priority_scaled_input_tokens(value: int, *, priority: str, minimum: int) -> int:
    normalized = str(priority or "primary").strip().lower()
    factor = {
        "primary": 1.0,
        "supporting": 0.6,
        "conditional": 0.45,
        "low": 0.35,
    }.get(normalized, 1.0)
    return max(int(minimum), int(round(max(0, int(value or 0)) * factor)))


def _estimated_memo_input_tokens(case: Mapping[str, Any]) -> int:
    mode = str(case.get("expected_execution_mode") or case.get("execution_mode") or "")
    if mode == "deep_research":
        return 10500
    if mode == "standard_memo":
        return 7500
    return 6500


def _llm_backend_is_paid(value: Any) -> bool:
    backend = str(value or "").strip().lower()
    return backend not in {"", "mock", "stub", "off", "false", "0", "fixture", "local"}


def _resolved_llm_gateway_proxy_mode(args: argparse.Namespace) -> str:
    mode = str(getattr(args, "llm_gateway_proxy_mode", "") or os.environ.get("LLM_GATEWAY_PROXY_MODE") or "auto").strip().lower()
    if mode != "auto":
        if mode in {"none", "no_proxy", "disable", "disabled"}:
            return "direct"
        return mode if mode in {"system", "direct", "explicit"} else "system"
    return "direct"


def _base_url_is_http_ip_or_local(base_url: str) -> bool:
    match = re.match(r"^http://([^/:]+)", str(base_url or "").strip(), flags=re.IGNORECASE)
    if not match:
        return False
    host = match.group(1).strip("[]").lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    parts = host.split(".")
    return len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)


def _write_output_quality_audit(aggregate: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    audit_summary, render_markdown = _load_quality_audit_helpers()
    audit = audit_summary(aggregate, artifact_root=output_dir)
    (output_dir / "multi_agent_output_quality_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "multi_agent_output_quality_audit.md").write_text(render_markdown(audit), encoding="utf-8")
    return audit


def _write_preflight_information_economy(plan: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    audit = build_preflight_information_economy(plan)
    (output_dir / "agent_information_economy_preflight.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return audit


def _write_agent_information_economy_audit(
    aggregate: Mapping[str, Any],
    *,
    output_quality_audit: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    audit = build_agent_information_economy_summary(aggregate, output_quality_audit=output_quality_audit)
    (output_dir / "agent_information_economy_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "agent_information_economy_audit.md").write_text(
        _render_agent_information_economy_markdown(audit),
        encoding="utf-8",
    )
    return audit


def _write_data_script_quality_audit(aggregate: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    audit = build_data_script_quality_summary(aggregate, artifact_root=output_dir)
    (output_dir / "data_script_quality_audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "data_script_quality_audit.md").write_text(
        render_data_script_quality_markdown(audit),
        encoding="utf-8",
    )
    return audit


def _compact_agent_information_economy_for_summary(audit: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": audit.get("schema_version") or "",
        "diagnostic_only": bool(audit.get("diagnostic_only")),
        "status": audit.get("status") or "",
        "case_count": int(audit.get("case_count") or 0),
        "failed_case_ids": audit.get("failed_case_ids") or [],
        "issue_counts": audit.get("issue_counts") or {},
        "aggregate_metrics": audit.get("aggregate_metrics") or {},
        "policy": audit.get("policy") or "",
    }


def _compact_data_script_quality_for_summary(audit: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": audit.get("schema_version") or "",
        "diagnostic_only": bool(audit.get("diagnostic_only")),
        "status": audit.get("status") or "",
        "case_count": int(audit.get("case_count") or 0),
        "failed_case_ids": audit.get("failed_case_ids") or [],
        "issue_counts": audit.get("issue_counts") or {},
        "policy": audit.get("policy") or "",
    }


def _render_agent_information_economy_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        f"# Agent Information Economy Audit: {audit.get('run_id') or ''}",
        "",
        "Deterministic audit generated from saved runtime artifacts. It does not call models or retrieval tools.",
        "",
        f"- Status: `{audit.get('status') or ''}`",
        f"- Cases: `{audit.get('case_count') or 0}`",
        f"- Failed cases: `{', '.join(str(item) for item in audit.get('failed_case_ids') or []) or 'none'}`",
        "",
        "## Issue Counts",
        "",
    ]
    issue_counts = audit.get("issue_counts") if isinstance(audit.get("issue_counts"), Mapping) else {}
    if issue_counts:
        for issue, count in sorted(issue_counts.items()):
            lines.append(f"- `{issue}`: {count}")
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Cases",
            "",
            "| Case | Gate | Tokens | Specialists | Supported claims | Memo claims | Prompt ref overlap | Same pack digests | Lead refs | Lead payload chars | Universe refs | Universe payload chars | Memo refs | Memo payload chars | Verifier refs | Verifier payload chars | Issues |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for case in audit.get("cases") or []:
        if not isinstance(case, Mapping):
            continue
        tokens = case.get("tokens") if isinstance(case.get("tokens"), Mapping) else {}
        specialists = case.get("specialists") if isinstance(case.get("specialists"), Mapping) else {}
        claims = case.get("claim_metrics") if isinstance(case.get("claim_metrics"), Mapping) else {}
        transfer = case.get("information_transfer") if isinstance(case.get("information_transfer"), Mapping) else {}
        prompt_overlap = transfer.get("prompt_pack_overlap") if isinstance(transfer.get("prompt_pack_overlap"), Mapping) else {}
        lead_input = transfer.get("research_lead_input_pack") if isinstance(transfer.get("research_lead_input_pack"), Mapping) else {}
        universe_input = transfer.get("universe_relationship_input_pack") if isinstance(transfer.get("universe_relationship_input_pack"), Mapping) else {}
        memo_input = transfer.get("memo_writer_input_pack") if isinstance(transfer.get("memo_writer_input_pack"), Mapping) else {}
        verifier_input = transfer.get("verifier_input_pack") if isinstance(transfer.get("verifier_input_pack"), Mapping) else {}
        issues = ", ".join(f"`{issue}`" for issue in case.get("issues") or []) or "none"
        lines.append(
            "| {case_id} | {gate} | {tokens} | {specialists} | {supported} | {memo_claims} | {prompt_refs} | {same_digests} | {lead_refs} | {lead_chars} | {universe_refs} | {universe_chars} | {memo_refs} | {memo_chars} | {verifier_refs} | {verifier_chars} | {issues} |".format(
                case_id=case.get("case_id") or "",
                gate=case.get("gate_status") or "",
                tokens=int(tokens.get("total_tokens") or 0),
                specialists=int(specialists.get("active_count") or 0),
                supported=int(claims.get("supported_claim_card_count") or 0),
                memo_claims=int(claims.get("memo_claim_count") or 0),
                prompt_refs=int(prompt_overlap.get("duplicate_prompt_evidence_ref_count") or 0),
                same_digests=int(prompt_overlap.get("same_component_digest_count") or 0),
                lead_refs=int(lead_input.get("known_evidence_ref_count") or 0),
                lead_chars=int(lead_input.get("approx_prompt_payload_chars") or 0),
                universe_refs=int(universe_input.get("known_evidence_ref_count") or 0),
                universe_chars=int(universe_input.get("approx_prompt_payload_chars") or 0),
                memo_refs=int(memo_input.get("known_evidence_ref_count") or 0),
                memo_chars=int(memo_input.get("approx_prompt_payload_chars") or 0),
                verifier_refs=int(verifier_input.get("known_evidence_ref_count") or 0),
                verifier_chars=int(verifier_input.get("approx_prompt_payload_chars") or 0),
                issues=issues,
            )
        )
    lines.append("")
    return "\n".join(lines)


def _apply_output_cost_quality_gate(aggregate: dict[str, Any], audit: Mapping[str, Any], *, ignore: bool) -> None:
    issue_counts = audit.get("issue_counts") if isinstance(audit.get("issue_counts"), Mapping) else {}
    blocking_flags = {
        "high_total_token_cost",
        "memo_writer_high_token_cost",
        "verifier_high_token_cost",
        "low_rendered_claim_token_efficiency",
        "low_claim_card_token_efficiency",
        "low_memo_chars_per_token",
        "memo_writer_retry_cost_present",
        "memo_payload_not_dense_enough",
        "specialist_claim_yield_low",
        "deep_research_all_specialists_active",
    }
    blocking = {
        flag: int(issue_counts.get(flag) or 0)
        for flag in sorted(blocking_flags)
        if int(issue_counts.get(flag) or 0) > 0
    }
    gate = {
        "schema_version": "sec_agent_output_cost_quality_gate_v0.1",
        "enforced": not ignore,
        "status": "pass" if ignore or not blocking else "fail",
        "blocking_flags": blocking,
        "policy": "post_run_token_efficiency_and_claim_yield_flags_block_full_chain_pass_v0_1",
    }
    aggregate["output_cost_quality_gate"] = gate
    if gate["status"] != "pass":
        aggregate["gate_status"] = "fail"
        metrics = aggregate.get("metrics") if isinstance(aggregate.get("metrics"), dict) else {}
        metrics["output_cost_quality_blocked"] = True
        metrics["output_cost_quality_blocking_flags"] = blocking
        aggregate["metrics"] = metrics


def _apply_data_script_quality_gate(aggregate: dict[str, Any], audit: Mapping[str, Any]) -> None:
    status = str(audit.get("status") or "")
    gate = {
        "schema_version": "sec_agent_data_script_quality_gate_v0.1",
        "status": "pass" if status == "pass" else "fail",
        "blocking_issues": audit.get("issue_counts") or {},
        "failed_case_ids": audit.get("failed_case_ids") or [],
        "policy": "owned_data_script_root_causes_block_full_chain_pass_before_paid_broad_regression_v0_1",
    }
    aggregate["data_script_quality_gate"] = gate
    if gate["status"] != "pass":
        aggregate["gate_status"] = "fail"
        metrics = aggregate.get("metrics") if isinstance(aggregate.get("metrics"), dict) else {}
        metrics["data_script_quality_blocked"] = True
        metrics["data_script_quality_blocking_issue_counts"] = gate["blocking_issues"]
        aggregate["metrics"] = metrics


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
    if not activation_validation and isinstance(result.get("research_lead_validation"), Mapping):
        activation_validation = result.get("research_lead_validation") or {}
    active_agents = set(_string_list(activation.get("activate_agents")))
    required_agents = _runtime_required_agents(case)
    forbidden_agents = set(_string_list(case.get("forbidden_agents")))
    required_specialists = set(_string_list(case.get("expected_paid_specialist_agents")) or _string_list(case.get("expected_specialist_agents")))
    tool_calls = _tool_calls(result, summary)
    llm_routes = summary.get("llm_routes") if isinstance(summary.get("llm_routes"), Mapping) else {}
    research_lead_route = _route(llm_routes, "research_lead")
    if not research_lead_route and isinstance(result.get("research_lead_model_diagnostics"), Mapping):
        research_lead_route = {"diagnostics": result.get("research_lead_model_diagnostics")}
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
    surface_readability = _rendered_surface_readability_checks(rendered_answer, expected_response_language)
    investment_quality = _rendered_investment_quality_checks(rendered_answer, expected_response_language)
    investment_quality_required = _investment_quality_required(case)
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
    diagnostic_quality = _diagnostic_quality_checks(
        case,
        result=result,
        rendered_answer=rendered_answer,
        memo_dimension_analyses=memo_dimension_analyses,
    )
    p30_root_cause_quality = _p30_root_cause_quality_audit(
        case,
        result=result,
        rendered_answer=rendered_answer,
        memo_dimension_analyses=memo_dimension_analyses,
    )
    supervising_analyst = _supervising_analyst_pack_checks(case, result=result)
    source_layer_capability = _source_layer_capability_checks(case, result=result, summary=summary)
    role_source_layer_distribution = _role_source_layer_distribution_checks(case, result=result, summary=summary)

    layer_checks = {
        "research_lead": {
            "llm_invoked": _diag_call_count(research_lead_route) >= 1 if case.get("require_lead_llm_pass") else True,
            "llm_calls_ok": _diag_calls_ok(research_lead_route) if case.get("require_lead_llm_pass") else True,
            "validation_pass": activation_validation.get("status") == "pass",
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
            "surface_readability_pass": (
                surface_readability["status"] == "pass"
                if case.get("require_dimension_memo_surface") or case.get("require_rendered_evidence_refs")
                else True
            ),
            "investment_memo_quality_pass": (
                investment_quality["status"] == "pass"
                if investment_quality_required
                else True
            ),
            **{
                f"surface.{key}": value
                for key, value in surface_readability.get("checks", {}).items()
                if case.get("require_dimension_memo_surface") or case.get("require_rendered_evidence_refs")
            },
            **{
                f"quality.{key}": value
                for key, value in investment_quality.get("checks", {}).items()
                if investment_quality_required
            },
        },
        "payload_safety": {
            "raw_payload_not_in_summary": (summary.get("payload_policy") or {}).get("raw_evidence") == "not_included",
            "no_api_key_marker": "sk-" not in json.dumps(summary, ensure_ascii=False),
            "no_private_path_marker": "raw_private" not in json.dumps(summary, ensure_ascii=False),
        },
        "analyst_depth": analyst_depth["checks"],
        "run_audit": run_audit["checks"],
        "vnext_contract": vnext_contract["checks"],
        "diagnostic_quality": diagnostic_quality["checks"],
        "supervising_analyst": supervising_analyst["checks"],
        "source_layer_capability": source_layer_capability["checks"],
        "role_source_layer_distribution": role_source_layer_distribution["checks"],
        "p30_root_cause_quality": p30_root_cause_quality["checks"],
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
        "surface_readability": surface_readability,
        "investment_quality": investment_quality,
        "investment_quality_required": investment_quality_required,
        "claim_verification": claim_verification.get("status") or "",
        "specialist_verification": specialist_verification.get("status") or "",
        "universe_validation": universe_validation.get("status") or ("skipped" if "universe_relationship" not in active_agents else ""),
        "relationship_lookup_status": relationship_lookup.get("status") or "",
        "agent_activation_validation_errors": activation_validation.get("errors") or [],
        "research_lead_failure_reason": result.get("research_lead_failure_reason") or "",
        "research_lead_routing_trace": result.get("multi_agent_routing_trace") or {},
        "plan_reflection_report": _compact_plan_reflection_report(result.get("plan_reflection_report") or {}),
        "real_retrieval_required": real_retrieval_required,
        "real_specialist_quality_required": real_specialist_quality_required,
        "specialist_real_evidence_quality": specialist_quality,
        "analyst_depth_audit": analyst_depth,
        "run_audit": run_audit,
        "vnext_contract_audit": vnext_contract,
        "diagnostic_quality_audit": diagnostic_quality,
        "supervising_analyst_audit": supervising_analyst,
        "source_layer_capability_audit": source_layer_capability,
        "role_source_layer_distribution_audit": role_source_layer_distribution,
        "p30_root_cause_quality_audit": p30_root_cause_quality,
        "layer_checks": layer_checks,
        "checks": checks,
        "agent_audit": _agent_audit(result, summary, tool_calls=tool_calls, specialist_routes=specialist_routes, specialist_quality=specialist_quality),
        "node_trace": [row.get("node") for row in result.get("node_trace") or [] if isinstance(row, Mapping)],
        "summary_artifact_present": bool(summary),
        "native_summary_artifact_present": bool(native),
        "rendered_answer_preview": rendered_answer[:640],
    }


def _compact_plan_reflection_report(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {
        "schema_version": value.get("schema_version") or "",
        "status": value.get("status") or "",
        "policy": value.get("policy") or "",
        "checked": value.get("checked") if isinstance(value.get("checked"), Mapping) else {},
        "errors": [dict(item) for item in value.get("errors") or [] if isinstance(item, Mapping)],
        "warnings": [dict(item) for item in value.get("warnings") or [] if isinstance(item, Mapping)],
        "repair_requests": [dict(item) for item in value.get("repair_requests") or [] if isinstance(item, Mapping)],
    }


def _rendered_has_claim_section(rendered_answer: str) -> bool:
    text = str(rendered_answer or "")
    return "Key memo claims:" in text or "关键论据:" in text


def _investment_quality_required(case: Mapping[str, Any]) -> bool:
    return bool(
        case.get("require_investment_memo_quality")
        or (
            case.get("require_dimension_memo_surface")
            and (
                case.get("expected_execution_mode") == "deep_research"
                or case.get("require_analyst_depth_gate")
                or case.get("category") in {"sector_depth", "standard_memo"}
            )
        )
    )


def _rendered_has_evidence_refs(rendered_answer: str) -> bool:
    text = str(rendered_answer or "")
    return "refs=" in text or "证据=" in text or bool(re.search(r"\[C\d+\]", text))


def _rendered_has_dimension_section(rendered_answer: str) -> bool:
    text = str(rendered_answer or "")
    return "Dimension analysis:" in text or "分维度分析:" in text


def _rendered_surface_readability_checks(rendered_answer: str, expected_language: str) -> dict[str, Any]:
    text = str(rendered_answer or "")
    internal_markers = [
        "机制：",
        "财务桥：",
        "mechanism:",
        "financial bridge:",
        "Bridge the claim",
        "This ClaimCard",
        "source_boundary_notes",
        "driver_id",
        "gap_id",
        "reconciliation_candidate:",
        "If the fact conflicts with another approved row",
        "证据锚点",
        "投资判断只能沿",
        "financial_metric:",
        "product_kpi:",
        "source_family",
        "memo_slot",
    ]
    checks = {
        "no_internal_field_labels": not any(marker.lower() in text.lower() for marker in internal_markers),
        "no_raw_interactive_refs": "INTERACTIVE_" not in text and "__mcp__::" not in text,
        "no_pipe_joined_dimension_dump": text.count(" | ") <= 1,
        "short_citations_present": bool(re.search(r"\[C\d+\]", text)) if _rendered_has_evidence_refs(text) else True,
        "boilerplate_wrapper_not_repeated": text.count("基于已验证证据并在当前证据边界内") <= 1,
        "language_mix_ok": _rendered_user_language_ok(text, expected_language),
        "no_english_template_prose": (
            not _rendered_has_english_template_prose(text) if expected_language == "zh-CN" else True
        ),
        "opening_not_template_salvage": not _rendered_opening_is_template_salvage(text, expected_language),
    }
    return {
        "schema_version": "sec_agent_rendered_surface_readability_gate_v0.1",
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "policy": "memo_surface_short_citations_no_internal_fields_v0_1",
    }


def _rendered_investment_quality_checks(rendered_answer: str, expected_language: str) -> dict[str, Any]:
    text = str(rendered_answer or "").strip()
    sentences = _memo_sentences(text)
    non_gap_sentences = [sentence for sentence in sentences if not _sentence_is_gap_dominant(sentence)]
    gap_sentences = [sentence for sentence in sentences if _sentence_is_gap_dominant(sentence)]
    opening = _opening_section_text(text, expected_language) or text[:520]
    gap_ratio = (len(gap_sentences) / max(1, len(sentences))) if sentences else 1.0
    insight_sentences = [sentence for sentence in non_gap_sentences if _sentence_has_investment_mechanism(sentence)]
    citation_backed_insights = [sentence for sentence in insight_sentences if bool(re.search(r"\[C\d+\]", sentence))]
    citation_backed_insight_lines = [
        line
        for line in str(text or "").splitlines()
        if bool(re.search(r"\[C\d+\]", line)) and _sentence_has_investment_mechanism(line)
    ]
    decision_sections = _decision_section_texts(text, expected_language)
    decision_section_nonempty = all(len(value.strip()) >= 24 for value in decision_sections.values()) if decision_sections else False
    decision_section_not_gap_only = all(not _text_is_gap_dominant(value) for value in decision_sections.values()) if decision_sections else False
    decision_sections_actionable = all(_decision_text_has_actionable_mechanism(value) for value in decision_sections.values()) if decision_sections else False
    gap_section_chars = len(_extract_gap_section(text, expected_language))
    gap_term_count = _gap_term_count(text)
    dimension_number_sequence_ok = _dimension_number_sequence_ok(text, expected_language)
    product_section_not_fake_financial_line = not _product_section_has_fake_financial_line(text, expected_language)
    checks = {
        "thesis_not_gap_first": not _text_is_gap_dominant(opening),
        "gap_budget_ok": (
            gap_ratio <= 0.30
            and gap_section_chars <= max(360, int(len(text) * 0.20))
            and gap_term_count <= max(8, int(max(1, len(sentences)) * 0.55))
        ),
        "opening_information_dense": _opening_has_information_density(opening, expected_language),
        "insight_density_ok": len(insight_sentences) >= 3,
        "citation_backed_insight_ok": (
            len({*citation_backed_insights, *citation_backed_insight_lines}) >= 2
            if _rendered_has_evidence_refs(text)
            else True
        ),
        "decision_sections_present": decision_section_nonempty,
        "decision_sections_not_gap_only": decision_section_not_gap_only,
        "decision_sections_actionable": decision_sections_actionable,
        "internal_gate_prose_absent": not _contains_internal_gate_prose(text),
        "not_claimcard_or_driver_dump": text.lower().count("claimcard") == 0 and text.lower().count("driver_id") == 0 and text.count(" | ") <= 1,
        "dimension_number_sequence_ok": dimension_number_sequence_ok,
        "product_section_not_fake_financial_line": product_section_not_fake_financial_line,
    }
    return {
        "schema_version": "sec_agent_rendered_investment_quality_gate_v0.1",
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "metrics": {
            "sentence_count": len(sentences),
            "gap_sentence_count": len(gap_sentences),
            "gap_sentence_ratio": round(gap_ratio, 4),
            "gap_term_count": gap_term_count,
            "insight_sentence_count": len(insight_sentences),
            "citation_backed_insight_count": len(citation_backed_insights),
            "citation_backed_insight_line_count": len(citation_backed_insight_lines),
            "gap_section_chars": gap_section_chars,
            "dimension_number_sequence_ok": dimension_number_sequence_ok,
            "product_section_fake_financial_line_count": _product_section_fake_financial_line_count(text, expected_language),
        },
        "policy": "analyst_memo_must_be_decision_useful_not_gap_ledger_v0_2",
    }


def _memo_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？.!?])\s+|\n+|(?<=；)\s*", str(text or ""))
    return [part.strip(" -*\t") for part in parts if len(part.strip(" -*\t")) >= 12]


def _sentence_is_gap_dominant(sentence: str) -> bool:
    return _text_is_gap_dominant(sentence)


def _text_is_gap_dominant(text: str) -> bool:
    value = _strip_role_boundary_prose(str(text or "")).lower()
    if not value.strip():
        return False
    gap_terms = (
        "缺口",
        "缺乏",
        "缺少",
        "缺失",
        "不足",
        "无法",
        "不能",
        "未披露",
        "尚未",
        "找不到",
        "未找到",
        "没有直接",
        "不支持",
        "受限",
        "仅能确认",
        "需等待",
        "口径不匹配",
        "边界",
        "gap",
        "insufficient",
        "not available",
        "not disclosed",
        "cannot",
        "could not",
        "missing",
        "limited",
        "not yet",
        "bounded",
        "commercial tracker",
    )
    hits = sum(value.count(term) for term in gap_terms)
    if hits >= 2:
        return True
    return hits >= 1 and len(value) <= 120


def _strip_role_boundary_prose(text: str) -> str:
    """Remove concise authority-boundary clauses that prevent overclaiming.

    These clauses are different from gap-first writing. For example,
    "cannot treat customer capex as supplier revenue" is a correct role boundary,
    while "data is missing, cannot judge" is a gap-led answer.
    """

    value = str(text or "")
    patterns = (
        r"不能(?:当作|当成|外推|转写成)[^。；\n]{0,80}",
        r"不是客户需求信号",
        r"not\s+(?:supplier\s+revenue|customer\s+demand|direct\s+order)[^.;\n]{0,80}",
        r"cannot\s+(?:treat|infer|rewrite)[^.;\n]{0,100}",
    )
    for pattern in patterns:
        value = re.sub(pattern, "", value, flags=re.IGNORECASE)
    return value


def _sentence_has_investment_mechanism(sentence: str) -> bool:
    value = str(sentence or "").lower()
    mechanism_terms = (
        "因为",
        "意味着",
        "传导",
        "支撑",
        "压制",
        "改善",
        "恶化",
        "反映",
        "对应",
        "回报",
        "现金流",
        "毛利",
        "订单",
        "积压",
        "capex",
        "margin",
        "cash flow",
        "backlog",
        "demand",
        "supplier",
        "therefore",
        "because",
        "implies",
        "supports",
        "pressures",
        "transmission",
        "read-through",
    )
    weak_gap_terms = ("无法", "不能", "缺口", "not available", "cannot", "insufficient")
    return any(term in value for term in mechanism_terms) and not all(term in value for term in weak_gap_terms[:3])


def _decision_text_has_actionable_mechanism(text: str) -> bool:
    value = str(text or "").lower()
    if _text_is_gap_dominant(value):
        return False
    metadata_markers = (
        "financial_metric:",
        "product_kpi:",
        "fundamentals /",
        "product_and_production",
        "这条已验证证据链",
        "证据链上",
        "claimcard",
        "driver_id",
        "source_family",
    )
    if any(marker in value for marker in metadata_markers):
        return False
    mechanism_terms = (
        "如果",
        "若",
        "因为",
        "意味着",
        "传导",
        "验证",
        "吸收",
        "压制",
        "支撑",
        "回报",
        "收入",
        "毛利",
        "现金流",
        "订单",
        "积压",
        "客户",
        "产能",
        "capex",
        "margin",
        "cash flow",
        "orders",
        "backlog",
        "demand",
        "supplier",
        "if",
        "because",
        "implies",
        "supports",
        "pressure",
        "validate",
    )
    return any(term in value for term in mechanism_terms)


def _decision_section_texts(text: str, expected_language: str) -> dict[str, str]:
    labels = (
        ("投资含义", "什么会改变判断", "后续跟踪")
        if expected_language == "zh-CN"
        else ("Investment implications", "What would change the view", "Monitoring items")
    )
    stop_labels = (
        ("投资含义", "什么会改变判断", "后续跟踪", "可行动的证据缺口", "限制与注意事项", "证据边界", "证据索引", "关键论据", "分维度分析")
        if expected_language == "zh-CN"
        else (
            "Investment implications",
            "What would change the view",
            "Monitoring items",
            "Evidence gaps but actionable",
            "Caveats",
            "Source boundary",
            "Evidence index",
            "Key memo claims",
            "Dimension analysis",
        )
    )
    sections: dict[str, str] = {}
    for label in labels:
        other_labels = [item for item in stop_labels if item != label]
        pattern = re.escape(label) + r"\s*[:：]\s*(.*?)(?=\n\n(?:%s)\s*[:：]|\Z)" % "|".join(re.escape(item) for item in other_labels)
        match = re.search(pattern, text, flags=re.S | re.I)
        if match:
            sections[label] = match.group(1).strip()
    return sections


def _opening_section_text(text: str, expected_language: str) -> str:
    label = "核心判断" if expected_language == "zh-CN" else "Core thesis"
    stop_labels = (
        ("分维度分析", "关键论据", "投资含义", "什么会改变判断", "后续跟踪")
        if expected_language == "zh-CN"
        else ("Dimension analysis", "Key memo claims", "Investment implications", "What would change the view", "Monitoring items")
    )
    return _extract_labeled_section(text, label, stop_labels)


def _dimension_number_sequence_ok(text: str, expected_language: str) -> bool:
    section = _extract_dimension_section(text, expected_language)
    if not section:
        return True
    numbers: list[int] = []
    for line in section.splitlines():
        match = re.match(r"\s*(?:[-*]\s*)?(\d+)[.、]\s+", line)
        if match:
            numbers.append(int(match.group(1)))
    if len(numbers) < 2:
        return True
    return numbers == list(range(1, len(numbers) + 1))


def _extract_dimension_section(text: str, expected_language: str) -> str:
    label = "分维度分析" if expected_language == "zh-CN" else "Dimension analysis"
    stop_labels = (
        ("关键问题回应", "关键论据", "投资含义", "什么会改变判断", "后续跟踪", "可行动的证据缺口", "证据索引")
        if expected_language == "zh-CN"
        else (
            "Required question coverage",
            "Key memo claims",
            "Investment implications",
            "What would change the view",
            "Monitoring items",
            "Evidence gaps",
            "Evidence index",
        )
    )
    return _extract_labeled_section(text, label, stop_labels)


def _extract_labeled_section(text: str, label: str, stop_labels: tuple[str, ...]) -> str:
    stop_pattern = "|".join(re.escape(item) for item in stop_labels)
    pattern = re.escape(label) + r"\s*[:：]\s*(.*?)(?=\n\n(?:%s)\s*[:：]|\Z)" % stop_pattern
    match = re.search(pattern, str(text or ""), flags=re.S | re.I)
    return match.group(1).strip() if match else ""


def _product_section_has_fake_financial_line(text: str, expected_language: str) -> bool:
    return _product_section_fake_financial_line_count(text, expected_language) > 0


def _product_section_fake_financial_line_count(text: str, expected_language: str) -> int:
    product_lines = _product_dimension_lines(text, expected_language)
    if not product_lines:
        return 0
    bad_phrases = (
        "proceeds from sales",
        "maturities of investments",
        "sales and maturities of investments",
        "realized gain",
        "unrealized gain",
        "gain on sales",
        "dividends",
        "cost of revenue",
        "costs of revenue",
        "cost of revenues",
        "costs of revenues",
        "cost of sales",
        "costs of sales",
        "deferred revenue",
        "deferred system revenue",
        "receivables sold",
        "accounts receivable",
        "factoring",
        "letter of credit",
        "proceeds from sales of lc",
        "contract liabilities",
        "capex",
        "capital expenditure",
        "capital expenditures",
        "purchases of property",
        "property and equipment",
        "投资到期",
        "出售投资",
        "投资收益",
        "资本开支",
        "资本支出",
        "购置物业",
        "固定资产购置",
        "递延",
        "收入成本",
        "销售成本",
    )
    product_markers = ("产品", "产线", "product", "production")
    product_anchor_phrases = (
        "产品收入",
        "server 收入",
        "servers 收入",
        "ai server 收入",
        "ai-optimized servers 收入",
        "product revenue",
        "segment revenue",
        "订单",
        "积压",
        "backlog",
        "出货",
        "销量",
        "shipments",
        "units",
        "客户部署",
        "部署",
        "deployment",
        "adoption",
        "规格",
        "参数",
        "spec",
        "benchmark",
    )
    count = 0
    for line in product_lines:
        value = line.lower()
        if any(marker in value for marker in product_markers) and any(phrase in value for phrase in bad_phrases):
            if any(anchor in value for anchor in product_anchor_phrases) and not any(
                marker in value for marker in ("被写成", "冒充", "mistaken as", "misstated as", "written as")
            ):
                continue
            count += 1
    return count


def _product_dimension_lines(text: str, expected_language: str) -> list[str]:
    section = _extract_dimension_section(text, expected_language)
    if not section:
        return []
    product_markers = ("产品", "产线", "product", "production")
    lines: list[str] = []
    capture = False
    for raw_line in section.splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        numbered = re.match(r"\s*(?:[-*]\s*)?(\d+)[.、]\s+(.+)", line)
        if numbered:
            title = re.split(r"[:：]", numbered.group(2), maxsplit=1)[0].lower()
            capture = any(marker in title for marker in product_markers)
        if capture:
            lines.append(raw_line)
    return lines


def _extract_gap_section(text: str, expected_language: str) -> str:
    labels = ("可行动的证据缺口", "限制与注意事项", "证据边界") if expected_language == "zh-CN" else ("Evidence gaps but actionable", "Caveats", "Source boundary")
    chunks: list[str] = []
    for label in labels:
        match = re.search(re.escape(label) + r"\s*[:：]\s*(.*?)(?=\n\n\S|$)", text, flags=re.S | re.I)
        if match:
            chunks.append(match.group(1).strip())
    return "\n".join(chunks)


def _contains_internal_gate_prose(text: str) -> bool:
    value = str(text or "").lower()
    markers = (
        "该声明为已核对",
        "该声明卡为",
        "不得推断未验证",
        "reported revenue",
        "company-disclosed product",
        "the evidence traces",
        "peer comparison is available only",
        "no direct competitive comparison",
        "source_boundary_notes",
        "bridge the claim",
        "if the fact conflicts with another approved row",
        "证据锚点",
        "投资判断只能沿",
        "financial_metric:",
        "product_kpi:",
        "source_family",
        "这条已验证证据链",
        "证据链上",
        "投资判断应先围绕",
        "而不是只复述披露条目",
    )
    return any(marker in value for marker in markers)


def _gap_term_count(text: str) -> int:
    value = str(text or "").lower()
    terms = (
        "缺口",
        "缺乏",
        "缺少",
        "缺失",
        "无法",
        "不能",
        "不足",
        "未披露",
        "尚未",
        "没有直接",
        "不支持",
        "受限",
        "仅能确认",
        "需等待",
        "口径不匹配",
        "边界",
        "gap",
        "missing",
        "insufficient",
        "not available",
        "not disclosed",
        "cannot",
        "limited",
        "not yet",
        "bounded",
        "commercial tracker",
    )
    return sum(value.count(term) for term in terms)


def _opening_has_information_density(opening: str, expected_language: str) -> bool:
    value = str(opening or "").lower()
    if not value.strip():
        return False
    if _rendered_opening_is_template_salvage(value, expected_language):
        return False
    thesis_terms = (
        "收入",
        "毛利",
        "利润",
        "现金流",
        "资本开支",
        "订单",
        "积压",
        "产品",
        "客户",
        "供应链",
        "估值",
        "竞争",
        "revenue",
        "margin",
        "earnings",
        "cash flow",
        "capex",
        "orders",
        "backlog",
        "product",
        "customer",
        "supplier",
        "valuation",
    )
    numeric_or_ticker = bool(re.search(r"\b[A-Z]{2,6}\b|\$?\d", opening))
    return numeric_or_ticker and sum(value.count(term) for term in thesis_terms) >= 2


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


def _diagnostic_quality_checks(
    case: Mapping[str, Any],
    *,
    result: Mapping[str, Any],
    rendered_answer: str,
    memo_dimension_analyses: list[Mapping[str, Any]],
) -> dict[str, Any]:
    required_metric_ids = set(_string_list(case.get("required_approved_metric_ids")))
    required_dimensions = set(_string_list(case.get("required_deterministic_claim_dimensions")))
    required_product_terms = _string_list(case.get("required_product_fact_terms"))
    required = any(
        [
            required_metric_ids,
            required_dimensions,
            required_product_terms,
            bool(case.get("require_no_internal_synthesis_dimension")),
            bool(case.get("require_numeric_fact_sanity")),
            bool(case.get("require_product_or_gap_evidence")),
            bool(case.get("require_capital_financing_signal")),
        ]
    )
    approved_facts = _diagnostic_approved_facts(result)
    supported_claims = _diagnostic_supported_claims(result)
    gap_rows = _diagnostic_gap_rows(result)
    approved_metric_ids = {
        _diagnostic_text(row.get("canonical_metric_id"))
        for row in approved_facts
        if _diagnostic_text(row.get("canonical_metric_id"))
    }
    supported_metric_ids = {
        metric_id
        for claim in supported_claims
        for metric_id in _string_list(claim.get("metric_scope"))
        if metric_id
    }
    deterministic_dimensions = {
        _diagnostic_text(claim.get("analysis_dimension"))
        for claim in supported_claims
        if _diagnostic_text(claim.get("agent_id")) == "pre_memo_fact_selector"
        and _diagnostic_text(claim.get("analysis_dimension"))
    }
    memo_dimension_ids = {
        _diagnostic_text(row.get("dimension_id"))
        for row in memo_dimension_analyses
        if _diagnostic_text(row.get("dimension_id"))
    }
    metric_ids_seen = approved_metric_ids | supported_metric_ids
    product_text = "\n".join(
        [
            *(_diagnostic_row_text(row) for row in approved_facts if _diagnostic_row_has_product_signal(row)),
            *(_diagnostic_row_text(row) for row in supported_claims if _diagnostic_claim_has_product_signal(row)),
        ]
    )
    supported_product_text = "\n".join(
        [
            *(_diagnostic_row_text(row) for row in supported_claims if _diagnostic_claim_has_product_signal(row)),
            *(
                _diagnostic_row_text(row)
                for row in memo_dimension_analyses
                if _diagnostic_text(row.get("dimension_id")) == "product_and_production"
                and _diagnostic_dimension_has_claim_or_evidence(row)
            ),
        ]
    )
    product_evidence_present = _diagnostic_product_evidence_present(approved_facts, supported_claims)
    product_gap_present = _diagnostic_product_gap_present(gap_rows)
    internal_synthesis_dimension_ids = [
        _diagnostic_text(row.get("dimension_id"))
        for row in memo_dimension_analyses
        if _diagnostic_text(row.get("dimension_id")) == "thesis_synthesis"
    ]
    internal_synthesis_rendered = any(
        marker in rendered_answer
        for marker in ("thesis_synthesis", "Synthesis: primary_sec_filing", "Synthesis：primary_sec_filing")
    )
    numeric_violations = _diagnostic_numeric_sanity_violations(approved_facts)
    capital_metric_ids = {
        "financial_metric:capex",
        "financial_metric:debt",
        "financial_metric:cash",
        "financial_metric:fcf",
        "financial_metric:operating_cash_flow",
    }
    capital_dimensions = {
        _diagnostic_text(claim.get("analysis_dimension"))
        for claim in supported_claims
        if _diagnostic_text(claim.get("analysis_dimension"))
    }
    checks = {
        "required_approved_metric_ids_present": required_metric_ids <= metric_ids_seen if required_metric_ids else True,
        "required_deterministic_claim_dimensions_present": required_dimensions <= deterministic_dimensions
        if required_dimensions
        else True,
        "no_internal_synthesis_dimension": (
            not internal_synthesis_dimension_ids and not internal_synthesis_rendered
            if case.get("require_no_internal_synthesis_dimension")
            else True
        ),
        "numeric_fact_sanity": not numeric_violations if case.get("require_numeric_fact_sanity") else True,
        "product_or_bounded_gap_evidence_present": (
            product_evidence_present or product_gap_present if case.get("require_product_or_gap_evidence") else True
        ),
        "required_product_fact_terms_present": (
            all(_diagnostic_required_term_present(supported_product_text, term) for term in required_product_terms)
            if required_product_terms
            else True
        ),
        "capital_financing_signal_present": (
            bool(metric_ids_seen & capital_metric_ids) or "capital_and_financing" in capital_dimensions
            if case.get("require_capital_financing_signal")
            else True
        ),
    }
    return {
        "schema_version": "sec_agent_diagnostic_quality_eval_check_v0.1",
        "required": required,
        "approved_metric_ids": sorted(approved_metric_ids),
        "supported_metric_ids": sorted(supported_metric_ids),
        "required_metric_ids": sorted(required_metric_ids),
        "deterministic_dimensions": sorted(deterministic_dimensions),
        "memo_dimension_ids": sorted(memo_dimension_ids),
        "required_dimensions": sorted(required_dimensions),
        "required_product_terms": required_product_terms,
        "product_evidence_present": product_evidence_present,
        "product_gap_present": product_gap_present,
        "supported_product_terms_surface_present": bool(supported_product_text.strip()),
        "numeric_violations": numeric_violations,
        "gap_count": len(gap_rows),
        "supported_claim_count": len(supported_claims),
        "approved_fact_count": len(approved_facts),
        "checks": checks,
    }


def _p30_root_cause_quality_audit(
    case: Mapping[str, Any],
    *,
    result: Mapping[str, Any],
    rendered_answer: str,
    memo_dimension_analyses: list[Mapping[str, Any]],
) -> dict[str, Any]:
    required_items = _p30_required_items(case)
    product_required = _p30_product_required(case, memo_dimension_analyses)
    approved_facts = _diagnostic_approved_facts(result)
    supported_claims = _diagnostic_supported_claims(result)
    gap_rows = _diagnostic_gap_rows(result)
    memo_logic_plan = result.get("memo_logic_plan") if isinstance(result.get("memo_logic_plan"), Mapping) else {}
    product_frame = memo_logic_plan.get("product_reasoning_frame") if isinstance(memo_logic_plan.get("product_reasoning_frame"), Mapping) else {}
    memo_logic_plan_validation = (
        memo_logic_plan.get("validation") if isinstance(memo_logic_plan.get("validation"), Mapping) else {}
    )
    required_item_answer_plan_rows = [
        row for row in memo_logic_plan.get("required_item_answer_plan") or [] if isinstance(row, Mapping)
    ]
    summary_artifact = result.get("multi_agent_summary") if isinstance(result.get("multi_agent_summary"), Mapping) else {}
    summary_memo_logic_plan = (
        summary_artifact.get("memo_logic_plan") if isinstance(summary_artifact.get("memo_logic_plan"), Mapping) else {}
    )
    all_evidence_text = "\n".join(
        [
            rendered_answer,
            *(_diagnostic_row_text(row) for row in approved_facts),
            *(_diagnostic_row_text(row) for row in supported_claims),
            *(_diagnostic_row_text(row) for row in gap_rows),
        ]
    )
    root_rows: list[dict[str, Any]] = []
    case_id_text = str(case.get("case_id") or "").lower()
    required = bool(
        case.get("require_p30_root_cause_quality")
        or "p30" in case_id_text
        or "ai_infra" in case_id_text
        or "semicap" in case_id_text
    )

    display_lineage_violations = _p30_display_lineage_violations(approved_facts)
    for row in display_lineage_violations:
        root_rows.append(
            _p30_root_row(
                case_id=case.get("case_id"),
                symptom="missing_display_value_lineage",
                required_item_id=_diagnostic_text(row.get("canonical_metric_id") or row.get("fact_id")),
                tickers=_string_list(row.get("ticker")),
                earliest_faulty_artifact="pre_memo_fact_selection.approved_facts",
                root_cause_layer="fact_selection_display_value_lineage",
                repair_action="derive display_value/display_value_lineage before fact enters ClaimCard or memo payload",
                evidence_refs=_string_list(row.get("evidence_ref")),
                verification_test="tests/test_d_series_fact_selection.py::display_value_lineage",
            )
        )

    raw_surface_violations = _p30_raw_numeric_surface_violations(rendered_answer)
    for issue in raw_surface_violations:
        root_rows.append(
            _p30_root_row(
                case_id=case.get("case_id"),
                symptom="raw_unitless_numeric_rendered",
                required_item_id="numeric_display_lineage",
                tickers=[],
                earliest_faulty_artifact="memo_answer.rendered_answer",
                root_cause_layer="memo_writer_numeric_projection",
                repair_action="writer must consume display_value only; upstream must emit display_value for every numeric fact",
                evidence_refs=[issue.get("token", "")],
                verification_test="p30_root_cause_quality.rendered_no_raw_unitless_numeric",
            )
        )

    missing_value_claims = _p30_missing_value_claims(rendered_answer)
    for issue in missing_value_claims:
        root_rows.append(
            _p30_root_row(
                case_id=case.get("case_id"),
                symptom="missing_value_before_citation",
                required_item_id="numeric_display_value",
                tickers=[],
                earliest_faulty_artifact="memo_answer.rendered_answer",
                root_cause_layer="memo_writer_numeric_projection",
                repair_action="replace empty numeric phrase with display_value or write display-lineage parser gap",
                evidence_refs=[issue],
                verification_test="p30_root_cause_quality.rendered_no_missing_value_claim",
            )
        )

    memo_logic_plan_validation_failed = _p30_memo_logic_plan_validation_failed(memo_logic_plan_validation)
    if memo_logic_plan_validation_failed:
        root_rows.append(
            _p30_root_row(
                case_id=case.get("case_id"),
                symptom="memo_logic_plan_validation_failed",
                required_item_id="MemoLogicPlan.validation",
                tickers=_string_list(case.get("focus_tickers")),
                earliest_faulty_artifact="memo_logic_plan.validation",
                root_cause_layer="research_lead_memo_logic_plan_projection",
                repair_action="repair MemoLogicPlan coverage/status before memo writer; do not let writer compensate for invalid plan",
                evidence_refs=_string_list(memo_logic_plan_validation.get("errors") or memo_logic_plan_validation.get("warnings"))[:6],
                verification_test="p30_root_cause_quality.memo_logic_plan_validation_pass",
            )
        )

    focus_matrix, contradiction_rows = _p30_focus_ticker_coverage_matrix(case, approved_facts, supported_claims, rendered_answer)
    root_rows.extend(contradiction_rows)

    required_matrix, missing_required_rows = _p30_required_item_matrix(
        case,
        required_items=required_items,
        text=all_evidence_text,
        approved_facts=approved_facts,
        supported_claims=supported_claims,
        rendered_answer=rendered_answer,
        memo_logic_plan=memo_logic_plan,
    )
    root_rows.extend(missing_required_rows)
    missing_answer_plan_rows = _p30_missing_required_item_answer_plan(required_items, required_item_answer_plan_rows)
    for item_id in missing_answer_plan_rows:
        root_rows.append(
            _p30_root_row(
                case_id=case.get("case_id"),
                symptom="required_item_missing_answer_plan",
                required_item_id=item_id,
                tickers=_string_list(case.get("focus_tickers")),
                earliest_faulty_artifact="memo_logic_plan.required_item_answer_plan",
                root_cause_layer="research_lead_memo_logic_plan_projection",
                repair_action="project every required question item into an answer-first judgment/evidence-bridge/counter-read plan before writer",
                evidence_refs=[],
                verification_test="p30_root_cause_quality.required_item_answer_plan_present",
            )
        )
    required_item_plan_projection_missing = _p30_required_item_plan_projection_missing(
        required_items=required_items,
        required_item_answer_plan_rows=required_item_answer_plan_rows,
        summary_memo_logic_plan=summary_memo_logic_plan,
    )
    if required_item_plan_projection_missing:
        root_rows.append(
            _p30_root_row(
                case_id=case.get("case_id"),
                symptom="required_item_answer_plan_not_projected_to_summary",
                required_item_id="MemoLogicPlan.required_item_answer_plan",
                tickers=_string_list(case.get("focus_tickers")),
                earliest_faulty_artifact="multi_agent_summary.memo_logic_plan.required_item_answer_plan",
                root_cause_layer="workbench_projection",
                repair_action="project MemoLogicPlan required question items and answer plans into the durable run summary for review/replay",
                evidence_refs=[],
                verification_test="p30_root_cause_quality.required_item_answer_plan_projected_to_summary",
            )
        )

    frame_roles = set(_string_list(product_frame.get("coverage_roles")))
    scope_hypothesis_refs = _string_list(product_frame.get("scope_hypothesis_refs"))
    non_scope_product_roles = frame_roles - {"scope_hypothesis"}
    product_frame_missing = product_required and not frame_roles
    if product_frame_missing:
        root_rows.append(
            _p30_root_row(
                case_id=case.get("case_id"),
                symptom="product_reasoning_frame_missing",
                required_item_id="ProductReasoningFrame",
                tickers=_string_list(case.get("focus_tickers")),
                earliest_faulty_artifact="memo_logic_plan.product_reasoning_frame",
                root_cause_layer="research_lead_memo_logic_plan_projection",
                repair_action="project ProductIntelligenceGraph/ProductBridge rows into MemoLogicPlan before writer",
                evidence_refs=[],
                verification_test="p30_root_cause_quality.product_reasoning_frame_present_when_product_required",
            )
        )
    scope_dominant = bool(product_required and scope_hypothesis_refs and not non_scope_product_roles)
    if scope_dominant:
        root_rows.append(
            _p30_root_row(
                case_id=case.get("case_id"),
                symptom="product_section_scope_hypothesis_only",
                required_item_id="product_primary_evidence",
                tickers=_string_list(case.get("focus_tickers")),
                earliest_faulty_artifact="product_reasoning_frame.scope_hypothesis_refs",
                root_cause_layer="product_evidence_selection_or_source_depth",
                repair_action="recover official product/spec/deployment/proxy evidence or mark section as low-confidence context with why_scope_only",
                evidence_refs=scope_hypothesis_refs[:6],
                verification_test="p30_root_cause_quality.scope_hypothesis_not_primary_product_proof",
            )
        )

    non_us_rows = _p30_non_us_disclosure_diagnostics(case, result, approved_facts, supported_claims, gap_rows, rendered_answer)
    root_rows.extend(non_us_rows)
    role_misuse_rows = _p30_economic_role_misuse_rows(case, rendered_answer)
    root_rows.extend(role_misuse_rows)

    checks = {
        "display_value_lineage_complete": (not display_lineage_violations) if required else True,
        "rendered_no_raw_unitless_numeric": (not raw_surface_violations) if required else True,
        "rendered_no_missing_value_claim": (not missing_value_claims) if required else True,
        "memo_logic_plan_validation_pass": (not memo_logic_plan_validation_failed) if required else True,
        "focus_ticker_no_evidence_contradiction": (not contradiction_rows) if required else True,
        "focus_ticker_no_product_evidence_contradiction": (
            not any(row.get("symptom") == "memo_claims_missing_product_data_despite_available_evidence" for row in contradiction_rows)
        )
        if required
        else True,
        "required_items_covered": (not missing_required_rows) if required else True,
        "required_item_answer_plan_present": (not missing_answer_plan_rows) if required else True,
        "required_item_answer_plan_projected_to_summary": (not required_item_plan_projection_missing) if required else True,
        "product_reasoning_frame_present_when_product_required": (not product_frame_missing) if required else True,
        "scope_hypothesis_not_primary_product_proof": (not scope_dominant) if required else True,
        "non_us_official_source_gaps_have_parser_diagnosis": (not non_us_rows) if required else True,
        "economic_role_no_misuse": (not role_misuse_rows) if required else True,
        "root_cause_rows_complete": all(_p30_root_row_complete(row) for row in root_rows),
    }
    return {
        "schema_version": "finsight_p30_root_cause_quality_audit_v0_1",
        "required": required,
        "status": "pass" if all(checks.values()) else "fail",
        "required_item_matrix": required_matrix,
        "focus_ticker_coverage_matrix": focus_matrix,
        "product_reasoning_frame_summary": {
            "coverage_roles": sorted(frame_roles),
            "scope_hypothesis_ref_count": len(scope_hypothesis_refs),
            "product_frame_present": bool(product_frame),
            "memo_logic_plan_validation_status": str(memo_logic_plan_validation.get("status") or ""),
            "required_item_answer_plan_count": len(required_item_answer_plan_rows),
            "summary_required_item_answer_plan_count": int(
                summary_memo_logic_plan.get("required_item_answer_plan_count") or 0
            ),
        },
        "display_lineage_violations": display_lineage_violations,
        "raw_surface_violations": raw_surface_violations,
        "missing_value_claims": missing_value_claims,
        "economic_role_misuse_rows": role_misuse_rows,
        "root_cause_rows": root_rows,
        "checks": checks,
        "policy": "repair_root_cause_before_release_no_gate_only_closeout_v0_1",
    }


def _p30_required_items(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    explicit = [dict(row) for row in case.get("required_answer_items") or [] if isinstance(row, Mapping)]
    if explicit:
        return explicit
    case_id = str(case.get("case_id") or "").lower()
    prompt = str(case.get("prompt") or case.get("query") or "").lower()
    items: list[dict[str, Any]] = []
    if "nvda" in prompt and "dell" in prompt:
        items.extend(
            [
                {
                    "item_id": "dell_ai_server_quality_margin_bridge",
                    "terms_any": ["dell", "ai server", "gross margin", "margin", "ai服务器", "毛利", "利润率"],
                },
                {
                    "item_id": "nvda_gpu_supply_generation",
                    "terms_any": ["nvda", "gpu", "h100", "h200", "b200", "gb200", "blackwell", "算力", "显卡"],
                },
                {
                    "item_id": "cloud_capex_read_through",
                    "terms_any": ["capex", "amzn", "msft", "googl", "cloud", "资本支出", "云服务", "数据中心"],
                },
                {
                    "item_id": "customer_deployment_or_order_signal",
                    "terms_any": ["deployment", "customer", "order", "configured", "adoption", "客户", "订单", "部署", "采用", "配置"],
                },
            ]
        )
    if "semicap" in case_id or {"asml", "lrcx", "amat", "klac"} & set(_string.lower() for _string in _string_list(case.get("search_scope_tickers"))):
        items.extend(
            [
                {"item_id": "asml_orders_or_backlog", "terms_any": ["asml", "order", "booking", "backlog", "订单", "预订", "积压"]},
                {
                    "item_id": "shipment_or_cycle_context",
                    "terms_any": ["shipment", "cycle", "wafer fab", "semicap", "出货", "周期", "晶圆厂", "半导体设备"],
                },
                {
                    "item_id": "customer_concentration_or_deployment",
                    "terms_any": ["customer", "tsmc", "samsung", "intel", "deployment", "客户", "台积电", "三星", "英特尔", "部署"],
                },
                {
                    "item_id": "export_restriction_context",
                    "terms_any": ["export", "china", "restriction", "license", "出口", "中国", "限制", "许可证", "管制"],
                },
            ]
        )
    return items


def _p30_product_required(case: Mapping[str, Any], memo_dimension_analyses: list[Mapping[str, Any]]) -> bool:
    dimensions = set(_string_list(case.get("required_dimension_ids")))
    dimensions.update(_diagnostic_text(row.get("dimension_id")) for row in memo_dimension_analyses if isinstance(row, Mapping))
    if "product_and_production" in dimensions:
        return True
    text = " ".join([str(case.get("prompt") or ""), " ".join(_string_list(case.get("expected_specialist_agents")))]).lower()
    return any(term in text for term in ("product", "产品", "gpu", "server", "ai", "semicap", "deployment"))


def _p30_memo_logic_plan_validation_failed(validation: Mapping[str, Any]) -> bool:
    if not isinstance(validation, Mapping) or not validation:
        return False
    status = _diagnostic_text(validation.get("status") or validation.get("result")).strip().lower()
    if not status:
        return False
    return status not in {"pass", "passed", "ok", "valid", "warning_only"}


def _p30_display_lineage_violations(approved_facts: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for row in approved_facts:
        if not _p30_numeric_present(row):
            continue
        lineage = row.get("display_value_lineage") if isinstance(row.get("display_value_lineage"), Mapping) else {}
        if not _diagnostic_text(row.get("display_value")) or lineage.get("schema_version") != "sec_agent_display_value_lineage_v0.1":
            violations.append(dict(row))
    return violations


def _p30_numeric_present(row: Mapping[str, Any]) -> bool:
    return bool(_diagnostic_text(row.get("numeric_value")) or re.fullmatch(r"-?\d+(?:\.\d+)?", _diagnostic_text(row.get("value"))))


def _p30_raw_numeric_surface_violations(rendered_answer: str) -> list[dict[str, str]]:
    text = _p30_user_prose_for_numeric_scan(rendered_answer)
    violations: list[dict[str, str]] = []
    for match in re.finditer(r"(?<![A-Za-z0-9$])(-?\d{4,}(?:\.\d+)?)(?![A-Za-z0-9])", text):
        token = match.group(1)
        try:
            value = float(token)
        except ValueError:
            continue
        if 1900 <= abs(value) <= 2100 and "." not in token:
            continue
        window = text[max(0, match.start() - 18) : min(len(text), match.end() + 18)].lower()
        if any(unit in window for unit in ("$", "usd", "美元", "million", "billion", "百万", "十亿", "亿", "万", "%", "bps", "台", "辆", "units")):
            continue
        violations.append({"token": token, "context": window.strip()})
    return violations[:20]


def _p30_user_prose_for_numeric_scan(rendered_answer: str) -> str:
    text = str(rendered_answer or "")
    for marker in ("证据索引:", "证据索引：", "Evidence index:", "Evidence Index:", "Citations:", "引用:"):
        if marker in text:
            text = text.split(marker, 1)[0]
    return text


def _p30_missing_value_claims(rendered_answer: str) -> list[str]:
    text = str(rendered_answer or "")
    patterns = [
        r"(?:达到|为|约为|录得|reported|reached|was|were)\s*(?:\[[A-Z]\d+\])",
        r"(?:达到|为|约为|录得)\s*[，,。.；;]",
    ]
    issues: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            issues.append(text[max(0, match.start() - 24) : min(len(text), match.end() + 24)].strip())
    return issues[:12]


def _p30_economic_role_misuse_rows(case: Mapping[str, Any], rendered_answer: str) -> list[dict[str, Any]]:
    text = str(rendered_answer or "")
    normalized = text.lower()
    case_id = str(case.get("case_id") or "").lower()
    prompt = str(case.get("prompt") or case.get("query") or "").lower()
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...], str]] = set()

    def add(symptom: str, tickers: list[str], context: str, repair_action: str) -> None:
        key = (symptom, tuple(sorted(tickers)), context[:120])
        if key in seen:
            return
        seen.add(key)
        rows.append(
            _p30_root_row(
                case_id=case.get("case_id"),
                symptom=symptom,
                required_item_id="economic_role_projection",
                tickers=tickers,
                earliest_faulty_artifact="memo_answer.rendered_answer",
                root_cause_layer="memo_logic_plan_economic_role_projection_or_writer_execution",
                repair_action=repair_action,
                evidence_refs=[context[:260]],
                verification_test="p30_root_cause_quality.economic_role_no_misuse",
            )
        )

    if "nvda" in prompt and "dell" in prompt:
        for ticker in ("AMZN", "MSFT", "GOOGL"):
            for context in _p30_windows_containing(text, ticker):
                lowered = context.lower()
                if any(term in context for term in ("供应商端", "供应商侧", "供应端")) and any(
                    term in lowered for term in ("product revenue", "产品收入", "承接需求", "供应商端已有")
                ):
                    add(
                        "peer_or_customer_capex_context_rendered_as_supplier_revenue",
                        [ticker],
                        context,
                        "Use economic_role/customer_or_demand_side_capex_signal: hyperscaler facts may support demand-pool context only, not supplier-side revenue or orders.",
                    )
                    break

    focus_tickers = [ticker.upper() for ticker in _string_list(case.get("focus_tickers")) if ticker]
    for ticker in focus_tickers:
        for context in _p30_windows_containing(text, ticker):
            if _p30_context_mentions_focus_ticker_own_capex(context, ticker) and _p30_context_affirms_own_capex_as_customer_demand(context):
                add(
                    "issuer_own_capex_rendered_as_customer_demand",
                    [ticker],
                    context,
                    "Use economic_role/issuer_own_capital_investment: focus issuer capex is own reinvestment, capacity preparation, or cash-flow pressure; do not render it as customer demand without a verified counterparty edge.",
                )
                break

    if "semicap" in case_id or any(ticker in prompt for ticker in ("asml", "amat", "lrcx", "klac")):
        for ticker in ("AMAT", "KLAC", "LRCX"):
            for context in _p30_windows_containing(text, ticker):
                if _p30_context_mentions_focus_ticker_own_capex(context, ticker) and _p30_context_affirms_own_capex_as_customer_demand(context):
                    add(
                        "issuer_own_capex_rendered_as_customer_demand",
                        [ticker],
                        context,
                        "Use economic_role/issuer_own_capital_investment: focus supplier capex is own reinvestment or cash-flow pressure, not customer demand without a verified counterparty edge.",
                    )
                    break
    return rows[:8]


def _p30_context_mentions_focus_ticker_own_capex(context: str, ticker: str) -> bool:
    value = str(context or "")
    ticker_text = str(ticker or "").upper().strip()
    lowered = value.lower()
    if not ticker_text:
        return False
    if not any(term in value for term in ("资本支出", "资本开支")) and not any(
        term in lowered for term in ("capex", "capital expenditure")
    ):
        return False
    direct_patterns = [
        rf"{re.escape(ticker_text)}\s*(?:的)?\s*(?:资本支出|资本开支)",
        rf"{re.escape(ticker_text)}\s*(?:在|于).{{0,48}}(?:资本支出|资本开支)",
        rf"{re.escape(ticker_text.lower())}\s*(?:capex|capital expenditure)",
        rf"{re.escape(ticker_text.lower())}.{{0,48}}(?:capex|capital expenditure)",
    ]
    if any(re.search(pattern, value if not pattern.islower() else lowered, flags=re.IGNORECASE) for pattern in direct_patterns):
        return True
    customer_capex_markers = (
        "客户资本支出",
        "客户的资本支出",
        "客户 capex",
        "客户capex",
        "需求端资本支出",
        "买方资本支出",
        "超大规模云服务商资本支出",
        "hyperscaler capex",
        "customer capex",
        "buyer capex",
        "demand-side capex",
    )
    if any(marker in lowered for marker in customer_capex_markers):
        return False
    return False


def _p30_windows_containing(text: str, term: str, *, radius: int = 110) -> list[str]:
    windows: list[str] = []
    raw_text = str(text or "")
    chunks = [chunk.strip() for chunk in re.split(r"(?<=[。！？.!?])\s+|\n+|\s+\|\s+", raw_text) if chunk.strip()]
    for chunk in chunks or [raw_text]:
        for match in re.finditer(re.escape(term), chunk, flags=re.IGNORECASE):
            windows.append(chunk[max(0, match.start() - radius) : min(len(chunk), match.end() + radius)])
    return windows


def _p30_context_affirms_own_capex_as_customer_demand(context: str) -> bool:
    value = str(context or "")
    lowered = value.lower()
    if "资本支出" not in value and "capex" not in lowered and "capital expenditure" not in lowered:
        return False
    if not any(term in value for term in ("需求端投入", "买方资本支出", "客户需求")) and not any(
        term in lowered for term in ("customer demand", "buyer capex", "demand-side")
    ):
        return False
    negated_patterns = [
        "非直接客户需求",
        "不是客户需求",
        "不是直接客户需求",
        "不是客户需求信号",
        "不能当作客户需求",
        "不能直接等同于客户需求",
        "不能直接等同于供应商营收",
        "不能直接等同于供应商收入",
        "不能直接等同于供应商订单",
        "不能直接等同于供应商backlog",
        "不能直接等同于供应商 backlog",
        "not customer demand",
        "not direct customer demand",
        "cannot be treated as customer demand",
        "cannot be read as customer demand",
        "cannot directly equal supplier revenue",
        "cannot be equated with supplier revenue",
    ]
    if any(pattern in lowered for pattern in negated_patterns if pattern.isascii()):
        return False
    if any(pattern in value for pattern in negated_patterns if not pattern.isascii()):
        return False
    return True


def _p30_focus_ticker_coverage_matrix(
    case: Mapping[str, Any],
    approved_facts: list[Mapping[str, Any]],
    supported_claims: list[Mapping[str, Any]],
    rendered_answer: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tickers = _string_list(case.get("focus_tickers")) or _string_list(case.get("search_scope_tickers"))[:4]
    rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    for ticker in [item.upper() for item in tickers if item]:
        fact_refs = [
            _diagnostic_text(row.get("evidence_ref") or row.get("fact_id"))
            for row in approved_facts
            if _diagnostic_text(row.get("ticker")).upper() == ticker
        ]
        product_fact_refs = [
            _diagnostic_text(row.get("evidence_ref") or row.get("fact_id") or row.get("selection_id"))
            for row in approved_facts
            if _diagnostic_text(row.get("ticker")).upper() == ticker and _p30_row_is_product_evidence(row)
        ]
        claim_refs = [
            _diagnostic_text(row.get("claim_id"))
            for row in supported_claims
            if ticker in {value.upper() for value in _string_list(row.get("ticker_scope"))}
            or ticker in _diagnostic_row_text(row).upper()
        ]
        product_claim_refs = [
            _diagnostic_text(row.get("claim_id"))
            for row in supported_claims
            if (
                ticker in {value.upper() for value in _string_list(row.get("ticker_scope"))}
                or ticker in _diagnostic_row_text(row).upper()
            )
            and _p30_row_is_product_evidence(row)
        ]
        financial_contradiction = _p30_rendered_says_missing_for_ticker(rendered_answer, ticker) and bool(fact_refs or claim_refs)
        product_contradiction = _p30_rendered_says_missing_product_for_ticker(rendered_answer, ticker) and bool(
            product_fact_refs or product_claim_refs
        )
        rows.append(
            {
                "ticker": ticker,
                "approved_fact_count": len([ref for ref in fact_refs if ref]),
                "product_fact_count": len([ref for ref in product_fact_refs if ref]),
                "supported_claim_count": len([ref for ref in claim_refs if ref]),
                "product_claim_count": len([ref for ref in product_claim_refs if ref]),
                "rendered_mentions_ticker": ticker in str(rendered_answer).upper(),
                "rendered_missing_contradiction": financial_contradiction or product_contradiction,
                "financial_missing_contradiction": financial_contradiction,
                "product_missing_contradiction": product_contradiction,
                "approved_fact_refs": [ref for ref in fact_refs if ref][:8],
                "product_fact_refs": [ref for ref in product_fact_refs if ref][:8],
                "claim_refs": [ref for ref in claim_refs if ref][:8],
                "product_claim_refs": [ref for ref in product_claim_refs if ref][:8],
            }
        )
        if financial_contradiction:
            root_rows.append(
                _p30_root_row(
                    case_id=case.get("case_id"),
                    symptom="memo_claims_missing_data_despite_available_evidence",
                    required_item_id=f"{ticker}_coverage",
                    tickers=[ticker],
                    earliest_faulty_artifact="memo_answer.rendered_answer",
                    root_cause_layer="memo_writer_or_memo_logic_plan_evidence_selection",
                    repair_action="trace why available fact/claim refs were not selected into MemoLogicPlan section before memo writer",
                    evidence_refs=[*fact_refs[:4], *claim_refs[:4]],
                    verification_test="p30_root_cause_quality.focus_ticker_no_evidence_contradiction",
                )
            )
        if product_contradiction:
            root_rows.append(
                _p30_root_row(
                    case_id=case.get("case_id"),
                    symptom="memo_claims_missing_product_data_despite_available_evidence",
                    required_item_id=f"{ticker}_product_coverage",
                    tickers=[ticker],
                    earliest_faulty_artifact="memo_answer.rendered_answer",
                    root_cause_layer="memo_writer_or_memo_logic_plan_product_evidence_selection",
                    repair_action="select exact product KPI/spec/deployment/product-context claims into MemoLogicPlan before emitting product-data absence",
                    evidence_refs=[*product_fact_refs[:4], *product_claim_refs[:4]],
                    verification_test="p30_root_cause_quality.focus_ticker_no_product_evidence_contradiction",
                )
            )
    return rows, root_rows


def _p30_rendered_says_missing_for_ticker(rendered_answer: str, ticker: str) -> bool:
    text = str(rendered_answer or "")
    for match in re.finditer(re.escape(ticker), text, flags=re.IGNORECASE):
        window = text[max(0, match.start() - 60) : min(len(text), match.end() + 90)].lower()
        if any(term in window for term in ("缺财务", "财务数据缺失", "缺少财务", "没有财务", "no financial", "missing financial", "financial data missing")):
            return True
    return False


def _p30_rendered_says_missing_product_for_ticker(rendered_answer: str, ticker: str) -> bool:
    text = str(rendered_answer or "")
    lower_text = text.lower()
    ticker_windows = []
    for match in re.finditer(re.escape(ticker), text, flags=re.IGNORECASE):
        ticker_windows.append(text[max(0, match.start() - 80) : min(len(text), match.end() + 150)].lower())
    if not ticker_windows and ticker.lower() in lower_text:
        ticker_windows.append(lower_text)
    product_markers = (
        "no runtime facts confirm",
        "no product data",
        "missing product",
        "product data missing",
        "product revenue not available",
        "no company-disclosed product",
        "no company product evidence",
        "product evidence missing",
        "缺少产品",
        "缺产品",
        "产品数据缺失",
        "没有产品",
        "没有 runtime facts",
        "没有运行时事实",
        "未确认产品",
        "无法确认产品",
        "缺少产品收入",
        "缺少产品级",
    )
    return any(any(marker in window for marker in product_markers) for window in ticker_windows)


def _p30_row_is_product_evidence(row: Mapping[str, Any]) -> bool:
    row_text = _diagnostic_row_text(row).lower()
    claim_type = _diagnostic_text(row.get("claim_type")).lower()
    metric_scope = " ".join(_string_list(row.get("metric_scope"))).lower()
    metric_id = _diagnostic_text(row.get("canonical_metric_id") or row.get("metric_id")).lower()
    source_role = _diagnostic_text(row.get("source_role") or row.get("evidence_role")).lower()
    if claim_type in {
        "company_reported_product_operating_fact",
        "technical_product_fact",
        "product_specification_fact",
        "product_architecture_fact",
        "product_taxonomy_context",
    }:
        return True
    product_markers = (
        "product_kpi",
        "product revenue",
        "product_revenue",
        "product_or_segment",
        "business segment",
        "segment revenue",
        "segment_revenue",
        "server",
        "servers and networking",
        "isg",
        "gpu",
        "blackwell",
        "h100",
        "h200",
        "b200",
        "gb200",
        "ai-optimized server",
        "deployment",
        "configured",
        "product surface",
        "official_product_surface",
        "customer_deployment",
    )
    combined = " ".join([row_text, metric_scope, metric_id, source_role])
    return any(marker in combined for marker in product_markers)


def _p30_required_item_matrix(
    case: Mapping[str, Any],
    *,
    required_items: list[Mapping[str, Any]],
    text: str,
    approved_facts: list[Mapping[str, Any]],
    supported_claims: list[Mapping[str, Any]],
    rendered_answer: str,
    memo_logic_plan: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    root_rows: list[dict[str, Any]] = []
    lower = str(text or "").lower()
    rendered_lower = str(rendered_answer or "").lower()
    answer_plan_ids = {
        _diagnostic_text(row.get("question_item_id"))
        for row in ((memo_logic_plan or {}).get("required_item_answer_plan") or [])
        if isinstance(row, Mapping)
    }
    for item in required_items:
        item_id = _diagnostic_text(item.get("item_id") or item.get("id") or item.get("required_item_id"))
        terms = [term.lower() for term in _string_list(item.get("terms_any") or item.get("terms"))]
        evidence_hit = any(term in lower for term in terms) if terms else False
        rendered_hit = any(term in rendered_lower for term in terms) if terms else False
        rendered_answer_status = _p30_required_item_rendered_answer_status(rendered_answer, item, terms=terms)
        rendered_judgment_hit = rendered_answer_status["status"] == "answered_with_judgment"
        if evidence_hit and rendered_judgment_hit:
            status = "covered"
        elif evidence_hit and rendered_hit:
            status = "term_only_or_boundary_only"
        elif evidence_hit:
            status = "available_not_rendered"
        else:
            status = "missing_or_not_selected"
        rows.append(
            {
                "item_id": item_id,
                "terms_any": terms,
                "status": status,
                "evidence_hit": evidence_hit,
                "rendered_hit": rendered_hit,
                "rendered_judgment_hit": rendered_judgment_hit,
                "answer_plan_present": item_id in answer_plan_ids if item_id else False,
                "rendered_answer_status": rendered_answer_status,
            }
        )
        if status != "covered":
            if status == "term_only_or_boundary_only":
                earliest = (
                    "memo_answer.rendered_answer"
                    if item_id in answer_plan_ids
                    else "memo_logic_plan.required_item_answer_plan"
                )
                symptom = "required_item_keyword_covered_without_analyst_judgment"
                root_layer = (
                    "memo_writer_required_item_answer_execution"
                    if item_id in answer_plan_ids
                    else "memo_logic_plan_required_item_answer_projection"
                )
                repair = (
                    "rewrite required-item section as answer-first analyst judgment with evidence bridge, counter-read, and what-would-change-view"
                )
            else:
                earliest = "memo_answer.rendered_answer" if evidence_hit else "retrieval_or_specialist_pack_selection"
                symptom = "required_item_not_covered"
                root_layer = "memo_logic_plan_evidence_selection" if evidence_hit else "research_lead_retrieval_or_specialist_selection"
                repair = "ensure required item is traced from retrieval to ClaimCard/MemoLogicPlan and final memo, or diagnose parser/source boundary"
            root_rows.append(
                _p30_root_row(
                    case_id=case.get("case_id"),
                    symptom=symptom,
                    required_item_id=item_id,
                    tickers=_string_list(case.get("focus_tickers")),
                    earliest_faulty_artifact=earliest,
                    root_cause_layer=root_layer,
                    repair_action=repair,
                    evidence_refs=_p30_refs_for_terms(terms, approved_facts, supported_claims)[:8],
                    verification_test="p30_root_cause_quality.required_items_covered",
                )
            )
    return rows, root_rows


def _p30_missing_required_item_answer_plan(
    required_items: list[Mapping[str, Any]],
    answer_plan_rows: list[Mapping[str, Any]],
) -> list[str]:
    required_ids = {
        _diagnostic_text(item.get("item_id") or item.get("id") or item.get("required_item_id"))
        for item in required_items
        if _diagnostic_text(item.get("item_id") or item.get("id") or item.get("required_item_id"))
    }
    plan_ids = {
        _diagnostic_text(item.get("question_item_id") or item.get("item_id") or item.get("required_item_id"))
        for item in answer_plan_rows
        if _diagnostic_text(item.get("question_item_id") or item.get("item_id") or item.get("required_item_id"))
    }
    return sorted(required_ids - plan_ids)


def _p30_required_item_plan_projection_missing(
    *,
    required_items: list[Mapping[str, Any]],
    required_item_answer_plan_rows: list[Mapping[str, Any]],
    summary_memo_logic_plan: Mapping[str, Any],
) -> bool:
    if not required_items:
        return False
    required_ids = {
        _diagnostic_text(item.get("item_id") or item.get("id") or item.get("required_item_id"))
        for item in required_items
        if _diagnostic_text(item.get("item_id") or item.get("id") or item.get("required_item_id"))
    }
    runtime_plan_ids = {
        _diagnostic_text(item.get("question_item_id") or item.get("item_id") or item.get("required_item_id"))
        for item in required_item_answer_plan_rows
        if _diagnostic_text(item.get("question_item_id") or item.get("item_id") or item.get("required_item_id"))
    }
    if not required_ids <= runtime_plan_ids:
        return False
    projected_rows = [
        row for row in summary_memo_logic_plan.get("required_item_answer_plan") or [] if isinstance(row, Mapping)
    ]
    projected_ids = {
        _diagnostic_text(item.get("question_item_id") or item.get("item_id") or item.get("required_item_id"))
        for item in projected_rows
        if _diagnostic_text(item.get("question_item_id") or item.get("item_id") or item.get("required_item_id"))
    }
    projected_count = int(summary_memo_logic_plan.get("required_item_answer_plan_count") or len(projected_rows))
    return not (required_ids <= projected_ids and projected_count >= len(required_ids))


def _p30_required_item_rendered_answer_status(
    rendered_answer: str,
    item: Mapping[str, Any],
    *,
    terms: list[str],
) -> dict[str, Any]:
    text = str(rendered_answer or "")
    windows = _p30_required_item_windows(text, terms)
    if not windows:
        return {"status": "not_rendered", "judgment_window_count": 0, "boundary_only_window_count": 0}
    judgment_windows = [window for window in windows if _p30_required_item_window_has_judgment(window, item)]
    boundary_only = [
        window
        for window in windows
        if _p30_required_item_window_is_boundary_only(window) and not _p30_required_item_window_has_judgment(window, item)
    ]
    if judgment_windows:
        return {
            "status": "answered_with_judgment",
            "judgment_window_count": len(judgment_windows),
            "boundary_only_window_count": len(boundary_only),
        }
    if boundary_only:
        return {
            "status": "boundary_or_watchlist_only",
            "judgment_window_count": 0,
            "boundary_only_window_count": len(boundary_only),
        }
    return {"status": "keyword_only", "judgment_window_count": 0, "boundary_only_window_count": 0}


def _p30_required_item_windows(text: str, terms: list[str]) -> list[str]:
    if not text or not terms:
        return []
    windows: list[str] = []
    lowered = text.lower()
    for term in terms:
        if not term:
            continue
        start = 0
        term_lower = term.lower()
        while True:
            index = lowered.find(term_lower, start)
            if index < 0:
                break
            windows.append(text[max(0, index - 120) : min(len(text), index + len(term) + 180)])
            start = index + max(1, len(term))
            if len(windows) >= 24:
                return windows
    return windows


def _p30_required_item_window_has_judgment(window: str, item: Mapping[str, Any]) -> bool:
    value = str(window or "").lower()
    judgment_terms = (
        "说明",
        "意味着",
        "支撑",
        "压制",
        "改善",
        "恶化",
        "反映",
        "对应",
        "传导",
        "回报",
        "质量",
        "风险",
        "利好",
        "利空",
        "正向",
        "负向",
        "受益",
        "拖累",
        "压力",
        "强于",
        "弱于",
        "只能作为",
        "不能形成",
        "supports",
        "implies",
        "therefore",
        "because",
        "pressure",
        "quality",
        "risk",
        "read-through",
        "bridge",
        "benefit",
        "weaken",
    )
    return any(term in value for term in judgment_terms)


def _p30_required_item_window_is_boundary_only(window: str) -> bool:
    value = str(window or "").lower()
    boundary_terms = (
        "缺口",
        "缺乏",
        "缺少",
        "缺失",
        "无法",
        "不能",
        "不足",
        "未披露",
        "尚未",
        "边界",
        "需要",
        "继续验证",
        "后续",
        "跟踪",
        "not available",
        "cannot",
        "missing",
        "insufficient",
        "limited",
        "needs verification",
        "watch",
    )
    mechanism_terms = ("说明", "意味着", "支撑", "传导", "回报", "质量", "风险", "supports", "implies", "read-through")
    return sum(value.count(term) for term in boundary_terms) >= 2 and not any(term in value for term in mechanism_terms)


def _p30_refs_for_terms(terms: list[str], approved_facts: list[Mapping[str, Any]], supported_claims: list[Mapping[str, Any]]) -> list[str]:
    refs: list[str] = []
    for row in [*approved_facts, *supported_claims]:
        text = _diagnostic_row_text(row).lower()
        if terms and not any(term in text for term in terms):
            continue
        ref = _diagnostic_text(row.get("evidence_ref") or row.get("claim_id") or row.get("fact_id"))
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def _p30_non_us_disclosure_diagnostics(
    case: Mapping[str, Any],
    result: Mapping[str, Any],
    approved_facts: list[Mapping[str, Any]],
    supported_claims: list[Mapping[str, Any]],
    gap_rows: list[Mapping[str, Any]],
    rendered_answer: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tickers = {ticker.upper() for ticker in _string_list(case.get("focus_tickers")) + _string_list(case.get("search_scope_tickers"))}
    if "ASML" not in tickers:
        return rows
    repair_rows = _p30_lead_repair_context_rows(result)
    combined_rows = [*supported_claims, *gap_rows, *repair_rows]
    official_presence_refs = []
    for row in combined_rows:
        text = _diagnostic_row_text(row).lower()
        if "asml" in text and any(term in text for term in ("6-k", "20-f", "annual report", "quarterly results", "ir", "local filing")):
            ref = _diagnostic_text(row.get("evidence_ref") or row.get("claim_id") or row.get("gap_id") or row.get("source_id"))
            if ref:
                official_presence_refs.append(ref)
    asml_fact_refs = [
        _diagnostic_text(row.get("evidence_ref") or row.get("fact_id"))
        for row in approved_facts
        if _diagnostic_text(row.get("ticker")).upper() == "ASML"
    ]
    parser_diagnosis_complete = _p30_non_us_parser_diagnosis_complete(combined_rows)
    if official_presence_refs and not asml_fact_refs and not parser_diagnosis_complete:
        rows.append(
            _p30_root_row(
                case_id=case.get("case_id"),
                symptom="non_us_official_source_located_but_no_promoted_fact",
                required_item_id="ASML_non_us_disclosure_parser",
                tickers=["ASML"],
                earliest_faulty_artifact="official_source_context_rows",
                root_cause_layer="non_us_disclosure_parser_or_table_extraction",
                repair_action="diagnose whether ASML 6-K/20-F/IR tables were fetched but not parsed, parsed without numeric rows, or blocked by route scope",
                evidence_refs=official_presence_refs[:8],
                verification_test="p30_root_cause_quality.non_us_official_source_gaps_have_parser_diagnosis",
            )
        )
    return rows


def _p30_lead_repair_context_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    execution = result.get("lead_targeted_repair_execution") if isinstance(result.get("lead_targeted_repair_execution"), Mapping) else {}
    rows.extend(dict(row) for row in execution.get("context_rows") or [] if isinstance(row, Mapping))
    rows.extend(dict(row) for row in execution.get("official_context_summaries") or [] if isinstance(row, Mapping))
    checkpoint = result.get("lead_review_checkpoint") if isinstance(result.get("lead_review_checkpoint"), Mapping) else {}
    nested_execution = (
        checkpoint.get("lead_targeted_repair_execution")
        if isinstance(checkpoint.get("lead_targeted_repair_execution"), Mapping)
        else {}
    )
    rows.extend(dict(row) for row in nested_execution.get("context_rows") or [] if isinstance(row, Mapping))
    rows.extend(dict(row) for row in nested_execution.get("official_context_summaries") or [] if isinstance(row, Mapping))
    return _dedupe_diagnostic_rows(rows, keys=("evidence_ref", "snapshot_id", "url"))


def _p30_non_us_parser_diagnosis_complete(rows: list[Mapping[str, Any]]) -> bool:
    for row in rows:
        text = _diagnostic_row_text(row).lower()
        if "asml" not in text:
            continue
        diagnosis = row.get("parser_diagnosis") if isinstance(row.get("parser_diagnosis"), Mapping) else {}
        complete = bool(row.get("parser_diagnosis_complete") or diagnosis.get("parser_diagnosis_complete"))
        failure_reason = _diagnostic_text(
            row.get("exact_fact_parser_failure_reason")
            or row.get("parser_failure_reason")
            or "; ".join(_string_list(diagnosis.get("exact_fact_parser_failure_reasons")))
        )
        next_action = _diagnostic_text(row.get("next_parser_action") or "; ".join(_string_list(diagnosis.get("next_parser_actions"))))
        parser_status = _diagnostic_text(
            row.get("source_specific_parser_status")
            or row.get("exact_value_parser_status")
            or "; ".join(_string_list(diagnosis.get("source_specific_parser_statuses")))
        )
        if complete and failure_reason and next_action and parser_status:
            return True
    return False


def _p30_root_row(
    *,
    case_id: Any,
    symptom: str,
    required_item_id: str,
    tickers: list[str],
    earliest_faulty_artifact: str,
    root_cause_layer: str,
    repair_action: str,
    evidence_refs: list[str],
    verification_test: str,
) -> dict[str, Any]:
    key = json.dumps(
        {
            "case_id": case_id,
            "symptom": symptom,
            "required_item_id": required_item_id,
            "tickers": tickers,
            "artifact": earliest_faulty_artifact,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return {
        "symptom_id": f"p30_{hashlib.sha1(key.encode('utf-8')).hexdigest()[:12]}",
        "case_id": str(case_id or ""),
        "required_item_id": required_item_id,
        "affected_tickers": [ticker.upper() for ticker in tickers if ticker],
        "symptom": symptom,
        "earliest_faulty_artifact": earliest_faulty_artifact,
        "root_cause_layer": root_cause_layer,
        "owned_by_project": True,
        "repairability": "root_cause_repair_required",
        "repair_action": repair_action,
        "evidence_refs_or_attempt_refs": [ref for ref in evidence_refs if ref],
        "why_not_external_gap": "classified as internal until parser/locator/adapter/context/writer path is attempted and documented",
        "verification_test": verification_test,
        "status": "open",
    }


def _p30_root_row_complete(row: Mapping[str, Any]) -> bool:
    required = {
        "symptom_id",
        "case_id",
        "required_item_id",
        "earliest_faulty_artifact",
        "root_cause_layer",
        "owned_by_project",
        "repairability",
        "repair_action",
        "why_not_external_gap",
        "verification_test",
        "status",
    }
    return all(_diagnostic_text(row.get(key)) if key != "owned_by_project" else isinstance(row.get(key), bool) for key in required)


def _supervising_analyst_pack_checks(case: Mapping[str, Any], *, result: Mapping[str, Any]) -> dict[str, Any]:
    expected_mode = str(case.get("expected_execution_mode") or "")
    required = bool(
        case.get("require_supervising_analyst_pack")
        or (case.get("require_investment_memo_quality") and expected_mode == "deep_research")
    )
    pack = result.get("supervising_analyst_pack") if isinstance(result.get("supervising_analyst_pack"), Mapping) else {}
    summary = result.get("multi_agent_summary") if isinstance(result.get("multi_agent_summary"), Mapping) else {}
    summary_pack = summary.get("supervising_analyst_pack") if isinstance(summary.get("supervising_analyst_pack"), Mapping) else {}
    financial = pack.get("financial_analysis_model") if isinstance(pack.get("financial_analysis_model"), Mapping) else {}
    product = pack.get("product_bridge_pack") if isinstance(pack.get("product_bridge_pack"), Mapping) else {}
    graph = pack.get("capital_transmission_graph") if isinstance(pack.get("capital_transmission_graph"), Mapping) else {}
    synthesis = pack.get("research_lead_synthesis_plan") if isinstance(pack.get("research_lead_synthesis_plan"), Mapping) else {}
    validation = pack.get("validation") if isinstance(pack.get("validation"), Mapping) else {}
    key_line_items = [row for row in financial.get("key_line_items") or [] if isinstance(row, Mapping)]
    product_kpis = [row for row in product.get("company_disclosed_product_kpis") or [] if isinstance(row, Mapping)]
    product_context = [row for row in product.get("official_product_context") or [] if isinstance(row, Mapping)]
    edges = [row for row in graph.get("edges") or [] if isinstance(row, Mapping)]
    writer_directives = _string_list(synthesis.get("writer_directives"))
    checks = {
        "pack_present": bool(pack) if required else True,
        "validation_pass": (validation.get("status") == "pass") if required and pack else True,
        "financial_analysis_model_present": bool(key_line_items) if required else True,
        "product_bridge_present": (bool(product_kpis) or bool(product_context)) if required else True,
        "capital_transmission_graph_present": bool(edges) if required else True,
        "research_lead_synthesis_plan_present": bool(str(synthesis.get("core_judgment") or "").strip()) if required else True,
        "writer_directives_present": bool(writer_directives) if required else True,
        "summary_tracks_pack": bool(summary_pack) if required else True,
    }
    return {
        "schema_version": "sec_agent_supervising_analyst_pack_eval_check_v0.1",
        "required": required,
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "metrics": {
            "key_line_item_count": len(key_line_items),
            "product_kpi_count": len(product_kpis),
            "product_context_count": len(product_context),
            "capital_edge_count": len(edges),
            "writer_directive_count": len(writer_directives),
        },
        "summary": dict(summary_pack) if isinstance(summary_pack, Mapping) else {},
        "policy": "deep_research_requires_research_lead_supervising_analyst_pack_v0_1",
    }


def _source_layer_capability_checks(
    case: Mapping[str, Any],
    *,
    result: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    required_layers = _string_list(case.get("required_source_layers"))
    required = bool(
        case.get("require_source_layer_capability_audit")
        or case.get("require_l2_l3_l4_source_audit")
        or required_layers
    )
    if required and not required_layers:
        required_layers = ["L2", "L3", "L4"]

    audit = result.get("source_layer_capability_audit") if isinstance(result.get("source_layer_capability_audit"), Mapping) else {}
    summary_audit = summary.get("source_layer_capability_audit") if isinstance(summary.get("source_layer_capability_audit"), Mapping) else {}
    if not audit and summary_audit:
        audit = summary_audit

    rows = [dict(row) for row in audit.get("rows") or [] if isinstance(row, Mapping)]
    audit_summary = audit.get("summary") if isinstance(audit.get("summary"), Mapping) else {}
    if not audit_summary and summary_audit:
        audit_summary = summary_audit
    by_layer = audit_summary.get("by_layer") if isinstance(audit_summary.get("by_layer"), Mapping) else {}
    by_status = (
        audit_summary.get("by_evidence_graph_status")
        if isinstance(audit_summary.get("by_evidence_graph_status"), Mapping)
        else {}
    )
    validation = audit.get("validation") if isinstance(audit.get("validation"), Mapping) else {}
    validation_status = str(validation.get("status") or audit.get("validation_status") or summary_audit.get("validation_status") or "")
    source_count = int(audit_summary.get("source_count") or len(rows) or 0)
    context_or_proxy_allowed_count = int(
        audit_summary.get("context_or_proxy_allowed_count")
        or sum(1 for row in rows if bool(row.get("context_or_proxy_allowed")))
        or 0
    )
    expected_missing_count = int(
        audit_summary.get("expected_missing_count")
        or int(by_status.get("not_registered") or 0)
        or sum(1 for row in rows if str(row.get("evidence_graph_status") or "") == "not_registered")
        or 0
    )
    exact_authority_ready_count = int(
        audit_summary.get("exact_authority_ready_count")
        or sum(1 for row in rows if bool(row.get("exact_value_authority_ready")))
        or 0
    )
    layer_counts = {
        layer: _source_layer_count(layer, by_layer=by_layer, rows=rows)
        for layer in required_layers
    }
    non_l1_exact_violations = [
        str(row.get("source_id") or "")
        for row in rows
        if str(row.get("layer_id") or "") in {"L2", "L3", "L4"}
        and (bool(row.get("can_support_company_exact_fact")) or bool(row.get("exact_value_authority_ready")))
    ]
    checks = {
        "audit_present": source_count > 0 if required else True,
        "validation_pass": validation_status == "pass" if required and validation_status else True,
        "required_layers_visible": all(count > 0 for count in layer_counts.values()) if required_layers else True,
        "context_or_proxy_allowed_present": context_or_proxy_allowed_count > 0 if required else True,
        "evidence_graph_status_distribution_present": bool(by_status) if required else True,
        "expected_missing_sources_exposed": expected_missing_count > 0 if required else True,
        "non_l1_exact_authority_absent": not non_l1_exact_violations,
    }
    return {
        "schema_version": "sec_agent_source_layer_capability_eval_check_v0.1",
        "required": required,
        "status": "pass" if all(checks.values()) else "fail",
        "required_layers": required_layers,
        "metrics": {
            "source_count": source_count,
            "context_or_proxy_allowed_count": context_or_proxy_allowed_count,
            "expected_missing_count": expected_missing_count,
            "exact_authority_ready_count": exact_authority_ready_count,
            "layer_counts": layer_counts,
            "by_evidence_graph_status": dict(by_status),
            "validation_status": validation_status,
            "non_l1_exact_violation_sources": non_l1_exact_violations,
        },
        "checks": checks,
        "policy": "l2_l3_l4_sources_must_be_visible_and_bounded_before_gap_or_memo_use_v0_1",
    }


def _source_layer_count(layer_id: str, *, by_layer: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> int:
    layer = by_layer.get(layer_id) if isinstance(by_layer.get(layer_id), Mapping) else {}
    if layer:
        return int(layer.get("count") or 0)
    return sum(1 for row in rows if str(row.get("layer_id") or "") == layer_id)


def _role_source_layer_distribution_checks(
    case: Mapping[str, Any],
    *,
    result: Mapping[str, Any],
    summary: Mapping[str, Any],
) -> dict[str, Any]:
    required = bool(case.get("require_role_source_layer_distribution") or case.get("require_role_visible_source_layer_audit"))
    expected_roles = set(_string_list(case.get("expected_specialist_agents")))
    barrier = result.get("specialist_fanout_barrier") if isinstance(result.get("specialist_fanout_barrier"), Mapping) else {}
    summary_barriers = summary.get("graph_barriers") if isinstance(summary.get("graph_barriers"), Mapping) else {}
    summary_specialist = (
        summary_barriers.get("specialist_fanout")
        if isinstance(summary_barriers.get("specialist_fanout"), Mapping)
        else {}
    )
    distribution = barrier.get("source_layer_distribution") if isinstance(barrier.get("source_layer_distribution"), Mapping) else {}
    if not distribution and isinstance(summary_specialist.get("source_layer_distribution"), Mapping):
        distribution = summary_specialist.get("source_layer_distribution") or {}
    route_results = [dict(row) for row in result.get("specialist_route_results") or [] if isinstance(row, Mapping)]
    route_distribution_roles = {
        str(row.get("agent_id") or "")
        for row in route_results
        if isinstance(row.get("source_layer_distribution"), Mapping) and row.get("source_layer_distribution")
    }
    roles = distribution.get("roles") if isinstance(distribution.get("roles"), Mapping) else {}
    available_roles = set(str(role) for role in roles) | route_distribution_roles
    if not expected_roles:
        expected_roles = {
            str(row.get("agent_id") or "")
            for row in route_results
            if str(row.get("agent_id") or "") and str(row.get("status") or "") != "skipped"
        }
    exact_violation_roles = [
        str(role)
        for role, row in roles.items()
        if isinstance(row, Mapping) and row.get("exact_authority_violation_sources")
    ]
    gap_roles = set(_string_list(distribution.get("gap_roles")))
    selected_missing_roles = {
        str(role)
        for role, row in roles.items()
        if isinstance(row, Mapping) and row.get("selected_missing_required_layers")
    }
    selector_gap_roles = sorted(gap_roles | selected_missing_roles)
    missing_expected_roles = sorted(role for role in expected_roles if role and role not in available_roles)
    checks = {
        "distribution_present": bool(distribution) if required else True,
        "expected_roles_present": not missing_expected_roles if required and expected_roles else True,
        "exact_authority_violation_absent": not exact_violation_roles,
        "selector_gaps_are_explicit": (
            all(role in selector_gap_roles or role in available_roles for role in expected_roles)
            if required and expected_roles
            else True
        ),
        "gap_status_allowed": (
            str(distribution.get("status") or "") in {"pass", "gap"}
            if required and distribution
            else True
        ),
        "no_silent_empty_role_distribution": (
            all(int((roles.get(role) or {}).get("candidate_count") or 0) > 0 or role in selector_gap_roles for role in expected_roles if role in roles)
            if required and roles
            else True
        ),
    }
    if case.get("fail_on_role_source_layer_gaps"):
        checks["no_selector_gap_roles"] = not selector_gap_roles
    else:
        checks["no_selector_gap_roles"] = True
    return {
        "schema_version": "sec_agent_role_source_layer_distribution_eval_check_v0.1",
        "required": required,
        "status": "pass" if all(checks.values()) else "fail",
        "expected_roles": sorted(expected_roles),
        "available_roles": sorted(available_roles),
        "missing_expected_roles": missing_expected_roles,
        "selector_gap_roles": selector_gap_roles,
        "exact_authority_violation_roles": exact_violation_roles,
        "distribution_status": distribution.get("status") or "",
        "checks": checks,
        "policy": "role_source_layer_distribution_must_be_visible_with_explicit_selector_gaps_v0_1",
    }


def _diagnostic_approved_facts(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    fact_selection = result.get("pre_memo_fact_selection") if isinstance(result.get("pre_memo_fact_selection"), Mapping) else {}
    rows = [dict(row) for row in fact_selection.get("approved_facts") or [] if isinstance(row, Mapping)]
    gates = result.get("deterministic_gates") if isinstance(result.get("deterministic_gates"), Mapping) else {}
    nested = gates.get("pre_memo_fact_selection") if isinstance(gates.get("pre_memo_fact_selection"), Mapping) else {}
    rows.extend(dict(row) for row in nested.get("approved_facts") or [] if isinstance(row, Mapping))
    return _dedupe_diagnostic_rows(rows, keys=("selection_id", "fact_id", "evidence_ref"))


def _diagnostic_supported_claims(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    judgment = result.get("verified_judgment_plan") if isinstance(result.get("verified_judgment_plan"), Mapping) else {}
    rows.extend(dict(row) for row in judgment.get("supported_claims") or [] if isinstance(row, Mapping))
    claim_store = result.get("claim_card_store") if isinstance(result.get("claim_card_store"), Mapping) else {}
    rows.extend(dict(row) for row in claim_store.get("supported_claims") or [] if isinstance(row, Mapping))
    rows.extend(dict(row) for row in claim_store.get("claim_cards") or [] if isinstance(row, Mapping))
    for output in result.get("specialist_outputs") or []:
        if not isinstance(output, Mapping):
            continue
        for observation in output.get("observations") or []:
            if isinstance(observation, Mapping) and not bool(observation.get("unsupported")):
                rows.append(dict(observation))
    return _dedupe_diagnostic_rows(rows, keys=("claim_id", "claim", "evidence_refs"))


def _diagnostic_gap_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    register = result.get("bounded_gap_register") if isinstance(result.get("bounded_gap_register"), Mapping) else {}
    rows.extend(dict(row) for row in register.get("gaps") or [] if isinstance(row, Mapping))
    fact_selection = result.get("pre_memo_fact_selection") if isinstance(result.get("pre_memo_fact_selection"), Mapping) else {}
    rows.extend(dict(row) for row in fact_selection.get("bounded_gap_links") or [] if isinstance(row, Mapping))
    judgment = result.get("verified_judgment_plan") if isinstance(result.get("verified_judgment_plan"), Mapping) else {}
    constraints = judgment.get("memo_constraints") if isinstance(judgment.get("memo_constraints"), Mapping) else {}
    rows.extend(dict(row) for row in constraints.get("missing_evidence") or [] if isinstance(row, Mapping))
    memo = result.get("memo_answer") if isinstance(result.get("memo_answer"), Mapping) else {}
    rows.extend(dict(row) for row in memo.get("missing_evidence") or [] if isinstance(row, Mapping))
    return _dedupe_diagnostic_rows(rows, keys=("gap_id", "gap_type", "reason"))


def _dedupe_diagnostic_rows(rows: list[dict[str, Any]], *, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for row in rows:
        key = "|".join(json.dumps(row.get(item), sort_keys=True, ensure_ascii=False, default=str) for item in keys)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _diagnostic_numeric_sanity_violations(approved_facts: list[Mapping[str, Any]]) -> list[dict[str, str]]:
    currency_metrics = {
        "financial_metric:revenue",
        "financial_metric:gross_profit",
        "financial_metric:cost_of_revenue",
        "financial_metric:operating_income",
        "financial_metric:operating_cash_flow",
        "financial_metric:fcf",
        "financial_metric:capex",
        "financial_metric:debt",
        "financial_metric:cash",
        "financial_metric:inventory",
        "product_kpi:product_revenue",
    }
    violations: list[dict[str, str]] = []
    for row in approved_facts:
        metric = _diagnostic_text(row.get("canonical_metric_id"))
        unit = _diagnostic_text(row.get("unit")).lower()
        text = _diagnostic_row_text(row).lower()
        unit_family = _diagnostic_unit_family(unit)
        if metric in currency_metrics and unit_family and unit_family != "currency":
            violations.append({"fact_id": _diagnostic_text(row.get("fact_id")), "reason": "currency_metric_non_currency_unit", "metric": metric, "unit": unit})
        if metric == "financial_metric:revenue" and _diagnostic_revenue_label_is_noise(text):
            violations.append({"fact_id": _diagnostic_text(row.get("fact_id")), "reason": "revenue_metric_semantic_noise", "metric": metric, "unit": unit})
        if metric == "financial_metric:gross_margin" and unit_family and unit_family != "percent":
            violations.append({"fact_id": _diagnostic_text(row.get("fact_id")), "reason": "gross_margin_non_percent_unit", "metric": metric, "unit": unit})
        if metric in {"financial_metric:gross_margin", "financial_metric:gross_profit"} and _diagnostic_profitability_label_is_noise(text):
            violations.append({"fact_id": _diagnostic_text(row.get("fact_id")), "reason": "profitability_metric_semantic_noise", "metric": metric, "unit": unit})
        if metric == "product_kpi:backlog":
            if unit_family == "percent":
                violations.append({"fact_id": _diagnostic_text(row.get("fact_id")), "reason": "backlog_percent_unit", "metric": metric, "unit": unit})
            if any(
                term in text
                for term in (
                    "corporate debt securities",
                    "corporate notes",
                    "corporate and other assets",
                    "corporate_and_other_assets",
                    "long-term debt",
                    "long term debt",
                    "long_term_debt",
                    "debt securities",
                    "debt_securities",
                    "unamortized discount",
                    "unamortized_discount",
                    "issuance costs",
                    "issuance_costs",
                    "bonds",
                )
            ):
                violations.append({"fact_id": _diagnostic_text(row.get("fact_id")), "reason": "backlog_debt_semantic_noise", "metric": metric, "unit": unit})
    return violations


def _diagnostic_revenue_label_is_noise(text: str) -> bool:
    raw = str(text or "").lower().replace("_", " ")
    return any(
        term in raw
        for term in (
            "deferred revenue",
            "deferred system revenue",
            "remaining performance obligation",
            " rpo ",
            "contract liability",
            "contract liabilities",
            "cost of revenue",
            "costs of revenue",
            "cost of sales",
            "proceeds from sales",
            "realized gain",
            "receivables sold",
            "factoring",
            "letter of credit",
        )
    )


def _diagnostic_profitability_label_is_noise(text: str) -> bool:
    raw = str(text or "").lower()
    return any(
        term in raw
        for term in (
            "cash flow",
            "cash_flow",
            "cash provided by",
            "cash from operations",
            "operating activities",
            "operating_activities",
            "financing activities",
            "investing activities",
            "earnings per share",
            "earnings_per_share",
            "diluted",
            "basic",
            "eps",
        )
    )


def _diagnostic_unit_family(unit: str) -> str:
    raw = str(unit or "").strip().lower()
    if not raw:
        return ""
    if raw in {
        "usd",
        "$",
        "dollars",
        "usd_millions",
        "usd millions",
        "usd_billions",
        "usd billions",
        "usd_thousands",
        "usd thousands",
        "currency",
    }:
        return "currency"
    if raw in {"%", "percent", "percentage"}:
        return "percent"
    if raw in {"shares", "share"}:
        return "shares"
    if raw in {"units", "vehicles", "devices", "systems"}:
        return "units"
    if "per share" in raw:
        return "currency_per_share"
    return "other"


def _diagnostic_product_evidence_present(
    approved_facts: list[Mapping[str, Any]],
    supported_claims: list[Mapping[str, Any]],
) -> bool:
    return any(_diagnostic_row_has_product_signal(row) for row in approved_facts) or any(
        _diagnostic_claim_has_product_signal(row) for row in supported_claims
    )


def _diagnostic_row_has_product_signal(row: Mapping[str, Any]) -> bool:
    metric = _diagnostic_text(row.get("canonical_metric_id"))
    if metric.startswith("product_kpi:"):
        return True
    return bool(_diagnostic_text(row.get("product_or_segment")))


def _diagnostic_claim_has_product_signal(row: Mapping[str, Any]) -> bool:
    if _diagnostic_text(row.get("analysis_dimension")) == "product_and_production":
        return True
    if _diagnostic_text(row.get("memo_slot")) == "product_and_production":
        return True
    if any(str(metric).startswith("product_kpi:") for metric in _string_list(row.get("metric_scope"))):
        return True
    return bool(_diagnostic_text(row.get("product_or_segment")))


def _diagnostic_dimension_has_claim_or_evidence(row: Mapping[str, Any]) -> bool:
    return bool(
        _string_list(row.get("claim_ids"))
        or _string_list(row.get("primary_claim_ids"))
        or _string_list(row.get("evidence_refs"))
        or _string_list(row.get("refs"))
    )


def _diagnostic_product_gap_present(gap_rows: list[Mapping[str, Any]]) -> bool:
    product_gap_terms = (
        "product",
        "产品",
        "asp",
        "unit",
        "shipment",
        "sell-through",
        "sales",
        "channel",
        "inventory",
        "tracker",
        "commercial",
        "idc",
        "counterpoint",
        "gartner",
        "iqvia",
        "symphony",
        "prescription",
        "clinical",
        "trial",
        "approval",
        "订单",
        "销量",
        "份额",
        "库存",
        "处方",
        "临床",
        "监管",
    )
    for row in gap_rows:
        text = _diagnostic_row_text(row).lower()
        if any(term in text for term in product_gap_terms):
            return True
    return False


def _diagnostic_row_text(row: Mapping[str, Any]) -> str:
    values: list[str] = []
    stack = list(row.values())
    while stack:
        value = stack.pop(0)
        if isinstance(value, (str, int, float, bool)):
            text = _diagnostic_text(value)
            if text:
                values.append(text)
        elif isinstance(value, Mapping):
            stack.extend(value.values())
        elif isinstance(value, (list, tuple, set)):
            stack.extend(value)
    return " ".join(values)


def _diagnostic_required_term_present(text: str, term: str) -> bool:
    haystack = _diagnostic_match_text(text)
    needle = _diagnostic_match_text(term)
    if not needle:
        return True
    if needle in haystack:
        return True
    singular = " ".join(
        token[:-1] if token.endswith("s") and len(token) > 3 else token
        for token in needle.split()
    )
    return bool(singular and singular in haystack)


def _diagnostic_match_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", " ", str(value or "").lower())).strip()


def _diagnostic_text(value: Any) -> str:
    return str(value or "").strip()


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
    latin_text = re.sub(
        r"\b(?:[A-Z]{1,8}|10-[KQ]|20-F|6-K|8-K|S-[13]|GAAP|SEC|FY\d{2,4}|Q[1-4]|AI|EV|GPU|CPU|API|SaaS)\b",
        " ",
        text,
    )
    latin_words = len(re.findall(r"[A-Za-z]{3,}", latin_text))
    return cjk_count >= 60 and latin_words <= max(28, cjk_count // 5)


def _rendered_has_english_template_prose(rendered_answer: str) -> bool:
    value = str(rendered_answer or "").lower()
    markers = (
        "the evidence supports",
        "the evidence frames",
        "the evidence links",
        "caveat:",
        "missing confirmation:",
        "period changes compare",
        "not strictly same-period",
        "non-gaap measure",
        "gaap gross margin",
        "company-reported orders/backlog",
    )
    return any(marker in value for marker in markers)


def _rendered_opening_is_template_salvage(rendered_answer: str, expected_language: str) -> bool:
    text = str(rendered_answer or "")
    opening = (_opening_section_text(text, expected_language) or text[:700]).lower()
    markers = (
        "当前证据更适合形成一份谨慎的分维度判断",
        "当前证据不足以支持强方向结论",
        "缺失的订单、份额或商业 tracker",
        "缺少的订单、份额或商业 tracker",
        "available evidence supports a cautious",
        "available evidence does not support a strong directional",
        "missing orders, share, and commercial tracker",
    )
    if any(marker.lower() in opening for marker in markers):
        return True
    return False


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


def _load_cases(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.case_catalog_path:
        catalog = load_case_catalog(args.case_catalog_path)
        cases = expand_case_catalog(catalog, subset=args.case_subset or None)
        if args.case_family:
            selected_families = {str(family) for family in args.case_family}
            cases = [case for case in cases if str(case.get("catalog_case_family") or "") in selected_families]
        setattr(
            args,
            "_resolved_case_catalog",
            {
                "catalog_path": str(args.case_catalog_path.resolve()),
                "catalog_id": str(catalog.get("catalog_id") or ""),
                "schema_version": str(catalog.get("schema_version") or ""),
                "case_subset": str(args.case_subset or ""),
                "case_family_filter": list(args.case_family or []),
            },
        )
        return _selected_cases(cases, args)
    setattr(args, "_resolved_case_catalog", {})
    return _selected_cases(_read_jsonl(args.cases_path), args)


def _dry_run_case_summary(
    *,
    args: argparse.Namespace,
    cases: list[Mapping[str, Any]],
    run_id: str,
    output_dir: Path,
) -> dict[str, Any]:
    catalog = getattr(args, "_resolved_case_catalog", {}) or {}
    return {
        "schema_version": "sec_agent_multi_agent_real_llm_chain_case_resolution_v0.1",
        "run_id": run_id,
        "status": "pass",
        "dry_run_cases": True,
        "case_count": len(cases),
        "cases_path": str(args.cases_path.resolve()) if not args.case_catalog_path else "",
        "case_catalog": catalog,
        "output_dir": str(output_dir.resolve()),
        "case_ids": [str(case.get("case_id") or "") for case in cases],
        "case_families": {
            family: sum(1 for case in cases if str(case.get("catalog_case_family") or "") == family)
            for family in sorted({str(case.get("catalog_case_family") or "") for case in cases if case.get("catalog_case_family")})
        },
    }


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
    if not plan_reflection and isinstance(result.get("plan_reflection_report"), Mapping):
        plan_reflection = result.get("plan_reflection_report")  # type: ignore[assignment]
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
        "required": any((required, require_plan_reflection, require_fusion, require_gap_register, require_graph_barriers, require_milvus)),
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
    config_runtime = _milvus_runtime_from_config_env()
    merged_runtime = {**config_runtime, **dict(runtime)}
    context = {
        "milvus_runtime": merged_runtime,
        "milvus_uri": os.environ.get("MILVUS_URI") or os.environ.get("ZILLIZ_URI") or "",
        "milvus_db_path": os.environ.get("MILVUS_DB_PATH") or str(merged_runtime.get("db_path") or ""),
        "milvus_collection_name": os.environ.get("MILVUS_COLLECTION_NAME")
        or os.environ.get("MILVUS_COLLECTION")
        or str(merged_runtime.get("collection") or merged_runtime.get("collection_name") or ""),
    }
    return context


def _milvus_runtime_from_config_env() -> dict[str, Any]:
    config_path = os.environ.get("FINSIGHT_MILVUS_RUNTIME_CONFIG")
    if not config_path:
        return {}
    path = Path(config_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        return {}
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(config, Mapping):
        return {}
    return {
        "status": config.get("status"),
        "location": "local" if str(config.get("location") or "").startswith("local") else config.get("location"),
        "db_path": config.get("db_path"),
        "collection_name": config.get("collection_name"),
        "vector_count": config.get("vector_count"),
        "vector_kinds": config.get("vector_kinds"),
        "claim_boundary": config.get("claim_boundary"),
        "fallback_routes": config.get("fallback_routes") or ["bm25", "object_bm25", "exact_value_ledger"],
    }


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


def _resolved_evidence_operator_fanout_workers(args: argparse.Namespace) -> int:
    requested = int(getattr(args, "evidence_operator_fanout_workers", 0) or 0)
    if requested > 0:
        return requested
    bge_device = str(getattr(args, "bge_device", "") or "").strip().lower()
    context_runner = str(getattr(args, "context_runner", "") or "").strip().lower()
    if bge_device in {"auto", "cuda"} or bge_device.startswith("cuda"):
        if context_runner in {"", "auto", "in_process"}:
            return 1
        if context_runner == "subprocess":
            return 2
    return 4


def _evidence_operator_resource_policy(args: argparse.Namespace) -> dict[str, Any]:
    workers = _resolved_evidence_operator_fanout_workers(args)
    bge_device = str(getattr(args, "bge_device", "") or "")
    context_runner = str(getattr(args, "context_runner", "") or "")
    requested = int(getattr(args, "evidence_operator_fanout_workers", 0) or 0)
    return {
        "schema_version": "sec_agent_evidence_operator_resource_policy_v0.1",
        "policy_name": (
            "explicit"
            if requested > 0
            else ("local_cuda_serial_bge_queue" if workers == 1 else "local_bge_subprocess_queue" if workers == 2 else "default_parallel_fanout")
        ),
        "evidence_operator_fanout_workers": workers,
        "requested_evidence_operator_fanout_workers": requested,
        "bge_device": bge_device,
        "context_runner": context_runner,
        "reason": (
            "explicit_cli_or_env"
            if requested > 0
            else (
                "serialize local CUDA in-process BGE-backed evidence routes to avoid duplicate model-load pressure"
                if workers == 1
                else "queue local auto/CUDA subprocess BGE-backed evidence routes to avoid duplicate model-load pressure"
                if workers == 2
                else "non-local-CUDA profile can keep default parallel fanout"
            )
        ),
    }


def _graph_env(args: argparse.Namespace) -> dict[str, str]:
    env = dict(os.environ)
    router_modes = _graph_router_modes(args)
    env.update(
        {
            "LLM_BACKEND": args.llm_backend,
            "BASE_URL": args.base_url,
            "CHAT_COMPLETIONS_PATH": args.chat_completions_path,
            "MODEL_NAME": args.model,
            "API_KEY_ENV": args.api_key_env,
            "LLM_GATEWAY_PROXY_MODE": _resolved_llm_gateway_proxy_mode(args),
            "LLM_GATEWAY_EVENT_LOG_PATH": str(getattr(args, "_llm_gateway_event_log_path", "") or ""),
            "SEC_AGENT_MULTI_AGENT_LEAD_ROUTER": router_modes["lead"],
            "SEC_AGENT_MULTI_AGENT_SPECIALIST_ROUTER": router_modes["specialist"],
            "SEC_AGENT_MULTI_AGENT_UNIVERSE_ROUTER": router_modes["universe"],
            "SEC_AGENT_MULTI_AGENT_MEMO_ROUTER": router_modes["memo"],
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
            "SEC_AGENT_EVIDENCE_OPERATOR_FANOUT_WORKERS": str(_resolved_evidence_operator_fanout_workers(args)),
            "RESEARCH_LEAD_MAX_TOKENS": str(args.research_lead_max_tokens),
            "SPECIALIST_MAX_TOKENS": str(args.specialist_max_tokens),
            "UNIVERSE_MAX_TOKENS": str(args.universe_max_tokens),
            "MEMO_MAX_TOKENS": str(args.memo_max_tokens),
            "VERIFIER_MAX_TOKENS": str(args.verifier_max_tokens),
            "RESEARCH_LEAD_TIMEOUT_S": str(args.timeout_s),
            "SPECIALIST_TIMEOUT_S": str(args.timeout_s),
            "UNIVERSE_TIMEOUT_S": str(args.universe_timeout_s),
            "MEMO_TIMEOUT_S": str(args.timeout_s),
        }
    )
    return env


def _graph_router_modes(args: argparse.Namespace) -> dict[str, str]:
    if _llm_backend_is_paid(args.llm_backend):
        universe_mode = "llm" if bool(getattr(args, "universe_llm_overlay", False)) else "deterministic"
        return {"lead": "llm", "specialist": "llm", "universe": universe_mode, "memo": "llm"}
    return {
        "lead": "deterministic",
        "specialist": "mock",
        "universe": "deterministic",
        "memo": "deterministic",
    }


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
    run_audit_db_path = _run_audit_db_path_for_case(args=args, case=case, run_id=run_id)
    if run_audit_db_path:
        state["run_audit_db_path"] = str(run_audit_db_path)
    inventory_companies = _string_list(case.get("source_inventory_companies"))
    case_source_families = _string_list(case.get("source_tiers"))
    project_inventory: dict[str, Any] = {
        "source_families": case_source_families,
        "available_source_families": case_source_families,
        "source_family_availability": {
            family: {"available": True, "status": "available"}
            for family in case_source_families
        },
        "evaluation_inventory": "summary_only_no_private_paths",
    }
    if inventory_companies:
        project_inventory["companies"] = [{"ticker": ticker} for ticker in inventory_companies]
    if _case_requires_milvus_runtime_contract(case):
        milvus_context = _milvus_runtime_context_from_env(case)
        capability = milvus_runtime_capability({"project_inventory": project_inventory, **milvus_context})
        milvus_runtime = _public_milvus_runtime_for_eval(capability)
        project_inventory["milvus_runtime"] = milvus_runtime
        availability = dict(project_inventory.get("source_family_availability") or {})
        availability["milvus_semantic"] = {
            "available": bool(milvus_runtime.get("available")),
            "status": str(milvus_runtime.get("status") or "unavailable"),
            "location": str(milvus_runtime.get("location") or "none"),
            "exact_value_authority": False,
            "allowed_claim_scope": "semantic_recall_supplement_only",
        }
        project_inventory["source_family_availability"] = availability
        if milvus_runtime.get("available") and "milvus_semantic" not in project_inventory["available_source_families"]:
            project_inventory["available_source_families"] = [*project_inventory["available_source_families"], "milvus_semantic"]
            project_inventory["source_families"] = [*project_inventory["source_families"], "milvus_semantic"]
    state["project_inventory"] = project_inventory
    response_language = str(case.get("response_language") or case.get("output_language") or "").strip()
    if response_language:
        state["response_language"] = response_language
    evidence_operator_resource_policy = _evidence_operator_resource_policy(args)
    context = {
        "execution_mode": str(case.get("execution_mode") or case.get("expected_execution_mode") or ""),
        "expected_execution_mode": str(case.get("expected_execution_mode") or ""),
        "expected_specialist_agents": _quality_expected_specialist_agents(case),
        "expected_paid_specialist_agents": _runtime_paid_specialist_agents(case),
        "expected_paid_specialist_priorities": _expected_paid_specialist_priorities(
            case,
            _runtime_paid_specialist_agents(case),
        ),
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
        "evidence_operator_fanout_workers": evidence_operator_resource_policy["evidence_operator_fanout_workers"],
        "evidence_operator_resource_policy": evidence_operator_resource_policy,
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
    if run_audit_db_path:
        context["run_audit_db_path"] = str(run_audit_db_path)
    if _case_requires_milvus_runtime_contract(case):
        context.update(_milvus_runtime_context_from_env(case))
        context["milvus_runtime"] = project_inventory.get("milvus_runtime") or {}
    if response_language:
        context["response_language"] = response_language
    state["multi_agent_context"] = context
    return state


def _runtime_paid_specialist_agents(case: Mapping[str, Any]) -> list[str]:
    explicit = _string_list(case.get("expected_paid_specialist_agents"))
    if explicit:
        agents = list(explicit)
        if _case_has_explicit_risk_or_counterevidence_intent(case) and "risk_counterevidence_analyst" not in agents:
            agents.append("risk_counterevidence_analyst")
        return agents
    quality_expected = _quality_expected_specialist_agents(case)
    estimated = _estimated_specialist_agents(case)
    fallback = estimated or quality_expected
    return _cost_aware_estimated_specialist_agents(case, fallback=fallback)


def _case_has_explicit_risk_or_counterevidence_intent(case: Mapping[str, Any]) -> bool:
    text = " ".join(
        [
            str(case.get("prompt") or ""),
            json.dumps(case.get("required_dimensions") or [], ensure_ascii=False, default=str),
            json.dumps(case.get("required_dimension_ids") or [], ensure_ascii=False, default=str),
            json.dumps(case.get("required_answer_moves") or [], ensure_ascii=False, default=str),
        ]
    ).lower()
    return any(
        term in text
        for term in (
            "risk",
            "counter",
            "counterevidence",
            "counter-thesis",
            "what-would-change",
            "what would change",
            "downside",
            "风险",
            "反证",
            "推翻",
        )
    )


def _run_audit_db_path_for_case(*, args: argparse.Namespace, case: Mapping[str, Any], run_id: str) -> Path | None:
    if args.run_audit_db_path:
        path = Path(args.run_audit_db_path)
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()
    if not bool(case.get("require_run_audit_store")):
        return None
    return (REPO_ROOT / "data" / "workbench_private" / "run_audit" / f"{run_id}.sqlite").resolve()


def _query_contract(case: Mapping[str, Any]) -> dict[str, Any]:
    tickers = _string_list(case.get("search_scope_tickers"))
    focus = _string_list(case.get("focus_tickers")) or tickers[:2]
    source_tiers = _string_list(case.get("source_tiers")) or ["primary_sec_filing"]
    metric_families = _string_list(case.get("metric_families")) or ["revenue", "capex", "margin"]
    required_dimension_ids = _string_list(case.get("required_dimension_ids"))
    demand_proxy_tickers = _infer_demand_proxy_tickers(case, search_scope_tickers=tickers, focus_tickers=focus)
    ticker_roles = _infer_ticker_roles(case, demand_proxy_tickers=demand_proxy_tickers)
    return {
        "task_type": "open_analysis",
        "search_scope_tickers": tickers,
        "focus_tickers": focus,
        "demand_proxy_tickers": demand_proxy_tickers,
        "ticker_roles": ticker_roles,
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


def _infer_demand_proxy_tickers(
    case: Mapping[str, Any],
    *,
    search_scope_tickers: list[str],
    focus_tickers: list[str],
) -> list[str]:
    explicit = _string_list(case.get("demand_proxy_tickers"))
    query_contract = case.get("query_contract") if isinstance(case.get("query_contract"), Mapping) else {}
    explicit.extend(_string_list(query_contract.get("demand_proxy_tickers")))
    if explicit:
        return _unique_upper([ticker for ticker in explicit if ticker not in set(_unique_upper(focus_tickers))])

    text = " ".join(
        [
            str(case.get("case_id") or ""),
            str(case.get("category") or ""),
            str(case.get("industry_schema") or ""),
            str(case.get("prompt") or ""),
            " ".join(_string_list(case.get("metric_families"))),
        ]
    ).lower()
    wants_cloud_capex_readthrough = (
        "capex" in text
        and any(marker in text for marker in ("ai", "cloud", "hyperscaler", "data center", "infrastructure", "供应链", "需求传导"))
        and any(marker in text for marker in ("read-through", "readthrough", "传导", "supplier", "供应链", "demand", "需求"))
    )
    if not wants_cloud_capex_readthrough:
        return []

    focus = set(_unique_upper(focus_tickers))
    cloud_buyer_candidates = {
        "MSFT",
        "AMZN",
        "GOOGL",
        "GOOG",
        "META",
        "ORCL",
    }
    return _unique_upper([ticker for ticker in search_scope_tickers if ticker.upper() in cloud_buyer_candidates and ticker.upper() not in focus])


def _infer_ticker_roles(case: Mapping[str, Any], *, demand_proxy_tickers: list[str]) -> dict[str, str]:
    query_contract = case.get("query_contract") if isinstance(case.get("query_contract"), Mapping) else {}
    roles: dict[str, str] = {}
    for source in (case.get("ticker_roles"), query_contract.get("ticker_roles")):
        if isinstance(source, Mapping):
            for ticker, role in source.items():
                ticker_text = str(ticker or "").upper().strip()
                role_text = str(role or "").strip()
                if ticker_text and role_text:
                    roles[ticker_text] = role_text
    for ticker in demand_proxy_tickers:
        roles.setdefault(str(ticker).upper(), "cloud_buyer_demand_proxy")
    return roles


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
    llm_overlay_required = bool(case.get("_universe_llm_overlay_required") or case.get("require_universe_llm_overlay_pass"))
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
        "llm_invoked_when_expected": (not llm_overlay_required) or _diag_call_count(route) >= 1,
        "llm_calls_ok": (not llm_overlay_required) or _diag_calls_ok(route),
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
        known_refs = _known_data_view_refs(data_view, rows)
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
        comparative_primary_gate = _comparative_primary_visibility_gate(case, rows, result, route_row=route_row)
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
            "focus_ticker_primary_source_gap_reasons": comparative_primary_gate["gap_reasons"],
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
        return {"primary_sec_filing", "company_authored_unaudited_sec_filing", "derived_metric_layer"}
    if agent_id == "market_valuation_analyst":
        return {"market_snapshot"}
    if agent_id == "industry_supply_chain_analyst":
        return {
            "industry_snapshot",
            "relationship_graph",
            "company_product_evidence_graph",
            "public_source_context",
            "live_public_web_context",
        }
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


def _known_data_view_refs(data_view: Mapping[str, Any], rows: list[Mapping[str, Any]]) -> set[str]:
    refs = _known_row_refs(rows)
    for key in (
        "relationship_summary",
        "product_spec_pack",
        "product_spec_pack_ref",
        "capital_macro_pack",
        "capital_macro_pack_ref",
        "fundamental_statement_pack",
        "fundamental_statement_pack_ref",
    ):
        refs.update(_nested_evidence_refs(data_view.get(key)))
    return refs


def _nested_evidence_refs(value: Any) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, Mapping):
        for key in (
            "evidence_refs",
            "refs",
            "supporting_evidence_ids",
            "evidence_ref",
            "evidence_id",
            "raw_record_ref",
            "source_fact_id",
            "line_item_id",
            "change_id",
            "comparison_id",
            "gap_id",
        ):
            refs.update(_string_list(value.get(key)))
        for item in value.values():
            if isinstance(item, (Mapping, list)):
                refs.update(_nested_evidence_refs(item))
    elif isinstance(value, list):
        for item in value:
            refs.update(_nested_evidence_refs(item))
    return {ref for ref in refs if ref}


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
    *,
    route_row: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    focus = set(_focus_tickers_from_case(case))
    if len(focus) < 2:
        return {"status": True, "visible_tickers": sorted(focus), "gap_tickers": [], "gap_reasons": {}, "missing_tickers": []}
    visible = {
        str(row.get("ticker") or "").upper()
        for row in rows
        if str(row.get("source_family") or "") in {"", "primary_sec_filing", "company_authored_unaudited_sec_filing"}
        and str(row.get("ticker") or "").strip()
    }
    gap_reasons: dict[str, list[str]] = {}
    for gap in result.get("source_gaps") or []:
        if not isinstance(gap, Mapping):
            continue
        if str(gap.get("source_family") or "") != "primary_sec_filing":
            continue
        ticker = str(gap.get("ticker") or "").upper().strip()
        reason = str(gap.get("reason_code") or gap.get("quality_gap_type") or "").strip()
        if ticker and reason:
            gap_reasons.setdefault(ticker, []).append(reason)
    coverage = route_row.get("input_coverage_summary") if isinstance(route_row, Mapping) else {}
    coverage_gap_reasons = (
        coverage.get("focus_ticker_source_gap_reasons")
        if isinstance(coverage, Mapping) and isinstance(coverage.get("focus_ticker_source_gap_reasons"), Mapping)
        else {}
    )
    for ticker_value, reasons_value in dict(coverage_gap_reasons or {}).items():
        ticker = str(ticker_value or "").upper().strip()
        reasons = [str(reason or "").strip() for reason in _string_list(reasons_value) if str(reason or "").strip()]
        if ticker and reasons:
            gap_reasons.setdefault(ticker, []).extend(reasons)
    gap_tickers = set(gap_reasons)
    covered = visible | gap_tickers
    missing = sorted(focus - covered)
    return {
        "status": not missing,
        "visible_tickers": sorted(visible & focus),
        "gap_tickers": sorted(gap_tickers & focus),
        "gap_reasons": {ticker: sorted(set(reasons)) for ticker, reasons in sorted(gap_reasons.items()) if ticker in focus},
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
    research_lead_fingerprint = (
        _route(llm_routes, "research_lead").get("input_pack_fingerprint")
        or result.get("research_lead_input_pack_fingerprint")
        or _fallback_research_lead_input_pack_fingerprint(result)
    )
    universe_fingerprint = (
        _route(llm_routes, "universe_relationship").get("input_pack_fingerprint")
        or result.get("universe_relationship_input_pack_fingerprint")
        or _fallback_universe_relationship_input_pack_fingerprint(result)
    )
    memo_route_result = dict(result.get("memo_route_result") or {}) if isinstance(result.get("memo_route_result"), Mapping) else {}
    if not isinstance(memo_route_result.get("input_pack_fingerprint"), Mapping):
        memo_route_result["input_pack_fingerprint"] = _fallback_memo_writer_input_pack_fingerprint(result)
        memo_route_result.setdefault("status", "deterministic_or_missing_route_result")
    verifier_input_projection = (
        dict((result.get("claim_verification") or {}).get("verifier_input_projection") or {})
        if isinstance(result.get("claim_verification"), Mapping)
        else {}
    )
    if not isinstance(verifier_input_projection.get("input_pack_fingerprint"), Mapping):
        verifier_input_projection["input_pack_fingerprint"] = _fallback_verifier_input_pack_fingerprint(result)
        verifier_input_projection.setdefault("projection_source", "deterministic_fallback_from_saved_state")
    specialist_routes = _specialist_routes_with_fallback_input_fingerprints(specialist_routes, result)
    return {
        "research_lead": {
            "route_status": result.get("research_lead_route_status")
            or _route(llm_routes, "research_lead").get("route_status")
            or "",
            "failure_reason": result.get("research_lead_failure_reason")
            or _route(llm_routes, "research_lead").get("failure_reason")
            or "",
            "validation_errors": (result.get("research_lead_validation") or {}).get("errors") or [],
            "validation_status": (
                (result.get("agent_activation_validation") or {}).get("status")
                if isinstance(result.get("agent_activation_validation"), Mapping)
                else (result.get("research_lead_validation") or {}).get("status")
                if isinstance(result.get("research_lead_validation"), Mapping)
                else ""
            ),
            "execution_mode": (result.get("agent_activation_plan") or {}).get("execution_mode")
            if isinstance(result.get("agent_activation_plan"), Mapping)
            else "",
            "diagnostics": _route(llm_routes, "research_lead").get("diagnostics") or result.get("research_lead_model_diagnostics") or {},
            "input_pack_fingerprint": research_lead_fingerprint,
        },
        "universe_relationship": {
            "lookup_status": (result.get("relationship_graph_observation") or {}).get("status")
            if isinstance(result.get("relationship_graph_observation"), Mapping)
            else "",
            "validation_status": (result.get("universe_relationship_validation") or {}).get("status")
            if isinstance(result.get("universe_relationship_validation"), Mapping)
            else "",
            "diagnostics": _route(llm_routes, "universe_relationship").get("diagnostics") or {},
            "input_pack_fingerprint": universe_fingerprint,
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
            "route_result": memo_route_result,
            "diagnostics": _route(llm_routes, "memo_writer").get("diagnostics") or {},
        },
        "verifier": {
            "claim_verification": (result.get("claim_verification") or {}).get("status")
            if isinstance(result.get("claim_verification"), Mapping)
            else "",
            "input_projection": verifier_input_projection,
            "diagnostics": _route(llm_routes, "verifier").get("diagnostics") or {},
        },
    }


def _fallback_research_lead_input_pack_fingerprint(result: Mapping[str, Any]) -> dict[str, Any]:
    return _fallback_input_pack_fingerprint(
        agent_id="research_lead",
        schema_version="sec_agent_research_lead_input_pack_fingerprint_v0_1",
        components={
            "query_contract": result.get("query_contract") if isinstance(result.get("query_contract"), Mapping) else {},
            "agent_activation_plan": result.get("agent_activation_plan") if isinstance(result.get("agent_activation_plan"), Mapping) else {},
            "evidence_requirement_plan": result.get("evidence_requirement_plan") if isinstance(result.get("evidence_requirement_plan"), Mapping) else {},
            "source_inventory": result.get("project_inventory") if isinstance(result.get("project_inventory"), Mapping) else {},
            "routing_trace": result.get("multi_agent_routing_trace") if isinstance(result.get("multi_agent_routing_trace"), Mapping) else {},
        },
        capture_source="deterministic_fallback_from_saved_research_lead_state",
    )


def _fallback_universe_relationship_input_pack_fingerprint(result: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from sec_agent.universe_relationship_llm import (
            _compact_relationship_lookup,
            _known_relationship_refs,
            _relationship_lookup_prompt_view,
            _universe_relationship_input_pack_fingerprint,
        )

        raw_lookup = (
            result.get("relationship_graph_observation")
            if isinstance(result.get("relationship_graph_observation"), Mapping)
            else {}
        )
        activation = result.get("agent_activation_plan") if isinstance(result.get("agent_activation_plan"), Mapping) else {}
        source_inventory = result.get("project_inventory") if isinstance(result.get("project_inventory"), Mapping) else {}
        lookup = _compact_relationship_lookup(
            raw_lookup,
            source_inventory=source_inventory,
            max_relationships=8,
            priority_tickers=_string_list(activation.get("search_scope_tickers") or activation.get("focus_tickers")),
        )
        prompt_request = {
            "user_query": result.get("user_query") or "",
            "activation_plan": activation,
            "relationship_lookup": _relationship_lookup_prompt_view(lookup),
            "source_inventory": source_inventory,
        }
        fingerprint = _universe_relationship_input_pack_fingerprint(
            prompt_request,
            known_refs=_known_relationship_refs(lookup),
            source_inventory=source_inventory,
        )
        return {
            **fingerprint,
            "capture_source": "deterministic_fallback_using_universe_relationship_input_contract",
        }
    except Exception as exc:
        generic = _generic_universe_relationship_input_pack_fingerprint(result)
        generic["fallback_error"] = str(exc)[:240]
        return generic


def _generic_universe_relationship_input_pack_fingerprint(result: Mapping[str, Any]) -> dict[str, Any]:
    return _fallback_input_pack_fingerprint(
        agent_id="universe_relationship",
        schema_version="sec_agent_universe_relationship_input_pack_fingerprint_v0_1",
        components={
            "agent_activation_plan": result.get("agent_activation_plan") if isinstance(result.get("agent_activation_plan"), Mapping) else {},
            "relationship_graph_observation": result.get("relationship_graph_observation")
            if isinstance(result.get("relationship_graph_observation"), Mapping)
            else {},
            "universe_relationship_plan": result.get("universe_relationship_plan")
            if isinstance(result.get("universe_relationship_plan"), Mapping)
            else {},
            "source_inventory": result.get("project_inventory") if isinstance(result.get("project_inventory"), Mapping) else {},
        },
        capture_source="deterministic_fallback_from_saved_universe_state",
    )


def _fallback_memo_writer_input_pack_fingerprint(result: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from sec_agent.memo_llm import (  # Local private-helper import keeps this path deterministic and no-model.
            _compact_shared_memo_context_for_prompt,
            _memo_writer_input_pack_fingerprint,
            build_shared_memo_context,
        )

        fingerprint = _memo_writer_input_pack_fingerprint(
            result,
            shared_context=_compact_shared_memo_context_for_prompt(build_shared_memo_context(result)),
            judgment=result.get("verified_judgment_plan") if isinstance(result.get("verified_judgment_plan"), Mapping) else {},
        )
        return {
            **fingerprint,
            "capture_source": "deterministic_fallback_using_memo_writer_input_contract",
        }
    except Exception as exc:
        generic = _generic_memo_writer_input_pack_fingerprint(result)
        generic["fallback_error"] = str(exc)[:240]
        return generic


def _generic_memo_writer_input_pack_fingerprint(result: Mapping[str, Any]) -> dict[str, Any]:
    return _fallback_input_pack_fingerprint(
        agent_id="memo_writer",
        schema_version="sec_agent_memo_writer_input_pack_fingerprint_v0_1",
        components={
            "memo_logic_plan": result.get("memo_logic_plan") if isinstance(result.get("memo_logic_plan"), Mapping) else {},
            "verified_judgment_plan": result.get("verified_judgment_plan") if isinstance(result.get("verified_judgment_plan"), Mapping) else {},
            "pre_memo_fact_selection": result.get("pre_memo_fact_selection") if isinstance(result.get("pre_memo_fact_selection"), Mapping) else {},
            "supervising_analyst_pack": result.get("supervising_analyst_pack") if isinstance(result.get("supervising_analyst_pack"), Mapping) else {},
        },
        capture_source="deterministic_fallback_from_saved_memo_writer_state",
    )


def _fallback_verifier_input_pack_fingerprint(result: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from sec_agent.memo_llm import _verifier_input_pack_fingerprint, _verifier_minimal_projection

        deterministic = result.get("claim_verification") if isinstance(result.get("claim_verification"), Mapping) else {}
        projection = _verifier_minimal_projection(result, deterministic=deterministic)
        fingerprint = _verifier_input_pack_fingerprint(projection)
        return {
            **fingerprint,
            "capture_source": "deterministic_fallback_using_verifier_projection_contract",
        }
    except Exception as exc:
        generic = _generic_verifier_input_pack_fingerprint(result)
        generic["fallback_error"] = str(exc)[:240]
        return generic


def _generic_verifier_input_pack_fingerprint(result: Mapping[str, Any]) -> dict[str, Any]:
    return _fallback_input_pack_fingerprint(
        agent_id="verifier",
        schema_version="sec_agent_verifier_input_pack_fingerprint_v0_1",
        components={
            "memo_answer": result.get("memo_answer") if isinstance(result.get("memo_answer"), Mapping) else {},
            "verified_judgment_plan": result.get("verified_judgment_plan") if isinstance(result.get("verified_judgment_plan"), Mapping) else {},
            "claim_evidence_ledger": result.get("claim_evidence_ledger") if isinstance(result.get("claim_evidence_ledger"), Mapping) else {},
            "pre_memo_fact_selection": result.get("pre_memo_fact_selection") if isinstance(result.get("pre_memo_fact_selection"), Mapping) else {},
        },
        capture_source="deterministic_fallback_from_saved_verifier_state",
    )


def _specialist_routes_with_fallback_input_fingerprints(
    routes: list[dict[str, Any]],
    result: Mapping[str, Any],
) -> list[dict[str, Any]]:
    outputs_by_agent = {
        str(row.get("agent_id") or ""): dict(row)
        for row in result.get("specialist_outputs") or []
        if isinstance(row, Mapping) and str(row.get("agent_id") or "")
    }
    rows: list[dict[str, Any]] = []
    for route in routes:
        row = dict(route)
        if not isinstance(row.get("input_pack_fingerprint"), Mapping):
            agent_id = str(row.get("agent_id") or "")
            row["input_pack_fingerprint"] = _fallback_input_pack_fingerprint(
                agent_id=agent_id,
                schema_version="sec_agent_specialist_input_pack_fingerprint_v0_1",
                components={
                    "route_summary": row,
                    "specialist_output_proxy": outputs_by_agent.get(agent_id, {}),
                },
                capture_source="deterministic_fallback_from_saved_specialist_output_proxy",
            )
        rows.append(row)
    return rows


def _fallback_input_pack_fingerprint(
    *,
    agent_id: str,
    schema_version: str,
    components: Mapping[str, Any],
    capture_source: str,
) -> dict[str, Any]:
    component_summaries: dict[str, dict[str, Any]] = {}
    component_digests: dict[str, str] = {}
    approx_chars = 0
    for name, value in components.items():
        if _prompt_component_empty(value):
            component_summaries[str(name)] = _empty_fingerprint_component()
            continue
        encoded = _stable_json(value)
        refs = sorted(_nested_evidence_refs(value))
        digest = _short_sha256({"component": name, "payload": value})
        approx_chars += len(encoded)
        component_digests[str(name)] = digest
        component_summaries[str(name)] = {
            "digest": digest,
            "item_count": _component_item_count(value),
            "evidence_ref_count": len(refs),
            "evidence_refs_sample": refs[:24],
            "approx_chars": len(encoded),
        }
    known_refs = sorted({ref for value in components.values() for ref in _nested_evidence_refs(value)})
    visible_refs = known_refs[:256]
    return {
        "schema_version": schema_version,
        "agent_id": str(agent_id or ""),
        "digest": _short_sha256(
            {
                "agent_id": str(agent_id or ""),
                "component_digests": component_digests,
                "known_evidence_refs": visible_refs,
                "capture_source": capture_source,
            }
        ),
        "known_evidence_ref_count": len(known_refs),
        "known_evidence_refs": visible_refs,
        "known_evidence_refs_truncated": len(known_refs) > len(visible_refs),
        "component_summaries": component_summaries,
        "approx_prompt_payload_chars": approx_chars,
        "fingerprint_policy": "fingerprint_only_no_prompt_text_persisted_v0_1",
        "capture_source": capture_source,
    }


def _prompt_component_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, Mapping):
        return not bool(value)
    if isinstance(value, (list, tuple, set)):
        return not bool(value)
    return False


def _empty_fingerprint_component() -> dict[str, Any]:
    return {
        "digest": "",
        "item_count": 0,
        "evidence_ref_count": 0,
        "evidence_refs_sample": [],
        "approx_chars": 0,
    }


def _component_item_count(value: Any) -> int:
    if isinstance(value, Mapping):
        return len(value)
    if isinstance(value, (list, tuple, set)):
        return len(value)
    if value is None:
        return 0
    return 1


def _short_sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()[:16]


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


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
        "cases_path": str(args.cases_path.resolve()) if not args.case_catalog_path else "",
        "case_catalog": getattr(args, "_resolved_case_catalog", {}) or {},
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
            "llm_gateway_proxy_mode": _resolved_llm_gateway_proxy_mode(args),
            "model_call_event_log_path": str(getattr(args, "_llm_gateway_event_log_path", "") or ""),
        },
        "provider_preflight": _compact_provider_preflight_for_summary(
            getattr(args, "_provider_preflight", {}) or {}
        ),
        "token_budget_preflight": _compact_token_budget_plan_for_summary(getattr(args, "_token_budget_plan", {}) or {}),
        "retrieval_runtime_config": {
            "real_evidence_operators": bool(args.real_evidence_operators),
            "stepwise_stop_after_node": str(args.stop_after_node or ""),
            "context_runner": args.context_runner,
            "bge_device": args.bge_device,
            "bge_model_ref": _model_ref(args.bge_model),
            "evidence_operator_fanout_workers": _resolved_evidence_operator_fanout_workers(args),
            "evidence_operator_resource_policy": _evidence_operator_resource_policy(args),
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
        "stepwise_node_run": {
            "enabled": bool(args.stop_after_node),
            "stop_after_node": str(args.stop_after_node or ""),
            "gate_semantics": (
                "node_level_diagnostic_only_not_full_chain_pass"
                if args.stop_after_node
                else "full_chain_or_preflight"
            ),
        },
    }


def _stdout_summary(summary: Mapping[str, Any], output_path: Path) -> dict[str, Any]:
    return {
        "run_id": summary.get("run_id"),
        "gate_status": summary.get("gate_status"),
        "diagnostic_only": summary.get("diagnostic_only"),
        "output_path": str(output_path.resolve()),
        "metrics": summary.get("metrics"),
        "stepwise_node_run": summary.get("stepwise_node_run"),
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
    if "all_calls_ok" in diagnostics:
        return bool(diagnostics.get("all_calls_ok")) and int(diagnostics.get("direct_tool_call_count") or 0) == 0
    calls = [dict(call) for call in diagnostics.get("calls") or [] if isinstance(call, Mapping)]
    if calls:
        return all(
            str(call.get("status") or "").lower() == "ok"
            and not str(call.get("failure_reason") or "").strip()
            and int(call.get("tool_call_count") or 0) == 0
            for call in calls
        )
    return False


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


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
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
