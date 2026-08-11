from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
EVAL_SCRIPT = REPO_ROOT / "scripts" / "eval_multi_agent" / "eval_multi_agent_real_llm_chain.py"
DEFAULT_CASES_PATH = REPO_ROOT / "tests" / "fixtures" / "fin_agent_full_chain_multiturn_cases_v0_1.jsonl"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "eval" / "sec_cases" / "outputs" / "multi_agent_real_llm_pressure"
DEFAULT_CASE_IDS = [
    "fin_full_focused_amzn_margin_management_zh",
    "fin_full_standard_nvda_amd_market_zh",
]
TERMINAL_PASS = {"pass"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded multi-user pressure over real DeepSeek full-chain cases.")
    parser.add_argument("--cases-path", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--case-id", action="append", default=[], help="Case ID to run. Repeatable.")
    parser.add_argument("--users", type=int, default=2, help="Virtual users to run concurrently.")
    parser.add_argument("--iterations", type=int, default=1, help="Sequential iterations per virtual user.")
    parser.add_argument("--timeout-per-case-s", type=int, default=720)
    parser.add_argument("--stagger-s", type=float, default=1.0)
    parser.add_argument("--api-key-env", default=os.environ.get("API_KEY_ENV", "DEEPSEEK_API_KEY"))
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", "deepseek-v4-pro"))
    parser.add_argument("--base-url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument(
        "--data-repo-root",
        type=Path,
        default=Path(os.environ["FIN_AGENT_DATA_REPO_ROOT"]) if os.environ.get("FIN_AGENT_DATA_REPO_ROOT") else None,
        help="Optional repository root that owns the private data/indexes used by real evidence operators.",
    )
    parser.add_argument("--manifest-path", type=Path, default=None)
    parser.add_argument("--bm25-index-dir", type=Path, default=None)
    parser.add_argument("--object-bm25-index-dir", type=Path, default=None)
    parser.add_argument("--market-evidence-path", type=Path, default=None)
    parser.add_argument("--industry-evidence-path", type=Path, default=None)
    parser.add_argument("--sector-depth-pack-path", type=Path, default=None)
    parser.add_argument("--ledger-store-path", type=Path, default=None)
    parser.add_argument("--bge-model", type=Path, default=Path(os.environ["BGE_MODEL"]) if os.environ.get("BGE_MODEL") else None)
    parser.add_argument("--strict-child", action="store_true", help="Pass --strict to child eval runs.")
    parser.add_argument("--dry-run-operators", action="store_true", help="Disable real evidence operators for a cheap harness check.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    case_ids = args.case_id or DEFAULT_CASE_IDS
    if args.users < 1:
        raise SystemExit("--users must be >= 1")
    if args.iterations < 1:
        raise SystemExit("--iterations must be >= 1")
    if not os.environ.get(args.api_key_env):
        raise SystemExit(f"Missing required API key environment variable: {args.api_key_env}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    benchmark_id = _benchmark_id()
    benchmark_dir = args.output_dir / benchmark_id
    benchmark_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    jobs = [
        {
            "user_id": user_id,
            "iteration": iteration,
            "case_id": case_id,
            "ordinal": ordinal,
        }
        for user_id in range(1, args.users + 1)
        for iteration in range(1, args.iterations + 1)
        for ordinal, case_id in enumerate(case_ids, start=1)
    ]

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.users) as executor:
        futures = []
        for user_id in range(1, args.users + 1):
            futures.append(executor.submit(_run_user, user_id, jobs, args, benchmark_dir))
            time.sleep(max(0.0, args.stagger_s))
        for future in concurrent.futures.as_completed(futures):
            results.extend(future.result())

    summary = _aggregate(
        benchmark_id=benchmark_id,
        args=args,
        case_ids=case_ids,
        results=sorted(results, key=lambda row: (row["user_id"], row["iteration"], row["ordinal"])),
        elapsed_ms=int((time.time() - started) * 1000),
        benchmark_dir=benchmark_dir,
    )
    (benchmark_dir / "pressure_results.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in summary["results"]),
        encoding="utf-8",
    )
    (benchmark_dir / "pressure_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(_stdout_summary(summary), ensure_ascii=False, indent=2))
    return 0 if summary["gate_status"] == "pass" else 1


def _run_user(user_id: int, jobs: list[dict[str, Any]], args: argparse.Namespace, benchmark_dir: Path) -> list[dict[str, Any]]:
    user_jobs = [job for job in jobs if job["user_id"] == user_id]
    out: list[dict[str, Any]] = []
    for job in user_jobs:
        out.append(_run_case(job, args, benchmark_dir))
    return out


def _run_case(job: dict[str, Any], args: argparse.Namespace, benchmark_dir: Path) -> dict[str, Any]:
    run_id = (
        f"{_timestamp()}_pressure_u{job['user_id']:02d}_i{job['iteration']:02d}_"
        f"c{job['ordinal']:02d}_{job['case_id']}"
    )
    child_output_dir = benchmark_dir / "case_runs"
    stdout_path = benchmark_dir / f"{run_id}.stdout.log"
    stderr_path = benchmark_dir / f"{run_id}.stderr.log"
    command = [
        sys.executable,
        str(EVAL_SCRIPT),
        "--cases-path",
        str(args.cases_path),
        "--output-dir",
        str(child_output_dir),
        "--case-id",
        str(job["case_id"]),
        "--run-id",
        run_id,
        "--api-key-env",
        args.api_key_env,
        "--base-url",
        args.base_url,
        "--model",
        args.model,
    ]
    if not args.dry_run_operators:
        command.append("--real-evidence-operators")
    if args.strict_child:
        command.append("--strict")
    command.extend(_child_path_args(args))

    started = time.time()
    env = os.environ.copy()
    env["API_KEY_ENV"] = args.api_key_env
    env["BASE_URL"] = args.base_url
    env["MODEL_NAME"] = args.model
    process_result: subprocess.CompletedProcess[str] | None = None
    timed_out = False
    try:
        process_result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=args.timeout_per_case_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout_path.write_text(str(exc.stdout or ""), encoding="utf-8")
        stderr_path.write_text(str(exc.stderr or ""), encoding="utf-8")
    else:
        stdout_path.write_text(process_result.stdout, encoding="utf-8")
        stderr_path.write_text(process_result.stderr, encoding="utf-8")

    elapsed_ms = int((time.time() - started) * 1000)
    summary_path = child_output_dir / run_id / "real_chain_eval_summary.json"
    child_summary = _read_json(summary_path)
    metrics = child_summary.get("metrics") if isinstance(child_summary.get("metrics"), dict) else {}
    return {
        "user_id": job["user_id"],
        "iteration": job["iteration"],
        "ordinal": job["ordinal"],
        "case_id": job["case_id"],
        "run_id": run_id,
        "elapsed_ms": elapsed_ms,
        "exit_code": None if timed_out else (process_result.returncode if process_result else None),
        "timed_out": timed_out,
        "child_gate_status": child_summary.get("gate_status", ""),
        "child_case_count": metrics.get("case_count", 0),
        "child_pass_count": metrics.get("passed", 0),
        "child_fail_count": metrics.get("failed", 0),
        "child_total_tool_calls": metrics.get("total_tool_calls", 0),
        "summary_path": str(summary_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
    }


def _child_path_args(args: argparse.Namespace) -> list[str]:
    paths = {
        "manifest-path": args.manifest_path,
        "bm25-index-dir": args.bm25_index_dir,
        "object-bm25-index-dir": args.object_bm25_index_dir,
        "market-evidence-path": args.market_evidence_path,
        "industry-evidence-path": args.industry_evidence_path,
        "sector-depth-pack-path": args.sector_depth_pack_path,
        "ledger-store-path": args.ledger_store_path,
        "bge-model": args.bge_model,
    }
    if args.data_repo_root:
        root = args.data_repo_root
        paths = {
            "manifest-path": paths["manifest-path"]
            or root / "data" / "processed_private" / "manifests" / "sector_depth_full238_us_v0_2_mixed_with_8k_manifest_fy2023_2027.jsonl",
            "bm25-index-dir": paths["bm25-index-dir"]
            or root / "data" / "indexes" / "bm25" / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027",
            "object-bm25-index-dir": paths["object-bm25-index-dir"]
            or root / "data" / "indexes" / "bm25" / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_objects",
            "market-evidence-path": paths["market-evidence-path"]
            or root
            / "data"
            / "processed_private"
            / "market"
            / "evidence_packs"
            / "20260530_market_yahoo_chart_full238_6m_bars_3m_fmp_key_metrics_partial_v1_3m_market_evidence.jsonl",
            "industry-evidence-path": paths["industry-evidence-path"]
            or root
            / "data"
            / "processed_private"
            / "industry_data"
            / "20260530_industry_sector_depth_v0_2_with_eia_total_energy_retail_sales"
            / "industry_evidence_rows.jsonl",
            "sector-depth-pack-path": paths["sector-depth-pack-path"] or root / "configs" / "sector_depth_packs_v0_2.yaml",
            "ledger-store-path": paths["ledger-store-path"]
            or root / "data" / "processed_private" / "ledger" / "sector_depth_full238_us_v0_2_mixed_with_8k_fy2023_2027_core_ledger.duckdb",
            "bge-model": paths["bge-model"],
        }
    out: list[str] = []
    for name, path in paths.items():
        if path:
            out.extend([f"--{name}", str(path)])
    return out


def _aggregate(
    *,
    benchmark_id: str,
    args: argparse.Namespace,
    case_ids: list[str],
    results: list[dict[str, Any]],
    elapsed_ms: int,
    benchmark_dir: Path,
) -> dict[str, Any]:
    pass_count = sum(1 for row in results if _row_passed(row))
    timeout_count = sum(1 for row in results if row.get("timed_out"))
    exit_fail_count = sum(1 for row in results if row.get("exit_code") not in {0, None})
    durations = [int(row.get("elapsed_ms") or 0) for row in results]
    gate_status = "pass" if results and pass_count == len(results) else "fail"
    return {
        "schema_version": "fin_agent_real_llm_pressure_v0.1",
        "benchmark_id": benchmark_id,
        "benchmark_dir": str(benchmark_dir),
        "gate_status": gate_status,
        "users": args.users,
        "iterations": args.iterations,
        "case_ids": case_ids,
        "case_run_count": len(results),
        "pass_count": pass_count,
        "fail_count": len(results) - pass_count,
        "timeout_count": timeout_count,
        "exit_fail_count": exit_fail_count,
        "elapsed_ms": elapsed_ms,
        "duration_ms": {
            "min": min(durations) if durations else 0,
            "max": max(durations) if durations else 0,
            "avg": int(sum(durations) / len(durations)) if durations else 0,
        },
        "api_key_env": args.api_key_env,
        "api_key_saved": False,
        "raw_llm_response_saved": False,
        "dry_run_operators": bool(args.dry_run_operators),
        "results": results,
    }


def _row_passed(row: dict[str, Any]) -> bool:
    return (
        not row.get("timed_out")
        and row.get("exit_code") == 0
        and str(row.get("child_gate_status") or "") in TERMINAL_PASS
    )


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _stdout_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "benchmark_id": summary["benchmark_id"],
        "gate_status": summary["gate_status"],
        "users": summary["users"],
        "iterations": summary["iterations"],
        "case_ids": summary["case_ids"],
        "case_run_count": summary["case_run_count"],
        "pass_count": summary["pass_count"],
        "fail_count": summary["fail_count"],
        "timeout_count": summary["timeout_count"],
        "elapsed_ms": summary["elapsed_ms"],
        "duration_ms": summary["duration_ms"],
        "benchmark_dir": summary["benchmark_dir"],
    }


def _benchmark_id() -> str:
    return f"{_timestamp()}_fin_agent_real_llm_pressure"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
