from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
DEFAULT_CASES_PATH = REPO_ROOT / "tests" / "fixtures" / "fin_agent_full_chain_multiturn_cases_v0_1.jsonl"
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "reports" / "quality" / "workbench_eval" / "artifacts"
SMOKE_CASE_IDS = [
    "fin_full_exact_msft_capex_zh",
    "fin_full_scope_nvda_basic_fundamental_zh",
    "fin_full_standard_nvda_amd_market_zh",
    "fin_full_sector_ai_infra_depth_zh",
]
EVAL_IDS = {"expanded_a6_full_chain_smoke", "expanded_a6_full_chain_main"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run expanded A6 full-chain eval and write a Workbench summary.")
    parser.add_argument("--eval-id", choices=sorted(EVAL_IDS), required=True)
    parser.add_argument("--output-path", type=Path, required=True)
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--case-id", action="append", default=[], help="Override selected case IDs. Repeatable.")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--prewarm-resident-tools",
        action="store_true",
        default=_env_bool("SEC_AGENT_A6_PREWARM_RESIDENT_TOOLS"),
        help="Prewarm resident SEC/Milvus tools before the timed child eval when SEC_AGENT_MCP_RESIDENT_URL is configured.",
    )
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started = time.time()
    output_path = args.output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    run_id = args.run_id or output_path.stem
    artifact_root = args.artifact_root.resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)

    selected_case_ids = _selected_case_ids(args)
    cases = _read_jsonl(args.cases_path.resolve())
    prewarm_report = _prewarm_resident_tools(
        enabled=bool(args.prewarm_resident_tools),
        cases=[case for case in cases if str(case.get("case_id") or "") in set(selected_case_ids)] if selected_case_ids else cases,
        run_id=run_id,
        artifact_root=artifact_root,
    )
    command = _child_command(
        eval_id=args.eval_id,
        cases_path=args.cases_path.resolve(),
        artifact_root=artifact_root,
        run_id=run_id,
        case_ids=selected_case_ids,
        limit=args.limit,
        strict=args.strict,
    )
    print(json.dumps({"stage": "expanded_a6_child_start", "eval_id": args.eval_id, "run_id": run_id}, ensure_ascii=False), flush=True)
    child = subprocess.run(command, cwd=REPO_ROOT)
    child_output_dir = artifact_root / run_id
    child_summary_path = child_output_dir / "real_chain_eval_summary.json"
    child_summary = _read_json(child_summary_path)
    report = build_workbench_eval_summary(
        eval_id=args.eval_id,
        run_id=run_id,
        output_path=output_path,
        child_summary=child_summary,
        child_summary_path=child_summary_path,
        child_output_dir=child_output_dir,
        child_return_code=child.returncode,
        elapsed_ms=int((time.time() - started) * 1000),
        selected_case_ids=selected_case_ids,
        prewarm_report=prewarm_report,
    )
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(_stdout_summary(report), ensure_ascii=False, indent=2), flush=True)
    return 0 if report["all_pass"] or not args.strict else 1


