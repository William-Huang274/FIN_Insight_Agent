from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


def _load_interactive_module() -> Any:
    path = REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py"
    spec = importlib.util.spec_from_file_location("sec_agent_interactive_market_smoke", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load interactive module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _split_csv(value: str) -> list[str]:
    return [item.strip().upper() for item in str(value or "").split(",") if item.strip()]


def _parse_years(value: str) -> list[int]:
    return [int(item.strip()) for item in str(value or "").split(",") if item.strip()]


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def _run_context_bm25_only(args: argparse.Namespace, cases_path: Path, trace_dir: Path) -> None:
    cmd = [
        sys.executable,
        "scripts/eval_sec_benchmark/run_sec_benchmark_eval.py",
        "--cases-path",
        str(cases_path),
        "--mode",
        "pipeline_context",
        "--output-dir",
        str(trace_dir),
        "--manifest-path",
        args.manifest_path,
        "--bm25-index-dir",
        args.bm25_index_dir,
        "--object-bm25-index-dir",
        args.object_bm25_index_dir,
        "--object-top-k",
        str(args.object_top_k),
        "--evidence-top-k",
        str(args.evidence_top_k),
        "--max-context-rows",
        str(args.max_context_rows),
        "--context-reranker",
        "none",
        "--allow-bm25-only-pipeline",
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "pipeline_context failed: "
            + json.dumps(
                {
                    "returncode": proc.returncode,
                    "stdout": proc.stdout[-2000:],
                    "stderr": proc.stderr[-2000:],
                },
                ensure_ascii=False,
            )
        )


def _summary(
    *,
    run_root: Path,
    query_contract: dict[str, Any],
    context_rows: list[dict[str, Any]],
    ledger_rows: list[dict[str, Any]],
    coverage_matrix: dict[str, Any],
    judgment_plan: dict[str, Any] | None,
    elapsed_sec: float,
) -> dict[str, Any]:
    market_rows = [row for row in context_rows if str(row.get("source_tier") or "") == "market_snapshot"]
    coverage_summary = coverage_matrix.get("summary") or {}
    market_coverage = coverage_matrix.get("market_snapshot_coverage") or {}
    market_requested = _contract_requests_market_snapshot(query_contract)
    common_ok = not query_contract.get("source_coverage_gaps") and not query_contract.get("market_source_gaps")
    market_ok = (
        len(market_rows) > 0 and bool(market_coverage.get("market_snapshot_support_complete"))
        if market_requested
        else len(market_rows) == 0
    )
    return {
        "schema_version": "sec_agent_market_snapshot_main_chain_smoke_v0.1",
        "status": "pass" if common_ok and market_ok else "fail",
        "run_root": str(run_root),
        "elapsed_sec": round(elapsed_sec, 4),
        "source_policy": query_contract.get("source_policy"),
        "source_coverage_gaps": query_contract.get("source_coverage_gaps") or [],
        "market_source_gaps": query_contract.get("market_source_gaps") or [],
        "market_requested": market_requested,
        "context_row_count": len(context_rows),
        "market_context_row_count": len(market_rows),
        "ledger_row_count": len(ledger_rows),
        "coverage_complete": coverage_summary.get("coverage_complete"),
        "primary_task_support_complete": coverage_summary.get("primary_task_support_complete"),
        "market_snapshot_support_complete": market_coverage.get("market_snapshot_support_complete"),
        "covered_market_fields": market_coverage.get("covered_market_fields") or [],
        "market_snapshot_ids": market_coverage.get("market_snapshot_ids") or [],
        "market_snapshot_as_of_dates": market_coverage.get("market_snapshot_as_of_dates") or [],
        "judgment_plan_present": bool(judgment_plan),
    }


def _contract_requests_market_snapshot(query_contract: dict[str, Any]) -> bool:
    source_tiers = {str(item) for item in (query_contract.get("source_tiers") or [])}
    if "market_snapshot" in source_tiers:
        return True
    if str(query_contract.get("source_policy") or "") == "SEC_PRIMARY_MIXED_WITH_8K_AND_MARKET_SNAPSHOT":
        return True
    market = query_contract.get("market_snapshot")
    return isinstance(market, dict) and bool(market.get("required"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local market snapshot main-chain smoke through coverage/Judgment Plan.")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--years", required=True)
    parser.add_argument("--manifest-path", default="data/processed_private/manifests/sec_tech_primary_mixed_10k_10q_manifest_2023_2026.jsonl")
    parser.add_argument("--bm25-index-dir", default="data/indexes/bm25/sec_tech_primary_mixed_10k_10q_2023_2026")
    parser.add_argument("--object-bm25-index-dir", default="data/indexes/bm25/sec_tech_primary_mixed_10k_10q_2023_2026_objects")
    parser.add_argument("--market-evidence-path", required=True)
    parser.add_argument("--market-snapshot-id", required=True)
    parser.add_argument("--market-as-of-date", required=True)
    parser.add_argument("--output-root", default="eval/sec_cases/outputs/market_snapshot_main_chain_smoke")
    parser.add_argument("--evidence-top-k", type=int, default=4)
    parser.add_argument("--object-top-k", type=int, default=4)
    parser.add_argument("--max-context-rows", type=int, default=120)
    parser.add_argument("--ledger-max-rows", type=int, default=80)
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    started = time.time()
    interactive = _load_interactive_module()
    tickers = _split_csv(args.tickers)
    years = _parse_years(args.years)
    runtime_args = SimpleNamespace(
        query_planner="heuristic",
        manifest_path=args.manifest_path,
        source_gap_path="",
        bm25_index_dir=args.bm25_index_dir,
        object_bm25_index_dir=args.object_bm25_index_dir,
        bge_model="",
        bge_device="none",
        bge_first=False,
        market_evidence_path=args.market_evidence_path,
        market_snapshot_id=args.market_snapshot_id,
        market_as_of_date=args.market_as_of_date,
        output_root=args.output_root,
        evidence_top_k=args.evidence_top_k,
        object_top_k=args.object_top_k,
        max_context_rows=args.max_context_rows,
        ledger_max_rows=args.ledger_max_rows,
        context_runner="subprocess",
        reranker_top_k=0,
        reranker_candidate_limit=0,
        reranker_batch_size=8,
        reranker_max_length=2048,
        reranker_doc_max_chars=6000,
        llm_backend="smoke_no_synthesis",
        model="none",
        base_url="",
        chat_completions_path="",
        api_key_env="",
        quiet=True,
    )

    manifest_rows = interactive._read_jsonl(_repo_path(args.manifest_path))
    project_inventory = interactive._project_inventory(runtime_args, manifest_rows)
    query_contract = interactive._build_query_contract(runtime_args, args.prompt, tickers, years, project_inventory)
    run_id = interactive._run_id(args.prompt)
    run_root = REPO_ROOT / args.output_root / run_id
    run_root.mkdir(parents=True, exist_ok=True)
    paths = interactive._interactive_paths(run_root)
    state = interactive._create_sec_agent_state(
        args=runtime_args,
        prompt=args.prompt,
        run_id=run_id,
        run_root=run_root,
        tickers=tickers,
        years=years,
        project_inventory=project_inventory,
    )
    state.source_policy = str(query_contract.get("source_policy") or "")
    interactive._write_sec_agent_state(state)
    case = interactive._build_case(args.prompt, tickers, years, run_id, query_contract)
    interactive._write_jsonl(paths["cases_path"], [case])
    interactive._write_json(run_root / "query_contract.json", query_contract)
    interactive._add_state_artifact(state, "query_contract", run_root / "query_contract.json")
    state.mark_stage("plan_query", "completed", metadata={"task_count": len(query_contract.get("decomposed_tasks") or [])})
    state.mark_stage("validate_query_contract", "completed", metadata={"validation": query_contract.get("query_contract_validation")})

    _run_context_bm25_only(args, paths["cases_path"], paths["trace_dir"])
    trace, context_rows = interactive._load_trace_context(paths)
    interactive._add_state_artifact(
        state,
        "retrieved_context",
        paths["trace_dir"] / "trace_logs.jsonl",
        row_count=len(context_rows),
        metadata={"context_reranker": "none", "smoke": "bm25_only"},
    )
    state.mark_stage("retrieve_context", "completed", metadata={"context_row_count": len(context_rows), "context_reranker": "none"})
    trace, context_rows = interactive._stage_attach_market_snapshot_context(
        runtime_args,
        state,
        case,
        paths,
        trace,
        context_rows,
        lambda *a, **k: None,
    )
    ledger_rows = interactive._stage_build_runtime_ledger(runtime_args, state, case, paths, context_rows, lambda *a, **k: None)
    coverage_matrix = interactive._stage_build_coverage_matrix(state, case, query_contract, paths, context_rows, ledger_rows, lambda *a, **k: None)
    judgment_plan = interactive._stage_build_judgment_plan(state, case, paths, ledger_rows, coverage_matrix, lambda *a, **k: None)
    payload = _summary(
        run_root=run_root,
        query_contract=query_contract,
        context_rows=context_rows,
        ledger_rows=ledger_rows,
        coverage_matrix=coverage_matrix,
        judgment_plan=judgment_plan,
        elapsed_sec=time.time() - started,
    )
    summary_path = run_root / "market_snapshot_main_chain_smoke_summary.json"
    interactive._write_json(summary_path, payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
