from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
SCRIPTS_ROOT = REPO_ROOT / "scripts"
for path in (SRC_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _jsonl_first(path: Path) -> dict[str, Any]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            return json.loads(line)
    raise ValueError(f"No JSONL row found: {path}")


def _repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


class TimedSearch:
    def __init__(self, obj: Any) -> None:
        self.obj = obj
        self.calls = 0
        self.elapsed_sec = 0.0
        self.unique_filter_keys: set[str] = set()

    def search(self, query: str, top_k: int = 10, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self.calls += 1
        self.unique_filter_keys.add(json.dumps(filters or {}, sort_keys=True, ensure_ascii=False))
        started = time.perf_counter()
        rows = self.obj.search(query, top_k=top_k, filters=filters)
        self.elapsed_sec += time.perf_counter() - started
        return rows

    def __getattr__(self, name: str) -> Any:
        return getattr(self.obj, name)


def _time_call(fn: Any) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - started


def _status_from_thresholds(payload: dict[str, Any], args: argparse.Namespace) -> tuple[str, list[str]]:
    failures: list[str] = []
    warnings: list[str] = []
    retrieval = payload["retrieval"]
    ledger = payload["runtime_ledger"]
    if retrieval["bm25_elapsed_sec"] > args.max_bm25_elapsed_sec:
        failures.append("bm25_elapsed_over_budget")
    if retrieval["candidate_generation_sec"] > args.max_candidate_generation_sec:
        warnings.append("candidate_generation_over_budget")
    if ledger["second_cached_elapsed_sec"] > args.max_cached_ledger_sec:
        warnings.append("cached_ledger_over_budget")
    if payload["coverage_matrix"]["elapsed_sec"] > args.max_coverage_sec:
        warnings.append("coverage_matrix_over_budget")
    if failures:
        return "fail", failures + warnings
    if warnings:
        return "warn", warnings
    return "pass", []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile local SEC agent non-LLM latency using one existing case.")
    parser.add_argument(
        "--case-path",
        default="reports/quality/resume_closeout/market_main_chain_smoke_outputs/20260526_031835_f7b01aec3a/case.jsonl",
    )
    parser.add_argument(
        "--bm25-index-dir",
        default="data/indexes/bm25/sec_tech_primary_mixed_10k_latest_10q_fy2023_2027",
    )
    parser.add_argument(
        "--object-bm25-index-dir",
        default="data/indexes/bm25/sec_tech_primary_mixed_10k_latest_10q_fy2023_2027_objects",
    )
    parser.add_argument(
        "--market-evidence-path",
        default="data/processed_private/market/evidence_packs/20260525_market_yahoo_chart_full30_3m_fmp_valuation_v1_3m_market_evidence.jsonl",
    )
    parser.add_argument("--evidence-top-k", type=int, default=4)
    parser.add_argument("--object-top-k", type=int, default=4)
    parser.add_argument("--ledger-max-rows", type=int, default=90)
    parser.add_argument("--output-path", default="reports/quality/latency_profile/sec_agent_latency_profile_local_latest.json")
    parser.add_argument("--max-bm25-elapsed-sec", type=float, default=2.5)
    parser.add_argument("--max-candidate-generation-sec", type=float, default=35.0)
    parser.add_argument("--max-cached-ledger-sec", type=float, default=5.0)
    parser.add_argument("--max-coverage-sec", type=float, default=2.0)
    parser.add_argument("--fail-on-warn", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    from retrieval.bm25_retriever import BM25Retriever
    from retrieval.object_bm25_retriever import ObjectBM25Retriever
    from sec_agent.coverage_matrix import build_coverage_matrix

    bench = _load_module("run_sec_benchmark_eval_latency_profile", REPO_ROOT / "scripts" / "eval_sec_benchmark" / "run_sec_benchmark_eval.py")
    interactive = _load_module("sec_agent_interactive_latency_profile", REPO_ROOT / "scripts" / "cloud" / "sec_agent_interactive.py")

    case = _jsonl_first(_repo_path(args.case_path))
    timings: dict[str, float] = {}
    bm25, timings["bm25_init_sec"] = _time_call(lambda: TimedSearch(BM25Retriever(_repo_path(args.bm25_index_dir))))
    object_bm25, timings["object_bm25_init_sec"] = _time_call(
        lambda: TimedSearch(ObjectBM25Retriever(_repo_path(args.object_bm25_index_dir)))
    )
    context_rows, timings["candidate_generation_sec"] = _time_call(
        lambda: bench._pipeline_context_rows(case, bm25, object_bm25, args.evidence_top_k, args.object_top_k)
    )

    market_rows: list[dict[str, Any]] = []
    market_path = _repo_path(args.market_evidence_path)
    if market_path.exists():
        market_rows, timings["market_attach_load_sec"] = _time_call(
            lambda: interactive._load_market_context_rows(str(market_path), case.get("query_contract") or {})
        )
    context_rows_with_market = interactive._append_unique_context_rows(context_rows, market_rows)

    ledger_args = SimpleNamespace(object_bm25_index_dir=args.object_bm25_index_dir, ledger_max_rows=args.ledger_max_rows)
    if hasattr(interactive, "_load_object_records_cached"):
        interactive._load_object_records_cached.cache_clear()
    ledger_first, timings["ledger_first_elapsed_sec"] = _time_call(
        lambda: interactive._build_runtime_ledger(case, context_rows_with_market, ledger_args)
    )
    ledger_second, timings["ledger_second_cached_elapsed_sec"] = _time_call(
        lambda: interactive._build_runtime_ledger(case, context_rows_with_market, ledger_args)
    )
    coverage_matrix, timings["coverage_elapsed_sec"] = _time_call(
        lambda: build_coverage_matrix(
            case=case,
            query_contract=case.get("query_contract") or {},
            context_rows=context_rows_with_market,
            ledger_rows=ledger_second,
            run_id=str(case.get("case_id") or ""),
        )
    )

    selection_counts = Counter(str(row.get("selection_method") or "") for row in context_rows)
    source_kind_counts = Counter(str(row.get("source_kind") or "") for row in context_rows)
    payload = {
        "schema_version": "sec_agent_latency_profile_v0.1",
        "case_id": case.get("case_id"),
        "case_path": str(_repo_path(args.case_path)),
        "indexes": {
            "bm25_index_dir": str(_repo_path(args.bm25_index_dir)),
            "object_bm25_index_dir": str(_repo_path(args.object_bm25_index_dir)),
        },
        "retrieval": {
            "bm25_records": len(bm25.records),
            "object_records": len(object_bm25.records),
            "bm25_init_sec": round(timings["bm25_init_sec"], 4),
            "object_bm25_init_sec": round(timings["object_bm25_init_sec"], 4),
            "candidate_generation_sec": round(timings["candidate_generation_sec"], 4),
            "bm25_calls": bm25.calls,
            "bm25_elapsed_sec": round(bm25.elapsed_sec, 4),
            "bm25_unique_filters": len(bm25.unique_filter_keys),
            "object_bm25_calls": object_bm25.calls,
            "object_bm25_elapsed_sec": round(object_bm25.elapsed_sec, 4),
            "object_bm25_unique_filters": len(object_bm25.unique_filter_keys),
            "context_row_count": len(context_rows),
            "selection_counts": dict(selection_counts),
            "source_kind_counts": dict(source_kind_counts),
        },
        "market_context": {
            "market_evidence_path": str(market_path),
            "market_row_count": len(market_rows),
            "elapsed_sec": round(timings.get("market_attach_load_sec", 0.0), 4),
            "context_row_count_after_market": len(context_rows_with_market),
        },
        "runtime_ledger": {
            "first_elapsed_sec": round(timings["ledger_first_elapsed_sec"], 4),
            "second_cached_elapsed_sec": round(timings["ledger_second_cached_elapsed_sec"], 4),
            "first_row_count": len(ledger_first),
            "second_row_count": len(ledger_second),
            "cache_speedup_sec": round(timings["ledger_first_elapsed_sec"] - timings["ledger_second_cached_elapsed_sec"], 4),
        },
        "coverage_matrix": {
            "elapsed_sec": round(timings["coverage_elapsed_sec"], 4),
            "task_count": len(coverage_matrix.get("tasks") or []),
            "summary": coverage_matrix.get("summary") or {},
        },
        "thresholds": {
            "max_bm25_elapsed_sec": args.max_bm25_elapsed_sec,
            "max_candidate_generation_sec": args.max_candidate_generation_sec,
            "max_cached_ledger_sec": args.max_cached_ledger_sec,
            "max_coverage_sec": args.max_coverage_sec,
        },
    }
    status, reasons = _status_from_thresholds(payload, args)
    payload["status"] = status
    payload["reasons"] = reasons

    output_path = _repo_path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "reasons": reasons, "output_path": str(output_path), "retrieval": payload["retrieval"], "runtime_ledger": payload["runtime_ledger"]}, ensure_ascii=False, indent=2))
    if status == "fail" or (args.fail_on_warn and status == "warn"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