def build_workbench_eval_summary(
    *,
    eval_id: str,
    run_id: str,
    output_path: Path,
    child_summary: Mapping[str, Any],
    child_summary_path: Path,
    child_output_dir: Path,
    child_return_code: int,
    elapsed_ms: int,
    selected_case_ids: list[str],
    prewarm_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    metrics = child_summary.get("metrics") if isinstance(child_summary.get("metrics"), Mapping) else {}
    case_count = _int(metrics.get("case_count"), len(child_summary.get("cases") or []))
    pass_count = _int(metrics.get("passed"), 0)
    failure_count = _int(metrics.get("failed"), max(0, case_count - pass_count))
    gate_status = str(child_summary.get("gate_status") or ("pass" if failure_count == 0 and case_count else "fail"))
    token_usage = _token_usage(child_summary)
    runtime = _runtime_summary(child_summary, elapsed_ms=elapsed_ms)
    all_pass = child_return_code == 0 and gate_status == "pass" and failure_count == 0 and case_count > 0
    return {
        "schema_version": "finsight_workbench_expanded_a6_eval_v0.1",
        "eval_id": eval_id,
        "run_id": run_id,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if all_pass else "fail",
        "gate_status": gate_status,
        "all_pass": all_pass,
        "case_count": case_count,
        "pass_count": pass_count,
        "failure_count": failure_count,
        "warn_count": 0,
        "skipped_count": 0,
        "elapsed_ms": elapsed_ms,
        "child_return_code": child_return_code,
        "selected_case_ids": selected_case_ids,
        "metrics": dict(metrics),
        "categories": child_summary.get("categories") if isinstance(child_summary.get("categories"), Mapping) else {},
        "token_usage": token_usage,
        "runtime": runtime,
        "prewarm": dict(prewarm_report or {}),
        "trace": {
            "workbench_job_id": os.environ.get("SEC_AGENT_WORKBENCH_JOB_ID", ""),
            "workbench_trace_id": os.environ.get("SEC_AGENT_TRACE_ID", ""),
        },
        "secret_safety": {
            "api_key_env": ((child_summary.get("model_config") or {}).get("api_key_env") if isinstance(child_summary.get("model_config"), Mapping) else "")
            or os.environ.get("API_KEY_ENV", ""),
            "api_key_saved": False,
            "raw_llm_response_saved": False,
        },
        "artifacts": {
            "workbench_output_path": str(output_path),
            "child_output_dir": str(child_output_dir),
            "child_summary_path": str(child_summary_path),
            "case_score_jsonl": str(child_output_dir / "real_chain_case_scores.jsonl"),
            "quality_audit_json": str(child_output_dir / "multi_agent_output_quality_audit.json"),
            "quality_audit_md": str(child_output_dir / "multi_agent_output_quality_audit.md"),
        },
        "failures": [
            _failure_row(case)
            for case in child_summary.get("cases") or []
            if isinstance(case, Mapping) and case.get("gate_status") != "pass"
        ],
        "raw_llm_response_saved": False,
        "api_key_saved": False,
    }


def _child_command(
    *,
    eval_id: str,
    cases_path: Path,
    artifact_root: Path,
    run_id: str,
    case_ids: list[str],
    limit: int,
    strict: bool,
) -> list[str]:
    args = [
        sys.executable,
        "-u",
        "scripts/eval_multi_agent/eval_multi_agent_real_llm_chain.py",
        "--cases-path",
        str(cases_path),
        "--output-dir",
        str(artifact_root),
        "--run-id",
        run_id,
        "--real-evidence-operators",
    ]
    for case_id in case_ids:
        args.extend(["--case-id", case_id])
    if limit > 0:
        args.extend(["--limit", str(limit)])
    if strict:
        args.append("--strict")
    return args


def _selected_case_ids(args: argparse.Namespace) -> list[str]:
    if args.case_id:
        return [str(item).strip() for item in args.case_id if str(item).strip()]
    if args.eval_id == "expanded_a6_full_chain_smoke":
        return list(SMOKE_CASE_IDS)
    return []


def _prewarm_resident_tools(
    *,
    enabled: bool,
    cases: list[Mapping[str, Any]],
    run_id: str,
    artifact_root: Path,
) -> dict[str, Any]:
    resident_url = str(os.environ.get("SEC_AGENT_MCP_RESIDENT_URL") or "").strip()
    if not enabled:
        return {"enabled": False, "status": "skipped", "reason": "disabled"}
    if not resident_url:
        return {"enabled": True, "status": "skipped", "reason": "SEC_AGENT_MCP_RESIDENT_URL_not_configured"}
    started = time.time()
    try:
        from sec_agent.mcp_tool_registry import invoke_mcp_tool
    except Exception as exc:  # noqa: BLE001
        return {"enabled": True, "status": "error", "error": f"{type(exc).__name__}:{exc}"[:500]}
    payloads = _resident_prewarm_payloads(cases=cases, run_id=run_id, artifact_root=artifact_root)
    results = []
    for payload in payloads:
        tool_started = time.time()
        tool_name = str(payload.get("tool_name") or "")
        arguments = payload.get("arguments") if isinstance(payload.get("arguments"), Mapping) else {}
        try:
            result = invoke_mcp_tool(tool_name, dict(arguments))
            results.append(
                {
                    "tool_name": tool_name,
                    "status": result.get("status"),
                    "row_count": result.get("row_count"),
                    "runtime_ledger_row_count": result.get("runtime_ledger_row_count"),
                    "error": str(result.get("error") or "")[:500],
                    "elapsed_ms": int((time.time() - tool_started) * 1000),
                    "resident_worker": _resident_metadata(result.get("resident_worker")),
                    "cache_hit": ((result.get("mcp_result_cache") or {}).get("hit") if isinstance(result.get("mcp_result_cache"), Mapping) else None),
                }
            )
        except Exception as exc:  # noqa: BLE001
            results.append({"tool_name": tool_name, "status": "error", "error": f"{type(exc).__name__}:{exc}"[:500], "elapsed_ms": int((time.time() - tool_started) * 1000)})
    status = "pass" if results and all(str(item.get("status")) in {"ok", "partial"} for item in results) else "warn"
    return {
        "enabled": True,
        "status": status,
        "resident_url_configured": True,
        "tool_count": len(results),
        "elapsed_ms": int((time.time() - started) * 1000),
        "results": results,
    }


def _resident_prewarm_payloads(*, cases: list[Mapping[str, Any]], run_id: str, artifact_root: Path) -> list[dict[str, Any]]:
    tickers = _case_tickers(cases) or ["NVDA"]
    years = _case_years(cases) or [2026, 2025]
    source_tiers = _case_source_tiers(cases) or ["primary_sec_filing", "company_authored_unaudited_sec_filing"]
    metric_families = _case_metric_families(cases) or ["revenue", "margin", "capex"]
    prewarm_dir = artifact_root / run_id / "_prewarm"
    payloads = []
    if _cases_need_sec_prewarm(cases):
        sec_args = {
            "query": " ".join([*tickers[:6], "fundamentals revenue margin AI infrastructure demand supply chain risk"]).strip(),
            "tickers": tickers[:8],
            "years": years[:3],
            "filing_types": ["10-K", "10-Q"],
            "source_tiers": [tier for tier in source_tiers if tier in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}] or ["primary_sec_filing"],
            "metric_families": metric_families[:8],
            "retrieval_route": "filing_text",
            "candidate_budget": _int_env("A6_PREWARM_RERANK_CANDIDATE_LIMIT", 80),
            "rerank_budget": _int_env("A6_PREWARM_RERANK_TOP_K", 8),
            "limit": _int_env("A6_PREWARM_CONTEXT_LIMIT", 6),
            "build_runtime_ledger": False,
            "cache_result": True,
            "output_dir": str(prewarm_dir / "sec_search"),
            "run_id": f"{run_id}_prewarm_sec_search",
            "bge_device": _prewarm_bge_device(),
            "bge_model": os.environ.get("BGE_MODEL", ""),
            "manifest_path": os.environ.get("MANIFEST_PATH", ""),
            "bm25_index_dir": os.environ.get("BM25_INDEX_DIR", ""),
            "object_bm25_index_dir": os.environ.get("OBJECT_BM25_INDEX_DIR", ""),
            "ledger_store_path": os.environ.get("LEDGER_STORE_PATH", ""),
            "context_runner": os.environ.get("SEC_AGENT_CONTEXT_RUNNER") or os.environ.get("CONTEXT_RUNNER") or "in_process",
        }
        payloads.append({"tool_name": "sec_search_filings", "arguments": sec_args})
    if _cases_need_8k_prewarm(cases):
        sec_8k_args = {
            "query": " ".join([*tickers[:6], "8-K earnings release management commentary revenue margin capex credit provision"]).strip(),
            "tickers": tickers[:8],
            "years": years[:3],
            "filing_types": ["8-K"],
            "source_tiers": [tier for tier in source_tiers if tier in {"primary_sec_filing", "company_authored_unaudited_sec_filing"}] or ["primary_sec_filing"],
            "metric_families": metric_families[:8],
            "retrieval_route": "8k_commentary",
            "candidate_budget": _int_env("A6_PREWARM_8K_CANDIDATE_LIMIT", 80),
            "rerank_budget": _int_env("A6_PREWARM_8K_RERANK_TOP_K", 8),
            "limit": _int_env("A6_PREWARM_8K_CONTEXT_LIMIT", 6),
            "build_runtime_ledger": False,
            "cache_result": True,
            "output_dir": str(prewarm_dir / "sec_search_8k"),
            "run_id": f"{run_id}_prewarm_sec_search_8k",
            "bge_device": _prewarm_bge_device(),
            "bge_model": os.environ.get("BGE_MODEL", ""),
            "manifest_path": os.environ.get("MANIFEST_PATH", ""),
            "bm25_index_dir": os.environ.get("BM25_INDEX_DIR", ""),
            "object_bm25_index_dir": os.environ.get("OBJECT_BM25_INDEX_DIR", ""),
            "ledger_store_path": os.environ.get("LEDGER_STORE_PATH", ""),
            "context_runner": os.environ.get("SEC_AGENT_CONTEXT_RUNNER") or os.environ.get("CONTEXT_RUNNER") or "in_process",
        }
        payloads.append({"tool_name": "sec_search_filings", "arguments": sec_8k_args})
    if _cases_need_milvus_prewarm(cases) and os.environ.get("MILVUS_DB_PATH") and os.environ.get("MILVUS_COLLECTION_NAME"):
        payloads.append(
            {
                "tool_name": "sec_milvus_semantic_search",
                "arguments": {
                    "query": " ".join([*tickers[:6], "AI infrastructure semantic recall supply chain market reaction risk"]).strip(),
                    "query_probes": [
                        "cloud capex demand hyperscaler AI infrastructure",
                        "memory HBM foundry equipment supply chain constraints",
                        "server networking power downstream data center demand",
                    ],
                    "tickers": tickers[:8],
                    "years": years[:3],
                    "filing_types": ["10-K", "10-Q"],
                    "source_tiers": ["primary_sec_filing", "company_authored_unaudited_sec_filing"],
                    "vector_kinds": _csv_env("MILVUS_VECTOR_KINDS") or ["paraphrase_context", "relationship_context", "narrative_chunk"],
                    "milvus_top_k": _int_env("A6_PREWARM_MILVUS_TOP_K", 8),
                    "final_top_k": _int_env("A6_PREWARM_MILVUS_FINAL_TOP_K", 4),
                    "milvus_db_path": os.environ.get("MILVUS_DB_PATH", ""),
                    "milvus_collection_name": os.environ.get("MILVUS_COLLECTION_NAME", ""),
                    "embedding_model": os.environ.get("MILVUS_EMBEDDING_MODEL") or os.environ.get("BGE_EMBEDDING_MODEL") or os.environ.get("BGE_MODEL", ""),
                    "embedding_device": os.environ.get("MILVUS_EMBEDDING_DEVICE") or os.environ.get("BGE_DEVICE", "auto"),
                },
            }
        )
    return payloads


