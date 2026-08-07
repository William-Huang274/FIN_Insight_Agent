from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.mcp_contracts import list_mcp_tool_contracts  # noqa: E402
from sec_agent.mcp_operational import McpToolProcessSupervisor  # noqa: E402
from sec_agent.mcp_server import MCP_SERVER_BUSINESS_TOOL_NAMES  # noqa: E402


DEFAULT_OUTPUT = (
    REPO_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_3_s1_06_mcp_operational_truth_proof_v1_0.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prove FIN 0.1.3 S1-06 MCP operational truth.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def _summary(result: dict[str, Any]) -> dict[str, Any]:
    operational = dict(result.get("operational") or {})
    runtime = dict(result.get("context_runtime") or {})
    candidate_counts = dict(result.get("candidate_counts") or {})
    return {
        "status": result.get("status"),
        "error": result.get("error"),
        "row_count": result.get("row_count", len(result.get("market_rows") or result.get("ledger_rows") or [])),
        "start_kind": operational.get("start_kind"),
        "worker_pid": operational.get("worker_pid"),
        "elapsed_ms": operational.get("elapsed_ms"),
        "terminal_status": operational.get("terminal_status"),
        "phases": operational.get("phases") or [],
        "resource_binding_status": (operational.get("resource_binding") or {}).get("status"),
        "context_reranker": runtime.get("context_reranker"),
        "context_cache_hit": runtime.get("context_cache_hit"),
        "candidate_sent_to_bge": candidate_counts.get("candidate_sent_to_bge"),
    }


def main() -> int:
    args = parse_args()
    if _git("status", "--porcelain"):
        raise SystemExit("S1-06 proof requires a clean Git worktree")
    head = _git("rev-parse", "HEAD")
    branch = _git("branch", "--show-current")
    contract_names = {str(row["name"]) for row in list_mcp_tool_contracts()}
    if contract_names != MCP_SERVER_BUSINESS_TOOL_NAMES:
        raise SystemExit("MCP server and registry tool surfaces do not match")

    runtime_root = REPO_ROOT / ".codex_runtime" / "fin013_s1_06_mcp_operational_truth"
    supervisor = McpToolProcessSupervisor()
    try:
        sec_args = {
            "query": "NVDA FY2025 revenue evidence",
            "tickers": ["NVDA"],
            "years": [2025],
            "filing_types": ["10-K"],
            "source_tiers": ["primary_sec_filing"],
            "metric_families": ["revenue"],
            "retrieval_route": "filing_text",
            "query_planner": "heuristic",
            "candidate_budget": 20,
            "rerank_budget": 0,
            "limit": 5,
            "timeout_s": 90,
        }
        sec_cold = supervisor.invoke(
            "sec_search_filings",
            {**sec_args, "output_dir": str(runtime_root / "sec_cold")},
        )
        sec_warm = supervisor.invoke(
            "sec_search_filings",
            {**sec_args, "output_dir": str(runtime_root / "sec_warm")},
        )
        ledger = supervisor.invoke(
            "sec_query_exact_value_ledger",
            {
                "case_id": "fin013_s1_06_proof",
                "tickers": ["NVDA"],
                "years": [2025],
                "metric_families": ["revenue"],
                "limit": 1,
                "timeout_s": 30,
            },
        )
        market = supervisor.invoke(
            "market_get_snapshot",
            {"tickers": ["NVDA"], "limit": 1, "timeout_s": 15},
        )
        missing_reranker = supervisor.invoke(
            "sec_search_filings",
            {
                **sec_args,
                "rerank_budget": 8,
                "output_dir": str(runtime_root / "missing_reranker"),
            },
        )
        active_pid = supervisor.worker_pid
    finally:
        supervisor.close()

    summaries = {
        "sec_cold": _summary(sec_cold),
        "sec_warm": _summary(sec_warm),
        "exact_ledger": _summary(ledger),
        "market": _summary(market),
        "missing_reranker": _summary(missing_reranker),
    }
    checks = {
        "registry_server_parity": contract_names == MCP_SERVER_BUSINESS_TOOL_NAMES,
        "business_tool_count": len(contract_names) == 9,
        "sec_cold_success": summaries["sec_cold"]["status"] == "ok",
        "sec_warm_success": summaries["sec_warm"]["status"] == "ok",
        "sec_worker_reused": summaries["sec_cold"]["worker_pid"] == summaries["sec_warm"]["worker_pid"],
        "sec_cache_cold_then_warm": summaries["sec_cold"]["context_cache_hit"] is False
        and summaries["sec_warm"]["context_cache_hit"] is True,
        "sec_bm25_only_no_bge_candidates": summaries["sec_cold"]["context_reranker"] == "none"
        and summaries["sec_cold"]["candidate_sent_to_bge"] == 0,
        "exact_ledger_success": summaries["exact_ledger"]["status"] == "ok",
        "market_success": summaries["market"]["status"] == "ok",
        "missing_reranker_typed_failure": summaries["missing_reranker"]["status"] == "error"
        and summaries["missing_reranker"]["error"] == "mcp_resource_binding_failed",
        "worker_closed_no_orphan": supervisor.worker_alive is False,
    }
    payload = {
        "schema_version": "fin_ia_0_1_3_s1_06_mcp_operational_truth_proof_v1_0",
        "status": "pass" if all(checks.values()) else "fail",
        "git": {"branch": branch, "commit": head, "clean_at_start": True},
        "scope": {
            "model_calls": 0,
            "provider_calls": 0,
            "external_network_calls": 0,
            "local_source_handlers": ["sec_search_filings", "sec_query_exact_value_ledger", "market_get_snapshot"],
            "quality_claim": "operational_only_bm25_quality_deferred_to_S1_08",
        },
        "registry": {
            "contract_tool_names": sorted(contract_names),
            "server_tool_names": sorted(MCP_SERVER_BUSINESS_TOOL_NAMES),
        },
        "results": summaries,
        "checks": checks,
        "active_worker_pid_before_close": active_pid,
        "known_boundary": (
            "This proves local MCP registry parity, canonical resource binding, bounded process supervision, "
            "cold/warm SEC handler operation, Exact-Value Ledger and market snapshot operation. It does not "
            "prove BGE/Milvus retrieval quality, live external source acquisition, Agentic Search quality, "
            "DeepSeek behavior, product acceptance, or release readiness."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": str(args.output), "checks": checks}, indent=2))
    return 0 if payload["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