def _cases_need_sec_prewarm(cases: list[Mapping[str, Any]]) -> bool:
    if not cases:
        return True
    return any("sec_search_filings" in set(_string_list(case.get("expected_tool_names"))) for case in cases)


def _cases_need_8k_prewarm(cases: list[Mapping[str, Any]]) -> bool:
    if not cases:
        return True
    return any("eight_k_operator" in set(_string_list(case.get("required_agents"))) for case in cases)


def _cases_need_milvus_prewarm(cases: list[Mapping[str, Any]]) -> bool:
    if not cases:
        return True
    return any("sec_milvus_semantic_search" in set(_string_list(case.get("expected_tool_names"))) for case in cases)


def _prewarm_bge_device() -> str:
    requested = str(os.environ.get("BGE_DEVICE") or "").strip().lower()
    if requested and requested not in {"auto", "default"}:
        return requested
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001
        return "cpu"


def _resident_metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    allowed = ("pid", "request_count", "server_elapsed_ms", "client_elapsed_ms", "cache")
    return {key: value.get(key) for key in allowed if key in value}


def _case_tickers(cases: list[Mapping[str, Any]]) -> list[str]:
    values: list[str] = []
    for case in cases:
        values.extend(_string_list(case.get("focus_tickers")))
        values.extend(_string_list(case.get("search_scope_tickers")))
    return _dedupe_upper(values)


def _case_years(cases: list[Mapping[str, Any]]) -> list[int]:
    values = []
    for case in cases:
        values.extend(_int_list(case.get("years")))
    return values


def _case_source_tiers(cases: list[Mapping[str, Any]]) -> list[str]:
    values: list[str] = []
    for case in cases:
        values.extend(_string_list(case.get("source_tiers")))
    return _dedupe(values)


def _case_metric_families(cases: list[Mapping[str, Any]]) -> list[str]:
    values: list[str] = []
    for case in cases:
        values.extend(_string_list(case.get("metric_families")))
    return _dedupe(values)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        if "," in value:
            return [item.strip() for item in value.split(",") if item.strip()]
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _int_list(value: Any) -> list[int]:
    values = []
    for item in _string_list(value):
        try:
            values.append(int(item))
        except ValueError:
            continue
    return _dedupe_int(values)


def _csv_env(name: str) -> list[str]:
    return _string_list(os.environ.get(name))


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, ""))
    except ValueError:
        return int(default)


def _env_bool(name: str) -> bool:
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_upper(values: list[str]) -> list[str]:
    return _dedupe([value.upper().strip() for value in values if value.strip()])


def _dedupe_int(values: list[int]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _token_usage(summary: Mapping[str, Any]) -> dict[str, Any]:
    by_agent: dict[str, int] = {}
    for case in summary.get("cases") or []:
        if not isinstance(case, Mapping):
            continue
        audit = case.get("agent_audit") if isinstance(case.get("agent_audit"), Mapping) else {}
        _add_diag_tokens(by_agent, "research_lead", ((audit.get("research_lead") or {}).get("diagnostics") if isinstance(audit.get("research_lead"), Mapping) else {}))
        _add_diag_tokens(by_agent, "universe_relationship", ((audit.get("universe_relationship") or {}).get("diagnostics") if isinstance(audit.get("universe_relationship"), Mapping) else {}))
        _add_diag_tokens(by_agent, "memo_writer", ((audit.get("memo_writer") or {}).get("diagnostics") if isinstance(audit.get("memo_writer"), Mapping) else {}))
        _add_diag_tokens(by_agent, "verifier", ((audit.get("verifier") or {}).get("diagnostics") if isinstance(audit.get("verifier"), Mapping) else {}))
        specialists = audit.get("specialists") if isinstance(audit.get("specialists"), Mapping) else {}
        for row in specialists.get("route_results") or []:
            if isinstance(row, Mapping):
                agent_id = str(row.get("agent_id") or "specialist")
                by_agent[agent_id] = by_agent.get(agent_id, 0) + _int(row.get("total_tokens"), 0)
    total = sum(by_agent.values())
    case_count = _int((summary.get("metrics") or {}).get("case_count") if isinstance(summary.get("metrics"), Mapping) else 0, 0)
    return {
        "total_tokens": total,
        "avg_tokens_per_case": round(total / case_count, 2) if case_count else 0,
        "by_agent": dict(sorted(by_agent.items())),
    }


def _add_diag_tokens(bucket: dict[str, int], agent_id: str, diagnostics: Any) -> None:
    if not isinstance(diagnostics, Mapping):
        return
    bucket[agent_id] = bucket.get(agent_id, 0) + _int(diagnostics.get("total_tokens"), 0)


def _runtime_summary(summary: Mapping[str, Any], *, elapsed_ms: int) -> dict[str, Any]:
    cases = [case for case in summary.get("cases") or [] if isinstance(case, Mapping)]
    durations = [_int(case.get("elapsed_ms"), 0) for case in cases]
    return {
        "elapsed_ms": elapsed_ms,
        "child_elapsed_ms": _int(summary.get("elapsed_ms"), 0),
        "case_elapsed_ms": {
            "min": min(durations) if durations else 0,
            "max": max(durations) if durations else 0,
            "avg": round(sum(durations) / len(durations), 2) if durations else 0,
        },
        "tool_call_count": _int((summary.get("metrics") or {}).get("total_tool_calls") if isinstance(summary.get("metrics"), Mapping) else 0, 0),
    }


def _failure_row(case: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id", ""),
        "category": case.get("category", ""),
        "execution_mode": case.get("execution_mode", ""),
        "expected_execution_mode": case.get("expected_execution_mode", ""),
        "failed_checks": {key: value for key, value in (case.get("checks") or {}).items() if not value}
        if isinstance(case.get("checks"), Mapping)
        else {},
        "loop_break_reason": case.get("loop_break_reason", ""),
    }


def _stdout_summary(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "eval_id": report.get("eval_id"),
        "run_id": report.get("run_id"),
        "status": report.get("status"),
        "case_count": report.get("case_count"),
        "pass_count": report.get("pass_count"),
        "failure_count": report.get("failure_count"),
        "elapsed_ms": report.get("elapsed_ms"),
        "total_tokens": (report.get("token_usage") or {}).get("total_tokens")
        if isinstance(report.get("token_usage"), Mapping)
        else 0,
        "output_path": (report.get("artifacts") or {}).get("workbench_output_path")
        if isinstance(report.get("artifacts"), Mapping)
        else "",
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    raise SystemExit(main())
